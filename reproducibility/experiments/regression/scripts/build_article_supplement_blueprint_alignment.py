"""Build a neutral article/supplement/KG blueprint-alignment audit.

This artifact sits after reviewer design, visual/table retention-readiness,
and the neutral result ledger.  It aligns candidate paper surfaces to source
artifacts and claim boundaries without writing final manuscript prose, choosing
retained figures/tables, deploying a site, creating the sterile repository, or
promoting any conformal method.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_article_supplement_blueprint_alignment_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/article_supplement_blueprint_alignment.json"
)

REVIEWER_DESIGN = Path("experiments/regression/manuscript/reviewer_design_brief.json")
CONTENT_MATRIX = Path(
    "experiments/regression/manuscript/article_supplement_content_matrix.json"
)
RETENTION_AUDIT = Path(
    "experiments/regression/manuscript/publication_retention_readiness_audit.json"
)
RETENTION_MATRIX = Path(
    "experiments/regression/manuscript/"
    "article_supplement_retention_recommendation_matrix.json"
)
NEUTRAL_LEDGER = Path("experiments/regression/manuscript/neutral_result_ledger.json")
PUBLICATION_ACTIVATION = Path(
    "experiments/regression/manuscript/post_experiment_publication_activation_audit.json"
)
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
PAPER_GATE_CLOSURE = Path(
    "experiments/regression/manuscript/paper_gate_closure_map.json"
)
NEUTRAL_LANGUAGE = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "neutral_reporting_language_audit.json"
)


RESULT_LINKS_BY_CONTENT_ID = {
    "experiment_scope_and_accounting_table": ["empirical_scope_accounting"],
    "method_performance_descriptive_summary": [
        "method_performance_descriptive_frontier"
    ],
    "method_selection_robustness_diagnostics": [
        "selection_multiplicity_robustness_diagnostic"
    ],
    "post_selection_validation_diagnostics": [
        "selection_multiplicity_robustness_diagnostic"
    ],
    "venn_abers_failure_mode_evidence": [
        "venn_abers_regression_negative_evidence"
    ],
    "bounded_support_endpoint_policy_table": [
        "bounded_support_endpoint_no_validity_claim"
    ],
    "fairness_group_diagnostic_tables": [
        "fairness_group_diagnostic_no_population_claim"
    ],
    "duplicate_split_caveat_inventory": ["neutral_publication_policy_no_promotion"],
    "knowledge_graph_navigation_quality": [
        "knowledge_graph_navigation_release_blocked"
    ],
    "neutral_closure_and_claim_boundary_table": [
        "neutral_publication_policy_no_promotion"
    ],
}

SCIENTIFIC_ROLE_BY_CONTENT_ID = {
    "experiment_scope_and_accounting_table": "empirical_scope_accounting_only",
    "method_performance_descriptive_summary": (
        "descriptive_method_behavior_no_final_selection"
    ),
    "method_selection_robustness_diagnostics": (
        "selection_robustness_diagnostic_no_final_winner"
    ),
    "post_selection_validation_diagnostics": (
        "post_selection_diagnostic_no_final_winner"
    ),
    "venn_abers_failure_mode_evidence": (
        "negative_failure_mode_no_validated_regression_claim"
    ),
    "bounded_support_endpoint_policy_table": (
        "bounded_support_endpoint_blocker_no_validity_claim"
    ),
    "fairness_group_diagnostic_tables": (
        "fairness_group_diagnostic_no_population_claim"
    ),
    "duplicate_split_caveat_inventory": (
        "integrity_caveat_inventory_no_claim_strengthening"
    ),
    "knowledge_graph_navigation_quality": (
        "kg_navigation_candidate_release_blocked"
    ),
    "neutral_closure_and_claim_boundary_table": (
        "claim_boundary_register_no_positive_claim_conversion"
    ),
}

EXPLICIT_NO_DIRECT_ADVICE_RATIONALE = {
    "post_selection_validation_diagnostics": (
        "No direct reviewer visual-family row targets this content area. It is "
        "retained as a supplement-only diagnostic because reviewer advice "
        "requires post-selection evidence to remain no-final-selection evidence "
        "and the retention matrix supplies source-traceable placement."
    )
}


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


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def content_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    rows = payload.get("article_supplement_content_matrix")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def retention_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("recommendation_rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def result_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("result_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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


def advice_records_by_content(
    advice_records: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_content: dict[str, list[dict[str, Any]]] = {}
    for advice in advice_records:
        for content_id in advice.get("visual_family_ids") or []:
            by_content.setdefault(str(content_id), []).append(advice)
    return by_content


def build_alignment_rows(
    *,
    root: Path,
    content_payload: dict[str, Any],
    reviewer_payload: dict[str, Any],
    retention_payload: dict[str, Any],
    ledger_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    advice_by_content = advice_records_by_content(
        [
            row
            for row in reviewer_payload.get("reviewer_advice_records") or []
            if isinstance(row, dict)
        ]
    )
    retention_by_content = {
        str(row.get("content_area_id")): row
        for row in retention_rows(retention_payload)
        if row.get("content_area_id")
    }
    ledger_by_result = {
        str(row.get("result_id")): row
        for row in result_rows(ledger_payload)
        if row.get("result_id")
    }

    rows: list[dict[str, Any]] = []
    for index, content in enumerate(content_rows(content_payload)):
        content_id = str(content.get("content_area_id") or "").strip()
        if not content_id:
            continue
        advice = advice_by_content.get(content_id, [])
        retention = retention_by_content.get(content_id, {})
        result_ids = RESULT_LINKS_BY_CONTENT_ID.get(content_id, [])
        linked_results = [ledger_by_result[result_id] for result_id in result_ids if result_id in ledger_by_result]
        source_artifacts = list(
            dict.fromkeys(
                [
                    *(content.get("source_artifacts") or []),
                    *(retention.get("source_artifacts") or []),
                    str(CONTENT_MATRIX),
                    str(REVIEWER_DESIGN),
                    str(RETENTION_AUDIT),
                    str(RETENTION_MATRIX),
                    str(NEUTRAL_LEDGER),
                    str(PUBLICATION_ACTIVATION),
                    str(PAPER_READINESS),
                    str(PAPER_GATE_CLOSURE),
                    str(NEUTRAL_LANGUAGE),
                ]
            )
        )
        present_sources, missing_sources = source_status(root, source_artifacts)
        direct_advice = bool(advice)
        no_direct_rationale = EXPLICIT_NO_DIRECT_ADVICE_RATIONALE.get(content_id, "")
        reviewer_alignment_status = (
            "direct_reviewer_advice_linked"
            if direct_advice
            else "explicit_no_direct_advice_rationale_recorded"
            if no_direct_rationale
            else "missing_direct_reviewer_advice"
        )
        row = {
            "content_area_id": content_id,
            "row_index": index,
            "artifact_type": content.get("artifact_type"),
            "target_surfaces": content.get("target_surfaces") or [],
            "candidate_surface": content.get("candidate_surface"),
            "recommended_surface": retention.get("recommended_surface"),
            "placement_status": content.get("placement_status"),
            "final_placement_decision": content.get("final_placement_decision"),
            "retained_visual_or_table_decision": content.get(
                "retained_visual_or_table_decision"
            ),
            "retention_recommendation_status": retention.get("recommendation_status"),
            "retention_readiness_decision": retention.get(
                "retention_readiness_decision"
            ),
            "reviewer_alignment_status": reviewer_alignment_status,
            "reviewer_advice_count": len(advice),
            "reviewer_advice_record_ids": [
                row.get("recommendation_id") for row in advice if row.get("recommendation_id")
            ],
            "no_direct_reviewer_advice_rationale": no_direct_rationale,
            "neutral_result_ids": result_ids,
            "neutral_result_claim_statuses": [
                row.get("claim_status") for row in linked_results
            ],
            "linked_neutral_result_count": len(linked_results),
            "scientific_reporting_role": SCIENTIFIC_ROLE_BY_CONTENT_ID.get(
                content_id, "neutral_candidate_evidence"
            ),
            "claim_boundary": retention.get("claim_boundary")
            or content.get("claim_boundary"),
            "source_artifacts": present_sources,
            "source_artifact_count": len(present_sources),
            "missing_source_artifacts": missing_sources,
            "source_traceability_status": "pass" if not missing_sources else "fail",
            "final_retention_authorized": False,
            "final_visual_table_retention_authorized": False,
            "final_manuscript_prose_permission": False,
            "publication_site_deployment_authorized": False,
            "kg_citable_component_authorized": False,
            "positive_claim_promotion_authorized": False,
            "sterile_repository_creation_authorized": False,
            "method_recommendation_authorized": False,
            "alignment_decision_scope": (
                "pre_prose_design_alignment_only_no_final_claim_or_method_promotion"
            ),
        }
        rows.append(row)
    return rows


def build_surface_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    surface_defs = [
        (
            "main_article",
            "Candidate main article surface after final-prose gate",
            lambda row: row["recommended_surface"]
            == "main_article_candidate_after_final_prose_gate",
        ),
        (
            "supplementary_document",
            "Candidate supplementary document surface after final-prose gate",
            lambda row: row["recommended_surface"]
            == "supplement_candidate_after_final_prose_gate",
        ),
        (
            "kg_or_publication_site",
            "Candidate KG/site navigation surface after release gates",
            lambda row: row["recommended_surface"]
            == "kg_or_site_candidate_release_blocked",
        ),
    ]
    surface_rows: list[dict[str, Any]] = []
    for surface_id, title, predicate in surface_defs:
        content_ids = [row["content_area_id"] for row in rows if predicate(row)]
        surface_rows.append(
            {
                "surface_id": surface_id,
                "title": title,
                "candidate_content_area_ids": content_ids,
                "candidate_content_area_count": len(content_ids),
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "positive_claim_promotion_authorized": False,
                "sterile_repository_creation_authorized": False,
                "claim_boundary": (
                    "Candidate surface only; use requires later final-prose, "
                    "visual-retention, KG usability, sterile repository, and "
                    "release gates as applicable."
                ),
            }
        )
    return surface_rows


def build_payload(root: Path) -> dict[str, Any]:
    reviewer_payload = read_json(root / REVIEWER_DESIGN)
    content_payload = read_json(root / CONTENT_MATRIX)
    retention_payload = read_json(root / RETENTION_AUDIT)
    retention_matrix_payload = read_json(root / RETENTION_MATRIX)
    ledger_payload = read_json(root / NEUTRAL_LEDGER)
    activation_payload = read_json(root / PUBLICATION_ACTIVATION)
    paper_readiness_payload = read_json(root / PAPER_READINESS)
    paper_gate_closure_payload = read_json(root / PAPER_GATE_CLOSURE)
    neutral_language_payload = read_json(root / NEUTRAL_LANGUAGE)

    reviewer_summary = summary(reviewer_payload)
    retention_summary = summary(retention_payload)
    retention_matrix_summary = summary(retention_matrix_payload)
    ledger_summary = summary(ledger_payload)
    activation_summary = summary(activation_payload)
    readiness_summary = summary(paper_readiness_payload)
    closure_summary = summary(paper_gate_closure_payload)
    neutral_language_summary = summary(neutral_language_payload)

    rows = build_alignment_rows(
        root=root,
        content_payload=content_payload,
        reviewer_payload=reviewer_payload,
        retention_payload=retention_payload,
        ledger_payload=ledger_payload,
    )
    surface_rows = build_surface_rows(rows)

    row_ids = {row["content_area_id"] for row in rows}
    retention_ids = {
        str(row.get("content_area_id"))
        for row in retention_rows(retention_payload)
        if row.get("content_area_id")
    }
    final_authorization_count = sum(
        1
        for row in rows
        if row["final_retention_authorized"]
        or row["final_visual_table_retention_authorized"]
        or row["final_manuscript_prose_permission"]
        or row["publication_site_deployment_authorized"]
        or row["kg_citable_component_authorized"]
        or row["positive_claim_promotion_authorized"]
        or row["sterile_repository_creation_authorized"]
        or row["method_recommendation_authorized"]
    )
    missing_source_count = sum(len(row["missing_source_artifacts"]) for row in rows)
    direct_advice_row_count = sum(
        row["reviewer_alignment_status"] == "direct_reviewer_advice_linked"
        for row in rows
    )
    explicit_no_direct_count = sum(
        row["reviewer_alignment_status"]
        == "explicit_no_direct_advice_rationale_recorded"
        for row in rows
    )
    reviewer_alignment_issue_count = sum(
        row["reviewer_alignment_status"] == "missing_direct_reviewer_advice"
        for row in rows
    )
    linked_result_issue_count = sum(
        safe_int(row["linked_neutral_result_count"]) == 0 for row in rows
    )
    status_counts = Counter(row["scientific_reporting_role"] for row in rows)
    recommended_surface_counts = Counter(row["recommended_surface"] for row in rows)

    venn_row = next(
        (
            row
            for row in rows
            if row["content_area_id"] == "venn_abers_failure_mode_evidence"
        ),
        {},
    )
    venn_is_negative = (
        venn_row.get("scientific_reporting_role")
        == "negative_failure_mode_no_validated_regression_claim"
        and "venn_abers_regression_negative_evidence"
        in set(venn_row.get("neutral_result_ids") or [])
        and "accepted_negative_result_for_current_manuscript"
        in set(venn_row.get("neutral_result_claim_statuses") or [])
        and venn_row.get("positive_claim_promotion_authorized") is False
    )
    activation_pre_prose_only = (
        activation_summary.get("publication_preparation_authorized") is True
        and activation_summary.get("manuscript_drafting_authorized") is False
        and activation_summary.get("sterile_repository_creation_authorized") is False
        and safe_int(activation_summary.get("blocked_check_count")) == 0
    )
    neutral_ledger_clean = (
        ledger_summary.get("overall_status")
        == "neutral_result_ledger_ready_no_method_promotion"
        and safe_int(ledger_summary.get("positive_claim_promotion_authorized_count"))
        == 0
        and safe_int(ledger_summary.get("final_method_selection_authorized_count"))
        == 0
        and ledger_summary.get("cqr_descriptive_candidate_recorded") is True
        and ledger_summary.get("venn_abers_negative_result_recorded") is True
    )

    checks = [
        check_row(
            "content_matrix_rows_present",
            len(rows) == 10
            and safe_int(reviewer_summary.get("content_matrix_row_count")) == 10,
            {
                "alignment_row_count": len(rows),
                "reviewer_content_matrix_row_count": reviewer_summary.get(
                    "content_matrix_row_count"
                ),
            },
            "content_matrix_alignment_missing_rows",
        ),
        check_row(
            "retention_rows_reconciled",
            row_ids == retention_ids
            and retention_summary.get("overall_status")
            == "publication_retention_readiness_ready_no_final_prose"
            and safe_int(retention_matrix_summary.get("recommendation_row_count"))
            == len(rows),
            {
                "alignment_row_count": len(rows),
                "retention_row_count": len(retention_ids),
                "retention_status": retention_summary.get("overall_status"),
                "retention_matrix_status": retention_matrix_summary.get(
                    "overall_status"
                ),
            },
            "retention_rows_not_reconciled",
        ),
        check_row(
            "reviewer_alignment_or_explicit_rationale_present",
            reviewer_alignment_issue_count == 0
            and direct_advice_row_count + explicit_no_direct_count == len(rows),
            {
                "direct_reviewer_advice_row_count": direct_advice_row_count,
                "explicit_no_direct_advice_rationale_count": explicit_no_direct_count,
                "reviewer_alignment_issue_count": reviewer_alignment_issue_count,
            },
            "reviewer_alignment_missing_without_rationale",
        ),
        check_row(
            "neutral_result_ledger_boundaries_clean",
            neutral_ledger_clean and linked_result_issue_count == 0,
            {
                "ledger_status": ledger_summary.get("overall_status"),
                "linked_result_issue_count": linked_result_issue_count,
                "positive_claim_promotion_authorized_count": ledger_summary.get(
                    "positive_claim_promotion_authorized_count"
                ),
                "final_method_selection_authorized_count": ledger_summary.get(
                    "final_method_selection_authorized_count"
                ),
            },
            "neutral_result_ledger_or_result_links_not_clean",
        ),
        check_row(
            "source_traceability_clean",
            missing_source_count == 0 and all(row["source_artifact_count"] > 0 for row in rows),
            {
                "missing_source_artifact_count": missing_source_count,
                "source_traceable_row_count": sum(
                    row["source_traceability_status"] == "pass" for row in rows
                ),
            },
            "source_traceability_missing",
        ),
        check_row(
            "activation_remains_pre_prose_only",
            activation_pre_prose_only,
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
            "activation_not_pre_prose_only",
        ),
        check_row(
            "neutral_language_clean",
            neutral_language_summary.get("overall_status")
            == "neutral_reporting_language_audit_pass"
            and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0,
            {
                "neutral_language_status": neutral_language_summary.get(
                    "overall_status"
                ),
                "unguarded_hit_count": neutral_language_summary.get(
                    "unguarded_hit_count"
                ),
            },
            "neutral_language_guard_not_clean",
        ),
        check_row(
            "final_authorizations_blocked",
            final_authorization_count == 0,
            {"final_authorization_count": final_authorization_count},
            "final_authorization_started_too_early",
        ),
        check_row(
            "venn_abers_negative_no_validated_claim",
            venn_is_negative,
            {
                "venn_abers_reporting_role": venn_row.get(
                    "scientific_reporting_role"
                ),
                "venn_abers_result_ids": venn_row.get("neutral_result_ids"),
                "venn_abers_claim_statuses": venn_row.get(
                    "neutral_result_claim_statuses"
                ),
            },
            "venn_abers_boundary_not_negative_failure_mode",
        ),
        check_row(
            "no_final_method_recommendation_or_positive_claim",
            readiness_summary.get("final_selection_claim_status") == "blocked"
            and safe_int(closure_summary.get("positive_claim_ready_gate_count")) == 0
            and all(row["method_recommendation_authorized"] is False for row in rows),
            {
                "paper_readiness_status": readiness_summary.get("overall_status"),
                "final_selection_claim_status": readiness_summary.get(
                    "final_selection_claim_status"
                ),
                "positive_claim_ready_gate_count": closure_summary.get(
                    "positive_claim_ready_gate_count"
                ),
            },
            "final_method_or_positive_claim_recommendation_detected",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    failed_check_count = len(failed_checks)
    overall_status = (
        "article_supplement_blueprint_alignment_ready_no_final_prose_no_method_promotion"
        if failed_check_count == 0
        else "article_supplement_blueprint_alignment_blocked"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "phase_state": (
                "neutral_pre_prose_blueprint_alignment_active_"
                "final_prose_and_release_blocked"
            ),
            "alignment_row_count": len(rows),
            "surface_row_count": len(surface_rows),
            "direct_reviewer_advice_row_count": direct_advice_row_count,
            "explicit_no_direct_advice_rationale_count": explicit_no_direct_count,
            "reviewer_alignment_issue_count": reviewer_alignment_issue_count,
            "linked_neutral_result_issue_count": linked_result_issue_count,
            "source_traceable_row_count": sum(
                row["source_traceability_status"] == "pass" for row in rows
            ),
            "missing_source_artifact_count": missing_source_count,
            "scientific_reporting_role_counts": dict(sorted(status_counts.items())),
            "recommended_surface_counts": dict(
                sorted(recommended_surface_counts.items())
            ),
            "neutral_result_ledger_clean": neutral_ledger_clean,
            "neutral_language_unguarded_hit_count": neutral_language_summary.get(
                "unguarded_hit_count"
            ),
            "activation_pre_prose_only": activation_pre_prose_only,
            "venn_abers_negative_no_validated_claim": venn_is_negative,
            "cqr_cvplus_reporting_role": (
                "descriptive_diagnostic_no_final_selection_no_method_promotion"
            ),
            "final_retained_artifact_count": 0,
            "final_visual_table_retention_authorized": False,
            "final_manuscript_prose_permission": False,
            "publication_site_deployment_authorized": False,
            "kg_citable_component_authorized": False,
            "positive_claim_promotion_authorized": False,
            "sterile_repository_creation_authorized": False,
            "method_recommendation_authorized": False,
            "scientific_no_method_promotion_guard_active": True,
            "check_count": len(checks),
            "failed_check_count": failed_check_count,
        },
        "claim_boundaries": [
            "This artifact aligns publication blueprints to evidence; it is not manuscript prose.",
            "Candidate article, supplement, KG, or site placement does not authorize final retention, KG citation, site deployment, sterile repository creation, or release.",
            "CQR and CV+ may be described only as diagnostic/descriptive evidence inside no-final-selection boundaries.",
            "Venn-Abers regression is recorded only as observed negative/failure-mode evidence with no validated regression claim.",
            "Blocked paper gates remain evidence boundaries and must not be converted into positive claims.",
        ],
        "checks": checks,
        "failed_checks": failed_checks,
        "alignment_rows": rows,
        "surface_rows": surface_rows,
        "sources": {
            "reviewer_design_brief": rel(root / REVIEWER_DESIGN, root),
            "article_supplement_content_matrix": rel(root / CONTENT_MATRIX, root),
            "publication_retention_readiness_audit": rel(
                root / RETENTION_AUDIT, root
            ),
            "article_supplement_retention_recommendation_matrix": rel(
                root / RETENTION_MATRIX, root
            ),
            "neutral_result_ledger": rel(root / NEUTRAL_LEDGER, root),
            "post_experiment_publication_activation_audit": rel(
                root / PUBLICATION_ACTIVATION, root
            ),
            "paper_readiness_map": rel(root / PAPER_READINESS, root),
            "paper_gate_closure_map": rel(root / PAPER_GATE_CLOSURE, root),
            "neutral_reporting_language_audit": rel(root / NEUTRAL_LANGUAGE, root),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Article Supplement Blueprint Alignment",
        "",
        "This is a neutral pre-prose alignment audit. It does not write final manuscript text, choose final retained visuals, deploy a site, create the sterile repository, or promote a conformal method.",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase state: `{summary_payload['phase_state']}`",
        f"- Alignment rows: {summary_payload['alignment_row_count']}",
        f"- Direct reviewer-advice rows: {summary_payload['direct_reviewer_advice_row_count']}",
        f"- Explicit no-direct-advice rationales: {summary_payload['explicit_no_direct_advice_rationale_count']}",
        f"- Missing source artifacts: {summary_payload['missing_source_artifact_count']}",
        f"- Venn-Abers negative/no validated claim: `{summary_payload['venn_abers_negative_no_validated_claim']}`",
        f"- CQR/CV+ reporting role: `{summary_payload['cqr_cvplus_reporting_role']}`",
        f"- Final manuscript prose permission: `{summary_payload['final_manuscript_prose_permission']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Alignment Rows",
        "",
        "| Content area | Surface | Reviewer alignment | Neutral result links | Role | Final prose | Positive claim |",
        "|---|---|---|---:|---|---:|---:|",
    ]
    for row in payload["alignment_rows"]:
        lines.append(
            "| `{content}` | `{surface}` | `{reviewer}` | {links} | `{role}` | `{prose}` | `{claim}` |".format(
                content=row["content_area_id"],
                surface=row["recommended_surface"],
                reviewer=row["reviewer_alignment_status"],
                links=row["linked_neutral_result_count"],
                role=row["scientific_reporting_role"],
                prose=row["final_manuscript_prose_permission"],
                claim=row["positive_claim_promotion_authorized"],
            )
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
                "alignment_row_count": payload["summary"]["alignment_row_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
