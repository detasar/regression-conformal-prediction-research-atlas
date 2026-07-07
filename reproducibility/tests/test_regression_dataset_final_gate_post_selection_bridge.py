import json
from pathlib import Path

import yaml

from experiments.regression.scripts import (
    build_dataset_final_gate_post_selection_validation_bridge as bridge,
)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_yaml(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def write_ledger(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_bridge_fixture(root):
    source_config = root / bridge.DEFAULT_SOURCE_CONFIG
    source_report = root / bridge.DEFAULT_SOURCE_REPORT
    source_feature_audit = root / bridge.DEFAULT_SOURCE_FEATURE_AUDIT
    remediation_plan = root / bridge.DEFAULT_REMEDIATION_PLAN
    ledger = (
        root
        / "experiments/regression/results/"
        "model_family_sweep_uci_wine_quality_duplicate_sensitivity/ledger.jsonl"
    )
    write_yaml(
        source_config,
        {
            "experiment_id": (
                "regression_model_family_sweep_uci_wine_quality_"
                "duplicate_sensitivity_v0"
            ),
            "random_seeds": [11, 23],
            "alphas": [0.1],
            "target_transform": "identity",
            "splits": {"train": 0.6, "calibration": 0.2, "test": 0.2},
            "conformal": {"cv_plus_folds": 5},
            "datasets": ["uci_wine_quality", "uci_wine_quality_dedup"],
            "models": [
                {
                    "model_id": "ridge",
                    "family": "linear",
                    "grid": {"alpha": [0.1, 1.0]},
                },
                {
                    "model_id": "random_forest",
                    "family": "tree_ensemble",
                    "grid": {"n_estimators": [10]},
                },
            ],
            "cp_methods": [
                "split_abs",
                "mondrian_abs",
                "normalized_abs",
                "cqr",
                "cv_plus",
                "venn_abers_quantile",
            ],
            "quality_controls": {
                "treat_quality_as_bounded_ordinal_numeric_target": True,
                "forbid_validated_venn_abers_regression_claims": True,
                "forbid_final_model_selection_claims": True,
            },
            "logging": {
                "ledger": bridge.rel(ledger, root),
                "checkpoint_root": "experiments/regression/results/source/checkpoints",
                "prediction_cache_root": (
                    "experiments/regression/results/source/checkpoints/predictions"
                ),
            },
        },
    )
    write_ledger(
        ledger,
        [
            {"dataset_id": "uci_wine_quality", "status": "completed"},
            {"dataset_id": "uci_wine_quality", "status": "completed"},
            {"dataset_id": "uci_wine_quality_dedup", "status": "completed"},
            {"dataset_id": "uci_wine_quality_dedup", "status": "completed"},
        ],
    )
    write_json(
        source_report,
        {
            "metadata": {
                "ledger_rows": 4,
                "status_counts": {"completed": 4},
                "dataset_counts": {
                    "uci_wine_quality": 2,
                    "uci_wine_quality_dedup": 2,
                },
            }
        },
    )
    write_json(
        source_feature_audit,
        {
            "violations_count": 0,
            "metadata_completeness": {
                "missing_feature_drop_columns": 0,
                "missing_feature_drop_policy": 0,
            },
            "backfill_policy_inference": {
                "exact_feature_set_enforced": True,
                "exact_drop_set_enforced": True,
            },
        },
    )
    write_json(
        remediation_plan,
        {
            "dataset_rows": [
                {
                    "dataset_id": "uci_wine_quality",
                    "readiness_status": (
                        "blocked_missing_post_selection_validation_bridge"
                    ),
                    "primary_next_action": "build_post_selection_validation_bridge",
                    "has_post_selection_validation_source": False,
                }
            ]
        },
    )
    return source_config, source_report, source_feature_audit, remediation_plan


def test_bridge_payload_generates_raw_uci_validation_config(tmp_path):
    source_config, source_report, source_feature_audit, remediation_plan = (
        write_bridge_fixture(tmp_path)
    )

    payload, config_writes = bridge.build_payload(
        root=tmp_path,
        source_config_path=source_config,
        source_report_path=source_report,
        source_feature_audit_path=source_feature_audit,
        remediation_plan_path=remediation_plan,
        bridge_results_path=tmp_path / bridge.DEFAULT_BRIDGE_RESULTS,
        config_dir=tmp_path / bridge.DEFAULT_CONFIG_DIR,
        results_root=tmp_path / bridge.DEFAULT_RESULTS_ROOT,
        dataset_id="uci_wine_quality",
        batch_id="demo_bridge",
    )
    config_path, config = config_writes[0]
    row = payload["generated_configs"][0]

    assert payload["summary"]["overall_status"] == (
        "dataset_final_gate_post_selection_validation_bridge_ready_no_promotions"
    )
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["execution_status"] == "config_generated_not_yet_run"
    assert payload["summary"]["observed_execution_status"] == "not_observed"
    assert (
        payload["summary"]["execution_reconciliation_status"]
        == "no_bridge_results_to_reconcile"
    )
    assert payload["summary"]["expected_atomic_run_count"] == 45
    assert payload["summary"]["source_feature_leakage_violation_count"] == 0
    assert len(config_writes) == 1
    assert config_path.name == (
        "method_selection_post_selection_validation_bridge_uci_wine_quality.yaml"
    )
    assert config["datasets"] == ["uci_wine_quality"]
    assert config["random_seeds"] == [101, 211, 307]
    assert config["alphas"] == [0.01, 0.05, 0.1, 0.15, 0.2]
    assert config["cp_methods"] == ["cqr", "cv_plus", "mondrian_abs"]
    assert config["models"] == [
        {"model_id": "ridge", "family": "linear", "grid": {"alpha": [0.1]}}
    ]
    assert config["quality_controls"][
        "dataset_final_gate_post_selection_validation_bridge"
    ] is True
    assert config["quality_controls"]["no_final_method_selection_claim"] is True
    assert config["quality_controls"][
        "forbid_validated_venn_abers_regression_claims"
    ] is True
    assert row["seed_overlap"] == []
    assert row["expected_atomic_run_count"] == 45
    assert row["source_ledger_row_count"] == 4
    assert row["source_completed_ledger_row_count"] == 4
    assert row["source_feature_leakage_violation_count"] == 0
    assert row["can_support_final_method_selection"] is False


def test_checked_in_uci_bridge_is_ready_without_promotions():
    payload, config_writes = bridge.build_payload(
        root=Path("."),
        source_config_path=Path(bridge.DEFAULT_SOURCE_CONFIG),
        source_report_path=Path(bridge.DEFAULT_SOURCE_REPORT),
        source_feature_audit_path=Path(bridge.DEFAULT_SOURCE_FEATURE_AUDIT),
        remediation_plan_path=Path(bridge.DEFAULT_REMEDIATION_PLAN),
        bridge_results_path=Path(bridge.DEFAULT_BRIDGE_RESULTS),
        config_dir=Path(bridge.DEFAULT_CONFIG_DIR),
        results_root=Path(bridge.DEFAULT_RESULTS_ROOT),
        dataset_id="uci_wine_quality",
        batch_id=bridge.DEFAULT_BATCH_ID,
    )
    row = payload["generated_configs"][0]
    config = config_writes[0][1]

    assert payload["summary"]["overall_status"] == (
        "dataset_final_gate_post_selection_validation_bridge_ready_no_promotions"
    )
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["reported_execution_status"] == "config_generated_not_yet_run"
    assert payload["summary"]["observed_execution_status"] == "ledgers_completed"
    assert payload["summary"]["execution_status"] == "completed_bridge_results"
    assert (
        payload["summary"]["execution_reconciliation_status"]
        == "reconciled_bridge_results_completed"
    )
    assert payload["summary"]["execution_reconciliation_requires_action"] is False
    assert payload["summary"]["bridge_results_completed_atomic_run_count"] == 45
    assert payload["summary"]["generated_config_count"] == 1
    assert payload["summary"]["expected_atomic_run_count"] == 45
    assert payload["summary"]["source_ledger_row_count"] == 1428
    assert payload["summary"]["source_completed_ledger_row_count"] == 1428
    assert payload["summary"]["source_feature_leakage_violation_count"] == 0
    assert row["dataset_id"] == "uci_wine_quality"
    assert row["source_report_dataset_count"] == 714
    assert row["validation_seeds"] == [101, 211, 307]
    assert row["seed_overlap"] == []
    assert row["cp_methods"] == ["cqr", "cv_plus", "mondrian_abs"]
    assert row["model_id"] == "ridge"
    assert row["model_grid"] == {"alpha": [0.1]}
    assert row["expected_atomic_run_count"] == 45
    assert row["reported_execution_status"] == "config_generated_not_yet_run"
    assert row["observed_execution_status"] == "ledgers_completed"
    assert row["execution_status"] == "completed_bridge_results"
    assert row["reconciled_execution_status"] == "completed_bridge_results"
    assert row["execution_reconciliation_requires_action"] is False
    assert row["can_support_final_method_selection"] is False
    assert config["datasets"] == ["uci_wine_quality"]
    assert config["quality_controls"]["raw_uci_wine_variant_only"] is True
    assert config["quality_controls"]["dedup_variant_not_rerun_in_bridge"] is True


def test_checked_in_uci_bridge_results_are_completed_no_promotion():
    payload = json.loads(
        Path(
            "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "dataset_final_gate_post_selection_validation_bridge_results.json"
        ).read_text(encoding="utf-8")
    )
    row = payload["dataset_rows"][0]

    assert payload["source_artifacts"] == {
        "dataset_final_gate_post_selection_validation_bridge": (
            "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "dataset_final_gate_post_selection_validation_bridge.json"
        )
    }
    assert payload["summary"]["overall_status"] == (
        "method_selection_post_selection_validation_results_ready_no_final_selection"
    )
    assert payload["summary"]["dataset_count"] == 1
    assert payload["summary"]["expected_atomic_run_count"] == 45
    assert payload["summary"]["completed_atomic_run_count"] == 45
    assert payload["summary"]["status_counts"] == {"completed": 45}
    assert payload["summary"]["pilot_summary_count"] == 1
    assert payload["summary"]["feature_leakage_sidecar_count"] == 1
    assert payload["summary"]["feature_leakage_violation_count"] == 0
    assert payload["summary"]["common_dataset_alpha_cell_count"] == 5
    assert payload["summary"]["diagnostic_winner_counts"] == {
        "cqr": 3,
        "cv_plus": 1,
        "mondrian_abs": 1,
    }
    assert payload["summary"]["width_pathology_row_count"] == 0
    assert payload["summary"]["can_support_final_method_selection"] is False
    assert row["dataset_id"] == "uci_wine_quality"
    assert row["completed_atomic_run_count"] == 45
    assert row["pilot_summary_row_count"] == 15
    assert row["feature_leakage_violations"] == 0
    assert payload["failed_checks"] == []
