import json

from experiments.regression.scripts import build_bounded_support_dataset_audit as audit


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root):
    write_json(
        root / audit.BOUNDED_SUPPORT_PROTOCOL,
        {
            "summary": {
                "overall_status": "bounded_support_protocol_defined_no_validity_claim"
            },
            "target_domain_classes": {
                "nonnegative": {},
                "bounded_continuous": {},
                "bounded_ordinal": {},
                "unbounded_real": {},
                "count_or_rate": {},
            },
            "interval_handling_policies": {
                "report_raw_unclipped_with_excursion_audit": {}
            },
        },
    )
    bundle = {
        "bundle_id": "duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_identity_ridreth3_model_visible",
        "dataset_id": "nhanes_2017_2018_bmi",
        "target": "BMXBMI",
        "target_transform": "identity",
        "diagnostic_group": "RIDRETH3",
        "manifest_path": (
            "experiments/regression/reports/"
            "duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_identity_ridreth3_model_visible/"
            "publication_readiness_manifest.md"
        ),
    }
    write_json(
        root / audit.BUNDLE_INDEX,
        {"bundle_summary": {"manifest_count": 1}, "bundles": [bundle]},
    )
    write_json(
        root / audit.EVIDENCE_VIEW,
        {"summary": {"endpoint_result_count": 7, "endpoint_caveat_count": 6}},
    )
    write_json(
        root / audit.FINAL_SELECTION,
        {
            "summary": {"claim_status": "blocked"},
            "requirement_statuses": {"endpoint_bounded_support_gate": "blocked"},
        },
    )
    write_json(
        root / audit.TARGET_DOMAIN_PROVENANCE,
        {
            "summary": {
                "overall_status": "target_domain_provenance_ready",
                "failed_check_count": 0,
                "row_count": 1,
                "source_artifact_complete_count": 1,
                "external_source_row_count": 0,
                "bounded_ordinal_row_count": 0,
            },
            "rows": [
                {
                    "dataset_id": "nhanes_2017_2018_bmi",
                    "target": "BMXBMI",
                    "target_domain_class": "nonnegative",
                    "natural_lower": 0.0,
                    "natural_upper": None,
                    "natural_bound_status": "lower_bound_provenance_present",
                    "provenance_notes": ["BMI lower-bound provenance fixture."],
                    "source_urls": [],
                    "source_artifacts": [
                        "experiments/regression/audits/nhanes_2017_2018_bmi/audit.json",
                        (
                            "experiments/regression/reports/"
                            "duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_identity_ridreth3_model_visible/"
                            "endpoint_audit.json"
                        ),
                    ],
                    "target_transform_inverse_policy": "identity",
                }
            ],
        },
    )
    write_json(
        root / audit.POSTHANDLING_VALIDATION,
        {
            "summary": {
                "overall_status": "bounded_support_posthandling_validation_partial",
                "validated_bundle_count": 0,
                "unvalidated_bundle_count": 1,
                "reconstruction_failures": 0,
            },
            "scope": {"scope_note": "method_or_row_limited", "include_methods": []},
            "rows": [],
        },
    )
    write_json(
        root / "experiments/regression/audits/nhanes_2017_2018_bmi/audit.json",
        {
            "dataset_id": "nhanes_2017_2018_bmi",
            "target": "BMXBMI",
            "n_rows": 10,
            "target_min": 12.3,
            "target_max": 86.2,
            "target_mean": 26.5,
            "target_std": 8.0,
            "target_missing_rate": 0.0,
        },
    )
    write_json(
        root / "experiments/regression/audits/nhanes_2017_2018_bmi/profile.json",
        {
            "dataset_id": "nhanes_2017_2018_bmi",
            "target": "BMXBMI",
            "target_summary": {
                "n": 10,
                "min": 12.3,
                "max": 86.2,
                "mean": 26.5,
                "std": 8.0,
                "missing_rate": 0.0,
                "quantiles": {"0.5": 25.0},
            },
        },
    )
    manifest_path = root / bundle["manifest_path"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "- Bounded-support policy: no bounded-support validity claim is made.",
        encoding="utf-8",
    )
    write_json(
        manifest_path.parent / "endpoint_audit.json",
        {
            "audit_schema": "cpfi_regression_endpoint_audit_v2",
            "completed_ledger_rows": 3,
            "reconstructed_runs": 3,
            "missing_artifacts": 0,
            "reconstruction_failures": 0,
            "failure_count_total": 0,
            "observed_target_min": 12.3,
            "observed_target_max": 86.2,
            "lower_floor": 0.0,
            "upper_warning": 100.0,
            "totals": {
                "intervals": 100,
                "lower_below_floor": 2,
                "upper_above_warning": 0,
                "lower_below_observed_min": 5,
                "upper_above_observed_max": 1,
                "width_above_observed_range": 1,
                "width_above_twice_observed_range": 0,
                "crossings": 0,
                "nonfinite_lower": 0,
                "nonfinite_upper": 0,
            },
        },
    )


def test_bounded_support_dataset_audit_blocks_current_bundle_claims(tmp_path):
    write_minimal_sources(tmp_path)

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "dataset_bounded_support_audit_completed_no_validity_claim"
    )
    assert payload["summary"]["bundle_count"] == 1
    assert payload["summary"]["bounded_support_ready_bundle_count"] == 0
    assert "ready_for_bounded_support_claim" not in payload["summary"]["claim_status_counts"]
    assert payload["summary"]["natural_domain_excursion_bundle_count"] == 1
    assert payload["summary"]["endpoint_support_status_counts"] == {
        "blocked_natural_domain_endpoint_excursions": 1
    }
    assert payload["summary"]["posthandling_support_status_counts"] == {"not_run": 1}
    assert payload["summary"]["endpoint_support_blocked_or_incomplete_bundle_count"] == 1
    assert payload["summary"]["target_domain_class_counts"] == {"nonnegative": 1}
    assert payload["failed_checks"] == []
    row = payload["rows"][0]
    assert row["target_domain_class"] == "nonnegative"
    assert row["endpoint_support_status"] == "blocked_natural_domain_endpoint_excursions"
    assert row["posthandling_support_status"] == "not_run"
    assert row["endpoint_audit"]["natural_domain_endpoint_excursion_count"] == 2
    assert row["endpoint_audit"]["natural_domain_endpoint_excursion_rate"] == 0.02
    assert row["can_support_bounded_support_validity"] is False
    assert "natural_domain_endpoint_excursions" in row["blockers"]
    assert "positive_bounded_support_validation_not_run" in row["blockers"]


def test_bounded_support_dataset_audit_fails_when_protocol_is_not_available(tmp_path):
    write_minimal_sources(tmp_path)
    protocol_path = tmp_path / audit.BOUNDED_SUPPORT_PROTOCOL
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["summary"]["overall_status"] = "bounded_support_protocol_incomplete"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "dataset_bounded_support_audit_incomplete"
    assert "bounded_support_protocol_available" in payload["failed_checks"]


def test_bounded_support_dataset_audit_markdown_lists_endpoint_excursions(tmp_path):
    write_minimal_sources(tmp_path)
    payload = audit.build_payload(tmp_path)

    markdown = audit.render_markdown(payload)

    assert "# Bounded Support Dataset Audit" in markdown
    assert "natural_domain_endpoint_excursions" in markdown
    assert "Endpoint support status counts" in markdown
    assert "bounded-support-ready bundles: 0".lower() in markdown.lower()


def test_bounded_support_dataset_audit_separates_clean_endpoint_from_global_claim_blocker(
    tmp_path,
):
    write_minimal_sources(tmp_path)
    manifest_path = (
        tmp_path
        / "experiments/regression/reports/"
        "duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_identity_ridreth3_model_visible/"
        "publication_readiness_manifest.md"
    )
    endpoint_path = manifest_path.parent / "endpoint_audit.json"
    endpoint = json.loads(endpoint_path.read_text(encoding="utf-8"))
    endpoint["totals"]["lower_below_floor"] = 0
    endpoint["totals"]["min_lower"] = 12.1
    endpoint_path.write_text(json.dumps(endpoint), encoding="utf-8")
    write_json(
        tmp_path / audit.POSTHANDLING_VALIDATION,
        {
            "summary": {
                "overall_status": "bounded_support_posthandling_validation_completed",
                "validated_bundle_count": 1,
                "unvalidated_bundle_count": 0,
                "reconstruction_failures": 0,
            },
            "scope": {
                "scope_note": "all_completed_rows_in_selected_bundles",
                "include_methods": [],
                "max_completed_per_bundle": None,
            },
            "rows": [
                {
                    "bundle_id": (
                        "duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_"
                        "identity_ridreth3_model_visible"
                    ),
                    "status": "validated",
                    "completed_ledger_rows": 3,
                    "total_completed_ledger_rows": 3,
                    "policies": {"clip_to_natural_bounds": {"coverage": 0.9}},
                }
            ],
        },
    )

    payload = audit.build_payload(tmp_path)

    row = payload["rows"][0]
    assert row["endpoint_support_status"] == "clean_no_natural_domain_endpoint_excursions"
    assert row["posthandling_support_status"] == "validated_all_completed_rows"
    assert row["claim_status"] == "blocked_no_bounded_support_validity_claim"
    assert row["blockers"] == ["global_bounded_support_validity_claim_disabled"]
    assert payload["summary"]["endpoint_support_clean_bundle_count"] == 1
    assert payload["summary"]["endpoint_support_blocked_or_incomplete_bundle_count"] == 0
    assert payload["summary"]["bounded_support_ready_bundle_count"] == 0


def test_bounded_support_dataset_audit_flags_unknown_natural_excursion_count(tmp_path):
    write_minimal_sources(tmp_path)
    bundle = {
        "bundle_id": "duplicate_cluster_sensitivity_uci_wine_quality_duplicate_sensitivity_row_signature",
        "dataset_id": "uci_wine_quality",
        "target": "quality",
        "target_transform": "identity",
        "diagnostic_group": "duplicate_sensitivity",
        "manifest_path": (
            "experiments/regression/reports/"
            "duplicate_cluster_sensitivity_uci_wine_quality_duplicate_sensitivity_row_signature/"
            "publication_readiness_manifest.md"
        ),
    }
    write_json(
        tmp_path / audit.BUNDLE_INDEX,
        {"bundle_summary": {"manifest_count": 1}, "bundles": [bundle]},
    )
    write_json(
        tmp_path / audit.TARGET_DOMAIN_PROVENANCE,
        {
            "summary": {
                "overall_status": "target_domain_provenance_ready",
                "failed_check_count": 0,
                "row_count": 1,
                "source_artifact_complete_count": 1,
                "external_source_row_count": 1,
                "bounded_ordinal_row_count": 1,
            },
            "rows": [
                {
                    "dataset_id": "uci_wine_quality",
                    "target": "quality",
                    "target_domain_class": "bounded_ordinal",
                    "natural_lower": 0.0,
                    "natural_upper": 10.0,
                    "natural_bound_status": "bounded_ordinal_source_provenance_present",
                    "provenance_notes": [
                        "Official UCI metadata describes quality score between 0 and 10."
                    ],
                    "source_urls": [
                        "https://archive.ics.uci.edu/dataset/186/wine%2Bquality"
                    ],
                    "source_artifacts": [
                        "experiments/regression/audits/uci_wine_quality/audit.json"
                    ],
                    "target_transform_inverse_policy": "identity on ordinal score scale",
                }
            ],
        },
    )
    write_json(
        tmp_path / audit.POSTHANDLING_VALIDATION,
        {
            "summary": {
                "overall_status": "bounded_support_posthandling_validation_partial",
                "validated_bundle_count": 1,
                "unvalidated_bundle_count": 0,
                "reconstruction_failures": 0,
            },
            "scope": {
                "scope_note": "all_completed_rows_in_selected_bundles",
                "include_methods": [],
                "max_completed_per_bundle": None,
            },
            "rows": [
                {
                    "bundle_id": bundle["bundle_id"],
                    "status": "validated",
                    "completed_ledger_rows": 1428,
                    "total_completed_ledger_rows": 1428,
                    "policies": {
                        "clip_to_natural_bounds": {
                            "coverage": 0.9,
                            "mean_width": 2.0,
                            "interval_score": 3.0,
                            "lower_below_natural_count": 0,
                            "upper_above_natural_count": 0,
                        }
                    },
                }
            ],
        },
    )
    write_json(
        tmp_path / "experiments/regression/audits/uci_wine_quality/audit.json",
        {
            "dataset_id": "uci_wine_quality",
            "target": "quality",
            "n_rows": 10,
            "target_min": 3.0,
            "target_max": 9.0,
            "target_mean": 5.7,
            "target_std": 0.8,
            "target_missing_rate": 0.0,
        },
    )
    write_json(
        tmp_path / "experiments/regression/audits/uci_wine_quality/profile.json",
        {
            "target_summary": {
                "n": 10,
                "min": 3.0,
                "max": 9.0,
                "mean": 5.7,
                "std": 0.8,
                "missing_rate": 0.0,
            }
        },
    )
    manifest_path = tmp_path / bundle["manifest_path"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "- Bounded-support policy: no bounded-support validity claim is made.",
        encoding="utf-8",
    )
    write_json(
        manifest_path.parent / "endpoint_audit.json",
        {
            "audit_schema": "cpfi_regression_endpoint_audit_v2",
            "completed_ledger_rows": 2,
            "reconstructed_runs": 2,
            "missing_artifacts": 0,
            "reconstruction_failures": 0,
            "failure_count_total": 0,
            "observed_target_min": 3.0,
            "observed_target_max": 9.0,
            "lower_floor": 0.0,
            "upper_warning": 9.0,
            "totals": {
                "intervals": 1000,
                "min_lower": 1.4,
                "max_upper": 10.2,
                "lower_below_floor": 0,
                "upper_above_warning": 12,
                "lower_below_observed_min": 5,
                "upper_above_observed_max": 12,
                "width_above_observed_range": 2,
                "width_above_twice_observed_range": 0,
                "crossings": 0,
                "nonfinite_lower": 0,
                "nonfinite_upper": 0,
            },
        },
    )

    payload = audit.build_payload(tmp_path)

    row = payload["rows"][0]
    endpoint = row["endpoint_audit"]
    assert row["natural_lower"] == 0.0
    assert row["natural_upper"] == 10.0
    assert row["natural_bound_status"] == "bounded_ordinal_source_provenance_present"
    assert "missing_natural_bound_provenance" not in row["blockers"]
    assert "positive_bounded_support_validation_not_run" not in row["blockers"]
    assert "positive_bounded_support_validation_incomplete_scope" not in row["blockers"]
    assert row["claim_status"] == "blocked_no_bounded_support_validity_claim"
    assert (
        row["endpoint_support_status"]
        == "blocked_natural_domain_endpoint_excursion_count_unknown"
    )
    assert row["posthandling_support_status"] == "validated_all_completed_rows"
    assert "global_bounded_support_validity_claim_disabled" in row["blockers"]
    assert (
        row["bounded_support_posthandling_validation"]["clip_policy"]["coverage"]
        == 0.9
    )
    assert endpoint["natural_domain_endpoint_excursion_present"] is True
    assert endpoint["natural_domain_endpoint_excursion_count"] is None
    assert (
        endpoint["natural_domain_endpoint_excursion_count_status"]
        == "not_computed_extreme_crossing"
    )
    assert payload["summary"]["natural_domain_excursion_unknown_count_bundle_count"] == 1
