import json
from pathlib import Path

from experiments.regression.scripts import (
    build_main_result_candidate_publication_sidecars as sidecars,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_candidate_publication_sidecars_generate_manifest_index_and_claim(tmp_path):
    report_dir = tmp_path / "experiments/regression/reports/main_result_candidate_bundle_demo"
    ledger = "experiments/regression/results/main_result_candidate_bundle_demo/ledger.jsonl"
    plan_path = tmp_path / sidecars.DEFAULT_PLAN
    results_path = tmp_path / sidecars.DEFAULT_RESULTS

    write_json(
        plan_path,
        {
            "candidate_rows": [
                {
                    "dataset_id": "demo_dataset",
                    "experiment_id": "regression_demo_v1",
                    "config_path": "experiments/regression/configs/main_result_candidate_bundle_demo.yaml",
                    "ledger": ledger,
                    "expected_atomic_run_count": 3,
                    "main_result_candidate_seeds": [401],
                    "target_alphas": ["0.1"],
                    "cp_methods": ["cqr", "cv_plus", "mondrian_abs"],
                    "model_count": 1,
                }
            ]
        },
    )
    write_json(
        results_path,
        {
            "dataset_rows": [
                {
                    "dataset_id": "demo_dataset",
                    "completed_atomic_run_count": 3,
                    "diagnostic_primary_method": "cqr",
                    "diagnostic_selection": {
                        "complete_matched_cell_count": 1,
                        "diagnostic_winner_counts": {"cqr": 1},
                    },
                    "pathology_summary": {
                        "flagged_row_count": 1,
                        "flag_counts": {"coverage_below_nominal": 1},
                    },
                }
            ]
        },
    )
    write_json(
        report_dir / "split_profile.json",
        {
            "target": "y",
            "target_transform": "identity",
            "primary_group": "group",
            "profiles": [
                {
                    "seeds": [
                        {
                            "all_row_id_overlaps_zero": True,
                            "all_split_group_overlaps_zero": True,
                            "sparse_primary_group_cell_count": 1,
                            "all_model_visible_feature_signature_overlaps_zero": False,
                            "all_model_visible_feature_plus_target_signature_overlaps_zero": True,
                        }
                    ]
                }
            ],
        },
    )
    write_json(
        report_dir / "feature_leakage_audit.json",
        {
            "metadata_files_scanned": 1,
            "violations_count": 0,
            "metadata_completeness": {
                "missing_feature_names": 0,
                "missing_preprocessed_feature_names": 0,
            },
        },
    )
    write_json(
        report_dir / "endpoint_audit.json",
        {
            "completed_ledger_rows": 3,
            "reconstructed_runs": 3,
            "reconstruction_failures": 0,
            "observed_target_min": 0,
            "observed_target_max": 10,
            "lower_floor": 0,
            "upper_warning": 10,
            "totals": {
                "lower_below_floor": 2,
                "upper_above_warning": 0,
                "crossings": 0,
                "nonfinite_lower": 0,
                "nonfinite_upper": 0,
                "width_above_observed_range": 1,
                "width_above_twice_observed_range": 0,
            },
        },
    )
    write_json(
        tmp_path / sidecars.BUNDLE_INDEX,
        {
            "schema": "cpfi_regression_manuscript_bundle_index_v1",
            "global_boundaries": ["No final method is selected here."],
            "bundles": [],
        },
    )
    write_json(
        tmp_path / sidecars.CLAIM_REGISTER,
        {
            "schema": "cpfi_regression_manuscript_claim_register_v1",
            "claims": [],
        },
    )
    (tmp_path / sidecars.CLAIM_REGISTER_MD).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / sidecars.CLAIM_REGISTER_MD).write_text(
        "# Regression CP Manuscript Claim Register\n",
        encoding="utf-8",
    )

    payload = sidecars.build_payload(
        tmp_path,
        plan_path=plan_path,
        results_path=results_path,
    )

    manifest = report_dir / "publication_readiness_manifest.md"
    bundle_index = json.loads((tmp_path / sidecars.BUNDLE_INDEX).read_text())
    claim_register = json.loads((tmp_path / sidecars.CLAIM_REGISTER).read_text())

    assert payload["summary"]["manifest_generated_count"] == 1
    assert manifest.exists()
    assert "Status: completed main-result candidate diagnostic bundle" in manifest.read_text()
    assert bundle_index["bundle_summary"]["manifest_count"] == 1
    assert bundle_index["bundles"][0]["paper_table_candidate"] == (
        "main_results_table_blocked_diagnostic_only"
    )
    assert claim_register["claims"][0]["claim_id"] == sidecars.AGGREGATE_CLAIM_ID
    assert claim_register["claims"][0]["status"] == (
        "diagnostic_candidate_evidence_blocked_no_main_result_promotion"
    )
