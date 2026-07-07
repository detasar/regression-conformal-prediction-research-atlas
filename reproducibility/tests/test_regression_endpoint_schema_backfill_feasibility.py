import json
from pathlib import Path

from experiments.regression.scripts import audit_endpoint_schema_backfill_feasibility as audit


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"run_id": "r1", "status": "completed", "cp_method": "split_abs"},
        {"run_id": "r2", "status": "completed", "cp_method": "cqr"},
        {"run_id": "r3", "status": "skipped_method", "cp_method": "cv_plus"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def write_config(path: Path, ledger: Path, prediction_root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "experiment_id: toy_v0",
                "logging:",
                f"  ledger: {ledger}",
                f"  prediction_cache_root: {prediction_root}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def backlog_payload(report_name: str, config_path: Path, dataset_id: str) -> dict:
    return {
        "schema": "cpfi_integrity_remediation_backlog_v1",
        "rows": [
            {
                "action_id": f"{report_name}:caveat:legacy_endpoint_schema_not_full_closure",
                "action_category": "endpoint_schema_upgrade",
                "issue_type": "legacy_endpoint_schema_not_full_closure",
                "status": "open",
                "report_id": f"report:{report_name}",
                "report_name": report_name,
                "config_path": str(config_path),
                "dataset_ids": [dataset_id],
                "source_sidecar_paths": [
                    f"experiments/regression/reports/{report_name}/endpoint_audit.json"
                ],
            }
        ],
    }


def build_ready_tree(tmp_path: Path, *, endpoint_payload: dict, dataset_id: str = "toy") -> Path:
    report_name = "toy_report"
    root = tmp_path
    ledger = root / "experiments/regression/results/toy/ledger.jsonl"
    prediction_root = root / "experiments/regression/results/toy/checkpoints/predictions"
    prediction_root.mkdir(parents=True)
    write_ledger(ledger)
    config = root / "experiments/regression/configs/toy.yaml"
    write_config(config, ledger, prediction_root)
    write_json(
        root / "experiments/regression/reports/toy_report/endpoint_audit.json",
        endpoint_payload,
    )
    write_json(
        root / "experiments/regression/reports/methodology_sanity_audit_20260627/backlog.json",
        backlog_payload(report_name, config, dataset_id),
    )
    return root / "experiments/regression/reports/methodology_sanity_audit_20260627/backlog.json"


def test_endpoint_feasibility_keeps_zero_observed_min(tmp_path):
    backlog_path = build_ready_tree(
        tmp_path,
        endpoint_payload={
            "audit_schema": "legacy_v1",
            "observed_target_bounds": {"min": 0.0, "max": 10.0},
        },
    )

    payload = audit.build_payload(tmp_path, backlog_path, tmp_path / "out.json")

    row = payload["rows"][0]
    assert row["status"] == "ready_for_v2_reconstruction"
    assert row["observed_target_min"] == 0.0
    assert row["observed_target_max"] == 10.0
    assert row["observed_bounds_source"] == "endpoint_observed_target_bounds"
    assert row["completed_ledger_rows"] == 2
    assert row["completed_method_counts"] == {"cqr": 1, "split_abs": 1}
    assert row["expensive_full_reconstruction_methods"] == ["cqr"]
    assert "--observed-min 0.0" in row["estimated_command"]


def test_endpoint_feasibility_uses_dataset_audit_bounds(tmp_path):
    backlog_path = build_ready_tree(
        tmp_path,
        endpoint_payload={"audit_schema": "legacy_v1"},
        dataset_id="audited_dataset",
    )
    write_json(
        tmp_path / "experiments/regression/audits/audited_dataset/audit.json",
        {"target_min": 12.5, "target_max": 17.5},
    )

    payload = audit.build_payload(tmp_path, backlog_path, tmp_path / "out.json")

    row = payload["rows"][0]
    assert row["status"] == "ready_for_v2_reconstruction"
    assert row["observed_bounds_source"] == "dataset_audit_target_bounds"
    assert row["observed_bounds_source_paths"] == [
        "experiments/regression/audits/audited_dataset/audit.json"
    ]
    assert row["observed_target_min"] == 12.5
    assert row["observed_target_max"] == 17.5


def test_endpoint_feasibility_blocks_missing_bounds(tmp_path):
    backlog_path = build_ready_tree(
        tmp_path,
        endpoint_payload={"audit_schema": "legacy_v1"},
        dataset_id="missing_audit",
    )

    payload = audit.build_payload(tmp_path, backlog_path, tmp_path / "out.json")

    row = payload["rows"][0]
    assert row["status"] == "blocked_missing_inputs"
    assert "missing_observed_target_bounds" in row["blockers"]
    assert payload["summary"]["blocked_count"] == 1


def test_rel_accepts_external_probe_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_path = repo_root / "experiments/regression/reports/endpoint.json"
    external_path = tmp_path / "scratch/endpoint.json"

    assert audit.rel(repo_path, repo_root) == "experiments/regression/reports/endpoint.json"
    assert audit.rel(external_path, repo_root) == str(external_path.resolve())
