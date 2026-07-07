"""Validate bounded-support post-handling policies for manuscript bundles.

This artifact reconstructs completed interval rows from prediction caches and
evaluates raw, clipped, and abstention policies on the original target scale.
It is intentionally scoped by bundle id when requested; a partial scope must
not be read as a manuscript-wide bounded-support validity claim.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from cpfi.regression.target import inverse_transform_target_with_metadata
from experiments.regression.scripts.audit_regression_endpoints import (
    build_from_row,
    canonical_rows,
    load_jsonl,
)
from experiments.regression.scripts.run_regression_pilot import (
    MethodSkipped,
    PredictionBundle,
    load_prediction_bundle,
    prediction_artifact_dir,
)

warnings.filterwarnings(
    "ignore",
    message="X does not have valid feature names, but LGBMRegressor was fitted with feature names",
    category=UserWarning,
)


SCHEMA = "cpfi_regression_bounded_support_posthandling_validation_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/bounded_support_posthandling_validation.json")
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
TARGET_DOMAIN_PROVENANCE = Path("experiments/regression/catalogs/target_domain_provenance.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument(
        "--bundle-id",
        action="append",
        default=[],
        help="Bundle id to validate. May be repeated. Defaults to all manuscript bundles.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=250,
        help="Print JSON progress every N completed rows per bundle; use 0 to disable.",
    )
    parser.add_argument(
        "--include-method",
        action="append",
        default=[],
        help="Only validate this CP method. May be repeated or comma-separated.",
    )
    parser.add_argument(
        "--include-model",
        action="append",
        default=[],
        help="Only validate this model_id. May be repeated or comma-separated.",
    )
    parser.add_argument(
        "--max-completed-per-bundle",
        type=int,
        default=None,
        help="Optional row cap per bundle after method filtering.",
    )
    parser.add_argument(
        "--state-dir",
        default=None,
        help=(
            "Optional durable JSONL state directory. When set, validated run "
            "records are appended per bundle and reused on resume."
        ),
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Delete matching bundle state files before validating.",
    )
    parser.add_argument(
        "--fsync-state-every",
        type=int,
        default=25,
        help="Fsync state files every N appended records; use 1 for maximum durability.",
    )
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


def state_path_for(state_dir: Path, bundle_id: str) -> Path:
    return state_dir / f"{bundle_id}.jsonl"


def row_key(row: dict[str, Any]) -> str:
    return "|".join(
        str(row.get(key, ""))
        for key in ("run_id", "cp_method", "prediction_artifact")
    )


def load_state_records(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        key = str(record.get("row_key") or "")
        if key:
            records[key] = record
    return records


def append_state_record(
    handle: Any,
    record: dict[str, Any],
    *,
    appended_count: int,
    fsync_every: int,
) -> None:
    handle.write(json.dumps(record, sort_keys=True) + "\n")
    handle.flush()
    if fsync_every > 0 and appended_count % fsync_every == 0:
        os.fsync(handle.fileno())


def normalize_filter_values(values: list[str]) -> set[str]:
    items: set[str] = set()
    for value in values:
        items.update(item.strip() for item in value.split(",") if item.strip())
    return items


def bundle_paths(root: Path, bundle_id: str) -> dict[str, Path]:
    return {
        "config": root / "experiments/regression/configs" / f"{bundle_id}.yaml",
        "ledger": root / "experiments/regression/results" / bundle_id / "ledger.jsonl",
        "endpoint_audit": root / "experiments/regression/reports" / bundle_id / "endpoint_audit.json",
    }


def prediction_cache_root(config: dict[str, Any]) -> Path:
    logging = config.get("logging") or {}
    value = logging.get("prediction_cache_root")
    if value:
        return Path(value)
    return Path(logging["checkpoint_root"]) / "predictions"


def load_prediction_bundle_for_posthandling(
    cache_root: Path,
    artifact_id: str,
) -> tuple[PredictionBundle | None, str | None]:
    """Load strict caches first, then legacy caches with an explicit caveat."""

    bundle = load_prediction_bundle(cache_root, artifact_id)
    if bundle is not None:
        return bundle, None

    artifact_dir = prediction_artifact_dir(cache_root, artifact_id)
    bundle_path = artifact_dir / "bundle.npz"
    metadata_path = artifact_dir / "metadata.json"
    if not bundle_path.exists() or not metadata_path.exists():
        return None, None

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("artifact_id") != artifact_id:
        return None, None

    missing_fields = []
    if not isinstance(metadata.get("data_provenance"), dict):
        missing_fields.append("data_provenance")
    if not isinstance(metadata.get("code_provenance"), dict):
        missing_fields.append("code_provenance")
    if not missing_fields:
        return None, None

    reason = "missing_" + "_and_".join(missing_fields)
    with np.load(bundle_path, allow_pickle=False) as data:
        return (
            PredictionBundle(
                artifact_id=artifact_id,
                artifact_dir=artifact_dir,
                cache_status=f"legacy_hit_{reason}",
                fit_seconds=float(metadata.get("fit_seconds", 0.0)),
                y_train=data["y_train"],
                y_cal=data["y_cal"],
                y_test=data["y_test"],
                yhat_train=data["yhat_train"],
                yhat_cal=data["yhat_cal"],
                yhat_test=data["yhat_test"],
                groups_cal=data["groups_cal"].astype(str),
                groups_test=data["groups_test"].astype(str),
                split_groups_train=(
                    data["split_groups_train"].astype(str)
                    if "split_groups_train" in data.files
                    else None
                ),
                X_train=data["X_train"],
                X_cal=data["X_cal"],
                X_test=data["X_test"],
                scale_cal=data["scale_cal"],
                scale_test=data["scale_test"],
                target_transform=str(metadata.get("target_transform", "identity")),
            ),
            reason,
        )


def empty_stats() -> dict[str, Any]:
    return {
        "interval_count": 0,
        "evaluable_interval_count": 0,
        "invalid_interval_count": 0,
        "abstained_interval_count": 0,
        "covered_count": 0,
        "lower_miss_count": 0,
        "upper_miss_count": 0,
        "width_sum": 0.0,
        "interval_score_sum": 0.0,
        "interval_score_nonfinite_count": 0,
        "interval_score_sum_overflow_count": 0,
        "min_lower": None,
        "max_upper": None,
        "max_width": None,
        "lower_below_natural_count": 0,
        "upper_above_natural_count": 0,
        "coverage_by_group_counts": {},
    }


def update_extreme(current: float | None, values: np.ndarray, *, op: str) -> float | None:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return current
    candidate = float(np.min(finite) if op == "min" else np.max(finite))
    if current is None:
        return candidate
    return min(current, candidate) if op == "min" else max(current, candidate)


def add_group_counts(stats: dict[str, Any], groups: np.ndarray, covered: np.ndarray, widths: np.ndarray) -> None:
    group_counts = stats.setdefault("coverage_by_group_counts", {})
    for group in np.unique(groups):
        mask = groups == group
        key = str(group)
        row = group_counts.setdefault(
            key,
            {"count": 0, "covered_count": 0, "width_sum": 0.0},
        )
        row["count"] += int(np.sum(mask))
        row["covered_count"] += int(np.sum(covered[mask]))
        row["width_sum"] += float(np.sum(widths[mask]))


def update_stats(
    stats: dict[str, Any],
    *,
    y_true: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    alpha: float,
    groups: np.ndarray,
    natural_lower: float | None,
    natural_upper: float | None,
    abstained_count: int = 0,
) -> None:
    y = np.asarray(y_true, dtype=float)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    stats["interval_count"] += int(len(y) + abstained_count)
    stats["abstained_interval_count"] += int(abstained_count)
    finite = np.isfinite(y) & np.isfinite(lo) & np.isfinite(hi) & (hi >= lo)
    stats["invalid_interval_count"] += int(len(y) - np.sum(finite))
    if not np.any(finite):
        return
    y = y[finite]
    lo = lo[finite]
    hi = hi[finite]
    valid_groups = np.asarray(groups)[finite]
    below = y < lo
    above = y > hi
    covered = ~(below | above)
    widths = hi - lo
    with np.errstate(over="ignore", invalid="ignore"):
        scores = widths.copy()
        scores[below] += (2.0 / alpha) * (lo[below] - y[below])
        scores[above] += (2.0 / alpha) * (y[above] - hi[above])
    finite_scores = scores[np.isfinite(scores)]
    stats["interval_score_nonfinite_count"] += int(len(scores) - len(finite_scores))
    try:
        score_sum = math.fsum(float(value) for value in finite_scores)
        next_score_sum = float(stats["interval_score_sum"]) + score_sum
    except OverflowError:
        stats["interval_score_sum_overflow_count"] += 1
        score_sum = None
        next_score_sum = None
    if next_score_sum is not None and math.isfinite(next_score_sum):
        stats["interval_score_sum"] = next_score_sum
    elif score_sum is not None:
        stats["interval_score_sum_overflow_count"] += 1
    stats["evaluable_interval_count"] += int(len(y))
    stats["covered_count"] += int(np.sum(covered))
    stats["lower_miss_count"] += int(np.sum(below))
    stats["upper_miss_count"] += int(np.sum(above))
    stats["width_sum"] += float(np.sum(widths))
    stats["min_lower"] = update_extreme(stats["min_lower"], lo, op="min")
    stats["max_upper"] = update_extreme(stats["max_upper"], hi, op="max")
    stats["max_width"] = update_extreme(stats["max_width"], widths, op="max")
    if natural_lower is not None:
        stats["lower_below_natural_count"] += int(np.sum(lo < natural_lower))
    if natural_upper is not None:
        stats["upper_above_natural_count"] += int(np.sum(hi > natural_upper))
    add_group_counts(stats, valid_groups, covered, widths)


def finalize_stats(stats: dict[str, Any]) -> dict[str, Any]:
    out = dict(stats)
    n = int(out["evaluable_interval_count"])
    total = int(out["interval_count"])
    out["coverage"] = None if n == 0 else out["covered_count"] / n
    out["mean_width"] = None if n == 0 else out["width_sum"] / n
    score_pathology_count = int(out.get("interval_score_nonfinite_count") or 0) + int(
        out.get("interval_score_sum_overflow_count") or 0
    )
    if n == 0 or score_pathology_count:
        out["interval_score"] = None
        if score_pathology_count:
            out["interval_score_sum"] = None
    else:
        out["interval_score"] = out["interval_score_sum"] / n
    out["lower_miss_rate"] = None if n == 0 else out["lower_miss_count"] / n
    out["upper_miss_rate"] = None if n == 0 else out["upper_miss_count"] / n
    out["abstention_rate"] = None if total == 0 else out["abstained_interval_count"] / total
    group_summary = {}
    for group, row in sorted((out.get("coverage_by_group_counts") or {}).items()):
        count = int(row["count"])
        group_summary[group] = {
            "count": count,
            "coverage": None if count == 0 else row["covered_count"] / count,
            "mean_width": None if count == 0 else row["width_sum"] / count,
        }
    out["coverage_by_group"] = group_summary
    out.pop("coverage_by_group_counts", None)
    return out


def merge_stats(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in (
        "interval_count",
        "evaluable_interval_count",
        "invalid_interval_count",
        "abstained_interval_count",
        "covered_count",
        "lower_miss_count",
        "upper_miss_count",
        "lower_below_natural_count",
        "upper_above_natural_count",
        "interval_score_nonfinite_count",
        "interval_score_sum_overflow_count",
    ):
        target[key] += int(source.get(key) or 0)
    for key in ("width_sum",):
        target[key] += float(source.get(key) or 0.0)
    source_score_sum = source.get("interval_score_sum")
    if source_score_sum is not None:
        try:
            next_score_sum = float(target["interval_score_sum"]) + float(source_score_sum)
        except (OverflowError, TypeError, ValueError):
            target["interval_score_sum_overflow_count"] += 1
        else:
            if math.isfinite(next_score_sum):
                target["interval_score_sum"] = next_score_sum
            else:
                target["interval_score_sum_overflow_count"] += 1
    target["min_lower"] = update_extreme(
        target["min_lower"],
        np.asarray([source["min_lower"]], dtype=float)
        if source.get("min_lower") is not None
        else np.asarray([], dtype=float),
        op="min",
    )
    target["max_upper"] = update_extreme(
        target["max_upper"],
        np.asarray([source["max_upper"]], dtype=float)
        if source.get("max_upper") is not None
        else np.asarray([], dtype=float),
        op="max",
    )
    target["max_width"] = update_extreme(
        target["max_width"],
        np.asarray([source["max_width"]], dtype=float)
        if source.get("max_width") is not None
        else np.asarray([], dtype=float),
        op="max",
    )
    group_counts = target.setdefault("coverage_by_group_counts", {})
    for group, row in (source.get("coverage_by_group_counts") or {}).items():
        current = group_counts.setdefault(group, {"count": 0, "covered_count": 0, "width_sum": 0.0})
        current["count"] += int(row["count"])
        current["covered_count"] += int(row["covered_count"])
        current["width_sum"] += float(row["width_sum"])


def merge_state_record(
    record: dict[str, Any],
    *,
    policy_stats: dict[str, dict[str, Any]],
    method_policy_stats: dict[str, dict[str, dict[str, Any]]],
    failures: list[dict[str, Any]],
) -> tuple[int, int]:
    method = str(record.get("cp_method", "missing"))
    if record.get("status") == "validated":
        for policy, stats in (record.get("policy_stats") or {}).items():
            if policy in policy_stats:
                merge_stats(policy_stats[policy], stats)
                merge_stats(method_policy_stats[method][policy], stats)
        return 1, int(record.get("y_out_of_natural_domain_count") or 0)
    if record.get("status") == "failed":
        failures.append(
            {
                "run_id": record.get("run_id"),
                "cp_method": method,
                "model_id": record.get("model_id"),
                "error_type": record.get("error_type"),
                "error_message": record.get("error_message"),
                "from_state": True,
            }
        )
    return 0, int(record.get("y_out_of_natural_domain_count") or 0)


def natural_out_of_domain_count(y_true: np.ndarray, natural_lower: float | None, natural_upper: float | None) -> int:
    count = 0
    if natural_lower is not None:
        count += int(np.sum(y_true < natural_lower))
    if natural_upper is not None:
        count += int(np.sum(y_true > natural_upper))
    return count


def validate_bundle(
    *,
    root: Path,
    bundle: dict[str, Any],
    provenance: dict[str, Any],
    progress_every: int,
    include_methods: set[str],
    include_models: set[str],
    max_completed_per_bundle: int | None,
    state_dir: Path | None,
    reset_state: bool,
    fsync_state_every: int,
) -> dict[str, Any]:
    bundle_id = str(bundle["bundle_id"])
    paths = bundle_paths(root, bundle_id)
    missing_paths = [name for name, path in paths.items() if not path.exists()]
    if missing_paths:
        return {
            "bundle_id": bundle_id,
            "dataset_id": bundle.get("dataset_id"),
            "target": bundle.get("target"),
            "status": "missing_required_artifacts",
            "missing_paths": missing_paths,
            "paths": {name: rel(path, root) for name, path in paths.items()},
        }

    config = yaml.safe_load(paths["config"].read_text(encoding="utf-8"))
    cache_root = resolve(root, prediction_cache_root(config))
    rows = [
        row
        for row in canonical_rows(load_jsonl(paths["ledger"]))
        if row.get("status") == "completed"
    ]
    total_completed_rows = len(rows)
    if include_methods:
        rows = [row for row in rows if str(row.get("cp_method")) in include_methods]
    if include_models:
        rows = [row for row in rows if str(row.get("model_id")) in include_models]
    filtered_completed_rows = len(rows)
    if max_completed_per_bundle is not None:
        rows = rows[:max_completed_per_bundle]
    natural_lower = provenance.get("natural_lower")
    natural_upper = provenance.get("natural_upper")
    if natural_lower is not None:
        natural_lower = float(natural_lower)
    if natural_upper is not None:
        natural_upper = float(natural_upper)

    policy_stats = {
        "raw_unclipped": empty_stats(),
        "clip_to_natural_bounds": empty_stats(),
        "abstain_if_raw_out_of_domain": empty_stats(),
    }
    method_policy_stats: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: {
            "raw_unclipped": empty_stats(),
            "clip_to_natural_bounds": empty_stats(),
            "abstain_if_raw_out_of_domain": empty_stats(),
        }
    )
    failures: list[dict[str, Any]] = []
    interval_cache: dict[tuple[Any, ...], Any] = {}
    prediction_bundle_cache: dict[str, PredictionBundle] = {}
    prediction_bundle_legacy_reasons: dict[str, str | None] = {}
    cache_stats: Counter = Counter()
    legacy_prediction_cache_record_count = 0
    legacy_prediction_cache_artifact_reasons: dict[str, str] = {}
    y_out_of_domain_count = 0
    reconstructed_runs = 0
    resumed_records = 0
    state_records_written = 0
    state_path = state_path_for(state_dir, bundle_id) if state_dir is not None else None
    state_records: dict[str, dict[str, Any]] = {}
    if state_path is not None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        if reset_state and state_path.exists():
            state_path.unlink()
        state_records = load_state_records(state_path)

    for row in rows:
        record = state_records.get(row_key(row))
        if not record:
            continue
        legacy_reason = record.get("legacy_prediction_cache_reason")
        if legacy_reason:
            legacy_prediction_cache_record_count += 1
            legacy_prediction_cache_artifact_reasons[
                str(record.get("prediction_artifact"))
            ] = str(legacy_reason)
        reconstructed, y_out = merge_state_record(
            record,
            policy_stats=policy_stats,
            method_policy_stats=method_policy_stats,
            failures=failures,
        )
        reconstructed_runs += reconstructed
        y_out_of_domain_count += y_out
        resumed_records += 1

    state_handle = None
    appended_since_open = 0
    try:
        if state_path is not None:
            state_handle = state_path.open("a", encoding="utf-8")
        for index, row in enumerate(rows, start=1):
            key = row_key(row)
            if key in state_records:
                continue
            method = str(row.get("cp_method", "missing"))
            artifact_id = str(row.get("prediction_artifact"))
            record_base = {
                "row_key": key,
                "run_id": row.get("run_id"),
                "cp_method": method,
                "model_id": row.get("model_id"),
                "prediction_artifact": artifact_id,
            }
            try:
                bundle_obj = prediction_bundle_cache.get(artifact_id)
                legacy_reason = prediction_bundle_legacy_reasons.get(artifact_id)
                if bundle_obj is None:
                    bundle_obj, legacy_reason = load_prediction_bundle_for_posthandling(
                        cache_root,
                        artifact_id,
                    )
                    cache_stats["prediction_bundle_misses"] += 1
                    if bundle_obj is None:
                        raise FileNotFoundError(
                            f"prediction bundle not found for {artifact_id}"
                        )
                    prediction_bundle_cache[artifact_id] = bundle_obj
                    prediction_bundle_legacy_reasons[artifact_id] = legacy_reason
                    if legacy_reason:
                        cache_stats["legacy_prediction_bundle_artifact_loads"] += 1
                        cache_stats[
                            f"legacy_prediction_bundle_artifact_loads_{legacy_reason}"
                        ] += 1
                else:
                    cache_stats["prediction_bundle_hits"] += 1
                    if legacy_reason:
                        cache_stats["legacy_prediction_bundle_cache_hits"] += 1
                lower, upper, _, _ = build_from_row(
                    row,
                    config,
                    cache_root,
                    interval_cache=interval_cache,
                    cache_stats=cache_stats,
                    prediction_bundle_loader=lambda _root, loaded_artifact_id: prediction_bundle_cache.get(
                        loaded_artifact_id
                    ),
                )
                y_true, _ = inverse_transform_target_with_metadata(
                    bundle_obj.y_test,
                    bundle_obj.target_transform,
                )
            except (FileNotFoundError, MethodSkipped, Exception) as exc:  # noqa: BLE001
                failure = {
                    "run_id": row.get("run_id"),
                    "cp_method": method,
                    "model_id": row.get("model_id"),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
                failures.append(failure)
                if state_handle is not None:
                    appended_since_open += 1
                    state_records_written += 1
                    append_state_record(
                        state_handle,
                        {
                            **record_base,
                            "status": "failed",
                            "error_type": failure["error_type"],
                            "error_message": failure["error_message"],
                            "y_out_of_natural_domain_count": 0,
                        },
                        appended_count=appended_since_open,
                        fsync_every=fsync_state_every,
                    )
                continue

            y_true = np.asarray(y_true, dtype=float)
            lower = np.asarray(lower, dtype=float)
            upper = np.asarray(upper, dtype=float)
            groups = np.asarray(bundle_obj.groups_test).astype(str)
            alpha = float(row["alpha"])
            run_y_out = natural_out_of_domain_count(
                y_true, natural_lower, natural_upper
            )
            y_out_of_domain_count += run_y_out
            if legacy_reason:
                legacy_prediction_cache_record_count += 1
                legacy_prediction_cache_artifact_reasons[artifact_id] = str(
                    legacy_reason
                )
            clipped_lower = lower.copy()
            clipped_upper = upper.copy()
            if natural_lower is not None:
                clipped_lower = np.maximum(clipped_lower, natural_lower)
            if natural_upper is not None:
                clipped_upper = np.minimum(clipped_upper, natural_upper)
            raw_in_domain = np.ones_like(y_true, dtype=bool)
            if natural_lower is not None:
                raw_in_domain &= lower >= natural_lower
            if natural_upper is not None:
                raw_in_domain &= upper <= natural_upper

            policy_inputs = {
                "raw_unclipped": (y_true, lower, upper, groups, 0),
                "clip_to_natural_bounds": (
                    y_true,
                    clipped_lower,
                    clipped_upper,
                    groups,
                    0,
                ),
                "abstain_if_raw_out_of_domain": (
                    y_true[raw_in_domain],
                    lower[raw_in_domain],
                    upper[raw_in_domain],
                    groups[raw_in_domain],
                    int(np.sum(~raw_in_domain)),
                ),
            }
            run_policy_stats: dict[str, dict[str, Any]] = {}
            for policy, (
                policy_y,
                policy_lower,
                policy_upper,
                policy_groups,
                abstained,
            ) in policy_inputs.items():
                run_stats = empty_stats()
                update_stats(
                    run_stats,
                    y_true=policy_y,
                    lower=policy_lower,
                    upper=policy_upper,
                    alpha=alpha,
                    groups=policy_groups,
                    natural_lower=natural_lower,
                    natural_upper=natural_upper,
                    abstained_count=abstained,
                )
                run_policy_stats[policy] = run_stats
                merge_stats(policy_stats[policy], run_stats)
                merge_stats(method_policy_stats[method][policy], run_stats)
            reconstructed_runs += 1
            if state_handle is not None:
                appended_since_open += 1
                state_records_written += 1
                append_state_record(
                    state_handle,
                    {
                        **record_base,
                        "status": "validated",
                        "y_out_of_natural_domain_count": run_y_out,
                        "legacy_prediction_cache_reason": legacy_reason,
                        "policy_stats": run_policy_stats,
                    },
                    appended_count=appended_since_open,
                    fsync_every=fsync_state_every,
                )
            if progress_every > 0 and index % progress_every == 0:
                print(
                    json.dumps(
                        {
                            "event": "bounded_support_posthandling_progress",
                            "bundle_id": bundle_id,
                            "processed_completed_rows": index,
                            "completed_rows": len(rows),
                            "resumed_records": resumed_records,
                            "reconstructed_runs": reconstructed_runs,
                            "failures": len(failures),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
    finally:
        if state_handle is not None:
            os.fsync(state_handle.fileno())
            state_handle.close()

    finalized_policy_stats = {
        policy: finalize_stats(stats) for policy, stats in sorted(policy_stats.items())
    }
    finalized_method_stats = {
        method: {
            policy: finalize_stats(stats)
            for policy, stats in sorted(policies.items())
        }
        for method, policies in sorted(method_policy_stats.items())
    }
    status = (
        "validated"
        if rows and reconstructed_runs == len(rows) and not failures
        else "validation_incomplete"
    )
    legacy_prediction_cache_reasons = Counter(
        legacy_prediction_cache_artifact_reasons.values()
    )
    return {
        "bundle_id": bundle_id,
        "dataset_id": bundle.get("dataset_id"),
        "target": bundle.get("target"),
        "target_domain_class": provenance.get("target_domain_class"),
        "natural_lower": natural_lower,
        "natural_upper": natural_upper,
        "natural_bound_status": provenance.get("natural_bound_status"),
        "status": status,
        "completed_ledger_rows": len(rows),
        "total_completed_ledger_rows": total_completed_rows,
        "filtered_completed_ledger_rows": filtered_completed_rows,
        "reconstructed_runs": reconstructed_runs,
        "reconstruction_failures": len(failures),
        "legacy_prediction_cache_record_count": legacy_prediction_cache_record_count,
        "legacy_prediction_cache_artifact_count": len(
            legacy_prediction_cache_artifact_reasons
        ),
        "legacy_prediction_cache_reasons": dict(
            sorted(legacy_prediction_cache_reasons.items())
        ),
        "legacy_prediction_cache_artifacts_sample": [
            {"prediction_artifact": artifact, "reason": reason}
            for artifact, reason in sorted(
                legacy_prediction_cache_artifact_reasons.items()
            )[:25]
        ],
        "y_out_of_natural_domain_count": y_out_of_domain_count,
        "policies": finalized_policy_stats,
        "method_policies": finalized_method_stats,
        "cache_stats": dict(sorted(cache_stats.items())),
        "state": {
            "path": None if state_path is None else rel(state_path, root),
            "resumed_records": resumed_records,
            "written_records": state_records_written,
            "available_records": len(state_records),
        },
        "failures": failures[:25],
        "failure_count_total": len(failures),
        "paths": {
            "config": rel(paths["config"], root),
            "ledger": rel(paths["ledger"], root),
            "endpoint_audit": rel(paths["endpoint_audit"], root),
            "prediction_cache_root": rel(cache_root, root),
        },
    }


def interval_score_pathology_count(row: dict[str, Any]) -> int:
    total = 0
    for stats in (row.get("policies") or {}).values():
        total += int(stats.get("interval_score_nonfinite_count") or 0)
        total += int(stats.get("interval_score_sum_overflow_count") or 0)
    return total


def build_payload(
    root: Path,
    bundle_ids: list[str],
    progress_every: int,
    include_methods: set[str] | None = None,
    include_models: set[str] | None = None,
    max_completed_per_bundle: int | None = None,
    state_dir: Path | None = None,
    reset_state: bool = False,
    fsync_state_every: int = 25,
) -> dict[str, Any]:
    bundle_index_path = root / BUNDLE_INDEX
    provenance_path = root / TARGET_DOMAIN_PROVENANCE
    bundle_index = read_json(bundle_index_path)
    provenance_payload = read_json(provenance_path)
    provenance_by_key = {
        (str(row.get("dataset_id")), str(row.get("target"))): row
        for row in provenance_payload.get("rows", []) or []
    }
    bundles = [row for row in bundle_index.get("bundles", []) or [] if isinstance(row, dict)]
    selected_ids = set(bundle_ids)
    selected = [
        bundle
        for bundle in bundles
        if not selected_ids or str(bundle.get("bundle_id")) in selected_ids
    ]
    rows = []
    include_methods = set() if include_methods is None else set(include_methods)
    include_models = set() if include_models is None else set(include_models)
    for bundle in selected:
        key = (str(bundle.get("dataset_id")), str(bundle.get("target")))
        rows.append(
            validate_bundle(
                root=root,
                bundle=bundle,
                provenance=provenance_by_key.get(key, {}),
                progress_every=progress_every,
                include_methods=include_methods,
                include_models=include_models,
                max_completed_per_bundle=max_completed_per_bundle,
                state_dir=state_dir,
                reset_state=reset_state,
                fsync_state_every=fsync_state_every,
            )
        )
    failed_rows = [row for row in rows if row.get("status") != "validated"]
    validated_rows = [row for row in rows if row.get("status") == "validated"]
    scope_complete = len(selected) == len(bundles) and bool(bundles)
    status = (
        "bounded_support_posthandling_validation_completed"
        if scope_complete and not failed_rows
        else "bounded_support_posthandling_validation_partial"
        if validated_rows and not failed_rows
        else "bounded_support_posthandling_validation_incomplete"
    )
    legacy_prediction_cache_record_count = sum(
        int(row.get("legacy_prediction_cache_record_count") or 0) for row in rows
    )
    legacy_prediction_cache_artifact_count = sum(
        int(row.get("legacy_prediction_cache_artifact_count") or 0) for row in rows
    )
    legacy_prediction_cache_bundle_count = sum(
        1
        for row in rows
        if int(row.get("legacy_prediction_cache_record_count") or 0) > 0
    )
    legacy_prediction_cache_reasons = Counter()
    for row in rows:
        legacy_prediction_cache_reasons.update(
            row.get("legacy_prediction_cache_reasons") or {}
        )
    interval_score_pathology_total = sum(interval_score_pathology_count(row) for row in rows)
    interval_score_pathology_bundle_count = sum(
        1 for row in rows if interval_score_pathology_count(row) > 0
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "manuscript_bundle_index": rel(bundle_index_path, root),
            "target_domain_provenance": rel(provenance_path, root),
        },
        "scope": {
            "bundle_ids": [str(bundle.get("bundle_id")) for bundle in selected],
            "include_methods": sorted(include_methods),
            "include_models": sorted(include_models),
            "max_completed_per_bundle": max_completed_per_bundle,
            "state_dir": None if state_dir is None else rel(state_dir, root),
            "scope_note": (
                "method_or_row_limited"
                if include_methods or include_models or max_completed_per_bundle is not None
                else "all_completed_rows_in_selected_bundles"
            ),
        },
        "summary": {
            "overall_status": status,
            "available_bundle_count": len(bundles),
            "selected_bundle_count": len(selected),
            "validated_bundle_count": len(validated_rows),
            "unvalidated_bundle_count": len(bundles) - len(validated_rows),
            "scope_complete": scope_complete,
            "reconstructed_runs": sum(int(row.get("reconstructed_runs") or 0) for row in rows),
            "completed_ledger_rows": sum(int(row.get("completed_ledger_rows") or 0) for row in rows),
            "filtered_completed_ledger_rows": sum(
                int(row.get("filtered_completed_ledger_rows") or 0) for row in rows
            ),
            "total_completed_ledger_rows_in_selected_bundles": sum(
                int(row.get("total_completed_ledger_rows") or 0) for row in rows
            ),
            "reconstruction_failures": sum(int(row.get("reconstruction_failures") or 0) for row in rows),
            "legacy_prediction_cache_record_count": legacy_prediction_cache_record_count,
            "legacy_prediction_cache_artifact_count": legacy_prediction_cache_artifact_count,
            "legacy_prediction_cache_bundle_count": legacy_prediction_cache_bundle_count,
            "legacy_prediction_cache_reasons": dict(
                sorted(legacy_prediction_cache_reasons.items())
            ),
            "interval_score_pathology_count": interval_score_pathology_total,
            "interval_score_pathology_bundle_count": interval_score_pathology_bundle_count,
            "state_resumed_records": sum(
                int((row.get("state") or {}).get("resumed_records") or 0)
                for row in rows
            ),
            "state_written_records": sum(
                int((row.get("state") or {}).get("written_records") or 0)
                for row in rows
            ),
            "clip_policy_support_clean_bundle_count": sum(
                1
                for row in validated_rows
                if (row.get("policies") or {})
                .get("clip_to_natural_bounds", {})
                .get("lower_below_natural_count")
                == 0
                and (row.get("policies") or {})
                .get("clip_to_natural_bounds", {})
                .get("upper_above_natural_count")
                == 0
            ),
            "can_support_all_current_bounded_support_claims": scope_complete
            and not failed_rows
            and not include_methods
            and not include_models
            and max_completed_per_bundle is None
            and legacy_prediction_cache_record_count == 0
            and interval_score_pathology_total == 0,
        },
        "claim_boundaries": [
            "This artifact validates post-handling metrics only for its selected scope.",
            "Partial validation must not be promoted to manuscript-wide bounded-support validity.",
            "Raw endpoint excursions remain visible; clipping and abstention policies are reported as separate post-handling policies.",
            "Legacy prediction-cache fallback is diagnostic only and cannot support cache-provenance completeness claims.",
            "Interval-score pathologies are retained as pathologies; affected interval-score summaries are null rather than infinite.",
        ],
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Bounded Support Post-Handling Validation",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Selected bundles: {summary['selected_bundle_count']} / {summary['available_bundle_count']}",
        f"- Method filter: `{payload.get('scope', {}).get('include_methods', [])}`",
        f"- Model filter: `{payload.get('scope', {}).get('include_models', [])}`",
        f"- Max completed rows per bundle: `{payload.get('scope', {}).get('max_completed_per_bundle')}`",
        f"- State dir: `{payload.get('scope', {}).get('state_dir')}`",
        f"- Validated bundles: {summary['validated_bundle_count']}",
        f"- Reconstructed runs: {summary['reconstructed_runs']} / {summary['completed_ledger_rows']}",
        f"- Filtered completed rows: {summary['filtered_completed_ledger_rows']} / {summary['total_completed_ledger_rows_in_selected_bundles']}",
        f"- Reconstruction failures: {summary['reconstruction_failures']}",
        f"- Legacy prediction-cache records / artifacts / bundles: {summary.get('legacy_prediction_cache_record_count')} / {summary.get('legacy_prediction_cache_artifact_count')} / {summary.get('legacy_prediction_cache_bundle_count')}",
        f"- Legacy prediction-cache reasons: `{summary.get('legacy_prediction_cache_reasons')}`",
        f"- Interval-score pathology count / bundles: {summary.get('interval_score_pathology_count')} / {summary.get('interval_score_pathology_bundle_count')}",
        f"- State resumed / written records: {summary.get('state_resumed_records')} / {summary.get('state_written_records')}",
        f"- Clip-policy clean bundles: {summary['clip_policy_support_clean_bundle_count']}",
        f"- Can support all current bounded-support claims: `{summary['can_support_all_current_bounded_support_claims']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Bundle Policy Summary",
            "",
            "| Bundle | Status | Policy | Coverage | Mean width | Interval score | Abstention | Lower < natural | Upper > natural |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["rows"]:
        for policy, stats in (row.get("policies") or {}).items():
            lines.append(
                "| "
                f"`{row['bundle_id']}` | "
                f"`{row.get('status')}` | "
                f"`{policy}` | "
                f"{stats.get('coverage')} | "
                f"{stats.get('mean_width')} | "
                f"{stats.get('interval_score')} | "
                f"{stats.get('abstention_rate')} | "
                f"{stats.get('lower_below_natural_count')} | "
                f"{stats.get('upper_above_natural_count')} |"
            )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(
        root,
        args.bundle_id,
        args.progress_every,
        include_methods=normalize_filter_values(args.include_method),
        include_models=normalize_filter_values(args.include_model),
        max_completed_per_bundle=args.max_completed_per_bundle,
        state_dir=None
        if args.state_dir is None
        else resolve(root, args.state_dir),
        reset_state=args.reset_state,
        fsync_state_every=args.fsync_state_every,
    )
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok"
                if payload["summary"]["overall_status"]
                != "bounded_support_posthandling_validation_incomplete"
                else "fail",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )
    return (
        1
        if payload["summary"]["overall_status"]
        == "bounded_support_posthandling_validation_incomplete"
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
