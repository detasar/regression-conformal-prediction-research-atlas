import json
from pathlib import Path

from experiments.regression.scripts import backfill_endpoint_method_coverage as backfill


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"run_id": "a", "status": "completed", "cp_method": "split_abs"},
        {"run_id": "b", "status": "completed", "cp_method": "cqr"},
        {"run_id": "c", "status": "skipped_method", "cp_method": "jackknife_plus"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _action() -> dict:
    return {
        "action_id": "toy:caveat:endpoint_audit_not_full_method_coverage",
        "issue_type": "endpoint_audit_not_full_method_coverage",
        "report_id": "report:toy",
        "report_name": "toy",
        "pilot_summary_path": "experiments/regression/reports/toy/pilot_summary.json",
        "source_sidecar_paths": ["experiments/regression/reports/toy/endpoint_audit.json"],
        "status": "open",
    }


def _endpoint_payload(ledger_path: str, reconstructed_runs: int = 2) -> dict:
    return {
        "audit_schema": "cpfi_regression_endpoint_audit_v2",
        "ledger": ledger_path,
        "completed_ledger_rows": reconstructed_runs,
        "reconstructed_runs": reconstructed_runs,
        "missing_artifacts": 0,
        "reconstruction_failures": 0,
        "failure_count_total": 0,
        "observed_target_min": 0.0,
        "observed_target_max": 10.0,
        "lower_floor": 0.0,
        "upper_warning": 20.0,
        "totals": {
            "runs": reconstructed_runs,
            "intervals": 4,
            "nonfinite_lower": 0,
            "nonfinite_upper": 0,
            "crossings": 0,
            "lower_below_floor": 0,
            "lower_below_observed_min": 0,
            "upper_above_observed_max": 0,
            "upper_above_warning": 0,
            "width_above_observed_range": 0,
            "width_above_twice_observed_range": 0,
            "inverse_saturation_lower": 0,
            "inverse_saturation_upper": 0,
            "max_width": 1.0,
            "min_lower": 0.0,
            "max_upper": 1.0,
        },
        "method_summary": {},
        "configured_completed_method_counts": {"cqr": 1, "split_abs": 1},
    }


def test_backfill_updates_existing_v2_when_ledger_counts_match(tmp_path):
    ledger = tmp_path / "experiments/regression/results/toy/ledger.jsonl"
    _write_ledger(ledger)
    endpoint = tmp_path / "experiments/regression/reports/toy/endpoint_audit.json"
    _write_json(
        endpoint,
        _endpoint_payload(
            "experiments/regression/results/toy/ledger.jsonl",
            reconstructed_runs=2,
        ),
    )

    row = backfill.backfill_payload(root=tmp_path, action=_action(), dry_run=False)

    assert row["status"] == "updated"
    payload = json.loads(endpoint.read_text(encoding="utf-8"))
    assert payload["method_filter"]["full_method_coverage"] is True
    assert payload["method_filter"]["metadata_backfilled_from_ledger"] is True
    assert payload["available_completed_method_counts"] == {"cqr": 1, "split_abs": 1}
    assert payload["omitted_completed_method_counts"] == {}
    assert endpoint.with_suffix(".md").exists()


def test_backfill_skips_when_reconstructed_count_mismatches_ledger(tmp_path):
    ledger = tmp_path / "experiments/regression/results/toy/ledger.jsonl"
    _write_ledger(ledger)
    endpoint = tmp_path / "experiments/regression/reports/toy/endpoint_audit.json"
    original = _endpoint_payload(
        "experiments/regression/results/toy/ledger.jsonl",
        reconstructed_runs=1,
    )
    _write_json(endpoint, original)

    row = backfill.backfill_payload(root=tmp_path, action=_action(), dry_run=False)

    assert row["status"] == "skipped_reconstruction_count_mismatch"
    payload = json.loads(endpoint.read_text(encoding="utf-8"))
    assert "method_filter" not in payload


def test_build_summary_counts_updated_rows(tmp_path):
    ledger = tmp_path / "experiments/regression/results/toy/ledger.jsonl"
    _write_ledger(ledger)
    endpoint = tmp_path / "experiments/regression/reports/toy/endpoint_audit.json"
    _write_json(endpoint, _endpoint_payload("experiments/regression/results/toy/ledger.jsonl"))
    backlog = tmp_path / "experiments/regression/reports/methodology/backlog.json"
    _write_json(backlog, {"rows": [_action()]})

    payload = backfill.build_summary(root=tmp_path, backlog_path=backlog, dry_run=True)

    assert payload["action_count"] == 1
    assert payload["updated_count"] == 1
    assert payload["status_counts"] == {"planned": 1}
    assert payload["total_completed_ledger_rows"] == 2


def test_build_summary_preserves_existing_backfilled_rows_after_backlog_closes(tmp_path):
    ledger = tmp_path / "experiments/regression/results/toy/ledger.jsonl"
    _write_ledger(ledger)
    report_dir = tmp_path / "experiments/regression/reports/toy"
    endpoint = report_dir / "endpoint_audit.json"
    payload = _endpoint_payload("experiments/regression/results/toy/ledger.jsonl")
    payload["method_filter"] = {
        "include_methods": [],
        "exclude_methods": [],
        "max_completed": None,
        "full_method_coverage": True,
        "metadata_backfilled_from_ledger": True,
    }
    payload["config"] = "experiments/regression/configs/toy.yaml"
    payload["available_completed_method_counts"] = {"cqr": 1, "split_abs": 1}
    payload["filtered_completed_method_counts"] = {"cqr": 1, "split_abs": 1}
    payload["omitted_completed_method_counts"] = {}
    _write_json(endpoint, payload)
    _write_json(
        report_dir / "pilot_summary.json",
        {"metadata": {"dataset_counts": {"toy_dataset": 2}}, "rows": []},
    )
    backlog = tmp_path / "experiments/regression/reports/methodology/backlog.json"
    _write_json(backlog, {"rows": []})

    summary = backfill.build_summary(root=tmp_path, backlog_path=backlog, dry_run=False)

    assert summary["action_count"] == 0
    assert summary["updated_count"] == 1
    assert summary["status_counts"] == {"existing_backfilled_endpoint_metadata": 1}
    assert summary["rows"][0]["dataset_ids"] == ["toy_dataset"]


def test_rel_accepts_external_probe_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_path = repo_root / "experiments/regression/reports/endpoint_method.json"
    external_path = tmp_path / "scratch/endpoint_method.json"

    assert backfill.rel(repo_path, repo_root) == (
        "experiments/regression/reports/endpoint_method.json"
    )
    assert backfill.rel(external_path, repo_root) == str(external_path.resolve())
