import numpy as np
import pytest

from experiments.regression.scripts.run_regression_pilot import (
    build_interval,
    fit_cqr_models,
    fit_cqr_model_matched_models,
    fit_residual_quantile_scores,
    fit_residual_scale,
    make_model,
)


MODEL_CASES = [
    ("dummy_mean", {}),
    ("ridge", {"alpha": 1.0}),
    ("elasticnet", {"alpha": 0.01, "l1_ratio": 0.5}),
    ("bayesian_ridge", {}),
    ("svr", {"C": 1.0, "gamma": "scale", "epsilon": 0.1}),
    ("kernel_ridge", {"alpha": 1.0, "kernel": "rbf", "gamma": 0.1}),
    ("knn", {"n_neighbors": 3}),
    ("random_forest", {"n_estimators": 5, "max_depth": 3}),
    ("extra_trees", {"n_estimators": 5, "max_depth": 3}),
    ("hist_gradient_boosting", {"max_iter": 5, "max_leaf_nodes": 7}),
    ("xgboost", {"n_estimators": 5, "max_depth": 2, "learning_rate": 0.1}),
    ("lightgbm", {"n_estimators": 5, "num_leaves": 7, "learning_rate": 0.1}),
    ("catboost", {"iterations": 5, "depth": 2, "learning_rate": 0.1}),
]


@pytest.mark.parametrize(("model_id", "params"), MODEL_CASES)
def test_make_model_fits_and_predicts_small_regression_problem(model_id, params):
    X = np.arange(80, dtype=float).reshape(40, 2)
    y = 0.3 * X[:, 0] - 0.1 * X[:, 1]

    model = make_model(model_id, params, seed=7)
    model.fit(X, y)
    preds = model.predict(X[:3])

    assert preds.shape == (3,)
    assert np.all(np.isfinite(preds))


def test_dummy_mean_model_handles_zero_feature_matrix():
    X = np.empty((12, 0), dtype=float)
    y = np.linspace(10.0, 21.0, num=12)

    model = make_model("dummy_mean", {}, seed=7)
    model.fit(X, y)
    preds = model.predict(np.empty((3, 0), dtype=float))

    np.testing.assert_allclose(preds, np.full(3, y.mean()))


def test_zero_feature_conformal_helpers_use_constant_fallbacks():
    X_train = np.empty((8, 0), dtype=float)
    X_cal = np.empty((3, 0), dtype=float)
    X_test = np.empty((4, 0), dtype=float)
    y_train = np.array([35.0, 37.0, 40.0, 42.0, 43.0, 44.0, 47.0, 55.0])
    yhat_train = np.full_like(y_train, y_train.mean())

    scale_cal, scale_test = fit_residual_scale(
        X_train, y_train, yhat_train, X_cal, X_test, seed=11
    )
    assert scale_cal.shape == (3,)
    assert scale_test.shape == (4,)
    assert np.all(scale_cal > 0.0)
    np.testing.assert_allclose(scale_cal, scale_cal[0])

    lower_cal, upper_cal, lower_test, upper_test, metadata = fit_cqr_models(
        X_train, y_train, X_cal, X_test, alpha=0.1, seed=11
    )
    assert metadata["zero_feature_constant_quantiles"] is True
    np.testing.assert_allclose(lower_cal, np.full(3, np.quantile(y_train, 0.05)))
    np.testing.assert_allclose(upper_test, np.full(4, np.quantile(y_train, 0.95)))
    assert np.all(lower_test <= upper_test)

    qhat_cal, qhat_test = fit_residual_quantile_scores(
        X_train,
        y_train,
        yhat_train,
        X_cal,
        X_test,
        alpha=0.1,
        seed=11,
    )
    expected = np.quantile(np.abs(y_train - yhat_train), 0.9)
    np.testing.assert_allclose(qhat_cal, np.full(3, expected))
    np.testing.assert_allclose(qhat_test, np.full(4, expected))


MODEL_MATCHED_CQR_CASES = [
    ("ridge", {"alpha": 1.0}, "linear_quantile_programming"),
    ("random_forest", {"n_estimators": 7, "max_depth": 3}, "tree_ensemble_empirical_quantile"),
    ("knn", {"n_neighbors": 4}, "local_neighbor_empirical_quantile"),
    (
        "hist_gradient_boosting",
        {"max_iter": 8, "max_leaf_nodes": 7},
        "native_histogram_boosting_quantile",
    ),
    (
        "kernel_ridge",
        {"kernel": "rbf", "gamma": 0.2, "alpha": 1.0},
        "kernel_feature_quantile_programming",
    ),
]


@pytest.mark.parametrize(
    ("model_id", "model_params", "backend_family"), MODEL_MATCHED_CQR_CASES
)
def test_model_matched_cqr_backends_return_interval_quantiles(
    model_id, model_params, backend_family
):
    X_train = np.linspace(-2.0, 2.0, num=80).reshape(40, 2)
    y_train = 0.8 * X_train[:, 0] - 0.2 * X_train[:, 1] + np.sin(X_train[:, 0])
    X_cal = np.linspace(-1.5, 1.5, num=20).reshape(10, 2)
    X_test = np.linspace(-1.0, 1.0, num=12).reshape(6, 2)

    lower_cal, upper_cal, lower_test, upper_test, metadata = fit_cqr_model_matched_models(
        X_train,
        y_train,
        X_cal,
        X_test,
        alpha=0.2,
        seed=13,
        model_id=model_id,
        model_params=model_params,
        cqr_params={"quantile_regressor_alpha": 0.0001, "nystroem_components": 12},
    )

    assert lower_cal.shape == upper_cal.shape == (10,)
    assert lower_test.shape == upper_test.shape == (6,)
    assert np.all(np.isfinite(lower_cal))
    assert np.all(np.isfinite(upper_test))
    assert metadata["cqr_method_id"] == "cqr_model_matched"
    assert metadata["source_model_id"] == model_id
    assert metadata["cqr_backend_family"] == backend_family
    assert metadata["lower_quantile"] == pytest.approx(0.1)
    assert metadata["upper_quantile"] == pytest.approx(0.9)


def test_build_interval_exposes_cqr_model_matched_method_metadata():
    X_train = np.linspace(-2.0, 2.0, num=40).reshape(20, 2)
    y_train = 0.5 * X_train[:, 0] + X_train[:, 1]
    yhat_train = y_train.copy()
    X_cal = np.linspace(-1.0, 1.0, num=12).reshape(6, 2)
    X_test = np.linspace(-0.5, 0.5, num=8).reshape(4, 2)
    y_cal = 0.5 * X_cal[:, 0] + X_cal[:, 1]
    yhat_cal = y_cal.copy()
    yhat_test = 0.5 * X_test[:, 0] + X_test[:, 1]

    result = build_interval(
        "cqr_model_matched",
        alpha=0.2,
        y_cal=y_cal,
        yhat_cal=yhat_cal,
        yhat_test=yhat_test,
        groups_cal=np.array(["a"] * len(y_cal)),
        groups_test=np.array(["a"] * len(yhat_test)),
        X_train=X_train,
        y_train=y_train,
        yhat_train=yhat_train,
        X_cal=X_cal,
        X_test=X_test,
        seed=17,
        model_id="ridge",
        model_params={"alpha": 1.0},
        cqr_params={"quantile_regressor_alpha": 0.0001},
    )

    assert result.metadata["method"] == "cqr_model_matched"
    assert result.metadata["base_conformal_method"] == "conformalized_quantile_regression"
    assert result.metadata["historical_cqr_comparator"] == "cqr_fixed_gradient_boosting_backend"
    assert result.metadata["cqr_backend_family"] == "linear_quantile_programming"
