"""Build neutral manuscript section evidence packets.

This artifact is the next publication-preparation layer after the claim-safe
result extraction matrix. It maps section-level paper/supplement/report packets
to source artifacts and neutral result rows without writing final prose,
retaining final visuals, recommending a method, promoting positive claims, or
authorizing release.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_manuscript_section_evidence_packet_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/manuscript_section_evidence_packet.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

CLAIM_SAFE_MATRIX = Path(
    "experiments/regression/manuscript/claim_safe_result_extraction_matrix.json"
)
NEUTRAL_LEDGER = Path("experiments/regression/manuscript/neutral_result_ledger.json")
BLUEPRINT_ALIGNMENT = Path(
    "experiments/regression/manuscript/article_supplement_blueprint_alignment.json"
)
INDIVIDUAL_REPORT_BLUEPRINT = Path(
    "experiments/regression/manuscript/individual_experiment_report_blueprint.json"
)
RELEASE_GAP = Path(
    "experiments/regression/manuscript/publication_release_gap_register.json"
)
RETENTION_READINESS = Path(
    "experiments/regression/manuscript/publication_retention_readiness_audit.json"
)
VISUAL_RENDER_AUDIT = Path(
    "experiments/regression/manuscript/visual_table_render_candidate_audit.json"
)
READER_PRIMER = Path(
    "experiments/regression/manuscript/reader_method_primer_citation_map.json"
)
READER_PRIMER_ALIGNMENT = Path(
    "experiments/regression/manuscript/reader_primer_section_alignment.json"
)
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
KG_PUBLICATION = REPORT_DIR / "kg_publication_quality_audit.json"
EXPERIMENT_ACCOUNTING = REPORT_DIR / "experiment_accounting_audit.json"
METHOD_PERFORMANCE = REPORT_DIR / "method_performance_synthesis.json"
VENN_ABERS_NEGATIVE = REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")


SOURCE_PATHS = {
    "claim_safe_matrix": CLAIM_SAFE_MATRIX,
    "neutral_ledger": NEUTRAL_LEDGER,
    "blueprint_alignment": BLUEPRINT_ALIGNMENT,
    "individual_report_blueprint": INDIVIDUAL_REPORT_BLUEPRINT,
    "release_gap": RELEASE_GAP,
    "retention_readiness": RETENTION_READINESS,
    "visual_render_audit": VISUAL_RENDER_AUDIT,
    "reader_primer": READER_PRIMER,
    "reader_primer_alignment": READER_PRIMER_ALIGNMENT,
    "neutral_language": NEUTRAL_LANGUAGE,
    "kg_publication": KG_PUBLICATION,
    "experiment_accounting": EXPERIMENT_ACCOUNTING,
    "method_performance": METHOD_PERFORMANCE,
    "venn_abers_negative": VENN_ABERS_NEGATIVE,
    "goal_completion": GOAL_COMPLETION,
}


SECTION_PACKET_DEFINITIONS = [
    {
        "packet_id": "paper_dataset_scope_evidence",
        "target_document": "main_article",
        "section_role": "dataset_scope_without_final_result_promotion",
        "claim_safe_surface_id": "dataset_table",
        "neutral_result_ids": ["neutral_publication_policy_no_promotion"],
        "source_keys": [
            "claim_safe_matrix",
            "blueprint_alignment",
            "neutral_ledger",
            "goal_completion",
        ],
        "packet_status": "pre_prose_evidence_ready",
        "allowed_use": "Use as dataset/source-scope evidence only.",
        "blocked_use": "Do not imply exhaustive internet coverage or final dataset-level result promotion.",
        "reader_concept_ids": [
            "conformal_prediction_regression",
            "weighted_conformal_covariate_shift",
            "result_metrics_and_claim_boundaries",
        ],
        "paragraph_blueprint": [
            "Define the completed empirical surface before reporting any result count.",
            "Tie dataset/source claims to audited source artifacts and resume-safe accounting.",
            "Warn that source breadth is not an exhaustive internet-coverage claim.",
        ],
    },
    {
        "packet_id": "paper_method_scope_evidence",
        "target_document": "main_article",
        "section_role": "method_inventory_without_recommendation",
        "claim_safe_surface_id": "method_table",
        "neutral_result_ids": ["method_performance_descriptive_frontier"],
        "source_keys": [
            "claim_safe_matrix",
            "method_performance",
            "neutral_ledger",
            "blueprint_alignment",
        ],
        "packet_status": "pre_prose_evidence_ready",
        "allowed_use": "Use as descriptive method-scope and observed frontier evidence.",
        "blocked_use": "Do not call CQR, CV+, or any method a final recommendation.",
        "reader_concept_ids": [
            "split_conformal_regression",
            "conformalized_quantile_regression_cqr",
            "jackknife_plus_and_cv_plus",
            "mondrian_and_group_calibration",
            "result_metrics_and_claim_boundaries",
        ],
        "paragraph_blueprint": [
            "Define each conformal family before comparing its observed diagnostic behavior.",
            "Report CQR/CV+/Mondrian patterns as descriptive frontier evidence only.",
            "Close the paragraph by preserving the no-recommendation claim boundary.",
        ],
    },
    {
        "packet_id": "paper_main_results_blocked_evidence",
        "target_document": "main_article",
        "section_role": "main_results_positive_claim_blocked",
        "claim_safe_surface_id": "main_results_table",
        "neutral_result_ids": ["selection_multiplicity_robustness_diagnostic"],
        "source_keys": ["claim_safe_matrix", "neutral_ledger", "release_gap"],
        "packet_status": "blocked_positive_claim_packet",
        "allowed_use": "Use only to state that positive main-result promotion is blocked.",
        "blocked_use": "Do not present a final main-results table, winner, or positive method conclusion.",
        "reader_concept_ids": [
            "alpha_and_nominal_coverage",
            "result_metrics_and_claim_boundaries",
        ],
        "paragraph_blueprint": [
            "Explain why observed coverage, width, and score diagnostics are not a final winner test.",
            "Name the positive-claim blockers before any result interpretation.",
            "Use the packet only to justify downgrading main-result language.",
        ],
    },
    {
        "packet_id": "supplement_robustness_diagnostic_evidence",
        "target_document": "supplementary_document",
        "section_role": "robustness_diagnostic_without_final_selection",
        "claim_safe_surface_id": "robustness_results_table",
        "neutral_result_ids": ["selection_multiplicity_robustness_diagnostic"],
        "source_keys": [
            "claim_safe_matrix",
            "neutral_ledger",
            "blueprint_alignment",
            "retention_readiness",
        ],
        "packet_status": "pre_prose_evidence_ready",
        "allowed_use": "Use as caveated robustness and post-selection diagnostic evidence.",
        "blocked_use": "Do not convert robustness diagnostics into confirmatory superiority.",
        "reader_concept_ids": [
            "alpha_and_nominal_coverage",
            "conformalized_quantile_regression_cqr",
            "jackknife_plus_and_cv_plus",
            "result_metrics_and_claim_boundaries",
        ],
        "paragraph_blueprint": [
            "State that robustness diagnostics test stability of an observed pattern, not superiority.",
            "Connect post-selection evidence to the earlier method-primer definitions.",
            "End with the multiplicity and final-selection blockers.",
        ],
    },
    {
        "packet_id": "supplement_venn_abers_negative_evidence",
        "target_document": "supplementary_document",
        "section_role": "venn_abers_failure_mode_without_validation_claim",
        "claim_safe_surface_id": "negative_results_table",
        "neutral_result_ids": ["venn_abers_regression_negative_evidence"],
        "source_keys": [
            "claim_safe_matrix",
            "venn_abers_negative",
            "neutral_ledger",
            "neutral_language",
        ],
        "packet_status": "pre_prose_negative_evidence_ready",
        "allowed_use": "Use as Venn-Abers negative/failure-mode evidence.",
        "blocked_use": "Do not state or imply validated Venn-Abers regression.",
        "reader_concept_ids": [
            "venn_abers_predictive_distributions",
            "distributional_and_full_conformal_references",
            "result_metrics_and_claim_boundaries",
        ],
        "paragraph_blueprint": [
            "Define the Venn-Abers predictive-distribution context before discussing interval-bridge rows.",
            "Report undercoverage and bridge failures as observed negative evidence.",
            "Separate bridge failure evidence from any rejection of the broader Venn-Abers literature.",
        ],
    },
    {
        "packet_id": "supplement_methodology_controls_evidence",
        "target_document": "supplementary_document",
        "section_role": "methodology_controls_without_claim_strengthening",
        "claim_safe_surface_id": "methodology_appendix",
        "neutral_result_ids": ["neutral_publication_policy_no_promotion"],
        "source_keys": [
            "claim_safe_matrix",
            "neutral_ledger",
            "kg_publication",
            "neutral_language",
        ],
        "packet_status": "pre_prose_evidence_ready",
        "allowed_use": "Use as methodology and audit-control evidence.",
        "blocked_use": "Do not treat control presence as proof of validity or production readiness.",
        "reader_concept_ids": [
            "conformal_prediction_regression",
            "mondrian_and_group_calibration",
            "normalized_and_locally_adaptive_split",
            "result_metrics_and_claim_boundaries",
        ],
        "paragraph_blueprint": [
            "Explain methodology controls as safeguards around interpretation.",
            "Link leakage, duplicate, endpoint, and group diagnostics to their specific claim boundaries.",
            "Avoid treating audit presence as a substitute for validity proof.",
        ],
    },
    {
        "packet_id": "supplement_reproducibility_traceability_evidence",
        "target_document": "supplementary_document",
        "section_role": "reproducibility_traceability_without_release",
        "claim_safe_surface_id": "reproducibility_appendix",
        "neutral_result_ids": ["empirical_scope_accounting"],
        "source_keys": [
            "claim_safe_matrix",
            "experiment_accounting",
            "kg_publication",
            "release_gap",
        ],
        "packet_status": "pre_prose_evidence_ready",
        "allowed_use": "Use as accounting, resume-safety, and KG-traceability evidence.",
        "blocked_use": "Do not cite the working repository as the final public artifact.",
        "reader_concept_ids": [
            "distributional_and_full_conformal_references",
            "result_metrics_and_claim_boundaries",
        ],
        "paragraph_blueprint": [
            "Describe reproducibility as source traceability, resumable execution, and artifact accounting.",
            "Use the KG as internal evidence infrastructure until release gates authorize citation.",
            "Keep the working repository distinct from the future sterile public package.",
        ],
    },
    {
        "packet_id": "individual_report_blueprint_evidence",
        "target_document": "individual_experiment_report",
        "section_role": "author_stamped_blueprint_without_final_outputs",
        "claim_safe_surface_id": "individual_experiment_report",
        "neutral_result_ids": ["neutral_publication_policy_no_promotion"],
        "source_keys": [
            "claim_safe_matrix",
            "individual_report_blueprint",
            "release_gap",
            "neutral_ledger",
        ],
        "packet_status": "pre_prose_blueprint_ready",
        "allowed_use": "Use as the author-stamped report section map.",
        "blocked_use": "Do not generate final LaTeX, HTML, Markdown, release, or citable report output.",
        "reader_concept_ids": [
            "conformal_prediction_regression",
            "alpha_and_nominal_coverage",
            "result_metrics_and_claim_boundaries",
        ],
        "paragraph_blueprint": [
            "State author/report identity and empirical scope without upgrading the report to a release artifact.",
            "Use primer definitions to keep the individual report readable for non-specialists.",
            "Keep all final output and public-citation language blocked.",
        ],
    },
]


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


def rows_by_key(payload: dict[str, Any], key: str, id_field: str) -> dict[str, dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get(id_field)): row
        for row in rows
        if isinstance(row, dict) and row.get(id_field)
    }


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


def build_packet_rows(
    root: Path,
    claim_safe_payload: dict[str, Any],
    neutral_ledger_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    surfaces = rows_by_key(claim_safe_payload, "surface_rows", "surface_id")
    results = rows_by_key(neutral_ledger_payload, "result_rows", "result_id")
    rows: list[dict[str, Any]] = []
    for index, packet in enumerate(SECTION_PACKET_DEFINITIONS):
        source_keys = list(
            dict.fromkeys(
                [
                    *packet["source_keys"],
                    "reader_primer",
                    "reader_primer_alignment",
                ]
            )
        )
        source_paths = [SOURCE_PATHS[key] for key in source_keys]
        present, missing = source_status(root, source_paths)
        surface_id = str(packet["claim_safe_surface_id"])
        surface = surfaces.get(surface_id, {})
        result_ids = [str(result_id) for result_id in packet["neutral_result_ids"]]
        linked_results = [results[result_id] for result_id in result_ids if result_id in results]
        packet_status = str(packet["packet_status"])
        blocked_positive = packet_status.startswith("blocked") or bool(
            surface.get("positive_claim_surface_blocked")
        )
        rows.append(
            {
                "packet_id": packet["packet_id"],
                "row_index": index,
                "target_document": packet["target_document"],
                "section_role": packet["section_role"],
                "claim_safe_surface_id": surface_id,
                "claim_safe_surface_status": surface.get("pre_prose_extraction_status"),
                "claim_safe_surface_linked": bool(surface),
                "claim_safe_surface_blocked": bool(
                    surface.get("positive_claim_surface_blocked")
                ),
                "neutral_result_ids": result_ids,
                "linked_neutral_result_count": len(linked_results),
                "neutral_result_claim_statuses": [
                    row.get("claim_status") for row in linked_results
                ],
                "reader_concept_ids": list(packet["reader_concept_ids"]),
                "reader_concept_count": len(packet["reader_concept_ids"]),
                "paragraph_blueprint": list(packet["paragraph_blueprint"]),
                "paragraph_blueprint_step_count": len(packet["paragraph_blueprint"]),
                "source_keys": source_keys,
                "source_artifacts": present,
                "missing_source_artifacts": missing,
                "source_traceability_status": "pass" if not missing else "fail",
                "packet_status": packet_status,
                "safe_pre_prose_evidence_packet": not blocked_positive,
                "positive_claim_packet_blocked": blocked_positive,
                "allowed_use": packet["allowed_use"],
                "blocked_use": packet["blocked_use"],
                "final_section_prose_authorized": False,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "release_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "claim_boundary": (
                    "Section packet is pre-prose evidence only; it cannot "
                    "authorize final section text, final manuscript prose, "
                    "final visual/table retention, release, method "
                    "recommendation, or positive claim promotion."
                ),
            }
        )
    return rows


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


def build_payload(root: Path) -> dict[str, Any]:
    claim_safe = read_json(root / CLAIM_SAFE_MATRIX)
    neutral_ledger = read_json(root / NEUTRAL_LEDGER)
    blueprint_alignment = read_json(root / BLUEPRINT_ALIGNMENT)
    individual_blueprint = read_json(root / INDIVIDUAL_REPORT_BLUEPRINT)
    release_gap = read_json(root / RELEASE_GAP)
    retention = read_json(root / RETENTION_READINESS)
    visual_render = read_json(root / VISUAL_RENDER_AUDIT)
    reader_primer = read_json(root / READER_PRIMER)
    reader_primer_alignment = read_json(root / READER_PRIMER_ALIGNMENT)
    neutral_language = read_json(root / NEUTRAL_LANGUAGE)
    kg_publication = read_json(root / KG_PUBLICATION)
    accounting = read_json(root / EXPERIMENT_ACCOUNTING)
    venn_negative = read_json(root / VENN_ABERS_NEGATIVE)
    goal_completion = read_json(root / GOAL_COMPLETION)

    claim_safe_summary = summary(claim_safe)
    neutral_ledger_summary = summary(neutral_ledger)
    alignment_summary = summary(blueprint_alignment)
    individual_summary = summary(individual_blueprint)
    release_summary = summary(release_gap)
    retention_summary = summary(retention)
    visual_summary = summary(visual_render)
    reader_primer_summary = summary(reader_primer)
    reader_primer_alignment_summary = summary(reader_primer_alignment)
    neutral_language_summary = summary(neutral_language)
    kg_publication_summary = summary(kg_publication)
    accounting_summary = summary(accounting)
    venn_negative_summary = summary(venn_negative)
    goal_summary = summary(goal_completion)

    rows = build_packet_rows(root, claim_safe, neutral_ledger)
    row_by_id = {row["packet_id"]: row for row in rows}
    missing_source_count = sum(len(row["missing_source_artifacts"]) for row in rows)
    surface_link_issue_count = sum(
        not row["claim_safe_surface_linked"] for row in rows
    )
    linked_result_issue_count = sum(
        safe_int(row["linked_neutral_result_count"]) == 0 for row in rows
    )
    final_authorization_count = sum(
        row["final_section_prose_authorized"]
        or row["final_manuscript_prose_permission"]
        or row["final_visual_table_retention_authorized"]
        or row["release_authorized"]
        or row["publication_site_deployment_authorized"]
        or row["kg_citable_component_authorized"]
        or row["sterile_repository_creation_authorized"]
        or row["working_repository_final_citable"]
        or row["method_recommendation_authorized"]
        or row["positive_claim_promotion_authorized"]
        for row in rows
    )
    target_counts = Counter(row["target_document"] for row in rows)
    status_counts = Counter(row["packet_status"] for row in rows)
    safe_packet_count = sum(row["safe_pre_prose_evidence_packet"] for row in rows)
    blocked_positive_packet_count = sum(row["positive_claim_packet_blocked"] for row in rows)
    paragraph_blueprint_complete_count = sum(
        bool(row["paragraph_blueprint"]) for row in rows
    )
    reader_concept_link_count = sum(row["reader_concept_count"] for row in rows)
    unique_reader_concepts = sorted(
        {
            concept_id
            for row in rows
            for concept_id in row.get("reader_concept_ids", [])
        }
    )

    claim_safe_clean = (
        claim_safe_summary.get("overall_status")
        == "claim_safe_result_extraction_matrix_ready_no_final_claims"
        and safe_int(claim_safe_summary.get("surface_row_count")) == 8
        and safe_int(claim_safe_summary.get("safe_pre_prose_extraction_candidate_count"))
        == 7
        and safe_int(claim_safe_summary.get("blocked_positive_surface_count")) == 1
        and claim_safe_summary.get("main_result_positive_claim_blocked") is True
        and claim_safe_summary.get("negative_result_reporting_ready") is True
        and claim_safe_summary.get("method_recommendation_authorized") is False
        and claim_safe_summary.get("positive_claim_promotion_authorized") is False
    )
    upstream_pre_prose_clean = (
        alignment_summary.get("final_manuscript_prose_permission") is False
        and individual_summary.get("final_report_prose_permission") is False
        and release_summary.get("final_manuscript_prose_permission") is False
        and release_summary.get("working_repository_final_citable") is False
        and release_summary.get("method_recommendation_authorized") is False
        and release_summary.get("positive_claim_promotion_authorized") is False
    )
    visual_and_release_blocked = (
        retention_summary.get("final_visual_table_retention_authorized") is False
        and visual_summary.get("final_visual_table_retention_authorized") is False
        and safe_int(visual_summary.get("final_retained_artifact_count")) == 0
        and safe_int(release_summary.get("release_authorized_count")) == 0
        and release_summary.get("sterile_repository_creation_authorized") is False
    )
    reader_primer_ready = (
        reader_primer_summary.get("overall_status")
        == "reader_method_primer_citation_map_ready_no_final_prose"
        and safe_int(reader_primer_summary.get("reader_explanation_outline_count"))
        == safe_int(reader_primer_summary.get("concept_row_count"))
        and reader_primer_alignment_summary.get("overall_status")
        == "reader_primer_section_alignment_ready_no_final_prose"
        and reader_primer_summary.get("final_manuscript_prose_permission") is False
        and reader_primer_alignment_summary.get("final_manuscript_prose_permission")
        is False
    )
    negative_packet_ready = (
        row_by_id["supplement_venn_abers_negative_evidence"][
            "safe_pre_prose_evidence_packet"
        ]
        and row_by_id["supplement_venn_abers_negative_evidence"]["packet_status"]
        == "pre_prose_negative_evidence_ready"
        and venn_negative_summary.get("negative_result_reporting_ready") is True
    )
    main_packet_blocked = (
        row_by_id["paper_main_results_blocked_evidence"][
            "positive_claim_packet_blocked"
        ]
        and row_by_id["paper_main_results_blocked_evidence"][
            "claim_safe_surface_status"
        ]
        == "blocked_positive_claim_surface"
        and safe_int(claim_safe_summary.get("positive_claim_ready_gate_count")) == 0
    )

    checks = [
        check_row(
            "section_packets_source_traceable",
            len(rows) == len(SECTION_PACKET_DEFINITIONS) and missing_source_count == 0,
            {
                "section_packet_row_count": len(rows),
                "expected_section_packet_row_count": len(SECTION_PACKET_DEFINITIONS),
                "missing_source_artifact_count": missing_source_count,
            },
            "section_packet_source_traceability_missing",
        ),
        check_row(
            "claim_safe_surface_links_clean",
            surface_link_issue_count == 0 and claim_safe_clean,
            {
                "surface_link_issue_count": surface_link_issue_count,
                "claim_safe_matrix_status": claim_safe_summary.get("overall_status"),
            },
            "claim_safe_surface_links_or_matrix_not_clean",
        ),
        check_row(
            "neutral_result_links_clean",
            linked_result_issue_count == 0
            and neutral_ledger_summary.get("overall_status")
            == "neutral_result_ledger_ready_no_method_promotion",
            {
                "linked_neutral_result_issue_count": linked_result_issue_count,
                "neutral_result_ledger_status": neutral_ledger_summary.get(
                    "overall_status"
                ),
            },
            "neutral_result_links_or_ledger_not_clean",
        ),
        check_row(
            "reader_primer_blueprints_complete",
            (
                reader_primer_ready
                and paragraph_blueprint_complete_count == len(rows)
                and reader_concept_link_count >= len(rows)
            ),
            {
                "reader_primer_status": reader_primer_summary.get("overall_status"),
                "reader_primer_alignment_status": reader_primer_alignment_summary.get(
                    "overall_status"
                ),
                "paragraph_blueprint_complete_count": (
                    paragraph_blueprint_complete_count
                ),
                "section_packet_row_count": len(rows),
                "reader_concept_link_count": reader_concept_link_count,
                "unique_reader_concept_count": len(unique_reader_concepts),
            },
            "reader_primer_or_paragraph_blueprints_not_complete",
        ),
        check_row(
            "main_results_packet_remains_blocked",
            main_packet_blocked,
            {
                "main_packet_status": row_by_id["paper_main_results_blocked_evidence"][
                    "packet_status"
                ],
                "main_surface_status": row_by_id["paper_main_results_blocked_evidence"][
                    "claim_safe_surface_status"
                ],
                "positive_claim_ready_gate_count": claim_safe_summary.get(
                    "positive_claim_ready_gate_count"
                ),
            },
            "main_results_packet_not_blocked",
        ),
        check_row(
            "negative_packet_ready_as_negative_only",
            negative_packet_ready,
            {
                "negative_packet_status": row_by_id[
                    "supplement_venn_abers_negative_evidence"
                ]["packet_status"],
                "venn_abers_negative_status": venn_negative_summary.get(
                    "overall_status"
                ),
                "negative_result_reporting_ready": venn_negative_summary.get(
                    "negative_result_reporting_ready"
                ),
            },
            "negative_packet_not_ready_or_overpromoted",
        ),
        check_row(
            "upstream_pre_prose_authorizations_remain_blocked",
            upstream_pre_prose_clean,
            {
                "blueprint_alignment_status": alignment_summary.get("overall_status"),
                "individual_report_status": individual_summary.get("overall_status"),
                "release_gap_status": release_summary.get("overall_status"),
            },
            "upstream_pre_prose_authorization_changed",
        ),
        check_row(
            "visual_release_and_repository_outputs_remain_blocked",
            visual_and_release_blocked,
            {
                "retention_status": retention_summary.get("overall_status"),
                "visual_render_status": visual_summary.get("overall_status"),
                "release_authorized_count": release_summary.get(
                    "release_authorized_count"
                ),
            },
            "visual_release_or_repository_output_authorized",
        ),
        check_row(
            "kg_accounting_and_publication_scope_available",
            kg_publication_pre_release_ready(kg_publication_summary)
            and accounting_summary.get("overall_status") == "experiment_accounting_pass"
            and goal_summary.get("neutral_empirical_phase_complete") is True,
            {
                "kg_publication_status": kg_publication_summary.get("overall_status"),
                "experiment_accounting_status": accounting_summary.get("overall_status"),
                "neutral_empirical_phase_complete": goal_summary.get(
                    "neutral_empirical_phase_complete"
                ),
            },
            "kg_accounting_or_goal_scope_not_ready",
        ),
        check_row(
            "neutral_reporting_language_clean",
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
            "no_final_section_or_method_authorizations",
            (
                final_authorization_count == 0
                and safe_int(
                    claim_safe_summary.get("positive_claim_ready_gate_count")
                )
                == 0
                and safe_int(release_summary.get("positive_claim_ready_gate_count"))
                == 0
                and claim_safe_summary.get("method_recommendation_authorized") is False
                and claim_safe_summary.get("positive_claim_promotion_authorized")
                is False
                and release_summary.get("method_recommendation_authorized") is False
                and release_summary.get("positive_claim_promotion_authorized") is False
            ),
            {
                "final_authorization_count": final_authorization_count,
                "claim_safe_positive_claim_ready_gate_count": claim_safe_summary.get(
                    "positive_claim_ready_gate_count"
                ),
                "release_positive_claim_ready_gate_count": release_summary.get(
                    "positive_claim_ready_gate_count"
                ),
                "claim_safe_method_recommendation_authorized": (
                    claim_safe_summary.get("method_recommendation_authorized")
                ),
                "claim_safe_positive_claim_promotion_authorized": (
                    claim_safe_summary.get("positive_claim_promotion_authorized")
                ),
                "release_method_recommendation_authorized": release_summary.get(
                    "method_recommendation_authorized"
                ),
                "release_positive_claim_promotion_authorized": release_summary.get(
                    "positive_claim_promotion_authorized"
                ),
            },
            "final_section_or_method_authorization_detected",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    overall_status = (
        "manuscript_section_evidence_packet_ready_no_final_prose"
        if not failed_checks
        else "manuscript_section_evidence_packet_blocked"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "phase_state": (
                "neutral_pre_prose_section_evidence_packet_active_"
                "final_outputs_blocked"
            ),
            "section_packet_row_count": len(rows),
            "source_traceable_row_count": sum(
                row["source_traceability_status"] == "pass" for row in rows
            ),
            "missing_source_artifact_count": missing_source_count,
            "claim_safe_surface_link_issue_count": surface_link_issue_count,
            "linked_neutral_result_issue_count": linked_result_issue_count,
            "paragraph_blueprint_complete_count": paragraph_blueprint_complete_count,
            "reader_concept_link_count": reader_concept_link_count,
            "unique_reader_concept_count": len(unique_reader_concepts),
            "unique_reader_concepts": unique_reader_concepts,
            "target_document_counts": dict(sorted(target_counts.items())),
            "packet_status_counts": dict(sorted(status_counts.items())),
            "safe_pre_prose_evidence_packet_count": safe_packet_count,
            "blocked_positive_packet_count": blocked_positive_packet_count,
            "main_results_packet_status": row_by_id[
                "paper_main_results_blocked_evidence"
            ]["packet_status"],
            "negative_packet_status": row_by_id[
                "supplement_venn_abers_negative_evidence"
            ]["packet_status"],
            "main_results_packet_blocked": main_packet_blocked,
            "negative_packet_ready": negative_packet_ready,
            "claim_safe_matrix_clean": claim_safe_clean,
            "neutral_result_ledger_clean": (
                neutral_ledger_summary.get("overall_status")
                == "neutral_result_ledger_ready_no_method_promotion"
            ),
            "publication_completed_rows": accounting_summary.get(
                "publication_completed_rows"
            ),
            "kg_publication_status": kg_publication_summary.get("overall_status"),
            "final_section_prose_authorized": False,
            "final_manuscript_prose_permission": False,
            "final_visual_table_retention_authorized": False,
            "release_authorized": False,
            "publication_site_deployment_authorized": False,
            "kg_citable_component_authorized": False,
            "sterile_repository_creation_authorized": False,
            "working_repository_final_citable": False,
            "method_recommendation_authorized": False,
            "positive_claim_promotion_authorized": False,
            "scientific_no_method_promotion_guard_active": True,
            "neutral_language_unguarded_hit_count": neutral_language_summary.get(
                "unguarded_hit_count"
            ),
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
        },
        "claim_boundaries": [
            "This artifact is a section evidence packet, not manuscript prose.",
            "Section packets may organize source-traceable evidence for later writing but cannot authorize final prose, release, method recommendation, or positive claim promotion.",
            "The main-results packet is intentionally blocked for positive claims.",
            "The Venn-Abers packet is negative/failure-mode evidence only and does not validate Venn-Abers regression.",
        ],
        "sources": {key: rel(root / path, root) for key, path in SOURCE_PATHS.items()},
        "section_packet_rows": rows,
        "checks": checks,
        "failed_checks": failed_checks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Manuscript Section Evidence Packet",
        "",
        f"- Status: `{summary_payload['overall_status']}`",
        f"- Phase: `{summary_payload['phase_state']}`",
        f"- Section packets: {summary_payload['section_packet_row_count']}",
        f"- Safe pre-prose evidence packets: {summary_payload['safe_pre_prose_evidence_packet_count']}",
        f"- Blocked positive packets: {summary_payload['blocked_positive_packet_count']}",
        f"- Missing source artifacts: {summary_payload['missing_source_artifact_count']}",
        f"- Linked neutral-result issues: {summary_payload['linked_neutral_result_issue_count']}",
        f"- Paragraph blueprints complete: {summary_payload['paragraph_blueprint_complete_count']}",
        f"- Reader concept links: {summary_payload['reader_concept_link_count']}",
        f"- Main-results packet: `{summary_payload['main_results_packet_status']}`",
        f"- Negative packet: `{summary_payload['negative_packet_status']}`",
        f"- Final section prose authorized: `{summary_payload['final_section_prose_authorized']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(["", "## Section Packets", ""])
    for row in payload["section_packet_rows"]:
        lines.extend(
            [
                f"### {row['packet_id']}",
                "",
                f"- Target document: `{row['target_document']}`",
                f"- Section role: `{row['section_role']}`",
                f"- Claim-safe surface: `{row['claim_safe_surface_id']}`",
                f"- Packet status: `{row['packet_status']}`",
                f"- Allowed use: {row['allowed_use']}",
                f"- Blocked use: {row['blocked_use']}",
                f"- Reader concepts: {', '.join(f'`{item}`' for item in row['reader_concept_ids'])}",
                "- Paragraph blueprint:",
                *[f"  - {item}" for item in row["paragraph_blueprint"]],
                f"- Source traceability: `{row['source_traceability_status']}`",
                f"- Final prose authorized: `{row['final_section_prose_authorized']}`",
                "",
            ]
        )
    lines.extend(["", "## Checks", ""])
    for check in payload["checks"]:
        lines.append(f"- `{check['check_id']}`: `{check['status']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root)
    out = root / args.out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(json.dumps(payload["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
