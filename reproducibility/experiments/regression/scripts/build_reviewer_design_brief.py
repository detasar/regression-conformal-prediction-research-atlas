"""Build neutral pre-prose reviewer design advice and reconciliation artifacts.

This script consumes ``publication_preparation_packets.json`` and creates the
next publication-preparation layer: structured reviewer advice, a reconciliation
matrix, an article/supplement/KG content matrix, and a publication-site decision
record. It is intentionally pre-prose: it does not write manuscript text, choose
final retained visuals, create the sterile repository, or promote any method.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_reviewer_design_brief_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/reviewer_design_brief.json")
PREPARATION_PACKETS = Path(
    "experiments/regression/manuscript/publication_preparation_packets.json"
)
POST_EXPERIMENT_PUBLICATION_PROGRAM = Path(
    "experiments/regression/manuscript/post_experiment_publication_program.json"
)
POST_EXPERIMENT_PUBLICATION_ACTIVATION = Path(
    "experiments/regression/manuscript/post_experiment_publication_activation_audit.json"
)
PUBLICATION_AUTHORING_DECISION = Path(
    "experiments/regression/manuscript/publication_authoring_decision_record.json"
)
NEUTRAL_LANGUAGE = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "neutral_reporting_language_audit.json"
)
GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
PAPER_GATE_CLOSURE = Path(
    "experiments/regression/manuscript/paper_gate_closure_map.json"
)


REVIEWER_ADVICE_TEMPLATES: dict[str, tuple[dict[str, str], ...]] = {
    "statistical_methodology_reviewer": (
        {
            "topic": "main_article_question_and_claim_design",
            "target_surface": "main_article",
            "recommendation_text": (
                "Frame the main article around empirical operating behavior "
                "and explicit claim boundaries, not a final winner narrative."
            ),
            "evidence_needed": (
                "method_performance_synthesis, method_selection_inferential_audit, "
                "paper_gate_closure_map"
            ),
            "decision": "accept_for_design",
            "mapped_artifact": "article_supplement_content_matrix.json",
        },
        {
            "topic": "supplementary_document_scope_and_table_inventory",
            "target_surface": "supplementary_document",
            "recommendation_text": (
                "Put dataset-alpha-method accounting, uncertainty intervals, "
                "blocked gates, and sensitivity caveats in structured supplement tables."
            ),
            "evidence_needed": (
                "experiment_accounting_audit, method_selection_robustness_audit, "
                "duplicate_sensitivity_closure_audit"
            ),
            "decision": "accept_for_design",
            "mapped_artifact": "reviewer_reconciliation_matrix.json",
        },
        {
            "topic": "figure_and_table_selection_rules",
            "target_surface": "main_article",
            "recommendation_text": (
                "Require every candidate figure or table to expose denominator, "
                "alpha scope, dataset scope, and no-final-selection status."
            ),
            "evidence_needed": "publication_preparation_packets, visual_table_inventory_plan",
            "decision": "accept_for_design",
            "mapped_artifact": "article_supplement_content_matrix.json",
        },
        {
            "topic": "reviewer_conflict_reconciliation_rules",
            "target_surface": "reconciliation_matrix",
            "recommendation_text": (
                "Resolve reviewer conflicts by favoring claim-boundary safety, "
                "source traceability, and reproducibility over narrative compactness."
            ),
            "evidence_needed": "neutral_reporting_language_audit, kg_quality_summary",
            "decision": "accept_for_design",
            "mapped_artifact": "reviewer_reconciliation_matrix.json",
        },
        {
            "topic": "latex_and_html_rendering_plan",
            "target_surface": "article_and_html",
            "recommendation_text": (
                "Draft LaTeX and HTML only after the design brief is reconciled; "
                "use the same source tables for both render targets."
            ),
            "evidence_needed": "reviewer_design_brief, article_supplement_content_matrix",
            "decision": "defer_until_design_brief_complete",
            "mapped_artifact": "reviewer_design_brief.json",
        },
    ),
    "conformal_prediction_reviewer": (
        {
            "topic": "main_article_question_and_claim_design",
            "target_surface": "main_article",
            "recommendation_text": (
                "Separate conformal method taxonomy from empirical selection "
                "diagnostics so CQR, CV+, Mondrian, and Venn-Abers are not "
                "ranked beyond audited evidence."
            ),
            "evidence_needed": "method_literature_coverage_audit, method_performance_synthesis",
            "decision": "accept_for_design",
            "mapped_artifact": "article_supplement_content_matrix.json",
        },
        {
            "topic": "supplementary_document_scope_and_table_inventory",
            "target_surface": "supplementary_document",
            "recommendation_text": (
                "Include method-family tables for split, tail-specific, normalized, "
                "Mondrian, plus-family, CQR, weighted, and Venn-Abers diagnostics."
            ),
            "evidence_needed": "method_performance_synthesis, method_literature_coverage_audit",
            "decision": "accept_for_design",
            "mapped_artifact": "article_supplement_content_matrix.json",
        },
        {
            "topic": "figure_and_table_selection_rules",
            "target_surface": "main_article",
            "recommendation_text": (
                "Show Venn-Abers regression evidence as failure-mode diagnostics "
                "when coverage or boundary gates block stronger interpretation."
            ),
            "evidence_needed": (
                "venn_abers_grid_failure_mode_decomposition, "
                "venn_abers_claim_gate_matrix"
            ),
            "decision": "accept_for_design",
            "mapped_artifact": "reviewer_reconciliation_matrix.json",
        },
        {
            "topic": "article_supplement_kg_triptych_design",
            "target_surface": "kg_or_publication_site",
            "recommendation_text": (
                "Use the KG as a traceability surface for method definitions, "
                "claim gates, and source artifacts if release review remains clean."
            ),
            "evidence_needed": "knowledge_graph_quality_summary, kg_publication_quality_audit",
            "decision": "accept_for_design",
            "mapped_artifact": "publication_site_decision_record.json",
        },
        {
            "topic": "reviewer_conflict_reconciliation_rules",
            "target_surface": "reconciliation_matrix",
            "recommendation_text": (
                "When empirical candidate ranking and formal validity language "
                "conflict, keep the ranking diagnostic and block validity wording."
            ),
            "evidence_needed": "paper_gate_closure_map, neutral_reporting_language_audit",
            "decision": "accept_for_design",
            "mapped_artifact": "reviewer_reconciliation_matrix.json",
        },
    ),
    "data_science_reproducibility_reviewer": (
        {
            "topic": "supplementary_document_scope_and_table_inventory",
            "target_surface": "supplementary_document",
            "recommendation_text": (
                "Make experiment accounting, source discovery, preprocessing, "
                "split policy, and resume behavior first-class supplement tables."
            ),
            "evidence_needed": (
                "experiment_accounting_audit, external_source_discovery_watchlist, "
                "cross_run_integrity_audit"
            ),
            "decision": "accept_for_design",
            "mapped_artifact": "article_supplement_content_matrix.json",
        },
        {
            "topic": "knowledge_graph_citability_and_navigation_design",
            "target_surface": "kg_or_publication_site",
            "recommendation_text": (
                "Cite the KG only after release review confirms no stale paths, "
                "private-only cache dependency, or untraceable edge remains."
            ),
            "evidence_needed": "knowledge_graph_quality_summary, kg_publication_quality_audit",
            "decision": "defer_until_release_review",
            "mapped_artifact": "publication_site_decision_record.json",
        },
        {
            "topic": "static_publication_site_design_and_release_boundary",
            "target_surface": "publication_site",
            "recommendation_text": (
                "Treat the static site as a reader navigation layer over released "
                "artifacts, not as the authoritative data store."
            ),
            "evidence_needed": "publication_site_decision_record, sterile_repository_plan",
            "decision": "defer_until_sterile_repository_review",
            "mapped_artifact": "publication_site_decision_record.json",
        },
        {
            "topic": "figure_and_table_selection_rules",
            "target_surface": "main_article",
            "recommendation_text": (
                "Every paper-facing table should carry source artifact paths, "
                "row-count denominators, and caveat fields."
            ),
            "evidence_needed": "publication_preparation_packets, reviewer_design_brief",
            "decision": "accept_for_design",
            "mapped_artifact": "reviewer_design_brief.json",
        },
        {
            "topic": "github_pages_publication_readiness_plan",
            "target_surface": "publication_site",
            "recommendation_text": (
                "Do not activate GitHub Pages until the final sterile repository "
                "exists and disclosure review passes."
            ),
            "evidence_needed": "post_experiment_publication_activation_audit",
            "decision": "defer_until_sterile_repository_review",
            "mapped_artifact": "publication_site_decision_record.json",
        },
    ),
    "fairness_domain_reviewer": (
        {
            "topic": "main_article_question_and_claim_design",
            "target_surface": "main_article",
            "recommendation_text": (
                "Present fairness material as diagnostic group behavior unless "
                "population estimand, weights, and multiplicity gates pass."
            ),
            "evidence_needed": (
                "fairness_group_diagnostic_audit, fairness_sampling_weight_policy, "
                "fairness_population_readiness_audit"
            ),
            "decision": "accept_for_design",
            "mapped_artifact": "article_supplement_content_matrix.json",
        },
        {
            "topic": "supplementary_document_scope_and_table_inventory",
            "target_surface": "supplementary_document",
            "recommendation_text": (
                "Put group counts, missingness by group, coverage by group, width "
                "by group, and comparison-family scope in supplement tables."
            ),
            "evidence_needed": "fairness_group_diagnostic_audit, fairness_group_multiplicity_scope",
            "decision": "accept_for_design",
            "mapped_artifact": "article_supplement_content_matrix.json",
        },
        {
            "topic": "reviewer_conflict_reconciliation_rules",
            "target_surface": "reconciliation_matrix",
            "recommendation_text": (
                "If reviewers request stronger fairness wording, defer it unless "
                "the fairness population-inference gate is explicitly clean."
            ),
            "evidence_needed": "fairness_population_readiness_audit, paper_gate_closure_map",
            "decision": "accept_for_design",
            "mapped_artifact": "reviewer_reconciliation_matrix.json",
        },
        {
            "topic": "figure_and_table_selection_rules",
            "target_surface": "supplementary_document",
            "recommendation_text": (
                "Require fairness visuals to show group sample sizes and avoid "
                "policy or production interpretation."
            ),
            "evidence_needed": "fairness_group_diagnostic_audit",
            "decision": "accept_for_design",
            "mapped_artifact": "reviewer_design_brief.json",
        },
        {
            "topic": "article_supplement_kg_triptych_design",
            "target_surface": "kg_or_publication_site",
            "recommendation_text": (
                "Use KG links for protected-attribute provenance and fairness "
                "claim gates so readers can distinguish diagnostics from claims."
            ),
            "evidence_needed": "knowledge_graph_quality_summary, fairness_population_readiness_audit",
            "decision": "accept_for_design",
            "mapped_artifact": "publication_site_decision_record.json",
        },
    ),
    "visual_editorial_reviewer": (
        {
            "topic": "figure_and_table_selection_rules",
            "target_surface": "main_article",
            "recommendation_text": (
                "Keep only figures that answer a paper question, survive overlap "
                "checks, and state the claim boundary in the caption."
            ),
            "evidence_needed": "visual_table_inventory_plan, visual_table_audit_agent_contract",
            "decision": "defer_until_candidate_visuals_rendered",
            "mapped_artifact": "article_supplement_content_matrix.json",
        },
        {
            "topic": "visual_auditor_iteration_and_stop_rules",
            "target_surface": "visual_table_audit",
            "recommendation_text": (
                "Require pass, revise, move, or remove decisions for every "
                "candidate visual/table before any retained-artifact claim."
            ),
            "evidence_needed": "post_experiment_publication_program.visual_table_audit_agent",
            "decision": "accept_for_design",
            "mapped_artifact": "reviewer_reconciliation_matrix.json",
        },
        {
            "topic": "latex_and_html_rendering_plan",
            "target_surface": "article_and_html",
            "recommendation_text": (
                "Use shared captions and table metadata for LaTeX and HTML to "
                "avoid drift between publication surfaces."
            ),
            "evidence_needed": "reviewer_design_brief, article_supplement_content_matrix",
            "decision": "defer_until_design_brief_complete",
            "mapped_artifact": "reviewer_design_brief.json",
        },
        {
            "topic": "static_publication_site_design_and_release_boundary",
            "target_surface": "publication_site",
            "recommendation_text": (
                "Plan site navigation around article, supplement, and KG entry "
                "points, but keep deployment blocked until release gates pass."
            ),
            "evidence_needed": "publication_site_decision_record, post_experiment_publication_activation_audit",
            "decision": "defer_until_sterile_repository_review",
            "mapped_artifact": "publication_site_decision_record.json",
        },
        {
            "topic": "article_supplement_kg_triptych_design",
            "target_surface": "kg_or_publication_site",
            "recommendation_text": (
                "Use the KG/site for drill-down provenance and keep dense audit "
                "tables out of the article body unless they are essential."
            ),
            "evidence_needed": "kg_publication_quality_audit, publication_preparation_packets",
            "decision": "accept_for_design",
            "mapped_artifact": "article_supplement_content_matrix.json",
        },
    ),
}


BLOCKED_GATE_BY_TOPIC = {
    "main_article_question_and_claim_design": "final_method_model_selection_gate",
    "supplementary_document_scope_and_table_inventory": "",
    "knowledge_graph_citability_and_navigation_design": "sterile_repository_and_release_review",
    "static_publication_site_design_and_release_boundary": "sterile_repository_and_release_review",
    "figure_and_table_selection_rules": "visual_table_audit_gate",
    "latex_and_html_rendering_plan": "reviewer_reconciliation_and_visual_audit_gate",
    "reviewer_conflict_reconciliation_rules": "",
    "article_supplement_kg_triptych_design": "kg_usability_disclosure_and_release_review",
    "github_pages_publication_readiness_plan": "sterile_repository_and_release_review",
    "visual_auditor_iteration_and_stop_rules": "visual_table_audit_gate",
}

VISUAL_FAMILIES_BY_TOPIC = {
    "main_article_question_and_claim_design": [
        "method_performance_descriptive_summary",
        "neutral_closure_and_claim_boundary_table",
    ],
    "supplementary_document_scope_and_table_inventory": [
        "experiment_scope_and_accounting_table",
        "fairness_group_diagnostic_tables",
        "bounded_support_endpoint_policy_table",
    ],
    "knowledge_graph_citability_and_navigation_design": [
        "knowledge_graph_navigation_quality"
    ],
    "static_publication_site_design_and_release_boundary": [
        "knowledge_graph_navigation_quality"
    ],
    "figure_and_table_selection_rules": [
        "method_selection_robustness_diagnostics",
        "venn_abers_failure_mode_evidence",
    ],
    "latex_and_html_rendering_plan": ["neutral_closure_and_claim_boundary_table"],
    "reviewer_conflict_reconciliation_rules": [
        "neutral_closure_and_claim_boundary_table"
    ],
    "article_supplement_kg_triptych_design": [
        "knowledge_graph_navigation_quality",
        "duplicate_split_caveat_inventory",
    ],
    "github_pages_publication_readiness_plan": [
        "knowledge_graph_navigation_quality"
    ],
    "visual_auditor_iteration_and_stop_rules": [
        "method_selection_robustness_diagnostics",
        "venn_abers_failure_mode_evidence",
    ],
}

VISUAL_FAMILY_GATE_DEPENDENCIES = {
    "experiment_scope_and_accounting_table": "",
    "method_performance_descriptive_summary": "final_method_model_selection_gate",
    "method_selection_robustness_diagnostics": "final_method_model_selection_gate",
    "post_selection_validation_diagnostics": "final_method_model_selection_gate",
    "venn_abers_failure_mode_evidence": "venn_abers_regression_validation_gate",
    "bounded_support_endpoint_policy_table": "endpoint_bounded_support_gate",
    "fairness_group_diagnostic_tables": "fairness_population_inference_gate",
    "duplicate_split_caveat_inventory": "dataset_specific_final_gates",
    "knowledge_graph_navigation_quality": "sterile_repository_and_release_review",
    "neutral_closure_and_claim_boundary_table": "",
}


def gate_dependency_for_visual_family(family_id: str) -> str:
    return VISUAL_FAMILY_GATE_DEPENDENCIES.get(
        family_id, "visual_table_audit_gate"
    )


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


def existing_sources(root: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if (root / path).exists()]


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def check_row(
    check_id: str,
    passed: bool,
    evidence: dict[str, Any],
    source_artifacts: list[str],
    blocker: str = "",
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "blocks_reviewer_design": not passed,
        "evidence": evidence,
        "source_artifacts": source_artifacts,
        "blocker": blocker,
    }


def build_advice_records(
    packets: list[dict[str, Any]],
    required_schema_fields: list[str],
    root: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    packet_by_reviewer = {
        str(packet.get("reviewer_id")): packet
        for packet in packets
        if packet.get("reviewer_id")
    }
    for reviewer_id, templates in REVIEWER_ADVICE_TEMPLATES.items():
        packet = packet_by_reviewer.get(reviewer_id, {})
        for index, template in enumerate(templates, start=1):
            recommendation_id = f"{reviewer_id}:R{index:02d}"
            row = {
                "reviewer_id": reviewer_id,
                "recommendation_id": recommendation_id,
                "recommendation_text": template["recommendation_text"],
                "target_surface": template["target_surface"],
                "evidence_needed": template["evidence_needed"],
                "accept_reject_defer_decision": template["decision"],
                "rationale": (
                    "Pre-prose design recommendation derived from the reviewer "
                    "packet; it preserves audited claim boundaries and does not "
                    "authorize final manuscript prose or retained visual selection."
                ),
                "mapped_artifact": template["mapped_artifact"],
                "advice_topic": template["topic"],
                "claim_boundary_tag": "neutral_pre_prose_design_only",
                "blocked_gate_dependency": BLOCKED_GATE_BY_TOPIC.get(
                    template["topic"], ""
                ),
                "visual_family_ids": VISUAL_FAMILIES_BY_TOPIC.get(
                    template["topic"], []
                ),
                "decision_scope": (
                    "publication_design_only_no_final_prose_no_retained_visuals"
                ),
                "packet_id": packet.get("packet_id"),
                "source_artifacts": [
                    artifact
                    for artifact in packet.get("source_artifacts") or []
                    if (root / artifact).exists()
                ],
                "claim_boundary": (
                    "Design advice only; no final prose, final retained visual, "
                    "sterile release, or positive method claim is authorized."
                ),
            }
            row["schema_fields_present"] = all(
                field in row for field in required_schema_fields
            )
            records.append(row)
    return records


def build_reconciliation_rows(advice_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in advice_records:
        decision = str(row.get("accept_reject_defer_decision") or "")
        rows.append(
            {
                "recommendation_id": row["recommendation_id"],
                "reviewer_id": row["reviewer_id"],
                "advice_topic": row["advice_topic"],
                "target_surface": row["target_surface"],
                "mapped_artifact": row["mapped_artifact"],
                "reconciliation_decision": decision,
                "reconciliation_status": (
                    "ready_for_design_brief"
                    if decision == "accept_for_design"
                    else "deferred_with_gate"
                ),
                "decision_scope": row["decision_scope"],
                "blocked_gate_dependency": row["blocked_gate_dependency"],
                "visual_family_ids": row["visual_family_ids"],
                "decision_rationale": (
                    "Accepted or deferred only for publication design planning. "
                    "No row authorizes final manuscript prose, final visual "
                    "retention, repository release, or stronger claims."
                ),
                "blocking_gate": (
                    ""
                    if decision == "accept_for_design"
                    else row["blocked_gate_dependency"]
                    or "final_prose_visual_or_release_gate"
                ),
                "claim_boundary": row["claim_boundary"],
            }
        )
    return rows


def build_content_matrix(
    root: Path, visual_inventory: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in visual_inventory:
        family_id = str(row.get("artifact_family_id") or "").strip()
        if not family_id:
            continue
        source_artifacts = existing_sources(root, list(row.get("source_artifacts") or []))
        rows.append(
            {
                "content_area_id": family_id,
                "artifact_type": row.get("artifact_type"),
                "candidate_surface": "_and_".join(row.get("target_surfaces") or []),
                "target_surfaces": row.get("target_surfaces") or [],
                "reader_question": row.get("paper_question"),
                "source_artifacts": source_artifacts,
                "source_artifact_count": len(source_artifacts),
                "gate_dependency": gate_dependency_for_visual_family(family_id),
                "claim_boundary": row.get("claim_boundary"),
                "placement_status": "candidate_design_only",
                "final_placement_decision": "not_started",
                "retained_visual_or_table_decision": "not_started",
                "visual_audit_status": "not_started",
            }
        )
    return rows


def build_publication_site_decision_record(
    root: Path,
    kg_quality_summary: dict[str, Any],
    activation_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "record_id": "publication_site_decision_record",
        "status": "site_design_candidate_release_blocked",
        "site_decision_status": "deferred_until_release_gates_pass",
        "kg_candidate_for_navigation": True,
        "github_pages_candidate": True,
        "site_deployment_authorized": False,
        "sterile_repository_required_before_deployment": True,
        "kg_node_count": kg_quality_summary.get("node_count"),
        "kg_edge_count": kg_quality_summary.get("edge_count"),
        "kg_issue_counts_by_severity": kg_quality_summary.get(
            "issue_counts_by_severity"
        ),
        "sterile_repository_creation_authorized": activation_summary.get(
            "sterile_repository_creation_authorized"
        ),
        "source_artifacts": existing_sources(
            root,
            [
                "experiments/regression/reports/knowledge_graph_quality/quality_summary.json",
                "experiments/regression/reports/methodology_sanity_audit_20260627/kg_publication_quality_audit.json",
                "experiments/regression/manuscript/post_experiment_publication_activation_audit.json",
            ],
        ),
        "claim_boundary": (
            "The site is a candidate reader-navigation surface only. Deployment "
            "and citation remain blocked until sterile repository and disclosure "
            "review pass."
        ),
    }


def build_payload(root: Path) -> dict[str, Any]:
    packets_payload = read_json(root / PREPARATION_PACKETS)
    program = read_json(root / POST_EXPERIMENT_PUBLICATION_PROGRAM)
    activation = read_json(root / POST_EXPERIMENT_PUBLICATION_ACTIVATION)
    authoring_decision = read_json(root / PUBLICATION_AUTHORING_DECISION)
    neutral_language = read_json(root / NEUTRAL_LANGUAGE)
    kg_quality = read_json(
        root / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
    )

    packets_summary = summary(packets_payload)
    activation_summary = summary(activation)
    authoring_summary = summary(authoring_decision)
    neutral_language_summary = summary(neutral_language)
    reviewer_gate = program.get("reviewer_design_gate") or {}
    required_schema_fields = list(reviewer_gate.get("advice_record_schema") or [])
    required_topics = set(reviewer_gate.get("required_advice_topics") or [])
    minimum_recommendations = safe_int(
        reviewer_gate.get("minimum_structured_recommendations_per_reviewer")
    )
    required_reviewer_count = safe_int(
        reviewer_gate.get("required_reviewer_pass_count")
    )
    reviewer_packets = list(packets_payload.get("reviewer_packets") or [])
    visual_inventory = list(packets_payload.get("visual_table_inventory_plan") or [])

    advice_records = build_advice_records(reviewer_packets, required_schema_fields, root)
    reconciliation_rows = build_reconciliation_rows(advice_records)
    content_matrix = build_content_matrix(root, visual_inventory)
    site_decision_record = build_publication_site_decision_record(
        root, kg_quality, activation_summary
    )

    advice_by_reviewer = Counter(row["reviewer_id"] for row in advice_records)
    topic_counts = Counter(row["advice_topic"] for row in advice_records)
    accepted_count = sum(
        1
        for row in advice_records
        if row["accept_reject_defer_decision"] == "accept_for_design"
    )
    deferred_count = sum(
        1
        for row in advice_records
        if str(row["accept_reject_defer_decision"]).startswith("defer_")
    )
    accepted_or_deferred_count = accepted_count + deferred_count
    topics_covered = set(topic_counts)
    missing_topics = sorted(required_topics - topics_covered)
    reviewers_below_minimum = sorted(
        reviewer_id
        for reviewer_id in REVIEWER_ADVICE_TEMPLATES
        if advice_by_reviewer[reviewer_id] < minimum_recommendations
    )

    final_actions_blocked = (
        activation_summary.get("manuscript_drafting_authorized") is False
        and activation_summary.get("sterile_repository_creation_authorized") is False
        and all(
            row.get("final_placement_decision") == "not_started"
            for row in content_matrix
        )
        and site_decision_record.get("site_deployment_authorized") is False
    )
    neutral_guard_active = (
        packets_summary.get("neutral_no_method_promotion_guard_active") is True
        and neutral_language_summary.get("overall_status")
        == "neutral_reporting_language_audit_pass"
        and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
    )
    private_manuscript_authoring_authorized = (
        packets_summary.get("private_manuscript_drafting_authorized") is True
        and activation_summary.get("private_manuscript_drafting_authorized") is True
        and authoring_summary.get("research_document_authoring_authorized") is True
        and authoring_summary.get("final_public_release_authorized") is False
        and authoring_summary.get("new_experiments_authorized") is False
    )

    checks = [
        check_row(
            "publication_preparation_packets_ready",
            packets_summary.get("overall_status")
            == "publication_preparation_packets_ready_no_final_prose",
            {"publication_preparation_status": packets_summary.get("overall_status")},
            [rel(root / PREPARATION_PACKETS, root)],
            "publication_preparation_packets_not_ready",
        ),
        check_row(
            "reviewer_advice_count_contract_met",
            required_reviewer_count > 0
            and len(advice_by_reviewer) == required_reviewer_count
            and not reviewers_below_minimum,
            {
                "required_reviewer_count": required_reviewer_count,
                "reviewer_count": len(advice_by_reviewer),
                "minimum_recommendations_per_reviewer": minimum_recommendations,
                "advice_by_reviewer": dict(sorted(advice_by_reviewer.items())),
                "reviewers_below_minimum": reviewers_below_minimum,
            },
            [rel(root / POST_EXPERIMENT_PUBLICATION_PROGRAM, root)],
            "reviewer_advice_minimum_not_met",
        ),
        check_row(
            "required_advice_topics_covered",
            bool(required_topics) and not missing_topics,
            {
                "required_topic_count": len(required_topics),
                "covered_topic_count": len(topics_covered),
                "missing_topics": missing_topics,
            },
            [rel(root / POST_EXPERIMENT_PUBLICATION_PROGRAM, root)],
            "required_advice_topics_missing",
        ),
        check_row(
            "advice_schema_fields_present",
            bool(required_schema_fields)
            and all(row.get("schema_fields_present") for row in advice_records),
            {
                "required_schema_fields": required_schema_fields,
                "schema_violation_count": sum(
                    1 for row in advice_records if not row.get("schema_fields_present")
                ),
            },
            [rel(root / POST_EXPERIMENT_PUBLICATION_PROGRAM, root)],
            "advice_schema_fields_missing",
        ),
        check_row(
            "reconciliation_decisions_recorded",
            len(reconciliation_rows) == len(advice_records)
            and accepted_or_deferred_count == len(advice_records),
            {
                "advice_record_count": len(advice_records),
                "reconciliation_row_count": len(reconciliation_rows),
                "accepted_count": accepted_count,
                "deferred_count": deferred_count,
            },
            [rel(root / PREPARATION_PACKETS, root)],
            "reconciliation_missing_or_rejected",
        ),
        check_row(
            "content_matrix_sources_traceable",
            bool(content_matrix)
            and len(content_matrix)
            == safe_int(packets_summary.get("visual_table_candidate_family_count"))
            and all(row["source_artifact_count"] > 0 for row in content_matrix),
            {
                "content_matrix_row_count": len(content_matrix),
                "expected_visual_table_family_count": packets_summary.get(
                    "visual_table_candidate_family_count"
                ),
                "source_missing_content_area_ids": [
                    row["content_area_id"]
                    for row in content_matrix
                    if row["source_artifact_count"] == 0
                ],
            },
            [rel(root / PREPARATION_PACKETS, root)],
            "content_matrix_source_links_missing",
        ),
        check_row(
            "neutral_no_method_promotion_guard_preserved",
            neutral_guard_active,
            {
                "packet_guard": packets_summary.get(
                    "neutral_no_method_promotion_guard_active"
                ),
                "neutral_language_status": neutral_language_summary.get(
                    "overall_status"
                ),
                "unguarded_hit_count": neutral_language_summary.get(
                    "unguarded_hit_count"
                ),
            },
            [
                rel(root / PREPARATION_PACKETS, root),
                rel(root / NEUTRAL_LANGUAGE, root),
            ],
            "neutral_no_method_promotion_guard_not_clean",
        ),
        check_row(
            "private_research_document_authoring_context_recorded",
            private_manuscript_authoring_authorized,
            {
                "packet_private_manuscript_drafting_authorized": packets_summary.get(
                    "private_manuscript_drafting_authorized"
                ),
                "activation_private_manuscript_drafting_authorized": (
                    activation_summary.get("private_manuscript_drafting_authorized")
                ),
                "research_document_authoring_authorized": authoring_summary.get(
                    "research_document_authoring_authorized"
                ),
                "final_public_release_authorized": authoring_summary.get(
                    "final_public_release_authorized"
                ),
                "new_experiments_authorized": authoring_summary.get(
                    "new_experiments_authorized"
                ),
            },
            [
                rel(root / PREPARATION_PACKETS, root),
                rel(root / POST_EXPERIMENT_PUBLICATION_ACTIVATION, root),
                rel(root / PUBLICATION_AUTHORING_DECISION, root),
            ],
            "private_research_document_authoring_context_missing",
        ),
        check_row(
            "final_prose_visual_release_actions_remain_blocked",
            final_actions_blocked,
            {
                "manuscript_drafting_authorized": activation_summary.get(
                    "manuscript_drafting_authorized"
                ),
                "sterile_repository_creation_authorized": activation_summary.get(
                    "sterile_repository_creation_authorized"
                ),
                "site_deployment_authorized": site_decision_record.get(
                    "site_deployment_authorized"
                ),
                "content_matrix_final_decisions": Counter(
                    row["final_placement_decision"] for row in content_matrix
                ),
            },
            [rel(root / POST_EXPERIMENT_PUBLICATION_ACTIVATION, root)],
            "final_publication_action_unexpectedly_authorized",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] == "fail"]
    overall_status = (
        "reviewer_design_brief_ready_no_final_prose"
        if not failed_checks
        else "reviewer_design_brief_blocked"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "phase_state": (
                "neutral_pre_prose_design_active_final_prose_and_release_blocked"
            ),
            "private_manuscript_drafting_authorized": (
                private_manuscript_authoring_authorized
            ),
            "private_research_document_authoring_authorized": (
                authoring_summary.get("research_document_authoring_authorized") is True
            ),
            "reviewer_count": len(advice_by_reviewer),
            "required_reviewer_count": required_reviewer_count,
            "advice_record_count": len(advice_records),
            "minimum_recommendations_per_reviewer": minimum_recommendations,
            "accepted_advice_count": accepted_count,
            "deferred_advice_count": deferred_count,
            "required_advice_topic_count": len(required_topics),
            "covered_advice_topic_count": len(topics_covered),
            "content_matrix_row_count": len(content_matrix),
            "expected_visual_table_family_count": packets_summary.get(
                "visual_table_candidate_family_count"
            ),
            "publication_site_deployment_authorized": site_decision_record.get(
                "site_deployment_authorized"
            ),
            "neutral_no_method_promotion_guard_active": neutral_guard_active,
            "manuscript_drafting_authorized": activation_summary.get(
                "manuscript_drafting_authorized"
            ),
            "sterile_repository_creation_authorized": activation_summary.get(
                "sterile_repository_creation_authorized"
            ),
            "final_visual_table_retention_authorized": False,
            "final_manuscript_prose_permission": False,
            "final_retain_decision_authorized": False,
            "positive_claim_promotion_authorized": False,
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
        },
        "checks": checks,
        "failed_checks": [row["check_id"] for row in failed_checks],
        "claim_boundaries": [
            "Phase state: neutral pre-prose design is active; final prose and release remain blocked.",
            "This artifact records publication design advice, not manuscript prose.",
            "Accepted advice means accepted for design planning only.",
            "Deferred advice remains blocked by final prose, visual audit, sterile repository, or release gates.",
            "No row promotes CQR, CV+, Venn-Abers, fairness, bounded-support, production, or final-selection claims.",
            "The article, supplement, KG, and site placements are candidate design surfaces until downstream audits pass.",
        ],
        "reviewer_advice_records": advice_records,
        "reviewer_reconciliation_matrix": reconciliation_rows,
        "article_supplement_content_matrix": content_matrix,
        "publication_site_decision_record": site_decision_record,
        "sources": {
            "publication_preparation_packets": rel(root / PREPARATION_PACKETS, root),
            "post_experiment_publication_program": rel(
                root / POST_EXPERIMENT_PUBLICATION_PROGRAM, root
            ),
            "post_experiment_publication_activation": rel(
                root / POST_EXPERIMENT_PUBLICATION_ACTIVATION, root
            ),
            "publication_authoring_decision": rel(
                root / PUBLICATION_AUTHORING_DECISION, root
            ),
            "neutral_reporting_language": rel(root / NEUTRAL_LANGUAGE, root),
            "goal_completion": rel(root / GOAL_COMPLETION, root),
            "paper_gate_closure_map": rel(root / PAPER_GATE_CLOSURE, root),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Reviewer Design Brief",
        "",
        "This artifact records pre-prose reviewer advice and reconciliation only. It does not draft manuscript prose, select retained visuals, create a sterile repository, or promote positive claims.",
        "",
        f"- Generated UTC: `{payload['generated_at_utc']}`",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase state: `{summary_payload['phase_state']}`",
        f"- Reviewers: {summary_payload['reviewer_count']} / {summary_payload['required_reviewer_count']}",
        f"- Advice records: {summary_payload['advice_record_count']}",
        f"- Advice accepted for design: {summary_payload['accepted_advice_count']}",
        f"- Advice deferred by gates: {summary_payload['deferred_advice_count']}",
        f"- Required advice topics covered: {summary_payload['covered_advice_topic_count']} / {summary_payload['required_advice_topic_count']}",
        f"- Content matrix rows: {summary_payload['content_matrix_row_count']} / {summary_payload['expected_visual_table_family_count']}",
        f"- Neutral no-method-promotion guard active: `{summary_payload['neutral_no_method_promotion_guard_active']}`",
        f"- Private manuscript drafting authorized: `{summary_payload['private_manuscript_drafting_authorized']}`",
        f"- Private Research Document authoring authorized: `{summary_payload['private_research_document_authoring_authorized']}`",
        f"- Manuscript drafting authorized: `{summary_payload['manuscript_drafting_authorized']}`",
        f"- Sterile repository creation authorized: `{summary_payload['sterile_repository_creation_authorized']}`",
        f"- Final visual/table retention authorized: `{summary_payload['final_visual_table_retention_authorized']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Blocks design |",
        "|---|---:|---:|",
    ]
    for row in payload["checks"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['blocks_reviewer_design']}` |"
        )
    lines.extend(["", "## Advice By Reviewer", ""])
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["reviewer_advice_records"]:
        grouped[row["reviewer_id"]].append(row)
    for reviewer_id in sorted(grouped):
        lines.append(f"### {reviewer_id}")
        for row in grouped[reviewer_id]:
            lines.append(
                f"- `{row['recommendation_id']}`: `{row['accept_reject_defer_decision']}` "
                f"for `{row['advice_topic']}` -> `{row['mapped_artifact']}`"
            )
        lines.append("")
    lines.extend(["## Content Matrix", ""])
    for row in payload["article_supplement_content_matrix"]:
        lines.append(
            f"- `{row['content_area_id']}`: `{row['candidate_surface']}`, "
            f"placement `{row['placement_status']}`, final decision `{row['final_placement_decision']}`"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def write_sidecars(out: Path, payload: dict[str, Any]) -> None:
    base_dir = out.parent
    reconciliation = base_dir / "reviewer_reconciliation_matrix.json"
    content_matrix = base_dir / "article_supplement_content_matrix.json"
    site_decision = base_dir / "publication_site_decision_record.json"
    atomic_write_json(
        reconciliation,
        {
            "schema": "cpfi_regression_reviewer_reconciliation_matrix_v1",
            "generated_at_utc": payload["generated_at_utc"],
            "summary": {
                "overall_status": payload["summary"]["overall_status"],
                "phase_state": payload["summary"]["phase_state"],
                "row_count": len(payload["reviewer_reconciliation_matrix"]),
                "accepted_advice_count": payload["summary"]["accepted_advice_count"],
                "deferred_advice_count": payload["summary"]["deferred_advice_count"],
                "final_prose_authorized": False,
                "positive_claim_promotion_authorized": False,
            },
            "rows": payload["reviewer_reconciliation_matrix"],
            "claim_boundaries": payload["claim_boundaries"],
            "sources": payload["sources"],
        },
    )
    atomic_write_json(
        content_matrix,
        {
            "schema": "cpfi_regression_article_supplement_content_matrix_v1",
            "generated_at_utc": payload["generated_at_utc"],
            "summary": {
                "overall_status": payload["summary"]["overall_status"],
                "phase_state": payload["summary"]["phase_state"],
                "row_count": len(payload["article_supplement_content_matrix"]),
                "expected_visual_table_family_count": payload["summary"][
                    "expected_visual_table_family_count"
                ],
                "final_placement_decision_started_count": 0,
                "retained_visual_or_table_decision_started_count": 0,
            },
            "rows": payload["article_supplement_content_matrix"],
            "claim_boundaries": payload["claim_boundaries"],
            "sources": payload["sources"],
        },
    )
    atomic_write_json(
        site_decision,
        {
            "schema": "cpfi_regression_publication_site_decision_record_v1",
            "generated_at_utc": payload["generated_at_utc"],
            "summary": {
                "overall_status": payload["summary"]["overall_status"],
                "phase_state": payload["summary"]["phase_state"],
                "site_deployment_authorized": payload[
                    "publication_site_decision_record"
                ]["site_deployment_authorized"],
                "sterile_repository_required_before_deployment": payload[
                    "publication_site_decision_record"
                ]["sterile_repository_required_before_deployment"],
            },
            "record": payload["publication_site_decision_record"],
            "claim_boundaries": payload["claim_boundaries"],
            "sources": payload["sources"],
        },
    )


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    write_sidecars(out, payload)
    print(
        json.dumps(
            {
                "status": "ok" if not payload["failed_checks"] else "fail",
                "overall_status": payload["summary"]["overall_status"],
                "advice_record_count": payload["summary"]["advice_record_count"],
                "content_matrix_row_count": payload["summary"][
                    "content_matrix_row_count"
                ],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )
    if payload["failed_checks"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
