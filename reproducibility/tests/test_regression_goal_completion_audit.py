import json
import subprocess
from pathlib import Path

from experiments.regression.scripts import build_goal_completion_audit as audit


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root: Path):
    report_dir = root / audit.REPORT_DIR
    write_json(
        root / audit.EXTERNAL_SOURCE_WATCHLIST,
        {
            "summary": {
                "overall_status": "external_source_discovery_watchlist_ready_with_gaps",
                "source_family_count": 3,
                "primary_source_family_count": 2,
                "local_audited_family_count": 2,
                "openml_discovery_rows": 10,
                "openml_ranked_rows": 3,
                "dataset_candidate_rows": 4,
                "pending_primary_family_count": 0,
            }
        },
    )
    write_json(
        root / audit.METHOD_LITERATURE,
        {
            "summary": {
                "overall_status": "method_literature_coverage_pass",
                "configured_cp_method_count": 4,
                "registry_method_count": 4,
                "runner_dispatch_method_count": 4,
                "literature_requirement_count": 2,
                "primary_source_url_count": 2,
                "tracked_gap_count": 0,
            }
        },
    )
    write_json(
        root / audit.METHOD_PERFORMANCE,
        {
            "summary": {
                "overall_status": "method_performance_synthesis_descriptive_no_final_selection",
                "failed_check_count": 0,
                "completed_ledger_rows": 20,
                "method_count": 4,
                "broad_support_method_count": 3,
                "dataset_count": 2,
                "dataset_alpha_cell_count": 4,
                "frontier_cell_count": 4,
                "top_frontier_methods": [{"cp_method": "cqr", "frontier_cell_count": 3}],
                "claim_status": "descriptive_no_final_selection",
            }
        },
    )
    write_json(
        root / audit.PUBLICATION_METHODOLOGY,
        {
            "summary": {
                "overall_status": "publication_workbench_ready_with_caveats",
                "manifest_count": 2,
                "bundle_index_manifest_count": 2,
                "failed_check_count": 0,
                "unsupported_claim_hits": 0,
                "hard_leakage_status": "hard_leakage_not_detected_in_scanned_artifacts",
                "open_remediation_actions": 0,
                "covered_remediation_actions": 3,
                "control_status_counts": {"pass": 2},
                "caveat_counts": {},
            }
        },
    )
    write_json(
        root / audit.EXPERIMENT_ACCOUNTING,
        {
            "summary": {
                "overall_status": "experiment_accounting_pass",
                "failed_check_count": 0,
                "ledger_file_count": 2,
                "raw_ledger_row_count": 30,
                "canonical_ledger_row_count": 25,
                "canonical_completed_row_count": 20,
                "publication_completed_rows": 20,
                "venn_grid_rows_completed": 5,
                "venn_grid_rows_pending": 0,
            }
        },
    )
    blocked_gates = [
        "dataset_specific_final_gates",
        "endpoint_bounded_support_gate",
        "fairness_population_inference_gate",
        "final_method_model_selection_gate",
        "multiplicity_selection_record",
        "venn_abers_regression_validation_gate",
    ]
    write_json(
        root / audit.PAPER_READINESS,
        {
            "summary": {
                "overall_status": "paper_readiness_blocked_with_evidence_map",
                "blocked_gate_count": 6,
            },
            "blocked_gates": [
                {"gate_id": gate_id, "status": "blocked"} for gate_id in blocked_gates
            ],
        },
    )
    write_json(
        root / audit.PAPER_GATE_CLOSURE,
        {
            "summary": {
                "overall_status": "paper_gate_closure_map_ready_no_promotions",
                "can_start_post_experiment_publication": False,
                "gate_count": 6,
                "blocked_gate_count": 6,
                "current_paper_blocking_gate_count": 5,
                "positive_claim_ready_gate_count": 0,
                "scoped_or_negative_path_ready_gate_count": 6,
                "local_execution_gap_gate_count": 0,
            },
            "gate_rows": [
                {
                    "gate_id": gate_id,
                    "current_status": "blocked",
                    "positive_claim_ready": False,
                    "scoped_or_negative_path_ready": True,
                    "closure_mode": "diagnostic_or_negative_path",
                    "gate_class": "test_gate",
                    "metrics": (
                        {"primary_candidate_method": "cqr"}
                        if gate_id == "final_method_model_selection_gate"
                        else {
                            "negative_result_reporting_ready": True,
                            "current_manuscript_positive_validation_required": False,
                        }
                        if gate_id == "venn_abers_regression_validation_gate"
                        else {}
                    ),
                    "next_decision": f"Resolve {gate_id}.",
                    "paper_allowed_language": ["diagnostic language"],
                    "paper_disallowed_language": ["positive claim"],
                    "source_artifacts": [],
                }
                for gate_id in blocked_gates
            ],
        },
    )
    write_json(
        root / audit.PAPER_GATE_EXECUTION_PLAN,
        {
            "summary": {
                "overall_status": "paper_gate_closure_execution_plan_ready",
                "action_count": 23,
                "ready_action_count": 0,
            }
        },
    )
    write_json(
        root / audit.PAPER_GATE_PROTOCOL_DESIGN_BUNDLE,
        {
            "summary": {
                "overall_status": (
                    "paper_gate_protocol_design_bundle_ready_no_claim_promotions"
                ),
                "completed_protocol_design_action_count": 4,
                "downstream_action_count": 5,
            }
        },
    )
    write_json(
        root / audit.BOUNDED_SUPPORT_POSITIVE_VALIDATION,
        {
            "summary": {
                "overall_status": (
                    "bounded_support_positive_validation_protocol_"
                    "completed_no_validity_claim"
                ),
                "action_status": (
                    "empirical_validation_complete_no_bounded_support_claim"
                ),
                "positive_acceptance_failed_count": 4,
                "interval_score_metrics_missing_bundle_count": 2,
                "positive_claim_ready_bundle_count": 0,
                "can_support_bounded_support_validity": False,
            }
        },
    )
    write_json(
        root / audit.FAIRNESS_SAMPLING_WEIGHT_POLICY,
        {
            "summary": {
                "overall_status": (
                    "fairness_sampling_weight_policy_defined_no_fairness_claim"
                ),
                "action_status": "protocol_design_complete",
            }
        },
    )
    write_json(
        root / audit.VENN_ABERS_NEGATIVE_DISPOSITION,
        {
            "summary": {
                "overall_status": "venn_abers_negative_evidence_disposition_pass",
                "negative_result_reporting_ready": True,
                "current_manuscript_positive_validation_required": False,
            }
        },
    )
    write_json(
        root / audit.POST_EXPERIMENT_PUBLICATION,
        {
            "status": "deferred_until_experimental_gates_complete",
            "activation_rule": {"requires_zero_blocked_paper_gates": True},
            "reviewer_design_gate": {"required_reviewer_pass_count": 5},
            "deliverables": ["main_article", "supplement"],
            "publication_author": {
                "author_name": "Emre Tasar",
                "author_email": "detasar@gmail.com",
            },
            "sterile_publication_repository_plan": {
                "status": "planned_after_full_experiment_closure"
            },
        },
    )
    write_json(
        root / audit.POST_EXPERIMENT_PUBLICATION_ACTIVATION,
        {
            "summary": {
                "overall_status": "post_experiment_publication_activation_blocked",
                "publication_phase_start_authorized": False,
                "manuscript_drafting_authorized": False,
                "blocked_check_count": 2,
                "caveat_check_count": 1,
            }
        },
    )
    write_json(
        root / audit.KG_QUALITY,
        {
            "issue_counts_by_severity": {},
            "graph": {
                "node_count": 10,
                "edge_count": 30,
                "edge_node_ratio": 3.0,
                "isolated_node_count": 0,
                "weak_component_count": 1,
            },
            "traceability": {
                "average_edge_confidence": 0.95,
                "explicit_edge_provenance_coverage": 1.0,
                "edge_selector_provenance_coverage": 1.0,
            },
            "freshness": {
                "working_tree_relevant_modified_count": 0,
                "working_tree_relevant_untracked_count": 0,
            },
            "observations": {"total_observation_count": 30},
        },
    )
    write_json(
        root / audit.GRAPH_ARTIFACT_READINESS,
        {"summary": {"overall_status": "graph_artifact_readiness_pass", "graph_count": 3}},
    )
    write_json(
        root / audit.SCIENTIFIC_REVIEW_FINDINGS,
        {
            "summary": {
                "overall_status": "scientific_review_findings_tracked_with_open_caveats",
                "hard_open_blocker_count": 0,
                "tracked_caveat_count": 1,
            }
        },
    )
    write_json(
        root / audit.MANUSCRIPT_BUNDLE_ELIGIBILITY,
        {
            "summary": {
                "bundle_count": 2,
                "final_claim_eligible_count": 0,
            }
        },
    )
    for path in (audit.CHANGELOG, audit.DATA_SCIENTIST_LOG):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text("checkpoint\n", encoding="utf-8")
    for path in (audit.CONTROL_FLOW, audit.DATA_FLOW, audit.DEPENDENCY_GRAPH):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text("graph TD\n", encoding="utf-8")

    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "regression-private", "https://example.com/private.git"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "fixture",
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )


def test_goal_completion_audit_minimal_fixture_closes_empirical_phase(tmp_path):
    write_minimal_sources(tmp_path)

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "goal_completion_audit_neutral_empirical_complete_publication_deferred"
    )
    assert payload["summary"]["can_mark_goal_complete"] is False
    assert payload["summary"]["can_start_post_experiment_publication"] is False
    assert payload["summary"]["neutral_empirical_phase_complete"] is True
    assert (
        payload["summary"]["empirical_completion_policy"]
        == "neutral_no_promotion_route_accepted"
    )
    assert payload["summary"]["blocked_positive_claim_requirement_count"] == 0
    assert payload["summary"]["positive_claim_blocking_gate_count"] == 6
    assert payload["summary"]["planned_deferred_requirement_count"] == 2
    assert payload["summary"]["in_progress_requirement_count"] == 0
    assert (
        payload["summary"]["can_start_post_experiment_publication_preparation"]
        is False
    )
    assert payload["summary"]["positive_claim_publication_ready"] is False
    assert payload["summary"]["neutral_publication_route_allowed"] is False
    assert payload["summary"]["final_dispositions_complete"] is True
    assert payload["summary"]["scoped_or_negative_path_ready_gate_count"] == 6
    assert payload["summary"]["current_paper_blocking_gate_count"] == 5
    assert payload["summary"]["primary_diagnostic_method"] == "cqr"
    assert payload["summary"]["validated_venn_abers_regression_claim_ready"] is False
    assert payload["summary"]["venn_abers_negative_result_reporting_ready"] is True
    assert payload["summary"]["paper_gate_protocol_design_complete_action_count"] == 4
    assert (
        payload["summary"]["post_experiment_publication_activation_status"]
        == "post_experiment_publication_activation_blocked"
    )
    assert (
        payload["summary"]["post_experiment_publication_phase_start_authorized"]
        is False
    )
    assert (
        payload["summary"][
            "post_experiment_private_manuscript_drafting_authorized"
        ]
        is None
    )
    assert (
        payload["summary"]["bounded_support_positive_validation_complete_action_count"]
        == 1
    )
    assert (
        payload["summary"]["bounded_support_positive_validation_claim_ready_bundle_count"]
        == 0
    )
    assert payload["summary"]["fairness_sampling_weight_policy_complete_action_count"] == 1
    assert {
        row["status"] for row in payload["requirement_rows"]
    } >= {"complete", "complete_with_scope_limits", "planned_deferred"}
    assert "blocked_positive_claim" not in {
        row["status"] for row in payload["requirement_rows"]
    }


def test_checked_in_goal_completion_audit_current_status_after_generation():
    payload = audit.build_payload(Path("."))
    rows = {row["requirement_id"]: row for row in payload["requirement_rows"]}

    assert payload["summary"]["requirement_count"] == 20
    assert payload["summary"]["can_mark_goal_complete"] is False
    assert payload["summary"]["neutral_empirical_phase_complete"] is True
    assert (
        payload["summary"]["overall_status"]
        == (
            "goal_completion_audit_neutral_empirical_complete_"
            "publication_preparation_active"
        )
    )
    assert payload["summary"]["paper_blocked_gate_count"] == 6
    assert payload["summary"]["blocked_positive_claim_requirement_count"] == 0
    assert payload["summary"]["positive_claim_blocking_gate_count"] == 6
    assert payload["summary"]["current_paper_blocking_gate_count"] == 5
    assert payload["summary"]["planned_deferred_requirement_count"] == 0
    assert payload["summary"]["in_progress_requirement_count"] == 1
    assert payload["summary"]["noncomplete_requirement_count"] == 1
    assert payload["summary"]["can_start_post_experiment_publication"] is True
    assert (
        payload["summary"]["can_start_post_experiment_publication_preparation"]
        is True
    )
    assert payload["summary"]["positive_claim_publication_ready"] is False
    assert payload["summary"]["neutral_publication_route_allowed"] is True
    assert payload["summary"]["final_dispositions_complete"] is True
    assert payload["summary"]["publication_completed_rows"] == 145839
    assert payload["summary"]["kg_node_count"] >= 3023
    assert payload["summary"]["kg_edge_count"] >= 18206
    assert payload["summary"]["primary_diagnostic_method"] == "cqr"
    assert payload["summary"]["paper_gate_closure_action_count"] >= 20
    assert payload["summary"]["paper_gate_closure_ready_action_count"] == 0
    assert payload["summary"]["paper_gate_protocol_design_complete_action_count"] == 4
    assert payload["summary"]["paper_gate_protocol_design_downstream_action_count"] == 5
    assert (
        payload["summary"]["post_experiment_publication_activation_status"]
        == "post_experiment_publication_preparation_active_with_caveats"
    )
    assert (
        payload["summary"]["post_experiment_publication_phase_start_authorized"]
        is True
    )
    assert (
        payload["summary"][
            "post_experiment_private_manuscript_drafting_authorized"
        ]
        is True
    )
    assert (
        payload["summary"]["post_experiment_manuscript_drafting_authorized"]
        is False
    )
    assert (
        payload["summary"][
            "post_experiment_publication_activation_blocked_check_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["bounded_support_positive_validation_status"]
        == "bounded_support_positive_validation_protocol_completed_no_validity_claim"
    )
    assert (
        payload["summary"]["bounded_support_positive_validation_complete_action_count"]
        == 1
    )
    assert (
        payload["summary"]["bounded_support_positive_validation_claim_ready_bundle_count"]
        == 0
    )
    assert (
        payload["summary"][
            "bounded_support_positive_validation_interval_score_missing_bundle_count"
        ]
        == 4
    )
    assert (
        payload["summary"]["fairness_sampling_weight_policy_status"]
        == "fairness_sampling_weight_policy_defined_no_fairness_claim"
    )
    assert payload["summary"]["fairness_sampling_weight_policy_complete_action_count"] == 1
    assert (
        rows["paper_gate:venn_abers_regression_validation_gate"]["status"]
        == "complete_with_scope_limits"
    )
    assert (
        rows["paper_gate:final_method_model_selection_gate"]["status"]
        == "complete_with_scope_limits"
    )
    assert (
        rows["paper_gate:endpoint_bounded_support_gate"]["status"]
        == "complete_with_scope_limits"
    )
    assert payload["summary"]["venn_abers_negative_result_reporting_ready"] is True
    assert rows["post_experiment_publication_program"]["status"] == "in_progress"
    sterile_repo = rows["sterile_final_publication_repository"]
    assert sterile_repo["status"] == "complete_with_scope_limits"
    assert (
        sterile_repo["metrics"]["private_package_status"]
        == "private_sterile_publication_package_ready"
    )
    assert sterile_repo["metrics"]["public_release_authorized"] is False
