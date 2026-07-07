"""Build the sterile repository staging manifest.

This artifact prepares the future clean publication repository requested by the
user. It is intentionally a staging manifest only: it does not create a GitHub
repository, package a release, cite the working repository, write final prose,
retain final visuals/tables, recommend a method, or promote a positive claim.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_sterile_repository_staging_manifest_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/sterile_repository_staging_manifest.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

POST_PROGRAM = Path("experiments/regression/manuscript/post_experiment_publication_program.json")
RELEASE_GAP = Path("experiments/regression/manuscript/publication_release_gap_register.json")
FINAL_AUTHORIZATION = Path(
    "experiments/regression/manuscript/final_publication_output_authorization_protocol.json"
)
GOAL_COMPLETION = Path("experiments/regression/manuscript/goal_completion_audit.json")
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
KG_PUBLICATION = REPORT_DIR / "kg_publication_quality_audit.json"
GRAPH_READINESS = REPORT_DIR / "graph_artifact_readiness_audit.json"
CLAIM_BOUNDARY = Path("experiments/regression/manuscript/section_claim_boundary_audit.json")
NAVIGATION_INDEX = Path(
    "experiments/regression/manuscript/article_supplement_kg_navigation_index.json"
)
VISUAL_AUDITOR = Path(
    "experiments/regression/manuscript/final_publication_visual_auditor_readiness.json"
)

SOURCE_PATHS = {
    "post_experiment_publication_program": POST_PROGRAM,
    "publication_release_gap_register": RELEASE_GAP,
    "final_publication_output_authorization_protocol": FINAL_AUTHORIZATION,
    "goal_completion_audit": GOAL_COMPLETION,
    "neutral_reporting_language_audit": NEUTRAL_LANGUAGE,
    "knowledge_graph_quality_summary": KG_QUALITY,
    "kg_publication_quality_audit": KG_PUBLICATION,
    "graph_artifact_readiness_audit": GRAPH_READINESS,
    "section_claim_boundary_audit": CLAIM_BOUNDARY,
    "article_supplement_kg_navigation_index": NAVIGATION_INDEX,
    "final_publication_visual_auditor_readiness": VISUAL_AUDITOR,
}

CONTENT_POLICIES = [
    {
        "content_id": "polished_readme",
        "match": "polished README",
        "package_family": "repository_documentation",
        "staging_status": "planned_after_final_readme_authoring",
        "candidate_sources": [
            "experiments/regression/manuscript/sterile_repository_readme_draft.md",
            "experiments/regression/manuscript/sterile_repository_readme_draft.json",
            "README.md",
            "experiments/regression/CHANGELOG.md",
            "experiments/regression/manuscript/README.md",
        ],
        "blocking_gate": "final_publication_repository_readme_not_authored",
    },
    {
        "content_id": "main_article_outputs",
        "match": "main article",
        "package_family": "main_article",
        "staging_status": "planned_after_final_manuscript_gate",
        "candidate_sources": [
            "experiments/regression/manuscript/main_article_draft.md",
            "experiments/regression/manuscript/main_article_draft.json",
            "experiments/regression/manuscript/article_supplement_blueprint_alignment.json",
            "experiments/regression/manuscript/manuscript_section_evidence_packet.json",
            "experiments/regression/manuscript/section_claim_boundary_audit.json",
        ],
        "blocking_gate": "final_manuscript_prose_not_authorized",
    },
    {
        "content_id": "supplementary_document_outputs",
        "match": "supplementary document",
        "package_family": "supplementary_document",
        "staging_status": "planned_after_final_supplement_gate",
        "candidate_sources": [
            "experiments/regression/manuscript/supplementary_document_draft.md",
            "experiments/regression/manuscript/supplementary_document_draft.json",
            "experiments/regression/manuscript/article_supplement_blueprint_alignment.json",
            "experiments/regression/manuscript/article_supplement_kg_navigation_index.json",
            "experiments/regression/manuscript/claim_safe_result_extraction_matrix.json",
        ],
        "blocking_gate": "latex_html_authoring_pending",
    },
    {
        "content_id": "individual_experiment_report",
        "match": "individual experiment report",
        "package_family": "individual_experiment_report",
        "staging_status": "blueprint_ready_final_report_blocked",
        "candidate_sources": [
            "experiments/regression/manuscript/individual_experiment_report_draft.md",
            "experiments/regression/manuscript/individual_experiment_report_draft.json",
            "experiments/regression/manuscript/individual_experiment_report_blueprint.json",
            "experiments/regression/manuscript/individual_experiment_report_blueprint.md",
        ],
        "blocking_gate": "final_manuscript_prose_not_authorized",
    },
    {
        "content_id": "knowledge_graph_export",
        "match": "navigable KG",
        "package_family": "knowledge_graph",
        "staging_status": "kg_snapshot_available_citation_blocked",
        "candidate_sources": [
            "experiments/regression/catalogs/knowledge_graph.json",
            "experiments/regression/reports/knowledge_graph_quality/quality_summary.json",
            "experiments/regression/reports/methodology_sanity_audit_20260627/kg_publication_quality_audit.json",
        ],
        "blocking_gate": "kg_citable_component_not_authorized",
    },
    {
        "content_id": "publication_site_package",
        "match": "GitHub Pages/static site",
        "package_family": "publication_site",
        "staging_status": "site_plan_ready_deployment_blocked",
        "candidate_sources": [
            "experiments/regression/manuscript/publication_site_decision_record.json",
            "experiments/regression/manuscript/article_supplement_kg_triptych_decision.json",
            "experiments/regression/manuscript/article_supplement_kg_navigation_index.json",
        ],
        "blocking_gate": "publication_site_deployment_not_authorized",
    },
    {
        "content_id": "reproducibility_environment_and_commands",
        "match": "reproducibility commands",
        "package_family": "reproducibility",
        "staging_status": "candidate_sources_available_needs_final_release_readme",
        "candidate_sources": [
            "requirements.txt",
            "cpfi",
            "experiments/regression/scripts",
            "experiments/regression/configs",
            "experiments/regression/policies",
            "tests",
        ],
        "blocking_gate": "sterile_repository_creation_not_authorized",
    },
    {
        "content_id": "citation_metadata_and_release_notes",
        "match": "citation metadata",
        "package_family": "citation_and_release_notes",
        "staging_status": "planned_after_release_metadata_review",
        "candidate_sources": [
            "LICENSE",
            "experiments/regression/CHANGELOG.md",
            "experiments/regression/manuscript/publication_citation_registry.json",
            "experiments/regression/manuscript/publication_citation_registry.md",
            "experiments/regression/manuscript/references.bib",
            "experiments/regression/manuscript/publication_release_gap_register.json",
        ],
        "blocking_gate": "sterile_release_packaging_pending",
    },
    {
        "content_id": "curated_figures_tables_and_audit_decisions",
        "match": "curated figures",
        "package_family": "figures_tables",
        "staging_status": "draft_candidates_available_final_retention_blocked",
        "candidate_sources": [
            "experiments/regression/manuscript/draft_visual_table_artifacts",
            "experiments/regression/manuscript/visual_table_audit_report.json",
            "experiments/regression/manuscript/final_publication_visual_auditor_readiness.json",
        ],
        "blocking_gate": "final_visual_table_retention_not_authorized",
    },
]

EXPANDED_EXCLUSION_POLICIES = [
    {
        "exclusion_id": "scratch_and_stale_working_notes",
        "patterns": ["scratch/**", "tmp/**", "experiments/output/**"],
        "rationale": "Exclude scratch files, stale notes, and non-citable working output.",
    },
    {
        "exclusion_id": "raw_or_nonredistributable_data",
        "patterns": ["data/raw/**", "data/results/**", "experiments/regression/data/**"],
        "rationale": "Exclude raw data and non-curated downloaded material unless a license-cleared release bundle explicitly includes it.",
    },
    {
        "exclusion_id": "working_ledgers_and_half_finished_reports",
        "patterns": ["experiments/regression/reports/**/ledger*", "experiments/regression/reports/**/checkpoints/**"],
        "rationale": "Exclude working-only ledgers and partial checkpoint state from the publication repository.",
    },
    {
        "exclusion_id": "secrets_credentials_and_local_env",
        "patterns": [".env*", "**/*.pem", "**/*.p12", "**/*secret*", "**/*credential*", "**/*token*"],
        "rationale": "Exclude secrets, credentials, tokens, and local environment files.",
    },
    {
        "exclusion_id": "cache_build_and_runtime_debris",
        "patterns": ["**/__pycache__/**", ".pytest_cache/**", "**/.cache/**", "*.egg-info/**", "build/**", "dist/**"],
        "rationale": "Exclude generated cache, build, and packaging debris.",
    },
    {
        "exclusion_id": "git_and_local_metadata",
        "patterns": [".git/**", ".DS_Store", "**/.ipynb_checkpoints/**"],
        "rationale": "Exclude VCS internals and local metadata.",
    },
    {
        "exclusion_id": "unsupported_or_promotional_claim_artifacts",
        "patterns": ["**/*unsupported_claim*", "**/*promotion*", "**/*winner_claim*"],
        "rationale": "Exclude artifacts whose claim boundary is not authorized by the final publication gates.",
    },
    {
        "exclusion_id": "unapproved_generated_visuals_tables",
        "patterns": ["experiments/regression/manuscript/draft_visual_table_artifacts/**"],
        "rationale": "Keep draft visuals/tables out of the final release unless the visual auditor and retention gates explicitly approve them.",
    },
    {
        "exclusion_id": "large_or_private_intermediate_outputs",
        "patterns": ["**/*.parquet", "**/*.feather", "**/*.pkl", "**/*.joblib", "**/*.sqlite", "**/*.db"],
        "rationale": "Exclude large or private intermediate files unless a citable release manifest explicitly includes them.",
    },
]

RISK_PATTERNS = tuple(
    pattern
    for policy in EXPANDED_EXCLUSION_POLICIES
    for pattern in policy["patterns"]
)

AUTHORIZATION_FIELDS = (
    "final_manuscript_prose_permission",
    "final_visual_table_retention_authorized",
    "latex_html_authoring_authorized",
    "publication_site_deployment_authorized",
    "kg_citable_component_authorized",
    "sterile_repository_creation_authorized",
    "working_repository_final_citable",
    "method_recommendation_authorized",
    "method_champion_authorized",
    "method_advocacy_authorized",
    "positive_claim_promotion_authorized",
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


def kg_quality_counts(payload: dict[str, Any]) -> dict[str, Any]:
    graph = payload.get("graph") if isinstance(payload, dict) else {}
    observations = payload.get("observations") if isinstance(payload, dict) else {}
    graph = graph if isinstance(graph, dict) else {}
    observations = observations if isinstance(observations, dict) else {}
    return {
        "node_count": graph.get("node_count"),
        "edge_count": graph.get("edge_count"),
        "isolated_node_count": graph.get("isolated_node_count"),
        "total_observation_count": observations.get("total_observation_count"),
    }


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


def source_status(root: Path, source_paths: list[str]) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for source in source_paths:
        source_path = root / source
        relative = rel(source_path, root)
        if source_path.exists():
            present.append(relative)
        else:
            missing.append(relative)
    return present, missing


def source_artifact_status(root: Path) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for path in SOURCE_PATHS.values():
        relative = rel(root / path, root)
        if (root / path).exists():
            present.append(relative)
        else:
            missing.append(relative)
    return present, missing


def tracked_paths(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            rel(path, root)
            for path in root.rglob("*")
            if path.is_file()
            and ".git" not in path.parts
            and "__pycache__" not in path.parts
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def matches_any(path: str, patterns: tuple[str, ...] | list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def candidate_inclusion_paths(rows: list[dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for row in rows:
        paths.update(str(path) for path in row.get("source_artifacts") or [])
    return paths


def build_required_content_rows(
    root: Path,
    required_contents: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, content in enumerate(required_contents):
        content_text = str(content)
        policy = next(
            (
                item
                for item in CONTENT_POLICIES
                if item["match"].lower() in content_text.lower()
            ),
            None,
        )
        if policy is None:
            policy = {
                "content_id": f"unmapped_required_content_{index}",
                "package_family": "unmapped",
                "staging_status": "mapping_required_before_release",
                "candidate_sources": [],
                "blocking_gate": "sterile_release_packaging_pending",
            }
        present, missing = source_status(root, list(policy["candidate_sources"]))
        risk_hits = sorted(path for path in present if matches_any(path, RISK_PATTERNS))
        rows.append(
            {
                "content_id": policy["content_id"],
                "row_index": index,
                "required_content": content_text,
                "package_family": policy["package_family"],
                "staging_status": policy["staging_status"],
                "blocking_gate": policy["blocking_gate"],
                "source_artifacts": present,
                "missing_source_artifacts": missing,
                "source_traceability_status": "pass" if present else "fail",
                "candidate_exclusion_risk_hits": risk_hits,
                "final_content_authorized": False,
                "release_authorized": False,
                "claim_boundary": (
                    "Required content is a staging-manifest row only; final "
                    "copying, citation, release, and publication use remain "
                    "blocked until downstream gates authorize them."
                ),
            }
        )
    return rows


def build_exclusion_rows(
    root: Path,
    post_program_exclusions: list[str],
    all_tracked_paths: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, rule in enumerate(post_program_exclusions):
        rows.append(
            {
                "exclusion_id": f"post_program_rule_{index}",
                "row_index": index,
                "source": "post_experiment_publication_program",
                "patterns": [],
                "rationale": str(rule),
                "tracked_path_hit_count": None,
                "tracked_path_hit_examples": [],
                "source_artifacts": [rel(root / POST_PROGRAM, root)],
                "source_traceability_status": "pass",
            }
        )
    offset = len(rows)
    for local_index, policy in enumerate(EXPANDED_EXCLUSION_POLICIES):
        patterns = list(policy["patterns"])
        hits = sorted(path for path in all_tracked_paths if matches_any(path, patterns))
        rows.append(
            {
                "exclusion_id": policy["exclusion_id"],
                "row_index": offset + local_index,
                "source": "expanded_sterile_repository_policy",
                "patterns": patterns,
                "rationale": policy["rationale"],
                "tracked_path_hit_count": len(hits),
                "tracked_path_hit_examples": hits[:12],
                "source_artifacts": [
                    rel(root / POST_PROGRAM, root),
                    rel(root / FINAL_AUTHORIZATION, root),
                    rel(root / RELEASE_GAP, root),
                ],
                "source_traceability_status": "pass",
            }
        )
    return rows


def authorization_violations(payloads: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for source_name, payload in payloads.items():
        payload_summary = summary(payload)
        for field in AUTHORIZATION_FIELDS:
            if payload_summary.get(field) is True:
                violations.append({"source": source_name, "field": field})
    return violations


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
    root = root.resolve()
    post_program = read_json(root / POST_PROGRAM)
    release_gap = read_json(root / RELEASE_GAP)
    final_authorization = read_json(root / FINAL_AUTHORIZATION)
    goal_completion = read_json(root / GOAL_COMPLETION)
    neutral_language = read_json(root / NEUTRAL_LANGUAGE)
    kg_quality = read_json(root / KG_QUALITY)
    kg_publication = read_json(root / KG_PUBLICATION)
    graph_readiness = read_json(root / GRAPH_READINESS)
    claim_boundary = read_json(root / CLAIM_BOUNDARY)
    navigation_index = read_json(root / NAVIGATION_INDEX)
    visual_auditor = read_json(root / VISUAL_AUDITOR)

    payloads = {
        "publication_release_gap_register": release_gap,
        "final_publication_output_authorization_protocol": final_authorization,
        "goal_completion_audit": goal_completion,
        "neutral_reporting_language_audit": neutral_language,
        "kg_publication_quality_audit": kg_publication,
        "graph_artifact_readiness_audit": graph_readiness,
        "section_claim_boundary_audit": claim_boundary,
        "article_supplement_kg_navigation_index": navigation_index,
        "final_publication_visual_auditor_readiness": visual_auditor,
    }
    source_present, source_missing = source_artifact_status(root)
    sterile_plan = post_program.get("sterile_publication_repository_plan") or {}
    required_contents = list(sterile_plan.get("required_contents") or [])
    post_exclusions = list(sterile_plan.get("exclusion_rules") or [])
    all_tracked_paths = tracked_paths(root)
    required_content_rows = build_required_content_rows(root, required_contents)
    exclusion_rows = build_exclusion_rows(root, post_exclusions, all_tracked_paths)
    candidate_paths = candidate_inclusion_paths(required_content_rows)
    candidate_risk_hits = sorted(path for path in candidate_paths if matches_any(path, RISK_PATTERNS))
    all_authorization_violations = authorization_violations(payloads)

    release_gap_summary = summary(release_gap)
    final_authorization_summary = summary(final_authorization)
    goal_summary = summary(goal_completion)
    neutral_language_summary = summary(neutral_language)
    kg_quality_graph = kg_quality_counts(kg_quality)
    kg_publication_summary = summary(kg_publication)
    graph_summary = summary(graph_readiness)
    claim_boundary_summary = summary(claim_boundary)
    navigation_summary = summary(navigation_index)
    visual_summary = summary(visual_auditor)

    required_content_traceable_count = sum(
        1 for row in required_content_rows if row["source_traceability_status"] == "pass"
    )
    required_content_with_blocking_gate_count = sum(
        1 for row in required_content_rows if row.get("blocking_gate")
    )
    final_authorized_content_count = sum(
        1 for row in required_content_rows if row.get("final_content_authorized") is True
    )
    exclusion_source_traceable_count = sum(
        1 for row in exclusion_rows if row["source_traceability_status"] == "pass"
    )
    tracked_risk_counts = Counter()
    for row in exclusion_rows:
        if row.get("tracked_path_hit_count") is not None:
            tracked_risk_counts[str(row["exclusion_id"])] = int(row["tracked_path_hit_count"])

    checks = [
        check_row(
            "source_artifacts_present",
            not source_missing,
            {"missing_source_artifacts": source_missing, "source_artifact_count": len(source_present)},
            "missing_sterile_repository_manifest_source",
        ),
        check_row(
            "post_program_sterile_plan_present",
            sterile_plan.get("status") == "planned_after_full_experiment_closure"
            and sterile_plan.get("repository_visibility_at_creation") == "private"
            and sterile_plan.get("working_repository_citation_status")
            == "not_final_citable_repository",
            {
                "status": sterile_plan.get("status"),
                "repository_visibility_at_creation": sterile_plan.get(
                    "repository_visibility_at_creation"
                ),
                "working_repository_citation_status": sterile_plan.get(
                    "working_repository_citation_status"
                ),
            },
            "sterile_repository_plan_missing_or_not_private",
        ),
        check_row(
            "required_contents_mapped",
            len(required_content_rows) == len(CONTENT_POLICIES)
            and required_content_traceable_count == len(required_content_rows)
            and required_content_with_blocking_gate_count == len(required_content_rows),
            {
                "required_content_row_count": len(required_content_rows),
                "expected_content_policy_count": len(CONTENT_POLICIES),
                "required_content_traceable_count": required_content_traceable_count,
                "required_content_with_blocking_gate_count": required_content_with_blocking_gate_count,
            },
            "sterile_repository_required_content_mapping_incomplete",
        ),
        check_row(
            "exclusion_policy_complete",
            len(post_exclusions) >= 3
            and len(exclusion_rows) == len(post_exclusions) + len(EXPANDED_EXCLUSION_POLICIES)
            and exclusion_source_traceable_count == len(exclusion_rows),
            {
                "post_program_exclusion_rule_count": len(post_exclusions),
                "expanded_exclusion_rule_count": len(EXPANDED_EXCLUSION_POLICIES),
                "exclusion_policy_row_count": len(exclusion_rows),
                "exclusion_source_traceable_count": exclusion_source_traceable_count,
            },
            "sterile_repository_exclusion_policy_incomplete",
        ),
        check_row(
            "candidate_inclusion_policy_excludes_risky_paths",
            not candidate_risk_hits,
            {"candidate_inclusion_risk_hit_count": len(candidate_risk_hits), "examples": candidate_risk_hits[:12]},
            "sterile_repository_candidate_inclusion_contains_excluded_paths",
        ),
        check_row(
            "final_authorizations_remain_closed",
            not all_authorization_violations
            and final_authorized_content_count == 0
            and final_authorization_summary.get("sterile_repository_creation_authorized") is False
            and final_authorization_summary.get("working_repository_final_citable") is False,
            {
                "authorization_violation_count": len(all_authorization_violations),
                "final_authorized_content_count": final_authorized_content_count,
                "sterile_repository_creation_authorized": final_authorization_summary.get(
                    "sterile_repository_creation_authorized"
                ),
                "working_repository_final_citable": final_authorization_summary.get(
                    "working_repository_final_citable"
                ),
            },
            "sterile_repository_final_authorization_opened",
        ),
        check_row(
            "release_gap_remains_blocked",
            release_gap_summary.get("sterile_repository_creation_authorized") is False
            and release_gap_summary.get("working_repository_final_citable") is False
            and safe_int(release_gap_summary.get("release_authorized_count")) == 0,
            {
                "release_authorized_count": release_gap_summary.get("release_authorized_count"),
                "sterile_repository_creation_authorized": release_gap_summary.get(
                    "sterile_repository_creation_authorized"
                ),
                "working_repository_final_citable": release_gap_summary.get(
                    "working_repository_final_citable"
                ),
            },
            "publication_release_gap_authorized_sterile_release",
        ),
        check_row(
            "neutral_scientific_reporting_guards_present",
            neutral_language_summary.get("overall_status") == "neutral_reporting_language_audit_pass"
            and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
            and final_authorization_summary.get("analysis_only_no_champion_method")
            is True
            and final_authorization_summary.get("method_champion_authorized") is False
            and final_authorization_summary.get("method_advocacy_authorized") is False
            and final_authorization_summary.get("result_reporting_policy")
            == "analysis_only_report_observed_behavior_no_method_advocacy"
            and claim_boundary_summary.get("main_results_positive_boundary_blocked") is True
            and navigation_summary.get("working_repository_final_citable") is False
            and visual_summary.get("final_visual_table_retention_authorized") is False,
            {
                "neutral_language_status": neutral_language_summary.get("overall_status"),
                "neutral_language_unguarded_hit_count": neutral_language_summary.get(
                    "unguarded_hit_count"
                ),
                "analysis_only_no_champion_method": final_authorization_summary.get(
                    "analysis_only_no_champion_method"
                ),
                "method_champion_authorized": final_authorization_summary.get(
                    "method_champion_authorized"
                ),
                "result_reporting_policy": final_authorization_summary.get(
                    "result_reporting_policy"
                ),
                "main_results_positive_boundary_blocked": claim_boundary_summary.get(
                    "main_results_positive_boundary_blocked"
                ),
                "navigation_working_repository_final_citable": navigation_summary.get(
                    "working_repository_final_citable"
                ),
                "visual_final_retention_authorized": visual_summary.get(
                    "final_visual_table_retention_authorized"
                ),
            },
            "neutral_scientific_reporting_guard_missing",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]

    summary_payload = {
        "overall_status": (
            "sterile_repository_staging_manifest_ready_no_repository_created"
            if not failed_checks
            else "sterile_repository_staging_manifest_blocked"
        ),
        "phase_state": "neutral_sterile_repository_manifest_ready_creation_blocked",
        "staging_manifest_status": "manifest_ready_creation_and_release_blocked",
        "repository_visibility_at_creation": sterile_plan.get(
            "repository_visibility_at_creation"
        ),
        "eventual_visibility": sterile_plan.get("eventual_visibility"),
        "citation_target": sterile_plan.get("citation_target"),
        "working_repository_citation_status": sterile_plan.get(
            "working_repository_citation_status"
        ),
        "required_content_row_count": len(required_content_rows),
        "required_content_traceable_count": required_content_traceable_count,
        "required_content_with_blocking_gate_count": required_content_with_blocking_gate_count,
        "candidate_inclusion_risk_hit_count": len(candidate_risk_hits),
        "post_program_exclusion_rule_count": len(post_exclusions),
        "expanded_exclusion_rule_count": len(EXPANDED_EXCLUSION_POLICIES),
        "exclusion_policy_row_count": len(exclusion_rows),
        "exclusion_source_traceable_count": exclusion_source_traceable_count,
        "tracked_path_count": len(all_tracked_paths),
        "tracked_risk_counts": dict(tracked_risk_counts),
        "source_artifact_count": len(source_present),
        "missing_source_artifact_count": len(source_missing),
        "goal_can_mark_complete": goal_summary.get("can_mark_goal_complete"),
        "neutral_empirical_phase_complete": goal_summary.get("neutral_empirical_phase_complete"),
        "publication_completed_rows": goal_summary.get("publication_completed_rows"),
        "kg_node_count": kg_quality_graph.get("node_count"),
        "kg_edge_count": kg_quality_graph.get("edge_count"),
        "kg_isolated_node_count": kg_quality_graph.get("isolated_node_count"),
        "kg_total_observation_count": kg_quality_graph.get("total_observation_count"),
        "kg_publication_status": kg_publication_summary.get("overall_status"),
        "graph_artifact_readiness_status": graph_summary.get("overall_status"),
        "private_repository_created": False,
        "sterile_repository_creation_authorized": False,
        "sterile_release_packaging_authorized": False,
        "release_authorized": False,
        "final_manuscript_prose_permission": False,
        "final_visual_table_retention_authorized": False,
        "latex_html_authoring_authorized": False,
        "publication_site_deployment_authorized": False,
        "kg_citable_component_authorized": False,
        "working_repository_final_citable": False,
        "method_recommendation_authorized": False,
        "positive_claim_promotion_authorized": False,
        "analysis_only_no_champion_method": final_authorization_summary.get(
            "analysis_only_no_champion_method"
        ),
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "result_reporting_policy": final_authorization_summary.get(
            "result_reporting_policy"
        ),
        "authorization_violation_count": len(all_authorization_violations),
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {name: rel(root / path, root) for name, path in SOURCE_PATHS.items()},
        "summary": summary_payload,
        "required_content_rows": required_content_rows,
        "exclusion_policy_rows": exclusion_rows,
        "candidate_inclusion_risk_hits": candidate_risk_hits,
        "authorization_violations": all_authorization_violations,
        "checks": checks,
        "claim_boundaries": [
            "This artifact is a staging manifest only; it does not create a repository.",
            "The working repository remains not final-citable.",
            "No method recommendation or positive scientific claim is authorized.",
            "Future sterile repository content must report analysis-only observations and must not frame any method as a champion, winner, or general recommendation.",
            "Raw data, secrets, cache files, and working-only debris must be excluded from the future sterile repository unless a later release manifest explicitly and safely includes them.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Sterile Repository Staging Manifest",
        "",
        "This is a neutral staging manifest. It does not create a repository, package a release, cite the working repository, write final prose, retain final visuals/tables, recommend a method, or promote a positive claim.",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase state: `{summary_payload['phase_state']}`",
        f"- Required content rows: {summary_payload['required_content_row_count']}",
        f"- Required content traceable rows: {summary_payload['required_content_traceable_count']}",
        f"- Exclusion policy rows: {summary_payload['exclusion_policy_row_count']}",
        f"- Candidate inclusion risk hits: {summary_payload['candidate_inclusion_risk_hit_count']}",
        f"- Private repository created: `{summary_payload['private_repository_created']}`",
        f"- Sterile repository creation authorized: `{summary_payload['sterile_repository_creation_authorized']}`",
        f"- Release authorized: `{summary_payload['release_authorized']}`",
        f"- Working repository final-citable: `{summary_payload['working_repository_final_citable']}`",
        f"- Result reporting policy: `{summary_payload['result_reporting_policy']}`",
        f"- Champion method authorized: `{summary_payload['method_champion_authorized']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive-claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        f"- Failed checks: {summary_payload['failed_check_count']}",
        "",
        "## Required Content Rows",
        "",
        "| Content | Family | Status | Blocking gate | Sources | Risk hits |",
        "|---|---|---|---|---:|---:|",
    ]
    for row in payload["required_content_rows"]:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` | {} | {} |".format(
                row["content_id"],
                row["package_family"],
                row["staging_status"],
                row["blocking_gate"],
                len(row["source_artifacts"]),
                len(row["candidate_exclusion_risk_hits"]),
            )
        )
    lines.extend(
        [
            "",
            "## Exclusion Policy Rows",
            "",
            "| Exclusion | Source | Patterns | Tracked hits |",
            "|---|---|---:|---:|",
        ]
    )
    for row in payload["exclusion_policy_rows"]:
        hit_count = row["tracked_path_hit_count"]
        hit_text = "" if hit_count is None else str(hit_count)
        lines.append(
            "| `{}` | `{}` | {} | {} |".format(
                row["exclusion_id"],
                row["source"],
                len(row["patterns"]),
                hit_text,
            )
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Blocker |",
            "|---|---|---|",
        ]
    )
    for row in payload["checks"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['blocker']}` |")
    lines.extend(["", "## Boundaries", ""])
    for item in payload["claim_boundaries"]:
        lines.append(f"- {item}")
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
                "required_content_row_count": payload["summary"][
                    "required_content_row_count"
                ],
                "exclusion_policy_row_count": payload["summary"][
                    "exclusion_policy_row_count"
                ],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
