from pathlib import Path

from experiments.regression.scripts import build_publication_preparation_packets as prep


def test_checked_in_publication_preparation_packets_are_neutral_pre_prose():
    payload = prep.build_payload(Path("."))
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "publication_preparation_packets_ready_no_final_prose"
    )
    assert summary["publication_preparation_authorized"] is True
    assert summary["reviewer_packet_count"] == 5
    assert summary["required_reviewer_pass_count"] == 5
    assert summary["visual_table_candidate_family_count"] == 10
    assert summary["private_manuscript_drafting_authorized"] is True
    assert summary["manuscript_drafting_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["positive_claim_publication_ready"] is False
    assert summary["neutral_no_method_promotion_guard_active"] is True
    assert summary["failed_check_count"] == 0
    assert all(
        packet["final_manuscript_prose_permission"] is False
        for packet in payload["reviewer_packets"]
    )
    assert all(
        row["final_retain_decision"] == "not_started"
        for row in payload["visual_table_inventory_plan"]
    )
    assert all(
        row["source_artifact_count"] > 0
        for row in payload["visual_table_inventory_plan"]
    )


def test_publication_preparation_packets_keep_expected_claim_boundaries():
    payload = prep.build_payload(Path("."))

    boundaries = " ".join(payload["claim_boundaries"])
    assert "not manuscript prose" in boundaries
    assert (
        "not designed to promote CQR, CV+, Venn-Abers, or any other method"
        in boundaries
    )
    assert "no artifact is retained" in boundaries
    assert "sterile publication repository remains downstream" in boundaries
    assert "Venn-Abers" in boundaries
