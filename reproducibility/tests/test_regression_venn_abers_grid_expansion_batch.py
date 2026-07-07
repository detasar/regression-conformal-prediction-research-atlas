import json
from pathlib import Path

import numpy as np

from experiments.regression.scripts import run_venn_abers_grid_expansion_batch as batch
from experiments.regression.scripts.run_regression_pilot import PredictionBundle


def tiny_bundle(tmp_path):
    return PredictionBundle(
        artifact_id="artifact_a",
        artifact_dir=tmp_path / "predictions" / "ar" / "artifact_a",
        cache_status="hit",
        fit_seconds=0.0,
        y_train=np.array([0.0, 1.0, 2.0, 3.0]),
        y_cal=np.array([0.0, 1.0, 2.0, 3.0]),
        y_test=np.array([0.5, 1.5, 2.5]),
        yhat_train=np.array([0.1, 0.9, 2.1, 2.9]),
        yhat_cal=np.array([0.1, 0.9, 2.1, 2.9]),
        yhat_test=np.array([0.4, 1.4, 2.4]),
        groups_cal=np.array(["a", "a", "b", "b"]),
        groups_test=np.array(["a", "b", "b"]),
        split_groups_train=None,
        X_train=np.zeros((4, 0)),
        X_cal=np.zeros((4, 0)),
        X_test=np.zeros((3, 0)),
        scale_cal=np.ones(4),
        scale_test=np.ones(3),
        target_transform="identity",
    )


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def source_task():
    return {
        "task_id": "report:venn_abers_real_data_diagnostic:run_a:venn_abers_quantile_grid_reference",
        "report_id": "report:venn_abers_real_data_diagnostic",
        "role": "real_data",
        "report_path": "experiments/regression/reports/venn_abers_real_data_diagnostic/diagnostic.json",
        "run_id": "run_a",
        "dataset_id": "toy_regression",
        "model_id": "ridge",
        "model_family": "linear",
        "seed": 7,
        "alpha": 0.2,
        "prediction_artifact": "artifact_a",
        "prediction_cache_status": "hit",
        "test_rows_available": 3,
        "completed_row_count": 1,
        "completed_row_indices": [0],
        "pending_row_count": 2,
        "next_batch_row_count": 2,
        "next_batch_row_indices": [1, 2],
        "status": "pending",
    }


def test_row_key_includes_grid_hash_and_artifact():
    base = {
        "report_id": "report:a",
        "run_id": "run",
        "test_index": 3,
        "score_grid_size": 4,
        "score_grid_sha256": "abc",
        "prediction_artifact": "artifact_a",
    }

    assert batch.row_key(**base) == batch.row_key(**base)
    assert batch.row_key(**base) != batch.row_key(
        **{**base, "prediction_artifact": "artifact_b"}
    )
    assert batch.row_key(**base) != batch.row_key(**{**base, "score_grid_sha256": "def"})


def test_plan_work_items_skips_completed_state_rows(tmp_path):
    task = source_task()
    source_report = {
        "results": [
            {
                "run_id": "run_a",
                "venn_abers_quantile_grid_reference": {
                    "grid_metadata": {"score_grid": [0.0, 0.2, 0.4, 0.8]}
                },
            }
        ]
    }
    write_json(tmp_path / task["report_path"], source_report)
    grid_hash = batch.score_grid_hash([0.0, 0.2, 0.4, 0.8])
    existing_key = batch.row_key(
        report_id=task["report_id"],
        run_id=task["run_id"],
        test_index=1,
        score_grid_size=4,
        score_grid_sha256=grid_hash,
        prediction_artifact=task["prediction_artifact"],
    )

    work_items, skipped = batch.plan_work_items(
        {"tasks": [task]},
        root=tmp_path,
        state_rows=[
            {"schema": batch.ROW_SCHEMA, "status": "completed", "row_key": existing_key}
        ],
        max_row_tasks=10,
    )

    assert skipped["skipped_existing"] == 1
    assert [item["test_index"] for item in work_items] == [2]


def test_score_group_records_grid_and_fallback_fields(tmp_path, monkeypatch):
    task = source_task()
    item = {
        "task": task,
        "source_result": {},
        "source_report_path": tmp_path / task["report_path"],
        "score_grid": [0.0, 0.2, 0.4, 0.8],
        "score_grid_sha256": batch.score_grid_hash([0.0, 0.2, 0.4, 0.8]),
        "test_index": 1,
        "row_key": "row_1",
    }
    config_path = tmp_path / "config.yaml"

    monkeypatch.setattr(
        batch,
        "load_prediction_bundle_for_task",
        lambda root, task, source_result: (
            tiny_bundle(tmp_path),
            config_path,
            {"mode": "test_bundle_loader"},
        ),
    )

    rows = batch.score_group(tmp_path, [item])

    assert len(rows) == 1
    row = rows[0]
    assert row["schema"] == batch.ROW_SCHEMA
    assert row["status"] == "completed"
    assert row["row_key"] == "row_1"
    assert row["test_index"] == 1
    assert row["source_score_grid"]["size"] == 4
    assert row["prediction_bundle_loader"]["mode"] == "test_bundle_loader"
    assert row["target_transform"] == "identity"
    assert row["grid_radius"] >= 0.0
    assert "split_fallback_radius" in row
    assert row["claim_boundary"].startswith("Row-level expansion evidence only")


def test_run_batch_writes_resume_summary(tmp_path, monkeypatch):
    task = source_task()
    plan_path = tmp_path / "plan.json"
    state_path = tmp_path / "state.jsonl"
    out_path = tmp_path / "batch.json"
    source_report = {
        "results": [
            {
                "run_id": "run_a",
                "venn_abers_quantile_grid_reference": {
                    "grid_metadata": {"score_grid": [0.0, 0.2, 0.4, 0.8]}
                },
            }
        ]
    }
    write_json(plan_path, {"tasks": [task]})
    write_json(tmp_path / task["report_path"], source_report)
    monkeypatch.setattr(
        batch,
        "load_prediction_bundle_for_task",
        lambda root, task, source_result: (
            tiny_bundle(tmp_path),
            tmp_path / "config.yaml",
            {"mode": "test_bundle_loader"},
        ),
    )

    first = batch.run_batch(
        root=tmp_path,
        plan_path=plan_path,
        state_path=state_path,
        out_path=out_path,
        max_row_tasks=1,
    )
    second = batch.run_batch(
        root=tmp_path,
        plan_path=plan_path,
        state_path=state_path,
        out_path=out_path,
        max_row_tasks=10,
    )

    assert first["summary"]["completed_new_row_tasks"] == 1
    assert second["summary"]["skipped_existing_completed_rows"] == 1
    assert second["summary"]["completed_new_row_tasks"] == 1
    assert second["summary"]["after_unique_completed_row_count"] == 2
    assert out_path.exists()
    assert out_path.with_suffix(".md").exists()
