"""Audit manuscript quarantine coverage for duplicate/content caveats.

This audit does not remove duplicate caveats. It verifies that duplicate-
sensitive evidence is either not a manuscript candidate or is carried only on
blocked/caveated manuscript surfaces, so it cannot support final claims.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_duplicate_content_quarantine_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "duplicate_content_quarantine_audit.json"
DUPLICATE_CLOSURE = REPORT_DIR / "duplicate_sensitivity_closure_audit.json"
BUNDLE_ELIGIBILITY = Path("experiments/regression/manuscript/bundle_eligibility_matrix.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def duplicate_actions(closure: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for source_key in ("covered_actions", "tracked_caveat_actions"):
        for row in closure.get(source_key, []) or []:
            if not isinstance(row, dict):
                continue
            issue_type = str(row.get("issue_type") or "")
            if "duplicate" not in issue_type and "model_visible" not in issue_type:
                continue
            rows.append({**row, "source_action_table": source_key})
    rows.sort(key=lambda row: (str(row.get("report_name")), str(row.get("issue_type"))))
    return rows


def eligibility_by_bundle(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("bundle_id")): row
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and row.get("bundle_id")
    }


def surface(row: dict[str, Any], surface_id: str) -> dict[str, Any]:
    value = (row.get("surface_eligibility") or {}).get(surface_id) or {}
    return value if isinstance(value, dict) else {}


def linked_claims_are_nonfinal(row: dict[str, Any]) -> bool:
    statuses = row.get("linked_claim_statuses") or {}
    if not isinstance(statuses, dict):
        return False
    final_markers = ("final", "main_result_eligible", "publication_ready")
    for status in statuses.values():
        text = str(status).lower()
        if any(marker in text for marker in final_markers):
            if "blocked" not in text and "no_final" not in text:
                return False
    return True


def quarantine_row(action: dict[str, Any], bundle: dict[str, Any] | None) -> dict[str, Any]:
    if bundle is None:
        return {
            "action_id": action.get("action_id"),
            "report_id": action.get("report_id"),
            "report_name": action.get("report_name"),
            "issue_type": action.get("issue_type"),
            "action_status": action.get("status"),
            "source_action_table": action.get("source_action_table"),
            "manuscript_candidate": False,
            "quarantine_status": "not_manuscript_candidate",
            "main_results_eligible": False,
            "requires_caveat_label": False,
            "caveat_label_present": True,
            "linked_claims_nonfinal": True,
            "allowed_surface_ids": [],
            "blocked_surface_ids": ["main_results_table"],
            "quarantined": True,
        }
    main_surface = surface(bundle, "main_results_table")
    robustness_surface = surface(bundle, "robustness_results_table")
    requires_caveat = bool(bundle.get("requires_caveat_label"))
    caveat_surface = (
        str(robustness_surface.get("status") or "").endswith("with_caveats")
        or str(bundle.get("status") or "").lower().endswith("with_caveats")
        or bool(bundle.get("promotion_blockers"))
    )
    main_eligible = bool(main_surface.get("eligible"))
    linked_nonfinal = linked_claims_are_nonfinal(bundle)
    blocked_surfaces = list(bundle.get("blocked_surface_ids") or [])
    allowed_surfaces = list(bundle.get("eligible_surface_ids") or [])
    caveat_label_present = requires_caveat and caveat_surface
    quarantined = (
        not main_eligible
        and "main_results_table" in blocked_surfaces
        and caveat_label_present
        and linked_nonfinal
    )
    return {
        "action_id": action.get("action_id"),
        "report_id": action.get("report_id"),
        "report_name": action.get("report_name"),
        "issue_type": action.get("issue_type"),
        "action_status": action.get("status"),
        "source_action_table": action.get("source_action_table"),
        "manuscript_candidate": True,
        "bundle_id": bundle.get("bundle_id"),
        "bundle_status": bundle.get("status"),
        "paper_table_candidate": bundle.get("paper_table_candidate"),
        "claim_scope": bundle.get("claim_scope"),
        "linked_claim_statuses": bundle.get("linked_claim_statuses"),
        "quarantine_status": "candidate_caveated_and_main_blocked" if quarantined else "candidate_not_quarantined",
        "main_results_eligible": main_eligible,
        "requires_caveat_label": requires_caveat,
        "caveat_label_present": caveat_label_present,
        "linked_claims_nonfinal": linked_nonfinal,
        "allowed_surface_ids": allowed_surfaces,
        "blocked_surface_ids": blocked_surfaces,
        "main_results_surface": main_surface,
        "robustness_surface": robustness_surface,
        "quarantined": quarantined,
    }


def build_payload(root: Path) -> dict[str, Any]:
    closure_path = root / DUPLICATE_CLOSURE
    eligibility_path = root / BUNDLE_ELIGIBILITY
    closure = read_json(closure_path)
    eligibility = read_json(eligibility_path)
    bundle_by_id = eligibility_by_bundle(eligibility)
    actions = duplicate_actions(closure)
    rows = [
        quarantine_row(action, bundle_by_id.get(str(action.get("report_name"))))
        for action in actions
    ]
    status_counts = Counter(str(row.get("quarantine_status")) for row in rows)
    action_status_counts = Counter(str(row.get("action_status")) for row in rows)
    issue_counts = Counter(str(row.get("issue_type")) for row in rows)
    manuscript_rows = [row for row in rows if row.get("manuscript_candidate")]
    unquarantined = [row for row in rows if not row.get("quarantined")]
    main_eligible = [row for row in rows if row.get("main_results_eligible")]
    caveat_missing = [
        row for row in manuscript_rows if not row.get("caveat_label_present")
    ]
    nonfinal_missing = [
        row for row in manuscript_rows if not row.get("linked_claims_nonfinal")
    ]
    duplicate_summary = closure.get("summary") or {}
    hard_failed = int(duplicate_summary.get("hard_failed_check_count") or 0)
    open_actions = int(duplicate_summary.get("open_action_count") or 0)
    failed_check_count = (
        len(unquarantined)
        + len(main_eligible)
        + len(caveat_missing)
        + len(nonfinal_missing)
        + hard_failed
        + open_actions
    )
    overall_status = (
        "duplicate_content_quarantine_fail"
        if failed_check_count
        else "duplicate_content_quarantine_pass"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "duplicate_sensitivity_closure": rel(closure_path, root),
            "bundle_eligibility_matrix": rel(eligibility_path, root),
        },
        "summary": {
            "overall_status": overall_status,
            "failed_check_count": failed_check_count,
            "duplicate_action_count": len(rows),
            "manuscript_candidate_action_count": len(manuscript_rows),
            "non_manuscript_action_count": len(rows) - len(manuscript_rows),
            "quarantined_action_count": sum(1 for row in rows if row.get("quarantined")),
            "unquarantined_action_count": len(unquarantined),
            "main_results_eligible_action_count": len(main_eligible),
            "caveat_label_missing_action_count": len(caveat_missing),
            "linked_final_claim_action_count": len(nonfinal_missing),
            "duplicate_closure_open_action_count": open_actions,
            "duplicate_closure_hard_failed_check_count": hard_failed,
            "duplicate_closure_duplicate_caveat_count": duplicate_summary.get(
                "duplicate_caveat_count"
            ),
            "quarantine_status_counts": dict(sorted(status_counts.items())),
            "action_status_counts": dict(sorted(action_status_counts.items())),
            "issue_type_counts": dict(sorted(issue_counts.items())),
        },
        "claim_boundaries": [
            "Duplicate-sensitive evidence remains caveated robustness or diagnostic evidence.",
            "A passing quarantine audit does not prove split independence.",
            "A passing quarantine audit does not select a final method, model, dataset, fairness claim, bounded-support claim, or Venn-Abers validation claim.",
        ],
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Duplicate Content Quarantine Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Duplicate actions: {summary['duplicate_action_count']}",
        f"- Manuscript candidate actions: {summary['manuscript_candidate_action_count']}",
        f"- Non-manuscript actions: {summary['non_manuscript_action_count']}",
        f"- Quarantined actions: {summary['quarantined_action_count']}",
        f"- Unquarantined actions: {summary['unquarantined_action_count']}",
        f"- Main-results eligible actions: {summary['main_results_eligible_action_count']}",
        f"- Caveat-label missing actions: {summary['caveat_label_missing_action_count']}",
        f"- Linked final-claim actions: {summary['linked_final_claim_action_count']}",
        f"- Quarantine status counts: `{summary['quarantine_status_counts']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Report | Issue | Action status | Manuscript candidate | Quarantine | Main eligible | Caveat label |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row.get('report_name')}` | "
            f"`{row.get('issue_type')}` | "
            f"`{row.get('action_status')}` | "
            f"`{row.get('manuscript_candidate')}` | "
            f"`{row.get('quarantine_status')}` | "
            f"`{row.get('main_results_eligible')}` | "
            f"`{row.get('caveat_label_present')}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
