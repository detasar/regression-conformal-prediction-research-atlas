"""Backfill provenance labels onto existing feature-leakage sidecars.

This script is intentionally label-only: it does not rerun models, rescan
violations, or rewrite the recorded leakage decision. It fills legacy
`metadata_selection` and `backfill_policy_inference` fields when current
config, ledger, and prediction metadata paths provide enough evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.backfill_feature_leakage_sidecars import (
    cache_root_for_action,
    infer_policy_checks,
    metadata_paths_for_action,
    rel,
    resolve_repo_path,
)


SCHEMA = "cpfi_feature_leakage_provenance_label_backfill_v1"
DEFAULT_TRIAGE = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "feature_leakage_metadata_completeness_triage.json"
)
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "feature_leakage_provenance_label_backfill.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--triage", default=DEFAULT_TRIAGE, help="Input triage JSON.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output summary JSON.")
    parser.add_argument(
        "--report-name",
        action="append",
        default=[],
        help="Optional report_name filter. Repeat to backfill selected reports.",
    )
    parser.add_argument(
        "--max-exact-feature-set-size",
        type=int,
        default=300,
        help="Exact feature-set inference threshold passed to the policy checker.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute labels even when the sidecar already has them.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan without writing.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_lines(values: list[str]) -> str:
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def action_from_triage_row(row: dict[str, Any]) -> dict[str, Any]:
    report_name = row.get("report_name")
    return {
        "action_id": (
            f"{report_name}:caveat:feature_leakage_legacy_provenance_label_gap"
        ),
        "report_id": row.get("report_id") or f"report:{report_name}",
        "report_name": report_name,
        "config_path": row.get("config_path"),
        "pilot_summary_path": row.get("pilot_summary_path"),
    }


def rows_needing_labels(payload: dict[str, Any], report_names: set[str]) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("rows", []) or []:
        report_name = str(row.get("report_name") or "")
        if report_names and report_name not in report_names:
            continue
        if row.get("metadata_selection_status") == "legacy_selection_label_not_recorded":
            rows.append(row)
            continue
        if row.get("policy_inference_status") == "legacy_policy_inference_label_not_recorded":
            rows.append(row)
            continue
    return rows


def label_status(sidecar: dict[str, Any], *, force: bool) -> str:
    has_selection = bool(sidecar.get("metadata_selection"))
    has_policy = bool(sidecar.get("backfill_policy_inference"))
    if has_selection and has_policy and not force:
        return "skipped_labels_already_present"
    if has_selection and not has_policy:
        return "needs_policy_inference_label"
    if has_policy and not has_selection:
        return "needs_metadata_selection_label"
    return "needs_selection_and_policy_labels"


def update_sidecar(
    *,
    root: Path,
    triage_row: dict[str, Any],
    force: bool,
    dry_run: bool,
    max_exact_feature_set_size: int,
) -> dict[str, Any]:
    sidecar_path = resolve_repo_path(root, triage_row.get("feature_leakage_audit_path"))
    action = action_from_triage_row(triage_row)
    cache_root = cache_root_for_action(root, action)
    metadata_paths, metadata_selection = metadata_paths_for_action(
        root=root,
        action=action,
        cache_root=cache_root,
    )
    base = {
        "report_id": action.get("report_id"),
        "report_name": action.get("report_name"),
        "config_path": action.get("config_path"),
        "pilot_summary_path": action.get("pilot_summary_path"),
        "sidecar_json": None if sidecar_path is None else rel(sidecar_path, root),
        "prediction_cache_root": None if cache_root is None else rel(cache_root, root),
        "metadata_selection": metadata_selection,
        "metadata_file_count": len(metadata_paths),
        "dry_run": bool(dry_run),
    }
    if sidecar_path is None or not sidecar_path.exists():
        return {**base, "status": "skipped_missing_sidecar"}
    if not metadata_paths:
        return {**base, "status": "skipped_no_metadata_paths"}

    sidecar = read_json(sidecar_path)
    current_status = label_status(sidecar, force=force)
    if current_status == "skipped_labels_already_present":
        return {**base, "status": current_status}

    checks = infer_policy_checks(
        metadata_paths,
        max_exact_feature_set_size=max_exact_feature_set_size,
    )
    relative_paths = [rel(path, root) for path in metadata_paths]
    backfill_record = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "current_config_ledger_prediction_metadata",
        "source_triage_report": DEFAULT_TRIAGE,
        "source_triage_report_id": "report:feature_leakage_metadata_completeness_triage",
        "source_cross_run_report_id": action.get("report_id"),
        "action_id": action.get("action_id"),
        "metadata_selection": metadata_selection,
        "metadata_path_count": len(relative_paths),
        "metadata_path_sha256": sha256_lines(relative_paths),
        "claim_boundary": (
            "Label-only provenance backfill; existing feature-leakage "
            "violation decisions and performance evidence are unchanged."
        ),
    }

    if not dry_run:
        updated = dict(sidecar)
        updated.setdefault("source_cross_run_report_id", action.get("report_id"))
        if action.get("config_path"):
            updated.setdefault("config_path", action.get("config_path"))
        if force or not updated.get("metadata_selection"):
            updated["metadata_selection"] = metadata_selection
        if force or not updated.get("backfill_policy_inference"):
            updated["backfill_policy_inference"] = checks["inference"]
        updated["provenance_label_backfill"] = backfill_record
        atomic_write_json(sidecar_path, updated)

    return {
        **base,
        "status": "planned" if dry_run else "updated",
        "previous_label_status": current_status,
        "metadata_path_sha256": backfill_record["metadata_path_sha256"],
        "complete_drop_metadata": checks["inference"]["complete_drop_metadata"],
        "complete_policy_metadata": checks["inference"]["complete_policy_metadata"],
        "exact_feature_set_enforced": checks["inference"]["exact_feature_set_enforced"],
        "exact_drop_set_enforced": checks["inference"]["exact_drop_set_enforced"],
        "violations_count": int(sidecar.get("violations_count") or 0),
    }


def build_payload(
    *,
    root: Path,
    triage_path: Path,
    report_names: set[str],
    force: bool,
    dry_run: bool,
    max_exact_feature_set_size: int,
) -> dict[str, Any]:
    triage = read_json(triage_path)
    source_rows = rows_needing_labels(triage, report_names)
    rows = [
        update_sidecar(
            root=root,
            triage_row=row,
            force=force,
            dry_run=dry_run,
            max_exact_feature_set_size=max_exact_feature_set_size,
        )
        for row in source_rows
    ]
    status_counts = Counter(str(row.get("status")) for row in rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_triage_path": rel(triage_path, root),
        "force": bool(force),
        "dry_run": bool(dry_run),
        "report_name_filter": sorted(report_names),
        "source_row_count": len(source_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "updated_sidecar_count": sum(1 for row in rows if row.get("status") == "updated"),
        "planned_sidecar_count": sum(1 for row in rows if row.get("status") == "planned"),
        "total_metadata_files_scanned": sum(
            int(row.get("metadata_file_count") or 0) for row in rows
        ),
        "total_violations": sum(int(row.get("violations_count") or 0) for row in rows),
        "claim_boundaries": [
            "This artifact records provenance-label backfill for existing feature-leakage sidecars.",
            "It does not rerun models, change prediction bundles, or change recorded leakage violations.",
            "A metadata-selection or policy-inference label is not a final fairness, production, causal, bounded-support, or model-selection claim.",
        ],
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Feature Leakage Provenance Label Backfill",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source triage: `{payload['source_triage_path']}`",
        f"- Source rows: {payload['source_row_count']}",
        f"- Updated sidecars: {payload['updated_sidecar_count']}",
        f"- Planned sidecars: {payload['planned_sidecar_count']}",
        f"- Status counts: `{payload['status_counts']}`",
        f"- Metadata files scanned: {payload['total_metadata_files_scanned']}",
        f"- Violations represented: {payload['total_violations']}",
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
            "| Report | Status | Selection | Metadata | Complete policy | Sidecar |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row.get('report_name')}` | "
            f"`{row.get('status')}` | "
            f"`{row.get('metadata_selection')}` | "
            f"{row.get('metadata_file_count')} | "
            f"`{row.get('complete_policy_metadata')}` | "
            f"`{row.get('sidecar_json')}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    triage_path = resolve_repo_path(root, args.triage) or Path(args.triage)
    out_path = resolve_repo_path(root, args.out) or Path(args.out)
    payload = build_payload(
        root=root,
        triage_path=triage_path,
        report_names={str(value) for value in args.report_name},
        force=args.force,
        dry_run=args.dry_run,
        max_exact_feature_set_size=args.max_exact_feature_set_size,
    )
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out_path, root),
                "source_row_count": payload["source_row_count"],
                "updated_sidecar_count": payload["updated_sidecar_count"],
                "planned_sidecar_count": payload["planned_sidecar_count"],
                "status_counts": payload["status_counts"],
                "total_metadata_files_scanned": payload[
                    "total_metadata_files_scanned"
                ],
                "total_violations": payload["total_violations"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
