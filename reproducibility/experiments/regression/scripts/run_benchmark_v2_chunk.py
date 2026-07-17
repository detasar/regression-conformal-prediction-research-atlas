"""Inspect or execute a planned Benchmark v2 chunk.

The public Research Atlas exposes Benchmark v2 preflight ledgers. In public
package use this script remains a dry-run chunk inspector. In the source
repository it can also execute a selected chunk against the existing regression
runner, writing a resumable Benchmark v2 execution ledger.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import shutil
from pathlib import Path
from typing import Any

from experiments.regression.scripts import run_regression_pilot as pilot


DEFAULT_CHUNKS_PATH = Path("atlas/benchmark_v2/preflight/execution_chunks.json")
DEFAULT_TASK_REGISTRY_PATH = Path(
    "atlas/benchmark_v2/preflight/task_variant_registry.csv"
)
DEFAULT_EXECUTION_ROOT = Path("experiments/regression/results/benchmark_v2")

PLACEHOLDER_TARGET_TRANSFORMS = {
    "",
    "benchmark_v2_to_be_frozen_before_execution",
    "pending",
    "pending_public_verification",
}

BENCHMARK_V2_TARGET_TRANSFORMS = {
    "aif360_lawschool_gpa": "identity",
    "aif360_lawschool_gpa_dedup": "identity",
    "college_scorecard_2026_median_earnings": "log1p",
    "hmda_2025_wy_interest_rate": "identity",
    "meps_2023_total_expenditure": "log1p",
    "nhanes_2017_2018_bmi": "identity",
    "nhanes_2017_2018_systolic_bp": "identity",
    "openml_auto_price": "log1p",
    "openml_kin8nm_y": "identity",
    "pisa_2022_math_pv_mean": "identity",
    "scf_2022_networth": "signed_log1p",
    "stackoverflow_2025_compensation": "log1p",
    "uci_bike_sharing": "log1p",
    "uci_wine_quality": "identity",
    "uci_wine_quality_dedup": "identity",
}

BENCHMARK_V2_TEMPORAL_ORDER_COLUMNS = {
    "uci_bike_sharing": ("dteday", "dteday"),
}

BENCHMARK_V2_SPATIAL_GROUP_COLUMNS = {
    "openml_california_housing_spatial_cell": "spatial_cell",
}

BENCHMARK_V2_COVARIATE_SHIFT_POLICIES = {
    "openml_kin8nm:openml_kin8nm_y:covariate_shift": {
        "strategy": "source_target",
        "source_target_col": "theta3_bin",
        "target_values": ["(0.792, 1.571]"],
        "covariate_shift_policy_id": "theta3_bin_upper_quartile_target_v1",
        "policy_note": (
            "Rows in the upper theta3_bin quartile are held out as the "
            "target-domain test split; the remaining bins form the source "
            "train/calibration domain."
        ),
    },
    "uci_wine_quality:uci_wine_quality_dedup:covariate_shift": {
        "strategy": "source_target",
        "source_target_col": "wine_color",
        "source_values": ["white"],
        "target_values": ["red"],
        "covariate_shift_policy_id": "wine_color_white_source_red_target_v1",
        "policy_note": (
            "White-wine rows form the train/calibration source domain and "
            "red-wine rows form the target-domain test split."
        ),
    },
}

EXECUTION_TERMINAL_STATUSES = {
    "completed",
    "failed",
    "skipped_method",
    "skipped_infeasible_grouped_regime",
    "skipped_non_variant_regime",
    "skipped_unsupported_regime",
    "skipped_existing_terminal",
}

UNSUPPORTED_REGIME_ERROR_SNIPPETS = (
    "requires at least 3 groups",
    "left fewer than 2 rest groups",
    "ordered grouped split produced an empty row split",
)


def is_unsupported_split_regime_text(text: str) -> bool:
    return any(snippet in text for snippet in UNSUPPORTED_REGIME_ERROR_SNIPPETS)


def is_unsupported_split_regime_exception(exc: Exception) -> bool:
    return is_unsupported_split_regime_text(str(exc))


def normalized_execution_status(row: dict[str, Any]) -> str:
    status = str(row.get("status", ""))
    if status == "skipped_completed":
        return "completed"
    if status == "skipped_skipped_method":
        return "skipped_method"
    if status == "failed":
        diagnostic_text = "\n".join(
            str(row.get(key, ""))
            for key in ("error_message", "traceback_tail", "skip_reason")
        )
        if is_unsupported_split_regime_text(diagnostic_text):
            return "skipped_infeasible_grouped_regime"
    return status


LEGACY_RESUME_SKIP_STATUSES = {"skipped_completed", "skipped_skipped_method"}

COMPLETED_PAYLOAD_FIELDS = (
    "alpha",
    "seed",
    "coverage",
    "mean_width",
    "median_width",
    "interval_score",
    "lower_miss_rate",
    "upper_miss_rate",
    "cp_metadata",
    "benchmark_v2_config",
)

SKIPPED_PAYLOAD_FIELDS = (
    "alpha",
    "seed",
    "skip_reason",
    "split_regime",
    "source_dataset_id",
    "task_variant_id",
)


def execution_row_payload_score(row: dict[str, Any]) -> int:
    """Score how useful a ledger row is when duplicate terminal rows exist."""
    normalized_status = normalized_execution_status(row)
    fields = (
        COMPLETED_PAYLOAD_FIELDS
        if normalized_status == "completed"
        else SKIPPED_PAYLOAD_FIELDS
    )
    score = sum(1 for field in fields if row.get(field) not in (None, ""))
    if str(row.get("status", "")) in LEGACY_RESUME_SKIP_STATUSES:
        score -= 100
    return score


def preferred_execution_row(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any],
) -> dict[str, Any]:
    """Keep the most informative row for a method key.

    Concurrent resume workers can append legacy skip rows after a full completed
    row. Those rows are terminal for resumability but intentionally sparse; they
    must not overwrite the metric-bearing row used by audit and synthesis.
    """
    if existing is None:
        return incoming
    if normalized_execution_status(existing) != normalized_execution_status(incoming):
        return incoming
    if execution_row_payload_score(existing) > execution_row_payload_score(incoming):
        return existing
    return incoming


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
        help="Inspect chunk metadata without running experiments.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Execute rows from the selected chunk. This is intended for the source "
            "repository, not the public package smoke path."
        ),
    )
    parser.add_argument(
        "--task-registry",
        default=str(DEFAULT_TASK_REGISTRY_PATH),
        help="Task registry CSV path relative to package root.",
    )
    parser.add_argument(
        "--execution-root",
        default=str(DEFAULT_EXECUTION_ROOT),
        help="Execution output root relative to the source repository root.",
    )
    parser.add_argument(
        "--max-method-rows",
        type=int,
        default=None,
        help="Optional cap on attempted method rows for smoke execution.",
    )
    parser.add_argument(
        "--min-free-disk-mb",
        type=float,
        default=None,
        help=(
            "Optional execution guard. When set, stop before starting the next "
            "method row if the output filesystem has less than this many MiB "
            "available. Already-terminal rows can still be skipped."
        ),
    )
    parser.add_argument(
        "--cv-plus-max-train-rows",
        type=int,
        default=None,
        help=(
            "Optional computational cap for CV+ family methods. Defaults to no "
            "cap so Benchmark v2 can test the common method surface."
        ),
    )
    parser.add_argument(
        "--jackknife-plus-max-train-rows",
        type=int,
        default=None,
        help=(
            "Optional computational cap for jackknife+ family methods. Defaults "
            "to no cap so Benchmark v2 can test the common method surface."
        ),
    )
    parser.add_argument("--dataset-id", action="append", default=None)
    parser.add_argument("--task-variant-id", action="append", default=None)
    parser.add_argument("--split-regime", action="append", default=None)
    parser.add_argument("--learner-family", action="append", default=None)
    parser.add_argument("--cp-method", action="append", default=None)
    parser.add_argument("--alpha", action="append", type=float, default=None)
    parser.add_argument("--seed", action="append", type=int, default=None)
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry previously failed Benchmark v2 method rows.",
    )
    parser.add_argument(
        "--retry-skipped-status",
        action="append",
        default=None,
        help=(
            "Retry rows whose latest status matches this skipped status. "
            "Useful after adding support for a previously unsupported regime."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force the underlying regression runner to overwrite checkpoints.",
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

    source_public_release = package_root / "experiments/regression/public_release"
    if (source_public_release / chunks_path).exists():
        return source_public_release

    parent = package_root.parent
    if (parent / chunks_path).exists() and package_root.name == "reproducibility":
        return parent

    return package_root


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def existing_disk_probe_path(path: Path) -> Path:
    probe = path.resolve()
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return probe if probe.exists() else Path.cwd()


def free_disk_mb(path: Path) -> float:
    usage = shutil.disk_usage(existing_disk_probe_path(path))
    return usage.free / (1024 * 1024)


def disk_guard(
    *,
    output_path: Path,
    min_free_disk_mb: float | None,
) -> dict[str, Any] | None:
    if min_free_disk_mb is None:
        return None
    available = free_disk_mb(output_path)
    if available >= min_free_disk_mb:
        return None
    return {
        "resource_guard_status": "stopped_before_next_method_row",
        "resource_guard_reason": "free disk below requested minimum",
        "disk_check_path": str(existing_disk_probe_path(output_path)),
        "available_free_disk_mb": round(available, 3),
        "min_free_disk_mb": float(min_free_disk_mb),
    }


def latest_status_by_method_row(ledger_path: Path) -> dict[str, str]:
    latest: dict[str, str] = {}
    for row in read_jsonl(ledger_path):
        key = str(row.get("method_row_key", ""))
        if key:
            latest[key] = normalized_execution_status(row)
    return latest


def should_retry_status(
    status: str,
    *,
    retry_failed: bool,
    retry_skipped_status: list[str] | None = None,
) -> bool:
    retry_statuses = {str(item) for item in retry_skipped_status or []}
    return status in retry_statuses or (
        retry_failed and status in {"failed", "skipped_failed"}
    )


def previously_terminal_rows(
    ledger_path: Path,
    *,
    retry_failed: bool,
    retry_skipped_status: list[str] | None = None,
) -> set[str]:
    terminal: set[str] = set()
    for row in read_jsonl(ledger_path):
        key = str(row.get("method_row_key", ""))
        status = normalized_execution_status(row)
        if not key:
            continue
        if should_retry_status(
            status,
            retry_failed=retry_failed,
            retry_skipped_status=retry_skipped_status,
        ):
            continue
        if status in EXECUTION_TERMINAL_STATUSES or status.startswith("skipped_"):
            terminal.add(key)
    return terminal


def chunk_rows(run_grid_path: Path, chunk: dict[str, Any]) -> list[dict[str, str]]:
    start = int(chunk["paired_cell_start_index"])
    end = int(chunk["paired_cell_end_index"])
    rows: list[dict[str, str]] = []
    cell_index = 0
    current_cell: str | None = None
    for row in read_csv_rows(run_grid_path):
        paired_cell = str(row["paired_cell_key"])
        if paired_cell != current_cell:
            current_cell = paired_cell
            cell_index += 1
        if start <= cell_index <= end:
            rows.append(row)
        elif cell_index > end:
            break
    return rows


def selected(value: Any, allowed: list[Any] | None) -> bool:
    if not allowed:
        return True
    return str(value) in {str(item) for item in allowed}


def dataset_id_from_task_variant(task_variant_id: str) -> str:
    parts = str(task_variant_id).split(":")
    if len(parts) >= 3:
        return parts[1]
    return str(task_variant_id)


def cp_method_from_config_id(method_config_id: str) -> str:
    suffix = "_benchmark_v2_v1"
    method = str(method_config_id)
    if method.endswith(suffix):
        method = method[: -len(suffix)]
    return method


def load_task_registry(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv_rows(path)
    return {str(row["task_variant_id"]): row for row in rows}


def split_config_for_row(
    row: dict[str, str],
    task_registry: dict[str, dict[str, str]],
) -> tuple[dict[str, Any] | None, str | None]:
    task_variant_id = str(row["task_variant_id"])
    task = task_registry.get(task_variant_id, {})
    planned_regime = str(task.get("split_regime", ""))
    split_regime = str(row["split_regime"])
    if planned_regime and split_regime != planned_regime:
        return None, (
            f"row split_regime={split_regime} is outside task-registry regime "
            f"{planned_regime}"
        )

    dataset_id = dataset_id_from_task_variant(task_variant_id)
    loader = pilot.DATASET_LOADERS.get(dataset_id, {})
    config: dict[str, Any] = {"train": 0.60, "calibration": 0.20, "test": 0.20}

    if split_regime == "iid":
        return config, None
    if split_regime == "grouped":
        group_col = loader.get("group")
        if not group_col:
            return None, f"grouped split has no loader group column for {dataset_id}"
        config["group_col"] = str(group_col)
        return config, None
    if split_regime == "temporal":
        if dataset_id not in BENCHMARK_V2_TEMPORAL_ORDER_COLUMNS:
            return None, f"temporal split policy is not implemented for {dataset_id}"
        group_col, order_col = BENCHMARK_V2_TEMPORAL_ORDER_COLUMNS[dataset_id]
        config.update({"strategy": "ordered", "group_col": group_col, "order_col": order_col})
        return config, None
    if split_regime == "spatial":
        group_col = BENCHMARK_V2_SPATIAL_GROUP_COLUMNS.get(dataset_id)
        if group_col is None:
            return None, f"spatial split policy is not implemented for {dataset_id}"
        config["group_col"] = group_col
        return config, None
    if split_regime == "covariate_shift":
        policy = BENCHMARK_V2_COVARIATE_SHIFT_POLICIES.get(task_variant_id)
        if policy is None:
            return None, (
                "covariate_shift split policy is not implemented for "
                f"{task_variant_id}"
            )
        config.update(policy)
        return config, None
    return None, f"unsupported Benchmark v2 split_regime={split_regime}"


def target_transform_for_row(
    row: dict[str, str],
    task_registry: dict[str, dict[str, str]],
) -> str:
    dataset_id = dataset_id_from_task_variant(str(row["task_variant_id"]))
    task = task_registry.get(str(row["task_variant_id"]), {})
    value = str(task.get("target_transform", "")).strip()
    if value and value not in PLACEHOLDER_TARGET_TRANSFORMS:
        return value
    return BENCHMARK_V2_TARGET_TRANSFORMS.get(dataset_id, "identity")


def row_config(
    row: dict[str, str],
    split_config: dict[str, Any],
    target_transform: str,
    execution_root: Path,
    chunk_id: str,
    *,
    cv_plus_max_train_rows: int | None = None,
    jackknife_plus_max_train_rows: int | None = None,
) -> dict[str, Any]:
    cp_label = str(row["conformal_method_config_id"])
    cp_method_id = cp_method_from_config_id(cp_label)
    return {
        "experiment_id": f"benchmark_v2_{chunk_id}",
        "purpose": "Benchmark v2 source execution row generated from the frozen preflight grid.",
        "random_seeds": [int(row["seed"])],
        "alphas": [float(row["alpha"])],
        "target_transform": target_transform,
        "splits": split_config,
        "conformal": {
            "cv_plus_folds": 5,
            "cv_plus_max_train_rows": cv_plus_max_train_rows,
            "jackknife_plus_max_train_rows": jackknife_plus_max_train_rows,
            "jackknife_after_bootstrap_n_resamples": 40,
            "jackknife_after_bootstrap_sample_fraction": 1.0,
            "jackknife_after_bootstrap_min_oob": 5,
            "jackknife_after_bootstrap_max_train_rows": 500,
            "venn_abers_m": 1,
            "plus_fold_local_preprocessing": True,
        },
        "datasets": [dataset_id_from_task_variant(str(row["task_variant_id"]))],
        "models": [
            {
                "model_id": str(row["model_id"]),
                "family": str(row["learner_family"]),
                "grid": {
                    key: [value]
                    for key, value in json.loads(row["learner_params_json"]).items()
                },
            }
        ],
        "cp_methods": [cp_label],
        "cp_method_configs": {
            cp_label: {
                "method_id": cp_method_id,
                "params": {},
            }
        },
        "quality_controls": {
            "benchmark_v2": True,
            "paired_cell_key": row["paired_cell_key"],
            "method_row_key": row["method_row_key"],
            "split_hash": row["split_hash"],
            "learner_config_id": row["learner_config_id"],
            "preprocessing_policy_id": row["preprocessing_policy_id"],
            "plus_fold_local_preprocessing_required": True,
            "no_method_winner_claim": True,
        },
        "logging": {
            "ledger": str(execution_root / "legacy_runner_ledger.jsonl"),
            "checkpoint_root": str(execution_root / "checkpoints"),
            "prediction_cache_root": str(execution_root / "checkpoints/predictions"),
        },
    }


def row_allowed(row: dict[str, str], args: argparse.Namespace) -> bool:
    cp_method = cp_method_from_config_id(row["conformal_method_config_id"])
    return (
        selected(row["source_dataset_id"], args.dataset_id)
        and selected(row["task_variant_id"], args.task_variant_id)
        and selected(row["split_regime"], args.split_regime)
        and selected(row["learner_family"], args.learner_family)
        and selected(cp_method, args.cp_method)
        and selected(float(row["alpha"]), args.alpha)
        and selected(int(row["seed"]), args.seed)
    )


def execute_chunk(
    *,
    package_root: Path,
    chunk: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    execution_root = Path(args.execution_root)
    if not execution_root.is_absolute():
        execution_root = Path.cwd() / execution_root
    chunk_execution_root = execution_root / str(chunk["chunk_id"])
    ledger_path = chunk_execution_root / "benchmark_v2_execution_ledger.jsonl"
    checkpoint_root = chunk_execution_root / "checkpoints"
    prediction_cache_root = checkpoint_root / "predictions"
    audit_root = Path.cwd() / "experiments/regression/audits"

    run_grid_path = package_root / str(chunk["run_grid_path"])
    task_registry_path = Path(args.task_registry)
    if not task_registry_path.is_absolute():
        task_registry_path = package_root / task_registry_path
    task_registry = load_task_registry(task_registry_path)
    rows = [row for row in chunk_rows(run_grid_path, chunk) if row_allowed(row, args)]
    terminal = previously_terminal_rows(
        ledger_path,
        retry_failed=args.retry_failed,
        retry_skipped_status=args.retry_skipped_status,
    )
    latest_statuses = latest_status_by_method_row(ledger_path)

    dataset_cache: dict[str, Any] = {}
    audited_datasets: set[str] = set()
    attempted = 0
    completed = 0
    failed = 0
    skipped = 0
    skipped_existing = 0
    status_counts: dict[str, int] = {}
    resource_guard: dict[str, Any] | None = None

    for row in rows:
        if args.max_method_rows is not None and attempted >= args.max_method_rows:
            break
        method_row_key = row["method_row_key"]
        if method_row_key in terminal and not args.force:
            skipped_existing += 1
            continue
        force_retry = should_retry_status(
            latest_statuses.get(method_row_key, ""),
            retry_failed=args.retry_failed,
            retry_skipped_status=args.retry_skipped_status,
        )
        resource_guard = disk_guard(
            output_path=chunk_execution_root,
            min_free_disk_mb=args.min_free_disk_mb,
        )
        if resource_guard is not None:
            break

        split_config, skip_reason = split_config_for_row(row, task_registry)
        base_payload = {
            "schema": "regression_cp_benchmark_v2_execution_row_v1",
            "chunk_id": chunk["chunk_id"],
            "method_row_key": method_row_key,
            "paired_cell_key": row["paired_cell_key"],
            "source_dataset_id": row["source_dataset_id"],
            "task_variant_id": row["task_variant_id"],
            "split_regime": row["split_regime"],
            "split_hash": row["split_hash"],
            "learner_family": row["learner_family"],
            "learner_config_id": row["learner_config_id"],
            "conformal_method_config_id": row["conformal_method_config_id"],
        }
        attempted += 1
        if split_config is None:
            status = (
                "skipped_non_variant_regime"
                if "outside task-registry regime" in str(skip_reason)
                else "skipped_unsupported_regime"
            )
            result = {**base_payload, "status": status, "skip_reason": skip_reason}
            write_jsonl(ledger_path, [result])
            skipped += 1
            status_counts[status] = status_counts.get(status, 0) + 1
            print(json.dumps(result, sort_keys=True))
            continue

        target_transform = target_transform_for_row(row, task_registry)
        config = row_config(
            row,
            split_config,
            target_transform,
            chunk_execution_root,
            str(chunk["chunk_id"]),
            cv_plus_max_train_rows=args.cv_plus_max_train_rows,
            jackknife_plus_max_train_rows=args.jackknife_plus_max_train_rows,
        )
        dataset_id = dataset_id_from_task_variant(str(row["task_variant_id"]))
        model_params = json.loads(row["learner_params_json"])
        cp_label = str(row["conformal_method_config_id"])
        run_tuple = (
            dataset_id,
            str(row["model_id"]),
            str(row["learner_family"]),
            model_params,
            cp_label,
            float(row["alpha"]),
            int(row["seed"]),
        )
        try:
            runner_result = pilot.run_one(
                *run_tuple,
                config=config,
                checkpoint_root=checkpoint_root,
                prediction_cache_root=prediction_cache_root,
                audit_root=audit_root,
                force=args.force or force_retry,
                dataset_cache=dataset_cache,
                audited_datasets=audited_datasets,
            )
        except Exception as exc:
            runner_result = pilot.failed_result_from_exception(
                run_tuple,
                checkpoint_root,
                exc,
                config=config,
            )
            if is_unsupported_split_regime_exception(exc):
                runner_result = {
                    **runner_result,
                    "status": "skipped_infeasible_grouped_regime",
                    "skip_reason": (
                        "unsupported Benchmark v2 split regime: "
                        f"{runner_result.get('error_message', str(exc))}"
                    ),
                }

        status = str(runner_result.get("status", "unknown"))
        result = {
            **base_payload,
            **runner_result,
            "status": status,
            "target_transform": target_transform,
            "benchmark_v2_config": {
                "split_config": split_config,
                "plus_fold_local_preprocessing": True,
            },
        }
        write_jsonl(ledger_path, [result])
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "completed":
            completed += 1
        elif status.startswith("skipped_") or status == "skipped_method":
            skipped += 1
        elif status == "failed":
            failed += 1
        print(json.dumps(result, sort_keys=True, default=str))

    summary = {
        "schema": "regression_cp_benchmark_v2_chunk_execution_summary_v1",
        "chunk_id": chunk["chunk_id"],
        "selected_method_row_count": len(rows),
        "attempted_this_invocation": attempted,
        "completed_this_invocation": completed,
        "failed_this_invocation": failed,
        "skipped_this_invocation": skipped,
        "skipped_existing_terminal": skipped_existing,
        "status_counts": status_counts,
        "ledger_path": str(ledger_path),
        "checkpoint_root": str(checkpoint_root),
        "prediction_cache_root": str(prediction_cache_root),
        "resource_guard": resource_guard,
    }
    summary_path = chunk_execution_root / "chunk_execution_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    args = parse_args()
    if args.dry_run and args.execute:
        raise SystemExit("Choose either --dry-run or --execute, not both.")
    if not args.dry_run and not args.execute:
        raise SystemExit(
            "Choose --dry-run to inspect a chunk or --execute to run selected rows."
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
    if args.execute:
        summary = execute_chunk(package_root=package_root, chunk=chunk, args=args)
        summary["dry_run_only"] = False
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
        return 0

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
