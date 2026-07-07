import json

from experiments.regression.scripts.benchmark_venn_abers_quantile_bridge import (
    main,
    render_markdown,
    run_benchmark,
)


def test_venn_abers_bridge_benchmark_payload_has_panel_comparisons():
    payload = run_benchmark(alpha=0.2, ivar_m=1)

    assert payload["benchmark_id"] == "venn_abers_quantile_bridge_vs_grid_v1"
    assert payload["method_under_test"] == "venn_abers_quantile"
    assert payload["reference_method"] == "venn_abers_quantile_grid"
    assert payload["summary"]["panel_count"] == 3
    assert payload["summary"]["max_abs_radius_delta"] >= 0.0
    assert payload["summary"]["mean_bridge_width"] < payload["summary"]["mean_grid_width"]
    for row in payload["rows"]:
        assert len(row["bridge_radii"]) == row["n_test"]
        assert len(row["grid_radii"]) == row["n_test"]
        assert row["score_grid_size"] == 17
        assert row["bridge_metrics"]["mean_width"] >= 0.0
        assert row["grid_metrics"]["mean_width"] >= 0.0


def test_venn_abers_bridge_benchmark_writes_artifacts(tmp_path, monkeypatch):
    out_dir = tmp_path / "benchmark"
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark_venn_abers_quantile_bridge.py",
            "--out-dir",
            str(out_dir),
            "--alpha",
            "0.2",
            "--ivar-m",
            "1",
        ],
    )

    main()

    payload = json.loads((out_dir / "benchmark.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "benchmark.md").read_text(encoding="utf-8")
    assert payload["summary"]["panel_count"] == 3
    assert "Venn-Abers Quantile Bridge Benchmark" in markdown
    assert render_markdown(payload) == markdown
