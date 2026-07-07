import json

from experiments.regression.scripts import build_manuscript_readiness_map as readiness


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_readiness_sources(root):
    report_dir = root / readiness.REPORT_DIR
    requirement_statuses = {
        "dataset_specific_final_gates": "blocked",
        "endpoint_bounded_support_gate": "blocked",
        "fairness_population_inference_gate": "blocked",
        "final_method_model_selection_gate": "blocked",
        "multiplicity_selection_record": "blocked",
        "remediation_backlog_closed_or_scoped": "pass",
        "venn_abers_regression_validation_gate": "blocked",
    }
    write_json(
        root / readiness.PUBLICATION_METHODOLOGY,
        {
            "summary": {"overall_status": "publication_workbench_ready_with_caveats"},
            "requirement_statuses": requirement_statuses,
        },
    )
    write_json(
        root / readiness.SELECTION_MULTIPLICITY_PROTOCOL,
        {
            "summary": {
                "overall_status": "selection_multiplicity_protocol_defined_no_final_selection",
                "can_support_final_method_selection": False,
            }
        },
    )
    write_json(
        root / readiness.SELECTION_MULTIPLICITY_EVIDENCE_RECORD,
        {
            "summary": {
                "overall_status": (
                    "selection_multiplicity_evidence_record_"
                    "ready_no_final_selection"
                ),
                "claim_status": (
                    "diagnostic_primary_candidate_recorded_no_final_selection"
                ),
            }
        },
    )
    write_json(
        root / readiness.BOUNDED_SUPPORT_PROTOCOL,
        {
            "summary": {
                "overall_status": "bounded_support_protocol_defined_no_validity_claim",
                "can_support_bounded_support_validity": False,
            }
        },
    )
    write_json(
        root / readiness.TARGET_DOMAIN_PROVENANCE,
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
        root / readiness.BOUNDED_SUPPORT_POSTHANDLING_VALIDATION,
        {
            "summary": {
                "overall_status": "bounded_support_posthandling_validation_completed",
                "validated_bundle_count": 9,
                "unvalidated_bundle_count": 0,
            }
        },
    )
    write_json(
        root / readiness.BOUNDED_SUPPORT_DATASET_AUDIT,
        {
            "summary": {
                "overall_status": "dataset_bounded_support_audit_completed_no_validity_claim",
                "bounded_support_ready_bundle_count": 0,
                "endpoint_support_clean_bundle_count": 2,
                "endpoint_support_not_applicable_bundle_count": 1,
                "endpoint_support_blocked_or_incomplete_bundle_count": 8,
                "endpoint_support_status_counts": {
                    "clean_no_natural_domain_endpoint_excursions": 2,
                    "not_applicable_unbounded_target_endpoint_hygiene_recorded": 1,
                    "blocked_natural_domain_endpoint_excursions": 8,
                },
                "natural_domain_excursion_bundle_count": 8,
            }
        },
    )
    write_json(
        root / readiness.BOUNDED_SUPPORT_ENDPOINT_CLOSURE,
        {
            "summary": {
                "overall_status": (
                    "endpoint_policy_triage_open_count_backfill_required_"
                    "no_validity_claim"
                ),
                "closed_policy_bundle_count": 10,
                "open_endpoint_count_backfill_bundle_count": 1,
                "global_no_claim_bundle_count": 11,
                "bounded_support_validity_claim_ready_bundle_count": 0,
                "dataset_open_endpoint_count_backfill_count": 1,
            }
        },
    )
    write_json(
        root / readiness.BOUNDED_SUPPORT_POSITIVE_VALIDATION,
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
                "current_manuscript_bounded_support_validity_claim_ready": False,
            }
        },
    )
    write_json(
        root / readiness.MANIFEST_COMPLETENESS_AUDIT,
        {
            "summary": {
                "selection_multiplicity_manifest_pass_count": 2,
                "selection_multiplicity_manifest_fail_count": 0,
                "selection_multiplicity_all_fields_covered": True,
            }
        },
    )
    write_json(
        root / readiness.DATASET_SPECIFIC_FINAL_GATE_AUDIT,
        {
            "summary": {
                "overall_status": (
                    "dataset_specific_final_gate_audit_completed_no_final_"
                    "dataset_promotions"
                ),
                "main_result_ready_dataset_count": 0,
                "main_result_ready_bundle_count": 0,
            }
        },
    )
    write_json(
        root / readiness.MAIN_RESULT_CANDIDATE_BUNDLE_PLAN,
        {
            "summary": {
                "overall_status": "main_result_candidate_bundle_plan_ready_no_promotions",
                "candidate_dataset_count": 5,
                "generated_config_count": 5,
                "expected_atomic_run_count": 225,
                "candidate_primary_consistent_dataset_count": 4,
                "ambiguous_challenger_control_dataset_count": 1,
            }
        },
    )
    write_json(
        root / readiness.MAIN_RESULT_CANDIDATE_BUNDLE_RESULTS,
        {
            "summary": {
                "overall_status": (
                    "main_result_candidate_bundle_results_completed_no_promotions"
                ),
                "completed_atomic_run_count": 225,
                "expected_atomic_run_count": 225,
                "pathology_flagged_row_count": 50,
                "diagnostic_winner_counts": {"cqr": 12, "cv_plus": 2, "mondrian_abs": 1},
            }
        },
    )
    write_json(
        root / readiness.MAIN_RESULT_CANDIDATE_POST_RUN_CLOSURE,
        {
            "summary": {
                "overall_status": "main_result_candidate_post_run_closure_blocked",
                "total_blocker_count": 25,
                "dataset_blocked_count": 5,
                "blocker_counts_by_artifact": {
                    "feature_leakage_audit": 5,
                    "endpoint_audit": 5,
                    "publication_readiness_manifest": 5,
                    "claim_register_refresh": 5,
                    "bundle_eligibility_refresh": 5,
                },
            }
        },
    )
    write_json(
        root / readiness.METHOD_SELECTION_ALPHA_EXPANSION_PLAN,
        {
            "summary": {
                "overall_status": "method_selection_alpha_expansion_plan_not_needed",
                "additional_common_cells_needed_to_clear_threshold": 0,
                "current_common_alpha_max_cell_share": 0.74,
                "current_common_alpha_imbalance_status": "no_large_alpha_concentration",
            }
        },
    )
    write_json(
        root / readiness.METHOD_SELECTION_ALPHA_EXPANSION_BATCH,
        {
            "summary": {
                "overall_status": "method_selection_alpha_expansion_batch_ready",
                "execution_status": "configs_generated_not_yet_run",
                "generated_config_count": 5,
            }
        },
    )
    write_json(
        root / readiness.METHOD_SELECTION_ALPHA_EXPANSION_EXECUTION,
        {
            "summary": {
                "overall_status": (
                    "method_selection_alpha_expansion_execution_closed_"
                    "no_final_selection"
                ),
                "observed_execution_status": "ledgers_completed",
                "active_execution_status": "ledgers_completed",
                "reconciled_execution_status": "ledgers_completed",
                "completed_atomic_run_count": 159,
                "expected_atomic_run_count": 159,
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
            }
        },
    )
    write_json(
        root / readiness.METHOD_SELECTION_INFERENTIAL_AUDIT,
        {
            "summary": {
                "overall_status": (
                    "method_selection_inferential_audit_ready_no_final_selection"
                ),
                "primary_candidate_method": "cqr",
                "bootstrap_primary_selection_rate": 1.0,
                "post_selection_validation_primary_win_rate": 0.72,
                "main_result_candidate_primary_win_rate": 2 / 3,
                "claim_status": (
                    "inferential_method_selection_evidence_ready_no_final_selection"
                ),
            }
        },
    )
    write_json(
        root / readiness.METHOD_SELECTION_POST_SELECTION_VALIDATION_RESULTS,
        {
            "summary": {
                "overall_status": (
                    "method_selection_post_selection_validation_results_"
                    "ready_no_final_selection"
                ),
                "completed_atomic_run_count": 225,
                "expected_atomic_run_count": 225,
                "common_dataset_alpha_cell_count": 25,
                "expected_common_dataset_alpha_cell_count": 25,
                "diagnostic_winner_counts": {"cqr": 18, "mondrian_abs": 7},
            }
        },
    )
    write_json(
        root / readiness.FINAL_SELECTION,
        {"summary": {"claim_status": "blocked"}},
    )
    write_json(
        root / readiness.FAIRNESS_POPULATION_READINESS,
        {
            "summary": {
                "overall_status": "fairness_population_readiness_audit_completed_no_fairness_claim",
                "fairness_population_claim_status": "blocked_diagnostic_only",
                "diagnostic_group_bundle_count": 2,
                "population_fairness_ready_bundle_count": 0,
            }
        },
    )
    write_json(
        root / readiness.FAIRNESS_GROUP_MULTIPLICITY_SCOPE,
        {
            "summary": {
                "overall_status": (
                    "fairness_group_multiplicity_scope_declared_no_fairness_claim"
                ),
                "action_status": "multiplicity_control_complete",
                "multiplicity_scope_declared_bundle_count": 2,
                "comparison_family_count": 2,
                "claim_register_cites_multiplicity_record": True,
                "current_manuscript_fairness_population_claim_ready": False,
            }
        },
    )
    write_json(
        root / readiness.VENN_ABERS_VALIDATION,
        {
            "summary": {
                "overall_status": "venn_abers_validation_blocked_with_negative_evidence"
            }
        },
    )
    write_json(
        root / readiness.VENN_ABERS_CLAIM_GATE_MATRIX,
        {
            "summary": {
                "overall_status": "venn_abers_claim_gate_matrix_blocked_with_complete_evidence",
                "positive_claim_requirement_count": 4,
                "positive_claim_pass_count": 1,
                "positive_claim_blocked_count": 3,
                "blocked_positive_requirement_ids": [
                    "score_grid_panel_coverage_nominal",
                    "score_grid_upper_boundary_free",
                    "ivapd_interval_cp_validated",
                ],
            }
        },
    )
    write_json(
        root / readiness.VENN_ABERS_NEGATIVE_DISPOSITION,
        {
            "summary": {
                "overall_status": "venn_abers_negative_evidence_disposition_pass",
                "negative_result_reporting_ready": True,
                "current_manuscript_positive_validation_required": False,
            }
        },
    )
    write_json(
        root / readiness.EVIDENCE_VIEW,
        {
            "summary": {"claim_count": 12},
            "rows": [
                {
                    "claim_id": "robustness_a",
                    "paper_table_candidates": ["robustness_results_table"],
                },
                {
                    "claim_id": "robustness_b",
                    "paper_table_candidates": ["robustness_results_table_with_caveats"],
                },
            ],
        },
    )
    write_json(
        root / readiness.BUNDLE_INDEX,
        {
            "bundle_summary": {"manifest_count": 2},
            "bundles": [{"bundle_id": "a"}, {"bundle_id": "b"}],
        },
    )
    write_json(
        root / readiness.KG_QUALITY,
        {
            "graph": {"node_count": 10, "edge_count": 25},
            "observations": {
                "total_observation_count": 20,
                "observation_node_ratio": 2.0,
            },
        },
    )
    write_json(
        root / readiness.KG_CATALOG,
        {
            "node_count": 12,
            "edge_count": 30,
            "nodes": [],
            "edges": [],
        },
    )
    write_json(
        root / readiness.POST_EXPERIMENT_PUBLICATION_PROGRAM,
        {
            "status": "deferred_until_experimental_gates_complete",
            "activation_rule": {
                "requires_experiment_closure_verification": True,
                "requires_zero_blocked_paper_gates": True,
                "requires_visual_table_auditor_pass": True,
                "requires_author_metadata_for_individual_experiment_report": True,
                "requires_sterile_publication_repository_plan": True,
            },
            "publication_author": {
                "author_name": "Emre Tasar",
                "author_role": "Data Scientist",
                "author_email": "detasar@gmail.com",
            },
            "experiment_completion_definition": {
                "closure_checks": [
                    "ledgers",
                    "dataset_audits",
                    "method_search",
                    "coverage_width_pathology",
                    "candidate_closure",
                    "paper_gates",
                    "kg_quality",
                    "visual_inventory",
                    "metadata_refresh",
                    "author_metadata",
                    "sterile_publication_repository",
                    "repo_commit",
                ]
            },
            "sterile_publication_repository_plan": {
                "status": "planned_after_full_experiment_closure",
                "citation_target": "sterile_publication_repository",
                "working_repository_citation_status": "not_final_citable_repository",
                "required_contents": [
                    "README",
                    "article",
                    "supplement",
                    "individual_experiment_report",
                ],
                "exclusion_rules": ["scratch", "unsupported_claims"],
            },
            "reviewer_perspectives": [
                {"reviewer_id": "statistical_methodology_reviewer"},
                {"reviewer_id": "conformal_prediction_reviewer"},
                {"reviewer_id": "data_science_reproducibility_reviewer"},
                {"reviewer_id": "fairness_domain_reviewer"},
                {"reviewer_id": "visual_editorial_reviewer"},
            ],
            "reviewer_design_gate": {
                "required_reviewer_pass_count": 5,
                "minimum_structured_recommendations_per_reviewer": 5,
                "advice_record_schema": [
                    "reviewer_id",
                    "recommendation_id",
                    "recommendation_text",
                    "target_surface",
                    "evidence_needed",
                    "accept_reject_defer_decision",
                    "rationale",
                    "mapped_artifact",
                ],
                "required_advice_topics": [
                    "main_article_question_and_claim_design",
                    "supplementary_document_scope_and_table_inventory",
                    "knowledge_graph_citability_and_navigation_design",
                    "static_publication_site_design_and_release_boundary",
                    "figure_and_table_selection_rules",
                    "latex_and_html_rendering_plan",
                    "reviewer_conflict_reconciliation_rules",
                ],
                "procedure": ["collect", "reconcile", "map", "block_drafting"],
            },
            "deliverables": [
                {"deliverable_id": "main_article_latex"},
                {"deliverable_id": "main_article_html"},
                {"deliverable_id": "supplementary_document"},
                {"deliverable_id": "supplementary_document_latex"},
                {"deliverable_id": "supplementary_document_html"},
                {"deliverable_id": "navigable_knowledge_graph"},
                {"deliverable_id": "github_pages_publication_site"},
                {"deliverable_id": "individual_experiment_report"},
                {"deliverable_id": "sterile_publication_repository"},
            ],
            "main_article_blueprint": {
                "sections": [
                    "abstract",
                    "introduction",
                    "background",
                    "data_sources",
                    "methods",
                    "main_results",
                    "robustness",
                    "limitations",
                    "reproducibility",
                ]
            },
            "supplementary_document_blueprint": {
                "sections": [
                    "extended_dataset_audits",
                    "preprocessing_logs",
                    "split_leakage_endpoint_audits",
                    "search_space",
                    "method_taxonomy",
                    "full_results",
                    "failure_modes",
                    "kg_schema",
                    "reproducibility_commands",
                ]
            },
            "publication_site_blueprint": {
                "components": [
                    "article",
                    "supplement",
                    "latex_sources",
                    "tables_figures",
                    "knowledge_graph",
                    "reproducibility_index",
                    "sterile_repository_readme",
                    "individual_experiment_report",
                ]
            },
            "visual_table_audit_agent": {
                "quality_checks": ["overlap", "readability", "utility"],
                "scope": [
                    "main_figures",
                    "supplement_figures",
                    "main_tables",
                    "supplement_tables",
                    "kg_site_visuals",
                ],
                "feedback_loop": [
                    "inventory",
                    "audit",
                    "return_fixes",
                    "regenerate",
                    "repeat",
                ],
                "required_output_artifacts": [
                    "visual_table_inventory.json",
                    "visual_table_audit_report.json",
                    "figure_quality_decision_log.md",
                    "table_quality_decision_log.md",
                ],
            },
            "publication_triptych": {
                "components": [
                    "main_paper",
                    "supplementary_document",
                    "knowledge_graph_or_publication_site",
                ]
            },
        },
    )
    (root / readiness.PROTOCOL).parent.mkdir(parents=True, exist_ok=True)
    (root / readiness.PROTOCOL).write_text("protocol placeholder", encoding="utf-8")
    return report_dir


def test_manuscript_readiness_map_keeps_final_claims_blocked(tmp_path):
    write_minimal_readiness_sources(tmp_path)

    payload = readiness.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "paper_readiness_blocked_with_evidence_map"
    )
    assert payload["summary"]["blocked_gate_count"] == 6
    assert payload["summary"]["venn_abers_negative_result_reporting_ready"] is True
    assert (
        payload["summary"][
            "current_manuscript_positive_venn_abers_validation_required"
        ]
        is False
    )
    assert payload["summary"]["manifested_bundle_count"] == 2
    assert (
        payload["summary"]["selection_multiplicity_protocol_status"]
        == "selection_multiplicity_protocol_defined_no_final_selection"
    )
    assert (
        payload["summary"]["selection_protocol_can_support_final_method_selection"]
        is False
    )
    assert (
        payload["summary"]["selection_multiplicity_evidence_record_status"]
        == "selection_multiplicity_evidence_record_ready_no_final_selection"
    )
    assert payload["summary"]["manifest_selection_multiplicity_pass_count"] == 2
    assert payload["summary"]["manifest_selection_multiplicity_fail_count"] == 0
    assert (
        payload["summary"]["manifest_selection_multiplicity_all_fields_covered"]
        is True
    )
    assert (
        payload["summary"]["dataset_specific_final_gate_audit_status"]
        == "dataset_specific_final_gate_audit_completed_no_final_dataset_promotions"
    )
    assert payload["summary"]["dataset_specific_final_gate_ready_dataset_count"] == 0
    assert payload["summary"]["dataset_specific_final_gate_ready_bundle_count"] == 0
    assert (
        payload["summary"]["main_result_candidate_bundle_plan_status"]
        == "main_result_candidate_bundle_plan_ready_no_promotions"
    )
    assert payload["summary"]["main_result_candidate_dataset_count"] == 5
    assert payload["summary"]["main_result_candidate_generated_config_count"] == 5
    assert payload["summary"]["main_result_candidate_expected_atomic_run_count"] == 225
    assert (
        payload["summary"]["main_result_candidate_results_status"]
        == "main_result_candidate_bundle_results_completed_no_promotions"
    )
    assert payload["summary"]["main_result_candidate_completed_atomic_run_count"] == 225
    assert (
        payload["summary"][
            "main_result_candidate_results_expected_atomic_run_count"
        ]
        == 225
    )
    assert (
        payload["summary"][
            "main_result_candidate_results_pathology_flagged_row_count"
        ]
        == 50
    )
    assert payload["summary"]["main_result_candidate_results_diagnostic_winner_counts"][
        "cqr"
    ] == 12
    assert (
        payload["summary"]["main_result_candidate_post_run_closure_status"]
        == "main_result_candidate_post_run_closure_blocked"
    )
    assert (
        payload["summary"][
            "main_result_candidate_post_run_closure_total_blocker_count"
        ]
        == 25
    )
    assert (
        payload["summary"][
            "main_result_candidate_post_run_closure_dataset_blocked_count"
        ]
        == 5
    )
    assert payload["summary"]["main_result_candidate_post_run_closure_blocker_counts"][
        "endpoint_audit"
    ] == 5
    assert payload["summary"]["main_result_candidate_primary_consistent_dataset_count"] == 4
    assert payload["summary"]["main_result_candidate_ambiguous_dataset_count"] == 1
    assert (
        payload["summary"]["method_selection_alpha_expansion_plan_status"]
        == "method_selection_alpha_expansion_plan_not_needed"
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_additional_common_cells_needed"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_current_common_alpha_max_cell_share"
        ]
        == 0.74
    )
    assert (
        payload["summary"]["method_selection_alpha_expansion_batch_status"]
        == "method_selection_alpha_expansion_batch_ready"
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_batch_reported_execution_status"
        ]
        == "configs_generated_not_yet_run"
    )
    assert (
        payload["summary"]["method_selection_alpha_expansion_execution_status"]
        == "method_selection_alpha_expansion_execution_closed_no_final_selection"
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_observed_execution_status"
        ]
        == "ledgers_completed"
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_active_execution_status"
        ]
        == "ledgers_completed"
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_completed_atomic_run_count"
        ]
        == 159
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_expected_atomic_run_count"
        ]
        == 159
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_batch_generation_label_stale_after_execution"
        ]
        is True
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_batch_generation_label_historical_only"
        ]
        is True
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_batch_reported_execution_status_is_historical"
        ]
        is True
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_reconciled_execution_status"
        ]
        == "ledgers_completed"
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_batch_generation_label_reconciliation_status"
        ]
        == "reconciled_historical_config_generation_label_with_completed_ledgers"
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_batch_generation_label_requires_action"
        ]
        is False
    )
    assert (
        payload["summary"][
            "method_selection_alpha_expansion_execution_metadata_consistency_status"
        ]
        == "historical_batch_generation_label_reconciled_no_action_required"
    )
    assert (
        payload["summary"]["method_selection_inferential_audit_status"]
        == "method_selection_inferential_audit_ready_no_final_selection"
    )
    assert (
        payload["summary"]["method_selection_inferential_primary_candidate_method"]
        == "cqr"
    )
    assert (
        payload["summary"][
            "method_selection_inferential_bootstrap_primary_selection_rate"
        ]
        == 1.0
    )
    assert (
        payload["summary"][
            "method_selection_inferential_post_selection_validation_primary_win_rate"
        ]
        == 0.72
    )
    assert (
        payload["summary"][
            "method_selection_inferential_main_result_candidate_primary_win_rate"
        ]
        == 2 / 3
    )
    assert (
        payload["summary"]["method_selection_inferential_claim_status"]
        == "inferential_method_selection_evidence_ready_no_final_selection"
    )
    assert (
        payload["summary"][
            "method_selection_post_selection_validation_results_status"
        ]
        == "method_selection_post_selection_validation_results_ready_no_final_selection"
    )
    assert (
        payload["summary"][
            "method_selection_post_selection_validation_completed_atomic_run_count"
        ]
        == 225
    )
    assert (
        payload["summary"][
            "method_selection_post_selection_validation_common_dataset_alpha_cell_count"
        ]
        == 25
    )
    assert (
        payload["summary"]["bounded_support_protocol_status"]
        == "bounded_support_protocol_defined_no_validity_claim"
    )
    assert payload["summary"]["bounded_support_protocol_can_support_validity"] is False
    assert (
        payload["summary"]["target_domain_provenance_status"]
        == "target_domain_provenance_ready"
    )
    assert payload["summary"]["target_domain_provenance_row_count"] == 5
    assert (
        payload["summary"]["bounded_support_posthandling_validation_status"]
        == "bounded_support_posthandling_validation_completed"
    )
    assert (
        payload["summary"]["bounded_support_posthandling_validated_bundle_count"] == 9
    )
    assert (
        payload["summary"]["bounded_support_dataset_audit_status"]
        == "dataset_bounded_support_audit_completed_no_validity_claim"
    )
    assert payload["summary"]["bounded_support_dataset_ready_bundle_count"] == 0
    assert (
        payload["summary"]["bounded_support_dataset_natural_excursion_bundle_count"]
        == 8
    )
    assert (
        payload["summary"]["bounded_support_dataset_endpoint_clean_bundle_count"]
        == 2
    )
    assert (
        payload["summary"][
            "bounded_support_dataset_endpoint_not_applicable_bundle_count"
        ]
        == 1
    )
    assert (
        payload["summary"][
            "bounded_support_dataset_endpoint_blocked_or_incomplete_bundle_count"
        ]
        == 8
    )
    assert (
        payload["summary"]["bounded_support_endpoint_closure_status"]
        == "endpoint_policy_triage_open_count_backfill_required_no_validity_claim"
    )
    assert (
        payload["summary"][
            "bounded_support_endpoint_closure_closed_policy_bundle_count"
        ]
        == 10
    )
    assert (
        payload["summary"][
            "bounded_support_endpoint_closure_open_count_backfill_bundle_count"
        ]
        == 1
    )
    assert (
        payload["summary"][
            "bounded_support_endpoint_closure_global_no_claim_bundle_count"
        ]
        == 11
    )
    assert (
        payload["summary"][
            "bounded_support_endpoint_closure_claim_ready_bundle_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["bounded_support_endpoint_closure_dataset_open_count"]
        == 1
    )
    assert (
        payload["summary"]["bounded_support_positive_validation_status"]
        == "bounded_support_positive_validation_protocol_completed_no_validity_claim"
    )
    assert (
        payload["summary"]["bounded_support_positive_validation_action_status"]
        == "empirical_validation_complete_no_bounded_support_claim"
    )
    assert (
        payload["summary"][
            "bounded_support_positive_validation_acceptance_failed_count"
        ]
        == 4
    )
    assert (
        payload["summary"][
            "bounded_support_positive_validation_interval_score_missing_bundle_count"
        ]
        == 2
    )
    assert (
        payload["summary"][
            "bounded_support_positive_validation_claim_ready_bundle_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "bounded_support_positive_validation_can_support_validity"
        ]
        is False
    )
    assert (
        payload["summary"]["fairness_population_readiness_status"]
        == "fairness_population_readiness_audit_completed_no_fairness_claim"
    )
    assert payload["summary"]["fairness_population_ready_bundle_count"] == 0
    assert (
        payload["summary"]["fairness_group_multiplicity_scope_status"]
        == "fairness_group_multiplicity_scope_declared_no_fairness_claim"
    )
    assert (
        payload["summary"][
            "fairness_group_multiplicity_scope_claim_register_cites_record"
        ]
        is True
    )
    assert (
        payload["summary"]["fairness_group_multiplicity_scope_claim_ready"]
        is False
    )
    assert payload["summary"]["main_surface_blocked_count"] == 1
    assert payload["summary"]["kg_node_count"] == 12
    assert payload["summary"]["kg_edge_count"] == 30
    assert (
        payload["summary"]["post_experiment_publication_program_status"]
        == "deferred_until_experimental_gates_complete"
    )
    assert (
        payload["summary"][
            "post_experiment_publication_activation_requires_zero_blocked_gates"
        ]
        is True
    )
    assert (
        payload["summary"][
            "post_experiment_publication_requires_experiment_closure_verification"
        ]
        is True
    )
    assert (
        payload["summary"][
            "post_experiment_publication_requires_visual_table_auditor_pass"
        ]
        is True
    )
    assert (
        payload["summary"]["post_experiment_publication_requires_author_metadata"]
        is True
    )
    assert (
        payload["summary"][
            "post_experiment_publication_requires_sterile_repository_plan"
        ]
        is True
    )
    assert payload["summary"]["post_experiment_publication_author_name"] == (
        "Emre Tasar"
    )
    assert (
        payload["summary"]["post_experiment_publication_author_role"]
        == "Data Scientist"
    )
    assert (
        payload["summary"]["post_experiment_publication_author_email_present"]
        is True
    )
    assert (
        payload["summary"]["post_experiment_sterile_repository_status"]
        == "planned_after_full_experiment_closure"
    )
    assert payload["summary"]["post_experiment_sterile_repository_required"] is True
    assert (
        payload["summary"]["post_experiment_working_repository_final_citable"]
        is False
    )
    assert (
        payload["summary"][
            "post_experiment_sterile_repository_required_content_count"
        ]
        == 4
    )
    assert (
        payload["summary"][
            "post_experiment_sterile_repository_exclusion_rule_count"
        ]
        == 2
    )
    assert payload["summary"]["post_experiment_completion_closure_check_count"] == 12
    assert (
        payload["summary"]["post_experiment_publication_reviewer_perspective_count"]
        == 5
    )
    assert (
        payload["summary"][
            "post_experiment_publication_reviewer_design_required_pass_count"
        ]
        == 5
    )
    assert (
        payload["summary"][
            "post_experiment_publication_minimum_recommendations_per_reviewer"
        ]
        == 5
    )
    assert (
        payload["summary"]["post_experiment_publication_advice_schema_field_count"]
        == 8
    )
    assert (
        payload["summary"]["post_experiment_publication_required_advice_topic_count"]
        == 7
    )
    assert (
        payload["summary"][
            "post_experiment_publication_reviewer_design_procedure_count"
        ]
        == 4
    )
    assert payload["summary"]["post_experiment_publication_deliverable_count"] == 9
    assert payload["summary"]["post_experiment_main_article_section_count"] == 9
    assert payload["summary"]["post_experiment_supplementary_section_count"] == 9
    assert payload["summary"]["post_experiment_publication_site_component_count"] == 8
    assert payload["summary"]["post_experiment_visual_table_quality_check_count"] == 3
    assert payload["summary"]["post_experiment_visual_table_scope_count"] == 5
    assert (
        payload["summary"]["post_experiment_visual_table_feedback_loop_step_count"]
        == 5
    )
    assert (
        payload["summary"]["post_experiment_visual_table_required_artifact_count"]
        == 4
    )
    assert (
        payload["summary"]["post_experiment_publication_triptych_component_count"]
        == 3
    )
    assert {row["gate_id"] for row in payload["blocked_gates"]} == {
        "dataset_specific_final_gates",
        "endpoint_bounded_support_gate",
        "fairness_population_inference_gate",
        "final_method_model_selection_gate",
        "multiplicity_selection_record",
        "venn_abers_regression_validation_gate",
    }
    venn_gate = next(
        row
        for row in payload["blocked_gates"]
        if row["gate_id"] == "venn_abers_regression_validation_gate"
    )
    assert (
        str(readiness.VENN_ABERS_GRID_FAILURE_MODE_DECOMPOSITION)
        in venn_gate["source_artifacts"]
    )
    assert str(readiness.VENN_ABERS_CLAIM_GATE_MATRIX) in venn_gate[
        "source_artifacts"
    ]
    assert (
        payload["summary"]["venn_abers_claim_gate_matrix_status"]
        == "venn_abers_claim_gate_matrix_blocked_with_complete_evidence"
    )
    assert payload["summary"]["venn_abers_claim_gate_positive_requirement_count"] == 4
    assert payload["summary"]["venn_abers_claim_gate_positive_pass_count"] == 1
    assert payload["summary"]["venn_abers_claim_gate_positive_blocked_count"] == 3
    dataset_gate = next(
        row
        for row in payload["blocked_gates"]
        if row["gate_id"] == "dataset_specific_final_gates"
    )
    assert (
        str(readiness.DATASET_SPECIFIC_FINAL_GATE_AUDIT)
        in dataset_gate["source_artifacts"]
    )
    assert (
        str(readiness.MAIN_RESULT_CANDIDATE_BUNDLE_PLAN)
        in dataset_gate["source_artifacts"]
    )
    final_gate = next(
        row
        for row in payload["blocked_gates"]
        if row["gate_id"] == "final_method_model_selection_gate"
    )
    assert (
        str(readiness.MAIN_RESULT_CANDIDATE_BUNDLE_PLAN)
        in final_gate["source_artifacts"]
    )
    assert (
        str(readiness.METHOD_SELECTION_ALPHA_EXPANSION_EXECUTION)
        in final_gate["source_artifacts"]
    )
    assert (
        str(readiness.METHOD_SELECTION_INFERENTIAL_AUDIT)
        in final_gate["source_artifacts"]
    )
    assert (
        str(readiness.METHOD_SELECTION_POST_SELECTION_VALIDATION_RESULTS)
        in final_gate["source_artifacts"]
    )
    multiplicity_gate = next(
        row
        for row in payload["blocked_gates"]
        if row["gate_id"] == "multiplicity_selection_record"
    )
    assert (
        str(readiness.SELECTION_MULTIPLICITY_EVIDENCE_RECORD)
        in multiplicity_gate["source_artifacts"]
    )
    assert (
        str(readiness.MANIFEST_COMPLETENESS_AUDIT)
        in multiplicity_gate["source_artifacts"]
    )
    assert (
        str(readiness.METHOD_SELECTION_ALPHA_EXPANSION_PLAN)
        in multiplicity_gate["source_artifacts"]
    )
    assert (
        str(readiness.METHOD_SELECTION_ALPHA_EXPANSION_EXECUTION)
        in multiplicity_gate["source_artifacts"]
    )
    assert (
        str(readiness.METHOD_SELECTION_INFERENTIAL_AUDIT)
        in multiplicity_gate["source_artifacts"]
    )
    fairness_gate = next(
        row
        for row in payload["blocked_gates"]
        if row["gate_id"] == "fairness_population_inference_gate"
    )
    assert (
        str(readiness.FAIRNESS_POPULATION_READINESS)
        in fairness_gate["source_artifacts"]
    )
    assert (
        str(readiness.FAIRNESS_GROUP_DIAGNOSTIC_AUDIT)
        in fairness_gate["source_artifacts"]
    )
    main_surface = next(
        row
        for row in payload["paper_surfaces"]
        if row["surface_id"] == "main_results_table"
    )
    assert main_surface["status"] == "blocked"
    robustness_surface = next(
        row
        for row in payload["paper_surfaces"]
        if row["surface_id"] == "robustness_results_table"
    )
    assert "2 claim rows" in robustness_surface["evidence"]


def test_manuscript_readiness_markdown_lists_closure_actions(tmp_path):
    write_minimal_readiness_sources(tmp_path)
    payload = readiness.build_payload(tmp_path)

    markdown = readiness.render_markdown(payload)

    assert "# Paper Readiness Map" in markdown
    assert "`final_method_model_selection_gate`" in markdown
    assert "Manifest selection/multiplicity coverage" in markdown
    assert "Dataset-specific final gate audit status" in markdown
    assert "Main-result candidate bundle plan" in markdown
    assert "Main-result candidate bundle results" in markdown
    assert "Main-result candidate post-run closure" in markdown
    assert "Method-selection alpha expansion plan" in markdown
    assert "Method-selection alpha expansion execution" in markdown
    assert "Method-selection post-selection validation" in markdown
    assert "Post-experiment publication program" in markdown
    assert "Post-experiment blueprints" in markdown
    assert "Post-experiment visual/table audit" in markdown
    assert "Apply the selection/multiplicity protocol" in markdown
    assert "alpha-expansion execution audit" in markdown
    assert "Apply the bounded-support protocol" in markdown
    assert "target-domain provenance" in markdown
    assert "post-handling validation" in markdown
    assert "Use the bounded-support dataset audit" in markdown


def test_manuscript_readiness_accepts_list_shaped_kg_issues(tmp_path):
    write_minimal_readiness_sources(tmp_path)
    kg_path = tmp_path / readiness.KG_QUALITY
    kg_quality = json.loads(kg_path.read_text(encoding="utf-8"))
    kg_quality["issues"] = [{"severity": "high", "code": "example"}]
    kg_path.write_text(json.dumps(kg_quality), encoding="utf-8")

    payload = readiness.build_payload(tmp_path)

    reproducibility = next(
        row
        for row in payload["paper_surfaces"]
        if row["surface_id"] == "reproducibility_appendix"
    )
    assert "KG status is review" in reproducibility["evidence"]
