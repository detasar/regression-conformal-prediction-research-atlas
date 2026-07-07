import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "experiments/regression/manuscript/neutral_result_ledger.json"


def load_ledger():
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def rows_by_id(payload):
    return {row["result_id"]: row for row in payload["result_rows"]}


def test_checked_in_neutral_result_ledger_is_no_promotion():
    payload = load_ledger()
    summary = payload["summary"]

    assert summary["overall_status"] == "neutral_result_ledger_ready_no_method_promotion"
    assert summary["row_count"] == 9
    assert summary["missing_source_artifact_count"] == 0
    assert summary["positive_claim_promotion_authorized_count"] == 0
    assert summary["final_method_selection_authorized_count"] == 0
    assert summary["final_visual_table_retention_authorized_count"] == 0
    assert summary["final_manuscript_prose_permission_count"] == 0
    assert summary["sterile_repository_creation_authorized_count"] == 0
    assert summary["neutral_no_method_promotion_guard_active"] is True
    assert summary["cqr_descriptive_candidate_recorded"] is True
    assert summary["venn_abers_negative_result_recorded"] is True
    assert summary["failed_check_count"] == 0


def test_neutral_result_ledger_rows_have_traceable_sources():
    payload = load_ledger()

    for row in payload["result_rows"]:
        assert row["source_traceability_status"] == "pass"
        assert row["missing_source_artifacts"] == []
        assert row["source_artifacts"]
        assert row["positive_claim_promotion_authorized"] is False
        assert row["final_method_selection_authorized"] is False
        assert row["final_manuscript_prose_permission"] is False
        for source in row["source_artifacts"]:
            assert (ROOT / source).exists(), source


def test_cqr_is_recorded_as_descriptive_not_final_selection():
    rows = rows_by_id(load_ledger())
    method_row = rows["method_performance_descriptive_frontier"]
    selection_row = rows["selection_multiplicity_robustness_diagnostic"]

    assert method_row["claim_status"] == "descriptive_no_final_selection"
    assert method_row["extracted_metrics"]["can_support_final_method_selection"] is False
    assert any("Do not call CQR" in item for item in method_row["forbidden_interpretations"])
    assert selection_row["extracted_metrics"]["diagnostic_primary_method"] == "cqr"
    assert selection_row["extracted_metrics"]["final_selection_claim_status"] == "blocked"
    assert selection_row["extracted_metrics"]["can_support_final_method_selection"] is False


def test_venn_abers_is_negative_diagnostic_not_validated():
    rows = rows_by_id(load_ledger())
    row = rows["venn_abers_regression_negative_evidence"]
    metrics = row["extracted_metrics"]

    assert row["claim_status"] == "accepted_negative_result_for_current_manuscript"
    assert metrics["positive_claim_ready"] is False
    assert metrics["positive_claim_blocked_count"] == 3
    assert metrics["undercoverage_run_count"] == 14
    assert metrics["ivapd_interval_cp_status"] == "blocked_predictive_distribution_only"
    assert metrics["negative_result_reporting_ready"] is True
    assert any("Do not claim validated Venn-Abers" in item for item in row["forbidden_interpretations"])
