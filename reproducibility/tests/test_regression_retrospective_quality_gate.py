import json

from experiments.regression.scripts import run_retrospective_quality_gate as gate


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_existing_step_results_for_summary_reuses_checked_in_steps(tmp_path):
    gate_path = tmp_path / "retrospective_quality_gate.json"
    write_json(
        gate_path,
        {
            "complete": True,
            "steps": [
                {
                    "step_id": "cross_run_integrity",
                    "family": "methodology",
                    "status": "pass",
                    "duration_seconds": 0.1,
                    "outputs": {"all_present": True},
                }
            ],
        },
    )

    steps, complete = gate.existing_step_results_for_summary(gate_path)

    assert complete is True
    assert len(steps) == 1
    assert steps[0]["step_id"] == "cross_run_integrity"


def test_existing_step_results_for_summary_blocks_empty_manifest(tmp_path):
    gate_path = tmp_path / "retrospective_quality_gate.json"
    write_json(gate_path, {"complete": True, "steps": []})

    steps, complete = gate.existing_step_results_for_summary(gate_path)

    assert steps == []
    assert complete is False


def write_minimal_artifacts(
    root, *, hard_leakage=False, kg_medium_issue=False, caveat=True
):
    report_dir = root / gate.REPORT_DIR
    manuscript_dir = root / "experiments/regression/manuscript"
    write_json(
        report_dir / "cross_run_integrity_audit.json",
        {
            "summary": {
                "reports_scanned": 2,
                "configs_scanned": 3,
                "total_completed_rows": 5,
                "blocking_issue_counts": (
                    {"row_id_overlap_detected": 1} if hard_leakage else {}
                ),
                "caveat_counts": (
                    {"feature_leakage_metadata_completeness_caveat": 1}
                    if caveat
                    else {}
                ),
                "unsupported_claim_hits": 0,
                "leakage_status": (
                    "blocking_issue_detected"
                    if hard_leakage
                    else "hard_leakage_not_detected_in_scanned_artifacts"
                ),
            }
        },
    )
    write_json(
        report_dir / "retrospective_methodology_controls.json",
        {
            "summary": {
                "control_status_counts": (
                    {"pass": 8, "caveat": 3} if caveat else {"pass": 11}
                ),
                "control_severity_counts": (
                    {"none": 8, "medium": 3} if caveat else {"none": 11}
                ),
                "hard_leakage_status": (
                    "hard_leakage_or_guard_failure_detected"
                    if hard_leakage
                    else "no_hard_leakage_detected_in_scanned_artifacts"
                ),
            }
        },
    )
    write_json(
        report_dir / "feature_leakage_metadata_completeness_triage.json",
        {
            "summary": {
                "caveat_rows_triaged": 1,
                "runner_feature_drop_guard_ok": True,
                "hard_feature_leakage_violation_row_count": 1 if hard_leakage else 0,
                "metadata_limitation_class_counts": {
                    "preprocessed_feature_names_missing_only": 1
                },
            }
        },
    )
    write_json(
        report_dir / "integrity_remediation_backlog.json",
        {
            "summary": {
                "open_action_count": 1,
                "severity_counts": {"low": 1},
                "category_counts": {"feature_leakage_preprocessed_name_closure": 1},
            }
        },
    )
    write_json(
        report_dir / "duplicate_sensitivity_closure_audit.json",
        {
            "summary": {
                "overall_status": (
                    "scoped_duplicate_sensitivity_closure_pass_with_caveats"
                    if caveat
                    else "scoped_duplicate_sensitivity_closure_pass"
                ),
                "duplicate_action_count": 21,
                "duplicate_caveat_count": 21,
                "row_signature_caveat_count": 10,
                "model_visible_caveat_count": 11,
                "open_action_count": 0,
                "covered_action_count": 21,
                "hard_failed_check_count": 0,
                "scoped_caveat_check_count": 2 if caveat else 0,
                "paired_dataset_count": 3,
                "paired_comparison_rows": 1043,
                "final_blocked_requirement_count": 6,
            }
        },
    )
    write_json(
        report_dir / "duplicate_content_quarantine_audit.json",
        {
            "summary": {
                "overall_status": "duplicate_content_quarantine_pass",
                "failed_check_count": 0,
                "duplicate_action_count": 21,
                "manuscript_candidate_action_count": 9,
                "non_manuscript_action_count": 12,
                "quarantined_action_count": 21,
                "unquarantined_action_count": 0,
                "main_results_eligible_action_count": 0,
                "caveat_label_missing_action_count": 0,
                "linked_final_claim_action_count": 0,
                "quarantine_status_counts": {
                    "candidate_caveated_and_main_blocked": 9,
                    "not_manuscript_candidate": 12,
                },
            }
        },
    )
    write_json(
        report_dir / "venn_abers_negative_evidence_disposition_audit.json",
        {
            "summary": {
                "overall_status": "venn_abers_negative_evidence_disposition_pass",
                "failed_check_count": 0,
                "negative_claim_present": True,
                "can_support_validated_venn_abers_regression": False,
                "undercoverage_run_count": 14,
                "validation_blocker_count": 3,
                "positive_claim_blocked_count": 3,
                "shortlist_method_count": 3,
                "shortlist_venn_abers_method_count": 0,
                "excluded_venn_abers_method_count": 2,
                "excluded_with_validation_gate_count": 2,
                "venn_bundle_row_count": 3,
                "venn_bundle_main_eligible_count": 0,
                "venn_bundle_main_unblocked_count": 0,
                "bundle_main_results_eligible_count": 0,
                "final_selection_venn_abers_gate_status": "blocked",
                "excluded_venn_abers_reason_counts": {
                    "frontier_cell_count_below_shortlist_threshold": 2,
                    "venn_abers_validation_gate_blocked": 2,
                },
            }
        },
    )
    write_json(
        report_dir / "endpoint_schema_backfill_feasibility.json",
        {
            "summary": {
                "ready_count": 2,
                "blocked_count": 0,
                "status_counts": {"ready_for_v2_reconstruction": 2},
                "completed_ledger_rows_ready": 10,
            }
        },
    )
    write_json(
        root / gate.KG_QUALITY_OUT,
        {
            "issue_counts_by_severity": {"medium": 1} if kg_medium_issue else {},
            "graph": {
                "node_count": 10,
                "edge_count": 25,
                "edge_node_ratio": 2.5,
                "isolated_node_count": 0,
                "weak_component_count": 1,
            },
            "traceability": {
                "average_edge_confidence": 0.94,
                "distinct_edge_confidence_value_count": 4,
                "explicit_edge_provenance_coverage": 1.0,
                "specific_edge_provenance_coverage": 1.0,
                "edge_selector_provenance_coverage": 0.43,
                "edge_confidence_coverage": 1.0,
                "edge_confidence_reason_coverage": 1.0,
                "weak_provenance_confidence_one_count": 0,
            },
            "observations": {
                "observation_node_ratio": 1.2,
                "paper_evidence_observation_node_ratio": 1.1,
                "topology_observation_count": 10,
                "total_observation_count": 12,
            },
            "summaries": {
                "direct_summary_coverage": 1.0,
                "semantic_summary_coverage": 1.0,
            },
            "ontology": {
                "unknown_node_types": [],
                "unknown_relation_types": [],
                "domain_range_violation_count": 0,
            },
        },
    )
    write_json(
        report_dir / "manuscript_manifest_completeness_audit.json",
        {
            "summary": {
                "overall_status": "pass",
                "manifest_count": 14,
                "status_counts": {"pass": 14},
                "bundle_index_status": "pass",
                "bundle_index_manifest_count": 14,
            }
        },
    )
    write_json(
        report_dir / "manuscript_claim_register_consistency_audit.json",
        {
            "summary": {
                "overall_status": "pass",
                "claim_count": 2,
                "status_counts": {"pass": 2},
                "failed_claim_count": 0,
            }
        },
    )
    write_json(
        report_dir / "final_selection_claim_boundary_audit.json",
        {
            "summary": {
                "overall_status": "pass",
                "claim_status": "blocked",
                "open_remediation_actions": 0,
                "blocked_requirement_count": 6,
                "pass_requirement_count": 1,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        report_dir / "fairness_population_readiness_audit.json",
        {
            "summary": {
                "overall_status": "fairness_population_readiness_audit_completed_no_fairness_claim",
                "failed_check_count": 0,
                "can_support_publication_ready_fairness": False,
                "fairness_population_claim_status": "blocked_diagnostic_only",
                "fairness_requirement_status": "blocked",
                "final_selection_claim_status": "blocked",
                "bundle_count": 9,
                "diagnostic_group_bundle_count": 9,
                "explicit_nonclaim_boundary_bundle_count": 9,
                "population_fairness_ready_bundle_count": 0,
                "sampling_weight_policy_artifact_status": (
                    "fairness_sampling_weight_policy_defined_no_fairness_claim"
                ),
                "sampling_weight_policy_declared_bundle_count": 2,
                "weighted_estimand_applied_bundle_count": 0,
                "fairness_group_multiplicity_scope_status": (
                    "fairness_group_multiplicity_scope_declared_no_fairness_claim"
                ),
                "multiplicity_scope_declared_bundle_count": 2,
                "claim_register_cites_multiplicity_record": True,
            }
        },
    )
    write_json(
        report_dir / "fairness_group_diagnostic_audit.json",
        {
            "summary": {
                "overall_status": (
                    "fairness_group_diagnostic_audit_completed_no_fairness_claim"
                ),
                "action_status": "empirical_execution_complete",
                "bundle_count": 2,
                "dataset_count": 1,
                "group_counts_recorded_bundle_count": 2,
                "missingness_by_group_audited_bundle_count": 2,
                "coverage_by_group_recorded_bundle_count": 2,
                "width_by_group_recorded_bundle_count": 2,
                "group_gap_uncertainty_recorded_bundle_count": 2,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "fairness_group_multiplicity_scope.json",
        {
            "summary": {
                "overall_status": (
                    "fairness_group_multiplicity_scope_declared_no_fairness_claim"
                ),
                "action_status": "multiplicity_control_complete",
                "bundle_count": 2,
                "dataset_count": 1,
                "comparison_family_count": 2,
                "pairwise_group_comparison_count": 2,
                "multiplicity_scope_declared_bundle_count": 2,
                "claim_register_cites_multiplicity_record": True,
                "current_manuscript_fairness_population_claim_ready": False,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        report_dir / "publication_methodology_audit.json",
        {
            "summary": {
                "overall_status": (
                    "publication_workbench_ready_with_caveats"
                    if caveat
                    else "publication_workbench_ready"
                ),
                "reports_scanned": 2,
                "total_completed_rows": 5,
                "unsupported_claim_hits": 0,
                "open_remediation_actions": 0,
                "blocked_final_requirement_count": 6,
                "failed_check_count": 0,
                "can_support_final_method_selection": False,
                "can_support_publication_ready_fairness": False,
                "can_support_bounded_support_validity": False,
                "can_support_venn_abers_regression_validation": False,
            }
        },
    )
    write_json(
        report_dir / "venn_abers_validation_readiness_audit.json",
        {
            "summary": {
                "overall_status": "venn_abers_validation_blocked_with_negative_evidence",
                "can_support_venn_abers_regression_validation": False,
                "failed_check_count": 0,
                "diagnostic_panel_count": 3,
                "undercoverage_panel_count": 3,
                "grid_reference_stronger_panel_count": 3,
                "split_fallback_near_nominal_panel_count": 3,
                "validation_requirement_status": "blocked",
                "negative_evidence_requirement_status": "present",
                "mean_venn_abers_coverage_by_panel": {
                    "report:venn_abers_real_data_diagnostic": 0.64,
                    "report:venn_abers_fairness_panel_diagnostic": 0.60,
                    "report:venn_abers_biomarker_clinical_panel_diagnostic": 0.67,
                },
            }
        },
    )
    write_json(
        report_dir / "venn_abers_grid_ivapd_validation_protocol.json",
        {
            "summary": {
                "overall_status": "venn_abers_grid_ivapd_validation_protocol_defined_no_claim",
                "failed_check_count": 0,
                "can_support_validated_venn_abers_regression": False,
                "can_support_exact_grid_venn_abers_validation": False,
                "can_support_ivapd_interval_cp_validation": False,
                "grid_reference_validation_status": "blocked",
                "ivapd_interval_cp_status": "blocked_predictive_distribution_only",
                "validation_blocker_count": 4,
                "validation_blocker_ids": [
                    "grid_reference_rows_below_claim_floor",
                    "grid_reference_not_full_test_scored",
                    "grid_reference_panel_coverage_below_nominal",
                    "ivapd_threshold_grid_is_predictive_distribution_not_interval_cp",
                ],
                "total_grid_reference_rows_scored": 82,
                "total_grid_reference_rows_available": 1400,
                "grid_reference_scored_fraction": 0.058,
                "min_panel_grid_reference_coverage": 0.733,
                "max_panel_grid_reference_coverage": 0.906,
                "max_panel_grid_hit_upper_rate": 0.1,
                "total_ivapd_rows_scored": 250,
                "total_ivapd_rows_available": 1400,
                "ivapd_scored_fraction": 0.179,
                "final_validation_requirement_status": "blocked",
            }
        },
    )
    write_json(
        report_dir / "venn_abers_grid_expansion_plan.json",
        {
            "summary": {
                "overall_status": "venn_abers_grid_expansion_plan_ready",
                "failed_check_count": 0,
                "source_report_count": 3,
                "run_task_count": 14,
                "task_status_counts": {"pending": 14},
                "task_count_by_report": {
                    "report:venn_abers_biomarker_clinical_panel_diagnostic": 6,
                    "report:venn_abers_fairness_panel_diagnostic": 4,
                    "report:venn_abers_real_data_diagnostic": 4,
                },
                "total_test_rows_available": 6001,
                "total_grid_rows_completed": 82,
                "total_grid_rows_pending": 5919,
                "grid_completion_fraction": 0.013664389268455257,
                "next_batch_total_rows": 340,
                "duplicate_next_batch_task_key_count": 0,
                "largest_pending_tasks": [
                    {
                        "report_id": "report:venn_abers_fairness_panel_diagnostic",
                        "run_id": "3040213189326a1c7d7f",
                        "dataset_id": "aif360_lawschool_gpa",
                        "model_id": "ridge",
                        "pending_row_count": 4464,
                        "test_rows_available": 4469,
                    }
                ],
            }
        },
    )
    write_json(
        report_dir / "venn_abers_grid_failure_mode_decomposition.json",
        {
            "summary": {
                "overall_status": "venn_abers_grid_failure_modes_decomposed_no_claim",
                "failed_check_count": 0,
                "claim_status": "no_validated_venn_abers_regression_claim",
                "can_support_validated_venn_abers_regression": False,
                "validation_blocker_count": 4,
                "validation_blocker_ids": [
                    "grid_reference_rows_below_claim_floor",
                    "grid_reference_not_full_test_scored",
                    "grid_reference_panel_coverage_below_nominal",
                    "ivapd_threshold_grid_is_predictive_distribution_not_interval_cp",
                ],
                "coverage_failure_panel_count": 3,
                "coverage_failure_run_count": 8,
                "coverage_failure_dataset_count": 4,
                "upper_boundary_failure_panel_count": 2,
                "upper_boundary_failure_run_count": 5,
                "upper_boundary_failure_dataset_count": 3,
                "total_grid_reference_rows_scored": 82,
                "total_grid_reference_rows_available": 1400,
                "min_run_grid_reference_coverage": 0.733,
                "max_run_grid_hit_upper_rate": 0.2,
                "dominant_coverage_deficit_run_id": "toy_coverage",
                "dominant_upper_boundary_run_id": "toy_upper",
            }
        },
    )
    write_json(
        report_dir / "venn_abers_claim_gate_matrix.json",
        {
            "summary": {
                "overall_status": "venn_abers_claim_gate_matrix_blocked_with_complete_evidence",
                "failed_check_count": 0,
                "can_support_validated_venn_abers_regression": False,
                "positive_claim_requirement_count": 4,
                "positive_claim_pass_count": 0,
                "positive_claim_blocked_count": 4,
                "blocked_positive_requirement_ids": [
                    "score_grid_full_test_scored",
                    "score_grid_panel_coverage_nominal",
                    "score_grid_upper_boundary_free",
                    "ivapd_interval_cp_validated",
                ],
                "total_grid_reference_rows_scored": 82,
                "total_grid_reference_rows_available": 1400,
                "min_panel_grid_reference_coverage": 0.733,
                "max_panel_grid_hit_upper_rate": 0.1,
                "ivapd_interval_cp_status": ("blocked_predictive_distribution_only"),
            }
        },
    )
    write_json(
        report_dir / "method_literature_coverage_audit.json",
        {
            "summary": {
                "overall_status": "method_literature_coverage_pass",
                "literature_requirement_count": 16,
                "status_counts": {"pass": 16},
                "hard_failed_requirement_count": 0,
                "tracked_gap_count": 0,
                "registry_method_count": 28,
                "runner_dispatch_method_count": 28,
                "configured_cp_method_count": 29,
                "primary_source_url_count": 15,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        root / "experiments/regression/manuscript/selection_multiplicity_protocol.json",
        {
            "summary": {
                "overall_status": "selection_multiplicity_protocol_defined_no_final_selection",
                "required_manifest_field_count": 8,
                "covered_manifest_field_count": 8,
                "failed_check_count": 0,
                "eligibility_filter_count": 10,
                "ranking_scope_count": 15,
                "selection_record_count": 1,
                "linked_indexed_bundle_count": 15,
                "unlinked_indexed_bundle_count": 0,
                "completed_ledger_rows_scanned": 145839,
                "can_support_final_method_selection": False,
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        root / "experiments/regression/manuscript/bounded_support_protocol.json",
        {
            "summary": {
                "overall_status": "bounded_support_protocol_defined_no_validity_claim",
                "failed_check_count": 0,
                "target_domain_class_count": 5,
                "interval_handling_policy_count": 4,
                "required_evidence_count": 11,
                "bounded_support_policy_field_present": True,
                "can_support_bounded_support_validity": False,
                "publication_can_support_bounded_support_validity": False,
                "endpoint_bounded_support_gate_status": "blocked",
                "final_selection_claim_status": "blocked",
                "manuscript_endpoint_result_count": 105,
                "manuscript_endpoint_caveat_count": 91,
                "kg_endpoint_result_count": 458,
                "kg_endpoint_caveat_count": 404,
            }
        },
    )
    write_json(
        root / "experiments/regression/catalogs/target_domain_provenance.json",
        {
            "summary": {
                "overall_status": "target_domain_provenance_ready",
                "failed_check_count": 0,
                "row_count": 5,
                "source_artifact_complete_count": 5,
                "external_source_row_count": 1,
                "bounded_ordinal_row_count": 1,
            }
        },
    )
    write_json(
        root
        / "experiments/regression/catalogs/external_source_discovery_watchlist.json",
        {
            "summary": {
                "overall_status": "external_source_discovery_watchlist_ready_with_gaps",
                "source_family_count": 19,
                "primary_source_family_count": 18,
                "secondary_source_family_count": 1,
                "implemented_or_active_family_count": 18,
                "pending_primary_family_count": 0,
                "local_audited_family_count": 18,
                "local_reported_family_count": 12,
                "official_url_count": 18,
                "openml_discovery_rows": 675,
                "openml_ranked_rows": 68,
                "dataset_candidate_rows": 91,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        root
        / "experiments/regression/manuscript/bounded_support_posthandling_validation.json",
        {
            "summary": {
                "overall_status": "bounded_support_posthandling_validation_completed",
                "available_bundle_count": 14,
                "selected_bundle_count": 14,
                "validated_bundle_count": 14,
                "unvalidated_bundle_count": 0,
                "reconstructed_runs": 14304,
                "completed_ledger_rows": 14304,
                "filtered_completed_ledger_rows": 14304,
                "total_completed_ledger_rows_in_selected_bundles": 14304,
                "reconstruction_failures": 0,
                "clip_policy_support_clean_bundle_count": 14,
                "state_resumed_records": 14304,
                "state_written_records": 0,
                "can_support_all_current_bounded_support_claims": False,
            }
        },
    )
    write_json(
        root / "experiments/regression/manuscript/bounded_support_dataset_audit.json",
        {
            "summary": {
                "overall_status": "dataset_bounded_support_audit_completed_no_validity_claim",
                "failed_check_count": 0,
                "bundle_count": 14,
                "unique_dataset_count": 6,
                "endpoint_audited_bundle_count": 14,
                "bounded_support_ready_bundle_count": 0,
                "endpoint_support_clean_bundle_count": 2,
                "endpoint_support_not_applicable_bundle_count": 1,
                "endpoint_support_blocked_or_incomplete_bundle_count": 11,
                "endpoint_support_status_counts": {
                    "clean_no_natural_domain_endpoint_excursions": 2,
                    "not_applicable_unbounded_target_endpoint_hygiene_recorded": 1,
                    "blocked_natural_domain_endpoint_excursions": 11,
                },
                "posthandling_support_status_counts": {
                    "validated_all_completed_rows": 14
                },
                "target_domain_class_counts": {
                    "bounded_continuous": 3,
                    "bounded_ordinal": 2,
                    "nonnegative": 8,
                    "unbounded_real": 1,
                },
                "blocker_counts": {
                    "global_bounded_support_validity_claim_disabled": 14,
                    "natural_domain_endpoint_excursions": 11,
                },
                "natural_domain_excursion_bundle_count": 11,
                "natural_domain_excursion_unknown_count_bundle_count": 0,
                "observed_range_excursion_bundle_count": 14,
                "target_domain_provenance_status": "target_domain_provenance_ready",
                "can_support_bounded_support_validity": False,
                "endpoint_bounded_support_gate_status": "blocked",
            }
        },
    )
    write_json(
        report_dir / "bounded_support_endpoint_closure_audit.json",
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
                "bundle_count": 14,
                "dataset_count": 6,
                "closed_policy_bundle_count": 14,
                "open_endpoint_count_backfill_bundle_count": 0,
                "raw_endpoint_excursion_bundle_count": 11,
                "endpoint_clean_or_not_applicable_bundle_count": 3,
                "posthandling_validated_bundle_count": 14,
                "global_no_claim_bundle_count": 14,
                "bounded_support_validity_claim_ready_bundle_count": 0,
                "can_support_bounded_support_validity": False,
                "current_manuscript_bounded_support_validity_claim_ready": False,
            }
        },
    )
    write_json(
        root
        / "experiments/regression/manuscript/"
        / "bounded_support_positive_validation_protocol.json",
        {
            "summary": {
                "overall_status": (
                    "bounded_support_positive_validation_protocol_"
                    "completed_no_validity_claim"
                ),
                "action_id": (
                    "endpoint_bounded_support_gate."
                    "run_positive_bounded_support_validity_protocol"
                ),
                "action_status": (
                    "empirical_validation_complete_no_bounded_support_claim"
                ),
                "failed_check_count": 0,
                "selected_bundle_count": 14,
                "posthandling_validated_bundle_count": 14,
                "policy_metrics_available_bundle_count": 14,
                "interval_score_metrics_missing_bundle_count": 4,
                "endpoint_blocked_or_incomplete_bundle_count": 11,
                "positive_claim_ready_bundle_count": 0,
                "positive_acceptance_failed_count": 4,
                "can_support_bounded_support_validity": False,
                "current_manuscript_bounded_support_validity_claim_ready": False,
            }
        },
    )
    write_json(
        report_dir / "experiment_accounting_audit.json",
        {
            "summary": {
                "overall_status": "experiment_accounting_pass",
                "failed_check_count": 0,
                "ledger_file_count": 161,
                "raw_ledger_row_count": 168853,
                "canonical_ledger_row_count": 168761,
                "raw_completed_row_count": 156306,
                "canonical_completed_row_count": 156233,
                "canonical_failed_row_count": 11,
                "regular_canonical_completed_row_count": 154006,
                "cross_run_completed_rows": 145839,
                "publication_completed_rows": 145839,
                "selection_completed_rows_scanned": 145839,
                "regular_completed_minus_cross_run_completed_rows": 8167,
                "invalidated_canonical_completed_row_count": 1377,
                "aborted_canonical_completed_row_count": 850,
                "bounded_support_selected_completed_rows": 14349,
                "venn_grid_rows_completed": 6001,
                "venn_grid_rows_pending": 0,
                "venn_grid_worker_rows_completed": 5919,
                "venn_grid_worker_rows_failed": 5,
            }
        },
    )
    write_json(
        report_dir / "method_performance_synthesis.json",
        {
            "summary": {
                "overall_status": "method_performance_synthesis_descriptive_no_final_selection",
                "failed_check_count": 0,
                "completed_ledger_rows": 5,
                "source_report_count": 2,
                "method_count": 3,
                "broad_support_method_count": 2,
                "dataset_count": 2,
                "dataset_alpha_cell_count": 4,
                "frontier_cell_count": 4,
                "top_frontier_methods": [
                    {
                        "cp_method": "cqr",
                        "frontier_cell_count": 2,
                        "candidate_status_counts": {"nominal_mean": 2},
                    }
                ],
                "can_support_final_method_selection": False,
                "claim_status": "descriptive_no_final_selection",
            }
        },
    )
    write_json(
        report_dir / "method_selection_candidate_audit.json",
        {
            "summary": {
                "overall_status": "method_selection_candidate_audit_ready_no_final_selection",
                "failed_check_count": 0,
                "source_completed_ledger_rows": 5,
                "source_dataset_alpha_cell_count": 4,
                "source_method_count": 3,
                "shortlist_method_count": 3,
                "primary_candidate_method": "cqr",
                "paired_comparison_count": 2,
                "minimum_shared_pairwise_cell_count": 4,
                "excluded_method_count": 2,
                "venn_abers_excluded_count": 2,
                "can_support_final_method_selection": False,
                "claim_status": "candidate_shortlist_ready_no_final_selection",
                "selection_protocol_status": "selection_multiplicity_protocol_defined_no_final_selection",
                "final_selection_claim_status": "blocked",
                "venn_abers_validation_status": "venn_abers_validation_blocked_with_negative_evidence",
            },
            "shortlist_methods": [
                {"cp_method": "cqr"},
                {"cp_method": "mondrian_abs"},
                {"cp_method": "cv_plus"},
            ],
            "excluded_methods": [
                {
                    "cp_method": "venn_abers_quantile",
                    "exclusion_reasons": [
                        "frontier_cell_count_below_shortlist_threshold",
                        "venn_abers_validation_gate_blocked",
                    ],
                },
                {
                    "cp_method": "venn_abers_split_fallback",
                    "exclusion_reasons": [
                        "frontier_cell_count_below_shortlist_threshold",
                        "venn_abers_validation_gate_blocked",
                    ],
                },
            ],
        },
    )
    write_json(
        report_dir / "method_selection_robustness_audit.json",
        {
            "summary": {
                "overall_status": "method_selection_robustness_audit_ready_no_final_selection",
                "failed_check_count": 0,
                "source_completed_ledger_rows": 5,
                "candidate_primary_method": "cqr",
                "candidate_method_count": 3,
                "common_dataset_alpha_cell_count": 30,
                "common_dataset_count": 10,
                "common_alpha_count": 3,
                "common_alpha_distribution": {"0.1": 20, "0.05": 5, "0.2": 5},
                "common_alpha_max_cell_share": 20 / 30,
                "common_alpha_imbalance_status": "no_large_alpha_concentration",
                "alpha_balanced_selected_method": "cqr",
                "alpha_balanced_primary_retained": True,
                "alpha_stratum_selection_counts": {"cqr": 3},
                "common_cell_selected_method": "cqr",
                "common_cell_primary_win_count": 18,
                "common_cell_winner_counts": {
                    "cqr": 18,
                    "cv_plus": 7,
                    "mondrian_abs": 5,
                },
                "common_cell_winner_margin_to_runner_up": 11,
                "leave_one_dataset_count": 10,
                "leave_one_dataset_primary_retention_rate": 1.0,
                "leave_one_alpha_count": 3,
                "leave_one_alpha_primary_retention_rate": 1.0,
                "bootstrap_replicates": 100,
                "bootstrap_primary_selection_rate": 0.9,
                "bootstrap_selection_counts": {"cqr": 90, "cv_plus": 10},
                "can_support_final_method_selection": False,
                "claim_status": "selection_robustness_ready_no_final_selection",
                "selection_protocol_status": "selection_multiplicity_protocol_defined_no_final_selection",
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        report_dir / "method_selection_alpha_expansion_plan.json",
        {
            "summary": {
                "overall_status": "method_selection_alpha_expansion_plan_not_needed",
                "failed_check_count": 0,
                "source_completed_ledger_rows": 5,
                "candidate_method_count": 3,
                "dominant_alpha": "0.1",
                "target_alphas": ["0.05", "0.2"],
                "current_common_alpha_distribution": {
                    "0.1": 20,
                    "0.05": 5,
                    "0.2": 5,
                },
                "current_common_alpha_max_cell_share": 20 / 30,
                "current_common_alpha_imbalance_status": "no_large_alpha_concentration",
                "additional_common_cells_needed_to_clear_threshold": 0,
                "target_common_alpha_distribution": {
                    "0.1": 20,
                    "0.05": 5,
                    "0.2": 5,
                },
                "task_pool_dataset_alpha_task_count": 0,
                "task_pool_method_run_task_count": 0,
                "task_status_counts": {},
                "next_batch_dataset_alpha_task_count": 0,
                "next_batch_method_run_task_count": 0,
                "next_batch_alpha_counts": {},
                "planned_common_cell_gain": 0,
                "projected_common_alpha_distribution_after_next_batch": {
                    "0.1": 20,
                    "0.05": 5,
                    "0.2": 5,
                },
                "projected_common_alpha_max_cell_share_after_next_batch": 20 / 30,
                "projected_common_alpha_imbalance_status_after_next_batch": "no_large_alpha_concentration",
                "can_support_final_method_selection": False,
                "claim_status": "alpha_expansion_not_needed_no_final_selection",
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        report_dir / "method_selection_post_selection_validation_batch.json",
        {
            "summary": {
                "overall_status": "method_selection_post_selection_validation_batch_ready",
                "failed_check_count": 0,
                "dataset_count": 2,
                "generated_config_count": 2,
                "expected_atomic_run_count": 24,
                "candidate_methods": ["cqr", "cv_plus", "mondrian_abs"],
                "target_alphas": ["0.05", "0.1"],
                "execution_status": "configs_generated_not_yet_run",
                "can_support_final_method_selection": False,
                "claim_status": "post_selection_validation_batch_ready_no_final_selection",
            }
        },
    )
    write_json(
        report_dir / "method_selection_post_selection_validation_results.json",
        {
            "summary": {
                "overall_status": (
                    "method_selection_post_selection_validation_results_"
                    "ready_no_final_selection"
                ),
                "failed_check_count": 0,
                "dataset_count": 2,
                "completed_atomic_run_count": 24,
                "expected_atomic_run_count": 24,
                "common_dataset_alpha_cell_count": 4,
                "expected_common_dataset_alpha_cell_count": 4,
                "diagnostic_winner_counts": {"cqr": 3, "mondrian_abs": 1},
                "feature_leakage_violation_count": 0,
                "width_pathology_row_count": 1,
                "can_support_final_method_selection": False,
                "claim_status": (
                    "post_selection_validation_results_ready_no_final_selection"
                ),
            }
        },
    )
    write_json(
        root
        / "experiments/regression/manuscript/selection_multiplicity_evidence_record.json",
        {
            "summary": {
                "overall_status": (
                    "selection_multiplicity_evidence_record_ready_" "no_final_selection"
                ),
                "failed_check_count": 0,
                "validation_results_status": (
                    "method_selection_post_selection_validation_results_"
                    "ready_no_final_selection"
                ),
                "validation_completed_atomic_rows": 24,
                "validation_expected_atomic_rows": 24,
                "diagnostic_primary_method": "cqr",
                "diagnostic_winner_counts": {"cqr": 3, "mondrian_abs": 1},
                "feature_leakage_violation_count": 0,
                "can_support_final_method_selection": False,
                "claim_status": (
                    "diagnostic_primary_candidate_recorded_no_final_selection"
                ),
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        report_dir / "method_selection_alpha_expansion_execution_audit.json",
        {
            "summary": {
                "overall_status": (
                    "method_selection_alpha_expansion_execution_closed_"
                    "no_final_selection"
                ),
                "failed_check_count": 0,
                "batch_overall_status": "method_selection_alpha_expansion_batch_ready",
                "batch_reported_execution_status": "configs_generated_not_yet_run",
                "batch_reported_execution_status_is_historical": True,
                "batch_generation_label_stale_after_execution": True,
                "batch_generation_label_historical_only": True,
                "batch_generation_label_reconciliation_status": (
                    "reconciled_historical_config_generation_label_with_completed_ledgers"
                ),
                "batch_generation_label_requires_action": False,
                "execution_metadata_consistency_status": (
                    "historical_batch_generation_label_reconciled_no_action_required"
                ),
                "observed_execution_status": "ledgers_completed",
                "active_execution_status": "ledgers_completed",
                "reconciled_execution_status": "ledgers_completed",
                "generated_config_count": 2,
                "dataset_count": 2,
                "completed_atomic_run_count": 24,
                "expected_atomic_run_count": 24,
                "plan_overall_status": "method_selection_alpha_expansion_plan_not_needed",
                "plan_additional_common_cells_needed_to_clear_threshold": 0,
                "post_selection_validation_status": (
                    "method_selection_post_selection_validation_results_"
                    "ready_no_final_selection"
                ),
                "post_selection_completed_atomic_run_count": 24,
                "post_selection_expected_atomic_run_count": 24,
                "can_support_final_method_selection": False,
                "claim_status": ("alpha_expansion_execution_closed_no_final_selection"),
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        report_dir / "method_selection_inferential_audit.json",
        {
            "summary": {
                "overall_status": (
                    "method_selection_inferential_audit_ready_no_final_selection"
                ),
                "failed_check_count": 0,
                "primary_candidate_method": "cqr",
                "candidate_methods": ["cqr", "cv_plus", "mondrian_abs"],
                "candidate_method_count": 3,
                "candidate_pairwise_comparison_count": 2,
                "candidate_min_shared_pairwise_cell_count": 40,
                "robustness_common_cell_primary_win_rate": 0.6,
                "robustness_common_cell_primary_win_rate_ci95": {
                    "low": 0.42,
                    "high": 0.75,
                },
                "bootstrap_primary_selection_rate": 0.95,
                "bootstrap_primary_selection_rate_ci95": {
                    "low": 0.89,
                    "high": 0.98,
                },
                "post_selection_validation_primary_win_rate": 0.72,
                "post_selection_validation_primary_win_rate_ci95": {
                    "low": 0.52,
                    "high": 0.86,
                },
                "main_result_candidate_primary_win_rate": 0.66,
                "main_result_candidate_primary_win_rate_ci95": {
                    "low": 0.55,
                    "high": 0.76,
                },
                "can_support_final_method_selection": False,
                "claim_status": (
                    "inferential_method_selection_evidence_ready_no_final_selection"
                ),
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        root / "experiments/regression/manuscript/paper_readiness_map.json",
        {
            "summary": {
                "overall_status": "paper_readiness_blocked_with_evidence_map",
                "blocked_gate_count": 6,
                "gate_count": 6,
                "main_surface_blocked_count": 1,
                "claim_count": 12,
                "manifested_bundle_count": 14,
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        root / "experiments/regression/manuscript/bundle_eligibility_matrix.json",
        {
            "summary": {
                "overall_status": "bundle_eligibility_matrix_ready_no_final_claims",
                "bundle_count": 14,
                "manifest_present_count": 14,
                "claim_linked_bundle_count": 14,
                "missing_manifest_count": 0,
                "unlinked_bundle_count": 0,
                "robustness_candidate_count": 9,
                "caveated_robustness_candidate_count": 9,
                "main_results_eligible_count": 0,
                "final_claim_eligible_count": 0,
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        report_dir / "dataset_specific_final_gate_audit.json",
        {
            "summary": {
                "overall_status": (
                    "dataset_specific_final_gate_audit_completed_"
                    "no_final_dataset_promotions"
                ),
                "dataset_count": 2,
                "bundle_count": 14,
                "main_result_candidate_diagnostic_bundle_count": 2,
                "main_result_ready_bundle_count": 0,
                "main_result_ready_dataset_count": 0,
                "blocking_reason_counts": {
                    "final_selection_claim_blocked": 14,
                    "main_results_surface_blocked": 14,
                },
                "paper_readiness_status": "paper_readiness_blocked_with_evidence_map",
                "paper_blocked_gate_count": 6,
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        report_dir / "dataset_final_gate_post_selection_validation_bridge.json",
        {
            "summary": {
                "overall_status": (
                    "dataset_final_gate_post_selection_validation_bridge_"
                    "ready_no_promotions"
                ),
                "failed_check_count": 0,
                "dataset_count": 1,
                "generated_config_count": 1,
                "expected_atomic_run_count": 12,
                "bridge_results_available": True,
                "bridge_results_completed_atomic_run_count": 12,
                "bridge_results_expected_atomic_run_count": 12,
                "bridge_results_feature_leakage_violation_count": 0,
                "execution_status": "completed_bridge_results",
                "execution_reconciliation_requires_action": False,
                "can_support_final_method_selection": False,
                "claim_status": "post_selection_validation_bridge_ready_no_promotions",
            }
        },
    )
    write_json(
        report_dir / "dataset_final_gate_post_selection_validation_bridge_results.json",
        {
            "summary": {
                "overall_status": (
                    "method_selection_post_selection_validation_results_"
                    "ready_no_final_selection"
                ),
                "failed_check_count": 0,
                "dataset_count": 1,
                "completed_atomic_run_count": 12,
                "expected_atomic_run_count": 12,
                "common_dataset_alpha_cell_count": 2,
                "expected_common_dataset_alpha_cell_count": 2,
                "diagnostic_winner_counts": {"cqr": 1, "cv_plus": 1},
                "feature_leakage_violation_count": 0,
                "can_support_final_method_selection": False,
                "claim_status": (
                    "post_selection_validation_results_ready_no_final_selection"
                ),
            }
        },
    )
    write_json(
        report_dir / "main_result_candidate_bundle_plan.json",
        {
            "summary": {
                "overall_status": "main_result_candidate_bundle_plan_ready_no_promotions",
                "failed_check_count": 0,
                "candidate_dataset_count": 2,
                "generated_config_count": 2,
                "expected_atomic_run_count": 36,
                "diagnostic_primary_method": "cqr",
                "candidate_primary_consistent_dataset_count": 1,
                "ambiguous_challenger_control_dataset_count": 1,
                "source_validation_combined_completed_atomic_rows": 36,
                "source_validation_combined_failed_check_count": 0,
                "source_validation_combined_feature_leakage_violation_count": 0,
                "can_support_main_result_promotion": False,
            }
        },
    )
    write_json(
        report_dir / "main_result_candidate_bundle_results.json",
        {
            "summary": {
                "overall_status": (
                    "main_result_candidate_bundle_results_completed_" "no_promotions"
                ),
                "failed_check_count": 0,
                "completed_atomic_run_count": 36,
                "expected_atomic_run_count": 36,
                "complete_matched_cell_count": 12,
                "diagnostic_winner_counts": {"cqr": 8, "cv_plus": 2, "mondrian_abs": 2},
                "pathology_flagged_row_count": 4,
                "missing_ledger_count": 0,
                "unique_run_row_count": 36,
                "raw_ledger_row_count": 36,
                "can_support_main_result_promotion": False,
            }
        },
    )
    write_json(
        report_dir / "main_result_candidate_post_run_closure_audit.json",
        {
            "summary": {
                "overall_status": (
                    "main_result_candidate_post_run_closure_ready_no_promotions"
                ),
                "candidate_dataset_count": 2,
                "completed_atomic_run_count": 36,
                "expected_atomic_run_count": 36,
                "total_blocker_count": 0,
                "dataset_blocked_count": 0,
                "blocker_counts_by_artifact": {},
                "can_support_main_result_promotion": False,
            }
        },
    )
    write_json(
        report_dir / "dataset_final_gate_remediation_plan.json",
        {
            "summary": {
                "overall_status": "dataset_final_gate_remediation_plan_ready_no_promotions",
                "dataset_count": 2,
                "ready_dataset_count": 0,
                "executable_action_count": 10,
                "action_counts": {
                    "resolve_final_method_model_selection_gate": 2,
                    "resolve_global_bounded_support_validity_claim_gate": 2,
                },
                "action_scope_counts": {
                    "global_gate_dependency": 6,
                    "local_dataset_remediation": 1,
                    "post_closure_refresh": 3,
                },
                "local_dataset_remediation_action_count": 1,
                "global_gate_dependency_action_count": 6,
                "post_closure_refresh_action_count": 3,
                "missing_post_selection_validation_bridge_count": 0,
                "missing_main_result_candidate_bundle_count": 0,
                "completed_main_result_candidate_results_dataset_count": 2,
                "candidate_post_run_closure_ready_dataset_count": 2,
                "dataset_with_no_remaining_execution_gap_count": 2,
                "dataset_blocked_only_by_global_gate_dependencies_count": 1,
                "readiness_status_counts": {
                    "blocked_bounded_support_endpoint_support": 1,
                    "blocked_bounded_support_global_validity_claim": 1,
                },
                "blocked_gate_ids": [
                    "dataset_specific_final_gates",
                    "endpoint_bounded_support_gate",
                    "fairness_population_inference_gate",
                    "final_method_model_selection_gate",
                    "multiplicity_selection_record",
                    "venn_abers_regression_validation_gate",
                ],
            }
        },
    )
    write_json(
        root / "experiments/regression/manuscript/paper_gate_closure_map.json",
        {
            "summary": {
                "overall_status": "paper_gate_closure_map_ready_no_promotions",
                "gate_count": 6,
                "blocked_gate_count": 6,
                "positive_claim_ready_gate_count": 0,
                "scoped_or_negative_path_ready_gate_count": 6,
                "local_execution_gap_gate_count": 0,
            }
        },
    )
    write_json(
        root / "experiments/regression/manuscript/paper_gate_protocol_design_bundle.json",
        {
            "summary": {
                "overall_status": (
                    "paper_gate_protocol_design_bundle_ready_no_claim_promotions"
                ),
                "protocol_design_count": 4,
                "completed_protocol_design_action_count": 4,
                "downstream_action_count": 5,
                "claim_promoted_action_count": 0,
                "status_counts": {"protocol_design_complete": 4},
                "downstream_action_ids": [
                    "endpoint_bounded_support_gate.audit_natural_domain_endpoint_excursions",
                    "fairness_population_inference_gate.define_sampling_weight_policy",
                    "multiplicity_selection_record.link_record_to_final_selection_claim",
                    "venn_abers_regression_validation_gate.run_exact_grid_or_theory_validation_benchmark",
                    "venn_abers_regression_validation_gate.validate_ivapd_interval_cp_contract",
                ],
            }
        },
    )
    write_json(
        root / "experiments/regression/manuscript/fairness_sampling_weight_policy.json",
        {
            "summary": {
                "overall_status": (
                    "fairness_sampling_weight_policy_defined_no_fairness_claim"
                ),
                "action_status": "protocol_design_complete",
                "policy_declared_bundle_count": 2,
                "weighted_estimand_applied_bundle_count": 0,
                "unweighted_diagnostic_only_bundle_count": 2,
                "population_fairness_ready_bundle_count": 0,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        root / "experiments/regression/manuscript/paper_gate_closure_execution_plan.json",
        {
            "summary": {
                "overall_status": "paper_gate_closure_execution_plan_ready",
                "gate_count": 6,
                "blocked_gate_count": 6,
                "action_count": 22,
                "ready_action_count": 4,
                "blocked_action_count": 13,
                "ready_for_protocol_design_action_count": 0,
                "ready_for_empirical_execution_action_count": 4,
                "protocol_design_complete_action_count": 5,
                "empirical_execution_complete_action_count": 2,
                "endpoint_natural_domain_audit_complete_action_count": 1,
                "current_manuscript_bounded_support_validity_claim_ready": False,
                "fairness_sampling_weight_policy_status": (
                    "fairness_sampling_weight_policy_defined_no_fairness_claim"
                ),
                "fairness_sampling_weight_policy_complete_action_count": 1,
                "can_close_any_positive_gate_now": False,
                "action_status_counts": {
                    "blocked_by_gate_dependencies": 4,
                    "blocked_by_prior_plan_actions": 9,
                    "protocol_design_complete": 5,
                    "ready_for_empirical_execution": 4,
                },
                "next_executable_action_ids": [
                    "endpoint_bounded_support_gate.audit_natural_domain_endpoint_excursions",
                    "fairness_population_inference_gate.compute_group_counts_missingness_and_gaps",
                ],
            }
        },
    )
    write_json(
        report_dir / "graph_artifact_readiness_audit.json",
        {
            "summary": {
                "overall_status": "graph_artifact_readiness_pass",
                "graph_count": 4,
                "failed_check_count": 0,
                "total_node_count_estimate": 120,
                "total_edge_count_estimate": 240,
                "all_required_tokens_present": True,
                "all_kg_graph_nodes_traceable": True,
            }
        },
    )
    write_json(
        report_dir / "kg_publication_quality_audit.json",
        {
            "summary": {
                "overall_status": (
                    "kg_publication_ready_with_polish_caveats"
                    if caveat
                    else "kg_publication_ready"
                ),
                "node_count": 10,
                "edge_count": 25,
                "hard_failed_check_count": 0,
                "polish_caveat_count": 1 if caveat else 0,
                "specific_edge_provenance_coverage": 0.99 if caveat else 1.0,
                "edge_selector_provenance_coverage": 0.43,
                "observation_node_ratio": 1.2 if caveat else 2.1,
                "paper_evidence_observation_node_ratio": 1.1,
                "tracked_missing_source_count": 0,
                "relevant_untracked_source_count": 0,
            }
        },
    )
    write_json(
        report_dir / "scientific_review_finding_register.json",
        {
            "summary": {
                "overall_status": (
                    "scientific_review_findings_tracked_with_open_caveats"
                    if caveat
                    else "scientific_review_findings_closed"
                ),
                "finding_count": 12,
                "closed_count": 9 if caveat else 12,
                "tracked_caveat_count": 3 if caveat else 0,
                "open_blocker_count": 0,
                "hard_open_blocker_count": 0,
                "status_counts": (
                    {"closed": 9, "tracked_caveat": 3} if caveat else {"closed": 12}
                ),
            }
        },
    )
    write_json(
        manuscript_dir / "post_experiment_publication_activation_audit.json",
        {
            "summary": {
                "overall_status": (
                    "post_experiment_publication_preparation_active_with_caveats"
                ),
                "publication_phase_start_authorized": True,
                "publication_preparation_authorized": True,
                "neutral_empirical_phase_complete": True,
                "neutral_publication_route_allowed": True,
                "positive_claim_language_blocked": True,
                "manuscript_drafting_authorized": False,
                "visual_table_audit_authorized": True,
                "sterile_repository_creation_authorized": False,
                "activation_check_count": 13,
                "blocked_check_count": 0,
                "caveat_check_count": 1 if caveat else 0,
                "deferred_check_count": 2,
                "paper_blocked_gate_count": 6,
                "paper_blocked_gate_ids": [
                    "dataset_specific_final_gates",
                    "endpoint_bounded_support_gate",
                    "fairness_population_inference_gate",
                    "final_method_model_selection_gate",
                    "multiplicity_selection_record",
                    "venn_abers_regression_validation_gate",
                ],
                "goal_can_mark_complete": False,
                "author_metadata_present": True,
                "sterile_repository_plan_present": True,
            }
        },
    )
    write_json(
        manuscript_dir / "publication_preparation_packets.json",
        {
            "summary": {
                "overall_status": "publication_preparation_packets_ready_no_final_prose",
                "publication_preparation_authorized": True,
                "reviewer_packet_count": 5,
                "required_reviewer_pass_count": 5,
                "visual_table_candidate_family_count": 10,
                "visual_table_quality_check_count": 10,
                "manuscript_drafting_authorized": False,
                "sterile_repository_creation_authorized": False,
                "positive_claim_publication_ready": False,
                "neutral_no_method_promotion_guard_active": True,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "reviewer_design_brief.json",
        {
            "summary": {
                "overall_status": "reviewer_design_brief_ready_no_final_prose",
                "phase_state": (
                    "neutral_pre_prose_design_active_final_prose_and_release_blocked"
                ),
                "reviewer_count": 5,
                "required_reviewer_count": 5,
                "advice_record_count": 25,
                "minimum_recommendations_per_reviewer": 5,
                "accepted_advice_count": 18,
                "deferred_advice_count": 7,
                "required_advice_topic_count": 10,
                "covered_advice_topic_count": 10,
                "content_matrix_row_count": 10,
                "expected_visual_table_family_count": 10,
                "publication_site_deployment_authorized": False,
                "neutral_no_method_promotion_guard_active": True,
                "manuscript_drafting_authorized": False,
                "sterile_repository_creation_authorized": False,
                "final_visual_table_retention_authorized": False,
                "final_manuscript_prose_permission": False,
                "final_retain_decision_authorized": False,
                "positive_claim_promotion_authorized": False,
                "check_count": 8,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "visual_table_audit_plan.json",
        {
            "summary": {
                "overall_status": (
                    "publication_visual_audit_plan_ready_no_retained_artifacts"
                ),
                "phase_state": (
                    "neutral_pre_prose_visual_audit_planning_active_"
                    "final_visuals_and_release_blocked"
                ),
                "candidate_artifact_count": 10,
                "expected_candidate_artifact_count": 10,
                "visual_table_quality_check_count": 10,
                "visual_table_scope_count": 5,
                "visual_table_feedback_loop_step_count": 5,
                "visual_table_required_output_artifact_count": 6,
                "triptych_component_count": 3,
                "triptych_decision_status": (
                    "candidate_triptych_deferred_until_kg_usability_release_gates"
                ),
                "kg_citable_component_authorized": False,
                "publication_site_deployment_authorized": False,
                "visual_table_audit_plan_authorized": True,
                "visual_table_audit_execution_authorized": False,
                "final_visual_table_retention_authorized": False,
                "final_triptych_release_authorized": False,
                "final_manuscript_prose_permission": False,
                "positive_claim_promotion_authorized": False,
                "neutral_no_method_promotion_guard_active": True,
                "check_count": 9,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "visual_table_audit_report.json",
        {
            "summary": {
                "overall_status": (
                    "visual_table_pre_retention_audit_completed_no_retained_artifacts"
                ),
                "phase_state": (
                    "pre_retention_audit_complete_rendering_and_final_retention_blocked"
                ),
                "inventory_row_count": 10,
                "expected_candidate_artifact_count": 10,
                "audit_row_count": 10,
                "pre_retention_audit_completed_count": 10,
                "source_traceable_candidate_count": 10,
                "pre_retention_decision_count": 10,
                "pre_retention_decision_counts": {
                    "candidate_keep_pending_render_audit": 2,
                    "move_to_kg_or_site_pending_release_gates": 1,
                    "move_to_supplement_pending_render_audit": 4,
                    "revise_claim_boundary_before_main_article_use": 3,
                },
                "actionable_feedback_count": 40,
                "iteration_action_count": 10,
                "rendered_artifact_count": 0,
                "layout_check_deferred_count": 10,
                "final_retained_artifact_count": 0,
                "final_visual_table_retention_authorized": False,
                "kg_citable_component_authorized": False,
                "publication_site_deployment_authorized": False,
                "final_triptych_release_authorized": False,
                "final_manuscript_prose_permission": False,
                "positive_claim_promotion_authorized": False,
                "neutral_no_method_promotion_guard_active": True,
                "check_count": 9,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "visual_table_render_candidate_audit.json",
        {
            "summary": {
                "overall_status": (
                    "draft_visual_table_render_audit_completed_no_final_retention"
                ),
                "phase_state": (
                    "draft_render_candidates_complete_final_retention_and_release_blocked"
                ),
                "pre_retention_input_row_count": 10,
                "candidate_row_count": 10,
                "rendered_draft_artifact_count": 10,
                "primary_rendered_artifact_count": 10,
                "supporting_artifact_count": 3,
                "layout_audit_row_count": 10,
                "layout_pass_count": 10,
                "layout_revise_count": 0,
                "caption_pass_count": 10,
                "source_traceability_pass_count": 10,
                "svg_static_text_overlap_detected_count": 0,
                "final_retained_artifact_count": 0,
                "final_visual_table_retention_authorized": False,
                "kg_citable_component_authorized": False,
                "publication_site_deployment_authorized": False,
                "final_triptych_release_authorized": False,
                "final_manuscript_prose_permission": False,
                "positive_claim_promotion_authorized": False,
                "neutral_no_method_promotion_guard_active": True,
                "check_count": 6,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "publication_retention_readiness_audit.json",
        {
            "summary": {
                "overall_status": (
                    "publication_retention_readiness_ready_no_final_prose"
                ),
                "phase_state": (
                    "pre_manuscript_retention_recommendations_ready_"
                    "final_prose_and_release_blocked"
                ),
                "recommendation_row_count": 10,
                "render_candidate_count": 10,
                "recommended_surface_counts": {
                    "kg_or_site_candidate_release_blocked": 1,
                    "main_article_candidate_after_final_prose_gate": 4,
                    "supplement_candidate_after_final_prose_gate": 5,
                },
                "main_article_candidate_count": 4,
                "supplement_candidate_count": 5,
                "kg_or_site_candidate_count": 1,
                "retention_recommendation_complete": True,
                "reviewer_design_reconciled": True,
                "neutral_result_ledger_clean": True,
                "neutral_language_unguarded_hit_count": 0,
                "final_retained_artifact_count": 0,
                "final_visual_table_retention_authorized": False,
                "final_manuscript_prose_permission": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "positive_claim_promotion_authorized": False,
                "sterile_repository_creation_authorized": False,
                "check_count": 6,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "final_publication_visual_auditor_readiness.json",
        {
            "summary": {
                "overall_status": (
                    "final_publication_visual_auditor_feedback_loop_ready_no_retention"
                ),
                "phase_state": (
                    "pre_final_visual_auditor_feedback_ready_"
                    "final_retention_blocked"
                ),
                "final_publication_visual_auditor_status": (
                    "feedback_loop_ready_no_final_retention"
                ),
                "feedback_loop_ready": True,
                "feedback_row_count": 10,
                "feedback_ready_row_count": 10,
                "feedback_blocked_row_count": 0,
                "feedback_item_count": 39,
                "recommended_surface_counts": {
                    "kg_or_site_candidate_release_blocked": 1,
                    "main_article_candidate_after_final_prose_gate": 4,
                    "supplement_candidate_after_final_prose_gate": 5,
                },
                "missing_rendered_artifact_count": 0,
                "authorization_violation_count": 0,
                "release_authorized_count": 0,
                "final_retained_artifact_count": 0,
                "final_visual_table_retention_authorized": False,
                "final_manuscript_prose_permission": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "neutral_language_unguarded_hit_count": 0,
                "missing_source_artifact_count": 0,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "neutral_result_ledger.json",
        {
            "summary": {
                "overall_status": "neutral_result_ledger_ready_no_method_promotion",
                "row_count": 9,
                "source_artifact_count": 18,
                "missing_source_artifact_count": 0,
                "positive_claim_promotion_authorized_count": 0,
                "final_method_selection_authorized_count": 0,
                "final_visual_table_retention_authorized_count": 0,
                "final_manuscript_prose_permission_count": 0,
                "sterile_repository_creation_authorized_count": 0,
                "neutral_no_method_promotion_guard_active": True,
                "cqr_descriptive_candidate_recorded": True,
                "venn_abers_negative_result_recorded": True,
                "check_count": 6,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "article_supplement_blueprint_alignment.json",
        {
            "summary": {
                "overall_status": (
                    "article_supplement_blueprint_alignment_ready_"
                    "no_final_prose_no_method_promotion"
                ),
                "phase_state": (
                    "neutral_pre_prose_blueprint_alignment_active_"
                    "final_prose_and_release_blocked"
                ),
                "alignment_row_count": 10,
                "surface_row_count": 3,
                "direct_reviewer_advice_row_count": 9,
                "explicit_no_direct_advice_rationale_count": 1,
                "reviewer_alignment_issue_count": 0,
                "linked_neutral_result_issue_count": 0,
                "source_traceable_row_count": 10,
                "missing_source_artifact_count": 0,
                "recommended_surface_counts": {
                    "kg_or_site_candidate_release_blocked": 1,
                    "main_article_candidate_after_final_prose_gate": 4,
                    "supplement_candidate_after_final_prose_gate": 5,
                },
                "neutral_result_ledger_clean": True,
                "neutral_language_unguarded_hit_count": 0,
                "activation_pre_prose_only": True,
                "venn_abers_negative_no_validated_claim": True,
                "cqr_cvplus_reporting_role": (
                    "descriptive_diagnostic_no_final_selection_no_method_promotion"
                ),
                "final_retained_artifact_count": 0,
                "final_visual_table_retention_authorized": False,
                "final_manuscript_prose_permission": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "positive_claim_promotion_authorized": False,
                "sterile_repository_creation_authorized": False,
                "method_recommendation_authorized": False,
                "scientific_no_method_promotion_guard_active": True,
                "check_count": 10,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "publication_release_gap_register.json",
        {
            "summary": {
                "overall_status": "publication_release_gap_register_ready_no_final_release",
                "phase_state": (
                    "neutral_pre_release_gap_register_active_final_release_blocked"
                ),
                "deliverable_row_count": 11,
                "deliverable_family_counts": {
                    "individual_experiment_report": 1,
                    "kg_or_publication_site": 4,
                    "main_article": 2,
                    "sterile_publication_repository": 1,
                    "supplementary_document": 3,
                },
                "release_status_counts": {
                    "release_blocked_pre_prose_candidate_ready": 11
                },
                "pre_prose_evidence_ready_row_count": 11,
                "release_authorized_count": 0,
                "blocked_release_row_count": 11,
                "source_traceable_row_count": 11,
                "missing_source_artifact_count": 0,
                "goal_can_mark_complete": False,
                "noncomplete_requirement_count": 2,
                "paper_blocked_gate_count": 6,
                "positive_claim_ready_gate_count": 0,
                "publication_preparation_authorized": True,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "method_recommendation_authorized": False,
                "working_repository_final_citable": False,
                "sterile_repository_status": "planned_after_full_experiment_closure",
                "author_metadata_present": True,
                "neutral_language_unguarded_hit_count": 0,
                "scientific_no_method_promotion_guard_active": True,
                "check_count": 10,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "individual_experiment_report_blueprint.json",
        {
            "summary": {
                "overall_status": (
                    "individual_experiment_report_blueprint_ready_no_final_prose"
                ),
                "phase_state": (
                    "neutral_pre_prose_individual_report_blueprint_active_"
                    "final_outputs_blocked"
                ),
                "author_header": "Author: Emre Tasar, Data Scientist",
                "author_email": "detasar@gmail.com",
                "approved_author_header_present": True,
                "deliverable_registered": True,
                "deliverable_format": "latex_html_and_markdown",
                "section_row_count": 10,
                "source_traceable_row_count": 10,
                "missing_source_artifact_count": 0,
                "linked_neutral_result_issue_count": 0,
                "final_report_prose_permission": False,
                "latex_output_authorized": False,
                "html_output_authorized": False,
                "markdown_output_authorized": False,
                "release_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "cqr_reporting_role": "descriptive_diagnostic_no_final_selection",
                "venn_abers_reporting_role": (
                    "negative_failure_mode_no_validated_regression_claim"
                ),
                "scientific_no_method_promotion_guard_active": True,
                "check_count": 10,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "claim_safe_result_extraction_matrix.json",
        {
            "summary": {
                "overall_status": (
                    "claim_safe_result_extraction_matrix_ready_no_final_claims"
                ),
                "phase_state": (
                    "neutral_pre_prose_result_extraction_active_"
                    "final_outputs_blocked"
                ),
                "surface_row_count": 8,
                "source_traceable_row_count": 8,
                "missing_source_artifact_count": 0,
                "linked_neutral_result_issue_count": 0,
                "safe_pre_prose_extraction_candidate_count": 7,
                "blocked_positive_surface_count": 1,
                "main_results_surface_status": "blocked_positive_claim_surface",
                "negative_results_surface_status": "candidate_negative_result_surface",
                "main_result_positive_claim_blocked": True,
                "negative_result_reporting_ready": True,
                "neutral_result_ledger_clean": True,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "release_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "release_authorized": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "scientific_no_method_promotion_guard_active": True,
                "check_count": 10,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "manuscript_section_evidence_packet.json",
        {
            "summary": {
                "overall_status": (
                    "manuscript_section_evidence_packet_ready_no_final_prose"
                ),
                "phase_state": (
                    "neutral_pre_prose_section_evidence_packet_active_"
                    "final_outputs_blocked"
                ),
                "section_packet_row_count": 8,
                "source_traceable_row_count": 8,
                "missing_source_artifact_count": 0,
                "claim_safe_surface_link_issue_count": 0,
                "linked_neutral_result_issue_count": 0,
                "safe_pre_prose_evidence_packet_count": 7,
                "blocked_positive_packet_count": 1,
                "main_results_packet_status": "blocked_positive_claim_packet",
                "negative_packet_status": "pre_prose_negative_evidence_ready",
                "main_results_packet_blocked": True,
                "negative_packet_ready": True,
                "claim_safe_matrix_clean": True,
                "neutral_result_ledger_clean": True,
                "final_section_prose_authorized": False,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "release_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "scientific_no_method_promotion_guard_active": True,
                "check_count": 10,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "section_claim_boundary_audit.json",
        {
            "summary": {
                "overall_status": "section_claim_boundary_audit_pass_no_final_claims",
                "phase_state": (
                    "neutral_pre_prose_section_claim_boundary_alignment_active_"
                    "final_outputs_blocked"
                ),
                "boundary_row_count": 8,
                "boundary_complete_row_count": 8,
                "allowed_use_complete_row_count": 8,
                "blocked_use_complete_row_count": 8,
                "claim_safe_surface_consistent_row_count": 8,
                "neutral_result_linked_row_count": 8,
                "release_target_linked_row_count": 8,
                "release_authorized_target_count": 0,
                "neutral_ledger_prose_boundary_gap_unique_result_count": 5,
                "section_boundary_backfill_row_count": 8,
                "main_results_positive_boundary_blocked": True,
                "venn_abers_negative_boundary_preserved": True,
                "section_packet_clean": True,
                "upstream_boundaries_clean": True,
                "post_program_controlled": True,
                "final_section_prose_authorized": False,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "release_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "scientific_no_method_promotion_guard_active": True,
                "check_count": 10,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "article_supplement_kg_navigation_index.json",
        {
            "summary": {
                "overall_status": (
                    "article_supplement_kg_navigation_index_ready_no_release"
                ),
                "phase_state": (
                    "neutral_pre_release_navigation_index_active_final_outputs_blocked"
                ),
                "navigation_row_count": 9,
                "section_navigation_row_count": 8,
                "kg_site_navigation_row_count": 1,
                "source_traceable_row_count": 9,
                "visual_table_candidate_index_row_count": 10,
                "visual_table_source_traceability_pass_count": 10,
                "visual_table_final_authorized_count": 0,
                "release_authorized_target_count": 0,
                "kg_node_reference_issue_count": 0,
                "missing_source_artifact_count": 0,
                "main_results_positive_boundary_blocked": True,
                "venn_abers_negative_boundary_preserved": True,
                "scientific_no_method_promotion_guard_active": True,
                "neutral_language_unguarded_hit_count": 0,
                "final_navigation_release_authorized": False,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "publication_phase_progress_reconciliation_audit.json",
        {
            "summary": {
                "overall_status": (
                    "publication_phase_progress_reconciliation_ready_no_final_outputs"
                ),
                "phase_state": (
                    "neutral_publication_progress_reconciled_final_outputs_blocked"
                ),
                "pre_prose_completed_control_count": 8,
                "pre_prose_control_count": 8,
                "resolved_prior_blocker_count": 2,
                "active_final_blocker_count": 10,
                "stale_goal_blocker_count": 0,
                "reviewer_design_reconciled": True,
                "pre_retention_visual_audit_completed": True,
                "claim_boundary_navigation_ready": True,
                "release_gap_ready": True,
                "neutral_guard_ready": True,
                "kg_publication_ready": True,
                "final_publication_visual_auditor_status": (
                    "feedback_loop_ready_no_final_retention"
                ),
                "final_publication_visual_auditor_feedback_ready": True,
                "goal_can_mark_complete": False,
                "goal_noncomplete_requirement_count": 2,
                "paper_blocked_gate_count": 6,
                "positive_claim_ready_gate_count": 0,
                "main_results_positive_boundary_blocked": True,
                "venn_abers_negative_boundary_preserved": True,
                "validated_venn_abers_regression_claim_ready": False,
                "final_manuscript_prose_permission": False,
                "manuscript_drafting_authorized": False,
                "latex_html_authoring_authorized": False,
                "final_visual_table_retention_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "neutral_language_unguarded_hit_count": 0,
                "missing_source_artifact_count": 0,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        report_dir / "neutral_reporting_language_audit.json",
        {
            "summary": {
                "overall_status": "neutral_reporting_language_audit_pass",
                "scanned_file_count": 12,
                "term_pattern_count": 8,
                "term_hit_count": 21,
                "guarded_hit_count": 21,
                "unguarded_hit_count": 0,
                "failed_check_count": 0,
                "positive_claim_ready_gate_count": 0,
                "final_result_disposition_gate_count": 2,
                "publication_phase_start_authorized": True,
            }
        },
    )
    write_json(
        manuscript_dir / "scientific_neutrality_interpretation_lock.json",
        {
            "summary": {
                "overall_status": (
                    "scientific_neutrality_interpretation_lock_ready_no_method_promotion"
                ),
                "phase_state": (
                    "neutral_interpretation_locked_final_claims_and_outputs_blocked"
                ),
                "interpretation_row_count": 8,
                "missing_source_artifact_count": 0,
                "neutral_language_unguarded_hit_count": 0,
                "cqr_cvplus_reporting_role": (
                    "descriptive_diagnostic_no_final_selection_no_method_promotion"
                ),
                "venn_abers_reporting_role": (
                    "negative_failure_mode_no_validated_regression_claim"
                ),
                "main_results_positive_boundary_blocked": True,
                "venn_abers_negative_boundary_preserved": True,
                "validated_venn_abers_regression_claim_ready": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "final_manuscript_prose_permission": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "scientific_test_not_method_promotion": True,
                "analysis_only_no_champion_method": True,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "result_reporting_policy": (
                    "analysis_only_report_observed_behavior_no_method_advocacy"
                ),
                "authorization_violation_count": 0,
                "promotional_phrase_hit_count": 0,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "final_publication_output_authorization_protocol.json",
        {
            "summary": {
                "overall_status": (
                    "final_publication_output_authorization_protocol_ready_no_authorizations"
                ),
                "phase_state": (
                    "neutral_final_output_authorization_protocol_defined_outputs_blocked"
                ),
                "final_output_authorization_protocol_status": (
                    "protocol_ready_all_final_outputs_blocked"
                ),
                "authorization_row_count": 10,
                "blocked_authorization_row_count": 10,
                "missing_policy_row_count": 0,
                "ready_to_authorize_output_count": 0,
                "active_final_blocker_count": 10,
                "goal_can_mark_complete": False,
                "neutral_empirical_phase_complete": True,
                "scientific_test_not_method_promotion": True,
                "analysis_only_no_champion_method": True,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "result_reporting_policy": (
                    "analysis_only_report_observed_behavior_no_method_advocacy"
                ),
                "paper_blocked_gate_count": 6,
                "positive_claim_ready_gate_count": 0,
                "release_authorized_count": 0,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "latex_html_authoring_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "authorization_violation_count": 0,
                "missing_source_artifact_count": 0,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "publication_claim_evidence_verification_matrix.json",
        {
            "summary": {
                "overall_status": (
                    "publication_claim_evidence_verification_ready_no_final_prose"
                ),
                "phase_state": (
                    "neutral_pre_prose_claim_evidence_verification_active_"
                    "final_outputs_blocked"
                ),
                "verification_row_count": 8,
                "verification_pass_count": 8,
                "source_traceable_row_count": 8,
                "boundary_aligned_row_count": 8,
                "navigation_aligned_row_count": 8,
                "kg_reference_issue_count": 0,
                "safe_pre_prose_evidence_row_count": 7,
                "blocked_positive_row_count": 1,
                "main_results_blocked_row_count": 1,
                "venn_abers_negative_ready_row_count": 1,
                "missing_source_artifact_count": 0,
                "source_authorization_violation_count": 0,
                "row_authorization_violation_count": 0,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "latex_html_authoring_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "release_authorized": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "positive_claim_promotion_authorized": False,
                "analysis_only_no_champion_method": True,
                "result_reporting_policy": (
                    "analysis_only_report_observed_behavior_no_method_advocacy"
                ),
                "neutral_language_unguarded_hit_count": 0,
                "kg_isolated_node_count": 0,
                "current_publication_draft_artifact_count": 5,
                "current_publication_draft_artifact_pass_count": 5,
                "current_publication_draft_artifact_traceable_count": 5,
                "current_publication_draft_missing_source_key_count": 0,
                "current_publication_draft_missing_artifact_count": 0,
                "current_publication_draft_authorization_violation_count": 0,
                "current_publication_draft_failed_upstream_check_count": 0,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "sterile_repository_staging_manifest.json",
        {
            "summary": {
                "overall_status": (
                    "sterile_repository_staging_manifest_ready_no_repository_created"
                ),
                "phase_state": (
                    "neutral_sterile_repository_manifest_ready_creation_blocked"
                ),
                "staging_manifest_status": (
                    "manifest_ready_creation_and_release_blocked"
                ),
                "repository_visibility_at_creation": "private",
                "eventual_visibility": "public_after_user_review_if_approved",
                "required_content_row_count": 9,
                "required_content_traceable_count": 9,
                "required_content_with_blocking_gate_count": 9,
                "candidate_inclusion_risk_hit_count": 0,
                "post_program_exclusion_rule_count": 3,
                "expanded_exclusion_rule_count": 9,
                "exclusion_policy_row_count": 12,
                "exclusion_source_traceable_count": 12,
                "private_repository_created": False,
                "sterile_repository_creation_authorized": False,
                "sterile_release_packaging_authorized": False,
                "release_authorized": False,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "latex_html_authoring_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "working_repository_citation_status": (
                    "not_final_citable_repository"
                ),
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "analysis_only_no_champion_method": True,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "result_reporting_policy": (
                    "analysis_only_report_observed_behavior_no_method_advocacy"
                ),
                "authorization_violation_count": 0,
                "missing_source_artifact_count": 0,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        report_dir / "neutral_experiment_closure_audit.json",
        {
            "summary": {
                "overall_status": "neutral_experiment_closure_ready",
                "neutral_closure_ready": True,
                "goal_policy_update_required": False,
                "publication_phase_deferred": False,
                "publication_preparation_authorized": True,
                "failed_check_count": 0,
                "gate_count": 6,
                "final_disposition_gate_count": 6,
                "positive_claim_ready_gate_count": 0,
                "scoped_or_negative_path_ready_gate_count": 6,
                "ready_action_count": 0,
                "local_execution_gap_gate_count": 0,
                "publication_completed_rows": 145839,
                "neutral_language_unguarded_hit_count": 0,
            }
        },
    )


def passed_steps():
    return [
        {"step_id": step.step_id, "status": "pass", "required": step.required}
        for step in gate.STEPS
    ]


def test_dirty_snapshot_hashes_full_patch(monkeypatch, tmp_path):
    patch_body = {
        "text": (
            "diff --git a/experiments/regression/scripts/a.py "
            "b/experiments/regression/scripts/a.py\n"
            "+first gate implementation\n"
        )
    }

    def fake_git_stdout(root, args):
        key = tuple(args)
        if key == ("status", "--porcelain", "--untracked-files=all"):
            return " M experiments/regression/scripts/a.py\n?? scratch.txt\n"
        if key == ("status", "--porcelain", "--untracked-files=no"):
            return " M experiments/regression/scripts/a.py\n"
        if key == ("diff", "--stat"):
            return " experiments/regression/scripts/a.py | 1 +\n"
        if key == ("diff", "--name-status"):
            return "M\texperiments/regression/scripts/a.py\n"
        if key == ("diff", "--binary"):
            return patch_body["text"]
        if key == (
            "diff",
            "--binary",
            "--",
            "experiments/regression/scripts/a.py",
        ):
            return patch_body["text"]
        return ""

    monkeypatch.setattr(gate, "git_stdout", fake_git_stdout)

    first = gate.dirty_snapshot(tmp_path)
    patch_body["text"] = (
        "diff --git a/experiments/regression/scripts/a.py "
        "b/experiments/regression/scripts/a.py\n"
        "+second gate implementation\n"
    )
    second = gate.dirty_snapshot(tmp_path)

    assert first["schema"] == "cpfi_retrospective_dirty_snapshot_v2"
    assert first["is_dirty"] is True
    assert first["tracked_dirty"] is True
    assert first["dirty_path_count"] == 2
    assert first["tracked_dirty_path_count"] == 1
    assert first["untracked_path_count"] == 1
    assert first["relevant_dirty_path_count"] == 1
    assert first["relevant_dirty_paths"] == ["experiments/regression/scripts/a.py"]
    assert first["diff_name_status_sha256"] == second["diff_name_status_sha256"]
    assert first["diff_patch_sha256"] != second["diff_patch_sha256"]
    assert first["relevant_diff_patch_sha256"] != second["relevant_diff_patch_sha256"]
    assert first["dirty_digest_sha256"] != second["dirty_digest_sha256"]


def test_gate_payload_separates_pre_and_post_run_dirty(monkeypatch, tmp_path):
    pre_run_dirty = {
        "schema": gate.DIRTY_SNAPSHOT_SCHEMA,
        "is_dirty": False,
        "dirty_path_count": 0,
        "diff_name_status_sha256": "pre_names",
        "diff_patch_sha256": "pre_patch",
        "relevant_diff_patch_sha256": "pre_relevant",
    }
    post_run_dirty = {
        "schema": gate.DIRTY_SNAPSHOT_SCHEMA,
        "is_dirty": True,
        "dirty_path_count": 3,
        "diff_name_status_sha256": "post_names",
        "diff_patch_sha256": "post_patch",
        "relevant_diff_patch_sha256": "post_relevant",
    }

    monkeypatch.setattr(gate, "dirty_snapshot", lambda root: post_run_dirty)
    monkeypatch.setattr(
        gate,
        "build_scientific_summary",
        lambda root, steps: {"overall_status": "pass", "step_status_counts": {}},
    )

    payload = gate.gate_payload(
        root=tmp_path,
        step_results=[],
        complete=False,
        pre_run_dirty=pre_run_dirty,
        git_commit="abc123",
    )

    assert payload["git_commit"] == "abc123"
    assert payload["git_dirty"] == pre_run_dirty
    assert payload["pre_run_git_dirty"] == pre_run_dirty
    assert payload["post_run_git_dirty"] == post_run_dirty
    assert payload["git_dirty_semantics"]["git_dirty"] == (
        "backward_compatible_alias_for_pre_run_git_dirty"
    )


def test_quality_gate_summarizes_pass_with_caveats(tmp_path):
    write_minimal_artifacts(tmp_path)

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "pass_with_caveats"
    assert summary["hard_leakage_clean_in_scanned_artifacts"] is True
    assert summary["knowledge_graph"]["node_count"] == 10
    assert (
        summary["duplicate_sensitivity_closure"]["overall_status"]
        == "scoped_duplicate_sensitivity_closure_pass_with_caveats"
    )
    assert summary["duplicate_sensitivity_closure"]["hard_failed_check_count"] == 0
    assert (
        summary["duplicate_content_quarantine"]["overall_status"]
        == "duplicate_content_quarantine_pass"
    )
    assert summary["duplicate_content_quarantine"]["unquarantined_action_count"] == 0
    assert summary["endpoint_backfill_feasibility"]["completed_ledger_rows_ready"] == 10
    assert summary["manuscript_claim_register_consistency"]["overall_status"] == "pass"
    assert summary["final_selection_claim_boundary"]["overall_status"] == "pass"
    assert (
        summary["fairness_population_readiness"]["overall_status"]
        == "fairness_population_readiness_audit_completed_no_fairness_claim"
    )
    assert (
        summary["fairness_population_readiness"][
            "can_support_publication_ready_fairness"
        ]
        is False
    )
    assert (
        summary["fairness_population_readiness"][
            "population_fairness_ready_bundle_count"
        ]
        == 0
    )
    assert (
        summary["fairness_group_diagnostic_audit"]["overall_status"]
        == "fairness_group_diagnostic_audit_completed_no_fairness_claim"
    )
    assert (
        summary["fairness_group_diagnostic_audit"]["action_status"]
        == "empirical_execution_complete"
    )
    assert (
        summary["fairness_group_diagnostic_audit"][
            "group_gap_uncertainty_recorded_bundle_count"
        ]
        == 2
    )
    assert (
        summary["fairness_group_multiplicity_scope"]["overall_status"]
        == "fairness_group_multiplicity_scope_declared_no_fairness_claim"
    )
    assert (
        summary["fairness_group_multiplicity_scope"]["action_status"]
        == "multiplicity_control_complete"
    )
    assert (
        summary["fairness_group_multiplicity_scope"][
            "claim_register_cites_multiplicity_record"
        ]
        is True
    )
    assert (
        summary["fairness_group_multiplicity_scope"][
            "current_manuscript_fairness_population_claim_ready"
        ]
        is False
    )
    assert (
        summary["publication_methodology_readiness"]["overall_status"]
        == "publication_workbench_ready_with_caveats"
    )
    assert (
        summary["venn_abers_validation_readiness"]["overall_status"]
        == "venn_abers_validation_blocked_with_negative_evidence"
    )
    assert (
        summary["venn_abers_validation_readiness"][
            "can_support_venn_abers_regression_validation"
        ]
        is False
    )
    assert summary["venn_abers_validation_readiness"]["failed_check_count"] == 0
    assert (
        summary["venn_abers_grid_ivapd_validation_protocol"]["overall_status"]
        == "venn_abers_grid_ivapd_validation_protocol_defined_no_claim"
    )
    assert (
        summary["venn_abers_grid_ivapd_validation_protocol"][
            "can_support_validated_venn_abers_regression"
        ]
        is False
    )
    assert (
        summary["venn_abers_grid_ivapd_validation_protocol"]["validation_blocker_count"]
        == 4
    )
    assert (
        summary["venn_abers_grid_ivapd_validation_protocol"][
            "total_grid_reference_rows_scored"
        ]
        == 82
    )
    assert (
        summary["venn_abers_grid_expansion_plan"]["overall_status"]
        == "venn_abers_grid_expansion_plan_ready"
    )
    assert summary["venn_abers_grid_expansion_plan"]["total_grid_rows_pending"] == 5919
    assert summary["venn_abers_grid_expansion_plan"]["next_batch_total_rows"] == 340
    assert (
        summary["venn_abers_grid_expansion_plan"]["duplicate_next_batch_task_key_count"]
        == 0
    )
    assert (
        summary["venn_abers_grid_failure_mode_decomposition"]["overall_status"]
        == "venn_abers_grid_failure_modes_decomposed_no_claim"
    )
    assert (
        summary["venn_abers_grid_failure_mode_decomposition"][
            "coverage_failure_run_count"
        ]
        == 8
    )
    assert (
        summary["venn_abers_grid_failure_mode_decomposition"][
            "upper_boundary_failure_run_count"
        ]
        == 5
    )
    assert (
        summary["venn_abers_grid_failure_mode_decomposition"][
            "can_support_validated_venn_abers_regression"
        ]
        is False
    )
    assert (
        summary["venn_abers_claim_gate_matrix"]["overall_status"]
        == "venn_abers_claim_gate_matrix_blocked_with_complete_evidence"
    )
    assert (
        summary["venn_abers_claim_gate_matrix"][
            "can_support_validated_venn_abers_regression"
        ]
        is False
    )
    assert summary["venn_abers_claim_gate_matrix"]["failed_check_count"] == 0
    assert (
        summary["venn_abers_claim_gate_matrix"]["positive_claim_requirement_count"] == 4
    )
    assert summary["venn_abers_claim_gate_matrix"]["positive_claim_blocked_count"] == 4
    assert summary["venn_abers_claim_gate_matrix"][
        "blocked_positive_requirement_ids"
    ] == [
        "score_grid_full_test_scored",
        "score_grid_panel_coverage_nominal",
        "score_grid_upper_boundary_free",
        "ivapd_interval_cp_validated",
    ]
    assert (
        summary["method_literature_coverage"]["overall_status"]
        == "method_literature_coverage_pass"
    )
    assert summary["method_literature_coverage"]["failed_check_count"] == 0
    assert summary["method_literature_coverage"]["tracked_gap_count"] == 0
    assert (
        summary["selection_multiplicity_protocol"]["overall_status"]
        == "selection_multiplicity_protocol_defined_no_final_selection"
    )
    assert (
        summary["selection_multiplicity_protocol"]["can_support_final_method_selection"]
        is False
    )
    assert summary["selection_multiplicity_protocol"]["failed_check_count"] == 0
    assert summary["selection_multiplicity_protocol"]["ranking_scope_count"] == 15
    assert summary["selection_multiplicity_protocol"]["selection_record_count"] == 1
    assert (
        summary["selection_multiplicity_protocol"]["completed_ledger_rows_scanned"]
        == 145839
    )
    assert (
        summary["bounded_support_protocol"]["overall_status"]
        == "bounded_support_protocol_defined_no_validity_claim"
    )
    assert summary["bounded_support_protocol"]["failed_check_count"] == 0
    assert (
        summary["bounded_support_protocol"]["can_support_bounded_support_validity"]
        is False
    )
    assert (
        summary["bounded_support_protocol"][
            "publication_can_support_bounded_support_validity"
        ]
        is False
    )
    assert (
        summary["bounded_support_protocol"]["endpoint_bounded_support_gate_status"]
        == "blocked"
    )
    assert (
        summary["target_domain_provenance"]["overall_status"]
        == "target_domain_provenance_ready"
    )
    assert summary["target_domain_provenance"]["row_count"] == 5
    assert summary["target_domain_provenance"]["external_source_row_count"] == 1
    assert (
        summary["external_source_discovery_watchlist"]["overall_status"]
        == "external_source_discovery_watchlist_ready_with_gaps"
    )
    assert summary["external_source_discovery_watchlist"]["source_family_count"] == 19
    assert (
        summary["external_source_discovery_watchlist"]["pending_primary_family_count"]
        == 0
    )
    assert (
        summary["external_source_discovery_watchlist"]["local_audited_family_count"]
        == 18
    )
    assert (
        summary["external_source_discovery_watchlist"]["openml_discovery_rows"] == 675
    )
    assert summary["external_source_discovery_watchlist"]["openml_ranked_rows"] == 68
    assert summary["external_source_discovery_watchlist"]["failed_check_count"] == 0
    assert (
        summary["bounded_support_posthandling_validation"]["overall_status"]
        == "bounded_support_posthandling_validation_completed"
    )
    assert (
        summary["bounded_support_posthandling_validation"]["validated_bundle_count"]
        == 14
    )
    assert (
        summary["bounded_support_posthandling_validation"][
            "can_support_all_current_bounded_support_claims"
        ]
        is False
    )
    assert (
        summary["bounded_support_posthandling_validation"]["state_resumed_records"]
        == 14304
    )
    assert (
        summary["bounded_support_posthandling_validation"]["state_written_records"] == 0
    )
    assert (
        summary["bounded_support_dataset_audit"]["overall_status"]
        == "dataset_bounded_support_audit_completed_no_validity_claim"
    )
    assert summary["bounded_support_dataset_audit"]["bundle_count"] == 14
    assert (
        summary["bounded_support_dataset_audit"]["bounded_support_ready_bundle_count"]
        == 0
    )
    assert (
        summary["bounded_support_dataset_audit"][
            "natural_domain_excursion_unknown_count_bundle_count"
        ]
        == 0
    )
    assert (
        summary["bounded_support_dataset_audit"]["endpoint_support_clean_bundle_count"]
        == 2
    )
    assert (
        summary["bounded_support_dataset_audit"][
            "endpoint_support_not_applicable_bundle_count"
        ]
        == 1
    )
    assert (
        summary["bounded_support_dataset_audit"][
            "endpoint_support_blocked_or_incomplete_bundle_count"
        ]
        == 11
    )
    assert (
        summary["bounded_support_dataset_audit"]["target_domain_provenance_status"]
        == "target_domain_provenance_ready"
    )
    assert (
        summary["bounded_support_dataset_audit"]["can_support_bounded_support_validity"]
        is False
    )
    assert (
        summary["bounded_support_dataset_audit"]["endpoint_bounded_support_gate_status"]
        == "blocked"
    )
    assert (
        summary["bounded_support_endpoint_closure_audit"]["overall_status"]
        == "endpoint_policy_triage_closed_no_bounded_support_validity_claim"
    )
    assert (
        summary["bounded_support_endpoint_closure_audit"]["action_status"]
        == "empirical_execution_complete"
    )
    assert (
        summary["bounded_support_endpoint_closure_audit"][
            "open_endpoint_count_backfill_bundle_count"
        ]
        == 0
    )
    assert (
        summary["bounded_support_endpoint_closure_audit"][
            "current_manuscript_bounded_support_validity_claim_ready"
        ]
        is False
    )
    assert (
        summary["bounded_support_positive_validation_protocol"]["overall_status"]
        == "bounded_support_positive_validation_protocol_completed_no_validity_claim"
    )
    assert (
        summary["bounded_support_positive_validation_protocol"]["action_status"]
        == "empirical_validation_complete_no_bounded_support_claim"
    )
    assert (
        summary["bounded_support_positive_validation_protocol"][
            "positive_claim_ready_bundle_count"
        ]
        == 0
    )
    assert (
        summary["bounded_support_positive_validation_protocol"][
            "positive_acceptance_failed_count"
        ]
        == 4
    )
    assert (
        summary["experiment_accounting"]["overall_status"]
        == "experiment_accounting_pass"
    )
    assert summary["experiment_accounting"]["failed_check_count"] == 0
    assert summary["experiment_accounting"]["raw_ledger_row_count"] == 168853
    assert summary["experiment_accounting"]["canonical_ledger_row_count"] == 168761
    assert summary["experiment_accounting"]["canonical_completed_row_count"] == 156233
    assert summary["experiment_accounting"]["cross_run_completed_rows"] == 145839
    assert summary["experiment_accounting"]["publication_completed_rows"] == 145839
    assert (
        summary["experiment_accounting"]["selection_completed_rows_scanned"] == 145839
    )
    assert (
        summary["experiment_accounting"][
            "regular_completed_minus_cross_run_completed_rows"
        ]
        == 8167
    )
    assert (
        summary["experiment_accounting"]["bounded_support_selected_completed_rows"]
        == 14349
    )
    assert summary["experiment_accounting"]["venn_grid_rows_completed"] == 6001
    assert summary["experiment_accounting"]["venn_grid_rows_pending"] == 0
    assert (
        summary["method_performance_synthesis"]["overall_status"]
        == "method_performance_synthesis_descriptive_no_final_selection"
    )
    assert summary["method_performance_synthesis"]["failed_check_count"] == 0
    assert summary["method_performance_synthesis"]["completed_ledger_rows"] == 5
    assert summary["method_performance_synthesis"]["source_report_count"] == 2
    assert summary["method_performance_synthesis"]["method_count"] == 3
    assert summary["method_performance_synthesis"]["broad_support_method_count"] == 2
    assert summary["method_performance_synthesis"]["frontier_cell_count"] == 4
    assert (
        summary["method_performance_synthesis"]["can_support_final_method_selection"]
        is False
    )
    assert (
        summary["method_performance_synthesis"]["claim_status"]
        == "descriptive_no_final_selection"
    )
    assert (
        summary["method_selection_candidate_audit"]["overall_status"]
        == "method_selection_candidate_audit_ready_no_final_selection"
    )
    assert summary["method_selection_candidate_audit"]["failed_check_count"] == 0
    assert (
        summary["method_selection_candidate_audit"]["source_completed_ledger_rows"] == 5
    )
    assert summary["method_selection_candidate_audit"]["shortlist_method_count"] == 3
    assert (
        summary["method_selection_candidate_audit"]["primary_candidate_method"] == "cqr"
    )
    assert summary["method_selection_candidate_audit"]["paired_comparison_count"] == 2
    assert (
        summary["method_selection_candidate_audit"][
            "can_support_final_method_selection"
        ]
        is False
    )
    assert (
        summary["method_selection_candidate_audit"]["claim_status"]
        == "candidate_shortlist_ready_no_final_selection"
    )
    assert (
        summary["method_selection_candidate_audit"]["final_selection_claim_status"]
        == "blocked"
    )
    assert (
        summary["method_selection_robustness_audit"]["overall_status"]
        == "method_selection_robustness_audit_ready_no_final_selection"
    )
    assert summary["method_selection_robustness_audit"]["failed_check_count"] == 0
    assert (
        summary["method_selection_robustness_audit"]["source_completed_ledger_rows"]
        == 5
    )
    assert (
        summary["method_selection_robustness_audit"]["candidate_primary_method"]
        == "cqr"
    )
    assert (
        summary["method_selection_robustness_audit"]["common_dataset_alpha_cell_count"]
        == 30
    )
    assert (
        summary["method_selection_robustness_audit"]["common_cell_selected_method"]
        == "cqr"
    )
    assert (
        summary["method_selection_robustness_audit"]["alpha_balanced_selected_method"]
        == "cqr"
    )
    assert (
        summary["method_selection_robustness_audit"]["alpha_balanced_primary_retained"]
        is True
    )
    assert (
        summary["method_selection_robustness_audit"]["common_alpha_imbalance_status"]
        == "no_large_alpha_concentration"
    )
    assert (
        summary["method_selection_robustness_audit"]["bootstrap_primary_selection_rate"]
        == 0.9
    )
    assert (
        summary["method_selection_robustness_audit"][
            "can_support_final_method_selection"
        ]
        is False
    )
    assert (
        summary["method_selection_robustness_audit"]["claim_status"]
        == "selection_robustness_ready_no_final_selection"
    )
    assert (
        summary["method_selection_robustness_audit"]["final_selection_claim_status"]
        == "blocked"
    )
    assert (
        summary["method_selection_alpha_expansion_plan"]["overall_status"]
        == "method_selection_alpha_expansion_plan_not_needed"
    )
    assert summary["method_selection_alpha_expansion_plan"]["failed_check_count"] == 0
    assert (
        summary["method_selection_alpha_expansion_plan"][
            "additional_common_cells_needed_to_clear_threshold"
        ]
        == 0
    )
    assert (
        summary["method_selection_alpha_expansion_plan"][
            "can_support_final_method_selection"
        ]
        is False
    )
    assert (
        summary["method_selection_alpha_expansion_plan"]["final_selection_claim_status"]
        == "blocked"
    )
    assert (
        summary["method_selection_post_selection_validation_batch"]["overall_status"]
        == "method_selection_post_selection_validation_batch_ready"
    )
    assert (
        summary["method_selection_post_selection_validation_batch"][
            "expected_atomic_run_count"
        ]
        == 24
    )
    assert (
        summary["method_selection_post_selection_validation_results"]["overall_status"]
        == "method_selection_post_selection_validation_results_ready_no_final_selection"
    )
    assert (
        summary["method_selection_post_selection_validation_results"][
            "completed_atomic_run_count"
        ]
        == 24
    )
    assert (
        summary["method_selection_post_selection_validation_results"][
            "feature_leakage_violation_count"
        ]
        == 0
    )
    assert (
        summary["selection_multiplicity_evidence_record"]["overall_status"]
        == "selection_multiplicity_evidence_record_ready_no_final_selection"
    )
    assert (
        summary["selection_multiplicity_evidence_record"]["diagnostic_primary_method"]
        == "cqr"
    )
    assert (
        summary["selection_multiplicity_evidence_record"][
            "final_selection_claim_status"
        ]
        == "blocked"
    )
    assert (
        summary["method_selection_alpha_expansion_execution"]["overall_status"]
        == "method_selection_alpha_expansion_execution_closed_no_final_selection"
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "observed_execution_status"
        ]
        == "ledgers_completed"
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "completed_atomic_run_count"
        ]
        == 24
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "expected_atomic_run_count"
        ]
        == 24
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "batch_generation_label_stale_after_execution"
        ]
        is True
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "batch_generation_label_historical_only"
        ]
        is True
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "batch_reported_execution_status_is_historical"
        ]
        is True
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "batch_generation_label_reconciliation_status"
        ]
        == "reconciled_historical_config_generation_label_with_completed_ledgers"
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "batch_generation_label_requires_action"
        ]
        is False
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "execution_metadata_consistency_status"
        ]
        == "historical_batch_generation_label_reconciled_no_action_required"
    )
    assert (
        summary["method_selection_alpha_expansion_execution"]["active_execution_status"]
        == "ledgers_completed"
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "reconciled_execution_status"
        ]
        == "ledgers_completed"
    )
    assert (
        summary["method_selection_alpha_expansion_execution"][
            "final_selection_claim_status"
        ]
        == "blocked"
    )
    assert (
        summary["method_selection_inferential_audit"]["overall_status"]
        == "method_selection_inferential_audit_ready_no_final_selection"
    )
    assert summary["method_selection_inferential_audit"]["failed_check_count"] == 0
    assert (
        summary["method_selection_inferential_audit"]["primary_candidate_method"]
        == "cqr"
    )
    assert (
        summary["method_selection_inferential_audit"][
            "candidate_pairwise_comparison_count"
        ]
        == 2
    )
    assert (
        summary["method_selection_inferential_audit"][
            "candidate_min_shared_pairwise_cell_count"
        ]
        == 40
    )
    assert (
        summary["method_selection_inferential_audit"][
            "bootstrap_primary_selection_rate"
        ]
        == 0.95
    )
    assert (
        summary["method_selection_inferential_audit"][
            "post_selection_validation_primary_win_rate"
        ]
        == 0.72
    )
    assert (
        summary["method_selection_inferential_audit"][
            "main_result_candidate_primary_win_rate"
        ]
        == 0.66
    )
    assert (
        summary["method_selection_inferential_audit"][
            "can_support_final_method_selection"
        ]
        is False
    )
    assert (
        summary["method_selection_inferential_audit"]["claim_status"]
        == "inferential_method_selection_evidence_ready_no_final_selection"
    )
    assert (
        summary["method_selection_inferential_audit"]["final_selection_claim_status"]
        == "blocked"
    )
    assert (
        summary["manuscript_readiness_map"]["overall_status"]
        == "paper_readiness_blocked_with_evidence_map"
    )
    assert summary["manuscript_readiness_map"]["blocked_gate_count"] == 6
    assert summary["manuscript_readiness_map"]["main_surface_blocked_count"] == 1
    assert (
        summary["manuscript_bundle_eligibility_matrix"]["overall_status"]
        == "bundle_eligibility_matrix_ready_no_final_claims"
    )
    assert summary["manuscript_bundle_eligibility_matrix"]["bundle_count"] == 14
    assert (
        summary["manuscript_bundle_eligibility_matrix"]["main_results_eligible_count"]
        == 0
    )
    assert (
        summary["manuscript_bundle_eligibility_matrix"]["final_claim_eligible_count"]
        == 0
    )
    assert (
        summary["dataset_specific_final_gate_audit"]["overall_status"]
        == "dataset_specific_final_gate_audit_completed_no_final_dataset_promotions"
    )
    assert (
        summary["dataset_specific_final_gate_audit"]["main_result_ready_dataset_count"]
        == 0
    )
    assert (
        summary["dataset_final_gate_post_selection_validation_bridge"][
            "execution_status"
        ]
        == "completed_bridge_results"
    )
    assert (
        summary["dataset_final_gate_post_selection_validation_bridge"][
            "bridge_results_completed_atomic_run_count"
        ]
        == 12
    )
    assert (
        summary["dataset_final_gate_post_selection_validation_bridge_results"][
            "completed_atomic_run_count"
        ]
        == 12
    )
    assert (
        summary["main_result_candidate_bundle_plan"][
            "source_validation_combined_completed_atomic_rows"
        ]
        == 36
    )
    assert (
        summary["main_result_candidate_bundle_results"]["completed_atomic_run_count"]
        == 36
    )
    assert summary["main_result_candidate_post_run_closure"]["total_blocker_count"] == 0
    assert (
        summary["dataset_final_gate_remediation_plan"]["action_scope_counts"][
            "global_gate_dependency"
        ]
        == 6
    )
    assert (
        summary["dataset_final_gate_remediation_plan"][
            "dataset_with_no_remaining_execution_gap_count"
        ]
        == 2
    )
    assert (
        summary["venn_abers_negative_evidence_disposition"]["overall_status"]
        == "venn_abers_negative_evidence_disposition_pass"
    )
    assert (
        summary["venn_abers_negative_evidence_disposition"][
            "shortlist_venn_abers_method_count"
        ]
        == 0
    )
    assert (
        summary["venn_abers_negative_evidence_disposition"][
            "excluded_venn_abers_method_count"
        ]
        == 2
    )
    assert (
        summary["venn_abers_negative_evidence_disposition"][
            "venn_bundle_main_eligible_count"
        ]
        == 0
    )
    assert (
        summary["venn_abers_negative_evidence_disposition"][
            "final_selection_venn_abers_gate_status"
        ]
        == "blocked"
    )
    assert (
        summary["graph_artifact_readiness"]["overall_status"]
        == "graph_artifact_readiness_pass"
    )
    assert summary["graph_artifact_readiness"]["failed_check_count"] == 0
    assert summary["graph_artifact_readiness"]["all_required_tokens_present"] is True
    assert summary["graph_artifact_readiness"]["all_kg_graph_nodes_traceable"] is True
    assert (
        summary["paper_gate_protocol_design_bundle"]["overall_status"]
        == "paper_gate_protocol_design_bundle_ready_no_claim_promotions"
    )
    assert (
        summary["paper_gate_protocol_design_bundle"][
            "completed_protocol_design_action_count"
        ]
        == 4
    )
    assert (
        summary["paper_gate_closure_execution_plan"][
            "protocol_design_complete_action_count"
        ]
        == 5
    )
    assert (
        summary["paper_gate_closure_execution_plan"][
            "empirical_execution_complete_action_count"
        ]
        == 2
    )
    assert (
        summary["paper_gate_closure_execution_plan"][
            "endpoint_natural_domain_audit_complete_action_count"
        ]
        == 1
    )
    assert summary["paper_gate_closure_execution_plan"]["ready_action_count"] == 4
    assert (
        summary["fairness_sampling_weight_policy"]["overall_status"]
        == "fairness_sampling_weight_policy_defined_no_fairness_claim"
    )
    assert (
        summary["fairness_sampling_weight_policy"]["policy_declared_bundle_count"]
        == 2
    )
    assert (
        summary["fairness_group_diagnostic_audit"]["overall_status"]
        == "fairness_group_diagnostic_audit_completed_no_fairness_claim"
    )
    assert (
        summary["fairness_group_diagnostic_audit"][
            "group_counts_recorded_bundle_count"
        ]
        == 2
    )
    assert (
        summary["fairness_population_readiness"][
            "sampling_weight_policy_artifact_status"
        ]
        == "fairness_sampling_weight_policy_defined_no_fairness_claim"
    )
    assert (
        summary["kg_publication_quality"]["overall_status"]
        == "kg_publication_ready_with_polish_caveats"
    )
    assert (
        summary["scientific_review_finding_register"]["overall_status"]
        == "scientific_review_findings_tracked_with_open_caveats"
    )
    assert summary["scientific_review_finding_register"]["open_blocker_count"] == 0
    assert (
        summary["post_experiment_publication_activation_audit"]["overall_status"]
        == "post_experiment_publication_preparation_active_with_caveats"
    )
    assert (
        summary["post_experiment_publication_activation_audit"][
            "publication_phase_start_authorized"
        ]
        is True
    )
    assert (
        summary["post_experiment_publication_activation_audit"][
            "publication_preparation_authorized"
        ]
        is True
    )
    assert (
        summary["post_experiment_publication_activation_audit"]["blocked_check_count"]
        == 0
    )
    assert (
        summary["publication_preparation_packets"]["overall_status"]
        == "publication_preparation_packets_ready_no_final_prose"
    )
    assert summary["publication_preparation_packets"]["reviewer_packet_count"] == 5
    assert (
        summary["publication_preparation_packets"]["required_reviewer_pass_count"]
        == 5
    )
    assert (
        summary["publication_preparation_packets"][
            "visual_table_candidate_family_count"
        ]
        == 10
    )
    assert (
        summary["publication_preparation_packets"]["manuscript_drafting_authorized"]
        is False
    )
    assert (
        summary["publication_preparation_packets"]["positive_claim_publication_ready"]
        is False
    )
    assert (
        summary["publication_preparation_packets"][
            "neutral_no_method_promotion_guard_active"
        ]
        is True
    )
    assert (
        summary["reviewer_design_brief"]["overall_status"]
        == "reviewer_design_brief_ready_no_final_prose"
    )
    assert (
        summary["reviewer_design_brief"]["phase_state"]
        == "neutral_pre_prose_design_active_final_prose_and_release_blocked"
    )
    assert summary["reviewer_design_brief"]["advice_record_count"] == 25
    assert summary["reviewer_design_brief"]["reviewer_count"] == 5
    assert summary["reviewer_design_brief"]["required_reviewer_count"] == 5
    assert summary["reviewer_design_brief"]["content_matrix_row_count"] == 10
    assert (
        summary["reviewer_design_brief"][
            "neutral_no_method_promotion_guard_active"
        ]
        is True
    )
    assert (
        summary["reviewer_design_brief"]["final_manuscript_prose_permission"]
        is False
    )
    assert (
        summary["reviewer_design_brief"]["positive_claim_promotion_authorized"]
        is False
    )
    assert (
        summary["reviewer_design_brief"]["publication_site_deployment_authorized"]
        is False
    )
    assert (
        summary["publication_visual_audit_plan"]["overall_status"]
        == "publication_visual_audit_plan_ready_no_retained_artifacts"
    )
    assert (
        summary["publication_visual_audit_plan"]["phase_state"]
        == "neutral_pre_prose_visual_audit_planning_active_final_visuals_and_release_blocked"
    )
    assert summary["publication_visual_audit_plan"]["candidate_artifact_count"] == 10
    assert (
        summary["publication_visual_audit_plan"][
            "expected_candidate_artifact_count"
        ]
        == 10
    )
    assert (
        summary["publication_visual_audit_plan"]["visual_table_quality_check_count"]
        == 10
    )
    assert summary["publication_visual_audit_plan"]["triptych_component_count"] == 3
    assert (
        summary["publication_visual_audit_plan"][
            "visual_table_audit_plan_authorized"
        ]
        is True
    )
    assert (
        summary["publication_visual_audit_plan"][
            "visual_table_audit_execution_authorized"
        ]
        is False
    )
    assert (
        summary["publication_visual_audit_plan"][
            "final_visual_table_retention_authorized"
        ]
        is False
    )
    assert (
        summary["publication_visual_audit_plan"]["kg_citable_component_authorized"]
        is False
    )
    assert (
        summary["publication_visual_audit_plan"]["positive_claim_promotion_authorized"]
        is False
    )
    assert (
        summary["visual_table_audit_report"]["overall_status"]
        == "visual_table_pre_retention_audit_completed_no_retained_artifacts"
    )
    assert (
        summary["visual_table_audit_report"]["phase_state"]
        == "pre_retention_audit_complete_rendering_and_final_retention_blocked"
    )
    assert summary["visual_table_audit_report"]["inventory_row_count"] == 10
    assert summary["visual_table_audit_report"]["audit_row_count"] == 10
    assert (
        summary["visual_table_audit_report"]["source_traceable_candidate_count"]
        == 10
    )
    assert summary["visual_table_audit_report"]["iteration_action_count"] == 10
    assert summary["visual_table_audit_report"]["rendered_artifact_count"] == 0
    assert summary["visual_table_audit_report"]["layout_check_deferred_count"] == 10
    assert summary["visual_table_audit_report"]["final_retained_artifact_count"] == 0
    assert (
        summary["visual_table_audit_report"][
            "final_visual_table_retention_authorized"
        ]
        is False
    )
    assert (
        summary["visual_table_audit_report"]["kg_citable_component_authorized"]
        is False
    )
    assert (
        summary["visual_table_audit_report"]["positive_claim_promotion_authorized"]
        is False
    )
    assert (
        summary["visual_table_render_candidate_audit"]["overall_status"]
        == "draft_visual_table_render_audit_completed_no_final_retention"
    )
    assert (
        summary["visual_table_render_candidate_audit"]["phase_state"]
        == "draft_render_candidates_complete_final_retention_and_release_blocked"
    )
    assert (
        summary["visual_table_render_candidate_audit"][
            "pre_retention_input_row_count"
        ]
        == 10
    )
    assert summary["visual_table_render_candidate_audit"]["candidate_row_count"] == 10
    assert (
        summary["visual_table_render_candidate_audit"][
            "rendered_draft_artifact_count"
        ]
        == 10
    )
    assert (
        summary["visual_table_render_candidate_audit"]["layout_audit_row_count"]
        == 10
    )
    assert summary["visual_table_render_candidate_audit"]["layout_pass_count"] == 10
    assert summary["visual_table_render_candidate_audit"]["layout_revise_count"] == 0
    assert (
        summary["visual_table_render_candidate_audit"][
            "svg_static_text_overlap_detected_count"
        ]
        == 0
    )
    assert (
        summary["visual_table_render_candidate_audit"][
            "final_retained_artifact_count"
        ]
        == 0
    )
    assert (
        summary["visual_table_render_candidate_audit"][
            "final_visual_table_retention_authorized"
        ]
        is False
    )
    assert (
        summary["visual_table_render_candidate_audit"][
            "kg_citable_component_authorized"
        ]
        is False
    )
    assert (
        summary["visual_table_render_candidate_audit"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert (
        summary["publication_retention_readiness_audit"]["overall_status"]
        == "publication_retention_readiness_ready_no_final_prose"
    )
    assert (
        summary["publication_retention_readiness_audit"]["phase_state"]
        == "pre_manuscript_retention_recommendations_ready_final_prose_and_release_blocked"
    )
    assert (
        summary["publication_retention_readiness_audit"]["recommendation_row_count"]
        == 10
    )
    assert (
        summary["publication_retention_readiness_audit"]["render_candidate_count"]
        == 10
    )
    assert (
        summary["publication_retention_readiness_audit"][
            "main_article_candidate_count"
        ]
        == 4
    )
    assert (
        summary["publication_retention_readiness_audit"]["supplement_candidate_count"]
        == 5
    )
    assert (
        summary["publication_retention_readiness_audit"]["kg_or_site_candidate_count"]
        == 1
    )
    assert (
        summary["publication_retention_readiness_audit"][
            "retention_recommendation_complete"
        ]
        is True
    )
    assert (
        summary["publication_retention_readiness_audit"][
            "final_visual_table_retention_authorized"
        ]
        is False
    )
    assert (
        summary["publication_retention_readiness_audit"][
            "final_manuscript_prose_permission"
        ]
        is False
    )
    assert (
        summary["publication_retention_readiness_audit"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert (
        summary["final_publication_visual_auditor_readiness"]["overall_status"]
        == "final_publication_visual_auditor_feedback_loop_ready_no_retention"
    )
    assert (
        summary["final_publication_visual_auditor_readiness"]["phase_state"]
        == "pre_final_visual_auditor_feedback_ready_final_retention_blocked"
    )
    assert (
        summary["final_publication_visual_auditor_readiness"][
            "final_publication_visual_auditor_status"
        ]
        == "feedback_loop_ready_no_final_retention"
    )
    assert (
        summary["final_publication_visual_auditor_readiness"]["feedback_loop_ready"]
        is True
    )
    assert (
        summary["final_publication_visual_auditor_readiness"]["feedback_row_count"]
        == 10
    )
    assert (
        summary["final_publication_visual_auditor_readiness"][
            "feedback_ready_row_count"
        ]
        == 10
    )
    assert (
        summary["final_publication_visual_auditor_readiness"][
            "feedback_blocked_row_count"
        ]
        == 0
    )
    assert (
        summary["final_publication_visual_auditor_readiness"][
            "missing_rendered_artifact_count"
        ]
        == 0
    )
    assert (
        summary["final_publication_visual_auditor_readiness"][
            "final_visual_table_retention_authorized"
        ]
        is False
    )
    assert (
        summary["final_publication_visual_auditor_readiness"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert (
        summary["final_publication_visual_auditor_readiness"]["failed_check_count"]
        == 0
    )
    assert (
        summary["neutral_result_ledger"]["overall_status"]
        == "neutral_result_ledger_ready_no_method_promotion"
    )
    assert summary["neutral_result_ledger"]["row_count"] == 9
    assert summary["neutral_result_ledger"]["missing_source_artifact_count"] == 0
    assert (
        summary["neutral_result_ledger"][
            "positive_claim_promotion_authorized_count"
        ]
        == 0
    )
    assert (
        summary["neutral_result_ledger"][
            "final_method_selection_authorized_count"
        ]
        == 0
    )
    assert (
        summary["neutral_result_ledger"]["final_manuscript_prose_permission_count"]
        == 0
    )
    assert (
        summary["neutral_result_ledger"]["cqr_descriptive_candidate_recorded"]
        is True
    )
    assert (
        summary["neutral_result_ledger"]["venn_abers_negative_result_recorded"]
        is True
    )
    assert (
        summary["article_supplement_blueprint_alignment"]["overall_status"]
        == (
            "article_supplement_blueprint_alignment_ready_"
            "no_final_prose_no_method_promotion"
        )
    )
    assert (
        summary["article_supplement_blueprint_alignment"]["phase_state"]
        == (
            "neutral_pre_prose_blueprint_alignment_active_"
            "final_prose_and_release_blocked"
        )
    )
    assert (
        summary["article_supplement_blueprint_alignment"]["alignment_row_count"]
        == 10
    )
    assert (
        summary["article_supplement_blueprint_alignment"]["surface_row_count"]
        == 3
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "reviewer_alignment_issue_count"
        ]
        == 0
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "linked_neutral_result_issue_count"
        ]
        == 0
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "missing_source_artifact_count"
        ]
        == 0
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "venn_abers_negative_no_validated_claim"
        ]
        is True
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "cqr_cvplus_reporting_role"
        ]
        == "descriptive_diagnostic_no_final_selection_no_method_promotion"
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "final_manuscript_prose_permission"
        ]
        is False
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "method_recommendation_authorized"
        ]
        is False
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert (
        summary["publication_release_gap_register"]["overall_status"]
        == "publication_release_gap_register_ready_no_final_release"
    )
    assert (
        summary["publication_release_gap_register"]["phase_state"]
        == "neutral_pre_release_gap_register_active_final_release_blocked"
    )
    assert summary["publication_release_gap_register"]["deliverable_row_count"] == 11
    assert (
        summary["publication_release_gap_register"][
            "pre_prose_evidence_ready_row_count"
        ]
        == 11
    )
    assert summary["publication_release_gap_register"]["release_authorized_count"] == 0
    assert summary["publication_release_gap_register"]["blocked_release_row_count"] == 11
    assert (
        summary["publication_release_gap_register"]["source_traceable_row_count"]
        == 11
    )
    assert (
        summary["publication_release_gap_register"]["missing_source_artifact_count"]
        == 0
    )
    assert summary["publication_release_gap_register"]["goal_can_mark_complete"] is False
    assert summary["publication_release_gap_register"]["paper_blocked_gate_count"] == 6
    assert (
        summary["publication_release_gap_register"][
            "positive_claim_ready_gate_count"
        ]
        == 0
    )
    assert (
        summary["publication_release_gap_register"][
            "final_manuscript_prose_permission"
        ]
        is False
    )
    assert (
        summary["publication_release_gap_register"][
            "sterile_repository_creation_authorized"
        ]
        is False
    )
    assert (
        summary["publication_release_gap_register"]["method_recommendation_authorized"]
        is False
    )
    assert (
        summary["publication_release_gap_register"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert (
        summary["publication_release_gap_register"]["working_repository_final_citable"]
        is False
    )
    assert summary["publication_release_gap_register"]["failed_check_count"] == 0
    assert (
        summary["individual_experiment_report_blueprint"]["overall_status"]
        == "individual_experiment_report_blueprint_ready_no_final_prose"
    )
    assert (
        summary["individual_experiment_report_blueprint"]["phase_state"]
        == "neutral_pre_prose_individual_report_blueprint_active_final_outputs_blocked"
    )
    assert (
        summary["individual_experiment_report_blueprint"]["author_header"]
        == "Author: Emre Tasar, Data Scientist"
    )
    assert (
        summary["individual_experiment_report_blueprint"]["author_email"]
        == "detasar@gmail.com"
    )
    assert (
        summary["individual_experiment_report_blueprint"][
            "approved_author_header_present"
        ]
        is True
    )
    assert summary["individual_experiment_report_blueprint"]["section_row_count"] == 10
    assert (
        summary["individual_experiment_report_blueprint"][
            "source_traceable_row_count"
        ]
        == 10
    )
    assert (
        summary["individual_experiment_report_blueprint"][
            "missing_source_artifact_count"
        ]
        == 0
    )
    assert (
        summary["individual_experiment_report_blueprint"][
            "linked_neutral_result_issue_count"
        ]
        == 0
    )
    assert (
        summary["individual_experiment_report_blueprint"][
            "final_report_prose_permission"
        ]
        is False
    )
    assert (
        summary["individual_experiment_report_blueprint"]["release_authorized"]
        is False
    )
    assert (
        summary["individual_experiment_report_blueprint"][
            "method_recommendation_authorized"
        ]
        is False
    )
    assert (
        summary["individual_experiment_report_blueprint"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert (
        summary["individual_experiment_report_blueprint"]["cqr_reporting_role"]
        == "descriptive_diagnostic_no_final_selection"
    )
    assert (
        summary["individual_experiment_report_blueprint"]["venn_abers_reporting_role"]
        == "negative_failure_mode_no_validated_regression_claim"
    )
    assert summary["individual_experiment_report_blueprint"]["failed_check_count"] == 0
    assert (
        summary["claim_safe_result_extraction_matrix"]["overall_status"]
        == "claim_safe_result_extraction_matrix_ready_no_final_claims"
    )
    assert (
        summary["claim_safe_result_extraction_matrix"]["phase_state"]
        == "neutral_pre_prose_result_extraction_active_final_outputs_blocked"
    )
    assert summary["claim_safe_result_extraction_matrix"]["surface_row_count"] == 8
    assert (
        summary["claim_safe_result_extraction_matrix"]["source_traceable_row_count"]
        == 8
    )
    assert (
        summary["claim_safe_result_extraction_matrix"][
            "missing_source_artifact_count"
        ]
        == 0
    )
    assert (
        summary["claim_safe_result_extraction_matrix"][
            "linked_neutral_result_issue_count"
        ]
        == 0
    )
    assert (
        summary["claim_safe_result_extraction_matrix"][
            "safe_pre_prose_extraction_candidate_count"
        ]
        == 7
    )
    assert (
        summary["claim_safe_result_extraction_matrix"][
            "blocked_positive_surface_count"
        ]
        == 1
    )
    assert (
        summary["claim_safe_result_extraction_matrix"]["main_results_surface_status"]
        == "blocked_positive_claim_surface"
    )
    assert (
        summary["claim_safe_result_extraction_matrix"][
            "negative_results_surface_status"
        ]
        == "candidate_negative_result_surface"
    )
    assert (
        summary["claim_safe_result_extraction_matrix"][
            "main_result_positive_claim_blocked"
        ]
        is True
    )
    assert (
        summary["claim_safe_result_extraction_matrix"][
            "negative_result_reporting_ready"
        ]
        is True
    )
    assert (
        summary["claim_safe_result_extraction_matrix"][
            "final_manuscript_prose_permission"
        ]
        is False
    )
    assert (
        summary["claim_safe_result_extraction_matrix"][
            "method_recommendation_authorized"
        ]
        is False
    )
    assert (
        summary["claim_safe_result_extraction_matrix"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert summary["claim_safe_result_extraction_matrix"]["failed_check_count"] == 0
    assert (
        summary["manuscript_section_evidence_packet"]["overall_status"]
        == "manuscript_section_evidence_packet_ready_no_final_prose"
    )
    assert (
        summary["manuscript_section_evidence_packet"]["phase_state"]
        == "neutral_pre_prose_section_evidence_packet_active_final_outputs_blocked"
    )
    assert (
        summary["manuscript_section_evidence_packet"]["section_packet_row_count"]
        == 8
    )
    assert (
        summary["manuscript_section_evidence_packet"]["source_traceable_row_count"]
        == 8
    )
    assert (
        summary["manuscript_section_evidence_packet"][
            "missing_source_artifact_count"
        ]
        == 0
    )
    assert (
        summary["manuscript_section_evidence_packet"][
            "claim_safe_surface_link_issue_count"
        ]
        == 0
    )
    assert (
        summary["manuscript_section_evidence_packet"][
            "linked_neutral_result_issue_count"
        ]
        == 0
    )
    assert (
        summary["manuscript_section_evidence_packet"][
            "safe_pre_prose_evidence_packet_count"
        ]
        == 7
    )
    assert (
        summary["manuscript_section_evidence_packet"][
            "blocked_positive_packet_count"
        ]
        == 1
    )
    assert (
        summary["manuscript_section_evidence_packet"]["main_results_packet_status"]
        == "blocked_positive_claim_packet"
    )
    assert (
        summary["manuscript_section_evidence_packet"]["negative_packet_status"]
        == "pre_prose_negative_evidence_ready"
    )
    assert (
        summary["manuscript_section_evidence_packet"]["main_results_packet_blocked"]
        is True
    )
    assert (
        summary["manuscript_section_evidence_packet"]["negative_packet_ready"]
        is True
    )
    assert (
        summary["manuscript_section_evidence_packet"]["final_section_prose_authorized"]
        is False
    )
    assert (
        summary["manuscript_section_evidence_packet"][
            "final_manuscript_prose_permission"
        ]
        is False
    )
    assert (
        summary["manuscript_section_evidence_packet"][
            "method_recommendation_authorized"
        ]
        is False
    )
    assert (
        summary["manuscript_section_evidence_packet"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert summary["manuscript_section_evidence_packet"]["failed_check_count"] == 0
    assert (
        summary["section_claim_boundary_audit"]["overall_status"]
        == "section_claim_boundary_audit_pass_no_final_claims"
    )
    assert (
        summary["section_claim_boundary_audit"]["phase_state"]
        == (
            "neutral_pre_prose_section_claim_boundary_alignment_active_"
            "final_outputs_blocked"
        )
    )
    assert summary["section_claim_boundary_audit"]["boundary_row_count"] == 8
    assert summary["section_claim_boundary_audit"]["boundary_complete_row_count"] == 8
    assert (
        summary["section_claim_boundary_audit"]["allowed_use_complete_row_count"]
        == 8
    )
    assert (
        summary["section_claim_boundary_audit"]["blocked_use_complete_row_count"]
        == 8
    )
    assert (
        summary["section_claim_boundary_audit"][
            "claim_safe_surface_consistent_row_count"
        ]
        == 8
    )
    assert (
        summary["section_claim_boundary_audit"]["neutral_result_linked_row_count"]
        == 8
    )
    assert (
        summary["section_claim_boundary_audit"]["release_target_linked_row_count"]
        == 8
    )
    assert (
        summary["section_claim_boundary_audit"]["release_authorized_target_count"]
        == 0
    )
    assert (
        summary["section_claim_boundary_audit"][
            "neutral_ledger_prose_boundary_gap_unique_result_count"
        ]
        == 5
    )
    assert (
        summary["section_claim_boundary_audit"]["section_boundary_backfill_row_count"]
        == 8
    )
    assert (
        summary["section_claim_boundary_audit"][
            "main_results_positive_boundary_blocked"
        ]
        is True
    )
    assert (
        summary["section_claim_boundary_audit"][
            "venn_abers_negative_boundary_preserved"
        ]
        is True
    )
    assert summary["section_claim_boundary_audit"]["section_packet_clean"] is True
    assert summary["section_claim_boundary_audit"]["upstream_boundaries_clean"] is True
    assert summary["section_claim_boundary_audit"]["post_program_controlled"] is True
    assert (
        summary["section_claim_boundary_audit"]["final_section_prose_authorized"]
        is False
    )
    assert (
        summary["section_claim_boundary_audit"]["method_recommendation_authorized"]
        is False
    )
    assert (
        summary["section_claim_boundary_audit"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert summary["section_claim_boundary_audit"]["failed_check_count"] == 0
    assert (
        summary["article_supplement_kg_navigation_index"]["overall_status"]
        == "article_supplement_kg_navigation_index_ready_no_release"
    )
    assert (
        summary["article_supplement_kg_navigation_index"]["phase_state"]
        == "neutral_pre_release_navigation_index_active_final_outputs_blocked"
    )
    assert summary["article_supplement_kg_navigation_index"]["navigation_row_count"] == 9
    assert (
        summary["article_supplement_kg_navigation_index"][
            "section_navigation_row_count"
        ]
        == 8
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "kg_site_navigation_row_count"
        ]
        == 1
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "source_traceable_row_count"
        ]
        == 9
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "visual_table_candidate_index_row_count"
        ]
        == 10
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "visual_table_source_traceability_pass_count"
        ]
        == 10
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "visual_table_final_authorized_count"
        ]
        == 0
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "release_authorized_target_count"
        ]
        == 0
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "kg_node_reference_issue_count"
        ]
        == 0
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "main_results_positive_boundary_blocked"
        ]
        is True
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "venn_abers_negative_boundary_preserved"
        ]
        is True
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "scientific_no_method_promotion_guard_active"
        ]
        is True
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "method_recommendation_authorized"
        ]
        is False
    )
    assert (
        summary["article_supplement_kg_navigation_index"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert summary["article_supplement_kg_navigation_index"]["failed_check_count"] == 0
    assert (
        summary["publication_phase_progress_reconciliation"]["overall_status"]
        == "publication_phase_progress_reconciliation_ready_no_final_outputs"
    )
    assert (
        summary["publication_phase_progress_reconciliation"]["phase_state"]
        == "neutral_publication_progress_reconciled_final_outputs_blocked"
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "pre_prose_completed_control_count"
        ]
        == 8
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "pre_prose_control_count"
        ]
        == 8
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "resolved_prior_blocker_count"
        ]
        == 2
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "active_final_blocker_count"
        ]
        == 10
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "stale_goal_blocker_count"
        ]
        == 0
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "final_publication_visual_auditor_status"
        ]
        == "feedback_loop_ready_no_final_retention"
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "final_publication_visual_auditor_feedback_ready"
        ]
        is True
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "main_results_positive_boundary_blocked"
        ]
        is True
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "venn_abers_negative_boundary_preserved"
        ]
        is True
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "validated_venn_abers_regression_claim_ready"
        ]
        is False
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "method_recommendation_authorized"
        ]
        is False
    )
    assert (
        summary["publication_phase_progress_reconciliation"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert (
        summary["publication_phase_progress_reconciliation"]["failed_check_count"]
        == 0
    )
    assert (
        summary["neutral_reporting_language_audit"]["overall_status"]
        == "neutral_reporting_language_audit_pass"
    )
    assert summary["neutral_reporting_language_audit"]["unguarded_hit_count"] == 0
    assert summary["neutral_reporting_language_audit"]["failed_check_count"] == 0
    assert (
        summary["scientific_neutrality_interpretation_lock"]["overall_status"]
        == "scientific_neutrality_interpretation_lock_ready_no_method_promotion"
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"]["phase_state"]
        == "neutral_interpretation_locked_final_claims_and_outputs_blocked"
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"][
            "interpretation_row_count"
        ]
        == 8
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"][
            "cqr_cvplus_reporting_role"
        ]
        == "descriptive_diagnostic_no_final_selection_no_method_promotion"
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"][
            "venn_abers_reporting_role"
        ]
        == "negative_failure_mode_no_validated_regression_claim"
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"][
            "method_recommendation_authorized"
        ]
        is False
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"][
            "scientific_test_not_method_promotion"
        ]
        is True
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"][
            "analysis_only_no_champion_method"
        ]
        is True
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"][
            "method_champion_authorized"
        ]
        is False
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"][
            "result_reporting_policy"
        ]
        == "analysis_only_report_observed_behavior_no_method_advocacy"
    )
    assert (
        summary["scientific_neutrality_interpretation_lock"]["failed_check_count"]
        == 0
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "overall_status"
        ]
        == "final_publication_output_authorization_protocol_ready_no_authorizations"
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "final_output_authorization_protocol_status"
        ]
        == "protocol_ready_all_final_outputs_blocked"
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "authorization_row_count"
        ]
        == 10
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "blocked_authorization_row_count"
        ]
        == 10
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "ready_to_authorize_output_count"
        ]
        == 0
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "method_recommendation_authorized"
        ]
        is False
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "final_manuscript_prose_permission"
        ]
        is False
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "failed_check_count"
        ]
        == 0
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "analysis_only_no_champion_method"
        ]
        is True
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "method_champion_authorized"
        ]
        is False
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "result_reporting_policy"
        ]
        == "analysis_only_report_observed_behavior_no_method_advocacy"
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "overall_status"
        ]
        == "publication_claim_evidence_verification_ready_no_final_prose"
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "verification_row_count"
        ]
        == 8
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "verification_pass_count"
        ]
        == 8
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "boundary_aligned_row_count"
        ]
        == 8
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "navigation_aligned_row_count"
        ]
        == 8
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "kg_reference_issue_count"
        ]
        == 0
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "safe_pre_prose_evidence_row_count"
        ]
        == 7
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "blocked_positive_row_count"
        ]
        == 1
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "venn_abers_negative_ready_row_count"
        ]
        == 1
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "current_publication_draft_artifact_count"
        ]
        == 5
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "current_publication_draft_artifact_pass_count"
        ]
        == 5
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "current_publication_draft_artifact_traceable_count"
        ]
        == 5
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "current_publication_draft_missing_source_key_count"
        ]
        == 0
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "current_publication_draft_authorization_violation_count"
        ]
        == 0
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "method_champion_authorized"
        ]
        is False
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "positive_claim_promotion_authorized"
        ]
        is False
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "failed_check_count"
        ]
        == 0
    )
    assert (
        summary["sterile_repository_staging_manifest"]["overall_status"]
        == "sterile_repository_staging_manifest_ready_no_repository_created"
    )
    assert (
        summary["sterile_repository_staging_manifest"]["staging_manifest_status"]
        == "manifest_ready_creation_and_release_blocked"
    )
    assert (
        summary["sterile_repository_staging_manifest"][
            "required_content_row_count"
        ]
        == 9
    )
    assert (
        summary["sterile_repository_staging_manifest"][
            "exclusion_policy_row_count"
        ]
        == 12
    )
    assert (
        summary["sterile_repository_staging_manifest"][
            "candidate_inclusion_risk_hit_count"
        ]
        == 0
    )
    assert (
        summary["sterile_repository_staging_manifest"][
            "private_repository_created"
        ]
        is False
    )
    assert (
        summary["sterile_repository_staging_manifest"][
            "sterile_repository_creation_authorized"
        ]
        is False
    )
    assert (
        summary["sterile_repository_staging_manifest"]["release_authorized"]
        is False
    )
    assert (
        summary["sterile_repository_staging_manifest"][
            "working_repository_final_citable"
        ]
        is False
    )
    assert (
        summary["sterile_repository_staging_manifest"][
            "analysis_only_no_champion_method"
        ]
        is True
    )
    assert (
        summary["sterile_repository_staging_manifest"][
            "method_champion_authorized"
        ]
        is False
    )
    assert (
        summary["sterile_repository_staging_manifest"][
            "result_reporting_policy"
        ]
        == "analysis_only_report_observed_behavior_no_method_advocacy"
    )
    assert (
        summary["sterile_repository_staging_manifest"]["failed_check_count"]
        == 0
    )
    assert (
        summary["neutral_experiment_closure_audit"]["overall_status"]
        == "neutral_experiment_closure_ready"
    )
    assert summary["neutral_experiment_closure_audit"]["neutral_closure_ready"] is True
    assert (
        summary["neutral_experiment_closure_audit"]["goal_policy_update_required"]
        is False
    )
    assert (
        summary["neutral_experiment_closure_audit"][
            "publication_preparation_authorized"
        ]
        is True
    )


def test_quality_gate_accepts_complete_venn_abers_grid_expansion_plan(tmp_path):
    write_minimal_artifacts(tmp_path)
    plan_report = tmp_path / gate.REPORT_DIR / "venn_abers_grid_expansion_plan.json"
    payload = json.loads(plan_report.read_text(encoding="utf-8"))
    payload["summary"].update(
        {
            "overall_status": "venn_abers_grid_expansion_plan_complete",
            "failed_check_count": 0,
            "task_status_counts": {"complete": 14},
            "total_grid_rows_completed": 6001,
            "total_grid_rows_pending": 0,
            "grid_completion_fraction": 1.0,
            "next_batch_total_rows": 0,
            "duplicate_next_batch_task_key_count": 0,
        }
    )
    write_json(plan_report, payload)
    claim_gate_report = tmp_path / gate.REPORT_DIR / "venn_abers_claim_gate_matrix.json"
    claim_payload = json.loads(claim_gate_report.read_text(encoding="utf-8"))
    claim_payload["summary"].update(
        {
            "positive_claim_pass_count": 1,
            "positive_claim_blocked_count": 3,
            "blocked_positive_requirement_ids": [
                "score_grid_panel_coverage_nominal",
                "score_grid_upper_boundary_free",
                "ivapd_interval_cp_validated",
            ],
            "total_grid_reference_rows_scored": 6001,
            "total_grid_reference_rows_available": 6001,
        }
    )
    write_json(claim_gate_report, claim_payload)

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "pass_with_caveats"
    assert (
        summary["venn_abers_grid_expansion_plan"]["overall_status"]
        == "venn_abers_grid_expansion_plan_complete"
    )
    assert summary["venn_abers_grid_expansion_plan"]["total_grid_rows_pending"] == 0
    assert summary["venn_abers_grid_expansion_plan"]["next_batch_total_rows"] == 0
    assert summary["venn_abers_claim_gate_matrix"]["positive_claim_pass_count"] == 1
    assert summary["venn_abers_claim_gate_matrix"]["positive_claim_blocked_count"] == 3


def test_quality_gate_fails_for_hard_leakage(tmp_path):
    write_minimal_artifacts(tmp_path, hard_leakage=True)

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["hard_leakage_clean_in_scanned_artifacts"] is False


def test_quality_gate_fails_for_required_step_or_medium_kg_issue(tmp_path):
    write_minimal_artifacts(tmp_path, kg_medium_issue=True, caveat=False)
    failed_steps = passed_steps()
    failed_steps[0] = {**failed_steps[0], "status": "fail"}

    summary = gate.build_scientific_summary(tmp_path, failed_steps)

    assert summary["overall_status"] == "fail"
    assert summary["failed_required_steps"] == [gate.STEPS[0].step_id]
    assert summary["knowledge_graph"]["status"] == "fail"


def test_quality_gate_fails_for_claim_register_inconsistency(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path / gate.REPORT_DIR / "manuscript_claim_register_consistency_audit.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "fail"
    payload["summary"]["failed_claim_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["manuscript_claim_register_consistency"]["failed_claim_count"] == 1


def test_quality_gate_fails_for_publication_methodology_failure(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / gate.REPORT_DIR / "publication_methodology_audit.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "fail"
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["publication_methodology_readiness"]["failed_check_count"] == 1


def test_quality_gate_fails_for_unguarded_neutral_reporting_language(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / gate.REPORT_DIR / "neutral_reporting_language_audit.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "neutral_reporting_language_audit_fail"
    payload["summary"]["unguarded_hit_count"] = 1
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["neutral_reporting_language_audit"]["unguarded_hit_count"] == 1


def test_quality_gate_fails_for_blocked_scientific_neutrality_lock(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/"
        / "scientific_neutrality_interpretation_lock.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = (
        "scientific_neutrality_interpretation_lock_blocked"
    )
    payload["summary"]["method_recommendation_authorized"] = True
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["scientific_neutrality_interpretation_lock"][
            "method_recommendation_authorized"
        ]
        is True
    )


def test_quality_gate_fails_for_blocked_final_output_authorization_protocol(
    tmp_path,
):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/"
        / "final_publication_output_authorization_protocol.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = (
        "final_publication_output_authorization_protocol_blocked"
    )
    payload["summary"]["ready_to_authorize_output_count"] = 1
    payload["summary"]["final_manuscript_prose_permission"] = True
    payload["summary"]["authorization_violation_count"] = 1
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["final_publication_output_authorization_protocol"][
            "ready_to_authorize_output_count"
        ]
        == 1
    )
    assert (
        summary["final_publication_output_authorization_protocol"][
            "final_manuscript_prose_permission"
        ]
        is True
    )


def test_quality_gate_fails_for_claim_evidence_verification_break(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/"
        / "publication_claim_evidence_verification_matrix.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = (
        "publication_claim_evidence_verification_blocked"
    )
    payload["summary"]["verification_pass_count"] = 7
    payload["summary"]["kg_reference_issue_count"] = 1
    payload["summary"]["method_champion_authorized"] = True
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "verification_pass_count"
        ]
        == 7
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "kg_reference_issue_count"
        ]
        == 1
    )
    assert (
        summary["publication_claim_evidence_verification_matrix"][
            "method_champion_authorized"
        ]
        is True
    )


def test_quality_gate_fails_for_sterile_repository_staging_manifest_release(
    tmp_path,
):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/"
        / "sterile_repository_staging_manifest.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "sterile_repository_staging_manifest_blocked"
    payload["summary"]["private_repository_created"] = True
    payload["summary"]["sterile_repository_creation_authorized"] = True
    payload["summary"]["release_authorized"] = True
    payload["summary"]["authorization_violation_count"] = 1
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["sterile_repository_staging_manifest"][
            "private_repository_created"
        ]
        is True
    )
    assert (
        summary["sterile_repository_staging_manifest"]["release_authorized"]
        is True
    )


def test_quality_gate_fails_for_blocked_neutral_experiment_closure(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / gate.REPORT_DIR / "neutral_experiment_closure_audit.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "neutral_experiment_closure_blocked"
    payload["summary"]["neutral_closure_ready"] = False
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["neutral_experiment_closure_audit"]["neutral_closure_ready"] is False


def test_quality_gate_fails_for_method_literature_hard_failure(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / gate.REPORT_DIR / "method_literature_coverage_audit.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "fail"
    payload["summary"]["failed_check_count"] = 1
    payload["summary"]["hard_failed_requirement_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["method_literature_coverage"]["failed_check_count"] == 1
    assert summary["method_literature_coverage"]["hard_failed_requirement_count"] == 1


def test_quality_gate_fails_for_duplicate_sensitivity_closure_failure(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / gate.REPORT_DIR / "duplicate_sensitivity_closure_audit.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "fail"
    payload["summary"]["hard_failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["duplicate_sensitivity_closure"]["hard_failed_check_count"] == 1


def test_quality_gate_fails_for_duplicate_content_quarantine_failure(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / gate.REPORT_DIR / "duplicate_content_quarantine_audit.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "duplicate_content_quarantine_fail"
    payload["summary"]["failed_check_count"] = 1
    payload["summary"]["unquarantined_action_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["duplicate_content_quarantine"]["failed_check_count"] == 1
    assert summary["duplicate_content_quarantine"]["unquarantined_action_count"] == 1


def test_quality_gate_fails_for_venn_abers_negative_disposition_failure(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / gate.REPORT_DIR
        / "venn_abers_negative_evidence_disposition_audit.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"][
        "overall_status"
    ] = "venn_abers_negative_evidence_disposition_fail"
    payload["summary"]["failed_check_count"] = 1
    payload["summary"]["shortlist_venn_abers_method_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["venn_abers_negative_evidence_disposition"]["failed_check_count"] == 1
    )
    assert (
        summary["venn_abers_negative_evidence_disposition"][
            "shortlist_venn_abers_method_count"
        ]
        == 1
    )


def test_quality_gate_fails_for_kg_publication_hard_failure(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / gate.REPORT_DIR / "kg_publication_quality_audit.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "fail_current_snapshot"
    payload["summary"]["hard_failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["kg_publication_quality"]["hard_failed_check_count"] == 1


def test_quality_gate_fails_when_publication_preparation_packets_not_clean(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/publication_preparation_packets.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "publication_preparation_packets_blocked"
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["publication_preparation_packets"]["failed_check_count"] == 1


def test_quality_gate_fails_when_publication_preparation_promotes_methods(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/publication_preparation_packets.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["neutral_no_method_promotion_guard_active"] = False
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["publication_preparation_packets"][
            "neutral_no_method_promotion_guard_active"
        ]
        is False
    )


def test_quality_gate_fails_when_reviewer_design_brief_not_clean(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/reviewer_design_brief.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "reviewer_design_brief_blocked"
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["reviewer_design_brief"]["failed_check_count"] == 1


def test_quality_gate_fails_when_reviewer_design_allows_final_prose(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/reviewer_design_brief.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["final_manuscript_prose_permission"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["reviewer_design_brief"]["final_manuscript_prose_permission"]
        is True
    )


def test_quality_gate_fails_when_reviewer_design_authorizes_final_retention(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/reviewer_design_brief.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["final_retain_decision_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["reviewer_design_brief"]["final_retain_decision_authorized"] is True


def test_quality_gate_fails_when_reviewer_design_promotes_claims(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/reviewer_design_brief.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["positive_claim_promotion_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["reviewer_design_brief"]["positive_claim_promotion_authorized"]
        is True
    )


def test_quality_gate_fails_when_reviewer_design_disables_neutral_guard(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/reviewer_design_brief.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["neutral_no_method_promotion_guard_active"] = False
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["reviewer_design_brief"]["neutral_no_method_promotion_guard_active"]
        is False
    )


def test_quality_gate_fails_when_reviewer_design_authorizes_site_deployment(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/reviewer_design_brief.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["publication_site_deployment_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["reviewer_design_brief"]["publication_site_deployment_authorized"]
        is True
    )


def test_quality_gate_fails_when_visual_audit_plan_not_clean(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/visual_table_audit_plan.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "publication_visual_audit_plan_blocked"
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["publication_visual_audit_plan"]["failed_check_count"] == 1


def test_quality_gate_fails_when_visual_audit_execution_is_authorized(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/visual_table_audit_plan.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["visual_table_audit_execution_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["publication_visual_audit_plan"][
            "visual_table_audit_execution_authorized"
        ]
        is True
    )


def test_quality_gate_fails_when_visual_audit_authorizes_final_retention(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/visual_table_audit_plan.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["final_visual_table_retention_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["publication_visual_audit_plan"][
            "final_visual_table_retention_authorized"
        ]
        is True
    )


def test_quality_gate_fails_when_visual_plan_authorizes_kg_citation(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/visual_table_audit_plan.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["kg_citable_component_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["publication_visual_audit_plan"]["kg_citable_component_authorized"]
        is True
    )


def test_quality_gate_fails_when_visual_plan_promotes_claims(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/visual_table_audit_plan.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["positive_claim_promotion_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["publication_visual_audit_plan"]["positive_claim_promotion_authorized"]
        is True
    )


def test_quality_gate_fails_when_visual_table_audit_report_not_clean(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path / "experiments/regression/manuscript/visual_table_audit_report.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "visual_table_pre_retention_audit_blocked"
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["visual_table_audit_report"]["failed_check_count"] == 1


def test_quality_gate_fails_when_visual_table_audit_report_retains_artifacts(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path / "experiments/regression/manuscript/visual_table_audit_report.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["final_retained_artifact_count"] = 1
    payload["summary"]["final_visual_table_retention_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["visual_table_audit_report"]["final_retained_artifact_count"] == 1
    assert (
        summary["visual_table_audit_report"][
            "final_visual_table_retention_authorized"
        ]
        is True
    )


def test_quality_gate_fails_when_visual_table_audit_report_has_rendered_artifact(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path / "experiments/regression/manuscript/visual_table_audit_report.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["rendered_artifact_count"] = 1
    payload["summary"]["layout_check_deferred_count"] = 9
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["visual_table_audit_report"]["rendered_artifact_count"] == 1


def test_quality_gate_fails_when_visual_table_audit_report_releases_kg(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path / "experiments/regression/manuscript/visual_table_audit_report.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["kg_citable_component_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["visual_table_audit_report"]["kg_citable_component_authorized"]
        is True
    )


def test_quality_gate_fails_when_visual_table_audit_report_promotes_claims(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path / "experiments/regression/manuscript/visual_table_audit_report.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["positive_claim_promotion_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["visual_table_audit_report"]["positive_claim_promotion_authorized"]
        is True
    )


def test_quality_gate_fails_when_visual_table_render_candidate_audit_not_clean(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "draft_visual_table_render_audit_blocked"
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["visual_table_render_candidate_audit"]["failed_check_count"] == 1


def test_quality_gate_fails_when_visual_table_render_candidate_layout_revises(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["layout_pass_count"] = 9
    payload["summary"]["layout_revise_count"] = 1
    payload["summary"]["svg_static_text_overlap_detected_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["visual_table_render_candidate_audit"]["layout_revise_count"] == 1
    assert (
        summary["visual_table_render_candidate_audit"][
            "svg_static_text_overlap_detected_count"
        ]
        == 1
    )


def test_quality_gate_fails_when_visual_table_render_candidate_retains_artifacts(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["final_retained_artifact_count"] = 1
    payload["summary"]["final_visual_table_retention_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["visual_table_render_candidate_audit"][
            "final_retained_artifact_count"
        ]
        == 1
    )
    assert (
        summary["visual_table_render_candidate_audit"][
            "final_visual_table_retention_authorized"
        ]
        is True
    )


def test_quality_gate_fails_when_visual_table_render_candidate_promotes_claims(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["positive_claim_promotion_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["visual_table_render_candidate_audit"][
            "positive_claim_promotion_authorized"
        ]
        is True
    )


def test_quality_gate_fails_when_retention_readiness_authorizes_final_outputs(
    tmp_path,
):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/publication_retention_readiness_audit.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["final_retained_artifact_count"] = 1
    payload["summary"]["final_visual_table_retention_authorized"] = True
    payload["summary"]["final_manuscript_prose_permission"] = True
    payload["summary"]["positive_claim_promotion_authorized"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["publication_retention_readiness_audit"][
            "final_retained_artifact_count"
        ]
        == 1
    )
    assert (
        summary["publication_retention_readiness_audit"][
            "final_visual_table_retention_authorized"
        ]
        is True
    )
    assert (
        summary["publication_retention_readiness_audit"][
            "final_manuscript_prose_permission"
        ]
        is True
    )
    assert (
        summary["publication_retention_readiness_audit"][
            "positive_claim_promotion_authorized"
        ]
        is True
    )


def test_quality_gate_fails_when_retention_readiness_loses_recommendations(
    tmp_path,
):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/publication_retention_readiness_audit.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["recommendation_row_count"] = 9
    payload["summary"]["main_article_candidate_count"] = 3
    payload["summary"]["retention_recommendation_complete"] = False
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["publication_retention_readiness_audit"][
            "recommendation_row_count"
        ]
        == 9
    )
    assert (
        summary["publication_retention_readiness_audit"][
            "main_article_candidate_count"
        ]
        == 3
    )
    assert (
        summary["publication_retention_readiness_audit"][
            "retention_recommendation_complete"
        ]
        is False
    )
    assert (
        summary["publication_retention_readiness_audit"]["failed_check_count"]
        == 1
    )


def test_quality_gate_fails_when_final_visual_auditor_readiness_blocks(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/"
        / "final_publication_visual_auditor_readiness.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = (
        "final_publication_visual_auditor_feedback_loop_blocked"
    )
    payload["summary"]["feedback_loop_ready"] = False
    payload["summary"]["feedback_ready_row_count"] = 9
    payload["summary"]["feedback_blocked_row_count"] = 1
    payload["summary"]["missing_rendered_artifact_count"] = 1
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["final_publication_visual_auditor_readiness"][
            "feedback_loop_ready"
        ]
        is False
    )
    assert (
        summary["final_publication_visual_auditor_readiness"][
            "feedback_blocked_row_count"
        ]
        == 1
    )
    assert (
        summary["final_publication_visual_auditor_readiness"][
            "missing_rendered_artifact_count"
        ]
        == 1
    )
    assert (
        summary["final_publication_visual_auditor_readiness"]["failed_check_count"]
        == 1
    )


def test_quality_gate_fails_when_blueprint_alignment_promotes_methods(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/"
        / "article_supplement_blueprint_alignment.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["final_manuscript_prose_permission"] = True
    payload["summary"]["method_recommendation_authorized"] = True
    payload["summary"]["positive_claim_promotion_authorized"] = True
    payload["summary"]["venn_abers_negative_no_validated_claim"] = False
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["article_supplement_blueprint_alignment"][
            "final_manuscript_prose_permission"
        ]
        is True
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "method_recommendation_authorized"
        ]
        is True
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "positive_claim_promotion_authorized"
        ]
        is True
    )
    assert (
        summary["article_supplement_blueprint_alignment"][
            "venn_abers_negative_no_validated_claim"
        ]
        is False
    )


def test_quality_gate_fails_when_publication_release_gap_authorizes_release(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/"
        / "publication_release_gap_register.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["release_authorized_count"] = 1
    payload["summary"]["final_manuscript_prose_permission"] = True
    payload["summary"]["sterile_repository_creation_authorized"] = True
    payload["summary"]["method_recommendation_authorized"] = True
    payload["summary"]["positive_claim_promotion_authorized"] = True
    payload["summary"]["working_repository_final_citable"] = True
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["publication_release_gap_register"]["release_authorized_count"] == 1
    assert (
        summary["publication_release_gap_register"][
            "final_manuscript_prose_permission"
        ]
        is True
    )
    assert (
        summary["publication_release_gap_register"][
            "sterile_repository_creation_authorized"
        ]
        is True
    )
    assert (
        summary["publication_release_gap_register"]["method_recommendation_authorized"]
        is True
    )
    assert (
        summary["publication_release_gap_register"][
            "positive_claim_promotion_authorized"
        ]
        is True
    )
    assert (
        summary["publication_release_gap_register"]["working_repository_final_citable"]
        is True
    )


def test_quality_gate_fails_when_individual_report_blueprint_authorizes_outputs(
    tmp_path,
):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = (
        tmp_path
        / "experiments/regression/manuscript/"
        / "individual_experiment_report_blueprint.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["final_report_prose_permission"] = True
    payload["summary"]["latex_output_authorized"] = True
    payload["summary"]["release_authorized"] = True
    payload["summary"]["method_recommendation_authorized"] = True
    payload["summary"]["positive_claim_promotion_authorized"] = True
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["individual_experiment_report_blueprint"][
            "final_report_prose_permission"
        ]
        is True
    )
    assert (
        summary["individual_experiment_report_blueprint"]["latex_output_authorized"]
        is True
    )
    assert (
        summary["individual_experiment_report_blueprint"]["release_authorized"]
        is True
    )
    assert (
        summary["individual_experiment_report_blueprint"][
            "method_recommendation_authorized"
        ]
        is True
    )
    assert (
        summary["individual_experiment_report_blueprint"][
            "positive_claim_promotion_authorized"
        ]
        is True
    )


def test_quality_gate_fails_when_neutral_result_ledger_promotes_claims(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/neutral_result_ledger.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["positive_claim_promotion_authorized_count"] = 1
    payload["summary"]["final_method_selection_authorized_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["neutral_result_ledger"][
            "positive_claim_promotion_authorized_count"
        ]
        == 1
    )
    assert (
        summary["neutral_result_ledger"][
            "final_method_selection_authorized_count"
        ]
        == 1
    )


def test_quality_gate_fails_when_neutral_result_ledger_loses_boundaries(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / "experiments/regression/manuscript/neutral_result_ledger.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["cqr_descriptive_candidate_recorded"] = False
    payload["summary"]["venn_abers_negative_result_recorded"] = False
    payload["summary"]["failed_check_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert (
        summary["neutral_result_ledger"]["cqr_descriptive_candidate_recorded"]
        is False
    )
    assert (
        summary["neutral_result_ledger"]["venn_abers_negative_result_recorded"]
        is False
    )
    assert summary["neutral_result_ledger"]["failed_check_count"] == 1


def test_quality_gate_fails_for_scientific_review_open_blocker(tmp_path):
    write_minimal_artifacts(tmp_path, caveat=False)
    report = tmp_path / gate.REPORT_DIR / "scientific_review_finding_register.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "scientific_review_findings_fail"
    payload["summary"]["status_counts"] = {"closed": 10, "open_blocker": 1}
    payload["summary"]["open_blocker_count"] = 1
    payload["summary"]["hard_open_blocker_count"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = gate.build_scientific_summary(tmp_path, passed_steps())

    assert summary["overall_status"] == "fail"
    assert summary["scientific_review_finding_register"]["open_blocker_count"] == 1
    assert summary["scientific_review_finding_register"]["hard_open_blocker_count"] == 1
