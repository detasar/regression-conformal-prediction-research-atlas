"""
CPFI Metrics Module - Session 2

Extended metrics with decision fairness and Cresswell trade-off focus.
"""

from .metrics import (
    compute_all_metrics,
    compute_cp_metrics,
    compute_fairness_metrics,
    compute_hypothesis_metrics,
)

from .decision_fairness import (
    compute_decision_fairness_metrics,
    compute_selection_rates,
    compute_equalized_odds,
    compute_accuracy_metrics,
)

from .cresswell import (
    compute_cresswell_metrics,
    compute_set_size_fairness,
    compute_trade_off_score,
)

from .cost import (
    compute_cost_metrics,
    compute_cost_optimal_gamma,
)

__all__ = [
    # Core metrics (from metrics.py)
    'compute_all_metrics',
    'compute_cp_metrics',
    'compute_fairness_metrics',
    'compute_hypothesis_metrics',
    # Decision fairness
    'compute_decision_fairness_metrics',
    'compute_selection_rates',
    'compute_equalized_odds',
    'compute_accuracy_metrics',
    # Cresswell
    'compute_cresswell_metrics',
    'compute_set_size_fairness',
    'compute_trade_off_score',
    # Cost
    'compute_cost_metrics',
    'compute_cost_optimal_gamma',
]
