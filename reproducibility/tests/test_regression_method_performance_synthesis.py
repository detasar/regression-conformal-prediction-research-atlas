import json
from pathlib import Path

from experiments.regression.scripts import build_method_performance_synthesis as synth


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def completed_row(
    run_id: str,
    *,
    dataset_id: str,
    cp_method: str,
    coverage: float,
    alpha: float = 0.1,
    interval_score: float = 1.0,
    mean_width: float = 1.0,
    seed: int = 1,
) -> dict:
    return {
        "run_id": run_id,
        "status": "completed",
        "dataset_id": dataset_id,
        "model_family": "linear",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "cp_method": cp_method,
        "cp_method_params": {},
        "alpha": alpha,
        "seed": seed,
        "coverage": coverage,
        "mean_width": mean_width,
        "interval_score": interval_score,
    }


def test_method_performance_synthesis_uses_publication_ledgers_and_keeps_no_selection_claim(
    tmp_path,
):
    ledger_a = tmp_path / "experiments/regression/results/a/ledger.jsonl"
    ledger_b = tmp_path / "experiments/regression/results/b/ledger.jsonl"
    report_a = tmp_path / "experiments/regression/reports/a/pilot_summary.json"
    report_b = tmp_path / "experiments/regression/reports/b/pilot_summary.json"
    cross_run = (
        tmp_path
        / "experiments/regression/reports/methodology_sanity_audit_20260627/cross_run_integrity_audit.json"
    )

    write_jsonl(
        ledger_a,
        [
            completed_row(
                "a-cqr",
                dataset_id="toy_a",
                cp_method="cqr",
                coverage=0.92,
                interval_score=2.0,
                seed=1,
            ),
            {
                **completed_row(
                    "a-cqr",
                    dataset_id="toy_a",
                    cp_method="cqr",
                    coverage=0.80,
                    interval_score=9.0,
                    seed=1,
                ),
                "status": "skipped_completed",
            },
            completed_row(
                "a-split",
                dataset_id="toy_a",
                cp_method="split_abs",
                coverage=0.89,
                interval_score=1.0,
                seed=1,
            ),
        ],
    )
    write_jsonl(
        ledger_b,
        [
            completed_row(
                "b-cqr",
                dataset_id="toy_b",
                cp_method="cqr",
                coverage=0.91,
                interval_score=3.0,
                seed=2,
            ),
            completed_row(
                "b-split",
                dataset_id="toy_b",
                cp_method="split_abs",
                coverage=0.95,
                interval_score=6.0,
                seed=2,
            ),
        ],
    )
    write_json(
        report_a,
        {
            "ledger": str(ledger_a.relative_to(tmp_path)),
            "metadata": {"status_counts": {"completed": 2}},
        },
    )
    write_json(
        report_b,
        {
            "ledger": str(ledger_b.relative_to(tmp_path)),
            "metadata": {"status_counts": {"completed": 2}},
        },
    )
    write_json(
        cross_run,
        {
            "summary": {"total_completed_rows": 4, "reports_scanned": 2},
            "rows": [
                {
                    "report_id": "report:a",
                    "report_name": "a",
                    "pilot_summary_path": str(report_a.relative_to(tmp_path)),
                },
                {
                    "report_id": "report:b",
                    "report_name": "b",
                    "pilot_summary_path": str(report_b.relative_to(tmp_path)),
                },
            ],
        },
    )

    payload = synth.build_payload(tmp_path, cross_run)
    by_method = {row["cp_method"]: row for row in payload["method_rows"]}

    assert payload["summary"]["overall_status"] == (
        "method_performance_synthesis_descriptive_no_final_selection"
    )
    assert payload["summary"]["completed_ledger_rows"] == 4
    assert payload["summary"]["source_report_count"] == 2
    assert payload["summary"]["method_count"] == 2
    assert payload["summary"]["can_support_final_method_selection"] is False
    assert payload["summary"]["claim_status"] == "descriptive_no_final_selection"
    assert payload["failed_checks"] == []

    assert by_method["cqr"]["row_count"] == 2
    assert by_method["cqr"]["dataset_count"] == 2
    assert by_method["cqr"]["row_weighted_nominal_hit_rate"] == 1.0
    assert by_method["cqr"]["frontier_cell_count"] == 2
    assert by_method["split_abs"]["row_count"] == 2
    assert by_method["split_abs"]["row_weighted_nominal_hit_rate"] == 0.5
    assert by_method["split_abs"]["frontier_cell_count"] == 0


def test_method_performance_synthesis_fails_without_completed_rows(tmp_path):
    cross_run = tmp_path / "cross_run.json"
    write_json(cross_run, {"summary": {}, "rows": []})

    payload = synth.build_payload(tmp_path, cross_run)

    assert payload["summary"]["overall_status"] == "method_performance_synthesis_failed"
    failed_ids = {row["check_id"] for row in payload["failed_checks"]}
    assert "completed_rows_present" in failed_ids
    assert "no_final_selection_claim" not in failed_ids
