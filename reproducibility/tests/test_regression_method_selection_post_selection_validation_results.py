import json
from pathlib import Path

from experiments.regression.scripts import (
    build_method_selection_post_selection_validation_results as results,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_ledger(path: Path, dataset_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"status": "completed", "dataset_id": dataset_id, "run_id": f"{dataset_id}_{i}"}
        for i in range(12)
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def summary_row(dataset_id: str, alpha: float, method: str, score: float) -> dict:
    coverage = 1.0 - alpha
    return {
        "dataset_id": dataset_id,
        "model_id": "ridge",
        "model_params_key": '{"alpha":1.0}',
        "cp_method": method,
        "alpha": alpha,
        "coverage_mean": coverage,
        "coverage_error_abs_mean": 0.0,
        "coverage_gap_mean": 0.01,
        "mean_width_mean": score,
        "normalized_mean_width_mean": score,
        "interval_score_mean": score,
        "coverage_count": 3,
    }


def write_report(root: Path, dataset_id: str, winner: str) -> None:
    report_dir = (
        root
        / "experiments/regression/reports"
        / f"method_selection_post_selection_validation_{dataset_id}"
    )
    rows = []
    for alpha in [0.1, 0.2]:
        for method in ["cqr", "cv_plus", "mondrian_abs"]:
            score = 1.0 if method == winner else 10.0
            rows.append(summary_row(dataset_id, alpha, method, score))
    write_json(
        report_dir / "pilot_summary.json",
        {"metadata": {"status_counts": {"completed": 12}}, "rows": rows},
    )
    write_json(
        report_dir / "feature_leakage_audit.json",
        {"violations_count": 0},
    )


def test_post_selection_validation_results_summarize_completed_common_support(tmp_path):
    root = tmp_path
    batch_path = root / "batch.json"
    generated = []
    for dataset_id, winner in [("d1", "cqr"), ("d2", "cv_plus")]:
        ledger = (
            Path("experiments/regression/results")
            / f"method_selection_post_selection_validation_{dataset_id}"
            / "ledger.jsonl"
        )
        write_ledger(root / ledger, dataset_id)
        write_report(root, dataset_id, winner)
        generated.append(
            {
                "dataset_id": dataset_id,
                "ledger": str(ledger),
                "config_path": f"experiments/regression/configs/{dataset_id}.yaml",
                "experiment_id": f"validation_{dataset_id}",
                "expected_atomic_run_count": 12,
            }
        )
    write_json(
        batch_path,
        {
            "summary": {
                "expected_atomic_run_count": 24,
                "candidate_methods": ["cqr", "cv_plus", "mondrian_abs"],
                "target_alphas": ["0.1", "0.2"],
            },
            "generated_configs": generated,
        },
    )

    payload = results.build_payload(root, batch_path)

    assert (
        payload["summary"]["overall_status"]
        == "method_selection_post_selection_validation_results_ready_no_final_selection"
    )
    assert payload["summary"]["completed_atomic_run_count"] == 24
    assert payload["summary"]["feature_leakage_violation_count"] == 0
    assert payload["summary"]["common_dataset_alpha_cell_count"] == 4
    assert payload["summary"]["expected_common_dataset_alpha_cell_count"] == 4
    assert payload["summary"]["diagnostic_winner_counts"] == {
        "cqr": 2,
        "cv_plus": 2,
    }
    assert payload["summary"]["can_support_final_method_selection"] is False
    assert payload["failed_checks"] == []
