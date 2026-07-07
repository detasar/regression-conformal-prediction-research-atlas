"""Audit World Bank WDI as a source-review-only regression candidate."""

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


SCHEMA = "cpfi_regression_wdi_source_review_v1"
DATASET_ID = "world_bank_wdi_source_review"
SOURCE = "World Bank World Development Indicators"
SOURCE_FAMILY = "world_bank_wdi"
SOURCE_ID = "2"
SOURCE_CODE = "WDI"
SOURCE_URL = "https://databank.worldbank.org/source/world-development-indicators"
WDI_HOME_URL = "https://datatopics.worldbank.org/world-development-indicators/"
USER_GUIDE_URL = (
    "https://datatopics.worldbank.org/world-development-indicators/user-guide.html"
)
API_DOC_URL = (
    "https://datahelpdesk.worldbank.org/knowledgebase/articles/"
    "889392-about-the-indicators-api-documentation"
)
INDICATOR_QUERY_DOC_URL = (
    "https://datahelpdesk.worldbank.org/knowledgebase/articles/"
    "898599-indicator-api-queries"
)
API_BASE_URL = "https://api.worldbank.org/v2"
SOURCE_API_URL = f"{API_BASE_URL}/source/{SOURCE_ID}?format=json"
SOURCE_INDICATORS_API_URL = (
    f"{API_BASE_URL}/source/{SOURCE_ID}/indicators?format=json&per_page=5"
)
COUNTRY_API_URL = f"{API_BASE_URL}/country?format=json&per_page=5"
DEFAULT_OUT_DIR = Path("experiments/regression/audits") / DATASET_ID

SAMPLE_INDICATORS = {
    "gdp_per_capita_constant_2015_usd": "NY.GDP.PCAP.KD",
    "life_expectancy_at_birth_years": "SP.DYN.LE00.IN",
    "population_total": "SP.POP.TOTL",
    "access_to_electricity_percent_population": "EG.ELC.ACCS.ZS",
    "school_enrollment_secondary_percent_gross": "SE.SEC.ENRR",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--wdi-home-url", default=WDI_HOME_URL)
    parser.add_argument("--user-guide-url", default=USER_GUIDE_URL)
    parser.add_argument("--api-doc-url", default=API_DOC_URL)
    parser.add_argument("--indicator-query-doc-url", default=INDICATOR_QUERY_DOC_URL)
    parser.add_argument("--source-api-url", default=SOURCE_API_URL)
    parser.add_argument("--source-indicators-api-url", default=SOURCE_INDICATORS_API_URL)
    parser.add_argument("--country-api-url", default=COUNTRY_API_URL)
    parser.add_argument("--api-base-url", default=API_BASE_URL)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--offline-source-json",
        default=None,
        help="Optional source API JSON fixture; otherwise the World Bank API is fetched.",
    )
    parser.add_argument(
        "--offline-indicators-json",
        default=None,
        help="Optional source-indicators API JSON fixture.",
    )
    parser.add_argument(
        "--offline-country-json",
        default=None,
        help="Optional country API JSON fixture.",
    )
    parser.add_argument(
        "--offline-sample-indicators-json",
        default=None,
        help="Optional JSON object keyed by sample indicator code.",
    )
    return parser.parse_args()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def fetch_json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": "cpfi-regression-source-audit/1.0"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, TimeoutError, URLError) as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"World Bank API request failed after retries: {url}") from last_error


def load_json_fixture(path: str | None, url: str) -> Any:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return fetch_json(url)


def api_page_metadata(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, list) or not payload:
        return {}
    metadata = payload[0]
    return metadata if isinstance(metadata, dict) else {}


def api_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        return []
    return [row for row in payload[1] if isinstance(row, dict)]


def api_total(payload: Any) -> int | None:
    metadata = api_page_metadata(payload)
    total = metadata.get("total")
    try:
        return int(total)
    except (TypeError, ValueError):
        return None


def fetch_sample_indicators(api_base_url: str) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for code in SAMPLE_INDICATORS.values():
        rows[code] = fetch_json(f"{api_base_url}/indicator/{code}?format=json")
    return rows


def parse_indicator_payload(indicator_id: str, payload: Any) -> dict[str, Any]:
    rows = api_rows(payload)
    row = rows[0] if rows else {}
    topics = [
        normalize_text(str(topic.get("value", "")))
        for topic in row.get("topics", [])
        if isinstance(topic, dict)
    ]
    source = row.get("source") if isinstance(row.get("source"), dict) else {}
    return {
        "indicator_id": indicator_id,
        "present": bool(row),
        "name": row.get("name"),
        "source_id": source.get("id"),
        "source": source.get("value"),
        "topic_names": topics,
        "source_note_present": bool(row.get("sourceNote")),
        "source_organization_present": bool(row.get("sourceOrganization")),
    }


def build_payload(
    *,
    source_json: Any,
    indicators_json: Any,
    country_json: Any,
    sample_indicator_json: dict[str, Any],
    generated_at_utc: str | None = None,
    source_url: str = SOURCE_URL,
    wdi_home_url: str = WDI_HOME_URL,
    user_guide_url: str = USER_GUIDE_URL,
    api_doc_url: str = API_DOC_URL,
    indicator_query_doc_url: str = INDICATOR_QUERY_DOC_URL,
    source_api_url: str = SOURCE_API_URL,
    source_indicators_api_url: str = SOURCE_INDICATORS_API_URL,
    country_api_url: str = COUNTRY_API_URL,
) -> dict[str, Any]:
    source_rows = api_rows(source_json)
    source_row = source_rows[0] if source_rows else {}
    source_metadata = {
        "id": source_row.get("id"),
        "name": source_row.get("name"),
        "code": source_row.get("code"),
        "lastupdated": source_row.get("lastupdated"),
        "dataavailability": source_row.get("dataavailability"),
        "metadataavailability": source_row.get("metadataavailability"),
        "concepts": source_row.get("concepts"),
    }
    sample_indicators = {
        candidate_id: parse_indicator_payload(
            indicator_id, sample_indicator_json.get(indicator_id)
        )
        for candidate_id, indicator_id in SAMPLE_INDICATORS.items()
    }
    source_id_consistent = all(
        row["source_id"] == SOURCE_ID for row in sample_indicators.values() if row["present"]
    )
    return {
        "schema": SCHEMA,
        "dataset_id": DATASET_ID,
        "source": SOURCE,
        "source_url": source_url,
        "source_family": SOURCE_FAMILY,
        "audit_status": "source_review_only_modeling_blocked",
        "generated_at_utc": generated_at_utc
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_pages": {
            "databank_wdi": source_url,
            "wdi_home": wdi_home_url,
            "user_guide": user_guide_url,
            "api_documentation": api_doc_url,
            "indicator_query_documentation": indicator_query_doc_url,
        },
        "api_endpoints": {
            "source_metadata": source_api_url,
            "source_indicators": source_indicators_api_url,
            "country_metadata": country_api_url,
        },
        "summary": {
            "source_id": source_metadata["id"],
            "source_code": source_metadata["code"],
            "source_name": source_metadata["name"],
            "source_lastupdated": source_metadata["lastupdated"],
            "source_dataavailability": source_metadata["dataavailability"],
            "source_metadataavailability": source_metadata["metadataavailability"],
            "source_concepts": source_metadata["concepts"],
            "source_indicator_total_api": api_total(indicators_json),
            "country_total_api": api_total(country_json),
            "sample_indicator_count": len(sample_indicators),
            "sample_indicator_present_count": sum(
                1 for row in sample_indicators.values() if row["present"]
            ),
            "sample_indicator_source_id_consistent": source_id_consistent,
            "modeling_approved": False,
            "runner_config_approved": False,
        },
        "official_source_notes": [
            "WDI is a cross-country comparable World Bank development indicator source.",
            "The World Bank Indicators API v2 is the required programmatic access path for this audit.",
            "Country API totals include countries and aggregates; aggregation handling must be explicit before modeling.",
            "The DataBank page warns that aggregation methods do not impute missing values.",
        ],
        "candidate_indicator_policy": {
            "status": "not_selected",
            "sample_indicators_verified_by_api": sample_indicators,
            "required_before_modeling": [
                "choose a single indicator or predeclared multivariate target panel",
                "pin indicator code, unit, topic, source note, and source organization",
                "choose country/economy scope and whether aggregates are excluded",
                "define temporal split, lag structure, and leakage controls",
                "define missingness policy without treating DataBank aggregates as ordinary observations",
            ],
        },
        "group_policy": {
            "status": "not_individual_fairness_dataset",
            "candidate_grouping_dimensions": [
                "region",
                "income_level",
                "lending_type",
                "country_or_economy",
                "time_period",
            ],
            "required_before_modeling": [
                "separate country/region diagnostics from individual fairness language",
                "predeclare whether region/income/lending groupings are diagnostic strata or modeling features",
                "exclude aggregate rows from country-level validation unless explicitly modeled",
            ],
        },
        "access_policy": {
            "source_is_official_world_bank": source_url.startswith(
                "https://databank.worldbank.org/"
            ),
            "api_metadata_fetched": True,
            "bulk_data_downloaded": False,
            "bulk_data_committed_to_git": False,
            "raw_panel_cache_policy": "Download indicator panels only into ignored local cache after target, country scope, and split policy are approved.",
        },
        "blockers": [
            "target indicator not selected",
            "country/economy scope not selected",
            "aggregate rows not excluded or separately modeled",
            "missingness policy not defined",
            "temporal split and lag leakage policy not defined",
            "raw indicator panel not downloaded or profiled",
            "no macroeconomic, causal, country-ranking, policy, individual fairness, or population claim may be made",
        ],
        "next_actions": [
            "Select one continuous WDI indicator and a country-only scope.",
            "Fetch a small ignored-cache panel for profiling after target approval.",
            "Profile year coverage, missingness, country aggregates, and temporal gaps.",
            "Predeclare temporal validation before any conformal regression benchmark.",
        ],
        "non_claims": [
            "This audit is not a modeled WDI dataset.",
            "This audit is not individual fairness evidence.",
            "This audit is not causal development-policy evidence.",
            "This audit is not a country ranking.",
            "This audit is not approval to run WDI conformal benchmarks.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# World Bank WDI Source Review Audit",
        "",
        f"- Dataset id: `{payload['dataset_id']}`",
        f"- Source family: `{payload['source_family']}`",
        f"- Status: `{payload['audit_status']}`",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source id/code: `{summary['source_id']}` / `{summary['source_code']}`",
        f"- Source name: {summary['source_name']}",
        f"- Source last updated: {summary['source_lastupdated']}",
        f"- Source indicators by API: {summary['source_indicator_total_api']}",
        f"- Country endpoint rows by API: {summary['country_total_api']}",
        f"- Sample indicators present: {summary['sample_indicator_present_count']} / {summary['sample_indicator_count']}",
        f"- Sample indicator source id consistent: `{summary['sample_indicator_source_id_consistent']}`",
        f"- Modeling approved: `{summary['modeling_approved']}`",
        "",
        "## Source Pages",
        "",
    ]
    for key, url in payload["source_pages"].items():
        lines.append(f"- `{key}`: {url}")
    lines.extend(["", "## API Endpoints", ""])
    for key, url in payload["api_endpoints"].items():
        lines.append(f"- `{key}`: {url}")
    lines.extend(["", "## Sample Candidate Indicators", ""])
    for candidate_id, row in payload["candidate_indicator_policy"][
        "sample_indicators_verified_by_api"
    ].items():
        lines.append(
            "- "
            f"`{candidate_id}` -> `{row['indicator_id']}`: "
            f"present `{row['present']}`, source `{row['source_id']}`, "
            f"name `{row['name']}`"
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
        "schema": "cpfi_regression_wdi_source_review_profile_v1",
        "dataset_id": payload["dataset_id"],
        "source": payload["source"],
        "source_url": payload["source_url"],
        "source_family": payload["source_family"],
        "audit_status": payload["audit_status"],
        "source_id": payload["summary"]["source_id"],
        "source_code": payload["summary"]["source_code"],
        "source_lastupdated": payload["summary"]["source_lastupdated"],
        "source_indicator_total_api": payload["summary"]["source_indicator_total_api"],
        "country_total_api": payload["summary"]["country_total_api"],
        "target_selected": False,
        "country_scope_selected": False,
        "bulk_data_downloaded": False,
        "modeling_approved": False,
        "sample_indicators": payload["candidate_indicator_policy"][
            "sample_indicators_verified_by_api"
        ],
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    lines = [
        "# World Bank WDI Source Review Profile",
        "",
        f"- Dataset id: `{profile['dataset_id']}`",
        f"- Source family: `{profile['source_family']}`",
        f"- Status: `{profile['audit_status']}`",
        f"- Source id/code: `{profile['source_id']}` / `{profile['source_code']}`",
        f"- Source last updated: {profile['source_lastupdated']}",
        f"- Source indicators by API: {profile['source_indicator_total_api']}",
        f"- Country endpoint rows by API: {profile['country_total_api']}",
        f"- Target selected: `{profile['target_selected']}`",
        f"- Country scope selected: `{profile['country_scope_selected']}`",
        f"- Bulk data downloaded: `{profile['bulk_data_downloaded']}`",
        f"- Modeling approved: `{profile['modeling_approved']}`",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    source_json = load_json_fixture(args.offline_source_json, args.source_api_url)
    indicators_json = load_json_fixture(
        args.offline_indicators_json, args.source_indicators_api_url
    )
    country_json = load_json_fixture(args.offline_country_json, args.country_api_url)
    if args.offline_sample_indicators_json:
        sample_indicator_json = json.loads(
            Path(args.offline_sample_indicators_json).read_text(encoding="utf-8")
        )
    else:
        sample_indicator_json = fetch_sample_indicators(args.api_base_url)
    payload = build_payload(
        source_json=source_json,
        indicators_json=indicators_json,
        country_json=country_json,
        sample_indicator_json=sample_indicator_json,
        source_url=args.source_url,
        wdi_home_url=args.wdi_home_url,
        user_guide_url=args.user_guide_url,
        api_doc_url=args.api_doc_url,
        indicator_query_doc_url=args.indicator_query_doc_url,
        source_api_url=args.source_api_url,
        source_indicators_api_url=args.source_indicators_api_url,
        country_api_url=args.country_api_url,
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
