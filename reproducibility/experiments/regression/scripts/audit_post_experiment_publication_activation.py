"""Audit whether the deferred publication-preparation phase may start.

This is a stop/go control. It does not authorize public final-submission prose,
choose retained publication figures, create the sterile repository, or promote
any scientific claim. It checks whether the current evidence authorizes the
private publication-preparation phase: reviewer design, visual/table audit
planning, and private manuscript drafting under the neutral no-promotion route.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_post_experiment_publication_activation_audit_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/"
    "post_experiment_publication_activation_audit.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

POST_EXPERIMENT_PUBLICATION_PROGRAM = Path(
    "experiments/regression/manuscript/post_experiment_publication_program.json"
)
GOAL_COMPLETION_AUDIT = Path(
    "experiments/regression/manuscript/goal_completion_audit.json"
)
PAPER_READINESS_MAP = Path("experiments/regression/manuscript/paper_readiness_map.json")
PAPER_GATE_CLOSURE_MAP = Path(
    "experiments/regression/manuscript/paper_gate_closure_map.json"
)
PAPER_GATE_CLOSURE_EXECUTION_PLAN = Path(
    "experiments/regression/manuscript/paper_gate_closure_execution_plan.json"
)
PUBLICATION_METHODOLOGY_AUDIT = REPORT_DIR / "publication_methodology_audit.json"
EXPERIMENT_ACCOUNTING_AUDIT = REPORT_DIR / "experiment_accounting_audit.json"
KG_QUALITY_SUMMARY = Path(
    "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
)
KG_PUBLICATION_QUALITY_AUDIT = REPORT_DIR / "kg_publication_quality_audit.json"
SCIENTIFIC_REVIEW_FINDING_REGISTER = (
    REPORT_DIR / "scientific_review_finding_register.json"
)
MANUSCRIPT_BUNDLE_ELIGIBILITY = Path(
    "experiments/regression/manuscript/bundle_eligibility_matrix.json"
)
REVIEWER_DESIGN_BRIEF = Path(
    "experiments/regression/manuscript/reviewer_design_brief.json"
)
PUBLICATION_RETENTION_READINESS_AUDIT = Path(
    "experiments/regression/manuscript/publication_retention_readiness_audit.json"
)


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


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("summary") or {}


def int_value(payload: dict[str, Any], key: str) -> int:
    try:
        return int(payload.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def source_paths(root: Path, *paths: Path) -> list[str]:
    return [rel(root / path, root) for path in paths if (root / path).exists()]


def check_row(
    *,
    check_id: str,
    title: str,
    status: str,
    evidence_summary: str,
    source_artifacts: list[str],
    metrics: dict[str, Any] | None = None,
    blocker: str = "",
    required_for: str = "publication_phase_activation",
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "title": title,
        "status": status,
        "blocks_activation": status == "blocked",
        "required_for": required_for,
        "evidence_summary": evidence_summary,
        "source_artifacts": source_artifacts,
        "metrics": metrics or {},
        "blocker": blocker,
    }


def build_payload(root: Path) -> dict[str, Any]:
    post_program = read_json(root / POST_EXPERIMENT_PUBLICATION_PROGRAM)
    goal = read_json(root / GOAL_COMPLETION_AUDIT)
    readiness = read_json(root / PAPER_READINESS_MAP)
    closure_map = read_json(root / PAPER_GATE_CLOSURE_MAP)
    execution_plan = read_json(root / PAPER_GATE_CLOSURE_EXECUTION_PLAN)
    publication = read_json(root / PUBLICATION_METHODOLOGY_AUDIT)
    accounting = read_json(root / EXPERIMENT_ACCOUNTING_AUDIT)
    kg_quality = read_json(root / KG_QUALITY_SUMMARY)
    kg_publication = read_json(root / KG_PUBLICATION_QUALITY_AUDIT)
    scientific_review = read_json(root / SCIENTIFIC_REVIEW_FINDING_REGISTER)
    bundle_matrix = read_json(root / MANUSCRIPT_BUNDLE_ELIGIBILITY)
    reviewer_design = read_json(root / REVIEWER_DESIGN_BRIEF)
    retention_readiness = read_json(root / PUBLICATION_RETENTION_READINESS_AUDIT)

    goal_summary = summary(goal)
    readiness_summary = summary(readiness)
    closure_summary = summary(closure_map)
    execution_summary = summary(execution_plan)
    publication_summary = summary(publication)
    accounting_summary = summary(accounting)
    kg_graph = kg_quality.get("graph") or {}
    kg_traceability = kg_quality.get("traceability") or {}
    kg_publication_summary = summary(kg_publication)
    scientific_review_summary = summary(scientific_review)
    bundle_summary = summary(bundle_matrix)
    reviewer_design_summary = summary(reviewer_design)
    retention_readiness_summary = summary(retention_readiness)

    activation_rule = post_program.get("activation_rule") or {}
    publication_author = post_program.get("publication_author") or {}
    sterile_repo = post_program.get("sterile_publication_repository_plan") or {}
    reviewer_gate = post_program.get("reviewer_design_gate") or {}
    visual_audit = post_program.get("visual_table_audit_agent") or {}
    deliverables = post_program.get("deliverables") or []
    completion_definition = (
        post_program.get("experiment_completion_definition") or {}
    )

    blocked_gate_count = int_value(readiness_summary, "blocked_gate_count")
    ready_action_count = int_value(execution_summary, "ready_action_count")
    positive_ready_gate_count = int_value(closure_summary, "positive_claim_ready_gate_count")
    scoped_or_negative_gate_count = int_value(
        closure_summary, "scoped_or_negative_path_ready_gate_count"
    )
    gate_count = int_value(closure_summary, "gate_count")
    final_result_disposition_gate_count = (
        positive_ready_gate_count + scoped_or_negative_gate_count
    )
    neutral_empirical_phase_complete = (
        goal_summary.get("neutral_empirical_phase_complete") is True
    )
    neutral_publication_route_allowed = bool(
        activation_rule.get("allows_neutral_scoped_no_claim_publication_route")
    )
    positive_claim_language_blocked = (
        positive_ready_gate_count == 0
        and final_result_disposition_gate_count == gate_count
        and gate_count > 0
    )
    reviewer_design_reconciled = (
        reviewer_design_summary.get("overall_status")
        == "reviewer_design_brief_ready_no_final_prose"
        and int_value(reviewer_design_summary, "failed_check_count") == 0
        and int_value(reviewer_design_summary, "reviewer_count")
        == int_value(reviewer_design_summary, "required_reviewer_count")
        == 5
        and int_value(reviewer_design_summary, "advice_record_count") >= 25
        and reviewer_design_summary.get("final_manuscript_prose_permission") is False
        and reviewer_design_summary.get("positive_claim_promotion_authorized") is False
    )
    retention_recommendations_ready = (
        retention_readiness_summary.get("overall_status")
        == "publication_retention_readiness_ready_no_final_prose"
        and int_value(retention_readiness_summary, "failed_check_count") == 0
        and int_value(retention_readiness_summary, "recommendation_row_count") > 0
        and retention_readiness_summary.get("retention_recommendation_complete") is True
        and retention_readiness_summary.get("final_visual_table_retention_authorized")
        is False
        and retention_readiness_summary.get("final_manuscript_prose_permission")
        is False
        and retention_readiness_summary.get("positive_claim_promotion_authorized")
        is False
    )
    paper_gate_blockers = [
        str(row.get("gate_id"))
        for row in readiness.get("blocked_gates", []) or []
        if isinstance(row, dict) and row.get("gate_id")
    ]

    kg_quality_clean = (
        not kg_quality.get("issue_counts_by_severity")
        and int_value(kg_graph, "isolated_node_count") == 0
        and float(kg_traceability.get("explicit_edge_provenance_coverage") or 0.0)
        >= 1.0
    )
    kg_publication_clean = (
        kg_publication_summary.get("overall_status") == "kg_publication_ready"
        and int_value(kg_publication_summary, "hard_failed_check_count") == 0
        and int_value(kg_publication_summary, "polish_caveat_count") == 0
    )
    kg_publication_usable_with_caveats = (
        kg_publication_summary.get("overall_status")
        in {"kg_publication_ready", "kg_publication_ready_with_polish_caveats"}
        and int_value(kg_publication_summary, "hard_failed_check_count") == 0
    )
    final_public_release_gate_closed_caveat = (
        neutral_empirical_phase_complete
        and neutral_publication_route_allowed
        and positive_claim_language_blocked
        and goal_summary.get("can_mark_goal_complete") is False
    )
    kg_publication_evidence_summary = (
        "KG topology/provenance quality is clean and publication freeze has no "
        "KG polish caveats."
        if kg_quality_clean and kg_publication_clean
        else "KG topology/provenance quality is usable for publication "
        "preparation, but the publication freeze still carries polish caveats."
        if kg_quality_clean and kg_publication_usable_with_caveats
        else "KG topology/provenance quality is not clean enough for "
        "publication preparation."
    )

    rows = [
        check_row(
            check_id="post_experiment_program_present",
            title="Post-experiment publication program exists",
            status=(
                "pass"
                if post_program.get("status")
                in {
                    "deferred_until_experimental_gates_complete",
                    "neutral_publication_preparation_active",
                }
                else "blocked"
            ),
            evidence_summary=(
                "Publication program is present and remains controlled by "
                "activation rules."
            ),
            source_artifacts=source_paths(root, POST_EXPERIMENT_PUBLICATION_PROGRAM),
            metrics={"program_status": post_program.get("status")},
            blocker="post_experiment_publication_program_missing_or_not_controlled",
        ),
        check_row(
            check_id="neutral_empirical_completion_verified",
            title="Neutral empirical experiment phase is complete",
            status=(
                "pass" if neutral_empirical_phase_complete else "blocked"
            ),
            evidence_summary=(
                "Goal completion audit verifies that the empirical phase is "
                "complete under the neutral no-promotion route; full publication "
                "deliverables remain separate downstream work."
            ),
            source_artifacts=source_paths(root, GOAL_COMPLETION_AUDIT),
            metrics={
                "goal_status": goal_summary.get("overall_status"),
                "can_mark_goal_complete": goal_summary.get("can_mark_goal_complete"),
                "neutral_empirical_phase_complete": neutral_empirical_phase_complete,
                "empirical_completion_policy": goal_summary.get(
                    "empirical_completion_policy"
                ),
                "noncomplete_requirement_count": goal_summary.get(
                    "noncomplete_requirement_count"
                ),
            },
            blocker="neutral_empirical_phase_not_complete",
        ),
        check_row(
            check_id="positive_claim_blockers_guarded_for_neutral_route",
            title="Positive-claim paper gates are guarded for neutral reporting",
            status=(
                "pass"
                if neutral_publication_route_allowed and positive_claim_language_blocked
                else "blocked"
            ),
            evidence_summary=(
                "Blocked paper gates are positive-claim blockers, not empirical "
                "execution gaps. They may coexist with publication preparation only "
                "when the neutral route is explicitly enabled and all final "
                "dispositions are recorded."
            ),
            source_artifacts=source_paths(root, PAPER_READINESS_MAP, PAPER_GATE_CLOSURE_MAP),
            metrics={
                "blocked_gate_count": blocked_gate_count,
                "blocked_gate_ids": paper_gate_blockers,
                "paper_readiness_status": readiness_summary.get("overall_status"),
                "neutral_publication_route_allowed": neutral_publication_route_allowed,
                "positive_claim_ready_gate_count": positive_ready_gate_count,
                "scoped_or_negative_path_ready_gate_count": scoped_or_negative_gate_count,
                "final_result_disposition_gate_count": final_result_disposition_gate_count,
                "gate_count": gate_count,
            },
            blocker="positive_claim_blockers_not_guarded_for_neutral_route",
        ),
        check_row(
            check_id="paper_gate_execution_queue_empty",
            title="No local paper-gate execution actions are ready",
            status="pass" if ready_action_count == 0 else "blocked",
            evidence_summary=(
                "The local paper-gate execution queue has no ready actions; "
                "remaining blockers are claim/activation blockers, not queued runs."
            ),
            source_artifacts=source_paths(root, PAPER_GATE_CLOSURE_EXECUTION_PLAN),
            metrics={
                "ready_action_count": ready_action_count,
                "action_count": execution_summary.get("action_count"),
                "blocked_action_count": execution_summary.get("blocked_action_count"),
                "next_executable_action_ids": execution_summary.get(
                    "next_executable_action_ids"
                ),
            },
            blocker="paper_gate_execution_queue_not_empty",
        ),
        check_row(
            check_id="final_result_dispositions_available",
            title="Final result dispositions are recorded without requiring positivity",
            status=(
                "pass"
                if gate_count > 0 and final_result_disposition_gate_count == gate_count
                else "blocked"
            ),
            evidence_summary=(
                "Publication preparation must be based on recorded result "
                "dispositions, including scoped, negative, no-claim, or positive "
                "outcomes as observed; positive support is not required by this check."
            ),
            source_artifacts=source_paths(
                root, MANUSCRIPT_BUNDLE_ELIGIBILITY, PAPER_GATE_CLOSURE_MAP
            ),
            metrics={
                "main_results_eligible_count": bundle_summary.get(
                    "main_results_eligible_count"
                ),
                "positive_claim_ready_gate_count": positive_ready_gate_count,
                "scoped_or_negative_path_ready_gate_count": scoped_or_negative_gate_count,
                "final_result_disposition_gate_count": (
                    final_result_disposition_gate_count
                ),
                "gate_count": gate_count,
            },
            blocker="final_result_dispositions_missing",
        ),
        check_row(
            check_id="publication_methodology_has_no_hard_failures",
            title="Publication methodology audit has no hard failures",
            status=(
                "pass"
                if publication_summary.get("overall_status")
                == "publication_workbench_ready_with_caveats"
                and int_value(publication_summary, "failed_check_count") == 0
                and int_value(publication_summary, "unsupported_claim_hits") == 0
                else "blocked"
            ),
            evidence_summary=(
                "The publication workbench can be used as caveated evidence, "
                "but it still records blocked final claims."
            ),
            source_artifacts=source_paths(root, PUBLICATION_METHODOLOGY_AUDIT),
            metrics={
                "publication_methodology_status": publication_summary.get(
                    "overall_status"
                ),
                "failed_check_count": publication_summary.get("failed_check_count"),
                "unsupported_claim_hits": publication_summary.get(
                    "unsupported_claim_hits"
                ),
                "blocked_final_requirement_count": publication_summary.get(
                    "blocked_final_requirement_count"
                ),
            },
            blocker="publication_methodology_hard_failure",
        ),
        check_row(
            check_id="experiment_accounting_complete",
            title="Experiment accounting is complete and reproducible",
            status=(
                "pass"
                if accounting_summary.get("overall_status")
                == "experiment_accounting_pass"
                and int_value(accounting_summary, "failed_check_count") == 0
                else "blocked"
            ),
            evidence_summary=(
                "Ledger accounting passes for raw, canonical, publication, "
                "bounded-support, and Venn-Abers grid rows."
            ),
            source_artifacts=source_paths(root, EXPERIMENT_ACCOUNTING_AUDIT),
            metrics={
                "publication_completed_rows": accounting_summary.get(
                    "publication_completed_rows"
                ),
                "canonical_completed_row_count": accounting_summary.get(
                    "canonical_completed_row_count"
                ),
                "venn_grid_rows_pending": accounting_summary.get(
                    "venn_grid_rows_pending"
                ),
            },
            blocker="experiment_accounting_not_passed",
        ),
        check_row(
            check_id="kg_quality_publication_clean",
            title="Knowledge graph has clean publication-quality evidence",
            status=(
                "pass"
                if kg_quality_clean and kg_publication_clean
                else "caveat"
                if kg_quality_clean and kg_publication_usable_with_caveats
                else "blocked"
            ),
            evidence_summary=kg_publication_evidence_summary,
            source_artifacts=source_paths(
                root, KG_QUALITY_SUMMARY, KG_PUBLICATION_QUALITY_AUDIT
            ),
            metrics={
                "kg_quality_issue_counts": kg_quality.get("issue_counts_by_severity"),
                "kg_node_count": kg_graph.get("node_count"),
                "kg_edge_count": kg_graph.get("edge_count"),
                "kg_publication_status": kg_publication_summary.get("overall_status"),
                "kg_publication_hard_failed_check_count": kg_publication_summary.get(
                    "hard_failed_check_count"
                ),
                "kg_publication_polish_caveat_count": kg_publication_summary.get(
                    "polish_caveat_count"
                ),
            },
            blocker="kg_publication_quality_not_clean",
        ),
        check_row(
            check_id="final_public_release_gate_closed",
            title="Final public release gate remains closed",
            status="caveat" if final_public_release_gate_closed_caveat else "pass",
            evidence_summary=(
                "Private publication preparation may proceed, but final public "
                "release, final-submission prose, and citable repository creation "
                "remain behind explicit downstream authorization."
            ),
            source_artifacts=source_paths(
                root, GOAL_COMPLETION_AUDIT, POST_EXPERIMENT_PUBLICATION_PROGRAM
            ),
            metrics={
                "goal_can_mark_complete": goal_summary.get("can_mark_goal_complete"),
                "manuscript_drafting_authorized": False,
                "sterile_repository_creation_requires_goal_completion": True,
                "public_release_authorized": False,
            },
            blocker="final_public_release_gate_closed",
            required_for="public_release",
        ),
        check_row(
            check_id="scientific_review_no_open_blockers",
            title="Scientific review register has no open hard blockers",
            status=(
                "pass"
                if int_value(scientific_review_summary, "open_blocker_count") == 0
                and int_value(scientific_review_summary, "hard_open_blocker_count")
                == 0
                else "blocked"
            ),
            evidence_summary=(
                "Scientific review findings have no open hard blocker, though "
                "tracked caveats remain part of the evidence boundary."
            ),
            source_artifacts=source_paths(root, SCIENTIFIC_REVIEW_FINDING_REGISTER),
            metrics={
                "scientific_review_status": scientific_review_summary.get(
                    "overall_status"
                ),
                "open_blocker_count": scientific_review_summary.get(
                    "open_blocker_count"
                ),
                "hard_open_blocker_count": scientific_review_summary.get(
                    "hard_open_blocker_count"
                ),
                "tracked_caveat_count": scientific_review_summary.get(
                    "tracked_caveat_count"
                ),
            },
            blocker="scientific_review_open_blockers",
        ),
        check_row(
            check_id="visual_table_audit_final_pass_pending",
            title="Visual/table retention-readiness audit pass is available",
            status="pass" if retention_recommendations_ready else "deferred",
            evidence_summary=(
                "Retention-readiness recommendations are available without "
                "authorizing final retained figures/tables."
                if retention_recommendations_ready
                else "The active preparation phase may inventory and plan visual/table "
                "audits; final retained figure/table selection still waits for "
                "the dedicated audit pass."
            ),
            source_artifacts=source_paths(
                root,
                POST_EXPERIMENT_PUBLICATION_PROGRAM,
                PUBLICATION_RETENTION_READINESS_AUDIT,
            ),
            metrics={
                "visual_quality_check_count": len(
                    visual_audit.get("quality_checks") or []
                ),
                "required_output_artifact_count": len(
                    visual_audit.get("required_output_artifacts") or []
                ),
                "retention_readiness_status": retention_readiness_summary.get(
                    "overall_status"
                ),
                "recommendation_row_count": retention_readiness_summary.get(
                    "recommendation_row_count"
                ),
                "final_visual_table_retention_authorized": (
                    retention_readiness_summary.get(
                        "final_visual_table_retention_authorized"
                    )
                ),
            },
            blocker="visual_table_audit_final_pass_pending",
            required_for="manuscript_drafting",
        ),
        check_row(
            check_id="reviewer_design_reconciliation_pending",
            title="Five-reviewer manuscript design reconciliation is available",
            status="pass" if reviewer_design_reconciled else "deferred",
            evidence_summary=(
                "Five-reviewer design feedback is reconciled for pre-prose "
                "planning without authorizing final manuscript text."
                if reviewer_design_reconciled
                else "Reviewer design packets may be prepared in the active phase; "
                "final manuscript prose waits for reconciled reviewer feedback."
            ),
            source_artifacts=source_paths(
                root,
                POST_EXPERIMENT_PUBLICATION_PROGRAM,
                REVIEWER_DESIGN_BRIEF,
            ),
            metrics={
                "required_reviewer_pass_count": reviewer_gate.get(
                    "required_reviewer_pass_count"
                ),
                "minimum_structured_recommendations_per_reviewer": reviewer_gate.get(
                    "minimum_structured_recommendations_per_reviewer"
                ),
                "required_advice_topic_count": len(
                    reviewer_gate.get("required_advice_topics") or []
                ),
                "reviewer_design_status": reviewer_design_summary.get(
                    "overall_status"
                ),
                "reviewer_count": reviewer_design_summary.get("reviewer_count"),
                "advice_record_count": reviewer_design_summary.get(
                    "advice_record_count"
                ),
            },
            blocker="reviewer_design_reconciliation_pending",
            required_for="manuscript_design",
        ),
        check_row(
            check_id="author_metadata_present",
            title="Individual Experiment Report author metadata is present",
            status=(
                "pass"
                if publication_author.get("author_name") == "Emre Tasar"
                and publication_author.get("author_role") == "Data Scientist"
                and bool(publication_author.get("author_email"))
                else "blocked"
            ),
            evidence_summary=(
                "Author metadata standard is recorded for the future Individual "
                "Experiment Report package."
            ),
            source_artifacts=source_paths(root, POST_EXPERIMENT_PUBLICATION_PROGRAM),
            metrics=publication_author,
            blocker="author_metadata_missing",
        ),
        check_row(
            check_id="sterile_repository_plan_present",
            title="Sterile publication repository plan is present but not activated",
            status=(
                "pass"
                if sterile_repo.get("status") == "planned_after_full_experiment_closure"
                and sterile_repo.get("citation_target")
                == "sterile_publication_repository"
                else "blocked"
            ),
            evidence_summary=(
                "The final citable repository is planned as a separate sterile "
                "private repository after full experiment closure."
            ),
            source_artifacts=source_paths(root, POST_EXPERIMENT_PUBLICATION_PROGRAM),
            metrics={
                "sterile_repository_status": sterile_repo.get("status"),
                "citation_target": sterile_repo.get("citation_target"),
                "required_content_count": len(sterile_repo.get("required_contents") or []),
                "exclusion_rule_count": len(sterile_repo.get("exclusion_rules") or []),
            },
            blocker="sterile_repository_plan_missing",
            required_for="release_packaging",
        ),
    ]

    status_counts = Counter(row["status"] for row in rows)
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    caveat_rows = [row for row in rows if row["status"] == "caveat"]
    deferred_rows = [row for row in rows if row["status"] == "deferred"]

    hard_blocks_absent = len(blocked_rows) == 0
    publication_phase_start_authorized = (
        hard_blocks_absent and kg_publication_usable_with_caveats
    )
    manuscript_design_authorized = publication_phase_start_authorized
    visual_table_audit_authorized = publication_phase_start_authorized
    private_manuscript_drafting_authorized = (
        publication_phase_start_authorized
        and neutral_publication_route_allowed
        and positive_claim_language_blocked
    )
    # Public final-submission prose stays blocked until a later explicit release
    # gate exists; private drafting is tracked separately above.
    manuscript_drafting_authorized = False
    sterile_repository_creation_authorized = (
        publication_phase_start_authorized
        and goal_summary.get("can_mark_goal_complete") is True
    )

    overall_status = (
        "post_experiment_publication_preparation_active_with_caveats"
        if publication_phase_start_authorized and caveat_rows
        else "post_experiment_publication_activation_ready"
        if publication_phase_start_authorized
        else "post_experiment_publication_activation_blocked"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "post_experiment_publication_program_status": post_program.get("status"),
            "publication_phase_start_authorized": publication_phase_start_authorized,
            "publication_preparation_authorized": publication_phase_start_authorized,
            "neutral_empirical_phase_complete": neutral_empirical_phase_complete,
            "neutral_publication_route_allowed": neutral_publication_route_allowed,
            "positive_claim_language_blocked": positive_claim_language_blocked,
            "manuscript_design_authorized": manuscript_design_authorized,
            "private_manuscript_drafting_authorized": (
                private_manuscript_drafting_authorized
            ),
            "manuscript_drafting_authorized": manuscript_drafting_authorized,
            "visual_table_audit_authorized": visual_table_audit_authorized,
            "sterile_repository_creation_authorized": (
                sterile_repository_creation_authorized
            ),
            "activation_check_count": len(rows),
            "pass_check_count": status_counts.get("pass", 0),
            "blocked_check_count": len(blocked_rows),
            "caveat_check_count": len(caveat_rows),
            "deferred_check_count": len(deferred_rows),
            "status_counts": dict(sorted(status_counts.items())),
            "paper_blocked_gate_count": blocked_gate_count,
            "paper_blocked_gate_ids": paper_gate_blockers,
            "paper_gate_closure_ready_action_count": ready_action_count,
            "positive_claim_ready_gate_count": positive_ready_gate_count,
            "scoped_or_negative_path_ready_gate_count": scoped_or_negative_gate_count,
            "final_result_disposition_gate_count": final_result_disposition_gate_count,
            "goal_can_mark_complete": goal_summary.get("can_mark_goal_complete"),
            "goal_neutral_empirical_phase_complete": goal_summary.get(
                "neutral_empirical_phase_complete"
            ),
            "goal_empirical_completion_policy": goal_summary.get(
                "empirical_completion_policy"
            ),
            "goal_noncomplete_requirement_count": goal_summary.get(
                "noncomplete_requirement_count"
            ),
            "publication_completed_rows": accounting_summary.get(
                "publication_completed_rows"
            ),
            "kg_node_count": kg_graph.get("node_count"),
            "kg_edge_count": kg_graph.get("edge_count"),
            "kg_publication_status": kg_publication_summary.get("overall_status"),
            "scientific_review_open_blocker_count": scientific_review_summary.get(
                "open_blocker_count"
            ),
            "closure_check_contract_count": len(
                completion_definition.get("closure_checks") or []
            ),
            "deliverable_count": len(deliverables),
            "required_reviewer_pass_count": reviewer_gate.get(
                "required_reviewer_pass_count"
            ),
            "author_metadata_present": publication_author.get("author_name")
            == "Emre Tasar"
            and bool(publication_author.get("author_email")),
            "sterile_repository_plan_present": bool(sterile_repo),
            "reviewer_design_reconciled": reviewer_design_reconciled,
            "retention_recommendations_ready": retention_recommendations_ready,
            "retention_recommendation_row_count": retention_readiness_summary.get(
                "recommendation_row_count"
            ),
        },
        "activation_decision": {
            "decision": "do_not_start_publication_phase"
            if not publication_phase_start_authorized
            else "publication_preparation_can_start",
            "reason": (
                "The neutral empirical phase is not yet sufficiently verified for "
                "publication preparation."
                if not publication_phase_start_authorized
                else "Neutral empirical completion authorizes pre-prose publication preparation with caveats."
                if caveat_rows
                else "Neutral empirical completion authorizes pre-prose publication preparation."
            ),
            "allowed_current_actions": [
                "maintain and refresh scientific audit artifacts",
                "preserve no-claim and negative-result evidence",
            ]
            + (
                [
                    "start five-reviewer manuscript design packets",
                    "start visual/table inventory and audit planning",
                    "prepare article/supplement/KG/site blueprints without final prose",
                ]
                if publication_phase_start_authorized
                else ["prepare activation evidence without drafting manuscript prose"]
            ),
            "disallowed_current_actions": [
                "write final manuscript prose before reviewer reconciliation",
                "select final publication figures or tables",
                "create the sterile citable repository",
                "promote final winner, fairness, bounded-support, dataset-promotion, or validated Venn-Abers claims",
            ],
        },
        "claim_boundaries": [
            "This audit is a publication-phase stop/go record, not a manuscript draft.",
            "Activated publication preparation authorizes reviewer design and visual/table audit planning, not final prose or release packaging.",
            "Scoped diagnostic and negative evidence can be preserved and later reported as such, but not converted into positive or stronger claims.",
            "A pass on author metadata or sterile repository plan does not authorize repository creation before full experiment closure.",
        ],
        "activation_checks": rows,
        "blocked_conditions": [
            {
                "check_id": row["check_id"],
                "blocker": row["blocker"],
                "evidence_summary": row["evidence_summary"],
                "source_artifacts": row["source_artifacts"],
            }
            for row in blocked_rows
        ],
        "sources": {
            "post_experiment_publication_program": rel(
                root / POST_EXPERIMENT_PUBLICATION_PROGRAM, root
            ),
            "goal_completion_audit": rel(root / GOAL_COMPLETION_AUDIT, root),
            "paper_readiness_map": rel(root / PAPER_READINESS_MAP, root),
            "paper_gate_closure_map": rel(root / PAPER_GATE_CLOSURE_MAP, root),
            "paper_gate_closure_execution_plan": rel(
                root / PAPER_GATE_CLOSURE_EXECUTION_PLAN, root
            ),
            "publication_methodology_audit": rel(
                root / PUBLICATION_METHODOLOGY_AUDIT, root
            ),
            "experiment_accounting_audit": rel(root / EXPERIMENT_ACCOUNTING_AUDIT, root),
            "knowledge_graph_quality_summary": rel(root / KG_QUALITY_SUMMARY, root),
            "kg_publication_quality_audit": rel(
                root / KG_PUBLICATION_QUALITY_AUDIT, root
            ),
            "scientific_review_finding_register": rel(
                root / SCIENTIFIC_REVIEW_FINDING_REGISTER, root
            ),
            "manuscript_bundle_eligibility": rel(
                root / MANUSCRIPT_BUNDLE_ELIGIBILITY, root
            ),
            "reviewer_design_brief": rel(root / REVIEWER_DESIGN_BRIEF, root),
            "publication_retention_readiness_audit": rel(
                root / PUBLICATION_RETENTION_READINESS_AUDIT, root
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    decision = payload["activation_decision"]
    lines = [
        "# Post-Experiment Publication Activation Audit",
        "",
        (
            "This is a stop/go audit. It permits private manuscript drafting only "
            "when the neutral route is active; public final-submission prose stays "
            "behind a later release gate."
        ),
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Decision: `{decision['decision']}`",
        f"- Publication phase start authorized: `{summary['publication_phase_start_authorized']}`",
        f"- Private manuscript drafting authorized: `{summary['private_manuscript_drafting_authorized']}`",
        f"- Public final-submission manuscript drafting authorized: `{summary['manuscript_drafting_authorized']}`",
        f"- Visual/table audit authorized: `{summary['visual_table_audit_authorized']}`",
        f"- Sterile repository creation authorized: `{summary['sterile_repository_creation_authorized']}`",
        f"- Activation checks: {summary['activation_check_count']}",
        f"- Status counts: `{summary['status_counts']}`",
        f"- Paper blocked gates: {summary['paper_blocked_gate_count']} `{summary['paper_blocked_gate_ids']}`",
        f"- Goal can mark complete: `{summary['goal_can_mark_complete']}`",
        f"- KG publication status: `{summary['kg_publication_status']}`",
        "",
        "## Decision Rationale",
        "",
        decision["reason"],
        "",
        "## Activation Checks",
        "",
        "| Check | Status | Blocks activation | Evidence |",
        "|---|---:|---:|---|",
    ]
    for row in payload["activation_checks"]:
        lines.append(
            "| `{check_id}` | `{status}` | `{blocks}` | {evidence} |".format(
                check_id=row["check_id"],
                status=row["status"],
                blocks=row["blocks_activation"],
                evidence=row["evidence_summary"],
            )
        )
    lines.extend(
        [
            "",
            "## Claim Boundaries",
            "",
            *[f"- {item}" for item in payload["claim_boundaries"]],
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root)
    out = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "overall_status": payload["summary"]["overall_status"],
                "blocked_check_count": payload["summary"]["blocked_check_count"],
                "publication_phase_start_authorized": payload["summary"][
                    "publication_phase_start_authorized"
                ],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
