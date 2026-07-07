"""Benchmark the Venn-Abers quantile runner bridge against the grid reference."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from cpfi.regression.conformal import (
    RegressionCPResult,
    venn_abers_quantile_grid_interval,
    venn_abers_quantile_interval,
)
from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from cpfi.regression.metrics import compute_interval_metrics


@dataclass(frozen=True)
class SyntheticPanel:
    panel_id: str
    notes: str
    y_cal: np.ndarray
    yhat_cal: np.ndarray
    yhat_test: np.ndarray
    y_test: np.ndarray
    residual_quantile_cal: np.ndarray
    residual_quantile_test: np.ndarray
    score_grid: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        default="experiments/regression/reports/venn_abers_quantile_bridge_benchmark",
        help="Directory for benchmark JSON/MD artifacts.",
    )
    parser.add_argument("--alpha", type=float, default=0.2)
    parser.add_argument("--ivar-m", type=int, default=1)
    return parser.parse_args()


def synthetic_panels() -> list[SyntheticPanel]:
    grid = np.round(np.linspace(0.0, 4.0, 17), 2)
    return [
        SyntheticPanel(
            panel_id="monotone_residual_scale",
            notes="Residual scores increase with the base residual-quantile score.",
            y_cal=np.array([0.1, 0.3, 0.5, 0.9, 1.1, 1.5, 2.0]),
            yhat_cal=np.zeros(7),
            yhat_test=np.array([10.0, 20.0, 30.0]),
            y_test=np.array([10.4, 21.0, 31.9]),
            residual_quantile_cal=np.array([0.2, 0.4, 0.7, 1.0, 1.4, 1.8, 2.2]),
            residual_quantile_test=np.array([0.6, 1.2, 2.0]),
            score_grid=grid,
        ),
        SyntheticPanel(
            panel_id="nonmonotone_tail_bump",
            notes="A high middle residual forces isotonic block merging.",
            y_cal=np.array([0.2, 1.8, 0.9, 1.2, 1.4, 2.4, 2.7]),
            yhat_cal=np.zeros(7),
            yhat_test=np.array([5.0, 7.5, 11.0]),
            y_test=np.array([5.5, 9.1, 13.5]),
            residual_quantile_cal=np.array([0.2, 0.8, 1.0, 1.3, 1.8, 2.2, 2.8]),
            residual_quantile_test=np.array([0.9, 1.6, 2.5]),
            score_grid=grid,
        ),
        SyntheticPanel(
            panel_id="flat_quantile_ties",
            notes="Repeated quantile scores test tie handling in both calibrators.",
            y_cal=np.array([0.1, 0.4, 0.6, 1.0, 1.3, 1.5, 1.9, 2.2]),
            yhat_cal=np.zeros(8),
            yhat_test=np.array([-2.0, 0.0, 3.0]),
            y_test=np.array([-1.8, 1.1, 4.8]),
            residual_quantile_cal=np.array([0.5, 0.5, 0.8, 0.8, 1.4, 1.4, 2.0, 2.0]),
            residual_quantile_test=np.array([0.5, 1.4, 2.0]),
            score_grid=grid,
        ),
    ]


def _metric_payload(result: RegressionCPResult, y_test: np.ndarray, alpha: float) -> dict:
    metrics = compute_interval_metrics(y_test, result.lower, result.upper, alpha)
    return {
        "coverage": metrics.coverage,
        "mean_width": metrics.mean_width,
        "median_width": metrics.median_width,
        "normalized_mean_width": metrics.normalized_mean_width,
        "interval_score": metrics.interval_score,
        "lower_miss_rate": metrics.lower_miss_rate,
        "upper_miss_rate": metrics.upper_miss_rate,
    }


def compare_panel(panel: SyntheticPanel, alpha: float, ivar_m: int) -> dict:
    bridge = venn_abers_quantile_interval(
        y_cal=panel.y_cal,
        yhat_cal=panel.yhat_cal,
        yhat_test=panel.yhat_test,
        residual_quantile_cal=panel.residual_quantile_cal,
        residual_quantile_test=panel.residual_quantile_test,
        alpha=alpha,
        m=ivar_m,
    )
    grid = venn_abers_quantile_grid_interval(
        y_cal=panel.y_cal,
        yhat_cal=panel.yhat_cal,
        yhat_test=panel.yhat_test,
        residual_quantile_cal=panel.residual_quantile_cal,
        residual_quantile_test=panel.residual_quantile_test,
        score_grid=panel.score_grid,
        alpha=alpha,
    )
    radius_delta = bridge.radii - grid.radii
    return {
        "panel_id": panel.panel_id,
        "notes": panel.notes,
        "n_cal": int(len(panel.y_cal)),
        "n_test": int(len(panel.y_test)),
        "alpha": alpha,
        "ivar_m": ivar_m,
        "score_grid_size": int(len(panel.score_grid)),
        "bridge_radii": [float(value) for value in bridge.radii],
        "grid_radii": [float(value) for value in grid.radii],
        "radius_delta": [float(value) for value in radius_delta],
        "mean_abs_radius_delta": float(np.mean(np.abs(radius_delta))),
        "max_abs_radius_delta": float(np.max(np.abs(radius_delta))),
        "bridge_metrics": _metric_payload(bridge, panel.y_test, alpha),
        "grid_metrics": _metric_payload(grid, panel.y_test, alpha),
        "grid_accepted_counts": grid.metadata["accepted_counts"],
        "grid_rejected_counts": grid.metadata["rejected_counts"],
    }


def summarize_rows(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    return {
        "panel_count": len(rows),
        "mean_abs_radius_delta": float(np.mean([row["mean_abs_radius_delta"] for row in rows])),
        "max_abs_radius_delta": float(np.max([row["max_abs_radius_delta"] for row in rows])),
        "mean_bridge_coverage": float(np.mean([row["bridge_metrics"]["coverage"] for row in rows])),
        "mean_grid_coverage": float(np.mean([row["grid_metrics"]["coverage"] for row in rows])),
        "mean_bridge_width": float(np.mean([row["bridge_metrics"]["mean_width"] for row in rows])),
        "mean_grid_width": float(np.mean([row["grid_metrics"]["mean_width"] for row in rows])),
    }


def render_markdown(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# Venn-Abers Quantile Bridge Benchmark",
        "",
        "This tiny synthetic benchmark compares the fast `venn_abers_quantile` "
        "runner bridge against the exact candidate-grid `venn_abers_quantile_grid` "
        "reference. It is a method diagnostic, not a data result.",
        "",
        "## Summary",
        "",
        f"- Panels: {summary['panel_count']}",
        f"- Mean absolute radius delta: {summary['mean_abs_radius_delta']:.6f}",
        f"- Max absolute radius delta: {summary['max_abs_radius_delta']:.6f}",
        f"- Mean bridge coverage: {summary['mean_bridge_coverage']:.6f}",
        f"- Mean grid coverage: {summary['mean_grid_coverage']:.6f}",
        f"- Mean bridge width: {summary['mean_bridge_width']:.6f}",
        f"- Mean grid width: {summary['mean_grid_width']:.6f}",
        "",
        "## Panel Details",
        "",
        "| panel_id | mean_abs_radius_delta | max_abs_radius_delta | bridge_coverage | grid_coverage | bridge_width | grid_width |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {panel_id} | {mean_abs_radius_delta:.6f} | {max_abs_radius_delta:.6f} | "
            "{bridge_coverage:.6f} | {grid_coverage:.6f} | {bridge_width:.6f} | "
            "{grid_width:.6f} |".format(
                panel_id=row["panel_id"],
                mean_abs_radius_delta=row["mean_abs_radius_delta"],
                max_abs_radius_delta=row["max_abs_radius_delta"],
                bridge_coverage=row["bridge_metrics"]["coverage"],
                grid_coverage=row["grid_metrics"]["coverage"],
                bridge_width=row["bridge_metrics"]["mean_width"],
                grid_width=row["grid_metrics"]["mean_width"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def run_benchmark(alpha: float, ivar_m: int) -> dict:
    rows = [compare_panel(panel, alpha=alpha, ivar_m=ivar_m) for panel in synthetic_panels()]
    return {
        "benchmark_id": "venn_abers_quantile_bridge_vs_grid_v1",
        "alpha": alpha,
        "ivar_m": ivar_m,
        "method_under_test": "venn_abers_quantile",
        "reference_method": "venn_abers_quantile_grid",
        "summary": summarize_rows(rows),
        "rows": rows,
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = run_benchmark(alpha=args.alpha, ivar_m=args.ivar_m)
    atomic_write_json(out_dir / "benchmark.json", payload)
    atomic_write_text(out_dir / "benchmark.md", render_markdown(payload))
    print(json.dumps({"status": "ok", "panels": len(payload["rows"])}))


if __name__ == "__main__":
    main()
