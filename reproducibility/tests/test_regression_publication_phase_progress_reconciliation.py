import json
from pathlib import Path

from experiments.regression.scripts import (
    audit_publication_phase_progress_reconciliation as reconciliation,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    ROOT
    / "experiments/regression/manuscript/"
    / "publication_phase_progress_reconciliation_audit.json"
)


def load_checked_in_payload():
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def copy_reconciliation_sources(tmp_path):
    for source in reconciliation.SOURCE_PATHS.values():
        source_path = ROOT / source
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")


def test_checked_in_publication_phase_progress_reconciliation_is_neutral():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "publication_phase_progress_reconciliation_ready_no_final_outputs"
    )
    assert summary["phase_state"] == (
        "neutral_publication_progress_reconciled_final_outputs_blocked"
    )
    assert summary["pre_prose_completed_control_count"] == 8
    assert summary["pre_prose_control_count"] == 8
    assert summary["private_review_milestone_complete_count"] == 3
    assert summary["private_review_milestone_count"] == 3
    assert summary["resolved_prior_blocker_count"] == 2
    assert summary["active_final_blocker_count"] == 10
    assert summary["stale_goal_blocker_count"] == 0
    assert summary["reviewer_design_reconciled"] is True
    assert summary["pre_retention_visual_audit_completed"] is True
    assert summary["claim_boundary_navigation_ready"] is True
    assert summary["release_gap_ready"] is True
    assert summary["private_authoring_ready"] is True
    assert summary["private_latex_html_review_outputs_ready"] is True
    assert summary["private_sterile_publication_package_ready"] is True
    assert summary["private_publication_repository_remote_ready"] is True
    assert summary["private_publication_repository_visibility"] == "PRIVATE"
    assert summary["private_publication_repository_commit_match"] is True
    assert summary["neutral_guard_ready"] is True
    assert summary["kg_publication_ready"] is True
    assert (
        summary["final_publication_visual_auditor_status"]
        == "feedback_loop_ready_no_final_retention"
    )
    assert summary["final_publication_visual_auditor_feedback_ready"] is True
    assert summary["goal_can_mark_complete"] is False
    assert summary["paper_blocked_gate_count"] == 6
    assert summary["positive_claim_ready_gate_count"] == 0
    assert summary["main_results_positive_boundary_blocked"] is True
    assert summary["venn_abers_negative_boundary_preserved"] is True
    assert summary["validated_venn_abers_regression_claim_ready"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["failed_check_count"] == 0


def test_reconciliation_rows_separate_resolved_and_active_blockers():
    payload = load_checked_in_payload()
    controls = {row["control_id"]: row for row in payload["pre_prose_control_rows"]}
    private = {row["control_id"]: row for row in payload["private_review_milestone_rows"]}
    resolved = {row["blocker_id"]: row for row in payload["resolved_prior_blocker_rows"]}
    active = {row["blocker_id"]: row for row in payload["active_final_blocker_rows"]}

    assert controls["reviewer_design_and_reconciliation_ready"]["status"] == "complete"
    assert (
        controls["visual_table_pre_retention_and_render_audits_ready"]["status"]
        == "complete"
    )
    assert (
        controls["final_publication_visual_auditor_feedback_loop_ready"]["status"]
        == "complete"
    )
    assert private["private_authoring_decision_ready"]["status"] == "complete"
    assert private["private_latex_html_review_outputs_ready"]["status"] == "complete"
    assert private["private_sterile_package_and_remote_ready"]["status"] == "complete"
    assert resolved["reviewer_design_reconciliation_pending"]["status"] == "resolved"
    assert resolved["visual_table_audit_pending"]["status"] == "resolved"
    assert active["final_manuscript_prose_not_authorized"]["status"] == "active"
    assert active["sterile_repository_creation_not_authorized"]["status"] == "active"
    assert active["positive_claim_promotion_not_authorized"]["status"] == "active"


def test_reconciliation_blocks_if_goal_row_reintroduces_resolved_blocker(tmp_path):
    copy_reconciliation_sources(tmp_path)

    goal_path = tmp_path / reconciliation.GOAL_COMPLETION
    goal_payload = json.loads(goal_path.read_text(encoding="utf-8"))
    for row in goal_payload["requirement_rows"]:
        if row["requirement_id"] == "post_experiment_publication_program":
            row["blockers"].append("reviewer_design_reconciliation_pending")
            break
    goal_path.write_text(json.dumps(goal_payload), encoding="utf-8")

    payload = reconciliation.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "publication_phase_progress_reconciliation_blocked"
    )
    assert checks["resolved_prior_blockers_not_active_in_goal_row"]["status"] == "fail"
    assert payload["summary"]["stale_goal_blocker_count"] == 1


def test_reconciliation_blocks_if_final_release_or_method_promotion_appears(tmp_path):
    copy_reconciliation_sources(tmp_path)

    release_path = tmp_path / reconciliation.RELEASE_GAP
    release_payload = json.loads(release_path.read_text(encoding="utf-8"))
    release_payload["summary"]["method_recommendation_authorized"] = True
    release_payload["summary"]["release_authorized_count"] = 1
    release_path.write_text(json.dumps(release_payload), encoding="utf-8")

    payload = reconciliation.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "publication_phase_progress_reconciliation_blocked"
    )
    assert checks["final_outputs_remain_blocked"]["status"] == "fail"
