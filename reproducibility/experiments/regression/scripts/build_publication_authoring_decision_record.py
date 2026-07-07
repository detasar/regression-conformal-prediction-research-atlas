"""Record user-authorized Research Document authoring decisions.

This artifact opens private Research Document authoring after the empirical
phase while keeping public release, method recommendation, positive claims, and
public KG/site publication closed until a later release gate.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_publication_authoring_decision_record_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/publication_authoring_decision_record.json"
)

GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
CLAIM_MATRIX = Path(
    "experiments/regression/manuscript/publication_claim_evidence_verification_matrix.json"
)
PRIVATE_PACKAGE = Path(
    "experiments/regression/manuscript/private_sterile_publication_package_manifest.json"
)
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")

INSPIRATION_SOURCES = (
    {
        "source_id": "papers_with_code_ml_code_completeness",
        "url": "https://github.com/paperswithcode/releasing-research-code",
        "design_implication": (
            "README must expose dependencies, evaluation/reproduction commands, "
            "and result tables with precise provenance."
        ),
    },
    {
        "source_id": "cornell_research_code_readme",
        "url": (
            "https://data.research.cornell.edu/data-management/sharing/"
            "writing-readmes-for-research-code-software/"
        ),
        "design_implication": (
            "README should be self-contained, metadata-rich, and organized for "
            "validation and reuse."
        ),
    },
    {
        "source_id": "jupyter_book_computational_narrative",
        "url": "https://jupyterbook.org/",
        "design_implication": (
            "Website should behave as a reusable, reproducible, cross-referenced "
            "computational narrative."
        ),
    },
    {
        "source_id": "distill_clear_ml_explanation",
        "url": "https://distill.pub/",
        "design_implication": (
            "Research Document should prioritize human understanding, precise "
            "visual explanation, and reader navigation."
        ),
    },
    {
        "source_id": "world_bank_reproducibility_repository",
        "url": "https://reproducibility.worldbank.org/home",
        "design_implication": (
            "Publication package should make scripts, documentation, data access "
            "boundaries, and reproducibility verification explicit."
        ),
    },
    {
        "source_id": "world_bank_reproducibility_checklist",
        "url": (
            "https://worldbank.github.io/wb-reproducible-research-repository/"
            "reproducibility_package_checklist.html"
        ),
        "design_implication": (
            "The package should map outputs to the scripts and source artifacts "
            "responsible for generating them."
        ),
    },
    {
        "source_id": "ropensci_research_compendium",
        "url": "https://github.com/ropensci/rrrpkg",
        "design_implication": (
            "Repository layout should be instantly legible as a research "
            "compendium, with README as the entry point."
        ),
    },
)

USER_DECISIONS = {
    "research_document_name": "Research Document",
    "scientific_framing": "neutral_scientific_test",
    "cqr_cv_plus_language": (
        "CQR/CV+ were observed as strong practical candidates in these experiments."
    ),
    "venn_abers_language": (
        "In these experiments, the evaluated Venn-Abers regression bridge did not "
        "behave as the expected strong regression solution."
    ),
    "main_supplement_strategy": "minimal_main_article_broad_supplementary_document",
    "kg_strategy": "browsable_supplementary_web_artifact_if_usable",
    "public_release_timing": "after_article_supplement_site_completion",
    "github_pages_strategy": "prepare_site_for_later_github_pages_publication",
    "positive_claim_policy": "keep_positive_claims_closed_report_observed_results",
    "new_experiments_authorized": False,
    "quality_bar": "postdoc_professor_level_research_document",
}

LATEST_NUMBERED_USER_DECISIONS = (
    {
        "decision_number": 1,
        "decision": "A",
        "recorded_effect": (
            "Use the previously offered option A as the active publication "
            "authoring branch."
        ),
    },
    {
        "decision_number": 2,
        "decision": (
            "CQR/CV+ were observed as strong practical candidates in these experiments."
        ),
        "recorded_effect": (
            "Use observed-in-these-experiments language only; do not convert it "
            "into a global recommendation."
        ),
    },
    {
        "decision_number": 3,
        "decision": (
            "Report the Venn-Abers result as observed: the expected strong "
            "regression solution did not emerge in these experiments."
        ),
        "recorded_effect": (
            "Report the evaluated bridge as negative/failure-mode evidence, "
            "without forcing a positive Venn-Abers story."
        ),
    },
    {
        "decision_number": 4,
        "decision": "Proceed to the final article text.",
        "recorded_effect": (
            "Proceed to private Research Document, main article, and supplement "
            "prose under closed public-release boundaries."
        ),
    },
    {
        "decision_number": 5,
        "decision": "Use a minimal main article plus a broad supplementary document.",
        "recorded_effect": (
            "Keep the main article compact and put detailed methods, audits, "
            "tables, and diagnostics into the supplement."
        ),
    },
    {
        "decision_number": 6,
        "decision": (
            "If the knowledge graph is genuinely usable, make it browsable as a "
            "supplementary web artifact."
        ),
        "recorded_effect": (
            "Treat the KG browser as a private supplementary/web artifact "
            "candidate while quality gates remain passing."
        ),
    },
    {
        "decision_number": 7,
        "decision": "Make the package public after the article, supplement, and site are complete.",
        "recorded_effect": (
            "Keep public release closed until article, supplement, and site are "
            "complete."
        ),
    },
    {
        "decision_number": 8,
        "decision": (
            "Publish through GitHub Pages after the article, supplement, and site "
            "are complete."
        ),
        "recorded_effect": (
            "Prepare the site for later GitHub Pages publication, but do not "
            "deploy it publicly now."
        ),
    },
    {
        "decision_number": 9,
        "decision": (
            "Keep Venn-Abers claims closed and report the observed result as it is."
        ),
        "recorded_effect": (
            "No Venn-Abers validation or champion-method claim is authorized."
        ),
    },
    {
        "decision_number": 10,
        "decision": "No, do not open a new experiment branch.",
        "recorded_effect": "No new experiment branch is authorized.",
    },
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


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def check_row(check_id: str, passed: bool, evidence: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "blocker": blocker,
    }


def build_payload(root: Path) -> dict[str, Any]:
    goal = read_json(root / GOAL_COMPLETION)
    claim_matrix = read_json(root / CLAIM_MATRIX)
    private_package = read_json(root / PRIVATE_PACKAGE)
    kg_quality = read_json(root / KG_QUALITY)

    goal_s = summary(goal)
    claim_s = summary(claim_matrix)
    private_s = summary(private_package)
    kg_graph = kg_quality.get("graph") or {}

    sources = {
        "goal_completion_audit": str(GOAL_COMPLETION),
        "publication_claim_evidence_verification_matrix": str(CLAIM_MATRIX),
        "private_sterile_publication_package_manifest": str(PRIVATE_PACKAGE),
        "knowledge_graph_quality_summary": str(KG_QUALITY),
    }
    missing_sources = [path for path in sources.values() if not (root / path).exists()]

    checks = [
        check_row(
            "source_artifacts_present",
            not missing_sources,
            {"missing_sources": missing_sources},
            "authoring_decision_source_missing",
        ),
        check_row(
            "neutral_empirical_phase_complete",
            goal_s.get("neutral_empirical_phase_complete") is True,
            {
                "goal_status": goal_s.get("overall_status"),
                "neutral_empirical_phase_complete": goal_s.get(
                    "neutral_empirical_phase_complete"
                ),
            },
            "neutral_empirical_phase_not_complete",
        ),
        check_row(
            "claim_boundaries_remain_closed",
            claim_s.get("method_recommendation_authorized") is False
            and claim_s.get("positive_claim_promotion_authorized") is False
            and claim_s.get("release_authorized") is False,
            {
                "method_recommendation_authorized": claim_s.get(
                    "method_recommendation_authorized"
                ),
                "positive_claim_promotion_authorized": claim_s.get(
                    "positive_claim_promotion_authorized"
                ),
                "release_authorized": claim_s.get("release_authorized"),
            },
            "claim_boundary_opened",
        ),
        check_row(
            "private_package_ready",
            private_s.get("overall_status") == "private_sterile_publication_package_ready"
            and private_s.get("public_release_authorized") is False,
            {
                "private_package_status": private_s.get("overall_status"),
                "public_release_authorized": private_s.get(
                    "public_release_authorized"
                ),
            },
            "private_package_not_ready",
        ),
        check_row(
            "kg_browsable_candidate_ready",
            int(kg_graph.get("node_count") or 0) > 0
            and int(kg_graph.get("edge_count") or 0) > 0
            and int(kg_graph.get("isolated_node_count") or 0) == 0,
            {
                "kg_node_count": kg_graph.get("node_count"),
                "kg_edge_count": kg_graph.get("edge_count"),
                "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
            },
            "kg_not_ready_for_browsable_candidate",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "summary": {
            "overall_status": (
                "research_document_authoring_decision_ready"
                if not failed_checks
                else "research_document_authoring_decision_blocked"
            ),
            "research_document_authoring_authorized": not failed_checks,
            "private_authoring_authorized": not failed_checks,
            "final_public_release_authorized": False,
            "public_repository_release_authorized": False,
            "publication_site_deployment_authorized": False,
            "kg_citable_component_authorized": False,
            "method_recommendation_authorized": False,
            "method_champion_authorized": False,
            "method_advocacy_authorized": False,
            "positive_claim_promotion_authorized": False,
            "new_experiments_authorized": False,
            "minimal_main_broad_supplement_authorized": True,
            "browsable_kg_site_authoring_authorized": not failed_checks,
            "private_package_status": private_s.get("overall_status"),
            "kg_node_count": kg_graph.get("node_count"),
            "kg_edge_count": kg_graph.get("edge_count"),
            "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
            "inspiration_source_count": len(INSPIRATION_SOURCES),
            "latest_numbered_user_decision_count": len(
                LATEST_NUMBERED_USER_DECISIONS
            ),
            "failed_check_count": len(failed_checks),
        },
        "user_decisions": USER_DECISIONS,
        "latest_numbered_user_decisions": list(LATEST_NUMBERED_USER_DECISIONS),
        "inspiration_sources": list(INSPIRATION_SOURCES),
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "Research Document authoring is authorized for private review.",
            "Public release remains closed until the article, supplement, site, KG, and README pass final review.",
            "CQR/CV+ may be described only as strong practical candidates observed in this experiment.",
            "Venn-Abers may be described only as observed negative/failure-mode evidence for the evaluated regression bridge.",
            "No positive fairness, bounded-support validity, validated Venn-Abers regression, production, or best-method claim is authorized.",
            "No new experiments are authorized by this decision record.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    decisions = payload["user_decisions"]
    lines = [
        "# Publication Authoring Decision Record",
        "",
        "This artifact records the user-approved transition from neutral empirical closure to private Research Document authoring. It does not authorize public release.",
        "",
        "## Status",
        "",
        f"- Overall status: `{s['overall_status']}`",
        f"- Research Document authoring authorized: `{s['research_document_authoring_authorized']}`",
        f"- Public release authorized: `{s['final_public_release_authorized']}`",
        f"- Method recommendation authorized: `{s['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{s['positive_claim_promotion_authorized']}`",
        f"- New experiments authorized: `{s['new_experiments_authorized']}`",
        f"- Browsable KG/site authoring authorized: `{s['browsable_kg_site_authoring_authorized']}`",
        f"- KG nodes / edges: {s['kg_node_count']} / {s['kg_edge_count']}",
        f"- Latest numbered user decisions: {s['latest_numbered_user_decision_count']}",
        f"- Failed checks: {s['failed_check_count']}",
        "",
        "## User Decisions",
        "",
    ]
    for key, value in decisions.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Latest Numbered User Decisions", ""])
    for row in payload["latest_numbered_user_decisions"]:
        lines.append(
            f"- `{row['decision_number']}`: {row['decision']} "
            f"-> {row['recorded_effect']}"
        )
    lines.extend(["", "## Inspiration Sources", ""])
    for row in payload["inspiration_sources"]:
        lines.append(
            f"- `{row['source_id']}`: {row['url']} -- {row['design_implication']}"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(["", "## Checks", "", "| Check | Status | Blocker |", "|---|---|---|"])
    for row in payload["checks"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['blocker']}` |")
    lines.extend(["", "## Source Artifacts", ""])
    for label, path in payload["sources"].items():
        lines.append(f"- `{label}`: `{path}`")
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
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
