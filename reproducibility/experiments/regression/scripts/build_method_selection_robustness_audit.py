"""Audit candidate method-selection stability without selecting a final winner."""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_method_selection_robustness_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_METHOD_SYNTHESIS = REPORT_DIR / "method_performance_synthesis.json"
DEFAULT_CANDIDATE_AUDIT = REPORT_DIR / "method_selection_candidate_audit.json"
DEFAULT_SELECTION_PROTOCOL = Path(
    "experiments/regression/manuscript/selection_multiplicity_protocol.json"
)
DEFAULT_FINAL_BOUNDARY = REPORT_DIR / "final_selection_claim_boundary_audit.json"
DEFAULT_OUT = REPORT_DIR / "method_selection_robustness_audit.json"

BOOTSTRAP_SEED = 20260703
BOOTSTRAP_REPLICATES = 1000
MIN_BOOTSTRAP_REPLICATES = 100
MIN_COMMON_CELL_COUNT = 30
ALPHA_IMBALANCE_SHARE_THRESHOLD = 0.75
SELECTION_METRICS = ("coverage_error_abs", "interval_score", "mean_width")
CLAIM_BOUNDARIES = [
    "This audit tests candidate-shortlist stability only; it does not select a final conformal method.",
    "Only dataset-alpha cells containing every shortlisted method are used, so missing method coverage cannot favor the primary candidate.",
    "Cell winners are computed with the same no-final-selection operating logic: nominal coverage tier, near-nominal tier, interval score, absolute coverage error, and mean width.",
    "Leave-one-dataset, leave-one-alpha, alpha-balanced selection, and bootstrap stability are descriptive stress tests over the current evidence surface, not post-selection validation.",
    "Final method selection remains blocked until dataset-specific final gates, multiplicity records, endpoint and fairness boundaries, and post-selection validation evidence are all satisfied.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument(
        "--method-synthesis",
        default=str(DEFAULT_METHOD_SYNTHESIS),
        help="Method performance synthesis JSON path.",
    )
    parser.add_argument(
        "--candidate-audit",
        default=str(DEFAULT_CANDIDATE_AUDIT),
        help="Method selection candidate audit JSON path.",
    )
    parser.add_argument(
        "--selection-protocol",
        default=str(DEFAULT_SELECTION_PROTOCOL),
        help="Selection multiplicity protocol JSON path.",
    )
    parser.add_argument(
        "--final-boundary",
        default=str(DEFAULT_FINAL_BOUNDARY),
        help="Final selection boundary audit JSON path.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=BOOTSTRAP_REPLICATES,
        help="Deterministic bootstrap replicate count.",
    )
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
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


def metric_mean(cell: dict[str, Any], metric: str) -> float | None:
    return as_float(((cell.get("metrics") or {}).get(metric) or {}).get("mean"))


def has_required_metrics(cell: dict[str, Any]) -> bool:
    return all(metric_mean(cell, metric) is not None for metric in SELECTION_METRICS)


def coverage_tier(cell: dict[str, Any]) -> int:
    if cell.get("eligible_nominal_mean") is True:
        return 0
    if cell.get("eligible_near_nominal_mean") is True:
        return 1
    return 2


def cell_score(cell: dict[str, Any], method_id: str) -> tuple[Any, ...]:
    return (
        coverage_tier(cell),
        metric_mean(cell, "interval_score") or float("inf"),
        metric_mean(cell, "coverage_error_abs") or float("inf"),
        metric_mean(cell, "mean_width") or float("inf"),
        method_id,
    )


def shortlisted_methods(candidate_audit: dict[str, Any]) -> list[str]:
    return [
        str(row.get("cp_method"))
        for row in candidate_audit.get("shortlist_methods") or []
        if row.get("cp_method")
    ]


def cells_by_key(
    method_synthesis: dict[str, Any],
    candidate_methods: list[str],
) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
    candidate_set = set(candidate_methods)
    output: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in method_synthesis.get("dataset_alpha_method_cells") or []:
        method_id = str(row.get("cp_method") or "")
        if method_id not in candidate_set or not has_required_metrics(row):
            continue
        key = (str(row.get("dataset_id") or ""), str(row.get("alpha") or ""))
        if not key[0] or not key[1]:
            continue
        output.setdefault(key, {})[method_id] = row
    return output


def common_keys(
    cells: dict[tuple[str, str], dict[str, dict[str, Any]]],
    candidate_methods: list[str],
) -> list[tuple[str, str]]:
    return sorted(
        key
        for key, rows in cells.items()
        if all(method in rows for method in candidate_methods)
    )


def winner_for_key(
    key: tuple[str, str],
    cells: dict[tuple[str, str], dict[str, dict[str, Any]]],
    candidate_methods: list[str],
) -> str:
    return min(
        candidate_methods,
        key=lambda method: cell_score(cells[key][method], method),
    )


def method_metric_means(
    keys: list[tuple[str, str]],
    cells: dict[tuple[str, str], dict[str, dict[str, Any]]],
    candidate_methods: list[str],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for method in candidate_methods:
        rows = [cells[key][method] for key in keys if method in cells.get(key, {})]
        metric_means = {}
        for metric in SELECTION_METRICS:
            values = [
                value
                for value in (metric_mean(row, metric) for row in rows)
                if value is not None
            ]
            metric_means[metric] = mean(values) if values else None
        output[method] = {
            "cell_count": len(rows),
            "nominal_cell_count": sum(
                1 for row in rows if row.get("eligible_nominal_mean") is True
            ),
            "near_nominal_cell_count": sum(
                1 for row in rows if row.get("eligible_near_nominal_mean") is True
            ),
            "below_near_nominal_cell_count": sum(
                1 for row in rows if row.get("eligible_near_nominal_mean") is not True
            ),
            "metric_means": metric_means,
        }
    return output


def selection_from_keys(
    keys: list[tuple[str, str]],
    cells: dict[tuple[str, str], dict[str, dict[str, Any]]],
    candidate_methods: list[str],
) -> dict[str, Any]:
    winners = Counter(
        winner_for_key(key, cells, candidate_methods) for key in keys if key in cells
    )
    metric_means = method_metric_means(keys, cells, candidate_methods)

    def aggregate_score(method: str) -> tuple[Any, ...]:
        metrics = metric_means.get(method, {}).get("metric_means") or {}
        return (
            -winners.get(method, 0),
            (
                metrics.get("interval_score")
                if metrics.get("interval_score") is not None
                else float("inf")
            ),
            (
                metrics.get("coverage_error_abs")
                if metrics.get("coverage_error_abs") is not None
                else float("inf")
            ),
            (
                metrics.get("mean_width")
                if metrics.get("mean_width") is not None
                else float("inf")
            ),
            method,
        )

    selected = (
        min(candidate_methods, key=aggregate_score) if candidate_methods else None
    )
    sorted_counts = sorted(winners.values(), reverse=True)
    margin = (
        sorted_counts[0] - sorted_counts[1]
        if len(sorted_counts) > 1
        else (sorted_counts[0] if sorted_counts else 0)
    )
    return {
        "selected_method": selected,
        "cell_count": len(keys),
        "winner_counts": dict(sorted(winners.items())),
        "winner_margin_to_runner_up": margin,
        "method_metric_means": metric_means,
    }


def alpha_distribution(keys: list[tuple[str, str]]) -> dict[str, int]:
    return dict(sorted(Counter(alpha for _, alpha in keys).items()))


def grouped_keys(
    keys: list[tuple[str, str]], group_index: int
) -> dict[str, list[tuple[str, str]]]:
    output: dict[str, list[tuple[str, str]]] = {}
    for key in keys:
        output.setdefault(key[group_index], []).append(key)
    return {group: sorted(group_keys) for group, group_keys in sorted(output.items())}


def alpha_balanced_metric_means(
    alpha_groups: dict[str, list[tuple[str, str]]],
    cells: dict[tuple[str, str], dict[str, dict[str, Any]]],
    candidate_methods: list[str],
) -> dict[str, dict[str, float | None]]:
    output: dict[str, dict[str, float | None]] = {}
    for method in candidate_methods:
        output[method] = {}
        for metric in SELECTION_METRICS:
            alpha_means = []
            for group_keys in alpha_groups.values():
                values = [
                    value
                    for value in (
                        metric_mean(cells[key][method], metric)
                        for key in group_keys
                        if method in cells.get(key, {})
                    )
                    if value is not None
                ]
                if values:
                    alpha_means.append(mean(values))
            output[method][metric] = mean(alpha_means) if alpha_means else None
    return output


def alpha_balanced_selection(
    keys: list[tuple[str, str]],
    cells: dict[tuple[str, str], dict[str, dict[str, Any]]],
    candidate_methods: list[str],
    primary_method: str | None,
) -> dict[str, Any]:
    alpha_groups = grouped_keys(keys, 1)
    per_alpha = []
    selection_counts: Counter[str] = Counter()
    for alpha, group_keys in alpha_groups.items():
        selection = selection_from_keys(group_keys, cells, candidate_methods)
        selected = str(selection["selected_method"])
        selection_counts[selected] += 1
        per_alpha.append(
            {
                "alpha": alpha,
                "cell_count": len(group_keys),
                "selected_method": selection["selected_method"],
                "primary_retained": selection["selected_method"] == primary_method,
                "winner_counts": selection["winner_counts"],
                "winner_margin_to_runner_up": selection["winner_margin_to_runner_up"],
            }
        )
    metric_means = alpha_balanced_metric_means(alpha_groups, cells, candidate_methods)

    def balanced_score(method: str) -> tuple[Any, ...]:
        metrics = metric_means.get(method, {})
        return (
            -selection_counts.get(method, 0),
            (
                metrics.get("interval_score")
                if metrics.get("interval_score") is not None
                else float("inf")
            ),
            (
                metrics.get("coverage_error_abs")
                if metrics.get("coverage_error_abs") is not None
                else float("inf")
            ),
            (
                metrics.get("mean_width")
                if metrics.get("mean_width") is not None
                else float("inf")
            ),
            method,
        )

    selected = min(candidate_methods, key=balanced_score) if candidate_methods else None
    distribution = alpha_distribution(keys)
    max_share = (max(distribution.values()) / len(keys)) if keys else None
    return {
        "alpha_count": len(alpha_groups),
        "alpha_distribution": distribution,
        "max_alpha_cell_share": max_share,
        "imbalance_status": (
            "imbalanced_common_alpha_support"
            if max_share is not None and max_share >= ALPHA_IMBALANCE_SHARE_THRESHOLD
            else "no_large_alpha_concentration"
        ),
        "imbalance_threshold": ALPHA_IMBALANCE_SHARE_THRESHOLD,
        "per_alpha": per_alpha,
        "alpha_stratum_selection_counts": dict(sorted(selection_counts.items())),
        "alpha_balanced_metric_means": metric_means,
        "alpha_balanced_selected_method": selected,
        "alpha_balanced_primary_retained": selected == primary_method,
    }


def leave_one_group_rows(
    keys: list[tuple[str, str]],
    cells: dict[tuple[str, str], dict[str, dict[str, Any]]],
    candidate_methods: list[str],
    primary_method: str | None,
    group_index: int,
    group_field: str,
) -> list[dict[str, Any]]:
    output = []
    for group_value in sorted({key[group_index] for key in keys}):
        remaining = [key for key in keys if key[group_index] != group_value]
        selection = selection_from_keys(remaining, cells, candidate_methods)
        output.append(
            {
                f"held_out_{group_field}": group_value,
                "remaining_cell_count": len(remaining),
                "selected_method": selection["selected_method"],
                "primary_retained": selection["selected_method"] == primary_method,
                "winner_counts": selection["winner_counts"],
                "winner_margin_to_runner_up": selection["winner_margin_to_runner_up"],
            }
        )
    return output


def bootstrap_rows(
    keys: list[tuple[str, str]],
    cells: dict[tuple[str, str], dict[str, dict[str, Any]]],
    candidate_methods: list[str],
    replicate_count: int,
) -> dict[str, Any]:
    rng = random.Random(BOOTSTRAP_SEED)
    selection_counts: Counter[str] = Counter()
    examples = []
    for replicate_index in range(replicate_count):
        sample = [rng.choice(keys) for _ in keys] if keys else []
        selection = selection_from_keys(sample, cells, candidate_methods)
        selected = str(selection["selected_method"])
        selection_counts[selected] += 1
        if replicate_index < 12:
            examples.append(
                {
                    "replicate_index": replicate_index,
                    "selected_method": selected,
                    "winner_counts": selection["winner_counts"],
                    "winner_margin_to_runner_up": selection[
                        "winner_margin_to_runner_up"
                    ],
                }
            )
    return {
        "seed": BOOTSTRAP_SEED,
        "replicate_count": replicate_count,
        "selection_counts": dict(sorted(selection_counts.items())),
        "selection_rates": (
            {
                method: selection_counts.get(method, 0) / replicate_count
                for method in candidate_methods
            }
            if replicate_count
            else {}
        ),
        "examples": examples,
    }


def build_payload(
    root: Path,
    method_synthesis_path: Path,
    candidate_audit_path: Path,
    selection_protocol_path: Path,
    final_boundary_path: Path,
    *,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    method_synthesis = read_json(method_synthesis_path)
    candidate_audit = read_json(candidate_audit_path)
    selection_protocol = read_json(selection_protocol_path)
    final_boundary = read_json(final_boundary_path)

    method_summary = method_synthesis.get("summary") or {}
    candidate_summary = candidate_audit.get("summary") or {}
    selection_summary = selection_protocol.get("summary") or {}
    final_summary = final_boundary.get("summary") or {}
    candidate_methods = shortlisted_methods(candidate_audit)
    primary_method = candidate_summary.get("primary_candidate_method")
    cells = cells_by_key(method_synthesis, candidate_methods)
    keys = common_keys(cells, candidate_methods)
    full_selection = selection_from_keys(keys, cells, candidate_methods)
    leave_one_dataset = leave_one_group_rows(
        keys, cells, candidate_methods, primary_method, 0, "dataset_id"
    )
    leave_one_alpha = leave_one_group_rows(
        keys, cells, candidate_methods, primary_method, 1, "alpha"
    )
    alpha_balance = alpha_balanced_selection(
        keys, cells, candidate_methods, primary_method
    )
    bootstrap = bootstrap_rows(
        keys, cells, candidate_methods, max(0, int(bootstrap_replicates))
    )
    primary_bootstrap_count = int(
        (bootstrap.get("selection_counts") or {}).get(str(primary_method), 0)
    )
    checks = [
        {
            "check_id": "candidate_audit_ready",
            "status": (
                "pass"
                if candidate_summary.get("overall_status")
                == "method_selection_candidate_audit_ready_no_final_selection"
                and int(candidate_summary.get("failed_check_count") or 0) == 0
                and primary_method
                else "fail"
            ),
            "observed": {
                "overall_status": candidate_summary.get("overall_status"),
                "failed_check_count": candidate_summary.get("failed_check_count"),
                "primary_candidate_method": primary_method,
            },
        },
        {
            "check_id": "common_cell_count_sufficient",
            "status": "pass" if len(keys) >= MIN_COMMON_CELL_COUNT else "fail",
            "observed": {
                "common_cell_count": len(keys),
                "minimum": MIN_COMMON_CELL_COUNT,
            },
        },
        {
            "check_id": "primary_consistent_with_common_cell_selection",
            "status": (
                "pass"
                if full_selection["selected_method"] == primary_method
                else "fail"
            ),
            "observed": {
                "primary_candidate_method": primary_method,
                "common_cell_selected_method": full_selection["selected_method"],
            },
        },
        {
            "check_id": "leave_one_dataset_completed",
            "status": "pass" if leave_one_dataset else "fail",
            "observed": {"leave_one_dataset_count": len(leave_one_dataset)},
        },
        {
            "check_id": "alpha_balance_diagnostic_completed",
            "status": (
                "pass"
                if alpha_balance.get("alpha_count")
                and alpha_balance.get("alpha_balanced_selected_method")
                else "fail"
            ),
            "observed": {
                "alpha_count": alpha_balance.get("alpha_count"),
                "alpha_balanced_selected_method": alpha_balance.get(
                    "alpha_balanced_selected_method"
                ),
                "alpha_balanced_primary_retained": alpha_balance.get(
                    "alpha_balanced_primary_retained"
                ),
                "imbalance_status": alpha_balance.get("imbalance_status"),
            },
        },
        {
            "check_id": "bootstrap_replicates_sufficient",
            "status": (
                "pass"
                if int(bootstrap.get("replicate_count") or 0)
                >= MIN_BOOTSTRAP_REPLICATES
                else "fail"
            ),
            "observed": {
                "bootstrap_replicates": bootstrap.get("replicate_count"),
                "minimum": MIN_BOOTSTRAP_REPLICATES,
            },
        },
        {
            "check_id": "selection_protocol_keeps_final_selection_blocked",
            "status": (
                "pass"
                if selection_summary.get("can_support_final_method_selection") is False
                and selection_summary.get("final_selection_claim_status") == "blocked"
                else "fail"
            ),
            "observed": {
                "can_support_final_method_selection": selection_summary.get(
                    "can_support_final_method_selection"
                ),
                "final_selection_claim_status": selection_summary.get(
                    "final_selection_claim_status"
                ),
            },
        },
        {
            "check_id": "no_final_selection_claim",
            "status": (
                "pass"
                if candidate_summary.get("can_support_final_method_selection") is False
                and final_summary.get("claim_status") == "blocked"
                else "fail"
            ),
            "observed": {
                "candidate_can_support_final_method_selection": candidate_summary.get(
                    "can_support_final_method_selection"
                ),
                "final_selection_claim_status": final_summary.get("claim_status"),
            },
        },
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    dataset_retained = sum(1 for row in leave_one_dataset if row["primary_retained"])
    alpha_retained = sum(1 for row in leave_one_alpha if row["primary_retained"])
    status = (
        "method_selection_robustness_audit_ready_no_final_selection"
        if not failed_checks
        else "method_selection_robustness_audit_failed"
    )
    summary = {
        "overall_status": status,
        "failed_check_count": len(failed_checks),
        "source_completed_ledger_rows": method_summary.get("completed_ledger_rows"),
        "candidate_primary_method": primary_method,
        "candidate_methods": candidate_methods,
        "candidate_method_count": len(candidate_methods),
        "common_dataset_alpha_cell_count": len(keys),
        "common_dataset_count": len({key[0] for key in keys}),
        "common_alpha_count": len({key[1] for key in keys}),
        "common_alpha_distribution": alpha_distribution(keys),
        "common_alpha_max_cell_share": alpha_balance.get("max_alpha_cell_share"),
        "common_alpha_imbalance_status": alpha_balance.get("imbalance_status"),
        "alpha_balanced_selected_method": alpha_balance.get(
            "alpha_balanced_selected_method"
        ),
        "alpha_balanced_primary_retained": alpha_balance.get(
            "alpha_balanced_primary_retained"
        ),
        "alpha_stratum_selection_counts": alpha_balance.get(
            "alpha_stratum_selection_counts"
        ),
        "common_cell_selected_method": full_selection["selected_method"],
        "common_cell_primary_win_count": (
            full_selection["winner_counts"].get(str(primary_method), 0)
        ),
        "common_cell_winner_counts": full_selection["winner_counts"],
        "common_cell_winner_margin_to_runner_up": full_selection[
            "winner_margin_to_runner_up"
        ],
        "leave_one_dataset_count": len(leave_one_dataset),
        "leave_one_dataset_primary_retained_count": dataset_retained,
        "leave_one_dataset_primary_retention_rate": (
            dataset_retained / len(leave_one_dataset) if leave_one_dataset else None
        ),
        "leave_one_alpha_count": len(leave_one_alpha),
        "leave_one_alpha_primary_retained_count": alpha_retained,
        "leave_one_alpha_primary_retention_rate": (
            alpha_retained / len(leave_one_alpha) if leave_one_alpha else None
        ),
        "bootstrap_seed": bootstrap.get("seed"),
        "bootstrap_replicates": bootstrap.get("replicate_count"),
        "bootstrap_primary_selection_count": primary_bootstrap_count,
        "bootstrap_primary_selection_rate": (
            primary_bootstrap_count / int(bootstrap.get("replicate_count") or 1)
            if int(bootstrap.get("replicate_count") or 0) > 0
            else None
        ),
        "bootstrap_selection_counts": bootstrap.get("selection_counts"),
        "can_support_final_method_selection": False,
        "claim_status": "selection_robustness_ready_no_final_selection",
        "selection_protocol_status": selection_summary.get("overall_status"),
        "final_selection_claim_status": final_summary.get("claim_status"),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "method_performance_synthesis": rel(method_synthesis_path, root),
            "method_selection_candidate_audit": rel(candidate_audit_path, root),
            "selection_multiplicity_protocol": rel(selection_protocol_path, root),
            "final_selection_claim_boundary": rel(final_boundary_path, root),
        },
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": summary,
        "checks": checks,
        "failed_checks": failed_checks,
        "full_common_cell_selection": full_selection,
        "leave_one_dataset": leave_one_dataset,
        "leave_one_alpha": leave_one_alpha,
        "alpha_balanced_selection": alpha_balance,
        "bootstrap": bootstrap,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    full = payload["full_common_cell_selection"]
    lines = [
        "# Method Selection Robustness Audit",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Candidate primary method: `{summary['candidate_primary_method']}`",
        f"- Candidate methods: `{summary['candidate_methods']}`",
        f"- Common dataset-alpha cells: {summary['common_dataset_alpha_cell_count']}",
        f"- Common datasets: {summary['common_dataset_count']}",
        f"- Common alpha distribution: `{summary['common_alpha_distribution']}`",
        f"- Common alpha max cell share: {summary['common_alpha_max_cell_share']}",
        f"- Common alpha imbalance status: `{summary['common_alpha_imbalance_status']}`",
        f"- Common-cell selected method: `{summary['common_cell_selected_method']}`",
        f"- Common-cell winner counts: `{summary['common_cell_winner_counts']}`",
        f"- Alpha-balanced selected method: `{summary['alpha_balanced_selected_method']}`",
        f"- Alpha-balanced primary retained: `{summary['alpha_balanced_primary_retained']}`",
        f"- Alpha-stratum selection counts: `{summary['alpha_stratum_selection_counts']}`",
        f"- Leave-one-dataset primary retention: {summary['leave_one_dataset_primary_retained_count']} / {summary['leave_one_dataset_count']}",
        f"- Leave-one-alpha primary retention: {summary['leave_one_alpha_primary_retained_count']} / {summary['leave_one_alpha_count']}",
        f"- Bootstrap primary selection: {summary['bootstrap_primary_selection_count']} / {summary['bootstrap_replicates']}",
        f"- Claim status: `{summary['claim_status']}`",
        "",
        "This audit does not select a final conformal method.",
        "",
        "## Full Common-Cell Selection",
        "",
        "| method | cell wins | nominal cells | near-nominal cells | below-near cells | mean interval score | mean abs coverage error | mean width |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, row in sorted(full["method_metric_means"].items()):
        metrics = row.get("metric_means") or {}
        lines.append(
            "| {method} | {wins} | {nominal} | {near} | {below} | {score} | {error} | {width} |".format(
                method=method,
                wins=full["winner_counts"].get(method, 0),
                nominal=row.get("nominal_cell_count"),
                near=row.get("near_nominal_cell_count"),
                below=row.get("below_near_nominal_cell_count"),
                score=(
                    f"{float(metrics['interval_score']):.6g}"
                    if metrics.get("interval_score") is not None
                    else ""
                ),
                error=(
                    f"{float(metrics['coverage_error_abs']):.6g}"
                    if metrics.get("coverage_error_abs") is not None
                    else ""
                ),
                width=(
                    f"{float(metrics['mean_width']):.6g}"
                    if metrics.get("mean_width") is not None
                    else ""
                ),
            )
        )
    lines.extend(["", "## Leave-One-Alpha", ""])
    lines.append(
        "| held out alpha | remaining cells | selected method | primary retained | winner counts |"
    )
    lines.append("| --- | ---: | --- | --- | --- |")
    for row in payload["leave_one_alpha"]:
        lines.append(
            "| {alpha} | {cells} | `{selected}` | `{retained}` | `{counts}` |".format(
                alpha=row["held_out_alpha"],
                cells=row["remaining_cell_count"],
                selected=row["selected_method"],
                retained=row["primary_retained"],
                counts=row["winner_counts"],
            )
        )
    lines.extend(["", "## Alpha-Balanced Selection", ""])
    alpha_balance = payload["alpha_balanced_selection"]
    lines.append(
        f"- Alpha-balanced selected method: `{alpha_balance['alpha_balanced_selected_method']}`"
    )
    lines.append(
        f"- Alpha imbalance status: `{alpha_balance['imbalance_status']}` with max alpha cell share {alpha_balance['max_alpha_cell_share']}"
    )
    lines.append("")
    lines.append(
        "| alpha | cells | selected method | primary retained | winner counts |"
    )
    lines.append("| --- | ---: | --- | --- | --- |")
    for row in alpha_balance["per_alpha"]:
        lines.append(
            "| {alpha} | {cells} | `{selected}` | `{retained}` | `{counts}` |".format(
                alpha=row["alpha"],
                cells=row["cell_count"],
                selected=row["selected_method"],
                retained=row["primary_retained"],
                counts=row["winner_counts"],
            )
        )
    lines.extend(["", "## Bootstrap Selection Rates", ""])
    lines.append("| method | selections | rate |")
    lines.append("| --- | ---: | ---: |")
    bootstrap_counts = payload["bootstrap"].get("selection_counts") or {}
    bootstrap_rates = payload["bootstrap"].get("selection_rates") or {}
    for method in summary["candidate_methods"]:
        lines.append(
            "| {method} | {count} | {rate:.6g} |".format(
                method=method,
                count=bootstrap_counts.get(method, 0),
                rate=float(bootstrap_rates.get(method, 0.0)),
            )
        )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    payload = build_payload(
        root,
        (root / args.method_synthesis).resolve(),
        (root / args.candidate_audit).resolve(),
        (root / args.selection_protocol).resolve(),
        (root / args.final_boundary).resolve(),
        bootstrap_replicates=args.bootstrap_replicates,
    )
    out_path = (root / args.out).resolve()
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "candidate_primary_method": payload["summary"][
                    "candidate_primary_method"
                ],
                "common_dataset_alpha_cell_count": payload["summary"][
                    "common_dataset_alpha_cell_count"
                ],
                "bootstrap_primary_selection_rate": payload["summary"][
                    "bootstrap_primary_selection_rate"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
