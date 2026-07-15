"""Inspect a planned Benchmark v2 execution chunk.

The public Research Atlas includes Benchmark v2 preflight ledgers so future
execution can resume by chunk. This utility validates one planned chunk and
prints a compact JSON summary. It intentionally does not run ML experiments.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_CHUNKS_PATH = Path("atlas/benchmark_v2/preflight/execution_chunks.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and summarize a planned Benchmark v2 chunk."
    )
    parser.add_argument(
        "--package-root",
        default=".",
        help="Research Atlas package root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--chunks",
        default=str(DEFAULT_CHUNKS_PATH),
        help="Path to execution_chunks.json relative to package root.",
    )
    parser.add_argument("--chunk-id", required=True, help="Chunk identifier to inspect.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Required execution mode. Prints metadata without running experiments.",
    )
    return parser.parse_args()


def load_chunks(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema") != "regression_cp_benchmark_v2_execution_chunks_v1":
        raise SystemExit(f"Unexpected chunk schema in {path}: {payload.get('schema')}")
    return payload


def resolve_package_root(package_root_arg: str, chunks_arg: str) -> Path:
    """Resolve the Research Atlas package root from common invocation locations."""
    package_root = Path(package_root_arg).resolve()
    chunks_path = Path(chunks_arg)
    if chunks_path.is_absolute() or (package_root / chunks_path).exists():
        return package_root

    parent = package_root.parent
    if (parent / chunks_path).exists() and package_root.name == "reproducibility":
        return parent

    return package_root


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        raise SystemExit(
            "This public utility only supports --dry-run inspection. "
            "Benchmark v2 execution requires a separate private runner."
        )

    package_root = resolve_package_root(args.package_root, args.chunks)
    chunks_path = Path(args.chunks)
    if not chunks_path.is_absolute():
        chunks_path = package_root / chunks_path
    payload = load_chunks(chunks_path)

    chunk = next(
        (row for row in payload.get("chunks", []) if row.get("chunk_id") == args.chunk_id),
        None,
    )
    if chunk is None:
        known = ", ".join(row.get("chunk_id", "") for row in payload.get("chunks", [])[:5])
        raise SystemExit(f"Unknown chunk id {args.chunk_id!r}. First known chunks: {known}")

    run_grid_path = package_root / str(chunk["run_grid_path"])
    status_ledger_path = package_root / str(chunk["status_ledger_path"])
    summary = {
        "chunk_id": chunk["chunk_id"],
        "chunk_index": int(chunk["chunk_index"]),
        "status": payload["status"],
        "result_generation_status": payload["result_generation_status"],
        "paired_cell_start_index": int(chunk["paired_cell_start_index"]),
        "paired_cell_end_index": int(chunk["paired_cell_end_index"]),
        "paired_cell_count": int(chunk["paired_cell_count"]),
        "method_row_count": int(chunk["method_row_count"]),
        "first_paired_cell_key": chunk["first_paired_cell_key"],
        "last_paired_cell_key": chunk["last_paired_cell_key"],
        "first_method_row_key": chunk.get("first_method_row_key", ""),
        "last_method_row_key": chunk.get("last_method_row_key", ""),
        "checkpoint_dir_template": chunk["checkpoint_dir_template"],
        "run_grid_exists": run_grid_path.exists(),
        "status_ledger_exists": status_ledger_path.exists(),
        "dry_run_only": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
