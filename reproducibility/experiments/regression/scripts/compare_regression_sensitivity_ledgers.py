"""Compare two regression experiment ledgers on shared semantic run groups."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_sensitivity_ledger_comparison_v1"
PAIR_KEY_FIELDS = ("dataset_id", "model_id", "model_params_key", "cp_method", "alpha")
METRICS = (
    "coverage",
    "coverage_error_abs",
    "coverage_gap",
    "mean_width",
    "normalized_mean_width",
    "interval_score",
    "lower_miss_rate",
    "upper_miss_rate",
    "width_gap",
)
CLAIM_BOUNDARIES = [
    "This is a paired diagnostic over shared semantic run groups, not a formal independent hypothesis test.",
    "Sensitivity rows are methodological variants; do not treat them as independent source datasets.",
    "Do not use this comparison to choose a final model or as production, causal, policy, public-health, or protected-fairness evidence.",
    "Venn-Abers regression bridge rows remain diagnostic-only unless separately validated against exact regression Venn-Abers coverage.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-ledger", required=True)
    parser.add_argument("--sensitivity-ledger", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--baseline-label", default="baseline")
    parser.add_argument("--sensitivity-label", default="sensitivity")
    parser.add_argument("--baseline-seed", action="append", type=int, default=[])
    parser.add_argument("--sensitivity-seed", action="append", type=int, default=[])
    parser.add_argument(
        "--baseline-dataset",
        action="append",
        default=[],
        help="Optional baseline dataset_id filter; repeat for multiple ids.",
    )
    parser.add_argument(
        "--sensitivity-dataset",
        action="append",
        default=[],
        help="Optional sensitivity dataset_id filter; repeat for multiple ids.",
    )
    parser.add_argument(
        "--baseline-method",
        action="append",
        default=[],
        help="Optional baseline CP method filter; repeat for multiple methods.",
    )
    parser.add_argument(
        "--sensitivity-method",
        action="append",
        default=[],
        help="Optional sensitivity CP method filter; repeat for multiple methods.",
    )
    parser.add_argument(
        "--method-pair",
        action="append",
        default=[],
        metavar="BASELINE=SENSITIVITY",
        help=(
            "Pair different CP method names as one semantic comparison key, "
            "for example cv_plus=cv_plus_grouped. May be repeated."
        ),
    )
    parser.add_argument(
        "--output-prefix",
        default="sensitivity_comparison",
        help="Output file prefix. Defaults to sensitivity_comparison.",
    )
    parser.add_argument(
        "--claim-boundary",
        action="append",
        default=[],
        help="Additional dataset- or design-specific claim boundary to preserve.",
    )
    parser.add_argument(
        "--allow-seed-imbalance",
        action="store_true",
        help="Allow shared semantic groups whose baseline/sensitivity seed sets differ.",
    )
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def read_ledger(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def canonical_params(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if value is None:
        return "{}"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "{}"
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"), default=str)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


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


def completed_rows(
    rows: list[dict[str, Any]],
    seeds: set[int],
    datasets: set[str],
    methods: set[str],
) -> list[dict[str, Any]]:
    completed = []
    for row in rows:
        if row.get("status") != "completed":
            continue
        dataset_id = row.get("dataset_id")
        if datasets and str(dataset_id) not in datasets:
            continue
        method = str(row.get("cp_method_id") or row.get("cp_method"))
        if methods and method not in methods:
            continue
        seed = row.get("seed")
        if seeds and int(seed) not in seeds:
            continue
        completed.append(row)
    return completed


def metric_value(row: dict[str, Any], metric: str) -> float | None:
    if metric == "coverage_error_abs":
        coverage = float_or_none(row.get("coverage"))
        alpha = float_or_none(row.get("alpha"))
        if coverage is None or alpha is None:
            return None
        return abs(coverage - (1.0 - alpha))
    return float_or_none(row.get(metric))


def canonical_model_params(row: dict[str, Any]) -> str:
    if row.get("model_params") is not None:
        return canonical_params(row.get("model_params"))
    return canonical_params(row.get("model_params_key"))


def row_method(row: dict[str, Any]) -> str:
    return str(row.get("cp_method_id") or row.get("cp_method"))


def pair_key(
    row: dict[str, Any],
    method_labels: dict[str, str] | None = None,
) -> tuple[Any, ...]:
    method = row_method(row)
    return (
        row.get("dataset_id"),
        row.get("model_id"),
        canonical_model_params(row),
        (method_labels or {}).get(method, method),
        row.get("alpha"),
    )


def aggregate_rows(
    rows: list[dict[str, Any]],
    method_labels: dict[str, str] | None = None,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[pair_key(row, method_labels)].append(row)
    aggregated: dict[tuple[Any, ...], dict[str, Any]] = {}
    for key, group_rows in grouped.items():
        item: dict[str, Any] = {
            "dataset_id": key[0],
            "model_id": key[1],
            "model_params_key": key[2],
            "cp_method": key[3],
            "source_cp_methods": sorted({row_method(row) for row in group_rows}),
            "alpha": key[4],
            "completed_rows": len(group_rows),
            "seeds": sorted({int(row["seed"]) for row in group_rows if row.get("seed") is not None}),
        }
        for metric in METRICS:
            values = [
                value
                for value in (metric_value(row, metric) for row in group_rows)
                if value is not None
            ]
            item[f"{metric}_mean"] = (
                statistics.fmean(values) if values else None
            )
        aggregated[key] = item
    return aggregated


def metric_delta(
    baseline: dict[str, Any],
    sensitivity: dict[str, Any],
    metric: str,
) -> dict[str, Any]:
    baseline_value = float_or_none(baseline.get(f"{metric}_mean"))
    sensitivity_value = float_or_none(sensitivity.get(f"{metric}_mean"))
    delta = (
        None
        if baseline_value is None or sensitivity_value is None
        else sensitivity_value - baseline_value
    )
    return {
        "baseline": rounded(baseline_value),
        "sensitivity": rounded(sensitivity_value),
        "delta_sensitivity_minus_baseline": rounded(delta),
        "abs_delta": rounded(abs(delta)) if delta is not None else None,
    }


def nominal(row: dict[str, Any]) -> bool:
    coverage = float_or_none(row.get("coverage_mean"))
    alpha = float_or_none(row.get("alpha"))
    if coverage is None or alpha is None:
        return False
    return coverage >= 1.0 - alpha


def compact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "dataset_id",
            "model_id",
            "model_params_key",
            "cp_method",
            "source_cp_methods",
            "alpha",
            "coverage_mean",
            "coverage_error_abs_mean",
            "mean_width_mean",
            "normalized_mean_width_mean",
            "interval_score_mean",
            "coverage_gap_mean",
            "completed_rows",
            "seeds",
        )
    }


def aggregate(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "max": None}
    return {
        "count": len(values),
        "mean": rounded(statistics.fmean(values)),
        "median": rounded(statistics.median(values)),
        "max": rounded(max(values)),
    }


def parse_method_pairs(values: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for value in values:
        if "=" not in value:
            raise ValueError(
                f"Invalid method-pair {value!r}; expected BASELINE=SENSITIVITY."
            )
        baseline, sensitivity = (part.strip() for part in value.split("=", 1))
        if not baseline or not sensitivity:
            raise ValueError(
                f"Invalid method-pair {value!r}; both sides must be non-empty."
            )
        pairs.append((baseline, sensitivity))
    return pairs


def method_pair_label(baseline: str, sensitivity: str) -> str:
    if baseline == sensitivity:
        return baseline
    return f"{baseline}->{sensitivity}"


def method_label_maps(
    method_pairs: list[tuple[str, str]],
) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
    baseline_labels: dict[str, str] = {}
    sensitivity_labels: dict[str, str] = {}
    records: list[dict[str, str]] = []
    for baseline, sensitivity in method_pairs:
        label = method_pair_label(baseline, sensitivity)
        baseline_labels[baseline] = label
        sensitivity_labels[sensitivity] = label
        records.append(
            {
                "baseline_method": baseline,
                "sensitivity_method": sensitivity,
                "comparison_method": label,
            }
        )
    return baseline_labels, sensitivity_labels, records


def build_payload(
    *,
    root: Path,
    baseline_ledger: Path,
    sensitivity_ledger: Path,
    out_dir: Path,
    baseline_label: str,
    sensitivity_label: str,
    baseline_seeds: set[int],
    sensitivity_seeds: set[int],
    baseline_datasets: set[str] | None = None,
    sensitivity_datasets: set[str] | None = None,
    baseline_methods: set[str] | None = None,
    sensitivity_methods: set[str] | None = None,
    method_pairs: list[tuple[str, str]] | None = None,
    extra_claim_boundaries: list[str] | None = None,
    require_matched_seeds: bool = True,
) -> dict[str, Any]:
    baseline_dataset_filter = set(baseline_datasets or set())
    sensitivity_dataset_filter = set(sensitivity_datasets or set())
    baseline_method_filter = set(baseline_methods or set())
    sensitivity_method_filter = set(sensitivity_methods or set())
    baseline_method_labels, sensitivity_method_labels, method_pair_records = (
        method_label_maps(method_pairs or [])
    )
    baseline_rows = completed_rows(
        read_ledger(baseline_ledger),
        baseline_seeds,
        baseline_dataset_filter,
        baseline_method_filter,
    )
    sensitivity_rows = completed_rows(
        read_ledger(sensitivity_ledger),
        sensitivity_seeds,
        sensitivity_dataset_filter,
        sensitivity_method_filter,
    )
    baseline = aggregate_rows(baseline_rows, baseline_method_labels)
    sensitivity = aggregate_rows(sensitivity_rows, sensitivity_method_labels)
    shared_keys = sorted(set(baseline) & set(sensitivity))
    baseline_only = sorted(set(baseline) - set(sensitivity))
    sensitivity_only = sorted(set(sensitivity) - set(baseline))

    comparison_rows = []
    for key in shared_keys:
        base = baseline[key]
        sens = sensitivity[key]
        deltas = {
            metric: metric_delta(base, sens, metric)
            for metric in METRICS
        }
        comparison_rows.append(
            {
                "dataset_id": key[0],
                "model_id": key[1],
                "model_params_key": key[2],
                "cp_method": key[3],
                "alpha": key[4],
                "baseline_completed_rows": base["completed_rows"],
                "sensitivity_completed_rows": sens["completed_rows"],
                "baseline_seeds": base["seeds"],
                "sensitivity_seeds": sens["seeds"],
                "baseline_source_cp_methods": base["source_cp_methods"],
                "sensitivity_source_cp_methods": sens["source_cp_methods"],
                "seed_balanced": base["seeds"] == sens["seeds"],
                "baseline_nominal": nominal(base),
                "sensitivity_nominal": nominal(sens),
                "metric_deltas": deltas,
            }
        )

    seed_imbalanced_rows = [
        row for row in comparison_rows if not row["seed_balanced"]
    ]
    if require_matched_seeds and seed_imbalanced_rows:
        examples = [
            {
                "dataset_id": row["dataset_id"],
                "model_id": row["model_id"],
                "cp_method": row["cp_method"],
                "alpha": row["alpha"],
                "baseline_seeds": row["baseline_seeds"],
                "sensitivity_seeds": row["sensitivity_seeds"],
            }
            for row in seed_imbalanced_rows[:5]
        ]
        raise ValueError(
            "Seed-imbalanced shared semantic groups detected; rerun after the "
            f"ledger is complete or pass --allow-seed-imbalance. Examples: {examples}"
        )

    def abs_metric(metric: str) -> list[float]:
        return [
            float(row["metric_deltas"][metric]["abs_delta"])
            for row in comparison_rows
            if row["metric_deltas"][metric]["abs_delta"] is not None
        ]

    method_summaries = []
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in comparison_rows:
        by_method[str(row["cp_method"])].append(row)
    for method, rows in sorted(by_method.items()):
        method_summaries.append(
            {
                "cp_method": method,
                "paired_rows": len(rows),
                "baseline_nominal_count": sum(row["baseline_nominal"] for row in rows),
                "sensitivity_nominal_count": sum(row["sensitivity_nominal"] for row in rows),
                "nominal_status_change_count": sum(
                    row["baseline_nominal"] != row["sensitivity_nominal"]
                    for row in rows
                ),
                "mean_abs_coverage_delta": aggregate(
                    [
                        float(row["metric_deltas"]["coverage"]["abs_delta"])
                        for row in rows
                        if row["metric_deltas"]["coverage"]["abs_delta"] is not None
                    ]
                )["mean"],
                "mean_abs_interval_score_delta": aggregate(
                    [
                        float(row["metric_deltas"]["interval_score"]["abs_delta"])
                        for row in rows
                        if row["metric_deltas"]["interval_score"]["abs_delta"] is not None
                    ]
                )["mean"],
            }
        )

    nominal_changes = [
        row for row in comparison_rows if row["baseline_nominal"] != row["sensitivity_nominal"]
    ]
    baseline_nominal_rows = [row for row in baseline.values() if nominal(row)]
    sensitivity_nominal_rows = [row for row in sensitivity.values() if nominal(row)]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline": {
            "label": baseline_label,
            "ledger": rel(baseline_ledger, root),
            "seed_filter": sorted(baseline_seeds),
            "dataset_filter": sorted(baseline_dataset_filter),
            "method_filter": sorted(baseline_method_filter),
            "completed_rows": len(baseline_rows),
            "grouped_rows": len(baseline),
        },
        "sensitivity": {
            "label": sensitivity_label,
            "ledger": rel(sensitivity_ledger, root),
            "seed_filter": sorted(sensitivity_seeds),
            "dataset_filter": sorted(sensitivity_dataset_filter),
            "method_filter": sorted(sensitivity_method_filter),
            "completed_rows": len(sensitivity_rows),
            "grouped_rows": len(sensitivity),
        },
        "out_dir": rel(out_dir, root),
        "method_pairs": method_pair_records,
        "claim_boundaries": CLAIM_BOUNDARIES + list(extra_claim_boundaries or []),
        "summary": {
            "paired_rows": len(comparison_rows),
            "baseline_only_rows": len(baseline_only),
            "sensitivity_only_rows": len(sensitivity_only),
            "seed_imbalanced_paired_rows": len(seed_imbalanced_rows),
            "nominal_status_change_count": len(nominal_changes),
            "coverage_delta_abs": aggregate(abs_metric("coverage")),
            "coverage_error_abs_delta_abs": aggregate(abs_metric("coverage_error_abs")),
            "interval_score_delta_abs": aggregate(abs_metric("interval_score")),
            "mean_width_delta_abs": aggregate(abs_metric("mean_width")),
            "normalized_mean_width_delta_abs": aggregate(abs_metric("normalized_mean_width")),
            "coverage_gap_delta_abs": aggregate(abs_metric("coverage_gap")),
            "baseline_nominal_count": len(baseline_nominal_rows),
            "sensitivity_nominal_count": len(sensitivity_nominal_rows),
            "method_summaries": method_summaries,
            "baseline_lowest_interval_score_nominal_row": compact(
                min(
                    baseline_nominal_rows,
                    key=lambda row: float_or_none(row.get("interval_score_mean")) or float("inf"),
                )
            )
            if baseline_nominal_rows
            else None,
            "sensitivity_lowest_interval_score_nominal_row": compact(
                min(
                    sensitivity_nominal_rows,
                    key=lambda row: float_or_none(row.get("interval_score_mean")) or float("inf"),
                )
            )
            if sensitivity_nominal_rows
            else None,
        },
        "largest_abs_coverage_delta_rows": sorted(
            comparison_rows,
            key=lambda row: (
                row["metric_deltas"]["coverage"]["abs_delta"] is None,
                -(row["metric_deltas"]["coverage"]["abs_delta"] or 0.0),
            ),
        )[:20],
        "largest_abs_interval_score_delta_rows": sorted(
            comparison_rows,
            key=lambda row: (
                row["metric_deltas"]["interval_score"]["abs_delta"] is None,
                -(row["metric_deltas"]["interval_score"]["abs_delta"] or 0.0),
            ),
        )[:20],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    baseline = payload["baseline"]
    sensitivity = payload["sensitivity"]
    lines = [
        "# Regression Sensitivity Ledger Comparison",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Baseline: `{baseline['label']}` ({baseline['completed_rows']} completed rows, {baseline['grouped_rows']} groups)",
        f"- Sensitivity: `{sensitivity['label']}` ({sensitivity['completed_rows']} completed rows, {sensitivity['grouped_rows']} groups)",
        f"- Paired rows: {summary['paired_rows']}",
        f"- Seed-imbalanced paired rows: {summary['seed_imbalanced_paired_rows']}",
        f"- Baseline/sensitivity only rows: {summary['baseline_only_rows']} / {summary['sensitivity_only_rows']}",
        f"- Nominal status changes: {summary['nominal_status_change_count']}",
        f"- Mean/max abs coverage delta: {summary['coverage_delta_abs']['mean']} / {summary['coverage_delta_abs']['max']}",
        f"- Mean/max abs interval-score delta: {summary['interval_score_delta_abs']['mean']} / {summary['interval_score_delta_abs']['max']}",
        f"- Mean/max abs width delta: {summary['mean_width_delta_abs']['mean']} / {summary['mean_width_delta_abs']['max']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(["", "## Method Summaries", ""])
    lines.append(
        "| method | paired | baseline nominal | sensitivity nominal | status changes | mean abs coverage delta | mean abs interval-score delta |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in summary["method_summaries"]:
        lines.append(
            "| {cp_method} | {paired_rows} | {baseline_nominal_count} | "
            "{sensitivity_nominal_count} | {nominal_status_change_count} | "
            "{mean_abs_coverage_delta} | {mean_abs_interval_score_delta} |".format(
                **row
            )
        )
    lines.extend(["", "## Frontier Rows", ""])
    lines.append(
        f"- Baseline lowest nominal interval-score row: `{summary['baseline_lowest_interval_score_nominal_row']}`"
    )
    lines.append(
        f"- Sensitivity lowest nominal interval-score row: `{summary['sensitivity_lowest_interval_score_nominal_row']}`"
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(".").resolve()
    baseline_ledger = Path(args.baseline_ledger)
    sensitivity_ledger = Path(args.sensitivity_ledger)
    out_dir = Path(args.out_dir)
    if not baseline_ledger.is_absolute():
        baseline_ledger = root / baseline_ledger
    if not sensitivity_ledger.is_absolute():
        sensitivity_ledger = root / sensitivity_ledger
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(
        root=root,
        baseline_ledger=baseline_ledger,
        sensitivity_ledger=sensitivity_ledger,
        out_dir=out_dir,
        baseline_label=args.baseline_label,
        sensitivity_label=args.sensitivity_label,
        baseline_seeds=set(args.baseline_seed),
        sensitivity_seeds=set(args.sensitivity_seed),
        baseline_datasets=set(args.baseline_dataset),
        sensitivity_datasets=set(args.sensitivity_dataset),
        baseline_methods=set(args.baseline_method),
        sensitivity_methods=set(args.sensitivity_method),
        method_pairs=parse_method_pairs(args.method_pair),
        extra_claim_boundaries=args.claim_boundary,
        require_matched_seeds=not args.allow_seed_imbalance,
    )
    atomic_write_json(out_dir / f"{args.output_prefix}.json", payload)
    atomic_write_text(out_dir / f"{args.output_prefix}.md", render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out_dir": rel(out_dir, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
