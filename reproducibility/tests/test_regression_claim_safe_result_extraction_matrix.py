import json
from pathlib import Path

from experiments.regression.scripts import (
    build_claim_safe_result_extraction_matrix as matrix,
)


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = (
    ROOT / "experiments/regression/manuscript/claim_safe_result_extraction_matrix.json"
)


def load_checked_in_payload():
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def rows_by_id(payload):
    return {row["surface_id"]: row for row in payload["surface_rows"]}


def copy_matrix_sources(tmp_path):
    for source in matrix.SOURCE_PATHS.values():
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / source).read_text(encoding="utf-8"), encoding="utf-8")


def test_checked_in_claim_safe_matrix_is_pre_prose_only():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "claim_safe_result_extraction_matrix_ready_no_final_claims"
    )
    assert summary["phase_state"] == (
        "neutral_pre_prose_result_extraction_active_final_outputs_blocked"
    )
    assert summary["surface_row_count"] == 8
    assert summary["source_traceable_row_count"] == 8
    assert summary["missing_source_artifact_count"] == 0
    assert summary["linked_neutral_result_issue_count"] == 0
    assert summary["safe_pre_prose_extraction_candidate_count"] == 7
    assert summary["blocked_positive_surface_count"] == 1
    assert summary["main_results_surface_status"] == "blocked_positive_claim_surface"
    assert summary["negative_results_surface_status"] == "candidate_negative_result_surface"
    assert summary["negative_result_reporting_ready"] is True
    assert summary["main_result_positive_claim_blocked"] is True
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["final_visual_table_retention_authorized"] is False
    assert summary["release_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["scientific_no_method_promotion_guard_active"] is True
    assert summary["failed_check_count"] == 0


def test_claim_safe_matrix_rows_keep_main_blocked_and_negative_scoped():
    payload = load_checked_in_payload()
    rows = rows_by_id(payload)

    main = rows["main_results_table"]
    assert main["safe_pre_prose_extraction_candidate"] is False
    assert main["positive_claim_surface_blocked"] is True
    assert main["pre_prose_extraction_status"] == "blocked_positive_claim_surface"
    assert main["method_recommendation_authorized"] is False
    assert main["positive_claim_promotion_authorized"] is False

    negative = rows["negative_results_table"]
    assert negative["safe_pre_prose_extraction_candidate"] is True
    assert negative["positive_claim_surface_blocked"] is False
    assert negative["claim_scope"] == (
        "venn_abers_negative_failure_mode_no_validated_claim"
    )
    assert negative["method_recommendation_authorized"] is False
    assert negative["positive_claim_promotion_authorized"] is False

    for row in payload["surface_rows"]:
        assert row["source_traceability_status"] == "pass"
        assert row["missing_source_artifacts"] == []
        assert row["linked_neutral_result_count"] >= 1
        assert row["final_manuscript_prose_permission"] is False
        assert row["final_visual_table_retention_authorized"] is False
        assert row["release_authorized"] is False
        assert row["method_recommendation_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False
        for source in row["source_artifacts"]:
            assert (ROOT / source).exists(), source


def test_claim_safe_matrix_blocks_if_main_result_gate_is_unblocked_without_policy(
    tmp_path,
):
    copy_matrix_sources(tmp_path)

    readiness_path = tmp_path / matrix.PAPER_READINESS
    readiness_payload = json.loads(readiness_path.read_text(encoding="utf-8"))
    readiness_payload["summary"]["overall_status"] = "paper_readiness_ready"
    readiness_payload["summary"]["main_surface_blocked_count"] = 0
    readiness_payload["summary"]["blocked_gate_count"] = 0
    readiness_path.write_text(json.dumps(readiness_payload), encoding="utf-8")

    closure_path = tmp_path / matrix.PAPER_GATE_CLOSURE
    closure_payload = json.loads(closure_path.read_text(encoding="utf-8"))
    closure_payload["summary"]["positive_claim_ready_gate_count"] = 1
    closure_path.write_text(json.dumps(closure_payload), encoding="utf-8")

    payload = matrix.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "claim_safe_result_extraction_matrix_blocked"
    )
    assert checks["main_results_surface_remains_blocked"]["status"] == "fail"
    assert checks["no_final_authorizations_or_method_promotion"]["status"] == "fail"


def test_claim_safe_matrix_blocks_if_release_or_method_promotion_is_authorized(
    tmp_path,
):
    copy_matrix_sources(tmp_path)

    release_path = tmp_path / matrix.RELEASE_GAP
    release_payload = json.loads(release_path.read_text(encoding="utf-8"))
    release_payload["summary"]["release_authorized_count"] = 1
    release_payload["summary"]["method_recommendation_authorized"] = True
    release_payload["summary"]["positive_claim_promotion_authorized"] = True
    release_payload["summary"]["working_repository_final_citable"] = True
    release_path.write_text(json.dumps(release_payload), encoding="utf-8")

    payload = matrix.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "claim_safe_result_extraction_matrix_blocked"
    )
    assert checks["release_and_repository_outputs_remain_blocked"]["status"] == "fail"
