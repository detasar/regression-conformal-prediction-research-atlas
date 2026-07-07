"""Audit the disposition of Venn-Abers negative evidence.

This audit checks that current Venn-Abers-adjacent regression evidence remains
diagnostic/negative evidence and cannot leak into final method selection or
main-result manuscript surfaces.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_venn_abers_negative_evidence_disposition_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
VA_METHODS = {"venn_abers_quantile", "venn_abers_split_fallback"}
NEGATIVE_CLAIM_ID = "venn_abers_fast_bridge_negative_result"

SOURCES = {
    "claim_register": Path("experiments/regression/catalogs/manuscript_claim_register.json"),
    "validation_readiness": REPORT_DIR / "venn_abers_validation_readiness_audit.json",
    "grid_ivapd_protocol": REPORT_DIR / "venn_abers_grid_ivapd_validation_protocol.json",
    "grid_failure_modes": REPORT_DIR / "venn_abers_grid_failure_mode_decomposition.json",
    "claim_gate_matrix": REPORT_DIR / "venn_abers_claim_gate_matrix.json",
    "method_selection_candidate": REPORT_DIR / "method_selection_candidate_audit.json",
    "method_performance_synthesis": REPORT_DIR / "method_performance_synthesis.json",
    "bundle_eligibility_matrix": Path(
        "experiments/regression/manuscript/bundle_eligibility_matrix.json"
    ),
    "final_selection_boundary": REPORT_DIR / "final_selection_claim_boundary_audit.json",
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


def read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return value if isinstance(value, dict) else {}


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def find_claim(register: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for claim in register.get("claims") or []:
        if isinstance(claim, dict) and claim.get("claim_id") == claim_id:
            return claim
    return {}


def requirement_status(claim: dict[str, Any], requirement_id: str) -> str | None:
    for row in claim.get("requirements") or []:
        if isinstance(row, dict) and row.get("requirement_id") == requirement_id:
            return str(row.get("status"))
    return None


def method_ids_from_shortlist(payload: dict[str, Any]) -> list[str]:
    rows = payload.get("shortlist_methods")
    if isinstance(rows, list):
        return [
            str(row.get("cp_method"))
            for row in rows
            if isinstance(row, dict) and row.get("cp_method")
        ]
    criterion = payload.get("operating_criterion") or {}
    values = criterion.get("candidate_methods") or []
    return [str(value) for value in values]


def excluded_venn_methods(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("excluded_methods") or []:
        if not isinstance(row, dict):
            continue
        method = str(row.get("cp_method") or "")
        if method in VA_METHODS:
            rows.append(row)
    return rows


def contains_venn_abers(value: Any) -> bool:
    return "venn_abers" in json.dumps(value, sort_keys=True).lower()


def surface(row: dict[str, Any], surface_id: str) -> dict[str, Any]:
    value = (row.get("surface_eligibility") or {}).get(surface_id) or {}
    return value if isinstance(value, dict) else {}


def bundle_disposition_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or not contains_venn_abers(row):
            continue
        main_surface = surface(row, "main_results_table")
        negative_surface = surface(row, "negative_results_table")
        blocked_surfaces = list(row.get("blocked_surface_ids") or [])
        rows.append(
            {
                "bundle_id": row.get("bundle_id"),
                "dataset_id": row.get("dataset_id"),
                "status": row.get("status"),
                "paper_table_candidate": row.get("paper_table_candidate"),
                "evidence_role": row.get("evidence_role"),
                "blocked_surface_ids": blocked_surfaces,
                "eligible_surface_ids": list(row.get("eligible_surface_ids") or []),
                "main_results_eligible": bool(main_surface.get("eligible")),
                "main_results_status": main_surface.get("status"),
                "negative_results_eligible": bool(negative_surface.get("eligible")),
                "negative_results_status": negative_surface.get("status"),
                "promotion_blockers": row.get("promotion_blockers") or [],
                "claim_scope": row.get("claim_scope"),
                "main_results_blocked": (
                    not bool(main_surface.get("eligible"))
                    and "main_results_table" in blocked_surfaces
                ),
            }
        )
    rows.sort(key=lambda item: str(item.get("bundle_id")))
    return rows


def check_row(
    check_id: str,
    passed: bool,
    *,
    severity: str,
    description: str,
    observed: dict[str, Any],
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "description": description,
        "observed": observed,
    }


def build_payload(root: Path) -> dict[str, Any]:
    paths = {key: root / value for key, value in SOURCES.items()}
    payloads = {key: read_json_if_present(path) for key, path in paths.items()}
    summaries = {key: summary(value) for key, value in payloads.items()}
    missing_sources = [
        key for key, path in paths.items() if not path.exists() or not payloads[key]
    ]

    claim = find_claim(payloads["claim_register"], NEGATIVE_CLAIM_ID)
    claim_not_claiming_text = " ".join(str(value) for value in claim.get("not_claiming") or [])
    negative_claim_ok = (
        bool(claim)
        and claim.get("claim_type") == "negative_result"
        and claim.get("status") == "diagnostic"
        and set(claim.get("method_ids") or []) >= VA_METHODS
        and requirement_status(claim, "negative_evidence_preserved") == "present"
        and "No Venn-Abers regression interval-coverage validation is claimed"
        in claim_not_claiming_text
    )

    readiness = summaries["validation_readiness"]
    fast_bridge_negative_ok = (
        readiness.get("overall_status")
        == "venn_abers_validation_blocked_with_negative_evidence"
        and readiness.get("can_support_venn_abers_regression_validation") is False
        and readiness.get("negative_evidence_requirement_status") == "present"
        and readiness.get("validation_requirement_status") == "blocked"
        and safe_int(readiness.get("undercoverage_run_count")) > 0
        and safe_int(readiness.get("undercoverage_panel_count"))
        == safe_int(readiness.get("diagnostic_panel_count"))
    )

    protocol = summaries["grid_ivapd_protocol"]
    failure_modes = summaries["grid_failure_modes"]
    grid_ivapd_diagnostic_ok = (
        protocol.get("overall_status")
        == "venn_abers_grid_ivapd_validation_protocol_defined_no_claim"
        and protocol.get("can_support_validated_venn_abers_regression") is False
        and protocol.get("can_support_exact_grid_venn_abers_validation") is False
        and protocol.get("can_support_ivapd_interval_cp_validation") is False
        and safe_int(protocol.get("validation_blocker_count")) > 0
        and failure_modes.get("overall_status")
        == "venn_abers_grid_failure_modes_decomposed_no_claim"
        and failure_modes.get("claim_status") == "no_validated_venn_abers_regression_claim"
        and failure_modes.get("can_support_validated_venn_abers_regression") is False
    )

    claim_gate = summaries["claim_gate_matrix"]
    claim_gate_blocks_ok = (
        claim_gate.get("overall_status")
        == "venn_abers_claim_gate_matrix_blocked_with_complete_evidence"
        and claim_gate.get("can_support_validated_venn_abers_regression") is False
        and claim_gate.get("positive_claim_ready") is False
        and safe_int(claim_gate.get("positive_claim_blocked_count")) > 0
        and safe_int(claim_gate.get("failed_check_count")) == 0
    )

    final_boundary = summaries["final_selection_boundary"]
    requirement_statuses = payloads["final_selection_boundary"].get(
        "requirement_statuses"
    ) or {}
    final_boundary_blocks_ok = (
        final_boundary.get("overall_status") == "pass"
        and final_boundary.get("claim_status") == "blocked"
        and requirement_statuses.get("venn_abers_regression_validation_gate")
        == "blocked"
    )

    method_selection = payloads["method_selection_candidate"]
    method_selection_summary = summaries["method_selection_candidate"]
    shortlist_methods = method_ids_from_shortlist(method_selection)
    excluded_rows = excluded_venn_methods(method_selection)
    excluded_methods = {str(row.get("cp_method")) for row in excluded_rows}
    excluded_with_gate = [
        row
        for row in excluded_rows
        if "venn_abers_validation_gate_blocked" in (row.get("exclusion_reasons") or [])
    ]
    selection_disposition_ok = (
        method_selection_summary.get("overall_status")
        == "method_selection_candidate_audit_ready_no_final_selection"
        and method_selection_summary.get("can_support_final_method_selection") is False
        and method_selection_summary.get("final_selection_claim_status") == "blocked"
        and set(shortlist_methods).isdisjoint(VA_METHODS)
        and excluded_methods == VA_METHODS
        and len(excluded_with_gate) == len(VA_METHODS)
        and safe_int(method_selection_summary.get("venn_abers_excluded_count"))
        == len(VA_METHODS)
        and method_selection_summary.get("venn_abers_validation_status")
        == "venn_abers_validation_blocked_with_negative_evidence"
    )

    performance_summary = summaries["method_performance_synthesis"]
    performance_descriptive_ok = (
        performance_summary.get("overall_status")
        == "method_performance_synthesis_descriptive_no_final_selection"
        and performance_summary.get("can_support_final_method_selection") is False
        and performance_summary.get("claim_status") == "descriptive_no_final_selection"
    )

    bundle_summary = summaries["bundle_eligibility_matrix"]
    bundle_rows = bundle_disposition_rows(payloads["bundle_eligibility_matrix"])
    bundle_main_eligible = [row for row in bundle_rows if row["main_results_eligible"]]
    bundle_main_unblocked = [row for row in bundle_rows if not row["main_results_blocked"]]
    bundle_disposition_ok = (
        bundle_summary.get("overall_status")
        == "bundle_eligibility_matrix_ready_no_final_claims"
        and safe_int(bundle_summary.get("main_results_eligible_count")) == 0
        and safe_int(bundle_summary.get("final_claim_eligible_count")) == 0
        and len(bundle_main_eligible) == 0
        and len(bundle_main_unblocked) == 0
    )

    checks = [
        check_row(
            "source_artifacts_present",
            not missing_sources,
            severity="high",
            description="All source artifacts for Venn-Abers disposition must exist.",
            observed={"missing_sources": missing_sources},
        ),
        check_row(
            "negative_claim_registered",
            negative_claim_ok,
            severity="high",
            description="The manuscript claim register keeps Venn-Abers as a diagnostic negative-result claim.",
            observed={
                "claim_id": claim.get("claim_id"),
                "claim_type": claim.get("claim_type"),
                "status": claim.get("status"),
                "method_ids": claim.get("method_ids"),
                "negative_evidence_requirement_status": requirement_status(
                    claim, "negative_evidence_preserved"
                ),
            },
        ),
        check_row(
            "fast_bridge_negative_evidence_preserved",
            fast_bridge_negative_ok,
            severity="high",
            description="Fast bridge undercoverage remains recorded and blocks validation.",
            observed={
                "overall_status": readiness.get("overall_status"),
                "can_support_venn_abers_regression_validation": readiness.get(
                    "can_support_venn_abers_regression_validation"
                ),
                "diagnostic_panel_count": readiness.get("diagnostic_panel_count"),
                "undercoverage_panel_count": readiness.get("undercoverage_panel_count"),
                "undercoverage_run_count": readiness.get("undercoverage_run_count"),
            },
        ),
        check_row(
            "grid_ivapd_remains_diagnostic",
            grid_ivapd_diagnostic_ok,
            severity="high",
            description="Score-grid and IVAPD diagnostics are not promoted to validated interval CP.",
            observed={
                "protocol_status": protocol.get("overall_status"),
                "failure_mode_status": failure_modes.get("overall_status"),
                "can_support_validated_venn_abers_regression": protocol.get(
                    "can_support_validated_venn_abers_regression"
                ),
                "validation_blocker_count": protocol.get("validation_blocker_count"),
                "ivapd_interval_cp_status": protocol.get("ivapd_interval_cp_status"),
            },
        ),
        check_row(
            "claim_gate_blocks_positive_validation",
            claim_gate_blocks_ok,
            severity="high",
            description="The Venn-Abers positive-claim gate is blocked with complete evidence.",
            observed={
                "overall_status": claim_gate.get("overall_status"),
                "positive_claim_ready": claim_gate.get("positive_claim_ready"),
                "positive_claim_blocked_count": claim_gate.get(
                    "positive_claim_blocked_count"
                ),
                "blocked_positive_requirement_ids": claim_gate.get(
                    "blocked_positive_requirement_ids"
                ),
            },
        ),
        check_row(
            "final_selection_boundary_blocks_venn_abers",
            final_boundary_blocks_ok,
            severity="high",
            description="The final-selection boundary keeps Venn-Abers validation blocked.",
            observed={
                "overall_status": final_boundary.get("overall_status"),
                "claim_status": final_boundary.get("claim_status"),
                "venn_abers_regression_validation_gate": requirement_statuses.get(
                    "venn_abers_regression_validation_gate"
                ),
            },
        ),
        check_row(
            "method_selection_excludes_validation_blocked_venn_abers",
            selection_disposition_ok,
            severity="high",
            description="Validation-blocked Venn-Abers methods are excluded from the shortlist.",
            observed={
                "shortlist_methods": shortlist_methods,
                "excluded_venn_methods": sorted(excluded_methods),
                "excluded_with_gate_count": len(excluded_with_gate),
                "venn_abers_excluded_count": method_selection_summary.get(
                    "venn_abers_excluded_count"
                ),
                "venn_abers_validation_status": method_selection_summary.get(
                    "venn_abers_validation_status"
                ),
            },
        ),
        check_row(
            "method_performance_is_descriptive_only",
            performance_descriptive_ok,
            severity="medium",
            description="Performance synthesis remains descriptive and cannot select a final method.",
            observed={
                "overall_status": performance_summary.get("overall_status"),
                "claim_status": performance_summary.get("claim_status"),
                "can_support_final_method_selection": performance_summary.get(
                    "can_support_final_method_selection"
                ),
            },
        ),
        check_row(
            "manuscript_bundle_surface_disposition",
            bundle_disposition_ok,
            severity="high",
            description="Venn-Abers-mentioned manuscript bundles are blocked from main-result surfaces.",
            observed={
                "bundle_row_count": len(bundle_rows),
                "main_results_eligible_count": bundle_summary.get(
                    "main_results_eligible_count"
                ),
                "final_claim_eligible_count": bundle_summary.get(
                    "final_claim_eligible_count"
                ),
                "venn_bundle_main_eligible_count": len(bundle_main_eligible),
                "venn_bundle_main_unblocked_count": len(bundle_main_unblocked),
            },
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    status_counts = Counter(row["status"] for row in checks)
    excluded_reason_counts = Counter(
        reason
        for row in excluded_rows
        for reason in row.get("exclusion_reasons") or []
    )
    overall_status = (
        "venn_abers_negative_evidence_disposition_fail"
        if failed_checks
        else "venn_abers_negative_evidence_disposition_pass"
    )
    negative_result_reporting_ready = not failed_checks
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {key: rel(path, root) for key, path in paths.items()},
        "summary": {
            "overall_status": overall_status,
            "manuscript_disposition_status": (
                "accepted_negative_result_for_current_manuscript"
                if negative_result_reporting_ready
                else "negative_result_disposition_not_clean"
            ),
            "negative_result_reporting_ready": negative_result_reporting_ready,
            "current_manuscript_positive_validation_required": (
                not negative_result_reporting_ready
            ),
            "optional_future_positive_validation_status": (
                "optional_deferred_not_required_for_current_manuscript"
                if negative_result_reporting_ready
                else "blocked_until_negative_disposition_is_clean"
            ),
            "failed_check_count": len(failed_checks),
            "check_status_counts": dict(sorted(status_counts.items())),
            "negative_claim_present": bool(claim),
            "can_support_validated_venn_abers_regression": protocol.get(
                "can_support_validated_venn_abers_regression"
            ),
            "undercoverage_run_count": readiness.get("undercoverage_run_count"),
            "validation_blocker_count": protocol.get("validation_blocker_count"),
            "positive_claim_blocked_count": claim_gate.get(
                "positive_claim_blocked_count"
            ),
            "shortlist_method_count": len(shortlist_methods),
            "shortlist_venn_abers_method_count": len(
                set(shortlist_methods) & VA_METHODS
            ),
            "excluded_venn_abers_method_count": len(excluded_methods),
            "excluded_with_validation_gate_count": len(excluded_with_gate),
            "venn_bundle_row_count": len(bundle_rows),
            "venn_bundle_main_eligible_count": len(bundle_main_eligible),
            "venn_bundle_main_unblocked_count": len(bundle_main_unblocked),
            "bundle_main_results_eligible_count": bundle_summary.get(
                "main_results_eligible_count"
            ),
            "final_selection_venn_abers_gate_status": requirement_statuses.get(
                "venn_abers_regression_validation_gate"
            ),
            "excluded_venn_abers_reason_counts": dict(
                sorted(excluded_reason_counts.items())
            ),
        },
        "claim_boundaries": [
            "This audit is a disposition control, not new empirical validation.",
            "Passing means Venn-Abers negative evidence is traceably quarantined from final-selection and main-result surfaces.",
            "The fast bridge remains failure-mode evidence; the split fallback remains ordinary split conformal fallback evidence.",
            "Score-grid and IVAPD diagnostics remain validation-design evidence, not validated interval-CP claims.",
            "The current manuscript may report the observed negative Venn-Abers result without forcing a positive validation outcome.",
        ],
        "checks": checks,
        "excluded_venn_abers_methods": excluded_rows,
        "venn_abers_bundle_disposition_rows": bundle_rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Venn-Abers Negative Evidence Disposition Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Undercoverage runs: {summary['undercoverage_run_count']}",
        f"- Validation blockers: {summary['validation_blocker_count']}",
        f"- Shortlist Venn-Abers methods: {summary['shortlist_venn_abers_method_count']}",
        f"- Excluded Venn-Abers methods: {summary['excluded_venn_abers_method_count']}",
        f"- Venn-Abers bundle rows: {summary['venn_bundle_row_count']}",
        f"- Venn-Abers bundle main-eligible rows: {summary['venn_bundle_main_eligible_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Severity | Status | Observed |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["checks"]:
        lines.append(
            "| "
            f"`{row['check_id']}` | "
            f"`{row['severity']}` | "
            f"`{row['status']}` | "
            f"`{json.dumps(row.get('observed') or {}, sort_keys=True)}` |"
        )
    lines.extend(
        [
            "",
            "## Venn-Abers Bundle Disposition Rows",
            "",
            "| Bundle | Candidate | Main eligible | Main blocked | Status |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["venn_abers_bundle_disposition_rows"]:
        lines.append(
            "| "
            f"`{row.get('bundle_id')}` | "
            f"`{row.get('paper_table_candidate')}` | "
            f"`{row.get('main_results_eligible')}` | "
            f"`{row.get('main_results_blocked')}` | "
            f"`{row.get('status')}` |"
        )
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
                "status": payload["summary"]["overall_status"],
                "out": rel(out_path, root),
                "failed_check_count": payload["summary"]["failed_check_count"],
                "excluded_venn_abers_method_count": payload["summary"][
                    "excluded_venn_abers_method_count"
                ],
                "venn_bundle_main_eligible_count": payload["summary"][
                    "venn_bundle_main_eligible_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
