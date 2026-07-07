import json
from pathlib import Path

from experiments.regression.scripts import build_reader_method_primer_citation_map as primer


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT / "experiments/regression/manuscript/reader_method_primer_citation_map.json"
)


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_reader_method_primer_citation_map_is_pre_prose_and_source_backed():
    payload = load_artifact()
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "reader_method_primer_citation_map_ready_no_final_prose"
    )
    assert (
        summary["phase_state"]
        == "pre_prose_reader_concept_citation_mapping_final_outputs_blocked"
    )
    assert summary["concept_row_count"] == 12
    assert summary["reader_explanation_outline_count"] == 12
    assert summary["primary_source_url_count"] >= 10
    assert summary["literature_tracked_gap_count"] == 0
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert (
        summary["result_reporting_policy"]
        == "analysis_only_report_observed_behavior_no_method_advocacy"
    )
    assert summary["failed_check_count"] == 0


def test_reader_method_primer_covers_core_nonexpert_concepts():
    payload = load_artifact()
    rows = {row["concept_id"]: row for row in payload["concept_rows"]}

    for concept_id in [
        "conformal_prediction_regression",
        "alpha_and_nominal_coverage",
        "conformalized_quantile_regression_cqr",
        "jackknife_plus_and_cv_plus",
        "venn_abers_predictive_distributions",
        "result_metrics_and_claim_boundaries",
    ]:
        assert concept_id in rows
        row = rows[concept_id]
        assert row["plain_language_role"]
        assert row["paper_use"]
        assert row["primary_source_urls"]
        assert row["required_reader_explanation"]
        assert row["reader_explanation_outline"]
        assert row["citation_use_note"]
        assert row["blocked_language"]

    assert rows["conformalized_quantile_regression_cqr"]["primary_source_urls"] == [
        "https://arxiv.org/abs/1905.03222"
    ]
    assert "CQR is the universally best regression CP method" in rows[
        "conformalized_quantile_regression_cqr"
    ]["blocked_language"]
    assert any(
        "calibration score" in item
        for item in rows["conformalized_quantile_regression_cqr"][
            "reader_explanation_outline"
        ]
    )
    assert "https://arxiv.org/abs/1905.02928" in rows[
        "jackknife_plus_and_cv_plus"
    ]["primary_source_urls"]
    assert "https://arxiv.org/abs/2002.09025" in rows[
        "jackknife_plus_and_cv_plus"
    ]["primary_source_urls"]
    assert "validated Venn-Abers regression interval method" in rows[
        "venn_abers_predictive_distributions"
    ]["blocked_language"]
    assert "not to imply a validated regression-interval recommendation" in rows[
        "venn_abers_predictive_distributions"
    ]["citation_use_note"]


def test_reader_method_primer_blocks_when_upstream_policy_opens(tmp_path):
    for path in [primer.METHOD_LITERATURE_AUDIT, primer.CLAIM_EVIDENCE_MATRIX]:
        src = ROOT / path
        dst = tmp_path / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    claim_path = tmp_path / primer.CLAIM_EVIDENCE_MATRIX
    payload = json.loads(claim_path.read_text(encoding="utf-8"))
    payload["summary"]["method_champion_authorized"] = True
    claim_path.write_text(json.dumps(payload), encoding="utf-8")

    result = primer.build_payload(tmp_path)
    summary = result["summary"]

    assert summary["overall_status"] == "reader_method_primer_citation_map_blocked"
    assert summary["failed_check_count"] == 1
    assert result["failed_checks"][0]["check_id"] == (
        "claim_evidence_matrix_keeps_final_outputs_blocked"
    )
