import json
from pathlib import Path

from experiments.regression.scripts import (
    build_article_supplement_blueprint_alignment as alignment,
)


ROOT = Path(__file__).resolve().parents[1]


def load_checked_in_payload():
    return json.loads(
        (
            ROOT
            / "experiments/regression/manuscript/"
            / "article_supplement_blueprint_alignment.json"
        ).read_text()
    )


def test_checked_in_blueprint_alignment_is_neutral_no_promotion():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "article_supplement_blueprint_alignment_ready_no_final_prose_no_method_promotion"
    )
    assert summary["phase_state"] == (
        "neutral_pre_prose_blueprint_alignment_active_final_prose_and_release_blocked"
    )
    assert summary["alignment_row_count"] == 10
    assert summary["surface_row_count"] == 3
    assert summary["direct_reviewer_advice_row_count"] == 9
    assert summary["explicit_no_direct_advice_rationale_count"] == 1
    assert summary["reviewer_alignment_issue_count"] == 0
    assert summary["linked_neutral_result_issue_count"] == 0
    assert summary["source_traceable_row_count"] == 10
    assert summary["missing_source_artifact_count"] == 0
    assert summary["neutral_result_ledger_clean"] is True
    assert summary["activation_pre_prose_only"] is True
    assert summary["venn_abers_negative_no_validated_claim"] is True
    assert summary["cqr_cvplus_reporting_role"] == (
        "descriptive_diagnostic_no_final_selection_no_method_promotion"
    )
    assert summary["final_retained_artifact_count"] == 0
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["scientific_no_method_promotion_guard_active"] is True
    assert summary["failed_check_count"] == 0


def test_blueprint_alignment_rows_are_traceable_and_not_final():
    payload = load_checked_in_payload()
    rows = payload["alignment_rows"]

    assert len(rows) == 10
    assert {
        row["recommended_surface"] for row in rows
    } == {
        "main_article_candidate_after_final_prose_gate",
        "supplement_candidate_after_final_prose_gate",
        "kg_or_site_candidate_release_blocked",
    }
    for row in rows:
        assert row["linked_neutral_result_count"] == 1
        assert row["source_traceability_status"] == "pass"
        assert row["missing_source_artifacts"] == []
        assert row["final_retention_authorized"] is False
        assert row["final_visual_table_retention_authorized"] is False
        assert row["final_manuscript_prose_permission"] is False
        assert row["publication_site_deployment_authorized"] is False
        assert row["kg_citable_component_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False
        assert row["sterile_repository_creation_authorized"] is False
        assert row["method_recommendation_authorized"] is False
        assert row["source_artifacts"]
        for source in row["source_artifacts"]:
            assert (ROOT / source).exists(), source


def test_blueprint_alignment_records_venn_abers_as_observed_negative_evidence():
    payload = load_checked_in_payload()
    row = next(
        row
        for row in payload["alignment_rows"]
        if row["content_area_id"] == "venn_abers_failure_mode_evidence"
    )

    assert row["scientific_reporting_role"] == (
        "negative_failure_mode_no_validated_regression_claim"
    )
    assert row["claim_boundary"] == (
        "Negative/failure-mode evidence; no validated Venn-Abers regression claim."
    )
    assert row["neutral_result_ids"] == [
        "venn_abers_regression_negative_evidence"
    ]
    assert row["neutral_result_claim_statuses"] == [
        "accepted_negative_result_for_current_manuscript"
    ]
    assert row["reviewer_alignment_status"] == "direct_reviewer_advice_linked"
    assert row["positive_claim_promotion_authorized"] is False
    assert row["method_recommendation_authorized"] is False


def test_blueprint_alignment_build_blocks_if_final_prose_is_authorized(tmp_path):
    source_root = ROOT
    for source in [
        alignment.REVIEWER_DESIGN,
        alignment.CONTENT_MATRIX,
        alignment.RETENTION_AUDIT,
        alignment.RETENTION_MATRIX,
        alignment.NEUTRAL_LEDGER,
        alignment.PUBLICATION_ACTIVATION,
        alignment.PAPER_READINESS,
        alignment.PAPER_GATE_CLOSURE,
        alignment.NEUTRAL_LANGUAGE,
    ]:
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((source_root / source).read_text(), encoding="utf-8")

    activation_path = tmp_path / alignment.PUBLICATION_ACTIVATION
    activation_payload = json.loads(activation_path.read_text())
    activation_payload["summary"]["manuscript_drafting_authorized"] = True
    activation_path.write_text(json.dumps(activation_payload), encoding="utf-8")

    payload = alignment.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "article_supplement_blueprint_alignment_blocked"
    )
    assert checks["activation_remains_pre_prose_only"]["status"] == "fail"
