import json
from pathlib import Path

from experiments.regression.scripts import (
    build_paper_gate_closure_execution_plan as plan,
)


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root: Path):
    gate_ids = [
        "dataset_specific_final_gates",
        "endpoint_bounded_support_gate",
        "fairness_population_inference_gate",
        "final_method_model_selection_gate",
        "multiplicity_selection_record",
        "venn_abers_regression_validation_gate",
    ]
    write_json(
        root / plan.PAPER_GATE_CLOSURE,
        {
            "summary": {
                "overall_status": "paper_gate_closure_map_ready_no_promotions",
                "blocked_gate_count": 6,
            },
            "gate_rows": [
                {
                    "gate_id": gate_id,
                    "current_status": "blocked",
                    "positive_claim_ready": False,
                    "scoped_or_negative_path_ready": True,
                    "source_artifacts": [
                        "experiments/regression/manuscript/paper_gate_closure_map.json"
                    ],
                }
                for gate_id in gate_ids
            ],
        },
    )
    write_json(
        root / plan.PAPER_READINESS,
        {
            "summary": {
                "overall_status": "paper_readiness_blocked_with_evidence_map"
            },
            "blocked_gates": [
                {"gate_id": gate_id, "status": "blocked"} for gate_id in gate_ids
            ],
        },
    )


def write_protocol_bundle(root: Path):
    write_json(
        root / plan.PAPER_GATE_PROTOCOL_DESIGN_BUNDLE,
        {
            "summary": {
                "overall_status": (
                    "paper_gate_protocol_design_bundle_ready_no_claim_promotions"
                ),
                "completed_protocol_design_action_count": 4,
            },
            "protocol_design_rows": [
                {"action_id": action_id, "status": "protocol_design_complete"}
                for action_id in [
                    "endpoint_bounded_support_gate.define_target_domain_validity_estimand",
                    "fairness_population_inference_gate.define_population_and_protected_scope",
                    "multiplicity_selection_record.freeze_searched_space_and_error_contract",
                    "venn_abers_regression_validation_gate.design_validated_regression_venn_abers_method",
                ]
            ],
        },
    )


def write_sampling_weight_policy(root: Path):
    write_json(
        root / plan.FAIRNESS_SAMPLING_WEIGHT_POLICY,
        {
            "summary": {
                "overall_status": (
                    "fairness_sampling_weight_policy_defined_no_fairness_claim"
                ),
                "action_id": (
                    "fairness_population_inference_gate."
                    "define_sampling_weight_policy"
                ),
                "action_status": "protocol_design_complete",
            }
        },
    )


def write_fairness_group_diagnostic(root: Path):
    write_json(
        root / plan.FAIRNESS_GROUP_DIAGNOSTIC_AUDIT,
        {
            "summary": {
                "overall_status": (
                    "fairness_group_diagnostic_audit_completed_no_fairness_claim"
                ),
                "action_id": (
                    "fairness_population_inference_gate."
                    "compute_group_counts_missingness_and_gaps"
                ),
                "action_status": "empirical_execution_complete",
            }
        },
    )


def write_fairness_group_multiplicity_scope(root: Path):
    write_json(
        root / plan.FAIRNESS_GROUP_MULTIPLICITY_SCOPE,
        {
            "summary": {
                "overall_status": (
                    "fairness_group_multiplicity_scope_declared_no_fairness_claim"
                ),
                "action_id": (
                    "fairness_population_inference_gate."
                    "declare_group_comparison_multiplicity_scope"
                ),
                "action_status": "multiplicity_control_complete",
                "claim_register_cites_multiplicity_record": True,
                "current_manuscript_fairness_population_claim_ready": False,
            }
        },
    )


def write_fairness_population_readiness(root: Path):
    write_json(
        root / plan.FAIRNESS_POPULATION_READINESS,
        {
            "summary": {
                "overall_status": (
                    "fairness_population_readiness_audit_completed_no_fairness_claim"
                ),
                "failed_check_count": 0,
                "can_support_publication_ready_fairness": False,
                "fairness_population_claim_status": "blocked_diagnostic_only",
                "fairness_requirement_status": "blocked",
                "bundle_count": 2,
                "diagnostic_group_bundle_count": 2,
                "population_fairness_ready_bundle_count": 0,
                "population_estimand_declared_bundle_count": 0,
                "protected_attribute_scope_declared_bundle_count": 0,
                "group_counts_recorded_bundle_count": 2,
                "group_gap_uncertainty_recorded_bundle_count": 2,
                "multiplicity_scope_declared_bundle_count": 2,
                "claim_register_cites_multiplicity_record": True,
            }
        },
    )


def write_endpoint_closure(root: Path):
    write_json(
        root / plan.BOUNDED_SUPPORT_ENDPOINT_CLOSURE,
        {
            "summary": {
                "overall_status": (
                    "endpoint_policy_triage_closed_no_bounded_support_validity_claim"
                ),
                "action_id": (
                    "endpoint_bounded_support_gate."
                    "audit_natural_domain_endpoint_excursions"
                ),
                "action_status": "empirical_execution_complete",
                "failed_check_count": 0,
                "bundle_count": 2,
                "closed_policy_bundle_count": 2,
                "open_endpoint_count_backfill_bundle_count": 0,
                "global_no_claim_bundle_count": 2,
                "bounded_support_validity_claim_ready_bundle_count": 0,
                "can_support_bounded_support_validity": False,
                "current_manuscript_bounded_support_validity_claim_ready": False,
            }
        },
    )


def write_bounded_support_positive_validation(root: Path):
    write_json(
        root / plan.BOUNDED_SUPPORT_POSITIVE_VALIDATION,
        {
            "summary": {
                "overall_status": (
                    "bounded_support_positive_validation_protocol_completed_no_validity_claim"
                ),
                "action_id": (
                    "endpoint_bounded_support_gate."
                    "run_positive_bounded_support_validity_protocol"
                ),
                "action_status": (
                    "empirical_validation_complete_no_bounded_support_claim"
                ),
                "failed_check_count": 0,
                "bundle_count": 2,
                "posthandling_validated_bundle_count": 2,
                "policy_metrics_available_bundle_count": 2,
                "endpoint_blocked_or_incomplete_bundle_count": 1,
                "positive_claim_ready_bundle_count": 0,
                "can_support_bounded_support_validity": False,
                "current_manuscript_bounded_support_validity_claim_ready": False,
                "positive_acceptance_failed_count": 4,
                "interval_score_metrics_missing_bundle_count": 1,
            }
        },
    )


def write_venn_abers_negative_disposition(root: Path):
    write_json(
        root / plan.VENN_ABERS_NEGATIVE_DISPOSITION,
        {
            "summary": {
                "overall_status": "venn_abers_negative_evidence_disposition_pass",
                "negative_result_reporting_ready": True,
                "current_manuscript_positive_validation_required": False,
            }
        },
    )


def test_execution_plan_fixture_maps_all_blocked_gates_to_actions(tmp_path):
    write_minimal_sources(tmp_path)

    payload = plan.build_payload(tmp_path)
    rows = {row["action_id"]: row for row in payload["action_rows"]}

    assert (
        payload["summary"]["overall_status"]
        == "paper_gate_closure_execution_plan_ready"
    )
    assert payload["summary"]["gate_count"] == 6
    assert payload["summary"]["blocked_gate_count"] == 6
    assert payload["summary"]["action_count"] >= 20
    assert payload["summary"]["can_close_any_positive_gate_now"] is False
    assert payload["summary"]["ready_for_protocol_design_action_count"] > 0
    assert payload["summary"]["blocked_by_gate_dependencies_action_count"] > 0
    assert (
        rows[
            "fairness_population_inference_gate.define_population_and_protected_scope"
        ]["status"]
        == "ready_for_protocol_design"
    )
    assert (
        rows["dataset_specific_final_gates.refresh_after_global_gate_closure"][
            "status"
        ]
        == "blocked_by_gate_dependencies"
    )
    assert payload["failed_checks"] == []


def test_execution_plan_consumes_protocol_design_bundle(tmp_path):
    write_minimal_sources(tmp_path)
    write_protocol_bundle(tmp_path)

    payload = plan.build_payload(tmp_path)
    rows = {row["action_id"]: row for row in payload["action_rows"]}

    assert payload["summary"]["protocol_design_complete_action_count"] == 4
    assert payload["summary"]["ready_for_empirical_execution_action_count"] == 4
    assert payload["summary"]["ready_for_protocol_design_action_count"] == 1
    assert (
        rows[
            "endpoint_bounded_support_gate.define_target_domain_validity_estimand"
        ]["status"]
        == "protocol_design_complete"
    )
    assert (
        rows[
            "endpoint_bounded_support_gate.audit_natural_domain_endpoint_excursions"
        ]["status"]
        == "ready_for_empirical_execution"
    )
    assert (
        rows[
            "fairness_population_inference_gate.define_sampling_weight_policy"
        ]["status"]
        == "ready_for_protocol_design"
    )
    assert payload["summary"]["can_close_any_positive_gate_now"] is False


def test_execution_plan_consumes_sampling_weight_policy(tmp_path):
    write_minimal_sources(tmp_path)
    write_protocol_bundle(tmp_path)
    write_sampling_weight_policy(tmp_path)

    payload = plan.build_payload(tmp_path)
    rows = {row["action_id"]: row for row in payload["action_rows"]}

    assert payload["summary"]["protocol_design_complete_action_count"] == 5
    assert payload["summary"]["ready_for_empirical_execution_action_count"] == 5
    assert payload["summary"]["ready_for_protocol_design_action_count"] == 0
    assert (
        payload["summary"]["fairness_sampling_weight_policy_complete_action_count"]
        == 1
    )
    assert (
        rows[
            "fairness_population_inference_gate.define_sampling_weight_policy"
        ]["status"]
        == "protocol_design_complete"
    )
    assert (
        rows[
            "fairness_population_inference_gate.compute_group_counts_missingness_and_gaps"
        ]["status"]
        == "ready_for_empirical_execution"
    )


def test_execution_plan_consumes_fairness_group_diagnostic_audit(tmp_path):
    write_minimal_sources(tmp_path)
    write_protocol_bundle(tmp_path)
    write_sampling_weight_policy(tmp_path)
    write_fairness_group_diagnostic(tmp_path)
    write_venn_abers_negative_disposition(tmp_path)

    payload = plan.build_payload(tmp_path)
    rows = {row["action_id"]: row for row in payload["action_rows"]}

    assert payload["summary"]["protocol_design_complete_action_count"] == 5
    assert payload["summary"]["empirical_execution_complete_action_count"] == 1
    assert payload["summary"]["venn_abers_negative_disposition_complete_action_count"] == 1
    assert payload["summary"]["ready_for_empirical_execution_action_count"] == 1
    assert payload["summary"]["ready_for_protocol_design_action_count"] == 1
    assert (
        rows[
            "fairness_population_inference_gate.compute_group_counts_missingness_and_gaps"
        ]["status"]
        == "empirical_execution_complete"
    )
    assert (
        rows[
            "fairness_population_inference_gate.declare_group_comparison_multiplicity_scope"
        ]["status"]
        == "ready_for_protocol_design"
    )
    assert (
        rows[
            "venn_abers_regression_validation_gate."
            "accept_negative_result_disposition_for_manuscript"
        ]["status"]
        == "negative_disposition_complete"
    )
    assert (
        rows[
            "venn_abers_regression_validation_gate."
            "run_exact_grid_or_theory_validation_benchmark"
        ]["status"]
        == "optional_deferred_after_negative_disposition"
    )


def test_execution_plan_consumes_endpoint_closure_audit(tmp_path):
    write_minimal_sources(tmp_path)
    write_protocol_bundle(tmp_path)
    write_sampling_weight_policy(tmp_path)
    write_fairness_group_diagnostic(tmp_path)
    write_fairness_group_multiplicity_scope(tmp_path)
    write_fairness_population_readiness(tmp_path)
    write_endpoint_closure(tmp_path)
    write_venn_abers_negative_disposition(tmp_path)

    payload = plan.build_payload(tmp_path)
    rows = {row["action_id"]: row for row in payload["action_rows"]}

    assert payload["summary"]["empirical_execution_complete_action_count"] == 2
    assert payload["summary"]["multiplicity_control_complete_action_count"] == 1
    assert (
        payload["summary"][
            "gate_refresh_complete_no_fairness_claim_action_count"
        ]
        == 1
    )
    assert (
        payload["summary"][
            "fairness_group_multiplicity_scope_complete_action_count"
        ]
        == 1
    )
    assert payload["summary"]["endpoint_natural_domain_audit_complete_action_count"] == 1
    assert payload["summary"]["fairness_population_refresh_complete_action_count"] == 1
    assert payload["summary"]["fairness_population_ready_bundle_count"] == 0
    assert payload["summary"]["ready_for_empirical_execution_action_count"] == 1
    assert (
        payload["summary"]["current_manuscript_bounded_support_validity_claim_ready"]
        is False
    )
    assert (
        rows[
            "endpoint_bounded_support_gate.audit_natural_domain_endpoint_excursions"
        ]["status"]
        == "empirical_execution_complete"
    )
    assert (
        rows[
            "endpoint_bounded_support_gate.run_positive_bounded_support_validity_protocol"
        ]["status"]
        == "ready_for_empirical_execution"
    )
    assert (
        rows[
            "fairness_population_inference_gate."
            "declare_group_comparison_multiplicity_scope"
        ]["status"]
        == "multiplicity_control_complete"
    )
    assert (
        rows[
            "fairness_population_inference_gate.refresh_fairness_population_gate"
        ]["status"]
        == "gate_refresh_complete_no_fairness_claim"
    )


def test_execution_plan_consumes_bounded_support_positive_validation_no_claim(
    tmp_path,
):
    write_minimal_sources(tmp_path)
    write_protocol_bundle(tmp_path)
    write_sampling_weight_policy(tmp_path)
    write_fairness_group_diagnostic(tmp_path)
    write_fairness_group_multiplicity_scope(tmp_path)
    write_fairness_population_readiness(tmp_path)
    write_endpoint_closure(tmp_path)
    write_bounded_support_positive_validation(tmp_path)
    write_venn_abers_negative_disposition(tmp_path)

    payload = plan.build_payload(tmp_path)
    rows = {row["action_id"]: row for row in payload["action_rows"]}

    assert (
        payload["summary"][
            "empirical_validation_complete_no_bounded_support_claim_action_count"
        ]
        == 1
    )
    assert (
        payload["summary"][
            "gate_refresh_complete_no_bounded_support_claim_action_count"
        ]
        == 1
    )
    assert (
        payload["summary"]["bounded_support_positive_validation_complete_action_count"]
        == 1
    )
    assert (
        payload["summary"]["bounded_support_claim_refresh_complete_action_count"]
        == 1
    )
    assert payload["summary"]["ready_for_empirical_execution_action_count"] == 0
    assert payload["summary"]["ready_action_count"] == 0
    assert (
        rows[
            "endpoint_bounded_support_gate."
            "run_positive_bounded_support_validity_protocol"
        ]["status"]
        == "empirical_validation_complete_no_bounded_support_claim"
    )
    assert (
        rows["endpoint_bounded_support_gate.refresh_bounded_support_claim_gate"][
            "status"
        ]
        == "gate_refresh_complete_no_bounded_support_claim"
    )


def test_checked_in_execution_plan_current_status_after_generation():
    payload = plan.build_payload(Path("."))
    rows = {row["action_id"]: row for row in payload["action_rows"]}

    assert payload["summary"]["gate_count"] == 6
    assert payload["summary"]["blocked_gate_count"] == 6
    assert payload["summary"]["action_count"] >= 23
    assert payload["summary"]["protocol_design_complete_action_count"] == 5
    assert payload["summary"]["empirical_execution_complete_action_count"] == 2
    assert (
        payload["summary"][
            "empirical_validation_complete_no_bounded_support_claim_action_count"
        ]
        == 1
    )
    assert (
        payload["summary"][
            "gate_refresh_complete_no_bounded_support_claim_action_count"
        ]
        == 1
    )
    assert payload["summary"]["multiplicity_control_complete_action_count"] == 1
    assert payload["summary"]["endpoint_natural_domain_audit_complete_action_count"] == 1
    assert (
        payload["summary"]["current_manuscript_bounded_support_validity_claim_ready"]
        is False
    )
    assert payload["summary"]["venn_abers_negative_disposition_complete_action_count"] == 1
    assert payload["summary"]["current_manuscript_positive_venn_abers_validation_required"] is False
    assert (
        payload["summary"]["fairness_group_multiplicity_scope_complete_action_count"]
        == 1
    )
    assert payload["summary"]["current_manuscript_fairness_population_claim_ready"] is False
    assert payload["summary"]["gate_refresh_complete_no_fairness_claim_action_count"] == 1
    assert payload["summary"]["fairness_population_refresh_complete_action_count"] == 1
    assert payload["summary"]["fairness_population_ready_bundle_count"] == 0
    assert payload["summary"]["bounded_support_positive_validation_complete_action_count"] == 1
    assert payload["summary"]["bounded_support_claim_refresh_complete_action_count"] == 1
    assert (
        payload["summary"][
            "bounded_support_positive_validation_interval_score_missing_bundle_count"
        ]
        == 4
    )
    assert payload["summary"]["ready_for_empirical_execution_action_count"] == 0
    assert payload["summary"]["ready_for_protocol_design_action_count"] == 0
    assert payload["summary"]["ready_action_count"] == 0
    assert payload["summary"]["blocked_action_count"] > 0
    assert payload["summary"]["can_close_any_positive_gate_now"] is False
    assert (
        "venn_abers_regression_validation_gate.design_validated_regression_venn_abers_method"
        in rows
    )
    assert (
        rows[
            "endpoint_bounded_support_gate.audit_natural_domain_endpoint_excursions"
        ]["status"]
        == "empirical_execution_complete"
    )
    assert (
        rows[
            "endpoint_bounded_support_gate.run_positive_bounded_support_validity_protocol"
        ]["status"]
        == "empirical_validation_complete_no_bounded_support_claim"
    )
    assert (
        rows["endpoint_bounded_support_gate.refresh_bounded_support_claim_gate"][
            "status"
        ]
        == "gate_refresh_complete_no_bounded_support_claim"
    )
    assert (
        rows[
            "venn_abers_regression_validation_gate.design_validated_regression_venn_abers_method"
        ]["status"]
        == "protocol_design_complete"
    )
    assert (
        rows[
            "venn_abers_regression_validation_gate."
            "run_exact_grid_or_theory_validation_benchmark"
        ]["status"]
        == "optional_deferred_after_negative_disposition"
    )
    assert (
        rows[
            "fairness_population_inference_gate.compute_group_counts_missingness_and_gaps"
        ]["status"]
        == "empirical_execution_complete"
    )
    assert (
        rows[
            "fairness_population_inference_gate.declare_group_comparison_multiplicity_scope"
        ]["status"]
        == "multiplicity_control_complete"
    )
    assert (
        rows[
            "fairness_population_inference_gate.refresh_fairness_population_gate"
        ]["status"]
        == "gate_refresh_complete_no_fairness_claim"
    )
