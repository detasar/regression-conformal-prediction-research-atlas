"""Build the reader-facing method primer citation map.

This is a pre-prose artifact for the future paper. It maps the conformal
prediction concepts that a non-specialist reader will need to primary sources
and to explicit claim boundaries. It does not draft final manuscript text or
authorize method recommendations.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_reader_method_primer_citation_map_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/reader_method_primer_citation_map.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
METHOD_LITERATURE_AUDIT = REPORT_DIR / "method_literature_coverage_audit.json"
CLAIM_EVIDENCE_MATRIX = Path(
    "experiments/regression/manuscript/"
    "publication_claim_evidence_verification_matrix.json"
)


CONCEPT_ROWS: tuple[dict[str, Any], ...] = (
    {
        "concept_id": "conformal_prediction_regression",
        "plain_language_role": (
            "A wrapper for building prediction intervals with finite-sample "
            "marginal coverage under exchangeability, without assuming a "
            "correct parametric regression model."
        ),
        "paper_use": (
            "Introduce the general task before any specific method comparison."
        ),
        "primary_source_urls": ["https://arxiv.org/abs/1604.04173"],
        "required_reader_explanation": [
            "prediction interval",
            "exchangeability",
            "finite-sample marginal coverage",
            "why marginal coverage is not the same as conditional or fairness coverage",
        ],
        "blocked_language": [
            "distribution-free conditional coverage guarantee",
            "fairness guarantee from marginal conformal prediction alone",
        ],
    },
    {
        "concept_id": "alpha_and_nominal_coverage",
        "plain_language_role": (
            "`alpha` is the target miscoverage rate; `1 - alpha` is the "
            "nominal coverage level used to calibrate prediction intervals."
        ),
        "paper_use": (
            "Define coverage targets before reporting coverage error, width, "
            "or interval score."
        ),
        "primary_source_urls": [
            "https://arxiv.org/abs/1604.04173",
            "https://arxiv.org/abs/1905.03222",
        ],
        "required_reader_explanation": [
            "miscoverage",
            "nominal coverage",
            "empirical coverage",
            "coverage error",
        ],
        "blocked_language": [
            "1-alpha proves every subgroup is covered",
            "nominal coverage is the observed coverage",
        ],
    },
    {
        "concept_id": "split_conformal_regression",
        "plain_language_role": (
            "A data-splitting method that fits a model on training data and "
            "uses calibration residuals to choose an interval radius."
        ),
        "paper_use": "Use as the baseline interval-construction explanation.",
        "primary_source_urls": ["https://arxiv.org/abs/1604.04173"],
        "required_reader_explanation": [
            "train/calibration split",
            "absolute residual conformity score",
            "calibration quantile",
        ],
        "blocked_language": [
            "best method",
            "conditional validity without additional assumptions",
        ],
    },
    {
        "concept_id": "conformalized_quantile_regression_cqr",
        "plain_language_role": (
            "CQR combines quantile-regression lower/upper predictions with a "
            "conformal calibration step so intervals can adapt to "
            "heteroscedasticity while retaining marginal coverage."
        ),
        "paper_use": (
            "Explain why CQR is a practical diagnostic candidate in these "
            "experiments without calling it a general recommendation."
        ),
        "primary_source_urls": ["https://arxiv.org/abs/1905.03222"],
        "required_reader_explanation": [
            "lower and upper quantile models",
            "quantile crossing risk",
            "conformal correction",
            "heteroscedastic interval width",
        ],
        "blocked_language": [
            "CQR is the universally best regression CP method",
            "CQR is finally selected by this study",
        ],
    },
    {
        "concept_id": "jackknife_plus_and_cv_plus",
        "plain_language_role": (
            "Plus-family methods use leave-one-out or cross-validation style "
            "out-of-fold predictions to account for fitted-model variability "
            "when building prediction intervals."
        ),
        "paper_use": (
            "Define CV+ and jackknife+ before comparing them with split and CQR rows."
        ),
        "primary_source_urls": [
            "https://arxiv.org/abs/1905.02928",
            "https://arxiv.org/abs/2002.09025",
        ],
        "required_reader_explanation": [
            "out-of-fold prediction",
            "fold-excluded model",
            "plus envelope",
            "minmax variant",
        ],
        "blocked_language": [
            "CV+ is free of computational or duplicate-cluster caveats",
            "CV+ is selected as a final method",
        ],
    },
    {
        "concept_id": "mondrian_and_group_calibration",
        "plain_language_role": (
            "Mondrian/group calibration calibrates scores within groups when "
            "enough calibration examples exist, making group diagnostics "
            "explicit but not automatically proving population fairness."
        ),
        "paper_use": (
            "Use when introducing diagnostic group coverage and group gap tables."
        ),
        "primary_source_urls": ["https://arxiv.org/abs/1604.04173"],
        "required_reader_explanation": [
            "group-specific calibration",
            "minimum calibration group size",
            "fallback behavior",
            "diagnostic group coverage gap",
        ],
        "blocked_language": [
            "fairness is solved",
            "population fairness inference is proven",
        ],
    },
    {
        "concept_id": "normalized_and_locally_adaptive_split",
        "plain_language_role": (
            "Normalized split conformal divides residuals by a fitted scale "
            "estimate so interval widths can vary with estimated local noise."
        ),
        "paper_use": (
            "Explain scale-model diagnostics and endpoint caveats before using "
            "normalized intervals in result tables."
        ),
        "primary_source_urls": ["https://arxiv.org/abs/1604.04173"],
        "required_reader_explanation": [
            "residual scale model",
            "local adaptivity",
            "endpoint extrapolation caveat",
        ],
        "blocked_language": [
            "bounded support is guaranteed",
            "scale normalization proves conditional validity",
        ],
    },
    {
        "concept_id": "weighted_conformal_covariate_shift",
        "plain_language_role": (
            "Weighted conformal prediction changes calibration weights when "
            "the test covariate distribution differs from the calibration "
            "distribution and a valid likelihood-ratio model is available."
        ),
        "paper_use": (
            "Use only as a covariate-shift sensitivity explanation unless "
            "likelihood ratios are externally validated."
        ),
        "primary_source_urls": ["https://arxiv.org/abs/1904.06019"],
        "required_reader_explanation": [
            "covariate shift",
            "likelihood ratio",
            "infinity atom",
            "estimated-ratio diagnostic caveat",
        ],
        "blocked_language": [
            "distribution-shift validity is proven by estimated weights",
            "weighted rows are ordinary marginal coverage evidence",
        ],
    },
    {
        "concept_id": "tail_specific_intervals",
        "plain_language_role": (
            "Tail-specific intervals allocate miscoverage separately to lower "
            "and upper tails to diagnose asymmetric miss behavior."
        ),
        "paper_use": (
            "Use for skewed-target diagnostics and lower/upper miss-rate discussion."
        ),
        "primary_source_urls": [
            "https://arxiv.org/abs/2606.18199",
            "https://arxiv.org/abs/2604.25202",
        ],
        "required_reader_explanation": [
            "lower-tail miss",
            "upper-tail miss",
            "tail allocation",
            "shortest-interval diagnostic caveat",
        ],
        "blocked_language": [
            "tail allocation was optimized without a separate tuning split",
            "tail-specific rows replace CQR or Venn-Abers diagnostics",
        ],
    },
    {
        "concept_id": "venn_abers_predictive_distributions",
        "plain_language_role": (
            "Venn-Abers regression-related methods target calibrated predictive "
            "distributions or quantile-calibration objects; converting them to "
            "ordinary intervals is an additional design choice."
        ),
        "paper_use": (
            "Explain why this study reports Venn-Abers evidence as negative or "
            "failure-mode evidence rather than as validated interval evidence."
        ),
        "primary_source_urls": [
            "https://proceedings.mlr.press/v91/nouretdinov18a.html",
            "https://proceedings.mlr.press/v230/nouretdinov24a.html",
            "https://proceedings.mlr.press/v267/van-der-laan25a.html",
            "https://arxiv.org/html/2605.06646v1",
        ],
        "required_reader_explanation": [
            "predictive distribution",
            "Venn-Abers calibration",
            "quantile bridge",
            "why current rows are diagnostic/negative evidence",
        ],
        "blocked_language": [
            "validated Venn-Abers regression interval method",
            "Venn-Abers recommendation",
        ],
    },
    {
        "concept_id": "distributional_and_full_conformal_references",
        "plain_language_role": (
            "Distributional, full conformal, rank-one-out, and conformal "
            "predictive-system entries are literature/reference families, not "
            "ordinary broad-sweep interval runner evidence in this repository."
        ),
        "paper_use": (
            "Use in related work and limitations to explain scoped-out method families."
        ),
        "primary_source_urls": [
            "https://arxiv.org/abs/1604.04173",
            "https://arxiv.org/abs/1909.07889",
            "https://arxiv.org/abs/1911.00941",
            "https://proceedings.mlr.press/v60/vovk17a.html",
        ],
        "required_reader_explanation": [
            "full conformal computational cost",
            "distributional conformal prediction",
            "conformal predictive system",
            "reference primitive versus completed experiment",
        ],
        "blocked_language": [
            "all literature families were run as broad experiments",
            "reference primitives are empirical evidence rows",
        ],
    },
    {
        "concept_id": "result_metrics_and_claim_boundaries",
        "plain_language_role": (
            "Coverage, width, interval score, group coverage gap, and endpoint "
            "state are different empirical diagnostics; no single metric "
            "authorizes a final method claim."
        ),
        "paper_use": (
            "Introduce result tables and explain why observed frontiers are not "
            "automatic recommendations."
        ),
        "primary_source_urls": [
            "https://arxiv.org/abs/1604.04173",
            "https://arxiv.org/abs/1905.03222",
        ],
        "required_reader_explanation": [
            "coverage",
            "mean width",
            "interval score",
            "group gap",
            "endpoint audit state",
        ],
        "blocked_language": [
            "best method from one metric",
            "final winner",
        ],
    },
)

EXPLANATION_OUTLINES: dict[str, dict[str, Any]] = {
    "conformal_prediction_regression": {
        "reader_explanation_outline": [
            "Start from the ordinary regression problem and replace a single point prediction with an interval intended to contain the unseen response.",
            "Define exchangeability as the condition that lets calibration residuals stand in for future residuals.",
            "State that the usual finite-sample guarantee is marginal over future draws, not a guarantee for every subgroup or every covariate value.",
        ],
        "citation_use_note": (
            "Use Lei et al. to justify split/full conformal regression terminology, "
            "finite-sample marginal coverage, and the warning against conditional "
            "or fairness over-claims."
        ),
    },
    "alpha_and_nominal_coverage": {
        "reader_explanation_outline": [
            "Define alpha as the target long-run miscoverage rate and 1-alpha as the nominal coverage target.",
            "Separate nominal coverage, which is chosen before calibration, from empirical coverage, which is measured after the experiment.",
            "Use coverage error only as a diagnostic gap between empirical behavior and the nominal target.",
        ],
        "citation_use_note": (
            "Use Lei et al. for regression conformal calibration and Romano et al. "
            "for the same coverage target inside CQR."
        ),
    },
    "split_conformal_regression": {
        "reader_explanation_outline": [
            "Describe the train/calibration split before introducing any model family.",
            "Define the absolute residual conformity score and the calibration quantile used as an interval radius.",
            "Explain the efficiency tradeoff: simple and model-agnostic, but intervals can be wide when residual scale varies across covariates.",
        ],
        "citation_use_note": (
            "Use Lei et al. as the primary source for split conformal regression "
            "and residual-score calibration."
        ),
    },
    "conformalized_quantile_regression_cqr": {
        "reader_explanation_outline": [
            "Introduce two quantile models that estimate lower and upper conditional response quantiles.",
            "Define the CQR calibration score as the amount by which a calibration response falls outside the predicted quantile band.",
            "Explain that conformal calibration expands the quantile band to recover marginal coverage while preserving heteroscedastic width information when the quantile models are useful.",
        ],
        "citation_use_note": (
            "Use Romano et al. for the CQR construction and for describing "
            "heteroscedastic interval adaptation without turning the empirical "
            "diagnostic into a universal recommendation."
        ),
    },
    "jackknife_plus_and_cv_plus": {
        "reader_explanation_outline": [
            "Explain out-of-fold prediction: each calibration-like residual is computed from a model that did not train on that row.",
            "Describe jackknife+ as the leave-one-out version and CV+ as the K-fold approximation.",
            "Introduce the plus envelope and minmax variant as interval aggregation rules, then state the computational and duplicate-cluster caveats.",
        ],
        "citation_use_note": (
            "Use Barber et al. for jackknife+ and the CV+/minmax literature row "
            "for cross-validation plus-family terminology."
        ),
    },
    "mondrian_and_group_calibration": {
        "reader_explanation_outline": [
            "Define group-specific calibration as estimating a separate calibration quantile inside each eligible group.",
            "State the minimum calibration-size issue before interpreting group coverage diagnostics.",
            "Separate diagnostic subgroup coverage tables from a population-level fairness guarantee.",
        ],
        "citation_use_note": (
            "Use Lei et al. for the Mondrian/group-calibration reference point "
            "and pair it with this study's fairness claim boundaries."
        ),
    },
    "normalized_and_locally_adaptive_split": {
        "reader_explanation_outline": [
            "Introduce a residual scale model as an estimate of local noise level.",
            "Explain normalized scores as residuals divided by the estimated scale and intervals as model predictions expanded by local scale.",
            "Flag endpoint and extrapolation caveats when the scale model or target support is unreliable.",
        ],
        "citation_use_note": (
            "Use Lei et al. for normalized conformal regression and keep endpoint "
            "claims tied to the repository endpoint audits."
        ),
    },
    "weighted_conformal_covariate_shift": {
        "reader_explanation_outline": [
            "Define covariate shift as a change in the distribution of covariates while the conditional response mechanism is treated as stable.",
            "Explain that valid weighting requires likelihood-ratio information between test and calibration covariate distributions.",
            "Mark estimated-ratio runs as sensitivity diagnostics unless the ratio model is externally validated.",
        ],
        "citation_use_note": (
            "Use Tibshirani et al. for weighted conformal prediction under "
            "covariate shift and keep estimated-ratio results diagnostic."
        ),
    },
    "tail_specific_intervals": {
        "reader_explanation_outline": [
            "Define lower-tail and upper-tail misses separately before discussing total coverage.",
            "Explain tail allocation as assigning different error budgets to the two sides of an interval.",
            "Treat shortest or asymmetric interval rows as diagnostics unless tail allocation was tuned and validated with a separate protocol.",
        ],
        "citation_use_note": (
            "Use the tail-specific interval sources for terminology while keeping "
            "this study's rows inside the diagnostic claim boundary."
        ),
    },
    "venn_abers_predictive_distributions": {
        "reader_explanation_outline": [
            "Define a predictive distribution as a calibrated distribution over possible response values rather than a single interval.",
            "Explain that Venn-Abers style calibration can target predictive distributions or quantile objects.",
            "State that converting those objects into ordinary regression intervals is an additional bridge, so undercoverage rows are reported as negative or failure-mode evidence.",
        ],
        "citation_use_note": (
            "Use the Venn-Abers predictive-distribution sources for method context, "
            "not to imply a validated regression-interval recommendation."
        ),
    },
    "distributional_and_full_conformal_references": {
        "reader_explanation_outline": [
            "Distinguish reference method families from experiment rows actually executed in this repository.",
            "Explain full conformal and rank-one-out ideas as computationally heavier reference points.",
            "Use distributional conformal and conformal predictive systems as related-work context, not as completed broad-sweep evidence.",
        ],
        "citation_use_note": (
            "Use these sources in related work and limitations to document scoped-out "
            "families without claiming they were broadly run here."
        ),
    },
    "result_metrics_and_claim_boundaries": {
        "reader_explanation_outline": [
            "Define coverage, mean width, interval score, group coverage gap, and endpoint state before presenting result tables.",
            "Explain that coverage and width form a tradeoff, while interval score combines miss penalties with width.",
            "State that no single metric row authorizes a final winner, especially under multiplicity, duplicate-cluster, fairness, and endpoint caveats.",
        ],
        "citation_use_note": (
            "Use the conformal regression and CQR sources for metric context, then "
            "bind empirical claims to the repository claim-evidence matrix."
        ),
    },
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


def build_payload(root: Path) -> dict[str, Any]:
    literature = read_json(root / METHOD_LITERATURE_AUDIT)
    claim_matrix = read_json(root / CLAIM_EVIDENCE_MATRIX)
    literature_summary = literature.get("summary") or {}
    claim_matrix_summary = claim_matrix.get("summary") or {}
    concept_rows = []
    for row in CONCEPT_ROWS:
        concept_row = dict(row)
        concept_row.update(EXPLANATION_OUTLINES.get(concept_row["concept_id"], {}))
        concept_rows.append(concept_row)
    primary_urls = sorted(
        {
            url
            for row in concept_rows
            for url in row.get("primary_source_urls", [])
        }
    )
    incomplete_rows = [
        row["concept_id"]
        for row in concept_rows
        if not row.get("plain_language_role")
        or not row.get("paper_use")
        or not row.get("primary_source_urls")
        or not row.get("required_reader_explanation")
        or not row.get("reader_explanation_outline")
        or not row.get("citation_use_note")
        or not row.get("blocked_language")
    ]
    checks = [
        {
            "check_id": "method_literature_audit_clean",
            "status": (
                "pass"
                if literature_summary.get("overall_status")
                == "method_literature_coverage_pass"
                and int(literature_summary.get("hard_failed_requirement_count") or 0)
                == 0
                and int(literature_summary.get("tracked_gap_count") or 0) == 0
                else "fail"
            ),
            "evidence": {
                "overall_status": literature_summary.get("overall_status"),
                "hard_failed_requirement_count": literature_summary.get(
                    "hard_failed_requirement_count"
                ),
                "tracked_gap_count": literature_summary.get("tracked_gap_count"),
            },
            "blocker": "method_literature_coverage_not_clean",
        },
        {
            "check_id": "claim_evidence_matrix_keeps_final_outputs_blocked",
            "status": (
                "pass"
                if claim_matrix_summary.get("overall_status")
                == "publication_claim_evidence_verification_ready_no_final_prose"
                and claim_matrix_summary.get("final_manuscript_prose_permission")
                is False
                and claim_matrix_summary.get("method_champion_authorized") is False
                and claim_matrix_summary.get("positive_claim_promotion_authorized")
                is False
                else "fail"
            ),
            "evidence": {
                "overall_status": claim_matrix_summary.get("overall_status"),
                "final_manuscript_prose_permission": claim_matrix_summary.get(
                    "final_manuscript_prose_permission"
                ),
                "method_champion_authorized": claim_matrix_summary.get(
                    "method_champion_authorized"
                ),
                "positive_claim_promotion_authorized": claim_matrix_summary.get(
                    "positive_claim_promotion_authorized"
                ),
            },
            "blocker": "claim_evidence_matrix_not_pre_prose_clean",
        },
        {
            "check_id": "reader_concept_rows_complete",
            "status": "pass" if not incomplete_rows and len(concept_rows) >= 10 else "fail",
            "evidence": {
                "concept_row_count": len(concept_rows),
                "incomplete_rows": incomplete_rows,
            },
            "blocker": "reader_concept_rows_incomplete",
        },
        {
            "check_id": "primary_sources_present",
            "status": "pass" if len(primary_urls) >= 10 else "fail",
            "evidence": {
                "primary_source_url_count": len(primary_urls),
                "primary_source_urls": primary_urls,
            },
            "blocker": "insufficient_primary_source_coverage",
        },
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "method_literature_coverage_audit": rel(
                root / METHOD_LITERATURE_AUDIT, root
            ),
            "publication_claim_evidence_verification_matrix": rel(
                root / CLAIM_EVIDENCE_MATRIX, root
            ),
        },
        "summary": {
            "overall_status": (
                "reader_method_primer_citation_map_ready_no_final_prose"
                if not failed_checks
                else "reader_method_primer_citation_map_blocked"
            ),
            "phase_state": "pre_prose_reader_concept_citation_mapping_final_outputs_blocked",
            "concept_row_count": len(concept_rows),
            "reader_explanation_outline_count": sum(
                1 for row in concept_rows if row.get("reader_explanation_outline")
            ),
            "primary_source_url_count": len(primary_urls),
            "literature_requirement_count": literature_summary.get(
                "literature_requirement_count"
            ),
            "literature_tracked_gap_count": literature_summary.get("tracked_gap_count"),
            "final_manuscript_prose_permission": False,
            "method_recommendation_authorized": False,
            "method_champion_authorized": False,
            "method_advocacy_authorized": False,
            "positive_claim_promotion_authorized": False,
            "result_reporting_policy": (
                "analysis_only_report_observed_behavior_no_method_advocacy"
            ),
            "failed_check_count": len(failed_checks),
        },
        "primary_source_urls": primary_urls,
        "concept_rows": concept_rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This map is pre-prose citation scaffolding, not final manuscript text.",
            "Every future method explanation must define the concept for non-specialist readers before interpreting results.",
            "The map does not authorize CQR, CV+, Venn-Abers, or any other method as a recommendation or final winner.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Reader Method Primer Citation Map",
        "",
        "This pre-prose artifact maps reader-facing conformal prediction concepts to primary sources and claim boundaries. It does not draft final manuscript text or authorize a method recommendation.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Phase state: `{summary['phase_state']}`",
        f"- Concept rows: {summary['concept_row_count']}",
        f"- Primary source URLs: {summary['primary_source_url_count']}",
        f"- Literature tracked gaps: {summary['literature_tracked_gap_count']}",
        f"- Final prose authorized: `{summary['final_manuscript_prose_permission']}`",
        f"- Method champion authorized: `{summary['method_champion_authorized']}`",
        f"- Positive-claim promotion authorized: `{summary['positive_claim_promotion_authorized']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        "",
        "## Concept Rows",
        "",
        "| Concept | Reader role | Sources | Blocked language |",
        "|---|---|---|---|",
    ]
    for row in payload["concept_rows"]:
        sources = "<br>".join(row["primary_source_urls"])
        blocked = "<br>".join(row["blocked_language"])
        lines.append(
            "| `{}` | {} | {} | {} |".format(
                row["concept_id"],
                row["plain_language_role"],
                sources,
                blocked,
            )
        )
    lines.extend(
        [
            "",
            "## Reader Explanation Outlines",
            "",
            "| Concept | Explanation outline | Citation use note |",
            "|---|---|---|",
        ]
    )
    for row in payload["concept_rows"]:
        outline = "<br>".join(row["reader_explanation_outline"])
        lines.append(
            "| `{}` | {} | {} |".format(
                row["concept_id"],
                outline,
                row["citation_use_note"],
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
                "concept_row_count": payload["summary"]["concept_row_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
