"""
Fairness baselines for CPFI experiments.

These are ALTERNATIVE arms to CP+HITL, not combined with CP.

Baselines:
1. ThresholdOptimizer (fairlearn) - Equalized Odds / Demographic Parity
2. Confidence Deferral - defer when max(p) < threshold (no CP theory)
3. Vanilla point prediction (no fairness intervention)

Purpose: Compare "CP + HITL" against traditional fairness methods.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from loguru import logger

# Try importing fairlearn
try:
    from fairlearn.postprocessing import ThresholdOptimizer
    FAIRLEARN_AVAILABLE = True
except ImportError:
    FAIRLEARN_AVAILABLE = False
    logger.warning("fairlearn not available, ThresholdOptimizer baseline disabled")


@dataclass
class BaselineResult:
    """Result from a fairness baseline method."""
    method: str
    y_pred: np.ndarray
    deferred: Optional[np.ndarray]  # Only for methods that defer
    metadata: Dict


def vanilla_baseline(
    probs: np.ndarray,
    threshold: float = 0.5
) -> BaselineResult:
    """
    Vanilla point prediction (no fairness intervention).

    Args:
        probs: Predicted probabilities, shape (n,) or (n, 2)
        threshold: Decision threshold

    Returns:
        BaselineResult with point predictions
    """
    if probs.ndim == 2:
        p1 = probs[:, 1]
    else:
        p1 = probs

    y_pred = (p1 >= threshold).astype(int)

    return BaselineResult(
        method='vanilla',
        y_pred=y_pred,
        deferred=None,
        metadata={'threshold': threshold}
    )


def threshold_optimizer_baseline(
    model: Any,
    X_fit: np.ndarray,
    y_fit: np.ndarray,
    sensitive_fit: np.ndarray,
    X_test: np.ndarray,
    sensitive_test: np.ndarray,
    constraint: str = 'equalized_odds'
) -> BaselineResult:
    """
    ThresholdOptimizer from fairlearn.

    Finds optimal threshold per group to satisfy fairness constraint.

    Args:
        model: Fitted sklearn-compatible model with predict_proba
        X_fit: Features for fitting ThresholdOptimizer (use cp_idx)
        y_fit: Labels for fitting
        sensitive_fit: Sensitive attributes for fitting
        X_test: Test features
        sensitive_test: Test sensitive attributes
        constraint: 'equalized_odds' or 'demographic_parity'

    Returns:
        BaselineResult with fair predictions
    """
    if not FAIRLEARN_AVAILABLE:
        logger.warning("fairlearn not available, returning vanilla predictions")
        probs = model.predict_proba(X_test)
        return vanilla_baseline(probs)

    try:
        to = ThresholdOptimizer(
            estimator=model,
            constraints=constraint,
            prefit=True,
            predict_method='predict_proba'
        )

        to.fit(X_fit, y_fit, sensitive_features=sensitive_fit)
        y_pred = to.predict(X_test, sensitive_features=sensitive_test)

        return BaselineResult(
            method=f'threshold_optimizer_{constraint}',
            y_pred=np.array(y_pred),
            deferred=None,
            metadata={
                'constraint': constraint,
                'fairlearn_version': True
            }
        )

    except Exception as e:
        logger.warning(f"ThresholdOptimizer failed: {e}, returning vanilla")
        probs = model.predict_proba(X_test)
        return vanilla_baseline(probs)


def confidence_deferral_baseline(
    probs: np.ndarray,
    target_defer_rate: float,
    y_true: Optional[np.ndarray] = None,
    human_acc: float = 0.8,
    default_policy: str = 'reject'
) -> BaselineResult:
    """
    Confidence deferral baseline (no CP theory).

    Defers samples where max(prob) < threshold, where threshold
    is chosen to match target_defer_rate.

    This baseline tests: "Is CP's principled deferral better than
    naive confidence deferral?"

    Args:
        probs: Predicted probabilities, shape (n, 2)
        target_defer_rate: Target deferral rate to match CP
        y_true: True labels (for HITL simulation)
        human_acc: Human accuracy when reviewing
        default_policy: 'reject' (0) or 'accept' (1) for unreviewed deferrals

    Returns:
        BaselineResult with predictions and deferral mask
    """
    if probs.ndim == 1:
        probs = np.column_stack([1 - probs, probs])

    # Confidence = max probability
    max_probs = probs.max(axis=1)

    # Find threshold that gives target defer rate
    # defer_rate = P(max_prob < threshold)
    if target_defer_rate <= 0:
        threshold = 0.0
    elif target_defer_rate >= 1:
        threshold = 1.0
    else:
        threshold = np.quantile(max_probs, target_defer_rate)

    # Determine deferred samples
    deferred = max_probs < threshold

    # Point prediction (argmax)
    point_pred = np.argmax(probs, axis=1)

    # Final predictions
    y_pred = point_pred.copy()

    # For deferred samples without human review: use default policy
    if default_policy == 'reject':
        y_pred[deferred] = 0
    else:
        y_pred[deferred] = 1

    # If y_true provided, simulate HITL for deferred samples
    # (Simplified: assume human reviews all deferred with human_acc)
    if y_true is not None and human_acc > 0:
        np.random.seed(42)
        n_deferred = deferred.sum()
        if n_deferred > 0:
            # Human is correct with probability human_acc
            human_correct = np.random.random(n_deferred) < human_acc
            deferred_indices = np.where(deferred)[0]

            for i, idx in enumerate(deferred_indices):
                if human_correct[i]:
                    y_pred[idx] = y_true[idx]
                else:
                    y_pred[idx] = 1 - y_true[idx]

    return BaselineResult(
        method='confidence_deferral',
        y_pred=y_pred,
        deferred=deferred,
        metadata={
            'threshold': threshold,
            'actual_defer_rate': deferred.mean(),
            'target_defer_rate': target_defer_rate
        }
    )


def compute_baseline_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    groups: np.ndarray,
    deferred: Optional[np.ndarray] = None
) -> Dict:
    """
    Compute metrics for baseline predictions.

    Same metrics as CP evaluation for fair comparison.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        groups: Group membership
        deferred: Optional deferral mask

    Returns:
        Dictionary of metrics
    """
    metrics = {}
    n = len(y_true)
    unique_groups = np.unique(groups)

    # Overall accuracy
    metrics['accuracy'] = (y_pred == y_true).mean()

    # Selection/positive rate
    metrics['positive_rate'] = (y_pred == 1).mean()

    # Deferral rate (if applicable)
    if deferred is not None:
        metrics['defer_rate'] = deferred.mean()

    # Per-group metrics
    for g in unique_groups:
        mask = groups == g
        prefix = f'g{g}_'

        metrics[f'{prefix}accuracy'] = (y_pred[mask] == y_true[mask]).mean()
        metrics[f'{prefix}positive_rate'] = (y_pred[mask] == 1).mean()

        if deferred is not None:
            metrics[f'{prefix}defer_rate'] = deferred[mask].mean()

        # Error rates
        y_g = y_true[mask]
        pred_g = y_pred[mask]

        # FPR
        neg_mask = y_g == 0
        if neg_mask.sum() > 0:
            metrics[f'{prefix}fpr'] = (pred_g[neg_mask] == 1).mean()
        else:
            metrics[f'{prefix}fpr'] = np.nan

        # FNR
        pos_mask = y_g == 1
        if pos_mask.sum() > 0:
            metrics[f'{prefix}fnr'] = (pred_g[pos_mask] == 0).mean()
        else:
            metrics[f'{prefix}fnr'] = np.nan

    # Fairness gaps
    accuracies = [metrics[f'g{g}_accuracy'] for g in unique_groups]
    metrics['accuracy_gap'] = max(accuracies) - min(accuracies)

    pos_rates = [metrics[f'g{g}_positive_rate'] for g in unique_groups]
    if min(pos_rates) > 0 and max(pos_rates) > 0:
        metrics['selection_rate_ratio'] = min(pos_rates) / max(pos_rates)
    else:
        metrics['selection_rate_ratio'] = np.nan

    # Equalized odds gap (max of FPR gap and FNR gap)
    fpr_values = [metrics.get(f'g{g}_fpr', np.nan) for g in unique_groups]
    fnr_values = [metrics.get(f'g{g}_fnr', np.nan) for g in unique_groups]

    fpr_valid = [v for v in fpr_values if not np.isnan(v)]
    fnr_valid = [v for v in fnr_values if not np.isnan(v)]

    if len(fpr_valid) >= 2:
        metrics['fpr_gap'] = max(fpr_valid) - min(fpr_valid)
    else:
        metrics['fpr_gap'] = np.nan

    if len(fnr_valid) >= 2:
        metrics['fnr_gap'] = max(fnr_valid) - min(fnr_valid)
    else:
        metrics['fnr_gap'] = np.nan

    metrics['equalized_odds_gap'] = max(
        metrics.get('fpr_gap', 0) or 0,
        metrics.get('fnr_gap', 0) or 0
    )

    return metrics


def run_all_baselines(
    model: Any,
    probs_test: np.ndarray,
    y_test: np.ndarray,
    groups_test: np.ndarray,
    X_cp: np.ndarray,
    y_cp: np.ndarray,
    groups_cp: np.ndarray,
    X_test: np.ndarray,
    target_defer_rate: float,
    human_acc: float = 0.8,
    default_policy: str = 'reject',
    enabled_methods: Optional[List[str]] = None
) -> Dict[str, Dict]:
    """
    Run all fairness baselines and return metrics.

    Args:
        model: Fitted model
        probs_test: Test probabilities
        y_test: Test labels
        groups_test: Test group membership
        X_cp: CP features (for ThresholdOptimizer fitting)
        y_cp: CP labels
        groups_cp: CP group membership
        X_test: Test features
        target_defer_rate: Target defer rate (from global CP)
        human_acc: Human accuracy for HITL simulation
        default_policy: Default policy for unreviewed deferrals
        enabled_methods: List of methods to run

    Returns:
        Dictionary mapping method name to metrics dictionary
    """
    if enabled_methods is None:
        enabled_methods = [
            'vanilla',
            'threshold_optimizer_equalized_odds',
            'threshold_optimizer_demographic_parity',
            'confidence_deferral'
        ]

    results = {}

    # Vanilla baseline
    if 'vanilla' in enabled_methods:
        baseline = vanilla_baseline(probs_test)
        metrics = compute_baseline_metrics(y_test, baseline.y_pred, groups_test)
        results['vanilla'] = {'result': baseline, 'metrics': metrics}

    # ThresholdOptimizer - Equalized Odds
    if 'threshold_optimizer_equalized_odds' in enabled_methods and FAIRLEARN_AVAILABLE:
        baseline = threshold_optimizer_baseline(
            model, X_cp, y_cp, groups_cp, X_test, groups_test,
            constraint='equalized_odds'
        )
        metrics = compute_baseline_metrics(y_test, baseline.y_pred, groups_test)
        results['threshold_optimizer_eo'] = {'result': baseline, 'metrics': metrics}

    # ThresholdOptimizer - Demographic Parity
    if 'threshold_optimizer_demographic_parity' in enabled_methods and FAIRLEARN_AVAILABLE:
        baseline = threshold_optimizer_baseline(
            model, X_cp, y_cp, groups_cp, X_test, groups_test,
            constraint='demographic_parity'
        )
        metrics = compute_baseline_metrics(y_test, baseline.y_pred, groups_test)
        results['threshold_optimizer_dp'] = {'result': baseline, 'metrics': metrics}

    # Confidence deferral
    if 'confidence_deferral' in enabled_methods:
        baseline = confidence_deferral_baseline(
            probs_test, target_defer_rate, y_test, human_acc, default_policy
        )
        metrics = compute_baseline_metrics(
            y_test, baseline.y_pred, groups_test, baseline.deferred
        )
        results['confidence_deferral'] = {'result': baseline, 'metrics': metrics}

    return results
