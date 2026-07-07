import json
from pathlib import Path

import yaml

from experiments.regression.scripts import (
    repair_feature_leakage_prediction_metadata as repair,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _metadata(cache: Path, artifact_id: str, payload: dict) -> Path:
    path = cache / artifact_id[:2] / artifact_id / "metadata.json"
    _write_json(path, payload)
    return path


def _fixture(tmp_path: Path, report_name: str = "legacy_policy_gap") -> dict[str, Path]:
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
                "experiment_id": f"{report_name}_v0",
                "logging": {
                    "ledger": str(ledger_path.relative_to(tmp_path)),
                    "prediction_cache_root": str(cache.relative_to(tmp_path)),
                },
            }
        ),
        encoding="utf-8",
    )
    _write_json(report_dir / "pilot_summary.json", {"ledger": str(ledger_path.relative_to(tmp_path))})
    return {
        "cache": cache,
        "config": config_path,
        "ledger": ledger_path,
        "report_dir": report_dir,
    }


def _ledger_row(artifact_id: str) -> dict:
    return {
        "status": "completed",
        "run_id": f"run-{artifact_id}",
        "prediction_artifact": artifact_id,
        "dataset_id": "toy",
        "model_family": "linear",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "seed": 7,
    }


def _sidecar(report_dir: Path) -> None:
    _write_json(
        report_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "metadata_files_scanned": 1,
            "metadata_selection": "ledger_referenced_prediction_artifacts",
            "forbidden_features": ["target", "group"],
            "required_features": ["x1", "x2"],
            "expected_features": ["x1", "x2"],
            "expected_drop_columns": ["target", "group"],
            "expected_target": "target",
            "expected_group_col": "group",
            "expected_target_transform": "identity",
            "violations_count": 0,
        },
    )


def _triage(
    tmp_path: Path, report_name: str, config_path: Path, report_dir: Path
) -> Path:
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
                    "dataset_ids": ["toy"],
                    "policy_inference_status": "incomplete_drop_or_policy_metadata",
                    "provenance_limitation_class": "policy_inference_incomplete",
                }
            ]
        },
    )
    return triage_path


def test_prediction_metadata_repair_updates_metadata_and_refreshes_sidecar(tmp_path):
    paths = _fixture(tmp_path)
    metadata_path = _metadata(
        paths["cache"],
        "repairme",
        {
            "artifact_id": "repairme",
            "artifact_schema": "prediction_bundle_v1",
            "dataset_id": "toy",
            "feature_count": 2,
            "feature_names": ["x1", "x2"],
            "feature_reducer": None,
            "group_col": "group",
            "model_id": "ridge",
            "model_params": {"alpha": 1.0},
            "seed": 7,
            "target": "target",
            "target_transform": "identity",
        },
    )
    paths["ledger"].parent.mkdir(parents=True, exist_ok=True)
    paths["ledger"].write_text(json.dumps(_ledger_row("repairme")) + "\n", encoding="utf-8")
    _sidecar(paths["report_dir"])
    triage_path = _triage(tmp_path, "legacy_policy_gap", paths["config"], paths["report_dir"])

    payload = repair.build_payload(
        root=tmp_path,
        triage_path=triage_path,
        report_names=set(),
        dry_run=False,
        force=False,
        max_exact_feature_set_size=10,
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    sidecar = json.loads(
        (paths["report_dir"] / "feature_leakage_audit.json").read_text(encoding="utf-8")
    )
    assert payload["status_counts"] == {"repaired": 1}
    assert payload["total_metadata_files_repaired"] == 1
    assert payload["fields_added_counts"] == {
        "feature_drop_columns": 1,
        "feature_drop_policy": 1,
        "preprocessed_feature_count": 1,
        "preprocessed_feature_names": 1,
    }
    assert metadata["feature_drop_columns"] == ["target", "group"]
    assert metadata["feature_drop_policy"]["target"] == "target"
    assert metadata["feature_drop_policy"]["primary_group_col"] == "group"
    assert metadata["preprocessed_feature_names"] == ["x1", "x2"]
    assert metadata["metadata_repair_history"][0]["schema"] == repair.METADATA_REPAIR_SCHEMA
    assert sidecar["raw_metadata_completeness"] == {
        "missing_feature_names": 0,
        "missing_preprocessed_feature_names": 0,
        "missing_feature_drop_columns": 0,
        "missing_feature_drop_policy": 0,
    }
    assert sidecar["metadata_closure"]["enabled"] is False
    assert sidecar["backfill_policy_inference"]["complete_drop_metadata"] is True
    assert sidecar["violations_count"] == 0


def test_prediction_metadata_repair_dry_run_does_not_write_metadata(tmp_path):
    paths = _fixture(tmp_path)
    metadata_path = _metadata(
        paths["cache"],
        "dryrun",
        {
            "artifact_id": "dryrun",
            "dataset_id": "toy",
            "feature_count": 1,
            "feature_names": ["x1"],
            "group_col": "group",
            "target": "target",
        },
    )
    before = metadata_path.read_text(encoding="utf-8")
    paths["ledger"].parent.mkdir(parents=True, exist_ok=True)
    paths["ledger"].write_text(json.dumps(_ledger_row("dryrun")) + "\n", encoding="utf-8")
    _sidecar(paths["report_dir"])
    triage_path = _triage(tmp_path, "legacy_policy_gap", paths["config"], paths["report_dir"])

    payload = repair.build_payload(
        root=tmp_path,
        triage_path=triage_path,
        report_names=set(),
        dry_run=True,
        force=False,
        max_exact_feature_set_size=10,
    )

    assert payload["status_counts"] == {"planned": 1}
    assert metadata_path.read_text(encoding="utf-8") == before


def test_safe_preprocessed_names_require_matching_feature_count():
    assert (
        repair.safe_preprocessed_feature_names(
            {"feature_names": ["x1", "x2"], "feature_count": 3, "feature_reducer": None}
        )
        is None
    )
