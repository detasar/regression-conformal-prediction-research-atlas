"""Audit feasibility of regenerating legacy endpoint sidecars as v2.

This script does not reconstruct endpoints. It reads the integrity remediation
backlog, inspects legacy endpoint sidecars, configs, ledgers, prediction-cache
roots, and dataset audits, then records whether each legacy endpoint schema
caveat has enough inputs for a later `audit_regression_endpoints.py` run.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.audit_regression_endpoints import (
    canonical_rows,
    load_jsonl,
)


SCHEMA = "cpfi_endpoint_schema_backfill_feasibility_v1"
ISSUE_TYPE = "legacy_endpoint_schema_not_full_closure"
ACTION_CATEGORY = "endpoint_schema_upgrade"
DEFAULT_BACKLOG = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "integrity_remediation_backlog.json"
)
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "endpoint_schema_backfill_feasibility.json"
)

CLAIM_BOUNDARIES = [
    "This feasibility audit does not rerun models or reconstruct endpoint arrays.",
    "Ready rows indicate that config, ledger, prediction cache, and observed target bounds are available.",
    "Readiness is not proof that a later full v2 endpoint reconstruction will be fast or failure-free.",
    "Observed bounds are used for endpoint diagnostics only; they do not create bounded-support validity.",
    "This artifact is methodology provenance, not performance, fairness, causal, legal, production, or final-model-selection evidence.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--backlog", default=DEFAULT_BACKLOG)
    parser.add_argument("--out", default=DEFAULT_OUT)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def rel(path: Path, root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        return str(resolved_path.relative_to(resolved_root))
    except ValueError:
        return str(resolved_path)


def resolve(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def nested(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def numeric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def endpoint_actions(backlog: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in backlog.get("rows", []) or []
        if row.get("status") == "open"
        and row.get("issue_type") == ISSUE_TYPE
        and row.get("action_category") == ACTION_CATEGORY
    ]


def path_from_endpoint_payload(payload: dict[str, Any], *paths: tuple[str, ...]) -> str | None:
    for path in paths:
        value = nested(payload, *path)
        if isinstance(value, dict):
            value = value.get("path")
        if isinstance(value, str) and value:
            return value
    return None


def observed_bounds_from_endpoint(payload: dict[str, Any]) -> tuple[float | None, float | None, str | None]:
    bounds = payload.get("observed_target_bounds") or {}
    target_bounds = payload.get("target_bounds") or {}
    metadata = payload.get("metadata") or {}
    observed_price = metadata.get("observed_price_summary") or {}
    observed_target = metadata.get("observed_target_summary") or {}
    scope = payload.get("scope") or {}
    source_context = payload.get("source_context") or {}

    candidates = [
        (
            numeric(payload.get("observed_target_min")),
            numeric(payload.get("observed_target_max")),
            "endpoint_top_level",
        ),
        (
            numeric(payload.get("observed_min")),
            numeric(payload.get("observed_max")),
            "endpoint_top_level_legacy",
        ),
        (
            numeric(first_present(bounds.get("min"), bounds.get("observed_min"))),
            numeric(first_present(bounds.get("max"), bounds.get("observed_max"))),
            "endpoint_observed_target_bounds",
        ),
        (
            numeric(bounds.get("source_audit_min")),
            numeric(bounds.get("source_audit_max")),
            "endpoint_source_audit_bounds",
        ),
        (
            numeric(bounds.get("benchmark_test_min_across_reconstructed_runs")),
            numeric(bounds.get("benchmark_test_max_across_reconstructed_runs")),
            "endpoint_benchmark_test_bounds",
        ),
        (
            numeric(target_bounds.get("observed_min")),
            numeric(target_bounds.get("observed_max")),
            "endpoint_target_bounds",
        ),
        (
            numeric(observed_price.get("min")),
            numeric(observed_price.get("max")),
            "endpoint_observed_price_summary",
        ),
        (
            numeric(observed_target.get("min")),
            numeric(observed_target.get("max")),
            "endpoint_observed_target_summary",
        ),
        (
            numeric(scope.get("observed_target_min")),
            numeric(scope.get("observed_target_max")),
            "endpoint_scope",
        ),
        (
            numeric(source_context.get("observed_target_min")),
            numeric(
                first_present(
                    source_context.get("observed_target_cap_max"),
                    source_context.get("observed_cap_value"),
                )
            ),
            "endpoint_source_context",
        ),
    ]
    for observed_min, observed_max, source in candidates:
        if observed_min is not None and observed_max is not None:
            return observed_min, observed_max, source
    return None, None, None


def observed_bounds_from_config(config: dict[str, Any]) -> tuple[float | None, float | None, str | None]:
    quality = config.get("quality_controls") or {}
    pairs = [
        ("quality_observed_min", "quality_observed_max", "config_quality_observed_bounds"),
        ("target_observed_min", "target_observed_max", "config_target_observed_bounds"),
        ("observed_target_min", "observed_target_max", "config_observed_target_bounds"),
    ]
    for min_key, max_key, source in pairs:
        observed_min = numeric(quality.get(min_key))
        observed_max = numeric(quality.get(max_key))
        if observed_min is not None and observed_max is not None:
            return observed_min, observed_max, source
    return None, None, None


def observed_bounds_from_dataset_audits(
    root: Path,
    dataset_ids: list[str],
) -> tuple[float | None, float | None, str | None, list[str]]:
    bounds: list[tuple[float, float]] = []
    sources: list[str] = []
    for dataset_id in dataset_ids:
        audit_path = root / "experiments/regression/audits" / str(dataset_id) / "audit.json"
        if not audit_path.exists():
            continue
        try:
            audit = read_json(audit_path)
        except json.JSONDecodeError:
            continue
        observed_min = numeric(audit.get("target_min"))
        observed_max = numeric(audit.get("target_max"))
        if observed_min is None or observed_max is None:
            continue
        bounds.append((observed_min, observed_max))
        sources.append(rel(audit_path, root))
    if not bounds:
        return None, None, None, sources
    return (
        min(item[0] for item in bounds),
        max(item[1] for item in bounds),
        "dataset_audit_target_bounds",
        sources,
    )


def infer_observed_bounds(
    root: Path,
    *,
    endpoint_payload: dict[str, Any],
    config: dict[str, Any],
    dataset_ids: list[str],
) -> tuple[float | None, float | None, str | None, list[str]]:
    observed_min, observed_max, source = observed_bounds_from_endpoint(endpoint_payload)
    if source:
        return observed_min, observed_max, source, []
    observed_min, observed_max, source = observed_bounds_from_config(config)
    if source:
        return observed_min, observed_max, source, []
    return observed_bounds_from_dataset_audits(root, dataset_ids)


def infer_lower_floor(endpoint_payload: dict[str, Any]) -> float | None:
    bounds = endpoint_payload.get("observed_target_bounds") or {}
    target_bounds = endpoint_payload.get("target_bounds") or {}
    source_context = endpoint_payload.get("source_context") or {}
    return first_present(
        numeric(endpoint_payload.get("lower_floor")),
        numeric(bounds.get("natural_floor")),
        numeric(bounds.get("logical_lower_percent")),
        numeric(target_bounds.get("possible_min")),
        numeric(source_context.get("natural_floor_checked")),
    )


def infer_upper_warning(endpoint_payload: dict[str, Any]) -> float | None:
    bounds = endpoint_payload.get("observed_target_bounds") or {}
    target_bounds = endpoint_payload.get("target_bounds") or {}
    scope = endpoint_payload.get("scope") or {}
    source_context = endpoint_payload.get("source_context") or {}
    return first_present(
        numeric(endpoint_payload.get("upper_warning")),
        numeric(bounds.get("upper_10x")),
        numeric(bounds.get("upper_2x_observed_max")),
        numeric(bounds.get("upper_10x_observed_max_threshold")),
        numeric(bounds.get("upper_2x_observed_max_threshold")),
        numeric(target_bounds.get("possible_max")),
        numeric(scope.get("observed_target_double_max")),
        numeric(source_context.get("observed_target_cap_max")),
    )


def ledger_profile(path: Path | None) -> tuple[int | None, dict[str, int], str | None]:
    if path is None or not path.exists():
        return None, {}, "missing_ledger"
    try:
        rows = canonical_rows(load_jsonl(path))
    except Exception as exc:  # pragma: no cover - defensive audit guard.
        return None, {}, f"{type(exc).__name__}: {exc}"
    completed = [row for row in rows if row.get("status") == "completed"]
    counts = Counter(str(row.get("cp_method", "missing")) for row in completed)
    return len(completed), dict(sorted((key, int(value)) for key, value in counts.items())), None


def completed_method_expense_flags(method_counts: dict[str, int]) -> list[str]:
    expensive = []
    for method in (
        "cqr",
        "cv_plus",
        "cv_minmax",
        "jackknife_plus",
        "jackknife_minmax",
        "jackknife_plus_after_bootstrap",
    ):
        if int(method_counts.get(method, 0)) > 0:
            expensive.append(method)
    return expensive


def old_partial_methods(endpoint_payload: dict[str, Any]) -> list[str]:
    metadata = endpoint_payload.get("metadata") or {}
    values = first_present(
        metadata.get("skipped_exact_endpoint_reconstruction_methods"),
        metadata.get("methods_skipped_exact_endpoint_reconstruction"),
        endpoint_payload.get("skipped_exact_endpoint_reconstruction_methods"),
    )
    if isinstance(values, list):
        return sorted(str(value) for value in values)
    return []


def build_row(root: Path, action: dict[str, Any]) -> dict[str, Any]:
    report_name = str(action.get("report_name"))
    endpoint_path = None
    source_paths = action.get("source_sidecar_paths") or []
    if source_paths:
        endpoint_path = resolve(root, str(source_paths[0]))
    if endpoint_path is None:
        endpoint_path = root / "experiments/regression/reports" / report_name / "endpoint_audit.json"

    config_path = resolve(root, action.get("config_path"))
    endpoint_payload: dict[str, Any] = {}
    config: dict[str, Any] = {}
    blockers: list[str] = []

    if endpoint_path is None or not endpoint_path.exists():
        blockers.append("missing_endpoint_audit")
    else:
        try:
            endpoint_payload = read_json(endpoint_path)
        except json.JSONDecodeError:
            blockers.append("malformed_endpoint_audit")

    if config_path is None or not config_path.exists():
        blockers.append("missing_config")
    else:
        config = read_yaml(config_path)

    ledger_value = first_present(
        endpoint_payload.get("ledger_path"),
        path_from_endpoint_payload(
            endpoint_payload,
            ("metadata", "ledger"),
            ("metadata", "ledger_path"),
            ("scope", "ledger_path"),
            ("reconstruction", "ledger_path"),
            ("ledger",),
        ),
        nested(config, "logging", "ledger"),
    )
    prediction_cache_value = first_present(
        nested(config, "logging", "prediction_cache_root"),
        nested(endpoint_payload, "reconstruction", "prediction_cache_root"),
    )
    ledger_path = resolve(root, str(ledger_value)) if ledger_value else None
    prediction_cache_root = (
        resolve(root, str(prediction_cache_value)) if prediction_cache_value else None
    )

    if ledger_path is None or not ledger_path.exists():
        blockers.append("missing_ledger")
    if prediction_cache_root is None or not prediction_cache_root.exists():
        blockers.append("missing_prediction_cache_root")

    dataset_ids = [str(value) for value in action.get("dataset_ids", []) or []]
    observed_min, observed_max, bounds_source, bounds_source_paths = infer_observed_bounds(
        root,
        endpoint_payload=endpoint_payload,
        config=config,
        dataset_ids=dataset_ids,
    )
    if observed_min is None or observed_max is None:
        blockers.append("missing_observed_target_bounds")

    completed_rows, method_counts, ledger_error = ledger_profile(ledger_path)
    if ledger_error:
        blockers.append(ledger_error)

    status = "ready_for_v2_reconstruction" if not blockers else "blocked_missing_inputs"
    command = None
    if status == "ready_for_v2_reconstruction":
        report_dir = root / "experiments/regression/reports" / report_name
        command_parts = [
            "PYTHONPATH=.",
            "/home/emre/miniconda3/envs/ml/bin/python",
            "experiments/regression/scripts/audit_regression_endpoints.py",
            "--config",
            rel(config_path, root) if config_path else "",
            "--ledger",
            rel(ledger_path, root) if ledger_path else "",
            "--out-dir",
            rel(report_dir, root),
            "--title",
            report_name,
            "--observed-min",
            str(observed_min),
            "--observed-max",
            str(observed_max),
            "--progress-every",
            "25",
        ]
        lower_floor = infer_lower_floor(endpoint_payload)
        upper_warning = infer_upper_warning(endpoint_payload)
        if lower_floor is not None:
            command_parts.extend(["--lower-floor", str(lower_floor)])
        if upper_warning is not None:
            command_parts.extend(["--upper-warning", str(upper_warning)])
        command = " ".join(command_parts)
    else:
        lower_floor = infer_lower_floor(endpoint_payload)
        upper_warning = infer_upper_warning(endpoint_payload)

    old_schema = first_present(
        endpoint_payload.get("audit_schema"),
        endpoint_payload.get("schema"),
        endpoint_payload.get("schema_version"),
        nested(endpoint_payload, "metadata", "schema"),
    )
    expensive_methods = completed_method_expense_flags(method_counts)
    old_partial = old_partial_methods(endpoint_payload)
    return {
        "action_id": action.get("action_id"),
        "report_id": action.get("report_id"),
        "report_name": report_name,
        "status": status,
        "blockers": blockers,
        "old_schema": old_schema,
        "config_path": None if config_path is None else rel(config_path, root),
        "ledger_path": None if ledger_path is None else rel(ledger_path, root),
        "prediction_cache_root": None
        if prediction_cache_root is None
        else rel(prediction_cache_root, root),
        "endpoint_audit_path": None if endpoint_path is None else rel(endpoint_path, root),
        "dataset_ids": dataset_ids,
        "observed_target_min": observed_min,
        "observed_target_max": observed_max,
        "observed_bounds_source": bounds_source,
        "observed_bounds_source_paths": bounds_source_paths,
        "lower_floor": lower_floor,
        "upper_warning": upper_warning,
        "completed_ledger_rows": completed_rows,
        "completed_method_counts": method_counts,
        "expensive_full_reconstruction_methods": expensive_methods,
        "old_partial_reconstruction_omitted_methods": old_partial,
        "estimated_command": command,
    }


def build_payload(root: Path, backlog_path: Path, out_path: Path) -> dict[str, Any]:
    backlog = read_json(backlog_path)
    rows = [build_row(root, action) for action in endpoint_actions(backlog)]
    status_counts = Counter(str(row["status"]) for row in rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_backlog_path": rel(backlog_path, root),
        "out_path": rel(out_path, root),
        "issue_type": ISSUE_TYPE,
        "action_category": ACTION_CATEGORY,
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "action_count": len(rows),
            "ready_count": int(status_counts.get("ready_for_v2_reconstruction", 0)),
            "blocked_count": int(status_counts.get("blocked_missing_inputs", 0)),
            "status_counts": dict(sorted(status_counts.items())),
            "completed_ledger_rows_ready": sum(
                int(row.get("completed_ledger_rows") or 0)
                for row in rows
                if row["status"] == "ready_for_v2_reconstruction"
            ),
            "reports_ready": sorted(
                row["report_name"]
                for row in rows
                if row["status"] == "ready_for_v2_reconstruction"
            ),
        },
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Endpoint Schema Backfill Feasibility",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source backlog: `{payload['source_backlog_path']}`",
        f"- Actions: {summary['action_count']}",
        f"- Ready for v2 reconstruction: {summary['ready_count']}",
        f"- Blocked: {summary['blocked_count']}",
        f"- Status counts: `{summary['status_counts']}`",
        f"- Completed ledger rows ready: {summary['completed_ledger_rows_ready']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Report | Status | Old schema | Bounds source | Completed rows | Expensive methods | Blockers |",
            "| --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row['report_name']}` | "
            f"`{row['status']}` | "
            f"`{row.get('old_schema')}` | "
            f"`{row.get('observed_bounds_source')}` | "
            f"{int(row.get('completed_ledger_rows') or 0)} | "
            f"`{row.get('expensive_full_reconstruction_methods') or []}` | "
            f"`{row.get('blockers') or []}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    backlog_path = resolve(root, args.backlog) or Path(args.backlog)
    out_path = resolve(root, args.out) or Path(args.out)
    payload = build_payload(root, backlog_path, out_path)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(json.dumps({"status": "ok", **payload["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
