import json
from pathlib import Path

import yaml

from experiments.regression.scripts import (
    backfill_feature_leakage_metadata_completeness_fields as backfill,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _metadata(cache: Path, artifact_id: str, payload: dict) -> None:
    _write_json(cache / artifact_id[:2] / artifact_id / "metadata.json", payload)


def _experiment_paths(tmp_path: Path, report_name: str) -> tuple[Path, Path, Path, Path]:
    cache = (
        tmp_path
        / f"experiments/regression/results/{report_name}/checkpoints/predictions"
    )
    config_path = tmp_path / f"experiments/regression/configs/{report_name}.yaml"
    ledger_path = tmp_path / f"experiments/regression/results/{report_name}/ledger.jsonl"
    report_dir = tmp_path / f"experiments/regression/reports/{report_name}"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "logging": {
                    "ledger": str(ledger_path.relative_to(tmp_path)),
                    "prediction_cache_root": str(cache.relative_to(tmp_path)),
                }
            }
        ),
        encoding="utf-8",
    )
    _write_json(report_dir / "pilot_summary.json", {"ledger": str(ledger_path.relative_to(tmp_path))})
    return cache, config_path, ledger_path, report_dir


def _ledger_row(artifact_id: str) -> dict:
    return {
        "status": "completed",
        "run_id": f"run-{artifact_id}",
        "prediction_artifact": artifact_id,
        "dataset_id": "toy",
        "model_family": "linear",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "seed": 11,
    }


def _triage_row(
    tmp_path: Path,
    report_name: str,
    config_path: Path,
    report_dir: Path,
) -> dict:
    return {
        "report_id": f"report:{report_name}",
        "report_name": report_name,
        "config_path": str(config_path.relative_to(tmp_path)),
        "pilot_summary_path": str((report_dir / "pilot_summary.json").relative_to(tmp_path)),
        "feature_leakage_audit_path": str(
            (report_dir / "feature_leakage_audit.json").relative_to(tmp_path)
        ),
        "metadata_limitation_class": "metadata_completeness_not_recorded",
    }


def test_completeness_backfill_updates_sidecar_without_changing_decision(tmp_path):
    report_name = "stackoverflow_custom"
    cache, config_path, ledger_path, report_dir = _experiment_paths(tmp_path, report_name)
    _metadata(
        cache,
        "clean123",
        {
            "artifact_id": "clean123",
            "dataset_id": "toy",
            "feature_names": ["x1", "x2"],
            "preprocessed_feature_names": ["x1", "x2"],
            "feature_drop_columns": ["target", "group"],
            "feature_drop_policy": {"target": "target", "primary_group_col": "group"},
            "group_col": "group",
            "model_id": "ridge",
            "model_params": {"alpha": 1.0},
            "seed": 11,
            "target": "target",
            "target_transform": "identity",
        },
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(_ledger_row("clean123")) + "\n", encoding="utf-8")
    _write_json(
        report_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_stackoverflow_feature_leakage_audit_v1",
            "metadata_files_scanned": 1,
            "metadata_selection": "ledger_referenced_prediction_artifacts",
            "violations_count": 0,
        },
    )
    triage_path = tmp_path / "experiments/regression/reports/audit/triage.json"
    _write_json(triage_path, {"rows": [_triage_row(tmp_path, report_name, config_path, report_dir)]})

    payload = backfill.build_payload(
        root=tmp_path,
        triage_path=triage_path,
        report_names=set(),
        force=False,
        dry_run=False,
    )

    sidecar = json.loads(
        (report_dir / "feature_leakage_audit.json").read_text(encoding="utf-8")
    )
    expected_zero = {
        "missing_feature_names": 0,
        "missing_preprocessed_feature_names": 0,
        "missing_feature_drop_columns": 0,
        "missing_feature_drop_policy": 0,
    }
    assert payload["status_counts"] == {"updated": 1}
    assert payload["updated_sidecar_count"] == 1
    assert payload["total_missing_metadata_fields"] == 0
    assert sidecar["schema"] == "cpfi_stackoverflow_feature_leakage_audit_v1"
    assert sidecar["violations_count"] == 0
    assert sidecar["metadata_completeness"] == expected_zero
    assert sidecar["raw_metadata_completeness"] == expected_zero
    assert sidecar["metadata_closure"]["enabled"] is False
    assert (
        sidecar["metadata_completeness_standardization"]["claim_boundary"]
        == "Metadata-completeness field standardization only; existing feature-leakage violation decisions and performance evidence are unchanged."
    )


def test_completeness_backfill_records_missing_fields_when_metadata_is_incomplete(tmp_path):
    report_name = "incomplete_metadata_report"
    cache, config_path, ledger_path, report_dir = _experiment_paths(tmp_path, report_name)
    _metadata(
        cache,
        "miss123",
        {
            "artifact_id": "miss123",
            "dataset_id": "toy",
            "feature_names": ["x1"],
            "model_id": "ridge",
            "seed": 11,
            "target": "target",
        },
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(_ledger_row("miss123")) + "\n", encoding="utf-8")
    _write_json(
        report_dir / "feature_leakage_audit.json",
        {"schema": "legacy", "metadata_files_scanned": 1, "violations_count": 0},
    )
    triage_path = tmp_path / "experiments/regression/reports/audit/triage.json"
    _write_json(triage_path, {"rows": [_triage_row(tmp_path, report_name, config_path, report_dir)]})

    payload = backfill.build_payload(
        root=tmp_path,
        triage_path=triage_path,
        report_names=set(),
        force=False,
        dry_run=False,
    )

    sidecar = json.loads(
        (report_dir / "feature_leakage_audit.json").read_text(encoding="utf-8")
    )
    assert payload["total_missing_metadata_fields"] == 3
    assert sidecar["metadata_completeness"] == {
        "missing_feature_names": 0,
        "missing_preprocessed_feature_names": 1,
        "missing_feature_drop_columns": 1,
        "missing_feature_drop_policy": 1,
    }
