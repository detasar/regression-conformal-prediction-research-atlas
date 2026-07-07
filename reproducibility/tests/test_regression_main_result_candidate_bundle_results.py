import json
from pathlib import Path

from experiments.regression.scripts import (
    build_main_result_candidate_bundle_results as results,
)


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def base_row(method: str, *, run_id: str, coverage: float, width: float) -> dict:
    return {
        "run_id": run_id,
        "status": "completed",
        "dataset_id": "demo",
        "seed": 401,
        "alpha": 0.1,
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "cp_method": method,
        "coverage": coverage,
        "interval_score": width + abs(coverage - 0.9) * 100.0,
        "mean_width": width,
        "median_width": width,
        "normalized_mean_width": width / 10.0,
        "coverage_gap": 0.05,
        "width_gap": 2.0,
        "lower_miss_rate": 0.05,
        "upper_miss_rate": 0.05,
        "cp_metadata": {
            "method": method,
            "target_inverse_transform": {
                "lower": {"inverse_saturation_count": 0},
                "upper": {"inverse_saturation_count": 0},
            },
        },
    }


def test_candidate_bundle_results_summarizes_completed_rows(tmp_path):
    plan_path = tmp_path / results.DEFAULT_PLAN
    ledger = tmp_path / "experiments/regression/results/demo/ledger.jsonl"
    write_json(
        plan_path,
        {
            "summary": {"candidate_methods": ["cqr", "cv_plus", "mondrian_abs"]},
            "candidate_rows": [
                {
                    "dataset_id": "demo",
                    "config_path": "experiments/regression/configs/demo.yaml",
                    "ledger": str(ledger.relative_to(tmp_path)),
                    "expected_atomic_run_count": 3,
                    "cp_methods": ["cqr", "cv_plus", "mondrian_abs"],
                    "primary_candidate_method": "cqr",
                    "promotion_priority": "candidate_primary_consistent",
                }
            ],
        },
    )
    cqr = base_row("cqr", run_id="r1", coverage=0.9, width=10.0)
    cqr["cp_metadata"]["quantile_crossings_test"] = 1
    cv_plus = base_row("cv_plus", run_id="r2", coverage=0.88, width=15.0)
    mondrian = base_row("mondrian_abs", run_id="r3", coverage=0.91, width=20.0)
    mondrian["cp_metadata"]["fallback_groups"] = ["small_group"]
    append_jsonl(ledger, [cqr, cv_plus, mondrian])

    payload = results.build_payload(tmp_path, plan_path=plan_path)

    assert (
        payload["summary"]["overall_status"]
        == "main_result_candidate_bundle_results_completed_no_promotions"
    )
    assert payload["summary"]["completed_atomic_run_count"] == 3
    assert payload["summary"]["can_support_main_result_promotion"] is False
    assert payload["summary"]["diagnostic_winner_counts"] == {"cqr": 1}
    assert (
        payload["summary"]["pathology_flag_counts"]["cqr_quantile_crossings_test"]
        == 1
    )
    assert (
        payload["summary"]["pathology_flag_counts"]["mondrian_fallback_groups"] == 1
    )
    assert payload["failed_checks"] == []


def test_checked_in_candidate_bundle_results_remain_no_promotion():
    path = ROOT / results.DEFAULT_OUT
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert (
        payload["summary"]["overall_status"]
        == "main_result_candidate_bundle_results_completed_no_promotions"
    )
    assert payload["summary"]["candidate_dataset_count"] == 6
    assert payload["summary"]["completed_atomic_run_count"] == 270
    assert payload["summary"]["expected_atomic_run_count"] == 270
    assert payload["summary"]["can_support_main_result_promotion"] is False
    assert payload["summary"]["failed_check_count"] == 0
    assert set(payload["summary"]["candidate_methods"]) == {
        "cqr",
        "cv_plus",
        "mondrian_abs",
    }
