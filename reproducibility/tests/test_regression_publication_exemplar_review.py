import json
from pathlib import Path

from experiments.regression.scripts import build_publication_exemplar_review as review


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "experiments/regression/manuscript/publication_exemplar_review.json"
MARKDOWN = ROOT / "experiments/regression/manuscript/publication_exemplar_review.md"


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_publication_exemplar_review_is_source_backed_and_neutral():
    payload = load_artifact()
    summary = payload["summary"]

    assert summary["overall_status"] == "publication_exemplar_review_ready"
    assert summary["external_source_row_count"] == 10
    assert summary["external_supporting_url_count"] >= 4
    assert summary["design_decision_row_count"] == 10
    assert summary["failed_check_count"] == 0
    assert summary["new_experiments_authorized"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["public_release_authorized"] is False

    source_ids = {row["source_id"] for row in payload["source_rows"]}
    assert source_ids == {
        "cqr_neurips_paper_and_supplement",
        "cqr_github_and_site",
        "cqr_comparison_repo",
        "mapie_docs_and_repo",
        "ryantibs_conformal_regression_repo",
        "angelopoulos_bates_tutorial_repo",
        "neurips_paper_checklist_guidelines",
        "paperswithcode_research_code_release_guidance",
        "venn_abers_pmlr_2024",
        "generalized_venn_abers_pmlr_2025",
    }
    for row in payload["source_rows"]:
        assert row["primary_url"].startswith("https://")
        assert row["inspected_evidence"]
        assert row["design_lesson"]

    for row in payload["design_decision_rows"]:
        assert row["source_ids"]
        assert set(row["source_ids"]).issubset(source_ids)
        assert row["project_application"]


def test_publication_exemplar_review_builder_blocks_missing_decision_source(monkeypatch):
    original = review.design_decision_rows

    def broken_rows():
        rows = original()
        rows[0] = {**rows[0], "source_ids": ["missing_source"]}
        return rows

    monkeypatch.setattr(review, "design_decision_rows", broken_rows)
    payload = review.build_payload(ROOT)

    assert payload["summary"]["overall_status"] == "publication_exemplar_review_blocked"
    failed_ids = {row["check_id"] for row in payload["failed_checks"]}
    assert "design_decisions_source_traceable" in failed_ids


def test_publication_exemplar_review_markdown_exposes_design_basis():
    text = MARKDOWN.read_text(encoding="utf-8")

    assert "# Publication Exemplar Review" in text
    assert "## External Sources Inspected" in text
    assert "## Design Lessons For This Project" in text
    assert "not a method recommendation" in text
    assert "not a public release authorization" in text
    assert "Conformalized Quantile Regression" in text
    assert "comparison of some conformal quantile regression methods" in text
    assert "MAPIE documentation and GitHub repository" in text
    assert "NeurIPS Paper Checklist Guidelines" in text
    assert "Papers with Code research-code release guidance" in text
    assert "Venn-Abers" in text
    assert "minimal main article and a broad supplementary document" in text
