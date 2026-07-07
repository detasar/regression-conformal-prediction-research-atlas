"""
Conformal prediction module for CPFI experiments.

Methods:
- global: vanilla split conformal
- mondrian: group-conditional (equalized coverage)
- ess: equalized set-size
- shrink_γ: shrinkage interpolation (γ ∈ {0.1, 0.25, 0.5, 0.75, 0.9})
- bin_adaptive: adaptive binning
"""

from .methods import (
    apply_cp_method,
    get_all_methods,
    AVAILABLE_METHODS,
    SHRINKAGE_GAMMAS,
    CPResult,
    aps_scores,
    compute_threshold,
    make_prediction_sets,
    global_cp,
    mondrian_cp,
    ess_cp,
    shrinkage_cp,
    bin_adaptive_cp,
)

__all__ = [
    'apply_cp_method',
    'get_all_methods',
    'AVAILABLE_METHODS',
    'SHRINKAGE_GAMMAS',
    'CPResult',
    'aps_scores',
    'compute_threshold',
    'make_prediction_sets',
    'global_cp',
    'mondrian_cp',
    'ess_cp',
    'shrinkage_cp',
    'bin_adaptive_cp',
]
