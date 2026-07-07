"""
Fairness baselines module for CPFI experiments.

These baselines are ALTERNATIVE experimental arms to CP+HITL.
"""

from .fairness import (
    BaselineResult,
    vanilla_baseline,
    threshold_optimizer_baseline,
    confidence_deferral_baseline,
    compute_baseline_metrics,
    run_all_baselines,
    FAIRLEARN_AVAILABLE,
)

__all__ = [
    'BaselineResult',
    'vanilla_baseline',
    'threshold_optimizer_baseline',
    'confidence_deferral_baseline',
    'compute_baseline_metrics',
    'run_all_baselines',
    'FAIRLEARN_AVAILABLE',
]
