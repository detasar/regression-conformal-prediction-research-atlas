"""
Probability calibration for CPFI experiments.

CRITICAL: Calibrator is fit ONLY on calib_idx, NOT on cp_idx.
This ensures no data leakage between probability calibration and conformal calibration.

Methods:
- Isotonic regression (preferred for n >= 5000)
- Platt scaling / sigmoid (for smaller datasets)

The calibrator transforms probabilities BEFORE conformal prediction,
improving CP efficiency without violating coverage guarantees.
"""

import numpy as np
from typing import Dict, Optional, Tuple, Literal
from dataclasses import dataclass
from loguru import logger

from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


@dataclass
class CalibrationResult:
    """Result from probability calibration."""
    method: str
    calibrator: object
    p_cp_calibrated: np.ndarray
    p_test_calibrated: np.ndarray
    metadata: Dict


def select_calibration_method(
    n_samples: int,
    method: str = 'auto',
    min_samples_isotonic: int = 5000
) -> str:
    """
    Select calibration method based on sample size.

    Args:
        n_samples: Number of calibration samples
        method: 'auto', 'isotonic', or 'platt'
        min_samples_isotonic: Minimum samples for isotonic regression

    Returns:
        Selected method name
    """
    if method != 'auto':
        return method

    if n_samples >= min_samples_isotonic:
        return 'isotonic'
    else:
        return 'platt'


def calibrate_probabilities(
    p_calib: np.ndarray,
    y_calib: np.ndarray,
    p_cp: np.ndarray,
    p_test: np.ndarray,
    method: str = 'auto',
    min_samples_isotonic: int = 5000
) -> CalibrationResult:
    """
    Fit probability calibrator on calib set, apply to cp and test.

    CRITICAL: This function fits ONLY on calib data, then transforms
    cp and test probabilities. The cp_idx is used ONLY for conformal
    threshold calibration later.

    Args:
        p_calib: Probabilities on calib_idx, shape (n_calib,) or (n_calib, 2)
        y_calib: True labels on calib_idx
        p_cp: Probabilities on cp_idx
        p_test: Probabilities on test_idx
        method: 'auto', 'isotonic', or 'platt'
        min_samples_isotonic: Min samples for isotonic

    Returns:
        CalibrationResult with calibrated probabilities
    """
    # Handle input shapes - we calibrate P(Y=1)
    if p_calib.ndim == 2:
        p1_calib = p_calib[:, 1]
    else:
        p1_calib = p_calib

    if p_cp.ndim == 2:
        p1_cp = p_cp[:, 1]
    else:
        p1_cp = p_cp

    if p_test.ndim == 2:
        p1_test = p_test[:, 1]
    else:
        p1_test = p_test

    # Select method
    selected_method = select_calibration_method(
        len(y_calib), method, min_samples_isotonic
    )
    logger.info(f"Probability calibration: {selected_method} (n_calib={len(y_calib)})")

    if selected_method == 'isotonic':
        calibrator = IsotonicRegression(
            y_min=0.0,
            y_max=1.0,
            out_of_bounds='clip'
        )
        calibrator.fit(p1_calib, y_calib)

        p1_cp_cal = calibrator.predict(p1_cp)
        p1_test_cal = calibrator.predict(p1_test)

    elif selected_method == 'platt':
        # Platt scaling: fit logistic regression on raw probabilities
        # Transform to log-odds space for better numerical stability
        eps = 1e-10
        p1_calib_clipped = np.clip(p1_calib, eps, 1 - eps)

        # Use raw probabilities as features (simpler and more robust)
        X_calib = p1_calib_clipped.reshape(-1, 1)

        calibrator = LogisticRegression(
            solver='lbfgs',
            max_iter=1000,
            random_state=42
        )
        calibrator.fit(X_calib, y_calib)

        p1_cp_clipped = np.clip(p1_cp, eps, 1 - eps)
        p1_test_clipped = np.clip(p1_test, eps, 1 - eps)

        X_cp = p1_cp_clipped.reshape(-1, 1)
        X_test = p1_test_clipped.reshape(-1, 1)

        p1_cp_cal = calibrator.predict_proba(X_cp)[:, 1]
        p1_test_cal = calibrator.predict_proba(X_test)[:, 1]

    else:
        raise ValueError(f"Unknown calibration method: {selected_method}")

    # Clip to valid probability range
    p1_cp_cal = np.clip(p1_cp_cal, 0.0, 1.0)
    p1_test_cal = np.clip(p1_test_cal, 0.0, 1.0)

    # Reconstruct 2-class probabilities
    p_cp_calibrated = np.column_stack([1 - p1_cp_cal, p1_cp_cal])
    p_test_calibrated = np.column_stack([1 - p1_test_cal, p1_test_cal])

    return CalibrationResult(
        method=selected_method,
        calibrator=calibrator,
        p_cp_calibrated=p_cp_calibrated,
        p_test_calibrated=p_test_calibrated,
        metadata={
            'n_calib': len(y_calib),
            'method': selected_method,
            'calib_brier_before': brier_score(p1_calib, y_calib),
            'calib_brier_after': brier_score(
                calibrator.predict(p1_calib) if selected_method == 'isotonic'
                else calibrator.predict_proba(p1_calib.reshape(-1, 1))[:, 1],
                y_calib
            )
        }
    )


def brier_score(p: np.ndarray, y: np.ndarray) -> float:
    """Compute Brier score (lower is better)."""
    return np.mean((p - y) ** 2)


def calibration_curve(
    p: np.ndarray,
    y: np.ndarray,
    n_bins: int = 10
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute calibration curve for visualization.

    Args:
        p: Predicted probabilities for class 1
        y: True labels
        n_bins: Number of bins

    Returns:
        Tuple of (bin_centers, mean_predicted, mean_actual)
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    mean_predicted = np.zeros(n_bins)
    mean_actual = np.zeros(n_bins)
    bin_counts = np.zeros(n_bins)

    for i in range(n_bins):
        mask = (p >= bin_edges[i]) & (p < bin_edges[i + 1])
        if mask.sum() > 0:
            mean_predicted[i] = p[mask].mean()
            mean_actual[i] = y[mask].mean()
            bin_counts[i] = mask.sum()

    return bin_centers, mean_predicted, mean_actual


class ProbabilityCalibrator:
    """
    Wrapper class for probability calibration.

    Usage:
        calibrator = ProbabilityCalibrator(method='auto')
        calibrator.fit(p_calib, y_calib)
        p_test_cal = calibrator.transform(p_test)
    """

    def __init__(
        self,
        method: str = 'auto',
        min_samples_isotonic: int = 5000
    ):
        self.method = method
        self.min_samples_isotonic = min_samples_isotonic
        self._fitted_method = None
        self._calibrator = None

    def fit(self, p: np.ndarray, y: np.ndarray):
        """Fit calibrator on calib data."""
        if p.ndim == 2:
            p1 = p[:, 1]
        else:
            p1 = p

        self._fitted_method = select_calibration_method(
            len(y), self.method, self.min_samples_isotonic
        )

        if self._fitted_method == 'isotonic':
            self._calibrator = IsotonicRegression(
                y_min=0.0, y_max=1.0, out_of_bounds='clip'
            )
            self._calibrator.fit(p1, y)

        elif self._fitted_method == 'platt':
            eps = 1e-10
            p1_clipped = np.clip(p1, eps, 1 - eps).reshape(-1, 1)
            self._calibrator = LogisticRegression(
                solver='lbfgs', max_iter=1000, random_state=42
            )
            self._calibrator.fit(p1_clipped, y)

        logger.debug(f"Fitted {self._fitted_method} calibrator on {len(y)} samples")
        return self

    def transform(self, p: np.ndarray) -> np.ndarray:
        """Transform probabilities using fitted calibrator."""
        if self._calibrator is None:
            raise ValueError("Calibrator not fitted. Call fit() first.")

        if p.ndim == 2:
            p1 = p[:, 1]
        else:
            p1 = p

        if self._fitted_method == 'isotonic':
            p1_cal = self._calibrator.predict(p1)
        else:
            eps = 1e-10
            p1_clipped = np.clip(p1, eps, 1 - eps).reshape(-1, 1)
            p1_cal = self._calibrator.predict_proba(p1_clipped)[:, 1]

        p1_cal = np.clip(p1_cal, 0.0, 1.0)

        # Return 2-class probabilities
        return np.column_stack([1 - p1_cal, p1_cal])

    def fit_transform(self, p: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Fit and transform in one call."""
        self.fit(p, y)
        return self.transform(p)

    @property
    def fitted_method(self) -> Optional[str]:
        return self._fitted_method
