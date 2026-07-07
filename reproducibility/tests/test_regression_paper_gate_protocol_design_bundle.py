from pathlib import Path

from experiments.regression.scripts import (
    build_paper_gate_protocol_design_bundle as bundle,
)


def test_checked_in_protocol_design_bundle_completes_initial_actions():
    payload = bundle.build_payload(Path("."))
    rows = {row["action_id"]: row for row in payload["protocol_design_rows"]}

    assert (
        payload["summary"]["overall_status"]
        == "paper_gate_protocol_design_bundle_ready_no_claim_promotions"
    )
    assert payload["summary"]["protocol_design_count"] == 4
    assert payload["summary"]["completed_protocol_design_action_count"] == 4
    assert payload["summary"]["claim_promoted_action_count"] == 0
    assert payload["summary"]["downstream_action_count"] == 5
    assert set(payload["summary"]["completed_action_ids"]) == set(rows)
    assert all(
        row["claim_effect"] == "protocol_only_no_positive_claim_promotion"
        for row in rows.values()
    )
    assert (
        rows[
            "venn_abers_regression_validation_gate.design_validated_regression_venn_abers_method"
        ]["status"]
        == "protocol_design_complete"
    )
    assert (
        "venn_abers_regression_validation_gate.validate_ivapd_interval_cp_contract"
        in payload["summary"]["downstream_action_ids"]
    )
