"""Build a neutral article/supplement/KG navigation index.

The index is a pre-release navigation aid, not manuscript prose. It links
section-level claim boundaries, visual/table candidates, release-gap rows, and
knowledge-graph controls so later article, supplement, and site work can trace
each reader-facing surface back to evidence without promoting a method.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_article_supplement_kg_navigation_index_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/article_supplement_kg_navigation_index.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

SECTION_BOUNDARY = Path(
    "experiments/regression/manuscript/section_claim_boundary_audit.json"
)
SECTION_PACKET = Path(
    "experiments/regression/manuscript/manuscript_section_evidence_packet.json"
)
CLAIM_SAFE_MATRIX = Path(
    "experiments/regression/manuscript/claim_safe_result_extraction_matrix.json"
)
NEUTRAL_LEDGER = Path("experiments/regression/manuscript/neutral_result_ledger.json")
RELEASE_GAP = Path(
    "experiments/regression/manuscript/publication_release_gap_register.json"
)
VISUAL_RENDER_AUDIT = Path(
    "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
)
RETENTION_AUDIT = Path(
    "experiments/regression/manuscript/publication_retention_readiness_audit.json"
)
CONTENT_MATRIX = Path(
    "experiments/regression/manuscript/article_supplement_content_matrix.json"
)
TRIPTYCH_DECISION = Path(
    "experiments/regression/manuscript/article_supplement_kg_triptych_decision.json"
)
SITE_DECISION = Path(
    "experiments/regression/manuscript/publication_site_decision_record.json"
)
KG_NAVIGATION_USABILITY = Path(
    "experiments/regression/manuscript/kg_navigation_usability_audit.json"
)
POST_PROGRAM = Path(
    "experiments/regression/manuscript/post_experiment_publication_program.json"
)
GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
KG_GRAPH = Path("experiments/regression/catalogs/knowledge_graph.json")
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
KG_PUBLICATION = REPORT_DIR / "kg_publication_quality_audit.json"
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
VENN_NEGATIVE = REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"

SOURCE_PATHS = {
    "section_claim_boundary_audit": SECTION_BOUNDARY,
    "manuscript_section_evidence_packet": SECTION_PACKET,
    "claim_safe_result_extraction_matrix": CLAIM_SAFE_MATRIX,
    "neutral_result_ledger": NEUTRAL_LEDGER,
    "publication_release_gap_register": RELEASE_GAP,
    "visual_table_render_candidate_audit": VISUAL_RENDER_AUDIT,
    "publication_retention_readiness_audit": RETENTION_AUDIT,
    "article_supplement_content_matrix": CONTENT_MATRIX,
    "article_supplement_kg_triptych_decision": TRIPTYCH_DECISION,
    "publication_site_decision_record": SITE_DECISION,
    "kg_navigation_usability_audit": KG_NAVIGATION_USABILITY,
    "post_experiment_publication_program": POST_PROGRAM,
    "goal_completion_audit": GOAL_COMPLETION,
    "knowledge_graph": KG_GRAPH,
    "knowledge_graph_quality_summary": KG_QUALITY,
    "kg_publication_quality_audit": KG_PUBLICATION,
    "neutral_reporting_language_audit": NEUTRAL_LANGUAGE,
    "venn_abers_negative_evidence_disposition_audit": VENN_NEGATIVE,
}

AUTHORIZATION_FIELDS = (
    "final_section_prose_authorized",
    "final_manuscript_prose_permission",
    "final_report_prose_permission",
    "final_visual_table_retention_authorized",
    "final_triptych_release_authorized",
    "release_authorized",
    "publication_site_deployment_authorized",
    "site_deployment_authorized",
    "kg_citable_component_authorized",
    "sterile_repository_creation_authorized",
    "working_repository_final_citable",
    "method_recommendation_authorized",
    "positive_claim_promotion_authorized",
)

KG_SITE_RELEASE_TARGETS = [
    "navigable_knowledge_graph",
    "github_pages_publication_site",
    "article_supplement_kg_navigation_index",
    "publication_site_html_package",
]

VISUAL_TARGET_HINTS = {
    "paper_dataset_scope_evidence": ["experiment_scope_and_accounting_table"],
    "paper_method_scope_evidence": ["method_performance_descriptive_summary"],
    "paper_main_results_blocked_evidence": [
        "method_selection_robustness_diagnostics",
        "neutral_closure_and_claim_boundary_table",
    ],
    "supplement_robustness_diagnostic_evidence": [
        "post_selection_validation_diagnostics",
        "duplicate_split_caveat_inventory",
    ],
    "supplement_venn_abers_negative_evidence": [
        "venn_abers_failure_mode_evidence"
    ],
    "supplement_methodology_controls_evidence": [
        "bounded_support_endpoint_policy_table",
        "fairness_group_diagnostic_tables",
    ],
    "supplement_reproducibility_traceability_evidence": [
        "duplicate_split_caveat_inventory"
    ],
    "individual_report_blueprint_evidence": [],
    "kg_site_navigation_candidate": ["knowledge_graph_navigation_quality"],
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
    if not isinstance(payload, dict):
        return {}
    value = payload.get("summary")
    return value if isinstance(value, dict) else payload


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


def slug_fragment(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unnamed"


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def rows_by_key(payload: dict[str, Any], key: str, id_field: str) -> dict[str, dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get(id_field)): row
        for row in rows
        if isinstance(row, dict) and row.get(id_field)
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


def authorization_count(row: dict[str, Any]) -> int:
    return sum(bool(row.get(field)) for field in AUTHORIZATION_FIELDS)


def kg_node_ids(kg: dict[str, Any]) -> set[str]:
    nodes = kg.get("nodes")
    if not isinstance(nodes, list):
        return set()
    return {str(node.get("id")) for node in nodes if isinstance(node, dict)}


def release_row_summaries(
    release_gap: dict[str, Any], deliverable_ids: list[str]
) -> tuple[list[dict[str, Any]], list[str], int]:
    deliverables = rows_by_key(release_gap, "deliverable_rows", "deliverable_id")
    linked: list[dict[str, Any]] = []
    missing: list[str] = []
    authorized_count = 0
    for deliverable_id in deliverable_ids:
        row = deliverables.get(deliverable_id)
        if not row:
            missing.append(deliverable_id)
            continue
        if row.get("release_authorized") is True:
            authorized_count += 1
        linked.append(
            {
                "deliverable_id": deliverable_id,
                "family": row.get("family"),
                "format": row.get("format"),
                "release_status": row.get("release_status"),
                "release_authorized": row.get("release_authorized"),
                "release_blockers": row.get("release_blockers") or [],
                "claim_boundary": row.get("claim_boundary"),
                "source_traceability_status": row.get("source_traceability_status"),
            }
        )
    return linked, missing, authorized_count


def method_promotion_text_guard(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=True).lower()
    unsafe_phrases = [
        "recommend cqr",
        "cqr is recommended",
        "cqr should be used",
        "cv+ is recommended",
        "best method",
        "winner method",
        "final method selection",
        "validated venn-abers regression claim",
    ]
    return not any(phrase in text for phrase in unsafe_phrases)


def build_visual_candidate_rows(
    render_audit: dict[str, Any], content_matrix: dict[str, Any]
) -> list[dict[str, Any]]:
    content_rows = rows_by_key(content_matrix, "rows", "content_area_id")
    rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(render_audit.get("render_candidate_rows") or []):
        if not isinstance(row, dict):
            continue
        content_area_id = str(row.get("content_area_id") or "")
        content = content_rows.get(content_area_id, {})
        rows.append(
            {
                "row_index": row_index,
                "content_area_id": content_area_id,
                "artifact_type": row.get("artifact_type"),
                "reader_question": row.get("reader_question")
                or content.get("reader_question"),
                "pre_retention_auditor_decision": row.get(
                    "pre_retention_auditor_decision"
                ),
                "retained_visual_or_table_decision": row.get(
                    "retained_visual_or_table_decision"
                ),
                "primary_rendered_artifact_path": row.get(
                    "primary_rendered_artifact_path"
                ),
                "source_traceability_status": row.get("source_traceability_status"),
                "final_retention_authorized": row.get(
                    "final_retention_authorized",
                    row.get("final_visual_table_retention_authorized"),
                ),
                "positive_claim_promotion_authorized": row.get(
                    "positive_claim_promotion_authorized"
                ),
                "claim_boundary": row.get("claim_boundary")
                or content.get("claim_boundary"),
            }
        )
    return rows


def kg_refs_for_section_row(row: dict[str, Any]) -> list[str]:
    packet_id = row.get("packet_id")
    refs = [
        "report:section_claim_boundary_audit",
        "report:manuscript_section_evidence_packet",
        "report:claim_safe_result_extraction_matrix",
        "report:neutral_result_ledger",
        "report:publication_release_gap_register",
        f"methodology_control:section_claim_boundary_audit:{slug_fragment(packet_id)}",
        (
            "methodology_control:manuscript_section_evidence_packet:"
            f"{slug_fragment(packet_id)}"
        ),
    ]
    surface_id = row.get("claim_safe_surface_id")
    if surface_id:
        refs.append(
            "methodology_control:claim_safe_result_extraction:"
            f"{slug_fragment(surface_id)}"
        )
    for result_id in row.get("neutral_result_ids") or []:
        refs.append(
            "methodology_control:neutral_result_ledger:"
            f"{slug_fragment(result_id)}"
        )
    return refs


def build_navigation_rows(
    section_boundary: dict[str, Any],
    release_gap: dict[str, Any],
    visual_candidate_rows: list[dict[str, Any]],
    kg_ids: set[str],
) -> list[dict[str, Any]]:
    visual_by_id = {
        row["content_area_id"]: row
        for row in visual_candidate_rows
        if row.get("content_area_id")
    }
    rows: list[dict[str, Any]] = []
    for row_index, boundary in enumerate(section_boundary.get("boundary_rows") or []):
        if not isinstance(boundary, dict):
            continue
        packet_id = str(boundary.get("packet_id") or "")
        release_targets = [
            str(target)
            for target in boundary.get("release_target_deliverable_ids") or []
        ]
        linked_release_targets, missing_release_targets, release_authorized_count = (
            release_row_summaries(release_gap, release_targets)
        )
        visual_ids = VISUAL_TARGET_HINTS.get(packet_id, [])
        kg_refs = kg_refs_for_section_row(boundary)
        missing_kg_refs = [node_id for node_id in kg_refs if node_id not in kg_ids]
        rows.append(
            {
                "row_index": row_index,
                "navigation_id": packet_id,
                "navigation_family": "section_boundary_surface",
                "target_document": boundary.get("target_document"),
                "reader_navigation_role": boundary.get("scientific_reporting_role"),
                "claim_safe_surface_id": boundary.get("claim_safe_surface_id"),
                "claim_safe_surface_status": boundary.get(
                    "claim_safe_surface_status"
                ),
                "neutral_result_ids": boundary.get("neutral_result_ids") or [],
                "neutral_result_claim_statuses": boundary.get(
                    "neutral_result_claim_statuses"
                )
                or [],
                "linked_visual_table_candidate_ids": [
                    visual_id for visual_id in visual_ids if visual_id in visual_by_id
                ],
                "missing_visual_table_candidate_ids": [
                    visual_id
                    for visual_id in visual_ids
                    if visual_id not in visual_by_id
                ],
                "release_target_deliverable_ids": release_targets,
                "linked_release_targets": linked_release_targets,
                "missing_release_target_ids": missing_release_targets,
                "release_authorized_target_count": release_authorized_count,
                "kg_reference_node_ids": kg_refs,
                "missing_kg_reference_node_ids": missing_kg_refs,
                "source_artifact_ids": [
                    "section_claim_boundary_audit",
                    "manuscript_section_evidence_packet",
                    "claim_safe_result_extraction_matrix",
                    "neutral_result_ledger",
                    "publication_release_gap_register",
                ],
                "source_traceability_status": (
                    "pass"
                    if not missing_release_targets and not missing_kg_refs
                    else "blocked"
                ),
                "boundary_status": boundary.get("boundary_status"),
                "boundary_complete": boundary.get("boundary_complete"),
                "allowed_use": boundary.get("allowed_use"),
                "blocked_use": boundary.get("blocked_use"),
                "claim_boundary": boundary.get("claim_boundary"),
                "main_results_positive_boundary_blocked": boundary.get(
                    "main_positive_boundary_blocked"
                ),
                "venn_abers_negative_boundary_preserved": boundary.get(
                    "venn_abers_negative_boundary_preserved"
                ),
                "final_section_prose_authorized": boundary.get(
                    "final_section_prose_authorized"
                ),
                "final_manuscript_prose_permission": boundary.get(
                    "final_manuscript_prose_permission"
                ),
                "final_visual_table_retention_authorized": boundary.get(
                    "final_visual_table_retention_authorized"
                ),
                "release_authorized": boundary.get("release_authorized"),
                "publication_site_deployment_authorized": boundary.get(
                    "publication_site_deployment_authorized"
                ),
                "kg_citable_component_authorized": boundary.get(
                    "kg_citable_component_authorized"
                ),
                "sterile_repository_creation_authorized": boundary.get(
                    "sterile_repository_creation_authorized"
                ),
                "working_repository_final_citable": boundary.get(
                    "working_repository_final_citable"
                ),
                "method_recommendation_authorized": boundary.get(
                    "method_recommendation_authorized"
                ),
                "positive_claim_promotion_authorized": boundary.get(
                    "positive_claim_promotion_authorized"
                ),
            }
        )

    kg_release_targets, missing_release_targets, release_authorized_count = (
        release_row_summaries(release_gap, KG_SITE_RELEASE_TARGETS)
    )
    kg_refs = [
        "report:kg_navigation_usability_audit",
        "report:knowledge_graph_quality_summary",
        "report:kg_publication_quality_audit",
        "report:article_supplement_kg_triptych_decision",
        "methodology_control:neutral_result_ledger:knowledge_graph_navigation_release_blocked",
        "methodology_control:article_supplement_kg_triptych_component:knowledge_graph_or_publication_site",
        "methodology_control:publication_release_gap:article_supplement_kg_navigation_index",
        "methodology_control:publication_release_gap:github_pages_publication_site",
        "methodology_control:publication_release_gap:publication_site_html_package",
    ]
    missing_kg_refs = [node_id for node_id in kg_refs if node_id not in kg_ids]
    rows.append(
        {
            "row_index": len(rows),
            "navigation_id": "kg_site_navigation_candidate",
            "navigation_family": "kg_or_publication_site_surface",
            "target_document": "knowledge_graph_or_publication_site",
            "reader_navigation_role": "kg_site_navigation_release_blocked",
            "claim_safe_surface_id": "knowledge_graph_navigation",
            "claim_safe_surface_status": "blocked_until_usability_release_gates",
            "neutral_result_ids": ["knowledge_graph_navigation_release_blocked"],
            "neutral_result_claim_statuses": [
                "blocked_until_sterile_repository_and_disclosure_review"
            ],
            "linked_visual_table_candidate_ids": [
                visual_id
                for visual_id in VISUAL_TARGET_HINTS["kg_site_navigation_candidate"]
                if visual_id in visual_by_id
            ],
            "missing_visual_table_candidate_ids": [
                visual_id
                for visual_id in VISUAL_TARGET_HINTS["kg_site_navigation_candidate"]
                if visual_id not in visual_by_id
            ],
            "release_target_deliverable_ids": KG_SITE_RELEASE_TARGETS,
            "linked_release_targets": kg_release_targets,
            "missing_release_target_ids": missing_release_targets,
            "release_authorized_target_count": release_authorized_count,
            "kg_reference_node_ids": kg_refs,
            "missing_kg_reference_node_ids": missing_kg_refs,
            "source_artifact_ids": [
                "kg_navigation_usability_audit",
                "knowledge_graph",
                "knowledge_graph_quality_summary",
                "kg_publication_quality_audit",
                "article_supplement_kg_triptych_decision",
                "publication_site_decision_record",
                "publication_release_gap_register",
            ],
            "source_traceability_status": (
                "pass"
                if not missing_release_targets and not missing_kg_refs
                else "blocked"
            ),
            "boundary_status": "kg_site_navigation_release_blocked",
            "boundary_complete": True,
            "allowed_use": (
                "Use as a pre-release navigation-control index tying the article, "
                "supplement, KG, and site candidates to evidence and blockers."
            ),
            "blocked_use": (
                "Do not cite, deploy, release, or treat the KG/site candidate as "
                "a final publication surface until sterile-repository and "
                "disclosure gates pass."
            ),
            "claim_boundary": (
                "KG/site navigation is a release-blocked candidate only; it cannot "
                "authorize citation, GitHub Pages deployment, method recommendation, "
                "or positive claim promotion."
            ),
            "main_results_positive_boundary_blocked": False,
            "venn_abers_negative_boundary_preserved": False,
            "final_section_prose_authorized": False,
            "final_manuscript_prose_permission": False,
            "final_visual_table_retention_authorized": False,
            "release_authorized": False,
            "publication_site_deployment_authorized": False,
            "kg_citable_component_authorized": False,
            "sterile_repository_creation_authorized": False,
            "working_repository_final_citable": False,
            "method_recommendation_authorized": False,
            "positive_claim_promotion_authorized": False,
        }
    )
    return rows


def add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    on_failure: str,
    **details: Any,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "passed": bool(passed),
            "severity": "critical" if not passed else "info",
            "on_failure": None if passed else on_failure,
            **details,
        }
    )


def build_payload(root: Path) -> dict[str, Any]:
    loaded = {name: read_json(root / path) for name, path in SOURCE_PATHS.items()}
    present_sources, missing_sources = source_status(root)

    section_summary = summary(loaded["section_claim_boundary_audit"])
    release_summary = summary(loaded["publication_release_gap_register"])
    render_summary = summary(loaded["visual_table_render_candidate_audit"])
    retention_summary = summary(loaded["publication_retention_readiness_audit"])
    triptych_summary = summary(loaded["article_supplement_kg_triptych_decision"])
    site_summary = summary(loaded["publication_site_decision_record"])
    kg_nav_summary = summary(loaded["kg_navigation_usability_audit"])
    kg_quality_summary = loaded["knowledge_graph_quality_summary"].get("graph") or {}
    kg_publication_summary = summary(loaded["kg_publication_quality_audit"])
    neutral_language_summary = summary(loaded["neutral_reporting_language_audit"])
    goal_summary = summary(loaded["goal_completion_audit"])

    kg_ids = kg_node_ids(loaded["knowledge_graph"])
    visual_candidate_rows = build_visual_candidate_rows(
        loaded["visual_table_render_candidate_audit"],
        loaded["article_supplement_content_matrix"],
    )
    navigation_rows = build_navigation_rows(
        loaded["section_claim_boundary_audit"],
        loaded["publication_release_gap_register"],
        visual_candidate_rows,
        kg_ids,
    )

    section_rows = [
        row
        for row in navigation_rows
        if row.get("navigation_family") == "section_boundary_surface"
    ]
    kg_site_rows = [
        row
        for row in navigation_rows
        if row.get("navigation_family") == "kg_or_publication_site_surface"
    ]
    all_missing_kg_refs = sorted(
        {
            ref
            for row in navigation_rows
            for ref in row.get("missing_kg_reference_node_ids") or []
        }
    )
    authorized_release_targets = [
        target
        for row in navigation_rows
        for target in row.get("linked_release_targets") or []
        if target.get("release_authorized") is True
    ]
    visual_source_traceability_pass = sum(
        row.get("source_traceability_status") == "pass"
        for row in visual_candidate_rows
    )
    visual_final_authorized_count = sum(
        bool(row.get("final_retention_authorized"))
        or bool(row.get("positive_claim_promotion_authorized"))
        for row in visual_candidate_rows
    )
    no_final_authorizations = all(authorization_count(row) == 0 for row in navigation_rows)
    main_positive_blocked = any(
        row.get("navigation_id") == "paper_main_results_blocked_evidence"
        and row.get("main_results_positive_boundary_blocked") is True
        and row.get("boundary_status") == "blocked_positive_boundary_preserved"
        for row in navigation_rows
    )
    venn_negative_preserved = any(
        row.get("navigation_id") == "supplement_venn_abers_negative_evidence"
        and row.get("venn_abers_negative_boundary_preserved") is True
        and row.get("boundary_status") == "negative_failure_mode_boundary_preserved"
        for row in navigation_rows
    )
    kg_site_blocked = bool(kg_site_rows) and all(
        row.get("release_authorized") is False
        and row.get("publication_site_deployment_authorized") is False
        and row.get("kg_citable_component_authorized") is False
        and row.get("sterile_repository_creation_authorized") is False
        and row.get("source_traceability_status") == "pass"
        for row in kg_site_rows
    )
    method_guard_clean = method_promotion_text_guard(navigation_rows)

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "all_required_sources_present",
        not missing_sources,
        "Do not build article/supplement/KG navigation while source artifacts are missing.",
        missing_sources=missing_sources,
    )
    add_check(
        checks,
        "section_claim_boundary_audit_is_clean",
        section_summary.get("overall_status")
        == "section_claim_boundary_audit_pass_no_final_claims"
        and safe_int(section_summary.get("boundary_row_count")) == 8
        and safe_int(section_summary.get("failed_check_count")) == 0,
        "Re-run or repair the section claim-boundary audit before navigation indexing.",
        section_status=section_summary.get("overall_status"),
        boundary_row_count=section_summary.get("boundary_row_count"),
    )
    add_check(
        checks,
        "navigation_rows_are_source_traceable",
        len(navigation_rows) == 9
        and len(section_rows) == 8
        and len(kg_site_rows) == 1
        and all(row.get("source_traceability_status") == "pass" for row in navigation_rows),
        "Every navigation row must trace to release targets and KG nodes.",
        navigation_row_count=len(navigation_rows),
        section_navigation_row_count=len(section_rows),
        kg_site_navigation_row_count=len(kg_site_rows),
        missing_kg_reference_node_ids=all_missing_kg_refs,
    )
    add_check(
        checks,
        "release_targets_remain_blocked",
        not authorized_release_targets
        and release_summary.get("release_authorized_count") == 0,
        "Navigation index cannot authorize article, supplement, KG, site, or report release.",
        authorized_release_targets=authorized_release_targets,
        release_authorized_count=release_summary.get("release_authorized_count"),
    )
    add_check(
        checks,
        "visual_table_candidates_are_draft_only",
        len(visual_candidate_rows) == 10
        and visual_source_traceability_pass == 10
        and visual_final_authorized_count == 0
        and render_summary.get("overall_status")
        == "draft_visual_table_render_audit_completed_no_final_retention"
        and retention_summary.get("overall_status")
        == "publication_retention_readiness_ready_no_final_prose",
        "Visual/table rows must stay draft candidates with no final retention.",
        visual_candidate_count=len(visual_candidate_rows),
        visual_source_traceability_pass=visual_source_traceability_pass,
        visual_final_authorized_count=visual_final_authorized_count,
    )
    add_check(
        checks,
        "kg_site_triptych_release_remains_blocked",
        kg_site_blocked
        and triptych_summary.get("final_triptych_release_authorized") is False
        and triptych_summary.get("kg_citable_component_authorized") is False
        and triptych_summary.get("publication_site_deployment_authorized") is False
        and site_summary.get("site_deployment_authorized") is False
        and site_summary.get("sterile_repository_required_before_deployment") is True
        and kg_nav_summary.get("publication_site_deployment_authorized") is False
        and kg_nav_summary.get("kg_citable_component_authorized") is False,
        "KG/site/triptych navigation cannot be released or cited yet.",
        triptych_status=triptych_summary.get("overall_status"),
        site_status=site_summary.get("overall_status"),
        kg_navigation_status=kg_nav_summary.get("overall_status"),
    )
    add_check(
        checks,
        "kg_quality_references_are_current_and_clean",
        safe_int(kg_quality_summary.get("node_count")) >= 3348
        and safe_int(kg_quality_summary.get("edge_count")) >= 19021
        and safe_int(kg_quality_summary.get("isolated_node_count")) == 0
        and kg_publication_pre_release_ready(kg_publication_summary),
        "Refresh KG build and KG publication-quality audit before indexing.",
        kg_node_count=kg_quality_summary.get("node_count"),
        kg_edge_count=kg_quality_summary.get("edge_count"),
        kg_isolated_node_count=kg_quality_summary.get("isolated_node_count"),
        kg_publication_status=kg_publication_summary.get("overall_status"),
    )
    add_check(
        checks,
        "scientific_no_method_promotion_policy_preserved",
        method_guard_clean
        and main_positive_blocked
        and venn_negative_preserved
        and neutral_language_summary.get("overall_status")
        == "neutral_reporting_language_audit_pass"
        and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
        and goal_summary.get("empirical_completion_policy")
        == "neutral_no_promotion_route_accepted"
        and goal_summary.get("positive_claim_publication_ready") is False,
        "Navigation must describe evidence neutrally and keep method promotion blocked.",
        main_results_positive_boundary_blocked=main_positive_blocked,
        venn_abers_negative_boundary_preserved=venn_negative_preserved,
        neutral_language_unguarded_hit_count=neutral_language_summary.get(
            "unguarded_hit_count"
        ),
        empirical_completion_policy=goal_summary.get("empirical_completion_policy"),
    )
    add_check(
        checks,
        "no_final_outputs_authorized",
        no_final_authorizations,
        "Navigation rows must not authorize final prose, release, citation, or method selection.",
        authorization_fields=AUTHORIZATION_FIELDS,
    )

    failed_checks = [check for check in checks if not check["passed"]]
    summary_payload = {
        "overall_status": (
            "article_supplement_kg_navigation_index_ready_no_release"
            if not failed_checks
            else "article_supplement_kg_navigation_index_blocked"
        ),
        "phase_state": (
            "neutral_pre_release_navigation_index_active_final_outputs_blocked"
        ),
        "navigation_row_count": len(navigation_rows),
        "section_navigation_row_count": len(section_rows),
        "kg_site_navigation_row_count": len(kg_site_rows),
        "source_traceable_row_count": sum(
            row.get("source_traceability_status") == "pass"
            for row in navigation_rows
        ),
        "visual_table_candidate_index_row_count": len(visual_candidate_rows),
        "visual_table_source_traceability_pass_count": visual_source_traceability_pass,
        "visual_table_final_authorized_count": visual_final_authorized_count,
        "release_target_linked_row_count": sum(
            not row.get("missing_release_target_ids") for row in navigation_rows
        ),
        "release_authorized_target_count": len(authorized_release_targets),
        "kg_node_reference_row_count": sum(
            bool(row.get("kg_reference_node_ids")) for row in navigation_rows
        ),
        "kg_node_reference_issue_count": len(all_missing_kg_refs),
        "missing_kg_reference_node_ids": all_missing_kg_refs,
        "missing_source_artifact_count": len(missing_sources),
        "kg_node_count": kg_quality_summary.get("node_count"),
        "kg_edge_count": kg_quality_summary.get("edge_count"),
        "kg_isolated_node_count": kg_quality_summary.get("isolated_node_count"),
        "main_results_positive_boundary_blocked": main_positive_blocked,
        "venn_abers_negative_boundary_preserved": venn_negative_preserved,
        "scientific_no_method_promotion_guard_active": method_guard_clean,
        "neutral_language_unguarded_hit_count": neutral_language_summary.get(
            "unguarded_hit_count"
        ),
        "final_navigation_release_authorized": False,
        "final_manuscript_prose_permission": False,
        "final_visual_table_retention_authorized": False,
        "publication_site_deployment_authorized": False,
        "kg_citable_component_authorized": False,
        "sterile_repository_creation_authorized": False,
        "working_repository_final_citable": False,
        "method_recommendation_authorized": False,
        "positive_claim_promotion_authorized": False,
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary_payload,
        "sources": {
            name: rel(root / path, root) for name, path in SOURCE_PATHS.items()
        },
        "present_source_artifacts": present_sources,
        "missing_source_artifacts": missing_sources,
        "claim_boundaries": [
            "This is a pre-release navigation index; it is not final manuscript prose.",
            "The index must not select, recommend, or promote any conformal method.",
            "CQR/CV+ evidence remains descriptive/diagnostic unless later gates pass.",
            "Venn-Abers regression evidence remains reportable as observed negative/failure-mode evidence; no validation claim is authorized.",
            "KG/site links are candidate navigation surfaces only until sterile-repository, disclosure, usability, and release gates pass.",
        ],
        "navigation_rows": navigation_rows,
        "visual_table_candidate_rows": visual_candidate_rows,
        "checks": checks,
        "failed_checks": failed_checks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Article/Supplement/KG Navigation Index",
        "",
        "This pre-release index maps article, supplementary document, individual report, and KG/site candidate surfaces to claim boundaries, visual/table candidates, release blockers, and KG nodes. It does not authorize final prose, method recommendation, citation, deployment, or positive claim promotion.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase: `{summary_payload['phase_state']}`",
        f"- Navigation rows: {summary_payload['navigation_row_count']} "
        f"({summary_payload['section_navigation_row_count']} section, "
        f"{summary_payload['kg_site_navigation_row_count']} KG/site)",
        f"- Visual/table candidates indexed: {summary_payload['visual_table_candidate_index_row_count']}",
        f"- Release-authorized targets: {summary_payload['release_authorized_target_count']}",
        f"- KG reference issues: {summary_payload['kg_node_reference_issue_count']}",
        f"- Main positive boundary blocked: `{summary_payload['main_results_positive_boundary_blocked']}`",
        f"- Venn-Abers negative boundary preserved: `{summary_payload['venn_abers_negative_boundary_preserved']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive-claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Navigation Rows",
        "",
        "| Navigation row | Target | Boundary status | Visual/table candidates | Release targets | KG refs missing |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in payload["navigation_rows"]:
        lines.append(
            "| "
            f"`{row['navigation_id']}` | "
            f"{row['target_document']} | "
            f"`{row['boundary_status']}` | "
            f"{len(row.get('linked_visual_table_candidate_ids') or [])} | "
            f"{len(row.get('linked_release_targets') or [])} | "
            f"{len(row.get('missing_kg_reference_node_ids') or [])} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundaries",
            "",
        ]
    )
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status |",
            "|---|---|",
        ]
    )
    for check in payload["checks"]:
        lines.append(
            f"| `{check['check_id']}` | {'pass' if check['passed'] else 'fail'} |"
        )
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
                "out": rel(out, root),
                "overall_status": payload["summary"]["overall_status"],
                "navigation_row_count": payload["summary"]["navigation_row_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
