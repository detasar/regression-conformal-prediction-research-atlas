"""Audit alpha-expansion execution closure for method-selection evidence.

The alpha-expansion batch artifact is a config-generation manifest. This audit
checks the current ledgers produced by that manifest, then reconciles them with
the refreshed alpha-expansion plan and post-selection validation results. It
does not select a final conformal method.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_method_selection_alpha_expansion_execution_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_PLAN = REPORT_DIR / "method_selection_alpha_expansion_plan.json"
DEFAULT_BATCH = REPORT_DIR / "method_selection_alpha_expansion_batch.json"
DEFAULT_POST_SELECTION_RESULTS = (
    REPORT_DIR / "method_selection_post_selection_validation_results.json"
)
DEFAULT_OUT = REPORT_DIR / "method_selection_alpha_expansion_execution_audit.json"


CLAIM_BOUNDARIES = [
    "This audit verifies execution closure for the alpha-expansion batch; it does not select a final conformal method.",
    "Completed alpha-expansion ledgers only close the alpha-support imbalance work queue.",
    "Final method/model selection remains blocked until dataset-specific final gates, endpoint, fairness/population, bounded-support, Venn-Abers validation, and post-selection claim boundaries pass.",
    "A historical batch generation execution label is reconciled against current ledgers before paper-readiness summaries cite alpha-support remediation.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument(
        "--plan",
        default=str(DEFAULT_PLAN),
        help="Current alpha-expansion plan JSON path.",
    )
    parser.add_argument(
        "--batch",
        default=str(DEFAULT_BATCH),
        help="Alpha-expansion batch JSON path.",
    )
    parser.add_argument(
        "--post-selection-results",
        default=str(DEFAULT_POST_SELECTION_RESULTS),
        help="Post-selection validation results JSON path.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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


def generated_config_rows(batch: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in batch.get("generated_configs", []) or []
        if isinstance(row, dict) and row.get("dataset_id")
    ]


def ledger_audit_rows(
    root: Path, generated_configs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for config in generated_configs:
        ledger_path = root / str(config.get("ledger") or "")
        ledger_rows = read_jsonl(ledger_path)
        status_counts = Counter(str(row.get("status") or "") for row in ledger_rows)
        completed_rows = [row for row in ledger_rows if row.get("status") == "completed"]
        expected_count = int(config.get("expected_atomic_run_count") or 0)
        target_alphas = {
            canonical_alpha(alpha) for alpha in config.get("target_alphas") or []
        }
        observed_alphas = {
            canonical_alpha(row.get("alpha"))
            for row in completed_rows
            if row.get("alpha") is not None
        }
        expected_methods = {str(method) for method in config.get("cp_methods") or []}
        observed_methods = {
            str(row.get("cp_method") or "")
            for row in completed_rows
            if row.get("cp_method")
        }
        expected_seeds = {int(seed) for seed in config.get("random_seeds") or []}
        observed_seeds = {
            int(row["seed"])
            for row in completed_rows
            if isinstance(row.get("seed"), int)
            or (isinstance(row.get("seed"), str) and str(row.get("seed")).isdigit())
        }
        expected_model_id = config.get("model_id")
        observed_model_ids = {
            str(row.get("model_id") or "")
            for row in completed_rows
            if row.get("model_id")
        }
        rows.append(
            {
                "dataset_id": config.get("dataset_id"),
                "experiment_id": config.get("experiment_id"),
                "config_path": config.get("config_path"),
                "ledger": config.get("ledger"),
                "ledger_present": ledger_path.exists(),
                "expected_atomic_run_count": expected_count,
                "ledger_row_count": len(ledger_rows),
                "completed_atomic_run_count": len(completed_rows),
                "status_counts": dict(sorted(status_counts.items())),
                "expected_target_alphas": sorted(target_alphas, key=alpha_sort_key),
                "observed_completed_alphas": sorted(observed_alphas, key=alpha_sort_key),
                "expected_methods": sorted(expected_methods),
                "observed_completed_methods": sorted(observed_methods),
                "expected_seeds": sorted(expected_seeds),
                "observed_completed_seeds": sorted(observed_seeds),
                "expected_model_id": expected_model_id,
                "observed_model_ids": sorted(observed_model_ids),
                "ledger_count_matches_expected": len(ledger_rows) == expected_count,
                "completed_count_matches_expected": len(completed_rows)
                == expected_count,
                "completed_design_matches_manifest": (
                    observed_alphas == target_alphas
                    and observed_methods == expected_methods
                    and observed_seeds == expected_seeds
                    and observed_model_ids == {str(expected_model_id)}
                ),
            }
        )
    return rows


def check_row(check_id: str, passed: bool, observed: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "observed": observed,
    }


def build_payload(
    root: Path,
    plan_path: Path,
    batch_path: Path,
    post_selection_results_path: Path,
) -> dict[str, Any]:
    plan = read_json(plan_path)
    batch = read_json(batch_path)
    post_selection_results = read_json(post_selection_results_path)
    plan_summary = plan.get("summary") or {}
    batch_summary = batch.get("summary") or {}
    post_summary = post_selection_results.get("summary") or {}
    configs = generated_config_rows(batch)
    ledger_rows = ledger_audit_rows(root, configs)

    total_expected = sum(
        int(row.get("expected_atomic_run_count") or 0) for row in ledger_rows
    )
    total_ledger_rows = sum(int(row.get("ledger_row_count") or 0) for row in ledger_rows)
    total_completed = sum(
        int(row.get("completed_atomic_run_count") or 0) for row in ledger_rows
    )
    stale_generation_label = (
        batch_summary.get("execution_status") == "configs_generated_not_yet_run"
        and total_completed == total_expected
        and total_expected > 0
    )
    observed_execution_status = (
        "ledgers_completed"
        if total_completed == total_expected and total_expected > 0
        else "ledgers_incomplete"
    )
    plan_no_longer_needs_expansion = (
        plan_summary.get("overall_status")
        == "method_selection_alpha_expansion_plan_not_needed"
        and int(plan_summary.get("additional_common_cells_needed_to_clear_threshold") or 0)
        == 0
        and int(plan_summary.get("failed_check_count") or 0) == 0
    )
    post_selection_complete = (
        post_summary.get("overall_status")
        == "method_selection_post_selection_validation_results_ready_no_final_selection"
        and int(post_summary.get("completed_atomic_run_count") or 0)
        == int(post_summary.get("expected_atomic_run_count") or -1)
        and int(post_summary.get("common_dataset_alpha_cell_count") or 0)
        == int(post_summary.get("expected_common_dataset_alpha_cell_count") or -1)
        and int(post_summary.get("failed_check_count") or 0) == 0
    )
    checks = [
        check_row(
            "batch_manifest_present",
            batch_summary.get("overall_status")
            == "method_selection_alpha_expansion_batch_ready"
            and bool(configs),
            {
                "batch_overall_status": batch_summary.get("overall_status"),
                "generated_config_count": len(configs),
            },
        ),
        check_row(
            "generated_config_ledgers_present",
            all(row["ledger_present"] for row in ledger_rows) and bool(ledger_rows),
            {
                "ledger_count": len(ledger_rows),
                "missing_ledgers": [
                    row["ledger"] for row in ledger_rows if not row["ledger_present"]
                ],
            },
        ),
        check_row(
            "ledger_counts_match_expected",
            all(row["ledger_count_matches_expected"] for row in ledger_rows)
            and total_ledger_rows == total_expected
            and total_expected > 0,
            {
                "total_ledger_rows": total_ledger_rows,
                "total_expected_atomic_run_count": total_expected,
                "mismatched_datasets": [
                    row["dataset_id"]
                    for row in ledger_rows
                    if not row["ledger_count_matches_expected"]
                ],
            },
        ),
        check_row(
            "ledger_statuses_completed",
            all(row["completed_count_matches_expected"] for row in ledger_rows)
            and total_completed == total_expected
            and total_expected > 0,
            {
                "total_completed_atomic_run_count": total_completed,
                "total_expected_atomic_run_count": total_expected,
                "status_counts_by_dataset": {
                    row["dataset_id"]: row["status_counts"] for row in ledger_rows
                },
            },
        ),
        check_row(
            "completed_design_matches_manifest",
            all(row["completed_design_matches_manifest"] for row in ledger_rows)
            and bool(ledger_rows),
            {
                "mismatched_datasets": [
                    row["dataset_id"]
                    for row in ledger_rows
                    if not row["completed_design_matches_manifest"]
                ],
            },
        ),
        check_row(
            "refreshed_plan_no_longer_needs_alpha_expansion",
            plan_no_longer_needs_expansion,
            {
                "plan_overall_status": plan_summary.get("overall_status"),
                "additional_common_cells_needed_to_clear_threshold": plan_summary.get(
                    "additional_common_cells_needed_to_clear_threshold"
                ),
                "current_common_alpha_max_cell_share": plan_summary.get(
                    "current_common_alpha_max_cell_share"
                ),
                "imbalance_share_threshold": plan_summary.get(
                    "imbalance_share_threshold"
                ),
            },
        ),
        check_row(
            "post_selection_validation_results_complete",
            post_selection_complete,
            {
                "post_selection_status": post_summary.get("overall_status"),
                "completed_atomic_run_count": post_summary.get(
                    "completed_atomic_run_count"
                ),
                "expected_atomic_run_count": post_summary.get(
                    "expected_atomic_run_count"
                ),
                "common_dataset_alpha_cell_count": post_summary.get(
                    "common_dataset_alpha_cell_count"
                ),
                "expected_common_dataset_alpha_cell_count": post_summary.get(
                    "expected_common_dataset_alpha_cell_count"
                ),
            },
        ),
        check_row(
            "no_final_selection_claim",
            plan_summary.get("can_support_final_method_selection") is False
            and batch_summary.get("can_support_final_method_selection") is False
            and post_summary.get("can_support_final_method_selection") is False
            and plan_summary.get("final_selection_claim_status") == "blocked",
            {
                "plan_can_support_final_method_selection": plan_summary.get(
                    "can_support_final_method_selection"
                ),
                "batch_can_support_final_method_selection": batch_summary.get(
                    "can_support_final_method_selection"
                ),
                "post_selection_can_support_final_method_selection": post_summary.get(
                    "can_support_final_method_selection"
                ),
                "plan_final_selection_claim_status": plan_summary.get(
                    "final_selection_claim_status"
                ),
            },
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    status = (
        "method_selection_alpha_expansion_execution_closed_no_final_selection"
        if not failed_checks
        else "method_selection_alpha_expansion_execution_blocked"
    )
    batch_reconciliation_status = "source_status_current"
    if batch_summary.get("execution_status") == "configs_generated_not_yet_run":
        batch_reconciliation_status = (
            "reconciled_historical_config_generation_label_with_completed_ledgers"
            if observed_execution_status == "ledgers_completed" and not failed_checks
            else "unreconciled_ledgers_not_complete"
        )
    batch_reconciliation_requires_action = (
        batch_reconciliation_status == "unreconciled_ledgers_not_complete"
    )
    active_execution_status = (
        observed_execution_status
        if not batch_reconciliation_requires_action
        else batch_summary.get("execution_status")
    )
    batch_generation_label_historical_only = (
        stale_generation_label and not batch_reconciliation_requires_action
    )
    execution_metadata_consistency_status = "source_status_current"
    if batch_generation_label_historical_only:
        execution_metadata_consistency_status = (
            "historical_batch_generation_label_reconciled_no_action_required"
        )
    elif batch_reconciliation_requires_action:
        execution_metadata_consistency_status = (
            "unreconciled_execution_metadata_requires_action"
        )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "method_selection_alpha_expansion_plan": rel(plan_path, root),
            "method_selection_alpha_expansion_batch": rel(batch_path, root),
            "method_selection_post_selection_validation_results": rel(
                post_selection_results_path, root
            ),
        },
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "overall_status": status,
            "failed_check_count": len(failed_checks),
            "batch_overall_status": batch_summary.get("overall_status"),
            "batch_reported_execution_status": batch_summary.get("execution_status"),
            "batch_reported_execution_status_is_historical": batch_generation_label_historical_only,
            "batch_generation_label_stale_after_execution": stale_generation_label,
            "batch_generation_label_historical_only": batch_generation_label_historical_only,
            "batch_generation_label_reconciliation_status": batch_reconciliation_status,
            "batch_generation_label_requires_action": batch_reconciliation_requires_action,
            "execution_metadata_consistency_status": execution_metadata_consistency_status,
            "active_execution_status": active_execution_status,
            "reconciled_execution_status": active_execution_status,
            "observed_execution_status": observed_execution_status,
            "generated_config_count": len(configs),
            "dataset_count": len({row.get("dataset_id") for row in ledger_rows}),
            "expected_atomic_run_count": total_expected,
            "ledger_row_count": total_ledger_rows,
            "completed_atomic_run_count": total_completed,
            "plan_overall_status": plan_summary.get("overall_status"),
            "plan_additional_common_cells_needed_to_clear_threshold": plan_summary.get(
                "additional_common_cells_needed_to_clear_threshold"
            ),
            "plan_current_common_alpha_distribution": plan_summary.get(
                "current_common_alpha_distribution"
            ),
            "plan_current_common_alpha_max_cell_share": plan_summary.get(
                "current_common_alpha_max_cell_share"
            ),
            "plan_current_common_alpha_imbalance_status": plan_summary.get(
                "current_common_alpha_imbalance_status"
            ),
            "post_selection_validation_status": post_summary.get("overall_status"),
            "post_selection_completed_atomic_run_count": post_summary.get(
                "completed_atomic_run_count"
            ),
            "post_selection_expected_atomic_run_count": post_summary.get(
                "expected_atomic_run_count"
            ),
            "post_selection_common_dataset_alpha_cell_count": post_summary.get(
                "common_dataset_alpha_cell_count"
            ),
            "post_selection_expected_common_dataset_alpha_cell_count": post_summary.get(
                "expected_common_dataset_alpha_cell_count"
            ),
            "post_selection_diagnostic_winner_counts": post_summary.get(
                "diagnostic_winner_counts"
            ),
            "can_support_final_method_selection": False,
            "claim_status": "alpha_expansion_execution_closed_no_final_selection",
            "final_selection_claim_status": "blocked",
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "ledger_rows": ledger_rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Method Selection Alpha Expansion Execution Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Observed execution status: `{summary['observed_execution_status']}`",
        f"- Active execution status: `{summary['active_execution_status']}`",
        f"- Reconciled execution status: `{summary['reconciled_execution_status']}`",
        f"- Batch reported execution status: `{summary['batch_reported_execution_status']}`; historical `{summary['batch_reported_execution_status_is_historical']}`",
        f"- Execution metadata consistency: `{summary['execution_metadata_consistency_status']}`",
        f"- Batch generation label reconciliation: `{summary['batch_generation_label_reconciliation_status']}`; requires action `{summary['batch_generation_label_requires_action']}`",
        f"- Completed / expected alpha-expansion rows: {summary['completed_atomic_run_count']} / {summary['expected_atomic_run_count']}",
        f"- Refreshed alpha plan: `{summary['plan_overall_status']}`; additional cells needed {summary['plan_additional_common_cells_needed_to_clear_threshold']}; max alpha share {summary['plan_current_common_alpha_max_cell_share']}",
        f"- Post-selection validation: `{summary['post_selection_validation_status']}` with {summary['post_selection_completed_atomic_run_count']} / {summary['post_selection_expected_atomic_run_count']} completed rows",
        f"- Claim status: `{summary['claim_status']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(["", "## Checks", "", "| Check | Status | Observed |", "| --- | --- | --- |"])
    for check in payload["checks"]:
        lines.append(
            f"| `{check['check_id']}` | `{check['status']}` | `{check.get('observed', {})}` |"
        )
    lines.extend(
        [
            "",
            "## Ledgers",
            "",
            "| Dataset | Ledger rows | Completed | Expected | Alphas | Methods |",
            "| --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in payload["ledger_rows"]:
        lines.append(
            "| `{dataset}` | {ledger_rows} | {completed} | {expected} | `{alphas}` | `{methods}` |".format(
                dataset=row["dataset_id"],
                ledger_rows=row["ledger_row_count"],
                completed=row["completed_atomic_run_count"],
                expected=row["expected_atomic_run_count"],
                alphas=row["observed_completed_alphas"],
                methods=row["observed_completed_methods"],
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    plan_path = resolve(root, args.plan)
    batch_path = resolve(root, args.batch)
    post_selection_results_path = resolve(root, args.post_selection_results)
    out_path = resolve(root, args.out)
    payload = build_payload(
        root,
        plan_path=plan_path,
        batch_path=batch_path,
        post_selection_results_path=post_selection_results_path,
    )
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "out": rel(out_path, root),
                "failed_checks": [row["check_id"] for row in payload["failed_checks"]],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
