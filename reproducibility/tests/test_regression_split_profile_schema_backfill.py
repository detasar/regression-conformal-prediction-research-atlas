import json
from pathlib import Path

import yaml

from experiments.regression.scripts import backfill_split_profile_schema as backfill


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _backlog(root: Path, report_name: str, dataset_id: str = "toy") -> Path:
    path = root / "experiments/regression/reports/audit/integrity_remediation_backlog.json"
    _write_json(
        path,
        {
            "schema": "cpfi_integrity_remediation_backlog_v1",
            "rows": [
                {
                    "action_id": f"{report_name}:caveat:legacy_split_profile_schema_partial_integrity",
                    "status": "open",
                    "issue_type": "legacy_split_profile_schema_partial_integrity",
                    "report_name": report_name,
                    "config_path": f"experiments/regression/configs/{report_name}.yaml",
                    "dataset_ids": [dataset_id],
                    "evidence": {
                        "split_profile": {
                            "path": (
                                f"experiments/regression/reports/{report_name}/"
                                "split_profile.json"
                            )
                        }
                    },
                },
                {
                    "action_id": "ignored:caveat:other",
                    "status": "open",
                    "issue_type": "duplicate_signature_cross_split_caveat",
                    "report_name": "ignored",
                },
            ],
        },
    )
    return path


def _legacy_report(root: Path, report_name: str) -> None:
    _write_yaml(
        root / f"experiments/regression/configs/{report_name}.yaml",
        {
            "experiment_id": f"{report_name}_v0",
            "datasets": ["toy"],
            "random_seeds": [11],
            "splits": {"train": 0.5, "calibration": 0.25, "test": 0.25},
        },
    )
    _write_json(
        root / f"experiments/regression/reports/{report_name}/split_profile.json",
        {"schema": "legacy_split_profile_v1", "dataset_id": "toy"},
    )


def test_split_profile_schema_backfill_updates_legacy_sidecar(tmp_path, monkeypatch):
    report_name = "model_family_sweep_toy"
    _legacy_report(tmp_path, report_name)
    backlog_path = _backlog(tmp_path, report_name)

    def fake_build_payload(config_path, config):
        assert config_path.name == f"{report_name}.yaml"
        assert config["datasets"] == ["toy"]
        return {
            "schema": "cpfi_regression_split_profile_v2",
            "created_at_utc": "2026-01-01T00:00:00+00:00",
            "config_path": str(config_path),
            "experiment_id": f"{report_name}_v0",
            "run_id": report_name,
            "dataset_ids": ["toy"],
            "dataset_id": "toy",
            "target_transform": "identity",
            "split_config": {
                "train": 0.5,
                "calibration": 0.25,
                "test": 0.25,
                "group_col": None,
                "strategy": "random",
                "order_col": None,
            },
            "profiles": [{"dataset_id": "toy", "seeds": [{"seed": 11}]}],
            "seeds": [{"seed": 11}],
        }

    monkeypatch.setattr(backfill.split_audit, "build_payload", fake_build_payload)
    monkeypatch.setattr(backfill.split_audit, "render_markdown", lambda payload: "# split\n")

    payload = backfill.build_payload(
        root=tmp_path,
        backlog_path=backlog_path,
        out_path=tmp_path / "out.json",
        report_names=set(),
        dry_run=False,
        force=False,
    )

    split_path = tmp_path / f"experiments/regression/reports/{report_name}/split_profile.json"
    updated = json.loads(split_path.read_text(encoding="utf-8"))
    assert payload["summary"]["status_counts"] == {"updated": 1}
    assert payload["summary"]["seed_profiles_generated"] == 1
    assert updated["schema"] == "cpfi_regression_split_profile_v2"
    assert split_path.with_suffix(".md").exists()


def test_split_profile_schema_backfill_dry_run_does_not_overwrite(tmp_path, monkeypatch):
    report_name = "model_family_sweep_toy"
    _legacy_report(tmp_path, report_name)
    backlog_path = _backlog(tmp_path, report_name)

    monkeypatch.setattr(
        backfill.split_audit,
        "build_payload",
        lambda config_path, config: {
            "schema": "cpfi_regression_split_profile_v2",
            "dataset_ids": ["toy"],
            "profiles": [{"dataset_id": "toy", "seeds": [{"seed": 11}]}],
        },
    )

    payload = backfill.build_payload(
        root=tmp_path,
        backlog_path=backlog_path,
        out_path=tmp_path / "out.json",
        report_names=set(),
        dry_run=True,
        force=False,
    )

    split_path = tmp_path / f"experiments/regression/reports/{report_name}/split_profile.json"
    assert payload["summary"]["status_counts"] == {"planned": 1}
    assert json.loads(split_path.read_text(encoding="utf-8"))["schema"] == (
        "legacy_split_profile_v1"
    )


def test_split_profile_schema_backfill_rejects_dataset_mismatch(tmp_path, monkeypatch):
    report_name = "model_family_sweep_toy"
    _legacy_report(tmp_path, report_name)
    backlog_path = _backlog(tmp_path, report_name, dataset_id="toy")

    monkeypatch.setattr(
        backfill.split_audit,
        "build_payload",
        lambda config_path, config: {
            "schema": "cpfi_regression_split_profile_v2",
            "dataset_ids": ["other"],
            "profiles": [{"dataset_id": "other", "seeds": [{"seed": 11}]}],
        },
    )

    payload = backfill.build_payload(
        root=tmp_path,
        backlog_path=backlog_path,
        out_path=tmp_path / "out.json",
        report_names=set(),
        dry_run=False,
        force=False,
    )

    assert payload["summary"]["status_counts"] == {"failed_dataset_mismatch": 1}
    assert payload["summary"]["failure_count"] == 1
