import json
from pathlib import Path

from experiments.regression.scripts import audit_cross_run_integrity as audit
from experiments.regression.scripts import audit_methodology_sanity as sanity


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_unsupported_claim_scan_skips_generated_knowledge_graph(tmp_path):
    kg_path = tmp_path / "experiments/regression/catalogs/knowledge_graph.json"
    write_json(
        kg_path,
        {
            "nodes": [
                {
                    "id": "paper_gate:venn_abers_regression_validation_gate",
                    "closure_standard": (
                        "Validated Venn-Abers regression needs a dedicated "
                        "methodology protocol."
                    ),
                }
            ]
        },
    )

    assert sanity.unsupported_claim_scan(tmp_path) == []

    readme = tmp_path / "experiments/regression/README.md"
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(
        "This study provides validated Venn-Abers regression for all datasets.\n",
        encoding="utf-8",
    )

    hits = sanity.unsupported_claim_scan(tmp_path)

    assert len(hits) == 1
    assert hits[0]["path"] == "experiments/regression/README.md"


def test_unsupported_claim_scan_covers_manuscript_artifacts(tmp_path):
    draft = tmp_path / "experiments/regression/manuscript/draft_claims.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(
        "This experiment is ready for final model selection.\n",
        encoding="utf-8",
    )

    hits = sanity.unsupported_claim_scan(tmp_path)

    assert len(hits) == 1
    assert hits[0]["path"] == "experiments/regression/manuscript/draft_claims.md"


def test_split_summary_reads_v2_and_legacy_overlap_shapes(tmp_path):
    v2_path = tmp_path / "experiments/regression/reports/v2/split_profile.json"
    write_json(
        v2_path,
        {
            "schema": "cpfi_regression_split_profile_v2",
            "dataset_ids": ["toy"],
            "profiles": [
                {
                    "dataset_id": "toy",
                    "split_group_col": "batch",
                    "seeds": [
                        {
                            "seed": 11,
                            "row_id_overlaps": {
                                "train_cal": 1,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                            "split_group_overlaps": {
                                "train_cal": 0,
                                "train_test": 2,
                                "cal_test": 0,
                            },
                            "row_signature_overlaps": {
                                "train_cal": 3,
                                "train_test": 0,
                                "cal_test": 4,
                            },
                            "model_visible_feature_signature_cross_split_overlaps": {
                                "train_cal": 2,
                                "train_test": 0,
                                "cal_test": 0,
                            },
                            "model_visible_feature_plus_target_signature_cross_split_overlaps": {
                                "train_cal": 0,
                                "train_test": 0,
                                "cal_test": 1,
                            },
                        }
                    ],
                }
            ],
        },
    )

    legacy_path = tmp_path / "experiments/regression/reports/legacy/split_profile.json"
    write_json(
        legacy_path,
        {
            "artifact_schema": "dataset_specific_split_profile_v1",
            "dataset_id": "legacy_toy",
            "seed_profiles": [
                {
                    "seed": 11,
                    "split_group_allocations": {
                        "train": ["a", "b"],
                        "cal": ["b"],
                        "test": ["c"],
                    },
                    "full_row_signature_cross_split_overlaps": {
                        "train_cal": 5,
                        "train_test": 0,
                        "cal_test": 0,
                    },
                    "model_visible_feature_signature_cross_split_overlaps": {
                        "train_cal": 1,
                        "train_test": 2,
                        "cal_test": 0,
                    },
                }
            ],
        },
    )

    v2 = audit.summarize_split_profile(v2_path, tmp_path)
    legacy = audit.summarize_split_profile(legacy_path, tmp_path)

    assert v2["row_id_overlap_violations"] == 1
    assert v2["split_group_overlap_violations"] == 1
    assert v2["duplicate_signature_warnings"] == 1
    assert v2["duplicate_signature_pair_overlaps"] == 7
    assert v2["model_visible_feature_signature_warnings"] == 1
    assert v2["model_visible_feature_signature_pair_overlaps"] == 2
    assert v2["model_visible_feature_plus_target_signature_warnings"] == 1
    assert v2["model_visible_feature_plus_target_signature_pair_overlaps"] == 1
    assert v2["model_visible_signature_warnings"] == 1
    assert v2["model_visible_signature_pair_overlaps"] == 1
    assert legacy["split_group_overlap_violations"] == 1
    assert legacy["duplicate_signature_pair_overlaps"] == 5
    assert legacy["model_visible_feature_signature_pair_overlaps"] == 3
    assert legacy["model_visible_signature_pair_overlaps"] == 0


def test_cross_run_audit_escalates_feature_leakage_violations(tmp_path):
    report_dir = tmp_path / "experiments/regression/reports/model_family_sweep_toy"
    config_path = tmp_path / "experiments/regression/configs/model_family_sweep_toy.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "experiment_id: regression_model_family_sweep_toy_v0",
                "datasets: [toy_dataset]",
                "cp_methods: [split_abs, cqr]",
                "quality_controls:",
                "  require_atomic_checkpoints: true",
                "  require_prediction_bundle_cache: true",
                "  require_dataset_audit: true",
                "  require_model_params_summary_key: true",
                "  interpret_rankings_as_triage_only: true",
                "  interpret_cqr_as_fixed_quantile_backend: true",
            ]
        ),
        encoding="utf-8",
    )
    write_json(
        report_dir / "pilot_summary.json",
        {
            "metadata": {
                "status_counts": {"completed": 2},
                "ledger_rows": 2,
                "unique_run_rows": 2,
                "dataset_counts": {"toy_dataset": 2},
            },
            "rows": [
                {"dataset_id": "toy_dataset", "cp_method": "split_abs"},
                {"dataset_id": "toy_dataset", "cp_method": "cqr"},
            ],
            "candidate_frontier_rows": [],
        },
    )
    write_json(
        report_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "metadata_files_scanned": 1,
            "violations_count": 1,
            "metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 0,
                "missing_feature_drop_columns": 0,
                "missing_feature_drop_policy": 0,
            },
        },
    )

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["reports_scanned"] == 1
    assert payload["summary"]["risk_counts"] == {"high": 1}
    assert payload["summary"]["blocking_issue_counts"] == {
        "feature_leakage_violation_recorded": 1
    }
    assert payload["rows"][0]["risk_level"] == "high"
    assert payload["rows"][0]["blocking_issues"] == [
        "feature_leakage_violation_recorded"
    ]


def test_cross_run_audit_propagates_feature_leakage_provenance(tmp_path):
    report_dir = tmp_path / "experiments/regression/reports/model_family_sweep_toy"
    config_path = tmp_path / "experiments/regression/configs/model_family_sweep_toy.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "experiment_id: regression_model_family_sweep_toy_v0",
                "datasets: [toy_dataset]",
                "cp_methods: [split_abs]",
                "quality_controls:",
                "  require_atomic_checkpoints: true",
                "  require_prediction_bundle_cache: true",
                "  require_dataset_audit: true",
                "  require_model_params_summary_key: true",
                "  interpret_rankings_as_triage_only: true",
            ]
        ),
        encoding="utf-8",
    )
    write_json(
        report_dir / "pilot_summary.json",
        {
            "metadata": {
                "status_counts": {"completed": 2},
                "ledger_rows": 2,
                "unique_run_rows": 2,
                "dataset_counts": {"toy_dataset": 2},
            },
            "rows": [{"dataset_id": "toy_dataset", "cp_method": "split_abs"}],
            "candidate_frontier_rows": [],
        },
    )
    write_json(
        report_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "source_backlog_action_id": (
                "model_family_sweep_toy:caveat:"
                "no_prediction_metadata_feature_leakage_sidecar"
            ),
            "source_cross_run_report_id": "report:model_family_sweep_toy",
            "metadata_selection": "ledger_referenced_prediction_artifacts",
            "metadata_files_scanned": 2,
            "violations_count": 0,
            "metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 1,
                "missing_feature_drop_columns": 0,
                "missing_feature_drop_policy": 0,
            },
            "backfill_policy_inference": {
                "complete_drop_metadata": True,
                "complete_policy_metadata": True,
                "exact_feature_set_enforced": True,
                "exact_drop_set_enforced": True,
                "metadata_files_scanned": 2,
            },
        },
    )

    payload = audit.build_payload(tmp_path)
    feature = payload["rows"][0]["feature_leakage_audit"]

    assert feature["metadata_selection"] == "ledger_referenced_prediction_artifacts"
    assert (
        feature["source_backlog_action_id"]
        == "model_family_sweep_toy:caveat:no_prediction_metadata_feature_leakage_sidecar"
    )
    assert feature["source_cross_run_report_id"] == "report:model_family_sweep_toy"
    assert feature["backfill_policy_inference"]["exact_feature_set_enforced"] is True
    assert payload["summary"]["feature_metadata_selection_counts"] == {
        "ledger_referenced_prediction_artifacts": 1
    }
    assert payload["summary"]["feature_policy_inference_counts"] == {
        "complete_drop_and_policy_metadata": 1
    }


def test_cross_run_audit_accepts_config_derived_metadata_closure(tmp_path):
    report_dir = tmp_path / "experiments/regression/reports/model_family_sweep_toy"
    config_path = tmp_path / "experiments/regression/configs/model_family_sweep_toy.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "experiment_id: regression_model_family_sweep_toy_v0",
                "datasets: [toy_dataset]",
                "cp_methods: [split_abs]",
                "quality_controls:",
                "  require_atomic_checkpoints: true",
                "  require_prediction_bundle_cache: true",
                "  require_dataset_audit: true",
                "  require_model_params_summary_key: true",
                "  interpret_rankings_as_triage_only: true",
            ]
        ),
        encoding="utf-8",
    )
    write_json(
        report_dir / "pilot_summary.json",
        {
            "metadata": {
                "status_counts": {"completed": 2},
                "ledger_rows": 2,
                "unique_run_rows": 2,
                "dataset_counts": {"toy_dataset": 2},
            },
            "rows": [{"dataset_id": "toy_dataset", "cp_method": "split_abs"}],
            "candidate_frontier_rows": [],
        },
    )
    write_json(
        report_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "metadata_files_scanned": 2,
            "violations_count": 0,
            "metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 0,
                "missing_feature_drop_columns": 0,
                "missing_feature_drop_policy": 0,
            },
            "raw_metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 2,
                "missing_feature_drop_columns": 2,
                "missing_feature_drop_policy": 2,
            },
            "metadata_closure": {
                "enabled": True,
                "closed_preprocessed_feature_names_from_feature_names": 2,
                "closed_feature_drop_columns_from_expected_policy": 2,
                "closed_feature_drop_policy_from_expected_policy": 2,
            },
        },
    )

    payload = audit.build_payload(tmp_path)
    row = payload["rows"][0]

    assert row["risk_level"] == "pass"
    assert row["caveats"] == []
    assert row["feature_leakage_audit"]["raw_metadata_completeness"][
        "missing_feature_drop_policy"
    ] == 2
    assert payload["summary"]["feature_policy_inference_counts"] == {
        "config_derived_metadata_closure": 1
    }


def test_cross_run_audit_marks_legacy_endpoint_schema_as_caveat(tmp_path):
    report_dir = tmp_path / "experiments/regression/reports/model_family_sweep_toy"
    config_path = tmp_path / "experiments/regression/configs/model_family_sweep_toy.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "experiment_id: regression_model_family_sweep_toy_v0",
                "datasets: [toy_dataset]",
                "cp_methods: [split_abs]",
                "quality_controls:",
                "  require_atomic_checkpoints: true",
                "  require_prediction_bundle_cache: true",
                "  require_dataset_audit: true",
                "  require_model_params_summary_key: true",
                "  interpret_rankings_as_triage_only: true",
            ]
        ),
        encoding="utf-8",
    )
    write_json(
        report_dir / "pilot_summary.json",
        {
            "metadata": {
                "status_counts": {"completed": 800},
                "ledger_rows": 800,
                "unique_run_rows": 800,
                "dataset_counts": {"toy_dataset": 800},
            },
            "rows": [{"dataset_id": "toy_dataset", "cp_method": "split_abs"}],
            "candidate_frontier_rows": [],
        },
    )
    write_json(
        report_dir / "split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "dataset_ids": ["toy_dataset"],
            "profiles": [
                {
                    "dataset_id": "toy_dataset",
                    "split_group_col": None,
                    "seeds": [
                        {
                            "seed": 11,
                            "row_id_overlaps": {},
                            "split_group_overlaps": {},
                            "row_signature_overlaps": {},
                        }
                    ],
                }
            ],
        },
    )
    write_json(
        report_dir / "endpoint_audit.json",
        {
            "audit_schema": "cpfi_regression_bounded_ordinal_endpoint_audit_v1",
            "run_count": 800,
        },
    )

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["blocking_issue_counts"] == {}
    assert payload["summary"]["caveat_counts"][
        "legacy_endpoint_schema_not_full_closure"
    ] == 1
    assert payload["rows"][0]["risk_level"] == "medium"


def test_endpoint_audit_summary_accepts_integer_missing_artifacts(tmp_path):
    endpoint_path = tmp_path / "experiments/regression/reports/toy/endpoint_audit.json"
    write_json(
        endpoint_path,
        {
            "audit_schema": "cpfi_regression_endpoint_audit_v2",
            "method_filter": {"full_method_coverage": True},
            "completed_ledger_rows": 12,
            "reconstructed_runs": 12,
            "reconstruction_failures": 0,
            "failure_count_total": 0,
            "missing_artifacts": 0,
        },
    )

    endpoint = audit.summarize_endpoint_audit(endpoint_path, tmp_path)

    assert endpoint["schema"] == "cpfi_regression_endpoint_audit_v2"
    assert endpoint["full_method_coverage"] is True
    assert endpoint["missing_artifacts_count"] == 0
    assert audit.endpoint_integrity_problem(endpoint) is False


def test_cross_run_audit_flags_duplicate_cluster_plus_family_internal_fold_caveat(tmp_path):
    report_dir = (
        tmp_path
        / "experiments/regression/reports/duplicate_cluster_sensitivity_toy_row_signature"
    )
    config_path = (
        tmp_path
        / "experiments/regression/configs/duplicate_cluster_sensitivity_toy_row_signature.yaml"
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "experiment_id: regression_duplicate_cluster_sensitivity_toy_row_signature_v0",
                "datasets: [toy_dataset]",
                "cp_methods: [split_abs, cv_plus]",
                "quality_controls:",
                "  require_atomic_checkpoints: true",
                "  require_prediction_bundle_cache: true",
                "  require_dataset_audit: true",
                "  require_model_params_summary_key: true",
                "  interpret_rankings_as_triage_only: true",
            ]
        ),
        encoding="utf-8",
    )
    write_json(
        report_dir / "pilot_summary.json",
        {
            "metadata": {
                "status_counts": {"completed": 2},
                "ledger_rows": 2,
                "unique_run_rows": 2,
                "dataset_counts": {"toy_dataset": 2},
            },
            "rows": [
                {"dataset_id": "toy_dataset", "cp_method": "split_abs"},
                {"dataset_id": "toy_dataset", "cp_method": "cv_plus"},
            ],
        },
    )

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["caveat_counts"][
        "duplicate_cluster_plus_family_internal_fold_caveat"
    ] == 1
    assert (
        "duplicate_cluster_plus_family_internal_fold_caveat"
        in payload["rows"][0]["caveats"]
    )
    assert payload["rows"][0]["risk_level"] == "medium"


def _grouped_cv_metadata(method: str, *, split_violation: bool = False) -> dict:
    base_method = {
        "cv_plus_grouped": "cv_plus",
        "cv_minmax_grouped": "cv_minmax",
    }[method]
    return {
        "method": method,
        "base_method": base_method,
        "grouped_variant_role": "split_group_preserving_internal_cv",
        "internal_resampling_unit": "split_group",
        "internal_fold_assignment": "seeded_greedy_group_kfold",
        "n_internal_groups": 4,
        "internal_fold_row_counts": [4, 4],
        "internal_fold_group_counts": [2, 2],
        "min_internal_fold_rows": 4,
        "max_internal_fold_rows": 4,
        "min_internal_fold_groups": 2,
        "max_internal_fold_groups": 2,
        "groups_split_across_internal_folds": split_violation,
    }


def _write_grouped_cv_cross_run_fixture(
    root: Path,
    *,
    split_violation: bool = False,
) -> None:
    report_name = "duplicate_cluster_sensitivity_toy_grouped"
    report_dir = root / f"experiments/regression/reports/{report_name}"
    config_path = root / f"experiments/regression/configs/{report_name}.yaml"
    ledger_path = root / f"experiments/regression/results/{report_name}/ledger.jsonl"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "experiment_id: regression_duplicate_cluster_sensitivity_toy_grouped_v0",
                "datasets: [toy_dataset]",
                "cp_methods: [cv_plus_grouped, cv_minmax_grouped]",
                "conformal:",
                "  cv_plus_folds: 2",
                "quality_controls:",
                "  require_atomic_checkpoints: true",
                "  require_prediction_bundle_cache: true",
                "  require_dataset_audit: true",
                "  require_model_params_summary_key: true",
                "  interpret_rankings_as_triage_only: true",
            ]
        ),
        encoding="utf-8",
    )
    write_json(
        report_dir / "pilot_summary.json",
        {
            "ledger": str(ledger_path.relative_to(root)),
            "metadata": {
                "status_counts": {"completed": 2},
                "ledger_rows": 2,
                "unique_run_rows": 2,
                "dataset_counts": {"toy_dataset": 2},
            },
            "rows": [
                {
                    "dataset_id": "toy_dataset",
                    "cp_method": "cv_plus_grouped",
                    "coverage_count": 1,
                },
                {
                    "dataset_id": "toy_dataset",
                    "cp_method": "cv_minmax_grouped",
                    "coverage_count": 1,
                },
            ],
        },
    )
    write_json(
        report_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "metadata_files_scanned": 2,
            "violations_count": 0,
            "metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 0,
                "missing_feature_drop_columns": 0,
                "missing_feature_drop_policy": 0,
            },
        },
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "run_id": "run-cv-plus-grouped",
            "status": "completed",
            "dataset_id": "toy_dataset",
            "model_family": "linear",
            "model_id": "ridge",
            "model_params": {"alpha": 1.0},
            "cp_method": "cv_plus_grouped",
            "cp_method_params": {},
            "alpha": 0.1,
            "seed": 11,
            "cp_metadata": _grouped_cv_metadata(
                "cv_plus_grouped",
                split_violation=split_violation,
            ),
        },
        {
            "run_id": "run-cv-minmax-grouped",
            "status": "completed",
            "dataset_id": "toy_dataset",
            "model_family": "linear",
            "model_id": "ridge",
            "model_params": {"alpha": 1.0},
            "cp_method": "cv_minmax_grouped",
            "cp_method_params": {},
            "alpha": 0.1,
            "seed": 11,
            "cp_metadata": _grouped_cv_metadata("cv_minmax_grouped"),
        },
    ]
    ledger_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_cross_run_audit_accepts_grouped_cv_metadata_evidence(tmp_path):
    _write_grouped_cv_cross_run_fixture(tmp_path)

    payload = audit.build_payload(tmp_path)
    row = payload["rows"][0]

    assert payload["summary"]["grouped_cv_audit_reports"] == 1
    assert payload["summary"]["grouped_cv_metadata_failure_rows"] == 0
    assert row["grouped_cv_audit"]["completed_rows_scanned"] == 2
    assert row["grouped_cv_audit"]["failure_count"] == 0
    assert "duplicate_cluster_plus_family_internal_fold_caveat" not in row["caveats"]
    assert row["blocking_issues"] == []
    assert row["risk_level"] == "pass"


def test_cross_run_audit_matches_post_selection_bridge_config_alias(tmp_path):
    report_name = "method_selection_post_selection_validation_toy_dataset"
    report_dir = tmp_path / f"experiments/regression/reports/{report_name}"
    config_path = (
        tmp_path
        / "experiments/regression/configs/"
        "method_selection_post_selection_validation_bridge_toy_dataset.yaml"
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "experiment_id: regression_dataset_final_gate_post_selection_validation_bridge_toy_dataset_v1",
                "datasets: [toy_dataset]",
                "cp_methods: [split_abs]",
                "quality_controls:",
                "  dataset_final_gate_post_selection_validation_bridge: true",
                "  post_selection_validation_only_no_final_selection: true",
                "logging:",
                f"  ledger: experiments/regression/results/{report_name}/ledger.jsonl",
            ]
        ),
        encoding="utf-8",
    )
    write_json(
        report_dir / "pilot_summary.json",
        {
            "metadata": {
                "status_counts": {"completed": 1},
                "ledger_rows": 1,
                "unique_run_rows": 1,
                "dataset_counts": {"toy_dataset": 1},
            },
            "rows": [{"dataset_id": "toy_dataset", "cp_method": "split_abs"}],
        },
    )
    write_json(
        report_dir / "feature_leakage_audit.json",
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "metadata_files_scanned": 1,
            "violations_count": 0,
            "metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 0,
                "missing_feature_drop_columns": 0,
                "missing_feature_drop_policy": 0,
            },
        },
    )

    payload = audit.build_payload(tmp_path)
    row = payload["rows"][0]

    assert row["report_name"] == report_name
    assert row["config_path"] == str(config_path.relative_to(tmp_path))
    assert "config_not_matched_by_report_directory" not in row["caveats"]
    assert row["risk_level"] == "pass"


def test_cross_run_audit_blocks_invalid_grouped_cv_metadata(tmp_path):
    _write_grouped_cv_cross_run_fixture(tmp_path, split_violation=True)

    payload = audit.build_payload(tmp_path)
    row = payload["rows"][0]

    assert payload["summary"]["grouped_cv_metadata_failure_rows"] == 1
    assert "grouped_cv_internal_fold_metadata_invalid" in row["blocking_issues"]
    assert row["grouped_cv_audit"]["failure_examples"][0]["failures"] == [
        "groups_split_across_internal_folds_not_false"
    ]
    assert row["risk_level"] == "high"


def test_methodology_status_accepts_synchronized_cross_run_audit(tmp_path):
    pilot_path = (
        tmp_path
        / "experiments/regression/reports/model_family_sweep_toy/pilot_summary.json"
    )
    write_json(
        pilot_path,
        {
            "metadata": {"status_counts": {"completed": 1}},
            "rows": [{"dataset_id": "toy_dataset", "cp_method": "split_abs"}],
        },
    )
    write_json(
        tmp_path / sanity.CROSS_RUN_INTEGRITY_AUDIT,
        {
            "schema": "cpfi_cross_run_integrity_audit_v1",
            "summary": {
                "reports_scanned": 1,
                "risk_counts": {"pass": 1},
                "blocking_issue_counts": {},
                "caveat_counts": {},
                "unsupported_claim_hits": 0,
                "leakage_status": "hard_leakage_not_detected_in_scanned_artifacts",
            },
        },
    )

    status = sanity.cross_run_integrity_audit_status(tmp_path, [pilot_path])

    assert status["synchronized"] is True
    assert status["expected_report_count"] == 1
    assert status["actual_report_count"] == 1
    assert status["blocking_issue_counts"] == {}


def test_rel_accepts_external_probe_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_path = repo_root / "experiments/regression/reports/audit.json"
    external_path = tmp_path / "scratch/audit.json"

    assert audit.rel(repo_path, repo_root) == "experiments/regression/reports/audit.json"
    assert audit.rel(external_path, repo_root) == str(external_path)


def test_methodology_rel_accepts_external_probe_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_path = repo_root / "experiments/regression/reports/sanity.json"
    external_path = tmp_path / "scratch/sanity.json"

    assert sanity.rel(repo_path, repo_root) == "experiments/regression/reports/sanity.json"
    assert sanity.rel(external_path, repo_root) == str(external_path)
