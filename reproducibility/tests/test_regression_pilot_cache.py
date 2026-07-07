import numpy as np
import pandas as pd

from experiments.regression.scripts import run_regression_pilot as pilot
from experiments.regression.scripts.run_regression_pilot import (
    MethodSkipped,
    build_interval,
    cp_method_settings,
    failed_result_from_exception,
    fit_or_load_prediction_bundle,
    run_payload,
    stable_run_id,
    target_transform_for_dataset,
)


def test_prediction_bundle_cache_reuses_model_predictions(tmp_path):
    n = 40
    x = np.arange(n, dtype=float)
    df = pd.DataFrame(
        {
            "x": x,
            "category": np.where(x % 3 == 0, "a", "b"),
            "group": np.where(x % 2 == 0, "even", "odd"),
            "target": 2.0 * x + np.where(x % 3 == 0, 1.0, -1.0),
        }
    )
    config = {
        "splits": {"train": 0.6, "calibration": 0.2},
        "logging": {"prediction_cache_root": str(tmp_path / "predictions")},
    }
    model_params = {"alpha": 1.0}

    first = fit_or_load_prediction_bundle(
        dataset_id="synthetic_regression",
        df=df,
        target="target",
        group_col="group",
        model_id="ridge",
        model_family="linear",
        model_params=model_params,
        seed=17,
        config=config,
        cache_root=tmp_path / "predictions",
        force=False,
    )
    second = fit_or_load_prediction_bundle(
        dataset_id="synthetic_regression",
        df=df,
        target="target",
        group_col="group",
        model_id="ridge",
        model_family="linear",
        model_params=model_params,
        seed=17,
        config=config,
        cache_root=tmp_path / "predictions",
        force=False,
    )

    assert first.cache_status == "miss"
    assert second.cache_status == "hit"
    assert first.target_transform == "identity"
    assert second.target_transform == "identity"
    assert first.artifact_id == second.artifact_id
    assert (first.artifact_dir / "bundle.npz").exists()
    assert (first.artifact_dir / "metadata.json").exists()
    metadata = pd.read_json(first.artifact_dir / "metadata.json", typ="series")
    assert metadata["data_provenance"]["schema"] == "cpfi_regression_data_provenance_v1"
    assert metadata["data_provenance"]["frame_fingerprint"]["row_count"] == n
    assert metadata["code_provenance"]["schema"] == "cpfi_regression_runtime_provenance_v2"
    np.testing.assert_allclose(first.yhat_cal, second.yhat_cal)
    np.testing.assert_allclose(first.scale_test, second.scale_test)


def test_runtime_provenance_hashes_full_dirty_patch(monkeypatch):
    patch_body = {
        "text": (
            "diff --git a/cpfi/regression/conformal.py b/cpfi/regression/conformal.py\n"
            "+first implementation\n"
        )
    }

    def fake_git_output(args):
        key = tuple(args)
        if key == ("rev-parse", "--short=12", "HEAD"):
            return "abc123def456\n"
        if key == ("status", "--porcelain", "--untracked-files=all"):
            return " M cpfi/regression/conformal.py\n?? scratch.txt\n"
        if key == ("status", "--porcelain", "--untracked-files=no"):
            return " M cpfi/regression/conformal.py\n"
        if key == ("diff", "--stat"):
            return " cpfi/regression/conformal.py | 1 +\n"
        if key == ("diff", "--name-status"):
            return "M\tcpfi/regression/conformal.py\n"
        if key == ("diff", "--binary"):
            return patch_body["text"]
        if key == (
            "diff",
            "--binary",
            "--",
            "cpfi/regression/conformal.py",
        ):
            return patch_body["text"]
        return ""

    monkeypatch.setattr(pilot, "git_output", fake_git_output)
    pilot._RUNTIME_PROVENANCE_CACHE = None
    try:
        first = pilot.runtime_provenance()
        pilot._RUNTIME_PROVENANCE_CACHE = None
        patch_body["text"] = (
            "diff --git a/cpfi/regression/conformal.py b/cpfi/regression/conformal.py\n"
            "+second implementation\n"
        )
        second = pilot.runtime_provenance()
    finally:
        pilot._RUNTIME_PROVENANCE_CACHE = None

    assert first["schema"] == "cpfi_regression_runtime_provenance_v2"
    assert first["git_commit"] == "abc123def456"
    assert first["git_dirty"] is True
    assert first["git_dirty_tracked"] is True
    assert first["git_dirty_path_count"] == 2
    assert first["git_tracked_dirty_path_count"] == 1
    assert first["git_untracked_path_count"] == 1
    assert first["git_relevant_dirty_path_count"] == 1
    assert first["git_relevant_dirty_paths"] == ["cpfi/regression/conformal.py"]
    assert first["git_dirty_name_status_sha256"] == second["git_dirty_name_status_sha256"]
    assert first["git_dirty_patch_sha256"] != second["git_dirty_patch_sha256"]
    assert first["git_relevant_dirty_patch_sha256"] != second[
        "git_relevant_dirty_patch_sha256"
    ]
    assert first["git_dirty_digest"] != second["git_dirty_digest"]


def test_prediction_bundle_key_includes_loaded_frame_fingerprint():
    df = pd.DataFrame(
        {
            "x": [0.0, 1.0, 2.0],
            "group": ["a", "b", "a"],
            "target": [1.0, 2.0, 3.0],
        }
    )
    changed = df.copy()
    changed.loc[2, "x"] = 20.0
    config = {"splits": {"train": 0.6, "calibration": 0.2}}
    code_provenance = {"schema": "test_runtime", "git_commit": "abc", "git_dirty": False}

    base_payload = pilot.prediction_artifact_payload(
        "synthetic_regression",
        "target",
        "group",
        "ridge",
        "linear",
        {"alpha": 1.0},
        17,
        config,
        data_provenance={
            "frame_fingerprint": pilot.dataframe_fingerprint(df),
        },
        code_provenance=code_provenance,
    )
    changed_payload = pilot.prediction_artifact_payload(
        "synthetic_regression",
        "target",
        "group",
        "ridge",
        "linear",
        {"alpha": 1.0},
        17,
        config,
        data_provenance={
            "frame_fingerprint": pilot.dataframe_fingerprint(changed),
        },
        code_provenance=code_provenance,
    )

    assert stable_run_id(base_payload) != stable_run_id(changed_payload)


def test_dataset_target_transform_override_changes_bundle_key(tmp_path):
    n = 40
    x = np.arange(n, dtype=float)
    df = pd.DataFrame(
        {
            "x": x,
            "group": np.where(x % 2 == 0, "even", "odd"),
            "target": x + 1.0,
        }
    )
    base_config = {
        "target_transform": "identity",
        "splits": {"train": 0.6, "calibration": 0.2},
        "logging": {"prediction_cache_root": str(tmp_path / "predictions")},
    }
    override_config = {
        **base_config,
        "dataset_target_transforms": {"synthetic_regression": "log1p"},
    }

    identity = fit_or_load_prediction_bundle(
        dataset_id="synthetic_regression",
        df=df,
        target="target",
        group_col="group",
        model_id="ridge",
        model_family="linear",
        model_params={"alpha": 1.0},
        seed=17,
        config=base_config,
        cache_root=tmp_path / "predictions",
        force=False,
    )
    log1p = fit_or_load_prediction_bundle(
        dataset_id="synthetic_regression",
        df=df,
        target="target",
        group_col="group",
        model_id="ridge",
        model_family="linear",
        model_params={"alpha": 1.0},
        seed=17,
        config=override_config,
        cache_root=tmp_path / "predictions",
        force=False,
    )

    assert target_transform_for_dataset(override_config, "synthetic_regression") == "log1p"
    assert target_transform_for_dataset(override_config, "other_dataset") == "identity"
    assert identity.target_transform == "identity"
    assert log1p.target_transform == "log1p"
    assert identity.artifact_id != log1p.artifact_id


def test_feature_reducer_changes_bundle_key_and_metadata(tmp_path):
    n = 72
    x = np.linspace(-2.0, 2.0, n)
    df = pd.DataFrame(
        {
            "x0": x,
            "x1": x**2,
            "x2": np.sin(x),
            "x3": np.cos(x),
            "x4": np.where(x > 0, 1.0, -1.0),
            "group": np.where(np.arange(n) % 2 == 0, "even", "odd"),
            "target": 1.5 * x + 0.2 * x**2,
        }
    )
    base_config = {
        "splits": {"train": 0.6, "calibration": 0.2},
        "logging": {"prediction_cache_root": str(tmp_path / "predictions")},
    }
    pca_config = {
        **base_config,
        "feature_reducer": {"method": "pca", "n_components": 2},
    }

    base = fit_or_load_prediction_bundle(
        dataset_id="synthetic_regression",
        df=df,
        target="target",
        group_col="group",
        model_id="ridge",
        model_family="linear",
        model_params={"alpha": 1.0},
        seed=17,
        config=base_config,
        cache_root=tmp_path / "predictions",
        force=False,
    )
    reduced = fit_or_load_prediction_bundle(
        dataset_id="synthetic_regression",
        df=df,
        target="target",
        group_col="group",
        model_id="ridge",
        model_family="linear",
        model_params={"alpha": 1.0},
        seed=17,
        config=pca_config,
        cache_root=tmp_path / "predictions",
        force=False,
    )
    metadata = pd.read_json(reduced.artifact_dir / "metadata.json", typ="series")

    assert base.artifact_id != reduced.artifact_id
    assert reduced.X_train.shape[1] == 2
    assert metadata["feature_reducer"]["method"] == "pca"
    assert metadata["feature_reducer_metadata"]["method"] == "pca"
    assert metadata["feature_reducer_metadata"]["fit_scope"] == "train_only"
    assert metadata["feature_reducer_metadata"]["original_feature_count"] > 2
    assert metadata["feature_reducer_metadata"]["reduced_feature_count"] == 2
    assert metadata["feature_names"] == ["pca_001", "pca_002"]
    assert metadata["preprocessed_feature_count"] == len(metadata["preprocessed_feature_names"])


def test_select_k_best_feature_reducer_records_selected_features(tmp_path):
    n = 72
    x = np.linspace(-3.0, 3.0, n)
    df = pd.DataFrame(
        {
            "signal_a": x,
            "signal_b": x**2,
            "noise_a": np.sin(np.arange(n)),
            "noise_b": np.cos(np.arange(n)),
            "group": np.where(np.arange(n) % 3 == 0, "a", "b"),
            "target": 2.0 * x - 0.4 * x**2,
        }
    )
    config = {
        "splits": {"train": 0.6, "calibration": 0.2},
        "feature_reducer": {"method": "select_k_best_f_regression", "k": 2},
        "logging": {"prediction_cache_root": str(tmp_path / "predictions")},
    }

    bundle = fit_or_load_prediction_bundle(
        dataset_id="synthetic_regression",
        df=df,
        target="target",
        group_col="group",
        model_id="ridge",
        model_family="linear",
        model_params={"alpha": 1.0},
        seed=17,
        config=config,
        cache_root=tmp_path / "predictions",
        force=False,
    )
    metadata = pd.read_json(bundle.artifact_dir / "metadata.json", typ="series")

    assert bundle.X_train.shape[1] == 2
    assert metadata["feature_reducer_metadata"]["method"] == "select_k_best_f_regression"
    assert metadata["feature_reducer_metadata"]["fit_scope"] == "train_only"
    assert metadata["feature_reducer_metadata"]["effective_k"] == 2
    assert len(metadata["feature_reducer_metadata"]["selected_feature_names"]) == 2
    assert set(metadata["feature_reducer_metadata"]["selected_feature_names"]).issubset(
        set(metadata["preprocessed_feature_names"])
    )


def test_run_id_includes_split_and_transform_context():
    base = {
        "target_transform": "identity",
        "splits": {"train": 0.6, "calibration": 0.2, "group_col": "county_code"},
    }
    lender = {
        "target_transform": "identity",
        "splits": {"train": 0.6, "calibration": 0.2, "group_col": "lei"},
    }
    log_target = {
        "target_transform": "log1p",
        "splits": {"train": 0.6, "calibration": 0.2, "group_col": "county_code"},
    }

    common = ("hmda_2025_wy_interest_rate", "ridge", {"alpha": 1.0}, "cqr", 0.1, 42)

    county_id = stable_run_id(run_payload(*common, config=base))
    lender_id = stable_run_id(run_payload(*common, config=lender))
    log_id = stable_run_id(run_payload(*common, config=log_target))

    assert county_id != lender_id
    assert county_id != log_id


def test_run_id_includes_feature_reducer_context():
    base = {
        "target_transform": "identity",
        "splits": {"train": 0.6, "calibration": 0.2},
    }
    pca = {
        **base,
        "feature_reducer": {"method": "pca", "n_components": 5},
    }
    common = ("openml_mtp2_oz1143", "ridge", {"alpha": 1.0}, "normalized_abs", 0.1, 42)

    base_id = stable_run_id(run_payload(*common, config=base))
    pca_id = stable_run_id(run_payload(*common, config=pca))

    assert base_id != pca_id


def test_run_id_includes_configured_cp_method_params():
    base = {
        "target_transform": "identity",
        "splits": {"train": 0.6, "calibration": 0.2},
        "cp_method_configs": {
            "cqr_gb_small": {
                "method_id": "cqr",
                "params": {"backend": "gradient_boosting", "n_estimators": 20},
            }
        },
    }
    changed = {
        **base,
        "cp_method_configs": {
            "cqr_gb_small": {
                "method_id": "cqr",
                "params": {"backend": "gradient_boosting", "n_estimators": 40},
            }
        },
    }
    common = (
        "openml_cholesterol_chol",
        "ridge",
        {"alpha": 1.0},
        "cqr_gb_small",
        0.1,
        11,
    )

    method_id, params = cp_method_settings(base, "cqr_gb_small")
    base_id = stable_run_id(run_payload(*common, config=base))
    changed_id = stable_run_id(run_payload(*common, config=changed))

    assert method_id == "cqr"
    assert params["n_estimators"] == 20
    assert base_id != changed_id


def test_run_one_does_not_resume_legacy_terminal_checkpoint_by_default(
    tmp_path, monkeypatch
):
    config = {
        "target_transform": "identity",
        "splits": {"train": 0.6, "calibration": 0.2, "group_col": "county_code"},
    }
    dataset_id = "hmda_2025_wy_interest_rate"
    model_id = "ridge"
    model_params = {"alpha": 1.0}
    cp_method = "cqr"
    alpha = 0.1
    seed = 42
    checkpoint_root = tmp_path / "checkpoints"

    legacy_run_id = stable_run_id(
        run_payload(dataset_id, model_id, model_params, cp_method, alpha, seed)
    )
    pilot.checkpoint_run(
        checkpoint_root,
        pilot.RunRecord(
            run_id=legacy_run_id,
            dataset_id=dataset_id,
            model_id=model_id,
            cp_method=cp_method,
            split_seed=seed,
            alpha=alpha,
            status="completed",
        ),
    )

    def stop_at_dataset_load(_dataset_id):
        raise RuntimeError("dataset load reached")

    monkeypatch.setattr(pilot, "load_dataset_frame", stop_at_dataset_load)

    try:
        pilot.run_one(
            dataset_id=dataset_id,
            model_id=model_id,
            model_family="linear",
            model_params=model_params,
            cp_method=cp_method,
            alpha=alpha,
            seed=seed,
            config=config,
            checkpoint_root=checkpoint_root,
            prediction_cache_root=tmp_path / "predictions",
            audit_root=tmp_path / "audits",
            force=False,
            dataset_cache={},
            audited_datasets=set(),
        )
    except RuntimeError as exc:
        assert str(exc) == "dataset load reached"
    else:
        raise AssertionError("modern run must not resume a legacy run_id_v1 by default")


def test_run_one_resumes_legacy_terminal_checkpoint_only_with_explicit_migration_flag(
    tmp_path, monkeypatch
):
    config = {
        "target_transform": "identity",
        "splits": {"train": 0.6, "calibration": 0.2, "group_col": "county_code"},
        "resume": {"allow_legacy_run_id_v1": True},
    }
    dataset_id = "hmda_2025_wy_interest_rate"
    model_id = "ridge"
    model_params = {"alpha": 1.0}
    cp_method = "cqr"
    alpha = 0.1
    seed = 42
    checkpoint_root = tmp_path / "checkpoints"

    legacy_run_id = stable_run_id(
        run_payload(dataset_id, model_id, model_params, cp_method, alpha, seed)
    )
    pilot.checkpoint_run(
        checkpoint_root,
        pilot.RunRecord(
            run_id=legacy_run_id,
            dataset_id=dataset_id,
            model_id=model_id,
            cp_method=cp_method,
            split_seed=seed,
            alpha=alpha,
            status="completed",
        ),
    )

    def fail_load_dataset_frame(_dataset_id):
        raise AssertionError("explicit legacy migration should skip before dataset load")

    monkeypatch.setattr(pilot, "load_dataset_frame", fail_load_dataset_frame)

    result = pilot.run_one(
        dataset_id=dataset_id,
        model_id=model_id,
        model_family="linear",
        model_params=model_params,
        cp_method=cp_method,
        alpha=alpha,
        seed=seed,
        config=config,
        checkpoint_root=checkpoint_root,
        prediction_cache_root=tmp_path / "predictions",
        audit_root=tmp_path / "audits",
        force=False,
        dataset_cache={},
        audited_datasets=set(),
    )

    assert result["status"] == "skipped_completed"
    assert result["run_id"] != legacy_run_id
    assert result["legacy_run_id"] == legacy_run_id
    assert result["resume_source"] == "legacy_run_id_v1"


def test_run_one_does_not_resume_legacy_checkpoint_when_feature_reducer_active(
    tmp_path, monkeypatch
):
    config = {
        "target_transform": "identity",
        "feature_reducer": {"method": "pca", "n_components": 2},
        "splits": {"train": 0.6, "calibration": 0.2},
    }
    dataset_id = "openml_mtp2_oz1143"
    model_id = "ridge"
    model_params = {"alpha": 1.0}
    cp_method = "normalized_abs"
    alpha = 0.1
    seed = 42
    checkpoint_root = tmp_path / "checkpoints"

    legacy_run_id = stable_run_id(
        run_payload(dataset_id, model_id, model_params, cp_method, alpha, seed)
    )
    pilot.checkpoint_run(
        checkpoint_root,
        pilot.RunRecord(
            run_id=legacy_run_id,
            dataset_id=dataset_id,
            model_id=model_id,
            cp_method=cp_method,
            split_seed=seed,
            alpha=alpha,
            status="completed",
        ),
    )

    def stop_at_dataset_load(_dataset_id):
        raise RuntimeError("dataset load reached")

    monkeypatch.setattr(pilot, "load_dataset_frame", stop_at_dataset_load)

    try:
        pilot.run_one(
            dataset_id=dataset_id,
            model_id=model_id,
            model_family="linear",
            model_params=model_params,
            cp_method=cp_method,
            alpha=alpha,
            seed=seed,
            config=config,
            checkpoint_root=checkpoint_root,
            prediction_cache_root=tmp_path / "predictions",
            audit_root=tmp_path / "audits",
            force=False,
            dataset_cache={},
            audited_datasets=set(),
        )
    except RuntimeError as exc:
        assert str(exc) == "dataset load reached"
    else:
        raise AssertionError("feature-reduced run must not resume a legacy run_id_v1")


def test_grouped_split_column_is_excluded_from_model_features(tmp_path):
    n = 60
    x = np.arange(n, dtype=float)
    df = pd.DataFrame(
        {
            "x": x,
            "group": np.where(x % 2 == 0, "even", "odd"),
            "holdout_id": [f"site_{idx // 5}" for idx in range(n)],
            "target": 1.5 * x + 3.0,
        }
    )
    config = {
        "splits": {"train": 0.6, "calibration": 0.2, "group_col": "holdout_id"},
        "logging": {"prediction_cache_root": str(tmp_path / "predictions")},
    }

    bundle = fit_or_load_prediction_bundle(
        dataset_id="synthetic_grouped_regression",
        df=df,
        target="target",
        group_col="group",
        model_id="ridge",
        model_family="linear",
        model_params={"alpha": 1.0},
        seed=17,
        config=config,
        cache_root=tmp_path / "predictions",
        force=False,
    )
    metadata = pd.read_json(bundle.artifact_dir / "metadata.json", typ="series")

    assert bundle.split_groups_train is not None
    assert len(bundle.split_groups_train) == len(bundle.y_train)
    assert metadata["split_group_col"] == "holdout_id"
    assert metadata["split_groups_train_available"] is True
    assert metadata["split_groups_train_unique"] == len(set(bundle.split_groups_train))
    assert "group" in metadata["feature_drop_columns"]
    assert "holdout_id" in metadata["feature_drop_columns"]
    assert all("holdout_id" not in name for name in metadata["feature_names"])
    assert metadata["feature_drop_policy"]["drop_split_group_col"] is True


def test_grouped_cv_plus_predictions_do_not_split_train_groups():
    X_train = np.arange(24, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.5 + X_train[:, 1]
    X_test = np.array([[30.0, 31.0], [32.0, 33.0]])
    split_groups_train = np.repeat(["g0", "g1", "g2", "g3"], 3)

    yhat_oof, yhat_test_by_fold, fold_ids, metadata = pilot.fit_grouped_cv_plus_predictions(
        "ridge",
        {"alpha": 1.0},
        X_train,
        y_train,
        X_test,
        split_groups_train,
        seed=13,
        n_folds=3,
    )

    assert yhat_oof.shape == y_train.shape
    assert yhat_test_by_fold.shape == (3, len(X_test))
    assert metadata["internal_resampling_unit"] == "split_group"
    assert metadata["groups_split_across_internal_folds"] is False
    for group in np.unique(split_groups_train):
        assert len(set(fold_ids[split_groups_train == group])) == 1


def test_build_interval_supports_cv_plus_with_runner_fits():
    X_train = np.arange(18, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.5 + X_train[:, 1]
    X_test = np.array([[20.0, 21.0], [22.0, 23.0]])

    result = build_interval(
        cp_method="cv_plus",
        alpha=0.2,
        y_cal=np.array([1.0, 2.0]),
        yhat_cal=np.array([1.0, 2.0]),
        yhat_test=np.array([1.0, 2.0]),
        groups_cal=np.array(["a", "b"]),
        groups_test=np.array(["a", "b"]),
        X_train=X_train,
        y_train=y_train,
        yhat_train=y_train,
        X_cal=np.array([[0.0, 1.0]]),
        X_test=X_test,
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
        cv_plus_folds=3,
    )

    assert result.metadata["method"] == "cv_plus"
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_supports_grouped_cv_plus_with_runner_fits():
    X_train = np.arange(36, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.5 + X_train[:, 1]
    X_test = np.array([[40.0, 41.0], [42.0, 43.0]])
    split_groups_train = np.repeat([f"site_{idx}" for idx in range(6)], 3)

    result = build_interval(
        cp_method="cv_plus_grouped",
        alpha=0.2,
        y_cal=np.array([1.0, 2.0]),
        yhat_cal=np.array([1.0, 2.0]),
        yhat_test=np.array([1.0, 2.0]),
        groups_cal=np.array(["a", "b"]),
        groups_test=np.array(["a", "b"]),
        X_train=X_train,
        y_train=y_train,
        yhat_train=y_train,
        X_cal=np.array([[0.0, 1.0]]),
        X_test=X_test,
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
        cv_plus_folds=3,
        split_groups_train=split_groups_train,
    )

    assert result.metadata["method"] == "cv_plus_grouped"
    assert result.metadata["base_method"] == "cv_plus"
    assert result.metadata["internal_resampling_unit"] == "split_group"
    assert result.metadata["groups_split_across_internal_folds"] is False
    assert result.metadata["n_internal_groups"] == 6
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_supports_configured_cqr_backend():
    X_train = np.arange(30, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.2 + X_train[:, 1] * 0.1
    X_cal = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
    y_cal = np.array([0.5, 0.8, 1.2, 1.7])
    X_test = np.array([[9.0, 10.0], [11.0, 12.0]])

    result = build_interval(
        cp_method="cqr",
        alpha=0.2,
        y_cal=y_cal,
        yhat_cal=np.zeros_like(y_cal),
        yhat_test=np.zeros(2),
        groups_cal=np.array(["a", "a", "b", "b"]),
        groups_test=np.array(["a", "b"]),
        X_train=X_train,
        y_train=y_train,
        yhat_train=y_train,
        X_cal=X_cal,
        X_test=X_test,
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
        cqr_params={
            "backend": "gradient_boosting",
            "n_estimators": 5,
            "max_depth": 1,
            "learning_rate": 0.05,
        },
    )

    assert result.metadata["method"] == "cqr"
    assert result.metadata["cqr_backend"] == "gradient_boosting"
    assert result.metadata["cqr_backend_params"]["n_estimators"] == 5
    assert result.metadata["cqr_backend_params"]["max_depth"] == 1
    assert result.metadata["lower_quantile"] == 0.1
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_supports_cv_minmax_with_runner_fits():
    X_train = np.arange(18, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.5 + X_train[:, 1]
    X_test = np.array([[20.0, 21.0], [22.0, 23.0]])

    result = build_interval(
        cp_method="cv_minmax",
        alpha=0.2,
        y_cal=np.array([1.0, 2.0]),
        yhat_cal=np.array([1.0, 2.0]),
        yhat_test=np.array([1.0, 2.0]),
        groups_cal=np.array(["a", "b"]),
        groups_test=np.array(["a", "b"]),
        X_train=X_train,
        y_train=y_train,
        yhat_train=y_train,
        X_cal=np.array([[0.0, 1.0]]),
        X_test=X_test,
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
        cv_plus_folds=3,
    )

    assert result.metadata["method"] == "cv_minmax"
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_supports_grouped_cv_minmax_with_runner_fits():
    X_train = np.arange(36, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.5 + X_train[:, 1]
    X_test = np.array([[40.0, 41.0], [42.0, 43.0]])
    split_groups_train = np.repeat([f"site_{idx}" for idx in range(6)], 3)

    result = build_interval(
        cp_method="cv_minmax_grouped",
        alpha=0.2,
        y_cal=np.array([1.0, 2.0]),
        yhat_cal=np.array([1.0, 2.0]),
        yhat_test=np.array([1.0, 2.0]),
        groups_cal=np.array(["a", "b"]),
        groups_test=np.array(["a", "b"]),
        X_train=X_train,
        y_train=y_train,
        yhat_train=y_train,
        X_cal=np.array([[0.0, 1.0]]),
        X_test=X_test,
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
        cv_plus_folds=3,
        split_groups_train=split_groups_train,
    )

    assert result.metadata["method"] == "cv_minmax_grouped"
    assert result.metadata["base_method"] == "cv_minmax"
    assert result.metadata["internal_resampling_unit"] == "split_group"
    assert result.metadata["groups_split_across_internal_folds"] is False
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_skips_grouped_cv_plus_without_train_split_groups():
    X_train = np.arange(18, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.5 + X_train[:, 1]

    try:
        build_interval(
            cp_method="cv_plus_grouped",
            alpha=0.2,
            y_cal=np.array([1.0, 2.0]),
            yhat_cal=np.array([1.0, 2.0]),
            yhat_test=np.array([1.0, 2.0]),
            groups_cal=np.array(["a", "b"]),
            groups_test=np.array(["a", "b"]),
            X_train=X_train,
            y_train=y_train,
            yhat_train=y_train,
            X_cal=np.array([[0.0, 1.0]]),
            X_test=np.array([[20.0, 21.0], [22.0, 23.0]]),
            seed=11,
            model_id="ridge",
            model_params={"alpha": 1.0},
            cv_plus_folds=3,
        )
    except MethodSkipped as exc:
        assert "split_groups_train is unavailable" in str(exc)
    else:
        raise AssertionError("expected MethodSkipped")


def test_build_interval_skips_cv_plus_above_configured_size():
    X_train = np.arange(24, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0]

    try:
        build_interval(
            cp_method="cv_plus",
            alpha=0.2,
            y_cal=np.array([1.0]),
            yhat_cal=np.array([1.0]),
            yhat_test=np.array([1.0]),
            groups_cal=np.array(["a"]),
            groups_test=np.array(["a"]),
            X_train=X_train,
            y_train=y_train,
            yhat_train=y_train,
            X_cal=np.array([[0.0, 1.0]]),
            X_test=np.array([[20.0, 21.0]]),
            seed=11,
            model_id="ridge",
            model_params={"alpha": 1.0},
            cv_plus_max_train_rows=3,
        )
    except MethodSkipped as exc:
        assert "cv_plus skipped" in str(exc)
    else:
        raise AssertionError("expected MethodSkipped")


def test_build_interval_skips_cv_minmax_above_configured_size():
    X_train = np.arange(24, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0]

    try:
        build_interval(
            cp_method="cv_minmax",
            alpha=0.2,
            y_cal=np.array([1.0]),
            yhat_cal=np.array([1.0]),
            yhat_test=np.array([1.0]),
            groups_cal=np.array(["a"]),
            groups_test=np.array(["a"]),
            X_train=X_train,
            y_train=y_train,
            yhat_train=y_train,
            X_cal=np.array([[0.0, 1.0]]),
            X_test=np.array([[20.0, 21.0]]),
            seed=11,
            model_id="ridge",
            model_params={"alpha": 1.0},
            cv_plus_max_train_rows=3,
        )
    except MethodSkipped as exc:
        assert "cv_minmax skipped" in str(exc)
    else:
        raise AssertionError("expected MethodSkipped")


def test_build_interval_supports_jackknife_after_bootstrap_with_oob_fits():
    X_train = np.arange(36, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.5 + X_train[:, 1]
    X_test = np.array([[40.0, 41.0], [42.0, 43.0]])

    result = build_interval(
        cp_method="jackknife_plus_after_bootstrap",
        alpha=0.2,
        y_cal=np.array([1.0, 2.0]),
        yhat_cal=np.array([1.0, 2.0]),
        yhat_test=np.array([1.0, 2.0]),
        groups_cal=np.array(["a", "b"]),
        groups_test=np.array(["a", "b"]),
        X_train=X_train,
        y_train=y_train,
        yhat_train=y_train,
        X_cal=np.array([[0.0, 1.0]]),
        X_test=X_test,
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
        jackknife_after_bootstrap_n_resamples=24,
        jackknife_after_bootstrap_sample_fraction=0.5,
        jackknife_after_bootstrap_min_oob=2,
    )

    assert result.metadata["method"] == "jackknife_plus_after_bootstrap"
    assert result.metadata["n_resamples"] == 24
    assert result.metadata["sample_fraction"] == 0.5
    assert result.metadata["min_oob_count"] >= 2
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_supports_split_tail_alias():
    result = build_interval(
        cp_method="split_tail_0.25",
        alpha=0.8,
        y_cal=np.array([-5.0, -4.0, -3.0, -2.0, -1.0, 1.0, 2.0, 3.0, 4.0, 8.0]),
        yhat_cal=np.zeros(10),
        yhat_test=np.array([10.0, 20.0]),
        groups_cal=np.array(["a"] * 10),
        groups_test=np.array(["a", "b"]),
        X_train=np.arange(12, dtype=float).reshape(-1, 2),
        y_train=np.arange(6, dtype=float),
        yhat_train=np.arange(6, dtype=float),
        X_cal=np.arange(20, dtype=float).reshape(-1, 2),
        X_test=np.array([[20.0, 21.0], [22.0, 23.0]]),
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
    )

    assert result.metadata["method"] == "split_tail"
    assert result.metadata["lower_tail_alpha_fraction"] == 0.25
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_supports_split_tail_grid_shortest_alias():
    result = build_interval(
        cp_method="split_tail_grid_shortest",
        alpha=0.8,
        y_cal=np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 20.0, 30.0, 100.0]),
        yhat_cal=np.zeros(10),
        yhat_test=np.array([10.0, 20.0]),
        groups_cal=np.array(["a"] * 10),
        groups_test=np.array(["a", "b"]),
        X_train=np.arange(12, dtype=float).reshape(-1, 2),
        y_train=np.arange(6, dtype=float),
        yhat_train=np.arange(6, dtype=float),
        X_cal=np.arange(20, dtype=float).reshape(-1, 2),
        X_test=np.array([[20.0, 21.0], [22.0, 23.0]]),
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
    )

    assert result.metadata["method"] == "split_tail_grid_shortest"
    assert result.metadata["allocation_selection_role"] == (
        "calibration_grid_min_width_diagnostic"
    )
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_supports_weighted_covariate_shift_alias():
    X_train = np.arange(20, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.25 + X_train[:, 1]
    X_cal = np.array(
        [
            [0.0, 0.2],
            [0.1, 0.0],
            [0.2, 0.1],
            [0.3, 0.2],
            [0.4, 0.2],
            [0.5, 0.3],
            [0.6, 0.4],
            [0.7, 0.4],
            [0.8, 0.5],
            [0.9, 0.6],
        ]
    )
    X_test = np.array([[0.45, 0.25]])

    result = build_interval(
        cp_method="weighted_abs_covariate_shift",
        alpha=0.2,
        y_cal=np.linspace(1.0, 10.0, 10),
        yhat_cal=np.linspace(1.1, 9.6, 10),
        yhat_test=np.array([10.0]),
        groups_cal=np.array(["a", "a", "a", "a", "a", "b", "b", "b", "b", "b"]),
        groups_test=np.array(["a"]),
        X_train=X_train,
        y_train=y_train,
        yhat_train=y_train,
        X_cal=X_cal,
        X_test=X_test,
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
        covariate_shift_probability_clip=0.05,
        covariate_shift_weight_clip=5.0,
    )

    assert result.metadata["method"] == "weighted_abs_covariate_shift"
    assert result.metadata["density_ratio_model"] == "logistic_regression_calibration_vs_test"
    assert result.metadata["weight_estimation"] == (
        "estimated_from_unlabeled_calibration_and_test_covariates"
    )
    assert result.lower.shape == (1,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_skips_weighted_covariate_shift_infinite_radius(monkeypatch):
    def fake_estimate_covariate_shift_weights(*args, **kwargs):
        return (
            np.ones(3, dtype=float),
            np.array([100.0], dtype=float),
            {"density_ratio_model": "test_double"},
        )

    monkeypatch.setattr(
        pilot,
        "estimate_covariate_shift_weights",
        fake_estimate_covariate_shift_weights,
    )

    try:
        pilot.build_interval(
            cp_method="weighted_abs_covariate_shift",
            alpha=0.2,
            y_cal=np.array([0.0, 0.0, 0.0]),
            yhat_cal=np.array([1.0, 2.0, 10.0]),
            yhat_test=np.array([100.0]),
            groups_cal=np.array(["a", "a", "b"]),
            groups_test=np.array(["a"]),
            X_train=np.arange(12, dtype=float).reshape(-1, 2),
            y_train=np.arange(6, dtype=float),
            yhat_train=np.arange(6, dtype=float),
            X_cal=np.arange(6, dtype=float).reshape(-1, 2),
            X_test=np.array([[20.0, 21.0]]),
            seed=11,
            model_id="ridge",
            model_params={"alpha": 1.0},
        )
    except MethodSkipped as exc:
        assert "infinite radii" in str(exc)
    else:
        raise AssertionError("expected MethodSkipped")


def test_build_interval_supports_venn_abers_quantile():
    X_train = np.arange(24, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.3 + np.sin(X_train[:, 1])
    yhat_train = y_train + np.linspace(-0.3, 0.4, len(y_train))
    X_cal = np.array([[2.0, 3.0], [4.0, 5.0], [6.0, 7.0], [8.0, 9.0], [10.0, 11.0]])
    y_cal = np.array([1.2, 1.6, 2.8, 3.2, 4.1])
    yhat_cal = np.array([1.0, 1.4, 2.5, 2.7, 3.6])
    X_test = np.array([[20.0, 21.0], [22.0, 23.0]])

    result = build_interval(
        cp_method="venn_abers_quantile",
        alpha=0.2,
        y_cal=y_cal,
        yhat_cal=yhat_cal,
        yhat_test=np.array([5.0, 6.0]),
        groups_cal=np.array(["a", "a", "b", "b", "b"]),
        groups_test=np.array(["a", "b"]),
        X_train=X_train,
        y_train=y_train,
        yhat_train=yhat_train,
        X_cal=X_cal,
        X_test=X_test,
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
        venn_abers_m=1,
    )

    assert result.metadata["method"] == "venn_abers_quantile"
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_supports_venn_abers_split_fallback():
    X_train = np.arange(24, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0] * 0.3 + np.sin(X_train[:, 1])
    yhat_train = y_train + np.linspace(-0.3, 0.4, len(y_train))
    X_cal = np.array([[2.0, 3.0], [4.0, 5.0], [6.0, 7.0], [8.0, 9.0], [10.0, 11.0]])
    y_cal = np.array([1.2, 1.6, 2.8, 3.2, 4.1])
    yhat_cal = np.array([1.0, 1.4, 2.5, 2.7, 3.6])
    X_test = np.array([[20.0, 21.0], [22.0, 23.0]])

    result = build_interval(
        cp_method="venn_abers_split_fallback",
        alpha=0.2,
        y_cal=y_cal,
        yhat_cal=yhat_cal,
        yhat_test=np.array([5.0, 6.0]),
        groups_cal=np.array(["a", "a", "b", "b", "b"]),
        groups_test=np.array(["a", "b"]),
        X_train=X_train,
        y_train=y_train,
        yhat_train=yhat_train,
        X_cal=X_cal,
        X_test=X_test,
        seed=11,
        model_id="ridge",
        model_params={"alpha": 1.0},
        venn_abers_m=1,
    )

    assert result.metadata["method"] == "venn_abers_split_fallback"
    assert result.metadata["bridge_method"] == "venn_abers_quantile"
    assert result.metadata["fallback_method"] == "split_abs"
    assert result.lower.shape == (2,)
    assert np.all(result.lower <= result.upper)


def test_build_interval_skips_jackknife_plus_above_configured_size():
    X_train = np.arange(12, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0]

    try:
        build_interval(
            cp_method="jackknife_plus",
            alpha=0.2,
            y_cal=np.array([1.0]),
            yhat_cal=np.array([1.0]),
            yhat_test=np.array([1.0]),
            groups_cal=np.array(["a"]),
            groups_test=np.array(["a"]),
            X_train=X_train,
            y_train=y_train,
            yhat_train=y_train,
            X_cal=np.array([[0.0, 1.0]]),
            X_test=np.array([[20.0, 21.0]]),
            seed=11,
            model_id="ridge",
            model_params={"alpha": 1.0},
            jackknife_plus_max_train_rows=3,
        )
    except MethodSkipped as exc:
        assert "jackknife_plus skipped" in str(exc)
    else:
        raise AssertionError("expected MethodSkipped")


def test_build_interval_skips_jackknife_minmax_above_configured_size():
    X_train = np.arange(12, dtype=float).reshape(-1, 2)
    y_train = X_train[:, 0]

    try:
        build_interval(
            cp_method="jackknife_minmax",
            alpha=0.2,
            y_cal=np.array([1.0]),
            yhat_cal=np.array([1.0]),
            yhat_test=np.array([1.0]),
            groups_cal=np.array(["a"]),
            groups_test=np.array(["a"]),
            X_train=X_train,
            y_train=y_train,
            yhat_train=y_train,
            X_cal=np.array([[0.0, 1.0]]),
            X_test=np.array([[20.0, 21.0]]),
            seed=11,
            model_id="ridge",
            model_params={"alpha": 1.0},
            jackknife_plus_max_train_rows=3,
        )
    except MethodSkipped as exc:
        assert "jackknife_plus skipped" in str(exc)
    else:
        raise AssertionError("expected MethodSkipped")


def test_failed_result_from_exception_writes_checkpoint(tmp_path):
    run = (
        "synthetic_dataset",
        "ridge",
        "linear",
        {"alpha": 1.0},
        "split_abs",
        0.1,
        42,
    )

    try:
        raise RuntimeError("synthetic failure")
    except RuntimeError as exc:
        result = failed_result_from_exception(run, tmp_path, exc)

    checkpoint = pd.read_json(result["checkpoint"], typ="series")
    assert result["status"] == "failed"
    assert result["error_type"] == "RuntimeError"
    assert checkpoint["status"] == "failed"
    assert "synthetic failure" in checkpoint["notes"]
