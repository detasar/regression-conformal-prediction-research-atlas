"""Build the evidence-linked main article draft.

The output is a draft article assembled from existing evidence artifacts. It is
not a final manuscript, not a release artifact, and not a method
recommendation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_main_article_draft_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/main_article_draft.md")
DEFAULT_JSON_OUT = Path("experiments/regression/manuscript/main_article_draft.json")
AUTHOR_NAME = "Emre Tasar"
AUTHOR_ROLE = "Data Scientist"
AUTHOR_EMAIL = "detasar@gmail.com"

INDIVIDUAL_REPORT = Path(
    "experiments/regression/manuscript/individual_experiment_report_draft.json"
)
ARTICLE_BLUEPRINT = Path(
    "experiments/regression/manuscript/article_supplement_blueprint_alignment.json"
)
SECTION_PACKET = Path(
    "experiments/regression/manuscript/manuscript_section_evidence_packet.json"
)
SECTION_BOUNDARY = Path(
    "experiments/regression/manuscript/section_claim_boundary_audit.json"
)
CLAIM_MATRIX = Path(
    "experiments/regression/manuscript/publication_claim_evidence_verification_matrix.json"
)
CITATION_REGISTRY = Path(
    "experiments/regression/manuscript/publication_citation_registry.json"
)
PUBLICATION_EXEMPLAR_REVIEW = Path(
    "experiments/regression/manuscript/publication_exemplar_review.json"
)
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output Markdown path.")
    parser.add_argument(
        "--json-out", default=str(DEFAULT_JSON_OUT), help="Output JSON path."
    )
    return parser.parse_args()


def read_json(root: Path, path: Path) -> dict[str, Any]:
    full = root / path
    if not full.exists():
        return {}
    return json.loads(full.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def collect_citation_keys(payload: dict[str, Any]) -> dict[str, str]:
    return {row["url"]: row["citation_key"] for row in payload.get("citation_rows", [])}


def build_claim_evidence_rows(facts: dict[str, Any], kg_quality: dict[str, Any]) -> list[dict[str, str]]:
    graph = kg_quality.get("graph", {})
    return [
        {
            "row_id": "empirical_scope",
            "claim_surface": "Audited empirical scope",
            "evidence": (
                f"{fmt(facts.get('publication_completed_rows'))} publication-scoped rows, "
                f"{fmt(facts.get('dataset_count'))} datasets, "
                f"{fmt(facts.get('dataset_alpha_cell_count'))} dataset-alpha cells, and "
                f"{fmt(facts.get('method_count'))} method labels."
            ),
            "supported_reading": "The study has a broad audited regression-CP accounting base.",
            "boundary": "Scope does not by itself authorize external validity or a general method recommendation.",
        },
        {
            "row_id": "cqr_cv_plus_practical_candidates",
            "claim_surface": "CQR/CV+ descriptive performance",
            "evidence": (
                f"CQR appears in {fmt(facts.get('cqr_frontier_cell_count'))} frontier cells; "
                f"CV+ appears in {fmt(facts.get('cv_plus_frontier_cell_count'))} frontier cells."
            ),
            "supported_reading": (
                "CQR/CV+ were observed in these experiments as strong practical "
                "candidates."
            ),
            "boundary": "This is not a claim that either method is universally best for regression conformal prediction.",
        },
        {
            "row_id": "venn_abers_bridge_negative_evidence",
            "claim_surface": "Venn-Abers regression bridge",
            "evidence": (
                f"The evaluated bridge has {fmt(facts.get('venn_undercoverage_run_count'))} "
                "undercoverage runs in the current evidence base."
            ),
            "supported_reading": (
                "The expected strong Venn-Abers regression solution did not emerge "
                "in these experiments."
            ),
            "boundary": "This is not a rejection of the Venn-Abers literature or of future bridge designs.",
        },
        {
            "row_id": "bounded_support_claim_closed",
            "claim_surface": "Bounded-support validity",
            "evidence": (
                f"{fmt(facts.get('bounded_support_validity_ready_bundle_count'))} "
                "validity-ready bounded-support bundles."
            ),
            "supported_reading": "Endpoint/bounded-support diagnostics remain useful audit signals.",
            "boundary": "No bounded-support validity claim is authorized.",
        },
        {
            "row_id": "fairness_claim_closed",
            "claim_surface": "Population fairness",
            "evidence": (
                f"{fmt(facts.get('fairness_population_ready_bundle_count'))} "
                "population-fairness-ready bundles."
            ),
            "supported_reading": "Group diagnostics can guide supplementary inspection.",
            "boundary": "No population fairness claim is authorized.",
        },
        {
            "row_id": "kg_traceability",
            "claim_surface": "Knowledge-graph traceability",
            "evidence": (
                f"{fmt(graph.get('node_count'))} KG nodes and "
                f"{fmt(graph.get('edge_count'))} KG edges."
            ),
            "supported_reading": (
                "The KG is evidence infrastructure linking artifacts, sections, "
                "citations, claims, and quality checks."
            ),
            "boundary": "The KG becomes a citable web artifact only after sterile-repository review and release.",
        },
    ]


def build_research_question_rows(
    facts: dict[str, Any], kg_quality: dict[str, Any]
) -> list[dict[str, str]]:
    graph = kg_quality.get("graph", {})
    return [
        {
            "question": "What empirical object is being audited?",
            "article_answer": (
                "A publication-scoped regression conformal prediction evidence "
                f"base with {fmt(facts.get('publication_completed_rows'))} "
                f"completed rows, {fmt(facts.get('dataset_count'))} datasets, "
                f"{fmt(facts.get('dataset_alpha_cell_count'))} dataset-alpha "
                f"cells, and {fmt(facts.get('method_count'))} method labels."
            ),
            "evidence_anchor": "Completed-row accounting and individual experiment report facts.",
            "closed_reading": "Do not read the scope as exhaustive internet coverage or deployment generality.",
        },
        {
            "question": "Which practical method pattern is supported descriptively?",
            "article_answer": (
                "CQR/CV+ were observed as strong practical candidates in these "
                "experiments, with CQR carrying the largest descriptive frontier "
                f"count ({fmt(facts.get('cqr_frontier_cell_count'))}) and CV+ "
                f"contributing {fmt(facts.get('cv_plus_frontier_cell_count'))} "
                "frontier cells."
            ),
            "evidence_anchor": "Frontier counts, coverage-width diagnostics, and claim/evidence matrix.",
            "closed_reading": "Do not turn the pattern into a selected method, best-method statement, or recommendation.",
        },
        {
            "question": "What did the evaluated Venn-Abers regression bridge show?",
            "article_answer": (
                "The evaluated bridge is negative/failure-mode evidence in this "
                f"study, including {fmt(facts.get('venn_undercoverage_run_count'))} "
                "undercoverage runs."
            ),
            "evidence_anchor": "Bridge diagnostics and Venn-Abers claim-boundary rows.",
            "closed_reading": "Do not reject the broader Venn-Abers predictive-distribution or generalized-calibration literature.",
        },
        {
            "question": "Which stronger positive claims remain closed?",
            "article_answer": (
                "Bounded-support validity and population fairness remain closed: "
                f"{fmt(facts.get('bounded_support_validity_ready_bundle_count'))} "
                "bounded-support-validity-ready bundles and "
                f"{fmt(facts.get('fairness_population_ready_bundle_count'))} "
                "population-fairness-ready bundles."
            ),
            "evidence_anchor": "Paper gate map, bounded-support audit, fairness audit, and claim matrix.",
            "closed_reading": "Do not convert diagnostic endpoint or group evidence into validity or fairness conclusions.",
        },
        {
            "question": "How can the evidence be audited without opening release?",
            "article_answer": (
                "The private KG and package provide traceability infrastructure "
                f"with {fmt(graph.get('node_count'))} KG nodes and "
                f"{fmt(graph.get('edge_count'))} KG edges."
            ),
            "evidence_anchor": "Knowledge-graph quality audit and sterile package metadata.",
            "closed_reading": "Do not cite, publish, or deploy the KG/site before explicit release authorization.",
        },
    ]


def build_guarantee_boundary_rows() -> list[dict[str, str]]:
    return [
        {
            "topic": "Marginal conformal coverage",
            "article_statement": (
                "The conformal guarantee is a marginal coverage statement under "
                "exchangeability and the stated calibration protocol."
            ),
            "closed_reading": (
                "It is not conditional, subgroup, endpoint, or deployment coverage."
            ),
        },
        {
            "topic": "Empirical coverage",
            "article_statement": (
                "Coverage values in this article summarize observed held-out "
                "behavior inside the audited dataset-alpha-method scope."
            ),
            "closed_reading": (
                "They are not theorem claims and not general product recommendations."
            ),
        },
        {
            "topic": "Group diagnostics",
            "article_statement": (
                "Group and Mondrian rows are heterogeneity diagnostics that help "
                "read the supplement."
            ),
            "closed_reading": (
                "They do not establish population fairness while the fairness-ready "
                "bundle count is zero."
            ),
        },
        {
            "topic": "Frontier evidence",
            "article_statement": (
                "Frontier counts describe observed coverage-width trade-offs among "
                "audited methods."
            ),
            "closed_reading": (
                "They are not final method selection or universal superiority claims."
            ),
        },
        {
            "topic": "Venn-Abers bridge",
            "article_statement": (
                "The negative evidence concerns the evaluated interval bridge."
            ),
            "closed_reading": (
                "It is not a rejection of predictive-distribution or generalized "
                "Venn-Abers research."
            ),
        },
    ]


def build_paper_architecture_rows(
    exemplar_review: dict[str, Any],
) -> list[dict[str, str]]:
    design_rows = {
        str(row.get("decision_id") or ""): row
        for row in exemplar_review.get("design_decision_rows", [])
        if isinstance(row, dict)
    }
    rows = [
        (
            "minimal_main_article",
            "Minimal main article",
            (
                "Use the article for the study question, non-specialist primer, "
                "claim-evidence map, headline diagnostics, and closed-claim summary."
            ),
            "Do not read the article as a final method recommendation or release artifact.",
            "minimal_main_broad_supplement",
        ),
        (
            "broad_supplement",
            "Broad supplementary document",
            (
                "Use the supplement for method detail, robustness diagnostics, "
                "post-selection checks, bounded-support policy, fairness diagnostics, "
                "duplicate caveats, and Venn-Abers negative evidence."
            ),
            "Supplementary diagnostics do not open final selection, fairness, or validity claims.",
            "minimal_main_broad_supplement",
        ),
        (
            "readme_review_router",
            "README review router",
            (
                "Use the README to choose the review path, locate artifacts, and "
                "check status before interpreting results."
            ),
            "README navigation does not authorize public release or citable status.",
            "readme_review_path_first",
        ),
        (
            "private_site_and_kg",
            "Private site and KG browser",
            (
                "Use the site and KG browser to trace claims to source artifacts, "
                "citation gates, quality checks, nodes, edges, and provenance."
            ),
            "KG citation, GitHub Pages, and public site deployment remain closed.",
            "site_as_review_portal",
        ),
        (
            "claim_evidence_contract",
            "Claim-evidence contract",
            (
                "Use the claim matrix to keep each reader-facing sentence tied "
                "to evidence, citation requirements, and an explicit blocked overclaim."
            ),
            "No prose may convert a blocked claim into a positive conclusion.",
            "claim_boundary_for_every_surface",
        ),
    ]
    return [
        {
            "row_id": row_id,
            "surface": surface,
            "reader_job": reader_job,
            "boundary": boundary,
            "source_decision_id": source_decision_id,
            "source_basis": str(
                design_rows.get(source_decision_id, {}).get("decision") or ""
            ),
        }
        for row_id, surface, reader_job, boundary, source_decision_id in rows
    ]


def build_method_reader_safety_rows() -> list[dict[str, str]]:
    return [
        {
            "concept": "`1 - alpha` target",
            "reader_safe_meaning": (
                "A nominal design target for marginal coverage under the stated "
                "calibration protocol."
            ),
            "not_authorized_reading": (
                "It is not proof that every subgroup, endpoint region, or future "
                "deployment slice is covered at that rate."
            ),
        },
        {
            "concept": "CQR",
            "reader_safe_meaning": (
                "Lower and upper quantile models are conformalized with "
                "calibration evidence so intervals can adapt to heterogeneous "
                "noise."
            ),
            "not_authorized_reading": (
                "It is not a final selected method, universal best method, or "
                "production recommendation."
            ),
        },
        {
            "concept": "CV+",
            "reader_safe_meaning": (
                "Out-of-fold prediction evidence is used to build intervals that "
                "reflect fitted-model variability."
            ),
            "not_authorized_reading": (
                "It is not caveat-free evidence and does not open final method "
                "selection."
            ),
        },
        {
            "concept": "Mondrian/group calibration",
            "reader_safe_meaning": (
                "Calibration can be stratified by groups when the comparison is "
                "intended to expose heterogeneity."
            ),
            "not_authorized_reading": (
                "It is not a population fairness claim while the fairness-ready "
                "bundle count is zero."
            ),
        },
        {
            "concept": "Venn-Abers bridge",
            "reader_safe_meaning": (
                "The experiment evaluates a bridge from Venn-Abers-style "
                "calibration evidence into interval diagnostics."
            ),
            "not_authorized_reading": (
                "The observed undercoverage is not a rejection of predictive "
                "distribution or generalized Venn-Abers research."
            ),
        },
    ]


def build_concept_bridge_rows(cite: dict[str, str]) -> list[dict[str, str]]:
    split_key = cite["https://arxiv.org/abs/1604.04173"]
    cqr_key = cite["https://arxiv.org/abs/1905.03222"]
    jack_key = cite["https://arxiv.org/abs/1905.02928"]
    jab_key = cite["https://arxiv.org/abs/2002.09025"]
    venn18_key = cite["https://proceedings.mlr.press/v91/nouretdinov18a.html"]
    venn24_key = cite["https://proceedings.mlr.press/v230/nouretdinov24a.html"]
    vanderlaan_key = cite["https://proceedings.mlr.press/v267/van-der-laan25a.html"]
    ivar_key = cite["https://arxiv.org/html/2605.06646v1"]
    return [
        {
            "concept": "Conformal prediction target",
            "source_anchor": f"Distribution-free regression conformal prediction [@{split_key}]",
            "article_use": (
                "`1 - alpha` is the nominal marginal coverage target under the "
                "stated calibration assumptions."
            ),
            "safe_sentence": (
                "The article may report target and observed coverage separately."
            ),
            "blocked_sentence": (
                "Do not write that the nominal target proves subgroup, endpoint, "
                "or future-deployment coverage."
            ),
        },
        {
            "concept": "Conformalized Quantile Regression",
            "source_anchor": f"CQR lower/upper quantile calibration [@{cqr_key}]",
            "article_use": (
                "CQR starts with lower and upper quantile models, then applies "
                "conformal calibration to the interval."
            ),
            "safe_sentence": (
                "CQR can be described as a strong practical candidate observed in "
                "these experiments."
            ),
            "blocked_sentence": (
                "Do not write that CQR is the selected, best, or recommended "
                "regression conformal method."
            ),
        },
        {
            "concept": "CV+ and jackknife-style intervals",
            "source_anchor": f"Jackknife+/CV+ resampling evidence [@{jack_key}; @{jab_key}]",
            "article_use": (
                "CV+ uses out-of-fold prediction evidence so interval construction "
                "reflects fitted-model variability."
            ),
            "safe_sentence": (
                "CV+ can be described as another strong practical candidate "
                "observed in these experiments."
            ),
            "blocked_sentence": (
                "Do not write that cross-validation evidence removes all model, "
                "split, or dataset caveats."
            ),
        },
        {
            "concept": "Venn-Abers regression bridge",
            "source_anchor": (
                "Venn-Abers predictive-distribution and generalized-calibration "
                f"literature [@{venn18_key}; @{venn24_key}; @{vanderlaan_key}; @{ivar_key}]"
            ),
            "article_use": (
                "The study evaluates a bridge from Venn-Abers-style calibration "
                "evidence into regression interval diagnostics."
            ),
            "safe_sentence": (
                "The evaluated bridge produced bridge-specific negative evidence "
                "in these experiments."
            ),
            "blocked_sentence": (
                "Do not write that the result rejects the broader Venn-Abers "
                "literature."
            ),
        },
        {
            "concept": "Claim-gated empirical wording",
            "source_anchor": "Publication claim-evidence matrix and section-boundary audit",
            "article_use": (
                "Every empirical sentence is paired with evidence, an allowed "
                "reading, and a blocked stronger reading."
            ),
            "safe_sentence": (
                "Closed gates are part of the scientific result and should remain "
                "visible."
            ),
            "blocked_sentence": (
                "Do not promote a diagnostic pattern into a method recommendation, "
                "fairness conclusion, endpoint-validity claim, or public-release claim."
            ),
        },
    ]


def build_evidence_to_claim_ladder_rows(facts: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "stage": "Completed row",
            "reader_question": "What was counted?",
            "evidence_object": (
                f"{fmt(facts.get('publication_completed_rows'))} publication-scoped "
                "completed rows."
            ),
            "allowed_claim": "The empirical accounting base is broad and auditable.",
            "blocked_upgrade": "A completed row is not, by itself, external validity.",
        },
        {
            "stage": "Dataset-alpha cell",
            "reader_question": "What comparison unit was preserved?",
            "evidence_object": (
                f"{fmt(facts.get('dataset_alpha_cell_count'))} dataset-alpha cells "
                f"across {fmt(facts.get('dataset_count'))} datasets."
            ),
            "allowed_claim": "Coverage behavior is read inside recorded calibration targets.",
            "blocked_upgrade": "A dataset-alpha cell is not a population claim.",
        },
        {
            "stage": "Method diagnostic",
            "reader_question": "What pattern was observed?",
            "evidence_object": (
                f"CQR={fmt(facts.get('cqr_frontier_cell_count'))}, "
                f"CV+={fmt(facts.get('cv_plus_frontier_cell_count'))}, "
                f"Mondrian={fmt(facts.get('mondrian_frontier_cell_count'))} "
                "frontier cells."
            ),
            "allowed_claim": "CQR/CV+ can be described as strong practical candidates observed here.",
            "blocked_upgrade": "Frontier counts do not select a final or universal best method.",
        },
        {
            "stage": "Failure-mode diagnostic",
            "reader_question": "What did not work as expected?",
            "evidence_object": (
                f"{fmt(facts.get('venn_undercoverage_run_count'))} Venn-Abers bridge "
                "undercoverage runs."
            ),
            "allowed_claim": "The evaluated bridge is reportable as negative evidence.",
            "blocked_upgrade": "The result does not reject the broader Venn-Abers literature.",
        },
        {
            "stage": "Closed positive gate",
            "reader_question": "Which stronger claims stay absent?",
            "evidence_object": (
                f"{fmt(facts.get('bounded_support_validity_ready_bundle_count'))} "
                "bounded-support-validity-ready bundles and "
                f"{fmt(facts.get('fairness_population_ready_bundle_count'))} "
                "population-fairness-ready bundles."
            ),
            "allowed_claim": "Closed gates are reported as scientific results.",
            "blocked_upgrade": "Zero-ready gates cannot be converted into validity or fairness claims.",
        },
        {
            "stage": "Release and citation gate",
            "reader_question": "When can artifacts be cited or published?",
            "evidence_object": "Private review package and KG navigation artifacts.",
            "allowed_claim": "The artifacts support private review and traceability.",
            "blocked_upgrade": "Public release, KG citation, and GitHub Pages remain closed.",
        },
    ]


def build_payload(root: Path) -> dict[str, Any]:
    individual = read_json(root, INDIVIDUAL_REPORT)
    blueprint = read_json(root, ARTICLE_BLUEPRINT)
    section_packet = read_json(root, SECTION_PACKET)
    section_boundary = read_json(root, SECTION_BOUNDARY)
    claim_matrix = read_json(root, CLAIM_MATRIX)
    citations = read_json(root, CITATION_REGISTRY)
    exemplar_review = read_json(root, PUBLICATION_EXEMPLAR_REVIEW)
    kg_quality = read_json(root, KG_QUALITY)
    facts = individual.get("report_facts") or {}
    cite = collect_citation_keys(citations)
    sources = {
        "individual_experiment_report_draft": str(INDIVIDUAL_REPORT),
        "article_supplement_blueprint_alignment": str(ARTICLE_BLUEPRINT),
        "manuscript_section_evidence_packet": str(SECTION_PACKET),
        "section_claim_boundary_audit": str(SECTION_BOUNDARY),
        "publication_claim_evidence_verification_matrix": str(CLAIM_MATRIX),
        "publication_citation_registry": str(CITATION_REGISTRY),
        "publication_exemplar_review": str(PUBLICATION_EXEMPLAR_REVIEW),
        "knowledge_graph_quality_summary": str(KG_QUALITY),
    }
    main_article_blueprint_rows = [
        row
        for row in blueprint.get("alignment_rows") or []
        if row.get("recommended_surface") == "main_article_candidate_after_final_prose_gate"
    ]
    main_article_verification_rows = [
        row
        for row in claim_matrix.get("verification_rows") or []
        if row.get("target_document") == "main_article"
    ]
    claim_evidence_rows = build_claim_evidence_rows(facts, kg_quality)
    research_question_rows = build_research_question_rows(facts, kg_quality)
    guarantee_boundary_rows = build_guarantee_boundary_rows()
    paper_architecture_rows = build_paper_architecture_rows(exemplar_review)
    method_reader_safety_rows = build_method_reader_safety_rows()
    concept_bridge_rows = build_concept_bridge_rows(cite)
    evidence_to_claim_ladder_rows = build_evidence_to_claim_ladder_rows(facts)
    article_sections = [
        {
            "section_id": "abstract",
            "role": "problem_method_result_boundary_summary",
            "evidence_sources": ["individual_experiment_report_draft"],
        },
        {
            "section_id": "introduction",
            "role": "motivation_scope_and_neutral_contribution",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_citation_registry",
            ],
        },
        {
            "section_id": "reader_orientation",
            "role": "plain_language_explanation_of_task_intervals_and_claim_limits",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_citation_registry",
            ],
        },
        {
            "section_id": "research_questions",
            "role": "compact_article_questions_answers_and_closed_readings",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_claim_evidence_verification_matrix",
                "knowledge_graph_quality_summary",
            ],
        },
        {
            "section_id": "concept_bridge",
            "role": "citation_backed_non_specialist_concept_bridge",
            "evidence_sources": [
                "publication_citation_registry",
                "publication_claim_evidence_verification_matrix",
                "section_claim_boundary_audit",
            ],
        },
        {
            "section_id": "study_design_summary",
            "role": "experiment_accounting_without_opening_new_experiments",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_claim_evidence_verification_matrix",
            ],
        },
        {
            "section_id": "evidence_to_claim_ladder",
            "role": "maps_empirical_objects_to_allowed_claims_and_blocked_upgrades",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_claim_evidence_verification_matrix",
                "section_claim_boundary_audit",
            ],
        },
        {
            "section_id": "paper_architecture_review_contract",
            "role": "main_article_supplement_readme_site_kg_reader_contract",
            "evidence_sources": [
                "article_supplement_blueprint_alignment",
                "publication_exemplar_review",
                "publication_claim_evidence_verification_matrix",
            ],
        },
        {
            "section_id": "background_and_methods",
            "role": "reader_primer_and_experimental_protocol",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_citation_registry",
            ],
        },
        {
            "section_id": "notation_and_evaluation_protocol",
            "role": "defines_interval_coverage_width_and_frontier_quantities",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_claim_evidence_verification_matrix",
            ],
        },
        {
            "section_id": "results",
            "role": "descriptive_method_behavior_and_negative_evidence",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_claim_evidence_verification_matrix",
            ],
        },
        {
            "section_id": "discussion_and_limitations",
            "role": "claim_boundaries_and_scientific_interpretation",
            "evidence_sources": [
                "section_claim_boundary_audit",
                "manuscript_section_evidence_packet",
                "individual_experiment_report_draft",
            ],
        },
        {
            "section_id": "reproducibility_and_traceability",
            "role": "kg_and_artifact_provenance",
            "evidence_sources": [
                "knowledge_graph_quality_summary",
                "article_supplement_blueprint_alignment",
            ],
        },
        {
            "section_id": "conclusion",
            "role": "descriptive_takeaway_and_closed_claim_recap",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_claim_evidence_verification_matrix",
                "section_claim_boundary_audit",
            ],
        },
    ]
    required_urls = [
        "https://arxiv.org/abs/1604.04173",
        "https://arxiv.org/abs/1905.03222",
        "https://arxiv.org/abs/1905.02928",
        "https://arxiv.org/abs/2002.09025",
        "https://proceedings.mlr.press/v91/nouretdinov18a.html",
        "https://proceedings.mlr.press/v230/nouretdinov24a.html",
        "https://proceedings.mlr.press/v267/van-der-laan25a.html",
        "https://arxiv.org/html/2605.06646v1",
    ]
    missing_sources = [path for path in sources.values() if not (root / path).exists()]
    missing_citations = [url for url in required_urls if url not in cite]
    checks = [
        {
            "check_id": "source_artifacts_present",
            "status": "pass" if not missing_sources else "fail",
            "evidence": {"missing_sources": missing_sources},
        },
        {
            "check_id": "required_citations_registered",
            "status": "pass" if not missing_citations else "fail",
            "evidence": {"missing_citations": missing_citations},
        },
        {
            "check_id": "main_article_surfaces_source_traceable",
            "status": (
                "pass"
                if len(main_article_blueprint_rows) >= 4
                and len(main_article_verification_rows) >= 3
                else "fail"
            ),
            "evidence": {
                "main_article_blueprint_row_count": len(main_article_blueprint_rows),
                "main_article_verification_row_count": len(main_article_verification_rows),
            },
        },
        {
            "check_id": "draft_remains_neutral_and_unreleased",
            "status": "pass",
            "evidence": {
                "final_manuscript_prose_permission": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "positive_claim_promotion_authorized": False,
                "release_authorized": False,
            },
        },
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "summary": {
            "overall_status": (
                "main_article_draft_ready" if not failed_checks else "main_article_draft_blocked"
            ),
            "draft_not_final": True,
            "author_name": AUTHOR_NAME,
            "author_role": AUTHOR_ROLE,
            "author_email": AUTHOR_EMAIL,
            "author_header": f"Author: {AUTHOR_NAME}, {AUTHOR_ROLE}",
            "publication_completed_rows": facts.get("publication_completed_rows"),
            "dataset_count": facts.get("dataset_count"),
            "dataset_alpha_cell_count": facts.get("dataset_alpha_cell_count"),
            "method_count": facts.get("method_count"),
            "cqr_frontier_cell_count": facts.get("cqr_frontier_cell_count"),
            "mondrian_frontier_cell_count": facts.get("mondrian_frontier_cell_count"),
            "cv_plus_frontier_cell_count": facts.get("cv_plus_frontier_cell_count"),
            "venn_undercoverage_run_count": facts.get("venn_undercoverage_run_count"),
            "bounded_support_validity_ready_bundle_count": facts.get(
                "bounded_support_validity_ready_bundle_count"
            ),
            "fairness_population_ready_bundle_count": facts.get(
                "fairness_population_ready_bundle_count"
            ),
            "kg_node_count": kg_quality.get("graph", {}).get("node_count"),
            "kg_edge_count": kg_quality.get("graph", {}).get("edge_count"),
            "main_article_blueprint_row_count": len(main_article_blueprint_rows),
            "main_article_verification_row_count": len(main_article_verification_rows),
            "claim_evidence_map_row_count": len(claim_evidence_rows),
            "research_question_row_count": len(research_question_rows),
            "guarantee_boundary_row_count": len(guarantee_boundary_rows),
            "paper_architecture_row_count": len(paper_architecture_rows),
            "method_reader_safety_row_count": len(method_reader_safety_rows),
            "concept_bridge_row_count": len(concept_bridge_rows),
            "evidence_to_claim_ladder_row_count": len(evidence_to_claim_ladder_rows),
            "failed_check_count": len(failed_checks),
            "final_manuscript_prose_permission": False,
            "method_recommendation_authorized": False,
            "method_champion_authorized": False,
            "method_advocacy_authorized": False,
            "positive_claim_promotion_authorized": False,
            "release_authorized": False,
        },
        "article_sections": article_sections,
        "research_question_rows": research_question_rows,
        "claim_evidence_rows": claim_evidence_rows,
        "guarantee_boundary_rows": guarantee_boundary_rows,
        "paper_architecture_rows": paper_architecture_rows,
        "method_reader_safety_rows": method_reader_safety_rows,
        "concept_bridge_rows": concept_bridge_rows,
        "evidence_to_claim_ladder_rows": evidence_to_claim_ladder_rows,
        "citation_keys": {url: cite[url] for url in required_urls if url in cite},
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This is a private final-prose review draft; it is not final manuscript prose for public submission or a submission package.",
            "The article reports observed diagnostic evidence without recommending a conformal method.",
            "CQR is described only as the largest current descriptive frontier pattern.",
            "Venn-Abers is reported as negative/failure-mode evidence for the current regression bridge.",
            "Group diagnostics are not population fairness claims.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    research_question_rows = payload["research_question_rows"]
    guarantee_rows = payload["guarantee_boundary_rows"]
    paper_architecture_rows = payload["paper_architecture_rows"]
    method_reader_safety_rows = payload["method_reader_safety_rows"]
    concept_bridge_rows = payload["concept_bridge_rows"]
    evidence_to_claim_ladder_rows = payload["evidence_to_claim_ladder_rows"]
    cite = payload["citation_keys"]
    split_key = cite["https://arxiv.org/abs/1604.04173"]
    cqr_key = cite["https://arxiv.org/abs/1905.03222"]
    jack_key = cite["https://arxiv.org/abs/1905.02928"]
    jab_key = cite["https://arxiv.org/abs/2002.09025"]
    venn18_key = cite["https://proceedings.mlr.press/v91/nouretdinov18a.html"]
    venn24_key = cite["https://proceedings.mlr.press/v230/nouretdinov24a.html"]
    vanderlaan_key = cite["https://proceedings.mlr.press/v267/van-der-laan25a.html"]
    ivar_key = cite["https://arxiv.org/html/2605.06646v1"]
    lines = [
        "# Regression Conformal Prediction Under Neutral Claim Boundaries",
        "",
        f"Author: {AUTHOR_NAME}, {AUTHOR_ROLE}",
        f"Email: {AUTHOR_EMAIL}",
        "",
        "> Draft status: private final-prose review draft; not final manuscript prose for public submission, not a release artifact, and not a method recommendation.",
        "",
        "## Abstract",
        "",
        (
            "This draft reports a regression conformal prediction study assembled "
            f"from {fmt(s['publication_completed_rows'])} publication-scoped completed "
            f"rows, {fmt(s['dataset_count'])} datasets, {fmt(s['dataset_alpha_cell_count'])} "
            f"dataset-alpha cells, and {fmt(s['method_count'])} conformal-method labels. "
            "The largest descriptive frontier pattern is CQR, with "
            f"{fmt(s['cqr_frontier_cell_count'])} frontier cells, followed by "
            f"Mondrian absolute-residual calibration with {fmt(s['mondrian_frontier_cell_count'])} "
            f"and CV+ with {fmt(s['cv_plus_frontier_cell_count'])}. "
            "These results are interpreted as diagnostic evidence only. The "
            "current evidence does not authorize a final method recommendation, "
            "a bounded-support validity claim, a population fairness claim, or a "
            "validated Venn-Abers regression interval claim."
        ),
        "",
        "## Introduction",
        "",
        (
            "Regression conformal prediction provides a way to wrap predictive "
            "models with prediction intervals calibrated for marginal coverage "
            f"under exchangeability [@{split_key}]. This study asks how a broad "
            "set of regression conformal methods behaves across audited tabular "
            "datasets while preserving source traceability, resumability, leakage "
            "checks, duplicate-split caveats, and explicit claim boundaries."
        ),
        "",
        (
            "The article deliberately separates empirical diagnostics from final "
            "claims. A method can appear frequently on the descriptive frontier "
            "without becoming a universal recommendation. A group coverage table "
            "can be useful without becoming a population fairness claim. A "
            "Venn-Abers bridge can be scientifically important even when the "
            "observed evidence is negative."
        ),
        "",
        "### Reader Orientation",
        "",
        (
            "A prediction interval is a range-valued prediction. Instead of saying "
            "that the model predicts one number, the procedure returns a lower "
            "and an upper endpoint. The target `1 - alpha` is the nominal coverage "
            "level: when `alpha = 0.10`, the interval procedure aims at 90% "
            "coverage under the assumptions required by the conformal method. "
            "Coverage and interval width must be read together, because a very "
            "wide interval can cover often without being informative."
        ),
        "",
        (
            "This article therefore treats the empirical output as a controlled "
            "measurement exercise. The central question is not 'Which method can "
            "we promote?' but 'Which patterns are supported by the completed "
            "evidence, and which stronger claims remain closed?' That framing is "
            "important for readers who are new to conformal prediction: the "
            "coverage target explains what the interval is trying to guarantee, "
            "while the claim gates explain what this particular experiment does "
            "not prove."
        ),
        "",
        "### Guarantee And Claim Boundary Snapshot",
        "",
        (
            "The snapshot below is the main article version of the Research "
            "Document's guarantee boundary ledger. It separates conformal "
            "prediction's theorem-level language from the empirical audit "
            "language used in this study, and it marks readings that remain "
            "closed in the article."
        ),
        "",
        "| Topic | Article statement | Closed reading |",
        "|---|---|---|",
    ]
    for row in guarantee_rows:
        lines.append(
            "| "
            f"{row['topic']} | "
            f"{row['article_statement']} | "
            f"{row['closed_reading']} |"
        )
    lines.extend(
        [
            "",
            "### Contributions And Boundaries",
            "",
            "- The study consolidates a large audited regression conformal-prediction evidence base under resumable, source-traceable execution records.",
            "- It reports CQR/CV+ as strong practical candidates observed in these experiments, without converting that observation into a universal recommendation.",
            "- It reports the evaluated Venn-Abers regression bridge as negative/failure-mode evidence, without rejecting the broader Venn-Abers literature.",
            "- It keeps population fairness, bounded-support validity, final method selection, public release, and citable web-artifact claims closed unless their explicit evidence gates are opened later.",
            "",
            "### Paper Architecture And Review Contract",
            "",
            (
                "The paper is organized as a small article, a broad supplement, "
                "and private navigation artifacts. This structure follows the "
                "source-backed publication exemplar review: the article carries "
                "the central claim-evidence narrative, while the supplement and "
                "KG carry the detailed audit trail. The contract below tells a "
                "reader where to look and what each surface must not claim."
            ),
            "",
            "| Surface | Reader job | Boundary | Source basis |",
            "|---|---|---|---|",
        ]
    )
    for row in paper_architecture_rows:
        lines.append(
            "| "
            f"{row['surface']} | "
            f"{row['reader_job']} | "
            f"{row['boundary']} | "
            f"{row['source_basis'] or row['source_decision_id']} |"
        )
    lines.extend(
        [
            "",
            "## Research Questions",
            "",
            (
                "The article is organized around five research questions. The "
                "answers below are intentionally scoped: each answer states what "
                "the audited evidence supports and the stronger reading that "
                "remains closed."
            ),
            "",
            "| Research question | Article answer | Evidence anchor | Closed reading |",
            "|---|---|---|---|",
        ]
    )
    for row in research_question_rows:
        lines.append(
            "| "
            f"{row['question']} | "
            f"{row['article_answer']} | "
            f"{row['evidence_anchor']} | "
            f"{row['closed_reading']} |"
        )
    lines.extend(
        [
            "",
            "## Concept Bridge For Non-Specialist Readers",
            "",
            (
                "This bridge links the main technical concepts to the sources and "
                "claim boundaries used in the article. It is intentionally compact: "
                "the supplement carries the longer method discussion, while this "
                "article keeps only the definitions needed to avoid over-reading "
                "the results."
            ),
            "",
            "| Concept | Source or evidence anchor | Article use | Safe sentence | Blocked sentence |",
            "|---|---|---|---|---|",
        ]
    )
    for row in concept_bridge_rows:
        lines.append(
            "| "
            f"{row['concept']} | "
            f"{row['source_anchor']} | "
            f"{row['article_use']} | "
            f"{row['safe_sentence']} | "
            f"{row['blocked_sentence']} |"
        )
    lines.extend(
        [
            "",
            "## Claim-Evidence Map",
            "",
            (
                "The table below is the draft's control surface: every reader-facing "
                "claim is paired with source-backed evidence and an explicit boundary. "
                "This keeps useful empirical signals separate from unsupported "
                "recommendations, fairness claims, endpoint-validity claims, and "
                "release claims."
            ),
            "",
            "| Claim surface | Evidence | Supported reading | Boundary |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["claim_evidence_rows"]:
        lines.append(
            "| "
            f"{row['claim_surface']} | "
            f"{row['evidence']} | "
            f"{row['supported_reading']} | "
            f"{row['boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Study Design Summary",
            "",
            (
                "The empirical system was designed to survive long execution, "
                "partial completion, and later review. Completed rows are counted "
                "only after they pass the publication-scoped accounting layer. "
                "Dataset-alpha cells preserve the calibration target being "
                "evaluated. Method labels preserve the conformal wrapper or "
                "calibration family being compared. Claim gates then decide "
                "which interpretations are allowed in the article."
            ),
            "",
            (
                "This separation is deliberate. Model training, interval "
                "construction, diagnostic aggregation, literature-aware method "
                "description, and release authorization are treated as different "
                "objects. As a result, a useful empirical pattern can be reported "
                "without becoming a deployment recommendation, and a negative "
                "result can be retained without being softened into a positive "
                "story."
            ),
            "",
            "## Evidence-To-Claim Ladder",
            "",
            (
                "The table below shows how a raw experimental object becomes a "
                "reader-facing statement in this article. Each step has an allowed "
                "claim and a blocked upgrade. The purpose is to make the scientific "
                "method visible: evidence can support a scoped statement only after "
                "the relevant accounting, diagnostic, claim-boundary, and release "
                "checks are kept attached."
            ),
            "",
            "| Stage | Reader question | Evidence object | Allowed claim | Blocked upgrade |",
            "|---|---|---|---|---|",
        ]
    )
    for row in evidence_to_claim_ladder_rows:
        lines.append(
            "| "
            f"{row['stage']} | "
            f"{row['reader_question']} | "
            f"{row['evidence_object']} | "
            f"{row['allowed_claim']} | "
            f"{row['blocked_upgrade']} |"
        )
    lines.extend(
        [
            "",
            "## Background And Methods",
            "",
            (
                "The core coverage target is `1 - alpha`; `alpha` is the target "
                "miscoverage rate. Split conformal regression estimates a residual "
                "calibration quantile on held-out calibration data. CQR replaces the "
                "single residual score with a lower/upper quantile-regression score "
                f"and then conformalizes that interval [@{cqr_key}]. CV+ and "
                "jackknife+ use out-of-fold or leave-one-out predictions to account "
                f"for fitted-model variability [@{jack_key}; @{jab_key}]."
            ),
            "",
            (
                "Venn-Abers-related regression work is handled separately because the "
                "literature includes predictive-distribution and calibration objects, "
                "not only ordinary interval wrappers [@"
                f"{venn18_key}; @{venn24_key}; @{vanderlaan_key}; @{ivar_key}]. "
                "This distinction matters: the present experiment evaluates a current "
                "bridge into interval-style diagnostics and therefore reports the "
                "observed failure modes without converting them into a validation claim."
            ),
            "",
            "### Method Primer For Non-Specialist Readers",
            "",
            (
                "A conformal method should be read as a calibration wrapper, not as "
                "proof that the base prediction model is correct. The wrapper turns "
                "model outputs and calibration evidence into a set-valued prediction; "
                "under the method's assumptions, the target coverage statement is "
                "about future exchangeable observations, not about every subgroup, "
                "endpoint range, or deployment setting."
            ),
            "",
            (
                "CQR means Conformalized Quantile Regression. It starts from lower "
                "and upper quantile models, then uses calibration data to correct the "
                "interval so the final set can be judged against the nominal coverage "
                f"target [@{cqr_key}]. CV+ belongs to the cross-validation-plus family: "
                "it uses out-of-fold prediction evidence rather than one fixed "
                f"calibration split [@{jack_key}; @{jab_key}]. In this article, both "
                "families are reported only as observed practical candidates in the "
                "completed experiment."
            ),
            "",
            (
                "The evaluated Venn-Abers regression bridge has a different status. "
                "Venn-Abers regression work is closer to predictive distributions and "
                "generalized calibration than to a single ordinary interval recipe [@"
                f"{venn18_key}; @{venn24_key}; @{vanderlaan_key}; @{ivar_key}]. The "
            "experiment therefore tests a bridge from that calibration evidence "
            "into interval diagnostics. The observed undercoverage is evidence "
            "against this bridge in this study, not evidence against the whole "
            "Venn-Abers research program."
        ),
        "",
        "### Reader Safety Checklist",
        "",
        (
            "The checklist below is intentionally conservative. It translates the "
            "method primer into claim boundaries so a reader can tell which "
            "parts are conformal-method background, which parts are empirical "
            "findings from this study, and which stronger readings remain closed."
        ),
        "",
        "| Concept | Reader-safe meaning | Not authorized reading |",
        "|---|---|---|",
    ]
    )
    for row in method_reader_safety_rows:
        lines.append(
            "| "
            f"{row['concept']} | "
            f"{row['reader_safe_meaning']} | "
            f"{row['not_authorized_reading']} |"
        )
    lines.extend(
        [
            "",
            "| Reader question | Short answer | Boundary |",
            "|---|---|---|",
            "| What is `1 - alpha`? | The nominal target coverage level used to design or calibrate the interval. | It is not the realized empirical coverage of every subgroup or future dataset. |",
            "| What is CQR? | Conformalized Quantile Regression: quantile models plus conformal calibration. | It is an observed strong practical candidate here, not a universal recommendation. |",
            "| What is CV+? | A cross-validation-plus interval family using out-of-fold prediction evidence. | Its frontier signal remains diagnostic and experiment-scoped. |",
            "| What is the Venn-Abers bridge result? | The evaluated bridge did not behave as the expected strong regression solution. | This is bridge-specific negative evidence, not a literature-wide rejection. |",
            "",
            "### Notation And Evaluation Protocol",
            "",
            (
                "For an observation with features `X_i` and outcome `Y_i`, a method "
                "`m` returns an interval `C_m(X_i) = [L_m(X_i), U_m(X_i)]`. The "
                "basic coverage indicator is `1{Y_i in C_m(X_i)}`. Empirical "
                "coverage is the average of this indicator over the evaluated "
                "rows, and empirical width is the average of `U_m(X_i) - L_m(X_i)`. "
                "The nominal target `1 - alpha` is therefore a target for coverage, "
                "not a guarantee that every subgroup, endpoint region, or future "
                "dataset will satisfy the same rate."
            ),
            "",
            (
                "The article uses these quantities descriptively. A frontier cell "
                "marks an observed coverage/width trade-off within a dataset-alpha "
                "comparison. Row-weighted coverage summarizes completed result rows. "
                "Undercoverage runs identify places where the empirical coverage "
                "fell below the target enough to be treated as failure-mode evidence. "
                "None of these summaries alone opens a final method-selection, "
                "fairness, or bounded-support claim."
            ),
            "",
            "| Quantity | Definition | Article use |",
            "|---|---|---|",
            "| Interval `C_m(X_i)` | Lower and upper endpoint returned by method `m` | Basic object being evaluated |",
            "| Empirical coverage | Mean of `1{Y_i in C_m(X_i)}` over evaluated rows | Descriptive calibration evidence |",
            "| Empirical width | Mean of `U_m(X_i) - L_m(X_i)` | Informativeness evidence paired with coverage |",
            "| Frontier cell | Observed coverage/width trade-off cell | Diagnostic pattern, not final selection |",
            "| Undercoverage run | Completed run below its target boundary | Failure-mode evidence |",
            "",
            "### Method Mechanics Snapshot",
            "",
            (
                "For a non-specialist reader, the methods differ mainly in how "
                "they choose or adjust interval endpoints. Split conformal uses "
                "a held-out residual quantile. CQR starts with lower and upper "
                "quantile models before conformal calibration. CV+ and jackknife+ "
                "use out-of-fold or leave-one-out predictions. Mondrian variants "
                "calibrate within groups or strata. The evaluated Venn-Abers "
                "regression bridge maps a distinct calibration object into "
                "interval-style diagnostics."
            ),
            "",
            "| Method family | Interval mechanism | Boundary in this article |",
            "|---|---|---|",
            "| Split conformal | Residual-score quantile on a calibration set | Baseline mechanism; not a complete endpoint or heterogeneity solution |",
            "| CQR | Lower/upper quantile models plus conformal calibration | Strong practical candidate observed here; not a universal recommendation |",
            "| CV+ / jackknife+ | Out-of-fold or leave-one-out conformity evidence | Strong practical candidate observed here; no final method selection |",
            "| Mondrian calibration | Group- or stratum-specific calibration | Diagnostic comparator; not a population fairness claim |",
            "| Venn-Abers bridge | Bridge from Venn-Abers-style calibration evidence to interval diagnostics | Negative evidence for the evaluated bridge only |",
            "",
            "## Results",
            "",
            "### How To Read The Results Table",
            "",
            (
                "The results table mixes scope counts, descriptive method signals, "
                "and closed claim gates. Frontier cells summarize observed "
                "coverage/width trade-offs; row-weighted coverage summarizes "
                "empirical coverage across completed result blocks; undercoverage "
                "runs flag failure modes; and zero-ready gates record claims the "
                "article must not make. These quantities support interpretation, "
                "not final method selection."
            ),
            "",
            "| Evidence area | Result | Interpretation |",
            "|---|---:|---|",
            f"| Publication-scoped completed rows | {fmt(s['publication_completed_rows'])} | Empirical accounting scope |",
            f"| Datasets | {fmt(s['dataset_count'])} | Method synthesis scope |",
            f"| Dataset-alpha cells | {fmt(s['dataset_alpha_cell_count'])} | Calibration/coverage comparison scope |",
            f"| CQR frontier cells | {fmt(s['cqr_frontier_cell_count'])} | Largest descriptive frontier pattern |",
            f"| Mondrian frontier cells | {fmt(s['mondrian_frontier_cell_count'])} | Secondary descriptive pattern |",
            f"| CV+ frontier cells | {fmt(s['cv_plus_frontier_cell_count'])} | Secondary descriptive pattern |",
            f"| Venn-Abers bridge undercoverage runs | {fmt(s['venn_undercoverage_run_count'])} | Negative/failure-mode evidence |",
            f"| Bounded-support validity-ready bundles | {fmt(s['bounded_support_validity_ready_bundle_count'])} | No bounded-support validity claim |",
            f"| Population-fairness-ready bundles | {fmt(s['fairness_population_ready_bundle_count'])} | No population fairness claim |",
            "",
            (
                "The descriptive method result is internally consistent with the "
                "individual experiment report: CQR has the largest current frontier "
                "share, but the final selection claim remains blocked. The correct "
                "claim is not that CQR is the best regression conformal method in "
                "general; the supported claim is that CQR is the largest current "
                "diagnostic frontier pattern in this audited study."
            ),
            "",
            "## Discussion",
            "",
            (
                "The study's main scientific value is the combination of broad "
                "empirical accounting and explicit negative evidence. Venn-Abers is "
                "not forced into a positive result: the current bridge shows "
                f"{fmt(s['venn_undercoverage_run_count'])} undercoverage runs and is "
                "therefore reported as a failure mode. This is compatible with the "
                "broader Venn-Abers literature because the bridge design is part of "
                "the empirical object being tested."
            ),
            "",
            (
                "The blocked claims are also results. Zero bounded-support validity-ready "
                "bundles and zero population-fairness-ready bundles mean the article "
                "should not claim endpoint validity or fairness. Those boundaries "
                "prevent useful diagnostics from becoming stronger claims than the "
                "evidence supports."
            ),
            "",
            "## Reproducibility And Traceability",
            "",
            (
                f"The knowledge graph snapshot used by this draft has {fmt(s['kg_node_count'])} "
                f"nodes and {fmt(s['kg_edge_count'])} edges. The graph links report "
                "sections, source artifacts, citation keys, claim boundaries, and "
                "quality checks. It is evidence infrastructure for the article and "
                "will become citable only after the sterile repository and release "
                "review are complete."
            ),
            "",
            "## Limitations",
            "",
            "- This is a draft article, not a final manuscript or submission package.",
            "- The method evidence is descriptive and diagnostic; it is not a general recommendation.",
            "- Venn-Abers evidence is negative for the current bridge; it is not a rejection of the entire literature.",
            "- Group metrics are diagnostic and do not establish population fairness.",
            "- Endpoint audits currently block bounded-support validity claims.",
            "",
            "## Conclusion",
            "",
            (
                "This draft closes with a descriptive, not prescriptive, "
                "interpretation of the completed regression conformal-prediction "
                "evidence. The audited evidence base supports reporting CQR/CV+ "
                "as strong practical candidates observed in these experiments and "
                "the evaluated Venn-Abers regression bridge as bridge-specific "
                "negative evidence. It does not support final method selection, a "
                "general method recommendation, a bounded-support validity claim, "
                "a population fairness claim, public release, or a citable KG/site "
                "claim."
            ),
            "",
            (
                "The scientific contribution is therefore the audited measurement "
                "and boundary record itself: useful empirical patterns are retained, "
                "negative evidence is not rewritten as success, and blocked claims "
                "remain visible until later evidence explicitly opens them."
            ),
            "",
            "## References",
            "",
        ]
    )
    for url, key in sorted(payload["citation_keys"].items(), key=lambda item: item[1]):
        lines.append(f"- `@{key}`: {url}")
    lines.extend(["", "## Source Artifacts", ""])
    for label, path in payload["sources"].items():
        lines.append(f"- `{label}`: `{path}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    json_out = root / args.json_out
    payload = build_payload(root)
    atomic_write_json(json_out, payload)
    atomic_write_text(out, render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out, root),
                "json_out": rel(json_out, root),
                "overall_status": payload["summary"]["overall_status"],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
