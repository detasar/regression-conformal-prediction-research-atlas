import json

from experiments.regression.scripts import build_venn_abers_grid_expansion_plan as plan


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_sources(root):
    write_json(
        root / "experiments/regression/reports/venn_abers_real_data_diagnostic/diagnostic.json",
        {
            "results": [
                {
                    "run_id": "real_a",
                    "dataset_id": "toy_real",
                    "model_id": "ridge",
                    "model_family": "linear",
                    "seed": 1,
                    "alpha": 0.1,
                    "prediction_artifact": "reports/real_a/predictions.json",
                    "prediction_cache_status": "hit",
                    "venn_abers_quantile_grid_reference": {
                        "test_rows_available": 5,
                        "selected_test_indices": [0, 2],
                    },
                },
                {
                    "run_id": "real_b",
                    "dataset_id": "toy_real",
                    "model_id": "hist_gradient_boosting",
                    "model_family": "tree",
                    "seed": 1,
                    "alpha": 0.1,
                    "venn_abers_quantile_grid_reference": {
                        "test_rows_available": 0,
                        "selected_test_indices": [],
                    },
                },
            ]
        },
    )
    write_json(
        root / "experiments/regression/reports/venn_abers_fairness_panel_diagnostic/diagnostic.json",
        {
            "results": [
                {
                    "run_id": "fair_a",
                    "dataset_id": "toy_fair",
                    "model_id": "ridge",
                    "model_family": "linear",
                    "seed": 2,
                    "alpha": 0.1,
                    "venn_abers_quantile_grid_reference": {
                        "test_rows_available": 3,
                        "selected_test_indices": [1],
                    },
                }
            ]
        },
    )
    write_json(
        root
        / "experiments/regression/reports/venn_abers_biomarker_clinical_panel_diagnostic/diagnostic.json",
        {
            "results": [
                {
                    "run_id": "bio_a",
                    "dataset_id": "toy_bio",
                    "model_id": "elasticnet",
                    "model_family": "linear",
                    "seed": 3,
                    "alpha": 0.1,
                    "venn_abers_quantile_grid_reference": {
                        "test_rows_available": 2,
                        "selected_test_indices": [0, 1],
                    },
                }
            ]
        },
    )


def test_grid_expansion_plan_builds_resumable_row_queue(tmp_path):
    write_sources(tmp_path)

    payload = plan.build_payload(tmp_path, next_batch_size=2)
    tasks = {row["run_id"]: row for row in payload["tasks"]}

    assert payload["summary"]["overall_status"] == "venn_abers_grid_expansion_plan_ready"
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["run_task_count"] == 4
    assert payload["summary"]["total_test_rows_available"] == 10
    assert payload["summary"]["total_grid_rows_completed"] == 5
    assert payload["summary"]["total_grid_rows_pending"] == 5
    assert payload["summary"]["next_batch_total_rows"] == 4
    assert payload["summary"]["duplicate_next_batch_task_key_count"] == 0

    assert tasks["real_a"]["pending_row_ranges"] == [
        {"start": 1, "end": 1, "count": 1},
        {"start": 3, "end": 4, "count": 2},
    ]
    assert tasks["real_a"]["next_batch_row_indices"] == [1, 4]
    assert tasks["fair_a"]["next_batch_row_indices"] == [0, 2]
    assert tasks["bio_a"]["status"] == "complete"
    assert "test_index" in tasks["real_a"]["resume_key_fields"]


def test_grid_expansion_plan_classifies_retained_failed_rows(tmp_path):
    write_sources(tmp_path)
    state_path = (
        tmp_path
        / "experiments/regression/results/venn_abers_grid_expansion/checkpoints/row_results.jsonl"
    )
    write_jsonl(
        state_path,
        [
            {
                "schema": plan.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": "fair_a_0_completed",
                "report_id": "report:venn_abers_fairness_panel_diagnostic",
                "run_id": "fair_a",
                "test_index": 0,
            },
            {
                "schema": plan.WORKER_ROW_SCHEMA,
                "status": "failed",
                "row_key": "fair_a_0_failed",
                "report_id": "report:venn_abers_fairness_panel_diagnostic",
                "run_id": "fair_a",
                "test_index": 0,
            },
            {
                "schema": plan.WORKER_ROW_SCHEMA,
                "status": "failed",
                "row_key": "real_a_3_failed",
                "report_id": "report:venn_abers_real_data_diagnostic",
                "run_id": "real_a",
                "test_index": 3,
            },
        ],
    )

    payload = plan.build_payload(tmp_path, next_batch_size=2, state_path=state_path)
    tasks = {row["run_id"]: row for row in payload["tasks"]}

    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["worker_failed_task_key_count"] == 2
    assert payload["summary"]["worker_superseded_failed_task_key_count"] == 1
    assert payload["summary"]["worker_pending_failed_task_key_count"] == 1
    assert payload["summary"]["worker_orphan_failed_task_key_count"] == 0
    assert payload["summary"]["failed_worker_rows_all_superseded_or_pending"] is True
    assert tasks["fair_a"]["worker_superseded_failed_row_count"] == 1
    assert tasks["real_a"]["worker_pending_failed_row_count"] == 1


def test_grid_expansion_plan_accepts_complete_queue(tmp_path):
    write_sources(tmp_path)
    state_path = (
        tmp_path
        / "experiments/regression/results/venn_abers_grid_expansion/checkpoints/row_results.jsonl"
    )
    write_jsonl(
        state_path,
        [
            {
                "schema": plan.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": f"real_a_{idx}",
                "report_id": "report:venn_abers_real_data_diagnostic",
                "run_id": "real_a",
                "test_index": idx,
            }
            for idx in [1, 3, 4]
        ]
        + [
            {
                "schema": plan.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": f"fair_a_{idx}",
                "report_id": "report:venn_abers_fairness_panel_diagnostic",
                "run_id": "fair_a",
                "test_index": idx,
            }
            for idx in [0, 2]
        ],
    )

    payload = plan.build_payload(tmp_path, next_batch_size=2, state_path=state_path)

    assert payload["summary"]["overall_status"] == "venn_abers_grid_expansion_plan_complete"
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["total_test_rows_available"] == 10
    assert payload["summary"]["total_grid_rows_completed"] == 10
    assert payload["summary"]["total_grid_rows_pending"] == 0
    assert payload["summary"]["next_batch_total_rows"] == 0
    assert payload["summary"]["duplicate_next_batch_task_key_count"] == 0


def test_grid_expansion_markdown_preserves_claim_boundary(tmp_path):
    write_sources(tmp_path)

    markdown = plan.render_markdown(plan.build_payload(tmp_path, next_batch_size=2))

    assert "# Venn-Abers Grid Expansion Plan" in markdown
    assert "not empirical validation evidence" in markdown
    assert "toy_fair" in markdown
