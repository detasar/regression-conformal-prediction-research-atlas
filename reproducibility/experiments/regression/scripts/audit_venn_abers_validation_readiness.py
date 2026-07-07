"""Audit the Venn-Abers regression validation claim boundary.

The study has several Venn-Abers-adjacent regression artifacts, but the fast
quantile bridge is currently negative diagnostic evidence rather than a
validated Venn-Abers regression interval method. This audit makes that boundary
executable so publication text cannot silently promote the diagnostic bridge or
the ordinary split fallback into a validation claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_venn_abers_validation_readiness_audit_v1"
NOMINAL_COVERAGE = 0.90
DEFAULT_REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = DEFAULT_REPORT_DIR / "venn_abers_validation_readiness_audit.json"
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
CLAIM_REGISTER_MD = Path("experiments/regression/catalogs/manuscript_claim_register.md")
METHOD_SPEC = Path("experiments/regression/method_specs/venn_abers_regression.md")

SOURCE_REPORTS = (
    {
        "report_id": "report:venn_abers_quantile_bridge_benchmark",
        "role": "synthetic_bridge_vs_grid_reference",
        "json_path": Path("experiments/regression/reports/venn_abers_quantile_bridge_benchmark/benchmark.json"),
    },
    {
        "report_id": "report:venn_abers_real_data_diagnostic",
        "role": "real_data_negative_diagnostic",
        "json_path": Path("experiments/regression/reports/venn_abers_real_data_diagnostic/diagnostic.json"),
    },
    {
        "report_id": "report:venn_abers_fairness_panel_diagnostic",
        "role": "fairness_panel_negative_diagnostic",
        "json_path": Path("experiments/regression/reports/venn_abers_fairness_panel_diagnostic/diagnostic.json"),
    },
    {
        "report_id": "report:venn_abers_biomarker_clinical_panel_diagnostic",
        "role": "biomarker_panel_negative_diagnostic",
        "json_path": Path("experiments/regression/reports/venn_abers_biomarker_clinical_panel_diagnostic/diagnostic.json"),
    },
)

DIAGNOSTIC_REPORT_IDS = {
    "report:venn_abers_real_data_diagnostic",
    "report:venn_abers_fairness_panel_diagnostic",
    "report:venn_abers_biomarker_clinical_panel_diagnostic",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
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


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


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


def report_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def interval_method(summary: dict[str, Any], method_id: str) -> dict[str, Any]:
    methods = summary.get("interval_method_summary")
    if not isinstance(methods, dict):
        return {}
    row = methods.get(method_id)
    return row if isinstance(row, dict) else {}


def panel_row(report_id: str, role: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    summary = report_summary(payload)
    va_method = interval_method(summary, "venn_abers_quantile")
    split_fallback = interval_method(summary, "venn_abers_split_fallback")
    grid_split = summary.get("split_fallback_grid_summary")
    if not isinstance(grid_split, dict):
        grid_split = {}
    return {
        "report_id": report_id,
        "role": role,
        "path": path.as_posix(),
        "dataset_count": summary.get("dataset_count"),
        "run_count": summary.get("run_count"),
        "mean_venn_abers_coverage": numeric(
            summary.get("mean_venn_abers_coverage")
        )
        or numeric(va_method.get("mean_coverage")),
        "mean_venn_abers_width": numeric(summary.get("mean_venn_abers_width")),
        "mean_va_grid_bridge_subset_coverage": numeric(
            summary.get("mean_va_grid_bridge_subset_coverage")
        ),
        "mean_va_grid_reference_subset_coverage": numeric(
            summary.get("mean_va_grid_reference_subset_coverage")
        ),
        "mean_va_grid_radius_ratio_vs_bridge": numeric(
            summary.get("mean_va_grid_radius_ratio_vs_bridge")
        ),
        "mean_va_grid_minus_bridge_radius": numeric(
            summary.get("mean_va_grid_minus_bridge_radius")
        ),
        "total_va_grid_reference_rows_scored": summary.get(
            "total_va_grid_reference_rows_scored"
        ),
        "total_ivapd_rows_scored": summary.get("total_ivapd_rows_scored"),
        "split_fallback_mean_coverage": numeric(split_fallback.get("mean_coverage")),
        "split_fallback_grid_mean_coverage": numeric(grid_split.get("mean_coverage")),
    }


def bridge_benchmark_row(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    summary = report_summary(payload)
    return {
        "report_id": "report:venn_abers_quantile_bridge_benchmark",
        "path": path.as_posix(),
        "panel_count": summary.get("panel_count"),
        "mean_bridge_coverage": numeric(summary.get("mean_bridge_coverage")),
        "mean_grid_coverage": numeric(summary.get("mean_grid_coverage")),
        "mean_bridge_width": numeric(summary.get("mean_bridge_width")),
        "mean_grid_width": numeric(summary.get("mean_grid_width")),
        "mean_abs_radius_delta": numeric(summary.get("mean_abs_radius_delta")),
        "max_abs_radius_delta": numeric(summary.get("max_abs_radius_delta")),
    }


def method_coverage(row: dict[str, Any], method_id: str) -> float | None:
    for item in row.get("interval_method_comparison") or []:
        if item.get("method") == method_id and item.get("coverage") is not None:
            return numeric(item.get("coverage"))
    metrics = ((row.get("interval_methods") or {}).get(method_id) or {}).get("metrics") or {}
    if metrics.get("coverage") is not None:
        return numeric(metrics.get("coverage"))
    if method_id == "venn_abers_quantile":
        fallback = row.get("venn_abers_quantile_interval") or {}
        if fallback.get("coverage") is not None:
            return numeric(fallback.get("coverage"))
    return None


def diagnostic_run_rows(
    report_id: str,
    role: str,
    path: Path,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("results") or []:
        if not isinstance(row, dict):
            continue
        coverage = method_coverage(row, "venn_abers_quantile")
        if coverage is None:
            continue
        rows.append(
            {
                "report_id": report_id,
                "role": role,
                "path": path.as_posix(),
                "run_id": row.get("run_id"),
                "dataset_id": row.get("dataset_id"),
                "model_id": row.get("model_id"),
                "model_family": row.get("model_family"),
                "seed": row.get("seed"),
                "coverage": coverage,
                "under_nominal": coverage < NOMINAL_COVERAGE,
            }
        )
    return rows


def run_undercoverage_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    coverages = [float(row["coverage"]) for row in rows]
    undercoverage_rows = [row for row in rows if row.get("under_nominal")]
    counts_by_panel = Counter(str(row.get("report_id")) for row in rows)
    under_counts_by_panel = Counter(str(row.get("report_id")) for row in undercoverage_rows)
    return {
        "nominal_coverage": NOMINAL_COVERAGE,
        "run_count": len(rows),
        "undercoverage_run_count": len(undercoverage_rows),
        "min_coverage": min(coverages) if coverages else None,
        "max_coverage": max(coverages) if coverages else None,
        "run_count_by_panel": dict(sorted(counts_by_panel.items())),
        "undercoverage_run_count_by_panel": dict(sorted(under_counts_by_panel.items())),
        "undercoverage_run_samples": undercoverage_rows[:12],
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


def build_payload(root: Path) -> dict[str, Any]:
    source_payloads: dict[str, dict[str, Any]] = {}
    source_rows = []
    for item in SOURCE_REPORTS:
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
        source_payloads[item["report_id"]] = read_json(path) if exists else {}

    claim_register_path = resolve(root, CLAIM_REGISTER)
    claim_register_md_path = resolve(root, CLAIM_REGISTER_MD)
    method_spec_path = resolve(root, METHOD_SPEC)
    claim_register = read_json(claim_register_path) if claim_register_path.exists() else {}
    final_claim = find_claim(claim_register, "final_selection_and_fairness_claims_blocked")
    va_negative_claim = find_claim(claim_register, "venn_abers_fast_bridge_negative_result")
    claim_md = claim_register_md_path.read_text(encoding="utf-8") if claim_register_md_path.exists() else ""
    method_spec = method_spec_path.read_text(encoding="utf-8") if method_spec_path.exists() else ""

    panels = [
        panel_row(
            item["report_id"],
            item["role"],
            item["json_path"],
            source_payloads[item["report_id"]],
        )
        for item in SOURCE_REPORTS
        if item["report_id"] in DIAGNOSTIC_REPORT_IDS
    ]
    diagnostic_runs = [
        row
        for item in SOURCE_REPORTS
        if item["report_id"] in DIAGNOSTIC_REPORT_IDS
        for row in diagnostic_run_rows(
            item["report_id"],
            item["role"],
            item["json_path"],
            source_payloads[item["report_id"]],
        )
    ]
    run_undercoverage = run_undercoverage_summary(diagnostic_runs)
    benchmark = bridge_benchmark_row(
        SOURCE_REPORTS[0]["json_path"],
        source_payloads["report:venn_abers_quantile_bridge_benchmark"],
    )

    undercoverage_panels = [
        row
        for row in panels
        if row.get("mean_venn_abers_coverage") is not None
        and float(row["mean_venn_abers_coverage"]) < NOMINAL_COVERAGE
    ]
    grid_stronger_panels = [
        row
        for row in panels
        if row.get("mean_va_grid_reference_subset_coverage") is not None
        and row.get("mean_va_grid_bridge_subset_coverage") is not None
        and float(row["mean_va_grid_reference_subset_coverage"])
        > float(row["mean_va_grid_bridge_subset_coverage"])
        and row.get("mean_va_grid_radius_ratio_vs_bridge") is not None
        and float(row["mean_va_grid_radius_ratio_vs_bridge"]) > 1.0
    ]
    fallback_coverage_panels = [
        row
        for row in panels
        if row.get("split_fallback_mean_coverage") is not None
        and float(row["split_fallback_mean_coverage"]) >= NOMINAL_COVERAGE - 0.05
    ]
    final_va_status = requirement_status(
        final_claim,
        "venn_abers_regression_validation_gate",
    )
    negative_requirement_status = requirement_status(
        va_negative_claim,
        "negative_evidence_preserved",
    )
    nonclaim_text = " ".join(str(item) for item in va_negative_claim.get("not_claiming", []) or [])
    lower_boundary_text = f"{claim_md} {method_spec} {nonclaim_text}".lower()

    checks = [
        check(
            "source_reports_present",
            all(row["exists"] for row in source_rows)
            and claim_register_path.exists()
            and claim_register_md_path.exists()
            and method_spec_path.exists(),
            severity="critical",
            description="All Venn-Abers diagnostic reports, claim register files, and method spec are present.",
            evidence_nodes=[row["report_id"] for row in source_rows]
            + ["catalog:manuscript_claim_register", "method_spec:venn_abers_regression"],
            details={"source_rows": source_rows},
        ),
        check(
            "fast_bridge_negative_evidence_preserved",
            len(undercoverage_panels) == len(panels)
            and negative_requirement_status == "present",
            severity="critical",
            description="Every real diagnostic panel records fast-bridge undercoverage below nominal coverage, and the negative-evidence claim remains present.",
            evidence_nodes=[
                "report:venn_abers_real_data_diagnostic",
                "report:venn_abers_fairness_panel_diagnostic",
                "report:venn_abers_biomarker_clinical_panel_diagnostic",
                "manuscript_claim:venn_abers_fast_bridge_negative_result",
            ],
            details={
                "nominal_coverage": NOMINAL_COVERAGE,
                "undercoverage_panel_count": len(undercoverage_panels),
                "panel_count": len(panels),
                "negative_requirement_status": negative_requirement_status,
            },
        ),
        check(
            "fast_bridge_run_undercoverage_recorded",
            run_undercoverage["run_count"] > 0
            and run_undercoverage["undercoverage_run_count"] > 0
            and negative_requirement_status == "present",
            severity="high",
            description="Run-level fast-bridge coverage is recorded and at least one real diagnostic run undercovers nominal coverage.",
            evidence_nodes=[
                "report:venn_abers_real_data_diagnostic",
                "report:venn_abers_fairness_panel_diagnostic",
                "report:venn_abers_biomarker_clinical_panel_diagnostic",
                "manuscript_claim:venn_abers_fast_bridge_negative_result",
            ],
            details=run_undercoverage,
        ),
        check(
            "grid_reference_exposes_bridge_shrinkage",
            len(grid_stronger_panels) == len(panels),
            severity="high",
            description="Grid reference intervals cover more than the fast bridge and are wider in every real diagnostic panel.",
            evidence_nodes=[
                "report:venn_abers_real_data_diagnostic",
                "report:venn_abers_fairness_panel_diagnostic",
                "report:venn_abers_biomarker_clinical_panel_diagnostic",
                "method:venn_abers_quantile_grid",
            ],
            details={
                "grid_stronger_panel_count": len(grid_stronger_panels),
                "panel_count": len(panels),
            },
        ),
        check(
            "split_fallback_boundary_preserved",
            "ordinary split" in lower_boundary_text
            and "not a venn-abers regression method" in lower_boundary_text
            and len(fallback_coverage_panels) >= 2,
            severity="high",
            description="The split fallback remains documented as ordinary split conformal evidence, not Venn-Abers validation.",
            evidence_nodes=[
                "method:venn_abers_split_fallback",
                "catalog:manuscript_claim_register",
                "method_spec:venn_abers_regression",
            ],
            details={
                "fallback_panels_near_nominal_or_better": len(fallback_coverage_panels),
                "panel_count": len(panels),
            },
        ),
        check(
            "final_validation_gate_stays_blocked",
            final_claim.get("status") == "blocked" and final_va_status == "blocked",
            severity="critical",
            description="The final-selection claim register keeps Venn-Abers regression validation blocked.",
            evidence_nodes=[
                "manuscript_claim:final_selection_and_fairness_claims_blocked",
                "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            ],
            details={
                "final_claim_status": final_claim.get("status"),
                "venn_abers_validation_requirement_status": final_va_status,
            },
        ),
        check(
            "bridge_benchmark_reference_recorded",
            benchmark.get("mean_grid_width") is not None
            and benchmark.get("mean_bridge_width") is not None
            and float(benchmark["mean_grid_width"]) > float(benchmark["mean_bridge_width"]),
            severity="medium",
            description="The synthetic bridge-vs-grid benchmark remains available as controlled reference evidence.",
            evidence_nodes=[
                "report:venn_abers_quantile_bridge_benchmark",
                "method:venn_abers_quantile",
                "method:venn_abers_quantile_grid",
            ],
            details=benchmark,
        ),
    ]
    status_counts = Counter(row["status"] for row in checks)
    failed_check_count = int(status_counts.get("fail", 0))
    overall_status = (
        "venn_abers_validation_blocked_with_negative_evidence"
        if failed_check_count == 0
        else "venn_abers_validation_boundary_audit_fail"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "nominal_coverage": NOMINAL_COVERAGE,
        "summary": {
            "overall_status": overall_status,
            "can_support_venn_abers_regression_validation": False,
            "failed_check_count": failed_check_count,
            "check_status_counts": dict(sorted(status_counts.items())),
            "source_report_count": len(source_rows),
            "diagnostic_panel_count": len(panels),
            "undercoverage_panel_count": len(undercoverage_panels),
            "diagnostic_run_count": run_undercoverage["run_count"],
            "undercoverage_run_count": run_undercoverage["undercoverage_run_count"],
            "min_venn_abers_run_coverage": run_undercoverage["min_coverage"],
            "max_venn_abers_run_coverage": run_undercoverage["max_coverage"],
            "grid_reference_stronger_panel_count": len(grid_stronger_panels),
            "split_fallback_near_nominal_panel_count": len(fallback_coverage_panels),
            "validation_requirement_status": final_va_status,
            "negative_evidence_requirement_status": negative_requirement_status,
            "mean_venn_abers_coverage_by_panel": {
                row["report_id"]: row.get("mean_venn_abers_coverage") for row in panels
            },
            "mean_va_grid_radius_ratio_vs_bridge_by_panel": {
                row["report_id"]: row.get("mean_va_grid_radius_ratio_vs_bridge")
                for row in panels
            },
            "claim_boundary": (
                "Fast bridge rows are diagnostic negative evidence; split fallback rows are ordinary "
                "split conformal fallback evidence; neither supports validated Venn-Abers regression."
            ),
        },
        "source_reports": source_rows,
        "validation_panels": panels,
        "diagnostic_runs": diagnostic_runs,
        "run_undercoverage": run_undercoverage,
        "bridge_benchmark": benchmark,
        "checks": checks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Venn-Abers Validation Readiness Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Can support Venn-Abers regression validation: `{summary['can_support_venn_abers_regression_validation']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Diagnostic panels below nominal {payload['nominal_coverage']}: {summary['undercoverage_panel_count']} / {summary['diagnostic_panel_count']}",
        f"- Diagnostic runs below nominal {payload['nominal_coverage']}: {summary['undercoverage_run_count']} / {summary['diagnostic_run_count']}",
        f"- Run-level VA coverage range: {summary['min_venn_abers_run_coverage']} to {summary['max_venn_abers_run_coverage']}",
        f"- Grid-reference stronger panels: {summary['grid_reference_stronger_panel_count']} / {summary['diagnostic_panel_count']}",
        f"- Validation requirement status: `{summary['validation_requirement_status']}`",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
        "## Diagnostic Panels",
        "",
        "| Report | VA coverage | Grid coverage | Bridge coverage | Grid/bridge radius | Split fallback coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["validation_panels"]:
        lines.append(
            "| "
            f"`{row['report_id']}` | "
            f"{row.get('mean_venn_abers_coverage')} | "
            f"{row.get('mean_va_grid_reference_subset_coverage')} | "
            f"{row.get('mean_va_grid_bridge_subset_coverage')} | "
            f"{row.get('mean_va_grid_radius_ratio_vs_bridge')} | "
            f"{row.get('split_fallback_mean_coverage')} |"
        )
    lines.extend(
        [
            "",
            "## Run-Level Undercoverage",
            "",
            "| Report | Run | Dataset | Coverage | Under nominal |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for row in payload["run_undercoverage"].get("undercoverage_run_samples", []):
        lines.append(
            "| "
            f"`{row.get('report_id')}` | "
            f"`{row.get('run_id')}` | "
            f"`{row.get('dataset_id')}` | "
            f"{row.get('coverage')} | "
            f"`{row.get('under_nominal')}` |"
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
    payload = build_payload(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok" if payload["summary"]["failed_check_count"] == 0 else "fail",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )
    return 1 if payload["summary"]["failed_check_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
