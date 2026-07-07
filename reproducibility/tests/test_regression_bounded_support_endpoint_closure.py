import json

from experiments.regression.scripts import audit_bounded_support_endpoint_closure as audit


ROOT = audit.Path(__file__).resolve().parents[1]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def row(
    *,
    bundle_id,
    dataset_id,
    endpoint_status,
    present,
    count,
    count_status,
    blockers=None,
):
    return {
        "bundle_id": bundle_id,
        "dataset_id": dataset_id,
        "target": "target",
        "target_domain_class": "nonnegative",
        "natural_lower": 0.0,
        "natural_upper": None,
        "natural_bound_status": "lower_bound_provenance_present",
        "endpoint_support_status": endpoint_status,
        "claim_status": "blocked_no_bounded_support_validity_claim",
        "can_support_bounded_support_validity": False,
        "interval_handling_policy": "report_raw_unclipped_with_excursion_audit",
        "posthandling_support_status": "validated_all_completed_rows",
        "blockers": blockers
        if blockers is not None
        else [
            "natural_domain_endpoint_excursions",
            "global_bounded_support_validity_claim_disabled",
        ],
        "bounded_support_posthandling_validation": {
            "status": "validated",
            "completed_ledger_rows": 3,
            "clip_policy": {
                "coverage": 0.9,
                "abstention_rate": 0.0,
            },
        },
        "endpoint_audit": {
            "report_id": f"report:{bundle_id}:endpoint_audit",
            "natural_domain_endpoint_excursion_present": present,
            "natural_domain_endpoint_excursion_count": count,
            "natural_domain_endpoint_excursion_rate": (
                None if count is None else count / 100.0
            ),
            "natural_domain_endpoint_excursion_count_status": count_status,
            "natural_lower_audit": {"count": count},
            "natural_upper_audit": {"count": 0},
            "observed_range_endpoint_excursion_count": 4,
        },
        "paths": {
            "endpoint_audit_json": f"experiments/regression/reports/{bundle_id}/endpoint_audit.json",
        },
    }


def write_minimal_sources(tmp_path):
    write_json(
        tmp_path / audit.BOUNDED_SUPPORT_PROTOCOL,
        {"summary": {"overall_status": "bounded_support_protocol_defined_no_validity_claim"}},
    )
    write_json(
        tmp_path / audit.TARGET_DOMAIN_PROVENANCE,
        {"summary": {"overall_status": "target_domain_provenance_ready"}},
    )
    write_json(
        tmp_path / audit.BOUNDED_SUPPORT_POSTHANDLING_VALIDATION,
        {"summary": {"overall_status": "bounded_support_posthandling_validation_completed"}},
    )
    write_json(
        tmp_path / audit.PAPER_READINESS_MAP,
        {
            "blocked_gates": [
                {"gate_id": "endpoint_bounded_support_gate", "status": "blocked"}
            ]
        },
    )
    write_json(
        tmp_path / audit.BOUNDED_SUPPORT_DATASET_AUDIT,
        {
            "rows": [
                row(
                    bundle_id="bundle_exact_blocked",
                    dataset_id="dataset_a",
                    endpoint_status="blocked_natural_domain_endpoint_excursions",
                    present=True,
                    count=2,
                    count_status="exact",
                ),
                row(
                    bundle_id="bundle_unknown",
                    dataset_id="dataset_b",
                    endpoint_status=(
                        "blocked_natural_domain_endpoint_excursion_count_unknown"
                    ),
                    present=True,
                    count=None,
                    count_status="not_computed_extreme_crossing",
                ),
                row(
                    bundle_id="bundle_clean",
                    dataset_id="dataset_c",
                    endpoint_status="clean_no_natural_domain_endpoint_excursions",
                    present=False,
                    count=0,
                    count_status="exact",
                    blockers=["global_bounded_support_validity_claim_disabled"],
                ),
            ]
        },
    )


def test_build_payload_separates_exact_excursions_from_backfill(tmp_path):
    write_minimal_sources(tmp_path)

    payload = audit.build_payload(tmp_path)

    summary = payload["summary"]
    assert (
        summary["overall_status"]
        == "endpoint_policy_triage_open_count_backfill_required_no_validity_claim"
    )
    assert summary["bundle_count"] == 3
    assert summary["dataset_count"] == 3
    assert summary["closed_policy_bundle_count"] == 2
    assert summary["open_endpoint_count_backfill_bundle_count"] == 1
    assert summary["bounded_support_validity_claim_ready_bundle_count"] == 0
    assert (
        summary["action_id"]
        == "endpoint_bounded_support_gate.audit_natural_domain_endpoint_excursions"
    )
    assert summary["action_status"] == "endpoint_count_backfill_required"
    assert summary["current_manuscript_bounded_support_validity_claim_ready"] is False
    assert summary["endpoint_closure_status_counts"] == {
        "closed_endpoint_clean_or_not_applicable_global_no_claim": 1,
        "closed_raw_endpoint_excursion_no_validity_claim": 1,
        "open_endpoint_excursion_count_backfill_required": 1,
    }
    assert summary["endpoint_closure_action_counts"] == {
        "backfill_unknown_natural_endpoint_excursion_count": 1,
        "maintain_no_bounded_support_validity_claim": 2,
    }
    assert payload["failed_checks"] == []

    rows = {row["bundle_id"]: row for row in payload["rows"]}
    assert (
        rows["bundle_exact_blocked"]["endpoint_closure_status"]
        == "closed_raw_endpoint_excursion_no_validity_claim"
    )
    assert (
        rows["bundle_unknown"]["next_action_id"]
        == "backfill_unknown_natural_endpoint_excursion_count"
    )
    assert (
        rows["bundle_clean"]["endpoint_closure_status"]
        == "closed_endpoint_clean_or_not_applicable_global_no_claim"
    )

    markdown = audit.render_markdown(payload)
    assert "Bounded Support Endpoint Closure Audit" in markdown
    assert "backfill_unknown_natural_endpoint_excursion_count" in markdown


def test_checked_in_endpoint_closure_audit_captures_current_backfill_boundary():
    payload = json.loads(
        (
            ROOT
            / "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "bounded_support_endpoint_closure_audit.json"
        ).read_text()
    )

    summary = payload["summary"]
    assert (
        summary["overall_status"]
        == "endpoint_policy_triage_closed_no_bounded_support_validity_claim"
    )
    assert summary["bundle_count"] == 15
    assert summary["dataset_count"] == 6
    assert summary["closed_policy_bundle_count"] == 15
    assert summary["open_endpoint_count_backfill_bundle_count"] == 0
    assert summary["posthandling_validated_bundle_count"] == 15
    assert summary["global_no_claim_bundle_count"] == 15
    assert summary["bounded_support_validity_claim_ready_bundle_count"] == 0
    assert (
        summary["action_id"]
        == "endpoint_bounded_support_gate.audit_natural_domain_endpoint_excursions"
    )
    assert summary["action_status"] == "empirical_execution_complete"
    assert summary["current_manuscript_bounded_support_validity_claim_ready"] is False
    assert summary["endpoint_closure_action_counts"] == {
        "maintain_no_bounded_support_validity_claim": 15,
    }

    rows = {row["bundle_id"]: row for row in payload["rows"]}
    uci_row_signature = rows[
        "duplicate_cluster_sensitivity_uci_wine_quality_duplicate_sensitivity_row_signature"
    ]
    assert (
        uci_row_signature["endpoint_closure_status"]
        == "closed_raw_endpoint_excursion_no_validity_claim"
    )
    assert (
        uci_row_signature["next_action_id"]
        == "maintain_no_bounded_support_validity_claim"
    )
    assert (
        uci_row_signature["natural_domain_endpoint_excursion_count_status"]
        == "exact"
    )
    assert uci_row_signature["natural_domain_endpoint_excursion_count"] == 2

    dataset_rows = {row["dataset_id"]: row for row in payload["dataset_rows"]}
    assert (
        dataset_rows["uci_wine_quality"]["endpoint_closure_status"]
        == "triaged_raw_endpoint_excursions_no_validity_claim"
    )
    assert (
        dataset_rows["openml_analcatdata_chlamydia"]["endpoint_closure_status"]
        == "triaged_endpoint_clean_or_not_applicable_global_no_claim"
    )
