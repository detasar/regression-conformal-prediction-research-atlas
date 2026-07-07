"""Build the neutral final-output authorization protocol.

This artifact translates the active final manuscript/release blockers into a
machine-readable authorization checklist. It distinguishes private review
authoring/package readiness from public release authorization. It does not
authorize public final prose, retain final visual/table artifacts, deploy a
public site, cite the KG as final, make the sterile repository public,
recommend a method, or promote a positive scientific claim.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_final_publication_output_authorization_protocol_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/"
    "final_publication_output_authorization_protocol.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
PROGRESS_RECONCILIATION = Path(
    "experiments/regression/manuscript/"
    "publication_phase_progress_reconciliation_audit.json"
)
RELEASE_GAP = Path(
    "experiments/regression/manuscript/publication_release_gap_register.json"
)
SCIENTIFIC_NEUTRALITY_LOCK = Path(
    "experiments/regression/manuscript/scientific_neutrality_interpretation_lock.json"
)
FINAL_VISUAL_AUDITOR = Path(
    "experiments/regression/manuscript/final_publication_visual_auditor_readiness.json"
)
CLAIM_BOUNDARY = Path(
    "experiments/regression/manuscript/section_claim_boundary_audit.json"
)
NAVIGATION_INDEX = Path(
    "experiments/regression/manuscript/article_supplement_kg_navigation_index.json"
)
PAPER_GATE_CLOSURE = Path(
    "experiments/regression/manuscript/paper_gate_closure_map.json"
)
KG_PUBLICATION = REPORT_DIR / "kg_publication_quality_audit.json"
KG_QUALITY = Path(
    "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
)
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
PUBLICATION_AUTHORING_DECISION = Path(
    "experiments/regression/manuscript/publication_authoring_decision_record.json"
)
PRIVATE_PACKAGE_MANIFEST = Path(
    "experiments/regression/manuscript/private_sterile_publication_package_manifest.json"
)
PRIVATE_REPOSITORY_REMOTE_AUDIT = Path(
    "experiments/regression/manuscript/private_publication_repository_remote_audit.json"
)

SOURCE_PATHS = {
    "goal_completion_audit": GOAL_COMPLETION,
    "publication_phase_progress_reconciliation_audit": PROGRESS_RECONCILIATION,
    "publication_release_gap_register": RELEASE_GAP,
    "scientific_neutrality_interpretation_lock": SCIENTIFIC_NEUTRALITY_LOCK,
    "final_publication_visual_auditor_readiness": FINAL_VISUAL_AUDITOR,
    "section_claim_boundary_audit": CLAIM_BOUNDARY,
    "article_supplement_kg_navigation_index": NAVIGATION_INDEX,
    "paper_gate_closure_map": PAPER_GATE_CLOSURE,
    "kg_publication_quality_audit": KG_PUBLICATION,
    "knowledge_graph_quality_summary": KG_QUALITY,
    "neutral_reporting_language_audit": NEUTRAL_LANGUAGE,
    "publication_authoring_decision_record": PUBLICATION_AUTHORING_DECISION,
    "private_sterile_publication_package_manifest": PRIVATE_PACKAGE_MANIFEST,
    "private_publication_repository_remote_audit": PRIVATE_REPOSITORY_REMOTE_AUDIT,
}

AUTHORIZATION_POLICIES = {
    "final_manuscript_prose_not_authorized": {
        "output_family": "manuscript_prose",
        "required_before_authorization": [
            "goal_can_mark_complete_true_or_explicit_publication_drafting_gate",
            "scientific_neutrality_lock_clean",
            "section_claim_boundaries_clean",
            "final_visual_table_retention_protocol_closed",
            "positive_claim_language_remains_blocked_or_scoped",
        ],
        "allowed_current_action": "write and revise private Research Document, main article, and supplement prose under closed public-release boundaries",
        "blocked_current_action": "treat private review prose as public final manuscript prose or submission-ready final text",
    },
    "final_visual_table_retention_not_authorized": {
        "output_family": "final_visual_table_retention",
        "required_before_authorization": [
            "visual_auditor_feedback_loop_complete",
            "layout_overlap_caption_source_checks_rerun_on_final_formats",
            "claim_boundary_review_complete_for_each_retained_item",
            "final_prose_or_supplement_surface_decision_recorded",
        ],
        "allowed_current_action": "keep draft visual/table candidates and auditor feedback rows",
        "blocked_current_action": "mark any visual or table as final retained",
    },
    "latex_html_authoring_pending": {
        "output_family": "latex_html_manuscript_outputs",
        "required_before_authorization": [
            "final_manuscript_prose_permission_true",
            "final_visual_table_retention_authorized_true",
            "neutral_language_scan_clean_after_render",
            "figure_table_auditor_pass_after_latex_and_html_render",
        ],
        "allowed_current_action": "prepare format requirements and output contracts",
        "blocked_current_action": "create final LaTeX or HTML manuscript outputs",
    },
    "publication_site_deployment_not_authorized": {
        "output_family": "publication_site_deployment",
        "required_before_authorization": [
            "kg_citable_component_authorized_true",
            "private_sterile_repository_ready_and_public_release_authorized_true",
            "site_disclosure_and_release_checklist_complete",
            "working_repository_not_cited_as_final",
        ],
        "allowed_current_action": "maintain the private static review site and release checklist",
        "blocked_current_action": "deploy or publish a publication website",
    },
    "kg_citable_component_not_authorized": {
        "output_family": "knowledge_graph_citation",
        "required_before_authorization": [
            "kg_publication_quality_ready",
            "final_kg_navigation_review_complete",
            "private_release_package_contains_review_kg_snapshot",
            "explicit_kg_publication_authorization_true",
            "kg_claim_boundaries_match_article_and_supplement",
        ],
        "allowed_current_action": "keep the KG as a private navigation and evidence traceability artifact",
        "blocked_current_action": "cite the KG as a final publication component",
    },
    "sterile_repository_creation_not_authorized": {
        "output_family": "public_sterile_publication_repository_release",
        "required_before_authorization": [
            "private_sterile_package_and_remote_audits_pass",
            "explicit_public_repository_release_authorization_true",
            "public_readme_and_reproducibility_manifest_user_approved",
            "working_repository_not_final_citable",
        ],
        "allowed_current_action": "maintain the private sterile publication package and synchronized private repository for review",
        "blocked_current_action": "make the sterile repository public or cite it as the final public repository",
    },
    "sterile_release_packaging_pending": {
        "output_family": "public_release_packaging",
        "required_before_authorization": [
            "private_sterile_package_and_remote_audits_pass",
            "all_article_supplement_kg_artifacts_user_approved",
            "release_manifest_and_checksums_user_approved",
            "citation_and_license_metadata_reviewed",
        ],
        "allowed_current_action": "regenerate and audit the private review package",
        "blocked_current_action": "treat the private review package as an approved final public release bundle",
    },
    "positive_claim_promotion_not_authorized": {
        "output_family": "positive_scientific_claims",
        "required_before_authorization": [
            "positive_claim_ready_gate_count_greater_than_zero_for_the_claim",
            "claim_register_and_source_artifact_support_match",
            "neutral_language_scan_clean_after_claim_text",
            "reviewer_claim_boundary_review_complete",
        ],
        "allowed_current_action": "report observed diagnostic, caveated, scoped, or negative evidence",
        "blocked_current_action": "promote positive performance, fairness, bounded-support, or validation claims",
    },
    "method_recommendation_not_authorized": {
        "output_family": "method_recommendation",
        "required_before_authorization": [
            "final_method_selection_gate_closed",
            "multiplicity_selection_record_consumed_by_final_selection_gate",
            "dataset_and_endpoint_claim_scope_compatible",
            "post_selection_validation_supports_the_intended_claim",
        ],
        "allowed_current_action": "describe CQR/CV+ as diagnostic patterns under blocked final selection",
        "blocked_current_action": "recommend CQR, CV+, Venn-Abers, or any method as generally best",
    },
    "six_positive_claim_gates_blocked": {
        "output_family": "paper_positive_claim_gate_set",
        "required_before_authorization": [
            "dataset_specific_final_gates_ready_or_claim_downgraded",
            "endpoint_bounded_support_gate_ready_or_no_bounded_support_claim",
            "fairness_population_inference_gate_ready_or_diagnostic_scope_only",
            "final_method_model_selection_gate_ready_or_no_recommendation",
            "multiplicity_selection_record_consumed_or_no_winner_language",
            "venn_abers_regression_validation_gate_ready_or_negative_result_only",
        ],
        "allowed_current_action": "use the scoped or negative reporting path already recorded for the current manuscript",
        "blocked_current_action": "open any of the six positive claim families in final prose",
    },
}

AUTHORIZATION_FIELDS = (
    "final_manuscript_prose_permission",
    "manuscript_drafting_authorized",
    "final_visual_table_retention_authorized",
    "latex_html_authoring_authorized",
    "publication_site_deployment_authorized",
    "kg_citable_component_authorized",
    "sterile_repository_creation_authorized",
    "working_repository_final_citable",
    "method_recommendation_authorized",
    "method_champion_authorized",
    "method_advocacy_authorized",
    "positive_claim_promotion_authorized",
)


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


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def source_status(root: Path) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for path in SOURCE_PATHS.values():
        relative = rel(root / path, root)
        if (root / path).exists():
            present.append(relative)
        else:
            missing.append(relative)
    return present, missing


def final_authorization_violations(payloads: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for source_name, payload in payloads.items():
        source_summary = summary(payload)
        for field in AUTHORIZATION_FIELDS:
            if source_summary.get(field) is True:
                violations.append({"source": source_name, "field": field})
    return violations


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


def build_authorization_rows(
    *,
    progress_payload: dict[str, Any],
    progress_summary: dict[str, Any],
    goal_summary: dict[str, Any],
    release_summary: dict[str, Any],
    neutrality_summary: dict[str, Any],
    paper_gate_summary: dict[str, Any],
    final_visual_summary: dict[str, Any],
    present_sources: list[str],
    missing_sources: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    active_rows = [
        row
        for row in progress_payload.get("active_final_blocker_rows") or []
        if isinstance(row, dict) and row.get("blocker_id")
    ]
    for index, active in enumerate(active_rows):
        blocker_id = str(active["blocker_id"])
        policy = AUTHORIZATION_POLICIES.get(blocker_id, {})
        row_missing_policy = not bool(policy)
        rows.append(
            {
                "blocker_id": blocker_id,
                "row_index": index,
                "output_family": policy.get("output_family", "unknown"),
                "authorization_status": (
                    "blocked_no_final_authorization"
                    if not row_missing_policy
                    else "blocked_missing_authorization_policy"
                ),
                "source_traceability_status": (
                    "pass" if not missing_sources else "missing_source_artifact"
                ),
                "active_progress_status": active.get("status"),
                "active_progress_reason": active.get("reason"),
                "required_before_authorization": policy.get(
                    "required_before_authorization", []
                ),
                "allowed_current_action": policy.get("allowed_current_action", ""),
                "blocked_current_action": policy.get("blocked_current_action", ""),
                "current_evidence": {
                    "goal_can_mark_complete": goal_summary.get(
                        "can_mark_goal_complete"
                    ),
                    "neutral_empirical_phase_complete": goal_summary.get(
                        "neutral_empirical_phase_complete"
                    ),
                    "release_authorized_count": release_summary.get(
                        "release_authorized_count"
                    ),
                    "final_visual_auditor_status": final_visual_summary.get(
                        "final_publication_visual_auditor_status"
                    ),
                    "scientific_neutrality_status": neutrality_summary.get(
                        "overall_status"
                    ),
                    "positive_claim_ready_gate_count": paper_gate_summary.get(
                        "positive_claim_ready_gate_count"
                    ),
                    "paper_blocked_gate_count": paper_gate_summary.get(
                        "blocked_gate_count"
                    ),
                    "progress_active_final_blocker_count": progress_summary.get(
                        "active_final_blocker_count"
                    ),
                },
                "source_artifacts": present_sources,
            }
        )
    return rows


def build_payload(root: Path) -> dict[str, Any]:
    payloads = {name: read_json(root / path) for name, path in SOURCE_PATHS.items()}
    present_sources, missing_sources = source_status(root)

    goal_payload = payloads["goal_completion_audit"]
    progress_payload = payloads["publication_phase_progress_reconciliation_audit"]
    release_payload = payloads["publication_release_gap_register"]
    neutrality_payload = payloads["scientific_neutrality_interpretation_lock"]
    final_visual_payload = payloads["final_publication_visual_auditor_readiness"]
    claim_boundary_payload = payloads["section_claim_boundary_audit"]
    navigation_payload = payloads["article_supplement_kg_navigation_index"]
    paper_gate_payload = payloads["paper_gate_closure_map"]
    kg_publication_payload = payloads["kg_publication_quality_audit"]
    neutral_language_payload = payloads["neutral_reporting_language_audit"]
    kg_quality_payload = payloads["knowledge_graph_quality_summary"]
    authoring_decision_payload = payloads["publication_authoring_decision_record"]
    private_package_payload = payloads["private_sterile_publication_package_manifest"]
    remote_audit_payload = payloads["private_publication_repository_remote_audit"]

    goal_summary = summary(goal_payload)
    progress_summary = summary(progress_payload)
    release_summary = summary(release_payload)
    neutrality_summary = summary(neutrality_payload)
    final_visual_summary = summary(final_visual_payload)
    claim_boundary_summary = summary(claim_boundary_payload)
    navigation_summary = summary(navigation_payload)
    paper_gate_summary = summary(paper_gate_payload)
    kg_publication_summary = summary(kg_publication_payload)
    neutral_language_summary = summary(neutral_language_payload)
    authoring_decision_summary = summary(authoring_decision_payload)
    private_package_summary = summary(private_package_payload)
    remote_audit_summary = summary(remote_audit_payload)
    kg_graph = kg_quality_payload.get("graph") or {}
    kg_traceability = kg_quality_payload.get("traceability") or {}
    private_final_prose_authoring_authorized = (
        authoring_decision_summary.get("private_authoring_authorized") is True
        and authoring_decision_summary.get("research_document_authoring_authorized")
        is True
        and authoring_decision_summary.get("minimal_main_broad_supplement_authorized")
        is True
        and authoring_decision_summary.get("final_public_release_authorized") is False
        and authoring_decision_summary.get("public_repository_release_authorized")
        is False
        and authoring_decision_summary.get("method_recommendation_authorized")
        is False
        and authoring_decision_summary.get("positive_claim_promotion_authorized")
        is False
    )
    private_sterile_package_ready = (
        private_package_summary.get("overall_status")
        == "private_sterile_publication_package_ready"
        and safe_int(private_package_summary.get("failed_check_count")) == 0
        and private_package_summary.get("public_release_authorized") is False
        and private_package_summary.get("working_repository_final_citable") is False
        and private_package_summary.get("method_recommendation_authorized") is False
        and private_package_summary.get("positive_claim_promotion_authorized") is False
    )
    private_repository_remote_ready = (
        remote_audit_summary.get("overall_status")
        == "private_publication_repository_remote_ready"
        and safe_int(remote_audit_summary.get("failed_check_count")) == 0
        and remote_audit_summary.get("commit_match") is True
        and remote_audit_summary.get("remote_visibility") == "PRIVATE"
        and remote_audit_summary.get("public_release_authorized") is False
        and remote_audit_summary.get("working_repository_final_citable") is False
        and remote_audit_summary.get("method_recommendation_authorized") is False
        and remote_audit_summary.get("positive_claim_promotion_authorized") is False
    )

    rows = build_authorization_rows(
        progress_payload=progress_payload,
        progress_summary=progress_summary,
        goal_summary=goal_summary,
        release_summary=release_summary,
        neutrality_summary=neutrality_summary,
        paper_gate_summary=paper_gate_summary,
        final_visual_summary=final_visual_summary,
        present_sources=present_sources,
        missing_sources=missing_sources,
    )
    authorization_violations = final_authorization_violations(payloads)
    missing_policy_rows = [
        row["blocker_id"]
        for row in rows
        if row["authorization_status"] == "blocked_missing_authorization_policy"
    ]
    active_blocker_ids = {
        str(row.get("blocker_id"))
        for row in progress_payload.get("active_final_blocker_rows") or []
        if isinstance(row, dict) and row.get("blocker_id")
    }
    expected_blocker_ids = set(AUTHORIZATION_POLICIES)
    unexpected_blockers = sorted(active_blocker_ids - expected_blocker_ids)
    missing_active_blockers = sorted(expected_blocker_ids - active_blocker_ids)

    checks = [
        check_row(
            "all_authorization_protocol_sources_present",
            not missing_sources,
            {"missing_source_artifacts": missing_sources},
            "missing_authorization_protocol_source_artifact",
        ),
        check_row(
            "active_final_blockers_fully_mapped",
            (
                len(rows) == 10
                and not missing_policy_rows
                and not unexpected_blockers
                and not missing_active_blockers
                and safe_int(progress_summary.get("active_final_blocker_count")) == 10
            ),
            {
                "authorization_row_count": len(rows),
                "missing_policy_rows": missing_policy_rows,
                "unexpected_blockers": unexpected_blockers,
                "missing_active_blockers": missing_active_blockers,
                "progress_active_final_blocker_count": progress_summary.get(
                    "active_final_blocker_count"
                ),
            },
            "final_output_blocker_mapping_incomplete",
        ),
        check_row(
            "final_authorizations_remain_closed",
            (
                not authorization_violations
                and release_summary.get("release_authorized_count") == 0
                and progress_summary.get("final_manuscript_prose_permission") is False
                and progress_summary.get("final_visual_table_retention_authorized")
                is False
                and progress_summary.get("latex_html_authoring_authorized") is False
                and progress_summary.get("publication_site_deployment_authorized")
                is False
                and progress_summary.get("kg_citable_component_authorized") is False
                and progress_summary.get("sterile_repository_creation_authorized")
                is False
                and progress_summary.get("method_recommendation_authorized") is False
                and progress_summary.get("positive_claim_promotion_authorized")
                is False
            ),
            {
                "authorization_violations": authorization_violations,
                "release_authorized_count": release_summary.get(
                    "release_authorized_count"
                ),
            },
            "final_output_authorized_too_early",
        ),
        check_row(
            "private_final_prose_authoring_decision_is_scoped",
            private_final_prose_authoring_authorized,
            {
                "authoring_decision_status": authoring_decision_summary.get(
                    "overall_status"
                ),
                "private_authoring_authorized": authoring_decision_summary.get(
                    "private_authoring_authorized"
                ),
                "research_document_authoring_authorized": (
                    authoring_decision_summary.get(
                        "research_document_authoring_authorized"
                    )
                ),
                "minimal_main_broad_supplement_authorized": (
                    authoring_decision_summary.get(
                        "minimal_main_broad_supplement_authorized"
                    )
                ),
                "final_public_release_authorized": authoring_decision_summary.get(
                    "final_public_release_authorized"
                ),
                "method_recommendation_authorized": authoring_decision_summary.get(
                    "method_recommendation_authorized"
                ),
                "positive_claim_promotion_authorized": authoring_decision_summary.get(
                    "positive_claim_promotion_authorized"
                ),
            },
            "private_final_prose_authoring_not_scoped_by_user_decision",
        ),
        check_row(
            "neutral_scientific_policy_locked",
            (
                neutrality_summary.get("overall_status")
                == "scientific_neutrality_interpretation_lock_ready_no_method_promotion"
                and neutrality_summary.get("scientific_test_not_method_promotion")
                is True
                and neutrality_summary.get("analysis_only_no_champion_method")
                is True
                and neutrality_summary.get("method_champion_authorized") is False
                and neutrality_summary.get("method_advocacy_authorized") is False
                and neutrality_summary.get("result_reporting_policy")
                == "analysis_only_report_observed_behavior_no_method_advocacy"
                and neutral_language_summary.get("overall_status")
                == "neutral_reporting_language_audit_pass"
                and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
                and safe_int(neutrality_summary.get("promotional_phrase_hit_count"))
                == 0
            ),
            {
                "scientific_neutrality_status": neutrality_summary.get(
                    "overall_status"
                ),
                "scientific_test_not_method_promotion": neutrality_summary.get(
                    "scientific_test_not_method_promotion"
                ),
                "analysis_only_no_champion_method": neutrality_summary.get(
                    "analysis_only_no_champion_method"
                ),
                "method_champion_authorized": neutrality_summary.get(
                    "method_champion_authorized"
                ),
                "result_reporting_policy": neutrality_summary.get(
                    "result_reporting_policy"
                ),
                "neutral_language_unguarded_hit_count": neutral_language_summary.get(
                    "unguarded_hit_count"
                ),
            },
            "neutral_scientific_policy_not_locked",
        ),
        check_row(
            "positive_claims_remain_scoped_or_negative",
            (
                safe_int(paper_gate_summary.get("blocked_gate_count")) == 6
                and safe_int(paper_gate_summary.get("positive_claim_ready_gate_count"))
                == 0
                and paper_gate_summary.get("venn_abers_negative_result_reporting_ready")
                is True
                and claim_boundary_summary.get("main_results_positive_boundary_blocked")
                is True
                and claim_boundary_summary.get("venn_abers_negative_boundary_preserved")
                is True
            ),
            {
                "blocked_gate_count": paper_gate_summary.get("blocked_gate_count"),
                "positive_claim_ready_gate_count": paper_gate_summary.get(
                    "positive_claim_ready_gate_count"
                ),
                "venn_abers_negative_result_reporting_ready": paper_gate_summary.get(
                    "venn_abers_negative_result_reporting_ready"
                ),
            },
            "positive_claim_gate_opened_without_protocol",
        ),
        check_row(
            "kg_ready_but_not_final_citable",
            (
                navigation_summary.get("overall_status")
                == "article_supplement_kg_navigation_index_ready_no_release"
                and kg_publication_summary.get("overall_status")
                in {"kg_publication_ready", "kg_publication_ready_with_polish_caveats"}
                and safe_int(kg_publication_summary.get("hard_failed_check_count"))
                == 0
                and safe_int(kg_graph.get("isolated_node_count")) == 0
                and float(kg_traceability.get("edge_confidence_coverage") or 0.0)
                == 1.0
                and progress_summary.get("kg_citable_component_authorized") is False
            ),
            {
                "navigation_status": navigation_summary.get("overall_status"),
                "kg_publication_status": kg_publication_summary.get("overall_status"),
                "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
                "kg_citable_component_authorized": progress_summary.get(
                    "kg_citable_component_authorized"
                ),
            },
            "kg_citation_or_quality_boundary_failed",
        ),
        check_row(
            "private_package_and_remote_ready_but_public_release_closed",
            private_sterile_package_ready and private_repository_remote_ready,
            {
                "private_package_status": private_package_summary.get(
                    "overall_status"
                ),
                "private_package_failed_check_count": private_package_summary.get(
                    "failed_check_count"
                ),
                "private_package_public_release_authorized": (
                    private_package_summary.get("public_release_authorized")
                ),
                "remote_audit_status": remote_audit_summary.get("overall_status"),
                "remote_failed_check_count": remote_audit_summary.get(
                    "failed_check_count"
                ),
                "remote_commit_match": remote_audit_summary.get("commit_match"),
                "remote_visibility": remote_audit_summary.get("remote_visibility"),
                "remote_public_release_authorized": remote_audit_summary.get(
                    "public_release_authorized"
                ),
                "remote_repository_url": remote_audit_summary.get(
                    "remote_repository_url"
                ),
            },
            "private_package_or_remote_release_boundary_failed",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    ready = not failed_checks
    row_status_counts = {
        "blocked_no_final_authorization": sum(
            1
            for row in rows
            if row["authorization_status"] == "blocked_no_final_authorization"
        ),
        "blocked_missing_authorization_policy": sum(
            1
            for row in rows
            if row["authorization_status"] == "blocked_missing_authorization_policy"
        ),
    }

    summary_payload = {
        "overall_status": (
            "final_publication_output_authorization_protocol_ready_no_authorizations"
            if ready
            else "final_publication_output_authorization_protocol_blocked"
        ),
        "phase_state": (
            "neutral_final_output_authorization_protocol_defined_outputs_blocked"
        ),
        "final_output_authorization_protocol_status": (
            "protocol_ready_all_final_outputs_blocked"
            if ready
            else "protocol_blocked"
        ),
        "authorization_row_count": len(rows),
        "blocked_authorization_row_count": row_status_counts[
            "blocked_no_final_authorization"
        ],
        "missing_policy_row_count": row_status_counts[
            "blocked_missing_authorization_policy"
        ],
        "ready_to_authorize_output_count": 0,
        "private_final_prose_authoring_authorized": (
            private_final_prose_authoring_authorized
        ),
        "private_main_article_authoring_authorized": (
            private_final_prose_authoring_authorized
        ),
        "private_supplement_authoring_authorized": (
            private_final_prose_authoring_authorized
        ),
        "private_research_document_authoring_authorized": (
            authoring_decision_summary.get("research_document_authoring_authorized")
            is True
        ),
        "private_final_prose_authoring_boundary": (
            "private_review_only_public_release_citation_and_method_recommendation_closed"
        ),
        "private_sterile_publication_package_ready": private_sterile_package_ready,
        "private_publication_repository_remote_ready": (
            private_repository_remote_ready
        ),
        "private_repository_visibility": remote_audit_summary.get("remote_visibility"),
        "private_repository_url": remote_audit_summary.get("remote_repository_url"),
        "public_repository_release_authorized": False,
        "github_pages_publication_authorized": False,
        "kg_public_web_artifact_authorized": False,
        "active_final_blocker_count": safe_int(
            progress_summary.get("active_final_blocker_count")
        ),
        "goal_can_mark_complete": goal_summary.get("can_mark_goal_complete"),
        "neutral_empirical_phase_complete": goal_summary.get(
            "neutral_empirical_phase_complete"
        ),
        "scientific_test_not_method_promotion": neutrality_summary.get(
            "scientific_test_not_method_promotion"
        ),
        "analysis_only_no_champion_method": neutrality_summary.get(
            "analysis_only_no_champion_method"
        ),
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "result_reporting_policy": neutrality_summary.get("result_reporting_policy"),
        "paper_blocked_gate_count": safe_int(paper_gate_summary.get("blocked_gate_count")),
        "positive_claim_ready_gate_count": safe_int(
            paper_gate_summary.get("positive_claim_ready_gate_count")
        ),
        "release_authorized_count": safe_int(release_summary.get("release_authorized_count")),
        "final_manuscript_prose_permission": False,
        "final_visual_table_retention_authorized": False,
        "latex_html_authoring_authorized": False,
        "publication_site_deployment_authorized": False,
        "kg_citable_component_authorized": False,
        "sterile_repository_creation_authorized": False,
        "sterile_repository_publication_authorized": False,
        "sterile_release_package_publication_authorized": False,
        "working_repository_final_citable": False,
        "method_recommendation_authorized": False,
        "positive_claim_promotion_authorized": False,
        "authorization_violation_count": len(authorization_violations),
        "source_artifact_count": len(present_sources),
        "missing_source_artifact_count": len(missing_sources),
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary_payload,
        "authorization_rows": rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This artifact defines authorization criteria only; it does not authorize final outputs.",
            "Private Research Document, main article, and supplement prose authoring is authorized for review only; it is not public release, citation, or final submission authorization.",
            "The current manuscript path remains scientific and neutral: observed evidence may be reported, but no method is recommended.",
            "No method may be framed as the champion, winner, method of choice, or general recommendation; results are analysis-only observations under audited scope.",
            "Positive performance, fairness, bounded-support, final-selection, and Venn-Abers validation claims remain blocked unless their specific gates are reopened with evidence.",
            "The private sterile publication package and synchronized private repository are review-only artifacts; public visibility, GitHub Pages, final citation, and release tagging remain closed.",
            "The working repository is not a final citable artifact.",
        ],
        "sources": {name: rel(root / path, root) for name, path in SOURCE_PATHS.items()},
        "present_source_artifacts": present_sources,
        "missing_source_artifacts": missing_sources,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Final Publication Output Authorization Protocol",
        "",
        "This pre-final artifact maps active final-output blockers to required evidence. It distinguishes private review authoring/package readiness from public release authorization. It does not authorize public final prose, final visuals/tables, public LaTeX/HTML release, KG/site release, public sterile repository release, method recommendation, or positive-claim promotion.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Protocol status: `{summary_payload['final_output_authorization_protocol_status']}`",
        f"- Authorization rows: {summary_payload['authorization_row_count']}",
        f"- Blocked authorization rows: {summary_payload['blocked_authorization_row_count']}",
        f"- Ready-to-authorize outputs: {summary_payload['ready_to_authorize_output_count']}",
        f"- Private final prose authoring authorized: `{summary_payload['private_final_prose_authoring_authorized']}`",
        f"- Private authoring boundary: `{summary_payload['private_final_prose_authoring_boundary']}`",
        f"- Private sterile package ready: `{summary_payload['private_sterile_publication_package_ready']}`",
        f"- Private repository remote ready: `{summary_payload['private_publication_repository_remote_ready']}`",
        f"- Private repository visibility: `{summary_payload['private_repository_visibility']}`",
        f"- Public repository release authorized: `{summary_payload['public_repository_release_authorized']}`",
        f"- GitHub Pages publication authorized: `{summary_payload['github_pages_publication_authorized']}`",
        f"- KG public web artifact authorized: `{summary_payload['kg_public_web_artifact_authorized']}`",
        f"- Active final blockers: {summary_payload['active_final_blocker_count']}",
        f"- Result reporting policy: `{summary_payload['result_reporting_policy']}`",
        f"- Champion method authorized: `{summary_payload['method_champion_authorized']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive-claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Authorization Rows",
        "",
        "| Blocker | Output Family | Status | Blocked Action |",
        "|---|---|---:|---|",
    ]
    for row in payload["authorization_rows"]:
        lines.append(
            "| "
            f"`{row['blocker_id']}` | "
            f"`{row['output_family']}` | "
            f"`{row['authorization_status']}` | "
            f"{row['blocked_current_action']} |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Blocker |",
            "|---|---:|---|",
        ]
    )
    for check in payload["checks"]:
        lines.append(
            f"| `{check['check_id']}` | `{check['status']}` | `{check['blocker']}` |"
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
    print(json.dumps(payload["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
