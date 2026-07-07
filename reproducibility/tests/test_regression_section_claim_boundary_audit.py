import json
from pathlib import Path

from experiments.regression.scripts import (
    audit_section_claim_boundary_alignment as audit,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "experiments/regression/manuscript/section_claim_boundary_audit.json"


def load_checked_in_payload():
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def rows_by_id(payload):
    return {row["packet_id"]: row for row in payload["boundary_rows"]}


def copy_audit_sources(tmp_path):
    for source in audit.SOURCE_PATHS.values():
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / source).read_text(encoding="utf-8"), encoding="utf-8")


def test_checked_in_section_claim_boundary_audit_is_no_final_claims():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == "section_claim_boundary_audit_pass_no_final_claims"
    assert summary["phase_state"] == (
        "neutral_pre_prose_section_claim_boundary_alignment_active_final_outputs_blocked"
    )
    assert summary["boundary_row_count"] == 8
    assert summary["boundary_complete_row_count"] == 8
    assert summary["allowed_use_complete_row_count"] == 8
    assert summary["blocked_use_complete_row_count"] == 8
    assert summary["claim_safe_surface_consistent_row_count"] == 8
    assert summary["neutral_result_linked_row_count"] == 8
    assert summary["release_target_linked_row_count"] == 8
    assert summary["release_authorized_target_count"] == 0
    assert summary["neutral_ledger_prose_boundary_gap_unique_result_count"] == 5
    assert summary["section_boundary_backfill_row_count"] == 8
    assert summary["main_results_positive_boundary_blocked"] is True
    assert summary["venn_abers_negative_boundary_preserved"] is True
    assert summary["section_packet_clean"] is True
    assert summary["upstream_boundaries_clean"] is True
    assert summary["post_program_controlled"] is True
    assert summary["final_section_prose_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["release_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["scientific_no_method_promotion_guard_active"] is True
    assert summary["neutral_language_unguarded_hit_count"] == 0
    assert summary["failed_check_count"] == 0


def test_section_claim_boundary_rows_keep_main_blocked_and_venn_negative():
    payload = load_checked_in_payload()
    rows = rows_by_id(payload)

    main = rows["paper_main_results_blocked_evidence"]
    assert main["boundary_status"] == "blocked_positive_boundary_preserved"
    assert main["scientific_reporting_role"] == "positive_main_result_claim_blocked"
    assert main["main_positive_boundary_blocked"] is True
    assert main["release_targets_blocked"] is True
    assert main["boundary_complete"] is True
    assert main["method_recommendation_authorized"] is False
    assert main["positive_claim_promotion_authorized"] is False

    negative = rows["supplement_venn_abers_negative_evidence"]
    assert negative["boundary_status"] == "negative_failure_mode_boundary_preserved"
    assert (
        negative["scientific_reporting_role"]
        == "venn_abers_negative_failure_mode_no_validation"
    )
    assert negative["venn_abers_negative_boundary_preserved"] is True
    assert negative["neutral_result_ids"] == ["venn_abers_regression_negative_evidence"]
    assert negative["release_targets_blocked"] is True
    assert negative["method_recommendation_authorized"] is False
    assert negative["positive_claim_promotion_authorized"] is False

    for row in payload["boundary_rows"]:
        assert row["boundary_complete"] is True
        assert row["section_allowed_use_present"] is True
        assert row["section_blocked_use_present"] is True
        assert row["section_claim_boundary_present"] is True
        assert row["claim_safe_surface_consistent"] is True
        assert row["missing_neutral_result_ids"] == []
        assert row["missing_release_target_ids"] == []
        assert row["release_target_authorized_count"] == 0
        assert row["section_boundary_backfills_ledger_gap"] is True
        assert row["authorization_count"] == 0


def test_section_claim_boundary_audit_blocks_if_section_boundary_is_removed(tmp_path):
    copy_audit_sources(tmp_path)

    packet_path = tmp_path / audit.SECTION_PACKET
    packet_payload = json.loads(packet_path.read_text(encoding="utf-8"))
    packet_payload["section_packet_rows"][0]["allowed_use"] = ""
    packet_payload["section_packet_rows"][0]["method_recommendation_authorized"] = True
    packet_path.write_text(json.dumps(packet_payload), encoding="utf-8")

    payload = audit.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == "section_claim_boundary_audit_blocked"
    assert checks["section_rows_have_complete_boundaries"]["status"] == "fail"


def test_section_claim_boundary_audit_blocks_if_release_target_is_authorized(tmp_path):
    copy_audit_sources(tmp_path)

    release_path = tmp_path / audit.RELEASE_GAP
    release_payload = json.loads(release_path.read_text(encoding="utf-8"))
    release_payload["summary"]["release_authorized_count"] = 1
    release_payload["deliverable_rows"][0]["release_authorized"] = True
    release_path.write_text(json.dumps(release_payload), encoding="utf-8")

    payload = audit.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == "section_claim_boundary_audit_blocked"
    assert checks["upstream_boundaries_clean"]["status"] == "fail"
    assert checks["release_targets_remain_blocked"]["status"] == "fail"
