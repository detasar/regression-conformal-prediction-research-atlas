"""Build pre-manuscript visual/table retention-readiness recommendations.

This is the audit pass after draft render/layout checks. It recommends where
candidate visuals/tables can be considered in the article, supplement, or KG
site workbench, but it does not retain final artifacts, authorize manuscript
prose, deploy a site, create the sterile repository, or promote any method.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_publication_retention_readiness_audit_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/publication_retention_readiness_audit.json"
)
RENDER_AUDIT = Path(
    "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
)
LAYOUT_AUDIT = Path(
    "experiments/regression/manuscript/visual_table_layout_quality_audit.json"
)
REVIEWER_DESIGN = Path("experiments/regression/manuscript/reviewer_design_brief.json")
CONTENT_MATRIX = Path(
    "experiments/regression/manuscript/article_supplement_content_matrix.json"
)
NEUTRAL_LEDGER = Path("experiments/regression/manuscript/neutral_result_ledger.json")
NEUTRAL_LANGUAGE = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "neutral_reporting_language_audit.json"
)

ARTICLE_CANDIDATES = {
    "experiment_scope_and_accounting_table",
    "method_performance_descriptive_summary",
    "venn_abers_failure_mode_evidence",
    "neutral_closure_and_claim_boundary_table",
}
KG_OR_SITE_CANDIDATES = {"knowledge_graph_navigation_quality"}


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


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def content_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    rows = payload.get("article_supplement_content_matrix")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def recommendation_for(content_id: str, content: dict[str, Any]) -> str:
    if content_id in KG_OR_SITE_CANDIDATES:
        return "kg_or_site_candidate_release_blocked"
    if content_id in ARTICLE_CANDIDATES:
        return "main_article_candidate_after_final_prose_gate"
    target_surfaces = set(content.get("target_surfaces") or [])
    if target_surfaces == {"main_article"}:
        return "main_article_candidate_after_final_prose_gate"
    return "supplement_candidate_after_final_prose_gate"


def build_payload(root: Path) -> dict[str, Any]:
    render_payload = read_json(root / RENDER_AUDIT)
    layout_payload = read_json(root / LAYOUT_AUDIT)
    reviewer_payload = read_json(root / REVIEWER_DESIGN)
    content_payload = read_json(root / CONTENT_MATRIX)
    ledger_payload = read_json(root / NEUTRAL_LEDGER)
    language_payload = read_json(root / NEUTRAL_LANGUAGE)

    render_summary = summary(render_payload)
    layout_summary = summary(layout_payload)
    reviewer_summary = summary(reviewer_payload)
    ledger_summary = summary(ledger_payload)
    language_summary = summary(language_payload)

    content_by_id = {
        str(row.get("content_area_id")): row
        for row in content_rows(content_payload)
        if row.get("content_area_id")
    }
    rows: list[dict[str, Any]] = []
    failed_checks: list[dict[str, Any]] = []

    for index, render_row in enumerate(render_payload.get("render_candidate_rows") or []):
        if not isinstance(render_row, dict):
            continue
        content_id = str(render_row.get("content_area_id") or "").strip()
        if not content_id:
            continue
        content = content_by_id.get(content_id, {})
        source_artifacts = list(
            dict.fromkeys(
                [
                    *(render_row.get("source_artifacts") or []),
                    str(RENDER_AUDIT),
                    str(REVIEWER_DESIGN),
                    str(CONTENT_MATRIX),
                    str(NEUTRAL_LEDGER),
                ]
            )
        )
        layout_pass = render_row.get("layout_quality_status") == "pass"
        caption_pass = render_row.get("caption_quality_status") == "pass"
        traceability_pass = render_row.get("source_traceability_status") == "pass"
        no_overlap = render_row.get("svg_static_text_overlap_detected") is False
        no_promotion = render_row.get("positive_claim_promotion_authorized") is False
        no_final_retention = render_row.get("final_retention_authorized") is False
        source_paths_exist = all((root / source).exists() for source in source_artifacts)
        recommendation = recommendation_for(content_id, content)
        row_status = (
            "recommendation_ready_no_final_retention"
            if all(
                [
                    layout_pass,
                    caption_pass,
                    traceability_pass,
                    no_overlap,
                    no_promotion,
                    no_final_retention,
                    source_paths_exist,
                ]
            )
            else "recommendation_blocked"
        )
        row = {
            "content_area_id": content_id,
            "row_index": index,
            "artifact_type": render_row.get("artifact_type"),
            "primary_rendered_artifact_path": render_row.get(
                "primary_rendered_artifact_path"
            ),
            "recommendation_status": row_status,
            "recommended_surface": recommendation,
            "candidate_surface": content.get("candidate_surface"),
            "target_surfaces": content.get("target_surfaces") or [],
            "gate_dependency": content.get("gate_dependency") or "",
            "reader_question": content.get("reader_question")
            or render_row.get("reader_question"),
            "claim_boundary": render_row.get("claim_boundary")
            or content.get("claim_boundary"),
            "layout_quality_status": render_row.get("layout_quality_status"),
            "caption_quality_status": render_row.get("caption_quality_status"),
            "source_traceability_status": render_row.get("source_traceability_status"),
            "svg_static_text_overlap_detected": render_row.get(
                "svg_static_text_overlap_detected"
            ),
            "source_artifacts": source_artifacts,
            "source_traceability_artifact_status": (
                "pass" if source_paths_exist else "missing_source_artifact"
            ),
            "retention_readiness_decision": (
                "candidate_ready_for_final_prose_stage_review"
                if row_status == "recommendation_ready_no_final_retention"
                else "candidate_requires_rework_before_final_prose_stage_review"
            ),
            "final_retention_authorized": False,
            "final_visual_table_retention_authorized": False,
            "final_manuscript_prose_permission": False,
            "publication_site_deployment_authorized": False,
            "kg_citable_component_authorized": False,
            "positive_claim_promotion_authorized": False,
            "sterile_repository_creation_authorized": False,
            "audit_note": (
                "Recommendation only; final article/supplement/KG use requires "
                "the manuscript drafting, release, and sterile repository gates."
            ),
        }
        rows.append(row)
        if row_status != "recommendation_ready_no_final_retention":
            failed_checks.append(
                {
                    "check_id": f"recommendation_ready:{content_id}",
                    "status": "fail",
                    "evidence": {
                        "layout_pass": layout_pass,
                        "caption_pass": caption_pass,
                        "traceability_pass": traceability_pass,
                        "no_overlap": no_overlap,
                        "no_promotion": no_promotion,
                        "no_final_retention": no_final_retention,
                        "source_paths_exist": source_paths_exist,
                    },
                }
            )

    recommendation_counts = Counter(row["recommended_surface"] for row in rows)
    status_counts = Counter(row["recommendation_status"] for row in rows)
    final_authorization_count = sum(
        1
        for row in rows
        if row["final_retention_authorized"]
        or row["final_visual_table_retention_authorized"]
        or row["final_manuscript_prose_permission"]
        or row["positive_claim_promotion_authorized"]
    )
    checks = [
        {
            "check_id": "all_render_candidates_reconciled",
            "status": "pass"
            if len(rows) == safe_int(render_summary.get("candidate_row_count"))
            else "fail",
            "evidence": {
                "recommendation_row_count": len(rows),
                "render_candidate_count": render_summary.get("candidate_row_count"),
            },
            "blocker": "missing_render_recommendation",
        },
        {
            "check_id": "layout_caption_traceability_all_pass",
            "status": "pass"
            if all(
                row["layout_quality_status"] == "pass"
                and row["caption_quality_status"] == "pass"
                and row["source_traceability_status"] == "pass"
                for row in rows
            )
            else "fail",
            "evidence": {
                "layout_pass_count": layout_summary.get("layout_pass_count"),
                "caption_pass_count": layout_summary.get("caption_pass_count"),
                "source_traceability_pass_count": layout_summary.get(
                    "source_traceability_pass_count"
                ),
            },
            "blocker": "render_candidate_quality_not_clean",
        },
        {
            "check_id": "reviewer_design_reconciled",
            "status": "pass"
            if reviewer_summary.get("overall_status")
            == "reviewer_design_brief_ready_no_final_prose"
            and safe_int(reviewer_summary.get("reviewer_count"))
            == safe_int(reviewer_summary.get("required_reviewer_count"))
            == 5
            and safe_int(reviewer_summary.get("advice_record_count")) >= 25
            else "fail",
            "evidence": {
                "reviewer_status": reviewer_summary.get("overall_status"),
                "reviewer_count": reviewer_summary.get("reviewer_count"),
                "required_reviewer_count": reviewer_summary.get(
                    "required_reviewer_count"
                ),
                "advice_record_count": reviewer_summary.get("advice_record_count"),
            },
            "blocker": "reviewer_design_not_reconciled",
        },
        {
            "check_id": "neutral_result_ledger_boundaries_clean",
            "status": "pass"
            if ledger_summary.get("overall_status")
            == "neutral_result_ledger_ready_no_method_promotion"
            and safe_int(ledger_summary.get("positive_claim_promotion_authorized_count"))
            == 0
            and safe_int(ledger_summary.get("final_method_selection_authorized_count"))
            == 0
            else "fail",
            "evidence": {
                "ledger_status": ledger_summary.get("overall_status"),
                "positive_claim_promotion_authorized_count": ledger_summary.get(
                    "positive_claim_promotion_authorized_count"
                ),
                "final_method_selection_authorized_count": ledger_summary.get(
                    "final_method_selection_authorized_count"
                ),
            },
            "blocker": "neutral_result_ledger_not_clean",
        },
        {
            "check_id": "neutral_language_clean",
            "status": "pass"
            if language_summary.get("overall_status")
            == "neutral_reporting_language_audit_pass"
            and safe_int(language_summary.get("unguarded_hit_count")) == 0
            else "fail",
            "evidence": {
                "neutral_language_status": language_summary.get("overall_status"),
                "unguarded_hit_count": language_summary.get("unguarded_hit_count"),
            },
            "blocker": "neutral_language_guard_not_clean",
        },
        {
            "check_id": "no_final_retention_or_release_authorized",
            "status": "pass" if final_authorization_count == 0 else "fail",
            "evidence": {"final_authorization_count": final_authorization_count},
            "blocker": "final_retention_or_release_authorized_too_early",
        },
    ]
    failed_checks.extend([check for check in checks if check["status"] != "pass"])
    failed_check_count = len(failed_checks)
    overall_status = (
        "publication_retention_readiness_ready_no_final_prose"
        if failed_check_count == 0
        else "publication_retention_readiness_blocked"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "phase_state": (
                "pre_manuscript_retention_recommendations_ready_"
                "final_prose_and_release_blocked"
            ),
            "recommendation_row_count": len(rows),
            "render_candidate_count": render_summary.get("candidate_row_count"),
            "recommendation_status_counts": dict(sorted(status_counts.items())),
            "recommended_surface_counts": dict(sorted(recommendation_counts.items())),
            "main_article_candidate_count": recommendation_counts.get(
                "main_article_candidate_after_final_prose_gate", 0
            ),
            "supplement_candidate_count": recommendation_counts.get(
                "supplement_candidate_after_final_prose_gate", 0
            ),
            "kg_or_site_candidate_count": recommendation_counts.get(
                "kg_or_site_candidate_release_blocked", 0
            ),
            "layout_pass_count": layout_summary.get("layout_pass_count"),
            "caption_pass_count": layout_summary.get("caption_pass_count"),
            "source_traceability_pass_count": layout_summary.get(
                "source_traceability_pass_count"
            ),
            "svg_static_text_overlap_detected_count": layout_summary.get(
                "svg_static_text_overlap_detected_count"
            ),
            "reviewer_design_reconciled": (
                reviewer_summary.get("overall_status")
                == "reviewer_design_brief_ready_no_final_prose"
            ),
            "neutral_result_ledger_clean": (
                ledger_summary.get("overall_status")
                == "neutral_result_ledger_ready_no_method_promotion"
            ),
            "neutral_language_unguarded_hit_count": language_summary.get(
                "unguarded_hit_count"
            ),
            "retention_recommendation_complete": failed_check_count == 0,
            "final_retained_artifact_count": 0,
            "final_visual_table_retention_authorized": False,
            "final_manuscript_prose_permission": False,
            "publication_site_deployment_authorized": False,
            "kg_citable_component_authorized": False,
            "positive_claim_promotion_authorized": False,
            "sterile_repository_creation_authorized": False,
            "check_count": len(checks),
            "failed_check_count": failed_check_count,
        },
        "claim_boundaries": [
            "This audit records retention-readiness recommendations, not final retained figures or tables.",
            "Recommended article or supplement placement does not authorize final manuscript prose.",
            "KG/site candidates remain blocked until sterile repository and release gates pass.",
            "CQR, CV+, Venn-Abers, fairness, bounded-support, and final-selection language must remain inside the neutral result ledger boundaries.",
        ],
        "checks": checks,
        "failed_checks": failed_checks,
        "recommendation_rows": rows,
        "sources": {
            "visual_table_render_candidate_audit": rel(root / RENDER_AUDIT, root),
            "visual_table_layout_quality_audit": rel(root / LAYOUT_AUDIT, root),
            "reviewer_design_brief": rel(root / REVIEWER_DESIGN, root),
            "article_supplement_content_matrix": rel(root / CONTENT_MATRIX, root),
            "neutral_result_ledger": rel(root / NEUTRAL_LEDGER, root),
            "neutral_reporting_language_audit": rel(root / NEUTRAL_LANGUAGE, root),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Publication Retention Readiness Audit",
        "",
        "This is a recommendation audit only. It does not retain final figures or tables and does not authorize final manuscript prose.",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase state: `{summary_payload['phase_state']}`",
        f"- Recommendation rows: {summary_payload['recommendation_row_count']}",
        f"- Recommended surface counts: `{summary_payload['recommended_surface_counts']}`",
        f"- Final visual/table retention authorized: `{summary_payload['final_visual_table_retention_authorized']}`",
        f"- Final manuscript prose permission: `{summary_payload['final_manuscript_prose_permission']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Recommendation Rows",
        "",
        "| Content area | Recommended surface | Status | Final retention | Claim boundary |",
        "|---|---|---|---:|---|",
    ]
    for row in payload["recommendation_rows"]:
        lines.append(
            "| `{content}` | `{surface}` | `{status}` | `{final}` | {boundary} |".format(
                content=row["content_area_id"],
                surface=row["recommended_surface"],
                status=row["recommendation_status"],
                final=row["final_retention_authorized"],
                boundary=row["claim_boundary"],
            )
        )
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


def matrix_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "cpfi_regression_article_supplement_retention_recommendation_matrix_v1",
        "generated_at_utc": payload["generated_at_utc"],
        "summary": {
            key: payload["summary"][key]
            for key in [
                "overall_status",
                "recommendation_row_count",
                "recommended_surface_counts",
                "final_visual_table_retention_authorized",
                "final_manuscript_prose_permission",
                "positive_claim_promotion_authorized",
            ]
        },
        "rows": payload["recommendation_rows"],
        "sources": payload["sources"],
    }


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root)
    out = Path(args.out)
    out = out if out.is_absolute() else root / out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    matrix_out = out.parent / "article_supplement_retention_recommendation_matrix.json"
    atomic_write_json(matrix_out, matrix_payload(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "overall_status": payload["summary"]["overall_status"],
                "recommendation_row_count": payload["summary"][
                    "recommendation_row_count"
                ],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
