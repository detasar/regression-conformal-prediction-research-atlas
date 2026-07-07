"""Audit Data.gov as a source-review-only regression candidate."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_datagov_source_review_v1"
DATASET_ID = "datagov_source_review"
SOURCE = "Data.gov catalog metadata portal"
SOURCE_FAMILY = "datagov"
SOURCE_URL = "https://catalog.data.gov/"
CATALOG_API_DOC_URL = "https://resources.data.gov/catalog-api/"
OPEN_GSA_API_DOC_URL = "https://open.gsa.gov/api/datadotgov/"
CATALOG_API_DATASET_URL = "https://catalog.data.gov/dataset/data-gov-ckan-api"
V4_SEARCH_URL = "https://api.gsa.gov/technology/datagov/v4/search"
LEGACY_V3_SEARCH_URL = (
    "https://catalog-old.data.gov/api/3/action/package_search"
)
DEFAULT_OUT_DIR = Path("experiments/regression/audits") / DATASET_ID

CANDIDATE_QUERIES = {
    "income": "income",
    "housing": "housing",
    "health": "health",
    "education": "education",
    "labor": "labor",
    "wages": "wages",
    "mortgage": "mortgage",
    "survey": "survey regression",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--catalog-api-doc-url", default=CATALOG_API_DOC_URL)
    parser.add_argument("--open-gsa-api-doc-url", default=OPEN_GSA_API_DOC_URL)
    parser.add_argument("--catalog-api-dataset-url", default=CATALOG_API_DATASET_URL)
    parser.add_argument("--v4-search-url", default=V4_SEARCH_URL)
    parser.add_argument("--legacy-v3-search-url", default=LEGACY_V3_SEARCH_URL)
    parser.add_argument("--api-key", default="DEMO_KEY")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--offline-v4-query-json",
        default=None,
        help="Optional JSON object keyed by candidate query id containing v4 search payloads.",
    )
    parser.add_argument(
        "--offline-legacy-query-json",
        default=None,
        help="Optional JSON object keyed by candidate query id containing legacy v3 search payloads.",
    )
    return parser.parse_args()


def fetch_json(url: str, *, api_key: str = "DEMO_KEY") -> Any:
    headers = {
        "User-Agent": "cpfi-regression-source-audit/1.0",
        "X-Api-Key": api_key,
    }
    request = Request(url, headers=headers)
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            with urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, TimeoutError, URLError) as exc:
            last_error = exc
            if isinstance(exc, HTTPError) and exc.code == 429:
                break
            if attempt == 4:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Data.gov source request failed after retries: {url}") from last_error


def fetch_json_or_error(url: str, *, api_key: str = "DEMO_KEY") -> Any:
    try:
        return fetch_json(url, api_key=api_key)
    except RuntimeError as exc:
        cause = exc.__cause__
        if isinstance(cause, HTTPError):
            return {
                "_fetch_status": f"http_error_{cause.code}",
                "_status_code": cause.code,
                "_url": url,
                "_error": str(exc),
            }
        return {
            "_fetch_status": type(cause).__name__ if cause else "fetch_error",
            "_status_code": None,
            "_url": url,
            "_error": str(exc),
        }


def load_json_object(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def query_url(base_url: str, **params: Any) -> str:
    return f"{base_url}?{urlencode(params)}"


def fetch_v4_queries(search_url: str, api_key: str) -> dict[str, Any]:
    results = {}
    for query_id, query in CANDIDATE_QUERIES.items():
        results[query_id] = fetch_json_or_error(
            query_url(search_url, q=query),
            api_key=api_key,
        )
        time.sleep(1.0)
    return results


def fetch_legacy_queries(search_url: str, api_key: str) -> dict[str, Any]:
    results = {}
    for query_id, query in CANDIDATE_QUERIES.items():
        params: dict[str, Any] = {"q": query, "rows": 1}
        if api_key and "api.gsa.gov" in search_url:
            params["api_key"] = api_key
        results[query_id] = fetch_json_or_error(
            query_url(search_url, **params),
            api_key=api_key,
        )
        time.sleep(1.0)
    return results


def value_from_mapping(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def list_from_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def v4_result_summary(payload: dict[str, Any]) -> dict[str, Any]:
    fetch_status = payload.get("_fetch_status")
    if fetch_status:
        return {
            "fetch_status": fetch_status,
            "fetch_status_code": payload.get("_status_code"),
            "fetch_error": payload.get("_error"),
            "result_count_returned": 0,
            "has_after_cursor": False,
            "sort": None,
            "access_level_counts": {},
            "distribution_count_returned": 0,
            "downloadable_distribution_count_returned": 0,
            "format_counts_returned": {},
            "organization_counts_returned": {},
            "top_result_samples": [],
        }
    results = [row for row in payload.get("results", []) if isinstance(row, dict)]
    access_counts = Counter()
    format_counts = Counter()
    organization_counts = Counter()
    distribution_count = 0
    downloadable_distribution_count = 0
    top_results = []
    for row in results:
        dcat = row.get("dcat") if isinstance(row.get("dcat"), dict) else {}
        access = str(dcat.get("accessLevel") or "unknown")
        access_counts[access] += 1
        organization = row.get("organization") or value_from_mapping(dcat, "publisher", "name")
        if organization:
            organization_counts[str(organization)] += 1
        distributions = [
            item for item in list_from_value(dcat.get("distribution")) if isinstance(item, dict)
        ]
        distribution_count += len(distributions)
        for distribution in distributions:
            distribution_format = (
                distribution.get("format")
                or distribution.get("mediaType")
                or distribution.get("downloadURL")
                or distribution.get("accessURL")
                or "unknown"
            )
            format_counts[str(distribution_format).lower()] += 1
            if distribution.get("downloadURL") or distribution.get("accessURL"):
                downloadable_distribution_count += 1
        if len(top_results) < 3:
            top_results.append(
                {
                    "identifier": row.get("identifier") or dcat.get("identifier"),
                    "title": row.get("title") or dcat.get("title"),
                    "access_level": access,
                    "organization": organization,
                    "theme": list_from_value(row.get("theme") or dcat.get("theme"))[:5],
                    "keyword": list_from_value(row.get("keyword") or dcat.get("keyword"))[:5],
                    "distribution_count": len(distributions),
                    "last_harvested_date": row.get("last_harvested_date"),
                }
            )
    return {
        "fetch_status": "ok",
        "fetch_status_code": 200,
        "fetch_error": None,
        "result_count_returned": len(results),
        "has_after_cursor": bool(payload.get("after")),
        "sort": payload.get("sort"),
        "access_level_counts": dict(sorted(access_counts.items())),
        "distribution_count_returned": distribution_count,
        "downloadable_distribution_count_returned": downloadable_distribution_count,
        "format_counts_returned": dict(format_counts.most_common(12)),
        "organization_counts_returned": dict(organization_counts.most_common(8)),
        "top_result_samples": top_results,
    }


def legacy_result_summary(payload: dict[str, Any]) -> dict[str, Any]:
    fetch_status = payload.get("_fetch_status")
    if fetch_status:
        return {
            "fetch_status": fetch_status,
            "fetch_status_code": payload.get("_status_code"),
            "fetch_error": payload.get("_error"),
            "success": False,
            "total_count": 0,
            "sample_result_count": 0,
            "sample_title": None,
            "sample_license_title": None,
            "sample_organization_title": None,
            "sample_metadata_created": None,
            "sample_metadata_modified": None,
        }
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    rows = [row for row in result.get("results", []) if isinstance(row, dict)]
    first = rows[0] if rows else {}
    return {
        "fetch_status": "ok",
        "fetch_status_code": 200,
        "fetch_error": None,
        "success": bool(payload.get("success")),
        "total_count": int(result.get("count") or 0),
        "sample_result_count": len(rows),
        "sample_title": first.get("title"),
        "sample_license_title": first.get("license_title"),
        "sample_organization_title": value_from_mapping(first, "organization", "title"),
        "sample_metadata_created": first.get("metadata_created"),
        "sample_metadata_modified": first.get("metadata_modified"),
    }


def build_payload(
    *,
    v4_query_json: dict[str, Any],
    legacy_query_json: dict[str, Any],
    generated_at_utc: str | None = None,
    source_url: str = SOURCE_URL,
    catalog_api_doc_url: str = CATALOG_API_DOC_URL,
    open_gsa_api_doc_url: str = OPEN_GSA_API_DOC_URL,
    catalog_api_dataset_url: str = CATALOG_API_DATASET_URL,
    v4_search_url: str = V4_SEARCH_URL,
    legacy_v3_search_url: str = LEGACY_V3_SEARCH_URL,
) -> dict[str, Any]:
    v4_queries = {
        query_id: {
            "query": CANDIDATE_QUERIES[query_id],
            "search_url": query_url(v4_search_url, q=CANDIDATE_QUERIES[query_id]),
            **v4_result_summary(payload if isinstance(payload, dict) else {}),
        }
        for query_id, payload in sorted(v4_query_json.items())
        if query_id in CANDIDATE_QUERIES
    }
    legacy_queries = {
        query_id: {
            "query": CANDIDATE_QUERIES[query_id],
            "search_url": query_url(
                legacy_v3_search_url,
                q=CANDIDATE_QUERIES[query_id],
                rows=1,
            ),
            **legacy_result_summary(payload if isinstance(payload, dict) else {}),
        }
        for query_id, payload in sorted(legacy_query_json.items())
        if query_id in CANDIDATE_QUERIES
    }
    positive_legacy_queries = [
        row for row in legacy_queries.values() if row["success"] and row["total_count"] > 0
    ]
    v4_positive_queries = [
        row for row in v4_queries.values() if row["result_count_returned"] > 0
    ]
    public_v4_results = sum(
        int((row.get("access_level_counts") or {}).get("public") or 0)
        for row in v4_queries.values()
    )
    total_v4_results = sum(row["result_count_returned"] for row in v4_queries.values())
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
            "catalog_home": source_url,
            "catalog_api_documentation": catalog_api_doc_url,
            "open_gsa_legacy_api_documentation": open_gsa_api_doc_url,
            "catalog_api_dataset_record": catalog_api_dataset_url,
        },
        "api_endpoints": {
            "v4_search": v4_search_url,
            "legacy_v3_package_search": legacy_v3_search_url,
        },
        "summary": {
            "candidate_query_count": len(CANDIDATE_QUERIES),
            "v4_query_count": len(v4_queries),
            "legacy_query_count": len(legacy_queries),
            "v4_positive_query_count": len(v4_positive_queries),
            "legacy_positive_query_count": len(positive_legacy_queries),
            "v4_fetch_failure_count": sum(
                1 for row in v4_queries.values() if row.get("fetch_status") != "ok"
            ),
            "legacy_fetch_failure_count": sum(
                1 for row in legacy_queries.values() if row.get("fetch_status") != "ok"
            ),
            "legacy_total_result_count_sum": sum(
                row["total_count"] for row in legacy_queries.values()
            ),
            "v4_results_returned_total": total_v4_results,
            "v4_public_access_result_count": public_v4_results,
            "v4_public_access_fraction_returned": (
                public_v4_results / total_v4_results if total_v4_results else None
            ),
            "v4_distribution_count_returned": sum(
                row["distribution_count_returned"] for row in v4_queries.values()
            ),
            "v4_downloadable_distribution_count_returned": sum(
                row["downloadable_distribution_count_returned"]
                for row in v4_queries.values()
            ),
            "modeling_approved": False,
            "runner_config_approved": False,
            "raw_data_downloaded": False,
            "metadata_only_review": True,
        },
        "query_reviews": {
            "v4_search": v4_queries,
            "legacy_v3_package_search": legacy_queries,
        },
        "access_caveats": [
            f"v4 query `{query_id}` returned `{row.get('fetch_status')}`"
            for query_id, row in v4_queries.items()
            if row.get("fetch_status") != "ok"
        ]
        + [
            f"legacy query `{query_id}` returned `{row.get('fetch_status')}`"
            for query_id, row in legacy_queries.items()
            if row.get("fetch_status") != "ok"
        ],
        "official_source_notes": [
            "The Data.gov catalog is a metadata portal for datasets published by federal, state, local, and tribal governments.",
            "The new Data.gov Catalog API v4 is the preferred search surface for new development.",
            "The legacy CKAN v3 package_search endpoint remains useful for metadata counts but should not be treated as raw data access.",
            "Data.gov search results identify candidate datasets; every candidate still needs its own license, dictionary, target, group, and download review.",
        ],
        "candidate_dataset_policy": {
            "status": "not_selected",
            "candidate_queries": CANDIDATE_QUERIES,
            "required_before_modeling": [
                "select one dataset record and pin its Data.gov identifier",
                "resolve the primary agency or subnational source instead of treating Data.gov as primary data provenance",
                "verify license, accessLevel, data dictionary, resource URLs, and update cadence",
                "download raw data only into ignored local cache after target and group variables are approved",
                "profile target type, missingness, duplicate rows, identifiers, leakage risks, and sensitive/proxy variables",
            ],
        },
        "access_policy": {
            "source_is_official_us_government_metadata_portal": source_url.startswith(
                "https://catalog.data.gov/"
            ),
            "metadata_api_reviewed": True,
            "raw_data_downloaded": False,
            "raw_data_committed_to_git": False,
            "api_key_policy": "DEMO_KEY is sufficient for metadata probing; any future high-volume extraction should use a project API key and commit only metadata/provenance, not raw data.",
        },
        "blockers": [
            "no individual Data.gov dataset record selected",
            "primary source agency provenance not resolved for any candidate record",
            "license/resource/data-dictionary review not complete for any candidate record",
            "target and group variables not selected",
            "raw data not downloaded or profiled",
            "split, leakage, missingness, imputation, and endpoint policies not defined",
            "no government, policy, fairness, population, legal, final model-selection, bounded-support, or validated Venn-Abers claim may be made",
        ],
        "next_actions": [
            "Pick a small number of high-value Data.gov records from income, housing, health, education, labor, or mortgage searches.",
            "Trace each selected record back to its primary publisher and data dictionary.",
            "Reject metadata-only records that do not expose stable tabular downloads or variable documentation.",
            "Create dataset-specific audits before any runner config is generated.",
        ],
        "non_claims": [
            "This audit is not a modeled Data.gov dataset.",
            "This audit does not approve any Data.gov dataset for runner use.",
            "This audit is not government-policy, legal, compliance, or population inference.",
            "This audit is not fairness evidence.",
            "This audit is not final method-selection or validated Venn-Abers evidence.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Data.gov Source Review Audit",
        "",
        f"- Dataset id: `{payload['dataset_id']}`",
        f"- Source family: `{payload['source_family']}`",
        f"- Status: `{payload['audit_status']}`",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Candidate queries: {summary['candidate_query_count']}",
        f"- v4 positive queries: {summary['v4_positive_query_count']} / {summary['v4_query_count']}",
        f"- Legacy positive queries: {summary['legacy_positive_query_count']} / {summary['legacy_query_count']}",
        f"- v4 fetch failures: {summary['v4_fetch_failure_count']}",
        f"- Legacy fetch failures: {summary['legacy_fetch_failure_count']}",
        f"- Legacy result-count sum: {summary['legacy_total_result_count_sum']}",
        f"- v4 returned results: {summary['v4_results_returned_total']}",
        f"- v4 public-access returned results: {summary['v4_public_access_result_count']}",
        f"- v4 downloadable distributions returned: {summary['v4_downloadable_distribution_count_returned']}",
        f"- Modeling approved: `{summary['modeling_approved']}`",
        "",
        "## Source Pages",
        "",
    ]
    for key, url in payload["source_pages"].items():
        lines.append(f"- `{key}`: {url}")
    if payload["access_caveats"]:
        lines.extend(["", "## Access Caveats", ""])
        lines.extend(f"- {caveat}" for caveat in payload["access_caveats"])
    lines.extend(["", "## Query Review", ""])
    lines.extend(
        [
            "| Query id | Query | v4 rows | v3 total count | v4 public rows | v4 download/access URLs |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    v4_queries = payload["query_reviews"]["v4_search"]
    legacy_queries = payload["query_reviews"]["legacy_v3_package_search"]
    for query_id in CANDIDATE_QUERIES:
        v4 = v4_queries.get(query_id, {})
        legacy = legacy_queries.get(query_id, {})
        lines.append(
            "| "
            f"`{query_id}` | "
            f"`{CANDIDATE_QUERIES[query_id]}` | "
            f"{v4.get('result_count_returned', 0)} | "
            f"{legacy.get('total_count', 0)} | "
            f"{(v4.get('access_level_counts') or {}).get('public', 0)} | "
            f"{v4.get('downloadable_distribution_count_returned', 0)} |"
        )
    lines.extend(["", "## Top v4 Samples", ""])
    for query_id, row in v4_queries.items():
        lines.append(f"### `{query_id}`")
        for sample in row.get("top_result_samples", [])[:2]:
            lines.append(
                "- "
                f"`{sample.get('identifier')}`: {sample.get('title')} "
                f"(access `{sample.get('access_level')}`, distributions {sample.get('distribution_count')})"
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
    summary = payload["summary"]
    return {
        "schema": "cpfi_regression_datagov_source_review_profile_v1",
        "dataset_id": payload["dataset_id"],
        "source": payload["source"],
        "source_url": payload["source_url"],
        "source_family": payload["source_family"],
        "audit_status": payload["audit_status"],
        "candidate_query_count": summary["candidate_query_count"],
        "legacy_positive_query_count": summary["legacy_positive_query_count"],
        "legacy_total_result_count_sum": summary["legacy_total_result_count_sum"],
        "v4_positive_query_count": summary["v4_positive_query_count"],
        "v4_results_returned_total": summary["v4_results_returned_total"],
        "v4_public_access_result_count": summary["v4_public_access_result_count"],
        "raw_data_downloaded": False,
        "dataset_record_selected": False,
        "primary_source_resolved": False,
        "target_selected": False,
        "group_variables_selected": False,
        "modeling_approved": False,
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    lines = [
        "# Data.gov Source Review Profile",
        "",
        f"- Dataset id: `{profile['dataset_id']}`",
        f"- Source family: `{profile['source_family']}`",
        f"- Status: `{profile['audit_status']}`",
        f"- Candidate queries: {profile['candidate_query_count']}",
        f"- Legacy positive queries: {profile['legacy_positive_query_count']}",
        f"- Legacy result-count sum: {profile['legacy_total_result_count_sum']}",
        f"- v4 positive queries: {profile['v4_positive_query_count']}",
        f"- v4 returned results: {profile['v4_results_returned_total']}",
        f"- v4 public-access returned results: {profile['v4_public_access_result_count']}",
        f"- Dataset record selected: `{profile['dataset_record_selected']}`",
        f"- Primary source resolved: `{profile['primary_source_resolved']}`",
        f"- Raw data downloaded: `{profile['raw_data_downloaded']}`",
        f"- Target selected: `{profile['target_selected']}`",
        f"- Group variables selected: `{profile['group_variables_selected']}`",
        f"- Modeling approved: `{profile['modeling_approved']}`",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    v4_query_json = load_json_object(args.offline_v4_query_json) or fetch_v4_queries(
        args.v4_search_url,
        args.api_key,
    )
    legacy_query_json = load_json_object(
        args.offline_legacy_query_json
    ) or fetch_legacy_queries(args.legacy_v3_search_url, args.api_key)
    payload = build_payload(
        v4_query_json=v4_query_json,
        legacy_query_json=legacy_query_json,
        source_url=args.source_url,
        catalog_api_doc_url=args.catalog_api_doc_url,
        open_gsa_api_doc_url=args.open_gsa_api_doc_url,
        catalog_api_dataset_url=args.catalog_api_dataset_url,
        v4_search_url=args.v4_search_url,
        legacy_v3_search_url=args.legacy_v3_search_url,
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
