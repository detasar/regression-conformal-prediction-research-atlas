import json
from pathlib import Path

from experiments.regression.scripts import (
    build_method_selection_candidate_audit as audit,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def method_row(method: str, *, frontier: int, support: str = "broad_support") -> dict:
    return {
        "cp_method": method,
        "support_class": support,
        "frontier_cell_count": frontier,
        "dataset_count": 12,
        "dataset_alpha_cell_count": 12,
        "balanced_cell_nominal_mean_hit_rate": 0.8,
        "balanced_coverage_error_abs_mean": 0.02,
        "balanced_interval_score_mean": 10.0,
    }


def cell(dataset_id: str, method: str, coverage_error: float, score: float) -> dict:
    return {
        "dataset_id": dataset_id,
        "alpha": "0.1",
        "cp_method": method,
        "metrics": {
            "coverage_error_abs": {"mean": coverage_error},
            "interval_score": {"mean": score},
            "mean_width": {"mean": score / 2.0},
        },
    }


def source_payload() -> dict:
    return {
        "summary": {
            "overall_status": "method_performance_synthesis_descriptive_no_final_selection",
            "failed_check_count": 0,
            "completed_ledger_rows": 12,
            "dataset_count": 3,
            "dataset_alpha_cell_count": 3,
            "method_count": 4,
        },
        "method_rows": [
            method_row("cqr", frontier=3),
            method_row("cv_plus", frontier=2),
            method_row("mondrian_abs", frontier=2),
            method_row("venn_abers_quantile", frontier=0),
        ],
        "dataset_alpha_method_cells": [
            cell("d1", "cqr", 0.01, 1.0),
            cell("d1", "cv_plus", 0.02, 2.0),
            cell("d1", "mondrian_abs", 0.03, 3.0),
            cell("d2", "cqr", 0.03, 2.0),
            cell("d2", "cv_plus", 0.02, 3.0),
            cell("d2", "mondrian_abs", 0.01, 4.0),
            cell("d3", "cqr", 0.01, 1.5),
            cell("d3", "cv_plus", 0.04, 2.5),
            cell("d3", "mondrian_abs", 0.04, 3.5),
        ],
    }


def write_supporting_sources(root: Path) -> tuple[Path, Path, Path, Path]:
    method_synthesis = root / "method_performance_synthesis.json"
    selection_protocol = root / "selection_multiplicity_protocol.json"
    final_boundary = root / "final_selection_claim_boundary_audit.json"
    venn_readiness = root / "venn_abers_validation_readiness_audit.json"
    write_json(method_synthesis, source_payload())
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
    write_json(
        venn_readiness,
        {
            "summary": {
                "overall_status": "venn_abers_validation_blocked_with_negative_evidence",
                "can_support_venn_abers_regression_validation": False,
            }
        },
    )
    return method_synthesis, selection_protocol, final_boundary, venn_readiness


def test_method_selection_candidate_audit_builds_shortlist_and_paired_diagnostics(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(audit, "SHORTLIST_FRONTIER_CELL_MIN", 2)
    sources = write_supporting_sources(tmp_path)

    payload = audit.build_payload(tmp_path, *sources)
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "method_selection_candidate_audit_ready_no_final_selection"
    )
    assert summary["failed_check_count"] == 0
    assert summary["primary_candidate_method"] == "cqr"
    assert summary["shortlist_method_count"] == 3
    assert summary["paired_comparison_count"] == 2
    assert summary["can_support_final_method_selection"] is False
    assert summary["claim_status"] == "candidate_shortlist_ready_no_final_selection"
    assert summary["venn_abers_excluded_count"] == 1

    by_pair = {row["comparator_method"]: row for row in payload["paired_comparisons"]}
    cv_score = next(
        row
        for row in by_pair["cv_plus"]["metric_comparisons"]
        if row["metric"] == "interval_score"
    )
    assert cv_score["primary_win_count"] == 3
    assert cv_score["comparator_win_count"] == 0
    assert cv_score["exact_sign_test_two_sided_p"] == 0.25


def test_method_selection_candidate_audit_fails_without_shortlist(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(audit, "SHORTLIST_FRONTIER_CELL_MIN", 99)
    sources = write_supporting_sources(tmp_path)

    payload = audit.build_payload(tmp_path, *sources)

    assert (
        payload["summary"]["overall_status"]
        == "method_selection_candidate_audit_failed"
    )
    failed_ids = {row["check_id"] for row in payload["failed_checks"]}
    assert "shortlist_has_minimum_candidates" in failed_ids
    assert "no_final_selection_claim" not in failed_ids
