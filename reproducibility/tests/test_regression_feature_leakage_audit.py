import json

from experiments.regression.scripts.audit_prediction_feature_leakage import (
    render_markdown,
    scan_metadata,
)
from experiments.regression.scripts.audit_methodology_sanity import (
    feature_leakage_sidecar_scan,
)


def _write_metadata(root, name, payload):
    path = root / name[:2] / name / "metadata.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_prediction_feature_leakage_audit_accepts_expected_metadata(tmp_path):
    _write_metadata(
        tmp_path,
        "abcdef",
        {
            "artifact_id": "abcdef",
            "dataset_id": "aif360_lawschool_gpa",
            "feature_names": ["gender", "lsat", "ugpa"],
            "preprocessed_feature_names": ["gender", "lsat", "ugpa"],
            "feature_drop_columns": ["zfygpa", "race"],
            "feature_drop_policy": {"target": "zfygpa", "primary_group_col": "race"},
            "group_col": "race",
            "model_id": "ridge",
            "seed": 11,
            "target": "zfygpa",
            "target_transform": "identity",
        },
    )

    payload = scan_metadata(
        tmp_path,
        forbidden_features={"zfygpa", "race"},
        required_features={"gender", "lsat", "ugpa"},
        expected_features={"gender", "lsat", "ugpa"},
        expected_drop_columns={"zfygpa", "race"},
        expected_target="zfygpa",
        expected_group_col="race",
        expected_target_transform="identity",
        config_path="experiments/regression/configs/lawschool.yaml",
    )

    assert payload["metadata_files_scanned"] == 1
    assert payload["config_path"] == "experiments/regression/configs/lawschool.yaml"
    assert payload["dataset_ids"] == ["aif360_lawschool_gpa"]
    assert payload["dataset_seed_cells"] == [
        {
            "dataset_id": "aif360_lawschool_gpa",
            "metadata_files": 1,
            "seed": "11",
            "unique_model_configs": 1,
        }
    ]
    assert payload["metadata_completeness"] == {
        "missing_feature_names": 0,
        "missing_feature_drop_columns": 0,
        "missing_feature_drop_policy": 0,
        "missing_preprocessed_feature_names": 0,
    }
    assert payload["violations_count"] == 0
    assert payload["unique_feature_sets"] == [
        {"count": 1, "values": ["gender", "lsat", "ugpa"]}
    ]


def test_prediction_feature_leakage_audit_flags_policy_violations(tmp_path):
    _write_metadata(
        tmp_path,
        "badbad",
        {
            "artifact_id": "badbad",
            "dataset_id": "aif360_lawschool_gpa",
            "feature_names": ["gender", "race", "zfygpa"],
            "preprocessed_feature_names": ["gender", "race", "zfygpa"],
            "feature_drop_columns": ["race"],
            "feature_drop_policy": {"target": "wrong", "primary_group_col": "race"},
            "group_col": "race",
            "model_id": "ridge",
            "seed": 11,
            "target": "zfygpa",
            "target_transform": "identity",
        },
    )

    payload = scan_metadata(
        tmp_path,
        forbidden_features={"zfygpa", "race"},
        required_features={"gender", "lsat", "ugpa"},
        expected_features={"gender", "lsat", "ugpa"},
        expected_drop_columns={"zfygpa", "race"},
        expected_target="zfygpa",
        expected_group_col="race",
        expected_target_transform="identity",
    )

    violation = payload["violations"][0]
    assert payload["violations_count"] == 1
    assert violation["bad_feature_names"] == ["race", "zfygpa"]
    assert violation["bad_preprocessed_feature_names"] == ["race", "zfygpa"]
    assert violation["missing_required_features"] == ["lsat", "ugpa"]
    assert violation["extra_features"] == ["race", "zfygpa"]
    assert violation["missing_expected_drop_columns"] == ["zfygpa"]
    assert violation["target_policy_ok"] is False


def test_prediction_feature_leakage_audit_flags_group_and_transform_policy(tmp_path):
    _write_metadata(
        tmp_path,
        "badgrp",
        {
            "artifact_id": "badgrp",
            "dataset_id": "aif360_lawschool_gpa",
            "feature_names": ["gender", "lsat", "ugpa"],
            "preprocessed_feature_names": ["gender", "lsat", "ugpa"],
            "feature_drop_columns": ["race", "zfygpa"],
            "feature_drop_policy": {"target": "zfygpa", "primary_group_col": "sex"},
            "group_col": "sex",
            "model_id": "ridge",
            "seed": 11,
            "target": "zfygpa",
            "target_transform": "log1p",
        },
    )

    payload = scan_metadata(
        tmp_path,
        forbidden_features={"zfygpa", "race"},
        required_features={"gender", "lsat", "ugpa"},
        expected_features={"gender", "lsat", "ugpa"},
        expected_drop_columns={"zfygpa", "race"},
        expected_target="zfygpa",
        expected_group_col="race",
        expected_target_transform="identity",
    )

    violation = payload["violations"][0]
    assert payload["violations_count"] == 1
    assert violation["group_policy_ok"] is False
    assert violation["target_transform_ok"] is False


def test_prediction_feature_leakage_audit_renders_legacy_metadata_caveat(tmp_path):
    _write_metadata(
        tmp_path,
        "legacy",
        {
            "artifact_id": "legacy",
            "dataset_id": "fairlearn_acs_income_wy",
            "feature_names": ["AGEP", "COW"],
            "model_id": "ridge",
            "seed": 0,
            "target": "PINCP",
            "target_transform": "log1p",
        },
    )

    payload = scan_metadata(
        tmp_path,
        forbidden_features={"PINCP", "SEX"},
        required_features=set(),
        expected_features={"AGEP", "COW"},
        expected_drop_columns=set(),
        expected_target=None,
        expected_group_col=None,
        expected_target_transform="log1p",
    )
    markdown = render_markdown(payload, "Legacy Audit")

    assert payload["metadata_completeness"] == {
        "missing_feature_names": 0,
        "missing_feature_drop_columns": 1,
        "missing_feature_drop_policy": 1,
        "missing_preprocessed_feature_names": 1,
    }
    assert "Some prediction metadata fields are absent" in markdown
    assert "Expected drop columns: not requested" in markdown
    assert "Expected target: `not requested`" in markdown


def test_prediction_feature_leakage_audit_closes_legacy_metadata_with_expected_policy(
    tmp_path,
):
    _write_metadata(
        tmp_path,
        "legacy",
        {
            "artifact_id": "legacy",
            "artifact_schema": "prediction_bundle_v1",
            "dataset_id": "fairlearn_acs_income_wy",
            "feature_names": ["AGEP", "COW"],
            "group_col": "SEX",
            "model_id": "ridge",
            "seed": 0,
            "target": "PINCP",
            "target_transform": "log1p",
        },
    )

    payload = scan_metadata(
        tmp_path,
        forbidden_features={"PINCP", "SEX"},
        required_features={"AGEP", "COW"},
        expected_features={"AGEP", "COW"},
        expected_drop_columns={"PINCP", "SEX"},
        expected_target="PINCP",
        expected_group_col="SEX",
        expected_target_transform="log1p",
        close_missing_preprocessed_feature_names_from_feature_names=True,
        close_missing_drop_metadata_from_expected_policy=True,
    )
    markdown = render_markdown(payload, "Legacy Closed Audit")

    assert payload["metadata_completeness"] == {
        "missing_feature_names": 0,
        "missing_feature_drop_columns": 0,
        "missing_feature_drop_policy": 0,
        "missing_preprocessed_feature_names": 0,
    }
    assert payload["raw_metadata_completeness"] == {
        "missing_feature_names": 0,
        "missing_feature_drop_columns": 1,
        "missing_feature_drop_policy": 1,
        "missing_preprocessed_feature_names": 1,
    }
    assert payload["metadata_closure"][
        "closed_preprocessed_feature_names_from_feature_names"
    ] == 1
    assert payload["metadata_closure"][
        "closed_feature_drop_columns_from_expected_policy"
    ] == 1
    assert payload["metadata_closure"][
        "closed_feature_drop_policy_from_expected_policy"
    ] == 1
    assert payload["violations_count"] == 0
    assert "Raw legacy metadata missingness before explicit closure" in markdown
    assert "checks are closed after applying" in markdown


def test_prediction_feature_leakage_audit_infers_v3_preprocessed_names(tmp_path):
    _write_metadata(
        tmp_path,
        "legacyv3",
        {
            "artifact_id": "legacyv3",
            "artifact_schema": "prediction_bundle_v3",
            "dataset_id": "fairlearn_acs_income_wy",
            "feature_names": ["AGEP", "COW"],
            "feature_drop_columns": ["PINCP", "SEX"],
            "feature_drop_policy": {"target": "PINCP", "primary_group_col": "SEX"},
            "group_col": "SEX",
            "model_id": "ridge",
            "seed": 0,
            "target": "PINCP",
            "target_transform": "log1p",
        },
    )

    payload = scan_metadata(
        tmp_path,
        forbidden_features={"PINCP", "SEX"},
        required_features=set(),
        expected_features={"AGEP", "COW"},
        expected_drop_columns={"PINCP", "SEX"},
        expected_target="PINCP",
        expected_group_col="SEX",
        expected_target_transform="log1p",
    )
    markdown = render_markdown(payload, "Legacy v3 Audit")

    assert payload["metadata_completeness"] == {
        "missing_feature_names": 0,
        "missing_feature_drop_columns": 0,
        "missing_feature_drop_policy": 0,
        "missing_preprocessed_feature_names": 0,
    }
    assert payload["metadata_inference"][
        "preprocessed_feature_names_from_legacy_feature_names"
    ] == 1
    assert payload["unique_preprocessed_feature_sets"] == [
        {"count": 1, "values": ["AGEP", "COW"]}
    ]
    assert payload["violations_count"] == 0
    assert "Legacy preprocessing-output feature names inferred" in markdown


def test_methodology_scan_collects_feature_leakage_sidecars(tmp_path):
    report_dir = tmp_path / "experiments/regression/reports/example"
    report_dir.mkdir(parents=True)
    (report_dir / "feature_leakage_audit.json").write_text(
        json.dumps(
            {
                "schema": "cpfi_prediction_feature_leakage_audit_v1",
                "metadata_files_scanned": 2,
                "violations_count": 1,
                "violations": [{"artifact_id": "bad"}],
            }
        ),
        encoding="utf-8",
    )

    evidence = feature_leakage_sidecar_scan(tmp_path)

    assert evidence["reports_scanned"] == 1
    assert evidence["metadata_files_scanned"] == 2
    assert evidence["violations_count"] == 1
    assert evidence["metadata_completeness_totals"] == {
        "missing_feature_names": 0,
        "missing_feature_drop_columns": 0,
        "missing_feature_drop_policy": 0,
        "missing_preprocessed_feature_names": 0,
    }
    assert evidence["violation_examples"] == [
        {
            "path": (
                "experiments/regression/reports/example/"
                "feature_leakage_audit.json"
            ),
            "violation": {"artifact_id": "bad"},
        }
    ]


def test_methodology_scan_flags_bad_feature_leakage_sidecar_schema(tmp_path):
    report_dir = tmp_path / "experiments/regression/reports/example"
    report_dir.mkdir(parents=True)
    (report_dir / "feature_leakage_audit.json").write_text(
        json.dumps(
            {
                "schema": "unknown",
                "metadata_files_scanned": 0,
                "violations_count": 0,
                "violations": [],
            }
        ),
        encoding="utf-8",
    )

    evidence = feature_leakage_sidecar_scan(tmp_path)

    assert evidence["schema_violations"] == [
        {
            "path": (
                "experiments/regression/reports/example/"
                "feature_leakage_audit.json"
            ),
            "schema": "unknown",
        }
    ]
    assert evidence["empty_reports"] == [
        {
            "path": (
                "experiments/regression/reports/example/"
                "feature_leakage_audit.json"
            ),
            "metadata_files_scanned": 0,
        }
    ]
