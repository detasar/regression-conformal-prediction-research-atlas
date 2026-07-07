"""Build an actionable remediation plan for dataset-specific final gates.

This joins the final-gate audit with main-result candidate planning, executed
candidate results, post-run closure, and post-selection validation evidence.
It is a work plan only: it must not promote a dataset, model, method, or
manuscript claim while paper gates remain blocked.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_dataset_final_gate_remediation_plan_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "dataset_final_gate_remediation_plan.json"

DATASET_FINAL_GATE = REPORT_DIR / "dataset_specific_final_gate_audit.json"
MAIN_RESULT_CANDIDATE_BUNDLE_PLAN = (
    REPORT_DIR / "main_result_candidate_bundle_plan.json"
)
MAIN_RESULT_CANDIDATE_BUNDLE_RESULTS = (
    REPORT_DIR / "main_result_candidate_bundle_results.json"
)
MAIN_RESULT_CANDIDATE_POST_RUN_CLOSURE = (
    REPORT_DIR / "main_result_candidate_post_run_closure_audit.json"
)
METHOD_SELECTION_POST_SELECTION_VALIDATION_RESULTS = (
    REPORT_DIR / "method_selection_post_selection_validation_results.json"
)
DATASET_FINAL_GATE_POST_SELECTION_VALIDATION_BRIDGE = (
    REPORT_DIR / "dataset_final_gate_post_selection_validation_bridge.json"
)
DATASET_FINAL_GATE_POST_SELECTION_VALIDATION_BRIDGE_RESULTS = (
    REPORT_DIR / "dataset_final_gate_post_selection_validation_bridge_results.json"
)
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
BOUNDED_SUPPORT_DATASET_AUDIT = Path(
    "experiments/regression/manuscript/bounded_support_dataset_audit.json"
)
BOUNDED_SUPPORT_ENDPOINT_CLOSURE_AUDIT = (
    REPORT_DIR / "bounded_support_endpoint_closure_audit.json"
)

GLOBAL_GATE_ACTIONS = {
    "fairness_population_claim_not_ready": "resolve_fairness_population_inference_gate",
    "final_selection_claim_blocked": "resolve_final_method_model_selection_gate",
    "main_results_surface_blocked": "refresh_paper_readiness_after_gate_closure",
}

CLAIM_BOUNDARIES = [
    "This plan records executable remediation steps; it does not promote final main-result evidence.",
    "A completed main-result candidate bundle remains diagnostic until all paper gates pass.",
    "Datasets without post-selection validation evidence must not be inserted directly into main-result candidate bundles.",
    "Final method/model selection, bounded-support validity, fairness/population inference, and Venn-Abers validation remain outside this plan's promotion scope.",
]

LOCAL_DATASET_ACTIONS = {
    "add_dataset_to_main_result_candidate_bundle_plan",
    "build_candidate_post_run_closure_audit",
    "build_post_selection_validation_bridge",
    "complete_bounded_support_dataset_audit_trace",
    "execute_main_result_candidate_bundle",
    "execute_post_selection_validation_bridge",
    "backfill_unknown_natural_endpoint_excursion_count",
    "resolve_candidate_post_run_closure_blockers",
    "resolve_natural_domain_endpoint_support_blockers",
    "resume_incomplete_main_result_candidate_bundle",
}

GLOBAL_GATE_ACTIONS_SCOPE = {
    "resolve_bounded_support_validity_claim_gate",
    "resolve_fairness_population_inference_gate",
    "resolve_final_method_model_selection_gate",
    "resolve_global_bounded_support_validity_claim_gate",
}

POST_CLOSURE_REFRESH_ACTIONS = {
    "refresh_paper_readiness_after_gate_closure",
    "regenerate_dataset_final_gate_after_global_gate_closure",
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
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rows_by_dataset(
    payload: dict[str, Any], key: str = "dataset_rows"
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in payload.get(key) or []:
        if isinstance(row, dict) and row.get("dataset_id"):
            rows[str(row["dataset_id"])] = row
    return rows


def row_lists_by_dataset(
    payload: dict[str, Any], key: str = "rows"
) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    for row in payload.get(key) or []:
        if not isinstance(row, dict):
            continue
        dataset_ids = [row.get("dataset_id"), row.get("paired_dataset_id")]
        for dataset_id in dataset_ids:
            if dataset_id:
                rows.setdefault(str(dataset_id), []).append(row)
    return rows


def endpoint_closure_open_backfill(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    if row.get("endpoint_closure_status") == "open_endpoint_count_backfill_required":
        return True
    counts = row.get("endpoint_closure_status_counts") or {}
    return int(counts.get("open_endpoint_excursion_count_backfill_required") or 0) > 0


def endpoint_closure_policy_closed(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    return not endpoint_closure_open_backfill(row)


def bounded_support_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    endpoint_counts = Counter(
        str(row.get("endpoint_support_status")) for row in rows
    )
    posthandling_counts = Counter(
        str(row.get("posthandling_support_status")) for row in rows
    )
    blocker_counts = Counter(
        str(blocker)
        for row in rows
        for blocker in row.get("blockers", []) or []
    )
    endpoint_blocked_or_incomplete = sum(
        count
        for status, count in endpoint_counts.items()
        if status.startswith("blocked_") or status.startswith("incomplete_")
    )
    endpoint_clean = endpoint_counts.get(
        "clean_no_natural_domain_endpoint_excursions", 0
    )
    endpoint_not_applicable = endpoint_counts.get(
        "not_applicable_unbounded_target_endpoint_hygiene_recorded", 0
    )
    return {
        "bundle_count": len(rows),
        "endpoint_support_status_counts": dict(sorted(endpoint_counts.items())),
        "posthandling_support_status_counts": dict(sorted(posthandling_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "endpoint_support_clean_bundle_count": endpoint_clean,
        "endpoint_support_not_applicable_bundle_count": endpoint_not_applicable,
        "endpoint_support_blocked_or_incomplete_bundle_count": (
            endpoint_blocked_or_incomplete
        ),
        "global_no_claim_bundle_count": blocker_counts.get(
            "global_bounded_support_validity_claim_disabled", 0
        ),
    }


def blocked_gate_ids(paper_readiness: dict[str, Any]) -> list[str]:
    gates = [
        str(row.get("gate_id"))
        for row in paper_readiness.get("blocked_gates") or []
        if isinstance(row, dict) and row.get("gate_id")
    ]
    if gates:
        return gates
    summary = paper_readiness.get("summary") or {}
    if int(summary.get("blocked_gate_count") or 0) <= 0:
        return []
    return [
        "dataset_specific_final_gates",
        "endpoint_bounded_support_gate",
        "fairness_population_inference_gate",
        "final_method_model_selection_gate",
        "multiplicity_selection_record",
        "venn_abers_regression_validation_gate",
    ]


def action_scope(action_id: str) -> str:
    if action_id in LOCAL_DATASET_ACTIONS:
        return "local_dataset_remediation"
    if action_id in GLOBAL_GATE_ACTIONS_SCOPE:
        return "global_gate_dependency"
    if action_id in POST_CLOSURE_REFRESH_ACTIONS:
        return "post_closure_refresh"
    return "uncategorized"


def action(action_id: str, rationale: str, source_artifacts: list[str]) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "action_scope": action_scope(action_id),
        "status": "required",
        "rationale": rationale,
        "source_artifacts": source_artifacts,
    }


def dataset_actions(
    *,
    dataset_id: str,
    final_row: dict[str, Any],
    validation_row: dict[str, Any] | None,
    validation_bridge_row: dict[str, Any] | None,
    plan_row: dict[str, Any] | None,
    result_row: dict[str, Any] | None,
    closure_row: dict[str, Any] | None,
    bounded_support_rows: list[dict[str, Any]],
    bounded_support_endpoint_closure_row: dict[str, Any] | None,
    global_blocked_gates: list[str],
    sources: dict[str, str],
) -> tuple[str, list[dict[str, Any]], str]:
    actions: list[dict[str, Any]] = []
    blocker_counts = final_row.get("blocking_reason_counts") or {}
    bounded_summary = bounded_support_summary(bounded_support_rows)

    if validation_row is None:
        if validation_bridge_row is None:
            actions.append(
                action(
                    "build_post_selection_validation_bridge",
                    (
                        "Dataset appears in the final-gate audit but has no "
                        "post-selection validation row, so it cannot be promoted "
                        "into a main-result candidate bundle without a validation bridge."
                    ),
                    [
                        sources["dataset_specific_final_gate_audit"],
                        sources[
                            "method_selection_post_selection_validation_results"
                        ],
                    ],
                )
            )
        else:
            actions.append(
                action(
                    "execute_post_selection_validation_bridge",
                    (
                        "Dataset has a generated post-selection validation "
                        "bridge config, but the bridge has not yet produced a "
                        "completed post-selection validation result row."
                    ),
                    [
                        sources[
                            "dataset_final_gate_post_selection_validation_bridge"
                        ],
                        sources[
                            "method_selection_post_selection_validation_results"
                        ],
                    ],
                )
            )
    if plan_row is None:
        actions.append(
            action(
                "add_dataset_to_main_result_candidate_bundle_plan",
                (
                    "Dataset has no fresh-seed main-result candidate config in "
                    "the current plan."
                ),
                [
                    sources["dataset_specific_final_gate_audit"],
                    sources["main_result_candidate_bundle_plan"],
                ],
            )
        )
    if plan_row is not None and result_row is None:
        actions.append(
            action(
                "execute_main_result_candidate_bundle",
                (
                    "Dataset has a candidate config but no completed candidate "
                    "result row."
                ),
                [
                    sources["main_result_candidate_bundle_plan"],
                    sources["main_result_candidate_bundle_results"],
                ],
            )
        )
    if result_row is not None:
        completed = int(result_row.get("completed_atomic_run_count") or 0)
        expected = int(result_row.get("expected_atomic_run_count") or 0)
        if expected and completed < expected:
            actions.append(
                action(
                    "resume_incomplete_main_result_candidate_bundle",
                    (
                        f"Candidate result row is incomplete: {completed} / "
                        f"{expected} atomic runs completed."
                    ),
                    [sources["main_result_candidate_bundle_results"]],
                )
            )
    if plan_row is not None and closure_row is None:
        actions.append(
            action(
                "build_candidate_post_run_closure_audit",
                "Dataset has a candidate plan row but no post-run closure row.",
                [
                    sources["main_result_candidate_bundle_plan"],
                    sources["main_result_candidate_post_run_closure_audit"],
                ],
            )
        )
    if closure_row is not None and int(closure_row.get("blocker_count") or 0) > 0:
        actions.append(
            action(
                "resolve_candidate_post_run_closure_blockers",
                (
                    "Candidate post-run closure audit has blockers that must "
                    "be cleared before dataset-specific final-gate re-evaluation."
                ),
                [sources["main_result_candidate_post_run_closure_audit"]],
            )
        )

    bounded_support_blocker_count = int(
        blocker_counts.get("bounded_support_validity_not_supported") or 0
    )
    if bounded_support_blocker_count > 0:
        endpoint_blocked = int(
            bounded_summary.get("endpoint_support_blocked_or_incomplete_bundle_count")
            or 0
        )
        global_no_claim = int(bounded_summary.get("global_no_claim_bundle_count") or 0)
        endpoint_policy_closed = endpoint_closure_policy_closed(
            bounded_support_endpoint_closure_row
        )
        endpoint_backfill_open = endpoint_closure_open_backfill(
            bounded_support_endpoint_closure_row
        )
        if not bounded_support_rows:
            actions.append(
                action(
                    "complete_bounded_support_dataset_audit_trace",
                    (
                        "Final-gate audit reports bounded-support blockers, but "
                        "the dataset has no matching row in the bounded-support "
                        "dataset audit."
                    ),
                    [
                        sources["dataset_specific_final_gate_audit"],
                        sources["bounded_support_dataset_audit"],
                    ],
                )
            )
        if endpoint_blocked > 0:
            if endpoint_backfill_open:
                actions.append(
                    action(
                        "backfill_unknown_natural_endpoint_excursion_count",
                        (
                            "Endpoint-closure audit reports open natural-domain "
                            f"endpoint-count backfill for `{dataset_id}`; exact "
                            "excursion counts are required before endpoint-policy "
                            "triage can be considered closed."
                        ),
                        [
                            sources["dataset_specific_final_gate_audit"],
                            sources["bounded_support_dataset_audit"],
                            sources["bounded_support_endpoint_closure_audit"],
                            sources["paper_readiness_map"],
                        ],
                    )
                )
            elif not endpoint_policy_closed:
                actions.append(
                    action(
                        "resolve_natural_domain_endpoint_support_blockers",
                        (
                            "Bounded-support dataset audit reports "
                            f"{endpoint_blocked} endpoint blocked/incomplete "
                            f"bundle(s) for `{dataset_id}`, but no endpoint-closure "
                            "row proves whether this is measured raw excursion "
                            "evidence or a remaining endpoint-count backfill gap."
                        ),
                        [
                            sources["dataset_specific_final_gate_audit"],
                            sources["bounded_support_dataset_audit"],
                            sources["bounded_support_endpoint_closure_audit"],
                            sources["paper_readiness_map"],
                        ],
                    )
                )
        if global_no_claim > 0:
            actions.append(
                action(
                    "resolve_global_bounded_support_validity_claim_gate",
                    (
                        "Bounded-support dataset audit reports "
                        f"{global_no_claim} bundle(s) for `{dataset_id}` still "
                        "under the global no-bounded-support-validity-claim boundary."
                    ),
                    [
                        sources["dataset_specific_final_gate_audit"],
                        sources["bounded_support_dataset_audit"],
                        sources["bounded_support_endpoint_closure_audit"],
                        sources["paper_readiness_map"],
                    ],
                )
            )
        if not any(
            item["action_id"]
            in {
                "complete_bounded_support_dataset_audit_trace",
                "resolve_natural_domain_endpoint_support_blockers",
                "resolve_global_bounded_support_validity_claim_gate",
            }
            for item in actions
        ):
            actions.append(
                action(
                    "resolve_bounded_support_validity_claim_gate",
                    (
                        "Final-gate audit reports bounded-support blockers, but "
                        "the bounded-support dataset audit does not expose a more "
                        "specific endpoint or global no-claim blocker."
                    ),
                    [
                        sources["dataset_specific_final_gate_audit"],
                        sources["bounded_support_dataset_audit"],
                        sources["paper_readiness_map"],
                    ],
                )
            )

    for blocker, action_id in GLOBAL_GATE_ACTIONS.items():
        if int(blocker_counts.get(blocker) or 0) > 0:
            actions.append(
                action(
                    action_id,
                    (
                        f"Final-gate audit reports `{blocker}` for "
                        f"{int(blocker_counts.get(blocker) or 0)} bundle(s)."
                    ),
                    [
                        sources["dataset_specific_final_gate_audit"],
                        sources["paper_readiness_map"],
                    ],
                )
            )
    if global_blocked_gates:
        actions.append(
            action(
                "regenerate_dataset_final_gate_after_global_gate_closure",
                (
                    "Paper-readiness map still has blocked gates; rerun this "
                    "plan only after those gates are closed."
                ),
                [sources["paper_readiness_map"]],
            )
        )

    if not actions:
        return (
            "ready_for_dataset_specific_final_gate_recheck",
            [],
            "recheck_dataset_final_gate",
        )
    primary = actions[0]["action_id"]
    if primary == "build_post_selection_validation_bridge":
        status = "blocked_missing_post_selection_validation_bridge"
    elif primary == "execute_post_selection_validation_bridge":
        status = "blocked_post_selection_validation_bridge_execution_pending"
    elif primary == "add_dataset_to_main_result_candidate_bundle_plan":
        status = "blocked_missing_main_result_candidate_bundle"
    elif primary in {
        "execute_main_result_candidate_bundle",
        "resume_incomplete_main_result_candidate_bundle",
    }:
        status = "blocked_candidate_bundle_execution_incomplete"
    elif primary in {
        "build_candidate_post_run_closure_audit",
        "resolve_candidate_post_run_closure_blockers",
    }:
        status = "blocked_candidate_post_run_closure_incomplete"
    elif primary == "resolve_natural_domain_endpoint_support_blockers":
        status = "blocked_bounded_support_endpoint_support"
    elif primary == "backfill_unknown_natural_endpoint_excursion_count":
        status = "blocked_bounded_support_endpoint_count_backfill"
    elif primary == "resolve_global_bounded_support_validity_claim_gate":
        status = "blocked_bounded_support_global_validity_claim"
    elif primary in {
        "complete_bounded_support_dataset_audit_trace",
        "resolve_bounded_support_validity_claim_gate",
    }:
        status = "blocked_bounded_support_gate_trace"
    else:
        status = "blocked_global_paper_gates"
    return status, actions, primary


def build_payload(root: Path) -> dict[str, Any]:
    paths = {
        "dataset_specific_final_gate_audit": root / DATASET_FINAL_GATE,
        "main_result_candidate_bundle_plan": root / MAIN_RESULT_CANDIDATE_BUNDLE_PLAN,
        "main_result_candidate_bundle_results": root
        / MAIN_RESULT_CANDIDATE_BUNDLE_RESULTS,
        "main_result_candidate_post_run_closure_audit": root
        / MAIN_RESULT_CANDIDATE_POST_RUN_CLOSURE,
        "method_selection_post_selection_validation_results": root
        / METHOD_SELECTION_POST_SELECTION_VALIDATION_RESULTS,
        "dataset_final_gate_post_selection_validation_bridge": root
        / DATASET_FINAL_GATE_POST_SELECTION_VALIDATION_BRIDGE,
        "dataset_final_gate_post_selection_validation_bridge_results": root
        / DATASET_FINAL_GATE_POST_SELECTION_VALIDATION_BRIDGE_RESULTS,
        "paper_readiness_map": root / PAPER_READINESS,
        "bounded_support_dataset_audit": root / BOUNDED_SUPPORT_DATASET_AUDIT,
        "bounded_support_endpoint_closure_audit": root
        / BOUNDED_SUPPORT_ENDPOINT_CLOSURE_AUDIT,
    }
    sources = {key: rel(path, root) for key, path in paths.items()}
    final_gate = read_json(paths["dataset_specific_final_gate_audit"])
    plan = read_json(paths["main_result_candidate_bundle_plan"])
    results = read_json(paths["main_result_candidate_bundle_results"])
    closure = read_json(paths["main_result_candidate_post_run_closure_audit"])
    validation = read_json(paths["method_selection_post_selection_validation_results"])
    validation_bridge = read_json(
        paths["dataset_final_gate_post_selection_validation_bridge"]
    )
    validation_bridge_results = read_json(
        paths["dataset_final_gate_post_selection_validation_bridge_results"]
    )
    paper_readiness = read_json(paths["paper_readiness_map"])
    bounded_support_dataset = read_json(paths["bounded_support_dataset_audit"])
    bounded_support_endpoint_closure = read_json(
        paths["bounded_support_endpoint_closure_audit"]
    )

    final_rows = rows_by_dataset(final_gate)
    plan_rows = rows_by_dataset(plan, "candidate_rows")
    result_rows = rows_by_dataset(results)
    closure_rows = rows_by_dataset(closure)
    validation_rows = rows_by_dataset(validation)
    validation_bridge_rows = rows_by_dataset(validation_bridge, "generated_configs")
    validation_bridge_result_rows = rows_by_dataset(validation_bridge_results)
    bounded_support_rows = row_lists_by_dataset(bounded_support_dataset)
    bounded_support_endpoint_closure_rows = rows_by_dataset(
        bounded_support_endpoint_closure
    )
    global_blocked_gates = blocked_gate_ids(paper_readiness)

    rows: list[dict[str, Any]] = []
    action_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    for dataset_id in sorted(final_rows):
        final_row = final_rows[dataset_id]
        standard_validation_row = validation_rows.get(dataset_id)
        bridge_validation_row = validation_bridge_result_rows.get(dataset_id)
        validation_row = standard_validation_row or bridge_validation_row
        validation_bridge_row = validation_bridge_rows.get(dataset_id)
        plan_row = plan_rows.get(dataset_id)
        result_row = result_rows.get(dataset_id)
        closure_row = closure_rows.get(dataset_id)
        bounded_rows = bounded_support_rows.get(dataset_id, [])
        bounded_support_endpoint_closure_row = (
            bounded_support_endpoint_closure_rows.get(dataset_id)
        )
        bridge_execution_status = None
        if bridge_validation_row is not None:
            bridge_execution_status = "completed_bridge_results"
        elif validation_bridge_row is not None:
            bridge_execution_status = validation_bridge_row.get("execution_status")
        status, actions, primary = dataset_actions(
            dataset_id=dataset_id,
            final_row=final_row,
            validation_row=validation_row,
            validation_bridge_row=validation_bridge_row,
            plan_row=plan_row,
            result_row=result_row,
            closure_row=closure_row,
            bounded_support_rows=bounded_rows,
            bounded_support_endpoint_closure_row=(
                bounded_support_endpoint_closure_row
            ),
            global_blocked_gates=global_blocked_gates,
            sources=sources,
        )
        bounded_summary = bounded_support_summary(bounded_rows)
        endpoint_policy_closed = endpoint_closure_policy_closed(
            bounded_support_endpoint_closure_row
        )
        endpoint_backfill_open = endpoint_closure_open_backfill(
            bounded_support_endpoint_closure_row
        )
        for item in actions:
            action_counts[str(item["action_id"])] += 1
        action_scope_counts = Counter(
            str(item.get("action_scope") or "uncategorized") for item in actions
        )
        status_counts[status] += 1
        rows.append(
            {
                "dataset_id": dataset_id,
                "readiness_status": status,
                "bundle_count": final_row.get("bundle_count"),
                "robustness_bundle_count": final_row.get("robustness_bundle_count"),
                "main_result_promotion_ready_bundle_count": final_row.get(
                    "main_result_promotion_ready_bundle_count"
                ),
                "has_main_result_ready_bundle": bool(
                    final_row.get("has_main_result_ready_bundle")
                ),
                "has_post_selection_validation_source": validation_row is not None,
                "has_standard_post_selection_validation_source": (
                    standard_validation_row is not None
                ),
                "has_post_selection_validation_bridge_results": (
                    bridge_validation_row is not None
                ),
                "post_selection_validation_source_kind": (
                    "standard_validation_results"
                    if standard_validation_row is not None
                    else (
                        "dataset_final_gate_bridge_results"
                        if bridge_validation_row is not None
                        else None
                    )
                ),
                "post_selection_validation_config_path": (
                    (validation_row or {}).get("config_path")
                ),
                "post_selection_validation_completed_atomic_run_count": (
                    (validation_row or {}).get("completed_atomic_run_count")
                ),
                "post_selection_validation_expected_atomic_run_count": (
                    (validation_row or {}).get("expected_atomic_run_count")
                ),
                "has_post_selection_validation_bridge_config": (
                    validation_bridge_row is not None
                ),
                "post_selection_validation_bridge_config_path": (
                    (validation_bridge_row or {}).get("config_path")
                ),
                "post_selection_validation_bridge_expected_atomic_run_count": (
                    (validation_bridge_row or {}).get("expected_atomic_run_count")
                ),
                "post_selection_validation_bridge_execution_status": (
                    bridge_execution_status
                ),
                "has_main_result_candidate_bundle": plan_row is not None,
                "main_result_candidate_config_path": (plan_row or {}).get(
                    "config_path"
                ),
                "has_completed_main_result_candidate_results": result_row is not None
                and int(result_row.get("completed_atomic_run_count") or 0)
                >= int(result_row.get("expected_atomic_run_count") or 0),
                "main_result_candidate_completed_atomic_run_count": (
                    (result_row or {}).get("completed_atomic_run_count")
                ),
                "main_result_candidate_expected_atomic_run_count": (
                    (result_row or {}).get("expected_atomic_run_count")
                ),
                "has_candidate_post_run_closure_record": closure_row is not None,
                "candidate_post_run_closure_status": (
                    (closure_row or {}).get("closure_status")
                ),
                "candidate_post_run_closure_blocker_count": (
                    (closure_row or {}).get("blocker_count")
                ),
                "final_gate_blocking_reason_counts": final_row.get(
                    "blocking_reason_counts"
                )
                or {},
                "bounded_support_audit_bundle_count": bounded_summary["bundle_count"],
                "bounded_support_endpoint_support_status_counts": (
                    bounded_summary["endpoint_support_status_counts"]
                ),
                "bounded_support_posthandling_support_status_counts": (
                    bounded_summary["posthandling_support_status_counts"]
                ),
                "bounded_support_blocker_counts": bounded_summary["blocker_counts"],
                "bounded_support_endpoint_clean_bundle_count": (
                    bounded_summary["endpoint_support_clean_bundle_count"]
                ),
                "bounded_support_endpoint_not_applicable_bundle_count": (
                    bounded_summary[
                        "endpoint_support_not_applicable_bundle_count"
                    ]
                ),
                "bounded_support_endpoint_blocked_or_incomplete_bundle_count": (
                    bounded_summary[
                        "endpoint_support_blocked_or_incomplete_bundle_count"
                    ]
                ),
                "bounded_support_global_no_claim_bundle_count": (
                    bounded_summary["global_no_claim_bundle_count"]
                ),
                "bounded_support_endpoint_closure_status": (
                    (bounded_support_endpoint_closure_row or {}).get(
                        "endpoint_closure_status"
                    )
                ),
                "bounded_support_endpoint_closure_next_action_ids": (
                    (bounded_support_endpoint_closure_row or {}).get(
                        "next_action_ids"
                    )
                    or []
                ),
                "bounded_support_endpoint_closure_open_backfill": (
                    endpoint_backfill_open
                ),
                "bounded_support_endpoint_policy_closed_by_closure_audit": (
                    endpoint_policy_closed
                ),
                "bounded_support_endpoint_blocked_but_policy_closed": (
                    int(
                        bounded_summary[
                            "endpoint_support_blocked_or_incomplete_bundle_count"
                        ]
                        or 0
                    )
                    > 0
                    and endpoint_policy_closed
                ),
                "blocked_gate_ids": global_blocked_gates,
                "primary_next_action": primary,
                "executable_next_actions": actions,
                "action_scope_counts": dict(sorted(action_scope_counts.items())),
                "has_local_dataset_remediation_action": bool(
                    action_scope_counts.get("local_dataset_remediation")
                ),
                "has_global_gate_dependency_action": bool(
                    action_scope_counts.get("global_gate_dependency")
                ),
                "has_post_closure_refresh_action": bool(
                    action_scope_counts.get("post_closure_refresh")
                ),
                "blocked_only_by_global_gate_dependencies": (
                    not action_scope_counts.get("local_dataset_remediation")
                    and bool(action_scope_counts.get("global_gate_dependency"))
                ),
                "claim_boundary": (
                    "Dataset remains non-promotional until this remediation "
                    "plan is completed and paper-readiness gates are rechecked."
                ),
            }
        )

    summary = {
        "overall_status": "dataset_final_gate_remediation_plan_ready_no_promotions",
        "dataset_count": len(rows),
        "ready_dataset_count": sum(
            row["readiness_status"] == "ready_for_dataset_specific_final_gate_recheck"
            for row in rows
        ),
        "missing_post_selection_validation_bridge_count": sum(
            not row["has_post_selection_validation_source"] for row in rows
        ),
        "post_selection_validation_bridge_config_count": sum(
            row["has_post_selection_validation_bridge_config"] for row in rows
        ),
        "missing_post_selection_validation_bridge_config_count": sum(
            (
                not row["has_post_selection_validation_source"]
                and not row["has_post_selection_validation_bridge_config"]
            )
            for row in rows
        ),
        "post_selection_validation_bridge_execution_pending_count": sum(
            row["primary_next_action"] == "execute_post_selection_validation_bridge"
            for row in rows
        ),
        "post_selection_validation_bridge_results_count": sum(
            row["has_post_selection_validation_bridge_results"] for row in rows
        ),
        "missing_main_result_candidate_bundle_count": sum(
            not row["has_main_result_candidate_bundle"] for row in rows
        ),
        "completed_main_result_candidate_results_dataset_count": sum(
            row["has_completed_main_result_candidate_results"] for row in rows
        ),
        "candidate_post_run_closure_ready_dataset_count": sum(
            str(row.get("candidate_post_run_closure_status") or "").startswith(
                "post_run_closure_ready"
            )
            for row in rows
        ),
        "bounded_support_blocked_dataset_count": sum(
            int(
                (row.get("final_gate_blocking_reason_counts") or {}).get(
                    "bounded_support_validity_not_supported"
                )
                or 0
            )
            > 0
            for row in rows
        ),
        "bounded_support_endpoint_blocked_or_incomplete_dataset_count": sum(
            int(
                row.get("bounded_support_endpoint_blocked_or_incomplete_bundle_count")
                or 0
            )
            > 0
            for row in rows
        ),
        "bounded_support_global_no_claim_dataset_count": sum(
            int(row.get("bounded_support_global_no_claim_bundle_count") or 0) > 0
            for row in rows
        ),
        "bounded_support_endpoint_clean_or_not_applicable_only_dataset_count": sum(
            int(
                row.get("bounded_support_endpoint_blocked_or_incomplete_bundle_count")
                or 0
            )
            == 0
            and (
                int(row.get("bounded_support_endpoint_clean_bundle_count") or 0)
                + int(
                    row.get("bounded_support_endpoint_not_applicable_bundle_count")
                    or 0
                )
                > 0
            )
            for row in rows
        ),
        "bounded_support_endpoint_closure_dataset_count": sum(
            row["bounded_support_endpoint_closure_status"] is not None for row in rows
        ),
        "bounded_support_endpoint_closure_open_backfill_dataset_count": sum(
            row["bounded_support_endpoint_closure_open_backfill"] for row in rows
        ),
        "bounded_support_endpoint_policy_closed_dataset_count": sum(
            row["bounded_support_endpoint_policy_closed_by_closure_audit"]
            for row in rows
        ),
        "bounded_support_endpoint_blocked_but_policy_closed_dataset_count": sum(
            row["bounded_support_endpoint_blocked_but_policy_closed"] for row in rows
        ),
        "bounded_support_endpoint_requiring_local_remediation_dataset_count": sum(
            any(
                item["action_id"]
                in {
                    "backfill_unknown_natural_endpoint_excursion_count",
                    "complete_bounded_support_dataset_audit_trace",
                    "resolve_natural_domain_endpoint_support_blockers",
                }
                for item in row["executable_next_actions"]
            )
            for row in rows
        ),
        "fairness_population_blocked_dataset_count": sum(
            int(
                (row.get("final_gate_blocking_reason_counts") or {}).get(
                    "fairness_population_claim_not_ready"
                )
                or 0
            )
            > 0
            for row in rows
        ),
        "final_selection_blocked_dataset_count": sum(
            int(
                (row.get("final_gate_blocking_reason_counts") or {}).get(
                    "final_selection_claim_blocked"
                )
                or 0
            )
            > 0
            for row in rows
        ),
        "paper_blocked_gate_count": len(global_blocked_gates),
        "blocked_gate_ids": global_blocked_gates,
        "action_counts": dict(sorted(action_counts.items())),
        "action_scope_counts": dict(
            sorted(
                Counter(
                    str(item.get("action_scope") or "uncategorized")
                    for row in rows
                    for item in row["executable_next_actions"]
                ).items()
            )
        ),
        "local_dataset_remediation_action_count": sum(
            int(row["action_scope_counts"].get("local_dataset_remediation", 0))
            for row in rows
        ),
        "global_gate_dependency_action_count": sum(
            int(row["action_scope_counts"].get("global_gate_dependency", 0))
            for row in rows
        ),
        "post_closure_refresh_action_count": sum(
            int(row["action_scope_counts"].get("post_closure_refresh", 0))
            for row in rows
        ),
        "dataset_with_local_dataset_remediation_action_count": sum(
            row["has_local_dataset_remediation_action"] for row in rows
        ),
        "dataset_blocked_only_by_global_gate_dependencies_count": sum(
            row["blocked_only_by_global_gate_dependencies"] for row in rows
        ),
        "dataset_with_no_remaining_execution_gap_count": sum(
            row["has_post_selection_validation_source"]
            and row["has_main_result_candidate_bundle"]
            and row["has_completed_main_result_candidate_results"]
            and row["has_candidate_post_run_closure_record"]
            and int(row.get("candidate_post_run_closure_blocker_count") or 0) == 0
            for row in rows
        ),
        "readiness_status_counts": dict(sorted(status_counts.items())),
        "missing_post_selection_validation_bridge_dataset_ids": [
            row["dataset_id"]
            for row in rows
            if not row["has_post_selection_validation_source"]
        ],
        "post_selection_validation_bridge_config_dataset_ids": [
            row["dataset_id"]
            for row in rows
            if row["has_post_selection_validation_bridge_config"]
        ],
        "post_selection_validation_bridge_results_dataset_ids": [
            row["dataset_id"]
            for row in rows
            if row["has_post_selection_validation_bridge_results"]
        ],
        "missing_post_selection_validation_bridge_config_dataset_ids": [
            row["dataset_id"]
            for row in rows
            if (
                not row["has_post_selection_validation_source"]
                and not row["has_post_selection_validation_bridge_config"]
            )
        ],
        "missing_main_result_candidate_bundle_dataset_ids": [
            row["dataset_id"]
            for row in rows
            if not row["has_main_result_candidate_bundle"]
        ],
        "executable_action_count": sum(
            len(row["executable_next_actions"]) for row in rows
        ),
        "executable_action_semantics": (
            "Counts required plan rows, including local dataset remediation, "
            "global gate dependencies, and post-closure refresh steps."
        ),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "summary": summary,
        "claim_boundaries": CLAIM_BOUNDARIES,
        "dataset_rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Dataset Final Gate Remediation Plan",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Datasets: {summary['dataset_count']}",
        f"- Ready datasets: {summary['ready_dataset_count']}",
        f"- Missing post-selection validation bridges: {summary['missing_post_selection_validation_bridge_count']}",
        f"- Generated post-selection validation bridge configs: {summary['post_selection_validation_bridge_config_count']}",
        f"- Bridge execution pending datasets: {summary['post_selection_validation_bridge_execution_pending_count']}",
        f"- Bridge result datasets: {summary['post_selection_validation_bridge_results_count']}",
        f"- Missing main-result candidate bundles: {summary['missing_main_result_candidate_bundle_count']}",
        f"- Completed main-result candidate result datasets: {summary['completed_main_result_candidate_results_dataset_count']}",
        f"- Candidate post-run closure ready datasets: {summary['candidate_post_run_closure_ready_dataset_count']}",
        f"- Bounded-support endpoint blocked/incomplete datasets: {summary['bounded_support_endpoint_blocked_or_incomplete_dataset_count']}",
        f"- Bounded-support endpoint policy-closed datasets: {summary['bounded_support_endpoint_policy_closed_dataset_count']}",
        f"- Bounded-support endpoint local-remediation datasets: {summary['bounded_support_endpoint_requiring_local_remediation_dataset_count']}",
        f"- Bounded-support global no-claim datasets: {summary['bounded_support_global_no_claim_dataset_count']}",
        f"- Bounded-support endpoint clean/not-applicable-only datasets: {summary['bounded_support_endpoint_clean_or_not_applicable_only_dataset_count']}",
        f"- Paper blocked gates: {summary['paper_blocked_gate_count']}",
        f"- Executable actions: {summary['executable_action_count']}",
        f"- Local dataset-remediation actions: {summary['local_dataset_remediation_action_count']}",
        f"- Global gate-dependency actions: {summary['global_gate_dependency_action_count']}",
        f"- Post-closure refresh actions: {summary['post_closure_refresh_action_count']}",
        f"- Datasets with no remaining execution gap: {summary['dataset_with_no_remaining_execution_gap_count']}",
        f"- Datasets blocked only by global gate dependencies: {summary['dataset_blocked_only_by_global_gate_dependencies_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Dataset Actions",
            "",
            "| Dataset | Status | Validation source | Bridge config | Candidate bundle | Candidate results | Endpoint blocked/incomplete | Endpoint closure | Global no-claim | Local actions | Global actions | Primary next action |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["dataset_rows"]:
        scope_counts = row.get("action_scope_counts") or {}
        lines.append(
            "| "
            f"`{row['dataset_id']}` | "
            f"`{row['readiness_status']}` | "
            f"`{row['has_post_selection_validation_source']}` | "
            f"`{row['has_post_selection_validation_bridge_config']}` | "
            f"`{row['has_main_result_candidate_bundle']}` | "
            f"`{row['has_completed_main_result_candidate_results']}` | "
            f"{row['bounded_support_endpoint_blocked_or_incomplete_bundle_count']} | "
            f"`{row['bounded_support_endpoint_closure_status']}` | "
            f"{row['bounded_support_global_no_claim_bundle_count']} | "
            f"{scope_counts.get('local_dataset_remediation', 0)} | "
            f"{scope_counts.get('global_gate_dependency', 0)} | "
            f"`{row['primary_next_action']}` |"
        )
    lines.extend(["", "## Action Counts", ""])
    for action_id, count in summary["action_counts"].items():
        lines.append(f"- `{action_id}`: {count}")
    lines.extend(["", "## Action Scope Counts", ""])
    for scope, count in summary["action_scope_counts"].items():
        lines.append(f"- `{scope}`: {count}")
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
        json.dumps({"out": rel(out_path, root), **payload["summary"]}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
