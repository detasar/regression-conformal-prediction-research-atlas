"""Metrics for regression prediction intervals and group diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

import numpy as np


@dataclass(frozen=True)
class RegressionIntervalMetrics:
    """Summary metrics for prediction intervals."""

    coverage: float
    mean_width: float
    median_width: float
    normalized_mean_width: float
    interval_score: float
    lower_miss_rate: float
    upper_miss_rate: float
    coverage_by_group: Dict[str, float] = field(default_factory=dict)
    width_by_group: Dict[str, float] = field(default_factory=dict)
    coverage_gap: Optional[float] = None
    width_gap: Optional[float] = None


def _as_1d(values: Iterable[float], name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D array, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values")
    return arr


def winkler_interval_score(
    y_true: Iterable[float],
    lower: Iterable[float],
    upper: Iterable[float],
    alpha: float,
) -> float:
    """Mean Winkler interval score, lower is better."""

    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    y = _as_1d(y_true, "y_true")
    lo = _as_1d(lower, "lower")
    hi = _as_1d(upper, "upper")
    if not (len(y) == len(lo) == len(hi)):
        raise ValueError("y_true, lower, and upper must have the same length")
    if np.any(hi < lo):
        raise ValueError("upper interval bound is smaller than lower bound")

    below = y < lo
    above = y > hi
    score = (hi - lo).copy()
    score[below] += (2.0 / alpha) * (lo[below] - y[below])
    score[above] += (2.0 / alpha) * (y[above] - hi[above])
    return float(score.mean())


def compute_interval_metrics(
    y_true: Iterable[float],
    lower: Iterable[float],
    upper: Iterable[float],
    alpha: float,
    groups: Optional[Iterable] = None,
) -> RegressionIntervalMetrics:
    """Compute marginal and optional group-wise interval metrics."""

    y = _as_1d(y_true, "y_true")
    lo = _as_1d(lower, "lower")
    hi = _as_1d(upper, "upper")
    if not (len(y) == len(lo) == len(hi)):
        raise ValueError("y_true, lower, and upper must have the same length")
    if np.any(hi < lo):
        raise ValueError("upper interval bound is smaller than lower bound")

    covered = (lo <= y) & (y <= hi)
    widths = hi - lo
    y_iqr = np.subtract(*np.percentile(y, [75, 25]))
    if y_iqr <= 0:
        y_iqr = float(np.std(y)) or 1.0

    coverage_by_group: Dict[str, float] = {}
    width_by_group: Dict[str, float] = {}
    coverage_gap = None
    width_gap = None

    if groups is not None:
        groups_arr = np.asarray(groups)
        if len(groups_arr) != len(y):
            raise ValueError("groups must have the same length as y_true")
        for group in np.unique(groups_arr):
            mask = groups_arr == group
            if mask.any():
                group_key = str(group)
                coverage_by_group[group_key] = float(covered[mask].mean())
                width_by_group[group_key] = float(widths[mask].mean())
        if len(coverage_by_group) >= 2:
            coverage_values = list(coverage_by_group.values())
            width_values = list(width_by_group.values())
            coverage_gap = float(max(coverage_values) - min(coverage_values))
            width_gap = float(max(width_values) - min(width_values))

    return RegressionIntervalMetrics(
        coverage=float(covered.mean()),
        mean_width=float(widths.mean()),
        median_width=float(np.median(widths)),
        normalized_mean_width=float(widths.mean() / y_iqr),
        interval_score=winkler_interval_score(y, lo, hi, alpha),
        lower_miss_rate=float((y < lo).mean()),
        upper_miss_rate=float((y > hi).mean()),
        coverage_by_group=coverage_by_group,
        width_by_group=width_by_group,
        coverage_gap=coverage_gap,
        width_gap=width_gap,
    )
