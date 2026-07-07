import json

from experiments.regression.scripts.benchmark_ivapd_threshold_grid import (
    main,
    render_markdown,
    run_benchmark,
)


def test_ivapd_benchmark_payload_scores_distribution_panels():
    payload = run_benchmark(alpha=0.2)

    assert payload["benchmark_id"] == "ivapd_threshold_grid_distribution_scoring_v1"
    assert payload["method_under_test"] == "ivapd_threshold_grid"
    assert payload["baseline_method"] == "point_prediction_step_cdf"
    assert payload["summary"]["panel_count"] == 3
    assert payload["summary"]["test_case_count"] == 9
    assert payload["summary"]["mean_ivapd_midpoint_crps"] >= 0.0
    assert payload["summary"]["mean_point_step_crps"] >= 0.0
    for panel in payload["rows"]:
        assert panel["threshold_grid_size"] >= 2
        assert len(panel["rows"]) == panel["n_test"]
        assert panel["max_cdf_band_width"] >= panel["mean_cdf_band_width"] >= 0.0


def test_ivapd_benchmark_writes_artifacts(tmp_path, monkeypatch):
    out_dir = tmp_path / "ivapd"
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark_ivapd_threshold_grid.py",
            "--out-dir",
            str(out_dir),
            "--alpha",
            "0.2",
        ],
    )

    main()

    payload = json.loads((out_dir / "benchmark.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "benchmark.md").read_text(encoding="utf-8")
    assert payload["summary"]["panel_count"] == 3
    assert "IVAPD Threshold-Grid Benchmark" in markdown
    assert render_markdown(payload) == markdown
