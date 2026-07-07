import json
from pathlib import Path

from experiments.regression.scripts import (
    audit_venn_abers_grid_ivapd_validation_protocol as audit,
)


ROOT = Path(__file__).resolve().parents[1]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_protocol_sources(root, *, final_status="blocked", requirement_status="blocked"):
    for report_dir, grid_coverage, grid_hit_upper, ivapd_coverage in (
        ("venn_abers_real_data_diagnostic", 0.91, 0.10, 0.94),
        ("venn_abers_fairness_panel_diagnostic", 0.80, 0.05, 0.92),
        ("venn_abers_biomarker_clinical_panel_diagnostic", 0.74, 0.00, 0.89),
    ):
        write_json(
            root / f"experiments/regression/reports/{report_dir}/diagnostic.json",
            {
                "summary": {
                    "run_count": 1,
                    "total_va_grid_reference_rows_scored": 8,
                    "mean_va_grid_reference_subset_coverage": grid_coverage,
                    "mean_va_grid_hit_upper_rate": grid_hit_upper,
                    "mean_va_grid_radius_ratio_vs_bridge": 2.0,
                    "total_ivapd_rows_scored": 10,
                    "mean_ivapd_crps_delta_vs_point_step": -0.1,
                    "mean_ivapd_midpoint_crps": 0.4,
                    "mean_point_step_crps": 0.5,
                },
                "results": [
                    {
                        "run_id": f"{report_dir}_run",
                        "dataset_id": "toy",
                        "model_id": "ridge",
                        "model_family": "linear",
                        "seed": 42,
                        "venn_abers_quantile_grid_reference": {
                            "test_rows_scored": 8,
                            "test_rows_available": 80,
                            "score_grid_size": 31,
                            "grid_hit_upper_rate": grid_hit_upper,
                            "grid_radius_ratio_vs_bridge": 2.0,
                            "grid_metrics": {"coverage": grid_coverage},
                            "bridge_metrics": {"coverage": 0.6},
                        },
                        "ivapd_threshold_grid": {
                            "test_rows_scored": 10,
                            "test_rows_available": 80,
                            "threshold_grid_size": 41,
                            "mean_midpoint_crps": 0.4,
                            "mean_point_step_crps": 0.5,
                            "mean_crps_delta_vs_point_step": -0.1,
                            "midpoint_interval_coverage": 0.86,
                            "interval_extraction_summary": {
                                "conservative_band": {"coverage": ivapd_coverage},
                                "midpoint_cdf": {"coverage": 0.86},
                            },
                        },
                    }
                ],
            },
        )

    write_json(
        root / "experiments/regression/catalogs/manuscript_claim_register.json",
        {
            "claims": [
                {
                    "claim_id": "final_selection_and_fairness_claims_blocked",
                    "status": final_status,
                    "requirements": [
                        {
                            "requirement_id": "venn_abers_regression_validation_gate",
                            "status": requirement_status,
                        }
                    ],
                }
            ]
        },
    )
    method_spec = root / "experiments/regression/method_specs/venn_abers_regression.md"
    method_spec.parent.mkdir(parents=True, exist_ok=True)
    method_spec.write_text(
        "`ivapd_threshold_grid` is not a runner method and not an interval CP claim.\n",
        encoding="utf-8",
    )
    module = root / "cpfi/regression/venn_abers.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(
        "prototype_role = 'threshold_grid_predictive_distribution_not_interval_cp'\n",
        encoding="utf-8",
    )


def test_grid_ivapd_protocol_records_blockers_without_claim(tmp_path):
    write_protocol_sources(tmp_path)

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "venn_abers_grid_ivapd_validation_protocol_defined_no_claim"
    )
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["can_support_validated_venn_abers_regression"] is False
    assert payload["summary"]["can_support_exact_grid_venn_abers_validation"] is False
    assert payload["summary"]["can_support_ivapd_interval_cp_validation"] is False
    assert payload["summary"]["total_grid_reference_rows_scored"] == 24
    assert payload["summary"]["total_ivapd_rows_scored"] == 30
    assert "grid_reference_rows_below_claim_floor" in payload["summary"][
        "validation_blocker_ids"
    ]
    assert "grid_reference_not_full_test_scored" in payload["summary"][
        "validation_blocker_ids"
    ]
    assert "grid_reference_panel_coverage_below_nominal" in payload["summary"][
        "validation_blocker_ids"
    ]
    assert "grid_reference_candidate_grid_hits_upper_boundary" in payload["summary"][
        "validation_blocker_ids"
    ]
    assert "ivapd_threshold_grid_is_predictive_distribution_not_interval_cp" in payload[
        "summary"
    ]["validation_blocker_ids"]


def test_checked_in_venn_abers_method_spec_tracks_completed_grid_audit():
    spec_text = (
        ROOT / "experiments/regression/method_specs/venn_abers_regression.md"
    ).read_text(encoding="utf-8")
    normalized_spec_text = " ".join(spec_text.split())
    plan = json.loads(
        (
            ROOT
            / "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "venn_abers_grid_expansion_plan.json"
        ).read_text(encoding="utf-8")
    )["summary"]
    protocol = json.loads(
        (
            ROOT
            / "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "venn_abers_grid_ivapd_validation_protocol.json"
        ).read_text(encoding="utf-8")
    )["summary"]
    decomposition = json.loads(
        (
            ROOT
            / "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "venn_abers_grid_failure_mode_decomposition.json"
        ).read_text(encoding="utf-8")
    )["summary"]

    assert "82 / 6001 already scored" not in spec_text
    assert "5919 pending rows" not in spec_text
    assert "340 unique next-batch" not in spec_text
    assert (
        f"{plan['total_grid_rows_completed']} / "
        f"{plan['total_test_rows_available']}"
    ) in spec_text
    assert f"{plan['total_grid_rows_pending']} pending rows" in spec_text
    assert f"{plan['next_batch_total_rows']} next-batch" in spec_text
    assert f"{protocol['total_ivapd_rows_scored']} / 6001" in spec_text
    assert "0.8341" in spec_text
    assert "0.9247" in spec_text
    assert "0.1263" in spec_text
    assert decomposition["claim_status"] in spec_text
    assert "validated Venn-Abers regression claims blocked" in normalized_spec_text


def test_grid_ivapd_protocol_counts_worker_grid_expansion_rows(tmp_path):
    write_protocol_sources(tmp_path)
    state_path = (
        tmp_path
        / "experiments/regression/results/venn_abers_grid_expansion/checkpoints/row_results.jsonl"
    )
    write_jsonl(
        state_path,
        [
            {
                "schema": audit.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": "worker_real_1",
                "report_id": "report:venn_abers_real_data_diagnostic",
                "run_id": "real_a",
                "dataset_id": "toy_real",
                "test_index": 2,
                "grid_covered": True,
                "grid_hit_upper": False,
            },
            {
                "schema": audit.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": "worker_real_2",
                "report_id": "report:venn_abers_real_data_diagnostic",
                "run_id": "real_a",
                "dataset_id": "toy_real",
                "test_index": 3,
                "grid_covered": False,
                "grid_hit_upper": True,
            },
            {
                "schema": audit.WORKER_ROW_SCHEMA,
                "status": "failed",
                "row_key": "worker_failed",
                "report_id": "report:venn_abers_real_data_diagnostic",
                "run_id": "real_a",
                "dataset_id": "toy_real",
                "test_index": 4,
            },
        ],
    )

    payload = audit.build_payload(tmp_path, worker_state_path=state_path)
    real_panel = next(
        row
        for row in payload["panel_evidence"]
        if row["report_id"] == "report:venn_abers_real_data_diagnostic"
    )

    assert payload["summary"]["source_grid_reference_rows_scored"] == 24
    assert payload["summary"]["worker_grid_reference_rows_scored"] == 2
    assert payload["summary"]["worker_grid_reference_rows_failed"] == 1
    assert payload["summary"]["worker_failed_task_key_count"] == 1
    assert payload["summary"]["worker_unresolved_failed_task_key_count"] == 1
    assert payload["summary"]["failed_worker_rows_all_superseded"] is False
    assert payload["summary"]["total_grid_reference_rows_scored"] == 26
    assert payload["summary"]["worker_grid_hit_upper_count"] == 1
    assert payload["worker_state"]["duplicate_completed_key_count"] == 0
    assert payload["worker_state"]["unresolved_failed_task_key_count"] == 1
    assert real_panel["worker_grid_reference_rows_scored"] == 2
    assert real_panel["worker_grid_reference_rows_failed"] == 1
    assert real_panel["worker_grid_reference_coverage"] == 0.5
    assert "grid_reference_candidate_grid_hits_upper_boundary" in payload["summary"][
        "validation_blocker_ids"
    ]
    assert "grid_reference_worker_failed_rows_unresolved" in payload["summary"][
        "validation_blocker_ids"
    ]


def test_grid_ivapd_protocol_fails_if_claim_gate_is_promoted(tmp_path):
    write_protocol_sources(
        tmp_path,
        final_status="ready",
        requirement_status="pass",
    )

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "venn_abers_grid_ivapd_validation_protocol_audit_fail"
    )
    failed = {row["check_id"] for row in payload["checks"] if row["status"] == "fail"}
    assert "final_validation_gate_stays_blocked" in failed
