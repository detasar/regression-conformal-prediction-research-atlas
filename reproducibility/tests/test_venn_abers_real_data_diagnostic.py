import json

import numpy as np
import pandas as pd
import pytest

from experiments.regression.scripts import benchmark_venn_abers_real_data as diagnostic


def minimal_diagnostic_config(tmp_path=None):
    logging = {
        "ledger": "ledger.jsonl",
        "checkpoint_root": "checkpoints",
        "prediction_cache_root": "checkpoints/predictions",
        "report_dir": "report",
    }
    if tmp_path is not None:
        logging = {
            "ledger": str(tmp_path / "ledger.jsonl"),
            "checkpoint_root": str(tmp_path / "checkpoints"),
            "prediction_cache_root": str(tmp_path / "checkpoints" / "predictions"),
            "report_dir": str(tmp_path / "report"),
        }
    return {
        "experiment_id": "synthetic_venn_abers_real_data",
        "purpose": "synthetic test",
        "random_seeds": [7],
        "alphas": [0.20],
        "target_transform": "identity",
        "splits": {"train": 0.60, "calibration": 0.20, "test": 0.20},
        "conformal": {
            "venn_abers_m": 1,
            "ivapd_grid_size": 9,
            "ivapd_max_test_rows": 3,
            "venn_abers_grid_size": 31,
            "venn_abers_grid_max_test_rows": 4,
        },
        "baseline_interval_methods": ["split_abs", "venn_abers_split_fallback"],
        "methods_under_diagnostic": {
            "interval_method": "venn_abers_quantile",
            "distribution_method": "ivapd_threshold_grid",
            "reference_method": "venn_abers_quantile_grid",
        },
        "datasets": ["synthetic_real"],
        "models": [
            {
                "model_id": "ridge",
                "family": "linear",
                "grid": {"alpha": [1.0]},
            }
        ],
        "logging": logging,
    }


def test_run_payload_includes_diagnostic_context_and_changes_with_config(tmp_path):
    base = minimal_diagnostic_config(tmp_path)
    changed = minimal_diagnostic_config(tmp_path)
    changed["conformal"]["ivapd_grid_size"] = 17

    common = {
        "dataset_id": "synthetic_real",
        "model_id": "ridge",
        "model_family": "linear",
        "model_params": {"alpha": 1.0},
        "alpha": 0.2,
        "seed": 7,
    }
    base_payload = diagnostic.run_payload(**common, config=base)
    changed_payload = diagnostic.run_payload(**common, config=changed)

    assert base_payload["schema"] == "venn_abers_real_data_diagnostic_run_payload_v2"
    assert (
        base_payload["diagnostic_run_context"]["schema"]
        == diagnostic.DIAGNOSTIC_RUN_CONTEXT_SCHEMA
    )
    assert (
        base_payload["diagnostic_run_context"]["diagnostic_conformal_settings"][
            "ivapd_grid_size"
        ]
        == 9
    )
    assert base_payload["run_payload_sha256"] != changed_payload["run_payload_sha256"]
    assert diagnostic.stable_run_id(base_payload) != diagnostic.stable_run_id(
        changed_payload
    )


def test_cached_diagnostic_requires_resume_compatibility(tmp_path):
    config = minimal_diagnostic_config(tmp_path)
    common = {
        "dataset_id": "synthetic_real",
        "model_id": "ridge",
        "model_family": "linear",
        "model_params": {"alpha": 1.0},
        "alpha": 0.2,
        "seed": 7,
    }
    payload = diagnostic.run_payload(**common, config=config)
    run_id = diagnostic.stable_run_id(payload)
    result_path = diagnostic.diagnostic_result_path(tmp_path / "checkpoints", run_id)
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        json.dumps({"status": "completed", "run_id": run_id}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="stale_incompatible"):
        diagnostic.run_one_diagnostic(
            **common,
            config=config,
            checkpoint_root=tmp_path / "checkpoints",
            prediction_cache_root=tmp_path / "checkpoints" / "predictions",
            force=False,
            dataset_cache={},
        )


def test_compatible_cached_diagnostic_loads_without_refitting(tmp_path):
    config = minimal_diagnostic_config(tmp_path)
    common = {
        "dataset_id": "synthetic_real",
        "model_id": "ridge",
        "model_family": "linear",
        "model_params": {"alpha": 1.0},
        "alpha": 0.2,
        "seed": 7,
    }
    payload = diagnostic.run_payload(**common, config=config)
    run_id = diagnostic.stable_run_id(payload)
    result_path = diagnostic.diagnostic_result_path(tmp_path / "checkpoints", run_id)
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": run_id,
                "resume_compatibility": diagnostic.expected_resume_compatibility(
                    payload
                ),
                "sentinel": "cached",
            }
        ),
        encoding="utf-8",
    )

    loaded = diagnostic.run_one_diagnostic(
        **common,
        config=config,
        checkpoint_root=tmp_path / "checkpoints",
        prediction_cache_root=tmp_path / "checkpoints" / "predictions",
        force=False,
        dataset_cache={},
    )

    assert loaded["status"] == "loaded_completed"
    assert loaded["sentinel"] == "cached"


def test_threshold_grid_and_test_subset_are_deterministic():
    y_cal = np.array([0.0, 1.0, 2.0, 3.0])
    yhat_cal = np.array([0.1, 0.9, 2.2, 2.8])
    yhat_test = np.array([0.5, 2.5])

    grid = diagnostic.build_threshold_grid(y_cal, yhat_cal, yhat_test, grid_size=9)
    selected = diagnostic.select_test_indices(np.array([3.0, 1.0, 4.0, 2.0, 0.0]), max_rows=3)

    assert len(grid) == 9
    assert np.all(np.diff(grid) > 0)
    assert grid[0] < min(y_cal.min(), yhat_test.min())
    assert grid[-1] > max(y_cal.max(), yhat_test.max())
    assert selected.tolist() == [2, 3, 4]


def test_residual_score_grid_covers_reference_scores():
    grid = diagnostic.build_residual_score_grid(
        y_cal=np.array([0.0, 2.0, 4.0]),
        yhat_cal=np.array([0.0, 1.0, 1.0]),
        reference_scores=np.array([0.5, 5.0]),
        grid_size=6,
    )

    assert len(grid) == 6
    assert grid[0] == 0.0
    assert np.all(np.diff(grid) > 0.0)
    assert grid[-1] > 5.0


def test_configured_ivar_m_values_filters_invalid_tail_parameters():
    values = diagnostic.configured_ivar_m_values(
        {"conformal": {"venn_abers_m": 1, "venn_abers_m_sensitivity": [1, 2, 4, 99]}},
        n_cal=9,
    )

    assert values == [1, 2, 4]


def test_configured_bridge_inflation_factors_keeps_positive_unique_values():
    values = diagnostic.configured_bridge_inflation_factors(
        {"conformal": {"venn_abers_bridge_inflation_factors": [2.0, 1.5, 0.0, 2.0]}}
    )

    assert values == [1.0, 1.5, 2.0]


def test_split_fallback_envelope_uses_larger_calibration_radius():
    bridge = type(
        "Interval",
        (),
        {
            "lower": np.array([0.0, 0.0]),
            "upper": np.array([0.0, 0.0]),
            "radii": np.array([1.0, 3.0]),
            "metadata": {"method": "venn_abers_quantile"},
        },
    )()
    split = type(
        "Interval",
        (),
        {
            "lower": np.array([0.0, 0.0]),
            "upper": np.array([0.0, 0.0]),
            "radii": np.array([2.0, 2.0]),
            "metadata": {"method": "split_abs"},
        },
    )()

    result = diagnostic.split_fallback_envelope(bridge, split, np.array([10.0, 20.0]))

    assert result.metadata["method"] == "venn_abers_split_fallback"
    assert result.metadata["calibration_only_fallback"] is True
    assert result.radii.tolist() == [2.0, 3.0]
    assert result.lower.tolist() == [8.0, 17.0]
    assert result.upper.tolist() == [12.0, 23.0]


def test_ivapd_interval_extractions_include_conservative_band():
    distribution = type(
        "Distribution",
        (),
        {
            "interval": lambda self, alpha, source: {
                "lower": (2.0, 8.0),
                "midpoint": (1.0, 9.0),
                "upper": (0.0, 10.0),
            }[source],
            "quantile": lambda self, probability, source: {
                ("upper", 0.1): -1.0,
                ("lower", 0.9): 11.0,
            }[(source, probability)],
        },
    )()

    extractions = diagnostic.ivapd_interval_extractions(distribution, alpha=0.2)

    assert set(extractions) == {"lower_cdf", "midpoint_cdf", "upper_cdf", "conservative_band"}
    assert extractions["conservative_band"]["lower"] == -1.0
    assert extractions["conservative_band"]["upper"] == 11.0


def test_ivapd_subset_scores_group_diagnostics():
    y_cal = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    yhat_cal = np.array([0.0, 1.1, 2.0, 2.9, 4.1])
    yhat_test = np.array([0.5, 1.5, 2.5, 3.5])
    y_test = np.array([0.4, 1.8, 2.2, 3.9])
    groups = np.array(["a", "a", "b", "b"])
    thresholds = diagnostic.build_threshold_grid(y_cal, yhat_cal, yhat_test, grid_size=11)

    result = diagnostic.score_ivapd_subset(
        y_cal=y_cal,
        yhat_cal=yhat_cal,
        yhat_test=yhat_test,
        y_test=y_test,
        groups_test=groups,
        alpha=0.2,
        thresholds=thresholds,
        max_test_rows=4,
    )

    assert result["method"] == "ivapd_threshold_grid"
    assert result["test_rows_scored"] == 4
    assert result["mean_midpoint_crps"] >= 0.0
    assert set(result["interval_extraction_summary"]) == {
        "conservative_band",
        "lower_cdf",
        "midpoint_cdf",
        "upper_cdf",
    }
    assert result["interval_extraction_summary"]["midpoint_cdf"]["coverage"] >= 0.0
    assert set(result["midpoint_crps_by_group"]) == {"a", "b"}
    assert result["midpoint_crps_gap"] is not None


def test_failure_diagnostics_distinguish_centered_and_noncentered_intervals():
    interval = type(
        "Interval",
        (),
        {
            "lower": np.array([0.0, 1.0, 3.0]),
            "upper": np.array([2.0, 3.0, 5.0]),
            "radii": np.array([1.0, 1.0, 1.0]),
        },
    )()
    y_true = np.array([1.0, 3.5, 2.5])
    yhat = np.array([1.0, 2.0, 4.0])

    split_diag = diagnostic.compute_failure_diagnostics("split_abs", interval, y_true, yhat)
    cqr_diag = diagnostic.compute_failure_diagnostics("cqr", interval, y_true, yhat)

    assert split_diag["miss_rate"] == 2 / 3
    assert split_diag["below_miss_rate"] == 1 / 3
    assert split_diag["above_miss_rate"] == 1 / 3
    assert split_diag["centered_residual_diagnostics"]["residual_exceeds_radius_rate"] == 2 / 3
    assert cqr_diag["centered_residual_diagnostics"] is None


def test_real_data_diagnostic_cli_writes_report_and_checkpoint(tmp_path, monkeypatch):
    n = 36
    x = np.arange(n, dtype=float)
    df = pd.DataFrame(
        {
            "x": x,
            "z": np.sin(x / 3.0),
            "group": np.where(x % 2 == 0, "even", "odd"),
            "target": 1.5 * x + np.where(x % 4 == 0, 2.0, -1.0),
        }
    )

    def fake_loader(dataset_id):
        assert dataset_id == "synthetic_real"
        return df, "target", "group"

    config = tmp_path / "diagnostic.yaml"
    config.write_text(
        f"""
experiment_id: synthetic_venn_abers_real_data
purpose: synthetic test
random_seeds: [7]
alphas: [0.20]
target_transform: identity
splits:
  train: 0.60
  calibration: 0.20
  test: 0.20
conformal:
  venn_abers_m: 1
  ivapd_grid_size: 9
  ivapd_max_test_rows: 3
baseline_interval_methods:
  - split_abs
  - venn_abers_split_fallback
  - normalized_abs
  - cqr
datasets:
  - synthetic_real
models:
  - model_id: ridge
    family: linear
    grid:
      alpha: [1.0]
logging:
  ledger: {tmp_path / "ledger.jsonl"}
  checkpoint_root: {tmp_path / "checkpoints"}
  prediction_cache_root: {tmp_path / "checkpoints" / "predictions"}
  report_dir: {tmp_path / "report"}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(diagnostic, "load_dataset_frame", fake_loader)
    monkeypatch.setattr("sys.argv", ["benchmark_venn_abers_real_data.py", "--config", str(config)])

    diagnostic.main()

    payload = json.loads((tmp_path / "report" / "diagnostic.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "report" / "diagnostic.md").read_text(encoding="utf-8")
    ledger = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()

    assert payload["benchmark_id"] == diagnostic.BENCHMARK_ID
    assert payload["summary"]["run_count"] == 1
    assert payload["summary"]["total_ivapd_rows_scored"] == 3
    assert set(payload["summary"]["ivapd_interval_extraction_summary"]) == {
        "conservative_band",
        "lower_cdf",
        "midpoint_cdf",
        "upper_cdf",
    }
    assert set(payload["summary"]["interval_method_summary"]) == {
        "cqr",
        "normalized_abs",
        "split_abs",
        "venn_abers_quantile",
        "venn_abers_split_fallback",
    }
    va_summary = payload["summary"]["interval_method_summary"]["venn_abers_quantile"]
    cqr_summary = payload["summary"]["interval_method_summary"]["cqr"]
    assert va_summary["mean_miss_rate_transformed"] >= 0.0
    assert va_summary["mean_radius_transformed"] is not None
    assert cqr_summary["mean_radius_transformed"] is None
    assert payload["summary"]["total_va_grid_reference_rows_scored"] > 0
    assert payload["summary"]["mean_va_grid_radius_ratio_vs_bridge"] >= 0.0
    assert "ivar_m_sensitivity_summary" in payload["summary"]
    assert "1" in payload["summary"]["ivar_m_sensitivity_summary"]
    assert "bridge_inflation_sensitivity_summary" in payload["summary"]
    assert "1" in payload["summary"]["bridge_inflation_sensitivity_summary"]
    assert "split_fallback_grid_summary" in payload["summary"]
    assert payload["summary"]["split_fallback_grid_summary"]["mean_coverage"] >= 0.0
    assert payload["results"][0]["primary_interval_method"] == "venn_abers_quantile"
    assert len(payload["results"][0]["interval_method_comparison"]) == 5
    assert "failure_diagnostics" in payload["results"][0]["interval_methods"]["venn_abers_quantile"]
    assert "venn_abers_quantile_grid_reference" in payload["results"][0]
    assert payload["results"][0]["venn_abers_quantile_grid_reference"]["score_grid_size"] == 31
    assert payload["results"][0]["venn_abers_quantile_grid_reference"][
        "bridge_inflation_sensitivity"
    ]
    assert payload["results"][0]["venn_abers_quantile_grid_reference"]["split_fallback_summary"]
    assert payload["results"][0]["venn_abers_quantile_grid_reference"]["ivar_m_sensitivity"]
    assert "Venn-Abers Real-Data Diagnostic" in markdown
    assert "Mean Interval Method Comparison" in markdown
    assert "IVAPD Interval Extraction Diagnostics" in markdown
    assert "Mean Failure-Mode Diagnostics" in markdown
    assert "Venn-Abers Bridge-vs-Grid Reference" in markdown
    assert "Calibration-Only Split Fallback Against Grid Reference" in markdown
    assert "Bridge Inflation Sensitivity Against Grid Reference" in markdown
    assert "IVAR m Sensitivity Against Grid Reference" in markdown
    assert len(ledger) == 1
    assert payload["results"][0]["artifact_paths"]["diagnostic"].endswith("diagnostic.json")
