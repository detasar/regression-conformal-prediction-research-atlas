"""Audit IPUMS CPS as a source-review-only regression candidate."""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_ipums_cps_source_review_v1"
DATASET_ID = "ipums_cps_source_review"
SOURCE = "IPUMS CPS harmonized Current Population Survey microdata"
SOURCE_FAMILY = "ipums_cps"
SOURCE_URL = "https://cps.ipums.org/cps/"
DOCUMENTATION_URL = "https://cps.ipums.org/cps/documentation.shtml"
INSTRUCTIONS_URL = "https://cps.ipums.org/cps/instructions.shtml"
FAQ_URL = "https://cps.ipums.org/cps-action/faq"
SAMPLE_IDS_URL = "https://cps.ipums.org/cps-action/samples/sample_ids"
SAMPLES_URL = "https://cps.ipums.org/cps/samples.shtml"
VARIABLE_GROUPS_URL = "https://cps.ipums.org/cps-action/variables/group"
REVISIONS_URL = "https://cps.ipums.org/cps-action/revisions"
API_DOC_URL = "https://developer.ipums.org/docs/v2/apiprogram/apis/microdata/"
API_WORKFLOW_URL = "https://developer.ipums.org/docs/v2/workflows/create_extracts/microdata/"
DEFAULT_OUT_DIR = Path("experiments/regression/audits") / DATASET_ID

CANDIDATE_VARIABLE_URLS = {
    "hourly_wage": "https://cps.ipums.org/cps-action/variables/HOURWAGE",
    "weekly_earnings": "https://cps.ipums.org/cps-action/variables/EARNWEEK",
    "wage_salary_income": "https://cps.ipums.org/cps-action/variables/INCWAGE",
    "total_personal_income": "https://cps.ipums.org/cps-action/variables/INCTOT",
    "usual_hours_all_jobs": "https://cps.ipums.org/cps-action/variables/UHRSWORKT",
}

API_FEATURE_PHRASES = {
    "rectangular_person_extracts": "Extracts rectangularized on person records",
    "preselected_variables": "Pre-selected variables included by default",
    "csv_or_fixed_width": "CSV or fixed-width data file output",
    "stata_spss_sas": "Formatted data files for Stata, SPSS, and SAS",
    "hierarchical_extracts": "Hierarchical extracts",
    "case_selection": "Case Selection",
    "attached_characteristics": "Attached Characteristics",
    "data_quality_flags": "Data Quality Flags",
    "adjust_monetary_values": "Adjustment of monetary values",
}

API_UNSUPPORTED_PHRASES = {
    "custom_sample_sizes": "Custom sample sizes",
    "longitudinal_extracts": "Longitudinal extracts",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--documentation-url", default=DOCUMENTATION_URL)
    parser.add_argument("--instructions-url", default=INSTRUCTIONS_URL)
    parser.add_argument("--faq-url", default=FAQ_URL)
    parser.add_argument("--sample-ids-url", default=SAMPLE_IDS_URL)
    parser.add_argument("--samples-url", default=SAMPLES_URL)
    parser.add_argument("--variable-groups-url", default=VARIABLE_GROUPS_URL)
    parser.add_argument("--revisions-url", default=REVISIONS_URL)
    parser.add_argument("--api-doc-url", default=API_DOC_URL)
    parser.add_argument("--api-workflow-url", default=API_WORKFLOW_URL)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--offline-source-html",
        default=None,
        help="Optional IPUMS CPS home HTML fixture.",
    )
    parser.add_argument(
        "--offline-documentation-html",
        default=None,
        help="Optional documentation-page HTML fixture.",
    )
    parser.add_argument(
        "--offline-instructions-html",
        default=None,
        help="Optional extract-instructions HTML fixture.",
    )
    parser.add_argument("--offline-faq-html", default=None)
    parser.add_argument("--offline-sample-ids-html", default=None)
    parser.add_argument("--offline-samples-html", default=None)
    parser.add_argument("--offline-variable-groups-html", default=None)
    parser.add_argument("--offline-revisions-html", default=None)
    parser.add_argument("--offline-api-doc-html", default=None)
    parser.add_argument("--offline-api-workflow-html", default=None)
    parser.add_argument(
        "--offline-variable-pages-json",
        default=None,
        help="Optional JSON object keyed by candidate variable id containing HTML.",
    )
    return parser.parse_args()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def html_to_text(source_html: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", source_html)
    return normalize_text(without_tags)


def html_lines(source_html: str) -> list[str]:
    lines = []
    for raw_line in source_html.splitlines():
        line = normalize_text(re.sub(r"<[^>]+>", " ", raw_line))
        if line:
            lines.append(line)
    return lines


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "cpfi-regression-source-audit/1.0"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", errors="replace")
        except (HTTPError, TimeoutError, URLError) as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"IPUMS CPS source request failed after retries: {url}") from last_error


def load_text_fixture(path: str | None, url: str) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    return fetch_text(url)


def parse_sample_ids(sample_ids_html: str) -> dict[str, Any]:
    sample_rows: list[dict[str, str]] = []
    pattern = re.compile(
        r"<span[^>]*>\s*(cps\d{4}_[0-9]{2}[bs])\s*</span>.*?"
        r"<td>\s*IPUMS-CPS,\s*(.*?)\s*</td>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(sample_ids_html):
        sample_rows.append(
            {
                "sample_id": match.group(1),
                "description": normalize_text(re.sub(r"<[^>]+>", " ", match.group(2))),
            }
        )
    latest = sample_rows[-1] if sample_rows else {}
    asec_count = sum("ASEC" in row["description"] for row in sample_rows)
    monthly_count = len(sample_rows) - asec_count
    return {
        "sample_id_count": len(sample_rows),
        "asec_sample_id_count": asec_count,
        "monthly_sample_id_count": monthly_count,
        "earliest_sample_id": sample_rows[0]["sample_id"] if sample_rows else None,
        "earliest_sample_description": sample_rows[0]["description"] if sample_rows else None,
        "latest_sample_id": latest.get("sample_id"),
        "latest_sample_description": latest.get("description"),
        "sample_id_examples": sample_rows[:3] + sample_rows[-3:] if len(sample_rows) >= 6 else sample_rows,
    }


def parse_revision_summary(revisions_html: str) -> dict[str, Any]:
    lines = html_lines(revisions_html)
    banner = next((line for line in lines if "monthly data are now available" in line), None)
    latest_date = next(
        (
            line
            for line in lines
            if re.match(r"^[A-Z][a-z]+ \d{1,2}, \d{4}$", line)
        ),
        None,
    )
    latest_added_samples = []
    if latest_date:
        date_index = lines.index(latest_date)
        for line in lines[date_index + 1 : date_index + 10]:
            if "Basic monthly variables are now available" in line or "ASEC data" in line:
                latest_added_samples.append(line)
    return {
        "top_banner": banner,
        "latest_revision_date": latest_date,
        "latest_added_sample_notes": latest_added_samples,
        "mentions_2025_shutdown_gap": "October 2025 data were not collected"
        in html_to_text(revisions_html),
    }


def parse_api_capabilities(api_doc_html: str, api_workflow_html: str) -> dict[str, Any]:
    doc_text = html_to_text(api_doc_html)
    workflow_text = html_to_text(api_workflow_html)
    features = {
        key: phrase in doc_text for key, phrase in API_FEATURE_PHRASES.items()
    }
    unsupported = {
        key: phrase in doc_text for key, phrase in API_UNSUPPORTED_PHRASES.items()
    }
    return {
        "api_version": "2",
        "collection_code": "cps",
        "extract_endpoint_documented": (
            "https://api.ipums.org/extracts?collection=cps&version=2" in workflow_text
        ),
        "api_key_required_documented": (
            "IPUMS_API_KEY" in api_workflow_html and "Authorization:" in api_workflow_html
        ),
        "metadata_api_gap_documented": "no metadata support in the API for IPUMS microdata collections"
        in doc_text,
        "supported_features": features,
        "supported_feature_count": sum(features.values()),
        "unsupported_features": unsupported,
        "unsupported_feature_count": sum(unsupported.values()),
    }


def parse_variable_page(candidate_id: str, variable_name: str, page_html: str) -> dict[str, Any]:
    text = html_to_text(page_html)
    description = None
    description_match = re.search(
        r'<div id="description_section">(.*?)(?:<div id="comparability_section"|<div id="universe_section")',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if description_match:
        description = html_to_text(description_match.group(1))[:500]
    keywords = {
        "topcoded": "topcoded" in text.lower(),
        "missing_code": "Missing" in text or "N.I.U" in text or "NIU" in text,
        "inflation_adjustment_needed": "adjust for inflation" in text.lower()
        or "Adjust Monetary Values" in text,
        "weight_guidance_present": "Researchers should use" in text and "weight" in text,
        "negative_values_possible": "Values can be negative" in text,
    }
    return {
        "candidate_id": candidate_id,
        "variable": variable_name,
        "url": CANDIDATE_VARIABLE_URLS[candidate_id],
        "present": variable_name.upper() in text.upper(),
        "description_excerpt": description,
        "risk_keywords": keywords,
        "risk_keyword_count": sum(keywords.values()),
    }


def build_payload(
    *,
    source_html: str,
    documentation_html: str,
    instructions_html: str,
    faq_html: str,
    sample_ids_html: str,
    samples_html: str,
    variable_groups_html: str,
    revisions_html: str,
    api_doc_html: str,
    api_workflow_html: str,
    variable_pages: dict[str, str],
    generated_at_utc: str | None = None,
    source_url: str = SOURCE_URL,
    documentation_url: str = DOCUMENTATION_URL,
    instructions_url: str = INSTRUCTIONS_URL,
    faq_url: str = FAQ_URL,
    sample_ids_url: str = SAMPLE_IDS_URL,
    samples_url: str = SAMPLES_URL,
    variable_groups_url: str = VARIABLE_GROUPS_URL,
    revisions_url: str = REVISIONS_URL,
    api_doc_url: str = API_DOC_URL,
    api_workflow_url: str = API_WORKFLOW_URL,
) -> dict[str, Any]:
    source_text = html_to_text(source_html)
    documentation_text = html_to_text(documentation_html)
    instructions_text = html_to_text(instructions_html)
    faq_text = html_to_text(faq_html)
    samples_text = html_to_text(samples_html)
    variable_groups_text = html_to_text(variable_groups_html)
    sample_summary = parse_sample_ids(sample_ids_html)
    revision_summary = parse_revision_summary(revisions_html)
    api_capabilities = parse_api_capabilities(api_doc_html, api_workflow_html)
    variables = {
        candidate_id: parse_variable_page(
            candidate_id,
            url.rsplit("/", 1)[-1].upper(),
            variable_pages.get(candidate_id, ""),
        )
        for candidate_id, url in CANDIDATE_VARIABLE_URLS.items()
    }
    present_variable_count = sum(row["present"] for row in variables.values())
    return {
        "schema": SCHEMA,
        "dataset_id": DATASET_ID,
        "source": SOURCE,
        "source_family": SOURCE_FAMILY,
        "source_url": source_url,
        "audit_status": "source_review_only_modeling_blocked",
        "generated_at_utc": generated_at_utc
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_pages": {
            "home": source_url,
            "documentation": documentation_url,
            "instructions": instructions_url,
            "faq": faq_url,
            "sample_ids": sample_ids_url,
            "samples": samples_url,
            "variable_groups": variable_groups_url,
            "revisions": revisions_url,
            "api_microdata_capabilities": api_doc_url,
            "api_extract_workflow": api_workflow_url,
        },
        "summary": {
            "home_identifies_ipums_cps": "IPUMS" in source_text and "CPS" in source_text,
            "documentation_lists_variables": "Variables" in documentation_text,
            "documentation_lists_samples": "Samples" in documentation_text,
            "instructions_describe_extract_system": (
                "data extraction system" in instructions_text.lower()
            ),
            "faq_unique_household_identifier_documented": "YEAR" in faq_text
            and "SERIAL" in faq_text,
            "samples_page_mentions_sample_sizes": "Sample sizes" in samples_text,
            "variable_groups_present": "Outgoing Rotation Groups" in variable_groups_text
            and "Annual Social" in variable_groups_text,
            "sample_id_count": sample_summary["sample_id_count"],
            "latest_sample_id": sample_summary["latest_sample_id"],
            "latest_sample_description": sample_summary["latest_sample_description"],
            "latest_revision_date": revision_summary["latest_revision_date"],
            "revision_mentions_2025_shutdown_gap": revision_summary[
                "mentions_2025_shutdown_gap"
            ],
            "candidate_variable_count": len(variables),
            "candidate_variable_present_count": present_variable_count,
            "api_supported_feature_count": api_capabilities["supported_feature_count"],
            "api_unsupported_feature_count": api_capabilities["unsupported_feature_count"],
            "api_key_required_documented": api_capabilities[
                "api_key_required_documented"
            ],
            "metadata_api_gap_documented": api_capabilities[
                "metadata_api_gap_documented"
            ],
            "modeling_approved": False,
            "runner_config_approved": False,
        },
        "sample_id_summary": sample_summary,
        "revision_summary": revision_summary,
        "api_capabilities": api_capabilities,
        "official_source_notes": [
            "IPUMS CPS is a harmonized Current Population Survey microdata access path.",
            "The web extract system and API require explicit sample and variable selection before data access.",
            "The API workflow documents collection=cps extract requests and use of an IPUMS API key.",
            "The microdata API documentation states that no metadata API support is currently available for IPUMS microdata collections, so sample IDs and variable mnemonics must be gathered from IPUMS websites.",
            "Recent revision history reports May 2026 monthly data availability and notes that October 2025 data were not collected during the U.S. federal government shutdown.",
        ],
        "candidate_target_policy": {
            "status": "not_selected",
            "sample_variables_verified_from_documentation": variables,
            "required_before_modeling": [
                "choose exact CPS extract samples, years, months, and supplement scope",
                "choose one continuous target and document its universe, codes, topcoding, inflation adjustment, and weight guidance",
                "pin person/household unit of analysis and all required preselected variables",
                "define survey weight usage or an explicit unweighted diagnostic-only policy",
                "define topcode, NIU, missing, negative-income, inflation, and imputation policy",
                "define train/validation/test split that prevents household/person longitudinal leakage",
                "store extract metadata and codebook in ignored local cache with reproducible extraction instructions",
            ],
        },
        "group_policy": {
            "status": "not_publication_ready_fairness_dataset",
            "candidate_grouping_dimensions": [
                "sex",
                "race",
                "age",
                "education",
                "state",
                "occupation",
                "industry",
                "household_or_family",
                "survey_month_or_year",
            ],
            "required_before_modeling": [
                "separate diagnostic group coverage from wage discrimination, labor-market, or population-fairness language",
                "predeclare whether group variables are used for diagnostics, Mondrian calibration, grouped split, or features",
                "handle household/person linkage and repeated respondent identifiers before any group coverage interpretation",
            ],
        },
        "access_policy": {
            "source_is_official_ipums_cps": source_url.startswith(
                "https://cps.ipums.org/"
            ),
            "api_key_required_documented": api_capabilities[
                "api_key_required_documented"
            ],
            "api_extract_submitted": False,
            "raw_extract_downloaded": False,
            "raw_extract_committed_to_git": False,
            "extract_cache_policy": "Submit/download IPUMS CPS extracts only after target, sample, weight, split, and terms/citation policy are approved; keep raw extracts in ignored local cache.",
        },
        "blockers": [
            "IPUMS API key and account/extract reproducibility are not configured in this audit",
            "target variable not selected",
            "sample/year/month/supplement scope not selected",
            "person versus household unit of analysis not selected",
            "survey weights and replicate/earnings weight policy not defined",
            "topcode, NIU, missing, negative-income, and inflation-adjustment policy not defined",
            "household/person longitudinal leakage split policy not defined",
            "raw extract and codebook not downloaded or profiled",
            "no labor-market, wage-discrimination, population inference, individual fairness, or policy claim may be made",
        ],
        "next_actions": [
            "Select one narrow CPS target such as HOURWAGE, EARNWEEK, INCWAGE, INCTOT, or UHRSWORKT.",
            "Choose a small sample window and supplement/month design before extract creation.",
            "Create an ignored-cache extract recipe with exact sample IDs, variables, data format, and codebook retention.",
            "Profile target missingness, topcodes, universe restrictions, weights, and repeated-person/household identifiers before any conformal benchmark.",
        ],
        "non_claims": [
            "This audit is not a modeled IPUMS CPS dataset.",
            "This audit is not labor-market or wage-discrimination evidence.",
            "This audit is not population-weighted CPS inference.",
            "This audit is not individual fairness evidence.",
            "This audit is not approval to run CPS conformal benchmarks.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# IPUMS CPS Source Review Audit",
        "",
        f"- Dataset id: `{payload['dataset_id']}`",
        f"- Source family: `{payload['source_family']}`",
        f"- Status: `{payload['audit_status']}`",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Sample IDs parsed: {summary['sample_id_count']}",
        f"- Latest sample: `{summary['latest_sample_id']}` - {summary['latest_sample_description']}",
        f"- Latest revision date: {summary['latest_revision_date']}",
        f"- Candidate variables present: {summary['candidate_variable_present_count']} / {summary['candidate_variable_count']}",
        f"- API supported features detected: {summary['api_supported_feature_count']}",
        f"- API unsupported features detected: {summary['api_unsupported_feature_count']}",
        f"- API key required documented: `{summary['api_key_required_documented']}`",
        f"- Metadata API gap documented: `{summary['metadata_api_gap_documented']}`",
        f"- Modeling approved: `{summary['modeling_approved']}`",
        "",
        "## Source Pages",
        "",
    ]
    for key, url in payload["source_pages"].items():
        lines.append(f"- `{key}`: {url}")
    lines.extend(["", "## Candidate Target Variables", ""])
    for candidate_id, row in payload["candidate_target_policy"][
        "sample_variables_verified_from_documentation"
    ].items():
        lines.append(
            "- "
            f"`{candidate_id}` -> `{row['variable']}`: "
            f"present `{row['present']}`, risk keywords {row['risk_keyword_count']}"
        )
    lines.extend(["", "## Official Source Notes", ""])
    lines.extend(f"- {note}" for note in payload["official_source_notes"])
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {blocker}" for blocker in payload["blockers"])
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in payload["next_actions"])
    lines.extend(["", "## Non-Claims", ""])
    lines.extend(f"- {non_claim}" for non_claim in payload["non_claims"])
    return "\n".join(lines).rstrip() + "\n"


def profile_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "cpfi_regression_ipums_cps_source_review_profile_v1",
        "dataset_id": payload["dataset_id"],
        "source": payload["source"],
        "source_url": payload["source_url"],
        "source_family": payload["source_family"],
        "audit_status": payload["audit_status"],
        "sample_id_count": payload["summary"]["sample_id_count"],
        "latest_sample_id": payload["summary"]["latest_sample_id"],
        "latest_revision_date": payload["summary"]["latest_revision_date"],
        "candidate_variable_count": payload["summary"]["candidate_variable_count"],
        "candidate_variable_present_count": payload["summary"][
            "candidate_variable_present_count"
        ],
        "target_selected": False,
        "sample_scope_selected": False,
        "raw_extract_downloaded": False,
        "modeling_approved": False,
        "candidate_variables": payload["candidate_target_policy"][
            "sample_variables_verified_from_documentation"
        ],
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    lines = [
        "# IPUMS CPS Source Review Profile",
        "",
        f"- Dataset id: `{profile['dataset_id']}`",
        f"- Source family: `{profile['source_family']}`",
        f"- Status: `{profile['audit_status']}`",
        f"- Sample IDs parsed: {profile['sample_id_count']}",
        f"- Latest sample: `{profile['latest_sample_id']}`",
        f"- Latest revision date: {profile['latest_revision_date']}",
        f"- Candidate variables present: {profile['candidate_variable_present_count']} / {profile['candidate_variable_count']}",
        f"- Target selected: `{profile['target_selected']}`",
        f"- Sample scope selected: `{profile['sample_scope_selected']}`",
        f"- Raw extract downloaded: `{profile['raw_extract_downloaded']}`",
        f"- Modeling approved: `{profile['modeling_approved']}`",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    source_html = load_text_fixture(args.offline_source_html, args.source_url)
    documentation_html = load_text_fixture(
        args.offline_documentation_html, args.documentation_url
    )
    instructions_html = load_text_fixture(
        args.offline_instructions_html, args.instructions_url
    )
    faq_html = load_text_fixture(args.offline_faq_html, args.faq_url)
    sample_ids_html = load_text_fixture(
        args.offline_sample_ids_html, args.sample_ids_url
    )
    samples_html = load_text_fixture(args.offline_samples_html, args.samples_url)
    variable_groups_html = load_text_fixture(
        args.offline_variable_groups_html, args.variable_groups_url
    )
    revisions_html = load_text_fixture(args.offline_revisions_html, args.revisions_url)
    api_doc_html = load_text_fixture(args.offline_api_doc_html, args.api_doc_url)
    api_workflow_html = load_text_fixture(
        args.offline_api_workflow_html, args.api_workflow_url
    )
    if args.offline_variable_pages_json:
        variable_pages = json.loads(
            Path(args.offline_variable_pages_json).read_text(encoding="utf-8")
        )
    else:
        variable_pages = {
            candidate_id: fetch_text(url)
            for candidate_id, url in CANDIDATE_VARIABLE_URLS.items()
        }
    payload = build_payload(
        source_html=source_html,
        documentation_html=documentation_html,
        instructions_html=instructions_html,
        faq_html=faq_html,
        sample_ids_html=sample_ids_html,
        samples_html=samples_html,
        variable_groups_html=variable_groups_html,
        revisions_html=revisions_html,
        api_doc_html=api_doc_html,
        api_workflow_html=api_workflow_html,
        variable_pages=variable_pages,
        source_url=args.source_url,
        documentation_url=args.documentation_url,
        instructions_url=args.instructions_url,
        faq_url=args.faq_url,
        sample_ids_url=args.sample_ids_url,
        samples_url=args.samples_url,
        variable_groups_url=args.variable_groups_url,
        revisions_url=args.revisions_url,
        api_doc_url=args.api_doc_url,
        api_workflow_url=args.api_workflow_url,
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
