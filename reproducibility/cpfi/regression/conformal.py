"""Conformal prediction intervals for regression.

Implemented methods are deliberately array-based. Model fitting stays outside
this module, which makes every interval construction easy to test, checkpoint,
and reuse across model families.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

import numpy as np
from sklearn.isotonic import IsotonicRegression


@dataclass(frozen=True)
class RegressionCPResult:
    """Prediction interval result for regression conformal methods."""

    lower: np.ndarray
    upper: np.ndarray
    radii: np.ndarray
    thresholds: Dict[str, float]
    metadata: Dict

    @property
    def width(self) -> np.ndarray:
        return self.upper - self.lower


@dataclass(frozen=True)
class FiniteSampleQuantileResult:
    """Finite-sample conformal quantile plus audit metadata."""

    value: float
    metadata: Dict


def _as_1d(values: Iterable[float], name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D array, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values")
    return arr


def _validate_alpha(alpha: float) -> None:
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")


def _ordered_bounds(lower: np.ndarray, upper: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    crossings = int(np.sum(lower > upper))
    return np.minimum(lower, upper), np.maximum(lower, upper), crossings


def _lower_weighted_quantile(
    values: np.ndarray,
    quantile: float,
    weights: np.ndarray | None = None,
) -> float:
    """Return the lower weighted quantile used by quantile-loss PAVA."""

    if not 0 < quantile < 1:
        raise ValueError(f"quantile must be in (0, 1), got {quantile}")
    values_arr = _as_1d(values, "values")
    if weights is None:
        weights_arr = np.ones(len(values_arr), dtype=float)
    else:
        weights_arr = _as_1d(weights, "weights")
        if len(weights_arr) != len(values_arr):
            raise ValueError("weights and values must have the same length")
        if np.any(weights_arr <= 0):
            raise ValueError("weights must be positive")

    order = np.argsort(values_arr, kind="mergesort")
    sorted_values = values_arr[order]
    sorted_weights = weights_arr[order]
    threshold = quantile * sorted_weights.sum()
    idx = int(np.searchsorted(np.cumsum(sorted_weights), threshold, side="left"))
    return float(sorted_values[min(idx, len(sorted_values) - 1)])


def _merge_quantile_blocks(blocks: list[dict], quantile: float) -> list[dict]:
    merged: list[dict] = []
    for block in blocks:
        merged.append(block)
        while len(merged) >= 2 and merged[-2]["value"] > merged[-1]["value"]:
            right = merged.pop()
            left = merged.pop()
            labels = np.concatenate([left["labels"], right["labels"]])
            combined = {
                "x_min": left["x_min"],
                "x_max": right["x_max"],
                "labels": labels,
                "value": _lower_weighted_quantile(labels, quantile),
            }
            merged.append(combined)
    return merged


def isotonic_quantile_fit_predict(
    x: Iterable[float],
    y: Iterable[float],
    x_eval: Iterable[float],
    quantile: float,
) -> tuple[np.ndarray, Dict]:
    """Fit monotone quantile regression by generalized PAVA and predict.

    This is a small deterministic reference implementation for Venn-Abers
    quantile-calibration tests. It minimizes pinball loss over nondecreasing
    step functions by repeatedly merging adjacent blocks whose lower quantiles
    violate monotonicity.
    """

    x_arr = _as_1d(x, "x")
    y_arr = _as_1d(y, "y")
    x_eval_arr = _as_1d(x_eval, "x_eval")
    if len(x_arr) != len(y_arr):
        raise ValueError("x and y must have the same length")
    if len(x_arr) == 0:
        raise ValueError("x and y must contain at least one row")
    if not 0 < quantile < 1:
        raise ValueError(f"quantile must be in (0, 1), got {quantile}")

    order = np.argsort(x_arr, kind="mergesort")
    x_sorted = x_arr[order]
    y_sorted = y_arr[order]

    blocks = []
    start = 0
    while start < len(x_sorted):
        end = start + 1
        while end < len(x_sorted) and x_sorted[end] == x_sorted[start]:
            end += 1
        labels = y_sorted[start:end]
        blocks.append(
            {
                "x_min": float(x_sorted[start]),
                "x_max": float(x_sorted[end - 1]),
                "labels": labels,
                "value": _lower_weighted_quantile(labels, quantile),
            }
        )
        start = end

    merged = _merge_quantile_blocks(blocks, quantile)
    x_max = np.array([block["x_max"] for block in merged], dtype=float)
    block_values = np.array([block["value"] for block in merged], dtype=float)
    pred_idx = np.searchsorted(x_max, x_eval_arr, side="left")
    pred_idx = np.clip(pred_idx, 0, len(block_values) - 1)
    metadata = {
        "quantile": float(quantile),
        "n_input": int(len(x_arr)),
        "n_initial_blocks": int(len(blocks)),
        "n_final_blocks": int(len(merged)),
        "block_values": [float(value) for value in block_values],
        "block_x_max": [float(value) for value in x_max],
    }
    return block_values[pred_idx], metadata


def finite_sample_quantile_result(
    scores: Iterable[float], alpha: float
) -> FiniteSampleQuantileResult:
    """Return the split-conformal finite-sample quantile with diagnostics.

    This uses ceil((n + 1) * (1 - alpha)) / n, capped at 1.0, matching the
    correction used by the existing classification CP code.
    """

    _validate_alpha(alpha)
    scores_arr = _as_1d(scores, "scores")
    if len(scores_arr) == 0:
        raise ValueError("scores must contain at least one calibration value")

    requested_q = float(np.ceil((len(scores_arr) + 1) * (1 - alpha)) / len(scores_arr))
    used_q = min(requested_q, 1.0)
    return FiniteSampleQuantileResult(
        value=float(np.quantile(scores_arr, used_q, method="higher")),
        metadata={
            "finite_sample_quantile_requested": requested_q,
            "finite_sample_quantile_used": used_q,
            "finite_sample_quantile_n": int(len(scores_arr)),
            "finite_sample_quantile_capped": requested_q > 1.0,
        },
    )


def finite_sample_quantile(scores: Iterable[float], alpha: float) -> float:
    """Return the split-conformal finite-sample quantile value."""

    return finite_sample_quantile_result(scores, alpha).value


def _prefixed_quantile_metadata(prefix: str, metadata: Dict) -> Dict:
    return {f"{prefix}_{key}": value for key, value in metadata.items()}


def _bcrt_plus_indices(n: int, alpha: float) -> tuple[int, int]:
    """Return zero-based BCRT jackknife+/CV+ lower and upper order indices."""

    _validate_alpha(alpha)
    if n <= 0:
        raise ValueError("n must be positive")
    lower_rank = max(1, int(np.floor(alpha * (n + 1))))
    upper_rank = min(n, int(np.ceil((1 - alpha) * (n + 1))))
    return lower_rank - 1, upper_rank - 1


def _bcrt_plus_quantiles(
    lower_candidates: np.ndarray, upper_candidates: np.ndarray, alpha: float
) -> tuple[np.ndarray, np.ndarray, Dict]:
    if lower_candidates.ndim != 2 or upper_candidates.ndim != 2:
        raise ValueError("plus candidates must be two-dimensional")
    if lower_candidates.shape != upper_candidates.shape:
        raise ValueError("lower and upper plus candidates must have the same shape")
    lower_idx, upper_idx = _bcrt_plus_indices(lower_candidates.shape[0], alpha)
    lower = np.sort(lower_candidates, axis=0)[lower_idx]
    upper = np.sort(upper_candidates, axis=0)[upper_idx]
    return lower, upper, {
        "plus_order_statistic_rule": "bcrt_floor_alpha_n_plus_1_ceil_one_minus_alpha_n_plus_1",
        "plus_lower_order_index_zero_based": int(lower_idx),
        "plus_upper_order_index_zero_based": int(upper_idx),
    }


def weighted_conformal_quantile(
    scores: Iterable[float],
    calibration_weights: Iterable[float],
    test_weight: float,
    alpha: float,
) -> float:
    """Return the weighted split-conformal quantile with an infinity atom.

    The empirical score distribution places mass proportional to each
    calibration likelihood ratio on finite calibration scores and mass
    proportional to the test likelihood ratio at infinity.
    """

    _validate_alpha(alpha)
    scores_arr = _as_1d(scores, "scores")
    weights_arr = _as_1d(calibration_weights, "calibration_weights")
    if len(scores_arr) == 0:
        raise ValueError("scores must contain at least one calibration value")
    if len(scores_arr) != len(weights_arr):
        raise ValueError("scores and calibration_weights must have the same length")
    if np.any(weights_arr <= 0):
        raise ValueError("calibration_weights must be positive")
    test_weight_value = float(test_weight)
    if not np.isfinite(test_weight_value) or test_weight_value <= 0:
        raise ValueError(f"test_weight must be a positive finite value, got {test_weight}")

    total_weight = float(weights_arr.sum() + test_weight_value)
    target_mass = 1.0 - alpha
    order = np.argsort(scores_arr, kind="mergesort")
    cumulative = np.cumsum(weights_arr[order]) / total_weight
    idx = int(np.searchsorted(cumulative, target_mass, side="left"))
    if idx >= len(scores_arr):
        return float("inf")
    return float(scores_arr[order[idx]])


def weighted_split_conformal_interval(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    calibration_weights: Iterable[float],
    test_weights: Iterable[float],
    alpha: float,
) -> RegressionCPResult:
    """Weighted split conformal regression with absolute residual scores."""

    y_cal_arr = _as_1d(y_cal, "y_cal")
    yhat_cal_arr = _as_1d(yhat_cal, "yhat_cal")
    yhat_test_arr = _as_1d(yhat_test, "yhat_test")
    cal_weights_arr = _as_1d(calibration_weights, "calibration_weights")
    test_weights_arr = _as_1d(test_weights, "test_weights")
    if len(y_cal_arr) != len(yhat_cal_arr) or len(y_cal_arr) != len(cal_weights_arr):
        raise ValueError("calibration arrays must have the same length")
    if len(yhat_test_arr) != len(test_weights_arr):
        raise ValueError("yhat_test and test_weights must have the same length")
    if np.any(cal_weights_arr <= 0) or np.any(test_weights_arr <= 0):
        raise ValueError("calibration_weights and test_weights must be positive")

    scores = np.abs(y_cal_arr - yhat_cal_arr)
    radii = np.array(
        [
            weighted_conformal_quantile(scores, cal_weights_arr, test_weight, alpha)
            for test_weight in test_weights_arr
        ],
        dtype=float,
    )
    finite_radii = radii[np.isfinite(radii)]
    infinite_count = int(np.sum(~np.isfinite(radii)))
    finite_mean = float(finite_radii.mean()) if len(finite_radii) else 0.0

    return RegressionCPResult(
        lower=yhat_test_arr - radii,
        upper=yhat_test_arr + radii,
        radii=radii,
        thresholds={
            "finite_radius_mean": finite_mean,
            "infinite_radius_count": float(infinite_count),
            "mean_calibration_weight": float(cal_weights_arr.mean()),
            "mean_test_weight": float(test_weights_arr.mean()),
        },
        metadata={
            "method": "weighted_abs_covariate_shift",
            "alpha": alpha,
            "n_cal": len(y_cal_arr),
            "weighting_role": "likelihood_ratio_weighted_split_conformal",
            "finite_sample_claim": (
                "valid under covariate shift when likelihood ratios are known; "
                "estimated ratios are diagnostic unless separately validated"
            ),
            "min_calibration_weight": float(cal_weights_arr.min()),
            "max_calibration_weight": float(cal_weights_arr.max()),
            "min_test_weight": float(test_weights_arr.min()),
            "max_test_weight": float(test_weights_arr.max()),
            "infinite_radius_count": infinite_count,
        },
    )


def _inverse_monotone_cdf_grid(
    probability: float,
    label_grid: np.ndarray,
    cdf_row: np.ndarray,
) -> float:
    """Invert a monotone CDF grid with a documented linear grid policy."""

    tolerance = 1e-12
    if probability < cdf_row[0] - tolerance or probability > cdf_row[-1] + tolerance:
        raise ValueError(
            "cdf_values_test rows must cover requested interval probabilities"
        )
    clipped_probability = float(np.clip(probability, cdf_row[0], cdf_row[-1]))
    unique_probabilities = []
    unique_labels = []
    for cdf_value, label in zip(cdf_row, label_grid):
        if not unique_probabilities or cdf_value > unique_probabilities[-1] + tolerance:
            unique_probabilities.append(float(cdf_value))
            unique_labels.append(float(label))
    if len(unique_probabilities) == 1:
        return unique_labels[0]
    return float(
        np.interp(
            clipped_probability,
            np.array(unique_probabilities, dtype=float),
            np.array(unique_labels, dtype=float),
        )
    )


def conformal_predictive_system_interval(
    label_grid: Iterable[float],
    cdf_values_test: Iterable[Iterable[float]],
    alpha: float,
    lower_tail_alpha_fraction: float = 0.5,
) -> RegressionCPResult:
    """Extract central intervals from conformal predictive-system CDF grids.

    The caller supplies test-time predictive CDF values generated by a conformal
    predictive-system protocol. This helper only applies an interval-extraction
    policy to those supplied distributions; it does not fit a CPS, choose
    randomization, or make broad runner claims.
    """

    _validate_alpha(alpha)
    if not 0 < lower_tail_alpha_fraction < 1:
        raise ValueError(
            "lower_tail_alpha_fraction must be in (0, 1), "
            f"got {lower_tail_alpha_fraction}"
        )

    labels = _as_1d(label_grid, "label_grid")
    cdf_values = np.asarray(cdf_values_test, dtype=float)
    if len(labels) < 2:
        raise ValueError("label_grid must contain at least two values")
    if np.any(np.diff(labels) <= 0.0):
        raise ValueError("label_grid must be strictly increasing")
    if cdf_values.ndim != 2:
        raise ValueError(f"cdf_values_test must be 2D, got shape {cdf_values.shape}")
    if cdf_values.shape[1] != len(labels):
        raise ValueError("cdf_values_test columns must match label_grid")
    if not np.all(np.isfinite(cdf_values)):
        raise ValueError("cdf_values_test contains non-finite values")
    if np.any((cdf_values < 0.0) | (cdf_values > 1.0)):
        raise ValueError("cdf_values_test values must be in [0, 1]")
    if np.any(np.diff(cdf_values, axis=1) < -1e-12):
        raise ValueError("each CPS CDF row must be nondecreasing")

    lower_tail_alpha = alpha * lower_tail_alpha_fraction
    upper_tail_alpha = alpha - lower_tail_alpha
    lower_probability = float(lower_tail_alpha)
    upper_probability = float(1.0 - upper_tail_alpha)

    lower = np.array(
        [
            _inverse_monotone_cdf_grid(lower_probability, labels, row)
            for row in cdf_values
        ],
        dtype=float,
    )
    upper = np.array(
        [
            _inverse_monotone_cdf_grid(upper_probability, labels, row)
            for row in cdf_values
        ],
        dtype=float,
    )
    lower, upper, crossings = _ordered_bounds(lower, upper)

    return RegressionCPResult(
        lower=lower,
        upper=upper,
        radii=(upper - lower) / 2.0,
        thresholds={
            "lower_probability": lower_probability,
            "upper_probability": upper_probability,
            "label_grid_min": float(labels[0]),
            "label_grid_max": float(labels[-1]),
        },
        metadata={
            "method": "conformal_predictive_system",
            "alpha": alpha,
            "n_test": int(cdf_values.shape[0]),
            "label_grid_size": int(len(labels)),
            "lower_tail_alpha": float(lower_tail_alpha),
            "upper_tail_alpha": float(upper_tail_alpha),
            "lower_tail_alpha_fraction": float(lower_tail_alpha_fraction),
            "calibrated_object": "conformal_predictive_distribution_cdf",
            "interval_extraction": "central_cdf_grid_interval",
            "cdf_grid_policy": "linear_inverse_cdf_interpolation_after_removing_flat_duplicates",
            "implementation_role": "cdf_grid_interval_extraction_reference_not_broad_runner",
            "cdf_grid_start_min": float(np.min(cdf_values[:, 0])),
            "cdf_grid_end_max": float(np.max(cdf_values[:, -1])),
            "interval_crossings_reordered": crossings,
            "finite_sample_interval_claim": (
                "reference interval-extraction primitive for conformal "
                "predictive-system CDF grids; interval validity requires the "
                "supplied CDFs to come from a valid CPS protocol and the label "
                "grid to cover the requested tail probabilities"
            ),
        },
    )


def distributional_pit_conformal_interval(
    pit_cal: Iterable[float],
    quantile_probabilities: Iterable[float],
    quantile_values_test: Iterable[Iterable[float]],
    alpha: float,
    lower_tail_alpha_fraction: float = 0.5,
) -> RegressionCPResult:
    """Distributional conformal interval from PIT scores and quantile grids.

    The caller supplies calibration probability integral transform values
    ``F_hat(Y_i | X_i)`` and a test-time conditional quantile grid. The helper
    calibrates a central PIT interval with two one-sided conformal scores, then
    maps the calibrated probability endpoints through each test quantile grid.

    Model estimation stays outside this function. The finite-sample claim is
    therefore conditional on the distribution estimator being trained without
    calibration/test leakage and the supplied quantile grid representing the
    inverse CDF used to compute the calibration PIT values.
    """

    _validate_alpha(alpha)
    if not 0 < lower_tail_alpha_fraction < 1:
        raise ValueError(
            "lower_tail_alpha_fraction must be in (0, 1), "
            f"got {lower_tail_alpha_fraction}"
        )

    pit = _as_1d(pit_cal, "pit_cal")
    probabilities = _as_1d(quantile_probabilities, "quantile_probabilities")
    quantiles = np.asarray(quantile_values_test, dtype=float)
    if len(pit) == 0:
        raise ValueError("pit_cal must contain at least one calibration value")
    if np.any((pit < 0.0) | (pit > 1.0)):
        raise ValueError("pit_cal values must be in [0, 1]")
    if len(probabilities) < 2:
        raise ValueError("quantile_probabilities must contain at least two values")
    if np.any((probabilities < 0.0) | (probabilities > 1.0)):
        raise ValueError("quantile_probabilities must be in [0, 1]")
    if np.any(np.diff(probabilities) <= 0.0):
        raise ValueError("quantile_probabilities must be strictly increasing")
    if quantiles.ndim != 2:
        raise ValueError(
            f"quantile_values_test must be 2D, got shape {quantiles.shape}"
        )
    if quantiles.shape[1] != len(probabilities):
        raise ValueError(
            "quantile_values_test columns must match quantile_probabilities"
        )
    if not np.all(np.isfinite(quantiles)):
        raise ValueError("quantile_values_test contains non-finite values")
    if np.any(np.diff(quantiles, axis=1) < -1e-12):
        raise ValueError("each test quantile row must be nondecreasing")

    lower_tail_alpha = alpha * lower_tail_alpha_fraction
    upper_tail_alpha = alpha - lower_tail_alpha
    base_lower_probability = lower_tail_alpha
    base_upper_probability = 1.0 - upper_tail_alpha
    lower_scores = base_lower_probability - pit
    upper_scores = pit - base_upper_probability
    raw_lower_result = finite_sample_quantile_result(lower_scores, lower_tail_alpha)
    raw_upper_result = finite_sample_quantile_result(upper_scores, upper_tail_alpha)
    raw_lower_correction = raw_lower_result.value
    raw_upper_correction = raw_upper_result.value
    lower_correction = max(raw_lower_correction, 0.0)
    upper_correction = max(raw_upper_correction, 0.0)
    lower_probability = float(np.clip(base_lower_probability - lower_correction, 0.0, 1.0))
    upper_probability = float(np.clip(base_upper_probability + upper_correction, 0.0, 1.0))

    if lower_probability < probabilities[0] or upper_probability > probabilities[-1]:
        raise ValueError(
            "quantile_probabilities must cover calibrated PIT interval endpoints "
            f"[{lower_probability}, {upper_probability}]"
        )

    lower = np.array(
        [
            np.interp(lower_probability, probabilities, row)
            for row in quantiles
        ],
        dtype=float,
    )
    upper = np.array(
        [
            np.interp(upper_probability, probabilities, row)
            for row in quantiles
        ],
        dtype=float,
    )
    lower, upper, crossings = _ordered_bounds(lower, upper)

    return RegressionCPResult(
        lower=lower,
        upper=upper,
        radii=(upper - lower) / 2.0,
        thresholds={
            "lower_probability": lower_probability,
            "upper_probability": upper_probability,
            "base_lower_probability": float(base_lower_probability),
            "base_upper_probability": float(base_upper_probability),
            "lower_pit_correction": float(lower_correction),
            "upper_pit_correction": float(upper_correction),
        },
        metadata={
            "method": "distributional_conformal_prediction",
            "alpha": alpha,
            "n_cal": int(len(pit)),
            "lower_tail_alpha": float(lower_tail_alpha),
            "upper_tail_alpha": float(upper_tail_alpha),
            "lower_tail_alpha_fraction": float(lower_tail_alpha_fraction),
            "raw_lower_pit_correction": float(raw_lower_correction),
            "raw_upper_pit_correction": float(raw_upper_correction),
            "negative_lower_correction_clipped": bool(raw_lower_correction < 0.0),
            "negative_upper_correction_clipped": bool(raw_upper_correction < 0.0),
            "calibrated_object": "probability_integral_transform_rank",
            "interval_extraction": "central_pit_interval_mapped_through_test_quantile_grid",
            "quantile_grid_size": int(len(probabilities)),
            "quantile_probability_min": float(probabilities[0]),
            "quantile_probability_max": float(probabilities[-1]),
            "interval_crossings_reordered": crossings,
            **_prefixed_quantile_metadata("lower_pit", raw_lower_result.metadata),
            **_prefixed_quantile_metadata("upper_pit", raw_upper_result.metadata),
            "finite_sample_interval_claim": (
                "reference distributional conformal primitive; valid as a split "
                "PIT-calibrated interval when the conditional distribution "
                "estimator is trained outside calibration/test data and the "
                "supplied quantile grid is the matching inverse CDF"
            ),
        },
    )


def full_conformal_score_grid_interval(
    candidate_values: Iterable[float],
    calibration_scores_by_candidate: Iterable[Iterable[float]],
    test_scores_by_candidate: Iterable[float],
    alpha: float,
) -> RegressionCPResult:
    """Invert a full conformal candidate-label score grid.

    The caller supplies a grid of candidate response values and the nonconformity
    scores obtained after augmenting/refitting the model for each candidate. The
    primitive computes the usual conformal p-value for every candidate and
    returns the hull of accepted candidates.

    This helper is a tiny-grid reference primitive. It does not fit or refit
    models, and it must not be reported as a broad-sweep full conformal runner
    unless candidate-grid construction, refit policy, and endpoint audits are
    supplied by a dedicated experiment bundle.
    """

    _validate_alpha(alpha)
    candidates = _as_1d(candidate_values, "candidate_values")
    cal_scores = np.asarray(calibration_scores_by_candidate, dtype=float)
    test_scores = _as_1d(test_scores_by_candidate, "test_scores_by_candidate")
    if len(candidates) == 0:
        raise ValueError("candidate_values must contain at least one candidate")
    if cal_scores.ndim != 2:
        raise ValueError(
            "calibration_scores_by_candidate must be 2D, "
            f"got shape {cal_scores.shape}"
        )
    if cal_scores.shape[0] != len(candidates):
        raise ValueError(
            "calibration_scores_by_candidate rows must match candidate_values"
        )
    if len(test_scores) != len(candidates):
        raise ValueError("test_scores_by_candidate must match candidate_values")
    if cal_scores.shape[1] == 0:
        raise ValueError("calibration_scores_by_candidate must include calibration rows")
    if not np.all(np.isfinite(cal_scores)):
        raise ValueError("calibration_scores_by_candidate contains non-finite values")

    order = np.argsort(candidates, kind="mergesort")
    sorted_candidates = candidates[order]
    sorted_cal_scores = cal_scores[order]
    sorted_test_scores = test_scores[order]
    if np.any(np.diff(sorted_candidates) <= 0.0):
        raise ValueError("candidate_values must be unique")

    exceed_counts = np.sum(sorted_cal_scores >= sorted_test_scores[:, None], axis=1)
    p_values = (exceed_counts + 1.0) / (sorted_cal_scores.shape[1] + 1.0)
    accepted_mask = p_values > alpha
    if not np.any(accepted_mask):
        raise ValueError(
            "no accepted full conformal candidates; expand candidate grid or "
            "review supplied score direction"
        )

    accepted_candidates = sorted_candidates[accepted_mask]
    lower = np.array([float(np.min(accepted_candidates))], dtype=float)
    upper = np.array([float(np.max(accepted_candidates))], dtype=float)

    return RegressionCPResult(
        lower=lower,
        upper=upper,
        radii=(upper - lower) / 2.0,
        thresholds={
            "accepted_min": float(lower[0]),
            "accepted_max": float(upper[0]),
            "min_p_value": float(np.min(p_values)),
            "max_p_value": float(np.max(p_values)),
        },
        metadata={
            "method": "full_conformal_regression",
            "alpha": alpha,
            "n_cal": int(sorted_cal_scores.shape[1]),
            "grid_size": int(len(sorted_candidates)),
            "accepted_count": int(np.sum(accepted_mask)),
            "rejected_count": int(len(sorted_candidates) - np.sum(accepted_mask)),
            "candidate_values": [float(value) for value in sorted_candidates],
            "p_values": [float(value) for value in p_values],
            "accepted_candidate_values": [
                float(value) for value in accepted_candidates
            ],
            "p_value_rule": "(1 + count(calibration_score >= test_score)) / (n_cal + 1)",
            "score_direction": "larger_nonconformity_score_is_worse",
            "implementation_role": "tiny_grid_reference_not_broad_runner",
            "finite_sample_interval_claim": (
                "full conformal score-grid inversion reference; finite-sample "
                "coverage requires candidate-specific scores from the exact "
                "transductive refit/augmentation protocol"
            ),
        },
    )


def rank_one_out_score_grid_interval(
    candidate_values: Iterable[float],
    comparison_scores_by_candidate: Iterable[Iterable[float]],
    target_scores_by_candidate: Iterable[float],
    alpha: float,
) -> RegressionCPResult:
    """Invert a rank-one-out conformal candidate-label score grid.

    The caller supplies candidate response values and precomputed rank-one-out
    nonconformity scores for each candidate. This function only performs the
    conformal rank/p-value inversion. It does not fit models or perform the
    rank-one update itself.
    """

    _validate_alpha(alpha)
    candidates = _as_1d(candidate_values, "candidate_values")
    comparison_scores = np.asarray(comparison_scores_by_candidate, dtype=float)
    target_scores = _as_1d(target_scores_by_candidate, "target_scores_by_candidate")
    if len(candidates) == 0:
        raise ValueError("candidate_values must contain at least one candidate")
    if comparison_scores.ndim != 2:
        raise ValueError(
            "comparison_scores_by_candidate must be 2D, "
            f"got shape {comparison_scores.shape}"
        )
    if comparison_scores.shape[0] != len(candidates):
        raise ValueError("comparison_scores_by_candidate rows must match candidate_values")
    if len(target_scores) != len(candidates):
        raise ValueError("target_scores_by_candidate must match candidate_values")
    if comparison_scores.shape[1] == 0:
        raise ValueError("comparison_scores_by_candidate must include comparison rows")
    if not np.all(np.isfinite(comparison_scores)):
        raise ValueError("comparison_scores_by_candidate contains non-finite values")

    order = np.argsort(candidates, kind="mergesort")
    sorted_candidates = candidates[order]
    sorted_comparison_scores = comparison_scores[order]
    sorted_target_scores = target_scores[order]
    if np.any(np.diff(sorted_candidates) <= 0.0):
        raise ValueError("candidate_values must be unique")

    exceed_counts = np.sum(
        sorted_comparison_scores >= sorted_target_scores[:, None],
        axis=1,
    )
    p_values = (exceed_counts + 1.0) / (sorted_comparison_scores.shape[1] + 1.0)
    accepted_mask = p_values > alpha
    if not np.any(accepted_mask):
        raise ValueError(
            "no accepted rank-one-out candidates; expand candidate grid or "
            "review supplied score direction"
        )

    accepted_candidates = sorted_candidates[accepted_mask]
    lower = np.array([float(np.min(accepted_candidates))], dtype=float)
    upper = np.array([float(np.max(accepted_candidates))], dtype=float)

    return RegressionCPResult(
        lower=lower,
        upper=upper,
        radii=(upper - lower) / 2.0,
        thresholds={
            "accepted_min": float(lower[0]),
            "accepted_max": float(upper[0]),
            "min_p_value": float(np.min(p_values)),
            "max_p_value": float(np.max(p_values)),
        },
        metadata={
            "method": "rank_one_out_conformal",
            "alpha": alpha,
            "n_comparison": int(sorted_comparison_scores.shape[1]),
            "grid_size": int(len(sorted_candidates)),
            "accepted_count": int(np.sum(accepted_mask)),
            "rejected_count": int(len(sorted_candidates) - np.sum(accepted_mask)),
            "candidate_values": [float(value) for value in sorted_candidates],
            "p_values": [float(value) for value in p_values],
            "accepted_candidate_values": [
                float(value) for value in accepted_candidates
            ],
            "p_value_rule": "(1 + count(comparison_score >= target_score)) / (n_comparison + 1)",
            "score_direction": "larger_nonconformity_score_is_worse",
            "implementation_role": "rank_one_out_score_grid_reference_not_broad_runner",
            "finite_sample_interval_claim": (
                "rank-one-out conformal score-grid inversion reference; "
                "finite-sample in-sample interval validity requires the supplied "
                "candidate-specific scores to come from the rank-one-out "
                "update/refit protocol"
            ),
        },
    )


def split_conformal_interval(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    alpha: float,
) -> RegressionCPResult:
    """Standard split conformal regression with absolute residual scores."""

    y_cal_arr = _as_1d(y_cal, "y_cal")
    yhat_cal_arr = _as_1d(yhat_cal, "yhat_cal")
    yhat_test_arr = _as_1d(yhat_test, "yhat_test")
    if len(y_cal_arr) != len(yhat_cal_arr):
        raise ValueError("y_cal and yhat_cal must have the same length")

    scores = np.abs(y_cal_arr - yhat_cal_arr)
    radius_result = finite_sample_quantile_result(scores, alpha)
    radius = radius_result.value
    radii = np.full_like(yhat_test_arr, radius, dtype=float)

    return RegressionCPResult(
        lower=yhat_test_arr - radii,
        upper=yhat_test_arr + radii,
        radii=radii,
        thresholds={"global": radius},
        metadata={
            "method": "split_abs",
            "alpha": alpha,
            "n_cal": len(y_cal_arr),
            **radius_result.metadata,
        },
    )


def split_tail_conformal_interval(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    alpha: float,
    lower_tail_alpha_fraction: float = 0.5,
    clip_negative_offsets: bool = True,
) -> RegressionCPResult:
    """Split conformal interval from separately calibrated one-sided tails.

    ``lower_tail_alpha_fraction`` allocates the total miscoverage budget to the
    lower-tail miss event ``Y < lower``; the remaining budget is assigned to
    upper-tail misses. The returned interval is the conservative hull of the
    two one-sided split conformal bounds.
    """

    _validate_alpha(alpha)
    if not 0 < lower_tail_alpha_fraction < 1:
        raise ValueError(
            "lower_tail_alpha_fraction must be in (0, 1), "
            f"got {lower_tail_alpha_fraction}"
        )

    y_cal_arr = _as_1d(y_cal, "y_cal")
    yhat_cal_arr = _as_1d(yhat_cal, "yhat_cal")
    yhat_test_arr = _as_1d(yhat_test, "yhat_test")
    if len(y_cal_arr) != len(yhat_cal_arr):
        raise ValueError("y_cal and yhat_cal must have the same length")

    lower_tail_alpha = alpha * lower_tail_alpha_fraction
    upper_tail_alpha = alpha - lower_tail_alpha
    lower_scores = yhat_cal_arr - y_cal_arr
    upper_scores = y_cal_arr - yhat_cal_arr
    raw_lower_result = finite_sample_quantile_result(lower_scores, lower_tail_alpha)
    raw_upper_result = finite_sample_quantile_result(upper_scores, upper_tail_alpha)
    raw_lower_offset = raw_lower_result.value
    raw_upper_offset = raw_upper_result.value

    lower_offset = max(raw_lower_offset, 0.0) if clip_negative_offsets else raw_lower_offset
    upper_offset = max(raw_upper_offset, 0.0) if clip_negative_offsets else raw_upper_offset
    lower = yhat_test_arr - lower_offset
    upper = yhat_test_arr + upper_offset
    lower, upper, crossings = _ordered_bounds(lower, upper)

    return RegressionCPResult(
        lower=lower,
        upper=upper,
        radii=(upper - lower) / 2.0,
        thresholds={
            "lower_offset": float(lower_offset),
            "upper_offset": float(upper_offset),
        },
        metadata={
            "method": "split_tail",
            "alpha": alpha,
            "n_cal": len(y_cal_arr),
            "lower_tail_alpha": float(lower_tail_alpha),
            "upper_tail_alpha": float(upper_tail_alpha),
            "lower_tail_alpha_fraction": float(lower_tail_alpha_fraction),
            "raw_lower_offset": float(raw_lower_offset),
            "raw_upper_offset": float(raw_upper_offset),
            "negative_lower_offset_clipped": bool(
                clip_negative_offsets and raw_lower_offset < 0.0
            ),
            "negative_upper_offset_clipped": bool(
                clip_negative_offsets and raw_upper_offset < 0.0
            ),
            "clip_negative_offsets": bool(clip_negative_offsets),
            "interval_crossings_reordered": crossings,
            **_prefixed_quantile_metadata("lower_tail", raw_lower_result.metadata),
            **_prefixed_quantile_metadata("upper_tail", raw_upper_result.metadata),
            "coverage_note": (
                "two one-sided split conformal bounds with total tail alpha; "
                "negative signed offsets are conservatively clipped by default"
            ),
        },
    )


def split_tail_grid_shortest_interval(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    alpha: float,
    lower_tail_alpha_fractions: Iterable[float] = (0.10, 0.25, 0.50, 0.75, 0.90),
) -> RegressionCPResult:
    """Select the shortest fixed split-tail interval from a predeclared grid.

    This is a diagnostic runner method. It searches over fixed one-sided
    split-tail allocations using the calibration-implied interval width and
    returns the selected split-tail interval. Because the same calibration
    split is used for both allocation selection and conformal calibration, this
    helper must not be reported as full TA-CQR or as an independent
    finite-sample shortest-interval guarantee.
    """

    fractions_arr = np.array(list(lower_tail_alpha_fractions), dtype=float)
    if fractions_arr.ndim != 1 or len(fractions_arr) == 0:
        raise ValueError("lower_tail_alpha_fractions must be a non-empty 1D grid")
    if not np.all(np.isfinite(fractions_arr)):
        raise ValueError("lower_tail_alpha_fractions contains non-finite values")
    if np.any((fractions_arr <= 0.0) | (fractions_arr >= 1.0)):
        raise ValueError("all lower_tail_alpha_fractions must be in (0, 1)")

    unique_fractions = np.unique(fractions_arr)
    candidates = []
    for fraction in unique_fractions:
        result = split_tail_conformal_interval(
            y_cal=y_cal,
            yhat_cal=yhat_cal,
            yhat_test=yhat_test,
            alpha=alpha,
            lower_tail_alpha_fraction=float(fraction),
        )
        width = float(result.thresholds["lower_offset"] + result.thresholds["upper_offset"])
        candidates.append(
            {
                "fraction": float(fraction),
                "width": width,
                "lower_offset": float(result.thresholds["lower_offset"]),
                "upper_offset": float(result.thresholds["upper_offset"]),
                "result": result,
            }
        )

    selected = min(
        candidates,
        key=lambda row: (row["width"], abs(row["fraction"] - 0.5), row["fraction"]),
    )
    result = selected["result"]
    metadata = {
        **result.metadata,
        "method": "split_tail_grid_shortest",
        "base_method": "split_tail",
        "selected_lower_tail_alpha_fraction": float(selected["fraction"]),
        "tail_fraction_grid": [float(value) for value in unique_fractions],
        "candidate_widths": {
            f"{row['fraction']:.2f}": float(row["width"]) for row in candidates
        },
        "candidate_offsets": {
            f"{row['fraction']:.2f}": {
                "lower_offset": float(row["lower_offset"]),
                "upper_offset": float(row["upper_offset"]),
            }
            for row in candidates
        },
        "allocation_selection_role": "calibration_grid_min_width_diagnostic",
        "finite_sample_interval_claim": (
            "diagnostic split-tail allocation search; not full TA-CQR and not an "
            "independent finite-sample shortest-interval guarantee because the "
            "same calibration split selects and calibrates the allocation"
        ),
    }
    thresholds = {
        **result.thresholds,
        "selected_lower_tail_alpha_fraction": float(selected["fraction"]),
        "selected_grid_width": float(selected["width"]),
    }
    return RegressionCPResult(
        lower=result.lower,
        upper=result.upper,
        radii=result.radii,
        thresholds=thresholds,
        metadata=metadata,
    )


def tail_allocation_shortest_interval(
    y_tune: Iterable[float],
    yhat_tune: Iterable[float],
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    alpha: float,
    lower_tail_alpha_fractions: Iterable[float] = (0.10, 0.25, 0.50, 0.75, 0.90),
) -> RegressionCPResult:
    """Select a split-tail allocation on tuning data, then calibrate separately.

    The tuning split selects the shortest predeclared lower-tail allocation.
    The calibration split then constructs the final one-sided split conformal
    interval using only the selected allocation. This separates allocation
    selection from calibration and is therefore a reference primitive for
    shortest-tail allocation experiments. It is still not full TA-CQR because it
    does not fit quantile cores or optimize quantile-regression endpoints.
    """

    fractions_arr = np.array(list(lower_tail_alpha_fractions), dtype=float)
    if fractions_arr.ndim != 1 or len(fractions_arr) == 0:
        raise ValueError("lower_tail_alpha_fractions must be a non-empty 1D grid")
    if not np.all(np.isfinite(fractions_arr)):
        raise ValueError("lower_tail_alpha_fractions contains non-finite values")
    if np.any((fractions_arr <= 0.0) | (fractions_arr >= 1.0)):
        raise ValueError("all lower_tail_alpha_fractions must be in (0, 1)")

    y_tune_arr = _as_1d(y_tune, "y_tune")
    yhat_tune_arr = _as_1d(yhat_tune, "yhat_tune")
    if len(y_tune_arr) != len(yhat_tune_arr):
        raise ValueError("y_tune and yhat_tune must have the same length")
    if len(y_tune_arr) == 0:
        raise ValueError("y_tune and yhat_tune must contain at least one row")

    unique_fractions = np.unique(fractions_arr)
    tuning_candidates = []
    for fraction in unique_fractions:
        tuning_result = split_tail_conformal_interval(
            y_cal=y_tune_arr,
            yhat_cal=yhat_tune_arr,
            yhat_test=np.array([0.0]),
            alpha=alpha,
            lower_tail_alpha_fraction=float(fraction),
        )
        tuning_width = float(
            tuning_result.thresholds["lower_offset"]
            + tuning_result.thresholds["upper_offset"]
        )
        tuning_candidates.append(
            {
                "fraction": float(fraction),
                "tuning_width": tuning_width,
                "tuning_lower_offset": float(tuning_result.thresholds["lower_offset"]),
                "tuning_upper_offset": float(tuning_result.thresholds["upper_offset"]),
            }
        )

    selected = min(
        tuning_candidates,
        key=lambda row: (
            row["tuning_width"],
            abs(row["fraction"] - 0.5),
            row["fraction"],
        ),
    )
    result = split_tail_conformal_interval(
        y_cal=y_cal,
        yhat_cal=yhat_cal,
        yhat_test=yhat_test,
        alpha=alpha,
        lower_tail_alpha_fraction=float(selected["fraction"]),
    )
    metadata = {
        **result.metadata,
        "method": "tail_allocation_shortest_interval",
        "base_method": "split_tail",
        "selected_lower_tail_alpha_fraction": float(selected["fraction"]),
        "tail_fraction_grid": [float(value) for value in unique_fractions],
        "tuning_candidate_widths": {
            f"{row['fraction']:.2f}": float(row["tuning_width"])
            for row in tuning_candidates
        },
        "tuning_candidate_offsets": {
            f"{row['fraction']:.2f}": {
                "lower_offset": float(row["tuning_lower_offset"]),
                "upper_offset": float(row["tuning_upper_offset"]),
            }
            for row in tuning_candidates
        },
        "allocation_selection_role": "independent_tuning_split_min_width_reference",
        "n_tune": int(len(y_tune_arr)),
        "n_cal": int(result.metadata["n_cal"]),
        "implementation_role": "tuning_split_reference_not_broad_ta_cqr_runner",
        "finite_sample_interval_claim": (
            "reference split-tail allocation primitive; allocation is selected "
            "on an independent tuning split and the final interval is calibrated "
            "on a separate calibration split, but this is not full TA-CQR and "
            "does not fit quantile-defined cores"
        ),
    }
    thresholds = {
        **result.thresholds,
        "selected_lower_tail_alpha_fraction": float(selected["fraction"]),
        "selected_tuning_width": float(selected["tuning_width"]),
    }
    return RegressionCPResult(
        lower=result.lower,
        upper=result.upper,
        radii=result.radii,
        thresholds=thresholds,
        metadata=metadata,
    )


def mondrian_conformal_interval(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    groups_cal: Iterable,
    groups_test: Iterable,
    alpha: float,
    min_group_size: int = 20,
) -> RegressionCPResult:
    """Group-conditional split conformal intervals.

    Each calibration group gets its own residual radius. Small or unseen groups
    fall back to the global radius, and that fallback is recorded in metadata.
    """

    y_cal_arr = _as_1d(y_cal, "y_cal")
    yhat_cal_arr = _as_1d(yhat_cal, "yhat_cal")
    yhat_test_arr = _as_1d(yhat_test, "yhat_test")
    groups_cal_arr = np.asarray(groups_cal)
    groups_test_arr = np.asarray(groups_test)

    if len(y_cal_arr) != len(yhat_cal_arr) or len(y_cal_arr) != len(groups_cal_arr):
        raise ValueError("calibration arrays must have the same length")
    if len(yhat_test_arr) != len(groups_test_arr):
        raise ValueError("yhat_test and groups_test must have the same length")

    scores = np.abs(y_cal_arr - yhat_cal_arr)
    global_radius_result = finite_sample_quantile_result(scores, alpha)
    global_radius = global_radius_result.value
    radii = np.full_like(yhat_test_arr, global_radius, dtype=float)
    thresholds: Dict[str, float] = {"global": global_radius}
    fallback_groups = []

    for group in np.unique(groups_cal_arr):
        mask_cal = groups_cal_arr == group
        group_key = f"group_{group}"
        if int(mask_cal.sum()) < min_group_size:
            thresholds[group_key] = global_radius
            fallback_groups.append(str(group))
            continue

        radius = finite_sample_quantile_result(scores[mask_cal], alpha).value
        thresholds[group_key] = radius
        radii[groups_test_arr == group] = radius

    unseen = sorted(set(np.unique(groups_test_arr)) - set(np.unique(groups_cal_arr)))
    fallback_groups.extend(str(group) for group in unseen)

    return RegressionCPResult(
        lower=yhat_test_arr - radii,
        upper=yhat_test_arr + radii,
        radii=radii,
        thresholds=thresholds,
        metadata={
            "method": "mondrian_abs",
            "alpha": alpha,
            "n_cal": len(y_cal_arr),
            "min_group_size": min_group_size,
            "fallback_groups": fallback_groups,
            **_prefixed_quantile_metadata("global", global_radius_result.metadata),
        },
    )


def shrinkage_conformal_interval(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    groups_cal: Iterable,
    groups_test: Iterable,
    alpha: float,
    gamma: float = 0.5,
    min_group_size: int = 20,
) -> RegressionCPResult:
    """Interpolate residual radii between global and group-conditional CP."""

    if not 0 <= gamma <= 1:
        raise ValueError(f"gamma must be in [0, 1], got {gamma}")

    global_result = split_conformal_interval(y_cal, yhat_cal, yhat_test, alpha)
    group_result = mondrian_conformal_interval(
        y_cal,
        yhat_cal,
        yhat_test,
        groups_cal,
        groups_test,
        alpha,
        min_group_size=min_group_size,
    )

    radii = (1 - gamma) * global_result.radii + gamma * group_result.radii
    yhat_test_arr = _as_1d(yhat_test, "yhat_test")
    thresholds = dict(group_result.thresholds)
    thresholds["gamma"] = float(gamma)

    return RegressionCPResult(
        lower=yhat_test_arr - radii,
        upper=yhat_test_arr + radii,
        radii=radii,
        thresholds=thresholds,
        metadata={
            "method": "shrinkage_abs",
            "alpha": alpha,
            "gamma": gamma,
            "n_cal": len(_as_1d(y_cal, "y_cal")),
            "min_group_size": min_group_size,
        },
    )


def normalized_conformal_interval(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    scale_cal: Iterable[float],
    scale_test: Iterable[float],
    alpha: float,
    scale_floor: float = 1e-8,
) -> RegressionCPResult:
    """Locally scaled split conformal interval.

    ``scale_cal`` and ``scale_test`` come from a separately trained residual
    dispersion model. The calibrated score is |y-yhat| / scale.
    """

    y_cal_arr = _as_1d(y_cal, "y_cal")
    yhat_cal_arr = _as_1d(yhat_cal, "yhat_cal")
    yhat_test_arr = _as_1d(yhat_test, "yhat_test")
    scale_cal_arr = np.maximum(_as_1d(scale_cal, "scale_cal"), scale_floor)
    scale_test_arr = np.maximum(_as_1d(scale_test, "scale_test"), scale_floor)

    if len(y_cal_arr) != len(yhat_cal_arr) or len(y_cal_arr) != len(scale_cal_arr):
        raise ValueError("calibration arrays must have the same length")
    if len(yhat_test_arr) != len(scale_test_arr):
        raise ValueError("yhat_test and scale_test must have the same length")

    scores = np.abs(y_cal_arr - yhat_cal_arr) / scale_cal_arr
    scale_result = finite_sample_quantile_result(scores, alpha)
    scale_threshold = scale_result.value
    radii = scale_threshold * scale_test_arr

    return RegressionCPResult(
        lower=yhat_test_arr - radii,
        upper=yhat_test_arr + radii,
        radii=radii,
        thresholds={"normalized": scale_threshold},
        metadata={
            "method": "normalized_abs",
            "alpha": alpha,
            "n_cal": len(y_cal_arr),
            "scale_floor": scale_floor,
            **scale_result.metadata,
        },
    )


def conformalized_quantile_interval(
    y_cal: Iterable[float],
    lower_cal: Iterable[float],
    upper_cal: Iterable[float],
    lower_test: Iterable[float],
    upper_test: Iterable[float],
    alpha: float,
) -> RegressionCPResult:
    """Conformalized Quantile Regression (CQR).

    The calibration score is max(lower_hat - y, y - upper_hat). The fitted
    lower/upper quantile models must be trained outside this function.
    """

    y_cal_arr = _as_1d(y_cal, "y_cal")
    lower_cal_arr = _as_1d(lower_cal, "lower_cal")
    upper_cal_arr = _as_1d(upper_cal, "upper_cal")
    lower_test_arr = _as_1d(lower_test, "lower_test")
    upper_test_arr = _as_1d(upper_test, "upper_test")

    if len(y_cal_arr) != len(lower_cal_arr) or len(y_cal_arr) != len(upper_cal_arr):
        raise ValueError("calibration arrays must have the same length")
    if len(lower_test_arr) != len(upper_test_arr):
        raise ValueError("lower_test and upper_test must have the same length")

    lower_cal_arr, upper_cal_arr, cal_crossings = _ordered_bounds(lower_cal_arr, upper_cal_arr)
    lower_test_arr, upper_test_arr, test_crossings = _ordered_bounds(lower_test_arr, upper_test_arr)
    scores = np.maximum(lower_cal_arr - y_cal_arr, y_cal_arr - upper_cal_arr)
    correction_result = finite_sample_quantile_result(scores, alpha)
    raw_correction = correction_result.value
    correction = max(raw_correction, 0.0)
    lower = lower_test_arr - correction
    upper = upper_test_arr + correction

    return RegressionCPResult(
        lower=lower,
        upper=upper,
        radii=(upper - lower) / 2.0,
        thresholds={"cqr_correction": correction},
        metadata={
            "method": "cqr",
            "alpha": alpha,
            "n_cal": len(y_cal_arr),
            "raw_cqr_correction": raw_correction,
            "negative_correction_clipped": raw_correction < 0.0,
            "quantile_crossings_cal": cal_crossings,
            "quantile_crossings_test": test_crossings,
            **correction_result.metadata,
        },
    )


def _validate_ivar_m(n_cal: int, m: int | None) -> int:
    """Validate the unbounded IVAR tail-moderation parameter."""

    if n_cal < 3:
        raise ValueError("unbounded IVAR requires at least three calibration scores")
    max_m = (n_cal - 1) // 2
    chosen_m = 1 if m is None else int(m)
    if not 1 <= chosen_m <= max_m:
        raise ValueError(f"m must be in [1, {max_m}] for n_cal={n_cal}, got {chosen_m}")
    return chosen_m


def _isotonic_predict_at(
    base_cal: np.ndarray,
    labels_cal: np.ndarray,
    base_test_value: float,
    pseudo_label: float,
) -> float:
    x = np.concatenate([base_cal, np.array([base_test_value], dtype=float)])
    y = np.concatenate([labels_cal, np.array([pseudo_label], dtype=float)])
    model = IsotonicRegression(increasing=True, out_of_bounds="clip")
    model.fit(x, y)
    return float(model.predict(np.array([base_test_value], dtype=float))[0])


def unbounded_ivar_interval(
    base_cal: Iterable[float],
    labels_cal: Iterable[float],
    base_test: Iterable[float],
    m: int | None = 1,
) -> tuple[np.ndarray, np.ndarray, Dict]:
    """Unbounded inductive Venn-Abers regressor intervals.

    This implements the unbounded IVAR construction from Petej and Vovk
    (2026) using PAVA through scikit-learn's isotonic regression. The base
    values are scalar regression scores; labels are the scalar quantity being
    calibrated.
    """

    base_cal_arr = _as_1d(base_cal, "base_cal")
    labels_cal_arr = _as_1d(labels_cal, "labels_cal")
    base_test_arr = _as_1d(base_test, "base_test")
    if len(base_cal_arr) != len(labels_cal_arr):
        raise ValueError("base_cal and labels_cal must have the same length")

    chosen_m = _validate_ivar_m(len(labels_cal_arr), m)
    sorted_labels = np.sort(labels_cal_arr)

    upper_lower_clip = sorted_labels[chosen_m]
    upper_pseudo = sorted_labels[-chosen_m]
    upper_labels = np.clip(labels_cal_arr, upper_lower_clip, upper_pseudo)

    lower_upper_clip = sorted_labels[-chosen_m - 1]
    lower_pseudo = sorted_labels[chosen_m - 1]
    lower_labels = np.clip(labels_cal_arr, lower_pseudo, lower_upper_clip)

    lower = np.empty_like(base_test_arr, dtype=float)
    upper = np.empty_like(base_test_arr, dtype=float)
    for idx, base_value in enumerate(base_test_arr):
        upper[idx] = _isotonic_predict_at(
            base_cal_arr, upper_labels, float(base_value), float(upper_pseudo)
        )
        lower[idx] = _isotonic_predict_at(
            base_cal_arr, lower_labels, float(base_value), float(lower_pseudo)
        )

    lower, upper, crossings = _ordered_bounds(lower, upper)
    metadata = {
        "ivar_variant": "unbounded",
        "m": chosen_m,
        "n_cal": len(labels_cal_arr),
        "lower_pseudo_label": float(lower_pseudo),
        "upper_pseudo_label": float(upper_pseudo),
        "interval_crossings_reordered": crossings,
    }
    return lower, upper, metadata


def venn_abers_quantile_interval(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    residual_quantile_cal: Iterable[float],
    residual_quantile_test: Iterable[float],
    alpha: float,
    m: int | None = 1,
    radius_floor: float = 0.0,
) -> RegressionCPResult:
    """Venn-Abers quantile-calibrated residual interval.

    The calibrated object is the absolute-residual conformity score. A model
    first predicts the ``1 - alpha`` residual quantile; unbounded IVAR then
    calibrates those scalar quantile scores. The reported prediction interval
    is symmetric around ``yhat_test`` using the upper IVAR endpoint as radius.
    """

    _validate_alpha(alpha)
    y_cal_arr = _as_1d(y_cal, "y_cal")
    yhat_cal_arr = _as_1d(yhat_cal, "yhat_cal")
    yhat_test_arr = _as_1d(yhat_test, "yhat_test")
    q_cal_arr = _as_1d(residual_quantile_cal, "residual_quantile_cal")
    q_test_arr = _as_1d(residual_quantile_test, "residual_quantile_test")
    if len(y_cal_arr) != len(yhat_cal_arr) or len(y_cal_arr) != len(q_cal_arr):
        raise ValueError("calibration arrays must have the same length")
    if len(yhat_test_arr) != len(q_test_arr):
        raise ValueError("yhat_test and residual_quantile_test must have the same length")

    scores = np.abs(y_cal_arr - yhat_cal_arr)
    lower_radius, upper_radius, ivar_metadata = unbounded_ivar_interval(
        base_cal=q_cal_arr,
        labels_cal=scores,
        base_test=q_test_arr,
        m=m,
    )
    radii = np.maximum(upper_radius, radius_floor)

    return RegressionCPResult(
        lower=yhat_test_arr - radii,
        upper=yhat_test_arr + radii,
        radii=radii,
        thresholds={
            "mean_lower_ivar_radius": float(lower_radius.mean()),
            "mean_upper_ivar_radius": float(upper_radius.mean()),
            "radius_floor": float(radius_floor),
        },
        metadata={
            "method": "venn_abers_quantile",
            "alpha": alpha,
            "n_cal": len(y_cal_arr),
            "calibrated_object": "absolute_residual_conformity_score",
            "base_score_model": "external_1_minus_alpha_residual_quantile_model",
            "interval_extraction": "symmetric_interval_using_upper_ivar_radius",
            "finite_sample_interval_claim": (
                "experimental_runner_bridge; validate against exact transductive "
                "candidate-grid Venn-Abers quantile calibration before headline use"
            ),
            **ivar_metadata,
        },
    )


def venn_abers_split_fallback_envelope(
    bridge: RegressionCPResult,
    split: RegressionCPResult,
    yhat_test: Iterable[float],
    alpha: float | None = None,
) -> RegressionCPResult:
    """Envelope a Venn-Abers bridge interval with split-conformal radii."""

    yhat_test_arr = _as_1d(yhat_test, "yhat_test")
    if not (len(yhat_test_arr) == len(bridge.radii) == len(split.radii)):
        raise ValueError("bridge, split, and yhat_test must have the same length")

    radii = np.maximum(np.asarray(bridge.radii, dtype=float), np.asarray(split.radii, dtype=float))
    split_active = np.asarray(split.radii, dtype=float) >= np.asarray(bridge.radii, dtype=float)
    metadata = {
        "method": "venn_abers_split_fallback",
        "bridge_method": bridge.metadata.get("method"),
        "fallback_method": split.metadata.get("method"),
        "split_active_rate": float(np.mean(split_active)),
        "calibration_only_fallback": True,
        "finite_sample_interval_claim": (
            "inherits ordinary split-conformal safety envelope; the "
            "Venn-Abers bridge remains diagnostic unless separately "
            "validated against the exact grid target"
        ),
    }
    if alpha is not None:
        metadata["alpha"] = float(alpha)
    if "n_cal" in split.metadata:
        metadata["n_cal"] = split.metadata["n_cal"]

    return RegressionCPResult(
        lower=yhat_test_arr - radii,
        upper=yhat_test_arr + radii,
        radii=radii,
        thresholds={
            "split_fallback_radius": float(np.max(split.radii)),
            "mean_bridge_radius": float(np.mean(bridge.radii)),
            "mean_fallback_radius": float(np.mean(radii)),
        },
        metadata=metadata,
    )


def venn_abers_split_fallback_interval(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    residual_quantile_cal: Iterable[float],
    residual_quantile_test: Iterable[float],
    alpha: float,
    m: int | None = 1,
) -> RegressionCPResult:
    """Venn-Abers quantile bridge with a split-conformal safety envelope.

    The fast Venn-Abers residual-quantile bridge has repeatedly undercovered in
    real-data diagnostics. This helper keeps the bridge radius when it is larger
    than the ordinary split-conformal radius and otherwise falls back to the
    split radius. The finite-sample coverage claim therefore comes from the
    split-conformal envelope, not from a validated Venn-Abers regression
    interval construction.
    """

    bridge = venn_abers_quantile_interval(
        y_cal=y_cal,
        yhat_cal=yhat_cal,
        yhat_test=yhat_test,
        residual_quantile_cal=residual_quantile_cal,
        residual_quantile_test=residual_quantile_test,
        alpha=alpha,
        m=m,
    )
    split = split_conformal_interval(y_cal, yhat_cal, yhat_test, alpha)
    return venn_abers_split_fallback_envelope(
        bridge=bridge,
        split=split,
        yhat_test=yhat_test,
        alpha=alpha,
    )


def venn_abers_quantile_grid_interval(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: Iterable[float],
    residual_quantile_cal: Iterable[float],
    residual_quantile_test: Iterable[float],
    score_grid: Iterable[float],
    alpha: float,
) -> RegressionCPResult:
    """Exact candidate-grid Venn-Abers quantile-calibration reference.

    This transductive reference augments the calibration set with each
    candidate residual score, refits monotone quantile calibration under
    pinball loss, and accepts candidate scores satisfying
    ``score <= calibrated_score``. It is intentionally grid-based and intended
    for small validation problems, not production sweeps.
    """

    _validate_alpha(alpha)
    y_cal_arr = _as_1d(y_cal, "y_cal")
    yhat_cal_arr = _as_1d(yhat_cal, "yhat_cal")
    yhat_test_arr = _as_1d(yhat_test, "yhat_test")
    q_cal_arr = _as_1d(residual_quantile_cal, "residual_quantile_cal")
    q_test_arr = _as_1d(residual_quantile_test, "residual_quantile_test")
    grid_arr = np.unique(_as_1d(score_grid, "score_grid"))
    if len(y_cal_arr) != len(yhat_cal_arr) or len(y_cal_arr) != len(q_cal_arr):
        raise ValueError("calibration arrays must have the same length")
    if len(yhat_test_arr) != len(q_test_arr):
        raise ValueError("yhat_test and residual_quantile_test must have the same length")
    if len(grid_arr) == 0:
        raise ValueError("score_grid must contain at least one candidate")
    if np.any(grid_arr < 0):
        raise ValueError("score_grid candidates must be nonnegative residual scores")

    quantile_level = 1.0 - alpha
    scores = np.abs(y_cal_arr - yhat_cal_arr)
    radii = np.empty_like(yhat_test_arr, dtype=float)
    accepted_counts = []
    rejected_counts = []
    calibrated_grid_by_test = []

    for test_idx, q_test in enumerate(q_test_arr):
        accepted = []
        calibrated_values = []
        for candidate_score in grid_arr:
            calibrated, _ = isotonic_quantile_fit_predict(
                x=np.concatenate([q_cal_arr, np.array([q_test], dtype=float)]),
                y=np.concatenate([scores, np.array([candidate_score], dtype=float)]),
                x_eval=np.array([q_test], dtype=float),
                quantile=quantile_level,
            )
            calibrated_score = float(calibrated[0])
            calibrated_values.append(calibrated_score)
            if candidate_score <= calibrated_score:
                accepted.append(float(candidate_score))

        if not accepted:
            raise ValueError(
                f"no accepted Venn-Abers score candidates for test index {test_idx}; "
                "expand or refine score_grid"
            )
        radii[test_idx] = max(accepted)
        accepted_counts.append(len(accepted))
        rejected_counts.append(int(len(grid_arr) - len(accepted)))
        calibrated_grid_by_test.append([float(value) for value in calibrated_values])

    return RegressionCPResult(
        lower=yhat_test_arr - radii,
        upper=yhat_test_arr + radii,
        radii=radii,
        thresholds={
            "mean_grid_radius": float(radii.mean()),
            "max_grid_radius": float(radii.max()),
        },
        metadata={
            "method": "venn_abers_quantile_grid",
            "alpha": alpha,
            "quantile_level": quantile_level,
            "n_cal": len(y_cal_arr),
            "grid_size": len(grid_arr),
            "score_grid": [float(value) for value in grid_arr],
            "accepted_counts": accepted_counts,
            "rejected_counts": rejected_counts,
            "calibrated_grid_by_test": calibrated_grid_by_test,
            "calibrated_object": "absolute_residual_conformity_score",
            "implementation_role": "tiny_grid_reference_not_runner_method",
            "interval_extraction": "symmetric_interval_using_max_accepted_score_grid_value",
        },
    )


def jackknife_plus_interval(
    y_train: Iterable[float],
    yhat_train_loo: Iterable[float],
    yhat_test_loo: np.ndarray,
    alpha: float,
) -> RegressionCPResult:
    """Jackknife+ interval from leave-one-out predictions.

    Parameters
    ----------
    y_train:
        Observed training responses.
    yhat_train_loo:
        Leave-one-out prediction for each training response.
    yhat_test_loo:
        Matrix with shape ``(n_train, n_test)`` where row ``i`` is the test
        prediction from the model that excluded training row ``i``.
    alpha:
        Target miscoverage.
    """

    _validate_alpha(alpha)
    y_train_arr = _as_1d(y_train, "y_train")
    yhat_train_arr = _as_1d(yhat_train_loo, "yhat_train_loo")
    test_preds = np.asarray(yhat_test_loo, dtype=float)
    if test_preds.ndim != 2:
        raise ValueError(f"yhat_test_loo must be 2D, got shape {test_preds.shape}")
    if len(y_train_arr) != len(yhat_train_arr) or len(y_train_arr) != test_preds.shape[0]:
        raise ValueError("train arrays and yhat_test_loo rows must have the same length")
    if not np.all(np.isfinite(test_preds)):
        raise ValueError("yhat_test_loo contains non-finite values")

    residuals = np.abs(y_train_arr - yhat_train_arr)
    lower_candidates = test_preds - residuals[:, None]
    upper_candidates = test_preds + residuals[:, None]
    lower, upper, plus_metadata = _bcrt_plus_quantiles(
        lower_candidates, upper_candidates, alpha
    )

    return RegressionCPResult(
        lower=lower,
        upper=upper,
        radii=(upper - lower) / 2.0,
        thresholds={},
        metadata={
            "method": "jackknife_plus",
            "alpha": alpha,
            "n_train": len(y_train_arr),
            **plus_metadata,
        },
    )


def jackknife_minmax_interval(
    y_train: Iterable[float],
    yhat_train_loo: Iterable[float],
    yhat_test_loo: np.ndarray,
    alpha: float,
) -> RegressionCPResult:
    """Jackknife-minmax interval from leave-one-out predictions.

    This is the conservative Barber-Candes-Ramdas-Tibshirani minmax variant:
    the residual radius is the finite-sample quantile of leave-one-out
    residuals, while the center envelope uses the minimum and maximum
    leave-one-out test predictions.
    """

    _validate_alpha(alpha)
    y_train_arr = _as_1d(y_train, "y_train")
    yhat_train_arr = _as_1d(yhat_train_loo, "yhat_train_loo")
    test_preds = np.asarray(yhat_test_loo, dtype=float)
    if test_preds.ndim != 2:
        raise ValueError(f"yhat_test_loo must be 2D, got shape {test_preds.shape}")
    if len(y_train_arr) != len(yhat_train_arr) or len(y_train_arr) != test_preds.shape[0]:
        raise ValueError("train arrays and yhat_test_loo rows must have the same length")
    if not np.all(np.isfinite(test_preds)):
        raise ValueError("yhat_test_loo contains non-finite values")

    residuals = np.abs(y_train_arr - yhat_train_arr)
    radius_result = finite_sample_quantile_result(residuals, alpha)
    residual_radius = radius_result.value
    lower = np.min(test_preds, axis=0) - residual_radius
    upper = np.max(test_preds, axis=0) + residual_radius

    return RegressionCPResult(
        lower=lower,
        upper=upper,
        radii=(upper - lower) / 2.0,
        thresholds={"residual_radius": residual_radius},
        metadata={
            "method": "jackknife_minmax",
            "alpha": alpha,
            "n_train": len(y_train_arr),
            "variant": "minmax",
            **radius_result.metadata,
        },
    )


def jackknife_after_bootstrap_interval(
    y_train: Iterable[float],
    yhat_train_oob: Iterable[float],
    yhat_test_oob: np.ndarray,
    alpha: float,
    oob_counts: Iterable[float] | None = None,
) -> RegressionCPResult:
    """Jackknife+-after-bootstrap interval from out-of-bag aggregations.

    The caller supplies, for each training row, the prediction aggregated over
    bootstrap models that did not train on that row. The test prediction matrix
    has the same row semantics and is passed through the jackknife+ envelope.
    """

    result = jackknife_plus_interval(
        y_train=y_train,
        yhat_train_loo=yhat_train_oob,
        yhat_test_loo=yhat_test_oob,
        alpha=alpha,
    )
    metadata = {
        "method": "jackknife_plus_after_bootstrap",
        "alpha": alpha,
        "n_train": len(_as_1d(y_train, "y_train")),
        "coverage_note": (
            "J+aB uses bootstrap out-of-bag aggregations as approximate "
            "leave-one-out predictors; assumption-free worst-case guarantee is "
            "1-2alpha under the Kim-Xu-Barber randomized resampling setup"
        ),
    }
    thresholds = dict(result.thresholds)
    if oob_counts is not None:
        counts_arr = _as_1d(oob_counts, "oob_counts")
        if len(counts_arr) != metadata["n_train"]:
            raise ValueError("oob_counts must have one value per training row")
        if np.any(counts_arr <= 0):
            raise ValueError("oob_counts must be positive")
        metadata.update(
            {
                "min_oob_count": int(np.min(counts_arr)),
                "max_oob_count": int(np.max(counts_arr)),
                "mean_oob_count": float(np.mean(counts_arr)),
            }
        )
        thresholds["mean_oob_count"] = float(np.mean(counts_arr))

    return RegressionCPResult(
        lower=result.lower,
        upper=result.upper,
        radii=result.radii,
        thresholds=thresholds,
        metadata=metadata,
    )


def cv_plus_interval(
    y_train: Iterable[float],
    yhat_train_oof: Iterable[float],
    yhat_test_by_fold: np.ndarray,
    fold_ids: Iterable[int],
    alpha: float,
) -> RegressionCPResult:
    """CV+ interval from out-of-fold and fold-specific test predictions.

    ``yhat_test_by_fold`` has shape ``(n_folds, n_test)``. Each training row
    uses the test predictions from the model that did not train on that row's
    fold, matching the CV+ construction.
    """

    fold_ids_arr = np.asarray(fold_ids)
    unique_folds = np.unique(fold_ids_arr)
    test_by_fold = np.asarray(yhat_test_by_fold, dtype=float)
    if test_by_fold.ndim != 2:
        raise ValueError(f"yhat_test_by_fold must be 2D, got shape {test_by_fold.shape}")
    if len(unique_folds) != test_by_fold.shape[0]:
        raise ValueError("number of unique fold_ids must match yhat_test_by_fold rows")

    y_train_arr = _as_1d(y_train, "y_train")
    yhat_train_arr = _as_1d(yhat_train_oof, "yhat_train_oof")
    if len(y_train_arr) != len(yhat_train_arr) or len(y_train_arr) != len(fold_ids_arr):
        raise ValueError("train arrays and fold_ids must have the same length")

    fold_to_row = {fold: row for row, fold in enumerate(unique_folds)}
    prediction_rows = np.fromiter(
        (fold_to_row[fold] for fold in fold_ids_arr),
        dtype=int,
        count=len(fold_ids_arr),
    )
    residuals = np.abs(y_train_arr - yhat_train_arr)
    n_test = test_by_fold.shape[1]
    lower = np.empty(n_test, dtype=float)
    upper = np.empty(n_test, dtype=float)
    max_candidate_bytes = 128 * 1024 * 1024
    chunk_size = max(1, min(n_test, max_candidate_bytes // max(1, len(y_train_arr) * 8)))
    plus_metadata: Dict = {}

    for start in range(0, n_test, chunk_size):
        stop = min(n_test, start + chunk_size)
        pred_chunk = test_by_fold[prediction_rows, start:stop]
        lower_candidates = pred_chunk - residuals[:, None]
        upper_candidates = pred_chunk + residuals[:, None]
        lower[start:stop], upper[start:stop], plus_metadata = _bcrt_plus_quantiles(
            lower_candidates, upper_candidates, alpha
        )

    return RegressionCPResult(
        lower=lower,
        upper=upper,
        radii=(upper - lower) / 2.0,
        thresholds={},
        metadata={
            "method": "cv_plus",
            "alpha": alpha,
            "n_train": len(y_train_arr),
            "n_folds": len(unique_folds),
            "candidate_chunk_size": int(chunk_size),
            **plus_metadata,
        },
    )


def cv_minmax_interval(
    y_train: Iterable[float],
    yhat_train_oof: Iterable[float],
    yhat_test_by_fold: np.ndarray,
    fold_ids: Iterable[int],
    alpha: float,
) -> RegressionCPResult:
    """CV-minmax interval from out-of-fold and fold-specific predictions."""

    fold_ids_arr = np.asarray(fold_ids)
    unique_folds = np.unique(fold_ids_arr)
    test_by_fold = np.asarray(yhat_test_by_fold, dtype=float)
    if test_by_fold.ndim != 2:
        raise ValueError(f"yhat_test_by_fold must be 2D, got shape {test_by_fold.shape}")
    if len(unique_folds) != test_by_fold.shape[0]:
        raise ValueError("number of unique fold_ids must match yhat_test_by_fold rows")

    y_train_arr = _as_1d(y_train, "y_train")
    yhat_train_arr = _as_1d(yhat_train_oof, "yhat_train_oof")
    if len(y_train_arr) != len(yhat_train_arr) or len(y_train_arr) != len(fold_ids_arr):
        raise ValueError("train arrays and fold_ids must have the same length")

    residuals = np.abs(y_train_arr - yhat_train_arr)
    radius_result = finite_sample_quantile_result(residuals, alpha)
    residual_radius = radius_result.value
    lower = np.min(test_by_fold, axis=0) - residual_radius
    upper = np.max(test_by_fold, axis=0) + residual_radius

    return RegressionCPResult(
        lower=lower,
        upper=upper,
        radii=(upper - lower) / 2.0,
        thresholds={"residual_radius": residual_radius},
        metadata={
            "method": "cv_minmax",
            "alpha": alpha,
            "n_train": len(y_train_arr),
            "n_folds": len(unique_folds),
            "variant": "minmax",
            **radius_result.metadata,
        },
    )


def cv_plus_grouped_interval(
    y_train: Iterable[float],
    yhat_train_oof: Iterable[float],
    yhat_test_by_fold: np.ndarray,
    fold_ids: Iterable[int],
    alpha: float,
) -> RegressionCPResult:
    """CV+ interval for predictions produced by group-held-out folds."""

    result = cv_plus_interval(
        y_train=y_train,
        yhat_train_oof=yhat_train_oof,
        yhat_test_by_fold=yhat_test_by_fold,
        fold_ids=fold_ids,
        alpha=alpha,
    )
    return RegressionCPResult(
        lower=result.lower,
        upper=result.upper,
        radii=result.radii,
        thresholds=result.thresholds,
        metadata={
            **result.metadata,
            "method": "cv_plus_grouped",
            "base_method": "cv_plus",
            "grouped_fold_input_contract": (
                "fold_ids must come from a split-group-preserving internal CV assignment"
            ),
        },
    )


def cv_minmax_grouped_interval(
    y_train: Iterable[float],
    yhat_train_oof: Iterable[float],
    yhat_test_by_fold: np.ndarray,
    fold_ids: Iterable[int],
    alpha: float,
) -> RegressionCPResult:
    """CV-minmax interval for predictions produced by group-held-out folds."""

    result = cv_minmax_interval(
        y_train=y_train,
        yhat_train_oof=yhat_train_oof,
        yhat_test_by_fold=yhat_test_by_fold,
        fold_ids=fold_ids,
        alpha=alpha,
    )
    return RegressionCPResult(
        lower=result.lower,
        upper=result.upper,
        radii=result.radii,
        thresholds=result.thresholds,
        metadata={
            **result.metadata,
            "method": "cv_minmax_grouped",
            "base_method": "cv_minmax",
            "grouped_fold_input_contract": (
                "fold_ids must come from a split-group-preserving internal CV assignment"
            ),
        },
    )


def _method_shrinkage_factory(gamma: float) -> Callable:
    def _method(**kwargs) -> RegressionCPResult:
        return shrinkage_conformal_interval(gamma=gamma, **kwargs)

    return _method


def _method_split_tail_factory(lower_tail_alpha_fraction: float) -> Callable:
    def _method(**kwargs) -> RegressionCPResult:
        return split_tail_conformal_interval(
            lower_tail_alpha_fraction=lower_tail_alpha_fraction,
            **kwargs,
        )

    return _method


REGRESSION_CP_METHODS: Dict[str, Callable[..., RegressionCPResult]] = {
    "split_abs": split_conformal_interval,
    "weighted_abs_covariate_shift": weighted_split_conformal_interval,
    "distributional_conformal_prediction": distributional_pit_conformal_interval,
    "full_conformal_regression": full_conformal_score_grid_interval,
    "rank_one_out_conformal": rank_one_out_score_grid_interval,
    "conformal_predictive_system": conformal_predictive_system_interval,
    "split_tail_0.25": _method_split_tail_factory(0.25),
    "split_tail_0.50": _method_split_tail_factory(0.50),
    "split_tail_0.75": _method_split_tail_factory(0.75),
    "split_tail_grid_shortest": split_tail_grid_shortest_interval,
    "tail_allocation_shortest_interval": tail_allocation_shortest_interval,
    "mondrian_abs": mondrian_conformal_interval,
    "normalized_abs": normalized_conformal_interval,
    "cqr": conformalized_quantile_interval,
    "venn_abers_quantile": venn_abers_quantile_interval,
    "venn_abers_split_fallback": venn_abers_split_fallback_interval,
    "jackknife_plus": jackknife_plus_interval,
    "jackknife_minmax": jackknife_minmax_interval,
    "jackknife_plus_after_bootstrap": jackknife_after_bootstrap_interval,
    "cv_plus": cv_plus_interval,
    "cv_minmax": cv_minmax_interval,
    "cv_plus_grouped": cv_plus_grouped_interval,
    "cv_minmax_grouped": cv_minmax_grouped_interval,
    "shrink_0.00": _method_shrinkage_factory(0.0),
    "shrink_0.10": _method_shrinkage_factory(0.1),
    "shrink_0.25": _method_shrinkage_factory(0.25),
    "shrink_0.50": _method_shrinkage_factory(0.5),
    "shrink_0.75": _method_shrinkage_factory(0.75),
    "shrink_0.90": _method_shrinkage_factory(0.9),
    "shrink_1.00": _method_shrinkage_factory(1.0),
}


def apply_regression_cp_method(method: str, **kwargs) -> RegressionCPResult:
    """Dispatch a named regression conformal method."""

    if method not in REGRESSION_CP_METHODS:
        raise ValueError(
            f"Unknown regression CP method: {method}. "
            f"Available: {sorted(REGRESSION_CP_METHODS)}"
        )
    return REGRESSION_CP_METHODS[method](**kwargs)


def get_regression_cp_methods() -> list[str]:
    """Return supported regression conformal method names."""

    return sorted(REGRESSION_CP_METHODS)
