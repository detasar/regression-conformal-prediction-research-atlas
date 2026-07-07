import json
from pathlib import Path

from experiments.regression.scripts import (
    build_dataset_final_gate_remediation_plan as plan,
)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_sources(root):
    blocked_gates = [
        {"gate_id": "dataset_specific_final_gates", "status": "blocked"},
        {"gate_id": "endpoint_bounded_support_gate", "status": "blocked"},
        {"gate_id": "fairness_population_inference_gate", "status": "blocked"},
        {"gate_id": "final_method_model_selection_gate", "status": "blocked"},
        {"gate_id": "multiplicity_selection_record", "status": "blocked"},
        {"gate_id": "venn_abers_regression_validation_gate", "status": "blocked"},
    ]
    write_json(
        root / plan.DATASET_FINAL_GATE,
        {
            "summary": {
                "overall_status": (
                    "dataset_specific_final_gate_audit_completed_no_final_"
                    "dataset_promotions"
                ),
                "dataset_count": 2,
            },
            "dataset_rows": [
                {
                    "dataset_id": "demo_candidate",
                    "bundle_count": 1,
                    "robustness_bundle_count": 0,
                    "main_result_promotion_ready_bundle_count": 0,
                    "has_main_result_ready_bundle": False,
                    "blocking_reason_counts": {
                        "bounded_support_validity_not_supported": 1,
                        "fairness_population_claim_not_ready": 1,
                        "final_selection_claim_blocked": 1,
                        "main_results_surface_blocked": 1,
                    },
                },
                {
                    "dataset_id": "demo_without_bridge",
                    "bundle_count": 2,
                    "robustness_bundle_count": 2,
                    "main_result_promotion_ready_bundle_count": 0,
                    "has_main_result_ready_bundle": False,
                    "blocking_reason_counts": {
                        "not_indexed_as_main_result_bundle": 2,
                        "bounded_support_validity_not_supported": 2,
                        "fairness_population_claim_not_ready": 2,
                        "final_selection_claim_blocked": 2,
                        "main_results_surface_blocked": 2,
                    },
                },
            ],
        },
    )
    write_json(
        root / plan.METHOD_SELECTION_POST_SELECTION_VALIDATION_RESULTS,
        {
            "dataset_rows": [
                {
                    "dataset_id": "demo_candidate",
                    "config_path": "experiments/regression/configs/demo_validation.yaml",
                    "completed_atomic_run_count": 45,
                    "expected_atomic_run_count": 45,
                }
            ]
        },
    )
    write_json(
        root / plan.MAIN_RESULT_CANDIDATE_BUNDLE_PLAN,
        {
            "candidate_rows": [
                {
                    "dataset_id": "demo_candidate",
                    "config_path": "experiments/regression/configs/demo_candidate.yaml",
                    "expected_atomic_run_count": 45,
                }
            ]
        },
    )
    write_json(
        root / plan.MAIN_RESULT_CANDIDATE_BUNDLE_RESULTS,
        {
            "dataset_rows": [
                {
                    "dataset_id": "demo_candidate",
                    "completed_atomic_run_count": 45,
                    "expected_atomic_run_count": 45,
                }
            ]
        },
    )
    write_json(
        root / plan.MAIN_RESULT_CANDIDATE_POST_RUN_CLOSURE,
        {
            "dataset_rows": [
                {
                    "dataset_id": "demo_candidate",
                    "closure_status": "post_run_closure_ready_with_caveats",
                    "blocker_count": 0,
                }
            ]
        },
    )
    write_json(
        root / plan.PAPER_READINESS,
        {
            "summary": {
                "overall_status": "paper_readiness_blocked_with_evidence_map",
                "blocked_gate_count": 6,
            },
            "blocked_gates": blocked_gates,
        },
    )
    write_json(
        root / plan.BOUNDED_SUPPORT_DATASET_AUDIT,
        {
            "rows": [
                {
                    "bundle_id": "demo_candidate_bundle",
                    "dataset_id": "demo_candidate",
                    "endpoint_support_status": (
                        "clean_no_natural_domain_endpoint_excursions"
                    ),
                    "posthandling_support_status": "validated_all_completed_rows",
                    "blockers": [
                        "global_bounded_support_validity_claim_disabled"
                    ],
                },
                {
                    "bundle_id": "demo_without_bridge_bundle",
                    "dataset_id": "demo_without_bridge",
                    "endpoint_support_status": (
                        "blocked_natural_domain_endpoint_excursions"
                    ),
                    "posthandling_support_status": "validated_all_completed_rows",
                    "blockers": [
                        "natural_domain_endpoint_excursions",
                        "global_bounded_support_validity_claim_disabled",
                    ],
                },
            ]
        },
    )


def test_remediation_plan_prioritizes_missing_validation_bridge(tmp_path):
    write_sources(tmp_path)

    payload = plan.build_payload(tmp_path)
    rows = {row["dataset_id"]: row for row in payload["dataset_rows"]}
    missing = rows["demo_without_bridge"]
    candidate = rows["demo_candidate"]

    assert (
        payload["summary"]["overall_status"]
        == "dataset_final_gate_remediation_plan_ready_no_promotions"
    )
    assert payload["summary"]["dataset_count"] == 2
    assert payload["summary"]["missing_post_selection_validation_bridge_count"] == 1
    assert payload["summary"]["post_selection_validation_bridge_config_count"] == 0
    assert (
        payload["summary"]["missing_post_selection_validation_bridge_config_count"]
        == 1
    )
    assert (
        payload["summary"]["post_selection_validation_bridge_execution_pending_count"]
        == 0
    )
    assert payload["summary"]["post_selection_validation_bridge_results_count"] == 0
    assert payload["summary"]["missing_main_result_candidate_bundle_count"] == 1
    assert payload["summary"]["executable_action_count"] == 13
    assert payload["summary"]["action_scope_counts"] == {
        "global_gate_dependency": 6,
        "local_dataset_remediation": 3,
        "post_closure_refresh": 4,
    }
    assert payload["summary"]["local_dataset_remediation_action_count"] == 3
    assert payload["summary"]["global_gate_dependency_action_count"] == 6
    assert payload["summary"]["post_closure_refresh_action_count"] == 4
    assert (
        payload["summary"]["dataset_with_local_dataset_remediation_action_count"]
        == 1
    )
    assert (
        payload["summary"]["dataset_blocked_only_by_global_gate_dependencies_count"]
        == 1
    )
    assert payload["summary"]["dataset_with_no_remaining_execution_gap_count"] == 1
    assert (
        payload["summary"]["completed_main_result_candidate_results_dataset_count"] == 1
    )
    assert payload["summary"]["candidate_post_run_closure_ready_dataset_count"] == 1
    assert (
        payload["summary"][
            "bounded_support_endpoint_blocked_or_incomplete_dataset_count"
        ]
        == 1
    )
    assert payload["summary"]["bounded_support_global_no_claim_dataset_count"] == 2
    assert (
        payload["summary"][
            "bounded_support_endpoint_clean_or_not_applicable_only_dataset_count"
        ]
        == 1
    )
    assert (
        payload["summary"]["readiness_status_counts"][
            "blocked_missing_post_selection_validation_bridge"
        ]
        == 1
    )
    assert missing["primary_next_action"] == "build_post_selection_validation_bridge"
    assert missing["has_post_selection_validation_source"] is False
    assert missing["has_post_selection_validation_bridge_config"] is False
    assert missing["has_main_result_candidate_bundle"] is False
    assert {item["action_id"] for item in missing["executable_next_actions"]} >= {
        "build_post_selection_validation_bridge",
        "add_dataset_to_main_result_candidate_bundle_plan",
    }
    assert (
        candidate["primary_next_action"]
        == "resolve_global_bounded_support_validity_claim_gate"
    )
    assert (
        candidate["readiness_status"]
        == "blocked_bounded_support_global_validity_claim"
    )
    assert candidate["action_scope_counts"] == {
        "global_gate_dependency": 3,
        "post_closure_refresh": 2,
    }
    assert candidate["blocked_only_by_global_gate_dependencies"] is True
    assert candidate["bounded_support_endpoint_clean_bundle_count"] == 1
    assert candidate["bounded_support_endpoint_blocked_or_incomplete_bundle_count"] == 0
    assert candidate["bounded_support_global_no_claim_bundle_count"] == 1
    assert candidate["has_completed_main_result_candidate_results"] is True


def test_checked_in_plan_closes_uci_wine_candidate_bridge_gap():
    payload = plan.build_payload(Path("."))
    rows = {row["dataset_id"]: row for row in payload["dataset_rows"]}
    uci = rows["uci_wine_quality"]

    assert payload["summary"]["dataset_count"] == 6
    assert payload["summary"]["ready_dataset_count"] == 0
    assert payload["summary"]["missing_post_selection_validation_bridge_count"] == 0
    assert payload["summary"]["post_selection_validation_bridge_config_count"] == 1
    assert (
        payload["summary"]["missing_post_selection_validation_bridge_config_count"]
        == 0
    )
    assert (
        payload["summary"]["post_selection_validation_bridge_execution_pending_count"]
        == 0
    )
    assert payload["summary"]["post_selection_validation_bridge_results_count"] == 1
    assert payload["summary"]["missing_main_result_candidate_bundle_count"] == 0
    assert (
        payload["summary"]["completed_main_result_candidate_results_dataset_count"] == 6
    )
    assert payload["summary"]["candidate_post_run_closure_ready_dataset_count"] == 6
    assert (
        payload["summary"][
            "bounded_support_endpoint_blocked_or_incomplete_dataset_count"
        ]
        == 5
    )
    assert payload["summary"]["bounded_support_global_no_claim_dataset_count"] == 6
    assert (
        payload["summary"][
            "bounded_support_endpoint_clean_or_not_applicable_only_dataset_count"
        ]
        == 1
    )
    assert payload["summary"]["bounded_support_endpoint_closure_dataset_count"] == 6
    assert (
        payload["summary"]["bounded_support_endpoint_closure_open_backfill_dataset_count"]
        == 0
    )
    assert (
        payload["summary"]["bounded_support_endpoint_policy_closed_dataset_count"] == 6
    )
    assert (
        payload["summary"][
            "bounded_support_endpoint_blocked_but_policy_closed_dataset_count"
        ]
        == 5
    )
    assert (
        payload["summary"][
            "bounded_support_endpoint_requiring_local_remediation_dataset_count"
        ]
        == 0
    )
    assert payload["summary"]["readiness_status_counts"] == {
        "blocked_bounded_support_global_validity_claim": 6,
    }
    assert (
        "resolve_natural_domain_endpoint_support_blockers"
        not in payload["summary"]["action_counts"]
    )
    assert payload["summary"]["action_counts"][
        "resolve_global_bounded_support_validity_claim_gate"
    ] == 6
    assert payload["summary"][
        "missing_post_selection_validation_bridge_dataset_ids"
    ] == []
    assert payload["summary"][
        "post_selection_validation_bridge_config_dataset_ids"
    ] == ["uci_wine_quality"]
    assert payload["summary"][
        "post_selection_validation_bridge_results_dataset_ids"
    ] == ["uci_wine_quality"]
    assert payload["summary"][
        "missing_post_selection_validation_bridge_config_dataset_ids"
    ] == []
    assert payload["summary"]["missing_main_result_candidate_bundle_dataset_ids"] == []
    assert payload["summary"]["executable_action_count"] == 30
    assert payload["summary"]["action_scope_counts"] == {
        "global_gate_dependency": 18,
        "post_closure_refresh": 12,
    }
    assert payload["summary"]["local_dataset_remediation_action_count"] == 0
    assert payload["summary"]["global_gate_dependency_action_count"] == 18
    assert payload["summary"]["post_closure_refresh_action_count"] == 12
    assert (
        payload["summary"]["dataset_with_local_dataset_remediation_action_count"]
        == 0
    )
    assert (
        payload["summary"]["dataset_blocked_only_by_global_gate_dependencies_count"]
        == 6
    )
    assert payload["summary"]["dataset_with_no_remaining_execution_gap_count"] == 6
    assert (
        uci["readiness_status"]
        == "blocked_bounded_support_global_validity_claim"
    )
    assert (
        uci["primary_next_action"]
        == "resolve_global_bounded_support_validity_claim_gate"
    )
    assert uci["bounded_support_endpoint_clean_bundle_count"] == 2
    assert uci["action_scope_counts"] == {
        "global_gate_dependency": 3,
        "post_closure_refresh": 2,
    }
    assert uci["blocked_only_by_global_gate_dependencies"] is True
    assert uci["bounded_support_endpoint_blocked_or_incomplete_bundle_count"] == 1
    assert uci["bounded_support_global_no_claim_bundle_count"] == 3
    assert (
        uci["bounded_support_endpoint_closure_status"]
        == "triaged_raw_endpoint_excursions_no_validity_claim"
    )
    assert uci["bounded_support_endpoint_closure_next_action_ids"] == [
        "maintain_no_bounded_support_validity_claim"
    ]
    assert uci["bounded_support_endpoint_closure_open_backfill"] is False
    assert uci["bounded_support_endpoint_policy_closed_by_closure_audit"] is True
    assert uci["bounded_support_endpoint_blocked_but_policy_closed"] is True
    assert uci["has_post_selection_validation_source"] is True
    assert uci["has_standard_post_selection_validation_source"] is False
    assert uci["has_post_selection_validation_bridge_results"] is True
    assert uci["post_selection_validation_source_kind"] == (
        "dataset_final_gate_bridge_results"
    )
    assert uci["post_selection_validation_completed_atomic_run_count"] == 45
    assert uci["post_selection_validation_expected_atomic_run_count"] == 45
    assert uci["has_main_result_candidate_bundle"] is True
    assert uci["has_completed_main_result_candidate_results"] is True
    assert uci["main_result_candidate_completed_atomic_run_count"] == 45
    assert uci["candidate_post_run_closure_status"] == "post_run_closure_ready_with_caveats"
    assert uci["has_post_selection_validation_bridge_config"] is True
    assert (
        uci["post_selection_validation_bridge_execution_status"]
        == "completed_bridge_results"
    )
    assert (
        uci["post_selection_validation_bridge_config_path"]
        == "experiments/regression/configs/"
        "method_selection_post_selection_validation_bridge_uci_wine_quality.yaml"
    )
    assert uci["post_selection_validation_bridge_expected_atomic_run_count"] == 45
    assert "add_dataset_to_main_result_candidate_bundle_plan" not in {
        item["action_id"] for item in uci["executable_next_actions"]
    }
