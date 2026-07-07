"""Summarize completed post-selection validation runs without final selection."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.build_method_selection_alpha_expansion_batch import (
    alpha_sort_key,
    read_json,
    rel,
)


SCHEMA = "cpfi_regression_method_selection_post_selection_validation_results_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_BATCH = REPORT_DIR / "method_selection_post_selection_validation_batch.json"
DEFAULT_OUT = REPORT_DIR / "method_selection_post_selection_validation_results.json"
WIDTH_PATHOLOGY_NORMALIZED_THRESHOLD = 100.0
WIDTH_PATHOLOGY_RAW_THRESHOLD = 1_000_000.0
NEAR_NOMINAL_TOLERANCE = 0.02
SELECTION_METRICS = (
    "coverage_error_abs",
    "interval_score",
    "mean_width",
    "normalized_mean_width",
    "coverage_gap",
)
CLAIM_BOUNDARIES = [
    "This audit summarizes completed post-selection validation rows; it does not select a final conformal method.",
    "Diagnostic winners are computed only within matched dataset-alpha cells containing every candidate method.",
    "The diagnostic ordering uses nominal coverage tier, near-nominal tolerance, interval score, absolute coverage error, and width.",
    "Extreme interval-width rows are retained as pathology evidence instead of being filtered away.",
    "Final method selection remains blocked until the multiplicity record, dataset-specific gates, endpoint/bounded-support gates, fairness/population gates, and claim register are updated.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--batch", default=str(DEFAULT_BATCH), help="Batch JSON path.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


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


def metric(row: dict[str, Any], name: str) -> float | None:
    value = as_float(row.get(f"{name}_mean"))
    if value is not None:
        return value
    return as_float(row.get(name))


def alpha_text(value: Any) -> str:
    value_float = as_float(value)
    if value_float is None:
        return str(value)
    return f"{value_float:.12g}"


def report_slug(dataset_id: str) -> str:
    return f"method_selection_post_selection_validation_{dataset_id}"


def pilot_summary_path(root: Path, dataset_id: str) -> Path:
    return root / "experiments/regression/reports" / report_slug(dataset_id) / "pilot_summary.json"


def feature_audit_path(root: Path, dataset_id: str) -> Path:
    return (
        root
        / "experiments/regression/reports"
        / report_slug(dataset_id)
        / "feature_leakage_audit.json"
    )


def load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def coverage_tier(row: dict[str, Any]) -> int:
    alpha = as_float(row.get("alpha"))
    coverage = metric(row, "coverage")
    coverage_error = metric(row, "coverage_error_abs")
    if alpha is None or coverage is None:
        return 2
    nominal = 1.0 - alpha
    if coverage >= nominal:
        return 0
    if coverage_error is not None and coverage_error <= NEAR_NOMINAL_TOLERANCE:
        return 1
    return 2


def cell_score(row: dict[str, Any], method_id: str) -> tuple[Any, ...]:
    return (
        coverage_tier(row),
        metric(row, "interval_score") or float("inf"),
        metric(row, "coverage_error_abs") or float("inf"),
        metric(row, "mean_width") or float("inf"),
        method_id,
    )


def method_metric_means(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("cp_method"))].append(row)
    output: dict[str, dict[str, Any]] = {}
    for method_id, method_rows in sorted(grouped.items()):
        metrics: dict[str, float | None] = {}
        for name in SELECTION_METRICS:
            values = [
                value
                for value in (metric(row, name) for row in method_rows)
                if value is not None
            ]
            metrics[name] = mean(values) if values else None
        output[method_id] = {
            "cell_count": len(method_rows),
            "nominal_or_above_cell_count": sum(
                1 for row in method_rows if coverage_tier(row) == 0
            ),
            "near_nominal_cell_count": sum(
                1 for row in method_rows if coverage_tier(row) == 1
            ),
            "below_near_nominal_cell_count": sum(
                1 for row in method_rows if coverage_tier(row) == 2
            ),
            "metric_means": metrics,
        }
    return output


def width_pathology_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        normalized = metric(row, "normalized_mean_width")
        raw_width = metric(row, "mean_width")
        width_gap = metric(row, "width_gap")
        if (
            (normalized is not None and normalized >= WIDTH_PATHOLOGY_NORMALIZED_THRESHOLD)
            or (raw_width is not None and raw_width >= WIDTH_PATHOLOGY_RAW_THRESHOLD)
            or (width_gap is not None and width_gap >= WIDTH_PATHOLOGY_RAW_THRESHOLD)
        ):
            output.append(
                {
                    "dataset_id": row.get("dataset_id"),
                    "alpha": alpha_text(row.get("alpha")),
                    "cp_method": row.get("cp_method"),
                    "coverage_mean": metric(row, "coverage"),
                    "mean_width_mean": raw_width,
                    "normalized_mean_width_mean": normalized,
                    "width_gap_mean": width_gap,
                    "interval_score_mean": metric(row, "interval_score"),
                }
            )
    return output


def diagnostic_selection(rows: list[dict[str, Any]], methods: list[str]) -> dict[str, Any]:
    cells: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = (str(row.get("dataset_id")), alpha_text(row.get("alpha")))
        method_id = str(row.get("cp_method"))
        if method_id in methods:
            cells[key][method_id] = row
    common_keys = sorted(
        [key for key, cell_rows in cells.items() if all(method in cell_rows for method in methods)],
        key=lambda item: (item[0], alpha_sort_key(item[1])),
    )
    winners = Counter()
    per_cell = []
    for dataset_id, alpha in common_keys:
        cell_rows = cells[(dataset_id, alpha)]
        winner = min(methods, key=lambda method: cell_score(cell_rows[method], method))
        winners[winner] += 1
        per_cell.append(
            {
                "dataset_id": dataset_id,
                "alpha": alpha,
                "diagnostic_winner": winner,
                "scores": {
                    method: {
                        "coverage_tier": coverage_tier(cell_rows[method]),
                        "coverage_mean": metric(cell_rows[method], "coverage"),
                        "coverage_error_abs_mean": metric(
                            cell_rows[method], "coverage_error_abs"
                        ),
                        "interval_score_mean": metric(
                            cell_rows[method], "interval_score"
                        ),
                        "mean_width_mean": metric(cell_rows[method], "mean_width"),
                    }
                    for method in methods
                },
            }
        )
    per_alpha: dict[str, Counter[str]] = defaultdict(Counter)
    per_dataset: dict[str, Counter[str]] = defaultdict(Counter)
    for row in per_cell:
        per_alpha[row["alpha"]][row["diagnostic_winner"]] += 1
        per_dataset[row["dataset_id"]][row["diagnostic_winner"]] += 1
    return {
        "common_dataset_alpha_cell_count": len(common_keys),
        "expected_common_dataset_alpha_cell_count": len({row[0] for row in common_keys})
        * len({row[1] for row in common_keys}),
        "diagnostic_winner_counts": dict(sorted(winners.items())),
        "diagnostic_winners_by_alpha": {
            alpha: dict(sorted(counter.items()))
            for alpha, counter in sorted(per_alpha.items(), key=lambda item: alpha_sort_key(item[0]))
        },
        "diagnostic_winners_by_dataset": {
            dataset_id: dict(sorted(counter.items()))
            for dataset_id, counter in sorted(per_dataset.items())
        },
        "per_cell": per_cell,
        "method_metric_means": method_metric_means(rows),
    }


def validate_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    summary = payload["summary"]
    expected_runs = int(summary.get("expected_atomic_run_count") or 0)
    completed_runs = int(summary.get("completed_atomic_run_count") or 0)
    expected_cells = int(summary.get("expected_common_dataset_alpha_cell_count") or 0)
    common_cells = int(summary.get("common_dataset_alpha_cell_count") or 0)
    checks = [
        {
            "check_id": "all_expected_runs_completed",
            "status": "pass" if expected_runs == completed_runs and expected_runs > 0 else "fail",
            "observed": {
                "expected_atomic_run_count": expected_runs,
                "completed_atomic_run_count": completed_runs,
                "status_counts": summary.get("status_counts"),
            },
        },
        {
            "check_id": "all_pilot_summaries_present",
            "status": (
                "pass"
                if summary.get("pilot_summary_count") == summary.get("dataset_count")
                else "fail"
            ),
            "observed": {
                "pilot_summary_count": summary.get("pilot_summary_count"),
                "dataset_count": summary.get("dataset_count"),
            },
        },
        {
            "check_id": "feature_leakage_sidecars_clean",
            "status": (
                "pass"
                if summary.get("feature_leakage_violation_count") == 0
                and summary.get("feature_leakage_sidecar_count")
                == summary.get("dataset_count")
                else "fail"
            ),
            "observed": {
                "feature_leakage_sidecar_count": summary.get(
                    "feature_leakage_sidecar_count"
                ),
                "feature_leakage_violation_count": summary.get(
                    "feature_leakage_violation_count"
                ),
            },
        },
        {
            "check_id": "matched_common_support_complete",
            "status": "pass" if common_cells == expected_cells and common_cells > 0 else "fail",
            "observed": {
                "common_dataset_alpha_cell_count": common_cells,
                "expected_common_dataset_alpha_cell_count": expected_cells,
            },
        },
        {
            "check_id": "no_final_selection_claim",
            "status": "pass" if summary.get("can_support_final_method_selection") is False else "fail",
            "observed": {
                "can_support_final_method_selection": summary.get(
                    "can_support_final_method_selection"
                ),
                "claim_status": summary.get("claim_status"),
            },
        },
    ]
    return checks


def build_payload(root: Path, batch_path: Path) -> dict[str, Any]:
    batch = read_json(batch_path)
    batch_schema = str(batch.get("schema") or "")
    source_artifact_key = (
        "dataset_final_gate_post_selection_validation_bridge"
        if batch_schema
        == "cpfi_regression_dataset_final_gate_post_selection_validation_bridge_v1"
        else "method_selection_post_selection_validation_batch"
    )
    batch_summary = batch.get("summary") or {}
    generated_configs = batch.get("generated_configs") or []
    candidate_methods = [str(method) for method in batch_summary.get("candidate_methods") or []]
    all_summary_rows: list[dict[str, Any]] = []
    dataset_rows = []
    status_counts: Counter[str] = Counter()
    feature_violation_count = 0
    feature_sidecar_count = 0
    pilot_summary_count = 0
    completed_atomic_run_count = 0
    for row in generated_configs:
        dataset_id = str(row.get("dataset_id") or "")
        ledger_path = root / str(row.get("ledger") or "")
        ledger_rows = load_ledger(ledger_path)
        ledger_status = Counter(str(item.get("status")) for item in ledger_rows)
        status_counts.update(ledger_status)
        completed_atomic_run_count += ledger_status.get("completed", 0)
        pilot_path = pilot_summary_path(root, dataset_id)
        feature_path = feature_audit_path(root, dataset_id)
        pilot = read_json(pilot_path)
        feature = read_json(feature_path)
        if pilot:
            pilot_summary_count += 1
            all_summary_rows.extend(pilot.get("rows") or [])
        if feature:
            feature_sidecar_count += 1
            feature_violation_count += int(feature.get("violations_count") or 0)
        dataset_rows.append(
            {
                "dataset_id": dataset_id,
                "ledger": row.get("ledger"),
                "config_path": row.get("config_path"),
                "experiment_id": row.get("experiment_id"),
                "pilot_summary": rel(pilot_path, root),
                "feature_leakage_audit": rel(feature_path, root),
                "expected_atomic_run_count": row.get("expected_atomic_run_count"),
                "completed_atomic_run_count": ledger_status.get("completed", 0),
                "status_counts": dict(sorted(ledger_status.items())),
                "pilot_summary_row_count": len(pilot.get("rows") or []),
                "feature_leakage_violations": int(feature.get("violations_count") or 0),
            }
        )
    diagnostic = diagnostic_selection(all_summary_rows, candidate_methods)
    pathology_rows = width_pathology_rows(all_summary_rows)
    summary = {
        "overall_status": "method_selection_post_selection_validation_results_ready_no_final_selection",
        "claim_status": "post_selection_validation_results_ready_no_final_selection",
        "can_support_final_method_selection": False,
        "dataset_count": len(generated_configs),
        "candidate_methods": candidate_methods,
        "expected_atomic_run_count": int(batch_summary.get("expected_atomic_run_count") or 0),
        "completed_atomic_run_count": completed_atomic_run_count,
        "status_counts": dict(sorted(status_counts.items())),
        "pilot_summary_count": pilot_summary_count,
        "feature_leakage_sidecar_count": feature_sidecar_count,
        "feature_leakage_violation_count": feature_violation_count,
        "common_dataset_alpha_cell_count": diagnostic["common_dataset_alpha_cell_count"],
        "expected_common_dataset_alpha_cell_count": (
            len(generated_configs) * len(batch_summary.get("target_alphas") or [])
        ),
        "diagnostic_winner_counts": diagnostic["diagnostic_winner_counts"],
        "width_pathology_row_count": len(pathology_rows),
        "extreme_width_pathology_policy": {
            "normalized_mean_width_threshold": WIDTH_PATHOLOGY_NORMALIZED_THRESHOLD,
            "raw_width_or_gap_threshold": WIDTH_PATHOLOGY_RAW_THRESHOLD,
        },
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {source_artifact_key: rel(batch_path, root)},
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": summary,
        "dataset_rows": dataset_rows,
        "diagnostic_selection": diagnostic,
        "width_pathology_rows": pathology_rows,
    }
    checks = validate_payload(payload)
    failed = [check for check in checks if check["status"] != "pass"]
    payload["checks"] = checks
    payload["failed_checks"] = failed
    if failed:
        payload["summary"]["overall_status"] = (
            "method_selection_post_selection_validation_results_failed"
        )
    payload["summary"]["failed_check_count"] = len(failed)
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Method Selection Post-Selection Validation Results",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Completed atomic runs: {summary['completed_atomic_run_count']} / {summary['expected_atomic_run_count']}",
        f"- Status counts: `{summary['status_counts']}`",
        f"- Common dataset-alpha cells: {summary['common_dataset_alpha_cell_count']} / {summary['expected_common_dataset_alpha_cell_count']}",
        f"- Diagnostic winner counts: `{summary['diagnostic_winner_counts']}`",
        f"- Feature-leakage violations: {summary['feature_leakage_violation_count']}",
        f"- Width pathology rows: {summary['width_pathology_row_count']}",
        f"- Claim status: `{summary['claim_status']}`",
        "",
        "This audit is validation evidence triage only; it does not select a final method.",
        "",
        "## Dataset Rows",
        "",
        "| dataset | completed | pilot rows | leakage violations |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in payload["dataset_rows"]:
        lines.append(
            "| `{dataset}` | {completed} | {pilot_rows} | {violations} |".format(
                dataset=row["dataset_id"],
                completed=row["completed_atomic_run_count"],
                pilot_rows=row["pilot_summary_row_count"],
                violations=row["feature_leakage_violations"],
            )
        )
    lines.extend(["", "## Diagnostic Winners By Alpha", ""])
    lines.append(
        json.dumps(
            payload["diagnostic_selection"]["diagnostic_winners_by_alpha"],
            indent=2,
            sort_keys=True,
        )
    )
    lines.extend(["", "## Width Pathology Rows", ""])
    if payload["width_pathology_rows"]:
        lines.append(
            json.dumps(payload["width_pathology_rows"][:20], indent=2, sort_keys=True)
        )
    else:
        lines.append("No extreme interval-width pathology rows under the configured policy.")
    lines.extend(["", "## Checks", ""])
    lines.append("| check | status | observed |")
    lines.append("| --- | --- | --- |")
    for check in payload["checks"]:
        lines.append(
            f"| `{check['check_id']}` | `{check['status']}` | `{check.get('observed', {})}` |"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    batch_path = (root / args.batch).resolve()
    out_path = (root / args.out).resolve()
    payload = build_payload(root, batch_path)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "completed_atomic_run_count": payload["summary"][
                    "completed_atomic_run_count"
                ],
                "diagnostic_winner_counts": payload["summary"][
                    "diagnostic_winner_counts"
                ],
                "width_pathology_row_count": payload["summary"][
                    "width_pathology_row_count"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
