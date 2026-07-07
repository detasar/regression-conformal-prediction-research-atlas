import json
from pathlib import Path

from experiments.regression.scripts import (
    build_article_supplement_kg_navigation_index as index,
)


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = (
    ROOT
    / "experiments/regression/manuscript/article_supplement_kg_navigation_index.json"
)


def load_checked_in_payload():
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def rows_by_id(payload):
    return {row["navigation_id"]: row for row in payload["navigation_rows"]}


def copy_index_sources(tmp_path):
    for source in index.SOURCE_PATHS.values():
        source_path = ROOT / source
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")


def test_checked_in_article_supplement_kg_navigation_index_is_neutral():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "article_supplement_kg_navigation_index_ready_no_release"
    )
    assert summary["phase_state"] == (
        "neutral_pre_release_navigation_index_active_final_outputs_blocked"
    )
    assert summary["navigation_row_count"] == 9
    assert summary["section_navigation_row_count"] == 8
    assert summary["kg_site_navigation_row_count"] == 1
    assert summary["source_traceable_row_count"] == 9
    assert summary["visual_table_candidate_index_row_count"] == 10
    assert summary["visual_table_source_traceability_pass_count"] == 10
    assert summary["visual_table_final_authorized_count"] == 0
    assert summary["release_target_linked_row_count"] == 9
    assert summary["release_authorized_target_count"] == 0
    assert summary["kg_node_reference_row_count"] == 9
    assert summary["kg_node_reference_issue_count"] == 0
    assert summary["missing_source_artifact_count"] == 0
    assert summary["main_results_positive_boundary_blocked"] is True
    assert summary["venn_abers_negative_boundary_preserved"] is True
    assert summary["scientific_no_method_promotion_guard_active"] is True
    assert summary["neutral_language_unguarded_hit_count"] == 0
    assert summary["final_navigation_release_authorized"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["failed_check_count"] == 0


def test_navigation_rows_keep_main_blocked_venn_negative_and_kg_site_unreleased():
    payload = load_checked_in_payload()
    rows = rows_by_id(payload)

    main = rows["paper_main_results_blocked_evidence"]
    assert main["boundary_status"] == "blocked_positive_boundary_preserved"
    assert main["main_results_positive_boundary_blocked"] is True
    assert main["method_recommendation_authorized"] is False
    assert main["positive_claim_promotion_authorized"] is False
    assert main["release_authorized_target_count"] == 0

    negative = rows["supplement_venn_abers_negative_evidence"]
    assert negative["boundary_status"] == "negative_failure_mode_boundary_preserved"
    assert negative["venn_abers_negative_boundary_preserved"] is True
    assert negative["neutral_result_ids"] == ["venn_abers_regression_negative_evidence"]
    assert negative["method_recommendation_authorized"] is False
    assert negative["positive_claim_promotion_authorized"] is False

    kg_site = rows["kg_site_navigation_candidate"]
    assert kg_site["boundary_status"] == "kg_site_navigation_release_blocked"
    assert kg_site["release_authorized"] is False
    assert kg_site["publication_site_deployment_authorized"] is False
    assert kg_site["kg_citable_component_authorized"] is False
    assert kg_site["sterile_repository_creation_authorized"] is False
    assert kg_site["source_traceability_status"] == "pass"

    for row in payload["navigation_rows"]:
        assert row["source_traceability_status"] == "pass"
        assert row["missing_release_target_ids"] == []
        assert row["missing_kg_reference_node_ids"] == []
        assert row["release_authorized"] is False
        assert row["method_recommendation_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False


def test_navigation_index_blocks_if_release_gap_authorizes_target(tmp_path):
    copy_index_sources(tmp_path)

    release_path = tmp_path / index.RELEASE_GAP
    release_payload = json.loads(release_path.read_text(encoding="utf-8"))
    for row in release_payload["deliverable_rows"]:
        if row["deliverable_id"] == "article_supplement_kg_navigation_index":
            row["release_authorized"] = True
            row["release_status"] = "release_authorized"
            break
    release_path.write_text(json.dumps(release_payload), encoding="utf-8")

    payload = index.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "article_supplement_kg_navigation_index_blocked"
    )
    assert checks["release_targets_remain_blocked"]["passed"] is False
    assert payload["summary"]["release_authorized_target_count"] == 1


def test_navigation_index_blocks_if_kg_reference_disappears(tmp_path):
    copy_index_sources(tmp_path)

    kg_path = tmp_path / index.KG_GRAPH
    kg_payload = json.loads(kg_path.read_text(encoding="utf-8"))
    kg_payload["nodes"] = [
        node
        for node in kg_payload["nodes"]
        if node.get("id") != "report:section_claim_boundary_audit"
    ]
    kg_path.write_text(json.dumps(kg_payload), encoding="utf-8")

    payload = index.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "article_supplement_kg_navigation_index_blocked"
    )
    assert checks["navigation_rows_are_source_traceable"]["passed"] is False
    assert payload["summary"]["kg_node_reference_issue_count"] >= 1
