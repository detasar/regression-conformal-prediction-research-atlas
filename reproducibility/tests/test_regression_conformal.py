import numpy as np

from cpfi.regression.conformal import (
    conformal_predictive_system_interval,
    conformalized_quantile_interval,
    distributional_pit_conformal_interval,
    finite_sample_quantile,
    finite_sample_quantile_result,
    full_conformal_score_grid_interval,
    rank_one_out_score_grid_interval,
    weighted_conformal_quantile,
    mondrian_conformal_interval,
    normalized_conformal_interval,
    jackknife_after_bootstrap_interval,
    jackknife_plus_interval,
    jackknife_minmax_interval,
    cv_plus_interval,
    cv_minmax_interval,
    split_conformal_interval,
    weighted_split_conformal_interval,
    split_tail_conformal_interval,
    split_tail_grid_shortest_interval,
    tail_allocation_shortest_interval,
    isotonic_quantile_fit_predict,
    unbounded_ivar_interval,
    venn_abers_quantile_interval,
    venn_abers_split_fallback_interval,
    venn_abers_quantile_grid_interval,
)
from cpfi.regression.metrics import compute_interval_metrics


def test_finite_sample_quantile_uses_upper_order_statistic():
    scores = np.array([0.1, 0.2, 0.3, 0.4])
    assert finite_sample_quantile(scores, alpha=0.25) == 0.4


def test_finite_sample_quantile_reports_cap_metadata():
    result = finite_sample_quantile_result(np.array([0.1, 0.2]), alpha=0.1)

    assert result.value == 0.2
    assert result.metadata["finite_sample_quantile_requested"] == 1.5
    assert result.metadata["finite_sample_quantile_used"] == 1.0
    assert result.metadata["finite_sample_quantile_n"] == 2
    assert result.metadata["finite_sample_quantile_capped"] is True


def test_split_conformal_interval_reports_finite_sample_cap_metadata():
    result = split_conformal_interval(
        y_cal=np.array([0.0, 2.0]),
        yhat_cal=np.array([0.0, 0.0]),
        yhat_test=np.array([1.0]),
        alpha=0.1,
    )

    assert result.metadata["finite_sample_quantile_requested"] == 1.5
    assert result.metadata["finite_sample_quantile_used"] == 1.0
    assert result.metadata["finite_sample_quantile_capped"] is True


def test_weighted_conformal_quantile_matches_split_with_unit_weights():
    scores = np.array([0.1, 0.2, 0.3, 0.4])
    result = weighted_conformal_quantile(
        scores,
        calibration_weights=np.ones(4),
        test_weight=1.0,
        alpha=0.25,
    )

    assert result == finite_sample_quantile(scores, alpha=0.25)


def test_weighted_conformal_quantile_uses_likelihood_ratio_weights():
    result = weighted_conformal_quantile(
        scores=np.array([1.0, 2.0, 10.0]),
        calibration_weights=np.array([10.0, 1.0, 1.0]),
        test_weight=1.0,
        alpha=0.2,
    )

    assert result == 2.0


def test_split_conformal_interval_covers_simple_calibration_residuals():
    y_cal = np.array([1.0, 2.0, 3.0, 4.0])
    yhat_cal = np.array([1.0, 1.5, 3.5, 5.0])
    yhat_test = np.array([10.0, 20.0])

    result = split_conformal_interval(y_cal, yhat_cal, yhat_test, alpha=0.2)

    np.testing.assert_allclose(result.radii, np.array([1.0, 1.0]))
    np.testing.assert_allclose(result.lower, np.array([9.0, 19.0]))
    np.testing.assert_allclose(result.upper, np.array([11.0, 21.0]))


def test_weighted_split_conformal_interval_returns_test_specific_radii():
    result = weighted_split_conformal_interval(
        y_cal=np.array([0.0, 0.0, 0.0]),
        yhat_cal=np.array([1.0, 2.0, 10.0]),
        yhat_test=np.array([100.0, 200.0]),
        calibration_weights=np.array([10.0, 1.0, 1.0]),
        test_weights=np.array([1.0, 20.0]),
        alpha=0.2,
    )

    assert result.metadata["method"] == "weighted_abs_covariate_shift"
    np.testing.assert_allclose(result.radii[0], 2.0)
    assert np.isinf(result.radii[1])
    assert result.metadata["infinite_radius_count"] == 1


def test_conformal_predictive_system_interval_extracts_central_cdf_grid_interval():
    result = conformal_predictive_system_interval(
        label_grid=np.array([0.0, 1.0, 2.0, 5.0, 8.0, 9.0, 10.0]),
        cdf_values_test=np.array(
            [
                [0.0, 0.1, 0.2, 0.5, 0.8, 0.9, 1.0],
                [0.0, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0],
            ]
        ),
        alpha=0.2,
    )

    assert result.metadata["method"] == "conformal_predictive_system"
    assert result.metadata["calibrated_object"] == "conformal_predictive_distribution_cdf"
    assert result.metadata["implementation_role"] == (
        "cdf_grid_interval_extraction_reference_not_broad_runner"
    )
    np.testing.assert_allclose(result.thresholds["lower_probability"], 0.1)
    np.testing.assert_allclose(result.thresholds["upper_probability"], 0.9)
    np.testing.assert_allclose(result.lower, np.array([1.0, 0.5]))
    np.testing.assert_allclose(result.upper, np.array([9.0, 8.6666666667]))
    assert "valid CPS protocol" in result.metadata["finite_sample_interval_claim"]


def test_distributional_pit_conformal_interval_maps_pit_to_quantile_grid():
    result = distributional_pit_conformal_interval(
        pit_cal=np.array([0.05, 0.2, 0.4, 0.6, 0.95]),
        quantile_probabilities=np.array([0.0, 0.05, 0.1, 0.5, 0.9, 0.95, 1.0]),
        quantile_values_test=np.array(
            [
                [0.0, 0.5, 1.0, 5.0, 9.0, 9.5, 10.0],
                [100.0, 101.0, 102.0, 110.0, 118.0, 119.0, 120.0],
            ]
        ),
        alpha=0.2,
    )

    assert result.metadata["method"] == "distributional_conformal_prediction"
    assert result.metadata["calibrated_object"] == "probability_integral_transform_rank"
    np.testing.assert_allclose(result.thresholds["lower_probability"], 0.05)
    np.testing.assert_allclose(result.thresholds["upper_probability"], 0.95)
    np.testing.assert_allclose(result.lower, np.array([0.5, 101.0]))
    np.testing.assert_allclose(result.upper, np.array([9.5, 119.0]))
    assert "PIT-calibrated" in result.metadata["finite_sample_interval_claim"]
    assert np.all(result.lower <= result.upper)


def test_full_conformal_score_grid_interval_inverts_candidate_p_values():
    result = full_conformal_score_grid_interval(
        candidate_values=np.array([-2.0, -1.0, 0.0, 1.0, 2.0]),
        calibration_scores_by_candidate=np.array(
            [
                [0.0, 0.0, 0.0, 0.0],
                [2.0, 2.0, 2.0, 2.0],
                [2.0, 2.0, 2.0, 2.0],
                [2.0, 2.0, 2.0, 2.0],
                [0.0, 0.0, 0.0, 0.0],
            ]
        ),
        test_scores_by_candidate=np.array([2.0, 1.0, 1.0, 1.0, 2.0]),
        alpha=0.2,
    )

    assert result.metadata["method"] == "full_conformal_regression"
    assert result.metadata["implementation_role"] == "tiny_grid_reference_not_broad_runner"
    np.testing.assert_allclose(result.lower, np.array([-1.0]))
    np.testing.assert_allclose(result.upper, np.array([1.0]))
    assert result.metadata["accepted_count"] == 3
    assert result.metadata["rejected_count"] == 2
    np.testing.assert_allclose(result.metadata["p_values"], [0.2, 1.0, 1.0, 1.0, 0.2])
    assert "transductive" in result.metadata["finite_sample_interval_claim"]


def test_rank_one_out_score_grid_interval_inverts_candidate_p_values():
    result = rank_one_out_score_grid_interval(
        candidate_values=np.array([-2.0, -1.0, 0.0, 1.0, 2.0]),
        comparison_scores_by_candidate=np.array(
            [
                [0.0, 0.0, 0.0, 0.0],
                [3.0, 2.0, 2.0, 2.0],
                [2.0, 3.0, 2.0, 2.0],
                [2.0, 2.0, 3.0, 2.0],
                [0.0, 0.0, 0.0, 0.0],
            ]
        ),
        target_scores_by_candidate=np.array([2.0, 1.0, 1.0, 1.0, 2.0]),
        alpha=0.2,
    )

    assert result.metadata["method"] == "rank_one_out_conformal"
    assert result.metadata["implementation_role"] == (
        "rank_one_out_score_grid_reference_not_broad_runner"
    )
    np.testing.assert_allclose(result.lower, np.array([-1.0]))
    np.testing.assert_allclose(result.upper, np.array([1.0]))
    assert result.metadata["accepted_count"] == 3
    assert result.metadata["rejected_count"] == 2
    np.testing.assert_allclose(result.metadata["p_values"], [0.2, 1.0, 1.0, 1.0, 0.2])
    assert "rank-one-out" in result.metadata["finite_sample_interval_claim"]


def test_split_tail_conformal_interval_calibrates_one_sided_offsets():
    yhat_cal = np.zeros(10)
    y_cal = np.array([-5.0, -4.0, -3.0, -2.0, -1.0, 1.0, 2.0, 3.0, 4.0, 8.0])
    yhat_test = np.array([10.0])

    result = split_tail_conformal_interval(
        y_cal,
        yhat_cal,
        yhat_test,
        alpha=0.8,
        lower_tail_alpha_fraction=0.25,
    )

    assert result.metadata["method"] == "split_tail"
    np.testing.assert_allclose(result.metadata["lower_tail_alpha"], 0.2)
    np.testing.assert_allclose(result.metadata["upper_tail_alpha"], 0.6)
    np.testing.assert_allclose(result.thresholds["lower_offset"], 5.0)
    np.testing.assert_allclose(result.thresholds["upper_offset"], 1.0)
    np.testing.assert_allclose(result.lower, np.array([5.0]))
    np.testing.assert_allclose(result.upper, np.array([11.0]))


def test_split_tail_conformal_interval_clips_negative_offsets_conservatively():
    result = split_tail_conformal_interval(
        y_cal=np.array([5.0, 6.0, 7.0, 8.0]),
        yhat_cal=np.zeros(4),
        yhat_test=np.array([10.0]),
        alpha=0.2,
    )

    assert result.metadata["negative_lower_offset_clipped"] is True
    assert result.thresholds["lower_offset"] == 0.0
    assert result.lower[0] == 10.0
    assert result.upper[0] >= result.lower[0]


def test_split_tail_grid_shortest_selects_predeclared_fraction_by_width():
    result = split_tail_grid_shortest_interval(
        y_cal=np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 20.0, 30.0, 100.0]),
        yhat_cal=np.zeros(10),
        yhat_test=np.array([10.0, 20.0]),
        alpha=0.8,
        lower_tail_alpha_fractions=(0.25, 0.50, 0.75),
    )

    assert result.metadata["method"] == "split_tail_grid_shortest"
    assert result.metadata["base_method"] == "split_tail"
    assert result.metadata["selected_lower_tail_alpha_fraction"] == 0.25
    assert result.thresholds["selected_lower_tail_alpha_fraction"] == 0.25
    assert result.metadata["tail_fraction_grid"] == [0.25, 0.5, 0.75]
    assert result.metadata["candidate_widths"]["0.25"] < result.metadata[
        "candidate_widths"
    ]["0.50"]
    assert "not full TA-CQR" in result.metadata["finite_sample_interval_claim"]
    assert np.all(result.lower <= result.upper)


def test_tail_allocation_shortest_interval_uses_independent_tuning_split():
    result = tail_allocation_shortest_interval(
        y_tune=np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 20.0, 30.0, 100.0]),
        yhat_tune=np.zeros(10),
        y_cal=np.array([0.0, 2.0, 4.0, 8.0, 16.0]),
        yhat_cal=np.zeros(5),
        yhat_test=np.array([10.0, 20.0]),
        alpha=0.8,
        lower_tail_alpha_fractions=(0.25, 0.50, 0.75),
    )

    assert result.metadata["method"] == "tail_allocation_shortest_interval"
    assert result.metadata["base_method"] == "split_tail"
    assert result.metadata["implementation_role"] == (
        "tuning_split_reference_not_broad_ta_cqr_runner"
    )
    assert result.metadata["selected_lower_tail_alpha_fraction"] == 0.25
    assert result.thresholds["selected_lower_tail_alpha_fraction"] == 0.25
    assert result.metadata["n_tune"] == 10
    assert result.metadata["n_cal"] == 5
    assert result.metadata["tuning_candidate_widths"]["0.25"] < result.metadata[
        "tuning_candidate_widths"
    ]["0.50"]
    np.testing.assert_allclose(result.thresholds["lower_offset"], 0.0)
    np.testing.assert_allclose(result.thresholds["upper_offset"], 8.0)
    np.testing.assert_allclose(result.lower, np.array([10.0, 20.0]))
    np.testing.assert_allclose(result.upper, np.array([18.0, 28.0]))
    assert "independent tuning split" in result.metadata["finite_sample_interval_claim"]
    assert "not full TA-CQR" in result.metadata["finite_sample_interval_claim"]


def test_mondrian_conformal_interval_uses_group_radius_and_global_fallback():
    y_cal = np.array([0.0, 0.0, 10.0, 10.0])
    yhat_cal = np.array([0.0, 0.1, 8.0, 12.0])
    yhat_test = np.array([5.0, 5.0, 5.0])
    groups_cal = np.array(["a", "a", "b", "b"])
    groups_test = np.array(["a", "b", "c"])

    result = mondrian_conformal_interval(
        y_cal,
        yhat_cal,
        yhat_test,
        groups_cal,
        groups_test,
        alpha=0.2,
        min_group_size=2,
    )

    assert result.radii[0] < result.radii[1]
    assert result.radii[2] == result.thresholds["global"]
    assert "c" in result.metadata["fallback_groups"]


def test_normalized_conformal_interval_scales_test_radii():
    result = normalized_conformal_interval(
        y_cal=np.array([1.0, 2.0]),
        yhat_cal=np.array([0.0, 4.0]),
        yhat_test=np.array([10.0, 10.0]),
        scale_cal=np.array([1.0, 2.0]),
        scale_test=np.array([1.0, 3.0]),
        alpha=0.2,
    )

    np.testing.assert_allclose(result.radii, np.array([1.0, 3.0]))


def test_cqr_interval_applies_single_conformal_correction():
    result = conformalized_quantile_interval(
        y_cal=np.array([1.0, 5.0]),
        lower_cal=np.array([0.0, 4.0]),
        upper_cal=np.array([2.0, 4.5]),
        lower_test=np.array([10.0]),
        upper_test=np.array([12.0]),
        alpha=0.2,
    )

    np.testing.assert_allclose(result.lower, np.array([9.5]))
    np.testing.assert_allclose(result.upper, np.array([12.5]))


def test_cqr_orders_crossed_quantile_predictions():
    result = conformalized_quantile_interval(
        y_cal=np.array([1.0, 5.0]),
        lower_cal=np.array([2.0, 7.0]),
        upper_cal=np.array([0.0, 4.0]),
        lower_test=np.array([12.0]),
        upper_test=np.array([10.0]),
        alpha=0.2,
    )

    assert result.lower[0] <= result.upper[0]
    assert result.metadata["quantile_crossings_cal"] == 2
    assert result.metadata["quantile_crossings_test"] == 1


def test_cqr_clips_negative_correction_to_keep_intervals_valid():
    result = conformalized_quantile_interval(
        y_cal=np.array([5.0, 6.0]),
        lower_cal=np.array([0.0, 0.0]),
        upper_cal=np.array([10.0, 10.0]),
        lower_test=np.array([2.0]),
        upper_test=np.array([8.0]),
        alpha=0.2,
    )

    np.testing.assert_allclose(result.lower, np.array([2.0]))
    np.testing.assert_allclose(result.upper, np.array([8.0]))
    assert result.metadata["raw_cqr_correction"] < 0.0
    assert result.metadata["negative_correction_clipped"] is True


def test_unbounded_ivar_interval_returns_ordered_monotone_endpoints():
    lower, upper, metadata = unbounded_ivar_interval(
        base_cal=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        labels_cal=np.array([0.0, 0.5, 1.0, 2.0, 4.0]),
        base_test=np.array([1.5, 3.5]),
        m=1,
    )

    assert metadata["ivar_variant"] == "unbounded"
    assert metadata["m"] == 1
    assert lower.shape == (2,)
    assert np.all(lower <= upper)
    assert upper[1] >= upper[0]


def test_venn_abers_quantile_interval_uses_upper_ivar_radius():
    result = venn_abers_quantile_interval(
        y_cal=np.array([0.0, 0.5, 1.0, 2.0, 4.0]),
        yhat_cal=np.zeros(5),
        yhat_test=np.array([10.0, 20.0]),
        residual_quantile_cal=np.array([0.0, 0.5, 1.0, 2.0, 4.0]),
        residual_quantile_test=np.array([1.5, 3.5]),
        alpha=0.2,
        m=1,
    )

    assert result.metadata["method"] == "venn_abers_quantile"
    assert result.metadata["calibrated_object"] == "absolute_residual_conformity_score"
    assert result.lower.shape == (2,)
    assert np.all(result.radii >= 0.0)
    assert np.all(result.lower <= result.upper)


def test_venn_abers_split_fallback_envelopes_bridge_with_split_radius():
    bridge = venn_abers_quantile_interval(
        y_cal=np.array([0.0, 0.5, 1.0, 2.0, 4.0]),
        yhat_cal=np.zeros(5),
        yhat_test=np.array([10.0, 20.0]),
        residual_quantile_cal=np.array([0.0, 0.5, 1.0, 2.0, 4.0]),
        residual_quantile_test=np.array([1.5, 3.5]),
        alpha=0.2,
        m=1,
    )
    split = split_conformal_interval(
        y_cal=np.array([0.0, 0.5, 1.0, 2.0, 4.0]),
        yhat_cal=np.zeros(5),
        yhat_test=np.array([10.0, 20.0]),
        alpha=0.2,
    )
    result = venn_abers_split_fallback_interval(
        y_cal=np.array([0.0, 0.5, 1.0, 2.0, 4.0]),
        yhat_cal=np.zeros(5),
        yhat_test=np.array([10.0, 20.0]),
        residual_quantile_cal=np.array([0.0, 0.5, 1.0, 2.0, 4.0]),
        residual_quantile_test=np.array([1.5, 3.5]),
        alpha=0.2,
        m=1,
    )

    assert result.metadata["method"] == "venn_abers_split_fallback"
    assert result.metadata["bridge_method"] == "venn_abers_quantile"
    assert result.metadata["fallback_method"] == "split_abs"
    assert result.metadata["calibration_only_fallback"] is True
    np.testing.assert_allclose(result.radii, np.maximum(bridge.radii, split.radii))
    assert np.all(result.lower <= result.upper)


def test_isotonic_quantile_fit_predict_merges_violating_blocks():
    pred, metadata = isotonic_quantile_fit_predict(
        x=np.array([0.0, 1.0, 2.0]),
        y=np.array([0.0, 3.0, 1.0]),
        x_eval=np.array([1.5]),
        quantile=0.5,
    )

    np.testing.assert_allclose(pred, np.array([1.0]))
    assert metadata["n_initial_blocks"] == 3
    assert metadata["n_final_blocks"] == 2


def test_venn_abers_quantile_grid_interval_rejects_large_candidate_score():
    result = venn_abers_quantile_grid_interval(
        y_cal=np.array([0.0, 1.0, 2.0]),
        yhat_cal=np.zeros(3),
        yhat_test=np.array([10.0]),
        residual_quantile_cal=np.array([0.0, 1.0, 2.0]),
        residual_quantile_test=np.array([1.5]),
        score_grid=np.array([0.0, 1.0, 2.0, 3.0]),
        alpha=0.5,
    )

    assert result.metadata["method"] == "venn_abers_quantile_grid"
    assert result.metadata["accepted_counts"] == [3]
    assert result.metadata["rejected_counts"] == [1]
    np.testing.assert_allclose(result.radii, np.array([2.0]))
    np.testing.assert_allclose(result.lower, np.array([8.0]))
    np.testing.assert_allclose(result.upper, np.array([12.0]))


def test_interval_metrics_reports_group_gaps():
    metrics = compute_interval_metrics(
        y_true=np.array([0.0, 1.0, 2.0, 3.0]),
        lower=np.array([-1.0, 0.0, 0.0, 0.0]),
        upper=np.array([1.0, 2.0, 1.0, 10.0]),
        alpha=0.25,
        groups=np.array(["a", "a", "b", "b"]),
    )

    assert metrics.coverage == 0.75
    assert metrics.coverage_gap == 0.5
    assert metrics.width_gap == 3.5


def test_jackknife_plus_interval_uses_per_training_row_test_predictions():
    result = jackknife_plus_interval(
        y_train=np.array([1.0, 2.0, 3.0]),
        yhat_train_loo=np.array([1.0, 1.0, 5.0]),
        yhat_test_loo=np.array([[10.0], [11.0], [12.0]]),
        alpha=0.2,
    )

    assert result.metadata["method"] == "jackknife_plus"
    assert result.lower.shape == (1,)
    assert result.upper.shape == (1,)
    assert result.lower[0] <= result.upper[0]


def test_jackknife_plus_interval_uses_bcrt_order_statistics():
    n_train = 101
    result = jackknife_plus_interval(
        y_train=np.zeros(n_train),
        yhat_train_loo=np.zeros(n_train),
        yhat_test_loo=np.arange(n_train, dtype=float)[:, None],
        alpha=0.1,
    )

    assert result.metadata["plus_lower_order_index_zero_based"] == 9
    assert result.metadata["plus_upper_order_index_zero_based"] == 91
    np.testing.assert_allclose(result.lower, np.array([9.0]))
    np.testing.assert_allclose(result.upper, np.array([91.0]))


def test_jackknife_plus_interval_bcrt_order_statistics_clamp_edges():
    result = jackknife_plus_interval(
        y_train=np.zeros(4),
        yhat_train_loo=np.zeros(4),
        yhat_test_loo=np.arange(4, dtype=float)[:, None],
        alpha=0.2,
    )

    assert result.metadata["plus_lower_order_index_zero_based"] == 0
    assert result.metadata["plus_upper_order_index_zero_based"] == 3
    np.testing.assert_allclose(result.lower, np.array([0.0]))
    np.testing.assert_allclose(result.upper, np.array([3.0]))


def test_jackknife_minmax_interval_uses_prediction_extremes_and_residual_radius():
    result = jackknife_minmax_interval(
        y_train=np.array([1.0, 2.0, 3.0]),
        yhat_train_loo=np.array([1.0, 1.0, 5.0]),
        yhat_test_loo=np.array([[10.0, 20.0], [11.0, 19.0], [12.0, 21.0]]),
        alpha=0.2,
    )

    assert result.metadata["method"] == "jackknife_minmax"
    assert result.thresholds["residual_radius"] == 2.0
    np.testing.assert_allclose(result.lower, np.array([8.0, 17.0]))
    np.testing.assert_allclose(result.upper, np.array([14.0, 23.0]))


def test_jackknife_after_bootstrap_interval_uses_oob_aggregates():
    result = jackknife_after_bootstrap_interval(
        y_train=np.array([1.0, 2.0, 3.0]),
        yhat_train_oob=np.array([1.0, 1.0, 5.0]),
        yhat_test_oob=np.array([[10.0, 20.0], [11.0, 19.0], [12.0, 21.0]]),
        alpha=0.2,
        oob_counts=np.array([2, 3, 4]),
    )

    assert result.metadata["method"] == "jackknife_plus_after_bootstrap"
    assert result.metadata["min_oob_count"] == 2
    assert result.metadata["max_oob_count"] == 4
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_cv_plus_interval_maps_fold_predictions_to_training_rows():
    y_train = np.array([1.0, 2.0, 3.0, 4.0])
    yhat_train_oof = np.array([1.0, 1.5, 2.5, 6.0])
    yhat_test_by_fold = np.array([[10.0, 20.0], [12.0, 22.0]])
    fold_ids = np.array([0, 0, 1, 1])
    result = cv_plus_interval(
        y_train=y_train,
        yhat_train_oof=yhat_train_oof,
        yhat_test_by_fold=yhat_test_by_fold,
        fold_ids=fold_ids,
        alpha=0.2,
    )
    expanded = jackknife_plus_interval(
        y_train=y_train,
        yhat_train_loo=yhat_train_oof,
        yhat_test_loo=yhat_test_by_fold[fold_ids],
        alpha=0.2,
    )

    assert result.metadata["method"] == "cv_plus"
    assert result.metadata["n_folds"] == 2
    assert result.lower.shape == (2,)
    assert result.upper.shape == (2,)
    np.testing.assert_allclose(result.lower, expanded.lower)
    np.testing.assert_allclose(result.upper, expanded.upper)


def test_cv_plus_interval_uses_bcrt_order_statistics():
    n_train = 101
    fold_ids = np.arange(n_train)
    result = cv_plus_interval(
        y_train=np.zeros(n_train),
        yhat_train_oof=np.zeros(n_train),
        yhat_test_by_fold=np.arange(n_train, dtype=float)[:, None],
        fold_ids=fold_ids,
        alpha=0.1,
    )

    assert result.metadata["plus_lower_order_index_zero_based"] == 9
    assert result.metadata["plus_upper_order_index_zero_based"] == 91
    np.testing.assert_allclose(result.lower, np.array([9.0]))
    np.testing.assert_allclose(result.upper, np.array([91.0]))


def test_cv_minmax_interval_maps_fold_predictions_to_prediction_extremes():
    y_train = np.array([1.0, 2.0, 3.0, 4.0])
    yhat_train_oof = np.array([1.0, 1.5, 2.5, 6.0])
    yhat_test_by_fold = np.array([[10.0, 20.0], [12.0, 22.0]])
    fold_ids = np.array([0, 0, 1, 1])
    result = cv_minmax_interval(
        y_train=y_train,
        yhat_train_oof=yhat_train_oof,
        yhat_test_by_fold=yhat_test_by_fold,
        fold_ids=fold_ids,
        alpha=0.2,
    )
    expanded = jackknife_minmax_interval(
        y_train=y_train,
        yhat_train_loo=yhat_train_oof,
        yhat_test_loo=yhat_test_by_fold[fold_ids],
        alpha=0.2,
    )

    assert result.metadata["method"] == "cv_minmax"
    assert result.metadata["n_folds"] == 2
    assert result.thresholds["residual_radius"] == 2.0
    np.testing.assert_allclose(result.lower, np.array([8.0, 18.0]))
    np.testing.assert_allclose(result.upper, np.array([14.0, 24.0]))
    np.testing.assert_allclose(result.lower, expanded.lower)
    np.testing.assert_allclose(result.upper, expanded.upper)
