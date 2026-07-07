"""Backfill missing prediction-metadata feature-leakage sidecars.

The integrity remediation backlog already identifies reports that lack a
feature-leakage sidecar. This script turns those backlog rows into concrete
`feature_leakage_audit.json`/`.md` artifacts whenever prediction metadata is
available in the experiment cache.
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
from experiments.regression.scripts.audit_prediction_feature_leakage import (
    render_markdown,
    scan_metadata,
)


DEFAULT_BACKLOG = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "integrity_remediation_backlog.json"
)
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "feature_leakage_sidecar_backfill.json"
)
FEATURE_SIDECAR_ISSUE = "no_prediction_metadata_feature_leakage_sidecar"
SCHEMA = "cpfi_feature_leakage_sidecar_backfill_v1"
STATUS_RANK = {
    "skipped_completed": 0,
    "skipped_method": 1,
    "failed": 2,
    "completed": 3,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--backlog", default=DEFAULT_BACKLOG, help="Backlog JSON path.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output summary JSON path.")
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
        help="Only enforce exact feature-set equality when the single observed set is at or below this size.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing sidecars.")
    parser.add_argument("--dry-run", action="store_true", help="Plan without writing sidecars.")
    parser.add_argument(
        "--no-existing-backfill-summary",
        action="store_true",
        help="Do not summarize already generated backfilled sidecars when the source backlog is closed.",
    )
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


def resolve_repo_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def load_yaml(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def cache_root_for_action(root: Path, action: dict[str, Any]) -> Path | None:
    config = load_yaml(resolve_repo_path(root, action.get("config_path")))
    prediction_cache = (config.get("logging") or {}).get("prediction_cache_root")
    if prediction_cache:
        return resolve_repo_path(root, str(prediction_cache))

    summary_path = resolve_repo_path(root, action.get("pilot_summary_path"))
    if summary_path is not None and summary_path.exists():
        summary = read_json(summary_path)
        ledger = summary.get("ledger")
        if ledger:
            ledger_path = resolve_repo_path(root, str(ledger))
            if ledger_path is not None:
                return ledger_path.parent / "checkpoints" / "predictions"
    return None


def ledger_path_for_action(root: Path, action: dict[str, Any]) -> Path | None:
    summary_path = resolve_repo_path(root, action.get("pilot_summary_path"))
    if summary_path is not None and summary_path.exists():
        summary = read_json(summary_path)
        ledger = summary.get("ledger")
        if ledger:
            return resolve_repo_path(root, str(ledger))

    config = load_yaml(resolve_repo_path(root, action.get("config_path")))
    ledger = (config.get("logging") or {}).get("ledger")
    if ledger:
        return resolve_repo_path(root, str(ledger))
    return None


def report_dir_for_action(root: Path, action: dict[str, Any]) -> Path | None:
    summary_path = resolve_repo_path(root, action.get("pilot_summary_path"))
    if summary_path is not None:
        return summary_path.parent
    report_name = action.get("report_name")
    if report_name:
        return root / "experiments/regression/reports" / str(report_name)
    return None


def metadata_paths(cache_root: Path | None) -> list[Path]:
    if cache_root is None or not cache_root.exists():
        return []
    return sorted(cache_root.glob("*/*/metadata.json"))


def canonical_ledger_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match pilot-summary canonical ledger semantics without pandas."""

    by_run_id: dict[str, tuple[int, int, dict[str, Any]]] = {}
    missing_run_rows: list[dict[str, Any]] = []
    for order, row in enumerate(rows):
        run_id = row.get("run_id")
        if not run_id:
            missing_run_rows.append(row)
            continue
        status_rank = STATUS_RANK.get(str(row.get("status", "missing")), 1)
        current = by_run_id.get(str(run_id))
        if current is None or (status_rank, order) >= (current[0], current[1]):
            by_run_id[str(run_id)] = (status_rank, order, row)
    canonical = [
        item[2]
        for item in sorted(by_run_id.values(), key=lambda value: value[1])
    ]
    return [*missing_run_rows, *canonical]


def _stable_key_part(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return str(value)


def prediction_semantic_key(row: dict[str, Any]) -> tuple[str, ...]:
    """Return a prediction-level key for superseding legacy metadata artifacts.

    Runner changes can legitimately rewrite prediction bundle schemas and thus
    produce new artifact ids/run ids for the same fitted prediction problem. For
    feature-leakage metadata, the relevant unit is the fitted prediction bundle,
    not each conformal method row. When the ledger has enough identity fields,
    use that prediction-level key so a later schema-complete rerun supersedes a
    legacy metadata-incomplete bundle.
    """

    required = ["dataset_id", "model_id", "seed"]
    if any(row.get(field) is None for field in required):
        return (
            "artifact",
            _stable_key_part(row.get("prediction_artifact") or row.get("run_id")),
        )
    return (
        "prediction",
        _stable_key_part(row.get("dataset_id")),
        _stable_key_part(row.get("model_family")),
        _stable_key_part(row.get("model_id")),
        _stable_key_part(row.get("model_params") or {}),
        _stable_key_part(row.get("seed")),
    )


def canonical_prediction_metadata_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return latest completed rows at prediction-bundle granularity."""

    canonical = canonical_ledger_rows(rows)
    by_key: dict[tuple[str, ...], tuple[int, dict[str, Any]]] = {}
    missing_key_rows: list[dict[str, Any]] = []
    for order, row in enumerate(canonical):
        if row.get("status") != "completed":
            continue
        key = prediction_semantic_key(row)
        if key == ("artifact", ""):
            missing_key_rows.append(row)
            continue
        current = by_key.get(key)
        if current is None or order >= current[0]:
            by_key[key] = (order, row)
    selected = [
        item[1]
        for item in sorted(by_key.values(), key=lambda value: value[0])
    ]
    return [*missing_key_rows, *selected]


def ledger_referenced_metadata_paths(
    *,
    root: Path,
    action: dict[str, Any],
    cache_root: Path | None,
) -> list[Path]:
    if cache_root is None:
        return []
    ledger_path = ledger_path_for_action(root, action)
    if ledger_path is None or not ledger_path.exists():
        return []

    paths: set[Path] = set()
    rows = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    for row in canonical_prediction_metadata_rows(rows):
        artifact_paths = row.get("artifact_paths") or {}
        metadata_path = artifact_paths.get("prediction_metadata")
        if metadata_path:
            path = resolve_repo_path(root, str(metadata_path))
            if path is not None and path.exists():
                paths.add(path)
            continue
        artifact_id = row.get("prediction_artifact")
        if artifact_id:
            artifact = str(artifact_id)
            path = cache_root / artifact[:2] / artifact / "metadata.json"
            if path.exists():
                paths.add(path)
    return sorted(paths)


def metadata_paths_for_action(
    *,
    root: Path,
    action: dict[str, Any],
    cache_root: Path | None,
) -> tuple[list[Path], str]:
    ledger_paths = ledger_referenced_metadata_paths(
        root=root,
        action=action,
        cache_root=cache_root,
    )
    if ledger_paths:
        return ledger_paths, "ledger_referenced_prediction_artifacts"
    return metadata_paths(cache_root), "cache_root_glob_fallback"


def _string_values(values: Any) -> set[str]:
    if not values:
        return set()
    return {str(value) for value in values if value is not None}


def _single_or_none(values: set[str]) -> str | None:
    if len(values) == 1:
        return next(iter(values))
    return None


def infer_policy_checks(
    paths: list[Path],
    *,
    max_exact_feature_set_size: int,
) -> dict[str, Any]:
    targets: set[str] = set()
    groups: set[str] = set()
    split_groups: set[str] = set()
    transforms: set[str] = set()
    forbidden_features: set[str] = set()
    feature_sets: Counter[tuple[str, ...]] = Counter()
    drop_sets: Counter[tuple[str, ...]] = Counter()
    missing_feature_drop_columns = 0
    missing_feature_drop_policy = 0

    for path in paths:
        metadata = read_json(path)
        target = metadata.get("target")
        group = metadata.get("group_col")
        transform = metadata.get("target_transform")
        policy = metadata.get("feature_drop_policy") or {}
        splits = metadata.get("splits") or {}
        drops = _string_values(metadata.get("feature_drop_columns"))
        features = tuple(sorted(_string_values(metadata.get("feature_names"))))
        if metadata.get("feature_drop_columns") is None:
            missing_feature_drop_columns += 1
        if not metadata.get("feature_drop_policy"):
            missing_feature_drop_policy += 1

        targets.update(_string_values([target]))
        groups.update(_string_values([group]))
        groups.update(_string_values([policy.get("primary_group_col")]))
        split_groups.update(_string_values([policy.get("split_group_col")]))
        split_groups.update(_string_values([splits.get("group_col")]))
        transforms.update(_string_values([transform]))
        forbidden_features.update(_string_values([target, group]))
        forbidden_features.update(_string_values([policy.get("primary_group_col")]))
        forbidden_features.update(_string_values([policy.get("split_group_col")]))
        forbidden_features.update(drops)

        if features:
            feature_sets[features] += 1
        if drops:
            drop_sets[tuple(sorted(drops))] += 1

    complete_policy_metadata = bool(paths) and missing_feature_drop_policy == 0
    expected_features: set[str] = set()
    exact_feature_set_enforced = False
    if len(feature_sets) == 1:
        only_features = set(next(iter(feature_sets)))
        if len(only_features) <= max_exact_feature_set_size:
            expected_features = only_features
            exact_feature_set_enforced = True

    expected_drop_columns: set[str] = set()
    exact_drop_set_enforced = False
    complete_drop_metadata = bool(paths) and missing_feature_drop_columns == 0
    if len(drop_sets) == 1 and complete_drop_metadata:
        expected_drop_columns = set(next(iter(drop_sets)))
        exact_drop_set_enforced = True

    return {
        "forbidden_features": forbidden_features,
        "required_features": expected_features,
        "expected_features": expected_features,
        "expected_drop_columns": expected_drop_columns,
        "expected_target": _single_or_none(targets) if complete_policy_metadata else None,
        "expected_group_col": _single_or_none(groups) if complete_policy_metadata else None,
        "expected_target_transform": _single_or_none(transforms),
        "inference": {
            "metadata_files_scanned": len(paths),
            "missing_feature_drop_columns": missing_feature_drop_columns,
            "missing_feature_drop_policy": missing_feature_drop_policy,
            "complete_drop_metadata": complete_drop_metadata,
            "complete_policy_metadata": complete_policy_metadata,
            "target_values": sorted(targets),
            "group_values": sorted(groups),
            "split_group_values": sorted(split_groups),
            "target_transform_values": sorted(transforms),
            "unique_feature_set_count": len(feature_sets),
            "unique_drop_set_count": len(drop_sets),
            "exact_feature_set_enforced": exact_feature_set_enforced,
            "exact_drop_set_enforced": exact_drop_set_enforced,
            "max_exact_feature_set_size": max_exact_feature_set_size,
            "forbidden_feature_count": len(forbidden_features),
        },
    }


def render_backfilled_markdown(payload: dict[str, Any], title: str) -> str:
    text = render_markdown(payload, title)
    inference = payload.get("backfill_policy_inference") or {}
    lines = [
        "",
        "## Backfill Policy Inference",
        "",
        f"- Source action id: `{payload.get('source_backlog_action_id')}`",
        f"- Target values: `{inference.get('target_values', [])}`",
        f"- Group values: `{inference.get('group_values', [])}`",
        f"- Split-group values: `{inference.get('split_group_values', [])}`",
        f"- Target-transform values: `{inference.get('target_transform_values', [])}`",
        f"- Unique feature-set count: `{inference.get('unique_feature_set_count')}`",
        f"- Unique drop-set count: `{inference.get('unique_drop_set_count')}`",
        f"- Exact feature-set enforced: `{inference.get('exact_feature_set_enforced')}`",
        f"- Exact drop-set enforced: `{inference.get('exact_drop_set_enforced')}`",
        "",
        "Backfilled sidecars are generated from prediction metadata already written "
        "by the runner. They do not rerun models and do not change performance "
        "evidence.",
    ]
    return text + "\n".join(lines) + "\n"


def render_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Feature Leakage Sidecar Backfill",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source backlog: `{payload['backlog_path']}`",
        f"- Current source-backlog action count: {payload['action_count']}",
        f"- Backfilled sidecar rows: {payload['backfilled_sidecar_count']}",
        f"- Status counts: `{payload['status_counts']}`",
        f"- Metadata files scanned: {payload['total_metadata_files_scanned']}",
        f"- Violations: {payload['total_violations']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")

    lines.extend(["", "## Generated Sidecars", ""])
    if not payload["rows"]:
        lines.append("No feature-leakage sidecar backlog actions matched the filters.")
    else:
        lines.extend(
            [
                "| Report | Status | Metadata | Violations | Selection | Sidecar |",
                "| --- | --- | ---: | ---: | --- | --- |",
            ]
        )
        for row in payload["rows"]:
            lines.append(
                "| "
                f"`{row['report_name']}` | "
                f"{row['status']} | "
                f"{row['metadata_file_count']} | "
                f"{row.get('violations_count', 0)} | "
                f"`{row.get('metadata_selection')}` | "
                f"`{row.get('sidecar_json')}` |"
            )
    return "\n".join(lines).rstrip() + "\n"


def backlog_feature_actions(backlog: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in backlog.get("rows", []) or []
        if row.get("issue_type") == FEATURE_SIDECAR_ISSUE
        and row.get("status", "open") == "open"
    ]


def existing_backfilled_sidecar_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for sidecar_json in sorted(
        (root / "experiments/regression/reports").glob("*/feature_leakage_audit.json")
    ):
        payload = read_json(sidecar_json)
        action_id = payload.get("source_backlog_action_id")
        if FEATURE_SIDECAR_ISSUE not in str(action_id):
            continue
        sidecar_md = sidecar_json.with_suffix(".md")
        report_name = sidecar_json.parent.name
        rows.append(
            {
                "action_id": action_id,
                "report_id": payload.get("source_cross_run_report_id")
                or f"report:{report_name}",
                "report_name": report_name,
                "status": "existing_backfilled_sidecar",
                "config_path": payload.get("config_path"),
                "pilot_summary_path": str(
                    Path("experiments/regression/reports")
                    / report_name
                    / "pilot_summary.json"
                ),
                "prediction_cache_root": payload.get("prediction_cache_root"),
                "metadata_file_count": int(payload.get("metadata_files_scanned") or 0),
                "sidecar_json": rel(sidecar_json, root),
                "sidecar_md": rel(sidecar_md, root) if sidecar_md.exists() else None,
                "metadata_selection": payload.get("metadata_selection"),
                "metadata_files_scanned": int(payload.get("metadata_files_scanned") or 0),
                "violations_count": int(payload.get("violations_count") or 0),
                "metadata_completeness": payload.get("metadata_completeness") or {},
                "dataset_ids": payload.get("dataset_ids") or [],
                "expected_target": payload.get("expected_target"),
                "expected_group_col": payload.get("expected_group_col"),
                "expected_target_transform": payload.get("expected_target_transform"),
                "exact_feature_set_enforced": (
                    payload.get("backfill_policy_inference") or {}
                ).get("exact_feature_set_enforced"),
                "exact_drop_set_enforced": (
                    payload.get("backfill_policy_inference") or {}
                ).get("exact_drop_set_enforced"),
            }
        )
    return rows


def backfill_from_backlog(
    *,
    root: Path,
    backlog_path: Path,
    report_names: set[str],
    force: bool,
    dry_run: bool,
    max_exact_feature_set_size: int,
    include_existing_backfills: bool = False,
) -> dict[str, Any]:
    backlog = read_json(backlog_path)
    actions = backlog_feature_actions(backlog)
    if report_names:
        actions = [row for row in actions if str(row.get("report_name")) in report_names]

    rows = []
    status_counts: Counter[str] = Counter()
    total_metadata_files = 0
    total_violations = 0

    if not actions and include_existing_backfills:
        existing_rows = existing_backfilled_sidecar_rows(root)
        if report_names:
            existing_rows = [
                row for row in existing_rows if str(row.get("report_name")) in report_names
            ]
        if force or dry_run:
            actions = [
                {
                    "action_id": row.get("action_id"),
                    "report_id": row.get("report_id"),
                    "report_name": row.get("report_name"),
                    "config_path": row.get("config_path"),
                    "pilot_summary_path": row.get("pilot_summary_path"),
                }
                for row in existing_rows
            ]
        else:
            rows = existing_rows
            status_counts.update(row["status"] for row in rows)
            total_metadata_files = sum(
                int(row.get("metadata_files_scanned") or 0) for row in rows
            )
            total_violations = sum(int(row.get("violations_count") or 0) for row in rows)
            actions = []

    for action in actions:
        report_dir = report_dir_for_action(root, action)
        cache_root = cache_root_for_action(root, action)
        sidecar_json = None if report_dir is None else report_dir / "feature_leakage_audit.json"
        sidecar_md = None if report_dir is None else report_dir / "feature_leakage_audit.md"
        paths, metadata_selection = metadata_paths_for_action(
            root=root,
            action=action,
            cache_root=cache_root,
        )

        status = "generated"
        payload_summary: dict[str, Any] = {}
        if report_dir is None:
            status = "skipped_missing_report_dir"
        elif sidecar_json is not None and sidecar_json.exists() and not force:
            status = "skipped_existing_sidecar"
        elif not paths:
            status = "skipped_no_metadata"
        elif dry_run:
            status = "planned"
        else:
            checks = infer_policy_checks(
                paths,
                max_exact_feature_set_size=max_exact_feature_set_size,
            )
            payload = scan_metadata(
                cache_root,
                forbidden_features=checks["forbidden_features"],
                required_features=checks["required_features"],
                expected_features=checks["expected_features"],
                expected_drop_columns=checks["expected_drop_columns"],
                expected_target=checks["expected_target"],
                expected_group_col=checks["expected_group_col"],
                expected_target_transform=checks["expected_target_transform"],
                config_path=action.get("config_path"),
                metadata_paths=paths,
            )
            payload["source_backlog_action_id"] = action.get("action_id")
            payload["source_cross_run_report_id"] = action.get("report_id")
            payload["metadata_selection"] = metadata_selection
            payload["backfill_policy_inference"] = checks["inference"]
            title = f"{action.get('report_name')} feature leakage audit"
            atomic_write_json(sidecar_json, payload)
            atomic_write_text(sidecar_md, render_backfilled_markdown(payload, title))
            payload_summary = {
                "metadata_files_scanned": payload["metadata_files_scanned"],
                "violations_count": payload["violations_count"],
                "metadata_completeness": payload["metadata_completeness"],
                "dataset_ids": payload["dataset_ids"],
                "expected_target": payload["expected_target"],
                "expected_group_col": payload["expected_group_col"],
                "expected_target_transform": payload["expected_target_transform"],
                "exact_feature_set_enforced": checks["inference"][
                    "exact_feature_set_enforced"
                ],
                "exact_drop_set_enforced": checks["inference"][
                    "exact_drop_set_enforced"
                ],
            }
            total_metadata_files += int(payload["metadata_files_scanned"])
            total_violations += int(payload["violations_count"])

        status_counts[status] += 1
        rows.append(
            {
                "action_id": action.get("action_id"),
                "report_id": action.get("report_id"),
                "report_name": action.get("report_name"),
                "status": status,
                "config_path": action.get("config_path"),
                "pilot_summary_path": action.get("pilot_summary_path"),
                "prediction_cache_root": None if cache_root is None else rel(cache_root, root),
                "metadata_file_count": len(paths),
                "sidecar_json": None if sidecar_json is None else rel(sidecar_json, root),
                "sidecar_md": None if sidecar_md is None else rel(sidecar_md, root),
                "metadata_selection": metadata_selection,
                **payload_summary,
            }
        )

    if include_existing_backfills:
        represented_action_ids = {
            str(row.get("action_id"))
            for row in rows
            if row.get("action_id") is not None
        }
        represented_report_names = {
            str(row.get("report_name"))
            for row in rows
            if row.get("report_name") is not None
        }
        existing_rows = existing_backfilled_sidecar_rows(root)
        if report_names:
            existing_rows = [
                row
                for row in existing_rows
                if str(row.get("report_name")) in report_names
            ]
        for row in existing_rows:
            if (
                str(row.get("action_id")) in represented_action_ids
                or str(row.get("report_name")) in represented_report_names
            ):
                continue
            rows.append(row)
            status_counts.update([str(row["status"])])
            total_metadata_files += int(row.get("metadata_files_scanned") or 0)
            total_violations += int(row.get("violations_count") or 0)

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "backlog_path": rel(backlog_path, root),
        "issue_type": FEATURE_SIDECAR_ISSUE,
        "force": bool(force),
        "dry_run": bool(dry_run),
        "report_name_filter": sorted(report_names),
        "action_count": len(actions),
        "backfilled_sidecar_count": sum(
            1
            for row in rows
            if row.get("status") in {"generated", "existing_backfilled_sidecar"}
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "total_metadata_files_scanned": total_metadata_files,
        "total_violations": total_violations,
        "rows": rows,
        "claim_boundaries": [
            "This backfill creates feature/drop-policy metadata sidecars only.",
            "A zero-violation sidecar is limited to available prediction metadata and inferred checks.",
            "These artifacts are not fairness, causal, legal, production, or final-model-selection evidence.",
        ],
    }


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    payload = backfill_from_backlog(
        root=root,
        backlog_path=resolve_repo_path(root, args.backlog) or Path(args.backlog),
        report_names={str(value) for value in args.report_name},
        force=args.force,
        dry_run=args.dry_run,
        max_exact_feature_set_size=args.max_exact_feature_set_size,
        include_existing_backfills=not args.no_existing_backfill_summary,
    )
    out_path = resolve_repo_path(root, args.out) or Path(args.out)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_summary_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out_path, root),
                "action_count": payload["action_count"],
                "backfilled_sidecar_count": payload["backfilled_sidecar_count"],
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
