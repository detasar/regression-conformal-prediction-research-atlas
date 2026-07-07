"""Build a resumable expansion plan for Venn-Abers score-grid validation.

The exact score-grid reference is currently a diagnostic subset. This planner
does not score new rows; it records the row-level work queue needed to expand
the reference toward full-test validation without losing progress between
server restarts.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts import audit_venn_abers_grid_ivapd_validation_protocol as protocol


SCHEMA = "cpfi_regression_venn_abers_grid_expansion_plan_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "venn_abers_grid_expansion_plan.json"
DEFAULT_NEXT_BATCH_SIZE = 25
DEFAULT_STATE = Path(
    "experiments/regression/results/venn_abers_grid_expansion/checkpoints/row_results.jsonl"
)
WORKER_ROW_SCHEMA = "cpfi_regression_venn_abers_grid_expansion_row_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument(
        "--next-batch-size",
        type=int,
        default=DEFAULT_NEXT_BATCH_SIZE,
        help="Maximum row tasks to propose per diagnostic run for the next worker cycle.",
    )
    parser.add_argument(
        "--state",
        default=str(DEFAULT_STATE),
        help="Optional worker JSONL ledger whose completed rows should be counted.",
    )
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
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_no}: {exc}") from exc
        if isinstance(row, dict):
            rows.append(row)
    return rows


def worker_task_key(row: dict[str, Any]) -> tuple[str, str, int] | None:
    try:
        test_index = int(row.get("test_index"))
    except (TypeError, ValueError):
        return None
    report_id = row.get("report_id")
    run_id = row.get("run_id")
    if report_id is None or run_id is None:
        return None
    return (str(report_id), str(run_id), test_index)


def serialize_task_key(key: tuple[str, str, int]) -> dict[str, Any]:
    return {"report_id": key[0], "run_id": key[1], "test_index": key[2]}


def worker_state_index(root: Path, state_path: Path) -> dict[str, Any]:
    rows = read_jsonl(state_path)
    completed_by_run: dict[tuple[str, str], set[int]] = defaultdict(set)
    failed_by_run: Counter[tuple[str, str]] = Counter()
    status_counts = Counter()
    duplicate_completed_keys = 0
    completed_keys = []
    completed_task_keys: set[tuple[str, str, int]] = set()
    failed_task_keys: set[tuple[str, str, int]] = set()
    failed_without_task_key_count = 0

    for row in rows:
        if row.get("schema") != WORKER_ROW_SCHEMA:
            continue
        status = str(row.get("status"))
        status_counts[status] += 1
        key = (str(row.get("report_id")), str(row.get("run_id")))
        if status == "completed":
            try:
                test_index = int(row.get("test_index"))
            except (TypeError, ValueError):
                continue
            completed_by_run[key].add(test_index)
            completed_task_keys.add((key[0], key[1], test_index))
            if row.get("row_key"):
                completed_keys.append(str(row["row_key"]))
        elif status == "failed":
            failed_by_run[key] += 1
            task_key = worker_task_key(row)
            if task_key is None:
                failed_without_task_key_count += 1
            else:
                failed_task_keys.add(task_key)

    duplicate_completed_keys = len(completed_keys) - len(set(completed_keys))
    return {
        "path": rel(state_path, root),
        "exists": state_path.exists(),
        "record_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "completed_by_run": completed_by_run,
        "failed_by_run": failed_by_run,
        "completed_task_keys": completed_task_keys,
        "failed_task_keys": failed_task_keys,
        "failed_without_task_key_count": failed_without_task_key_count,
        "completed_row_count": sum(len(values) for values in completed_by_run.values()),
        "failed_row_count": sum(failed_by_run.values()),
        "failed_task_key_count": len(failed_task_keys),
        "duplicate_completed_key_count": duplicate_completed_keys,
    }


def as_int_set(values: Any) -> set[int]:
    if not isinstance(values, list):
        return set()
    rows = set()
    for value in values:
        try:
            rows.add(int(value))
        except (TypeError, ValueError):
            continue
    return rows


def spread_indices(values: list[int], size: int) -> list[int]:
    if size <= 0 or not values:
        return []
    if len(values) <= size:
        return list(values)
    if size == 1:
        return [values[0]]
    selected_positions = []
    for idx in range(size):
        pos = round(idx * (len(values) - 1) / (size - 1))
        if pos not in selected_positions:
            selected_positions.append(pos)
    selected = [values[pos] for pos in selected_positions]
    if len(selected) < size:
        selected_set = set(selected)
        for value in values:
            if value not in selected_set:
                selected.append(value)
                selected_set.add(value)
            if len(selected) == size:
                break
    return sorted(selected)


def index_ranges(values: list[int]) -> list[dict[str, int]]:
    if not values:
        return []
    ordered = sorted(set(values))
    ranges = []
    start = prev = ordered[0]
    for value in ordered[1:]:
        if value == prev + 1:
            prev = value
            continue
        ranges.append({"start": start, "end": prev, "count": prev - start + 1})
        start = prev = value
    ranges.append({"start": start, "end": prev, "count": prev - start + 1})
    return ranges


def run_task(
    report_id: str,
    role: str,
    report_path: Path,
    result: dict[str, Any],
    next_batch_size: int,
    worker_state: dict[str, Any],
) -> dict[str, Any]:
    grid = result.get("venn_abers_quantile_grid_reference") or {}
    available = int(grid.get("test_rows_available") or 0)
    source_completed = sorted(
        value for value in as_int_set(grid.get("selected_test_indices")) if 0 <= value < available
    )
    run_key = (report_id, str(result.get("run_id")))
    worker_completed = sorted(
        value
        for value in worker_state["completed_by_run"].get(run_key, set())
        if 0 <= value < available
    )
    completed = sorted(set(source_completed) | set(worker_completed))
    completed_set = set(completed)
    pending = [idx for idx in range(available) if idx not in completed_set]
    pending_set = set(pending)
    worker_failed_indices = sorted(
        key[2]
        for key in worker_state["failed_task_keys"]
        if (key[0], key[1]) == run_key and 0 <= key[2] < available
    )
    superseded_failed_indices = [
        idx for idx in worker_failed_indices if idx in completed_set
    ]
    pending_failed_indices = [idx for idx in worker_failed_indices if idx in pending_set]
    unresolved_failed_indices = sorted(
        set(worker_failed_indices)
        - set(superseded_failed_indices)
        - set(pending_failed_indices)
    )
    next_batch = spread_indices(pending, next_batch_size)
    status = (
        "complete"
        if not pending and available > 0
        else "not_applicable"
        if available <= 0
        else "pending"
    )
    return {
        "task_id": (
            f"{report_id}:{result.get('run_id')}:"
            "venn_abers_quantile_grid_reference"
        ),
        "report_id": report_id,
        "role": role,
        "report_path": report_path.as_posix(),
        "run_id": result.get("run_id"),
        "dataset_id": result.get("dataset_id"),
        "model_id": result.get("model_id"),
        "model_family": result.get("model_family"),
        "seed": result.get("seed"),
        "alpha": result.get("alpha"),
        "prediction_artifact": result.get("prediction_artifact"),
        "prediction_cache_status": result.get("prediction_cache_status"),
        "test_rows_available": available,
        "source_completed_row_count": len(source_completed),
        "source_completed_row_indices": source_completed,
        "worker_completed_row_count": len(worker_completed),
        "worker_completed_row_indices": worker_completed,
        "worker_failed_row_count": int(worker_state["failed_by_run"].get(run_key, 0)),
        "worker_failed_task_key_count": len(worker_failed_indices),
        "worker_superseded_failed_row_count": len(superseded_failed_indices),
        "worker_pending_failed_row_count": len(pending_failed_indices),
        "worker_unresolved_failed_row_count": len(unresolved_failed_indices),
        "completed_row_count": len(completed),
        "completed_row_indices": completed,
        "pending_row_count": len(pending),
        "pending_row_ranges": index_ranges(pending),
        "next_batch_row_count": len(next_batch),
        "next_batch_row_indices": next_batch,
        "resume_key_fields": [
            "report_id",
            "run_id",
            "test_index",
            "score_grid_size",
            "prediction_artifact",
        ],
        "status": status,
    }


def build_payload(
    root: Path,
    next_batch_size: int,
    state_path: str | Path = DEFAULT_STATE,
) -> dict[str, Any]:
    if next_batch_size < 1:
        raise ValueError("next_batch_size must be positive")

    resolved_state_path = resolve(root, state_path)
    worker_state = worker_state_index(root, resolved_state_path)
    tasks = []
    source_rows = []
    for spec in protocol.source_report_specs():
        path = resolve(root, spec["json_path"])
        payload = read_json(path)
        exists = path.exists()
        source_rows.append(
            {
                "report_id": spec["report_id"],
                "role": spec["role"],
                "path": rel(path, root),
                "exists": exists,
                "result_count": len(payload.get("results") or []),
            }
        )
        for result in payload.get("results") or []:
            if isinstance(result, dict):
                tasks.append(
                    run_task(
                        str(spec["report_id"]),
                        str(spec["role"]),
                        Path(spec["json_path"]),
                        result,
                        next_batch_size,
                        worker_state,
                    )
                )

    total_available = sum(int(row["test_rows_available"]) for row in tasks)
    total_completed = sum(int(row["completed_row_count"]) for row in tasks)
    total_pending = sum(int(row["pending_row_count"]) for row in tasks)
    completed_task_keys = {
        (str(row["report_id"]), str(row["run_id"]), int(idx))
        for row in tasks
        for idx in row["completed_row_indices"]
    }
    pending_task_keys = {
        (str(row["report_id"]), str(row["run_id"]), int(idx))
        for row in tasks
        for pending_range in row["pending_row_ranges"]
        for idx in range(
            int(pending_range["start"]),
            int(pending_range["end"]) + 1,
        )
    }
    failed_task_keys = set(worker_state["failed_task_keys"])
    superseded_failed_task_keys = failed_task_keys & completed_task_keys
    pending_failed_task_keys = failed_task_keys & pending_task_keys
    orphan_failed_task_keys = failed_task_keys - completed_task_keys - pending_task_keys
    failed_worker_rows_all_superseded_or_pending = (
        worker_state["failed_without_task_key_count"] == 0
        and not orphan_failed_task_keys
    )
    next_batch_total = sum(int(row["next_batch_row_count"]) for row in tasks)
    task_keys = [
        (row["report_id"], row["run_id"], idx)
        for row in tasks
        for idx in row["next_batch_row_indices"]
    ]
    duplicate_task_key_count = len(task_keys) - len(set(task_keys))
    status_counts = Counter(str(row["status"]) for row in tasks)
    panel_counts = Counter(str(row["report_id"]) for row in tasks)
    largest_pending = sorted(
        tasks,
        key=lambda row: int(row["pending_row_count"]),
        reverse=True,
    )[:8]
    expansion_ready = (
        bool(tasks)
        and total_pending > 0
        and next_batch_total > 0
        and duplicate_task_key_count == 0
        and all(row["exists"] for row in source_rows)
    )
    expansion_complete = (
        bool(tasks)
        and total_available > 0
        and total_pending == 0
        and total_completed == total_available
        and next_batch_total == 0
        and duplicate_task_key_count == 0
        and all(row["exists"] for row in source_rows)
    )
    overall_status = (
        "venn_abers_grid_expansion_plan_ready"
        if expansion_ready
        else "venn_abers_grid_expansion_plan_complete"
        if expansion_complete
        else "venn_abers_grid_expansion_plan_incomplete"
    )
    checks = [
        {
            "check_id": "source_reports_present",
            "status": "pass" if all(row["exists"] for row in source_rows) else "fail",
            "severity": "critical",
            "description": "All diagnostic reports used by the score-grid expansion plan are present.",
        },
        {
            "check_id": "row_tasks_identified",
            "status": "pass" if tasks and total_available > 0 else "fail",
            "severity": "critical",
            "description": "The plan identifies score-grid rows and their completed/pending state.",
        },
        {
            "check_id": "next_batches_are_unique",
            "status": "pass"
            if duplicate_task_key_count == 0
            and ((total_pending > 0 and next_batch_total > 0) or total_pending == 0)
            else "fail",
            "severity": "high",
            "description": "Next-batch row tasks have unique report/run/test-index keys.",
        },
        {
            "check_id": "resume_keys_declared",
            "status": "pass"
            if all(row.get("resume_key_fields") for row in tasks)
            else "fail",
            "severity": "high",
            "description": "Every task declares the fields needed for row-level resume.",
        },
        {
            "check_id": "worker_state_ledger_readable",
            "status": "pass",
            "severity": "medium",
            "description": (
                "The optional worker ledger was parsed; completed worker rows are "
                "counted and failed worker rows remain audit evidence only."
            ),
        },
        {
            "check_id": "failed_worker_rows_are_superseded_or_pending",
            "status": "pass" if failed_worker_rows_all_superseded_or_pending else "fail",
            "severity": "high",
            "description": (
                "Every retained failed worker row resolves to either an already "
                "completed score-grid task or a still-pending task key."
            ),
        },
    ]
    failed_check_count = sum(1 for row in checks if row["status"] == "fail")
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "plan_policy": {
            "next_batch_size_per_run": next_batch_size,
            "next_batch_selection": (
                "deterministic index-space spread over pending test indices; "
                "completed rows are excluded"
            ),
            "worker_unit": "one report_id + run_id + test_index score-grid row",
            "claim_boundary": (
                "This is a resumable work queue, not empirical validation evidence."
            ),
            "worker_state_counting": (
                "Source diagnostic selected rows and completed worker ledger rows are "
                "unioned; failed worker ledger rows are not counted as completed."
            ),
        },
        "summary": {
            "overall_status": overall_status,
            "failed_check_count": failed_check_count,
            "source_report_count": len(source_rows),
            "run_task_count": len(tasks),
            "task_status_counts": dict(sorted(status_counts.items())),
            "task_count_by_report": dict(sorted(panel_counts.items())),
            "total_test_rows_available": total_available,
            "total_grid_rows_completed": total_completed,
            "source_grid_rows_completed": sum(
                int(row["source_completed_row_count"]) for row in tasks
            ),
            "worker_grid_rows_completed": sum(
                int(row["worker_completed_row_count"]) for row in tasks
            ),
            "worker_grid_rows_failed": sum(int(row["worker_failed_row_count"]) for row in tasks),
            "worker_failed_task_key_count": worker_state["failed_task_key_count"],
            "worker_failed_without_task_key_count": worker_state[
                "failed_without_task_key_count"
            ],
            "worker_superseded_failed_task_key_count": len(
                superseded_failed_task_keys
            ),
            "worker_pending_failed_task_key_count": len(pending_failed_task_keys),
            "worker_orphan_failed_task_key_count": len(orphan_failed_task_keys),
            "failed_worker_rows_all_superseded_or_pending": (
                failed_worker_rows_all_superseded_or_pending
            ),
            "total_grid_rows_pending": total_pending,
            "grid_completion_fraction": (total_completed / total_available)
            if total_available
            else 0.0,
            "next_batch_total_rows": next_batch_total,
            "duplicate_next_batch_task_key_count": duplicate_task_key_count,
            "largest_pending_tasks": [
                {
                    "report_id": row["report_id"],
                    "run_id": row["run_id"],
                    "dataset_id": row["dataset_id"],
                    "model_id": row["model_id"],
                    "pending_row_count": row["pending_row_count"],
                    "test_rows_available": row["test_rows_available"],
                }
                for row in largest_pending
            ],
        },
        "worker_state": {
            "path": worker_state["path"],
            "exists": worker_state["exists"],
            "record_count": worker_state["record_count"],
            "status_counts": worker_state["status_counts"],
            "completed_row_count": worker_state["completed_row_count"],
            "failed_row_count": worker_state["failed_row_count"],
            "failed_task_key_count": worker_state["failed_task_key_count"],
            "failed_without_task_key_count": worker_state[
                "failed_without_task_key_count"
            ],
            "superseded_failed_task_key_count": len(superseded_failed_task_keys),
            "pending_failed_task_key_count": len(pending_failed_task_keys),
            "orphan_failed_task_key_count": len(orphan_failed_task_keys),
            "failed_worker_rows_all_superseded_or_pending": (
                failed_worker_rows_all_superseded_or_pending
            ),
            "orphan_failed_task_key_samples": [
                serialize_task_key(key) for key in sorted(orphan_failed_task_keys)[:25]
            ],
            "duplicate_completed_key_count": worker_state["duplicate_completed_key_count"],
        },
        "source_reports": source_rows,
        "checks": checks,
        "tasks": tasks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    policy = payload["plan_policy"]
    lines = [
        "# Venn-Abers Grid Expansion Plan",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Run tasks: {summary['run_task_count']}",
        f"- Grid rows completed: {summary['total_grid_rows_completed']} / {summary['total_test_rows_available']}",
        f"- Source diagnostic completed rows: {summary['source_grid_rows_completed']}",
        f"- Worker ledger completed rows: {summary['worker_grid_rows_completed']}",
        f"- Worker ledger failed rows: {summary['worker_grid_rows_failed']}",
        f"- Worker failed task keys superseded or pending: `{summary['failed_worker_rows_all_superseded_or_pending']}`",
        f"- Grid completion fraction: {summary['grid_completion_fraction']}",
        f"- Grid rows pending: {summary['total_grid_rows_pending']}",
        f"- Next batch rows: {summary['next_batch_total_rows']}",
        "",
        "## Plan Policy",
        "",
        f"- Worker unit: {policy['worker_unit']}",
        f"- Next batch size per run: {policy['next_batch_size_per_run']}",
        f"- Next batch selection: {policy['next_batch_selection']}",
        f"- Worker state counting: {policy['worker_state_counting']}",
        f"- Claim boundary: {policy['claim_boundary']}",
        "",
        "## Worker State",
        "",
        f"- Path: `{payload['worker_state']['path']}`",
        f"- Exists: `{payload['worker_state']['exists']}`",
        f"- Records: {payload['worker_state']['record_count']}",
        f"- Status counts: `{json.dumps(payload['worker_state']['status_counts'], sort_keys=True)}`",
        f"- Failed task keys: {payload['worker_state']['failed_task_key_count']}",
        f"- Superseded failed task keys: {payload['worker_state']['superseded_failed_task_key_count']}",
        f"- Pending failed task keys: {payload['worker_state']['pending_failed_task_key_count']}",
        f"- Orphan failed task keys: {payload['worker_state']['orphan_failed_task_key_count']}",
        f"- Duplicate completed row keys: {payload['worker_state']['duplicate_completed_key_count']}",
        "",
        "## Largest Pending Tasks",
        "",
        "| Report | Run | Dataset | Model | Pending | Available |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for row in summary["largest_pending_tasks"]:
        lines.append(
            "| "
            f"`{row['report_id']}` | "
            f"`{row['run_id']}` | "
            f"`{row['dataset_id']}` | "
            f"`{row['model_id']}` | "
            f"{row['pending_row_count']} | "
            f"{row['test_rows_available']} |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Severity |",
            "| --- | --- | --- |",
        ]
    )
    for row in payload["checks"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | {row['severity']} |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(root, next_batch_size=args.next_batch_size, state_path=args.state)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "out": rel(out_path, root),
                "failed_check_count": payload["summary"]["failed_check_count"],
                "run_task_count": payload["summary"]["run_task_count"],
                "total_grid_rows_pending": payload["summary"][
                    "total_grid_rows_pending"
                ],
                "next_batch_total_rows": payload["summary"]["next_batch_total_rows"],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
