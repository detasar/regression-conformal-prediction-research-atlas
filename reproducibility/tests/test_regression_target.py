import numpy as np
import pytest

from cpfi.regression.target import (
    MAX_FINITE_INVERSE_LOG,
    inverse_transform_target,
    inverse_transform_target_with_metadata,
    transform_target,
)


def test_log1p_target_transform_round_trips_positive_values():
    y = np.array([0.0, 1.0, 10.0, 100.0])

    transformed = transform_target(y, "log1p")
    restored = inverse_transform_target(transformed, "log1p")

    np.testing.assert_allclose(restored, y)


def test_signed_log1p_target_transform_round_trips_signed_values():
    y = np.array([-10.0, -1.0, 0.0, 2.0, 20.0])

    transformed = transform_target(y, "signed_log1p")
    restored = inverse_transform_target(transformed, "signed_log1p")

    np.testing.assert_allclose(restored, y)


def test_log1p_rejects_values_at_or_below_minus_one():
    with pytest.raises(ValueError, match="requires all values > -1"):
        transform_target(np.array([-1.0, 0.0]), "log1p")


def test_log_inverse_saturates_pathological_large_endpoints():
    values = np.array([0.0, MAX_FINITE_INVERSE_LOG + 100.0])

    restored = inverse_transform_target(values, "log1p")

    assert np.all(np.isfinite(restored))
    assert restored[1] == pytest.approx(np.expm1(MAX_FINITE_INVERSE_LOG))


def test_signed_log_inverse_saturates_pathological_large_endpoints():
    values = np.array([-(MAX_FINITE_INVERSE_LOG + 100.0), MAX_FINITE_INVERSE_LOG + 100.0])

    restored = inverse_transform_target(values, "signed_log1p")

    assert np.all(np.isfinite(restored))
    assert restored[0] == pytest.approx(-np.expm1(MAX_FINITE_INVERSE_LOG))
    assert restored[1] == pytest.approx(np.expm1(MAX_FINITE_INVERSE_LOG))


def test_inverse_transform_reports_saturation_metadata():
    values = np.array([0.0, MAX_FINITE_INVERSE_LOG + 100.0])

    restored, metadata = inverse_transform_target_with_metadata(values, "log1p")

    assert np.all(np.isfinite(restored))
    assert metadata["transform"] == "log1p"
    assert metadata["inverse_saturation_count"] == 1
    assert metadata["inverse_saturation_threshold"] == MAX_FINITE_INVERSE_LOG
