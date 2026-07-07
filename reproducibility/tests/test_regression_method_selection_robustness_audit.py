import json
from pathlib import Path

from experiments.regression.scripts import (
    build_method_selection_robustness_audit as audit,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def cell(
    dataset_id: str,
    alpha: str,
    method: str,
    *,
    score: float,
    error: float,
    width: float,
    nominal: bool,
    near: bool = True,
) -> dict:
    return {
        "dataset_id": dataset_id,
        "alpha": alpha,
        "cp_method": method,
        "eligible_nominal_mean": nominal,
        "eligible_near_nominal_mean": near,
        "metrics": {
            "coverage_error_abs": {"mean": error},
            "interval_score": {"mean": score},
            "mean_width": {"mean": width},
        },
    }


def source_cells() -> list[dict]:
    rows = []
    for dataset_id in ["d1", "d2", "d3", "d4"]:
        rows.extend(
            [
                cell(
                    dataset_id,
                    "0.1",
                    "cqr",
                    score=1.0,
                    error=0.01,
                    width=0.5,
                    nominal=True,
                ),
                cell(
                    dataset_id,
                    "0.1",
                    "cv_plus",
                    score=2.0,
                    error=0.02,
                    width=0.6,
                    nominal=True,
                ),
                cell(
                    dataset_id,
                    "0.1",
                    "mondrian_abs",
                    score=3.0,
                    error=0.03,
                    width=0.7,
                    nominal=True,
                ),
            ]
        )
    rows.extend(
        [
            cell(
                "d5",
                "0.2",
                "cqr",
                score=5.0,
                error=0.05,
                width=2.0,
                nominal=False,
                near=True,
            ),
            cell(
                "d5",
                "0.2",
                "cv_plus",
                score=1.0,
                error=0.01,
                width=0.5,
                nominal=True,
            ),
            cell(
                "d5",
                "0.2",
                "mondrian_abs",
                score=2.0,
                error=0.02,
                width=0.6,
                nominal=True,
            ),
        ]
    )
    return rows


def write_sources(root: Path) -> tuple[Path, Path, Path, Path]:
    method_synthesis = root / "method_performance_synthesis.json"
    candidate_audit = root / "method_selection_candidate_audit.json"
    selection_protocol = root / "selection_multiplicity_protocol.json"
    final_boundary = root / "final_selection_claim_boundary_audit.json"
    write_json(
        method_synthesis,
        {
            "summary": {
                "overall_status": "method_performance_synthesis_descriptive_no_final_selection",
                "failed_check_count": 0,
                "completed_ledger_rows": 15,
            },
            "dataset_alpha_method_cells": source_cells(),
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
        },
    )
    write_json(
        selection_protocol,
        {
            "summary": {
                "overall_status": "selection_multiplicity_protocol_defined_no_final_selection",
                "can_support_final_method_selection": False,
                "final_selection_claim_status": "blocked",
            }
        },
    )
    write_json(
        final_boundary,
        {"summary": {"claim_status": "blocked", "failed_check_count": 0}},
    )
    return method_synthesis, candidate_audit, selection_protocol, final_boundary


def test_method_selection_robustness_audit_quantifies_primary_stability(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(audit, "MIN_COMMON_CELL_COUNT", 5)
    monkeypatch.setattr(audit, "MIN_BOOTSTRAP_REPLICATES", 20)
    sources = write_sources(tmp_path)

    payload = audit.build_payload(tmp_path, *sources, bootstrap_replicates=50)
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "method_selection_robustness_audit_ready_no_final_selection"
    )
    assert summary["candidate_primary_method"] == "cqr"
    assert summary["common_dataset_alpha_cell_count"] == 5
    assert summary["common_cell_selected_method"] == "cqr"
    assert summary["common_cell_winner_counts"] == {
        "cqr": 4,
        "cv_plus": 1,
    }
    assert summary["common_alpha_imbalance_status"] == "imbalanced_common_alpha_support"
    assert summary["common_alpha_max_cell_share"] == 0.8
    assert summary["alpha_stratum_selection_counts"] == {
        "cqr": 1,
        "cv_plus": 1,
    }
    assert summary["alpha_balanced_selected_method"] == "cv_plus"
    assert summary["alpha_balanced_primary_retained"] is False
    assert summary["leave_one_dataset_primary_retained_count"] == 5
    assert summary["leave_one_alpha_primary_retained_count"] == 1
    assert summary["bootstrap_replicates"] == 50
    assert summary["bootstrap_primary_selection_rate"] > 0.9
    assert summary["can_support_final_method_selection"] is False
    assert summary["claim_status"] == "selection_robustness_ready_no_final_selection"
    assert payload["alpha_balanced_selection"]["per_alpha"][0]["alpha"] == "0.1"


def test_method_selection_robustness_audit_fails_without_common_support(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(audit, "MIN_COMMON_CELL_COUNT", 99)
    monkeypatch.setattr(audit, "MIN_BOOTSTRAP_REPLICATES", 20)
    sources = write_sources(tmp_path)

    payload = audit.build_payload(tmp_path, *sources, bootstrap_replicates=50)

    assert (
        payload["summary"]["overall_status"]
        == "method_selection_robustness_audit_failed"
    )
    failed_ids = {row["check_id"] for row in payload["failed_checks"]}
    assert "common_cell_count_sufficient" in failed_ids
    assert "no_final_selection_claim" not in failed_ids
