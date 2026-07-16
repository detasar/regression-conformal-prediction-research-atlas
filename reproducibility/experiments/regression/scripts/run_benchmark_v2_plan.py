"""Plan, summarize, or execute Benchmark v2 chunks.

This script is the orchestration layer above ``run_benchmark_v2_chunk``.  It
keeps Benchmark v2 execution resumable by preserving one ledger per chunk and a
separate aggregate status summary for the selected run plan.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiments.regression.scripts import run_benchmark_v2_chunk as chunk_runner


DEFAULT_SUMMARY_NAME = "benchmark_v2_execution_plan_summary.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize or execute the frozen Benchmark v2 chunk plan."
    )
    parser.add_argument(
        "--package-root",
        default=".",
        help="Research Atlas package root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--chunks",
        default=str(chunk_runner.DEFAULT_CHUNKS_PATH),
        help="Path to execution_chunks.json relative to package root.",
    )
    parser.add_argument(
        "--task-registry",
        default=str(chunk_runner.DEFAULT_TASK_REGISTRY_PATH),
        help="Task registry CSV path relative to package root.",
    )
    parser.add_argument(
        "--execution-root",
        default=str(chunk_runner.DEFAULT_EXECUTION_ROOT),
        help="Execution output root relative to the current source repository.",
    )
    parser.add_argument("--chunk-id", action="append", default=None)
    parser.add_argument("--chunk-index-min", type=int, default=None)
    parser.add_argument("--chunk-index-max", type=int, default=None)
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Maximum selected chunks to summarize or execute.",
    )
    parser.add_argument(
        "--max-method-rows-per-chunk",
        type=int,
        default=None,
        help="Optional cap passed to each chunk execution.",
    )
    parser.add_argument(
        "--cv-plus-max-train-rows",
        type=int,
        default=None,
        help="Optional computational cap passed to CV+ family methods.",
    )
    parser.add_argument(
        "--jackknife-plus-max-train-rows",
        type=int,
        default=None,
        help="Optional computational cap passed to jackknife+ family methods.",
    )
    parser.add_argument("--dataset-id", action="append", default=None)
    parser.add_argument("--task-variant-id", action="append", default=None)
    parser.add_argument("--split-regime", action="append", default=None)
    parser.add_argument("--learner-family", action="append", default=None)
    parser.add_argument("--cp-method", action="append", default=None)
    parser.add_argument("--alpha", action="append", type=float, default=None)
    parser.add_argument("--seed", action="append", type=int, default=None)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute selected chunks. Without this flag, only summarize status.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry rows whose latest chunk-ledger status is failed.",
    )
    parser.add_argument(
        "--retry-skipped-status",
        action="append",
        default=None,
        help=(
            "Retry rows whose latest chunk-ledger status matches this skipped "
            "status. Use this after adding support for a previously skipped regime."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force the underlying regression runner to overwrite checkpoints.",
    )
    parser.add_argument(
        "--output-summary",
        default=None,
        help=(
            "Aggregate summary JSON path. Defaults to "
            "<execution-root>/benchmark_v2_execution_plan_summary.json."
        ),
    )
    parser.add_argument(
        "--no-write-summary",
        action="store_true",
        help="Print the aggregate summary without writing it to disk.",
    )
    return parser.parse_args()


def resolve_execution_root(path_arg: str) -> Path:
    execution_root = Path(path_arg)
    if not execution_root.is_absolute():
        execution_root = Path.cwd() / execution_root
    return execution_root


def resolve_package_root(package_root_arg: str, chunks_arg: str) -> Path:
    return chunk_runner.resolve_package_root(package_root_arg, chunks_arg)


def load_chunk_payload(package_root: Path, chunks_arg: str) -> dict[str, Any]:
    chunks_path = Path(chunks_arg)
    if not chunks_path.is_absolute():
        chunks_path = package_root / chunks_path
    return chunk_runner.load_chunks(chunks_path)


def select_chunks(payload: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    allowed_ids = {str(item) for item in args.chunk_id or []}
    for chunk in payload.get("chunks", []):
        chunk_id = str(chunk.get("chunk_id", ""))
        chunk_index = int(chunk.get("chunk_index", 0))
        if allowed_ids and chunk_id not in allowed_ids:
            continue
        if args.chunk_index_min is not None and chunk_index < args.chunk_index_min:
            continue
        if args.chunk_index_max is not None and chunk_index > args.chunk_index_max:
            continue
        selected.append(chunk)
        if args.max_chunks is not None and len(selected) >= args.max_chunks:
            break
    return selected


def filtered_chunk_rows(
    package_root: Path,
    chunk: dict[str, Any],
    args: argparse.Namespace,
) -> list[dict[str, str]]:
    run_grid_path = package_root / str(chunk["run_grid_path"])
    rows = [
        row
        for row in chunk_runner.chunk_rows(run_grid_path, chunk)
        if chunk_runner.row_allowed(row, args)
    ]
    if args.max_method_rows_per_chunk is not None:
        return rows[: args.max_method_rows_per_chunk]
    return rows


def latest_status_by_method_row(ledger_path: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in chunk_runner.read_jsonl(ledger_path):
        method_row_key = str(row.get("method_row_key", ""))
        if method_row_key:
            latest[method_row_key] = row
    return latest


def summarize_chunk(
    package_root: Path,
    chunk: dict[str, Any],
    args: argparse.Namespace,
    execution_root: Path,
) -> dict[str, Any]:
    rows = filtered_chunk_rows(package_root, chunk, args)
    selected_keys = [str(row["method_row_key"]) for row in rows]
    chunk_execution_root = execution_root / str(chunk["chunk_id"])
    ledger_path = chunk_execution_root / "benchmark_v2_execution_ledger.jsonl"
    latest = latest_status_by_method_row(ledger_path)
    selected_latest = {key: latest[key] for key in selected_keys if key in latest}
    status_counts = Counter(str(row.get("status", "unknown")) for row in selected_latest.values())
    retry_statuses = {str(status) for status in args.retry_skipped_status or []}
    observed_terminal = sum(
        count
        for status, count in status_counts.items()
        if status in chunk_runner.EXECUTION_TERMINAL_STATUSES
        or status.startswith("skipped_")
        if status not in retry_statuses
    )
    pending = max(0, len(selected_keys) - observed_terminal)
    return {
        "chunk_id": str(chunk["chunk_id"]),
        "chunk_index": int(chunk["chunk_index"]),
        "selected_method_row_count": len(selected_keys),
        "observed_method_row_count": len(selected_latest),
        "terminal_method_row_count": observed_terminal,
        "pending_method_row_count": pending,
        "completed_method_row_count": status_counts.get("completed", 0),
        "failed_method_row_count": status_counts.get("failed", 0),
        "skipped_method_row_count": sum(
            count
            for status, count in status_counts.items()
            if status.startswith("skipped_") or status == "skipped_method"
            if status not in retry_statuses
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "ledger_path": str(ledger_path),
        "summary_path": str(chunk_execution_root / "chunk_execution_summary.json"),
    }


def chunk_args(args: argparse.Namespace, chunk_id: str) -> argparse.Namespace:
    return argparse.Namespace(
        package_root=args.package_root,
        chunks=args.chunks,
        chunk_id=chunk_id,
        dry_run=False,
        execute=True,
        task_registry=args.task_registry,
        execution_root=args.execution_root,
        max_method_rows=args.max_method_rows_per_chunk,
        cv_plus_max_train_rows=args.cv_plus_max_train_rows,
        jackknife_plus_max_train_rows=args.jackknife_plus_max_train_rows,
        dataset_id=args.dataset_id,
        task_variant_id=args.task_variant_id,
        split_regime=args.split_regime,
        learner_family=args.learner_family,
        cp_method=args.cp_method,
        alpha=args.alpha,
        seed=args.seed,
        retry_failed=args.retry_failed,
        retry_skipped_status=args.retry_skipped_status,
        force=args.force,
    )


def aggregate_summary(
    *,
    package_root: Path,
    payload: dict[str, Any],
    selected_chunks: list[dict[str, Any]],
    chunk_summaries: list[dict[str, Any]],
    executed_chunk_summaries: list[dict[str, Any]],
    execution_root: Path,
    executed: bool,
) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    for summary in chunk_summaries:
        status_counts.update(summary.get("status_counts", {}))
    return {
        "schema": "regression_cp_benchmark_v2_execution_plan_summary_v1",
        "package_root": str(package_root),
        "execution_root": str(execution_root),
        "source_chunk_count": int(payload.get("chunk_count", 0)),
        "selected_chunk_count": len(selected_chunks),
        "executed_this_invocation": executed,
        "executed_chunk_count": len(executed_chunk_summaries),
        "selected_method_row_count": sum(
            int(row["selected_method_row_count"]) for row in chunk_summaries
        ),
        "observed_method_row_count": sum(
            int(row["observed_method_row_count"]) for row in chunk_summaries
        ),
        "terminal_method_row_count": sum(
            int(row["terminal_method_row_count"]) for row in chunk_summaries
        ),
        "pending_method_row_count": sum(
            int(row["pending_method_row_count"]) for row in chunk_summaries
        ),
        "completed_method_row_count": sum(
            int(row["completed_method_row_count"]) for row in chunk_summaries
        ),
        "failed_method_row_count": sum(
            int(row["failed_method_row_count"]) for row in chunk_summaries
        ),
        "skipped_method_row_count": sum(
            int(row["skipped_method_row_count"]) for row in chunk_summaries
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "chunks": chunk_summaries,
        "executed_chunks": executed_chunk_summaries,
    }


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    package_root = resolve_package_root(args.package_root, args.chunks)
    payload = load_chunk_payload(package_root, args.chunks)
    selected_chunks = select_chunks(payload, args)
    execution_root = resolve_execution_root(args.execution_root)

    executed_chunk_summaries: list[dict[str, Any]] = []
    if args.execute:
        for chunk in selected_chunks:
            executed_chunk_summaries.append(
                chunk_runner.execute_chunk(
                    package_root=package_root,
                    chunk=chunk,
                    args=chunk_args(args, str(chunk["chunk_id"])),
                )
            )

    chunk_summaries = [
        summarize_chunk(package_root, chunk, args, execution_root)
        for chunk in selected_chunks
    ]
    summary = aggregate_summary(
        package_root=package_root,
        payload=payload,
        selected_chunks=selected_chunks,
        chunk_summaries=chunk_summaries,
        executed_chunk_summaries=executed_chunk_summaries,
        execution_root=execution_root,
        executed=args.execute,
    )

    if not args.no_write_summary:
        output_summary = (
            Path(args.output_summary)
            if args.output_summary
            else execution_root / DEFAULT_SUMMARY_NAME
        )
        if not output_summary.is_absolute():
            output_summary = Path.cwd() / output_summary
        write_summary(output_summary, summary)
        summary["summary_path"] = str(output_summary)

    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
