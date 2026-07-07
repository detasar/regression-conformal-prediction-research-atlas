"""
Human-in-the-Loop (HITL) simulation module for CPFI experiments.

Simulates human review of uncertain predictions and computes fairness metrics.
"""

from .simulator import (
    simulate_hitl,
    simulate_hitl_grid,
    compute_hitl_metrics,
    HITLResult,
    HITLMetrics,
    HITLMetricsComputer,
)

__all__ = [
    'simulate_hitl',
    'simulate_hitl_grid',
    'compute_hitl_metrics',
    'HITLResult',
    'HITLMetrics',
    'HITLMetricsComputer',
]
