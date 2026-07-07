from experiments.regression.scripts import audit_retrospective_methodology_controls as audit


def control_by_id(payload):
    return {row["control_id"]: row for row in payload}


def base_cross_run_payload():
    return {
        "schema": "cpfi_cross_run_integrity_audit_v1",
        "summary": {
            "reports_scanned": 1,
            "configs_scanned": 1,
            "total_completed_rows": 10,
            "blocking_issue_counts": {},
            "caveat_counts": {},
            "unsupported_claim_hits": 0,
            "feature_metadata_selection_counts": {},
            "feature_policy_inference_counts": {},
        },
        "study_level_layers": {
            "split_profile_integrity_scan": {
                "row_id_overlap_violations": 0,
                "split_group_overlap_violations": 0,
                "duplicate_signature_warnings": 0,
                "total_duplicate_signature_pair_overlaps": 0,
            },
            "feature_leakage_sidecar_scan": {"violations_count": 0},
            "runner_feature_drop_guard_scan": {
                "runner_path": "experiments/regression/scripts/run_regression_pilot.py",
                "fit_block_found": True,
                "drops_target_before_preprocessing": True,
                "drops_primary_group_when_present": True,
                "drops_split_group_when_present": True,
                "deduplicates_feature_drop_columns": True,
            },
            "config_loader_leakage_policy_scan": {
                "dataset_refs_scanned": 1,
                "unknown_dataset_refs": [],
                "missing_loader_target_or_group": [],
                "model_family_extra_target_boundary_missing": [],
                "legacy_extra_target_boundary_weak": [],
                "model_family_derived_group_source_policy_missing": [],
                "legacy_derived_group_source_policy_weak": [],
            },
        },
        "rows": [
            {
                "report_id": "report:toy",
                "report_name": "toy",
                "status_counts": {"completed": 10},
                "blocking_issues": [],
                "caveats": [],
                "split_profile": {
                    "present": True,
                    "schema": "cpfi_regression_split_profile_v2",
                },
                "endpoint_audit": {
                    "present": True,
                    "schema": "cpfi_regression_endpoint_audit_v2",
                    "full_method_coverage": True,
                },
                "feature_leakage_audit": {
                    "present": True,
                    "violations_count": 0,
                    "missing_metadata_field_total": 0,
                },
            }
        ],
    }


def test_retrospective_controls_escalate_hard_leakage_and_endpoint_failures():
    cross_payload = base_cross_run_payload()
    cross_payload["summary"]["blocking_issue_counts"] = {
        "row_id_overlap_detected": 1,
        "endpoint_reconstructed_runs_mismatch_completed": 1,
    }
    cross_payload["rows"][0]["blocking_issues"] = [
        "row_id_overlap_detected",
        "endpoint_reconstructed_runs_mismatch_completed",
    ]
    cross_payload["study_level_layers"]["split_profile_integrity_scan"][
        "row_id_overlap_violations"
    ] = 1

    controls = control_by_id(audit.build_controls_from_cross_run(cross_payload))

    assert controls["hard_split_leakage_absence"]["status"] == "fail"
    assert controls["hard_split_leakage_absence"]["severity"] == "high"
    assert controls["endpoint_reconstruction_closure"]["status"] == "fail"
    assert controls["endpoint_reconstruction_closure"]["severity"] == "high"


def test_retrospective_controls_keep_duplicate_and_metadata_limits_as_caveats():
    cross_payload = base_cross_run_payload()
    cross_payload["summary"]["caveat_counts"] = {
        "duplicate_signature_cross_split_caveat": 1,
        "feature_leakage_metadata_completeness_caveat": 1,
    }
    cross_payload["summary"]["feature_metadata_selection_counts"] = {
        "ledger_referenced_prediction_artifacts": 1
    }
    cross_payload["summary"]["feature_policy_inference_counts"] = {
        "complete_drop_and_policy_metadata": 1
    }
    cross_payload["study_level_layers"]["split_profile_integrity_scan"][
        "duplicate_signature_warnings"
    ] = 1
    cross_payload["study_level_layers"]["split_profile_integrity_scan"][
        "total_duplicate_signature_pair_overlaps"
    ] = 4
    cross_payload["rows"][0]["caveats"] = [
        "duplicate_signature_cross_split_caveat",
        "feature_leakage_metadata_completeness_caveat",
    ]
    cross_payload["rows"][0]["feature_leakage_audit"][
        "missing_metadata_field_total"
    ] = 2

    controls = control_by_id(audit.build_controls_from_cross_run(cross_payload))

    assert controls["hard_split_leakage_absence"]["status"] == "pass"
    assert controls["prediction_feature_leakage_absence"]["status"] == "pass"
    assert controls["duplicate_signature_sensitivity_tracking"]["status"] == "caveat"
    assert controls["prediction_metadata_leakage_coverage"]["status"] == "caveat"
    assert (
        controls["plus_family_duplicate_cluster_internal_fold_boundary"]["status"]
        == "pass"
    )


def test_retrospective_controls_caveat_when_feature_metadata_counts_not_recorded():
    cross_payload = base_cross_run_payload()
    cross_payload["summary"]["feature_metadata_selection_counts"] = {
        "ledger_referenced_prediction_artifacts": 3,
        "not_recorded": 2,
    }
    cross_payload["summary"]["feature_policy_inference_counts"] = {
        "complete_drop_and_policy_metadata": 3,
        "not_recorded": 1,
    }

    controls = control_by_id(audit.build_controls_from_cross_run(cross_payload))
    control = controls["prediction_metadata_leakage_coverage"]

    assert control["status"] == "caveat"
    assert control["severity"] == "medium"
    assert control["evidence"]["metadata_selection_not_recorded"] == 2
    assert control["evidence"]["policy_inference_not_recorded"] == 1
    assert control["evidence"]["metadata_scope_caveats"] == 3


def test_retrospective_controls_caveat_duplicate_cluster_plus_family_internal_folds():
    cross_payload = base_cross_run_payload()
    cross_payload["summary"]["caveat_counts"] = {
        "duplicate_cluster_plus_family_internal_fold_caveat": 1,
    }
    cross_payload["rows"][0]["report_name"] = "duplicate_cluster_sensitivity_toy"
    cross_payload["rows"][0]["cp_methods"] = ["cv_plus", "split_abs"]
    cross_payload["rows"][0]["caveats"] = [
        "duplicate_cluster_plus_family_internal_fold_caveat",
    ]

    controls = control_by_id(audit.build_controls_from_cross_run(cross_payload))

    control = controls["plus_family_duplicate_cluster_internal_fold_boundary"]
    assert control["status"] == "caveat"
    assert control["severity"] == "medium"
    assert control["evidence"]["duplicate_cluster_plus_family_caveated_reports"] == 1
    assert "cv_plus" in control["evidence"]["affected_methods"]


def test_rel_accepts_external_probe_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_path = repo_root / "experiments/regression/reports/audit.json"
    external_path = tmp_path / "scratch/audit.json"

    assert audit.rel(repo_path, repo_root) == "experiments/regression/reports/audit.json"
    assert audit.rel(external_path, repo_root) == str(external_path)
