"""Build neutral visual/table audit and triptych planning artifacts.

This script is a pre-prose publication-preparation layer. It converts the
reviewer design brief and article/supplement content matrix into a visual/table
audit plan and a main-article/supplement/KG triptych decision record. It does
not render figures, retain tables, authorize manuscript prose, deploy a site,
or promote any method or claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_publication_visual_audit_plan_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/visual_table_audit_plan.json")
POST_EXPERIMENT_PUBLICATION_PROGRAM = Path(
    "experiments/regression/manuscript/post_experiment_publication_program.json"
)
REVIEWER_DESIGN_BRIEF = Path(
    "experiments/regression/manuscript/reviewer_design_brief.json"
)
ARTICLE_SUPPLEMENT_CONTENT_MATRIX = Path(
    "experiments/regression/manuscript/article_supplement_content_matrix.json"
)
PUBLICATION_SITE_DECISION_RECORD = Path(
    "experiments/regression/manuscript/publication_site_decision_record.json"
)
NEUTRAL_LANGUAGE = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "neutral_reporting_language_audit.json"
)
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
KG_PUBLICATION_QUALITY = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "kg_publication_quality_audit.json"
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


def existing_sources(root: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if (root / path).exists()]


def check_row(
    check_id: str,
    passed: bool,
    evidence: dict[str, Any],
    source_artifacts: list[str],
    blocker: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "blocks_visual_audit_plan": not passed,
        "evidence": evidence,
        "source_artifacts": source_artifacts,
        "blocker": blocker,
    }


def content_rows_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    rows = payload.get("article_supplement_content_matrix")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def build_candidate_audit_rows(
    root: Path,
    content_rows: list[dict[str, Any]],
    quality_checks: list[str],
) -> list[dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    allowed_decisions = [
        "revise",
        "move_to_supplement",
        "move_to_kg_or_site",
        "remove",
        "candidate_keep_pending_final_gates",
    ]
    for index, row in enumerate(content_rows, start=1):
        content_id = str(row.get("content_area_id") or f"candidate_{index:02d}")
        source_artifacts = existing_sources(root, list(row.get("source_artifacts") or []))
        audit_rows.append(
            {
                "audit_item_id": f"visual_table_audit_item:{content_id}",
                "content_area_id": content_id,
                "artifact_type": row.get("artifact_type"),
                "candidate_surface": row.get("candidate_surface"),
                "target_surfaces": row.get("target_surfaces") or [],
                "reader_question": row.get("reader_question"),
                "gate_dependency": row.get("gate_dependency"),
                "claim_boundary": row.get("claim_boundary"),
                "source_artifacts": source_artifacts,
                "source_artifact_count": len(source_artifacts),
                "required_quality_checks": quality_checks,
                "required_quality_check_count": len(quality_checks),
                "audit_status": "planned_not_started",
                "rendered_artifact_path": "",
                "auditor_decision": "not_started",
                "allowed_pre_retention_decisions": allowed_decisions,
                "final_retention_authorized": False,
                "final_placement_decision": "not_started",
                "retained_visual_or_table_decision": "not_started",
                "decision_scope": (
                    "visual_table_audit_planning_only_no_retained_artifacts"
                ),
            }
        )
    return audit_rows


def claim_role_for_content(content_area_id: str) -> str:
    role_by_content = {
        "experiment_scope_and_accounting_table": "scope_accounting_claim",
        "method_performance_descriptive_summary": "descriptive_method_behavior_claim",
        "method_selection_robustness_diagnostics": "post_selection_robustness_diagnostic",
        "post_selection_validation_diagnostics": "post_selection_validation_diagnostic",
        "venn_abers_failure_mode_evidence": "negative_failure_mode_claim",
        "bounded_support_endpoint_policy_table": "blocked_bounded_support_validity_claim",
        "fairness_group_diagnostic_tables": "diagnostic_group_evidence_no_population_fairness",
        "duplicate_split_caveat_inventory": "integrity_and_split_caveat_claim",
        "knowledge_graph_navigation_quality": "traceability_and_navigation_claim",
        "neutral_closure_and_claim_boundary_table": "claim_boundary_and_release_gate_claim",
    }
    return role_by_content.get(content_area_id, "visual_table_claim_boundary")


def reader_utility_for_content(content_area_id: str) -> str:
    utility_by_content = {
        "experiment_scope_and_accounting_table": (
            "Lets a reader see the empirical object before reading any result."
        ),
        "method_performance_descriptive_summary": (
            "Keeps observed method behavior compact without turning it into a recommendation."
        ),
        "method_selection_robustness_diagnostics": (
            "Shows whether the descriptive candidate pattern is stable under diagnostics."
        ),
        "post_selection_validation_diagnostics": (
            "Separates post-selection evidence from final selected-method language."
        ),
        "venn_abers_failure_mode_evidence": (
            "Makes the Venn-Abers bridge failure mode visible without rejecting the literature."
        ),
        "bounded_support_endpoint_policy_table": (
            "Shows why bounded-support validity remains closed."
        ),
        "fairness_group_diagnostic_tables": (
            "Shows group diagnostics without implying population fairness."
        ),
        "duplicate_split_caveat_inventory": (
            "Keeps duplicate, split, and caveat constraints visible to readers."
        ),
        "knowledge_graph_navigation_quality": (
            "Lets reviewers judge whether KG navigation is usable as a private trace surface."
        ),
        "neutral_closure_and_claim_boundary_table": (
            "Lists allowed, diagnostic, negative, and blocked readings in one place."
        ),
    }
    return utility_by_content.get(
        content_area_id,
        "Clarifies how a visual or table supports a bounded reader-facing claim.",
    )


def build_claim_linked_decision_rows(
    candidate_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(candidate_rows, start=1):
        content_area_id = str(row.get("content_area_id") or "")
        rows.append(
            {
                "decision_row_id": f"visual_table_claim_decision:{content_area_id}",
                "row_index": index,
                "content_area_id": content_area_id,
                "artifact_type": row.get("artifact_type"),
                "target_surfaces": row.get("target_surfaces") or [],
                "reader_question": row.get("reader_question"),
                "claim_role": claim_role_for_content(content_area_id),
                "reader_utility": reader_utility_for_content(content_area_id),
                "source_artifacts": row.get("source_artifacts") or [],
                "source_artifact_count": row.get("source_artifact_count"),
                "quality_check_count": row.get("required_quality_check_count"),
                "gate_dependency": row.get("gate_dependency"),
                "allowed_current_action": (
                    "plan_candidate_visual_or_table_for_private_review_only"
                ),
                "blocked_current_action": (
                    "render_retain_publish_or_use_as_final_claim_evidence"
                ),
                "overclaim_blocked": row.get("claim_boundary"),
                "audit_status": row.get("audit_status"),
                "auditor_decision": row.get("auditor_decision"),
                "final_retention_authorized": False,
                "public_release_authorized": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
            }
        )
    return rows


def build_triptych_rows(
    triptych: dict[str, Any],
    kg_quality_summary: dict[str, Any],
    kg_publication_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for component in list(triptych.get("components") or []):
        if component == "main_paper":
            status = "candidate_blueprint_only_no_prose"
            target = "main_article"
            dependency = "reviewer_reconciliation_and_visual_table_audit_gate"
        elif component == "supplementary_document":
            status = "candidate_blueprint_only_no_prose"
            target = "supplementary_document"
            dependency = "reviewer_reconciliation_and_visual_table_audit_gate"
        else:
            status = "candidate_deferred_until_kg_usability_release_gates"
            target = "knowledge_graph_or_publication_site"
            dependency = "kg_usability_disclosure_and_sterile_repository_review"
        rows.append(
            {
                "component_id": component,
                "target_surface": target,
                "decision_status": status,
                "gate_dependency": dependency,
                "kg_node_count": kg_quality_summary.get("node_count"),
                "kg_edge_count": kg_quality_summary.get("edge_count"),
                "kg_publication_status": kg_publication_summary.get(
                    "overall_status"
                ),
                "final_release_authorized": False,
                "citable_component_authorized": False,
                "claim_boundary": (
                    "Triptych planning only; final prose, KG citation, site "
                    "deployment, and release packaging remain blocked."
                ),
            }
        )
    return rows


def build_payload(root: Path) -> dict[str, Any]:
    program = read_json(root / POST_EXPERIMENT_PUBLICATION_PROGRAM)
    reviewer_design = read_json(root / REVIEWER_DESIGN_BRIEF)
    content_matrix = read_json(root / ARTICLE_SUPPLEMENT_CONTENT_MATRIX)
    site_record = read_json(root / PUBLICATION_SITE_DECISION_RECORD)
    neutral_language = read_json(root / NEUTRAL_LANGUAGE)
    kg_quality = read_json(root / KG_QUALITY)
    kg_publication = read_json(root / KG_PUBLICATION_QUALITY)

    reviewer_summary = summary(reviewer_design)
    content_summary = summary(content_matrix)
    site_summary = summary(site_record)
    neutral_summary = summary(neutral_language)
    kg_quality_summary = kg_quality.get("graph") or {}
    kg_publication_summary = summary(kg_publication)
    visual_agent = program.get("visual_table_audit_agent") or {}
    triptych = program.get("publication_triptych") or {}
    quality_checks = list(visual_agent.get("quality_checks") or [])
    scope = list(visual_agent.get("scope") or [])
    feedback_loop = list(visual_agent.get("feedback_loop") or [])
    required_outputs = list(visual_agent.get("required_output_artifacts") or [])
    content_rows = content_rows_from_payload(content_matrix)
    candidate_rows = build_candidate_audit_rows(root, content_rows, quality_checks)
    claim_linked_decision_rows = build_claim_linked_decision_rows(candidate_rows)
    triptych_rows = build_triptych_rows(
        triptych, kg_quality_summary, kg_publication_summary
    )

    neutral_guard_active = (
        reviewer_summary.get("neutral_no_method_promotion_guard_active") is True
        and neutral_summary.get("overall_status")
        == "neutral_reporting_language_audit_pass"
        and safe_int(neutral_summary.get("unguarded_hit_count")) == 0
    )
    all_candidate_rows_design_only = bool(candidate_rows) and all(
        row["audit_status"] == "planned_not_started"
        and row["auditor_decision"] == "not_started"
        and row["final_retention_authorized"] is False
        and row["final_placement_decision"] == "not_started"
        and row["retained_visual_or_table_decision"] == "not_started"
        for row in candidate_rows
    )
    all_sources_traceable = bool(candidate_rows) and all(
        row["source_artifact_count"] > 0 for row in candidate_rows
    )
    triptych_release_blocked = bool(triptych_rows) and all(
        row["final_release_authorized"] is False
        and row["citable_component_authorized"] is False
        for row in triptych_rows
    )
    visual_contract_present = (
        visual_agent.get("status") == "planned_not_started"
        and len(quality_checks) >= 10
        and len(scope) >= 5
        and len(feedback_loop) >= 5
        and len(required_outputs) >= 6
    )
    triptych_contract_present = (
        triptych.get("status") == "planned_if_kg_usability_passes"
        and len(triptych.get("components") or []) == 3
    )
    final_actions_blocked = (
        site_summary.get("site_deployment_authorized") is False
        and all_candidate_rows_design_only
        and triptych_release_blocked
    )
    claim_linked_decision_rows_complete = bool(claim_linked_decision_rows) and all(
        row["source_artifact_count"] > 0
        and row["quality_check_count"] == len(quality_checks)
        and row["reader_question"]
        and row["claim_role"]
        and row["reader_utility"]
        and row["overclaim_blocked"]
        and row["final_retention_authorized"] is False
        and row["public_release_authorized"] is False
        and row["method_recommendation_authorized"] is False
        and row["positive_claim_promotion_authorized"] is False
        for row in claim_linked_decision_rows
    )

    checks = [
        check_row(
            "reviewer_design_brief_ready",
            reviewer_summary.get("overall_status")
            == "reviewer_design_brief_ready_no_final_prose",
            {"reviewer_design_status": reviewer_summary.get("overall_status")},
            [rel(root / REVIEWER_DESIGN_BRIEF, root)],
            "reviewer_design_brief_not_ready",
        ),
        check_row(
            "content_matrix_complete",
            len(content_rows) == safe_int(
                content_summary.get("expected_visual_table_family_count")
            )
            == 10,
            {
                "content_row_count": len(content_rows),
                "expected_visual_table_family_count": content_summary.get(
                    "expected_visual_table_family_count"
                ),
            },
            [rel(root / ARTICLE_SUPPLEMENT_CONTENT_MATRIX, root)],
            "content_matrix_incomplete",
        ),
        check_row(
            "visual_table_audit_contract_present",
            visual_contract_present,
            {
                "quality_check_count": len(quality_checks),
                "scope_count": len(scope),
                "feedback_loop_step_count": len(feedback_loop),
                "required_output_artifact_count": len(required_outputs),
            },
            [rel(root / POST_EXPERIMENT_PUBLICATION_PROGRAM, root)],
            "visual_table_audit_contract_missing",
        ),
        check_row(
            "triptych_contract_present",
            triptych_contract_present,
            {
                "triptych_status": triptych.get("status"),
                "component_count": len(triptych.get("components") or []),
            },
            [rel(root / POST_EXPERIMENT_PUBLICATION_PROGRAM, root)],
            "triptych_contract_missing",
        ),
        check_row(
            "candidate_rows_remain_design_only",
            all_candidate_rows_design_only,
            {
                "candidate_artifact_count": len(candidate_rows),
                "audit_status_counts": dict(
                    Counter(row["audit_status"] for row in candidate_rows)
                ),
                "auditor_decision_counts": dict(
                    Counter(row["auditor_decision"] for row in candidate_rows)
                ),
            },
            [rel(root / ARTICLE_SUPPLEMENT_CONTENT_MATRIX, root)],
            "candidate_visual_table_row_started_or_retained",
        ),
        check_row(
            "candidate_sources_traceable",
            all_sources_traceable,
            {
                "candidate_artifact_count": len(candidate_rows),
                "source_missing_candidate_ids": [
                    row["content_area_id"]
                    for row in candidate_rows
                    if row["source_artifact_count"] == 0
                ],
            },
            [rel(root / ARTICLE_SUPPLEMENT_CONTENT_MATRIX, root)],
            "candidate_visual_table_sources_missing",
        ),
        check_row(
            "triptych_release_and_citation_blocked",
            triptych_release_blocked,
            {
                "triptych_component_count": len(triptych_rows),
                "citable_component_authorized_count": sum(
                    1 for row in triptych_rows if row["citable_component_authorized"]
                ),
                "final_release_authorized_count": sum(
                    1 for row in triptych_rows if row["final_release_authorized"]
                ),
            },
            [
                rel(root / KG_QUALITY, root),
                rel(root / KG_PUBLICATION_QUALITY, root),
            ],
            "triptych_component_unexpectedly_authorized",
        ),
        check_row(
            "neutral_no_method_promotion_guard_preserved",
            neutral_guard_active,
            {
                "reviewer_design_guard": reviewer_summary.get(
                    "neutral_no_method_promotion_guard_active"
                ),
                "neutral_language_status": neutral_summary.get("overall_status"),
                "unguarded_hit_count": neutral_summary.get("unguarded_hit_count"),
            },
            [
                rel(root / REVIEWER_DESIGN_BRIEF, root),
                rel(root / NEUTRAL_LANGUAGE, root),
            ],
            "neutral_no_method_promotion_guard_not_clean",
        ),
        check_row(
            "final_visual_site_release_actions_remain_blocked",
            final_actions_blocked,
            {
                "site_deployment_authorized": site_summary.get(
                    "site_deployment_authorized"
                ),
                "candidate_final_retention_authorized_count": sum(
                    1 for row in candidate_rows if row["final_retention_authorized"]
                ),
                "triptych_release_blocked": triptych_release_blocked,
            },
            [rel(root / PUBLICATION_SITE_DECISION_RECORD, root)],
            "final_visual_site_release_unexpectedly_authorized",
        ),
        check_row(
            "claim_linked_decision_rows_complete",
            claim_linked_decision_rows_complete,
            {
                "claim_linked_decision_row_count": len(
                    claim_linked_decision_rows
                ),
                "expected_candidate_artifact_count": content_summary.get(
                    "expected_visual_table_family_count"
                ),
                "authorized_final_retention_count": sum(
                    1
                    for row in claim_linked_decision_rows
                    if row["final_retention_authorized"]
                ),
                "authorized_positive_claim_count": sum(
                    1
                    for row in claim_linked_decision_rows
                    if row["positive_claim_promotion_authorized"]
                ),
            },
            [rel(root / ARTICLE_SUPPLEMENT_CONTENT_MATRIX, root)],
            "claim_linked_visual_table_decisions_incomplete",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] == "fail"]
    overall_status = (
        "publication_visual_audit_plan_ready_no_retained_artifacts"
        if not failed_checks
        else "publication_visual_audit_plan_blocked"
    )
    generated_at = datetime.now(timezone.utc).isoformat()

    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "summary": {
            "overall_status": overall_status,
            "phase_state": (
                "neutral_pre_prose_visual_audit_planning_active_"
                "final_visuals_and_release_blocked"
            ),
            "candidate_artifact_count": len(candidate_rows),
            "claim_linked_decision_row_count": len(claim_linked_decision_rows),
            "expected_candidate_artifact_count": content_summary.get(
                "expected_visual_table_family_count"
            ),
            "visual_table_quality_check_count": len(quality_checks),
            "visual_table_scope_count": len(scope),
            "visual_table_feedback_loop_step_count": len(feedback_loop),
            "visual_table_required_output_artifact_count": len(required_outputs),
            "triptych_component_count": len(triptych_rows),
            "triptych_decision_status": (
                "candidate_triptych_deferred_until_kg_usability_release_gates"
            ),
            "kg_citable_component_authorized": False,
            "publication_site_deployment_authorized": site_summary.get(
                "site_deployment_authorized"
            ),
            "visual_table_audit_plan_authorized": True,
            "visual_table_audit_execution_authorized": False,
            "final_visual_table_retention_authorized": False,
            "final_triptych_release_authorized": False,
            "final_manuscript_prose_permission": False,
            "positive_claim_promotion_authorized": False,
            "neutral_no_method_promotion_guard_active": neutral_guard_active,
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
        },
        "checks": checks,
        "failed_checks": [row["check_id"] for row in failed_checks],
        "visual_table_audit_contract": {
            "agent_role": visual_agent.get("agent_role"),
            "agent_contract": visual_agent.get("agent_contract") or {},
            "scope": scope,
            "quality_checks": quality_checks,
            "acceptance_rule": visual_agent.get("acceptance_rule"),
            "iteration_rule": visual_agent.get("iteration_rule"),
            "feedback_loop": feedback_loop,
            "required_output_artifacts": required_outputs,
        },
        "candidate_audit_rows": candidate_rows,
        "claim_linked_decision_rows": claim_linked_decision_rows,
        "article_supplement_kg_triptych_decision": {
            "schema": "cpfi_regression_article_supplement_kg_triptych_decision_v1",
            "generated_at_utc": generated_at,
            "summary": {
                "overall_status": overall_status,
                "phase_state": (
                    "neutral_pre_prose_visual_audit_planning_active_"
                    "final_visuals_and_release_blocked"
                ),
                "component_count": len(triptych_rows),
                "triptych_decision_status": (
                    "candidate_triptych_deferred_until_kg_usability_release_gates"
                ),
                "kg_citable_component_authorized": False,
                "publication_site_deployment_authorized": site_summary.get(
                    "site_deployment_authorized"
                ),
                "final_triptych_release_authorized": False,
                "positive_claim_promotion_authorized": False,
            },
            "components": triptych_rows,
            "design_rule": triptych.get("design_rule"),
            "decision_rule": triptych.get("decision_rule"),
        },
        "claim_boundaries": [
            "This artifact plans visual/table audit work; it does not render, retain, or publish artifacts.",
            "The triptych is a candidate design decision only; KG citation and site deployment remain blocked.",
            "No visual/table row authorizes final manuscript prose or retained artifact selection.",
            "No row promotes CQR, CV+, Venn-Abers, fairness, bounded-support, production, or final-selection claims.",
        ],
        "sources": {
            "post_experiment_publication_program": rel(
                root / POST_EXPERIMENT_PUBLICATION_PROGRAM, root
            ),
            "reviewer_design_brief": rel(root / REVIEWER_DESIGN_BRIEF, root),
            "article_supplement_content_matrix": rel(
                root / ARTICLE_SUPPLEMENT_CONTENT_MATRIX, root
            ),
            "publication_site_decision_record": rel(
                root / PUBLICATION_SITE_DECISION_RECORD, root
            ),
            "neutral_reporting_language": rel(root / NEUTRAL_LANGUAGE, root),
            "kg_quality": rel(root / KG_QUALITY, root),
            "kg_publication_quality": rel(root / KG_PUBLICATION_QUALITY, root),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Visual/Table Audit Plan",
        "",
        "This artifact is a pre-prose visual/table audit plan. It does not render figures, retain tables, authorize manuscript prose, deploy a site, or promote claims.",
        "",
        f"- Generated UTC: `{payload['generated_at_utc']}`",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase state: `{summary_payload['phase_state']}`",
        f"- Candidate artifacts: {summary_payload['candidate_artifact_count']} / {summary_payload['expected_candidate_artifact_count']}",
        f"- Claim-linked decision rows: {summary_payload['claim_linked_decision_row_count']}",
        f"- Quality checks: {summary_payload['visual_table_quality_check_count']}",
        f"- Scope classes: {summary_payload['visual_table_scope_count']}",
        f"- Feedback-loop steps: {summary_payload['visual_table_feedback_loop_step_count']}",
        f"- Required output artifact names: {summary_payload['visual_table_required_output_artifact_count']}",
        f"- Triptych components: {summary_payload['triptych_component_count']}",
        f"- Visual audit execution authorized: `{summary_payload['visual_table_audit_execution_authorized']}`",
        f"- Final visual/table retention authorized: `{summary_payload['final_visual_table_retention_authorized']}`",
        f"- KG citable component authorized: `{summary_payload['kg_citable_component_authorized']}`",
        f"- Site deployment authorized: `{summary_payload['publication_site_deployment_authorized']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Blocks plan |",
        "|---|---:|---:|",
    ]
    for row in payload["checks"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['blocks_visual_audit_plan']}` |"
        )
    lines.extend(["", "## Candidate Audit Rows", ""])
    for row in payload["candidate_audit_rows"]:
        lines.append(
            f"- `{row['content_area_id']}`: `{row['artifact_type']}`, "
            f"audit `{row['audit_status']}`, decision `{row['auditor_decision']}`, "
            f"final retention `{row['final_retention_authorized']}`"
        )
    lines.extend(
        [
            "",
            "## Claim-Linked Visual/Table Decision Matrix",
            "",
            "| Candidate | Claim role | Reader utility | Current action | Blocked action |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["claim_linked_decision_rows"]:
        lines.append(
            "| "
            f"`{row['content_area_id']}` | "
            f"`{row['claim_role']}` | "
            f"{row['reader_utility']} | "
            f"`{row['allowed_current_action']}` | "
            f"`{row['blocked_current_action']}` |"
        )
    lines.extend(["", "## Triptych Components", ""])
    for row in payload["article_supplement_kg_triptych_decision"]["components"]:
        lines.append(
            f"- `{row['component_id']}` -> `{row['target_surface']}`: "
            f"`{row['decision_status']}`"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def write_sidecars(out: Path, payload: dict[str, Any]) -> None:
    base_dir = out.parent
    triptych_json = base_dir / "article_supplement_kg_triptych_decision.json"
    triptych_md = base_dir / "article_supplement_kg_triptych_decision.md"
    atomic_write_json(
        triptych_json,
        {
            **payload["article_supplement_kg_triptych_decision"],
            "claim_boundaries": payload["claim_boundaries"],
            "sources": payload["sources"],
        },
    )
    triptych_lines = [
        "# Article/Supplement/KG Triptych Decision",
        "",
        "This artifact records a candidate triptych design only. Final prose, KG citation, site deployment, and release packaging remain blocked.",
        "",
        f"- Overall status: `{payload['summary']['overall_status']}`",
        f"- Decision status: `{payload['summary']['triptych_decision_status']}`",
        f"- KG citable component authorized: `{payload['summary']['kg_citable_component_authorized']}`",
        f"- Final triptych release authorized: `{payload['summary']['final_triptych_release_authorized']}`",
        "",
        "## Components",
        "",
    ]
    for row in payload["article_supplement_kg_triptych_decision"]["components"]:
        triptych_lines.append(
            f"- `{row['component_id']}`: `{row['decision_status']}`, "
            f"release `{row['final_release_authorized']}`, citable `{row['citable_component_authorized']}`"
        )
    triptych_lines.append("")
    atomic_write_text(triptych_md, "\n".join(triptych_lines))


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
                "candidate_artifact_count": payload["summary"][
                    "candidate_artifact_count"
                ],
                "triptych_component_count": payload["summary"][
                    "triptych_component_count"
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
