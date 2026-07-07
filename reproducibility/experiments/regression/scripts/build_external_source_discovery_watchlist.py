"""Build an external source-family discovery watchlist.

This catalog controls the "find datasets on the internet" part of the
regression study. It records source families, official URLs, current local
coverage, and next discovery actions without claiming exhaustive coverage.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_external_source_discovery_watchlist_v1"
DEFAULT_OUT = Path("experiments/regression/catalogs/external_source_discovery_watchlist.json")
AUDITS_DIR = Path("experiments/regression/audits")
REPORTS_DIR = Path("experiments/regression/reports")
SOURCE_REGISTRY = Path("experiments/regression/catalogs/source_registry.md")
OPENML_DISCOVERY = Path("experiments/regression/catalogs/openml_feature_discovery.jsonl")
OPENML_RANKED = Path("experiments/regression/catalogs/openml_ranked_candidates.jsonl")
DATASET_CANDIDATES = Path("experiments/regression/catalogs/dataset_candidates.jsonl")


@dataclass(frozen=True)
class SourceFamily:
    source_id: str
    label: str
    source_url: str
    source_type: str
    audit_prefixes: tuple[str, ...]
    report_tokens: tuple[str, ...]
    current_external_note: str
    discovery_strategy: str
    inclusion_policy: str
    next_actions: tuple[str, ...]
    non_claims: tuple[str, ...]
    secondary: bool = False


SOURCE_FAMILIES: tuple[SourceFamily, ...] = (
    SourceFamily(
        "openml",
        "OpenML data and supervised-regression task catalog",
        "https://www.openml.org/search?type=data",
        "machine_learning_catalog",
        ("openml_",),
        ("openml_",),
        "OpenML exposes machine-learning datasets and task metadata through website and API discovery.",
        "Continue feature-inspected supervised-regression metadata sweeps; rank sensitive-name and domain-theme hits before manual source audit.",
        "A dataset enters modeling only after local source audit, target/group policy, leakage review, and license/access notes.",
        (
            "Refresh OpenML supervised-regression discovery in bounded batches.",
            "Manually review ranked candidates before adding configs.",
            "Track OpenML mirrors of UCI or other sources as mirrors, not independent evidence.",
        ),
        (
            "OpenML discovery rows are not audited datasets.",
            "OpenML mirrors are not independent source-family evidence.",
        ),
    ),
    SourceFamily(
        "uci",
        "UCI Machine Learning Repository",
        "https://archive.ics.uci.edu/datasets",
        "benchmark_repository",
        ("uci_",),
        ("uci_",),
        "UCI is a maintained benchmark repository with hundreds of datasets.",
        "Use official UCI dataset pages and variable metadata for regression targets, missingness, identifiers, and domain caveats.",
        "Prefer direct UCI source pages over mirrors; audit each target/group setup separately.",
        (
            "Review newly donated UCI regression datasets by date.",
            "Separate ordinal, count, bounded, and continuous targets in target-domain provenance.",
        ),
        (
            "A UCI benchmark result is not domain-policy or fairness evidence.",
            "UCI source availability does not imply clean protected-group semantics.",
        ),
    ),
    SourceFamily(
        "fairlearn",
        "Fairlearn packaged datasets",
        "https://fairlearn.org/main/api_reference/index.html#fairlearn-datasets",
        "fairness_package",
        ("fairlearn_",),
        ("fairlearn_", "acs_income_log1p", "diabetes_los"),
        "Fairlearn exposes benchmarking datasets including ACS Income regression.",
        "Use package loaders when they provide stable fetchers and explicit dataset documentation.",
        "Treat Fairlearn loaders as packaged access paths; trace back to original source where possible.",
        (
            "Keep ACS Income regression separated from binary-classification packaged datasets.",
            "Record loader version and upstream source in every audit.",
        ),
        (
            "Package availability is not a final fairness claim.",
            "A packaged dataset may still require population and weighting policy.",
        ),
    ),
    SourceFamily(
        "folktables",
        "Folktables / ACS PUMS derived tasks",
        "https://github.com/socialfoundations/folktables",
        "census_derived_task_library",
        ("folktables_",),
        ("folktables_", "acs_"),
        "Folktables provides ACS-derived prediction tasks and custom task construction.",
        "Create narrowly scoped regression tasks from ACS PUMS only with explicit state/year, target, group, and weighting boundaries.",
        "ACS-derived tasks require source, retention, sampling, and population-inference caveats.",
        (
            "Expand only after predeclaring state/year/task and target-domain policy.",
            "Keep ACS/Folktables tasks separate from Fairlearn packaged ACS rows.",
        ),
        (
            "ACS-derived diagnostics are not population fairness conclusions without a dedicated design.",
        ),
    ),
    SourceFamily(
        "aif360",
        "AIF360 fairness datasets",
        "https://aif360.readthedocs.io/",
        "fairness_package",
        ("aif360_",),
        ("lawschool", "aif360"),
        "AIF360 supplies fairness benchmark loaders such as Lawschool GPA.",
        "Use AIF360 tasks where regression targets and protected attributes are explicitly documented.",
        "Keep legal/admissions and fairness claims blocked unless claim-register gates pass.",
        (
            "Continue duplicate-scope and grouped-CV controls for Lawschool variants.",
            "Audit every AIF360 loader version and preprocessing choice.",
        ),
        (
            "AIF360 benchmark use is not legal or admissions-policy evidence.",
            "Protected-column availability does not imply publication-ready fairness inference.",
        ),
    ),
    SourceFamily(
        "cdc_nhanes",
        "CDC/NCHS NHANES public datasets",
        "https://wwwn.cdc.gov/nchs/nhanes/",
        "official_public_health_survey",
        ("nhanes_",),
        ("nhanes_",),
        "NHANES provides public questionnaires, examination, laboratory, and documentation files.",
        "Use component-level source docs and survey-design caveats for each biomarker or clinical target.",
        "Health targets require explicit diagnostic, clinical, and population-inference non-claims unless separately designed.",
        (
            "Prioritize target-domain provenance for bounded/clinical measurements.",
            "Keep survey weights and population inference outside current method-engineering runs.",
        ),
        (
            "Current NHANES runs are not clinical guidance.",
            "Current NHANES diagnostics are not population-weighted estimates.",
        ),
    ),
    SourceFamily(
        "ahrq_meps",
        "AHRQ Medical Expenditure Panel Survey",
        "https://meps.ahrq.gov/",
        "official_health_expenditure_survey",
        ("meps_",),
        ("meps_",),
        "MEPS is an official survey source for health care cost, use, and insurance coverage.",
        "Use public-use files only after expenditure target, panel/year, survey design, and privacy caveats are explicit.",
        "MEPS targets are cost/use quantities; use log transforms and endpoint policies carefully.",
        (
            "Extend expenditure targets only after source-file and variable dictionary review.",
            "Record survey design non-claims in every run manifest.",
        ),
        (
            "Current MEPS runs are not health-policy or population expenditure inference.",
        ),
    ),
    SourceFamily(
        "hmda_ffiec",
        "FFIEC/CFPB HMDA public mortgage data",
        "https://ffiec.cfpb.gov/data-publication/modified-lar",
        "official_financial_regulatory_data",
        ("hmda_",),
        ("hmda_",),
        "HMDA public data products include modified loan/application records and aggregate products.",
        "Use bounded state/year samples with explicit regulatory-field missingness and exemption policy.",
        "Mortgage data require strict legal, policy, fairness, and privacy non-claims unless separately approved.",
        (
            "Keep state/year HMDA extracts reproducible and ignored raw data out of Git.",
            "Audit exemption-coded missingness before any modeling expansion.",
        ),
        (
            "Current HMDA runs are not lending-law, compliance, or fair-lending conclusions.",
        ),
    ),
    SourceFamily(
        "college_scorecard",
        "U.S. Department of Education College Scorecard",
        "https://collegescorecard.ed.gov/data/",
        "official_education_data",
        ("college_scorecard_",),
        ("college_scorecard",),
        "College Scorecard provides downloadable and API-accessible U.S. higher-education data.",
        "Use official data dictionary, update date, privacy-suppression handling, and target timing windows.",
        "Institution/program earnings targets require cohort timing and suppression caveats.",
        (
            "Track update date and data dictionary version in every audit.",
            "Separate institution-level and field-of-study targets.",
        ),
        (
            "Current Scorecard runs are not school rankings or policy recommendations.",
        ),
    ),
    SourceFamily(
        "federal_reserve_scf",
        "Federal Reserve Survey of Consumer Finances",
        "https://www.federalreserve.gov/econres/scfindex.htm",
        "official_financial_survey",
        ("scf_",),
        ("scf_",),
        "SCF is an official survey source for household balance-sheet variables.",
        "Use public extracts with signed transforms, family/unit policy, and survey-weight non-claims.",
        "Financial targets require strict outlier, transform, and disclosure-risk documentation.",
        (
            "Keep net-worth transforms and family split policy explicit.",
            "Do not promote survey population claims without survey-design analysis.",
        ),
        (
            "Current SCF runs are not wealth-distribution or policy conclusions.",
        ),
    ),
    SourceFamily(
        "oecd_pisa",
        "OECD PISA public data",
        "https://www.oecd.org/pisa/data/",
        "official_education_assessment_data",
        ("pisa_",),
        ("pisa_",),
        "PISA provides international education assessment data and documentation.",
        "Use plausible-value, school/student hierarchy, country, and replicate-weight caveats.",
        "Assessment data require careful target construction and no country-policy claims by default.",
        (
            "Treat plausible values as measurement design artifacts, not ordinary repeated labels.",
            "Keep school-split and country-scope controls explicit.",
        ),
        (
            "Current PISA runs are not education-system rankings or policy conclusions.",
        ),
    ),
    SourceFamily(
        "stackoverflow",
        "Stack Overflow Developer Survey",
        "https://survey.stackoverflow.co/",
        "public_survey_data",
        ("stackoverflow_",),
        ("stackoverflow_",),
        "Stack Overflow publishes annual developer survey data and schema files.",
        "Use annual schema review, self-selection caveats, compensation transforms, and sparse-group checks.",
        "Survey compensation targets need strict endpoint and population non-claims.",
        (
            "Keep raw compensation and winsor/log robustness as separate future work.",
            "Audit sparse demographic cells before group interpretation.",
        ),
        (
            "Current StackOverflow runs are not developer-population wage or labor-market evidence.",
        ),
    ),
    SourceFamily(
        "oulad",
        "Open University Learning Analytics Dataset",
        "https://analyse.kmi.open.ac.uk/open_dataset",
        "education_learning_analytics_data",
        ("oulad_",),
        ("oulad_",),
        "OULAD is an educational learning-analytics source with assessment and activity data.",
        "Use only after license/access review, temporal leakage audit, and assessment target policy.",
        "Learning analytics targets can leak through future activity unless time windows are explicit.",
        (
            "Promote OULAD only after source audit and temporal leakage controls are checked in.",
        ),
        (
            "OULAD availability is not evidence of student intervention effectiveness.",
        ),
    ),
    SourceFamily(
        "cdc_brfss",
        "CDC Behavioral Risk Factor Surveillance System",
        "https://www.cdc.gov/brfss/annual_data/annual_data.htm",
        "official_public_health_survey",
        ("brfss_",),
        ("brfss_",),
        "CDC BRFSS annual files provide public survey data and documentation for adult health risk behaviors, preventive practices, and health status.",
        "Treat BRFSS as a manual-review source family for health-behavior regression targets after year, state/territory coverage, survey-design fields, missingness, and sensitive health-language policies are explicit.",
        "Do not add BRFSS modeling configs until the exact annual file, questionnaire, weighting/sampling notes, target, group variables, and health non-claims have a local audit.",
        (
            "Review the latest CDC annual data page and data documentation before selecting a BRFSS year.",
            "Predeclare whether the target is continuous, count-like, ordinal, or derived from survey-coded health days.",
            "Record survey-weight, state coverage, and questionnaire-change non-claims before any runner work.",
        ),
        (
            "BRFSS discovery is not clinical guidance or population health inference.",
            "Current BRFSS source-family status does not authorize modeling or fairness claims.",
        ),
    ),
    SourceFamily(
        "ipums_cps",
        "IPUMS CPS harmonized Current Population Survey microdata",
        "https://cps.ipums.org/",
        "harmonized_official_labor_survey_microdata",
        ("ipums_cps_",),
        ("ipums_cps",),
        "IPUMS CPS harmonizes Current Population Survey microdata for social, economic, health, income, and labor research across decades.",
        "Use IPUMS CPS only after extract terms, account/API reproducibility, sample/year/supplement, person/household unit, target, weights, and restricted-use boundaries are explicit.",
        "CPS/IPUMS extracts require reproducible extract metadata and survey-design non-claims before any wage, income, labor, or health target enters modeling.",
        (
            "Define a narrow wage, income, hours, or expenditure-like regression target before extract creation.",
            "Record IPUMS extract metadata and upstream Census/BLS CPS provenance in the local source audit.",
            "Separate harmonized-IPUMS access policy from direct Census/BLS CPS public table usage.",
        ),
        (
            "IPUMS CPS discovery is not labor-market, wage-discrimination, or population fairness evidence.",
            "No CPS target is approved until extract reproducibility and survey-design policy are checked in.",
        ),
    ),
    SourceFamily(
        "world_bank_wdi",
        "World Bank World Development Indicators",
        "https://databank.worldbank.org/source/world-development-indicators",
        "official_macro_time_series_indicators",
        ("world_bank_wdi_", "wdi_"),
        ("world_bank_wdi", "wdi_"),
        "World Development Indicators is the World Bank's primary collection of development indicators, with API-accessible country-year time series compiled from recognized sources.",
        "Treat WDI as a macro/time-series conformal benchmark candidate, not an individual fairness dataset, and audit indicator metadata, missingness, country aggregation, and temporal split design before use.",
        "WDI enters modeling only through an indicator-specific local audit with source IDs, country/year scope, missing-data policy, temporal validation design, and no individual-level fairness claim.",
        (
            "Select a small set of continuous indicators with stable metadata and clear units.",
            "Use World Bank API source IDs and metadata in any future extraction script.",
            "Predefine temporal or country-block split policy before any conformal interval benchmark.",
        ),
        (
            "WDI discovery is not individual fairness evidence.",
            "Country-level indicators are not causal, policy, or development-effectiveness conclusions.",
        ),
    ),
    SourceFamily(
        "icpsr_openicpsr",
        "ICPSR and openICPSR research data repositories",
        "https://www.icpsr.umich.edu/sites/icpsr/find-data",
        "research_data_repository",
        ("icpsr_", "openicpsr_"),
        ("icpsr", "openicpsr"),
        "ICPSR and openICPSR expose study-level, variable-level, and replication-data discovery across social, behavioral, health, economics, government, and related research domains.",
        "Use ICPSR/openICPSR as a repository-level discovery source only; each candidate study needs independent license/access, documentation, variable, target, group, and reuse-policy review.",
        "No ICPSR study enters modeling until study-level terms, citation requirements, public/restricted status, data dictionary, and reproducible download path are documented.",
        (
            "Search study-level metadata for public regression-ready tabular datasets with continuous outcomes.",
            "Reject restricted-use or unclear-license studies unless a separate access protocol is approved.",
            "Record study DOI/citation, variable dictionary, and original article context before modeling.",
        ),
        (
            "ICPSR/openICPSR repository discovery is not dataset audit completion.",
            "Replication data availability is not independent domain validation or fairness evidence.",
        ),
    ),
    SourceFamily(
        "datagov",
        "Data.gov catalog metadata portal",
        "https://catalog.data.gov/",
        "official_open_data_metadata_catalog",
        ("datagov_",),
        ("datagov", "data.gov"),
        "Data.gov exposes metadata for datasets published by federal, state, local, and tribal governments through the current v4 Catalog API and legacy CKAN metadata API.",
        "Use Data.gov as a discovery layer only: every candidate must be traced back to its primary publisher, resource URL, license, data dictionary, target, and group-variable policy before local modeling.",
        "Data.gov catalog hits enter modeling only through dataset-specific local audits; the catalog metadata record is not sufficient provenance for raw data or fairness claims.",
        (
            "Use Data.gov v4 search to identify candidate records in income, housing, health, education, labor, mortgage, and survey domains.",
            "Reject metadata-only records without stable tabular resources and variable documentation.",
            "Resolve primary agency provenance before creating any runner config.",
        ),
        (
            "Data.gov discovery is not a modeled dataset.",
            "Data.gov metadata availability is not a government-policy, legal, population, or fairness claim.",
            "Catalog records are not independent evidence when the primary source is already audited elsewhere.",
        ),
    ),
    SourceFamily(
        "kaggle_secondary",
        "Kaggle and other secondary mirrors",
        "https://www.kaggle.com/datasets",
        "secondary_aggregator",
        (),
        (),
        "Secondary aggregators can reveal candidates but may mirror primary sources with separate license and account constraints.",
        "Use only as discovery hints unless the primary source, license, and reproducible download path are documented.",
        "Do not treat aggregator mirrors as independent evidence.",
        (
            "Prefer official primary sources before adding any Kaggle-derived candidate.",
            "Record account/API/license constraints before local audit.",
        ),
        (
            "Secondary-aggregator discovery is not source provenance.",
        ),
        secondary=True,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def count_named_dirs(base: Path, prefixes: tuple[str, ...] = (), tokens: tuple[str, ...] = ()) -> int:
    if not base.exists():
        return 0
    count = 0
    for path in base.iterdir():
        if not path.is_dir():
            continue
        name = path.name.lower()
        if prefixes and any(name.startswith(prefix.lower()) for prefix in prefixes):
            count += 1
        elif tokens and any(token.lower() in name for token in tokens):
            count += 1
    return count


def source_registry_mentions(source_registry_text: str, family: SourceFamily) -> int:
    terms = {family.source_id, family.label, family.source_url}
    terms.update(family.audit_prefixes)
    terms.update(family.report_tokens)
    lowered = source_registry_text.lower()
    return sum(1 for term in terms if term and str(term).lower() in lowered)


def row_status(family: SourceFamily, audit_count: int, report_count: int, openml_rows: int) -> str:
    if family.secondary:
        return "secondary_discovery_deferred"
    if audit_count and report_count:
        return "implemented_with_audits_and_reports"
    if audit_count:
        return "audited_not_promoted_to_report"
    if family.source_id == "openml" and openml_rows:
        return "metadata_discovery_active"
    return "watchlist_pending_manual_review"


def build_payload(root: Path) -> dict[str, Any]:
    audits_dir = root / AUDITS_DIR
    reports_dir = root / REPORTS_DIR
    source_registry_path = root / SOURCE_REGISTRY
    openml_discovery_path = root / OPENML_DISCOVERY
    openml_ranked_path = root / OPENML_RANKED
    dataset_candidates_path = root / DATASET_CANDIDATES

    source_registry_text = read_text(source_registry_path)
    openml_rows = count_jsonl(openml_discovery_path)
    openml_ranked_rows = count_jsonl(openml_ranked_path)
    candidate_rows = count_jsonl(dataset_candidates_path)
    rows = []
    for family in SOURCE_FAMILIES:
        audit_count = count_named_dirs(audits_dir, prefixes=family.audit_prefixes)
        report_count = count_named_dirs(reports_dir, tokens=family.report_tokens)
        status = row_status(family, audit_count, report_count, openml_rows)
        rows.append(
            {
                "source_id": family.source_id,
                "label": family.label,
                "source_url": family.source_url,
                "source_type": family.source_type,
                "repo_status": status,
                "audit_directory_count": audit_count,
                "report_directory_count": report_count,
                "source_registry_mention_count": source_registry_mentions(
                    source_registry_text,
                    family,
                ),
                "current_external_note": family.current_external_note,
                "discovery_strategy": family.discovery_strategy,
                "inclusion_policy": family.inclusion_policy,
                "next_actions": list(family.next_actions),
                "non_claims": list(family.non_claims),
                "secondary_source": family.secondary,
                "covered_by_local_audit": audit_count > 0,
                "covered_by_local_report": report_count > 0,
            }
        )

    implemented_rows = [
        row for row in rows if row["repo_status"] in {
            "implemented_with_audits_and_reports",
            "audited_not_promoted_to_report",
            "metadata_discovery_active",
        }
    ]
    pending_rows = [
        row for row in rows if row["repo_status"] == "watchlist_pending_manual_review"
    ]
    secondary_rows = [row for row in rows if row["secondary_source"]]
    failed_checks = []
    if openml_rows == 0:
        failed_checks.append(
            {
                "check_id": "openml_discovery_rows_present",
                "message": "OpenML discovery JSONL is empty or missing.",
            }
        )
    if not source_registry_text:
        failed_checks.append(
            {
                "check_id": "source_registry_present",
                "message": "Source registry markdown is missing.",
            }
        )
    if sum(row["covered_by_local_audit"] for row in rows) < 10:
        failed_checks.append(
            {
                "check_id": "minimum_audited_source_families",
                "message": "Fewer than ten source families have local audit coverage.",
            }
        )

    overall_status = (
        "external_source_discovery_watchlist_ready_with_gaps"
        if not failed_checks
        else "external_source_discovery_watchlist_review_required"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "external_review_date": "2026-07-04",
        "sources": {
            "source_registry": rel(source_registry_path, root),
            "openml_feature_discovery": rel(openml_discovery_path, root),
            "openml_ranked_candidates": rel(openml_ranked_path, root),
            "dataset_candidates": rel(dataset_candidates_path, root),
        },
        "summary": {
            "overall_status": overall_status,
            "source_family_count": len(rows),
            "primary_source_family_count": len(rows) - len(secondary_rows),
            "secondary_source_family_count": len(secondary_rows),
            "implemented_or_active_family_count": len(implemented_rows),
            "pending_primary_family_count": len(
                [row for row in pending_rows if not row["secondary_source"]]
            ),
            "local_audited_family_count": sum(row["covered_by_local_audit"] for row in rows),
            "local_reported_family_count": sum(row["covered_by_local_report"] for row in rows),
            "official_url_count": sum(bool(row["source_url"]) for row in rows),
            "openml_discovery_rows": openml_rows,
            "openml_ranked_rows": openml_ranked_rows,
            "dataset_candidate_rows": candidate_rows,
            "failed_check_count": len(failed_checks),
        },
        "claim_boundaries": [
            "This watchlist is a source-family discovery control, not an exhaustive dataset inventory.",
            "A source family can be active even when many individual datasets remain unaudited.",
            "No dataset enters modeling from this watchlist without a local audit, policy record, and claim boundary.",
            "Secondary aggregators are discovery hints, not primary provenance.",
        ],
        "failed_checks": failed_checks,
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# External Source Discovery Watchlist",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- External review date: {payload['external_review_date']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Source families: {summary['source_family_count']} ({summary['primary_source_family_count']} primary, {summary['secondary_source_family_count']} secondary)",
        f"- Implemented or active families: {summary['implemented_or_active_family_count']}",
        f"- Locally audited families: {summary['local_audited_family_count']}",
        f"- Locally reported families: {summary['local_reported_family_count']}",
        f"- OpenML discovery/ranked rows: {summary['openml_discovery_rows']} / {summary['openml_ranked_rows']}",
        f"- Dataset candidate rows: {summary['dataset_candidate_rows']}",
        f"- Failed checks: {summary['failed_check_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Source Families",
            "",
            "| Source | Status | Audits | Reports | Registry mentions | URL |",
            "| --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row['source_id']}` | "
            f"`{row['repo_status']}` | "
            f"{row['audit_directory_count']} | "
            f"{row['report_directory_count']} | "
            f"{row['source_registry_mention_count']} | "
            f"{row['source_url']} |"
        )
    lines.extend(["", "## Next Actions", ""])
    for row in payload["rows"]:
        lines.append(f"### `{row['source_id']}`")
        lines.append(f"- Strategy: {row['discovery_strategy']}")
        lines.append(f"- Inclusion policy: {row['inclusion_policy']}")
        for action in row["next_actions"]:
            lines.append(f"- {action}")
        for non_claim in row["non_claims"]:
            lines.append(f"- Non-claim: {non_claim}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
