"""Build diagnostic group-count, missingness, and gap evidence.

This artifact completes the empirical action for the fairness/population gate
without promoting any population or protected-class fairness claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from cpfi.regression.target import transform_target


SCHEMA = "cpfi_regression_fairness_group_diagnostic_audit_v1"
ACTION_ID = "fairness_population_inference_gate.compute_group_counts_missingness_and_gaps"
GATE_ID = "fairness_population_inference_gate"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "fairness_group_diagnostic_audit.json"
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
SAMPLING_WEIGHT_POLICY = Path(
    "experiments/regression/manuscript/fairness_sampling_weight_policy.json"
)
REPORTS_ROOT = Path("experiments/regression/reports")
RESULTS_ROOT = Path("experiments/regression/results")
BOOTSTRAP_REPLICATES = 500
CI_Z = 1.96


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=BOOTSTRAP_REPLICATES,
        help="Within-group bootstrap replicates for transformed target mean gaps.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def stable_seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % (2**32)


def finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def round_or_none(value: Any, digits: int = 10) -> float | None:
    result = finite_float(value)
    if result is None:
        return None
    return round(result, digits)


def numeric_summary(values: list[float]) -> dict[str, Any]:
    finite = np.asarray([value for value in values if math.isfinite(value)], dtype=float)
    if finite.size == 0:
        return {"count": 0}
    return {
        "count": int(finite.size),
        "min": round_or_none(np.min(finite)),
        "median": round_or_none(np.median(finite)),
        "mean": round_or_none(np.mean(finite)),
        "max": round_or_none(np.max(finite)),
        "std": round_or_none(np.std(finite, ddof=1)) if finite.size > 1 else 0.0,
    }


def mean_by_key(values: dict[str, list[float]]) -> dict[str, float]:
    return {
        key: round_or_none(float(np.mean(items)))
        for key, items in sorted(values.items())
        if items
    }


def ci_from_mean_std_count(
    *, mean: Any, std: Any, count: Any, metric: str, source: str
) -> dict[str, Any] | None:
    mean_value = finite_float(mean)
    std_value = finite_float(std)
    try:
        count_value = int(count)
    except (TypeError, ValueError):
        return None
    if mean_value is None or std_value is None or count_value <= 1:
        return None
    half_width = CI_Z * std_value / math.sqrt(count_value)
    return {
        "metric": metric,
        "source": source,
        "mean": round_or_none(mean_value),
        "std": round_or_none(std_value),
        "count": count_value,
        "low": round_or_none(mean_value - half_width),
        "high": round_or_none(mean_value + half_width),
        "method": "normal_approximation_across_repeated_seed_cells",
    }


def load_model_frame(dataset_id: str) -> tuple[pd.DataFrame, str, str]:
    from experiments.regression.scripts.run_regression_pilot import load_dataset_frame

    return load_dataset_frame(dataset_id)


def transformed_target(values: pd.Series, transform: str) -> np.ndarray:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[np.isfinite(numeric)].to_numpy(dtype=float)
    if finite.size == 0:
        return finite
    return transform_target(finite, transform)


def group_dataframe_diagnostics(
    frame: pd.DataFrame,
    *,
    target: str,
    group_col: str,
    target_transform: str,
    seed_key: str,
    bootstrap_replicates: int,
) -> dict[str, Any]:
    if target not in frame.columns:
        raise ValueError(f"target column {target!r} is absent from loaded frame")
    if group_col not in frame.columns:
        raise ValueError(f"group column {group_col!r} is absent from loaded frame")

    group = frame[group_col]
    group_missing_rate = float(group.isna().mean())
    group_labels = group.astype("object").where(group.notna(), "__missing__").astype(str)
    group_counts = Counter(group_labels)
    group_counts_dict = {
        key: int(count)
        for key, count in sorted(
            group_counts.items(), key=lambda item: (-item[1], item[0])
        )
    }
    feature_columns = [col for col in frame.columns if col != target]
    any_feature_missing = frame[feature_columns].isna().any(axis=1)
    target_missing = frame[target].isna()

    missingness_by_group: dict[str, dict[str, Any]] = {}
    for label in sorted(group_counts):
        mask = group_labels == label
        missingness_by_group[label] = {
            "row_count": int(mask.sum()),
            "target_missing_rate": round_or_none(target_missing[mask].mean()),
            "any_feature_missing_rate": round_or_none(any_feature_missing[mask].mean()),
            "group_value_missing_rate": 1.0 if label == "__missing__" else 0.0,
        }

    usable = frame.loc[group.notna() & frame[target].notna(), [group_col, target]].copy()
    usable[target] = pd.to_numeric(usable[target], errors="coerce")
    usable = usable[np.isfinite(usable[target])]
    target_by_group: dict[str, np.ndarray] = {}
    target_stats_by_group: dict[str, dict[str, Any]] = {}
    for value, subset in usable.groupby(group_col, dropna=True, observed=True):
        label = str(value)
        transformed = transformed_target(subset[target], target_transform)
        if transformed.size == 0:
            continue
        target_by_group[label] = transformed
        target_stats_by_group[label] = {
            "row_count": int(transformed.size),
            "transformed_target_mean": round_or_none(np.mean(transformed)),
            "transformed_target_median": round_or_none(np.median(transformed)),
            "transformed_target_std": round_or_none(np.std(transformed, ddof=1))
            if transformed.size > 1
            else 0.0,
        }

    target_mean_values = [
        float(item["transformed_target_mean"])
        for item in target_stats_by_group.values()
        if item["transformed_target_mean"] is not None
    ]
    observed_gap = (
        float(max(target_mean_values) - min(target_mean_values))
        if len(target_mean_values) >= 2
        else None
    )
    bootstrap_interval: dict[str, Any] | None = None
    if observed_gap is not None and bootstrap_replicates > 0:
        rng = np.random.default_rng(stable_seed(seed_key))
        labels = sorted(target_by_group)
        boot_gaps: list[float] = []
        for _ in range(bootstrap_replicates):
            means = []
            for label in labels:
                values = target_by_group[label]
                sample = values[rng.integers(0, len(values), len(values))]
                means.append(float(np.mean(sample)))
            boot_gaps.append(float(max(means) - min(means)))
        boot = np.asarray(boot_gaps, dtype=float)
        bootstrap_interval = {
            "metric": "transformed_target_mean_gap",
            "source": "loaded_model_frame",
            "observed": round_or_none(observed_gap),
            "low": round_or_none(np.quantile(boot, 0.025)),
            "high": round_or_none(np.quantile(boot, 0.975)),
            "bootstrap_replicates": int(bootstrap_replicates),
            "method": "within_group_nonparametric_bootstrap",
        }

    return {
        "frame_row_count": int(len(frame)),
        "frame_column_count": int(len(frame.columns)),
        "group_counts": group_counts_dict,
        "group_count": len(group_counts_dict),
        "min_group_count": int(min(group_counts.values())) if group_counts else 0,
        "group_missing_rate": round_or_none(group_missing_rate),
        "target_missing_rate": round_or_none(target_missing.mean()),
        "any_feature_missing_rate": round_or_none(any_feature_missing.mean()),
        "missingness_by_group": missingness_by_group,
        "target_stats_by_group": target_stats_by_group,
        "transformed_target_mean_gap": round_or_none(observed_gap),
        "transformed_target_mean_gap_ci95": bootstrap_interval,
        "target_gap_uncertainty_recorded": bootstrap_interval is not None,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(json.loads(text))
    return rows


def ledger_path_from_summary(
    root: Path, bundle_id: str, pilot_summary: dict[str, Any]
) -> Path:
    ledger = pilot_summary.get("ledger")
    if isinstance(ledger, str) and ledger:
        path = Path(ledger)
        return path if path.is_absolute() else root / path
    return root / RESULTS_ROOT / bundle_id / "ledger.jsonl"


def completed_run_gap_diagnostics(ledger_rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [
        row for row in ledger_rows if str(row.get("status") or "") == "completed"
    ]
    coverage_by_group: dict[str, list[float]] = defaultdict(list)
    width_by_group: dict[str, list[float]] = defaultdict(list)
    coverage_gaps: list[float] = []
    width_gaps: list[float] = []
    methods: Counter[str] = Counter()
    alphas: Counter[str] = Counter()
    for row in completed:
        methods[str(row.get("cp_method") or row.get("cp_method_id") or "")] += 1
        alphas[str(row.get("alpha"))] += 1
        coverage_gap = finite_float(row.get("coverage_gap"))
        width_gap = finite_float(row.get("width_gap"))
        if coverage_gap is not None:
            coverage_gaps.append(coverage_gap)
        if width_gap is not None:
            width_gaps.append(width_gap)
        for group, value in (row.get("coverage_by_group") or {}).items():
            finite = finite_float(value)
            if finite is not None:
                coverage_by_group[str(group)].append(finite)
        for group, value in (row.get("width_by_group") or {}).items():
            finite = finite_float(value)
            if finite is not None:
                width_by_group[str(group)].append(finite)
    return {
        "ledger_row_count": len(ledger_rows),
        "completed_run_count": len(completed),
        "cp_method_counts": dict(sorted(methods.items())),
        "alpha_counts": dict(sorted(alphas.items())),
        "coverage_by_group_mean": mean_by_key(coverage_by_group),
        "width_by_group_mean": mean_by_key(width_by_group),
        "coverage_gap_completed_run_summary": numeric_summary(coverage_gaps),
        "width_gap_completed_run_summary": numeric_summary(width_gaps),
        "coverage_by_group_recorded": bool(coverage_by_group),
        "width_by_group_recorded": bool(width_by_group),
    }


def pilot_repeated_seed_uncertainty(pilot_summary: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in pilot_summary.get("rows", []) or [] if isinstance(row, dict)]
    coverage_intervals: list[dict[str, Any]] = []
    width_intervals: list[dict[str, Any]] = []
    for row in rows:
        source = (
            f"{row.get('cp_method')}|alpha={row.get('alpha')}|"
            f"model={row.get('model_id')}|params={row.get('model_params_key')}"
        )
        coverage_ci = ci_from_mean_std_count(
            mean=row.get("coverage_gap_mean"),
            std=row.get("coverage_gap_std"),
            count=row.get("coverage_gap_count"),
            metric="coverage_gap",
            source=source,
        )
        width_ci = ci_from_mean_std_count(
            mean=row.get("width_gap_mean"),
            std=row.get("width_gap_std"),
            count=row.get("width_gap_count"),
            metric="width_gap",
            source=source,
        )
        if coverage_ci is not None:
            coverage_intervals.append(coverage_ci)
        if width_ci is not None:
            width_intervals.append(width_ci)
    coverage_means = [
        finite_float(row.get("coverage_gap_mean"))
        for row in rows
        if finite_float(row.get("coverage_gap_mean")) is not None
    ]
    width_means = [
        finite_float(row.get("width_gap_mean"))
        for row in rows
        if finite_float(row.get("width_gap_mean")) is not None
    ]
    best_coverage = min(coverage_intervals, key=lambda item: item["mean"], default=None)
    best_width = min(width_intervals, key=lambda item: item["mean"], default=None)
    return {
        "pilot_summary_row_count": len(rows),
        "coverage_gap_mean_summary": numeric_summary([float(v) for v in coverage_means]),
        "width_gap_mean_summary": numeric_summary([float(v) for v in width_means]),
        "coverage_gap_repeated_seed_interval_count": len(coverage_intervals),
        "width_gap_repeated_seed_interval_count": len(width_intervals),
        "representative_lowest_coverage_gap_ci95": best_coverage,
        "representative_lowest_width_gap_ci95": best_width,
        "predictive_gap_uncertainty_recorded": bool(
            coverage_intervals and width_intervals
        ),
    }


def sampling_policy_by_bundle(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("bundle_id")): row
        for row in payload.get("bundle_policy_rows", []) or []
        if isinstance(row, dict) and row.get("bundle_id")
    }


def diagnostic_bundle_row(
    root: Path,
    bundle: dict[str, Any],
    *,
    sampling_policy: dict[str, dict[str, Any]],
    bootstrap_replicates: int,
) -> dict[str, Any]:
    bundle_id = str(bundle.get("bundle_id") or "")
    dataset_id = str(bundle.get("dataset_id") or "")
    target = str(bundle.get("target") or "")
    target_transform = str(bundle.get("target_transform") or "identity")
    diagnostic_group = str(bundle.get("diagnostic_group") or "")
    frame, loader_target, loader_group = load_model_frame(dataset_id)
    group_col = diagnostic_group or loader_group
    if loader_target != target and target not in frame.columns:
        target = loader_target
    frame_diag = group_dataframe_diagnostics(
        frame,
        target=target,
        group_col=group_col,
        target_transform=target_transform,
        seed_key=bundle_id,
        bootstrap_replicates=bootstrap_replicates,
    )
    pilot_summary_path = root / REPORTS_ROOT / bundle_id / "pilot_summary.json"
    pilot_summary = read_json(pilot_summary_path)
    ledger_path = ledger_path_from_summary(root, bundle_id, pilot_summary)
    ledger_rows = read_jsonl(ledger_path)
    run_diag = completed_run_gap_diagnostics(ledger_rows)
    pilot_diag = pilot_repeated_seed_uncertainty(pilot_summary)
    policy = sampling_policy.get(bundle_id, {})
    group_gap_uncertainty_recorded = bool(
        frame_diag["target_gap_uncertainty_recorded"]
        and pilot_diag["predictive_gap_uncertainty_recorded"]
    )
    return {
        "action_id": ACTION_ID,
        "gate_id": GATE_ID,
        "bundle_id": bundle_id,
        "dataset_id": dataset_id,
        "target": target,
        "target_transform": target_transform,
        "diagnostic_group": diagnostic_group,
        "group_source_column": bundle.get("group_source_column") or group_col,
        "sampling_policy_id": policy.get("policy_id"),
        "sampling_policy_status": policy.get("policy_status"),
        "current_estimand_policy": policy.get("current_estimand_policy"),
        "claim_effect": "diagnostic_group_evidence_only_no_population_fairness_claim",
        "fairness_population_claim_status": "blocked_diagnostic_only_no_population_claim",
        "group_counts": frame_diag["group_counts"],
        "group_count": frame_diag["group_count"],
        "min_group_count": frame_diag["min_group_count"],
        "group_missing_rate": frame_diag["group_missing_rate"],
        "target_missing_rate": frame_diag["target_missing_rate"],
        "any_feature_missing_rate": frame_diag["any_feature_missing_rate"],
        "missingness_by_group": frame_diag["missingness_by_group"],
        "target_stats_by_group": frame_diag["target_stats_by_group"],
        "transformed_target_mean_gap": frame_diag["transformed_target_mean_gap"],
        "transformed_target_mean_gap_ci95": frame_diag[
            "transformed_target_mean_gap_ci95"
        ],
        "coverage_by_group": run_diag["coverage_by_group_mean"],
        "width_by_group": run_diag["width_by_group_mean"],
        "coverage_gap_completed_run_summary": run_diag[
            "coverage_gap_completed_run_summary"
        ],
        "width_gap_completed_run_summary": run_diag[
            "width_gap_completed_run_summary"
        ],
        "coverage_gap_repeated_seed_uncertainty": pilot_diag[
            "representative_lowest_coverage_gap_ci95"
        ],
        "width_gap_repeated_seed_uncertainty": pilot_diag[
            "representative_lowest_width_gap_ci95"
        ],
        "pilot_summary_gap_diagnostics": pilot_diag,
        "ledger_diagnostics": run_diag,
        "group_counts_recorded": bool(frame_diag["group_counts"]),
        "missingness_by_group_audited": bool(frame_diag["missingness_by_group"]),
        "coverage_by_group_recorded": run_diag["coverage_by_group_recorded"],
        "width_by_group_recorded": run_diag["width_by_group_recorded"],
        "group_gap_uncertainty_recorded": group_gap_uncertainty_recorded,
        "population_fairness_claim_promoted": False,
        "source_artifacts": [
            rel(root / BUNDLE_INDEX, root),
            rel(root / SAMPLING_WEIGHT_POLICY, root),
            rel(pilot_summary_path, root),
            rel(ledger_path, root),
        ],
    }


def build_payload(root: Path, *, bootstrap_replicates: int) -> dict[str, Any]:
    bundle_index_path = root / BUNDLE_INDEX
    sampling_policy_path = root / SAMPLING_WEIGHT_POLICY
    bundle_index = read_json(bundle_index_path)
    sampling_policy = sampling_policy_by_bundle(read_json(sampling_policy_path))
    bundles = [
        row
        for row in bundle_index.get("bundles", []) or []
        if isinstance(row, dict) and row.get("diagnostic_group")
    ]
    rows = [
        diagnostic_bundle_row(
            root,
            row,
            sampling_policy=sampling_policy,
            bootstrap_replicates=bootstrap_replicates,
        )
        for row in bundles
    ]
    failed_checks: list[dict[str, Any]] = []
    if not rows:
        failed_checks.append(
            {"check_id": "diagnostic_group_bundle_rows_present", "status": "fail"}
        )
    if not all(row["group_counts_recorded"] for row in rows):
        failed_checks.append(
            {"check_id": "all_bundle_group_counts_recorded", "status": "fail"}
        )
    if not all(row["missingness_by_group_audited"] for row in rows):
        failed_checks.append(
            {"check_id": "all_bundle_missingness_by_group_audited", "status": "fail"}
        )
    if not all(row["coverage_by_group_recorded"] for row in rows):
        failed_checks.append(
            {"check_id": "all_bundle_coverage_by_group_recorded", "status": "fail"}
        )
    if not all(row["width_by_group_recorded"] for row in rows):
        failed_checks.append(
            {"check_id": "all_bundle_width_by_group_recorded", "status": "fail"}
        )
    if not all(row["group_gap_uncertainty_recorded"] for row in rows):
        failed_checks.append(
            {"check_id": "all_bundle_group_gap_uncertainty_recorded", "status": "fail"}
        )
    if any(row["population_fairness_claim_promoted"] for row in rows):
        failed_checks.append(
            {"check_id": "no_population_fairness_claim_promoted", "status": "fail"}
        )

    dataset_counts = Counter(row["dataset_id"] for row in rows)
    status = (
        "fairness_group_diagnostic_audit_failed"
        if failed_checks
        else "fairness_group_diagnostic_audit_completed_no_fairness_claim"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": status,
            "action_id": ACTION_ID,
            "gate_id": GATE_ID,
            "action_status": "empirical_execution_complete"
            if not failed_checks
            else "incomplete",
            "claim_promoted_action_count": 0,
            "failed_check_count": len(failed_checks),
            "bundle_count": len(rows),
            "dataset_count": len(dataset_counts),
            "dataset_counts": dict(sorted(dataset_counts.items())),
            "group_counts_recorded_bundle_count": sum(
                1 for row in rows if row["group_counts_recorded"]
            ),
            "missingness_by_group_audited_bundle_count": sum(
                1 for row in rows if row["missingness_by_group_audited"]
            ),
            "coverage_by_group_recorded_bundle_count": sum(
                1 for row in rows if row["coverage_by_group_recorded"]
            ),
            "width_by_group_recorded_bundle_count": sum(
                1 for row in rows if row["width_by_group_recorded"]
            ),
            "group_gap_uncertainty_recorded_bundle_count": sum(
                1 for row in rows if row["group_gap_uncertainty_recorded"]
            ),
            "population_fairness_ready_bundle_count": 0,
            "bootstrap_replicates": bootstrap_replicates,
        },
        "completed_action_ids": [ACTION_ID] if not failed_checks else [],
        "checks": {
            "diagnostic_group_bundle_rows_present": bool(rows),
            "all_bundle_group_counts_recorded": all(
                row["group_counts_recorded"] for row in rows
            ),
            "all_bundle_missingness_by_group_audited": all(
                row["missingness_by_group_audited"] for row in rows
            ),
            "all_bundle_coverage_by_group_recorded": all(
                row["coverage_by_group_recorded"] for row in rows
            ),
            "all_bundle_width_by_group_recorded": all(
                row["width_by_group_recorded"] for row in rows
            ),
            "all_bundle_group_gap_uncertainty_recorded": all(
                row["group_gap_uncertainty_recorded"] for row in rows
            ),
            "no_population_fairness_claim_promoted": not any(
                row["population_fairness_claim_promoted"] for row in rows
            ),
        },
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This artifact records diagnostic group evidence only.",
            "Repeated-seed gap intervals summarize experiment stability, not population fairness uncertainty.",
            "Transformed-target group-gap bootstrap intervals summarize loaded benchmark rows, not a survey-weighted population estimand.",
            "No protected-class, legal, clinical, policy, causal, or population fairness claim is promoted by this audit.",
        ],
        "rows": rows,
        "sources": {
            "manuscript_bundle_index": rel(bundle_index_path, root),
            "fairness_sampling_weight_policy": rel(sampling_policy_path, root),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Fairness Group Diagnostic Audit",
        "",
        "This artifact records group diagnostic evidence. It does not promote a population fairness claim.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Action: `{summary['action_id']}`",
        f"- Bundles: {summary['bundle_count']}",
        f"- Datasets: {summary['dataset_count']}",
        f"- Group-count rows: {summary['group_counts_recorded_bundle_count']}",
        f"- Missingness-by-group rows: {summary['missingness_by_group_audited_bundle_count']}",
        f"- Coverage-by-group rows: {summary['coverage_by_group_recorded_bundle_count']}",
        f"- Width-by-group rows: {summary['width_by_group_recorded_bundle_count']}",
        f"- Group-gap uncertainty rows: {summary['group_gap_uncertainty_recorded_bundle_count']}",
        f"- Failed checks: {summary['failed_check_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Bundle Rows",
            "",
            "| Bundle | Dataset | Group | Min group n | Coverage gap mean | Width gap mean | Claim effect |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in payload["rows"]:
        coverage_mean = row["coverage_gap_completed_run_summary"].get("mean")
        width_mean = row["width_gap_completed_run_summary"].get("mean")
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['bundle_id']}`",
                    f"`{row['dataset_id']}`",
                    f"`{row['diagnostic_group']}`",
                    str(row["min_group_count"]),
                    str(coverage_mean),
                    str(width_mean),
                    f"`{row['claim_effect']}`",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = root / args.out
    payload = build_payload(root, bootstrap_replicates=args.bootstrap_replicates)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "out": rel(out_path, root),
                "failed_checks": payload["failed_checks"],
            },
            sort_keys=True,
        )
    )
    return 0 if not payload["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
