"""Run resumable row-level Venn-Abers score-grid expansion batches.

The source diagnostics scored only a tiny selected subset of test rows with the
exact score-grid reference. This worker expands that reference one durable row
ledger at a time. It intentionally records operational evidence only; it does
not promote Venn-Abers regression to a validated headline method.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from cpfi.regression.conformal import (
    split_conformal_interval,
    venn_abers_quantile_grid_interval,
    venn_abers_quantile_interval,
)
from cpfi.regression.experiment import append_jsonl, atomic_write_json, atomic_write_text
from cpfi.regression.target import transform_target
from experiments.regression.scripts.benchmark_venn_abers_real_data import (
    split_fallback_envelope,
)
from experiments.regression.scripts.run_regression_pilot import (
    PredictionBundle,
    fit_residual_quantile_scores,
    load_prediction_bundle,
)


SCHEMA = "cpfi_regression_venn_abers_grid_expansion_batch_v1"
ROW_SCHEMA = "cpfi_regression_venn_abers_grid_expansion_row_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_PLAN = REPORT_DIR / "venn_abers_grid_expansion_plan.json"
DEFAULT_STATE = Path(
    "experiments/regression/results/venn_abers_grid_expansion/checkpoints/row_results.jsonl"
)
DEFAULT_OUT = REPORT_DIR / "venn_abers_grid_expansion_batch.json"
DEFAULT_MAX_ROW_TASKS = 25

CONFIG_BY_REPORT_ID = {
    "report:venn_abers_real_data_diagnostic": Path(
        "experiments/regression/configs/venn_abers_real_data_diagnostic.yaml"
    ),
    "report:venn_abers_fairness_panel_diagnostic": Path(
        "experiments/regression/configs/venn_abers_fairness_panel_diagnostic.yaml"
    ),
    "report:venn_abers_biomarker_clinical_panel_diagnostic": Path(
        "experiments/regression/configs/venn_abers_biomarker_clinical_panel_diagnostic.yaml"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="Expansion plan JSON path.")
    parser.add_argument(
        "--state",
        default=str(DEFAULT_STATE),
        help="Append-only row-level JSONL progress ledger.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Batch summary JSON path.")
    parser.add_argument(
        "--max-row-tasks",
        type=int,
        default=DEFAULT_MAX_ROW_TASKS,
        help="Maximum new row tasks to score in this worker cycle.",
    )
    parser.add_argument("--report-id", default=None, help="Optional report_id filter.")
    parser.add_argument("--run-id", default=None, help="Optional run_id filter.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-score rows even when a completed row key already exists.",
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
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def finite_float(value: Any) -> float:
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"non-finite numeric value: {value!r}")
    return result


def bool_item(value: Any) -> bool:
    return bool(np.asarray(value).item())


def score_grid_hash(score_grid: list[float]) -> str:
    payload = json.dumps([finite_float(value) for value in score_grid], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def row_key(
    *,
    report_id: str,
    run_id: str,
    test_index: int,
    score_grid_size: int,
    score_grid_sha256: str,
    prediction_artifact: str,
) -> str:
    payload = {
        "prediction_artifact": prediction_artifact,
        "report_id": report_id,
        "run_id": run_id,
        "score_grid_sha256": score_grid_sha256,
        "score_grid_size": score_grid_size,
        "test_index": int(test_index),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def read_state_rows(state_path: Path) -> list[dict[str, Any]]:
    if not state_path.exists():
        return []
    rows = []
    for line_no, line in enumerate(state_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {state_path}:{line_no}: {exc}") from exc
        if isinstance(row, dict):
            rows.append(row)
    return rows


def completed_keys(state_rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(row["row_key"])
        for row in state_rows
        if row.get("schema") == ROW_SCHEMA
        and row.get("status") == "completed"
        and row.get("row_key")
    }


def find_source_result(source_report: dict[str, Any], run_id: str) -> dict[str, Any]:
    for row in source_report.get("results") or []:
        if isinstance(row, dict) and str(row.get("run_id")) == str(run_id):
            return row
    raise ValueError(f"run_id {run_id!r} not found in source diagnostic report")


def source_score_grid(source_result: dict[str, Any]) -> list[float]:
    reference = source_result.get("venn_abers_quantile_grid_reference") or {}
    metadata = reference.get("grid_metadata") or {}
    raw_grid = metadata.get("score_grid")
    if not isinstance(raw_grid, list) or not raw_grid:
        raise ValueError("source diagnostic result does not contain a fixed score_grid")
    grid = sorted(set(finite_float(value) for value in raw_grid))
    if not grid:
        raise ValueError("source score_grid is empty after numeric parsing")
    if grid[0] < 0.0:
        raise ValueError("source score_grid contains negative residual scores")
    return grid


def config_for_task(root: Path, task: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    report_id = str(task.get("report_id"))
    if report_id not in CONFIG_BY_REPORT_ID:
        raise ValueError(f"no config mapping registered for report_id={report_id!r}")
    path = resolve(root, CONFIG_BY_REPORT_ID[report_id])
    return load_yaml(path), path


def source_context_for_task(root: Path, task: dict[str, Any]) -> tuple[dict[str, Any], Path, list[float]]:
    report_path = resolve(root, str(task["report_path"]))
    source_report = read_json(report_path)
    source_result = find_source_result(source_report, str(task["run_id"]))
    return source_result, report_path, source_score_grid(source_result)


def plan_work_items(
    plan_payload: dict[str, Any],
    root: Path,
    state_rows: list[dict[str, Any]],
    max_row_tasks: int,
    report_id_filter: str | None = None,
    run_id_filter: str | None = None,
    force: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if max_row_tasks < 1:
        raise ValueError("max_row_tasks must be positive")

    existing = completed_keys(state_rows)
    work_items = []
    skipped_existing = 0
    skipped_filtered = 0

    for task in plan_payload.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        report_id = str(task.get("report_id"))
        run_id = str(task.get("run_id"))
        if report_id_filter and report_id != report_id_filter:
            skipped_filtered += int(task.get("next_batch_row_count") or 0)
            continue
        if run_id_filter and run_id != run_id_filter:
            skipped_filtered += int(task.get("next_batch_row_count") or 0)
            continue

        source_result, report_path, score_grid = source_context_for_task(root, task)
        grid_hash = score_grid_hash(score_grid)
        for test_index in task.get("next_batch_row_indices") or []:
            idx = int(test_index)
            key = row_key(
                report_id=report_id,
                run_id=run_id,
                test_index=idx,
                score_grid_size=len(score_grid),
                score_grid_sha256=grid_hash,
                prediction_artifact=str(task.get("prediction_artifact")),
            )
            if key in existing and not force:
                skipped_existing += 1
                continue
            work_items.append(
                {
                    "task": task,
                    "source_result": source_result,
                    "source_report_path": report_path,
                    "score_grid": score_grid,
                    "score_grid_sha256": grid_hash,
                    "test_index": idx,
                    "row_key": key,
                }
            )
            if len(work_items) >= max_row_tasks:
                return work_items, {
                    "skipped_existing": skipped_existing,
                    "skipped_filtered": skipped_filtered,
                }

    return work_items, {
        "skipped_existing": skipped_existing,
        "skipped_filtered": skipped_filtered,
    }


def group_work_items(work_items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    grouped = defaultdict(list)
    for item in work_items:
        task = item["task"]
        key = (str(task.get("report_id")), str(task.get("run_id")))
        grouped[key].append(item)
    return list(grouped.values())


def load_legacy_prediction_bundle_from_dir(
    artifact_dir: Path,
    artifact_id: str,
) -> PredictionBundle | None:
    """Load pre-provenance prediction bundles while preserving legacy labeling."""

    bundle_path = artifact_dir / "bundle.npz"
    metadata_path = artifact_dir / "metadata.json"
    if not bundle_path.exists() or not metadata_path.exists():
        return None
    metadata = read_json(metadata_path)
    if metadata.get("artifact_id") != artifact_id:
        return None
    with np.load(bundle_path, allow_pickle=False) as data:
        return PredictionBundle(
            artifact_id=artifact_id,
            artifact_dir=artifact_dir,
            cache_status="legacy_hit_missing_runtime_provenance",
            fit_seconds=float(metadata.get("fit_seconds", 0.0)),
            y_train=data["y_train"],
            y_cal=data["y_cal"],
            y_test=data["y_test"],
            yhat_train=data["yhat_train"],
            yhat_cal=data["yhat_cal"],
            yhat_test=data["yhat_test"],
            groups_cal=data["groups_cal"].astype(str),
            groups_test=data["groups_test"].astype(str),
            split_groups_train=(
                data["split_groups_train"].astype(str)
                if "split_groups_train" in data.files
                else None
            ),
            X_train=data["X_train"],
            X_cal=data["X_cal"],
            X_test=data["X_test"],
            scale_cal=data["scale_cal"],
            scale_test=data["scale_test"],
            target_transform=str(metadata.get("target_transform", "identity")),
        )


def load_prediction_bundle_for_task(
    root: Path,
    task: dict[str, Any],
    source_result: dict[str, Any],
) -> tuple[PredictionBundle, Path, dict[str, str]]:
    config, config_path = config_for_task(root, task)
    cache_root_raw = config.get("logging", {}).get("prediction_cache_root")
    if not cache_root_raw:
        raise ValueError("config logging.prediction_cache_root is required")
    cache_root = resolve(root, cache_root_raw)
    artifact_id = str(task.get("prediction_artifact"))
    bundle = load_prediction_bundle(cache_root, artifact_id)
    if bundle is None:
        artifact_paths = source_result.get("artifact_paths") or {}
        bundle_path_raw = artifact_paths.get("prediction_bundle")
        if isinstance(bundle_path_raw, str):
            bundle_path = resolve(root, bundle_path_raw)
            bundle = load_legacy_prediction_bundle_from_dir(bundle_path.parent, artifact_id)
            if bundle is not None:
                return (
                    bundle,
                    config_path,
                    {
                        "mode": "legacy_prediction_bundle_path",
                        "cache_root": rel(cache_root, root),
                        "prediction_bundle_path": rel(bundle_path, root),
                    },
                )
        raise FileNotFoundError(f"prediction bundle {artifact_id!r} not found under {cache_root}")
    return (
        bundle,
        config_path,
        {
            "mode": "validated_prediction_cache_root",
            "cache_root": rel(cache_root, root),
            "prediction_bundle_path": rel(bundle.artifact_dir / "bundle.npz", root),
        },
    )


def score_group(root: Path, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    first = items[0]
    task = first["task"]
    bundle, config_path, load_context = load_prediction_bundle_for_task(
        root,
        task,
        first.get("source_result") or {},
    )
    alpha = finite_float(task["alpha"])
    seed = int(task["seed"])
    score_grid = [finite_float(value) for value in first["score_grid"]]
    score_grid_sha = str(first["score_grid_sha256"])
    test_indices = np.array([int(item["test_index"]) for item in items], dtype=int)

    if np.any(test_indices < 0) or np.any(test_indices >= len(bundle.y_test)):
        raise IndexError("test_index outside prediction bundle y_test range")

    start = time.time()
    y_test_transformed = transform_target(bundle.y_test, bundle.target_transform)
    qhat_cal, qhat_test = fit_residual_quantile_scores(
        bundle.X_train,
        bundle.y_train,
        bundle.yhat_train,
        bundle.X_cal,
        bundle.X_test,
        alpha,
        seed,
    )
    yhat_selected = bundle.yhat_test[test_indices]
    y_true_selected = y_test_transformed[test_indices]
    group_selected = bundle.groups_test[test_indices].astype(str)
    qhat_selected = qhat_test[test_indices]
    bridge = venn_abers_quantile_interval(
        y_cal=bundle.y_cal,
        yhat_cal=bundle.yhat_cal,
        yhat_test=yhat_selected,
        residual_quantile_cal=qhat_cal,
        residual_quantile_test=qhat_selected,
        alpha=alpha,
        m=1,
    )
    split = split_conformal_interval(
        y_cal=bundle.y_cal,
        yhat_cal=bundle.yhat_cal,
        yhat_test=yhat_selected,
        alpha=alpha,
    )
    split_fallback = split_fallback_envelope(bridge, split, yhat_selected)
    grid = venn_abers_quantile_grid_interval(
        y_cal=bundle.y_cal,
        yhat_cal=bundle.yhat_cal,
        yhat_test=yhat_selected,
        residual_quantile_cal=qhat_cal,
        residual_quantile_test=qhat_selected,
        score_grid=score_grid,
        alpha=alpha,
    )
    elapsed = time.time() - start
    per_row_seconds = elapsed / max(len(test_indices), 1)

    rows = []
    generated_at = utc_now()
    for local_idx, item in enumerate(items):
        y_true = finite_float(y_true_selected[local_idx])
        yhat = finite_float(yhat_selected[local_idx])
        abs_residual = abs(y_true - yhat)
        record = {
            "schema": ROW_SCHEMA,
            "row_key": str(item["row_key"]),
            "status": "completed",
            "generated_at_utc": generated_at,
            "report_id": str(task.get("report_id")),
            "run_id": str(task.get("run_id")),
            "dataset_id": str(task.get("dataset_id")),
            "model_id": str(task.get("model_id")),
            "model_family": str(task.get("model_family")),
            "seed": seed,
            "alpha": alpha,
            "test_index": int(item["test_index"]),
            "group": str(group_selected[local_idx]),
            "prediction_artifact": str(task.get("prediction_artifact")),
            "prediction_cache_status": str(task.get("prediction_cache_status")),
            "prediction_bundle_loader": load_context,
            "prediction_bundle_path": rel(bundle.artifact_dir / "bundle.npz", root),
            "source_report_path": rel(Path(item["source_report_path"]), root),
            "source_config_path": rel(config_path, root),
            "source_score_grid": {
                "size": len(score_grid),
                "min": finite_float(score_grid[0]),
                "max": finite_float(score_grid[-1]),
                "sha256": score_grid_sha,
                "policy": "fixed_grid_reused_from_source_diagnostic_for_cross_row_comparability",
            },
            "scale": "transformed_target",
            "target_transform": str(bundle.target_transform),
            "y_true_transformed": y_true,
            "yhat_test_transformed": yhat,
            "abs_residual": finite_float(abs_residual),
            "residual_quantile_test": finite_float(qhat_selected[local_idx]),
            "bridge_radius": finite_float(bridge.radii[local_idx]),
            "split_radius": finite_float(split.radii[local_idx]),
            "split_fallback_radius": finite_float(split_fallback.radii[local_idx]),
            "grid_radius": finite_float(grid.radii[local_idx]),
            "grid_minus_bridge_radius": finite_float(
                grid.radii[local_idx] - bridge.radii[local_idx]
            ),
            "grid_minus_split_fallback_radius": finite_float(
                grid.radii[local_idx] - split_fallback.radii[local_idx]
            ),
            "bridge_covered": bool_item(
                bridge.lower[local_idx] <= y_true_selected[local_idx] <= bridge.upper[local_idx]
            ),
            "split_covered": bool_item(
                split.lower[local_idx] <= y_true_selected[local_idx] <= split.upper[local_idx]
            ),
            "split_fallback_covered": bool_item(
                split_fallback.lower[local_idx]
                <= y_true_selected[local_idx]
                <= split_fallback.upper[local_idx]
            ),
            "grid_covered": bool_item(
                grid.lower[local_idx] <= y_true_selected[local_idx] <= grid.upper[local_idx]
            ),
            "grid_accepted_count": int(grid.metadata["accepted_counts"][local_idx]),
            "grid_rejected_count": int(grid.metadata["rejected_counts"][local_idx]),
            "grid_hit_upper": bool_item(
                np.isclose(grid.radii[local_idx], finite_float(score_grid[-1]))
            ),
            "seconds": finite_float(per_row_seconds),
            "claim_boundary": (
                "Row-level expansion evidence only; not a validated finite-sample "
                "Venn-Abers regression coverage claim."
            ),
        }
        rows.append(record)
    return rows


def failed_row(item: dict[str, Any], exc: Exception) -> dict[str, Any]:
    task = item["task"]
    return {
        "schema": ROW_SCHEMA,
        "row_key": str(item["row_key"]),
        "status": "failed",
        "generated_at_utc": utc_now(),
        "report_id": str(task.get("report_id")),
        "run_id": str(task.get("run_id")),
        "dataset_id": str(task.get("dataset_id")),
        "model_id": str(task.get("model_id")),
        "seed": task.get("seed"),
        "alpha": task.get("alpha"),
        "test_index": int(item["test_index"]),
        "prediction_artifact": str(task.get("prediction_artifact")),
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "claim_boundary": "Failed operational row task; no empirical claim.",
    }


def summarize_state(state_rows: list[dict[str, Any]]) -> dict[str, Any]:
    row_records = [row for row in state_rows if row.get("schema") == ROW_SCHEMA]
    completed = [row for row in row_records if row.get("status") == "completed"]
    row_keys = [str(row.get("row_key")) for row in completed if row.get("row_key")]
    duplicate_completed_keys = len(row_keys) - len(set(row_keys))
    grid_hit_upper_count = sum(1 for row in completed if row.get("grid_hit_upper") is True)
    return {
        "ledger_record_count": len(row_records),
        "completed_row_count": len(completed),
        "unique_completed_row_count": len(set(row_keys)),
        "duplicate_completed_key_count": duplicate_completed_keys,
        "failed_row_count": sum(1 for row in row_records if row.get("status") == "failed"),
        "grid_hit_upper_completed_count": grid_hit_upper_count,
        "status_counts": dict(Counter(str(row.get("status")) for row in row_records)),
        "completed_by_report": dict(Counter(str(row.get("report_id")) for row in completed)),
        "completed_by_dataset": dict(Counter(str(row.get("dataset_id")) for row in completed)),
    }


def build_summary(
    *,
    root: Path,
    plan_path: Path,
    state_path: Path,
    out_path: Path,
    work_items: list[dict[str, Any]],
    written_rows: list[dict[str, Any]],
    skipped_counts: dict[str, int],
    before_state: list[dict[str, Any]],
    after_state: list[dict[str, Any]],
    started_at: str,
    seconds: float,
) -> dict[str, Any]:
    completed_written = [row for row in written_rows if row.get("status") == "completed"]
    failed_written = [row for row in written_rows if row.get("status") == "failed"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "started_at_utc": started_at,
        "seconds": seconds,
        "paths": {
            "plan": rel(plan_path, root),
            "state": rel(state_path, root),
            "summary": rel(out_path, root),
        },
        "batch_policy": {
            "worker_unit": "one report_id + run_id + test_index score-grid row",
            "state_mode": "append_only_jsonl_with_fsync_per_group",
            "score_grid_policy": (
                "reuse fixed score_grid from source diagnostic report for all new rows "
                "in the same run"
            ),
            "claim_boundary": (
                "Operational score-grid expansion evidence only; not manuscript-ready "
                "validated Venn-Abers regression coverage evidence."
            ),
        },
        "summary": {
            "planned_new_row_tasks": len(work_items),
            "completed_new_row_tasks": len(completed_written),
            "failed_new_row_tasks": len(failed_written),
            "skipped_existing_completed_rows": int(skipped_counts.get("skipped_existing", 0)),
            "skipped_filtered_rows": int(skipped_counts.get("skipped_filtered", 0)),
            "before_completed_row_count": summarize_state(before_state)["completed_row_count"],
            "after_completed_row_count": summarize_state(after_state)["completed_row_count"],
            "after_unique_completed_row_count": summarize_state(after_state)[
                "unique_completed_row_count"
            ],
            "after_failed_row_count": summarize_state(after_state)["failed_row_count"],
        },
        "state_summary": summarize_state(after_state),
        "written_row_keys": [str(row.get("row_key")) for row in written_rows],
        "written_rows_preview": written_rows[:10],
        "claim_boundary": (
            "This batch summary is a reproducibility and resume artifact; it should be "
            "cited as operational evidence until the full validation protocol is closed."
        ),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    state = payload["state_summary"]
    lines = [
        "# Venn-Abers Grid Expansion Batch",
        "",
        "This artifact records row-level expansion progress for the exact Venn-Abers "
        "score-grid reference. It is not empirical validation evidence by itself.",
        "",
        "## Batch Summary",
        "",
        f"- Planned new row tasks: {summary['planned_new_row_tasks']}",
        f"- Completed new row tasks: {summary['completed_new_row_tasks']}",
        f"- Failed new row tasks: {summary['failed_new_row_tasks']}",
        f"- Skipped existing completed rows: {summary['skipped_existing_completed_rows']}",
        f"- Completed rows in ledger after batch: {summary['after_completed_row_count']}",
        f"- Unique completed rows in ledger after batch: {summary['after_unique_completed_row_count']}",
        f"- Failed rows in ledger after batch: {summary['after_failed_row_count']}",
        "",
        "## State Health",
        "",
        f"- Duplicate completed row keys: {state['duplicate_completed_key_count']}",
        f"- Completed rows hitting source grid upper bound: {state['grid_hit_upper_completed_count']}",
        f"- Completed by report: `{json.dumps(state['completed_by_report'], sort_keys=True)}`",
        f"- Completed by dataset: `{json.dumps(state['completed_by_dataset'], sort_keys=True)}`",
        "",
        "## Claim Boundary",
        "",
        payload["claim_boundary"],
        "",
    ]
    return "\n".join(lines)


def run_batch(
    root: Path,
    plan_path: Path,
    state_path: Path,
    out_path: Path,
    max_row_tasks: int,
    report_id_filter: str | None = None,
    run_id_filter: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    started_at = utc_now()
    start = time.time()
    plan_payload = read_json(plan_path)
    before_state = read_state_rows(state_path)
    work_items, skipped_counts = plan_work_items(
        plan_payload=plan_payload,
        root=root,
        state_rows=before_state,
        max_row_tasks=max_row_tasks,
        report_id_filter=report_id_filter,
        run_id_filter=run_id_filter,
        force=force,
    )

    written_rows: list[dict[str, Any]] = []
    for group in group_work_items(work_items):
        try:
            rows = score_group(root, group)
        except Exception as exc:  # pragma: no cover - exercised by integration failures
            rows = [failed_row(item, exc) for item in group]
        append_jsonl(state_path, rows)
        written_rows.extend(rows)

    after_state = read_state_rows(state_path)
    payload = build_summary(
        root=root,
        plan_path=plan_path,
        state_path=state_path,
        out_path=out_path,
        work_items=work_items,
        written_rows=written_rows,
        skipped_counts=skipped_counts,
        before_state=before_state,
        after_state=after_state,
        started_at=started_at,
        seconds=time.time() - start,
    )
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    return payload


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    payload = run_batch(
        root=root,
        plan_path=resolve(root, args.plan),
        state_path=resolve(root, args.state),
        out_path=resolve(root, args.out),
        max_row_tasks=args.max_row_tasks,
        report_id_filter=args.report_id,
        run_id_filter=args.run_id,
        force=args.force,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
