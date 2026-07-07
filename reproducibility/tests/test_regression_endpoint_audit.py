import json
from collections import Counter
from pathlib import Path

import numpy as np

from experiments.regression.scripts import audit_methodology_sanity as sanity
from experiments.regression.scripts import audit_regression_endpoints as endpoints
from experiments.regression.scripts.aggregate_endpoint_audits import (
    aggregate_endpoint_audits,
)


def _completed_row(run_id: str, method: str) -> dict:
    return {
        "run_id": run_id,
        "status": "completed",
        "cp_method": method,
        "model_id": "ridge",
        "alpha": 0.1,
        "seed": 11,
        "prediction_artifact": f"{run_id}.json",
    }


def _write_legacy_prediction_bundle(cache_root: Path, artifact_id: str) -> None:
    artifact_dir = endpoints.prediction_artifact_dir(cache_root, artifact_id)
    artifact_dir.mkdir(parents=True)
    arrays = {
        "y_train": np.asarray([1.0]),
        "y_cal": np.asarray([2.0]),
        "y_test": np.asarray([3.0]),
        "yhat_train": np.asarray([1.1]),
        "yhat_cal": np.asarray([2.1]),
        "yhat_test": np.asarray([3.1]),
        "groups_cal": np.asarray(["g"]),
        "groups_test": np.asarray(["g"]),
        "X_train": np.asarray([[1.0]]),
        "X_cal": np.asarray([[2.0]]),
        "X_test": np.asarray([[3.0]]),
        "scale_cal": np.asarray([1.0]),
        "scale_test": np.asarray([1.0]),
    }
    np.savez_compressed(artifact_dir / "bundle.npz", **arrays)
    (artifact_dir / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_id": artifact_id,
                "fit_seconds": 0.5,
                "target_transform": "identity",
            }
        ),
        encoding="utf-8",
    )


def test_endpoint_audit_loads_legacy_prediction_bundle_with_explicit_caveat(tmp_path):
    artifact_id = "abcdef123456"
    _write_legacy_prediction_bundle(tmp_path, artifact_id)

    assert endpoints.load_prediction_bundle(tmp_path, artifact_id) is None

    bundle, reason = endpoints.load_prediction_bundle_allow_legacy(
        tmp_path,
        artifact_id,
    )

    assert bundle is not None
    assert bundle.cache_status == (
        "legacy_hit_missing_data_provenance_and_code_provenance"
    )
    assert reason == "missing_data_provenance_and_code_provenance"
    assert bundle.groups_test.tolist() == ["g"]


def test_endpoint_audit_records_legacy_prediction_cache_usage(
    tmp_path,
    monkeypatch,
):
    artifact_id = "abcdef123456"
    _write_legacy_prediction_bundle(tmp_path, artifact_id)
    rows = [
        {
            **_completed_row("r1", "split_abs"),
            "prediction_artifact": artifact_id,
        }
    ]

    def fake_build_from_row(row, config, prediction_cache_root, **kwargs):
        bundle = kwargs["prediction_bundle_loader"](
            prediction_cache_root,
            row["prediction_artifact"],
        )
        assert bundle.cache_status.startswith("legacy_hit_")
        return np.array([1.0]), np.array([2.0]), {}, {}

    monkeypatch.setattr(endpoints, "build_from_row", fake_build_from_row)

    payload = endpoints.audit_endpoints(
        rows,
        {},
        prediction_cache_root=tmp_path,
        observed_min=0.0,
        observed_max=10.0,
        lower_floor=None,
        upper_warning=None,
        max_completed=None,
        progress_every=0,
        allow_legacy_prediction_cache=True,
    )

    assert payload["legacy_prediction_cache_enabled"] is True
    assert payload["legacy_prediction_cache_record_count"] == 1
    assert payload["legacy_prediction_cache_artifact_count"] == 1
    assert payload["legacy_prediction_cache_reasons"] == {
        "missing_data_provenance_and_code_provenance": 1
    }
    assert payload["cache_stats"]["legacy_prediction_bundle_artifact_loads"] == 1


def test_endpoint_audit_method_filter_records_partial_coverage(monkeypatch):
    rows = [
        _completed_row("r1", "split_abs"),
        _completed_row("r2", "cqr"),
        _completed_row("r3", "venn_abers_quantile"),
    ]

    def fake_build_from_row(row, *args, **kwargs):
        offset = float(len(str(row["run_id"])))
        lower = np.array([1.0 + offset, 2.0 + offset])
        upper = np.array([3.0 + offset, 4.0 + offset])
        return lower, upper, {}, {}

    monkeypatch.setattr(endpoints, "build_from_row", fake_build_from_row)

    payload = endpoints.audit_endpoints(
        rows,
        {},
        prediction_cache_root=Path("unused"),
        observed_min=0.0,
        observed_max=10.0,
        lower_floor=0.0,
        upper_warning=20.0,
        max_completed=None,
        progress_every=0,
        exclude_methods={"venn_abers_quantile"},
    )

    assert payload["method_filter"] == {
        "include_methods": [],
        "exclude_methods": ["venn_abers_quantile"],
        "include_models": [],
        "exclude_models": [],
        "max_completed": None,
        "full_method_coverage": False,
    }
    assert payload["total_completed_ledger_rows"] == 3
    assert payload["filtered_completed_ledger_rows"] == 2
    assert payload["completed_ledger_rows"] == 2
    assert payload["reconstructed_runs"] == 2
    assert payload["configured_completed_method_counts"] == {"cqr": 1, "split_abs": 1}
    assert payload["omitted_completed_method_counts"] == {"venn_abers_quantile": 1}


def test_endpoint_audit_full_coverage_flag_without_filters(monkeypatch):
    rows = [_completed_row("r1", "split_abs")]

    def fake_build_from_row(row, *args, **kwargs):
        return np.array([1.0]), np.array([2.0]), {}, {}

    monkeypatch.setattr(endpoints, "build_from_row", fake_build_from_row)

    payload = endpoints.audit_endpoints(
        rows,
        {},
        prediction_cache_root=Path("unused"),
        observed_min=0.0,
        observed_max=10.0,
        lower_floor=None,
        upper_warning=None,
        max_completed=None,
        progress_every=0,
    )

    assert payload["method_filter"]["full_method_coverage"] is True
    assert payload["omitted_completed_method_counts"] == {}


def test_endpoint_audit_model_filter_records_partial_coverage(monkeypatch):
    rows = [
        {**_completed_row("r1", "split_abs"), "model_id": "ridge"},
        {**_completed_row("r2", "split_abs"), "model_id": "lightgbm"},
    ]

    def fake_build_from_row(row, *args, **kwargs):
        return np.array([1.0]), np.array([2.0]), {}, {}

    monkeypatch.setattr(endpoints, "build_from_row", fake_build_from_row)

    payload = endpoints.audit_endpoints(
        rows,
        {},
        prediction_cache_root=Path("unused"),
        observed_min=0.0,
        observed_max=10.0,
        lower_floor=None,
        upper_warning=None,
        max_completed=None,
        progress_every=0,
        include_models={"lightgbm"},
    )

    assert payload["method_filter"]["include_models"] == ["lightgbm"]
    assert payload["method_filter"]["full_method_coverage"] is False
    assert payload["total_completed_ledger_rows"] == 2
    assert payload["filtered_completed_ledger_rows"] == 1
    assert payload["completed_ledger_rows"] == 1
    assert payload["configured_completed_method_counts"] == {"split_abs": 1}


def test_cv_plus_endpoint_reconstruction_reuses_fold_predictions(monkeypatch):
    class Bundle:
        target_transform = "identity"
        X_train = np.arange(16, dtype=float).reshape(4, 4)
        y_train = np.array([1.0, 2.0, 3.0, 4.0])
        X_cal = np.arange(8, dtype=float).reshape(2, 4)
        X_test = np.arange(12, dtype=float).reshape(3, 4)
        yhat_train = np.array([1.1, 1.9, 3.1, 3.9])
        y_cal = np.array([1.5, 2.5])
        yhat_cal = np.array([1.4, 2.6])
        yhat_test = np.array([1.0, 2.0, 3.0])
        groups_cal = np.array(["a", "b"])
        groups_test = np.array(["a", "b", "a"])
        scale_cal = None
        scale_test = None

    fit_calls = {"count": 0}

    def fake_load_prediction_bundle(*args, **kwargs):
        return Bundle()

    def fake_fit_cv_plus_predictions(*args, **kwargs):
        fit_calls["count"] += 1
        return (
            np.array([1.0, 2.0, 3.0, 4.0]),
            np.array([[1.0, 2.0, 3.0], [1.2, 2.2, 3.2]]),
            np.array([0, 0, 1, 1]),
        )

    monkeypatch.setattr(endpoints, "load_prediction_bundle", fake_load_prediction_bundle)
    monkeypatch.setattr(
        endpoints, "fit_cv_plus_predictions", fake_fit_cv_plus_predictions
    )
    interval_cache = {}
    cache_stats = Counter()
    base_row = {
        "run_id": "run-alpha-010",
        "status": "completed",
        "cp_method": "cv_plus",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "alpha": 0.1,
        "seed": 11,
        "prediction_artifact": "same-bundle",
    }

    endpoints.build_from_row(
        base_row,
        {"conformal": {"cv_plus_folds": 2}},
        Path("unused"),
        interval_cache=interval_cache,
        cache_stats=cache_stats,
    )
    endpoints.build_from_row(
        {**base_row, "run_id": "run-alpha-020", "alpha": 0.2},
        {"conformal": {"cv_plus_folds": 2}},
        Path("unused"),
        interval_cache=interval_cache,
        cache_stats=cache_stats,
    )

    assert fit_calls["count"] == 1
    assert cache_stats["cv_plus_prediction_misses"] == 1
    assert cache_stats["cv_plus_prediction_hits"] == 1


def test_grouped_cv_endpoint_reconstruction_passes_split_groups_train(monkeypatch):
    class Bundle:
        target_transform = "identity"
        X_train = np.arange(16, dtype=float).reshape(4, 4)
        y_train = np.array([1.0, 2.0, 3.0, 4.0])
        X_cal = np.arange(8, dtype=float).reshape(2, 4)
        X_test = np.arange(12, dtype=float).reshape(3, 4)
        yhat_train = np.array([1.1, 1.9, 3.1, 3.9])
        y_cal = np.array([1.5, 2.5])
        yhat_cal = np.array([1.4, 2.6])
        yhat_test = np.array([1.0, 2.0, 3.0])
        groups_cal = np.array(["a", "b"])
        groups_test = np.array(["a", "b", "a"])
        split_groups_train = np.array(["g0", "g0", "g1", "g1"])
        scale_cal = None
        scale_test = None

    captured = {}

    def fake_load_prediction_bundle(*args, **kwargs):
        return Bundle()

    def fake_fit_grouped_cv_plus_predictions(
        model_id,
        model_params,
        X_train,
        y_train,
        X_test,
        split_groups_train,
        seed,
        *,
        n_folds,
        method_name,
    ):
        captured["method_name"] = method_name
        captured["split_groups_train"] = split_groups_train
        return (
            np.array([1.0, 2.0, 3.0, 4.0]),
            np.array([[1.0, 2.0, 3.0], [1.2, 2.2, 3.2]]),
            np.array([0, 0, 1, 1]),
            {"groups_split_across_internal_folds": False},
        )

    monkeypatch.setattr(endpoints, "load_prediction_bundle", fake_load_prediction_bundle)
    monkeypatch.setattr(
        endpoints,
        "fit_grouped_cv_plus_predictions",
        fake_fit_grouped_cv_plus_predictions,
    )

    lower, upper, _, _ = endpoints.build_from_row(
        _completed_row("r1", "cv_plus_grouped"),
        {"conformal": {"cv_plus_folds": 2}},
        Path("unused"),
    )

    assert captured["method_name"] == "cv_plus_grouped"
    assert np.array_equal(captured["split_groups_train"], Bundle.split_groups_train)
    assert lower.shape == (3,)
    assert upper.shape == (3,)


def test_grouped_cv_endpoint_reconstruction_reuses_fold_predictions(monkeypatch):
    class Bundle:
        target_transform = "identity"
        X_train = np.arange(16, dtype=float).reshape(4, 4)
        y_train = np.array([1.0, 2.0, 3.0, 4.0])
        X_cal = np.arange(8, dtype=float).reshape(2, 4)
        X_test = np.arange(12, dtype=float).reshape(3, 4)
        yhat_train = np.array([1.1, 1.9, 3.1, 3.9])
        y_cal = np.array([1.5, 2.5])
        yhat_cal = np.array([1.4, 2.6])
        yhat_test = np.array([1.0, 2.0, 3.0])
        groups_cal = np.array(["a", "b"])
        groups_test = np.array(["a", "b", "a"])
        split_groups_train = np.array(["g0", "g0", "g1", "g1"])
        scale_cal = None
        scale_test = None

    fit_calls = {"count": 0}

    def fake_load_prediction_bundle(*args, **kwargs):
        return Bundle()

    def fake_fit_grouped_cv_plus_predictions(*args, **kwargs):
        fit_calls["count"] += 1
        return (
            np.array([1.0, 2.0, 3.0, 4.0]),
            np.array([[1.0, 2.0, 3.0], [1.2, 2.2, 3.2]]),
            np.array([0, 0, 1, 1]),
            {"groups_split_across_internal_folds": False},
        )

    monkeypatch.setattr(endpoints, "load_prediction_bundle", fake_load_prediction_bundle)
    monkeypatch.setattr(
        endpoints,
        "fit_grouped_cv_plus_predictions",
        fake_fit_grouped_cv_plus_predictions,
    )
    interval_cache = {}
    cache_stats = Counter()
    base_row = {
        "run_id": "run-grouped-cv-plus",
        "status": "completed",
        "cp_method": "cv_plus_grouped",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "alpha": 0.1,
        "seed": 11,
        "prediction_artifact": "same-bundle",
    }

    endpoints.build_from_row(
        base_row,
        {"conformal": {"cv_plus_folds": 2}},
        Path("unused"),
        interval_cache=interval_cache,
        cache_stats=cache_stats,
    )
    endpoints.build_from_row(
        {**base_row, "run_id": "run-grouped-minmax", "cp_method": "cv_minmax_grouped"},
        {"conformal": {"cv_plus_folds": 2}},
        Path("unused"),
        interval_cache=interval_cache,
        cache_stats=cache_stats,
    )

    assert fit_calls["count"] == 1
    assert cache_stats["grouped_cv_prediction_misses"] == 1
    assert cache_stats["grouped_cv_prediction_hits"] == 1


def test_methodology_backlog_rejects_partial_endpoint_audit(tmp_path):
    endpoint_path = tmp_path / "endpoint_audit.json"
    endpoint_path.write_text(
        (
            '{"audit_schema":"cpfi_regression_endpoint_audit_v2",'
            '"method_filter":{"full_method_coverage":false}}'
        ),
        encoding="utf-8",
    )

    assert (
        sanity.artifact_satisfies_large_backlog(endpoint_path, "endpoint_audit.json")
        is False
    )

    endpoint_path.write_text(
        (
            '{"audit_schema":"cpfi_regression_endpoint_audit_v2",'
            '"method_filter":{"full_method_coverage":true}}'
        ),
        encoding="utf-8",
    )

    assert (
        sanity.artifact_satisfies_large_backlog(endpoint_path, "endpoint_audit.json")
        is True
    )


def _partial_endpoint_payload(method: str, runs: int, intervals: int) -> dict:
    stats = endpoints.empty_method_stats()
    stats.update(
        {
            "runs": runs,
            "intervals": intervals,
            "lower_below_floor": int(method == "split_abs"),
            "lower_below_observed_min": 0,
            "upper_above_observed_max": int(method == "cqr"),
            "max_width": 2.0 if method == "split_abs" else 3.0,
            "min_lower": 0.1 if method == "split_abs" else 0.2,
            "max_upper": 2.1 if method == "split_abs" else 3.2,
        }
    )
    return {
        "audit_schema": "cpfi_regression_endpoint_audit_v2",
        "method_filter": {
            "include_methods": [method],
            "exclude_methods": [],
            "max_completed": None,
            "full_method_coverage": False,
        },
        "total_completed_ledger_rows": 3,
        "filtered_completed_ledger_rows": runs,
        "completed_ledger_rows": runs,
        "reconstructed_runs": runs,
        "missing_artifacts": 0,
        "reconstruction_failures": 0,
        "observed_target_min": 0.0,
        "observed_target_max": 10.0,
        "lower_floor": 0.0,
        "upper_warning": 20.0,
        "available_completed_method_counts": {"cqr": 1, "split_abs": 2},
        "filtered_completed_method_counts": {method: runs},
        "configured_completed_method_counts": {method: runs},
        "omitted_completed_method_counts": {},
        "totals": stats,
        "method_summary": {method: stats},
        "cache_stats": {f"{method}_misses": runs},
        "failures": [],
        "failure_count_total": 0,
        "config": "config.yaml",
        "ledger": "ledger.jsonl",
    }


def test_aggregate_endpoint_audits_promotes_complete_method_coverage(tmp_path):
    split_path = tmp_path / "endpoint_audit__split_abs.json"
    cqr_path = tmp_path / "endpoint_audit__cqr.json"
    split_path.write_text(
        json.dumps(_partial_endpoint_payload("split_abs", 2, 6)),
        encoding="utf-8",
    )
    cqr_path.write_text(
        json.dumps(_partial_endpoint_payload("cqr", 1, 3)),
        encoding="utf-8",
    )

    payload = aggregate_endpoint_audits([split_path, cqr_path])

    assert payload["method_filter"]["full_method_coverage"] is True
    assert payload["method_filter"]["aggregated_partial_count"] == 2
    assert payload["completed_ledger_rows"] == 3
    assert payload["reconstructed_runs"] == 3
    assert payload["omitted_completed_method_counts"] == {}
    assert payload["totals"]["runs"] == 3
    assert payload["totals"]["intervals"] == 9
    assert payload["totals"]["lower_below_floor"] == 1
    assert payload["totals"]["upper_above_observed_max"] == 1
    assert payload["totals"]["max_width"] == 3.0
    assert payload["totals"]["min_lower"] == 0.1
    assert payload["totals"]["max_upper"] == 3.2
    assert set(payload["method_summary"]) == {"cqr", "split_abs"}


def test_aggregate_endpoint_audits_combines_duplicate_method_chunks(tmp_path):
    split_a = tmp_path / "endpoint_audit__split_abs__ridge.json"
    split_b = tmp_path / "endpoint_audit__split_abs__lightgbm.json"
    split_a.write_text(
        json.dumps(_partial_endpoint_payload("split_abs", 1, 3)),
        encoding="utf-8",
    )
    split_b.write_text(
        json.dumps(_partial_endpoint_payload("split_abs", 1, 4)),
        encoding="utf-8",
    )

    payload = aggregate_endpoint_audits([split_a, split_b])

    assert payload["method_filter"]["full_method_coverage"] is False
    assert payload["completed_ledger_rows"] == 2
    assert payload["reconstructed_runs"] == 2
    assert payload["configured_completed_method_counts"] == {"split_abs": 2}
    assert payload["omitted_completed_method_counts"] == {"cqr": 1}
    assert payload["method_summary"]["split_abs"]["runs"] == 2
    assert payload["method_summary"]["split_abs"]["intervals"] == 7


def test_aggregate_endpoint_audits_allows_duplicate_method_chunks(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(
        json.dumps(_partial_endpoint_payload("split_abs", 1, 3)),
        encoding="utf-8",
    )
    second.write_text(
        json.dumps(_partial_endpoint_payload("split_abs", 1, 3)),
        encoding="utf-8",
    )

    payload = aggregate_endpoint_audits([first, second])

    assert payload["method_summary"]["split_abs"]["runs"] == 2
    assert payload["method_summary"]["split_abs"]["intervals"] == 6


def test_endpoint_backlog_reports_partial_progress(tmp_path):
    root = tmp_path
    report_dir = root / "experiments/regression/reports/example"
    report_dir.mkdir(parents=True)
    pilot_path = report_dir / "pilot_summary.json"
    pilot_path.write_text(
        json.dumps({"metadata": {"status_counts": {"completed": 1000}}}),
        encoding="utf-8",
    )
    partial_path = report_dir / "endpoint_audit__split_abs.json"
    partial_path.write_text(
        json.dumps(_partial_endpoint_payload("split_abs", 2, 6)),
        encoding="utf-8",
    )
    payloads = [
        {
            "path": pilot_path,
            "payload": json.loads(pilot_path.read_text(encoding="utf-8")),
        }
    ]

    backlog = sanity.large_summary_backlog(payloads, root, "endpoint_audit.json")

    assert backlog == [
        {
            "path": "experiments/regression/reports/example/pilot_summary.json",
            "completed": 1000,
            "partial_endpoint_progress": {
                "partial_count": 1,
                "completed_ledger_rows": 2,
                "reconstructed_runs": 2,
                "reconstruction_failures": 0,
                "methods_completed": ["split_abs"],
                "omitted_completed_method_counts": {"cqr": 1},
                "malformed_partials": [],
            },
        }
    ]


def test_methodology_backlog_skips_root_aggregate_pilot_summary(tmp_path):
    root = tmp_path
    reports_root = root / "experiments/regression/reports"
    model_report = reports_root / "model_family_sweep_example"
    reports_root.mkdir(parents=True)
    model_report.mkdir()
    payloads = [
        {
            "path": reports_root / "pilot_summary.json",
            "payload": {"metadata": {"status_counts": {"completed": 1000}}},
        },
        {
            "path": model_report / "pilot_summary.json",
            "payload": {"metadata": {"status_counts": {"completed": 1000}}},
        },
    ]

    backlog = sanity.large_summary_backlog(payloads, root, "split_profile.json")

    assert backlog == [
        {
            "path": (
                "experiments/regression/reports/"
                "model_family_sweep_example/pilot_summary.json"
            ),
            "completed": 1000,
        }
    ]


def test_split_profile_integrity_scan_separates_duplicate_signatures(tmp_path):
    root = tmp_path
    report_dir = root / "experiments/regression/reports/example"
    report_dir.mkdir(parents=True)
    (report_dir / "split_profile.json").write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "dataset_id": "example_dataset",
                        "split_group_col": None,
                        "seeds": [
                            {
                                "seed": 11,
                                "row_id_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                                "split_group_overlaps": {},
                                "row_signature_overlaps": {
                                    "train_cal": 2,
                                    "train_test": 0,
                                    "cal_test": 1,
                                },
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    evidence = sanity.split_profile_integrity_scan(root)

    assert evidence["split_profiles_scanned"] == 1
    assert evidence["seed_profiles_scanned"] == 1
    assert evidence["row_id_overlap_violations"] == 0
    assert evidence["split_group_overlap_violations"] == 0
    assert evidence["duplicate_signature_warnings"] == 1
    assert evidence["total_duplicate_signature_pair_overlaps"] == 3
    assert evidence["duplicate_signature_by_dataset"] == {
        "example_dataset": {
            "seed_profiles": 1,
            "total_pair_overlaps": 3,
            "paths": ["experiments/regression/reports/example/split_profile.json"],
        }
    }


def test_split_profile_integrity_scan_flags_group_overlap(tmp_path):
    root = tmp_path
    report_dir = root / "experiments/regression/reports/example"
    report_dir.mkdir(parents=True)
    (report_dir / "split_profile.json").write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "dataset_id": "example_dataset",
                        "split_group_col": "household_id",
                        "seeds": [
                            {
                                "seed": 23,
                                "row_id_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                                "split_group_overlaps": {
                                    "train_cal": 1,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                                "row_signature_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    evidence = sanity.split_profile_integrity_scan(root)

    assert evidence["row_id_overlap_violations"] == 0
    assert evidence["split_group_overlap_violations"] == 1
    assert evidence["duplicate_signature_warnings"] == 0
    assert evidence["split_group_examples"][0]["split_group_col"] == "household_id"
