"""Build a Venn-Abers regression positive-claim gate matrix.

The Venn-Abers diagnostics now include fast-bridge negative evidence, a full
score-grid reference, IVAPD threshold-grid diagnostics, and a failure-mode
decomposition. This audit joins those artifacts into one claim-gate matrix so
the manuscript path can distinguish:

- hygiene requirements that are already satisfied;
- positive-claim requirements that remain blocked by empirical evidence; and
- true audit failures where the repository would be overclaiming validation.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_venn_abers_claim_gate_matrix_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "venn_abers_claim_gate_matrix.json"
VALIDATION_READINESS = REPORT_DIR / "venn_abers_validation_readiness_audit.json"
GRID_IVAPD_PROTOCOL = REPORT_DIR / "venn_abers_grid_ivapd_validation_protocol.json"
GRID_EXPANSION_PLAN = REPORT_DIR / "venn_abers_grid_expansion_plan.json"
FAILURE_MODE_DECOMPOSITION = (
    REPORT_DIR / "venn_abers_grid_failure_mode_decomposition.json"
)
FINAL_SELECTION = REPORT_DIR / "final_selection_claim_boundary_audit.json"
PUBLICATION_METHODOLOGY = REPORT_DIR / "publication_methodology_audit.json"


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
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return value if isinstance(value, dict) else {}


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def status_for_condition(
    passed: bool,
    *,
    blocked_when_false: bool,
    missing: bool = False,
) -> str:
    if missing:
        return "fail"
    if passed:
        return "pass"
    return "blocked" if blocked_when_false else "fail"


def gate_row(
    requirement_id: str,
    family: str,
    status: str,
    *,
    positive_claim_requirement: bool,
    requirement: str,
    evidence_artifacts: list[str],
    evidence_node_ids: list[str],
    observed: dict[str, Any],
    closure_standard: str,
    interpretation: str,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "family": family,
        "status": status,
        "positive_claim_requirement": positive_claim_requirement,
        "requirement": requirement,
        "closure_standard": closure_standard,
        "interpretation": interpretation,
        "evidence_artifacts": evidence_artifacts,
        "evidence_node_ids": evidence_node_ids,
        "observed": observed,
    }


def build_payload(root: Path) -> dict[str, Any]:
    paths = {
        "validation_readiness": root / VALIDATION_READINESS,
        "grid_ivapd_protocol": root / GRID_IVAPD_PROTOCOL,
        "grid_expansion_plan": root / GRID_EXPANSION_PLAN,
        "failure_mode_decomposition": root / FAILURE_MODE_DECOMPOSITION,
        "final_selection": root / FINAL_SELECTION,
        "publication_methodology": root / PUBLICATION_METHODOLOGY,
    }
    payloads = {key: read_json(path) for key, path in paths.items()}
    summaries = {key: summary(value) for key, value in payloads.items()}

    readiness = summaries["validation_readiness"]
    protocol = summaries["grid_ivapd_protocol"]
    plan = summaries["grid_expansion_plan"]
    failure_modes = summaries["failure_mode_decomposition"]
    final_selection = summaries["final_selection"]
    publication = summaries["publication_methodology"]

    missing_sources = [key for key, path in paths.items() if not path.exists()]
    nominal = as_float(protocol.get("nominal_coverage")) or as_float(
        failure_modes.get("nominal_coverage")
    )
    if nominal is None:
        nominal = 0.9

    source_reports_available = (
        not missing_sources
        and as_int(readiness.get("source_report_count")) >= 4
        and as_int(protocol.get("source_report_count")) >= 3
        and as_int(failure_modes.get("source_report_count")) >= 3
    )
    diagnostic_panel_count = as_int(readiness.get("diagnostic_panel_count"))
    undercoverage_panel_count = as_int(readiness.get("undercoverage_panel_count"))
    undercoverage_run_count = as_int(readiness.get("undercoverage_run_count"))
    negative_evidence_present = (
        readiness.get("negative_evidence_requirement_status") == "present"
        and diagnostic_panel_count > 0
        and undercoverage_panel_count == diagnostic_panel_count
        and undercoverage_run_count > 0
    )
    bridge_blocked = (
        readiness.get("can_support_venn_abers_regression_validation") is False
        and readiness.get("validation_requirement_status") == "blocked"
        and readiness.get("overall_status")
        == "venn_abers_validation_blocked_with_negative_evidence"
    )
    split_fallback_boundary = (
        as_int(readiness.get("split_fallback_near_nominal_panel_count")) > 0
        and "split fallback"
        in str(readiness.get("claim_boundary", "")).lower()
    )
    grid_complete = (
        plan.get("overall_status") == "venn_abers_grid_expansion_plan_complete"
        and as_int(plan.get("total_grid_rows_pending")) == 0
        and as_int(plan.get("total_grid_rows_completed"))
        == as_int(plan.get("total_test_rows_available"))
        == as_int(protocol.get("total_grid_reference_rows_scored"))
        == as_int(protocol.get("total_grid_reference_rows_available"))
    )
    min_panel_grid_coverage = as_float(protocol.get("min_panel_grid_reference_coverage"))
    grid_panel_coverage_nominal = (
        min_panel_grid_coverage is not None and min_panel_grid_coverage >= nominal
    )
    max_panel_grid_hit_upper_rate = as_float(protocol.get("max_panel_grid_hit_upper_rate"))
    grid_upper_boundary_free = (
        max_panel_grid_hit_upper_rate is not None
        and max_panel_grid_hit_upper_rate
        <= as_float(failure_modes.get("max_grid_upper_hit_rate_for_claim") or 0.0)
    )
    ivapd_validated = (
        protocol.get("can_support_ivapd_interval_cp_validation") is True
        and protocol.get("ivapd_interval_cp_status") == "validated_interval_cp"
    )
    worker_failures_resolved = (
        protocol.get("failed_worker_rows_all_superseded") is True
        and as_int(protocol.get("worker_unresolved_failed_task_key_count")) == 0
    )
    failure_decomposition_present = (
        failure_modes.get("overall_status")
        == "venn_abers_grid_failure_modes_decomposed_no_claim"
        and failure_modes.get("can_support_validated_venn_abers_regression") is False
        and as_int(failure_modes.get("validation_blocker_count")) > 0
        and as_int(failure_modes.get("failed_check_count")) == 0
    )

    evidence_path = {
        key: rel(path, root) for key, path in paths.items()
    }
    rows = [
        gate_row(
            "source_reports_available",
            "evidence_hygiene",
            status_for_condition(
                source_reports_available,
                blocked_when_false=False,
                missing=bool(missing_sources),
            ),
            positive_claim_requirement=False,
            requirement="All Venn-Abers diagnostic, protocol, expansion, failure-mode, final-claim, and publication guardrail artifacts must be present.",
            closure_standard="All source artifacts exist and report the expected diagnostic source counts.",
            interpretation="This is a reproducibility hygiene requirement, not positive validation evidence.",
            evidence_artifacts=list(evidence_path.values()),
            evidence_node_ids=[
                "report:venn_abers_validation_readiness_audit",
                "report:venn_abers_grid_ivapd_validation_protocol",
                "report:venn_abers_grid_expansion_plan",
                "report:venn_abers_grid_failure_mode_decomposition",
            ],
            observed={
                "missing_sources": missing_sources,
                "validation_source_report_count": readiness.get("source_report_count"),
                "protocol_source_report_count": protocol.get("source_report_count"),
                "failure_mode_source_report_count": failure_modes.get(
                    "source_report_count"
                ),
            },
        ),
        gate_row(
            "fast_bridge_negative_evidence_preserved",
            "negative_evidence",
            status_for_condition(negative_evidence_present, blocked_when_false=False),
            positive_claim_requirement=False,
            requirement="The fast Venn-Abers quantile bridge must remain recorded as negative diagnostic evidence.",
            closure_standard="Every diagnostic panel undercovers nominal coverage and the negative-evidence manuscript requirement is present.",
            interpretation="The fast bridge is useful failure-mode evidence, not a validated regression Venn-Abers interval method.",
            evidence_artifacts=[evidence_path["validation_readiness"]],
            evidence_node_ids=[
                "report:venn_abers_validation_readiness_audit",
                "manuscript_claim:venn_abers_fast_bridge_negative_result",
            ],
            observed={
                "nominal_coverage": nominal,
                "diagnostic_panel_count": diagnostic_panel_count,
                "undercoverage_panel_count": undercoverage_panel_count,
                "undercoverage_run_count": undercoverage_run_count,
                "min_venn_abers_run_coverage": readiness.get(
                    "min_venn_abers_run_coverage"
                ),
                "max_venn_abers_run_coverage": readiness.get(
                    "max_venn_abers_run_coverage"
                ),
            },
        ),
        gate_row(
            "fast_bridge_not_validated",
            "claim_boundary",
            status_for_condition(bridge_blocked, blocked_when_false=False),
            positive_claim_requirement=False,
            requirement="The fast bridge must not be promoted to validated Venn-Abers regression.",
            closure_standard="The readiness audit and final validation requirement keep the bridge blocked.",
            interpretation="This guardrail prevents a negative diagnostic from becoming a positive method claim.",
            evidence_artifacts=[evidence_path["validation_readiness"]],
            evidence_node_ids=[
                "report:venn_abers_validation_readiness_audit",
                "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            ],
            observed={
                "overall_status": readiness.get("overall_status"),
                "validation_requirement_status": readiness.get(
                    "validation_requirement_status"
                ),
                "can_support_venn_abers_regression_validation": readiness.get(
                    "can_support_venn_abers_regression_validation"
                ),
            },
        ),
        gate_row(
            "split_fallback_boundary_preserved",
            "claim_boundary",
            status_for_condition(split_fallback_boundary, blocked_when_false=False),
            positive_claim_requirement=False,
            requirement="The split fallback must remain ordinary split conformal fallback evidence.",
            closure_standard="Fallback performance is documented without labeling it as Venn-Abers validation.",
            interpretation="Good fallback coverage cannot repair the Venn-Abers bridge claim.",
            evidence_artifacts=[evidence_path["validation_readiness"]],
            evidence_node_ids=[
                "method:venn_abers_split_fallback",
                "method_spec:venn_abers_regression",
            ],
            observed={
                "split_fallback_near_nominal_panel_count": readiness.get(
                    "split_fallback_near_nominal_panel_count"
                ),
                "claim_boundary": readiness.get("claim_boundary"),
            },
        ),
        gate_row(
            "score_grid_full_test_scored",
            "grid_reference",
            status_for_condition(grid_complete, blocked_when_false=True),
            positive_claim_requirement=True,
            requirement="The score-grid reference must be complete over all diagnostic test rows.",
            closure_standard="Completed grid rows equal available test rows, with zero pending rows.",
            interpretation="This requirement now passes operationally; it is necessary but not sufficient for validation.",
            evidence_artifacts=[
                evidence_path["grid_ivapd_protocol"],
                evidence_path["grid_expansion_plan"],
            ],
            evidence_node_ids=[
                "report:venn_abers_grid_ivapd_validation_protocol",
                "report:venn_abers_grid_expansion_plan",
            ],
            observed={
                "total_grid_rows_completed": plan.get("total_grid_rows_completed"),
                "total_test_rows_available": plan.get("total_test_rows_available"),
                "total_grid_rows_pending": plan.get("total_grid_rows_pending"),
                "protocol_total_grid_reference_rows_scored": protocol.get(
                    "total_grid_reference_rows_scored"
                ),
                "protocol_total_grid_reference_rows_available": protocol.get(
                    "total_grid_reference_rows_available"
                ),
                "grid_completion_fraction": plan.get("grid_completion_fraction"),
            },
        ),
        gate_row(
            "score_grid_panel_coverage_nominal",
            "grid_reference",
            status_for_condition(grid_panel_coverage_nominal, blocked_when_false=True),
            positive_claim_requirement=True,
            requirement="The score-grid reference must meet nominal coverage at the panel level.",
            closure_standard="Minimum panel grid-reference coverage is at least nominal coverage.",
            interpretation="This is a current empirical blocker for a positive Venn-Abers regression claim.",
            evidence_artifacts=[
                evidence_path["grid_ivapd_protocol"],
                evidence_path["failure_mode_decomposition"],
            ],
            evidence_node_ids=[
                "report:venn_abers_grid_ivapd_validation_protocol",
                "report:venn_abers_grid_failure_mode_decomposition",
            ],
            observed={
                "nominal_coverage": nominal,
                "min_panel_grid_reference_coverage": min_panel_grid_coverage,
                "min_run_grid_reference_coverage": failure_modes.get(
                    "min_run_grid_reference_coverage"
                ),
                "coverage_failure_panel_count": failure_modes.get(
                    "coverage_failure_panel_count"
                ),
                "coverage_failure_run_count": failure_modes.get(
                    "coverage_failure_run_count"
                ),
            },
        ),
        gate_row(
            "score_grid_upper_boundary_free",
            "grid_reference",
            status_for_condition(grid_upper_boundary_free, blocked_when_false=True),
            positive_claim_requirement=True,
            requirement="The finite score grid must not place candidate intervals against the upper grid boundary.",
            closure_standard="Observed grid upper-hit rate is at the claim threshold, currently zero.",
            interpretation="This is a current grid-resolution blocker: the finite grid is still binding on some rows.",
            evidence_artifacts=[
                evidence_path["grid_ivapd_protocol"],
                evidence_path["failure_mode_decomposition"],
            ],
            evidence_node_ids=[
                "report:venn_abers_grid_ivapd_validation_protocol",
                "report:venn_abers_grid_failure_mode_decomposition",
            ],
            observed={
                "max_grid_upper_hit_rate_for_claim": failure_modes.get(
                    "max_grid_upper_hit_rate_for_claim"
                ),
                "max_panel_grid_hit_upper_rate": max_panel_grid_hit_upper_rate,
                "max_run_grid_hit_upper_rate": failure_modes.get(
                    "max_run_grid_hit_upper_rate"
                ),
                "worker_grid_hit_upper_count": protocol.get(
                    "worker_grid_hit_upper_count"
                ),
                "worker_grid_hit_upper_rate": protocol.get(
                    "worker_grid_hit_upper_rate"
                ),
            },
        ),
        gate_row(
            "ivapd_interval_cp_validated",
            "ivapd",
            status_for_condition(ivapd_validated, blocked_when_false=True),
            positive_claim_requirement=True,
            requirement="The IVAPD threshold grid must be converted into and validated as an interval conformal prediction method before being used as a Venn-Abers regression claim.",
            closure_standard="The protocol explicitly supports IVAPD interval-CP validation.",
            interpretation="Current IVAPD evidence is predictive-distribution diagnostic evidence only.",
            evidence_artifacts=[evidence_path["grid_ivapd_protocol"]],
            evidence_node_ids=[
                "report:venn_abers_grid_ivapd_validation_protocol",
                "method:ivapd_regression",
            ],
            observed={
                "ivapd_interval_cp_status": protocol.get("ivapd_interval_cp_status"),
                "can_support_ivapd_interval_cp_validation": protocol.get(
                    "can_support_ivapd_interval_cp_validation"
                ),
                "total_ivapd_rows_scored": protocol.get("total_ivapd_rows_scored"),
                "total_ivapd_rows_available": protocol.get(
                    "total_ivapd_rows_available"
                ),
                "ivapd_scored_fraction": protocol.get("ivapd_scored_fraction"),
            },
        ),
        gate_row(
            "worker_failures_resolved_or_superseded",
            "reproducibility",
            status_for_condition(worker_failures_resolved, blocked_when_false=False),
            positive_claim_requirement=False,
            requirement="Append-only grid worker failures must be resolved or superseded by completed task keys.",
            closure_standard="No unresolved failed worker task keys remain.",
            interpretation="The resumable grid expansion state is operationally clean.",
            evidence_artifacts=[
                evidence_path["grid_ivapd_protocol"],
                evidence_path["grid_expansion_plan"],
            ],
            evidence_node_ids=[
                "report:venn_abers_grid_ivapd_validation_protocol",
                "report:venn_abers_grid_expansion_plan",
            ],
            observed={
                "failed_worker_rows_all_superseded": protocol.get(
                    "failed_worker_rows_all_superseded"
                ),
                "worker_failed_task_key_count": protocol.get(
                    "worker_failed_task_key_count"
                ),
                "worker_superseded_failed_task_key_count": protocol.get(
                    "worker_superseded_failed_task_key_count"
                ),
                "worker_unresolved_failed_task_key_count": protocol.get(
                    "worker_unresolved_failed_task_key_count"
                ),
            },
        ),
        gate_row(
            "failure_mode_decomposition_present",
            "failure_mode",
            status_for_condition(
                failure_decomposition_present,
                blocked_when_false=False,
            ),
            positive_claim_requirement=False,
            requirement="Completed grid evidence must be decomposed into interpretable blockers before manuscript use.",
            closure_standard="The decomposition records coverage, upper-boundary, and IVAPD blockers under a no-claim boundary.",
            interpretation="This supplies negative-result discussion material without validating Venn-Abers regression.",
            evidence_artifacts=[evidence_path["failure_mode_decomposition"]],
            evidence_node_ids=["report:venn_abers_grid_failure_mode_decomposition"],
            observed={
                "overall_status": failure_modes.get("overall_status"),
                "validation_blocker_count": failure_modes.get("validation_blocker_count"),
                "validation_blocker_ids": failure_modes.get(
                    "validation_blocker_ids",
                    [],
                ),
                "claim_status": failure_modes.get("claim_status"),
            },
        ),
    ]

    positive_rows = [row for row in rows if row["positive_claim_requirement"]]
    blocked_positive_rows = [row for row in positive_rows if row["status"] != "pass"]
    positive_claim_ready = bool(positive_rows) and not blocked_positive_rows
    final_gate_blocked = (
        final_selection.get("claim_status") == "blocked"
        and as_int(final_selection.get("blocked_requirement_count")) > 0
    )
    publication_blocks_va = (
        publication.get("can_support_venn_abers_regression_validation") is False
        and publication.get("overall_status")
        in {"publication_workbench_ready", "publication_workbench_ready_with_caveats"}
    )
    guardrail_rows = [
        gate_row(
            "final_claim_gate_consistent_with_matrix",
            "claim_boundary",
            "pass"
            if (positive_claim_ready or final_gate_blocked)
            else "fail",
            positive_claim_requirement=False,
            requirement="The final Venn-Abers validation claim gate must stay blocked while positive-claim requirements are blocked.",
            closure_standard="Final claim status is blocked unless every positive-claim requirement passes.",
            interpretation="This is the central overclaim guardrail.",
            evidence_artifacts=[evidence_path["final_selection"]],
            evidence_node_ids=[
                "report:final_selection_claim_boundary_audit",
                "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            ],
            observed={
                "positive_claim_ready": positive_claim_ready,
                "final_claim_status": final_selection.get("claim_status"),
                "blocked_requirement_count": final_selection.get(
                    "blocked_requirement_count"
                ),
                "blocked_positive_requirement_ids": [
                    row["requirement_id"] for row in blocked_positive_rows
                ],
            },
        ),
        gate_row(
            "publication_methodology_blocks_venn_abers_claim",
            "claim_boundary",
            status_for_condition(
                positive_claim_ready or publication_blocks_va,
                blocked_when_false=False,
            ),
            positive_claim_requirement=False,
            requirement="The publication methodology audit must block Venn-Abers validation claims.",
            closure_standard="Publication methodology cannot support Venn-Abers regression validation while positive-claim requirements are blocked.",
            interpretation="This prevents manuscript extraction from overriding method-specific blockers.",
            evidence_artifacts=[evidence_path["publication_methodology"]],
            evidence_node_ids=["report:publication_methodology_audit"],
            observed={
                "overall_status": publication.get("overall_status"),
                "can_support_venn_abers_regression_validation": publication.get(
                    "can_support_venn_abers_regression_validation"
                ),
                "failed_check_count": publication.get("failed_check_count"),
            },
        ),
    ]
    rows.extend(guardrail_rows)

    status_counts = Counter(row["status"] for row in rows)
    positive_status_counts = Counter(row["status"] for row in positive_rows)
    failed_count = status_counts.get("fail", 0)
    publication_can_support_validated = (
        publication.get("can_support_venn_abers_regression_validation") is True
    )
    can_support_validated = (
        positive_claim_ready and publication_can_support_validated and failed_count == 0
    )
    if failed_count:
        overall_status = "venn_abers_claim_gate_matrix_audit_fail"
    elif can_support_validated:
        overall_status = "venn_abers_claim_gate_matrix_ready_for_positive_claim"
    else:
        overall_status = "venn_abers_claim_gate_matrix_blocked_with_complete_evidence"

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": evidence_path,
        "nominal_coverage": nominal,
        "summary": {
            "overall_status": overall_status,
            "can_support_validated_venn_abers_regression": can_support_validated,
            "positive_claim_ready": positive_claim_ready,
            "requirement_count": len(rows),
            "positive_claim_requirement_count": len(positive_rows),
            "positive_claim_pass_count": positive_status_counts.get("pass", 0),
            "positive_claim_blocked_count": sum(
                count
                for status, count in positive_status_counts.items()
                if status != "pass"
            ),
            "blocked_positive_requirement_ids": [
                row["requirement_id"] for row in blocked_positive_rows
            ],
            "status_counts": dict(sorted(status_counts.items())),
            "failed_check_count": failed_count,
            "diagnostic_panel_count": diagnostic_panel_count,
            "undercoverage_run_count": undercoverage_run_count,
            "total_grid_reference_rows_scored": protocol.get(
                "total_grid_reference_rows_scored"
            ),
            "total_grid_reference_rows_available": protocol.get(
                "total_grid_reference_rows_available"
            ),
            "grid_completion_fraction": plan.get("grid_completion_fraction"),
            "min_panel_grid_reference_coverage": min_panel_grid_coverage,
            "max_panel_grid_hit_upper_rate": max_panel_grid_hit_upper_rate,
            "ivapd_interval_cp_status": protocol.get("ivapd_interval_cp_status"),
            "validation_blocker_ids": failure_modes.get("validation_blocker_ids", []),
        },
        "claim_boundaries": [
            "This matrix is a claim-gate audit, not a new Venn-Abers method result.",
            "Positive Venn-Abers regression validation requires every positive-claim requirement to pass.",
            "Fast bridge undercoverage and finite-grid blockers are negative or diagnostic evidence only.",
            "Split fallback evidence remains ordinary split conformal fallback evidence.",
        ],
        "requirements": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Venn-Abers Claim Gate Matrix",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Can support validated Venn-Abers regression: `{summary['can_support_validated_venn_abers_regression']}`",
        f"- Positive-claim requirements: {summary['positive_claim_pass_count']} pass / {summary['positive_claim_blocked_count']} blocked",
        f"- Requirement status counts: `{summary['status_counts']}`",
        f"- Blocked positive requirements: `{summary['blocked_positive_requirement_ids']}`",
        f"- Grid rows scored / available: {summary['total_grid_reference_rows_scored']} / {summary['total_grid_reference_rows_available']}",
        f"- Min panel grid-reference coverage: {summary['min_panel_grid_reference_coverage']}",
        f"- Max panel grid upper-hit rate: {summary['max_panel_grid_hit_upper_rate']}",
        f"- IVAPD status: `{summary['ivapd_interval_cp_status']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Requirements",
            "",
            "| Requirement | Family | Status | Positive claim requirement | Interpretation |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["requirements"]:
        lines.append(
            "| "
            f"`{row['requirement_id']}` | "
            f"`{row['family']}` | "
            f"`{row['status']}` | "
            f"`{row['positive_claim_requirement']}` | "
            f"{row['interpretation']} |"
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
                "status": "ok",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
