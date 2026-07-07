"""Decompose completed Venn-Abers score-grid blockers into failure modes.

The report produced here is diagnostic evidence only. It summarizes why the
completed score-grid evidence still does not support a validated Venn-Abers
regression interval claim.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_venn_abers_grid_failure_mode_decomposition_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "venn_abers_grid_failure_mode_decomposition.json"
DEFAULT_WORKER_STATE = Path(
    "experiments/regression/results/venn_abers_grid_expansion/checkpoints/"
    "row_results.jsonl"
)
WORKER_ROW_SCHEMA = "cpfi_regression_venn_abers_grid_expansion_row_v1"
NOMINAL_COVERAGE = 0.9


SOURCE_REPORTS: tuple[dict[str, str], ...] = (
    {
        "report_id": "report:venn_abers_real_data_diagnostic",
        "role": "real_data_negative_diagnostic",
        "path": "experiments/regression/reports/venn_abers_real_data_diagnostic/"
        "diagnostic.json",
    },
    {
        "report_id": "report:venn_abers_fairness_panel_diagnostic",
        "role": "fairness_panel_negative_diagnostic",
        "path": "experiments/regression/reports/venn_abers_fairness_panel_diagnostic/"
        "diagnostic.json",
    },
    {
        "report_id": "report:venn_abers_biomarker_clinical_panel_diagnostic",
        "role": "biomarker_panel_negative_diagnostic",
        "path": "experiments/regression/reports/"
        "venn_abers_biomarker_clinical_panel_diagnostic/diagnostic.json",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument(
        "--worker-state",
        default=str(DEFAULT_WORKER_STATE),
        help="Append-only Venn-Abers grid expansion worker state.",
    )
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


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


def numeric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def task_key(row: dict[str, Any]) -> tuple[str, str, int] | None:
    report_id = row.get("report_id")
    run_id = row.get("run_id")
    test_index = row.get("test_index")
    if report_id is None or run_id is None or test_index is None:
        return None
    try:
        return str(report_id), str(run_id), int(test_index)
    except (TypeError, ValueError):
        return None


def worker_state_index(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed_by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    failed_rows: list[dict[str, Any]] = []
    duplicate_completed = 0
    for row in rows:
        if row.get("schema") != WORKER_ROW_SCHEMA:
            continue
        key = task_key(row)
        status = row.get("status")
        if status == "completed" and key is not None:
            if key in completed_by_key:
                duplicate_completed += 1
            completed_by_key[key] = row
        elif status == "failed":
            failed_rows.append(row)
    completed_rows = list(completed_by_key.values())
    by_report_run: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_report: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_dataset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in completed_rows:
        report_id = str(row.get("report_id"))
        run_id = str(row.get("run_id"))
        dataset_id = str(row.get("dataset_id"))
        by_report_run[(report_id, run_id)].append(row)
        by_report[report_id].append(row)
        by_dataset[dataset_id].append(row)
    return {
        "completed_rows": completed_rows,
        "failed_rows": failed_rows,
        "completed_by_report_run": by_report_run,
        "completed_by_report": by_report,
        "completed_by_dataset": by_dataset,
        "duplicate_completed_key_count": duplicate_completed,
    }


def count_bool(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if bool_value(row.get(field)) is True)


def known_bool_count(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if bool_value(row.get(field)) is not None)


def source_run_rows(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for spec in SOURCE_REPORTS:
        path = resolve(root, spec["path"])
        payload = read_json(path)
        reports.append(
            {
                "report_id": spec["report_id"],
                "role": spec["role"],
                "path": rel(path, root),
                "exists": path.exists(),
                "result_count": len(payload.get("results") or []),
            }
        )
        for result in payload.get("results") or []:
            grid = result.get("venn_abers_quantile_grid_reference") or {}
            grid_metrics = grid.get("grid_metrics") or {}
            bridge_metrics = grid.get("bridge_metrics") or {}
            split_metrics = grid.get("split_fallback_metrics") or {}
            scored = safe_int(grid.get("test_rows_scored"))
            rows.append(
                {
                    "report_id": spec["report_id"],
                    "role": spec["role"],
                    "source_path": rel(path, root),
                    "run_id": str(result.get("run_id")),
                    "dataset_id": str(result.get("dataset_id")),
                    "model_id": str(result.get("model_id")),
                    "model_family": str(result.get("model_family")),
                    "seed": result.get("seed"),
                    "alpha": result.get("alpha"),
                    "target": result.get("target"),
                    "target_transform": result.get("target_transform"),
                    "source_grid_rows_scored": scored,
                    "test_rows_available": safe_int(grid.get("test_rows_available")),
                    "source_grid_covered_estimate": (
                        numeric(grid_metrics.get("coverage")) * scored
                        if numeric(grid_metrics.get("coverage")) is not None
                        else 0.0
                    ),
                    "source_grid_hit_upper_estimate": (
                        numeric(grid.get("grid_hit_upper_rate")) * scored
                        if numeric(grid.get("grid_hit_upper_rate")) is not None
                        else 0.0
                    ),
                    "source_grid_coverage": numeric(grid_metrics.get("coverage")),
                    "source_grid_hit_upper_rate": numeric(
                        grid.get("grid_hit_upper_rate")
                    ),
                    "source_bridge_coverage": numeric(bridge_metrics.get("coverage")),
                    "source_split_fallback_coverage": numeric(
                        split_metrics.get("coverage")
                    ),
                    "grid_radius_ratio_vs_bridge": numeric(
                        grid.get("grid_radius_ratio_vs_bridge")
                    ),
                    "score_grid_size": safe_int(grid.get("score_grid_size")),
                }
            )
    return rows, reports


def combine_run(
    source_row: dict[str, Any],
    worker_rows: list[dict[str, Any]],
    nominal_coverage: float,
    max_upper_hit_rate: float,
) -> dict[str, Any]:
    source_scored = safe_int(source_row.get("source_grid_rows_scored"))
    worker_scored = len(worker_rows)
    total_scored = source_scored + worker_scored
    worker_grid_covered = count_bool(worker_rows, "grid_covered")
    worker_grid_hit_upper = count_bool(worker_rows, "grid_hit_upper")
    grid_covered_estimate = (
        float(source_row.get("source_grid_covered_estimate") or 0.0)
        + worker_grid_covered
    )
    grid_hit_upper_estimate = (
        float(source_row.get("source_grid_hit_upper_estimate") or 0.0)
        + worker_grid_hit_upper
    )
    bridge_known = known_bool_count(worker_rows, "bridge_covered")
    split_known = known_bool_count(worker_rows, "split_fallback_covered")
    bridge_covered = count_bool(worker_rows, "bridge_covered")
    split_covered = count_bool(worker_rows, "split_fallback_covered")
    source_bridge_covered = (
        source_row["source_bridge_coverage"] * source_scored
        if source_row.get("source_bridge_coverage") is not None
        else 0.0
    )
    source_split_covered = (
        source_row["source_split_fallback_coverage"] * source_scored
        if source_row.get("source_split_fallback_coverage") is not None
        else 0.0
    )
    grid_coverage = ratio(grid_covered_estimate, total_scored)
    upper_hit_rate = ratio(grid_hit_upper_estimate, total_scored)
    bridge_coverage = ratio(
        source_bridge_covered + bridge_covered,
        source_scored + bridge_known,
    )
    split_coverage = ratio(
        source_split_covered + split_covered,
        source_scored + split_known,
    )
    coverage_deficit = (
        max(0.0, nominal_coverage - grid_coverage)
        if grid_coverage is not None
        else None
    )
    return {
        **source_row,
        "worker_grid_rows_scored": worker_scored,
        "grid_reference_rows_scored": total_scored,
        "grid_reference_rows_available": source_row.get("test_rows_available"),
        "grid_reference_coverage": grid_coverage,
        "grid_reference_covered_estimate": grid_covered_estimate,
        "grid_coverage_deficit_vs_nominal": coverage_deficit,
        "grid_hit_upper_count_estimate": grid_hit_upper_estimate,
        "grid_hit_upper_rate": upper_hit_rate,
        "bridge_coverage": bridge_coverage,
        "split_fallback_coverage": split_coverage,
        "coverage_failure": bool(
            grid_coverage is not None and grid_coverage < nominal_coverage
        ),
        "upper_boundary_failure": bool(
            upper_hit_rate is not None and upper_hit_rate > max_upper_hit_rate
        ),
    }


def aggregate_rows(
    rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
    nominal_coverage: float,
    max_upper_hit_rate: float,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(str(row.get(field)) for field in key_fields)
        grouped[key].append(row)
    out = []
    for key, group in sorted(grouped.items()):
        scored = sum(safe_int(row.get("grid_reference_rows_scored")) for row in group)
        available = sum(
            safe_int(row.get("grid_reference_rows_available")) for row in group
        )
        covered = sum(
            float(row.get("grid_reference_covered_estimate") or 0.0)
            for row in group
        )
        upper_hits = sum(
            float(row.get("grid_hit_upper_count_estimate") or 0.0)
            for row in group
        )
        coverage = ratio(covered, scored)
        upper_hit_rate = ratio(upper_hits, scored)
        payload = {
            field: value for field, value in zip(key_fields, key, strict=True)
        }
        payload.update(
            {
                "run_count": len(group),
                "dataset_count": len({str(row.get("dataset_id")) for row in group}),
                "grid_reference_rows_scored": scored,
                "grid_reference_rows_available": available,
                "grid_reference_coverage": coverage,
                "grid_coverage_deficit_vs_nominal": (
                    max(0.0, nominal_coverage - coverage)
                    if coverage is not None
                    else None
                ),
                "grid_hit_upper_count_estimate": upper_hits,
                "grid_hit_upper_rate": upper_hit_rate,
                "coverage_failure": bool(
                    coverage is not None and coverage < nominal_coverage
                ),
                "upper_boundary_failure": bool(
                    upper_hit_rate is not None and upper_hit_rate > max_upper_hit_rate
                ),
            }
        )
        out.append(payload)
    return out


def top_by(rows: list[dict[str, Any]], field: str, limit: int = 10) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            row.get(field) is not None,
            float(row.get(field) or 0.0),
            safe_int(row.get("grid_reference_rows_scored")),
        ),
        reverse=True,
    )[:limit]


def check(
    check_id: str,
    condition: bool,
    *,
    description: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if condition else "fail",
        "severity": "hard",
        "description": description,
        "details": details or {},
    }


def build_payload(
    root: Path,
    worker_state_path: str | Path = DEFAULT_WORKER_STATE,
) -> dict[str, Any]:
    protocol_path = root / REPORT_DIR / "venn_abers_grid_ivapd_validation_protocol.json"
    plan_path = root / REPORT_DIR / "venn_abers_grid_expansion_plan.json"
    protocol = read_json(protocol_path)
    plan = read_json(plan_path)
    protocol_summary = protocol.get("summary") or {}
    plan_summary = plan.get("summary") or {}
    nominal_coverage = numeric(protocol.get("nominal_coverage")) or NOMINAL_COVERAGE
    claim_thresholds = protocol.get("claim_thresholds") or {}
    max_upper_hit_rate = numeric(
        claim_thresholds.get("max_grid_upper_hit_rate_for_claim")
    )
    if max_upper_hit_rate is None:
        max_upper_hit_rate = 0.0

    worker_path = resolve(root, worker_state_path)
    worker_rows = read_jsonl(worker_path)
    worker_state = worker_state_index(worker_rows)
    source_rows, source_reports = source_run_rows(root)
    runs = [
        combine_run(
            row,
            worker_state["completed_by_report_run"].get(
                (str(row["report_id"]), str(row["run_id"])),
                [],
            ),
            nominal_coverage,
            max_upper_hit_rate,
        )
        for row in source_rows
    ]
    panels = aggregate_rows(
        runs,
        ("report_id", "role"),
        nominal_coverage,
        max_upper_hit_rate,
    )
    datasets = aggregate_rows(
        runs,
        ("dataset_id",),
        nominal_coverage,
        max_upper_hit_rate,
    )

    checks = [
        check(
            "protocol_report_present",
            protocol_path.exists() and bool(protocol_summary),
            description="Grid/IVAPD protocol report is available.",
            details={"path": rel(protocol_path, root)},
        ),
        check(
            "grid_expansion_plan_present",
            plan_path.exists() and bool(plan_summary),
            description="Grid expansion plan report is available.",
            details={"path": rel(plan_path, root)},
        ),
        check(
            "worker_state_present",
            worker_path.exists(),
            description="Append-only row-level worker state is available.",
            details={"path": rel(worker_path, root), "row_count": len(worker_rows)},
        ),
        check(
            "source_diagnostic_reports_present",
            all(row["exists"] for row in source_reports),
            description="All Venn-Abers diagnostic source reports are present.",
            details={"source_reports": source_reports},
        ),
        check(
            "decomposition_has_run_rows",
            len(runs) > 0,
            description="Run-level failure-mode rows were reconstructed.",
            details={"run_count": len(runs)},
        ),
        check(
            "grid_expansion_is_complete",
            plan_summary.get("overall_status") == "venn_abers_grid_expansion_plan_complete"
            and safe_int(plan_summary.get("total_grid_rows_pending")) == 0,
            description="The failure-mode decomposition is based on a complete score-grid expansion.",
            details={
                "overall_status": plan_summary.get("overall_status"),
                "total_grid_rows_pending": plan_summary.get("total_grid_rows_pending"),
            },
        ),
        check(
            "no_validated_venn_abers_claim_enforced",
            protocol_summary.get("can_support_validated_venn_abers_regression")
            is False
            and safe_int(protocol_summary.get("validation_blocker_count")) > 0,
            description="Protocol keeps the validated Venn-Abers regression claim blocked.",
            details={
                "validation_blocker_ids": protocol_summary.get(
                    "validation_blocker_ids",
                    [],
                )
            },
        ),
        check(
            "scored_rows_match_protocol_and_plan",
            safe_int(protocol_summary.get("total_grid_reference_rows_scored"))
            == safe_int(protocol_summary.get("total_grid_reference_rows_available"))
            == safe_int(plan_summary.get("total_grid_rows_completed"))
            == safe_int(plan_summary.get("total_test_rows_available")),
            description="Full-grid scored row totals agree across protocol and plan.",
            details={
                "protocol_scored": protocol_summary.get(
                    "total_grid_reference_rows_scored"
                ),
                "protocol_available": protocol_summary.get(
                    "total_grid_reference_rows_available"
                ),
                "plan_completed": plan_summary.get("total_grid_rows_completed"),
                "plan_available": plan_summary.get("total_test_rows_available"),
            },
        ),
    ]
    failed_check_count = sum(1 for row in checks if row["status"] != "pass")
    blocker_ids = list(protocol_summary.get("validation_blocker_ids") or [])
    coverage_failure_panels = [row for row in panels if row["coverage_failure"]]
    upper_hit_panels = [row for row in panels if row["upper_boundary_failure"]]
    coverage_failure_runs = [row for row in runs if row["coverage_failure"]]
    upper_hit_runs = [row for row in runs if row["upper_boundary_failure"]]
    coverage_failure_datasets = [row for row in datasets if row["coverage_failure"]]
    upper_hit_datasets = [row for row in datasets if row["upper_boundary_failure"]]
    top_coverage_deficits = top_by(
        [row for row in runs if row.get("grid_coverage_deficit_vs_nominal")],
        "grid_coverage_deficit_vs_nominal",
    )
    top_upper_hits = top_by(
        [row for row in runs if row.get("grid_hit_upper_rate")],
        "grid_hit_upper_rate",
    )
    max_run_upper_hit_rate = max(
        (float(row["grid_hit_upper_rate"]) for row in runs if row.get("grid_hit_upper_rate") is not None),
        default=None,
    )
    min_run_coverage = min(
        (float(row["grid_reference_coverage"]) for row in runs if row.get("grid_reference_coverage") is not None),
        default=None,
    )
    summary = {
        "overall_status": (
            "venn_abers_grid_failure_modes_decomposed_no_claim"
            if failed_check_count == 0
            else "venn_abers_grid_failure_mode_decomposition_audit_fail"
        ),
        "failed_check_count": failed_check_count,
        "claim_status": "no_validated_venn_abers_regression_claim",
        "can_support_validated_venn_abers_regression": False,
        "nominal_coverage": nominal_coverage,
        "max_grid_upper_hit_rate_for_claim": max_upper_hit_rate,
        "source_report_count": len(source_reports),
        "panel_count": len(panels),
        "run_count": len(runs),
        "dataset_count": len(datasets),
        "grid_completion_fraction": plan_summary.get("grid_completion_fraction"),
        "total_grid_reference_rows_scored": protocol_summary.get(
            "total_grid_reference_rows_scored"
        ),
        "total_grid_reference_rows_available": protocol_summary.get(
            "total_grid_reference_rows_available"
        ),
        "validation_blocker_count": len(blocker_ids),
        "validation_blocker_ids": blocker_ids,
        "coverage_failure_panel_count": len(coverage_failure_panels),
        "coverage_failure_run_count": len(coverage_failure_runs),
        "coverage_failure_dataset_count": len(coverage_failure_datasets),
        "upper_boundary_failure_panel_count": len(upper_hit_panels),
        "upper_boundary_failure_run_count": len(upper_hit_runs),
        "upper_boundary_failure_dataset_count": len(upper_hit_datasets),
        "worker_grid_hit_upper_count": protocol_summary.get("worker_grid_hit_upper_count"),
        "worker_grid_hit_upper_rate": protocol_summary.get("worker_grid_hit_upper_rate"),
        "min_run_grid_reference_coverage": min_run_coverage,
        "max_run_grid_hit_upper_rate": max_run_upper_hit_rate,
        "min_panel_grid_reference_coverage": min(
            (
                float(row["grid_reference_coverage"])
                for row in panels
                if row.get("grid_reference_coverage") is not None
            ),
            default=None,
        ),
        "max_panel_grid_hit_upper_rate": max(
            (
                float(row["grid_hit_upper_rate"])
                for row in panels
                if row.get("grid_hit_upper_rate") is not None
            ),
            default=None,
        ),
        "dominant_coverage_deficit_run_id": (
            top_coverage_deficits[0]["run_id"] if top_coverage_deficits else None
        ),
        "dominant_upper_boundary_run_id": (
            top_upper_hits[0]["run_id"] if top_upper_hits else None
        ),
        "ivapd_interval_cp_status": protocol_summary.get("ivapd_interval_cp_status"),
        "claim_boundary": (
            "This decomposition explains completed score-grid and IVAPD blockers; "
            "it does not validate Venn-Abers regression interval coverage."
        ),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_reports": source_reports,
        "source_artifacts": {
            "protocol": rel(protocol_path, root),
            "grid_expansion_plan": rel(plan_path, root),
            "worker_state": rel(worker_path, root),
        },
        "summary": summary,
        "checks": checks,
        "blocker_decomposition": {
            "coverage_below_nominal": {
                "blocker_id": "grid_reference_panel_coverage_below_nominal",
                "panel_count": len(coverage_failure_panels),
                "run_count": len(coverage_failure_runs),
                "dataset_count": len(coverage_failure_datasets),
                "top_runs": top_coverage_deficits,
                "top_datasets": top_by(
                    [
                        row
                        for row in datasets
                        if row.get("grid_coverage_deficit_vs_nominal")
                    ],
                    "grid_coverage_deficit_vs_nominal",
                ),
            },
            "candidate_grid_hits_upper_boundary": {
                "blocker_id": "grid_reference_candidate_grid_hits_upper_boundary",
                "panel_count": len(upper_hit_panels),
                "run_count": len(upper_hit_runs),
                "dataset_count": len(upper_hit_datasets),
                "top_runs": top_upper_hits,
                "top_datasets": top_by(
                    [row for row in datasets if row.get("grid_hit_upper_rate")],
                    "grid_hit_upper_rate",
                ),
            },
            "ivapd_predictive_distribution_only": {
                "blocker_id": "ivapd_threshold_grid_is_predictive_distribution_not_interval_cp",
                "present": (
                    "ivapd_threshold_grid_is_predictive_distribution_not_interval_cp"
                    in blocker_ids
                ),
                "status": protocol_summary.get("ivapd_interval_cp_status"),
            },
        },
        "panel_rows": panels,
        "dataset_rows": datasets,
        "run_rows": sorted(
            runs,
            key=lambda row: (
                str(row.get("report_id")),
                str(row.get("dataset_id")),
                str(row.get("model_id")),
                str(row.get("run_id")),
            ),
        ),
        "methodological_interpretation": [
            {
                "finding": "Exact-grid completion is solved.",
                "interpretation": (
                    "The remaining issue is not missing rows; it is that the "
                    "completed evidence still violates the coverage and "
                    "grid-boundary claim conditions."
                ),
            },
            {
                "finding": "Coverage failures are panel and run dependent.",
                "interpretation": (
                    "The failure-mode rows identify which panels and runs drive "
                    "the no-claim boundary."
                ),
            },
            {
                "finding": "IVAPD remains a predictive-distribution diagnostic.",
                "interpretation": (
                    "Threshold-grid IVAPD evidence must not be reported as "
                    "validated interval conformal prediction."
                ),
            },
        ],
    }


def pct(value: Any) -> str:
    number = numeric(value)
    return "NA" if number is None else f"{number:.6f}"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Venn-Abers Grid Failure-Mode Decomposition",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Claim status: `{summary['claim_status']}`",
        f"- Can support validated Venn-Abers regression: `{summary['can_support_validated_venn_abers_regression']}`",
        f"- Grid rows scored: {summary['total_grid_reference_rows_scored']} / {summary['total_grid_reference_rows_available']}",
        f"- Grid completion fraction: {summary['grid_completion_fraction']}",
        f"- Validation blockers: {summary['validation_blocker_count']} `{summary['validation_blocker_ids']}`",
        f"- Coverage failure panels/runs/datasets: {summary['coverage_failure_panel_count']} / {summary['coverage_failure_run_count']} / {summary['coverage_failure_dataset_count']}",
        f"- Upper-boundary failure panels/runs/datasets: {summary['upper_boundary_failure_panel_count']} / {summary['upper_boundary_failure_run_count']} / {summary['upper_boundary_failure_dataset_count']}",
        f"- Min run grid coverage: {pct(summary['min_run_grid_reference_coverage'])}",
        f"- Max run grid upper-hit rate: {pct(summary['max_run_grid_hit_upper_rate'])}",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
        "## Panel Rows",
        "",
        "| report | scored / available | coverage | deficit | upper-hit rate | coverage failure | upper-boundary failure |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["panel_rows"]:
        lines.append(
            "| "
            f"{row['report_id']} | "
            f"{row['grid_reference_rows_scored']} / {row['grid_reference_rows_available']} | "
            f"{pct(row['grid_reference_coverage'])} | "
            f"{pct(row['grid_coverage_deficit_vs_nominal'])} | "
            f"{pct(row['grid_hit_upper_rate'])} | "
            f"`{row['coverage_failure']}` | "
            f"`{row['upper_boundary_failure']}` |"
        )
    lines.extend(
        [
            "",
            "## Top Coverage Deficits",
            "",
            "| run | dataset | model | scored | coverage | deficit |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in payload["blocker_decomposition"]["coverage_below_nominal"]["top_runs"]:
        lines.append(
            "| "
            f"{row['run_id']} | {row['dataset_id']} | {row['model_id']} | "
            f"{row['grid_reference_rows_scored']} | "
            f"{pct(row['grid_reference_coverage'])} | "
            f"{pct(row['grid_coverage_deficit_vs_nominal'])} |"
        )
    lines.extend(
        [
            "",
            "## Top Upper-Boundary Hits",
            "",
            "| run | dataset | model | scored | hit count estimate | hit rate |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in payload["blocker_decomposition"]["candidate_grid_hits_upper_boundary"][
        "top_runs"
    ]:
        lines.append(
            "| "
            f"{row['run_id']} | {row['dataset_id']} | {row['model_id']} | "
            f"{row['grid_reference_rows_scored']} | "
            f"{pct(row['grid_hit_upper_count_estimate'])} | "
            f"{pct(row['grid_hit_upper_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
        ]
    )
    for row in payload["methodological_interpretation"]:
        lines.append(f"- {row['finding']} {row['interpretation']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = resolve(root, args.out)
    payload = build_payload(root, worker_state_path=args.worker_state)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "out": rel(out, root),
                "failed_check_count": payload["summary"]["failed_check_count"],
                "coverage_failure_run_count": payload["summary"][
                    "coverage_failure_run_count"
                ],
                "upper_boundary_failure_run_count": payload["summary"][
                    "upper_boundary_failure_run_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
