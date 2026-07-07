import json
from pathlib import Path

from experiments.regression.scripts import (
    build_publication_claim_evidence_verification_matrix as matrix,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT
    / "experiments/regression/manuscript/"
    / "publication_claim_evidence_verification_matrix.json"
)


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def copy_matrix_sources(tmp_path):
    for path in matrix.SOURCE_PATHS.values():
        src = ROOT / path
        dst = tmp_path / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        md_src = src.with_suffix(".md")
        if md_src.exists():
            md_dst = dst.with_suffix(".md")
            md_dst.write_text(md_src.read_text(encoding="utf-8"), encoding="utf-8")


def test_publication_claim_evidence_matrix_summary_is_claim_safe():
    payload = load_artifact()
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "publication_claim_evidence_verification_ready_no_final_prose"
    )
    assert (
        summary["phase_state"]
        == "neutral_pre_prose_claim_evidence_verification_active_final_outputs_blocked"
    )
    assert summary["verification_row_count"] == 8
    assert summary["verification_pass_count"] == 8
    assert summary["source_traceable_row_count"] == 8
    assert summary["boundary_aligned_row_count"] == 8
    assert summary["navigation_aligned_row_count"] == 8
    assert summary["kg_reference_issue_count"] == 0
    assert summary["safe_pre_prose_evidence_row_count"] == 7
    assert summary["blocked_positive_row_count"] == 1
    assert summary["main_results_blocked_row_count"] == 1
    assert summary["venn_abers_negative_ready_row_count"] == 1
    assert summary["claim_review_row_count"] == 8
    assert summary["claim_review_supported_count"] == 8
    assert summary["claim_review_citation_gate_count"] == 8
    assert summary["claim_review_overclaim_blocked_count"] == 8
    assert summary["claim_review_non_specialist_explanation_count"] == 8
    assert summary["claim_review_status_counts"] == {"pass": 8}
    assert summary["current_publication_draft_artifact_count"] == 6
    assert summary["current_publication_draft_artifact_pass_count"] == 6
    assert summary["current_publication_draft_artifact_traceable_count"] == 6
    assert summary["current_publication_draft_missing_source_key_count"] == 0
    assert summary["current_publication_draft_missing_artifact_count"] == 0
    assert summary["current_publication_draft_authorization_violation_count"] == 0
    assert summary["current_publication_draft_failed_upstream_check_count"] == 0
    assert summary["private_review_surface_count"] == 6
    assert summary["private_review_surface_pass_count"] == 6
    assert summary["private_review_surface_missing_count"] == 0
    assert summary["private_review_surface_phrase_issue_count"] == 0
    assert summary["private_review_surface_authorization_violation_count"] == 0
    assert summary["source_authorization_violation_count"] == 0
    assert summary["row_authorization_violation_count"] == 0
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["latex_html_authoring_authorized"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["analysis_only_no_champion_method"] is True
    assert (
        summary["result_reporting_policy"]
        == "analysis_only_report_observed_behavior_no_method_advocacy"
    )
    assert summary["neutral_language_unguarded_hit_count"] == 0
    assert summary["kg_isolated_node_count"] == 0
    assert summary["failed_check_count"] == 0


def test_publication_claim_evidence_matrix_has_claim_reviewer_rows():
    payload = load_artifact()
    rows = {row["claim_review_id"]: row for row in payload["claim_review_rows"]}

    assert set(rows) == {row["verification_id"] for row in payload["verification_rows"]}
    for row in rows.values():
        assert row["claim_review_status"] == "pass"
        assert row["support_status"] == (
            "supported_with_internal_artifacts_boundaries_and_kg_trace"
        )
        assert row["citation_status"] == "citation_or_source_gate_recorded"
        assert row["source_artifact_count"] > 0
        assert row["kg_reference_node_count"] > 0
        assert row["required_support_type_count"] >= 4
        assert row["allowed_publication_sentence"]
        assert row["overclaim_blocked"]
        assert row["citation_gate"]
        assert row["non_specialist_explanation"]
        assert row["method_recommendation_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False
        assert row["final_manuscript_prose_permission"] is False

    method = rows["paper_method_scope_evidence"]
    assert method["claim_type"] == "descriptive_empirical_claim"
    assert method["allowed_publication_sentence"] == (
        "CQR/CV+ were observed as strong practical candidates in these "
        "experiments."
    )
    assert "final recommendation" in method["overclaim_blocked"]

    venn = rows["supplement_venn_abers_negative_evidence"]
    assert venn["claim_type"] == "negative_failure_mode_claim"
    assert "bridge-specific negative evidence" in venn["citation_gate"]
    assert "broader Venn-Abers literature" in venn["citation_gate"]


def test_publication_claim_evidence_matrix_covers_current_draft_artifacts():
    payload = load_artifact()
    rows = {
        row["artifact_id"]: row
        for row in payload["current_publication_draft_artifact_rows"]
    }

    assert set(rows) == {
        "main_article_draft",
        "supplementary_document_draft",
        "individual_experiment_report_draft",
        "publication_citation_registry",
        "sterile_repository_readme_draft",
        "research_document",
    }
    for row in rows.values():
        assert row["verification_status"] == "pass"
        assert row["source_traceability_status"] == "pass"
        assert row["artifact_exists"] is True
        assert row["markdown_exists"] is True
        assert row["missing_required_source_keys"] == []
        assert row["failed_check_count"] == 0
        assert row["authorization_violations"] == []
        assert row["method_champion_authorized"] is False
        assert row["method_advocacy_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False

    main = rows["main_article_draft"]
    assert (
        "publication_claim_evidence_verification_matrix"
        in main["required_source_keys"]
    )
    sterile_readme = rows["sterile_repository_readme_draft"]
    assert "sterile_repository_staging_manifest" in sterile_readme["required_source_keys"]
    assert (
        "private_sterile_publication_package_manifest"
        in sterile_readme["required_source_keys"]
    )
    assert "private_latex_html_review_output_audit" in sterile_readme["required_source_keys"]
    research_document = rows["research_document"]
    assert research_document["target_document"] == "research_document"
    assert research_document["overall_status"] == (
        "research_document_private_authoring_ready"
    )
    assert "publication_authoring_decision_record" in research_document[
        "required_source_keys"
    ]
    assert "private_sterile_publication_package_manifest" in research_document[
        "required_source_keys"
    ]


def test_publication_claim_evidence_matrix_covers_private_review_surfaces():
    payload = load_artifact()
    rows = {row["surface_id"]: row for row in payload["private_review_surface_rows"]}

    assert set(rows) == {
        "private_review_readme",
        "private_review_boundaries",
        "private_user_review_handoff",
        "private_public_release_review_checklist",
        "private_review_site_index",
        "private_kg_browser",
    }
    assert rows["private_user_review_handoff"]["package_path"] == (
        "USER_REVIEW_HANDOFF.md"
    )
    assert rows["private_public_release_review_checklist"]["package_path"] == (
        "PUBLIC_RELEASE_REVIEW_CHECKLIST.md"
    )
    assert rows["private_review_site_index"]["package_path"] == "site/index.html"
    assert rows["private_kg_browser"]["package_path"] == "site/kg_browser.html"
    for row in rows.values():
        assert row["verification_status"] == "pass"
        assert row["exists"] is True
        assert row["missing_required_phrases"] == []
        assert row["authorization_violations"] == []
        assert row["public_release_authorized"] is False
        assert row["method_recommendation_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False


def test_publication_claim_evidence_matrix_preserves_blocked_and_negative_roles():
    payload = load_artifact()
    rows = {row["verification_id"]: row for row in payload["verification_rows"]}
    main = rows["paper_main_results_blocked_evidence"]
    venn = rows["supplement_venn_abers_negative_evidence"]

    assert main["verification_status"] == "pass"
    assert main["safe_pre_prose_evidence_packet"] is False
    assert main["positive_claim_packet_blocked"] is True
    assert main["main_results_positive_boundary_blocked"] is True
    assert "method/model winner" in main["disallowed_language"]
    assert main["method_champion_authorized"] is False
    assert main["method_advocacy_authorized"] is False
    assert main["positive_claim_promotion_authorized"] is False
    assert main["authorization_violations"] == []

    assert venn["verification_status"] == "pass"
    assert venn["safe_pre_prose_evidence_packet"] is True
    assert venn["positive_claim_packet_blocked"] is False
    assert venn["venn_abers_negative_boundary_preserved"] is True
    assert "validated Venn-Abers regression" in venn["disallowed_language"]
    assert "venn_abers_regression_negative_evidence" in venn["neutral_result_ids"]
    assert venn["method_champion_authorized"] is False
    assert venn["method_advocacy_authorized"] is False
    assert venn["positive_claim_promotion_authorized"] is False
    assert venn["authorization_violations"] == []


def test_publication_claim_evidence_matrix_blocks_missing_kg_reference(tmp_path):
    copy_matrix_sources(tmp_path)
    nav_path = tmp_path / matrix.NAVIGATION_INDEX
    payload = json.loads(nav_path.read_text(encoding="utf-8"))
    payload["navigation_rows"][0]["missing_kg_reference_node_ids"] = [
        "missing:paper_dataset_scope_evidence"
    ]
    nav_path.write_text(json.dumps(payload), encoding="utf-8")

    result = matrix.build_payload(tmp_path)
    summary = result["summary"]

    assert summary["overall_status"] == "publication_claim_evidence_verification_blocked"
    assert summary["verification_pass_count"] == 7
    assert summary["kg_reference_issue_count"] == 1
    assert summary["failed_check_count"] >= 1
    failed_ids = {row["check_id"] for row in result["failed_checks"]}
    assert "boundary_navigation_alignment_clean" in failed_ids


def test_publication_claim_evidence_matrix_blocks_authorization_opening(tmp_path):
    copy_matrix_sources(tmp_path)
    final_path = tmp_path / matrix.FINAL_AUTHORIZATION
    payload = json.loads(final_path.read_text(encoding="utf-8"))
    payload["summary"]["analysis_only_no_champion_method"] = False
    payload["summary"]["method_champion_authorized"] = True
    payload["summary"]["final_manuscript_prose_permission"] = True
    final_path.write_text(json.dumps(payload), encoding="utf-8")

    result = matrix.build_payload(tmp_path)
    summary = result["summary"]

    assert summary["overall_status"] == "publication_claim_evidence_verification_blocked"
    assert summary["source_authorization_violation_count"] >= 1
    assert summary["failed_check_count"] >= 1
    failed_ids = {row["check_id"] for row in result["failed_checks"]}
    assert "analysis_only_no_champion_policy_preserved" in failed_ids
    assert "final_outputs_and_release_remain_blocked" in failed_ids


def test_publication_claim_evidence_matrix_blocks_current_draft_source_gap(tmp_path):
    copy_matrix_sources(tmp_path)
    article_path = tmp_path / matrix.MAIN_ARTICLE_DRAFT
    payload = json.loads(article_path.read_text(encoding="utf-8"))
    payload["sources"].pop("publication_citation_registry")
    article_path.write_text(json.dumps(payload), encoding="utf-8")

    result = matrix.build_payload(tmp_path)
    summary = result["summary"]

    assert summary["overall_status"] == "publication_claim_evidence_verification_blocked"
    assert summary["current_publication_draft_artifact_pass_count"] == 5
    assert summary["current_publication_draft_missing_source_key_count"] == 1
    failed_ids = {row["check_id"] for row in result["failed_checks"]}
    assert "current_publication_draft_artifacts_claim_evidence_covered" in failed_ids


def test_publication_claim_evidence_matrix_blocks_private_review_surface_gap(
    tmp_path,
):
    copy_matrix_sources(tmp_path)
    package_path = tmp_path / matrix.PRIVATE_STERILE_PUBLICATION_PACKAGE
    payload = json.loads(package_path.read_text(encoding="utf-8"))
    payload["generated_review_surface_rows"][2][
        "missing_required_phrases"
    ] = ["Public release requires explicit user approval after review."]
    payload["generated_review_surface_rows"][2]["verification_status"] = "fail"
    package_path.write_text(json.dumps(payload), encoding="utf-8")

    result = matrix.build_payload(tmp_path)
    summary = result["summary"]

    assert summary["overall_status"] == "publication_claim_evidence_verification_blocked"
    assert summary["private_review_surface_pass_count"] == 5
    assert summary["private_review_surface_phrase_issue_count"] == 1
    failed_ids = {row["check_id"] for row in result["failed_checks"]}
    assert "private_review_package_surfaces_claim_evidence_covered" in failed_ids
