import json
from pathlib import Path

import yaml

from experiments.regression.scripts import (
    backfill_feature_leakage_provenance_labels as backfill,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _metadata(root: Path, artifact_id: str, payload: dict) -> None:
    _write_json(root / artifact_id[:2] / artifact_id / "metadata.json", payload)


def test_backfill_updates_missing_labels_without_changing_violation_decision(tmp_path):
    report_name = "legacy_feature_report"
    cache = (
        tmp_path
        / "experiments/regression/results/legacy_feature_report/checkpoints/predictions"
    )
    _metadata(
        cache,
        "clean1",
        {
            "artifact_id": "clean1",
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
    config_path = tmp_path / f"experiments/regression/configs/{report_name}.yaml"
    ledger_path = tmp_path / f"experiments/regression/results/{report_name}/ledger.jsonl"
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
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": "run-1",
                "prediction_artifact": "clean1",
                "dataset_id": "toy",
                "model_family": "linear",
                "model_id": "ridge",
                "model_params": {"alpha": 1.0},
                "seed": 11,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report_dir = tmp_path / f"experiments/regression/reports/{report_name}"
    _write_json(report_dir / "pilot_summary.json", {"ledger": str(ledger_path.relative_to(tmp_path))})
    _write_json(
        report_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "metadata_files_scanned": 1,
            "metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 0,
                "missing_feature_drop_columns": 0,
                "missing_feature_drop_policy": 0,
            },
            "violations_count": 0,
        },
    )
    triage_path = tmp_path / "experiments/regression/reports/audit/triage.json"
    _write_json(
        triage_path,
        {
            "rows": [
                {
                    "report_id": f"report:{report_name}",
                    "report_name": report_name,
                    "config_path": str(config_path.relative_to(tmp_path)),
                    "pilot_summary_path": str(
                        (report_dir / "pilot_summary.json").relative_to(tmp_path)
                    ),
                    "feature_leakage_audit_path": str(
                        (report_dir / "feature_leakage_audit.json").relative_to(tmp_path)
                    ),
                    "metadata_selection_status": "legacy_selection_label_not_recorded",
                    "policy_inference_status": "legacy_policy_inference_label_not_recorded",
                }
            ]
        },
    )

    payload = backfill.build_payload(
        root=tmp_path,
        triage_path=triage_path,
        report_names=set(),
        force=False,
        dry_run=False,
        max_exact_feature_set_size=10,
    )

    sidecar = json.loads(
        (report_dir / "feature_leakage_audit.json").read_text(encoding="utf-8")
    )
    assert payload["status_counts"] == {"updated": 1}
    assert payload["updated_sidecar_count"] == 1
    assert sidecar["violations_count"] == 0
    assert sidecar["metadata_selection"] == "ledger_referenced_prediction_artifacts"
    assert sidecar["backfill_policy_inference"]["complete_drop_metadata"] is True
    assert sidecar["backfill_policy_inference"]["complete_policy_metadata"] is True
    assert sidecar["provenance_label_backfill"]["schema"] == backfill.SCHEMA
    assert (
        sidecar["provenance_label_backfill"]["claim_boundary"]
        == "Label-only provenance backfill; existing feature-leakage violation decisions and performance evidence are unchanged."
    )


def test_backfill_dry_run_does_not_write_sidecar(tmp_path):
    report_name = "dry_run_feature_report"
    cache = (
        tmp_path
        / "experiments/regression/results/dry_run_feature_report/checkpoints/predictions"
    )
    _metadata(
        cache,
        "clean1",
        {
            "artifact_id": "clean1",
            "dataset_id": "toy",
            "feature_names": ["x"],
            "feature_drop_columns": ["target"],
            "feature_drop_policy": {"target": "target"},
            "model_id": "ridge",
            "seed": 1,
            "target": "target",
        },
    )
    config_path = tmp_path / f"experiments/regression/configs/{report_name}.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump({"logging": {"prediction_cache_root": str(cache.relative_to(tmp_path))}}),
        encoding="utf-8",
    )
    report_dir = tmp_path / f"experiments/regression/reports/{report_name}"
    _write_json(report_dir / "pilot_summary.json", {})
    _write_json(
        report_dir / "feature_leakage_audit.json",
        {"schema": "legacy", "metadata_files_scanned": 1, "violations_count": 0},
    )
    triage_path = tmp_path / "experiments/regression/reports/audit/triage.json"
    _write_json(
        triage_path,
        {
            "rows": [
                {
                    "report_id": f"report:{report_name}",
                    "report_name": report_name,
                    "config_path": str(config_path.relative_to(tmp_path)),
                    "pilot_summary_path": str(
                        (report_dir / "pilot_summary.json").relative_to(tmp_path)
                    ),
                    "feature_leakage_audit_path": str(
                        (report_dir / "feature_leakage_audit.json").relative_to(tmp_path)
                    ),
                    "metadata_selection_status": "legacy_selection_label_not_recorded",
                    "policy_inference_status": "legacy_policy_inference_label_not_recorded",
                }
            ]
        },
    )

    payload = backfill.build_payload(
        root=tmp_path,
        triage_path=triage_path,
        report_names=set(),
        force=False,
        dry_run=True,
        max_exact_feature_set_size=10,
    )

    sidecar = json.loads(
        (report_dir / "feature_leakage_audit.json").read_text(encoding="utf-8")
    )
    assert payload["status_counts"] == {"planned": 1}
    assert payload["planned_sidecar_count"] == 1
    assert "metadata_selection" not in sidecar
    assert "backfill_policy_inference" not in sidecar
