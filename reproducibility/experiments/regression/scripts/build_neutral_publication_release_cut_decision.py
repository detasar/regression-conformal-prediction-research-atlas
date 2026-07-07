"""Build the neutral publication release-cut decision.

This artifact is the narrow transition from pre-final controls to private
sterile publication packaging. It does not authorize public release, working
repository citation, method recommendation, method advocacy, or positive
scientific claims.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_neutral_publication_release_cut_decision_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/neutral_publication_release_cut_decision.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

FINAL_AUTHORIZATION = Path(
    "experiments/regression/manuscript/"
    "final_publication_output_authorization_protocol.json"
)
CLAIM_CITATION_AUDIT = Path(
    "experiments/regression/manuscript/"
    "manuscript_claim_citation_readiness_audit.json"
)
CLAIM_EVIDENCE_MATRIX = Path(
    "experiments/regression/manuscript/"
    "publication_claim_evidence_verification_matrix.json"
)
MAIN_ARTICLE = Path("experiments/regression/manuscript/main_article_draft.json")
SUPPLEMENT = Path("experiments/regression/manuscript/supplementary_document_draft.json")
INDIVIDUAL_REPORT = Path(
    "experiments/regression/manuscript/individual_experiment_report_draft.json"
)
STERILE_MANIFEST = Path(
    "experiments/regression/manuscript/sterile_repository_staging_manifest.json"
)
STERILE_README = Path(
    "experiments/regression/manuscript/sterile_repository_readme_draft.json"
)
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
GRAPH_READINESS = REPORT_DIR / "graph_artifact_readiness_audit.json"
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"

SOURCE_PATHS = {
    "final_publication_output_authorization_protocol": FINAL_AUTHORIZATION,
    "manuscript_claim_citation_readiness_audit": CLAIM_CITATION_AUDIT,
    "publication_claim_evidence_verification_matrix": CLAIM_EVIDENCE_MATRIX,
    "main_article_draft": MAIN_ARTICLE,
    "supplementary_document_draft": SUPPLEMENT,
    "individual_experiment_report_draft": INDIVIDUAL_REPORT,
    "sterile_repository_staging_manifest": STERILE_MANIFEST,
    "sterile_repository_readme_draft": STERILE_README,
    "knowledge_graph_quality_summary": KG_QUALITY,
    "graph_artifact_readiness_audit": GRAPH_READINESS,
    "neutral_reporting_language_audit": NEUTRAL_LANGUAGE,
}

AUTHORIZED_NEXT_ACTIONS = (
    {
        "action_id": "prepare_private_sterile_repository",
        "authorization_status": "authorized_for_private_packaging",
        "scope": "Create or stage a private clean repository package for user review.",
        "must_preserve": [
            "working_repository_final_citable_false",
            "public_release_requires_user_review",
            "raw_data_and_secrets_excluded",
        ],
    },
    {
        "action_id": "assemble_neutral_article_and_supplement_outputs",
        "authorization_status": "authorized_for_neutral_output_assembly",
        "scope": "Assemble article and supplement outputs from evidence-linked drafts.",
        "must_preserve": [
            "observed_evidence_language_only",
            "no_method_recommendation",
            "no_positive_claim_promotion",
        ],
    },
    {
        "action_id": "export_citable_knowledge_graph_snapshot",
        "authorization_status": "authorized_for_private_package_snapshot",
        "scope": "Export the current KG and quality summary into the private package.",
        "must_preserve": [
            "kg_claim_boundaries_visible",
            "source_provenance_retained",
            "public_citation_requires_user_review",
        ],
    },
    {
        "action_id": "prepare_latex_html_and_static_site_package",
        "authorization_status": "authorized_for_private_render_package",
        "scope": "Prepare LaTeX, HTML, and static-site files for private review.",
        "must_preserve": [
            "no_public_deployment_without_user_review",
            "neutral_language_scan_after_render",
            "figure_table_overlap_check_after_render",
        ],
    },
)

BLOCKED_ACTIONS = (
    "public_repository_release_before_user_review",
    "working_repository_final_citation",
    "method_recommendation_or_winner_language",
    "positive_performance_fairness_bounded_support_or_venn_abers_claim",
    "raw_or_nonredistributable_data_inclusion",
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


def check_row(check_id: str, passed: bool, evidence: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "blocker": blocker,
    }


def build_payload(root: Path) -> dict[str, Any]:
    payloads = {name: read_json(root / path) for name, path in SOURCE_PATHS.items()}
    summaries = {name: summary(payload) for name, payload in payloads.items()}
    present_sources, missing_sources = source_status(root)

    final_auth = summaries["final_publication_output_authorization_protocol"]
    claim_citation = summaries["manuscript_claim_citation_readiness_audit"]
    claim_matrix = summaries["publication_claim_evidence_verification_matrix"]
    main_article = summaries["main_article_draft"]
    supplement = summaries["supplementary_document_draft"]
    individual = summaries["individual_experiment_report_draft"]
    sterile_manifest = summaries["sterile_repository_staging_manifest"]
    sterile_readme = summaries["sterile_repository_readme_draft"]
    neutral_language = summaries["neutral_reporting_language_audit"]
    graph_readiness = summaries["graph_artifact_readiness_audit"]

    kg_quality = payloads["knowledge_graph_quality_summary"]
    kg_graph = kg_quality.get("graph") or {}
    kg_traceability = kg_quality.get("traceability") or {}
    kg_issues = kg_quality.get("issue_counts_by_severity") or {}

    output_readiness = {
        "final_authorization_protocol_clean": (
            final_auth.get("overall_status")
            == "final_publication_output_authorization_protocol_ready_no_authorizations"
            and safe_int(final_auth.get("failed_check_count")) == 0
        ),
        "claim_citation_ready": (
            claim_citation.get("overall_status")
            == "manuscript_claim_citation_readiness_ready_no_final_prose"
            and safe_int(claim_citation.get("failed_check_count")) == 0
        ),
        "claim_evidence_ready": (
            claim_matrix.get("overall_status")
            == "publication_claim_evidence_verification_ready_no_final_prose"
            and safe_int(claim_matrix.get("failed_check_count")) == 0
        ),
        "main_article_ready": (
            main_article.get("overall_status") == "main_article_draft_ready"
            and safe_int(main_article.get("failed_check_count")) == 0
        ),
        "supplement_ready": (
            supplement.get("overall_status") == "supplementary_document_draft_ready"
            and safe_int(supplement.get("failed_check_count")) == 0
        ),
        "individual_report_ready": (
            individual.get("overall_status") == "individual_experiment_report_draft_ready"
            and safe_int(individual.get("failed_check_count")) == 0
        ),
        "sterile_manifest_ready": (
            sterile_manifest.get("overall_status")
            == "sterile_repository_staging_manifest_ready_no_repository_created"
            and safe_int(sterile_manifest.get("failed_check_count")) == 0
        ),
        "sterile_readme_ready": (
            sterile_readme.get("overall_status") == "sterile_repository_readme_draft_ready"
            and safe_int(sterile_readme.get("failed_check_count")) == 0
        ),
        "neutral_language_ready": (
            neutral_language.get("overall_status") == "neutral_reporting_language_audit_pass"
            and safe_int(neutral_language.get("unguarded_hit_count")) == 0
        ),
        "kg_ready": (
            safe_int(kg_graph.get("node_count")) >= 3538
            and safe_int(kg_graph.get("edge_count")) >= 20069
            and safe_int(kg_graph.get("isolated_node_count")) == 0
            and not kg_issues
            and float(kg_traceability.get("edge_selector_provenance_coverage") or 0.0)
            == 1.0
        ),
        "graph_artifacts_ready": (
            graph_readiness.get("overall_status") == "graph_artifact_readiness_pass"
            and safe_int(graph_readiness.get("failed_check_count")) == 0
            and graph_readiness.get("all_required_tokens_present") is True
            and graph_readiness.get("all_kg_graph_nodes_traceable") is True
        ),
    }
    readiness_counts = Counter(
        "pass" if value else "fail" for value in output_readiness.values()
    )

    promotion_boundary_ok = (
        final_auth.get("scientific_test_not_method_promotion") is True
        and final_auth.get("analysis_only_no_champion_method") is True
        and final_auth.get("method_recommendation_authorized") is False
        and final_auth.get("method_champion_authorized") is False
        and final_auth.get("method_advocacy_authorized") is False
        and final_auth.get("positive_claim_promotion_authorized") is False
        and final_auth.get("working_repository_final_citable") is False
    )
    public_release_boundary_ok = (
        sterile_manifest.get("private_repository_created") is False
        and sterile_manifest.get("release_authorized") is False
        and sterile_readme.get("release_authorized") is False
    )

    checks = [
        check_row(
            "source_artifacts_present",
            not missing_sources,
            {"missing_source_artifacts": missing_sources},
            "missing_release_cut_source",
        ),
        check_row(
            "neutral_output_surfaces_ready",
            all(output_readiness.values()),
            {
                "readiness": output_readiness,
                "pass_count": readiness_counts.get("pass", 0),
                "fail_count": readiness_counts.get("fail", 0),
            },
            "neutral_output_surface_not_ready",
        ),
        check_row(
            "promotion_boundaries_remain_closed",
            promotion_boundary_ok,
            {
                "method_recommendation_authorized": final_auth.get(
                    "method_recommendation_authorized"
                ),
                "method_champion_authorized": final_auth.get("method_champion_authorized"),
                "method_advocacy_authorized": final_auth.get("method_advocacy_authorized"),
                "positive_claim_promotion_authorized": final_auth.get(
                    "positive_claim_promotion_authorized"
                ),
                "working_repository_final_citable": final_auth.get(
                    "working_repository_final_citable"
                ),
            },
            "promotion_or_working_repo_citation_opened",
        ),
        check_row(
            "private_release_cut_keeps_public_release_closed",
            public_release_boundary_ok,
            {
                "private_repository_created": sterile_manifest.get(
                    "private_repository_created"
                ),
                "staging_release_authorized": sterile_manifest.get("release_authorized"),
                "readme_release_authorized": sterile_readme.get("release_authorized"),
            },
            "public_release_opened_before_user_review",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    ready = not failed_checks

    summary_payload = {
        "overall_status": (
            "neutral_publication_release_cut_ready"
            if ready
            else "neutral_publication_release_cut_blocked"
        ),
        "phase_state": "neutral_private_release_cut_ready_public_release_blocked",
        "neutral_private_sterile_repository_preparation_authorized": ready,
        "neutral_article_supplement_output_assembly_authorized": ready,
        "neutral_latex_html_static_site_package_authorized": ready,
        "kg_private_package_snapshot_authorized": ready,
        "public_release_authorized": False,
        "working_repository_final_citable": False,
        "method_recommendation_authorized": False,
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "positive_claim_promotion_authorized": False,
        "raw_data_or_secret_inclusion_authorized": False,
        "authorized_next_action_count": len(AUTHORIZED_NEXT_ACTIONS) if ready else 0,
        "blocked_action_count": len(BLOCKED_ACTIONS),
        "source_artifact_count": len(present_sources),
        "missing_source_artifact_count": len(missing_sources),
        "readiness_check_count": len(output_readiness),
        "readiness_pass_count": readiness_counts.get("pass", 0),
        "readiness_fail_count": readiness_counts.get("fail", 0),
        "kg_node_count": kg_graph.get("node_count"),
        "kg_edge_count": kg_graph.get("edge_count"),
        "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
        "graph_artifact_readiness_status": graph_readiness.get("overall_status"),
        "claim_citation_status": claim_citation.get("overall_status"),
        "claim_evidence_status": claim_matrix.get("overall_status"),
        "neutral_language_status": neutral_language.get("overall_status"),
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {name: rel(root / path, root) for name, path in SOURCE_PATHS.items()},
        "present_source_artifacts": present_sources,
        "missing_source_artifacts": missing_sources,
        "summary": summary_payload,
        "output_readiness": output_readiness,
        "authorized_next_actions": list(AUTHORIZED_NEXT_ACTIONS) if ready else [],
        "blocked_actions": list(BLOCKED_ACTIONS),
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This decision authorizes private neutral packaging only, not public release.",
            "The working repository remains non-citable as a final publication artifact.",
            "Method recommendation, method advocacy, and positive claims remain unauthorized.",
            "CQR/CV+/Venn-Abers findings must remain descriptive, scoped, or negative as supported by the evidence matrix.",
            "Raw data, secrets, local caches, and nonredistributable source files remain excluded from the sterile package.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# Neutral Publication Release-Cut Decision",
        "",
        "This decision opens private neutral publication packaging while keeping public release, method recommendation, and positive claims closed.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{s['overall_status']}`",
        f"- Phase state: `{s['phase_state']}`",
        f"- Private sterile repository preparation authorized: `{s['neutral_private_sterile_repository_preparation_authorized']}`",
        f"- Neutral article/supplement assembly authorized: `{s['neutral_article_supplement_output_assembly_authorized']}`",
        f"- LaTeX/HTML/static-site package authorized: `{s['neutral_latex_html_static_site_package_authorized']}`",
        f"- KG private package snapshot authorized: `{s['kg_private_package_snapshot_authorized']}`",
        f"- Public release authorized: `{s['public_release_authorized']}`",
        f"- Method recommendation authorized: `{s['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{s['positive_claim_promotion_authorized']}`",
        f"- Readiness checks passing: {s['readiness_pass_count']} / {s['readiness_check_count']}",
        f"- KG snapshot: {s['kg_node_count']} nodes / {s['kg_edge_count']} edges / {s['kg_isolated_node_count']} isolated",
        f"- Failed checks: {s['failed_check_count']}",
        "",
        "## Authorized Next Actions",
        "",
        "| Action | Status | Scope |",
        "|---|---|---|",
    ]
    for action in payload["authorized_next_actions"]:
        lines.append(
            "| `{}` | `{}` | {} |".format(
                action["action_id"],
                action["authorization_status"],
                action["scope"],
            )
        )
    lines.extend(["", "## Blocked Actions", ""])
    for action in payload["blocked_actions"]:
        lines.append(f"- `{action}`")
    lines.extend(["", "## Checks", "", "| Check | Status | Blocker |", "|---|---|---|"])
    for row in payload["checks"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['blocker']}` |")
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
                "authorized_next_action_count": payload["summary"][
                    "authorized_next_action_count"
                ],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
