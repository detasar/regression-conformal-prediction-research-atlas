import json
from pathlib import Path

from experiments.regression.scripts import (
    audit_scientific_neutrality_interpretation_lock as lock,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    ROOT
    / "experiments/regression/manuscript/"
    / "scientific_neutrality_interpretation_lock.json"
)


def load_checked_in_payload():
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def copy_lock_sources(tmp_path):
    for source in lock.SOURCE_PATHS.values():
        source_path = ROOT / source
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")


def test_checked_in_scientific_neutrality_interpretation_lock_is_neutral():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "scientific_neutrality_interpretation_lock_ready_no_method_promotion"
    )
    assert summary["phase_state"] == (
        "neutral_interpretation_locked_final_claims_and_outputs_blocked"
    )
    assert summary["interpretation_row_count"] == 8
    assert summary["missing_source_artifact_count"] == 0
    assert summary["neutral_language_unguarded_hit_count"] == 0
    assert summary["cqr_cvplus_reporting_role"] == (
        "descriptive_diagnostic_no_final_selection_no_method_promotion"
    )
    assert summary["venn_abers_reporting_role"] == (
        "negative_failure_mode_no_validated_regression_claim"
    )
    assert summary["main_results_positive_boundary_blocked"] is True
    assert summary["venn_abers_negative_boundary_preserved"] is True
    assert summary["validated_venn_abers_regression_claim_ready"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["scientific_test_not_method_promotion"] is True
    assert summary["analysis_only_no_champion_method"] is True
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert (
        summary["result_reporting_policy"]
        == "analysis_only_report_observed_behavior_no_method_advocacy"
    )
    assert summary["failed_check_count"] == 0


def test_interpretation_rows_have_allowed_and_blocked_language_boundaries():
    payload = load_checked_in_payload()
    rows = {row["row_id"]: row for row in payload["interpretation_rows"]}

    assert set(rows) == {
        "experiment_scope",
        "method_frontier_cqr_cvplus",
        "venn_abers_negative_result",
        "main_results_positive_claim",
        "fairness_population_scope",
        "bounded_support_scope",
        "kg_site_visuals",
        "sterile_repository_and_manuscript_outputs",
    }
    method_row = rows["method_frontier_cqr_cvplus"]
    assert "descriptive or diagnostic" in method_row["allowed_interpretation"]
    assert "global best method" in method_row["blocked_interpretation"]
    venn_row = rows["venn_abers_negative_result"]
    assert "negative/failure-mode" in venn_row["allowed_interpretation"]
    assert "validated Venn-Abers regression" in venn_row["blocked_interpretation"]
    for row in rows.values():
        assert row["source_artifacts"]
        assert row["final_prose_authorized"] is False
        assert row["method_recommendation_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False


def test_lock_blocks_if_method_recommendation_flag_is_opened(tmp_path):
    copy_lock_sources(tmp_path)

    reconciliation_path = tmp_path / lock.PUBLICATION_RECONCILIATION
    payload = json.loads(reconciliation_path.read_text(encoding="utf-8"))
    payload["summary"]["method_recommendation_authorized"] = True
    reconciliation_path.write_text(json.dumps(payload), encoding="utf-8")

    result = lock.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "scientific_neutrality_interpretation_lock_blocked"
    )
    assert checks["neutral_policy_and_language_controls_pass"]["status"] == "fail"
    assert checks["method_frontier_not_promoted"]["status"] == "fail"
    assert checks["analysis_only_no_champion_method_locked"]["status"] == "fail"


def test_lock_blocks_if_method_synthesis_becomes_final_selection(tmp_path):
    copy_lock_sources(tmp_path)

    synthesis_path = tmp_path / lock.METHOD_SYNTHESIS
    payload = json.loads(synthesis_path.read_text(encoding="utf-8"))
    payload["summary"]["claim_status"] = "final_selection_claim"
    synthesis_path.write_text(json.dumps(payload), encoding="utf-8")

    result = lock.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "scientific_neutrality_interpretation_lock_blocked"
    )
    assert result["summary"]["analysis_only_no_champion_method"] is False
    assert checks["analysis_only_no_champion_method_locked"]["status"] == "fail"


def test_lock_blocks_if_venn_abers_positive_validation_claim_opens(tmp_path):
    copy_lock_sources(tmp_path)

    validation_path = tmp_path / lock.VENN_VALIDATION
    validation_payload = json.loads(validation_path.read_text(encoding="utf-8"))
    validation_payload["summary"][
        "can_support_venn_abers_regression_validation"
    ] = True
    validation_path.write_text(json.dumps(validation_payload), encoding="utf-8")

    result = lock.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "scientific_neutrality_interpretation_lock_blocked"
    )
    assert checks["venn_abers_negative_boundary_preserved"]["status"] == "fail"


def test_lock_blocks_if_final_release_is_authorized(tmp_path):
    copy_lock_sources(tmp_path)

    release_path = tmp_path / lock.RELEASE_GAP
    release_payload = json.loads(release_path.read_text(encoding="utf-8"))
    release_payload["summary"]["release_authorized_count"] = 1
    release_path.write_text(json.dumps(release_payload), encoding="utf-8")

    result = lock.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "scientific_neutrality_interpretation_lock_blocked"
    )
    assert checks["final_outputs_and_release_remain_blocked"]["status"] == "fail"
