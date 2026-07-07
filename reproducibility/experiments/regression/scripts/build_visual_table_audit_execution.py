"""Build pre-retention visual/table audit execution artifacts.

This script performs the first visual/table auditor pass over candidate
publication artifacts. It audits source traceability, claim boundaries, reader
utility, placement scope, and required follow-up before rendering. It does not
render figures, retain tables, authorize manuscript prose, deploy a site, or
promote any method or claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_visual_table_audit_execution_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/visual_table_audit_report.json")
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
VISUAL_TABLE_AUDIT_PLAN = Path(
    "experiments/regression/manuscript/visual_table_audit_plan.json"
)
ARTICLE_SUPPLEMENT_CONTENT_MATRIX = Path(
    "experiments/regression/manuscript/article_supplement_content_matrix.json"
)
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
KG_PUBLICATION_QUALITY = REPORT_DIR / "kg_publication_quality_audit.json"


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
        "blocks_pre_retention_audit": not passed,
        "evidence": evidence,
        "source_artifacts": source_artifacts,
        "blocker": blocker,
    }


def source_digest(root: Path, source_path: str) -> dict[str, Any]:
    path = root / source_path
    row: dict[str, Any] = {
        "source_artifact": source_path,
        "exists": path.exists(),
        "suffix": path.suffix,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "summary_present": False,
        "summary_key_count": 0,
        "summary_status_fields": {},
    }
    if not path.exists() or path.suffix.lower() != ".json":
        return row
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        row["json_read_error"] = True
        return row
    source_summary = summary(payload)
    row["summary_present"] = bool(source_summary)
    row["summary_key_count"] = len(source_summary)
    status_fields: dict[str, Any] = {}
    for key in (
        "overall_status",
        "claim_status",
        "final_selection_claim_status",
        "can_support_final_method_selection",
        "can_support_validated_venn_abers_regression",
        "can_support_bounded_support_validity",
        "can_support_publication_ready_fairness",
        "failed_check_count",
        "positive_claim_ready_gate_count",
        "unsupported_claim_hits",
    ):
        if key in source_summary:
            status_fields[key] = source_summary[key]
    row["summary_status_fields"] = status_fields
    return row


def pre_retention_decision(row: dict[str, Any]) -> str:
    content_id = str(row.get("content_area_id") or "")
    target_surfaces = set(row.get("target_surfaces") or [])
    gate_dependency = str(row.get("gate_dependency") or "")
    if content_id == "knowledge_graph_navigation_quality":
        return "move_to_kg_or_site_pending_release_gates"
    if "supplementary_document" in target_surfaces and "main_article" not in target_surfaces:
        return "move_to_supplement_pending_render_audit"
    if gate_dependency:
        return "revise_claim_boundary_before_main_article_use"
    return "candidate_keep_pending_render_audit"


def placement_note(row: dict[str, Any], decision: str) -> str:
    if decision == "move_to_kg_or_site_pending_release_gates":
        return "KG/site candidate only; citable or deployed status remains blocked."
    if decision == "move_to_supplement_pending_render_audit":
        return "Supplement candidate pending rendered artifact and final audit."
    if decision == "revise_claim_boundary_before_main_article_use":
        return "Main-article use requires a tighter no-claim caption and caveat note."
    return "Main/supplement candidate pending rendered artifact and final audit."


def feedback_items(row: dict[str, Any], decision: str) -> list[str]:
    items = [
        "Render a concrete figure or table before any layout, overlap, or resolution judgment.",
        "Attach source artifact paths, denominators, and caveat fields directly to the caption or table note.",
        "State the claim boundary without converting diagnostic, negative, scoped, or blocked evidence into a positive claim.",
    ]
    if decision == "revise_claim_boundary_before_main_article_use":
        items.append(
            "If used in the main article, keep the blocked gate dependency visible in the caption."
        )
    elif decision == "move_to_supplement_pending_render_audit":
        items.append(
            "Use the supplement as the default surface unless the rendered artifact proves compact and reader-critical."
        )
    elif decision == "move_to_kg_or_site_pending_release_gates":
        items.append(
            "Do not cite or deploy the KG/site surface until release, disclosure, and sterile-repository gates pass."
        )
    else:
        items.append(
            "Keep the main-article version compact and move detailed accounting to the supplement."
        )
    return items


def audit_rows(root: Path, candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidate_rows, start=1):
        source_artifacts = list(candidate.get("source_artifacts") or [])
        source_rows = [source_digest(root, path) for path in source_artifacts]
        missing_sources = [
            row["source_artifact"] for row in source_rows if not row["exists"]
        ]
        decision = pre_retention_decision(candidate)
        rows.append(
            {
                "audit_execution_id": (
                    f"visual_table_pre_retention_audit:{candidate.get('content_area_id')}"
                ),
                "audit_order": index,
                "content_area_id": candidate.get("content_area_id"),
                "artifact_type": candidate.get("artifact_type"),
                "candidate_surface": candidate.get("candidate_surface"),
                "target_surfaces": candidate.get("target_surfaces") or [],
                "reader_question": candidate.get("reader_question"),
                "claim_boundary": candidate.get("claim_boundary"),
                "gate_dependency": candidate.get("gate_dependency"),
                "source_artifacts": source_artifacts,
                "source_artifact_count": len(source_artifacts),
                "source_digest": source_rows,
                "missing_source_artifacts": missing_sources,
                "source_traceability_status": (
                    "pass" if not missing_sources and source_artifacts else "fail"
                ),
                "scientific_utility_status": (
                    "pass" if candidate.get("reader_question") else "fail"
                ),
                "claim_boundary_status": (
                    "pass" if candidate.get("claim_boundary") else "fail"
                ),
                "placement_scope_status": (
                    "pass" if candidate.get("target_surfaces") else "fail"
                ),
                "required_quality_check_count": candidate.get(
                    "required_quality_check_count"
                ),
                "rendered_artifact_path": "",
                "rendered_artifact_status": "not_rendered",
                "layout_overlap_check_status": "deferred_until_rendered_artifact",
                "accessibility_resolution_check_status": (
                    "deferred_until_rendered_artifact"
                ),
                "caption_quality_check_status": "deferred_until_rendered_artifact",
                "pre_retention_audit_status": "completed",
                "pre_retention_auditor_decision": decision,
                "pre_retention_placement_note": placement_note(candidate, decision),
                "actionable_feedback": feedback_items(candidate, decision),
                "actionable_feedback_count": len(feedback_items(candidate, decision)),
                "iteration_required": True,
                "iteration_reason": (
                    "Rendered artifact and final placement review are still required "
                    "before any retention decision."
                ),
                "final_retention_authorized": False,
                "final_placement_decision": "not_started",
                "retained_visual_or_table_decision": "not_started",
                "decision_scope": (
                    "pre_retention_audit_only_no_final_artifact_selection"
                ),
            }
        )
    return rows


def build_inventory(audited_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "cpfi_regression_visual_table_inventory_v1",
        "summary": {
            "inventory_row_count": len(audited_rows),
            "rendered_artifact_count": sum(
                1 for row in audited_rows if row["rendered_artifact_path"]
            ),
            "final_retained_artifact_count": sum(
                1 for row in audited_rows if row["final_retention_authorized"]
            ),
            "source_traceable_row_count": sum(
                1 for row in audited_rows if row["source_traceability_status"] == "pass"
            ),
            "final_retention_authorized": False,
        },
        "rows": [
            {
                "content_area_id": row["content_area_id"],
                "artifact_type": row["artifact_type"],
                "target_surfaces": row["target_surfaces"],
                "rendered_artifact_path": row["rendered_artifact_path"],
                "source_artifacts": row["source_artifacts"],
                "pre_retention_auditor_decision": row[
                    "pre_retention_auditor_decision"
                ],
                "final_retention_authorized": row["final_retention_authorized"],
            }
            for row in audited_rows
        ],
    }


def build_iteration_register(audited_rows: list[dict[str, Any]]) -> dict[str, Any]:
    actions = []
    for row in audited_rows:
        actions.append(
            {
                "action_id": f"render_and_reaudit:{row['content_area_id']}",
                "content_area_id": row["content_area_id"],
                "action_status": "planned_not_started",
                "required_before": "final_visual_table_retention",
                "pre_retention_auditor_decision": row[
                    "pre_retention_auditor_decision"
                ],
                "feedback": row["actionable_feedback"],
                "final_retention_authorized": False,
            }
        )
    return {
        "schema": "cpfi_regression_visual_table_iteration_register_v1",
        "summary": {
            "iteration_action_count": len(actions),
            "planned_not_started_action_count": len(actions),
            "completed_iteration_action_count": 0,
            "final_retention_authorized": False,
        },
        "actions": actions,
    }


def build_kg_usability_audit(
    kg_quality_summary: dict[str, Any],
    kg_traceability_summary: dict[str, Any],
    kg_issue_counts: dict[str, Any],
    kg_publication_summary: dict[str, Any],
    kg_row: dict[str, Any] | None,
) -> dict[str, Any]:
    node_count = safe_int(kg_quality_summary.get("node_count"))
    edge_count = safe_int(kg_quality_summary.get("edge_count"))
    isolated = safe_int(kg_quality_summary.get("isolated_node_count"))
    publication_node_count = safe_int(kg_publication_summary.get("node_count"))
    publication_edge_count = safe_int(kg_publication_summary.get("edge_count"))
    publication_isolated = safe_int(kg_publication_summary.get("isolated_node_count"))
    publication_metric_match = (
        publication_node_count == node_count
        and publication_edge_count == edge_count
        and publication_isolated == isolated
    )
    selector_coverage = float(
        kg_traceability_summary.get("edge_selector_provenance_coverage") or 0.0
    )
    release_ready = (
        node_count > 0
        and edge_count > 0
        and isolated == 0
        and selector_coverage >= 1.0
        and not kg_issue_counts
        and kg_publication_summary.get("tracked_missing_source_count") == 0
        and kg_publication_summary.get("relevant_untracked_source_count") == 0
        and publication_metric_match
    )
    return {
        "schema": "cpfi_regression_kg_navigation_usability_audit_v1",
        "summary": {
            "overall_status": (
                "kg_navigation_internal_ready_release_blocked"
                if release_ready
                else "kg_navigation_audit_blocked"
            ),
            "node_count": node_count,
            "edge_count": edge_count,
            "isolated_node_count": isolated,
            "publication_node_count": publication_node_count,
            "publication_edge_count": publication_edge_count,
            "publication_isolated_node_count": publication_isolated,
            "publication_metric_match": publication_metric_match,
            "edge_selector_provenance_coverage": selector_coverage,
            "publication_quality_status": kg_publication_summary.get(
                "overall_status"
            ),
            "kg_navigation_candidate_row_present": kg_row is not None,
            "kg_citable_component_authorized": False,
            "publication_site_deployment_authorized": False,
            "final_triptych_release_authorized": False,
            "release_gate_status": "blocked_until_sterile_repository_and_disclosure_review",
        },
        "candidate_row": kg_row or {},
        "claim_boundary": (
            "KG navigation can support internal evidence review, but citation or "
            "site deployment remains blocked until release gates pass."
        ),
    }


def build_payload(root: Path) -> dict[str, Any]:
    visual_plan = read_json(root / VISUAL_TABLE_AUDIT_PLAN)
    content_matrix = read_json(root / ARTICLE_SUPPLEMENT_CONTENT_MATRIX)
    neutral_language = read_json(root / NEUTRAL_LANGUAGE)
    kg_quality = read_json(root / KG_QUALITY)
    kg_publication = read_json(root / KG_PUBLICATION_QUALITY)

    visual_summary = summary(visual_plan)
    content_summary = summary(content_matrix)
    neutral_summary = summary(neutral_language)
    kg_quality_summary = kg_quality.get("graph") or {}
    kg_traceability_summary = kg_quality.get("traceability") or {}
    kg_issue_counts = kg_quality.get("issue_counts_by_severity") or {}
    kg_publication_summary = summary(kg_publication)
    candidate_rows = [
        row for row in visual_plan.get("candidate_audit_rows") or [] if isinstance(row, dict)
    ]
    audited_rows = audit_rows(root, candidate_rows)
    decision_counts = Counter(row["pre_retention_auditor_decision"] for row in audited_rows)
    status_counts = Counter(row["source_traceability_status"] for row in audited_rows)
    final_retained_count = sum(1 for row in audited_rows if row["final_retention_authorized"])
    rendered_count = sum(1 for row in audited_rows if row["rendered_artifact_path"])
    layout_deferred_count = sum(
        1
        for row in audited_rows
        if row["layout_overlap_check_status"] == "deferred_until_rendered_artifact"
    )
    kg_row = next(
        (
            row
            for row in audited_rows
            if row.get("content_area_id") == "knowledge_graph_navigation_quality"
        ),
        None,
    )
    inventory = build_inventory(audited_rows)
    iteration_register = build_iteration_register(audited_rows)
    kg_usability = build_kg_usability_audit(
        kg_quality_summary,
        kg_traceability_summary,
        kg_issue_counts,
        kg_publication_summary,
        kg_row,
    )
    checks = [
        check_row(
            "visual_table_audit_plan_ready",
            visual_summary.get("overall_status")
            == "publication_visual_audit_plan_ready_no_retained_artifacts",
            {"visual_plan_status": visual_summary.get("overall_status")},
            [rel(root / VISUAL_TABLE_AUDIT_PLAN, root)],
            "visual_table_audit_plan_not_ready",
        ),
        check_row(
            "candidate_rows_complete",
            len(audited_rows)
            == safe_int(visual_summary.get("expected_candidate_artifact_count"))
            == 10,
            {
                "audit_row_count": len(audited_rows),
                "expected_candidate_artifact_count": visual_summary.get(
                    "expected_candidate_artifact_count"
                ),
                "content_matrix_row_count": content_summary.get("row_count"),
            },
            [
                rel(root / VISUAL_TABLE_AUDIT_PLAN, root),
                rel(root / ARTICLE_SUPPLEMENT_CONTENT_MATRIX, root),
            ],
            "candidate_rows_incomplete",
        ),
        check_row(
            "all_sources_traceable",
            bool(audited_rows)
            and all(row["source_traceability_status"] == "pass" for row in audited_rows),
            {"source_traceability_status_counts": dict(status_counts)},
            [rel(root / VISUAL_TABLE_AUDIT_PLAN, root)],
            "candidate_source_missing",
        ),
        check_row(
            "all_rows_have_claim_boundaries",
            bool(audited_rows)
            and all(row["claim_boundary_status"] == "pass" for row in audited_rows),
            {
                "missing_claim_boundary_ids": [
                    row["content_area_id"]
                    for row in audited_rows
                    if row["claim_boundary_status"] != "pass"
                ]
            },
            [rel(root / VISUAL_TABLE_AUDIT_PLAN, root)],
            "claim_boundary_missing",
        ),
        check_row(
            "all_rows_have_reader_questions",
            bool(audited_rows)
            and all(row["scientific_utility_status"] == "pass" for row in audited_rows),
            {
                "missing_reader_question_ids": [
                    row["content_area_id"]
                    for row in audited_rows
                    if row["scientific_utility_status"] != "pass"
                ]
            },
            [rel(root / VISUAL_TABLE_AUDIT_PLAN, root)],
            "reader_question_missing",
        ),
        check_row(
            "no_rendered_or_retained_artifacts",
            rendered_count == 0 and final_retained_count == 0,
            {
                "rendered_artifact_count": rendered_count,
                "final_retained_artifact_count": final_retained_count,
            },
            [rel(root / VISUAL_TABLE_AUDIT_PLAN, root)],
            "artifact_unexpectedly_rendered_or_retained",
        ),
        check_row(
            "layout_checks_deferred_until_rendering",
            layout_deferred_count == len(audited_rows) == 10,
            {
                "layout_deferred_count": layout_deferred_count,
                "audit_row_count": len(audited_rows),
            },
            [rel(root / VISUAL_TABLE_AUDIT_PLAN, root)],
            "layout_checks_unexpectedly_finalized",
        ),
        check_row(
            "neutral_no_method_promotion_guard_preserved",
            neutral_summary.get("overall_status")
            == "neutral_reporting_language_audit_pass"
            and safe_int(neutral_summary.get("unguarded_hit_count")) == 0,
            {
                "neutral_language_status": neutral_summary.get("overall_status"),
                "unguarded_hit_count": neutral_summary.get("unguarded_hit_count"),
            },
            [rel(root / NEUTRAL_LANGUAGE, root)],
            "neutral_language_not_clean",
        ),
        check_row(
            "kg_navigation_release_still_blocked",
            kg_usability["summary"]["kg_citable_component_authorized"] is False
            and kg_usability["summary"]["publication_site_deployment_authorized"] is False,
            kg_usability["summary"],
            [
                rel(root / KG_QUALITY, root),
                rel(root / KG_PUBLICATION_QUALITY, root),
            ],
            "kg_navigation_unexpectedly_released",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] == "fail"]
    overall_status = (
        "visual_table_pre_retention_audit_completed_no_retained_artifacts"
        if not failed_checks
        else "visual_table_pre_retention_audit_blocked"
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "summary": {
            "overall_status": overall_status,
            "phase_state": (
                "pre_retention_audit_complete_rendering_and_final_retention_blocked"
            ),
            "inventory_row_count": len(audited_rows),
            "expected_candidate_artifact_count": visual_summary.get(
                "expected_candidate_artifact_count"
            ),
            "audit_row_count": len(audited_rows),
            "pre_retention_audit_completed_count": len(audited_rows),
            "source_traceable_candidate_count": sum(
                1 for row in audited_rows if row["source_traceability_status"] == "pass"
            ),
            "pre_retention_decision_count": sum(decision_counts.values()),
            "pre_retention_decision_counts": dict(sorted(decision_counts.items())),
            "actionable_feedback_count": sum(
                row["actionable_feedback_count"] for row in audited_rows
            ),
            "iteration_action_count": len(iteration_register["actions"]),
            "rendered_artifact_count": rendered_count,
            "layout_check_deferred_count": layout_deferred_count,
            "final_retained_artifact_count": final_retained_count,
            "final_visual_table_retention_authorized": False,
            "kg_citable_component_authorized": False,
            "publication_site_deployment_authorized": False,
            "final_triptych_release_authorized": False,
            "final_manuscript_prose_permission": False,
            "positive_claim_promotion_authorized": False,
            "neutral_no_method_promotion_guard_active": (
                neutral_summary.get("overall_status")
                == "neutral_reporting_language_audit_pass"
                and safe_int(neutral_summary.get("unguarded_hit_count")) == 0
            ),
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
        },
        "checks": checks,
        "failed_checks": [row["check_id"] for row in failed_checks],
        "audit_rows": audited_rows,
        "visual_table_inventory": inventory,
        "visual_table_iteration_register": iteration_register,
        "kg_navigation_usability_audit": kg_usability,
        "claim_boundaries": [
            "This audit is pre-retention only; it does not retain figures or tables.",
            "Rendered layout, overlap, caption, accessibility, and resolution checks remain deferred until concrete artifacts exist.",
            "No audit row promotes CQR, CV+, Venn-Abers, fairness, bounded-support, production, or final-selection claims.",
            "KG citation and site deployment remain blocked until release gates pass.",
        ],
        "sources": {
            "visual_table_audit_plan": rel(root / VISUAL_TABLE_AUDIT_PLAN, root),
            "article_supplement_content_matrix": rel(
                root / ARTICLE_SUPPLEMENT_CONTENT_MATRIX, root
            ),
            "neutral_reporting_language": rel(root / NEUTRAL_LANGUAGE, root),
            "kg_quality": rel(root / KG_QUALITY, root),
            "kg_publication_quality": rel(root / KG_PUBLICATION_QUALITY, root),
        },
    }


def render_report_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Visual/Table Audit Report",
        "",
        "This is a pre-retention audit. It does not retain figures or tables, authorize final manuscript prose, cite the KG, deploy a site, or promote claims.",
        "",
        f"- Generated UTC: `{payload['generated_at_utc']}`",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Inventory rows: {summary_payload['inventory_row_count']}",
        f"- Source-traceable rows: {summary_payload['source_traceable_candidate_count']}",
        f"- Rendered artifacts: {summary_payload['rendered_artifact_count']}",
        f"- Final retained artifacts: {summary_payload['final_retained_artifact_count']}",
        f"- Layout checks deferred: {summary_payload['layout_check_deferred_count']}",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Decisions",
        "",
        "| Content Area | Artifact | Pre-Retention Decision | Final Retention |",
        "|---|---|---|---:|",
    ]
    for row in payload["audit_rows"]:
        lines.append(
            f"| `{row['content_area_id']}` | `{row['artifact_type']}` | "
            f"`{row['pre_retention_auditor_decision']}` | "
            f"`{row['final_retention_authorized']}` |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "|---|---:|"])
    for row in payload["checks"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` |")
    lines.append("")
    return "\n".join(lines)


def render_decision_log(
    title: str,
    rows: list[dict[str, Any]],
) -> str:
    lines = [
        f"# {title}",
        "",
        "All rows are pre-retention audit records. No final retained artifact is authorized.",
        "",
        "| Content Area | Decision | Feedback Count |",
        "|---|---|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['content_area_id']}` | "
            f"`{row['pre_retention_auditor_decision']}` | "
            f"{row['actionable_feedback_count']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_sidecars(out: Path, payload: dict[str, Any]) -> None:
    base_dir = out.parent
    atomic_write_json(
        base_dir / "visual_table_inventory.json",
        {
            **payload["visual_table_inventory"],
            "generated_at_utc": payload["generated_at_utc"],
            "sources": payload["sources"],
        },
    )
    atomic_write_json(
        base_dir / "visual_table_iteration_register.json",
        {
            **payload["visual_table_iteration_register"],
            "generated_at_utc": payload["generated_at_utc"],
            "sources": payload["sources"],
        },
    )
    atomic_write_json(
        base_dir / "kg_navigation_usability_audit.json",
        {
            **payload["kg_navigation_usability_audit"],
            "generated_at_utc": payload["generated_at_utc"],
            "sources": payload["sources"],
        },
    )
    figure_rows = [
        row
        for row in payload["audit_rows"]
        if "figure" in str(row.get("artifact_type") or "")
        or "kg" in str(row.get("candidate_surface") or "")
    ]
    table_rows = [
        row
        for row in payload["audit_rows"]
        if row not in figure_rows
    ]
    atomic_write_text(
        base_dir / "figure_quality_decision_log.md",
        render_decision_log("Figure Quality Decision Log", figure_rows),
    )
    atomic_write_text(
        base_dir / "table_quality_decision_log.md",
        render_decision_log("Table Quality Decision Log", table_rows),
    )


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_report_markdown(payload))
    write_sidecars(out, payload)
    print(
        json.dumps(
            {
                "status": "ok" if not payload["failed_checks"] else "fail",
                "overall_status": payload["summary"]["overall_status"],
                "audit_row_count": payload["summary"]["audit_row_count"],
                "final_retained_artifact_count": payload["summary"][
                    "final_retained_artifact_count"
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
