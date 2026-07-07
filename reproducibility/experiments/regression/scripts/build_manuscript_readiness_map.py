"""Build a paper-readiness map from current manuscript gates.

The output is a planning artifact for drafting the future paper. It does not
promote any final result; it makes the blocked final-claim gates, eligible
caveated surfaces, and required closure evidence explicit and reproducible.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_manuscript_readiness_map_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/paper_readiness_map.json")
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
PROTOCOL = Path("experiments/regression/PUBLICATION_READINESS_PROTOCOL.md")
SELECTION_MULTIPLICITY_PROTOCOL = Path(
    "experiments/regression/manuscript/selection_multiplicity_protocol.json"
)
SELECTION_MULTIPLICITY_EVIDENCE_RECORD = Path(
    "experiments/regression/manuscript/selection_multiplicity_evidence_record.json"
)
BOUNDED_SUPPORT_PROTOCOL = Path(
    "experiments/regression/manuscript/bounded_support_protocol.json"
)
BOUNDED_SUPPORT_DATASET_AUDIT = Path(
    "experiments/regression/manuscript/bounded_support_dataset_audit.json"
)
BOUNDED_SUPPORT_ENDPOINT_CLOSURE = (
    REPORT_DIR / "bounded_support_endpoint_closure_audit.json"
)
BOUNDED_SUPPORT_POSITIVE_VALIDATION = Path(
    "experiments/regression/manuscript/"
    "bounded_support_positive_validation_protocol.json"
)
TARGET_DOMAIN_PROVENANCE = Path(
    "experiments/regression/catalogs/target_domain_provenance.json"
)
BOUNDED_SUPPORT_POSTHANDLING_VALIDATION = Path(
    "experiments/regression/manuscript/bounded_support_posthandling_validation.json"
)
PUBLICATION_METHODOLOGY = REPORT_DIR / "publication_methodology_audit.json"
MANIFEST_COMPLETENESS_AUDIT = REPORT_DIR / "manuscript_manifest_completeness_audit.json"
DATASET_SPECIFIC_FINAL_GATE_AUDIT = REPORT_DIR / "dataset_specific_final_gate_audit.json"
MAIN_RESULT_CANDIDATE_BUNDLE_PLAN = REPORT_DIR / "main_result_candidate_bundle_plan.json"
MAIN_RESULT_CANDIDATE_BUNDLE_RESULTS = (
    REPORT_DIR / "main_result_candidate_bundle_results.json"
)
MAIN_RESULT_CANDIDATE_POST_RUN_CLOSURE = (
    REPORT_DIR / "main_result_candidate_post_run_closure_audit.json"
)
METHOD_SELECTION_ALPHA_EXPANSION_PLAN = (
    REPORT_DIR / "method_selection_alpha_expansion_plan.json"
)
METHOD_SELECTION_ALPHA_EXPANSION_BATCH = (
    REPORT_DIR / "method_selection_alpha_expansion_batch.json"
)
METHOD_SELECTION_ALPHA_EXPANSION_EXECUTION = (
    REPORT_DIR / "method_selection_alpha_expansion_execution_audit.json"
)
METHOD_SELECTION_INFERENTIAL_AUDIT = (
    REPORT_DIR / "method_selection_inferential_audit.json"
)
METHOD_SELECTION_POST_SELECTION_VALIDATION_RESULTS = (
    REPORT_DIR / "method_selection_post_selection_validation_results.json"
)
FINAL_SELECTION = REPORT_DIR / "final_selection_claim_boundary_audit.json"
FAIRNESS_POPULATION_READINESS = REPORT_DIR / "fairness_population_readiness_audit.json"
FAIRNESS_GROUP_DIAGNOSTIC_AUDIT = REPORT_DIR / "fairness_group_diagnostic_audit.json"
FAIRNESS_GROUP_MULTIPLICITY_SCOPE = Path(
    "experiments/regression/manuscript/fairness_group_multiplicity_scope.json"
)
FAIRNESS_SAMPLING_WEIGHT_POLICY = Path(
    "experiments/regression/manuscript/fairness_sampling_weight_policy.json"
)
VENN_ABERS_VALIDATION = REPORT_DIR / "venn_abers_validation_readiness_audit.json"
VENN_ABERS_GRID_IVAPD_PROTOCOL = (
    REPORT_DIR / "venn_abers_grid_ivapd_validation_protocol.json"
)
VENN_ABERS_GRID_FAILURE_MODE_DECOMPOSITION = (
    REPORT_DIR / "venn_abers_grid_failure_mode_decomposition.json"
)
VENN_ABERS_CLAIM_GATE_MATRIX = REPORT_DIR / "venn_abers_claim_gate_matrix.json"
VENN_ABERS_NEGATIVE_DISPOSITION = (
    REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
)
EVIDENCE_VIEW = Path("experiments/regression/manuscript/evidence_view.json")
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
KG_QUALITY = Path(
    "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
)
KG_CATALOG = Path("experiments/regression/catalogs/knowledge_graph.json")
POST_EXPERIMENT_PUBLICATION_PROGRAM = Path(
    "experiments/regression/manuscript/post_experiment_publication_program.json"
)

GATE_DETAILS: dict[str, dict[str, Any]] = {
    "final_method_model_selection_gate": {
        "paper_risk": "No final conformal method/model winner can be claimed.",
        "closure_standard": "Predeclare the operating criterion, ranking scope, tie-break rule, and post-selection validation evidence before promoting a winner.",
        "next_actions": [
            "Apply the selection/multiplicity protocol to each candidate main-result manifest.",
            "Use the alpha-expansion execution audit to verify alpha-support imbalance closure before interpreting method-selection robustness.",
            "Use post-selection validation results as diagnostic validation evidence only, not as final winner evidence.",
            "Run selection only inside bundles whose split, leakage, duplicate, endpoint, and claim gates pass.",
            "Record selected and non-selected rows with multiplicity scope and validation status.",
        ],
        "source_artifacts": [
            str(PROTOCOL),
            str(SELECTION_MULTIPLICITY_PROTOCOL),
            str(SELECTION_MULTIPLICITY_EVIDENCE_RECORD),
            str(METHOD_SELECTION_ALPHA_EXPANSION_PLAN),
            str(METHOD_SELECTION_ALPHA_EXPANSION_BATCH),
            str(METHOD_SELECTION_ALPHA_EXPANSION_EXECUTION),
            str(METHOD_SELECTION_INFERENTIAL_AUDIT),
            str(METHOD_SELECTION_POST_SELECTION_VALIDATION_RESULTS),
            str(MAIN_RESULT_CANDIDATE_BUNDLE_PLAN),
            str(MAIN_RESULT_CANDIDATE_BUNDLE_RESULTS),
            str(MAIN_RESULT_CANDIDATE_POST_RUN_CLOSURE),
            str(MANIFEST_COMPLETENESS_AUDIT),
            str(FINAL_SELECTION),
            str(PUBLICATION_METHODOLOGY),
        ],
    },
    "multiplicity_selection_record": {
        "paper_risk": "Best/winner language would be post-hoc and overstate the searched model-method grid.",
        "closure_standard": "Every paper-facing recommendation must state how many dataset/model/method/seed rows were searched and how ties or failed rows were handled.",
        "next_actions": [
            "Add selection_multiplicity_evidence to every main-result manifest.",
            "Aggregate completed ledger rows into declared ranking scopes.",
            "Reconcile alpha-expansion batch-generation labels against completed ledgers before citing alpha-support remediation.",
            "Audit that recommendation text cites the multiplicity record before publication extraction.",
        ],
        "source_artifacts": [
            str(PROTOCOL),
            str(SELECTION_MULTIPLICITY_PROTOCOL),
            str(SELECTION_MULTIPLICITY_EVIDENCE_RECORD),
            str(METHOD_SELECTION_ALPHA_EXPANSION_PLAN),
            str(METHOD_SELECTION_ALPHA_EXPANSION_EXECUTION),
            str(METHOD_SELECTION_INFERENTIAL_AUDIT),
            str(METHOD_SELECTION_POST_SELECTION_VALIDATION_RESULTS),
            str(BUNDLE_INDEX),
            str(MANIFEST_COMPLETENESS_AUDIT),
            str(PUBLICATION_METHODOLOGY),
        ],
    },
    "dataset_specific_final_gates": {
        "paper_risk": "Current completed bundles are robustness/sensitivity evidence with caveats, not final dataset result bundles.",
        "closure_standard": "Each dataset used in a main table needs a passed manifest, data audit, split/leakage/duplicate controls, endpoint audit, and claim-register scope.",
        "next_actions": [
            "Choose candidate main-paper datasets from the source registry and bundle index.",
            "Generate or refresh publication-readiness manifests for each main dataset bundle.",
            "Promote only bundles whose manifest and claim boundaries pass without final-claim caveats.",
        ],
        "source_artifacts": [
            str(DATASET_SPECIFIC_FINAL_GATE_AUDIT),
            str(MAIN_RESULT_CANDIDATE_BUNDLE_PLAN),
            str(MAIN_RESULT_CANDIDATE_BUNDLE_RESULTS),
            str(MAIN_RESULT_CANDIDATE_POST_RUN_CLOSURE),
            str(EVIDENCE_VIEW),
            str(BUNDLE_INDEX),
            str(PUBLICATION_METHODOLOGY),
        ],
    },
    "endpoint_bounded_support_gate": {
        "paper_risk": "Endpoint reconstruction hygiene is not the same as bounded-support or target-domain validity.",
        "closure_standard": "Targets with natural bounds need explicit endpoint-domain policy, out-of-support accounting, and interval handling rules before bounded-support claims.",
        "next_actions": [
            "Apply the bounded-support protocol to classify target-domain bounds for each candidate main-paper dataset.",
            "Use target-domain provenance to separate source-backed natural bounds from observed-range diagnostics.",
            "Use bounded-support post-handling validation to separate raw endpoint excursions from clipped/abstained policy metrics.",
            "Use the bounded-support dataset audit to review endpoint-domain excursions and missing natural-bound provenance by bundle.",
            "Run endpoint-domain audits that separate reconstruction hygiene from support validity.",
            "Record clipping, truncation, or abstention policy before using bounded-support language.",
        ],
        "source_artifacts": [
            str(PROTOCOL),
            str(BOUNDED_SUPPORT_PROTOCOL),
            str(TARGET_DOMAIN_PROVENANCE),
            str(BOUNDED_SUPPORT_POSTHANDLING_VALIDATION),
            str(BOUNDED_SUPPORT_DATASET_AUDIT),
            str(BOUNDED_SUPPORT_ENDPOINT_CLOSURE),
            str(BOUNDED_SUPPORT_POSITIVE_VALIDATION),
            str(EVIDENCE_VIEW),
            str(PUBLICATION_METHODOLOGY),
        ],
    },
    "fairness_population_inference_gate": {
        "paper_risk": "Group diagnostics cannot be promoted to protected-class fairness, population, legal, policy, or clinical conclusions.",
        "closure_standard": "Fairness or population claims require dedicated group definitions, sampling/weighting policy, protected-attribute scope, and claim-register approval.",
        "next_actions": [
            "Separate diagnostic-group coverage from fairness/population inference in every table.",
            "For any fairness paper claim, define population, protected group, estimand, and weighting policy.",
            "Run a dedicated fairness-readiness audit before moving beyond diagnostic language.",
        ],
        "source_artifacts": [
            str(PROTOCOL),
            str(EVIDENCE_VIEW),
            str(FAIRNESS_POPULATION_READINESS),
            str(FAIRNESS_GROUP_DIAGNOSTIC_AUDIT),
            str(FAIRNESS_SAMPLING_WEIGHT_POLICY),
            str(FINAL_SELECTION),
        ],
    },
    "venn_abers_regression_validation_gate": {
        "paper_risk": "The current fast Venn-Abers bridge undercovers and cannot be reported as validated Venn-Abers regression.",
        "closure_standard": "The current paper can report the observed negative Venn-Abers result; a positive Venn-Abers regression validation claim needs a separate methodologically sound construction and benchmark.",
        "next_actions": [
            "Keep the fast bridge as negative/failure-mode evidence in the current manuscript layer.",
            "Do not force a positive Venn-Abers validation outcome for the current paper.",
            "Design a separate Venn-Abers regression validation protocol only as optional future work before any positive claim.",
        ],
        "source_artifacts": [
            str(VENN_ABERS_VALIDATION),
            str(VENN_ABERS_GRID_IVAPD_PROTOCOL),
            str(VENN_ABERS_GRID_FAILURE_MODE_DECOMPOSITION),
            str(VENN_ABERS_CLAIM_GATE_MATRIX),
            str(VENN_ABERS_NEGATIVE_DISPOSITION),
            str(FINAL_SELECTION),
            str(PUBLICATION_METHODOLOGY),
        ],
    },
}

SURFACE_ORDER = (
    "dataset_table",
    "method_table",
    "main_results_table",
    "robustness_results_table",
    "negative_results_table",
    "methodology_appendix",
    "reproducibility_appendix",
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def kg_has_high_issue(kg_quality: dict[str, Any]) -> bool:
    issues = kg_quality.get("issues") or {}
    if isinstance(issues, dict):
        return bool(issues.get("high"))
    if isinstance(issues, list):
        return any(
            isinstance(row, dict)
            and str(row.get("severity", "")).lower() in {"high", "critical"}
            for row in issues
        )
    return False


def graph_count(value: dict[str, Any], key: str, fallback_key: str) -> int | None:
    raw = value.get(key)
    if raw is None:
        raw = value.get(fallback_key)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def gate_rows(requirement_statuses: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gate_id, status in sorted(requirement_statuses.items()):
        if gate_id == "remediation_backlog_closed_or_scoped":
            continue
        detail = GATE_DETAILS.get(gate_id, {})
        rows.append(
            {
                "gate_id": gate_id,
                "status": status,
                "paper_risk": detail.get("paper_risk", "Unspecified final-claim risk."),
                "closure_standard": detail.get(
                    "closure_standard", "Dedicated gate must pass before promotion."
                ),
                "next_actions": list(detail.get("next_actions", [])),
                "source_artifacts": list(detail.get("source_artifacts", [])),
            }
        )
    return rows


def surface_rows(
    evidence_view: dict[str, Any],
    bundle_index: dict[str, Any],
    publication_summary: dict[str, Any],
    kg_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence_rows = [
        row for row in evidence_view.get("rows", []) or [] if isinstance(row, dict)
    ]
    table_candidate_counts = Counter(
        candidate
        for row in evidence_rows
        for candidate in row.get("paper_table_candidates", []) or []
    )
    bundle_summary = bundle_index.get("bundle_summary") or {}
    manifested_bundle_count = int(
        bundle_summary.get("manifest_count")
        or len(bundle_index.get("bundles", []) or [])
    )
    main_blockers = [
        "final_method_model_selection_gate",
        "multiplicity_selection_record",
        "dataset_specific_final_gates",
    ]
    surfaces = {
        "dataset_table": {
            "status": "scaffold_ready_with_source_audit_dependency",
            "evidence": f"{manifested_bundle_count} manifested bundles; dataset table remains descriptive.",
            "blocking_gates": ["dataset_specific_final_gates"],
        },
        "method_table": {
            "status": "scaffold_ready",
            "evidence": "Method registry/spec material can support a descriptive method table with explicit boundaries.",
            "blocking_gates": [],
        },
        "main_results_table": {
            "status": "blocked",
            "evidence": "No final method/model selection or dataset-specific final gate is passed.",
            "blocking_gates": main_blockers,
        },
        "robustness_results_table": {
            "status": "caveated_extraction_candidate",
            "evidence": f"{sum(count for candidate, count in table_candidate_counts.items() if candidate.startswith('robustness_results_table'))} claim rows point to robustness table candidates.",
            "blocking_gates": ["dataset_specific_final_gates"],
        },
        "negative_results_table": {
            "status": "diagnostic_extraction_candidate",
            "evidence": "Venn-Abers fast-bridge undercoverage is preserved as negative evidence.",
            "blocking_gates": [],
        },
        "methodology_appendix": {
            "status": "ready_with_caveats",
            "evidence": f"Publication methodology status is {publication_summary.get('overall_status')}.",
            "blocking_gates": [],
        },
        "reproducibility_appendix": {
            "status": "ready_with_caveats",
            "evidence": f"KG status is {kg_summary.get('status')} with {kg_summary.get('node_count')} nodes and {kg_summary.get('edge_count')} edges.",
            "blocking_gates": [],
        },
    }
    return [{"surface_id": key, **surfaces[key]} for key in SURFACE_ORDER]


def build_payload(root: Path) -> dict[str, Any]:
    publication_path = root / PUBLICATION_METHODOLOGY
    selection_protocol_path = root / SELECTION_MULTIPLICITY_PROTOCOL
    selection_evidence_path = root / SELECTION_MULTIPLICITY_EVIDENCE_RECORD
    bounded_support_protocol_path = root / BOUNDED_SUPPORT_PROTOCOL
    target_domain_provenance_path = root / TARGET_DOMAIN_PROVENANCE
    bounded_support_posthandling_path = root / BOUNDED_SUPPORT_POSTHANDLING_VALIDATION
    bounded_support_dataset_audit_path = root / BOUNDED_SUPPORT_DATASET_AUDIT
    bounded_support_endpoint_closure_path = root / BOUNDED_SUPPORT_ENDPOINT_CLOSURE
    bounded_support_positive_validation_path = (
        root / BOUNDED_SUPPORT_POSITIVE_VALIDATION
    )
    manifest_completeness_path = root / MANIFEST_COMPLETENESS_AUDIT
    dataset_specific_final_gate_path = root / DATASET_SPECIFIC_FINAL_GATE_AUDIT
    main_result_candidate_bundle_plan_path = root / MAIN_RESULT_CANDIDATE_BUNDLE_PLAN
    main_result_candidate_bundle_results_path = (
        root / MAIN_RESULT_CANDIDATE_BUNDLE_RESULTS
    )
    main_result_candidate_post_run_closure_path = (
        root / MAIN_RESULT_CANDIDATE_POST_RUN_CLOSURE
    )
    method_selection_alpha_expansion_plan_path = (
        root / METHOD_SELECTION_ALPHA_EXPANSION_PLAN
    )
    method_selection_alpha_expansion_batch_path = (
        root / METHOD_SELECTION_ALPHA_EXPANSION_BATCH
    )
    method_selection_alpha_expansion_execution_path = (
        root / METHOD_SELECTION_ALPHA_EXPANSION_EXECUTION
    )
    method_selection_inferential_audit_path = (
        root / METHOD_SELECTION_INFERENTIAL_AUDIT
    )
    method_selection_post_selection_validation_results_path = (
        root / METHOD_SELECTION_POST_SELECTION_VALIDATION_RESULTS
    )
    final_selection_path = root / FINAL_SELECTION
    fairness_population_path = root / FAIRNESS_POPULATION_READINESS
    venn_abers_path = root / VENN_ABERS_VALIDATION
    venn_abers_grid_ivapd_path = root / VENN_ABERS_GRID_IVAPD_PROTOCOL
    venn_abers_claim_gate_matrix_path = root / VENN_ABERS_CLAIM_GATE_MATRIX
    venn_abers_negative_disposition_path = root / VENN_ABERS_NEGATIVE_DISPOSITION
    evidence_view_path = root / EVIDENCE_VIEW
    bundle_index_path = root / BUNDLE_INDEX
    kg_quality_path = root / KG_QUALITY
    kg_catalog_path = root / KG_CATALOG
    post_experiment_publication_program_path = (
        root / POST_EXPERIMENT_PUBLICATION_PROGRAM
    )
    protocol_path = root / PROTOCOL

    publication = read_json(publication_path)
    selection_protocol = read_json(selection_protocol_path)
    selection_evidence = (
        read_json(selection_evidence_path) if selection_evidence_path.exists() else {}
    )
    bounded_support_protocol = read_json(bounded_support_protocol_path)
    target_domain_provenance = read_json(target_domain_provenance_path)
    bounded_support_posthandling = read_json(bounded_support_posthandling_path)
    bounded_support_dataset_audit = read_json(bounded_support_dataset_audit_path)
    bounded_support_endpoint_closure = (
        read_json(bounded_support_endpoint_closure_path)
        if bounded_support_endpoint_closure_path.exists()
        else {}
    )
    bounded_support_positive_validation = (
        read_json(bounded_support_positive_validation_path)
        if bounded_support_positive_validation_path.exists()
        else {}
    )
    manifest_completeness = (
        read_json(manifest_completeness_path)
        if manifest_completeness_path.exists()
        else {}
    )
    dataset_specific_final_gate = (
        read_json(dataset_specific_final_gate_path)
        if dataset_specific_final_gate_path.exists()
        else {}
    )
    main_result_candidate_bundle_plan = (
        read_json(main_result_candidate_bundle_plan_path)
        if main_result_candidate_bundle_plan_path.exists()
        else {}
    )
    main_result_candidate_bundle_results = (
        read_json(main_result_candidate_bundle_results_path)
        if main_result_candidate_bundle_results_path.exists()
        else {}
    )
    main_result_candidate_post_run_closure = (
        read_json(main_result_candidate_post_run_closure_path)
        if main_result_candidate_post_run_closure_path.exists()
        else {}
    )
    method_selection_alpha_expansion_plan = (
        read_json(method_selection_alpha_expansion_plan_path)
        if method_selection_alpha_expansion_plan_path.exists()
        else {}
    )
    method_selection_alpha_expansion_batch = (
        read_json(method_selection_alpha_expansion_batch_path)
        if method_selection_alpha_expansion_batch_path.exists()
        else {}
    )
    method_selection_alpha_expansion_execution = (
        read_json(method_selection_alpha_expansion_execution_path)
        if method_selection_alpha_expansion_execution_path.exists()
        else {}
    )
    method_selection_inferential_audit = (
        read_json(method_selection_inferential_audit_path)
        if method_selection_inferential_audit_path.exists()
        else {}
    )
    method_selection_post_selection_validation_results = (
        read_json(method_selection_post_selection_validation_results_path)
        if method_selection_post_selection_validation_results_path.exists()
        else {}
    )
    final_selection = read_json(final_selection_path)
    fairness_population = read_json(fairness_population_path)
    fairness_group_diagnostic_path = root / FAIRNESS_GROUP_DIAGNOSTIC_AUDIT
    fairness_group_diagnostic = (
        read_json(fairness_group_diagnostic_path)
        if fairness_group_diagnostic_path.exists()
        else {}
    )
    fairness_group_multiplicity_scope_path = root / FAIRNESS_GROUP_MULTIPLICITY_SCOPE
    fairness_group_multiplicity_scope = (
        read_json(fairness_group_multiplicity_scope_path)
        if fairness_group_multiplicity_scope_path.exists()
        else {}
    )
    venn_abers = read_json(venn_abers_path)
    venn_abers_claim_gate_matrix = (
        read_json(venn_abers_claim_gate_matrix_path)
        if venn_abers_claim_gate_matrix_path.exists()
        else {}
    )
    venn_abers_negative_disposition = (
        read_json(venn_abers_negative_disposition_path)
        if venn_abers_negative_disposition_path.exists()
        else {}
    )
    evidence_view = read_json(evidence_view_path)
    bundle_index = read_json(bundle_index_path)
    kg_quality = read_json(kg_quality_path)
    kg_catalog = read_json(kg_catalog_path) if kg_catalog_path.exists() else {}
    post_experiment_publication_program = (
        read_json(post_experiment_publication_program_path)
        if post_experiment_publication_program_path.exists()
        else {}
    )

    publication_summary = publication.get("summary") or {}
    selection_protocol_summary = selection_protocol.get("summary") or {}
    selection_evidence_summary = selection_evidence.get("summary") or {}
    bounded_support_protocol_summary = bounded_support_protocol.get("summary") or {}
    target_domain_provenance_summary = target_domain_provenance.get("summary") or {}
    bounded_support_posthandling_summary = (
        bounded_support_posthandling.get("summary") or {}
    )
    bounded_support_dataset_summary = bounded_support_dataset_audit.get("summary") or {}
    bounded_support_endpoint_closure_summary = (
        bounded_support_endpoint_closure.get("summary") or {}
    )
    bounded_support_positive_validation_summary = (
        bounded_support_positive_validation.get("summary") or {}
    )
    manifest_completeness_summary = manifest_completeness.get("summary") or {}
    dataset_specific_final_gate_summary = (
        dataset_specific_final_gate.get("summary") or {}
    )
    main_result_candidate_bundle_plan_summary = (
        main_result_candidate_bundle_plan.get("summary") or {}
    )
    main_result_candidate_bundle_results_summary = (
        main_result_candidate_bundle_results.get("summary") or {}
    )
    main_result_candidate_post_run_closure_summary = (
        main_result_candidate_post_run_closure.get("summary") or {}
    )
    method_selection_alpha_expansion_plan_summary = (
        method_selection_alpha_expansion_plan.get("summary") or {}
    )
    method_selection_alpha_expansion_batch_summary = (
        method_selection_alpha_expansion_batch.get("summary") or {}
    )
    method_selection_alpha_expansion_execution_summary = (
        method_selection_alpha_expansion_execution.get("summary") or {}
    )
    method_selection_inferential_audit_summary = (
        method_selection_inferential_audit.get("summary") or {}
    )
    method_selection_post_selection_validation_results_summary = (
        method_selection_post_selection_validation_results.get("summary") or {}
    )
    final_summary = final_selection.get("summary") or {}
    fairness_population_summary = fairness_population.get("summary") or {}
    fairness_group_diagnostic_summary = (
        fairness_group_diagnostic.get("summary") or {}
    )
    fairness_group_multiplicity_scope_summary = (
        fairness_group_multiplicity_scope.get("summary") or {}
    )
    venn_summary = venn_abers.get("summary") or {}
    venn_claim_gate_summary = venn_abers_claim_gate_matrix.get("summary") or {}
    venn_negative_summary = venn_abers_negative_disposition.get("summary") or {}
    evidence_summary = evidence_view.get("summary") or {}
    kg_graph = kg_quality.get("graph") or {}
    kg_observations = kg_quality.get("observations") or {}
    post_experiment_activation_rule = (
        post_experiment_publication_program.get("activation_rule") or {}
    )
    post_experiment_publication_author = (
        post_experiment_publication_program.get("publication_author") or {}
    )
    post_experiment_sterile_repo_plan = (
        post_experiment_publication_program.get("sterile_publication_repository_plan")
        or {}
    )
    post_experiment_completion_definition = (
        post_experiment_publication_program.get("experiment_completion_definition")
        or {}
    )
    post_experiment_reviewer_perspectives = (
        post_experiment_publication_program.get("reviewer_perspectives") or []
    )
    post_experiment_reviewer_design_gate = (
        post_experiment_publication_program.get("reviewer_design_gate") or {}
    )
    post_experiment_deliverables = (
        post_experiment_publication_program.get("deliverables") or []
    )
    post_experiment_main_article_blueprint = (
        post_experiment_publication_program.get("main_article_blueprint") or {}
    )
    post_experiment_supplementary_blueprint = (
        post_experiment_publication_program.get("supplementary_document_blueprint")
        or {}
    )
    post_experiment_site_blueprint = (
        post_experiment_publication_program.get("publication_site_blueprint") or {}
    )
    post_experiment_visual_table_audit = (
        post_experiment_publication_program.get("visual_table_audit_agent") or {}
    )
    post_experiment_triptych = (
        post_experiment_publication_program.get("publication_triptych") or {}
    )
    kg_catalog_node_count = graph_count(kg_catalog, "node_count", "declared_node_count")
    kg_catalog_edge_count = graph_count(kg_catalog, "edge_count", "declared_edge_count")
    kg_summary = {
        "status": "review" if kg_has_high_issue(kg_quality) else "pass",
        "node_count": (
            kg_catalog_node_count
            if kg_catalog_node_count is not None
            else kg_graph.get("node_count")
        ),
        "edge_count": (
            kg_catalog_edge_count
            if kg_catalog_edge_count is not None
            else kg_graph.get("edge_count")
        ),
        "observation_count": kg_observations.get("total_observation_count"),
        "observation_node_ratio": kg_observations.get("observation_node_ratio"),
    }
    requirement_statuses = {
        str(key): str(value)
        for key, value in (publication.get("requirement_statuses") or {}).items()
    }
    gates = gate_rows(requirement_statuses)
    blocked_gates = [row for row in gates if row["status"] == "blocked"]
    surfaces = surface_rows(
        evidence_view, bundle_index, publication_summary, kg_summary
    )
    main_surfaces_blocked = [
        row["surface_id"] for row in surfaces if row["status"] == "blocked"
    ]
    overall_status = (
        "paper_readiness_blocked_with_evidence_map"
        if blocked_gates
        else "paper_readiness_ready_for_extraction"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "publication_readiness_protocol": rel(protocol_path, root),
            "selection_multiplicity_protocol": rel(selection_protocol_path, root),
            "selection_multiplicity_evidence_record": rel(
                selection_evidence_path, root
            ),
            "manuscript_manifest_completeness_audit": rel(
                manifest_completeness_path, root
            ),
            "dataset_specific_final_gate_audit": rel(
                dataset_specific_final_gate_path, root
            ),
            "main_result_candidate_bundle_plan": rel(
                main_result_candidate_bundle_plan_path, root
            ),
            "main_result_candidate_bundle_results": rel(
                main_result_candidate_bundle_results_path, root
            ),
            "main_result_candidate_post_run_closure": rel(
                main_result_candidate_post_run_closure_path, root
            ),
            "method_selection_alpha_expansion_plan": rel(
                method_selection_alpha_expansion_plan_path,
                root,
            ),
            "method_selection_alpha_expansion_batch": rel(
                method_selection_alpha_expansion_batch_path,
                root,
            ),
            "method_selection_alpha_expansion_execution_audit": rel(
                method_selection_alpha_expansion_execution_path,
                root,
            ),
            "method_selection_inferential_audit": rel(
                method_selection_inferential_audit_path,
                root,
            ),
            "method_selection_post_selection_validation_results": rel(
                method_selection_post_selection_validation_results_path,
                root,
            ),
            "bounded_support_protocol": rel(bounded_support_protocol_path, root),
            "target_domain_provenance": rel(target_domain_provenance_path, root),
            "bounded_support_posthandling_validation": rel(
                bounded_support_posthandling_path, root
            ),
            "bounded_support_dataset_audit": rel(
                bounded_support_dataset_audit_path, root
            ),
            "bounded_support_endpoint_closure_audit": rel(
                bounded_support_endpoint_closure_path, root
            ),
            "bounded_support_positive_validation_protocol": rel(
                bounded_support_positive_validation_path, root
            ),
            "publication_methodology_audit": rel(publication_path, root),
            "final_selection_claim_boundary": rel(final_selection_path, root),
            "fairness_population_readiness": rel(fairness_population_path, root),
            "fairness_group_diagnostic_audit": rel(
                fairness_group_diagnostic_path, root
            ),
            "fairness_group_multiplicity_scope": rel(
                fairness_group_multiplicity_scope_path, root
            ),
            "venn_abers_validation_readiness": rel(venn_abers_path, root),
            "venn_abers_grid_ivapd_validation_protocol": rel(
                venn_abers_grid_ivapd_path,
                root,
            ),
            "venn_abers_claim_gate_matrix": rel(
                venn_abers_claim_gate_matrix_path,
                root,
            ),
            "venn_abers_negative_evidence_disposition": rel(
                venn_abers_negative_disposition_path,
                root,
            ),
            "manuscript_evidence_view": rel(evidence_view_path, root),
            "manuscript_bundle_index": rel(bundle_index_path, root),
            "knowledge_graph": rel(kg_catalog_path, root),
            "knowledge_graph_quality": rel(kg_quality_path, root),
            "post_experiment_publication_program": rel(
                post_experiment_publication_program_path,
                root,
            ),
        },
        "summary": {
            "overall_status": overall_status,
            "blocked_gate_count": len(blocked_gates),
            "gate_count": len(gates),
            "main_surface_blocked_count": len(main_surfaces_blocked),
            "claim_count": evidence_summary.get("claim_count"),
            "manifested_bundle_count": int(
                (bundle_index.get("bundle_summary") or {}).get("manifest_count")
                or len(bundle_index.get("bundles", []) or [])
            ),
            "final_selection_claim_status": final_summary.get("claim_status"),
            "publication_methodology_status": publication_summary.get("overall_status"),
            "selection_multiplicity_protocol_status": selection_protocol_summary.get(
                "overall_status"
            ),
            "selection_protocol_can_support_final_method_selection": selection_protocol_summary.get(
                "can_support_final_method_selection"
            ),
            "selection_multiplicity_evidence_record_status": selection_evidence_summary.get(
                "overall_status"
            ),
            "selection_multiplicity_evidence_record_claim_status": selection_evidence_summary.get(
                "claim_status"
            ),
            "manifest_selection_multiplicity_pass_count": manifest_completeness_summary.get(
                "selection_multiplicity_manifest_pass_count"
            ),
            "manifest_selection_multiplicity_fail_count": manifest_completeness_summary.get(
                "selection_multiplicity_manifest_fail_count"
            ),
            "manifest_selection_multiplicity_all_fields_covered": manifest_completeness_summary.get(
                "selection_multiplicity_all_fields_covered"
            ),
            "dataset_specific_final_gate_audit_status": dataset_specific_final_gate_summary.get(
                "overall_status"
            ),
            "dataset_specific_final_gate_ready_dataset_count": dataset_specific_final_gate_summary.get(
                "main_result_ready_dataset_count"
            ),
            "dataset_specific_final_gate_ready_bundle_count": dataset_specific_final_gate_summary.get(
                "main_result_ready_bundle_count"
            ),
            "main_result_candidate_bundle_plan_status": main_result_candidate_bundle_plan_summary.get(
                "overall_status"
            ),
            "main_result_candidate_dataset_count": main_result_candidate_bundle_plan_summary.get(
                "candidate_dataset_count"
            ),
            "main_result_candidate_generated_config_count": main_result_candidate_bundle_plan_summary.get(
                "generated_config_count"
            ),
            "main_result_candidate_expected_atomic_run_count": main_result_candidate_bundle_plan_summary.get(
                "expected_atomic_run_count"
            ),
            "main_result_candidate_results_status": main_result_candidate_bundle_results_summary.get(
                "overall_status"
            ),
            "main_result_candidate_completed_atomic_run_count": main_result_candidate_bundle_results_summary.get(
                "completed_atomic_run_count"
            ),
            "main_result_candidate_results_expected_atomic_run_count": main_result_candidate_bundle_results_summary.get(
                "expected_atomic_run_count"
            ),
            "main_result_candidate_results_pathology_flagged_row_count": main_result_candidate_bundle_results_summary.get(
                "pathology_flagged_row_count"
            ),
            "main_result_candidate_results_diagnostic_winner_counts": main_result_candidate_bundle_results_summary.get(
                "diagnostic_winner_counts"
            ),
            "main_result_candidate_post_run_closure_status": main_result_candidate_post_run_closure_summary.get(
                "overall_status"
            ),
            "main_result_candidate_post_run_closure_total_blocker_count": main_result_candidate_post_run_closure_summary.get(
                "total_blocker_count"
            ),
            "main_result_candidate_post_run_closure_dataset_blocked_count": main_result_candidate_post_run_closure_summary.get(
                "dataset_blocked_count"
            ),
            "main_result_candidate_post_run_closure_blocker_counts": main_result_candidate_post_run_closure_summary.get(
                "blocker_counts_by_artifact"
            ),
            "main_result_candidate_primary_consistent_dataset_count": main_result_candidate_bundle_plan_summary.get(
                "candidate_primary_consistent_dataset_count"
            ),
            "main_result_candidate_ambiguous_dataset_count": main_result_candidate_bundle_plan_summary.get(
                "ambiguous_challenger_control_dataset_count"
            ),
            "method_selection_alpha_expansion_plan_status": method_selection_alpha_expansion_plan_summary.get(
                "overall_status"
            ),
            "method_selection_alpha_expansion_additional_common_cells_needed": method_selection_alpha_expansion_plan_summary.get(
                "additional_common_cells_needed_to_clear_threshold"
            ),
            "method_selection_alpha_expansion_current_common_alpha_max_cell_share": method_selection_alpha_expansion_plan_summary.get(
                "current_common_alpha_max_cell_share"
            ),
            "method_selection_alpha_expansion_current_common_alpha_imbalance_status": method_selection_alpha_expansion_plan_summary.get(
                "current_common_alpha_imbalance_status"
            ),
            "method_selection_alpha_expansion_batch_status": method_selection_alpha_expansion_batch_summary.get(
                "overall_status"
            ),
            "method_selection_alpha_expansion_batch_reported_execution_status": method_selection_alpha_expansion_batch_summary.get(
                "execution_status"
            ),
            "method_selection_alpha_expansion_batch_generated_config_count": method_selection_alpha_expansion_batch_summary.get(
                "generated_config_count"
            ),
            "method_selection_alpha_expansion_execution_status": method_selection_alpha_expansion_execution_summary.get(
                "overall_status"
            ),
            "method_selection_alpha_expansion_observed_execution_status": method_selection_alpha_expansion_execution_summary.get(
                "observed_execution_status"
            ),
            "method_selection_alpha_expansion_active_execution_status": method_selection_alpha_expansion_execution_summary.get(
                "active_execution_status"
            ),
            "method_selection_alpha_expansion_reconciled_execution_status": method_selection_alpha_expansion_execution_summary.get(
                "reconciled_execution_status"
            ),
            "method_selection_alpha_expansion_completed_atomic_run_count": method_selection_alpha_expansion_execution_summary.get(
                "completed_atomic_run_count"
            ),
            "method_selection_alpha_expansion_expected_atomic_run_count": method_selection_alpha_expansion_execution_summary.get(
                "expected_atomic_run_count"
            ),
            "method_selection_alpha_expansion_batch_generation_label_stale_after_execution": method_selection_alpha_expansion_execution_summary.get(
                "batch_generation_label_stale_after_execution"
            ),
            "method_selection_alpha_expansion_batch_generation_label_historical_only": method_selection_alpha_expansion_execution_summary.get(
                "batch_generation_label_historical_only"
            ),
            "method_selection_alpha_expansion_batch_reported_execution_status_is_historical": method_selection_alpha_expansion_execution_summary.get(
                "batch_reported_execution_status_is_historical"
            ),
            "method_selection_alpha_expansion_batch_generation_label_reconciliation_status": method_selection_alpha_expansion_execution_summary.get(
                "batch_generation_label_reconciliation_status"
            ),
            "method_selection_alpha_expansion_batch_generation_label_requires_action": method_selection_alpha_expansion_execution_summary.get(
                "batch_generation_label_requires_action"
            ),
            "method_selection_alpha_expansion_execution_metadata_consistency_status": method_selection_alpha_expansion_execution_summary.get(
                "execution_metadata_consistency_status"
            ),
            "method_selection_inferential_audit_status": method_selection_inferential_audit_summary.get(
                "overall_status"
            ),
            "method_selection_inferential_primary_candidate_method": method_selection_inferential_audit_summary.get(
                "primary_candidate_method"
            ),
            "method_selection_inferential_bootstrap_primary_selection_rate": method_selection_inferential_audit_summary.get(
                "bootstrap_primary_selection_rate"
            ),
            "method_selection_inferential_post_selection_validation_primary_win_rate": method_selection_inferential_audit_summary.get(
                "post_selection_validation_primary_win_rate"
            ),
            "method_selection_inferential_main_result_candidate_primary_win_rate": method_selection_inferential_audit_summary.get(
                "main_result_candidate_primary_win_rate"
            ),
            "method_selection_inferential_claim_status": method_selection_inferential_audit_summary.get(
                "claim_status"
            ),
            "method_selection_post_selection_validation_results_status": method_selection_post_selection_validation_results_summary.get(
                "overall_status"
            ),
            "method_selection_post_selection_validation_completed_atomic_run_count": method_selection_post_selection_validation_results_summary.get(
                "completed_atomic_run_count"
            ),
            "method_selection_post_selection_validation_expected_atomic_run_count": method_selection_post_selection_validation_results_summary.get(
                "expected_atomic_run_count"
            ),
            "method_selection_post_selection_validation_common_dataset_alpha_cell_count": method_selection_post_selection_validation_results_summary.get(
                "common_dataset_alpha_cell_count"
            ),
            "method_selection_post_selection_validation_expected_common_dataset_alpha_cell_count": method_selection_post_selection_validation_results_summary.get(
                "expected_common_dataset_alpha_cell_count"
            ),
            "method_selection_post_selection_validation_diagnostic_winner_counts": method_selection_post_selection_validation_results_summary.get(
                "diagnostic_winner_counts"
            ),
            "bounded_support_protocol_status": bounded_support_protocol_summary.get(
                "overall_status"
            ),
            "bounded_support_protocol_can_support_validity": bounded_support_protocol_summary.get(
                "can_support_bounded_support_validity"
            ),
            "target_domain_provenance_status": target_domain_provenance_summary.get(
                "overall_status"
            ),
            "target_domain_provenance_row_count": target_domain_provenance_summary.get(
                "row_count"
            ),
            "target_domain_provenance_external_source_row_count": target_domain_provenance_summary.get(
                "external_source_row_count"
            ),
            "bounded_support_posthandling_validation_status": bounded_support_posthandling_summary.get(
                "overall_status"
            ),
            "bounded_support_posthandling_validated_bundle_count": bounded_support_posthandling_summary.get(
                "validated_bundle_count"
            ),
            "bounded_support_posthandling_unvalidated_bundle_count": bounded_support_posthandling_summary.get(
                "unvalidated_bundle_count"
            ),
            "bounded_support_dataset_audit_status": bounded_support_dataset_summary.get(
                "overall_status"
            ),
            "bounded_support_dataset_ready_bundle_count": bounded_support_dataset_summary.get(
                "bounded_support_ready_bundle_count"
            ),
            "bounded_support_dataset_endpoint_clean_bundle_count": bounded_support_dataset_summary.get(
                "endpoint_support_clean_bundle_count"
            ),
            "bounded_support_dataset_endpoint_not_applicable_bundle_count": bounded_support_dataset_summary.get(
                "endpoint_support_not_applicable_bundle_count"
            ),
            "bounded_support_dataset_endpoint_blocked_or_incomplete_bundle_count": bounded_support_dataset_summary.get(
                "endpoint_support_blocked_or_incomplete_bundle_count"
            ),
            "bounded_support_dataset_endpoint_support_status_counts": bounded_support_dataset_summary.get(
                "endpoint_support_status_counts"
            ),
            "bounded_support_dataset_natural_excursion_bundle_count": bounded_support_dataset_summary.get(
                "natural_domain_excursion_bundle_count"
            ),
            "bounded_support_endpoint_closure_status": bounded_support_endpoint_closure_summary.get(
                "overall_status"
            ),
            "bounded_support_endpoint_closure_closed_policy_bundle_count": bounded_support_endpoint_closure_summary.get(
                "closed_policy_bundle_count"
            ),
            "bounded_support_endpoint_closure_open_count_backfill_bundle_count": bounded_support_endpoint_closure_summary.get(
                "open_endpoint_count_backfill_bundle_count"
            ),
            "bounded_support_endpoint_closure_global_no_claim_bundle_count": bounded_support_endpoint_closure_summary.get(
                "global_no_claim_bundle_count"
            ),
            "bounded_support_endpoint_closure_claim_ready_bundle_count": bounded_support_endpoint_closure_summary.get(
                "bounded_support_validity_claim_ready_bundle_count"
            ),
            "bounded_support_endpoint_closure_dataset_open_count": bounded_support_endpoint_closure_summary.get(
                "dataset_open_endpoint_count_backfill_count"
            ),
            "bounded_support_positive_validation_status": bounded_support_positive_validation_summary.get(
                "overall_status"
            ),
            "bounded_support_positive_validation_action_status": bounded_support_positive_validation_summary.get(
                "action_status"
            ),
            "bounded_support_positive_validation_acceptance_failed_count": bounded_support_positive_validation_summary.get(
                "positive_acceptance_failed_count"
            ),
            "bounded_support_positive_validation_interval_score_missing_bundle_count": bounded_support_positive_validation_summary.get(
                "interval_score_metrics_missing_bundle_count"
            ),
            "bounded_support_positive_validation_claim_ready_bundle_count": bounded_support_positive_validation_summary.get(
                "positive_claim_ready_bundle_count"
            ),
            "bounded_support_positive_validation_can_support_validity": bounded_support_positive_validation_summary.get(
                "can_support_bounded_support_validity"
            ),
            "bounded_support_positive_validation_current_claim_ready": bounded_support_positive_validation_summary.get(
                "current_manuscript_bounded_support_validity_claim_ready"
            ),
            "fairness_population_readiness_status": fairness_population_summary.get(
                "overall_status"
            ),
            "fairness_population_claim_status": fairness_population_summary.get(
                "fairness_population_claim_status"
            ),
            "fairness_population_diagnostic_group_bundle_count": fairness_population_summary.get(
                "diagnostic_group_bundle_count"
            ),
            "fairness_population_ready_bundle_count": fairness_population_summary.get(
                "population_fairness_ready_bundle_count"
            ),
            "fairness_group_diagnostic_audit_status": fairness_group_diagnostic_summary.get(
                "overall_status"
            ),
            "fairness_group_diagnostic_action_status": fairness_group_diagnostic_summary.get(
                "action_status"
            ),
            "fairness_group_diagnostic_group_counts_recorded_bundle_count": fairness_group_diagnostic_summary.get(
                "group_counts_recorded_bundle_count"
            ),
            "fairness_group_diagnostic_missingness_audited_bundle_count": fairness_group_diagnostic_summary.get(
                "missingness_by_group_audited_bundle_count"
            ),
            "fairness_group_diagnostic_gap_uncertainty_recorded_bundle_count": fairness_group_diagnostic_summary.get(
                "group_gap_uncertainty_recorded_bundle_count"
            ),
            "fairness_group_multiplicity_scope_status": fairness_group_multiplicity_scope_summary.get(
                "overall_status"
            ),
            "fairness_group_multiplicity_scope_action_status": fairness_group_multiplicity_scope_summary.get(
                "action_status"
            ),
            "fairness_group_multiplicity_scope_declared_bundle_count": fairness_group_multiplicity_scope_summary.get(
                "multiplicity_scope_declared_bundle_count"
            ),
            "fairness_group_multiplicity_scope_comparison_family_count": fairness_group_multiplicity_scope_summary.get(
                "comparison_family_count"
            ),
            "fairness_group_multiplicity_scope_claim_register_cites_record": fairness_group_multiplicity_scope_summary.get(
                "claim_register_cites_multiplicity_record"
            ),
            "fairness_group_multiplicity_scope_claim_ready": fairness_group_multiplicity_scope_summary.get(
                "current_manuscript_fairness_population_claim_ready"
            ),
            "venn_abers_validation_status": venn_summary.get("overall_status"),
            "venn_abers_claim_gate_matrix_status": venn_claim_gate_summary.get(
                "overall_status"
            ),
            "venn_abers_claim_gate_positive_requirement_count": venn_claim_gate_summary.get(
                "positive_claim_requirement_count"
            ),
            "venn_abers_claim_gate_positive_pass_count": venn_claim_gate_summary.get(
                "positive_claim_pass_count"
            ),
            "venn_abers_claim_gate_positive_blocked_count": venn_claim_gate_summary.get(
                "positive_claim_blocked_count"
            ),
            "venn_abers_claim_gate_blocked_positive_requirement_ids": venn_claim_gate_summary.get(
                "blocked_positive_requirement_ids"
            ),
            "venn_abers_negative_disposition_status": venn_negative_summary.get(
                "overall_status"
            ),
            "venn_abers_negative_result_reporting_ready": venn_negative_summary.get(
                "negative_result_reporting_ready"
            ),
            "current_manuscript_positive_venn_abers_validation_required": venn_negative_summary.get(
                "current_manuscript_positive_validation_required"
            ),
            "kg_node_count": kg_summary.get("node_count"),
            "kg_edge_count": kg_summary.get("edge_count"),
            "kg_observation_count": kg_summary.get("observation_count"),
            "post_experiment_publication_program_status": post_experiment_publication_program.get(
                "status"
            ),
            "post_experiment_publication_activation_requires_zero_blocked_gates": post_experiment_activation_rule.get(
                "requires_zero_blocked_paper_gates"
            ),
            "post_experiment_publication_requires_experiment_closure_verification": post_experiment_activation_rule.get(
                "requires_experiment_closure_verification"
            ),
            "post_experiment_publication_requires_visual_table_auditor_pass": post_experiment_activation_rule.get(
                "requires_visual_table_auditor_pass"
            ),
            "post_experiment_publication_requires_author_metadata": post_experiment_activation_rule.get(
                "requires_author_metadata_for_individual_experiment_report"
            ),
            "post_experiment_publication_requires_sterile_repository_plan": post_experiment_activation_rule.get(
                "requires_sterile_publication_repository_plan"
            ),
            "post_experiment_publication_author_name": post_experiment_publication_author.get(
                "author_name"
            ),
            "post_experiment_publication_author_role": post_experiment_publication_author.get(
                "author_role"
            ),
            "post_experiment_publication_author_email_present": bool(
                post_experiment_publication_author.get("author_email")
            ),
            "post_experiment_sterile_repository_status": post_experiment_sterile_repo_plan.get(
                "status"
            ),
            "post_experiment_sterile_repository_required": (
                post_experiment_sterile_repo_plan.get("citation_target")
                == "sterile_publication_repository"
            ),
            "post_experiment_working_repository_final_citable": (
                post_experiment_sterile_repo_plan.get(
                    "working_repository_citation_status"
                )
                != "not_final_citable_repository"
            )
            if post_experiment_sterile_repo_plan
            else None,
            "post_experiment_sterile_repository_required_content_count": len(
                post_experiment_sterile_repo_plan.get("required_contents") or []
            ),
            "post_experiment_sterile_repository_exclusion_rule_count": len(
                post_experiment_sterile_repo_plan.get("exclusion_rules") or []
            ),
            "post_experiment_completion_closure_check_count": len(
                post_experiment_completion_definition.get("closure_checks") or []
            ),
            "post_experiment_publication_reviewer_perspective_count": len(
                post_experiment_reviewer_perspectives
            ),
            "post_experiment_publication_reviewer_design_required_pass_count": post_experiment_reviewer_design_gate.get(
                "required_reviewer_pass_count"
            ),
            "post_experiment_publication_minimum_recommendations_per_reviewer": post_experiment_reviewer_design_gate.get(
                "minimum_structured_recommendations_per_reviewer"
            ),
            "post_experiment_publication_advice_schema_field_count": len(
                post_experiment_reviewer_design_gate.get("advice_record_schema") or []
            ),
            "post_experiment_publication_required_advice_topic_count": len(
                post_experiment_reviewer_design_gate.get("required_advice_topics")
                or []
            ),
            "post_experiment_publication_reviewer_design_procedure_count": len(
                post_experiment_reviewer_design_gate.get("procedure") or []
            ),
            "post_experiment_publication_deliverable_count": len(
                post_experiment_deliverables
            ),
            "post_experiment_main_article_section_count": len(
                post_experiment_main_article_blueprint.get("sections") or []
            ),
            "post_experiment_supplementary_section_count": len(
                post_experiment_supplementary_blueprint.get("sections") or []
            ),
            "post_experiment_publication_site_component_count": len(
                post_experiment_site_blueprint.get("components") or []
            ),
            "post_experiment_visual_table_quality_check_count": len(
                post_experiment_visual_table_audit.get("quality_checks") or []
            ),
            "post_experiment_visual_table_scope_count": len(
                post_experiment_visual_table_audit.get("scope") or []
            ),
            "post_experiment_visual_table_feedback_loop_step_count": len(
                post_experiment_visual_table_audit.get("feedback_loop") or []
            ),
            "post_experiment_visual_table_required_artifact_count": len(
                post_experiment_visual_table_audit.get("required_output_artifacts")
                or []
            ),
            "post_experiment_publication_triptych_component_count": len(
                post_experiment_triptych.get("components") or []
            ),
        },
        "claim_boundaries": [
            "This map is a drafting control artifact, not a result table.",
            "A blocked gate means paper prose must not promote the associated final claim.",
            "Caveated robustness and negative-result surfaces can be drafted only inside their explicit claim-register scope.",
            "The post-experiment publication program is deferred until all paper gates and KG publication-readiness checks pass.",
        ],
        "blocked_gates": blocked_gates,
        "paper_surfaces": surfaces,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Paper Readiness Map",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Blocked gates: {summary['blocked_gate_count']} / {summary['gate_count']}",
        f"- Blocked main surfaces: {summary['main_surface_blocked_count']}",
        f"- Claim count: {summary['claim_count']}",
        f"- Manifested bundles: {summary['manifested_bundle_count']}",
        f"- Publication methodology status: `{summary['publication_methodology_status']}`",
        f"- Selection/multiplicity protocol status: `{summary['selection_multiplicity_protocol_status']}`",
        f"- Selection/multiplicity evidence record status: `{summary['selection_multiplicity_evidence_record_status']}`",
        f"- Manifest selection/multiplicity coverage: {summary['manifest_selection_multiplicity_pass_count']} pass / {summary['manifest_selection_multiplicity_fail_count']} fail; all fields covered `{summary['manifest_selection_multiplicity_all_fields_covered']}`",
        f"- Dataset-specific final gate audit status: `{summary['dataset_specific_final_gate_audit_status']}` with {summary['dataset_specific_final_gate_ready_dataset_count']} ready datasets and {summary['dataset_specific_final_gate_ready_bundle_count']} ready bundles",
        f"- Main-result candidate bundle plan: `{summary['main_result_candidate_bundle_plan_status']}` with {summary['main_result_candidate_dataset_count']} candidate datasets, {summary['main_result_candidate_generated_config_count']} generated configs, and {summary['main_result_candidate_expected_atomic_run_count']} expected atomic runs",
        f"- Main-result candidate bundle results: `{summary['main_result_candidate_results_status']}` with {summary['main_result_candidate_completed_atomic_run_count']} / {summary['main_result_candidate_results_expected_atomic_run_count']} completed rows",
        f"- Main-result candidate post-run closure: `{summary['main_result_candidate_post_run_closure_status']}` with {summary['main_result_candidate_post_run_closure_total_blocker_count']} blockers",
        f"- Method-selection alpha expansion plan: `{summary['method_selection_alpha_expansion_plan_status']}` with {summary['method_selection_alpha_expansion_additional_common_cells_needed']} additional common alpha cells needed and max alpha share {summary['method_selection_alpha_expansion_current_common_alpha_max_cell_share']}",
        f"- Method-selection alpha expansion execution: `{summary['method_selection_alpha_expansion_execution_status']}` with active status `{summary['method_selection_alpha_expansion_active_execution_status']}`, reconciled status `{summary['method_selection_alpha_expansion_reconciled_execution_status']}`, and {summary['method_selection_alpha_expansion_completed_atomic_run_count']} / {summary['method_selection_alpha_expansion_expected_atomic_run_count']} completed rows",
        f"- Method-selection alpha expansion batch-label reconciliation: `{summary['method_selection_alpha_expansion_batch_generation_label_reconciliation_status']}`; historical `{summary['method_selection_alpha_expansion_batch_generation_label_historical_only']}`; action required `{summary['method_selection_alpha_expansion_batch_generation_label_requires_action']}`; metadata `{summary['method_selection_alpha_expansion_execution_metadata_consistency_status']}`",
        f"- Method-selection inferential audit: `{summary['method_selection_inferential_audit_status']}` with primary `{summary['method_selection_inferential_primary_candidate_method']}`, bootstrap selection rate {summary['method_selection_inferential_bootstrap_primary_selection_rate']}, fresh-seed validation win rate {summary['method_selection_inferential_post_selection_validation_primary_win_rate']}, and claim status `{summary['method_selection_inferential_claim_status']}`",
        f"- Method-selection post-selection validation: `{summary['method_selection_post_selection_validation_results_status']}` with {summary['method_selection_post_selection_validation_completed_atomic_run_count']} / {summary['method_selection_post_selection_validation_expected_atomic_run_count']} completed rows and {summary['method_selection_post_selection_validation_common_dataset_alpha_cell_count']} / {summary['method_selection_post_selection_validation_expected_common_dataset_alpha_cell_count']} common dataset-alpha cells",
        f"- Bounded-support protocol status: `{summary['bounded_support_protocol_status']}`",
        f"- Target-domain provenance status: `{summary['target_domain_provenance_status']}` over {summary['target_domain_provenance_row_count']} rows",
        f"- Bounded-support post-handling validation status: `{summary['bounded_support_posthandling_validation_status']}` with {summary['bounded_support_posthandling_validated_bundle_count']} validated bundles",
        f"- Bounded-support dataset audit status: `{summary['bounded_support_dataset_audit_status']}` with {summary['bounded_support_dataset_ready_bundle_count']} ready bundles",
        f"- Bounded-support endpoint support split: {summary['bounded_support_dataset_endpoint_clean_bundle_count']} clean, {summary['bounded_support_dataset_endpoint_not_applicable_bundle_count']} not applicable, {summary['bounded_support_dataset_endpoint_blocked_or_incomplete_bundle_count']} blocked/incomplete",
        f"- Bounded-support endpoint closure audit: `{summary['bounded_support_endpoint_closure_status']}` with {summary['bounded_support_endpoint_closure_closed_policy_bundle_count']} closed policy bundles, {summary['bounded_support_endpoint_closure_open_count_backfill_bundle_count']} endpoint-count backfill bundle, and {summary['bounded_support_endpoint_closure_claim_ready_bundle_count']} bounded-support claim-ready bundles",
        f"- Bounded-support positive validation protocol: `{summary['bounded_support_positive_validation_status']}` action `{summary['bounded_support_positive_validation_action_status']}` with {summary['bounded_support_positive_validation_claim_ready_bundle_count']} claim-ready bundles and {summary['bounded_support_positive_validation_acceptance_failed_count']} failed positive acceptance criteria",
        f"- Fairness/population readiness status: `{summary['fairness_population_readiness_status']}` with {summary['fairness_population_ready_bundle_count']} ready bundles",
        f"- Fairness group diagnostic audit: `{summary['fairness_group_diagnostic_audit_status']}` with {summary['fairness_group_diagnostic_group_counts_recorded_bundle_count']} group-count bundles, {summary['fairness_group_diagnostic_missingness_audited_bundle_count']} missingness-audited bundles, and {summary['fairness_group_diagnostic_gap_uncertainty_recorded_bundle_count']} gap-uncertainty bundles",
        f"- Fairness group multiplicity scope: `{summary['fairness_group_multiplicity_scope_status']}` with {summary['fairness_group_multiplicity_scope_declared_bundle_count']} scoped bundles, {summary['fairness_group_multiplicity_scope_comparison_family_count']} comparison families, claim-register citation `{summary['fairness_group_multiplicity_scope_claim_register_cites_record']}`, and fairness claim ready `{summary['fairness_group_multiplicity_scope_claim_ready']}`",
        f"- Venn-Abers validation status: `{summary['venn_abers_validation_status']}`",
        f"- Venn-Abers claim gate matrix: `{summary['venn_abers_claim_gate_matrix_status']}` with {summary['venn_abers_claim_gate_positive_pass_count']} / {summary['venn_abers_claim_gate_positive_requirement_count']} positive-claim requirements passing",
        f"- KG nodes / edges / observations: {summary['kg_node_count']} / {summary['kg_edge_count']} / {summary['kg_observation_count']}",
        f"- Post-experiment publication program: `{summary['post_experiment_publication_program_status']}` with {summary['post_experiment_publication_reviewer_perspective_count']} reviewer perspectives and {summary['post_experiment_publication_deliverable_count']} deliverables",
        f"- Post-experiment activation controls: {summary['post_experiment_completion_closure_check_count']} experiment-closure checks, visual auditor pass required `{summary['post_experiment_publication_requires_visual_table_auditor_pass']}`",
        f"- Post-experiment author standard: `{summary['post_experiment_publication_author_name']}` / `{summary['post_experiment_publication_author_role']}`, email present `{summary['post_experiment_publication_author_email_present']}`",
        f"- Post-experiment sterile repository: `{summary['post_experiment_sterile_repository_status']}`, sterile repo required `{summary['post_experiment_sterile_repository_required']}`, working repo final-citable `{summary['post_experiment_working_repository_final_citable']}`",
        f"- Post-experiment reviewer design gate: {summary['post_experiment_publication_reviewer_design_required_pass_count']} reviewer passes, at least {summary['post_experiment_publication_minimum_recommendations_per_reviewer']} structured recommendations each, {summary['post_experiment_publication_required_advice_topic_count']} required advice topics",
        f"- Post-experiment blueprints: {summary['post_experiment_main_article_section_count']} main-article sections, {summary['post_experiment_supplementary_section_count']} supplementary sections, {summary['post_experiment_publication_site_component_count']} site components",
        f"- Post-experiment triptych: {summary['post_experiment_publication_triptych_component_count']} coordinated publication surfaces",
        f"- Post-experiment visual/table audit: {summary['post_experiment_visual_table_quality_check_count']} checks, {summary['post_experiment_visual_table_scope_count']} scoped artifact classes, {summary['post_experiment_visual_table_feedback_loop_step_count']} feedback-loop steps, and {summary['post_experiment_visual_table_required_artifact_count']} required artifacts",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Blocked Gates",
            "",
            "| Gate | Status | Paper risk | Closure standard |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["blocked_gates"]:
        lines.append(
            "| "
            f"`{row['gate_id']}` | "
            f"`{row['status']}` | "
            f"{row['paper_risk']} | "
            f"{row['closure_standard']} |"
        )
    lines.extend(
        [
            "",
            "## Next Actions",
            "",
        ]
    )
    for row in payload["blocked_gates"]:
        lines.append(f"### `{row['gate_id']}`")
        for action in row["next_actions"]:
            lines.append(f"- {action}")
        lines.append("")
    lines.extend(
        [
            "## Paper Surfaces",
            "",
            "| Surface | Status | Blocking gates | Evidence |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["paper_surfaces"]:
        blockers = ", ".join(f"`{gate}`" for gate in row["blocking_gates"]) or "none"
        lines.append(
            "| "
            f"`{row['surface_id']}` | "
            f"`{row['status']}` | "
            f"{blockers} | "
            f"{row['evidence']} |"
        )
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
