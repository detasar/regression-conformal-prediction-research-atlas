"""Audit regression knowledge graph quality and traceability."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GRAPH = REPO_ROOT / "experiments/regression/catalogs/knowledge_graph.json"
DEFAULT_OUT = (
    REPO_ROOT
    / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
)

PATH_KEYS = ("path", "json_path", "audit_path", "ledger_path", "report_path")
EDGE_PROVENANCE_KEYS = (
    "provenance",
    "provenance_id",
    "evidence",
    "evidence_path",
    "source_file",
    "source_path",
    "sources",
)
SPECIFIC_EDGE_PROVENANCE_KEYS = (
    "evidence",
    "evidence_path",
    "source_path",
    "sources",
)
EDGE_SELECTOR_PROVENANCE_KEYS = ("evidence",)
TOPOLOGY_OBSERVATION_PREFIX = "KG topology observation:"
SUMMARY_KEYS = (
    "summary",
    "description",
    "purpose",
    "notes",
    "fairness_relevance",
    "reason",
    "next_action",
)
METHOD_EDGE_RELATIONS = {
    "QUEUES_METHOD",
    "QUEUES_BASELINE_METHOD",
    "QUEUES_DIAGNOSTIC_METHOD",
}
AUDIT_GAP_DECISIONS = {"queued_manual_audit"}
DATASET_QUEUE_DECISION_MARKERS = (
    "not_runner_queued",
    "queued_manual_audit",
)
SOURCE_REVIEW_DECISION_MARKERS = (
    "exclude_",
    "not_runner_queued",
)
ENDPOINT_RESULT_REQUIRED_RELATIONS = (
    "SUPPORTED_BY_ENDPOINT_AUDIT",
    "SUPPORTS_REPORT",
    "EVALUATES_METHOD",
    "SUMMARIZES_DATASET",
    "REPORTS_METRIC",
)
ENDPOINT_RESULT_CONTEXT_RELATIONS = (
    "SUMMARIZES_CONFIG",
    "HAS_CAVEAT",
    "HAS_ENDPOINT_STATE",
)
ENDPOINT_CAVEAT_REQUIRED_RELATIONS = ("SUPPORTED_BY_ENDPOINT_AUDIT",)
ENDPOINT_STATE_REQUIRED_RELATIONS = ("SUPPORTED_BY_ENDPOINT_AUDIT",)
GROUPED_CV_CONTROL_METHOD_IDS = (
    "method:cv_plus_grouped",
    "method:cv_minmax_grouped",
)

ALLOWED_NODE_TYPES = {
    "audit",
    "catalog",
    "commit",
    "config",
    "dataset",
    "dataset_family",
    "dataset_profile",
    "decision",
    "endpoint_caveat",
    "endpoint_result",
    "endpoint_state",
    "experiment",
    "graph",
    "log",
    "manifest",
    "method",
    "method_config",
    "method_report",
    "method_spec",
    "methodology_control",
    "paper_gate",
    "claim_requirement",
    "manuscript_claim",
    "metric",
    "model",
    "module",
    "openml_review_decision",
    "policy",
    "publication_activation_check",
    "publication_audit_artifact",
    "publication_auditor_contract_rule",
    "publication_design_requirement",
    "publication_deliverable",
    "publication_quality_check",
    "publication_surface",
    "publication_triptych_component",
    "report",
    "reviewer_perspective",
    "run_registry",
    "source",
}

ALLOWED_RELATIONS = {
    "AUDITS_GRAPH",
    "BELONGS_TO_FAMILY",
    "BLOCKED_BY",
    "CITES_SOURCES",
    "COMPLEMENTS",
    "CONFIGURES_METHOD",
    "CONCERNS_DATASET",
    "CONCERNS_METHOD",
    "DECIDES_DATASET",
    "DERIVED_FROM",
    "DOCUMENTS_GRAPH",
    "EVALUATES_METHOD",
    "EVALUATES_METHOD_CONFIG",
    "EVALUATES_MODEL",
    "EVIDENCES",
    "EXTENDS",
    "FROM_SOURCE",
    "GOVERNED_BY",
    "HAS_AUDIT",
    "HAS_CAVEAT",
    "HAS_ENDPOINT_STATE",
    "HAS_PROFILE",
    "HAS_REQUIREMENT",
    "INDEXES_MANIFEST",
    "IMPLEMENTS_PROTOTYPE",
    "IMPLEMENTS_SPEC",
    "MANIFESTS_REPORT",
    "MIRRORS_DATASET",
    "NOTES",
    "QUEUES_BASELINE_METHOD",
    "QUEUES_DATASET",
    "QUEUES_DIAGNOSTIC_METHOD",
    "QUEUES_METHOD",
    "QUEUES_METHOD_CONFIG",
    "QUEUES_MODEL",
    "RECORDED_IN",
    "RECORDED_AT_COMMIT",
    "REGISTERED_IN",
    "REPORTS_METRIC",
    "RENDERS",
    "REVIEWS",
    "REVIEWS_SOURCE",
    "RUNS_DATASETS_FROM",
    "SPECIFIED_BY",
    "SUMMARIZES_CHANGES_TO",
    "SUMMARIZES_CONFIG",
    "SUMMARIZES_CONTROL",
    "SUMMARIZES_DATASET",
    "SUMMARIZES_ENDPOINT_RESULT",
    "SUMMARIZES_MANIFEST",
    "SUPPORTED_BY",
    "SUPPORTED_BY_ENDPOINT_AUDIT",
    "SUPPORTS_REPORT",
    "USES_MODULE",
    "USES_REFERENCE",
    "USES_SCHEMA",
    "VARIANT_OF_DATASET",
    "VARIANT_OF_METHOD",
}

RELATION_RULES: dict[str, tuple[set[str], set[str]]] = {
    "AUDITS_GRAPH": ({"report"}, {"graph"}),
    "BELONGS_TO_FAMILY": ({"dataset"}, {"dataset_family"}),
    "BLOCKED_BY": (
        {"manuscript_claim", "claim_requirement"},
        {
            "report",
            "method_report",
            "methodology_control",
            "endpoint_caveat",
            "paper_gate",
        },
    ),
    "CITES_SOURCES": ({"catalog"}, {"catalog"}),
    "COMPLEMENTS": ({"catalog"}, {"policy"}),
    "CONFIGURES_METHOD": ({"method_config"}, {"method"}),
    "CONCERNS_DATASET": ({"manuscript_claim"}, {"dataset"}),
    "CONCERNS_METHOD": ({"manuscript_claim"}, {"method"}),
    "DECIDES_DATASET": ({"openml_review_decision", "decision"}, {"dataset"}),
    "DERIVED_FROM": (
        {"catalog", "report", "paper_gate", "methodology_control"},
        {"audit", "catalog", "report", "methodology_control"},
    ),
    "DOCUMENTS_GRAPH": ({"graph"}, {"catalog"}),
    "EVALUATES_METHOD": ({"report", "method_report", "endpoint_result"}, {"method"}),
    "EVALUATES_METHOD_CONFIG": (
        {"report", "method_report", "endpoint_result"},
        {"method_config"},
    ),
    "EVALUATES_MODEL": ({"report", "method_report"}, {"model"}),
    "EVIDENCES": ({"method_report", "report"}, {"method_spec"}),
    "EXTENDS": ({"catalog"}, {"catalog"}),
    "FROM_SOURCE": ({"dataset"}, {"source"}),
    "GOVERNED_BY": ({"dataset"}, {"policy"}),
    "HAS_AUDIT": ({"dataset"}, {"audit"}),
    "HAS_PROFILE": ({"audit"}, {"dataset_profile"}),
    "HAS_REQUIREMENT": ({"manuscript_claim"}, {"claim_requirement"}),
    "INDEXES_MANIFEST": ({"catalog"}, {"manifest"}),
    "IMPLEMENTS_PROTOTYPE": ({"module"}, {"method"}),
    "IMPLEMENTS_SPEC": ({"module"}, {"method_spec"}),
    "MANIFESTS_REPORT": ({"manifest"}, {"report", "method_report"}),
    "MIRRORS_DATASET": ({"dataset"}, {"dataset"}),
    "NOTES": ({"log"}, {"catalog"}),
    "QUEUES_BASELINE_METHOD": ({"config"}, {"method"}),
    "QUEUES_DATASET": ({"config"}, {"dataset"}),
    "QUEUES_DIAGNOSTIC_METHOD": ({"config"}, {"method"}),
    "QUEUES_METHOD": ({"config"}, {"method"}),
    "QUEUES_METHOD_CONFIG": ({"config"}, {"method_config"}),
    "QUEUES_MODEL": ({"config"}, {"model"}),
    "RECORDED_IN": (
        {
            "dataset",
            "openml_review_decision",
            "decision",
            "manuscript_claim",
            "claim_requirement",
        },
        {"catalog"},
    ),
    "RECORDED_AT_COMMIT": ({"catalog", "log", "run_registry"}, {"commit"}),
    "REGISTERED_IN": ({"method", "model", "metric"}, {"catalog"}),
    "HAS_CAVEAT": ({"endpoint_result", "report", "method_report"}, {"endpoint_caveat"}),
    "HAS_ENDPOINT_STATE": ({"endpoint_result"}, {"endpoint_state"}),
    "REPORTS_METRIC": (
        {"report", "method_report", "endpoint_result", "manifest"},
        {"metric"},
    ),
    "RENDERS": ({"catalog"}, {"catalog", "report"}),
    "REVIEWS": ({"catalog"}, {"catalog"}),
    "REVIEWS_SOURCE": ({"openml_review_decision", "decision"}, {"source"}),
    "RUNS_DATASETS_FROM": ({"run_registry"}, {"catalog"}),
    "SPECIFIED_BY": ({"method"}, {"method_spec"}),
    "SUMMARIZES_CHANGES_TO": ({"log"}, {"catalog"}),
    "SUMMARIZES_CONFIG": (
        {"report", "method_report", "endpoint_result", "manifest"},
        {"config"},
    ),
    "SUMMARIZES_CONTROL": (
        {"catalog", "report"},
        {
            "methodology_control",
            "paper_gate",
            "publication_activation_check",
            "publication_audit_artifact",
            "publication_auditor_contract_rule",
            "publication_design_requirement",
            "publication_deliverable",
            "publication_quality_check",
            "publication_surface",
            "publication_triptych_component",
            "reviewer_perspective",
        },
    ),
    "SUMMARIZES_DATASET": (
        {"report", "method_report", "endpoint_result", "manifest"},
        {"dataset"},
    ),
    "SUMMARIZES_ENDPOINT_RESULT": ({"report", "method_report"}, {"endpoint_result"}),
    "SUMMARIZES_MANIFEST": ({"report"}, {"manifest"}),
    "SUPPORTED_BY": (
        {"manuscript_claim", "claim_requirement", "manifest"},
        {
            "audit",
            "catalog",
            "commit",
            "config",
            "dataset",
            "dataset_profile",
            "graph",
            "log",
            "manifest",
            "method",
            "method_report",
            "method_spec",
            "methodology_control",
            "metric",
            "policy",
            "report",
            "run_registry",
        },
    ),
    "SUPPORTED_BY_ENDPOINT_AUDIT": (
        {"endpoint_result", "endpoint_caveat", "endpoint_state"},
        {"report", "method_report"},
    ),
    "SUPPORTS_REPORT": (
        {"report", "method_report", "endpoint_result"},
        {"report", "method_report"},
    ),
    "USES_MODULE": ({"report", "method_report"}, {"module"}),
    "USES_REFERENCE": ({"report", "method_report"}, {"method"}),
    "USES_SCHEMA": ({"manifest", "report"}, {"catalog"}),
    "VARIANT_OF_DATASET": ({"dataset"}, {"dataset"}),
    "VARIANT_OF_METHOD": ({"method"}, {"method"}),
}

CRITICAL_CATEGORIES = {
    "dataset": {"dataset"},
    "experiment": {"config", "experiment"},
    "model": {"model"},
    "conformal_method": {"method", "method_config"},
    "metric": {"metric"},
    "audit": {"audit"},
    "policy": {"policy"},
    "report": {"report", "method_report"},
    "commit": {"commit"},
    "decision": {"decision", "openml_review_decision"},
    "manuscript_claim": {"manuscript_claim"},
    "manuscript_manifest": {"manifest"},
}

THRESHOLDS = {
    "min_edge_node_ratio": 2.0,
    "max_isolated_node_ratio": 0.0,
    "max_weak_component_count": 5,
    "min_largest_component_ratio": 0.95,
    "min_edge_provenance_coverage": 0.95,
    "min_specific_edge_provenance_coverage": 0.95,
    "min_edge_confidence_coverage": 0.95,
    "min_confidence_reason_coverage": 0.95,
    "min_average_edge_confidence": 0.80,
    "min_distinct_edge_confidence_values": 3,
    "min_edge_selector_provenance_coverage": 0.80,
    "min_claim_edge_selector_provenance_coverage": 0.95,
    "min_paper_gate_traceability_coverage": 1.0,
    "min_paper_gate_source_selector_coverage": 1.0,
    "max_missing_paper_gate_traceability_links": 0,
    "max_weak_provenance_confidence_one_edges": 0,
    "max_high_multiplicity_edges_without_evidence_samples": 0,
    "max_missing_endpoint_edges": 0,
    "max_duplicate_edge_triples": 0,
    "max_unknown_node_types": 0,
    "max_unknown_relation_types": 0,
    "max_domain_range_violations": 0,
    "min_direct_summary_coverage": 0.70,
    "min_semantic_summary_coverage": 0.50,
    "min_observation_node_ratio": 1.0,
    "min_paper_evidence_observation_node_ratio": 1.0,
    "max_stale_node_paths": 0,
    "max_missing_tracked_configs": 0,
    "max_missing_tracked_reports": 0,
    "max_missing_tracked_audits": 0,
    "max_missing_tracked_graph_docs": 0,
    "max_zero_interval_endpoint_results": 0,
    "max_clean_zero_interval_endpoint_results": 0,
    "max_endpoint_results_without_state": 0,
}

CLAIM_TRACEABILITY_NODE_TYPES = {"manuscript_claim", "claim_requirement"}
CLAIM_TRACEABILITY_RELATIONS = {
    "BLOCKED_BY",
    "CONCERNS_DATASET",
    "CONCERNS_METHOD",
    "HAS_REQUIREMENT",
    "RECORDED_IN",
    "SUPPORTED_BY",
}

STANDALONE_METHODOLOGY_REPORTS = {
    "report:duplicate_sensitivity_closure_audit",
    "report:duplicate_split_caveat_backlog",
    "report:endpoint_schema_backfill_feasibility",
    "report:experiment_accounting_audit",
    "report:feature_leakage_metadata_completeness_triage",
    "report:feature_leakage_provenance_label_backfill",
    "report:feature_leakage_prediction_metadata_repair",
    "report:fairness_group_diagnostic_audit",
    "report:fairness_group_multiplicity_scope",
    "report:fairness_population_readiness_audit",
    "report:final_selection_claim_boundary_audit",
    "report:graph_artifact_readiness_audit",
    "report:integrity_remediation_backlog",
    "report:kg_publication_quality_audit",
    "report:knowledge_graph_quality_summary",
    "report:scientific_review_finding_register",
    "report:manuscript_manifest_completeness_audit",
    "report:manuscript_readiness_map",
    "report:paper_gate_closure_map",
    "report:paper_gate_closure_execution_plan",
    "report:paper_gate_protocol_design_bundle",
    "report:fairness_sampling_weight_policy",
    "report:goal_completion_audit",
    "report:post_experiment_publication_activation_audit",
    "report:publication_preparation_packets",
    "report:reviewer_design_reconciliation",
    "report:publication_visual_table_audit_plan",
    "report:article_supplement_kg_triptych_decision",
    "report:article_supplement_retention_recommendation_matrix",
    "report:article_supplement_blueprint_alignment",
    "report:publication_release_gap_register",
    "report:individual_experiment_report_blueprint",
    "report:claim_safe_result_extraction_matrix",
    "report:manuscript_section_evidence_packet",
    "report:section_claim_boundary_audit",
    "report:article_supplement_kg_navigation_index",
    "report:publication_phase_progress_reconciliation_audit",
    "report:scientific_neutrality_interpretation_lock",
    "report:final_publication_output_authorization_protocol",
    "report:publication_claim_evidence_verification_matrix",
    "report:publication_exemplar_review",
    "report:publication_citation_registry",
    "report:manuscript_claim_citation_readiness_audit",
    "report:reader_method_primer_citation_map",
    "report:reader_primer_section_alignment",
    "report:main_article_draft",
    "report:supplementary_document_draft",
    "report:individual_experiment_report_draft",
    "report:sterile_repository_staging_manifest",
    "report:sterile_repository_readme_draft",
    "report:neutral_publication_release_cut_decision",
    "report:private_publication_repository_remote_audit",
    "report:private_latex_html_review_outputs_manifest",
    "report:private_latex_html_review_output_audit",
    "report:private_sterile_publication_package_manifest",
    "report:publication_authoring_decision_record",
    "report:publication_visual_table_audit_report",
    "report:publication_retention_readiness_audit",
    "report:final_publication_visual_auditor_readiness",
    "report:visual_table_inventory",
    "report:visual_table_iteration_register",
    "report:kg_navigation_usability_audit",
    "report:publication_visual_table_render_candidate_audit",
    "report:visual_table_render_candidate_inventory",
    "report:visual_table_layout_quality_audit",
    "report:dataset_specific_final_gate_audit",
    "report:dataset_final_gate_remediation_plan",
    "report:dataset_final_gate_post_selection_validation_bridge",
    "report:dataset_final_gate_post_selection_validation_bridge_results",
    "report:method_literature_coverage_audit",
    "report:method_selection_alpha_expansion_batch",
    "report:method_selection_alpha_expansion_execution_audit",
    "report:method_selection_post_selection_validation_batch",
    "report:method_selection_post_selection_validation_results",
    "report:main_result_candidate_bundle_plan",
    "report:main_result_candidate_bundle_results",
    "report:main_result_candidate_post_run_closure_audit",
    "report:method_performance_synthesis",
    "report:method_selection_alpha_expansion_plan",
    "report:method_selection_candidate_audit",
    "report:method_selection_inferential_audit",
    "report:method_selection_robustness_audit",
    "report:neutral_experiment_closure_audit",
    "report:neutral_reporting_language_audit",
    "report:neutral_result_ledger",
    "report:paired_duplicate_sensitivity_audit",
    "report:publication_methodology_audit",
    "report:retrospective_quality_gate",
    "report:retrospective_methodology_controls",
    "report:bounded_support_dataset_audit",
    "report:bounded_support_endpoint_closure_audit",
    "report:bounded_support_positive_validation_protocol",
    "report:bounded_support_protocol",
    "report:bounded_support_posthandling_validation",
    "report:target_domain_provenance",
    "report:selection_multiplicity_evidence_record",
    "report:selection_multiplicity_protocol",
    "report:venn_abers_grid_expansion_batch",
    "report:venn_abers_grid_failure_mode_decomposition",
    "report:venn_abers_claim_gate_matrix",
    "report:venn_abers_negative_evidence_disposition_audit",
    "report:venn_abers_grid_expansion_plan",
    "report:venn_abers_grid_ivapd_validation_protocol",
    "report:venn_abers_validation_readiness_audit",
}

SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", default=str(DEFAULT_GRAPH))
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--fail-on",
        choices=("none", "low", "medium", "high", "critical"),
        default="none",
        help="Exit nonzero if any issue has this severity or higher.",
    )
    parser.add_argument("--max-examples", type=int, default=25)
    return parser.parse_args()


def load_graph(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_rel_path(value: Any, repo_root: Path) -> str | None:
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return repo_relative(path, repo_root)
    return path.as_posix()


def compact_counter(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def edge_key(edge: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    return (edge.get("source"), edge.get("relation"), edge.get("target"))


def has_nonempty_value(item: dict[str, Any], keys: tuple[str, ...]) -> bool:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, (list, tuple, dict)) and value:
            return True
    return False


def decision_value(node: dict[str, Any]) -> str:
    value = node.get("decision") or node.get("status") or ""
    return str(value)


def is_audit_gap_decision(node: dict[str, Any]) -> bool:
    return decision_value(node) in AUDIT_GAP_DECISIONS


def is_dataset_queue_qualified_decision(node: dict[str, Any]) -> bool:
    value = decision_value(node)
    return any(marker in value for marker in DATASET_QUEUE_DECISION_MARKERS)


def is_source_review_decision(node: dict[str, Any]) -> bool:
    value = decision_value(node)
    return any(marker in value for marker in SOURCE_REVIEW_DECISION_MARKERS)


def numeric_confidence(edge: dict[str, Any]) -> float | None:
    value = edge.get("confidence")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def issue(
    severity: str,
    code: str,
    path: str,
    metric: str,
    observed: Any,
    threshold: Any,
    recommendation: str,
    samples: list[Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "severity": severity,
        "risk": severity,
        "code": code,
        "path": path,
        "metric": metric,
        "observed": observed,
        "threshold": threshold,
        "recommendation": recommendation,
    }
    if samples:
        payload["samples"] = samples
    return payload


def git_ls_files(repo_root: Path, patterns: list[str]) -> list[str]:
    cmd = ["git", "-C", str(repo_root), "ls-files", *patterns]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    return sorted(line for line in result.stdout.splitlines() if line.strip())


def git_untracked_relevant(repo_root: Path) -> list[str]:
    cmd = [
        "git",
        "-C",
        str(repo_root),
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "experiments/regression/catalogs",
        "experiments/regression/configs",
        "experiments/regression/reports",
        "experiments/regression/audits",
        "experiments/regression/graphs",
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    paths = []
    for line in result.stdout.splitlines():
        status = line[:2]
        value = line[3:].strip()
        if value.startswith("experiments/regression/reports/knowledge_graph_quality/"):
            continue
        if status == "??" and value:
            paths.append(value)
    return sorted(paths)


def git_modified_relevant(repo_root: Path) -> list[str]:
    cmd = [
        "git",
        "-C",
        str(repo_root),
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--",
        "experiments/regression/catalogs",
        "experiments/regression/configs",
        "experiments/regression/reports",
        "experiments/regression/audits",
        "experiments/regression/graphs",
        "experiments/regression/manuscript",
        "experiments/regression/scripts",
        "tests",
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    paths = []
    for line in result.stdout.splitlines():
        status = line[:2]
        value = line[3:].strip()
        if not value or status == "??":
            continue
        if value.startswith("experiments/regression/reports/knowledge_graph_quality/"):
            continue
        paths.append(value)
    return sorted(paths)


def inventory_tracked_sources(repo_root: Path) -> dict[str, list[str]]:
    catalog_paths = [
        "experiments/regression/catalogs/audit_index.json",
        "experiments/regression/catalogs/dataset_candidates.jsonl",
        "experiments/regression/catalogs/internet_dataset_inventory.jsonl",
        "experiments/regression/catalogs/internet_dataset_inventory.md",
        "experiments/regression/catalogs/knowledge_graph.json",
        "experiments/regression/catalogs/method_registry.json",
        "experiments/regression/catalogs/openml_feature_discovery.jsonl",
        "experiments/regression/catalogs/openml_ranked_candidates.jsonl",
        "experiments/regression/catalogs/openml_ranked_candidates.md",
        "experiments/regression/catalogs/openml_review_decisions.jsonl",
        "experiments/regression/catalogs/source_registry.md",
        "experiments/regression/catalogs/target_domain_provenance.json",
        "experiments/regression/catalogs/target_domain_provenance.md",
        "experiments/regression/PUBLICATION_READINESS_PROTOCOL.md",
        "experiments/regression/policies/data_policy_registry.md",
        "experiments/regression/diary/data_scientist_log.md",
        "experiments/regression/CHANGELOG.md",
        "experiments/regression/runs/run_registry.md",
        "experiments/regression/manuscript/README.md",
        "experiments/regression/manuscript/dataset_table.md",
        "experiments/regression/manuscript/method_table.md",
        "experiments/regression/manuscript/main_results_table.md",
        "experiments/regression/manuscript/robustness_results_table.md",
        "experiments/regression/manuscript/negative_results_table.md",
        "experiments/regression/manuscript/evidence_view.json",
        "experiments/regression/manuscript/evidence_view.md",
        "experiments/regression/manuscript/bounded_support_protocol.json",
        "experiments/regression/manuscript/bounded_support_protocol.md",
        "experiments/regression/manuscript/bounded_support_posthandling_validation.json",
        "experiments/regression/manuscript/bounded_support_posthandling_validation.md",
        "experiments/regression/manuscript/bounded_support_dataset_audit.json",
        "experiments/regression/manuscript/bounded_support_dataset_audit.md",
        "experiments/regression/manuscript/selection_multiplicity_protocol.json",
        "experiments/regression/manuscript/selection_multiplicity_protocol.md",
        "experiments/regression/manuscript/paper_readiness_map.json",
        "experiments/regression/manuscript/paper_readiness_map.md",
        "experiments/regression/manuscript/figure_index.md",
        "experiments/regression/manuscript/figures/README.md",
    ]
    catalog_paths = [
        path
        for path in catalog_paths
        if (repo_root / path).exists() and path in set(git_ls_files(repo_root, [path]))
    ]
    report_patterns = [
        "experiments/regression/reports/**/pilot_summary.json",
        "experiments/regression/reports/**/benchmark.json",
        "experiments/regression/reports/**/diagnostic.json",
    ]
    return {
        "configs": git_ls_files(repo_root, ["experiments/regression/configs/*.yaml"]),
        "reports": git_ls_files(repo_root, report_patterns),
        "audits": git_ls_files(
            repo_root, ["experiments/regression/audits/**/audit.md"]
        ),
        "graph_docs": git_ls_files(repo_root, ["experiments/regression/graphs/*.mmd"]),
        "catalogs": catalog_paths,
    }


def node_path_index(
    nodes: list[dict[str, Any]], repo_root: Path
) -> dict[str, list[str]]:
    by_path: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        for key in PATH_KEYS:
            path = normalize_rel_path(node.get(key), repo_root)
            if path:
                by_path[path].append(node.get("id", "<missing-id>"))
    return dict(by_path)


def connectivity_metrics(
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    degree: Counter[str] = Counter()
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source in nodes_by_id and target in nodes_by_id:
            adjacency[source].add(target)
            adjacency[target].add(source)
            degree[source] += 1
            degree[target] += 1

    isolated = sorted(node_id for node_id in nodes_by_id if degree[node_id] == 0)
    seen: set[str] = set()
    components: list[list[str]] = []
    for node_id in nodes_by_id:
        if node_id in seen:
            continue
        queue: deque[str] = deque([node_id])
        seen.add(node_id)
        component: list[str] = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))

    sizes = sorted((len(component) for component in components), reverse=True)
    node_count = len(nodes_by_id)
    largest = sizes[0] if sizes else 0
    return {
        "isolated_node_count": len(isolated),
        "isolated_node_ratio": len(isolated) / node_count if node_count else 0.0,
        "isolated_node_samples": isolated,
        "weak_component_count": len(components),
        "weak_component_sizes": sizes,
        "largest_component_size": largest,
        "largest_component_ratio": largest / node_count if node_count else 0.0,
    }


def ontology_metrics(
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    max_examples: int,
) -> dict[str, Any]:
    node_type_counts = Counter(str(node.get("type")) for node in nodes_by_id.values())
    relation_counts = Counter(str(edge.get("relation")) for edge in edges)
    unknown_node_types = sorted(set(node_type_counts) - ALLOWED_NODE_TYPES)
    unknown_relation_types = sorted(set(relation_counts) - ALLOWED_RELATIONS)

    violations: list[dict[str, Any]] = []
    for edge in edges:
        relation = edge.get("relation")
        rule = RELATION_RULES.get(str(relation))
        source = nodes_by_id.get(str(edge.get("source")))
        target = nodes_by_id.get(str(edge.get("target")))
        if not rule or not source or not target:
            continue
        allowed_sources, allowed_targets = rule
        source_type = str(source.get("type"))
        target_type = str(target.get("type"))
        if source_type not in allowed_sources or target_type not in allowed_targets:
            violations.append(
                {
                    "edge": edge_key(edge),
                    "source_type": source_type,
                    "target_type": target_type,
                    "allowed_source_types": sorted(allowed_sources),
                    "allowed_target_types": sorted(allowed_targets),
                }
            )

    critical_coverage = {}
    present_types = set(node_type_counts)
    for category, accepted_types in CRITICAL_CATEGORIES.items():
        matched_types = sorted(present_types & accepted_types)
        critical_coverage[category] = {
            "covered": bool(matched_types),
            "matched_types": matched_types,
            "node_count": sum(
                node_type_counts[node_type] for node_type in matched_types
            ),
        }

    return {
        "node_type_counts": compact_counter(node_type_counts),
        "relation_type_counts": compact_counter(relation_counts),
        "unknown_node_types": unknown_node_types,
        "unknown_relation_types": unknown_relation_types,
        "domain_range_violation_count": len(violations),
        "domain_range_violation_samples": violations[:max_examples],
        "critical_category_coverage": critical_coverage,
    }


def traceability_metrics(edges: list[dict[str, Any]]) -> dict[str, Any]:
    edge_count = len(edges)
    provenance_count = sum(
        has_nonempty_value(edge, EDGE_PROVENANCE_KEYS) for edge in edges
    )
    specific_provenance_count = sum(
        has_nonempty_value(edge, SPECIFIC_EDGE_PROVENANCE_KEYS) for edge in edges
    )
    selector_provenance_count = sum(
        has_nonempty_value(edge, EDGE_SELECTOR_PROVENANCE_KEYS) for edge in edges
    )
    confidence_reason_count = sum(
        bool(str(edge.get("confidence_reason", "")).strip()) for edge in edges
    )
    weak_provenance_confidence_one = [
        edge_key(edge)
        for edge in edges
        if not has_nonempty_value(edge, SPECIFIC_EDGE_PROVENANCE_KEYS)
        and numeric_confidence(edge) == 1.0
    ]
    confidence_values = [
        value
        for value in (numeric_confidence(edge) for edge in edges)
        if value is not None
    ]
    confidence_value_counts = Counter(round(value, 4) for value in confidence_values)
    provenance_granularity_counts = Counter(
        str(edge.get("provenance_granularity") or "unknown") for edge in edges
    )
    high_multiplicity_without_evidence_samples = [
        {
            "edge": edge_key(edge),
            "multiplicity": edge.get("multiplicity"),
        }
        for edge in edges
        if int(edge.get("multiplicity") or 0) > 1
        and not edge.get("multiplicity_evidence_samples")
    ]
    multiplicity_edges = [
        edge for edge in edges if int(edge.get("multiplicity") or 0) > 1
    ]
    return {
        "explicit_edge_provenance_count": provenance_count,
        "explicit_edge_provenance_coverage": (
            provenance_count / edge_count if edge_count else 0.0
        ),
        "specific_edge_provenance_count": specific_provenance_count,
        "specific_edge_provenance_coverage": (
            specific_provenance_count / edge_count if edge_count else 0.0
        ),
        "edge_selector_provenance_count": selector_provenance_count,
        "edge_selector_provenance_coverage": (
            selector_provenance_count / edge_count if edge_count else 0.0
        ),
        "edge_confidence_count": len(confidence_values),
        "edge_confidence_coverage": (
            len(confidence_values) / edge_count if edge_count else 0.0
        ),
        "edge_confidence_reason_count": confidence_reason_count,
        "edge_confidence_reason_coverage": (
            confidence_reason_count / edge_count if edge_count else 0.0
        ),
        "weak_provenance_confidence_one_count": len(weak_provenance_confidence_one),
        "weak_provenance_confidence_one_samples": weak_provenance_confidence_one[:25],
        "confidence_value_counts": {
            str(key): confidence_value_counts[key]
            for key in sorted(confidence_value_counts)
        },
        "distinct_edge_confidence_value_count": len(confidence_value_counts),
        "provenance_granularity_counts": compact_counter(provenance_granularity_counts),
        "multiplicity_edge_count": len(multiplicity_edges),
        "high_multiplicity_edges_without_evidence_samples_count": len(
            high_multiplicity_without_evidence_samples
        ),
        "high_multiplicity_edges_without_evidence_samples": (
            high_multiplicity_without_evidence_samples[:25]
        ),
        "average_edge_confidence": (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else None
        ),
    }


def claim_traceability_metrics(
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    max_examples: int,
) -> dict[str, Any]:
    claim_edges = []
    relation_rows = {}
    missing_selector_samples = []
    for edge in edges:
        relation = str(edge.get("relation") or "")
        source_type = str(
            nodes_by_id.get(str(edge.get("source")), {}).get("type") or ""
        )
        target_type = str(
            nodes_by_id.get(str(edge.get("target")), {}).get("type") or ""
        )
        is_claim_edge = (
            source_type in CLAIM_TRACEABILITY_NODE_TYPES
            or target_type in CLAIM_TRACEABILITY_NODE_TYPES
        )
        if not is_claim_edge or relation not in CLAIM_TRACEABILITY_RELATIONS:
            continue
        claim_edges.append(edge)
        has_selector = has_nonempty_value(edge, EDGE_SELECTOR_PROVENANCE_KEYS)
        row = relation_rows.setdefault(
            relation,
            {
                "edge_count": 0,
                "selector_provenance_count": 0,
                "missing_selector_count": 0,
                "missing_selector_samples": [],
            },
        )
        row["edge_count"] += 1
        if has_selector:
            row["selector_provenance_count"] += 1
        else:
            row["missing_selector_count"] += 1
            sample = {
                "source": edge.get("source"),
                "relation": relation,
                "target": edge.get("target"),
                "evidence_path": edge.get("evidence_path"),
                "provenance_granularity": edge.get("provenance_granularity"),
            }
            if len(row["missing_selector_samples"]) < max_examples:
                row["missing_selector_samples"].append(sample)
            if len(missing_selector_samples) < max_examples:
                missing_selector_samples.append(sample)

    selector_count = sum(
        has_nonempty_value(edge, EDGE_SELECTOR_PROVENANCE_KEYS) for edge in claim_edges
    )
    relation_coverage = {}
    for relation, row in relation_rows.items():
        edge_count = int(row["edge_count"])
        selector_provenance_count = int(row["selector_provenance_count"])
        relation_coverage[relation] = {
            **row,
            "selector_provenance_coverage": (
                selector_provenance_count / edge_count if edge_count else 0.0
            ),
        }

    claim_node_count = sum(
        1
        for node in nodes_by_id.values()
        if str(node.get("type") or "") == "manuscript_claim"
    )
    requirement_node_count = sum(
        1
        for node in nodes_by_id.values()
        if str(node.get("type") or "") == "claim_requirement"
    )
    edge_count = len(claim_edges)
    return {
        "claim_node_count": claim_node_count,
        "claim_requirement_node_count": requirement_node_count,
        "claim_edge_count": edge_count,
        "claim_edge_selector_provenance_count": selector_count,
        "claim_edge_missing_selector_count": edge_count - selector_count,
        "claim_edge_selector_provenance_coverage": (
            selector_count / edge_count if edge_count else 1.0
        ),
        "claim_edge_missing_selector_samples": missing_selector_samples,
        "claim_relation_selector_coverage": {
            relation: relation_coverage[relation]
            for relation in sorted(relation_coverage)
        },
    }


def paper_gate_traceability_metrics(
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    max_examples: int,
) -> dict[str, Any]:
    edge_index: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        edge_index[
            (
                str(edge.get("source") or ""),
                str(edge.get("relation") or ""),
                str(edge.get("target") or ""),
            )
        ].append(edge)

    gate_nodes = sorted(
        (
            node
            for node in nodes_by_id.values()
            if str(node.get("type") or "") == "paper_gate"
        ),
        key=lambda node: str(node.get("id") or ""),
    )
    rows = []
    missing_samples = []
    total_source_artifacts = 0
    resolved_source_artifacts = 0
    source_edges_with_exact_selector = 0
    requirement_edges_with_exact_selector = 0
    summary_edges_with_exact_selector = 0

    for node in gate_nodes:
        gate_id = str(node.get("gate_id") or "").strip()
        node_id = str(node.get("id") or "")
        requirement_id = (
            "claim_requirement:final_selection_and_fairness_claims_blocked:"
            f"{gate_id}"
        )
        if requirement_id not in nodes_by_id:
            requirement_id = (
                "claim_requirement:final_selection_and_fairness_claims_blocked:"
                f"{gate_id.lower().replace('-', '_')}"
            )
        requirement_edges = edge_index.get((requirement_id, "BLOCKED_BY", node_id), [])
        summary_edges = edge_index.get(
            ("report:manuscript_readiness_map", "SUMMARIZES_CONTROL", node_id),
            [],
        )
        requirement_exact = any(
            gate_id and gate_id in str(edge.get("evidence") or "")
            for edge in requirement_edges
        )
        summary_exact = any(
            gate_id and gate_id in str(edge.get("evidence") or "")
            for edge in summary_edges
        )
        if requirement_exact:
            requirement_edges_with_exact_selector += 1
        if summary_exact:
            summary_edges_with_exact_selector += 1

        source_artifacts = [
            str(value)
            for value in node.get("source_artifacts", []) or []
            if str(value).strip()
        ]
        source_artifact_rows = []
        for artifact_path in source_artifacts:
            total_source_artifacts += 1
            candidates = [
                edge
                for edge in edges
                if str(edge.get("source") or "") == node_id
                and str(edge.get("relation") or "") == "DERIVED_FROM"
                and str(edge.get("artifact_path") or "") == artifact_path
            ]
            has_candidate = bool(candidates)
            has_exact_selector = any(
                artifact_path in str(edge.get("evidence") or "")
                and gate_id in str(edge.get("evidence") or "")
                for edge in candidates
            )
            if has_candidate:
                resolved_source_artifacts += 1
            if has_exact_selector:
                source_edges_with_exact_selector += 1
            source_artifact_rows.append(
                {
                    "artifact_path": artifact_path,
                    "resolved_edge_count": len(candidates),
                    "has_exact_selector": has_exact_selector,
                }
            )
            if (not has_candidate or not has_exact_selector) and len(
                missing_samples
            ) < max_examples:
                missing_samples.append(
                    {
                        "paper_gate": node_id,
                        "gate_id": gate_id,
                        "artifact_path": artifact_path,
                        "resolved_edge_count": len(candidates),
                        "has_exact_selector": has_exact_selector,
                    }
                )

        fully_traceable = (
            bool(requirement_edges)
            and requirement_exact
            and bool(summary_edges)
            and summary_exact
            and bool(source_artifacts)
            and all(row["resolved_edge_count"] > 0 for row in source_artifact_rows)
            and all(row["has_exact_selector"] for row in source_artifact_rows)
        )
        if not fully_traceable and len(missing_samples) < max_examples:
            missing_samples.append(
                {
                    "paper_gate": node_id,
                    "gate_id": gate_id,
                    "requirement_id": requirement_id,
                    "requirement_edge_count": len(requirement_edges),
                    "requirement_exact_selector": requirement_exact,
                    "summary_edge_count": len(summary_edges),
                    "summary_exact_selector": summary_exact,
                    "source_artifact_count": len(source_artifacts),
                }
            )
        rows.append(
            {
                "paper_gate": node_id,
                "gate_id": gate_id,
                "status": node.get("status"),
                "requirement_id": requirement_id,
                "requirement_edge_count": len(requirement_edges),
                "requirement_exact_selector": requirement_exact,
                "summary_edge_count": len(summary_edges),
                "summary_exact_selector": summary_exact,
                "source_artifact_count": len(source_artifacts),
                "resolved_source_artifact_count": sum(
                    row["resolved_edge_count"] > 0 for row in source_artifact_rows
                ),
                "source_artifact_exact_selector_count": sum(
                    row["has_exact_selector"] for row in source_artifact_rows
                ),
                "fully_traceable": fully_traceable,
            }
        )

    gate_count = len(rows)
    fully_traceable_count = sum(row["fully_traceable"] for row in rows)
    missing_link_count = sum(
        max(0, 1 - int(row["requirement_edge_count"] > 0))
        + max(0, 1 - int(row["summary_edge_count"] > 0))
        + (row["source_artifact_count"] - row["resolved_source_artifact_count"])
        for row in rows
    )
    required_selector_count = gate_count * 2 + total_source_artifacts
    exact_selector_count = (
        requirement_edges_with_exact_selector
        + summary_edges_with_exact_selector
        + source_edges_with_exact_selector
    )
    return {
        "paper_gate_count": gate_count,
        "fully_traceable_gate_count": fully_traceable_count,
        "fully_traceable_gate_coverage": (
            fully_traceable_count / gate_count if gate_count else 1.0
        ),
        "requirement_gate_edge_count": sum(
            row["requirement_edge_count"] for row in rows
        ),
        "requirement_gate_exact_selector_count": requirement_edges_with_exact_selector,
        "summary_gate_edge_count": sum(row["summary_edge_count"] for row in rows),
        "summary_gate_exact_selector_count": summary_edges_with_exact_selector,
        "source_artifact_count": total_source_artifacts,
        "resolved_source_artifact_count": resolved_source_artifacts,
        "source_artifact_resolution_coverage": (
            resolved_source_artifacts / total_source_artifacts
            if total_source_artifacts
            else 1.0
        ),
        "source_artifact_exact_selector_count": source_edges_with_exact_selector,
        "source_artifact_exact_selector_coverage": (
            source_edges_with_exact_selector / total_source_artifacts
            if total_source_artifacts
            else 1.0
        ),
        "required_selector_count": required_selector_count,
        "exact_selector_count": exact_selector_count,
        "exact_selector_coverage": (
            exact_selector_count / required_selector_count
            if required_selector_count
            else 1.0
        ),
        "missing_traceability_link_count": missing_link_count,
        "missing_traceability_samples": missing_samples[:max_examples],
        "rows": rows[:max_examples],
    }


def summary_metrics(nodes: list[dict[str, Any]], max_examples: int) -> dict[str, Any]:
    node_count = len(nodes)
    direct_count = sum(bool(str(node.get("summary", "")).strip()) for node in nodes)
    semantic_count = sum(has_nonempty_value(node, SUMMARY_KEYS) for node in nodes)
    short_direct = [
        node["id"]
        for node in nodes
        if str(node.get("summary", "")).strip()
        and len(str(node.get("summary", "")).strip()) < 24
    ]
    missing_direct = [
        node["id"] for node in nodes if not str(node.get("summary", "")).strip()
    ]
    by_type: dict[str, dict[str, float | int]] = {}
    for node_type in sorted({str(node.get("type")) for node in nodes}):
        type_nodes = [node for node in nodes if str(node.get("type")) == node_type]
        count = len(type_nodes)
        with_summary = sum(
            bool(str(node.get("summary", "")).strip()) for node in type_nodes
        )
        with_semantic = sum(
            has_nonempty_value(node, SUMMARY_KEYS) for node in type_nodes
        )
        by_type[node_type] = {
            "node_count": count,
            "direct_summary_count": with_summary,
            "direct_summary_coverage": with_summary / count if count else 0.0,
            "semantic_summary_count": with_semantic,
            "semantic_summary_coverage": with_semantic / count if count else 0.0,
        }
    return {
        "direct_summary_count": direct_count,
        "direct_summary_coverage": direct_count / node_count if node_count else 0.0,
        "semantic_summary_count": semantic_count,
        "semantic_summary_coverage": semantic_count / node_count if node_count else 0.0,
        "short_direct_summary_count": len(short_direct),
        "short_direct_summary_samples": short_direct[:max_examples],
        "missing_direct_summary_count": len(missing_direct),
        "missing_direct_summary_samples": missing_direct[:max_examples],
        "summary_coverage_by_type": by_type,
    }


def observation_metrics(
    graph: dict[str, Any], nodes: list[dict[str, Any]]
) -> dict[str, Any]:
    observations = graph.get("observations", [])
    total = len(observations) if isinstance(observations, list) else 0
    topology_count = 0
    paper_evidence_count = total
    for node in nodes:
        node_observations = node.get("observations")
        if isinstance(node_observations, list):
            total += len(node_observations)
            for observation in node_observations:
                if str(observation).startswith(TOPOLOGY_OBSERVATION_PREFIX):
                    topology_count += 1
                else:
                    paper_evidence_count += 1
        elif isinstance(node.get("observation_count"), int):
            count = int(node["observation_count"])
            total += count
            paper_evidence_count += count
    node_count = len(nodes)
    return {
        "total_observation_count": total,
        "observation_node_ratio": total / node_count if node_count else 0.0,
        "topology_observation_count": topology_count,
        "paper_evidence_observation_count": paper_evidence_count,
        "paper_evidence_observation_node_ratio": (
            paper_evidence_count / node_count if node_count else 0.0
        ),
    }


def referential_integrity_metrics(
    nodes: list[dict[str, Any]],
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    repo_root: Path,
    max_examples: int,
) -> dict[str, Any]:
    node_ids = [str(node.get("id")) for node in nodes]
    duplicate_node_ids = sorted(
        node_id for node_id, count in Counter(node_ids).items() if count > 1
    )

    missing_endpoint_edges = []
    for edge in edges:
        missing = []
        if edge.get("source") not in nodes_by_id:
            missing.append({"endpoint": "source", "id": edge.get("source")})
        if edge.get("target") not in nodes_by_id:
            missing.append({"endpoint": "target", "id": edge.get("target")})
        if missing:
            missing_endpoint_edges.append({"edge": edge, "missing": missing})

    duplicate_edge_triples = [
        {"edge": key, "count": count}
        for key, count in Counter(edge_key(edge) for edge in edges).items()
        if count > 1
    ]
    duplicate_edge_triples.sort(key=lambda item: (-item["count"], str(item["edge"])))

    stale_paths = []
    for node in nodes:
        for key in PATH_KEYS:
            path = normalize_rel_path(node.get(key), repo_root)
            if path and not (repo_root / path).exists():
                stale_paths.append({"node": node.get("id"), "key": key, "path": path})

    return {
        "duplicate_node_id_count": len(duplicate_node_ids),
        "duplicate_node_id_samples": duplicate_node_ids[:max_examples],
        "missing_endpoint_edge_count": len(missing_endpoint_edges),
        "missing_endpoint_edge_samples": missing_endpoint_edges[:max_examples],
        "duplicate_edge_triple_count": len(duplicate_edge_triples),
        "duplicate_edge_triple_samples": duplicate_edge_triples[:max_examples],
        "stale_node_path_count": len(stale_paths),
        "stale_node_path_samples": stale_paths[:max_examples],
    }


def source_freshness_metrics(
    nodes: list[dict[str, Any]],
    repo_root: Path,
    max_examples: int,
) -> dict[str, Any]:
    tracked = inventory_tracked_sources(repo_root)
    represented = set(node_path_index(nodes, repo_root))
    missing = {
        category: sorted(path for path in paths if path not in represented)
        for category, paths in tracked.items()
    }
    covered = {
        category: sorted(path for path in paths if path in represented)
        for category, paths in tracked.items()
    }
    coverage = {}
    for category, paths in tracked.items():
        count = len(paths)
        coverage[category] = {
            "tracked_count": count,
            "covered_count": len(covered[category]),
            "missing_count": len(missing[category]),
            "coverage": len(covered[category]) / count if count else 1.0,
            "missing_samples": missing[category][:max_examples],
        }
    untracked = git_untracked_relevant(repo_root)
    modified = git_modified_relevant(repo_root)
    return {
        "tracked_source_coverage": coverage,
        "working_tree_relevant_untracked_count": len(untracked),
        "working_tree_relevant_untracked_samples": untracked[:max_examples],
        "working_tree_relevant_modified_count": len(modified),
        "working_tree_relevant_modified_samples": modified[:max_examples],
    }


def linkage_ratio(
    node_ids: set[str],
    relation_index: dict[tuple[str, str], set[str]],
    direction: str,
    relation: str,
) -> float:
    if not node_ids:
        return 1.0
    covered = 0
    for node_id in node_ids:
        if direction == "out":
            has_relation = bool(relation_index.get((node_id, relation), set()))
        else:
            has_relation = any(
                node_id in targets
                for (source, rel), targets in relation_index.items()
                if rel == relation and source != node_id
            )
        covered += int(has_relation)
    return covered / len(node_ids)


def critical_linkage_metrics(
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    max_examples: int,
) -> dict[str, Any]:
    outgoing: dict[tuple[str, str], set[str]] = defaultdict(set)
    incoming: dict[tuple[str, str], set[str]] = defaultdict(set)
    for edge in edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        relation = str(edge.get("relation"))
        if source in nodes_by_id and target in nodes_by_id:
            outgoing[(source, relation)].add(target)
            incoming[(target, relation)].add(source)

    by_type: dict[str, set[str]] = defaultdict(set)
    for node_id, node in nodes_by_id.items():
        by_type[str(node.get("type"))].add(node_id)

    datasets = by_type["dataset"]
    configs = by_type["config"]
    report_sidecars = {
        node_id
        for node_id in by_type["report"]
        if outgoing.get((node_id, "SUPPORTS_REPORT"))
        and node_id not in STANDALONE_METHODOLOGY_REPORTS
    }
    non_experiment_reports = {
        node_id
        for node_id in by_type["report"]
        if node_id.startswith("report:methodology_sanity_audit_")
    } | STANDALONE_METHODOLOGY_REPORTS
    source_review_reports = {
        node_id
        for node_id in by_type["report"]
        if str(nodes_by_id[node_id].get("report_status") or "").startswith(
            "source_review_report"
        )
    }
    non_experiment_reports |= source_review_reports
    primary_reports = by_type["report"] - report_sidecars - non_experiment_reports
    partial_reports = {
        node_id
        for node_id in primary_reports
        if nodes_by_id[node_id].get("report_status") == "partial_run"
    }
    method_reports = by_type["method_report"]
    reports_requiring_method_results = (
        primary_reports - partial_reports
    ) | method_reports
    methods = by_type["method"]
    decisions = by_type["decision"] | by_type["openml_review_decision"]
    audit_gap_decisions = {
        node_id for node_id in decisions if is_audit_gap_decision(nodes_by_id[node_id])
    }
    audit_gap_datasets = {
        target
        for node_id in audit_gap_decisions
        for target in outgoing.get((node_id, "DECIDES_DATASET"), set())
        if target in datasets
    }
    queue_qualified_decisions = {
        node_id
        for node_id in decisions
        if is_dataset_queue_qualified_decision(nodes_by_id[node_id])
    }
    queue_qualified_datasets = {
        target
        for node_id in queue_qualified_decisions
        for target in outgoing.get((node_id, "DECIDES_DATASET"), set())
        if target in datasets
    }
    source_review_decisions = {
        node_id
        for node_id in decisions
        if outgoing.get((node_id, "REVIEWS_SOURCE"))
        and is_source_review_decision(nodes_by_id[node_id])
    }

    dataset_with_audit = {
        node_id for node_id in datasets if outgoing.get((node_id, "HAS_AUDIT"))
    } | audit_gap_datasets
    dataset_with_source = {
        node_id for node_id in datasets if outgoing.get((node_id, "FROM_SOURCE"))
    }
    dataset_governed = {
        node_id for node_id in datasets if outgoing.get((node_id, "GOVERNED_BY"))
    }
    source_review_only_datasets = {
        node_id
        for node_id in datasets
        if nodes_by_id[node_id].get("status") == "source_review_only_modeling_blocked"
    }
    dataset_with_config_or_report = {
        node_id
        for node_id in datasets
        if incoming.get((node_id, "QUEUES_DATASET"))
        or incoming.get((node_id, "SUMMARIZES_DATASET"))
        or node_id in queue_qualified_datasets
    } | source_review_only_datasets
    configs_with_dataset = {
        node_id for node_id in configs if outgoing.get((node_id, "QUEUES_DATASET"))
    }
    configs_with_method = {
        node_id
        for node_id in configs
        if any(outgoing.get((node_id, relation)) for relation in METHOD_EDGE_RELATIONS)
        or outgoing.get((node_id, "QUEUES_METHOD_CONFIG"))
    }
    reports_with_dataset = {
        node_id
        for node_id in primary_reports
        if outgoing.get((node_id, "SUMMARIZES_DATASET"))
    }
    reports_with_method = {
        node_id
        for node_id in reports_requiring_method_results
        if outgoing.get((node_id, "EVALUATES_METHOD"))
        or outgoing.get((node_id, "EVALUATES_METHOD_CONFIG"))
    }
    report_sidecars_supporting_primary = {
        node_id
        for node_id in report_sidecars
        if any(
            target in primary_reports
            for target in outgoing.get((node_id, "SUPPORTS_REPORT"), set())
        )
    }
    methods_with_spec = {
        node_id for node_id in methods if outgoing.get((node_id, "SPECIFIED_BY"))
    }
    decisions_with_dataset = {
        node_id for node_id in decisions if outgoing.get((node_id, "DECIDES_DATASET"))
    } | source_review_decisions

    def coverage(numerator: set[str], denominator: set[str]) -> dict[str, Any]:
        missing = sorted(denominator - numerator)
        return {
            "covered_count": len(numerator),
            "total_count": len(denominator),
            "coverage": len(numerator) / len(denominator) if denominator else 1.0,
            "missing_samples": missing[:max_examples],
        }

    return {
        "datasets_with_audit": coverage(dataset_with_audit, datasets),
        "datasets_with_source": coverage(dataset_with_source, datasets),
        "datasets_governed_by_policy": coverage(dataset_governed, datasets),
        "datasets_queued_or_reported": coverage(
            dataset_with_config_or_report, datasets
        ),
        "datasets_with_audit_qualified_gap_count": len(audit_gap_datasets),
        "datasets_queued_or_reported_qualified_decision_count": len(
            queue_qualified_datasets
        ),
        "datasets_queued_or_reported_source_review_only_count": len(
            source_review_only_datasets
        ),
        "decisions_with_source_review_only_count": len(source_review_decisions),
        "configs_queue_dataset": coverage(configs_with_dataset, configs),
        "configs_queue_method": coverage(configs_with_method, configs),
        "primary_report_count": len(primary_reports),
        "partial_report_count": len(partial_reports),
        "report_sidecar_count": len(report_sidecars),
        "method_report_count": len(method_reports),
        "reports_summarize_dataset": coverage(reports_with_dataset, primary_reports),
        "reports_evaluate_method": coverage(
            reports_with_method,
            reports_requiring_method_results,
        ),
        "report_sidecars_support_primary": coverage(
            report_sidecars_supporting_primary,
            report_sidecars,
        ),
        "methods_specified": coverage(methods_with_spec, methods),
        "decisions_link_dataset": coverage(decisions_with_dataset, decisions),
    }


def endpoint_linkage_metrics(
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    max_examples: int,
) -> dict[str, Any]:
    outgoing: dict[tuple[str, str], set[str]] = defaultdict(set)
    for edge in edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        relation = str(edge.get("relation"))
        if source in nodes_by_id and target in nodes_by_id:
            outgoing[(source, relation)].add(target)

    endpoint_results = {
        node_id
        for node_id, node in nodes_by_id.items()
        if node.get("type") == "endpoint_result"
    }
    endpoint_caveats = {
        node_id
        for node_id, node in nodes_by_id.items()
        if node.get("type") == "endpoint_caveat"
    }
    endpoint_states = {
        node_id
        for node_id, node in nodes_by_id.items()
        if node.get("type") == "endpoint_state"
    }

    def coverage(node_ids: set[str], relation: str) -> dict[str, Any]:
        covered = {
            node_id for node_id in node_ids if outgoing.get((node_id, relation), set())
        }
        missing = sorted(node_ids - covered)
        return {
            "covered_count": len(covered),
            "total_count": len(node_ids),
            "coverage": len(covered) / len(node_ids) if node_ids else 1.0,
            "missing_samples": missing[:max_examples],
        }

    result_relation_coverage = {
        relation: coverage(endpoint_results, relation)
        for relation in (
            *ENDPOINT_RESULT_REQUIRED_RELATIONS,
            *ENDPOINT_RESULT_CONTEXT_RELATIONS,
        )
    }
    caveat_relation_coverage = {
        relation: coverage(endpoint_caveats, relation)
        for relation in ENDPOINT_CAVEAT_REQUIRED_RELATIONS
    }
    state_relation_coverage = {
        relation: coverage(endpoint_states, relation)
        for relation in ENDPOINT_STATE_REQUIRED_RELATIONS
    }
    result_state_targets = {
        node_id: outgoing.get((node_id, "HAS_ENDPOINT_STATE"), set())
        for node_id in endpoint_results
    }
    uncaveated = sorted(
        node_id
        for node_id in endpoint_results
        if not outgoing.get((node_id, "HAS_CAVEAT"), set())
    )
    missing_state = sorted(
        node_id for node_id, targets in result_state_targets.items() if not targets
    )
    explicit_clean_no_caveat = sorted(
        node_id
        for node_id in uncaveated
        if any(
            nodes_by_id.get(state_id, {}).get("has_caveat") is False
            for state_id in result_state_targets.get(node_id, set())
        )
    )
    uncaveated_without_state = sorted(set(uncaveated) - set(explicit_clean_no_caveat))
    zero_interval_results = sorted(
        node_id
        for node_id in endpoint_results
        if (nodes_by_id[node_id].get("intervals") or 0) <= 0
    )
    clean_zero_interval_results = sorted(
        node_id
        for node_id in zero_interval_results
        if nodes_by_id[node_id].get("support_status")
        == "clean_endpoint_support_diagnostic"
    )
    schema_incomplete_results = sorted(
        node_id
        for node_id in endpoint_results
        if nodes_by_id[node_id].get("support_status")
        == "schema_incomplete_endpoint_diagnostic"
    )
    return {
        "endpoint_result_count": len(endpoint_results),
        "endpoint_caveat_count": len(endpoint_caveats),
        "endpoint_state_count": len(endpoint_states),
        "endpoint_result_relation_coverage": result_relation_coverage,
        "endpoint_caveat_relation_coverage": caveat_relation_coverage,
        "endpoint_state_relation_coverage": state_relation_coverage,
        "uncaveated_endpoint_result_count": len(uncaveated),
        "uncaveated_endpoint_result_samples": uncaveated[:max_examples],
        "explicit_clean_no_caveat_endpoint_result_count": len(explicit_clean_no_caveat),
        "explicit_clean_no_caveat_endpoint_result_samples": explicit_clean_no_caveat[
            :max_examples
        ],
        "missing_endpoint_state_count": len(missing_state),
        "missing_endpoint_state_samples": missing_state[:max_examples],
        "uncaveated_without_state_count": len(uncaveated_without_state),
        "uncaveated_without_state_samples": uncaveated_without_state[:max_examples],
        "zero_interval_endpoint_result_count": len(zero_interval_results),
        "zero_interval_endpoint_result_samples": zero_interval_results[:max_examples],
        "clean_zero_interval_endpoint_result_count": len(clean_zero_interval_results),
        "clean_zero_interval_endpoint_result_samples": clean_zero_interval_results[
            :max_examples
        ],
        "schema_incomplete_endpoint_result_count": len(schema_incomplete_results),
        "schema_incomplete_endpoint_result_samples": schema_incomplete_results[
            :max_examples
        ],
    }


def method_evidence_metrics(
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    max_examples: int,
) -> dict[str, Any]:
    incoming: dict[tuple[str, str], set[str]] = defaultdict(set)
    outgoing: dict[tuple[str, str], set[str]] = defaultdict(set)
    for edge in edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        relation = str(edge.get("relation"))
        if source in nodes_by_id and target in nodes_by_id:
            incoming[(target, relation)].add(source)
            outgoing[(source, relation)].add(target)

    methods: dict[str, Any] = {}
    for method_id in GROUPED_CV_CONTROL_METHOD_IDS:
        node = nodes_by_id.get(method_id)
        registered_in = sorted(outgoing.get((method_id, "REGISTERED_IN"), set()))
        specified_by = sorted(outgoing.get((method_id, "SPECIFIED_BY"), set()))
        queued_by = sorted(incoming.get((method_id, "QUEUES_METHOD"), set()))
        evaluated_by = sorted(incoming.get((method_id, "EVALUATES_METHOD"), set()))
        concerned_by = sorted(incoming.get((method_id, "CONCERNS_METHOD"), set()))
        supported_by = sorted(incoming.get((method_id, "SUPPORTED_BY"), set()))

        if node is None:
            evidence_status = "missing_method_node"
        elif evaluated_by:
            evidence_status = "empirical_evidence_present"
        elif queued_by:
            evidence_status = "queued_pending_report_evidence"
        else:
            evidence_status = "registered_pending_config_and_report_evidence"

        methods[method_id] = {
            "present": node is not None,
            "status": node.get("status") if node else None,
            "summary": node.get("summary") if node else None,
            "registered_in_count": len(registered_in),
            "registered_in_samples": registered_in[:max_examples],
            "specified_by_count": len(specified_by),
            "specified_by_samples": specified_by[:max_examples],
            "queued_config_count": len(queued_by),
            "queued_config_samples": queued_by[:max_examples],
            "evaluating_report_count": len(evaluated_by),
            "evaluating_report_samples": evaluated_by[:max_examples],
            "claim_or_requirement_count": len(concerned_by) + len(supported_by),
            "claim_or_requirement_samples": (concerned_by + supported_by)[
                :max_examples
            ],
            "evidence_status": evidence_status,
        }

    present_count = sum(1 for row in methods.values() if row["present"])
    registered_count = sum(
        1 for row in methods.values() if row["registered_in_count"] > 0
    )
    specified_count = sum(
        1 for row in methods.values() if row["specified_by_count"] > 0
    )
    queued_count = sum(1 for row in methods.values() if row["queued_config_count"] > 0)
    evaluated_count = sum(
        1 for row in methods.values() if row["evaluating_report_count"] > 0
    )
    pending_empirical = sorted(
        method_id
        for method_id, row in methods.items()
        if row["evidence_status"]
        in {
            "queued_pending_report_evidence",
            "registered_pending_config_and_report_evidence",
        }
    )

    return {
        "grouped_cv_duplicate_cluster_controls": {
            "monitor_id": "grouped_cv_duplicate_cluster_controls",
            "purpose": (
                "Track whether split-group-preserving CV+/CV-minmax controls "
                "are merely registered, queued in duplicate-cluster configs, "
                "or backed by completed report/endpoint evidence."
            ),
            "tracked_method_ids": list(GROUPED_CV_CONTROL_METHOD_IDS),
            "tracked_method_count": len(GROUPED_CV_CONTROL_METHOD_IDS),
            "present_count": present_count,
            "registered_count": registered_count,
            "specified_count": specified_count,
            "queued_method_count": queued_count,
            "evaluated_method_count": evaluated_count,
            "pending_empirical_method_count": len(pending_empirical),
            "pending_empirical_method_ids": pending_empirical[:max_examples],
            "methods": methods,
            "claim_boundary": (
                "Registered grouped-CV methods do not close historical "
                "duplicate-cluster plus-family caveats until they are queued, "
                "run, endpoint-audited, and linked to the relevant reports."
            ),
        }
    }


def build_issues(
    graph_path: Path,
    metrics: dict[str, Any],
    max_examples: int,
) -> list[dict[str, Any]]:
    graph_rel = metrics["metadata"]["graph_path"]
    issues: list[dict[str, Any]] = []

    graph_metrics = metrics["graph"]
    if graph_metrics["edge_node_ratio"] < THRESHOLDS["min_edge_node_ratio"]:
        issues.append(
            issue(
                "medium",
                "LOW_EDGE_NODE_RATIO",
                graph_rel,
                "edge_node_ratio",
                round(graph_metrics["edge_node_ratio"], 4),
                f">= {THRESHOLDS['min_edge_node_ratio']}",
                "Add explicit links among config, dataset, report, audit, policy, method, metric, and decision nodes.",
            )
        )
    if graph_metrics["isolated_node_ratio"] > THRESHOLDS["max_isolated_node_ratio"]:
        issues.append(
            issue(
                "medium",
                "ISOLATED_NODES",
                graph_rel,
                "isolated_node_ratio",
                round(graph_metrics["isolated_node_ratio"], 4),
                f"<= {THRESHOLDS['max_isolated_node_ratio']}",
                "Connect graph/method/audit nodes to the source document, governing policy, or evidence node that justifies their presence.",
                graph_metrics["isolated_node_samples"][:max_examples],
            )
        )
    if graph_metrics["weak_component_count"] > THRESHOLDS["max_weak_component_count"]:
        issues.append(
            issue(
                "medium",
                "FRAGMENTED_GRAPH",
                graph_rel,
                "weak_component_count",
                graph_metrics["weak_component_count"],
                f"<= {THRESHOLDS['max_weak_component_count']}",
                "Attach isolated documentation and orphan evidence nodes to the main regression KG component.",
            )
        )
    if (
        graph_metrics["largest_component_ratio"]
        < THRESHOLDS["min_largest_component_ratio"]
    ):
        issues.append(
            issue(
                "high",
                "LOW_MAIN_COMPONENT_COVERAGE",
                graph_rel,
                "largest_component_ratio",
                round(graph_metrics["largest_component_ratio"], 4),
                f">= {THRESHOLDS['min_largest_component_ratio']}",
                "Promote disconnected evidence into the main component or remove stale nodes.",
            )
        )

    integrity = metrics["referential_integrity"]
    if (
        integrity["missing_endpoint_edge_count"]
        > THRESHOLDS["max_missing_endpoint_edges"]
    ):
        issues.append(
            issue(
                "critical",
                "MISSING_EDGE_ENDPOINTS",
                graph_rel,
                "missing_endpoint_edge_count",
                integrity["missing_endpoint_edge_count"],
                THRESHOLDS["max_missing_endpoint_edges"],
                "Every edge endpoint must resolve to a node; add missing dataset/method nodes or normalize IDs in the KG builder.",
                integrity["missing_endpoint_edge_samples"][:max_examples],
            )
        )
    if (
        integrity["duplicate_edge_triple_count"]
        > THRESHOLDS["max_duplicate_edge_triples"]
    ):
        issues.append(
            issue(
                "medium",
                "DUPLICATE_EDGE_TRIPLES",
                graph_rel,
                "duplicate_edge_triple_count",
                integrity["duplicate_edge_triple_count"],
                THRESHOLDS["max_duplicate_edge_triples"],
                "Deduplicate repeated report-method triples or attach run-level evidence nodes if multiplicity is intentional.",
                integrity["duplicate_edge_triple_samples"][:max_examples],
            )
        )
    if integrity["stale_node_path_count"] > THRESHOLDS["max_stale_node_paths"]:
        issues.append(
            issue(
                "critical",
                "STALE_NODE_PATHS",
                graph_rel,
                "stale_node_path_count",
                integrity["stale_node_path_count"],
                THRESHOLDS["max_stale_node_paths"],
                "Remove stale nodes or update their path/json_path/audit_path fields to existing source artifacts.",
                integrity["stale_node_path_samples"][:max_examples],
            )
        )

    trace = metrics["traceability"]
    if (
        trace["explicit_edge_provenance_coverage"]
        < THRESHOLDS["min_edge_provenance_coverage"]
    ):
        issues.append(
            issue(
                "critical",
                "LOW_EDGE_PROVENANCE_COVERAGE",
                graph_rel,
                "explicit_edge_provenance_coverage",
                round(trace["explicit_edge_provenance_coverage"], 4),
                f">= {THRESHOLDS['min_edge_provenance_coverage']}",
                "Add per-edge provenance_id or evidence_path pointing to the config/report/audit/catalog/ledger/doc that supports each relation.",
            )
        )
    if (
        trace["specific_edge_provenance_coverage"]
        < THRESHOLDS["min_specific_edge_provenance_coverage"]
    ):
        issues.append(
            issue(
                "medium",
                "LOW_SPECIFIC_EDGE_PROVENANCE_COVERAGE",
                graph_rel,
                "specific_edge_provenance_coverage",
                round(trace["specific_edge_provenance_coverage"], 4),
                f">= {THRESHOLDS['min_specific_edge_provenance_coverage']}",
                "Carry evidence_path/source_path/sources on edges so provenance resolves to the artifact that supports the relation, not only the KG builder.",
            )
        )
    if (
        trace["edge_selector_provenance_coverage"]
        < THRESHOLDS["min_edge_selector_provenance_coverage"]
    ):
        issues.append(
            issue(
                "medium",
                "LOW_EDGE_SELECTOR_PROVENANCE_COVERAGE",
                graph_rel,
                "edge_selector_provenance_coverage",
                round(trace["edge_selector_provenance_coverage"], 4),
                f">= {THRESHOLDS['min_edge_selector_provenance_coverage']}",
                "Add fact-level evidence selectors for high-volume report/config/audit edges so a paper writer can locate the exact row or field supporting the relation.",
            )
        )
    claim_traceability = metrics.get("claim_traceability") or {}
    if (
        float(claim_traceability.get("claim_edge_selector_provenance_coverage") or 0.0)
        < THRESHOLDS["min_claim_edge_selector_provenance_coverage"]
    ):
        issues.append(
            issue(
                "medium",
                "LOW_CLAIM_EDGE_SELECTOR_PROVENANCE_COVERAGE",
                graph_rel,
                "claim_edge_selector_provenance_coverage",
                round(
                    float(
                        claim_traceability.get(
                            "claim_edge_selector_provenance_coverage"
                        )
                        or 0.0
                    ),
                    4,
                ),
                f">= {THRESHOLDS['min_claim_edge_selector_provenance_coverage']}",
                "Add fact-level selectors for manuscript claim and claim-requirement support/blocker edges so paper claims can be traced to exact claim-register fields or audit summaries.",
                claim_traceability.get("claim_edge_missing_selector_samples", [])[
                    :max_examples
                ],
            )
        )
    paper_gate_traceability = metrics.get("paper_gate_traceability") or {}
    if (
        int(paper_gate_traceability.get("missing_traceability_link_count") or 0)
        > THRESHOLDS["max_missing_paper_gate_traceability_links"]
    ):
        issues.append(
            issue(
                "medium",
                "MISSING_PAPER_GATE_TRACEABILITY_LINKS",
                graph_rel,
                "paper_gate_traceability.missing_traceability_link_count",
                paper_gate_traceability.get("missing_traceability_link_count"),
                THRESHOLDS["max_missing_paper_gate_traceability_links"],
                "Each blocked paper gate must trace from the final claim requirement to a paper_gate node and from that gate to every declared source artifact.",
                paper_gate_traceability.get("missing_traceability_samples", [])[
                    :max_examples
                ],
            )
        )
    if (
        float(paper_gate_traceability.get("fully_traceable_gate_coverage") or 0.0)
        < THRESHOLDS["min_paper_gate_traceability_coverage"]
    ):
        issues.append(
            issue(
                "medium",
                "LOW_PAPER_GATE_TRACEABILITY_COVERAGE",
                graph_rel,
                "paper_gate_traceability.fully_traceable_gate_coverage",
                round(
                    float(
                        paper_gate_traceability.get("fully_traceable_gate_coverage")
                        or 0.0
                    ),
                    4,
                ),
                f">= {THRESHOLDS['min_paper_gate_traceability_coverage']}",
                "Blocked final-claim gates need a complete requirement -> paper_gate -> source artifact chain before manuscript extraction.",
                paper_gate_traceability.get("missing_traceability_samples", [])[
                    :max_examples
                ],
            )
        )
    if (
        float(paper_gate_traceability.get("exact_selector_coverage") or 0.0)
        < THRESHOLDS["min_paper_gate_source_selector_coverage"]
    ):
        issues.append(
            issue(
                "medium",
                "LOW_PAPER_GATE_SOURCE_SELECTOR_COVERAGE",
                graph_rel,
                "paper_gate_traceability.exact_selector_coverage",
                round(
                    float(
                        paper_gate_traceability.get("exact_selector_coverage") or 0.0
                    ),
                    4,
                ),
                f">= {THRESHOLDS['min_paper_gate_source_selector_coverage']}",
                "Paper-gate edges must point to exact blocked-gate and source_artifacts selectors, not only the paper-readiness artifact root.",
                paper_gate_traceability.get("missing_traceability_samples", [])[
                    :max_examples
                ],
            )
        )
    if trace["edge_confidence_coverage"] < THRESHOLDS["min_edge_confidence_coverage"]:
        issues.append(
            issue(
                "high",
                "LOW_EDGE_CONFIDENCE_COVERAGE",
                graph_rel,
                "edge_confidence_coverage",
                round(trace["edge_confidence_coverage"], 4),
                f">= {THRESHOLDS['min_edge_confidence_coverage']}",
                "Emit confidence for all generated edges; use 1.0 for direct parsed facts and lower scores for inferred links.",
            )
        )
    if (
        trace["edge_confidence_reason_coverage"]
        < THRESHOLDS["min_confidence_reason_coverage"]
    ):
        issues.append(
            issue(
                "medium",
                "LOW_EDGE_CONFIDENCE_REASON_COVERAGE",
                graph_rel,
                "edge_confidence_reason_coverage",
                round(trace["edge_confidence_reason_coverage"], 4),
                f">= {THRESHOLDS['min_confidence_reason_coverage']}",
                "Add confidence_reason to each edge so calibrated confidence can be audited during manuscript extraction.",
            )
        )
    if (
        trace["weak_provenance_confidence_one_count"]
        > THRESHOLDS["max_weak_provenance_confidence_one_edges"]
    ):
        issues.append(
            issue(
                "medium",
                "WEAK_PROVENANCE_WITH_MAX_CONFIDENCE",
                graph_rel,
                "weak_provenance_confidence_one_count",
                trace["weak_provenance_confidence_one_count"],
                THRESHOLDS["max_weak_provenance_confidence_one_edges"],
                "Edges without artifact-level provenance must not retain confidence 1.0; attach evidence_path or lower and explain confidence.",
                trace["weak_provenance_confidence_one_samples"][:max_examples],
            )
        )
    average_confidence = trace["average_edge_confidence"]
    if (
        average_confidence is None
        or average_confidence < THRESHOLDS["min_average_edge_confidence"]
    ):
        issues.append(
            issue(
                "high",
                "LOW_AVERAGE_EDGE_CONFIDENCE",
                graph_rel,
                "average_edge_confidence",
                average_confidence,
                f">= {THRESHOLDS['min_average_edge_confidence']}",
                "Once confidence is emitted, keep the mean confidence above the audit threshold or split uncertain edges into review queues.",
            )
        )
    if (
        trace["distinct_edge_confidence_value_count"]
        < THRESHOLDS["min_distinct_edge_confidence_values"]
    ):
        issues.append(
            issue(
                "medium",
                "UNCALIBRATED_EDGE_CONFIDENCE_DISTRIBUTION",
                graph_rel,
                "distinct_edge_confidence_value_count",
                trace["distinct_edge_confidence_value_count"],
                f">= {THRESHOLDS['min_distinct_edge_confidence_values']}",
                "Confidence must separate fact-level, path-level, inferred, and builder-only relations instead of using a single completeness value.",
                trace["confidence_value_counts"],
            )
        )
    if (
        trace["high_multiplicity_edges_without_evidence_samples_count"]
        > THRESHOLDS["max_high_multiplicity_edges_without_evidence_samples"]
    ):
        issues.append(
            issue(
                "medium",
                "MULTIPLICITY_WITHOUT_EVIDENCE_SAMPLES",
                graph_rel,
                "high_multiplicity_edges_without_evidence_samples_count",
                trace["high_multiplicity_edges_without_evidence_samples_count"],
                THRESHOLDS["max_high_multiplicity_edges_without_evidence_samples"],
                "Collapsed duplicate edge triples must preserve bounded samples of contributing evidence paths/selectors.",
                trace["high_multiplicity_edges_without_evidence_samples"][
                    :max_examples
                ],
            )
        )

    ontology = metrics["ontology"]
    if len(ontology["unknown_node_types"]) > THRESHOLDS["max_unknown_node_types"]:
        issues.append(
            issue(
                "critical",
                "UNKNOWN_NODE_TYPES",
                graph_rel,
                "unknown_node_type_count",
                len(ontology["unknown_node_types"]),
                THRESHOLDS["max_unknown_node_types"],
                "Map unknown node types into the allowed ontology or extend ALLOWED_NODE_TYPES with an explicit domain contract.",
                ontology["unknown_node_types"][:max_examples],
            )
        )
    if (
        len(ontology["unknown_relation_types"])
        > THRESHOLDS["max_unknown_relation_types"]
    ):
        issues.append(
            issue(
                "critical",
                "UNKNOWN_RELATION_TYPES",
                graph_rel,
                "unknown_relation_type_count",
                len(ontology["unknown_relation_types"]),
                THRESHOLDS["max_unknown_relation_types"],
                "Map unknown relations into the allowed ontology or add relation rules with domain/range constraints.",
                ontology["unknown_relation_types"][:max_examples],
            )
        )
    if (
        ontology["domain_range_violation_count"]
        > THRESHOLDS["max_domain_range_violations"]
    ):
        issues.append(
            issue(
                "critical",
                "RELATION_DOMAIN_RANGE_VIOLATIONS",
                graph_rel,
                "domain_range_violation_count",
                ontology["domain_range_violation_count"],
                THRESHOLDS["max_domain_range_violations"],
                "Fix relation endpoints so every edge satisfies the declared source and target node-type contract.",
                ontology["domain_range_violation_samples"][:max_examples],
            )
        )

    missing_critical_categories = sorted(
        category
        for category, coverage in ontology["critical_category_coverage"].items()
        if not coverage["covered"]
    )
    if missing_critical_categories:
        issues.append(
            issue(
                "high",
                "MISSING_CRITICAL_NODE_CATEGORIES",
                graph_rel,
                "missing_critical_category_count",
                len(missing_critical_categories),
                0,
                "Represent model, metric, commit, and decision evidence as first-class nodes or document an explicit ontology mapping.",
                missing_critical_categories[:max_examples],
            )
        )

    summaries = metrics["summaries"]
    if summaries["direct_summary_coverage"] < THRESHOLDS["min_direct_summary_coverage"]:
        issues.append(
            issue(
                "high",
                "LOW_DIRECT_SUMMARY_COVERAGE",
                graph_rel,
                "direct_summary_coverage",
                round(summaries["direct_summary_coverage"], 4),
                f">= {THRESHOLDS['min_direct_summary_coverage']}",
                "Populate node.summary with a short evidence-grounded summary for datasets, configs, reports, methods, audits, and policies.",
                summaries["missing_direct_summary_samples"][:max_examples],
            )
        )
    if (
        summaries["semantic_summary_coverage"]
        < THRESHOLDS["min_semantic_summary_coverage"]
    ):
        issues.append(
            issue(
                "medium",
                "LOW_SEMANTIC_SUMMARY_COVERAGE",
                graph_rel,
                "semantic_summary_coverage",
                round(summaries["semantic_summary_coverage"], 4),
                f">= {THRESHOLDS['min_semantic_summary_coverage']}",
                "Ensure nodes have at least one human-readable summary-like field, not only IDs and paths.",
            )
        )
    if summaries["short_direct_summary_count"]:
        issues.append(
            issue(
                "low",
                "THIN_NODE_SUMMARIES",
                graph_rel,
                "short_direct_summary_count",
                summaries["short_direct_summary_count"],
                0,
                "Replace generic generated summaries with evidence-grounded method/config descriptions where the audit marks them as short.",
                summaries["short_direct_summary_samples"][:max_examples],
            )
        )

    endpoint_linkage = metrics["endpoint_linkage"]
    for relation in ENDPOINT_RESULT_REQUIRED_RELATIONS:
        coverage = endpoint_linkage["endpoint_result_relation_coverage"][relation]
        if coverage["coverage"] < 1.0:
            issues.append(
                issue(
                    "medium",
                    f"ENDPOINT_RESULT_MISSING_{relation}",
                    graph_rel,
                    f"endpoint_result.{relation}.coverage",
                    round(coverage["coverage"], 4),
                    1.0,
                    "Endpoint result nodes must remain traceable to their endpoint audit, primary report, method, dataset, and reported metrics.",
                    coverage["missing_samples"][:max_examples],
                )
            )
    config_coverage = endpoint_linkage["endpoint_result_relation_coverage"][
        "SUMMARIZES_CONFIG"
    ]
    if config_coverage["coverage"] < 1.0:
        issues.append(
            issue(
                "low",
                "ENDPOINT_RESULTS_WITHOUT_CONFIG_LINKAGE",
                graph_rel,
                "endpoint_result.SUMMARIZES_CONFIG.coverage",
                round(config_coverage["coverage"], 4),
                1.0,
                "Link every endpoint_result node to the config it summarizes so method/config provenance stays explicit.",
                config_coverage["missing_samples"][:max_examples],
            )
        )
    for relation in ENDPOINT_CAVEAT_REQUIRED_RELATIONS:
        coverage = endpoint_linkage["endpoint_caveat_relation_coverage"][relation]
        if coverage["coverage"] < 1.0:
            issues.append(
                issue(
                    "medium",
                    f"ENDPOINT_CAVEAT_MISSING_{relation}",
                    graph_rel,
                    f"endpoint_caveat.{relation}.coverage",
                    round(coverage["coverage"], 4),
                    1.0,
                    "Endpoint caveat nodes must point back to the endpoint-audit evidence that created them.",
                    coverage["missing_samples"][:max_examples],
                )
            )
    for relation in ENDPOINT_STATE_REQUIRED_RELATIONS:
        coverage = endpoint_linkage["endpoint_state_relation_coverage"][relation]
        if coverage["coverage"] < 1.0:
            issues.append(
                issue(
                    "medium",
                    f"ENDPOINT_STATE_MISSING_{relation}",
                    graph_rel,
                    f"endpoint_state.{relation}.coverage",
                    round(coverage["coverage"], 4),
                    1.0,
                    "Endpoint state nodes must point back to the endpoint-audit evidence that created them.",
                    coverage["missing_samples"][:max_examples],
                )
            )
    if (
        endpoint_linkage["missing_endpoint_state_count"]
        > THRESHOLDS["max_endpoint_results_without_state"]
    ):
        issues.append(
            issue(
                "medium",
                "ENDPOINT_RESULTS_WITHOUT_EXPLICIT_STATE",
                graph_rel,
                "endpoint_linkage.missing_endpoint_state_count",
                endpoint_linkage["missing_endpoint_state_count"],
                THRESHOLDS["max_endpoint_results_without_state"],
                (
                    "Every endpoint_result should link to an endpoint_state node "
                    "so clean/no-caveat and caveated states are both queryable."
                ),
                endpoint_linkage["missing_endpoint_state_samples"][:max_examples],
            )
        )
    if (
        endpoint_linkage["clean_zero_interval_endpoint_result_count"]
        > THRESHOLDS["max_clean_zero_interval_endpoint_results"]
    ):
        issues.append(
            issue(
                "high",
                "CLEAN_ENDPOINT_RESULT_WITH_ZERO_INTERVALS",
                graph_rel,
                "endpoint_linkage.clean_zero_interval_endpoint_result_count",
                endpoint_linkage["clean_zero_interval_endpoint_result_count"],
                THRESHOLDS["max_clean_zero_interval_endpoint_results"],
                (
                    "Endpoint results without positive reconstructed interval counts "
                    "must not be labeled clean; normalize legacy endpoint schemas or "
                    "mark them schema-incomplete."
                ),
                endpoint_linkage["clean_zero_interval_endpoint_result_samples"][
                    :max_examples
                ],
            )
        )
    if (
        endpoint_linkage["zero_interval_endpoint_result_count"]
        > THRESHOLDS["max_zero_interval_endpoint_results"]
    ):
        issues.append(
            issue(
                "medium",
                "ENDPOINT_RESULT_WITH_ZERO_INTERVALS",
                graph_rel,
                "endpoint_linkage.zero_interval_endpoint_result_count",
                endpoint_linkage["zero_interval_endpoint_result_count"],
                THRESHOLDS["max_zero_interval_endpoint_results"],
                (
                    "Every endpoint_result should carry a positive reconstructed "
                    "interval count, either from v2 fields or normalized legacy "
                    "endpoint_count/endpoints fields."
                ),
                endpoint_linkage["zero_interval_endpoint_result_samples"][
                    :max_examples
                ],
            )
        )

    critical_linkage = metrics["critical_linkage"]
    for key in (
        "datasets_with_audit",
        "datasets_with_source",
        "datasets_queued_or_reported",
        "decisions_link_dataset",
        "reports_summarize_dataset",
        "reports_evaluate_method",
    ):
        coverage = critical_linkage[key]
        if coverage["coverage"] < 1.0:
            issues.append(
                issue(
                    "low",
                    f"INCOMPLETE_{key.upper()}",
                    graph_rel,
                    f"critical_linkage.{key}.coverage",
                    round(coverage["coverage"], 4),
                    1.0,
                    "Review whether missing links are intentional exclusions; if so, model that decision explicitly instead of leaving an unqualified linkage gap.",
                    coverage["missing_samples"][:max_examples],
                )
            )

    observations = metrics["observations"]
    if (
        observations["observation_node_ratio"]
        < THRESHOLDS["min_observation_node_ratio"]
    ):
        issues.append(
            issue(
                "high",
                "LOW_OBSERVATION_NODE_RATIO",
                graph_rel,
                "observation_node_ratio",
                round(observations["observation_node_ratio"], 4),
                f">= {THRESHOLDS['min_observation_node_ratio']}",
                "Emit observation records per node for key facts, source snippets, report metrics, and audit decisions.",
            )
        )
    if (
        observations["paper_evidence_observation_node_ratio"]
        < THRESHOLDS["min_paper_evidence_observation_node_ratio"]
    ):
        issues.append(
            issue(
                "medium",
                "LOW_PAPER_EVIDENCE_OBSERVATION_NODE_RATIO",
                graph_rel,
                "paper_evidence_observation_node_ratio",
                round(observations["paper_evidence_observation_node_ratio"], 4),
                f">= {THRESHOLDS['min_paper_evidence_observation_node_ratio']}",
                "Do not count generated topology observations as paper evidence; add source-grounded observations to important nodes.",
            )
        )

    freshness = metrics["freshness"]["tracked_source_coverage"]
    freshness_thresholds = {
        "configs": "max_missing_tracked_configs",
        "reports": "max_missing_tracked_reports",
        "audits": "max_missing_tracked_audits",
        "graph_docs": "max_missing_tracked_graph_docs",
    }
    for category, threshold_name in freshness_thresholds.items():
        missing_count = freshness[category]["missing_count"]
        if missing_count > THRESHOLDS[threshold_name]:
            issues.append(
                issue(
                    "critical",
                    f"MISSING_TRACKED_{category.upper()}",
                    graph_rel,
                    f"{category}.missing_count",
                    missing_count,
                    THRESHOLDS[threshold_name],
                    "Rebuild or patch the KG so every tracked source artifact in this category has a node path/json_path/audit_path.",
                    freshness[category]["missing_samples"][:max_examples],
                )
            )

    if metrics["freshness"]["working_tree_relevant_untracked_count"]:
        issues.append(
            issue(
                "info",
                "UNTRACKED_RELEVANT_SOURCES",
                graph_rel,
                "working_tree_relevant_untracked_count",
                metrics["freshness"]["working_tree_relevant_untracked_count"],
                0,
                "Another active agent may be preparing sources; do not treat untracked files as committed KG staleness until they are owned.",
                metrics["freshness"]["working_tree_relevant_untracked_samples"][
                    :max_examples
                ],
            )
        )

    return issues


def audit_graph(
    graph_path: Path = DEFAULT_GRAPH,
    repo_root: Path = REPO_ROOT,
    max_examples: int = 25,
) -> dict[str, Any]:
    graph = load_graph(graph_path)
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    nodes_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    node_count = len(nodes)
    edge_count = len(edges)
    unique_edge_triples = {edge_key(edge) for edge in edges}
    possible_directed_edges = node_count * (node_count - 1)
    connectivity = connectivity_metrics(nodes_by_id, edges)

    metadata = {
        "schema": graph.get("schema"),
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "graph_path": repo_relative(graph_path, repo_root),
        "repo_root": str(repo_root),
        "thresholds": THRESHOLDS,
    }
    metrics = {
        "metadata": metadata,
        "graph": {
            "declared_node_count": graph.get("node_count"),
            "declared_edge_count": graph.get("edge_count"),
            "node_count": node_count,
            "edge_count": edge_count,
            "edge_node_ratio": edge_count / node_count if node_count else 0.0,
            "unique_edge_triple_count": len(unique_edge_triples),
            "graph_density": (
                len(unique_edge_triples) / possible_directed_edges
                if possible_directed_edges
                else 0.0
            ),
            **connectivity,
        },
        "referential_integrity": referential_integrity_metrics(
            nodes, nodes_by_id, edges, repo_root, max_examples
        ),
        "traceability": traceability_metrics(edges),
        "claim_traceability": claim_traceability_metrics(
            nodes_by_id,
            edges,
            max_examples,
        ),
        "paper_gate_traceability": paper_gate_traceability_metrics(
            nodes_by_id,
            edges,
            max_examples,
        ),
        "ontology": ontology_metrics(nodes_by_id, edges, max_examples),
        "summaries": summary_metrics(nodes, max_examples),
        "observations": observation_metrics(graph, nodes),
        "freshness": source_freshness_metrics(nodes, repo_root, max_examples),
        "critical_linkage": critical_linkage_metrics(nodes_by_id, edges, max_examples),
        "endpoint_linkage": endpoint_linkage_metrics(
            nodes_by_id,
            edges,
            max_examples,
        ),
        "method_evidence": method_evidence_metrics(
            nodes_by_id,
            edges,
            max_examples,
        ),
    }
    metrics["issues"] = build_issues(graph_path, metrics, max_examples)
    metrics["issue_counts_by_severity"] = compact_counter(
        Counter(issue["severity"] for issue in metrics["issues"])
    )
    return metrics


def has_blocking_issues(issues: list[dict[str, Any]], fail_on: str) -> bool:
    if fail_on == "none":
        return False
    threshold = SEVERITY_RANK[fail_on]
    return any(SEVERITY_RANK[issue["severity"]] >= threshold for issue in issues)


def write_report(report: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    graph_path = Path(args.graph)
    if not graph_path.is_absolute():
        graph_path = repo_root / graph_path
    report = audit_graph(
        graph_path=graph_path,
        repo_root=repo_root,
        max_examples=args.max_examples,
    )
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = repo_root / out_path
        write_report(report, out_path)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if has_blocking_issues(report["issues"], args.fail_on) else 0


if __name__ == "__main__":
    sys.exit(main())
