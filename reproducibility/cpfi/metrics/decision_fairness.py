"""
Decision Fairness Metrics Module

Computes decision-level fairness metrics including:
- Selection rate and disparate impact
- Equalized odds (FPR and FNR gaps)
- Accuracy gaps by group

These metrics are CRITICAL for Session 2 analysis as they measure
the OUTCOME fairness, not just the uncertainty fairness (coverage).
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def compute_decision_fairness_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    sensitive_attr: np.ndarray,
    prefix: str = ""
) -> Dict[str, float]:
    """
    Compute comprehensive decision-level fairness metrics.

    Parameters
    ----------
    y_true : np.ndarray
        True binary labels
    y_pred : np.ndarray
        Predicted binary labels (final decisions after HITL)
    sensitive_attr : np.ndarray
        Sensitive attribute values (binary: 0 or 1)
    prefix : str
        Prefix for metric names

    Returns
    -------
    dict
        Dictionary containing all decision fairness metrics
    """
    metrics = {}

    # Get unique groups
    groups = np.unique(sensitive_attr[~np.isnan(sensitive_attr)])

    if len(groups) < 2:
        logger.warning("Less than 2 groups found, returning NaN metrics")
        return _nan_metrics(prefix)

    # Compute per-group metrics
    group_metrics = {}
    for g in groups:
        mask = sensitive_attr == g
        y_true_g = y_true[mask]
        y_pred_g = y_pred[mask]

        gm = {}
        gm['n'] = len(y_true_g)
        gm['base_rate'] = y_true_g.mean() if len(y_true_g) > 0 else np.nan

        # Selection rate
        gm['selection_rate'] = y_pred_g.mean() if len(y_pred_g) > 0 else np.nan

        # Confusion matrix
        tp = ((y_pred_g == 1) & (y_true_g == 1)).sum()
        fp = ((y_pred_g == 1) & (y_true_g == 0)).sum()
        tn = ((y_pred_g == 0) & (y_true_g == 0)).sum()
        fn = ((y_pred_g == 0) & (y_true_g == 1)).sum()

        # Rates
        gm['tpr'] = tp / (tp + fn) if (tp + fn) > 0 else np.nan
        gm['fpr'] = fp / (fp + tn) if (fp + tn) > 0 else np.nan
        gm['fnr'] = fn / (fn + tp) if (fn + tp) > 0 else np.nan
        gm['tnr'] = tn / (tn + fp) if (tn + fp) > 0 else np.nan

        # Precision/NPV
        gm['ppv'] = tp / (tp + fp) if (tp + fp) > 0 else np.nan
        gm['npv'] = tn / (tn + fn) if (tn + fn) > 0 else np.nan

        # Accuracy
        gm['accuracy'] = (tp + tn) / len(y_true_g) if len(y_true_g) > 0 else np.nan

        group_metrics[g] = gm

    # Store per-group metrics
    for g, gm in group_metrics.items():
        g_label = f"g{int(g)}"
        for metric_name, value in gm.items():
            metrics[f"{prefix}{g_label}_{metric_name}"] = value

    # Compute gaps (assuming binary groups)
    if len(groups) == 2:
        g0, g1 = sorted(groups)
        gm0 = group_metrics[g0]
        gm1 = group_metrics[g1]

        # Selection rate gap and ratio
        sr0, sr1 = gm0['selection_rate'], gm1['selection_rate']
        metrics[f"{prefix}selection_rate_gap"] = abs(sr0 - sr1)
        if max(sr0, sr1) > 0:
            metrics[f"{prefix}selection_rate_ratio"] = min(sr0, sr1) / max(sr0, sr1)
        else:
            metrics[f"{prefix}selection_rate_ratio"] = np.nan

        # Disparate impact (4/5 rule)
        metrics[f"{prefix}disparate_impact"] = metrics[f"{prefix}selection_rate_ratio"]

        # FPR gap
        metrics[f"{prefix}fpr_gap"] = abs(gm0['fpr'] - gm1['fpr'])

        # FNR gap
        metrics[f"{prefix}fnr_gap"] = abs(gm0['fnr'] - gm1['fnr'])

        # Equalized odds gap (max of FPR and FNR gaps)
        metrics[f"{prefix}equalized_odds_gap"] = max(
            metrics[f"{prefix}fpr_gap"],
            metrics[f"{prefix}fnr_gap"]
        )

        # Accuracy gap
        metrics[f"{prefix}accuracy_gap"] = abs(gm0['accuracy'] - gm1['accuracy'])

        # TPR gap (equal opportunity)
        metrics[f"{prefix}tpr_gap"] = abs(gm0['tpr'] - gm1['tpr'])

        # PPV gap (predictive parity)
        metrics[f"{prefix}ppv_gap"] = abs(gm0['ppv'] - gm1['ppv'])

        # NPV gap
        metrics[f"{prefix}npv_gap"] = abs(gm0['npv'] - gm1['npv'])

        # Base rate gap (for Chouldechova analysis)
        metrics[f"{prefix}base_rate_gap"] = abs(gm0['base_rate'] - gm1['base_rate'])

    return metrics


def compute_selection_rates(
    y_pred: np.ndarray,
    sensitive_attr: np.ndarray
) -> Tuple[float, float, float]:
    """
    Compute selection rates by group.

    Returns
    -------
    sr_g0, sr_g1, sr_gap
    """
    groups = np.unique(sensitive_attr[~np.isnan(sensitive_attr)])
    if len(groups) < 2:
        return np.nan, np.nan, np.nan

    g0, g1 = sorted(groups)
    sr_g0 = y_pred[sensitive_attr == g0].mean()
    sr_g1 = y_pred[sensitive_attr == g1].mean()
    sr_gap = abs(sr_g0 - sr_g1)

    return sr_g0, sr_g1, sr_gap


def compute_equalized_odds(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    sensitive_attr: np.ndarray
) -> Tuple[float, float, float]:
    """
    Compute equalized odds metrics.

    Returns
    -------
    fpr_gap, fnr_gap, eo_gap
    """
    groups = np.unique(sensitive_attr[~np.isnan(sensitive_attr)])
    if len(groups) < 2:
        return np.nan, np.nan, np.nan

    g0, g1 = sorted(groups)

    def compute_rates(mask):
        y_t = y_true[mask]
        y_p = y_pred[mask]
        tp = ((y_p == 1) & (y_t == 1)).sum()
        fp = ((y_p == 1) & (y_t == 0)).sum()
        tn = ((y_p == 0) & (y_t == 0)).sum()
        fn = ((y_p == 0) & (y_t == 1)).sum()
        fpr = fp / (fp + tn) if (fp + tn) > 0 else np.nan
        fnr = fn / (fn + tp) if (fn + tp) > 0 else np.nan
        return fpr, fnr

    fpr0, fnr0 = compute_rates(sensitive_attr == g0)
    fpr1, fnr1 = compute_rates(sensitive_attr == g1)

    fpr_gap = abs(fpr0 - fpr1)
    fnr_gap = abs(fnr0 - fnr1)
    eo_gap = max(fpr_gap, fnr_gap)

    return fpr_gap, fnr_gap, eo_gap


def compute_accuracy_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    sensitive_attr: np.ndarray
) -> Tuple[float, float, float, float]:
    """
    Compute accuracy metrics by group.

    Returns
    -------
    acc_overall, acc_g0, acc_g1, acc_gap
    """
    acc_overall = (y_true == y_pred).mean()

    groups = np.unique(sensitive_attr[~np.isnan(sensitive_attr)])
    if len(groups) < 2:
        return acc_overall, np.nan, np.nan, np.nan

    g0, g1 = sorted(groups)
    acc_g0 = (y_true[sensitive_attr == g0] == y_pred[sensitive_attr == g0]).mean()
    acc_g1 = (y_true[sensitive_attr == g1] == y_pred[sensitive_attr == g1]).mean()
    acc_gap = abs(acc_g0 - acc_g1)

    return acc_overall, acc_g0, acc_g1, acc_gap


def _nan_metrics(prefix: str) -> Dict[str, float]:
    """Return NaN metrics when groups are not available."""
    metric_names = [
        'selection_rate_gap', 'selection_rate_ratio', 'disparate_impact',
        'fpr_gap', 'fnr_gap', 'equalized_odds_gap',
        'accuracy_gap', 'tpr_gap', 'ppv_gap', 'npv_gap', 'base_rate_gap'
    ]
    return {f"{prefix}{name}": np.nan for name in metric_names}
