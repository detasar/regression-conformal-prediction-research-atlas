"""Audit neutral experiment-closure readiness without requiring positive claims.

This audit is a bridge between empirical completion evidence and the still
deferred publication program. It does not mark the full user goal complete,
start manuscript drafting, create a sterile repository, or promote a final
method. It checks whether the current artifacts support a neutral no-promotion
closure route: all paper gates have recorded positive/scoped/negative/no-claim
dispositions, no local execution queue remains, and quality controls are clean.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_neutral_experiment_closure_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "neutral_experiment_closure_audit.json"

GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
PAPER_GATE_CLOSURE = Path("experiments/regression/manuscript/paper_gate_closure_map.json")
PAPER_GATE_EXECUTION_PLAN = Path(
    "experiments/regression/manuscript/paper_gate_closure_execution_plan.json"
)
PUBLICATION_ACTIVATION = Path(
    "experiments/regression/manuscript/post_experiment_publication_activation_audit.json"
)
EXPERIMENT_ACCOUNTING = REPORT_DIR / "experiment_accounting_audit.json"
METHOD_LITERATURE = REPORT_DIR / "method_literature_coverage_audit.json"
METHOD_PERFORMANCE = REPORT_DIR / "method_performance_synthesis.json"
PUBLICATION_METHODOLOGY = REPORT_DIR / "publication_methodology_audit.json"
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
SCIENTIFIC_REVIEW = REPORT_DIR / "scientific_review_finding_register.json"
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
KG_PUBLICATION = REPORT_DIR / "kg_publication_quality_audit.json"


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


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def check_row(
    check_id: str,
    status: str,
    evidence: dict[str, Any],
    source_artifacts: list[str],
    blocker: str = "",
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "blocks_neutral_closure": status == "fail",
        "evidence": evidence,
        "source_artifacts": source_artifacts,
        "blocker": blocker,
    }


def build_payload(root: Path) -> dict[str, Any]:
    paths = {
        "goal_completion": root / GOAL_COMPLETION,
        "paper_gate_closure": root / PAPER_GATE_CLOSURE,
        "paper_gate_execution_plan": root / PAPER_GATE_EXECUTION_PLAN,
        "publication_activation": root / PUBLICATION_ACTIVATION,
        "experiment_accounting": root / EXPERIMENT_ACCOUNTING,
        "method_literature": root / METHOD_LITERATURE,
        "method_performance": root / METHOD_PERFORMANCE,
        "publication_methodology": root / PUBLICATION_METHODOLOGY,
        "neutral_language": root / NEUTRAL_LANGUAGE,
        "scientific_review": root / SCIENTIFIC_REVIEW,
        "kg_quality": root / KG_QUALITY,
        "kg_publication": root / KG_PUBLICATION,
    }
    payloads = {key: read_json(path) for key, path in paths.items()}
    summaries = {key: summary(value) for key, value in payloads.items()}
    kg_quality = payloads["kg_quality"]
    kg_graph = kg_quality.get("graph") or {}
    kg_traceability = kg_quality.get("traceability") or {}
    kg_publication_summary = summaries["kg_publication"]

    closure_summary = summaries["paper_gate_closure"]
    execution_summary = summaries["paper_gate_execution_plan"]
    goal_summary = summaries["goal_completion"]
    activation_summary = summaries["publication_activation"]
    accounting_summary = summaries["experiment_accounting"]
    method_literature_summary = summaries["method_literature"]
    method_performance_summary = summaries["method_performance"]
    publication_summary = summaries["publication_methodology"]
    neutral_language_summary = summaries["neutral_language"]
    scientific_review_summary = summaries["scientific_review"]

    gate_count = safe_int(closure_summary.get("gate_count"))
    positive_ready_gate_count = safe_int(
        closure_summary.get("positive_claim_ready_gate_count")
    )
    scoped_or_negative_gate_count = safe_int(
        closure_summary.get("scoped_or_negative_path_ready_gate_count")
    )
    final_disposition_gate_count = positive_ready_gate_count + scoped_or_negative_gate_count
    publication_phase_start_authorized = (
        activation_summary.get("publication_phase_start_authorized") is True
    )
    publication_preparation_authorized = (
        activation_summary.get("publication_preparation_authorized") is True
        or publication_phase_start_authorized
    )
    final_manuscript_actions_blocked = (
        activation_summary.get("manuscript_drafting_authorized") is False
        and activation_summary.get("sterile_repository_creation_authorized") is False
    )
    neutral_activation_policy_respected = (
        (
            not publication_phase_start_authorized
            and activation_summary.get("manuscript_drafting_authorized") is False
            and activation_summary.get("sterile_repository_creation_authorized") is False
        )
        or (
            publication_phase_start_authorized
            and publication_preparation_authorized
            and goal_summary.get("neutral_empirical_phase_complete") is True
            and final_manuscript_actions_blocked
        )
    )

    checks = [
        check_row(
            "all_paper_gates_have_final_dispositions",
            (
                "pass"
                if gate_count > 0
                and final_disposition_gate_count == gate_count
                and safe_int(closure_summary.get("failed_check_count")) == 0
                else "fail"
            ),
            {
                "gate_count": gate_count,
                "positive_claim_ready_gate_count": positive_ready_gate_count,
                "scoped_or_negative_path_ready_gate_count": scoped_or_negative_gate_count,
                "final_disposition_gate_count": final_disposition_gate_count,
                "paper_gate_closure_status": closure_summary.get("overall_status"),
            },
            [rel(paths["paper_gate_closure"], root)],
            "paper_gate_dispositions_incomplete",
        ),
        check_row(
            "neutral_route_requires_no_positive_claim_promotion",
            (
                "pass"
                if positive_ready_gate_count == 0
                and scoped_or_negative_gate_count == gate_count
                and safe_int(closure_summary.get("disallowed_language_item_count")) > 0
                else "fail"
            ),
            {
                "positive_claim_ready_gate_count": positive_ready_gate_count,
                "scoped_or_negative_path_ready_gate_count": scoped_or_negative_gate_count,
                "disallowed_language_item_count": closure_summary.get(
                    "disallowed_language_item_count"
                ),
            },
            [rel(paths["paper_gate_closure"], root)],
            "positive_claim_promotion_or_missing_disallowed_language_controls",
        ),
        check_row(
            "no_local_execution_queue_remains",
            (
                "pass"
                if safe_int(execution_summary.get("ready_action_count")) == 0
                and safe_int(goal_summary.get("local_execution_gap_gate_count")) == 0
                else "fail"
            ),
            {
                "ready_action_count": execution_summary.get("ready_action_count"),
                "next_executable_action_ids": execution_summary.get(
                    "next_executable_action_ids"
                ),
                "local_execution_gap_gate_count": goal_summary.get(
                    "local_execution_gap_gate_count"
                ),
            },
            [rel(paths["paper_gate_execution_plan"], root), rel(paths["goal_completion"], root)],
            "local_execution_queue_not_empty",
        ),
        check_row(
            "empirical_accounting_and_method_surface_ready",
            (
                "pass"
                if accounting_summary.get("overall_status") == "experiment_accounting_pass"
                and safe_int(accounting_summary.get("publication_completed_rows")) > 0
                and method_literature_summary.get("overall_status")
                == "method_literature_coverage_pass"
                and safe_int(method_literature_summary.get("failed_check_count")) == 0
                and str(method_performance_summary.get("overall_status", "")).endswith(
                    "no_final_selection"
                )
                and method_performance_summary.get("claim_status")
                in {
                    "descriptive_no_final_selection",
                    "performance_synthesis_ready_no_final_selection",
                }
                else "fail"
            ),
            {
                "experiment_accounting_status": accounting_summary.get("overall_status"),
                "publication_completed_rows": accounting_summary.get(
                    "publication_completed_rows"
                ),
                "method_literature_status": method_literature_summary.get(
                    "overall_status"
                ),
                "method_performance_status": method_performance_summary.get(
                    "overall_status"
                ),
                "method_performance_claim_status": method_performance_summary.get(
                    "claim_status"
                ),
            },
            [
                rel(paths["experiment_accounting"], root),
                rel(paths["method_literature"], root),
                rel(paths["method_performance"], root),
            ],
            "empirical_accounting_or_method_surface_incomplete",
        ),
        check_row(
            "quality_controls_support_neutral_closure",
            (
                "pass"
                if publication_summary.get("overall_status")
                in {"publication_workbench_ready", "publication_workbench_ready_with_caveats"}
                and safe_int(publication_summary.get("unsupported_claim_hits")) == 0
                and neutral_language_summary.get("overall_status")
                == "neutral_reporting_language_audit_pass"
                and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
                and safe_int(scientific_review_summary.get("open_blocker_count")) == 0
                and safe_int(scientific_review_summary.get("hard_open_blocker_count")) == 0
                and not kg_quality.get("issue_counts_by_severity")
                and safe_int(kg_graph.get("isolated_node_count")) == 0
                and float(kg_traceability.get("explicit_edge_provenance_coverage") or 0.0)
                >= 1.0
                and kg_publication_summary.get("overall_status")
                in {"kg_publication_ready", "kg_publication_ready_with_polish_caveats"}
                and safe_int(kg_publication_summary.get("hard_failed_check_count")) == 0
                else "fail"
            ),
            {
                "publication_methodology_status": publication_summary.get("overall_status"),
                "unsupported_claim_hits": publication_summary.get("unsupported_claim_hits"),
                "neutral_language_status": neutral_language_summary.get("overall_status"),
                "unguarded_hit_count": neutral_language_summary.get("unguarded_hit_count"),
                "scientific_review_status": scientific_review_summary.get("overall_status"),
                "open_blocker_count": scientific_review_summary.get("open_blocker_count"),
                "kg_issue_counts": kg_quality.get("issue_counts_by_severity"),
                "kg_publication_status": kg_publication_summary.get("overall_status"),
                "kg_publication_hard_failed_check_count": kg_publication_summary.get(
                    "hard_failed_check_count"
                ),
            },
            [
                rel(paths["publication_methodology"], root),
                rel(paths["neutral_language"], root),
                rel(paths["scientific_review"], root),
                rel(paths["kg_quality"], root),
                rel(paths["kg_publication"], root),
            ],
            "quality_controls_do_not_support_neutral_closure",
        ),
        check_row(
            "publication_phase_respects_neutral_activation_policy",
            (
                "pass"
                if neutral_activation_policy_respected
                else "fail"
            ),
            {
                "publication_activation_status": activation_summary.get("overall_status"),
                "publication_phase_start_authorized": activation_summary.get(
                    "publication_phase_start_authorized"
                ),
                "publication_preparation_authorized": activation_summary.get(
                    "publication_preparation_authorized"
                ),
                "visual_table_audit_authorized": activation_summary.get(
                    "visual_table_audit_authorized"
                ),
                "manuscript_drafting_authorized": activation_summary.get(
                    "manuscript_drafting_authorized"
                ),
                "sterile_repository_creation_authorized": activation_summary.get(
                    "sterile_repository_creation_authorized"
                ),
                "goal_neutral_empirical_phase_complete": goal_summary.get(
                    "neutral_empirical_phase_complete"
                ),
                "goal_can_mark_complete": goal_summary.get("can_mark_goal_complete"),
                "goal_noncomplete_requirement_count": goal_summary.get(
                    "noncomplete_requirement_count"
                ),
            },
            [rel(paths["publication_activation"], root), rel(paths["goal_completion"], root)],
            "publication_phase_started_beyond_neutral_policy",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] == "fail"]
    goal_policy_update_required = (
        goal_summary.get("neutral_empirical_phase_complete") is not True
    )
    publication_phase_deferred = not publication_phase_start_authorized
    neutral_closure_ready = not failed_checks
    overall_status = (
        "neutral_experiment_closure_ready_for_goal_policy_update"
        if neutral_closure_ready and goal_policy_update_required
        else "neutral_experiment_closure_ready"
        if neutral_closure_ready
        else "neutral_experiment_closure_blocked"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "neutral_closure_ready": neutral_closure_ready,
            "goal_policy_update_required": goal_policy_update_required,
            "publication_phase_deferred": publication_phase_deferred,
            "publication_preparation_authorized": publication_preparation_authorized,
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
            "gate_count": gate_count,
            "final_disposition_gate_count": final_disposition_gate_count,
            "positive_claim_ready_gate_count": positive_ready_gate_count,
            "scoped_or_negative_path_ready_gate_count": scoped_or_negative_gate_count,
            "ready_action_count": execution_summary.get("ready_action_count"),
            "local_execution_gap_gate_count": goal_summary.get(
                "local_execution_gap_gate_count"
            ),
            "publication_completed_rows": accounting_summary.get(
                "publication_completed_rows"
            ),
            "neutral_language_unguarded_hit_count": neutral_language_summary.get(
                "unguarded_hit_count"
            ),
            "kg_node_count": (kg_quality.get("graph") or {}).get("node_count"),
            "kg_edge_count": (kg_quality.get("graph") or {}).get("edge_count"),
            "goal_can_mark_complete": goal_summary.get("can_mark_goal_complete"),
            "goal_neutral_empirical_phase_complete": goal_summary.get(
                "neutral_empirical_phase_complete"
            ),
            "goal_empirical_completion_policy": goal_summary.get(
                "empirical_completion_policy"
            ),
            "post_experiment_publication_authorized": activation_summary.get(
                "publication_phase_start_authorized"
            ),
        },
        "checks": checks,
        "failed_checks": [row["check_id"] for row in failed_checks],
        "claim_boundaries": [
            "This audit does not mark the full original goal complete.",
            "A ready neutral empirical phase means the experiment can be treated as empirically closed while publication deliverables remain separately gated.",
            "A ready neutral closure means current evidence supports reporting scoped, negative, diagnostic, or no-claim dispositions without positive method promotion.",
            "Post-experiment publication preparation may be active for reviewer design and visual/table planning; final manuscript prose and sterile release remain controlled by later activation gates.",
            "Positive CQR, CV+, bounded-support, fairness, final-winner, production, or Venn-Abers claims remain disallowed unless their dedicated gates pass.",
        ],
        "source_artifacts": {key: rel(path, root) for key, path in paths.items()},
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Neutral Experiment Closure Audit",
        "",
        "This audit checks whether the experiment can be treated as empirically closed under a neutral no-promotion reporting route.",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Neutral closure ready: `{summary_payload['neutral_closure_ready']}`",
        f"- Goal policy update required: `{summary_payload['goal_policy_update_required']}`",
        f"- Publication phase deferred: `{summary_payload['publication_phase_deferred']}`",
        f"- Publication preparation authorized: `{summary_payload['publication_preparation_authorized']}`",
        f"- Final result dispositions: {summary_payload['final_disposition_gate_count']} / {summary_payload['gate_count']}",
        f"- Positive-claim-ready gates: {summary_payload['positive_claim_ready_gate_count']}",
        f"- Scoped/negative/no-claim gates: {summary_payload['scoped_or_negative_path_ready_gate_count']}",
        f"- Ready execution actions: {summary_payload['ready_action_count']}",
        f"- Local execution-gap gates: {summary_payload['local_execution_gap_gate_count']}",
        f"- Failed checks: {summary_payload['failed_check_count']} / {summary_payload['check_count']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Blocks neutral closure |",
        "|---|---:|---:|",
    ]
    for row in payload["checks"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['blocks_neutral_closure']}` |"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok" if not payload["failed_checks"] else "fail",
                "overall_status": payload["summary"]["overall_status"],
                "neutral_closure_ready": payload["summary"]["neutral_closure_ready"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )
    if payload["failed_checks"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
