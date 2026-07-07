from pathlib import Path

from experiments.regression.scripts import build_reviewer_design_brief as brief


def test_checked_in_reviewer_design_brief_is_neutral_pre_prose():
    payload = brief.build_payload(Path("."))
    summary = payload["summary"]

    assert summary["overall_status"] == "reviewer_design_brief_ready_no_final_prose"
    assert (
        summary["phase_state"]
        == "neutral_pre_prose_design_active_final_prose_and_release_blocked"
    )
    assert summary["reviewer_count"] == 5
    assert summary["required_reviewer_count"] == 5
    assert summary["advice_record_count"] == 25
    assert summary["accepted_advice_count"] == 18
    assert summary["deferred_advice_count"] == 7
    assert summary["content_matrix_row_count"] == 10
    assert summary["expected_visual_table_family_count"] == 10
    assert summary["neutral_no_method_promotion_guard_active"] is True
    assert summary["private_manuscript_drafting_authorized"] is True
    assert summary["private_research_document_authoring_authorized"] is True
    assert summary["manuscript_drafting_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["final_retain_decision_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["failed_check_count"] == 0


def test_reviewer_design_brief_records_design_only_schema_and_sources():
    payload = brief.build_payload(Path("."))

    assert all(
        row["decision_scope"]
        == "publication_design_only_no_final_prose_no_retained_visuals"
        for row in payload["reviewer_advice_records"]
    )
    assert all(
        row["claim_boundary_tag"] == "neutral_pre_prose_design_only"
        for row in payload["reviewer_advice_records"]
    )
    assert all(
        row["final_placement_decision"] == "not_started"
        for row in payload["article_supplement_content_matrix"]
    )
    assert all(
        row["retained_visual_or_table_decision"] == "not_started"
        for row in payload["article_supplement_content_matrix"]
    )
    assert all(
        row["source_artifact_count"] > 0
        for row in payload["article_supplement_content_matrix"]
    )
    assert (
        payload["publication_site_decision_record"]["site_decision_status"]
        == "deferred_until_release_gates_pass"
    )
    assert (
        payload["publication_site_decision_record"]["site_deployment_authorized"]
        is False
    )
    assert (
        payload["sources"]["publication_authoring_decision"]
        == "experiments/regression/manuscript/publication_authoring_decision_record.json"
    )


def test_reviewer_design_brief_claim_boundaries_forbid_method_promotion():
    payload = brief.build_payload(Path("."))
    boundaries = " ".join(payload["claim_boundaries"])

    assert "final prose and release remain blocked" in boundaries
    assert "not manuscript prose" in boundaries
    assert "No row promotes CQR, CV+, Venn-Abers" in boundaries
    assert "candidate design surfaces" in boundaries


def test_reviewer_design_brief_separates_private_authoring_from_public_prose():
    payload = brief.build_payload(Path("."))
    summary = payload["summary"]
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert summary["private_manuscript_drafting_authorized"] is True
    assert summary["private_research_document_authoring_authorized"] is True
    assert summary["manuscript_drafting_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert (
        checks["private_research_document_authoring_context_recorded"]["status"]
        == "pass"
    )
    evidence = checks["private_research_document_authoring_context_recorded"][
        "evidence"
    ]
    assert evidence["final_public_release_authorized"] is False
    assert evidence["new_experiments_authorized"] is False
