"""Build a paper-gate closure map for claim-safe manuscript planning.

This artifact separates positive final-claim gates from negative, diagnostic,
or no-claim manuscript paths. It does not close paper gates or promote a final
winner; it records which blocked gates still require new positive evidence and
which already have a scoped manuscript disposition.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_paper_gate_closure_map_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/paper_gate_closure_map.json")
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
DATASET_FINAL_REMEDIATION = REPORT_DIR / "dataset_final_gate_remediation_plan.json"
DATASET_FINAL_GATE = REPORT_DIR / "dataset_specific_final_gate_audit.json"
PUBLICATION_METHODOLOGY = REPORT_DIR / "publication_methodology_audit.json"
FINAL_SELECTION = REPORT_DIR / "final_selection_claim_boundary_audit.json"
FAIRNESS_POPULATION = REPORT_DIR / "fairness_population_readiness_audit.json"
FAIRNESS_SAMPLING_WEIGHT_POLICY = Path(
    "experiments/regression/manuscript/fairness_sampling_weight_policy.json"
)
BOUNDED_SUPPORT_PROTOCOL = Path(
    "experiments/regression/manuscript/bounded_support_protocol.json"
)
BOUNDED_SUPPORT_DATASET_AUDIT = Path(
    "experiments/regression/manuscript/bounded_support_dataset_audit.json"
)
BOUNDED_SUPPORT_ENDPOINT_CLOSURE = (
    REPORT_DIR / "bounded_support_endpoint_closure_audit.json"
)
SELECTION_PROTOCOL = Path(
    "experiments/regression/manuscript/selection_multiplicity_protocol.json"
)
SELECTION_EVIDENCE = Path(
    "experiments/regression/manuscript/selection_multiplicity_evidence_record.json"
)
METHOD_SELECTION_CANDIDATE = REPORT_DIR / "method_selection_candidate_audit.json"
METHOD_SELECTION_ROBUSTNESS = REPORT_DIR / "method_selection_robustness_audit.json"
METHOD_SELECTION_INFERENTIAL = REPORT_DIR / "method_selection_inferential_audit.json"
METHOD_SELECTION_POST_SELECTION = (
    REPORT_DIR / "method_selection_post_selection_validation_results.json"
)
VENN_ABERS_VALIDATION = REPORT_DIR / "venn_abers_validation_readiness_audit.json"
VENN_ABERS_CLAIM_GATE = REPORT_DIR / "venn_abers_claim_gate_matrix.json"
VENN_ABERS_NEGATIVE_DISPOSITION = (
    REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
)
VENN_ABERS_FAILURE_MODES = (
    REPORT_DIR / "venn_abers_grid_failure_mode_decomposition.json"
)


GATE_SOURCE_ARTIFACTS: dict[str, list[Path]] = {
    "dataset_specific_final_gates": [
        PAPER_READINESS,
        DATASET_FINAL_REMEDIATION,
        DATASET_FINAL_GATE,
        PUBLICATION_METHODOLOGY,
    ],
    "endpoint_bounded_support_gate": [
        PAPER_READINESS,
        BOUNDED_SUPPORT_PROTOCOL,
        BOUNDED_SUPPORT_DATASET_AUDIT,
        BOUNDED_SUPPORT_ENDPOINT_CLOSURE,
        PUBLICATION_METHODOLOGY,
    ],
    "fairness_population_inference_gate": [
        PAPER_READINESS,
        FAIRNESS_POPULATION,
        FAIRNESS_SAMPLING_WEIGHT_POLICY,
        FINAL_SELECTION,
        PUBLICATION_METHODOLOGY,
    ],
    "final_method_model_selection_gate": [
        PAPER_READINESS,
        FINAL_SELECTION,
        SELECTION_PROTOCOL,
        SELECTION_EVIDENCE,
        METHOD_SELECTION_CANDIDATE,
        METHOD_SELECTION_ROBUSTNESS,
        METHOD_SELECTION_INFERENTIAL,
        METHOD_SELECTION_POST_SELECTION,
    ],
    "multiplicity_selection_record": [
        PAPER_READINESS,
        SELECTION_PROTOCOL,
        SELECTION_EVIDENCE,
        METHOD_SELECTION_CANDIDATE,
        METHOD_SELECTION_INFERENTIAL,
        METHOD_SELECTION_POST_SELECTION,
        PUBLICATION_METHODOLOGY,
    ],
    "venn_abers_regression_validation_gate": [
        PAPER_READINESS,
        VENN_ABERS_VALIDATION,
        VENN_ABERS_CLAIM_GATE,
        VENN_ABERS_NEGATIVE_DISPOSITION,
        VENN_ABERS_FAILURE_MODES,
        FINAL_SELECTION,
    ],
}

GATE_DEPENDENCIES: dict[str, list[str]] = {
    "dataset_specific_final_gates": [
        "endpoint_bounded_support_gate",
        "fairness_population_inference_gate",
        "final_method_model_selection_gate",
        "multiplicity_selection_record",
    ],
    "final_method_model_selection_gate": [
        "dataset_specific_final_gates",
        "multiplicity_selection_record",
    ],
    "multiplicity_selection_record": ["final_method_model_selection_gate"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("summary") or {}


def status_is_ready(value: Any) -> bool:
    text = str(value or "").lower()
    return any(token in text for token in ("ready", "pass", "completed"))


def status_is_blocked(value: Any) -> bool:
    return "blocked" in str(value or "").lower()


def venn_abers_negative_result_ready(row: dict[str, Any]) -> bool:
    return (
        row.get("gate_id") == "venn_abers_regression_validation_gate"
        and bool(row.get("scoped_or_negative_path_ready"))
        and (row.get("metrics") or {}).get("negative_result_reporting_ready") is True
        and (row.get("metrics") or {}).get(
            "current_manuscript_positive_validation_required"
        )
        is False
    )


def selection_protocol_defined(value: Any) -> bool:
    text = str(value or "").lower()
    return status_is_ready(text) or "protocol_defined" in text or "defined" in text


def source_paths(gate_id: str, root: Path) -> list[str]:
    paths = GATE_SOURCE_ARTIFACTS.get(gate_id, [PAPER_READINESS])
    return [rel(root / path, root) for path in paths if (root / path).exists()]


def gate_lookup(paper_readiness: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("gate_id")): row
        for row in paper_readiness.get("blocked_gates", []) or []
        if isinstance(row, dict) and row.get("gate_id")
    }


def build_gate_row(
    gate_id: str,
    current_status: str,
    root: Path,
    facts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    dataset_plan = facts["dataset_plan"]
    dataset_gate = facts["dataset_gate"]
    final_selection = facts["final_selection"]
    fairness = facts["fairness"]
    fairness_sampling_policy = facts["fairness_sampling_policy"]
    bounded_protocol = facts["bounded_protocol"]
    bounded_dataset = facts["bounded_dataset"]
    bounded_closure = facts["bounded_closure"]
    selection_protocol = facts["selection_protocol"]
    selection_evidence = facts["selection_evidence"]
    method_candidate = facts["method_candidate"]
    method_robustness = facts["method_robustness"]
    method_inferential = facts["method_inferential"]
    method_post_selection = facts["method_post_selection"]
    venn_validation = facts["venn_validation"]
    venn_claim_gate = facts["venn_claim_gate"]
    venn_negative = facts["venn_negative"]
    venn_failure = facts["venn_failure"]

    base = {
        "gate_id": gate_id,
        "current_status": current_status,
        "dependency_gate_ids": GATE_DEPENDENCIES.get(gate_id, []),
        "source_artifacts": source_paths(gate_id, root),
        "positive_claim_ready": False,
        "scoped_or_negative_path_ready": False,
        "local_execution_gap_remaining": False,
        "closure_mode": "positive_evidence_required",
        "paper_allowed_language": [],
        "paper_disallowed_language": [],
        "next_decision": "",
        "metrics": {},
    }

    if gate_id == "dataset_specific_final_gates":
        local_actions = int(
            dataset_plan.get("local_dataset_remediation_action_count") or 0
        )
        no_gap_datasets = int(
            dataset_plan.get("dataset_with_no_remaining_execution_gap_count") or 0
        )
        dataset_count = int(dataset_plan.get("dataset_count") or 0)
        base.update(
            {
                "gate_class": "dataset_promotion_gate",
                "local_execution_gap_remaining": local_actions > 0,
                "closure_mode": "global_claim_gate_dependencies_then_refresh",
                "scoped_or_negative_path_ready": local_actions == 0,
                "paper_allowed_language": [
                    "completed candidate bundles may be described as diagnostic or caveated evidence",
                    "dataset-specific final-result promotion remains withheld",
                ],
                "paper_disallowed_language": [
                    "publication-ready dataset final result",
                    "final main-table dataset promotion",
                ],
                "next_decision": (
                    "Resolve global bounded-support, fairness/population, "
                    "method-selection, and multiplicity gates before refreshing "
                    "dataset-specific promotion."
                ),
                "metrics": {
                    "dataset_count": dataset_count,
                    "dataset_with_no_remaining_execution_gap_count": no_gap_datasets,
                    "local_dataset_remediation_action_count": local_actions,
                    "ready_dataset_count": int(dataset_plan.get("ready_dataset_count") or 0),
                    "main_result_ready_dataset_count": int(
                        dataset_gate.get("main_result_ready_dataset_count") or 0
                    ),
                },
            }
        )
    elif gate_id == "endpoint_bounded_support_gate":
        posthandling_ready = (
            int(bounded_dataset.get("bounded_support_posthandling_unvalidated_bundle_count") or 0)
            == 0
        )
        policy_closed = (
            int(bounded_closure.get("open_count_backfill_bundle_count") or 0) == 0
            and int(bounded_closure.get("dataset_open_endpoint_count_backfill_count") or 0)
            == 0
        )
        no_claim_count = int(
            bounded_closure.get("global_no_claim_bundle_count")
            or bounded_dataset.get("bounded_support_global_no_claim_bundle_count")
            or 0
        )
        base.update(
            {
                "gate_class": "bounded_support_positive_validity_gate",
                "closure_mode": "no_bounded_support_claim_path_or_new_validity_evidence",
                "scoped_or_negative_path_ready": posthandling_ready and policy_closed,
                "paper_allowed_language": [
                    "raw endpoint hygiene and post-handling validation may be reported",
                    "bounded-support validity remains explicitly out of scope",
                ],
                "paper_disallowed_language": [
                    "bounded-support validity",
                    "target-domain-valid clipped intervals",
                ],
                "next_decision": (
                    "Keep no bounded-support validity claim, or run a separate "
                    "validity protocol with target-domain policy before using "
                    "bounded-support language."
                ),
                "metrics": {
                    "can_support_bounded_support_validity": bool(
                        bounded_protocol.get("can_support_bounded_support_validity")
                    ),
                    "posthandling_ready": posthandling_ready,
                    "endpoint_policy_closed": policy_closed,
                    "global_no_claim_bundle_count": no_claim_count,
                    "endpoint_blocked_or_incomplete_bundle_count": int(
                        bounded_dataset.get(
                            "bounded_support_dataset_endpoint_blocked_or_incomplete_bundle_count"
                        )
                        or bounded_dataset.get(
                            "endpoint_support_blocked_or_incomplete_bundle_count"
                        )
                        or 0
                    ),
                },
            }
        )
    elif gate_id == "fairness_population_inference_gate":
        diagnostic_count = int(fairness.get("diagnostic_group_bundle_count") or 0)
        ready_count = int(fairness.get("population_fairness_ready_bundle_count") or 0)
        base.update(
            {
                "gate_class": "fairness_population_positive_inference_gate",
                "closure_mode": "diagnostic_group_path_or_new_population_estimand",
                "scoped_or_negative_path_ready": diagnostic_count > 0 and ready_count == 0,
                "paper_allowed_language": [
                    "diagnostic group coverage summaries",
                    "no protected-class, policy, legal, or population inference claim",
                ],
                "paper_disallowed_language": [
                    "fairness conclusion",
                    "population-level protected-group effect",
                ],
                "next_decision": (
                    "Either keep group results diagnostic, or define population, "
                    "protected attribute scope, estimand, and weighting policy."
                ),
                "metrics": {
                    "diagnostic_group_bundle_count": diagnostic_count,
                    "population_fairness_ready_bundle_count": ready_count,
                    "sampling_weight_policy_status": fairness_sampling_policy.get(
                        "overall_status"
                    ),
                    "sampling_weight_policy_declared_bundle_count": (
                        fairness_sampling_policy.get("policy_declared_bundle_count")
                    ),
                    "weighted_estimand_applied_bundle_count": (
                        fairness_sampling_policy.get(
                            "weighted_estimand_applied_bundle_count"
                        )
                    ),
                    "can_support_publication_ready_fairness": bool(
                        fairness.get("can_support_publication_ready_fairness")
                    ),
                },
            }
        )
    elif gate_id == "final_method_model_selection_gate":
        post_rows = int(method_post_selection.get("completed_atomic_run_count") or 0)
        expected_rows = int(method_post_selection.get("expected_atomic_run_count") or 0)
        base.update(
            {
                "gate_class": "final_winner_selection_gate",
                "closure_mode": "diagnostic_primary_candidate_path_or_final_selection_protocol",
                "scoped_or_negative_path_ready": (
                    status_is_ready(method_candidate.get("overall_status"))
                    and status_is_ready(method_robustness.get("overall_status"))
                    and status_is_ready(method_inferential.get("overall_status"))
                    and post_rows == expected_rows
                    and post_rows > 0
                ),
                "paper_allowed_language": [
                    "CQR may be described as diagnostic primary candidate under blocked final-selection scope",
                    "post-selection validation remains diagnostic evidence",
                ],
                "paper_disallowed_language": [
                    "global best conformal method",
                    "final selected model or method",
                ],
                "next_decision": (
                    "Apply final selection only after dataset, endpoint, "
                    "fairness/population, and multiplicity gates are compatible "
                    "with the intended claim."
                ),
                "metrics": {
                    "final_selection_claim_status": final_selection.get("claim_status"),
                    "primary_candidate_method": method_candidate.get(
                        "primary_candidate_method"
                    )
                    or method_inferential.get("primary_candidate_method"),
                    "post_selection_completed_atomic_run_count": post_rows,
                    "post_selection_expected_atomic_run_count": expected_rows,
                    "robustness_common_cell_primary_win_rate": method_robustness.get(
                        "common_cell_primary_win_count"
                    ),
                    "inferential_bootstrap_primary_selection_rate": method_inferential.get(
                        "bootstrap_primary_selection_rate"
                    ),
                },
            }
        )
    elif gate_id == "multiplicity_selection_record":
        base.update(
            {
                "gate_class": "selection_search_accounting_gate",
                "closure_mode": "diagnostic_multiplicity_record_ready_no_final_winner",
                "scoped_or_negative_path_ready": (
                    selection_protocol_defined(selection_protocol.get("overall_status"))
                    and status_is_ready(selection_evidence.get("overall_status"))
                ),
                "paper_allowed_language": [
                    "searched row counts, candidate scope, and diagnostic ranking may be reported",
                    "selection multiplicity must be cited wherever candidate language appears",
                ],
                "paper_disallowed_language": [
                    "post-hoc best method without searched-space accounting",
                    "winner language without final-selection gate closure",
                ],
                "next_decision": (
                    "Keep recommendation language diagnostic until the final "
                    "selection gate can consume the multiplicity record."
                ),
                "metrics": {
                    "selection_protocol_status": selection_protocol.get("overall_status"),
                    "selection_evidence_status": selection_evidence.get("overall_status"),
                    "validation_completed_atomic_rows": selection_evidence.get(
                        "validation_completed_atomic_rows"
                    ),
                    "validation_expected_atomic_rows": selection_evidence.get(
                        "validation_expected_atomic_rows"
                    ),
                },
            }
        )
    elif gate_id == "venn_abers_regression_validation_gate":
        negative_present = bool(venn_negative.get("negative_claim_present"))
        negative_reporting_ready = (
            venn_negative.get("negative_result_reporting_ready") is True
            or (
                status_is_ready(venn_negative.get("overall_status"))
                and negative_present
            )
        )
        positive_required = not negative_reporting_ready
        positive_blocked = int(venn_claim_gate.get("positive_claim_blocked_count") or 0)
        grid_scored = int(
            venn_failure.get("total_grid_reference_rows_scored")
            or venn_claim_gate.get("total_grid_reference_rows_scored")
            or 0
        )
        base.update(
            {
                "gate_class": "venn_abers_positive_validation_gate",
                "closure_mode": "negative_result_disposition_or_new_validated_method",
                "scoped_or_negative_path_ready": (
                    negative_present
                    and positive_blocked > 0
                    and negative_reporting_ready
                ),
                "paper_allowed_language": [
                    "fast Venn-Abers bridge is negative/failure-mode evidence",
                    "split fallback is ordinary split conformal fallback evidence",
                    "positive Venn-Abers validation is optional future work, not required for the current manuscript",
                ],
                "paper_disallowed_language": [
                    "validated Venn-Abers regression interval coverage",
                    "Venn-Abers final winner",
                ],
                "next_decision": (
                    "Report the observed negative result under explicit "
                    "no-validation language; design a separate validated "
                    "Venn-Abers regression method only as optional future work."
                ),
                "metrics": {
                    "validation_status": venn_validation.get("overall_status"),
                    "negative_claim_present": negative_present,
                    "negative_result_reporting_ready": negative_reporting_ready,
                    "current_manuscript_positive_validation_required": (
                        positive_required
                    ),
                    "manuscript_disposition_status": venn_negative.get(
                        "manuscript_disposition_status"
                    ),
                    "positive_claim_blocked_count": positive_blocked,
                    "positive_claim_pass_count": int(
                        venn_claim_gate.get("positive_claim_pass_count") or 0
                    ),
                    "grid_reference_rows_scored": grid_scored,
                    "validation_blocker_ids": venn_claim_gate.get(
                        "blocked_positive_requirement_ids"
                    )
                    or venn_failure.get("validation_blocker_ids")
                    or [],
                },
            }
        )
    else:
        base.update(
            {
                "gate_class": "unclassified_gate",
                "next_decision": "Add this gate to the closure-map taxonomy.",
            }
        )

    return base


def build_payload(root: Path) -> dict[str, Any]:
    paper_readiness = read_json(root / PAPER_READINESS)
    publication = read_json(root / PUBLICATION_METHODOLOGY)
    gate_rows_by_id = gate_lookup(paper_readiness)
    requirement_statuses = publication.get("requirement_statuses") or {}
    gate_ids = sorted(
        {
            *gate_rows_by_id.keys(),
            *[
                str(key)
                for key in requirement_statuses
                if key != "remediation_backlog_closed_or_scoped"
            ],
        }
    )

    facts = {
        "dataset_plan": summary(read_json(root / DATASET_FINAL_REMEDIATION)),
        "dataset_gate": summary(read_json(root / DATASET_FINAL_GATE)),
        "final_selection": summary(read_json(root / FINAL_SELECTION)),
        "fairness": summary(read_json(root / FAIRNESS_POPULATION)),
        "fairness_sampling_policy": summary(
            read_json(root / FAIRNESS_SAMPLING_WEIGHT_POLICY)
        ),
        "bounded_protocol": summary(read_json(root / BOUNDED_SUPPORT_PROTOCOL)),
        "bounded_dataset": summary(read_json(root / BOUNDED_SUPPORT_DATASET_AUDIT)),
        "bounded_closure": summary(read_json(root / BOUNDED_SUPPORT_ENDPOINT_CLOSURE)),
        "selection_protocol": summary(read_json(root / SELECTION_PROTOCOL)),
        "selection_evidence": summary(read_json(root / SELECTION_EVIDENCE)),
        "method_candidate": summary(read_json(root / METHOD_SELECTION_CANDIDATE)),
        "method_robustness": summary(read_json(root / METHOD_SELECTION_ROBUSTNESS)),
        "method_inferential": summary(read_json(root / METHOD_SELECTION_INFERENTIAL)),
        "method_post_selection": summary(read_json(root / METHOD_SELECTION_POST_SELECTION)),
        "venn_validation": summary(read_json(root / VENN_ABERS_VALIDATION)),
        "venn_claim_gate": summary(read_json(root / VENN_ABERS_CLAIM_GATE)),
        "venn_negative": summary(read_json(root / VENN_ABERS_NEGATIVE_DISPOSITION)),
        "venn_failure": summary(read_json(root / VENN_ABERS_FAILURE_MODES)),
    }

    rows = [
        build_gate_row(
            gate_id,
            str(requirement_statuses.get(gate_id) or gate_rows_by_id.get(gate_id, {}).get("status") or "unknown"),
            root,
            facts,
        )
        for gate_id in gate_ids
    ]
    blocked_rows = [row for row in rows if status_is_blocked(row["current_status"])]
    current_paper_blocking_rows = [
        row
        for row in blocked_rows
        if not venn_abers_negative_result_ready(row)
    ]
    class_counts = Counter(row["gate_class"] for row in rows)
    closure_mode_counts = Counter(row["closure_mode"] for row in rows)
    positive_ready_count = sum(1 for row in rows if row["positive_claim_ready"])
    scoped_ready_count = sum(1 for row in rows if row["scoped_or_negative_path_ready"])
    local_gap_count = sum(1 for row in rows if row["local_execution_gap_remaining"])
    disallowed_language_count = sum(
        len(row["paper_disallowed_language"]) for row in rows
    )

    failed_checks: list[dict[str, Any]] = []
    if any(
        row["positive_claim_ready"] and status_is_blocked(row["current_status"])
        for row in rows
    ):
        failed_checks.append(
            {
                "check_id": "blocked_gates_do_not_promote_positive_claims",
                "status": "fail",
            }
        )
    if "venn_abers_regression_validation_gate" in gate_ids:
        venn_row = next(
            row for row in rows if row["gate_id"] == "venn_abers_regression_validation_gate"
        )
        if not venn_row["scoped_or_negative_path_ready"]:
            failed_checks.append(
                {
                    "check_id": "venn_abers_negative_disposition_path_recorded",
                    "status": "fail",
                }
            )

    overall_status = (
        "paper_gate_closure_map_failed"
        if failed_checks
        else "paper_gate_closure_map_ready_no_promotions"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "paper_readiness_status": summary(paper_readiness).get("overall_status"),
            "gate_count": len(rows),
            "blocked_gate_count": len(blocked_rows),
            "current_paper_blocking_gate_count": len(current_paper_blocking_rows),
            "positive_claim_ready_gate_count": positive_ready_count,
            "scoped_or_negative_path_ready_gate_count": scoped_ready_count,
            "local_execution_gap_gate_count": local_gap_count,
            "class_counts": dict(sorted(class_counts.items())),
            "closure_mode_counts": dict(sorted(closure_mode_counts.items())),
            "can_start_post_experiment_publication": (
                len(current_paper_blocking_rows) == 0
            ),
            "can_extract_negative_results_table": any(
                row["gate_id"] == "venn_abers_regression_validation_gate"
                and row["scoped_or_negative_path_ready"]
                for row in rows
            ),
            "venn_abers_negative_result_reporting_ready": any(
                venn_abers_negative_result_ready(row) for row in rows
            ),
            "positive_venn_abers_validation_forcing_required": not any(
                venn_abers_negative_result_ready(row) for row in rows
            ),
            "dataset_final_local_remediation_action_count": int(
                facts["dataset_plan"].get("local_dataset_remediation_action_count") or 0
            ),
            "dataset_with_no_remaining_execution_gap_count": int(
                facts["dataset_plan"].get("dataset_with_no_remaining_execution_gap_count")
                or 0
            ),
            "disallowed_language_item_count": disallowed_language_count,
            "failed_check_count": len(failed_checks),
        },
        "claim_boundaries": [
            "This map does not close any blocked paper gate.",
            "A scoped or negative path means claim-safe prose can be drafted only inside the stated limits.",
            "Positive winner, fairness, bounded-support-validity, and validated Venn-Abers claims remain blocked until their dedicated gates pass.",
            "A clean Venn-Abers negative-result disposition means positive Venn-Abers validation is optional future work, not a current-manuscript requirement.",
        ],
        "failed_checks": failed_checks,
        "gate_rows": rows,
        "sources": {
            "paper_readiness_map": rel(root / PAPER_READINESS, root),
            "publication_methodology_audit": rel(root / PUBLICATION_METHODOLOGY, root),
            "dataset_final_gate_remediation_plan": rel(
                root / DATASET_FINAL_REMEDIATION, root
            ),
            "venn_abers_negative_evidence_disposition": rel(
                root / VENN_ABERS_NEGATIVE_DISPOSITION, root
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Paper Gate Closure Map",
        "",
        "This is a claim-control artifact. It does not promote final paper claims.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Paper readiness status: `{summary_payload['paper_readiness_status']}`",
        f"- Blocked gates: {summary_payload['blocked_gate_count']} / {summary_payload['gate_count']}",
        f"- Current-paper blocking gates: {summary_payload['current_paper_blocking_gate_count']}",
        f"- Scoped or negative paths ready: {summary_payload['scoped_or_negative_path_ready_gate_count']}",
        f"- Positive-claim-ready gates: {summary_payload['positive_claim_ready_gate_count']}",
        f"- Local execution-gap gates: {summary_payload['local_execution_gap_gate_count']}",
        f"- Can start post-experiment publication: `{summary_payload['can_start_post_experiment_publication']}`",
        f"- Can extract negative-results table: `{summary_payload['can_extract_negative_results_table']}`",
        f"- Venn-Abers negative result reporting ready: `{summary_payload['venn_abers_negative_result_reporting_ready']}`",
        f"- Positive Venn-Abers validation forcing required: `{summary_payload['positive_venn_abers_validation_forcing_required']}`",
        "",
        "## Gate Rows",
        "",
        "| Gate | Class | Status | Positive Claim Ready | Scoped/Negative Path Ready | Closure Mode |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in payload["gate_rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['gate_id']}`",
                    f"`{row['gate_class']}`",
                    f"`{row['current_status']}`",
                    f"`{row['positive_claim_ready']}`",
                    f"`{row['scoped_or_negative_path_ready']}`",
                    f"`{row['closure_mode']}`",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(["", "## Next Decisions", ""])
    for row in payload["gate_rows"]:
        lines.append(f"- `{row['gate_id']}`: {row['next_decision']}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))


if __name__ == "__main__":
    main()
