import json
from pathlib import Path

from experiments.regression.scripts import audit_experiment_accounting as audit


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_source_accounting(
    root: Path,
    *,
    cross_completed: int = 2,
    publication_completed: int = 2,
    selection_completed: int = 2,
) -> None:
    report_dir = (
        root / "experiments/regression/reports/methodology_sanity_audit_20260627"
    )
    write_json(
        report_dir / "cross_run_integrity_audit.json",
        {"summary": {"total_completed_rows": cross_completed, "reports_scanned": 1}},
    )
    write_json(
        report_dir / "publication_methodology_audit.json",
        {"summary": {"total_completed_rows": publication_completed}},
    )
    write_json(
        root / "experiments/regression/manuscript/selection_multiplicity_protocol.json",
        {"summary": {"completed_ledger_rows_scanned": selection_completed}},
    )
    write_json(
        root
        / "experiments/regression/manuscript/bounded_support_posthandling_validation.json",
        {
            "summary": {
                "completed_ledger_rows": 1,
                "state_resumed_records": 1,
                "state_written_records": 0,
                "reconstruction_failures": 0,
            }
        },
    )
    write_json(
        report_dir / "venn_abers_grid_expansion_plan.json",
        {
            "summary": {
                "total_test_rows_available": 3,
                "total_grid_rows_completed": 3,
                "total_grid_rows_pending": 0,
                "worker_grid_rows_completed": 2,
                "worker_grid_rows_failed": 1,
                "grid_completion_fraction": 1.0,
            }
        },
    )
    write_json(
        report_dir / "venn_abers_grid_ivapd_validation_protocol.json",
        {
            "summary": {
                "total_grid_reference_rows_scored": 3,
                "total_ivapd_rows_scored": 1,
            }
        },
    )


def test_experiment_accounting_separates_raw_canonical_and_claim_scopes(tmp_path):
    common = {
        "dataset_id": "toy",
        "model_id": "ridge",
        "model_family": "linear",
        "model_params": {"alpha": 1.0},
        "seed": 1,
        "cp_method": "split_abs",
        "cp_method_params": {},
        "alpha": 0.1,
    }
    write_jsonl(
        tmp_path / "experiments/regression/results/demo/ledger.jsonl",
        [
            {**common, "run_id": "a", "status": "completed"},
            {**common, "run_id": "a", "status": "skipped_completed"},
            {**common, "run_id": "b", "status": "completed", "seed": 2},
        ],
    )
    write_jsonl(
        tmp_path / "experiments/regression/results/invalidated/demo/ledger.jsonl",
        [{**common, "run_id": "invalid", "status": "completed", "seed": 3}],
    )
    write_jsonl(
        tmp_path / "experiments/regression/results/demo_aborted_reason/ledger.jsonl",
        [{**common, "run_id": "failed", "status": "failed", "seed": 4}],
    )
    write_source_accounting(tmp_path)

    payload = audit.build_audit(tmp_path)
    summary = payload["summary"]

    assert summary["overall_status"] == "experiment_accounting_pass"
    assert summary["ledger_file_count"] == 3
    assert summary["raw_ledger_row_count"] == 5
    assert summary["canonical_ledger_row_count"] == 4
    assert summary["raw_completed_row_count"] == 3
    assert summary["canonical_completed_row_count"] == 3
    assert summary["canonical_failed_row_count"] == 1
    assert summary["regular_canonical_completed_row_count"] == 2
    assert summary["cross_run_completed_rows"] == 2
    assert summary["invalidated_canonical_completed_row_count"] == 1
    assert summary["aborted_canonical_completed_row_count"] == 0
    assert summary["regular_completed_minus_cross_run_completed_rows"] == 0
    assert summary["bounded_support_selected_completed_rows"] == 1
    assert summary["venn_grid_rows_completed"] == 3
    assert summary["venn_grid_rows_pending"] == 0
    assert payload["failed_checks"] == []


def test_experiment_accounting_fails_when_publication_counts_diverge(tmp_path):
    write_jsonl(
        tmp_path / "experiments/regression/results/demo/ledger.jsonl",
        [
            {
                "run_id": "a",
                "status": "completed",
                "dataset_id": "toy",
                "model_id": "ridge",
                "seed": 1,
                "cp_method": "split_abs",
                "alpha": 0.1,
            }
        ],
    )
    write_source_accounting(
        tmp_path,
        cross_completed=1,
        publication_completed=2,
        selection_completed=1,
    )

    payload = audit.build_audit(tmp_path)
    failed_ids = {row["check_id"] for row in payload["failed_checks"]}

    assert payload["summary"]["overall_status"] == "experiment_accounting_fail"
    assert "cross_publication_selection_completed_rows_align" in failed_ids


def test_experiment_accounting_counts_new_bounded_support_state_writes(tmp_path):
    write_jsonl(
        tmp_path / "experiments/regression/results/demo/ledger.jsonl",
        [
            {
                "run_id": "a",
                "status": "completed",
                "dataset_id": "toy",
                "model_id": "ridge",
                "seed": 1,
                "cp_method": "split_abs",
                "alpha": 0.1,
            },
            {
                "run_id": "b",
                "status": "completed",
                "dataset_id": "toy",
                "model_id": "ridge",
                "seed": 2,
                "cp_method": "split_abs",
                "alpha": 0.1,
            },
        ],
    )
    write_source_accounting(tmp_path, cross_completed=2, publication_completed=2, selection_completed=2)
    write_json(
        tmp_path
        / "experiments/regression/manuscript/bounded_support_posthandling_validation.json",
        {
            "summary": {
                "completed_ledger_rows": 2,
                "state_resumed_records": 1,
                "state_written_records": 1,
                "reconstruction_failures": 0,
            }
        },
    )

    payload = audit.build_audit(tmp_path)
    failed_ids = {row["check_id"] for row in payload["failed_checks"]}

    assert "bounded_support_state_matches_selected_rows" not in failed_ids
    assert payload["summary"]["bounded_support_state_resumed_records"] == 1
    assert payload["summary"]["bounded_support_state_written_records"] == 1
