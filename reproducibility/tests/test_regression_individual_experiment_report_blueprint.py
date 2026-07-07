import json
from pathlib import Path

from experiments.regression.scripts import (
    build_individual_experiment_report_blueprint as blueprint,
)


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_PATH = (
    ROOT
    / "experiments/regression/manuscript/individual_experiment_report_blueprint.json"
)


def load_checked_in_payload():
    return json.loads(BLUEPRINT_PATH.read_text(encoding="utf-8"))


def rows_by_id(payload):
    return {row["section_id"]: row for row in payload["section_rows"]}


def copy_blueprint_sources(tmp_path):
    for source in blueprint.SOURCE_PATHS.values():
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / source).read_text(encoding="utf-8"), encoding="utf-8")


def test_checked_in_individual_report_blueprint_is_pre_prose_only():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "individual_experiment_report_blueprint_ready_no_final_prose"
    )
    assert summary["phase_state"] == (
        "neutral_pre_prose_individual_report_blueprint_active_final_outputs_blocked"
    )
    assert summary["author_header"] == "Author: Emre Tasar, Data Scientist"
    assert summary["author_email"] == "detasar@gmail.com"
    assert summary["approved_author_header_present"] is True
    assert summary["deliverable_registered"] is True
    assert summary["deliverable_format"] == "latex_html_and_markdown"
    assert summary["section_row_count"] == 10
    assert summary["source_traceable_row_count"] == 10
    assert summary["missing_source_artifact_count"] == 0
    assert summary["linked_neutral_result_issue_count"] == 0
    assert summary["final_report_prose_permission"] is False
    assert summary["latex_output_authorized"] is False
    assert summary["html_output_authorized"] is False
    assert summary["markdown_output_authorized"] is False
    assert summary["release_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["cqr_reporting_role"] == "descriptive_diagnostic_no_final_selection"
    assert summary["venn_abers_reporting_role"] == (
        "negative_failure_mode_no_validated_regression_claim"
    )
    assert summary["scientific_no_method_promotion_guard_active"] is True
    assert summary["failed_check_count"] == 0


def test_individual_report_blueprint_rows_are_traceable_and_not_final_outputs():
    payload = load_checked_in_payload()
    assert len(payload["section_rows"]) == 10

    for row in payload["section_rows"]:
        assert row["source_traceability_status"] == "pass"
        assert row["missing_source_artifacts"] == []
        assert row["source_artifacts"]
        assert row["linked_neutral_result_count"] >= 1
        assert row["final_report_prose_permission"] is False
        assert row["latex_output_authorized"] is False
        assert row["html_output_authorized"] is False
        assert row["markdown_output_authorized"] is False
        assert row["release_authorized"] is False
        assert row["sterile_repository_creation_authorized"] is False
        assert row["working_repository_final_citable"] is False
        assert row["method_recommendation_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False
        for source in row["source_artifacts"]:
            assert (ROOT / source).exists(), source


def test_venn_abers_section_is_negative_evidence_not_validated_claim():
    row = rows_by_id(load_checked_in_payload())["venn_abers_negative_evidence"]

    assert row["section_role"] == "negative_failure_mode_no_validated_regression_claim"
    assert row["neutral_result_ids"] == ["venn_abers_regression_negative_evidence"]
    assert row["method_recommendation_authorized"] is False
    assert row["positive_claim_promotion_authorized"] is False
    assert row["final_report_prose_permission"] is False


def test_individual_report_blueprint_blocks_if_release_or_final_prose_is_authorized(
    tmp_path,
):
    copy_blueprint_sources(tmp_path)

    release_path = tmp_path / blueprint.RELEASE_GAP
    release_payload = json.loads(release_path.read_text(encoding="utf-8"))
    release_payload["summary"]["release_authorized_count"] = 1
    for row in release_payload["deliverable_rows"]:
        if row["deliverable_id"] == "individual_experiment_report":
            row["release_authorized"] = True
            row["final_manuscript_prose_permission"] = True
    release_path.write_text(json.dumps(release_payload), encoding="utf-8")

    activation_path = tmp_path / blueprint.ACTIVATION
    activation_payload = json.loads(activation_path.read_text(encoding="utf-8"))
    activation_payload["summary"]["manuscript_drafting_authorized"] = True
    activation_path.write_text(json.dumps(activation_payload), encoding="utf-8")

    payload = blueprint.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "individual_experiment_report_blueprint_blocked"
    )
    assert checks["release_gap_blocks_final_report"]["status"] == "fail"
    assert checks["activation_remains_pre_prose_only"]["status"] == "fail"
    assert checks["no_final_report_outputs_or_claim_promotions"]["status"] == "fail"
