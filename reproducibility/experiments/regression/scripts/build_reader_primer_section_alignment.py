"""Build the reader-primer to manuscript-section alignment map.

This pre-prose artifact connects reader-facing conformal prediction concepts to
planned article, supplement, and individual-report sections. It is a drafting
guardrail only: it does not write final manuscript prose or authorize method
recommendations.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_reader_primer_section_alignment_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/reader_primer_section_alignment.json"
)
PRIMER_MAP = Path(
    "experiments/regression/manuscript/reader_method_primer_citation_map.json"
)
ARTICLE_ALIGNMENT = Path(
    "experiments/regression/manuscript/article_supplement_blueprint_alignment.json"
)
INDIVIDUAL_BLUEPRINT = Path(
    "experiments/regression/manuscript/individual_experiment_report_blueprint.json"
)


ROLE_CONCEPT_MAP = {
    "author_header_and_scope_identity": [
        "conformal_prediction_regression",
        "result_metrics_and_claim_boundaries",
    ],
    "empirical_scope_accounting_only": [
        "conformal_prediction_regression",
        "alpha_and_nominal_coverage",
        "result_metrics_and_claim_boundaries",
    ],
    "source_audit_summary_no_new_dataset_claim": [
        "conformal_prediction_regression",
        "weighted_conformal_covariate_shift",
        "result_metrics_and_claim_boundaries",
    ],
    "methodology_integrity_controls_no_claim_strengthening": [
        "split_conformal_regression",
        "normalized_and_locally_adaptive_split",
        "result_metrics_and_claim_boundaries",
    ],
    "method_scope_no_final_selection": [
        "conformal_prediction_regression",
        "split_conformal_regression",
        "conformalized_quantile_regression_cqr",
        "jackknife_plus_and_cv_plus",
        "mondrian_and_group_calibration",
        "normalized_and_locally_adaptive_split",
        "weighted_conformal_covariate_shift",
        "tail_specific_intervals",
        "venn_abers_predictive_distributions",
        "distributional_and_full_conformal_references",
    ],
    "diagnostic_selection_evidence_no_final_winner": [
        "alpha_and_nominal_coverage",
        "conformalized_quantile_regression_cqr",
        "jackknife_plus_and_cv_plus",
        "result_metrics_and_claim_boundaries",
    ],
    "negative_failure_mode_no_validated_regression_claim": [
        "venn_abers_predictive_distributions",
        "result_metrics_and_claim_boundaries",
    ],
    "blocked_bounded_support_and_fairness_claims": [
        "mondrian_and_group_calibration",
        "normalized_and_locally_adaptive_split",
        "weighted_conformal_covariate_shift",
        "result_metrics_and_claim_boundaries",
    ],
    "kg_navigation_candidate_release_blocked": [
        "result_metrics_and_claim_boundaries",
        "distributional_and_full_conformal_references",
    ],
    "release_gap_summary_no_final_release": [
        "result_metrics_and_claim_boundaries",
    ],
    "descriptive_method_behavior_no_final_selection": [
        "conformal_prediction_regression",
        "alpha_and_nominal_coverage",
        "split_conformal_regression",
        "conformalized_quantile_regression_cqr",
        "jackknife_plus_and_cv_plus",
        "result_metrics_and_claim_boundaries",
    ],
    "selection_robustness_diagnostic_no_final_winner": [
        "conformalized_quantile_regression_cqr",
        "jackknife_plus_and_cv_plus",
        "result_metrics_and_claim_boundaries",
    ],
    "post_selection_diagnostic_no_final_winner": [
        "alpha_and_nominal_coverage",
        "conformalized_quantile_regression_cqr",
        "jackknife_plus_and_cv_plus",
        "result_metrics_and_claim_boundaries",
    ],
    "bounded_support_endpoint_blocker_no_validity_claim": [
        "normalized_and_locally_adaptive_split",
        "weighted_conformal_covariate_shift",
        "result_metrics_and_claim_boundaries",
    ],
    "fairness_group_diagnostic_no_population_claim": [
        "alpha_and_nominal_coverage",
        "mondrian_and_group_calibration",
        "result_metrics_and_claim_boundaries",
    ],
    "integrity_caveat_inventory_no_claim_strengthening": [
        "split_conformal_regression",
        "jackknife_plus_and_cv_plus",
        "result_metrics_and_claim_boundaries",
    ],
    "claim_boundary_register_no_positive_claim_conversion": [
        "conformal_prediction_regression",
        "distributional_and_full_conformal_references",
        "result_metrics_and_claim_boundaries",
    ],
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


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def alignment_row(
    *,
    source_family: str,
    row_index: int,
    row_id: str,
    role: str,
    target_surfaces: list[str],
    concept_ids: list[str],
    known_concepts: set[str],
) -> dict[str, Any]:
    missing = sorted(concept_id for concept_id in concept_ids if concept_id not in known_concepts)
    return {
        "alignment_id": f"{source_family}:{row_id}",
        "source_family": source_family,
        "row_index": row_index,
        "source_row_id": row_id,
        "scientific_reporting_role": role,
        "target_surfaces": target_surfaces,
        "required_concept_ids": concept_ids,
        "missing_concept_ids": missing,
        "concept_alignment_status": "pass" if not missing and concept_ids else "fail",
        "final_manuscript_prose_permission": False,
        "method_recommendation_authorized": False,
        "method_champion_authorized": False,
        "positive_claim_promotion_authorized": False,
        "claim_boundary": (
            "This alignment row only states which concepts must be explained "
            "before drafting; it does not write final prose or authorize "
            "positive method claims."
        ),
    }


def build_payload(root: Path) -> dict[str, Any]:
    primer = read_json(root / PRIMER_MAP)
    article = read_json(root / ARTICLE_ALIGNMENT)
    individual = read_json(root / INDIVIDUAL_BLUEPRINT)
    primer_summary = primer.get("summary") or {}
    article_summary = article.get("summary") or {}
    individual_summary = individual.get("summary") or {}
    known_concepts = {
        str(row.get("concept_id"))
        for row in primer.get("concept_rows") or []
        if isinstance(row, dict) and row.get("concept_id")
    }

    rows: list[dict[str, Any]] = []
    for index, row in enumerate(individual.get("section_rows") or []):
        if not isinstance(row, dict):
            continue
        role = str(row.get("section_role") or "")
        row_id = str(row.get("section_id") or f"section_{index}")
        rows.append(
            alignment_row(
                source_family="individual_experiment_report",
                row_index=index,
                row_id=row_id,
                role=role,
                target_surfaces=["individual_experiment_report"],
                concept_ids=ROLE_CONCEPT_MAP.get(role, []),
                known_concepts=known_concepts,
            )
        )
    for index, row in enumerate(article.get("alignment_rows") or []):
        if not isinstance(row, dict):
            continue
        role = str(row.get("scientific_reporting_role") or "")
        row_id = str(row.get("content_area_id") or f"surface_{index}")
        rows.append(
            alignment_row(
                source_family="article_supplement_blueprint_alignment",
                row_index=index,
                row_id=row_id,
                role=role,
                target_surfaces=[str(value) for value in row.get("target_surfaces") or []],
                concept_ids=ROLE_CONCEPT_MAP.get(role, []),
                known_concepts=known_concepts,
            )
        )

    failed_rows = [row for row in rows if row["concept_alignment_status"] != "pass"]
    checks = [
        {
            "check_id": "reader_primer_ready",
            "status": (
                "pass"
                if primer_summary.get("overall_status")
                == "reader_method_primer_citation_map_ready_no_final_prose"
                and int(primer_summary.get("failed_check_count") or 0) == 0
                else "fail"
            ),
            "evidence": {
                "overall_status": primer_summary.get("overall_status"),
                "failed_check_count": primer_summary.get("failed_check_count"),
                "concept_row_count": primer_summary.get("concept_row_count"),
            },
            "blocker": "reader_primer_not_ready",
        },
        {
            "check_id": "blueprints_ready_no_final_prose",
            "status": (
                "pass"
                if article_summary.get("final_manuscript_prose_permission") is False
                and individual_summary.get("final_report_prose_permission") is False
                and int(article_summary.get("failed_check_count") or 0) == 0
                and int(individual_summary.get("failed_check_count") or 0) == 0
                else "fail"
            ),
            "evidence": {
                "article_status": article_summary.get("overall_status"),
                "individual_status": individual_summary.get("overall_status"),
                "article_final_prose": article_summary.get(
                    "final_manuscript_prose_permission"
                ),
                "individual_final_prose": individual_summary.get(
                    "final_report_prose_permission"
                ),
            },
            "blocker": "blueprint_final_prose_or_checks_not_clean",
        },
        {
            "check_id": "section_alignment_rows_complete",
            "status": "pass" if len(rows) == 20 and not failed_rows else "fail",
            "evidence": {
                "alignment_row_count": len(rows),
                "failed_alignment_count": len(failed_rows),
                "failed_alignment_ids": [row["alignment_id"] for row in failed_rows],
            },
            "blocker": "section_primer_alignment_incomplete",
        },
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    unique_concepts = sorted(
        {concept_id for row in rows for concept_id in row["required_concept_ids"]}
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "reader_method_primer_citation_map": rel(root / PRIMER_MAP, root),
            "article_supplement_blueprint_alignment": rel(
                root / ARTICLE_ALIGNMENT, root
            ),
            "individual_experiment_report_blueprint": rel(
                root / INDIVIDUAL_BLUEPRINT, root
            ),
        },
        "summary": {
            "overall_status": (
                "reader_primer_section_alignment_ready_no_final_prose"
                if not failed_checks
                else "reader_primer_section_alignment_blocked"
            ),
            "phase_state": "pre_prose_section_concept_alignment_final_outputs_blocked",
            "alignment_row_count": len(rows),
            "individual_report_alignment_row_count": sum(
                row["source_family"] == "individual_experiment_report" for row in rows
            ),
            "article_supplement_alignment_row_count": sum(
                row["source_family"] == "article_supplement_blueprint_alignment"
                for row in rows
            ),
            "unique_required_concept_count": len(unique_concepts),
            "failed_alignment_row_count": len(failed_rows),
            "final_manuscript_prose_permission": False,
            "method_recommendation_authorized": False,
            "method_champion_authorized": False,
            "positive_claim_promotion_authorized": False,
            "failed_check_count": len(failed_checks),
        },
        "unique_required_concept_ids": unique_concepts,
        "alignment_rows": rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This alignment is a pre-prose writing guardrail only.",
            "A row passing here means required concepts are mapped, not that final prose is authorized.",
            "The alignment must not be used to recommend CQR, CV+, Venn-Abers, or any other method.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Reader Primer Section Alignment",
        "",
        "This pre-prose artifact maps planned article, supplement, and individual-report rows to reader-primer concepts. It does not draft final prose or authorize method recommendations.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Alignment rows: {summary['alignment_row_count']}",
        f"- Individual-report rows: {summary['individual_report_alignment_row_count']}",
        f"- Article/supplement rows: {summary['article_supplement_alignment_row_count']}",
        f"- Unique required concepts: {summary['unique_required_concept_count']}",
        f"- Failed alignment rows: {summary['failed_alignment_row_count']}",
        f"- Final prose authorized: `{summary['final_manuscript_prose_permission']}`",
        f"- Method champion authorized: `{summary['method_champion_authorized']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        "",
        "## Alignment Rows",
        "",
        "| Alignment | Role | Targets | Concepts | Status |",
        "|---|---|---|---|---|",
    ]
    for row in payload["alignment_rows"]:
        lines.append(
            "| `{}` | `{}` | {} | {} | `{}` |".format(
                row["alignment_id"],
                row["scientific_reporting_role"],
                ", ".join(row["target_surfaces"]),
                "<br>".join(row["required_concept_ids"]),
                row["concept_alignment_status"],
            )
        )
    lines.extend(["", "## Claim Boundaries", ""])
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out, root),
                "overall_status": payload["summary"]["overall_status"],
                "alignment_row_count": payload["summary"]["alignment_row_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
