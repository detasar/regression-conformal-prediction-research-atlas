import json
from pathlib import Path

from experiments.regression.scripts import (
    build_final_publication_visual_auditor_readiness as auditor,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    ROOT
    / "experiments/regression/manuscript/"
    / "final_publication_visual_auditor_readiness.json"
)


def load_checked_in_payload():
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def copy_file_if_present(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def copy_sources(tmp_path: Path, *, include_rendered_artifacts: bool = True) -> None:
    for source in auditor.SOURCE_PATHS.values():
        copy_file_if_present(ROOT / source, tmp_path / source)

    render_payload = json.loads((ROOT / auditor.VISUAL_RENDER).read_text())
    retention_payload = json.loads((ROOT / auditor.RETENTION_READINESS).read_text())
    source_artifacts = set()
    rendered_artifacts = set()
    for row in render_payload.get("render_candidate_rows") or []:
        source_artifacts.update(row.get("source_artifacts") or [])
        rendered_artifacts.update(row.get("rendered_artifact_paths") or [])
        if row.get("primary_rendered_artifact_path"):
            rendered_artifacts.add(row["primary_rendered_artifact_path"])
    for row in retention_payload.get("recommendation_rows") or []:
        source_artifacts.update(row.get("source_artifacts") or [])

    for source in source_artifacts:
        copy_file_if_present(ROOT / source, tmp_path / source)
    if include_rendered_artifacts:
        for source in rendered_artifacts:
            copy_file_if_present(ROOT / source, tmp_path / source)


def test_checked_in_final_publication_visual_auditor_readiness_is_neutral():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "final_publication_visual_auditor_feedback_loop_ready_no_retention"
    )
    assert summary["final_publication_visual_auditor_status"] == (
        "feedback_loop_ready_no_final_retention"
    )
    assert summary["feedback_loop_ready"] is True
    assert summary["feedback_row_count"] == 10
    assert summary["feedback_ready_row_count"] == 10
    assert summary["feedback_blocked_row_count"] == 0
    assert summary["feedback_item_count"] >= 30
    assert summary["missing_rendered_artifact_count"] == 0
    assert summary["authorization_violation_count"] == 0
    assert summary["final_retained_artifact_count"] == 0
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["failed_check_count"] == 0


def test_feedback_rows_keep_source_traceability_and_final_retention_closed():
    payload = load_checked_in_payload()
    rows = payload["visual_auditor_feedback_rows"]

    assert len(rows) == 10
    for row in rows:
        assert row["source_artifacts"]
        assert row["feedback_items"]
        assert row["visual_auditor_feedback_status"] == (
            "feedback_ready_no_final_retention"
        )
        assert row["source_traceability_status"] == "pass"
        assert row["svg_static_text_overlap_detected"] is False
        assert row["final_retention_authorized"] is False
        assert row["final_visual_table_retention_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False


def test_visual_auditor_blocks_if_final_retention_is_opened(tmp_path):
    copy_sources(tmp_path)

    retention_path = tmp_path / auditor.RETENTION_READINESS
    payload = json.loads(retention_path.read_text(encoding="utf-8"))
    payload["summary"]["final_visual_table_retention_authorized"] = True
    retention_path.write_text(json.dumps(payload), encoding="utf-8")

    result = auditor.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "final_publication_visual_auditor_feedback_loop_blocked"
    )
    assert result["summary"]["authorization_violation_count"] == 1
    assert checks["final_outputs_and_release_remain_blocked"]["status"] == "fail"


def test_visual_auditor_blocks_if_rendered_artifacts_are_missing(tmp_path):
    copy_sources(tmp_path, include_rendered_artifacts=False)

    result = auditor.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "final_publication_visual_auditor_feedback_loop_blocked"
    )
    assert result["summary"]["missing_rendered_artifact_count"] > 0
    assert checks["layout_caption_overlap_traceability_clean"]["status"] == "fail"
