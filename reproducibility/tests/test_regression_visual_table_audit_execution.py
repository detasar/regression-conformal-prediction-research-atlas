import json
from pathlib import Path

from experiments.regression.scripts import build_visual_table_audit_execution as audit


ROOT = Path(__file__).resolve().parents[1]
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
KG_NAVIGATION = ROOT / "experiments/regression/manuscript/kg_navigation_usability_audit.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_checked_in_visual_table_audit_execution_is_pre_retention_only():
    payload = audit.build_payload(Path("."))
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "visual_table_pre_retention_audit_completed_no_retained_artifacts"
    )
    assert (
        summary["phase_state"]
        == "pre_retention_audit_complete_rendering_and_final_retention_blocked"
    )
    assert summary["inventory_row_count"] == 10
    assert summary["audit_row_count"] == 10
    assert summary["expected_candidate_artifact_count"] == 10
    assert summary["pre_retention_audit_completed_count"] == 10
    assert summary["source_traceable_candidate_count"] == 10
    assert summary["pre_retention_decision_count"] == 10
    assert summary["actionable_feedback_count"] == 40
    assert summary["iteration_action_count"] == 10
    assert summary["rendered_artifact_count"] == 0
    assert summary["layout_check_deferred_count"] == 10
    assert summary["final_retained_artifact_count"] == 0
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["final_triptych_release_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["neutral_no_method_promotion_guard_active"] is True
    assert summary["failed_check_count"] == 0


def test_visual_table_audit_rows_have_traceable_sources_and_no_retention():
    payload = audit.build_payload(Path("."))

    assert all(row["source_traceability_status"] == "pass" for row in payload["audit_rows"])
    assert all(row["claim_boundary_status"] == "pass" for row in payload["audit_rows"])
    assert all(row["scientific_utility_status"] == "pass" for row in payload["audit_rows"])
    assert all(row["rendered_artifact_status"] == "not_rendered" for row in payload["audit_rows"])
    assert all(
        row["layout_overlap_check_status"] == "deferred_until_rendered_artifact"
        for row in payload["audit_rows"]
    )
    assert all(row["iteration_required"] is True for row in payload["audit_rows"])
    assert all(row["final_retention_authorized"] is False for row in payload["audit_rows"])
    assert all(
        row["retained_visual_or_table_decision"] == "not_started"
        for row in payload["audit_rows"]
    )
    assert {
        row["pre_retention_auditor_decision"] for row in payload["audit_rows"]
    } == {
        "candidate_keep_pending_render_audit",
        "move_to_kg_or_site_pending_release_gates",
        "move_to_supplement_pending_render_audit",
        "revise_claim_boundary_before_main_article_use",
    }


def test_kg_navigation_usability_sidecar_keeps_release_blocked():
    payload = audit.build_payload(Path("."))
    kg = payload["kg_navigation_usability_audit"]["summary"]
    graph = load_json(KG_QUALITY)["graph"]

    assert kg["overall_status"] == "kg_navigation_internal_ready_release_blocked"
    assert kg["node_count"] == graph["node_count"]
    assert kg["edge_count"] == graph["edge_count"]
    assert kg["isolated_node_count"] == 0
    assert kg["publication_node_count"] == graph["node_count"]
    assert kg["publication_edge_count"] == graph["edge_count"]
    assert kg["publication_isolated_node_count"] == 0
    assert kg["publication_metric_match"] is True
    assert kg["edge_selector_provenance_coverage"] == 1.0
    assert kg["kg_navigation_candidate_row_present"] is True
    assert kg["kg_citable_component_authorized"] is False
    assert kg["publication_site_deployment_authorized"] is False
    assert kg["final_triptych_release_authorized"] is False


def test_checked_in_kg_navigation_usability_matches_current_graph():
    graph = load_json(KG_QUALITY)["graph"]
    kg = load_json(KG_NAVIGATION)["summary"]

    assert kg["node_count"] == graph["node_count"]
    assert kg["edge_count"] == graph["edge_count"]
    assert kg["isolated_node_count"] == graph["isolated_node_count"]
    assert kg["publication_node_count"] == graph["node_count"]
    assert kg["publication_edge_count"] == graph["edge_count"]
    assert kg["publication_isolated_node_count"] == graph["isolated_node_count"]
    assert kg["publication_metric_match"] is True
