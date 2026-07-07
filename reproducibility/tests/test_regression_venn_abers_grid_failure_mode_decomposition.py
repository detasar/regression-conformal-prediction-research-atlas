import json

from experiments.regression.scripts import (
    analyze_venn_abers_grid_failure_modes as failure_modes,
)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_failure_mode_sources(root):
    report_dir = root / failure_modes.REPORT_DIR
    write_json(
        report_dir / "venn_abers_grid_ivapd_validation_protocol.json",
        {
            "nominal_coverage": 0.9,
            "claim_thresholds": {"max_grid_upper_hit_rate_for_claim": 0.0},
            "summary": {
                "overall_status": "venn_abers_grid_ivapd_validation_protocol_defined_no_claim",
                "failed_check_count": 0,
                "can_support_validated_venn_abers_regression": False,
                "validation_blocker_count": 3,
                "validation_blocker_ids": [
                    "grid_reference_panel_coverage_below_nominal",
                    "grid_reference_candidate_grid_hits_upper_boundary",
                    "ivapd_threshold_grid_is_predictive_distribution_not_interval_cp",
                ],
                "total_grid_reference_rows_scored": 12,
                "total_grid_reference_rows_available": 12,
                "worker_grid_hit_upper_count": 1,
                "worker_grid_hit_upper_rate": 0.125,
                "ivapd_interval_cp_status": "blocked_predictive_distribution_only",
            },
        },
    )
    write_json(
        report_dir / "venn_abers_grid_expansion_plan.json",
        {
            "summary": {
                "overall_status": "venn_abers_grid_expansion_plan_complete",
                "failed_check_count": 0,
                "run_task_count": 3,
                "total_test_rows_available": 12,
                "total_grid_rows_completed": 12,
                "total_grid_rows_pending": 0,
                "next_batch_total_rows": 0,
                "grid_completion_fraction": 1.0,
            }
        },
    )
    source_rows = [
        (
            "venn_abers_real_data_diagnostic",
            "report:venn_abers_real_data_diagnostic",
            "real_a",
            "toy_real",
            0.5,
            0.0,
        ),
        (
            "venn_abers_fairness_panel_diagnostic",
            "report:venn_abers_fairness_panel_diagnostic",
            "fair_a",
            "toy_fair",
            1.0,
            0.5,
        ),
        (
            "venn_abers_biomarker_clinical_panel_diagnostic",
            "report:venn_abers_biomarker_clinical_panel_diagnostic",
            "bio_a",
            "toy_bio",
            1.0,
            0.0,
        ),
    ]
    for dirname, _report_id, run_id, dataset_id, coverage, hit_rate in source_rows:
        write_json(
            root / f"experiments/regression/reports/{dirname}/diagnostic.json",
            {
                "results": [
                    {
                        "run_id": run_id,
                        "dataset_id": dataset_id,
                        "model_id": "ridge",
                        "model_family": "linear",
                        "seed": 42,
                        "alpha": 0.1,
                        "target": "target",
                        "target_transform": "identity",
                        "venn_abers_quantile_grid_reference": {
                            "test_rows_scored": 2,
                            "test_rows_available": 4,
                            "score_grid_size": 31,
                            "grid_hit_upper_rate": hit_rate,
                            "grid_radius_ratio_vs_bridge": 2.0,
                            "grid_metrics": {"coverage": coverage},
                            "bridge_metrics": {"coverage": 0.5},
                            "split_fallback_metrics": {"coverage": 0.75},
                        },
                    }
                ]
            },
        )
    state_path = (
        root
        / "experiments/regression/results/venn_abers_grid_expansion/checkpoints/"
        "row_results.jsonl"
    )
    write_jsonl(
        state_path,
        [
            {
                "schema": failure_modes.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": "real_a_2",
                "report_id": "report:venn_abers_real_data_diagnostic",
                "run_id": "real_a",
                "dataset_id": "toy_real",
                "test_index": 2,
                "grid_covered": False,
                "grid_hit_upper": False,
                "bridge_covered": False,
                "split_fallback_covered": False,
            },
            {
                "schema": failure_modes.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": "real_a_3",
                "report_id": "report:venn_abers_real_data_diagnostic",
                "run_id": "real_a",
                "dataset_id": "toy_real",
                "test_index": 3,
                "grid_covered": True,
                "grid_hit_upper": False,
                "bridge_covered": True,
                "split_fallback_covered": True,
            },
            {
                "schema": failure_modes.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": "fair_a_2",
                "report_id": "report:venn_abers_fairness_panel_diagnostic",
                "run_id": "fair_a",
                "dataset_id": "toy_fair",
                "test_index": 2,
                "grid_covered": True,
                "grid_hit_upper": True,
                "bridge_covered": True,
                "split_fallback_covered": True,
            },
            {
                "schema": failure_modes.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": "fair_a_3",
                "report_id": "report:venn_abers_fairness_panel_diagnostic",
                "run_id": "fair_a",
                "dataset_id": "toy_fair",
                "test_index": 3,
                "grid_covered": True,
                "grid_hit_upper": False,
                "bridge_covered": True,
                "split_fallback_covered": True,
            },
            {
                "schema": failure_modes.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": "bio_a_2",
                "report_id": "report:venn_abers_biomarker_clinical_panel_diagnostic",
                "run_id": "bio_a",
                "dataset_id": "toy_bio",
                "test_index": 2,
                "grid_covered": True,
                "grid_hit_upper": False,
                "bridge_covered": True,
                "split_fallback_covered": True,
            },
            {
                "schema": failure_modes.WORKER_ROW_SCHEMA,
                "status": "completed",
                "row_key": "bio_a_3",
                "report_id": "report:venn_abers_biomarker_clinical_panel_diagnostic",
                "run_id": "bio_a",
                "dataset_id": "toy_bio",
                "test_index": 3,
                "grid_covered": True,
                "grid_hit_upper": False,
                "bridge_covered": True,
                "split_fallback_covered": True,
            },
        ],
    )
    return state_path


def test_grid_failure_mode_decomposition_keeps_no_claim_boundary(tmp_path):
    state_path = write_failure_mode_sources(tmp_path)

    payload = failure_modes.build_payload(tmp_path, worker_state_path=state_path)

    assert (
        payload["summary"]["overall_status"]
        == "venn_abers_grid_failure_modes_decomposed_no_claim"
    )
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["can_support_validated_venn_abers_regression"] is False
    assert payload["summary"]["coverage_failure_run_count"] == 1
    assert payload["summary"]["upper_boundary_failure_run_count"] == 1
    assert payload["summary"]["total_grid_reference_rows_scored"] == 12
    assert (
        payload["blocker_decomposition"]["coverage_below_nominal"]["top_runs"][0][
            "run_id"
        ]
        == "real_a"
    )
    assert (
        payload["blocker_decomposition"]["candidate_grid_hits_upper_boundary"][
            "top_runs"
        ][0]["run_id"]
        == "fair_a"
    )


def test_grid_failure_mode_markdown_explains_no_validation_claim(tmp_path):
    state_path = write_failure_mode_sources(tmp_path)
    payload = failure_modes.build_payload(tmp_path, worker_state_path=state_path)

    markdown = failure_modes.render_markdown(payload)

    assert "# Venn-Abers Grid Failure-Mode Decomposition" in markdown
    assert "Can support validated Venn-Abers regression: `False`" in markdown
    assert "does not validate Venn-Abers regression interval coverage" in markdown
