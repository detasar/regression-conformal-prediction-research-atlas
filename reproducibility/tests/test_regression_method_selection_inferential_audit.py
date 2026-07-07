import json
from pathlib import Path

from experiments.regression.scripts import (
    build_method_selection_inferential_audit as audit,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def scores(cqr: float, cv_plus: float, mondrian: float) -> dict:
    return {
        "cqr": {
            "coverage_error_abs": 0.01,
            "interval_score": cqr,
            "mean_width": cqr / 2,
        },
        "cv_plus": {
            "coverage_error_abs": 0.02,
            "interval_score": cv_plus,
            "mean_width": cv_plus / 2,
        },
        "mondrian_abs": {
            "coverage_error_abs": 0.03,
            "interval_score": mondrian,
            "mean_width": mondrian / 2,
        },
    }


def validation_cells(count: int) -> list[dict]:
    rows = []
    for index in range(count):
        rows.append(
            {
                "dataset_id": f"d{index % 5}",
                "alpha": str([0.01, 0.05, 0.1, 0.15, 0.2][index % 5]),
                "seed": 100 + index,
                "diagnostic_winner": "cqr" if index < max(1, count - 2) else "mondrian_abs",
                "scores": scores(1.0 + index / 100, 2.0 + index / 100, 3.0 + index / 100),
            }
        )
    return rows


def write_sources(root: Path, *, validation_count: int = 25) -> tuple[Path, ...]:
    method_synthesis = root / "method_performance_synthesis.json"
    candidate_audit = root / "method_selection_candidate_audit.json"
    robustness = root / "method_selection_robustness_audit.json"
    validation_results = root / "method_selection_post_selection_validation_results.json"
    main_candidate_results = root / "main_result_candidate_bundle_results.json"
    selection_protocol = root / "selection_multiplicity_protocol.json"
    final_boundary = root / "final_selection_claim_boundary_audit.json"
    write_json(
        method_synthesis,
        {
            "summary": {
                "overall_status": "method_performance_synthesis_descriptive_no_final_selection",
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        candidate_audit,
        {
            "summary": {
                "overall_status": "method_selection_candidate_audit_ready_no_final_selection",
                "failed_check_count": 0,
                "primary_candidate_method": "cqr",
                "can_support_final_method_selection": False,
            },
            "shortlist_methods": [
                {"cp_method": "cqr"},
                {"cp_method": "cv_plus"},
                {"cp_method": "mondrian_abs"},
            ],
            "paired_comparisons": [
                {
                    "primary_method": "cqr",
                    "comparator_method": "cv_plus",
                    "shared_dataset_alpha_cell_count": 40,
                    "metric_comparisons": [
                        {
                            "metric": "interval_score",
                            "orientation": "lower_is_better",
                            "shared_cell_count": 40,
                            "primary_win_count": 35,
                            "comparator_win_count": 5,
                            "tie_count": 0,
                            "primary_non_tie_win_rate": 0.875,
                            "exact_sign_test_two_sided_p": 0.0001,
                            "difference_primary_minus_comparator": {
                                "count": 40,
                                "mean": -1.0,
                                "median": -1.0,
                                "std": 0.5,
                                "ci95": {"low": -1.2, "high": -0.8},
                            },
                        }
                    ],
                },
                {
                    "primary_method": "cqr",
                    "comparator_method": "mondrian_abs",
                    "shared_dataset_alpha_cell_count": 40,
                    "metric_comparisons": [
                        {
                            "metric": "interval_score",
                            "orientation": "lower_is_better",
                            "shared_cell_count": 40,
                            "primary_win_count": 34,
                            "comparator_win_count": 6,
                            "tie_count": 0,
                            "primary_non_tie_win_rate": 0.85,
                            "exact_sign_test_two_sided_p": 0.0002,
                            "difference_primary_minus_comparator": {
                                "count": 40,
                                "mean": -2.0,
                                "median": -2.0,
                                "std": 1.0,
                                "ci95": {"low": -2.3, "high": -1.7},
                            },
                        }
                    ],
                },
            ],
        },
    )
    write_json(
        robustness,
        {
            "summary": {
                "overall_status": "method_selection_robustness_audit_ready_no_final_selection",
                "failed_check_count": 0,
                "candidate_primary_method": "cqr",
                "candidate_methods": ["cqr", "cv_plus", "mondrian_abs"],
                "common_cell_primary_win_count": 30,
                "common_dataset_alpha_cell_count": 40,
                "bootstrap_primary_selection_count": 95,
                "bootstrap_replicates": 100,
                "leave_one_dataset_primary_retained_count": 10,
                "leave_one_dataset_count": 10,
                "leave_one_alpha_primary_retained_count": 5,
                "leave_one_alpha_count": 5,
            }
        },
    )
    write_json(
        validation_results,
        {
            "summary": {
                "overall_status": "method_selection_post_selection_validation_results_ready_no_final_selection",
                "failed_check_count": 0,
                "common_dataset_alpha_cell_count": validation_count,
                "diagnostic_winner_counts": {
                    "cqr": max(1, validation_count - 2),
                    "mondrian_abs": min(2, validation_count),
                },
            },
            "diagnostic_selection": {"per_cell": validation_cells(validation_count)},
        },
    )
    write_json(
        main_candidate_results,
        {
            "summary": {
                "overall_status": "main_result_candidate_bundle_results_completed_no_promotions",
                "failed_check_count": 0,
                "complete_matched_cell_count": 75,
                "diagnostic_winner_counts": {"cqr": 50, "cv_plus": 9, "mondrian_abs": 16},
            }
        },
    )
    write_json(
        selection_protocol,
        {
            "summary": {
                "can_support_final_method_selection": False,
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        final_boundary,
        {"summary": {"claim_status": "blocked", "failed_check_count": 0}},
    )
    return (
        method_synthesis,
        candidate_audit,
        robustness,
        validation_results,
        main_candidate_results,
        selection_protocol,
        final_boundary,
    )


def test_method_selection_inferential_audit_records_intervals_without_final_claim(
    tmp_path,
):
    sources = write_sources(tmp_path)

    payload = audit.build_payload(tmp_path, *sources)
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "method_selection_inferential_audit_ready_no_final_selection"
    )
    assert summary["primary_candidate_method"] == "cqr"
    assert summary["candidate_pairwise_comparison_count"] == 2
    assert summary["candidate_min_shared_pairwise_cell_count"] == 40
    assert summary["bootstrap_primary_selection_rate"] == 0.95
    assert summary["post_selection_validation_primary_win_rate"] == 23 / 25
    assert summary["can_support_final_method_selection"] is False
    assert (
        summary["claim_status"]
        == "inferential_method_selection_evidence_ready_no_final_selection"
    )
    assert payload["winner_rate_intervals"][
        "robustness_bootstrap_primary_selection_rate"
    ]["ci95"]["low"] < 0.95
    cv_pair = payload["post_selection_validation_pairwise_diagnostics"][0]
    interval_score = next(
        row for row in cv_pair["metric_comparisons"] if row["metric"] == "interval_score"
    )
    assert interval_score["primary_win_count"] == 25
    assert interval_score["comparator_win_count"] == 0
    assert interval_score["difference_primary_minus_comparator"][
        "paired_standardized_effect_size"
    ] < 0


def test_method_selection_inferential_audit_fails_when_validation_surface_is_small(
    tmp_path,
):
    sources = write_sources(tmp_path, validation_count=5)

    payload = audit.build_payload(tmp_path, *sources)

    assert payload["summary"]["overall_status"] == "method_selection_inferential_audit_failed"
    failed_ids = {row["check_id"] for row in payload["failed_checks"]}
    assert "post_selection_validation_ready" in failed_ids
    assert payload["summary"]["can_support_final_method_selection"] is False
