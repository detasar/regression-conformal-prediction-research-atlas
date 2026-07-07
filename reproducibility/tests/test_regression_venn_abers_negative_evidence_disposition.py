import json
from pathlib import Path

from experiments.regression.scripts import (
    audit_venn_abers_negative_evidence_disposition as disposition,
)


def _write_json(root: Path, relative: str, payload: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _base_fixture(root: Path) -> None:
    report = "experiments/regression/reports/methodology_sanity_audit_20260627"
    _write_json(
        root,
        "experiments/regression/catalogs/manuscript_claim_register.json",
        {
            "claims": [
                {
                    "claim_id": "venn_abers_fast_bridge_negative_result",
                    "claim_type": "negative_result",
                    "status": "diagnostic",
                    "method_ids": [
                        "venn_abers_quantile",
                        "venn_abers_split_fallback",
                    ],
                    "not_claiming": [
                        "No Venn-Abers regression interval-coverage validation is claimed for the fast bridge."
                    ],
                    "requirements": [
                        {
                            "requirement_id": "negative_evidence_preserved",
                            "status": "present",
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        root,
        f"{report}/venn_abers_validation_readiness_audit.json",
        {
            "summary": {
                "overall_status": "venn_abers_validation_blocked_with_negative_evidence",
                "can_support_venn_abers_regression_validation": False,
                "negative_evidence_requirement_status": "present",
                "validation_requirement_status": "blocked",
                "diagnostic_panel_count": 3,
                "undercoverage_panel_count": 3,
                "undercoverage_run_count": 14,
            }
        },
    )
    _write_json(
        root,
        f"{report}/venn_abers_grid_ivapd_validation_protocol.json",
        {
            "summary": {
                "overall_status": "venn_abers_grid_ivapd_validation_protocol_defined_no_claim",
                "can_support_validated_venn_abers_regression": False,
                "can_support_exact_grid_venn_abers_validation": False,
                "can_support_ivapd_interval_cp_validation": False,
                "validation_blocker_count": 3,
                "ivapd_interval_cp_status": "blocked_predictive_distribution_only",
            }
        },
    )
    _write_json(
        root,
        f"{report}/venn_abers_grid_failure_mode_decomposition.json",
        {
            "summary": {
                "overall_status": "venn_abers_grid_failure_modes_decomposed_no_claim",
                "claim_status": "no_validated_venn_abers_regression_claim",
                "can_support_validated_venn_abers_regression": False,
            }
        },
    )
    _write_json(
        root,
        f"{report}/venn_abers_claim_gate_matrix.json",
        {
            "summary": {
                "overall_status": "venn_abers_claim_gate_matrix_blocked_with_complete_evidence",
                "can_support_validated_venn_abers_regression": False,
                "positive_claim_ready": False,
                "positive_claim_blocked_count": 3,
                "failed_check_count": 0,
                "blocked_positive_requirement_ids": [
                    "score_grid_panel_coverage_nominal"
                ],
            }
        },
    )
    _write_json(
        root,
        f"{report}/method_selection_candidate_audit.json",
        {
            "summary": {
                "overall_status": "method_selection_candidate_audit_ready_no_final_selection",
                "can_support_final_method_selection": False,
                "final_selection_claim_status": "blocked",
                "venn_abers_excluded_count": 2,
                "venn_abers_validation_status": "venn_abers_validation_blocked_with_negative_evidence",
            },
            "shortlist_methods": [
                {"cp_method": "cqr"},
                {"cp_method": "mondrian_abs"},
                {"cp_method": "cv_plus"},
            ],
            "excluded_methods": [
                {
                    "cp_method": "venn_abers_quantile",
                    "exclusion_reasons": [
                        "frontier_cell_count_below_shortlist_threshold",
                        "venn_abers_validation_gate_blocked",
                    ],
                },
                {
                    "cp_method": "venn_abers_split_fallback",
                    "exclusion_reasons": [
                        "frontier_cell_count_below_shortlist_threshold",
                        "venn_abers_validation_gate_blocked",
                    ],
                },
            ],
        },
    )
    _write_json(
        root,
        f"{report}/method_performance_synthesis.json",
        {
            "summary": {
                "overall_status": "method_performance_synthesis_descriptive_no_final_selection",
                "can_support_final_method_selection": False,
                "claim_status": "descriptive_no_final_selection",
            }
        },
    )
    _write_json(
        root,
        "experiments/regression/manuscript/bundle_eligibility_matrix.json",
        {
            "summary": {
                "overall_status": "bundle_eligibility_matrix_ready_no_final_claims",
                "main_results_eligible_count": 0,
                "final_claim_eligible_count": 0,
            },
            "rows": [
                {
                    "bundle_id": "bundle_with_venn_abers_negative_evidence",
                    "dataset_id": "dataset_a",
                    "status": "completed_with_caveats",
                    "paper_table_candidate": "robustness_results_table_with_caveats",
                    "blocked_surface_ids": ["main_results_table"],
                    "eligible_surface_ids": ["robustness_results_table"],
                    "promotion_blockers": [
                        "venn_abers_quantile remains diagnostic negative evidence"
                    ],
                    "surface_eligibility": {
                        "main_results_table": {
                            "eligible": False,
                            "status": "blocked",
                        },
                        "negative_results_table": {
                            "eligible": False,
                            "status": "not_applicable",
                        },
                    },
                }
            ],
        },
    )
    _write_json(
        root,
        f"{report}/final_selection_claim_boundary_audit.json",
        {
            "requirement_statuses": {
                "venn_abers_regression_validation_gate": "blocked"
            },
            "summary": {"overall_status": "pass", "claim_status": "blocked"},
        },
    )


def test_venn_abers_negative_evidence_disposition_passes_when_quarantined(tmp_path):
    _base_fixture(tmp_path)

    payload = disposition.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "venn_abers_negative_evidence_disposition_pass"
    )
    assert payload["summary"]["shortlist_venn_abers_method_count"] == 0
    assert payload["summary"]["excluded_venn_abers_method_count"] == 2
    assert payload["summary"]["venn_bundle_main_eligible_count"] == 0
    assert payload["summary"]["negative_result_reporting_ready"] is True
    assert (
        payload["summary"]["current_manuscript_positive_validation_required"]
        is False
    )
    assert (
        payload["summary"]["optional_future_positive_validation_status"]
        == "optional_deferred_not_required_for_current_manuscript"
    )


def test_venn_abers_negative_evidence_disposition_fails_if_shortlisted(tmp_path):
    _base_fixture(tmp_path)
    path = (
        tmp_path
        / "experiments/regression/reports/methodology_sanity_audit_20260627"
        / "method_selection_candidate_audit.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["shortlist_methods"].append({"cp_method": "venn_abers_quantile"})
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = disposition.build_payload(tmp_path)

    assert result["summary"]["failed_check_count"] == 1
    assert result["summary"]["shortlist_venn_abers_method_count"] == 1
    failed = [row["check_id"] for row in result["checks"] if row["status"] == "fail"]
    assert failed == ["method_selection_excludes_validation_blocked_venn_abers"]


def test_venn_abers_negative_evidence_disposition_fails_if_main_eligible(tmp_path):
    _base_fixture(tmp_path)
    path = tmp_path / "experiments/regression/manuscript/bundle_eligibility_matrix.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    row = payload["rows"][0]
    row["blocked_surface_ids"] = []
    row["surface_eligibility"]["main_results_table"]["eligible"] = True
    row["surface_eligibility"]["main_results_table"]["status"] = "eligible"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = disposition.build_payload(tmp_path)

    assert result["summary"]["failed_check_count"] == 1
    assert result["summary"]["venn_bundle_main_eligible_count"] == 1
    failed = [row["check_id"] for row in result["checks"] if row["status"] == "fail"]
    assert failed == ["manuscript_bundle_surface_disposition"]


def test_negative_results_table_preserves_venn_abers_claim_boundaries():
    text = (
        Path("experiments/regression/manuscript/negative_results_table.md")
        .read_text(encoding="utf-8")
    )

    required_snippets = [
        "14 / 14 diagnostic runs are below nominal 0.9",
        "coverage range is 0.5625 to 0.725",
        "6001 / 6001 available grid-reference rows are scored",
        "maximum panel upper-bound hit rate is 0.12634408602150538",
        "250 / 6001 IVAPD rows are scored",
        "`blocked_predictive_distribution_only`",
        "Positive Venn-Abers validation requirements are 1 pass / 3 blocked",
        "Venn-Abers bundle main-eligible rows: 0",
        "not standalone scientific proof",
    ]
    for snippet in required_snippets:
        assert snippet in text
