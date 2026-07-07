"""Build a paper-facing selection/multiplicity evidence record.

This artifact binds the completed post-selection validation results to the
manuscript selection/multiplicity contract. It records a diagnostic primary
candidate and full multiplicity scope, but it does not promote a final method
or model winner while paper gates remain blocked.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_selection_multiplicity_evidence_record_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/selection_multiplicity_evidence_record.json")
MANIFEST_SCHEMA = Path("experiments/regression/catalogs/manuscript_evidence_manifest_schema.json")
SELECTION_PROTOCOL = Path("experiments/regression/manuscript/selection_multiplicity_protocol.json")
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
CANDIDATE_AUDIT = REPORT_DIR / "method_selection_candidate_audit.json"
ROBUSTNESS_AUDIT = REPORT_DIR / "method_selection_robustness_audit.json"
VALIDATION_RESULTS = REPORT_DIR / "method_selection_post_selection_validation_results.json"
FINAL_SELECTION = REPORT_DIR / "final_selection_claim_boundary_audit.json"
PUBLICATION_METHODOLOGY = REPORT_DIR / "publication_methodology_audit.json"

CLAIM_BOUNDARIES = [
    "This is a selection/multiplicity evidence record, not a final method-selection result.",
    "CQR can be described only as the diagnostic primary candidate under the recorded validation scope.",
    "Final winner, fairness/population, bounded-support, production, and validated Venn-Abers regression claims remain blocked by separate gates.",
    "All searched validation methods and non-selected outcomes remain part of the multiplicity record.",
]


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
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def top_counts(counts: dict[str, int]) -> tuple[str | None, int, str | None, int]:
    ranked = sorted(
        ((str(key), int(value)) for key, value in counts.items()),
        key=lambda item: (-item[1], item[0]),
    )
    if not ranked:
        return None, 0, None, 0
    first = ranked[0]
    second = ranked[1] if len(ranked) > 1 else (None, 0)
    return first[0], first[1], second[0], second[1]


def source_paths(root: Path) -> dict[str, Path]:
    return {
        "manifest_schema": root / MANIFEST_SCHEMA,
        "selection_multiplicity_protocol": root / SELECTION_PROTOCOL,
        "paper_readiness_map": root / PAPER_READINESS,
        "method_selection_candidate_audit": root / CANDIDATE_AUDIT,
        "method_selection_robustness_audit": root / ROBUSTNESS_AUDIT,
        "method_selection_post_selection_validation_results": root / VALIDATION_RESULTS,
        "final_selection_claim_boundary_audit": root / FINAL_SELECTION,
        "publication_methodology_audit": root / PUBLICATION_METHODOLOGY,
    }


def build_selection_multiplicity_evidence(
    manifest_schema: dict[str, Any],
    selection_protocol: dict[str, Any],
    validation_results: dict[str, Any],
    candidate_audit: dict[str, Any],
    robustness_audit: dict[str, Any],
    paper_readiness: dict[str, Any],
    final_selection: dict[str, Any],
    publication_methodology: dict[str, Any],
) -> dict[str, Any]:
    schema_fields = list(
        manifest_schema.get("selection_multiplicity_evidence_fields") or []
    )
    validation_summary = validation_results.get("summary") or {}
    protocol_summary = selection_protocol.get("summary") or {}
    candidate_summary = candidate_audit.get("summary") or {}
    robustness_summary = robustness_audit.get("summary") or {}
    paper_summary = paper_readiness.get("summary") or {}
    final_summary = final_selection.get("summary") or {}
    publication_summary = publication_methodology.get("summary") or {}
    diagnostic_counts = {
        str(key): int(value)
        for key, value in (validation_summary.get("diagnostic_winner_counts") or {}).items()
    }
    primary, primary_count, runner_up, runner_up_count = top_counts(diagnostic_counts)
    validation_dataset_rows = validation_results.get("dataset_rows") or []
    validation_datasets = [
        str(row.get("dataset_id"))
        for row in validation_dataset_rows
        if row.get("dataset_id")
    ]
    validation_methods = [
        str(method) for method in validation_summary.get("candidate_methods") or []
    ]
    per_cell = (
        (validation_results.get("diagnostic_selection") or {}).get("per_cell") or []
    )
    alphas = sorted({str(row.get("alpha")) for row in per_cell if row.get("alpha")})
    evidence = {
        "predeclared_operating_criterion": {
            "status": "recorded_from_protocol_and_validation_audit",
            "criterion": (
                "Within matched dataset-alpha validation cells, rank candidate "
                "methods by nominal coverage tier, near-nominal tolerance, "
                "interval score, absolute coverage error, and width."
            ),
            "source_protocol_field": "predeclared_operating_criterion",
            "diagnostic_primary_method": primary,
            "final_winner_language_allowed": False,
        },
        "ranking_scope": {
            "status": "validation_scope_recorded",
            "dataset_count": len(validation_datasets),
            "datasets": validation_datasets,
            "alpha_count": len(alphas),
            "alphas": alphas,
            "candidate_method_count": len(validation_methods),
            "candidate_methods": validation_methods,
            "model_scope": "one representative ridge source model per dataset",
            "seed_scope": "independent post-selection validation seeds 101, 211, 307",
            "common_dataset_alpha_cell_count": validation_summary.get(
                "common_dataset_alpha_cell_count"
            ),
        },
        "multiplicity_scope": {
            "status": "validation_multiplicity_recorded",
            "pre_validation_completed_rows_scanned": candidate_summary.get(
                "source_completed_ledger_rows"
            ),
            "robustness_common_cell_count": robustness_summary.get(
                "common_dataset_alpha_cell_count"
            ),
            "validation_expected_atomic_rows": validation_summary.get(
                "expected_atomic_run_count"
            ),
            "validation_completed_atomic_rows": validation_summary.get(
                "completed_atomic_run_count"
            ),
            "validation_aggregated_candidate_rows": (
                len(validation_datasets) * len(alphas) * len(validation_methods)
            ),
            "diagnostic_winner_counts": diagnostic_counts,
            "nonselected_methods": [
                method for method in validation_methods if method != primary
            ],
            "width_pathology_row_count": validation_summary.get(
                "width_pathology_row_count"
            ),
        },
        "tie_break_rule": {
            "status": "deterministic_tie_break_recorded",
            "rule": [
                "prefer nominal-or-above coverage tier",
                "then near-nominal coverage tier",
                "then lower interval score",
                "then lower absolute coverage error",
                "then lower mean width",
                "then lexicographic method id",
            ],
        },
        "nominal_coverage_requirement": {
            "status": "coverage_guard_recorded",
            "requirement": (
                "Winner language requires nominal-or-above coverage inside the "
                "declared scope; undercoverage remains negative evidence."
            ),
            "validation_width_pathologies_retained": validation_summary.get(
                "width_pathology_row_count"
            ),
        },
        "post_selection_claim_boundary": {
            "status": "blocked_final_claim_boundary_recorded",
            "can_support_final_method_selection": False,
            "final_selection_claim_status": final_summary.get("claim_status"),
            "paper_readiness_status": paper_summary.get("overall_status"),
            "blocked_gate_count": paper_summary.get("blocked_gate_count"),
        },
        "exploratory_ranking_label": {
            "status": "diagnostic_primary_candidate_only",
            "allowed_label": "diagnostic primary candidate",
            "forbidden_labels": [
                "final winner",
                "validated best method",
                "fairness-ready method",
                "bounded-support-valid method",
                "validated Venn-Abers regression method",
            ],
        },
        "sensitivity_or_holdout_validation": {
            "status": "post_selection_validation_completed_but_claim_gates_blocked",
            "validation_completed_atomic_rows": validation_summary.get(
                "completed_atomic_run_count"
            ),
            "feature_leakage_violation_count": validation_summary.get(
                "feature_leakage_violation_count"
            ),
            "validation_failed_check_count": validation_summary.get(
                "failed_check_count"
            ),
            "publication_methodology_status": publication_summary.get(
                "overall_status"
            ),
        },
    }
    missing_fields = [field for field in schema_fields if field not in evidence]
    extra_fields = [field for field in evidence if field not in schema_fields]
    selection_record = {
        "record_id": "post_selection_validation_cqr_diagnostic_primary_candidate",
        "record_status": "diagnostic_primary_candidate_recorded_final_selection_blocked",
        "diagnostic_primary_method": primary,
        "diagnostic_primary_win_count": primary_count,
        "diagnostic_runner_up_method": runner_up,
        "diagnostic_runner_up_win_count": runner_up_count,
        "diagnostic_margin": primary_count - runner_up_count,
        "candidate_methods": validation_methods,
        "final_selection_eligible": False,
        "can_support_final_method_selection": False,
        "blocking_gate_count": paper_summary.get("blocked_gate_count"),
        "blocking_gate_ids": [
            row.get("gate_id")
            for row in paper_readiness.get("blocked_gates") or []
            if row.get("status") == "blocked"
        ],
    }
    return {
        "required_fields": schema_fields,
        "missing_fields": missing_fields,
        "extra_fields": extra_fields,
        "field_record": evidence,
        "selection_records": [selection_record],
    }


def build_checks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    summary = payload["summary"]
    evidence = payload["selection_multiplicity_evidence"]
    checks = [
        {
            "check_id": "required_manifest_fields_covered",
            "status": "pass" if not evidence["missing_fields"] and not evidence["extra_fields"] else "fail",
            "observed": {
                "missing_fields": evidence["missing_fields"],
                "extra_fields": evidence["extra_fields"],
            },
        },
        {
            "check_id": "validation_results_complete",
            "status": (
                "pass"
                if summary["validation_completed_atomic_rows"]
                == summary["validation_expected_atomic_rows"]
                and summary["validation_failed_check_count"] == 0
                else "fail"
            ),
            "observed": {
                "expected": summary["validation_expected_atomic_rows"],
                "completed": summary["validation_completed_atomic_rows"],
                "failed_check_count": summary["validation_failed_check_count"],
            },
        },
        {
            "check_id": "diagnostic_primary_consistent_with_prior_audits",
            "status": (
                "pass"
                if summary["diagnostic_primary_method"]
                == summary["candidate_audit_primary_method"]
                == summary["robustness_primary_method"]
                else "fail"
            ),
            "observed": {
                "diagnostic_primary_method": summary["diagnostic_primary_method"],
                "candidate_audit_primary_method": summary[
                    "candidate_audit_primary_method"
                ],
                "robustness_primary_method": summary["robustness_primary_method"],
            },
        },
        {
            "check_id": "feature_leakage_clean",
            "status": (
                "pass"
                if summary["feature_leakage_violation_count"] == 0
                else "fail"
            ),
            "observed": {
                "feature_leakage_violation_count": summary[
                    "feature_leakage_violation_count"
                ]
            },
        },
        {
            "check_id": "final_selection_remains_blocked",
            "status": (
                "pass"
                if summary["can_support_final_method_selection"] is False
                and summary["final_selection_claim_status"] == "blocked"
                else "fail"
            ),
            "observed": {
                "can_support_final_method_selection": summary[
                    "can_support_final_method_selection"
                ],
                "final_selection_claim_status": summary[
                    "final_selection_claim_status"
                ],
                "paper_blocked_gate_count": summary["paper_blocked_gate_count"],
            },
        },
    ]
    return checks


def build_payload(root: Path) -> dict[str, Any]:
    paths = source_paths(root)
    manifest_schema = read_json(paths["manifest_schema"])
    selection_protocol = read_json(paths["selection_multiplicity_protocol"])
    validation_results = read_json(paths["method_selection_post_selection_validation_results"])
    candidate_audit = read_json(paths["method_selection_candidate_audit"])
    robustness_audit = read_json(paths["method_selection_robustness_audit"])
    paper_readiness = read_json(paths["paper_readiness_map"])
    final_selection = read_json(paths["final_selection_claim_boundary_audit"])
    publication_methodology = read_json(paths["publication_methodology_audit"])
    validation_summary = validation_results.get("summary") or {}
    candidate_summary = candidate_audit.get("summary") or {}
    robustness_summary = robustness_audit.get("summary") or {}
    paper_summary = paper_readiness.get("summary") or {}
    final_summary = final_selection.get("summary") or {}
    protocol_summary = selection_protocol.get("summary") or {}
    diagnostic_counts = validation_summary.get("diagnostic_winner_counts") or {}
    primary, primary_count, runner_up, runner_up_count = top_counts(diagnostic_counts)
    evidence = build_selection_multiplicity_evidence(
        manifest_schema,
        selection_protocol,
        validation_results,
        candidate_audit,
        robustness_audit,
        paper_readiness,
        final_selection,
        publication_methodology,
    )
    summary = {
        "overall_status": "selection_multiplicity_evidence_record_ready_no_final_selection",
        "claim_status": "diagnostic_primary_candidate_recorded_no_final_selection",
        "can_support_final_method_selection": False,
        "final_selection_claim_status": final_summary.get("claim_status"),
        "selection_protocol_status": protocol_summary.get("overall_status"),
        "validation_results_status": validation_summary.get("overall_status"),
        "validation_expected_atomic_rows": validation_summary.get(
            "expected_atomic_run_count"
        ),
        "validation_completed_atomic_rows": validation_summary.get(
            "completed_atomic_run_count"
        ),
        "validation_failed_check_count": validation_summary.get("failed_check_count"),
        "validation_common_cell_count": validation_summary.get(
            "common_dataset_alpha_cell_count"
        ),
        "diagnostic_primary_method": primary,
        "diagnostic_primary_win_count": primary_count,
        "diagnostic_runner_up_method": runner_up,
        "diagnostic_runner_up_win_count": runner_up_count,
        "diagnostic_primary_margin": primary_count - runner_up_count,
        "diagnostic_winner_counts": diagnostic_counts,
        "candidate_audit_primary_method": candidate_summary.get(
            "primary_candidate_method"
        ),
        "robustness_primary_method": robustness_summary.get(
            "common_cell_selected_method"
        ),
        "robustness_common_cell_count": robustness_summary.get(
            "common_dataset_alpha_cell_count"
        ),
        "pre_validation_completed_rows_scanned": candidate_summary.get(
            "source_completed_ledger_rows"
        ),
        "feature_leakage_violation_count": validation_summary.get(
            "feature_leakage_violation_count"
        ),
        "width_pathology_row_count": validation_summary.get(
            "width_pathology_row_count"
        ),
        "paper_readiness_status": paper_summary.get("overall_status"),
        "paper_blocked_gate_count": paper_summary.get("blocked_gate_count"),
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {key: rel(path, root) for key, path in paths.items()},
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": summary,
        "selection_multiplicity_evidence": evidence,
    }
    checks = build_checks(payload)
    failed_checks = [check for check in checks if check["status"] != "pass"]
    payload["checks"] = checks
    payload["failed_checks"] = failed_checks
    payload["summary"]["failed_check_count"] = len(failed_checks)
    if failed_checks:
        payload["summary"]["overall_status"] = (
            "selection_multiplicity_evidence_record_failed"
        )
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    evidence = payload["selection_multiplicity_evidence"]
    record = evidence["selection_records"][0]
    lines = [
        "# Selection Multiplicity Evidence Record",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Claim status: `{summary['claim_status']}`",
        f"- Diagnostic primary method: `{summary['diagnostic_primary_method']}` ({summary['diagnostic_primary_win_count']} cells)",
        f"- Runner-up: `{summary['diagnostic_runner_up_method']}` ({summary['diagnostic_runner_up_win_count']} cells)",
        f"- Diagnostic margin: {summary['diagnostic_primary_margin']}",
        f"- Validation atomic rows: {summary['validation_completed_atomic_rows']} / {summary['validation_expected_atomic_rows']}",
        f"- Validation common cells: {summary['validation_common_cell_count']}",
        f"- Pre-validation completed rows scanned: {summary['pre_validation_completed_rows_scanned']}",
        f"- Feature-leakage violations: {summary['feature_leakage_violation_count']}",
        f"- Width pathology rows retained: {summary['width_pathology_row_count']}",
        f"- Final selection allowed: `{summary['can_support_final_method_selection']}`",
        f"- Paper blocked gates: {summary['paper_blocked_gate_count']}",
        "",
        "This record does not promote a final winner.",
        "",
        "## Selection Record",
        "",
        f"- Record id: `{record['record_id']}`",
        f"- Record status: `{record['record_status']}`",
        f"- Diagnostic primary: `{record['diagnostic_primary_method']}`",
        f"- Candidate methods: `{record['candidate_methods']}`",
        f"- Final-selection eligible: `{record['final_selection_eligible']}`",
        f"- Blocking gates: `{record['blocking_gate_ids']}`",
        "",
        "## Required Field Evidence",
        "",
        "| Field | Status |",
        "| --- | --- |",
    ]
    for field in evidence["required_fields"]:
        field_status = evidence["field_record"][field]["status"]
        lines.append(f"| `{field}` | `{field_status}` |")
    lines.extend(["", "## Multiplicity Scope", ""])
    multiplicity = evidence["field_record"]["multiplicity_scope"]
    for key, value in multiplicity.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Checks", ""])
    lines.append("| check | status | observed |")
    lines.append("| --- | --- | --- |")
    for check in payload["checks"]:
        lines.append(
            f"| `{check['check_id']}` | `{check['status']}` | `{check.get('observed', {})}` |"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


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
                "diagnostic_primary_method": payload["summary"][
                    "diagnostic_primary_method"
                ],
                "diagnostic_primary_win_count": payload["summary"][
                    "diagnostic_primary_win_count"
                ],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if not payload["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
