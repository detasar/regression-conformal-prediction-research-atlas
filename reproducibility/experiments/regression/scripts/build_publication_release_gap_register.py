"""Build the neutral publication release-gap register.

This artifact maps the post-experiment article, supplement, KG/site, individual
report, and sterile repository deliverables to their current evidence gates. It
records private review readiness separately from public release. It does not
authorize public final manuscript prose, choose final retained figures/tables,
deploy a public site, make the private repository public, recommend a method, or
promote a positive scientific claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_publication_release_gap_register_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/publication_release_gap_register.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

POST_PROGRAM = Path("experiments/regression/manuscript/post_experiment_publication_program.json")
GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
ACTIVATION = Path(
    "experiments/regression/manuscript/post_experiment_publication_activation_audit.json"
)
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
PAPER_GATE_CLOSURE = Path("experiments/regression/manuscript/paper_gate_closure_map.json")
BLUEPRINT_ALIGNMENT = Path(
    "experiments/regression/manuscript/article_supplement_blueprint_alignment.json"
)
RETENTION_READINESS = Path(
    "experiments/regression/manuscript/publication_retention_readiness_audit.json"
)
VISUAL_TABLE_AUDIT = Path("experiments/regression/manuscript/visual_table_audit_report.json")
KG_PUBLICATION = REPORT_DIR / "kg_publication_quality_audit.json"
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
AUTHORING_DECISION = Path(
    "experiments/regression/manuscript/publication_authoring_decision_record.json"
)
RELEASE_CUT = Path(
    "experiments/regression/manuscript/neutral_publication_release_cut_decision.json"
)
PRIVATE_LATEX_HTML_MANIFEST = Path(
    "experiments/regression/manuscript/private_latex_html_review_outputs_manifest.json"
)
PRIVATE_LATEX_HTML_AUDIT = Path(
    "experiments/regression/manuscript/private_latex_html_review_output_audit.json"
)
PRIVATE_PACKAGE_MANIFEST = Path(
    "experiments/regression/manuscript/private_sterile_publication_package_manifest.json"
)
PRIVATE_REMOTE_AUDIT = Path(
    "experiments/regression/manuscript/private_publication_repository_remote_audit.json"
)

ARTICLE_DELIVERABLES = {"main_article_latex", "main_article_html"}
SUPPLEMENT_DELIVERABLES = {
    "supplementary_document",
    "supplementary_document_latex",
    "supplementary_document_html",
}
KG_SITE_DELIVERABLES = {
    "navigable_knowledge_graph",
    "github_pages_publication_site",
    "article_supplement_kg_navigation_index",
    "publication_site_html_package",
}
AUTHOR_REPORT_DELIVERABLES = {"individual_experiment_report"}
STERILE_REPO_DELIVERABLES = {"sterile_publication_repository"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary") if isinstance(payload, dict) else {}
    return value if isinstance(value, dict) else {}


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def kg_publication_pre_release_ready(summary_payload: dict[str, Any]) -> bool:
    return (
        summary_payload.get("overall_status")
        in {"kg_publication_ready", "kg_publication_ready_with_polish_caveats"}
        and safe_int(summary_payload.get("hard_failed_check_count")) == 0
    )


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def source_paths(root: Path, *paths: Path) -> list[str]:
    return [rel(root / path, root) for path in paths if (root / path).exists()]


def source_status(root: Path, sources: list[str]) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for source in sources:
        if (root / source).exists():
            present.append(source)
        else:
            missing.append(source)
    return present, missing


def check_row(
    check_id: str,
    passed: bool,
    evidence: dict[str, Any],
    blocker: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "blocker": blocker,
    }


def deliverable_family(deliverable_id: str) -> str:
    if deliverable_id in ARTICLE_DELIVERABLES:
        return "main_article"
    if deliverable_id in SUPPLEMENT_DELIVERABLES:
        return "supplementary_document"
    if deliverable_id in KG_SITE_DELIVERABLES:
        return "kg_or_publication_site"
    if deliverable_id in AUTHOR_REPORT_DELIVERABLES:
        return "individual_experiment_report"
    if deliverable_id in STERILE_REPO_DELIVERABLES:
        return "sterile_publication_repository"
    return "other_publication_deliverable"


def release_blockers_for_family(family: str) -> list[str]:
    base = [
        "goal_not_marked_complete",
        "final_manuscript_prose_not_authorized",
        "positive_claim_promotion_not_authorized",
        "method_recommendation_not_authorized",
    ]
    if family in {"main_article", "supplementary_document", "individual_experiment_report"}:
        return [
            *base,
            "final_visual_table_retention_not_authorized",
            "latex_html_authoring_not_started",
        ]
    if family == "kg_or_publication_site":
        return [
            *base,
            "kg_citable_component_not_authorized",
            "publication_site_deployment_not_authorized",
            "sterile_repository_creation_not_authorized",
        ]
    if family == "sterile_publication_repository":
        return [
            "goal_not_marked_complete",
            "sterile_repository_creation_not_authorized",
            "sterile_release_packaging_not_started",
            "working_repository_not_final_citable",
        ]
    return base


def build_deliverable_rows(
    *,
    root: Path,
    post_program: dict[str, Any],
    activation_summary: dict[str, Any],
    goal_summary: dict[str, Any],
    blueprint_summary: dict[str, Any],
    retention_summary: dict[str, Any],
    kg_publication_summary: dict[str, Any],
    neutral_language_summary: dict[str, Any],
    authoring_summary: dict[str, Any],
    release_cut_summary: dict[str, Any],
    private_latex_html_summary: dict[str, Any],
    private_latex_html_audit_summary: dict[str, Any],
    private_package_summary: dict[str, Any],
    private_remote_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    deliverables = [
        row
        for row in post_program.get("deliverables") or []
        if isinstance(row, dict) and row.get("deliverable_id")
    ]
    for index, deliverable in enumerate(deliverables):
        deliverable_id = str(deliverable["deliverable_id"])
        family = deliverable_family(deliverable_id)
        source_artifacts = source_paths(
            root,
            POST_PROGRAM,
            GOAL_COMPLETION,
            ACTIVATION,
            PAPER_READINESS,
            PAPER_GATE_CLOSURE,
            BLUEPRINT_ALIGNMENT,
            RETENTION_READINESS,
            VISUAL_TABLE_AUDIT,
            KG_PUBLICATION,
            NEUTRAL_LANGUAGE,
            AUTHORING_DECISION,
            RELEASE_CUT,
            PRIVATE_LATEX_HTML_MANIFEST,
            PRIVATE_LATEX_HTML_AUDIT,
            PRIVATE_PACKAGE_MANIFEST,
            PRIVATE_REMOTE_AUDIT,
        )
        present_sources, missing_sources = source_status(root, source_artifacts)
        release_blockers = release_blockers_for_family(family)
        pre_prose_evidence_ready = (
            activation_summary.get("publication_preparation_authorized") is True
            and activation_summary.get("manuscript_drafting_authorized") is False
            and blueprint_summary.get("overall_status")
            == "article_supplement_blueprint_alignment_ready_no_final_prose_no_method_promotion"
            and retention_summary.get("overall_status")
            == "publication_retention_readiness_ready_no_final_prose"
            and neutral_language_summary.get("overall_status")
            == "neutral_reporting_language_audit_pass"
            and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
            and not missing_sources
        )
        if family == "kg_or_publication_site":
            pre_prose_evidence_ready = pre_prose_evidence_ready and (
                kg_publication_pre_release_ready(kg_publication_summary)
            )
        if family == "sterile_publication_repository":
            sterile_plan = post_program.get("sterile_publication_repository_plan") or {}
            pre_prose_evidence_ready = (
                sterile_plan.get("status") == "planned_after_full_experiment_closure"
                and bool(sterile_plan.get("required_contents"))
                and bool(sterile_plan.get("exclusion_rules"))
            )
        private_authoring_ready = (
            authoring_summary.get("private_authoring_authorized") is True
            and authoring_summary.get("research_document_authoring_authorized") is True
            and authoring_summary.get("minimal_main_broad_supplement_authorized") is True
        )
        private_latex_html_ready = (
            release_cut_summary.get("neutral_latex_html_static_site_package_authorized")
            is True
            and private_latex_html_summary.get("overall_status")
            == "private_latex_html_review_outputs_ready"
            and private_latex_html_audit_summary.get("overall_status")
            == "private_latex_html_review_output_audit_pass"
        )
        private_package_ready = (
            private_package_summary.get("overall_status")
            == "private_sterile_publication_package_ready"
        )
        private_remote_ready = (
            private_remote_summary.get("overall_status")
            == "private_publication_repository_remote_ready"
            and private_remote_summary.get("remote_visibility") == "PRIVATE"
            and private_remote_summary.get("commit_match") is True
        )
        private_review_artifact_ready = private_package_ready and private_remote_ready
        rows.append(
            {
                "deliverable_id": deliverable_id,
                "row_index": index,
                "family": family,
                "format": deliverable.get("format"),
                "description": deliverable.get("description"),
                "pre_prose_evidence_ready": pre_prose_evidence_ready,
                "private_authoring_ready": private_authoring_ready,
                "private_latex_html_review_outputs_ready": private_latex_html_ready,
                "private_review_artifact_ready": private_review_artifact_ready,
                "release_status": "release_blocked_pre_prose_candidate_ready"
                if pre_prose_evidence_ready
                else "release_blocked_missing_pre_prose_evidence",
                "release_authorized": False,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "method_recommendation_authorized": False,
                "working_repository_final_citable": False,
                "release_blockers": release_blockers,
                "release_blocker_count": len(release_blockers),
                "source_artifacts": present_sources,
                "missing_source_artifacts": missing_sources,
                "source_traceability_status": "pass" if not missing_sources else "fail",
                "claim_boundary": (
                    "Publication deliverable is tracked only as a pre-prose "
                    "release gap. It cannot be released, cited, or used to "
                    "recommend a conformal method until downstream gates pass."
                ),
                "evidence_metrics": {
                    "goal_can_mark_complete": goal_summary.get("can_mark_goal_complete"),
                    "paper_blocked_gate_count": goal_summary.get("paper_blocked_gate_count"),
                    "positive_claim_blocking_gate_count": goal_summary.get(
                        "positive_claim_blocking_gate_count"
                    ),
                    "publication_preparation_authorized": activation_summary.get(
                        "publication_preparation_authorized"
                    ),
                    "manuscript_drafting_authorized": activation_summary.get(
                        "manuscript_drafting_authorized"
                    ),
                    "sterile_repository_creation_authorized": activation_summary.get(
                        "sterile_repository_creation_authorized"
                    ),
                    "private_authoring_authorized": authoring_summary.get(
                        "private_authoring_authorized"
                    ),
                    "private_latex_html_outputs_status": (
                        private_latex_html_summary.get("overall_status")
                    ),
                    "private_latex_html_output_audit_status": (
                        private_latex_html_audit_summary.get("overall_status")
                    ),
                    "private_package_status": private_package_summary.get(
                        "overall_status"
                    ),
                    "private_repository_remote_status": private_remote_summary.get(
                        "overall_status"
                    ),
                    "private_repository_visibility": private_remote_summary.get(
                        "remote_visibility"
                    ),
                },
            }
        )
    return rows


def build_payload(root: Path) -> dict[str, Any]:
    post_program = read_json(root / POST_PROGRAM)
    goal = read_json(root / GOAL_COMPLETION)
    activation = read_json(root / ACTIVATION)
    readiness = read_json(root / PAPER_READINESS)
    closure = read_json(root / PAPER_GATE_CLOSURE)
    blueprint = read_json(root / BLUEPRINT_ALIGNMENT)
    retention = read_json(root / RETENTION_READINESS)
    visual_audit = read_json(root / VISUAL_TABLE_AUDIT)
    kg_publication = read_json(root / KG_PUBLICATION)
    neutral_language = read_json(root / NEUTRAL_LANGUAGE)
    authoring_decision = read_json(root / AUTHORING_DECISION)
    release_cut = read_json(root / RELEASE_CUT)
    private_latex_html = read_json(root / PRIVATE_LATEX_HTML_MANIFEST)
    private_latex_html_audit = read_json(root / PRIVATE_LATEX_HTML_AUDIT)
    private_package = read_json(root / PRIVATE_PACKAGE_MANIFEST)
    private_remote = read_json(root / PRIVATE_REMOTE_AUDIT)

    goal_summary = summary(goal)
    activation_summary = summary(activation)
    readiness_summary = summary(readiness)
    closure_summary = summary(closure)
    blueprint_summary = summary(blueprint)
    retention_summary = summary(retention)
    visual_audit_summary = summary(visual_audit)
    kg_publication_summary = summary(kg_publication)
    neutral_language_summary = summary(neutral_language)
    authoring_summary = summary(authoring_decision)
    release_cut_summary = summary(release_cut)
    private_latex_html_summary = summary(private_latex_html)
    private_latex_html_audit_summary = summary(private_latex_html_audit)
    private_package_summary = summary(private_package)
    private_remote_summary = summary(private_remote)

    rows = build_deliverable_rows(
        root=root,
        post_program=post_program,
        activation_summary=activation_summary,
        goal_summary=goal_summary,
        blueprint_summary=blueprint_summary,
        retention_summary=retention_summary,
        kg_publication_summary=kg_publication_summary,
        neutral_language_summary=neutral_language_summary,
        authoring_summary=authoring_summary,
        release_cut_summary=release_cut_summary,
        private_latex_html_summary=private_latex_html_summary,
        private_latex_html_audit_summary=private_latex_html_audit_summary,
        private_package_summary=private_package_summary,
        private_remote_summary=private_remote_summary,
    )
    family_counts = Counter(row["family"] for row in rows)
    release_status_counts = Counter(row["release_status"] for row in rows)
    missing_source_count = sum(len(row["missing_source_artifacts"]) for row in rows)
    release_authorized_count = sum(row["release_authorized"] is True for row in rows)
    final_authorization_count = sum(
        row["final_manuscript_prose_permission"]
        or row["final_visual_table_retention_authorized"]
        or row["publication_site_deployment_authorized"]
        or row["kg_citable_component_authorized"]
        or row["sterile_repository_creation_authorized"]
        or row["positive_claim_promotion_authorized"]
        or row["method_recommendation_authorized"]
        for row in rows
    )
    sterile_plan = post_program.get("sterile_publication_repository_plan") or {}
    author = post_program.get("publication_author") or {}
    private_authoring_ready = (
        authoring_summary.get("private_authoring_authorized") is True
        and authoring_summary.get("research_document_authoring_authorized") is True
        and authoring_summary.get("minimal_main_broad_supplement_authorized") is True
    )
    private_latex_html_ready = (
        release_cut_summary.get("neutral_latex_html_static_site_package_authorized")
        is True
        and private_latex_html_summary.get("overall_status")
        == "private_latex_html_review_outputs_ready"
        and private_latex_html_audit_summary.get("overall_status")
        == "private_latex_html_review_output_audit_pass"
    )
    private_package_ready = (
        private_package_summary.get("overall_status")
        == "private_sterile_publication_package_ready"
    )
    private_remote_ready = (
        private_remote_summary.get("overall_status")
        == "private_publication_repository_remote_ready"
        and private_remote_summary.get("remote_visibility") == "PRIVATE"
        and private_remote_summary.get("commit_match") is True
    )
    checks = [
        check_row(
            "publication_program_active",
            post_program.get("status") == "neutral_publication_preparation_active"
            and len(rows) == 11,
            {
                "program_status": post_program.get("status"),
                "deliverable_row_count": len(rows),
            },
            "publication_program_not_active_or_deliverables_missing",
        ),
        check_row(
            "goal_not_prematurely_complete",
            goal_summary.get("can_mark_goal_complete") is False
            and safe_int(goal_summary.get("noncomplete_requirement_count")) >= 1,
            {
                "can_mark_goal_complete": goal_summary.get("can_mark_goal_complete"),
                "noncomplete_requirement_count": goal_summary.get(
                    "noncomplete_requirement_count"
                ),
            },
            "goal_completion_status_unexpected_for_release_gap_register",
        ),
        check_row(
            "activation_is_pre_prose_only",
            activation_summary.get("publication_preparation_authorized") is True
            and activation_summary.get("manuscript_drafting_authorized") is False
            and activation_summary.get("sterile_repository_creation_authorized") is False
            and safe_int(activation_summary.get("blocked_check_count")) == 0,
            {
                "activation_status": activation_summary.get("overall_status"),
                "publication_preparation_authorized": activation_summary.get(
                    "publication_preparation_authorized"
                ),
                "manuscript_drafting_authorized": activation_summary.get(
                    "manuscript_drafting_authorized"
                ),
                "sterile_repository_creation_authorized": activation_summary.get(
                    "sterile_repository_creation_authorized"
                ),
            },
            "publication_activation_not_pre_prose_only",
        ),
        check_row(
            "private_review_artifacts_ready_but_not_public",
            private_authoring_ready
            and private_latex_html_ready
            and private_package_ready
            and private_remote_ready
            and private_package_summary.get("public_release_authorized") is False
            and private_remote_summary.get("public_release_authorized") is False,
            {
                "private_authoring_ready": private_authoring_ready,
                "private_latex_html_ready": private_latex_html_ready,
                "private_package_status": private_package_summary.get(
                    "overall_status"
                ),
                "private_remote_status": private_remote_summary.get("overall_status"),
                "private_remote_visibility": private_remote_summary.get(
                    "remote_visibility"
                ),
                "private_package_public_release_authorized": (
                    private_package_summary.get("public_release_authorized")
                ),
                "private_remote_public_release_authorized": (
                    private_remote_summary.get("public_release_authorized")
                ),
            },
            "private_review_artifact_status_missing_or_public",
        ),
        check_row(
            "paper_gates_block_positive_claims",
            readiness_summary.get("overall_status") == "paper_readiness_blocked_with_evidence_map"
            and safe_int(readiness_summary.get("blocked_gate_count")) == 6
            and safe_int(closure_summary.get("positive_claim_ready_gate_count")) == 0,
            {
                "paper_readiness_status": readiness_summary.get("overall_status"),
                "blocked_gate_count": readiness_summary.get("blocked_gate_count"),
                "positive_claim_ready_gate_count": closure_summary.get(
                    "positive_claim_ready_gate_count"
                ),
            },
            "positive_claim_gates_not_guarded",
        ),
        check_row(
            "blueprint_and_retention_are_pre_prose",
            blueprint_summary.get("overall_status")
            == "article_supplement_blueprint_alignment_ready_no_final_prose_no_method_promotion"
            and retention_summary.get("overall_status")
            == "publication_retention_readiness_ready_no_final_prose"
            and blueprint_summary.get("final_manuscript_prose_permission") is False
            and retention_summary.get("final_manuscript_prose_permission") is False,
            {
                "blueprint_status": blueprint_summary.get("overall_status"),
                "retention_status": retention_summary.get("overall_status"),
                "blueprint_final_prose": blueprint_summary.get(
                    "final_manuscript_prose_permission"
                ),
                "retention_final_prose": retention_summary.get(
                    "final_manuscript_prose_permission"
                ),
            },
            "blueprint_or_retention_started_final_prose",
        ),
        check_row(
            "visual_and_kg_release_not_authorized",
            visual_audit_summary.get("final_visual_table_retention_authorized") is False
            and visual_audit_summary.get("kg_citable_component_authorized") is False
            and kg_publication_pre_release_ready(kg_publication_summary),
            {
                "visual_audit_status": visual_audit_summary.get("overall_status"),
                "final_visual_table_retention_authorized": visual_audit_summary.get(
                    "final_visual_table_retention_authorized"
                ),
                "kg_citable_component_authorized": visual_audit_summary.get(
                    "kg_citable_component_authorized"
                ),
                "kg_publication_status": kg_publication_summary.get("overall_status"),
            },
            "visual_or_kg_release_authorized_too_early",
        ),
        check_row(
            "sterile_repository_deferred_with_plan",
            sterile_plan.get("status") == "planned_after_full_experiment_closure"
            and sterile_plan.get("repository_visibility_at_creation") == "private"
            and bool(sterile_plan.get("required_contents"))
            and bool(sterile_plan.get("exclusion_rules")),
            {
                "sterile_repository_status": sterile_plan.get("status"),
                "repository_visibility_at_creation": sterile_plan.get(
                    "repository_visibility_at_creation"
                ),
                "required_content_count": len(sterile_plan.get("required_contents") or []),
                "exclusion_rule_count": len(sterile_plan.get("exclusion_rules") or []),
            },
            "sterile_repository_plan_missing_or_not_deferred",
        ),
        check_row(
            "author_metadata_available_for_later_report",
            author.get("author_name") == "Emre Tasar"
            and author.get("author_role") == "Data Scientist"
            and bool(author.get("author_email")),
            {
                "author_name": author.get("author_name"),
                "author_role": author.get("author_role"),
                "author_email_present": bool(author.get("author_email")),
            },
            "author_metadata_missing",
        ),
        check_row(
            "neutral_language_and_no_method_promotion",
            neutral_language_summary.get("overall_status") == "neutral_reporting_language_audit_pass"
            and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
            and release_authorized_count == 0
            and final_authorization_count == 0,
            {
                "neutral_language_status": neutral_language_summary.get("overall_status"),
                "unguarded_hit_count": neutral_language_summary.get("unguarded_hit_count"),
                "release_authorized_count": release_authorized_count,
                "final_authorization_count": final_authorization_count,
            },
            "neutral_language_or_no_promotion_guard_failed",
        ),
        check_row(
            "all_deliverable_rows_source_traceable",
            missing_source_count == 0
            and all(row["source_traceability_status"] == "pass" for row in rows),
            {
                "deliverable_row_count": len(rows),
                "source_traceable_row_count": sum(
                    row["source_traceability_status"] == "pass" for row in rows
                ),
                "missing_source_artifact_count": missing_source_count,
            },
            "deliverable_row_source_traceability_missing",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    failed_check_count = len(failed_checks)
    overall_status = (
        "publication_release_gap_register_ready_no_final_release"
        if failed_check_count == 0
        else "publication_release_gap_register_blocked"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "phase_state": (
                "neutral_pre_release_gap_register_active_final_release_blocked"
            ),
            "deliverable_row_count": len(rows),
            "deliverable_family_counts": dict(sorted(family_counts.items())),
            "release_status_counts": dict(sorted(release_status_counts.items())),
            "pre_prose_evidence_ready_row_count": sum(
                row["pre_prose_evidence_ready"] for row in rows
            ),
            "release_authorized_count": release_authorized_count,
            "blocked_release_row_count": sum(
                row["release_authorized"] is False for row in rows
            ),
            "source_traceable_row_count": sum(
                row["source_traceability_status"] == "pass" for row in rows
            ),
            "missing_source_artifact_count": missing_source_count,
            "goal_can_mark_complete": goal_summary.get("can_mark_goal_complete"),
            "noncomplete_requirement_count": goal_summary.get(
                "noncomplete_requirement_count"
            ),
            "paper_blocked_gate_count": readiness_summary.get("blocked_gate_count"),
            "positive_claim_ready_gate_count": closure_summary.get(
                "positive_claim_ready_gate_count"
            ),
            "publication_preparation_authorized": activation_summary.get(
                "publication_preparation_authorized"
            ),
            "private_authoring_authorized": authoring_summary.get(
                "private_authoring_authorized"
            ),
            "research_document_authoring_authorized": authoring_summary.get(
                "research_document_authoring_authorized"
            ),
            "minimal_main_broad_supplement_authorized": authoring_summary.get(
                "minimal_main_broad_supplement_authorized"
            ),
            "private_latex_html_review_outputs_ready": private_latex_html_ready,
            "private_latex_html_review_output_audit_pass": (
                private_latex_html_audit_summary.get("overall_status")
                == "private_latex_html_review_output_audit_pass"
            ),
            "private_sterile_publication_package_ready": private_package_ready,
            "private_publication_repository_remote_ready": private_remote_ready,
            "private_publication_repository_visibility": private_remote_summary.get(
                "remote_visibility"
            ),
            "private_publication_repository_commit_match": private_remote_summary.get(
                "commit_match"
            ),
            "private_review_artifact_ready_row_count": sum(
                row["private_review_artifact_ready"] for row in rows
            ),
            "final_manuscript_prose_permission": False,
            "final_visual_table_retention_authorized": False,
            "publication_site_deployment_authorized": False,
            "kg_citable_component_authorized": False,
            "sterile_repository_creation_authorized": False,
            "positive_claim_promotion_authorized": False,
            "method_recommendation_authorized": False,
            "working_repository_final_citable": False,
            "sterile_repository_status": sterile_plan.get("status"),
            "author_metadata_present": bool(author.get("author_email")),
            "neutral_language_unguarded_hit_count": neutral_language_summary.get(
                "unguarded_hit_count"
            ),
            "scientific_no_method_promotion_guard_active": True,
            "check_count": len(checks),
            "failed_check_count": failed_check_count,
        },
        "claim_boundaries": [
            "This register tracks public release gaps and private review readiness; it is not final public manuscript prose.",
            "Every deliverable row remains blocked for public release until downstream final-prose, visual/table retention, KG/site, sterile repository-publication, and citation gates pass or are explicitly rescoped.",
            "Private authoring, private LaTeX/HTML review outputs, and the private sterile package may be ready without making any artifact public or citable.",
            "The working repository is not the final citable repository.",
            "CQR/CV+ and Venn-Abers may only be reported under existing neutral result boundaries; no method recommendation is authorized here.",
            "Venn-Abers regression remains observed negative/failure-mode evidence with no validated regression claim.",
        ],
        "checks": checks,
        "failed_checks": failed_checks,
        "deliverable_rows": rows,
        "sources": {
            "post_experiment_publication_program": rel(root / POST_PROGRAM, root),
            "goal_completion_audit": rel(root / GOAL_COMPLETION, root),
            "post_experiment_publication_activation_audit": rel(root / ACTIVATION, root),
            "paper_readiness_map": rel(root / PAPER_READINESS, root),
            "paper_gate_closure_map": rel(root / PAPER_GATE_CLOSURE, root),
            "article_supplement_blueprint_alignment": rel(
                root / BLUEPRINT_ALIGNMENT, root
            ),
            "publication_retention_readiness_audit": rel(root / RETENTION_READINESS, root),
            "visual_table_audit_report": rel(root / VISUAL_TABLE_AUDIT, root),
            "kg_publication_quality_audit": rel(root / KG_PUBLICATION, root),
            "neutral_reporting_language_audit": rel(root / NEUTRAL_LANGUAGE, root),
            "publication_authoring_decision_record": rel(
                root / AUTHORING_DECISION, root
            ),
            "neutral_publication_release_cut_decision": rel(root / RELEASE_CUT, root),
            "private_latex_html_review_outputs_manifest": rel(
                root / PRIVATE_LATEX_HTML_MANIFEST, root
            ),
            "private_latex_html_review_output_audit": rel(
                root / PRIVATE_LATEX_HTML_AUDIT, root
            ),
            "private_sterile_publication_package_manifest": rel(
                root / PRIVATE_PACKAGE_MANIFEST, root
            ),
            "private_publication_repository_remote_audit": rel(
                root / PRIVATE_REMOTE_AUDIT, root
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Publication Release Gap Register",
        "",
        "This is a neutral release-gap register. It records private review readiness while keeping public release closed. It does not authorize public final manuscript prose, choose retained visuals, deploy a public site, make the private repository public, cite this working repository, recommend a conformal method, or promote a positive claim.",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase state: `{summary_payload['phase_state']}`",
        f"- Deliverable rows: {summary_payload['deliverable_row_count']}",
        f"- Pre-prose evidence-ready rows: {summary_payload['pre_prose_evidence_ready_row_count']}",
        f"- Release-authorized rows: {summary_payload['release_authorized_count']}",
        f"- Blocked release rows: {summary_payload['blocked_release_row_count']}",
        f"- Paper blocked gates: {summary_payload['paper_blocked_gate_count']}",
        f"- Positive-claim ready gates: {summary_payload['positive_claim_ready_gate_count']}",
        f"- Private authoring authorized: `{summary_payload['private_authoring_authorized']}`",
        f"- Private LaTeX/HTML review outputs ready: `{summary_payload['private_latex_html_review_outputs_ready']}`",
        f"- Private sterile package ready: `{summary_payload['private_sterile_publication_package_ready']}`",
        f"- Private repository remote ready: `{summary_payload['private_publication_repository_remote_ready']}`",
        f"- Final manuscript prose permission: `{summary_payload['final_manuscript_prose_permission']}`",
        f"- Sterile repository creation authorized: `{summary_payload['sterile_repository_creation_authorized']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        "",
        "## Private Review Readiness",
        "",
        "| Item | Status |",
        "|---|---:|",
        f"| Private authoring authorized | `{summary_payload['private_authoring_authorized']}` |",
        f"| Research Document authoring authorized | `{summary_payload['research_document_authoring_authorized']}` |",
        f"| Minimal main + broad supplement authorized | `{summary_payload['minimal_main_broad_supplement_authorized']}` |",
        f"| Private LaTeX/HTML review outputs ready | `{summary_payload['private_latex_html_review_outputs_ready']}` |",
        f"| Private LaTeX/HTML review output audit pass | `{summary_payload['private_latex_html_review_output_audit_pass']}` |",
        f"| Private sterile package ready | `{summary_payload['private_sterile_publication_package_ready']}` |",
        f"| Private repository remote ready | `{summary_payload['private_publication_repository_remote_ready']}` |",
        f"| Private repository visibility | `{summary_payload['private_publication_repository_visibility']}` |",
        f"| Private repository commit match | `{summary_payload['private_publication_repository_commit_match']}` |",
        "",
        "## Deliverable Rows",
        "",
        "| Deliverable | Family | Format | Pre-prose ready | Release authorized | Blockers |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in payload["deliverable_rows"]:
        lines.append(
            "| `{deliverable}` | `{family}` | `{fmt}` | `{ready}` | `{release}` | {blockers} |".format(
                deliverable=row["deliverable_id"],
                family=row["family"],
                fmt=row["format"],
                ready=row["pre_prose_evidence_ready"],
                release=row["release_authorized"],
                blockers=row["release_blocker_count"],
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Blocker |", "|---|---:|---|"])
    for check in payload["checks"]:
        lines.append(
            f"| `{check['check_id']}` | `{check['status']}` | `{check['blocker']}` |"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root)
    out = Path(args.out)
    out = out if out.is_absolute() else root / out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "overall_status": payload["summary"]["overall_status"],
                "deliverable_row_count": payload["summary"]["deliverable_row_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
