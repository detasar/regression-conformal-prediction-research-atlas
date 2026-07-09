"""Run the generated model-matched CQR rerun configs sequentially.

The per-run experiment driver already owns scientific checkpointing and the
ledger schema. This wrapper only adds a durable batch event log around the 29
generated rerun configs so a long run can be restarted without losing context.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path(
    "experiments/regression/reports/model_matched_cqr_rerun_plan/"
    "model_matched_cqr_rerun_manifest.json"
)
DEFAULT_STATE_JSONL = Path(
    "experiments/regression/results/model_matched_cqr_rerun_batch/batch_events.jsonl"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    rows = manifest.get("generated_configs")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No generated_configs found in manifest: {path}")
    return manifest


def ledger_status_counts(ledger_path: Path, cp_method: str | None) -> dict[str, int]:
    counts: Counter[str] = Counter()
    if not ledger_path.exists():
        return {}
    with ledger_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                counts["invalid_jsonl_row"] += 1
                continue
            if cp_method and row.get("cp_method") != cp_method:
                continue
            counts[str(row.get("status", "missing_status"))] += 1
    return dict(sorted(counts.items()))


def build_command(
    *,
    config_path: Path,
    cp_method: str | None,
    max_runs_per_config: int | None,
) -> list[str]:
    command = [
        sys.executable,
        "-u",
        "-m",
        "experiments.regression.scripts.run_regression_pilot",
        "--config",
        config_path.as_posix(),
    ]
    if cp_method:
        command.extend(["--cp-method", cp_method])
    if max_runs_per_config is not None:
        command.extend(["--max-runs", str(max_runs_per_config)])
    return command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run generated model-matched CQR rerun configs with batch events."
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--state-jsonl", type=Path, default=DEFAULT_STATE_JSONL)
    parser.add_argument("--cp-method", default="cqr_model_matched")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--max-configs", type=int, default=None)
    parser.add_argument("--max-runs-per-config", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop at the first subprocess failure instead of continuing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path
    state_jsonl = args.state_jsonl
    if not state_jsonl.is_absolute():
        state_jsonl = repo_root / state_jsonl

    manifest = load_manifest(manifest_path)
    rows = list(manifest["generated_configs"])
    selected_rows = rows[args.start_index :]
    if args.max_configs is not None:
        selected_rows = selected_rows[: args.max_configs]

    batch_id = f"model_matched_cqr_rerun_{utc_now()}"
    start_event = {
        "event": "batch_start",
        "batch_id": batch_id,
        "time_utc": utc_now(),
        "manifest": manifest_path.relative_to(repo_root).as_posix(),
        "cp_method": args.cp_method,
        "selected_config_count": len(selected_rows),
        "manifest_summary": manifest.get("summary", {}),
        "dry_run": bool(args.dry_run),
        "max_runs_per_config": args.max_runs_per_config,
    }
    append_event(state_jsonl, start_event)
    print(json.dumps(start_event, sort_keys=True), flush=True)

    failure_count = 0
    for absolute_index, row in enumerate(selected_rows, start=args.start_index):
        config_path = repo_root / row["generated_config"]
        ledger_path = repo_root / row["ledger"]
        if not config_path.exists():
            failure_count += 1
            event = {
                "event": "config_missing",
                "batch_id": batch_id,
                "time_utc": utc_now(),
                "config_index": absolute_index,
                "config": row["generated_config"],
            }
            append_event(state_jsonl, event)
            print(json.dumps(event, sort_keys=True), flush=True)
            if args.stop_on_failure:
                break
            continue

        command = build_command(
            config_path=Path(row["generated_config"]),
            cp_method=args.cp_method,
            max_runs_per_config=args.max_runs_per_config,
        )
        before_counts = ledger_status_counts(ledger_path, args.cp_method)
        event = {
            "event": "config_start",
            "batch_id": batch_id,
            "time_utc": utc_now(),
            "config_index": absolute_index,
            "config": row["generated_config"],
            "expected_cqr_model_matched_run_count": row.get(
                "expected_cqr_model_matched_run_count"
            ),
            "ledger": row["ledger"],
            "ledger_status_counts_before": before_counts,
            "command": command,
        }
        append_event(state_jsonl, event)
        print(json.dumps(event, sort_keys=True), flush=True)

        returncode = 0
        if not args.dry_run:
            completed = subprocess.run(command, cwd=repo_root, check=False)
            returncode = int(completed.returncode)
        after_counts = ledger_status_counts(ledger_path, args.cp_method)
        event = {
            "event": "config_finish",
            "batch_id": batch_id,
            "time_utc": utc_now(),
            "config_index": absolute_index,
            "config": row["generated_config"],
            "returncode": returncode,
            "ledger_status_counts_after": after_counts,
        }
        append_event(state_jsonl, event)
        print(json.dumps(event, sort_keys=True), flush=True)
        if returncode != 0:
            failure_count += 1
            if args.stop_on_failure:
                break

    finish_event = {
        "event": "batch_finish",
        "batch_id": batch_id,
        "time_utc": utc_now(),
        "failure_count": failure_count,
        "state_jsonl": state_jsonl.relative_to(repo_root).as_posix(),
    }
    append_event(state_jsonl, finish_event)
    print(json.dumps(finish_event, sort_keys=True), flush=True)
    return 1 if failure_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
