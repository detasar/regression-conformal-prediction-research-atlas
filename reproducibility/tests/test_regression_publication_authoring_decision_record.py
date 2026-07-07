import json
from pathlib import Path

from experiments.regression.scripts import (
    build_publication_authoring_decision_record as decision_record,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT
    / "experiments/regression/manuscript/"
    / "publication_authoring_decision_record.json"
)
MARKDOWN = (
    ROOT
    / "experiments/regression/manuscript/"
    / "publication_authoring_decision_record.md"
)
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_publication_authoring_decision_record_opens_private_authoring_only():
    payload = load_artifact()
    summary = payload["summary"]
    graph = json.loads(KG_QUALITY.read_text(encoding="utf-8"))["graph"]

    assert payload["schema"] == "cpfi_regression_publication_authoring_decision_record_v1"
    assert summary["overall_status"] == "research_document_authoring_decision_ready"
    assert summary["research_document_authoring_authorized"] is True
    assert summary["private_authoring_authorized"] is True
    assert summary["browsable_kg_site_authoring_authorized"] is True
    assert summary["minimal_main_broad_supplement_authorized"] is True
    assert summary["final_public_release_authorized"] is False
    assert summary["public_repository_release_authorized"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["new_experiments_authorized"] is False
    assert summary["failed_check_count"] == 0
    assert summary["inspiration_source_count"] == 7
    assert summary["latest_numbered_user_decision_count"] == 10
    assert summary["kg_node_count"] == graph["node_count"]
    assert summary["kg_edge_count"] == graph["edge_count"]
    assert summary["kg_isolated_node_count"] == 0


def test_publication_authoring_decision_record_preserves_user_claim_boundaries():
    payload = load_artifact()
    decisions = payload["user_decisions"]
    boundaries = "\n".join(payload["claim_boundaries"])
    markdown = MARKDOWN.read_text(encoding="utf-8")

    assert decisions["scientific_framing"] == "neutral_scientific_test"
    assert (
        decisions["cqr_cv_plus_language"]
        == "CQR/CV+ were observed as strong practical candidates in these experiments."
    )
    assert "did not behave as the expected strong regression solution" in decisions[
        "venn_abers_language"
    ]
    assert decisions["new_experiments_authorized"] is False
    assert decisions["research_document_name"] == "Research Document"
    latest_decisions = payload["latest_numbered_user_decisions"]
    assert len(latest_decisions) == 10
    assert latest_decisions[0]["decision"] == "A"
    assert latest_decisions[-1]["decision"] == "No, do not open a new experiment branch."
    assert all("makale" not in row["decision"].lower() for row in latest_decisions)
    assert all("yeni deney" not in row["decision"].lower() for row in latest_decisions)
    assert "No positive fairness" in boundaries
    assert "No new experiments are authorized" in boundaries
    assert "Public release authorized: `False`" in markdown
    assert "Method recommendation authorized: `False`" in markdown
    assert "## Latest Numbered User Decisions" in markdown


def test_publication_authoring_decision_record_rebuild_is_stable():
    payload = decision_record.build_payload(ROOT)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "research_document_authoring_decision_ready"
    )
    assert payload["summary"]["failed_check_count"] == 0
    assert checks["source_artifacts_present"]["status"] == "pass"
    assert checks["neutral_empirical_phase_complete"]["status"] == "pass"
    assert checks["claim_boundaries_remain_closed"]["status"] == "pass"
    assert checks["private_package_ready"]["status"] == "pass"
    assert checks["kg_browsable_candidate_ready"]["status"] == "pass"
