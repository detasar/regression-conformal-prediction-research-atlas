"""Build a requirement-by-requirement completion audit for the regression goal.

This artifact is deliberately conservative. It maps the user's broad original
objective to current evidence, records what is complete only within an explicit
scope, and separates neutral empirical completion from downstream publication
deliverables. Positive paper claims are never required for neutral empirical
completion or for pre-prose neutral publication preparation.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_goal_completion_audit_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/goal_completion_audit.json")
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

EXTERNAL_SOURCE_WATCHLIST = Path(
    "experiments/regression/catalogs/external_source_discovery_watchlist.json"
)
METHOD_LITERATURE = REPORT_DIR / "method_literature_coverage_audit.json"
METHOD_PERFORMANCE = REPORT_DIR / "method_performance_synthesis.json"
PUBLICATION_METHODOLOGY = REPORT_DIR / "publication_methodology_audit.json"
EXPERIMENT_ACCOUNTING = REPORT_DIR / "experiment_accounting_audit.json"
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
PAPER_GATE_CLOSURE = Path(
    "experiments/regression/manuscript/paper_gate_closure_map.json"
)
PAPER_GATE_EXECUTION_PLAN = Path(
    "experiments/regression/manuscript/paper_gate_closure_execution_plan.json"
)
PAPER_GATE_PROTOCOL_DESIGN_BUNDLE = Path(
    "experiments/regression/manuscript/paper_gate_protocol_design_bundle.json"
)
BOUNDED_SUPPORT_POSITIVE_VALIDATION = Path(
    "experiments/regression/manuscript/"
    "bounded_support_positive_validation_protocol.json"
)
FAIRNESS_SAMPLING_WEIGHT_POLICY = Path(
    "experiments/regression/manuscript/fairness_sampling_weight_policy.json"
)
FAIRNESS_GROUP_DIAGNOSTIC_AUDIT = (
    REPORT_DIR / "fairness_group_diagnostic_audit.json"
)
FAIRNESS_GROUP_MULTIPLICITY_SCOPE = Path(
    "experiments/regression/manuscript/fairness_group_multiplicity_scope.json"
)
VENN_ABERS_NEGATIVE_DISPOSITION = (
    REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
)
POST_EXPERIMENT_PUBLICATION = Path(
    "experiments/regression/manuscript/post_experiment_publication_program.json"
)
POST_EXPERIMENT_PUBLICATION_ACTIVATION = Path(
    "experiments/regression/manuscript/"
    "post_experiment_publication_activation_audit.json"
)
PUBLICATION_PREPARATION_PACKETS = Path(
    "experiments/regression/manuscript/publication_preparation_packets.json"
)
REVIEWER_DESIGN_BRIEF = Path(
    "experiments/regression/manuscript/reviewer_design_brief.json"
)
REVIEWER_RECONCILIATION = Path(
    "experiments/regression/manuscript/reviewer_reconciliation_matrix.json"
)
VISUAL_TABLE_AUDIT_PLAN = Path(
    "experiments/regression/manuscript/visual_table_audit_plan.json"
)
VISUAL_TABLE_AUDIT_REPORT = Path(
    "experiments/regression/manuscript/visual_table_audit_report.json"
)
VISUAL_TABLE_RENDER_CANDIDATE_AUDIT = Path(
    "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
)
PUBLICATION_RETENTION_READINESS_AUDIT = Path(
    "experiments/regression/manuscript/publication_retention_readiness_audit.json"
)
ARTICLE_SUPPLEMENT_KG_NAVIGATION_INDEX = Path(
    "experiments/regression/manuscript/article_supplement_kg_navigation_index.json"
)
PUBLICATION_RELEASE_GAP_REGISTER = Path(
    "experiments/regression/manuscript/publication_release_gap_register.json"
)
NEUTRAL_PUBLICATION_RELEASE_CUT = Path(
    "experiments/regression/manuscript/neutral_publication_release_cut_decision.json"
)
PRIVATE_STERILE_PUBLICATION_PACKAGE = Path(
    "experiments/regression/manuscript/private_sterile_publication_package_manifest.json"
)
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
GRAPH_ARTIFACT_READINESS = REPORT_DIR / "graph_artifact_readiness_audit.json"
SCIENTIFIC_REVIEW_FINDINGS = REPORT_DIR / "scientific_review_finding_register.json"
MANUSCRIPT_BUNDLE_ELIGIBILITY = Path(
    "experiments/regression/manuscript/bundle_eligibility_matrix.json"
)
CHANGELOG = Path("experiments/regression/CHANGELOG.md")
DATA_SCIENTIST_LOG = Path("experiments/regression/diary/data_scientist_log.md")
CONTROL_FLOW = Path("experiments/regression/graphs/control_flow.mmd")
DATA_FLOW = Path("experiments/regression/graphs/data_flow.mmd")
DEPENDENCY_GRAPH = Path("experiments/regression/graphs/dependency_graph.mmd")

COMPLETE_STATUSES = {"complete", "complete_with_scope_limits"}
NONCOMPLETION_STATUSES = {
    "blocked_positive_claim",
    "planned_deferred",
    "not_verified",
    "incomplete",
}


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
    return payload.get("summary") or {}


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def int_value(payload: dict[str, Any], key: str) -> int:
    try:
        return int(payload.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def float_value(payload: dict[str, Any], key: str) -> float:
    try:
        return float(payload.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def is_complete_status(status: str) -> bool:
    return status in COMPLETE_STATUSES


def source_paths(root: Path, *paths: Path) -> list[str]:
    return [rel(root / path, root) for path in paths if (root / path).exists()]


def git_snapshot(root: Path) -> dict[str, Any]:
    def run_git(args: list[str]) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip()

    latest = run_git(["log", "-1", "--format=%H%x09%s"])
    remote = run_git(["remote", "get-url", "regression-private"])
    branch = run_git(["branch", "--show-current"])
    status = run_git(["status", "--short"])
    latest_hash = None
    latest_subject = None
    if latest:
        parts = latest.split("\t", 1)
        latest_hash = parts[0]
        latest_subject = parts[1] if len(parts) > 1 else ""
    return {
        "git_available": bool(latest),
        "branch": branch,
        "regression_private_remote_configured": bool(remote),
        "regression_private_remote": remote,
        "latest_commit": latest_hash,
        "latest_commit_subject": latest_subject,
        "working_tree_clean_at_audit_start": status == "",
        "working_tree_status_line_count_at_audit_start": 0
        if status in ("", None)
        else len(status.splitlines()),
    }


def closure_rows_by_id(closure_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("gate_id")): row
        for row in closure_map.get("gate_rows", []) or []
        if isinstance(row, dict) and row.get("gate_id")
    }


def requirement_row(
    *,
    requirement_id: str,
    title: str,
    status: str,
    evidence_summary: str,
    source_artifacts: list[str],
    metrics: dict[str, Any] | None = None,
    blockers: list[str] | None = None,
    next_action: str = "",
    scope_limit: str = "",
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "title": title,
        "status": status,
        "completion_ready": is_complete_status(status),
        "evidence_summary": evidence_summary,
        "source_artifacts": source_artifacts,
        "metrics": metrics or {},
        "blockers": blockers or [],
        "next_action": next_action,
        "scope_limit": scope_limit,
    }


def gate_requirement_row(
    *,
    gate_id: str,
    title: str,
    closure_rows: dict[str, dict[str, Any]],
    root: Path,
    source_artifacts: list[str],
) -> dict[str, Any]:
    row = closure_rows.get(gate_id, {})
    positive_ready = bool(row.get("positive_claim_ready"))
    scoped_ready = bool(row.get("scoped_or_negative_path_ready"))
    current_paper_positive_va_required = (
        row.get("metrics") or {}
    ).get("current_manuscript_positive_validation_required")
    status = (
        "complete"
        if positive_ready
        else "complete_with_scope_limits"
        if scoped_ready
        else "blocked_positive_claim"
    )
    allowed = row.get("paper_allowed_language") or []
    disallowed = row.get("paper_disallowed_language") or []
    metrics = dict(row.get("metrics") or {})
    metrics.update(
        {
            "positive_claim_ready": positive_ready,
            "scoped_or_negative_path_ready": scoped_ready,
            "closure_mode": row.get("closure_mode"),
            "gate_class": row.get("gate_class"),
        }
    )
    return requirement_row(
        requirement_id=f"paper_gate:{gate_id}",
        title=title,
        status=status,
        evidence_summary=(
            f"Gate `{gate_id}` is {row.get('current_status')}; "
            f"positive_claim_ready={positive_ready}, "
            f"scoped_or_negative_path_ready={scoped_ready}."
        ),
        source_artifacts=source_artifacts
        or source_paths(root, PAPER_GATE_CLOSURE, PAPER_READINESS),
        metrics=metrics,
        blockers=[] if status in COMPLETE_STATUSES else [gate_id],
        next_action=str(row.get("next_decision") or ""),
        scope_limit=(
            "Allowed language: "
            + "; ".join(str(item) for item in allowed)
            + ". Disallowed language: "
            + "; ".join(str(item) for item in disallowed)
            if allowed or disallowed
            else ""
        ),
    )


def build_payload(root: Path) -> dict[str, Any]:
    external = summary(read_json(root / EXTERNAL_SOURCE_WATCHLIST))
    method_literature = summary(read_json(root / METHOD_LITERATURE))
    method_performance = summary(read_json(root / METHOD_PERFORMANCE))
    publication = summary(read_json(root / PUBLICATION_METHODOLOGY))
    accounting = summary(read_json(root / EXPERIMENT_ACCOUNTING))
    paper_readiness = read_json(root / PAPER_READINESS)
    paper_readiness_summary = summary(paper_readiness)
    closure_map = read_json(root / PAPER_GATE_CLOSURE)
    closure_summary = summary(closure_map)
    closure_rows = closure_rows_by_id(closure_map)
    execution_plan = read_json(root / PAPER_GATE_EXECUTION_PLAN)
    execution_plan_summary = summary(execution_plan)
    protocol_design_bundle = read_json(root / PAPER_GATE_PROTOCOL_DESIGN_BUNDLE)
    protocol_design_summary = summary(protocol_design_bundle)
    bounded_support_positive_validation = read_json(
        root / BOUNDED_SUPPORT_POSITIVE_VALIDATION
    )
    bounded_support_positive_validation_summary = summary(
        bounded_support_positive_validation
    )
    sampling_weight_policy = read_json(root / FAIRNESS_SAMPLING_WEIGHT_POLICY)
    sampling_weight_policy_summary = summary(sampling_weight_policy)
    fairness_group_diagnostic = read_json(root / FAIRNESS_GROUP_DIAGNOSTIC_AUDIT)
    fairness_group_diagnostic_summary = summary(fairness_group_diagnostic)
    fairness_group_multiplicity_scope = read_json(
        root / FAIRNESS_GROUP_MULTIPLICITY_SCOPE
    )
    fairness_group_multiplicity_scope_summary = summary(
        fairness_group_multiplicity_scope
    )
    venn_abers_negative_disposition = read_json(root / VENN_ABERS_NEGATIVE_DISPOSITION)
    venn_abers_negative_disposition_summary = summary(
        venn_abers_negative_disposition
    )
    post_publication = read_json(root / POST_EXPERIMENT_PUBLICATION)
    post_publication_activation = read_json(
        root / POST_EXPERIMENT_PUBLICATION_ACTIVATION
    )
    post_publication_activation_summary = summary(post_publication_activation)
    publication_preparation_packets_summary = summary(
        read_json(root / PUBLICATION_PREPARATION_PACKETS)
    )
    reviewer_design_brief_summary = summary(read_json(root / REVIEWER_DESIGN_BRIEF))
    reviewer_reconciliation_summary = summary(read_json(root / REVIEWER_RECONCILIATION))
    visual_table_audit_plan_summary = summary(read_json(root / VISUAL_TABLE_AUDIT_PLAN))
    visual_table_audit_report_summary = summary(
        read_json(root / VISUAL_TABLE_AUDIT_REPORT)
    )
    visual_table_render_candidate_summary = summary(
        read_json(root / VISUAL_TABLE_RENDER_CANDIDATE_AUDIT)
    )
    publication_retention_readiness_summary = summary(
        read_json(root / PUBLICATION_RETENTION_READINESS_AUDIT)
    )
    article_supplement_kg_navigation_summary = summary(
        read_json(root / ARTICLE_SUPPLEMENT_KG_NAVIGATION_INDEX)
    )
    publication_release_gap_summary = summary(
        read_json(root / PUBLICATION_RELEASE_GAP_REGISTER)
    )
    neutral_release_cut_summary = summary(
        read_json(root / NEUTRAL_PUBLICATION_RELEASE_CUT)
    )
    private_package_summary = summary(
        read_json(root / PRIVATE_STERILE_PUBLICATION_PACKAGE)
    )
    kg_quality = read_json(root / KG_QUALITY)
    kg_graph = kg_quality.get("graph") or {}
    kg_traceability = kg_quality.get("traceability") or {}
    kg_freshness = kg_quality.get("freshness") or {}
    kg_observations = kg_quality.get("observations") or {}
    graph_artifact = summary(read_json(root / GRAPH_ARTIFACT_READINESS))
    scientific_review = summary(read_json(root / SCIENTIFIC_REVIEW_FINDINGS))
    bundle_matrix = summary(read_json(root / MANUSCRIPT_BUNDLE_ELIGIBILITY))
    git = git_snapshot(root)

    graph_files = [CONTROL_FLOW, DATA_FLOW, DEPENDENCY_GRAPH]
    graph_files_present = [path for path in graph_files if (root / path).exists()]
    diary_docs_present = all((root / path).exists() for path in (CHANGELOG, DATA_SCIENTIST_LOG))
    private_package_ready = (
        private_package_summary.get("overall_status")
        == "private_sterile_publication_package_ready"
        and int_value(private_package_summary, "failed_check_count") == 0
        and private_package_summary.get("public_release_authorized") is False
        and private_package_summary.get("working_repository_final_citable") is False
        and private_package_summary.get("method_recommendation_authorized") is False
        and private_package_summary.get("positive_claim_promotion_authorized") is False
        and bool(private_package_summary.get("local_git_commit"))
    )

    rows: list[dict[str, Any]] = [
        requirement_row(
            requirement_id="regression_reframing_and_workbench",
            title="Classification-era workflow reframed for regression conformal prediction",
            status="complete",
            evidence_summary=(
                "Regression method performance and method-literature artifacts are present "
                "and use regression conformal-prediction methods."
            ),
            source_artifacts=source_paths(root, METHOD_PERFORMANCE, METHOD_LITERATURE),
            metrics={
                "method_count": method_performance.get("method_count"),
                "dataset_count": method_performance.get("dataset_count"),
                "completed_ledger_rows": method_performance.get("completed_ledger_rows"),
            },
        ),
        requirement_row(
            requirement_id="external_dataset_discovery_and_source_review",
            title="Internet dataset discovery and source review",
            status=(
                "complete_with_scope_limits"
                if external.get("overall_status")
                == "external_source_discovery_watchlist_ready_with_gaps"
                and int_value(external, "pending_primary_family_count") == 0
                else "incomplete"
            ),
            evidence_summary=(
                "External source watchlist is ready with declared gaps; primary "
                "families are locally audited and no primary family is pending."
            ),
            source_artifacts=source_paths(root, EXTERNAL_SOURCE_WATCHLIST),
            metrics={
                "source_family_count": external.get("source_family_count"),
                "primary_source_family_count": external.get("primary_source_family_count"),
                "local_audited_family_count": external.get("local_audited_family_count"),
                "openml_discovery_rows": external.get("openml_discovery_rows"),
                "openml_ranked_rows": external.get("openml_ranked_rows"),
                "dataset_candidate_rows": external.get("dataset_candidate_rows"),
                "pending_primary_family_count": external.get(
                    "pending_primary_family_count"
                ),
            },
            scope_limit=(
                "This proves a broad audited watchlist, not the literal enumeration "
                "of every possible internet dataset."
            ),
        ),
        requirement_row(
            requirement_id="dataset_audit_preprocessing_and_manifests",
            title="Dataset audit, preprocessing, imputation, feature and manifest coverage",
            status=(
                "complete_with_scope_limits"
                if int_value(publication, "manifest_count") > 0
                and int_value(publication, "failed_check_count") == 0
                else "incomplete"
            ),
            evidence_summary=(
                "Publication methodology audit has manifests and no failed checks; "
                "bundle eligibility records current manuscript eligibility."
            ),
            source_artifacts=source_paths(
                root, PUBLICATION_METHODOLOGY, MANUSCRIPT_BUNDLE_ELIGIBILITY
            ),
            metrics={
                "manifest_count": publication.get("manifest_count"),
                "bundle_index_manifest_count": publication.get(
                    "bundle_index_manifest_count"
                ),
                "bundle_count": bundle_matrix.get("bundle_count"),
                "final_claim_eligible_count": bundle_matrix.get(
                    "final_claim_eligible_count"
                ),
            },
            scope_limit=(
                "The audit supports the current workbench and manuscript bundles; "
                "final promotion is separately blocked by paper gates."
            ),
        ),
        requirement_row(
            requirement_id="resume_safe_experiment_accounting",
            title="Resume-safe ledgers, accounting, and interrupted-run recovery",
            status=(
                "complete"
                if accounting.get("overall_status") == "experiment_accounting_pass"
                and int_value(accounting, "failed_check_count") == 0
                else "incomplete"
            ),
            evidence_summary=(
                "Experiment accounting passes and records raw, canonical, completed, "
                "publication-scope, and Venn-Abers grid rows."
            ),
            source_artifacts=source_paths(root, EXPERIMENT_ACCOUNTING),
            metrics={
                "ledger_file_count": accounting.get("ledger_file_count"),
                "raw_ledger_row_count": accounting.get("raw_ledger_row_count"),
                "canonical_ledger_row_count": accounting.get(
                    "canonical_ledger_row_count"
                ),
                "canonical_completed_row_count": accounting.get(
                    "canonical_completed_row_count"
                ),
                "publication_completed_rows": accounting.get(
                    "publication_completed_rows"
                ),
                "venn_grid_rows_completed": accounting.get("venn_grid_rows_completed"),
                "venn_grid_rows_pending": accounting.get("venn_grid_rows_pending"),
            },
        ),
        requirement_row(
            requirement_id="method_literature_registry_and_dispatch",
            title="Conformal method literature coverage, registry, and runner dispatch",
            status=(
                "complete"
                if method_literature.get("overall_status")
                == "method_literature_coverage_pass"
                and int_value(method_literature, "tracked_gap_count") == 0
                else "incomplete"
            ),
            evidence_summary=(
                "Method literature audit passes with registered and runner-dispatched "
                "methods aligned."
            ),
            source_artifacts=source_paths(root, METHOD_LITERATURE),
            metrics={
                "configured_cp_method_count": method_literature.get(
                    "configured_cp_method_count"
                ),
                "registry_method_count": method_literature.get("registry_method_count"),
                "runner_dispatch_method_count": method_literature.get(
                    "runner_dispatch_method_count"
                ),
                "literature_requirement_count": method_literature.get(
                    "literature_requirement_count"
                ),
                "primary_source_url_count": method_literature.get(
                    "primary_source_url_count"
                ),
            },
        ),
        requirement_row(
            requirement_id="broad_model_method_hyperparameter_search",
            title="Broad model, conformal method, alpha, and hyperparameter search",
            status=(
                "complete_with_scope_limits"
                if method_performance.get("overall_status")
                == "method_performance_synthesis_descriptive_no_final_selection"
                and int_value(method_performance, "failed_check_count") == 0
                else "incomplete"
            ),
            evidence_summary=(
                "Method performance synthesis covers the current publication-scope "
                "surface descriptively, while final selection remains blocked."
            ),
            source_artifacts=source_paths(root, METHOD_PERFORMANCE),
            metrics={
                "completed_ledger_rows": method_performance.get("completed_ledger_rows"),
                "method_count": method_performance.get("method_count"),
                "broad_support_method_count": method_performance.get(
                    "broad_support_method_count"
                ),
                "dataset_count": method_performance.get("dataset_count"),
                "dataset_alpha_cell_count": method_performance.get(
                    "dataset_alpha_cell_count"
                ),
                "frontier_cell_count": method_performance.get("frontier_cell_count"),
                "top_frontier_methods": method_performance.get("top_frontier_methods"),
                "claim_status": method_performance.get("claim_status"),
            },
            scope_limit="Descriptive synthesis only; no final global winner claim.",
        ),
    ]

    gate_titles = {
        "dataset_specific_final_gates": "Dataset-specific final result promotion",
        "endpoint_bounded_support_gate": "Bounded-support endpoint validity claim",
        "fairness_population_inference_gate": "Fairness and population inference claim",
        "final_method_model_selection_gate": "Final method/model winner selection",
        "multiplicity_selection_record": "Selection multiplicity record consumed by final winner claim",
        "venn_abers_regression_validation_gate": "Venn-Abers regression negative-result disposition",
    }
    for gate_id, title in gate_titles.items():
        gate_row = closure_rows.get(gate_id, {})
        rows.append(
            gate_requirement_row(
                gate_id=gate_id,
                title=title,
                closure_rows=closure_rows,
                root=root,
                source_artifacts=[
                    rel(root / Path(path), root)
                    for path in gate_row.get("source_artifacts", []) or []
                    if (root / Path(path)).exists()
                ]
                + source_paths(root, PAPER_GATE_EXECUTION_PLAN)
                + source_paths(root, PAPER_GATE_PROTOCOL_DESIGN_BUNDLE)
                + source_paths(root, FAIRNESS_SAMPLING_WEIGHT_POLICY),
            )
        )

    rows.extend(
        [
            requirement_row(
                requirement_id="leakage_sanity_and_methodology_controls",
                title="Leakage, split, duplicate, endpoint, and methodology sanity controls",
                status=(
                    "complete_with_scope_limits"
                    if int_value(publication, "failed_check_count") == 0
                    and int_value(publication, "unsupported_claim_hits") == 0
                    and publication.get("hard_leakage_status")
                    == "hard_leakage_not_detected_in_scanned_artifacts"
                    else "incomplete"
                ),
                evidence_summary=(
                    "Publication methodology audit has no failed checks, no "
                    "unsupported-claim hits, and no hard leakage in scanned artifacts."
                ),
                source_artifacts=source_paths(root, PUBLICATION_METHODOLOGY),
                metrics={
                    "hard_leakage_status": publication.get("hard_leakage_status"),
                    "unsupported_claim_hits": publication.get("unsupported_claim_hits"),
                    "open_remediation_actions": publication.get(
                        "open_remediation_actions"
                    ),
                    "covered_remediation_actions": publication.get(
                        "covered_remediation_actions"
                    ),
                    "control_status_counts": publication.get("control_status_counts"),
                    "caveat_counts": publication.get("caveat_counts"),
                },
                scope_limit="Controls apply to scanned artifacts and documented caveats.",
            ),
            requirement_row(
                requirement_id="knowledge_graph_quality_and_traceability",
                title="Knowledge graph topology, ontology, provenance, and freshness",
                status=(
                    "complete"
                    if not kg_quality.get("issue_counts_by_severity")
                    and int_value(kg_graph, "isolated_node_count") == 0
                    and float_value(kg_traceability, "explicit_edge_provenance_coverage")
                    >= 1.0
                    else "incomplete"
                ),
                evidence_summary=(
                    "KG quality snapshot has no issues, no isolated nodes, full "
                    "edge provenance, and explicit freshness metrics."
                ),
                source_artifacts=source_paths(root, KG_QUALITY),
                metrics={
                    "node_count": kg_graph.get("node_count"),
                    "edge_count": kg_graph.get("edge_count"),
                    "edge_node_ratio": kg_graph.get("edge_node_ratio"),
                    "isolated_node_count": kg_graph.get("isolated_node_count"),
                    "weak_component_count": kg_graph.get("weak_component_count"),
                    "average_edge_confidence": kg_traceability.get(
                        "average_edge_confidence"
                    ),
                    "edge_provenance_coverage": kg_traceability.get(
                        "explicit_edge_provenance_coverage"
                    ),
                    "edge_selector_provenance_coverage": kg_traceability.get(
                        "edge_selector_provenance_coverage"
                    ),
                    "total_observation_count": kg_observations.get(
                        "total_observation_count"
                    ),
                    "working_tree_relevant_modified_count": (
                        kg_freshness.get("working_tree_relevant_modified_count")
                    ),
                    "working_tree_relevant_untracked_count": (
                        kg_freshness.get("working_tree_relevant_untracked_count")
                    ),
                },
            ),
            requirement_row(
                requirement_id="diary_changelog_and_graph_artifacts",
                title="Data scientist diary, changelog, data-flow, control-flow, dependency, and KG graph artifacts",
                status=(
                    "complete"
                    if diary_docs_present
                    and len(graph_files_present) == len(graph_files)
                    and graph_artifact.get("overall_status")
                    == "graph_artifact_readiness_pass"
                    else "incomplete"
                ),
                evidence_summary=(
                    "Diary/changelog files and graph artifacts are present; graph "
                    "artifact readiness passes."
                ),
                source_artifacts=source_paths(
                    root,
                    CHANGELOG,
                    DATA_SCIENTIST_LOG,
                    CONTROL_FLOW,
                    DATA_FLOW,
                    DEPENDENCY_GRAPH,
                    GRAPH_ARTIFACT_READINESS,
                ),
                metrics={
                    "diary_docs_present": diary_docs_present,
                    "graph_files_present_count": len(graph_files_present),
                    "required_graph_file_count": len(graph_files),
                    "graph_artifact_status": graph_artifact.get("overall_status"),
                    "graph_count": graph_artifact.get("graph_count"),
                },
            ),
            requirement_row(
                requirement_id="private_working_repository_checkpoints",
                title="Private working repository checkpoints and reproducibility metadata",
                status=(
                    "complete_with_scope_limits"
                    if git.get("git_available")
                    and git.get("regression_private_remote_configured")
                    else "not_verified"
                ),
                evidence_summary=(
                    "Git metadata records the regression-private remote and latest "
                    "local commit. Remote visibility and push freshness are external "
                    "state and are not fully proven by this artifact."
                ),
                source_artifacts=[],
                metrics=git,
                scope_limit="Local Git metadata is verified; private/public visibility is not proven by JSON artifacts.",
            ),
            requirement_row(
                requirement_id="artifact_based_parallel_auditors",
                title="KG-quality and scientific-methodology audit agents/equivalent controls",
                status=(
                    "complete_with_scope_limits"
                    if int_value(scientific_review, "hard_open_blocker_count") == 0
                    and not kg_quality.get("issue_counts_by_severity")
                    else "incomplete"
                ),
                evidence_summary=(
                    "Durable artifact-level equivalents exist for KG quality and "
                    "scientific methodology review; live subagent continuity is not "
                    "claimed by this file."
                ),
                source_artifacts=source_paths(root, KG_QUALITY, SCIENTIFIC_REVIEW_FINDINGS),
                metrics={
                    "scientific_review_overall_status": scientific_review.get(
                        "overall_status"
                    ),
                    "hard_open_blocker_count": scientific_review.get(
                        "hard_open_blocker_count"
                    ),
                    "tracked_caveat_count": scientific_review.get(
                        "tracked_caveat_count"
                    ),
                    "kg_issue_counts_by_severity": kg_quality.get(
                        "issue_counts_by_severity"
                    ),
                },
                scope_limit="This verifies durable audit artifacts, not a continuously running live agent.",
            ),
            requirement_row(
                requirement_id="individual_experiment_report_author_standard",
                title="Individual Experiment Report author metadata standard",
                status=(
                    "complete"
                    if (post_publication.get("publication_author") or {}).get(
                        "author_name"
                    )
                    == "Emre Tasar"
                    and bool(
                        (post_publication.get("publication_author") or {}).get(
                            "author_email"
                        )
                    )
                    else "incomplete"
                ),
                evidence_summary=(
                    "Post-experiment publication program records the approved author "
                    "line and email for Individual Experiment Report outputs."
                ),
                source_artifacts=source_paths(root, POST_EXPERIMENT_PUBLICATION),
                metrics=post_publication.get("publication_author") or {},
            ),
            requirement_row(
                requirement_id="sterile_final_publication_repository",
                title="Separate sterile final citable repository",
                status=(
                    "complete_with_scope_limits"
                    if private_package_ready
                    else "planned_deferred"
                ),
                evidence_summary=(
                    "A separate sterile private review package has been generated "
                    "and committed locally; public citable release remains closed "
                    "until explicit user review and approval."
                    if private_package_ready
                    else (
                        "The sterile repository plan exists but is explicitly "
                        "deferred until private package readiness is proven."
                    )
                ),
                source_artifacts=source_paths(
                    root,
                    POST_EXPERIMENT_PUBLICATION,
                    POST_EXPERIMENT_PUBLICATION_ACTIVATION,
                    NEUTRAL_PUBLICATION_RELEASE_CUT,
                    PRIVATE_STERILE_PUBLICATION_PACKAGE,
                ),
                metrics={
                    **(post_publication.get("sterile_publication_repository_plan") or {}),
                    "release_cut_status": neutral_release_cut_summary.get(
                        "overall_status"
                    ),
                    "neutral_private_sterile_repository_preparation_authorized": (
                        neutral_release_cut_summary.get(
                            "neutral_private_sterile_repository_preparation_authorized"
                        )
                    ),
                    "private_package_status": private_package_summary.get(
                        "overall_status"
                    ),
                    "private_package_root": private_package_summary.get(
                        "package_root"
                    ),
                    "private_package_copied_file_count": private_package_summary.get(
                        "copied_file_count"
                    ),
                    "private_package_failed_check_count": private_package_summary.get(
                        "failed_check_count"
                    ),
                    "private_package_local_git_initialized": private_package_summary.get(
                        "local_git_initialized"
                    ),
                    "private_package_local_git_commit": private_package_summary.get(
                        "local_git_commit"
                    ),
                    "public_release_authorized": private_package_summary.get(
                        "public_release_authorized"
                    ),
                    "working_repository_final_citable": private_package_summary.get(
                        "working_repository_final_citable"
                    ),
                },
                blockers=[] if private_package_ready else ["private_package_not_ready"],
                next_action=(
                    "User review must explicitly approve any public citable release "
                    "or remote-public transition."
                    if private_package_ready
                    else (
                        "Generate the sterile private review package after the "
                        "neutral release cut authorizes private packaging."
                    )
                ),
                scope_limit=(
                    "Private review package is ready; public release, final citable "
                    "status, and positive/method-recommendation claims remain closed."
                    if private_package_ready
                    else ""
                ),
            ),
            requirement_row(
                requirement_id="post_experiment_publication_program",
                title="Main article, supplement, KG/site, visual auditor, LaTeX and HTML publication phase",
                status=(
                    "in_progress"
                    if post_publication.get("status")
                    == "neutral_publication_preparation_active"
                    else "planned_deferred"
                ),
                evidence_summary=(
                    "The publication program is active and the pre-prose reviewer, "
                    "visual/table, claim-boundary, release-gap, navigation, private "
                    "LaTeX/HTML review, and private sterile packaging controls are "
                    "reconciled. Final public prose, retained visual selection, "
                    "public KG/site publication, method recommendation, and positive "
                    "claim promotion remain downstream gates."
                ),
                source_artifacts=source_paths(
                    root,
                    POST_EXPERIMENT_PUBLICATION,
                    POST_EXPERIMENT_PUBLICATION_ACTIVATION,
                    PUBLICATION_PREPARATION_PACKETS,
                    REVIEWER_DESIGN_BRIEF,
                    REVIEWER_RECONCILIATION,
                    VISUAL_TABLE_AUDIT_PLAN,
                    VISUAL_TABLE_AUDIT_REPORT,
                    VISUAL_TABLE_RENDER_CANDIDATE_AUDIT,
                    PUBLICATION_RETENTION_READINESS_AUDIT,
                    ARTICLE_SUPPLEMENT_KG_NAVIGATION_INDEX,
                    PUBLICATION_RELEASE_GAP_REGISTER,
                    NEUTRAL_PUBLICATION_RELEASE_CUT,
                    PRIVATE_STERILE_PUBLICATION_PACKAGE,
                ),
                metrics={
                    "status": post_publication.get("status"),
                    "requires_zero_blocked_paper_gates": (
                        post_publication.get("activation_rule") or {}
                    ).get("requires_zero_blocked_paper_gates"),
                    "requires_neutral_empirical_phase_complete": (
                        post_publication.get("activation_rule") or {}
                    ).get("requires_neutral_empirical_phase_complete"),
                    "allows_neutral_scoped_no_claim_publication_route": (
                        post_publication.get("activation_rule") or {}
                    ).get("allows_neutral_scoped_no_claim_publication_route"),
                    "reviewer_required_pass_count": (
                        post_publication.get("reviewer_design_gate") or {}
                    ).get("required_reviewer_pass_count"),
                    "deliverable_count": len(post_publication.get("deliverables") or []),
                    "activation_audit_status": post_publication_activation_summary.get(
                        "overall_status"
                    ),
                    "publication_phase_start_authorized": (
                        post_publication_activation_summary.get(
                            "publication_phase_start_authorized"
                        )
                    ),
                    "manuscript_drafting_authorized": (
                        post_publication_activation_summary.get(
                            "manuscript_drafting_authorized"
                        )
                    ),
                    "activation_blocked_check_count": (
                        post_publication_activation_summary.get("blocked_check_count")
                    ),
                    "activation_caveat_check_count": (
                        post_publication_activation_summary.get("caveat_check_count")
                    ),
                    "preparation_packets_status": (
                        publication_preparation_packets_summary.get("overall_status")
                    ),
                    "reviewer_design_status": (
                        reviewer_design_brief_summary.get("overall_status")
                    ),
                    "reviewer_reconciliation_status": (
                        reviewer_reconciliation_summary.get("overall_status")
                    ),
                    "reviewer_reconciliation_row_count": (
                        reviewer_reconciliation_summary.get("row_count")
                    ),
                    "visual_table_audit_plan_status": (
                        visual_table_audit_plan_summary.get("overall_status")
                    ),
                    "visual_table_pre_retention_status": (
                        visual_table_audit_report_summary.get("overall_status")
                    ),
                    "visual_table_render_candidate_status": (
                        visual_table_render_candidate_summary.get("overall_status")
                    ),
                    "visual_table_layout_pass_count": (
                        visual_table_render_candidate_summary.get("layout_pass_count")
                    ),
                    "visual_table_overlap_detected_count": (
                        visual_table_render_candidate_summary.get(
                            "svg_static_text_overlap_detected_count"
                        )
                    ),
                    "retention_readiness_status": (
                        publication_retention_readiness_summary.get("overall_status")
                    ),
                    "navigation_index_status": (
                        article_supplement_kg_navigation_summary.get("overall_status")
                    ),
                    "release_gap_status": (
                        publication_release_gap_summary.get("overall_status")
                    ),
                    "release_authorized_count": (
                        publication_release_gap_summary.get("release_authorized_count")
                    ),
                    "release_cut_status": neutral_release_cut_summary.get(
                        "overall_status"
                    ),
                    "private_latex_html_static_site_package_authorized": (
                        neutral_release_cut_summary.get(
                            "neutral_latex_html_static_site_package_authorized"
                        )
                    ),
                    "private_package_status": private_package_summary.get(
                        "overall_status"
                    ),
                    "private_package_failed_check_count": private_package_summary.get(
                        "failed_check_count"
                    ),
                    "private_package_copied_file_count": private_package_summary.get(
                        "copied_file_count"
                    ),
                },
                blockers=[
                    "final_manuscript_prose_not_authorized",
                    "final_visual_table_retention_not_authorized",
                    "public_publication_site_deployment_not_authorized",
                    "public_kg_citable_component_not_authorized",
                    "public_citable_release_not_authorized",
                    "method_recommendation_not_authorized",
                    "positive_claim_promotion_not_authorized",
                ],
                next_action=(
                    "Keep the neutral private review package synchronized while "
                    "final public manuscript prose, retained visuals/tables, public "
                    "KG/site deployment, method recommendation, and positive claims "
                    "remain blocked."
                ),
            ),
        ]
    )

    status_counts = Counter(row["status"] for row in rows)
    noncomplete_rows = [
        row for row in rows if row["status"] not in COMPLETE_STATUSES
    ]
    blocked_positive_rows = [
        row for row in rows if row["status"] == "blocked_positive_claim"
    ]
    deferred_rows = [row for row in rows if row["status"] == "planned_deferred"]
    in_progress_rows = [row for row in rows if row["status"] == "in_progress"]
    blocked_gate_ids = [
        row["requirement_id"].split(":", 1)[1]
        for row in blocked_positive_rows
        if row["requirement_id"].startswith("paper_gate:")
    ]
    positive_claim_blocking_gate_ids = [
        gate_id
        for gate_id, row in closure_rows.items()
        if not bool(row.get("positive_claim_ready"))
    ]
    empirical_rows = [
        row
        for row in rows
        if row["requirement_id"]
        not in {
            "post_experiment_publication_program",
            "sterile_final_publication_repository",
        }
    ]
    neutral_empirical_phase_complete = (
        bool(empirical_rows)
        and all(row["status"] in COMPLETE_STATUSES for row in empirical_rows)
        and int_value(closure_summary, "gate_count") > 0
        and int_value(closure_summary, "scoped_or_negative_path_ready_gate_count")
        == int_value(closure_summary, "gate_count")
        and int_value(closure_summary, "local_execution_gap_gate_count") == 0
        and int_value(execution_plan_summary, "ready_action_count") == 0
        and accounting.get("overall_status") == "experiment_accounting_pass"
        and method_literature.get("overall_status") == "method_literature_coverage_pass"
        and method_performance.get("overall_status")
        == "method_performance_synthesis_descriptive_no_final_selection"
    )
    activation_rule = post_publication.get("activation_rule") or {}
    neutral_publication_route_allowed = (
        activation_rule.get("allows_neutral_scoped_no_claim_publication_route") is True
    )
    final_dispositions_complete = (
        int_value(closure_summary, "gate_count") > 0
        and int_value(closure_summary, "scoped_or_negative_path_ready_gate_count")
        == int_value(closure_summary, "gate_count")
    )
    positive_claim_publication_ready = bool(
        closure_summary.get("can_start_post_experiment_publication")
    )
    can_start_publication = (
        neutral_empirical_phase_complete
        and post_publication.get("status") == "neutral_publication_preparation_active"
        and neutral_publication_route_allowed
        and final_dispositions_complete
        and int_value(closure_summary, "local_execution_gap_gate_count") == 0
        and int_value(execution_plan_summary, "ready_action_count") == 0
    )
    can_mark_complete = (
        not noncomplete_rows
        and int_value(paper_readiness_summary, "blocked_gate_count") == 0
        and can_start_publication
    )

    route_options = [
        {
            "route_id": "full_positive_claim_publication",
            "status": "blocked",
            "blocking_gate_ids": positive_claim_blocking_gate_ids,
            "description": (
                "Allows final winner, dataset-promotion, fairness/population, "
                "bounded-support, and validated Venn-Abers claims only after all "
                "positive paper gates pass."
            ),
        },
        {
            "route_id": "scoped_diagnostic_negative_results_publication",
            "status": (
                "active_pre_prose_publication_preparation"
                if can_start_publication
                else "neutral_empirical_phase_complete_publication_preparation_inactive"
                if neutral_empirical_phase_complete
                else "not_ready"
            ),
            "blocking_rule": (
                "final prose, retained figure/table selection, sterile release, "
                "and positive claims remain downstream-gated"
            ),
            "description": (
                "Allows pre-prose reviewer design and visual/table inventory for "
                "a neutral no-promotion paper that reports scoped, negative, "
                "diagnostic, and no-claim results exactly as observed."
            ),
        },
    ]

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": (
                "goal_completion_audit_complete"
                if can_mark_complete
                else (
                    "goal_completion_audit_neutral_empirical_complete_"
                    "publication_preparation_active"
                )
                if neutral_empirical_phase_complete and can_start_publication
                else "goal_completion_audit_neutral_empirical_complete_publication_deferred"
                if neutral_empirical_phase_complete
                else "goal_completion_audit_incomplete_with_evidence"
            ),
            "can_mark_goal_complete": can_mark_complete,
            "neutral_empirical_phase_complete": neutral_empirical_phase_complete,
            "empirical_completion_policy": (
                "neutral_no_promotion_route_accepted"
                if neutral_empirical_phase_complete
                else "neutral_no_promotion_route_not_ready"
            ),
            "can_start_post_experiment_publication": can_start_publication,
            "can_start_post_experiment_publication_preparation": can_start_publication,
            "positive_claim_publication_ready": positive_claim_publication_ready,
            "neutral_publication_route_allowed": neutral_publication_route_allowed,
            "final_dispositions_complete": final_dispositions_complete,
            "requirement_count": len(rows),
            "empirical_requirement_count": len(empirical_rows),
            "complete_or_scoped_requirement_count": sum(
                1 for row in rows if row["status"] in COMPLETE_STATUSES
            ),
            "strict_complete_requirement_count": sum(
                1 for row in rows if row["status"] == "complete"
            ),
            "noncomplete_requirement_count": len(noncomplete_rows),
            "blocked_positive_claim_requirement_count": len(blocked_positive_rows),
            "positive_claim_blocking_gate_count": len(positive_claim_blocking_gate_ids),
            "positive_claim_blocking_gate_ids": positive_claim_blocking_gate_ids,
            "planned_deferred_requirement_count": len(deferred_rows),
            "in_progress_requirement_count": len(in_progress_rows),
            "post_experiment_publication_activation_status": (
                post_publication_activation_summary.get("overall_status")
            ),
            "post_experiment_publication_phase_start_authorized": (
                post_publication_activation_summary.get(
                    "publication_phase_start_authorized"
                )
            ),
            "post_experiment_private_manuscript_drafting_authorized": (
                post_publication_activation_summary.get(
                    "private_manuscript_drafting_authorized"
                )
            ),
            "post_experiment_manuscript_drafting_authorized": (
                post_publication_activation_summary.get(
                    "manuscript_drafting_authorized"
                )
            ),
            "post_experiment_publication_activation_blocked_check_count": (
                post_publication_activation_summary.get("blocked_check_count")
            ),
            "post_experiment_publication_activation_caveat_check_count": (
                post_publication_activation_summary.get("caveat_check_count")
            ),
            "status_counts": dict(sorted(status_counts.items())),
            "paper_readiness_status": paper_readiness_summary.get("overall_status"),
            "paper_blocked_gate_count": paper_readiness_summary.get(
                "blocked_gate_count"
            ),
            "paper_gate_closure_status": closure_summary.get("overall_status"),
            "paper_gate_closure_execution_plan_status": (
                execution_plan_summary.get("overall_status")
            ),
            "paper_gate_closure_action_count": execution_plan_summary.get(
                "action_count"
            ),
            "paper_gate_closure_ready_action_count": execution_plan_summary.get(
                "ready_action_count"
            ),
            "paper_gate_protocol_design_bundle_status": (
                protocol_design_summary.get("overall_status")
            ),
            "paper_gate_protocol_design_complete_action_count": (
                protocol_design_summary.get("completed_protocol_design_action_count")
            ),
            "paper_gate_protocol_design_downstream_action_count": (
                protocol_design_summary.get("downstream_action_count")
            ),
            "bounded_support_positive_validation_status": (
                bounded_support_positive_validation_summary.get("overall_status")
            ),
            "bounded_support_positive_validation_action_status": (
                bounded_support_positive_validation_summary.get("action_status")
            ),
            "bounded_support_positive_validation_complete_action_count": (
                1
                if bounded_support_positive_validation_summary.get("action_status")
                == "empirical_validation_complete_no_bounded_support_claim"
                else 0
            ),
            "bounded_support_positive_validation_acceptance_failed_count": (
                bounded_support_positive_validation_summary.get(
                    "positive_acceptance_failed_count"
                )
            ),
            "bounded_support_positive_validation_interval_score_missing_bundle_count": (
                bounded_support_positive_validation_summary.get(
                    "interval_score_metrics_missing_bundle_count"
                )
            ),
            "bounded_support_positive_validation_claim_ready_bundle_count": (
                bounded_support_positive_validation_summary.get(
                    "positive_claim_ready_bundle_count"
                )
            ),
            "bounded_support_positive_validation_can_support_validity": (
                bounded_support_positive_validation_summary.get(
                    "can_support_bounded_support_validity"
                )
            ),
            "fairness_sampling_weight_policy_status": (
                sampling_weight_policy_summary.get("overall_status")
            ),
            "fairness_sampling_weight_policy_complete_action_count": (
                1
                if sampling_weight_policy_summary.get("action_status")
                == "protocol_design_complete"
                else 0
            ),
            "fairness_group_diagnostic_audit_status": (
                fairness_group_diagnostic_summary.get("overall_status")
            ),
            "fairness_group_diagnostic_complete_action_count": (
                1
                if fairness_group_diagnostic_summary.get("action_status")
                == "empirical_execution_complete"
                else 0
            ),
            "fairness_group_diagnostic_gap_uncertainty_recorded_bundle_count": (
                fairness_group_diagnostic_summary.get(
                    "group_gap_uncertainty_recorded_bundle_count"
                )
            ),
            "fairness_group_multiplicity_scope_status": (
                fairness_group_multiplicity_scope_summary.get("overall_status")
            ),
            "fairness_group_multiplicity_scope_complete_action_count": (
                1
                if fairness_group_multiplicity_scope_summary.get("action_status")
                == "multiplicity_control_complete"
                else 0
            ),
            "fairness_group_multiplicity_scope_claim_ready": (
                fairness_group_multiplicity_scope_summary.get(
                    "current_manuscript_fairness_population_claim_ready"
                )
            ),
            "positive_claim_ready_gate_count": closure_summary.get(
                "positive_claim_ready_gate_count"
            ),
            "scoped_or_negative_path_ready_gate_count": closure_summary.get(
                "scoped_or_negative_path_ready_gate_count"
            ),
            "current_paper_blocking_gate_count": closure_summary.get(
                "current_paper_blocking_gate_count"
            ),
            "local_execution_gap_gate_count": closure_summary.get(
                "local_execution_gap_gate_count"
            ),
            "publication_completed_rows": accounting.get("publication_completed_rows"),
            "kg_node_count": kg_graph.get("node_count"),
            "kg_edge_count": kg_graph.get("edge_count"),
            "kg_issue_counts_by_severity": kg_quality.get("issue_counts_by_severity"),
            "primary_diagnostic_method": (
                closure_rows.get("final_method_model_selection_gate", {})
                .get("metrics", {})
                .get("primary_candidate_method")
            ),
            "validated_venn_abers_regression_claim_ready": bool(
                closure_rows.get("venn_abers_regression_validation_gate", {}).get(
                    "positive_claim_ready"
                )
            ),
            "venn_abers_negative_result_reporting_ready": (
                venn_abers_negative_disposition_summary.get(
                    "negative_result_reporting_ready"
                )
            ),
            "current_manuscript_positive_venn_abers_validation_required": (
                venn_abers_negative_disposition_summary.get(
                    "current_manuscript_positive_validation_required"
                )
            ),
        },
        "claim_boundaries": [
            "This audit separates neutral empirical completion from full goal completion.",
            "The empirical phase can be complete under scoped diagnostic, negative, or no-claim dispositions without positive method promotion.",
            "This audit is evidence for full-goal incompletion unless can_mark_goal_complete is true.",
            "Complete-with-scope-limits rows must not be cited as unrestricted completion.",
            "Non-positive scoped rows cannot support final winner, fairness, bounded-support, dataset-promotion, or validated Venn-Abers language.",
            "A complete-with-scope-limits Venn-Abers row means the current manuscript reports the observed negative result; it does not validate Venn-Abers regression.",
            "The scoped diagnostic/negative-results route is active only for pre-prose reviewer design and visual/table audit planning.",
            "Final manuscript prose, retained figure/table selection, positive claims, and sterile repository creation remain separately gated.",
        ],
        "route_options": route_options,
        "requirement_rows": rows,
        "open_blockers": [
            {
                "requirement_id": row["requirement_id"],
                "status": row["status"],
                "blockers": row["blockers"],
                "next_action": row["next_action"],
            }
            for row in noncomplete_rows
        ],
        "sources": {
            "external_source_watchlist": rel(root / EXTERNAL_SOURCE_WATCHLIST, root),
            "method_literature_coverage": rel(root / METHOD_LITERATURE, root),
            "method_performance_synthesis": rel(root / METHOD_PERFORMANCE, root),
            "publication_methodology_audit": rel(root / PUBLICATION_METHODOLOGY, root),
            "experiment_accounting_audit": rel(root / EXPERIMENT_ACCOUNTING, root),
            "paper_readiness_map": rel(root / PAPER_READINESS, root),
            "paper_gate_closure_map": rel(root / PAPER_GATE_CLOSURE, root),
            "paper_gate_closure_execution_plan": rel(
                root / PAPER_GATE_EXECUTION_PLAN, root
            ),
            "paper_gate_protocol_design_bundle": rel(
                root / PAPER_GATE_PROTOCOL_DESIGN_BUNDLE, root
            ),
            "bounded_support_positive_validation_protocol": rel(
                root / BOUNDED_SUPPORT_POSITIVE_VALIDATION, root
            ),
            "fairness_sampling_weight_policy": rel(
                root / FAIRNESS_SAMPLING_WEIGHT_POLICY, root
            ),
            "fairness_group_diagnostic_audit": rel(
                root / FAIRNESS_GROUP_DIAGNOSTIC_AUDIT, root
            ),
            "fairness_group_multiplicity_scope": rel(
                root / FAIRNESS_GROUP_MULTIPLICITY_SCOPE, root
            ),
            "venn_abers_negative_evidence_disposition": rel(
                root / VENN_ABERS_NEGATIVE_DISPOSITION, root
            ),
            "post_experiment_publication_program": rel(
                root / POST_EXPERIMENT_PUBLICATION, root
            ),
            "post_experiment_publication_activation_audit": rel(
                root / POST_EXPERIMENT_PUBLICATION_ACTIVATION, root
            ),
            "knowledge_graph_quality": rel(root / KG_QUALITY, root),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Goal Completion Audit",
        "",
        "This artifact is conservative: it blocks goal completion unless every",
        "explicit requirement is proven by current evidence.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Can mark goal complete: `{summary_payload['can_mark_goal_complete']}`",
        f"- Neutral empirical phase complete: `{summary_payload['neutral_empirical_phase_complete']}`",
        f"- Empirical completion policy: `{summary_payload['empirical_completion_policy']}`",
        f"- Can start post-experiment publication: `{summary_payload['can_start_post_experiment_publication']}`",
        f"- Requirements: {summary_payload['complete_or_scoped_requirement_count']} complete/scoped out of {summary_payload['requirement_count']}",
        f"- Noncomplete requirements: {summary_payload['noncomplete_requirement_count']}",
        f"- Blocked positive-claim requirements: {summary_payload['blocked_positive_claim_requirement_count']}",
        f"- Positive-claim blocking gates: {summary_payload['positive_claim_blocking_gate_count']} `{summary_payload['positive_claim_blocking_gate_ids']}`",
        f"- Planned deferred requirements: {summary_payload['planned_deferred_requirement_count']}",
        f"- Post-experiment publication activation: `{summary_payload['post_experiment_publication_activation_status']}` with start authorized `{summary_payload['post_experiment_publication_phase_start_authorized']}`",
        f"- Paper readiness: `{summary_payload['paper_readiness_status']}`",
        f"- Paper blocked gates: {summary_payload['paper_blocked_gate_count']}",
        f"- Current-paper blocking gates: {summary_payload['current_paper_blocking_gate_count']}",
        f"- Bounded-support positive validation: `{summary_payload['bounded_support_positive_validation_status']}` with {summary_payload['bounded_support_positive_validation_claim_ready_bundle_count']} claim-ready bundles",
        f"- Publication completed rows: {summary_payload['publication_completed_rows']}",
        f"- KG nodes / edges: {summary_payload['kg_node_count']} / {summary_payload['kg_edge_count']}",
        f"- Primary diagnostic method: `{summary_payload['primary_diagnostic_method']}`",
        f"- Venn-Abers negative result reporting ready: `{summary_payload['venn_abers_negative_result_reporting_ready']}`",
        "",
        "## Route Options",
        "",
    ]
    for route in payload["route_options"]:
        lines.extend(
            [
                f"- `{route['route_id']}`: `{route['status']}`",
                f"  - {route['description']}",
            ]
        )
        if route.get("blocking_gate_ids"):
            lines.append(
                "  - Blocking gates: "
                + ", ".join(f"`{gate}`" for gate in route["blocking_gate_ids"])
            )
        if route.get("blocking_rule"):
            lines.append(f"  - Blocking rule: `{route['blocking_rule']}`")
    lines.extend(
        [
            "",
            "## Requirements",
            "",
            "| Requirement | Status | Evidence | Next action |",
            "|---|---:|---|---|",
        ]
    )
    for row in payload["requirement_rows"]:
        next_action = row["next_action"] or "-"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['requirement_id']}`",
                    f"`{row['status']}`",
                    str(row["evidence_summary"]).replace("|", "\\|"),
                    str(next_action).replace("|", "\\|"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundaries",
            "",
        ]
    )
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out, root),
                "overall_status": payload["summary"]["overall_status"],
                "can_mark_goal_complete": payload["summary"][
                    "can_mark_goal_complete"
                ],
                "noncomplete_requirement_count": payload["summary"][
                    "noncomplete_requirement_count"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
