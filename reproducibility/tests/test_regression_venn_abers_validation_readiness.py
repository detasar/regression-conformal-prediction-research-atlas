import json

from experiments.regression.scripts import audit_venn_abers_validation_readiness as audit


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_source_reports(root):
    write_json(
        root / "experiments/regression/reports/venn_abers_quantile_bridge_benchmark/benchmark.json",
        {
            "summary": {
                "panel_count": 3,
                "mean_bridge_coverage": 0.9,
                "mean_grid_coverage": 0.95,
                "mean_bridge_width": 2.0,
                "mean_grid_width": 4.0,
                "mean_abs_radius_delta": 1.0,
                "max_abs_radius_delta": 2.0,
            }
        },
    )
    for report_dir, coverage, grid_coverage, bridge_coverage, ratio, fallback in (
        ("venn_abers_real_data_diagnostic", 0.64, 0.91, 0.59, 2.4, 0.88),
        ("venn_abers_fairness_panel_diagnostic", 0.60, 0.80, 0.60, 2.2, 0.91),
        ("venn_abers_biomarker_clinical_panel_diagnostic", 0.67, 0.73, 0.56, 2.3, 0.92),
    ):
        write_json(
            root / f"experiments/regression/reports/{report_dir}/diagnostic.json",
            {
                "summary": {
                    "dataset_count": 2,
                    "run_count": 4,
                    "mean_venn_abers_coverage": coverage,
                    "mean_venn_abers_width": 10.0,
                    "mean_va_grid_bridge_subset_coverage": bridge_coverage,
                    "mean_va_grid_reference_subset_coverage": grid_coverage,
                    "mean_va_grid_radius_ratio_vs_bridge": ratio,
                    "mean_va_grid_minus_bridge_radius": 1.0,
                    "total_va_grid_reference_rows_scored": 10,
                    "total_ivapd_rows_scored": 20,
                    "interval_method_summary": {
                        "venn_abers_quantile": {"mean_coverage": coverage},
                        "venn_abers_split_fallback": {"mean_coverage": fallback},
                    },
                    "split_fallback_grid_summary": {"mean_coverage": fallback},
                },
                "results": [
                    {
                        "run_id": f"{report_dir}_run_1",
                        "dataset_id": "toy_a",
                        "model_id": "ridge",
                        "model_family": "linear",
                        "seed": 11,
                        "interval_method_comparison": [
                            {"method": "venn_abers_quantile", "coverage": coverage}
                        ],
                    },
                    {
                        "run_id": f"{report_dir}_run_2",
                        "dataset_id": "toy_b",
                        "model_id": "ridge",
                        "model_family": "linear",
                        "seed": 23,
                        "interval_method_comparison": [
                            {
                                "method": "venn_abers_quantile",
                                "coverage": max(0.0, coverage - 0.02),
                            }
                        ],
                    },
                ],
            },
        )


def write_claim_register(root, *, final_status="blocked"):
    write_json(
        root / "experiments/regression/catalogs/manuscript_claim_register.json",
        {
            "claims": [
                {
                    "claim_id": "venn_abers_fast_bridge_negative_result",
                    "status": "diagnostic",
                    "not_claiming": [
                        "No Venn-Abers regression interval-coverage validation is claimed for the fast bridge.",
                        "The split fallback is ordinary split conformal and not a Venn-Abers regression method.",
                    ],
                    "requirements": [
                        {
                            "requirement_id": "negative_evidence_preserved",
                            "status": "present",
                        }
                    ],
                },
                {
                    "claim_id": "final_selection_and_fairness_claims_blocked",
                    "status": "blocked",
                    "requirements": [
                        {
                            "requirement_id": "venn_abers_regression_validation_gate",
                            "status": final_status,
                        }
                    ],
                },
            ]
        },
    )
    write_text(
        root / "experiments/regression/catalogs/manuscript_claim_register.md",
        "The split fallback is ordinary split conformal and not a Venn-Abers regression method.",
    )
    write_text(
        root / "experiments/regression/method_specs/venn_abers_regression.md",
        "The fallback is ordinary split conformal, not a Venn-Abers regression method.",
    )


def test_venn_abers_validation_audit_passes_for_blocked_negative_evidence(tmp_path):
    write_source_reports(tmp_path)
    write_claim_register(tmp_path)

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "venn_abers_validation_blocked_with_negative_evidence"
    )
    assert payload["summary"]["can_support_venn_abers_regression_validation"] is False
    assert payload["summary"]["undercoverage_panel_count"] == 3
    assert payload["summary"]["diagnostic_run_count"] == 6
    assert payload["summary"]["undercoverage_run_count"] == 6
    assert payload["run_undercoverage"]["min_coverage"] < audit.NOMINAL_COVERAGE
    assert payload["summary"]["grid_reference_stronger_panel_count"] == 3
    assert payload["summary"]["failed_check_count"] == 0


def test_venn_abers_validation_audit_fails_if_final_gate_is_promoted(tmp_path):
    write_source_reports(tmp_path)
    write_claim_register(tmp_path, final_status="pass")

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "venn_abers_validation_boundary_audit_fail"
    assert payload["summary"]["failed_check_count"] == 1
    failed = [row for row in payload["checks"] if row["status"] == "fail"]
    assert failed[0]["check_id"] == "final_validation_gate_stays_blocked"
