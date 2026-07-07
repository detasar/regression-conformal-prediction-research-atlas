"""
Cost-Aware Metrics Module

Computes cost metrics for HITL deployment including:
- Total cost (automated + human review)
- Cost per correct decision
- Cost-optimal configurations

This module helps answer: "Given a budget constraint and cost ratio,
what's the optimal CP method and review rate?"
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)


def compute_cost_metrics(
    n_total: int,
    n_deferred: int,
    n_reviewed: int,
    n_correct: int,
    auto_cost: float = 1.0,
    human_cost: float = 10.0,
    default_cost: float = 5.0,  # Cost of default decision when human unavailable
    prefix: str = ""
) -> Dict[str, float]:
    """
    Compute cost-related metrics.

    Parameters
    ----------
    n_total : int
        Total number of predictions
    n_deferred : int
        Number deferred to human (set size > 1)
    n_reviewed : int
        Number actually reviewed by human (may be < n_deferred if budget limited)
    n_correct : int
        Number of correct final decisions
    auto_cost : float
        Cost per automated decision
    human_cost : float
        Cost per human review
    default_cost : float
        Cost per default decision (when deferred but not reviewed)

    Returns
    -------
    dict
        Cost metrics
    """
    metrics = {}

    # Basic counts
    n_auto = n_total - n_deferred
    n_default = n_deferred - n_reviewed

    # Total cost
    total_cost = (n_auto * auto_cost) + (n_reviewed * human_cost) + (n_default * default_cost)
    metrics[f"{prefix}total_cost"] = total_cost

    # Cost breakdown
    metrics[f"{prefix}auto_cost_total"] = n_auto * auto_cost
    metrics[f"{prefix}human_cost_total"] = n_reviewed * human_cost
    metrics[f"{prefix}default_cost_total"] = n_default * default_cost

    # Rates
    metrics[f"{prefix}auto_rate"] = n_auto / n_total if n_total > 0 else np.nan
    metrics[f"{prefix}review_rate_actual"] = n_reviewed / n_total if n_total > 0 else np.nan
    metrics[f"{prefix}default_rate"] = n_default / n_total if n_total > 0 else np.nan

    # Efficiency metrics
    metrics[f"{prefix}cost_per_decision"] = total_cost / n_total if n_total > 0 else np.nan
    metrics[f"{prefix}cost_per_correct"] = total_cost / n_correct if n_correct > 0 else np.nan

    # Accuracy
    metrics[f"{prefix}accuracy"] = n_correct / n_total if n_total > 0 else np.nan

    # Cost-effectiveness (accuracy per unit cost)
    if total_cost > 0:
        metrics[f"{prefix}cost_effectiveness"] = n_correct / total_cost
    else:
        metrics[f"{prefix}cost_effectiveness"] = np.nan

    return metrics


def compute_cost_optimal_gamma(
    results_df: pd.DataFrame,
    cost_ratio: float,
    gamma_col: str = 'gamma',
    accuracy_col: str = 'final_accuracy',
    defer_rate_col: str = 'defer_rate',
    review_rate_col: str = 'review_rate'
) -> Tuple[float, Dict[str, float]]:
    """
    Find cost-optimal gamma for a given cost ratio.

    Parameters
    ----------
    results_df : pd.DataFrame
        Results with gamma, accuracy, defer_rate, review_rate
    cost_ratio : float
        Ratio of human_cost to auto_cost

    Returns
    -------
    optimal_gamma, metrics
    """
    # Compute total cost for each row
    auto_cost = 1.0
    human_cost = cost_ratio

    df = results_df.copy()
    df['n_auto'] = 1 - df[defer_rate_col]
    df['n_reviewed'] = df[defer_rate_col] * df[review_rate_col]
    df['n_default'] = df[defer_rate_col] * (1 - df[review_rate_col])

    df['total_cost'] = (
        df['n_auto'] * auto_cost +
        df['n_reviewed'] * human_cost +
        df['n_default'] * (auto_cost + human_cost) / 2  # Default cost as average
    )

    df['cost_per_correct'] = df['total_cost'] / df[accuracy_col]

    # Find optimal gamma
    optimal_idx = df['cost_per_correct'].idxmin()

    optimal_gamma = df.loc[optimal_idx, gamma_col]
    metrics = {
        'optimal_gamma': optimal_gamma,
        'cost_ratio': cost_ratio,
        'optimal_accuracy': df.loc[optimal_idx, accuracy_col],
        'optimal_defer_rate': df.loc[optimal_idx, defer_rate_col],
        'optimal_cost_per_correct': df.loc[optimal_idx, 'cost_per_correct'],
    }

    return optimal_gamma, metrics


def compute_break_even_point(
    baseline_accuracy: float,
    baseline_cost: float,
    cp_accuracy_by_gamma: Dict[float, float],
    cp_cost_by_gamma: Dict[float, float]
) -> Optional[float]:
    """
    Find gamma where CP+HITL becomes cost-effective vs baseline.

    Returns
    -------
    gamma or None if no break-even point
    """
    baseline_cost_per_correct = baseline_cost / baseline_accuracy if baseline_accuracy > 0 else np.inf

    for gamma in sorted(cp_cost_by_gamma.keys()):
        cp_acc = cp_accuracy_by_gamma[gamma]
        cp_cost = cp_cost_by_gamma[gamma]

        if cp_acc > 0:
            cp_cost_per_correct = cp_cost / cp_acc
            if cp_cost_per_correct < baseline_cost_per_correct:
                return gamma

    return None


def compute_roi_of_human_review(
    accuracy_no_review: float,
    accuracy_with_review: float,
    review_cost: float,
    value_per_correct: float = 1.0
) -> float:
    """
    Compute ROI of human review.

    ROI = (Value gained - Cost) / Cost

    Parameters
    ----------
    accuracy_no_review : float
        Accuracy without human review
    accuracy_with_review : float
        Accuracy with human review
    review_cost : float
        Total cost of human review
    value_per_correct : float
        Value per correct decision

    Returns
    -------
    float
        ROI (>0 means profitable, <0 means not worth it)
    """
    value_gained = (accuracy_with_review - accuracy_no_review) * value_per_correct

    if review_cost > 0:
        return (value_gained - review_cost) / review_cost
    else:
        return np.inf if value_gained > 0 else 0.0


def generate_cost_frontier(
    results_df: pd.DataFrame,
    cost_ratios: List[float] = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0],
    gamma_col: str = 'gamma',
    accuracy_col: str = 'final_accuracy',
    defer_rate_col: str = 'defer_rate'
) -> pd.DataFrame:
    """
    Generate cost-optimal frontier across different cost ratios.

    Returns
    -------
    DataFrame with optimal gamma for each cost ratio
    """
    results = []

    for cost_ratio in cost_ratios:
        optimal_gamma, metrics = compute_cost_optimal_gamma(
            results_df, cost_ratio, gamma_col, accuracy_col, defer_rate_col
        )
        results.append(metrics)

    return pd.DataFrame(results)
