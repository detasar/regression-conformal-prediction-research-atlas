"""Build a no-final-selection audit for method shortlist and paired diagnostics."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_method_selection_candidate_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_METHOD_SYNTHESIS = REPORT_DIR / "method_performance_synthesis.json"
DEFAULT_SELECTION_PROTOCOL = Path(
    "experiments/regression/manuscript/selection_multiplicity_protocol.json"
)
DEFAULT_FINAL_BOUNDARY = REPORT_DIR / "final_selection_claim_boundary_audit.json"
DEFAULT_VENN_READINESS = REPORT_DIR / "venn_abers_validation_readiness_audit.json"
DEFAULT_OUT = REPORT_DIR / "method_selection_candidate_audit.json"

BROAD_SUPPORT_CLASS = "broad_support"
SHORTLIST_FRONTIER_CELL_MIN = 10
SHORTLIST_MIN_METHODS = 3
PRIMARY_METRIC = "interval_score"
SECONDARY_METRICS = ["coverage_error_abs", "mean_width"]
PAIRWISE_METRICS = ["coverage_error_abs", "interval_score", "mean_width"]
LOWER_IS_BETTER = set(PAIRWISE_METRICS)
CI_Z = 1.96
CLAIM_BOUNDARIES = [
    "This audit creates a descriptive shortlist and paired diagnostics only; it does not select a final method.",
    "Shortlist eligibility is derived from broad-support method-performance synthesis and frontier-cell frequency.",
    "Pairwise comparisons are over shared dataset-alpha cells, not independent experimental populations.",
    "Final method selection remains blocked until dataset-specific final gates, multiplicity records, endpoint and fairness boundaries, and post-selection validation evidence are all satisfied.",
    "Venn-Abers bridge methods remain diagnostic while the dedicated Venn-Abers validation gate is blocked.",
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
        "--selection-protocol",
        default=str(DEFAULT_SELECTION_PROTOCOL),
        help="Selection multiplicity protocol JSON path.",
    )
    parser.add_argument(
        "--final-boundary",
        default=str(DEFAULT_FINAL_BOUNDARY),
        help="Final selection boundary audit JSON path.",
    )
    parser.add_argument(
        "--venn-readiness",
        default=str(DEFAULT_VENN_READINESS),
        help="Venn-Abers validation readiness audit JSON path.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
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


def mean_ci(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "std": None, "ci95": None}
    avg = mean(values)
    std = stdev(values) if len(values) > 1 else 0.0
    ci = CI_Z * std / math.sqrt(len(values)) if values else None
    return {
        "count": len(values),
        "mean": avg,
        "median": median(values),
        "std": std,
        "ci95": {
            "low": avg - ci if ci is not None else None,
            "high": avg + ci if ci is not None else None,
        },
    }


def sign_test_two_sided_p(wins: int, losses: int) -> float | None:
    n = wins + losses
    if n == 0:
        return None
    tail = min(wins, losses)
    probability = sum(math.comb(n, k) for k in range(tail + 1)) / (2**n)
    return min(1.0, 2.0 * probability)


def candidate_method_rows(method_synthesis: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in method_synthesis.get("method_rows") or []:
        if row.get("support_class") != BROAD_SUPPORT_CLASS:
            continue
        if str(row.get("cp_method", "")).startswith("venn_abers"):
            continue
        if int(row.get("frontier_cell_count") or 0) < SHORTLIST_FRONTIER_CELL_MIN:
            continue
        rows.append(dict(row))
    return sorted(
        rows,
        key=lambda row: (
            -int(row.get("frontier_cell_count") or 0),
            -float(row.get("balanced_cell_nominal_mean_hit_rate") or -1.0),
            float(row.get("balanced_coverage_error_abs_mean") or float("inf")),
            float(row.get("balanced_interval_score_mean") or float("inf")),
            str(row.get("cp_method")),
        ),
    )


def exclusion_rows(
    method_synthesis: dict[str, Any], venn_readiness: dict[str, Any]
) -> list[dict[str, Any]]:
    venn_blocked = (venn_readiness.get("summary") or {}).get(
        "can_support_venn_abers_regression_validation"
    ) is False
    output = []
    for row in method_synthesis.get("method_rows") or []:
        method = str(row.get("cp_method", ""))
        reasons = []
        if row.get("support_class") != BROAD_SUPPORT_CLASS:
            reasons.append("limited_support")
        if int(row.get("frontier_cell_count") or 0) < SHORTLIST_FRONTIER_CELL_MIN:
            reasons.append("frontier_cell_count_below_shortlist_threshold")
        if method.startswith("venn_abers") and venn_blocked:
            reasons.append("venn_abers_validation_gate_blocked")
        if reasons:
            output.append(
                {
                    "cp_method": method,
                    "support_class": row.get("support_class"),
                    "frontier_cell_count": row.get("frontier_cell_count"),
                    "dataset_count": row.get("dataset_count"),
                    "dataset_alpha_cell_count": row.get("dataset_alpha_cell_count"),
                    "exclusion_reasons": sorted(set(reasons)),
                }
            )
    return sorted(output, key=lambda row: (row["cp_method"], row["exclusion_reasons"]))


def cells_by_method(
    method_synthesis: dict[str, Any],
) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    output: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for cell in method_synthesis.get("dataset_alpha_method_cells") or []:
        method = str(cell.get("cp_method", ""))
        key = (str(cell.get("dataset_id", "")), str(cell.get("alpha", "")))
        output.setdefault(method, {})[key] = cell
    return output


def paired_metric_summary(
    primary_method: str,
    comparator_method: str,
    primary_cells: dict[tuple[str, str], dict[str, Any]],
    comparator_cells: dict[tuple[str, str], dict[str, Any]],
    metric: str,
) -> dict[str, Any]:
    common_keys = sorted(set(primary_cells).intersection(comparator_cells))
    diffs = []
    wins = losses = ties = 0
    examples = []
    for key in common_keys:
        primary_value = metric_mean(primary_cells[key], metric)
        comparator_value = metric_mean(comparator_cells[key], metric)
        if primary_value is None or comparator_value is None:
            continue
        diff = primary_value - comparator_value
        diffs.append(diff)
        if abs(diff) <= 1e-12:
            ties += 1
            winner = "tie"
        elif metric in LOWER_IS_BETTER:
            winner = primary_method if diff < 0 else comparator_method
        else:
            winner = primary_method if diff > 0 else comparator_method
        if winner == primary_method:
            wins += 1
        elif winner == comparator_method:
            losses += 1
        examples.append(
            {
                "dataset_id": key[0],
                "alpha": key[1],
                "primary_value": primary_value,
                "comparator_value": comparator_value,
                "difference_primary_minus_comparator": diff,
                "winner": winner,
            }
        )
    evaluable = wins + losses + ties
    non_tie = wins + losses
    return {
        "metric": metric,
        "orientation": (
            "lower_is_better" if metric in LOWER_IS_BETTER else "higher_is_better"
        ),
        "shared_cell_count": len(common_keys),
        "evaluable_cell_count": evaluable,
        "primary_win_count": wins,
        "comparator_win_count": losses,
        "tie_count": ties,
        "primary_non_tie_win_rate": wins / non_tie if non_tie else None,
        "exact_sign_test_two_sided_p": sign_test_two_sided_p(wins, losses),
        "difference_primary_minus_comparator": mean_ci(diffs),
        "examples": examples[:12],
    }


def paired_comparisons(
    shortlist: list[dict[str, Any]], method_synthesis: dict[str, Any]
) -> list[dict[str, Any]]:
    if not shortlist:
        return []
    primary = str(shortlist[0]["cp_method"])
    cells = cells_by_method(method_synthesis)
    output = []
    for comparator_row in shortlist[1:]:
        comparator = str(comparator_row["cp_method"])
        metric_rows = [
            paired_metric_summary(
                primary,
                comparator,
                cells.get(primary, {}),
                cells.get(comparator, {}),
                metric,
            )
            for metric in PAIRWISE_METRICS
        ]
        output.append(
            {
                "primary_method": primary,
                "comparator_method": comparator,
                "shared_dataset_alpha_cell_count": (
                    min(row["shared_cell_count"] for row in metric_rows)
                    if metric_rows
                    else 0
                ),
                "metric_comparisons": metric_rows,
            }
        )
    return output


def operating_criterion(shortlist: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "criterion_id": "predeclared_candidate_validation_criterion_v1",
        "status": "defined_for_future_validation_not_applied_as_final_selection",
        "candidate_methods": [row["cp_method"] for row in shortlist],
        "eligibility_filter": {
            "support_class": BROAD_SUPPORT_CLASS,
            "minimum_frontier_cell_count": SHORTLIST_FRONTIER_CELL_MIN,
            "exclude_validation_blocked_venn_abers": True,
            "require_method_spec_coverage": True,
        },
        "primary_operating_metric": PRIMARY_METRIC,
        "secondary_metrics": SECONDARY_METRICS,
        "coverage_guard": "method must maintain nominal or near-nominal empirical coverage within declared dataset-specific validation scope",
        "tie_break_rule": [
            "lower paired interval_score among cells passing the coverage guard",
            "lower paired absolute coverage error",
            "lower paired mean_width",
            "simpler and more stable method implementation when empirical evidence is indistinguishable",
        ],
        "post_selection_requirement": "rerun or reserve a post-selection validation surface before any final method/model winner language",
    }


def build_payload(
    root: Path,
    method_synthesis_path: Path,
    selection_protocol_path: Path,
    final_boundary_path: Path,
    venn_readiness_path: Path,
) -> dict[str, Any]:
    method_synthesis = read_json(method_synthesis_path)
    selection_protocol = read_json(selection_protocol_path)
    final_boundary = read_json(final_boundary_path)
    venn_readiness = read_json(venn_readiness_path)
    method_summary = method_synthesis.get("summary") or {}
    selection_summary = selection_protocol.get("summary") or {}
    final_summary = final_boundary.get("summary") or {}
    venn_summary = venn_readiness.get("summary") or {}

    shortlist = candidate_method_rows(method_synthesis)
    exclusions = exclusion_rows(method_synthesis, venn_readiness)
    comparisons = paired_comparisons(shortlist, method_synthesis)
    primary = shortlist[0]["cp_method"] if shortlist else None
    checks = [
        {
            "check_id": "method_synthesis_ready",
            "status": (
                "pass"
                if method_summary.get("overall_status")
                == "method_performance_synthesis_descriptive_no_final_selection"
                and int(method_summary.get("failed_check_count") or 0) == 0
                else "fail"
            ),
            "observed": {
                "overall_status": method_summary.get("overall_status"),
                "failed_check_count": method_summary.get("failed_check_count"),
            },
        },
        {
            "check_id": "shortlist_has_minimum_candidates",
            "status": "pass" if len(shortlist) >= SHORTLIST_MIN_METHODS else "fail",
            "observed": {
                "shortlist_method_count": len(shortlist),
                "minimum": SHORTLIST_MIN_METHODS,
            },
        },
        {
            "check_id": "paired_comparisons_available",
            "status": "pass" if comparisons else "fail",
            "observed": {"paired_comparison_count": len(comparisons)},
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
            "check_id": "final_boundary_keeps_claim_blocked",
            "status": (
                "pass"
                if final_summary.get("claim_status") == "blocked"
                and int(final_summary.get("failed_check_count") or 0) == 0
                else "fail"
            ),
            "observed": {
                "claim_status": final_summary.get("claim_status"),
                "failed_check_count": final_summary.get("failed_check_count"),
            },
        },
        {
            "check_id": "venn_abers_validation_gate_blocks_venn_shortlist",
            "status": (
                "pass"
                if venn_summary.get("can_support_venn_abers_regression_validation")
                is False
                else "fail"
            ),
            "observed": {
                "can_support_venn_abers_regression_validation": venn_summary.get(
                    "can_support_venn_abers_regression_validation"
                )
            },
        },
        {
            "check_id": "no_final_selection_claim",
            "status": "pass",
            "observed": {"can_support_final_method_selection": False},
        },
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    status = (
        "method_selection_candidate_audit_ready_no_final_selection"
        if not failed_checks
        else "method_selection_candidate_audit_failed"
    )
    comparison_cells = [
        row.get("shared_dataset_alpha_cell_count", 0) for row in comparisons
    ]
    summary = {
        "overall_status": status,
        "failed_check_count": len(failed_checks),
        "source_completed_ledger_rows": method_summary.get("completed_ledger_rows"),
        "source_dataset_count": method_summary.get("dataset_count"),
        "source_dataset_alpha_cell_count": method_summary.get(
            "dataset_alpha_cell_count"
        ),
        "source_method_count": method_summary.get("method_count"),
        "shortlist_method_count": len(shortlist),
        "primary_candidate_method": primary,
        "paired_comparison_count": len(comparisons),
        "minimum_shared_pairwise_cell_count": (
            min(comparison_cells) if comparison_cells else 0
        ),
        "excluded_method_count": len(exclusions),
        "venn_abers_excluded_count": sum(
            1
            for row in exclusions
            if str(row.get("cp_method", "")).startswith("venn_abers")
        ),
        "can_support_final_method_selection": False,
        "claim_status": "candidate_shortlist_ready_no_final_selection",
        "selection_protocol_status": selection_summary.get("overall_status"),
        "final_selection_claim_status": final_summary.get("claim_status"),
        "venn_abers_validation_status": venn_summary.get("overall_status"),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "method_performance_synthesis": rel(method_synthesis_path, root),
            "selection_multiplicity_protocol": rel(selection_protocol_path, root),
            "final_selection_claim_boundary": rel(final_boundary_path, root),
            "venn_abers_validation_readiness": rel(venn_readiness_path, root),
        },
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": summary,
        "checks": checks,
        "failed_checks": failed_checks,
        "operating_criterion": operating_criterion(shortlist),
        "shortlist_methods": shortlist,
        "paired_comparisons": comparisons,
        "excluded_methods": exclusions,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Method Selection Candidate Audit",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Source completed rows: {summary['source_completed_ledger_rows']}",
        f"- Shortlist methods: {summary['shortlist_method_count']}",
        f"- Primary candidate: `{summary['primary_candidate_method']}`",
        f"- Paired comparisons: {summary['paired_comparison_count']}",
        f"- Claim status: `{summary['claim_status']}`",
        "",
        "This audit does not select a final conformal method.",
        "",
        "## Shortlist",
        "",
        "| cp_method | frontier cells | datasets | dataset-alpha cells | balanced nominal hit rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["shortlist_methods"]:
        lines.append(
            "| {cp_method} | {frontier} | {datasets} | {cells} | {nominal} |".format(
                cp_method=row["cp_method"],
                frontier=row.get("frontier_cell_count"),
                datasets=row.get("dataset_count"),
                cells=row.get("dataset_alpha_cell_count"),
                nominal=(
                    f"{float(row['balanced_cell_nominal_mean_hit_rate']):.6g}"
                    if row.get("balanced_cell_nominal_mean_hit_rate") is not None
                    else ""
                ),
            )
        )
    lines.extend(["", "## Paired Diagnostics", ""])
    for comparison in payload["paired_comparisons"]:
        lines.append(
            "### `{primary}` vs `{comparator}`".format(
                primary=comparison["primary_method"],
                comparator=comparison["comparator_method"],
            )
        )
        lines.append("")
        lines.append(
            "| metric | shared cells | primary wins | comparator wins | ties | sign-test p | mean diff | 95% CI |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
        for metric in comparison["metric_comparisons"]:
            diff = metric["difference_primary_minus_comparator"]
            ci = diff.get("ci95") or {}
            lines.append(
                "| {metric} | {cells} | {wins} | {losses} | {ties} | {p} | {mean} | [{low}, {high}] |".format(
                    metric=metric["metric"],
                    cells=metric["shared_cell_count"],
                    wins=metric["primary_win_count"],
                    losses=metric["comparator_win_count"],
                    ties=metric["tie_count"],
                    p=(
                        f"{float(metric['exact_sign_test_two_sided_p']):.6g}"
                        if metric.get("exact_sign_test_two_sided_p") is not None
                        else ""
                    ),
                    mean=(
                        f"{float(diff['mean']):.6g}"
                        if diff.get("mean") is not None
                        else ""
                    ),
                    low=(
                        f"{float(ci['low']):.6g}" if ci.get("low") is not None else ""
                    ),
                    high=(
                        f"{float(ci['high']):.6g}" if ci.get("high") is not None else ""
                    ),
                )
            )
        lines.append("")
    lines.extend(["## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    payload = build_payload(
        root,
        (root / args.method_synthesis).resolve(),
        (root / args.selection_protocol).resolve(),
        (root / args.final_boundary).resolve(),
        (root / args.venn_readiness).resolve(),
    )
    out_path = (root / args.out).resolve()
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "primary_candidate_method": payload["summary"][
                    "primary_candidate_method"
                ],
                "shortlist_method_count": payload["summary"]["shortlist_method_count"],
                "paired_comparison_count": payload["summary"][
                    "paired_comparison_count"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
