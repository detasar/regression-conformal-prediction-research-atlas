"""Build a neutral, claim-bounded result ledger for regression CP.

The ledger is a manuscript-preparation control, not final prose. It turns the
current evidence packets into source-traceable result rows and keeps every
method statement inside the no-promotion scientific policy.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_neutral_result_ledger_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/neutral_result_ledger.json")
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary") if isinstance(payload, dict) else {}
    return value if isinstance(value, dict) else {}


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def source_exists(root: Path, path: str) -> bool:
    return (root / path).exists()


def metric_text(metrics: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in sorted(metrics):
        value = metrics[key]
        if isinstance(value, dict):
            value = json.dumps(value, sort_keys=True)
        parts.append(f"{key}={value}")
    return "; ".join(parts)


def result_row(
    *,
    result_id: str,
    result_family: str,
    evidence_strength: str,
    claim_status: str,
    observed_result: str,
    allowed_interpretation: str,
    forbidden_interpretations: list[str],
    source_artifacts: list[str],
    extracted_metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "result_id": result_id,
        "result_family": result_family,
        "evidence_strength": evidence_strength,
        "claim_status": claim_status,
        "observed_result": observed_result,
        "allowed_interpretation": allowed_interpretation,
        "forbidden_interpretations": forbidden_interpretations,
        "source_artifacts": source_artifacts,
        "extracted_metrics": extracted_metrics,
        "source_traceability_status": "pending",
        "final_method_selection_authorized": False,
        "final_visual_table_retention_authorized": False,
        "final_manuscript_prose_permission": False,
        "positive_claim_promotion_authorized": False,
        "sterile_repository_creation_authorized": False,
    }


def build_rows(root: Path) -> list[dict[str, Any]]:
    accounting_path = REPORT_DIR / "experiment_accounting_audit.json"
    method_perf_path = REPORT_DIR / "method_performance_synthesis.json"
    robustness_path = REPORT_DIR / "method_selection_robustness_audit.json"
    selection_path = Path(
        "experiments/regression/manuscript/selection_multiplicity_evidence_record.json"
    )
    va_claim_path = REPORT_DIR / "venn_abers_claim_gate_matrix.json"
    va_negative_path = REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
    va_failure_path = REPORT_DIR / "venn_abers_grid_failure_mode_decomposition.json"
    bounded_path = REPORT_DIR / "bounded_support_endpoint_closure_audit.json"
    bounded_positive_path = Path(
        "experiments/regression/manuscript/"
        "bounded_support_positive_validation_protocol.json"
    )
    fairness_group_path = REPORT_DIR / "fairness_group_diagnostic_audit.json"
    fairness_population_path = REPORT_DIR / "fairness_population_readiness_audit.json"
    visual_render_path = Path(
        "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
    )
    retention_readiness_path = Path(
        "experiments/regression/manuscript/publication_retention_readiness_audit.json"
    )
    kg_navigation_path = Path(
        "experiments/regression/manuscript/kg_navigation_usability_audit.json"
    )
    graph_readiness_path = REPORT_DIR / "graph_artifact_readiness_audit.json"
    neutral_language_path = REPORT_DIR / "neutral_reporting_language_audit.json"
    goal_completion_path = Path(
        "experiments/regression/manuscript/goal_completion_audit.json"
    )
    publication_packets_path = Path(
        "experiments/regression/manuscript/publication_preparation_packets.json"
    )

    accounting = summary(read_json(root / accounting_path))
    method_perf = summary(read_json(root / method_perf_path))
    robustness = summary(read_json(root / robustness_path))
    selection = summary(read_json(root / selection_path))
    va_claim = summary(read_json(root / va_claim_path))
    va_negative = summary(read_json(root / va_negative_path))
    va_failure = summary(read_json(root / va_failure_path))
    bounded = summary(read_json(root / bounded_path))
    bounded_positive = summary(read_json(root / bounded_positive_path))
    fairness_group = summary(read_json(root / fairness_group_path))
    fairness_population = summary(read_json(root / fairness_population_path))
    visual_render = summary(read_json(root / visual_render_path))
    retention_readiness = summary(read_json(root / retention_readiness_path))
    kg_navigation = summary(read_json(root / kg_navigation_path))
    graph_readiness = summary(read_json(root / graph_readiness_path))
    neutral_language = summary(read_json(root / neutral_language_path))
    goal_completion = summary(read_json(root / goal_completion_path))
    publication_packets = summary(read_json(root / publication_packets_path))

    top_methods = method_perf.get("top_frontier_methods") or []
    top_method_text = ", ".join(
        f"{row.get('cp_method')}:{row.get('frontier_cell_count')}"
        for row in top_methods[:3]
        if isinstance(row, dict)
    )

    return [
        result_row(
            result_id="empirical_scope_accounting",
            result_family="experiment_scope",
            evidence_strength="accounted_completed_ledger_scope",
            claim_status=str(accounting.get("overall_status")),
            observed_result=(
                "Publication accounting currently records "
                f"{accounting.get('publication_completed_rows')} completed rows, "
                f"{accounting.get('ledger_file_count')} ledger files, "
                f"and Venn-Abers grid completion "
                f"{accounting.get('venn_grid_completion_fraction')}."
            ),
            allowed_interpretation=(
                "Use as scope/accounting evidence for completed regression CP runs."
            ),
            forbidden_interpretations=[
                "Do not treat row count as proof of final method selection.",
                "Do not treat grid completion as Venn-Abers validation.",
            ],
            source_artifacts=[str(accounting_path)],
            extracted_metrics={
                "publication_completed_rows": accounting.get(
                    "publication_completed_rows"
                ),
                "canonical_completed_row_count": accounting.get(
                    "canonical_completed_row_count"
                ),
                "ledger_file_count": accounting.get("ledger_file_count"),
                "venn_grid_completion_fraction": accounting.get(
                    "venn_grid_completion_fraction"
                ),
                "failed_check_count": accounting.get("failed_check_count"),
            },
        ),
        result_row(
            result_id="method_performance_descriptive_frontier",
            result_family="method_performance",
            evidence_strength="descriptive_frontier_synthesis",
            claim_status=str(method_perf.get("claim_status")),
            observed_result=(
                "Descriptive frontier synthesis covers "
                f"{method_perf.get('completed_ledger_rows')} completed rows, "
                f"{method_perf.get('dataset_count')} datasets, "
                f"{method_perf.get('method_count')} methods, and top frontier "
                f"counts {top_method_text}."
            ),
            allowed_interpretation=(
                "Report as descriptive evidence about observed frontier frequency."
            ),
            forbidden_interpretations=[
                "Do not call CQR, CV+, or any method the final winner.",
                "Do not convert frontier frequency into a universal recommendation.",
            ],
            source_artifacts=[str(method_perf_path)],
            extracted_metrics={
                "overall_status": method_perf.get("overall_status"),
                "completed_ledger_rows": method_perf.get("completed_ledger_rows"),
                "dataset_count": method_perf.get("dataset_count"),
                "method_count": method_perf.get("method_count"),
                "frontier_cell_count": method_perf.get("frontier_cell_count"),
                "top_frontier_methods": top_methods[:3],
                "can_support_final_method_selection": method_perf.get(
                    "can_support_final_method_selection"
                ),
            },
        ),
        result_row(
            result_id="selection_multiplicity_robustness_diagnostic",
            result_family="selection_multiplicity",
            evidence_strength="post_selection_diagnostic_control",
            claim_status=str(selection.get("claim_status")),
            observed_result=(
                "Diagnostic selection records CQR as the current primary "
                f"candidate, with robustness common-cell count "
                f"{selection.get('robustness_common_cell_count')} and "
                f"post-selection validation rows "
                f"{selection.get('validation_completed_atomic_rows')} / "
                f"{selection.get('validation_expected_atomic_rows')}."
            ),
            allowed_interpretation=(
                "Use as a diagnostic multiplicity and robustness record."
            ),
            forbidden_interpretations=[
                "Do not claim final method/model selection.",
                "Do not ignore the six paper gates that remain blocked.",
            ],
            source_artifacts=[str(selection_path), str(robustness_path)],
            extracted_metrics={
                "diagnostic_primary_method": selection.get(
                    "diagnostic_primary_method"
                ),
                "diagnostic_primary_win_count": selection.get(
                    "diagnostic_primary_win_count"
                ),
                "diagnostic_runner_up_method": selection.get(
                    "diagnostic_runner_up_method"
                ),
                "final_selection_claim_status": selection.get(
                    "final_selection_claim_status"
                ),
                "paper_blocked_gate_count": selection.get("paper_blocked_gate_count"),
                "bootstrap_primary_selection_rate": robustness.get(
                    "bootstrap_primary_selection_rate"
                ),
                "can_support_final_method_selection": selection.get(
                    "can_support_final_method_selection"
                ),
            },
        ),
        result_row(
            result_id="venn_abers_regression_negative_evidence",
            result_family="venn_abers",
            evidence_strength="negative_failure_mode_diagnostic",
            claim_status=str(va_negative.get("manuscript_disposition_status")),
            observed_result=(
                "Venn-Abers regression remains a negative/diagnostic result: "
                f"{va_claim.get('positive_claim_blocked_count')} positive-claim "
                "requirements are blocked, undercoverage run count is "
                f"{va_claim.get('undercoverage_run_count')}, and IVAPD status is "
                f"{va_claim.get('ivapd_interval_cp_status')}."
            ),
            allowed_interpretation=(
                "Report observed Venn-Abers regression failure modes as negative evidence."
            ),
            forbidden_interpretations=[
                "Do not claim validated Venn-Abers regression interval coverage.",
                "Do not force Venn-Abers into the main method recommendation.",
            ],
            source_artifacts=[
                str(va_claim_path),
                str(va_negative_path),
                str(va_failure_path),
            ],
            extracted_metrics={
                "positive_claim_ready": va_claim.get("positive_claim_ready"),
                "positive_claim_blocked_count": va_claim.get(
                    "positive_claim_blocked_count"
                ),
                "undercoverage_run_count": va_claim.get("undercoverage_run_count"),
                "min_panel_grid_reference_coverage": va_claim.get(
                    "min_panel_grid_reference_coverage"
                ),
                "max_panel_grid_hit_upper_rate": va_claim.get(
                    "max_panel_grid_hit_upper_rate"
                ),
                "ivapd_interval_cp_status": va_claim.get("ivapd_interval_cp_status"),
                "negative_result_reporting_ready": va_negative.get(
                    "negative_result_reporting_ready"
                ),
                "grid_failure_claim_status": va_failure.get("claim_status"),
            },
        ),
        result_row(
            result_id="bounded_support_endpoint_no_validity_claim",
            result_family="bounded_support",
            evidence_strength="endpoint_policy_triage",
            claim_status=str(bounded.get("bounded_support_validity_claim_boundary")),
            observed_result=(
                "Bounded-support endpoint policy is closed as no-claim evidence: "
                f"{bounded.get('raw_endpoint_excursion_bundle_count')} bundles show "
                "raw endpoint excursions and "
                f"{bounded.get('bounded_support_validity_claim_ready_bundle_count')} "
                "bundles are bounded-support-validity claim ready."
            ),
            allowed_interpretation=(
                "Report endpoint hygiene and no bounded-support validity claim."
            ),
            forbidden_interpretations=[
                "Do not claim bounded-support validity.",
                "Do not treat post-handling validation as endpoint-validity proof.",
            ],
            source_artifacts=[str(bounded_path), str(bounded_positive_path)],
            extracted_metrics={
                "overall_status": bounded.get("overall_status"),
                "bundle_count": bounded.get("bundle_count"),
                "raw_endpoint_excursion_bundle_count": bounded.get(
                    "raw_endpoint_excursion_bundle_count"
                ),
                "bounded_support_validity_claim_ready_bundle_count": bounded.get(
                    "bounded_support_validity_claim_ready_bundle_count"
                ),
                "positive_validation_status": bounded_positive.get("overall_status"),
                "positive_validation_can_support_validity": bounded_positive.get(
                    "can_support_bounded_support_validity"
                ),
            },
        ),
        result_row(
            result_id="fairness_group_diagnostic_no_population_claim",
            result_family="fairness",
            evidence_strength="diagnostic_group_gap_audit",
            claim_status=str(fairness_population.get("fairness_population_claim_status")),
            observed_result=(
                "Fairness diagnostics are complete for "
                f"{fairness_group.get('bundle_count')} bundles, but "
                f"{fairness_population.get('population_fairness_ready_bundle_count')} "
                "bundles are population-fairness ready."
            ),
            allowed_interpretation=(
                "Report group diagnostics, missingness, and uncertainty as diagnostic evidence."
            ),
            forbidden_interpretations=[
                "Do not claim population fairness.",
                "Do not compare protected groups as confirmatory inference.",
            ],
            source_artifacts=[str(fairness_group_path), str(fairness_population_path)],
            extracted_metrics={
                "group_counts_recorded_bundle_count": fairness_group.get(
                    "group_counts_recorded_bundle_count"
                ),
                "group_gap_uncertainty_recorded_bundle_count": fairness_group.get(
                    "group_gap_uncertainty_recorded_bundle_count"
                ),
                "population_fairness_ready_bundle_count": fairness_population.get(
                    "population_fairness_ready_bundle_count"
                ),
                "can_support_publication_ready_fairness": fairness_population.get(
                    "can_support_publication_ready_fairness"
                ),
            },
        ),
        result_row(
            result_id="visual_table_draft_render_no_retention",
            result_family="publication_visuals",
            evidence_strength="draft_render_layout_audit",
            claim_status=str(visual_render.get("overall_status")),
            observed_result=(
                f"{visual_render.get('candidate_row_count')} draft visual/table "
                "candidates were rendered with layout pass/revise counts "
                f"{visual_render.get('layout_pass_count')} / "
                f"{visual_render.get('layout_revise_count')} and "
                f"{visual_render.get('final_retained_artifact_count')} final "
                "retained artifacts; retention-readiness recommendations cover "
                f"{retention_readiness.get('recommendation_row_count')} candidates."
            ),
            allowed_interpretation=(
                "Use as a pre-retention visual/table quality control."
            ),
            forbidden_interpretations=[
                "Do not cite draft visuals as final manuscript figures or tables.",
                "Do not deploy the publication site from draft artifacts.",
            ],
            source_artifacts=[str(visual_render_path), str(retention_readiness_path)],
            extracted_metrics={
                "candidate_row_count": visual_render.get("candidate_row_count"),
                "layout_pass_count": visual_render.get("layout_pass_count"),
                "layout_revise_count": visual_render.get("layout_revise_count"),
                "svg_static_text_overlap_detected_count": visual_render.get(
                    "svg_static_text_overlap_detected_count"
                ),
                "retention_recommendation_complete": retention_readiness.get(
                    "retention_recommendation_complete"
                ),
                "retention_recommendation_row_count": retention_readiness.get(
                    "recommendation_row_count"
                ),
                "final_retained_artifact_count": visual_render.get(
                    "final_retained_artifact_count"
                ),
                "positive_claim_promotion_authorized": visual_render.get(
                    "positive_claim_promotion_authorized"
                ),
            },
        ),
        result_row(
            result_id="knowledge_graph_navigation_release_blocked",
            result_family="knowledge_graph",
            evidence_strength="kg_navigation_and_graph_readiness",
            claim_status=str(kg_navigation.get("release_gate_status")),
            observed_result=(
                "KG navigation is internally ready but release blocked; graph "
                f"readiness status is {graph_readiness.get('overall_status')}."
            ),
            allowed_interpretation=(
                "Use KG as internal traceability and candidate navigation evidence."
            ),
            forbidden_interpretations=[
                "Do not cite the KG as a released public artifact yet.",
                "Do not deploy a site before sterile repository and disclosure review.",
            ],
            source_artifacts=[str(kg_navigation_path), str(graph_readiness_path)],
            extracted_metrics={
                "kg_navigation_status": kg_navigation.get("overall_status"),
                "kg_citable_component_authorized": kg_navigation.get(
                    "kg_citable_component_authorized"
                ),
                "release_gate_status": kg_navigation.get("release_gate_status"),
                "graph_artifact_readiness_status": graph_readiness.get(
                    "overall_status"
                ),
                "graph_failed_check_count": graph_readiness.get(
                    "failed_check_count"
                ),
            },
        ),
        result_row(
            result_id="neutral_publication_policy_no_promotion",
            result_family="claim_policy",
            evidence_strength="neutral_language_and_goal_policy_gate",
            claim_status=str(goal_completion.get("overall_status")),
            observed_result=(
                "Neutral publication preparation is active, while final prose, "
                "sterile repository creation, positive claim language, and goal "
                "completion remain blocked or unauthorized."
            ),
            allowed_interpretation=(
                "Use as the governing policy for scientific no-promotion reporting."
            ),
            forbidden_interpretations=[
                "Do not start final manuscript prose from this ledger.",
                "Do not create the sterile publication repository before its gate opens.",
            ],
            source_artifacts=[
                str(neutral_language_path),
                str(goal_completion_path),
                str(publication_packets_path),
            ],
            extracted_metrics={
                "neutral_language_status": neutral_language.get("overall_status"),
                "unguarded_hit_count": neutral_language.get("unguarded_hit_count"),
                "guarded_hit_count": neutral_language.get("guarded_hit_count"),
                "can_mark_goal_complete": goal_completion.get("can_mark_goal_complete"),
                "neutral_empirical_phase_complete": goal_completion.get(
                    "neutral_empirical_phase_complete"
                ),
                "manuscript_drafting_authorized": publication_packets.get(
                    "manuscript_drafting_authorized"
                ),
                "sterile_repository_creation_authorized": publication_packets.get(
                    "sterile_repository_creation_authorized"
                ),
                "positive_claim_language_blocked": publication_packets.get(
                    "positive_claim_language_blocked"
                ),
            },
        ),
    ]


def finalize_rows(root: Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        missing_sources = [
            path for path in row["source_artifacts"] if not source_exists(root, path)
        ]
        row["missing_source_artifacts"] = missing_sources
        row["source_traceability_status"] = "pass" if not missing_sources else "fail"


def check_row(
    check_id: str,
    passed: bool,
    evidence: dict[str, Any],
    blocker: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "blocker": blocker,
    }


def build_payload(root: Path) -> dict[str, Any]:
    rows = build_rows(root)
    finalize_rows(root, rows)
    claim_status_counts = Counter(str(row["claim_status"]) for row in rows)
    family_counts = Counter(str(row["result_family"]) for row in rows)
    missing_source_count = sum(len(row["missing_source_artifacts"]) for row in rows)
    positive_claim_count = sum(
        1 for row in rows if row["positive_claim_promotion_authorized"]
    )
    final_selection_count = sum(
        1 for row in rows if row["final_method_selection_authorized"]
    )
    final_visual_count = sum(
        1 for row in rows if row["final_visual_table_retention_authorized"]
    )
    prose_count = sum(1 for row in rows if row["final_manuscript_prose_permission"])
    sterile_repo_count = sum(
        1 for row in rows if row["sterile_repository_creation_authorized"]
    )
    source_artifacts = sorted(
        {source for row in rows for source in row["source_artifacts"]}
    )
    row_ids = {row["result_id"] for row in rows}

    checks = [
        check_row(
            "required_result_rows_present",
            row_ids
            == {
                "empirical_scope_accounting",
                "method_performance_descriptive_frontier",
                "selection_multiplicity_robustness_diagnostic",
                "venn_abers_regression_negative_evidence",
                "bounded_support_endpoint_no_validity_claim",
                "fairness_group_diagnostic_no_population_claim",
                "visual_table_draft_render_no_retention",
                "knowledge_graph_navigation_release_blocked",
                "neutral_publication_policy_no_promotion",
            },
            {"row_count": len(rows), "result_ids": sorted(row_ids)},
            "missing_required_result_row",
        ),
        check_row(
            "all_sources_traceable",
            missing_source_count == 0,
            {"missing_source_artifact_count": missing_source_count},
            "source_artifact_missing",
        ),
        check_row(
            "no_positive_claim_promotion",
            positive_claim_count
            == final_selection_count
            == final_visual_count
            == prose_count
            == sterile_repo_count
            == 0,
            {
                "positive_claim_promotion_authorized_count": positive_claim_count,
                "final_method_selection_authorized_count": final_selection_count,
                "final_visual_table_retention_authorized_count": final_visual_count,
                "final_manuscript_prose_permission_count": prose_count,
                "sterile_repository_creation_authorized_count": sterile_repo_count,
            },
            "unauthorized_claim_or_release_detected",
        ),
        check_row(
            "cqr_is_descriptive_not_final_selection",
            any(
                row["result_id"] == "method_performance_descriptive_frontier"
                and "Do not call CQR" in " ".join(row["forbidden_interpretations"])
                for row in rows
            )
            and any(
                row["result_id"] == "selection_multiplicity_robustness_diagnostic"
                and row["extracted_metrics"].get("final_selection_claim_status")
                == "blocked"
                for row in rows
            ),
            {"candidate_method": "cqr", "required_boundary": "blocked final selection"},
            "cqr_promoted_beyond_descriptive_evidence",
        ),
        check_row(
            "venn_abers_negative_or_diagnostic_only",
            any(
                row["result_id"] == "venn_abers_regression_negative_evidence"
                and row["extracted_metrics"].get("positive_claim_ready") is False
                and row["extracted_metrics"].get("negative_result_reporting_ready")
                is True
                for row in rows
            ),
            {"required_boundary": "no validated Venn-Abers regression claim"},
            "venn_abers_promoted_to_positive_claim",
        ),
        check_row(
            "neutral_language_guard_clean",
            any(
                row["result_id"] == "neutral_publication_policy_no_promotion"
                and row["extracted_metrics"].get("unguarded_hit_count") == 0
                for row in rows
            ),
            {"required_unguarded_hit_count": 0},
            "neutral_language_guard_not_clean",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": (
                "neutral_result_ledger_ready_no_method_promotion"
                if not failed_checks
                else "neutral_result_ledger_blocked"
            ),
            "row_count": len(rows),
            "source_artifact_count": len(source_artifacts),
            "result_family_counts": dict(sorted(family_counts.items())),
            "claim_status_counts": dict(sorted(claim_status_counts.items())),
            "missing_source_artifact_count": missing_source_count,
            "positive_claim_promotion_authorized_count": positive_claim_count,
            "final_method_selection_authorized_count": final_selection_count,
            "final_visual_table_retention_authorized_count": final_visual_count,
            "final_manuscript_prose_permission_count": prose_count,
            "sterile_repository_creation_authorized_count": sterile_repo_count,
            "neutral_no_method_promotion_guard_active": True,
            "cqr_descriptive_candidate_recorded": True,
            "venn_abers_negative_result_recorded": True,
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
        },
        "claim_boundaries": [
            "This ledger is a neutral result-control artifact, not final prose.",
            "CQR, CV+, Mondrian, Venn-Abers, fairness, bounded-support, KG, and visual/table statements remain bounded by their source gates.",
            "Descriptive primary-candidate evidence must not be rewritten as final winner, universal recommendation, production readiness, or validated Venn-Abers regression.",
            "Positive, negative, blocked, diagnostic, and no-claim outcomes are all valid scientific results when reported within their observed evidence boundaries.",
        ],
        "source_artifacts": source_artifacts,
        "result_rows": rows,
        "checks": checks,
        "failed_checks": failed_checks,
    }


def markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Neutral Result Ledger",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Result rows: {summary_payload['row_count']}",
        f"- Source artifacts: {summary_payload['source_artifact_count']}",
        f"- Failed checks: {summary_payload['failed_check_count']}",
        f"- Positive-claim promotions authorized: {summary_payload['positive_claim_promotion_authorized_count']}",
        f"- Final method-selection authorizations: {summary_payload['final_method_selection_authorized_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(
        [
            "",
            "## Result Rows",
            "",
            "| Result | Family | Evidence | Claim status | Key metrics |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["result_rows"]:
        lines.append(
            "| "
            f"`{row['result_id']}` | "
            f"`{row['result_family']}` | "
            f"`{row['evidence_strength']}` | "
            f"`{row['claim_status']}` | "
            f"{metric_text(row['extracted_metrics'])} |"
        )
    lines.extend(["", "## Forbidden Interpretations", ""])
    for row in payload["result_rows"]:
        lines.append(f"### `{row['result_id']}`")
        for item in row["forbidden_interpretations"]:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok" if not payload["failed_checks"] else "fail",
                "overall_status": payload["summary"]["overall_status"],
                "row_count": payload["summary"]["row_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
