"""Run real-data diagnostics for regression Venn-Abers methods.

The script keeps two method families separate:

- `venn_abers_quantile` is evaluated as an interval method on the full test set.
- `ivapd_threshold_grid` is evaluated as a predictive distribution on a
  deterministic test subset with threshold-grid CRPS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import numpy as np
import yaml

from cpfi.regression.experiment import (
    RunRecord,
    append_jsonl,
    atomic_write_json,
    atomic_write_text,
    checkpoint_run,
)
from cpfi.regression.conformal import (
    RegressionCPResult,
    split_conformal_interval,
    venn_abers_quantile_grid_interval,
    venn_abers_quantile_interval,
    venn_abers_split_fallback_envelope,
)
from cpfi.regression.metrics import compute_interval_metrics
from cpfi.regression.target import inverse_transform_target, transform_target
from cpfi.regression.venn_abers import (
    ivapd_distribution_metrics,
    ivapd_threshold_grid,
    threshold_grid_crps,
)
from experiments.regression.scripts.benchmark_ivapd_threshold_grid import point_step_cdf
from experiments.regression.scripts.run_regression_pilot import (
    DATASET_LOADER_SCHEMA,
    DATASET_LOADERS,
    build_interval,
    feature_reducer_config,
    fit_residual_quantile_scores,
    fit_or_load_prediction_bundle,
    iter_model_configs,
    load_dataset_frame,
    runtime_provenance,
    stable_run_id,
    target_transform_for_dataset,
)


BENCHMARK_ID = "venn_abers_real_data_diagnostic_v7"
DIAGNOSTIC_RUN_CONTEXT_SCHEMA = "venn_abers_real_data_diagnostic_run_context_v2"
DIAGNOSTIC_RESUME_COMPATIBILITY_SCHEMA = "venn_abers_diagnostic_resume_compatibility_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="experiments/regression/configs/venn_abers_real_data_diagnostic.yaml",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-runs", type=int, default=None)
    return parser.parse_args()


def diagnostic_result_path(checkpoint_root: Path, run_id: str) -> Path:
    return checkpoint_root / "diagnostics" / run_id[:2] / run_id / "diagnostic.json"


def json_sha256(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def diagnostic_script_fingerprint() -> dict:
    path = Path(__file__)
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        digest = None
    return {
        "path": "experiments/regression/scripts/benchmark_venn_abers_real_data.py",
        "sha256": digest,
    }


def diagnostic_run_context(
    dataset_id: str,
    model_id: str,
    model_family: str,
    model_params: dict,
    alpha: float,
    seed: int,
    config: dict,
) -> dict:
    conformal = dict(config.get("conformal", {}) or {})
    splits = dict(config.get("splits", {}) or {})
    loader_spec = dict(DATASET_LOADERS.get(dataset_id, {}) or {})
    context = {
        "schema": DIAGNOSTIC_RUN_CONTEXT_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "experiment_id": config.get("experiment_id"),
        "dataset_id": dataset_id,
        "dataset_loader_schema": DATASET_LOADER_SCHEMA,
        "dataset_loader": json_safe(loader_spec),
        "model_id": model_id,
        "model_family": model_family,
        "model_params": json_safe(model_params),
        "alpha": float(alpha),
        "seed": int(seed),
        "target_transform": target_transform_for_dataset(config, dataset_id),
        "splits": json_safe(splits),
        "feature_reducer": json_safe(feature_reducer_config(config)),
        "methods_under_diagnostic": json_safe(
            config.get("methods_under_diagnostic", {}) or {}
        ),
        "baseline_interval_methods": [
            str(method) for method in config.get("baseline_interval_methods", []) or []
        ],
        "diagnostic_conformal_settings": {
            key: json_safe(conformal.get(key))
            for key in (
                "venn_abers_m",
                "ivapd_grid_size",
                "ivapd_max_test_rows",
                "venn_abers_grid_size",
                "venn_abers_grid_max_test_rows",
                "venn_abers_m_sensitivity",
                "venn_abers_bridge_inflation_factors",
            )
            if key in conformal
        },
        "script": diagnostic_script_fingerprint(),
    }
    context["context_sha256"] = json_sha256(context)
    return context


def expected_resume_compatibility(run_payload: dict) -> dict:
    context = run_payload.get("diagnostic_run_context", {}) or {}
    return {
        "schema": DIAGNOSTIC_RESUME_COMPATIBILITY_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "run_payload_sha256": run_payload.get("run_payload_sha256"),
        "diagnostic_run_context_schema": context.get("schema"),
        "diagnostic_run_context_sha256": context.get("context_sha256"),
    }


def assert_cached_result_compatible(result: dict, expected: dict, result_path: Path) -> None:
    observed = result.get("resume_compatibility")
    if not isinstance(observed, dict):
        raise ValueError(
            "stale_incompatible Venn-Abers diagnostic cache lacks "
            f"resume_compatibility: {result_path}"
        )
    keys = (
        "schema",
        "benchmark_id",
        "run_payload_sha256",
        "diagnostic_run_context_schema",
        "diagnostic_run_context_sha256",
    )
    mismatches = [
        key for key in keys if observed.get(key) != expected.get(key)
    ]
    if mismatches:
        raise ValueError(
            "stale_incompatible Venn-Abers diagnostic cache has mismatched "
            f"resume compatibility fields {mismatches}: {result_path}"
        )


def build_threshold_grid(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    grid_size: int,
) -> np.ndarray:
    y_cal_arr = np.asarray(y_cal, dtype=float)
    yhat_cal_arr = np.asarray(yhat_cal, dtype=float)
    yhat_test_arr = np.asarray(yhat_test, dtype=float)
    if grid_size < 2:
        raise ValueError(f"grid_size must be at least 2, got {grid_size}")
    residuals = np.abs(y_cal_arr - yhat_cal_arr)
    spread = np.subtract(*np.percentile(y_cal_arr, [75, 25]))
    padding = max(float(np.quantile(residuals, 0.9)), float(spread) * 0.25, 1e-6)
    lower = min(float(np.min(y_cal_arr)), float(np.min(yhat_test_arr))) - padding
    upper = max(float(np.max(y_cal_arr)), float(np.max(yhat_test_arr))) + padding
    if not np.isfinite(lower) or not np.isfinite(upper):
        raise ValueError("threshold grid bounds are non-finite")
    if upper <= lower:
        upper = lower + 1.0
    return np.linspace(lower, upper, grid_size)


def build_residual_score_grid(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    reference_scores: Iterable[float],
    grid_size: int,
) -> np.ndarray:
    y_cal_arr = np.asarray(y_cal, dtype=float)
    yhat_cal_arr = np.asarray(yhat_cal, dtype=float)
    reference_arr = np.asarray(reference_scores, dtype=float)
    if grid_size < 2:
        raise ValueError(f"grid_size must be at least 2, got {grid_size}")
    residuals = np.abs(y_cal_arr - yhat_cal_arr)
    candidates = [float(np.max(residuals))]
    if reference_arr.size:
        candidates.append(float(np.max(np.maximum(reference_arr, 0.0))))
    upper = max(candidates) * 2.0
    if not np.isfinite(upper) or upper <= 0.0:
        upper = 1.0
    return np.linspace(0.0, upper + 1e-9, grid_size)


def select_test_indices(y_test: Iterable[float], max_rows: int) -> np.ndarray:
    y = np.asarray(y_test, dtype=float)
    if max_rows < 1:
        raise ValueError(f"max_rows must be positive, got {max_rows}")
    if len(y) <= max_rows:
        return np.arange(len(y), dtype=int)
    order = np.argsort(y, kind="mergesort")
    positions = np.linspace(0, len(y) - 1, max_rows)
    selected = order[np.unique(np.rint(positions).astype(int))]
    return np.sort(selected.astype(int))


def summarize_group_values(values: np.ndarray, groups: np.ndarray) -> tuple[dict[str, float], float | None]:
    by_group = {}
    for group in np.unique(groups):
        mask = groups == group
        by_group[str(group)] = float(np.mean(values[mask]))
    if len(by_group) < 2:
        return by_group, None
    vals = list(by_group.values())
    return by_group, float(max(vals) - min(vals))


def summarize_numeric(values: Iterable[float]) -> dict:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {
            "count": 0,
            "mean": None,
            "p10": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "min": None,
            "max": None,
        }
    return {
        "count": int(arr.size),
        "mean": float(np.mean(arr)),
        "p10": float(np.quantile(arr, 0.10)),
        "p25": float(np.quantile(arr, 0.25)),
        "p50": float(np.quantile(arr, 0.50)),
        "p75": float(np.quantile(arr, 0.75)),
        "p90": float(np.quantile(arr, 0.90)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def configured_ivar_m_values(config: dict, n_cal: int) -> list[int]:
    conformal = config.get("conformal", {})
    base_m = int(conformal.get("venn_abers_m", 1))
    requested = conformal.get("venn_abers_m_sensitivity", [base_m, 2, 4, 8, 16])
    if not isinstance(requested, list):
        requested = [requested]
    max_m = (int(n_cal) - 1) // 2
    values = set()
    if 1 <= base_m <= max_m:
        values.add(base_m)
    for value in requested:
        m = int(value)
        if 1 <= m <= max_m:
            values.add(m)
    if not values and max_m >= 1:
        values.add(1)
    return sorted(values)


def configured_bridge_inflation_factors(config: dict) -> list[float]:
    conformal = config.get("conformal", {})
    requested = conformal.get(
        "venn_abers_bridge_inflation_factors",
        [1.0, 1.5, 2.0, 2.5, 3.0],
    )
    if not isinstance(requested, list):
        requested = [requested]
    values = {1.0}
    for value in requested:
        factor = float(value)
        if factor > 0.0 and np.isfinite(factor):
            values.add(factor)
    return sorted(values)


def is_yhat_centered_method(cp_method: str) -> bool:
    return cp_method in {
        "split_abs",
        "mondrian_abs",
        "normalized_abs",
        "venn_abers_quantile",
        "venn_abers_split_fallback",
    } or cp_method.startswith("shrink_")


def split_fallback_envelope(
    bridge: RegressionCPResult,
    split: RegressionCPResult,
    yhat_test: Iterable[float],
) -> RegressionCPResult:
    """Return the calibration-only split fallback envelope around yhat."""

    return venn_abers_split_fallback_envelope(
        bridge=bridge,
        split=split,
        yhat_test=yhat_test,
    )


def compute_failure_diagnostics(
    cp_method: str,
    interval,
    y_test_transformed: Iterable[float],
    yhat_test: Iterable[float],
) -> dict:
    y_true = np.asarray(y_test_transformed, dtype=float)
    yhat = np.asarray(yhat_test, dtype=float)
    lower = np.asarray(interval.lower, dtype=float)
    upper = np.asarray(interval.upper, dtype=float)
    radii = np.asarray(interval.radii, dtype=float)
    if not (len(y_true) == len(yhat) == len(lower) == len(upper) == len(radii)):
        raise ValueError("interval diagnostics require aligned test arrays")

    below_excess = np.maximum(lower - y_true, 0.0)
    above_excess = np.maximum(y_true - upper, 0.0)
    interval_excess = np.maximum(below_excess, above_excess)
    missed = interval_excess > 0.0
    centered = None
    if is_yhat_centered_method(cp_method):
        abs_residual = np.abs(y_true - yhat)
        denom = np.maximum(radii, 1e-12)
        residual_to_radius = abs_residual / denom
        radius_excess = np.maximum(abs_residual - radii, 0.0)
        centered = {
            "centered_on_yhat": True,
            "radius_summary": summarize_numeric(radii),
            "abs_residual_summary": summarize_numeric(abs_residual),
            "residual_to_radius_summary": summarize_numeric(residual_to_radius),
            "residual_exceeds_radius_rate": float(np.mean(radius_excess > 0.0)),
            "mean_radius_excess": float(np.mean(radius_excess[radius_excess > 0.0]))
            if np.any(radius_excess > 0.0)
            else 0.0,
            "max_radius_excess": float(np.max(radius_excess)) if len(radius_excess) else 0.0,
        }

    return {
        "scale": "transformed_target",
        "method": cp_method,
        "n_test": int(len(y_true)),
        "interval_width_summary": summarize_numeric(upper - lower),
        "miss_rate": float(np.mean(missed)),
        "below_miss_rate": float(np.mean(below_excess > 0.0)),
        "above_miss_rate": float(np.mean(above_excess > 0.0)),
        "mean_miss_excess": float(np.mean(interval_excess[missed])) if np.any(missed) else 0.0,
        "max_miss_excess": float(np.max(interval_excess)) if len(interval_excess) else 0.0,
        "centered_residual_diagnostics": centered,
    }


def compute_interval_diagnostic(
    cp_method: str,
    alpha: float,
    bundle,
    seed: int,
    model_id: str,
    model_params: dict,
    config: dict,
) -> dict:
    start = time.time()
    if cp_method == "venn_abers_split_fallback":
        bridge = build_interval(
            "venn_abers_quantile",
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
            cv_plus_folds=int(config.get("conformal", {}).get("cv_plus_folds", 5)),
            jackknife_plus_max_train_rows=config.get("conformal", {}).get(
                "jackknife_plus_max_train_rows"
            ),
            venn_abers_m=int(config.get("conformal", {}).get("venn_abers_m", 1)),
        )
        split = split_conformal_interval(bundle.y_cal, bundle.yhat_cal, bundle.yhat_test, alpha)
        interval = split_fallback_envelope(bridge, split, bundle.yhat_test)
    else:
        interval = build_interval(
            cp_method,
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
            cv_plus_folds=int(config.get("conformal", {}).get("cv_plus_folds", 5)),
            jackknife_plus_max_train_rows=config.get("conformal", {}).get(
                "jackknife_plus_max_train_rows"
            ),
            venn_abers_m=int(config.get("conformal", {}).get("venn_abers_m", 1)),
        )
    y_test_transformed = transform_target(bundle.y_test, bundle.target_transform)
    lower_metric = inverse_transform_target(interval.lower, bundle.target_transform)
    upper_metric = inverse_transform_target(interval.upper, bundle.target_transform)
    metrics = compute_interval_metrics(
        y_true=bundle.y_test,
        lower=lower_metric,
        upper=upper_metric,
        alpha=alpha,
        groups=bundle.groups_test,
    )
    return {
        "method": cp_method,
        "metrics": asdict(metrics),
        "interval_seconds": time.time() - start,
        "metadata": interval.metadata,
        "failure_diagnostics": compute_failure_diagnostics(
            cp_method,
            interval,
            y_test_transformed,
            bundle.yhat_test,
        ),
    }


def configured_interval_methods(config: dict) -> tuple[str, list[str]]:
    primary = str(
        config.get("methods_under_diagnostic", {}).get(
            "interval_method",
            "venn_abers_quantile",
        )
    )
    baselines = [str(method) for method in config.get("baseline_interval_methods", [])]
    baselines = [method for method in baselines if method != primary]
    return primary, baselines


def compare_interval_methods(interval_methods: dict[str, dict], primary_method: str) -> list[dict]:
    primary = interval_methods[primary_method]["metrics"]
    primary_failure = interval_methods[primary_method]["failure_diagnostics"]
    primary_centered = primary_failure.get("centered_residual_diagnostics") or {}
    primary_radius_mean = (
        primary_centered.get("radius_summary", {}).get("mean") if primary_centered else None
    )
    rows = []
    for method, payload in interval_methods.items():
        metrics = payload["metrics"]
        failure = payload["failure_diagnostics"]
        centered = failure.get("centered_residual_diagnostics") or {}
        radius_mean = centered.get("radius_summary", {}).get("mean") if centered else None
        radius_ratio = None
        if radius_mean is not None and primary_radius_mean is not None and primary_radius_mean > 0:
            radius_ratio = float(radius_mean / primary_radius_mean)
        width_ratio = None
        if primary["mean_width"] > 0:
            width_ratio = float(metrics["mean_width"] / primary["mean_width"])
        rows.append(
            {
                "method": method,
                "coverage": metrics["coverage"],
                "coverage_gap": metrics["coverage_gap"],
                "mean_width": metrics["mean_width"],
                "interval_score": metrics["interval_score"],
                "coverage_delta_vs_primary": float(metrics["coverage"] - primary["coverage"]),
                "width_ratio_vs_primary": width_ratio,
                "miss_rate_transformed": failure["miss_rate"],
                "mean_miss_excess_transformed": failure["mean_miss_excess"],
                "mean_width_transformed": failure["interval_width_summary"]["mean"],
                "mean_radius_transformed": radius_mean,
                "radius_ratio_vs_primary": radius_ratio,
                "mean_residual_to_radius_ratio": centered.get(
                    "residual_to_radius_summary", {}
                ).get("mean")
                if centered
                else None,
                "residual_exceeds_radius_rate": centered.get("residual_exceeds_radius_rate")
                if centered
                else None,
            }
        )
    return rows


def ivapd_interval_extractions(distribution, alpha: float) -> dict[str, dict]:
    """Extract central intervals from IVAPD CDF summaries for diagnostics."""

    extractions = {}
    for source in ("lower", "midpoint", "upper"):
        lower, upper = distribution.interval(alpha=alpha, source=source)
        extractions[f"{source}_cdf"] = {
            "lower": float(lower),
            "upper": float(upper),
            "source": source,
        }
    conservative_lower = distribution.quantile(alpha / 2.0, source="upper")
    conservative_upper = distribution.quantile(1.0 - alpha / 2.0, source="lower")
    lower = min(conservative_lower, conservative_upper)
    upper = max(conservative_lower, conservative_upper)
    extractions["conservative_band"] = {
        "lower": float(lower),
        "upper": float(upper),
        "source": "upper_cdf_lower_quantile + lower_cdf_upper_quantile",
    }
    return extractions


def score_ivapd_subset(
    y_cal: np.ndarray,
    yhat_cal: np.ndarray,
    yhat_test: np.ndarray,
    y_test: np.ndarray,
    groups_test: np.ndarray,
    alpha: float,
    thresholds: np.ndarray,
    max_test_rows: int,
) -> dict:
    selected = select_test_indices(y_test, max_rows=max_test_rows)
    rows = []
    for row_idx in selected:
        distribution = ivapd_threshold_grid(
            y_cal=y_cal,
            yhat_cal=yhat_cal,
            yhat_test=float(yhat_test[row_idx]),
            thresholds=thresholds,
        )
        metrics = ivapd_distribution_metrics(
            distribution,
            y_true=float(y_test[row_idx]),
            alpha=alpha,
        )
        interval_extractions = ivapd_interval_extractions(distribution, alpha)
        baseline_cdf = point_step_cdf(thresholds, float(yhat_test[row_idx]))
        baseline_crps = threshold_grid_crps(float(y_test[row_idx]), thresholds, baseline_cdf)
        rows.append(
            {
                "test_index": int(row_idx),
                "group": str(groups_test[row_idx]),
                "y_true_transformed": float(y_test[row_idx]),
                "yhat_test_transformed": float(yhat_test[row_idx]),
                "ivapd_midpoint_crps": metrics["midpoint_crps"],
                "ivapd_lower_crps": metrics["lower_crps"],
                "ivapd_upper_crps": metrics["upper_crps"],
                "point_step_crps": baseline_crps,
                "crps_delta_vs_point_step": metrics["midpoint_crps"] - baseline_crps,
                "cdf_band_mean_width": metrics["cdf_band_mean_width"],
                "cdf_band_max_width": metrics["cdf_band_max_width"],
                "covered_by_midpoint_interval": metrics["covered_by_midpoint_interval"],
                "central_interval_lower": metrics["central_interval_lower"],
                "central_interval_upper": metrics["central_interval_upper"],
                "interval_extractions": interval_extractions,
            }
        )

    midpoint_crps = np.array([row["ivapd_midpoint_crps"] for row in rows], dtype=float)
    point_crps = np.array([row["point_step_crps"] for row in rows], dtype=float)
    band_width = np.array([row["cdf_band_mean_width"] for row in rows], dtype=float)
    covered = np.array([row["covered_by_midpoint_interval"] for row in rows], dtype=float)
    selected_groups = np.asarray([row["group"] for row in rows], dtype=str)
    crps_by_group, crps_gap = summarize_group_values(midpoint_crps, selected_groups)
    coverage_by_group, coverage_gap = summarize_group_values(covered, selected_groups)
    selected_y = np.asarray([row["y_true_transformed"] for row in rows], dtype=float)
    interval_extraction_summary = {}
    for policy in ("lower_cdf", "midpoint_cdf", "upper_cdf", "conservative_band"):
        lower = np.asarray(
            [row["interval_extractions"][policy]["lower"] for row in rows],
            dtype=float,
        )
        upper = np.asarray(
            [row["interval_extractions"][policy]["upper"] for row in rows],
            dtype=float,
        )
        metrics = compute_interval_metrics(
            y_true=selected_y,
            lower=lower,
            upper=upper,
            alpha=alpha,
            groups=selected_groups,
        )
        interval_extraction_summary[policy] = {
            **asdict(metrics),
            "mean_lower": float(np.mean(lower)),
            "mean_upper": float(np.mean(upper)),
        }

    return {
        "method": "ivapd_threshold_grid",
        "score": "threshold_grid_crps_trapezoid",
        "test_rows_scored": int(len(rows)),
        "test_rows_available": int(len(y_test)),
        "selected_test_indices": [int(value) for value in selected],
        "threshold_grid_size": int(len(thresholds)),
        "threshold_min": float(np.min(thresholds)),
        "threshold_max": float(np.max(thresholds)),
        "mean_midpoint_crps": float(np.mean(midpoint_crps)),
        "mean_point_step_crps": float(np.mean(point_crps)),
        "mean_crps_delta_vs_point_step": float(np.mean(midpoint_crps - point_crps)),
        "mean_cdf_band_width": float(np.mean(band_width)),
        "max_cdf_band_width": float(np.max([row["cdf_band_max_width"] for row in rows])),
        "midpoint_interval_coverage": float(np.mean(covered)),
        "interval_extraction_summary": interval_extraction_summary,
        "midpoint_crps_by_group": crps_by_group,
        "midpoint_crps_gap": crps_gap,
        "midpoint_interval_coverage_by_group": coverage_by_group,
        "midpoint_interval_coverage_gap": coverage_gap,
        "rows": rows,
    }


def score_venn_abers_grid_reference(
    bundle,
    alpha: float,
    seed: int,
    config: dict,
) -> dict:
    start = time.time()
    y_test_transformed = transform_target(bundle.y_test, bundle.target_transform)
    selected = select_test_indices(
        y_test_transformed,
        max_rows=int(config.get("conformal", {}).get("venn_abers_grid_max_test_rows", 8)),
    )
    qhat_cal, qhat_test = fit_residual_quantile_scores(
        bundle.X_train,
        bundle.y_train,
        bundle.yhat_train,
        bundle.X_cal,
        bundle.X_test,
        alpha,
        seed,
    )
    bridge = venn_abers_quantile_interval(
        y_cal=bundle.y_cal,
        yhat_cal=bundle.yhat_cal,
        yhat_test=bundle.yhat_test[selected],
        residual_quantile_cal=qhat_cal,
        residual_quantile_test=qhat_test[selected],
        alpha=alpha,
        m=int(config.get("conformal", {}).get("venn_abers_m", 1)),
    )
    score_grid = build_residual_score_grid(
        bundle.y_cal,
        bundle.yhat_cal,
        np.concatenate([bridge.radii, qhat_test[selected]]),
        grid_size=int(config.get("conformal", {}).get("venn_abers_grid_size", 31)),
    )
    grid = venn_abers_quantile_grid_interval(
        y_cal=bundle.y_cal,
        yhat_cal=bundle.yhat_cal,
        yhat_test=bundle.yhat_test[selected],
        residual_quantile_cal=qhat_cal,
        residual_quantile_test=qhat_test[selected],
        score_grid=score_grid,
        alpha=alpha,
    )
    bridge_metrics = compute_interval_metrics(
        y_true=y_test_transformed[selected],
        lower=bridge.lower,
        upper=bridge.upper,
        alpha=alpha,
        groups=bundle.groups_test[selected],
    )
    split = split_conformal_interval(
        bundle.y_cal,
        bundle.yhat_cal,
        bundle.yhat_test[selected],
        alpha,
    )
    split_fallback = split_fallback_envelope(bridge, split, bundle.yhat_test[selected])
    split_fallback_metrics = compute_interval_metrics(
        y_true=y_test_transformed[selected],
        lower=split_fallback.lower,
        upper=split_fallback.upper,
        alpha=alpha,
        groups=bundle.groups_test[selected],
    )
    grid_metrics = compute_interval_metrics(
        y_true=y_test_transformed[selected],
        lower=grid.lower,
        upper=grid.upper,
        alpha=alpha,
        groups=bundle.groups_test[selected],
    )
    radius_delta = grid.radii - bridge.radii
    split_fallback_delta = grid.radii - split_fallback.radii
    residuals = np.abs(y_test_transformed[selected] - bundle.yhat_test[selected])
    grid_hits_upper = np.isclose(grid.radii, score_grid[-1])
    positive_bridge = bridge.radii > 0.0
    row_grid_to_bridge = np.divide(
        grid.radii,
        bridge.radii,
        out=np.full_like(grid.radii, np.nan, dtype=float),
        where=positive_bridge,
    )
    finite_row_factors = row_grid_to_bridge[np.isfinite(row_grid_to_bridge)]
    mean_grid_radius = float(np.mean(grid.radii))
    mean_split_fallback_radius = float(np.mean(split_fallback.radii))
    split_fallback_summary = {
        "method": "venn_abers_split_fallback",
        "coverage": split_fallback_metrics.coverage,
        "mean_width": split_fallback_metrics.mean_width,
        "interval_score": split_fallback_metrics.interval_score,
        "split_radius": float(np.max(split.radii)),
        "mean_radius": mean_split_fallback_radius,
        "radius_ratio_vs_grid": mean_split_fallback_radius / mean_grid_radius
        if mean_grid_radius > 0.0
        else None,
        "grid_minus_split_fallback_radius": float(np.mean(split_fallback_delta)),
        "mean_abs_radius_delta_vs_grid": float(np.mean(np.abs(split_fallback_delta))),
        "residual_exceeds_radius_rate": float(np.mean(residuals > split_fallback.radii)),
        "split_radius_active_rate": float(np.mean(split.radii >= bridge.radii)),
        "split_fallback_radius_exceeds_grid_rate": float(
            np.mean(split_fallback.radii > grid.radii)
        ),
        "metadata": split_fallback.metadata,
    }
    inflation_sensitivity = []
    for factor in configured_bridge_inflation_factors(config):
        inflated_radii = bridge.radii * factor
        inflated_lower = bundle.yhat_test[selected] - inflated_radii
        inflated_upper = bundle.yhat_test[selected] + inflated_radii
        inflated_metrics = compute_interval_metrics(
            y_true=y_test_transformed[selected],
            lower=inflated_lower,
            upper=inflated_upper,
            alpha=alpha,
            groups=bundle.groups_test[selected],
        )
        mean_grid_radius = float(np.mean(grid.radii))
        mean_inflated_radius = float(np.mean(inflated_radii))
        inflation_sensitivity.append(
            {
                "factor": float(factor),
                "coverage": inflated_metrics.coverage,
                "mean_width": inflated_metrics.mean_width,
                "interval_score": inflated_metrics.interval_score,
                "mean_radius": mean_inflated_radius,
                "radius_ratio_vs_grid": mean_inflated_radius / mean_grid_radius
                if mean_grid_radius > 0.0
                else None,
                "grid_minus_inflated_radius": float(np.mean(grid.radii - inflated_radii)),
                "mean_abs_radius_delta_vs_grid": float(np.mean(np.abs(grid.radii - inflated_radii))),
                "residual_exceeds_radius_rate": float(np.mean(residuals > inflated_radii)),
                "inflated_radius_exceeds_grid_rate": float(np.mean(inflated_radii > grid.radii)),
            }
        )
    m_sensitivity = []
    for m_value in configured_ivar_m_values(config, n_cal=len(bundle.y_cal)):
        m_bridge = venn_abers_quantile_interval(
            y_cal=bundle.y_cal,
            yhat_cal=bundle.yhat_cal,
            yhat_test=bundle.yhat_test[selected],
            residual_quantile_cal=qhat_cal,
            residual_quantile_test=qhat_test[selected],
            alpha=alpha,
            m=m_value,
        )
        m_metrics = compute_interval_metrics(
            y_true=y_test_transformed[selected],
            lower=m_bridge.lower,
            upper=m_bridge.upper,
            alpha=alpha,
            groups=bundle.groups_test[selected],
        )
        m_delta = grid.radii - m_bridge.radii
        mean_grid_radius = float(np.mean(grid.radii))
        mean_m_radius = float(np.mean(m_bridge.radii))
        m_sensitivity.append(
            {
                "m": int(m_value),
                "coverage": m_metrics.coverage,
                "mean_width": m_metrics.mean_width,
                "interval_score": m_metrics.interval_score,
                "mean_radius": mean_m_radius,
                "radius_ratio_vs_grid": mean_m_radius / mean_grid_radius
                if mean_grid_radius > 0.0
                else None,
                "grid_minus_m_radius": float(np.mean(m_delta)),
                "mean_abs_radius_delta_vs_grid": float(np.mean(np.abs(m_delta))),
                "max_abs_radius_delta_vs_grid": float(np.max(np.abs(m_delta))),
                "residual_exceeds_radius_rate": float(np.mean(residuals > m_bridge.radii)),
            }
        )
    rows = []
    for local_idx, row_idx in enumerate(selected):
        rows.append(
            {
                "test_index": int(row_idx),
                "group": str(bundle.groups_test[row_idx]),
                "y_true_transformed": float(y_test_transformed[row_idx]),
                "yhat_test_transformed": float(bundle.yhat_test[row_idx]),
                "abs_residual": float(residuals[local_idx]),
                "residual_quantile_test": float(qhat_test[row_idx]),
                "bridge_radius": float(bridge.radii[local_idx]),
                "grid_radius": float(grid.radii[local_idx]),
                "grid_minus_bridge_radius": float(radius_delta[local_idx]),
                "bridge_covered": bool(
                    bridge.lower[local_idx]
                    <= y_test_transformed[row_idx]
                    <= bridge.upper[local_idx]
                ),
                "grid_covered": bool(
                    grid.lower[local_idx] <= y_test_transformed[row_idx] <= grid.upper[local_idx]
                ),
                "grid_accepted_count": int(grid.metadata["accepted_counts"][local_idx]),
                "grid_rejected_count": int(grid.metadata["rejected_counts"][local_idx]),
                "grid_hit_upper": bool(grid_hits_upper[local_idx]),
            }
        )

    return {
        "method_under_test": "venn_abers_quantile",
        "reference_method": "venn_abers_quantile_grid",
        "scale": "transformed_target",
        "test_rows_scored": int(len(selected)),
        "test_rows_available": int(len(y_test_transformed)),
        "selected_test_indices": [int(value) for value in selected],
        "score_grid_size": int(len(score_grid)),
        "score_grid_min": float(np.min(score_grid)),
        "score_grid_max": float(np.max(score_grid)),
        "bridge_mean_radius": float(np.mean(bridge.radii)),
        "grid_mean_radius": float(np.mean(grid.radii)),
        "mean_grid_minus_bridge_radius": float(np.mean(radius_delta)),
        "mean_abs_radius_delta": float(np.mean(np.abs(radius_delta))),
        "max_abs_radius_delta": float(np.max(np.abs(radius_delta))),
        "grid_radius_ratio_vs_bridge": float(np.mean(grid.radii) / np.mean(bridge.radii))
        if float(np.mean(bridge.radii)) > 0.0
        else None,
        "grid_to_bridge_row_factor_summary": summarize_numeric(finite_row_factors)
        if len(finite_row_factors) > 0
        else None,
        "grid_hit_upper_rate": float(np.mean(grid_hits_upper)),
        "bridge_metrics": asdict(bridge_metrics),
        "split_fallback_metrics": asdict(split_fallback_metrics),
        "grid_metrics": asdict(grid_metrics),
        "bridge_metadata": bridge.metadata,
        "split_fallback_summary": split_fallback_summary,
        "grid_metadata": {
            key: value
            for key, value in grid.metadata.items()
            if key != "calibrated_grid_by_test"
        },
        "bridge_inflation_sensitivity": inflation_sensitivity,
        "ivar_m_sensitivity": m_sensitivity,
        "rows": rows,
        "seconds": time.time() - start,
    }


def run_payload(
    dataset_id: str,
    model_id: str,
    model_family: str,
    model_params: dict,
    alpha: float,
    seed: int,
    config: dict,
) -> dict:
    payload = {
        "schema": "venn_abers_real_data_diagnostic_run_payload_v2",
        "benchmark_id": BENCHMARK_ID,
        "dataset_id": dataset_id,
        "model_id": model_id,
        "model_family": model_family,
        "model_params": model_params,
        "alpha": float(alpha),
        "seed": int(seed),
        "diagnostic_run_context": diagnostic_run_context(
            dataset_id=dataset_id,
            model_id=model_id,
            model_family=model_family,
            model_params=model_params,
            alpha=alpha,
            seed=seed,
            config=config,
        ),
    }
    payload["run_payload_sha256"] = json_sha256(payload)
    return payload


def run_one_diagnostic(
    dataset_id: str,
    model_id: str,
    model_family: str,
    model_params: dict,
    alpha: float,
    seed: int,
    config: dict,
    checkpoint_root: Path,
    prediction_cache_root: Path,
    force: bool,
    dataset_cache: dict,
) -> dict:
    payload = run_payload(dataset_id, model_id, model_family, model_params, alpha, seed, config)
    expected_compatibility = expected_resume_compatibility(payload)
    run_id = stable_run_id(payload)
    result_path = diagnostic_result_path(checkpoint_root, run_id)
    if result_path.exists() and not force:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        assert_cached_result_compatible(result, expected_compatibility, result_path)
        result["status"] = "loaded_completed"
        return result

    if dataset_id not in dataset_cache:
        dataset_cache[dataset_id] = load_dataset_frame(dataset_id)
    df, target, group_col = dataset_cache[dataset_id]

    start = time.time()
    bundle = fit_or_load_prediction_bundle(
        dataset_id=dataset_id,
        df=df,
        target=target,
        group_col=group_col,
        model_id=model_id,
        model_family=model_family,
        model_params=model_params,
        seed=seed,
        config=config,
        cache_root=prediction_cache_root,
        force=force,
    )
    y_test_transformed = transform_target(bundle.y_test, bundle.target_transform)
    primary_interval_method, baseline_interval_methods = configured_interval_methods(config)
    interval_methods = {}
    for cp_method in [primary_interval_method, *baseline_interval_methods]:
        interval_methods[cp_method] = compute_interval_diagnostic(
            cp_method=cp_method,
            alpha=alpha,
            bundle=bundle,
            seed=seed,
            model_id=model_id,
            model_params=model_params,
            config=config,
        )
    primary_interval_metrics = interval_methods[primary_interval_method]["metrics"]
    interval_comparison = compare_interval_methods(interval_methods, primary_interval_method)
    thresholds = build_threshold_grid(
        y_cal=bundle.y_cal,
        yhat_cal=bundle.yhat_cal,
        yhat_test=bundle.yhat_test,
        grid_size=int(config.get("conformal", {}).get("ivapd_grid_size", 41)),
    )
    ivapd_metrics = score_ivapd_subset(
        y_cal=bundle.y_cal,
        yhat_cal=bundle.yhat_cal,
        yhat_test=bundle.yhat_test,
        y_test=y_test_transformed,
        groups_test=bundle.groups_test,
        alpha=alpha,
        thresholds=thresholds,
        max_test_rows=int(config.get("conformal", {}).get("ivapd_max_test_rows", 25)),
    )
    grid_reference_metrics = score_venn_abers_grid_reference(
        bundle=bundle,
        alpha=alpha,
        seed=seed,
        config=config,
    )
    seconds = time.time() - start
    result = {
        "status": "completed",
        "run_id": run_id,
        "run_payload": payload,
        "resume_compatibility": {
            **expected_compatibility,
            "prediction_artifact": bundle.artifact_id,
            "prediction_cache_status": bundle.cache_status,
            "runtime_provenance": runtime_provenance(),
        },
        "benchmark_id": BENCHMARK_ID,
        "dataset_id": dataset_id,
        "target": target,
        "group_col": group_col,
        "model_id": model_id,
        "model_family": model_family,
        "model_params": model_params,
        "alpha": float(alpha),
        "seed": int(seed),
        "target_transform": bundle.target_transform,
        "prediction_artifact": bundle.artifact_id,
        "prediction_cache_status": bundle.cache_status,
        "fit_seconds": bundle.fit_seconds,
        "diagnostic_seconds": seconds,
        "primary_interval_method": primary_interval_method,
        "baseline_interval_methods": baseline_interval_methods,
        "interval_methods": interval_methods,
        "interval_method_comparison": interval_comparison,
        "venn_abers_quantile_interval": interval_methods["venn_abers_quantile"]["metrics"],
        "ivapd_threshold_grid": ivapd_metrics,
        "venn_abers_quantile_grid_reference": grid_reference_metrics,
        "artifact_paths": {
            **bundle.artifact_paths,
            "diagnostic": str(result_path),
        },
    }
    atomic_write_json(result_path, result)
    checkpoint_run(
        checkpoint_root,
        RunRecord(
            run_id=run_id,
            dataset_id=dataset_id,
            model_id=model_id,
            cp_method="venn_abers_real_data_diagnostic",
            split_seed=seed,
            alpha=alpha,
            status="completed",
            artifact_paths=result["artifact_paths"],
            metrics={
                "venn_abers_coverage": primary_interval_metrics["coverage"],
                "venn_abers_mean_width": primary_interval_metrics["mean_width"],
                "ivapd_mean_midpoint_crps": ivapd_metrics["mean_midpoint_crps"],
                "ivapd_mean_crps_delta_vs_point_step": ivapd_metrics[
                    "mean_crps_delta_vs_point_step"
                ],
                "va_grid_mean_radius_delta": grid_reference_metrics[
                    "mean_grid_minus_bridge_radius"
                ],
                "va_grid_radius_ratio_vs_bridge": grid_reference_metrics[
                    "grid_radius_ratio_vs_bridge"
                ],
            },
            notes=(
                f"family={model_family}; params={json.dumps(model_params, sort_keys=True)}; "
                f"prediction_artifact={bundle.artifact_id}; cache={bundle.cache_status}; "
                f"ivapd_rows={ivapd_metrics['test_rows_scored']}; "
                f"grid_reference_rows={grid_reference_metrics['test_rows_scored']}"
            ),
        ),
    )
    return result


def iter_diagnostic_runs(config: dict) -> Iterable[tuple]:
    for dataset_id in config["datasets"]:
        for seed in config["random_seeds"]:
            for model_id, family, params in iter_model_configs(config):
                for alpha in config["alphas"]:
                    yield dataset_id, model_id, family, params, float(alpha), int(seed)


def ledger_row(result: dict) -> dict:
    interval = result["venn_abers_quantile_interval"]
    ivapd = result["ivapd_threshold_grid"]
    grid_reference = result["venn_abers_quantile_grid_reference"]
    baseline_coverages = {
        method: payload["metrics"]["coverage"]
        for method, payload in result.get("interval_methods", {}).items()
        if method != result.get("primary_interval_method")
    }
    baseline_widths = {
        method: payload["metrics"]["mean_width"]
        for method, payload in result.get("interval_methods", {}).items()
        if method != result.get("primary_interval_method")
    }
    return {
        "status": result["status"],
        "run_id": result["run_id"],
        "benchmark_id": result["benchmark_id"],
        "dataset_id": result["dataset_id"],
        "model_id": result["model_id"],
        "model_family": result["model_family"],
        "model_params": result["model_params"],
        "alpha": result["alpha"],
        "seed": result["seed"],
        "target_transform": result["target_transform"],
        "prediction_artifact": result["prediction_artifact"],
        "prediction_cache_status": result["prediction_cache_status"],
        "venn_abers_coverage": interval["coverage"],
        "venn_abers_coverage_gap": interval["coverage_gap"],
        "venn_abers_mean_width": interval["mean_width"],
        "venn_abers_interval_score": interval["interval_score"],
        "baseline_interval_coverages": baseline_coverages,
        "baseline_interval_widths": baseline_widths,
        "ivapd_test_rows_scored": ivapd["test_rows_scored"],
        "ivapd_mean_midpoint_crps": ivapd["mean_midpoint_crps"],
        "ivapd_mean_point_step_crps": ivapd["mean_point_step_crps"],
        "ivapd_mean_crps_delta_vs_point_step": ivapd["mean_crps_delta_vs_point_step"],
        "ivapd_mean_cdf_band_width": ivapd["mean_cdf_band_width"],
        "ivapd_midpoint_crps_gap": ivapd["midpoint_crps_gap"],
        "va_grid_reference_rows_scored": grid_reference["test_rows_scored"],
        "va_grid_mean_radius_delta": grid_reference["mean_grid_minus_bridge_radius"],
        "va_grid_radius_ratio_vs_bridge": grid_reference["grid_radius_ratio_vs_bridge"],
        "va_grid_bridge_coverage_subset": grid_reference["bridge_metrics"]["coverage"],
        "va_grid_reference_coverage_subset": grid_reference["grid_metrics"]["coverage"],
        "va_grid_split_fallback_summary": grid_reference["split_fallback_summary"],
        "va_grid_bridge_inflation_sensitivity": grid_reference[
            "bridge_inflation_sensitivity"
        ],
        "va_grid_ivar_m_sensitivity": grid_reference["ivar_m_sensitivity"],
        "diagnostic_seconds": result["diagnostic_seconds"],
    }


def summarize_results(results: list[dict]) -> dict:
    completed = [result for result in results if result["status"] in {"completed", "loaded_completed"}]
    if not completed:
        return {"run_count": 0}
    interval_coverage = [row["venn_abers_quantile_interval"]["coverage"] for row in completed]
    interval_width = [row["venn_abers_quantile_interval"]["mean_width"] for row in completed]
    ivapd_crps = [row["ivapd_threshold_grid"]["mean_midpoint_crps"] for row in completed]
    point_crps = [row["ivapd_threshold_grid"]["mean_point_step_crps"] for row in completed]
    delta = [row["ivapd_threshold_grid"]["mean_crps_delta_vs_point_step"] for row in completed]
    ivapd_interval_rows: dict[str, list[dict]] = {}
    for row in completed:
        for policy, payload in row["ivapd_threshold_grid"].get(
            "interval_extraction_summary",
            {},
        ).items():
            ivapd_interval_rows.setdefault(policy, []).append(payload)
    ivapd_interval_extraction_summary = {}
    for policy, rows in sorted(ivapd_interval_rows.items()):
        ivapd_interval_extraction_summary[policy] = {
            "run_count": int(len(rows)),
            "mean_coverage": float(np.mean([row["coverage"] for row in rows])),
            "mean_coverage_gap": None
            if any(row["coverage_gap"] is None for row in rows)
            else float(np.mean([row["coverage_gap"] for row in rows])),
            "mean_width": float(np.mean([row["mean_width"] for row in rows])),
            "mean_interval_score": float(np.mean([row["interval_score"] for row in rows])),
            "mean_lower_miss_rate": float(np.mean([row["lower_miss_rate"] for row in rows])),
            "mean_upper_miss_rate": float(np.mean([row["upper_miss_rate"] for row in rows])),
            "mean_lower": float(np.mean([row["mean_lower"] for row in rows])),
            "mean_upper": float(np.mean([row["mean_upper"] for row in rows])),
        }
    grid_references = [row["venn_abers_quantile_grid_reference"] for row in completed]
    split_fallback_rows = [row["split_fallback_summary"] for row in grid_references]
    method_rows: dict[str, list[dict]] = {}
    for row in completed:
        for comparison in row.get("interval_method_comparison", []):
            method_rows.setdefault(comparison["method"], []).append(comparison)
    interval_method_summary = {}
    for method, rows in sorted(method_rows.items()):
        interval_method_summary[method] = {
            "mean_coverage": float(np.mean([row["coverage"] for row in rows])),
            "mean_coverage_gap": None
            if any(row["coverage_gap"] is None for row in rows)
            else float(np.mean([row["coverage_gap"] for row in rows])),
            "mean_width": float(np.mean([row["mean_width"] for row in rows])),
            "mean_interval_score": float(np.mean([row["interval_score"] for row in rows])),
            "mean_coverage_delta_vs_primary": float(
                np.mean([row["coverage_delta_vs_primary"] for row in rows])
            ),
            "mean_width_ratio_vs_primary": None
            if any(row["width_ratio_vs_primary"] is None for row in rows)
            else float(np.mean([row["width_ratio_vs_primary"] for row in rows])),
            "mean_miss_rate_transformed": float(
                np.mean([row["miss_rate_transformed"] for row in rows])
            ),
            "mean_miss_excess_transformed": float(
                np.mean([row["mean_miss_excess_transformed"] for row in rows])
            ),
            "mean_width_transformed": float(
                np.mean([row["mean_width_transformed"] for row in rows])
            ),
            "mean_radius_transformed": None
            if any(row["mean_radius_transformed"] is None for row in rows)
            else float(np.mean([row["mean_radius_transformed"] for row in rows])),
            "mean_radius_ratio_vs_primary": None
            if any(row["radius_ratio_vs_primary"] is None for row in rows)
            else float(np.mean([row["radius_ratio_vs_primary"] for row in rows])),
            "mean_residual_to_radius_ratio": None
            if any(row["mean_residual_to_radius_ratio"] is None for row in rows)
            else float(np.mean([row["mean_residual_to_radius_ratio"] for row in rows])),
            "mean_residual_exceeds_radius_rate": None
            if any(row["residual_exceeds_radius_rate"] is None for row in rows)
            else float(np.mean([row["residual_exceeds_radius_rate"] for row in rows])),
        }
    m_rows_by_value: dict[int, list[dict]] = {}
    for reference in grid_references:
        for row in reference.get("ivar_m_sensitivity", []):
            m_rows_by_value.setdefault(int(row["m"]), []).append(row)
    ivar_m_sensitivity_summary = {}
    for m_value, rows in sorted(m_rows_by_value.items()):
        ivar_m_sensitivity_summary[str(m_value)] = {
            "run_count": int(len(rows)),
            "mean_coverage": float(np.mean([row["coverage"] for row in rows])),
            "mean_width": float(np.mean([row["mean_width"] for row in rows])),
            "mean_interval_score": float(np.mean([row["interval_score"] for row in rows])),
            "mean_radius": float(np.mean([row["mean_radius"] for row in rows])),
            "mean_radius_ratio_vs_grid": None
            if any(row["radius_ratio_vs_grid"] is None for row in rows)
            else float(np.mean([row["radius_ratio_vs_grid"] for row in rows])),
            "mean_grid_minus_m_radius": float(
                np.mean([row["grid_minus_m_radius"] for row in rows])
            ),
            "mean_abs_radius_delta_vs_grid": float(
                np.mean([row["mean_abs_radius_delta_vs_grid"] for row in rows])
            ),
            "max_abs_radius_delta_vs_grid": float(
                np.max([row["max_abs_radius_delta_vs_grid"] for row in rows])
            ),
            "mean_residual_exceeds_radius_rate": float(
                np.mean([row["residual_exceeds_radius_rate"] for row in rows])
            ),
        }
    inflation_rows_by_factor: dict[float, list[dict]] = {}
    for reference in grid_references:
        for row in reference.get("bridge_inflation_sensitivity", []):
            inflation_rows_by_factor.setdefault(float(row["factor"]), []).append(row)
    bridge_inflation_sensitivity_summary = {}
    for factor, rows in sorted(inflation_rows_by_factor.items()):
        key = f"{factor:g}"
        bridge_inflation_sensitivity_summary[key] = {
            "run_count": int(len(rows)),
            "mean_coverage": float(np.mean([row["coverage"] for row in rows])),
            "mean_width": float(np.mean([row["mean_width"] for row in rows])),
            "mean_interval_score": float(np.mean([row["interval_score"] for row in rows])),
            "mean_radius": float(np.mean([row["mean_radius"] for row in rows])),
            "mean_radius_ratio_vs_grid": None
            if any(row["radius_ratio_vs_grid"] is None for row in rows)
            else float(np.mean([row["radius_ratio_vs_grid"] for row in rows])),
            "mean_grid_minus_inflated_radius": float(
                np.mean([row["grid_minus_inflated_radius"] for row in rows])
            ),
            "mean_abs_radius_delta_vs_grid": float(
                np.mean([row["mean_abs_radius_delta_vs_grid"] for row in rows])
            ),
            "mean_residual_exceeds_radius_rate": float(
                np.mean([row["residual_exceeds_radius_rate"] for row in rows])
            ),
            "mean_inflated_radius_exceeds_grid_rate": float(
                np.mean([row["inflated_radius_exceeds_grid_rate"] for row in rows])
            ),
        }
    row_factor_summaries = [
        row["grid_to_bridge_row_factor_summary"]
        for row in grid_references
        if row.get("grid_to_bridge_row_factor_summary") is not None
    ]
    split_fallback_summary = {
        "run_count": int(len(split_fallback_rows)),
        "mean_coverage": float(np.mean([row["coverage"] for row in split_fallback_rows])),
        "mean_width": float(np.mean([row["mean_width"] for row in split_fallback_rows])),
        "mean_interval_score": float(
            np.mean([row["interval_score"] for row in split_fallback_rows])
        ),
        "mean_radius": float(np.mean([row["mean_radius"] for row in split_fallback_rows])),
        "mean_split_radius": float(np.mean([row["split_radius"] for row in split_fallback_rows])),
        "mean_radius_ratio_vs_grid": None
        if any(row["radius_ratio_vs_grid"] is None for row in split_fallback_rows)
        else float(np.mean([row["radius_ratio_vs_grid"] for row in split_fallback_rows])),
        "mean_grid_minus_split_fallback_radius": float(
            np.mean([row["grid_minus_split_fallback_radius"] for row in split_fallback_rows])
        ),
        "mean_abs_radius_delta_vs_grid": float(
            np.mean([row["mean_abs_radius_delta_vs_grid"] for row in split_fallback_rows])
        ),
        "mean_residual_exceeds_radius_rate": float(
            np.mean([row["residual_exceeds_radius_rate"] for row in split_fallback_rows])
        ),
        "mean_split_radius_active_rate": float(
            np.mean([row["split_radius_active_rate"] for row in split_fallback_rows])
        ),
        "mean_split_fallback_radius_exceeds_grid_rate": float(
            np.mean([row["split_fallback_radius_exceeds_grid_rate"] for row in split_fallback_rows])
        ),
    }
    return {
        "run_count": int(len(completed)),
        "dataset_count": int(len({row["dataset_id"] for row in completed})),
        "mean_venn_abers_coverage": float(np.mean(interval_coverage)),
        "mean_venn_abers_width": float(np.mean(interval_width)),
        "mean_ivapd_midpoint_crps": float(np.mean(ivapd_crps)),
        "mean_point_step_crps": float(np.mean(point_crps)),
        "mean_ivapd_crps_delta_vs_point_step": float(np.mean(delta)),
        "ivapd_interval_extraction_summary": ivapd_interval_extraction_summary,
        "total_ivapd_rows_scored": int(
            sum(row["ivapd_threshold_grid"]["test_rows_scored"] for row in completed)
        ),
        "total_va_grid_reference_rows_scored": int(
            sum(row["test_rows_scored"] for row in grid_references)
        ),
        "mean_va_grid_bridge_subset_coverage": float(
            np.mean([row["bridge_metrics"]["coverage"] for row in grid_references])
        ),
        "mean_va_grid_reference_subset_coverage": float(
            np.mean([row["grid_metrics"]["coverage"] for row in grid_references])
        ),
        "mean_va_grid_bridge_radius": float(
            np.mean([row["bridge_mean_radius"] for row in grid_references])
        ),
        "mean_va_grid_reference_radius": float(
            np.mean([row["grid_mean_radius"] for row in grid_references])
        ),
        "mean_va_grid_minus_bridge_radius": float(
            np.mean([row["mean_grid_minus_bridge_radius"] for row in grid_references])
        ),
        "mean_va_grid_abs_radius_delta": float(
            np.mean([row["mean_abs_radius_delta"] for row in grid_references])
        ),
        "max_va_grid_abs_radius_delta": float(
            np.max([row["max_abs_radius_delta"] for row in grid_references])
        ),
        "mean_va_grid_radius_ratio_vs_bridge": float(
            np.mean([row["grid_radius_ratio_vs_bridge"] for row in grid_references])
        ),
        "mean_va_grid_hit_upper_rate": float(
            np.mean([row["grid_hit_upper_rate"] for row in grid_references])
        ),
        "mean_va_grid_to_bridge_row_factor_mean": float(
            np.mean([row["mean"] for row in row_factor_summaries])
        )
        if row_factor_summaries
        else None,
        "mean_va_grid_to_bridge_row_factor_p90": float(
            np.mean([row["p90"] for row in row_factor_summaries])
        )
        if row_factor_summaries
        else None,
        "interval_method_summary": interval_method_summary,
        "split_fallback_grid_summary": split_fallback_summary,
        "bridge_inflation_sensitivity_summary": bridge_inflation_sensitivity_summary,
        "ivar_m_sensitivity_summary": ivar_m_sensitivity_summary,
    }


def render_markdown(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# Venn-Abers Real-Data Diagnostic",
        "",
        "This report evaluates `venn_abers_quantile` as an interval method on the "
        "full test split and `ivapd_threshold_grid` as a predictive-distribution "
        "diagnostic on a deterministic test subset. IVAPD rows are distribution "
        "scores, not conformal interval ledger rows.",
        "",
        "## Summary",
        "",
        f"- Runs: {summary.get('run_count', 0)}",
        f"- Datasets: {summary.get('dataset_count', 0)}",
        f"- Mean Venn-Abers interval coverage: {summary.get('mean_venn_abers_coverage', 0.0):.6f}",
        f"- Mean Venn-Abers interval width: {summary.get('mean_venn_abers_width', 0.0):.6f}",
        f"- Mean IVAPD midpoint grid-CRPS: {summary.get('mean_ivapd_midpoint_crps', 0.0):.6f}",
        f"- Mean point-step grid-CRPS: {summary.get('mean_point_step_crps', 0.0):.6f}",
        f"- Mean IVAPD CRPS delta vs point-step: {summary.get('mean_ivapd_crps_delta_vs_point_step', 0.0):.6f}",
        f"- IVAPD rows scored: {summary.get('total_ivapd_rows_scored', 0)}",
        f"- VA grid-reference rows scored: {summary.get('total_va_grid_reference_rows_scored', 0)}",
        f"- Mean VA grid radius ratio vs bridge: {summary.get('mean_va_grid_radius_ratio_vs_bridge', 0.0):.6f}",
        f"- Mean VA grid minus bridge radius: {summary.get('mean_va_grid_minus_bridge_radius', 0.0):.6f}",
        "",
        "## Mean Interval Method Comparison",
        "",
        "| method | coverage | coverage_delta_vs_va | width | width_ratio_vs_va | interval_score |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, row in summary.get("interval_method_summary", {}).items():
        width_ratio = row["mean_width_ratio_vs_primary"]
        lines.append(
            "| {method} | {coverage:.6f} | {coverage_delta:.6f} | {width:.6f} | "
            "{width_ratio} | {interval_score:.6f} |".format(
                method=method,
                coverage=row["mean_coverage"],
                coverage_delta=row["mean_coverage_delta_vs_primary"],
                width=row["mean_width"],
                width_ratio="NA" if width_ratio is None else f"{width_ratio:.6f}",
                interval_score=row["mean_interval_score"],
            )
        )
    lines.extend(
        [
            "",
            "## IVAPD Interval Extraction Diagnostics",
            "",
            "These rows convert the IVAPD threshold-grid CDF bands into central "
            "intervals on the deterministic IVAPD subset. `conservative_band` uses "
            "the upper CDF for the lower quantile and the lower CDF for the upper "
            "quantile.",
            "",
            "| policy | coverage | coverage_gap | width | interval_score | lower_miss | upper_miss | mean_lower | mean_upper |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for policy, row in summary.get("ivapd_interval_extraction_summary", {}).items():
        coverage_gap = row["mean_coverage_gap"]
        lines.append(
            "| {policy} | {coverage:.6f} | {gap} | {width:.6f} | {score:.6f} | "
            "{lower_miss:.6f} | {upper_miss:.6f} | {mean_lower:.6f} | "
            "{mean_upper:.6f} |".format(
                policy=policy,
                coverage=row["mean_coverage"],
                gap="NA" if coverage_gap is None else f"{coverage_gap:.6f}",
                width=row["mean_width"],
                score=row["mean_interval_score"],
                lower_miss=row["mean_lower_miss_rate"],
                upper_miss=row["mean_upper_miss_rate"],
                mean_lower=row["mean_lower"],
                mean_upper=row["mean_upper"],
            )
        )
    lines.extend(
        [
            "",
            "## Mean Failure-Mode Diagnostics",
            "",
            "These diagnostics are computed on the transformed target scale. Radius columns "
            "are only defined for intervals centered on the base point prediction; CQR "
            "is intentionally reported as `NA` for those columns.",
            "",
            "| method | miss_rate | mean_excess | width_t | radius_t | radius_ratio_vs_va | residual/radius | residual>radius |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for method, row in summary.get("interval_method_summary", {}).items():
        radius = row["mean_radius_transformed"]
        radius_ratio = row["mean_radius_ratio_vs_primary"]
        residual_ratio = row["mean_residual_to_radius_ratio"]
        exceeds = row["mean_residual_exceeds_radius_rate"]
        lines.append(
            "| {method} | {miss_rate:.6f} | {excess:.6f} | {width:.6f} | "
            "{radius} | {radius_ratio} | {residual_ratio} | {exceeds} |".format(
                method=method,
                miss_rate=row["mean_miss_rate_transformed"],
                excess=row["mean_miss_excess_transformed"],
                width=row["mean_width_transformed"],
                radius="NA" if radius is None else f"{radius:.6f}",
                radius_ratio="NA" if radius_ratio is None else f"{radius_ratio:.6f}",
                residual_ratio="NA" if residual_ratio is None else f"{residual_ratio:.6f}",
                exceeds="NA" if exceeds is None else f"{exceeds:.6f}",
            )
        )
    lines.extend(
        [
            "",
            "## Venn-Abers Bridge-vs-Grid Reference",
            "",
            "This exact candidate-grid check is intentionally restricted to a deterministic "
            "test subset because it refits the quantile calibration across every residual "
            "score candidate. Metrics are on the transformed target scale.",
            "",
            "| metric | value |",
            "|---|---:|",
            f"| rows_scored | {summary.get('total_va_grid_reference_rows_scored', 0)} |",
            f"| bridge_subset_coverage | {summary.get('mean_va_grid_bridge_subset_coverage', 0.0):.6f} |",
            f"| grid_reference_subset_coverage | {summary.get('mean_va_grid_reference_subset_coverage', 0.0):.6f} |",
            f"| bridge_mean_radius | {summary.get('mean_va_grid_bridge_radius', 0.0):.6f} |",
            f"| grid_reference_mean_radius | {summary.get('mean_va_grid_reference_radius', 0.0):.6f} |",
            f"| grid_minus_bridge_radius | {summary.get('mean_va_grid_minus_bridge_radius', 0.0):.6f} |",
            f"| grid_radius_ratio_vs_bridge | {summary.get('mean_va_grid_radius_ratio_vs_bridge', 0.0):.6f} |",
            f"| row_grid_to_bridge_factor_mean | {summary.get('mean_va_grid_to_bridge_row_factor_mean', 0.0):.6f} |",
            f"| row_grid_to_bridge_factor_p90 | {summary.get('mean_va_grid_to_bridge_row_factor_p90', 0.0):.6f} |",
            f"| max_abs_radius_delta | {summary.get('max_va_grid_abs_radius_delta', 0.0):.6f} |",
            f"| grid_hit_upper_rate | {summary.get('mean_va_grid_hit_upper_rate', 0.0):.6f} |",
            "",
            "## Per-Run Bridge-vs-Grid Reference",
            "",
            "| dataset | model | rows | bridge_cov | grid_cov | bridge_radius | grid_radius | grid_minus_bridge | grid_ratio | hit_upper |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for result in payload["results"]:
        row = result["venn_abers_quantile_grid_reference"]
        ratio = row["grid_radius_ratio_vs_bridge"]
        lines.append(
            "| {dataset_id} | {model_id} | {rows} | {bridge_cov:.6f} | {grid_cov:.6f} | "
            "{bridge_radius:.6f} | {grid_radius:.6f} | {delta:.6f} | {ratio} | "
            "{hit_upper:.6f} |".format(
                dataset_id=result["dataset_id"],
                model_id=result["model_id"],
                rows=row["test_rows_scored"],
                bridge_cov=row["bridge_metrics"]["coverage"],
                grid_cov=row["grid_metrics"]["coverage"],
                bridge_radius=row["bridge_mean_radius"],
                grid_radius=row["grid_mean_radius"],
                delta=row["mean_grid_minus_bridge_radius"],
                ratio="NA" if ratio is None else f"{ratio:.6f}",
                hit_upper=row["grid_hit_upper_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Calibration-Only Split Fallback Against Grid Reference",
            "",
            "`venn_abers_split_fallback` uses the fast Venn-Abers bridge radius unless "
            "the ordinary split-conformal calibration radius is larger. This is a "
            "conservative fallback diagnostic, not a new Venn-Abers validity claim.",
            "",
            "| metric | value |",
            "|---|---:|",
        ]
    )
    fallback = summary.get("split_fallback_grid_summary", {})
    fallback_ratio = fallback.get("mean_radius_ratio_vs_grid")
    fallback_rows = [
        ("coverage", fallback.get("mean_coverage")),
        ("mean_width", fallback.get("mean_width")),
        ("mean_radius", fallback.get("mean_radius")),
        ("mean_split_radius", fallback.get("mean_split_radius")),
        ("radius_ratio_vs_grid", fallback_ratio),
        ("grid_minus_radius", fallback.get("mean_grid_minus_split_fallback_radius")),
        ("abs_delta_vs_grid", fallback.get("mean_abs_radius_delta_vs_grid")),
        ("residual_exceeds_radius", fallback.get("mean_residual_exceeds_radius_rate")),
        ("split_radius_active_rate", fallback.get("mean_split_radius_active_rate")),
        (
            "fallback_radius_exceeds_grid_rate",
            fallback.get("mean_split_fallback_radius_exceeds_grid_rate"),
        ),
        ("interval_score", fallback.get("mean_interval_score")),
    ]
    for metric, value in fallback_rows:
        lines.append(f"| {metric} | {'NA' if value is None else f'{value:.6f}'} |")
    lines.extend(
        [
            "",
            "## Bridge Inflation Sensitivity Against Grid Reference",
            "",
            "This is a diagnostic only. It multiplies the fast bridge radius by fixed "
            "factors on the same selected rows to estimate how much conservative "
            "slack would be needed to approach the grid reference.",
            "",
            "| factor | coverage | radius | radius/grid | grid_minus_radius | abs_delta | residual>radius | inflated>grid | interval_score |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for factor, row in summary.get("bridge_inflation_sensitivity_summary", {}).items():
        ratio = row["mean_radius_ratio_vs_grid"]
        lines.append(
            "| {factor} | {coverage:.6f} | {radius:.6f} | {ratio} | {delta:.6f} | "
            "{abs_delta:.6f} | {exceeds:.6f} | {over:.6f} | {score:.6f} |".format(
                factor=factor,
                coverage=row["mean_coverage"],
                radius=row["mean_radius"],
                ratio="NA" if ratio is None else f"{ratio:.6f}",
                delta=row["mean_grid_minus_inflated_radius"],
                abs_delta=row["mean_abs_radius_delta_vs_grid"],
                exceeds=row["mean_residual_exceeds_radius_rate"],
                over=row["mean_inflated_radius_exceeds_grid_rate"],
                score=row["mean_interval_score"],
            )
        )
    lines.extend(
        [
            "",
            "## IVAR m Sensitivity Against Grid Reference",
            "",
            "Each row compares a fast bridge using IVAR tail parameter `m` against the "
            "same exact grid reference rows.",
            "",
            "| m | coverage | radius | radius/grid | grid_minus_radius | abs_delta | residual>radius | interval_score |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for m_value, row in summary.get("ivar_m_sensitivity_summary", {}).items():
        ratio = row["mean_radius_ratio_vs_grid"]
        lines.append(
            "| {m} | {coverage:.6f} | {radius:.6f} | {ratio} | {delta:.6f} | "
            "{abs_delta:.6f} | {exceeds:.6f} | {score:.6f} |".format(
                m=m_value,
                coverage=row["mean_coverage"],
                radius=row["mean_radius"],
                ratio="NA" if ratio is None else f"{ratio:.6f}",
                delta=row["mean_grid_minus_m_radius"],
                abs_delta=row["mean_abs_radius_delta_vs_grid"],
                exceeds=row["mean_residual_exceeds_radius_rate"],
                score=row["mean_interval_score"],
            )
        )
    lines.extend(
        [
            "",
            "## Run Details",
            "",
            "| dataset | model | alpha | VA coverage | VA width | IVAPD rows | IVAPD CRPS | point-step CRPS | delta | CRPS gap |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for result in payload["results"]:
        interval = result["venn_abers_quantile_interval"]
        ivapd = result["ivapd_threshold_grid"]
        crps_gap = ivapd["midpoint_crps_gap"]
        lines.append(
            "| {dataset_id} | {model_id} | {alpha:.2f} | {coverage:.6f} | {width:.6f} | "
            "{rows} | {crps:.6f} | {point:.6f} | {delta:.6f} | {gap} |".format(
                dataset_id=result["dataset_id"],
                model_id=result["model_id"],
                alpha=result["alpha"],
                coverage=interval["coverage"],
                width=interval["mean_width"],
                rows=ivapd["test_rows_scored"],
                crps=ivapd["mean_midpoint_crps"],
                point=ivapd["mean_point_step_crps"],
                delta=ivapd["mean_crps_delta_vs_point_step"],
                gap="NA" if crps_gap is None else f"{crps_gap:.6f}",
            )
        )
    lines.extend(
        [
            "",
            "## Per-Run Interval Comparison",
            "",
            "| dataset | model | method | coverage | coverage_delta_vs_va | width | width_ratio_vs_va | interval_score | miss_rate | radius_ratio_vs_va | residual/radius |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for result in payload["results"]:
        for row in result.get("interval_method_comparison", []):
            width_ratio = row["width_ratio_vs_primary"]
            radius_ratio = row["radius_ratio_vs_primary"]
            residual_ratio = row["mean_residual_to_radius_ratio"]
            lines.append(
                "| {dataset_id} | {model_id} | {method} | {coverage:.6f} | "
                "{coverage_delta:.6f} | {width:.6f} | {width_ratio} | "
                "{interval_score:.6f} | {miss_rate:.6f} | {radius_ratio} | "
                "{residual_ratio} |".format(
                    dataset_id=result["dataset_id"],
                    model_id=result["model_id"],
                    method=row["method"],
                    coverage=row["coverage"],
                    coverage_delta=row["coverage_delta_vs_primary"],
                    width=row["mean_width"],
                    width_ratio="NA" if width_ratio is None else f"{width_ratio:.6f}",
                    interval_score=row["interval_score"],
                    miss_rate=row["miss_rate_transformed"],
                    radius_ratio="NA" if radius_ratio is None else f"{radius_ratio:.6f}",
                    residual_ratio="NA" if residual_ratio is None else f"{residual_ratio:.6f}",
                )
            )
    lines.append("")
    return "\n".join(lines)


def run_diagnostics(config: dict, force: bool = False, max_runs: int | None = None) -> dict:
    checkpoint_root = Path(config["logging"]["checkpoint_root"])
    prediction_cache_root = Path(config["logging"]["prediction_cache_root"])
    dataset_cache = {}
    results = []
    for run_idx, run in enumerate(iter_diagnostic_runs(config)):
        if max_runs is not None and run_idx >= max_runs:
            break
        results.append(
            run_one_diagnostic(
                *run,
                config=config,
                checkpoint_root=checkpoint_root,
                prediction_cache_root=prediction_cache_root,
                force=force,
                dataset_cache=dataset_cache,
            )
        )
    return {
        "benchmark_id": BENCHMARK_ID,
        "experiment_id": config.get("experiment_id"),
        "purpose": config.get("purpose"),
        "summary": summarize_results(results),
        "results": results,
    }


def main() -> None:
    args = parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    payload = run_diagnostics(config, force=args.force, max_runs=args.max_runs)
    report_dir = Path(config["logging"]["report_dir"])
    report_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(report_dir / "diagnostic.json", payload)
    atomic_write_text(report_dir / "diagnostic.md", render_markdown(payload))
    append_jsonl(Path(config["logging"]["ledger"]), [ledger_row(result) for result in payload["results"]])
    print(json.dumps({"status": "ok", "runs": len(payload["results"])}))


if __name__ == "__main__":
    main()
