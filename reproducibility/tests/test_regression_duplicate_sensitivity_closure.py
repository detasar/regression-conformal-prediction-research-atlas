import json
from pathlib import Path

from experiments.regression.scripts import audit_duplicate_sensitivity_closure as audit


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok\n", encoding="utf-8")


def write_minimal_sources(root: Path) -> None:
    report_dir = root / audit.REPORT_DIR
    evidence_dir = root / "experiments/regression/reports/sensitivity_demo"
    evidence_paths = {
        "comparison_path": evidence_dir / "sensitivity_comparison.json",
        "endpoint_audit_path": evidence_dir / "endpoint_audit.json",
        "experiment_notes_path": evidence_dir / "experiment_notes.md",
        "feature_leakage_audit_path": evidence_dir / "feature_leakage_audit.json",
        "split_profile_path": evidence_dir / "split_profile.json",
    }
    for path in evidence_paths.values():
        touch(path)
    config_path = root / "experiments/regression/configs/demo_duplicate.yaml"
    touch(config_path)
    sensitivity_evidence = {
        key: str(path.relative_to(root)) for key, path in evidence_paths.items()
    }
    sensitivity_evidence.update(
        {
            "paired_rows": 12,
            "nominal_status_change_count": 2,
            "seed_imbalanced_paired_rows": 0,
            "offending_seed_coverage_complete": True,
            "feature_leakage_violations_count": 0,
            "coverage_delta_abs": {"max": 0.01},
            "status": "completed_duplicate_cluster_sensitivity",
        }
    )

    write_json(
        report_dir / "cross_run_integrity_audit.json",
        {
            "summary": {
                "caveat_counts": {
                    "duplicate_signature_cross_split_caveat": 1,
                    "model_visible_signature_cross_split_caveat": 0,
                },
                "leakage_status": "hard_leakage_not_detected_in_scanned_artifacts",
            },
            "rows": [
                {
                    "report_id": "report:demo",
                    "report_name": "demo",
                    "dataset_ids": ["demo_dataset"],
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
    write_json(
        report_dir / "duplicate_split_caveat_backlog.json",
        {
            "summary": {
                "affected_dataset_count": 1,
                "affected_seed_profile_count": 1,
                "malformed_split_profile_count": 0,
                "row_id_overlap_violation_seed_profiles": 0,
                "split_group_overlap_violation_seed_profiles": 0,
                "total_duplicate_signature_pair_overlaps": 3,
            }
        },
    )
    write_json(
        report_dir / "paired_duplicate_sensitivity_audit.json",
        {
            "summary": {
                "paired_dataset_count": 3,
                "paired_comparison_rows": 12,
                "raw_only_rows": 0,
                "dedup_only_rows": 0,
            }
        },
    )
    write_json(
        report_dir / "integrity_remediation_backlog.json",
        {
            "summary": {
                "action_count": 1,
                "covered_action_count": 1,
                "open_action_count": 0,
                "issue_counts_match_cross_run": True,
                "status_counts": {"covered_by_sensitivity": 1},
                "issue_counts": {"duplicate_signature_cross_split_caveat": 1},
            },
            "rows": [
                {
                    "action_id": "demo:caveat:duplicate_signature_cross_split_caveat",
                    "report_id": "report:demo",
                    "report_name": "demo",
                    "issue_type": "duplicate_signature_cross_split_caveat",
                    "status": "covered_by_sensitivity",
                    "dataset_ids": ["demo_dataset"],
                    "config_path": str(config_path.relative_to(root)),
                    "sensitivity_evidence": [sensitivity_evidence],
                }
            ],
        },
    )
    final_summary = {
        "overall_status": "pass",
        "claim_status": "blocked",
        "blocked_requirement_count": 6,
    }
    write_json(
        report_dir / "final_selection_claim_boundary_audit.json",
        {"summary": final_summary},
    )
    write_json(
        report_dir / "publication_methodology_audit.json",
        {
            "summary": {
                "overall_status": "publication_workbench_ready_with_caveats",
                "failed_check_count": 0,
                "open_remediation_actions": 0,
                "can_support_final_method_selection": False,
                "can_support_publication_ready_fairness": False,
                "can_support_bounded_support_validity": False,
                "can_support_venn_abers_regression_validation": False,
            }
        },
    )
    write_json(
        root / audit.CLAIM_REGISTER,
        {
            "claims": [
                {
                    "claim_id": audit.FINAL_CLAIM_ID,
                    "status": "blocked",
                    "requirements": [
                        {"requirement_id": key, "status": "blocked"}
                        for key in sorted(audit.FINAL_BLOCKED_REQUIREMENTS)
                    ],
                },
                {
                    "claim_id": "demo_duplicate_sensitivity_pending",
                    "claim_type": "dataset_robustness_gate",
                    "status": "robustness_evidence_gate_passed_with_caveats",
                },
            ]
        },
    )
    write_json(
        root / audit.BUNDLE_INDEX,
        {
            "bundle_summary": {
                "manifest_count": 1,
                "completed_with_caveats_count": 1,
            },
            "bundles": [
                {
                    "bundle_id": "demo_duplicate_bundle",
                    "evidence_role": "robustness",
                    "status": "completed_with_caveats",
                    "claim_scope": "Demo duplicate-sensitivity robustness only.",
                    "promotion_blockers": [
                        "no final-selection, fairness, bounded-support, or Venn-Abers validation claim"
                    ],
                }
            ],
        },
    )


def test_duplicate_sensitivity_closure_fixture_passes_with_scoped_caveats(tmp_path):
    write_minimal_sources(tmp_path)

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "scoped_duplicate_sensitivity_closure_pass_with_caveats"
    )
    assert payload["summary"]["hard_failed_check_count"] == 0
    assert payload["summary"]["open_action_count"] == 0
    assert payload["summary"]["covered_action_count"] == 1
    assert payload["summary"]["duplicate_caveat_count"] == 1
    assert payload["summary"]["scoped_caveat_check_count"] == 2
    assert payload["schema"] == audit.SCHEMA
    assert [row["status"] for row in payload["covered_actions"]] == [
        "covered_by_sensitivity"
    ]
    assert payload["tracked_caveat_actions"] == []
    assert {
        item["check_id"]: item["status"] for item in payload["checks"]
    }["covered_actions_output_contract_is_strict"] == "pass"


def test_duplicate_closure_ignores_tracked_non_duplicate_methodology_caveats(
    tmp_path,
):
    write_minimal_sources(tmp_path)
    report_dir = tmp_path / audit.REPORT_DIR

    cross_path = report_dir / "cross_run_integrity_audit.json"
    cross_payload = json.loads(cross_path.read_text(encoding="utf-8"))
    cross_payload["summary"]["caveat_counts"][
        "duplicate_cluster_plus_family_internal_fold_caveat"
    ] = 1
    cross_payload["rows"].append(
        {
            "report_id": "report:plus_family",
            "report_name": "duplicate_cluster_sensitivity_demo",
            "dataset_ids": ["demo_dataset"],
            "caveats": ["duplicate_cluster_plus_family_internal_fold_caveat"],
            "split_profile": {
                "present": True,
                "schema": "cpfi_regression_split_profile_v2",
                "row_id_overlap_violations": 0,
                "split_group_overlap_violations": 0,
            },
            "endpoint_audit": {"present": True},
            "feature_leakage_audit": {"present": True, "violations_count": 0},
        }
    )
    cross_path.write_text(json.dumps(cross_payload), encoding="utf-8")

    backlog_path = report_dir / "integrity_remediation_backlog.json"
    backlog_payload = json.loads(backlog_path.read_text(encoding="utf-8"))
    backlog_payload["summary"]["action_count"] = 2
    backlog_payload["summary"]["covered_action_count"] = 2
    backlog_payload["summary"]["status_counts"] = {
        "covered_by_sensitivity": 1,
        "tracked_methodology_caveat": 1,
    }
    backlog_payload["summary"]["issue_counts"][
        "duplicate_cluster_plus_family_internal_fold_caveat"
    ] = 1
    backlog_payload["rows"].append(
        {
            "action_id": (
                "plus_family:caveat:"
                "duplicate_cluster_plus_family_internal_fold_caveat"
            ),
            "report_id": "report:plus_family",
            "report_name": "duplicate_cluster_sensitivity_demo",
            "issue_type": "duplicate_cluster_plus_family_internal_fold_caveat",
            "status": "tracked_methodology_caveat",
            "dataset_ids": ["demo_dataset"],
            "sensitivity_evidence": [],
        }
    )
    backlog_path.write_text(json.dumps(backlog_payload), encoding="utf-8")

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "scoped_duplicate_sensitivity_closure_pass_with_caveats"
    )
    assert payload["summary"]["duplicate_action_count"] == 1
    assert payload["summary"]["covered_action_count"] == 1
    assert payload["summary"]["tracked_caveat_action_count"] == 1
    assert payload["summary"]["backlog_covered_action_count_total"] == 2
    assert payload["summary"]["hard_failed_check_count"] == 0
    assert [row["status"] for row in payload["covered_actions"]] == [
        "covered_by_sensitivity"
    ]
    assert [row["status"] for row in payload["tracked_caveat_actions"]] == [
        "tracked_methodology_caveat"
    ]


def test_duplicate_closure_tracks_main_result_candidate_diagnostic_caveat(
    tmp_path,
):
    write_minimal_sources(tmp_path)
    report_dir = tmp_path / audit.REPORT_DIR

    cross_path = report_dir / "cross_run_integrity_audit.json"
    cross_payload = json.loads(cross_path.read_text(encoding="utf-8"))
    cross_payload["summary"]["caveat_counts"][
        "duplicate_signature_cross_split_caveat"
    ] = 2
    cross_payload["rows"].append(
        {
            "report_id": "report:main_result_candidate_bundle_demo",
            "report_name": "main_result_candidate_bundle_demo",
            "dataset_ids": ["demo_candidate_dataset"],
            "caveats": ["duplicate_signature_cross_split_caveat"],
            "split_profile": {
                "present": True,
                "schema": "cpfi_regression_split_profile_v2",
                "row_id_overlap_violations": 0,
                "split_group_overlap_violations": 0,
            },
            "endpoint_audit": {"present": True},
            "feature_leakage_audit": {"present": True, "violations_count": 0},
        }
    )
    cross_path.write_text(json.dumps(cross_payload), encoding="utf-8")

    backlog_path = report_dir / "integrity_remediation_backlog.json"
    backlog_payload = json.loads(backlog_path.read_text(encoding="utf-8"))
    backlog_payload["summary"]["action_count"] = 2
    backlog_payload["summary"]["covered_action_count"] = 2
    backlog_payload["summary"]["open_action_count"] = 0
    backlog_payload["summary"]["status_counts"] = {
        "covered_by_sensitivity": 1,
        "tracked_diagnostic_caveat": 1,
    }
    backlog_payload["summary"]["issue_counts"][
        "duplicate_signature_cross_split_caveat"
    ] = 2
    backlog_payload["rows"].append(
        {
            "action_id": (
                "main_result_candidate_bundle_demo:caveat:"
                "duplicate_signature_cross_split_caveat"
            ),
            "report_id": "report:main_result_candidate_bundle_demo",
            "report_name": "main_result_candidate_bundle_demo",
            "issue_type": "duplicate_signature_cross_split_caveat",
            "status": "tracked_diagnostic_caveat",
            "dataset_ids": ["demo_candidate_dataset"],
            "sensitivity_evidence": [],
        }
    )
    backlog_path.write_text(json.dumps(backlog_payload), encoding="utf-8")

    bundle_path = tmp_path / audit.BUNDLE_INDEX
    bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle_payload["bundle_summary"]["manifest_count"] = 2
    bundle_payload["bundles"].append(
        {
            "bundle_id": "main_result_candidate_bundle_demo",
            "evidence_role": "main_result_candidate_diagnostic",
            "status": "completed_main_result_candidate_blocked_with_caveats",
            "claim_scope": (
                "Diagnostic main-result candidate only; no final result claim."
            ),
            "promotion_blockers": [
                "no final-selection claim",
                "no fairness, bounded-support, or Venn-Abers validation claim",
            ],
        }
    )
    bundle_path.write_text(json.dumps(bundle_payload), encoding="utf-8")

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "scoped_duplicate_sensitivity_closure_pass_with_caveats"
    )
    assert payload["summary"]["duplicate_action_count"] == 2
    assert payload["summary"]["covered_action_count"] == 1
    assert payload["summary"]["tracked_caveat_action_count"] == 1
    assert payload["summary"]["tracked_methodology_caveat_action_count"] == 0
    assert payload["summary"]["tracked_diagnostic_caveat_action_count"] == 1
    assert payload["summary"]["hard_failed_check_count"] == 0
    assert [row["status"] for row in payload["covered_actions"]] == [
        "covered_by_sensitivity"
    ]
    assert [row["status"] for row in payload["tracked_caveat_actions"]] == [
        "tracked_diagnostic_caveat"
    ]


def test_duplicate_sensitivity_closure_fails_for_open_backlog_action(tmp_path):
    write_minimal_sources(tmp_path)
    path = tmp_path / audit.REMEDIATION_BACKLOG
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["summary"]["open_action_count"] = 1
    payload["summary"]["covered_action_count"] = 0
    payload["summary"]["status_counts"] = {"open": 1}
    payload["rows"][0]["status"] = "open"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = audit.build_payload(tmp_path)

    assert result["summary"]["overall_status"] == "fail"
    assert result["summary"]["hard_failed_check_count"] == 1
    assert {
        item["check_id"] for item in result["failed_checks"]
    } == {"all_duplicate_actions_are_covered_by_sensitivity"}


def test_duplicate_sensitivity_closure_fails_when_final_claim_is_promoted(tmp_path):
    write_minimal_sources(tmp_path)
    path = tmp_path / audit.CLAIM_REGISTER
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["claims"][0]["status"] = "pass"
    payload["claims"][0]["requirements"][0]["status"] = "pass"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = audit.build_payload(tmp_path)

    assert result["summary"]["overall_status"] == "fail"
    assert {
        item["check_id"] for item in result["failed_checks"]
    } == {"final_selection_claims_remain_blocked"}


def test_checked_in_duplicate_sensitivity_closure_payload_is_scoped():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "duplicate_sensitivity_closure_audit.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert (
        payload["summary"]["overall_status"]
        == "scoped_duplicate_sensitivity_closure_pass_with_caveats"
    )
    assert payload["summary"]["duplicate_action_count"] == 29
    assert payload["summary"]["covered_action_count"] == 25
    assert payload["summary"]["tracked_caveat_action_count"] == 21
    assert payload["summary"]["tracked_methodology_caveat_action_count"] == 17
    assert payload["summary"]["tracked_diagnostic_caveat_action_count"] == 4
    assert payload["summary"]["open_action_count"] == 0
    assert payload["summary"]["hard_failed_check_count"] == 0
    assert payload["summary"]["final_blocked_requirement_count"] == 6
    assert len(payload["covered_actions"]) == 25
    assert len(payload["tracked_caveat_actions"]) == 21
    assert {
        row["status"] for row in payload["covered_actions"]
    } == {"covered_by_sensitivity"}
    assert {
        row["status"] for row in payload["tracked_caveat_actions"]
    } == {"tracked_diagnostic_caveat", "tracked_methodology_caveat"}
    assert {
        item["check_id"]: item["status"] for item in payload["checks"]
    }["covered_actions_output_contract_is_strict"] == "pass"
