"""
Cresswell Mechanism Metrics Module

The Cresswell mechanism states:
    Equalizing coverage across groups → Unequal set sizes → Unequal outcomes

This module computes metrics to quantify and validate this mechanism:
- Set size fairness metrics
- Coverage-decision trade-off scores
- Pareto frontier position

Reference: Cresswell et al., "Impossibility of Exact Equalized Odds in Decision-Making"
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)


def compute_cresswell_metrics(
    coverage_gap: float,
    set_size_gap: float,
    eo_gap: float,
    prefix: str = ""
) -> Dict[str, float]:
    """
    Compute Cresswell trade-off metrics.

    Parameters
    ----------
    coverage_gap : float
        Coverage gap between groups (|cov_g0 - cov_g1|)
    set_size_gap : float
        Set size gap between groups (|ss_g0 - ss_g1|)
    eo_gap : float
        Equalized odds gap (max(fpr_gap, fnr_gap))

    Returns
    -------
    dict
        Cresswell trade-off metrics
    """
    metrics = {}

    # Cresswell ratio: how much set size increases per unit coverage decrease
    if coverage_gap > 0:
        metrics[f"{prefix}cresswell_ratio"] = set_size_gap / coverage_gap
    else:
        metrics[f"{prefix}cresswell_ratio"] = np.nan

    # Coverage-decision trade-off score (lower is better)
    # This is a simple linear combination - could be weighted
    metrics[f"{prefix}coverage_decision_score"] = coverage_gap + eo_gap

    # Normalized trade-off (for comparing across datasets)
    metrics[f"{prefix}coverage_gap_norm"] = coverage_gap
    metrics[f"{prefix}eo_gap_norm"] = eo_gap

    # Direction indicators
    metrics[f"{prefix}coverage_favors_mondrian"] = 1 if coverage_gap < 0.02 else 0
    metrics[f"{prefix}decision_favors_global"] = 1 if eo_gap > 0.06 else 0

    return metrics


def compute_set_size_fairness(
    set_sizes: np.ndarray,
    sensitive_attr: np.ndarray,
    prefix: str = ""
) -> Dict[str, float]:
    """
    Compute set-size related fairness metrics.

    Parameters
    ----------
    set_sizes : np.ndarray
        Prediction set sizes (1 = singleton, 2 = both classes, 0 = empty)
    sensitive_attr : np.ndarray
        Sensitive attribute values

    Returns
    -------
    dict
        Set size fairness metrics
    """
    metrics = {}

    groups = np.unique(sensitive_attr[~np.isnan(sensitive_attr)])

    # Per-group metrics
    for g in groups:
        mask = sensitive_attr == g
        ss_g = set_sizes[mask]
        g_label = f"g{int(g)}"

        metrics[f"{prefix}{g_label}_avg_set_size"] = ss_g.mean()
        metrics[f"{prefix}{g_label}_singleton_rate"] = (ss_g == 1).mean()
        metrics[f"{prefix}{g_label}_both_rate"] = (ss_g == 2).mean()
        metrics[f"{prefix}{g_label}_empty_rate"] = (ss_g == 0).mean()
        metrics[f"{prefix}{g_label}_defer_rate"] = (ss_g > 1).mean()  # Both = defer

    # Gaps (assuming binary groups)
    if len(groups) == 2:
        g0, g1 = sorted(groups)
        ss_g0 = set_sizes[sensitive_attr == g0]
        ss_g1 = set_sizes[sensitive_attr == g1]

        # Average set size gap
        avg_ss_g0 = ss_g0.mean()
        avg_ss_g1 = ss_g1.mean()
        metrics[f"{prefix}set_size_gap"] = abs(avg_ss_g0 - avg_ss_g1)

        # Set size ratio (for measuring disparity magnitude)
        if min(avg_ss_g0, avg_ss_g1) > 0:
            metrics[f"{prefix}set_size_ratio"] = max(avg_ss_g0, avg_ss_g1) / min(avg_ss_g0, avg_ss_g1)
        else:
            metrics[f"{prefix}set_size_ratio"] = np.nan

        # Defer rate gap
        defer_g0 = (ss_g0 > 1).mean()
        defer_g1 = (ss_g1 > 1).mean()
        metrics[f"{prefix}defer_gap"] = abs(defer_g0 - defer_g1)

        # Singleton rate gap
        sing_g0 = (ss_g0 == 1).mean()
        sing_g1 = (ss_g1 == 1).mean()
        metrics[f"{prefix}singleton_gap"] = abs(sing_g0 - sing_g1)

    return metrics


def compute_trade_off_score(
    coverage_gap: float,
    eo_gap: float,
    coverage_weight: float = 0.5,
    decision_weight: float = 0.5
) -> float:
    """
    Compute a weighted trade-off score.

    Lower score is better. The weights determine the relative importance
    of coverage fairness vs decision fairness.

    Parameters
    ----------
    coverage_gap : float
        Coverage gap
    eo_gap : float
        Equalized odds gap
    coverage_weight : float
        Weight for coverage fairness (0-1)
    decision_weight : float
        Weight for decision fairness (0-1)

    Returns
    -------
    float
        Weighted trade-off score
    """
    return coverage_weight * coverage_gap + decision_weight * eo_gap


def compute_pareto_position(
    coverage_gaps: np.ndarray,
    eo_gaps: np.ndarray,
    coverage_gap: float,
    eo_gap: float
) -> int:
    """
    Compute position on Pareto frontier.

    Returns
    -------
    int
        Rank (1 = on frontier, higher = dominated by more points)
    """
    # Count how many points dominate this one
    # A point dominates if it's better on BOTH metrics
    n_dominating = 0
    for cg, eg in zip(coverage_gaps, eo_gaps):
        if cg < coverage_gap and eg < eo_gap:
            n_dominating += 1

    return n_dominating + 1


def analyze_cresswell_trajectory(
    results_df: pd.DataFrame,
    gamma_col: str = 'gamma',
    coverage_gap_col: str = 'coverage_gap',
    set_size_gap_col: str = 'set_size_gap',
    eo_gap_col: str = 'eo_gap'
) -> Dict[str, float]:
    """
    Analyze the Cresswell trajectory across gamma values.

    Returns
    -------
    dict
        Analysis results including correlations and optimal gamma
    """
    results = {}

    # Correlation analysis
    from scipy import stats

    # Coverage gap vs Set size gap (should be negative for Cresswell)
    corr_cov_ss, p_cov_ss = stats.pearsonr(
        results_df[coverage_gap_col],
        results_df[set_size_gap_col]
    )
    results['corr_coverage_setsize'] = corr_cov_ss
    results['corr_coverage_setsize_pvalue'] = p_cov_ss
    results['cresswell_mechanism_confirmed'] = corr_cov_ss < -0.5 and p_cov_ss < 0.05

    # Set size gap vs EO gap (should be positive)
    corr_ss_eo, p_ss_eo = stats.pearsonr(
        results_df[set_size_gap_col],
        results_df[eo_gap_col]
    )
    results['corr_setsize_eo'] = corr_ss_eo
    results['corr_setsize_eo_pvalue'] = p_ss_eo

    # Coverage gap vs EO gap (overall trade-off)
    corr_cov_eo, p_cov_eo = stats.pearsonr(
        results_df[coverage_gap_col],
        results_df[eo_gap_col]
    )
    results['corr_coverage_eo'] = corr_cov_eo
    results['corr_coverage_eo_pvalue'] = p_cov_eo

    # Find optimal gamma (minimizes combined score)
    results_df['trade_off_score'] = results_df[coverage_gap_col] + results_df[eo_gap_col]
    optimal_idx = results_df['trade_off_score'].idxmin()
    results['optimal_gamma'] = results_df.loc[optimal_idx, gamma_col]
    results['optimal_coverage_gap'] = results_df.loc[optimal_idx, coverage_gap_col]
    results['optimal_eo_gap'] = results_df.loc[optimal_idx, eo_gap_col]

    return results
