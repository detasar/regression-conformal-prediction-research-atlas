"""Plan alpha-support expansion for method-selection robustness.

This planner does not run models and does not select a final method. It turns
the current common-cell alpha imbalance into a deterministic, resumable queue of
dataset-alpha-method work items needed before a stronger final-selection claim
can be considered.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_method_selection_alpha_expansion_plan_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_METHOD_SYNTHESIS = REPORT_DIR / "method_performance_synthesis.json"
DEFAULT_CANDIDATE_AUDIT = REPORT_DIR / "method_selection_candidate_audit.json"
DEFAULT_ROBUSTNESS_AUDIT = REPORT_DIR / "method_selection_robustness_audit.json"
DEFAULT_CROSS_RUN = REPORT_DIR / "cross_run_integrity_audit.json"
DEFAULT_OUT = REPORT_DIR / "method_selection_alpha_expansion_plan.json"

ALPHA_IMBALANCE_SHARE_THRESHOLD = 0.75
DEFAULT_TARGET_ALPHAS = ("0.01", "0.05", "0.15", "0.2")
MAX_SOURCE_CONFIGS_PER_TASK = 3

CLAIM_BOUNDARIES = [
    "This artifact is a work-queue plan for alpha-support expansion; it does not run new models.",
    "The plan only addresses common-cell alpha imbalance for the current shortlisted methods.",
    "Completing this plan would not by itself select a final conformal method or close endpoint, fairness, bounded-support, or Venn-Abers validation gates.",
    "Recommended tasks should be executed through the normal resumable experiment runner and then re-audited before any manuscript claim is promoted.",
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
        "--robustness-audit",
        default=str(DEFAULT_ROBUSTNESS_AUDIT),
        help="Method selection robustness audit JSON path.",
    )
    parser.add_argument(
        "--cross-run",
        default=str(DEFAULT_CROSS_RUN),
        help="Cross-run integrity audit JSON path.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def canonical_alpha(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    if math.isnan(number) or math.isinf(number):
        return str(value).strip()
    return f"{number:.12g}"


def alpha_sort_key(value: str) -> tuple[int, float | str]:
    try:
        return (0, float(value))
    except ValueError:
        return (1, value)


def shortlisted_methods(candidate_audit: dict[str, Any]) -> list[str]:
    return [
        str(row.get("cp_method"))
        for row in candidate_audit.get("shortlist_methods") or []
        if row.get("cp_method")
    ]


def common_support_index(
    method_synthesis: dict[str, Any],
    candidate_methods: list[str],
) -> tuple[
    dict[tuple[str, str], set[str]],
    dict[tuple[str, str, str], dict[str, Any]],
]:
    candidate_set = set(candidate_methods)
    support: dict[tuple[str, str], set[str]] = defaultdict(set)
    cells: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in method_synthesis.get("dataset_alpha_method_cells") or []:
        method = str(row.get("cp_method") or "")
        if method not in candidate_set:
            continue
        dataset_id = str(row.get("dataset_id") or "")
        alpha = canonical_alpha(row.get("alpha"))
        if not dataset_id or not alpha:
            continue
        support[(dataset_id, alpha)].add(method)
        cells[(dataset_id, alpha, method)] = row
    return support, cells


def common_keys(
    support: dict[tuple[str, str], set[str]],
    candidate_methods: list[str],
) -> list[tuple[str, str]]:
    candidate_set = set(candidate_methods)
    return sorted(
        key for key, methods in support.items() if candidate_set <= methods
    )


def alpha_distribution(keys: list[tuple[str, str]]) -> dict[str, int]:
    return dict(sorted(Counter(alpha for _, alpha in keys).items(), key=lambda item: alpha_sort_key(item[0])))


def additional_cells_needed(
    dominant_count: int,
    total_count: int,
    threshold: float,
) -> int:
    if total_count <= 0 or dominant_count <= 0:
        return 0
    if dominant_count / total_count < threshold:
        return 0
    minimum_total = math.floor(dominant_count / threshold) + 1
    return max(0, minimum_total - total_count)


def target_alpha_counts(
    current_distribution: dict[str, int],
    dominant_alpha: str | None,
    target_alphas: list[str],
    additional_needed: int,
) -> dict[str, int]:
    target = Counter(current_distribution)
    for _ in range(additional_needed):
        alpha = min(
            target_alphas,
            key=lambda item: (target.get(item, 0), alpha_sort_key(item)),
        )
        target[alpha] += 1
    if dominant_alpha is not None:
        target.setdefault(dominant_alpha, current_distribution.get(dominant_alpha, 0))
    return dict(sorted(target.items(), key=lambda item: alpha_sort_key(item[0])))


def target_additions(
    current_distribution: dict[str, int],
    target_distribution: dict[str, int],
    dominant_alpha: str | None,
) -> dict[str, int]:
    return {
        alpha: max(0, int(target_distribution.get(alpha, 0)) - int(current_count))
        for alpha, current_count in sorted(
            current_distribution.items(), key=lambda item: alpha_sort_key(item[0])
        )
        if alpha != dominant_alpha
    } | {
        alpha: int(count)
        for alpha, count in sorted(
            target_distribution.items(), key=lambda item: alpha_sort_key(item[0])
        )
        if alpha != dominant_alpha and alpha not in current_distribution
    }


def config_id_from_payload(config_path: Path, payload: dict[str, Any]) -> str:
    return f"config:{payload.get('experiment_id', config_path.stem)}"


def config_source_index(
    root: Path,
    cross_run: dict[str, Any],
    candidate_methods: list[str],
    dominant_alpha: str | None,
) -> dict[str, list[dict[str, Any]]]:
    candidate_set = set(candidate_methods)
    by_dataset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cross_run.get("rows") or []:
        config_path_value = row.get("config_path")
        if not config_path_value:
            continue
        config_path = root / str(config_path_value)
        config = read_yaml(config_path)
        config_methods = {str(method) for method in config.get("cp_methods") or []}
        config_alphas = [canonical_alpha(alpha) for alpha in config.get("alphas") or []]
        if dominant_alpha and dominant_alpha not in config_alphas:
            continue
        if not candidate_set <= config_methods:
            continue
        for dataset_id in row.get("dataset_ids") or config.get("datasets") or []:
            dataset = str(dataset_id)
            by_dataset[dataset].append(
                {
                    "report_id": row.get("report_id"),
                    "report_name": row.get("report_name"),
                    "config_path": rel(config_path, root),
                    "config_id": config_id_from_payload(config_path, config),
                    "experiment_id": config.get("experiment_id"),
                    "current_alphas": config_alphas,
                    "cp_methods": sorted(config_methods),
                    "risk_level": row.get("risk_level"),
                    "ledger_rows": row.get("ledger_rows"),
                    "large_sweep": bool(row.get("large_sweep")),
                }
            )
    for dataset_id, rows in by_dataset.items():
        by_dataset[dataset_id] = sorted(
            rows,
            key=lambda item: (
                item.get("risk_level") != "pass",
                bool(item.get("large_sweep")),
                int(item.get("ledger_rows") or 0),
                str(item.get("config_path")),
            ),
        )
    return by_dataset


def source_common_row_count(
    dataset_id: str,
    dominant_alpha: str | None,
    candidate_methods: list[str],
    cells: dict[tuple[str, str, str], dict[str, Any]],
) -> int:
    if dominant_alpha is None:
        return 0
    return sum(
        int((cells.get((dataset_id, dominant_alpha, method)) or {}).get("row_count") or 0)
        for method in candidate_methods
    )


def build_task_pool(
    common_dataset_ids: list[str],
    target_alphas: list[str],
    support: dict[tuple[str, str], set[str]],
    cells: dict[tuple[str, str, str], dict[str, Any]],
    candidate_methods: list[str],
    dominant_alpha: str | None,
    source_configs: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    candidate_set = set(candidate_methods)
    rows = []
    for alpha in target_alphas:
        for dataset_id in common_dataset_ids:
            existing = support.get((dataset_id, alpha), set())
            missing = sorted(candidate_set - existing)
            if not missing:
                continue
            dataset_sources = source_configs.get(dataset_id, [])
            task_id = (
                "method_selection_alpha_expansion::"
                f"{dataset_id}::alpha_{alpha.replace('.', '_')}"
            )
            rows.append(
                {
                    "task_id": task_id,
                    "dataset_id": dataset_id,
                    "source_alpha": dominant_alpha,
                    "target_alpha": alpha,
                    "existing_candidate_methods_at_target_alpha": sorted(existing),
                    "missing_candidate_methods": missing,
                    "method_run_task_count": len(missing),
                    "estimated_common_cell_gain": 1,
                    "source_common_row_count": source_common_row_count(
                        dataset_id, dominant_alpha, candidate_methods, cells
                    ),
                    "status": (
                        "ready_for_config_clone"
                        if dataset_sources
                        else "blocked_missing_source_config"
                    ),
                    "configuration_action": (
                        "clone_or_extend_source_config_with_target_alpha"
                    ),
                    "source_configs": dataset_sources[:MAX_SOURCE_CONFIGS_PER_TASK],
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["status"] != "ready_for_config_clone",
            alpha_sort_key(str(row["target_alpha"])),
            -int(row["source_common_row_count"] or 0),
            str(row["dataset_id"]),
        ),
    )


def select_next_batch(
    task_pool: list[dict[str, Any]], required_additions_by_alpha: dict[str, int]
) -> list[dict[str, Any]]:
    selected = []
    for alpha, needed in sorted(
        required_additions_by_alpha.items(), key=lambda item: alpha_sort_key(item[0])
    ):
        if needed <= 0:
            continue
        alpha_tasks = [
            row
            for row in task_pool
            if row["target_alpha"] == alpha and row["status"] == "ready_for_config_clone"
        ]
        selected.extend(alpha_tasks[:needed])
    return sorted(selected, key=lambda row: (alpha_sort_key(str(row["target_alpha"])), str(row["dataset_id"])))


def method_run_tasks(dataset_alpha_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for task in dataset_alpha_tasks:
        for method in task["missing_candidate_methods"]:
            rows.append(
                {
                    "task_id": f"{task['task_id']}::method::{method}",
                    "dataset_alpha_task_id": task["task_id"],
                    "dataset_id": task["dataset_id"],
                    "target_alpha": task["target_alpha"],
                    "cp_method": method,
                    "configuration_action": task["configuration_action"],
                    "source_config_count": len(task.get("source_configs") or []),
                }
            )
    return rows


def max_alpha_share(distribution: dict[str, int]) -> float | None:
    total = sum(int(value) for value in distribution.values())
    if total <= 0:
        return None
    return max(int(value) for value in distribution.values()) / total


def build_payload(
    root: Path,
    method_synthesis_path: Path,
    candidate_audit_path: Path,
    robustness_audit_path: Path,
    cross_run_path: Path,
) -> dict[str, Any]:
    method_synthesis = read_json(method_synthesis_path)
    candidate_audit = read_json(candidate_audit_path)
    robustness_audit = read_json(robustness_audit_path)
    cross_run = read_json(cross_run_path)
    method_summary = method_synthesis.get("summary") or {}
    candidate_summary = candidate_audit.get("summary") or {}
    robustness_summary = robustness_audit.get("summary") or {}
    candidate_methods = shortlisted_methods(candidate_audit)
    support, cells = common_support_index(method_synthesis, candidate_methods)
    common = common_keys(support, candidate_methods)
    distribution = alpha_distribution(common)
    dominant_alpha = (
        max(distribution, key=lambda alpha: (distribution[alpha], -alpha_sort_key(alpha)[0], alpha))
        if distribution
        else None
    )
    if dominant_alpha is not None:
        dominant_alpha = str(dominant_alpha)
    dominant_count = int(distribution.get(dominant_alpha, 0) if dominant_alpha else 0)
    total_common = sum(distribution.values())
    current_share = max_alpha_share(distribution)
    imbalance_status = (
        "imbalanced_common_alpha_support"
        if current_share is not None
        and current_share >= ALPHA_IMBALANCE_SHARE_THRESHOLD
        else "no_large_alpha_concentration"
    )
    target_alphas = sorted(
        (
            set(DEFAULT_TARGET_ALPHAS)
            | {alpha for alpha in distribution if alpha != dominant_alpha}
        )
        - ({dominant_alpha} if dominant_alpha else set()),
        key=alpha_sort_key,
    )
    needed = additional_cells_needed(
        dominant_count, total_common, ALPHA_IMBALANCE_SHARE_THRESHOLD
    )
    target_distribution = target_alpha_counts(
        distribution, dominant_alpha, target_alphas, needed
    )
    additions_by_alpha = target_additions(
        distribution, target_distribution, dominant_alpha
    )
    common_dataset_ids = sorted({dataset_id for dataset_id, alpha in common if alpha == dominant_alpha})
    source_configs = config_source_index(
        root, cross_run, candidate_methods, dominant_alpha
    )
    task_pool = build_task_pool(
        common_dataset_ids,
        target_alphas,
        support,
        cells,
        candidate_methods,
        dominant_alpha,
        source_configs,
    )
    next_batch = select_next_batch(task_pool, additions_by_alpha)
    next_batch_method_tasks = method_run_tasks(next_batch)
    projected_distribution = Counter(distribution)
    for task in next_batch:
        projected_distribution[str(task["target_alpha"])] += 1
    projected_distribution_dict = dict(
        sorted(projected_distribution.items(), key=lambda item: alpha_sort_key(item[0]))
    )
    projected_share = max_alpha_share(projected_distribution_dict)
    projected_status = (
        "no_large_alpha_concentration"
        if projected_share is not None
        and projected_share < ALPHA_IMBALANCE_SHARE_THRESHOLD
        else imbalance_status
    )
    task_status_counts = Counter(row["status"] for row in task_pool)
    next_batch_alpha_counts = Counter(str(row["target_alpha"]) for row in next_batch)
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
            "check_id": "candidate_audit_ready",
            "status": (
                "pass"
                if candidate_summary.get("overall_status")
                == "method_selection_candidate_audit_ready_no_final_selection"
                and int(candidate_summary.get("failed_check_count") or 0) == 0
                and len(candidate_methods) >= 3
                else "fail"
            ),
            "observed": {
                "overall_status": candidate_summary.get("overall_status"),
                "failed_check_count": candidate_summary.get("failed_check_count"),
                "candidate_methods": candidate_methods,
            },
        },
        {
            "check_id": "robustness_audit_ready",
            "status": (
                "pass"
                if robustness_summary.get("overall_status")
                == "method_selection_robustness_audit_ready_no_final_selection"
                and int(robustness_summary.get("failed_check_count") or 0) == 0
                else "fail"
            ),
            "observed": {
                "overall_status": robustness_summary.get("overall_status"),
                "failed_check_count": robustness_summary.get("failed_check_count"),
            },
        },
        {
            "check_id": "dominant_alpha_identified",
            "status": "pass" if dominant_alpha else "fail",
            "observed": {
                "dominant_alpha": dominant_alpha,
                "current_common_alpha_distribution": distribution,
            },
        },
        {
            "check_id": "task_keys_unique",
            "status": (
                "pass"
                if len({row["task_id"] for row in task_pool}) == len(task_pool)
                and len({row["task_id"] for row in next_batch}) == len(next_batch)
                else "fail"
            ),
            "observed": {
                "task_pool_count": len(task_pool),
                "next_batch_task_count": len(next_batch),
            },
        },
        {
            "check_id": "planned_gain_sufficient_for_threshold",
            "status": (
                "pass"
                if needed == 0 or len(next_batch) >= needed
                else "fail"
            ),
            "observed": {
                "additional_common_cells_needed_to_clear_threshold": needed,
                "next_batch_dataset_alpha_task_count": len(next_batch),
            },
        },
        {
            "check_id": "source_config_traceability_present",
            "status": (
                "pass"
                if needed == 0
                or (
                    len(next_batch) >= needed
                    and all(row.get("source_configs") for row in next_batch)
                )
                else "fail"
            ),
            "observed": {
                "additional_common_cells_needed_to_clear_threshold": needed,
                "next_batch_dataset_alpha_task_count": len(next_batch),
                "next_batch_without_source_config": [
                    row["task_id"] for row in next_batch if not row.get("source_configs")
                ],
            },
        },
        {
            "check_id": "projected_alpha_concentration_clears_threshold",
            "status": (
                "pass"
                if needed == 0
                or (
                    projected_share is not None
                    and projected_share < ALPHA_IMBALANCE_SHARE_THRESHOLD
                )
                else "fail"
            ),
            "observed": {
                "projected_common_alpha_distribution": projected_distribution_dict,
                "projected_common_alpha_max_cell_share": projected_share,
                "threshold": ALPHA_IMBALANCE_SHARE_THRESHOLD,
            },
        },
        {
            "check_id": "no_final_selection_claim",
            "status": (
                "pass"
                if robustness_summary.get("can_support_final_method_selection") is False
                and robustness_summary.get("final_selection_claim_status") == "blocked"
                else "fail"
            ),
            "observed": {
                "robustness_can_support_final_method_selection": robustness_summary.get(
                    "can_support_final_method_selection"
                ),
                "robustness_final_selection_claim_status": robustness_summary.get(
                    "final_selection_claim_status"
                ),
            },
        },
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    if failed_checks:
        status = "method_selection_alpha_expansion_plan_failed"
        claim_status = "alpha_expansion_plan_failed_no_final_selection"
    elif needed == 0:
        status = "method_selection_alpha_expansion_plan_not_needed"
        claim_status = "alpha_expansion_not_needed_no_final_selection"
    else:
        status = "method_selection_alpha_expansion_plan_ready"
        claim_status = "alpha_expansion_plan_ready_no_final_selection"
    summary = {
        "overall_status": status,
        "failed_check_count": len(failed_checks),
        "source_completed_ledger_rows": method_summary.get("completed_ledger_rows"),
        "candidate_methods": candidate_methods,
        "candidate_method_count": len(candidate_methods),
        "dominant_alpha": dominant_alpha,
        "target_alphas": target_alphas,
        "current_common_dataset_alpha_cell_count": total_common,
        "current_common_dataset_count_at_dominant_alpha": len(common_dataset_ids),
        "current_common_alpha_distribution": distribution,
        "current_common_alpha_max_cell_share": current_share,
        "current_common_alpha_imbalance_status": imbalance_status,
        "imbalance_share_threshold": ALPHA_IMBALANCE_SHARE_THRESHOLD,
        "additional_common_cells_needed_to_clear_threshold": needed,
        "target_common_alpha_distribution": target_distribution,
        "target_additional_common_cells_by_alpha": additions_by_alpha,
        "task_pool_dataset_alpha_task_count": len(task_pool),
        "task_pool_method_run_task_count": sum(
            int(row["method_run_task_count"]) for row in task_pool
        ),
        "task_status_counts": dict(sorted(task_status_counts.items())),
        "next_batch_dataset_alpha_task_count": len(next_batch),
        "next_batch_method_run_task_count": len(next_batch_method_tasks),
        "next_batch_alpha_counts": dict(
            sorted(next_batch_alpha_counts.items(), key=lambda item: alpha_sort_key(item[0]))
        ),
        "planned_common_cell_gain": sum(
            int(row["estimated_common_cell_gain"]) for row in next_batch
        ),
        "projected_common_alpha_distribution_after_next_batch": projected_distribution_dict,
        "projected_common_alpha_max_cell_share_after_next_batch": projected_share,
        "projected_common_alpha_imbalance_status_after_next_batch": projected_status,
        "can_support_final_method_selection": False,
        "claim_status": claim_status,
        "final_selection_claim_status": robustness_summary.get(
            "final_selection_claim_status"
        ),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "method_performance_synthesis": rel(method_synthesis_path, root),
            "method_selection_candidate_audit": rel(candidate_audit_path, root),
            "method_selection_robustness_audit": rel(robustness_audit_path, root),
            "cross_run_integrity": rel(cross_run_path, root),
        },
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": summary,
        "checks": checks,
        "failed_checks": failed_checks,
        "task_pool": task_pool,
        "next_batch_dataset_alpha_tasks": next_batch,
        "next_batch_method_run_tasks": next_batch_method_tasks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Method Selection Alpha Expansion Plan",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Candidate methods: `{summary['candidate_methods']}`",
        f"- Dominant alpha: `{summary['dominant_alpha']}`",
        f"- Current common alpha distribution: `{summary['current_common_alpha_distribution']}`",
        f"- Current max alpha cell share: {summary['current_common_alpha_max_cell_share']}",
        f"- Imbalance status: `{summary['current_common_alpha_imbalance_status']}`",
        f"- Additional common cells needed: {summary['additional_common_cells_needed_to_clear_threshold']}",
        f"- Target common alpha distribution: `{summary['target_common_alpha_distribution']}`",
        f"- Next-batch dataset-alpha tasks: {summary['next_batch_dataset_alpha_task_count']}",
        f"- Next-batch method-run tasks: {summary['next_batch_method_run_task_count']}",
        f"- Projected max alpha cell share after next batch: {summary['projected_common_alpha_max_cell_share_after_next_batch']}",
        f"- Claim status: `{summary['claim_status']}`",
        "",
        "This plan does not select a final conformal method.",
        "",
        "## Next Batch",
        "",
        "| task | dataset | target alpha | missing methods | source configs |",
        "| --- | --- | ---: | --- | ---: |",
    ]
    for row in payload["next_batch_dataset_alpha_tasks"]:
        lines.append(
            "| `{task}` | `{dataset}` | {alpha} | `{methods}` | {configs} |".format(
                task=row["task_id"],
                dataset=row["dataset_id"],
                alpha=row["target_alpha"],
                methods=row["missing_candidate_methods"],
                configs=len(row.get("source_configs") or []),
            )
        )
    if not payload["next_batch_dataset_alpha_tasks"]:
        lines.append("|  |  |  |  |  |")
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
    payload = build_payload(
        root,
        (root / args.method_synthesis).resolve(),
        (root / args.candidate_audit).resolve(),
        (root / args.robustness_audit).resolve(),
        (root / args.cross_run).resolve(),
    )
    out_path = (root / args.out).resolve()
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "dominant_alpha": payload["summary"]["dominant_alpha"],
                "additional_common_cells_needed_to_clear_threshold": payload[
                    "summary"
                ]["additional_common_cells_needed_to_clear_threshold"],
                "next_batch_dataset_alpha_task_count": payload["summary"][
                    "next_batch_dataset_alpha_task_count"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
