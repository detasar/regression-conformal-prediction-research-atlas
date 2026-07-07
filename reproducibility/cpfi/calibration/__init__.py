"""
Probability calibration module for CPFI experiments.

CRITICAL: Calibrator is fit ONLY on calib_idx, NOT on cp_idx.
"""

from .calibrator import (
    CalibrationResult,
    ProbabilityCalibrator,
    calibrate_probabilities,
    select_calibration_method,
    brier_score,
    calibration_curve,
)

__all__ = [
    'CalibrationResult',
    'ProbabilityCalibrator',
    'calibrate_probabilities',
    'select_calibration_method',
    'brier_score',
    'calibration_curve',
]
