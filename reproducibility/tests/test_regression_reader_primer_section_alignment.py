import json
from pathlib import Path

from experiments.regression.scripts import build_reader_primer_section_alignment as alignment


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "experiments/regression/manuscript/reader_primer_section_alignment.json"


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_reader_primer_section_alignment_summary_is_pre_prose():
    payload = load_artifact()
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "reader_primer_section_alignment_ready_no_final_prose"
    )
    assert (
        summary["phase_state"]
        == "pre_prose_section_concept_alignment_final_outputs_blocked"
    )
    assert summary["alignment_row_count"] == 20
    assert summary["individual_report_alignment_row_count"] == 10
    assert summary["article_supplement_alignment_row_count"] == 10
    assert summary["unique_required_concept_count"] == 12
    assert summary["failed_alignment_row_count"] == 0
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["failed_check_count"] == 0


def test_reader_primer_section_alignment_maps_core_sections_to_concepts():
    payload = load_artifact()
    rows = {row["alignment_id"]: row for row in payload["alignment_rows"]}

    method_scope = rows[
        "individual_experiment_report:model_and_conformal_method_scope"
    ]
    assert "conformalized_quantile_regression_cqr" in method_scope[
        "required_concept_ids"
    ]
    assert "jackknife_plus_and_cv_plus" in method_scope["required_concept_ids"]
    assert "venn_abers_predictive_distributions" in method_scope[
        "required_concept_ids"
    ]
    assert method_scope["concept_alignment_status"] == "pass"

    venn = rows[
        "article_supplement_blueprint_alignment:venn_abers_failure_mode_evidence"
    ]
    assert venn["required_concept_ids"] == [
        "venn_abers_predictive_distributions",
        "result_metrics_and_claim_boundaries",
    ]
    assert venn["method_champion_authorized"] is False
    assert venn["positive_claim_promotion_authorized"] is False

    fairness = rows[
        "article_supplement_blueprint_alignment:fairness_group_diagnostic_tables"
    ]
    assert "mondrian_and_group_calibration" in fairness["required_concept_ids"]
    assert "alpha_and_nominal_coverage" in fairness["required_concept_ids"]


def test_reader_primer_section_alignment_blocks_missing_concepts(tmp_path):
    for path in [
        alignment.PRIMER_MAP,
        alignment.ARTICLE_ALIGNMENT,
        alignment.INDIVIDUAL_BLUEPRINT,
    ]:
        src = ROOT / path
        dst = tmp_path / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    primer_path = tmp_path / alignment.PRIMER_MAP
    primer = json.loads(primer_path.read_text(encoding="utf-8"))
    primer["concept_rows"] = [
        row
        for row in primer["concept_rows"]
        if row["concept_id"] != "venn_abers_predictive_distributions"
    ]
    primer_path.write_text(json.dumps(primer), encoding="utf-8")

    result = alignment.build_payload(tmp_path)
    summary = result["summary"]

    assert summary["overall_status"] == "reader_primer_section_alignment_blocked"
    assert summary["failed_alignment_row_count"] > 0
    assert summary["failed_check_count"] == 1
    assert result["failed_checks"][0]["check_id"] == "section_alignment_rows_complete"
