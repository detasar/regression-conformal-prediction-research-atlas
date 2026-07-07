import json

import yaml

from experiments.regression.scripts.backfill_feature_leakage_sidecars import (
    backfill_from_backlog,
    canonical_ledger_rows,
    canonical_prediction_metadata_rows,
    infer_policy_checks,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _metadata(root, artifact_id, payload):
    _write_json(root / artifact_id[:2] / artifact_id / "metadata.json", payload)


def _backlog(root, report_name):
    backlog = {
        "schema": "cpfi_integrity_remediation_backlog_v1",
        "rows": [
            {
                "action_id": f"{report_name}:caveat:no_prediction_metadata_feature_leakage_sidecar",
                "status": "open",
                "issue_type": "no_prediction_metadata_feature_leakage_sidecar",
                "report_id": f"report:{report_name}",
                "report_name": report_name,
                "config_path": f"experiments/regression/configs/{report_name}.yaml",
                "pilot_summary_path": (
                    f"experiments/regression/reports/{report_name}/pilot_summary.json"
                ),
            }
        ],
    }
    path = root / "experiments/regression/reports/audit/integrity_backlog.json"
    _write_json(path, backlog)
    return path


def test_infer_policy_checks_enforces_single_feature_and_drop_set(tmp_path):
    cache = tmp_path / "cache"
    _metadata(
        cache,
        "abcdef",
        {
            "target": "zfygpa",
            "group_col": "race",
            "target_transform": "identity",
            "feature_names": ["gender", "lsat", "ugpa"],
            "feature_drop_columns": ["race", "zfygpa"],
            "feature_drop_policy": {"target": "zfygpa", "primary_group_col": "race"},
        },
    )

    checks = infer_policy_checks(
        list(cache.glob("*/*/metadata.json")),
        max_exact_feature_set_size=10,
    )

    assert checks["forbidden_features"] == {"race", "zfygpa"}
    assert checks["expected_features"] == {"gender", "lsat", "ugpa"}
    assert checks["required_features"] == {"gender", "lsat", "ugpa"}
    assert checks["expected_drop_columns"] == {"race", "zfygpa"}
    assert checks["expected_target"] == "zfygpa"
    assert checks["expected_group_col"] == "race"
    assert checks["expected_target_transform"] == "identity"
    assert checks["inference"]["exact_feature_set_enforced"] is True
    assert checks["inference"]["exact_drop_set_enforced"] is True


def test_infer_policy_checks_avoids_exact_feature_set_for_variable_reducers(tmp_path):
    cache = tmp_path / "cache"
    base = {
        "target": "oz2",
        "group_col": "oz2_bin",
        "target_transform": "identity",
        "feature_drop_columns": ["oz2", "oz2_bin"],
        "feature_drop_policy": {"target": "oz2", "primary_group_col": "oz2_bin"},
    }
    _metadata(cache, "aaaaaa", {**base, "feature_names": ["f1", "f2"]})
    _metadata(cache, "bbbbbb", {**base, "feature_names": ["f2", "f3"]})

    checks = infer_policy_checks(
        list(cache.glob("*/*/metadata.json")),
        max_exact_feature_set_size=10,
    )

    assert checks["forbidden_features"] == {"oz2", "oz2_bin"}
    assert checks["expected_features"] == set()
    assert checks["required_features"] == set()
    assert checks["expected_drop_columns"] == {"oz2", "oz2_bin"}
    assert checks["inference"]["unique_feature_set_count"] == 2
    assert checks["inference"]["exact_feature_set_enforced"] is False


def test_infer_policy_checks_treats_missing_policy_as_completeness_caveat(tmp_path):
    cache = tmp_path / "cache"
    _metadata(
        cache,
        "legacy",
        {
            "target": "WAGE",
            "group_col": "SEX",
            "target_transform": "log1p",
            "feature_names": ["AGE", "EDUCATION"],
        },
    )

    checks = infer_policy_checks(
        list(cache.glob("*/*/metadata.json")),
        max_exact_feature_set_size=10,
    )

    assert checks["forbidden_features"] == {"SEX", "WAGE"}
    assert checks["expected_target"] is None
    assert checks["expected_group_col"] is None
    assert checks["expected_target_transform"] == "log1p"
    assert checks["expected_drop_columns"] == set()
    assert checks["inference"]["missing_feature_drop_columns"] == 1
    assert checks["inference"]["missing_feature_drop_policy"] == 1
    assert checks["inference"]["complete_drop_metadata"] is False
    assert checks["inference"]["complete_policy_metadata"] is False


def test_backfill_from_backlog_writes_sidecar_with_inferred_policy(tmp_path):
    report_name = "toy_regression_report"
    cache = (
        tmp_path
        / "experiments/regression/results/toy_regression_report/checkpoints/predictions"
    )
    _metadata(
        cache,
        "abcdef",
        {
            "artifact_id": "abcdef",
            "dataset_id": "aif360_lawschool_gpa",
            "feature_names": ["gender", "lsat", "ugpa"],
            "preprocessed_feature_names": ["gender", "lsat", "ugpa"],
            "feature_drop_columns": ["race", "zfygpa"],
            "feature_drop_policy": {"target": "zfygpa", "primary_group_col": "race"},
            "group_col": "race",
            "model_id": "ridge",
            "model_params": {"alpha": 1.0},
            "seed": 11,
            "target": "zfygpa",
            "target_transform": "identity",
        },
    )
    config_path = tmp_path / f"experiments/regression/configs/{report_name}.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "logging": {
                    "prediction_cache_root": (
                        "experiments/regression/results/toy_regression_report/"
                        "checkpoints/predictions"
                    )
                }
            }
        ),
        encoding="utf-8",
    )
    _write_json(
        tmp_path / f"experiments/regression/reports/{report_name}/pilot_summary.json",
        {"ledger": "experiments/regression/results/toy_regression_report/ledger.jsonl"},
    )
    backlog = _backlog(tmp_path, report_name)

    summary = backfill_from_backlog(
        root=tmp_path,
        backlog_path=backlog,
        report_names=set(),
        force=False,
        dry_run=False,
        max_exact_feature_set_size=10,
    )

    sidecar = (
        tmp_path
        / f"experiments/regression/reports/{report_name}/feature_leakage_audit.json"
    )
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert summary["status_counts"] == {"generated": 1}
    assert summary["total_metadata_files_scanned"] == 1
    assert payload["violations_count"] == 0
    assert payload["forbidden_features"] == ["race", "zfygpa"]
    assert payload["expected_features"] == ["gender", "lsat", "ugpa"]
    assert payload["expected_drop_columns"] == ["race", "zfygpa"]
    assert payload["expected_target"] == "zfygpa"
    assert payload["expected_group_col"] == "race"
    assert payload["backfill_policy_inference"]["exact_feature_set_enforced"] is True
    assert (
        tmp_path
        / f"experiments/regression/reports/{report_name}/feature_leakage_audit.md"
    ).exists()


def test_backfill_from_backlog_skips_existing_sidecar_without_force(tmp_path):
    report_name = "toy_existing_report"
    cache = (
        tmp_path
        / "experiments/regression/results/toy_existing_report/checkpoints/predictions"
    )
    _metadata(
        cache,
        "abcdef",
        {
            "dataset_id": "toy",
            "feature_names": ["x"],
            "feature_drop_columns": ["y", "g"],
            "feature_drop_policy": {"target": "y", "primary_group_col": "g"},
            "group_col": "g",
            "model_id": "ridge",
            "seed": 1,
            "target": "y",
            "target_transform": "identity",
        },
    )
    config_path = tmp_path / f"experiments/regression/configs/{report_name}.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "logging": {
                    "prediction_cache_root": (
                        "experiments/regression/results/toy_existing_report/"
                        "checkpoints/predictions"
                    )
                }
            }
        ),
        encoding="utf-8",
    )
    report_dir = tmp_path / f"experiments/regression/reports/{report_name}"
    _write_json(report_dir / "pilot_summary.json", {"ledger": "unused"})
    _write_json(report_dir / "feature_leakage_audit.json", {"schema": "existing"})
    backlog = _backlog(tmp_path, report_name)

    summary = backfill_from_backlog(
        root=tmp_path,
        backlog_path=backlog,
        report_names=set(),
        force=False,
        dry_run=False,
        max_exact_feature_set_size=10,
    )

    assert summary["status_counts"] == {"skipped_existing_sidecar": 1}
    assert json.loads((report_dir / "feature_leakage_audit.json").read_text()) == {
        "schema": "existing"
    }


def test_backfill_scans_ledger_referenced_metadata_not_stale_cache(tmp_path):
    report_name = "toy_stale_cache_report"
    cache = (
        tmp_path
        / "experiments/regression/results/toy_stale_cache_report/checkpoints/predictions"
    )
    _metadata(
        cache,
        "clean1",
        {
            "artifact_id": "clean1",
            "dataset_id": "toy",
            "feature_names": ["x"],
            "preprocessed_feature_names": ["x"],
            "feature_drop_columns": ["y", "g"],
            "feature_drop_policy": {"target": "y", "primary_group_col": "g"},
            "group_col": "g",
            "model_id": "ridge",
            "model_params": {},
            "seed": 1,
            "target": "y",
            "target_transform": "identity",
        },
    )
    _metadata(
        cache,
        "stale1",
        {
            "artifact_id": "stale1",
            "dataset_id": "toy",
            "feature_names": ["x", "y", "g"],
            "preprocessed_feature_names": ["x", "y", "g"],
            "feature_drop_columns": ["y", "g"],
            "feature_drop_policy": {"target": "y", "primary_group_col": "g"},
            "group_col": "g",
            "model_id": "ridge",
            "model_params": {},
            "seed": 1,
            "target": "y",
            "target_transform": "identity",
        },
    )
    config_path = tmp_path / f"experiments/regression/configs/{report_name}.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "logging": {
                    "ledger": (
                        "experiments/regression/results/toy_stale_cache_report/"
                        "ledger.jsonl"
                    ),
                    "prediction_cache_root": (
                        "experiments/regression/results/toy_stale_cache_report/"
                        "checkpoints/predictions"
                    ),
                }
            }
        ),
        encoding="utf-8",
    )
    ledger = (
        tmp_path / "experiments/regression/results/toy_stale_cache_report/ledger.jsonl"
    )
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps(
            {
                "status": "completed",
                "prediction_artifact": "clean1",
                "dataset_id": "toy",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        tmp_path / f"experiments/regression/reports/{report_name}/pilot_summary.json",
        {
            "ledger": (
                "experiments/regression/results/toy_stale_cache_report/ledger.jsonl"
            )
        },
    )
    backlog = _backlog(tmp_path, report_name)

    summary = backfill_from_backlog(
        root=tmp_path,
        backlog_path=backlog,
        report_names=set(),
        force=False,
        dry_run=False,
        max_exact_feature_set_size=10,
    )

    sidecar = (
        tmp_path
        / f"experiments/regression/reports/{report_name}/feature_leakage_audit.json"
    )
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert summary["rows"][0]["metadata_selection"] == (
        "ledger_referenced_prediction_artifacts"
    )
    assert payload["metadata_selection"] == "ledger_referenced_prediction_artifacts"
    assert payload["metadata_files_scanned"] == 1
    assert payload["violations_count"] == 0


def test_backfill_uses_canonical_ledger_when_run_id_is_rewritten(tmp_path):
    report_name = "toy_canonical_cache_report"
    cache = (
        tmp_path
        / "experiments/regression/results/toy_canonical_cache_report/checkpoints/predictions"
    )
    _metadata(
        cache,
        "stale1",
        {
            "artifact_id": "stale1",
            "dataset_id": "toy",
            "feature_names": ["x", "y", "g"],
            "preprocessed_feature_names": ["x", "y", "g"],
            "feature_drop_columns": ["y", "g"],
            "feature_drop_policy": {"target": "y", "primary_group_col": "g"},
            "group_col": "g",
            "model_id": "ridge",
            "model_params": {},
            "seed": 1,
            "target": "y",
            "target_transform": "identity",
        },
    )
    _metadata(
        cache,
        "clean1",
        {
            "artifact_id": "clean1",
            "dataset_id": "toy",
            "feature_names": ["x"],
            "preprocessed_feature_names": ["x"],
            "feature_drop_columns": ["y", "g"],
            "feature_drop_policy": {"target": "y", "primary_group_col": "g"},
            "group_col": "g",
            "model_id": "ridge",
            "model_params": {},
            "seed": 1,
            "target": "y",
            "target_transform": "identity",
        },
    )
    config_path = tmp_path / f"experiments/regression/configs/{report_name}.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "logging": {
                    "ledger": (
                        "experiments/regression/results/toy_canonical_cache_report/"
                        "ledger.jsonl"
                    ),
                    "prediction_cache_root": (
                        "experiments/regression/results/toy_canonical_cache_report/"
                        "checkpoints/predictions"
                    ),
                }
            }
        ),
        encoding="utf-8",
    )
    ledger = (
        tmp_path
        / "experiments/regression/results/toy_canonical_cache_report/ledger.jsonl"
    )
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "status": "completed",
                        "run_id": "same-run",
                        "prediction_artifact": "stale1",
                    }
                ),
                json.dumps(
                    {
                        "status": "completed",
                        "run_id": "same-run",
                        "prediction_artifact": "clean1",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        tmp_path / f"experiments/regression/reports/{report_name}/pilot_summary.json",
        {
            "ledger": (
                "experiments/regression/results/toy_canonical_cache_report/ledger.jsonl"
            )
        },
    )
    backlog = _backlog(tmp_path, report_name)

    summary = backfill_from_backlog(
        root=tmp_path,
        backlog_path=backlog,
        report_names=set(),
        force=False,
        dry_run=False,
        max_exact_feature_set_size=10,
    )

    sidecar = (
        tmp_path
        / f"experiments/regression/reports/{report_name}/feature_leakage_audit.json"
    )
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert summary["rows"][0]["metadata_selection"] == (
        "ledger_referenced_prediction_artifacts"
    )
    assert payload["metadata_files_scanned"] == 1
    assert payload["violations_count"] == 0


def test_backfill_supersedes_legacy_prediction_schema_with_new_run_id(tmp_path):
    report_name = "toy_prediction_schema_refresh"
    cache = (
        tmp_path
        / "experiments/regression/results/toy_prediction_schema_refresh/"
        "checkpoints/predictions"
    )
    _metadata(
        cache,
        "legacy1",
        {
            "artifact_schema": "prediction_bundle_v1",
            "dataset_id": "toy",
            "feature_names": ["x"],
            "group_col": "g",
            "model_id": "ridge",
            "model_params": {"alpha": 1.0},
            "seed": 7,
            "target": "y",
            "target_transform": "identity",
        },
    )
    _metadata(
        cache,
        "schema4",
        {
            "artifact_schema": "prediction_bundle_v4",
            "dataset_id": "toy",
            "feature_names": ["x"],
            "preprocessed_feature_names": ["x"],
            "feature_drop_columns": ["y", "g"],
            "feature_drop_policy": {"target": "y", "primary_group_col": "g"},
            "group_col": "g",
            "model_id": "ridge",
            "model_params": {"alpha": 1.0},
            "seed": 7,
            "target": "y",
            "target_transform": "identity",
        },
    )
    config_path = tmp_path / f"experiments/regression/configs/{report_name}.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "logging": {
                    "ledger": (
                        "experiments/regression/results/"
                        "toy_prediction_schema_refresh/ledger.jsonl"
                    ),
                    "prediction_cache_root": (
                        "experiments/regression/results/"
                        "toy_prediction_schema_refresh/checkpoints/predictions"
                    ),
                }
            }
        ),
        encoding="utf-8",
    )
    ledger = (
        tmp_path
        / "experiments/regression/results/toy_prediction_schema_refresh/ledger.jsonl"
    )
    ledger.parent.mkdir(parents=True, exist_ok=True)
    common = {
        "status": "completed",
        "dataset_id": "toy",
        "model_family": "linear",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "seed": 7,
    }
    ledger.write_text(
        "\n".join(
            [
                json.dumps({**common, "run_id": "old-run", "prediction_artifact": "legacy1"}),
                json.dumps({**common, "run_id": "new-run", "prediction_artifact": "schema4"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        tmp_path / f"experiments/regression/reports/{report_name}/pilot_summary.json",
        {
            "ledger": (
                "experiments/regression/results/"
                "toy_prediction_schema_refresh/ledger.jsonl"
            )
        },
    )
    backlog = _backlog(tmp_path, report_name)

    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [
        row["prediction_artifact"]
        for row in canonical_prediction_metadata_rows(rows)
    ] == ["schema4"]

    summary = backfill_from_backlog(
        root=tmp_path,
        backlog_path=backlog,
        report_names=set(),
        force=False,
        dry_run=False,
        max_exact_feature_set_size=10,
    )

    sidecar = (
        tmp_path
        / f"experiments/regression/reports/{report_name}/feature_leakage_audit.json"
    )
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert summary["total_metadata_files_scanned"] == 1
    assert payload["metadata_files_scanned"] == 1
    assert payload["metadata_completeness"] == {
        "missing_feature_drop_columns": 0,
        "missing_feature_drop_policy": 0,
        "missing_feature_names": 0,
        "missing_preprocessed_feature_names": 0,
    }
    assert payload["violations_count"] == 0


def test_canonical_ledger_rows_prefers_completed_and_later_rows():
    rows = [
        {"run_id": "a", "status": "completed", "prediction_artifact": "old"},
        {"run_id": "b", "status": "failed", "prediction_artifact": "failed"},
        {"run_id": "a", "status": "completed", "prediction_artifact": "new"},
        {"run_id": "b", "status": "completed", "prediction_artifact": "fixed"},
    ]

    canonical = canonical_ledger_rows(rows)

    assert [row["prediction_artifact"] for row in canonical] == ["new", "fixed"]


def test_backfill_summarizes_existing_sidecars_after_backlog_closes(tmp_path):
    backlog = tmp_path / "experiments/regression/reports/audit/integrity_backlog.json"
    _write_json(
        backlog,
        {
            "schema": "cpfi_integrity_remediation_backlog_v1",
            "rows": [],
        },
    )
    sidecar = (
        tmp_path
        / "experiments/regression/reports/toy_closed/feature_leakage_audit.json"
    )
    _write_json(
        sidecar,
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "source_backlog_action_id": (
                "toy_closed:caveat:no_prediction_metadata_feature_leakage_sidecar"
            ),
            "source_cross_run_report_id": "report:toy_closed",
            "config_path": "experiments/regression/configs/toy_closed.yaml",
            "prediction_cache_root": "experiments/regression/results/toy_closed",
            "metadata_selection": "ledger_referenced_prediction_artifacts",
            "metadata_files_scanned": 2,
            "violations_count": 1,
            "metadata_completeness": {"missing_feature_drop_policy": 1},
            "dataset_ids": ["toy"],
            "expected_target_transform": "identity",
            "backfill_policy_inference": {
                "exact_feature_set_enforced": True,
                "exact_drop_set_enforced": False,
            },
        },
    )
    (sidecar.with_suffix(".md")).write_text("# sidecar\n", encoding="utf-8")

    summary = backfill_from_backlog(
        root=tmp_path,
        backlog_path=backlog,
        report_names=set(),
        force=False,
        dry_run=False,
        max_exact_feature_set_size=10,
        include_existing_backfills=True,
    )

    assert summary["action_count"] == 0
    assert summary["status_counts"] == {"existing_backfilled_sidecar": 1}
    assert summary["total_metadata_files_scanned"] == 2
    assert summary["total_violations"] == 1
    assert summary["rows"][0]["report_name"] == "toy_closed"


def test_backfill_keeps_existing_sidecar_rows_when_new_actions_exist(tmp_path):
    backlog = tmp_path / "experiments/regression/reports/audit/integrity_backlog.json"
    active_report = "toy_active"
    closed_report = "toy_closed"
    _write_json(
        backlog,
        {
            "schema": "cpfi_integrity_remediation_backlog_v1",
            "rows": [
                {
                    "action_id": (
                        f"{active_report}:caveat:"
                        "no_prediction_metadata_feature_leakage_sidecar"
                    ),
                    "report_id": f"report:{active_report}",
                    "report_name": active_report,
                    "issue_type": "no_prediction_metadata_feature_leakage_sidecar",
                    "status": "open",
                    "config_path": (
                        f"experiments/regression/configs/{active_report}.yaml"
                    ),
                    "pilot_summary_path": (
                        f"experiments/regression/reports/{active_report}/"
                        "pilot_summary.json"
                    ),
                }
            ],
        },
    )

    cache = (
        tmp_path
        / f"experiments/regression/results/{active_report}/checkpoints/predictions"
    )
    _metadata(
        cache,
        "clean1",
        {
            "artifact_id": "clean1",
            "dataset_id": "toy_active_dataset",
            "feature_names": ["x"],
            "feature_drop_columns": ["y", "g"],
            "feature_drop_policy": {"target": "y", "primary_group_col": "g"},
            "group_col": "g",
            "model_id": "ridge",
            "seed": 1,
            "target": "y",
            "target_transform": "identity",
        },
    )
    config_path = tmp_path / f"experiments/regression/configs/{active_report}.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "logging": {
                    "prediction_cache_root": (
                        f"experiments/regression/results/{active_report}/"
                        "checkpoints/predictions"
                    )
                }
            }
        ),
        encoding="utf-8",
    )
    report_dir = tmp_path / f"experiments/regression/reports/{active_report}"
    report_dir.mkdir(parents=True, exist_ok=True)
    _write_json(report_dir / "pilot_summary.json", {})

    closed_sidecar = (
        tmp_path
        / f"experiments/regression/reports/{closed_report}/feature_leakage_audit.json"
    )
    _write_json(
        closed_sidecar,
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "source_backlog_action_id": (
                f"{closed_report}:caveat:"
                "no_prediction_metadata_feature_leakage_sidecar"
            ),
            "source_cross_run_report_id": f"report:{closed_report}",
            "metadata_selection": "ledger_referenced_prediction_artifacts",
            "metadata_files_scanned": 2,
            "violations_count": 0,
            "dataset_ids": ["toy_closed_dataset"],
        },
    )

    summary = backfill_from_backlog(
        root=tmp_path,
        backlog_path=backlog,
        report_names=set(),
        force=False,
        dry_run=False,
        max_exact_feature_set_size=10,
        include_existing_backfills=True,
    )

    assert summary["action_count"] == 1
    assert summary["backfilled_sidecar_count"] == 2
    assert summary["status_counts"] == {
        "existing_backfilled_sidecar": 1,
        "generated": 1,
    }
    assert {row["report_name"] for row in summary["rows"]} == {
        active_report,
        closed_report,
    }


def test_force_refresh_existing_backfill_after_backlog_closes(tmp_path):
    report_name = "toy_force_refresh"
    cache = (
        tmp_path
        / "experiments/regression/results/toy_force_refresh/checkpoints/predictions"
    )
    _metadata(
        cache,
        "stale1",
        {
            "artifact_id": "stale1",
            "dataset_id": "toy",
            "feature_names": ["x", "y", "g"],
            "feature_drop_columns": ["y", "g"],
            "feature_drop_policy": {"target": "y", "primary_group_col": "g"},
            "group_col": "g",
            "model_id": "ridge",
            "seed": 1,
            "target": "y",
            "target_transform": "identity",
        },
    )
    _metadata(
        cache,
        "clean1",
        {
            "artifact_id": "clean1",
            "dataset_id": "toy",
            "feature_names": ["x"],
            "feature_drop_columns": ["y", "g"],
            "feature_drop_policy": {"target": "y", "primary_group_col": "g"},
            "group_col": "g",
            "model_id": "ridge",
            "seed": 1,
            "target": "y",
            "target_transform": "identity",
        },
    )
    config_path = tmp_path / f"experiments/regression/configs/{report_name}.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "logging": {
                    "ledger": (
                        "experiments/regression/results/toy_force_refresh/"
                        "ledger.jsonl"
                    ),
                    "prediction_cache_root": (
                        "experiments/regression/results/toy_force_refresh/"
                        "checkpoints/predictions"
                    ),
                }
            }
        ),
        encoding="utf-8",
    )
    ledger = tmp_path / "experiments/regression/results/toy_force_refresh/ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "status": "completed",
                        "run_id": "same-run",
                        "prediction_artifact": "stale1",
                    }
                ),
                json.dumps(
                    {
                        "status": "completed",
                        "run_id": "same-run",
                        "prediction_artifact": "clean1",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    report_dir = tmp_path / f"experiments/regression/reports/{report_name}"
    _write_json(
        report_dir / "pilot_summary.json",
        {"ledger": "experiments/regression/results/toy_force_refresh/ledger.jsonl"},
    )
    _write_json(
        report_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "source_backlog_action_id": (
                "toy_force_refresh:caveat:"
                "no_prediction_metadata_feature_leakage_sidecar"
            ),
            "source_cross_run_report_id": "report:toy_force_refresh",
            "config_path": f"experiments/regression/configs/{report_name}.yaml",
            "prediction_cache_root": (
                "experiments/regression/results/toy_force_refresh/"
                "checkpoints/predictions"
            ),
            "metadata_files_scanned": 1,
            "violations_count": 1,
        },
    )
    backlog = tmp_path / "experiments/regression/reports/audit/integrity_backlog.json"
    _write_json(backlog, {"schema": "cpfi_integrity_remediation_backlog_v1", "rows": []})

    summary = backfill_from_backlog(
        root=tmp_path,
        backlog_path=backlog,
        report_names=set(),
        force=True,
        dry_run=False,
        max_exact_feature_set_size=10,
        include_existing_backfills=True,
    )

    payload = json.loads((report_dir / "feature_leakage_audit.json").read_text())
    assert summary["status_counts"] == {"generated": 1}
    assert summary["total_violations"] == 0
    assert payload["metadata_files_scanned"] == 1
    assert payload["violations_count"] == 0
