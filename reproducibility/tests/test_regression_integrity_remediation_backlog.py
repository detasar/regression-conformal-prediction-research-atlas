import json
from pathlib import Path

from experiments.regression.scripts import audit_methodology_sanity as sanity
from experiments.regression.scripts import build_integrity_remediation_backlog as backlog


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_backlog_expands_cross_run_issues_into_prioritized_actions(tmp_path):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 2,
                "total_completed_rows": 13,
                "blocking_issue_counts": {"feature_leakage_violation_recorded": 1},
                "caveat_counts": {
                    "no_prediction_metadata_feature_leakage_sidecar": 1,
                    "legacy_endpoint_schema_not_full_closure": 1,
                },
            },
            "rows": [
                {
                    "report_id": "report:toy_a",
                    "report_name": "toy_a",
                    "pilot_summary_path": "experiments/regression/reports/toy_a/pilot_summary.json",
                    "config_path": "experiments/regression/configs/toy_a.yaml",
                    "experiment_id": "toy_a_v0",
                    "dataset_ids": ["dataset_a"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 10},
                    "large_sweep": False,
                    "summary_rows": 1,
                    "ledger_rows": 10,
                    "blocking_issues": ["feature_leakage_violation_recorded"],
                    "caveats": ["legacy_endpoint_schema_not_full_closure"],
                    "feature_leakage_audit": {
                        "present": True,
                        "path": "experiments/regression/reports/toy_a/feature_leakage_audit.json",
                    },
                    "endpoint_audit": {
                        "present": True,
                        "path": "experiments/regression/reports/toy_a/endpoint_audit.json",
                    },
                    "split_profile": {"present": False},
                },
                {
                    "report_id": "report:toy_b",
                    "report_name": "toy_b",
                    "pilot_summary_path": "experiments/regression/reports/toy_b/pilot_summary.json",
                    "config_path": "experiments/regression/configs/toy_b.yaml",
                    "experiment_id": "toy_b_v0",
                    "dataset_ids": ["dataset_b"],
                    "cp_methods": ["cqr"],
                    "status_counts": {"completed": 3},
                    "large_sweep": False,
                    "summary_rows": 1,
                    "ledger_rows": 3,
                    "blocking_issues": [],
                    "caveats": ["no_prediction_metadata_feature_leakage_sidecar"],
                    "feature_leakage_audit": {"present": False},
                    "endpoint_audit": {"present": False},
                    "split_profile": {"present": False},
                },
            ],
        },
    )

    payload = backlog.build_payload(tmp_path, cross_run_path)

    assert payload["schema"] == backlog.SCHEMA
    assert payload["summary"]["open_action_count"] == 3
    assert payload["summary"]["severity_counts"] == {"high": 1, "medium": 2}
    assert payload["summary"]["issue_counts_match_cross_run"] is True
    assert payload["rows"][0]["issue_type"] == "feature_leakage_violation_recorded"
    assert payload["rows"][0]["severity"] == "high"
    assert payload["rows"][0]["source_sidecar_paths"] == [
        "experiments/regression/reports/toy_a/feature_leakage_audit.json"
    ]


def test_backlog_markdown_renders_action_queue(tmp_path):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "total_completed_rows": 1,
                "blocking_issue_counts": {},
                "caveat_counts": {"duplicate_signature_cross_split_caveat": 1},
            },
            "rows": [
                {
                    "report_id": "report:toy",
                    "report_name": "toy",
                    "pilot_summary_path": "experiments/regression/reports/toy/pilot_summary.json",
                    "dataset_ids": ["dataset_a"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 1},
                    "large_sweep": False,
                    "summary_rows": 1,
                    "ledger_rows": 1,
                    "blocking_issues": [],
                    "caveats": ["duplicate_signature_cross_split_caveat"],
                    "split_profile": {
                        "present": True,
                        "path": "experiments/regression/reports/toy/split_profile.json",
                    },
                    "endpoint_audit": {"present": False},
                    "feature_leakage_audit": {"present": False},
                }
            ],
        },
    )
    payload = backlog.build_payload(tmp_path, cross_run_path)
    markdown = backlog.render_markdown(payload)

    assert "# Integrity Remediation Backlog" in markdown
    assert "`duplicate_signature_cross_split_caveat`" in markdown
    assert "Run duplicate-aware split" in markdown


def test_plus_family_internal_fold_caveat_is_tracked_not_open(tmp_path):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "total_completed_rows": 17,
                "blocking_issue_counts": {},
                "caveat_counts": {
                    "duplicate_cluster_plus_family_internal_fold_caveat": 1
                },
            },
            "rows": [
                {
                    "report_id": "report:plus_family",
                    "report_name": "duplicate_cluster_sensitivity_demo",
                    "pilot_summary_path": (
                        "experiments/regression/reports/plus_family/"
                        "pilot_summary.json"
                    ),
                    "dataset_ids": ["dataset_a"],
                    "cp_methods": ["cv_plus"],
                    "status_counts": {"completed": 17},
                    "large_sweep": False,
                    "summary_rows": 1,
                    "ledger_rows": 17,
                    "blocking_issues": [],
                    "caveats": [
                        "duplicate_cluster_plus_family_internal_fold_caveat"
                    ],
                    "split_profile": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/plus_family/"
                            "split_profile.json"
                        ),
                    },
                    "endpoint_audit": {"present": True},
                    "feature_leakage_audit": {"present": True},
                }
            ],
        },
    )

    payload = backlog.build_payload(tmp_path, cross_run_path)

    assert payload["summary"]["open_action_count"] == 0
    assert payload["summary"]["covered_action_count"] == 1
    assert payload["summary"]["status_counts"] == {
        "tracked_methodology_caveat": 1
    }
    assert payload["summary"]["issue_counts_match_cross_run"] is True
    assert payload["rows"][0]["status"] == "tracked_methodology_caveat"
    assert payload["rows"][0]["action_category"] == "plus_family_internal_fold_scope"


def test_feature_metadata_completeness_backlog_severity_uses_sidecar_evidence(tmp_path):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 3,
                "total_completed_rows": 6,
                "blocking_issue_counts": {},
                "caveat_counts": {"feature_leakage_metadata_completeness_caveat": 3},
            },
            "rows": [
                {
                    "report_id": "report:preprocessed_only",
                    "report_name": "preprocessed_only",
                    "pilot_summary_path": (
                        "experiments/regression/reports/preprocessed_only/"
                        "pilot_summary.json"
                    ),
                    "dataset_ids": ["dataset_a"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 2},
                    "large_sweep": False,
                    "summary_rows": 1,
                    "ledger_rows": 2,
                    "blocking_issues": [],
                    "caveats": ["feature_leakage_metadata_completeness_caveat"],
                    "split_profile": {"present": False},
                    "endpoint_audit": {"present": False},
                    "feature_leakage_audit": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/preprocessed_only/"
                            "feature_leakage_audit.json"
                        ),
                        "metadata_selection": "ledger_referenced_prediction_artifacts",
                        "violations_count": 0,
                        "metadata_completeness": {
                            "missing_feature_names": 0,
                            "missing_preprocessed_feature_names": 2,
                            "missing_feature_drop_columns": 0,
                            "missing_feature_drop_policy": 0,
                        },
                        "backfill_policy_inference": {
                            "complete_drop_metadata": True,
                            "complete_policy_metadata": True,
                            "exact_drop_set_enforced": True,
                            "exact_feature_set_enforced": True,
                        },
                    },
                },
                {
                    "report_id": "report:drop_policy_missing",
                    "report_name": "drop_policy_missing",
                    "pilot_summary_path": (
                        "experiments/regression/reports/drop_policy_missing/"
                        "pilot_summary.json"
                    ),
                    "dataset_ids": ["dataset_b"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 2},
                    "large_sweep": False,
                    "summary_rows": 1,
                    "ledger_rows": 2,
                    "blocking_issues": [],
                    "caveats": ["feature_leakage_metadata_completeness_caveat"],
                    "split_profile": {"present": False},
                    "endpoint_audit": {"present": False},
                    "feature_leakage_audit": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/drop_policy_missing/"
                            "feature_leakage_audit.json"
                        ),
                        "metadata_selection": "ledger_referenced_prediction_artifacts",
                        "violations_count": 0,
                        "metadata_completeness": {
                            "missing_feature_names": 0,
                            "missing_preprocessed_feature_names": 2,
                            "missing_feature_drop_columns": 2,
                            "missing_feature_drop_policy": 2,
                        },
                        "backfill_policy_inference": {
                            "complete_drop_metadata": False,
                            "complete_policy_metadata": False,
                        },
                    },
                },
                {
                    "report_id": "report:drop_set_not_enforced",
                    "report_name": "drop_set_not_enforced",
                    "pilot_summary_path": (
                        "experiments/regression/reports/drop_set_not_enforced/"
                        "pilot_summary.json"
                    ),
                    "dataset_ids": ["dataset_c"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 2},
                    "large_sweep": False,
                    "summary_rows": 1,
                    "ledger_rows": 2,
                    "blocking_issues": [],
                    "caveats": ["feature_leakage_metadata_completeness_caveat"],
                    "split_profile": {"present": False},
                    "endpoint_audit": {"present": False},
                    "feature_leakage_audit": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/drop_set_not_enforced/"
                            "feature_leakage_audit.json"
                        ),
                        "metadata_selection": "ledger_referenced_prediction_artifacts",
                        "violations_count": 0,
                        "metadata_completeness": {
                            "missing_feature_names": 0,
                            "missing_preprocessed_feature_names": 2,
                            "missing_feature_drop_columns": 0,
                            "missing_feature_drop_policy": 0,
                        },
                        "backfill_policy_inference": {
                            "complete_drop_metadata": True,
                            "complete_policy_metadata": True,
                            "exact_drop_set_enforced": False,
                            "exact_feature_set_enforced": True,
                        },
                    },
                },
            ],
        },
    )

    payload = backlog.build_payload(tmp_path, cross_run_path)

    by_report = {row["report_name"]: row for row in payload["rows"]}
    assert payload["summary"]["issue_counts_match_cross_run"] is True
    assert payload["summary"]["severity_counts"] == {"low": 1, "medium": 2}
    assert payload["summary"]["category_counts"] == {
        "feature_leakage_drop_policy_metadata": 1,
        "feature_leakage_metadata_completeness": 1,
        "feature_leakage_preprocessed_name_closure": 1,
    }
    assert by_report["preprocessed_only"]["severity"] == "low"
    assert by_report["preprocessed_only"]["action_category"] == (
        "feature_leakage_preprocessed_name_closure"
    )
    assert by_report["preprocessed_only"]["evidence"][
        "feature_metadata_completeness_profile"
    ]["bounded_raw_policy_evidence"] is True
    assert by_report["drop_policy_missing"]["severity"] == "medium"
    assert by_report["drop_policy_missing"]["action_category"] == (
        "feature_leakage_drop_policy_metadata"
    )
    assert by_report["drop_set_not_enforced"]["severity"] == "medium"
    assert by_report["drop_set_not_enforced"]["action_category"] == (
        "feature_leakage_metadata_completeness"
    )
    assert by_report["drop_set_not_enforced"]["evidence"][
        "feature_metadata_completeness_profile"
    ]["bounded_raw_policy_evidence"] is False


def test_model_visible_duplicate_caveat_links_completed_sensitivity(tmp_path):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "total_completed_rows": 100,
                "blocking_issue_counts": {},
                "caveat_counts": {"model_visible_signature_cross_split_caveat": 1},
            },
            "rows": [
                {
                    "report_id": "report:baseline_report",
                    "report_name": "baseline_report",
                    "pilot_summary_path": (
                        "experiments/regression/reports/baseline_report/"
                        "pilot_summary.json"
                    ),
                    "dataset_ids": ["toy_dataset"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 100},
                    "large_sweep": True,
                    "summary_rows": 1,
                    "ledger_rows": 100,
                    "blocking_issues": [],
                    "caveats": ["model_visible_signature_cross_split_caveat"],
                    "split_profile": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/baseline_report/"
                            "split_profile.json"
                        ),
                    },
                    "endpoint_audit": {"present": False},
                    "feature_leakage_audit": {"present": False},
                }
            ],
        },
    )
    write_json(
        tmp_path
        / "experiments/regression/reports/baseline_report/split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 1,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                        {
                            "seed": 71,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 1,
                                "cal_test": 0,
                            },
                        },
                    ],
                }
            ],
        },
    )
    sensitivity_dir = (
        tmp_path
        / "experiments/regression/reports/duplicate_cluster_sensitivity_toy"
    )
    write_json(
        sensitivity_dir / "sensitivity_comparison.json",
        {
            "schema": "cpfi_regression_sensitivity_ledger_comparison_v1",
            "baseline": {
                "ledger": (
                    "experiments/regression/results/baseline_report/ledger.jsonl"
                ),
                "seed_filter": [42, 71],
            },
            "sensitivity": {
                "ledger": (
                    "experiments/regression/results/duplicate_cluster_sensitivity_toy/"
                    "ledger.jsonl"
                ),
                "seed_filter": [42, 71],
            },
            "summary": {
                "paired_rows": 10,
                "seed_imbalanced_paired_rows": 0,
                "baseline_only_rows": 0,
                "sensitivity_only_rows": 0,
                "baseline_nominal_count": 6,
                "sensitivity_nominal_count": 5,
                "nominal_status_change_count": 3,
                "coverage_delta_abs": {"mean": 0.02},
            },
        },
    )
    write_json(
        sensitivity_dir / "split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "split_config": {
                "duplicate_cluster_scope": "model_visible_features_plus_target"
            },
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "all_model_visible_feature_plus_target_signature_overlaps_zero": True,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                        {
                            "seed": 71,
                            "all_model_visible_feature_plus_target_signature_overlaps_zero": True,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                    ],
                }
            ],
        },
    )
    write_json(
        sensitivity_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "violations_count": 0,
        },
    )

    payload = backlog.build_payload(tmp_path, cross_run_path)

    assert payload["summary"]["action_count"] == 1
    assert payload["summary"]["open_action_count"] == 0
    assert payload["summary"]["covered_action_count"] == 1
    assert payload["summary"]["status_counts"] == {"covered_by_sensitivity": 1}
    assert payload["summary"]["issue_counts_match_cross_run"] is True
    row = payload["rows"][0]
    assert row["status"] == "covered_by_sensitivity"
    assert row["severity"] == "low"
    assert row["sensitivity_evidence"][0]["report_name"] == (
        "duplicate_cluster_sensitivity_toy"
    )
    assert row["sensitivity_evidence"][0]["paired_rows"] == 10
    assert row["sensitivity_evidence"][0]["seed_imbalanced_paired_rows"] == 0
    assert row["sensitivity_evidence"][0]["required_offending_seeds"] == [42, 71]


def test_model_visible_duplicate_caveat_requires_all_offending_seeds(tmp_path):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "total_completed_rows": 100,
                "blocking_issue_counts": {},
                "caveat_counts": {"model_visible_signature_cross_split_caveat": 1},
            },
            "rows": [
                {
                    "report_id": "report:baseline_report",
                    "report_name": "baseline_report",
                    "pilot_summary_path": (
                        "experiments/regression/reports/baseline_report/"
                        "pilot_summary.json"
                    ),
                    "dataset_ids": ["toy_dataset"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 100},
                    "large_sweep": True,
                    "summary_rows": 1,
                    "ledger_rows": 100,
                    "blocking_issues": [],
                    "caveats": ["model_visible_signature_cross_split_caveat"],
                    "split_profile": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/baseline_report/"
                            "split_profile.json"
                        ),
                    },
                    "endpoint_audit": {"present": False},
                    "feature_leakage_audit": {"present": False},
                }
            ],
        },
    )
    write_json(
        tmp_path
        / "experiments/regression/reports/baseline_report/split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 1,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                        {
                            "seed": 71,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 1,
                                "cal_test": 0,
                            },
                        },
                    ],
                }
            ],
        },
    )
    sensitivity_dir = (
        tmp_path
        / "experiments/regression/reports/duplicate_cluster_sensitivity_toy_partial"
    )
    write_json(
        sensitivity_dir / "sensitivity_comparison.json",
        {
            "schema": "cpfi_regression_sensitivity_ledger_comparison_v1",
            "baseline": {
                "ledger": (
                    "experiments/regression/results/baseline_report/ledger.jsonl"
                ),
                "seed_filter": [42],
            },
            "sensitivity": {
                "ledger": (
                    "experiments/regression/results/"
                    "duplicate_cluster_sensitivity_toy_partial/ledger.jsonl"
                ),
                "seed_filter": [42],
            },
            "summary": {
                "paired_rows": 5,
                "seed_imbalanced_paired_rows": 0,
                "baseline_only_rows": 0,
                "sensitivity_only_rows": 0,
            },
        },
    )
    write_json(
        sensitivity_dir / "split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "split_config": {
                "duplicate_cluster_scope": "model_visible_features_plus_target"
            },
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "all_model_visible_feature_plus_target_signature_overlaps_zero": True,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        }
                    ],
                }
            ],
        },
    )

    payload = backlog.build_payload(tmp_path, cross_run_path)

    assert payload["summary"]["action_count"] == 1
    assert payload["summary"]["open_action_count"] == 1
    assert payload["summary"]["covered_action_count"] == 0
    assert payload["summary"]["status_counts"] == {"open": 1}
    assert payload["rows"][0]["status"] == "open"
    assert payload["rows"][0]["sensitivity_evidence"] == []


def test_model_visible_duplicate_caveat_uses_split_seeds_when_filters_are_empty(
    tmp_path,
):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "total_completed_rows": 100,
                "blocking_issue_counts": {},
                "caveat_counts": {"model_visible_signature_cross_split_caveat": 1},
            },
            "rows": [
                {
                    "report_id": "report:baseline_report",
                    "report_name": "baseline_report",
                    "pilot_summary_path": (
                        "experiments/regression/reports/baseline_report/"
                        "pilot_summary.json"
                    ),
                    "dataset_ids": ["toy_dataset"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 100},
                    "large_sweep": True,
                    "summary_rows": 1,
                    "ledger_rows": 100,
                    "blocking_issues": [],
                    "caveats": ["model_visible_signature_cross_split_caveat"],
                    "split_profile": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/baseline_report/"
                            "split_profile.json"
                        ),
                    },
                    "endpoint_audit": {"present": False},
                    "feature_leakage_audit": {"present": False},
                }
            ],
        },
    )
    write_json(
        tmp_path
        / "experiments/regression/reports/baseline_report/split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 1,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                        {
                            "seed": 71,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 1,
                                "cal_test": 0,
                            },
                        },
                    ],
                }
            ],
        },
    )
    sensitivity_dir = (
        tmp_path
        / "experiments/regression/reports/duplicate_cluster_sensitivity_toy"
    )
    write_json(
        sensitivity_dir / "sensitivity_comparison.json",
        {
            "schema": "cpfi_regression_sensitivity_ledger_comparison_v1",
            "baseline": {
                "ledger": (
                    "experiments/regression/results/baseline_report/ledger.jsonl"
                ),
                "seed_filter": [],
            },
            "sensitivity": {
                "ledger": (
                    "experiments/regression/results/duplicate_cluster_sensitivity_toy/"
                    "ledger.jsonl"
                ),
                "seed_filter": [],
            },
            "summary": {
                "paired_rows": 10,
                "seed_imbalanced_paired_rows": 0,
                "baseline_only_rows": 0,
                "sensitivity_only_rows": 0,
            },
        },
    )
    write_json(
        sensitivity_dir / "split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "split_config": {
                "duplicate_cluster_scope": "model_visible_features_plus_target"
            },
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "all_model_visible_feature_plus_target_signature_overlaps_zero": True,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                        {
                            "seed": 71,
                            "all_model_visible_feature_plus_target_signature_overlaps_zero": True,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                    ],
                }
            ],
        },
    )

    payload = backlog.build_payload(tmp_path, cross_run_path)

    assert payload["summary"]["open_action_count"] == 0
    assert payload["summary"]["covered_action_count"] == 1
    row = payload["rows"][0]
    assert row["status"] == "covered_by_sensitivity"
    assert row["sensitivity_evidence"][0]["required_offending_seeds"] == [42, 71]


def test_grouped_cv_model_visible_caveat_links_ordinary_vs_grouped_comparison(tmp_path):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "total_completed_rows": 188,
                "blocking_issue_counts": {},
                "caveat_counts": {"model_visible_signature_cross_split_caveat": 1},
            },
            "rows": [
                {
                    "report_id": "report:duplicate_cluster_grouped_cv_row",
                    "report_name": "duplicate_cluster_grouped_cv_row",
                    "pilot_summary_path": (
                        "experiments/regression/reports/"
                        "duplicate_cluster_grouped_cv_row/pilot_summary.json"
                    ),
                    "dataset_ids": ["toy_dataset"],
                    "cp_methods": ["cv_plus_grouped", "cv_minmax_grouped"],
                    "status_counts": {"completed": 188},
                    "large_sweep": False,
                    "summary_rows": 94,
                    "ledger_rows": 188,
                    "blocking_issues": [],
                    "caveats": ["model_visible_signature_cross_split_caveat"],
                    "split_profile": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/"
                            "duplicate_cluster_grouped_cv_row/split_profile.json"
                        ),
                    },
                    "endpoint_audit": {"present": True},
                    "feature_leakage_audit": {"present": True},
                }
            ],
        },
    )
    write_json(
        tmp_path
        / "experiments/regression/reports/duplicate_cluster_grouped_cv_row/"
        "split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 1,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                        {
                            "seed": 71,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 1,
                                "cal_test": 0,
                            },
                        },
                    ],
                }
            ],
        },
    )
    sensitivity_dir = (
        tmp_path
        / "experiments/regression/reports/duplicate_cluster_grouped_cv_model_visible"
    )
    write_json(
        sensitivity_dir / "ordinary_vs_grouped_cv_comparison.json",
        {
            "schema": "cpfi_regression_sensitivity_ledger_comparison_v1",
            "baseline": {
                "ledger": (
                    "experiments/regression/results/"
                    "duplicate_cluster_grouped_cv_row/ledger.jsonl"
                ),
                "seed_filter": [42, 71],
            },
            "sensitivity": {
                "ledger": (
                    "experiments/regression/results/"
                    "duplicate_cluster_grouped_cv_model_visible/ledger.jsonl"
                ),
                "seed_filter": [42, 71],
            },
            "summary": {
                "paired_rows": 47,
                "seed_imbalanced_paired_rows": 0,
                "baseline_only_rows": 0,
                "sensitivity_only_rows": 0,
                "baseline_nominal_count": 17,
                "sensitivity_nominal_count": 5,
                "nominal_status_change_count": 6,
                "coverage_delta_abs": {"mean": 0.001},
            },
        },
    )
    write_json(
        sensitivity_dir / "split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "split_config": {
                "duplicate_cluster_scope": "model_visible_features_plus_target"
            },
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "all_model_visible_feature_plus_target_signature_overlaps_zero": True,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                        {
                            "seed": 71,
                            "all_model_visible_feature_plus_target_signature_overlaps_zero": True,
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                    ],
                }
            ],
        },
    )
    write_json(
        sensitivity_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "violations_count": 0,
        },
    )

    payload = backlog.build_payload(tmp_path, cross_run_path)

    assert payload["summary"]["open_action_count"] == 0
    assert payload["summary"]["covered_action_count"] == 1
    row = payload["rows"][0]
    assert row["status"] == "covered_by_sensitivity"
    assert row["sensitivity_evidence"][0]["report_name"] == (
        "duplicate_cluster_grouped_cv_model_visible"
    )
    assert row["sensitivity_evidence"][0]["comparison_path"] == (
        "experiments/regression/reports/"
        "duplicate_cluster_grouped_cv_model_visible/"
        "ordinary_vs_grouped_cv_comparison.json"
    )


def test_full_row_duplicate_caveat_links_row_signature_sensitivity(tmp_path):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "total_completed_rows": 100,
                "blocking_issue_counts": {},
                "caveat_counts": {"duplicate_signature_cross_split_caveat": 1},
            },
            "rows": [
                {
                    "report_id": "report:baseline_report",
                    "report_name": "baseline_report",
                    "pilot_summary_path": (
                        "experiments/regression/reports/baseline_report/"
                        "pilot_summary.json"
                    ),
                    "dataset_ids": ["toy_dataset"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 100},
                    "large_sweep": True,
                    "summary_rows": 1,
                    "ledger_rows": 100,
                    "blocking_issues": [],
                    "caveats": ["duplicate_signature_cross_split_caveat"],
                    "split_profile": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/baseline_report/"
                            "split_profile.json"
                        ),
                    },
                    "endpoint_audit": {"present": False},
                    "feature_leakage_audit": {"present": False},
                }
            ],
        },
    )
    write_json(
        tmp_path
        / "experiments/regression/reports/baseline_report/split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "row_signature_overlaps": {
                                "train_cal": 1,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                        {
                            "seed": 71,
                            "row_signature_overlaps": {
                                "train_cal": 0,
                                "train_test": 1,
                                "cal_test": 0,
                            },
                        },
                    ],
                }
            ],
        },
    )
    sensitivity_dir = (
        tmp_path
        / "experiments/regression/reports/duplicate_cluster_sensitivity_toy_row"
    )
    write_json(
        sensitivity_dir / "sensitivity_comparison.json",
        {
            "schema": "cpfi_regression_sensitivity_ledger_comparison_v1",
            "baseline": {
                "ledger": (
                    "experiments/regression/results/baseline_report/ledger.jsonl"
                ),
                "seed_filter": [42, 71],
            },
            "sensitivity": {
                "ledger": (
                    "experiments/regression/results/"
                    "duplicate_cluster_sensitivity_toy_row/ledger.jsonl"
                ),
                "seed_filter": [42, 71],
            },
            "summary": {
                "paired_rows": 10,
                "seed_imbalanced_paired_rows": 0,
                "baseline_only_rows": 0,
                "sensitivity_only_rows": 0,
                "baseline_nominal_count": 6,
                "sensitivity_nominal_count": 8,
                "nominal_status_change_count": 2,
                "coverage_delta_abs": {"mean": 0.01},
            },
        },
    )
    write_json(
        sensitivity_dir / "split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "split_config": {"duplicate_cluster_scope": "row_signature"},
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "all_row_signature_overlaps_zero": True,
                            "row_signature_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                        {
                            "seed": 71,
                            "all_row_signature_overlaps_zero": True,
                            "row_signature_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                    ],
                }
            ],
        },
    )
    write_json(
        sensitivity_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "violations_count": 0,
        },
    )

    payload = backlog.build_payload(tmp_path, cross_run_path)

    assert payload["summary"]["action_count"] == 1
    assert payload["summary"]["open_action_count"] == 0
    assert payload["summary"]["covered_action_count"] == 1
    assert payload["summary"]["status_counts"] == {"covered_by_sensitivity": 1}
    row = payload["rows"][0]
    assert row["status"] == "covered_by_sensitivity"
    assert row["severity"] == "low"
    assert row["action_category"] == "duplicate_sensitivity"
    assert row["sensitivity_evidence"][0]["status"] == (
        "completed_row_signature_duplicate_cluster_sensitivity"
    )
    assert row["sensitivity_evidence"][0]["report_name"] == (
        "duplicate_cluster_sensitivity_toy_row"
    )
    assert row["sensitivity_evidence"][0]["required_offending_seeds"] == [42, 71]


def test_full_row_duplicate_caveat_requires_all_offending_seeds(tmp_path):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "total_completed_rows": 100,
                "blocking_issue_counts": {},
                "caveat_counts": {"duplicate_signature_cross_split_caveat": 1},
            },
            "rows": [
                {
                    "report_id": "report:baseline_report",
                    "report_name": "baseline_report",
                    "pilot_summary_path": (
                        "experiments/regression/reports/baseline_report/"
                        "pilot_summary.json"
                    ),
                    "dataset_ids": ["toy_dataset"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 100},
                    "large_sweep": True,
                    "summary_rows": 1,
                    "ledger_rows": 100,
                    "blocking_issues": [],
                    "caveats": ["duplicate_signature_cross_split_caveat"],
                    "split_profile": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/baseline_report/"
                            "split_profile.json"
                        ),
                    },
                    "endpoint_audit": {"present": False},
                    "feature_leakage_audit": {"present": False},
                }
            ],
        },
    )
    write_json(
        tmp_path
        / "experiments/regression/reports/baseline_report/split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "row_signature_overlaps": {
                                "train_cal": 1,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        },
                        {
                            "seed": 71,
                            "row_signature_overlaps": {
                                "train_cal": 0,
                                "train_test": 1,
                                "cal_test": 0,
                            },
                        },
                    ],
                }
            ],
        },
    )
    sensitivity_dir = (
        tmp_path
        / "experiments/regression/reports/duplicate_cluster_sensitivity_toy_row_partial"
    )
    write_json(
        sensitivity_dir / "sensitivity_comparison.json",
        {
            "schema": "cpfi_regression_sensitivity_ledger_comparison_v1",
            "baseline": {
                "ledger": (
                    "experiments/regression/results/baseline_report/ledger.jsonl"
                ),
                "seed_filter": [42],
            },
            "sensitivity": {
                "ledger": (
                    "experiments/regression/results/"
                    "duplicate_cluster_sensitivity_toy_row_partial/ledger.jsonl"
                ),
                "seed_filter": [42],
            },
            "summary": {
                "paired_rows": 5,
                "seed_imbalanced_paired_rows": 0,
                "baseline_only_rows": 0,
                "sensitivity_only_rows": 0,
            },
        },
    )
    write_json(
        sensitivity_dir / "split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "split_config": {"duplicate_cluster_scope": "row_signature"},
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "seeds": [
                        {
                            "seed": 42,
                            "all_row_signature_overlaps_zero": True,
                            "row_signature_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                        }
                    ],
                }
            ],
        },
    )

    payload = backlog.build_payload(tmp_path, cross_run_path)

    assert payload["summary"]["action_count"] == 1
    assert payload["summary"]["open_action_count"] == 1
    assert payload["summary"]["covered_action_count"] == 0
    assert payload["summary"]["status_counts"] == {"open": 1}
    assert payload["rows"][0]["status"] == "open"
    assert payload["rows"][0]["sensitivity_evidence"] == []


def test_main_result_candidate_duplicate_caveat_is_tracked_diagnostic(tmp_path):
    cross_run_path = tmp_path / "cross_run_integrity_audit.json"
    write_json(
        cross_run_path,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "total_completed_rows": 45,
                "blocking_issue_counts": {},
                "caveat_counts": {"duplicate_signature_cross_split_caveat": 1},
            },
            "rows": [
                {
                    "report_id": "report:main_result_candidate_bundle_demo",
                    "report_name": "main_result_candidate_bundle_demo",
                    "pilot_summary_path": (
                        "experiments/regression/reports/"
                        "main_result_candidate_bundle_demo/pilot_summary.json"
                    ),
                    "dataset_ids": ["demo_dataset"],
                    "cp_methods": ["cqr", "cv_plus", "mondrian_abs"],
                    "status_counts": {"completed": 45},
                    "large_sweep": False,
                    "summary_rows": 45,
                    "ledger_rows": 45,
                    "blocking_issues": [],
                    "caveats": ["duplicate_signature_cross_split_caveat"],
                    "split_profile": {
                        "present": True,
                        "schema": "cpfi_regression_split_profile_v2",
                        "row_id_overlap_violations": 0,
                        "split_group_overlap_violations": 0,
                    },
                    "endpoint_audit": {"present": True},
                    "feature_leakage_audit": {
                        "present": True,
                        "violations_count": 0,
                    },
                }
            ],
        },
    )

    payload = backlog.build_payload(tmp_path, cross_run_path)

    assert payload["summary"]["action_count"] == 1
    assert payload["summary"]["open_action_count"] == 0
    assert payload["summary"]["status_counts"] == {
        "tracked_diagnostic_caveat": 1
    }
    row = payload["rows"][0]
    assert row["status"] == "tracked_diagnostic_caveat"
    assert row["severity"] == "low"
    assert row["sensitivity_evidence"] == []
    assert "diagnostic-only" in row["recommended_next_action"]
    assert "seed-matched duplicate-aware sensitivity" in row["recommended_next_action"]


def test_methodology_status_accepts_synchronized_remediation_backlog(tmp_path):
    write_json(
        tmp_path / sanity.CROSS_RUN_INTEGRITY_AUDIT,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "risk_counts": {"medium": 1},
                "blocking_issue_counts": {},
                "caveat_counts": {"no_prediction_metadata_feature_leakage_sidecar": 1},
                "unsupported_claim_hits": 0,
                "leakage_status": "hard_leakage_not_detected_in_scanned_artifacts",
            },
            "rows": [
                {
                    "report_id": "report:toy",
                    "report_name": "toy",
                    "pilot_summary_path": "experiments/regression/reports/toy/pilot_summary.json",
                    "dataset_ids": ["dataset_a"],
                    "cp_methods": ["split_abs"],
                    "status_counts": {"completed": 1},
                    "large_sweep": False,
                    "summary_rows": 1,
                    "ledger_rows": 1,
                    "blocking_issues": [],
                    "caveats": ["no_prediction_metadata_feature_leakage_sidecar"],
                    "split_profile": {"present": False},
                    "endpoint_audit": {"present": False},
                    "feature_leakage_audit": {"present": False},
                }
            ],
        },
    )
    payload = backlog.build_payload(tmp_path, tmp_path / sanity.CROSS_RUN_INTEGRITY_AUDIT)
    write_json(tmp_path / sanity.INTEGRITY_REMEDIATION_BACKLOG, payload)

    status = sanity.integrity_remediation_backlog_status(tmp_path)

    assert status["synchronized"] is True
    assert status["actual_open_action_count"] == 1
    assert status["expected_issue_counts"] == {
        "no_prediction_metadata_feature_leakage_sidecar": 1
    }


def test_rel_accepts_external_probe_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_path = repo_root / "experiments/regression/reports/backlog.json"
    external_path = tmp_path / "scratch/backlog.json"

    assert backlog.rel(repo_path, repo_root) == "experiments/regression/reports/backlog.json"
    assert backlog.rel(external_path, repo_root) == str(external_path)
