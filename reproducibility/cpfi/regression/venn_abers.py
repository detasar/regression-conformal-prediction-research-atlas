"""Venn-Abers predictive-distribution prototypes for regression.

This module is intentionally separate from :mod:`cpfi.regression.conformal`.
The objects here are predictive distributions, not conformal intervals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.isotonic import IsotonicRegression


@dataclass(frozen=True)
class BinaryVennAbersResult:
    """Binary Venn-Abers probability interval for one test score."""

    lower: float
    upper: float
    midpoint: float
    metadata: dict


@dataclass(frozen=True)
class IVAPDPredictiveDistribution:
    """Threshold-grid predictive CDF prototype for IVAPD regression."""

    thresholds: np.ndarray
    lower_cdf: np.ndarray
    upper_cdf: np.ndarray
    midpoint_cdf: np.ndarray
    metadata: dict

    def quantile(self, probability: float, source: str = "midpoint") -> float:
        """Return the first threshold whose selected CDF reaches probability."""

        if not 0 <= probability <= 1:
            raise ValueError(f"probability must be in [0, 1], got {probability}")
        cdf = self._cdf(source)
        idx = int(np.searchsorted(cdf, probability, side="left"))
        return float(self.thresholds[min(idx, len(self.thresholds) - 1)])

    def interval(self, alpha: float, source: str = "midpoint") -> tuple[float, float]:
        """Return central interval endpoints from the selected CDF."""

        if not 0 < alpha < 1:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        return (
            self.quantile(alpha / 2.0, source=source),
            self.quantile(1.0 - alpha / 2.0, source=source),
        )

    def _cdf(self, source: str) -> np.ndarray:
        if source == "lower":
            return self.lower_cdf
        if source == "upper":
            return self.upper_cdf
        if source == "midpoint":
            return self.midpoint_cdf
        raise ValueError("source must be one of: lower, upper, midpoint")


def _as_1d(values: Iterable[float], name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D array, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values")
    return arr


def _monotone_unit(values: np.ndarray) -> np.ndarray:
    return np.maximum.accumulate(np.clip(values, 0.0, 1.0))


def threshold_grid_crps(
    y_true: float,
    thresholds: Iterable[float],
    cdf_values: Iterable[float],
) -> float:
    """Approximate CRPS for a scalar outcome over a threshold CDF grid.

    The continuous ranked probability score is
    ``integral (F(t) - 1{y <= t})^2 dt``. This helper computes a deterministic
    trapezoidal approximation over an already chosen threshold grid.
    """

    grid = _as_1d(thresholds, "thresholds")
    cdf = _as_1d(cdf_values, "cdf_values")
    if len(grid) != len(cdf):
        raise ValueError("thresholds and cdf_values must have the same length")
    if len(grid) < 2:
        raise ValueError("thresholds must contain at least two values for grid CRPS")
    if np.any(np.diff(grid) <= 0):
        raise ValueError("thresholds must be strictly increasing")
    if np.any(cdf < -1e-12) or np.any(cdf > 1.0 + 1e-12):
        raise ValueError("cdf_values must be in [0, 1]")
    if np.any(np.diff(cdf) < -1e-12):
        raise ValueError("cdf_values must be nondecreasing")
    outcome = float(y_true)
    if not np.isfinite(outcome):
        raise ValueError("y_true must be finite")

    clipped_cdf = np.clip(cdf, 0.0, 1.0)
    observed_cdf = (grid >= outcome).astype(float)
    squared_error = np.square(clipped_cdf - observed_cdf)
    integrate = getattr(np, "trapezoid", None)
    if integrate is None:
        integrate = np.trapz
    return float(integrate(squared_error, grid))


def ivapd_distribution_metrics(
    distribution: IVAPDPredictiveDistribution,
    y_true: float,
    alpha: float = 0.2,
) -> dict:
    """Score an IVAPD threshold-grid predictive distribution for one outcome."""

    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    outcome = float(y_true)
    if not np.isfinite(outcome):
        raise ValueError("y_true must be finite")

    lower_crps = threshold_grid_crps(outcome, distribution.thresholds, distribution.lower_cdf)
    midpoint_crps = threshold_grid_crps(
        outcome,
        distribution.thresholds,
        distribution.midpoint_cdf,
    )
    upper_crps = threshold_grid_crps(outcome, distribution.thresholds, distribution.upper_cdf)
    interval_lower, interval_upper = distribution.interval(alpha=alpha, source="midpoint")
    band_width = np.asarray(distribution.upper_cdf - distribution.lower_cdf, dtype=float)

    return {
        "method": "ivapd_threshold_grid_metrics",
        "distribution_method": distribution.metadata.get("method"),
        "alpha": float(alpha),
        "y_true": outcome,
        "lower_crps": lower_crps,
        "midpoint_crps": midpoint_crps,
        "upper_crps": upper_crps,
        "cdf_band_mean_width": float(np.mean(band_width)),
        "cdf_band_max_width": float(np.max(band_width)),
        "central_interval_lower": float(interval_lower),
        "central_interval_upper": float(interval_upper),
        "covered_by_midpoint_interval": bool(interval_lower <= outcome <= interval_upper),
        "grid_size": int(len(distribution.thresholds)),
    }


def binary_venn_abers_probability_interval(
    scores_cal: Iterable[float],
    labels_cal: Iterable[int],
    score_test: float,
) -> BinaryVennAbersResult:
    """Return binary Venn-Abers probability interval for class 1.

    The function appends the test score with candidate labels 0 and 1, fits
    isotonic calibration for each augmented set, and returns the two calibrated
    probabilities at the test score.
    """

    scores = _as_1d(scores_cal, "scores_cal")
    labels = _as_1d(labels_cal, "labels_cal")
    if len(scores) != len(labels):
        raise ValueError("scores_cal and labels_cal must have the same length")
    if len(scores) == 0:
        raise ValueError("calibration arrays must contain at least one row")
    if not np.all((labels == 0.0) | (labels == 1.0)):
        raise ValueError("labels_cal must contain only binary 0/1 labels")
    test_score = float(score_test)
    if not np.isfinite(test_score):
        raise ValueError("score_test must be finite")

    candidate_probs = []
    for candidate_label in (0.0, 1.0):
        aug_scores = np.concatenate([scores, np.array([test_score], dtype=float)])
        aug_labels = np.concatenate([labels, np.array([candidate_label], dtype=float)])
        model = IsotonicRegression(increasing=True, out_of_bounds="clip", y_min=0.0, y_max=1.0)
        model.fit(aug_scores, aug_labels)
        candidate_probs.append(float(model.predict(np.array([test_score], dtype=float))[0]))

    lower, upper = sorted(candidate_probs)
    return BinaryVennAbersResult(
        lower=lower,
        upper=upper,
        midpoint=(lower + upper) / 2.0,
        metadata={
            "method": "binary_venn_abers_probability_interval",
            "n_cal": int(len(scores)),
            "score_test": test_score,
            "candidate_probabilities": candidate_probs,
        },
    )


def ivapd_threshold_grid(
    y_cal: Iterable[float],
    yhat_cal: Iterable[float],
    yhat_test: float,
    thresholds: Iterable[float],
) -> IVAPDPredictiveDistribution:
    """Build a threshold-grid IVAPD regression predictive CDF prototype.

    For every threshold ``t``, the binary event is ``Y <= t``. The score for
    each object is ``t - yhat`` so larger scores imply a larger base belief that
    the response is below the threshold. Binary Venn-Abers calibration is then
    applied independently at each threshold, and the resulting CDF bands are
    monotonized over the threshold grid.
    """

    y = _as_1d(y_cal, "y_cal")
    yhat = _as_1d(yhat_cal, "yhat_cal")
    grid = np.unique(_as_1d(thresholds, "thresholds"))
    if len(y) != len(yhat):
        raise ValueError("y_cal and yhat_cal must have the same length")
    if len(grid) == 0:
        raise ValueError("thresholds must contain at least one value")
    test_pred = float(yhat_test)
    if not np.isfinite(test_pred):
        raise ValueError("yhat_test must be finite")

    lower = []
    upper = []
    midpoint = []
    threshold_metadata = []
    for threshold in grid:
        labels = (y <= threshold).astype(float)
        scores = threshold - yhat
        result = binary_venn_abers_probability_interval(
            scores_cal=scores,
            labels_cal=labels,
            score_test=float(threshold - test_pred),
        )
        lower.append(result.lower)
        upper.append(result.upper)
        midpoint.append(result.midpoint)
        threshold_metadata.append(
            {
                "threshold": float(threshold),
                "positive_count": int(labels.sum()),
                "lower": result.lower,
                "upper": result.upper,
            }
        )

    lower_arr = _monotone_unit(np.asarray(lower, dtype=float))
    upper_arr = _monotone_unit(np.maximum(np.asarray(upper, dtype=float), lower_arr))
    midpoint_arr = _monotone_unit(np.asarray(midpoint, dtype=float))
    midpoint_arr = np.minimum(np.maximum(midpoint_arr, lower_arr), upper_arr)

    return IVAPDPredictiveDistribution(
        thresholds=grid,
        lower_cdf=lower_arr,
        upper_cdf=upper_arr,
        midpoint_cdf=midpoint_arr,
        metadata={
            "method": "ivapd_threshold_grid",
            "prototype_role": "threshold_grid_predictive_distribution_not_interval_cp",
            "n_cal": int(len(y)),
            "grid_size": int(len(grid)),
            "thresholds": [float(value) for value in grid],
            "threshold_metadata": threshold_metadata,
            "base_score": "threshold_minus_point_prediction",
        },
    )
