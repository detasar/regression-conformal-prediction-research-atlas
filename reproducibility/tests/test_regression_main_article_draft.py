import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "experiments/regression/manuscript/main_article_draft.json"
ARTICLE = ROOT / "experiments/regression/manuscript/main_article_draft.md"
REGISTRY = ROOT / "experiments/regression/manuscript/publication_citation_registry.json"
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def load_kg_graph():
    return json.loads(KG_QUALITY.read_text(encoding="utf-8"))["graph"]


def test_main_article_draft_is_source_backed_and_neutral():
    payload = load_artifact()
    summary = payload["summary"]
    graph = load_kg_graph()

    assert summary["overall_status"] == "main_article_draft_ready"
    assert summary["draft_not_final"] is True
    assert summary["author_name"] == "Emre Tasar"
    assert summary["author_role"] == "Data Scientist"
    assert summary["author_email"] == "detasar@gmail.com"
    assert summary["author_header"] == "Author: Emre Tasar, Data Scientist"
    assert summary["publication_completed_rows"] == 145839
    assert summary["dataset_count"] == 67
    assert summary["dataset_alpha_cell_count"] == 95
    assert summary["method_count"] == 28
    assert summary["cqr_frontier_cell_count"] == 56
    assert summary["mondrian_frontier_cell_count"] == 15
    assert summary["cv_plus_frontier_cell_count"] == 13
    assert summary["venn_undercoverage_run_count"] == 14
    assert summary["bounded_support_validity_ready_bundle_count"] == 0
    assert summary["fairness_population_ready_bundle_count"] == 0
    assert summary["kg_node_count"] == graph["node_count"]
    assert summary["kg_edge_count"] == graph["edge_count"]
    assert summary["main_article_blueprint_row_count"] == 4
    assert summary["main_article_verification_row_count"] == 3
    assert summary["claim_evidence_map_row_count"] == 6
    assert summary["research_question_row_count"] == 5
    assert summary["guarantee_boundary_row_count"] == 5
    assert summary["paper_architecture_row_count"] == 5
    assert summary["method_reader_safety_row_count"] == 5
    assert summary["concept_bridge_row_count"] == 5
    assert summary["evidence_to_claim_ladder_row_count"] == 6
    assert summary["failed_check_count"] == 0
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["release_authorized"] is False

    claim_row_ids = {row["row_id"] for row in payload["claim_evidence_rows"]}
    assert claim_row_ids == {
        "empirical_scope",
        "cqr_cv_plus_practical_candidates",
        "venn_abers_bridge_negative_evidence",
        "bounded_support_claim_closed",
        "fairness_claim_closed",
        "kg_traceability",
    }
    question_rows = {row["question"]: row for row in payload["research_question_rows"]}
    assert set(question_rows) == {
        "What empirical object is being audited?",
        "Which practical method pattern is supported descriptively?",
        "What did the evaluated Venn-Abers regression bridge show?",
        "Which stronger positive claims remain closed?",
        "How can the evidence be audited without opening release?",
    }
    assert all(row["article_answer"] for row in question_rows.values())
    assert all(row["evidence_anchor"] for row in question_rows.values())
    assert all(row["closed_reading"].startswith("Do not ") for row in question_rows.values())
    assert f"{summary['kg_node_count']:,}" in question_rows[
        "How can the evidence be audited without opening release?"
    ]["article_answer"]
    guarantee_topics = {row["topic"] for row in payload["guarantee_boundary_rows"]}
    assert guarantee_topics == {
        "Marginal conformal coverage",
        "Empirical coverage",
        "Group diagnostics",
        "Frontier evidence",
        "Venn-Abers bridge",
    }
    assert all(row["article_statement"] for row in payload["guarantee_boundary_rows"])
    assert all(row["closed_reading"] for row in payload["guarantee_boundary_rows"])
    architecture_rows = {row["row_id"]: row for row in payload["paper_architecture_rows"]}
    assert set(architecture_rows) == {
        "minimal_main_article",
        "broad_supplement",
        "readme_review_router",
        "private_site_and_kg",
        "claim_evidence_contract",
    }
    assert (
        architecture_rows["private_site_and_kg"]["boundary"]
        == "KG citation, GitHub Pages, and public site deployment remain closed."
    )
    assert (
        architecture_rows["claim_evidence_contract"]["boundary"]
        == "No prose may convert a blocked claim into a positive conclusion."
    )
    concept_rows = {row["concept"]: row for row in payload["concept_bridge_rows"]}
    assert set(concept_rows) == {
        "Conformal prediction target",
        "Conformalized Quantile Regression",
        "CV+ and jackknife-style intervals",
        "Venn-Abers regression bridge",
        "Claim-gated empirical wording",
    }
    assert all(row["source_anchor"] for row in concept_rows.values())
    assert all(row["article_use"] for row in concept_rows.values())
    assert all(row["safe_sentence"] for row in concept_rows.values())
    assert all(row["blocked_sentence"].startswith("Do not ") for row in concept_rows.values())
    assert "lei2017distribution_free_regression" in concept_rows[
        "Conformal prediction target"
    ]["source_anchor"]
    assert "romano2019conformalized_quantile_regression" in concept_rows[
        "Conformalized Quantile Regression"
    ]["source_anchor"]
    assert "barber2020jackknife_plus" in concept_rows[
        "CV+ and jackknife-style intervals"
    ]["source_anchor"]
    assert "vanderlaan2025generalized_venn_abers" in concept_rows[
        "Venn-Abers regression bridge"
    ]["source_anchor"]
    ladder_rows = {row["stage"]: row for row in payload["evidence_to_claim_ladder_rows"]}
    assert set(ladder_rows) == {
        "Completed row",
        "Dataset-alpha cell",
        "Method diagnostic",
        "Failure-mode diagnostic",
        "Closed positive gate",
        "Release and citation gate",
    }
    assert (
        ladder_rows["Method diagnostic"]["blocked_upgrade"]
        == "Frontier counts do not select a final or universal best method."
    )
    assert (
        ladder_rows["Closed positive gate"]["blocked_upgrade"]
        == "Zero-ready gates cannot be converted into validity or fairness claims."
    )


def test_main_article_draft_uses_registered_citations():
    report = ARTICLE.read_text(encoding="utf-8")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registered = {row["citation_key"] for row in registry["citation_rows"]}
    cited = set(re.findall(r"\[@([A-Za-z0-9_]+)", report))
    cited.update(re.findall(r"`@([A-Za-z0-9_]+)`", report))

    assert cited
    assert cited.issubset(registered)
    for required_key in [
        "lei2017distribution_free_regression",
        "romano2019conformalized_quantile_regression",
        "barber2020jackknife_plus",
        "kim2020jackknife_after_bootstrap",
        "nouretdinov2018ivapd",
        "vanderlaan2025generalized_venn_abers",
    ]:
        assert required_key in cited


def test_main_article_draft_markdown_keeps_claim_boundaries_visible():
    article = ARTICLE.read_text(encoding="utf-8")

    for heading in [
        "## Abstract",
        "## Introduction",
        "### Reader Orientation",
        "### Guarantee And Claim Boundary Snapshot",
        "### Contributions And Boundaries",
        "### Paper Architecture And Review Contract",
        "## Research Questions",
        "## Concept Bridge For Non-Specialist Readers",
        "## Claim-Evidence Map",
        "## Study Design Summary",
        "## Evidence-To-Claim Ladder",
        "## Background And Methods",
        "### Method Primer For Non-Specialist Readers",
        "### Reader Safety Checklist",
        "### Notation And Evaluation Protocol",
        "## Results",
        "## Discussion",
        "## Reproducibility And Traceability",
        "## Limitations",
        "## Conclusion",
        "## References",
    ]:
        assert heading in article

    assert "not a method recommendation" in article
    assert "Author: Emre Tasar, Data Scientist" in article
    assert "Email: detasar@gmail.com" in article
    assert "A prediction interval is a range-valued prediction" in article
    assert "Coverage and interval width must be read together" in article
    assert "Which patterns are supported by the completed evidence" in article
    assert "the main article version of the Research Document's guarantee boundary ledger" in article
    assert "The conformal guarantee is a marginal coverage statement" in article
    assert "not conditional, subgroup, endpoint, or deployment coverage" in article
    assert "not final method selection or universal superiority claims" in article
    assert "not a rejection of predictive-distribution or generalized Venn-Abers research" in article
    assert "under resumable, source-traceable execution records" in article
    assert "source-backed publication exemplar review" in article
    assert "the supplement and KG carry the detailed audit trail" in article
    assert "Use the supplement for method detail, robustness diagnostics" in article
    assert "Use the site and KG browser to trace claims to source artifacts" in article
    assert "No prose may convert a blocked claim into a positive conclusion" in article
    assert "KG citation, GitHub Pages, and public site deployment remain closed" in article
    assert "The article is organized around five research questions" in article
    assert "What empirical object is being audited?" in article
    assert "Which practical method pattern is supported descriptively?" in article
    assert "What did the evaluated Venn-Abers regression bridge show?" in article
    assert "Which stronger positive claims remain closed?" in article
    assert "How can the evidence be audited without opening release?" in article
    assert "Do not cite, publish, or deploy the KG/site before explicit release authorization" in article
    assert "This bridge links the main technical concepts to the sources and claim boundaries" in article
    assert "Conformal prediction target | Distribution-free regression conformal prediction" in article
    assert "Conformalized Quantile Regression | CQR lower/upper quantile calibration" in article
    assert "CV+ and jackknife-style intervals | Jackknife+/CV+ resampling evidence" in article
    assert "Venn-Abers regression bridge | Venn-Abers predictive-distribution and generalized-calibration literature" in article
    assert "Claim-gated empirical wording | Publication claim-evidence matrix and section-boundary audit" in article
    assert "Closed gates are part of the scientific result and should remain visible" in article
    assert "Do not promote a diagnostic pattern into a method recommendation" in article
    assert "a negative result can be retained without being softened into a positive story" in article
    assert "how a raw experimental object becomes a reader-facing statement" in article
    assert "Each step has an allowed claim and a blocked upgrade" in article
    assert "Completed row | What was counted?" in article
    assert "Method diagnostic | What pattern was observed?" in article
    assert "Closed positive gate | Which stronger claims stay absent?" in article
    assert "Release and citation gate | When can artifacts be cited or published?" in article
    assert "Zero-ready gates cannot be converted into validity or fairness claims" in article
    assert "reader-facing claim is paired with source-backed evidence" in article
    assert "C_m(X_i) = [L_m(X_i), U_m(X_i)]" in article
    assert "basic coverage indicator is `1{Y_i in C_m(X_i)}`" in article
    assert "Empirical coverage is the average of this indicator" in article
    assert "frontier cell marks an observed coverage/width trade-off" in article
    assert "Diagnostic pattern, not final selection" in article
    assert "### Method Mechanics Snapshot" in article
    assert "methods differ mainly in how they choose or adjust interval endpoints" in article
    assert "Split conformal | Residual-score quantile" in article
    assert "Venn-Abers bridge | Bridge from Venn-Abers-style calibration evidence" in article
    assert "A conformal method should be read as a calibration wrapper" in article
    assert "CQR means Conformalized Quantile Regression" in article
    assert "CV+ belongs to the cross-validation-plus family" in article
    assert "The evaluated Venn-Abers regression bridge has a different status" in article
    assert "This is bridge-specific negative evidence, not a literature-wide rejection" in article
    assert "method primer into claim boundaries" in article
    assert "which parts are conformal-method background" in article
    assert (
        "It is not a final selected method, universal best method, or production recommendation"
        in article
    )
    assert (
        "It is not caveat-free evidence and does not open final method selection"
        in article
    )
    assert (
        "It is not a population fairness claim while the fairness-ready bundle count is zero"
        in article
    )
    assert (
        "not a rejection of predictive distribution or generalized Venn-Abers research"
        in article
    )
    assert "### How To Read The Results Table" in article
    assert "zero-ready gates record claims the article must not make" in article
    assert "support interpretation, not final method selection" in article
    assert "CQR/CV+ were observed in these experiments as strong practical candidates" in article
    assert "The expected strong Venn-Abers regression solution did not emerge" in article
    assert "not that CQR is the best regression conformal method in general" in article
    assert "a validated Venn-Abers regression interval claim" in article
    assert "No population fairness claim" in article
    assert "No bounded-support validity claim" in article
    assert "will become citable only after the sterile repository" in article
    assert "descriptive, not prescriptive, interpretation" in article
    assert "does not support final method selection" in article
    assert "general method recommendation" in article
    assert "negative evidence is not rewritten as success" in article
    assert "blocked claims remain visible until later evidence explicitly opens them" in article
