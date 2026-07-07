import numpy as np

from cpfi.regression.venn_abers import (
    binary_venn_abers_probability_interval,
    ivapd_distribution_metrics,
    ivapd_threshold_grid,
    threshold_grid_crps,
)


def test_binary_venn_abers_probability_interval_is_ordered_and_bounded():
    result = binary_venn_abers_probability_interval(
        scores_cal=np.array([-2.0, -1.0, 0.0, 1.0, 2.0]),
        labels_cal=np.array([0, 0, 0, 1, 1]),
        score_test=0.5,
    )

    assert 0.0 <= result.lower <= result.midpoint <= result.upper <= 1.0
    assert result.metadata["method"] == "binary_venn_abers_probability_interval"
    assert result.metadata["n_cal"] == 5


def test_ivapd_threshold_grid_returns_monotone_predictive_distribution():
    result = ivapd_threshold_grid(
        y_cal=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        yhat_cal=np.array([0.2, 0.8, 2.1, 2.9, 3.8]),
        yhat_test=2.2,
        thresholds=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
    )

    assert result.metadata["method"] == "ivapd_threshold_grid"
    assert result.metadata["prototype_role"] == "threshold_grid_predictive_distribution_not_interval_cp"
    assert result.thresholds.shape == (5,)
    assert np.all(np.diff(result.lower_cdf) >= -1e-12)
    assert np.all(np.diff(result.upper_cdf) >= -1e-12)
    assert np.all(result.lower_cdf <= result.midpoint_cdf)
    assert np.all(result.midpoint_cdf <= result.upper_cdf)
    assert 0.0 <= result.midpoint_cdf[0] <= result.midpoint_cdf[-1] <= 1.0


def test_ivapd_threshold_grid_quantile_and_interval_use_selected_cdf():
    result = ivapd_threshold_grid(
        y_cal=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        yhat_cal=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        yhat_test=2.0,
        thresholds=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
    )

    median = result.quantile(0.5)
    lo, hi = result.interval(alpha=0.4)

    assert median in set(result.thresholds)
    assert lo <= hi
    assert lo in set(result.thresholds)
    assert hi in set(result.thresholds)


def test_threshold_grid_crps_rewards_better_cdf_on_same_grid():
    thresholds = np.array([0.0, 1.0, 2.0, 3.0])
    sharp_near_truth = np.array([0.0, 0.1, 0.9, 1.0])
    wrong_tail = np.array([0.0, 0.0, 0.1, 0.2])

    assert threshold_grid_crps(1.6, thresholds, sharp_near_truth) < threshold_grid_crps(
        1.6,
        thresholds,
        wrong_tail,
    )


def test_threshold_grid_crps_does_not_eagerly_require_trapz(monkeypatch):
    monkeypatch.delattr(np, "trapz", raising=False)

    assert threshold_grid_crps(
        y_true=1.0,
        thresholds=np.array([0.0, 1.0, 2.0]),
        cdf_values=np.array([0.0, 0.5, 1.0]),
    ) >= 0.0


def test_ivapd_distribution_metrics_report_crps_and_band_widths():
    result = ivapd_threshold_grid(
        y_cal=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        yhat_cal=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        yhat_test=2.0,
        thresholds=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
    )

    metrics = ivapd_distribution_metrics(result, y_true=2.1, alpha=0.2)

    assert metrics["method"] == "ivapd_threshold_grid_metrics"
    assert metrics["distribution_method"] == "ivapd_threshold_grid"
    assert metrics["grid_size"] == 5
    assert metrics["midpoint_crps"] >= 0.0
    assert 0.0 <= metrics["cdf_band_mean_width"] <= metrics["cdf_band_max_width"] <= 1.0
    assert metrics["central_interval_lower"] <= metrics["central_interval_upper"]
