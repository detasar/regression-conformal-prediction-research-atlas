"""Audit section-level claim boundaries before manuscript prose.

This audit sits after the manuscript section evidence packet. It verifies that
each section packet has an explicit allowed-use, blocked-use, claim-safe
surface, neutral-result link, and blocked release target. It does not draft
final prose, select a method, promote CQR/CV+, validate Venn-Abers regression,
or authorize a release.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_section_claim_boundary_audit_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/section_claim_boundary_audit.json")
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

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
POST_PROGRAM = Path(
    "experiments/regression/manuscript/post_experiment_publication_program.json"
)
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
VENN_NEGATIVE = REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"

SOURCE_PATHS = {
    "section_packet": SECTION_PACKET,
    "claim_safe_matrix": CLAIM_SAFE_MATRIX,
    "neutral_ledger": NEUTRAL_LEDGER,
    "release_gap": RELEASE_GAP,
    "post_experiment_publication_program": POST_PROGRAM,
    "neutral_language": NEUTRAL_LANGUAGE,
    "venn_abers_negative": VENN_NEGATIVE,
}

TARGET_DOCUMENT_RELEASE_TARGETS = {
    "main_article": ["main_article_latex", "main_article_html"],
    "supplementary_document": [
        "supplementary_document",
        "supplementary_document_latex",
        "supplementary_document_html",
    ],
    "individual_experiment_report": ["individual_experiment_report"],
}

AUTHORIZATION_FIELDS = (
    "final_section_prose_authorized",
    "final_manuscript_prose_permission",
    "final_visual_table_retention_authorized",
    "release_authorized",
    "publication_site_deployment_authorized",
    "kg_citable_component_authorized",
    "sterile_repository_creation_authorized",
    "working_repository_final_citable",
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


def text_present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def neutral_ledger_boundary_gap(row: dict[str, Any]) -> bool:
    return not (
        text_present(row.get("allowed_reporting_use"))
        and text_present(row.get("blocked_reporting_use"))
        and text_present(row.get("claim_boundary"))
    )


def release_targets_for(target_document: str) -> list[str]:
    return TARGET_DOCUMENT_RELEASE_TARGETS.get(target_document, [])


def build_boundary_rows(
    section_packet: dict[str, Any],
    claim_safe: dict[str, Any],
    neutral_ledger: dict[str, Any],
    release_gap: dict[str, Any],
) -> list[dict[str, Any]]:
    surfaces = rows_by_key(claim_safe, "surface_rows", "surface_id")
    results = rows_by_key(neutral_ledger, "result_rows", "result_id")
    deliverables = rows_by_key(release_gap, "deliverable_rows", "deliverable_id")

    rows: list[dict[str, Any]] = []
    for row_index, packet in enumerate(section_packet.get("section_packet_rows") or []):
        if not isinstance(packet, dict):
            continue
        packet_id = str(packet.get("packet_id") or "")
        target_document = str(packet.get("target_document") or "")
        surface_id = str(packet.get("claim_safe_surface_id") or "")
        surface = surfaces.get(surface_id, {})
        result_ids = [str(result_id) for result_id in packet.get("neutral_result_ids") or []]
        linked_results = [results[result_id] for result_id in result_ids if result_id in results]
        missing_result_ids = [result_id for result_id in result_ids if result_id not in results]
        release_target_ids = release_targets_for(target_document)
        linked_release_targets = [
            deliverables[target_id] for target_id in release_target_ids if target_id in deliverables
        ]
        missing_release_targets = [
            target_id for target_id in release_target_ids if target_id not in deliverables
        ]
        ledger_gap_ids = [
            result_id
            for result_id in result_ids
            if result_id in results and neutral_ledger_boundary_gap(results[result_id])
        ]
        authorization_count = sum(bool(packet.get(field)) for field in AUTHORIZATION_FIELDS)
        allowed_use_present = text_present(packet.get("allowed_use"))
        blocked_use_present = text_present(packet.get("blocked_use"))
        section_claim_boundary_present = text_present(packet.get("claim_boundary"))
        boundary_complete = (
            allowed_use_present
            and blocked_use_present
            and section_claim_boundary_present
            and authorization_count == 0
        )
        surface_consistent = (
            bool(surface)
            and packet.get("claim_safe_surface_status")
            == surface.get("pre_prose_extraction_status")
            and bool(packet.get("claim_safe_surface_blocked"))
            == bool(surface.get("positive_claim_surface_blocked"))
        )
        release_targets_blocked = (
            bool(release_target_ids)
            and len(linked_release_targets) == len(release_target_ids)
            and all(target.get("release_authorized") is False for target in linked_release_targets)
        )
        main_positive_blocked = (
            packet_id == "paper_main_results_blocked_evidence"
            and packet.get("packet_status") == "blocked_positive_claim_packet"
            and packet.get("positive_claim_packet_blocked") is True
            and surface.get("pre_prose_extraction_status")
            == "blocked_positive_claim_surface"
        )
        negative_failure_mode = (
            packet_id == "supplement_venn_abers_negative_evidence"
            and packet.get("packet_status") == "pre_prose_negative_evidence_ready"
            and packet.get("positive_claim_packet_blocked") is False
            and result_ids == ["venn_abers_regression_negative_evidence"]
        )
        if main_positive_blocked:
            boundary_status = "blocked_positive_boundary_preserved"
            reporting_role = "positive_main_result_claim_blocked"
        elif negative_failure_mode:
            boundary_status = "negative_failure_mode_boundary_preserved"
            reporting_role = "venn_abers_negative_failure_mode_no_validation"
        else:
            boundary_status = "pre_prose_boundary_preserved"
            reporting_role = "descriptive_or_control_evidence_no_method_promotion"

        rows.append(
            {
                "packet_id": packet_id,
                "row_index": row_index,
                "target_document": target_document,
                "release_target_deliverable_ids": release_target_ids,
                "linked_release_target_count": len(linked_release_targets),
                "missing_release_target_ids": missing_release_targets,
                "release_target_authorized_count": sum(
                    target.get("release_authorized") is True
                    for target in linked_release_targets
                ),
                "packet_status": packet.get("packet_status"),
                "boundary_status": boundary_status,
                "scientific_reporting_role": reporting_role,
                "claim_safe_surface_id": surface_id,
                "claim_safe_surface_status": packet.get("claim_safe_surface_status"),
                "claim_safe_surface_consistent": surface_consistent,
                "neutral_result_ids": result_ids,
                "neutral_result_claim_statuses": [
                    result.get("claim_status") for result in linked_results
                ],
                "missing_neutral_result_ids": missing_result_ids,
                "neutral_ledger_prose_boundary_gap_result_ids": ledger_gap_ids,
                "section_allowed_use_present": allowed_use_present,
                "section_blocked_use_present": blocked_use_present,
                "section_claim_boundary_present": section_claim_boundary_present,
                "section_boundary_backfills_ledger_gap": bool(ledger_gap_ids)
                and boundary_complete,
                "boundary_complete": boundary_complete,
                "authorization_count": authorization_count,
                "release_targets_blocked": release_targets_blocked,
                "main_positive_boundary_blocked": main_positive_blocked,
                "venn_abers_negative_boundary_preserved": negative_failure_mode,
                "allowed_use": packet.get("allowed_use"),
                "blocked_use": packet.get("blocked_use"),
                "claim_boundary": packet.get("claim_boundary"),
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
    section_packet = read_json(root / SECTION_PACKET)
    claim_safe = read_json(root / CLAIM_SAFE_MATRIX)
    neutral_ledger = read_json(root / NEUTRAL_LEDGER)
    release_gap = read_json(root / RELEASE_GAP)
    post_program = read_json(root / POST_PROGRAM)
    neutral_language = read_json(root / NEUTRAL_LANGUAGE)
    venn_negative = read_json(root / VENN_NEGATIVE)

    section_summary = summary(section_packet)
    claim_safe_summary = summary(claim_safe)
    neutral_ledger_summary = summary(neutral_ledger)
    release_summary = summary(release_gap)
    neutral_language_summary = summary(neutral_language)
    venn_negative_summary = summary(venn_negative)

    present_sources, missing_sources = source_status(root)
    rows = build_boundary_rows(section_packet, claim_safe, neutral_ledger, release_gap)
    rows_by_id = {row["packet_id"]: row for row in rows}
    status_counts = Counter(row["boundary_status"] for row in rows)
    target_counts = Counter(row["target_document"] for row in rows)
    unique_ledger_gap_ids = sorted(
        {
            result_id
            for row in rows
            for result_id in row["neutral_ledger_prose_boundary_gap_result_ids"]
        }
    )
    release_target_ids = sorted(
        {
            target_id
            for row in rows
            for target_id in row["release_target_deliverable_ids"]
        }
    )
    boundary_complete_count = sum(row["boundary_complete"] for row in rows)
    allowed_complete_count = sum(row["section_allowed_use_present"] for row in rows)
    blocked_complete_count = sum(row["section_blocked_use_present"] for row in rows)
    surface_consistent_count = sum(row["claim_safe_surface_consistent"] for row in rows)
    neutral_linked_count = sum(not row["missing_neutral_result_ids"] for row in rows)
    release_linked_count = sum(not row["missing_release_target_ids"] for row in rows)
    section_backfill_count = sum(row["section_boundary_backfills_ledger_gap"] for row in rows)
    release_authorized_target_count = sum(
        row["release_target_authorized_count"] for row in rows
    )
    row_authorization_count = sum(row["authorization_count"] for row in rows)

    section_packet_clean = (
        section_summary.get("overall_status")
        == "manuscript_section_evidence_packet_ready_no_final_prose"
        and safe_int(section_summary.get("section_packet_row_count")) == 8
        and section_summary.get("method_recommendation_authorized") is False
        and section_summary.get("positive_claim_promotion_authorized") is False
        and section_summary.get("final_section_prose_authorized") is False
    )
    upstream_boundaries_clean = (
        claim_safe_summary.get("overall_status")
        == "claim_safe_result_extraction_matrix_ready_no_final_claims"
        and neutral_ledger_summary.get("overall_status")
        == "neutral_result_ledger_ready_no_method_promotion"
        and release_summary.get("overall_status")
        == "publication_release_gap_register_ready_no_final_release"
        and release_summary.get("release_authorized_count") == 0
        and release_summary.get("method_recommendation_authorized") is False
        and release_summary.get("positive_claim_promotion_authorized") is False
    )
    main_positive_boundary_blocked = (
        rows_by_id.get("paper_main_results_blocked_evidence", {}).get(
            "main_positive_boundary_blocked"
        )
        is True
    )
    venn_negative_boundary_preserved = (
        rows_by_id.get("supplement_venn_abers_negative_evidence", {}).get(
            "venn_abers_negative_boundary_preserved"
        )
        is True
        and venn_negative_summary.get("negative_result_reporting_ready") is True
        and venn_negative_summary.get("can_support_validated_venn_abers_regression")
        is False
    )
    no_method_promotion = (
        neutral_language_summary.get("overall_status")
        == "neutral_reporting_language_audit_pass"
        and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
        and claim_safe_summary.get("method_recommendation_authorized") is False
        and claim_safe_summary.get("positive_claim_promotion_authorized") is False
        and release_summary.get("method_recommendation_authorized") is False
        and release_summary.get("positive_claim_promotion_authorized") is False
    )
    post_program_controlled = (
        post_program.get("status") == "neutral_publication_preparation_active"
        and (post_program.get("sterile_publication_repository_plan") or {}).get(
            "working_repository_citation_status"
        )
        == "not_final_citable_repository"
    )

    checks = [
        check_row(
            "source_artifacts_present",
            not missing_sources and len(present_sources) == len(SOURCE_PATHS),
            {
                "source_artifact_count": len(present_sources),
                "missing_source_artifacts": missing_sources,
            },
            "section_claim_boundary_source_missing",
        ),
        check_row(
            "section_packet_clean",
            section_packet_clean,
            {
                "section_packet_status": section_summary.get("overall_status"),
                "section_packet_row_count": section_summary.get(
                    "section_packet_row_count"
                ),
            },
            "section_packet_not_clean",
        ),
        check_row(
            "upstream_boundaries_clean",
            upstream_boundaries_clean,
            {
                "claim_safe_status": claim_safe_summary.get("overall_status"),
                "neutral_ledger_status": neutral_ledger_summary.get("overall_status"),
                "release_gap_status": release_summary.get("overall_status"),
                "release_authorized_count": release_summary.get(
                    "release_authorized_count"
                ),
            },
            "upstream_claim_boundaries_not_clean",
        ),
        check_row(
            "section_rows_have_complete_boundaries",
            len(rows) == 8
            and boundary_complete_count == 8
            and allowed_complete_count == 8
            and blocked_complete_count == 8
            and row_authorization_count == 0,
            {
                "boundary_row_count": len(rows),
                "boundary_complete_row_count": boundary_complete_count,
                "allowed_use_complete_row_count": allowed_complete_count,
                "blocked_use_complete_row_count": blocked_complete_count,
                "row_authorization_count": row_authorization_count,
            },
            "section_boundary_text_or_authorization_invalid",
        ),
        check_row(
            "claim_safe_surface_alignment_clean",
            surface_consistent_count == len(rows) and len(rows) == 8,
            {
                "claim_safe_surface_consistent_row_count": surface_consistent_count,
                "boundary_row_count": len(rows),
            },
            "claim_safe_surface_alignment_issue",
        ),
        check_row(
            "neutral_result_links_covered_by_section_boundaries",
            neutral_linked_count == len(rows)
            and section_backfill_count == len(rows)
            and len(unique_ledger_gap_ids) >= 1,
            {
                "neutral_result_linked_row_count": neutral_linked_count,
                "section_boundary_backfill_row_count": section_backfill_count,
                "neutral_ledger_prose_boundary_gap_unique_result_count": len(
                    unique_ledger_gap_ids
                ),
            },
            "neutral_result_links_not_section_boundary_covered",
        ),
        check_row(
            "release_targets_remain_blocked",
            release_linked_count == len(rows)
            and release_authorized_target_count == 0
            and safe_int(release_summary.get("release_authorized_count")) == 0,
            {
                "release_target_linked_row_count": release_linked_count,
                "release_authorized_target_count": release_authorized_target_count,
                "unique_release_target_count": len(release_target_ids),
            },
            "release_target_authorized_or_missing",
        ),
        check_row(
            "main_positive_boundary_remains_blocked",
            main_positive_boundary_blocked,
            {
                "main_results_boundary_status": rows_by_id.get(
                    "paper_main_results_blocked_evidence", {}
                ).get("boundary_status"),
                "main_results_packet_status": rows_by_id.get(
                    "paper_main_results_blocked_evidence", {}
                ).get("packet_status"),
            },
            "main_positive_claim_boundary_not_blocked",
        ),
        check_row(
            "venn_abers_boundary_is_negative_only",
            venn_negative_boundary_preserved,
            {
                "venn_boundary_status": rows_by_id.get(
                    "supplement_venn_abers_negative_evidence", {}
                ).get("boundary_status"),
                "venn_negative_status": venn_negative_summary.get("overall_status"),
                "venn_validated_claim_ready": venn_negative_summary.get(
                    "can_support_validated_venn_abers_regression"
                ),
            },
            "venn_abers_boundary_not_negative_only",
        ),
        check_row(
            "no_method_promotion_or_positive_claim_authorization",
            no_method_promotion and post_program_controlled,
            {
                "neutral_language_status": neutral_language_summary.get(
                    "overall_status"
                ),
                "unguarded_hit_count": neutral_language_summary.get(
                    "unguarded_hit_count"
                ),
                "post_program_status": post_program.get("status"),
                "working_repository_citation_status": (
                    post_program.get("sterile_publication_repository_plan") or {}
                ).get("working_repository_citation_status"),
            },
            "method_promotion_or_positive_claim_authorization_detected",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    overall_status = (
        "section_claim_boundary_audit_pass_no_final_claims"
        if not failed_checks
        else "section_claim_boundary_audit_blocked"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "phase_state": (
                "neutral_pre_prose_section_claim_boundary_alignment_active_"
                "final_outputs_blocked"
            ),
            "boundary_row_count": len(rows),
            "boundary_complete_row_count": boundary_complete_count,
            "allowed_use_complete_row_count": allowed_complete_count,
            "blocked_use_complete_row_count": blocked_complete_count,
            "claim_safe_surface_consistent_row_count": surface_consistent_count,
            "neutral_result_linked_row_count": neutral_linked_count,
            "release_target_linked_row_count": release_linked_count,
            "release_authorized_target_count": release_authorized_target_count,
            "unique_release_target_count": len(release_target_ids),
            "neutral_ledger_prose_boundary_gap_unique_result_count": len(
                unique_ledger_gap_ids
            ),
            "section_boundary_backfill_row_count": section_backfill_count,
            "target_document_counts": dict(sorted(target_counts.items())),
            "boundary_status_counts": dict(sorted(status_counts.items())),
            "main_results_positive_boundary_blocked": main_positive_boundary_blocked,
            "venn_abers_negative_boundary_preserved": (
                venn_negative_boundary_preserved
            ),
            "section_packet_clean": section_packet_clean,
            "upstream_boundaries_clean": upstream_boundaries_clean,
            "post_program_controlled": post_program_controlled,
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
            "scientific_no_method_promotion_guard_active": True,
            "neutral_language_unguarded_hit_count": neutral_language_summary.get(
                "unguarded_hit_count"
            ),
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
        },
        "claim_boundaries": [
            "This audit checks section-level claim-boundary alignment; it is not manuscript prose.",
            "Section packet allowed/blocked-use text is the controlling prose boundary when linked neutral-ledger rows do not carry prose fields.",
            "The main-results section remains blocked for positive method or model claims.",
            "The Venn-Abers section remains negative/failure-mode evidence only and does not validate Venn-Abers regression.",
            "No final prose, figure/table retention, release, sterile repository, KG citation, method recommendation, or positive claim promotion is authorized here.",
        ],
        "sources": {key: rel(root / path, root) for key, path in SOURCE_PATHS.items()},
        "neutral_ledger_prose_boundary_gap_result_ids": unique_ledger_gap_ids,
        "boundary_rows": rows,
        "checks": checks,
        "failed_checks": failed_checks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Section Claim Boundary Audit",
        "",
        f"- Status: `{summary_payload['overall_status']}`",
        f"- Phase: `{summary_payload['phase_state']}`",
        f"- Boundary rows: {summary_payload['boundary_row_count']}",
        f"- Complete boundary rows: {summary_payload['boundary_complete_row_count']}",
        f"- Claim-safe surface consistent rows: {summary_payload['claim_safe_surface_consistent_row_count']}",
        f"- Neutral-result linked rows: {summary_payload['neutral_result_linked_row_count']}",
        f"- Section boundary backfill rows: {summary_payload['section_boundary_backfill_row_count']}",
        f"- Release target linked rows: {summary_payload['release_target_linked_row_count']}",
        f"- Release-authorized targets: {summary_payload['release_authorized_target_count']}",
        f"- Main positive boundary blocked: `{summary_payload['main_results_positive_boundary_blocked']}`",
        f"- Venn-Abers negative boundary preserved: `{summary_payload['venn_abers_negative_boundary_preserved']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(["", "## Boundary Rows", ""])
    for row in payload["boundary_rows"]:
        lines.extend(
            [
                f"### {row['packet_id']}",
                "",
                f"- Target document: `{row['target_document']}`",
                f"- Boundary status: `{row['boundary_status']}`",
                f"- Reporting role: `{row['scientific_reporting_role']}`",
                f"- Claim-safe surface: `{row['claim_safe_surface_id']}`",
                f"- Neutral result ids: `{', '.join(row['neutral_result_ids'])}`",
                f"- Release targets: `{', '.join(row['release_target_deliverable_ids'])}`",
                f"- Section boundary backfills ledger gap: `{row['section_boundary_backfills_ledger_gap']}`",
                f"- Allowed use: {row['allowed_use']}",
                f"- Blocked use: {row['blocked_use']}",
                "",
            ]
        )
    lines.extend(["", "## Checks", ""])
    for check in payload["checks"]:
        lines.append(f"- `{check['check_id']}`: `{check['status']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root)
    out = root / args.out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(json.dumps(payload["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
