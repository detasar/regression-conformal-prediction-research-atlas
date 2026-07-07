import json
import pytest

from experiments.regression.scripts import compare_regression_sensitivity_ledgers as compare


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_sensitivity_comparison_filters_seeds_and_pairs_rows(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    sensitivity = tmp_path / "sensitivity.jsonl"
    write_jsonl(
        baseline,
        [
            {
                "status": "completed",
                "dataset_id": "toy",
                "model_id": "ridge",
                "model_params": {"alpha": 1.0},
                "cp_method": "split_abs",
                "alpha": 0.1,
                "seed": 42,
                "coverage": 0.85,
                "mean_width": 10.0,
                "interval_score": 12.0,
                "coverage_gap": 0.2,
            },
            {
                "status": "completed",
                "dataset_id": "toy",
                "model_id": "ridge",
                "model_params": {"alpha": 1.0},
                "cp_method": "split_abs",
                "alpha": 0.1,
                "seed": 11,
                "coverage": 1.0,
                "mean_width": 100.0,
                "interval_score": 100.0,
                "coverage_gap": 0.0,
            },
        ],
    )
    write_jsonl(
        sensitivity,
        [
            {
                "status": "completed",
                "dataset_id": "toy",
                "model_id": "ridge",
                "model_params": {"alpha": 1.0},
                "cp_method_id": "split_abs",
                "cp_method": "split_abs",
                "alpha": 0.1,
                "seed": 42,
                "coverage": 0.9,
                "mean_width": 11.0,
                "interval_score": 11.5,
                "coverage_gap": 0.1,
            }
        ],
    )

    payload = compare.build_payload(
        root=tmp_path,
        baseline_ledger=baseline,
        sensitivity_ledger=sensitivity,
        out_dir=tmp_path / "out",
        baseline_label="baseline",
        sensitivity_label="duplicate_cluster",
        baseline_seeds={42},
        sensitivity_seeds={42},
    )

    assert payload["baseline"]["completed_rows"] == 1
    assert payload["sensitivity"]["completed_rows"] == 1
    assert payload["summary"]["paired_rows"] == 1
    assert payload["summary"]["nominal_status_change_count"] == 1
    row = payload["largest_abs_coverage_delta_rows"][0]
    assert row["metric_deltas"]["coverage"]["delta_sensitivity_minus_baseline"] == 0.05
    assert row["metric_deltas"]["mean_width"]["delta_sensitivity_minus_baseline"] == 1.0


def test_sensitivity_comparison_rejects_seed_imbalanced_pairs(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    sensitivity = tmp_path / "sensitivity.jsonl"
    shared = {
        "status": "completed",
        "dataset_id": "toy",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "cp_method": "split_abs",
        "alpha": 0.1,
        "coverage": 0.9,
    }
    write_jsonl(
        baseline,
        [
            {**shared, "seed": 42},
            {**shared, "seed": 71},
        ],
    )
    write_jsonl(sensitivity, [{**shared, "seed": 42}])

    with pytest.raises(ValueError, match="Seed-imbalanced"):
        compare.build_payload(
            root=tmp_path,
            baseline_ledger=baseline,
            sensitivity_ledger=sensitivity,
            out_dir=tmp_path / "out",
            baseline_label="baseline",
            sensitivity_label="duplicate_cluster",
            baseline_seeds={42, 71},
            sensitivity_seeds={42, 71},
        )


def test_sensitivity_comparison_pairs_legacy_model_params_key(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    sensitivity = tmp_path / "sensitivity.jsonl"
    write_jsonl(
        baseline,
        [
            {
                "status": "completed",
                "dataset_id": "toy",
                "model_id": "ridge",
                "model_params_key": "{\"alpha\":1.0}",
                "cp_method": "split_abs",
                "alpha": 0.1,
                "seed": 42,
                "coverage": 0.9,
            }
        ],
    )
    write_jsonl(
        sensitivity,
        [
            {
                "status": "completed",
                "dataset_id": "toy",
                "model_id": "ridge",
                "model_params": {"alpha": 1.0},
                "cp_method": "split_abs",
                "alpha": 0.1,
                "seed": 42,
                "coverage": 0.91,
            }
        ],
    )

    payload = compare.build_payload(
        root=tmp_path,
        baseline_ledger=baseline,
        sensitivity_ledger=sensitivity,
        out_dir=tmp_path / "out",
        baseline_label="baseline",
        sensitivity_label="duplicate_cluster",
        baseline_seeds={42},
        sensitivity_seeds={42},
    )

    assert payload["summary"]["paired_rows"] == 1
    assert payload["summary"]["seed_imbalanced_paired_rows"] == 0


def test_sensitivity_comparison_filters_datasets_before_pairing(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    sensitivity = tmp_path / "sensitivity.jsonl"
    common = {
        "status": "completed",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "cp_method": "split_abs",
        "alpha": 0.1,
        "seed": 42,
        "coverage": 0.9,
    }
    write_jsonl(
        baseline,
        [
            {**common, "dataset_id": "raw"},
            {**common, "dataset_id": "dedup"},
        ],
    )
    write_jsonl(sensitivity, [{**common, "dataset_id": "raw"}])

    payload = compare.build_payload(
        root=tmp_path,
        baseline_ledger=baseline,
        sensitivity_ledger=sensitivity,
        out_dir=tmp_path / "out",
        baseline_label="baseline",
        sensitivity_label="duplicate_cluster",
        baseline_seeds={42},
        sensitivity_seeds={42},
        baseline_datasets={"raw"},
        sensitivity_datasets={"raw"},
    )

    assert payload["baseline"]["completed_rows"] == 1
    assert payload["baseline"]["dataset_filter"] == ["raw"]
    assert payload["summary"]["paired_rows"] == 1
    assert payload["summary"]["baseline_only_rows"] == 0


def test_sensitivity_comparison_pairs_renamed_methods_with_filters(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    sensitivity = tmp_path / "sensitivity.jsonl"
    common = {
        "status": "completed",
        "dataset_id": "toy",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "alpha": 0.1,
        "seed": 42,
        "coverage": 0.9,
        "mean_width": 2.0,
        "interval_score": 2.5,
    }
    write_jsonl(
        baseline,
        [
            {**common, "cp_method": "cv_plus"},
            {**common, "cp_method": "split_abs", "coverage": 0.5},
        ],
    )
    write_jsonl(
        sensitivity,
        [
            {**common, "cp_method_id": "cv_plus_grouped", "coverage": 0.91},
            {**common, "cp_method_id": "cv_minmax_grouped", "coverage": 0.92},
        ],
    )

    payload = compare.build_payload(
        root=tmp_path,
        baseline_ledger=baseline,
        sensitivity_ledger=sensitivity,
        out_dir=tmp_path / "out",
        baseline_label="ordinary",
        sensitivity_label="grouped",
        baseline_seeds={42},
        sensitivity_seeds={42},
        baseline_methods={"cv_plus"},
        sensitivity_methods={"cv_plus_grouped"},
        method_pairs=[("cv_plus", "cv_plus_grouped")],
    )

    assert payload["baseline"]["completed_rows"] == 1
    assert payload["sensitivity"]["completed_rows"] == 1
    assert payload["summary"]["paired_rows"] == 1
    row = payload["largest_abs_coverage_delta_rows"][0]
    assert row["cp_method"] == "cv_plus->cv_plus_grouped"
    assert row["baseline_source_cp_methods"] == ["cv_plus"]
    assert row["sensitivity_source_cp_methods"] == ["cv_plus_grouped"]
    assert payload["method_pairs"] == [
        {
            "baseline_method": "cv_plus",
            "sensitivity_method": "cv_plus_grouped",
            "comparison_method": "cv_plus->cv_plus_grouped",
        }
    ]
