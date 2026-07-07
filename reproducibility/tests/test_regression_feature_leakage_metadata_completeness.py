import json
from pathlib import Path

from experiments.regression.scripts import audit_feature_leakage_metadata_completeness as audit


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_metadata_limitation_class_separates_preprocessed_only():
    assert (
        audit.metadata_limitation_class(
            {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 3,
                "missing_feature_drop_columns": 0,
                "missing_feature_drop_policy": 0,
            }
        )
        == "preprocessed_feature_names_missing_only"
    )


def test_metadata_limitation_class_separates_unrecorded_completeness():
    assert audit.metadata_limitation_class({}) == "metadata_completeness_not_recorded"


def test_metadata_limitation_class_separates_drop_policy_gaps():
    assert (
        audit.metadata_limitation_class(
            {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 2,
                "missing_feature_drop_columns": 2,
                "missing_feature_drop_policy": 2,
            }
        )
        == "drop_policy_and_preprocessed_feature_names_missing"
    )


def test_row_from_cross_run_uses_sidecar_claim_boundary(tmp_path):
    sidecar = tmp_path / "experiments/regression/reports/toy/feature_leakage_audit.json"
    _write_json(
        sidecar,
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "metadata_files_scanned": 2,
            "metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 2,
                "missing_feature_drop_columns": 2,
                "missing_feature_drop_policy": 2,
            },
            "violations_count": 0,
            "forbidden_features": ["target", "group"],
            "expected_features": ["x1", "x2"],
            "expected_drop_columns": [],
            "backfill_policy_inference": {
                "exact_feature_set_enforced": True,
                "exact_drop_set_enforced": False,
                "complete_drop_metadata": False,
                "complete_policy_metadata": False,
            },
        },
    )

    row = audit.row_from_cross_run(
        root=tmp_path,
        cross_row={
            "report_id": "report:toy",
            "report_name": "toy",
            "feature_leakage_audit": {
                "path": "experiments/regression/reports/toy/feature_leakage_audit.json"
            },
        },
        runner_drop_guard_ok=True,
    )

    assert row["metadata_limitation_class"] == "drop_policy_and_preprocessed_feature_names_missing"
    assert row["metadata_selection_status"] == "legacy_selection_label_not_recorded"
    assert (
        row["policy_inference_status"]
        == "incomplete_drop_or_policy_metadata"
    )
    assert (
        row["provenance_limitation_class"]
        == "drop_policy_and_preprocessed_feature_names_missing"
    )
    assert row["claim_status"] == "legacy_drop_policy_metadata_missing_no_violation_recorded"
    assert row["available_checks"]["exact_feature_set_enforced"] is True
    assert row["available_checks"]["complete_policy_metadata"] is False


def test_build_payload_triages_legacy_provenance_label_gaps(tmp_path):
    sidecar = tmp_path / "experiments/regression/reports/legacy/feature_leakage_audit.json"
    _write_json(
        sidecar,
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "metadata_files_scanned": 3,
            "metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 0,
                "missing_feature_drop_columns": 0,
                "missing_feature_drop_policy": 0,
            },
            "violations_count": 0,
        },
    )
    cross_run = tmp_path / "experiments/regression/reports/audit/cross_run.json"
    _write_json(
        cross_run,
        {
            "rows": [
                {
                    "report_id": "report:legacy",
                    "report_name": "legacy",
                    "dataset_ids": ["toy"],
                    "feature_leakage_audit": {
                        "present": True,
                        "path": "experiments/regression/reports/legacy/feature_leakage_audit.json",
                        "metadata_selection": None,
                        "backfill_policy_inference": {},
                        "metadata_files_scanned": 3,
                        "metadata_completeness": {
                            "missing_feature_names": 0,
                            "missing_preprocessed_feature_names": 0,
                            "missing_feature_drop_columns": 0,
                            "missing_feature_drop_policy": 0,
                        },
                        "violations_count": 0,
                    },
                    "caveats": [],
                }
            ]
        },
    )

    payload = audit.build_payload(tmp_path, cross_run)

    assert payload["summary"]["triaged_report_count"] == 1
    assert payload["summary"]["legacy_provenance_gap_row_count"] == 1
    assert payload["summary"]["field_metadata_incomplete_row_count"] == 0
    assert payload["summary"]["full_preprocessing_lineage_claim_supported"] is False
    row = payload["rows"][0]
    assert row["metadata_selection_status"] == "legacy_selection_label_not_recorded"
    assert (
        row["policy_inference_status"]
        == "legacy_policy_inference_label_not_recorded"
    )
    assert (
        row["provenance_limitation_class"]
        == "legacy_selection_and_policy_provenance_labels_missing"
    )
    assert (
        row["claim_status"]
        == "legacy_complete_metadata_provenance_label_gap_no_violation_recorded"
    )


def test_build_payload_triages_incomplete_policy_inference_even_when_closure_complete(tmp_path):
    sidecar = (
        tmp_path
        / "experiments/regression/reports/closed_raw_gap/feature_leakage_audit.json"
    )
    _write_json(
        sidecar,
        {
            "schema": "cpfi_prediction_feature_leakage_audit_v1",
            "metadata_files_scanned": 2,
            "metadata_selection": "ledger_referenced_prediction_artifacts",
            "metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 0,
                "missing_feature_drop_columns": 0,
                "missing_feature_drop_policy": 0,
            },
            "raw_metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 2,
                "missing_feature_drop_columns": 2,
                "missing_feature_drop_policy": 2,
            },
            "metadata_closure": {
                "enabled": True,
                "close_missing_preprocessed_feature_names_from_feature_names": True,
                "close_missing_drop_metadata_from_expected_policy": True,
            },
            "backfill_policy_inference": {
                "exact_feature_set_enforced": True,
                "exact_drop_set_enforced": False,
                "complete_drop_metadata": False,
                "complete_policy_metadata": False,
            },
            "violations_count": 0,
        },
    )
    cross_run = tmp_path / "experiments/regression/reports/audit/cross_run.json"
    _write_json(
        cross_run,
        {
            "rows": [
                {
                    "report_id": "report:closed_raw_gap",
                    "report_name": "closed_raw_gap",
                    "dataset_ids": ["toy"],
                    "feature_leakage_audit": {
                        "present": True,
                        "path": (
                            "experiments/regression/reports/closed_raw_gap/"
                            "feature_leakage_audit.json"
                        ),
                        "metadata_selection": "ledger_referenced_prediction_artifacts",
                        "backfill_policy_inference": {
                            "complete_drop_metadata": False,
                            "complete_policy_metadata": False,
                        },
                        "metadata_closure": {"enabled": True},
                        "metadata_completeness": {
                            "missing_feature_names": 0,
                            "missing_preprocessed_feature_names": 0,
                            "missing_feature_drop_columns": 0,
                            "missing_feature_drop_policy": 0,
                        },
                        "violations_count": 0,
                    },
                    "caveats": [],
                }
            ]
        },
    )

    payload = audit.build_payload(tmp_path, cross_run)

    assert payload["summary"]["triaged_report_count"] == 1
    assert payload["summary"]["policy_inference_incomplete_row_count"] == 1
    assert payload["summary"]["field_metadata_incomplete_row_count"] == 0
    assert payload["summary"]["full_preprocessing_lineage_claim_supported"] is False
    row = payload["rows"][0]
    assert row["metadata_limitation_class"] == "complete_metadata"
    assert row["provenance_limitation_class"] == "policy_inference_incomplete"
    assert row["claim_status"] == "incomplete_policy_inference_no_violation_recorded"


def test_render_markdown_includes_boundaries():
    payload = {
        "generated_at_utc": "2026-01-01T00:00:00+00:00",
        "source_cross_run_integrity_audit_path": "cross.json",
        "claim_boundaries": audit.CLAIM_BOUNDARIES,
        "summary": {
            "caveat_rows_triaged": 1,
            "runner_feature_drop_guard_ok": True,
            "metadata_limitation_class_counts": {"preprocessed_feature_names_missing_only": 1},
            "provenance_limitation_class_counts": {"preprocessed_feature_names_missing_only": 1},
            "metadata_selection_status_counts": {"ledger_referenced_prediction_artifacts": 1},
            "policy_inference_status_counts": {"complete_drop_and_policy_metadata": 1},
            "claim_status_counts": {
                "bounded_raw_feature_and_runner_drop_check_no_violation_recorded": 1
            },
            "missing_metadata_field_totals": {"missing_preprocessed_feature_names": 3},
            "hard_feature_leakage_violation_row_count": 0,
            "legacy_provenance_gap_row_count": 0,
            "field_metadata_incomplete_row_count": 1,
            "full_preprocessing_lineage_claim_supported": False,
            "scientific_status": "hard_feature_leakage_not_detected_in_available_sidecars_but_full_preprocessed_metadata_closure_not_claimed",
        },
        "rows": [
            {
                "report_name": "toy",
                "metadata_limitation_class": "preprocessed_feature_names_missing_only",
                "provenance_limitation_class": "preprocessed_feature_names_missing_only",
                "claim_status": "bounded_raw_feature_and_runner_drop_check_no_violation_recorded",
                "metadata_completeness": {"missing_preprocessed_feature_names": 3},
                "recommended_next_action": "Keep caveat.",
            }
        ],
    }

    markdown = audit.render_markdown(payload)

    assert "# Feature Leakage Metadata Completeness Triage" in markdown
    assert "full preprocessing-output feature-name closure is not claimed" in markdown
    assert "`toy`" in markdown


def test_rel_accepts_external_probe_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_path = repo_root / "experiments/regression/reports/audit.json"
    external_path = tmp_path / "scratch/audit.json"

    assert audit.rel(repo_path, repo_root) == "experiments/regression/reports/audit.json"
    assert audit.rel(external_path, repo_root) == str(external_path.resolve())
