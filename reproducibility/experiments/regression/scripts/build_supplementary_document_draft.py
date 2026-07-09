"""Build the evidence-linked supplementary document draft.

The output is a draft supplement assembled from existing audited artifacts. It
does not run experiments, does not authorize release, and does not promote any
conformal method as a final recommendation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_supplementary_document_draft_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/supplementary_document_draft.md"
)
DEFAULT_JSON_OUT = Path(
    "experiments/regression/manuscript/supplementary_document_draft.json"
)
AUTHOR_NAME = "Emre Tasar"
AUTHOR_ROLE = "Data Scientist"
AUTHOR_EMAIL = "detasar@gmail.com"

MAIN_ARTICLE = Path("experiments/regression/manuscript/main_article_draft.json")
INDIVIDUAL_REPORT = Path(
    "experiments/regression/manuscript/individual_experiment_report_draft.json"
)
ARTICLE_BLUEPRINT = Path(
    "experiments/regression/manuscript/article_supplement_blueprint_alignment.json"
)
ROBUSTNESS = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "method_selection_robustness_audit.json"
)
INFERENTIAL = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "method_selection_inferential_audit.json"
)
POST_SELECTION = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "method_selection_post_selection_validation_results.json"
)
POST_SELECTION_BRIDGE = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "dataset_final_gate_post_selection_validation_bridge_results.json"
)
BOUNDED_ENDPOINT = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "bounded_support_endpoint_closure_audit.json"
)
BOUNDED_PROTOCOL = Path(
    "experiments/regression/manuscript/bounded_support_positive_validation_protocol.json"
)
FAIRNESS_GROUP = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "fairness_group_diagnostic_audit.json"
)
FAIRNESS_POPULATION = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "fairness_population_readiness_audit.json"
)
FAIRNESS_MULTIPLICITY = Path(
    "experiments/regression/manuscript/fairness_group_multiplicity_scope.json"
)
DUPLICATE_CLOSURE = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "duplicate_sensitivity_closure_audit.json"
)
DUPLICATE_QUARANTINE = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "duplicate_content_quarantine_audit.json"
)
CROSS_RUN = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "cross_run_integrity_audit.json"
)
CITATION_REGISTRY = Path(
    "experiments/regression/manuscript/publication_citation_registry.json"
)
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
CQR_MODEL_MATCHED_SYNTHESIS = Path(
    "experiments/regression/reports/model_matched_cqr_rerun_plan/"
    "cqr_fixed_vs_model_matched_synthesis.json"
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
    full = root / path
    if not full.exists():
        return {}
    return json.loads(full.read_text(encoding="utf-8"))


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
        return f"{value:.{digits}f}"
    if value is None:
        return "n/a"
    return str(value)


def count_text(value: Any) -> str:
    if not isinstance(value, dict):
        return fmt(value)
    return "; ".join(f"{key}={fmt(value[key])}" for key in sorted(value))


def ci_text(value: Any) -> str:
    if not isinstance(value, dict):
        return "n/a"
    low = value.get("low")
    high = value.get("high")
    if low is None or high is None:
        return "n/a"
    return f"{fmt(low)} to {fmt(high)}"


def citation_keys(payload: dict[str, Any]) -> dict[str, str]:
    return {row["url"]: row["citation_key"] for row in payload.get("citation_rows", [])}


def required_citation_urls() -> list[str]:
    return [
        "https://arxiv.org/abs/1604.04173",
        "https://arxiv.org/abs/1904.06019",
        "https://arxiv.org/abs/1905.02928",
        "https://arxiv.org/abs/1905.03222",
        "https://arxiv.org/abs/2002.09025",
        "https://arxiv.org/html/2605.06646v1",
        "https://proceedings.mlr.press/v91/nouretdinov18a.html",
        "https://proceedings.mlr.press/v230/nouretdinov24a.html",
        "https://proceedings.mlr.press/v267/van-der-laan25a.html",
    ]


def build_payload(root: Path) -> dict[str, Any]:
    main_article = read_json(root, MAIN_ARTICLE)
    individual = read_json(root, INDIVIDUAL_REPORT)
    blueprint = read_json(root, ARTICLE_BLUEPRINT)
    robustness = read_json(root, ROBUSTNESS)
    inferential = read_json(root, INFERENTIAL)
    post_selection = read_json(root, POST_SELECTION)
    post_selection_bridge = read_json(root, POST_SELECTION_BRIDGE)
    bounded_endpoint = read_json(root, BOUNDED_ENDPOINT)
    bounded_protocol = read_json(root, BOUNDED_PROTOCOL)
    fairness_group = read_json(root, FAIRNESS_GROUP)
    fairness_population = read_json(root, FAIRNESS_POPULATION)
    fairness_multiplicity = read_json(root, FAIRNESS_MULTIPLICITY)
    duplicate_closure = read_json(root, DUPLICATE_CLOSURE)
    duplicate_quarantine = read_json(root, DUPLICATE_QUARANTINE)
    cross_run = read_json(root, CROSS_RUN)
    citations = read_json(root, CITATION_REGISTRY)
    kg_quality = read_json(root, KG_QUALITY)
    cqr_model_matched = read_json(root, CQR_MODEL_MATCHED_SYNTHESIS)

    sources = {
        "main_article_draft": str(MAIN_ARTICLE),
        "individual_experiment_report_draft": str(INDIVIDUAL_REPORT),
        "article_supplement_blueprint_alignment": str(ARTICLE_BLUEPRINT),
        "method_selection_robustness_audit": str(ROBUSTNESS),
        "method_selection_inferential_audit": str(INFERENTIAL),
        "method_selection_post_selection_validation_results": str(POST_SELECTION),
        "dataset_final_gate_post_selection_validation_bridge_results": str(
            POST_SELECTION_BRIDGE
        ),
        "bounded_support_endpoint_closure_audit": str(BOUNDED_ENDPOINT),
        "bounded_support_positive_validation_protocol": str(BOUNDED_PROTOCOL),
        "fairness_group_diagnostic_audit": str(FAIRNESS_GROUP),
        "fairness_population_readiness_audit": str(FAIRNESS_POPULATION),
        "fairness_group_multiplicity_scope": str(FAIRNESS_MULTIPLICITY),
        "duplicate_sensitivity_closure_audit": str(DUPLICATE_CLOSURE),
        "duplicate_content_quarantine_audit": str(DUPLICATE_QUARANTINE),
        "cross_run_integrity_audit": str(CROSS_RUN),
        "publication_citation_registry": str(CITATION_REGISTRY),
        "knowledge_graph_quality_summary": str(KG_QUALITY),
        "cqr_fixed_vs_model_matched_synthesis": str(CQR_MODEL_MATCHED_SYNTHESIS),
    }

    supplement_rows = [
        row
        for row in blueprint.get("alignment_rows") or []
        if row.get("recommended_surface") == "supplement_candidate_after_final_prose_gate"
    ]
    missing_sources = [path for path in sources.values() if not (root / path).exists()]
    blueprint_missing_rows = [
        row.get("content_area_id")
        for row in supplement_rows
        if row.get("missing_source_artifacts")
        or row.get("source_traceability_status") != "pass"
    ]
    cite = citation_keys(citations)
    missing_citations = [url for url in required_citation_urls() if url not in cite]

    robust_s = robustness.get("summary") or {}
    inferential_s = inferential.get("summary") or {}
    post_s = post_selection.get("summary") or {}
    bridge_s = post_selection_bridge.get("summary") or {}
    bounded_s = bounded_endpoint.get("summary") or {}
    bounded_protocol_s = bounded_protocol.get("summary") or {}
    fairness_group_s = fairness_group.get("summary") or {}
    fairness_population_s = fairness_population.get("summary") or {}
    fairness_multiplicity_s = fairness_multiplicity.get("summary") or {}
    duplicate_s = duplicate_closure.get("summary") or {}
    quarantine_s = duplicate_quarantine.get("summary") or {}
    cross_s = cross_run.get("summary") or {}
    cqr_model_matched_s = cqr_model_matched.get("summary") or {}
    cqr_backend_counts = (
        cqr_model_matched_s.get("coverage_eligible_interval_score_selected_counts")
        or {}
    )
    main_s = main_article.get("summary") or {}
    individual_s = individual.get("summary") or {}
    kg_graph = kg_quality.get("graph") or {}

    supplement_sections = [
        {
            "section_id": "method_selection_robustness",
            "heading": "S1. Method Selection Robustness Diagnostics",
            "role": "selection_robustness_diagnostic_no_final_selection",
            "claim_boundary": "Robustness diagnostic only; final selection remains blocked.",
            "evidence_sources": [
                "method_selection_robustness_audit",
                "method_selection_inferential_audit",
                "publication_citation_registry",
                "cqr_fixed_vs_model_matched_synthesis",
            ],
        },
        {
            "section_id": "post_selection_validation",
            "heading": "S2. Post-Selection Validation Diagnostics",
            "role": "post_selection_diagnostic_no_final_selection",
            "claim_boundary": "Post-selection validation evidence is no-final-selection evidence.",
            "evidence_sources": [
                "method_selection_post_selection_validation_results",
                "dataset_final_gate_post_selection_validation_bridge_results",
            ],
        },
        {
            "section_id": "bounded_support_endpoint_policy",
            "heading": "S3. Bounded-Support Endpoint Policy",
            "role": "bounded_support_endpoint_blocker_no_validity_claim",
            "claim_boundary": "No bounded-support validity claim is supported.",
            "evidence_sources": [
                "bounded_support_endpoint_closure_audit",
                "bounded_support_positive_validation_protocol",
                "publication_citation_registry",
            ],
        },
        {
            "section_id": "fairness_group_diagnostics",
            "heading": "S4. Fairness Group Diagnostics",
            "role": "fairness_group_diagnostic_no_population_claim",
            "claim_boundary": "Diagnostic group comparison only; no population fairness claim.",
            "evidence_sources": [
                "fairness_group_diagnostic_audit",
                "fairness_population_readiness_audit",
                "fairness_group_multiplicity_scope",
            ],
        },
        {
            "section_id": "duplicate_integrity_caveats",
            "heading": "S5. Duplicate And Integrity Caveats",
            "role": "integrity_caveat_inventory_no_claim_strengthening",
            "claim_boundary": "Integrity caveats are retained and do not strengthen claims.",
            "evidence_sources": [
                "duplicate_sensitivity_closure_audit",
                "duplicate_content_quarantine_audit",
                "cross_run_integrity_audit",
            ],
        },
        {
            "section_id": "traceability_and_release",
            "heading": "S6. Traceability And Release State",
            "role": "source_traceability_release_blocked",
            "claim_boundary": "The supplement is a draft component; release remains blocked.",
            "evidence_sources": [
                "main_article_draft",
                "individual_experiment_report_draft",
                "article_supplement_blueprint_alignment",
                "knowledge_graph_quality_summary",
            ],
        },
    ]
    supplement_reader_crosswalk = [
        {
            "main_article_surface": "CQR/CV+ descriptive performance",
            "supplement_support": "S1 robustness diagnostics, S1b CQR backend sensitivity, and S2 post-selection diagnostics",
            "primary_evidence_source": "method_selection_robustness_audit; cqr_fixed_vs_model_matched_synthesis",
            "closed_claim": "No final method selection, global best method, or deployment recommendation.",
        },
        {
            "main_article_surface": "Venn-Abers bridge negative evidence",
            "supplement_support": "S2 bridge validation slice and S6 release-state boundary",
            "primary_evidence_source": "dataset_final_gate_post_selection_validation_bridge_results",
            "closed_claim": "No validated Venn-Abers regression interval claim.",
        },
        {
            "main_article_surface": "Bounded-support validity",
            "supplement_support": "S3 bounded-support endpoint policy",
            "primary_evidence_source": "bounded_support_endpoint_closure_audit",
            "closed_claim": "No endpoint or bounded-support validity claim.",
        },
        {
            "main_article_surface": "Population fairness",
            "supplement_support": "S4 fairness group diagnostics",
            "primary_evidence_source": "fairness_population_readiness_audit",
            "closed_claim": "No population fairness claim.",
        },
        {
            "main_article_surface": "Duplicate and leakage integrity",
            "supplement_support": "S5 duplicate and integrity caveats",
            "primary_evidence_source": "cross_run_integrity_audit",
            "closed_claim": "No claim strengthening by hiding duplicate or split-integrity caveats.",
        },
        {
            "main_article_surface": "Knowledge-graph traceability and release state",
            "supplement_support": "S6 traceability and release state",
            "primary_evidence_source": "knowledge_graph_quality_summary",
            "closed_claim": "No public citable KG/site/repository release.",
        },
    ]
    supplement_reading_protocol_rows = [
        {
            "section_id": "S1",
            "reader_check": "Check whether the method-selection signal is robust enough to describe, but not promote.",
            "evidence_metric": (
                "CQR common-cell wins 58 of 94 cells; bootstrap selection count "
                "is cqr=1,000."
            ),
            "allowed_use": "Report CQR/CV+ as strong practical candidates observed in these experiments.",
            "blocked_use": "Do not call CQR the final selected method or a universal recommendation.",
        },
        {
            "section_id": "S1b",
            "reader_check": "Check whether CQR's signal survives a backend-confound diagnostic.",
            "evidence_metric": (
                "Model-matched CQR completed "
                f"{fmt(cqr_model_matched_s.get('model_matched_cqr_completed_rows'))} "
                "rows; paired cells="
                f"{fmt(cqr_model_matched_s.get('paired_cell_count'))}; selected "
                "cells are fixed_gbm_cqr="
                f"{fmt(cqr_backend_counts.get('fixed_gbm_cqr'))}, "
                "model_matched_cqr="
                f"{fmt(cqr_backend_counts.get('model_matched_cqr'))}, "
                "neither="
                f"{fmt(cqr_backend_counts.get('no_coverage_eligible_variant'))}."
            ),
            "allowed_use": "Use as a backend sensitivity check for the experiment-scoped CQR signal.",
            "blocked_use": "Do not upgrade the check into a universal CQR method recommendation.",
        },
        {
            "section_id": "S2",
            "reader_check": "Check whether post-selection and bridge diagnostics preserve the same boundary.",
            "evidence_metric": (
                "Post-selection diagnostic counts are cqr=18 and mondrian_abs=7; "
                "the bridge slice has 45 completed atomic runs."
            ),
            "allowed_use": "Use the slice as diagnostic stress-test evidence.",
            "blocked_use": "Do not upgrade the slice into final method selection or validated Venn-Abers regression intervals.",
        },
        {
            "section_id": "S3",
            "reader_check": "Check whether bounded-support endpoint behavior authorizes a validity claim.",
            "evidence_metric": (
                "0 bounded-support-validity-ready bundles and 11 raw "
                "endpoint-excursion bundles."
            ),
            "allowed_use": "Report endpoint policy closure and retained domain caveats.",
            "blocked_use": "Do not state bounded-support or endpoint validity.",
        },
        {
            "section_id": "S4",
            "reader_check": "Check whether group diagnostics define a population-fairness estimand.",
            "evidence_metric": (
                "187 pairwise group comparisons, 0 population-fairness-ready "
                "bundles, and 0 population-estimand-declared bundles."
            ),
            "allowed_use": "Use group rows as heterogeneity diagnostics.",
            "blocked_use": "Do not state population fairness or deployment fairness.",
        },
        {
            "section_id": "S5",
            "reader_check": "Check whether duplicate and leakage controls strengthen or limit interpretation.",
            "evidence_metric": (
                "29 duplicate actions, 46 quarantined actions, 0 unquarantined "
                "actions, and hard leakage not detected in scanned artifacts."
            ),
            "allowed_use": "Retain integrity caveats as part of the scientific record.",
            "blocked_use": "Do not hide caveats to make the empirical result look cleaner.",
        },
        {
            "section_id": "S6",
            "reader_check": "Check whether traceability artifacts are review infrastructure or public outputs.",
            "evidence_metric": (
                f"{fmt(kg_graph.get('node_count'))} KG nodes, "
                f"{fmt(kg_graph.get('edge_count'))} edges, "
                f"{fmt(kg_graph.get('isolated_node_count'))} isolated nodes, "
                "and release authorization false."
            ),
            "allowed_use": "Use the KG and package for private claim tracing.",
            "blocked_use": "Do not cite, publish, or deploy the KG/site before explicit authorization.",
        },
    ]

    checks = [
        {
            "check_id": "source_artifacts_present",
            "status": "pass" if not missing_sources else "fail",
            "evidence": {"missing_sources": missing_sources},
        },
        {
            "check_id": "supplement_blueprint_rows_traceable",
            "status": (
                "pass"
                if len(supplement_rows) == 5 and not blueprint_missing_rows
                else "fail"
            ),
            "evidence": {
                "supplement_blueprint_row_count": len(supplement_rows),
                "blueprint_rows_with_missing_or_untraced_sources": blueprint_missing_rows,
            },
        },
        {
            "check_id": "required_citations_registered",
            "status": "pass" if not missing_citations else "fail",
            "evidence": {"missing_citations": missing_citations},
        },
        {
            "check_id": "draft_remains_neutral_and_unreleased",
            "status": "pass",
            "evidence": {
                "final_manuscript_prose_permission": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "positive_claim_promotion_authorized": False,
                "release_authorized": False,
            },
        },
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]

    summary = {
        "overall_status": (
            "supplementary_document_draft_ready"
            if not failed_checks
            else "supplementary_document_draft_blocked"
        ),
        "draft_not_final": True,
        "author_name": AUTHOR_NAME,
        "author_role": AUTHOR_ROLE,
        "author_email": AUTHOR_EMAIL,
        "author_header": f"Author: {AUTHOR_NAME}, {AUTHOR_ROLE}",
        "publication_completed_rows": main_s.get(
            "publication_completed_rows", individual_s.get("publication_completed_rows")
        ),
        "dataset_count": main_s.get("dataset_count", individual_s.get("dataset_count")),
        "dataset_alpha_cell_count": main_s.get(
            "dataset_alpha_cell_count", individual_s.get("dataset_alpha_cell_count")
        ),
        "method_count": main_s.get("method_count", individual_s.get("method_count")),
        "supplement_blueprint_row_count": len(supplement_rows),
        "supplement_section_count": len(supplement_sections),
        "supplement_reader_crosswalk_row_count": len(supplement_reader_crosswalk),
        "supplement_reading_protocol_row_count": len(supplement_reading_protocol_rows),
        "candidate_method_count": robust_s.get("candidate_method_count"),
        "candidate_methods": robust_s.get("candidate_methods"),
        "common_dataset_alpha_cell_count": robust_s.get(
            "common_dataset_alpha_cell_count"
        ),
        "common_cell_selected_method": robust_s.get("common_cell_selected_method"),
        "common_cell_primary_win_count": robust_s.get("common_cell_primary_win_count"),
        "common_cell_winner_counts": robust_s.get("common_cell_winner_counts"),
        "bootstrap_replicates": robust_s.get("bootstrap_replicates"),
        "bootstrap_selection_counts": robust_s.get("bootstrap_selection_counts"),
        "bootstrap_primary_selection_rate": robust_s.get(
            "bootstrap_primary_selection_rate"
        ),
        "bootstrap_primary_selection_rate_ci95": inferential_s.get(
            "bootstrap_primary_selection_rate_ci95"
        ),
        "leave_one_dataset_primary_retention_rate": robust_s.get(
            "leave_one_dataset_primary_retention_rate"
        ),
        "leave_one_alpha_primary_retention_rate": robust_s.get(
            "leave_one_alpha_primary_retention_rate"
        ),
        "final_selection_claim_status": robust_s.get("final_selection_claim_status"),
        "cqr_backend_sensitivity_status": cqr_model_matched_s.get("status"),
        "cqr_backend_sensitivity_fixed_gbm_completed_rows": (
            cqr_model_matched_s.get("fixed_gbm_cqr_completed_rows")
        ),
        "cqr_backend_sensitivity_model_matched_completed_rows": (
            cqr_model_matched_s.get("model_matched_cqr_completed_rows")
        ),
        "cqr_backend_sensitivity_paired_cell_count": (
            cqr_model_matched_s.get("paired_cell_count")
        ),
        "cqr_backend_sensitivity_selected_counts": cqr_backend_counts,
        "cqr_backend_sensitivity_can_support_method_winner_claim": (
            cqr_model_matched_s.get("can_support_method_winner_claim")
        ),
        "inferential_candidate_min_shared_pairwise_cell_count": inferential_s.get(
            "candidate_min_shared_pairwise_cell_count"
        ),
        "inferential_pairwise_comparison_count": inferential_s.get(
            "candidate_pairwise_comparison_count"
        ),
        "main_result_candidate_primary_win_rate": inferential_s.get(
            "main_result_candidate_primary_win_rate"
        ),
        "main_result_candidate_primary_win_rate_ci95": inferential_s.get(
            "main_result_candidate_primary_win_rate_ci95"
        ),
        "robustness_common_cell_primary_win_rate": inferential_s.get(
            "robustness_common_cell_primary_win_rate"
        ),
        "robustness_common_cell_primary_win_rate_ci95": inferential_s.get(
            "robustness_common_cell_primary_win_rate_ci95"
        ),
        "post_selection_validation_primary_win_rate": inferential_s.get(
            "post_selection_validation_primary_win_rate"
        ),
        "post_selection_validation_primary_win_rate_ci95": inferential_s.get(
            "post_selection_validation_primary_win_rate_ci95"
        ),
        "post_selection_dataset_count": post_s.get("dataset_count"),
        "post_selection_common_dataset_alpha_cell_count": post_s.get(
            "common_dataset_alpha_cell_count"
        ),
        "post_selection_completed_atomic_run_count": post_s.get(
            "completed_atomic_run_count"
        ),
        "post_selection_diagnostic_winner_counts": post_s.get(
            "diagnostic_winner_counts"
        ),
        "post_selection_feature_leakage_violation_count": post_s.get(
            "feature_leakage_violation_count"
        ),
        "post_selection_width_pathology_row_count": post_s.get(
            "width_pathology_row_count"
        ),
        "bridge_validation_dataset_count": bridge_s.get("dataset_count"),
        "bridge_validation_completed_atomic_run_count": bridge_s.get(
            "completed_atomic_run_count"
        ),
        "bridge_validation_diagnostic_winner_counts": bridge_s.get(
            "diagnostic_winner_counts"
        ),
        "venn_undercoverage_run_count": main_s.get("venn_undercoverage_run_count"),
        "bounded_bundle_count": bounded_s.get("bundle_count"),
        "bounded_dataset_count": bounded_s.get("dataset_count"),
        "bounded_raw_endpoint_excursion_bundle_count": bounded_s.get(
            "raw_endpoint_excursion_bundle_count"
        ),
        "bounded_posthandling_validated_bundle_count": bounded_s.get(
            "posthandling_validated_bundle_count"
        ),
        "bounded_endpoint_clean_or_not_applicable_bundle_count": bounded_s.get(
            "endpoint_clean_or_not_applicable_bundle_count"
        ),
        "bounded_support_validity_ready_bundle_count": bounded_s.get(
            "bounded_support_validity_claim_ready_bundle_count"
        ),
        "bounded_positive_claim_ready_bundle_count": bounded_protocol_s.get(
            "positive_claim_ready_bundle_count"
        ),
        "bounded_endpoint_support_status_counts": bounded_s.get(
            "endpoint_support_status_counts"
        ),
        "fairness_bundle_count": fairness_group_s.get("bundle_count"),
        "fairness_dataset_count": fairness_group_s.get("dataset_count"),
        "fairness_bootstrap_replicates": fairness_group_s.get("bootstrap_replicates"),
        "fairness_group_counts_recorded_bundle_count": fairness_group_s.get(
            "group_counts_recorded_bundle_count"
        ),
        "fairness_coverage_by_group_recorded_bundle_count": fairness_group_s.get(
            "coverage_by_group_recorded_bundle_count"
        ),
        "fairness_width_by_group_recorded_bundle_count": fairness_group_s.get(
            "width_by_group_recorded_bundle_count"
        ),
        "fairness_gap_uncertainty_recorded_bundle_count": fairness_group_s.get(
            "group_gap_uncertainty_recorded_bundle_count"
        ),
        "fairness_population_ready_bundle_count": fairness_population_s.get(
            "population_fairness_ready_bundle_count"
        ),
        "fairness_population_estimand_declared_bundle_count": fairness_population_s.get(
            "population_estimand_declared_bundle_count"
        ),
        "fairness_protected_attribute_scope_declared_bundle_count": (
            fairness_population_s.get("protected_attribute_scope_declared_bundle_count")
        ),
        "fairness_weighted_estimand_applied_bundle_count": fairness_population_s.get(
            "weighted_estimand_applied_bundle_count"
        ),
        "fairness_sampling_weight_policy_declared_bundle_count": (
            fairness_population_s.get("sampling_weight_policy_declared_bundle_count")
        ),
        "fairness_pairwise_group_comparison_count": fairness_multiplicity_s.get(
            "pairwise_group_comparison_count"
        ),
        "cross_run_risk_counts": cross_s.get("risk_counts"),
        "cross_run_caveat_counts": cross_s.get("caveat_counts"),
        "duplicate_action_count": duplicate_s.get("duplicate_action_count"),
        "duplicate_open_action_count": duplicate_s.get("open_action_count"),
        "duplicate_paired_comparison_rows": duplicate_s.get("paired_comparison_rows"),
        "duplicate_quarantined_action_count": quarantine_s.get(
            "quarantined_action_count"
        ),
        "duplicate_unquarantined_action_count": quarantine_s.get(
            "unquarantined_action_count"
        ),
        "cross_run_leakage_status": cross_s.get("leakage_status"),
        "cross_run_unsupported_claim_hits": cross_s.get("unsupported_claim_hits"),
        "kg_node_count": kg_graph.get("node_count"),
        "kg_edge_count": kg_graph.get("edge_count"),
        "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
        "failed_check_count": len(failed_checks),
        "final_manuscript_prose_permission": False,
        "method_recommendation_authorized": False,
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "positive_claim_promotion_authorized": False,
        "release_authorized": False,
    }

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "summary": summary,
        "supplement_sections": supplement_sections,
        "supplement_reader_crosswalk": supplement_reader_crosswalk,
        "supplement_reading_protocol_rows": supplement_reading_protocol_rows,
        "supplement_blueprint_rows": [
            {
                "content_area_id": row.get("content_area_id"),
                "scientific_reporting_role": row.get("scientific_reporting_role"),
                "claim_boundary": row.get("claim_boundary"),
                "source_artifact_count": row.get("source_artifact_count"),
                "source_traceability_status": row.get("source_traceability_status"),
                "method_recommendation_authorized": row.get(
                    "method_recommendation_authorized"
                ),
                "positive_claim_promotion_authorized": row.get(
                    "positive_claim_promotion_authorized"
                ),
                "final_retention_authorized": row.get("final_retention_authorized"),
            }
            for row in supplement_rows
        ],
        "citation_keys": {
            url: cite[url] for url in required_citation_urls() if url in cite
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This is a private final-prose supplementary review draft, not final manuscript prose for public submission.",
            "Method evidence is diagnostic; no final method selection or recommendation is authorized.",
            "Bounded-support endpoint results block validity claims.",
            "Group diagnostics do not establish population fairness.",
            "Duplicate and integrity caveats are retained rather than hidden.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    cqr_backend_counts = s.get("cqr_backend_sensitivity_selected_counts") or {}
    cite = payload["citation_keys"]
    split_key = cite["https://arxiv.org/abs/1604.04173"]
    weighted_key = cite["https://arxiv.org/abs/1904.06019"]
    jack_key = cite["https://arxiv.org/abs/1905.02928"]
    cqr_key = cite["https://arxiv.org/abs/1905.03222"]
    jab_key = cite["https://arxiv.org/abs/2002.09025"]
    venn_key = cite["https://proceedings.mlr.press/v91/nouretdinov18a.html"]

    lines = [
        "# Supplementary Document Draft",
        "",
        f"Author: {AUTHOR_NAME}, {AUTHOR_ROLE}",
        f"Email: {AUTHOR_EMAIL}",
        "",
        "> Draft status: private final-prose supplement review draft; not final manuscript prose for public submission, not a release artifact, and not a method recommendation.",
        "",
        "## Supplement Reader Crosswalk",
        "",
        (
            "This crosswalk explains how the supplement should be read with the "
            "main article. Each row identifies the main article surface, the "
            "supplement section that supplies the detailed audit evidence, the "
            "primary source artifact, and the stronger claim that remains closed. "
            "The table is a navigation aid; it does not add experiments or promote "
            "a method."
        ),
        "",
        "| Main article surface | Supplement support | Primary source artifact | Closed claim |",
        "|---|---|---|---|",
    ]
    for row in payload["supplement_reader_crosswalk"]:
        lines.append(
            "| "
            f"{row['main_article_surface']} | "
            f"{row['supplement_support']} | "
            f"`{row['primary_evidence_source']}` | "
            f"{row['closed_claim']} |"
        )
    lines.extend(
        [
            "",
        "## Supplement Reading Protocol",
        "",
        (
            "The supplement is intentionally broader than the main article. "
            "Each section adds audit detail, but the extra detail must be read "
            "through a specific boundary. The protocol below states what a "
            "reviewer should check, which evidence metric anchors the check, "
            "the allowed use of that evidence, and the overclaim that remains "
            "closed."
        ),
        "",
        "| Section | Reviewer check | Evidence metric | Allowed use | Blocked use |",
        "|---|---|---|---|---|",
        ]
    )
    for row in payload["supplement_reading_protocol_rows"]:
        lines.append(
            "| "
            f"{row['section_id']} | "
            f"{row['reader_check']} | "
            f"{row['evidence_metric']} | "
            f"{row['allowed_use']} | "
            f"{row['blocked_use']} |"
        )
    lines.extend(
        [
            "",
        "## S1. Method Selection Robustness Diagnostics",
        "",
        (
            "This section supports the main article by separating descriptive "
            "method behavior from final method selection. In conformal "
            f"prediction, `1 - alpha` is the target coverage level and `alpha` "
            f"is the target miscoverage rate [@{split_key}]. CQR builds an "
            f"interval from lower and upper quantile models before calibration "
            f"[@{cqr_key}], while CV+ and jackknife-style methods use "
            f"out-of-fold or leave-one-out predictions [@{jack_key}; @{jab_key}]."
        ),
        "",
        "| Diagnostic item | Value | Boundary |",
        "|---|---:|---|",
        f"| Candidate methods | {fmt(s['candidate_method_count'])} | CQR, CV+, and Mondrian absolute-residual calibration only |",
        f"| Common dataset-alpha cells | {fmt(s['common_dataset_alpha_cell_count'])} | Shared comparison cells |",
        f"| Common-cell selected diagnostic method | `{s['common_cell_selected_method']}` | Not a final method selection |",
        f"| Common-cell counts | {count_text(s['common_cell_winner_counts'])} | Descriptive counts only |",
        f"| Bootstrap replicates | {fmt(s['bootstrap_replicates'])} | Selection stability diagnostic |",
        f"| Bootstrap counts | {count_text(s['bootstrap_selection_counts'])} | No method recommendation |",
        f"| Bootstrap primary selection rate | {fmt(s['bootstrap_primary_selection_rate'])} | Stability estimate, not final selection |",
        f"| Bootstrap primary selection-rate 95% interval | {ci_text(s['bootstrap_primary_selection_rate_ci95'])} | Precision check for the diagnostic rate |",
        f"| Leave-one-dataset retention | {fmt(s['leave_one_dataset_primary_retention_rate'])} | Diagnostic robustness |",
        f"| Leave-one-alpha retention | {fmt(s['leave_one_alpha_primary_retention_rate'])} | Diagnostic robustness |",
        f"| Final selection claim | `{s['final_selection_claim_status']}` | Final selection remains blocked |",
        f"| Pairwise shared cells | {fmt(s['inferential_candidate_min_shared_pairwise_cell_count'])} | Inferential support, not a claim upgrade |",
        f"| Main-result primary win rate | {fmt(s['main_result_candidate_primary_win_rate'])} | Descriptive rate with final claim blocked |",
        f"| Main-result primary win-rate 95% interval | {ci_text(s['main_result_candidate_primary_win_rate_ci95'])} | Uncertainty around the descriptive rate |",
        f"| Robustness common-cell primary win rate | {fmt(s['robustness_common_cell_primary_win_rate'])} | Common-cell diagnostic only |",
        f"| Robustness common-cell 95% interval | {ci_text(s['robustness_common_cell_primary_win_rate_ci95'])} | Precision check, not claim authorization |",
        "",
        (
            "Reader note: this section explains why CQR/CV+ can be reported as "
            "strong practical candidates observed in these experiments while the "
            "final-selection gate remains closed. The confidence intervals quantify "
            "diagnostic uncertainty around the observed rates; they do not change "
            "the authorization state of the final-selection claim."
        ),
        "",
        "### S1b. CQR Backend Sensitivity Check",
        "",
        (
            "The completed model-matched CQR rerun checks whether the historical "
            "fixed-GBM CQR backend explains the CQR signal. It preserves the "
            "experiment-scoped interpretation and does not create a method-selection "
            "claim."
        ),
        "",
        "| Backend diagnostic item | Value | Boundary |",
        "|---|---:|---|",
        f"| Fixed-GBM CQR completed rows | {fmt(s['cqr_backend_sensitivity_fixed_gbm_completed_rows'])} | Historical comparator rows |",
        f"| Model-matched CQR completed rows | {fmt(s['cqr_backend_sensitivity_model_matched_completed_rows'])} | Completed rerun rows |",
        f"| Paired dataset-alpha-model-family cells | {fmt(s['cqr_backend_sensitivity_paired_cell_count'])} | Direct CQR backend comparison cells |",
        f"| Fixed-GBM CQR selected cells | {fmt(cqr_backend_counts.get('fixed_gbm_cqr'))} | Coverage-eligible interval-score selections |",
        f"| Model-matched CQR selected cells | {fmt(cqr_backend_counts.get('model_matched_cqr'))} | Coverage-eligible interval-score selections |",
        f"| Neither coverage-eligible variant | {fmt(cqr_backend_counts.get('no_coverage_eligible_variant'))} | Cells where both CQR variants fail the coverage-eligibility rule |",
        f"| Method-selection claim supported | `{s['cqr_backend_sensitivity_can_support_method_winner_claim']}` | No method recommendation opens |",
        "",
        "## S2. Post-Selection Validation Diagnostics",
        "",
        (
            "Post-selection validation asks whether the descriptive pattern "
            "persists in a held-out validation-style slice after the candidate "
            "methods have already been identified. The supplement treats this "
            "as a diagnostic stress test. It does not convert the observed "
            "counts into a final method selection."
        ),
        "",
        "| Diagnostic item | Value | Boundary |",
        "|---|---:|---|",
        f"| Validation datasets | {fmt(s['post_selection_dataset_count'])} | Narrow validation scope |",
        f"| Validation dataset-alpha cells | {fmt(s['post_selection_common_dataset_alpha_cell_count'])} | Shared cells only |",
        f"| Completed validation atomic runs | {fmt(s['post_selection_completed_atomic_run_count'])} | Completed diagnostic rows |",
        f"| Validation diagnostic counts | {count_text(s['post_selection_diagnostic_winner_counts'])} | No final method selection |",
        f"| Validation primary win rate | {fmt(s['post_selection_validation_primary_win_rate'])} | Post-selection diagnostic rate |",
        f"| Validation primary win-rate 95% interval | {ci_text(s['post_selection_validation_primary_win_rate_ci95'])} | Wide uncertainty remains visible |",
        f"| Feature leakage violations | {fmt(s['post_selection_feature_leakage_violation_count'])} | Leakage sidecars clean in this slice |",
        f"| Width pathology rows | {fmt(s['post_selection_width_pathology_row_count'])} | Retained caveat evidence |",
        f"| Bridge validation datasets | {fmt(s['bridge_validation_dataset_count'])} | Dataset-final-gate bridge slice |",
        f"| Bridge validation atomic runs | {fmt(s['bridge_validation_completed_atomic_run_count'])} | Auxiliary diagnostic evidence |",
        f"| Bridge validation diagnostic counts | {count_text(s['bridge_validation_diagnostic_winner_counts'])} | Bridge-slice diagnostics only |",
        f"| Venn-Abers bridge undercoverage runs | {fmt(s['venn_undercoverage_run_count'])} | Negative bridge evidence |",
        "",
        (
            "Reader note: post-selection diagnostics are stress tests of a "
            "descriptive pattern. They do not license language such as final "
            "method selection, globally best conformal method, or validated Venn-Abers "
            "regression interval. The Venn-Abers rows are especially narrow: "
            f"they concern the evaluated bridge, while predictive-distribution "
            f"and generalized Venn-Abers work remain separate literature objects "
            f"[@{venn_key}; @{cite['https://proceedings.mlr.press/v230/nouretdinov24a.html']}; "
            f"@{cite['https://proceedings.mlr.press/v267/van-der-laan25a.html']}; "
            f"@{cite['https://arxiv.org/html/2605.06646v1']}]."
        ),
        "",
        "## S3. Bounded-Support Endpoint Policy",
        "",
        (
            "Bounded-support checks ask whether prediction interval endpoints "
            "respect the natural domain of the target. This is different from "
            "ordinary marginal coverage. Weighted conformal ideas can address "
            f"some covariate-shift settings [@{weighted_key}], but the present "
            "endpoint policy is an empirical domain-validity gate. The current "
            "gate blocks bounded-support validity claims."
        ),
        "",
        "| Diagnostic item | Value | Boundary |",
        "|---|---:|---|",
        f"| Bounded-support bundles | {fmt(s['bounded_bundle_count'])} | Manuscript-candidate bundles |",
        f"| Bounded-support datasets | {fmt(s['bounded_dataset_count'])} | Current endpoint-audit scope |",
        f"| Raw endpoint-excursion bundles | {fmt(s['bounded_raw_endpoint_excursion_bundle_count'])} | Domain blocker retained |",
        f"| Post-handling validated bundles | {fmt(s['bounded_posthandling_validated_bundle_count'])} | Policy triage complete |",
        f"| Clean or not-applicable bundles | {fmt(s['bounded_endpoint_clean_or_not_applicable_bundle_count'])} | Not enough for global validity |",
        f"| Validity-ready bundles | {fmt(s['bounded_support_validity_ready_bundle_count'])} | No bounded-support validity claim |",
        f"| Positive-claim-ready bundles | {fmt(s['bounded_positive_claim_ready_bundle_count'])} | Positive endpoint claim blocked |",
        f"| Endpoint support status counts | {count_text(s['bounded_endpoint_support_status_counts'])} | Support-status inventory, not a validity upgrade |",
        "",
        (
            "Reader note: bounded-support evidence is stricter than ordinary "
            "coverage evidence. A method can have acceptable empirical coverage "
            "and still fail a natural-domain endpoint gate. The supplement "
            "therefore reports endpoint closure as a limitation, not as a "
            "post-processing success story."
        ),
        "",
        "## S4. Fairness Group Diagnostics",
        "",
        (
            "Group coverage diagnostics compare interval behavior across "
            "observed groups. They are useful for auditing heterogeneity, but "
            "they are not population fairness claims unless the population "
            "estimand, protected-attribute scope, sampling design, and "
            "multiplicity treatment support that claim."
        ),
        "",
        "| Diagnostic item | Value | Boundary |",
        "|---|---:|---|",
        f"| Fairness diagnostic bundles | {fmt(s['fairness_bundle_count'])} | Diagnostic group scope |",
        f"| Fairness diagnostic datasets | {fmt(s['fairness_dataset_count'])} | Current diagnostic scope |",
        f"| Bootstrap replicates | {fmt(s['fairness_bootstrap_replicates'])} | Gap-uncertainty diagnostic |",
        f"| Group counts recorded | {fmt(s['fairness_group_counts_recorded_bundle_count'])} | Required diagnostic metadata |",
        f"| Coverage by group recorded | {fmt(s['fairness_coverage_by_group_recorded_bundle_count'])} | Group comparison evidence |",
        f"| Width by group recorded | {fmt(s['fairness_width_by_group_recorded_bundle_count'])} | Interval-size comparison evidence |",
        f"| Gap uncertainty recorded | {fmt(s['fairness_gap_uncertainty_recorded_bundle_count'])} | Multiplicity-aware caveat evidence |",
        f"| Pairwise group comparisons | {fmt(s['fairness_pairwise_group_comparison_count'])} | Multiplicity scope, not fairness proof |",
        f"| Population-estimand-declared bundles | {fmt(s['fairness_population_estimand_declared_bundle_count'])} | Required for population fairness, absent here |",
        f"| Protected-attribute-scope-declared bundles | {fmt(s['fairness_protected_attribute_scope_declared_bundle_count'])} | Required scope declaration, absent here |",
        f"| Weighted-estimand-applied bundles | {fmt(s['fairness_weighted_estimand_applied_bundle_count'])} | No weighted population estimand applied |",
        f"| Sampling-weight-policy-declared bundles | {fmt(s['fairness_sampling_weight_policy_declared_bundle_count'])} | Policy exists but does not open fairness claim |",
        f"| Population-fairness-ready bundles | {fmt(s['fairness_population_ready_bundle_count'])} | No population fairness claim |",
        "",
        (
            "Reader note: group rows can show where interval behavior differs, "
            "but fairness is an estimand-level claim. Because the current "
            "population estimand and protected-attribute scope are not declared "
            "at the bundle level, the correct supplement reading is diagnostic "
            "heterogeneity, not population fairness."
        ),
        "",
        "## S5. Duplicate And Integrity Caveats",
        "",
        (
            "Duplicate and split-integrity checks protect the interpretation of "
            "model comparisons. If repeated rows, row signatures, or model-visible "
            "duplicates can affect train/calibration/test separation, the result "
            "must retain the caveat rather than become stronger prose."
        ),
        "",
        "| Diagnostic item | Value | Boundary |",
        "|---|---:|---|",
        f"| Duplicate actions | {fmt(s['duplicate_action_count'])} | Caveat inventory scope |",
        f"| Open duplicate actions | {fmt(s['duplicate_open_action_count'])} | Closure evidence only |",
        f"| Paired duplicate comparison rows | {fmt(s['duplicate_paired_comparison_rows'])} | Sensitivity evidence |",
        f"| Quarantined actions | {fmt(s['duplicate_quarantined_action_count'])} | Main-claim promotion blocked |",
        f"| Unquarantined actions | {fmt(s['duplicate_unquarantined_action_count'])} | No untracked duplicate action |",
        f"| Cross-run leakage status | `{s['cross_run_leakage_status']}` | Hard leakage not detected in scanned artifacts |",
        f"| Unsupported claim hits | {fmt(s['cross_run_unsupported_claim_hits'])} | Claim scan clean for this audit |",
        f"| Cross-run risk counts | {count_text(s['cross_run_risk_counts'])} | Risk inventory retained |",
        f"| Cross-run caveat counts | {count_text(s['cross_run_caveat_counts'])} | Caveats constrain interpretation |",
        "",
        (
            "Reader note: the clean unsupported-claim scan does not erase "
            "duplicate or split caveats. It means the scanned artifacts did not "
            "contain unsupported claim language; the caveats still travel with "
            "the empirical interpretation."
        ),
        "",
        "## S6. Traceability And Release State",
        "",
        (
            f"The supplement is linked to a knowledge graph snapshot with "
            f"{fmt(s['kg_node_count'])} nodes, {fmt(s['kg_edge_count'])} edges, "
            f"and {fmt(s['kg_isolated_node_count'])} isolated nodes. The graph "
            "connects report sections, source artifacts, citations, claim "
            "boundaries, and quality checks. It remains an internal evidence "
            "artifact until the sterile repository and release review are complete."
        ),
        "",
        (
            "Venn-Abers evidence is retained as part of the negative and "
            f"boundary evidence for this study [@{venn_key}]. The supplement "
            "does not claim that the current interval bridge validates "
            "Venn-Abers regression intervals."
        ),
        "",
        "## Claim Boundaries",
        "",
    ]
    )
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(["", "## References", ""])
    for url, key in sorted(payload["citation_keys"].items(), key=lambda item: item[1]):
        lines.append(f"- `@{key}`: {url}")
    lines.extend(["", "## Source Artifacts", ""])
    for label, path in payload["sources"].items():
        lines.append(f"- `{label}`: `{path}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    json_out = root / args.json_out
    payload = build_payload(root)
    atomic_write_json(json_out, payload)
    atomic_write_text(out, render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out, root),
                "json_out": rel(json_out, root),
                "overall_status": payload["summary"]["overall_status"],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
