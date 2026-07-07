"""Build the neutral Individual Experiment Report blueprint.

This artifact prepares a source-traceable section map for the later individual
experiment report requested by the user. It records the approved author header
and evidence dependencies, but it does not write final report prose, create
LaTeX/HTML outputs, release the sterile repository, cite the working repository,
recommend a method, or promote a positive scientific claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_individual_experiment_report_blueprint_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/individual_experiment_report_blueprint.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

POST_PROGRAM = Path("experiments/regression/manuscript/post_experiment_publication_program.json")
RELEASE_GAP = Path("experiments/regression/manuscript/publication_release_gap_register.json")
GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
ACTIVATION = Path(
    "experiments/regression/manuscript/post_experiment_publication_activation_audit.json"
)
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
BLUEPRINT_ALIGNMENT = Path(
    "experiments/regression/manuscript/article_supplement_blueprint_alignment.json"
)
NEUTRAL_LEDGER = Path("experiments/regression/manuscript/neutral_result_ledger.json")
EXPERIMENT_ACCOUNTING = REPORT_DIR / "experiment_accounting_audit.json"
METHOD_PERFORMANCE = REPORT_DIR / "method_performance_synthesis.json"
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
KG_PUBLICATION = REPORT_DIR / "kg_publication_quality_audit.json"
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"


SECTION_DEFINITIONS = [
    {
        "section_id": "author_and_report_identity",
        "title": "Author and Report Identity",
        "section_role": "author_header_and_scope_identity",
        "source_keys": ["post_program", "release_gap"],
        "neutral_result_ids": ["neutral_publication_policy_no_promotion"],
    },
    {
        "section_id": "experiment_scope_and_accounting",
        "title": "Experiment Scope and Accounting",
        "section_role": "empirical_scope_accounting_only",
        "source_keys": ["experiment_accounting", "goal_completion", "release_gap"],
        "neutral_result_ids": ["empirical_scope_accounting"],
    },
    {
        "section_id": "dataset_and_source_audit_summary",
        "title": "Dataset and Source Audit Summary",
        "section_role": "source_audit_summary_no_new_dataset_claim",
        "source_keys": ["paper_readiness", "blueprint_alignment"],
        "neutral_result_ids": ["neutral_publication_policy_no_promotion"],
    },
    {
        "section_id": "preprocessing_policy_and_integrity_controls",
        "title": "Preprocessing Policy and Integrity Controls",
        "section_role": "methodology_integrity_controls_no_claim_strengthening",
        "source_keys": ["paper_readiness", "neutral_ledger"],
        "neutral_result_ids": ["neutral_publication_policy_no_promotion"],
    },
    {
        "section_id": "model_and_conformal_method_scope",
        "title": "Model and Conformal Method Scope",
        "section_role": "method_scope_no_final_selection",
        "source_keys": ["method_performance", "neutral_ledger", "blueprint_alignment"],
        "neutral_result_ids": ["method_performance_descriptive_frontier"],
    },
    {
        "section_id": "selection_and_post_selection_diagnostics",
        "title": "Selection and Post-Selection Diagnostics",
        "section_role": "diagnostic_selection_evidence_no_final_winner",
        "source_keys": ["paper_readiness", "blueprint_alignment", "neutral_ledger"],
        "neutral_result_ids": ["selection_multiplicity_robustness_diagnostic"],
    },
    {
        "section_id": "venn_abers_negative_evidence",
        "title": "Venn-Abers Negative Evidence",
        "section_role": "negative_failure_mode_no_validated_regression_claim",
        "source_keys": ["paper_readiness", "blueprint_alignment", "neutral_ledger"],
        "neutral_result_ids": ["venn_abers_regression_negative_evidence"],
    },
    {
        "section_id": "bounded_support_and_fairness_boundaries",
        "title": "Bounded-Support and Fairness Boundaries",
        "section_role": "blocked_bounded_support_and_fairness_claims",
        "source_keys": ["paper_readiness", "neutral_ledger"],
        "neutral_result_ids": [
            "bounded_support_endpoint_no_validity_claim",
            "fairness_group_diagnostic_no_population_claim",
        ],
    },
    {
        "section_id": "knowledge_graph_and_artifact_traceability",
        "title": "Knowledge Graph and Artifact Traceability",
        "section_role": "kg_navigation_candidate_release_blocked",
        "source_keys": ["kg_quality", "kg_publication", "blueprint_alignment"],
        "neutral_result_ids": ["knowledge_graph_navigation_release_blocked"],
    },
    {
        "section_id": "release_boundaries_and_next_gates",
        "title": "Release Boundaries and Next Gates",
        "section_role": "release_gap_summary_no_final_release",
        "source_keys": ["release_gap", "activation", "goal_completion"],
        "neutral_result_ids": ["neutral_publication_policy_no_promotion"],
    },
]


SOURCE_PATHS = {
    "post_program": POST_PROGRAM,
    "release_gap": RELEASE_GAP,
    "goal_completion": GOAL_COMPLETION,
    "activation": ACTIVATION,
    "paper_readiness": PAPER_READINESS,
    "blueprint_alignment": BLUEPRINT_ALIGNMENT,
    "neutral_ledger": NEUTRAL_LEDGER,
    "experiment_accounting": EXPERIMENT_ACCOUNTING,
    "method_performance": METHOD_PERFORMANCE,
    "kg_quality": KG_QUALITY,
    "kg_publication": KG_PUBLICATION,
    "neutral_language": NEUTRAL_LANGUAGE,
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


def source_status(root: Path, source_paths: list[Path]) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for source in source_paths:
        relative = rel(root / source, root)
        if (root / source).exists():
            present.append(relative)
        else:
            missing.append(relative)
    return present, missing


def result_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("result_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def release_row(payload: dict[str, Any]) -> dict[str, Any]:
    for row in payload.get("deliverable_rows") or []:
        if isinstance(row, dict) and row.get("deliverable_id") == "individual_experiment_report":
            return row
    return {}


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


def build_section_rows(root: Path, neutral_ledger: dict[str, Any]) -> list[dict[str, Any]]:
    ledger_by_result = {
        str(row.get("result_id")): row
        for row in result_rows(neutral_ledger)
        if row.get("result_id")
    }
    rows: list[dict[str, Any]] = []
    for index, section in enumerate(SECTION_DEFINITIONS):
        source_keys = list(section["source_keys"])
        paths = [SOURCE_PATHS[key] for key in source_keys]
        present, missing = source_status(root, paths)
        result_ids = list(section["neutral_result_ids"])
        linked_results = [ledger_by_result[result_id] for result_id in result_ids if result_id in ledger_by_result]
        rows.append(
            {
                "section_id": section["section_id"],
                "row_index": index,
                "title": section["title"],
                "section_role": section["section_role"],
                "source_keys": source_keys,
                "source_artifacts": present,
                "missing_source_artifacts": missing,
                "source_traceability_status": "pass" if not missing else "fail",
                "neutral_result_ids": result_ids,
                "linked_neutral_result_count": len(linked_results),
                "neutral_result_claim_statuses": [
                    row.get("claim_status") for row in linked_results
                ],
                "final_report_prose_permission": False,
                "latex_output_authorized": False,
                "html_output_authorized": False,
                "markdown_output_authorized": False,
                "release_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "section_decision_scope": (
                    "pre_prose_individual_report_blueprint_only_no_final_release"
                ),
                "claim_boundary": (
                    "Section is a source-traceable blueprint row only; it is "
                    "not final report prose and cannot be used to recommend a "
                    "method or promote a positive claim."
                ),
            }
        )
    return rows


def build_payload(root: Path) -> dict[str, Any]:
    post_program = read_json(root / POST_PROGRAM)
    release_gap = read_json(root / RELEASE_GAP)
    goal = read_json(root / GOAL_COMPLETION)
    activation = read_json(root / ACTIVATION)
    paper_readiness = read_json(root / PAPER_READINESS)
    blueprint = read_json(root / BLUEPRINT_ALIGNMENT)
    neutral_ledger = read_json(root / NEUTRAL_LEDGER)
    accounting = read_json(root / EXPERIMENT_ACCOUNTING)
    kg_quality = read_json(root / KG_QUALITY)
    kg_publication = read_json(root / KG_PUBLICATION)
    neutral_language = read_json(root / NEUTRAL_LANGUAGE)

    post_program_summary = summary(post_program)
    release_summary = summary(release_gap)
    goal_summary = summary(goal)
    activation_summary = summary(activation)
    readiness_summary = summary(paper_readiness)
    blueprint_summary = summary(blueprint)
    ledger_summary = summary(neutral_ledger)
    accounting_summary = summary(accounting)
    kg_publication_summary = summary(kg_publication)
    neutral_language_summary = summary(neutral_language)
    kg_graph = kg_quality.get("graph") or {}
    kg_observations = kg_quality.get("observations") or {}
    author = post_program.get("publication_author") or {}
    deliverable = next(
        (
            row
            for row in post_program.get("deliverables") or []
            if isinstance(row, dict)
            and row.get("deliverable_id") == "individual_experiment_report"
        ),
        {},
    )
    release = release_row(release_gap)
    rows = build_section_rows(root, neutral_ledger)

    missing_source_count = sum(len(row["missing_source_artifacts"]) for row in rows)
    linked_result_issue_count = sum(
        safe_int(row["linked_neutral_result_count"]) == 0 for row in rows
    )
    final_authorization_count = sum(
        row["final_report_prose_permission"]
        or row["latex_output_authorized"]
        or row["html_output_authorized"]
        or row["markdown_output_authorized"]
        or row["release_authorized"]
        or row["sterile_repository_creation_authorized"]
        or row["working_repository_final_citable"]
        or row["method_recommendation_authorized"]
        or row["positive_claim_promotion_authorized"]
        for row in rows
    )
    author_header = author.get("author_line") or ""
    author_email = author.get("author_email") or ""
    approved_author_header = (
        author.get("author_name") == "Emre Tasar"
        and author.get("author_role") == "Data Scientist"
        and author_email == "detasar@gmail.com"
        and author_header == "Author: Emre Tasar, Data Scientist"
    )
    release_blocked = (
        release.get("deliverable_id") == "individual_experiment_report"
        and release.get("pre_prose_evidence_ready") is True
        and release.get("release_authorized") is False
        and release.get("final_manuscript_prose_permission") is False
        and release.get("method_recommendation_authorized") is False
        and release.get("positive_claim_promotion_authorized") is False
        and release.get("working_repository_final_citable") is False
    )
    neutral_ledger_clean = (
        ledger_summary.get("overall_status")
        == "neutral_result_ledger_ready_no_method_promotion"
        and safe_int(ledger_summary.get("positive_claim_promotion_authorized_count")) == 0
        and safe_int(ledger_summary.get("final_method_selection_authorized_count")) == 0
        and ledger_summary.get("cqr_descriptive_candidate_recorded") is True
        and ledger_summary.get("venn_abers_negative_result_recorded") is True
    )
    activation_pre_prose_only = (
        activation_summary.get("publication_preparation_authorized") is True
        and activation_summary.get("manuscript_drafting_authorized") is False
        and activation_summary.get("sterile_repository_creation_authorized") is False
        and safe_int(activation_summary.get("blocked_check_count")) == 0
    )
    checks = [
        check_row(
            "approved_author_header_present",
            approved_author_header,
            {
                "author_line": author_header,
                "author_email": author_email,
                "author_name": author.get("author_name"),
                "author_role": author.get("author_role"),
            },
            "approved_author_header_missing",
        ),
        check_row(
            "individual_report_deliverable_registered",
            deliverable.get("deliverable_id") == "individual_experiment_report"
            and deliverable.get("format") == "latex_html_and_markdown",
            {
                "deliverable_id": deliverable.get("deliverable_id"),
                "format": deliverable.get("format"),
            },
            "individual_report_deliverable_missing",
        ),
        check_row(
            "release_gap_blocks_final_report",
            release_blocked
            and release_summary.get("overall_status")
            == "publication_release_gap_register_ready_no_final_release",
            {
                "release_gap_status": release_summary.get("overall_status"),
                "release_status": release.get("release_status"),
                "release_authorized": release.get("release_authorized"),
                "working_repository_final_citable": release.get(
                    "working_repository_final_citable"
                ),
            },
            "individual_report_release_not_blocked",
        ),
        check_row(
            "section_rows_source_traceable",
            len(rows) == 10 and missing_source_count == 0,
            {
                "section_row_count": len(rows),
                "missing_source_artifact_count": missing_source_count,
                "source_traceable_row_count": sum(
                    row["source_traceability_status"] == "pass" for row in rows
                ),
            },
            "section_source_traceability_missing",
        ),
        check_row(
            "neutral_result_links_present",
            linked_result_issue_count == 0 and neutral_ledger_clean,
            {
                "linked_result_issue_count": linked_result_issue_count,
                "neutral_ledger_status": ledger_summary.get("overall_status"),
            },
            "neutral_result_links_or_ledger_not_clean",
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
            },
            "activation_not_pre_prose_only",
        ),
        check_row(
            "no_final_report_outputs_or_claim_promotions",
            final_authorization_count == 0
            and release_summary.get("release_authorized_count") == 0
            and release_summary.get("method_recommendation_authorized") is False
            and release_summary.get("positive_claim_promotion_authorized") is False,
            {
                "final_authorization_count": final_authorization_count,
                "release_authorized_count": release_summary.get("release_authorized_count"),
                "method_recommendation_authorized": release_summary.get(
                    "method_recommendation_authorized"
                ),
                "positive_claim_promotion_authorized": release_summary.get(
                    "positive_claim_promotion_authorized"
                ),
            },
            "final_report_output_or_claim_promotion_authorized",
        ),
        check_row(
            "empirical_scope_and_kg_ready_for_blueprint",
            accounting_summary.get("overall_status") == "experiment_accounting_pass"
            and safe_int(accounting_summary.get("publication_completed_rows")) > 0
            and kg_publication_pre_release_ready(kg_publication_summary)
            and safe_int(kg_graph.get("isolated_node_count")) == 0,
            {
                "experiment_accounting_status": accounting_summary.get("overall_status"),
                "publication_completed_rows": accounting_summary.get(
                    "publication_completed_rows"
                ),
                "kg_publication_status": kg_publication_summary.get("overall_status"),
                "kg_node_count": kg_graph.get("node_count"),
                "kg_observation_count": kg_observations.get("total_observation_count"),
            },
            "empirical_scope_or_kg_not_ready",
        ),
        check_row(
            "paper_claim_boundaries_remain_blocked",
            goal_summary.get("can_mark_goal_complete") is False
            and readiness_summary.get("overall_status")
            == "paper_readiness_blocked_with_evidence_map"
            and safe_int(readiness_summary.get("blocked_gate_count")) == 6
            and blueprint_summary.get("venn_abers_negative_no_validated_claim") is True,
            {
                "goal_can_mark_complete": goal_summary.get("can_mark_goal_complete"),
                "paper_readiness_status": readiness_summary.get("overall_status"),
                "blocked_gate_count": readiness_summary.get("blocked_gate_count"),
                "venn_abers_negative_no_validated_claim": blueprint_summary.get(
                    "venn_abers_negative_no_validated_claim"
                ),
            },
            "paper_claim_boundaries_not_blocked",
        ),
        check_row(
            "neutral_language_clean",
            neutral_language_summary.get("overall_status")
            == "neutral_reporting_language_audit_pass"
            and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0,
            {
                "neutral_language_status": neutral_language_summary.get("overall_status"),
                "unguarded_hit_count": neutral_language_summary.get("unguarded_hit_count"),
            },
            "neutral_language_guard_not_clean",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    failed_check_count = len(failed_checks)
    status_counts = Counter(row["section_role"] for row in rows)
    overall_status = (
        "individual_experiment_report_blueprint_ready_no_final_prose"
        if failed_check_count == 0
        else "individual_experiment_report_blueprint_blocked"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "phase_state": (
                "neutral_pre_prose_individual_report_blueprint_active_final_outputs_blocked"
            ),
            "author_header": author_header,
            "author_email": author_email,
            "approved_author_header_present": approved_author_header,
            "deliverable_registered": bool(deliverable),
            "deliverable_format": deliverable.get("format"),
            "section_row_count": len(rows),
            "source_traceable_row_count": sum(
                row["source_traceability_status"] == "pass" for row in rows
            ),
            "missing_source_artifact_count": missing_source_count,
            "linked_neutral_result_issue_count": linked_result_issue_count,
            "section_role_counts": dict(sorted(status_counts.items())),
            "publication_completed_rows": accounting_summary.get(
                "publication_completed_rows"
            ),
            "kg_node_count": kg_graph.get("node_count"),
            "kg_edge_count": kg_graph.get("edge_count"),
            "kg_observation_count": kg_observations.get("total_observation_count"),
            "release_gap_status": release_summary.get("overall_status"),
            "individual_report_release_status": release.get("release_status"),
            "individual_report_release_blocker_count": release.get(
                "release_blocker_count"
            ),
            "final_report_prose_permission": False,
            "latex_output_authorized": False,
            "html_output_authorized": False,
            "markdown_output_authorized": False,
            "release_authorized": False,
            "sterile_repository_creation_authorized": False,
            "working_repository_final_citable": False,
            "method_recommendation_authorized": False,
            "positive_claim_promotion_authorized": False,
            "cqr_reporting_role": "descriptive_diagnostic_no_final_selection",
            "venn_abers_reporting_role": (
                "negative_failure_mode_no_validated_regression_claim"
            ),
            "neutral_language_unguarded_hit_count": neutral_language_summary.get(
                "unguarded_hit_count"
            ),
            "scientific_no_method_promotion_guard_active": True,
            "check_count": len(checks),
            "failed_check_count": failed_check_count,
        },
        "claim_boundaries": [
            "This artifact is an individual-report blueprint, not final report prose.",
            "The approved author header is recorded for later use, but LaTeX, HTML, and Markdown final outputs remain unauthorized.",
            "The individual experiment report remains release-blocked until final prose, visual/table retention, sterile repository, citation, and disclosure gates pass or are explicitly rescoped.",
            "CQR may be described only as diagnostic/descriptive no-final-selection evidence.",
            "Venn-Abers regression remains observed negative/failure-mode evidence with no validated regression claim.",
        ],
        "checks": checks,
        "failed_checks": failed_checks,
        "section_rows": rows,
        "sources": {key: rel(root / path, root) for key, path in SOURCE_PATHS.items()},
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Individual Experiment Report Blueprint",
        "",
        "This is a neutral pre-prose blueprint. It records the approved author header and section evidence map, but it does not write final report text, create LaTeX/HTML/Markdown outputs, release the sterile repository, cite the working repository, recommend a method, or promote a positive claim.",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase state: `{summary_payload['phase_state']}`",
        f"- Author header: `{summary_payload['author_header']}`",
        f"- Author email: `{summary_payload['author_email']}`",
        f"- Section rows: {summary_payload['section_row_count']}",
        f"- Missing source artifacts: {summary_payload['missing_source_artifact_count']}",
        f"- Release authorized: `{summary_payload['release_authorized']}`",
        f"- Final report prose permission: `{summary_payload['final_report_prose_permission']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Section Rows",
        "",
        "| Section | Role | Source traceability | Neutral result links | Final prose | Release |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["section_rows"]:
        lines.append(
            "| `{section}` | `{role}` | `{trace}` | {links} | `{prose}` | `{release}` |".format(
                section=row["section_id"],
                role=row["section_role"],
                trace=row["source_traceability_status"],
                links=row["linked_neutral_result_count"],
                prose=row["final_report_prose_permission"],
                release=row["release_authorized"],
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
                "section_row_count": payload["summary"]["section_row_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
