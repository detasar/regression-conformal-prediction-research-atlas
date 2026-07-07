"""Summarize executed main-result candidate bundles without promotion claims."""

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


SCHEMA = "cpfi_regression_main_result_candidate_bundle_results_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_PLAN = REPORT_DIR / "main_result_candidate_bundle_plan.json"
DEFAULT_OUT = REPORT_DIR / "main_result_candidate_bundle_results.json"

NEAR_NOMINAL_TOLERANCE = 0.02
SEVERE_COVERAGE_GAP_THRESHOLD = 0.25
EXTREME_NORMALIZED_WIDTH_THRESHOLD = 5.0
EXTREME_RAW_WIDTH_THRESHOLD = 1_000_000.0
TOP_PATHOLOGY_EXAMPLE_LIMIT = 25

SELECTION_METRICS = (
    "coverage",
    "coverage_error_abs",
    "interval_score",
    "mean_width",
    "median_width",
    "normalized_mean_width",
    "coverage_gap",
    "width_gap",
    "lower_miss_rate",
    "upper_miss_rate",
)

CLAIM_BOUNDARIES = [
    "This artifact summarizes executed fresh-seed main-result candidate bundles; it does not promote a main result.",
    "Diagnostic leaders are computed only inside complete matched dataset-seed-alpha-model cells.",
    "The diagnostic ordering uses nominal coverage tier, interval score, absolute coverage error, width, and method id as a deterministic tie-breaker.",
    "Pathological rows are retained as evidence and blockers; they are not filtered out to improve rankings.",
    "Main-result promotion remains blocked until split, leakage, endpoint, bounded-support, fairness/population, final-selection, manifest, and KG gates pass.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="Candidate plan JSON.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


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


def alpha_text(value: Any) -> str:
    number = as_float(value)
    if number is None:
        return str(value)
    return f"{number:.12g}"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def canonical_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    status_rank = {
        "skipped_completed": 0,
        "skipped_method": 1,
        "failed": 2,
        "completed": 3,
    }
    indexed = []
    for index, row in enumerate(rows):
        run_id = str(row.get("run_id") or index)
        status = str(row.get("status") or "missing")
        indexed.append((run_id, status_rank.get(status, 1), index, row))
    indexed.sort(key=lambda item: (item[0], item[1], item[2]))
    by_run_id: dict[str, dict[str, Any]] = {}
    for run_id, _, _, row in indexed:
        by_run_id[run_id] = row
    return list(by_run_id.values())


def metric(row: dict[str, Any], name: str) -> float | None:
    if name == "coverage_error_abs":
        alpha = as_float(row.get("alpha"))
        coverage = as_float(row.get("coverage"))
        if alpha is not None and coverage is not None:
            return abs(coverage - (1.0 - alpha))
        return None
    return as_float(row.get(name))


def coverage_tier(row: dict[str, Any]) -> int:
    alpha = as_float(row.get("alpha"))
    coverage = metric(row, "coverage")
    error = metric(row, "coverage_error_abs")
    if alpha is None or coverage is None:
        return 2
    nominal = 1.0 - alpha
    if coverage >= nominal:
        return 0
    if error is not None and error <= NEAR_NOMINAL_TOLERANCE:
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


def mean_or_none(values: list[float]) -> float | None:
    return mean(values) if values else None


def summarize_methods(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("cp_method") or row.get("cp_method_id"))].append(row)
    output: dict[str, dict[str, Any]] = {}
    for method_id, method_rows in sorted(grouped.items()):
        metric_means = {}
        for name in SELECTION_METRICS:
            values = [
                value
                for value in (metric(row, name) for row in method_rows)
                if value is not None
            ]
            metric_means[name] = mean_or_none(values)
        output[method_id] = {
            "row_count": len(method_rows),
            "nominal_or_above_count": sum(
                1 for row in method_rows if coverage_tier(row) == 0
            ),
            "near_nominal_count": sum(
                1 for row in method_rows if coverage_tier(row) == 1
            ),
            "below_near_nominal_count": sum(
                1 for row in method_rows if coverage_tier(row) == 2
            ),
            "metric_means": metric_means,
        }
    return output


def summarize_method_alpha(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        method_id = str(row.get("cp_method") or row.get("cp_method_id"))
        grouped[(method_id, alpha_text(row.get("alpha")))].append(row)
    output = []
    for (method_id, alpha), method_rows in sorted(
        grouped.items(), key=lambda item: (item[0][0], alpha_sort_key(item[0][1]))
    ):
        output.append(
            {
                "cp_method": method_id,
                "alpha": alpha,
                "row_count": len(method_rows),
                "coverage_mean": mean_or_none(
                    [value for value in (metric(row, "coverage") for row in method_rows) if value is not None]
                ),
                "coverage_error_abs_mean": mean_or_none(
                    [
                        value
                        for value in (
                            metric(row, "coverage_error_abs") for row in method_rows
                        )
                        if value is not None
                    ]
                ),
                "interval_score_mean": mean_or_none(
                    [
                        value
                        for value in (
                            metric(row, "interval_score") for row in method_rows
                        )
                        if value is not None
                    ]
                ),
                "mean_width_mean": mean_or_none(
                    [
                        value
                        for value in (metric(row, "mean_width") for row in method_rows)
                        if value is not None
                    ]
                ),
                "coverage_gap_mean": mean_or_none(
                    [
                        value
                        for value in (
                            metric(row, "coverage_gap") for row in method_rows
                        )
                        if value is not None
                    ]
                ),
            }
        )
    return output


def cell_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("dataset_id") or ""),
        str(row.get("seed") or ""),
        alpha_text(row.get("alpha")),
        str(row.get("model_id") or ""),
        stable_json(row.get("model_params") or {}),
    )


def diagnostic_selection(
    rows: list[dict[str, Any]], methods: list[str]
) -> dict[str, Any]:
    cells: dict[tuple[str, str, str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        method_id = str(row.get("cp_method") or row.get("cp_method_id"))
        if method_id in methods:
            cells[cell_key(row)][method_id] = row

    complete_keys = sorted(
        [
            key
            for key, cell in cells.items()
            if all(method in cell for method in methods)
        ],
        key=lambda key: (key[0], key[1], alpha_sort_key(key[2]), key[3], key[4]),
    )
    winners = Counter()
    per_dataset: dict[str, Counter[str]] = defaultdict(Counter)
    per_alpha: dict[str, Counter[str]] = defaultdict(Counter)
    per_cell = []
    for key in complete_keys:
        dataset_id, seed, alpha, model_id, model_params_json = key
        cell = cells[key]
        winner = min(methods, key=lambda method_id: cell_score(cell[method_id], method_id))
        winners[winner] += 1
        per_dataset[dataset_id][winner] += 1
        per_alpha[alpha][winner] += 1
        per_cell.append(
            {
                "dataset_id": dataset_id,
                "seed": int(seed) if seed.isdigit() else seed,
                "alpha": alpha,
                "model_id": model_id,
                "model_params": json.loads(model_params_json),
                "diagnostic_winner": winner,
                "scores": {
                    method_id: {
                        "coverage_tier": coverage_tier(cell[method_id]),
                        "coverage": metric(cell[method_id], "coverage"),
                        "coverage_error_abs": metric(
                            cell[method_id], "coverage_error_abs"
                        ),
                        "interval_score": metric(cell[method_id], "interval_score"),
                        "mean_width": metric(cell[method_id], "mean_width"),
                        "coverage_gap": metric(cell[method_id], "coverage_gap"),
                    }
                    for method_id in methods
                },
            }
        )

    return {
        "complete_matched_cell_count": len(complete_keys),
        "diagnostic_winner_counts": dict(sorted(winners.items())),
        "diagnostic_winners_by_dataset": {
            dataset_id: dict(sorted(counter.items()))
            for dataset_id, counter in sorted(per_dataset.items())
        },
        "diagnostic_winners_by_alpha": {
            alpha: dict(sorted(counter.items()))
            for alpha, counter in sorted(
                per_alpha.items(), key=lambda item: alpha_sort_key(item[0])
            )
        },
        "per_cell": per_cell,
    }


def inverse_saturation_count(row: dict[str, Any]) -> int:
    metadata = row.get("cp_metadata") or {}
    transform = metadata.get("target_inverse_transform") or {}
    count = 0
    for bound in ("lower", "upper"):
        bound_payload = transform.get(bound) or {}
        raw = bound_payload.get("inverse_saturation_count")
        try:
            count += int(raw or 0)
        except (TypeError, ValueError):
            continue
    return count


def pathology_flags(row: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    metadata = row.get("cp_metadata") or {}
    for name in SELECTION_METRICS:
        if metric(row, name) is None and row.get(name) is not None:
            flags.append(f"nonfinite_{name}")
    if int(metadata.get("quantile_crossings_cal") or 0) > 0:
        flags.append("cqr_quantile_crossings_cal")
    if int(metadata.get("quantile_crossings_test") or 0) > 0:
        flags.append("cqr_quantile_crossings_test")
    if metadata.get("negative_correction_clipped") is True:
        flags.append("cqr_negative_correction_clipped")
    if metadata.get("fallback_groups"):
        flags.append("mondrian_fallback_groups")
    if inverse_saturation_count(row) > 0:
        flags.append("target_inverse_saturation")
    normalized_width = metric(row, "normalized_mean_width")
    raw_width = metric(row, "mean_width")
    width_gap = metric(row, "width_gap")
    if normalized_width is not None and normalized_width >= EXTREME_NORMALIZED_WIDTH_THRESHOLD:
        flags.append("extreme_normalized_width")
    if raw_width is not None and raw_width >= EXTREME_RAW_WIDTH_THRESHOLD:
        flags.append("extreme_raw_width")
    if width_gap is not None and width_gap >= EXTREME_RAW_WIDTH_THRESHOLD:
        flags.append("extreme_width_gap")
    coverage_gap = metric(row, "coverage_gap")
    if coverage_gap is not None and coverage_gap >= SEVERE_COVERAGE_GAP_THRESHOLD:
        flags.append("severe_group_coverage_gap")
    alpha = as_float(row.get("alpha"))
    coverage = metric(row, "coverage")
    if alpha is not None and coverage is not None:
        nominal = 1.0 - alpha
        if coverage < nominal:
            flags.append("coverage_below_nominal")
        if coverage < nominal - NEAR_NOMINAL_TOLERANCE:
            flags.append("coverage_below_nominal_by_more_than_0_02")
    return flags


def pathology_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counter = Counter()
    examples = []
    for row in rows:
        flags = pathology_flags(row)
        counter.update(flags)
        if flags and len(examples) < TOP_PATHOLOGY_EXAMPLE_LIMIT:
            examples.append(
                {
                    "dataset_id": row.get("dataset_id"),
                    "seed": row.get("seed"),
                    "alpha": alpha_text(row.get("alpha")),
                    "cp_method": row.get("cp_method") or row.get("cp_method_id"),
                    "flags": flags,
                    "coverage": metric(row, "coverage"),
                    "target_coverage": (
                        1.0 - as_float(row.get("alpha"))
                        if as_float(row.get("alpha")) is not None
                        else None
                    ),
                    "interval_score": metric(row, "interval_score"),
                    "mean_width": metric(row, "mean_width"),
                    "normalized_mean_width": metric(row, "normalized_mean_width"),
                    "coverage_gap": metric(row, "coverage_gap"),
                    "fallback_groups": (row.get("cp_metadata") or {}).get(
                        "fallback_groups"
                    ),
                    "inverse_saturation_count": inverse_saturation_count(row),
                }
            )
    return {
        "flag_counts": dict(sorted(counter.items())),
        "flagged_row_count": sum(1 for row in rows if pathology_flags(row)),
        "examples": examples,
    }


def dataset_summary(plan_row: dict[str, Any], ledger_rows: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = canonical_rows(ledger_rows)
    completed = [row for row in canonical if row.get("status") == "completed"]
    status_counts = Counter(str(row.get("status") or "missing") for row in canonical)
    expected = int(plan_row.get("expected_atomic_run_count") or 0)
    methods = [str(method) for method in plan_row.get("cp_methods") or []]
    diagnostics = diagnostic_selection(completed, methods)
    return {
        "dataset_id": plan_row["dataset_id"],
        "config_path": plan_row.get("config_path"),
        "ledger": plan_row.get("ledger"),
        "expected_atomic_run_count": expected,
        "raw_ledger_row_count": len(ledger_rows),
        "unique_run_row_count": len(canonical),
        "completed_atomic_run_count": len(completed),
        "completed_fraction": (len(completed) / expected) if expected else None,
        "status_counts": dict(sorted(status_counts.items())),
        "diagnostic_primary_method": plan_row.get("primary_candidate_method"),
        "promotion_priority_from_plan": plan_row.get("promotion_priority"),
        "can_support_main_result_promotion": False,
        "method_summary": summarize_methods(completed),
        "method_alpha_summary": summarize_method_alpha(completed),
        "diagnostic_selection": diagnostics,
        "pathology_summary": pathology_summary(completed),
    }


def build_payload(root: Path, *, plan_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    dataset_rows = []
    all_completed: list[dict[str, Any]] = []
    all_raw_count = 0
    all_unique_count = 0
    status_counts = Counter()
    missing_ledgers = []
    for plan_row in plan.get("candidate_rows") or []:
        ledger_path = resolve(root, str(plan_row.get("ledger") or ""))
        ledger_rows = load_jsonl(ledger_path)
        if not ledger_path.exists():
            missing_ledgers.append(rel(ledger_path, root))
        summary = dataset_summary(plan_row, ledger_rows)
        dataset_rows.append(summary)
        all_raw_count += summary["raw_ledger_row_count"]
        all_unique_count += summary["unique_run_row_count"]
        status_counts.update(summary["status_counts"])
        all_completed.extend(
            row
            for row in canonical_rows(ledger_rows)
            if row.get("status") == "completed"
        )

    expected = sum(int(row.get("expected_atomic_run_count") or 0) for row in dataset_rows)
    completed = len(all_completed)
    methods = [str(method) for method in (plan.get("summary") or {}).get("candidate_methods") or []]
    diagnostic = diagnostic_selection(all_completed, methods)
    failed_checks = []
    if missing_ledgers:
        failed_checks.append("missing_candidate_ledgers")
    if expected == 0:
        failed_checks.append("zero_expected_atomic_runs")
    if completed != expected:
        failed_checks.append("incomplete_candidate_bundle_rows")
    if any(
        status not in {"completed"} and count
        for status, count in status_counts.items()
    ):
        failed_checks.append("non_completed_terminal_rows_present")
    if diagnostic["complete_matched_cell_count"] == 0:
        failed_checks.append("no_complete_matched_diagnostic_cells")

    overall_status = (
        "main_result_candidate_bundle_results_completed_no_promotions"
        if not failed_checks
        else "main_result_candidate_bundle_results_incomplete_no_promotions"
    )
    pathologies = pathology_summary(all_completed)
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "main_result_candidate_bundle_plan": rel(plan_path, root),
            "candidate_ledgers": [
                str(row.get("ledger")) for row in plan.get("candidate_rows") or []
            ],
        },
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "overall_status": overall_status,
            "can_support_main_result_promotion": False,
            "candidate_dataset_count": len(dataset_rows),
            "candidate_methods": methods,
            "expected_atomic_run_count": expected,
            "raw_ledger_row_count": all_raw_count,
            "unique_run_row_count": all_unique_count,
            "completed_atomic_run_count": completed,
            "completed_fraction": (completed / expected) if expected else None,
            "status_counts": dict(sorted(status_counts.items())),
            "complete_matched_cell_count": diagnostic["complete_matched_cell_count"],
            "diagnostic_winner_counts": diagnostic["diagnostic_winner_counts"],
            "pathology_flag_counts": pathologies["flag_counts"],
            "pathology_flagged_row_count": pathologies["flagged_row_count"],
            "missing_ledger_count": len(missing_ledgers),
            "failed_check_count": len(failed_checks),
        },
        "failed_checks": failed_checks,
        "missing_ledgers": missing_ledgers,
        "method_summary": summarize_methods(all_completed),
        "diagnostic_selection": diagnostic,
        "pathology_summary": pathologies,
        "dataset_rows": dataset_rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Main-Result Candidate Bundle Results",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Main-result promotion supported: `{summary['can_support_main_result_promotion']}`",
        f"- Completed rows: {summary['completed_atomic_run_count']} / {summary['expected_atomic_run_count']}",
        f"- Candidate datasets: {summary['candidate_dataset_count']}",
        f"- Candidate methods: `{summary['candidate_methods']}`",
        f"- Complete matched diagnostic cells: {summary['complete_matched_cell_count']}",
        f"- Diagnostic winner counts: `{summary['diagnostic_winner_counts']}`",
        f"- Pathology flagged rows: {summary['pathology_flagged_row_count']}",
        f"- Failed checks: {summary['failed_check_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Dataset Completion",
            "",
            "| Dataset | Completed | Status counts | Diagnostic winners | Flagged rows |",
            "| --- | ---: | --- | --- | ---: |",
        ]
    )
    for row in payload["dataset_rows"]:
        lines.append(
            "| "
            f"`{row['dataset_id']}` | "
            f"{row['completed_atomic_run_count']} / {row['expected_atomic_run_count']} | "
            f"`{row['status_counts']}` | "
            f"`{row['diagnostic_selection']['diagnostic_winner_counts']}` | "
            f"{row['pathology_summary']['flagged_row_count']} |"
        )
    lines.extend(
        [
            "",
            "## Method Diagnostics",
            "",
            "| Method | Rows | Coverage | Abs coverage error | Interval score | Mean width | Group gap |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for method_id, row in payload["method_summary"].items():
        metrics = row["metric_means"]
        lines.append(
            "| "
            f"`{method_id}` | "
            f"{row['row_count']} | "
            f"{metrics.get('coverage')} | "
            f"{metrics.get('coverage_error_abs')} | "
            f"{metrics.get('interval_score')} | "
            f"{metrics.get('mean_width')} | "
            f"{metrics.get('coverage_gap')} |"
        )
    lines.extend(
        [
            "",
            "## Pathology Flags",
            "",
        ]
    )
    for key, count in payload["pathology_summary"]["flag_counts"].items():
        lines.append(f"- `{key}`: {count}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    plan_path = resolve(root, args.plan)
    out_path = resolve(root, args.out)
    payload = build_payload(root, plan_path=plan_path)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(json.dumps({"out": rel(out_path, root), **payload["summary"]}, sort_keys=True))
    return 0 if not payload["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
