import json
from pathlib import Path

from experiments.regression.scripts import (
    build_manuscript_section_evidence_packet as packet,
)


ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = (
    ROOT / "experiments/regression/manuscript/manuscript_section_evidence_packet.json"
)


def load_checked_in_payload():
    return json.loads(PACKET_PATH.read_text(encoding="utf-8"))


def rows_by_id(payload):
    return {row["packet_id"]: row for row in payload["section_packet_rows"]}


def copy_packet_sources(tmp_path):
    for source in packet.SOURCE_PATHS.values():
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / source).read_text(encoding="utf-8"), encoding="utf-8")


def test_checked_in_section_evidence_packet_is_pre_prose_only():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "manuscript_section_evidence_packet_ready_no_final_prose"
    )
    assert summary["phase_state"] == (
        "neutral_pre_prose_section_evidence_packet_active_final_outputs_blocked"
    )
    assert summary["section_packet_row_count"] == 8
    assert summary["source_traceable_row_count"] == 8
    assert summary["missing_source_artifact_count"] == 0
    assert summary["claim_safe_surface_link_issue_count"] == 0
    assert summary["linked_neutral_result_issue_count"] == 0
    assert summary["paragraph_blueprint_complete_count"] == 8
    assert summary["reader_concept_link_count"] >= 8
    assert "conformalized_quantile_regression_cqr" in summary["unique_reader_concepts"]
    assert "venn_abers_predictive_distributions" in summary["unique_reader_concepts"]
    assert summary["safe_pre_prose_evidence_packet_count"] == 7
    assert summary["blocked_positive_packet_count"] == 1
    assert summary["main_results_packet_status"] == "blocked_positive_claim_packet"
    assert summary["negative_packet_status"] == "pre_prose_negative_evidence_ready"
    assert summary["main_results_packet_blocked"] is True
    assert summary["negative_packet_ready"] is True
    assert summary["claim_safe_matrix_clean"] is True
    assert summary["neutral_result_ledger_clean"] is True
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


def test_section_evidence_rows_keep_main_blocked_and_negative_scoped():
    payload = load_checked_in_payload()
    rows = rows_by_id(payload)

    main = rows["paper_main_results_blocked_evidence"]
    assert main["safe_pre_prose_evidence_packet"] is False
    assert main["positive_claim_packet_blocked"] is True
    assert main["packet_status"] == "blocked_positive_claim_packet"
    assert main["claim_safe_surface_id"] == "main_results_table"
    assert main["claim_safe_surface_status"] == "blocked_positive_claim_surface"
    assert main["final_section_prose_authorized"] is False
    assert main["method_recommendation_authorized"] is False
    assert main["positive_claim_promotion_authorized"] is False

    negative = rows["supplement_venn_abers_negative_evidence"]
    assert negative["safe_pre_prose_evidence_packet"] is True
    assert negative["positive_claim_packet_blocked"] is False
    assert negative["packet_status"] == "pre_prose_negative_evidence_ready"
    assert negative["claim_safe_surface_id"] == "negative_results_table"
    assert negative["claim_safe_surface_status"] == "candidate_negative_result_surface"
    assert negative["neutral_result_ids"] == ["venn_abers_regression_negative_evidence"]
    assert negative["final_section_prose_authorized"] is False
    assert negative["method_recommendation_authorized"] is False
    assert negative["positive_claim_promotion_authorized"] is False

    for row in payload["section_packet_rows"]:
        assert row["source_traceability_status"] == "pass"
        assert row["missing_source_artifacts"] == []
        assert row["claim_safe_surface_linked"] is True
        assert row["linked_neutral_result_count"] >= 1
        assert row["reader_concept_ids"]
        assert row["reader_concept_count"] == len(row["reader_concept_ids"])
        assert row["paragraph_blueprint"]
        assert row["paragraph_blueprint_step_count"] == len(
            row["paragraph_blueprint"]
        )
        assert "reader_primer" in row["source_keys"]
        assert "reader_primer_alignment" in row["source_keys"]
        assert row["final_section_prose_authorized"] is False
        assert row["final_manuscript_prose_permission"] is False
        assert row["final_visual_table_retention_authorized"] is False
        assert row["release_authorized"] is False
        assert row["method_recommendation_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False
        for source in row["source_artifacts"]:
            assert (ROOT / source).exists(), source


def test_section_evidence_packet_blocks_if_claim_safe_matrix_is_overpromoted(
    tmp_path,
):
    copy_packet_sources(tmp_path)

    claim_safe_path = tmp_path / packet.CLAIM_SAFE_MATRIX
    claim_safe_payload = json.loads(claim_safe_path.read_text(encoding="utf-8"))
    claim_safe_payload["summary"]["method_recommendation_authorized"] = True
    claim_safe_payload["summary"]["positive_claim_promotion_authorized"] = True
    claim_safe_payload["summary"]["safe_pre_prose_extraction_candidate_count"] = 8
    claim_safe_payload["summary"]["blocked_positive_surface_count"] = 0
    claim_safe_path.write_text(json.dumps(claim_safe_payload), encoding="utf-8")

    payload = packet.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "manuscript_section_evidence_packet_blocked"
    )
    assert checks["claim_safe_surface_links_clean"]["status"] == "fail"
    assert checks["no_final_section_or_method_authorizations"]["status"] == "fail"


def test_section_evidence_packet_blocks_if_release_or_final_prose_is_authorized(
    tmp_path,
):
    copy_packet_sources(tmp_path)

    release_path = tmp_path / packet.RELEASE_GAP
    release_payload = json.loads(release_path.read_text(encoding="utf-8"))
    release_payload["summary"]["release_authorized_count"] = 1
    release_payload["summary"]["final_manuscript_prose_permission"] = True
    release_payload["summary"]["working_repository_final_citable"] = True
    release_path.write_text(json.dumps(release_payload), encoding="utf-8")

    payload = packet.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "manuscript_section_evidence_packet_blocked"
    )
    assert checks["upstream_pre_prose_authorizations_remain_blocked"]["status"] == "fail"
    assert (
        checks["visual_release_and_repository_outputs_remain_blocked"]["status"]
        == "fail"
    )
