"""Target transformations for regression conformal experiments."""

from __future__ import annotations

from typing import Dict, Iterable, Tuple

import numpy as np


SUPPORTED_TARGET_TRANSFORMS = ("identity", "log1p", "signed_log1p")
MAX_FINITE_INVERSE_LOG = 700.0


def _as_array(values: Iterable[float], name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values")
    return arr


def transform_target(values: Iterable[float], transform: str) -> np.ndarray:
    """Transform target values before model fitting and conformal calibration."""

    arr = _as_array(values, "target")
    if transform == "identity":
        return arr
    if transform == "log1p":
        if np.any(arr <= -1.0):
            raise ValueError("log1p target transform requires all values > -1")
        return np.log1p(arr)
    if transform == "signed_log1p":
        return np.sign(arr) * np.log1p(np.abs(arr))
    raise ValueError(
        f"Unsupported target transform: {transform}. "
        f"Available: {SUPPORTED_TARGET_TRANSFORMS}"
    )


def inverse_transform_target_with_metadata(
    values: Iterable[float],
    transform: str,
) -> Tuple[np.ndarray, Dict[str, float | int | str | None]]:
    """Invert target-space values and report numerical saturation counts."""

    arr = _as_array(values, "target_prediction")
    metadata: Dict[str, float | int | str | None] = {
        "transform": transform,
        "inverse_saturation_count": 0,
        "inverse_saturation_threshold": None,
    }
    if transform == "identity":
        return arr, metadata
    if transform == "log1p":
        # Keep interval metrics finite when a conformal method emits a
        # pathological but finite log-scale endpoint. The saturated value is
        # still enormous, so interval scores remain strongly penalized.
        saturation_mask = np.abs(arr) > MAX_FINITE_INVERSE_LOG
        metadata["inverse_saturation_count"] = int(saturation_mask.sum())
        metadata["inverse_saturation_threshold"] = MAX_FINITE_INVERSE_LOG
        return (
            np.expm1(np.clip(arr, -MAX_FINITE_INVERSE_LOG, MAX_FINITE_INVERSE_LOG)),
            metadata,
        )
    if transform == "signed_log1p":
        saturation_mask = np.abs(arr) > MAX_FINITE_INVERSE_LOG
        metadata["inverse_saturation_count"] = int(saturation_mask.sum())
        metadata["inverse_saturation_threshold"] = MAX_FINITE_INVERSE_LOG
        clipped_abs = np.clip(np.abs(arr), 0.0, MAX_FINITE_INVERSE_LOG)
        return np.sign(arr) * np.expm1(clipped_abs), metadata
    raise ValueError(
        f"Unsupported target transform: {transform}. "
        f"Available: {SUPPORTED_TARGET_TRANSFORMS}"
    )


def inverse_transform_target(values: Iterable[float], transform: str) -> np.ndarray:
    """Invert target-space predictions or interval endpoints."""

    restored, _ = inverse_transform_target_with_metadata(values, transform)
    return restored
