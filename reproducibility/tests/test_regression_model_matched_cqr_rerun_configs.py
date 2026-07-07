import yaml

from experiments.regression.scripts import build_model_matched_cqr_rerun_configs as rerun


def test_model_matched_cqr_rerun_config_replaces_cqr_and_preserves_comparators(tmp_path):
    root = tmp_path
    config_dir = root / "experiments/regression/configs"
    config_dir.mkdir(parents=True)
    source = config_dir / "model_family_sweep_toy.yaml"
    source.write_text(
        yaml.safe_dump(
            {
                "experiment_id": "regression_model_family_sweep_toy_v0",
                "purpose": "toy source",
                "random_seeds": [1, 2],
                "alphas": [0.1],
                "splits": {"train": 0.6, "calibration": 0.2, "test": 0.2},
                "datasets": ["toy"],
                "models": [
                    {
                        "model_id": "ridge",
                        "family": "linear",
                        "grid": {"alpha": [0.1, 1.0]},
                    }
                ],
                "cp_methods": ["split_abs", "cqr", "cv_plus"],
                "quality_controls": {
                    "interpret_cqr_as_fixed_quantile_backend": True,
                    "forbid_validated_venn_abers_regression_claims": True,
                },
                "logging": {
                    "ledger": "experiments/regression/results/source/ledger.jsonl",
                    "checkpoint_root": "experiments/regression/results/source/checkpoints",
                    "prediction_cache_root": "experiments/regression/results/source/checkpoints/predictions",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload, generated = rerun.build_payload(root, config_dir, "model_family_sweep_*.yaml")

    assert payload["summary"]["generated_config_count"] == 1
    assert payload["summary"]["expected_atomic_run_count"] == 12
    assert payload["summary"]["expected_cqr_model_matched_run_count"] == 4
    row = payload["generated_configs"][0]
    config = generated[root / row["generated_config"]]
    assert config["experiment_id"] == "regression_model_family_sweep_toy_model_matched_cqr_v1"
    assert config["cp_methods"] == ["split_abs", "cqr_model_matched", "cv_plus"]
    assert config["cp_method_configs"]["cqr_model_matched"]["method_id"] == (
        "cqr_model_matched"
    )
    controls = config["quality_controls"]
    assert "interpret_cqr_as_fixed_quantile_backend" not in controls
    assert controls["interpret_cqr_as_model_matched_quantile_backend"] is True
    assert controls["historical_fixed_gbm_cqr_preserved_as_comparator"] is True
    assert controls["no_method_winner_claim"] is True
    assert config["logging"]["ledger"].endswith(
        "model_family_sweep_toy_model_matched_cqr_v1/ledger.jsonl"
    )
    assert config["rerun_metadata"]["fixed_gbm_cqr_rows_preserved"] is True
