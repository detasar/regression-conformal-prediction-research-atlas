from pathlib import Path

from experiments.regression.scripts import build_publication_visual_audit_plan as plan


def test_checked_in_visual_audit_plan_is_pre_prose_and_design_only():
    payload = plan.build_payload(Path("."))
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "publication_visual_audit_plan_ready_no_retained_artifacts"
    )
    assert (
        summary["phase_state"]
        == "neutral_pre_prose_visual_audit_planning_active_final_visuals_and_release_blocked"
    )
    assert summary["candidate_artifact_count"] == 10
    assert summary["expected_candidate_artifact_count"] == 10
    assert summary["claim_linked_decision_row_count"] == 10
    assert summary["visual_table_quality_check_count"] == 10
    assert summary["visual_table_scope_count"] == 5
    assert summary["visual_table_feedback_loop_step_count"] == 5
    assert summary["visual_table_required_output_artifact_count"] == 6
    assert summary["triptych_component_count"] == 3
    assert (
        summary["triptych_decision_status"]
        == "candidate_triptych_deferred_until_kg_usability_release_gates"
    )
    assert summary["visual_table_audit_plan_authorized"] is True
    assert summary["visual_table_audit_execution_authorized"] is False
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["final_triptych_release_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["neutral_no_method_promotion_guard_active"] is True
    assert summary["check_count"] == 10
    assert summary["failed_check_count"] == 0


def test_visual_audit_plan_rows_are_not_retained_or_started():
    payload = plan.build_payload(Path("."))

    assert all(
        row["audit_status"] == "planned_not_started"
        for row in payload["candidate_audit_rows"]
    )
    assert all(
        row["auditor_decision"] == "not_started"
        for row in payload["candidate_audit_rows"]
    )
    assert all(
        row["final_retention_authorized"] is False
        for row in payload["candidate_audit_rows"]
    )
    assert all(
        row["retained_visual_or_table_decision"] == "not_started"
        for row in payload["candidate_audit_rows"]
    )
    assert all(
        row["source_artifact_count"] > 0 for row in payload["candidate_audit_rows"]
    )
    assert all(
        len(row["required_quality_checks"]) == 10
        for row in payload["candidate_audit_rows"]
    )


def test_visual_audit_plan_claim_linked_decisions_are_traceable_and_bounded():
    payload = plan.build_payload(Path("."))
    rows = payload["claim_linked_decision_rows"]

    assert len(rows) == 10
    assert {row["content_area_id"] for row in rows} == {
        "experiment_scope_and_accounting_table",
        "method_performance_descriptive_summary",
        "method_selection_robustness_diagnostics",
        "post_selection_validation_diagnostics",
        "venn_abers_failure_mode_evidence",
        "bounded_support_endpoint_policy_table",
        "fairness_group_diagnostic_tables",
        "duplicate_split_caveat_inventory",
        "knowledge_graph_navigation_quality",
        "neutral_closure_and_claim_boundary_table",
    }
    assert {row["claim_role"] for row in rows} >= {
        "descriptive_method_behavior_claim",
        "negative_failure_mode_claim",
        "blocked_bounded_support_validity_claim",
        "diagnostic_group_evidence_no_population_fairness",
        "traceability_and_navigation_claim",
    }
    assert all(row["source_artifact_count"] > 0 for row in rows)
    assert all(row["quality_check_count"] == 10 for row in rows)
    assert all(row["reader_question"] for row in rows)
    assert all(row["reader_utility"] for row in rows)
    assert all(row["overclaim_blocked"] for row in rows)
    assert all(
        row["allowed_current_action"]
        == "plan_candidate_visual_or_table_for_private_review_only"
        for row in rows
    )
    assert all(
        row["blocked_current_action"]
        == "render_retain_publish_or_use_as_final_claim_evidence"
        for row in rows
    )
    assert all(row["final_retention_authorized"] is False for row in rows)
    assert all(row["public_release_authorized"] is False for row in rows)
    assert all(row["method_recommendation_authorized"] is False for row in rows)
    assert all(row["positive_claim_promotion_authorized"] is False for row in rows)
    venn_row = next(
        row for row in rows if row["content_area_id"] == "venn_abers_failure_mode_evidence"
    )
    assert venn_row["claim_role"] == "negative_failure_mode_claim"
    assert "without rejecting the literature" in venn_row["reader_utility"]


def test_triptych_decision_keeps_kg_and_site_release_blocked():
    payload = plan.build_payload(Path("."))
    triptych = payload["article_supplement_kg_triptych_decision"]

    assert triptych["summary"]["component_count"] == 3
    assert triptych["summary"]["kg_citable_component_authorized"] is False
    assert triptych["summary"]["final_triptych_release_authorized"] is False
    assert triptych["summary"]["positive_claim_promotion_authorized"] is False
    assert {row["component_id"] for row in triptych["components"]} == {
        "main_paper",
        "supplementary_document",
        "knowledge_graph_or_publication_site",
    }
    assert all(row["final_release_authorized"] is False for row in triptych["components"])
    assert all(
        row["citable_component_authorized"] is False
        for row in triptych["components"]
    )
