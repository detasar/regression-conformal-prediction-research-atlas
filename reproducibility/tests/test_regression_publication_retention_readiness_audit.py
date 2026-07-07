import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_payload():
    return json.loads(
        (
            ROOT
            / "experiments/regression/manuscript/"
            / "publication_retention_readiness_audit.json"
        ).read_text()
    )


def test_checked_in_publication_retention_readiness_is_no_final_prose():
    payload = load_payload()
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "publication_retention_readiness_ready_no_final_prose"
    )
    assert (
        summary["phase_state"]
        == "pre_manuscript_retention_recommendations_ready_final_prose_and_release_blocked"
    )
    assert summary["recommendation_row_count"] == 10
    assert summary["render_candidate_count"] == 10
    assert summary["main_article_candidate_count"] == 4
    assert summary["supplement_candidate_count"] == 5
    assert summary["kg_or_site_candidate_count"] == 1
    assert summary["retention_recommendation_complete"] is True
    assert summary["reviewer_design_reconciled"] is True
    assert summary["neutral_result_ledger_clean"] is True
    assert summary["neutral_language_unguarded_hit_count"] == 0
    assert summary["final_retained_artifact_count"] == 0
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["failed_check_count"] == 0


def test_retention_recommendation_rows_are_traceable_and_not_final():
    payload = load_payload()
    rows = payload["recommendation_rows"]
    assert len(rows) == 10
    assert {
        row["recommended_surface"] for row in rows
    } == {
        "main_article_candidate_after_final_prose_gate",
        "supplement_candidate_after_final_prose_gate",
        "kg_or_site_candidate_release_blocked",
    }
    for row in rows:
        assert row["recommendation_status"] == "recommendation_ready_no_final_retention"
        assert row["retention_readiness_decision"] == (
            "candidate_ready_for_final_prose_stage_review"
        )
        assert row["layout_quality_status"] == "pass"
        assert row["caption_quality_status"] == "pass"
        assert row["source_traceability_status"] == "pass"
        assert row["source_traceability_artifact_status"] == "pass"
        assert row["final_retention_authorized"] is False
        assert row["final_visual_table_retention_authorized"] is False
        assert row["final_manuscript_prose_permission"] is False
        assert row["positive_claim_promotion_authorized"] is False
        assert row["source_artifacts"]
        for source in row["source_artifacts"]:
            assert (ROOT / source).exists(), source


def test_retention_recommendation_matrix_matches_audit_summary():
    audit = load_payload()
    matrix = json.loads(
        (
            ROOT
            / "experiments/regression/manuscript/"
            / "article_supplement_retention_recommendation_matrix.json"
        ).read_text()
    )

    assert matrix["summary"]["overall_status"] == audit["summary"]["overall_status"]
    assert matrix["summary"]["recommendation_row_count"] == 10
    assert matrix["summary"]["final_visual_table_retention_authorized"] is False
    assert matrix["summary"]["final_manuscript_prose_permission"] is False
    assert matrix["summary"]["positive_claim_promotion_authorized"] is False
    assert len(matrix["rows"]) == len(audit["recommendation_rows"])
