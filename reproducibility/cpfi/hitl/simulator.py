"""
Human-in-the-Loop (HITL) simulation for CPFI experiments.

Simulates human review of uncertain predictions (set_size >= 2).

HITL Logic:
- deferred = (set_size >= 2) - human reviews if uncertain
- For each review_rate r:
  - If deferred: human sees case with probability r (uniform random)
    - If human sees case: human_correct with probability human_acc
    - human_decision = y_true if human_correct else 1 - y_true
  - If not deferred or human not sampled: decision = argmax(probs) or default_policy
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from loguru import logger


class HITLResult(NamedTuple):
    """Result from HITL simulation."""
    final_decisions: np.ndarray  # Final predictions after human review
    was_deferred: np.ndarray  # Boolean: was this case deferred?
    was_reviewed: np.ndarray  # Boolean: did human actually review?
    human_correct: np.ndarray  # Boolean: was human correct? (NaN if not reviewed)
    metadata: Dict


@dataclass
class HITLMetrics:
    """Metrics computed from HITL simulation."""
    # Overall
    accuracy: float
    deferral_rate: float
    actual_review_rate: float

    # By group (if groups provided)
    accuracy_by_group: Optional[Dict[int, float]] = None
    deferral_rate_by_group: Optional[Dict[int, float]] = None
    review_rate_by_group: Optional[Dict[int, float]] = None

    # Fairness metrics
    accuracy_gap: Optional[float] = None  # max - min across groups
    deferral_gap: Optional[float] = None
    disparate_impact_ratio: Optional[float] = None


def simulate_hitl(
    prediction_sets: np.ndarray,
    probs: np.ndarray,
    y_true: np.ndarray,
    review_rate: float,
    human_acc: float,
    default_policy: str = 'reject',
    seed: int = 0,
    groups: Optional[np.ndarray] = None,
    human_acc_by_group: Optional[Dict[int, float]] = None
) -> Tuple[HITLResult, HITLMetrics]:
    """
    Simulate human-in-the-loop decision process.

    Args:
        prediction_sets: Shape (n, 2) boolean array of prediction sets
        probs: Predicted probabilities for class 1
        y_true: True labels
        review_rate: Probability that human reviews a deferred case
        human_acc: Human accuracy when reviewing (used as fallback if human_acc_by_group provided)
        default_policy: 'reject' (predict 0) or 'accept' (predict 1) when not reviewed
        seed: Random seed for reproducibility
        groups: Optional group membership for fairness metrics
        human_acc_by_group: Optional dict mapping group_id -> human_accuracy.
            If provided, human accuracy varies by group. Requires groups to be set.

    Returns:
        Tuple of (HITLResult, HITLMetrics)
    """
    np.random.seed(seed)
    n = len(probs)

    # Determine which cases are deferred (set_size >= 2)
    set_sizes = prediction_sets.sum(axis=1)
    was_deferred = set_sizes >= 2

    # Sample which deferred cases are actually reviewed
    review_draw = np.random.random(n)
    was_reviewed = was_deferred & (review_draw < review_rate)

    # For reviewed cases, simulate human decision
    human_draw = np.random.random(n)
    if human_acc_by_group is not None and groups is not None:
        # Group-dependent accuracy: each sample uses its group's accuracy
        human_correct = np.array([
            human_draw[i] < human_acc_by_group.get(int(groups[i]), human_acc)
            for i in range(n)
        ])
    else:
        # Uniform accuracy (backward compatible)
        human_correct = human_draw < human_acc

    # Initialize decisions
    final_decisions = np.zeros(n, dtype=int)

    # For non-deferred cases: use argmax of probs
    non_deferred_mask = ~was_deferred
    final_decisions[non_deferred_mask] = (probs[non_deferred_mask] >= 0.5).astype(int)

    # For deferred but not reviewed: use default policy
    deferred_not_reviewed = was_deferred & ~was_reviewed
    if default_policy == 'reject':
        final_decisions[deferred_not_reviewed] = 0
    else:  # accept
        final_decisions[deferred_not_reviewed] = 1

    # For reviewed cases: human decision
    reviewed_mask = was_reviewed
    human_decisions = np.where(
        human_correct[reviewed_mask],
        y_true[reviewed_mask],  # Correct: predict true label
        1 - y_true[reviewed_mask]  # Incorrect: predict opposite
    )
    final_decisions[reviewed_mask] = human_decisions

    # Create result
    human_correct_result = np.full(n, np.nan)
    human_correct_result[reviewed_mask] = human_correct[reviewed_mask]

    result = HITLResult(
        final_decisions=final_decisions,
        was_deferred=was_deferred,
        was_reviewed=was_reviewed,
        human_correct=human_correct_result,
        metadata={
            'review_rate': review_rate,
            'human_acc': human_acc,
            'human_acc_by_group': human_acc_by_group,
            'default_policy': default_policy,
            'seed': seed
        }
    )

    # Compute metrics
    metrics = compute_hitl_metrics(
        final_decisions=final_decisions,
        y_true=y_true,
        was_deferred=was_deferred,
        was_reviewed=was_reviewed,
        groups=groups
    )

    return result, metrics


def compute_hitl_metrics(
    final_decisions: np.ndarray,
    y_true: np.ndarray,
    was_deferred: np.ndarray,
    was_reviewed: np.ndarray,
    groups: Optional[np.ndarray] = None
) -> HITLMetrics:
    """
    Compute HITL metrics.

    Args:
        final_decisions: Final predictions
        y_true: True labels
        was_deferred: Boolean array of deferred cases
        was_reviewed: Boolean array of reviewed cases
        groups: Optional group membership

    Returns:
        HITLMetrics object
    """
    n = len(y_true)

    # Overall metrics
    accuracy = (final_decisions == y_true).mean()
    deferral_rate = was_deferred.mean()
    actual_review_rate = was_reviewed.mean()

    # Initialize group metrics
    accuracy_by_group = None
    deferral_rate_by_group = None
    review_rate_by_group = None
    accuracy_gap = None
    deferral_gap = None
    disparate_impact_ratio = None

    if groups is not None:
        unique_groups = np.unique(groups)

        accuracy_by_group = {}
        deferral_rate_by_group = {}
        review_rate_by_group = {}

        for g in unique_groups:
            mask = groups == g
            if mask.sum() > 0:
                accuracy_by_group[g] = (final_decisions[mask] == y_true[mask]).mean()
                deferral_rate_by_group[g] = was_deferred[mask].mean()
                review_rate_by_group[g] = was_reviewed[mask].mean()

        # Fairness gaps
        if len(accuracy_by_group) >= 2:
            acc_values = list(accuracy_by_group.values())
            accuracy_gap = max(acc_values) - min(acc_values)

            def_values = list(deferral_rate_by_group.values())
            deferral_gap = max(def_values) - min(def_values)

            # Disparate impact: min/max ratio of positive decision rates
            pos_rates = {g: (final_decisions[groups == g] == 1).mean()
                        for g in unique_groups}
            pos_values = [v for v in pos_rates.values() if v > 0]
            if len(pos_values) >= 2 and max(pos_values) > 0:
                disparate_impact_ratio = min(pos_values) / max(pos_values)

    return HITLMetrics(
        accuracy=accuracy,
        deferral_rate=deferral_rate,
        actual_review_rate=actual_review_rate,
        accuracy_by_group=accuracy_by_group,
        deferral_rate_by_group=deferral_rate_by_group,
        review_rate_by_group=review_rate_by_group,
        accuracy_gap=accuracy_gap,
        deferral_gap=deferral_gap,
        disparate_impact_ratio=disparate_impact_ratio
    )


def simulate_hitl_grid(
    prediction_sets: np.ndarray,
    probs: np.ndarray,
    y_true: np.ndarray,
    review_rates: List[float],
    human_accs: List[float],
    default_policies: List[str],
    seed: int = 0,
    groups: Optional[np.ndarray] = None
) -> List[Tuple[Dict, HITLResult, HITLMetrics]]:
    """
    Simulate HITL over a grid of parameters.

    Args:
        prediction_sets: Shape (n, 2) boolean array
        probs: Predicted probabilities
        y_true: True labels
        review_rates: List of review rates to try
        human_accs: List of human accuracies to try
        default_policies: List of default policies to try
        seed: Base random seed
        groups: Optional group membership

    Returns:
        List of (params, result, metrics) tuples
    """
    results = []
    run_idx = 0

    for review_rate in review_rates:
        for human_acc in human_accs:
            for default_policy in default_policies:
                params = {
                    'review_rate': review_rate,
                    'human_acc': human_acc,
                    'default_policy': default_policy
                }

                result, metrics = simulate_hitl(
                    prediction_sets=prediction_sets,
                    probs=probs,
                    y_true=y_true,
                    review_rate=review_rate,
                    human_acc=human_acc,
                    default_policy=default_policy,
                    seed=seed + run_idx,
                    groups=groups
                )

                results.append((params, result, metrics))
                run_idx += 1

    return results


class HITLMetricsComputer:
    """
    Compute comprehensive HITL metrics for experiment reporting.
    """

    def __init__(
        self,
        y_true: np.ndarray,
        groups: Optional[np.ndarray] = None
    ):
        """
        Initialize metrics computer.

        Args:
            y_true: True labels
            groups: Optional group membership
        """
        self.y_true = y_true
        self.groups = groups
        self.unique_groups = np.unique(groups) if groups is not None else None

    def compute_all_metrics(
        self,
        prediction_sets: np.ndarray,
        probs: np.ndarray,
        hitl_result: HITLResult
    ) -> Dict:
        """
        Compute all metrics for a single HITL run.

        Returns dictionary ready for DataFrame/Parquet storage.
        """
        n = len(self.y_true)
        set_sizes = prediction_sets.sum(axis=1)

        metrics = {}

        # CP metrics
        metrics['coverage'] = np.mean([
            prediction_sets[i, self.y_true[i]]
            for i in range(n)
        ])
        metrics['avg_set_size'] = set_sizes.mean()
        metrics['empty_set_rate'] = (set_sizes == 0).mean()
        metrics['singleton_rate'] = (set_sizes == 1).mean()
        metrics['both_rate'] = (set_sizes == 2).mean()

        # HITL metrics
        metrics['deferral_rate'] = hitl_result.was_deferred.mean()
        metrics['actual_review_rate'] = hitl_result.was_reviewed.mean()
        metrics['final_accuracy'] = (
            hitl_result.final_decisions == self.y_true
        ).mean()

        # Compute metrics by group if available
        if self.groups is not None:
            for g in self.unique_groups:
                mask = self.groups == g
                prefix = f'group_{g}_'

                # CP metrics by group
                metrics[f'{prefix}coverage'] = np.mean([
                    prediction_sets[i, self.y_true[i]]
                    for i in np.where(mask)[0]
                ])
                metrics[f'{prefix}avg_set_size'] = set_sizes[mask].mean()
                metrics[f'{prefix}deferral_rate'] = hitl_result.was_deferred[mask].mean()
                metrics[f'{prefix}accuracy'] = (
                    hitl_result.final_decisions[mask] == self.y_true[mask]
                ).mean()

            # Fairness gaps
            coverages = [metrics[f'group_{g}_coverage'] for g in self.unique_groups]
            metrics['coverage_gap'] = max(coverages) - min(coverages)

            set_sizes_by_group = [metrics[f'group_{g}_avg_set_size'] for g in self.unique_groups]
            metrics['set_size_gap'] = max(set_sizes_by_group) - min(set_sizes_by_group)

            accuracies = [metrics[f'group_{g}_accuracy'] for g in self.unique_groups]
            metrics['accuracy_gap'] = max(accuracies) - min(accuracies)

            deferral_rates = [metrics[f'group_{g}_deferral_rate'] for g in self.unique_groups]
            metrics['deferral_gap'] = max(deferral_rates) - min(deferral_rates)

        return metrics
