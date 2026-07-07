"""Build inferential diagnostics for method-selection evidence.

This report summarizes uncertainty around the current diagnostic CQR preference
without promoting a final method-selection claim. It joins the broad
publication workbench, candidate shortlist, robustness audit, fresh-seed
post-selection validation, and main-result candidate surfaces into one
no-promotion inferential evidence record.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_method_selection_inferential_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_METHOD_SYNTHESIS = REPORT_DIR / "method_performance_synthesis.json"
DEFAULT_CANDIDATE_AUDIT = REPORT_DIR / "method_selection_candidate_audit.json"
DEFAULT_ROBUSTNESS_AUDIT = REPORT_DIR / "method_selection_robustness_audit.json"
DEFAULT_VALIDATION_RESULTS = (
    REPORT_DIR / "method_selection_post_selection_validation_results.json"
)
DEFAULT_MAIN_RESULT_CANDIDATE_RESULTS = (
    REPORT_DIR / "main_result_candidate_bundle_results.json"
)
DEFAULT_SELECTION_PROTOCOL = Path(
    "experiments/regression/manuscript/selection_multiplicity_protocol.json"
)
DEFAULT_FINAL_BOUNDARY = REPORT_DIR / "final_selection_claim_boundary_audit.json"
DEFAULT_OUT = REPORT_DIR / "method_selection_inferential_audit.json"

METRICS = ("coverage_error_abs", "interval_score", "mean_width")
LOWER_IS_BETTER = set(METRICS)
CI_Z = 1.96
MIN_CANDIDATE_SHARED_CELLS = 30
MIN_VALIDATION_COMMON_CELLS = 25
MIN_BOOTSTRAP_REPLICATES = 100
CLAIM_BOUNDARIES = [
    "This audit is inferential diagnostic evidence only; it does not select a final conformal method.",
    "Paired cells are not treated as independent populations for a publication claim; intervals and p-values are descriptive diagnostics.",
    "Fresh-seed post-selection validation is used as no-promotion validation evidence until all paper gates pass.",
    "CQR remains a diagnostic primary candidate, not a final winner, while final-selection, multiplicity, dataset, bounded-support, fairness, and Venn-Abers gates are blocked.",
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
        "--robustness-audit",
        default=str(DEFAULT_ROBUSTNESS_AUDIT),
        help="Method selection robustness audit JSON path.",
    )
    parser.add_argument(
        "--validation-results",
        default=str(DEFAULT_VALIDATION_RESULTS),
        help="Post-selection validation results JSON path.",
    )
    parser.add_argument(
        "--main-result-candidate-results",
        default=str(DEFAULT_MAIN_RESULT_CANDIDATE_RESULTS),
        help="Main-result candidate bundle results JSON path.",
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
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def mean_ci(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "ci95": None,
            "paired_standardized_effect_size": None,
        }
    avg = mean(values)
    med = median(values)
    std = stdev(values) if len(values) > 1 else 0.0
    half_width = CI_Z * std / math.sqrt(len(values)) if len(values) > 1 else 0.0
    effect = avg / std if std > 0 else None
    return {
        "count": len(values),
        "mean": avg,
        "median": med,
        "std": std,
        "ci95": {"low": avg - half_width, "high": avg + half_width},
        "paired_standardized_effect_size": effect,
    }


def wilson_ci(successes: int, total: int) -> dict[str, Any]:
    if total <= 0:
        return {"successes": successes, "total": total, "rate": None, "ci95": None}
    p = successes / total
    z2 = CI_Z**2
    denom = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / denom
    half = (
        CI_Z
        * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total)
        / denom
    )
    return {
        "successes": successes,
        "total": total,
        "rate": p,
        "ci95": {"low": max(0.0, centre - half), "high": min(1.0, centre + half)},
    }


def sign_test_two_sided_p(wins: int, losses: int) -> float | None:
    n = wins + losses
    if n == 0:
        return None
    tail = min(wins, losses)
    probability = sum(math.comb(n, k) for k in range(tail + 1)) / (2**n)
    return min(1.0, 2.0 * probability)


def metric_value(cell: dict[str, Any], method: str, metric: str) -> float | None:
    scores = cell.get("scores") or {}
    return as_float((scores.get(method) or {}).get(metric))


def paired_metric_summary(
    cells: list[dict[str, Any]],
    primary_method: str,
    comparator_method: str,
    metric: str,
) -> dict[str, Any]:
    diffs: list[float] = []
    wins = losses = ties = 0
    examples = []
    for cell in cells:
        primary_value = metric_value(cell, primary_method, metric)
        comparator_value = metric_value(cell, comparator_method, metric)
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
        if len(examples) < 12:
            examples.append(
                {
                    "dataset_id": cell.get("dataset_id"),
                    "alpha": cell.get("alpha"),
                    "seed": cell.get("seed"),
                    "primary_value": primary_value,
                    "comparator_value": comparator_value,
                    "difference_primary_minus_comparator": diff,
                    "winner": winner,
                }
            )
    non_tie = wins + losses
    return {
        "metric": metric,
        "orientation": (
            "lower_is_better" if metric in LOWER_IS_BETTER else "higher_is_better"
        ),
        "shared_cell_count": len(diffs),
        "primary_win_count": wins,
        "comparator_win_count": losses,
        "tie_count": ties,
        "primary_non_tie_win_rate": wins / non_tie if non_tie else None,
        "primary_win_rate_ci95": wilson_ci(wins, non_tie) if non_tie else None,
        "exact_sign_test_two_sided_p": sign_test_two_sided_p(wins, losses),
        "difference_primary_minus_comparator": mean_ci(diffs),
        "examples": examples,
    }


def validation_pairwise_rows(
    validation_results: dict[str, Any],
    primary_method: str,
    comparators: list[str],
) -> list[dict[str, Any]]:
    cells = ((validation_results.get("diagnostic_selection") or {}).get("per_cell")) or []
    rows = []
    for comparator in comparators:
        rows.append(
            {
                "primary_method": primary_method,
                "comparator_method": comparator,
                "surface": "fresh_seed_post_selection_validation",
                "metric_comparisons": [
                    paired_metric_summary(cells, primary_method, comparator, metric)
                    for metric in METRICS
                ],
            }
        )
    return rows


def candidate_pairwise_rows(candidate_audit: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for comparison in candidate_audit.get("paired_comparisons") or []:
        metric_rows = []
        for metric in comparison.get("metric_comparisons") or []:
            diff = metric.get("difference_primary_minus_comparator") or {}
            std = as_float(diff.get("std"))
            avg = as_float(diff.get("mean"))
            metric_rows.append(
                {
                    "metric": metric.get("metric"),
                    "orientation": metric.get("orientation"),
                    "shared_cell_count": metric.get("shared_cell_count"),
                    "primary_win_count": metric.get("primary_win_count"),
                    "comparator_win_count": metric.get("comparator_win_count"),
                    "tie_count": metric.get("tie_count"),
                    "primary_non_tie_win_rate": metric.get(
                        "primary_non_tie_win_rate"
                    ),
                    "primary_win_rate_ci95": wilson_ci(
                        as_int(metric.get("primary_win_count")),
                        as_int(metric.get("primary_win_count"))
                        + as_int(metric.get("comparator_win_count")),
                    ),
                    "exact_sign_test_two_sided_p": metric.get(
                        "exact_sign_test_two_sided_p"
                    ),
                    "difference_primary_minus_comparator": {
                        **diff,
                        "paired_standardized_effect_size": (
                            avg / std if avg is not None and std and std > 0 else None
                        ),
                    },
                }
            )
        output.append(
            {
                "primary_method": comparison.get("primary_method"),
                "comparator_method": comparison.get("comparator_method"),
                "surface": "publication_workbench_shared_dataset_alpha_cells",
                "shared_dataset_alpha_cell_count": comparison.get(
                    "shared_dataset_alpha_cell_count"
                ),
                "metric_comparisons": metric_rows,
            }
        )
    return output


def winner_rate_summaries(
    robustness: dict[str, Any],
    validation_results: dict[str, Any],
    main_result_candidate_results: dict[str, Any],
    primary_method: str,
) -> dict[str, Any]:
    robustness_summary = robustness.get("summary") or {}
    validation_summary = validation_results.get("summary") or {}
    main_summary = main_result_candidate_results.get("summary") or {}
    validation_winners = validation_summary.get("diagnostic_winner_counts") or {}
    main_winners = main_summary.get("diagnostic_winner_counts") or {}
    bootstrap_count = as_int(robustness_summary.get("bootstrap_primary_selection_count"))
    bootstrap_total = as_int(robustness_summary.get("bootstrap_replicates"))
    return {
        "robustness_common_cell_primary_win_rate": wilson_ci(
            as_int(robustness_summary.get("common_cell_primary_win_count")),
            as_int(robustness_summary.get("common_dataset_alpha_cell_count")),
        ),
        "robustness_bootstrap_primary_selection_rate": wilson_ci(
            bootstrap_count,
            bootstrap_total,
        ),
        "leave_one_dataset_primary_retention_rate": wilson_ci(
            as_int(robustness_summary.get("leave_one_dataset_primary_retained_count")),
            as_int(robustness_summary.get("leave_one_dataset_count")),
        ),
        "leave_one_alpha_primary_retention_rate": wilson_ci(
            as_int(robustness_summary.get("leave_one_alpha_primary_retained_count")),
            as_int(robustness_summary.get("leave_one_alpha_count")),
        ),
        "post_selection_validation_primary_win_rate": wilson_ci(
            as_int(validation_winners.get(primary_method)),
            as_int(validation_summary.get("common_dataset_alpha_cell_count")),
        ),
        "main_result_candidate_primary_win_rate": wilson_ci(
            as_int(main_winners.get(primary_method)),
            as_int(main_summary.get("complete_matched_cell_count")),
        ),
    }


def min_shared_cells(pairwise_rows: list[dict[str, Any]]) -> int:
    counts = [
        as_int(row.get("shared_dataset_alpha_cell_count"))
        for row in pairwise_rows
        if row.get("shared_dataset_alpha_cell_count") is not None
    ]
    return min(counts) if counts else 0


def build_payload(
    root: Path,
    method_synthesis_path: Path,
    candidate_audit_path: Path,
    robustness_audit_path: Path,
    validation_results_path: Path,
    main_result_candidate_results_path: Path,
    selection_protocol_path: Path,
    final_boundary_path: Path,
) -> dict[str, Any]:
    method_synthesis = read_json(method_synthesis_path)
    candidate_audit = read_json(candidate_audit_path)
    robustness = read_json(robustness_audit_path)
    validation_results = read_json(validation_results_path)
    main_candidate_results = read_json(main_result_candidate_results_path)
    selection_protocol = read_json(selection_protocol_path)
    final_boundary = read_json(final_boundary_path)

    method_summary = method_synthesis.get("summary") or {}
    candidate_summary = candidate_audit.get("summary") or {}
    robustness_summary = robustness.get("summary") or {}
    validation_summary = validation_results.get("summary") or {}
    main_candidate_summary = main_candidate_results.get("summary") or {}
    selection_summary = selection_protocol.get("summary") or {}
    final_summary = final_boundary.get("summary") or {}

    primary_method = str(candidate_summary.get("primary_candidate_method") or "")
    candidate_methods = [
        str(method)
        for method in robustness_summary.get("candidate_methods") or []
        if method
    ]
    if not candidate_methods:
        candidate_methods = [
            str(row.get("cp_method"))
            for row in candidate_audit.get("shortlist_methods") or []
            if row.get("cp_method")
        ]
    comparators = [method for method in candidate_methods if method != primary_method]
    candidate_pairs = candidate_pairwise_rows(candidate_audit)
    validation_pairs = validation_pairwise_rows(
        validation_results,
        primary_method,
        comparators,
    )
    winner_rates = winner_rate_summaries(
        robustness,
        validation_results,
        main_candidate_results,
        primary_method,
    )
    checks = [
        {
            "check_id": "method_performance_synthesis_ready",
            "status": (
                "pass"
                if method_summary.get("overall_status")
                == "method_performance_synthesis_descriptive_no_final_selection"
                and as_int(method_summary.get("failed_check_count")) == 0
                else "fail"
            ),
            "observed": {
                "overall_status": method_summary.get("overall_status"),
                "failed_check_count": method_summary.get("failed_check_count"),
            },
        },
        {
            "check_id": "candidate_audit_ready",
            "status": (
                "pass"
                if candidate_summary.get("overall_status")
                == "method_selection_candidate_audit_ready_no_final_selection"
                and as_int(candidate_summary.get("failed_check_count")) == 0
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
            "check_id": "candidate_pairwise_support_sufficient",
            "status": (
                "pass"
                if min_shared_cells(candidate_pairs) >= MIN_CANDIDATE_SHARED_CELLS
                else "fail"
            ),
            "observed": {
                "minimum_shared_cells": min_shared_cells(candidate_pairs),
                "threshold": MIN_CANDIDATE_SHARED_CELLS,
            },
        },
        {
            "check_id": "robustness_audit_ready",
            "status": (
                "pass"
                if robustness_summary.get("overall_status")
                == "method_selection_robustness_audit_ready_no_final_selection"
                and as_int(robustness_summary.get("failed_check_count")) == 0
                and robustness_summary.get("candidate_primary_method")
                == primary_method
                else "fail"
            ),
            "observed": {
                "overall_status": robustness_summary.get("overall_status"),
                "failed_check_count": robustness_summary.get("failed_check_count"),
                "candidate_primary_method": robustness_summary.get(
                    "candidate_primary_method"
                ),
            },
        },
        {
            "check_id": "bootstrap_replicates_sufficient",
            "status": (
                "pass"
                if as_int(robustness_summary.get("bootstrap_replicates"))
                >= MIN_BOOTSTRAP_REPLICATES
                else "fail"
            ),
            "observed": {
                "bootstrap_replicates": robustness_summary.get(
                    "bootstrap_replicates"
                ),
                "threshold": MIN_BOOTSTRAP_REPLICATES,
            },
        },
        {
            "check_id": "post_selection_validation_ready",
            "status": (
                "pass"
                if validation_summary.get("overall_status")
                == "method_selection_post_selection_validation_results_ready_no_final_selection"
                and as_int(validation_summary.get("failed_check_count")) == 0
                and as_int(validation_summary.get("common_dataset_alpha_cell_count"))
                >= MIN_VALIDATION_COMMON_CELLS
                else "fail"
            ),
            "observed": {
                "overall_status": validation_summary.get("overall_status"),
                "failed_check_count": validation_summary.get("failed_check_count"),
                "common_dataset_alpha_cell_count": validation_summary.get(
                    "common_dataset_alpha_cell_count"
                ),
                "threshold": MIN_VALIDATION_COMMON_CELLS,
            },
        },
        {
            "check_id": "main_result_candidate_results_ready",
            "status": (
                "pass"
                if main_candidate_summary.get("overall_status")
                == "main_result_candidate_bundle_results_completed_no_promotions"
                and as_int(main_candidate_summary.get("failed_check_count")) == 0
                else "fail"
            ),
            "observed": {
                "overall_status": main_candidate_summary.get("overall_status"),
                "failed_check_count": main_candidate_summary.get(
                    "failed_check_count"
                ),
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
            "check_id": "final_boundary_keeps_claim_blocked",
            "status": (
                "pass"
                if final_summary.get("claim_status") == "blocked"
                and as_int(final_summary.get("failed_check_count")) == 0
                else "fail"
            ),
            "observed": {
                "claim_status": final_summary.get("claim_status"),
                "failed_check_count": final_summary.get("failed_check_count"),
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
        "method_selection_inferential_audit_ready_no_final_selection"
        if not failed_checks
        else "method_selection_inferential_audit_failed"
    )
    robustness_common = winner_rates["robustness_common_cell_primary_win_rate"]
    bootstrap = winner_rates["robustness_bootstrap_primary_selection_rate"]
    post_selection = winner_rates["post_selection_validation_primary_win_rate"]
    main_candidate = winner_rates["main_result_candidate_primary_win_rate"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "method_performance_synthesis": rel(method_synthesis_path, root),
            "method_selection_candidate_audit": rel(candidate_audit_path, root),
            "method_selection_robustness_audit": rel(robustness_audit_path, root),
            "method_selection_post_selection_validation_results": rel(
                validation_results_path,
                root,
            ),
            "main_result_candidate_bundle_results": rel(
                main_result_candidate_results_path,
                root,
            ),
            "selection_multiplicity_protocol": rel(selection_protocol_path, root),
            "final_selection_claim_boundary": rel(final_boundary_path, root),
        },
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "overall_status": status,
            "failed_check_count": len(failed_checks),
            "primary_candidate_method": primary_method,
            "candidate_methods": candidate_methods,
            "candidate_method_count": len(candidate_methods),
            "candidate_pairwise_comparison_count": len(candidate_pairs),
            "candidate_min_shared_pairwise_cell_count": min_shared_cells(
                candidate_pairs
            ),
            "robustness_common_cell_primary_win_rate": robustness_common.get("rate"),
            "robustness_common_cell_primary_win_rate_ci95": robustness_common.get(
                "ci95"
            ),
            "bootstrap_primary_selection_rate": bootstrap.get("rate"),
            "bootstrap_primary_selection_rate_ci95": bootstrap.get("ci95"),
            "post_selection_validation_primary_win_rate": post_selection.get("rate"),
            "post_selection_validation_primary_win_rate_ci95": post_selection.get(
                "ci95"
            ),
            "main_result_candidate_primary_win_rate": main_candidate.get("rate"),
            "main_result_candidate_primary_win_rate_ci95": main_candidate.get("ci95"),
            "can_support_final_method_selection": False,
            "claim_status": "inferential_method_selection_evidence_ready_no_final_selection",
            "final_selection_claim_status": final_summary.get("claim_status"),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "winner_rate_intervals": winner_rates,
        "candidate_pairwise_diagnostics": candidate_pairs,
        "post_selection_validation_pairwise_diagnostics": validation_pairs,
    }


def format_ci(ci: dict[str, Any] | None) -> str:
    if not ci:
        return ""
    low = ci.get("low")
    high = ci.get("high")
    if low is None or high is None:
        return ""
    return f"[{float(low):.6g}, {float(high):.6g}]"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Method Selection Inferential Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Primary diagnostic candidate: `{summary['primary_candidate_method']}`",
        f"- Candidate methods: `{summary['candidate_methods']}`",
        f"- Claim status: `{summary['claim_status']}`",
        "",
        "This report does not select a final conformal method.",
        "",
        "## Winner-Rate Intervals",
        "",
        "| Surface | Successes | Total | Rate | 95% CI |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for label, row in payload["winner_rate_intervals"].items():
        lines.append(
            "| {label} | {successes} | {total} | {rate} | {ci} |".format(
                label=label,
                successes=row.get("successes"),
                total=row.get("total"),
                rate=(
                    f"{float(row['rate']):.6g}" if row.get("rate") is not None else ""
                ),
                ci=format_ci(row.get("ci95")),
            )
        )
    lines.extend(["", "## Fresh-Seed Post-Selection Pairwise Diagnostics", ""])
    for comparison in payload["post_selection_validation_pairwise_diagnostics"]:
        lines.append(
            f"### `{comparison['primary_method']}` vs `{comparison['comparator_method']}`"
        )
        lines.append("")
        lines.append(
            "| Metric | Cells | Primary wins | Comparator wins | Sign-test p | Mean diff | Effect size | 95% CI |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
        for metric in comparison["metric_comparisons"]:
            diff = metric["difference_primary_minus_comparator"]
            lines.append(
                "| {metric} | {cells} | {wins} | {losses} | {p} | {mean} | {effect} | {ci} |".format(
                    metric=metric["metric"],
                    cells=metric["shared_cell_count"],
                    wins=metric["primary_win_count"],
                    losses=metric["comparator_win_count"],
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
                    effect=(
                        f"{float(diff['paired_standardized_effect_size']):.6g}"
                        if diff.get("paired_standardized_effect_size") is not None
                        else ""
                    ),
                    ci=format_ci(diff.get("ci95")),
                )
            )
        lines.append("")
    lines.extend(["## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(
        root,
        resolve(root, args.method_synthesis),
        resolve(root, args.candidate_audit),
        resolve(root, args.robustness_audit),
        resolve(root, args.validation_results),
        resolve(root, args.main_result_candidate_results),
        resolve(root, args.selection_protocol),
        resolve(root, args.final_boundary),
    )
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "out": rel(out_path, root),
                "primary_candidate_method": payload["summary"][
                    "primary_candidate_method"
                ],
                "candidate_pairwise_comparison_count": payload["summary"][
                    "candidate_pairwise_comparison_count"
                ],
                "post_selection_validation_primary_win_rate": payload["summary"][
                    "post_selection_validation_primary_win_rate"
                ],
                "can_support_final_method_selection": payload["summary"][
                    "can_support_final_method_selection"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
