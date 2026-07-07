"""
Baseline Deferral Methods for Comparison with CP+HITL.

This module implements non-CP deferral baselines to answer the critical question:
"Does CP's deferral selection really make a difference?"

BASELINE COMPARISON ARMS:
=========================
1. CP+HITL (our main system)
   - Uses conformal prediction sets to identify uncertain samples
   - Defers samples with |prediction_set| > 1 to human review

2. ThresholdOptimizer / EO Postprocessing (no CP)
   - Uses fairlearn ThresholdOptimizer to find group-specific thresholds
   - Optimizes for equalized odds directly
   - No deferral, just adjusted predictions

3. Confidence Deferral + HITL (no CP)
   - Defers samples where max(p) < confidence_threshold
   - Threshold t chosen to match same deferral rate as CP
   - Tests: "Is CP's set-based uncertainty better than raw confidence?"

4. Random Deferral + HITL
   - Randomly defers samples at specified rate
   - Control baseline for deferral benefit

Each baseline is treated as a separate "arm" in the experiment, allowing
clean ablation comparisons.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass
from loguru import logger


class DeferralResult(NamedTuple):
    """Result from a deferral method."""
    y_pred: np.ndarray           # Final predictions (after deferral resolution)
    deferred_mask: np.ndarray    # Boolean mask of deferred samples
    deferral_rate: float         # Proportion deferred
    method: str                  # Method name
    params: Dict                 # Method parameters


# =============================================================================
# CONFIDENCE-BASED DEFERRAL (Non-CP Baseline)
# =============================================================================

def confidence_deferral(
    probs: np.ndarray,
    y_test: np.ndarray,
    confidence_threshold: float,
    human_accuracy: float = 0.80,
    seed: int = 42
) -> DeferralResult:
    """
    Defer samples where max(p) < confidence_threshold.

    This is the primary non-CP baseline. It tests whether CP's set-based
    uncertainty identification is better than raw probability confidence.

    Args:
        probs: Predicted probabilities for positive class
        y_test: True labels (for simulating human review)
        confidence_threshold: Defer if max(p, 1-p) < threshold
        human_accuracy: Simulated human accuracy on deferred samples
        seed: Random seed for human simulation

    Returns:
        DeferralResult with predictions and deferral info
    """
    np.random.seed(seed)
    n = len(probs)

    # Compute confidence (max of p and 1-p)
    confidence = np.maximum(probs, 1 - probs)

    # Identify samples to defer (low confidence)
    deferred_mask = confidence < confidence_threshold

    # Make predictions
    y_pred = (probs >= 0.5).astype(int)

    # Simulate human review for deferred samples
    n_deferred = deferred_mask.sum()
    if n_deferred > 0:
        human_correct = np.random.random(n_deferred) < human_accuracy
        y_pred[deferred_mask] = np.where(
            human_correct,
            y_test[deferred_mask],
            1 - y_test[deferred_mask]
        )

    deferral_rate = deferred_mask.mean()

    return DeferralResult(
        y_pred=y_pred,
        deferred_mask=deferred_mask,
        deferral_rate=deferral_rate,
        method='confidence_deferral',
        params={
            'confidence_threshold': confidence_threshold,
            'human_accuracy': human_accuracy
        }
    )


def confidence_deferral_match_rate(
    probs: np.ndarray,
    y_test: np.ndarray,
    target_deferral_rate: float,
    human_accuracy: float = 0.80,
    seed: int = 42
) -> DeferralResult:
    """
    Defer samples to match a target deferral rate using confidence threshold.

    This allows direct comparison with CP methods at the same deferral rate.

    Args:
        probs: Predicted probabilities for positive class
        y_test: True labels (for simulating human review)
        target_deferral_rate: Target proportion to defer
        human_accuracy: Simulated human accuracy on deferred samples
        seed: Random seed for human simulation

    Returns:
        DeferralResult with predictions and deferral info
    """
    # Compute confidence
    confidence = np.maximum(probs, 1 - probs)

    # Find threshold that gives target deferral rate
    # Higher threshold = more deferrals
    if target_deferral_rate <= 0:
        threshold = 0.5  # Never defer
    elif target_deferral_rate >= 1:
        threshold = 1.0  # Always defer
    else:
        # Find quantile that gives target rate
        # We defer when confidence < threshold
        # So threshold = (1 - target_rate) quantile of confidence
        threshold = np.quantile(confidence, target_deferral_rate)

    return confidence_deferral(probs, y_test, threshold, human_accuracy, seed)


# =============================================================================
# RANDOM DEFERRAL (Control Baseline)
# =============================================================================

def random_deferral(
    probs: np.ndarray,
    y_test: np.ndarray,
    deferral_rate: float,
    human_accuracy: float = 0.80,
    seed: int = 42
) -> DeferralResult:
    """
    Randomly defer samples at specified rate.

    This is a control baseline to measure the benefit of intelligent deferral.

    Args:
        probs: Predicted probabilities for positive class
        y_test: True labels (for simulating human review)
        deferral_rate: Proportion of samples to defer
        human_accuracy: Simulated human accuracy on deferred samples
        seed: Random seed

    Returns:
        DeferralResult with predictions and deferral info
    """
    np.random.seed(seed)
    n = len(probs)

    # Random deferral
    deferred_mask = np.random.random(n) < deferral_rate

    # Make predictions
    y_pred = (probs >= 0.5).astype(int)

    # Simulate human review
    n_deferred = deferred_mask.sum()
    if n_deferred > 0:
        human_correct = np.random.random(n_deferred) < human_accuracy
        y_pred[deferred_mask] = np.where(
            human_correct,
            y_test[deferred_mask],
            1 - y_test[deferred_mask]
        )

    return DeferralResult(
        y_pred=y_pred,
        deferred_mask=deferred_mask,
        deferral_rate=deferred_mask.mean(),
        method='random_deferral',
        params={
            'target_deferral_rate': deferral_rate,
            'human_accuracy': human_accuracy
        }
    )


# =============================================================================
# THRESHOLD OPTIMIZER (Fairlearn EO Postprocessing)
# =============================================================================

def threshold_optimizer_eo(
    probs: np.ndarray,
    y_test: np.ndarray,
    sensitive: np.ndarray,
    constraint: str = 'equalized_odds'
) -> DeferralResult:
    """
    Apply fairlearn ThresholdOptimizer for equalized odds.

    This is a postprocessing baseline that adjusts group-specific thresholds
    to optimize for fairness, WITHOUT any deferral mechanism.

    Args:
        probs: Predicted probabilities for positive class
        y_test: True labels (used for fitting thresholds)
        sensitive: Sensitive attribute values
        constraint: Fairness constraint ('equalized_odds', 'demographic_parity')

    Returns:
        DeferralResult with NO deferral (deferral_rate=0)
    """
    try:
        from fairlearn.postprocessing import ThresholdOptimizer
        from sklearn.base import BaseEstimator, ClassifierMixin

        # Create a dummy estimator that just returns our probabilities
        class ProbabilityWrapper(BaseEstimator, ClassifierMixin):
            def __init__(self, probs):
                self._probs = probs
                self.classes_ = np.array([0, 1])

            def fit(self, X, y):
                return self

            def predict(self, X):
                return (self._probs >= 0.5).astype(int)

            def predict_proba(self, X):
                return np.column_stack([1 - self._probs, self._probs])

        # Wrap probabilities
        wrapper = ProbabilityWrapper(probs)

        # Create dummy X (ThresholdOptimizer needs it but doesn't use features)
        X_dummy = np.zeros((len(probs), 1))

        # Fit ThresholdOptimizer
        if constraint == 'equalized_odds':
            to = ThresholdOptimizer(
                estimator=wrapper,
                constraints='equalized_odds',
                prefit=True
            )
        else:
            to = ThresholdOptimizer(
                estimator=wrapper,
                constraints='demographic_parity',
                prefit=True
            )

        to.fit(X_dummy, y_test, sensitive_features=sensitive)

        # Get predictions
        y_pred = to.predict(X_dummy, sensitive_features=sensitive)

        return DeferralResult(
            y_pred=y_pred,
            deferred_mask=np.zeros(len(probs), dtype=bool),
            deferral_rate=0.0,
            method='threshold_optimizer',
            params={'constraint': constraint}
        )

    except ImportError:
        logger.warning("fairlearn not available, falling back to group-specific thresholds")
        return _manual_threshold_optimizer(probs, y_test, sensitive)
    except Exception as e:
        logger.warning(f"ThresholdOptimizer failed: {e}, falling back to manual")
        return _manual_threshold_optimizer(probs, y_test, sensitive)


def _manual_threshold_optimizer(
    probs: np.ndarray,
    y_test: np.ndarray,
    sensitive: np.ndarray
) -> DeferralResult:
    """
    Manual group-specific threshold optimization for equalized odds.

    Finds thresholds t0, t1 for each group that minimize EO gap.
    """
    best_eo_gap = float('inf')
    best_y_pred = (probs >= 0.5).astype(int)
    best_thresholds = {0: 0.5, 1: 0.5}

    # Grid search over thresholds
    for t0 in np.arange(0.1, 0.9, 0.05):
        for t1 in np.arange(0.1, 0.9, 0.05):
            y_pred = np.zeros(len(probs), dtype=int)
            y_pred[sensitive == 0] = (probs[sensitive == 0] >= t0).astype(int)
            y_pred[sensitive == 1] = (probs[sensitive == 1] >= t1).astype(int)

            # Compute EO gap
            eo_gap = _compute_eo_gap(y_test, y_pred, sensitive)

            if eo_gap < best_eo_gap:
                best_eo_gap = eo_gap
                best_y_pred = y_pred.copy()
                best_thresholds = {0: t0, 1: t1}

    return DeferralResult(
        y_pred=best_y_pred,
        deferred_mask=np.zeros(len(probs), dtype=bool),
        deferral_rate=0.0,
        method='manual_threshold_optimizer',
        params={'thresholds': best_thresholds, 'eo_gap': best_eo_gap}
    )


def _compute_eo_gap(y_true: np.ndarray, y_pred: np.ndarray, sensitive: np.ndarray) -> float:
    """Compute equalized odds gap (max of FPR gap and FNR gap)."""
    metrics = {}
    for g in [0, 1]:
        mask = sensitive == g
        if mask.sum() == 0:
            continue

        y_g = y_true[mask]
        pred_g = y_pred[mask]

        # FPR
        neg_mask = y_g == 0
        fpr = (pred_g[neg_mask] == 1).mean() if neg_mask.sum() > 0 else 0

        # FNR
        pos_mask = y_g == 1
        fnr = (pred_g[pos_mask] == 0).mean() if pos_mask.sum() > 0 else 0

        metrics[f'fpr_g{g}'] = fpr
        metrics[f'fnr_g{g}'] = fnr

    fpr_gap = abs(metrics.get('fpr_g0', 0) - metrics.get('fpr_g1', 0))
    fnr_gap = abs(metrics.get('fnr_g0', 0) - metrics.get('fnr_g1', 0))

    return max(fpr_gap, fnr_gap)


# =============================================================================
# BASELINE REGISTRY
# =============================================================================

DEFERRAL_BASELINES = {
    'confidence_deferral': confidence_deferral_match_rate,
    'random_deferral': random_deferral,
    'threshold_optimizer': threshold_optimizer_eo,
}


def run_baseline(
    method: str,
    probs: np.ndarray,
    y_test: np.ndarray,
    sensitive: np.ndarray,
    target_deferral_rate: float = 0.0,
    human_accuracy: float = 0.80,
    seed: int = 42
) -> DeferralResult:
    """
    Run a baseline deferral method.

    Args:
        method: One of 'confidence_deferral', 'random_deferral', 'threshold_optimizer'
        probs: Predicted probabilities
        y_test: True labels
        sensitive: Sensitive attribute
        target_deferral_rate: Target deferral rate (for confidence/random)
        human_accuracy: Human accuracy for HITL simulation
        seed: Random seed

    Returns:
        DeferralResult
    """
    if method == 'confidence_deferral':
        return confidence_deferral_match_rate(
            probs, y_test, target_deferral_rate, human_accuracy, seed
        )
    elif method == 'random_deferral':
        return random_deferral(
            probs, y_test, target_deferral_rate, human_accuracy, seed
        )
    elif method == 'threshold_optimizer':
        return threshold_optimizer_eo(probs, y_test, sensitive)
    else:
        raise ValueError(f"Unknown baseline method: {method}")


# =============================================================================
# COMPARISON UTILITIES
# =============================================================================

def compare_deferral_methods(
    probs: np.ndarray,
    y_test: np.ndarray,
    sensitive: np.ndarray,
    cp_deferred_mask: np.ndarray,
    human_accuracy: float = 0.80,
    seed: int = 42
) -> Dict[str, DeferralResult]:
    """
    Compare all baseline methods against CP deferral at matched rate.

    Args:
        probs: Predicted probabilities
        y_test: True labels
        sensitive: Sensitive attribute
        cp_deferred_mask: Boolean mask from CP method
        human_accuracy: Human accuracy for HITL simulation
        seed: Random seed

    Returns:
        Dict mapping method name to DeferralResult
    """
    # Get CP deferral rate to match
    cp_deferral_rate = cp_deferred_mask.mean()

    results = {}

    # Confidence-based deferral (matched rate)
    results['confidence_deferral'] = confidence_deferral_match_rate(
        probs, y_test, cp_deferral_rate, human_accuracy, seed
    )

    # Random deferral (matched rate)
    results['random_deferral'] = random_deferral(
        probs, y_test, cp_deferral_rate, human_accuracy, seed
    )

    # Threshold optimizer (no deferral)
    results['threshold_optimizer'] = threshold_optimizer_eo(
        probs, y_test, sensitive
    )

    return results
