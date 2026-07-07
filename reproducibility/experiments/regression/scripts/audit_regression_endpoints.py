"""Reconstruct and audit regression conformal interval endpoints.

The runner stores compact metrics in ledgers, but endpoint support checks need
the original interval arrays. This script reloads prediction bundles, rebuilds
completed conformal intervals with the same runner settings, maps endpoints
back to the original target scale, and writes machine-readable plus markdown
audit artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from cpfi.regression.conformal import (
    cv_minmax_interval,
    cv_plus_interval,
    venn_abers_quantile_interval,
    venn_abers_split_fallback_interval,
)
from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from cpfi.regression.target import inverse_transform_target_with_metadata
from experiments.regression.scripts.run_regression_pilot import (
    MethodSkipped,
    PredictionBundle,
    build_interval,
    cp_method_settings,
    fit_cv_plus_predictions,
    fit_grouped_cv_plus_predictions,
    fit_residual_quantile_scores,
    load_prediction_bundle,
    prediction_artifact_dir,
)

warnings.filterwarnings(
    "ignore",
    message="X does not have valid feature names, but LGBMRegressor was fitted with feature names",
    category=UserWarning,
)


STATUS_RANK = {
    "skipped_completed": 0,
    "skipped_method": 1,
    "failed": 2,
    "completed": 3,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Regression sweep YAML config.")
    parser.add_argument("--ledger", required=True, help="Input JSONL ledger.")
    parser.add_argument("--out-dir", required=True, help="Output report directory.")
    parser.add_argument("--title", required=True, help="Markdown report title.")
    parser.add_argument(
        "--observed-min",
        type=float,
        required=True,
        help="Observed target minimum on the original scale.",
    )
    parser.add_argument(
        "--observed-max",
        type=float,
        required=True,
        help="Observed target maximum on the original scale.",
    )
    parser.add_argument(
        "--lower-floor",
        type=float,
        default=None,
        help="Optional lower support floor, for example 0 for nonnegative targets.",
    )
    parser.add_argument(
        "--upper-warning",
        type=float,
        default=None,
        help="Optional upper sanity threshold beyond the observed maximum.",
    )
    parser.add_argument(
        "--max-completed",
        type=int,
        default=None,
        help="Optional development limit on completed rows to reconstruct.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Print JSON progress every N completed ledger rows; use 0 to disable.",
    )
    parser.add_argument(
        "--include-method",
        action="append",
        default=[],
        help=(
            "Only audit this CP method. May be repeated. If set, the output is "
            "marked as partial method coverage."
        ),
    )
    parser.add_argument(
        "--exclude-method",
        action="append",
        default=[],
        help=(
            "Skip this CP method. May be repeated. If set, the output is marked "
            "as partial method coverage."
        ),
    )
    parser.add_argument(
        "--include-model",
        action="append",
        default=[],
        help=(
            "Only audit this model_id. May be repeated. If set, the output is "
            "marked as partial method/model coverage."
        ),
    )
    parser.add_argument(
        "--exclude-model",
        action="append",
        default=[],
        help=(
            "Skip this model_id. May be repeated. If set, the output is marked "
            "as partial method/model coverage."
        ),
    )
    parser.add_argument(
        "--output-prefix",
        default="endpoint_audit",
        help=(
            "Output file prefix. Defaults to endpoint_audit; use a distinct "
            "prefix for partial method-coverage audits."
        ),
    )
    parser.add_argument(
        "--allow-legacy-prediction-cache",
        action="store_true",
        help=(
            "Allow legacy prediction bundles that are present on disk but lack "
            "data/code provenance metadata. The audit records explicit legacy "
            "cache caveats when this is used."
        ),
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def canonical_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = []
    for idx, row in enumerate(rows):
        status = str(row.get("status", "missing"))
        indexed.append((str(row.get("run_id", idx)), STATUS_RANK.get(status, 1), idx, row))
    indexed.sort(key=lambda item: (item[0], item[1], item[2]))
    by_run_id: dict[str, dict[str, Any]] = {}
    for run_id, _, _, row in indexed:
        by_run_id[run_id] = row
    return list(by_run_id.values())


def normalize_filter_values(values: list[str]) -> set[str]:
    items: set[str] = set()
    for value in values:
        items.update(item.strip() for item in value.split(",") if item.strip())
    return items


def filter_completed_rows(
    completed: list[dict[str, Any]],
    *,
    include_methods: set[str],
    exclude_methods: set[str],
    include_models: set[str],
    exclude_models: set[str],
) -> list[dict[str, Any]]:
    if include_methods and exclude_methods:
        overlap = sorted(include_methods.intersection(exclude_methods))
        if overlap:
            raise ValueError(
                "include/exclude method filters overlap: " + ", ".join(overlap)
            )
    if include_models and exclude_models:
        overlap = sorted(include_models.intersection(exclude_models))
        if overlap:
            raise ValueError(
                "include/exclude model filters overlap: " + ", ".join(overlap)
            )
    filtered = []
    for row in completed:
        method = str(row.get("cp_method", "missing"))
        model = str(row.get("model_id", "missing"))
        if include_methods and method not in include_methods:
            continue
        if method in exclude_methods:
            continue
        if include_models and model not in include_models:
            continue
        if model in exclude_models:
            continue
        filtered.append(row)
    return filtered


def _finite(values: np.ndarray) -> np.ndarray:
    return values[np.isfinite(values)]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _array_digest(values: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(values, dtype=np.float64))
    return hashlib.sha256(array.view(np.uint8)).hexdigest()


def _string_array_digest(values: np.ndarray) -> str:
    encoded = "\0".join(str(value) for value in np.asarray(values, dtype=object))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_prediction_bundle_allow_legacy(
    cache_root: Path,
    artifact_id: str,
) -> tuple[PredictionBundle | None, str | None]:
    """Load strict caches first, then legacy caches with an explicit reason."""

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


def _bundle_input_fingerprint(bundle, *, include_predictions: bool) -> tuple[Any, ...]:
    parts: list[Any] = [
        bundle.target_transform,
        tuple(np.shape(bundle.X_train)),
        tuple(np.shape(bundle.X_cal)),
        tuple(np.shape(bundle.X_test)),
        _array_digest(bundle.y_train),
        _array_digest(bundle.X_train),
        _array_digest(bundle.X_cal),
        _array_digest(bundle.X_test),
    ]
    if include_predictions:
        parts.extend(
            [
                _array_digest(bundle.yhat_train),
                _array_digest(bundle.yhat_cal),
                _array_digest(bundle.yhat_test),
            ]
        )
    return tuple(parts)


def _none_max(old: float | None, values: np.ndarray) -> float | None:
    finite = _finite(values)
    if finite.size == 0:
        return old
    candidate = float(np.max(finite))
    return candidate if old is None else max(old, candidate)


def _none_min(old: float | None, values: np.ndarray) -> float | None:
    finite = _finite(values)
    if finite.size == 0:
        return old
    candidate = float(np.min(finite))
    return candidate if old is None else min(old, candidate)


def empty_method_stats() -> dict[str, Any]:
    return {
        "runs": 0,
        "intervals": 0,
        "nonfinite_lower": 0,
        "nonfinite_upper": 0,
        "crossings": 0,
        "lower_below_floor": 0,
        "lower_below_observed_min": 0,
        "upper_above_observed_max": 0,
        "upper_above_warning": 0,
        "width_above_observed_range": 0,
        "width_above_twice_observed_range": 0,
        "inverse_saturation_lower": 0,
        "inverse_saturation_upper": 0,
        "max_width": None,
        "min_lower": None,
        "max_upper": None,
    }


def add_interval_stats(
    stats: dict[str, Any],
    lower: np.ndarray,
    upper: np.ndarray,
    lower_metadata: dict[str, Any],
    upper_metadata: dict[str, Any],
    *,
    observed_min: float,
    observed_max: float,
    lower_floor: float | None,
    upper_warning: float | None,
) -> None:
    width = upper - lower
    observed_range = observed_max - observed_min
    finite_lower = np.isfinite(lower)
    finite_upper = np.isfinite(upper)
    finite_pair = finite_lower & finite_upper

    stats["runs"] += 1
    stats["intervals"] += int(lower.size)
    stats["nonfinite_lower"] += int(np.sum(~finite_lower))
    stats["nonfinite_upper"] += int(np.sum(~finite_upper))
    stats["crossings"] += int(np.sum(finite_pair & (lower > upper)))
    if lower_floor is not None:
        stats["lower_below_floor"] += int(np.sum(finite_lower & (lower < lower_floor)))
    stats["lower_below_observed_min"] += int(np.sum(finite_lower & (lower < observed_min)))
    stats["upper_above_observed_max"] += int(np.sum(finite_upper & (upper > observed_max)))
    if upper_warning is not None:
        stats["upper_above_warning"] += int(np.sum(finite_upper & (upper > upper_warning)))
    stats["width_above_observed_range"] += int(
        np.sum(finite_pair & (width > observed_range))
    )
    stats["width_above_twice_observed_range"] += int(
        np.sum(finite_pair & (width > 2.0 * observed_range))
    )
    stats["inverse_saturation_lower"] += int(
        lower_metadata.get("inverse_saturation_count", 0)
    )
    stats["inverse_saturation_upper"] += int(
        upper_metadata.get("inverse_saturation_count", 0)
    )
    stats["max_width"] = _none_max(stats["max_width"], width)
    stats["min_lower"] = _none_min(stats["min_lower"], lower)
    stats["max_upper"] = _none_max(stats["max_upper"], upper)


def build_from_row(
    row: dict[str, Any],
    config: dict[str, Any],
    prediction_cache_root: Path,
    interval_cache: dict[tuple[Any, ...], Any] | None = None,
    cache_stats: Counter | None = None,
    prediction_bundle_loader: Any | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any], dict[str, Any]]:
    artifact_id = str(row["prediction_artifact"])
    loader = load_prediction_bundle if prediction_bundle_loader is None else prediction_bundle_loader
    bundle = loader(prediction_cache_root, artifact_id)
    if bundle is None:
        raise FileNotFoundError(f"prediction bundle not found for {artifact_id}")

    cp_method = str(row["cp_method"])
    cp_method_id, cp_method_params = cp_method_settings(config, cp_method)
    alpha = float(row["alpha"])
    seed = int(row["seed"])
    model_id = str(row["model_id"])
    model_params = dict(row.get("model_params") or {})
    conformal_config = config.get("conformal", {})

    cache_key = None
    if cp_method_id == "cqr" and interval_cache is not None:
        cache_key = (
            "interval",
            "cqr",
            alpha,
            seed,
            _stable_json(cp_method_params),
            _bundle_input_fingerprint(bundle, include_predictions=False),
        )
        if cache_key in interval_cache:
            if cache_stats is not None:
                cache_stats["cqr_interval_hits"] += 1
            return interval_cache[cache_key]
        if cache_stats is not None:
            cache_stats["cqr_interval_misses"] += 1

    if cp_method_id in {"venn_abers_quantile", "venn_abers_split_fallback"}:
        qhat_key = (
            "residual_quantile_scores",
            alpha,
            seed,
            model_id,
            _stable_json(model_params),
            _bundle_input_fingerprint(bundle, include_predictions=True),
        )
        if interval_cache is not None and qhat_key in interval_cache:
            qhat_cal, qhat_test = interval_cache[qhat_key]
            if cache_stats is not None:
                cache_stats["venn_abers_qhat_hits"] += 1
        else:
            qhat_cal, qhat_test = fit_residual_quantile_scores(
                bundle.X_train,
                bundle.y_train,
                bundle.yhat_train,
                bundle.X_cal,
                bundle.X_test,
                alpha,
                seed,
            )
            if interval_cache is not None:
                interval_cache[qhat_key] = (qhat_cal, qhat_test)
            if cache_stats is not None:
                cache_stats["venn_abers_qhat_misses"] += 1

        if cp_method_id == "venn_abers_quantile":
            interval = venn_abers_quantile_interval(
                bundle.y_cal,
                bundle.yhat_cal,
                bundle.yhat_test,
                qhat_cal,
                qhat_test,
                alpha,
                m=int(conformal_config.get("venn_abers_m", 1)),
            )
        else:
            interval = venn_abers_split_fallback_interval(
                bundle.y_cal,
                bundle.yhat_cal,
                bundle.yhat_test,
                qhat_cal,
                qhat_test,
                alpha,
                m=int(conformal_config.get("venn_abers_m", 1)),
            )
        lower, lower_metadata = inverse_transform_target_with_metadata(
            interval.lower, bundle.target_transform
        )
        upper, upper_metadata = inverse_transform_target_with_metadata(
            interval.upper, bundle.target_transform
        )
        return lower, upper, lower_metadata, upper_metadata

    if cp_method_id == "cv_plus":
        cv_plus_max_train_rows = conformal_config.get("cv_plus_max_train_rows")
        if (
            cv_plus_max_train_rows is not None
            and len(bundle.y_train) > cv_plus_max_train_rows
        ):
            raise MethodSkipped(
                f"cv_plus skipped: n_train={len(bundle.y_train)} exceeds "
                f"cv_plus_max_train_rows={cv_plus_max_train_rows}"
            )
        cv_plus_folds = int(conformal_config.get("cv_plus_folds", 5))
        predictions_key = (
            "cv_plus_predictions",
            seed,
            model_id,
            _stable_json(model_params),
            cv_plus_folds,
            _bundle_input_fingerprint(bundle, include_predictions=False),
        )
        if interval_cache is not None and predictions_key in interval_cache:
            yhat_train_oof, yhat_test_by_fold, fold_ids = interval_cache[
                predictions_key
            ]
            if cache_stats is not None:
                cache_stats["cv_plus_prediction_hits"] += 1
        else:
            yhat_train_oof, yhat_test_by_fold, fold_ids = fit_cv_plus_predictions(
                model_id,
                model_params,
                bundle.X_train,
                bundle.y_train,
                bundle.X_test,
                seed,
                n_folds=cv_plus_folds,
            )
            if interval_cache is not None:
                interval_cache[predictions_key] = (
                    yhat_train_oof,
                    yhat_test_by_fold,
                    fold_ids,
                )
            if cache_stats is not None:
                cache_stats["cv_plus_prediction_misses"] += 1

        interval = cv_plus_interval(
            bundle.y_train,
            yhat_train_oof,
            yhat_test_by_fold,
            fold_ids,
            alpha,
        )
        lower, lower_metadata = inverse_transform_target_with_metadata(
            interval.lower, bundle.target_transform
        )
        upper, upper_metadata = inverse_transform_target_with_metadata(
            interval.upper, bundle.target_transform
        )
        return lower, upper, lower_metadata, upper_metadata

    if cp_method_id in {"cv_plus_grouped", "cv_minmax_grouped"}:
        cv_plus_max_train_rows = conformal_config.get("cv_plus_max_train_rows")
        if (
            cv_plus_max_train_rows is not None
            and len(bundle.y_train) > cv_plus_max_train_rows
        ):
            raise MethodSkipped(
                f"{cp_method_id} skipped: n_train={len(bundle.y_train)} exceeds "
                f"cv_plus_max_train_rows={cv_plus_max_train_rows}"
            )
        if bundle.split_groups_train is None:
            raise MethodSkipped(
                f"{cp_method_id} skipped: split_groups_train is unavailable in the "
                "prediction bundle; rebuild the bundle with a split_group_col or "
                "duplicate_cluster_split scope"
            )

        cv_plus_folds = int(conformal_config.get("cv_plus_folds", 5))
        predictions_key = (
            "grouped_cv_plus_predictions",
            seed,
            model_id,
            _stable_json(model_params),
            cv_plus_folds,
            _bundle_input_fingerprint(bundle, include_predictions=False),
            _string_array_digest(bundle.split_groups_train),
        )
        if interval_cache is not None and predictions_key in interval_cache:
            yhat_train_oof, yhat_test_by_fold, fold_ids = interval_cache[
                predictions_key
            ]
            if cache_stats is not None:
                cache_stats["grouped_cv_prediction_hits"] += 1
        else:
            yhat_train_oof, yhat_test_by_fold, fold_ids, _ = (
                fit_grouped_cv_plus_predictions(
                    model_id,
                    model_params,
                    bundle.X_train,
                    bundle.y_train,
                    bundle.X_test,
                    bundle.split_groups_train,
                    seed,
                    n_folds=cv_plus_folds,
                    method_name=cp_method_id,
                )
            )
            if interval_cache is not None:
                interval_cache[predictions_key] = (
                    yhat_train_oof,
                    yhat_test_by_fold,
                    fold_ids,
                )
            if cache_stats is not None:
                cache_stats["grouped_cv_prediction_misses"] += 1

        if cp_method_id == "cv_plus_grouped":
            interval = cv_plus_interval(
                bundle.y_train,
                yhat_train_oof,
                yhat_test_by_fold,
                fold_ids,
                alpha,
            )
        else:
            interval = cv_minmax_interval(
                bundle.y_train,
                yhat_train_oof,
                yhat_test_by_fold,
                fold_ids,
                alpha,
            )
        lower, lower_metadata = inverse_transform_target_with_metadata(
            interval.lower, bundle.target_transform
        )
        upper, upper_metadata = inverse_transform_target_with_metadata(
            interval.upper, bundle.target_transform
        )
        return lower, upper, lower_metadata, upper_metadata

    interval = build_interval(
        cp_method_id,
        alpha,
        bundle.y_cal,
        bundle.yhat_cal,
        bundle.yhat_test,
        bundle.groups_cal,
        bundle.groups_test,
        bundle.X_train,
        bundle.y_train,
        bundle.yhat_train,
        bundle.X_cal,
        bundle.X_test,
        seed,
        model_id=model_id,
        model_params=model_params,
        scale_cal=bundle.scale_cal,
        scale_test=bundle.scale_test,
        cv_plus_folds=int(conformal_config.get("cv_plus_folds", 5)),
        cv_plus_max_train_rows=conformal_config.get("cv_plus_max_train_rows"),
        jackknife_plus_max_train_rows=conformal_config.get(
            "jackknife_plus_max_train_rows"
        ),
        jackknife_after_bootstrap_n_resamples=int(
            conformal_config.get("jackknife_after_bootstrap_n_resamples", 50)
        ),
        jackknife_after_bootstrap_sample_fraction=float(
            conformal_config.get("jackknife_after_bootstrap_sample_fraction", 1.0)
        ),
        jackknife_after_bootstrap_min_oob=int(
            conformal_config.get("jackknife_after_bootstrap_min_oob", 1)
        ),
        jackknife_after_bootstrap_max_train_rows=conformal_config.get(
            "jackknife_after_bootstrap_max_train_rows"
        ),
        covariate_shift_probability_clip=float(
            conformal_config.get("covariate_shift_probability_clip", 0.01)
        ),
        covariate_shift_weight_clip=float(
            conformal_config.get("covariate_shift_weight_clip", 20.0)
        ),
        venn_abers_m=int(conformal_config.get("venn_abers_m", 1)),
        cqr_params=cp_method_params if cp_method_id == "cqr" else None,
        split_groups_train=bundle.split_groups_train,
    )
    lower, lower_metadata = inverse_transform_target_with_metadata(
        interval.lower, bundle.target_transform
    )
    upper, upper_metadata = inverse_transform_target_with_metadata(
        interval.upper, bundle.target_transform
    )
    if cache_key is not None and interval_cache is not None:
        interval_cache[cache_key] = (lower, upper, lower_metadata, upper_metadata)
    return lower, upper, lower_metadata, upper_metadata


def audit_endpoints(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    prediction_cache_root: Path,
    observed_min: float,
    observed_max: float,
    lower_floor: float | None,
    upper_warning: float | None,
    max_completed: int | None,
    progress_every: int,
    include_methods: set[str] | None = None,
    exclude_methods: set[str] | None = None,
    include_models: set[str] | None = None,
    exclude_models: set[str] | None = None,
    allow_legacy_prediction_cache: bool = False,
) -> dict[str, Any]:
    canonical = canonical_rows(rows)
    all_completed = [row for row in canonical if row.get("status") == "completed"]
    include_methods = set() if include_methods is None else set(include_methods)
    exclude_methods = set() if exclude_methods is None else set(exclude_methods)
    include_models = set() if include_models is None else set(include_models)
    exclude_models = set() if exclude_models is None else set(exclude_models)
    filtered_completed = filter_completed_rows(
        all_completed,
        include_methods=include_methods,
        exclude_methods=exclude_methods,
        include_models=include_models,
        exclude_models=exclude_models,
    )
    completed = filtered_completed
    if max_completed is not None:
        completed = completed[:max_completed]

    totals = empty_method_stats()
    method_stats: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    missing_artifacts = 0
    available_method_counts = Counter(
        str(row.get("cp_method", "missing")) for row in all_completed
    )
    filtered_method_counts = Counter(
        str(row.get("cp_method", "missing")) for row in filtered_completed
    )
    method_counts = Counter(str(row.get("cp_method", "missing")) for row in completed)
    omitted_method_counts = available_method_counts - filtered_method_counts
    full_method_coverage = (
        not include_methods
        and not exclude_methods
        and not include_models
        and not exclude_models
        and max_completed is None
        and len(completed) == len(all_completed)
    )
    interval_cache: dict[tuple[Any, ...], Any] = {}
    cache_stats: Counter = Counter()
    prediction_bundle_cache: dict[str, PredictionBundle] = {}
    prediction_bundle_legacy_reasons: dict[str, str | None] = {}
    legacy_prediction_cache_record_count = 0
    legacy_prediction_cache_artifact_reasons: dict[str, str] = {}

    def prediction_bundle_loader(
        cache_root: Path,
        artifact_id: str,
    ) -> PredictionBundle | None:
        if artifact_id in prediction_bundle_cache:
            cache_stats["prediction_bundle_cache_hits"] += 1
            legacy_reason = prediction_bundle_legacy_reasons.get(artifact_id)
            if legacy_reason:
                cache_stats["legacy_prediction_bundle_cache_hits"] += 1
            return prediction_bundle_cache[artifact_id]

        cache_stats["prediction_bundle_cache_misses"] += 1
        if allow_legacy_prediction_cache:
            bundle, legacy_reason = load_prediction_bundle_allow_legacy(
                cache_root,
                artifact_id,
            )
        else:
            bundle = load_prediction_bundle(cache_root, artifact_id)
            legacy_reason = None
        if bundle is None:
            return None

        prediction_bundle_cache[artifact_id] = bundle
        prediction_bundle_legacy_reasons[artifact_id] = legacy_reason
        if legacy_reason:
            legacy_prediction_cache_artifact_reasons[artifact_id] = legacy_reason
            cache_stats["legacy_prediction_bundle_artifact_loads"] += 1
            cache_stats[f"legacy_prediction_bundle_artifact_loads_{legacy_reason}"] += 1
        return bundle

    for index, row in enumerate(completed, start=1):
        method = str(row.get("cp_method", "missing"))
        stats = method_stats.setdefault(method, empty_method_stats())
        try:
            lower, upper, lower_metadata, upper_metadata = build_from_row(
                row,
                config,
                prediction_cache_root,
                interval_cache=interval_cache,
                cache_stats=cache_stats,
                prediction_bundle_loader=prediction_bundle_loader,
            )
        except FileNotFoundError as exc:
            missing_artifacts += 1
            failures.append(
                {
                    "run_id": row.get("run_id"),
                    "cp_method": method,
                    "model_id": row.get("model_id"),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            continue
        except MethodSkipped as exc:
            failures.append(
                {
                    "run_id": row.get("run_id"),
                    "cp_method": method,
                    "model_id": row.get("model_id"),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            continue
        except Exception as exc:  # noqa: BLE001 - audit must report all failures.
            failures.append(
                {
                    "run_id": row.get("run_id"),
                    "cp_method": method,
                    "model_id": row.get("model_id"),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            continue

        artifact_id = str(row.get("prediction_artifact"))
        if artifact_id in legacy_prediction_cache_artifact_reasons:
            legacy_prediction_cache_record_count += 1
        add_interval_stats(
            totals,
            lower,
            upper,
            lower_metadata,
            upper_metadata,
            observed_min=observed_min,
            observed_max=observed_max,
            lower_floor=lower_floor,
            upper_warning=upper_warning,
        )
        add_interval_stats(
            stats,
            lower,
            upper,
            lower_metadata,
            upper_metadata,
            observed_min=observed_min,
            observed_max=observed_max,
            lower_floor=lower_floor,
            upper_warning=upper_warning,
        )
        if progress_every > 0 and index % progress_every == 0:
            print(
                json.dumps(
                    {
                        "event": "endpoint_audit_progress",
                        "processed_completed_rows": index,
                        "total_completed_rows": len(completed),
                        "reconstructed_runs": totals["runs"],
                        "failures": len(failures),
                        "current_method": method,
                        "cache_stats": dict(sorted(cache_stats.items())),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    return {
        "audit_schema": "cpfi_regression_endpoint_audit_v2",
        "legacy_prediction_cache_enabled": allow_legacy_prediction_cache,
        "legacy_prediction_cache_record_count": legacy_prediction_cache_record_count,
        "legacy_prediction_cache_artifact_count": len(
            legacy_prediction_cache_artifact_reasons
        ),
        "legacy_prediction_cache_reasons": dict(
            sorted(Counter(legacy_prediction_cache_artifact_reasons.values()).items())
        ),
        "legacy_prediction_cache_artifacts_sample": [
            {"prediction_artifact": artifact, "reason": reason}
            for artifact, reason in sorted(
                legacy_prediction_cache_artifact_reasons.items()
            )[:25]
        ],
        "method_filter": {
            "include_methods": sorted(include_methods),
            "exclude_methods": sorted(exclude_methods),
            "include_models": sorted(include_models),
            "exclude_models": sorted(exclude_models),
            "max_completed": max_completed,
            "full_method_coverage": full_method_coverage,
        },
        "total_completed_ledger_rows": len(all_completed),
        "filtered_completed_ledger_rows": len(filtered_completed),
        "completed_ledger_rows": len(completed),
        "reconstructed_runs": totals["runs"],
        "missing_artifacts": missing_artifacts,
        "reconstruction_failures": len(failures),
        "observed_target_min": observed_min,
        "observed_target_max": observed_max,
        "lower_floor": lower_floor,
        "upper_warning": upper_warning,
        "available_completed_method_counts": dict(sorted(available_method_counts.items())),
        "filtered_completed_method_counts": dict(sorted(filtered_method_counts.items())),
        "configured_completed_method_counts": dict(sorted(method_counts.items())),
        "omitted_completed_method_counts": dict(sorted(omitted_method_counts.items())),
        "totals": totals,
        "method_summary": dict(sorted(method_stats.items())),
        "cache_stats": dict(sorted(cache_stats.items())),
        "failures": failures[:50],
        "failure_count_total": len(failures),
    }


def render_markdown(title: str, payload: dict[str, Any]) -> str:
    totals = payload["totals"]
    lower_floor = payload.get("lower_floor")
    upper_warning = payload.get("upper_warning")
    method_filter = payload.get("method_filter", {})
    lines = [
        f"# Endpoint Audit: {title}",
        "",
        f"- Full method coverage: `{method_filter.get('full_method_coverage', True)}`",
        (
            "- Method filter: "
            f"`include={method_filter.get('include_methods', [])}, "
            f"exclude={method_filter.get('exclude_methods', [])}, "
            f"include_models={method_filter.get('include_models', [])}, "
            f"exclude_models={method_filter.get('exclude_models', [])}, "
            f"max_completed={method_filter.get('max_completed')}`"
        ),
        f"- Total completed ledger rows available: {payload.get('total_completed_ledger_rows', payload['completed_ledger_rows'])}",
        f"- Filtered completed ledger rows before max limit: {payload.get('filtered_completed_ledger_rows', payload['completed_ledger_rows'])}",
        f"- Completed ledger rows checked: {payload['completed_ledger_rows']}",
        f"- Reconstructed runs: {payload['reconstructed_runs']}",
        f"- Intervals checked: {totals['intervals']}",
        f"- Scalar endpoints checked: {2 * totals['intervals']}",
        f"- Missing artifacts: {payload['missing_artifacts']}",
        f"- Reconstruction failures: {payload['reconstruction_failures']}",
        f"- Reconstruction cache stats: `{payload.get('cache_stats', {})}`",
        f"- Legacy prediction-cache enabled: `{payload.get('legacy_prediction_cache_enabled', False)}`",
        (
            "- Legacy prediction-cache records / artifacts / reasons: "
            f"{payload.get('legacy_prediction_cache_record_count', 0)} / "
            f"{payload.get('legacy_prediction_cache_artifact_count', 0)} / "
            f"`{payload.get('legacy_prediction_cache_reasons', {})}`"
        ),
        (
            "- Nonfinite lower/upper endpoints: "
            f"{totals['nonfinite_lower']} / {totals['nonfinite_upper']}"
        ),
        f"- Interval crossings: {totals['crossings']}",
    ]
    if lower_floor is not None:
        lines.append(f"- Lower endpoints below {lower_floor}: {totals['lower_below_floor']}")
    lines.extend(
        [
            (
                "- Lower endpoints below observed target minimum "
                f"{payload['observed_target_min']}: "
                f"{totals['lower_below_observed_min']}"
            ),
            (
                "- Upper endpoints above observed target maximum "
                f"{payload['observed_target_max']}: "
                f"{totals['upper_above_observed_max']}"
            ),
        ]
    )
    if upper_warning is not None:
        lines.append(
            f"- Upper endpoints above {upper_warning}: "
            f"{totals['upper_above_warning']}"
        )
    if payload.get("omitted_completed_method_counts"):
        lines.append(
            "- Omitted completed method counts: "
            f"`{payload['omitted_completed_method_counts']}`"
        )
    observed_range = payload["observed_target_max"] - payload["observed_target_min"]
    lines.extend(
        [
            (
                f"- Widths above observed target range {observed_range}: "
                f"{totals['width_above_observed_range']}"
            ),
            (
                f"- Widths above twice observed target range {2.0 * observed_range}: "
                f"{totals['width_above_twice_observed_range']}"
            ),
            "",
            "## Method Endpoint Summary",
            "",
        ]
    )
    method_rows = []
    for method, stats in payload["method_summary"].items():
        method_rows.append(
            {
                "method": f"`{method}`",
                "runs": stats["runs"],
                "intervals": stats["intervals"],
                "lower < floor": stats["lower_below_floor"],
                "lower < observed min": stats["lower_below_observed_min"],
                "upper > observed max": stats["upper_above_observed_max"],
                "upper > warning": stats["upper_above_warning"],
                "width > range": stats["width_above_observed_range"],
                "inverse saturation L/U": (
                    f"{stats['inverse_saturation_lower']} / "
                    f"{stats['inverse_saturation_upper']}"
                ),
                "max width": stats["max_width"],
                "min lower": stats["min_lower"],
                "max upper": stats["max_upper"],
            }
        )
    if method_rows:
        lines.append(pd.DataFrame(method_rows).to_markdown(index=False))
    else:
        lines.append("No reconstructed completed runs.")
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "- Intervals are raw and unclipped on the original target scale.",
            "- Endpoint flags are engineering diagnostics, not bounded-support guarantees.",
            "- Venn-Abers quantile bridge remains diagnostic-only; split fallback is an ordinary split envelope, not a Venn-Abers regression method with validated interval coverage.",
            "",
        ]
    )
    if payload["failure_count_total"]:
        lines.extend(
            [
                "## Reconstruction Failures",
                "",
                f"First {len(payload['failures'])} failures are stored in the JSON audit payload.",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    ledger_path = Path(args.ledger)
    out_dir = Path(args.out_dir)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    prediction_cache_root = Path(
        config["logging"].get(
            "prediction_cache_root",
            Path(config["logging"]["checkpoint_root"]) / "predictions",
        )
    )
    payload = audit_endpoints(
        load_jsonl(ledger_path),
        config,
        prediction_cache_root=prediction_cache_root,
        observed_min=float(args.observed_min),
        observed_max=float(args.observed_max),
        lower_floor=args.lower_floor,
        upper_warning=args.upper_warning,
        max_completed=args.max_completed,
        progress_every=int(args.progress_every),
        include_methods=normalize_filter_values(args.include_method),
        exclude_methods=normalize_filter_values(args.exclude_method),
        include_models=normalize_filter_values(args.include_model),
        exclude_models=normalize_filter_values(args.exclude_model),
        allow_legacy_prediction_cache=bool(args.allow_legacy_prediction_cache),
    )
    payload["config"] = str(config_path)
    payload["ledger"] = str(ledger_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = str(args.output_prefix)
    if not output_prefix or "/" in output_prefix or "\\" in output_prefix:
        raise ValueError(f"invalid output prefix: {output_prefix!r}")
    atomic_write_json(out_dir / f"{output_prefix}.json", payload)
    atomic_write_text(
        out_dir / f"{output_prefix}.md",
        render_markdown(args.title, payload),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "output_prefix": output_prefix,
                "full_method_coverage": payload["method_filter"][
                    "full_method_coverage"
                ],
                "completed_ledger_rows": payload["completed_ledger_rows"],
                "reconstructed_runs": payload["reconstructed_runs"],
                "reconstruction_failures": payload["reconstruction_failures"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
