"""Build a claim-safe result extraction matrix for manuscript planning.

This artifact maps paper-facing result surfaces to the evidence controls that
bound them. It is a pre-prose planning matrix: it does not write manuscript
text, retain final visuals, recommend a conformal method, promote positive
claims, or authorize release.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_claim_safe_result_extraction_matrix_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/claim_safe_result_extraction_matrix.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
PAPER_GATE_CLOSURE = Path(
    "experiments/regression/manuscript/paper_gate_closure_map.json"
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
KG_PUBLICATION = REPORT_DIR / "kg_publication_quality_audit.json"
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
EXPERIMENT_ACCOUNTING = REPORT_DIR / "experiment_accounting_audit.json"
METHOD_PERFORMANCE = REPORT_DIR / "method_performance_synthesis.json"
VENN_ABERS_NEGATIVE = REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
FINAL_SELECTION = REPORT_DIR / "final_selection_claim_boundary_audit.json"


SOURCE_PATHS = {
    "paper_readiness": PAPER_READINESS,
    "paper_gate_closure": PAPER_GATE_CLOSURE,
    "neutral_ledger": NEUTRAL_LEDGER,
    "blueprint_alignment": BLUEPRINT_ALIGNMENT,
    "individual_report_blueprint": INDIVIDUAL_REPORT_BLUEPRINT,
    "release_gap": RELEASE_GAP,
    "retention_readiness": RETENTION_READINESS,
    "visual_render_audit": VISUAL_RENDER_AUDIT,
    "kg_publication": KG_PUBLICATION,
    "neutral_language": NEUTRAL_LANGUAGE,
    "experiment_accounting": EXPERIMENT_ACCOUNTING,
    "method_performance": METHOD_PERFORMANCE,
    "venn_abers_negative": VENN_ABERS_NEGATIVE,
    "final_selection": FINAL_SELECTION,
}


SURFACE_DEFINITIONS = [
    {
        "surface_id": "dataset_table",
        "surface_family": "main_article",
        "surface_role": "descriptive_dataset_scope_table",
        "source_keys": ["paper_readiness", "blueprint_alignment", "neutral_ledger"],
        "neutral_result_ids": ["neutral_publication_policy_no_promotion"],
        "pre_prose_extraction_status": "candidate_source_audit_only",
        "claim_scope": "dataset_scope_description_no_final_result_promotion",
        "allowed_language": [
            "Dataset and source audit rows may be described as scope evidence.",
            "Dataset-specific final-result promotion remains withheld.",
        ],
        "disallowed_language": [
            "publication-ready dataset final result",
            "final main-table dataset promotion",
        ],
    },
    {
        "surface_id": "method_table",
        "surface_family": "main_article",
        "surface_role": "method_scope_table",
        "source_keys": ["method_performance", "neutral_ledger", "blueprint_alignment"],
        "neutral_result_ids": ["method_performance_descriptive_frontier"],
        "pre_prose_extraction_status": "candidate_method_scope_only",
        "claim_scope": "method_inventory_and_descriptive_frontier_no_recommendation",
        "allowed_language": [
            "Method families and descriptive frontier frequencies may be reported as observed evidence.",
            "CQR/CV+ language must stay diagnostic and non-recommendational.",
        ],
        "disallowed_language": [
            "best method",
            "final method selection",
            "universal conformal recommendation",
        ],
    },
    {
        "surface_id": "main_results_table",
        "surface_family": "main_article",
        "surface_role": "positive_main_result_surface",
        "source_keys": ["paper_readiness", "paper_gate_closure", "final_selection"],
        "neutral_result_ids": ["selection_multiplicity_robustness_diagnostic"],
        "pre_prose_extraction_status": "blocked_positive_claim_surface",
        "claim_scope": "blocked_until_dataset_method_multiplicity_and_claim_gates_pass",
        "allowed_language": [
            "Main-result promotion is blocked in the current evidence state.",
            "Candidate bundles may be discussed only as diagnostic or caveated evidence.",
        ],
        "disallowed_language": [
            "final main result",
            "positive method conclusion",
            "method/model winner",
        ],
    },
    {
        "surface_id": "robustness_results_table",
        "surface_family": "supplementary_document",
        "surface_role": "caveated_robustness_surface",
        "source_keys": [
            "paper_readiness",
            "paper_gate_closure",
            "neutral_ledger",
            "blueprint_alignment",
        ],
        "neutral_result_ids": ["selection_multiplicity_robustness_diagnostic"],
        "pre_prose_extraction_status": "candidate_caveated_diagnostic_surface",
        "claim_scope": "robustness_diagnostic_no_final_selection",
        "allowed_language": [
            "Robustness rows may be framed as post-selection diagnostics.",
            "Multiplicity and blocked positive-gate caveats must travel with the table.",
        ],
        "disallowed_language": [
            "confirmatory superiority",
            "final model selection",
            "validated production evidence",
        ],
    },
    {
        "surface_id": "negative_results_table",
        "surface_family": "supplementary_document",
        "surface_role": "negative_failure_mode_surface",
        "source_keys": [
            "paper_readiness",
            "paper_gate_closure",
            "venn_abers_negative",
            "neutral_ledger",
        ],
        "neutral_result_ids": ["venn_abers_regression_negative_evidence"],
        "pre_prose_extraction_status": "candidate_negative_result_surface",
        "claim_scope": "venn_abers_negative_failure_mode_no_validated_claim",
        "allowed_language": [
            "Fast Venn-Abers bridge evidence may be reported as negative/failure-mode evidence.",
            "No positive Venn-Abers regression validation is implied.",
        ],
        "disallowed_language": [
            "validated Venn-Abers regression",
            "positive Venn-Abers result",
            "Venn-Abers recommendation",
        ],
    },
    {
        "surface_id": "methodology_appendix",
        "surface_family": "supplementary_document",
        "surface_role": "methodology_control_surface",
        "source_keys": ["paper_gate_closure", "neutral_ledger", "kg_publication"],
        "neutral_result_ids": ["neutral_publication_policy_no_promotion"],
        "pre_prose_extraction_status": "candidate_control_appendix",
        "claim_scope": "methodology_controls_no_empirical_claim_strengthening",
        "allowed_language": [
            "Control and audit procedures may be described as reproducibility infrastructure.",
            "Control presence must not be converted into scientific validity claims.",
        ],
        "disallowed_language": [
            "proof of validity",
            "production readiness",
            "complete scientific finality",
        ],
    },
    {
        "surface_id": "reproducibility_appendix",
        "surface_family": "supplementary_document",
        "surface_role": "reproducibility_and_traceability_surface",
        "source_keys": ["experiment_accounting", "kg_publication", "release_gap"],
        "neutral_result_ids": ["empirical_scope_accounting"],
        "pre_prose_extraction_status": "candidate_reproducibility_appendix",
        "claim_scope": "accounting_and_traceability_no_method_claim",
        "allowed_language": [
            "Completed-row accounting, resume controls, and KG traceability may be reported.",
            "The working repository remains non-citable as the final public artifact.",
        ],
        "disallowed_language": [
            "final repository release",
            "working repository final citable",
            "goal complete",
        ],
    },
    {
        "surface_id": "individual_experiment_report",
        "surface_family": "individual_experiment_report",
        "surface_role": "author_stamped_pre_prose_report_surface",
        "source_keys": ["individual_report_blueprint", "release_gap", "neutral_ledger"],
        "neutral_result_ids": ["neutral_publication_policy_no_promotion"],
        "pre_prose_extraction_status": "blueprint_only_no_final_report",
        "claim_scope": "individual_report_blueprint_no_final_outputs",
        "allowed_language": [
            "The approved author header and section map may be reused later.",
            "Final report prose and LaTeX/HTML/Markdown outputs remain unauthorized.",
        ],
        "disallowed_language": [
            "final individual report",
            "released individual report",
            "citable individual report",
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


def build_surface_rows(root: Path, neutral_ledger: dict[str, Any]) -> list[dict[str, Any]]:
    ledger_by_result = {
        str(row.get("result_id")): row
        for row in result_rows(neutral_ledger)
        if row.get("result_id")
    }
    rows: list[dict[str, Any]] = []
    for index, surface in enumerate(SURFACE_DEFINITIONS):
        paths = [SOURCE_PATHS[key] for key in surface["source_keys"]]
        present, missing = source_status(root, paths)
        result_ids = list(surface["neutral_result_ids"])
        linked_results = [ledger_by_result[result_id] for result_id in result_ids if result_id in ledger_by_result]
        status = str(surface["pre_prose_extraction_status"])
        rows.append(
            {
                "surface_id": surface["surface_id"],
                "row_index": index,
                "surface_family": surface["surface_family"],
                "surface_role": surface["surface_role"],
                "source_keys": list(surface["source_keys"]),
                "source_artifacts": present,
                "missing_source_artifacts": missing,
                "source_traceability_status": "pass" if not missing else "fail",
                "neutral_result_ids": result_ids,
                "linked_neutral_result_count": len(linked_results),
                "neutral_result_claim_statuses": [
                    row.get("claim_status") for row in linked_results
                ],
                "pre_prose_extraction_status": status,
                "claim_scope": surface["claim_scope"],
                "safe_pre_prose_extraction_candidate": not status.startswith("blocked"),
                "positive_claim_surface_blocked": status.startswith("blocked"),
                "allowed_language": list(surface["allowed_language"]),
                "disallowed_language": list(surface["disallowed_language"]),
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
                    "Surface row is a pre-prose extraction control only; it "
                    "cannot authorize final manuscript text, final visual/table "
                    "retention, method recommendation, positive claim promotion, "
                    "or release."
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
    paper_readiness = read_json(root / PAPER_READINESS)
    paper_gate_closure = read_json(root / PAPER_GATE_CLOSURE)
    neutral_ledger = read_json(root / NEUTRAL_LEDGER)
    blueprint_alignment = read_json(root / BLUEPRINT_ALIGNMENT)
    individual_report = read_json(root / INDIVIDUAL_REPORT_BLUEPRINT)
    release_gap = read_json(root / RELEASE_GAP)
    retention = read_json(root / RETENTION_READINESS)
    visual_render = read_json(root / VISUAL_RENDER_AUDIT)
    kg_publication = read_json(root / KG_PUBLICATION)
    neutral_language = read_json(root / NEUTRAL_LANGUAGE)
    accounting = read_json(root / EXPERIMENT_ACCOUNTING)
    venn_abers_negative = read_json(root / VENN_ABERS_NEGATIVE)

    readiness_summary = summary(paper_readiness)
    closure_summary = summary(paper_gate_closure)
    ledger_summary = summary(neutral_ledger)
    alignment_summary = summary(blueprint_alignment)
    individual_summary = summary(individual_report)
    release_summary = summary(release_gap)
    retention_summary = summary(retention)
    visual_summary = summary(visual_render)
    kg_publication_summary = summary(kg_publication)
    neutral_language_summary = summary(neutral_language)
    accounting_summary = summary(accounting)
    venn_negative_summary = summary(venn_abers_negative)

    rows = build_surface_rows(root, neutral_ledger)
    row_by_id = {row["surface_id"]: row for row in rows}
    missing_source_count = sum(len(row["missing_source_artifacts"]) for row in rows)
    linked_result_issue_count = sum(
        safe_int(row["linked_neutral_result_count"]) == 0 for row in rows
    )
    final_authorization_count = sum(
        row["final_manuscript_prose_permission"]
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

    candidate_count = sum(row["safe_pre_prose_extraction_candidate"] for row in rows)
    blocked_positive_count = sum(row["positive_claim_surface_blocked"] for row in rows)
    family_counts = Counter(row["surface_family"] for row in rows)
    status_counts = Counter(row["pre_prose_extraction_status"] for row in rows)

    neutral_ledger_clean = (
        ledger_summary.get("overall_status")
        == "neutral_result_ledger_ready_no_method_promotion"
        and safe_int(ledger_summary.get("positive_claim_promotion_authorized_count")) == 0
        and safe_int(ledger_summary.get("final_method_selection_authorized_count")) == 0
        and ledger_summary.get("cqr_descriptive_candidate_recorded") is True
        and ledger_summary.get("venn_abers_negative_result_recorded") is True
    )
    no_final_release = (
        release_summary.get("overall_status")
        == "publication_release_gap_register_ready_no_final_release"
        and safe_int(release_summary.get("release_authorized_count")) == 0
        and release_summary.get("final_manuscript_prose_permission") is False
        and release_summary.get("method_recommendation_authorized") is False
        and release_summary.get("positive_claim_promotion_authorized") is False
        and release_summary.get("working_repository_final_citable") is False
    )
    visual_retention_blocked = (
        retention_summary.get("final_visual_table_retention_authorized") is False
        and visual_summary.get("final_visual_table_retention_authorized") is False
        and safe_int(visual_summary.get("final_retained_artifact_count")) == 0
    )
    negative_result_ready = (
        row_by_id["negative_results_table"]["safe_pre_prose_extraction_candidate"]
        and closure_summary.get("venn_abers_negative_result_reporting_ready") is True
        and venn_negative_summary.get("negative_result_reporting_ready") is True
    )
    main_result_blocked = (
        row_by_id["main_results_table"]["positive_claim_surface_blocked"]
        and readiness_summary.get("overall_status")
        == "paper_readiness_blocked_with_evidence_map"
        and safe_int(readiness_summary.get("main_surface_blocked_count")) >= 1
        and safe_int(closure_summary.get("positive_claim_ready_gate_count")) == 0
    )

    checks = [
        check_row(
            "surface_rows_source_traceable",
            len(rows) == len(SURFACE_DEFINITIONS) and missing_source_count == 0,
            {
                "surface_row_count": len(rows),
                "expected_surface_row_count": len(SURFACE_DEFINITIONS),
                "missing_source_artifact_count": missing_source_count,
            },
            "surface_source_traceability_missing",
        ),
        check_row(
            "neutral_result_links_clean",
            linked_result_issue_count == 0 and neutral_ledger_clean,
            {
                "linked_result_issue_count": linked_result_issue_count,
                "neutral_ledger_status": ledger_summary.get("overall_status"),
            },
            "neutral_result_links_or_ledger_not_clean",
        ),
        check_row(
            "main_results_surface_remains_blocked",
            main_result_blocked,
            {
                "paper_readiness_status": readiness_summary.get("overall_status"),
                "main_surface_blocked_count": readiness_summary.get(
                    "main_surface_blocked_count"
                ),
                "positive_claim_ready_gate_count": closure_summary.get(
                    "positive_claim_ready_gate_count"
                ),
            },
            "main_results_surface_not_blocked",
        ),
        check_row(
            "negative_results_surface_ready_as_negative_only",
            negative_result_ready,
            {
                "paper_gate_closure_status": closure_summary.get("overall_status"),
                "venn_abers_negative_result_reporting_ready": closure_summary.get(
                    "venn_abers_negative_result_reporting_ready"
                ),
                "negative_disposition_status": venn_negative_summary.get(
                    "overall_status"
                ),
            },
            "negative_results_surface_not_ready_or_overpromoted",
        ),
        check_row(
            "article_and_individual_blueprints_remain_pre_prose",
            alignment_summary.get("final_manuscript_prose_permission") is False
            and individual_summary.get("final_report_prose_permission") is False
            and individual_summary.get("release_authorized") is False,
            {
                "article_alignment_status": alignment_summary.get("overall_status"),
                "individual_report_status": individual_summary.get("overall_status"),
                "individual_report_release_authorized": individual_summary.get(
                    "release_authorized"
                ),
            },
            "blueprint_layer_authorized_final_prose",
        ),
        check_row(
            "visual_table_retention_not_finalized",
            visual_retention_blocked,
            {
                "retention_status": retention_summary.get("overall_status"),
                "render_audit_status": visual_summary.get("overall_status"),
                "final_retained_artifact_count": visual_summary.get(
                    "final_retained_artifact_count"
                ),
            },
            "visual_table_final_retention_authorized",
        ),
        check_row(
            "release_and_repository_outputs_remain_blocked",
            no_final_release,
            {
                "release_gap_status": release_summary.get("overall_status"),
                "release_authorized_count": release_summary.get(
                    "release_authorized_count"
                ),
                "working_repository_final_citable": release_summary.get(
                    "working_repository_final_citable"
                ),
            },
            "release_or_repository_output_authorized",
        ),
        check_row(
            "kg_and_accounting_ready_for_traceable_extraction",
            kg_publication_pre_release_ready(kg_publication_summary)
            and accounting_summary.get("overall_status") == "experiment_accounting_pass",
            {
                "kg_publication_status": kg_publication_summary.get("overall_status"),
                "experiment_accounting_status": accounting_summary.get("overall_status"),
                "publication_completed_rows": accounting_summary.get(
                    "publication_completed_rows"
                ),
            },
            "kg_or_accounting_not_ready",
        ),
        check_row(
            "neutral_reporting_language_clean",
            neutral_language_summary.get("overall_status")
            == "neutral_reporting_language_audit_pass"
            and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0,
            {
                "neutral_language_status": neutral_language_summary.get("overall_status"),
                "unguarded_hit_count": neutral_language_summary.get("unguarded_hit_count"),
            },
            "neutral_language_guard_not_clean",
        ),
        check_row(
            "no_final_authorizations_or_method_promotion",
            final_authorization_count == 0
            and safe_int(release_summary.get("positive_claim_ready_gate_count")) == 0
            and safe_int(closure_summary.get("positive_claim_ready_gate_count")) == 0,
            {
                "final_authorization_count": final_authorization_count,
                "release_positive_claim_ready_gate_count": release_summary.get(
                    "positive_claim_ready_gate_count"
                ),
                "closure_positive_claim_ready_gate_count": closure_summary.get(
                    "positive_claim_ready_gate_count"
                ),
            },
            "final_authorization_or_method_promotion_detected",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    overall_status = (
        "claim_safe_result_extraction_matrix_ready_no_final_claims"
        if not failed_checks
        else "claim_safe_result_extraction_matrix_blocked"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "phase_state": "neutral_pre_prose_result_extraction_active_final_outputs_blocked",
            "surface_row_count": len(rows),
            "source_traceable_row_count": sum(
                row["source_traceability_status"] == "pass" for row in rows
            ),
            "missing_source_artifact_count": missing_source_count,
            "linked_neutral_result_issue_count": linked_result_issue_count,
            "surface_family_counts": dict(sorted(family_counts.items())),
            "pre_prose_extraction_status_counts": dict(sorted(status_counts.items())),
            "safe_pre_prose_extraction_candidate_count": candidate_count,
            "blocked_positive_surface_count": blocked_positive_count,
            "main_results_surface_status": row_by_id["main_results_table"][
                "pre_prose_extraction_status"
            ],
            "negative_results_surface_status": row_by_id["negative_results_table"][
                "pre_prose_extraction_status"
            ],
            "negative_result_reporting_ready": negative_result_ready,
            "main_result_positive_claim_blocked": main_result_blocked,
            "neutral_result_ledger_clean": neutral_ledger_clean,
            "kg_publication_status": kg_publication_summary.get("overall_status"),
            "experiment_accounting_status": accounting_summary.get("overall_status"),
            "publication_completed_rows": accounting_summary.get(
                "publication_completed_rows"
            ),
            "paper_blocked_gate_count": readiness_summary.get("blocked_gate_count"),
            "positive_claim_ready_gate_count": closure_summary.get(
                "positive_claim_ready_gate_count"
            ),
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
            "This artifact is a claim-safe result extraction matrix, not final manuscript prose.",
            "Pre-prose extraction candidates are source-traceable planning rows only; final visual/table retention and release remain unauthorized.",
            "The main-results surface remains blocked because positive dataset, method-selection, multiplicity, fairness, and bounded-support gates have not passed.",
            "Negative Venn-Abers material may be extracted only as negative/failure-mode evidence, not as validated Venn-Abers regression.",
            "CQR/CV+ material may be extracted only as diagnostic/descriptive evidence, not as a recommendation or final selection.",
        ],
        "checks": checks,
        "failed_checks": failed_checks,
        "surface_rows": rows,
        "sources": {key: rel(root / path, root) for key, path in SOURCE_PATHS.items()},
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Claim-Safe Result Extraction Matrix",
        "",
        "This is a neutral pre-prose planning matrix. It maps paper-facing result surfaces to source artifacts and claim boundaries without writing final manuscript text, retaining final visuals, recommending a method, promoting a positive claim, or authorizing release.",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase state: `{summary_payload['phase_state']}`",
        f"- Surface rows: {summary_payload['surface_row_count']}",
        f"- Safe pre-prose extraction candidates: {summary_payload['safe_pre_prose_extraction_candidate_count']}",
        f"- Blocked positive surfaces: {summary_payload['blocked_positive_surface_count']}",
        f"- Main results surface: `{summary_payload['main_results_surface_status']}`",
        f"- Negative results surface: `{summary_payload['negative_results_surface_status']}`",
        f"- Final prose permission: `{summary_payload['final_manuscript_prose_permission']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Surface Rows",
        "",
        "| Surface | Role | Extraction status | Source traceability | Linked results | Final prose | Claim promotion |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["surface_rows"]:
        lines.append(
            "| `{surface}` | `{role}` | `{status}` | `{trace}` | {links} | `{prose}` | `{claim}` |".format(
                surface=row["surface_id"],
                role=row["surface_role"],
                status=row["pre_prose_extraction_status"],
                trace=row["source_traceability_status"],
                links=row["linked_neutral_result_count"],
                prose=row["final_manuscript_prose_permission"],
                claim=row["positive_claim_promotion_authorized"],
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
                "surface_row_count": payload["summary"]["surface_row_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
