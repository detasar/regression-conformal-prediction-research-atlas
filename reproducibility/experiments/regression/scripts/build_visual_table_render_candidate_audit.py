"""Build draft visual/table render candidates and layout-quality audit.

This is the second visual/table pass after the pre-retention audit. It creates
concrete draft artifacts so layout, caption, source-traceability, and overlap
checks can be measured. It does not retain figures or tables, authorize final
manuscript prose, cite the KG, deploy a site, or promote any method.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_visual_table_render_candidate_audit_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
)
PRE_RETENTION_AUDIT = Path(
    "experiments/regression/manuscript/visual_table_audit_report.json"
)
DRAFT_DIR = Path("experiments/regression/manuscript/draft_visual_table_artifacts")
MAX_FACTS_PER_SOURCE = 8
MAX_TOTAL_FACTS = 18
MAX_TABLE_ROWS = 24
MAX_MARKDOWN_LINE_LENGTH = 180


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


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def title_from_id(value: str) -> str:
    return value.replace("_", " ").title()


def scalar_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.6g}" if isinstance(value, float) else str(value)
    if isinstance(value, str):
        cleaned = " ".join(value.split())
        return cleaned[:120]
    if isinstance(value, list):
        return f"list[{len(value)}]"
    if isinstance(value, dict):
        return f"object[{len(value)}]"
    if value is None:
        return "null"
    return str(value)[:120]


def compact_text(value: str, limit: int = 76) -> str:
    cleaned = " ".join(str(value).split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: max(0, limit - 3)]}..."


def scalar_is_publication_safe(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def flatten_summary(prefix: str, payload: dict[str, Any]) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key in sorted(payload):
        value = payload[key]
        name = f"{prefix}.{key}" if prefix else str(key)
        if scalar_is_publication_safe(value):
            rows.append((name, value))
        elif isinstance(value, dict):
            nested_scalar = {
                nested_key: nested_value
                for nested_key, nested_value in value.items()
                if scalar_is_publication_safe(nested_value)
            }
            for nested_key in sorted(nested_scalar):
                rows.append((f"{name}.{nested_key}", nested_scalar[nested_key]))
        elif isinstance(value, list):
            rows.append((f"{name}.count", len(value)))
    return rows


def collect_source_facts(root: Path, source_path: str) -> list[dict[str, Any]]:
    path = root / source_path
    if not path.exists() or path.suffix.lower() != ".json":
        return [
            {
                "source_artifact": source_path,
                "metric": "source_exists",
                "value": path.exists(),
                "value_text": scalar_text(path.exists()),
            }
        ]
    try:
        payload = read_json(path)
    except json.JSONDecodeError:
        return [
            {
                "source_artifact": source_path,
                "metric": "json_parse_status",
                "value": "parse_error",
                "value_text": "parse_error",
            }
        ]
    source_summary = summary(payload)
    candidates = flatten_summary("", source_summary)
    preferred: list[tuple[str, Any]] = []
    other: list[tuple[str, Any]] = []
    preferred_tokens = (
        "overall_status",
        "claim_status",
        "failed",
        "blocked",
        "count",
        "ready",
        "complete",
        "coverage",
        "node",
        "edge",
        "row",
        "bundle",
        "candidate",
        "authorized",
    )
    for metric, value in candidates:
        target = preferred if any(token in metric for token in preferred_tokens) else other
        target.append((metric, value))
    selected = [*preferred, *other][:MAX_FACTS_PER_SOURCE]
    if not selected:
        selected = [("summary_present", bool(source_summary))]
    return [
        {
            "source_artifact": source_path,
            "metric": metric,
            "value": value,
            "value_text": scalar_text(value),
        }
        for metric, value in selected
    ]


def collect_candidate_facts(root: Path, row: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for source_path in row.get("source_artifacts") or []:
        facts.extend(collect_source_facts(root, str(source_path)))
    return facts[:MAX_TOTAL_FACTS]


def markdown_table(row: dict[str, Any], facts: list[dict[str, Any]]) -> str:
    content_id = str(row.get("content_area_id") or "unknown")
    title = title_from_id(content_id)
    source_paths = list(dict.fromkeys(str(fact["source_artifact"]) for fact in facts))
    source_ids = {source_path: f"S{index}" for index, source_path in enumerate(source_paths, start=1)}
    lines = [
        f"# Draft Table Candidate: {title}",
        "",
        "Status: draft render candidate only; no final visual/table retention, no final manuscript prose, and no positive method claim are authorized.",
        "",
        f"Reader question: {row.get('reader_question')}",
        "",
        f"Claim boundary: {row.get('claim_boundary')}",
        "",
        "Source path registry:",
        "",
    ]
    for source_path in source_paths:
        lines.append(f"- `{source_ids[source_path]}`: `{source_path}`")
    lines.extend(
        [
            "",
            "Source-traceable draft facts:",
            "",
            "| Source | Metric | Value |",
            "| --- | --- | --- |",
        ]
    )
    for fact in facts[:MAX_TABLE_ROWS]:
        lines.append(
            "| "
            f"`{source_ids[str(fact['source_artifact'])]}` | "
            f"`{compact_text(str(fact['metric']), 70)}` | "
            f"`{compact_text(str(fact['value_text']), 64)}` |"
        )
    lines.extend(
        [
            "",
            "Caption boundary: descriptive, diagnostic, and no-final-selection evidence only.",
            "",
        ]
    )
    return "\n".join(lines)


def numeric_fact_rows(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fact in facts:
        value = fact.get("value")
        if isinstance(value, bool):
            numeric_value = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            numeric_value = float(value)
        else:
            continue
        if numeric_value < 0:
            continue
        rows.append({**fact, "numeric_value": numeric_value})
    return rows[:8]


def svg_bar_chart(row: dict[str, Any], facts: list[dict[str, Any]]) -> str:
    content_id = str(row.get("content_area_id") or "unknown")
    title = title_from_id(content_id)
    numeric_rows = numeric_fact_rows(facts)
    if not numeric_rows:
        numeric_rows = [
            {
                "metric": "source_artifact_count",
                "value": len(row.get("source_artifacts") or []),
                "value_text": str(len(row.get("source_artifacts") or [])),
                "numeric_value": float(len(row.get("source_artifacts") or [])),
                "source_artifact": "visual_table_audit_report.json",
            }
        ]
    width = 960
    top = 84
    row_height = 42
    height = top + 54 + row_height * len(numeric_rows)
    label_x = 28
    bar_x = 360
    bar_max_width = 420
    value_x = bar_x + bar_max_width + 18
    max_value = max(float(item["numeric_value"]) for item in numeric_rows) or 1.0
    text_boxes: list[tuple[int, int, int, int]] = []

    def text_element(x: int, y: int, text: str, size: int = 14, weight: str = "400") -> str:
        escaped = html.escape(text)
        approx_width = min(width - x - 20, int(len(text) * size * 0.58))
        text_boxes.append((x, y - size, x + approx_width, y + 4))
        return (
            f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="#1f2937">{escaped}</text>'
        )

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
        "<title>Draft visual/table render candidate</title>",
        '<rect x="0" y="0" width="960" height="{0}" fill="#ffffff"/>'.format(height),
        text_element(label_x, 36, f"Draft Candidate: {title}", 20, "700"),
        text_element(
            label_x,
            62,
            "Diagnostic/no-claim draft; final retention and manuscript prose remain unauthorized.",
            14,
        ),
    ]
    for index, fact in enumerate(numeric_rows):
        y = top + index * row_height
        metric = str(fact["metric"])
        if len(metric) > 44:
            metric = f"{metric[:41]}..."
        value = float(fact["numeric_value"])
        bar_width = max(3, int((value / max_value) * bar_max_width))
        elements.append(text_element(label_x, y + 19, metric, 13))
        elements.append(
            f'<rect x="{bar_x}" y="{y}" width="{bar_width}" height="22" fill="#2563eb"/>'
        )
        elements.append(text_element(value_x, y + 17, str(fact["value_text"]), 13))
    elements.append(
        text_element(
            label_x,
            height - 18,
            "Caption boundary: source-traceable descriptive evidence only; no final method/model selection claim.",
            12,
        )
    )
    elements.append("</svg>")
    return "\n".join(elements)


def estimated_text_overlap(svg_text: str) -> bool:
    boxes: list[tuple[int, int, int, int]] = []
    for match in re.finditer(r'<text x="(\d+)" y="(\d+)"[^>]*font-size="(\d+)"[^>]*>(.*?)</text>', svg_text):
        x = int(match.group(1))
        y = int(match.group(2))
        size = int(match.group(3))
        text = re.sub(r"<[^>]+>", "", html.unescape(match.group(4)))
        boxes.append((x, y - size, x + int(len(text) * size * 0.58), y + 4))
    for index, first in enumerate(boxes):
        for second in boxes[index + 1 :]:
            horizontal = first[0] < second[2] and second[0] < first[2]
            vertical = first[1] < second[3] and second[1] < first[3]
            if horizontal and vertical:
                return True
    return False


def write_render_candidate(
    root: Path,
    row: dict[str, Any],
    facts: list[dict[str, Any]],
) -> dict[str, Any]:
    content_id = str(row.get("content_area_id") or "unknown")
    stem = slug(content_id)
    artifact_type = str(row.get("artifact_type") or "")
    draft_dir = root / DRAFT_DIR
    md_path = draft_dir / f"{stem}.md"
    md_text = markdown_table(row, facts)
    atomic_write_text(md_path, md_text)
    rendered_paths = [rel(md_path, root)]
    primary_path = md_path
    render_kind = "markdown_table"
    svg_path = None
    svg_text = ""
    if "figure" in artifact_type or content_id == "knowledge_graph_navigation_quality":
        svg_path = draft_dir / f"{stem}.svg"
        svg_text = svg_bar_chart(row, facts)
        atomic_write_text(svg_path, svg_text)
        rendered_paths.insert(0, rel(svg_path, root))
        primary_path = svg_path
        render_kind = "svg_bar_chart_plus_markdown_table"
    line_lengths = [len(line) for line in md_text.splitlines()]
    long_line_count = sum(1 for length in line_lengths if length > MAX_MARKDOWN_LINE_LENGTH)
    table_row_count = sum(1 for line in md_text.splitlines() if line.startswith("| "))
    overlap_detected = estimated_text_overlap(svg_text) if svg_text else False
    layout_status = (
        "pass"
        if long_line_count == 0
        and table_row_count <= MAX_TABLE_ROWS + 2
        and not overlap_detected
        else "revise"
    )
    return {
        "content_area_id": content_id,
        "artifact_type": row.get("artifact_type"),
        "render_kind": render_kind,
        "primary_rendered_artifact_path": rel(primary_path, root),
        "rendered_artifact_paths": rendered_paths,
        "source_artifacts": row.get("source_artifacts") or [],
        "source_fact_count": len(facts),
        "reader_question": row.get("reader_question"),
        "claim_boundary": row.get("claim_boundary"),
        "pre_retention_auditor_decision": row.get("pre_retention_auditor_decision"),
        "draft_render_status": "rendered_draft_candidate",
        "layout_quality_status": layout_status,
        "markdown_long_line_count": long_line_count,
        "markdown_table_row_count": table_row_count,
        "svg_static_text_overlap_detected": overlap_detected,
        "caption_quality_status": (
            "pass"
            if row.get("reader_question") and row.get("claim_boundary")
            else "revise"
        ),
        "source_traceability_status": (
            "pass" if row.get("source_artifacts") and facts else "revise"
        ),
        "final_retention_authorized": False,
        "retained_visual_or_table_decision": "not_started",
        "final_manuscript_prose_permission": False,
        "positive_claim_promotion_authorized": False,
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


def build_inventory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "cpfi_regression_visual_table_render_candidate_inventory_v1",
        "summary": {
            "candidate_row_count": len(rows),
            "rendered_draft_artifact_count": len(rows),
            "primary_rendered_artifact_count": len(
                [row for row in rows if row["primary_rendered_artifact_path"]]
            ),
            "supporting_artifact_count": sum(
                max(0, len(row["rendered_artifact_paths"]) - 1) for row in rows
            ),
            "final_retained_artifact_count": 0,
            "final_visual_table_retention_authorized": False,
        },
        "rows": rows,
    }


def build_layout_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(row["layout_quality_status"] for row in rows)
    return {
        "schema": "cpfi_regression_visual_table_layout_quality_audit_v1",
        "summary": {
            "layout_audit_row_count": len(rows),
            "layout_pass_count": int(status_counts.get("pass", 0)),
            "layout_revise_count": int(status_counts.get("revise", 0)),
            "caption_pass_count": sum(
                1 for row in rows if row["caption_quality_status"] == "pass"
            ),
            "source_traceability_pass_count": sum(
                1 for row in rows if row["source_traceability_status"] == "pass"
            ),
            "svg_static_text_overlap_detected_count": sum(
                1 for row in rows if row["svg_static_text_overlap_detected"]
            ),
            "final_retention_authorized": False,
        },
        "rows": [
            {
                "content_area_id": row["content_area_id"],
                "layout_quality_status": row["layout_quality_status"],
                "caption_quality_status": row["caption_quality_status"],
                "source_traceability_status": row["source_traceability_status"],
                "primary_rendered_artifact_path": row[
                    "primary_rendered_artifact_path"
                ],
                "markdown_long_line_count": row["markdown_long_line_count"],
                "markdown_table_row_count": row["markdown_table_row_count"],
                "svg_static_text_overlap_detected": row[
                    "svg_static_text_overlap_detected"
                ],
                "final_retention_authorized": False,
            }
            for row in rows
        ],
    }


def build_payload(root: Path) -> dict[str, Any]:
    pre_retention = read_json(root / PRE_RETENTION_AUDIT)
    pre_summary = summary(pre_retention)
    pre_rows = [
        row
        for row in pre_retention.get("audit_rows") or []
        if isinstance(row, dict)
    ]
    rendered_rows: list[dict[str, Any]] = []
    for row in pre_rows:
        facts = collect_candidate_facts(root, row)
        rendered_rows.append(write_render_candidate(root, row, facts))
    inventory = build_inventory(rendered_rows)
    layout_audit = build_layout_audit(rendered_rows)
    final_retained_count = sum(
        1 for row in rendered_rows if row["final_retention_authorized"]
    )
    failed_layout_count = layout_audit["summary"]["layout_revise_count"]
    failed_checks: list[dict[str, Any]]
    checks = [
        check_row(
            "pre_retention_audit_clean",
            pre_summary.get("overall_status")
            == "visual_table_pre_retention_audit_completed_no_retained_artifacts"
            and safe_int(pre_summary.get("failed_check_count")) == 0,
            {
                "pre_retention_status": pre_summary.get("overall_status"),
                "pre_retention_failed_check_count": pre_summary.get(
                    "failed_check_count"
                ),
            },
            "pre_retention_audit_not_clean",
        ),
        check_row(
            "all_candidates_rendered_as_drafts",
            len(rendered_rows) == 10
            and all(row["primary_rendered_artifact_path"] for row in rendered_rows),
            {"rendered_row_count": len(rendered_rows)},
            "draft_render_candidate_missing",
        ),
        check_row(
            "layout_quality_passes_for_all_drafts",
            failed_layout_count == 0 and len(rendered_rows) == 10,
            layout_audit["summary"],
            "draft_layout_quality_issue",
        ),
        check_row(
            "captions_and_claim_boundaries_present",
            layout_audit["summary"]["caption_pass_count"] == len(rendered_rows) == 10,
            {
                "caption_pass_count": layout_audit["summary"]["caption_pass_count"],
                "candidate_count": len(rendered_rows),
            },
            "caption_or_claim_boundary_missing",
        ),
        check_row(
            "sources_traceable_for_all_drafts",
            layout_audit["summary"]["source_traceability_pass_count"]
            == len(rendered_rows)
            == 10,
            {
                "source_traceability_pass_count": layout_audit["summary"][
                    "source_traceability_pass_count"
                ],
                "candidate_count": len(rendered_rows),
            },
            "draft_source_traceability_missing",
        ),
        check_row(
            "no_final_retention_or_release",
            final_retained_count == 0,
            {
                "final_retained_artifact_count": final_retained_count,
                "kg_citable_component_authorized": False,
                "publication_site_deployment_authorized": False,
                "final_manuscript_prose_permission": False,
                "positive_claim_promotion_authorized": False,
            },
            "unexpected_final_retention_or_release",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] == "fail"]
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "summary": {
            "overall_status": (
                "draft_visual_table_render_audit_completed_no_final_retention"
                if not failed_checks
                else "draft_visual_table_render_audit_blocked"
            ),
            "phase_state": (
                "draft_render_candidates_complete_final_retention_and_release_blocked"
            ),
            "pre_retention_input_row_count": len(pre_rows),
            "candidate_row_count": len(rendered_rows),
            "rendered_draft_artifact_count": len(rendered_rows),
            "primary_rendered_artifact_count": inventory["summary"][
                "primary_rendered_artifact_count"
            ],
            "supporting_artifact_count": inventory["summary"][
                "supporting_artifact_count"
            ],
            "layout_audit_row_count": layout_audit["summary"][
                "layout_audit_row_count"
            ],
            "layout_pass_count": layout_audit["summary"]["layout_pass_count"],
            "layout_revise_count": layout_audit["summary"]["layout_revise_count"],
            "caption_pass_count": layout_audit["summary"]["caption_pass_count"],
            "source_traceability_pass_count": layout_audit["summary"][
                "source_traceability_pass_count"
            ],
            "svg_static_text_overlap_detected_count": layout_audit["summary"][
                "svg_static_text_overlap_detected_count"
            ],
            "final_retained_artifact_count": final_retained_count,
            "final_visual_table_retention_authorized": False,
            "kg_citable_component_authorized": False,
            "publication_site_deployment_authorized": False,
            "final_triptych_release_authorized": False,
            "final_manuscript_prose_permission": False,
            "positive_claim_promotion_authorized": False,
            "neutral_no_method_promotion_guard_active": True,
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
        },
        "checks": checks,
        "failed_checks": [row["check_id"] for row in failed_checks],
        "render_candidate_rows": rendered_rows,
        "visual_table_render_candidate_inventory": inventory,
        "visual_table_layout_quality_audit": layout_audit,
        "claim_boundaries": [
            "Draft rendered artifacts are measurement surfaces only; they are not retained figures or tables.",
            "No draft artifact authorizes final manuscript prose, KG citation, site deployment, or final triptych release.",
            "CQR, CV+, Venn-Abers, fairness, bounded-support, and final-selection claims remain bounded by audited no-claim or diagnostic evidence.",
        ],
        "sources": {
            "pre_retention_visual_table_audit_report": rel(
                root / PRE_RETENTION_AUDIT, root
            ),
            "draft_artifact_directory": rel(root / DRAFT_DIR, root),
        },
    }


def render_report_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Visual/Table Render Candidate Audit",
        "",
        "This audit creates draft render candidates for layout measurement only. It does not retain figures or tables, authorize final manuscript prose, cite the KG, deploy a site, or promote any method.",
        "",
        f"- Generated UTC: `{payload['generated_at_utc']}`",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Draft candidates: {summary_payload['candidate_row_count']}",
        f"- Rendered draft artifacts: {summary_payload['rendered_draft_artifact_count']}",
        f"- Layout pass / revise: {summary_payload['layout_pass_count']} / {summary_payload['layout_revise_count']}",
        f"- Static SVG text-overlap detections: {summary_payload['svg_static_text_overlap_detected_count']}",
        f"- Final retained artifacts: {summary_payload['final_retained_artifact_count']}",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Draft Candidates",
        "",
        "| Content Area | Render Kind | Layout | Primary Artifact |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["render_candidate_rows"]:
        lines.append(
            "| "
            f"`{row['content_area_id']}` | "
            f"`{row['render_kind']}` | "
            f"`{row['layout_quality_status']}` | "
            f"`{row['primary_rendered_artifact_path']}` |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for row in payload["checks"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` |")
    lines.append("")
    return "\n".join(lines)


def render_artifact_index(payload: dict[str, Any]) -> str:
    lines = [
        "# Draft Visual/Table Artifacts",
        "",
        "These files are draft render candidates for measurement. They are not final retained article or supplement artifacts.",
        "",
    ]
    for index, row in enumerate(payload["render_candidate_rows"], start=1):
        lines.append(f"## {index}. `{row['content_area_id']}`")
        lines.append("")
        for path in row["rendered_artifact_paths"]:
            lines.append(f"- `{path}`")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def write_sidecars(out: Path, payload: dict[str, Any], root: Path) -> None:
    base_dir = out.parent
    atomic_write_json(
        base_dir / "visual_table_render_candidate_inventory.json",
        {
            **payload["visual_table_render_candidate_inventory"],
            "generated_at_utc": payload["generated_at_utc"],
            "sources": payload["sources"],
        },
    )
    atomic_write_json(
        base_dir / "visual_table_layout_quality_audit.json",
        {
            **payload["visual_table_layout_quality_audit"],
            "generated_at_utc": payload["generated_at_utc"],
            "sources": payload["sources"],
        },
    )
    atomic_write_text(root / DRAFT_DIR / "README.md", render_artifact_index(payload))


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_report_markdown(payload))
    write_sidecars(out, payload, root)
    print(
        json.dumps(
            {
                "status": "ok" if not payload["failed_checks"] else "fail",
                "overall_status": payload["summary"]["overall_status"],
                "candidate_row_count": payload["summary"]["candidate_row_count"],
                "rendered_draft_artifact_count": payload["summary"][
                    "rendered_draft_artifact_count"
                ],
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
