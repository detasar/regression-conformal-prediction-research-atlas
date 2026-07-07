import json
from pathlib import Path

from experiments.regression.scripts import (
    build_paired_duplicate_sensitivity_audit as audit,
)
from experiments.regression.scripts import audit_methodology_sanity as methodology


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_paired_duplicate_sensitivity_compares_matching_grid_rows(tmp_path):
    report_dir = tmp_path / "experiments/regression/reports/toy_report"
    write_json(
        report_dir / "pilot_summary.json",
        {
            "rows": [
                {
                    "dataset_id": "toy_raw",
                    "model_id": "ridge",
                    "model_params_key": "{}",
                    "cp_method": "split_abs",
                    "alpha": 0.1,
                    "coverage_mean": 0.88,
                    "coverage_error_abs_mean": 0.02,
                    "mean_width_mean": 1.0,
                    "normalized_mean_width_mean": 1.0,
                    "interval_score_mean": 2.0,
                    "coverage_gap_mean": 0.10,
                    "width_gap_mean": 0.20,
                    "lower_miss_rate_mean": 0.07,
                    "upper_miss_rate_mean": 0.05,
                    "coverage_count": 2,
                },
                {
                    "dataset_id": "toy_dedup",
                    "model_id": "ridge",
                    "model_params_key": "{}",
                    "cp_method": "split_abs",
                    "alpha": 0.1,
                    "coverage_mean": 0.92,
                    "coverage_error_abs_mean": 0.02,
                    "mean_width_mean": 1.2,
                    "normalized_mean_width_mean": 1.1,
                    "interval_score_mean": 2.4,
                    "coverage_gap_mean": 0.05,
                    "width_gap_mean": 0.30,
                    "lower_miss_rate_mean": 0.04,
                    "upper_miss_rate_mean": 0.04,
                    "coverage_count": 2,
                },
            ]
        },
    )
    backlog_row = {
        "dataset_id": "toy_raw",
        "paired_dedup_variant_dataset_id": "toy_dedup",
        "report_id": "report:toy_report",
        "report_dir": "experiments/regression/reports/toy_report",
        "config_path": "experiments/regression/configs/toy.yaml",
        "total_duplicate_signature_pair_overlaps": 3,
        "severity": "low",
    }

    result = audit.compare_dataset(root=tmp_path, backlog_row=backlog_row)

    assert result["paired_comparison_rows"] == 1
    assert result["raw_nominal_count"] == 0
    assert result["dedup_nominal_count"] == 1
    assert result["nominal_status_change_count"] == 1
    row = result["largest_abs_coverage_delta_rows"][0]
    assert row["metric_deltas"]["coverage_mean"]["delta_dedup_minus_raw"] == 0.04
    assert row["metric_deltas"]["mean_width_mean"]["delta_dedup_minus_raw"] == 0.2


def test_build_payload_uses_only_backlog_rows_with_paired_dedup_variant(tmp_path):
    report_dir = tmp_path / "experiments/regression/reports/toy_report"
    write_json(
        report_dir / "pilot_summary.json",
        {
            "rows": [
                {
                    "dataset_id": "toy_raw",
                    "model_id": "ridge",
                    "model_params_key": "{}",
                    "cp_method": "split_abs",
                    "alpha": 0.1,
                    "coverage_mean": 0.90,
                    "interval_score_mean": 2.0,
                },
                {
                    "dataset_id": "toy_raw_dedup",
                    "model_id": "ridge",
                    "model_params_key": "{}",
                    "cp_method": "split_abs",
                    "alpha": 0.1,
                    "coverage_mean": 0.91,
                    "interval_score_mean": 2.2,
                },
            ]
        },
    )
    backlog_path = tmp_path / "duplicate_split_caveat_backlog.json"
    write_json(
        backlog_path,
        {
            "rows": [
                {
                    "dataset_id": "toy_raw",
                    "paired_dedup_variant_available": True,
                    "paired_dedup_variant_dataset_id": "toy_raw_dedup",
                    "report_id": "report:toy_report",
                    "report_dir": "experiments/regression/reports/toy_report",
                    "config_path": "experiments/regression/configs/toy.yaml",
                },
                {
                    "dataset_id": "toy_unpaired",
                    "paired_dedup_variant_available": False,
                    "paired_dedup_variant_dataset_id": None,
                    "report_id": "report:other",
                    "report_dir": "experiments/regression/reports/other",
                },
            ]
        },
    )

    payload = audit.build_payload(tmp_path, backlog_path)

    assert payload["schema"] == audit.SCHEMA
    assert payload["summary"]["paired_dataset_count"] == 1
    assert payload["summary"]["paired_comparison_rows"] == 1
    assert payload["datasets"][0]["raw_dataset_id"] == "toy_raw"


def test_methodology_status_accepts_synchronized_paired_duplicate_audit(tmp_path):
    report_dir = tmp_path / "experiments/regression/reports/toy_report"
    write_json(
        report_dir / "pilot_summary.json",
        {
            "rows": [
                {
                    "dataset_id": "toy_raw",
                    "model_id": "ridge",
                    "model_params_key": "{}",
                    "cp_method": "split_abs",
                    "alpha": 0.1,
                    "coverage_mean": 0.90,
                    "interval_score_mean": 2.0,
                },
                {
                    "dataset_id": "toy_raw_dedup",
                    "model_id": "ridge",
                    "model_params_key": "{}",
                    "cp_method": "split_abs",
                    "alpha": 0.1,
                    "coverage_mean": 0.91,
                    "interval_score_mean": 2.2,
                },
            ]
        },
    )
    backlog_path = tmp_path / methodology.DUPLICATE_SPLIT_CAVEAT_BACKLOG
    write_json(
        backlog_path,
        {
            "rows": [
                {
                    "dataset_id": "toy_raw",
                    "paired_dedup_variant_available": True,
                    "paired_dedup_variant_dataset_id": "toy_raw_dedup",
                    "report_id": "report:toy_report",
                    "report_dir": "experiments/regression/reports/toy_report",
                    "config_path": "experiments/regression/configs/toy.yaml",
                }
            ]
        },
    )
    audit_path = tmp_path / methodology.PAIRED_DUPLICATE_SENSITIVITY_AUDIT
    write_json(audit_path, audit.build_payload(tmp_path, backlog_path))

    status = methodology.paired_duplicate_sensitivity_audit_status(tmp_path)

    assert status["synchronized"] is True
    assert status["actual_paired_datasets"] == ["toy_raw"]
    assert status["paired_comparison_rows"] == 1


def test_rel_accepts_external_probe_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_path = repo_root / "experiments/regression/reports/paired.json"
    external_path = tmp_path / "scratch/paired.json"

    assert audit.rel(repo_path, repo_root) == "experiments/regression/reports/paired.json"
    assert audit.rel(external_path, repo_root) == str(external_path)
