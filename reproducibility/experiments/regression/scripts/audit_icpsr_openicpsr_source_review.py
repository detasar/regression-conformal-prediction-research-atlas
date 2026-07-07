"""Audit ICPSR/openICPSR as a source-review-only regression candidate."""

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
from urllib.parse import quote
from urllib.request import Request, urlopen

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_icpsr_openicpsr_source_review_v1"
DATASET_ID = "icpsr_openicpsr_source_review"
SOURCE = "ICPSR and openICPSR research data repositories"
SOURCE_FAMILY = "icpsr_openicpsr"
SOURCE_URL = "https://www.icpsr.umich.edu/sites/icpsr/find-data"
ICPSR_STUDY_SEARCH_URL = "https://www.icpsr.umich.edu/sites/icpsr/search/studies?q="
ICPSR_VARIABLE_SEARCH_URL = "https://www.icpsr.umich.edu/sites/icpsr/search/variables?q="
ICPSR_PUBLICATION_SEARCH_URL = (
    "https://www.icpsr.umich.edu/sites/icpsr/search/publications?q="
)
OPENICPSR_ARCHIVE_SEARCH_URL = (
    "https://www.icpsr.umich.edu/sites/icpsr/search/studies?fq=ARCHIVE%3Aopenicpsr&q="
)
METADATA_RECORDS_URL = (
    "https://www.icpsr.umich.edu/sites/icpsr/about/repository-operations/"
    "accessing-metadata"
)
REPOSITORY_OPERATIONS_URL = (
    "https://www.icpsr.umich.edu/sites/icpsr/about/repository-operations"
)
OPENICPSR_HOME_URL = "https://www.openicpsr.org/"
OPENICPSR_ABOUT_URL = "https://www.openicpsr.org/openicpsr/about"
OPENICPSR_FAQ_URL = "https://www.openicpsr.org/openicpsr/faqs"
OPENICPSR_REPOSITORIES_URL = "https://www.openicpsr.org/openicpsr/repository/"
DEFAULT_OUT_DIR = Path("experiments/regression/audits") / DATASET_ID

CANDIDATE_DISCOVERY_QUERIES = {
    "income": "income",
    "housing": "housing",
    "health": "health",
    "education": "education",
    "labor": "labor",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--study-search-url", default=ICPSR_STUDY_SEARCH_URL)
    parser.add_argument("--variable-search-url", default=ICPSR_VARIABLE_SEARCH_URL)
    parser.add_argument("--publication-search-url", default=ICPSR_PUBLICATION_SEARCH_URL)
    parser.add_argument(
        "--openicpsr-archive-search-url", default=OPENICPSR_ARCHIVE_SEARCH_URL
    )
    parser.add_argument("--metadata-records-url", default=METADATA_RECORDS_URL)
    parser.add_argument("--repository-operations-url", default=REPOSITORY_OPERATIONS_URL)
    parser.add_argument("--openicpsr-home-url", default=OPENICPSR_HOME_URL)
    parser.add_argument("--openicpsr-about-url", default=OPENICPSR_ABOUT_URL)
    parser.add_argument("--openicpsr-faq-url", default=OPENICPSR_FAQ_URL)
    parser.add_argument(
        "--openicpsr-repositories-url", default=OPENICPSR_REPOSITORIES_URL
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--offline-find-data-html", default=None)
    parser.add_argument("--offline-study-search-html", default=None)
    parser.add_argument("--offline-variable-search-html", default=None)
    parser.add_argument("--offline-publication-search-html", default=None)
    parser.add_argument("--offline-openicpsr-archive-search-html", default=None)
    parser.add_argument("--offline-metadata-records-html", default=None)
    parser.add_argument("--offline-repository-operations-html", default=None)
    parser.add_argument(
        "--offline-candidate-query-html-json",
        default=None,
        help="Optional JSON object keyed by candidate query id containing search HTML.",
    )
    parser.add_argument(
        "--skip-openicpsr-direct-fetch",
        action="store_true",
        help="Do not probe direct openICPSR pages; useful for offline fixtures.",
    )
    return parser.parse_args()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def html_to_text(source_html: str) -> str:
    return normalize_text(re.sub(r"<[^>]+>", " ", source_html))


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
    raise RuntimeError(f"ICPSR source request failed after retries: {url}") from last_error


def probe_url(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "cpfi-regression-source-audit/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read(1024).decode("utf-8", errors="replace")
            return {"url": url, "fetch_status": "ok", "status_code": response.status, "body_prefix": body[:120]}
    except HTTPError as exc:
        return {"url": url, "fetch_status": f"http_error_{exc.code}", "status_code": exc.code}
    except (TimeoutError, URLError) as exc:
        return {"url": url, "fetch_status": type(exc).__name__, "status_code": None}


def load_text_fixture(path: str | None, url: str) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    return fetch_text(url)


def parse_result_count(search_html: str) -> int | None:
    text = html_to_text(search_html)
    match = re.search(r"Showing\s+1\s+[–-]\s+50\s+of\s+([0-9,]+)\s+results", text)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def parse_find_data(find_data_html: str) -> dict[str, Any]:
    text = html_to_text(find_data_html)
    return {
        "studies_are_packages": "studies are" in text.lower()
        and "packages" in text.lower(),
        "search_study_variable_publication_levels": all(
            phrase in text
            for phrase in ("study level", "variable level", "publications")
        ),
        "ssvd_variable_search_documented": "Social Science Variables Database" in text,
        "browse_by_discipline_documented": "Browse by Discipline" in text,
        "thematic_collections_documented": "Thematic Collections" in text,
        "raw_data_individuals_organizations": (
            "raw data about individuals and organizations" in text
        ),
        "rectangular_data_files_common": "rectangular data files" in text,
        "statistical_package_downloads_documented": (
            "downloaded in a variety of formats" in text
        ),
    }


def parse_metadata_records(metadata_html: str) -> dict[str, Any]:
    text = html_to_text(metadata_html)
    formats = {
        "dcat_us": "DCAT-US" in text,
        "marcxml": "MARCXML" in text,
        "dublin_core": "Dublin Core" in text,
        "ddi_codebook": "DDI-Codebook" in text,
    }
    return {
        "metadata_api_documented": "Metadata Export Application Programming Interface" in text,
        "metadata_query_fields_documented": all(
            phrase in text
            for phrase in (
                "study identifier",
                "subject terms",
                "geographic coverage area",
                "original release date",
            )
        ),
        "metadata_formats": formats,
        "metadata_format_count": sum(formats.values()),
        "individual_export_metadata_tab_documented": "Export Metadata tab" in text,
        "metadata_license_cc_by_nc": "Creative Commons Attribution-NonCommercial 4.0" in text,
        "study_specific_terms_apply": "study-specific ICPSR terms of use" in text,
    }


def parse_repository_operations(repository_html: str) -> dict[str, Any]:
    text = html_to_text(repository_html)
    return {
        "researcher_passport_documented": "Researcher Passport" in text,
        "deposit_agreement_documented": "deposit agreement" in text.lower(),
        "secure_processing_area_documented": "secure area for processing" in text,
        "checksums_documented": "checksums" in text.lower(),
        "collection_development_policy_documented": "Collection Development Policy" in text,
    }


def candidate_query_url(base_url: str, query: str) -> str:
    return f"{base_url}{quote(query)}"


def build_payload(
    *,
    find_data_html: str,
    study_search_html: str,
    variable_search_html: str,
    publication_search_html: str,
    openicpsr_archive_search_html: str,
    metadata_records_html: str,
    repository_operations_html: str,
    candidate_query_html: dict[str, str],
    direct_openicpsr_probes: list[dict[str, Any]],
    generated_at_utc: str | None = None,
    source_url: str = SOURCE_URL,
    study_search_url: str = ICPSR_STUDY_SEARCH_URL,
    variable_search_url: str = ICPSR_VARIABLE_SEARCH_URL,
    publication_search_url: str = ICPSR_PUBLICATION_SEARCH_URL,
    openicpsr_archive_search_url: str = OPENICPSR_ARCHIVE_SEARCH_URL,
    metadata_records_url: str = METADATA_RECORDS_URL,
    repository_operations_url: str = REPOSITORY_OPERATIONS_URL,
    openicpsr_home_url: str = OPENICPSR_HOME_URL,
    openicpsr_about_url: str = OPENICPSR_ABOUT_URL,
    openicpsr_faq_url: str = OPENICPSR_FAQ_URL,
    openicpsr_repositories_url: str = OPENICPSR_REPOSITORIES_URL,
) -> dict[str, Any]:
    find_data = parse_find_data(find_data_html)
    metadata = parse_metadata_records(metadata_records_html)
    repository = parse_repository_operations(repository_operations_html)
    query_counts = {
        query_id: {
            "query": query,
            "search_url": candidate_query_url(openicpsr_archive_search_url, query),
            "openicpsr_archive_result_count": parse_result_count(
                candidate_query_html.get(query_id, "")
            ),
        }
        for query_id, query in CANDIDATE_DISCOVERY_QUERIES.items()
    }
    direct_probe_failures = [
        probe for probe in direct_openicpsr_probes if probe["fetch_status"] != "ok"
    ]
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
            "icpsr_find_data": source_url,
            "icpsr_study_search": study_search_url,
            "icpsr_variable_search": variable_search_url,
            "icpsr_publication_search": publication_search_url,
            "icpsr_openicpsr_archive_search": openicpsr_archive_search_url,
            "icpsr_metadata_records": metadata_records_url,
            "icpsr_repository_operations": repository_operations_url,
            "openicpsr_home": openicpsr_home_url,
            "openicpsr_about": openicpsr_about_url,
            "openicpsr_faq": openicpsr_faq_url,
            "openicpsr_repositories": openicpsr_repositories_url,
        },
        "summary": {
            "icpsr_study_search_result_count": parse_result_count(study_search_html),
            "icpsr_variable_search_result_count": parse_result_count(
                variable_search_html
            ),
            "icpsr_publication_search_result_count": parse_result_count(
                publication_search_html
            ),
            "openicpsr_archive_result_count": parse_result_count(
                openicpsr_archive_search_html
            ),
            "candidate_query_count": len(query_counts),
            "candidate_query_with_results_count": sum(
                1
                for row in query_counts.values()
                if (row["openicpsr_archive_result_count"] or 0) > 0
            ),
            "metadata_api_documented": metadata["metadata_api_documented"],
            "metadata_format_count": metadata["metadata_format_count"],
            "repository_operations_evidence_count": sum(repository.values()),
            "find_data_evidence_count": sum(find_data.values()),
            "direct_openicpsr_probe_count": len(direct_openicpsr_probes),
            "direct_openicpsr_probe_failure_count": len(direct_probe_failures),
            "modeling_approved": False,
            "runner_config_approved": False,
        },
        "find_data_evidence": find_data,
        "metadata_records_evidence": metadata,
        "repository_operations_evidence": repository,
        "openicpsr_direct_access_probes": direct_openicpsr_probes,
        "candidate_discovery_queries": query_counts,
        "official_source_notes": [
            "ICPSR studies are source packages containing one or more datasets plus metadata.",
            "ICPSR search supports study-level, variable-level, and publication-linked discovery.",
            "ICPSR metadata can be exported through metadata APIs and study-level metadata formats; study-specific terms of use still apply.",
            "openICPSR is treated here as a repository/archive discovery surface, not as a single curated dataset.",
            "Direct openICPSR pages may require browser/JavaScript access from this CLI environment; the audit uses ICPSR's openICPSR archive search surface for reproducible source-family discovery counts.",
        ],
        "candidate_study_policy": {
            "status": "not_selected",
            "repository_level_queries": query_counts,
            "required_before_modeling": [
                "choose one concrete public study/project and version",
                "verify public versus restricted access status and all study/project terms",
                "download and inspect the study-level codebook, files, formats, citation, DOI, and license",
                "choose one continuous target and document variable universe, missing codes, scale, and units",
                "define group variables, leakage-sensitive IDs, temporal/geographic clustering, and split policy",
                "profile raw data in ignored cache before any conformal benchmark",
                "record whether the source is curated ICPSR data or self-published/openICPSR material distributed as submitted",
            ],
        },
        "access_policy": {
            "source_is_official_icpsr": source_url.startswith(
                "https://www.icpsr.umich.edu/"
            ),
            "metadata_api_documented": metadata["metadata_api_documented"],
            "direct_openicpsr_probe_failures": direct_probe_failures,
            "study_selected": False,
            "raw_data_downloaded": False,
            "raw_data_committed_to_git": False,
            "restricted_data_application_submitted": False,
            "local_cache_policy": "Download study files only into ignored local cache after study/version, license, access status, target, group, and split policies are approved.",
        },
        "blockers": [
            "no individual ICPSR/openICPSR study or version is selected",
            "public versus restricted access status is not selected",
            "license, citation, DOI, and terms-of-use policy are not selected",
            "data dictionary/codebook and file formats are not downloaded or inspected",
            "target variable not selected",
            "group variables and leakage-sensitive identifiers not selected",
            "temporal/geographic/respondent clustering and split policy not defined",
            "raw files are not downloaded or profiled",
            "no social-science, behavioral, health, economics, replication, causal, fairness, or policy claim may be made",
        ],
        "next_actions": [
            "Use ICPSR study/variable/publication search to identify a narrow public study with a continuous outcome.",
            "Prefer public-use projects with clear codebooks, file formats, DOI/citation, and permissive reuse terms.",
            "Reject restricted-use or unclear-license studies unless a separate access protocol is approved.",
            "Audit the chosen study/version manually before creating any runner config.",
        ],
        "non_claims": [
            "This audit is not a modeled ICPSR/openICPSR dataset.",
            "This audit does not approve any individual study or project for modeling.",
            "This audit is not social-science, health, economics, policy, or replication validation evidence.",
            "This audit is not individual fairness evidence.",
            "This audit is not approval to run ICPSR/openICPSR conformal benchmarks.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# ICPSR/openICPSR Source Review Audit",
        "",
        f"- Dataset id: `{payload['dataset_id']}`",
        f"- Source family: `{payload['source_family']}`",
        f"- Status: `{payload['audit_status']}`",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- ICPSR study search results: {summary['icpsr_study_search_result_count']}",
        f"- ICPSR variable search results: {summary['icpsr_variable_search_result_count']}",
        f"- ICPSR publication search results: {summary['icpsr_publication_search_result_count']}",
        f"- openICPSR archive search results: {summary['openicpsr_archive_result_count']}",
        f"- Candidate repository queries with results: {summary['candidate_query_with_results_count']} / {summary['candidate_query_count']}",
        f"- Metadata API documented: `{summary['metadata_api_documented']}`",
        f"- Metadata formats detected: {summary['metadata_format_count']}",
        f"- Direct openICPSR probe failures: {summary['direct_openicpsr_probe_failure_count']} / {summary['direct_openicpsr_probe_count']}",
        f"- Modeling approved: `{summary['modeling_approved']}`",
        "",
        "## Source Pages",
        "",
    ]
    for key, url in payload["source_pages"].items():
        lines.append(f"- `{key}`: {url}")
    lines.extend(["", "## Candidate Repository Queries", ""])
    for query_id, row in payload["candidate_discovery_queries"].items():
        lines.append(
            "- "
            f"`{query_id}` -> `{row['query']}`: "
            f"openICPSR archive results `{row['openicpsr_archive_result_count']}`"
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
        "schema": "cpfi_regression_icpsr_openicpsr_source_review_profile_v1",
        "dataset_id": payload["dataset_id"],
        "source": payload["source"],
        "source_url": payload["source_url"],
        "source_family": payload["source_family"],
        "audit_status": payload["audit_status"],
        "icpsr_study_search_result_count": payload["summary"][
            "icpsr_study_search_result_count"
        ],
        "icpsr_variable_search_result_count": payload["summary"][
            "icpsr_variable_search_result_count"
        ],
        "icpsr_publication_search_result_count": payload["summary"][
            "icpsr_publication_search_result_count"
        ],
        "openicpsr_archive_result_count": payload["summary"][
            "openicpsr_archive_result_count"
        ],
        "candidate_query_with_results_count": payload["summary"][
            "candidate_query_with_results_count"
        ],
        "study_selected": False,
        "raw_data_downloaded": False,
        "modeling_approved": False,
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    lines = [
        "# ICPSR/openICPSR Source Review Profile",
        "",
        f"- Dataset id: `{profile['dataset_id']}`",
        f"- Source family: `{profile['source_family']}`",
        f"- Status: `{profile['audit_status']}`",
        f"- ICPSR study search results: {profile['icpsr_study_search_result_count']}",
        f"- ICPSR variable search results: {profile['icpsr_variable_search_result_count']}",
        f"- ICPSR publication search results: {profile['icpsr_publication_search_result_count']}",
        f"- openICPSR archive search results: {profile['openicpsr_archive_result_count']}",
        f"- Candidate queries with results: {profile['candidate_query_with_results_count']}",
        f"- Study selected: `{profile['study_selected']}`",
        f"- Raw data downloaded: `{profile['raw_data_downloaded']}`",
        f"- Modeling approved: `{profile['modeling_approved']}`",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    find_data_html = load_text_fixture(args.offline_find_data_html, args.source_url)
    study_search_html = load_text_fixture(
        args.offline_study_search_html, args.study_search_url
    )
    variable_search_html = load_text_fixture(
        args.offline_variable_search_html, args.variable_search_url
    )
    publication_search_html = load_text_fixture(
        args.offline_publication_search_html, args.publication_search_url
    )
    openicpsr_archive_search_html = load_text_fixture(
        args.offline_openicpsr_archive_search_html,
        args.openicpsr_archive_search_url,
    )
    metadata_records_html = load_text_fixture(
        args.offline_metadata_records_html, args.metadata_records_url
    )
    repository_operations_html = load_text_fixture(
        args.offline_repository_operations_html, args.repository_operations_url
    )
    if args.offline_candidate_query_html_json:
        candidate_query_html = json.loads(
            Path(args.offline_candidate_query_html_json).read_text(encoding="utf-8")
        )
    else:
        candidate_query_html = {
            query_id: fetch_text(candidate_query_url(args.openicpsr_archive_search_url, query))
            for query_id, query in CANDIDATE_DISCOVERY_QUERIES.items()
        }
    direct_openicpsr_probes: list[dict[str, Any]]
    if args.skip_openicpsr_direct_fetch:
        direct_openicpsr_probes = []
    else:
        direct_openicpsr_probes = [
            probe_url(args.openicpsr_home_url),
            probe_url(args.openicpsr_about_url),
            probe_url(args.openicpsr_faq_url),
            probe_url(args.openicpsr_repositories_url),
        ]
    payload = build_payload(
        find_data_html=find_data_html,
        study_search_html=study_search_html,
        variable_search_html=variable_search_html,
        publication_search_html=publication_search_html,
        openicpsr_archive_search_html=openicpsr_archive_search_html,
        metadata_records_html=metadata_records_html,
        repository_operations_html=repository_operations_html,
        candidate_query_html=candidate_query_html,
        direct_openicpsr_probes=direct_openicpsr_probes,
        source_url=args.source_url,
        study_search_url=args.study_search_url,
        variable_search_url=args.variable_search_url,
        publication_search_url=args.publication_search_url,
        openicpsr_archive_search_url=args.openicpsr_archive_search_url,
        metadata_records_url=args.metadata_records_url,
        repository_operations_url=args.repository_operations_url,
        openicpsr_home_url=args.openicpsr_home_url,
        openicpsr_about_url=args.openicpsr_about_url,
        openicpsr_faq_url=args.openicpsr_faq_url,
        openicpsr_repositories_url=args.openicpsr_repositories_url,
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
