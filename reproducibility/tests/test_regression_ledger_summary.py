import pandas as pd

from experiments.regression.scripts.summarize_regression_results import (
    candidate_frontier_rows,
    canonical_model_params,
    canonical_ledger,
    render_markdown,
    summarize,
    summarize_ledger_metadata,
    summary_payload,
)


def test_ledger_summary_prefers_completed_records_over_resume_skips():
    df = pd.DataFrame(
        [
            {
                "run_id": "abc",
                "status": "completed",
                "dataset_id": "dataset_a",
                "model_id": "ridge",
                "cp_method": "split_abs",
                "alpha": 0.1,
                "coverage": 0.9,
                "coverage_gap": 0.02,
                "mean_width": 1.0,
                "interval_score": 1.2,
            },
            {"run_id": "abc", "status": "skipped_completed"},
        ]
    )

    canonical = canonical_ledger(df)
    metadata = summarize_ledger_metadata(df)
    summary = summarize(df)

    assert len(canonical) == 1
    assert canonical.iloc[0]["status"] == "completed"
    assert metadata["ledger_rows"] == 2
    assert metadata["unique_run_rows"] == 1
    assert metadata["status_counts"] == {"completed": 1}
    assert metadata["raw_status_counts"] == {"completed": 1, "skipped_completed": 1}
    assert summary.iloc[0]["coverage_count"] == 1
    assert summary.iloc[0]["coverage_error_abs_mean"] == 0.0


def test_ledger_summary_supersedes_schema_refresh_with_new_run_id():
    common = {
        "status": "completed",
        "dataset_id": "dataset_a",
        "model_family": "linear",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "seed": 42,
        "cp_method": "split_abs",
        "alpha": 0.1,
        "coverage_gap": 0.02,
        "mean_width": 1.0,
        "interval_score": 1.2,
    }
    df = pd.DataFrame(
        [
            {**common, "run_id": "legacy-schema", "coverage": 0.8},
            {
                **common,
                "run_id": "schema-v4",
                "cp_method_params": {},
                "coverage": 0.9,
            },
        ]
    )

    canonical = canonical_ledger(df)
    metadata = summarize_ledger_metadata(df)
    summary = summarize(df)

    assert len(canonical) == 1
    assert canonical.iloc[0]["run_id"] == "schema-v4"
    assert metadata["ledger_rows"] == 2
    assert metadata["unique_run_rows"] == 1
    assert metadata["status_counts"] == {"completed": 1}
    assert metadata["raw_status_counts"] == {"completed": 2}
    assert summary.iloc[0]["coverage_count"] == 1
    assert summary.iloc[0]["coverage_mean"] == 0.9


def test_ledger_metadata_counts_failed_runs_canonically():
    df = pd.DataFrame(
        [
            {"run_id": "abc", "status": "failed", "dataset_id": "dataset_a"},
            {"run_id": "def", "status": "skipped_method", "dataset_id": "dataset_a"},
        ]
    )

    metadata = summarize_ledger_metadata(df)

    assert metadata["status_counts"] == {"failed": 1, "skipped_method": 1}
    assert metadata["dataset_counts"] == {"dataset_a": 2}


def test_summary_keeps_model_hyperparameters_separate():
    df = pd.DataFrame(
        [
            {
                "run_id": "ridge-a",
                "status": "completed",
                "dataset_id": "dataset_a",
                "model_id": "ridge",
                "model_params": {"alpha": 0.1},
                "cp_method": "split_abs",
                "alpha": 0.1,
                "coverage": 0.9,
                "coverage_gap": 0.02,
                "mean_width": 1.0,
                "interval_score": 1.2,
            },
            {
                "run_id": "ridge-b",
                "status": "completed",
                "dataset_id": "dataset_a",
                "model_id": "ridge",
                "model_params": {"alpha": 10.0},
                "cp_method": "split_abs",
                "alpha": 0.1,
                "coverage": 0.8,
                "coverage_gap": 0.10,
                "mean_width": 0.5,
                "interval_score": 3.4,
            },
        ]
    )

    summary = summarize(df)

    assert len(summary) == 2
    assert set(summary["model_params_key"]) == {
        canonical_model_params({"alpha": 0.1}),
        canonical_model_params({"alpha": 10.0}),
    }
    assert summary["coverage_count"].tolist() == [1, 1]


def test_markdown_frontier_is_not_labeled_as_best_rows():
    df = pd.DataFrame(
        [
            {
                "run_id": "abc",
                "status": "completed",
                "dataset_id": "dataset_a",
                "model_id": "ridge",
                "cp_method": "split_abs",
                "alpha": 0.1,
                "coverage": 0.9,
                "coverage_gap": 0.02,
                "mean_width": 1.0,
                "interval_score": 1.2,
            }
        ]
    )

    markdown = render_markdown(df, summarize(df))

    assert "## Candidate Frontier By Dataset And Alpha" in markdown
    assert "They are not method recommendations" in markdown
    assert "Best Rows By Dataset And Alpha" not in markdown


def test_json_payload_frontier_is_not_labeled_as_best_rows(tmp_path):
    df = pd.DataFrame(
        [
            {
                "run_id": "abc",
                "status": "completed",
                "dataset_id": "dataset_a",
                "model_id": "ridge",
                "cp_method": "split_abs",
                "alpha": 0.1,
                "coverage": 0.9,
                "coverage_gap": 0.02,
                "mean_width": 1.0,
                "interval_score": 1.2,
            }
        ]
    )
    summary = summarize(df)
    payload = summary_payload(
        tmp_path / "ledger.jsonl",
        summarize_ledger_metadata(df),
        summary,
        candidate_frontier_rows(summary),
    )

    assert "candidate_frontier_rows" in payload
    assert "candidate_frontier_note" in payload
    assert "best_rows" not in payload
