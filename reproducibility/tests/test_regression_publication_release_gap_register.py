import json
from pathlib import Path

from experiments.regression.scripts import (
    build_publication_release_gap_register as release_gap,
)


ROOT = Path(__file__).resolve().parents[1]


def load_checked_in_payload():
    return json.loads(
        (
            ROOT
            / "experiments/regression/manuscript/publication_release_gap_register.json"
        ).read_text()
    )


def test_checked_in_release_gap_register_blocks_final_release():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "publication_release_gap_register_ready_no_final_release"
    )
    assert summary["phase_state"] == (
        "neutral_pre_release_gap_register_active_final_release_blocked"
    )
    assert summary["deliverable_row_count"] == 11
    assert summary["pre_prose_evidence_ready_row_count"] == 11
    assert summary["release_authorized_count"] == 0
    assert summary["blocked_release_row_count"] == 11
    assert summary["source_traceable_row_count"] == 11
    assert summary["missing_source_artifact_count"] == 0
    assert summary["goal_can_mark_complete"] is False
    assert summary["noncomplete_requirement_count"] == 1
    assert summary["paper_blocked_gate_count"] == 6
    assert summary["positive_claim_ready_gate_count"] == 0
    assert summary["publication_preparation_authorized"] is True
    assert summary["private_authoring_authorized"] is True
    assert summary["research_document_authoring_authorized"] is True
    assert summary["minimal_main_broad_supplement_authorized"] is True
    assert summary["private_latex_html_review_outputs_ready"] is True
    assert summary["private_latex_html_review_output_audit_pass"] is True
    assert summary["private_sterile_publication_package_ready"] is True
    assert summary["private_publication_repository_remote_ready"] is True
    assert summary["private_publication_repository_visibility"] == "PRIVATE"
    assert summary["private_publication_repository_commit_match"] is True
    assert summary["private_review_artifact_ready_row_count"] == 11
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["sterile_repository_status"] == "planned_after_full_experiment_closure"
    assert summary["author_metadata_present"] is True
    assert summary["neutral_language_unguarded_hit_count"] == 0
    assert summary["scientific_no_method_promotion_guard_active"] is True
    assert summary["failed_check_count"] == 0


def test_release_gap_rows_are_source_traceable_and_not_release_authorized():
    payload = load_checked_in_payload()
    rows = payload["deliverable_rows"]

    assert {row["family"] for row in rows} == {
        "main_article",
        "supplementary_document",
        "kg_or_publication_site",
        "individual_experiment_report",
        "sterile_publication_repository",
    }
    for row in rows:
        assert row["pre_prose_evidence_ready"] is True
        assert row["private_review_artifact_ready"] is True
        assert row["release_status"] == "release_blocked_pre_prose_candidate_ready"
        assert row["release_authorized"] is False
        assert row["final_manuscript_prose_permission"] is False
        assert row["final_visual_table_retention_authorized"] is False
        assert row["publication_site_deployment_authorized"] is False
        assert row["kg_citable_component_authorized"] is False
        assert row["sterile_repository_creation_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False
        assert row["method_recommendation_authorized"] is False
        assert row["working_repository_final_citable"] is False
        assert row["release_blocker_count"] >= 4
        assert row["source_traceability_status"] == "pass"
        assert row["missing_source_artifacts"] == []
        assert "goal_not_marked_complete" in row["release_blockers"]
        for source in row["source_artifacts"]:
            assert (ROOT / source).exists(), source


def test_sterile_repository_row_is_deferred_to_new_clean_repo():
    payload = load_checked_in_payload()
    row = next(
        row
        for row in payload["deliverable_rows"]
        if row["deliverable_id"] == "sterile_publication_repository"
    )

    assert row["family"] == "sterile_publication_repository"
    assert row["release_authorized"] is False
    assert row["sterile_repository_creation_authorized"] is False
    assert row["working_repository_final_citable"] is False
    assert "sterile_repository_creation_not_authorized" in row["release_blockers"]
    assert "working_repository_not_final_citable" in row["release_blockers"]


def test_release_gap_build_blocks_if_final_release_is_authorized(tmp_path):
    for source in [
        release_gap.POST_PROGRAM,
        release_gap.GOAL_COMPLETION,
        release_gap.ACTIVATION,
        release_gap.PAPER_READINESS,
        release_gap.PAPER_GATE_CLOSURE,
        release_gap.BLUEPRINT_ALIGNMENT,
        release_gap.RETENTION_READINESS,
        release_gap.VISUAL_TABLE_AUDIT,
        release_gap.KG_PUBLICATION,
        release_gap.NEUTRAL_LANGUAGE,
        release_gap.AUTHORING_DECISION,
        release_gap.RELEASE_CUT,
        release_gap.PRIVATE_LATEX_HTML_MANIFEST,
        release_gap.PRIVATE_LATEX_HTML_AUDIT,
        release_gap.PRIVATE_PACKAGE_MANIFEST,
        release_gap.PRIVATE_REMOTE_AUDIT,
    ]:
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / source).read_text(), encoding="utf-8")

    activation_path = tmp_path / release_gap.ACTIVATION
    activation_payload = json.loads(activation_path.read_text())
    activation_payload["summary"]["manuscript_drafting_authorized"] = True
    activation_path.write_text(json.dumps(activation_payload), encoding="utf-8")

    payload = release_gap.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "publication_release_gap_register_blocked"
    )
    assert checks["activation_is_pre_prose_only"]["status"] == "fail"
