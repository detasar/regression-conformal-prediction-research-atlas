"""Compare paired raw-vs-dedup duplicate-sensitivity reports.

This audit consumes the duplicate split caveat backlog and existing
``pilot_summary.json`` files. It only compares rows where the raw and dedup
dataset variants share the same model, model-parameter summary, conformal
method, and alpha. The result is a diagnostic sensitivity artifact, not a
statistical proof that duplicate handling is solved.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_paired_duplicate_sensitivity_audit_v1"
DEFAULT_BACKLOG = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "duplicate_split_caveat_backlog.json"
)
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "paired_duplicate_sensitivity_audit.json"
)
PAIR_KEY_FIELDS = ("model_id", "model_params_key", "cp_method", "alpha")
METRICS = (
    "coverage_mean",
    "coverage_error_abs_mean",
    "mean_width_mean",
    "normalized_mean_width_mean",
    "interval_score_mean",
    "coverage_gap_mean",
    "width_gap_mean",
    "lower_miss_rate_mean",
    "upper_miss_rate_mean",
)
CLAIM_BOUNDARIES = [
    "This is a paired diagnostic over completed model/CP grid summaries, not a formal independent hypothesis test.",
    "Dedup variants are sensitivity variants, not independent source datasets.",
    "Do not use raw-vs-dedup stability as final model-selection, production, causal, policy, legal, or protected-fairness evidence.",
    "Do not claim duplicate-content caveats are resolved for datasets without a paired dedup variant in the backlog.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--backlog", default=DEFAULT_BACKLOG, help="Duplicate backlog JSON.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output JSON path.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def paired_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row.get(field) for field in PAIR_KEY_FIELDS)


def float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rounded(value: float | None, digits: int = 10) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def metric_delta(raw: dict[str, Any], dedup: dict[str, Any], metric: str) -> dict[str, Any]:
    raw_value = float_or_none(raw.get(metric))
    dedup_value = float_or_none(dedup.get(metric))
    delta = None if raw_value is None or dedup_value is None else dedup_value - raw_value
    return {
        "raw": rounded(raw_value),
        "dedup": rounded(dedup_value),
        "delta_dedup_minus_raw": rounded(delta),
        "abs_delta": rounded(abs(delta)) if delta is not None else None,
    }


def nominal(row: dict[str, Any]) -> bool:
    coverage = float_or_none(row.get("coverage_mean"))
    alpha = float_or_none(row.get("alpha"))
    if coverage is None or alpha is None:
        return False
    return coverage >= 1.0 - alpha


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        field: row.get(field)
        for field in (
            "dataset_id",
            "model_id",
            "model_params_key",
            "cp_method",
            "alpha",
            "coverage_mean",
            "coverage_error_abs_mean",
            "mean_width_mean",
            "normalized_mean_width_mean",
            "interval_score_mean",
            "coverage_gap_mean",
            "width_gap_mean",
            "coverage_count",
        )
        if field in row
    }


def lowest_interval_score_nominal_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    nominal_rows = [row for row in rows if nominal(row)]
    if not nominal_rows:
        return None
    return compact_row(
        min(
            nominal_rows,
            key=lambda row: float_or_none(row.get("interval_score_mean")) or float("inf"),
        )
    )


def aggregate(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "max": None}
    return {
        "count": len(values),
        "mean": rounded(statistics.fmean(values)),
        "median": rounded(statistics.median(values)),
        "max": rounded(max(values)),
    }


def compare_dataset(
    *,
    root: Path,
    backlog_row: dict[str, Any],
) -> dict[str, Any]:
    report_dir = root / str(backlog_row["report_dir"])
    pilot_path = report_dir / "pilot_summary.json"
    pilot = read_json(pilot_path)
    raw_dataset_id = str(backlog_row["dataset_id"])
    dedup_dataset_id = str(backlog_row["paired_dedup_variant_dataset_id"])
    rows = pilot.get("rows", []) or []
    raw_rows = [row for row in rows if row.get("dataset_id") == raw_dataset_id]
    dedup_rows = [row for row in rows if row.get("dataset_id") == dedup_dataset_id]
    raw_by_key = {paired_key(row): row for row in raw_rows}
    dedup_by_key = {paired_key(row): row for row in dedup_rows}
    shared_keys = sorted(set(raw_by_key) & set(dedup_by_key))
    raw_only = sorted(set(raw_by_key) - set(dedup_by_key))
    dedup_only = sorted(set(dedup_by_key) - set(raw_by_key))

    comparison_rows = []
    method_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key in shared_keys:
        raw = raw_by_key[key]
        dedup = dedup_by_key[key]
        metric_deltas = {
            metric: metric_delta(raw, dedup, metric)
            for metric in METRICS
        }
        row = {
            "model_id": key[0],
            "model_params_key": key[1],
            "cp_method": key[2],
            "alpha": key[3],
            "raw_nominal": nominal(raw),
            "dedup_nominal": nominal(dedup),
            "metric_deltas": metric_deltas,
        }
        comparison_rows.append(row)
        method_groups[str(key[2])].append(row)

    def abs_metric_values(metric: str) -> list[float]:
        values = []
        for row in comparison_rows:
            value = row["metric_deltas"][metric]["abs_delta"]
            if value is not None:
                values.append(float(value))
        return values

    nominal_status_changes = [
        row for row in comparison_rows if row["raw_nominal"] != row["dedup_nominal"]
    ]
    method_summaries = []
    for method, method_rows in sorted(method_groups.items()):
        method_summaries.append(
            {
                "cp_method": method,
                "paired_rows": len(method_rows),
                "raw_nominal_count": sum(row["raw_nominal"] for row in method_rows),
                "dedup_nominal_count": sum(row["dedup_nominal"] for row in method_rows),
                "nominal_status_change_count": sum(
                    row["raw_nominal"] != row["dedup_nominal"] for row in method_rows
                ),
                "mean_abs_coverage_delta": aggregate(
                    [
                        float(row["metric_deltas"]["coverage_mean"]["abs_delta"])
                        for row in method_rows
                        if row["metric_deltas"]["coverage_mean"]["abs_delta"] is not None
                    ]
                )["mean"],
                "mean_abs_interval_score_delta": aggregate(
                    [
                        float(row["metric_deltas"]["interval_score_mean"]["abs_delta"])
                        for row in method_rows
                        if row["metric_deltas"]["interval_score_mean"]["abs_delta"] is not None
                    ]
                )["mean"],
            }
        )

    coverage_delta_summary = aggregate(abs_metric_values("coverage_mean"))
    interval_score_delta_summary = aggregate(abs_metric_values("interval_score_mean"))
    mean_width_delta_summary = aggregate(abs_metric_values("mean_width_mean"))
    normalized_width_delta_summary = aggregate(abs_metric_values("normalized_mean_width_mean"))
    coverage_gap_delta_summary = aggregate(abs_metric_values("coverage_gap_mean"))
    return {
        "raw_dataset_id": raw_dataset_id,
        "dedup_dataset_id": dedup_dataset_id,
        "report_id": backlog_row["report_id"],
        "report_dir": backlog_row["report_dir"],
        "pilot_summary_path": rel(pilot_path, root),
        "config_path": backlog_row.get("config_path"),
        "duplicate_backlog_pair_overlaps": backlog_row.get(
            "total_duplicate_signature_pair_overlaps"
        ),
        "duplicate_backlog_severity": backlog_row.get("severity"),
        "raw_summary_rows": len(raw_rows),
        "dedup_summary_rows": len(dedup_rows),
        "paired_comparison_rows": len(comparison_rows),
        "raw_only_rows": len(raw_only),
        "dedup_only_rows": len(dedup_only),
        "raw_nominal_count": sum(row["raw_nominal"] for row in comparison_rows),
        "dedup_nominal_count": sum(row["dedup_nominal"] for row in comparison_rows),
        "nominal_status_change_count": len(nominal_status_changes),
        "coverage_delta_abs": coverage_delta_summary,
        "interval_score_delta_abs": interval_score_delta_summary,
        "mean_width_delta_abs": mean_width_delta_summary,
        "normalized_mean_width_delta_abs": normalized_width_delta_summary,
        "coverage_gap_delta_abs": coverage_gap_delta_summary,
        "raw_lowest_interval_score_nominal_row": lowest_interval_score_nominal_row(raw_rows),
        "dedup_lowest_interval_score_nominal_row": lowest_interval_score_nominal_row(dedup_rows),
        "method_summaries": method_summaries,
        "largest_abs_coverage_delta_rows": sorted(
            comparison_rows,
            key=lambda row: (
                row["metric_deltas"]["coverage_mean"]["abs_delta"] is None,
                -(row["metric_deltas"]["coverage_mean"]["abs_delta"] or 0.0),
            ),
        )[:10],
        "largest_abs_interval_score_delta_rows": sorted(
            comparison_rows,
            key=lambda row: (
                row["metric_deltas"]["interval_score_mean"]["abs_delta"] is None,
                -(row["metric_deltas"]["interval_score_mean"]["abs_delta"] or 0.0),
            ),
        )[:10],
        "claim_boundaries": CLAIM_BOUNDARIES,
    }


def build_payload(root: Path, backlog_path: Path) -> dict[str, Any]:
    backlog = read_json(backlog_path)
    paired_rows = [
        row
        for row in backlog.get("rows", []) or []
        if row.get("paired_dedup_variant_available")
        and row.get("paired_dedup_variant_dataset_id")
    ]
    dataset_summaries = [
        compare_dataset(root=root, backlog_row=row)
        for row in paired_rows
    ]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_backlog_path": rel(backlog_path, root),
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "paired_dataset_count": len(dataset_summaries),
            "paired_comparison_rows": sum(
                item["paired_comparison_rows"] for item in dataset_summaries
            ),
            "raw_only_rows": sum(item["raw_only_rows"] for item in dataset_summaries),
            "dedup_only_rows": sum(item["dedup_only_rows"] for item in dataset_summaries),
            "nominal_status_change_count": sum(
                item["nominal_status_change_count"] for item in dataset_summaries
            ),
            "datasets": [
                {
                    "raw_dataset_id": item["raw_dataset_id"],
                    "dedup_dataset_id": item["dedup_dataset_id"],
                    "paired_comparison_rows": item["paired_comparison_rows"],
                    "nominal_status_change_count": item[
                        "nominal_status_change_count"
                    ],
                    "mean_abs_coverage_delta": item["coverage_delta_abs"]["mean"],
                    "max_abs_coverage_delta": item["coverage_delta_abs"]["max"],
                    "mean_abs_interval_score_delta": item[
                        "interval_score_delta_abs"
                    ]["mean"],
                    "raw_nominal_count": item["raw_nominal_count"],
                    "dedup_nominal_count": item["dedup_nominal_count"],
                }
                for item in dataset_summaries
            ],
        },
        "datasets": dataset_summaries,
    }


def render_row_summary(item: dict[str, Any]) -> str:
    raw_frontier = item.get("raw_lowest_interval_score_nominal_row") or {}
    dedup_frontier = item.get("dedup_lowest_interval_score_nominal_row") or {}
    return "\n".join(
        [
            f"### {item['raw_dataset_id']} -> {item['dedup_dataset_id']}",
            "",
            f"- Paired rows: {item['paired_comparison_rows']}",
            f"- Raw/dedup only rows: {item['raw_only_rows']} / {item['dedup_only_rows']}",
            f"- Raw nominal rows: {item['raw_nominal_count']}",
            f"- Dedup nominal rows: {item['dedup_nominal_count']}",
            f"- Nominal status changes: {item['nominal_status_change_count']}",
            f"- Mean/max abs coverage delta: {item['coverage_delta_abs']['mean']} / {item['coverage_delta_abs']['max']}",
            f"- Mean/max abs interval-score delta: {item['interval_score_delta_abs']['mean']} / {item['interval_score_delta_abs']['max']}",
            f"- Mean/max abs width delta: {item['mean_width_delta_abs']['mean']} / {item['mean_width_delta_abs']['max']}",
            f"- Raw lowest nominal interval-score row: `{raw_frontier.get('model_id')}` + `{raw_frontier.get('cp_method')}`",
            f"- Dedup lowest nominal interval-score row: `{dedup_frontier.get('model_id')}` + `{dedup_frontier.get('cp_method')}`",
            "",
        ]
    )


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Paired Duplicate Sensitivity Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source backlog: `{payload['source_backlog_path']}`",
        f"- Paired datasets: {summary['paired_dataset_count']}",
        f"- Paired comparison rows: {summary['paired_comparison_rows']}",
        f"- Nominal status changes: {summary['nominal_status_change_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(["", "## Dataset Summaries", ""])
    for item in payload["datasets"]:
        lines.append(render_row_summary(item))
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    backlog_path = Path(args.backlog)
    out_path = Path(args.out)
    if not backlog_path.is_absolute():
        backlog_path = root / backlog_path
    if not out_path.is_absolute():
        out_path = root / out_path
    payload = build_payload(root, backlog_path)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
