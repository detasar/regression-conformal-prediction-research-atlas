"""Backfill full-method coverage metadata for existing endpoint v2 audits.

Some endpoint audits were generated after the v2 endpoint schema existed but
before `method_filter.full_method_coverage` and completed-method count fields
were mandatory. This script only updates those already-v2 audits when the
canonical ledger proves that all completed rows were reconstructed and there
are no reconstruction or missing-artifact failures.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.audit_regression_endpoints import (
    canonical_rows,
    load_jsonl,
    render_markdown,
)


SCHEMA = "cpfi_endpoint_method_coverage_backfill_v1"
DEFAULT_BACKLOG = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "integrity_remediation_backlog.json"
)
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "endpoint_method_coverage_backfill.json"
)
ISSUE_TYPE = "endpoint_audit_not_full_method_coverage"


CLAIM_BOUNDARIES = [
    "This backfill updates endpoint-audit metadata only; it does not rerun models or reconstruct intervals.",
    "Rows are eligible only when the existing endpoint audit is already cpfi_regression_endpoint_audit_v2.",
    "Rows are eligible only when canonical ledger completed-row counts match reconstructed runs and no endpoint failures are recorded.",
    "Full method coverage here means all completed ledger rows, not skipped_method rows controlled by runtime caps.",
    "This is endpoint engineering evidence, not bounded-support validity, fairness, causal, legal, production, or final-model-selection evidence.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--backlog", default=DEFAULT_BACKLOG)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        return str(resolved_path.relative_to(resolved_root))
    except ValueError:
        return str(resolved_path)


def resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def endpoint_actions(backlog: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in backlog.get("rows", []) or []
        if row.get("issue_type") == ISSUE_TYPE and row.get("status", "open") == "open"
    ]


def ledger_completed_counts(path: Path) -> tuple[int, dict[str, int]]:
    rows = canonical_rows(load_jsonl(path))
    completed = [row for row in rows if row.get("status") == "completed"]
    counts = Counter(str(row.get("cp_method", "missing")) for row in completed)
    return len(completed), dict(sorted((key, int(value)) for key, value in counts.items()))


def _count_value(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if value is None:
        return 0
    return int(value)


def endpoint_has_failures(payload: dict[str, Any]) -> bool:
    return any(
        _count_value(payload.get(key)) > 0
        for key in ["missing_artifacts", "reconstruction_failures", "failure_count_total"]
    )


def dataset_ids_from_summary(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        payload = read_json(path)
    except json.JSONDecodeError:
        return []
    dataset_ids: set[str] = set()
    for row in payload.get("rows", []) or []:
        dataset_id = row.get("dataset_id")
        if dataset_id:
            dataset_ids.add(str(dataset_id))
    metadata_counts = (payload.get("metadata") or {}).get("dataset_counts") or {}
    dataset_ids.update(str(key) for key in metadata_counts)
    return sorted(dataset_ids)


def existing_backfilled_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for endpoint_path in sorted((root / "experiments/regression/reports").glob("*/endpoint_audit.json")):
        payload = read_json(endpoint_path)
        method_filter = payload.get("method_filter") or {}
        if not (
            payload.get("audit_schema") == "cpfi_regression_endpoint_audit_v2"
            and isinstance(method_filter, dict)
            and method_filter.get("metadata_backfilled_from_ledger") is True
        ):
            continue
        report_name = endpoint_path.parent.name
        summary_path = endpoint_path.parent / "pilot_summary.json"
        rows.append(
            {
                "action_id": None,
                "report_id": f"report:{report_name}",
                "report_name": report_name,
                "status": "existing_backfilled_endpoint_metadata",
                "config_path": payload.get("config"),
                "dataset_ids": dataset_ids_from_summary(summary_path),
                "endpoint_audit_path": rel(endpoint_path, root),
                "ledger_path": payload.get("ledger"),
                "completed_ledger_rows": int(payload.get("completed_ledger_rows") or 0),
                "reconstructed_runs": int(payload.get("reconstructed_runs") or 0),
                "method_counts": payload.get("configured_completed_method_counts") or {},
            }
        )
    return rows


def backfill_payload(
    *,
    root: Path,
    action: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    sidecar_values = action.get("source_sidecar_paths") or []
    endpoint_path = resolve_path(root, str(sidecar_values[0])) if sidecar_values else None
    if endpoint_path is None or not endpoint_path.exists():
        return {
            "action_id": action.get("action_id"),
            "report_name": action.get("report_name"),
            "status": "skipped_missing_endpoint_audit",
            "config_path": action.get("config_path"),
            "dataset_ids": action.get("dataset_ids") or [],
            "endpoint_audit_path": None if endpoint_path is None else rel(endpoint_path, root),
        }

    payload = read_json(endpoint_path)
    if payload.get("audit_schema") != "cpfi_regression_endpoint_audit_v2":
        return {
            "action_id": action.get("action_id"),
            "report_name": action.get("report_name"),
            "status": "skipped_non_v2_endpoint_audit",
            "config_path": action.get("config_path"),
            "dataset_ids": action.get("dataset_ids") or [],
            "endpoint_audit_path": rel(endpoint_path, root),
            "audit_schema": payload.get("audit_schema"),
        }

    if endpoint_has_failures(payload):
        return {
            "action_id": action.get("action_id"),
            "report_name": action.get("report_name"),
            "status": "skipped_endpoint_failures_present",
            "config_path": action.get("config_path"),
            "dataset_ids": action.get("dataset_ids") or [],
            "endpoint_audit_path": rel(endpoint_path, root),
        }

    ledger_path = resolve_path(root, str(payload.get("ledger") or action.get("pilot_summary_path")))
    if ledger_path is not None and ledger_path.name == "pilot_summary.json":
        summary = read_json(ledger_path)
        ledger_path = resolve_path(root, str(summary.get("ledger")))
    if ledger_path is None or not ledger_path.exists():
        return {
            "action_id": action.get("action_id"),
            "report_name": action.get("report_name"),
            "status": "skipped_missing_ledger",
            "config_path": action.get("config_path"),
            "dataset_ids": action.get("dataset_ids") or [],
            "endpoint_audit_path": rel(endpoint_path, root),
        }

    completed_rows, method_counts = ledger_completed_counts(ledger_path)
    reconstructed = int(payload.get("reconstructed_runs") or 0)
    existing_completed = int(payload.get("completed_ledger_rows") or reconstructed)
    if reconstructed != completed_rows or existing_completed != completed_rows:
        return {
            "action_id": action.get("action_id"),
            "report_name": action.get("report_name"),
            "status": "skipped_reconstruction_count_mismatch",
            "config_path": action.get("config_path"),
            "dataset_ids": action.get("dataset_ids") or [],
            "endpoint_audit_path": rel(endpoint_path, root),
            "ledger_completed_rows": completed_rows,
            "existing_completed_ledger_rows": existing_completed,
            "reconstructed_runs": reconstructed,
        }

    existing_counts = payload.get("configured_completed_method_counts") or method_counts
    if {str(k): int(v) for k, v in existing_counts.items()} != method_counts:
        return {
            "action_id": action.get("action_id"),
            "report_name": action.get("report_name"),
            "status": "skipped_method_count_mismatch",
            "config_path": action.get("config_path"),
            "dataset_ids": action.get("dataset_ids") or [],
            "endpoint_audit_path": rel(endpoint_path, root),
            "ledger_method_counts": method_counts,
            "existing_method_counts": existing_counts,
        }

    updated = dict(payload)
    updated["method_filter"] = {
        "include_methods": [],
        "exclude_methods": [],
        "max_completed": None,
        "full_method_coverage": True,
        "metadata_backfilled_from_ledger": True,
    }
    updated["total_completed_ledger_rows"] = completed_rows
    updated["filtered_completed_ledger_rows"] = completed_rows
    updated["completed_ledger_rows"] = completed_rows
    updated["available_completed_method_counts"] = method_counts
    updated["filtered_completed_method_counts"] = method_counts
    updated["configured_completed_method_counts"] = method_counts
    updated["omitted_completed_method_counts"] = {}

    if not dry_run:
        atomic_write_json(endpoint_path, updated)
        atomic_write_text(
            endpoint_path.with_suffix(".md"),
            render_markdown(str(action.get("report_name")), updated),
        )

    return {
        "action_id": action.get("action_id"),
        "report_id": action.get("report_id"),
        "report_name": action.get("report_name"),
        "status": "planned" if dry_run else "updated",
        "config_path": action.get("config_path"),
        "dataset_ids": action.get("dataset_ids") or [],
        "endpoint_audit_path": rel(endpoint_path, root),
        "ledger_path": rel(ledger_path, root),
        "completed_ledger_rows": completed_rows,
        "reconstructed_runs": reconstructed,
        "method_counts": method_counts,
    }


def build_summary(*, root: Path, backlog_path: Path, dry_run: bool) -> dict[str, Any]:
    backlog = read_json(backlog_path)
    actions = endpoint_actions(backlog)
    rows = [
        backfill_payload(root=root, action=action, dry_run=dry_run)
        for action in actions
    ]
    if not actions:
        rows = existing_backfilled_rows(root)
    status_counts = Counter(str(row.get("status")) for row in rows)
    updated_rows = [
        row
        for row in rows
        if row.get("status")
        in {"updated", "planned", "existing_backfilled_endpoint_metadata"}
    ]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "backlog_path": rel(backlog_path, root),
        "issue_type": ISSUE_TYPE,
        "dry_run": bool(dry_run),
        "action_count": len(actions),
        "updated_count": len(updated_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "total_completed_ledger_rows": sum(
            int(row.get("completed_ledger_rows") or 0) for row in updated_rows
        ),
        "claim_boundaries": CLAIM_BOUNDARIES,
        "rows": rows,
    }


def render_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Endpoint Method Coverage Backfill",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source backlog: `{payload['backlog_path']}`",
        f"- Dry run: {payload['dry_run']}",
        f"- Action count: {payload['action_count']}",
        f"- Updated count: {payload['updated_count']}",
        f"- Status counts: `{payload['status_counts']}`",
        f"- Total completed ledger rows represented: {payload['total_completed_ledger_rows']}",
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
            "| Report | Status | Completed rows | Endpoint audit |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row.get('report_name')}` | "
            f"`{row.get('status')}` | "
            f"{int(row.get('completed_ledger_rows') or 0)} | "
            f"`{row.get('endpoint_audit_path')}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    backlog_path = resolve_path(root, args.backlog) or Path(args.backlog)
    out_path = resolve_path(root, args.out) or Path(args.out)
    payload = build_summary(root=root, backlog_path=backlog_path, dry_run=bool(args.dry_run))
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_summary_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out_path, root),
                "action_count": payload["action_count"],
                "updated_count": payload["updated_count"],
                "status_counts": payload["status_counts"],
                "total_completed_ledger_rows": payload["total_completed_ledger_rows"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
