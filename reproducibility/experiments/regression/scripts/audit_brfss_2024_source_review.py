"""Audit CDC BRFSS 2024 as a source-review-only regression candidate."""

from __future__ import annotations

import argparse
import html
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_brfss_source_review_v1"
DATASET_ID = "brfss_2024_llcp_source_review"
SOURCE_FAMILY = "cdc_brfss"
SOURCE_URL = "https://www.cdc.gov/brfss/annual_data/annual_2024.html"
ANNUAL_INDEX_URL = "https://www.cdc.gov/brfss/annual_data/annual_data.htm"
DOCUMENTATION_URL = "https://www.cdc.gov/brfss/data_documentation/index.htm"
DEFAULT_OUT_DIR = Path("experiments/regression/audits") / DATASET_ID

REQUIRED_LINK_PATTERNS = {
    "overview": ("overview",),
    "codebook_zip": ("codebook",),
    "calculated_variables": ("calculated variables in data files",),
    "data_quality_report": ("summary data quality report",),
    "complex_sampling_weights": ("complex sampling weights",),
    "response_rates": ("weighted response rates",),
    "comparability": ("comparability of data",),
    "weighting_formula": ("weighting formula",),
    "ascii_data": ("data (ascii)",),
    "xpt_data": ("sas transport",),
    "variable_layout": ("variable layout",),
    "summary_matrix": ("summary", "matrix", "calculated variables"),
}

TARGET_CANDIDATE_VARIABLES = {
    "bmi_calculated": "_BMI5",
    "physical_health_not_good_days": "PHYSHLTH",
    "mental_health_not_good_days": "MENTHLTH",
    "activity_limited_days": "POORHLTH",
    "general_health_ordinal": "GENHLTH",
    "reported_weight_pounds": "WEIGHT2",
    "reported_height_feet_inches": "HEIGHT3",
}

SENSITIVE_OR_GROUP_CANDIDATE_VARIABLES = [
    "_STATE",
    "SEXVAR",
    "LANDSEX3",
    "CELLSEX3",
    "_AGEG5YR",
    "_AGE80",
    "_RACE",
    "_RACEGR4",
    "_HISPANC",
    "EDUCA",
    "INCOME3",
    "EMPLOY1",
    "RENTHOM1",
]


@dataclass(frozen=True)
class ParsedLink:
    label: str
    url: str


class LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[ParsedLink] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        label = normalize_text("".join(self._parts))
        if label:
            self.links.append(ParsedLink(label=label, url=urljoin(self.base_url, self._href)))
        self._href = None
        self._parts = []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--annual-index-url", default=ANNUAL_INDEX_URL)
    parser.add_argument("--documentation-url", default=DOCUMENTATION_URL)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--offline-html",
        default=None,
        help="Optional local HTML page fixture; otherwise the CDC source page is fetched.",
    )
    parser.add_argument(
        "--offline-codebook-zip",
        default=None,
        help="Optional local codebook ZIP fixture; otherwise the CDC codebook ZIP is fetched.",
    )
    parser.add_argument(
        "--skip-codebook-fetch",
        action="store_true",
        help="Skip codebook download and record only source-page metadata.",
    )
    return parser.parse_args()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def html_to_text(source_html: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", source_html)
    return normalize_text(without_tags)


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "cpfi-regression-source-audit/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8", errors="replace")


def collect_links(source_html: str, base_url: str) -> list[ParsedLink]:
    parser = LinkParser(base_url)
    parser.feed(source_html)
    return parser.links


def find_required_links(links: list[ParsedLink]) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for key, patterns in REQUIRED_LINK_PATTERNS.items():
        for link in links:
            label = link.label.lower()
            if all(pattern in label for pattern in patterns):
                found[key] = {"label": link.label, "url": link.url}
                break
    return found


def first_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return normalize_text(match.group(1)) if match else None


def parse_codebook_zip(zip_bytes: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        html_members = [
            info for info in archive.infolist() if info.filename.lower().endswith(".html")
        ]
        if len(html_members) != 1:
            raise ValueError(
                "Expected exactly one HTML codebook member, "
                f"found {[info.filename for info in html_members]}"
            )
        member = html_members[0]
        raw = archive.read(member.filename)
    codebook_html = raw.decode("latin1", errors="replace")
    plain = html_to_text(codebook_html)
    variables = re.findall(r"SAS\s+Variable\s+Name:\s*([A-Z0-9_]+)", plain)
    unique_variables = list(dict.fromkeys(variables))
    candidate_variables = {}
    for candidate_id, variable in TARGET_CANDIDATE_VARIABLES.items():
        candidate_variables[candidate_id] = {
            "variable": variable,
            "present_in_codebook": variable in unique_variables,
            "label": variable_label(plain, variable),
        }
    group_variables = {
        variable: variable in unique_variables
        for variable in SENSITIVE_OR_GROUP_CANDIDATE_VARIABLES
    }
    return {
        "zip_bytes": len(zip_bytes),
        "member_name": member.filename,
        "member_uncompressed_bytes": int(member.file_size),
        "sas_variable_name_count": len(unique_variables),
        "candidate_target_variables": candidate_variables,
        "sensitive_or_group_candidate_variables": group_variables,
    }


def variable_label(plain_codebook: str, variable: str) -> str | None:
    variable_pattern = re.compile(
        r"SAS\s+Variable\s+Name:\s*" + re.escape(variable) + r"\b",
        flags=re.IGNORECASE,
    )
    label_pattern = re.compile(
        r"Label:\s*(?P<label>.*?)\s+Section\s+Name:",
        flags=re.IGNORECASE,
    )
    for entry in re.split(r"(?=Label:\s)", plain_codebook):
        if not variable_pattern.search(entry):
            continue
        match = label_pattern.search(entry)
        return normalize_text(match.group("label")) if match else None
    return None


def build_payload(
    *,
    source_html: str,
    source_url: str,
    annual_index_url: str,
    documentation_url: str,
    codebook_zip: bytes | None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    page_text = html_to_text(source_html)
    links = collect_links(source_html, source_url)
    required_links = find_required_links(links)
    codebook = parse_codebook_zip(codebook_zip) if codebook_zip is not None else None
    records = first_int(r"There are\s+([0-9,]+)\s+records\s+for\s+2024", page_text)
    xpt_variables = first_int(r"contains\s+([0-9,]+)\s+variables", page_text)
    fixed_record_length = first_int(r"fixed record length of\s+([0-9,]+)\s+positions", page_text)
    last_reviewed = first_match(r"Last Reviewed:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", page_text)
    release_month = first_match(r"Data \(ASCII\).*?([A-Za-z]+,\s+\d{4})", page_text)
    missing_required_links = sorted(set(REQUIRED_LINK_PATTERNS) - set(required_links))
    return {
        "schema": SCHEMA,
        "dataset_id": DATASET_ID,
        "source": "CDC Behavioral Risk Factor Surveillance System",
        "source_url": source_url,
        "source_family": SOURCE_FAMILY,
        "audit_status": "source_review_only_modeling_blocked",
        "generated_at_utc": generated_at_utc
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_pages": {
            "annual_2024": source_url,
            "annual_index": annual_index_url,
            "documentation_index": documentation_url,
        },
        "summary": {
            "records_reported": records,
            "xpt_variable_count_reported": xpt_variables,
            "codebook_sas_variable_count": None
            if codebook is None
            else codebook["sas_variable_name_count"],
            "fixed_record_length_reported": fixed_record_length,
            "data_release_month": release_month,
            "last_reviewed": last_reviewed,
            "required_source_link_count": len(required_links),
            "missing_required_source_link_count": len(missing_required_links),
            "modeling_approved": False,
            "runner_config_approved": False,
        },
        "official_artifacts": required_links,
        "missing_required_artifacts": missing_required_links,
        "codebook_review": codebook,
        "coverage_and_design_notes": [
            "2024 aggregate combined landline and cell phone data include 49 states, DC, Guam, Puerto Rico, and the US Virgin Islands.",
            "Tennessee is excluded because minimum collection requirements were not met.",
            "The page records 2011-era raking and cellphone-frame changes; pre-2011 trend comparisons require a separate comparability design.",
            "The page states that the 2024 data were modified for executive-order compliance and that removed questions can induce missing-value inconsistencies.",
            "Complex sampling weights and module-analysis preparation must be handled before any population-facing metric.",
        ],
        "target_policy": {
            "status": "not_selected",
            "candidate_variables_verified_in_codebook": {}
            if codebook is None
            else codebook["candidate_target_variables"],
            "required_before_modeling": [
                "choose exactly one regression target and justify scale",
                "parse target value labels and special missing codes from the codebook",
                "define whether the target is continuous, count-like, bounded, ordinal, or transformed",
                "define target-domain endpoint policy before conformal interval evaluation",
                "define whether survey weights are used or explicitly excluded as benchmark-only",
            ],
        },
        "group_policy": {
            "status": "not_selected",
            "candidate_variables_checked": {}
            if codebook is None
            else codebook["sensitive_or_group_candidate_variables"],
            "required_before_modeling": [
                "choose diagnostic group variables and remove direct group leakage from features when required",
                "check sparse cells and missing-value codes for all group variables",
                "separate diagnostic group coverage from fairness or population inference",
            ],
        },
        "access_policy": {
            "source_is_official_cdc_gov": source_url.startswith("https://www.cdc.gov/"),
            "raw_data_downloaded": False,
            "raw_data_committed_to_git": False,
            "large_raw_files": [
                "ASCII ZIP listed as 41.5 MB",
                "SAS Transport ZIP listed as 64.3 MB",
            ],
            "raw_cache_policy": "Download raw files only into ignored local cache after target and group policy are approved.",
        },
        "blockers": [
            "raw data not downloaded or profiled",
            "target variable not selected",
            "group variables not selected",
            "BRFSS special missing codes and skip patterns not parsed",
            "survey weights and complex design not integrated",
            "question removals and induced missingness not audited",
            "no split policy for state/module/year structure",
            "no health, clinical, population, or fairness claim may be made",
        ],
        "next_actions": [
            "Download ASCII or XPT raw file into ignored cache only after selecting target and groups.",
            "Parse variable layout and codebook value labels for candidate targets.",
            "Build a small target-specific profile with missingness, special codes, and state/module availability.",
            "Predeclare survey-weight handling and benchmark-only non-claims before runner config.",
        ],
        "non_claims": [
            "This audit is not a dataset profile.",
            "This audit is not approval to run BRFSS models.",
            "This audit is not clinical guidance.",
            "This audit is not population health inference.",
            "This audit is not fairness or discrimination evidence.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# BRFSS 2024 Source Review Audit",
        "",
        f"- Dataset id: `{payload['dataset_id']}`",
        f"- Source family: `{payload['source_family']}`",
        f"- Status: `{payload['audit_status']}`",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Records reported: {summary['records_reported']}",
        f"- XPT variables reported: {summary['xpt_variable_count_reported']}",
        f"- Codebook SAS variables parsed: {summary['codebook_sas_variable_count']}",
        f"- Fixed record length: {summary['fixed_record_length_reported']}",
        f"- Data release month: {summary['data_release_month']}",
        f"- Last reviewed: {summary['last_reviewed']}",
        f"- Required source links found: {summary['required_source_link_count']}",
        f"- Missing required source links: {summary['missing_required_source_link_count']}",
        f"- Modeling approved: `{summary['modeling_approved']}`",
        "",
        "## Source Pages",
        "",
    ]
    for key, url in payload["source_pages"].items():
        lines.append(f"- `{key}`: {url}")
    lines.extend(["", "## Official Artifacts", ""])
    for key, row in sorted(payload["official_artifacts"].items()):
        lines.append(f"- `{key}`: {row['label']} - {row['url']}")
    if payload["missing_required_artifacts"]:
        lines.extend(["", "## Missing Required Artifacts", ""])
        lines.extend(f"- `{key}`" for key in payload["missing_required_artifacts"])
    lines.extend(["", "## Candidate Target Variables", ""])
    candidates = payload["target_policy"]["candidate_variables_verified_in_codebook"]
    if candidates:
        for candidate_id, row in candidates.items():
            lines.append(
                "- "
                f"`{candidate_id}` -> `{row['variable']}`: "
                f"present `{row['present_in_codebook']}`, label `{row['label']}`"
            )
    else:
        lines.append("- Codebook parsing skipped.")
    lines.extend(["", "## Group Candidate Variables", ""])
    groups = payload["group_policy"]["candidate_variables_checked"]
    if groups:
        for variable, present in groups.items():
            lines.append(f"- `{variable}`: present `{present}`")
    else:
        lines.append("- Codebook parsing skipped.")
    lines.extend(["", "## Coverage And Design Notes", ""])
    lines.extend(f"- {note}" for note in payload["coverage_and_design_notes"])
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {blocker}" for blocker in payload["blockers"])
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in payload["next_actions"])
    lines.extend(["", "## Non-Claims", ""])
    lines.extend(f"- {non_claim}" for non_claim in payload["non_claims"])
    return "\n".join(lines).rstrip() + "\n"


def profile_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "cpfi_regression_brfss_source_review_profile_v1",
        "dataset_id": payload["dataset_id"],
        "source": payload["source"],
        "source_url": payload["source_url"],
        "source_family": payload["source_family"],
        "audit_status": payload["audit_status"],
        "records_reported": payload["summary"]["records_reported"],
        "xpt_variable_count_reported": payload["summary"]["xpt_variable_count_reported"],
        "codebook_sas_variable_count": payload["summary"]["codebook_sas_variable_count"],
        "target_selected": False,
        "group_selected": False,
        "raw_data_downloaded": False,
        "modeling_approved": False,
        "candidate_target_variables": payload["target_policy"][
            "candidate_variables_verified_in_codebook"
        ],
        "candidate_group_variables": payload["group_policy"][
            "candidate_variables_checked"
        ],
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    lines = [
        "# BRFSS 2024 Source Review Profile",
        "",
        f"- Dataset id: `{profile['dataset_id']}`",
        f"- Source family: `{profile['source_family']}`",
        f"- Status: `{profile['audit_status']}`",
        f"- Records reported: {profile['records_reported']}",
        f"- XPT variables reported: {profile['xpt_variable_count_reported']}",
        f"- Codebook SAS variables parsed: {profile['codebook_sas_variable_count']}",
        f"- Target selected: `{profile['target_selected']}`",
        f"- Group selected: `{profile['group_selected']}`",
        f"- Raw data downloaded: `{profile['raw_data_downloaded']}`",
        f"- Modeling approved: `{profile['modeling_approved']}`",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    if args.offline_html:
        source_html = Path(args.offline_html).read_text(encoding="utf-8")
    else:
        source_html = fetch_text(args.source_url)
    codebook_zip = None
    if not args.skip_codebook_fetch:
        if args.offline_codebook_zip:
            codebook_zip = Path(args.offline_codebook_zip).read_bytes()
        else:
            links = find_required_links(collect_links(source_html, args.source_url))
            codebook_url = links.get("codebook_zip", {}).get("url")
            if not codebook_url:
                raise ValueError("Could not find BRFSS codebook ZIP link on source page")
            codebook_zip = fetch_bytes(codebook_url)
    payload = build_payload(
        source_html=source_html,
        source_url=args.source_url,
        annual_index_url=args.annual_index_url,
        documentation_url=args.documentation_url,
        codebook_zip=codebook_zip,
    )
    profile = profile_from_payload(payload)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "audit.json", payload)
    atomic_write_text(out_dir / "audit.md", render_markdown(payload))
    atomic_write_json(out_dir / "profile.json", profile)
    atomic_write_text(out_dir / "profile.md", render_profile_markdown(profile))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
