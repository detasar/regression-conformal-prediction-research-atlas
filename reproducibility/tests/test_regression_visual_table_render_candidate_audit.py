import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_visual_table_render_candidate_audit_is_draft_only():
    payload = json.loads(
        (
            ROOT
            / "experiments/regression/manuscript/"
            / "visual_table_render_candidate_audit.json"
        ).read_text()
    )
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "draft_visual_table_render_audit_completed_no_final_retention"
    )
    assert (
        summary["phase_state"]
        == "draft_render_candidates_complete_final_retention_and_release_blocked"
    )
    assert summary["pre_retention_input_row_count"] == 10
    assert summary["candidate_row_count"] == 10
    assert summary["rendered_draft_artifact_count"] == 10
    assert summary["primary_rendered_artifact_count"] == 10
    assert summary["layout_audit_row_count"] == 10
    assert summary["layout_pass_count"] == 10
    assert summary["layout_revise_count"] == 0
    assert summary["caption_pass_count"] == 10
    assert summary["source_traceability_pass_count"] == 10
    assert summary["svg_static_text_overlap_detected_count"] == 0
    assert summary["final_retained_artifact_count"] == 0
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["final_triptych_release_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["failed_check_count"] == 0


def test_render_candidate_rows_have_traceable_primary_artifacts():
    payload = json.loads(
        (
            ROOT
            / "experiments/regression/manuscript/"
            / "visual_table_render_candidate_audit.json"
        ).read_text()
    )

    rows = payload["render_candidate_rows"]
    assert len(rows) == 10
    assert any(row["render_kind"] == "svg_bar_chart_plus_markdown_table" for row in rows)
    for row in rows:
        primary = ROOT / row["primary_rendered_artifact_path"]
        assert primary.exists(), row["primary_rendered_artifact_path"]
        assert row["layout_quality_status"] == "pass"
        assert row["caption_quality_status"] == "pass"
        assert row["source_traceability_status"] == "pass"
        assert row["final_retention_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False
        assert row["source_artifacts"]


def test_layout_quality_sidecar_matches_render_candidate_audit():
    report = json.loads(
        (
            ROOT
            / "experiments/regression/manuscript/"
            / "visual_table_render_candidate_audit.json"
        ).read_text()
    )
    layout = json.loads(
        (
            ROOT
            / "experiments/regression/manuscript/visual_table_layout_quality_audit.json"
        ).read_text()
    )

    assert layout["summary"]["layout_audit_row_count"] == report["summary"][
        "layout_audit_row_count"
    ]
    assert layout["summary"]["layout_pass_count"] == report["summary"][
        "layout_pass_count"
    ]
    assert layout["summary"]["layout_revise_count"] == 0
    assert layout["summary"]["final_retention_authorized"] is False
