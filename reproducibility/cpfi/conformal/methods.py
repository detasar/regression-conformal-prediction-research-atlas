"""
Conformal prediction methods for CPFI experiments.

Methods:
1. global - vanilla split conformal
2. mondrian - group-conditional CP for equalized coverage
3. ess - equalized set-size (equalize deferral rates)
4. shrink - interpolation between global and group thresholds
5. bin_adaptive - adaptive binning (SC-CP inspired)

All methods use APS (Adaptive Prediction Sets) scoring for binary classification.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from loguru import logger


class CPResult(NamedTuple):
    """Result from conformal prediction."""
    prediction_sets: np.ndarray  # Shape: (n_test, 2) boolean array
    thresholds: Dict[str, float]  # Threshold(s) used
    set_sizes: np.ndarray  # Size of each prediction set
    metadata: Dict


def aps_scores(probs: np.ndarray, y: np.ndarray) -> np.ndarray:
    """
    Compute APS (Adaptive Prediction Sets) scores for binary classification.

    For binary classification:
    - Sort classes by decreasing probability
    - Score = cumulative probability until true class is included

    Simplified for binary: score = 1 - p_true + U*p_true
    where U ~ Uniform(0,1) for randomization

    Args:
        probs: Predicted probabilities for class 1
        y: True labels (0 or 1)

    Returns:
        Conformity scores
    """
    # For binary: score = 1 - prob of true class
    # If y=1: score = 1 - probs
    # If y=0: score = probs (since prob of class 0 = 1 - probs)
    scores = np.where(y == 1, 1 - probs, probs)
    return scores


def compute_threshold(scores: np.ndarray, alpha: float) -> float:
    """
    Compute conformal threshold for given miscoverage rate.

    Args:
        scores: Calibration conformity scores
        alpha: Target miscoverage rate

    Returns:
        Threshold tau such that P(score <= tau) >= 1 - alpha
    """
    n = len(scores)
    # Quantile with finite-sample correction
    q = np.ceil((n + 1) * (1 - alpha)) / n
    q = min(q, 1.0)  # Cap at 1.0
    return np.quantile(scores, q)


def make_prediction_sets(
    probs_test: np.ndarray,
    threshold: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Construct prediction sets given threshold.

    Args:
        probs_test: Test probabilities for class 1
        threshold: Conformity threshold

    Returns:
        Tuple of (prediction_sets, set_sizes)
        prediction_sets shape: (n_test, 2) boolean
    """
    n = len(probs_test)
    pred_sets = np.zeros((n, 2), dtype=bool)

    # Class 0 included if score for class 0 <= threshold
    # Score for class 0 (if y=0) = probs (prob of class 1)
    # So class 0 included if probs <= threshold
    pred_sets[:, 0] = probs_test <= threshold

    # Class 1 included if score for class 1 <= threshold
    # Score for class 1 (if y=1) = 1 - probs
    # So class 1 included if 1 - probs <= threshold, i.e., probs >= 1 - threshold
    pred_sets[:, 1] = probs_test >= (1 - threshold)

    set_sizes = pred_sets.sum(axis=1)
    return pred_sets, set_sizes


# =============================================================================
# Method 1: Global (Vanilla Split Conformal)
# =============================================================================

def global_cp(
    probs_cal: np.ndarray,
    y_cal: np.ndarray,
    probs_test: np.ndarray,
    alpha: float,
    **kwargs
) -> CPResult:
    """
    Global (vanilla) split conformal prediction.

    Uses a single threshold computed from all calibration data.

    Args:
        probs_cal: Calibration probabilities
        y_cal: Calibration labels
        probs_test: Test probabilities
        alpha: Target miscoverage rate

    Returns:
        CPResult with prediction sets
    """
    scores = aps_scores(probs_cal, y_cal)
    threshold = compute_threshold(scores, alpha)

    pred_sets, set_sizes = make_prediction_sets(probs_test, threshold)

    return CPResult(
        prediction_sets=pred_sets,
        thresholds={'global': threshold},
        set_sizes=set_sizes,
        metadata={'method': 'global', 'alpha': alpha}
    )


# =============================================================================
# Method 2: Mondrian (Group-Conditional CP)
# =============================================================================

def mondrian_cp(
    probs_cal: np.ndarray,
    y_cal: np.ndarray,
    probs_test: np.ndarray,
    alpha: float,
    groups_cal: np.ndarray,
    groups_test: np.ndarray,
    **kwargs
) -> CPResult:
    """
    Mondrian (group-conditional) conformal prediction.

    Computes separate thresholds for each group to achieve
    equalized coverage across groups.

    Args:
        probs_cal: Calibration probabilities
        y_cal: Calibration labels
        probs_test: Test probabilities
        alpha: Target miscoverage rate
        groups_cal: Group membership for calibration
        groups_test: Group membership for test

    Returns:
        CPResult with prediction sets
    """
    scores_cal = aps_scores(probs_cal, y_cal)
    unique_groups = np.unique(groups_cal)

    # Compute group-specific thresholds
    group_thresholds = {}
    for g in unique_groups:
        mask = groups_cal == g
        if mask.sum() > 0:
            group_thresholds[g] = compute_threshold(scores_cal[mask], alpha)
        else:
            # Fallback to global if group is empty
            group_thresholds[g] = compute_threshold(scores_cal, alpha)

    # Apply group-specific thresholds to test data
    n_test = len(probs_test)
    pred_sets = np.zeros((n_test, 2), dtype=bool)

    for g in unique_groups:
        mask = groups_test == g
        if mask.any():
            threshold = group_thresholds[g]
            pred_sets[mask, 0] = probs_test[mask] <= threshold
            pred_sets[mask, 1] = probs_test[mask] >= (1 - threshold)

    # Handle unseen groups in test (use global threshold)
    unseen_mask = ~np.isin(groups_test, unique_groups)
    if unseen_mask.any():
        global_threshold = compute_threshold(scores_cal, alpha)
        pred_sets[unseen_mask, 0] = probs_test[unseen_mask] <= global_threshold
        pred_sets[unseen_mask, 1] = probs_test[unseen_mask] >= (1 - global_threshold)

    set_sizes = pred_sets.sum(axis=1)

    return CPResult(
        prediction_sets=pred_sets,
        thresholds={f'group_{g}': t for g, t in group_thresholds.items()},
        set_sizes=set_sizes,
        metadata={
            'method': 'mondrian',
            'alpha': alpha,
            'n_groups': len(unique_groups)
        }
    )


# =============================================================================
# Method 3: ESS (Equalized Set Size)
# =============================================================================

def ess_cp(
    probs_cal: np.ndarray,
    y_cal: np.ndarray,
    probs_test: np.ndarray,
    alpha: float,
    groups_cal: np.ndarray,
    groups_test: np.ndarray,
    target_set_size: Optional[float] = None,
    **kwargs
) -> CPResult:
    """
    Equalized Set Size (ESS) conformal prediction.

    Finds thresholds that equalize average set sizes across groups
    while maintaining overall coverage.

    Args:
        probs_cal: Calibration probabilities
        y_cal: Calibration labels
        probs_test: Test probabilities
        alpha: Target miscoverage rate
        groups_cal: Group membership for calibration
        groups_test: Group membership for test
        target_set_size: Target average set size (if None, uses global average)

    Returns:
        CPResult with prediction sets
    """
    from scipy.optimize import minimize_scalar

    scores_cal = aps_scores(probs_cal, y_cal)
    unique_groups = np.unique(groups_cal)

    # First compute global to get baseline
    global_threshold = compute_threshold(scores_cal, alpha)
    _, global_sizes = make_prediction_sets(probs_cal, global_threshold)

    if target_set_size is None:
        target_set_size = global_sizes.mean()

    # For each group, find threshold that gives target set size
    group_thresholds = {}

    for g in unique_groups:
        mask_cal = groups_cal == g
        group_probs = probs_cal[mask_cal]

        if len(group_probs) < 10:
            # Too few samples, use global threshold
            group_thresholds[g] = global_threshold
            continue

        def set_size_diff(threshold):
            _, sizes = make_prediction_sets(group_probs, threshold)
            return abs(sizes.mean() - target_set_size)

        # Search for threshold that gives target set size
        result = minimize_scalar(
            set_size_diff,
            bounds=(0, 1),
            method='bounded'
        )
        group_thresholds[g] = result.x

    # Apply thresholds
    n_test = len(probs_test)
    pred_sets = np.zeros((n_test, 2), dtype=bool)

    for g in unique_groups:
        mask = groups_test == g
        if mask.any():
            threshold = group_thresholds[g]
            pred_sets[mask, 0] = probs_test[mask] <= threshold
            pred_sets[mask, 1] = probs_test[mask] >= (1 - threshold)

    # Handle unseen groups
    unseen_mask = ~np.isin(groups_test, unique_groups)
    if unseen_mask.any():
        pred_sets[unseen_mask, 0] = probs_test[unseen_mask] <= global_threshold
        pred_sets[unseen_mask, 1] = probs_test[unseen_mask] >= (1 - global_threshold)

    set_sizes = pred_sets.sum(axis=1)

    return CPResult(
        prediction_sets=pred_sets,
        thresholds={f'group_{g}': t for g, t in group_thresholds.items()},
        set_sizes=set_sizes,
        metadata={
            'method': 'ess',
            'alpha': alpha,
            'target_set_size': target_set_size,
            'n_groups': len(unique_groups)
        }
    )


# =============================================================================
# Method 4: Shrinkage CP
# =============================================================================

def shrinkage_cp(
    probs_cal: np.ndarray,
    y_cal: np.ndarray,
    probs_test: np.ndarray,
    alpha: float,
    groups_cal: np.ndarray,
    groups_test: np.ndarray,
    gamma: float = 0.5,
    **kwargs
) -> CPResult:
    """
    Shrinkage conformal prediction.

    Interpolates between global and group-specific thresholds:
    tau_shrink = (1 - gamma) * tau_global + gamma * tau_group

    Args:
        probs_cal: Calibration probabilities
        y_cal: Calibration labels
        probs_test: Test probabilities
        alpha: Target miscoverage rate
        groups_cal: Group membership for calibration
        groups_test: Group membership for test
        gamma: Shrinkage parameter (0 = global, 1 = mondrian)

    Returns:
        CPResult with prediction sets
    """
    scores_cal = aps_scores(probs_cal, y_cal)
    unique_groups = np.unique(groups_cal)

    # Global threshold
    global_threshold = compute_threshold(scores_cal, alpha)

    # Group thresholds
    group_thresholds_raw = {}
    for g in unique_groups:
        mask = groups_cal == g
        if mask.sum() > 0:
            group_thresholds_raw[g] = compute_threshold(scores_cal[mask], alpha)
        else:
            group_thresholds_raw[g] = global_threshold

    # Shrunk thresholds
    group_thresholds = {}
    for g in unique_groups:
        group_thresholds[g] = (
            (1 - gamma) * global_threshold +
            gamma * group_thresholds_raw[g]
        )

    # Apply thresholds
    n_test = len(probs_test)
    pred_sets = np.zeros((n_test, 2), dtype=bool)

    for g in unique_groups:
        mask = groups_test == g
        if mask.any():
            threshold = group_thresholds[g]
            pred_sets[mask, 0] = probs_test[mask] <= threshold
            pred_sets[mask, 1] = probs_test[mask] >= (1 - threshold)

    # Handle unseen groups
    unseen_mask = ~np.isin(groups_test, unique_groups)
    if unseen_mask.any():
        pred_sets[unseen_mask, 0] = probs_test[unseen_mask] <= global_threshold
        pred_sets[unseen_mask, 1] = probs_test[unseen_mask] >= (1 - global_threshold)

    set_sizes = pred_sets.sum(axis=1)

    return CPResult(
        prediction_sets=pred_sets,
        thresholds={
            'global': global_threshold,
            **{f'group_{g}': t for g, t in group_thresholds.items()}
        },
        set_sizes=set_sizes,
        metadata={
            'method': 'shrinkage',
            'alpha': alpha,
            'gamma': gamma,
            'n_groups': len(unique_groups)
        }
    )


# =============================================================================
# Method 5: Bin-Adaptive CP (SC-CP inspired)
# =============================================================================

def bin_adaptive_cp(
    probs_cal: np.ndarray,
    y_cal: np.ndarray,
    probs_test: np.ndarray,
    alpha: float,
    candidate_bins: List[int] = [5, 10, 15, 20, 30],
    tol: float = 0.01,
    groups_cal: Optional[np.ndarray] = None,
    groups_test: Optional[np.ndarray] = None,
    **kwargs
) -> CPResult:
    """
    Bin-adaptive conformal prediction.

    Automatically selects the number of probability bins that
    achieves good coverage while minimizing set sizes.

    Args:
        probs_cal: Calibration probabilities
        y_cal: Calibration labels
        probs_test: Test probabilities
        alpha: Target miscoverage rate
        candidate_bins: List of bin counts to try
        tol: Tolerance for coverage violation
        groups_cal: Optional group membership for calibration
        groups_test: Optional group membership for test

    Returns:
        CPResult with prediction sets
    """
    scores_cal = aps_scores(probs_cal, y_cal)

    best_n_bins = candidate_bins[0]
    best_score = float('inf')
    best_result = None

    for n_bins in candidate_bins:
        # Create bins based on calibration probabilities
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_indices_cal = np.digitize(probs_cal, bin_edges[1:-1])
        bin_indices_test = np.digitize(probs_test, bin_edges[1:-1])

        # Compute bin-specific thresholds
        bin_thresholds = {}
        for b in range(n_bins):
            mask = bin_indices_cal == b
            if mask.sum() >= 5:  # Minimum samples per bin
                bin_thresholds[b] = compute_threshold(scores_cal[mask], alpha)
            else:
                # Fallback to global
                bin_thresholds[b] = compute_threshold(scores_cal, alpha)

        # Apply bin-specific thresholds
        n_test = len(probs_test)
        pred_sets = np.zeros((n_test, 2), dtype=bool)

        for b in range(n_bins):
            mask = bin_indices_test == b
            if mask.any():
                threshold = bin_thresholds[b]
                pred_sets[mask, 0] = probs_test[mask] <= threshold
                pred_sets[mask, 1] = probs_test[mask] >= (1 - threshold)

        set_sizes = pred_sets.sum(axis=1)

        # Compute calibration coverage to check validity
        cal_pred_sets = np.zeros((len(probs_cal), 2), dtype=bool)
        for b in range(n_bins):
            mask = bin_indices_cal == b
            if mask.any():
                threshold = bin_thresholds[b]
                cal_pred_sets[mask, 0] = probs_cal[mask] <= threshold
                cal_pred_sets[mask, 1] = probs_cal[mask] >= (1 - threshold)

        coverage = np.mean([
            cal_pred_sets[i, y_cal[i]] for i in range(len(y_cal))
        ])

        # Score: prefer smaller sets while maintaining coverage
        coverage_penalty = max(0, (1 - alpha) - coverage - tol) * 100
        avg_set_size = set_sizes.mean()

        score = avg_set_size + coverage_penalty

        if score < best_score:
            best_score = score
            best_n_bins = n_bins
            best_result = CPResult(
                prediction_sets=pred_sets,
                thresholds={f'bin_{b}': t for b, t in bin_thresholds.items()},
                set_sizes=set_sizes,
                metadata={
                    'method': 'bin_adaptive',
                    'alpha': alpha,
                    'n_bins': n_bins,
                    'coverage_estimate': coverage
                }
            )

    return best_result


# =============================================================================
# Registry and dispatcher
# =============================================================================

AVAILABLE_METHODS = {
    'global': global_cp,
    'mondrian': mondrian_cp,
    'ess': ess_cp,
    'shrinkage': shrinkage_cp,
    'bin_adaptive': bin_adaptive_cp,
}

# Shrinkage variants with specific gamma values
# Extended grid for Session 2 Cresswell analysis (focus on low gamma)
SHRINKAGE_GAMMAS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.50, 0.75, 0.90]


def apply_cp_method(
    method: str,
    probs_cal: np.ndarray,
    y_cal: np.ndarray,
    probs_test: np.ndarray,
    alpha: float,
    groups_cal: Optional[np.ndarray] = None,
    groups_test: Optional[np.ndarray] = None,
    **kwargs
) -> CPResult:
    """
    Apply a conformal prediction method.

    Args:
        method: Method name (global, mondrian, ess, shrink_0.1, etc., bin_adaptive)
        probs_cal: Calibration probabilities
        y_cal: Calibration labels
        probs_test: Test probabilities
        alpha: Target miscoverage rate
        groups_cal: Group membership for calibration (required for group methods)
        groups_test: Group membership for test (required for group methods)
        **kwargs: Additional method-specific arguments

    Returns:
        CPResult with prediction sets
    """
    # Handle shrinkage variants
    if method.startswith('shrink_'):
        try:
            gamma = float(method.split('_')[1])
        except (IndexError, ValueError):
            raise ValueError(f"Invalid shrinkage method: {method}. Use shrink_0.5 format.")

        return shrinkage_cp(
            probs_cal=probs_cal,
            y_cal=y_cal,
            probs_test=probs_test,
            alpha=alpha,
            groups_cal=groups_cal,
            groups_test=groups_test,
            gamma=gamma,
            **kwargs
        )

    # Handle base methods
    if method not in AVAILABLE_METHODS:
        raise ValueError(f"Unknown method: {method}. Available: {list(AVAILABLE_METHODS.keys())}")

    method_fn = AVAILABLE_METHODS[method]

    # Methods that require groups
    group_methods = {'mondrian', 'ess', 'shrinkage'}
    if method in group_methods:
        if groups_cal is None or groups_test is None:
            raise ValueError(f"Method {method} requires groups_cal and groups_test")

    return method_fn(
        probs_cal=probs_cal,
        y_cal=y_cal,
        probs_test=probs_test,
        alpha=alpha,
        groups_cal=groups_cal,
        groups_test=groups_test,
        **kwargs
    )


def get_all_methods(include_shrinkage_variants: bool = True) -> List[str]:
    """Get list of all available CP methods."""
    methods = list(AVAILABLE_METHODS.keys())
    methods.remove('shrinkage')  # Remove base shrinkage

    if include_shrinkage_variants:
        for gamma in SHRINKAGE_GAMMAS:
            methods.append(f'shrink_{gamma}')

    return methods
