"""
Metrics computation for CPFI experiments.

Computes:
1. Conformal prediction metrics (coverage, set size, etc.)
2. Fairness metrics (gaps across groups)
3. HITL metrics (deferral, accuracy, etc.)
4. Hypothesis-specific metrics (H1-H4)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class CPMetrics:
    """Conformal prediction metrics."""
    coverage: float
    avg_set_size: float
    empty_rate: float
    singleton_rate: float
    both_rate: float

    # By group
    coverage_by_group: Dict[int, float] = field(default_factory=dict)
    set_size_by_group: Dict[int, float] = field(default_factory=dict)

    # Gaps
    coverage_gap: Optional[float] = None
    set_size_gap: Optional[float] = None


@dataclass
class FairnessMetrics:
    """Fairness metrics for CP and HITL."""
    # Coverage parity (H1)
    coverage_gap: float  # max - min coverage across groups
    coverage_ratio: float  # min / max coverage

    # Set size parity (H1)
    set_size_gap: float
    set_size_ratio: float

    # Deferral parity (H2)
    deferral_gap: Optional[float] = None
    deferral_ratio: Optional[float] = None

    # Accuracy parity
    accuracy_gap: Optional[float] = None
    accuracy_ratio: Optional[float] = None

    # Disparate impact
    disparate_impact: Optional[float] = None

    # Chouldechova metrics (H4)
    fpr_gap: Optional[float] = None
    fnr_gap: Optional[float] = None
    ppv_gap: Optional[float] = None
    npv_gap: Optional[float] = None


def compute_cp_metrics(
    prediction_sets: np.ndarray,
    y_true: np.ndarray,
    groups: Optional[np.ndarray] = None
) -> CPMetrics:
    """
    Compute conformal prediction metrics.

    Args:
        prediction_sets: Shape (n, 2) boolean array
        y_true: True labels
        groups: Optional group membership

    Returns:
        CPMetrics object
    """
    n = len(y_true)
    set_sizes = prediction_sets.sum(axis=1)

    # Coverage: true label is in prediction set
    coverage = np.mean([prediction_sets[i, y_true[i]] for i in range(n)])

    # Set size statistics
    avg_set_size = set_sizes.mean()
    empty_rate = (set_sizes == 0).mean()
    singleton_rate = (set_sizes == 1).mean()
    both_rate = (set_sizes == 2).mean()

    # Initialize group metrics
    coverage_by_group = {}
    set_size_by_group = {}
    coverage_gap = None
    set_size_gap = None

    if groups is not None:
        unique_groups = np.unique(groups)

        for g in unique_groups:
            mask = groups == g
            if mask.sum() > 0:
                coverage_by_group[g] = np.mean([
                    prediction_sets[i, y_true[i]]
                    for i in np.where(mask)[0]
                ])
                set_size_by_group[g] = set_sizes[mask].mean()

        if len(coverage_by_group) >= 2:
            cov_values = list(coverage_by_group.values())
            coverage_gap = max(cov_values) - min(cov_values)

            size_values = list(set_size_by_group.values())
            set_size_gap = max(size_values) - min(size_values)

    return CPMetrics(
        coverage=coverage,
        avg_set_size=avg_set_size,
        empty_rate=empty_rate,
        singleton_rate=singleton_rate,
        both_rate=both_rate,
        coverage_by_group=coverage_by_group,
        set_size_by_group=set_size_by_group,
        coverage_gap=coverage_gap,
        set_size_gap=set_size_gap
    )


def compute_fairness_metrics(
    prediction_sets: np.ndarray,
    y_true: np.ndarray,
    groups: np.ndarray,
    final_decisions: Optional[np.ndarray] = None,
    was_deferred: Optional[np.ndarray] = None
) -> FairnessMetrics:
    """
    Compute fairness metrics across groups.

    Args:
        prediction_sets: Shape (n, 2) boolean array
        y_true: True labels
        groups: Group membership
        final_decisions: Optional final predictions (for HITL)
        was_deferred: Optional deferral indicator

    Returns:
        FairnessMetrics object
    """
    unique_groups = np.unique(groups)
    n = len(y_true)
    set_sizes = prediction_sets.sum(axis=1)

    # Coverage by group
    coverage_by_group = {}
    for g in unique_groups:
        mask = groups == g
        coverage_by_group[g] = np.mean([
            prediction_sets[i, y_true[i]]
            for i in np.where(mask)[0]
        ])

    cov_values = list(coverage_by_group.values())
    coverage_gap = max(cov_values) - min(cov_values)
    coverage_ratio = min(cov_values) / max(cov_values) if max(cov_values) > 0 else 0

    # Set size by group
    set_size_by_group = {g: set_sizes[groups == g].mean() for g in unique_groups}
    size_values = list(set_size_by_group.values())
    set_size_gap = max(size_values) - min(size_values)
    set_size_ratio = min(size_values) / max(size_values) if max(size_values) > 0 else 0

    # Deferral metrics
    deferral_gap = None
    deferral_ratio = None
    if was_deferred is not None:
        deferral_by_group = {g: was_deferred[groups == g].mean() for g in unique_groups}
        def_values = list(deferral_by_group.values())
        deferral_gap = max(def_values) - min(def_values)
        deferral_ratio = min(def_values) / max(def_values) if max(def_values) > 0 else 0

    # Accuracy metrics
    accuracy_gap = None
    accuracy_ratio = None
    disparate_impact = None
    if final_decisions is not None:
        accuracy_by_group = {
            g: (final_decisions[groups == g] == y_true[groups == g]).mean()
            for g in unique_groups
        }
        acc_values = list(accuracy_by_group.values())
        accuracy_gap = max(acc_values) - min(acc_values)
        accuracy_ratio = min(acc_values) / max(acc_values) if max(acc_values) > 0 else 0

        # Disparate impact (positive rate ratio)
        pos_rate_by_group = {
            g: (final_decisions[groups == g] == 1).mean()
            for g in unique_groups
        }
        pos_values = [v for v in pos_rate_by_group.values() if v > 0]
        if len(pos_values) >= 2 and max(pos_values) > 0:
            disparate_impact = min(pos_values) / max(pos_values)

    # Chouldechova metrics (H4)
    fpr_gap = None
    fnr_gap = None
    ppv_gap = None
    npv_gap = None

    if final_decisions is not None:
        fpr_by_group = {}
        fnr_by_group = {}
        ppv_by_group = {}
        npv_by_group = {}

        for g in unique_groups:
            mask = groups == g
            y_g = y_true[mask]
            pred_g = final_decisions[mask]

            # FPR: FP / (FP + TN) = FP / (y=0)
            neg_mask = y_g == 0
            if neg_mask.sum() > 0:
                fpr_by_group[g] = (pred_g[neg_mask] == 1).mean()

            # FNR: FN / (FN + TP) = FN / (y=1)
            pos_mask = y_g == 1
            if pos_mask.sum() > 0:
                fnr_by_group[g] = (pred_g[pos_mask] == 0).mean()

            # PPV: TP / (TP + FP) = TP / (pred=1)
            pred_pos = pred_g == 1
            if pred_pos.sum() > 0:
                ppv_by_group[g] = (y_g[pred_pos] == 1).mean()

            # NPV: TN / (TN + FN) = TN / (pred=0)
            pred_neg = pred_g == 0
            if pred_neg.sum() > 0:
                npv_by_group[g] = (y_g[pred_neg] == 0).mean()

        if len(fpr_by_group) >= 2:
            fpr_values = list(fpr_by_group.values())
            fpr_gap = max(fpr_values) - min(fpr_values)

        if len(fnr_by_group) >= 2:
            fnr_values = list(fnr_by_group.values())
            fnr_gap = max(fnr_values) - min(fnr_values)

        if len(ppv_by_group) >= 2:
            ppv_values = list(ppv_by_group.values())
            ppv_gap = max(ppv_values) - min(ppv_values)

        if len(npv_by_group) >= 2:
            npv_values = list(npv_by_group.values())
            npv_gap = max(npv_values) - min(npv_values)

    return FairnessMetrics(
        coverage_gap=coverage_gap,
        coverage_ratio=coverage_ratio,
        set_size_gap=set_size_gap,
        set_size_ratio=set_size_ratio,
        deferral_gap=deferral_gap,
        deferral_ratio=deferral_ratio,
        accuracy_gap=accuracy_gap,
        accuracy_ratio=accuracy_ratio,
        disparate_impact=disparate_impact,
        fpr_gap=fpr_gap,
        fnr_gap=fnr_gap,
        ppv_gap=ppv_gap,
        npv_gap=npv_gap
    )


def compute_all_metrics(
    prediction_sets: np.ndarray,
    y_true: np.ndarray,
    probs: np.ndarray,
    groups: np.ndarray,
    final_decisions: Optional[np.ndarray] = None,
    was_deferred: Optional[np.ndarray] = None,
    was_reviewed: Optional[np.ndarray] = None
) -> Dict:
    """
    Compute all metrics and return as flat dictionary.

    This is the main function for experiment logging.
    Returns a dictionary suitable for DataFrame/Parquet storage.
    """
    n = len(y_true)
    set_sizes = prediction_sets.sum(axis=1)
    unique_groups = np.unique(groups)

    metrics = {}

    # ==========================================================================
    # Basic CP metrics
    # ==========================================================================
    metrics['coverage'] = np.mean([
        prediction_sets[i, y_true[i]] for i in range(n)
    ])
    metrics['avg_set_size'] = set_sizes.mean()
    metrics['empty_rate'] = (set_sizes == 0).mean()
    metrics['singleton_rate'] = (set_sizes == 1).mean()
    metrics['both_rate'] = (set_sizes == 2).mean()

    # ==========================================================================
    # CP metrics by group
    # ==========================================================================
    for g in unique_groups:
        mask = groups == g
        prefix = f'g{g}_'

        metrics[f'{prefix}coverage'] = np.mean([
            prediction_sets[i, y_true[i]]
            for i in np.where(mask)[0]
        ])
        metrics[f'{prefix}avg_set_size'] = set_sizes[mask].mean()
        metrics[f'{prefix}empty_rate'] = (set_sizes[mask] == 0).mean()
        metrics[f'{prefix}singleton_rate'] = (set_sizes[mask] == 1).mean()
        metrics[f'{prefix}both_rate'] = (set_sizes[mask] == 2).mean()
        metrics[f'{prefix}n'] = mask.sum()
        metrics[f'{prefix}base_rate'] = y_true[mask].mean()

    # ==========================================================================
    # Fairness gaps
    # ==========================================================================
    coverages = [metrics[f'g{g}_coverage'] for g in unique_groups]
    metrics['coverage_gap'] = max(coverages) - min(coverages)

    set_sizes_by_g = [metrics[f'g{g}_avg_set_size'] for g in unique_groups]
    metrics['set_size_gap'] = max(set_sizes_by_g) - min(set_sizes_by_g)

    # ==========================================================================
    # HITL metrics (if available)
    # ==========================================================================
    if was_deferred is not None:
        metrics['deferral_rate'] = was_deferred.mean()

        for g in unique_groups:
            mask = groups == g
            metrics[f'g{g}_deferral_rate'] = was_deferred[mask].mean()

        deferral_rates = [metrics[f'g{g}_deferral_rate'] for g in unique_groups]
        metrics['deferral_gap'] = max(deferral_rates) - min(deferral_rates)

    if was_reviewed is not None:
        metrics['actual_review_rate'] = was_reviewed.mean()

    if final_decisions is not None:
        metrics['final_accuracy'] = (final_decisions == y_true).mean()

        for g in unique_groups:
            mask = groups == g
            metrics[f'g{g}_accuracy'] = (
                final_decisions[mask] == y_true[mask]
            ).mean()

            # Positive rate
            metrics[f'g{g}_pos_rate'] = (final_decisions[mask] == 1).mean()

        accuracies = [metrics[f'g{g}_accuracy'] for g in unique_groups]
        metrics['accuracy_gap'] = max(accuracies) - min(accuracies)

        pos_rates = [metrics[f'g{g}_pos_rate'] for g in unique_groups]
        if min(pos_rates) > 0 and max(pos_rates) > 0:
            metrics['disparate_impact'] = min(pos_rates) / max(pos_rates)
        else:
            metrics['disparate_impact'] = np.nan

        # ==========================================================================
        # Chouldechova metrics (H4)
        # ==========================================================================
        for g in unique_groups:
            mask = groups == g
            y_g = y_true[mask]
            pred_g = final_decisions[mask]

            # FPR
            neg_mask = y_g == 0
            if neg_mask.sum() > 0:
                metrics[f'g{g}_fpr'] = (pred_g[neg_mask] == 1).mean()
            else:
                metrics[f'g{g}_fpr'] = np.nan

            # FNR
            pos_mask = y_g == 1
            if pos_mask.sum() > 0:
                metrics[f'g{g}_fnr'] = (pred_g[pos_mask] == 0).mean()
            else:
                metrics[f'g{g}_fnr'] = np.nan

            # PPV
            pred_pos = pred_g == 1
            if pred_pos.sum() > 0:
                metrics[f'g{g}_ppv'] = (y_g[pred_pos] == 1).mean()
            else:
                metrics[f'g{g}_ppv'] = np.nan

            # NPV
            pred_neg = pred_g == 0
            if pred_neg.sum() > 0:
                metrics[f'g{g}_npv'] = (y_g[pred_neg] == 0).mean()
            else:
                metrics[f'g{g}_npv'] = np.nan

        # Gaps for Chouldechova metrics
        for metric_name in ['fpr', 'fnr', 'ppv', 'npv']:
            values = [
                metrics[f'g{g}_{metric_name}']
                for g in unique_groups
                if not np.isnan(metrics.get(f'g{g}_{metric_name}', np.nan))
            ]
            if len(values) >= 2:
                metrics[f'{metric_name}_gap'] = max(values) - min(values)
            else:
                metrics[f'{metric_name}_gap'] = np.nan

        # Equalized odds gap (max of FPR and FNR gaps) - CRITICAL for Cresswell analysis
        fpr_gap = metrics.get('fpr_gap', np.nan)
        fnr_gap = metrics.get('fnr_gap', np.nan)
        if not np.isnan(fpr_gap) and not np.isnan(fnr_gap):
            metrics['equalized_odds_gap'] = max(fpr_gap, fnr_gap)
        elif not np.isnan(fpr_gap):
            metrics['equalized_odds_gap'] = fpr_gap
        elif not np.isnan(fnr_gap):
            metrics['equalized_odds_gap'] = fnr_gap
        else:
            metrics['equalized_odds_gap'] = np.nan

        # Selection rate gap (demographic parity)
        pos_rates = [metrics[f'g{g}_pos_rate'] for g in unique_groups]
        metrics['selection_rate_gap'] = max(pos_rates) - min(pos_rates)

    return metrics


def compute_hypothesis_metrics(
    results_df,  # pandas DataFrame with all experiment results
) -> Dict:
    """
    Compute hypothesis-specific summary metrics from experiment results.

    H1: Mondrian reduces coverage gap but increases set-size disparity
    H2: ESS reduces disparate impact under limited review budgets
    H3: Bin-adaptive methods reduce sensitivity to bin count
    H4: Chouldechova impossibility persists in conformal settings

    Args:
        results_df: DataFrame with all experiment results

    Returns:
        Dictionary with hypothesis-specific metrics
    """
    import pandas as pd

    hypothesis_metrics = {}

    # ==========================================================================
    # H1: Mondrian vs Global coverage/set-size trade-off
    # ==========================================================================
    if 'method' in results_df.columns:
        global_results = results_df[results_df['method'] == 'global']
        mondrian_results = results_df[results_df['method'] == 'mondrian']

        if len(global_results) > 0 and len(mondrian_results) > 0:
            # Coverage gap improvement
            hypothesis_metrics['h1_coverage_gap_global'] = global_results['coverage_gap'].mean()
            hypothesis_metrics['h1_coverage_gap_mondrian'] = mondrian_results['coverage_gap'].mean()
            hypothesis_metrics['h1_coverage_gap_reduction'] = (
                hypothesis_metrics['h1_coverage_gap_global'] -
                hypothesis_metrics['h1_coverage_gap_mondrian']
            )

            # Set size gap change
            hypothesis_metrics['h1_set_size_gap_global'] = global_results['set_size_gap'].mean()
            hypothesis_metrics['h1_set_size_gap_mondrian'] = mondrian_results['set_size_gap'].mean()
            hypothesis_metrics['h1_set_size_gap_increase'] = (
                hypothesis_metrics['h1_set_size_gap_mondrian'] -
                hypothesis_metrics['h1_set_size_gap_global']
            )

    # ==========================================================================
    # H2: ESS and disparate impact at limited review rates
    # ==========================================================================
    if 'review_rate' in results_df.columns and 'disparate_impact' in results_df.columns:
        limited_review = results_df[results_df['review_rate'] < 1.0]
        if len(limited_review) > 0:
            for method in ['global', 'ess']:
                method_results = limited_review[limited_review['method'] == method]
                if len(method_results) > 0:
                    hypothesis_metrics[f'h2_di_{method}'] = method_results['disparate_impact'].mean()

            if 'h2_di_global' in hypothesis_metrics and 'h2_di_ess' in hypothesis_metrics:
                hypothesis_metrics['h2_di_improvement'] = (
                    hypothesis_metrics['h2_di_ess'] - hypothesis_metrics['h2_di_global']
                )

    # ==========================================================================
    # H3: Bin-adaptive sensitivity (would need multiple bin configs)
    # ==========================================================================
    if 'n_bins' in results_df.columns:
        bin_adaptive_results = results_df[results_df['method'] == 'bin_adaptive']
        if len(bin_adaptive_results) > 0:
            # Variance across different bin counts
            hypothesis_metrics['h3_coverage_variance'] = (
                bin_adaptive_results.groupby('n_bins')['coverage'].mean().var()
            )

    # ==========================================================================
    # H4: Chouldechova impossibility
    # ==========================================================================
    if all(col in results_df.columns for col in ['fpr_gap', 'fnr_gap', 'ppv_gap']):
        for method in results_df['method'].unique():
            method_results = results_df[results_df['method'] == method]
            if len(method_results) > 0:
                # Check if any method achieves equalized odds
                avg_fpr_gap = method_results['fpr_gap'].mean()
                avg_fnr_gap = method_results['fnr_gap'].mean()
                avg_ppv_gap = method_results['ppv_gap'].mean()

                hypothesis_metrics[f'h4_{method}_fpr_gap'] = avg_fpr_gap
                hypothesis_metrics[f'h4_{method}_fnr_gap'] = avg_fnr_gap
                hypothesis_metrics[f'h4_{method}_ppv_gap'] = avg_ppv_gap

                # Product of gaps (should be positive if impossibility holds)
                hypothesis_metrics[f'h4_{method}_impossibility_product'] = (
                    avg_fpr_gap * avg_fnr_gap * avg_ppv_gap
                )

    return hypothesis_metrics
