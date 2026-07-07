import json
from collections import defaultdict

import numpy as np

from experiments.regression.scripts import (
    build_bounded_support_posthandling_validation as validation,
)


def test_posthandling_stats_compute_coverage_score_and_support_counts():
    stats = validation.empty_stats()

    validation.update_stats(
        stats,
        y_true=np.asarray([0.0, 5.0, 10.0]),
        lower=np.asarray([-1.0, 4.0, 9.0]),
        upper=np.asarray([1.0, 6.0, 11.0]),
        alpha=0.1,
        groups=np.asarray(["a", "a", "b"]),
        natural_lower=0.0,
        natural_upper=10.0,
    )
    result = validation.finalize_stats(stats)

    assert result["coverage"] == 1.0
    assert result["mean_width"] == 2.0
    assert result["interval_score"] == 2.0
    assert result["lower_below_natural_count"] == 1
    assert result["upper_above_natural_count"] == 1
    assert result["coverage_by_group"]["a"]["coverage"] == 1.0
    assert result["coverage_by_group"]["b"]["mean_width"] == 2.0


def test_posthandling_stats_track_abstention_denominator():
    stats = validation.empty_stats()

    validation.update_stats(
        stats,
        y_true=np.asarray([5.0]),
        lower=np.asarray([4.0]),
        upper=np.asarray([6.0]),
        alpha=0.1,
        groups=np.asarray(["kept"]),
        natural_lower=0.0,
        natural_upper=10.0,
        abstained_count=3,
    )
    result = validation.finalize_stats(stats)

    assert result["interval_count"] == 4
    assert result["evaluable_interval_count"] == 1
    assert result["abstention_rate"] == 0.75
    assert result["coverage"] == 1.0


def test_posthandling_stats_record_interval_score_overflow_without_infinity():
    stats = validation.empty_stats()

    validation.update_stats(
        stats,
        y_true=np.asarray([1.0e308]),
        lower=np.asarray([0.0]),
        upper=np.asarray([1.0]),
        alpha=0.01,
        groups=np.asarray(["extreme"]),
        natural_lower=0.0,
        natural_upper=None,
    )
    result = validation.finalize_stats(stats)

    assert result["coverage"] == 0.0
    assert result["interval_score"] is None
    assert result["interval_score_sum"] is None
    assert result["interval_score_nonfinite_count"] == 1
    assert result["interval_score_sum_overflow_count"] == 0


def test_posthandling_loads_legacy_prediction_bundle_with_explicit_caveat(tmp_path):
    artifact_id = "abcdef123456"
    artifact_dir = validation.prediction_artifact_dir(tmp_path, artifact_id)
    artifact_dir.mkdir(parents=True)
    arrays = {
        "y_train": np.asarray([1.0]),
        "y_cal": np.asarray([2.0]),
        "y_test": np.asarray([3.0]),
        "yhat_train": np.asarray([1.1]),
        "yhat_cal": np.asarray([2.1]),
        "yhat_test": np.asarray([3.1]),
        "groups_cal": np.asarray(["g"]),
        "groups_test": np.asarray(["g"]),
        "X_train": np.asarray([[1.0]]),
        "X_cal": np.asarray([[2.0]]),
        "X_test": np.asarray([[3.0]]),
        "scale_cal": np.asarray([1.0]),
        "scale_test": np.asarray([1.0]),
    }
    np.savez_compressed(artifact_dir / "bundle.npz", **arrays)
    (artifact_dir / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_id": artifact_id,
                "fit_seconds": 0.5,
                "target_transform": "identity",
            }
        ),
        encoding="utf-8",
    )

    bundle, reason = validation.load_prediction_bundle_for_posthandling(
        tmp_path,
        artifact_id,
    )

    assert bundle is not None
    assert bundle.cache_status == (
        "legacy_hit_missing_data_provenance_and_code_provenance"
    )
    assert reason == "missing_data_provenance_and_code_provenance"
    assert bundle.groups_test.tolist() == ["g"]


def test_posthandling_state_record_roundtrip_merges_sufficient_stats(tmp_path):
    run_stats = validation.empty_stats()
    validation.update_stats(
        run_stats,
        y_true=np.asarray([1.0, 5.0]),
        lower=np.asarray([0.0, 6.0]),
        upper=np.asarray([2.0, 8.0]),
        alpha=0.1,
        groups=np.asarray(["a", "b"]),
        natural_lower=0.0,
        natural_upper=10.0,
    )
    record = {
        "row_key": "run-1|split_abs|artifact-1",
        "status": "validated",
        "run_id": "run-1",
        "cp_method": "split_abs",
        "model_id": "ridge",
        "prediction_artifact": "artifact-1",
        "y_out_of_natural_domain_count": 0,
        "policy_stats": {"raw_unclipped": run_stats},
    }
    path = validation.state_path_for(tmp_path, "bundle-a")
    with path.open("a", encoding="utf-8") as handle:
        validation.append_state_record(
            handle,
            record,
            appended_count=1,
            fsync_every=0,
        )

    loaded = validation.load_state_records(path)
    policy_stats = {
        "raw_unclipped": validation.empty_stats(),
        "clip_to_natural_bounds": validation.empty_stats(),
        "abstain_if_raw_out_of_domain": validation.empty_stats(),
    }
    method_policy_stats = defaultdict(
        lambda: {
            "raw_unclipped": validation.empty_stats(),
            "clip_to_natural_bounds": validation.empty_stats(),
            "abstain_if_raw_out_of_domain": validation.empty_stats(),
        }
    )
    reconstructed, y_out = validation.merge_state_record(
        loaded["run-1|split_abs|artifact-1"],
        policy_stats=policy_stats,
        method_policy_stats=method_policy_stats,
        failures=[],
    )
    result = validation.finalize_stats(policy_stats["raw_unclipped"])
    method_result = validation.finalize_stats(
        method_policy_stats["split_abs"]["raw_unclipped"]
    )

    assert reconstructed == 1
    assert y_out == 0
    assert result["coverage"] == 0.5
    assert result["lower_miss_count"] == 1
    assert method_result["coverage_by_group"]["b"]["coverage"] == 0.0
