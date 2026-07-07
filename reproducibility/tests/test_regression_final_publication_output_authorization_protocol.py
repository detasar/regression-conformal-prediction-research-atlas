import json
from pathlib import Path

from experiments.regression.scripts import (
    build_final_publication_output_authorization_protocol as protocol,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = (
    ROOT
    / "experiments/regression/manuscript/"
    / "final_publication_output_authorization_protocol.json"
)


def load_checked_in_payload():
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def copy_sources(tmp_path: Path) -> None:
    for source in protocol.SOURCE_PATHS.values():
        source_path = ROOT / source
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")


def test_checked_in_final_output_authorization_protocol_is_neutral_and_closed():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "final_publication_output_authorization_protocol_ready_no_authorizations"
    )
    assert summary["final_output_authorization_protocol_status"] == (
        "protocol_ready_all_final_outputs_blocked"
    )
    assert summary["authorization_row_count"] == 10
    assert summary["blocked_authorization_row_count"] == 10
    assert summary["missing_policy_row_count"] == 0
    assert summary["ready_to_authorize_output_count"] == 0
    assert summary["active_final_blocker_count"] == 10
    assert summary["private_final_prose_authoring_authorized"] is True
    assert summary["private_main_article_authoring_authorized"] is True
    assert summary["private_supplement_authoring_authorized"] is True
    assert summary["private_research_document_authoring_authorized"] is True
    assert summary["private_final_prose_authoring_boundary"] == (
        "private_review_only_public_release_citation_and_method_recommendation_closed"
    )
    assert summary["private_sterile_publication_package_ready"] is True
    assert summary["private_publication_repository_remote_ready"] is True
    assert summary["private_repository_visibility"] == "PRIVATE"
    assert summary["private_repository_url"].startswith(
        "https://github.com/detasar/"
    )
    assert summary["public_repository_release_authorized"] is False
    assert summary["github_pages_publication_authorized"] is False
    assert summary["kg_public_web_artifact_authorized"] is False
    assert summary["goal_can_mark_complete"] is False
    assert summary["scientific_test_not_method_promotion"] is True
    assert summary["analysis_only_no_champion_method"] is True
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert (
        summary["result_reporting_policy"]
        == "analysis_only_report_observed_behavior_no_method_advocacy"
    )
    assert summary["paper_blocked_gate_count"] == 6
    assert summary["positive_claim_ready_gate_count"] == 0
    assert summary["release_authorized_count"] == 0
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["latex_html_authoring_authorized"] is False
    assert summary["publication_site_deployment_authorized"] is False
    assert summary["kg_citable_component_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["sterile_repository_publication_authorized"] is False
    assert summary["sterile_release_package_publication_authorized"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["authorization_violation_count"] == 0
    assert summary["source_artifact_count"] == 14
    assert summary["missing_source_artifact_count"] == 0
    assert summary["failed_check_count"] == 0


def test_authorization_rows_are_source_traceable_and_block_final_outputs():
    payload = load_checked_in_payload()
    rows = payload["authorization_rows"]

    assert len(rows) == 10
    for row in rows:
        assert row["authorization_status"] == "blocked_no_final_authorization"
        assert row["source_traceability_status"] == "pass"
        assert row["source_artifacts"]
        assert row["required_before_authorization"]
        assert row["allowed_current_action"]
        assert row["blocked_current_action"]
    manuscript_row = next(
        row for row in rows if row["blocker_id"] == "final_manuscript_prose_not_authorized"
    )
    assert "write and revise private Research Document" in manuscript_row[
        "allowed_current_action"
    ]
    assert manuscript_row["blocked_current_action"] == (
        "treat private review prose as public final manuscript prose or "
        "submission-ready final text"
    )
    repository_row = next(
        row
        for row in rows
        if row["blocker_id"] == "sterile_repository_creation_not_authorized"
    )
    assert (
        repository_row["output_family"]
        == "public_sterile_publication_repository_release"
    )
    assert "synchronized private repository" in repository_row[
        "allowed_current_action"
    ]
    assert (
        repository_row["blocked_current_action"]
        == "make the sterile repository public or cite it as the final public repository"
    )
    release_package_row = next(
        row for row in rows if row["blocker_id"] == "sterile_release_packaging_pending"
    )
    assert release_package_row["output_family"] == "public_release_packaging"
    assert "regenerate and audit the private review package" in release_package_row[
        "allowed_current_action"
    ]
    assert "approved final public release bundle" in release_package_row[
        "blocked_current_action"
    ]


def test_protocol_blocks_if_method_recommendation_is_opened(tmp_path):
    copy_sources(tmp_path)

    progress_path = tmp_path / protocol.PROGRESS_RECONCILIATION
    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    payload["summary"]["method_recommendation_authorized"] = True
    progress_path.write_text(json.dumps(payload), encoding="utf-8")

    result = protocol.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "final_publication_output_authorization_protocol_blocked"
    )
    assert result["summary"]["authorization_violation_count"] == 1
    assert checks["final_authorizations_remain_closed"]["status"] == "fail"


def test_protocol_blocks_if_champion_method_policy_is_missing(tmp_path):
    copy_sources(tmp_path)

    lock_path = tmp_path / protocol.SCIENTIFIC_NEUTRALITY_LOCK
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    payload["summary"]["analysis_only_no_champion_method"] = False
    payload["summary"]["method_champion_authorized"] = True
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    result = protocol.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "final_publication_output_authorization_protocol_blocked"
    )
    assert result["summary"]["analysis_only_no_champion_method"] is False
    assert result["summary"]["authorization_violation_count"] == 1
    assert checks["final_authorizations_remain_closed"]["status"] == "fail"
    assert checks["neutral_scientific_policy_locked"]["status"] == "fail"


def test_protocol_blocks_if_active_blocker_mapping_is_incomplete(tmp_path):
    copy_sources(tmp_path)

    progress_path = tmp_path / protocol.PROGRESS_RECONCILIATION
    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    payload["active_final_blocker_rows"] = payload["active_final_blocker_rows"][:-1]
    payload["summary"]["active_final_blocker_count"] = 9
    progress_path.write_text(json.dumps(payload), encoding="utf-8")

    result = protocol.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "final_publication_output_authorization_protocol_blocked"
    )
    assert result["summary"]["authorization_row_count"] == 9
    assert checks["active_final_blockers_fully_mapped"]["status"] == "fail"


def test_protocol_blocks_if_private_remote_is_public(tmp_path):
    copy_sources(tmp_path)

    remote_path = tmp_path / protocol.PRIVATE_REPOSITORY_REMOTE_AUDIT
    payload = json.loads(remote_path.read_text(encoding="utf-8"))
    payload["summary"]["remote_visibility"] = "PUBLIC"
    remote_path.write_text(json.dumps(payload), encoding="utf-8")

    result = protocol.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "final_publication_output_authorization_protocol_blocked"
    )
    assert result["summary"]["private_publication_repository_remote_ready"] is False
    assert (
        checks["private_package_and_remote_ready_but_public_release_closed"][
            "status"
        ]
        == "fail"
    )
