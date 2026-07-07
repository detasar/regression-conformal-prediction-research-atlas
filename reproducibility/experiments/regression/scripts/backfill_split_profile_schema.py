"""Backfill legacy regression split-profile sidecars to schema v2.

This script consumes the integrity remediation backlog and regenerates only
rows carrying the legacy split-profile schema caveat. It uses the canonical
split audit builder rather than translating legacy sidecars in place.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts import audit_regression_splits as split_audit


SCHEMA = "cpfi_split_profile_schema_backfill_v1"
ISSUE_TYPE = "legacy_split_profile_schema_partial_integrity"
DEFAULT_BACKLOG = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "integrity_remediation_backlog.json"
)
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "split_profile_schema_backfill.json"
)

CLAIM_BOUNDARIES = [
    "This backfill regenerates split-profile sidecars only; it does not rerun models.",
    "Schema v2 split profiles check row-id and configured split-group disjointness, plus row-signature caveats.",
    "Duplicate row-signature overlaps remain interpretation caveats, not row-id leakage by themselves.",
    "This artifact is methodology provenance, not performance, fairness, causal, legal, production, or final-model-selection evidence.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--backlog", default=DEFAULT_BACKLOG)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--report-name", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if the current sidecar is already schema v2.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def rel(path: Path, root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        return str(resolved_path.relative_to(resolved_root))
    except ValueError:
        return str(resolved_path)


def resolve(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def sidecar_schema(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    try:
        payload = read_json(path)
    except json.JSONDecodeError:
        return "<malformed>"
    return payload.get("schema") or payload.get("artifact_schema")


def seed_profile_count(payload: dict[str, Any]) -> int:
    profiles = payload.get("profiles") or []
    if isinstance(profiles, list) and profiles:
        return sum(len(profile.get("seeds", []) or []) for profile in profiles if isinstance(profile, dict))
    return len(payload.get("seeds", []) or [])


def backlog_actions(backlog: dict[str, Any], report_names: set[str]) -> list[dict[str, Any]]:
    rows = []
    for row in backlog.get("rows", []) or []:
        if row.get("issue_type") != ISSUE_TYPE or row.get("status") != "open":
            continue
        if report_names and row.get("report_name") not in report_names:
            continue
        rows.append(row)
    return rows


def build_row(root: Path, action: dict[str, Any], *, dry_run: bool, force: bool) -> dict[str, Any]:
    report_name = str(action.get("report_name"))
    config_path = resolve(root, action.get("config_path"))
    split_profile_path = resolve(
        root,
        ((action.get("evidence") or {}).get("split_profile") or {}).get("path")
        or f"experiments/regression/reports/{report_name}/split_profile.json",
    )
    report_dir = split_profile_path.parent if split_profile_path else root / "experiments/regression/reports" / report_name
    row: dict[str, Any] = {
        "action_id": action.get("action_id"),
        "report_name": report_name,
        "config_path": None if config_path is None else rel(config_path, root),
        "split_profile_path": None if split_profile_path is None else rel(split_profile_path, root),
        "old_schema": sidecar_schema(split_profile_path),
        "new_schema": None,
        "dataset_ids": action.get("dataset_ids") or [],
        "seed_profile_count": None,
        "status": None,
        "error": None,
    }
    if config_path is None or not config_path.exists():
        row.update({"status": "skipped_missing_config", "error": "config path missing"})
        return row
    if split_profile_path is None or not split_profile_path.exists():
        row.update({"status": "skipped_missing_split_profile", "error": "split profile missing"})
        return row
    if row["old_schema"] == "cpfi_regression_split_profile_v2" and not force:
        row.update({"status": "skipped_already_v2"})
        return row

    try:
        config = read_yaml(config_path)
        payload = split_audit.build_payload(config_path, config)
    except Exception as exc:  # pragma: no cover - exercised through integration runs.
        row.update({"status": "failed_build", "error": f"{type(exc).__name__}: {exc}"})
        return row

    row["new_schema"] = payload.get("schema")
    row["seed_profile_count"] = seed_profile_count(payload)
    if payload.get("schema") != "cpfi_regression_split_profile_v2":
        row.update({"status": "failed_invalid_schema", "error": "generated payload is not schema v2"})
        return row
    expected_datasets = {str(value) for value in row["dataset_ids"]}
    actual_datasets = {str(value) for value in payload.get("dataset_ids", [])}
    if expected_datasets and expected_datasets != actual_datasets:
        row.update(
            {
                "status": "failed_dataset_mismatch",
                "error": f"expected {sorted(expected_datasets)} got {sorted(actual_datasets)}",
            }
        )
        return row
    if dry_run:
        row.update({"status": "planned"})
        return row

    atomic_write_json(report_dir / "split_profile.json", payload)
    atomic_write_text(report_dir / "split_profile.md", split_audit.render_markdown(payload))
    row.update({"status": "updated"})
    return row


def build_payload(
    *,
    root: Path,
    backlog_path: Path,
    out_path: Path,
    report_names: set[str],
    dry_run: bool,
    force: bool,
) -> dict[str, Any]:
    backlog = read_json(backlog_path)
    actions = backlog_actions(backlog, report_names)
    rows = [build_row(root, action, dry_run=dry_run, force=force) for action in actions]
    status_counts = Counter(str(row["status"]) for row in rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "force": force,
        "source_backlog_path": rel(backlog_path, root),
        "out_path": rel(out_path, root),
        "issue_type": ISSUE_TYPE,
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "action_count": len(actions),
            "updated_count": int(status_counts.get("updated", 0)),
            "planned_count": int(status_counts.get("planned", 0)),
            "failure_count": sum(
                count for status, count in status_counts.items() if status.startswith("failed")
            ),
            "status_counts": dict(sorted(status_counts.items())),
            "seed_profiles_generated": sum(int(row.get("seed_profile_count") or 0) for row in rows),
            "reports_updated": sorted(row["report_name"] for row in rows if row["status"] == "updated"),
        },
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Split Profile Schema Backfill",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source backlog: `{payload['source_backlog_path']}`",
        f"- Dry run: `{payload['dry_run']}`",
        f"- Force: `{payload['force']}`",
        f"- Actions: {summary['action_count']}",
        f"- Updated: {summary['updated_count']}",
        f"- Planned: {summary['planned_count']}",
        f"- Failures: {summary['failure_count']}",
        f"- Status counts: `{summary['status_counts']}`",
        f"- Seed profiles generated: {summary['seed_profiles_generated']}",
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
            "| Report | Status | Old schema | New schema | Seeds | Error |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row['report_name']}` | "
            f"`{row['status']}` | "
            f"`{row['old_schema']}` | "
            f"`{row['new_schema']}` | "
            f"{int(row.get('seed_profile_count') or 0)} | "
            f"{row.get('error') or 'none'} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def backfill_from_args(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve()
    backlog_path = resolve(root, args.backlog) or Path(args.backlog)
    out_path = resolve(root, args.out) or Path(args.out)
    payload = build_payload(
        root=root,
        backlog_path=backlog_path,
        out_path=out_path,
        report_names={str(value) for value in args.report_name},
        dry_run=bool(args.dry_run),
        force=bool(args.force),
    )
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    return payload


def main() -> None:
    payload = backfill_from_args(parse_args())
    print(json.dumps({"status": "ok", **payload["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
