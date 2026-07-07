"""Build final visual/table auditor readiness without final retention.

This artifact starts the publication visual-auditor feedback loop as a
pre-prose, no-retention control. It reviews draft visual/table candidates for
layout, caption, provenance, reader value, and claim-boundary readiness. It
does not retain final figures or tables, write manuscript prose, deploy a site,
cite the KG as final, create a sterile repository, or promote any method.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_final_publication_visual_auditor_readiness_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/"
    "final_publication_visual_auditor_readiness.json"
)

VISUAL_RENDER = Path(
    "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
)
RETENTION_READINESS = Path(
    "experiments/regression/manuscript/publication_retention_readiness_audit.json"
)
VISUAL_AUDIT_REPORT = Path(
    "experiments/regression/manuscript/visual_table_audit_report.json"
)
REVIEWER_DESIGN = Path("experiments/regression/manuscript/reviewer_design_brief.json")
CONTENT_MATRIX = Path(
    "experiments/regression/manuscript/article_supplement_content_matrix.json"
)
SECTION_BOUNDARY = Path(
    "experiments/regression/manuscript/section_claim_boundary_audit.json"
)
NEUTRAL_LANGUAGE = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "neutral_reporting_language_audit.json"
)
RELEASE_GAP = Path(
    "experiments/regression/manuscript/publication_release_gap_register.json"
)

SOURCE_PATHS = {
    "visual_table_render_candidate_audit": VISUAL_RENDER,
    "publication_retention_readiness_audit": RETENTION_READINESS,
    "visual_table_audit_report": VISUAL_AUDIT_REPORT,
    "reviewer_design_brief": REVIEWER_DESIGN,
    "article_supplement_content_matrix": CONTENT_MATRIX,
    "section_claim_boundary_audit": SECTION_BOUNDARY,
    "neutral_reporting_language_audit": NEUTRAL_LANGUAGE,
    "publication_release_gap_register": RELEASE_GAP,
}

FINAL_AUTHORIZATION_FIELDS = (
    "final_retention_authorized",
    "final_visual_table_retention_authorized",
    "final_manuscript_prose_permission",
    "publication_site_deployment_authorized",
    "kg_citable_component_authorized",
    "sterile_repository_creation_authorized",
    "method_recommendation_authorized",
    "positive_claim_promotion_authorized",
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


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def source_status(root: Path) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for path in SOURCE_PATHS.values():
        relative = rel(root / path, root)
        if (root / path).exists():
            present.append(relative)
        else:
            missing.append(relative)
    return present, missing


def content_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    rows = payload.get("article_supplement_content_matrix")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def row_by_content_id(payload: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("content_area_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("content_area_id")
    }


def final_authorization_violations(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for source_name, payload in payloads.items():
        source_summary = summary(payload)
        for field in FINAL_AUTHORIZATION_FIELDS:
            if source_summary.get(field) is True:
                violations.append({"source": source_name, "field": field})
        for row_key in (
            "render_candidate_rows",
            "recommendation_rows",
            "visual_auditor_feedback_rows",
        ):
            rows = payload.get(row_key)
            if not isinstance(rows, list):
                continue
            for row_index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                for field in FINAL_AUTHORIZATION_FIELDS:
                    if row.get(field) is True:
                        violations.append(
                            {
                                "source": source_name,
                                "row_key": row_key,
                                "row_index": row_index,
                                "field": field,
                            }
                        )
    return violations


def feedback_items_for(row: dict[str, Any]) -> list[dict[str, str]]:
    content_id = str(row.get("content_area_id") or "")
    items = [
        {
            "feedback_id": f"{content_id}:caption_claim_boundary",
            "severity": "required",
            "feedback": (
                "Keep the caption scoped to the recorded claim boundary and "
                "avoid converting diagnostic evidence into a final claim."
            ),
        },
        {
            "feedback_id": f"{content_id}:source_registry",
            "severity": "required",
            "feedback": (
                "Retain source-path references beside the visual/table so every "
                "visible fact can be traced to a checked artifact."
            ),
        },
        {
            "feedback_id": f"{content_id}:layout_regression_check",
            "severity": "required",
            "feedback": (
                "Re-run layout and overlap checks after any manuscript, HTML, or "
                "LaTeX rendering change."
            ),
        },
    ]
    gate_dependency = str(row.get("gate_dependency") or "")
    if gate_dependency:
        items.append(
            {
                "feedback_id": f"{content_id}:gate_dependency_label",
                "severity": "required",
                "feedback": (
                    f"Carry the `{gate_dependency}` dependency label into final "
                    "review notes so readers do not infer a stronger claim."
                ),
            }
        )
    if row.get("recommended_surface") == "kg_or_site_candidate_release_blocked":
        items.append(
            {
                "feedback_id": f"{content_id}:kg_site_release_boundary",
                "severity": "required",
                "feedback": (
                    "Keep KG/site use blocked until release, KG citation, and "
                    "sterile repository gates explicitly authorize publication."
                ),
            }
        )
    return items


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


def build_payload(root: Path) -> dict[str, Any]:
    payloads = {name: read_json(root / path) for name, path in SOURCE_PATHS.items()}
    present_sources, missing_sources = source_status(root)

    render_payload = payloads["visual_table_render_candidate_audit"]
    retention_payload = payloads["publication_retention_readiness_audit"]
    visual_report_payload = payloads["visual_table_audit_report"]
    reviewer_payload = payloads["reviewer_design_brief"]
    content_payload = payloads["article_supplement_content_matrix"]
    section_payload = payloads["section_claim_boundary_audit"]
    language_payload = payloads["neutral_reporting_language_audit"]
    release_payload = payloads["publication_release_gap_register"]

    render_summary = summary(render_payload)
    retention_summary = summary(retention_payload)
    visual_report_summary = summary(visual_report_payload)
    reviewer_summary = summary(reviewer_payload)
    section_summary = summary(section_payload)
    language_summary = summary(language_payload)
    release_summary = summary(release_payload)

    content_by_id = {
        str(row.get("content_area_id")): row
        for row in content_rows(content_payload)
        if row.get("content_area_id")
    }
    retention_by_id = row_by_content_id(retention_payload, "recommendation_rows")

    feedback_rows: list[dict[str, Any]] = []
    missing_rendered_artifacts: list[str] = []
    incomplete_feedback_rows: list[str] = []
    for row_index, render_row in enumerate(
        render_payload.get("render_candidate_rows") or []
    ):
        if not isinstance(render_row, dict):
            continue
        content_id = str(render_row.get("content_area_id") or "").strip()
        if not content_id:
            continue
        retention_row = retention_by_id.get(content_id, {})
        content_row = content_by_id.get(content_id, {})
        source_artifacts = list(
            dict.fromkeys(
                [
                    *(render_row.get("source_artifacts") or []),
                    *(retention_row.get("source_artifacts") or []),
                    str(VISUAL_RENDER),
                    str(RETENTION_READINESS),
                    str(SECTION_BOUNDARY),
                ]
            )
        )
        rendered_paths = [
            str(path)
            for path in render_row.get("rendered_artifact_paths") or []
            if isinstance(path, str)
        ]
        primary_path = str(render_row.get("primary_rendered_artifact_path") or "")
        if primary_path and primary_path not in rendered_paths:
            rendered_paths.insert(0, primary_path)
        missing_paths = [path for path in rendered_paths if not (root / path).exists()]
        missing_rendered_artifacts.extend(missing_paths)

        layout_pass = render_row.get("layout_quality_status") == "pass"
        caption_pass = render_row.get("caption_quality_status") == "pass"
        traceability_pass = render_row.get("source_traceability_status") == "pass"
        no_overlap = render_row.get("svg_static_text_overlap_detected") is False
        claim_boundary_present = bool(
            str(render_row.get("claim_boundary") or "").strip()
        )
        reader_question_present = bool(
            str(render_row.get("reader_question") or "").strip()
        )
        recommendation_ready = (
            retention_row.get("recommendation_status")
            == "recommendation_ready_no_final_retention"
        )
        no_final_authorization = all(
            render_row.get(field) is not True
            and retention_row.get(field) is not True
            for field in FINAL_AUTHORIZATION_FIELDS
        )
        source_paths_exist = all((root / source).exists() for source in source_artifacts)
        feedback_items = feedback_items_for(
            {
                **render_row,
                "recommended_surface": retention_row.get("recommended_surface"),
                "gate_dependency": retention_row.get("gate_dependency")
                or content_row.get("gate_dependency"),
            }
        )
        feedback_ready = all(
            [
                layout_pass,
                caption_pass,
                traceability_pass,
                no_overlap,
                claim_boundary_present,
                reader_question_present,
                recommendation_ready,
                no_final_authorization,
                source_paths_exist,
                not missing_paths,
                bool(feedback_items),
            ]
        )
        if not feedback_ready:
            incomplete_feedback_rows.append(content_id)
        feedback_rows.append(
            {
                "content_area_id": content_id,
                "row_index": row_index,
                "artifact_type": render_row.get("artifact_type"),
                "render_kind": render_row.get("render_kind"),
                "primary_rendered_artifact_path": primary_path,
                "rendered_artifact_paths": rendered_paths,
                "missing_rendered_artifact_paths": missing_paths,
                "recommended_surface": retention_row.get("recommended_surface"),
                "retention_readiness_decision": retention_row.get(
                    "retention_readiness_decision"
                ),
                "target_surfaces": retention_row.get("target_surfaces")
                or content_row.get("target_surfaces")
                or [],
                "reader_question": render_row.get("reader_question")
                or content_row.get("reader_question"),
                "claim_boundary": render_row.get("claim_boundary")
                or content_row.get("claim_boundary"),
                "gate_dependency": retention_row.get("gate_dependency")
                or content_row.get("gate_dependency")
                or "",
                "layout_quality_status": render_row.get("layout_quality_status"),
                "caption_quality_status": render_row.get("caption_quality_status"),
                "source_traceability_status": render_row.get(
                    "source_traceability_status"
                ),
                "svg_static_text_overlap_detected": render_row.get(
                    "svg_static_text_overlap_detected"
                ),
                "claim_boundary_present": claim_boundary_present,
                "reader_question_present": reader_question_present,
                "source_traceability_artifact_status": (
                    "pass" if source_paths_exist else "missing_source_artifact"
                ),
                "feedback_item_count": len(feedback_items),
                "feedback_items": feedback_items,
                "visual_auditor_feedback_status": (
                    "feedback_ready_no_final_retention"
                    if feedback_ready
                    else "feedback_blocked"
                ),
                "final_retention_authorized": False,
                "final_visual_table_retention_authorized": False,
                "final_manuscript_prose_permission": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "source_artifacts": source_artifacts,
            }
        )

    authorization_violations = final_authorization_violations(payloads)
    feedback_status_counts = Counter(
        row["visual_auditor_feedback_status"] for row in feedback_rows
    )
    recommended_surface_counts = Counter(
        row.get("recommended_surface") or "unknown" for row in feedback_rows
    )
    checks = [
        check_row(
            "all_required_sources_present",
            not missing_sources,
            {"missing_source_artifacts": missing_sources},
            "missing_visual_auditor_source_artifact",
        ),
        check_row(
            "render_and_retention_inputs_complete",
            (
                render_summary.get("overall_status")
                == "draft_visual_table_render_audit_completed_no_final_retention"
                and retention_summary.get("overall_status")
                == "publication_retention_readiness_ready_no_final_prose"
                and safe_int(render_summary.get("candidate_row_count"))
                == safe_int(retention_summary.get("recommendation_row_count"))
                == len(feedback_rows)
                == 10
            ),
            {
                "render_status": render_summary.get("overall_status"),
                "retention_status": retention_summary.get("overall_status"),
                "render_candidate_count": render_summary.get("candidate_row_count"),
                "retention_recommendation_count": retention_summary.get(
                    "recommendation_row_count"
                ),
                "feedback_row_count": len(feedback_rows),
            },
            "visual_auditor_input_count_or_status_mismatch",
        ),
        check_row(
            "layout_caption_overlap_traceability_clean",
            (
                safe_int(render_summary.get("layout_pass_count")) == 10
                and safe_int(render_summary.get("caption_pass_count")) == 10
                and safe_int(render_summary.get("source_traceability_pass_count")) == 10
                and safe_int(
                    render_summary.get("svg_static_text_overlap_detected_count")
                )
                == 0
                and not missing_rendered_artifacts
            ),
            {
                "layout_pass_count": render_summary.get("layout_pass_count"),
                "caption_pass_count": render_summary.get("caption_pass_count"),
                "source_traceability_pass_count": render_summary.get(
                    "source_traceability_pass_count"
                ),
                "svg_static_text_overlap_detected_count": render_summary.get(
                    "svg_static_text_overlap_detected_count"
                ),
                "missing_rendered_artifacts": missing_rendered_artifacts,
            },
            "visual_auditor_layout_caption_or_render_artifact_issue",
        ),
        check_row(
            "claim_boundaries_and_neutrality_locked",
            (
                section_summary.get("overall_status")
                == "section_claim_boundary_audit_pass_no_final_claims"
                and language_summary.get("overall_status")
                == "neutral_reporting_language_audit_pass"
                and safe_int(language_summary.get("unguarded_hit_count")) == 0
                and section_summary.get("main_results_positive_boundary_blocked")
                is True
                and section_summary.get("venn_abers_negative_boundary_preserved")
                is True
            ),
            {
                "section_boundary_status": section_summary.get("overall_status"),
                "neutral_language_status": language_summary.get("overall_status"),
                "unguarded_hit_count": language_summary.get("unguarded_hit_count"),
            },
            "visual_auditor_claim_boundary_or_neutrality_issue",
        ),
        check_row(
            "feedback_loop_rows_complete",
            (
                len(feedback_rows) == 10
                and not incomplete_feedback_rows
                and feedback_status_counts
                == {"feedback_ready_no_final_retention": 10}
            ),
            {
                "feedback_row_count": len(feedback_rows),
                "incomplete_feedback_rows": incomplete_feedback_rows,
                "feedback_status_counts": dict(sorted(feedback_status_counts.items())),
            },
            "visual_auditor_feedback_row_incomplete",
        ),
        check_row(
            "final_outputs_and_release_remain_blocked",
            (
                not authorization_violations
                and release_summary.get("overall_status")
                == "publication_release_gap_register_ready_no_final_release"
                and safe_int(release_summary.get("release_authorized_count")) == 0
                and visual_report_summary.get("final_visual_table_retention_authorized")
                is False
                and reviewer_summary.get("manuscript_drafting_authorized") is False
            ),
            {
                "authorization_violations": authorization_violations,
                "release_status": release_summary.get("overall_status"),
                "release_authorized_count": release_summary.get(
                    "release_authorized_count"
                ),
                "visual_report_final_retention": visual_report_summary.get(
                    "final_visual_table_retention_authorized"
                ),
                "reviewer_manuscript_drafting_authorized": reviewer_summary.get(
                    "manuscript_drafting_authorized"
                ),
            },
            "final_visual_or_publication_output_authorized_too_early",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    final_retained_artifact_count = sum(
        1 for row in feedback_rows if row["final_retention_authorized"]
    )
    feedback_loop_ready = not failed_checks
    summary_payload = {
        "overall_status": (
            "final_publication_visual_auditor_feedback_loop_ready_no_retention"
            if feedback_loop_ready
            else "final_publication_visual_auditor_feedback_loop_blocked"
        ),
        "phase_state": (
            "pre_final_visual_auditor_feedback_ready_final_retention_blocked"
        ),
        "final_publication_visual_auditor_status": (
            "feedback_loop_ready_no_final_retention"
            if feedback_loop_ready
            else "feedback_loop_blocked"
        ),
        "feedback_loop_ready": feedback_loop_ready,
        "feedback_row_count": len(feedback_rows),
        "feedback_ready_row_count": feedback_status_counts.get(
            "feedback_ready_no_final_retention", 0
        ),
        "feedback_blocked_row_count": feedback_status_counts.get(
            "feedback_blocked", 0
        ),
        "feedback_item_count": sum(row["feedback_item_count"] for row in feedback_rows),
        "recommended_surface_counts": dict(sorted(recommended_surface_counts.items())),
        "main_article_candidate_count": recommended_surface_counts.get(
            "main_article_candidate_after_final_prose_gate", 0
        ),
        "supplement_candidate_count": recommended_surface_counts.get(
            "supplement_candidate_after_final_prose_gate", 0
        ),
        "kg_or_site_candidate_count": recommended_surface_counts.get(
            "kg_or_site_candidate_release_blocked", 0
        ),
        "layout_pass_count": safe_int(render_summary.get("layout_pass_count")),
        "caption_pass_count": safe_int(render_summary.get("caption_pass_count")),
        "source_traceability_pass_count": safe_int(
            render_summary.get("source_traceability_pass_count")
        ),
        "svg_static_text_overlap_detected_count": safe_int(
            render_summary.get("svg_static_text_overlap_detected_count")
        ),
        "missing_rendered_artifact_count": len(missing_rendered_artifacts),
        "authorization_violation_count": len(authorization_violations),
        "release_authorized_count": safe_int(
            release_summary.get("release_authorized_count")
        ),
        "final_retained_artifact_count": final_retained_artifact_count,
        "final_visual_table_retention_authorized": False,
        "final_manuscript_prose_permission": False,
        "publication_site_deployment_authorized": False,
        "kg_citable_component_authorized": False,
        "sterile_repository_creation_authorized": False,
        "method_recommendation_authorized": False,
        "positive_claim_promotion_authorized": False,
        "main_results_positive_boundary_blocked": section_summary.get(
            "main_results_positive_boundary_blocked"
        ),
        "venn_abers_negative_boundary_preserved": section_summary.get(
            "venn_abers_negative_boundary_preserved"
        ),
        "neutral_language_unguarded_hit_count": safe_int(
            language_summary.get("unguarded_hit_count")
        ),
        "source_artifact_count": len(present_sources),
        "missing_source_artifact_count": len(missing_sources),
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary_payload,
        "claim_boundaries": [
            "This artifact starts a pre-final visual/table auditor feedback loop; it is not a final figure or table retention decision.",
            "All feedback rows preserve neutral, source-traceable, no-method-promotion language.",
            "Final manuscript prose, final retained visuals/tables, KG/site deployment, sterile repository creation, method recommendation, and positive-claim promotion remain unauthorized.",
        ],
        "visual_auditor_feedback_rows": feedback_rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "sources": {name: rel(root / path, root) for name, path in SOURCE_PATHS.items()},
        "present_source_artifacts": present_sources,
        "missing_source_artifacts": missing_sources,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Final Publication Visual Auditor Readiness",
        "",
        "This pre-final artifact records visual/table auditor feedback readiness. It does not authorize final retained figures or tables, manuscript prose, KG/site release, sterile repository creation, method recommendation, or positive-claim promotion.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Auditor status: `{summary_payload['final_publication_visual_auditor_status']}`",
        f"- Feedback rows ready: {summary_payload['feedback_ready_row_count']} / {summary_payload['feedback_row_count']}",
        f"- Feedback items: {summary_payload['feedback_item_count']}",
        f"- Missing rendered artifacts: {summary_payload['missing_rendered_artifact_count']}",
        f"- Final retention authorized: `{summary_payload['final_visual_table_retention_authorized']}`",
        f"- Positive-claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Feedback Rows",
        "",
        "| Content Area | Surface | Status | Feedback Items |",
        "|---|---|---:|---:|",
    ]
    for row in payload["visual_auditor_feedback_rows"]:
        lines.append(
            "| "
            f"`{row['content_area_id']}` | "
            f"`{row.get('recommended_surface')}` | "
            f"`{row['visual_auditor_feedback_status']}` | "
            f"{row['feedback_item_count']} |"
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


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(json.dumps(payload["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
