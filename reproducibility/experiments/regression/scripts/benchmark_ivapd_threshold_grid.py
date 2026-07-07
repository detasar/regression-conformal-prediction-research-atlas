"""Benchmark the IVAPD threshold-grid predictive-distribution prototype."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from cpfi.regression.venn_abers import (
    ivapd_distribution_metrics,
    ivapd_threshold_grid,
    threshold_grid_crps,
)


@dataclass(frozen=True)
class IVAPDPanel:
    panel_id: str
    notes: str
    y_cal: np.ndarray
    yhat_cal: np.ndarray
    yhat_test: np.ndarray
    y_test: np.ndarray
    thresholds: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        default="experiments/regression/reports/ivapd_threshold_grid_benchmark",
        help="Directory for benchmark JSON/MD artifacts.",
    )
    parser.add_argument("--alpha", type=float, default=0.2)
    return parser.parse_args()


def synthetic_panels() -> list[IVAPDPanel]:
    return [
        IVAPDPanel(
            panel_id="well_ranked_location_shift",
            notes="Point predictions are well ranked but shifted upward on one test point.",
            y_cal=np.array([-2.0, -1.2, -0.4, 0.1, 0.7, 1.4, 2.1, 2.8]),
            yhat_cal=np.array([-1.8, -1.0, -0.2, 0.2, 0.6, 1.2, 2.0, 2.6]),
            yhat_test=np.array([-0.8, 0.8, 2.2]),
            y_test=np.array([-0.6, 0.4, 1.7]),
            thresholds=np.round(np.linspace(-3.0, 3.0, 25), 2),
        ),
        IVAPDPanel(
            panel_id="heteroscedastic_tail",
            notes="Upper-tail calibration residuals are wider than lower-tail residuals.",
            y_cal=np.array([-1.5, -0.9, -0.4, 0.0, 0.6, 1.6, 2.7, 4.1]),
            yhat_cal=np.array([-1.4, -0.8, -0.3, 0.1, 0.5, 1.0, 1.6, 2.5]),
            yhat_test=np.array([-0.5, 1.0, 2.4]),
            y_test=np.array([-0.2, 2.0, 4.0]),
            thresholds=np.round(np.linspace(-2.0, 5.0, 29), 2),
        ),
        IVAPDPanel(
            panel_id="flat_prediction_ties",
            notes="Repeated point predictions stress binary Venn-Abers tie handling.",
            y_cal=np.array([0.0, 0.2, 0.9, 1.1, 1.7, 2.0, 2.5, 3.0]),
            yhat_cal=np.array([0.5, 0.5, 1.0, 1.0, 1.8, 1.8, 2.4, 2.4]),
            yhat_test=np.array([0.5, 1.8, 2.4]),
            y_test=np.array([0.4, 1.4, 3.1]),
            thresholds=np.round(np.linspace(-0.5, 3.5, 21), 2),
        ),
    ]


def point_step_cdf(thresholds: Iterable[float], yhat_test: float) -> np.ndarray:
    grid = np.asarray(thresholds, dtype=float)
    return (grid >= float(yhat_test)).astype(float)


def compare_panel(panel: IVAPDPanel, alpha: float) -> dict:
    rows = []
    for idx, (yhat, y_true) in enumerate(zip(panel.yhat_test, panel.y_test)):
        distribution = ivapd_threshold_grid(
            y_cal=panel.y_cal,
            yhat_cal=panel.yhat_cal,
            yhat_test=float(yhat),
            thresholds=panel.thresholds,
        )
        ivapd_metrics = ivapd_distribution_metrics(distribution, y_true=float(y_true), alpha=alpha)
        baseline_cdf = point_step_cdf(panel.thresholds, float(yhat))
        baseline_crps = threshold_grid_crps(float(y_true), panel.thresholds, baseline_cdf)
        rows.append(
            {
                "test_index": idx,
                "yhat_test": float(yhat),
                "y_true": float(y_true),
                "ivapd_midpoint_crps": ivapd_metrics["midpoint_crps"],
                "ivapd_lower_crps": ivapd_metrics["lower_crps"],
                "ivapd_upper_crps": ivapd_metrics["upper_crps"],
                "point_step_crps": baseline_crps,
                "crps_delta_vs_point_step": ivapd_metrics["midpoint_crps"] - baseline_crps,
                "cdf_band_mean_width": ivapd_metrics["cdf_band_mean_width"],
                "cdf_band_max_width": ivapd_metrics["cdf_band_max_width"],
                "central_interval_lower": ivapd_metrics["central_interval_lower"],
                "central_interval_upper": ivapd_metrics["central_interval_upper"],
                "covered_by_midpoint_interval": ivapd_metrics["covered_by_midpoint_interval"],
            }
        )

    return {
        "panel_id": panel.panel_id,
        "notes": panel.notes,
        "n_cal": int(len(panel.y_cal)),
        "n_test": int(len(panel.y_test)),
        "threshold_grid_size": int(len(panel.thresholds)),
        "threshold_min": float(np.min(panel.thresholds)),
        "threshold_max": float(np.max(panel.thresholds)),
        "mean_ivapd_midpoint_crps": float(np.mean([row["ivapd_midpoint_crps"] for row in rows])),
        "mean_point_step_crps": float(np.mean([row["point_step_crps"] for row in rows])),
        "mean_crps_delta_vs_point_step": float(
            np.mean([row["crps_delta_vs_point_step"] for row in rows])
        ),
        "mean_cdf_band_width": float(np.mean([row["cdf_band_mean_width"] for row in rows])),
        "max_cdf_band_width": float(np.max([row["cdf_band_max_width"] for row in rows])),
        "midpoint_interval_coverage": float(np.mean([row["covered_by_midpoint_interval"] for row in rows])),
        "rows": rows,
    }


def summarize_rows(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    return {
        "panel_count": len(rows),
        "test_case_count": int(sum(row["n_test"] for row in rows)),
        "mean_ivapd_midpoint_crps": float(np.mean([row["mean_ivapd_midpoint_crps"] for row in rows])),
        "mean_point_step_crps": float(np.mean([row["mean_point_step_crps"] for row in rows])),
        "mean_crps_delta_vs_point_step": float(
            np.mean([row["mean_crps_delta_vs_point_step"] for row in rows])
        ),
        "mean_cdf_band_width": float(np.mean([row["mean_cdf_band_width"] for row in rows])),
        "max_cdf_band_width": float(np.max([row["max_cdf_band_width"] for row in rows])),
        "mean_midpoint_interval_coverage": float(
            np.mean([row["midpoint_interval_coverage"] for row in rows])
        ),
    }


def render_markdown(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# IVAPD Threshold-Grid Benchmark",
        "",
        "This deterministic benchmark scores the `ivapd_threshold_grid` predictive "
        "CDF prototype with a threshold-grid CRPS approximation. It compares the "
        "IVAPD midpoint CDF against a point-prediction step CDF baseline. It is a "
        "distribution diagnostic, not an interval-coverage sweep.",
        "",
        "## Summary",
        "",
        f"- Panels: {summary['panel_count']}",
        f"- Test cases: {summary['test_case_count']}",
        f"- Mean IVAPD midpoint grid-CRPS: {summary['mean_ivapd_midpoint_crps']:.6f}",
        f"- Mean point-step grid-CRPS: {summary['mean_point_step_crps']:.6f}",
        f"- Mean CRPS delta vs point-step: {summary['mean_crps_delta_vs_point_step']:.6f}",
        f"- Mean CDF band width: {summary['mean_cdf_band_width']:.6f}",
        f"- Max CDF band width: {summary['max_cdf_band_width']:.6f}",
        f"- Mean midpoint interval coverage: {summary['mean_midpoint_interval_coverage']:.6f}",
        "",
        "## Panel Details",
        "",
        "| panel_id | grid | mean_ivapd_crps | mean_point_step_crps | mean_delta | mean_band_width | midpoint_interval_coverage |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {panel_id} | {threshold_grid_size} | {mean_ivapd_midpoint_crps:.6f} | "
            "{mean_point_step_crps:.6f} | {mean_crps_delta_vs_point_step:.6f} | "
            "{mean_cdf_band_width:.6f} | {midpoint_interval_coverage:.6f} |".format(**row)
        )
    lines.append("")
    return "\n".join(lines)


def run_benchmark(alpha: float) -> dict:
    rows = [compare_panel(panel, alpha=alpha) for panel in synthetic_panels()]
    return {
        "benchmark_id": "ivapd_threshold_grid_distribution_scoring_v1",
        "alpha": float(alpha),
        "method_under_test": "ivapd_threshold_grid",
        "baseline_method": "point_prediction_step_cdf",
        "score": "threshold_grid_crps_trapezoid",
        "summary": summarize_rows(rows),
        "rows": rows,
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = run_benchmark(alpha=args.alpha)
    atomic_write_json(out_dir / "benchmark.json", payload)
    atomic_write_text(out_dir / "benchmark.md", render_markdown(payload))
    print(json.dumps({"status": "ok", "panels": len(payload["rows"])}))


if __name__ == "__main__":
    main()
