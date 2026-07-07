"""Build neutral publication-preparation packets without manuscript prose.

This artifact starts the allowed pre-prose publication work: reviewer design
packets and a visual/table inventory plan. It does not write final manuscript
text, select retained figures, create the sterile repository, or promote any
method beyond audited evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_publication_preparation_packets_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/publication_preparation_packets.json")
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

POST_EXPERIMENT_PUBLICATION_PROGRAM = Path(
    "experiments/regression/manuscript/post_experiment_publication_program.json"
)
POST_EXPERIMENT_PUBLICATION_ACTIVATION = Path(
    "experiments/regression/manuscript/post_experiment_publication_activation_audit.json"
)
GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
PAPER_GATE_CLOSURE = Path("experiments/regression/manuscript/paper_gate_closure_map.json")
METHOD_PERFORMANCE = REPORT_DIR / "method_performance_synthesis.json"
METHOD_SELECTION_ROBUSTNESS = REPORT_DIR / "method_selection_robustness_audit.json"
METHOD_SELECTION_INFERENTIAL = REPORT_DIR / "method_selection_inferential_audit.json"
POST_SELECTION_VALIDATION_RESULTS = (
    REPORT_DIR / "method_selection_post_selection_validation_results.json"
)
VENN_ABERS_VALIDATION = REPORT_DIR / "venn_abers_validation_readiness_audit.json"
VENN_ABERS_GRID_FAILURE = REPORT_DIR / "venn_abers_grid_failure_mode_decomposition.json"
VENN_ABERS_CLAIM_GATE = REPORT_DIR / "venn_abers_claim_gate_matrix.json"
BOUNDED_SUPPORT_DATASET = Path(
    "experiments/regression/manuscript/bounded_support_dataset_audit.json"
)
BOUNDED_SUPPORT_ENDPOINT = REPORT_DIR / "bounded_support_endpoint_closure_audit.json"
BOUNDED_SUPPORT_POSITIVE = Path(
    "experiments/regression/manuscript/bounded_support_positive_validation_protocol.json"
)
FAIRNESS_GROUP_DIAGNOSTIC = REPORT_DIR / "fairness_group_diagnostic_audit.json"
FAIRNESS_GROUP_MULTIPLICITY = Path(
    "experiments/regression/manuscript/fairness_group_multiplicity_scope.json"
)
FAIRNESS_POPULATION = REPORT_DIR / "fairness_population_readiness_audit.json"
DUPLICATE_SENSITIVITY = REPORT_DIR / "duplicate_sensitivity_closure_audit.json"
DUPLICATE_QUARANTINE = REPORT_DIR / "duplicate_content_quarantine_audit.json"
CROSS_RUN_INTEGRITY = REPORT_DIR / "cross_run_integrity_audit.json"
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
KG_PUBLICATION = REPORT_DIR / "kg_publication_quality_audit.json"
RETROSPECTIVE_GATE = REPORT_DIR / "retrospective_quality_gate.json"
NEUTRAL_CLOSURE = REPORT_DIR / "neutral_experiment_closure_audit.json"
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
PUBLICATION_METHODOLOGY = REPORT_DIR / "publication_methodology_audit.json"


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
    return payload.get("summary") or {}


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def source_paths(root: Path, *paths: Path) -> list[str]:
    return [rel(root / path, root) for path in paths if (root / path).exists()]


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def check_row(
    check_id: str,
    passed: bool,
    evidence: dict[str, Any],
    source_artifacts: list[str],
    blocker: str = "",
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "blocks_preparation": not passed,
        "evidence": evidence,
        "source_artifacts": source_artifacts,
        "blocker": blocker,
    }


REVIEWER_FOCUS_QUESTIONS: dict[str, list[str]] = {
    "statistical_methodology_reviewer": [
        "Do operating criteria separate descriptive evidence from final claims?",
        "Are coverage, width, multiplicity, and interval-score limitations explicit?",
        "Are confidence intervals or uncertainty bands required wherever comparisons are summarized?",
        "Does the design prevent final-winner language until the dedicated gate passes?",
    ],
    "conformal_prediction_reviewer": [
        "Is the regression conformal prediction taxonomy complete and non-promotional?",
        "Are CQR, CV+, Mondrian, and Venn-Abers boundaries mapped to observed evidence?",
        "Are Venn-Abers undercoverage and upper-boundary failures retained as negative evidence?",
        "Are split, calibration, and alpha-specific claims restricted to audited cells?",
    ],
    "data_science_reproducibility_reviewer": [
        "Can every paper-facing table trace back to ledgers, configs, and audit manifests?",
        "Are preprocessing, imputation, feature engineering, and split decisions cited?",
        "Are resume-safety and interrupted-run recovery artifacts sufficient for reproduction?",
        "Are stale or working-only artifacts excluded from future sterile release packaging?",
    ],
    "fairness_domain_reviewer": [
        "Are diagnostic group comparisons clearly separated from population fairness claims?",
        "Are protected-attribute, sampling-weight, and estimand limitations stated?",
        "Do fairness tables report missingness, counts, uncertainty, and multiplicity scope?",
        "Does the paper avoid policy or production fairness claims that are not gate-supported?",
    ],
    "visual_editorial_reviewer": [
        "Does each candidate figure or table answer a paper-relevant question?",
        "Can the artifact be read without overlapping text, marks, legends, or captions?",
        "Is the artifact better placed in the article, supplement, KG/site, or removed?",
        "Does every caption state the relevant claim boundary and caveat scope?",
    ],
}


VISUAL_TABLE_FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "artifact_family_id": "experiment_scope_and_accounting_table",
        "artifact_type": "table",
        "target_surfaces": ["main_article", "supplementary_document"],
        "source_paths": [RETROSPECTIVE_GATE, GOAL_COMPLETION, PAPER_GATE_CLOSURE],
        "paper_question": "What empirical surface was actually completed and audited?",
        "claim_boundary": "Scope table only; it must not imply all possible internet datasets or positive claims were exhausted.",
    },
    {
        "artifact_family_id": "method_performance_descriptive_summary",
        "artifact_type": "table",
        "target_surfaces": ["main_article", "supplementary_document"],
        "source_paths": [METHOD_PERFORMANCE, METHOD_SELECTION_INFERENTIAL],
        "paper_question": "How did methods behave descriptively under the current audited protocol?",
        "claim_boundary": "Descriptive no-final-selection evidence; not a final winner claim.",
    },
    {
        "artifact_family_id": "method_selection_robustness_diagnostics",
        "artifact_type": "figure_or_table",
        "target_surfaces": ["supplementary_document", "main_article"],
        "source_paths": [METHOD_SELECTION_ROBUSTNESS, METHOD_SELECTION_INFERENTIAL],
        "paper_question": "How stable are method-selection diagnostics across leave-one and bootstrap views?",
        "claim_boundary": "Robustness diagnostic only; final selection remains blocked.",
    },
    {
        "artifact_family_id": "post_selection_validation_diagnostics",
        "artifact_type": "table",
        "target_surfaces": ["supplementary_document"],
        "source_paths": [POST_SELECTION_VALIDATION_RESULTS],
        "paper_question": "What fresh validation evidence exists after candidate selection?",
        "claim_boundary": "Post-selection validation evidence is no-final-selection evidence.",
    },
    {
        "artifact_family_id": "venn_abers_failure_mode_evidence",
        "artifact_type": "figure_or_table",
        "target_surfaces": ["main_article", "supplementary_document"],
        "source_paths": [VENN_ABERS_VALIDATION, VENN_ABERS_GRID_FAILURE, VENN_ABERS_CLAIM_GATE],
        "paper_question": "Where and why did Venn-Abers regression evidence fail validation gates?",
        "claim_boundary": "Negative/failure-mode evidence; no validated Venn-Abers regression claim.",
    },
    {
        "artifact_family_id": "bounded_support_endpoint_policy_table",
        "artifact_type": "table",
        "target_surfaces": ["supplementary_document"],
        "source_paths": [BOUNDED_SUPPORT_DATASET, BOUNDED_SUPPORT_ENDPOINT, BOUNDED_SUPPORT_POSITIVE],
        "paper_question": "Which bounded-support target-domain and endpoint checks blocked validity claims?",
        "claim_boundary": "No bounded-support validity claim; endpoint blockers are retained as evidence.",
    },
    {
        "artifact_family_id": "fairness_group_diagnostic_tables",
        "artifact_type": "table",
        "target_surfaces": ["supplementary_document"],
        "source_paths": [FAIRNESS_GROUP_DIAGNOSTIC, FAIRNESS_GROUP_MULTIPLICITY, FAIRNESS_POPULATION],
        "paper_question": "What diagnostic group evidence exists without population fairness inference?",
        "claim_boundary": "Diagnostic group comparison only; no population fairness claim.",
    },
    {
        "artifact_family_id": "duplicate_split_caveat_inventory",
        "artifact_type": "table",
        "target_surfaces": ["supplementary_document"],
        "source_paths": [DUPLICATE_SENSITIVITY, DUPLICATE_QUARANTINE, CROSS_RUN_INTEGRITY],
        "paper_question": "Which duplicate, split, and caveat controls constrain interpretation?",
        "claim_boundary": "Integrity caveat evidence; not a claim-strengthening artifact.",
    },
    {
        "artifact_family_id": "knowledge_graph_navigation_quality",
        "artifact_type": "figure_or_table",
        "target_surfaces": ["supplementary_document", "kg_or_publication_site"],
        "source_paths": [KG_QUALITY, KG_PUBLICATION],
        "paper_question": "Is the KG traceable and navigable enough to cite as a publication surface?",
        "claim_boundary": "KG may be cited only if usability, provenance, and release gates remain clean.",
    },
    {
        "artifact_family_id": "neutral_closure_and_claim_boundary_table",
        "artifact_type": "table",
        "target_surfaces": ["main_article", "supplementary_document"],
        "source_paths": [NEUTRAL_CLOSURE, NEUTRAL_LANGUAGE, PUBLICATION_METHODOLOGY],
        "paper_question": "Which claims are allowed, blocked, diagnostic, or no-claim?",
        "claim_boundary": "Claim-boundary table only; it must not convert blocked gates into positive claims.",
    },
)


def build_reviewer_packets(
    root: Path,
    post_program: dict[str, Any],
    activation_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    reviewer_gate = post_program.get("reviewer_design_gate") or {}
    topics = list(reviewer_gate.get("required_advice_topics") or [])
    schema_fields = list(reviewer_gate.get("advice_record_schema") or [])
    required_outputs = list(reviewer_gate.get("required_output_artifacts") or [])
    preparation_authorized = (
        activation_summary.get("publication_preparation_authorized") is True
    )
    packets: list[dict[str, Any]] = []
    for index, reviewer in enumerate(post_program.get("reviewer_perspectives") or []):
        if not isinstance(reviewer, dict) or not reviewer.get("reviewer_id"):
            continue
        reviewer_id = str(reviewer["reviewer_id"])
        packets.append(
            {
                "packet_id": f"reviewer_packet:{reviewer_id}",
                "reviewer_id": reviewer_id,
                "focus": reviewer.get("focus"),
                "packet_status": (
                    "ready_for_pre_prose_design_review"
                    if preparation_authorized
                    else "blocked_until_publication_preparation_authorized"
                ),
                "final_manuscript_prose_permission": False,
                "minimum_structured_recommendation_count": safe_int(
                    reviewer_gate.get("minimum_structured_recommendations_per_reviewer")
                ),
                "required_advice_schema_fields": schema_fields,
                "required_advice_topics": topics,
                "focus_questions": REVIEWER_FOCUS_QUESTIONS.get(reviewer_id, []),
                "required_reconciliation_outputs": required_outputs,
                "source_artifacts": source_paths(
                    root,
                    POST_EXPERIMENT_PUBLICATION_PROGRAM,
                    POST_EXPERIMENT_PUBLICATION_ACTIVATION,
                    GOAL_COMPLETION,
                    PAPER_GATE_CLOSURE,
                ),
                "evidence_selector": f"reviewer_perspectives[{index}].reviewer_id",
                "claim_boundary": (
                    "Reviewer packet can request design advice only; final prose, "
                    "final retained visuals, sterile release, and positive claims "
                    "remain gated."
                ),
            }
        )
    return packets


def build_visual_inventory(root: Path, post_program: dict[str, Any]) -> list[dict[str, Any]]:
    visual_audit = post_program.get("visual_table_audit_agent") or {}
    quality_checks = list(visual_audit.get("quality_checks") or [])
    rows: list[dict[str, Any]] = []
    for family in VISUAL_TABLE_FAMILIES:
        source_artifacts = source_paths(root, *family["source_paths"])
        rows.append(
            {
                "artifact_family_id": family["artifact_family_id"],
                "artifact_type": family["artifact_type"],
                "inventory_status": "candidate_for_visual_table_audit",
                "final_retain_decision": "not_started",
                "target_surfaces": family["target_surfaces"],
                "paper_question": family["paper_question"],
                "required_quality_checks": quality_checks,
                "source_artifacts": source_artifacts,
                "source_artifact_count": len(source_artifacts),
                "claim_boundary": family["claim_boundary"],
            }
        )
    return rows


def build_payload(root: Path) -> dict[str, Any]:
    post_program = read_json(root / POST_EXPERIMENT_PUBLICATION_PROGRAM)
    activation = read_json(root / POST_EXPERIMENT_PUBLICATION_ACTIVATION)
    goal = read_json(root / GOAL_COMPLETION)
    kg_quality = read_json(root / KG_QUALITY)
    kg_publication = read_json(root / KG_PUBLICATION)
    neutral_language = read_json(root / NEUTRAL_LANGUAGE)

    activation_summary = summary(activation)
    goal_summary = summary(goal)
    kg_graph = kg_quality.get("graph") or {}
    kg_traceability = kg_quality.get("traceability") or {}
    kg_publication_summary = summary(kg_publication)
    neutral_language_summary = summary(neutral_language)

    reviewer_gate = post_program.get("reviewer_design_gate") or {}
    visual_audit = post_program.get("visual_table_audit_agent") or {}
    reviewer_packets = build_reviewer_packets(root, post_program, activation_summary)
    visual_inventory = build_visual_inventory(root, post_program)

    required_reviewer_count = safe_int(reviewer_gate.get("required_reviewer_pass_count"))
    preparation_authorized = (
        activation_summary.get("publication_preparation_authorized") is True
    )
    private_manuscript_drafting_authorized = (
        activation_summary.get("private_manuscript_drafting_authorized") is True
    )
    manuscript_drafting_blocked = (
        activation_summary.get("manuscript_drafting_authorized") is False
    )
    sterile_release_blocked = (
        activation_summary.get("sterile_repository_creation_authorized") is False
    )
    positive_claims_blocked = (
        activation_summary.get("positive_claim_language_blocked") is True
        and goal_summary.get("positive_claim_publication_ready") is False
        and safe_int(goal_summary.get("positive_claim_ready_gate_count")) == 0
    )
    neutral_no_method_promotion_guard_active = (
        neutral_language_summary.get("overall_status")
        == "neutral_reporting_language_audit_pass"
        and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
        and safe_int(neutral_language_summary.get("unsupported_claim_hits")) == 0
        and positive_claims_blocked
    )
    visual_contract_present = (
        bool(visual_audit.get("scope"))
        and bool(visual_audit.get("quality_checks"))
        and bool(visual_audit.get("required_output_artifacts"))
    )
    source_artifacts_present = all(
        row["source_artifact_count"] > 0 for row in visual_inventory
    )

    checks = [
        check_row(
            "publication_preparation_is_authorized",
            preparation_authorized,
            {
                "activation_status": activation_summary.get("overall_status"),
                "publication_preparation_authorized": activation_summary.get(
                    "publication_preparation_authorized"
                ),
            },
            source_paths(root, POST_EXPERIMENT_PUBLICATION_ACTIVATION),
            "publication_preparation_not_authorized",
        ),
        check_row(
            "reviewer_packets_match_required_count",
            required_reviewer_count > 0 and len(reviewer_packets) == required_reviewer_count,
            {
                "required_reviewer_pass_count": required_reviewer_count,
                "reviewer_packet_count": len(reviewer_packets),
            },
            source_paths(root, POST_EXPERIMENT_PUBLICATION_PROGRAM),
            "reviewer_packet_count_mismatch",
        ),
        check_row(
            "advice_schema_and_topics_present",
            bool(reviewer_gate.get("advice_record_schema"))
            and bool(reviewer_gate.get("required_advice_topics")),
            {
                "advice_schema_field_count": len(
                    reviewer_gate.get("advice_record_schema") or []
                ),
                "required_advice_topic_count": len(
                    reviewer_gate.get("required_advice_topics") or []
                ),
            },
            source_paths(root, POST_EXPERIMENT_PUBLICATION_PROGRAM),
            "reviewer_design_schema_missing",
        ),
        check_row(
            "visual_table_inventory_contract_present",
            visual_contract_present,
            {
                "visual_scope_count": len(visual_audit.get("scope") or []),
                "quality_check_count": len(visual_audit.get("quality_checks") or []),
                "required_output_artifact_count": len(
                    visual_audit.get("required_output_artifacts") or []
                ),
            },
            source_paths(root, POST_EXPERIMENT_PUBLICATION_PROGRAM),
            "visual_table_contract_missing",
        ),
        check_row(
            "candidate_inventory_rows_have_sources",
            source_artifacts_present,
            {
                "candidate_artifact_family_count": len(visual_inventory),
                "source_missing_family_ids": [
                    row["artifact_family_id"]
                    for row in visual_inventory
                    if row["source_artifact_count"] == 0
                ],
            },
            source_paths(root, DEFAULT_OUT),
            "visual_inventory_source_links_missing",
        ),
        check_row(
            "final_prose_and_release_remain_blocked",
            manuscript_drafting_blocked and sterile_release_blocked,
            {
                "manuscript_drafting_authorized": activation_summary.get(
                    "manuscript_drafting_authorized"
                ),
                "sterile_repository_creation_authorized": activation_summary.get(
                    "sterile_repository_creation_authorized"
                ),
            },
            source_paths(root, POST_EXPERIMENT_PUBLICATION_ACTIVATION),
            "final_publication_actions_unexpectedly_authorized",
        ),
        check_row(
            "positive_claim_boundaries_preserved",
            positive_claims_blocked,
            {
                "positive_claim_language_blocked": activation_summary.get(
                    "positive_claim_language_blocked"
                ),
                "positive_claim_publication_ready": goal_summary.get(
                    "positive_claim_publication_ready"
                ),
                "positive_claim_ready_gate_count": goal_summary.get(
                    "positive_claim_ready_gate_count"
                ),
                "neutral_language_unguarded_hit_count": neutral_language_summary.get(
                    "unguarded_hit_count"
                ),
            },
            source_paths(root, POST_EXPERIMENT_PUBLICATION_ACTIVATION, GOAL_COMPLETION),
            "positive_claim_boundary_not_preserved",
        ),
        check_row(
            "neutral_scientific_reporting_no_method_promotion",
            neutral_no_method_promotion_guard_active,
            {
                "neutral_language_status": neutral_language_summary.get(
                    "overall_status"
                ),
                "unguarded_hit_count": neutral_language_summary.get(
                    "unguarded_hit_count"
                ),
                "unsupported_claim_hits": neutral_language_summary.get(
                    "unsupported_claim_hits"
                ),
                "positive_claims_blocked": positive_claims_blocked,
            },
            source_paths(root, NEUTRAL_LANGUAGE, POST_EXPERIMENT_PUBLICATION_ACTIVATION),
            "neutral_no_method_promotion_guard_not_clean",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] == "fail"]
    overall_status = (
        "publication_preparation_packets_ready_no_final_prose"
        if not failed_checks
        else "publication_preparation_packets_blocked"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "publication_preparation_authorized": preparation_authorized,
            "reviewer_packet_count": len(reviewer_packets),
            "required_reviewer_pass_count": required_reviewer_count,
            "visual_table_candidate_family_count": len(visual_inventory),
            "visual_table_quality_check_count": len(visual_audit.get("quality_checks") or []),
            "failed_check_count": len(failed_checks),
            "check_count": len(checks),
            "manuscript_drafting_authorized": activation_summary.get(
                "manuscript_drafting_authorized"
            ),
            "private_manuscript_drafting_authorized": (
                private_manuscript_drafting_authorized
            ),
            "sterile_repository_creation_authorized": activation_summary.get(
                "sterile_repository_creation_authorized"
            ),
            "positive_claim_language_blocked": activation_summary.get(
                "positive_claim_language_blocked"
            ),
            "positive_claim_publication_ready": goal_summary.get(
                "positive_claim_publication_ready"
            ),
            "neutral_no_method_promotion_guard_active": (
                neutral_no_method_promotion_guard_active
            ),
            "kg_node_count": kg_graph.get("node_count"),
            "kg_edge_count": kg_graph.get("edge_count"),
            "kg_edge_provenance_coverage": kg_traceability.get(
                "explicit_edge_provenance_coverage"
            ),
            "kg_publication_status": kg_publication_summary.get("overall_status"),
        },
        "preparation_scope": {
            "allowed_current_actions": [
                "prepare reviewer design packets",
                "prepare visual/table inventory plan",
                "map paper, supplement, KG, and site design questions to source artifacts",
                "report observed evidence, including negative and blocked outcomes, without method promotion",
            ],
            "disallowed_current_actions": [
                "write final manuscript prose",
                "select final retained figures or tables",
                "create the sterile citable repository",
                "promote final winner, fairness, bounded-support, production, or Venn-Abers regression claims whose validation gate is blocked",
                "advocate for any conformal method beyond what the audited analysis observed",
            ],
        },
        "checks": checks,
        "failed_checks": [row["check_id"] for row in failed_checks],
        "reviewer_packets": reviewer_packets,
        "visual_table_inventory_plan": visual_inventory,
        "next_actions": [
            "Collect structured advice rows from each reviewer packet.",
            "Build reviewer_design_brief.json and reviewer_reconciliation_matrix.json after advice is recorded.",
            "Enumerate concrete candidate figures and tables from the artifact families before final visual audit.",
            "Run the independent visual/table auditor only after candidate artifacts are rendered.",
        ],
        "claim_boundaries": [
            "This artifact is publication preparation, not manuscript prose.",
            "Reviewer packets may request design advice, not positive result promotion.",
            "The study reports observed analysis results and failure modes; it is not designed to promote CQR, CV+, Venn-Abers, or any other method.",
            "Visual/table inventory rows are candidates; no artifact is retained until the final audit passes.",
            "CQR, CV+, Venn-Abers, fairness, bounded-support, and dataset-promotion claims remain limited to audited claim gates.",
            "The sterile publication repository remains downstream and is not created by this artifact.",
        ],
        "sources": {
            "post_experiment_publication_program": rel(
                root / POST_EXPERIMENT_PUBLICATION_PROGRAM, root
            ),
            "post_experiment_publication_activation": rel(
                root / POST_EXPERIMENT_PUBLICATION_ACTIVATION, root
            ),
            "goal_completion": rel(root / GOAL_COMPLETION, root),
            "paper_gate_closure_map": rel(root / PAPER_GATE_CLOSURE, root),
            "kg_quality": rel(root / KG_QUALITY, root),
            "kg_publication": rel(root / KG_PUBLICATION, root),
            "neutral_reporting_language": rel(root / NEUTRAL_LANGUAGE, root),
            "neutral_closure": rel(root / NEUTRAL_CLOSURE, root),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Publication Preparation Packets",
        "",
        (
            "This artifact records private publication preparation and private "
            "manuscript drafting under the neutral route. It does not authorize "
            "public final-submission prose, select retained visuals, create a "
            "sterile repository, or promote positive claims."
        ),
        "",
        f"- Generated UTC: `{payload['generated_at_utc']}`",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Publication preparation authorized: `{summary_payload['publication_preparation_authorized']}`",
        f"- Reviewer packets: {summary_payload['reviewer_packet_count']} / {summary_payload['required_reviewer_pass_count']}",
        f"- Visual/table candidate families: {summary_payload['visual_table_candidate_family_count']}",
        f"- Private manuscript drafting authorized: `{summary_payload['private_manuscript_drafting_authorized']}`",
        f"- Public final-submission manuscript drafting authorized: `{summary_payload['manuscript_drafting_authorized']}`",
        f"- Sterile repository creation authorized: `{summary_payload['sterile_repository_creation_authorized']}`",
        f"- Positive claim publication ready: `{summary_payload['positive_claim_publication_ready']}`",
        f"- Neutral no-method-promotion guard active: `{summary_payload['neutral_no_method_promotion_guard_active']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Blocks preparation |",
        "|---|---:|---:|",
    ]
    for row in payload["checks"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['blocks_preparation']}` |"
        )
    lines.extend(["", "## Reviewer Packets", ""])
    for packet in payload["reviewer_packets"]:
        lines.append(
            f"- `{packet['reviewer_id']}`: `{packet['packet_status']}`; "
            f"minimum recommendations `{packet['minimum_structured_recommendation_count']}`; "
            f"final prose permission `{packet['final_manuscript_prose_permission']}`"
        )
    lines.extend(["", "## Visual/Table Inventory Families", ""])
    for row in payload["visual_table_inventory_plan"]:
        lines.append(
            f"- `{row['artifact_family_id']}` ({row['artifact_type']}): "
            f"`{row['inventory_status']}`, retain decision `{row['final_retain_decision']}`"
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
                "reviewer_packet_count": payload["summary"]["reviewer_packet_count"],
                "visual_table_candidate_family_count": payload["summary"][
                    "visual_table_candidate_family_count"
                ],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )
    if payload["failed_checks"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
