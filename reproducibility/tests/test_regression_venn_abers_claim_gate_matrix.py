import json

from experiments.regression.scripts import audit_venn_abers_claim_gate_matrix as audit


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_claim_gate_sources(
    root,
    *,
    final_claim_status="blocked",
    publication_can_support=False,
    min_panel_grid_coverage=0.84,
    max_panel_grid_hit_upper_rate=0.12,
    ivapd_validated=False,
):
    report_dir = root / audit.REPORT_DIR
    write_json(
        root / audit.VALIDATION_READINESS,
        {
            "summary": {
                "overall_status": "venn_abers_validation_blocked_with_negative_evidence",
                "source_report_count": 4,
                "diagnostic_panel_count": 3,
                "undercoverage_panel_count": 3,
                "diagnostic_run_count": 14,
                "undercoverage_run_count": 14,
                "min_venn_abers_run_coverage": 0.56,
                "max_venn_abers_run_coverage": 0.72,
                "negative_evidence_requirement_status": "present",
                "validation_requirement_status": "blocked",
                "can_support_venn_abers_regression_validation": False,
                "split_fallback_near_nominal_panel_count": 3,
                "claim_boundary": (
                    "Fast bridge rows are diagnostic negative evidence; split "
                    "fallback rows are ordinary split conformal fallback evidence."
                ),
            }
        },
    )
    write_json(
        root / audit.GRID_IVAPD_PROTOCOL,
        {
            "summary": {
                "overall_status": "venn_abers_grid_ivapd_validation_protocol_defined_no_claim",
                "source_report_count": 3,
                "nominal_coverage": 0.9,
                "total_grid_reference_rows_scored": 6001,
                "total_grid_reference_rows_available": 6001,
                "min_panel_grid_reference_coverage": min_panel_grid_coverage,
                "max_panel_grid_hit_upper_rate": max_panel_grid_hit_upper_rate,
                "can_support_ivapd_interval_cp_validation": ivapd_validated,
                "ivapd_interval_cp_status": (
                    "validated_interval_cp"
                    if ivapd_validated
                    else "blocked_predictive_distribution_only"
                ),
                "total_ivapd_rows_scored": 250,
                "total_ivapd_rows_available": 6001,
                "ivapd_scored_fraction": 250 / 6001,
                "failed_worker_rows_all_superseded": True,
                "worker_failed_task_key_count": 5,
                "worker_superseded_failed_task_key_count": 5,
                "worker_unresolved_failed_task_key_count": 0,
                "worker_grid_hit_upper_count": 111,
                "worker_grid_hit_upper_rate": 111 / 5919,
            }
        },
    )
    write_json(
        root / audit.GRID_EXPANSION_PLAN,
        {
            "summary": {
                "overall_status": "venn_abers_grid_expansion_plan_complete",
                "failed_check_count": 0,
                "source_report_count": 3,
                "total_grid_rows_completed": 6001,
                "total_test_rows_available": 6001,
                "total_grid_rows_pending": 0,
                "grid_completion_fraction": 1.0,
            }
        },
    )
    write_json(
        root / audit.FAILURE_MODE_DECOMPOSITION,
        {
            "summary": {
                "overall_status": "venn_abers_grid_failure_modes_decomposed_no_claim",
                "source_report_count": 3,
                "failed_check_count": 0,
                "can_support_validated_venn_abers_regression": False,
                "validation_blocker_count": 3,
                "validation_blocker_ids": [
                    "grid_reference_panel_coverage_below_nominal",
                    "grid_reference_candidate_grid_hits_upper_boundary",
                    "ivapd_threshold_grid_is_predictive_distribution_not_interval_cp",
                ],
                "claim_status": "no_validated_venn_abers_regression_claim",
                "nominal_coverage": 0.9,
                "max_grid_upper_hit_rate_for_claim": 0.0,
                "min_run_grid_reference_coverage": 0.8,
                "max_run_grid_hit_upper_rate": 0.18,
                "coverage_failure_panel_count": 2,
                "coverage_failure_run_count": 9,
            }
        },
    )
    write_json(
        root / audit.FINAL_SELECTION,
        {
            "summary": {
                "claim_status": final_claim_status,
                "blocked_requirement_count": 6 if final_claim_status == "blocked" else 0,
            }
        },
    )
    write_json(
        root / audit.PUBLICATION_METHODOLOGY,
        {
            "summary": {
                "overall_status": "publication_workbench_ready_with_caveats",
                "failed_check_count": 0,
                "can_support_venn_abers_regression_validation": publication_can_support,
            }
        },
    )
    assert report_dir.exists()


def test_venn_abers_claim_gate_matrix_blocks_positive_claim_with_evidence(tmp_path):
    write_claim_gate_sources(tmp_path)

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "venn_abers_claim_gate_matrix_blocked_with_complete_evidence"
    )
    assert payload["summary"]["can_support_validated_venn_abers_regression"] is False
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["positive_claim_requirement_count"] == 4
    assert payload["summary"]["positive_claim_pass_count"] == 1
    assert payload["summary"]["positive_claim_blocked_count"] == 3
    assert payload["summary"]["blocked_positive_requirement_ids"] == [
        "score_grid_panel_coverage_nominal",
        "score_grid_upper_boundary_free",
        "ivapd_interval_cp_validated",
    ]

    rows = {row["requirement_id"]: row for row in payload["requirements"]}
    assert rows["score_grid_full_test_scored"]["status"] == "pass"
    assert rows["score_grid_panel_coverage_nominal"]["status"] == "blocked"
    assert rows["score_grid_upper_boundary_free"]["status"] == "blocked"
    assert rows["ivapd_interval_cp_validated"]["status"] == "blocked"


def test_venn_abers_claim_gate_matrix_fails_if_claim_guardrail_is_promoted(tmp_path):
    write_claim_gate_sources(
        tmp_path,
        final_claim_status="ready",
        publication_can_support=True,
    )

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "venn_abers_claim_gate_matrix_audit_fail"
    assert payload["summary"]["failed_check_count"] == 2
    failed = [
        row["requirement_id"]
        for row in payload["requirements"]
        if row["status"] == "fail"
    ]
    assert failed == [
        "final_claim_gate_consistent_with_matrix",
        "publication_methodology_blocks_venn_abers_claim",
    ]


def test_venn_abers_claim_gate_matrix_can_describe_ready_positive_requirements(tmp_path):
    write_claim_gate_sources(
        tmp_path,
        final_claim_status="ready",
        publication_can_support=True,
        min_panel_grid_coverage=0.91,
        max_panel_grid_hit_upper_rate=0.0,
        ivapd_validated=True,
    )

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "venn_abers_claim_gate_matrix_ready_for_positive_claim"
    )
    assert payload["summary"]["can_support_validated_venn_abers_regression"] is True
    assert payload["summary"]["positive_claim_pass_count"] == 4
    assert payload["summary"]["positive_claim_blocked_count"] == 0
