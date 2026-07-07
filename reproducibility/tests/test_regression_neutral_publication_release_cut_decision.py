import json
from pathlib import Path

from experiments.regression.scripts import (
    build_neutral_publication_release_cut_decision as decision,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT
    / "experiments/regression/manuscript/"
    / "neutral_publication_release_cut_decision.json"
)
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def copy_sources(tmp_path):
    for path in decision.SOURCE_PATHS.values():
        src = ROOT / path
        dst = tmp_path / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def test_neutral_publication_release_cut_is_ready_and_private_only():
    payload = load_artifact()
    summary = payload["summary"]
    kg_graph = json.loads(KG_QUALITY.read_text(encoding="utf-8"))["graph"]

    assert summary["overall_status"] == "neutral_publication_release_cut_ready"
    assert (
        summary["phase_state"]
        == "neutral_private_release_cut_ready_public_release_blocked"
    )
    assert summary["neutral_private_sterile_repository_preparation_authorized"] is True
    assert summary["neutral_article_supplement_output_assembly_authorized"] is True
    assert summary["neutral_latex_html_static_site_package_authorized"] is True
    assert summary["kg_private_package_snapshot_authorized"] is True
    assert summary["authorized_next_action_count"] == 4
    assert summary["readiness_pass_count"] == summary["readiness_check_count"] == 11
    assert summary["readiness_fail_count"] == 0
    assert summary["public_release_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["raw_data_or_secret_inclusion_authorized"] is False
    assert summary["kg_node_count"] == kg_graph["node_count"]
    assert summary["kg_edge_count"] == kg_graph["edge_count"]
    assert summary["kg_isolated_node_count"] == kg_graph["isolated_node_count"]
    assert summary["failed_check_count"] == 0

    assert all(payload["output_readiness"].values())
    assert {row["action_id"] for row in payload["authorized_next_actions"]} == {
        "prepare_private_sterile_repository",
        "assemble_neutral_article_and_supplement_outputs",
        "export_citable_knowledge_graph_snapshot",
        "prepare_latex_html_and_static_site_package",
    }
    assert "method_recommendation_or_winner_language" in payload["blocked_actions"]
    assert (
        "positive_performance_fairness_bounded_support_or_venn_abers_claim"
        in payload["blocked_actions"]
    )


def test_release_cut_blocks_if_promotion_boundary_opens(tmp_path):
    copy_sources(tmp_path)
    final_auth_path = tmp_path / decision.FINAL_AUTHORIZATION
    payload = json.loads(final_auth_path.read_text(encoding="utf-8"))
    payload["summary"]["method_recommendation_authorized"] = True
    final_auth_path.write_text(json.dumps(payload), encoding="utf-8")

    result = decision.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "neutral_publication_release_cut_blocked"
    )
    assert result["summary"]["authorized_next_action_count"] == 0
    assert result["summary"]["method_recommendation_authorized"] is False
    assert checks["promotion_boundaries_remain_closed"]["status"] == "fail"


def test_release_cut_blocks_if_claim_citation_audit_is_not_ready(tmp_path):
    copy_sources(tmp_path)
    audit_path = tmp_path / decision.CLAIM_CITATION_AUDIT
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["summary"]["overall_status"] = "manuscript_claim_citation_readiness_blocked"
    payload["summary"]["failed_check_count"] = 1
    audit_path.write_text(json.dumps(payload), encoding="utf-8")

    result = decision.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "neutral_publication_release_cut_blocked"
    )
    assert result["output_readiness"]["claim_citation_ready"] is False
    assert checks["neutral_output_surfaces_ready"]["status"] == "fail"


def test_release_cut_blocks_if_public_release_is_opened(tmp_path):
    copy_sources(tmp_path)
    manifest_path = tmp_path / decision.STERILE_MANIFEST
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["summary"]["release_authorized"] = True
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    result = decision.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "neutral_publication_release_cut_blocked"
    )
    assert result["summary"]["public_release_authorized"] is False
    assert checks["private_release_cut_keeps_public_release_closed"]["status"] == "fail"
