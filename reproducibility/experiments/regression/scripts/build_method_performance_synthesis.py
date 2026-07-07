"""Build descriptive method-performance synthesis over the publication surface."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Iterable

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.audit_cross_run_integrity import (
    canonical_ledger_rows,
    load_jsonl_rows,
    stable_params_key,
)


SCHEMA = "cpfi_regression_method_performance_synthesis_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_CROSS_RUN = REPORT_DIR / "cross_run_integrity_audit.json"
DEFAULT_OUT = REPORT_DIR / "method_performance_synthesis.json"
NOMINAL_TOLERANCE = 0.0
NEAR_NOMINAL_TOLERANCE = 0.01
BROAD_SUPPORT_MIN_DATASETS = 10
BROAD_SUPPORT_MIN_DATASET_ALPHA_CELLS = 10
CI_Z = 1.96
SELECTED_CELL_TERM = "coverage-eligible interval-score selected cells"
CLAIM_BOUNDARIES = [
    "This synthesis is descriptive evidence over the audited publication workbench surface, not a final method/model selection claim.",
    "Rows are completed ledger tasks; they are not independent scientific replications.",
    "Row-weighted summaries can be dominated by large sweeps; dataset-balanced summaries are reported separately.",
    "Nominal and near-nominal rates are empirical diagnostics and do not override split, leakage, duplicate, endpoint, fairness, bounded-support, or Venn-Abers validation gates.",
    "Venn-Abers bridge rows remain negative/diagnostic unless the dedicated Venn-Abers validation gate is closed.",
]


METRIC_FIELDS = [
    "coverage",
    "coverage_error_abs",
    "coverage_margin",
    "mean_width",
    "normalized_mean_width",
    "interval_score",
    "lower_miss_rate",
    "upper_miss_rate",
    "coverage_gap",
    "width_gap",
    "fit_seconds",
    "interval_seconds",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument(
        "--cross-run",
        default=str(DEFAULT_CROSS_RUN),
        help="Cross-run integrity audit JSON path.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def mean_ci(values: Iterable[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if as_float(value) is not None]
    if not clean:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "se": None,
            "ci95_low": None,
            "ci95_high": None,
            "min": None,
            "max": None,
        }
    avg = mean(clean)
    std = stdev(clean) if len(clean) > 1 else 0.0
    se = std / math.sqrt(len(clean)) if clean else None
    ci = CI_Z * se if se is not None else None
    return {
        "count": len(clean),
        "mean": avg,
        "std": std,
        "se": se,
        "ci95_low": avg - ci if ci is not None else None,
        "ci95_high": avg + ci if ci is not None else None,
        "interval_interpretation": (
            "descriptive row-level dispersion summary only; not an audited "
            "inferential confidence interval"
        ),
        "min": min(clean),
        "max": max(clean),
    }


def row_key(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("report_name", "")),
        str(row.get("dataset_id", "")),
        str(row.get("model_family", "")),
        str(row.get("model_id", "")),
        stable_params_key(row.get("model_params")),
        str(row.get("cp_method", "")),
        stable_params_key(row.get("cp_method_params")),
        str(row.get("alpha", "")),
        str(row.get("seed", "")),
        str(row.get("run_id", "")),
    )


def completed_publication_rows(
    root: Path, cross_run_path: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cross_run = read_json(cross_run_path)
    report_rows = cross_run.get("rows") or []
    rows: list[dict[str, Any]] = []
    source_reports: list[dict[str, Any]] = []
    for report in report_rows:
        pilot_summary_path = report.get("pilot_summary_path")
        if not pilot_summary_path:
            continue
        pilot_summary = read_json(root / str(pilot_summary_path))
        ledger_path = root / str(pilot_summary.get("ledger"))
        raw = load_jsonl_rows(ledger_path)
        canonical = canonical_ledger_rows(raw)
        completed = [row for row in canonical if str(row.get("status")) == "completed"]
        source_reports.append(
            {
                "report_id": report.get("report_id"),
                "report_name": report.get("report_name"),
                "pilot_summary_path": pilot_summary_path,
                "ledger_path": rel(ledger_path, root),
                "completed_rows": len(completed),
                "summary_completed_rows": int(
                    (
                        (pilot_summary.get("metadata") or {}).get("status_counts") or {}
                    ).get("completed", 0)
                ),
            }
        )
        for row in completed:
            enriched = dict(row)
            enriched["report_id"] = report.get("report_id")
            enriched["report_name"] = report.get("report_name")
            enriched["pilot_summary_path"] = pilot_summary_path
            enriched["ledger_path"] = rel(ledger_path, root)
            rows.append(enriched)
    rows.sort(key=row_key)
    return rows, source_reports


def enrich_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        coverage = as_float(row.get("coverage"))
        alpha = as_float(row.get("alpha"))
        target = None if alpha is None else 1.0 - alpha
        coverage_margin = None
        coverage_error_abs = None
        nominal = None
        near_nominal = None
        if coverage is not None and target is not None:
            coverage_margin = coverage - target
            coverage_error_abs = abs(coverage_margin)
            nominal = coverage_margin >= -NOMINAL_TOLERANCE
            near_nominal = coverage_margin >= -NEAR_NOMINAL_TOLERANCE
        out = dict(row)
        out["target_coverage"] = target
        out["coverage_margin"] = coverage_margin
        out["coverage_error_abs"] = coverage_error_abs
        out["nominal_coverage_hit"] = nominal
        out["near_nominal_coverage_hit"] = near_nominal
        enriched.append(out)
    return enriched


def summarize_group(
    rows: list[dict[str, Any]], group_fields: list[str]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(str(row.get(field, "")) for field in group_fields)
        grouped[key].append(row)

    output: list[dict[str, Any]] = []
    for key, group_rows in sorted(grouped.items()):
        item = {field: key[idx] for idx, field in enumerate(group_fields)}
        item["row_count"] = len(group_rows)
        item["report_count"] = len({str(row.get("report_name")) for row in group_rows})
        item["dataset_count"] = len({str(row.get("dataset_id")) for row in group_rows})
        item["model_count"] = len(
            {
                (
                    str(row.get("model_id")),
                    stable_params_key(row.get("model_params")),
                )
                for row in group_rows
            }
        )
        item["seed_count"] = len({str(row.get("seed")) for row in group_rows})
        item["alpha_count"] = len({str(row.get("alpha")) for row in group_rows})
        nominal_values = [
            row.get("nominal_coverage_hit")
            for row in group_rows
            if row.get("nominal_coverage_hit") is not None
        ]
        near_nominal_values = [
            row.get("near_nominal_coverage_hit")
            for row in group_rows
            if row.get("near_nominal_coverage_hit") is not None
        ]
        item["nominal_hit_count"] = int(sum(1 for value in nominal_values if value))
        item["nominal_evaluable_count"] = len(nominal_values)
        item["nominal_hit_rate"] = (
            item["nominal_hit_count"] / item["nominal_evaluable_count"]
            if item["nominal_evaluable_count"]
            else None
        )
        item["near_nominal_hit_count"] = int(
            sum(1 for value in near_nominal_values if value)
        )
        item["near_nominal_evaluable_count"] = len(near_nominal_values)
        item["near_nominal_hit_rate"] = (
            item["near_nominal_hit_count"] / item["near_nominal_evaluable_count"]
            if item["near_nominal_evaluable_count"]
            else None
        )
        item["metrics"] = {
            field: mean_ci(
                value
                for value in (as_float(row.get(field)) for row in group_rows)
                if value is not None
            )
            for field in METRIC_FIELDS
        }
        output.append(item)
    return output


def dataset_alpha_cells(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cells = summarize_group(rows, ["dataset_id", "alpha", "cp_method"])
    output: list[dict[str, Any]] = []
    for cell in cells:
        coverage = ((cell.get("metrics") or {}).get("coverage") or {}).get("mean")
        target = None
        try:
            target = 1.0 - float(cell["alpha"])
        except (TypeError, ValueError):
            pass
        coverage_margin = (
            None if coverage is None or target is None else coverage - target
        )
        item = dict(cell)
        item["target_coverage"] = target
        item["coverage_margin_mean"] = coverage_margin
        item["eligible_nominal_mean"] = (
            coverage_margin is not None and coverage_margin >= -NOMINAL_TOLERANCE
        )
        item["eligible_near_nominal_mean"] = (
            coverage_margin is not None and coverage_margin >= -NEAR_NOMINAL_TOLERANCE
        )
        output.append(item)
    return output


def balanced_method_summary(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        by_method[str(cell.get("cp_method"))].append(cell)
    output: list[dict[str, Any]] = []
    for method, method_cells in sorted(by_method.items()):
        nominal_hits = [
            bool(cell.get("eligible_nominal_mean")) for cell in method_cells
        ]
        near_hits = [
            bool(cell.get("eligible_near_nominal_mean")) for cell in method_cells
        ]
        item = {
            "cp_method": method,
            "dataset_alpha_cell_count": len(method_cells),
            "dataset_count": len(
                {str(cell.get("dataset_id")) for cell in method_cells}
            ),
            "alpha_count": len({str(cell.get("alpha")) for cell in method_cells}),
            "cell_nominal_mean_hit_count": int(sum(nominal_hits)),
            "cell_nominal_mean_hit_rate": (
                sum(nominal_hits) / len(nominal_hits) if nominal_hits else None
            ),
            "cell_near_nominal_mean_hit_count": int(sum(near_hits)),
            "cell_near_nominal_mean_hit_rate": (
                sum(near_hits) / len(near_hits) if near_hits else None
            ),
            "balanced_metrics": {
                field: mean_ci(
                    ((cell.get("metrics") or {}).get(field) or {}).get("mean")
                    for cell in method_cells
                    if ((cell.get("metrics") or {}).get(field) or {}).get("mean")
                    is not None
                )
                for field in METRIC_FIELDS
            },
        }
        output.append(item)
    return output


def frontier_by_cell(
    cells: list[dict[str, Any]], limit: int = 100
) -> list[dict[str, Any]]:
    by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        by_cell[(str(cell.get("dataset_id")), str(cell.get("alpha")))].append(cell)
    output: list[dict[str, Any]] = []
    for (dataset_id, alpha), cell_rows in sorted(by_cell.items()):
        nominal = [row for row in cell_rows if row.get("eligible_nominal_mean")]
        near_nominal = [
            row for row in cell_rows if row.get("eligible_near_nominal_mean")
        ]
        candidate_pool = nominal or near_nominal or cell_rows
        candidate_pool = sorted(
            candidate_pool,
            key=lambda row: (
                0 if row.get("eligible_nominal_mean") else 1,
                0 if row.get("eligible_near_nominal_mean") else 1,
                (
                    ((row.get("metrics") or {}).get("interval_score") or {}).get("mean")
                    if ((row.get("metrics") or {}).get("interval_score") or {}).get(
                        "mean"
                    )
                    is not None
                    else float("inf")
                ),
                (
                    ((row.get("metrics") or {}).get("mean_width") or {}).get("mean")
                    if ((row.get("metrics") or {}).get("mean_width") or {}).get("mean")
                    is not None
                    else float("inf")
                ),
                (
                    ((row.get("metrics") or {}).get("coverage_error_abs") or {}).get(
                        "mean"
                    )
                    if ((row.get("metrics") or {}).get("coverage_error_abs") or {}).get(
                        "mean"
                    )
                    is not None
                    else float("inf")
                ),
                str(row.get("cp_method")),
            ),
        )
        best = candidate_pool[0]
        output.append(
            {
                "dataset_id": dataset_id,
                "alpha": alpha,
                "candidate_status": (
                    "nominal_mean"
                    if best.get("eligible_nominal_mean")
                    else (
                        "near_nominal_mean"
                        if best.get("eligible_near_nominal_mean")
                        else "coverage_below_near_nominal"
                    )
                ),
                "cp_method": best.get("cp_method"),
                "row_count": best.get("row_count"),
                "coverage_mean": (
                    (best.get("metrics") or {}).get("coverage") or {}
                ).get("mean"),
                "coverage_margin_mean": best.get("coverage_margin_mean"),
                "mean_width_mean": (
                    ((best.get("metrics") or {}).get("mean_width") or {}).get("mean")
                ),
                "interval_score_mean": (
                    ((best.get("metrics") or {}).get("interval_score") or {}).get(
                        "mean"
                    )
                ),
            }
        )
    return output[:limit]


def method_candidate_summary(
    frontier_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in frontier_rows:
        method = str(row.get("cp_method"))
        counts[method]["frontier_cell_count"] += 1
        counts[method][f"status:{row.get('candidate_status')}"] += 1
    return [
        {
            "cp_method": method,
            "frontier_cell_count": int(counter["frontier_cell_count"]),
            "coverage_eligible_interval_score_selected_cell_count": int(
                counter["frontier_cell_count"]
            ),
            "candidate_status_counts": {
                key.split(":", 1)[1]: int(value)
                for key, value in sorted(counter.items())
                if key.startswith("status:")
            },
        }
        for method, counter in sorted(
            counts.items(),
            key=lambda item: (-item[1]["frontier_cell_count"], item[0]),
        )
    ]


def build_payload(root: Path, cross_run_path: Path) -> dict[str, Any]:
    rows, source_reports = completed_publication_rows(root, cross_run_path)
    enriched = enrich_metrics(rows)
    row_weighted = summarize_group(enriched, ["cp_method"])
    cells = dataset_alpha_cells(enriched)
    balanced = balanced_method_summary(cells)
    frontier = frontier_by_cell(cells, limit=200)
    frontier_summary = method_candidate_summary(frontier)
    frontier_count_by_method = {
        row["cp_method"]: int(row["frontier_cell_count"]) for row in frontier_summary
    }
    row_weighted_by_method = {row["cp_method"]: row for row in row_weighted}
    balanced_by_method = {row["cp_method"]: row for row in balanced}
    method_rows = []
    for method in sorted(set(row_weighted_by_method) | set(balanced_by_method)):
        row_summary = row_weighted_by_method.get(method, {})
        balanced_summary = balanced_by_method.get(method, {})
        dataset_count = int(row_summary.get("dataset_count", 0) or 0)
        dataset_alpha_cell_count = int(
            balanced_summary.get("dataset_alpha_cell_count", 0) or 0
        )
        support_class = (
            "broad_support"
            if dataset_count >= BROAD_SUPPORT_MIN_DATASETS
            and dataset_alpha_cell_count >= BROAD_SUPPORT_MIN_DATASET_ALPHA_CELLS
            else "limited_support"
        )
        method_rows.append(
            {
                "cp_method": method,
                "support_class": support_class,
                "row_count": row_summary.get("row_count", 0),
                "report_count": row_summary.get("report_count", 0),
                "dataset_count": dataset_count,
                "model_count": row_summary.get("model_count", 0),
                "seed_count": row_summary.get("seed_count", 0),
                "alpha_count": row_summary.get("alpha_count", 0),
                "frontier_cell_count": frontier_count_by_method.get(method, 0),
                "coverage_eligible_interval_score_selected_cell_count": (
                    frontier_count_by_method.get(method, 0)
                ),
                "row_weighted_nominal_hit_rate": row_summary.get("nominal_hit_rate"),
                "row_weighted_near_nominal_hit_rate": row_summary.get(
                    "near_nominal_hit_rate"
                ),
                "row_weighted_coverage_mean": (
                    ((row_summary.get("metrics") or {}).get("coverage") or {}).get(
                        "mean"
                    )
                ),
                "row_weighted_coverage_ci95": {
                    "low": (
                        ((row_summary.get("metrics") or {}).get("coverage") or {}).get(
                            "ci95_low"
                        )
                    ),
                    "high": (
                        ((row_summary.get("metrics") or {}).get("coverage") or {}).get(
                            "ci95_high"
                        )
                    ),
                },
                "row_weighted_uncertainty_note": (
                    "Row-weighted intervals are descriptive dispersion summaries "
                    "over completed ledger rows; they are not audited inferential "
                    "confidence intervals."
                ),
                "row_weighted_coverage_error_abs_mean": (
                    (
                        (row_summary.get("metrics") or {}).get("coverage_error_abs")
                        or {}
                    ).get("mean")
                ),
                "row_weighted_interval_score_mean": (
                    (
                        (row_summary.get("metrics") or {}).get("interval_score") or {}
                    ).get("mean")
                ),
                "row_weighted_mean_width_mean": (
                    ((row_summary.get("metrics") or {}).get("mean_width") or {}).get(
                        "mean"
                    )
                ),
                "dataset_alpha_cell_count": dataset_alpha_cell_count,
                "balanced_cell_nominal_mean_hit_rate": balanced_summary.get(
                    "cell_nominal_mean_hit_rate"
                ),
                "balanced_cell_near_nominal_mean_hit_rate": balanced_summary.get(
                    "cell_near_nominal_mean_hit_rate"
                ),
                "balanced_coverage_mean": (
                    (
                        (balanced_summary.get("balanced_metrics") or {}).get("coverage")
                        or {}
                    ).get("mean")
                ),
                "balanced_coverage_error_abs_mean": (
                    (
                        (balanced_summary.get("balanced_metrics") or {}).get(
                            "coverage_error_abs"
                        )
                        or {}
                    ).get("mean")
                ),
                "balanced_interval_score_mean": (
                    (
                        (balanced_summary.get("balanced_metrics") or {}).get(
                            "interval_score"
                        )
                        or {}
                    ).get("mean")
                ),
                "balanced_mean_width_mean": (
                    (
                        (balanced_summary.get("balanced_metrics") or {}).get(
                            "mean_width"
                        )
                        or {}
                    ).get("mean")
                ),
            }
        )

    completed_rows = len(enriched)
    summary = {
        "overall_status": "method_performance_synthesis_descriptive_no_final_selection",
        "failed_check_count": 0,
        "source_report_count": len(source_reports),
        "completed_ledger_rows": completed_rows,
        "method_count": len(method_rows),
        "dataset_count": len({str(row.get("dataset_id")) for row in enriched}),
        "alpha_count": len({str(row.get("alpha")) for row in enriched}),
        "dataset_alpha_cell_count": len(
            {(str(row.get("dataset_id")), str(row.get("alpha"))) for row in enriched}
        ),
        "frontier_cell_count": len(frontier),
        "coverage_eligible_interval_score_selected_cell_count": len(frontier),
        "can_support_final_method_selection": False,
        "claim_status": "descriptive_no_final_selection",
        "selected_cell_term": SELECTED_CELL_TERM,
        "nominal_tolerance": NOMINAL_TOLERANCE,
        "near_nominal_tolerance": NEAR_NOMINAL_TOLERANCE,
        "broad_support_min_datasets": BROAD_SUPPORT_MIN_DATASETS,
        "broad_support_min_dataset_alpha_cells": BROAD_SUPPORT_MIN_DATASET_ALPHA_CELLS,
        "broad_support_method_count": sum(
            1 for row in method_rows if row["support_class"] == "broad_support"
        ),
        "top_frontier_methods": frontier_summary[:10],
        "top_coverage_eligible_interval_score_selected_methods": frontier_summary[:10],
    }
    checks = [
        {
            "check_id": "source_reports_present",
            "status": "pass" if source_reports else "fail",
            "observed": {"source_report_count": len(source_reports)},
        },
        {
            "check_id": "completed_rows_present",
            "status": "pass" if completed_rows > 0 else "fail",
            "observed": {"completed_ledger_rows": completed_rows},
        },
        {
            "check_id": "method_rows_present",
            "status": "pass" if method_rows else "fail",
            "observed": {"method_count": len(method_rows)},
        },
        {
            "check_id": "frontier_cells_present",
            "status": "pass" if frontier else "fail",
            "observed": {"frontier_cell_count": len(frontier)},
            "selected_cell_term": SELECTED_CELL_TERM,
        },
        {
            "check_id": "no_final_selection_claim",
            "status": "pass",
            "observed": {"can_support_final_method_selection": False},
        },
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    summary["failed_check_count"] = len(failed_checks)
    if failed_checks:
        summary["overall_status"] = "method_performance_synthesis_failed"

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "cross_run_integrity": rel(cross_run_path, root),
        },
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": summary,
        "checks": checks,
        "failed_checks": failed_checks,
        "method_rows": sorted(
            method_rows,
            key=lambda row: (
                0 if row.get("support_class") == "broad_support" else 1,
                -int(row.get("frontier_cell_count") or 0),
                row.get("balanced_cell_nominal_mean_hit_rate") is None,
                -float(row.get("balanced_cell_nominal_mean_hit_rate") or -1.0),
                float(row.get("balanced_coverage_error_abs_mean") or float("inf")),
                float(row.get("balanced_interval_score_mean") or float("inf")),
                str(row.get("cp_method")),
            ),
        ),
        "row_weighted_method_rows": row_weighted,
        "dataset_alpha_method_cells": cells,
        "frontier_by_dataset_alpha": frontier,
        "coverage_eligible_interval_score_selected_by_dataset_alpha": frontier,
        "frontier_method_summary": frontier_summary,
        "coverage_eligible_interval_score_selected_method_summary": frontier_summary,
        "broad_support_method_rows": [
            row for row in method_rows if row["support_class"] == "broad_support"
        ],
        "source_reports": source_reports,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    method_rows = payload["method_rows"][:20]
    frontier_summary = payload["frontier_method_summary"][:20]
    lines = [
        "# Method Performance Synthesis",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Completed ledger rows: {summary['completed_ledger_rows']}",
        f"- Source reports: {summary['source_report_count']}",
        f"- Methods: {summary['method_count']}",
        f"- Datasets: {summary['dataset_count']}",
        f"- Dataset-alpha cells: {summary['dataset_alpha_cell_count']}",
        f"- Broad-support methods: {summary['broad_support_method_count']}",
        f"- Claim status: `{summary['claim_status']}`",
        "",
        "This is a descriptive synthesis only. It does not select a final method. "
        "Row-level uncertainty fields are descriptive summaries, not audited "
        "inferential confidence intervals.",
        "",
        "## Method Summary",
        "",
    ]
    if method_rows:
        columns = [
            "cp_method",
            "support_class",
            "row_count",
            "dataset_count",
            "dataset_alpha_cell_count",
            "coverage_eligible_interval_score_selected_cell_count",
            "row_weighted_nominal_hit_rate",
            "row_weighted_coverage_mean",
            "row_weighted_coverage_error_abs_mean",
            "row_weighted_interval_score_mean",
            "balanced_cell_nominal_mean_hit_rate",
            "balanced_coverage_mean",
            "balanced_coverage_error_abs_mean",
            "balanced_interval_score_mean",
        ]
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
        for row in method_rows:
            values = []
            for col in columns:
                value = row.get(col)
                if isinstance(value, float):
                    values.append(f"{value:.6g}")
                else:
                    values.append("" if value is None else str(value))
            lines.append("| " + " | ".join(values) + " |")
    else:
        lines.append("No method rows available.")
    lines.extend(["", "## Coverage-Eligible Interval-Score Selected Counts", ""])
    if frontier_summary:
        lines.append(
            "| cp_method | coverage_eligible_interval_score_selected_cell_count | candidate_status_counts |"
        )
        lines.append("| --- | ---: | --- |")
        for row in frontier_summary:
            lines.append(
                "| {cp_method} | {selected_count} | `{counts}` |".format(
                    cp_method=row["cp_method"],
                    selected_count=row[
                        "coverage_eligible_interval_score_selected_cell_count"
                    ],
                    counts=json.dumps(row["candidate_status_counts"], sort_keys=True),
                )
            )
    else:
        lines.append("No coverage-eligible interval-score selected cells available.")
    lines.extend(
        [
            "",
            "## Claim Boundaries",
            "",
            *[f"- {item}" for item in payload["claim_boundaries"]],
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    cross_run_path = (root / args.cross_run).resolve()
    out_path = (root / args.out).resolve()
    payload = build_payload(root, cross_run_path)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "completed_ledger_rows": payload["summary"]["completed_ledger_rows"],
                "method_count": payload["summary"]["method_count"],
                "frontier_cell_count": payload["summary"]["frontier_cell_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
