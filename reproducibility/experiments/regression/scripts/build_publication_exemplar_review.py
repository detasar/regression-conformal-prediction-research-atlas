"""Build a source-backed review of comparable publication packages.

The review records external paper, repository, documentation, and site examples
that inform the final Research Document, supplementary material, README, and
private site design. It is not a literature-result claim, not a method
recommendation, and not a public-release authorization.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_publication_exemplar_review_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/publication_exemplar_review.md")
DEFAULT_JSON_OUT = Path("experiments/regression/manuscript/publication_exemplar_review.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output Markdown path.")
    parser.add_argument(
        "--json-out", default=str(DEFAULT_JSON_OUT), help="Output JSON path."
    )
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def source_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "cqr_neurips_paper_and_supplement",
            "source_type": "paper_with_supplement",
            "title": "Conformalized Quantile Regression",
            "primary_url": (
                "https://papers.nips.cc/paper_files/paper/2019/hash/"
                "5103c3584b063c431bd1268e9b5e76fb-Abstract.html"
            ),
            "supporting_urls": [
                "https://papers.neurips.cc/paper/8613-conformalized-quantile-regression.pdf",
                "https://arxiv.org/abs/1905.03222",
            ],
            "inspected_evidence": (
                "Proceedings page exposes the paper, reviews, and supplemental "
                "material; the paper combines a compact method statement, "
                "algorithm box, theorem, experiment table, and supplemental "
                "implementation details."
            ),
            "design_lesson": (
                "Keep the main article compact and readable, while moving broad "
                "implementation details, per-dataset tables, and robustness "
                "material to the supplement."
            ),
        },
        {
            "source_id": "cqr_github_and_site",
            "source_type": "repo_plus_website",
            "title": "Reliable Predictive Inference CQR repository and site",
            "primary_url": "https://github.com/yromano/cqr",
            "supporting_urls": ["https://sites.google.com/view/cqr"],
            "inspected_evidence": (
                "The repository README gives a plain problem motivation, method "
                "overview, notebook pointers, and reproducible experiment "
                "directory; the companion site offers navigation to synthetic, "
                "real-data, and equalized-coverage examples."
            ),
            "design_lesson": (
                "Give reviewers a clear route from narrative to examples, code, "
                "reproducibility material, and site pages."
            ),
        },
        {
            "source_id": "mapie_docs_and_repo",
            "source_type": "library_docs_and_repo",
            "title": "MAPIE documentation and GitHub repository",
            "primary_url": "https://contrib.scikit-learn.org/MAPIE/",
            "supporting_urls": ["https://github.com/scikit-learn-contrib/MAPIE"],
            "inspected_evidence": (
                "The docs and README expose installation, quickstart examples, "
                "regression/classification entry points, references, citation "
                "metadata, contribution guidance, and release notes."
            ),
            "design_lesson": (
                "The final README should prioritize status, reader entry points, "
                "review path, citation metadata, source provenance, and explicit "
                "boundaries before deep implementation detail."
            ),
        },
        {
            "source_id": "cqr_comparison_repo",
            "source_type": "regression_reproducibility_repo",
            "title": "A comparison of some conformal quantile regression methods",
            "primary_url": "https://github.com/msesia/cqr-comparison",
            "supporting_urls": ["https://arxiv.org/abs/1909.05433"],
            "inspected_evidence": (
                "The repository separates experiments, datasets, third-party "
                "code, prerequisites, and publicly available versus usage-bound "
                "data sources for a regression conformal quantile comparison."
            ),
            "design_lesson": (
                "The supplementary document and README should make dataset "
                "provenance, reproduction entry points, and data-use boundaries "
                "explicit rather than burying them in prose."
            ),
        },
        {
            "source_id": "ryantibs_conformal_regression_repo",
            "source_type": "regression_reproducibility_repo",
            "title": "Conformal Inference R Project",
            "primary_url": "https://github.com/ryantibs/conformal",
            "supporting_urls": [],
            "inspected_evidence": (
                "The repository separates the installable conformalInference "
                "package, documentation PDF, paper-specific reproduction folders, "
                "tests, and relevant-work list."
            ),
            "design_lesson": (
                "Separate reusable code, reproduction scripts, paper outputs, "
                "tests, and related-work metadata in the sterile repository."
            ),
        },
        {
            "source_id": "angelopoulos_bates_tutorial_repo",
            "source_type": "tutorial_repo_with_reproducibility_path",
            "title": "Conformal Prediction tutorial repository",
            "primary_url": "https://github.com/aangelopoulos/conformal-prediction",
            "supporting_urls": ["https://arxiv.org/abs/2107.07511"],
            "inspected_evidence": (
                "The repository organizes notebooks, generation scripts, an "
                "environment file, paper citation, and examples that can run from "
                "precomputed model outputs and data subsamples."
            ),
            "design_lesson": (
                "A review package should make expected reading and reproduction "
                "paths explicit without requiring raw private data in the release."
            ),
        },
        {
            "source_id": "neurips_paper_checklist_guidelines",
            "source_type": "research_transparency_guideline",
            "title": "NeurIPS Paper Checklist Guidelines",
            "primary_url": "https://neurips.cc/public/guides/PaperChecklist",
            "supporting_urls": [
                "https://neurips.cc/public/guides/CodeSubmissionPolicy"
            ],
            "inspected_evidence": (
                "The checklist asks authors to align claims with contribution "
                "scope, state limitations, document assumptions, provide "
                "reproducibility paths, disclose experimental details, report "
                "uncertainty, record compute, and cite licenses for assets."
            ),
            "design_lesson": (
                "The Research Document should keep a visible checklist-like "
                "spine for claims, limitations, assumptions, reproducibility, "
                "compute, licenses, and release boundaries."
            ),
        },
        {
            "source_id": "paperswithcode_research_code_release_guidance",
            "source_type": "research_code_release_guideline",
            "title": "Papers with Code research-code release guidance",
            "primary_url": "https://github.com/paperswithcode/releasing-research-code",
            "supporting_urls": [],
            "inspected_evidence": (
                "The guidance highlights dependency specification, training "
                "code, evaluation code, reusable artifacts when appropriate, "
                "and README result tables with precise commands."
            ),
            "design_lesson": (
                "The sterile repository README should foreground environment, "
                "evaluation and reproduction commands, expected outputs, and "
                "the exact files needed to verify the reported results."
            ),
        },
        {
            "source_id": "venn_abers_pmlr_2024",
            "source_type": "venn_abers_regression_paper",
            "title": "Inductive Venn-Abers Predictive Distributions",
            "primary_url": "https://proceedings.mlr.press/v230/nouretdinov24a.html",
            "supporting_urls": [],
            "inspected_evidence": (
                "The PMLR abstract frames the regression extension as predictive "
                "distributions and evaluates accuracy and informativeness metrics."
            ),
            "design_lesson": (
                "Venn-Abers regression language should distinguish predictive "
                "distribution work from the interval bridge evaluated in this "
                "project."
            ),
        },
        {
            "source_id": "generalized_venn_abers_pmlr_2025",
            "source_type": "generalized_calibration_paper",
            "title": "Generalized Venn and Venn-Abers Calibration",
            "primary_url": "https://proceedings.mlr.press/v267/van-der-laan25a.html",
            "supporting_urls": [],
            "inspected_evidence": (
                "The PMLR abstract presents a generalized calibration framework "
                "for generic loss functions and notes quantile-loss links to "
                "conformal prediction intervals."
            ),
            "design_lesson": (
                "Negative evidence for the current bridge must be reported as "
                "bridge-specific evidence, not as a claim about all Venn-Abers "
                "or generalized calibration research."
            ),
        },
    ]


def design_decision_rows() -> list[dict[str, Any]]:
    return [
        {
            "decision_id": "minimal_main_broad_supplement",
            "decision": "Use a minimal main article and a broad supplementary document.",
            "source_ids": [
                "cqr_neurips_paper_and_supplement",
                "cqr_comparison_repo",
            ],
            "project_application": (
                "The main article keeps the claim-evidence map and headline "
                "results; the supplement carries broad method, dataset, audit, "
                "robustness, and negative-evidence material."
            ),
        },
        {
            "decision_id": "readme_review_path_first",
            "decision": "Make the README a review router, not a dense methods dump.",
            "source_ids": ["mapie_docs_and_repo", "cqr_github_and_site"],
            "project_application": (
                "The README starts with status, plain-language summary, review "
                "path, evidence snapshot, repository map, KG entry, and citation "
                "surface."
            ),
        },
        {
            "decision_id": "site_as_review_portal",
            "decision": "Use the site as a private review portal with explicit lanes.",
            "source_ids": ["cqr_github_and_site", "mapie_docs_and_repo"],
            "project_application": (
                "The private site should expose the handoff, Research Document, "
                "rendered article/supplement, KG browser, and governance checks."
            ),
        },
        {
            "decision_id": "source_backed_claim_boundaries",
            "decision": "Pair every reader-facing claim with evidence and a boundary.",
            "source_ids": [
                "cqr_neurips_paper_and_supplement",
                "neurips_paper_checklist_guidelines",
                "venn_abers_pmlr_2024",
                "generalized_venn_abers_pmlr_2025",
            ],
            "project_application": (
                "The article, Research Document, and README retain neutral "
                "language: observed practical candidates are not recommendations, "
                "and bridge-specific failures are not literature-wide rejections."
            ),
        },
        {
            "decision_id": "checklist_like_research_document_spine",
            "decision": "Give the Research Document a checklist-like transparency spine.",
            "source_ids": [
                "neurips_paper_checklist_guidelines",
                "paperswithcode_research_code_release_guidance",
            ],
            "project_application": (
                "The Research Document should visibly cover claims, limitations, "
                "assumptions, reproducibility route, compute, license and source "
                "provenance, and closed release gates."
            ),
        },
        {
            "decision_id": "reproducibility_without_raw_data",
            "decision": "Expose reproduction structure while excluding raw data and secrets.",
            "source_ids": [
                "angelopoulos_bates_tutorial_repo",
                "ryantibs_conformal_regression_repo",
                "cqr_comparison_repo",
                "paperswithcode_research_code_release_guidance",
            ],
            "project_application": (
                "The private package copies source, configs, tests, reports, and "
                "metadata, while excluding raw data, caches, local databases, and "
                "secret-like material."
            ),
        },
        {
            "decision_id": "kg_as_browsable_artifact",
            "decision": "Treat the knowledge graph as a browsable supplementary/web artifact.",
            "source_ids": ["cqr_github_and_site", "mapie_docs_and_repo"],
            "project_application": (
                "The KG browser becomes part of the review path when its quality "
                "and provenance checks pass; it remains private until release is "
                "explicitly authorized."
            ),
        },
        {
            "decision_id": "readme_results_commands_and_expected_outputs",
            "decision": "Make result verification commands and expected outputs explicit.",
            "source_ids": [
                "paperswithcode_research_code_release_guidance",
                "mapie_docs_and_repo",
            ],
            "project_application": (
                "The sterile README should connect headline results to exact "
                "commands, manifest paths, and expected pass/fail statuses rather "
                "than relying on prose-only reproducibility claims."
            ),
        },
        {
            "decision_id": "venn_abers_bridge_language",
            "decision": "Keep Venn-Abers wording bridge-specific and conservative.",
            "source_ids": ["venn_abers_pmlr_2024", "generalized_venn_abers_pmlr_2025"],
            "project_application": (
                "The manuscript reports that the evaluated bridge did not emerge "
                "as the expected strong regression solution in these experiments."
            ),
        },
        {
            "decision_id": "private_to_public_release_gate",
            "decision": "Keep private review and public release as separate states.",
            "source_ids": ["mapie_docs_and_repo", "angelopoulos_bates_tutorial_repo"],
            "project_application": (
                "The sterile package can be reviewed privately; public release, "
                "public site deployment, and citable status stay blocked until "
                "explicit user approval."
            ),
        },
    ]


def build_payload(root: Path) -> dict[str, Any]:
    rows = source_rows()
    decisions = design_decision_rows()
    source_ids = {row["source_id"] for row in rows}
    missing_decision_sources = [
        {
            "decision_id": row["decision_id"],
            "missing_source_ids": [
                source_id for source_id in row["source_ids"] if source_id not in source_ids
            ],
        }
        for row in decisions
        if any(source_id not in source_ids for source_id in row["source_ids"])
    ]
    malformed_source_urls = [
        row["source_id"]
        for row in rows
        if not str(row["primary_url"]).startswith("https://")
    ]
    checks = [
        {
            "check_id": "external_sources_reviewed",
            "status": "pass" if len(rows) >= 7 else "fail",
            "evidence": {"source_row_count": len(rows)},
        },
        {
            "check_id": "design_decisions_source_traceable",
            "status": "pass" if not missing_decision_sources else "fail",
            "evidence": {"missing_decision_sources": missing_decision_sources},
        },
        {
            "check_id": "source_urls_are_https",
            "status": "pass" if not malformed_source_urls else "fail",
            "evidence": {"malformed_source_urls": malformed_source_urls},
        },
        {
            "check_id": "review_remains_design_guidance_only",
            "status": "pass",
            "evidence": {
                "new_experiments_authorized": False,
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "public_release_authorized": False,
            },
        },
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    supporting_url_count = sum(len(row["supporting_urls"]) for row in rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": (
                "publication_exemplar_review_ready"
                if not failed_checks
                else "publication_exemplar_review_blocked"
            ),
            "external_source_row_count": len(rows),
            "external_supporting_url_count": supporting_url_count,
            "design_decision_row_count": len(decisions),
            "new_experiments_authorized": False,
            "method_recommendation_authorized": False,
            "method_champion_authorized": False,
            "positive_claim_promotion_authorized": False,
            "public_release_authorized": False,
            "failed_check_count": len(failed_checks),
        },
        "source_rows": rows,
        "design_decision_rows": decisions,
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This artifact reviews publication-package design examples only.",
            "It does not add experiments or empirical method claims.",
            "It does not recommend CQR, CV+, Venn-Abers, or any conformal method.",
            "It keeps private review separate from public release and citable status.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# Publication Exemplar Review",
        "",
        (
            "> Source-backed design review for the Research Document, supplement, "
            "README, private site, and future sterile repository. This is not a "
            "method recommendation and not a public release authorization."
        ),
        "",
        "## Summary",
        "",
        f"- Overall status: `{s['overall_status']}`",
        f"- External source rows: {s['external_source_row_count']}",
        f"- Supporting URLs: {s['external_supporting_url_count']}",
        f"- Design-decision rows: {s['design_decision_row_count']}",
        f"- Method recommendation authorized: `{s['method_recommendation_authorized']}`",
        f"- Public release authorized: `{s['public_release_authorized']}`",
        "",
        "## External Sources Inspected",
        "",
        "| Source | Type | Inspected evidence | Design lesson |",
        "|---|---|---|---|",
    ]
    for row in payload["source_rows"]:
        lines.append(
            "| "
            f"{row['title']} | "
            f"{row['source_type']} | "
            f"{row['inspected_evidence']} | "
            f"{row['design_lesson']} |"
        )
    lines.extend(
        [
            "",
            "## Design Lessons For This Project",
            "",
            "| Decision | Source basis | Project application |",
            "|---|---|---|",
        ]
    )
    source_titles = {row["source_id"]: row["title"] for row in payload["source_rows"]}
    for row in payload["design_decision_rows"]:
        source_basis = ", ".join(source_titles[source_id] for source_id in row["source_ids"])
        lines.append(
            "| "
            f"{row['decision']} | "
            f"{source_basis} | "
            f"{row['project_application']} |"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(["", "## Source URLs", ""])
    for row in payload["source_rows"]:
        urls = [row["primary_url"], *row["supporting_urls"]]
        lines.append(f"- `{row['source_id']}`: " + "; ".join(urls))
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    json_out = root / args.json_out
    payload = build_payload(root)
    atomic_write_json(json_out, payload)
    atomic_write_text(out, render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out, root),
                "json_out": rel(json_out, root),
                "overall_status": payload["summary"]["overall_status"],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
