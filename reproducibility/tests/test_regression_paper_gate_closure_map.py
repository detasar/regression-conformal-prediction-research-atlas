import json
from pathlib import Path

from experiments.regression.scripts import build_paper_gate_closure_map as closure


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root):
    blocked_gates = [
        {"gate_id": "dataset_specific_final_gates", "status": "blocked"},
        {"gate_id": "endpoint_bounded_support_gate", "status": "blocked"},
        {"gate_id": "fairness_population_inference_gate", "status": "blocked"},
        {"gate_id": "final_method_model_selection_gate", "status": "blocked"},
        {"gate_id": "multiplicity_selection_record", "status": "blocked"},
        {"gate_id": "venn_abers_regression_validation_gate", "status": "blocked"},
    ]
    requirement_statuses = {
        row["gate_id"]: "blocked" for row in blocked_gates
    }
    requirement_statuses["remediation_backlog_closed_or_scoped"] = "pass"
    write_json(
        root / closure.PAPER_READINESS,
        {
            "summary": {
                "overall_status": "paper_readiness_blocked_with_evidence_map",
            },
            "blocked_gates": blocked_gates,
        },
    )
    write_json(
        root / closure.PUBLICATION_METHODOLOGY,
        {
            "summary": {
                "overall_status": "publication_workbench_ready_with_caveats"
            },
            "requirement_statuses": requirement_statuses,
        },
    )
    write_json(
        root / closure.DATASET_FINAL_REMEDIATION,
        {
            "summary": {
                "dataset_count": 2,
                "dataset_with_no_remaining_execution_gap_count": 2,
                "local_dataset_remediation_action_count": 0,
                "ready_dataset_count": 0,
            }
        },
    )
    write_json(
        root / closure.DATASET_FINAL_GATE,
        {"summary": {"main_result_ready_dataset_count": 0}},
    )
    write_json(
        root / closure.FINAL_SELECTION,
        {"summary": {"claim_status": "blocked"}},
    )
    write_json(
        root / closure.FAIRNESS_POPULATION,
        {
            "summary": {
                "diagnostic_group_bundle_count": 4,
                "population_fairness_ready_bundle_count": 0,
                "can_support_publication_ready_fairness": False,
            }
        },
    )
    write_json(
        root / closure.BOUNDED_SUPPORT_PROTOCOL,
        {"summary": {"can_support_bounded_support_validity": False}},
    )
    write_json(
        root / closure.BOUNDED_SUPPORT_DATASET_AUDIT,
        {
            "summary": {
                "bounded_support_posthandling_unvalidated_bundle_count": 0,
                "bounded_support_dataset_endpoint_blocked_or_incomplete_bundle_count": 2,
            }
        },
    )
    write_json(
        root / closure.BOUNDED_SUPPORT_ENDPOINT_CLOSURE,
        {
            "summary": {
                "open_count_backfill_bundle_count": 0,
                "dataset_open_endpoint_count_backfill_count": 0,
                "global_no_claim_bundle_count": 3,
            }
        },
    )
    write_json(
        root / closure.SELECTION_PROTOCOL,
        {
            "summary": {
                "overall_status": "selection_multiplicity_protocol_defined_no_final_selection"
            }
        },
    )
    write_json(
        root / closure.SELECTION_EVIDENCE,
        {
            "summary": {
                "overall_status": "selection_multiplicity_evidence_record_ready_no_final_selection",
                "validation_completed_atomic_rows": 45,
                "validation_expected_atomic_rows": 45,
            }
        },
    )
    write_json(
        root / closure.METHOD_SELECTION_CANDIDATE,
        {
            "summary": {
                "overall_status": "method_selection_candidate_audit_ready_no_final_selection",
                "primary_candidate_method": "cqr",
            }
        },
    )
    write_json(
        root / closure.METHOD_SELECTION_ROBUSTNESS,
        {
            "summary": {
                "overall_status": "method_selection_robustness_audit_ready_no_final_selection",
                "common_cell_primary_win_count": 58,
            }
        },
    )
    write_json(
        root / closure.METHOD_SELECTION_INFERENTIAL,
        {
            "summary": {
                "overall_status": "method_selection_inferential_audit_ready_no_final_selection",
                "primary_candidate_method": "cqr",
                "bootstrap_primary_selection_rate": 1.0,
            }
        },
    )
    write_json(
        root / closure.METHOD_SELECTION_POST_SELECTION,
        {
            "summary": {
                "completed_atomic_run_count": 45,
                "expected_atomic_run_count": 45,
            }
        },
    )
    write_json(
        root / closure.VENN_ABERS_VALIDATION,
        {
            "summary": {
                "overall_status": "venn_abers_validation_blocked_with_negative_evidence"
            }
        },
    )
    write_json(
        root / closure.VENN_ABERS_CLAIM_GATE,
        {
            "summary": {
                "positive_claim_blocked_count": 3,
                "positive_claim_pass_count": 1,
                "blocked_positive_requirement_ids": [
                    "score_grid_panel_coverage_nominal",
                    "score_grid_upper_boundary_free",
                    "ivapd_interval_cp_validated",
                ],
                "total_grid_reference_rows_scored": 6001,
            }
        },
    )
    write_json(
        root / closure.VENN_ABERS_NEGATIVE_DISPOSITION,
        {
            "summary": {
                "overall_status": "venn_abers_negative_evidence_disposition_pass",
                "negative_claim_present": True,
                "negative_result_reporting_ready": True,
                "current_manuscript_positive_validation_required": False,
                "manuscript_disposition_status": (
                    "accepted_negative_result_for_current_manuscript"
                ),
            }
        },
    )
    write_json(
        root / closure.VENN_ABERS_FAILURE_MODES,
        {"summary": {"total_grid_reference_rows_scored": 6001}},
    )


def test_closure_map_separates_positive_claims_from_scoped_paths(tmp_path):
    write_minimal_sources(tmp_path)

    payload = closure.build_payload(tmp_path)
    rows = {row["gate_id"]: row for row in payload["gate_rows"]}

    assert (
        payload["summary"]["overall_status"]
        == "paper_gate_closure_map_ready_no_promotions"
    )
    assert payload["summary"]["gate_count"] == 6
    assert payload["summary"]["blocked_gate_count"] == 6
    assert payload["summary"]["current_paper_blocking_gate_count"] == 5
    assert payload["summary"]["positive_claim_ready_gate_count"] == 0
    assert payload["summary"]["scoped_or_negative_path_ready_gate_count"] == 6
    assert payload["summary"]["local_execution_gap_gate_count"] == 0
    assert payload["summary"]["can_start_post_experiment_publication"] is False
    assert payload["summary"]["can_extract_negative_results_table"] is True
    assert payload["summary"]["venn_abers_negative_result_reporting_ready"] is True
    assert payload["summary"]["positive_venn_abers_validation_forcing_required"] is False
    assert rows["dataset_specific_final_gates"][
        "closure_mode"
    ] == "global_claim_gate_dependencies_then_refresh"
    assert rows["final_method_model_selection_gate"][
        "metrics"
    ]["primary_candidate_method"] == "cqr"
    assert rows["multiplicity_selection_record"][
        "scoped_or_negative_path_ready"
    ] is True
    assert rows["endpoint_bounded_support_gate"][
        "metrics"
    ]["endpoint_policy_closed"] is True
    assert rows["venn_abers_regression_validation_gate"][
        "scoped_or_negative_path_ready"
    ] is True
    assert "validated Venn-Abers regression interval coverage" in rows[
        "venn_abers_regression_validation_gate"
    ]["paper_disallowed_language"]
    assert payload["failed_checks"] == []


def test_checked_in_closure_map_current_status_after_generation():
    payload = closure.build_payload(Path("."))
    rows = {row["gate_id"]: row for row in payload["gate_rows"]}

    assert payload["summary"]["gate_count"] == 6
    assert payload["summary"]["blocked_gate_count"] == 6
    assert payload["summary"]["current_paper_blocking_gate_count"] == 5
    assert payload["summary"]["can_start_post_experiment_publication"] is False
    assert payload["summary"]["can_extract_negative_results_table"] is True
    assert payload["summary"]["venn_abers_negative_result_reporting_ready"] is True
    assert payload["summary"]["positive_venn_abers_validation_forcing_required"] is False
    assert (
        payload["summary"]["dataset_final_local_remediation_action_count"] == 0
    )
    assert (
        payload["summary"]["dataset_with_no_remaining_execution_gap_count"] == 6
    )
    assert rows["venn_abers_regression_validation_gate"][
        "metrics"
    ]["grid_reference_rows_scored"] == 6001
    assert rows["final_method_model_selection_gate"][
        "metrics"
    ]["primary_candidate_method"] == "cqr"
