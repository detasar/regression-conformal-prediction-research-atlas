"""Reconcile post-experiment publication progress without authorizing release.

This audit is a pre-release control artifact. It records which publication
preparation controls are now complete, which old blockers are resolved, which
private review artifacts are ready, and which public final manuscript/release
blockers remain active. It must not recommend a conformal method, promote a
positive claim, retain final visuals/tables, authorize public final prose,
deploy a public site, or make the private sterile publication repository public.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_publication_phase_progress_reconciliation_audit_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/"
    "publication_phase_progress_reconciliation_audit.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

POST_PROGRAM = Path(
    "experiments/regression/manuscript/post_experiment_publication_program.json"
)
ACTIVATION = Path(
    "experiments/regression/manuscript/"
    "post_experiment_publication_activation_audit.json"
)
GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
PREPARATION_PACKETS = Path(
    "experiments/regression/manuscript/publication_preparation_packets.json"
)
REVIEWER_DESIGN = Path("experiments/regression/manuscript/reviewer_design_brief.json")
REVIEWER_RECONCILIATION = Path(
    "experiments/regression/manuscript/reviewer_reconciliation_matrix.json"
)
VISUAL_PLAN = Path("experiments/regression/manuscript/visual_table_audit_plan.json")
VISUAL_AUDIT = Path("experiments/regression/manuscript/visual_table_audit_report.json")
VISUAL_RENDER = Path(
    "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
)
RETENTION_READINESS = Path(
    "experiments/regression/manuscript/publication_retention_readiness_audit.json"
)
FINAL_VISUAL_AUDITOR = Path(
    "experiments/regression/manuscript/"
    "final_publication_visual_auditor_readiness.json"
)
BLUEPRINT_ALIGNMENT = Path(
    "experiments/regression/manuscript/article_supplement_blueprint_alignment.json"
)
RELEASE_GAP = Path(
    "experiments/regression/manuscript/publication_release_gap_register.json"
)
CLAIM_SAFE_MATRIX = Path(
    "experiments/regression/manuscript/claim_safe_result_extraction_matrix.json"
)
SECTION_PACKET = Path(
    "experiments/regression/manuscript/manuscript_section_evidence_packet.json"
)
SECTION_BOUNDARY = Path(
    "experiments/regression/manuscript/section_claim_boundary_audit.json"
)
NAVIGATION_INDEX = Path(
    "experiments/regression/manuscript/article_supplement_kg_navigation_index.json"
)
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
VENN_NEGATIVE = REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
KG_PUBLICATION = REPORT_DIR / "kg_publication_quality_audit.json"
KG_QUALITY = Path(
    "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
)
AUTHORING_DECISION = Path(
    "experiments/regression/manuscript/publication_authoring_decision_record.json"
)
RELEASE_CUT = Path(
    "experiments/regression/manuscript/neutral_publication_release_cut_decision.json"
)
PRIVATE_LATEX_HTML_MANIFEST = Path(
    "experiments/regression/manuscript/private_latex_html_review_outputs_manifest.json"
)
PRIVATE_LATEX_HTML_AUDIT = Path(
    "experiments/regression/manuscript/private_latex_html_review_output_audit.json"
)
PRIVATE_PACKAGE_MANIFEST = Path(
    "experiments/regression/manuscript/private_sterile_publication_package_manifest.json"
)
PRIVATE_REMOTE_AUDIT = Path(
    "experiments/regression/manuscript/private_publication_repository_remote_audit.json"
)

SOURCE_PATHS = {
    "post_experiment_publication_program": POST_PROGRAM,
    "post_experiment_publication_activation_audit": ACTIVATION,
    "goal_completion_audit": GOAL_COMPLETION,
    "publication_preparation_packets": PREPARATION_PACKETS,
    "reviewer_design_brief": REVIEWER_DESIGN,
    "reviewer_reconciliation_matrix": REVIEWER_RECONCILIATION,
    "visual_table_audit_plan": VISUAL_PLAN,
    "visual_table_audit_report": VISUAL_AUDIT,
    "visual_table_render_candidate_audit": VISUAL_RENDER,
    "publication_retention_readiness_audit": RETENTION_READINESS,
    "final_publication_visual_auditor_readiness": FINAL_VISUAL_AUDITOR,
    "article_supplement_blueprint_alignment": BLUEPRINT_ALIGNMENT,
    "publication_release_gap_register": RELEASE_GAP,
    "claim_safe_result_extraction_matrix": CLAIM_SAFE_MATRIX,
    "manuscript_section_evidence_packet": SECTION_PACKET,
    "section_claim_boundary_audit": SECTION_BOUNDARY,
    "article_supplement_kg_navigation_index": NAVIGATION_INDEX,
    "neutral_reporting_language_audit": NEUTRAL_LANGUAGE,
    "venn_abers_negative_evidence_disposition_audit": VENN_NEGATIVE,
    "kg_publication_quality_audit": KG_PUBLICATION,
    "knowledge_graph_quality_summary": KG_QUALITY,
    "publication_authoring_decision_record": AUTHORING_DECISION,
    "neutral_publication_release_cut_decision": RELEASE_CUT,
    "private_latex_html_review_outputs_manifest": PRIVATE_LATEX_HTML_MANIFEST,
    "private_latex_html_review_output_audit": PRIVATE_LATEX_HTML_AUDIT,
    "private_sterile_publication_package_manifest": PRIVATE_PACKAGE_MANIFEST,
    "private_publication_repository_remote_audit": PRIVATE_REMOTE_AUDIT,
}

RESOLVED_PRIOR_BLOCKERS = {
    "reviewer_design_reconciliation_pending": (
        "reviewer_design_and_reconciliation_ready"
    ),
    "visual_table_audit_pending": "visual_table_pre_retention_and_render_audits_ready",
}

ACTIVE_FINAL_BLOCKERS = [
    "final_manuscript_prose_not_authorized",
    "final_visual_table_retention_not_authorized",
    "latex_html_authoring_pending",
    "publication_site_deployment_not_authorized",
    "kg_citable_component_not_authorized",
    "sterile_repository_creation_not_authorized",
    "sterile_release_packaging_pending",
    "positive_claim_promotion_not_authorized",
    "method_recommendation_not_authorized",
    "six_positive_claim_gates_blocked",
]

PROMOTION_PHRASES = (
    "recommend cqr",
    "cqr is recommended",
    "cqr should be used",
    "cv+ is recommended",
    "venn-abers regression is validated",
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
    value = payload.get("summary") if isinstance(payload, dict) else {}
    return value if isinstance(value, dict) else {}


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def kg_publication_pre_release_ready(summary_payload: dict[str, Any]) -> bool:
    return (
        summary_payload.get("overall_status")
        in {"kg_publication_ready", "kg_publication_ready_with_polish_caveats"}
        and safe_int(summary_payload.get("hard_failed_check_count")) == 0
    )


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def rows_by_requirement(goal_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("requirement_id")): row
        for row in goal_payload.get("requirement_rows") or []
        if isinstance(row, dict) and row.get("requirement_id")
    }


def source_status(root: Path) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for source in SOURCE_PATHS.values():
        relative = rel(root / source, root)
        if (root / source).exists():
            present.append(relative)
        else:
            missing.append(relative)
    return present, missing


def status_row(
    *,
    control_id: str,
    status: str,
    evidence: dict[str, Any],
    source_artifacts: list[str],
    note: str,
) -> dict[str, Any]:
    return {
        "control_id": control_id,
        "status": status,
        "evidence": evidence,
        "source_artifacts": source_artifacts,
        "note": note,
    }


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


def no_promotion_text(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=True).lower()
    return not any(phrase in text for phrase in PROMOTION_PHRASES)


def build_payload(root: Path) -> dict[str, Any]:
    loaded = {name: read_json(root / path) for name, path in SOURCE_PATHS.items()}
    present_sources, missing_sources = source_status(root)

    post_program = loaded["post_experiment_publication_program"]
    activation_summary = summary(loaded["post_experiment_publication_activation_audit"])
    goal_payload = loaded["goal_completion_audit"]
    goal_summary = summary(goal_payload)
    goal_rows = rows_by_requirement(goal_payload)
    post_program_goal_row = goal_rows.get("post_experiment_publication_program", {})
    preparation_summary = summary(loaded["publication_preparation_packets"])
    reviewer_summary = summary(loaded["reviewer_design_brief"])
    reconciliation_summary = summary(loaded["reviewer_reconciliation_matrix"])
    visual_plan_summary = summary(loaded["visual_table_audit_plan"])
    visual_audit_summary = summary(loaded["visual_table_audit_report"])
    visual_render_summary = summary(loaded["visual_table_render_candidate_audit"])
    retention_summary = summary(loaded["publication_retention_readiness_audit"])
    final_visual_auditor_summary = summary(
        loaded["final_publication_visual_auditor_readiness"]
    )
    blueprint_summary = summary(loaded["article_supplement_blueprint_alignment"])
    release_gap_summary = summary(loaded["publication_release_gap_register"])
    claim_safe_summary = summary(loaded["claim_safe_result_extraction_matrix"])
    section_packet_summary = summary(loaded["manuscript_section_evidence_packet"])
    section_boundary_summary = summary(loaded["section_claim_boundary_audit"])
    navigation_summary = summary(loaded["article_supplement_kg_navigation_index"])
    neutral_language_summary = summary(loaded["neutral_reporting_language_audit"])
    venn_negative_summary = summary(
        loaded["venn_abers_negative_evidence_disposition_audit"]
    )
    kg_publication_summary = summary(loaded["kg_publication_quality_audit"])
    kg_quality_graph = loaded["knowledge_graph_quality_summary"].get("graph") or {}
    authoring_summary = summary(loaded["publication_authoring_decision_record"])
    release_cut_summary = summary(loaded["neutral_publication_release_cut_decision"])
    private_latex_html_summary = summary(
        loaded["private_latex_html_review_outputs_manifest"]
    )
    private_latex_html_audit_summary = summary(
        loaded["private_latex_html_review_output_audit"]
    )
    private_package_summary = summary(
        loaded["private_sterile_publication_package_manifest"]
    )
    private_remote_summary = summary(
        loaded["private_publication_repository_remote_audit"]
    )

    reviewer_ready = (
        reviewer_summary.get("overall_status")
        == "reviewer_design_brief_ready_no_final_prose"
        and safe_int(reviewer_summary.get("reviewer_count")) == 5
        and safe_int(reviewer_summary.get("failed_check_count")) == 0
        and reviewer_summary.get("manuscript_drafting_authorized") is False
        and reconciliation_summary.get("overall_status")
        == "reviewer_design_brief_ready_no_final_prose"
        and safe_int(reconciliation_summary.get("row_count")) >= 25
    )
    visual_pre_retention_ready = (
        visual_plan_summary.get("overall_status")
        == "publication_visual_audit_plan_ready_no_retained_artifacts"
        and visual_audit_summary.get("overall_status")
        == "visual_table_pre_retention_audit_completed_no_retained_artifacts"
        and visual_render_summary.get("overall_status")
        == "draft_visual_table_render_audit_completed_no_final_retention"
        and retention_summary.get("overall_status")
        == "publication_retention_readiness_ready_no_final_prose"
        and safe_int(visual_render_summary.get("layout_pass_count")) == 10
        and safe_int(visual_render_summary.get("svg_static_text_overlap_detected_count"))
        == 0
        and safe_int(retention_summary.get("recommendation_row_count")) == 10
        and retention_summary.get("final_visual_table_retention_authorized") is False
    )
    final_visual_auditor_ready = (
        final_visual_auditor_summary.get("overall_status")
        == "final_publication_visual_auditor_feedback_loop_ready_no_retention"
        and final_visual_auditor_summary.get(
            "final_publication_visual_auditor_status"
        )
        == "feedback_loop_ready_no_final_retention"
        and final_visual_auditor_summary.get("feedback_loop_ready") is True
        and safe_int(final_visual_auditor_summary.get("feedback_row_count")) == 10
        and safe_int(final_visual_auditor_summary.get("feedback_blocked_row_count"))
        == 0
        and safe_int(final_visual_auditor_summary.get("missing_rendered_artifact_count"))
        == 0
        and safe_int(final_visual_auditor_summary.get("failed_check_count")) == 0
        and final_visual_auditor_summary.get("final_visual_table_retention_authorized")
        is False
        and final_visual_auditor_summary.get("positive_claim_promotion_authorized")
        is False
    )
    claim_boundary_ready = (
        claim_safe_summary.get("overall_status")
        == "claim_safe_result_extraction_matrix_ready_no_final_claims"
        and section_packet_summary.get("overall_status")
        == "manuscript_section_evidence_packet_ready_no_final_prose"
        and section_boundary_summary.get("overall_status")
        == "section_claim_boundary_audit_pass_no_final_claims"
        and navigation_summary.get("overall_status")
        == "article_supplement_kg_navigation_index_ready_no_release"
        and section_boundary_summary.get("main_results_positive_boundary_blocked")
        is True
        and section_boundary_summary.get("venn_abers_negative_boundary_preserved")
        is True
    )
    release_gap_ready = (
        release_gap_summary.get("overall_status")
        == "publication_release_gap_register_ready_no_final_release"
        and safe_int(release_gap_summary.get("deliverable_row_count")) == 11
        and safe_int(release_gap_summary.get("release_authorized_count")) == 0
        and release_gap_summary.get("sterile_repository_creation_authorized") is False
    )
    private_authoring_ready = (
        authoring_summary.get("private_authoring_authorized") is True
        and authoring_summary.get("research_document_authoring_authorized") is True
        and authoring_summary.get("minimal_main_broad_supplement_authorized") is True
        and authoring_summary.get("public_repository_release_authorized") is False
    )
    private_latex_html_ready = (
        release_cut_summary.get("neutral_latex_html_static_site_package_authorized")
        is True
        and private_latex_html_summary.get("overall_status")
        == "private_latex_html_review_outputs_ready"
        and private_latex_html_audit_summary.get("overall_status")
        == "private_latex_html_review_output_audit_pass"
        and private_latex_html_summary.get("public_release_authorized") is False
    )
    private_package_ready = (
        private_package_summary.get("overall_status")
        == "private_sterile_publication_package_ready"
        and private_package_summary.get("public_release_authorized") is False
    )
    private_remote_ready = (
        private_remote_summary.get("overall_status")
        == "private_publication_repository_remote_ready"
        and private_remote_summary.get("remote_visibility") == "PRIVATE"
        and private_remote_summary.get("commit_match") is True
        and private_remote_summary.get("public_release_authorized") is False
    )
    private_review_ready = (
        private_authoring_ready
        and private_latex_html_ready
        and private_package_ready
        and private_remote_ready
    )
    kg_ready = (
        kg_publication_pre_release_ready(kg_publication_summary)
        and safe_int(kg_quality_graph.get("node_count")) >= 3358
        and safe_int(kg_quality_graph.get("edge_count")) >= 19160
        and safe_int(kg_quality_graph.get("isolated_node_count")) == 0
    )
    no_final_authorization = all(
        field_value is False
        for field_value in [
            activation_summary.get("manuscript_drafting_authorized"),
            release_gap_summary.get("final_manuscript_prose_permission"),
            release_gap_summary.get("final_visual_table_retention_authorized"),
            release_gap_summary.get("publication_site_deployment_authorized"),
            release_gap_summary.get("kg_citable_component_authorized"),
            release_gap_summary.get("sterile_repository_creation_authorized"),
            release_gap_summary.get("positive_claim_promotion_authorized"),
            release_gap_summary.get("method_recommendation_authorized"),
            navigation_summary.get("final_navigation_release_authorized"),
            navigation_summary.get("working_repository_final_citable"),
        ]
    )
    neutral_guard_ready = (
        neutral_language_summary.get("overall_status")
        == "neutral_reporting_language_audit_pass"
        and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
        and no_promotion_text(loaded)
        and goal_summary.get("positive_claim_publication_ready") is False
        and goal_summary.get("validated_venn_abers_regression_claim_ready") is False
        and venn_negative_summary.get("negative_result_reporting_ready") is True
    )

    pre_prose_controls = [
        status_row(
            control_id="publication_activation_ready",
            status=(
                "complete"
                if activation_summary.get("publication_phase_start_authorized") is True
                and activation_summary.get("publication_preparation_authorized")
                is True
                else "blocked"
            ),
            evidence={
                "overall_status": activation_summary.get("overall_status"),
                "publication_phase_start_authorized": activation_summary.get(
                    "publication_phase_start_authorized"
                ),
                "manuscript_drafting_authorized": activation_summary.get(
                    "manuscript_drafting_authorized"
                ),
            },
            source_artifacts=[rel(root / ACTIVATION, root)],
            note="Pre-prose publication preparation is active; final drafting is not.",
        ),
        status_row(
            control_id="publication_preparation_packets_ready",
            status=(
                "complete"
                if preparation_summary.get("overall_status")
                == "publication_preparation_packets_ready_no_final_prose"
                and safe_int(preparation_summary.get("reviewer_packet_count")) == 5
                else "blocked"
            ),
            evidence={
                "overall_status": preparation_summary.get("overall_status"),
                "reviewer_packet_count": preparation_summary.get(
                    "reviewer_packet_count"
                ),
                "visual_table_candidate_family_count": preparation_summary.get(
                    "visual_table_candidate_family_count"
                ),
            },
            source_artifacts=[rel(root / PREPARATION_PACKETS, root)],
            note="Reviewer and visual/table preparation packets are present.",
        ),
        status_row(
            control_id="reviewer_design_and_reconciliation_ready",
            status="complete" if reviewer_ready else "blocked",
            evidence={
                "reviewer_status": reviewer_summary.get("overall_status"),
                "reviewer_count": reviewer_summary.get("reviewer_count"),
                "reconciliation_status": reconciliation_summary.get("overall_status"),
                "reconciliation_row_count": reconciliation_summary.get("row_count"),
            },
            source_artifacts=[
                rel(root / REVIEWER_DESIGN, root),
                rel(root / REVIEWER_RECONCILIATION, root),
            ],
            note="The old reviewer-design pending blocker is resolved for pre-prose design.",
        ),
        status_row(
            control_id="visual_table_pre_retention_and_render_audits_ready",
            status="complete" if visual_pre_retention_ready else "blocked",
            evidence={
                "plan_status": visual_plan_summary.get("overall_status"),
                "pre_retention_status": visual_audit_summary.get("overall_status"),
                "render_status": visual_render_summary.get("overall_status"),
                "retention_status": retention_summary.get("overall_status"),
                "layout_pass_count": visual_render_summary.get("layout_pass_count"),
                "overlap_count": visual_render_summary.get(
                    "svg_static_text_overlap_detected_count"
                ),
            },
            source_artifacts=[
                rel(root / VISUAL_PLAN, root),
                rel(root / VISUAL_AUDIT, root),
                rel(root / VISUAL_RENDER, root),
                rel(root / RETENTION_READINESS, root),
            ],
            note="The old visual/table audit pending blocker is resolved for draft/pre-retention controls.",
        ),
        status_row(
            control_id="final_publication_visual_auditor_feedback_loop_ready",
            status="complete" if final_visual_auditor_ready else "blocked",
            evidence={
                "overall_status": final_visual_auditor_summary.get(
                    "overall_status"
                ),
                "auditor_status": final_visual_auditor_summary.get(
                    "final_publication_visual_auditor_status"
                ),
                "feedback_row_count": final_visual_auditor_summary.get(
                    "feedback_row_count"
                ),
                "feedback_item_count": final_visual_auditor_summary.get(
                    "feedback_item_count"
                ),
                "missing_rendered_artifact_count": (
                    final_visual_auditor_summary.get(
                        "missing_rendered_artifact_count"
                    )
                ),
            },
            source_artifacts=[rel(root / FINAL_VISUAL_AUDITOR, root)],
            note=(
                "The final visual/table auditor feedback loop is ready for "
                "future final-prose-stage review, with no final retention authorized."
            ),
        ),
        status_row(
            control_id="claim_safe_sections_and_navigation_ready",
            status="complete" if claim_boundary_ready else "blocked",
            evidence={
                "claim_safe_status": claim_safe_summary.get("overall_status"),
                "section_packet_status": section_packet_summary.get("overall_status"),
                "section_boundary_status": section_boundary_summary.get(
                    "overall_status"
                ),
                "navigation_status": navigation_summary.get("overall_status"),
                "main_results_positive_boundary_blocked": (
                    section_boundary_summary.get(
                        "main_results_positive_boundary_blocked"
                    )
                ),
                "venn_abers_negative_boundary_preserved": (
                    section_boundary_summary.get(
                        "venn_abers_negative_boundary_preserved"
                    )
                ),
            },
            source_artifacts=[
                rel(root / CLAIM_SAFE_MATRIX, root),
                rel(root / SECTION_PACKET, root),
                rel(root / SECTION_BOUNDARY, root),
                rel(root / NAVIGATION_INDEX, root),
            ],
            note="Reader-facing candidate surfaces are claim bounded and navigable.",
        ),
        status_row(
            control_id="release_gap_and_sterile_repo_deferment_ready",
            status="complete" if release_gap_ready else "blocked",
            evidence={
                "release_gap_status": release_gap_summary.get("overall_status"),
                "deliverable_row_count": release_gap_summary.get(
                    "deliverable_row_count"
                ),
                "release_authorized_count": release_gap_summary.get(
                    "release_authorized_count"
                ),
                "sterile_repository_status": release_gap_summary.get(
                    "sterile_repository_status"
                ),
            },
            source_artifacts=[rel(root / RELEASE_GAP, root)],
            note="Release targets are inventoried but all final release paths remain blocked.",
        ),
        status_row(
            control_id="neutral_reporting_and_kg_quality_ready",
            status="complete" if neutral_guard_ready and kg_ready else "blocked",
            evidence={
                "neutral_language_status": neutral_language_summary.get(
                    "overall_status"
                ),
                "unguarded_hit_count": neutral_language_summary.get(
                    "unguarded_hit_count"
                ),
                "kg_publication_status": kg_publication_summary.get("overall_status"),
                "kg_node_count": kg_quality_graph.get("node_count"),
                "kg_edge_count": kg_quality_graph.get("edge_count"),
            },
            source_artifacts=[
                rel(root / NEUTRAL_LANGUAGE, root),
                rel(root / KG_PUBLICATION, root),
                rel(root / KG_QUALITY, root),
            ],
            note="Neutral language and KG quality controls are available for pre-release planning.",
        ),
    ]
    private_review_milestones = [
        status_row(
            control_id="private_authoring_decision_ready",
            status="complete" if private_authoring_ready else "blocked",
            evidence={
                "overall_status": authoring_summary.get("overall_status"),
                "private_authoring_authorized": authoring_summary.get(
                    "private_authoring_authorized"
                ),
                "research_document_authoring_authorized": (
                    authoring_summary.get("research_document_authoring_authorized")
                ),
                "minimal_main_broad_supplement_authorized": (
                    authoring_summary.get("minimal_main_broad_supplement_authorized")
                ),
                "public_repository_release_authorized": (
                    authoring_summary.get("public_repository_release_authorized")
                ),
            },
            source_artifacts=[rel(root / AUTHORING_DECISION, root)],
            note="Private Research Document, main article, and supplement authoring are allowed for review only.",
        ),
        status_row(
            control_id="private_latex_html_review_outputs_ready",
            status="complete" if private_latex_html_ready else "blocked",
            evidence={
                "release_cut_status": release_cut_summary.get("overall_status"),
                "render_manifest_status": private_latex_html_summary.get(
                    "overall_status"
                ),
                "render_audit_status": private_latex_html_audit_summary.get(
                    "overall_status"
                ),
                "public_release_authorized": private_latex_html_summary.get(
                    "public_release_authorized"
                ),
            },
            source_artifacts=[
                rel(root / RELEASE_CUT, root),
                rel(root / PRIVATE_LATEX_HTML_MANIFEST, root),
                rel(root / PRIVATE_LATEX_HTML_AUDIT, root),
            ],
            note="Private LaTeX/HTML review outputs exist, but they are not public final manuscript outputs.",
        ),
        status_row(
            control_id="private_sterile_package_and_remote_ready",
            status="complete" if private_package_ready and private_remote_ready else "blocked",
            evidence={
                "private_package_status": private_package_summary.get("overall_status"),
                "private_remote_status": private_remote_summary.get("overall_status"),
                "private_remote_visibility": private_remote_summary.get(
                    "remote_visibility"
                ),
                "private_remote_commit_match": private_remote_summary.get(
                    "commit_match"
                ),
                "public_release_authorized": private_remote_summary.get(
                    "public_release_authorized"
                ),
            },
            source_artifacts=[
                rel(root / PRIVATE_PACKAGE_MANIFEST, root),
                rel(root / PRIVATE_REMOTE_AUDIT, root),
            ],
            note="The private package and private GitHub remote are synchronized for review only.",
        ),
    ]

    resolved_blockers = [
        {
            "blocker_id": blocker_id,
            "resolved_by_control_id": control_id,
            "status": "resolved",
        }
        for blocker_id, control_id in RESOLVED_PRIOR_BLOCKERS.items()
    ]
    active_blockers = [
        {
            "blocker_id": blocker_id,
            "status": "active",
            "reason": (
                "Final prose, retained artifacts, site/KG citation, sterile "
                "repository packaging, method recommendation, and positive claims "
                "remain downstream-gated."
            ),
        }
        for blocker_id in ACTIVE_FINAL_BLOCKERS
    ]
    goal_blockers = post_program_goal_row.get("blockers") or []
    stale_goal_blockers = [
        blocker
        for blocker in goal_blockers
        if blocker in RESOLVED_PRIOR_BLOCKERS and blocker not in ACTIVE_FINAL_BLOCKERS
    ]
    failed_controls = [
        row for row in pre_prose_controls if row.get("status") != "complete"
    ]
    failed_private_milestones = [
        row for row in private_review_milestones if row.get("status") != "complete"
    ]
    checks = [
        check_row(
            "all_required_sources_present",
            not missing_sources,
            {"missing_source_artifacts": missing_sources},
            "missing_reconciliation_source_artifact",
        ),
        check_row(
            "pre_prose_controls_complete",
            not failed_controls and len(pre_prose_controls) == 8,
            {
                "control_count": len(pre_prose_controls),
                "failed_control_ids": [
                    row["control_id"] for row in failed_controls
                ],
            },
            "pre_prose_publication_control_incomplete",
        ),
        check_row(
            "private_review_artifacts_ready",
            private_review_ready and not failed_private_milestones,
            {
                "private_authoring_ready": private_authoring_ready,
                "private_latex_html_ready": private_latex_html_ready,
                "private_package_ready": private_package_ready,
                "private_remote_ready": private_remote_ready,
                "failed_private_milestone_ids": [
                    row["control_id"] for row in failed_private_milestones
                ],
            },
            "private_review_artifact_readiness_incomplete",
        ),
        check_row(
            "resolved_prior_blockers_not_active_in_goal_row",
            not stale_goal_blockers,
            {
                "goal_row_blockers": goal_blockers,
                "stale_goal_blockers": stale_goal_blockers,
            },
            "goal_completion_publication_row_contains_resolved_blocker",
        ),
        check_row(
            "final_outputs_remain_blocked",
            no_final_authorization,
            {
                "manuscript_drafting_authorized": activation_summary.get(
                    "manuscript_drafting_authorized"
                ),
                "release_authorized_count": release_gap_summary.get(
                    "release_authorized_count"
                ),
                "working_repository_final_citable": navigation_summary.get(
                    "working_repository_final_citable"
                ),
            },
            "final_publication_output_authorized_too_early",
        ),
        check_row(
            "neutral_no_promotion_policy_preserved",
            neutral_guard_ready,
            {
                "positive_claim_publication_ready": goal_summary.get(
                    "positive_claim_publication_ready"
                ),
                "validated_venn_abers_regression_claim_ready": goal_summary.get(
                    "validated_venn_abers_regression_claim_ready"
                ),
                "venn_negative_reporting_ready": venn_negative_summary.get(
                    "negative_result_reporting_ready"
                ),
                "no_promotion_text": no_promotion_text(loaded),
            },
            "neutral_no_promotion_policy_failed",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    final_visual_agent = final_visual_auditor_summary.get(
        "final_publication_visual_auditor_status"
    ) or (post_program.get("visual_table_audit_agent") or {}).get("status")
    summary_payload = {
        "overall_status": (
            "publication_phase_progress_reconciliation_ready_no_final_outputs"
            if not failed_checks
            else "publication_phase_progress_reconciliation_blocked"
        ),
        "phase_state": (
            "neutral_publication_progress_reconciled_final_outputs_blocked"
        ),
        "pre_prose_completed_control_count": sum(
            row.get("status") == "complete" for row in pre_prose_controls
        ),
        "pre_prose_control_count": len(pre_prose_controls),
        "private_review_milestone_complete_count": sum(
            row.get("status") == "complete" for row in private_review_milestones
        ),
        "private_review_milestone_count": len(private_review_milestones),
        "resolved_prior_blocker_count": len(resolved_blockers),
        "active_final_blocker_count": len(active_blockers),
        "stale_goal_blocker_count": len(stale_goal_blockers),
        "stale_goal_blockers": stale_goal_blockers,
        "final_publication_visual_auditor_status": final_visual_agent,
        "pre_retention_visual_audit_completed": visual_pre_retention_ready,
        "final_publication_visual_auditor_feedback_ready": (
            final_visual_auditor_ready
        ),
        "reviewer_design_reconciled": reviewer_ready,
        "claim_boundary_navigation_ready": claim_boundary_ready,
        "release_gap_ready": release_gap_ready,
        "private_authoring_ready": private_authoring_ready,
        "private_latex_html_review_outputs_ready": private_latex_html_ready,
        "private_sterile_publication_package_ready": private_package_ready,
        "private_publication_repository_remote_ready": private_remote_ready,
        "private_publication_repository_visibility": private_remote_summary.get(
            "remote_visibility"
        ),
        "private_publication_repository_commit_match": private_remote_summary.get(
            "commit_match"
        ),
        "neutral_guard_ready": neutral_guard_ready,
        "kg_publication_ready": kg_ready,
        "source_artifact_count": len(present_sources),
        "missing_source_artifact_count": len(missing_sources),
        "goal_can_mark_complete": goal_summary.get("can_mark_goal_complete"),
        "goal_noncomplete_requirement_count": goal_summary.get(
            "noncomplete_requirement_count"
        ),
        "paper_blocked_gate_count": goal_summary.get("paper_blocked_gate_count"),
        "positive_claim_ready_gate_count": goal_summary.get(
            "positive_claim_ready_gate_count"
        ),
        "final_manuscript_prose_permission": False,
        "manuscript_drafting_authorized": False,
        "latex_html_authoring_authorized": False,
        "final_visual_table_retention_authorized": False,
        "publication_site_deployment_authorized": False,
        "kg_citable_component_authorized": False,
        "sterile_repository_creation_authorized": False,
        "working_repository_final_citable": False,
        "method_recommendation_authorized": False,
        "positive_claim_promotion_authorized": False,
        "main_results_positive_boundary_blocked": section_boundary_summary.get(
            "main_results_positive_boundary_blocked"
        ),
        "venn_abers_negative_boundary_preserved": section_boundary_summary.get(
            "venn_abers_negative_boundary_preserved"
        ),
        "validated_venn_abers_regression_claim_ready": goal_summary.get(
            "validated_venn_abers_regression_claim_ready"
        ),
        "neutral_language_unguarded_hit_count": neutral_language_summary.get(
            "unguarded_hit_count"
        ),
        "kg_node_count": kg_quality_graph.get("node_count"),
        "kg_edge_count": kg_quality_graph.get("edge_count"),
        "kg_isolated_node_count": kg_quality_graph.get("isolated_node_count"),
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary_payload,
        "claim_boundaries": [
            "This audit reconciles publication-preparation progress; it is not manuscript prose.",
            "Resolved reviewer/visual blockers mean pre-prose controls are complete, not that final article, supplement, KG, site, or sterile repository outputs are released.",
            "Private authoring, private LaTeX/HTML review outputs, and the private sterile package may be complete while public final prose, KG citation, GitHub Pages, and public repository release remain blocked.",
            "CQR/CV+ evidence may only be described as observed descriptive/diagnostic behavior under existing claim boundaries.",
            "Venn-Abers regression remains reportable only as observed negative/failure-mode evidence with no validated regression claim.",
            "No method recommendation, final winner claim, positive scientific claim, site deployment, citation target, or sterile repository creation is authorized here.",
        ],
        "pre_prose_control_rows": pre_prose_controls,
        "private_review_milestone_rows": private_review_milestones,
        "resolved_prior_blocker_rows": resolved_blockers,
        "active_final_blocker_rows": active_blockers,
        "checks": checks,
        "failed_checks": failed_checks,
        "sources": {name: rel(root / path, root) for name, path in SOURCE_PATHS.items()},
        "present_source_artifacts": present_sources,
        "missing_source_artifacts": missing_sources,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Publication Phase Progress Reconciliation Audit",
        "",
        "This pre-release audit reconciles completed preparation controls and private-review artifacts with still-blocked public final outputs. It does not authorize public final prose, final visual/table retention, public LaTeX/HTML release, KG/site release, public repository release, method recommendation, or positive claim promotion.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase: `{summary_payload['phase_state']}`",
        f"- Pre-prose controls complete: {summary_payload['pre_prose_completed_control_count']} / {summary_payload['pre_prose_control_count']}",
        f"- Private review milestones complete: {summary_payload['private_review_milestone_complete_count']} / {summary_payload['private_review_milestone_count']}",
        f"- Resolved prior blockers: {summary_payload['resolved_prior_blocker_count']}",
        f"- Active final blockers: {summary_payload['active_final_blocker_count']}",
        f"- Stale goal blockers: {summary_payload['stale_goal_blocker_count']}",
        f"- Final publication visual auditor status: `{summary_payload['final_publication_visual_auditor_status']}`",
        f"- Main positive boundary blocked: `{summary_payload['main_results_positive_boundary_blocked']}`",
        f"- Venn-Abers negative boundary preserved: `{summary_payload['venn_abers_negative_boundary_preserved']}`",
        f"- Private authoring ready: `{summary_payload['private_authoring_ready']}`",
        f"- Private LaTeX/HTML review outputs ready: `{summary_payload['private_latex_html_review_outputs_ready']}`",
        f"- Private sterile package ready: `{summary_payload['private_sterile_publication_package_ready']}`",
        f"- Private repository remote ready: `{summary_payload['private_publication_repository_remote_ready']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive-claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Completed Pre-Prose Controls",
        "",
        "| Control | Status | Note |",
        "|---|---:|---|",
    ]
    for row in payload["pre_prose_control_rows"]:
        note = str(row["note"]).replace("|", "\\|")
        lines.append(
            "| "
            f"`{row['control_id']}` | `{row['status']}` | "
            f"{note} |"
        )
    lines.extend(
        [
            "",
            "## Private Review Milestones",
            "",
            "| Milestone | Status | Note |",
            "|---|---:|---|",
        ]
    )
    for row in payload["private_review_milestone_rows"]:
        note = str(row["note"]).replace("|", "\\|")
        lines.append(
            "| "
            f"`{row['control_id']}` | `{row['status']}` | "
            f"{note} |"
        )
    lines.extend(
        [
            "",
            "## Active Final Blockers",
            "",
            "| Blocker | Status |",
            "|---|---:|",
        ]
    )
    for row in payload["active_final_blocker_rows"]:
        lines.append(f"| `{row['blocker_id']}` | `{row['status']}` |")
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Blocker |",
            "|---|---:|---|",
        ]
    )
    for check in payload["checks"]:
        lines.append(
            f"| `{check['check_id']}` | `{check['status']}` | `{check['blocker']}` |"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = Path(args.out)
    out = out if out.is_absolute() else root / out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "out": rel(out, root),
                "overall_status": payload["summary"]["overall_status"],
                "pre_prose_completed_control_count": payload["summary"][
                    "pre_prose_completed_control_count"
                ],
                "active_final_blocker_count": payload["summary"][
                    "active_final_blocker_count"
                ],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
