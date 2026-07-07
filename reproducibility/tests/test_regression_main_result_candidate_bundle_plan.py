import json
from pathlib import Path

import yaml

from experiments.regression.scripts import (
    build_main_result_candidate_bundle_plan as plan,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def source_config(dataset_id: str, *, alpha: float = 0.1) -> dict:
    return {
        "experiment_id": f"validation_{dataset_id}",
        "random_seeds": [101, 211, 307],
        "alphas": [0.01, 0.05, 0.1, 0.15, 0.2],
        "target_transform": "identity",
        "splits": {"train": 0.6, "calibration": 0.2, "test": 0.2},
        "conformal": {"cv_plus_folds": 5},
        "datasets": [dataset_id],
        "models": [
            {
                "model_id": "ridge",
                "family": "linear",
                "grid": {"alpha": [alpha]},
            }
        ],
        "cp_methods": ["cqr", "cv_plus", "mondrian_abs"],
        "post_selection_validation_provenance": {
            "source_selection_seeds": [11, 23, 47],
            "validation_seeds": [101, 211, 307],
        },
        "quality_controls": {"post_selection_validation_only_no_final_selection": True},
        "logging": {
            "ledger": f"experiments/regression/results/validation_{dataset_id}/ledger.jsonl"
        },
    }


def write_sources(root: Path) -> None:
    datasets = ["d1", "d2"]
    dataset_rows = []
    for dataset_id in datasets:
        config_path = (
            root
            / "experiments/regression/configs"
            / f"method_selection_post_selection_validation_{dataset_id}.yaml"
        )
        write_yaml(config_path, source_config(dataset_id))
        dataset_rows.append(
            {
                "dataset_id": dataset_id,
                "config_path": str(config_path.relative_to(root)),
                "experiment_id": f"validation_{dataset_id}",
                "ledger": f"experiments/regression/results/validation_{dataset_id}/ledger.jsonl",
                "pilot_summary": f"experiments/regression/reports/validation_{dataset_id}/pilot_summary.json",
                "completed_atomic_run_count": 45,
                "expected_atomic_run_count": 45,
                "feature_leakage_violations": 0,
            }
        )
    write_json(
        root / plan.VALIDATION_RESULTS,
        {
            "summary": {
                "candidate_methods": ["cqr", "cv_plus", "mondrian_abs"],
                "completed_atomic_run_count": 90,
                "failed_check_count": 0,
                "feature_leakage_violation_count": 0,
            },
            "dataset_rows": dataset_rows,
            "diagnostic_selection": {
                "diagnostic_winners_by_dataset": {
                    "d1": {"cqr": 4, "mondrian_abs": 1},
                    "d2": {"cqr": 2, "mondrian_abs": 3},
                }
            },
        },
    )
    write_json(root / plan.VALIDATION_BATCH, {"summary": {"candidate_methods": ["cqr"]}})
    write_json(
        root / plan.DATASET_FINAL_GATE,
        {"summary": {"overall_status": "blocked", "main_result_ready_dataset_count": 0}},
    )
    write_json(
        root / plan.SELECTION_RECORD,
        {
            "summary": {
                "overall_status": "selection_multiplicity_evidence_record_ready_no_final_selection",
                "diagnostic_primary_method": "cqr",
            }
        },
    )
    write_json(
        root / plan.PAPER_READINESS,
        {
            "summary": {
                "overall_status": "paper_readiness_blocked_with_evidence_map",
                "blocked_gate_count": 6,
            },
            "blocked_gates": [
                {"gate_id": "dataset_specific_final_gates", "status": "blocked"},
                {"gate_id": "final_method_model_selection_gate", "status": "blocked"},
            ],
        },
    )


def write_bridge_sources(root: Path) -> None:
    dataset_id = "d_bridge"
    config_path = (
        root
        / "experiments/regression/configs"
        / f"method_selection_post_selection_validation_bridge_{dataset_id}.yaml"
    )
    write_yaml(config_path, source_config(dataset_id, alpha=1.0))
    write_json(
        root / plan.DATASET_FINAL_GATE_POST_SELECTION_VALIDATION_BRIDGE_RESULTS,
        {
            "summary": {
                "candidate_methods": ["cqr", "cv_plus", "mondrian_abs"],
                "completed_atomic_run_count": 45,
                "failed_check_count": 0,
                "feature_leakage_violation_count": 0,
            },
            "dataset_rows": [
                {
                    "dataset_id": dataset_id,
                    "config_path": str(config_path.relative_to(root)),
                    "experiment_id": f"validation_bridge_{dataset_id}",
                    "ledger": (
                        "experiments/regression/results/"
                        f"validation_bridge_{dataset_id}/ledger.jsonl"
                    ),
                    "pilot_summary": (
                        "experiments/regression/reports/"
                        f"validation_bridge_{dataset_id}/pilot_summary.json"
                    ),
                    "completed_atomic_run_count": 45,
                    "expected_atomic_run_count": 45,
                    "feature_leakage_violations": 0,
                }
            ],
            "diagnostic_selection": {
                "diagnostic_winners_by_dataset": {
                    dataset_id: {"cqr": 3, "cv_plus": 1, "mondrian_abs": 1}
                }
            },
        },
    )


def test_main_result_candidate_bundle_plan_materializes_fresh_configs(tmp_path):
    write_sources(tmp_path)

    payload, configs = plan.build_payload_and_configs(
        tmp_path,
        config_dir=tmp_path / plan.DEFAULT_CONFIG_DIR,
        results_root=tmp_path / plan.DEFAULT_RESULTS_ROOT,
    )

    assert payload["summary"]["overall_status"] == (
        "main_result_candidate_bundle_plan_ready_no_promotions"
    )
    assert payload["summary"]["can_support_main_result_promotion"] is False
    assert payload["summary"]["candidate_dataset_count"] == 2
    assert payload["summary"]["expected_atomic_run_count"] == 90
    assert payload["summary"]["candidate_primary_consistent_dataset_count"] == 1
    assert payload["summary"]["ambiguous_challenger_control_dataset_count"] == 1
    assert payload["failed_checks"] == []
    assert len(configs) == 2
    for config in configs.values():
        assert config["random_seeds"] == [401, 503, 701]
        assert config["cp_methods"] == ["cqr", "cv_plus", "mondrian_abs"]
        assert config["main_result_candidate_provenance"]["seed_overlap"] == []
        assert (
            config["quality_controls"]["forbid_main_result_claims_until_all_paper_gates_pass"]
            is True
        )


def test_main_result_candidate_bundle_plan_merges_bridge_validation_sources(tmp_path):
    write_sources(tmp_path)
    write_bridge_sources(tmp_path)

    payload, configs = plan.build_payload_and_configs(
        tmp_path,
        config_dir=tmp_path / plan.DEFAULT_CONFIG_DIR,
        results_root=tmp_path / plan.DEFAULT_RESULTS_ROOT,
    )

    assert payload["summary"]["candidate_dataset_count"] == 3
    assert payload["summary"]["expected_atomic_run_count"] == 135
    assert payload["summary"]["source_validation_standard_dataset_count"] == 2
    assert payload["summary"]["source_validation_bridge_dataset_count"] == 1
    assert payload["summary"]["source_validation_bridge_duplicate_dataset_count"] == 0
    assert payload["summary"]["source_validation_bridge_completed_atomic_rows"] == 45
    assert payload["summary"]["source_validation_combined_completed_atomic_rows"] == 135
    assert payload["summary"]["source_validation_combined_failed_check_count"] == 0
    assert payload["summary"]["candidate_primary_consistent_dataset_count"] == 1
    assert payload["summary"]["ambiguous_challenger_control_dataset_count"] == 1
    assert payload["summary"]["priority_counts"][
        "candidate_primary_supported_with_challenger_controls"
    ] == 1
    bridge_row = next(
        row for row in payload["candidate_rows"] if row["dataset_id"] == "d_bridge"
    )
    assert bridge_row["source_validation_kind"] == (
        "dataset_final_gate_bridge_post_selection_validation"
    )
    assert bridge_row["promotion_priority"] == (
        "candidate_primary_supported_with_challenger_controls"
    )
    assert bridge_row["config_path"] in configs
    assert configs[bridge_row["config_path"]]["main_result_candidate_provenance"][
        "source_validation_kind"
    ] == "dataset_final_gate_bridge_post_selection_validation"


def test_checked_in_main_result_candidate_plan_has_no_promotions():
    payload, _ = plan.build_payload_and_configs(
        Path("."),
        config_dir=plan.DEFAULT_CONFIG_DIR,
        results_root=plan.DEFAULT_RESULTS_ROOT,
    )

    assert payload["summary"]["candidate_dataset_count"] == 6
    assert payload["summary"]["generated_config_count"] == 6
    assert payload["summary"]["expected_atomic_run_count"] == 270
    assert payload["summary"]["can_support_main_result_promotion"] is False
    assert payload["summary"]["diagnostic_primary_method"] == "cqr"
    assert payload["summary"]["candidate_primary_consistent_dataset_count"] == 4
    assert payload["summary"]["ambiguous_challenger_control_dataset_count"] == 1
    assert payload["summary"]["source_validation_bridge_dataset_count"] == 1
    assert payload["summary"]["source_validation_bridge_completed_atomic_rows"] == 45
    assert payload["summary"]["source_validation_combined_completed_atomic_rows"] == 270
    assert payload["summary"]["priority_counts"][
        "candidate_primary_supported_with_challenger_controls"
    ] == 1
