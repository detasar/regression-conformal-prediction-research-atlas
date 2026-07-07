import json
from pathlib import Path

import yaml

from experiments.regression.scripts import (
    build_method_selection_alpha_expansion_batch as batch,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def source_config(path: Path, dataset_id: str) -> None:
    write_yaml(
        path,
        {
            "experiment_id": f"source_{dataset_id}_v0",
            "random_seeds": [1, 2],
            "alphas": [0.10],
            "target_transform": "identity",
            "splits": {"train": 0.6, "calibration": 0.2, "test": 0.2},
            "conformal": {"cv_plus_folds": 5, "venn_abers_m": 1},
            "datasets": [dataset_id],
            "models": [
                {
                    "model_id": "ridge",
                    "family": "linear",
                    "grid": {"alpha": [0.1, 1.0]},
                },
                {
                    "model_id": "random_forest",
                    "family": "tree_ensemble",
                    "grid": {"n_estimators": [20, 40]},
                },
            ],
            "cp_methods": ["cqr", "cv_plus", "mondrian_abs"],
            "quality_controls": {"forbid_final_model_selection_claims": True},
            "logging": {
                "ledger": f"experiments/regression/results/source_{dataset_id}/ledger.jsonl",
                "checkpoint_root": f"experiments/regression/results/source_{dataset_id}/checkpoints",
            },
        },
    )


def task(dataset_id: str, alpha: str, config_path: str) -> dict:
    return {
        "task_id": f"method_selection_alpha_expansion::{dataset_id}::alpha_{alpha.replace('.', '_')}",
        "dataset_id": dataset_id,
        "target_alpha": alpha,
        "missing_candidate_methods": ["cqr", "cv_plus"],
        "method_run_task_count": 2,
        "status": "ready_for_config_clone",
        "source_configs": [
            {
                "config_id": f"config:source_{dataset_id}_v0",
                "config_path": config_path,
                "experiment_id": f"source_{dataset_id}_v0",
            }
        ],
    }


def test_alpha_expansion_batch_materializes_resumable_configs(tmp_path):
    root = tmp_path
    d1_config = Path("experiments/regression/configs/source_d1.yaml")
    d2_config = Path("experiments/regression/configs/source_d2.yaml")
    source_config(root / d1_config, "d1")
    source_config(root / d2_config, "d2")
    plan_path = root / "plan.json"
    write_json(
        plan_path,
        {
            "summary": {
                "overall_status": "method_selection_alpha_expansion_plan_ready",
                "can_support_final_method_selection": False,
            },
            "next_batch_dataset_alpha_tasks": [
                task("d1", "0.01", str(d1_config)),
                task("d1", "0.05", str(d1_config)),
                task("d2", "0.01", str(d2_config)),
            ],
        },
    )

    payload, writes = batch.build_payload(
        root=root,
        plan_path=plan_path,
        config_dir=root / "experiments/regression/configs",
        results_root=Path("experiments/regression/results"),
        batch_id="test_batch",
    )

    assert payload["summary"]["overall_status"] == "method_selection_alpha_expansion_batch_ready"
    assert payload["summary"]["generated_config_count"] == 2
    assert payload["summary"]["planned_dataset_alpha_task_count"] == 3
    assert payload["summary"]["planned_method_run_task_count"] == 6
    assert payload["summary"]["expected_atomic_run_count"] == 12
    assert {path.name for path, _ in writes} == {
        "method_selection_alpha_expansion_d1.yaml",
        "method_selection_alpha_expansion_d2.yaml",
    }

    configs = {config["datasets"][0]: config for _, config in writes}
    assert configs["d1"]["alphas"] == [0.01, 0.05]
    assert configs["d2"]["alphas"] == [0.01]
    assert configs["d1"]["cp_methods"] == ["cqr", "cv_plus"]
    assert configs["d1"]["models"] == [
        {"model_id": "ridge", "family": "linear", "grid": {"alpha": [0.1]}}
    ]
    assert configs["d1"]["quality_controls"][
        "support_expansion_only_no_final_selection"
    ]
    assert configs["d1"]["alpha_expansion_provenance"]["source_config"] == str(
        d1_config
    )


def test_alpha_expansion_batch_fails_without_source_config_traceability(tmp_path):
    root = tmp_path
    plan_path = root / "plan.json"
    write_json(
        plan_path,
        {
            "summary": {
                "overall_status": "method_selection_alpha_expansion_plan_ready",
                "can_support_final_method_selection": False,
            },
            "next_batch_dataset_alpha_tasks": [
                task("d1", "0.01", "experiments/regression/configs/missing.yaml")
            ],
        },
    )

    payload, writes = batch.build_payload(
        root=root,
        plan_path=plan_path,
        config_dir=root / "experiments/regression/configs",
        results_root=Path("experiments/regression/results"),
        batch_id="test_batch",
    )

    assert payload["summary"]["overall_status"] == "method_selection_alpha_expansion_batch_failed"
    failed = {check["check_id"] for check in payload["failed_checks"]}
    assert "source_config_traceability_present" in failed
    assert "representative_model_scope_enforced" in failed
    assert writes[0][1]["random_seeds"] == []
