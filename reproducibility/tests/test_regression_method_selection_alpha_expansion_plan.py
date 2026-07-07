import json
from pathlib import Path

from experiments.regression.scripts import (
    build_method_selection_alpha_expansion_plan as plan,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def cell(dataset_id: str, alpha: str, method: str) -> dict:
    return {
        "dataset_id": dataset_id,
        "alpha": alpha,
        "cp_method": method,
        "row_count": 3,
        "metrics": {
            "coverage_error_abs": {"mean": 0.01},
            "interval_score": {"mean": 1.0},
            "mean_width": {"mean": 0.5},
        },
    }


def write_sources(root: Path, *, with_config: bool = True) -> tuple[Path, Path, Path, Path]:
    method_synthesis = root / "method_performance_synthesis.json"
    candidate_audit = root / "method_selection_candidate_audit.json"
    robustness_audit = root / "method_selection_robustness_audit.json"
    cross_run = root / "cross_run_integrity_audit.json"
    candidate_methods = ["cqr", "cv_plus", "mondrian_abs"]
    rows = []
    for dataset_id in ["d1", "d2", "d3", "d4"]:
        for method in candidate_methods:
            rows.append(cell(dataset_id, "0.1", method))
    for method in candidate_methods:
        rows.append(cell("d5", "0.2", method))
    write_json(
        method_synthesis,
        {
            "summary": {
                "overall_status": "method_performance_synthesis_descriptive_no_final_selection",
                "failed_check_count": 0,
                "completed_ledger_rows": 15,
            },
            "dataset_alpha_method_cells": rows,
        },
    )
    write_json(
        candidate_audit,
        {
            "summary": {
                "overall_status": "method_selection_candidate_audit_ready_no_final_selection",
                "failed_check_count": 0,
            },
            "shortlist_methods": [{"cp_method": method} for method in candidate_methods],
        },
    )
    write_json(
        robustness_audit,
        {
            "summary": {
                "overall_status": "method_selection_robustness_audit_ready_no_final_selection",
                "failed_check_count": 0,
                "can_support_final_method_selection": False,
                "final_selection_claim_status": "blocked",
            }
        },
    )
    config_path = root / "experiments/regression/configs/d1.yaml"
    if with_config:
        write_text(
            config_path,
            "\n".join(
                [
                    "experiment_id: d1_alpha_source",
                    "datasets: [d1]",
                    "alphas: [0.10]",
                    "cp_methods:",
                    "  - cqr",
                    "  - cv_plus",
                    "  - mondrian_abs",
                    "",
                ]
            ),
        )
    write_json(
        cross_run,
        {
            "summary": {"total_completed_rows": 15},
            "rows": [
                {
                    "report_id": "report:d1",
                    "report_name": "d1",
                    "config_path": "experiments/regression/configs/d1.yaml",
                    "dataset_ids": ["d1"],
                    "risk_level": "pass",
                    "ledger_rows": 9,
                    "large_sweep": False,
                }
            ],
        },
    )
    return method_synthesis, candidate_audit, robustness_audit, cross_run


def test_alpha_expansion_plan_builds_resumable_next_batch(tmp_path):
    sources = write_sources(tmp_path)

    payload = plan.build_payload(tmp_path, *sources)
    summary = payload["summary"]

    assert summary["overall_status"] == "method_selection_alpha_expansion_plan_ready"
    assert summary["dominant_alpha"] == "0.1"
    assert summary["current_common_alpha_distribution"] == {"0.1": 4, "0.2": 1}
    assert summary["additional_common_cells_needed_to_clear_threshold"] == 1
    assert summary["next_batch_dataset_alpha_task_count"] == 1
    assert summary["next_batch_method_run_task_count"] == 3
    assert summary["planned_common_cell_gain"] == 1
    assert (
        summary["projected_common_alpha_imbalance_status_after_next_batch"]
        == "no_large_alpha_concentration"
    )
    task = payload["next_batch_dataset_alpha_tasks"][0]
    assert task["dataset_id"] == "d1"
    assert task["target_alpha"] == "0.01"
    assert task["missing_candidate_methods"] == ["cqr", "cv_plus", "mondrian_abs"]
    assert task["source_configs"][0]["config_id"] == "config:d1_alpha_source"
    assert summary["can_support_final_method_selection"] is False
    assert summary["final_selection_claim_status"] == "blocked"


def test_alpha_expansion_plan_fails_without_source_config_traceability(tmp_path):
    sources = write_sources(tmp_path, with_config=False)

    payload = plan.build_payload(tmp_path, *sources)

    assert payload["summary"]["overall_status"] == "method_selection_alpha_expansion_plan_failed"
    failed_ids = {row["check_id"] for row in payload["failed_checks"]}
    assert "planned_gain_sufficient_for_threshold" in failed_ids
    assert "source_config_traceability_present" in failed_ids
