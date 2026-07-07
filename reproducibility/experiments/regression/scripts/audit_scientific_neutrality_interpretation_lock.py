"""Build a neutral interpretation lock for publication-prep surfaces.

This artifact translates the latest no-method-promotion policy into a
machine-readable pre-prose control. It is not manuscript prose, not a final
table, and not a method recommendation. It records how current evidence may be
interpreted in the article, supplement, individual report, KG, or site only
while final claims remain blocked.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_scientific_neutrality_interpretation_lock_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/"
    "scientific_neutrality_interpretation_lock.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
PUBLICATION_RECONCILIATION = Path(
    "experiments/regression/manuscript/"
    "publication_phase_progress_reconciliation_audit.json"
)
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
NEUTRAL_LEDGER = Path("experiments/regression/manuscript/neutral_result_ledger.json")
METHOD_SYNTHESIS = REPORT_DIR / "method_performance_synthesis.json"
METHOD_SELECTION_CANDIDATE = REPORT_DIR / "method_selection_candidate_audit.json"
METHOD_SELECTION_INFERENTIAL = REPORT_DIR / "method_selection_inferential_audit.json"
VENN_NEGATIVE = REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
VENN_VALIDATION = REPORT_DIR / "venn_abers_validation_readiness_audit.json"
VENN_CLAIM_GATE = REPORT_DIR / "venn_abers_claim_gate_matrix.json"
PAPER_GATE_MAP = Path("experiments/regression/manuscript/paper_gate_closure_map.json")
SECTION_BOUNDARY = Path(
    "experiments/regression/manuscript/section_claim_boundary_audit.json"
)
CLAIM_SAFE_MATRIX = Path(
    "experiments/regression/manuscript/claim_safe_result_extraction_matrix.json"
)
NAVIGATION_INDEX = Path(
    "experiments/regression/manuscript/article_supplement_kg_navigation_index.json"
)
RELEASE_GAP = Path(
    "experiments/regression/manuscript/publication_release_gap_register.json"
)
KG_QUALITY = Path(
    "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
)

SOURCE_PATHS = {
    "goal_completion_audit": GOAL_COMPLETION,
    "publication_phase_progress_reconciliation_audit": PUBLICATION_RECONCILIATION,
    "neutral_reporting_language_audit": NEUTRAL_LANGUAGE,
    "neutral_result_ledger": NEUTRAL_LEDGER,
    "method_performance_synthesis": METHOD_SYNTHESIS,
    "method_selection_candidate_audit": METHOD_SELECTION_CANDIDATE,
    "method_selection_inferential_audit": METHOD_SELECTION_INFERENTIAL,
    "venn_abers_negative_evidence_disposition_audit": VENN_NEGATIVE,
    "venn_abers_validation_readiness_audit": VENN_VALIDATION,
    "venn_abers_claim_gate_matrix": VENN_CLAIM_GATE,
    "paper_gate_closure_map": PAPER_GATE_MAP,
    "section_claim_boundary_audit": SECTION_BOUNDARY,
    "claim_safe_result_extraction_matrix": CLAIM_SAFE_MATRIX,
    "article_supplement_kg_navigation_index": NAVIGATION_INDEX,
    "publication_release_gap_register": RELEASE_GAP,
    "knowledge_graph_quality_summary": KG_QUALITY,
}

FINAL_AUTHORIZATION_FIELDS = (
    "final_manuscript_prose_permission",
    "manuscript_drafting_authorized",
    "final_section_prose_authorized",
    "final_visual_table_retention_authorized",
    "publication_site_deployment_authorized",
    "kg_citable_component_authorized",
    "sterile_repository_creation_authorized",
    "working_repository_final_citable",
    "method_recommendation_authorized",
    "method_champion_authorized",
    "method_advocacy_authorized",
    "positive_claim_promotion_authorized",
    "validated_venn_abers_regression_claim_ready",
)

PROMOTIONAL_PHRASES = (
    "cqr is the best",
    "cqr is recommended",
    "cqr should be used",
    "recommend cqr",
    "cv+ is recommended",
    "champion method",
    "global best conformal",
    "final selected model",
    "method of choice",
    "validated venn-abers regression interval coverage",
    "winning method",
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


def authorization_violations(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for source_name, payload in payloads.items():
        source_summary = summary(payload)
        for field in FINAL_AUTHORIZATION_FIELDS:
            if source_summary.get(field) is True:
                violations.append(
                    {
                        "source": source_name,
                        "field": field,
                        "value": True,
                    }
                )
    return violations


def promotional_phrase_hits(rows: list[dict[str, Any]]) -> list[str]:
    allowed_text = {
        row.get("row_id"): row.get("allowed_interpretation")
        for row in rows
    }
    text = json.dumps(allowed_text, ensure_ascii=True).lower()
    return [phrase for phrase in PROMOTIONAL_PHRASES if phrase in text]


def interpretation_row(
    *,
    row_id: str,
    surface: str,
    allowed_interpretation: str,
    blocked_interpretation: str,
    evidence_basis: str,
    source_artifacts: list[str],
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "surface": surface,
        "allowed_interpretation": allowed_interpretation,
        "blocked_interpretation": blocked_interpretation,
        "evidence_basis": evidence_basis,
        "source_artifacts": source_artifacts,
        "final_prose_authorized": False,
        "method_recommendation_authorized": False,
        "positive_claim_promotion_authorized": False,
    }


def build_interpretation_rows(root: Path) -> list[dict[str, Any]]:
    source = lambda path: [rel(root / path, root)]  # noqa: E731
    return [
        interpretation_row(
            row_id="experiment_scope",
            surface="article_or_supplement_scope",
            allowed_interpretation=(
                "Describe the work as a broad, audited regression conformal "
                "prediction experiment under the recorded dataset and method scope."
            ),
            blocked_interpretation=(
                "Do not claim literal coverage of every possible internet dataset, "
                "every future method variant, or a completed final paper."
            ),
            evidence_basis=(
                "Goal completion marks the neutral empirical phase complete with "
                "scope limits, while full goal completion remains false."
            ),
            source_artifacts=source(GOAL_COMPLETION),
        ),
        interpretation_row(
            row_id="method_frontier_cqr_cvplus",
            surface="method_discussion_or_table_caption",
            allowed_interpretation=(
                "Report CQR and CV+ as observed descriptive or diagnostic "
                "frontier candidates under the searched surface."
            ),
            blocked_interpretation=(
                "Do not call CQR, CV+, or any other method a global best method, "
                "a default recommendation, or the final selected model."
            ),
            evidence_basis=(
                "Method synthesis and selection audits are descriptive and the "
                "final method/model selection gate is blocked."
            ),
            source_artifacts=[
                rel(root / METHOD_SYNTHESIS, root),
                rel(root / METHOD_SELECTION_CANDIDATE, root),
                rel(root / METHOD_SELECTION_INFERENTIAL, root),
            ],
        ),
        interpretation_row(
            row_id="venn_abers_negative_result",
            surface="negative_results_or_discussion",
            allowed_interpretation=(
                "Report the fast Venn-Abers regression bridge as observed "
                "negative/failure-mode evidence for the current implementation."
            ),
            blocked_interpretation=(
                "Do not claim validated Venn-Abers regression interval coverage "
                "or treat Venn-Abers as a final winning regression method."
            ),
            evidence_basis=(
                "Venn-Abers validation readiness, claim gate, and negative "
                "evidence disposition keep the positive validation claim blocked."
            ),
            source_artifacts=[
                rel(root / VENN_NEGATIVE, root),
                rel(root / VENN_VALIDATION, root),
                rel(root / VENN_CLAIM_GATE, root),
            ],
        ),
        interpretation_row(
            row_id="main_results_positive_claim",
            surface="main_results_section",
            allowed_interpretation=(
                "State that the main-results positive claim surface is currently "
                "blocked and that evidence remains diagnostic or caveated."
            ),
            blocked_interpretation=(
                "Do not promote a final main result, dataset-level result, or "
                "publication-ready positive method conclusion."
            ),
            evidence_basis=(
                "Claim-safe extraction, section-boundary, paper-gate, and "
                "publication-reconciliation controls keep positive claims blocked."
            ),
            source_artifacts=[
                rel(root / CLAIM_SAFE_MATRIX, root),
                rel(root / SECTION_BOUNDARY, root),
                rel(root / PAPER_GATE_MAP, root),
                rel(root / PUBLICATION_RECONCILIATION, root),
            ],
        ),
        interpretation_row(
            row_id="fairness_population_scope",
            surface="fairness_or_group_diagnostics",
            allowed_interpretation=(
                "Use group outputs as diagnostic coverage and width summaries "
                "with explicit scope limits."
            ),
            blocked_interpretation=(
                "Do not claim protected-class, policy, legal, or population-level "
                "fairness conclusions."
            ),
            evidence_basis=(
                "The paper-gate map records fairness/population inference as "
                "blocked and only scoped diagnostic language as allowed."
            ),
            source_artifacts=source(PAPER_GATE_MAP),
        ),
        interpretation_row(
            row_id="bounded_support_scope",
            surface="endpoint_or_interval_handling",
            allowed_interpretation=(
                "Report endpoint hygiene, post-handling checks, and documented "
                "bounded-support caveats."
            ),
            blocked_interpretation=(
                "Do not claim bounded-support validity or target-domain-valid "
                "clipped intervals."
            ),
            evidence_basis=(
                "The paper-gate map keeps the endpoint bounded-support validity "
                "claim blocked under current evidence."
            ),
            source_artifacts=source(PAPER_GATE_MAP),
        ),
        interpretation_row(
            row_id="kg_site_visuals",
            surface="kg_site_or_visual_table_navigation",
            allowed_interpretation=(
                "Use the KG, site, and visual/table artifacts as pre-release "
                "navigation and audit evidence."
            ),
            blocked_interpretation=(
                "Do not cite the KG/site as final, deploy publication pages, or "
                "retain final visuals/tables until downstream gates authorize it."
            ),
            evidence_basis=(
                "Navigation, release-gap, reconciliation, and KG quality reports "
                "show readiness for navigation but no final release authorization."
            ),
            source_artifacts=[
                rel(root / NAVIGATION_INDEX, root),
                rel(root / RELEASE_GAP, root),
                rel(root / PUBLICATION_RECONCILIATION, root),
                rel(root / KG_QUALITY, root),
            ],
        ),
        interpretation_row(
            row_id="sterile_repository_and_manuscript_outputs",
            surface="release_and_citation_material",
            allowed_interpretation=(
                "Describe the sterile final repository, LaTeX/HTML manuscript, "
                "supplement, and site as planned downstream deliverables."
            ),
            blocked_interpretation=(
                "Do not create or cite a final release repository, final article, "
                "supplement, or publication site before all release gates close."
            ),
            evidence_basis=(
                "Release-gap and progress reconciliation artifacts keep all final "
                "publication outputs blocked."
            ),
            source_artifacts=[
                rel(root / RELEASE_GAP, root),
                rel(root / PUBLICATION_RECONCILIATION, root),
            ],
        ),
    ]


def build_payload(root: Path) -> dict[str, Any]:
    loaded = {name: read_json(root / path) for name, path in SOURCE_PATHS.items()}
    present_sources, missing_sources = source_status(root)
    goal = summary(loaded["goal_completion_audit"])
    reconciliation = summary(loaded["publication_phase_progress_reconciliation_audit"])
    neutral_language = summary(loaded["neutral_reporting_language_audit"])
    neutral_ledger = summary(loaded["neutral_result_ledger"])
    method_synthesis = summary(loaded["method_performance_synthesis"])
    venn_negative = summary(loaded["venn_abers_negative_evidence_disposition_audit"])
    venn_validation = summary(loaded["venn_abers_validation_readiness_audit"])
    venn_claim_gate = summary(loaded["venn_abers_claim_gate_matrix"])
    section_boundary = summary(loaded["section_claim_boundary_audit"])
    navigation = summary(loaded["article_supplement_kg_navigation_index"])
    release_gap = summary(loaded["publication_release_gap_register"])
    kg_graph = loaded["knowledge_graph_quality_summary"].get("graph") or {}

    rows = build_interpretation_rows(root)
    rows_with_missing_fields = [
        row["row_id"]
        for row in rows
        if not all(
            row.get(field)
            for field in (
                "allowed_interpretation",
                "blocked_interpretation",
                "evidence_basis",
                "source_artifacts",
            )
        )
    ]
    authorization_hits = authorization_violations(loaded)
    phrase_hits = promotional_phrase_hits(rows)
    neutral_policy_ready = (
        neutral_language.get("overall_status") == "neutral_reporting_language_audit_pass"
        and safe_int(neutral_language.get("unguarded_hit_count")) == 0
        and goal.get("positive_claim_publication_ready") is False
        and reconciliation.get("method_recommendation_authorized") is False
        and reconciliation.get("positive_claim_promotion_authorized") is False
        and release_gap.get("method_recommendation_authorized") is False
        and release_gap.get("positive_claim_promotion_authorized") is False
        and neutral_ledger.get("positive_claim_promotion_authorized_count") == 0
    )
    method_boundary_ready = (
        method_synthesis.get("claim_status") == "descriptive_no_final_selection"
        and goal.get("primary_diagnostic_method") == "cqr"
        and goal.get("positive_claim_publication_ready") is False
        and "cqr" in json.dumps(method_synthesis).lower()
    )
    analysis_only_no_champion_method = (
        method_synthesis.get("claim_status") == "descriptive_no_final_selection"
        and goal.get("positive_claim_publication_ready") is False
        and reconciliation.get("method_recommendation_authorized") is False
        and reconciliation.get("positive_claim_promotion_authorized") is False
        and release_gap.get("method_recommendation_authorized") is False
        and release_gap.get("positive_claim_promotion_authorized") is False
        and not phrase_hits
        and not authorization_hits
    )
    venn_boundary_ready = (
        venn_negative.get("negative_result_reporting_ready") is True
        and venn_negative.get("can_support_validated_venn_abers_regression") is False
        and venn_validation.get("can_support_venn_abers_regression_validation")
        is False
        and venn_claim_gate.get("can_support_validated_venn_abers_regression")
        is False
        and section_boundary.get("venn_abers_negative_boundary_preserved") is True
    )
    final_outputs_blocked = (
        reconciliation.get("final_manuscript_prose_permission") is False
        and reconciliation.get("final_visual_table_retention_authorized") is False
        and reconciliation.get("publication_site_deployment_authorized") is False
        and reconciliation.get("kg_citable_component_authorized") is False
        and reconciliation.get("sterile_repository_creation_authorized") is False
        and navigation.get("working_repository_final_citable") is False
        and release_gap.get("release_authorized_count") == 0
    )
    kg_navigation_ready = (
        navigation.get("overall_status")
        == "article_supplement_kg_navigation_index_ready_no_release"
        and safe_int(kg_graph.get("node_count")) >= 3378
        and safe_int(kg_graph.get("isolated_node_count")) == 0
    )

    checks = [
        check_row(
            "all_interpretation_lock_sources_present",
            not missing_sources,
            {"missing_source_artifacts": missing_sources},
            "missing_interpretation_lock_source_artifact",
        ),
        check_row(
            "interpretation_rows_complete",
            len(rows) == 8 and not rows_with_missing_fields,
            {
                "interpretation_row_count": len(rows),
                "rows_with_missing_fields": rows_with_missing_fields,
            },
            "interpretation_lock_row_incomplete",
        ),
        check_row(
            "neutral_policy_and_language_controls_pass",
            neutral_policy_ready and not phrase_hits,
            {
                "neutral_language_status": neutral_language.get("overall_status"),
                "unguarded_hit_count": neutral_language.get("unguarded_hit_count"),
                "promotional_phrase_hits": phrase_hits,
            },
            "neutral_policy_or_language_control_failed",
        ),
        check_row(
            "method_frontier_not_promoted",
            method_boundary_ready and not authorization_hits,
            {
                "method_synthesis_claim_status": method_synthesis.get("claim_status"),
                "primary_diagnostic_method": goal.get("primary_diagnostic_method"),
                "authorization_violations": authorization_hits,
            },
            "method_frontier_promoted_to_recommendation",
        ),
        check_row(
            "analysis_only_no_champion_method_locked",
            analysis_only_no_champion_method,
            {
                "result_reporting_policy": (
                    "analysis_only_report_observed_behavior_no_method_advocacy"
                ),
                "method_synthesis_claim_status": method_synthesis.get("claim_status"),
                "method_champion_authorized": False,
                "method_recommendation_authorized": reconciliation.get(
                    "method_recommendation_authorized"
                ),
                "positive_claim_promotion_authorized": reconciliation.get(
                    "positive_claim_promotion_authorized"
                ),
                "promotional_phrase_hits": phrase_hits,
                "authorization_violations": authorization_hits,
            },
            "method_champion_or_advocacy_language_opened",
        ),
        check_row(
            "venn_abers_negative_boundary_preserved",
            venn_boundary_ready,
            {
                "negative_result_reporting_ready": venn_negative.get(
                    "negative_result_reporting_ready"
                ),
                "can_support_validated_venn_abers_regression": venn_negative.get(
                    "can_support_validated_venn_abers_regression"
                ),
                "claim_gate_status": venn_claim_gate.get("overall_status"),
            },
            "venn_abers_positive_validation_claim_opened",
        ),
        check_row(
            "final_outputs_and_release_remain_blocked",
            final_outputs_blocked,
            {
                "release_authorized_count": release_gap.get(
                    "release_authorized_count"
                ),
                "working_repository_final_citable": navigation.get(
                    "working_repository_final_citable"
                ),
                "sterile_repository_creation_authorized": reconciliation.get(
                    "sterile_repository_creation_authorized"
                ),
            },
            "final_output_or_release_authorized_too_early",
        ),
        check_row(
            "kg_navigation_ready_but_not_citable_final",
            kg_navigation_ready,
            {
                "navigation_status": navigation.get("overall_status"),
                "kg_node_count": kg_graph.get("node_count"),
                "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
            },
            "kg_navigation_or_quality_not_ready",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "pass"]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {name: rel(root / path, root) for name, path in SOURCE_PATHS.items()},
        "present_source_artifacts": present_sources,
        "missing_source_artifacts": missing_sources,
        "interpretation_rows": rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This lock authorizes interpretation constraints only, not final prose.",
            "Observed descriptive patterns must not be rewritten as method recommendations.",
            "The study is an analysis-only scientific test; no method may be framed as a champion, winner, or general recommendation.",
            "Negative Venn-Abers evidence may be reported without validating Venn-Abers regression.",
            "Final article, supplement, KG/site citation, and sterile release remain blocked.",
        ],
        "summary": {
            "overall_status": (
                "scientific_neutrality_interpretation_lock_ready_no_method_promotion"
                if not failed_checks
                else "scientific_neutrality_interpretation_lock_blocked"
            ),
            "phase_state": (
                "neutral_interpretation_locked_final_claims_and_outputs_blocked"
            ),
            "interpretation_row_count": len(rows),
            "source_artifact_count": len(present_sources),
            "missing_source_artifact_count": len(missing_sources),
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
            "neutral_language_unguarded_hit_count": neutral_language.get(
                "unguarded_hit_count"
            ),
            "method_synthesis_claim_status": method_synthesis.get("claim_status"),
            "primary_diagnostic_method": goal.get("primary_diagnostic_method"),
            "cqr_cvplus_reporting_role": (
                "descriptive_diagnostic_no_final_selection_no_method_promotion"
            ),
            "venn_abers_reporting_role": (
                "negative_failure_mode_no_validated_regression_claim"
            ),
            "venn_abers_negative_boundary_preserved": venn_boundary_ready,
            "validated_venn_abers_regression_claim_ready": False,
            "main_results_positive_boundary_blocked": section_boundary.get(
                "main_results_positive_boundary_blocked"
            ),
            "positive_claim_publication_ready": goal.get(
                "positive_claim_publication_ready"
            ),
            "method_recommendation_authorized": False,
            "positive_claim_promotion_authorized": False,
            "final_manuscript_prose_permission": False,
            "final_visual_table_retention_authorized": False,
            "publication_site_deployment_authorized": False,
            "kg_citable_component_authorized": False,
            "sterile_repository_creation_authorized": False,
            "working_repository_final_citable": False,
            "release_authorized_count": release_gap.get("release_authorized_count"),
            "kg_navigation_ready": kg_navigation_ready,
            "kg_node_count": kg_graph.get("node_count"),
            "kg_edge_count": kg_graph.get("edge_count"),
            "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
            "authorization_violation_count": len(authorization_hits),
            "promotional_phrase_hit_count": len(phrase_hits),
            "scientific_test_not_method_promotion": True,
            "analysis_only_no_champion_method": analysis_only_no_champion_method,
            "method_champion_authorized": False,
            "method_advocacy_authorized": False,
            "result_reporting_policy": (
                "analysis_only_report_observed_behavior_no_method_advocacy"
            ),
        },
    }
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Scientific Neutrality Interpretation Lock",
        "",
        "This is a pre-prose control. It records how current evidence may be interpreted without promoting a method or authorizing final outputs.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Phase state: `{summary['phase_state']}`",
        f"- Interpretation rows: {summary['interpretation_row_count']}",
        f"- Unguarded neutral-language hits: {summary['neutral_language_unguarded_hit_count']}",
        f"- CQR/CV+ role: `{summary['cqr_cvplus_reporting_role']}`",
        f"- Venn-Abers role: `{summary['venn_abers_reporting_role']}`",
        f"- Result reporting policy: `{summary['result_reporting_policy']}`",
        f"- Champion method authorized: `{summary['method_champion_authorized']}`",
        f"- Method recommendation authorized: `{summary['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{summary['positive_claim_promotion_authorized']}`",
        f"- Final prose permission: `{summary['final_manuscript_prose_permission']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        "",
        "## Interpretation Rows",
        "",
        "| Row | Surface | Allowed interpretation | Blocked interpretation |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["interpretation_rows"]:
        allowed = row["allowed_interpretation"].replace("|", "\\|")
        blocked = row["blocked_interpretation"].replace("|", "\\|")
        lines.append(
            f"| `{row['row_id']}` | `{row['surface']}` | {allowed} | {blocked} |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Blocker |",
            "| --- | --- | --- |",
        ]
    )
    for check in payload["checks"]:
        lines.append(
            f"| `{check['check_id']}` | `{check['status']}` | `{check['blocker']}` |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundaries",
            "",
        ]
    )
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root)
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "interpretation_rows": payload["summary"]["interpretation_row_count"],
                "failed_checks": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
