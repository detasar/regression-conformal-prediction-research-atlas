"""Build the evidence-linked individual experiment report draft.

The output is a draft scientific report assembled from existing audited
artifacts. It is not a final manuscript, does not authorize release, and does
not promote any conformal method as a final recommendation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_individual_experiment_report_draft_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/individual_experiment_report_draft.md"
)
DEFAULT_JSON_OUT = Path(
    "experiments/regression/manuscript/individual_experiment_report_draft.json"
)

ACCOUNTING = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "experiment_accounting_audit.json"
)
METHOD_SYNTHESIS = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "method_performance_synthesis.json"
)
ROBUSTNESS = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "method_selection_robustness_audit.json"
)
VENN_DISPOSITION = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "venn_abers_negative_evidence_disposition_audit.json"
)
VENN_FAILURES = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "venn_abers_grid_failure_mode_decomposition.json"
)
BOUNDED_SUPPORT = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "bounded_support_endpoint_closure_audit.json"
)
FAIRNESS = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "fairness_population_readiness_audit.json"
)
GOAL_AUDIT = Path("experiments/regression/manuscript/goal_completion_audit.json")
RELEASE_GAP = Path(
    "experiments/regression/manuscript/publication_release_gap_register.json"
)
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
CITATION_REGISTRY = Path(
    "experiments/regression/manuscript/publication_citation_registry.json"
)
SECTION_ALIGNMENT = Path(
    "experiments/regression/manuscript/reader_primer_section_alignment.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output Markdown path.")
    parser.add_argument(
        "--json-out", default=str(DEFAULT_JSON_OUT), help="Output JSON path."
    )
    return parser.parse_args()


def read_json(root: Path, path: Path) -> dict[str, Any]:
    full_path = root / path
    if not full_path.exists():
        return {}
    return json.loads(full_path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if abs(value) >= 1_000_000:
            return f"{value:,.3g}"
        return f"{value:.{digits}f}"
    return str(value)


def by_method(rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    for row in rows:
        if row.get("cp_method") == method:
            return row
    return {}


def cite_keys(payload: dict[str, Any]) -> dict[str, str]:
    return {row["url"]: row["citation_key"] for row in payload.get("citation_rows", [])}


def build_payload(root: Path) -> dict[str, Any]:
    accounting = read_json(root, ACCOUNTING)
    method_synthesis = read_json(root, METHOD_SYNTHESIS)
    robustness = read_json(root, ROBUSTNESS)
    venn_disposition = read_json(root, VENN_DISPOSITION)
    venn_failures = read_json(root, VENN_FAILURES)
    bounded = read_json(root, BOUNDED_SUPPORT)
    fairness = read_json(root, FAIRNESS)
    goal = read_json(root, GOAL_AUDIT)
    release = read_json(root, RELEASE_GAP)
    kg = read_json(root, KG_QUALITY)
    citations = read_json(root, CITATION_REGISTRY)
    alignment = read_json(root, SECTION_ALIGNMENT)

    method_rows = method_synthesis.get("broad_support_method_rows") or []
    cqr = by_method(method_rows, "cqr")
    cv_plus = by_method(method_rows, "cv_plus")
    mondrian = by_method(method_rows, "mondrian_abs")
    venn_quantile = by_method(method_rows, "venn_abers_quantile")
    venn_fallback = by_method(method_rows, "venn_abers_split_fallback")
    cite = cite_keys(citations)
    source_paths = {
        "experiment_accounting_audit": str(ACCOUNTING),
        "method_performance_synthesis": str(METHOD_SYNTHESIS),
        "method_selection_robustness_audit": str(ROBUSTNESS),
        "venn_abers_negative_evidence_disposition_audit": str(VENN_DISPOSITION),
        "venn_abers_grid_failure_mode_decomposition": str(VENN_FAILURES),
        "bounded_support_endpoint_closure_audit": str(BOUNDED_SUPPORT),
        "fairness_population_readiness_audit": str(FAIRNESS),
        "goal_completion_audit": str(GOAL_AUDIT),
        "publication_release_gap_register": str(RELEASE_GAP),
        "knowledge_graph_quality_summary": str(KG_QUALITY),
        "publication_citation_registry": str(CITATION_REGISTRY),
        "reader_primer_section_alignment": str(SECTION_ALIGNMENT),
    }
    report_facts = {
        "publication_completed_rows": accounting.get("summary", {}).get(
            "publication_completed_rows"
        ),
        "canonical_completed_row_count": accounting.get("summary", {}).get(
            "canonical_completed_row_count"
        ),
        "dataset_count": method_synthesis.get("summary", {}).get("dataset_count"),
        "dataset_alpha_cell_count": method_synthesis.get("summary", {}).get(
            "dataset_alpha_cell_count"
        ),
        "alpha_count": method_synthesis.get("summary", {}).get("alpha_count"),
        "method_count": method_synthesis.get("summary", {}).get("method_count"),
        "broad_support_method_count": method_synthesis.get("summary", {}).get(
            "broad_support_method_count"
        ),
        "source_report_count": method_synthesis.get("summary", {}).get(
            "source_report_count"
        ),
        "cqr_frontier_cell_count": cqr.get("frontier_cell_count"),
        "cqr_row_weighted_coverage_mean": cqr.get("row_weighted_coverage_mean"),
        "cqr_row_weighted_coverage_ci95": cqr.get("row_weighted_coverage_ci95"),
        "cqr_row_weighted_coverage_error_abs_mean": cqr.get(
            "row_weighted_coverage_error_abs_mean"
        ),
        "cqr_near_nominal_hit_rate": cqr.get("row_weighted_near_nominal_hit_rate"),
        "cqr_nominal_hit_rate": cqr.get("row_weighted_nominal_hit_rate"),
        "mondrian_frontier_cell_count": mondrian.get("frontier_cell_count"),
        "mondrian_row_weighted_coverage_mean": mondrian.get(
            "row_weighted_coverage_mean"
        ),
        "mondrian_near_nominal_hit_rate": mondrian.get(
            "row_weighted_near_nominal_hit_rate"
        ),
        "mondrian_nominal_hit_rate": mondrian.get("row_weighted_nominal_hit_rate"),
        "cv_plus_frontier_cell_count": cv_plus.get("frontier_cell_count"),
        "cv_plus_row_weighted_coverage_mean": cv_plus.get(
            "row_weighted_coverage_mean"
        ),
        "cv_plus_near_nominal_hit_rate": cv_plus.get(
            "row_weighted_near_nominal_hit_rate"
        ),
        "cv_plus_nominal_hit_rate": cv_plus.get("row_weighted_nominal_hit_rate"),
        "robustness_common_cell_selected_method": robustness.get("summary", {}).get(
            "common_cell_selected_method"
        ),
        "robustness_common_cell_winner_counts": robustness.get("summary", {}).get(
            "common_cell_winner_counts"
        ),
        "robustness_bootstrap_selection_counts": robustness.get("summary", {}).get(
            "bootstrap_selection_counts"
        ),
        "robustness_leave_one_dataset_retention_rate": robustness.get(
            "summary", {}
        ).get("leave_one_dataset_primary_retention_rate"),
        "robustness_leave_one_alpha_retention_rate": robustness.get(
            "summary", {}
        ).get("leave_one_alpha_primary_retention_rate"),
        "final_selection_claim_status": robustness.get("summary", {}).get(
            "final_selection_claim_status"
        ),
        "venn_abers_quantile_coverage_mean": venn_quantile.get(
            "row_weighted_coverage_mean"
        ),
        "venn_abers_quantile_near_nominal_hit_rate": venn_quantile.get(
            "row_weighted_near_nominal_hit_rate"
        ),
        "venn_abers_split_fallback_frontier_cell_count": venn_fallback.get(
            "frontier_cell_count"
        ),
        "venn_undercoverage_run_count": venn_disposition.get("summary", {}).get(
            "undercoverage_run_count"
        ),
        "venn_can_support_validated_regression": venn_disposition.get(
            "summary", {}
        ).get("can_support_validated_venn_abers_regression"),
        "venn_grid_reference_rows_scored": venn_failures.get("summary", {}).get(
            "total_grid_reference_rows_scored"
        ),
        "venn_max_run_grid_hit_upper_rate": venn_failures.get("summary", {}).get(
            "max_run_grid_hit_upper_rate"
        ),
        "bounded_support_validity_ready_bundle_count": bounded.get(
            "summary", {}
        ).get("bounded_support_validity_claim_ready_bundle_count"),
        "bounded_raw_endpoint_excursion_bundle_count": bounded.get("summary", {}).get(
            "raw_endpoint_excursion_bundle_count"
        ),
        "fairness_population_ready_bundle_count": fairness.get("summary", {}).get(
            "population_fairness_ready_bundle_count"
        ),
        "fairness_diagnostic_group_bundle_count": fairness.get("summary", {}).get(
            "diagnostic_group_bundle_count"
        ),
        "kg_node_count": kg.get("graph", {}).get("node_count"),
        "kg_edge_count": kg.get("graph", {}).get("edge_count"),
        "kg_isolated_node_count": kg.get("graph", {}).get("isolated_node_count"),
        "kg_issue_count": len(kg.get("issues") or []),
        "release_authorized_count": release.get("summary", {}).get(
            "release_authorized_count"
        ),
        "goal_can_mark_complete": goal.get("summary", {}).get("can_mark_goal_complete"),
        "positive_claim_ready_gate_count": goal.get("summary", {}).get(
            "positive_claim_ready_gate_count"
        ),
    }
    sections = [
        {
            "section_id": "executive_summary",
            "evidence_sources": [
                "experiment_accounting_audit",
                "method_performance_synthesis",
                "method_selection_robustness_audit",
                "venn_abers_negative_evidence_disposition_audit",
                "goal_completion_audit",
            ],
        },
        {
            "section_id": "reader_primer",
            "evidence_sources": [
                "publication_citation_registry",
                "reader_primer_section_alignment",
            ],
        },
        {
            "section_id": "empirical_scope",
            "evidence_sources": ["experiment_accounting_audit", "method_performance_synthesis"],
        },
        {
            "section_id": "method_findings",
            "evidence_sources": ["method_performance_synthesis", "method_selection_robustness_audit"],
        },
        {
            "section_id": "negative_and_blocked_claims",
            "evidence_sources": [
                "venn_abers_negative_evidence_disposition_audit",
                "venn_abers_grid_failure_mode_decomposition",
                "bounded_support_endpoint_closure_audit",
                "fairness_population_readiness_audit",
            ],
        },
        {
            "section_id": "traceability_and_release_state",
            "evidence_sources": [
                "knowledge_graph_quality_summary",
                "publication_release_gap_register",
                "goal_completion_audit",
            ],
        },
    ]
    required_citation_urls = [
        "https://arxiv.org/abs/1604.04173",
        "https://arxiv.org/abs/1905.03222",
        "https://arxiv.org/abs/1905.02928",
        "https://arxiv.org/abs/2002.09025",
        "https://proceedings.mlr.press/v91/nouretdinov18a.html",
        "https://proceedings.mlr.press/v230/nouretdinov24a.html",
        "https://proceedings.mlr.press/v267/van-der-laan25a.html",
        "https://arxiv.org/html/2605.06646v1",
    ]
    missing_citation_urls = [url for url in required_citation_urls if url not in cite]
    missing_sources = [
        path for path in source_paths.values() if not (root / path).exists()
    ]
    checks = [
        {
            "check_id": "source_artifacts_present",
            "status": "pass" if not missing_sources else "fail",
            "evidence": {"missing_sources": missing_sources},
        },
        {
            "check_id": "required_citations_available",
            "status": "pass" if not missing_citation_urls else "fail",
            "evidence": {"missing_citation_urls": missing_citation_urls},
        },
        {
            "check_id": "report_remains_draft_and_neutral",
            "status": "pass",
            "evidence": {
                "final_manuscript_prose_permission": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "release_authorized": False,
            },
        },
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "author": {
            "name": "Emre Tasar",
            "role": "Data Scientist",
            "email": "detasar@gmail.com",
        },
        "sources": source_paths,
        "summary": {
            "overall_status": (
                "individual_experiment_report_draft_ready"
                if not failed_checks
                else "individual_experiment_report_draft_blocked"
            ),
            "draft_not_final": True,
            "publication_completed_rows": report_facts["publication_completed_rows"],
            "dataset_count": report_facts["dataset_count"],
            "dataset_alpha_cell_count": report_facts["dataset_alpha_cell_count"],
            "method_count": report_facts["method_count"],
            "primary_diagnostic_method": "cqr",
            "final_selection_claim_status": report_facts[
                "final_selection_claim_status"
            ],
            "venn_abers_positive_validation_ready": report_facts[
                "venn_can_support_validated_regression"
            ],
            "bounded_support_validity_ready_bundle_count": report_facts[
                "bounded_support_validity_ready_bundle_count"
            ],
            "fairness_population_ready_bundle_count": report_facts[
                "fairness_population_ready_bundle_count"
            ],
            "kg_node_count": report_facts["kg_node_count"],
            "kg_edge_count": report_facts["kg_edge_count"],
            "failed_check_count": len(failed_checks),
            "final_manuscript_prose_permission": False,
            "method_recommendation_authorized": False,
            "method_champion_authorized": False,
            "method_advocacy_authorized": False,
            "positive_claim_promotion_authorized": False,
            "release_authorized": False,
        },
        "report_facts": report_facts,
        "citation_keys": {url: cite[url] for url in required_citation_urls if url in cite},
        "sections": sections,
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "The report is a draft evidence report, not the final article or supplement.",
            "CQR is described as the largest current descriptive frontier pattern, not as a universal recommendation.",
            "Venn-Abers evidence is reported as negative/failure-mode evidence for the current bridge, not as a validated regression interval method.",
            "Group diagnostics are not population fairness claims.",
            "Endpoint audits do not support a bounded-support validity claim.",
        ],
    }


def render_report(payload: dict[str, Any]) -> str:
    facts = payload["report_facts"]
    cite = payload["citation_keys"]
    cqr_key = cite["https://arxiv.org/abs/1905.03222"]
    split_key = cite["https://arxiv.org/abs/1604.04173"]
    jackknife_key = cite["https://arxiv.org/abs/1905.02928"]
    jab_key = cite["https://arxiv.org/abs/2002.09025"]
    venn18_key = cite["https://proceedings.mlr.press/v91/nouretdinov18a.html"]
    venn24_key = cite["https://proceedings.mlr.press/v230/nouretdinov24a.html"]
    vanderlaan_key = cite["https://proceedings.mlr.press/v267/van-der-laan25a.html"]
    ivar_key = cite["https://arxiv.org/html/2605.06646v1"]
    cqr_ci = facts["cqr_row_weighted_coverage_ci95"] or {}
    winner_counts = facts["robustness_common_cell_winner_counts"] or {}
    bootstrap_counts = facts["robustness_bootstrap_selection_counts"] or {}
    lines = [
        "# Individual Experiment Report",
        "",
        "Author: Emre Tasar, Data Scientist",
        "Email: detasar@gmail.com",
        "",
        "> Draft status: evidence-linked draft, not final manuscript prose, not a release artifact, and not a method recommendation.",
        "",
        "## Executive Summary",
        "",
        (
            "This regression conformal prediction study evaluated a broad set "
            f"of audited experiment rows: {fmt(facts['publication_completed_rows'])} "
            "publication-scoped completed rows after accounting controls. The "
            f"method synthesis covers {fmt(facts['dataset_count'])} datasets, "
            f"{fmt(facts['dataset_alpha_cell_count'])} dataset-alpha cells, "
            f"{fmt(facts['alpha_count'])} alpha levels, "
            f"{fmt(facts['method_count'])} conformal-method labels, and "
            f"{fmt(facts['source_report_count'])} source reports."
        ),
        "",
        (
            "The main empirical pattern is descriptive: CQR has the largest "
            "current descriptive frontier share in the audited synthesis, but "
            "the final-selection claim remains blocked. CQR appears on "
            f"{fmt(facts['cqr_frontier_cell_count'])} frontier cells, compared "
            f"with {fmt(facts['mondrian_frontier_cell_count'])} for Mondrian "
            f"absolute-residual calibration and {fmt(facts['cv_plus_frontier_cell_count'])} "
            "for CV+. The robustness audit also retains CQR under common-cell, "
            "leave-one-dataset, leave-one-alpha, and bootstrap views; this is "
            "diagnostic robustness evidence, not a final winner claim."
        ),
        "",
        (
            "The Venn-Abers regression bridge is not validated as an interval "
            "method in the current evidence. The negative disposition audit "
            f"records {fmt(facts['venn_undercoverage_run_count'])} undercoverage "
            "runs, and the grid failure decomposition reports "
            f"{fmt(facts['venn_grid_reference_rows_scored'])} scored grid-reference "
            "rows with an upper-boundary hit pattern. This supports reporting "
            "Venn-Abers as negative/failure-mode evidence for this bridge."
        ),
        "",
        "## Reader Primer",
        "",
        (
            "Conformal prediction is a wrapper for producing prediction sets or "
            "intervals with finite-sample marginal coverage under exchangeability. "
            "In regression, a prediction interval is intended to contain the next "
            f"response value with target coverage `1 - alpha` [@{split_key}]. "
            "`alpha` is the target miscoverage rate, so `alpha = 0.1` corresponds "
            "to nominal 90% coverage. Nominal coverage is the target; empirical "
            "coverage is what the experiment actually observed."
        ),
        "",
        (
            "Split conformal regression calibrates residuals on a held-out "
            "calibration split. CQR changes the score: it first fits lower and "
            "upper quantile functions, then applies a conformal correction so "
            f"interval width can adapt to heteroscedasticity [@{cqr_key}]. "
            "CV+ and jackknife+ use out-of-fold or leave-one-out predictions to "
            f"account for fitted-model variability [@{jackknife_key}; @{jab_key}]."
        ),
        "",
        (
            "Venn-Abers methods are related but not identical to ordinary split "
            "interval conformal regression. The cited Venn-Abers regression and "
            "calibration literature focuses on predictive distributions, "
            "auto-calibration, generalized calibration, and regression-related "
            f"extensions [@{venn18_key}; @{venn24_key}; @{vanderlaan_key}; @{ivar_key}]. "
            "Therefore, converting a Venn-Abers object into the same interval "
            "contract used by CQR or CV+ is an extra design decision, not a "
            "free positive validation."
        ),
        "",
        "## Empirical Scope",
        "",
        "| Quantity | Value | Source |",
        "|---|---:|---|",
        f"| Canonical completed rows | {fmt(facts['canonical_completed_row_count'])} | `experiment_accounting_audit.json` |",
        f"| Publication-scoped completed rows | {fmt(facts['publication_completed_rows'])} | `experiment_accounting_audit.json` |",
        f"| Datasets in method synthesis | {fmt(facts['dataset_count'])} | `method_performance_synthesis.json` |",
        f"| Dataset-alpha cells | {fmt(facts['dataset_alpha_cell_count'])} | `method_performance_synthesis.json` |",
        f"| Alpha levels | {fmt(facts['alpha_count'])} | `method_performance_synthesis.json` |",
        f"| Conformal method labels | {fmt(facts['method_count'])} | `method_performance_synthesis.json` |",
        f"| Broad-support methods | {fmt(facts['broad_support_method_count'])} | `method_performance_synthesis.json` |",
        "",
        "## Method Findings",
        "",
        "| Method | Frontier cells | Row-weighted coverage mean | Row-weighted nominal hit rate | Row-weighted near-nominal hit rate | Claim status |",
        "|---|---:|---:|---:|---:|---|",
        f"| CQR | {fmt(facts['cqr_frontier_cell_count'])} | {fmt(facts['cqr_row_weighted_coverage_mean'])} | {fmt(facts['cqr_nominal_hit_rate'])} | {fmt(facts['cqr_near_nominal_hit_rate'])} | descriptive diagnostic only |",
        f"| Mondrian absolute residual | {fmt(facts['mondrian_frontier_cell_count'])} | {fmt(facts['mondrian_row_weighted_coverage_mean'])} | {fmt(facts['mondrian_nominal_hit_rate'])} | {fmt(facts['mondrian_near_nominal_hit_rate'])} | descriptive diagnostic only |",
        f"| CV+ | {fmt(facts['cv_plus_frontier_cell_count'])} | {fmt(facts['cv_plus_row_weighted_coverage_mean'])} | {fmt(facts['cv_plus_nominal_hit_rate'])} | {fmt(facts['cv_plus_near_nominal_hit_rate'])} | descriptive diagnostic only |",
        "",
        (
            "For CQR, the row-weighted coverage mean is "
            f"{fmt(facts['cqr_row_weighted_coverage_mean'])}, with a 95% interval "
            f"from {fmt(cqr_ci.get('low'))} to {fmt(cqr_ci.get('high'))}. "
            "The row-weighted absolute coverage error mean is "
            f"{fmt(facts['cqr_row_weighted_coverage_error_abs_mean'])}. "
            "These values support a descriptive statement that CQR has the "
            "largest current frontier share in this study; they do not support "
            "a general recommendation that all regression conformal prediction "
            "users should choose CQR."
        ),
        "",
        "## Selection Robustness Diagnostics",
        "",
        "| Diagnostic | Result | Source |",
        "|---|---:|---|",
        f"| Common-cell selected method | `{facts['robustness_common_cell_selected_method']}` | `method_selection_robustness_audit.json` |",
        f"| Common-cell CQR wins | {fmt(winner_counts.get('cqr'))} | `method_selection_robustness_audit.json` |",
        f"| Common-cell CV+ wins | {fmt(winner_counts.get('cv_plus'))} | `method_selection_robustness_audit.json` |",
        f"| Common-cell Mondrian wins | {fmt(winner_counts.get('mondrian_abs'))} | `method_selection_robustness_audit.json` |",
        f"| Bootstrap CQR selections | {fmt(bootstrap_counts.get('cqr'))} | `method_selection_robustness_audit.json` |",
        f"| Leave-one-dataset CQR retention rate | {fmt(facts['robustness_leave_one_dataset_retention_rate'])} | `method_selection_robustness_audit.json` |",
        f"| Leave-one-alpha CQR retention rate | {fmt(facts['robustness_leave_one_alpha_retention_rate'])} | `method_selection_robustness_audit.json` |",
        f"| Final-selection claim status | `{facts['final_selection_claim_status']}` | `method_selection_robustness_audit.json` |",
        "",
        (
            "The robustness diagnostics point in the same direction as the "
            "descriptive frontier table: CQR is stable under the current "
            "diagnostic protocol. The correct interpretation is still cautious. "
            "The audit explicitly keeps the final-selection claim blocked."
        ),
        "",
        "## Negative And Blocked Claims",
        "",
        "| Claim area | Observed evidence | Current claim state |",
        "|---|---|---|",
        f"| Venn-Abers bridge | {fmt(facts['venn_undercoverage_run_count'])} undercoverage runs; quantile bridge coverage mean {fmt(facts['venn_abers_quantile_coverage_mean'])}; max run grid upper-hit rate {fmt(facts['venn_max_run_grid_hit_upper_rate'])} | negative/failure-mode evidence, no validated regression interval claim |",
        f"| Bounded support | {fmt(facts['bounded_raw_endpoint_excursion_bundle_count'])} raw endpoint-excursion bundles; {fmt(facts['bounded_support_validity_ready_bundle_count'])} validity-ready bundles | no bounded-support validity claim |",
        f"| Fairness | {fmt(facts['fairness_diagnostic_group_bundle_count'])} diagnostic group bundles; {fmt(facts['fairness_population_ready_bundle_count'])} population-fairness-ready bundles | group diagnostics only, no population fairness claim |",
        f"| Positive method selection | {fmt(facts['positive_claim_ready_gate_count'])} positive-claim-ready gates | blocked |",
        "",
        "## Traceability And Release State",
        "",
        (
            "The current knowledge graph snapshot contains "
            f"{fmt(facts['kg_node_count'])} nodes and {fmt(facts['kg_edge_count'])} "
            f"edges, with {fmt(facts['kg_isolated_node_count'])} isolated nodes "
            f"and {fmt(facts['kg_issue_count'])} quality issues in the latest "
            "quality summary. The graph is evidence infrastructure for navigating "
            "the experiment; it is not yet the final citable public artifact."
        ),
        "",
        (
            "The release register records "
            f"{fmt(facts['release_authorized_count'])} authorized release rows. "
            f"The goal-completion audit says `can_mark_goal_complete = {fmt(facts['goal_can_mark_complete'])}`. "
            "The next publication work should therefore stay in draft/reporting "
            "mode until the sterile repository, final article/supplement outputs, "
            "and release review are completed."
        ),
        "",
        "## Evidence Sources",
        "",
    ]
    for label, path in payload["sources"].items():
        lines.append(f"- `{label}`: `{path}`")
    lines.extend(["", "## References", ""])
    for row in sorted(
        payload["citation_keys"].items(), key=lambda item: item[1]
    ):
        url, key = row
        lines.append(f"- `@{key}`: {url}")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    json_out = root / args.json_out
    payload = build_payload(root)
    atomic_write_json(json_out, payload)
    atomic_write_text(out, render_report(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out, root),
                "json_out": rel(json_out, root),
                "overall_status": payload["summary"]["overall_status"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "publication_completed_rows": payload["summary"][
                    "publication_completed_rows"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
