import json
from pathlib import Path

from experiments.regression.scripts import (
    audit_method_selection_alpha_expansion_execution as execution,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_ledger(path: Path, dataset_id: str, *, row_count: int = 12) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for seed in [11, 23]:
        for alpha in [0.01, 0.05]:
            for method in ["cqr", "cv_plus", "mondrian_abs"]:
                rows.append(
                    {
                        "status": "completed",
                        "dataset_id": dataset_id,
                        "run_id": f"{dataset_id}_{seed}_{alpha}_{method}",
                        "seed": seed,
                        "alpha": alpha,
                        "cp_method": method,
                        "model_id": "ridge",
                    }
                )
    path.write_text(
        "\n".join(json.dumps(row) for row in rows[:row_count]) + "\n",
        encoding="utf-8",
    )


def write_sources(root: Path, *, missing_ledger: bool = False) -> tuple[Path, Path, Path]:
    plan_path = root / "plan.json"
    batch_path = root / "batch.json"
    post_selection_results_path = root / "post_selection_results.json"
    write_json(
        plan_path,
        {
            "summary": {
                "overall_status": "method_selection_alpha_expansion_plan_not_needed",
                "failed_check_count": 0,
                "additional_common_cells_needed_to_clear_threshold": 0,
                "current_common_alpha_distribution": {
                    "0.01": 1,
                    "0.05": 1,
                    "0.1": 2,
                },
                "current_common_alpha_max_cell_share": 0.5,
                "current_common_alpha_imbalance_status": "no_large_alpha_concentration",
                "imbalance_share_threshold": 0.75,
                "can_support_final_method_selection": False,
                "final_selection_claim_status": "blocked",
            }
        },
    )
    generated_configs = []
    for dataset_id in ["d1", "d2"]:
        ledger = (
            Path("experiments/regression/results")
            / f"method_selection_alpha_expansion_{dataset_id}"
            / "ledger.jsonl"
        )
        if not (missing_ledger and dataset_id == "d2"):
            write_ledger(root / ledger, dataset_id)
        generated_configs.append(
            {
                "dataset_id": dataset_id,
                "experiment_id": f"regression_method_selection_alpha_expansion_{dataset_id}_v1",
                "config_path": f"experiments/regression/configs/{dataset_id}.yaml",
                "ledger": str(ledger),
                "expected_atomic_run_count": 12,
                "target_alphas": ["0.01", "0.05"],
                "cp_methods": ["cqr", "cv_plus", "mondrian_abs"],
                "random_seeds": [11, 23],
                "model_id": "ridge",
            }
        )
    write_json(
        batch_path,
        {
            "summary": {
                "overall_status": "method_selection_alpha_expansion_batch_ready",
                "execution_status": "configs_generated_not_yet_run",
                "generated_config_count": 2,
                "can_support_final_method_selection": False,
            },
            "generated_configs": generated_configs,
        },
    )
    write_json(
        post_selection_results_path,
        {
            "summary": {
                "overall_status": (
                    "method_selection_post_selection_validation_results_"
                    "ready_no_final_selection"
                ),
                "completed_atomic_run_count": 24,
                "expected_atomic_run_count": 24,
                "common_dataset_alpha_cell_count": 4,
                "expected_common_dataset_alpha_cell_count": 4,
                "failed_check_count": 0,
                "diagnostic_winner_counts": {"cqr": 3, "mondrian_abs": 1},
                "can_support_final_method_selection": False,
            }
        },
    )
    return plan_path, batch_path, post_selection_results_path


def test_alpha_expansion_execution_audit_closes_completed_ledgers(tmp_path):
    plan_path, batch_path, post_selection_results_path = write_sources(tmp_path)

    payload = execution.build_payload(
        tmp_path,
        plan_path=plan_path,
        batch_path=batch_path,
        post_selection_results_path=post_selection_results_path,
    )

    assert (
        payload["summary"]["overall_status"]
        == "method_selection_alpha_expansion_execution_closed_no_final_selection"
    )
    assert payload["summary"]["completed_atomic_run_count"] == 24
    assert payload["summary"]["expected_atomic_run_count"] == 24
    assert payload["summary"]["observed_execution_status"] == "ledgers_completed"
    assert payload["summary"]["active_execution_status"] == "ledgers_completed"
    assert payload["summary"]["batch_generation_label_stale_after_execution"] is True
    assert payload["summary"]["batch_generation_label_historical_only"] is True
    assert payload["summary"]["batch_reported_execution_status_is_historical"] is True
    assert (
        payload["summary"]["batch_generation_label_reconciliation_status"]
        == "reconciled_historical_config_generation_label_with_completed_ledgers"
    )
    assert payload["summary"]["batch_generation_label_requires_action"] is False
    assert (
        payload["summary"]["execution_metadata_consistency_status"]
        == "historical_batch_generation_label_reconciled_no_action_required"
    )
    assert payload["summary"]["reconciled_execution_status"] == "ledgers_completed"
    assert (
        payload["summary"]["plan_overall_status"]
        == "method_selection_alpha_expansion_plan_not_needed"
    )
    assert (
        payload["summary"]["post_selection_validation_status"]
        == "method_selection_post_selection_validation_results_ready_no_final_selection"
    )
    assert payload["summary"]["can_support_final_method_selection"] is False
    assert payload["failed_checks"] == []


def test_alpha_expansion_execution_audit_blocks_missing_ledger(tmp_path):
    plan_path, batch_path, post_selection_results_path = write_sources(
        tmp_path, missing_ledger=True
    )

    payload = execution.build_payload(
        tmp_path,
        plan_path=plan_path,
        batch_path=batch_path,
        post_selection_results_path=post_selection_results_path,
    )

    assert (
        payload["summary"]["overall_status"]
        == "method_selection_alpha_expansion_execution_blocked"
    )
    failed = {row["check_id"] for row in payload["failed_checks"]}
    assert "generated_config_ledgers_present" in failed
    assert "ledger_counts_match_expected" in failed
    assert "ledger_statuses_completed" in failed
    assert (
        payload["summary"]["batch_generation_label_reconciliation_status"]
        == "unreconciled_ledgers_not_complete"
    )
    assert payload["summary"]["batch_generation_label_requires_action"] is True
