"""Build the private Research Document authoring artifact.

The Research Document is the reader-facing manuscript surface requested after
neutral empirical closure. It is authored for private review and keeps public
release, method recommendation, and positive claims closed.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_research_document_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/research_document.md")
DEFAULT_JSON_OUT = Path("experiments/regression/manuscript/research_document.json")
AUTHOR_NAME = "Emre Tasar"
AUTHOR_ROLE = "Data Scientist"
AUTHOR_EMAIL = "detasar@gmail.com"

AUTHORING_DECISION = Path(
    "experiments/regression/manuscript/publication_authoring_decision_record.json"
)
MAIN_ARTICLE = Path("experiments/regression/manuscript/main_article_draft.json")
SUPPLEMENT = Path("experiments/regression/manuscript/supplementary_document_draft.json")
INDIVIDUAL_REPORT = Path(
    "experiments/regression/manuscript/individual_experiment_report_draft.json"
)
CLAIM_MATRIX = Path(
    "experiments/regression/manuscript/publication_claim_evidence_verification_matrix.json"
)
CITATION_REGISTRY = Path(
    "experiments/regression/manuscript/publication_citation_registry.json"
)
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
PRIVATE_PACKAGE = Path(
    "experiments/regression/manuscript/private_sterile_publication_package_manifest.json"
)
PUBLICATION_EXEMPLAR_REVIEW = Path(
    "experiments/regression/manuscript/publication_exemplar_review.json"
)
CQR_MODEL_MATCHED_SYNTHESIS = Path(
    "experiments/regression/reports/model_matched_cqr_rerun_plan/"
    "cqr_fixed_vs_model_matched_synthesis.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output Markdown path.")
    parser.add_argument(
        "--json-out", default=str(DEFAULT_JSON_OUT), help="Output JSON path."
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary") if isinstance(payload, dict) else {}
    return value if isinstance(value, dict) else {}


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
    if value is None:
        return "n/a"
    return str(value)


def fmt_counts(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "n/a"
    return ", ".join(f"{key}={fmt(count)}" for key, count in sorted(value.items()))


def citation_keys(payload: dict[str, Any]) -> dict[str, str]:
    return {row["url"]: row["citation_key"] for row in payload.get("citation_rows", [])}


def required_citation_urls() -> tuple[str, ...]:
    return (
        "https://arxiv.org/abs/1604.04173",
        "https://arxiv.org/abs/1905.03222",
        "https://arxiv.org/abs/1905.02928",
        "https://arxiv.org/abs/2002.09025",
        "https://proceedings.mlr.press/v91/nouretdinov18a.html",
        "https://proceedings.mlr.press/v230/nouretdinov24a.html",
        "https://proceedings.mlr.press/v267/van-der-laan25a.html",
        "https://arxiv.org/html/2605.06646v1",
    )


def build_reader_contract_rows() -> list[dict[str, str]]:
    return [
        {
            "reading_layer": "Empirical object",
            "reader_question": "What was actually measured?",
            "safe_reading": (
                "A publication-scoped regression conformal prediction audit over "
                "completed dataset-alpha-method result rows."
            ),
            "boundary": (
                "Do not read the scope as exhaustive internet coverage, a product "
                "benchmark, or a deployment claim."
            ),
        },
        {
            "reading_layer": "Observed pattern",
            "reader_question": "Which methods looked practically useful here?",
            "safe_reading": (
                "CQR/CV+ were observed as strong practical candidates in these "
                "experiments."
            ),
            "boundary": (
                "Do not convert that observation into a selected method, a universal "
                "best-method statement, or a recommendation."
            ),
        },
        {
            "reading_layer": "Negative evidence",
            "reader_question": "What happened to the Venn-Abers regression bridge?",
            "safe_reading": (
                "The evaluated bridge did not emerge as the expected strong "
                "regression interval solution in this experiment."
            ),
            "boundary": (
                "Do not reject predictive-distribution or generalized Venn-Abers "
                "research from this bridge-specific result."
            ),
        },
        {
            "reading_layer": "Traceability and release",
            "reader_question": "How should the package, KG, and site be treated?",
            "safe_reading": (
                "They are Research Atlas surfaces for tracing claims to evidence, "
                "citations, and scope boundaries."
            ),
            "boundary": (
                "The KG is a navigation and traceability artifact, not an "
                "independent scientific claim."
            ),
        },
    ]


def build_executive_synthesis_rows(
    summary_payload: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "paragraph_id": "study_identity",
            "heading": "What this document is",
            "body": (
                "This Research Document is a private, evidence-linked synthesis "
                "of a regression conformal prediction audit. It summarizes "
                f"{fmt(summary_payload['publication_completed_rows'])} completed "
                f"rows across {fmt(summary_payload['dataset_count'])} datasets, "
                f"{fmt(summary_payload['dataset_alpha_cell_count'])} "
                "dataset-alpha cells, and "
                f"{fmt(summary_payload['method_count'])} conformal-method labels. "
                "The unit of evidence is therefore an audited result surface, not "
                "a single showcase run."
            ),
            "boundary": (
                "Do not read the study identity as exhaustive internet coverage, "
                "deployment validation, or a final public release."
            ),
        },
        {
            "paragraph_id": "supported_finding",
            "heading": "What the evidence supports",
            "body": (
                "The central supported wording is deliberately narrow: CQR/CV+ "
                "were observed as strong practical candidates in these "
                "experiments. CQR has "
                f"{fmt(summary_payload['cqr_frontier_cell_count'])} descriptive "
                "frontier cells, and CV+ has "
                f"{fmt(summary_payload['cv_plus_frontier_cell_count'])}. These "
                "counts support a practical-candidate reading, not a selected "
                "method claim."
            ),
            "boundary": (
                "Do not turn observed practical-candidate evidence into a "
                "universal best-method statement or recommendation."
            ),
        },
        {
            "paragraph_id": "cqr_backend_sensitivity_check",
            "heading": "What the CQR backend check adds",
            "body": (
                "The completed backend-confound check adds a model-matched CQR "
                "rerun rather than a new method-selection claim. It completed "
                f"{fmt(summary_payload['cqr_backend_sensitivity_model_matched_completed_rows'])} "
                "model-matched CQR rows and paired "
                f"{fmt(summary_payload['cqr_backend_sensitivity_paired_cell_count'])} "
                "dataset-alpha-model-family cells against the historical "
                "fixed-GBM CQR pipeline. Coverage-eligible interval-score "
                "selections were fixed-GBM CQR="
                f"{fmt(summary_payload['cqr_backend_sensitivity_fixed_gbm_selected_count'])}, "
                "model-matched CQR="
                f"{fmt(summary_payload['cqr_backend_sensitivity_model_matched_selected_count'])}, "
                "and neither="
                f"{fmt(summary_payload['cqr_backend_sensitivity_no_coverage_eligible_count'])}."
            ),
            "boundary": (
                "The check keeps CQR as an experiment-scoped practical signal; "
                "it does not authorize a method-selection or production "
                "recommendation claim."
            ),
        },
        {
            "paragraph_id": "negative_evidence",
            "heading": "What the evidence does not support",
            "body": (
                "The evaluated Venn-Abers regression bridge did not become the "
                "expected strong interval solution in this experiment. The bridge "
                f"has {fmt(summary_payload['venn_undercoverage_run_count'])} "
                "undercoverage runs, a quantile-coverage mean of "
                f"{fmt(summary_payload['venn_abers_quantile_coverage_mean'])}, "
                "and validated-regression support flag "
                f"`{summary_payload['venn_can_support_validated_regression']}`."
            ),
            "boundary": (
                "Do not generalize this bridge-specific negative evidence into a "
                "rejection of predictive-distribution or generalized Venn-Abers "
                "research."
            ),
        },
        {
            "paragraph_id": "closed_claims",
            "heading": "Which claims remain closed",
            "body": (
                "Several attractive positive claims remain explicitly closed. "
                "The current record contains "
                f"{fmt(summary_payload['bounded_support_validity_ready_bundle_count'])} "
                "bounded-support-validity-ready bundles and "
                f"{fmt(summary_payload['fairness_population_ready_bundle_count'])} "
                "population-fairness-ready bundles. These zeros are not gaps to "
                "hide; they are part of the scientific result."
            ),
            "boundary": (
                "Do not soften zero-ready validity or fairness gates into "
                "positive endpoint, fairness, or deployment claims."
            ),
        },
        {
            "paragraph_id": "review_path",
            "heading": "How a reviewer should inspect it",
            "body": (
                "The review path is intentionally traceable. The private package "
                "and KG connect the Research Document to source artifacts, "
                "scripts, claim gates, and citation boundaries. The current KG "
                f"has {fmt(summary_payload['kg_node_count'])} nodes, "
                f"{fmt(summary_payload['kg_edge_count'])} edges, "
                f"{fmt(summary_payload['kg_isolated_node_count'])} isolated nodes, "
                "and edge selector provenance coverage "
                f"{fmt(summary_payload['kg_edge_selector_provenance_coverage'])}."
            ),
            "boundary": (
                "Treat the KG as Research Atlas navigation and traceability, not "
                "as a standalone scientific result."
            ),
        },
    ]


def build_plain_language_summary_rows(summary_payload: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "reader_question": "What is the shortest correct reading of the study?",
            "plain_language_answer": (
                "This is an audited measurement record for regression conformal "
                "prediction, not a recommendation list."
            ),
            "evidence_anchor": (
                f"{fmt(summary_payload['publication_completed_rows'])} completed "
                f"rows across {fmt(summary_payload['dataset_count'])} datasets, "
                f"{fmt(summary_payload['dataset_alpha_cell_count'])} dataset-alpha "
                f"cells, and {fmt(summary_payload['method_count'])} method labels."
            ),
            "boundary": (
                "Do not read the study as exhaustive internet coverage, a product "
                "benchmark, or deployment advice."
            ),
        },
        {
            "reader_question": "What does the CQR/CV+ finding mean?",
            "plain_language_answer": (
                "CQR/CV+ looked practically useful in these experiments, with CQR "
                "carrying the largest descriptive frontier signal and a completed "
                "backend-sensitivity check."
            ),
            "evidence_anchor": (
                f"CQR has {fmt(summary_payload['cqr_frontier_cell_count'])} "
                f"frontier cells and CV+ has "
                f"{fmt(summary_payload['cv_plus_frontier_cell_count'])} frontier "
                "cells; the model-matched CQR rerun completed "
                f"{fmt(summary_payload['cqr_backend_sensitivity_model_matched_completed_rows'])} "
                "rows and "
                f"{fmt(summary_payload['cqr_backend_sensitivity_paired_cell_count'])} "
                "paired cells."
            ),
            "boundary": (
                "Do not turn the observed pattern into a final selected method, "
                "universal best-method statement, or production recommendation."
            ),
        },
        {
            "reader_question": "What does `1 - alpha` mean here?",
            "plain_language_answer": (
                "`1 - alpha` is the target coverage level; observed coverage still "
                "has to be measured in the audited cells."
            ),
            "evidence_anchor": (
                "The document reports coverage means, near-nominal hit rates, "
                "frontier cells, and undercoverage runs after the target is fixed."
            ),
            "boundary": (
                "Do not treat the nominal target as proof that every dataset, "
                "endpoint, or subgroup achieved that target."
            ),
        },
        {
            "reader_question": "How should the Venn-Abers bridge result be read?",
            "plain_language_answer": (
                "The evaluated regression bridge produced negative failure-mode "
                "evidence in this experiment."
            ),
            "evidence_anchor": (
                f"{fmt(summary_payload['venn_undercoverage_run_count'])} "
                "undercoverage runs, quantile-coverage mean "
                f"{fmt(summary_payload['venn_abers_quantile_coverage_mean'])}, "
                "and validated-regression support flag "
                f"`{summary_payload['venn_can_support_validated_regression']}`."
            ),
            "boundary": (
                "Do not reject predictive-distribution or generalized Venn-Abers "
                "research from this bridge-specific result."
            ),
        },
        {
            "reader_question": "Why keep the KG and private package in the review path?",
            "plain_language_answer": (
                "They let a reviewer trace claims to reports, scripts, citations, "
                "quality gates, and release boundaries."
            ),
            "evidence_anchor": (
                f"{fmt(summary_payload['kg_node_count'])} KG nodes, "
                f"{fmt(summary_payload['kg_edge_count'])} edges, "
                f"{fmt(summary_payload['kg_isolated_node_count'])} isolated nodes, "
                "and edge selector provenance coverage "
                f"{fmt(summary_payload['kg_edge_selector_provenance_coverage'])}."
            ),
            "boundary": (
                "Do not cite, publish, or deploy the KG/site before explicit public "
                "release authorization."
            ),
        },
    ]


def build_reader_primer_rows() -> list[dict[str, str]]:
    return [
        {
            "term": "prediction interval",
            "plain_language_meaning": (
                "A lower-to-upper range around a regression prediction."
            ),
            "research_document_role": (
                "The interval is the object whose empirical coverage and width "
                "are audited."
            ),
            "evidence_boundary": (
                "A useful interval in this study is not a production guarantee."
            ),
        },
        {
            "term": "coverage",
            "plain_language_meaning": (
                "The fraction of held-out outcomes that fall inside the interval."
            ),
            "research_document_role": (
                "Coverage is reported as an empirical diagnostic by dataset, "
                "alpha, and method family."
            ),
            "evidence_boundary": (
                "Observed coverage is not treated as proof of universal validity."
            ),
        },
        {
            "term": "1 - alpha",
            "plain_language_meaning": (
                "The target coverage level; alpha is the target miscoverage rate."
            ),
            "research_document_role": (
                "Dataset-alpha cells define the main calibration comparison unit."
            ),
            "evidence_boundary": (
                "Near-target behavior is reported within the audited scope only."
            ),
        },
        {
            "term": "calibration set",
            "plain_language_meaning": (
                "Data reserved to tune interval size after the base model is fit."
            ),
            "research_document_role": (
                "Calibration is the mechanism that turns model errors into "
                "interval adjustments."
            ),
            "evidence_boundary": (
                "Calibration diagnostics do not authorize claims about deployment."
            ),
        },
        {
            "term": "CQR",
            "plain_language_meaning": (
                "Conformalized Quantile Regression: quantile models plus "
                "conformal calibration."
            ),
            "research_document_role": (
                "CQR is reported as a strong practical candidate observed in "
                "these experiments."
            ),
            "evidence_boundary": (
                "The document does not claim CQR is the best method in general."
            ),
        },
        {
            "term": "CV+",
            "plain_language_meaning": (
                "A cross-validation-style conformal method using out-of-fold "
                "predictions."
            ),
            "research_document_role": (
                "CV+ is reported as a strong practical candidate observed in "
                "these experiments."
            ),
            "evidence_boundary": (
                "The document does not issue a method recommendation."
            ),
        },
        {
            "term": "frontier cell",
            "plain_language_meaning": (
                "A dataset-alpha comparison where a method appears on the "
                "descriptive trade-off frontier."
            ),
            "research_document_role": (
                "Frontier counts summarize observed coverage/width trade-offs."
            ),
            "evidence_boundary": (
                "A frontier count is descriptive evidence, not a final-selection claim."
            ),
        },
        {
            "term": "Venn-Abers regression bridge",
            "plain_language_meaning": (
                "The evaluated bridge from Venn-Abers-style calibration evidence "
                "to regression intervals."
            ),
            "research_document_role": (
                "It is reported as negative/failure-mode evidence in this study."
            ),
            "evidence_boundary": (
                "This does not invalidate the broader Venn-Abers literature."
            ),
        },
    ]


def build_method_mechanics_rows() -> list[dict[str, str]]:
    return [
        {
            "method_family": "Split conformal regression",
            "what_it_does": (
                "Fits a regression model, measures held-out calibration errors, "
                "and expands future predictions by a calibration quantile."
            ),
            "what_the_interval_depends_on": (
                "The split policy, the residual score, and the empirical score "
                "quantile tied to `1 - alpha`."
            ),
            "study_boundary": (
                "It is a baseline calibration mechanism, not a complete answer "
                "to heterogeneity or endpoint validity."
            ),
        },
        {
            "method_family": "CQR",
            "what_it_does": (
                "Fits lower and upper quantile models, then conformalizes the "
                "two-sided quantile interval with calibration scores."
            ),
            "what_the_interval_depends_on": (
                "Quantile-model quality, lower/upper quantile levels, calibration "
                "scores, and the target miscoverage rate."
            ),
            "study_boundary": (
                "Observed here as a strong practical candidate; not stated as a "
                "universal regression-CP recommendation."
            ),
        },
        {
            "method_family": "CV+ / jackknife-style methods",
            "what_it_does": (
                "Uses out-of-fold or leave-one-out predictions so interval "
                "construction reflects model-fitting variability."
            ),
            "what_the_interval_depends_on": (
                "Fold design, base-model stability, conformity scores, and the "
                "cross-validated aggregation rule."
            ),
            "study_boundary": (
                "Observed here as a strong practical candidate; final method "
                "selection remains closed."
            ),
        },
        {
            "method_family": "Mondrian calibration",
            "what_it_does": (
                "Calibrates scores within groups or strata rather than using a "
                "single pooled calibration quantile."
            ),
            "what_the_interval_depends_on": (
                "The grouping rule, group sample sizes, residual scores, and the "
                "same `1 - alpha` coverage target."
            ),
            "study_boundary": (
                "Useful as a diagnostic comparator; group diagnostics do not "
                "become population fairness claims."
            ),
        },
        {
            "method_family": "Venn-Abers regression bridge",
            "what_it_does": (
                "Maps Venn-Abers-style calibration evidence into interval-style "
                "regression diagnostics for this experiment."
            ),
            "what_the_interval_depends_on": (
                "The bridge design, its calibration object, and the diagnostic "
                "conversion into coverage/interval evidence."
            ),
            "study_boundary": (
                "The evaluated bridge produced negative evidence here; this does "
                "not reject the broader Venn-Abers literature."
            ),
        },
    ]


def build_citation_backed_concept_rows(cite: dict[str, str]) -> list[dict[str, Any]]:
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
            "concept": "Regression conformal prediction",
            "reader_question": "What kind of uncertainty statement is being audited?",
            "literature_basis": (
                "Distribution-free predictive inference for regression motivates "
                "calibrated prediction intervals under stated assumptions."
            ),
            "citation_keys": [split_key],
            "experiment_anchor": (
                "Coverage, width, interval score, and target `1 - alpha` are "
                "reported inside audited dataset-alpha-method cells."
            ),
            "closed_reading": (
                "Do not read marginal interval calibration as conditional, "
                "endpoint, subgroup, or deployment validity."
            ),
        },
        {
            "concept": "`1 - alpha` and `alpha`",
            "reader_question": "Is the nominal target the same as observed coverage?",
            "literature_basis": (
                "`1 - alpha` is the target coverage level and `alpha` is the "
                "target miscoverage rate used by the calibration rule."
            ),
            "citation_keys": [split_key, cqr_key],
            "experiment_anchor": (
                "The experiment evaluates observed coverage and near-nominal "
                "behavior after the target level is fixed."
            ),
            "closed_reading": (
                "Do not treat a nominal target as proof that every audited cell "
                "or subgroup achieved that target."
            ),
        },
        {
            "concept": "Calibration data and conformity scores",
            "reader_question": "Where does the interval correction come from?",
            "literature_basis": (
                "Conformal regression uses held-out calibration evidence to map "
                "model errors or scores into interval adjustments."
            ),
            "citation_keys": [split_key],
            "experiment_anchor": (
                "Split, normalized, Mondrian, and related rows differ partly by "
                "how calibration scores are pooled or stratified."
            ),
            "closed_reading": (
                "Do not infer that a calibration mechanism alone solves covariate "
                "shift, bounded support, or fairness validity."
            ),
        },
        {
            "concept": "Conformalized Quantile Regression (CQR)",
            "reader_question": "Why does CQR use two quantile models before calibration?",
            "literature_basis": (
                "CQR starts from lower and upper quantile estimates and then "
                "conformalizes the interval using calibration residual evidence."
            ),
            "citation_keys": [cqr_key],
            "experiment_anchor": (
                "CQR has 56 descriptive frontier cells and is written only as a "
                "strong practical candidate observed in these experiments."
            ),
            "closed_reading": (
                "Do not convert the observed CQR pattern into a universal best-method "
                "or production recommendation."
            ),
        },
        {
            "concept": "CV+ and jackknife-style resampling",
            "reader_question": "Why do CV+ rows use out-of-fold predictions?",
            "literature_basis": (
                "Jackknife+ and related cross-validation conformal methods use "
                "resampling predictions to account for model-fitting variability."
            ),
            "citation_keys": [jack_key, jab_key],
            "experiment_anchor": (
                "CV+ has 13 descriptive frontier cells and is written as a strong "
                "practical candidate observed in these experiments."
            ),
            "closed_reading": (
                "Do not treat CV+ evidence as a final selected method or a claim "
                "that resampling always improves interval quality."
            ),
        },
        {
            "concept": "Group and Mondrian diagnostics",
            "reader_question": "Why are group-calibrated rows not fairness claims?",
            "literature_basis": (
                "Group or stratified calibration changes how calibration evidence "
                "is pooled; it is separate from a population-fairness estimand."
            ),
            "citation_keys": [split_key],
            "experiment_anchor": (
                "Mondrian absolute-residual calibration has 15 frontier cells and "
                "187 pairwise group comparisons are retained as diagnostics."
            ),
            "closed_reading": (
                "Do not state that fairness is solved while the population-fairness "
                "ready bundle count is zero."
            ),
        },
        {
            "concept": "Venn-Abers predictive distributions",
            "reader_question": "Why is the Venn-Abers result described narrowly?",
            "literature_basis": (
                "Venn-Abers predictive distributions and generalized Venn-Abers "
                "calibration are broader than the interval bridge evaluated here."
            ),
            "citation_keys": [venn18_key, venn24_key, vanderlaan_key, ivar_key],
            "experiment_anchor": (
                "The evaluated bridge has 14 undercoverage runs and validated "
                "regression support flag `False`."
            ),
            "closed_reading": (
                "Do not reject predictive-distribution or generalized Venn-Abers "
                "research from this bridge-specific negative evidence."
            ),
        },
        {
            "concept": "Claim gates and release gates",
            "reader_question": "Why does the document report closed claims as results?",
            "literature_basis": (
                "The literature citations support method definitions; the release "
                "and claim gates are project evidence controls, not new theory."
            ),
            "citation_keys": [split_key, cqr_key],
            "experiment_anchor": (
                "Final method selection, bounded-support validity, population "
                "fairness, KG citation, and public release remain explicitly closed."
            ),
            "closed_reading": (
                "Do not open a closed scientific or release claim by wording it "
                "more optimistically in prose."
            ),
        },
    ]


def build_scientific_method_rows(
    summary_payload: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "stage": "Question and empirical object",
            "reader_question": (
                "What exactly is being measured before any method interpretation?"
            ),
            "evidence_anchor": (
                f"{fmt(summary_payload.get('publication_completed_rows'))} "
                "publication-scoped rows, "
                f"{fmt(summary_payload.get('dataset_count'))} datasets, "
                f"{fmt(summary_payload.get('dataset_alpha_cell_count'))} "
                "dataset-alpha cells, and "
                f"{fmt(summary_payload.get('method_count'))} method labels."
            ),
            "scientific_boundary": (
                "Scope size is audit evidence, not proof of exhaustive internet "
                "coverage or deployment generality."
            ),
        },
        {
            "stage": "Measurement protocol",
            "reader_question": (
                "Which quantities turn model outputs into comparable evidence?"
            ),
            "evidence_anchor": (
                "Coverage, width, frontier cells, near-nominal hit rates, and "
                "undercoverage runs are read within dataset-alpha-method cells."
            ),
            "scientific_boundary": (
                "Empirical metrics are not theorem-level guarantees and do not "
                "open conditional, endpoint, or subgroup claims."
            ),
        },
        {
            "stage": "Candidate-method comparison",
            "reader_question": (
                "Which practical patterns survived the audited comparison?"
            ),
            "evidence_anchor": (
                "CQR has "
                f"{fmt(summary_payload.get('cqr_frontier_cell_count'))} "
                "frontier cells and CV+ has "
                f"{fmt(summary_payload.get('cv_plus_frontier_cell_count'))}; "
                "CQR row-weighted coverage mean is "
                f"{fmt(summary_payload.get('cqr_row_weighted_coverage_mean'))}."
            ),
            "scientific_boundary": (
                "This supports the wording 'observed as strong practical "
                "candidates in these experiments', not a selected-method or "
                "best-method claim."
            ),
        },
        {
            "stage": "CQR backend sensitivity control",
            "reader_question": (
                "Was the CQR signal only an artifact of the fixed-GBM CQR backend?"
            ),
            "evidence_anchor": (
                "The model-matched CQR rerun completed "
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_model_matched_completed_rows'))} "
                "rows and formed "
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_paired_cell_count'))} "
                "paired dataset-alpha-model-family cells. Coverage-eligible "
                "interval-score selected cells were fixed-GBM CQR="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_fixed_gbm_selected_count'))}, "
                "model-matched CQR="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_model_matched_selected_count'))}, "
                "and neither="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_no_coverage_eligible_count'))}."
            ),
            "scientific_boundary": (
                "The check supports a backend-sensitivity reading only; it does "
                "not open a CQR selection, CQR recommendation, or universal method "
                "claim."
            ),
        },
        {
            "stage": "Falsification and negative evidence",
            "reader_question": (
                "Which attractive claims failed to close under the current evidence?"
            ),
            "evidence_anchor": (
                "The evaluated Venn-Abers bridge has "
                f"{fmt(summary_payload.get('venn_undercoverage_run_count'))} "
                "undercoverage runs and validated-regression support flag "
                f"`{summary_payload.get('venn_can_support_validated_regression')}`."
            ),
            "scientific_boundary": (
                "The negative result is bridge-specific and does not reject "
                "predictive-distribution or generalized Venn-Abers research."
            ),
        },
        {
            "stage": "Closed positive-claim gates",
            "reader_question": (
                "Which stronger conclusions must remain absent from the prose?"
            ),
            "evidence_anchor": (
                f"{fmt(summary_payload.get('bounded_support_validity_ready_bundle_count'))} "
                "bounded-support-validity-ready bundles and "
                f"{fmt(summary_payload.get('fairness_population_ready_bundle_count'))} "
                "population-fairness-ready bundles."
            ),
            "scientific_boundary": (
                "A zero-ready gate is reported as a result; prose cannot convert "
                "it into bounded-support validity or population fairness."
            ),
        },
        {
            "stage": "Reproducibility and traceability",
            "reader_question": (
                "How can a reviewer trace the evidence without opening release?"
            ),
            "evidence_anchor": (
                f"{fmt(summary_payload.get('kg_node_count'))} KG nodes, "
                f"{fmt(summary_payload.get('kg_edge_count'))} KG edges, "
                f"{fmt(summary_payload.get('kg_isolated_node_count'))} isolated nodes, "
                "and edge selector provenance coverage "
                f"{fmt(summary_payload.get('kg_edge_selector_provenance_coverage'))}."
            ),
            "scientific_boundary": (
                "The KG and private package are review infrastructure; public "
                "citation and GitHub Pages deployment remain closed."
            ),
        },
    ]


def build_private_review_decision_rows(
    summary_payload: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "decision_point": "Private review readability",
            "accept_if": (
                "The Research Document, main article, supplement, README, and "
                "private site keep the empirical wording scoped and readable."
            ),
            "evidence_to_check": (
                f"{fmt(summary_payload.get('private_review_surface_pass_count'))} of "
                f"{fmt(summary_payload.get('private_review_surface_count'))} private "
                "review surfaces pass required phrase and boundary checks."
            ),
            "still_closed": (
                "Private readability does not authorize public release, final "
                "submission prose, or a method recommendation."
            ),
        },
        {
            "decision_point": "Empirical result wording",
            "accept_if": (
                "CQR/CV+ are written only as strong practical candidates observed "
                "in these experiments."
            ),
            "evidence_to_check": (
                f"CQR frontier cells {fmt(summary_payload.get('cqr_frontier_cell_count'))}; "
                f"CV+ frontier cells {fmt(summary_payload.get('cv_plus_frontier_cell_count'))}; "
                "claim/evidence matrix status pass."
            ),
            "still_closed": (
                "No final selected method, best-method statement, production "
                "recommendation, or universal superiority claim."
            ),
        },
        {
            "decision_point": "CQR backend sensitivity wording",
            "accept_if": (
                "The model-matched CQR rerun is reported as a backend-confound "
                "diagnostic and not as a selection-making experiment."
            ),
            "evidence_to_check": (
                f"Completed fixed-GBM rows {fmt(summary_payload.get('cqr_backend_sensitivity_fixed_gbm_completed_rows'))}; "
                f"completed model-matched rows {fmt(summary_payload.get('cqr_backend_sensitivity_model_matched_completed_rows'))}; "
                f"paired cells {fmt(summary_payload.get('cqr_backend_sensitivity_paired_cell_count'))}; "
                "coverage-eligible interval-score selections fixed-GBM="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_fixed_gbm_selected_count'))}, "
                "model-matched="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_model_matched_selected_count'))}, "
                "neither="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_no_coverage_eligible_count'))}."
            ),
            "still_closed": (
                "No method-selection claim and no production recommendation."
            ),
        },
        {
            "decision_point": "Venn-Abers negative evidence",
            "accept_if": (
                "The evaluated bridge is reported as bridge-specific negative "
                "or failure-mode evidence."
            ),
            "evidence_to_check": (
                f"{fmt(summary_payload.get('venn_undercoverage_run_count'))} "
                "undercoverage runs and validated-regression support flag "
                f"`{summary_payload.get('venn_can_support_validated_regression')}`."
            ),
            "still_closed": (
                "No validated Venn-Abers regression interval claim and no "
                "literature-wide rejection of Venn-Abers research."
            ),
        },
        {
            "decision_point": "Closed positive scientific claims",
            "accept_if": (
                "Bounded-support validity and population-fairness claims are "
                "reported as closed rather than softened into optimistic prose."
            ),
            "evidence_to_check": (
                "Bounded-support-validity-ready bundles "
                f"{fmt(summary_payload.get('bounded_support_validity_ready_bundle_count'))}; "
                "population-fairness-ready bundles "
                f"{fmt(summary_payload.get('fairness_population_ready_bundle_count'))}."
            ),
            "still_closed": (
                "No bounded-support validity, endpoint validity, population "
                "fairness, or deployment-fairness conclusion."
            ),
        },
        {
            "decision_point": "KG and site publication",
            "accept_if": (
                "The KG and private site are useful for review navigation and "
                "claim tracing."
            ),
            "evidence_to_check": (
                f"{fmt(summary_payload.get('kg_node_count'))} KG nodes, "
                f"{fmt(summary_payload.get('kg_edge_count'))} edges, "
                f"{fmt(summary_payload.get('kg_isolated_node_count'))} isolated nodes, "
                "and edge selector provenance coverage "
                f"{fmt(summary_payload.get('kg_edge_selector_provenance_coverage'))}."
            ),
            "still_closed": (
                "No public KG citation, GitHub Pages deployment, public site, or "
                "public repository release before explicit authorization."
            ),
        },
    ]


def build_contribution_finding_rows(
    summary_payload: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "contribution_or_finding": "Audited regression-CP experiment scope",
            "reader_safe_statement": (
                "The study reports a publication-scoped regression conformal "
                "prediction audit over "
                f"{fmt(summary_payload.get('publication_completed_rows'))} completed "
                f"rows, {fmt(summary_payload.get('dataset_count'))} datasets, "
                f"{fmt(summary_payload.get('dataset_alpha_cell_count'))} "
                "dataset-alpha cells, and "
                f"{fmt(summary_payload.get('method_count'))} method labels."
            ),
            "evidence_anchor": (
                "Individual experiment report facts, main article scope summary, "
                "and completed-row accounting."
            ),
            "closed_reading": (
                "This is not a claim of exhaustive internet dataset coverage or "
                "deployment generality."
            ),
        },
        {
            "contribution_or_finding": "Practical candidate pattern",
            "reader_safe_statement": (
                "CQR/CV+ were observed as strong practical candidates in these "
                "experiments, with CQR carrying the largest descriptive frontier "
                f"count ({fmt(summary_payload.get('cqr_frontier_cell_count'))}) "
                "and CV+ contributing "
                f"{fmt(summary_payload.get('cv_plus_frontier_cell_count'))} "
                "frontier cells."
            ),
            "evidence_anchor": (
                "Main article claim-evidence map, result reading guide, and "
                "supplementary robustness diagnostics."
            ),
            "closed_reading": (
                "This is not a final selected method, global superiority claim, "
                "or recommendation."
            ),
        },
        {
            "contribution_or_finding": "CQR backend sensitivity check",
            "reader_safe_statement": (
                "The completed model-matched CQR rerun tested whether the CQR "
                "signal was only a fixed-GBM pipeline artifact. It produced "
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_model_matched_completed_rows'))} "
                "model-matched CQR rows and "
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_paired_cell_count'))} "
                "paired dataset-alpha-model-family cells."
            ),
            "evidence_anchor": (
                "Fixed-vs-model-matched CQR synthesis and model-matched CQR rerun "
                "manifest."
            ),
            "closed_reading": (
                "This check does not authorize a universal CQR recommendation or "
                "a final method-selection claim."
            ),
        },
        {
            "contribution_or_finding": "Venn-Abers bridge negative evidence",
            "reader_safe_statement": (
                "The evaluated Venn-Abers regression bridge produced negative "
                "failure-mode evidence, including "
                f"{fmt(summary_payload.get('venn_undercoverage_run_count'))} "
                "undercoverage runs and quantile-coverage mean "
                f"{fmt(summary_payload.get('venn_abers_quantile_coverage_mean'))}."
            ),
            "evidence_anchor": (
                "Bridge diagnostics, undercoverage accounting, and Venn-Abers "
                "citation boundary rows."
            ),
            "closed_reading": (
                "This is not a rejection of predictive-distribution or generalized "
                "Venn-Abers research."
            ),
        },
        {
            "contribution_or_finding": "Closed positive claims are part of the result",
            "reader_safe_statement": (
                "Bounded-support validity and population-fairness positive claims "
                "remain closed, with "
                f"{fmt(summary_payload.get('bounded_support_validity_ready_bundle_count'))} "
                "bounded-support-validity-ready bundles and "
                f"{fmt(summary_payload.get('fairness_population_ready_bundle_count'))} "
                "population-fairness-ready bundles."
            ),
            "evidence_anchor": (
                "Paper gate map, publication claim/evidence matrix, bounded-support "
                "audit, and fairness diagnostic scope."
            ),
            "closed_reading": (
                "The document must not fill these gaps with optimistic prose."
            ),
        },
        {
            "contribution_or_finding": "Traceability and reproducibility surface",
            "reader_safe_statement": (
                "The knowledge graph is usable as a private traceability surface "
                f"with {fmt(summary_payload.get('kg_node_count'))} nodes, "
                f"{fmt(summary_payload.get('kg_edge_count'))} edges, "
                f"{fmt(summary_payload.get('kg_isolated_node_count'))} isolated "
                "nodes, and edge selector provenance coverage "
                f"{fmt(summary_payload.get('kg_edge_selector_provenance_coverage'))}."
            ),
            "evidence_anchor": (
                "Knowledge-graph quality audit and private sterile package manifest."
            ),
            "closed_reading": (
                "This does not yet make the KG a public citable component."
            ),
        },
        {
            "contribution_or_finding": "Publication package architecture",
            "reader_safe_statement": (
                "The current package separates a minimal main article, broad "
                "supplement, integrated Research Document, README review router, "
                "private site, and governance checks."
            ),
            "evidence_anchor": (
                "Publication exemplar review, sterile README draft, private site "
                "manifest, and final-output authorization protocol."
            ),
            "closed_reading": (
                "This is a private review architecture, not public release."
            ),
        },
    ]


def build_research_question_rows(
    summary_payload: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "research_question": (
                "What empirical object does this Research Document evaluate?"
            ),
            "short_answer": (
                "It evaluates a publication-scoped regression conformal "
                "prediction audit over "
                f"{fmt(summary_payload.get('publication_completed_rows'))} "
                "completed rows, "
                f"{fmt(summary_payload.get('dataset_count'))} datasets, "
                f"{fmt(summary_payload.get('dataset_alpha_cell_count'))} "
                "dataset-alpha cells, and "
                f"{fmt(summary_payload.get('method_count'))} method labels."
            ),
            "evidence_anchor": (
                "Experimental scope table, individual experiment report facts, "
                "completed-row accounting, and dataset/source audit lineage."
            ),
            "closed_reading": (
                "Do not read the scope as exhaustive internet coverage or as "
                "deployment generality."
            ),
        },
        {
            "research_question": (
                "Which conformal approaches looked practically useful in the "
                "audited experiments?"
            ),
            "short_answer": (
                "CQR/CV+ were observed as strong practical candidates in these "
                "experiments; CQR has "
                f"{fmt(summary_payload.get('cqr_frontier_cell_count'))} "
                "descriptive frontier cells and CV+ has "
                f"{fmt(summary_payload.get('cv_plus_frontier_cell_count'))}."
            ),
            "evidence_anchor": (
                "Observed method behavior table, result reading guide, "
                "row-weighted coverage summaries, and robustness diagnostics."
            ),
            "closed_reading": (
                "Do not present CQR, CV+, or any method as the selected method, "
                "best method, or general recommendation."
            ),
        },
        {
            "research_question": (
                "Was the observed CQR signal robust to matching the CQR backend "
                "to the model-family sweep?"
            ),
            "short_answer": (
                "The backend sensitivity check completed "
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_model_matched_completed_rows'))} "
                "model-matched CQR rows and compared "
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_paired_cell_count'))} "
                "paired dataset-alpha-model-family cells. Selected cells were "
                "fixed-GBM CQR="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_fixed_gbm_selected_count'))}, "
                "model-matched CQR="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_model_matched_selected_count'))}, "
                "and neither="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_no_coverage_eligible_count'))}."
            ),
            "evidence_anchor": (
                "CQR fixed-vs-model-matched synthesis, rerun manifest, article "
                "backend-sensitivity section, and supplement S1b."
            ),
            "closed_reading": (
                "Do not read the check as resolving a universal CQR selection claim."
            ),
        },
        {
            "research_question": (
                "What was learned from the evaluated Venn-Abers regression bridge?"
            ),
            "short_answer": (
                "The evaluated bridge produced negative failure-mode evidence: "
                f"{fmt(summary_payload.get('venn_undercoverage_run_count'))} "
                "undercoverage runs, quantile-coverage mean "
                f"{fmt(summary_payload.get('venn_abers_quantile_coverage_mean'))}, "
                "and validated-regression support flag "
                f"`{summary_payload.get('venn_can_support_validated_regression')}`."
            ),
            "evidence_anchor": (
                "Venn-Abers bridge diagnostics, undercoverage accounting, "
                "negative-evidence section, and Venn-Abers citation boundary."
            ),
            "closed_reading": (
                "Do not reject predictive-distribution or generalized "
                "Venn-Abers research from this bridge result."
            ),
        },
        {
            "research_question": (
                "Which stronger scientific claims remain closed?"
            ),
            "short_answer": (
                "Bounded-support validity and population-fairness claims remain "
                "closed, with "
                f"{fmt(summary_payload.get('bounded_support_validity_ready_bundle_count'))} "
                "bounded-support-validity-ready bundles and "
                f"{fmt(summary_payload.get('fairness_population_ready_bundle_count'))} "
                "population-fairness-ready bundles."
            ),
            "evidence_anchor": (
                "Paper gate map, bounded-support audit, fairness diagnostic "
                "scope, and publication claim/evidence matrix."
            ),
            "closed_reading": (
                "Do not turn diagnostic bounded-support, endpoint, or group rows "
                "into positive validity or fairness claims."
            ),
        },
        {
            "research_question": (
                "How can a reviewer audit or navigate the evidence?"
            ),
            "short_answer": (
                "The private KG and publication package provide a traceability "
                "surface with "
                f"{fmt(summary_payload.get('kg_node_count'))} KG nodes, "
                f"{fmt(summary_payload.get('kg_edge_count'))} edges, "
                f"{fmt(summary_payload.get('kg_isolated_node_count'))} isolated "
                "nodes, and edge selector provenance coverage "
                f"{fmt(summary_payload.get('kg_edge_selector_provenance_coverage'))}."
            ),
            "evidence_anchor": (
                "Knowledge-graph quality audit, private package manifest, README "
                "review router, and KG browser."
            ),
            "closed_reading": (
                "Do not cite the KG, site, or private repository as public final "
                "artifacts before the release gate opens."
            ),
        },
    ]


def build_guarantee_boundary_rows() -> list[dict[str, str]]:
    return [
        {
            "topic": "Marginal conformal coverage",
            "reader_safe_statement": (
                "The conformal regression guarantee is a marginal coverage "
                "statement for future exchangeable draws, not a pointwise promise "
                "for every individual row."
            ),
            "required_condition_or_evidence": (
                "Exchangeability, a fixed calibration protocol, and a stated "
                "`1 - alpha` target."
            ),
            "closed_reading": (
                "Do not read marginal coverage as conditional, subgroup, endpoint, "
                "or deployment coverage."
            ),
        },
        {
            "topic": "Empirical coverage in this study",
            "reader_safe_statement": (
                "Observed coverage summarizes held-out behavior inside the audited "
                "dataset, split, method, and alpha scope."
            ),
            "required_condition_or_evidence": (
                "Completed-row accounting, dataset-alpha cells, split policy, and "
                "result audits."
            ),
            "closed_reading": (
                "Do not convert an empirical coverage mean into a theorem or a "
                "general product recommendation."
            ),
        },
        {
            "topic": "Conditional and group behavior",
            "reader_safe_statement": (
                "Group and Mondrian diagnostics can reveal heterogeneity, but they "
                "do not by themselves prove population fairness."
            ),
            "required_condition_or_evidence": (
                "Group definitions, calibration sample sizes, pairwise comparisons, "
                "and the population-fairness gate."
            ),
            "closed_reading": (
                "Do not state that fairness is solved when the population-fairness "
                "ready bundle count is zero."
            ),
        },
        {
            "topic": "Efficiency and frontier evidence",
            "reader_safe_statement": (
                "Coverage-width frontier counts describe the observed trade-off "
                "surface among audited methods."
            ),
            "required_condition_or_evidence": (
                "Coverage, width, interval-score, and robustness diagnostics under "
                "the same comparison policy."
            ),
            "closed_reading": (
                "Do not treat frontier membership as a final selected method or "
                "as evidence of universal superiority."
            ),
        },
        {
            "topic": "Venn-Abers regression bridge",
            "reader_safe_statement": (
                "The negative result concerns the evaluated interval bridge, while "
                "Venn-Abers predictive-distribution and generalized calibration "
                "work remain separate literature objects."
            ),
            "required_condition_or_evidence": (
                "Bridge implementation details, undercoverage diagnostics, and "
                "the Venn-Abers citation boundary."
            ),
            "closed_reading": (
                "Do not reject the broader Venn-Abers literature from this bridge "
                "failure mode."
            ),
        },
    ]


def build_result_reading_rows() -> list[dict[str, str]]:
    return [
        {
            "metric": "row-weighted coverage mean",
            "plain_language_meaning": (
                "Average empirical coverage after giving larger completed-result "
                "blocks proportionally more influence."
            ),
            "how_to_read_it": (
                "Use it as a broad descriptive coverage summary within the audited "
                "experiment scope."
            ),
            "boundary": (
                "It is not a theorem-level coverage guarantee and not a deployment "
                "claim."
            ),
        },
        {
            "metric": "95% interval around coverage",
            "plain_language_meaning": (
                "A quantified uncertainty band around the observed aggregate "
                "coverage estimate."
            ),
            "how_to_read_it": (
                "Use it to judge the precision of the descriptive aggregate, not "
                "only the point estimate."
            ),
            "boundary": (
                "It does not remove split, dataset, endpoint, or selection caveats."
            ),
        },
        {
            "metric": "frontier cell",
            "plain_language_meaning": (
                "A dataset-alpha comparison where a method sits on the observed "
                "coverage/width trade-off frontier."
            ),
            "how_to_read_it": (
                "Use frontier counts as a compact map of practical trade-offs "
                "seen in the study."
            ),
            "boundary": (
                "A frontier count is descriptive evidence, not a final selection "
                "or general recommendation."
            ),
        },
        {
            "metric": "near-nominal hit rate",
            "plain_language_meaning": (
                "The share of comparison cells where empirical coverage is close "
                "to the target `1 - alpha` level."
            ),
            "how_to_read_it": (
                "Use it to separate approximate calibration behavior from raw "
                "coverage averages."
            ),
            "boundary": (
                "Near-nominal behavior remains scoped to the audited cells."
            ),
        },
        {
            "metric": "undercoverage run",
            "plain_language_meaning": (
                "A run where empirical coverage falls below the target coverage "
                "level by the audit rule."
            ),
            "how_to_read_it": (
                "Use it as failure-mode evidence, especially for methods or bridges "
                "that do not close validation gates."
            ),
            "boundary": (
                "It is bridge- or run-specific evidence, not a rejection of a whole "
                "research literature."
            ),
        },
        {
            "metric": "closed claim gate",
            "plain_language_meaning": (
                "An explicit record that the current evidence cannot support a "
                "stronger claim."
            ),
            "how_to_read_it": (
                "Use closed gates as results: they say what the article must not "
                "claim."
            ),
            "boundary": (
                "Closed gates can be revised only by later evidence and explicit "
                "authorization, not by prose."
            ),
        },
    ]


def build_result_interpretation_ladder_rows(
    summary_payload: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "evidence_layer": "Nominal target",
            "what_it_can_support": (
                "`1 - alpha` states the coverage target that a method is evaluated "
                "against."
            ),
            "evidence_in_this_study": (
                f"{fmt(summary_payload.get('dataset_alpha_cell_count'))} "
                "dataset-alpha cells define the main target/coverage comparison "
                "surface."
            ),
            "what_it_cannot_support": (
                "It cannot prove that every dataset, endpoint, or group achieved "
                "the nominal target."
            ),
            "reader_action": (
                "Compare observed coverage and near-nominal rates after reading "
                "the target."
            ),
        },
        {
            "evidence_layer": "Observed aggregate coverage",
            "what_it_can_support": (
                "Coverage means and uncertainty intervals summarize empirical "
                "interval behavior inside the audited scope."
            ),
            "evidence_in_this_study": (
                "CQR row-weighted coverage mean is "
                f"{fmt(summary_payload.get('cqr_row_weighted_coverage_mean'))}; "
                "CV+ row-weighted coverage mean is "
                f"{fmt(summary_payload.get('cv_plus_row_weighted_coverage_mean'))}."
            ),
            "what_it_cannot_support": (
                "It cannot be rewritten as theorem-level conditional coverage or "
                "deployment validity."
            ),
            "reader_action": (
                "Use coverage as one descriptive axis, not as a standalone "
                "recommendation."
            ),
        },
        {
            "evidence_layer": "Coverage-width trade-off",
            "what_it_can_support": (
                "Frontier cells identify methods that looked practically efficient "
                "under the audited comparison policy."
            ),
            "evidence_in_this_study": (
                f"CQR has {fmt(summary_payload.get('cqr_frontier_cell_count'))} "
                "frontier cells; CV+ has "
                f"{fmt(summary_payload.get('cv_plus_frontier_cell_count'))}."
            ),
            "what_it_cannot_support": (
                "Frontier evidence cannot be promoted to a universal best-method "
                "claim."
            ),
            "reader_action": (
                "Read CQR/CV+ as strong practical candidates observed in these "
                "experiments."
            ),
        },
        {
            "evidence_layer": "Robustness retention",
            "what_it_can_support": (
                "Bootstrap and leave-one diagnostics test whether the practical "
                "candidate pattern is fragile."
            ),
            "evidence_in_this_study": (
                "Bootstrap selection counts are "
                f"{fmt_counts(summary_payload.get('robustness_bootstrap_selection_counts'))}; "
                "leave-one-dataset and leave-one-alpha retention rates are "
                f"{fmt(summary_payload.get('robustness_leave_one_dataset_retention_rate'))} "
                "and "
                f"{fmt(summary_payload.get('robustness_leave_one_alpha_retention_rate'))}."
            ),
            "what_it_cannot_support": (
                "Robustness retention cannot open final method selection or "
                "production recommendation gates."
            ),
            "reader_action": (
                "Use robustness as support for cautious wording, not for a final "
                "selection sentence."
            ),
        },
        {
            "evidence_layer": "CQR backend sensitivity",
            "what_it_can_support": (
                "The model-matched rerun tests whether the fixed-GBM CQR signal "
                "was only a backend artifact."
            ),
            "evidence_in_this_study": (
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_model_matched_completed_rows'))} "
                "model-matched CQR rows, "
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_paired_cell_count'))} "
                "paired cells, selected cells fixed-GBM CQR="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_fixed_gbm_selected_count'))}, "
                "model-matched CQR="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_model_matched_selected_count'))}, "
                "neither="
                f"{fmt(summary_payload.get('cqr_backend_sensitivity_no_coverage_eligible_count'))}."
            ),
            "what_it_cannot_support": (
                "It cannot promote CQR from experiment-scoped practical signal "
                "to universal method-selection or production recommendation."
            ),
            "reader_action": (
                "Read the check as backend-confound evidence and keep the final "
                "claim descriptive."
            ),
        },
        {
            "evidence_layer": "Negative bridge evidence",
            "what_it_can_support": (
                "Undercoverage and a closed validation flag support a narrow "
                "failure-mode reading for the evaluated bridge."
            ),
            "evidence_in_this_study": (
                f"The evaluated Venn-Abers bridge has "
                f"{fmt(summary_payload.get('venn_undercoverage_run_count'))} "
                "undercoverage runs and validated-regression support flag "
                f"`{summary_payload.get('venn_can_support_validated_regression')}`."
            ),
            "what_it_cannot_support": (
                "It cannot reject predictive-distribution or generalized "
                "Venn-Abers research."
            ),
            "reader_action": (
                "Report the bridge result as negative evidence exactly at the "
                "evaluated bridge scope."
            ),
        },
        {
            "evidence_layer": "Closed gates",
            "what_it_can_support": (
                "Closed gates identify claims that the current evidence is not "
                "allowed to make."
            ),
            "evidence_in_this_study": (
                "Bounded-support-validity-ready bundles "
                f"{fmt(summary_payload.get('bounded_support_validity_ready_bundle_count'))}; "
                "population-fairness-ready bundles "
                f"{fmt(summary_payload.get('fairness_population_ready_bundle_count'))}; "
                f"KG citable component authorized "
                f"`{summary_payload.get('kg_citable_component_authorized')}`."
            ),
            "what_it_cannot_support": (
                "Closed gates cannot be reopened by optimistic prose, README "
                "wording, or site polish."
            ),
            "reader_action": (
                "Treat closed gates as scientific results and release boundaries."
            ),
        },
    ]


def build_claim_language_guardrail_rows(
    claim_matrix: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = claim_matrix.get("claim_review_rows") or []
    if not isinstance(rows, list):
        return []

    def claim_safe_text(value: Any) -> str:
        return (
            str(value or "")
            .replace("final winner", "final selected method")
            .replace("winner", "selected method")
            .replace("definitively better", "definitively preferred")
        )

    return [
        {
            "claim_review_id": row.get("claim_review_id"),
            "target_document": row.get("target_document"),
            "claim_type": row.get("claim_type"),
            "allowed_publication_sentence": claim_safe_text(
                row.get("allowed_publication_sentence")
            ),
            "citation_gate": claim_safe_text(row.get("citation_gate")),
            "overclaim_blocked": claim_safe_text(row.get("overclaim_blocked")),
            "non_specialist_explanation": claim_safe_text(
                row.get("non_specialist_explanation")
            ),
            "claim_review_status": row.get("claim_review_status"),
            "support_status": row.get("support_status"),
        }
        for row in sorted(rows, key=lambda item: int(item.get("row_index") or 0))
        if isinstance(row, dict)
    ]


def check_row(check_id: str, passed: bool, evidence: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "blocker": blocker,
    }


def build_payload(root: Path) -> dict[str, Any]:
    decision = read_json(root / AUTHORING_DECISION)
    main = read_json(root / MAIN_ARTICLE)
    supplement = read_json(root / SUPPLEMENT)
    individual = read_json(root / INDIVIDUAL_REPORT)
    claim_matrix = read_json(root / CLAIM_MATRIX)
    citations = read_json(root / CITATION_REGISTRY)
    kg_quality = read_json(root / KG_QUALITY)
    private_package = read_json(root / PRIVATE_PACKAGE)
    exemplar_review = read_json(root / PUBLICATION_EXEMPLAR_REVIEW)
    cqr_model_matched = read_json(root / CQR_MODEL_MATCHED_SYNTHESIS)

    decision_s = summary(decision)
    main_s = summary(main)
    supplement_s = summary(supplement)
    individual_s = summary(individual)
    facts = individual.get("report_facts") or {}
    claim_s = summary(claim_matrix)
    kg_graph = kg_quality.get("graph") or {}
    kg_traceability = kg_quality.get("traceability") or {}
    private_package_s = summary(private_package)
    exemplar_s = summary(exemplar_review)
    cqr_model_matched_s = summary(cqr_model_matched)
    cqr_backend_counts = (
        cqr_model_matched_s.get("coverage_eligible_interval_score_selected_counts")
        or {}
    )
    cite = citation_keys(citations)
    reader_contract_rows = build_reader_contract_rows()
    primer_rows = build_reader_primer_rows()
    citation_backed_concept_rows = build_citation_backed_concept_rows(cite)
    method_mechanics_rows = build_method_mechanics_rows()
    guarantee_boundary_rows = build_guarantee_boundary_rows()
    result_reading_rows = build_result_reading_rows()
    claim_guardrail_rows = build_claim_language_guardrail_rows(claim_matrix)
    design_decision_rows = exemplar_review.get("design_decision_rows") or []

    sources = {
        "publication_authoring_decision_record": str(AUTHORING_DECISION),
        "main_article_draft": str(MAIN_ARTICLE),
        "supplementary_document_draft": str(SUPPLEMENT),
        "individual_experiment_report_draft": str(INDIVIDUAL_REPORT),
        "publication_claim_evidence_verification_matrix": str(CLAIM_MATRIX),
        "publication_citation_registry": str(CITATION_REGISTRY),
        "knowledge_graph_quality_summary": str(KG_QUALITY),
        "private_sterile_publication_package_manifest": str(PRIVATE_PACKAGE),
        "publication_exemplar_review": str(PUBLICATION_EXEMPLAR_REVIEW),
        "cqr_fixed_vs_model_matched_synthesis": str(CQR_MODEL_MATCHED_SYNTHESIS),
    }
    missing_sources = [path for path in sources.values() if not (root / path).exists()]
    missing_citations = [url for url in required_citation_urls() if url not in cite]

    sections = [
        {
            "section_id": "abstract",
            "claim_role": "neutral_scope_result_boundary_summary",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_authoring_decision_record",
            ],
        },
        {
            "section_id": "executive_synthesis",
            "claim_role": "private_review_executive_synthesis_no_method_recommendation",
            "evidence_sources": [
                "main_article_draft",
                "supplementary_document_draft",
                "cqr_fixed_vs_model_matched_synthesis",
                "publication_claim_evidence_verification_matrix",
                "knowledge_graph_quality_summary",
                "private_sterile_publication_package_manifest",
            ],
        },
        {
            "section_id": "plain_language_summary",
            "claim_role": "non_specialist_headline_result_and_boundary_summary",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "main_article_draft",
                "supplementary_document_draft",
                "cqr_fixed_vs_model_matched_synthesis",
                "publication_claim_evidence_verification_matrix",
                "knowledge_graph_quality_summary",
                "private_sterile_publication_package_manifest",
            ],
        },
        {
            "section_id": "research_questions",
            "claim_role": "research_question_answer_evidence_boundary_map",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "main_article_draft",
                "supplementary_document_draft",
                "cqr_fixed_vs_model_matched_synthesis",
                "publication_claim_evidence_verification_matrix",
                "knowledge_graph_quality_summary",
            ],
        },
        {
            "section_id": "reader_primer",
            "claim_role": "plain_language_method_primer_with_citations",
            "evidence_sources": [
                "publication_citation_registry",
                "main_article_draft",
            ],
        },
        {
            "section_id": "contribution_finding_map",
            "claim_role": "reader_safe_contribution_and_finding_summary",
            "evidence_sources": [
                "main_article_draft",
                "supplementary_document_draft",
                "cqr_fixed_vs_model_matched_synthesis",
                "publication_claim_evidence_verification_matrix",
                "knowledge_graph_quality_summary",
                "private_sterile_publication_package_manifest",
            ],
        },
        {
            "section_id": "scientific_method_audit_trail",
            "claim_role": "research_question_measurement_falsification_traceability_chain",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "main_article_draft",
                "supplementary_document_draft",
                "cqr_fixed_vs_model_matched_synthesis",
                "publication_claim_evidence_verification_matrix",
                "knowledge_graph_quality_summary",
                "private_sterile_publication_package_manifest",
            ],
        },
        {
            "section_id": "private_review_decision_protocol",
            "claim_role": "private_review_acceptance_and_closed_release_decisions",
            "evidence_sources": [
                "publication_claim_evidence_verification_matrix",
                "knowledge_graph_quality_summary",
                "private_sterile_publication_package_manifest",
                "publication_authoring_decision_record",
            ],
        },
        {
            "section_id": "publication_design_basis",
            "claim_role": "source_backed_publication_package_design_basis",
            "evidence_sources": [
                "publication_exemplar_review",
                "publication_citation_registry",
            ],
        },
        {
            "section_id": "guarantee_boundary_ledger",
            "claim_role": "theory_empirical_and_closed_reading_separation",
            "evidence_sources": [
                "publication_citation_registry",
                "publication_claim_evidence_verification_matrix",
                "knowledge_graph_quality_summary",
            ],
        },
        {
            "section_id": "empirical_design",
            "claim_role": "audited_resumeable_experiment_design_and_controls",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "publication_claim_evidence_verification_matrix",
            ],
        },
        {
            "section_id": "results",
            "claim_role": "observed_candidate_patterns_no_recommendation",
            "evidence_sources": [
                "main_article_draft",
                "supplementary_document_draft",
                "cqr_fixed_vs_model_matched_synthesis",
            ],
        },
        {
            "section_id": "negative_evidence",
            "claim_role": "robustness_integrity_and_negative_evidence",
            "evidence_sources": [
                "individual_experiment_report_draft",
                "supplementary_document_draft",
                "publication_authoring_decision_record",
            ],
        },
        {
            "section_id": "claim_boundaries",
            "claim_role": "positive_claims_remain_closed",
            "evidence_sources": [
                "publication_claim_evidence_verification_matrix",
                "publication_authoring_decision_record",
            ],
        },
        {
            "section_id": "claim_language_guardrails",
            "claim_role": "safe_sentence_citation_gate_and_overclaim_control",
            "evidence_sources": [
                "publication_claim_evidence_verification_matrix",
                "publication_citation_registry",
                "knowledge_graph_quality_summary",
            ],
        },
        {
            "section_id": "reproducibility_and_kg",
            "claim_role": "browsable_kg_candidate_and_traceability",
            "evidence_sources": [
                "knowledge_graph_quality_summary",
                "publication_authoring_decision_record",
            ],
        },
        {
            "section_id": "artifact_reading_path",
            "claim_role": "private_review_artifact_navigation",
            "evidence_sources": [
                "private_sterile_publication_package_manifest",
                "knowledge_graph_quality_summary",
            ],
        },
    ]

    checks = [
        check_row(
            "source_artifacts_present",
            not missing_sources,
            {"missing_sources": missing_sources},
            "research_document_source_missing",
        ),
        check_row(
            "authoring_decision_allows_private_research_document",
            decision_s.get("research_document_authoring_authorized") is True
            and decision_s.get("final_public_release_authorized") is False,
            {
                "research_document_authoring_authorized": decision_s.get(
                    "research_document_authoring_authorized"
                ),
                "final_public_release_authorized": decision_s.get(
                    "final_public_release_authorized"
                ),
            },
            "research_document_authoring_not_authorized",
        ),
        check_row(
            "required_citations_registered",
            not missing_citations,
            {"missing_citations": missing_citations},
            "research_document_missing_required_citations",
        ),
        check_row(
            "claim_boundaries_closed",
            claim_s.get("method_recommendation_authorized") is False
            and claim_s.get("positive_claim_promotion_authorized") is False
            and claim_s.get("release_authorized") is False,
            {
                "method_recommendation_authorized": claim_s.get(
                    "method_recommendation_authorized"
                ),
                "positive_claim_promotion_authorized": claim_s.get(
                    "positive_claim_promotion_authorized"
                ),
                "release_authorized": claim_s.get("release_authorized"),
            },
            "research_document_claim_boundary_open",
        ),
        check_row(
            "kg_traceability_available",
            int(kg_graph.get("node_count") or 0) == int(main_s.get("kg_node_count") or 0)
            and int(kg_graph.get("isolated_node_count") or 0) == 0,
            {
                "kg_node_count": kg_graph.get("node_count"),
                "main_article_kg_node_count": main_s.get("kg_node_count"),
                "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
            },
            "research_document_kg_traceability_mismatch",
        ),
        check_row(
            "publication_exemplar_review_ready",
            exemplar_s.get("overall_status") == "publication_exemplar_review_ready"
            and exemplar_s.get("method_recommendation_authorized") is False
            and exemplar_s.get("public_release_authorized") is False,
            {
                "publication_exemplar_review_status": exemplar_s.get("overall_status"),
                "method_recommendation_authorized": exemplar_s.get(
                    "method_recommendation_authorized"
                ),
                "public_release_authorized": exemplar_s.get("public_release_authorized"),
            },
            "research_document_publication_exemplar_review_not_ready",
        ),
        check_row(
            "private_review_package_supports_document_navigation",
            private_package_s.get("overall_status")
            == "private_sterile_publication_package_ready"
            and private_package_s.get("public_release_authorized") is False
            and private_package_s.get("method_recommendation_authorized") is False
            and int(kg_graph.get("isolated_node_count") or 0) == 0,
            {
                "private_package_status": private_package_s.get("overall_status"),
                "public_release_authorized": private_package_s.get(
                    "public_release_authorized"
                ),
                "method_recommendation_authorized": private_package_s.get(
                    "method_recommendation_authorized"
                ),
                "kg_browser_node_count": private_package_s.get(
                    "kg_browser_node_count"
                ),
                "kg_browser_edge_count": private_package_s.get(
                    "kg_browser_edge_count"
                ),
                "source_kg_node_count": kg_graph.get("node_count"),
                "source_kg_edge_count": kg_graph.get("edge_count"),
                "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
            },
            "research_document_private_navigation_not_ready",
        ),
        check_row(
            "claim_language_guardrails_complete",
            len(claim_guardrail_rows) == int(claim_s.get("claim_review_row_count") or 0)
            and all(
                row.get("claim_review_status") == "pass"
                and row.get("allowed_publication_sentence")
                and row.get("citation_gate")
                and row.get("overclaim_blocked")
                and row.get("non_specialist_explanation")
                for row in claim_guardrail_rows
            ),
            {
                "claim_language_guardrail_row_count": len(claim_guardrail_rows),
                "claim_review_row_count": claim_s.get("claim_review_row_count"),
                "claim_review_status_counts": claim_s.get(
                    "claim_review_status_counts"
                ),
            },
            "research_document_claim_language_guardrail_missing",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]

    summary_payload = {
        "overall_status": (
            "research_document_private_authoring_ready"
            if not failed_checks
            else "research_document_private_authoring_blocked"
        ),
        "research_document_authoring_authorized": not failed_checks,
        "public_release_authorized": False,
        "publication_site_deployment_authorized": False,
        "kg_citable_component_authorized": False,
        "author_name": AUTHOR_NAME,
        "author_role": AUTHOR_ROLE,
        "author_email": AUTHOR_EMAIL,
        "author_header": f"Author: {AUTHOR_NAME}, {AUTHOR_ROLE}",
        "method_recommendation_authorized": False,
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "positive_claim_promotion_authorized": False,
        "new_experiments_authorized": False,
        "publication_completed_rows": main_s.get(
            "publication_completed_rows", individual_s.get("publication_completed_rows")
        ),
        "dataset_count": main_s.get("dataset_count", individual_s.get("dataset_count")),
        "dataset_alpha_cell_count": main_s.get(
            "dataset_alpha_cell_count", individual_s.get("dataset_alpha_cell_count")
        ),
        "method_count": main_s.get("method_count", individual_s.get("method_count")),
        "cqr_frontier_cell_count": main_s.get("cqr_frontier_cell_count"),
        "cv_plus_frontier_cell_count": main_s.get("cv_plus_frontier_cell_count"),
        "mondrian_frontier_cell_count": main_s.get("mondrian_frontier_cell_count"),
        "cqr_backend_sensitivity_status": cqr_model_matched_s.get("status"),
        "cqr_backend_sensitivity_fixed_gbm_completed_rows": cqr_model_matched_s.get(
            "fixed_gbm_cqr_completed_rows"
        ),
        "cqr_backend_sensitivity_model_matched_completed_rows": cqr_model_matched_s.get(
            "model_matched_cqr_completed_rows"
        ),
        "cqr_backend_sensitivity_paired_cell_count": cqr_model_matched_s.get(
            "paired_cell_count"
        ),
        "cqr_backend_sensitivity_cell_count": cqr_model_matched_s.get("cell_count"),
        "cqr_backend_sensitivity_selected_counts": cqr_backend_counts,
        "cqr_backend_sensitivity_fixed_gbm_selected_count": cqr_backend_counts.get(
            "fixed_gbm_cqr"
        ),
        "cqr_backend_sensitivity_model_matched_selected_count": cqr_backend_counts.get(
            "model_matched_cqr"
        ),
        "cqr_backend_sensitivity_no_coverage_eligible_count": cqr_backend_counts.get(
            "no_coverage_eligible_variant"
        ),
        "cqr_backend_sensitivity_can_support_method_winner_claim": (
            cqr_model_matched_s.get("can_support_method_winner_claim")
        ),
        "cqr_backend_sensitivity_method_boundary": cqr_model_matched_s.get(
            "method_boundary"
        ),
        "cqr_row_weighted_coverage_mean": facts.get("cqr_row_weighted_coverage_mean"),
        "cqr_row_weighted_coverage_ci95": facts.get("cqr_row_weighted_coverage_ci95"),
        "cv_plus_row_weighted_coverage_mean": facts.get(
            "cv_plus_row_weighted_coverage_mean"
        ),
        "mondrian_row_weighted_coverage_mean": facts.get(
            "mondrian_row_weighted_coverage_mean"
        ),
        "venn_undercoverage_run_count": main_s.get("venn_undercoverage_run_count"),
        "venn_abers_quantile_coverage_mean": facts.get(
            "venn_abers_quantile_coverage_mean"
        ),
        "venn_abers_quantile_near_nominal_hit_rate": facts.get(
            "venn_abers_quantile_near_nominal_hit_rate"
        ),
        "venn_can_support_validated_regression": facts.get(
            "venn_can_support_validated_regression"
        ),
        "cqr_nominal_hit_rate": facts.get("cqr_nominal_hit_rate"),
        "cqr_near_nominal_hit_rate": facts.get("cqr_near_nominal_hit_rate"),
        "cv_plus_near_nominal_hit_rate": facts.get("cv_plus_near_nominal_hit_rate"),
        "mondrian_near_nominal_hit_rate": facts.get(
            "mondrian_near_nominal_hit_rate"
        ),
        "robustness_common_cell_selected_method": facts.get(
            "robustness_common_cell_selected_method"
        ),
        "robustness_common_cell_winner_counts": facts.get(
            "robustness_common_cell_winner_counts"
        ),
        "robustness_bootstrap_selection_counts": facts.get(
            "robustness_bootstrap_selection_counts"
        ),
        "robustness_leave_one_dataset_retention_rate": facts.get(
            "robustness_leave_one_dataset_retention_rate"
        ),
        "robustness_leave_one_alpha_retention_rate": facts.get(
            "robustness_leave_one_alpha_retention_rate"
        ),
        "duplicate_action_count": supplement_s.get("duplicate_action_count"),
        "duplicate_quarantined_action_count": supplement_s.get(
            "duplicate_quarantined_action_count"
        ),
        "duplicate_unquarantined_action_count": supplement_s.get(
            "duplicate_unquarantined_action_count"
        ),
        "cross_run_leakage_status": supplement_s.get("cross_run_leakage_status"),
        "cross_run_unsupported_claim_hits": supplement_s.get(
            "cross_run_unsupported_claim_hits"
        ),
        "bounded_bundle_count": supplement_s.get("bounded_bundle_count"),
        "bounded_raw_endpoint_excursion_bundle_count": supplement_s.get(
            "bounded_raw_endpoint_excursion_bundle_count"
        ),
        "fairness_bundle_count": supplement_s.get("fairness_bundle_count"),
        "fairness_pairwise_group_comparison_count": supplement_s.get(
            "fairness_pairwise_group_comparison_count"
        ),
        "bounded_support_validity_ready_bundle_count": main_s.get(
            "bounded_support_validity_ready_bundle_count"
        ),
        "fairness_population_ready_bundle_count": main_s.get(
            "fairness_population_ready_bundle_count"
        ),
        "supplement_section_count": supplement_s.get("supplement_section_count"),
        "kg_node_count": kg_graph.get("node_count"),
        "kg_edge_count": kg_graph.get("edge_count"),
        "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
        "kg_average_edge_confidence": kg_traceability.get("average_edge_confidence"),
        "kg_edge_selector_provenance_coverage": kg_traceability.get(
            "edge_selector_provenance_coverage"
        ),
        "private_review_surface_count": private_package_s.get(
            "generated_review_surface_count"
        ),
        "private_review_surface_pass_count": private_package_s.get(
            "generated_review_surface_pass_count"
        ),
        "kg_browser_node_count": private_package_s.get("kg_browser_node_count"),
        "kg_browser_edge_count": private_package_s.get("kg_browser_edge_count"),
        "kg_browser_node_type_count": private_package_s.get(
            "kg_browser_node_type_count"
        ),
        "kg_browser_relation_type_count": private_package_s.get(
            "kg_browser_relation_type_count"
        ),
        "reader_contract_row_count": len(reader_contract_rows),
        "reader_primer_term_count": len(primer_rows),
        "citation_backed_concept_row_count": len(citation_backed_concept_rows),
        "method_mechanics_row_count": len(method_mechanics_rows),
        "guarantee_boundary_row_count": len(guarantee_boundary_rows),
        "result_reading_row_count": len(result_reading_rows),
        "claim_language_guardrail_row_count": len(claim_guardrail_rows),
        "claim_review_row_count": claim_s.get("claim_review_row_count"),
        "claim_review_supported_count": claim_s.get("claim_review_supported_count"),
        "claim_review_citation_gate_count": claim_s.get(
            "claim_review_citation_gate_count"
        ),
        "claim_review_overclaim_blocked_count": claim_s.get(
            "claim_review_overclaim_blocked_count"
        ),
        "claim_review_non_specialist_explanation_count": claim_s.get(
            "claim_review_non_specialist_explanation_count"
        ),
        "claim_review_status_counts": claim_s.get("claim_review_status_counts"),
        "publication_exemplar_source_row_count": exemplar_s.get(
            "external_source_row_count"
        ),
        "publication_exemplar_design_decision_row_count": exemplar_s.get(
            "design_decision_row_count"
        ),
        "failed_check_count": len(failed_checks),
    }
    contribution_finding_rows = build_contribution_finding_rows(summary_payload)
    research_question_rows = build_research_question_rows(summary_payload)
    scientific_method_rows = build_scientific_method_rows(summary_payload)
    private_review_decision_rows = build_private_review_decision_rows(summary_payload)
    result_interpretation_ladder_rows = build_result_interpretation_ladder_rows(
        summary_payload
    )
    summary_payload["contribution_finding_row_count"] = len(contribution_finding_rows)
    summary_payload["research_question_row_count"] = len(research_question_rows)
    summary_payload["scientific_method_row_count"] = len(scientific_method_rows)
    summary_payload["private_review_decision_row_count"] = len(
        private_review_decision_rows
    )
    summary_payload["result_interpretation_ladder_row_count"] = len(
        result_interpretation_ladder_rows
    )
    plain_language_summary_rows = build_plain_language_summary_rows(summary_payload)
    summary_payload["plain_language_summary_row_count"] = len(
        plain_language_summary_rows
    )
    executive_synthesis_rows = build_executive_synthesis_rows(summary_payload)
    summary_payload["executive_synthesis_paragraph_count"] = len(
        executive_synthesis_rows
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "summary": summary_payload,
        "sections": sections,
        "reader_contract_rows": reader_contract_rows,
        "executive_synthesis_rows": executive_synthesis_rows,
        "plain_language_summary_rows": plain_language_summary_rows,
        "research_question_rows": research_question_rows,
        "contribution_finding_rows": contribution_finding_rows,
        "scientific_method_rows": scientific_method_rows,
        "private_review_decision_rows": private_review_decision_rows,
        "reader_primer_rows": primer_rows,
        "citation_backed_concept_rows": citation_backed_concept_rows,
        "method_mechanics_rows": method_mechanics_rows,
        "guarantee_boundary_rows": guarantee_boundary_rows,
        "result_reading_rows": result_reading_rows,
        "result_interpretation_ladder_rows": result_interpretation_ladder_rows,
        "claim_language_guardrail_rows": claim_guardrail_rows,
        "publication_design_decision_rows": design_decision_rows,
        "citation_keys": {
            url: cite[url] for url in required_citation_urls() if url in cite
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This Research Document is a Research Atlas narrative, not a method recommendation.",
            "CQR/CV+ are described as strong practical candidates observed in this experiment, not as recommended methods.",
            "The model-matched CQR rerun is a backend-sensitivity check, not a method-selection claim.",
            "The evaluated Venn-Abers regression bridge is described as negative/failure-mode evidence.",
            "Positive fairness, bounded-support validity, validated Venn-Abers regression, production, and best-method claims remain closed.",
            "The KG is prepared as a browsable supplementary/web traceability artifact; it is not an independent scientific claim.",
            "No new experiments are authorized or required for this document.",
            "Publication-package design examples are used only to improve navigation and source traceability.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    executive_synthesis_rows = payload["executive_synthesis_rows"]
    plain_language_summary_rows = payload["plain_language_summary_rows"]
    research_question_rows = payload["research_question_rows"]
    contribution_finding_rows = payload["contribution_finding_rows"]
    scientific_method_rows = payload["scientific_method_rows"]
    private_review_decision_rows = payload["private_review_decision_rows"]
    primer_rows = payload["reader_primer_rows"]
    citation_backed_concept_rows = payload["citation_backed_concept_rows"]
    method_mechanics_rows = payload["method_mechanics_rows"]
    guarantee_boundary_rows = payload["guarantee_boundary_rows"]
    result_reading_rows = payload["result_reading_rows"]
    result_interpretation_ladder_rows = payload["result_interpretation_ladder_rows"]
    claim_guardrail_rows = payload["claim_language_guardrail_rows"]
    design_rows = payload["publication_design_decision_rows"]
    cite = payload["citation_keys"]
    split_key = cite["https://arxiv.org/abs/1604.04173"]
    cqr_key = cite["https://arxiv.org/abs/1905.03222"]
    jack_key = cite["https://arxiv.org/abs/1905.02928"]
    jab_key = cite["https://arxiv.org/abs/2002.09025"]
    venn18_key = cite["https://proceedings.mlr.press/v91/nouretdinov18a.html"]
    venn24_key = cite["https://proceedings.mlr.press/v230/nouretdinov24a.html"]
    vanderlaan_key = cite["https://proceedings.mlr.press/v267/van-der-laan25a.html"]
    ivar_key = cite["https://arxiv.org/html/2605.06646v1"]
    ci = s["cqr_row_weighted_coverage_ci95"] or {}
    winner_counts = s["robustness_common_cell_winner_counts"] or {}
    bootstrap_counts = s["robustness_bootstrap_selection_counts"] or {}

    lines = [
        "# Research Document",
        "",
        "## Regression Conformal Prediction Under Neutral Claim Boundaries",
        "",
        f"Author: {AUTHOR_NAME}, {AUTHOR_ROLE}",
        f"Email: {AUTHOR_EMAIL}",
        "",
        (
            "> Research Atlas status: public-facing wording is descriptive and "
            "experiment-scoped; no universal method selection or production "
            "recommendation is claimed."
        ),
        "",
        "## Abstract",
        "",
        (
            "This Research Document reports a neutral empirical study of regression "
            "conformal prediction. The study aggregates "
            f"{fmt(s['publication_completed_rows'])} publication-scoped completed "
            f"rows across {fmt(s['dataset_count'])} datasets, "
            f"{fmt(s['dataset_alpha_cell_count'])} dataset-alpha cells, and "
            f"{fmt(s['method_count'])} conformal-method labels. The purpose is not "
            "to name a universal final selected method. The purpose is to "
            "document what the audited experiment observed, what the evidence "
            "can support, and what claims remain closed."
        ),
        "",
        (
            "CQR/CV+ were observed as strong practical candidates in these "
            "experiments. CQR has the largest current descriptive frontier count "
            f"({fmt(s['cqr_frontier_cell_count'])} cells), while CV+ contributes "
            f"{fmt(s['cv_plus_frontier_cell_count'])} frontier cells. The evaluated "
            "backend-confound check completed "
            f"{fmt(s['cqr_backend_sensitivity_model_matched_completed_rows'])} "
            "model-matched CQR rows and compared "
            f"{fmt(s['cqr_backend_sensitivity_paired_cell_count'])} paired "
            "dataset-alpha-model-family cells; it supports a backend-sensitivity "
            "reading but not a method-selection claim. The evaluated "
            "Venn-Abers regression bridge did not behave as the expected strong "
            f"regression solution: it produced {fmt(s['venn_undercoverage_run_count'])} "
            "undercoverage runs and a low quantile-coverage mean in the current "
            "diagnostic bridge. These statements are descriptive. They are not "
            "method recommendations."
        ),
        "",
        (
            "Read this document in four layers. First, identify the empirical object "
            "that was audited. Second, separate observed practical-candidate patterns "
            "from recommendations. Third, keep negative Venn-Abers bridge evidence "
            "separate from the broader Venn-Abers literature. Fourth, treat the "
            "package, KG, and site as private traceability surfaces until explicit "
            "release authorization exists."
        ),
        "",
        "| Reading layer | Reader question | Safe reading | Boundary |",
        "|---|---|---|---|",
    ]
    for row in payload["reader_contract_rows"]:
        lines.append(
            "| "
            f"{row['reading_layer']} | "
            f"{row['reader_question']} | "
            f"{row['safe_reading']} | "
            f"{row['boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Executive Synthesis",
            "",
            (
                "This synthesis states the document's position before the detailed "
                "tables. It is written for a reviewer who needs to understand the "
                "scientific result, the negative evidence, and the release boundary "
                "without first reading every audit artifact."
            ),
            "",
        ]
    )
    for row in executive_synthesis_rows:
        lines.extend(
            [
                f"### {row['heading']}",
                "",
                row["body"],
                "",
                f"Boundary: {row['boundary']}",
                "",
            ]
        )
    lines.extend(
        [
            "",
        "## Plain-Language Summary",
        "",
        (
            "This section gives the shortest reader-safe interpretation before "
            "the technical tables. It is written for a reader who may not know "
            "conformal prediction. Each answer is paired with the evidence that "
            "supports it and the stronger reading that remains closed."
        ),
        "",
        "| Reader question | Plain-language answer | Evidence anchor | Boundary |",
        "|---|---|---|---|",
        ]
    )
    for row in plain_language_summary_rows:
        lines.append(
            "| "
            f"{row['reader_question']} | "
            f"{row['plain_language_answer']} | "
            f"{row['evidence_anchor']} | "
            f"{row['boundary']} |"
        )
    lines.extend(
        [
            "",
        "## Research Questions And Answers",
        "",
        (
            "The table below gives the reader a compact map of the study's "
            "research questions, the answer currently supported by the evidence, "
            "the artifact family that supports the answer, and the stronger "
            "interpretation that remains closed. It is a writing and review "
            "map, not a new experiment."
        ),
        "",
        "| Research question | Evidence-supported answer | Evidence anchor | Closed reading |",
        "|---|---|---|---|",
        ]
    )
    for row in research_question_rows:
        lines.append(
            "| "
            f"{row['research_question']} | "
            f"{row['short_answer']} | "
            f"{row['evidence_anchor']} | "
            f"{row['closed_reading']} |"
        )
    lines.extend(
        [
            "",
        "## Contribution And Finding Map",
        "",
        (
            "This map states the document's contribution and core empirical "
            "findings in a form that can be read before the technical sections. "
            "Each row includes the evidence anchor and the stronger reading that "
            "remains closed."
        ),
        "",
        "| Contribution or finding | Reader-safe statement | Evidence anchor | Closed reading |",
        "|---|---|---|---|",
        ]
    )
    for row in contribution_finding_rows:
        lines.append(
            "| "
            f"{row['contribution_or_finding']} | "
            f"{row['reader_safe_statement']} | "
            f"{row['evidence_anchor']} | "
            f"{row['closed_reading']} |"
        )
    lines.extend(
        [
            "",
            "## Scientific Method Audit Trail",
            "",
            (
                "This table rewrites the study as a scientific-method chain: "
                "question, measurement, comparison, falsification, closed "
                "positive claims, and reproducibility. It is included so a "
                "reader can see why the document reports both strong practical "
                "candidate patterns and negative or blocked conclusions."
            ),
            "",
            "| Stage | Reader question | Evidence anchor | Scientific boundary |",
            "|---|---|---|---|",
        ]
    )
    for row in scientific_method_rows:
        lines.append(
            "| "
            f"{row['stage']} | "
            f"{row['reader_question']} | "
            f"{row['evidence_anchor']} | "
            f"{row['scientific_boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Private Review Decision Protocol",
            "",
            (
                "This protocol states what a private reviewer may accept at this "
                "stage and which decisions remain closed. It is deliberately "
                "stricter than a normal manuscript checklist because the same "
                "artifact set can look publication-ready while public release, "
                "KG citation, final submission prose, and method recommendation "
                "remain unauthorized."
            ),
            "",
            "| Decision point | Accept private review if | Evidence to check | Still closed |",
            "|---|---|---|---|",
        ]
    )
    for row in private_review_decision_rows:
        lines.append(
            "| "
            f"{row['decision_point']} | "
            f"{row['accept_if']} | "
            f"{row['evidence_to_check']} | "
            f"{row['still_closed']} |"
        )
    lines.extend(
        [
            "",
            "## 1. Reader Primer",
            "",
            (
                "Regression conformal prediction wraps a regression model with a "
                "prediction interval calibrated to a target coverage level. The "
                "usual notation is `1 - alpha`, where `alpha` is the target "
                f"miscoverage rate [@{split_key}]. Split conformal regression uses "
                "a calibration set to estimate a score quantile. Conformalized "
                "quantile regression, or CQR, instead starts from lower and upper "
                f"quantile models and then conformalizes the resulting interval "
                f"[@{cqr_key}]. Jackknife+ and CV+ use leave-one-out or out-of-fold "
                f"predictions to account for fitted-model variability "
                f"[@{jack_key}; @{jab_key}]."
            ),
            "",
        (
            "Venn-Abers methods belong to a related but distinct calibration "
            "family. The literature includes Venn-Abers predictive distributions "
            "and generalized formulations, not merely ordinary interval wrappers "
            f"[@{venn18_key}; @{venn24_key}; @{vanderlaan_key}; @{ivar_key}]. "
            "For that reason, the present study does not claim to invalidate the "
            "Venn-Abers literature. It reports that the evaluated regression "
            "bridge did not validate as a strong interval solution in this "
            "experiment."
        ),
        "",
        "### Citation-Backed Concept Map",
        "",
        (
            "The concept map below links the plain-language idea, its literature "
            "basis, the experiment anchor in this study, and the reading that "
            "remains closed. It is included so non-specialist readers can see "
            "which parts are conformal prediction background, which parts are "
            "empirical observations, and which parts are governance boundaries."
        ),
        "",
        "| Concept | Reader question | Literature basis | Experiment anchor | Closed reading |",
        "|---|---|---|---|---|",
        ]
    )
    for row in citation_backed_concept_rows:
        citations = "; ".join(f"@{key}" for key in row["citation_keys"])
        lines.append(
            "| "
            f"{row['concept']} | "
            f"{row['reader_question']} | "
            f"{row['literature_basis']} [{citations}] | "
            f"{row['experiment_anchor']} | "
            f"{row['closed_reading']} |"
        )
    lines.extend(
        [
            "",
        "### Terminology Compass",
        "",
        (
            "The following table fixes the meaning of recurring terms before the "
            "results are interpreted. Each term is defined as it is used in this "
            "Research Document. The last column states the boundary that prevents "
            "a descriptive result from becoming a recommendation."
        ),
        "",
        "| Term | Plain-language meaning | Role in this document | Boundary |",
        "|---|---|---|---|",
        ]
    )
    for row in primer_rows:
        lines.append(
            "| `{}` | {} | {} | {} |".format(
                row["term"],
                row["plain_language_meaning"],
                row["research_document_role"],
                row["evidence_boundary"],
            )
        )
    lines.extend(
        [
            "",
            "### How To Interpret `1 - alpha`",
            "",
            (
                "`1 - alpha` is the target coverage level, not an observed "
                "success rate. For example, if `alpha = 0.10`, the target "
                "coverage is 0.90. A conformal method can be judged against "
                "that target only after specifying the dataset, split policy, "
                "calibration method, and scoring rule. This Research Document "
                "therefore reports coverage, near-nominal behavior, frontier "
                "membership, and closed gates as scoped empirical diagnostics "
                f"rather than theorem claims [@{split_key}; @{cqr_key}]."
            ),
            "",
            (
                "This distinction matters for non-specialist readers. A method "
                "can show attractive empirical coverage in this study and still "
                "remain inappropriate as a general recommendation. Conversely, "
                "a failure mode for one evaluated bridge does not reject an "
                "entire research family. The document keeps both sides visible "
                "so the later article, supplement, and KG can cite exactly what "
                "was observed."
            ),
            "",
            "### Guarantee Boundary Ledger",
            "",
            (
                "The ledger below separates three layers that are easy to confuse: "
                "the conformal prediction theorem layer, the empirical audit layer, "
                "and the closed-claim layer. It is a reader-safety device, not a "
                "new theorem and not a new experiment. The marginal coverage "
                f"language follows the regression conformal prediction sources "
                f"[@{split_key}; @{cqr_key}], while the Venn-Abers row is bounded "
                f"by the predictive-distribution and generalized-calibration "
                f"sources [@{venn18_key}; @{venn24_key}; @{vanderlaan_key}; "
                f"@{ivar_key}]."
            ),
            "",
            "| Topic | Reader-safe statement | Required condition or evidence | Closed reading |",
            "|---|---|---|---|",
        ]
    )
    for row in guarantee_boundary_rows:
        lines.append(
            "| "
            f"{row['topic']} | "
            f"{row['reader_safe_statement']} | "
            f"{row['required_condition_or_evidence']} | "
            f"{row['closed_reading']} |"
        )
    lines.extend(
        [
            "",
            "### Method Mechanics At A Glance",
            "",
            (
                "The table below explains how each method family creates or "
                "adjusts prediction intervals before the empirical results are "
                "read. It is intentionally operational: the goal is to show what "
                "changes the interval, and what this study is not allowed to "
                "claim from that mechanism."
            ),
            "",
            "| Method family | What it does | What the interval depends on | Study boundary |",
            "|---|---|---|---|",
        ]
    )
    for row in method_mechanics_rows:
        lines.append(
            "| "
            f"{row['method_family']} | "
            f"{row['what_it_does']} | "
            f"{row['what_the_interval_depends_on']} | "
            f"{row['study_boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Publication Design Basis",
            "",
            (
                "Before the private Research Document, supplement, README, and "
                "site are treated as reviewable publication surfaces, their "
                "structure is checked against a small source-backed review of "
                "comparable conformal prediction papers, repositories, docs, and "
                "sites. This review contributes navigation and traceability "
                "decisions only. It does not add experiments and does not "
                "recommend a conformal method."
            ),
            "",
            "| Design decision | Project application |",
            "|---|---|",
        ]
    )
    for row in design_rows:
        lines.append(
            "| "
            f"{row['decision']} | "
            f"{row['project_application']} |"
        )
    lines.extend(
        [
            "",
            "## 2. Experimental Scope",
            "",
            "| Scope item | Value | Interpretation |",
            "|---|---:|---|",
            f"| Publication-scoped completed rows | {fmt(s['publication_completed_rows'])} | Audited empirical accounting scope |",
            f"| Datasets | {fmt(s['dataset_count'])} | Public regression dataset scope |",
            f"| Dataset-alpha cells | {fmt(s['dataset_alpha_cell_count'])} | Calibration comparison cells |",
            f"| Conformal-method labels | {fmt(s['method_count'])} | Broad conformal method surface |",
            f"| Model-matched CQR completed rows | {fmt(s['cqr_backend_sensitivity_model_matched_completed_rows'])} | Backend-confound sensitivity check |",
            f"| CQR fixed-vs-model-matched paired cells | {fmt(s['cqr_backend_sensitivity_paired_cell_count'])} | Dataset-alpha-model-family comparison cells |",
            f"| Supplement sections | {fmt(s['supplement_section_count'])} | Broad supplementary evidence plan |",
            "",
            (
                "The design emphasizes resumability, source traceability, duplicate "
                "and leakage controls, and conservative claim boundaries. The study "
                "therefore treats blocked claims as part of the result rather than "
                "as missing decoration. If an endpoint, fairness, or validation gate "
                "does not close, the Research Document reports that gate as closed "
                "against the positive claim."
            ),
            "",
            "### Audit Controls",
            "",
            (
                "The publication-scoped accounting separates empirical observations "
                "from release claims. The current source artifacts record "
                f"{fmt(s['private_review_surface_pass_count'])} of "
                f"{fmt(s['private_review_surface_count'])} private review surfaces "
                "passing their required phrase and boundary checks. Cross-run leakage "
                f"status is `{s['cross_run_leakage_status']}`, with "
                f"{fmt(s['cross_run_unsupported_claim_hits'])} unsupported-claim hits "
                "in the scanned cross-run artifacts. These controls support the "
                "Research Atlas document, not a deployment recommendation."
            ),
            "",
            (
                "Duplicate handling is also reported as evidence rather than hidden. "
                f"The supplement records {fmt(s['duplicate_action_count'])} duplicate "
                f"actions, {fmt(s['duplicate_quarantined_action_count'])} quarantined "
                f"actions, and {fmt(s['duplicate_unquarantined_action_count'])} "
                "unquarantined actions. The Research Document therefore keeps the "
                "interpretation conditional on the audited data-integrity state."
            ),
            "",
            "## 3. Observed Method Behavior",
            "",
            "### Result Reading Guide",
            "",
            (
                "The result tables combine several diagnostic quantities. The "
                "guide below states how each quantity should be read before the "
                "method rows are interpreted. This prevents a descriptive metric "
                "from being mistaken for a final method selection, a fairness "
                "claim, an endpoint-validity claim, or a Venn-Abers validation "
                "claim."
            ),
            "",
            "| Metric | Plain-language meaning | How to read it | Boundary |",
            "|---|---|---|---|",
        ]
    )
    for row in result_reading_rows:
        lines.append(
            "| "
            f"`{row['metric']}` | "
            f"{row['plain_language_meaning']} | "
            f"{row['how_to_read_it']} | "
            f"{row['boundary']} |"
        )
    lines.extend(
        [
            "",
            "### Evidence-To-Claim Interpretation Ladder",
            "",
            (
                "The ladder below connects each result type to the strongest "
                "claim it can support and the claim it still cannot support. It "
                "is the reader-facing bridge between the numeric tables and the "
                "neutral prose used in the Research Document."
            ),
            "",
            "| Evidence layer | What it can support | Evidence in this study | What it cannot support | Reader action |",
            "|---|---|---|---|---|",
        ]
    )
    for row in result_interpretation_ladder_rows:
        lines.append(
            "| "
            f"{row['evidence_layer']} | "
            f"{row['what_it_can_support']} | "
            f"{row['evidence_in_this_study']} | "
            f"{row['what_it_cannot_support']} | "
            f"{row['reader_action']} |"
        )
    lines.extend(
        [
            "",
            "### Claim Language Guardrails",
            "",
            (
                "The rows below are writing controls derived from the claim/evidence "
                "verification matrix. They are not final prose. They state the "
                "safe sentence currently allowed, the source or citation gate that "
                "must stay attached to it, the overclaim that remains blocked, and "
                "the plain-language reason a non-specialist reader should not read "
                "more into the evidence than the study can support."
            ),
            "",
            "| Target | Claim type | Allowed sentence | Source/citation gate | Overclaim blocked | Plain-language note |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in claim_guardrail_rows:
        lines.append(
            "| "
            f"`{row['target_document']}` | "
            f"`{row['claim_type']}` | "
            f"{row['allowed_publication_sentence']} | "
            f"{row['citation_gate']} | "
            f"{row['overclaim_blocked']} | "
            f"{row['non_specialist_explanation']} |"
        )
    lines.extend(
        [
            "",
            "| Method family | Key observed evidence | Authorized interpretation |",
            "|---|---:|---|",
            f"| CQR | {fmt(s['cqr_frontier_cell_count'])} descriptive frontier cells; row-weighted coverage mean {fmt(s['cqr_row_weighted_coverage_mean'])} | Strong practical candidate observed in this experiment |",
            f"| Model-matched CQR check | {fmt(s['cqr_backend_sensitivity_model_matched_completed_rows'])} completed model-matched rows; {fmt(s['cqr_backend_sensitivity_paired_cell_count'])} paired cells; selected cells fixed-GBM={fmt(s['cqr_backend_sensitivity_fixed_gbm_selected_count'])}, model-matched={fmt(s['cqr_backend_sensitivity_model_matched_selected_count'])}, neither={fmt(s['cqr_backend_sensitivity_no_coverage_eligible_count'])} | Backend sensitivity evidence; no method-selection claim |",
            f"| CV+ | {fmt(s['cv_plus_frontier_cell_count'])} descriptive frontier cells; row-weighted coverage mean {fmt(s['cv_plus_row_weighted_coverage_mean'])} | Strong practical candidate observed in this experiment |",
            f"| Mondrian absolute-residual calibration | {fmt(s['mondrian_frontier_cell_count'])} descriptive frontier cells; row-weighted coverage mean {fmt(s['mondrian_row_weighted_coverage_mean'])} | Useful diagnostic comparator |",
            f"| Venn-Abers regression bridge | {fmt(s['venn_undercoverage_run_count'])} undercoverage runs; quantile-coverage mean {fmt(s['venn_abers_quantile_coverage_mean'])} | Negative/failure-mode evidence for the evaluated bridge |",
            "",
            (
            "The CQR row-weighted coverage mean is "
            f"{fmt(s['cqr_row_weighted_coverage_mean'])}, with an audited 95% "
            f"interval from {fmt(ci.get('low'))} to {fmt(ci.get('high'))}. "
            "This is evidence of strong empirical behavior inside the audited "
            "scope. It is not a proof that CQR is generally best, and it is not "
            "a production recommendation."
        ),
        "",
        (
            "Robustness diagnostics are aligned with that descriptive reading. "
            f"The common-cell selected method is `{s['robustness_common_cell_selected_method']}`; "
            f"common-cell counts are CQR={fmt(winner_counts.get('cqr'))}, "
            f"CV+={fmt(winner_counts.get('cv_plus'))}, and "
            f"Mondrian={fmt(winner_counts.get('mondrian_abs'))}. Bootstrap "
            f"selection counts are {fmt_counts(bootstrap_counts)}. Leave-one-dataset and "
            "leave-one-alpha retention rates are "
            f"{fmt(s['robustness_leave_one_dataset_retention_rate'])} and "
            f"{fmt(s['robustness_leave_one_alpha_retention_rate'])}. These "
            "numbers support a practical-candidate description; they do not "
            "authorize final selection language."
        ),
        "",
        (
            "Coverage summaries provide additional context. CQR has nominal and "
            "near-nominal hit rates of "
            f"{fmt(s['cqr_nominal_hit_rate'])} and "
            f"{fmt(s['cqr_near_nominal_hit_rate'])}; CV+ has near-nominal hit "
            f"rate {fmt(s['cv_plus_near_nominal_hit_rate'])}; Mondrian "
            f"absolute-residual calibration has near-nominal hit rate "
            f"{fmt(s['mondrian_near_nominal_hit_rate'])}. The document reports "
            "these values as diagnostics at the audited scope."
        ),
        "",
        "## 4. Negative And Closed Claims",
        "",
        (
            "The Research Document keeps three high-risk claims closed. First, "
            f"bounded-support validity is not supported: {fmt(s['bounded_support_validity_ready_bundle_count'])} "
            "bundles are validity-ready, despite "
            f"{fmt(s['bounded_bundle_count'])} bounded-support bundles and "
            f"{fmt(s['bounded_raw_endpoint_excursion_bundle_count'])} raw "
            "endpoint-excursion bundles being recorded. Second, population "
            "fairness is not supported: "
            f"{fmt(s['fairness_population_ready_bundle_count'])} bundles are "
            "population-fairness-ready, even though "
            f"{fmt(s['fairness_bundle_count'])} fairness bundles and "
            f"{fmt(s['fairness_pairwise_group_comparison_count'])} pairwise "
            "group comparisons are available as diagnostics. Third, the "
            "evaluated Venn-Abers bridge is reported as negative evidence "
            "rather than as a validated regression solution."
        ),
        "",
        (
            "The Venn-Abers result is intentionally narrow. The evaluated bridge "
            f"has quantile-coverage mean {fmt(s['venn_abers_quantile_coverage_mean'])}, "
            f"near-nominal hit rate {fmt(s['venn_abers_quantile_near_nominal_hit_rate'])}, "
            f"and validated-regression support flag `{s['venn_can_support_validated_regression']}`. "
            "This does not reject Venn-Abers research. It only records that the "
            "current regression interval bridge did not close the validation "
            "gate in this experiment."
        ),
        "",
        "## 5. Knowledge Graph And Reproducibility",
        "",
        (
            f"The current knowledge graph has {fmt(s['kg_node_count'])} nodes, "
            f"{fmt(s['kg_edge_count'])} edges, and "
            f"{fmt(s['kg_isolated_node_count'])} isolated nodes. Average edge "
            f"confidence is {fmt(s['kg_average_edge_confidence'])}, and edge "
            "selector provenance coverage is "
            f"{fmt(s['kg_edge_selector_provenance_coverage'])}. In the private "
            "publication package, the KG browser exposes "
            f"{fmt(s['kg_browser_node_count'])} nodes, "
            f"{fmt(s['kg_browser_edge_count'])} edges, "
            f"{fmt(s['kg_browser_node_type_count'])} node types, and "
            f"{fmt(s['kg_browser_relation_type_count'])} relation types. The "
            "browser is intended to let reviewers move from claims to source "
            "reports, tables, scripts, and quality gates. It is not yet a "
            "public citable component; public citation waits for article, "
            "supplement, site, README, and release review."
        ),
        "",
        "## 6. How To Read The Artifact Set",
        "",
        (
            "The review order is deliberately simple. Read this Research "
            "Document first, then inspect the rendered main article and broad "
            "supplement, then use the individual experiment report for the "
            "author-stamped experiment summary. The KG browser should be used "
            "when a reader wants to trace a claim to reports, source artifacts, "
            "scripts, or quality gates. Governance files should be checked before "
            "any release decision because they encode the closed claims."
        ),
        "",
        "| Artifact | Role | Release boundary |",
        "|---|---|---|",
        "| `manuscript/research_document.md` | Integrated Research Atlas narrative | Descriptive, experiment-scoped interpretation |",
        "| `rendered_outputs/main_article_review.html` | Main article surface | Conservative scientific wording |",
        "| `rendered_outputs/supplementary_document_review.html` | Broad supplementary surface | Methods, diagnostics, and estimator conventions |",
        "| `site/kg_browser.html` | Browsable KG surface | Navigation and traceability, not a standalone claim |",
        "| `governance/publication_authoring_decision_record.md` | Decision boundary record | Scientific claim boundaries and release scope |",
        "",
        "## 7. Publication Boundary",
        "",
        "This document is intentionally strict about what it does not claim:",
        "",
    ]
    )
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(
        [
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
