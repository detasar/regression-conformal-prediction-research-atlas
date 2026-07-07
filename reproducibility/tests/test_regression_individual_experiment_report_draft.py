import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT / "experiments/regression/manuscript/individual_experiment_report_draft.json"
)
REPORT = ROOT / "experiments/regression/manuscript/individual_experiment_report_draft.md"
REGISTRY = ROOT / "experiments/regression/manuscript/publication_citation_registry.json"
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def load_kg_graph():
    return json.loads(KG_QUALITY.read_text(encoding="utf-8"))["graph"]


def test_individual_experiment_report_draft_is_source_backed_and_neutral():
    payload = load_artifact()
    summary = payload["summary"]
    facts = payload["report_facts"]
    graph = load_kg_graph()

    assert summary["overall_status"] == "individual_experiment_report_draft_ready"
    assert summary["draft_not_final"] is True
    assert summary["publication_completed_rows"] == 145839
    assert summary["dataset_count"] == 67
    assert summary["dataset_alpha_cell_count"] == 95
    assert summary["method_count"] == 28
    assert summary["primary_diagnostic_method"] == "cqr"
    assert summary["final_selection_claim_status"] == "blocked"
    assert summary["venn_abers_positive_validation_ready"] is False
    assert summary["bounded_support_validity_ready_bundle_count"] == 0
    assert summary["fairness_population_ready_bundle_count"] == 0
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["release_authorized"] is False
    assert summary["failed_check_count"] == 0

    assert facts["cqr_frontier_cell_count"] == 56
    assert facts["mondrian_frontier_cell_count"] == 15
    assert facts["cv_plus_frontier_cell_count"] == 13
    assert facts["venn_undercoverage_run_count"] == 14
    assert facts["kg_node_count"] == graph["node_count"]
    assert facts["kg_edge_count"] == graph["edge_count"]


def test_individual_experiment_report_draft_uses_registered_citations():
    payload = load_artifact()
    report = REPORT.read_text(encoding="utf-8")
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
        "nouretdinov2018ivapd",
        "vanderlaan2025generalized_venn_abers",
    ]:
        assert required_key in cited
        assert required_key in payload["citation_keys"].values()


def test_individual_experiment_report_draft_markdown_contains_expected_sections():
    report = REPORT.read_text(encoding="utf-8")

    assert "Author: Emre Tasar, Data Scientist" in report
    assert "Email: detasar@gmail.com" in report
    for heading in [
        "## Executive Summary",
        "## Reader Primer",
        "## Empirical Scope",
        "## Method Findings",
        "## Selection Robustness Diagnostics",
        "## Negative And Blocked Claims",
        "## Traceability And Release State",
        "## Evidence Sources",
        "## References",
    ]:
        assert heading in report

    assert "unavailable in draft table" not in report
    assert "general recommendation" in report
    assert "no validated regression interval claim" in report
    assert "no population fairness claim" in report
