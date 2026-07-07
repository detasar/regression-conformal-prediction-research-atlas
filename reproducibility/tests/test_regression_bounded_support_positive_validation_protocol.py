import json
from pathlib import Path

from experiments.regression.scripts import (
    run_bounded_support_positive_validation_protocol as protocol,
)


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def policy(coverage=0.9):
    return {
        "coverage": coverage,
        "mean_width": 2.0,
        "interval_score": 3.0,
        "interval_count": 100,
        "lower_below_natural_count": 0,
        "upper_above_natural_count": 0,
        "invalid_interval_count": 0,
        "interval_score_nonfinite_count": 0,
        "abstention_rate": 0.0,
        "abstained_interval_count": 0,
    }


def write_minimal_sources(root: Path):
    write_json(
        root / protocol.BOUNDED_SUPPORT_PROTOCOL,
        {
            "summary": {
                "overall_status": "bounded_support_protocol_defined_no_validity_claim",
                "failed_check_count": 0,
                "can_support_bounded_support_validity": False,
                "publication_can_support_bounded_support_validity": False,
                "endpoint_bounded_support_gate_status": "blocked",
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        root / protocol.BOUNDED_SUPPORT_DATASET_AUDIT,
        {
            "summary": {
                "overall_status": (
                    "dataset_bounded_support_audit_completed_no_validity_claim"
                ),
                "failed_check_count": 0,
                "bundle_count": 2,
                "can_support_bounded_support_validity": False,
                "bounded_support_ready_bundle_count": 0,
                "endpoint_bounded_support_gate_status": "blocked",
            },
            "rows": [
                {
                    "bundle_id": "blocked_bundle",
                    "dataset_id": "dataset_a",
                    "target": "y",
                    "target_transform": "identity",
                    "target_domain_class": "nonnegative",
                    "endpoint_support_status": (
                        "blocked_natural_domain_endpoint_excursions"
                    ),
                    "posthandling_support_status": "validated_all_completed_rows",
                    "claim_status": "blocked_no_bounded_support_validity_claim",
                    "blockers": [
                        "natural_domain_endpoint_excursions",
                        "global_bounded_support_validity_claim_disabled",
                    ],
                    "endpoint_audit": {
                        "natural_domain_endpoint_excursion_present": True,
                        "natural_domain_endpoint_excursion_count": 4,
                        "natural_domain_endpoint_excursion_rate": 0.04,
                    },
                    "paths": {
                        "endpoint_audit_json": "reports/blocked_bundle/endpoint_audit.json",
                        "manifest_path": "reports/blocked_bundle/publication_readiness_manifest.md",
                    },
                },
                {
                    "bundle_id": "clean_bundle",
                    "dataset_id": "dataset_b",
                    "target": "z",
                    "target_transform": "identity",
                    "target_domain_class": "bounded_ordinal",
                    "endpoint_support_status": (
                        "clean_no_natural_domain_endpoint_excursions"
                    ),
                    "posthandling_support_status": "validated_all_completed_rows",
                    "claim_status": "blocked_no_bounded_support_validity_claim",
                    "blockers": ["global_bounded_support_validity_claim_disabled"],
                    "endpoint_audit": {
                        "natural_domain_endpoint_excursion_present": False,
                        "natural_domain_endpoint_excursion_count": 0,
                        "natural_domain_endpoint_excursion_rate": 0.0,
                    },
                    "paths": {
                        "endpoint_audit_json": "reports/clean_bundle/endpoint_audit.json",
                        "manifest_path": "reports/clean_bundle/publication_readiness_manifest.md",
                    },
                },
            ],
        },
    )
    write_json(
        root / protocol.BOUNDED_SUPPORT_POSTHANDLING,
        {
            "summary": {
                "overall_status": "bounded_support_posthandling_validation_completed",
                "scope_complete": True,
                "validated_bundle_count": 2,
                "unvalidated_bundle_count": 0,
            },
            "rows": [
                {
                    "bundle_id": "blocked_bundle",
                    "status": "validated",
                    "policies": {
                        "raw_unclipped": policy(0.88),
                        "clip_to_natural_bounds": policy(0.88),
                        "abstain_if_raw_out_of_domain": policy(0.87),
                    },
                },
                {
                    "bundle_id": "clean_bundle",
                    "status": "validated",
                    "policies": {
                        "raw_unclipped": policy(0.91),
                        "clip_to_natural_bounds": policy(0.91),
                        "abstain_if_raw_out_of_domain": policy(0.91),
                    },
                },
            ],
        },
    )
    write_json(
        root / protocol.BOUNDED_SUPPORT_ENDPOINT_CLOSURE,
        {
            "summary": {
                "overall_status": (
                    "endpoint_policy_triage_closed_no_bounded_support_validity_claim"
                ),
                "failed_check_count": 0,
                "open_endpoint_count_backfill_bundle_count": 0,
                "current_manuscript_bounded_support_validity_claim_ready": False,
                "bounded_support_validity_claim_ready_bundle_count": 0,
                "paper_readiness_endpoint_gate_status": "blocked",
            }
        },
    )
    write_json(
        root / protocol.PAPER_READINESS,
        {
            "summary": {
                "overall_status": "paper_readiness_blocked_with_evidence_map",
                "blocked_gate_count": 6,
            }
        },
    )


def test_positive_validation_protocol_records_negative_result_without_claim(tmp_path):
    write_minimal_sources(tmp_path)

    payload = protocol.build_payload(tmp_path)

    summary = payload["summary"]
    assert (
        summary["overall_status"]
        == "bounded_support_positive_validation_protocol_completed_no_validity_claim"
    )
    assert summary["action_status"] == "empirical_validation_complete_no_bounded_support_claim"
    assert summary["selected_bundle_scope"] == "all_current_manuscript_bundles"
    assert summary["selected_bundle_count"] == 2
    assert summary["posthandling_validated_bundle_count"] == 2
    assert summary["policy_metrics_available_bundle_count"] == 2
    assert summary["interval_score_metrics_available_bundle_count"] == 2
    assert summary["endpoint_blocked_or_incomplete_bundle_count"] == 1
    assert summary["positive_claim_ready_bundle_count"] == 0
    assert summary["can_support_bounded_support_validity"] is False
    assert summary["current_manuscript_bounded_support_validity_claim_ready"] is False
    assert summary["failed_check_count"] == 0
    assert summary["positive_acceptance_failed_count"] > 0
    assert "neutral scientific test" in payload["neutral_reporting_policy"]
    assert "no conformal method" in payload["neutral_reporting_policy"]
    assert payload["neutral_reporting_policy"] in payload["claim_boundaries"]
    assert (
        payload["acceptance_criteria_results"][
            "no_selected_bundle_blocked_by_endpoint_hygiene_posthandling_or_policy"
        ]
        is False
    )
    assert (
        payload["acceptance_criteria_results"][
            "coverage_and_interval_validity_metrics_available_after_handling"
        ]
        is True
    )


def test_checked_in_positive_validation_protocol_current_status_after_generation():
    payload = protocol.build_payload(Path("."))
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "bounded_support_positive_validation_protocol_completed_no_validity_claim"
    )
    assert summary["selected_bundle_count"] == 15
    assert summary["posthandling_validated_bundle_count"] == 15
    assert summary["policy_metrics_available_bundle_count"] == 15
    assert summary["interval_score_metrics_available_bundle_count"] == 11
    assert summary["interval_score_metrics_missing_bundle_count"] == 4
    assert summary["endpoint_blocked_or_incomplete_bundle_count"] == 11
    assert summary["positive_claim_ready_bundle_count"] == 0
    assert summary["can_support_bounded_support_validity"] is False
    assert summary["current_manuscript_bounded_support_validity_claim_ready"] is False
    assert summary["failed_check_count"] == 0
    assert "neutral scientific test" in payload["neutral_reporting_policy"]
