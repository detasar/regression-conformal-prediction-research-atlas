"""Audit the exact-grid and IVAPD path for Venn-Abers regression validation.

The fast Venn-Abers bridge already has negative run-level evidence. This audit
keeps the next path honest: the tiny score-grid reference and IVAPD threshold
grid are useful diagnostics, but they do not yet support a validated
Venn-Abers regression interval claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts import audit_venn_abers_validation_readiness as va_audit


SCHEMA = "cpfi_regression_venn_abers_grid_ivapd_validation_protocol_v1"
DEFAULT_REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = DEFAULT_REPORT_DIR / "venn_abers_grid_ivapd_validation_protocol.json"
DEFAULT_WORKER_STATE = Path(
    "experiments/regression/results/venn_abers_grid_expansion/checkpoints/row_results.jsonl"
)
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
METHOD_SPEC = Path("experiments/regression/method_specs/venn_abers_regression.md")
IVAPD_MODULE = Path("cpfi/regression/venn_abers.py")
WORKER_ROW_SCHEMA = "cpfi_regression_venn_abers_grid_expansion_row_v1"

NOMINAL_COVERAGE = 0.90
MIN_GRID_REFERENCE_ROWS_FOR_CLAIM = 500
MIN_GRID_REFERENCE_FULL_TEST_FRACTION = 1.0
MAX_GRID_UPPER_HIT_RATE_FOR_CLAIM = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument(
        "--worker-state",
        default=str(DEFAULT_WORKER_STATE),
        help="Optional Venn-Abers grid expansion worker JSONL state ledger.",
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


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def find_claim(claim_register: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for claim in claim_register.get("claims", []) or []:
        if isinstance(claim, dict) and claim.get("claim_id") == claim_id:
            return claim
    return {}


def requirement_status(claim: dict[str, Any], requirement_id: str) -> str | None:
    for row in claim.get("requirements", []) or []:
        if isinstance(row, dict) and row.get("requirement_id") == requirement_id:
            return str(row.get("status"))
    return None


def mean(values: list[float]) -> float | None:
    return float(sum(values) / len(values)) if values else None


def bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


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


def source_report_specs() -> tuple[dict[str, Any], ...]:
    return tuple(
        item
        for item in va_audit.SOURCE_REPORTS
        if item["report_id"] in va_audit.DIAGNOSTIC_REPORT_IDS
    )


def grid_row(result: dict[str, Any]) -> dict[str, Any]:
    grid = result.get("venn_abers_quantile_grid_reference") or {}
    grid_metrics = grid.get("grid_metrics") or {}
    bridge_metrics = grid.get("bridge_metrics") or {}
    return {
        "run_id": result.get("run_id"),
        "dataset_id": result.get("dataset_id"),
        "model_id": result.get("model_id"),
        "model_family": result.get("model_family"),
        "seed": result.get("seed"),
        "test_rows_scored": safe_int(grid.get("test_rows_scored")),
        "test_rows_available": safe_int(grid.get("test_rows_available")),
        "grid_reference_coverage": numeric(grid_metrics.get("coverage")),
        "bridge_subset_coverage": numeric(bridge_metrics.get("coverage")),
        "grid_hit_upper_rate": numeric(grid.get("grid_hit_upper_rate")),
        "grid_radius_ratio_vs_bridge": numeric(grid.get("grid_radius_ratio_vs_bridge")),
        "score_grid_size": safe_int(grid.get("score_grid_size")),
    }


def worker_state_evidence(root: Path, state_path: Path) -> dict[str, Any]:
    rows = read_jsonl(state_path)
    status_counts = Counter()
    completed_by_report: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failed_by_report = Counter()
    unique_completed: dict[str, dict[str, Any]] = {}
    duplicate_completed_key_count = 0
    completed_task_keys: set[tuple[str, str, int]] = set()
    failed_task_keys: set[tuple[str, str, int]] = set()
    failed_without_task_key_count = 0

    for row in rows:
        if row.get("schema") != WORKER_ROW_SCHEMA:
            continue
        status = str(row.get("status"))
        status_counts[status] += 1
        report_id = str(row.get("report_id"))
        if status == "completed":
            key = str(
                row.get("row_key")
                or f"{report_id}:{row.get('run_id')}:{row.get('test_index')}"
            )
            if key in unique_completed:
                duplicate_completed_key_count += 1
                continue
            unique_completed[key] = row
            task_key = worker_task_key(row)
            if task_key is not None:
                completed_task_keys.add(task_key)
        elif status == "failed":
            failed_by_report[report_id] += 1
            task_key = worker_task_key(row)
            if task_key is None:
                failed_without_task_key_count += 1
            else:
                failed_task_keys.add(task_key)

    for row in unique_completed.values():
        completed_by_report[str(row.get("report_id"))].append(row)

    superseded_failed_task_keys = failed_task_keys & completed_task_keys
    unresolved_failed_task_keys = failed_task_keys - completed_task_keys
    completed_rows = list(unique_completed.values())
    grid_hit_upper_count = sum(
        1 for row in completed_rows if bool_value(row.get("grid_hit_upper")) is True
    )
    grid_covered_count = sum(
        1 for row in completed_rows if bool_value(row.get("grid_covered")) is True
    )
    known_coverage_count = sum(
        1 for row in completed_rows if bool_value(row.get("grid_covered")) is not None
    )
    return {
        "path": rel(state_path, root),
        "exists": state_path.exists(),
        "record_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "completed_row_count": len(completed_rows),
        "failed_row_count": sum(failed_by_report.values()),
        "failed_task_key_count": len(failed_task_keys),
        "failed_without_task_key_count": failed_without_task_key_count,
        "superseded_failed_task_key_count": len(superseded_failed_task_keys),
        "unresolved_failed_task_key_count": len(unresolved_failed_task_keys),
        "failed_worker_rows_all_superseded": (
            failed_without_task_key_count == 0 and not unresolved_failed_task_keys
        ),
        "unresolved_failed_task_key_samples": [
            serialize_task_key(key) for key in sorted(unresolved_failed_task_keys)[:25]
        ],
        "duplicate_completed_key_count": duplicate_completed_key_count,
        "grid_hit_upper_count": grid_hit_upper_count,
        "grid_covered_count": grid_covered_count,
        "known_coverage_count": known_coverage_count,
        "grid_coverage": (grid_covered_count / known_coverage_count)
        if known_coverage_count
        else None,
        "grid_hit_upper_rate": (grid_hit_upper_count / len(completed_rows))
        if completed_rows
        else None,
        "completed_by_report": completed_by_report,
        "failed_by_report": failed_by_report,
    }


def worker_panel_evidence(report_id: str, worker_state: dict[str, Any]) -> dict[str, Any]:
    rows = list(worker_state.get("completed_by_report", {}).get(report_id, []))
    failed_count = int(worker_state.get("failed_by_report", {}).get(report_id, 0))
    covered_count = sum(1 for row in rows if bool_value(row.get("grid_covered")) is True)
    known_coverage_count = sum(
        1 for row in rows if bool_value(row.get("grid_covered")) is not None
    )
    hit_upper_count = sum(1 for row in rows if bool_value(row.get("grid_hit_upper")) is True)
    return {
        "completed_row_count": len(rows),
        "failed_row_count": failed_count,
        "grid_covered_count": covered_count,
        "known_coverage_count": known_coverage_count,
        "grid_coverage": (covered_count / known_coverage_count)
        if known_coverage_count
        else None,
        "grid_hit_upper_count": hit_upper_count,
        "grid_hit_upper_rate": (hit_upper_count / len(rows)) if rows else None,
        "dataset_counts": dict(Counter(str(row.get("dataset_id")) for row in rows)),
        "run_counts": dict(Counter(str(row.get("run_id")) for row in rows)),
    }


def ivapd_row(result: dict[str, Any]) -> dict[str, Any]:
    ivapd = result.get("ivapd_threshold_grid") or {}
    extractions = ivapd.get("interval_extraction_summary") or {}
    conservative = extractions.get("conservative_band") or {}
    midpoint = extractions.get("midpoint_cdf") or {}
    return {
        "run_id": result.get("run_id"),
        "dataset_id": result.get("dataset_id"),
        "model_id": result.get("model_id"),
        "model_family": result.get("model_family"),
        "seed": result.get("seed"),
        "test_rows_scored": safe_int(ivapd.get("test_rows_scored")),
        "test_rows_available": safe_int(ivapd.get("test_rows_available")),
        "threshold_grid_size": safe_int(ivapd.get("threshold_grid_size")),
        "mean_midpoint_crps": numeric(ivapd.get("mean_midpoint_crps")),
        "mean_point_step_crps": numeric(ivapd.get("mean_point_step_crps")),
        "mean_crps_delta_vs_point_step": numeric(ivapd.get("mean_crps_delta_vs_point_step")),
        "midpoint_interval_coverage": numeric(ivapd.get("midpoint_interval_coverage")),
        "conservative_band_coverage": numeric(conservative.get("coverage")),
        "midpoint_cdf_coverage": numeric(midpoint.get("coverage")),
    }


def panel_evidence(
    report_id: str,
    role: str,
    path: Path,
    payload: dict[str, Any],
    worker_state: dict[str, Any],
) -> dict[str, Any]:
    summary = payload.get("summary") or {}
    results = [row for row in payload.get("results") or [] if isinstance(row, dict)]
    grid_rows = [grid_row(row) for row in results]
    grid_rows = [row for row in grid_rows if row["test_rows_scored"] > 0]
    ivapd_rows = [ivapd_row(row) for row in results]
    ivapd_rows = [row for row in ivapd_rows if row["test_rows_scored"] > 0]

    grid_scored = sum(row["test_rows_scored"] for row in grid_rows)
    grid_available = sum(row["test_rows_available"] for row in grid_rows)
    ivapd_scored = sum(row["test_rows_scored"] for row in ivapd_rows)
    ivapd_available = sum(row["test_rows_available"] for row in ivapd_rows)
    grid_coverages = [
        float(row["grid_reference_coverage"])
        for row in grid_rows
        if row.get("grid_reference_coverage") is not None
    ]
    grid_hit_rates = [
        float(row["grid_hit_upper_rate"])
        for row in grid_rows
        if row.get("grid_hit_upper_rate") is not None
    ]
    source_grid_covered_estimate = sum(
        float(row["grid_reference_coverage"]) * row["test_rows_scored"]
        for row in grid_rows
        if row.get("grid_reference_coverage") is not None
    )
    source_grid_hit_upper_estimate = sum(
        float(row["grid_hit_upper_rate"]) * row["test_rows_scored"]
        for row in grid_rows
        if row.get("grid_hit_upper_rate") is not None
    )
    worker_panel = worker_panel_evidence(report_id, worker_state)
    combined_grid_scored = grid_scored + int(worker_panel["completed_row_count"])
    combined_grid_covered_estimate = (
        source_grid_covered_estimate + int(worker_panel["grid_covered_count"])
    )
    combined_grid_hit_upper_estimate = (
        source_grid_hit_upper_estimate + int(worker_panel["grid_hit_upper_count"])
    )
    conservative_coverages = [
        float(row["conservative_band_coverage"])
        for row in ivapd_rows
        if row.get("conservative_band_coverage") is not None
    ]

    return {
        "report_id": report_id,
        "role": role,
        "path": path.as_posix(),
        "run_count": safe_int(summary.get("run_count")) or len(results),
        "source_grid_reference_rows_scored": grid_scored
        or safe_int(summary.get("total_va_grid_reference_rows_scored")),
        "worker_grid_reference_rows_scored": int(worker_panel["completed_row_count"]),
        "worker_grid_reference_rows_failed": int(worker_panel["failed_row_count"]),
        "grid_reference_rows_scored": combined_grid_scored
        or safe_int(summary.get("total_va_grid_reference_rows_scored")),
        "grid_reference_rows_available": grid_available,
        "grid_reference_scored_fraction": (combined_grid_scored / grid_available)
        if grid_available
        else None,
        "source_mean_grid_reference_subset_coverage": numeric(
            summary.get("mean_va_grid_reference_subset_coverage")
        )
        or mean(grid_coverages),
        "worker_grid_reference_coverage": worker_panel["grid_coverage"],
        "mean_grid_reference_subset_coverage": (
            combined_grid_covered_estimate / combined_grid_scored
        )
        if combined_grid_scored
        else None,
        "min_run_grid_reference_coverage": min(grid_coverages) if grid_coverages else None,
        "source_mean_grid_hit_upper_rate": numeric(summary.get("mean_va_grid_hit_upper_rate"))
        or mean(grid_hit_rates),
        "worker_grid_hit_upper_count": int(worker_panel["grid_hit_upper_count"]),
        "worker_grid_hit_upper_rate": worker_panel["grid_hit_upper_rate"],
        "mean_grid_hit_upper_rate": (
            combined_grid_hit_upper_estimate / combined_grid_scored
        )
        if combined_grid_scored
        else None,
        "max_run_grid_hit_upper_rate": max(grid_hit_rates) if grid_hit_rates else None,
        "mean_grid_radius_ratio_vs_bridge": numeric(
            summary.get("mean_va_grid_radius_ratio_vs_bridge")
        ),
        "ivapd_rows_scored": ivapd_scored or safe_int(summary.get("total_ivapd_rows_scored")),
        "ivapd_rows_available": ivapd_available,
        "ivapd_scored_fraction": (ivapd_scored / ivapd_available)
        if ivapd_available
        else None,
        "mean_ivapd_crps_delta_vs_point_step": numeric(
            summary.get("mean_ivapd_crps_delta_vs_point_step")
        ),
        "mean_ivapd_midpoint_crps": numeric(summary.get("mean_ivapd_midpoint_crps")),
        "mean_point_step_crps": numeric(summary.get("mean_point_step_crps")),
        "ivapd_conservative_band_coverage": mean(conservative_coverages),
        "worker_grid_reference": worker_panel,
        "grid_run_samples": grid_rows[:8],
        "ivapd_run_samples": ivapd_rows[:8],
    }


def check(
    check_id: str,
    passed: bool,
    *,
    severity: str,
    description: str,
    evidence_nodes: list[str],
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "description": description,
        "evidence_node_ids": evidence_nodes,
        "details": details or {},
    }


def build_payload(root: Path, worker_state_path: str | Path = DEFAULT_WORKER_STATE) -> dict[str, Any]:
    source_payloads: dict[str, dict[str, Any]] = {}
    source_rows = []
    for item in source_report_specs():
        path = resolve(root, item["json_path"])
        exists = path.exists()
        source_rows.append(
            {
                "report_id": item["report_id"],
                "role": item["role"],
                "path": rel(path, root),
                "exists": exists,
                "size_bytes": path.stat().st_size if exists else 0,
            }
        )
        source_payloads[item["report_id"]] = read_json(path)

    worker_state = worker_state_evidence(root, resolve(root, worker_state_path))
    panels = [
        panel_evidence(
            item["report_id"],
            item["role"],
            item["json_path"],
            source_payloads[item["report_id"]],
            worker_state,
        )
        for item in source_report_specs()
    ]
    claim_register = read_json(resolve(root, CLAIM_REGISTER))
    final_claim = find_claim(claim_register, "final_selection_and_fairness_claims_blocked")
    final_va_status = requirement_status(final_claim, "venn_abers_regression_validation_gate")
    method_spec_path = resolve(root, METHOD_SPEC)
    ivapd_module_path = resolve(root, IVAPD_MODULE)
    method_spec = method_spec_path.read_text(encoding="utf-8") if method_spec_path.exists() else ""
    ivapd_module = ivapd_module_path.read_text(encoding="utf-8") if ivapd_module_path.exists() else ""
    boundary_text = f"{method_spec}\n{ivapd_module}".lower()

    total_grid_rows = sum(safe_int(row["grid_reference_rows_scored"]) for row in panels)
    source_grid_rows = sum(safe_int(row["source_grid_reference_rows_scored"]) for row in panels)
    worker_grid_rows = sum(safe_int(row["worker_grid_reference_rows_scored"]) for row in panels)
    worker_failed_rows = sum(safe_int(row["worker_grid_reference_rows_failed"]) for row in panels)
    worker_grid_hit_upper_count = sum(
        safe_int(row["worker_grid_hit_upper_count"]) for row in panels
    )
    total_grid_available = sum(safe_int(row["grid_reference_rows_available"]) for row in panels)
    total_ivapd_rows = sum(safe_int(row["ivapd_rows_scored"]) for row in panels)
    total_ivapd_available = sum(safe_int(row["ivapd_rows_available"]) for row in panels)
    panel_coverages = [
        float(row["mean_grid_reference_subset_coverage"])
        for row in panels
        if row.get("mean_grid_reference_subset_coverage") is not None
    ]
    panel_upper_hits = [
        float(row["mean_grid_hit_upper_rate"])
        for row in panels
        if row.get("mean_grid_hit_upper_rate") is not None
    ]
    scored_fraction = total_grid_rows / total_grid_available if total_grid_available else 0.0
    ivapd_scored_fraction = total_ivapd_rows / total_ivapd_available if total_ivapd_available else 0.0

    blockers: list[dict[str, Any]] = []
    if total_grid_rows < MIN_GRID_REFERENCE_ROWS_FOR_CLAIM:
        blockers.append(
            {
                "blocker_id": "grid_reference_rows_below_claim_floor",
                "observed": total_grid_rows,
                "required": MIN_GRID_REFERENCE_ROWS_FOR_CLAIM,
            }
        )
    if scored_fraction < MIN_GRID_REFERENCE_FULL_TEST_FRACTION:
        blockers.append(
            {
                "blocker_id": "grid_reference_not_full_test_scored",
                "observed": scored_fraction,
                "required": MIN_GRID_REFERENCE_FULL_TEST_FRACTION,
            }
        )
    if panel_coverages and min(panel_coverages) < NOMINAL_COVERAGE:
        blockers.append(
            {
                "blocker_id": "grid_reference_panel_coverage_below_nominal",
                "observed": min(panel_coverages),
                "required": NOMINAL_COVERAGE,
            }
        )
    if panel_upper_hits and max(panel_upper_hits) > MAX_GRID_UPPER_HIT_RATE_FOR_CLAIM:
        blockers.append(
            {
                "blocker_id": "grid_reference_candidate_grid_hits_upper_boundary",
                "observed": max(panel_upper_hits),
                "required": MAX_GRID_UPPER_HIT_RATE_FOR_CLAIM,
            }
        )
    if (
        worker_state["unresolved_failed_task_key_count"] > 0
        or worker_state["failed_without_task_key_count"] > 0
    ):
        blockers.append(
            {
                "blocker_id": "grid_reference_worker_failed_rows_unresolved",
                "observed": {
                    "unresolved_failed_task_key_count": worker_state[
                        "unresolved_failed_task_key_count"
                    ],
                    "failed_without_task_key_count": worker_state[
                        "failed_without_task_key_count"
                    ],
                },
                "required": (
                    "all retained failed worker rows must be superseded by a "
                    "completed row task before exact-grid validation claims"
                ),
            }
        )
    blockers.append(
        {
            "blocker_id": "ivapd_threshold_grid_is_predictive_distribution_not_interval_cp",
            "observed": "prototype_role=threshold_grid_predictive_distribution_not_interval_cp",
            "required": "dedicated interval-CP validity protocol before IVAPD interval claims",
        }
    )

    can_support_grid_validation = len([row for row in blockers if row["blocker_id"].startswith("grid_")]) == 0
    can_support_ivapd_interval_cp = False
    can_support_validated_venn_abers = (
        can_support_grid_validation
        and can_support_ivapd_interval_cp
        and final_va_status != "blocked"
    )

    checks = [
        check(
            "source_reports_present",
            all(row["exists"] for row in source_rows)
            and method_spec_path.exists()
            and ivapd_module_path.exists(),
            severity="critical",
            description="Real diagnostic reports, Venn-Abers method spec, and IVAPD prototype module are present.",
            evidence_nodes=[row["report_id"] for row in source_rows]
            + ["method_spec:venn_abers_regression", "module:cpfi.regression.venn_abers"],
            details={"source_rows": source_rows},
        ),
        check(
            "grid_reference_evidence_summarized",
            len(panels) == len(source_rows)
            and total_grid_rows > 0
            and all(row["grid_reference_rows_scored"] > 0 for row in panels),
            severity="high",
            description="Every real diagnostic panel contributes score-grid reference rows.",
            evidence_nodes=[
                "report:venn_abers_real_data_diagnostic",
                "report:venn_abers_fairness_panel_diagnostic",
                "report:venn_abers_biomarker_clinical_panel_diagnostic",
                "method:venn_abers_quantile_grid",
            ],
            details={
                "total_grid_reference_rows_scored": total_grid_rows,
                "total_grid_reference_rows_available": total_grid_available,
                "grid_reference_scored_fraction": scored_fraction,
            },
        ),
        check(
            "worker_grid_expansion_evidence_summarized",
            (not worker_state["exists"])
            or (
                worker_state["completed_row_count"] >= 0
                and worker_state["duplicate_completed_key_count"] == 0
                and worker_state["failed_without_task_key_count"] == 0
            ),
            severity="medium",
            description=(
                "Optional Venn-Abers grid expansion worker rows are parsed as "
                "operational evidence; retained failures are keyed and never "
                "promoted to validation claims."
            ),
            evidence_nodes=[
                "report:venn_abers_grid_expansion_batch",
                "report:venn_abers_grid_expansion_plan",
            ],
            details={
                "worker_state_path": worker_state["path"],
                "worker_state_exists": worker_state["exists"],
                "worker_completed_row_count": worker_state["completed_row_count"],
                "worker_failed_row_count": worker_state["failed_row_count"],
                "worker_failed_task_key_count": worker_state["failed_task_key_count"],
                "worker_superseded_failed_task_key_count": worker_state[
                    "superseded_failed_task_key_count"
                ],
                "worker_unresolved_failed_task_key_count": worker_state[
                    "unresolved_failed_task_key_count"
                ],
                "worker_grid_hit_upper_count": worker_state["grid_hit_upper_count"],
                "duplicate_completed_key_count": worker_state[
                    "duplicate_completed_key_count"
                ],
            },
        ),
        check(
            "grid_validation_blockers_recorded",
            can_support_grid_validation is False
            and any(row["blocker_id"].startswith("grid_") for row in blockers),
            severity="critical",
            description="The finite score-grid reference remains blocked from validation claims until coverage, size, and boundary criteria pass.",
            evidence_nodes=[
                "method:venn_abers_quantile_grid",
                "report:venn_abers_validation_readiness_audit",
            ],
            details={"blockers": [row for row in blockers if row["blocker_id"].startswith("grid_")]},
        ),
        check(
            "ivapd_boundary_preserved",
            "threshold_grid_predictive_distribution_not_interval_cp" in boundary_text
            and "not a runner" in boundary_text
            and can_support_ivapd_interval_cp is False,
            severity="critical",
            description="IVAPD remains documented as a predictive-distribution diagnostic, not a validated interval-CP runner claim.",
            evidence_nodes=["method:ivapd_regression", "module:cpfi.regression.venn_abers"],
            details={
                "total_ivapd_rows_scored": total_ivapd_rows,
                "total_ivapd_rows_available": total_ivapd_available,
                "ivapd_scored_fraction": ivapd_scored_fraction,
            },
        ),
        check(
            "final_validation_gate_stays_blocked",
            final_claim.get("status") == "blocked" and final_va_status == "blocked",
            severity="critical",
            description="The manuscript claim register keeps validated Venn-Abers regression blocked.",
            evidence_nodes=[
                "manuscript_claim:final_selection_and_fairness_claims_blocked",
                "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            ],
            details={
                "final_claim_status": final_claim.get("status"),
                "venn_abers_validation_requirement_status": final_va_status,
            },
        ),
    ]
    status_counts = Counter(row["status"] for row in checks)
    failed_check_count = int(status_counts.get("fail", 0))
    overall_status = (
        "venn_abers_grid_ivapd_validation_protocol_defined_no_claim"
        if failed_check_count == 0
        else "venn_abers_grid_ivapd_validation_protocol_audit_fail"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "nominal_coverage": NOMINAL_COVERAGE,
        "claim_thresholds": {
            "min_grid_reference_rows_for_claim": MIN_GRID_REFERENCE_ROWS_FOR_CLAIM,
            "min_grid_reference_full_test_fraction": MIN_GRID_REFERENCE_FULL_TEST_FRACTION,
            "max_grid_upper_hit_rate_for_claim": MAX_GRID_UPPER_HIT_RATE_FOR_CLAIM,
        },
        "summary": {
            "overall_status": overall_status,
            "failed_check_count": failed_check_count,
            "check_status_counts": dict(sorted(status_counts.items())),
            "can_support_validated_venn_abers_regression": can_support_validated_venn_abers,
            "can_support_exact_grid_venn_abers_validation": can_support_grid_validation,
            "can_support_ivapd_interval_cp_validation": can_support_ivapd_interval_cp,
            "grid_reference_validation_status": "blocked" if not can_support_grid_validation else "candidate_ready",
            "ivapd_interval_cp_status": "blocked_predictive_distribution_only",
            "validation_blocker_count": len(blockers),
            "validation_blocker_ids": [row["blocker_id"] for row in blockers],
            "source_report_count": len(source_rows),
            "diagnostic_panel_count": len(panels),
            "total_grid_reference_rows_scored": total_grid_rows,
            "source_grid_reference_rows_scored": source_grid_rows,
            "worker_grid_reference_rows_scored": worker_grid_rows,
            "worker_grid_reference_rows_failed": worker_failed_rows,
            "worker_failed_task_key_count": worker_state["failed_task_key_count"],
            "worker_superseded_failed_task_key_count": worker_state[
                "superseded_failed_task_key_count"
            ],
            "worker_unresolved_failed_task_key_count": worker_state[
                "unresolved_failed_task_key_count"
            ],
            "failed_worker_rows_all_superseded": worker_state[
                "failed_worker_rows_all_superseded"
            ],
            "worker_grid_hit_upper_count": worker_grid_hit_upper_count,
            "worker_grid_hit_upper_rate": (worker_grid_hit_upper_count / worker_grid_rows)
            if worker_grid_rows
            else None,
            "total_grid_reference_rows_available": total_grid_available,
            "grid_reference_scored_fraction": scored_fraction,
            "min_panel_grid_reference_coverage": min(panel_coverages) if panel_coverages else None,
            "max_panel_grid_reference_coverage": max(panel_coverages) if panel_coverages else None,
            "max_panel_grid_hit_upper_rate": max(panel_upper_hits) if panel_upper_hits else None,
            "total_ivapd_rows_scored": total_ivapd_rows,
            "total_ivapd_rows_available": total_ivapd_available,
            "ivapd_scored_fraction": ivapd_scored_fraction,
            "final_validation_requirement_status": final_va_status,
            "claim_boundary": (
                "Score-grid rows are finite-grid diagnostic reference evidence and IVAPD rows are "
                "predictive-distribution diagnostics; neither currently supports validated "
                "Venn-Abers regression interval claims."
            ),
        },
        "worker_state": {
            "path": worker_state["path"],
            "exists": worker_state["exists"],
            "record_count": worker_state["record_count"],
            "status_counts": worker_state["status_counts"],
            "completed_row_count": worker_state["completed_row_count"],
            "failed_row_count": worker_state["failed_row_count"],
            "failed_task_key_count": worker_state["failed_task_key_count"],
            "failed_without_task_key_count": worker_state["failed_without_task_key_count"],
            "superseded_failed_task_key_count": worker_state[
                "superseded_failed_task_key_count"
            ],
            "unresolved_failed_task_key_count": worker_state[
                "unresolved_failed_task_key_count"
            ],
            "failed_worker_rows_all_superseded": worker_state[
                "failed_worker_rows_all_superseded"
            ],
            "unresolved_failed_task_key_samples": worker_state[
                "unresolved_failed_task_key_samples"
            ],
            "duplicate_completed_key_count": worker_state["duplicate_completed_key_count"],
            "grid_hit_upper_count": worker_state["grid_hit_upper_count"],
            "grid_coverage": worker_state["grid_coverage"],
            "grid_hit_upper_rate": worker_state["grid_hit_upper_rate"],
        },
        "source_reports": source_rows,
        "panel_evidence": panels,
        "validation_blockers": blockers,
        "checks": checks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Venn-Abers Grid and IVAPD Validation Protocol Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Can support validated Venn-Abers regression: `{summary['can_support_validated_venn_abers_regression']}`",
        f"- Can support exact-grid validation: `{summary['can_support_exact_grid_venn_abers_validation']}`",
        f"- Can support IVAPD interval-CP validation: `{summary['can_support_ivapd_interval_cp_validation']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Grid reference rows scored: {summary['total_grid_reference_rows_scored']} / {summary['total_grid_reference_rows_available']}",
        f"- Source grid rows scored: {summary['source_grid_reference_rows_scored']}",
        f"- Worker grid rows scored: {summary['worker_grid_reference_rows_scored']}",
        f"- Worker grid upper-hit count: {summary['worker_grid_hit_upper_count']}",
        f"- Grid reference scored fraction: {summary['grid_reference_scored_fraction']}",
        f"- Panel grid coverage range: {summary['min_panel_grid_reference_coverage']} to {summary['max_panel_grid_reference_coverage']}",
        f"- Max panel grid upper-bound hit rate: {summary['max_panel_grid_hit_upper_rate']}",
        f"- IVAPD rows scored: {summary['total_ivapd_rows_scored']} / {summary['total_ivapd_rows_available']}",
        f"- Final validation requirement status: `{summary['final_validation_requirement_status']}`",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
        "## Panel Evidence",
        "",
        "| Report | Grid rows | Worker rows | Grid fraction | Grid coverage | Grid upper hit | IVAPD rows | IVAPD fraction |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["panel_evidence"]:
        lines.append(
            "| "
            f"`{row['report_id']}` | "
            f"{row.get('grid_reference_rows_scored')} / {row.get('grid_reference_rows_available')} | "
            f"{row.get('worker_grid_reference_rows_scored')} | "
            f"{row.get('grid_reference_scored_fraction')} | "
            f"{row.get('mean_grid_reference_subset_coverage')} | "
            f"{row.get('mean_grid_hit_upper_rate')} | "
            f"{row.get('ivapd_rows_scored')} / {row.get('ivapd_rows_available')} | "
            f"{row.get('ivapd_scored_fraction')} |"
        )
    lines.extend(
        [
            "",
            "## Validation Blockers",
            "",
            "| Blocker | Observed | Required |",
            "| --- | --- | --- |",
        ]
    )
    for row in payload["validation_blockers"]:
        lines.append(
            "| "
            f"`{row['blocker_id']}` | "
            f"`{row.get('observed')}` | "
            f"`{row.get('required')}` |"
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
    payload = build_payload(root, worker_state_path=args.worker_state)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "out": rel(out_path, root),
                "failed_check_count": payload["summary"]["failed_check_count"],
                "validation_blocker_count": payload["summary"]["validation_blocker_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
