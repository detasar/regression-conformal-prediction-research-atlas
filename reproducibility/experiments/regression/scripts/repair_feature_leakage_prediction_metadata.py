"""Repair legacy prediction metadata used by feature-leakage audits.

The repair is metadata-only. It annotates existing prediction metadata bundles
with feature-drop and preprocessing-name fields that the current runner writes
for new bundles, then refreshes the existing feature-leakage sidecar from the
repaired metadata. It does not rewrite predictions, intervals, metrics, or
ledger rows.
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
from experiments.regression.scripts.audit_prediction_feature_leakage import (
    render_markdown as render_feature_markdown,
    scan_metadata,
)
from experiments.regression.scripts.backfill_feature_leakage_sidecars import (
    cache_root_for_action,
    infer_policy_checks,
    metadata_paths_for_action,
    rel,
    resolve_repo_path,
)


SCHEMA = "cpfi_feature_leakage_prediction_metadata_repair_v1"
METADATA_REPAIR_SCHEMA = "cpfi_prediction_metadata_feature_leakage_repair_v1"
DEFAULT_TRIAGE = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "feature_leakage_metadata_completeness_triage.json"
)
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "feature_leakage_prediction_metadata_repair.json"
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
        help="Optional report_name filter. Repeat to repair selected reports.",
    )
    parser.add_argument(
        "--max-exact-feature-set-size",
        type=int,
        default=300,
        help="Exact feature-set inference threshold passed to policy inference.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refresh sidecars even when all metadata fields are already present.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan without writing.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_lines(values: list[str]) -> str:
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def _feature_reducer_method(metadata: dict[str, Any]) -> str:
    reducer = metadata.get("feature_reducer")
    if reducer is None:
        return "none"
    if isinstance(reducer, dict):
        return str(reducer.get("method", "none")).lower()
    return str(reducer).lower()


def rows_needing_repair(
    payload: dict[str, Any], report_names: set[str]
) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("rows", []) or []:
        report_name = str(row.get("report_name") or "")
        if report_names and report_name not in report_names:
            continue
        if row.get("policy_inference_status") == "incomplete_drop_or_policy_metadata":
            rows.append(row)
            continue
        if row.get("provenance_limitation_class") == "policy_inference_incomplete":
            rows.append(row)
    return rows


def action_from_triage_row(row: dict[str, Any]) -> dict[str, Any]:
    report_name = row.get("report_name")
    return {
        "action_id": f"{report_name}:caveat:feature_leakage_prediction_metadata_repair",
        "report_id": row.get("report_id") or f"report:{report_name}",
        "report_name": report_name,
        "config_path": row.get("config_path"),
        "pilot_summary_path": row.get("pilot_summary_path"),
    }


def unique_preserving(values: list[str]) -> list[str]:
    return [value for value in dict.fromkeys(values) if value]


def expected_drop_columns(sidecar: dict[str, Any], metadata: dict[str, Any]) -> list[str]:
    expected = [str(value) for value in sidecar.get("expected_drop_columns") or []]
    if expected:
        return unique_preserving(expected)
    target = metadata.get("target")
    group = metadata.get("group_col")
    split_group = metadata.get("split_group_col")
    if split_group is None and isinstance(metadata.get("splits"), dict):
        split_group = (metadata.get("splits") or {}).get("group_col")
    return unique_preserving(
        [str(value) for value in [target, group, split_group] if value is not None]
    )


def repaired_feature_drop_policy(
    *,
    sidecar: dict[str, Any],
    metadata: dict[str, Any],
    drop_columns: list[str],
) -> dict[str, Any] | None:
    target = sidecar.get("expected_target") or metadata.get("target")
    group = sidecar.get("expected_group_col") or metadata.get("group_col")
    if target is None or group is None:
        return None
    split_group = metadata.get("split_group_col")
    if split_group is None and isinstance(metadata.get("splits"), dict):
        split_group = (metadata.get("splits") or {}).get("group_col")
    policy = {
        "target": str(target),
        "primary_group_col": str(group),
        "split_group_col": None if split_group is None else str(split_group),
        "drop_split_group_col": split_group is not None,
    }
    base_drop = {str(target), str(group)}
    if split_group is not None:
        base_drop.add(str(split_group))
    extras = [value for value in drop_columns if value not in base_drop]
    if extras:
        policy["extra_feature_drop_columns"] = extras
    return policy


def safe_preprocessed_feature_names(metadata: dict[str, Any]) -> list[str] | None:
    features = metadata.get("feature_names")
    if not isinstance(features, list):
        return None
    feature_count = metadata.get("feature_count")
    if feature_count is not None and int(feature_count) != len(features):
        return None
    if _feature_reducer_method(metadata) not in {"", "none"}:
        return None
    return [str(value) for value in features]


def repair_metadata_payload(
    *,
    metadata: dict[str, Any],
    sidecar: dict[str, Any],
    repair_record: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    updated = dict(metadata)
    fields_added: list[str] = []
    fields_skipped: list[str] = []
    drop_columns = expected_drop_columns(sidecar, metadata)

    if updated.get("feature_drop_columns") is None:
        if drop_columns:
            updated["feature_drop_columns"] = drop_columns
            fields_added.append("feature_drop_columns")
        else:
            fields_skipped.append("feature_drop_columns")

    if updated.get("feature_drop_policy") is None:
        policy = repaired_feature_drop_policy(
            sidecar=sidecar,
            metadata=metadata,
            drop_columns=drop_columns,
        )
        if policy is not None:
            updated["feature_drop_policy"] = policy
            fields_added.append("feature_drop_policy")
        else:
            fields_skipped.append("feature_drop_policy")

    if updated.get("preprocessed_feature_names") is None:
        names = safe_preprocessed_feature_names(metadata)
        if names is not None:
            updated["preprocessed_feature_names"] = names
            updated["preprocessed_feature_count"] = len(names)
            fields_added.append("preprocessed_feature_names")
            if metadata.get("preprocessed_feature_count") is None:
                fields_added.append("preprocessed_feature_count")
        else:
            fields_skipped.append("preprocessed_feature_names")

    if fields_added:
        history = list(updated.get("metadata_repair_history") or [])
        history.append({**repair_record, "fields_added": fields_added})
        updated["metadata_repair_history"] = history
    return updated, fields_added, fields_skipped


def repair_metadata_files(
    *,
    root: Path,
    action: dict[str, Any],
    sidecar: dict[str, Any],
    metadata_paths: list[Path],
    dry_run: bool,
) -> dict[str, Any]:
    fields_added_counts: Counter[str] = Counter()
    fields_skipped_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    repaired_paths: list[str] = []
    sample_rows: list[dict[str, Any]] = []
    before_hashes: list[str] = []
    after_hashes: list[str] = []
    generated_at = datetime.now(timezone.utc).isoformat()

    for path in metadata_paths:
        before_sha = sha256_bytes(path)
        before_hashes.append(f"{rel(path, root)} {before_sha}")
        metadata = read_json(path)
        repair_record = {
            "schema": METADATA_REPAIR_SCHEMA,
            "generated_at_utc": generated_at,
            "source": "current_runner_feature_drop_policy_for_legacy_prediction_metadata",
            "source_triage_report": DEFAULT_TRIAGE,
            "source_triage_report_id": "report:feature_leakage_metadata_completeness_triage",
            "source_cross_run_report_id": action.get("report_id"),
            "action_id": action.get("action_id"),
            "pre_repair_sha256": before_sha,
            "claim_boundary": (
                "Metadata-only repair; prediction arrays, intervals, metrics, "
                "ledger rows, and model fits are unchanged."
            ),
        }
        updated, fields_added, fields_skipped = repair_metadata_payload(
            metadata=metadata,
            sidecar=sidecar,
            repair_record=repair_record,
        )
        fields_added_counts.update(fields_added)
        fields_skipped_counts.update(fields_skipped)
        if fields_added:
            status = "planned" if dry_run else "repaired"
            repaired_paths.append(rel(path, root))
            if not dry_run:
                atomic_write_json(path, updated)
        else:
            status = "skipped_already_complete"
        status_counts[status] += 1
        after_sha = before_sha if dry_run else sha256_bytes(path)
        after_hashes.append(f"{rel(path, root)} {after_sha}")
        if len(sample_rows) < 5:
            sample_rows.append(
                {
                    "path": rel(path, root),
                    "status": status,
                    "fields_added": fields_added,
                    "fields_skipped": fields_skipped,
                    "pre_repair_sha256": before_sha,
                    "post_repair_sha256": after_sha,
                }
            )

    return {
        "metadata_file_count": len(metadata_paths),
        "repaired_metadata_file_count": len(repaired_paths),
        "status_counts": dict(sorted(status_counts.items())),
        "fields_added_counts": dict(sorted(fields_added_counts.items())),
        "fields_skipped_counts": dict(sorted(fields_skipped_counts.items())),
        "metadata_path_sha256": sha256_lines([rel(path, root) for path in metadata_paths]),
        "pre_repair_content_sha256": sha256_lines(before_hashes),
        "post_repair_content_sha256": sha256_lines(after_hashes),
        "sample_rows": sample_rows,
    }


def refresh_sidecar(
    *,
    root: Path,
    sidecar_path: Path,
    cache_root: Path,
    metadata_paths: list[Path],
    existing_sidecar: dict[str, Any],
    action: dict[str, Any],
    metadata_selection: str,
    repair_summary: dict[str, Any],
    max_exact_feature_set_size: int,
    dry_run: bool,
) -> dict[str, Any]:
    checks = infer_policy_checks(
        metadata_paths,
        max_exact_feature_set_size=max_exact_feature_set_size,
    )
    payload = scan_metadata(
        cache_root,
        forbidden_features=set(
            str(value) for value in existing_sidecar.get("forbidden_features") or []
        ),
        required_features=set(
            str(value)
            for value in existing_sidecar.get("required_features")
            or existing_sidecar.get("expected_features")
            or []
        ),
        expected_features=set(
            str(value) for value in existing_sidecar.get("expected_features") or []
        ),
        expected_drop_columns=set(
            str(value) for value in existing_sidecar.get("expected_drop_columns") or []
        ),
        expected_target=existing_sidecar.get("expected_target"),
        expected_group_col=existing_sidecar.get("expected_group_col"),
        expected_target_transform=existing_sidecar.get("expected_target_transform"),
        config_path=action.get("config_path"),
        metadata_paths=metadata_paths,
    )
    payload["source_cross_run_report_id"] = action.get("report_id")
    payload["metadata_selection"] = metadata_selection
    payload["backfill_policy_inference"] = checks["inference"]
    if existing_sidecar.get("provenance_label_backfill"):
        payload["provenance_label_backfill"] = existing_sidecar[
            "provenance_label_backfill"
        ]
    payload["prediction_metadata_repair"] = {
        "schema": SCHEMA,
        "source_repair_report": DEFAULT_OUT,
        "source_repair_report_id": "report:feature_leakage_prediction_metadata_repair",
        "metadata_file_count": repair_summary["metadata_file_count"],
        "repaired_metadata_file_count": repair_summary["repaired_metadata_file_count"],
        "fields_added_counts": repair_summary["fields_added_counts"],
        "metadata_path_sha256": repair_summary["metadata_path_sha256"],
        "claim_boundary": (
            "Feature-leakage sidecar refreshed from repaired prediction metadata; "
            "prediction arrays, intervals, metrics, ledger rows, and model fits are unchanged."
        ),
    }
    if not dry_run:
        atomic_write_json(sidecar_path, payload)
        title = f"{action.get('report_name')} feature leakage audit"
        md = render_feature_markdown(payload, title)
        md += (
            "\n## Prediction Metadata Repair\n\n"
            f"- Repair report: `{DEFAULT_OUT}`\n"
            f"- Repaired metadata files: {repair_summary['repaired_metadata_file_count']}\n"
            f"- Fields added: `{repair_summary['fields_added_counts']}`\n"
            "- Prediction arrays, intervals, metrics, ledger rows, and model fits are unchanged.\n"
        )
        atomic_write_text(sidecar_path.with_suffix(".md"), md)
    return {
        "metadata_completeness": payload["metadata_completeness"],
        "raw_metadata_completeness": payload["raw_metadata_completeness"],
        "metadata_closure": payload["metadata_closure"],
        "backfill_policy_inference": payload["backfill_policy_inference"],
        "violations_count": int(payload.get("violations_count") or 0),
    }


def update_report(
    *,
    root: Path,
    triage_row: dict[str, Any],
    dry_run: bool,
    force: bool,
    max_exact_feature_set_size: int,
) -> dict[str, Any]:
    action = action_from_triage_row(triage_row)
    sidecar_path = resolve_repo_path(root, triage_row.get("feature_leakage_audit_path"))
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
        "dry_run": bool(dry_run),
    }
    if sidecar_path is None or not sidecar_path.exists():
        return {**base, "status": "skipped_missing_sidecar"}
    if cache_root is None or not cache_root.exists():
        return {**base, "status": "skipped_missing_prediction_cache"}
    if not metadata_paths:
        return {**base, "status": "skipped_no_metadata_paths"}

    sidecar = read_json(sidecar_path)
    repair_summary = repair_metadata_files(
        root=root,
        action=action,
        sidecar=sidecar,
        metadata_paths=metadata_paths,
        dry_run=dry_run,
    )
    if (
        repair_summary["repaired_metadata_file_count"] == 0
        and not force
        and not dry_run
    ):
        return {
            **base,
            "status": "skipped_metadata_already_complete",
            **repair_summary,
        }

    sidecar_summary = refresh_sidecar(
        root=root,
        sidecar_path=sidecar_path,
        cache_root=cache_root,
        metadata_paths=metadata_paths,
        existing_sidecar=sidecar,
        action=action,
        metadata_selection=metadata_selection,
        repair_summary=repair_summary,
        max_exact_feature_set_size=max_exact_feature_set_size,
        dry_run=dry_run,
    )
    return {
        **base,
        "status": "planned" if dry_run else "repaired",
        **repair_summary,
        "sidecar_summary": sidecar_summary,
        "violations_count": sidecar_summary["violations_count"],
        "dataset_ids": sidecar.get("dataset_ids") or triage_row.get("dataset_ids") or [],
    }


def build_payload(
    *,
    root: Path,
    triage_path: Path,
    report_names: set[str],
    dry_run: bool,
    force: bool,
    max_exact_feature_set_size: int,
) -> dict[str, Any]:
    triage = read_json(triage_path)
    source_rows = rows_needing_repair(triage, report_names)
    rows = [
        update_report(
            root=root,
            triage_row=row,
            dry_run=dry_run,
            force=force,
            max_exact_feature_set_size=max_exact_feature_set_size,
        )
        for row in source_rows
    ]
    status_counts = Counter(str(row.get("status")) for row in rows)
    field_counts: Counter[str] = Counter()
    for row in rows:
        field_counts.update(row.get("fields_added_counts") or {})
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_triage_path": rel(triage_path, root),
        "force": bool(force),
        "dry_run": bool(dry_run),
        "report_name_filter": sorted(report_names),
        "source_row_count": len(source_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "repaired_report_count": sum(1 for row in rows if row.get("status") == "repaired"),
        "planned_report_count": sum(1 for row in rows if row.get("status") == "planned"),
        "total_metadata_files_scanned": sum(
            int(row.get("metadata_file_count") or 0) for row in rows
        ),
        "total_metadata_files_repaired": sum(
            int(row.get("repaired_metadata_file_count") or 0) for row in rows
        ),
        "fields_added_counts": dict(sorted(field_counts.items())),
        "total_violations": sum(int(row.get("violations_count") or 0) for row in rows),
        "claim_boundaries": [
            "This artifact records metadata-only repair of legacy prediction metadata.",
            "The repair adds current-runner feature-drop and safe preprocessing-name metadata fields only.",
            "It does not rewrite predictions, intervals, metrics, ledger rows, or model fits.",
            "This is not fairness, causal, legal, production, bounded-support, Venn-Abers validation, or final-model-selection evidence.",
        ],
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Feature Leakage Prediction Metadata Repair",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source triage: `{payload['source_triage_path']}`",
        f"- Source rows: {payload['source_row_count']}",
        f"- Repaired reports: {payload['repaired_report_count']}",
        f"- Planned reports: {payload['planned_report_count']}",
        f"- Status counts: `{payload['status_counts']}`",
        f"- Metadata files scanned: {payload['total_metadata_files_scanned']}",
        f"- Metadata files repaired: {payload['total_metadata_files_repaired']}",
        f"- Fields added: `{payload['fields_added_counts']}`",
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
            "| Report | Status | Metadata | Repaired | Violations | Sidecar |",
            "| --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row.get('report_name')}` | "
            f"`{row.get('status')}` | "
            f"{row.get('metadata_file_count')} | "
            f"{row.get('repaired_metadata_file_count')} | "
            f"{row.get('violations_count', 0)} | "
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
        dry_run=args.dry_run,
        force=args.force,
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
                "repaired_report_count": payload["repaired_report_count"],
                "planned_report_count": payload["planned_report_count"],
                "status_counts": payload["status_counts"],
                "total_metadata_files_scanned": payload[
                    "total_metadata_files_scanned"
                ],
                "total_metadata_files_repaired": payload[
                    "total_metadata_files_repaired"
                ],
                "fields_added_counts": payload["fields_added_counts"],
                "total_violations": payload["total_violations"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
