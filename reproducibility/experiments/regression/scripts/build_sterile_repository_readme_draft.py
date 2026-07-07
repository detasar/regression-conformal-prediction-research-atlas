"""Build the README for the private sterile publication review package.

The output is a source-linked README for the private review package/repository.
It does not authorize public release, write final manuscript prose, or
recommend a conformal method.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_sterile_repository_readme_draft_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/sterile_repository_readme_draft.md"
)
DEFAULT_JSON_OUT = Path(
    "experiments/regression/manuscript/sterile_repository_readme_draft.json"
)
AUTHOR_NAME = "Emre Tasar"
AUTHOR_ROLE = "Data Scientist"
AUTHOR_EMAIL = "detasar@gmail.com"

STAGING_MANIFEST = Path(
    "experiments/regression/manuscript/sterile_repository_staging_manifest.json"
)
MAIN_ARTICLE = Path("experiments/regression/manuscript/main_article_draft.json")
SUPPLEMENT = Path("experiments/regression/manuscript/supplementary_document_draft.json")
INDIVIDUAL_REPORT = Path(
    "experiments/regression/manuscript/individual_experiment_report_draft.json"
)
CITATION_REGISTRY = Path(
    "experiments/regression/manuscript/publication_citation_registry.json"
)
KG_QUALITY = Path(
    "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
)
FINAL_AUTHORIZATION = Path(
    "experiments/regression/manuscript/final_publication_output_authorization_protocol.json"
)
PRIVATE_PACKAGE = Path(
    "experiments/regression/manuscript/private_sterile_publication_package_manifest.json"
)
PRIVATE_RENDER_AUDIT = Path(
    "experiments/regression/manuscript/private_latex_html_review_output_audit.json"
)
RESEARCH_DOCUMENT = Path("experiments/regression/manuscript/research_document.json")
PUBLICATION_AUTHORING_DECISION = Path(
    "experiments/regression/manuscript/publication_authoring_decision_record.json"
)
PUBLICATION_CLAIM_EVIDENCE_MATRIX = Path(
    "experiments/regression/manuscript/publication_claim_evidence_verification_matrix.json"
)
PRIVATE_REMOTE_AUDIT = Path(
    "experiments/regression/manuscript/private_publication_repository_remote_audit.json"
)
PUBLICATION_EXEMPLAR_REVIEW = Path(
    "experiments/regression/manuscript/publication_exemplar_review.json"
)
DATA_SCIENTIST_LOG = Path("experiments/regression/diary/data_scientist_log.md")
DATA_FLOW_GRAPH = Path("experiments/regression/graphs/data_flow.mmd")
CONTROL_FLOW_GRAPH = Path("experiments/regression/graphs/control_flow.mmd")
DEPENDENCY_GRAPH = Path("experiments/regression/graphs/dependency_graph.mmd")
SYSTEM_ONTOLOGY_GRAPH = Path("experiments/regression/graphs/system_ontology.mmd")


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
    if value is None:
        return "n/a"
    return str(value)


def citation_keys(payload: dict[str, Any]) -> dict[str, str]:
    return {row["url"]: row["citation_key"] for row in payload.get("citation_rows", [])}


def required_citation_urls() -> list[str]:
    return [
        "https://arxiv.org/abs/1604.04173",
        "https://arxiv.org/abs/1905.02928",
        "https://arxiv.org/abs/1905.03222",
        "https://arxiv.org/abs/2002.09025",
        "https://proceedings.mlr.press/v91/nouretdinov18a.html",
    ]


CLAIM_READER_QUESTIONS = {
    "paper_dataset_scope_evidence": "What data/source scope was inspected?",
    "paper_method_scope_evidence": "How should CQR/CV+ be described?",
    "paper_main_results_blocked_evidence": "Can the package name a final selected method?",
    "supplement_robustness_diagnostic_evidence": "How should robustness rows be read?",
    "supplement_venn_abers_negative_evidence": "How should the Venn-Abers result be written?",
    "supplement_methodology_controls_evidence": "What do audit controls prove?",
    "supplement_reproducibility_traceability_evidence": "What does the private package prove?",
    "individual_report_blueprint_evidence": "What does the individual report blueprint prove?",
}


def readme_safe_claim_text(text: str) -> str:
    return (
        text.replace("final winner", "final selected method")
        .replace("winner", "selected method")
        .replace("definitively better", "definitively preferred")
    )


def build_claim_safe_reading_rows(
    research_document: dict[str, Any],
) -> list[dict[str, str]]:
    guardrail_rows = research_document.get("claim_language_guardrail_rows") or []
    if not isinstance(guardrail_rows, list):
        return []
    rows = []
    for row in guardrail_rows:
        if not isinstance(row, dict):
            continue
        claim_review_id = str(row.get("claim_review_id") or "")
        rows.append(
            {
                "reader_question": CLAIM_READER_QUESTIONS.get(
                    claim_review_id, claim_review_id
                ),
                "target_document": str(row.get("target_document") or ""),
                "allowed_publication_sentence": readme_safe_claim_text(
                    str(row.get("allowed_publication_sentence") or "")
                ),
                "evidence_gate": readme_safe_claim_text(
                    str(row.get("citation_gate") or "")
                ),
                "blocked_reading": readme_safe_claim_text(
                    str(row.get("overclaim_blocked") or "")
                ),
                "claim_review_status": str(row.get("claim_review_status") or ""),
            }
        )
    return rows


def build_plain_language_summary_rows(
    research_document: dict[str, Any],
) -> list[dict[str, str]]:
    rows = research_document.get("plain_language_summary_rows") or []
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        result.append(
            {
                "reader_question": readme_safe_claim_text(
                    str(row.get("reader_question") or "")
                ),
                "plain_language_answer": readme_safe_claim_text(
                    str(row.get("plain_language_answer") or "")
                ),
                "evidence_anchor": readme_safe_claim_text(
                    str(row.get("evidence_anchor") or "")
                ),
                "boundary": readme_safe_claim_text(
                    str(row.get("boundary") or "")
                ),
            }
        )
    return result


def build_result_interpretation_ladder_rows(
    research_document: dict[str, Any],
) -> list[dict[str, str]]:
    rows = research_document.get("result_interpretation_ladder_rows") or []
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        result.append(
            {
                "evidence_layer": readme_safe_claim_text(
                    str(row.get("evidence_layer") or "")
                ),
                "what_it_can_support": readme_safe_claim_text(
                    str(row.get("what_it_can_support") or "")
                ),
                "evidence_in_this_study": readme_safe_claim_text(
                    str(row.get("evidence_in_this_study") or "")
                ),
                "what_it_cannot_support": readme_safe_claim_text(
                    str(row.get("what_it_cannot_support") or "")
                ),
                "reader_action": readme_safe_claim_text(
                    str(row.get("reader_action") or "")
                ),
            }
        )
    return result


def build_review_at_a_glance_rows(summary: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "review_need": "Start point",
            "what_to_read": "`manuscript/research_document.md`",
            "what_it_answers": (
                "Integrated non-specialist primer, scientific-method audit trail, "
                "observed results, and closed claim gates."
            ),
            "boundary": "Private review narrative only; not public release.",
        },
        {
            "review_need": "Main empirical wording",
            "what_to_read": (
                "Research Question Answer Map, Contribution And Finding Snapshot, "
                "and Current Evidence Snapshot."
            ),
            "what_it_answers": (
                "CQR/CV+ were observed as strong practical candidates in these "
                f"experiments; CQR has {fmt(summary.get('cqr_frontier_cell_count'))} "
                "frontier cells and CV+ has "
                f"{fmt(summary.get('cv_plus_frontier_cell_count'))}."
            ),
            "boundary": "No final selected method, best-method claim, or recommendation.",
        },
        {
            "review_need": "Negative evidence",
            "what_to_read": (
                "Plain-Language Summary, Claim-Safe Reading Map, and supplement "
                "S2/S6."
            ),
            "what_it_answers": (
                "The evaluated Venn-Abers bridge is negative/failure-mode evidence "
                f"with {fmt(summary.get('venn_undercoverage_run_count'))} "
                "undercoverage runs."
            ),
            "boundary": "No validated Venn-Abers regression interval claim.",
        },
        {
            "review_need": "Closed positive claims",
            "what_to_read": (
                "Guarantee Boundary Snapshot, Claim Boundaries, and release checklist."
            ),
            "what_it_answers": (
                f"{fmt(summary.get('bounded_support_validity_ready_bundle_count'))} "
                "bounded-support-validity-ready bundles and "
                f"{fmt(summary.get('fairness_population_ready_bundle_count'))} "
                "population-fairness-ready bundles."
            ),
            "boundary": (
                "No prose may convert zero-ready gates into validity or fairness claims."
            ),
        },
        {
            "review_need": "Traceability",
            "what_to_read": "`site/kg_browser.html` and `site/kg_browser_data.json`",
            "what_it_answers": (
                f"{fmt(summary.get('kg_browser_node_count'))} KG browser nodes, "
                f"{fmt(summary.get('kg_browser_edge_count'))} KG browser edges, "
                f"{fmt(summary.get('kg_isolated_node_count'))} isolated nodes, "
                "and guided trace presets."
            ),
            "boundary": "KG citation and GitHub Pages deployment remain closed.",
        },
        {
            "review_need": "Release state",
            "what_to_read": (
                "`PUBLIC_RELEASE_REVIEW_CHECKLIST.md` and governance records."
            ),
            "what_it_answers": (
                "Private repository visibility is "
                f"`{summary.get('private_publication_repository_visibility')}` "
                "and private local/remote commit match is "
                f"`{summary.get('private_publication_repository_commit_match')}`."
            ),
            "boundary": "Public release requires a later explicit approval record.",
        },
    ]


def build_first_ten_minute_rows(summary: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "minute": "0-1",
            "review_action": "Read the One-Minute Thesis and Status block.",
            "artifact": "README.md",
            "acceptance_check": (
                "The package is private, method recommendation is false, and "
                "public release is false."
            ),
            "stop_if_missing": (
                "Stop if private visibility, release status, or method-recommendation "
                "status is ambiguous."
            ),
        },
        {
            "minute": "1-3",
            "review_action": "Open the Research Document through the Read lane.",
            "artifact": "manuscript/research_document.md",
            "acceptance_check": (
                "The empirical object is explicit: "
                f"{fmt(summary.get('publication_completed_rows'))} rows, "
                f"{fmt(summary.get('dataset_count'))} datasets, "
                f"{fmt(summary.get('dataset_alpha_cell_count'))} dataset-alpha cells, "
                f"and {fmt(summary.get('method_count'))} method labels."
            ),
            "stop_if_missing": (
                "Stop if the scope can be mistaken for exhaustive internet coverage "
                "or deployment generality."
            ),
        },
        {
            "minute": "3-5",
            "review_action": "Check the main empirical wording against evidence.",
            "artifact": "Contribution And Finding Snapshot",
            "acceptance_check": (
                "CQR/CV+ wording stays experiment-scoped, with CQR frontier cells "
                f"{fmt(summary.get('cqr_frontier_cell_count'))} and CV+ frontier "
                f"cells {fmt(summary.get('cv_plus_frontier_cell_count'))}."
            ),
            "stop_if_missing": (
                "Stop if the wording becomes a final selected method, best-method "
                "claim, or recommendation."
            ),
        },
        {
            "minute": "5-7",
            "review_action": "Check the Venn-Abers and closed-claim boundaries.",
            "artifact": "supplementary_document_draft.md; Claim-Safe Reading Map",
            "acceptance_check": (
                "The bridge result is negative/failure-mode evidence with "
                f"{fmt(summary.get('venn_undercoverage_run_count'))} undercoverage "
                "runs, and fairness/bounded-support ready counts remain zero."
            ),
            "stop_if_missing": (
                "Stop if the bridge result rejects the whole Venn-Abers literature "
                "or if zero-ready gates are written as positive claims."
            ),
        },
        {
            "minute": "7-10",
            "review_action": "Trace one claim through the KG and release checklist.",
            "artifact": "site/kg_browser.html; PUBLIC_RELEASE_REVIEW_CHECKLIST.md",
            "acceptance_check": (
                f"The KG has {fmt(summary.get('kg_browser_node_count'))} nodes, "
                f"{fmt(summary.get('kg_browser_edge_count'))} edges, "
                f"{fmt(summary.get('kg_isolated_node_count'))} isolated nodes, "
                "and public release still requires a separate authorization record."
            ),
            "stop_if_missing": (
                "Stop if KG citation, GitHub Pages, or public visibility appears "
                "authorized by implication."
            ),
        },
    ]


def build_reviewer_acceptance_rows(summary: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "acceptance_item": "Private review status is unambiguous.",
            "evidence": (
                "Status block shows private package created, private repository "
                f"visibility `{summary.get('private_publication_repository_visibility')}`, "
                f"public release `{summary.get('public_release_authorized')}`, and "
                f"method recommendation `{summary.get('method_recommendation_authorized')}`."
            ),
            "reject_if": (
                "Any reader can mistake this package for a public release or a "
                "method-recommendation artifact."
            ),
        },
        {
            "acceptance_item": "The central empirical wording is scoped.",
            "evidence": (
                "CQR/CV+ are written as strong practical candidates observed in "
                "these experiments, with CQR frontier cells "
                f"{fmt(summary.get('cqr_frontier_cell_count'))} and CV+ frontier "
                f"cells {fmt(summary.get('cv_plus_frontier_cell_count'))}."
            ),
            "reject_if": (
                "The wording becomes a selected-method, best-method, or general "
                "recommendation claim."
            ),
        },
        {
            "acceptance_item": "Negative evidence is narrow enough.",
            "evidence": (
                "The Venn-Abers row is bridge-specific negative/failure-mode "
                f"evidence with {fmt(summary.get('venn_undercoverage_run_count'))} "
                "undercoverage runs."
            ),
            "reject_if": (
                "The result is written as a rejection of the broader Venn-Abers, "
                "predictive-distribution, or generalized-calibration literature."
            ),
        },
        {
            "acceptance_item": "Closed positive claims stay closed.",
            "evidence": (
                f"Bounded-support-ready bundles are "
                f"{fmt(summary.get('bounded_support_validity_ready_bundle_count'))}; "
                f"population-fairness-ready bundles are "
                f"{fmt(summary.get('fairness_population_ready_bundle_count'))}."
            ),
            "reject_if": (
                "Zero-ready gates are converted into bounded-support validity, "
                "population fairness, production, or deployment claims."
            ),
        },
        {
            "acceptance_item": "Traceability is useful but not citable yet.",
            "evidence": (
                f"KG browser exposes {fmt(summary.get('kg_browser_node_count'))} "
                f"nodes, {fmt(summary.get('kg_browser_edge_count'))} edges, and "
                f"{fmt(summary.get('kg_isolated_node_count'))} isolated nodes."
            ),
            "reject_if": (
                "The KG, site, or private repository is cited or published before "
                "the release authorization record exists."
            ),
        },
    ]


def build_private_review_contract_rows(summary: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "review_action": "Read and critique the package privately.",
            "current_answer": "Allowed for private scientific review.",
            "evidence": (
                "Research Document status is "
                f"`{summary.get('research_document_status')}` and "
                f"{fmt(summary.get('private_review_surface_pass_count'))} / "
                f"{fmt(summary.get('private_review_surface_count'))} private "
                "review surfaces pass."
            ),
            "boundary": "This is not public final manuscript prose.",
        },
        {
            "review_action": "Cite, publish, or make the repository public.",
            "current_answer": "Not allowed at this stage.",
            "evidence": (
                f"Public release is `{summary.get('public_release_authorized')}` "
                "and working-repository final-citable status is "
                f"`{summary.get('working_repository_final_citable')}`."
            ),
            "boundary": (
                "Public release, GitHub Pages, and citable repository status need "
                "a later explicit authorization record."
            ),
        },
        {
            "review_action": "Use CQR/CV+ as the practical reading of the evidence.",
            "current_answer": "Allowed only as experiment-scoped observation.",
            "evidence": (
                "CQR/CV+ were observed as strong practical candidates in these "
                "experiments; method recommendation is "
                f"`{summary.get('method_recommendation_authorized')}`."
            ),
            "boundary": "No final selected method, global superiority claim, or recommendation.",
        },
        {
            "review_action": "Interpret the Venn-Abers result.",
            "current_answer": "Allowed only as bridge-specific negative evidence.",
            "evidence": (
                "The evaluated bridge has "
                f"{fmt(summary.get('venn_undercoverage_run_count'))} "
                "undercoverage runs in the current evidence snapshot."
            ),
            "boundary": (
                "Do not reject the broader Venn-Abers, predictive-distribution, "
                "or generalized-calibration literature."
            ),
        },
        {
            "review_action": "Use the KG and site to navigate evidence.",
            "current_answer": "Allowed as private review navigation.",
            "evidence": (
                f"The KG browser exposes {fmt(summary.get('kg_browser_node_count'))} "
                f"nodes, {fmt(summary.get('kg_browser_edge_count'))} edges, and "
                f"{fmt(summary.get('kg_isolated_node_count'))} isolated nodes."
            ),
            "boundary": "No public KG citation, public site, or GitHub Pages release.",
        },
    ]


def build_reviewer_front_door_rows(summary: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "lane": "Read",
            "open_first": "`manuscript/research_document.md`",
            "reader_action": (
                "Read the integrated narrative before the separate article and "
                "supplement."
            ),
            "safe_takeaway": (
                "CQR/CV+ were observed as strong practical candidates in these "
                "experiments."
            ),
            "closed_boundary": "No final selected method or recommendation.",
        },
        {
            "lane": "Check",
            "open_first": "`manuscript/supplementary_document_draft.md`",
            "reader_action": (
                "Check robustness, post-selection diagnostics, and negative "
                "evidence before accepting the wording."
            ),
            "safe_takeaway": (
                "The evaluated Venn-Abers bridge is reported as bridge-specific "
                "negative evidence."
            ),
            "closed_boundary": "No validated Venn-Abers regression interval claim.",
        },
        {
            "lane": "Trace",
            "open_first": "`site/kg_browser.html`",
            "reader_action": (
                "Use guided KG presets to follow claims to reports, source "
                "artifacts, and gate evidence."
            ),
            "safe_takeaway": (
                f"{fmt(summary.get('kg_browser_node_count'))} nodes, "
                f"{fmt(summary.get('kg_browser_edge_count'))} edges, and "
                f"{fmt(summary.get('kg_isolated_node_count'))} isolated nodes "
                "are available in the private browser."
            ),
            "closed_boundary": "No citable KG, public site, or GitHub Pages release.",
        },
        {
            "lane": "Decide",
            "open_first": "`PUBLIC_RELEASE_REVIEW_CHECKLIST.md`",
            "reader_action": (
                "Use the checklist only after the prose, evidence, KG, and "
                "governance surfaces have been reviewed."
            ),
            "safe_takeaway": (
                "The private repository is synchronized, but public visibility "
                "remains a later decision."
            ),
            "closed_boundary": "Public release requires explicit approval.",
        },
    ]


def build_reader_mode_selector_rows(summary: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "reader_mode": "Fast orientation",
            "use_when": "You need the study thesis and current status in two minutes.",
            "open_first": "One-Minute Thesis; Status; Plain-Language Summary",
            "then_check": (
                "Confirm private visibility, public release false, method "
                "recommendation false, and the experiment-scoped CQR/CV+ wording."
            ),
            "do_not_do": "Do not treat the README as a public release or recommendation.",
        },
        {
            "reader_mode": "Scientific review",
            "use_when": "You need to judge whether the empirical interpretation is defensible.",
            "open_first": "`manuscript/research_document.md`",
            "then_check": (
                "Compare the Research Question Answer Map, main article, and "
                "supplement against the claim-safe reading rows."
            ),
            "do_not_do": "Do not upgrade descriptive diagnostics into final selection claims.",
        },
        {
            "reader_mode": "Claim audit",
            "use_when": "You need to trace a sentence, number, method, or gate to evidence.",
            "open_first": "`site/kg_browser.html`",
            "then_check": (
                f"Use guided KG presets over {fmt(summary.get('kg_browser_node_count'))} "
                f"nodes and {fmt(summary.get('kg_browser_edge_count'))} edges, then "
                "verify the linked source artifact."
            ),
            "do_not_do": "Do not cite the KG or site before explicit release authorization.",
        },
        {
            "reader_mode": "Release review",
            "use_when": "You need to decide whether public release can be considered later.",
            "open_first": "`PUBLIC_RELEASE_REVIEW_CHECKLIST.md`",
            "then_check": (
                "Inspect governance records, finalization blockers, private remote "
                "visibility, and local/remote package commit match."
            ),
            "do_not_do": "Do not make the repository public without a later approval record.",
        },
    ]


def build_provenance_graph_log_rows() -> list[dict[str, str]]:
    return [
        {
            "review_task": "Data scientist log",
            "source_artifact": str(DATA_SCIENTIST_LOG),
            "package_artifact": "provenance/data_scientist_log.md",
            "reader_job": (
                "Inspect dated decisions, resume checkpoints, audit outcomes, and "
                "interpretation changes across the study."
            ),
            "boundary": (
                "Review-only scientific diary; it does not upgrade empirical claims "
                "or authorize public release."
            ),
        },
        {
            "review_task": "Data flow graph",
            "source_artifact": str(DATA_FLOW_GRAPH),
            "package_artifact": "provenance/graphs/data_flow.mmd",
            "reader_job": (
                "Trace how source inventory, audits, preprocessing policies, runs, "
                "reports, manuscript artifacts, and KG exports connect."
            ),
            "boundary": "Provenance diagram only; not additional experimental evidence.",
        },
        {
            "review_task": "Control flow graph",
            "source_artifact": str(CONTROL_FLOW_GRAPH),
            "package_artifact": "provenance/graphs/control_flow.mmd",
            "reader_job": (
                "Inspect the execution gates, resume logic, audit sequence, and "
                "publication-stage decision flow."
            ),
            "boundary": "Workflow-control diagram only; not a method-performance result.",
        },
        {
            "review_task": "Dependency graph",
            "source_artifact": str(DEPENDENCY_GRAPH),
            "package_artifact": "provenance/graphs/dependency_graph.mmd",
            "reader_job": (
                "Audit how loaders, scripts, models, conformal methods, reports, "
                "tests, and publication builders depend on one another."
            ),
            "boundary": "Dependency trace only; not a claim that a dependency is endorsed.",
        },
        {
            "review_task": "System ontology graph",
            "source_artifact": str(SYSTEM_ONTOLOGY_GRAPH),
            "package_artifact": "provenance/graphs/system_ontology.mmd",
            "reader_job": (
                "Read the typed system map connecting datasets, methods, audits, "
                "paper gates, reports, and publication artifacts."
            ),
            "boundary": "Ontology/navigation surface only; not a public citable KG.",
        },
    ]


def build_result_verification_command_rows() -> list[dict[str, str]]:
    python = "/home/emre/miniconda3/envs/ml/bin/python"
    return [
        {
            "verification_task": "Rebuild the private review README draft",
            "command": (
                f"PYTHONPATH=. {python} "
                "experiments/regression/scripts/"
                "build_sterile_repository_readme_draft.py --repo-root ."
            ),
            "expected_evidence": (
                "`overall_status` is `sterile_repository_readme_draft_ready` "
                "and `failed_check_count` is 0."
            ),
            "primary_artifact": (
                "experiments/regression/manuscript/"
                "sterile_repository_readme_draft.json"
            ),
            "boundary": (
                "Rebuilding the README verifies the private review surface; it "
                "does not authorize public release."
            ),
        },
        {
            "verification_task": "Check reader-facing publication artifacts",
            "command": (
                f"PYTHONDONTWRITEBYTECODE=1 {python} -m pytest -q "
                "tests/test_regression_sterile_repository_readme_draft.py "
                "tests/test_regression_research_document.py "
                "tests/test_regression_private_latex_html_review_outputs.py"
            ),
            "expected_evidence": (
                "README, Research Document, and private LaTeX/HTML review "
                "artifact tests pass."
            ),
            "primary_artifact": (
                "experiments/regression/manuscript/"
                "private_latex_html_review_output_audit.json"
            ),
            "boundary": (
                "Passing publication-surface tests supports private review "
                "readiness, not public release or final submission status."
            ),
        },
        {
            "verification_task": "Regenerate the sterile private package",
            "command": (
                f"PYTHONPATH=. {python} "
                "experiments/regression/scripts/"
                "build_private_sterile_publication_package.py --repo-root ."
            ),
            "expected_evidence": (
                "`overall_status` is `private_sterile_publication_package_ready` "
                "and `failed_check_count` is 0."
            ),
            "primary_artifact": (
                "experiments/regression/manuscript/"
                "private_sterile_publication_package_manifest.json"
            ),
            "boundary": (
                "Package readiness means private review packaging only; public "
                "release and public visibility remain closed."
            ),
        },
        {
            "verification_task": "Check KG metadata freshness",
            "command": (
                f"PYTHONDONTWRITEBYTECODE=1 {python} -m pytest -q "
                "tests/test_regression_publication_kg_metadata_freshness.py "
                "tests/test_regression_knowledge_graph_quality.py"
            ),
            "expected_evidence": (
                "KG freshness and quality tests pass with the current node and "
                "edge counts."
            ),
            "primary_artifact": (
                "experiments/regression/reports/knowledge_graph_quality/"
                "quality_summary.json"
            ),
            "boundary": (
                "KG quality supports traceability review; it does not make the "
                "KG citable."
            ),
        },
        {
            "verification_task": "Run the full source test suite",
            "command": f"PYTHONDONTWRITEBYTECODE=1 {python} -m pytest -q",
            "expected_evidence": (
                "Expected current result: 834 tests pass with the existing "
                "LightGBM feature-name warning."
            ),
            "primary_artifact": "tests/",
            "boundary": (
                "A green source suite is required evidence for this package; it "
                "does not open method recommendation or public release gates."
            ),
        },
    ]


def build_environment_data_access_rows(
    summary: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "surface": "Runtime and dependency specification",
            "package_path": "requirements.txt",
            "reader_use": (
                "Use the requirements file as the dependency floor for the "
                "private review commands. The verified source environment uses "
                "`/home/emre/miniconda3/envs/ml/bin/python`."
            ),
            "evidence": (
                "The verification commands execute with the recorded Python "
                "interpreter and the current full suite passes."
            ),
            "boundary": (
                "This is not a locked container image and does not authorize "
                "public release."
            ),
        },
        {
            "surface": "Executable source, configs, and tests",
            "package_path": "reproducibility/",
            "reader_use": (
                "Inspect copied `cpfi`, regression scripts, configs, policies, "
                "and tests under the reproducibility tree."
            ),
            "evidence": (
                f"The current package manifest records "
                f"{fmt(summary.get('private_review_package_copied_file_count'))} "
                "copied files and "
                f"{fmt(summary.get('private_review_package_failed_check_count'))} "
                "failed package checks."
            ),
            "boundary": (
                "The reproducibility tree supports review and verification; it "
                "does not rerun the full historical experiment grid by default."
            ),
        },
        {
            "surface": "Data access and preprocessing policy",
            "package_path": (
                "reproducibility/experiments/regression/policies/"
                "data_policy_registry.md"
            ),
            "reader_use": (
                "Review the binding defaults for source/license notes, target "
                "handling, group policy, leakage policy, missingness, duplicates, "
                "and split policy."
            ),
            "evidence": (
                "The policy registry is copied into the private package and "
                "dataset/source audits remain source-linked."
            ),
            "boundary": (
                "The private package is not a raw-data archive; external data "
                "access remains subject to the original source terms."
            ),
        },
        {
            "surface": "Raw-data, cache, and secret exclusion",
            "package_path": "metadata/private_sterile_publication_package_manifest.json",
            "reader_use": (
                "Use the manifest to inspect copied files, excluded files, path "
                "risk checks, and high-confidence secret-pattern checks."
            ),
            "evidence": (
                f"Current path-risk hits: "
                f"{fmt(summary.get('private_review_package_path_risk_hit_count'))}; "
                f"secret-pattern hits: "
                f"{fmt(summary.get('private_review_package_secret_pattern_hit_count'))}."
            ),
            "boundary": (
                "A clean package scan supports sterile review packaging; it does "
                "not certify external data licenses or public release."
            ),
        },
        {
            "surface": "Authority of generated review artifacts",
            "package_path": "manuscript/research_document.md; site/index.html",
            "reader_use": (
                "Read generated narrative and site surfaces as review entry "
                "points, then verify claims through source artifacts and commands."
            ),
            "evidence": (
                "The README, Research Document, private render audit, KG quality "
                "summary, and package manifest are regenerated from source-side "
                "builders."
            ),
            "boundary": (
                "Generated review surfaces are private authoring outputs, not "
                "public final manuscript prose."
            ),
        },
    ]


def build_repository_map_rows() -> list[dict[str, str]]:
    return [
        {
            "package_item": "README",
            "package_path": "README.md",
            "review_job": "Start the private review and confirm status, scope, and release boundaries.",
            "current_review_status": "Draft source-linked README available; final README not authorized.",
        },
        {
            "package_item": "Research Document",
            "package_path": "manuscript/research_document.md",
            "review_job": "Read the integrated narrative, reader primer, result interpretation, and closed gates.",
            "current_review_status": "Private authoring surface available; public release blocked.",
        },
        {
            "package_item": "Main article",
            "package_path": "manuscript/main_article_draft.md",
            "review_job": "Inspect the compact article surface for claim wording and evidence boundaries.",
            "current_review_status": (
                "Private final-prose review draft available; public/submission "
                "final manuscript blocked."
            ),
        },
        {
            "package_item": "Supplement",
            "package_path": "manuscript/supplementary_document_draft.md",
            "review_job": "Inspect broad method, audit, robustness, fairness, endpoint, and negative-evidence detail.",
            "current_review_status": (
                "Private final-prose review draft available; public/submission "
                "final supplement blocked."
            ),
        },
        {
            "package_item": "Individual report",
            "package_path": "manuscript/individual_experiment_report_draft.md",
            "review_job": "Review the author-stamped experiment summary and result interpretation details.",
            "current_review_status": "Evidence-linked draft available; final report blocked.",
        },
        {
            "package_item": "Knowledge graph",
            "package_path": "site/kg_browser.html",
            "review_job": "Trace claims to reports, methods, citations, source artifacts, and quality gates.",
            "current_review_status": (
                "Internal graph and private browser available; citable KG component blocked."
            ),
        },
        {
            "package_item": "Site package",
            "package_path": "site/index.html",
            "review_job": "Use the private web portal for reviewer lanes, rendered outputs, and KG navigation.",
            "current_review_status": "Private review site generated; public deployment blocked.",
        },
        {
            "package_item": "Governance",
            "package_path": "governance/",
            "review_job": "Check release, citation, method-recommendation, and public-visibility authorization gates.",
            "current_review_status": "Governance records available; public release still requires explicit approval.",
        },
        {
            "package_item": "Provenance",
            "package_path": "provenance/",
            "review_job": "Inspect the data scientist log and Mermaid flow/control/dependency/ontology graphs.",
            "current_review_status": "Review-only provenance available; it does not upgrade empirical claims.",
        },
    ]


def build_finalization_blocker_rows(
    final_authorization: dict[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in final_authorization.get("authorization_rows") or []:
        if not isinstance(row, dict):
            continue
        required = [
            str(item)
            for item in row.get("required_before_authorization") or []
            if str(item).strip()
        ]
        evidence = row.get("current_evidence") or {}
        rows.append(
            {
                "blocker_id": str(row.get("blocker_id") or ""),
                "output_family": str(row.get("output_family") or ""),
                "authorization_status": str(row.get("authorization_status") or ""),
                "blocked_current_action": str(row.get("blocked_current_action") or ""),
                "allowed_current_action": str(row.get("allowed_current_action") or ""),
                "required_before_authorization": "; ".join(required[:3]),
                "evidence_summary": (
                    "goal_can_mark_complete="
                    f"{evidence.get('goal_can_mark_complete')}; "
                    "release_authorized_count="
                    f"{evidence.get('release_authorized_count')}; "
                    "positive_claim_ready_gate_count="
                    f"{evidence.get('positive_claim_ready_gate_count')}"
                ),
            }
        )
    return rows


def build_payload(root: Path) -> dict[str, Any]:
    staging = read_json(root, STAGING_MANIFEST)
    main_article = read_json(root, MAIN_ARTICLE)
    supplement = read_json(root, SUPPLEMENT)
    individual = read_json(root, INDIVIDUAL_REPORT)
    citations = read_json(root, CITATION_REGISTRY)
    kg_quality = read_json(root, KG_QUALITY)
    final_authorization = read_json(root, FINAL_AUTHORIZATION)
    private_package = read_json(root, PRIVATE_PACKAGE)
    private_render_audit = read_json(root, PRIVATE_RENDER_AUDIT)
    research_document = read_json(root, RESEARCH_DOCUMENT)
    publication_authoring_decision = read_json(root, PUBLICATION_AUTHORING_DECISION)
    private_remote_audit = read_json(root, PRIVATE_REMOTE_AUDIT)
    exemplar_review = read_json(root, PUBLICATION_EXEMPLAR_REVIEW)

    sources = {
        "sterile_repository_staging_manifest": str(STAGING_MANIFEST),
        "main_article_draft": str(MAIN_ARTICLE),
        "supplementary_document_draft": str(SUPPLEMENT),
        "individual_experiment_report_draft": str(INDIVIDUAL_REPORT),
        "research_document": str(RESEARCH_DOCUMENT),
        "publication_authoring_decision_record": str(PUBLICATION_AUTHORING_DECISION),
        "publication_claim_evidence_verification_matrix": str(
            PUBLICATION_CLAIM_EVIDENCE_MATRIX
        ),
        "publication_citation_registry": str(CITATION_REGISTRY),
        "knowledge_graph_quality_summary": str(KG_QUALITY),
        "final_publication_output_authorization_protocol": str(FINAL_AUTHORIZATION),
        "private_sterile_publication_package_manifest": str(PRIVATE_PACKAGE),
        "private_latex_html_review_output_audit": str(PRIVATE_RENDER_AUDIT),
        "private_publication_repository_remote_audit": str(PRIVATE_REMOTE_AUDIT),
        "publication_exemplar_review": str(PUBLICATION_EXEMPLAR_REVIEW),
        "data_scientist_log": str(DATA_SCIENTIST_LOG),
        "data_flow_graph": str(DATA_FLOW_GRAPH),
        "control_flow_graph": str(CONTROL_FLOW_GRAPH),
        "dependency_graph": str(DEPENDENCY_GRAPH),
        "system_ontology_graph": str(SYSTEM_ONTOLOGY_GRAPH),
    }

    staging_s = staging.get("summary") or {}
    main_s = main_article.get("summary") or {}
    main_article_guarantee_rows = [
        row
        for row in main_article.get("guarantee_boundary_rows") or []
        if isinstance(row, dict)
    ]
    paper_architecture_rows = [
        row
        for row in main_article.get("paper_architecture_rows") or []
        if isinstance(row, dict)
    ]
    supplement_s = supplement.get("summary") or {}
    individual_s = individual.get("summary") or {}
    individual_facts = individual.get("report_facts") or {}
    citation_s = citations.get("summary") or {}
    kg_graph = kg_quality.get("graph") or {}
    kg_traceability = kg_quality.get("traceability") or {}
    final_auth_s = final_authorization.get("summary") or {}
    private_package_s = private_package.get("summary") or {}
    private_render_audit_s = private_render_audit.get("summary") or {}
    research_document_s = research_document.get("summary") or {}
    authoring_decision_s = publication_authoring_decision.get("summary") or {}
    private_remote_s = private_remote_audit.get("summary") or {}
    exemplar_s = exemplar_review.get("summary") or {}
    design_decision_rows = exemplar_review.get("design_decision_rows") or []
    claim_safe_reading_rows = build_claim_safe_reading_rows(research_document)
    plain_language_summary_rows = build_plain_language_summary_rows(
        research_document
    )
    result_interpretation_ladder_rows = build_result_interpretation_ladder_rows(
        research_document
    )
    research_question_rows = [
        row
        for row in research_document.get("research_question_rows") or []
        if isinstance(row, dict)
    ]
    contribution_finding_rows = [
        row
        for row in research_document.get("contribution_finding_rows") or []
        if isinstance(row, dict)
    ]
    cite = citation_keys(citations)

    missing_sources = [path for path in sources.values() if not (root / path).exists()]
    missing_citations = [url for url in required_citation_urls() if url not in cite]
    readme_sections = [
        {
            "section_id": "status",
            "heading": "Status",
            "evidence_sources": [
                "sterile_repository_staging_manifest",
                "final_publication_output_authorization_protocol",
            ],
        },
        {
            "section_id": "private_review_contract",
            "heading": "Private Review Contract",
            "evidence_sources": [
                "research_document",
                "private_sterile_publication_package_manifest",
                "private_publication_repository_remote_audit",
                "knowledge_graph_quality_summary",
                "final_publication_output_authorization_protocol",
            ],
        },
        {
            "section_id": "reader_mode_selector",
            "heading": "Reader Mode Selector",
            "evidence_sources": [
                "research_document",
                "private_sterile_publication_package_manifest",
                "knowledge_graph_quality_summary",
                "final_publication_output_authorization_protocol",
                "private_publication_repository_remote_audit",
            ],
        },
        {
            "section_id": "plain_language_summary",
            "heading": "Plain-Language Summary",
            "evidence_sources": [
                "research_document",
                "main_article_draft",
                "supplementary_document_draft",
                "publication_citation_registry",
            ],
        },
        {
            "section_id": "evidence_to_claim_ladder",
            "heading": "Evidence-To-Claim Ladder",
            "evidence_sources": [
                "research_document",
                "publication_claim_evidence_verification_matrix",
                "final_publication_output_authorization_protocol",
            ],
        },
        {
            "section_id": "first_ten_minute_review_protocol",
            "heading": "First 10 Minutes Review Protocol",
            "evidence_sources": [
                "research_document",
                "main_article_draft",
                "supplementary_document_draft",
                "knowledge_graph_quality_summary",
                "private_publication_repository_remote_audit",
                "final_publication_output_authorization_protocol",
            ],
        },
        {
            "section_id": "research_question_answer_map",
            "heading": "Research Question Answer Map",
            "evidence_sources": [
                "research_document",
                "main_article_draft",
                "supplementary_document_draft",
                "publication_claim_evidence_verification_matrix",
                "knowledge_graph_quality_summary",
            ],
        },
        {
            "section_id": "contribution_finding_snapshot",
            "heading": "Contribution And Finding Snapshot",
            "evidence_sources": [
                "research_document",
                "main_article_draft",
                "supplementary_document_draft",
                "publication_claim_evidence_verification_matrix",
                "knowledge_graph_quality_summary",
                "private_sterile_publication_package_manifest",
            ],
        },
        {
            "section_id": "method_reading_guide",
            "heading": "Method Reading Guide",
            "evidence_sources": [
                "main_article_draft",
                "publication_citation_registry",
            ],
        },
        {
            "section_id": "guarantee_boundary_snapshot",
            "heading": "Guarantee Boundary Snapshot",
            "evidence_sources": [
                "main_article_draft",
                "research_document",
                "publication_claim_evidence_verification_matrix",
            ],
        },
        {
            "section_id": "current_evidence_snapshot",
            "heading": "Current Evidence Snapshot",
            "evidence_sources": [
                "main_article_draft",
                "supplementary_document_draft",
                "individual_experiment_report_draft",
            ],
        },
        {
            "section_id": "evidence_snapshot_reading_notes",
            "heading": "Evidence Snapshot Reading Notes",
            "evidence_sources": [
                "main_article_draft",
                "publication_claim_evidence_verification_matrix",
            ],
        },
        {
            "section_id": "review_path",
            "heading": "Review Path",
            "evidence_sources": [
                "research_document",
                "publication_authoring_decision_record",
                "private_sterile_publication_package_manifest",
            ],
        },
        {
            "section_id": "claim_safe_reading_map",
            "heading": "Claim-Safe Reading Map",
            "evidence_sources": [
                "research_document",
                "publication_claim_evidence_verification_matrix",
            ],
        },
        {
            "section_id": "reviewer_decision_matrix",
            "heading": "Reviewer Decision Matrix",
            "evidence_sources": [
                "publication_authoring_decision_record",
                "final_publication_output_authorization_protocol",
                "publication_claim_evidence_verification_matrix",
                "private_publication_repository_remote_audit",
            ],
        },
        {
            "section_id": "finalization_blocker_snapshot",
            "heading": "Finalization Blocker Snapshot",
            "evidence_sources": [
                "final_publication_output_authorization_protocol",
                "publication_authoring_decision_record",
                "publication_claim_evidence_verification_matrix",
            ],
        },
        {
            "section_id": "publication_design_basis",
            "heading": "Publication Design Basis",
            "evidence_sources": ["publication_exemplar_review"],
        },
        {
            "section_id": "repository_map",
            "heading": "Repository Map",
            "evidence_sources": ["sterile_repository_staging_manifest"],
        },
        {
            "section_id": "private_review_package",
            "heading": "Private Review Package",
            "evidence_sources": [
                "private_sterile_publication_package_manifest",
                "private_latex_html_review_output_audit",
            ],
        },
        {
            "section_id": "research_document_entry_point",
            "heading": "Research Document Entry Point",
            "evidence_sources": [
                "research_document",
                "publication_authoring_decision_record",
                "private_sterile_publication_package_manifest",
            ],
        },
        {
            "section_id": "review_handoff",
            "heading": "Review Handoff",
            "evidence_sources": [
                "private_sterile_publication_package_manifest",
                "private_publication_repository_remote_audit",
                "final_publication_output_authorization_protocol",
            ],
        },
        {
            "section_id": "claim_boundaries",
            "heading": "Claim Boundaries",
            "evidence_sources": [
                "sterile_repository_staging_manifest",
                "final_publication_output_authorization_protocol",
            ],
        },
        {
            "section_id": "knowledge_graph",
            "heading": "Knowledge Graph",
            "evidence_sources": [
                "knowledge_graph_quality_summary",
                "private_sterile_publication_package_manifest",
            ],
        },
        {
            "section_id": "provenance_graph_and_log_entry_points",
            "heading": "Provenance Graph And Log Entry Points",
            "evidence_sources": [
                "data_scientist_log",
                "data_flow_graph",
                "control_flow_graph",
                "dependency_graph",
                "system_ontology_graph",
            ],
        },
        {
            "section_id": "references",
            "heading": "References",
            "evidence_sources": ["publication_citation_registry"],
        },
    ]
    reviewer_decision_rows = [
        {
            "decision_id": "scientific_framing",
            "reviewer_question": (
                "Is the neutral wording acceptable: CQR/CV+ are experiment-scoped "
                "practical candidates, not recommendations?"
            ),
            "current_evidence": (
                "Claim-evidence matrix, Research Document, and final authorization "
                "protocol all keep method recommendation closed."
            ),
            "default_state": "keep_neutral_private_review_wording",
            "release_boundary": "No public or final method recommendation is open.",
        },
        {
            "decision_id": "venn_abers_wording",
            "reviewer_question": (
                "Is the Venn-Abers result stated narrowly enough as bridge-specific "
                "negative evidence?"
            ),
            "current_evidence": (
                "The evaluated regression bridge remains a failure-mode diagnostic; "
                "broader Venn-Abers literature claims are not rejected."
            ),
            "default_state": "keep_bridge_specific_negative_evidence_wording",
            "release_boundary": "Validated Venn-Abers regression claims remain closed.",
        },
        {
            "decision_id": "reader_surface_readiness",
            "reviewer_question": (
                "Are the Research Document, main article, and supplement readable "
                "enough for external scientific review?"
            ),
            "current_evidence": (
                "Private authoring is authorized and rendered HTML/LaTeX review "
                "outputs pass the current private render audit."
            ),
            "default_state": "revise_privately_until_reader_ready",
            "release_boundary": "Final manuscript prose remains unauthorized.",
        },
        {
            "decision_id": "kg_site_value",
            "reviewer_question": (
                "Is the KG browser useful enough to expose later as a supplementary "
                "or web artifact?"
            ),
            "current_evidence": (
                "The KG has no isolated nodes and full edge provenance/selector "
                "coverage in the current quality summary."
            ),
            "default_state": "keep_private_until_release_review",
            "release_boundary": "KG citation and GitHub Pages deployment remain closed.",
        },
        {
            "decision_id": "public_release_timing",
            "reviewer_question": (
                "After article, supplement, site, and README review, should the "
                "sterile repository be made public?"
            ),
            "current_evidence": (
                "The private GitHub review repository exists and local/remote "
                "commits match, but public release is explicitly closed."
            ),
            "default_state": "keep_private",
            "release_boundary": "Public release requires a later explicit approval record.",
        },
    ]
    artifact_entry_rows = [
        {
            "entry_point": "Start here",
            "artifact": "manuscript/research_document.md",
            "reader_job": "Read the integrated narrative before inspecting separate article and supplement surfaces.",
            "boundary": "Private review narrative only; not public release.",
        },
        {
            "entry_point": "Main article",
            "artifact": "manuscript/main_article_draft.md",
            "reader_job": "Inspect the compact claim-evidence map, notation, headline descriptive results, and limitations.",
            "boundary": "Private final-prose review draft only; no public/submission final manuscript.",
        },
        {
            "entry_point": "Supplement",
            "artifact": "manuscript/supplementary_document_draft.md",
            "reader_job": "Inspect robustness, post-selection, endpoint, fairness, duplicate, and traceability evidence.",
            "boundary": "Detailed audit support only; no claim upgrade.",
        },
        {
            "entry_point": "Individual report",
            "artifact": "manuscript/individual_experiment_report_draft.md",
            "reader_job": "Review the author-stamped experiment summary and result interpretation details.",
            "boundary": "Experiment report draft only; no recommendation.",
        },
        {
            "entry_point": "KG browser",
            "artifact": "site/kg_browser.html",
            "reader_job": (
                "Use guided trace presets for claim gates, then traverse claim, "
                "artifact, method, dataset, and quality-check links with provenance."
            ),
            "boundary": "Private browser only; not a citable web artifact.",
        },
        {
            "entry_point": "Release gate",
            "artifact": "PUBLIC_RELEASE_REVIEW_CHECKLIST.md",
            "reader_job": "Check the blocked public-release, citation, GitHub Pages, and method-recommendation gates.",
            "boundary": "Review checklist only; public release remains closed.",
        },
    ]
    article_supplement_crosswalk_rows = [
        {
            "main_article_surface": "CQR/CV+ descriptive performance",
            "readme_pointer": "Current Evidence Snapshot",
            "supplement_pointer": "Supplement Reader Crosswalk; S1-S2",
            "closed_claim": "No final selection or general recommendation.",
        },
        {
            "main_article_surface": "Venn-Abers bridge negative evidence",
            "readme_pointer": "Plain-Language Summary; Claim Boundaries",
            "supplement_pointer": "Supplement Reader Crosswalk; S2/S6",
            "closed_claim": "No validated Venn-Abers regression interval claim.",
        },
        {
            "main_article_surface": "Bounded-support validity",
            "readme_pointer": "Current Evidence Snapshot; Claim Boundaries",
            "supplement_pointer": "S3 bounded-support endpoint policy",
            "closed_claim": "No bounded-support validity claim.",
        },
        {
            "main_article_surface": "Population fairness",
            "readme_pointer": "Current Evidence Snapshot; Claim Boundaries",
            "supplement_pointer": "S4 fairness group diagnostics",
            "closed_claim": "No population fairness claim.",
        },
        {
            "main_article_surface": "KG traceability and release state",
            "readme_pointer": "Knowledge Graph; Private Review Package",
            "supplement_pointer": "S6 traceability and release state",
            "closed_claim": "No public citable KG/site/repository release.",
        },
    ]
    provenance_graph_log_rows = build_provenance_graph_log_rows()
    repository_map_rows = build_repository_map_rows()
    finalization_blocker_rows = build_finalization_blocker_rows(final_authorization)

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
            "check_id": "public_release_and_citable_status_still_closed",
            "status": (
                "pass"
                if final_auth_s.get("release_authorized_count") == 0
                and final_auth_s.get("working_repository_final_citable") is False
                and authoring_decision_s.get("final_public_release_authorized") is False
                and private_remote_s.get("remote_visibility") == "PRIVATE"
                and private_remote_s.get("commit_match") is True
                else "fail"
            ),
            "evidence": {
                "release_authorized_count": final_auth_s.get(
                    "release_authorized_count"
                ),
                "working_repository_final_citable": final_auth_s.get(
                    "working_repository_final_citable"
                ),
                "final_public_release_authorized": authoring_decision_s.get(
                    "final_public_release_authorized"
                ),
                "private_remote_visibility": private_remote_s.get("remote_visibility"),
                "private_remote_commit_match": private_remote_s.get("commit_match"),
            },
        },
        {
            "check_id": "readme_remains_neutral_and_unreleased",
            "status": "pass",
            "evidence": {
                "final_manuscript_prose_permission": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "positive_claim_promotion_authorized": False,
                "release_authorized": False,
            },
        },
        {
            "check_id": "publication_exemplar_review_ready",
            "status": (
                "pass"
                if exemplar_s.get("overall_status")
                == "publication_exemplar_review_ready"
                and exemplar_s.get("method_recommendation_authorized") is False
                and exemplar_s.get("public_release_authorized") is False
                else "fail"
            ),
            "evidence": {
                "publication_exemplar_review_status": exemplar_s.get("overall_status"),
                "method_recommendation_authorized": exemplar_s.get(
                    "method_recommendation_authorized"
                ),
                "public_release_authorized": exemplar_s.get(
                    "public_release_authorized"
                ),
            },
        },
        {
            "check_id": "private_review_package_status_traceable",
            "status": (
                "pass"
                if private_package_s.get("overall_status")
                == "private_sterile_publication_package_ready"
                and private_package_s.get("public_release_authorized") is False
                and private_package_s.get("method_recommendation_authorized") is False
                and private_package_s.get("positive_claim_promotion_authorized")
                is False
                and authoring_decision_s.get("research_document_authoring_authorized")
                is True
                else "fail"
            ),
            "evidence": {
                "private_package_status": private_package_s.get("overall_status"),
                "private_render_audit_status": private_render_audit_s.get(
                    "overall_status"
                ),
                "research_document_status": research_document_s.get("overall_status"),
                "public_release_authorized": private_package_s.get(
                    "public_release_authorized"
                ),
            },
        },
        {
            "check_id": "claim_safe_reading_map_complete",
            "status": (
                "pass"
                if len(claim_safe_reading_rows)
                == int(
                    research_document_s.get("claim_language_guardrail_row_count") or 0
                )
                and all(
                    row["claim_review_status"] == "pass"
                    and row["allowed_publication_sentence"]
                    and row["evidence_gate"]
                    and row["blocked_reading"]
                    for row in claim_safe_reading_rows
                )
                else "fail"
            ),
            "evidence": {
                "claim_safe_reading_row_count": len(claim_safe_reading_rows),
                "research_document_claim_language_guardrail_row_count": (
                    research_document_s.get("claim_language_guardrail_row_count")
                ),
                "claim_review_status_counts": research_document_s.get(
                    "claim_review_status_counts"
                ),
            },
        },
        {
            "check_id": "finalization_blocker_snapshot_complete",
            "status": (
                "pass"
                if len(finalization_blocker_rows)
                == int(final_auth_s.get("authorization_row_count") or 0)
                and len(finalization_blocker_rows)
                == int(final_auth_s.get("active_final_blocker_count") or 0)
                and all(
                    row["authorization_status"] == "blocked_no_final_authorization"
                    and row["blocked_current_action"]
                    and row["allowed_current_action"]
                    and row["required_before_authorization"]
                    for row in finalization_blocker_rows
                )
                else "fail"
            ),
            "evidence": {
                "finalization_blocker_row_count": len(finalization_blocker_rows),
                "authorization_row_count": final_auth_s.get("authorization_row_count"),
                "active_final_blocker_count": final_auth_s.get(
                    "active_final_blocker_count"
                ),
            },
        },
        {
            "check_id": "provenance_graph_log_entry_points_complete",
            "status": (
                "pass"
                if len(provenance_graph_log_rows) == 5
                and all(
                    row["review_task"]
                    and row["source_artifact"]
                    and row["package_artifact"]
                    and row["reader_job"]
                    and row["boundary"]
                    for row in provenance_graph_log_rows
                )
                else "fail"
            ),
            "evidence": {
                "provenance_graph_log_row_count": len(provenance_graph_log_rows),
            },
        },
        {
            "check_id": "repository_map_paths_are_reviewable",
            "status": (
                "pass"
                if len(repository_map_rows) >= 8
                and all(
                    row["package_item"]
                    and row["package_path"]
                    and row["review_job"]
                    and row["current_review_status"]
                    for row in repository_map_rows
                )
                else "fail"
            ),
            "evidence": {
                "repository_map_row_count": len(repository_map_rows),
                "package_paths": [row["package_path"] for row in repository_map_rows],
            },
        },
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]

    summary = {
        "overall_status": (
            "sterile_repository_readme_draft_ready"
            if not failed_checks
            else "sterile_repository_readme_draft_blocked"
        ),
        "draft_not_final": True,
        "author_name": AUTHOR_NAME,
        "author_role": AUTHOR_ROLE,
        "author_email": AUTHOR_EMAIL,
        "author_header": f"Author: {AUTHOR_NAME}, {AUTHOR_ROLE}",
        "publication_completed_rows": main_s.get(
            "publication_completed_rows", individual_s.get("publication_completed_rows")
        ),
        "dataset_count": main_s.get("dataset_count", individual_s.get("dataset_count")),
        "dataset_alpha_cell_count": main_s.get(
            "dataset_alpha_cell_count", individual_s.get("dataset_alpha_cell_count")
        ),
        "method_count": main_s.get("method_count", individual_s.get("method_count")),
        "cqr_frontier_cell_count": main_s.get("cqr_frontier_cell_count"),
        "mondrian_frontier_cell_count": main_s.get("mondrian_frontier_cell_count"),
        "cv_plus_frontier_cell_count": main_s.get("cv_plus_frontier_cell_count"),
        "cqr_row_weighted_coverage_mean": individual_facts.get(
            "cqr_row_weighted_coverage_mean"
        ),
        "venn_undercoverage_run_count": main_s.get("venn_undercoverage_run_count"),
        "bounded_support_validity_ready_bundle_count": main_s.get(
            "bounded_support_validity_ready_bundle_count"
        ),
        "fairness_population_ready_bundle_count": main_s.get(
            "fairness_population_ready_bundle_count"
        ),
        "supplement_blueprint_row_count": supplement_s.get(
            "supplement_blueprint_row_count"
        ),
        "supplement_section_count": supplement_s.get("supplement_section_count"),
        "sterile_required_content_row_count": staging_s.get(
            "required_content_row_count"
        ),
        "sterile_required_content_traceable_count": staging_s.get(
            "required_content_traceable_count"
        ),
        "sterile_candidate_inclusion_risk_hit_count": staging_s.get(
            "candidate_inclusion_risk_hit_count"
        ),
        "citation_row_count": citation_s.get("citation_row_count"),
        "bibtex_entry_count": citation_s.get("bibtex_entry_count"),
        "kg_node_count": kg_graph.get("node_count"),
        "kg_edge_count": kg_graph.get("edge_count"),
        "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
        "kg_average_edge_confidence": kg_traceability.get("average_edge_confidence"),
        "private_review_package_status": private_package_s.get("overall_status"),
        "private_review_package_copied_file_count": private_package_s.get(
            "copied_file_count"
        ),
        "private_review_package_excluded_file_count": private_package_s.get(
            "excluded_file_count"
        ),
        "private_review_package_failed_check_count": private_package_s.get(
            "failed_check_count"
        ),
        "private_review_package_path_risk_hit_count": private_package_s.get(
            "path_risk_hit_count"
        ),
        "private_review_package_secret_pattern_hit_count": private_package_s.get(
            "secret_pattern_hit_count"
        ),
        "private_render_audit_status": private_render_audit_s.get("overall_status"),
        "private_render_audit_html_quality_pass_count": private_render_audit_s.get(
            "html_quality_pass_count"
        ),
        "private_render_audit_latex_compile_pass_count": private_render_audit_s.get(
            "latex_compile_pass_count"
        ),
        "private_render_audit_failed_check_count": private_render_audit_s.get(
            "failed_check_count"
        ),
        "research_document_status": research_document_s.get("overall_status"),
        "research_document_authoring_authorized": research_document_s.get(
            "research_document_authoring_authorized"
        ),
        "research_document_public_release_authorized": research_document_s.get(
            "public_release_authorized"
        ),
        "publication_authoring_decision_status": authoring_decision_s.get(
            "overall_status"
        ),
        "publication_authoring_final_public_release_authorized": (
            authoring_decision_s.get("final_public_release_authorized")
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
        "kg_browser_guided_trace_preset_count": private_package_s.get(
            "kg_browser_guided_trace_preset_count"
        ),
        "private_remote_visibility": private_remote_s.get("remote_visibility"),
        "private_remote_commit_match": private_remote_s.get("commit_match"),
        "publication_exemplar_source_row_count": exemplar_s.get(
            "external_source_row_count"
        ),
        "publication_exemplar_design_decision_row_count": exemplar_s.get(
            "design_decision_row_count"
        ),
        "reviewer_decision_row_count": len(reviewer_decision_rows),
        "finalization_blocker_row_count": len(finalization_blocker_rows),
        "blocked_finalization_blocker_row_count": sum(
            1
            for row in finalization_blocker_rows
            if row["authorization_status"] == "blocked_no_final_authorization"
        ),
        "artifact_entry_row_count": len(artifact_entry_rows),
        "provenance_graph_log_row_count": len(provenance_graph_log_rows),
        "repository_map_row_count": len(repository_map_rows),
        "article_supplement_crosswalk_row_count": len(
            article_supplement_crosswalk_rows
        ),
        "research_question_row_count": len(research_question_rows),
        "contribution_finding_row_count": len(contribution_finding_rows),
        "paper_architecture_row_count": len(paper_architecture_rows),
        "main_article_guarantee_boundary_row_count": len(main_article_guarantee_rows),
        "plain_language_summary_row_count": len(plain_language_summary_rows),
        "research_document_plain_language_summary_row_count": (
            research_document_s.get("plain_language_summary_row_count")
        ),
        "result_interpretation_ladder_row_count": len(
            result_interpretation_ladder_rows
        ),
        "research_document_result_interpretation_ladder_row_count": (
            research_document_s.get("result_interpretation_ladder_row_count")
        ),
        "claim_safe_reading_row_count": len(claim_safe_reading_rows),
        "research_document_claim_language_guardrail_row_count": (
            research_document_s.get("claim_language_guardrail_row_count")
        ),
        "research_document_claim_review_status_counts": research_document_s.get(
            "claim_review_status_counts"
        ),
        "private_review_package_created": (
            private_package_s.get("overall_status")
            == "private_sterile_publication_package_ready"
        ),
        "private_publication_repository_created": (
            private_remote_s.get("overall_status")
            == "private_publication_repository_remote_ready"
        ),
        "private_publication_repository_url": private_remote_s.get(
            "remote_repository_url"
        ),
        "private_publication_repository_visibility": private_remote_s.get(
            "remote_visibility"
        ),
        "private_publication_repository_commit_match": private_remote_s.get(
            "commit_match"
        ),
        "private_repository_created": (
            private_remote_s.get("overall_status")
            == "private_publication_repository_remote_ready"
        ),
        "sterile_repository_creation_authorized": final_auth_s.get(
            "sterile_repository_creation_authorized"
        ),
        "release_authorized": False,
        "public_release_authorized": authoring_decision_s.get(
            "final_public_release_authorized"
        ),
        "working_repository_final_citable": final_auth_s.get(
            "working_repository_final_citable"
        ),
        "final_manuscript_prose_permission": False,
        "method_recommendation_authorized": False,
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "positive_claim_promotion_authorized": False,
        "analysis_only_no_champion_method": final_auth_s.get(
            "analysis_only_no_champion_method"
        ),
        "result_reporting_policy": final_auth_s.get("result_reporting_policy"),
        "failed_check_count": len(failed_checks),
    }
    reviewer_front_door_rows = build_reviewer_front_door_rows(summary)
    review_at_a_glance_rows = build_review_at_a_glance_rows(summary)
    first_ten_minute_rows = build_first_ten_minute_rows(summary)
    reviewer_acceptance_rows = build_reviewer_acceptance_rows(summary)
    private_review_contract_rows = build_private_review_contract_rows(summary)
    summary["reviewer_front_door_row_count"] = len(reviewer_front_door_rows)
    summary["review_at_a_glance_row_count"] = len(review_at_a_glance_rows)
    summary["first_ten_minute_review_row_count"] = len(first_ten_minute_rows)
    summary["reviewer_acceptance_row_count"] = len(reviewer_acceptance_rows)
    summary["private_review_contract_row_count"] = len(private_review_contract_rows)
    reader_mode_selector_rows = build_reader_mode_selector_rows(summary)
    summary["reader_mode_selector_row_count"] = len(reader_mode_selector_rows)
    result_verification_command_rows = build_result_verification_command_rows()
    summary["result_verification_command_row_count"] = len(
        result_verification_command_rows
    )
    environment_data_access_rows = build_environment_data_access_rows(summary)
    summary["environment_data_access_row_count"] = len(environment_data_access_rows)

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "summary": summary,
        "readme_sections": readme_sections,
        "reviewer_front_door_rows": reviewer_front_door_rows,
        "review_at_a_glance_rows": review_at_a_glance_rows,
        "first_ten_minute_review_rows": first_ten_minute_rows,
        "reviewer_acceptance_rows": reviewer_acceptance_rows,
        "private_review_contract_rows": private_review_contract_rows,
        "reader_mode_selector_rows": reader_mode_selector_rows,
        "result_verification_command_rows": result_verification_command_rows,
        "environment_data_access_rows": environment_data_access_rows,
        "reviewer_decision_rows": reviewer_decision_rows,
        "finalization_blocker_rows": finalization_blocker_rows,
        "artifact_entry_rows": artifact_entry_rows,
        "provenance_graph_log_rows": provenance_graph_log_rows,
        "repository_map_rows": repository_map_rows,
        "research_question_rows": research_question_rows,
        "contribution_finding_rows": contribution_finding_rows,
        "paper_architecture_rows": paper_architecture_rows,
        "plain_language_summary_rows": plain_language_summary_rows,
        "result_interpretation_ladder_rows": result_interpretation_ladder_rows,
        "main_article_guarantee_boundary_rows": main_article_guarantee_rows,
        "claim_safe_reading_rows": claim_safe_reading_rows,
        "article_supplement_crosswalk_rows": article_supplement_crosswalk_rows,
        "publication_design_decision_rows": design_decision_rows,
        "citation_keys": {
            url: cite[url] for url in required_citation_urls() if url in cite
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This README describes the private sterile publication review package, not the final public release README.",
            "The private package/repository supports review only; it does not authorize public visibility, GitHub Pages deployment, citation, or method recommendation.",
            "The public/citable release remains blocked until explicit reviewer approval and a separate release authorization record.",
            "The study reports observed diagnostics and does not recommend a conformal method.",
            "Research Document authoring is private-review output and not a public release.",
            "The knowledge-graph browser is private-review output and not a public citable component.",
            "Publication exemplar review is design guidance only, not empirical method evidence.",
            "CQR is not claimed as the best regression conformal method in general.",
            "The current Venn-Abers bridge does not support a validated regression interval claim.",
            "Group diagnostics do not establish population fairness.",
            "Endpoint diagnostics do not establish bounded-support validity.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    cite = payload["citation_keys"]
    split_key = cite["https://arxiv.org/abs/1604.04173"]
    cqr_key = cite["https://arxiv.org/abs/1905.03222"]
    jack_key = cite["https://arxiv.org/abs/1905.02928"]
    jab_key = cite["https://arxiv.org/abs/2002.09025"]
    venn_key = cite["https://proceedings.mlr.press/v91/nouretdinov18a.html"]

    lines = [
        "# Regression Conformal Prediction Study",
        "",
        "> Private review README for the generated sterile publication package and private GitHub review repository. This file does not authorize public release, recommend a method, or make final manuscript claims.",
        "",
        "## One-Minute Thesis",
        "",
        (
            "This repository is a private, sterile review package for a neutral "
            "empirical study of regression conformal prediction. The central "
            "result is scoped: CQR/CV+ were observed as strong practical "
            "candidates in these experiments, while method recommendation and "
            "final selection remain closed."
        ),
        "",
        (
            "The evaluated Venn-Abers regression bridge is reported as negative "
            "evidence for this bridge: the expected strong regression solution "
            "did not emerge in these experiments. This does not reject the "
            "broader Venn-Abers literature."
        ),
        "",
        (
            "The knowledge graph is a browsable traceability surface linking "
            "claims, reports, methods, citations, quality gates, and source "
            "artifacts. It is valuable as a private supplementary/web artifact "
            "candidate; public KG citation and GitHub Pages publication remain "
            "closed until release review."
        ),
        "",
        "## Status",
        "",
        f"- Author: {s['author_name']}, {s['author_role']}.",
        f"- Contact: {s['author_email']}.",
        f"- README draft status: `{s['overall_status']}`.",
        f"- Private review package created: `{s['private_review_package_created']}`.",
        f"- Private GitHub review repository: `{s['private_publication_repository_visibility']}`.",
        f"- Private GitHub review repository commit match: `{s['private_publication_repository_commit_match']}`.",
        f"- Public release authorized: `{s['public_release_authorized']}`.",
        f"- Working repository final-citable: `{s['working_repository_final_citable']}`.",
        f"- Method recommendation authorized: `{s['method_recommendation_authorized']}`.",
        f"- Result reporting policy: `{s['result_reporting_policy']}`.",
        f"- Research Document status: `{s['research_document_status']}`.",
        f"- Private review surfaces passing: {fmt(s['private_review_surface_pass_count'])} / {fmt(s['private_review_surface_count'])}.",
        "",
        "## Reader Mode Selector",
        "",
        (
            "Use this selector before scrolling through the full README. It "
            "routes four common reviewer modes to the right first artifact and "
            "keeps the release and method-selection boundaries visible."
        ),
        "",
        "| Reader mode | Use when | Open first | Then check | Do not do |",
        "|---|---|---|---|---|",
    ]
    for row in payload["reader_mode_selector_rows"]:
        lines.append(
            "| "
            f"{row['reader_mode']} | "
            f"{row['use_when']} | "
            f"{row['open_first']} | "
            f"{row['then_check']} | "
            f"{row['do_not_do']} |"
        )
    lines.extend(
        [
            "",
        "## Private Review Contract",
        "",
        (
            "Use this contract before interpreting any result. It separates "
            "private scientific review from public citation, publication, GitHub "
            "Pages deployment, final method selection, and positive claim "
            "promotion."
        ),
        "",
        "| Reviewer action | Current answer | Evidence | Boundary |",
        "|---|---|---|---|",
        ]
    )
    for row in payload["private_review_contract_rows"]:
        lines.append(
            "| "
            f"{row['review_action']} | "
            f"{row['current_answer']} | "
            f"{row['evidence']} | "
            f"{row['boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Reviewer Acceptance Checklist",
            "",
            (
                "Use this checklist before treating the package as reader-ready for "
                "private review. These checks accept review readability only; they "
                "do not authorize public release, KG citation, final prose, or a "
                "method recommendation."
            ),
            "",
            "| Acceptance item | Evidence to inspect | Reject private review readiness if |",
            "|---|---|---|",
        ]
    )
    for row in payload["reviewer_acceptance_rows"]:
        lines.append(
            "| "
            f"[ ] {row['acceptance_item']} | "
            f"{row['evidence']} | "
            f"{row['reject_if']} |"
        )
    lines.extend(
        [
            "",
            "## Reviewer Front Door",
            "",
            (
                "Use this as the first 60-second route through the package. It "
                "separates reading, checking, tracing, and release decisions so a "
                "reviewer does not turn a private diagnostic result into a public "
                "claim."
            ),
            "",
            "| Lane | Open first | Reader action | Safe takeaway | Closed boundary |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["reviewer_front_door_rows"]:
        lines.append(
            "| "
            f"{row['lane']} | "
            f"{row['open_first']} | "
            f"{row['reader_action']} | "
            f"{row['safe_takeaway']} | "
            f"{row['closed_boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Review At A Glance",
            "",
            (
                "Use this table as the first 30-second review map. It states what "
                "to open first, what question that surface answers, and which "
                "claim boundary remains closed before any public-release decision."
            ),
            "",
            "| Review need | What to read | What it answers | Boundary |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["review_at_a_glance_rows"]:
        lines.append(
            "| "
            f"{row['review_need']} | "
            f"{row['what_to_read']} | "
            f"{row['what_it_answers']} | "
            f"{row['boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Plain-Language Summary",
            "",
            (
                "This project studies regression conformal prediction: methods that "
                "wrap regression models with prediction intervals calibrated to a "
                f"target coverage level `1 - alpha` [@{split_key}]. CQR uses lower "
                f"and upper quantile-regression models before conformal calibration "
                f"[@{cqr_key}]. CV+ and jackknife-style methods use out-of-fold or "
                f"leave-one-out predictions to account for model-fitting variability "
                f"[@{jack_key}; @{jab_key}]. Venn-Abers-related evidence is retained "
                f"as diagnostic and boundary evidence [@{venn_key}]."
            ),
            "",
            (
                "The current empirical result is descriptive. CQR/CV+ were "
                "observed as strong practical candidates in these experiments, "
                "but the project does not claim that either method is the best "
                "regression conformal method in general. The current Venn-Abers "
                "interval bridge is reported as negative/failure-mode evidence, "
                "not as a validated regression interval method."
            ),
            "",
            (
                "The table below mirrors the Research Document's plain-language "
                "reader surface. Each answer is paired with the evidence anchor "
                "that supports it and the stronger reading that remains closed."
            ),
            "",
            "| Reader question | Plain-language answer | Evidence anchor | Boundary |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["plain_language_summary_rows"]:
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
            "## Evidence-To-Claim Ladder",
            "",
            (
                "This README-level ladder mirrors the Research Document's "
                "Evidence-To-Claim Interpretation Ladder. Use it before reading "
                "the numeric result tables: each row states what a result layer "
                "can support, what it cannot support, and the action a reviewer "
                "should take."
            ),
            "",
            "| Evidence layer | What it can support | Evidence in this study | What it cannot support | Reader action |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["result_interpretation_ladder_rows"]:
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
            "## First 10 Minutes Review Protocol",
            "",
            (
                "Use this protocol when opening the package for the first time. "
                "It gives a short, acceptance-check driven route through the "
                "private evidence package without opening public release, final "
                "method selection, KG citation, or GitHub Pages publication."
            ),
            "",
            "| Minute | Review action | Artifact | Acceptance check | Stop if missing |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["first_ten_minute_review_rows"]:
        lines.append(
            "| "
            f"{row['minute']} | "
            f"{row['review_action']} | "
            f"`{row['artifact']}` | "
            f"{row['acceptance_check']} | "
            f"{row['stop_if_missing']} |"
        )
    lines.extend(
        [
            "",
            "## Research Question Answer Map",
            "",
            (
                "This README-level map routes into the Research Document's research "
                "questions. It states each question, the answer currently supported "
                "by the private evidence package, the evidence anchor, and the "
                "stronger interpretation that remains closed."
            ),
            "",
            "| Research question | Evidence-supported answer | Evidence anchor | Closed reading |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["research_question_rows"]:
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
            "## Contribution And Finding Snapshot",
            "",
            (
                "This README-level snapshot routes into the Research Document's "
                "Contribution And Finding Map. Each row states what the private "
                "review package can say, the evidence anchor to inspect, and the "
                "stronger reading that remains closed."
            ),
            "",
            "| Contribution or finding | Reader-safe statement | Evidence anchor | Closed reading |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["contribution_finding_rows"]:
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
            "## Paper Architecture And Review Contract",
            "",
            (
                "This README-level table routes into the main article's Paper "
                "Architecture And Review Contract. It tells reviewers which "
                "surface to use, what reader job that surface serves, and which "
                "boundary remains closed before any public-release decision."
            ),
            "",
            "| Surface | Reader job | Boundary | Source basis |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["paper_architecture_rows"]:
        lines.append(
            "| "
            f"{row['surface']} | "
            f"{row['reader_job']} | "
            f"{row['boundary']} | "
            f"{row.get('source_basis') or row.get('source_decision_id', '')} |"
        )
    lines.extend(
        [
            "",
            "## Method Reading Guide",
            "",
            (
                "Use this section as a compact decoder before reading the Research "
                "Document. The methods differ in how they build or adjust prediction "
                "intervals; the repository reports what happened under those "
                "mechanisms without turning the observations into prescriptions."
            ),
            "",
            (
                "For non-specialist readers, the main article also contains "
                "`Method Primer For Non-Specialist Readers` and `Reader Safety "
                "Checklist`, which explain `1 - alpha`, CQR, CV+, "
                "Mondrian/group calibration, and the Venn-Abers bridge result "
                "before the notation-heavy evaluation protocol. Treat those "
                "sections as orientation only: they do not open method "
                "recommendation, final selection, population fairness, or "
                "validated Venn-Abers regression claims."
            ),
            "",
            "| Method family | How to read it in this package | Boundary |",
            "|---|---|---|",
            (
                "| Split conformal | A held-out calibration set turns residual errors "
                "into an interval adjustment. | Baseline calibration mechanism, "
                "not endpoint or fairness validity. |"
            ),
            (
                "| CQR | Lower and upper quantile models are conformalized into an "
                "adaptive interval. | Strong practical candidate observed here, "
                "not a general recommendation. |"
            ),
            (
                "| CV+ / jackknife-style | Out-of-fold or leave-one-out predictions "
                "account for fitted-model variability. | Strong practical candidate "
                "observed here, with final selection still closed. |"
            ),
            (
                "| Venn-Abers bridge | A Venn-Abers-style calibration object is mapped "
                "into interval diagnostics. | Negative evidence for the evaluated "
                "bridge, not a rejection of the literature. |"
            ),
            "",
            "## Guarantee Boundary Snapshot",
            "",
            (
                "This README-level snapshot mirrors the main article's guarantee and "
                "claim boundary table. Use it before interpreting coverage, group "
                "diagnostics, frontier counts, or Venn-Abers bridge evidence."
            ),
            "",
            "| Topic | Article statement | Closed reading |",
            "|---|---|---|",
        ]
    )
    for row in payload["main_article_guarantee_boundary_rows"]:
        lines.append(
            "| "
            f"{row['topic']} | "
            f"{row['article_statement']} | "
            f"{row['closed_reading']} |"
        )
    lines.extend(
        [
            "",
            "## Review Path",
            "",
            (
                "Start with `manuscript/research_document.md`. It is the integrated "
                "private-review narrative that explains the core conformal prediction "
                "concepts for non-specialist readers, reports CQR/CV+ only as strong "
                "practical candidates observed in these experiments, and records the "
                "evaluated Venn-Abers regression bridge as negative/failure-mode "
                "evidence."
            ),
            "",
            "Then review the rendered article and supplement, the individual experiment report, the KG browser, and the governance files in this order:",
            "",
            "1. `manuscript/research_document.md`",
            "2. `PUBLIC_RELEASE_REVIEW_CHECKLIST.md`",
            "3. `rendered_outputs/main_article_review.html`",
            "4. `rendered_outputs/supplementary_document_review.html`",
            "5. `manuscript/individual_experiment_report_draft.md`",
            "6. `site/kg_browser.html`",
            "7. `governance/publication_authoring_decision_record.md`",
            "8. `governance/final_publication_output_authorization_protocol.json`",
            "",
            "## Artifact Entry Points",
            "",
            (
                "Use this table to choose the right file for the review task at hand. "
                "The package is intentionally split into narrative, evidence, browser, "
                "and governance surfaces so that a reader can inspect claims without "
                "accidentally treating a draft as a release artifact."
            ),
            "",
            "| Entry point | Artifact | Reader job | Boundary |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["artifact_entry_rows"]:
        lines.append(
            "| "
            f"{row['entry_point']} | "
            f"`{row['artifact']}` | "
            f"{row['reader_job']} | "
            f"{row['boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Provenance Graph And Log Entry Points",
            "",
            (
                "Use these files when the review question is about how the study "
                "was executed, resumed, audited, or packaged. They are provenance "
                "and navigation artifacts: they make the experiment easier to "
                "inspect, but they do not create new empirical evidence, method "
                "recommendations, public release, or final citable KG status."
            ),
            "",
            "| Review task | Source artifact | Private package artifact | Reader job | Boundary |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["provenance_graph_log_rows"]:
        lines.append(
            "| "
            f"{row['review_task']} | "
            f"`{row['source_artifact']}` | "
            f"`{row['package_artifact']}` | "
            f"{row['reader_job']} | "
            f"{row['boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Claim-Safe Reading Map",
            "",
            (
                "This table is a README-level route into the Research Document "
                "guardrails. It states which reader question each claim row "
                "answers, the README-safe wording that is currently allowed, the evidence "
                "gate that must stay attached, and the stronger reading that "
                "remains blocked."
            ),
            "",
            "| Reader question | Target | Allowed wording | Evidence gate | Blocked reading |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["claim_safe_reading_rows"]:
        lines.append(
            "| "
            f"{row['reader_question']} | "
            f"`{row['target_document']}` | "
            f"{row['allowed_publication_sentence']} | "
            f"{row['evidence_gate']} | "
            f"{row['blocked_reading']} |"
        )
    lines.extend(
        [
            "",
            "## Reviewer Decision Matrix",
            "",
            (
                "The table below separates decisions that can be made during private "
                "review from decisions that remain blocked until a later release "
                "authorization. It keeps prose revision, scientific interpretation, "
                "KG usefulness, and public visibility as separate decisions."
            ),
            "",
            "| Decision | Reviewer question | Current evidence | Default state | Release boundary |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["reviewer_decision_rows"]:
        lines.append(
            "| "
            f"`{row['decision_id']}` | "
            f"{row['reviewer_question']} | "
            f"{row['current_evidence']} | "
            f"`{row['default_state']}` | "
            f"{row['release_boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Finalization Blocker Snapshot",
            "",
            (
                "This table is the README-level view of the final-output "
                "authorization protocol. It lists what remains blocked before "
                "public release, final manuscript prose, final visual/table "
                "retention, KG/site citation, method recommendation, or positive "
                "claim promotion can be opened. The allowed-current-action column "
                "states what private review work may continue now."
            ),
            "",
            "| Blocker | Blocked action | Allowed now | Evidence gate |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["finalization_blocker_rows"]:
        lines.append(
            "| "
            f"`{row['blocker_id']}` | "
            f"{row['blocked_current_action']} | "
            f"{row['allowed_current_action']} | "
            f"{row['evidence_summary']} |"
        )
    lines.extend(
        [
            "",
            "## Publication Design Basis",
            "",
            (
                "This README and the private site are shaped by a source-backed "
                "review of comparable conformal prediction papers, repositories, "
                "documentation sites, and companion code releases. The review is "
                "used only for publication-package design: navigation, source "
                "traceability, supplement structure, KG exposure, and release "
                "gating. It is not empirical method evidence."
            ),
            "",
            "| Design decision | Project application |",
            "|---|---|",
        ]
    )
    for row in payload["publication_design_decision_rows"]:
        lines.append("| " f"{row['decision']} | " f"{row['project_application']} |")
    lines.extend(
        [
            "",
            "## Current Evidence Snapshot",
            "",
            "| Item | Value |",
            "|---|---:|",
            f"| Publication-scoped completed rows | {fmt(s['publication_completed_rows'])} |",
            f"| Datasets | {fmt(s['dataset_count'])} |",
            f"| Dataset-alpha cells | {fmt(s['dataset_alpha_cell_count'])} |",
            f"| Conformal-method labels | {fmt(s['method_count'])} |",
            f"| CQR descriptive frontier cells | {fmt(s['cqr_frontier_cell_count'])} |",
            f"| Mondrian descriptive frontier cells | {fmt(s['mondrian_frontier_cell_count'])} |",
            f"| CV+ descriptive frontier cells | {fmt(s['cv_plus_frontier_cell_count'])} |",
            f"| CQR row-weighted coverage mean | {fmt(s['cqr_row_weighted_coverage_mean'])} |",
            f"| Venn-Abers bridge undercoverage runs | {fmt(s['venn_undercoverage_run_count'])} |",
            f"| Bounded-support validity-ready bundles | {fmt(s['bounded_support_validity_ready_bundle_count'])} |",
            f"| Population-fairness-ready bundles | {fmt(s['fairness_population_ready_bundle_count'])} |",
            f"| Supplement sections | {fmt(s['supplement_section_count'])} |",
            f"| Private KG browser nodes | {fmt(s['kg_browser_node_count'])} |",
            f"| Private KG browser edges | {fmt(s['kg_browser_edge_count'])} |",
            "",
            "## Result Verification Commands",
            "",
            (
                "Use these commands from the source repository root to verify the "
                "numbers and review surfaces before refreshing the private sterile "
                "package. The copied tests and scripts are also present under "
                "`reproducibility/` inside the private package, but the source "
                "repository remains the authoritative execution environment for "
                "these checks."
            ),
            "",
            "| Verification task | Command | Expected evidence | Primary artifact | Boundary |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["result_verification_command_rows"]:
        lines.append(
            "| "
            f"{row['verification_task']} | "
            f"`{row['command']}` | "
            f"{row['expected_evidence']} | "
            f"`{row['primary_artifact']}` | "
            f"{row['boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Environment And Data Access",
            "",
            (
                "Use this table before running verification commands. It states "
                "which environment, code, policy, and packaging surfaces are "
                "available in the private package, and which data or release "
                "claims remain closed."
            ),
            "",
            "| Surface | Package path | Reader use | Evidence | Boundary |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["environment_data_access_rows"]:
        lines.append(
            "| "
            f"{row['surface']} | "
            f"`{row['package_path']}` | "
            f"{row['reader_use']} | "
            f"{row['evidence']} | "
            f"{row['boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Evidence Snapshot Reading Notes",
            "",
            (
                "Read the snapshot as a scoped audit summary. Frontier-cell counts "
                "describe observed coverage/width trade-offs; row-weighted coverage "
                "summarizes empirical coverage over completed result blocks; "
                "undercoverage runs mark failure modes; and zero-ready bundles are "
                "closed claim gates. These numbers support private review and "
                "interpretation, not public release or final method selection."
            ),
            "",
            "## Article-Supplement Evidence Crosswalk",
            "",
            (
                "The main article is intentionally compact. This crosswalk points "
                "each major main-article surface to the README location, the "
                "supplement location, and the stronger claim that remains closed. "
                "It is meant for review navigation, not claim expansion."
            ),
            "",
            "| Main article surface | README pointer | Supplement pointer | Closed claim |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["article_supplement_crosswalk_rows"]:
        lines.append(
            "| "
            f"{row['main_article_surface']} | "
            f"{row['readme_pointer']} | "
            f"{row['supplement_pointer']} | "
            f"{row['closed_claim']} |"
        )
    lines.extend(
        [
            "",
            "## Repository Map",
            "",
            (
                "This private review package contains a polished review README, "
                "article drafts, supplementary drafts, an individual experiment "
                "report, a knowledge-graph export, reproducibility material, "
                "citation metadata, and governed review outputs. Public release "
                "and final citable status remain closed until explicit reviewer "
                "approval."
            ),
            "",
            "| Private review package item | Package path | Review job | Current review status |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["repository_map_rows"]:
        lines.append(
            "| "
            f"{row['package_item']} | "
            f"`{row['package_path']}` | "
            f"{row['review_job']} | "
            f"{row['current_review_status']} |"
        )
    lines.extend(
        [
            "",
            "## Private Review Package",
            "",
            (
                "A local/private sterile review package has been generated for inspection. "
                "It is not a public release and does not make the working repository "
                "citable. The package manifest reports status "
                f"`{s['private_review_package_status']}`, "
                f"{fmt(s['private_review_package_copied_file_count'])} copied files, "
                f"{fmt(s['private_review_package_excluded_file_count'])} excluded files, "
                f"and {fmt(s['private_review_package_failed_check_count'])} failed checks. "
                "The private render audit reports status "
                f"`{s['private_render_audit_status']}` with "
                f"{fmt(s['private_render_audit_html_quality_pass_count'])} HTML quality "
                f"passes and {fmt(s['private_render_audit_latex_compile_pass_count'])} "
                "LaTeX/BibTeX compile passes."
            ),
            "",
            (
                f"The private GitHub publication repository remains `{s['private_remote_visibility']}` "
                f"with remote/local commit match `{s['private_remote_commit_match']}`. "
                "This state supports private review only; it does not make the package "
                "public or citable."
            ),
            "",
            "## Research Document Entry Point",
            "",
            (
                "Use `manuscript/research_document.md` as the primary reader-facing "
                "review surface. It is written for private review, explains the core "
                "conformal prediction concepts for non-specialist readers, reports "
                "CQR/CV+ only as strong practical candidates observed in these "
                "experiments, and reports the evaluated Venn-Abers regression bridge "
                "as negative/failure-mode evidence. The governing decision record is "
                "`governance/publication_authoring_decision_record.md`."
            ),
            "",
            "## Review Handoff",
            "",
            (
                "Start with `USER_REVIEW_HANDOFF.md` for the private review order, "
                "approval boundaries, and questions to answer before any public-release "
                "decision."
            ),
            "",
            "## Claim Boundaries",
            "",
        ]
    )
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(
        [
            "",
            "## Knowledge Graph",
            "",
            (
                f"The current knowledge graph has {fmt(s['kg_node_count'])} nodes, "
                f"{fmt(s['kg_edge_count'])} edges, and "
                f"{fmt(s['kg_isolated_node_count'])} isolated nodes. Average edge "
                f"confidence is {fmt(s['kg_average_edge_confidence'])}. The graph "
                "links datasets, configs, methods, reports, claim boundaries, "
                "citations, and staging artifacts."
            ),
            "",
            (
                "The private review package also contains `site/kg_browser.html` "
                "and `site/kg_browser_data.json`, a static browser over "
                f"{fmt(s['kg_browser_node_count'])} nodes, "
                f"{fmt(s['kg_browser_edge_count'])} edges, "
                f"{fmt(s['kg_browser_node_type_count'])} node types, and "
                f"{fmt(s['kg_browser_relation_type_count'])} relation types. "
                "The browser exposes node search, node-type filtering, edge "
                "confidence, edge provenance, and "
                f"{fmt(s['kg_browser_guided_trace_preset_count'])} guided trace "
                "presets for review: Final selected-method gate, Venn-Abers "
                "bridge gate, Claim/evidence matrix, Claim-safe README map, "
                "Research Document guardrail, Private package manifest, and "
                "KG quality summary."
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
