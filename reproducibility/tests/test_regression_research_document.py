import json
import re
from pathlib import Path

from experiments.regression.scripts import build_research_document


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "experiments/regression/manuscript/research_document.json"
DOCUMENT = ROOT / "experiments/regression/manuscript/research_document.md"
REGISTRY = ROOT / "experiments/regression/manuscript/publication_citation_registry.json"
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_research_document_is_private_ready_and_neutral():
    payload = load_artifact()
    summary = payload["summary"]
    graph = json.loads(KG_QUALITY.read_text(encoding="utf-8"))["graph"]

    assert payload["schema"] == "cpfi_regression_research_document_v1"
    assert summary["overall_status"] == "research_document_private_authoring_ready"
    assert summary["research_document_authoring_authorized"] is True
    assert summary["public_release_authorized"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["author_name"] == "Emre Tasar"
    assert summary["author_role"] == "Data Scientist"
    assert summary["author_email"] == "detasar@gmail.com"
    assert summary["author_header"] == "Author: Emre Tasar, Data Scientist"
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["new_experiments_authorized"] is False
    assert summary["publication_completed_rows"] == 145839
    assert summary["dataset_count"] == 67
    assert summary["dataset_alpha_cell_count"] == 95
    assert summary["method_count"] == 28
    assert summary["cqr_frontier_cell_count"] == 56
    assert summary["cv_plus_frontier_cell_count"] == 13
    assert summary["mondrian_frontier_cell_count"] == 15
    assert summary["venn_undercoverage_run_count"] == 14
    assert summary["bounded_support_validity_ready_bundle_count"] == 0
    assert summary["fairness_population_ready_bundle_count"] == 0
    assert summary["supplement_section_count"] == 6
    assert summary["kg_node_count"] == graph["node_count"]
    assert summary["kg_edge_count"] == graph["edge_count"]
    assert summary["kg_isolated_node_count"] == 0
    assert summary["kg_average_edge_confidence"] > 0.99
    assert summary["kg_edge_selector_provenance_coverage"] == 1.0
    assert summary["private_review_surface_count"] == 6
    assert summary["private_review_surface_pass_count"] == 6
    assert summary["research_question_row_count"] == 5
    assert summary["contribution_finding_row_count"] == 6
    assert summary["scientific_method_row_count"] == 6
    assert summary["private_review_decision_row_count"] == 5
    assert summary["reader_contract_row_count"] == 4
    assert summary["executive_synthesis_paragraph_count"] == 5
    assert summary["plain_language_summary_row_count"] == 5
    assert summary["reader_primer_term_count"] == 8
    assert summary["citation_backed_concept_row_count"] == 8
    assert summary["method_mechanics_row_count"] == 5
    assert summary["guarantee_boundary_row_count"] == 5
    assert summary["result_reading_row_count"] == 6
    assert summary["result_interpretation_ladder_row_count"] == 6
    assert summary["claim_language_guardrail_row_count"] == 8
    assert summary["claim_review_row_count"] == 8
    assert summary["claim_review_supported_count"] == 8
    assert summary["claim_review_citation_gate_count"] == 8
    assert summary["claim_review_overclaim_blocked_count"] == 8
    assert summary["claim_review_non_specialist_explanation_count"] == 8
    assert summary["claim_review_status_counts"] == {"pass": 8}
    assert summary["publication_exemplar_source_row_count"] == 10
    assert summary["publication_exemplar_design_decision_row_count"] == 10
    assert summary["kg_browser_node_count"] == graph["node_count"]
    assert summary["kg_browser_edge_count"] == graph["edge_count"]
    assert summary["kg_browser_node_type_count"] > 0
    assert summary["kg_browser_relation_type_count"] > 0
    assert summary["cross_run_leakage_status"] == (
        "hard_leakage_not_detected_in_scanned_artifacts"
    )
    assert summary["cross_run_unsupported_claim_hits"] == 0
    assert summary["duplicate_unquarantined_action_count"] == 0
    assert summary["robustness_bootstrap_selection_counts"] == {"cqr": 1000}
    assert summary["venn_can_support_validated_regression"] is False
    assert summary["failed_check_count"] == 0
    contract_rows = payload["reader_contract_rows"]
    assert len(contract_rows) == 4
    assert {row["reading_layer"] for row in contract_rows} == {
        "Empirical object",
        "Observed pattern",
        "Negative evidence",
        "Traceability and release",
    }
    assert all(row["reader_question"] for row in contract_rows)
    assert all(row["safe_reading"] for row in contract_rows)
    assert all(row["boundary"].startswith("Do not ") for row in contract_rows)
    executive_rows = payload["executive_synthesis_rows"]
    assert len(executive_rows) == 5
    assert {row["paragraph_id"] for row in executive_rows} == {
        "study_identity",
        "supported_finding",
        "negative_evidence",
        "closed_claims",
        "review_path",
    }
    assert all(row["heading"] for row in executive_rows)
    assert all(row["body"] for row in executive_rows)
    assert all(row["boundary"].startswith("Do not ") for row in executive_rows)
    assert any("CQR/CV+ were observed" in row["body"] for row in executive_rows)
    assert any("Venn-Abers regression bridge" in row["body"] for row in executive_rows)
    assert any("zero" in row["body"] for row in executive_rows)
    plain_rows = payload["plain_language_summary_rows"]
    assert len(plain_rows) == 5
    assert {row["reader_question"] for row in plain_rows} == {
        "What is the shortest correct reading of the study?",
        "What does the CQR/CV+ finding mean?",
        "What does `1 - alpha` mean here?",
        "How should the Venn-Abers bridge result be read?",
        "Why keep the KG and private package in the review path?",
    }
    assert all(row["plain_language_answer"] for row in plain_rows)
    assert all(row["evidence_anchor"] for row in plain_rows)
    assert all(row["boundary"].startswith("Do not ") for row in plain_rows)
    expected_kg_anchor = f"{graph['node_count']:,} KG nodes"
    assert any(expected_kg_anchor in row["evidence_anchor"] for row in plain_rows)
    terms = {row["term"] for row in payload["reader_primer_rows"]}
    assert terms == {
        "prediction interval",
        "coverage",
        "1 - alpha",
        "calibration set",
        "CQR",
        "CV+",
        "frontier cell",
        "Venn-Abers regression bridge",
    }
    guardrails = payload["claim_language_guardrail_rows"]
    assert len(guardrails) == 8
    assert {row["claim_review_status"] for row in guardrails} == {"pass"}
    assert all(row["allowed_publication_sentence"] for row in guardrails)
    assert all(row["citation_gate"] for row in guardrails)
    assert all(row["overclaim_blocked"] for row in guardrails)
    assert all(row["non_specialist_explanation"] for row in guardrails)
    contribution_rows = payload["contribution_finding_rows"]
    assert len(contribution_rows) == 6
    assert {row["contribution_or_finding"] for row in contribution_rows} == {
        "Audited regression-CP experiment scope",
        "Practical candidate pattern",
        "Venn-Abers bridge negative evidence",
        "Closed positive claims are part of the result",
        "Traceability and reproducibility surface",
        "Publication package architecture",
    }
    assert all(row["reader_safe_statement"] for row in contribution_rows)
    assert all(row["evidence_anchor"] for row in contribution_rows)
    assert all(row["closed_reading"] for row in contribution_rows)
    scientific_rows = payload["scientific_method_rows"]
    assert len(scientific_rows) == 6
    assert {row["stage"] for row in scientific_rows} == {
        "Question and empirical object",
        "Measurement protocol",
        "Candidate-method comparison",
        "Falsification and negative evidence",
        "Closed positive-claim gates",
        "Reproducibility and traceability",
    }
    assert all(row["reader_question"] for row in scientific_rows)
    assert all(row["evidence_anchor"] for row in scientific_rows)
    assert all(row["scientific_boundary"] for row in scientific_rows)
    guarantee_rows = payload["guarantee_boundary_rows"]
    assert len(guarantee_rows) == 5
    assert {row["topic"] for row in guarantee_rows} == {
        "Marginal conformal coverage",
        "Empirical coverage in this study",
        "Conditional and group behavior",
        "Efficiency and frontier evidence",
        "Venn-Abers regression bridge",
    }
    assert all(row["reader_safe_statement"] for row in guarantee_rows)
    assert all(row["required_condition_or_evidence"] for row in guarantee_rows)
    assert all(row["closed_reading"].startswith("Do not ") for row in guarantee_rows)
    question_rows = payload["research_question_rows"]
    assert len(question_rows) == 5
    assert {row["research_question"] for row in question_rows} == {
        "What empirical object does this Research Document evaluate?",
        "Which conformal approaches looked practically useful in the audited experiments?",
        "What was learned from the evaluated Venn-Abers regression bridge?",
        "Which stronger scientific claims remain closed?",
        "How can a reviewer audit or navigate the evidence?",
    }
    assert all(row["short_answer"] for row in question_rows)
    assert all(row["evidence_anchor"] for row in question_rows)
    assert all(row["closed_reading"].startswith("Do not ") for row in question_rows)
    concept_rows = payload["citation_backed_concept_rows"]
    assert len(concept_rows) == 8
    assert {row["concept"] for row in concept_rows} == {
        "Regression conformal prediction",
        "`1 - alpha` and `alpha`",
        "Calibration data and conformity scores",
        "Conformalized Quantile Regression (CQR)",
        "CV+ and jackknife-style resampling",
        "Group and Mondrian diagnostics",
        "Venn-Abers predictive distributions",
        "Claim gates and release gates",
    }
    assert all(row["reader_question"] for row in concept_rows)
    assert all(row["literature_basis"] for row in concept_rows)
    assert all(row["experiment_anchor"] for row in concept_rows)
    assert all(row["closed_reading"].startswith("Do not ") for row in concept_rows)
    assert all(row["citation_keys"] for row in concept_rows)
    venn_row = next(
        row
        for row in concept_rows
        if row["concept"] == "Venn-Abers predictive distributions"
    )
    assert {
        "nouretdinov2018ivapd",
        "nouretdinov2024ivapd_applications",
        "vanderlaan2025generalized_venn_abers",
        "petej2026inductive_venn_abers_regressors",
    }.issubset(set(venn_row["citation_keys"]))
    ladder_rows = payload["result_interpretation_ladder_rows"]
    assert len(ladder_rows) == 6
    assert {row["evidence_layer"] for row in ladder_rows} == {
        "Nominal target",
        "Observed aggregate coverage",
        "Coverage-width trade-off",
        "Robustness retention",
        "Negative bridge evidence",
        "Closed gates",
    }
    assert all(row["what_it_can_support"] for row in ladder_rows)
    assert all(row["evidence_in_this_study"] for row in ladder_rows)
    assert all(row["what_it_cannot_support"] for row in ladder_rows)
    assert all(row["reader_action"] for row in ladder_rows)
    assert any(
        "CQR/CV+ as strong practical candidates observed in these experiments"
        in row["reader_action"]
        for row in ladder_rows
    )
    assert any(
        "cannot reject predictive-distribution or generalized Venn-Abers"
        in row["what_it_cannot_support"]
        for row in ladder_rows
    )
    assert any(
        "Treat closed gates as scientific results and release boundaries"
        in row["reader_action"]
        for row in ladder_rows
    )


def test_research_document_markdown_contains_required_reader_surface():
    document = DOCUMENT.read_text(encoding="utf-8")

    for heading in [
        "# Research Document",
        "## Regression Conformal Prediction Under Neutral Claim Boundaries",
        "## Abstract",
        "## Executive Synthesis",
        "## Plain-Language Summary",
        "## Research Questions And Answers",
        "## Contribution And Finding Map",
        "## Scientific Method Audit Trail",
        "## Private Review Decision Protocol",
        "## 1. Reader Primer",
        "### Citation-Backed Concept Map",
        "### Terminology Compass",
        "### How To Interpret `1 - alpha`",
        "### Guarantee Boundary Ledger",
        "### Method Mechanics At A Glance",
        "## Publication Design Basis",
        "## 2. Experimental Scope",
        "## 3. Observed Method Behavior",
        "### Result Reading Guide",
        "### Evidence-To-Claim Interpretation Ladder",
        "### Claim Language Guardrails",
        "## 4. Negative And Closed Claims",
        "## 5. Knowledge Graph And Reproducibility",
        "## 6. How To Read The Artifact Set",
        "## 7. Publication Boundary",
        "## References",
        "## Source Artifacts",
    ]:
        assert heading in document

    assert "Author: Emre Tasar, Data Scientist" in document
    assert "Email: detasar@gmail.com" in document
    assert "research questions, the answer currently supported by the evidence" in document
    assert "What empirical object does this Research Document evaluate?" in document
    assert "Which conformal approaches looked practically useful" in document
    assert "How can a reviewer audit or navigate the evidence?" in document
    assert "CQR/CV+ were observed as strong practical candidates" in document
    assert "Read this document in four layers" in document
    assert "| Reading layer | Reader question | Safe reading | Boundary |" in document
    assert "This synthesis states the document's position before the detailed tables" in document
    assert "### What this document is" in document
    assert "### What the evidence supports" in document
    assert "### What the evidence does not support" in document
    assert "### Which claims remain closed" in document
    assert "### How a reviewer should inspect it" in document
    assert "The unit of evidence is therefore an audited result surface" in document
    assert "These zeros are not gaps to hide; they are part of the scientific result" in document
    assert "Boundary: Do not turn observed practical-candidate evidence" in document
    assert "shortest reader-safe interpretation before the technical tables" in document
    assert "| Reader question | Plain-language answer | Evidence anchor | Boundary |" in document
    assert "This is an audited measurement record for regression conformal prediction" in document
    assert "CQR/CV+ looked practically useful in these experiments" in document
    assert "`1 - alpha` is the target coverage level; observed coverage still has to be measured" in document
    assert "Do not cite, publish, or deploy the KG/site before explicit public release authorization" in document
    assert "Empirical object" in document
    assert "Observed pattern" in document
    assert "Negative evidence" in document
    assert "Traceability and release" in document
    assert "Do not cite, publish, or make the repository public before the explicit release gate opens" in document
    assert "This map states the document's contribution and core empirical findings" in document
    assert "This table rewrites the study as a scientific-method chain" in document
    assert "Question and empirical object" in document
    assert "Measurement protocol" in document
    assert "Candidate-method comparison" in document
    assert "Falsification and negative evidence" in document
    assert "Closed positive-claim gates" in document
    assert "Reproducibility and traceability" in document
    assert "Scope size is audit evidence, not proof of exhaustive internet coverage" in document
    assert "prose cannot convert it into bounded-support validity or population fairness" in document
    assert "what a private reviewer may accept at this stage" in document
    assert "| Decision point | Accept private review if | Evidence to check | Still closed |" in document
    assert "Private review readability" in document
    assert "Empirical result wording" in document
    assert "Venn-Abers negative evidence" in document
    assert "KG and site publication" in document
    assert "No public KG citation, GitHub Pages deployment, public site" in document
    assert "Audited regression-CP experiment scope" in document
    assert "Practical candidate pattern" in document
    assert "Closed positive claims are part of the result" in document
    assert "Traceability and reproducibility surface" in document
    assert "This is not a final selected method, global superiority claim, or recommendation" in document
    assert "This does not yet make the KG a public citable component" in document
    assert "target coverage level, not an observed success rate" in document
    assert "which parts are conformal prediction background" in document
    assert "Regression conformal prediction" in document
    assert "Calibration data and conformity scores" in document
    assert "Group and Mondrian diagnostics" in document
    assert "Claim gates and release gates" in document
    assert "which parts are governance boundaries" in document
    assert "the conformal prediction theorem layer, the empirical audit layer" in document
    assert "marginal coverage statement for future exchangeable draws" in document
    assert "Do not read marginal coverage as conditional, subgroup, endpoint" in document
    assert "Do not state that fairness is solved" in document
    assert "Do not reject the broader Venn-Abers literature" in document
    assert "The table below explains how each method family creates or adjusts prediction intervals" in document
    assert "Split conformal regression" in document
    assert "Quantile-model quality" in document
    assert "CV+ / jackknife-style methods" in document
    assert "Mondrian calibration" in document
    assert "The result tables combine several diagnostic quantities" in document
    assert "The ladder below connects each result type to the strongest claim" in document
    assert "| Evidence layer | What it can support | Evidence in this study | What it cannot support | Reader action |" in document
    assert "Nominal target" in document
    assert "Observed aggregate coverage" in document
    assert "Coverage-width trade-off" in document
    assert "Robustness retention" in document
    assert "Negative bridge evidence" in document
    assert "Closed gates" in document
    assert "cannot be promoted to a universal best-method claim" in document
    assert "Report the bridge result as negative evidence exactly at the evaluated bridge scope" in document
    assert "Closed gates cannot be reopened by optimistic prose" in document
    assert "writing controls derived from the claim/evidence verification matrix" in document
    assert "The current evidence does not authorize a final selected method" in document
    assert "bridge-specific negative evidence" in document
    assert "broader Venn-Abers literature" in document
    assert "This row tells a reader how the work can be audited and resumed" in document
    assert "`row-weighted coverage mean`" in document
    assert "`undercoverage run`" in document
    assert "Closed gates can be revised only by later evidence" in document
    assert "source-backed review of comparable conformal prediction papers" in document
    assert "Use a minimal main article and a broad supplementary document" in document
    assert "Make the README a review router" in document
    assert "It does not add experiments and does not recommend a conformal method" in document
    assert "frontier count is descriptive evidence, not a final-selection claim" in document
    assert "does not reject an entire research family" in document
    assert "did not behave as the expected strong regression solution" in document
    assert "They are not method recommendations" in document
    assert "### Audit Controls" in document
    assert "Cross-run leakage status" in document
    assert "Bootstrap selection counts are cqr=1,000" in document
    assert "site/kg_browser.html" in document
    assert "edge selector provenance coverage" in document
    assert "How To Read The Artifact Set" in document
    assert "No new experiments are authorized or required" in document
    assert "not a public release" in document
    assert "not yet a public citable component" in document
    assert "production recommendation" in document
    assert "best regression conformal method" not in document.lower()


def test_research_document_uses_registered_citations():
    payload = load_artifact()
    document = DOCUMENT.read_text(encoding="utf-8")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registered = {row["citation_key"] for row in registry["citation_rows"]}
    cited = set(re.findall(r"\[@([A-Za-z0-9_]+)", document))
    cited.update(re.findall(r"; @([A-Za-z0-9_]+)", document))
    cited.update(re.findall(r"`@([A-Za-z0-9_]+)`", document))

    assert cited
    assert cited.issubset(registered)
    for required_key in [
        "lei2017distribution_free_regression",
        "romano2019conformalized_quantile_regression",
        "barber2020jackknife_plus",
        "kim2020jackknife_after_bootstrap",
        "nouretdinov2018ivapd",
        "nouretdinov2024ivapd_applications",
        "vanderlaan2025generalized_venn_abers",
        "petej2026inductive_venn_abers_regressors",
    ]:
        assert required_key in cited
        assert required_key in payload["citation_keys"].values()


def test_research_document_rebuild_is_stable():
    payload = build_research_document.build_payload(ROOT)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == "research_document_private_authoring_ready"
    assert payload["summary"]["failed_check_count"] == 0
    assert checks["source_artifacts_present"]["status"] == "pass"
    assert checks["authoring_decision_allows_private_research_document"]["status"] == "pass"
    assert checks["required_citations_registered"]["status"] == "pass"
    assert checks["claim_boundaries_closed"]["status"] == "pass"
    assert checks["kg_traceability_available"]["status"] == "pass"
    assert checks["publication_exemplar_review_ready"]["status"] == "pass"
    assert checks["private_review_package_supports_document_navigation"]["status"] == "pass"
    assert checks["claim_language_guardrails_complete"]["status"] == "pass"
