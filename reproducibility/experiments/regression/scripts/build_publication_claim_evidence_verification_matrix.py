"""Build the publication claim/evidence verification matrix.

This is a pre-prose publication artifact. It verifies that each planned
article, supplement, and individual-report evidence row has matching
claim-safe, section-boundary, and KG-navigation controls while final prose,
release, method recommendation, method advocacy, and positive-claim promotion
remain blocked.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_publication_claim_evidence_verification_matrix_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/"
    "publication_claim_evidence_verification_matrix.json"
)

REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
CLAIM_SAFE_MATRIX = Path(
    "experiments/regression/manuscript/claim_safe_result_extraction_matrix.json"
)
SECTION_PACKET = Path(
    "experiments/regression/manuscript/manuscript_section_evidence_packet.json"
)
SECTION_BOUNDARY = Path(
    "experiments/regression/manuscript/section_claim_boundary_audit.json"
)
NAVIGATION_INDEX = Path(
    "experiments/regression/manuscript/article_supplement_kg_navigation_index.json"
)
FINAL_AUTHORIZATION = Path(
    "experiments/regression/manuscript/"
    "final_publication_output_authorization_protocol.json"
)
SCIENTIFIC_NEUTRALITY = Path(
    "experiments/regression/manuscript/scientific_neutrality_interpretation_lock.json"
)
RELEASE_GAP = Path(
    "experiments/regression/manuscript/publication_release_gap_register.json"
)
NEUTRAL_LANGUAGE = REPORT_DIR / "neutral_reporting_language_audit.json"
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
PUBLICATION_CITATION_REGISTRY = Path(
    "experiments/regression/manuscript/publication_citation_registry.json"
)
MAIN_ARTICLE_DRAFT = Path("experiments/regression/manuscript/main_article_draft.json")
SUPPLEMENTARY_DOCUMENT_DRAFT = Path(
    "experiments/regression/manuscript/supplementary_document_draft.json"
)
INDIVIDUAL_EXPERIMENT_REPORT_DRAFT = Path(
    "experiments/regression/manuscript/individual_experiment_report_draft.json"
)
STERILE_REPOSITORY_README_DRAFT = Path(
    "experiments/regression/manuscript/sterile_repository_readme_draft.json"
)
RESEARCH_DOCUMENT = Path("experiments/regression/manuscript/research_document.json")
PRIVATE_STERILE_PUBLICATION_PACKAGE = Path(
    "experiments/regression/manuscript/private_sterile_publication_package_manifest.json"
)
PRIVATE_LATEX_HTML_REVIEW_OUTPUT_AUDIT = Path(
    "experiments/regression/manuscript/private_latex_html_review_output_audit.json"
)

SOURCE_PATHS = {
    "claim_safe_result_extraction_matrix": CLAIM_SAFE_MATRIX,
    "manuscript_section_evidence_packet": SECTION_PACKET,
    "section_claim_boundary_audit": SECTION_BOUNDARY,
    "article_supplement_kg_navigation_index": NAVIGATION_INDEX,
    "final_publication_output_authorization_protocol": FINAL_AUTHORIZATION,
    "scientific_neutrality_interpretation_lock": SCIENTIFIC_NEUTRALITY,
    "publication_release_gap_register": RELEASE_GAP,
    "neutral_reporting_language_audit": NEUTRAL_LANGUAGE,
    "knowledge_graph_quality_summary": KG_QUALITY,
    "publication_citation_registry": PUBLICATION_CITATION_REGISTRY,
    "main_article_draft": MAIN_ARTICLE_DRAFT,
    "supplementary_document_draft": SUPPLEMENTARY_DOCUMENT_DRAFT,
    "individual_experiment_report_draft": INDIVIDUAL_EXPERIMENT_REPORT_DRAFT,
    "sterile_repository_readme_draft": STERILE_REPOSITORY_README_DRAFT,
    "research_document": RESEARCH_DOCUMENT,
    "private_sterile_publication_package_manifest": (
        PRIVATE_STERILE_PUBLICATION_PACKAGE
    ),
    "private_latex_html_review_output_audit": PRIVATE_LATEX_HTML_REVIEW_OUTPUT_AUDIT,
}

CURRENT_DRAFT_ARTIFACTS = (
    {
        "artifact_id": "main_article_draft",
        "target_document": "main_article",
        "expected_overall_status": "main_article_draft_ready",
        "required_source_keys": (
            "article_supplement_blueprint_alignment",
            "individual_experiment_report_draft",
            "knowledge_graph_quality_summary",
            "manuscript_section_evidence_packet",
            "publication_citation_registry",
            "publication_claim_evidence_verification_matrix",
            "section_claim_boundary_audit",
        ),
    },
    {
        "artifact_id": "supplementary_document_draft",
        "target_document": "supplementary_document",
        "expected_overall_status": "supplementary_document_draft_ready",
        "required_source_keys": (
            "article_supplement_blueprint_alignment",
            "individual_experiment_report_draft",
            "knowledge_graph_quality_summary",
            "main_article_draft",
            "publication_citation_registry",
        ),
    },
    {
        "artifact_id": "individual_experiment_report_draft",
        "target_document": "individual_experiment_report",
        "expected_overall_status": "individual_experiment_report_draft_ready",
        "required_source_keys": (
            "knowledge_graph_quality_summary",
            "publication_citation_registry",
            "publication_release_gap_register",
            "reader_primer_section_alignment",
        ),
    },
    {
        "artifact_id": "publication_citation_registry",
        "target_document": "bibliography_metadata",
        "expected_overall_status": "publication_citation_registry_ready_no_final_prose",
        "required_source_keys": (
            "method_literature_coverage_audit",
            "reader_method_primer_citation_map",
        ),
    },
    {
        "artifact_id": "sterile_repository_readme_draft",
        "target_document": "sterile_repository_readme",
        "expected_overall_status": "sterile_repository_readme_draft_ready",
        "required_source_keys": (
            "final_publication_output_authorization_protocol",
            "individual_experiment_report_draft",
            "knowledge_graph_quality_summary",
            "main_article_draft",
            "publication_citation_registry",
            "private_latex_html_review_output_audit",
            "private_sterile_publication_package_manifest",
            "sterile_repository_staging_manifest",
            "supplementary_document_draft",
        ),
    },
    {
        "artifact_id": "research_document",
        "target_document": "research_document",
        "expected_overall_status": "research_document_private_authoring_ready",
        "required_source_keys": (
            "individual_experiment_report_draft",
            "knowledge_graph_quality_summary",
            "main_article_draft",
            "private_sterile_publication_package_manifest",
            "publication_authoring_decision_record",
            "publication_citation_registry",
            "publication_claim_evidence_verification_matrix",
            "supplementary_document_draft",
        ),
    },
)

FINAL_AUTHORIZATION_FIELDS = (
    "final_section_prose_authorized",
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

CLAIM_REVIEW_PROFILES = {
    "paper_dataset_scope_evidence": {
        "claim_type": "scope_claim",
        "reviewed_claim": (
            "The manuscript may describe audited dataset/source scope as "
            "evidence for what was examined."
        ),
        "required_support_types": (
            "internal_audit_artifacts",
            "citation_registry_for_dataset_sources",
            "kg_navigation_trace",
            "explicit_boundary",
        ),
        "citation_gate": (
            "Dataset/source descriptions need source citations before final prose; "
            "the matrix does not certify exhaustive internet coverage."
        ),
        "allowed_publication_sentence": (
            "The dataset/source audit defines the studied scope under the recorded "
            "review policy."
        ),
        "non_specialist_explanation": (
            "This row tells a reader what data sources were inspected; it does not "
            "turn the dataset list into a final result."
        ),
    },
    "paper_method_scope_evidence": {
        "claim_type": "descriptive_empirical_claim",
        "reviewed_claim": (
            "The manuscript may report method-scope and observed frontier evidence, "
            "including CQR/CV+ as experiment-scoped practical candidates."
        ),
        "required_support_types": (
            "internal_result_synthesis",
            "method_literature_citations",
            "kg_navigation_trace",
            "explicit_boundary",
        ),
        "citation_gate": (
            "Method descriptions need literature citations; empirical language must "
            "stay limited to these experiments."
        ),
        "allowed_publication_sentence": (
            "CQR/CV+ were observed as strong practical candidates in these "
            "experiments."
        ),
        "non_specialist_explanation": (
            "This row permits a careful description of what looked useful in the "
            "experiment, not a recommendation for every regression problem."
        ),
    },
    "paper_main_results_blocked_evidence": {
        "claim_type": "blocked_positive_claim",
        "reviewed_claim": (
            "The manuscript may state that positive main-result promotion is "
            "blocked in the current evidence state."
        ),
        "required_support_types": (
            "claim_boundary_audit",
            "release_gap_register",
            "kg_navigation_trace",
            "explicit_boundary",
        ),
        "citation_gate": (
            "No citation can open this claim; it needs a later release/selection "
            "authorization if the scientific state changes."
        ),
        "allowed_publication_sentence": (
            "The current evidence does not authorize a final method selection, final main "
            "result, or deployment recommendation."
        ),
        "non_specialist_explanation": (
            "This row prevents a reader from mistaking promising diagnostic "
            "patterns for a final answer."
        ),
    },
    "supplement_robustness_diagnostic_evidence": {
        "claim_type": "caveated_diagnostic_claim",
        "reviewed_claim": (
            "The supplement may report robustness and post-selection diagnostic "
            "evidence when multiplicity caveats travel with it."
        ),
        "required_support_types": (
            "internal_audit_artifacts",
            "retention_readiness_audit",
            "kg_navigation_trace",
            "explicit_boundary",
        ),
        "citation_gate": (
            "Statistical or robustness interpretations need the documented audit "
            "context; they are not confirmatory superiority claims."
        ),
        "allowed_publication_sentence": (
            "Robustness rows are post-selection diagnostics and should be read with "
            "their multiplicity caveats."
        ),
        "non_specialist_explanation": (
            "This row says the extra checks are useful diagnostics, not proof that "
            "one method is definitively better."
        ),
    },
    "supplement_venn_abers_negative_evidence": {
        "claim_type": "negative_failure_mode_claim",
        "reviewed_claim": (
            "The supplement may report the evaluated fast Venn-Abers regression "
            "bridge as negative/failure-mode evidence."
        ),
        "required_support_types": (
            "venn_abers_negative_disposition_audit",
            "neutral_language_audit",
            "kg_navigation_trace",
            "explicit_boundary",
        ),
        "citation_gate": (
            "The claim is bridge-specific negative evidence; it must not be written "
            "as a rejection of the broader Venn-Abers literature."
        ),
        "allowed_publication_sentence": (
            "In these experiments, the evaluated fast Venn-Abers regression bridge "
            "did not validate as the expected strong regression interval solution."
        ),
        "non_specialist_explanation": (
            "This row records that one tested bridge behaved poorly; it does not "
            "say every Venn-Abers idea is wrong."
        ),
    },
    "supplement_methodology_controls_evidence": {
        "claim_type": "methodology_control_claim",
        "reviewed_claim": (
            "The supplement may describe audit controls as reproducibility and "
            "methodology infrastructure."
        ),
        "required_support_types": (
            "control_audit_artifacts",
            "neutral_language_audit",
            "kg_navigation_trace",
            "explicit_boundary",
        ),
        "citation_gate": (
            "Control descriptions can support reproducibility claims only; they do "
            "not establish scientific validity by themselves."
        ),
        "allowed_publication_sentence": (
            "The study includes audit controls for traceability, neutrality, and "
            "reproducibility."
        ),
        "non_specialist_explanation": (
            "This row explains the guardrails around the study rather than claiming "
            "the guardrails make every result final."
        ),
    },
    "supplement_reproducibility_traceability_evidence": {
        "claim_type": "reproducibility_traceability_claim",
        "reviewed_claim": (
            "The supplement may report completed-row accounting, resume controls, "
            "and KG traceability."
        ),
        "required_support_types": (
            "experiment_accounting_audit",
            "kg_quality_audit",
            "release_gap_register",
            "explicit_boundary",
        ),
        "citation_gate": (
            "The working repository is evidence infrastructure; it is not yet the "
            "final public citable repository."
        ),
        "allowed_publication_sentence": (
            "The private package records completed-row accounting, resume-safety "
            "controls, and knowledge-graph traceability."
        ),
        "non_specialist_explanation": (
            "This row tells a reader how the work can be audited and resumed, not "
            "that the current repository is the final released artifact."
        ),
    },
    "individual_report_blueprint_evidence": {
        "claim_type": "authoring_blueprint_claim",
        "reviewed_claim": (
            "The approved author header and individual-report section map may be "
            "reused as a private review blueprint."
        ),
        "required_support_types": (
            "individual_report_blueprint",
            "release_gap_register",
            "kg_navigation_trace",
            "explicit_boundary",
        ),
        "citation_gate": (
            "This is an authoring blueprint, not a final report or citable output."
        ),
        "allowed_publication_sentence": (
            "The individual report blueprint records the author-stamped section map "
            "for later review."
        ),
        "non_specialist_explanation": (
            "This row preserves the report plan and author metadata without "
            "pretending the final report is finished."
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


def rows_by_key(
    payload: dict[str, Any], key: str, id_field: str
) -> dict[str, dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get(id_field)): row
        for row in rows
        if isinstance(row, dict) and row.get(id_field)
    }


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


def authorization_violations(payloads: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for source_name, payload in payloads.items():
        source_summary = summary(payload)
        for field in FINAL_AUTHORIZATION_FIELDS:
            if source_summary.get(field) is True:
                violations.append({"source": source_name, "field": field})
    return violations


def row_authorization_violations(row: dict[str, Any]) -> list[str]:
    return [field for field in FINAL_AUTHORIZATION_FIELDS if row.get(field) is True]


def check_row(
    check_id: str, passed: bool, evidence: dict[str, Any], blocker: str
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "blocker": blocker,
    }


def build_verification_rows(
    claim_safe: dict[str, Any],
    section_packet: dict[str, Any],
    section_boundary: dict[str, Any],
    navigation_index: dict[str, Any],
) -> list[dict[str, Any]]:
    surfaces = rows_by_key(claim_safe, "surface_rows", "surface_id")
    packets = section_packet.get("section_packet_rows") or []
    boundaries = rows_by_key(section_boundary, "boundary_rows", "packet_id")
    navigation = rows_by_key(navigation_index, "navigation_rows", "navigation_id")

    rows: list[dict[str, Any]] = []
    for index, packet in enumerate(packets):
        if not isinstance(packet, dict):
            continue
        packet_id = str(packet.get("packet_id") or "").strip()
        surface_id = str(packet.get("claim_safe_surface_id") or "").strip()
        boundary = boundaries.get(packet_id, {})
        nav = navigation.get(packet_id, {})
        surface = surfaces.get(surface_id, {})
        auth_hits = sorted(
            set(row_authorization_violations(packet))
            | set(row_authorization_violations(boundary))
            | set(row_authorization_violations(nav))
            | set(row_authorization_violations(surface))
        )
        source_artifacts = sorted(
            set(str(path) for path in packet.get("source_artifacts") or [])
            | set(str(path) for path in surface.get("source_artifacts") or [])
        )
        missing_sources = sorted(
            str(path)
            for path in (
                packet.get("missing_source_artifacts")
                or surface.get("missing_source_artifacts")
                or []
            )
        )
        rows.append(
            {
                "verification_id": packet_id,
                "packet_id": packet_id,
                "row_index": index,
                "target_document": packet.get("target_document"),
                "claim_safe_surface_id": surface_id,
                "surface_linked": bool(surface),
                "boundary_linked": bool(boundary),
                "navigation_linked": bool(nav),
                "surface_status": surface.get("pre_prose_extraction_status"),
                "packet_status": packet.get("packet_status"),
                "boundary_status": boundary.get("boundary_status"),
                "navigation_family": nav.get("navigation_family"),
                "reader_navigation_role": nav.get("reader_navigation_role"),
                "allowed_use": packet.get("allowed_use") or boundary.get("allowed_use"),
                "blocked_use": packet.get("blocked_use") or boundary.get("blocked_use"),
                "allowed_language": surface.get("allowed_language") or [],
                "disallowed_language": surface.get("disallowed_language") or [],
                "neutral_result_ids": packet.get("neutral_result_ids") or [],
                "release_target_deliverable_ids": (
                    nav.get("release_target_deliverable_ids")
                    or boundary.get("release_target_deliverable_ids")
                    or []
                ),
                "kg_reference_node_ids": nav.get("kg_reference_node_ids") or [],
                "missing_kg_reference_node_ids": (
                    nav.get("missing_kg_reference_node_ids") or []
                ),
                "source_artifacts": source_artifacts,
                "missing_source_artifacts": missing_sources,
                "source_traceability_status": (
                    "pass"
                    if not missing_sources
                    and packet.get("source_traceability_status") == "pass"
                    else "fail"
                ),
                "boundary_complete": bool(boundary.get("boundary_complete")),
                "claim_safe_surface_consistent": (
                    bool(boundary.get("claim_safe_surface_consistent"))
                    if boundary
                    else False
                ),
                "release_targets_blocked": bool(boundary.get("release_targets_blocked"))
                and safe_int(nav.get("release_authorized_target_count")) == 0,
                "safe_pre_prose_evidence_packet": bool(
                    packet.get("safe_pre_prose_evidence_packet")
                ),
                "positive_claim_packet_blocked": bool(
                    packet.get("positive_claim_packet_blocked")
                ),
                "main_results_positive_boundary_blocked": bool(
                    boundary.get("main_positive_boundary_blocked")
                    or nav.get("main_results_positive_boundary_blocked")
                ),
                "venn_abers_negative_boundary_preserved": bool(
                    boundary.get("venn_abers_negative_boundary_preserved")
                    or nav.get("venn_abers_negative_boundary_preserved")
                ),
                "authorization_violations": auth_hits,
                "verification_status": (
                    "pass"
                    if bool(surface)
                    and bool(boundary)
                    and bool(nav)
                    and packet.get("source_traceability_status") == "pass"
                    and not missing_sources
                    and not auth_hits
                    and not (nav.get("missing_kg_reference_node_ids") or [])
                    else "fail"
                ),
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "latex_html_authoring_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "positive_claim_promotion_authorized": False,
                "claim_boundary": (
                    "Verification row is pre-prose evidence control only; it "
                    "does not authorize final article prose, final retained "
                    "visuals/tables, release, method recommendation, method "
                    "advocacy, or positive-claim promotion."
                ),
            }
        )
    return rows


def build_claim_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claim_review_rows: list[dict[str, Any]] = []
    for row in rows:
        verification_id = str(row.get("verification_id") or "")
        profile = CLAIM_REVIEW_PROFILES.get(verification_id, {})
        source_artifacts = [str(value) for value in row.get("source_artifacts") or []]
        kg_reference_node_ids = [
            str(value) for value in row.get("kg_reference_node_ids") or []
        ]
        required_support_types = [
            str(value) for value in profile.get("required_support_types") or []
        ]
        overclaim_blocked = str(row.get("blocked_use") or "").strip()
        allowed_sentence = str(profile.get("allowed_publication_sentence") or "").strip()
        citation_gate = str(profile.get("citation_gate") or "").strip()
        supported = (
            bool(profile)
            and bool(source_artifacts)
            and bool(kg_reference_node_ids)
            and bool(required_support_types)
            and bool(allowed_sentence)
            and bool(citation_gate)
            and bool(overclaim_blocked)
            and row.get("verification_status") == "pass"
            and not row.get("authorization_violations")
            and not row.get("missing_source_artifacts")
            and not row.get("missing_kg_reference_node_ids")
        )
        claim_review_rows.append(
            {
                "claim_review_id": verification_id,
                "row_index": row.get("row_index"),
                "target_document": row.get("target_document"),
                "claim_safe_surface_id": row.get("claim_safe_surface_id"),
                "claim_type": profile.get("claim_type"),
                "reviewed_claim": profile.get("reviewed_claim"),
                "allowed_publication_sentence": allowed_sentence,
                "overclaim_blocked": overclaim_blocked,
                "citation_gate": citation_gate,
                "required_support_types": required_support_types,
                "source_artifact_count": len(source_artifacts),
                "kg_reference_node_count": len(kg_reference_node_ids),
                "required_support_type_count": len(required_support_types),
                "support_status": (
                    "supported_with_internal_artifacts_boundaries_and_kg_trace"
                    if supported
                    else "claim_review_support_incomplete"
                ),
                "citation_status": (
                    "citation_or_source_gate_recorded"
                    if citation_gate
                    else "citation_or_source_gate_missing"
                ),
                "boundary_status": row.get("boundary_status"),
                "reader_navigation_role": row.get("reader_navigation_role"),
                "non_specialist_explanation": profile.get(
                    "non_specialist_explanation"
                ),
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
                "final_manuscript_prose_permission": False,
                "claim_review_status": "pass" if supported else "fail",
            }
        )
    return claim_review_rows


def build_draft_artifact_rows(
    root: Path, payloads: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, spec in enumerate(CURRENT_DRAFT_ARTIFACTS):
        artifact_id = str(spec["artifact_id"])
        artifact_path = SOURCE_PATHS[artifact_id]
        md_path = artifact_path.with_suffix(".md")
        payload = payloads.get(artifact_id) or {}
        artifact_summary = summary(payload)
        sources = payload.get("sources") if isinstance(payload, dict) else {}
        sources = sources if isinstance(sources, dict) else {}
        required_source_keys = tuple(str(key) for key in spec["required_source_keys"])
        missing_required_source_keys = sorted(
            key for key in required_source_keys if key not in sources
        )
        artifact_exists = (root / artifact_path).exists()
        markdown_exists = (root / md_path).exists()
        authorization_hits = sorted(
            field
            for field in FINAL_AUTHORIZATION_FIELDS
            if artifact_summary.get(field) is True
        )
        failed_check_count = safe_int(artifact_summary.get("failed_check_count"))
        draft_not_final = artifact_summary.get("draft_not_final")
        draft_flag_ok = draft_not_final is not False
        overall_status_matches = (
            artifact_summary.get("overall_status")
            == spec["expected_overall_status"]
        )
        source_traceability_status = (
            "pass" if not missing_required_source_keys else "fail"
        )
        verification_status = (
            "pass"
            if artifact_exists
            and markdown_exists
            and overall_status_matches
            and source_traceability_status == "pass"
            and failed_check_count == 0
            and not authorization_hits
            and draft_flag_ok
            else "fail"
        )
        rows.append(
            {
                "artifact_id": artifact_id,
                "row_index": index,
                "target_document": spec["target_document"],
                "artifact_json_path": rel(root / artifact_path, root),
                "artifact_markdown_path": rel(root / md_path, root),
                "artifact_exists": artifact_exists,
                "markdown_exists": markdown_exists,
                "overall_status": artifact_summary.get("overall_status"),
                "expected_overall_status": spec["expected_overall_status"],
                "overall_status_matches": overall_status_matches,
                "draft_not_final": draft_not_final,
                "draft_flag_ok": draft_flag_ok,
                "failed_check_count": failed_check_count,
                "required_source_keys": list(required_source_keys),
                "missing_required_source_keys": missing_required_source_keys,
                "source_traceability_status": source_traceability_status,
                "authorization_violations": authorization_hits,
                "verification_status": verification_status,
                "final_manuscript_prose_permission": False,
                "final_visual_table_retention_authorized": False,
                "latex_html_authoring_authorized": False,
                "publication_site_deployment_authorized": False,
                "kg_citable_component_authorized": False,
                "sterile_repository_creation_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "positive_claim_promotion_authorized": False,
                "claim_boundary": (
                    "Current publication draft artifact is covered by the "
                    "claim/evidence matrix as a draft-only source. It remains "
                    "non-final and does not authorize final prose, release, "
                    "method recommendation, or positive-claim promotion."
                ),
            }
        )
    return rows


def build_private_review_surface_rows(
    payloads: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    package_payload = payloads.get("private_sterile_publication_package_manifest") or {}
    source_rows = package_payload.get("generated_review_surface_rows")
    if not isinstance(source_rows, list):
        return []
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(source_rows):
        if not isinstance(row, dict):
            continue
        authorization_hits = sorted(
            field for field in FINAL_AUTHORIZATION_FIELDS if row.get(field) is True
        )
        missing_required_phrases = [
            str(value) for value in row.get("missing_required_phrases") or []
        ]
        exists = bool(row.get("exists"))
        verification_status = (
            "pass"
            if exists
            and row.get("verification_status") == "pass"
            and not missing_required_phrases
            and not authorization_hits
            else "fail"
        )
        rows.append(
            {
                "surface_id": str(row.get("surface_id") or f"surface_{index}"),
                "row_index": index,
                "package_path": row.get("package_path"),
                "exists": exists,
                "bytes": row.get("bytes"),
                "sha256": row.get("sha256"),
                "required_phrases": row.get("required_phrases") or [],
                "missing_required_phrases": missing_required_phrases,
                "source_verification_status": row.get("verification_status"),
                "authorization_violations": authorization_hits,
                "verification_status": verification_status,
                "public_release_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "positive_claim_promotion_authorized": False,
                "claim_boundary": (
                    "Private review package surface is included only for user "
                    "review traceability. It does not authorize public release, "
                    "final citable status, method recommendation, method "
                    "advocacy, or positive-claim promotion."
                ),
            }
        )
    return rows


def build_payload(root: Path) -> dict[str, Any]:
    payloads = {name: read_json(root / path) for name, path in SOURCE_PATHS.items()}
    claim_safe = payloads["claim_safe_result_extraction_matrix"]
    section_packet = payloads["manuscript_section_evidence_packet"]
    section_boundary = payloads["section_claim_boundary_audit"]
    navigation_index = payloads["article_supplement_kg_navigation_index"]
    final_authorization = payloads["final_publication_output_authorization_protocol"]
    scientific_neutrality = payloads["scientific_neutrality_interpretation_lock"]
    release_gap = payloads["publication_release_gap_register"]
    neutral_language = payloads["neutral_reporting_language_audit"]
    kg_quality = payloads["knowledge_graph_quality_summary"]

    present_sources, missing_sources = source_status(root)
    rows = build_verification_rows(
        claim_safe, section_packet, section_boundary, navigation_index
    )
    claim_review_rows = build_claim_review_rows(rows)
    draft_rows = build_draft_artifact_rows(root, payloads)
    private_review_surface_rows = build_private_review_surface_rows(payloads)
    target_counts = Counter(str(row.get("target_document")) for row in rows)
    status_counts = Counter(str(row.get("verification_status")) for row in rows)
    packet_status_counts = Counter(str(row.get("packet_status")) for row in rows)
    claim_review_status_counts = Counter(
        str(row.get("claim_review_status")) for row in claim_review_rows
    )
    draft_status_counts = Counter(
        str(row.get("verification_status")) for row in draft_rows
    )
    row_auth_violations = [
        {"verification_id": row["verification_id"], "fields": row["authorization_violations"]}
        for row in rows
        if row.get("authorization_violations")
    ]
    source_traceable_count = sum(
        row.get("source_traceability_status") == "pass" for row in rows
    )
    boundary_aligned_count = sum(
        row.get("boundary_linked")
        and row.get("boundary_complete")
        and row.get("claim_safe_surface_consistent")
        for row in rows
    )
    navigation_aligned_count = sum(
        row.get("navigation_linked")
        and not row.get("missing_kg_reference_node_ids")
        for row in rows
    )
    kg_reference_issue_count = sum(
        len(row.get("missing_kg_reference_node_ids") or []) for row in rows
    )
    safe_pre_prose_count = sum(row.get("safe_pre_prose_evidence_packet") for row in rows)
    blocked_positive_count = sum(row.get("positive_claim_packet_blocked") for row in rows)
    main_blocked_count = sum(
        row.get("verification_id") == "paper_main_results_blocked_evidence"
        and row.get("positive_claim_packet_blocked")
        and row.get("main_results_positive_boundary_blocked")
        for row in rows
    )
    negative_ready_count = sum(
        row.get("verification_id") == "supplement_venn_abers_negative_evidence"
        and row.get("safe_pre_prose_evidence_packet")
        and row.get("venn_abers_negative_boundary_preserved")
        for row in rows
    )
    source_auth_violations = authorization_violations(payloads)
    draft_traceable_count = sum(
        row.get("source_traceability_status") == "pass" for row in draft_rows
    )
    draft_missing_source_key_count = sum(
        len(row.get("missing_required_source_keys") or []) for row in draft_rows
    )
    draft_missing_artifact_count = sum(
        (not row.get("artifact_exists")) + (not row.get("markdown_exists"))
        for row in draft_rows
    )
    draft_authorization_violation_count = sum(
        len(row.get("authorization_violations") or []) for row in draft_rows
    )
    draft_failed_upstream_check_count = sum(
        safe_int(row.get("failed_check_count")) for row in draft_rows
    )
    private_review_surface_pass_count = sum(
        row.get("verification_status") == "pass" for row in private_review_surface_rows
    )
    private_review_surface_missing_count = sum(
        not row.get("exists") for row in private_review_surface_rows
    )
    private_review_surface_phrase_issue_count = sum(
        len(row.get("missing_required_phrases") or [])
        for row in private_review_surface_rows
    )
    private_review_surface_authorization_violation_count = sum(
        len(row.get("authorization_violations") or [])
        for row in private_review_surface_rows
    )
    claim_review_supported_count = sum(
        row.get("claim_review_status") == "pass" for row in claim_review_rows
    )
    claim_review_citation_gate_count = sum(
        row.get("citation_status") == "citation_or_source_gate_recorded"
        for row in claim_review_rows
    )
    claim_review_overclaim_blocked_count = sum(
        bool(row.get("overclaim_blocked")) for row in claim_review_rows
    )
    claim_review_non_specialist_explanation_count = sum(
        bool(row.get("non_specialist_explanation")) for row in claim_review_rows
    )
    expected_draft_artifact_count = len(CURRENT_DRAFT_ARTIFACTS)

    claim_safe_summary = summary(claim_safe)
    packet_summary = summary(section_packet)
    boundary_summary = summary(section_boundary)
    nav_summary = summary(navigation_index)
    final_summary = summary(final_authorization)
    neutrality_summary = summary(scientific_neutrality)
    release_summary = summary(release_gap)
    private_package_summary = summary(
        payloads["private_sterile_publication_package_manifest"]
    )
    expected_private_review_surface_count = safe_int(
        private_package_summary.get("generated_review_surface_count")
    )
    if expected_private_review_surface_count == 0:
        expected_private_review_surface_count = len(private_review_surface_rows)
    neutral_language_summary = summary(neutral_language)
    kg_graph = kg_quality.get("graph") or {}

    checks = [
        check_row(
            "source_artifacts_present",
            not missing_sources,
            {
                "source_artifact_count": len(present_sources),
                "missing_source_artifacts": missing_sources,
            },
            "missing_publication_claim_verification_source",
        ),
        check_row(
            "verification_rows_complete",
            len(rows) == 8
            and status_counts.get("pass", 0) == 8
            and source_traceable_count == 8,
            {
                "verification_row_count": len(rows),
                "status_counts": dict(status_counts),
                "source_traceable_count": source_traceable_count,
            },
            "publication_claim_verification_rows_incomplete",
        ),
        check_row(
            "upstream_claim_boundary_sources_clean",
            claim_safe_summary.get("overall_status")
            == "claim_safe_result_extraction_matrix_ready_no_final_claims"
            and packet_summary.get("overall_status")
            == "manuscript_section_evidence_packet_ready_no_final_prose"
            and boundary_summary.get("overall_status")
            == "section_claim_boundary_audit_pass_no_final_claims"
            and nav_summary.get("overall_status")
            == "article_supplement_kg_navigation_index_ready_no_release",
            {
                "claim_safe_status": claim_safe_summary.get("overall_status"),
                "section_packet_status": packet_summary.get("overall_status"),
                "boundary_status": boundary_summary.get("overall_status"),
                "navigation_status": nav_summary.get("overall_status"),
            },
            "upstream_claim_boundary_source_not_clean",
        ),
        check_row(
            "boundary_navigation_alignment_clean",
            boundary_aligned_count == 8
            and navigation_aligned_count == 8
            and kg_reference_issue_count == 0,
            {
                "boundary_aligned_count": boundary_aligned_count,
                "navigation_aligned_count": navigation_aligned_count,
                "kg_reference_issue_count": kg_reference_issue_count,
            },
            "boundary_or_navigation_alignment_issue",
        ),
        check_row(
            "blocked_and_negative_claim_roles_preserved",
            safe_pre_prose_count == 7
            and blocked_positive_count == 1
            and main_blocked_count == 1
            and negative_ready_count == 1,
            {
                "safe_pre_prose_count": safe_pre_prose_count,
                "blocked_positive_count": blocked_positive_count,
                "main_blocked_count": main_blocked_count,
                "negative_ready_count": negative_ready_count,
                "packet_status_counts": dict(packet_status_counts),
            },
            "blocked_or_negative_claim_role_changed",
        ),
        check_row(
            "claim_reviewer_rows_complete",
            len(claim_review_rows) == len(rows)
            and claim_review_supported_count == len(rows)
            and claim_review_citation_gate_count == len(rows)
            and claim_review_overclaim_blocked_count == len(rows)
            and claim_review_non_specialist_explanation_count == len(rows),
            {
                "claim_review_row_count": len(claim_review_rows),
                "claim_review_supported_count": claim_review_supported_count,
                "claim_review_status_counts": dict(claim_review_status_counts),
                "claim_review_citation_gate_count": (
                    claim_review_citation_gate_count
                ),
                "claim_review_overclaim_blocked_count": (
                    claim_review_overclaim_blocked_count
                ),
                "claim_review_non_specialist_explanation_count": (
                    claim_review_non_specialist_explanation_count
                ),
            },
            "claim_reviewer_row_support_or_boundary_missing",
        ),
        check_row(
            "analysis_only_no_champion_policy_preserved",
            final_summary.get("analysis_only_no_champion_method") is True
            and final_summary.get("method_champion_authorized") is False
            and final_summary.get("method_advocacy_authorized") is False
            and final_summary.get("method_recommendation_authorized") is False
            and final_summary.get("positive_claim_promotion_authorized") is False
            and neutrality_summary.get("analysis_only_no_champion_method") is True
            and neutrality_summary.get("result_reporting_policy")
            == "analysis_only_report_observed_behavior_no_method_advocacy",
            {
                "final_result_reporting_policy": final_summary.get(
                    "result_reporting_policy"
                ),
                "neutrality_result_reporting_policy": neutrality_summary.get(
                    "result_reporting_policy"
                ),
                "method_champion_authorized": final_summary.get(
                    "method_champion_authorized"
                ),
                "method_advocacy_authorized": final_summary.get(
                    "method_advocacy_authorized"
                ),
            },
            "analysis_only_no_champion_policy_not_preserved",
        ),
        check_row(
            "final_outputs_and_release_remain_blocked",
            not source_auth_violations
            and not row_auth_violations
            and final_summary.get("final_manuscript_prose_permission") is False
            and final_summary.get("final_visual_table_retention_authorized") is False
            and final_summary.get("latex_html_authoring_authorized") is False
            and release_summary.get("release_authorized_count") == 0
            and release_summary.get("working_repository_final_citable") is False,
            {
                "source_authorization_violations": source_auth_violations,
                "row_authorization_violations": row_auth_violations,
                "release_authorized_count": release_summary.get(
                    "release_authorized_count"
                ),
            },
            "final_output_or_release_authorized",
        ),
        check_row(
            "neutral_language_and_kg_ready_for_navigation",
            neutral_language_summary.get("overall_status")
            == "neutral_reporting_language_audit_pass"
            and safe_int(neutral_language_summary.get("unguarded_hit_count")) == 0
            and safe_int(kg_graph.get("isolated_node_count")) == 0
            and safe_int(kg_graph.get("node_count")) >= 3442,
            {
                "neutral_language_status": neutral_language_summary.get(
                    "overall_status"
                ),
                "unguarded_hit_count": neutral_language_summary.get(
                    "unguarded_hit_count"
                ),
                "kg_node_count": kg_graph.get("node_count"),
                "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
            },
            "neutral_language_or_kg_navigation_not_ready",
        ),
        check_row(
            "current_publication_draft_artifacts_claim_evidence_covered",
            len(draft_rows) == expected_draft_artifact_count
            and draft_status_counts.get("pass", 0) == expected_draft_artifact_count
            and draft_traceable_count == expected_draft_artifact_count
            and draft_missing_source_key_count == 0
            and draft_missing_artifact_count == 0
            and draft_authorization_violation_count == 0
            and draft_failed_upstream_check_count == 0,
            {
                "draft_artifact_count": len(draft_rows),
                "draft_status_counts": dict(draft_status_counts),
                "draft_traceable_count": draft_traceable_count,
                "draft_missing_source_key_count": draft_missing_source_key_count,
                "draft_missing_artifact_count": draft_missing_artifact_count,
                "draft_authorization_violation_count": (
                    draft_authorization_violation_count
                ),
                "draft_failed_upstream_check_count": (
                    draft_failed_upstream_check_count
                ),
            },
            "current_publication_draft_artifact_claim_evidence_gap",
        ),
        check_row(
            "private_review_package_surfaces_claim_evidence_covered",
            private_package_summary.get("overall_status")
            == "private_sterile_publication_package_ready"
            and len(private_review_surface_rows) == expected_private_review_surface_count
            and private_review_surface_pass_count == expected_private_review_surface_count
            and private_review_surface_missing_count == 0
            and private_review_surface_phrase_issue_count == 0
            and private_review_surface_authorization_violation_count == 0,
            {
                "private_package_status": private_package_summary.get(
                    "overall_status"
                ),
                "private_review_surface_count": len(private_review_surface_rows),
                "expected_private_review_surface_count": (
                    expected_private_review_surface_count
                ),
                "private_review_surface_pass_count": (
                    private_review_surface_pass_count
                ),
                "private_review_surface_missing_count": (
                    private_review_surface_missing_count
                ),
                "private_review_surface_phrase_issue_count": (
                    private_review_surface_phrase_issue_count
                ),
                "private_review_surface_authorization_violation_count": (
                    private_review_surface_authorization_violation_count
                ),
            },
            "private_review_package_surface_claim_evidence_gap",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    summary_payload = {
        "overall_status": (
            "publication_claim_evidence_verification_ready_no_final_prose"
            if not failed_checks
            else "publication_claim_evidence_verification_blocked"
        ),
        "phase_state": (
            "neutral_pre_prose_claim_evidence_verification_active_"
            "final_outputs_blocked"
        ),
        "verification_row_count": len(rows),
        "verification_pass_count": status_counts.get("pass", 0),
        "source_traceable_row_count": source_traceable_count,
        "boundary_aligned_row_count": boundary_aligned_count,
        "navigation_aligned_row_count": navigation_aligned_count,
        "kg_reference_issue_count": kg_reference_issue_count,
        "safe_pre_prose_evidence_row_count": safe_pre_prose_count,
        "blocked_positive_row_count": blocked_positive_count,
        "main_results_blocked_row_count": main_blocked_count,
        "venn_abers_negative_ready_row_count": negative_ready_count,
        "claim_review_row_count": len(claim_review_rows),
        "claim_review_supported_count": claim_review_supported_count,
        "claim_review_citation_gate_count": claim_review_citation_gate_count,
        "claim_review_overclaim_blocked_count": claim_review_overclaim_blocked_count,
        "claim_review_non_specialist_explanation_count": (
            claim_review_non_specialist_explanation_count
        ),
        "claim_review_status_counts": dict(sorted(claim_review_status_counts.items())),
        "target_document_counts": dict(sorted(target_counts.items())),
        "packet_status_counts": dict(sorted(packet_status_counts.items())),
        "source_artifact_count": len(present_sources),
        "missing_source_artifact_count": len(missing_sources),
        "source_authorization_violation_count": len(source_auth_violations),
        "row_authorization_violation_count": len(row_auth_violations),
        "final_manuscript_prose_permission": False,
        "final_visual_table_retention_authorized": False,
        "latex_html_authoring_authorized": False,
        "publication_site_deployment_authorized": False,
        "kg_citable_component_authorized": False,
        "sterile_repository_creation_authorized": False,
        "working_repository_final_citable": False,
        "release_authorized": False,
        "method_recommendation_authorized": False,
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "positive_claim_promotion_authorized": False,
        "analysis_only_no_champion_method": True,
        "result_reporting_policy": (
            "analysis_only_report_observed_behavior_no_method_advocacy"
        ),
        "neutral_language_unguarded_hit_count": neutral_language_summary.get(
            "unguarded_hit_count"
        ),
        "kg_node_count": kg_graph.get("node_count"),
        "kg_edge_count": kg_graph.get("edge_count"),
        "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
        "current_publication_draft_artifact_count": len(draft_rows),
        "current_publication_draft_artifact_pass_count": draft_status_counts.get(
            "pass", 0
        ),
        "current_publication_draft_artifact_traceable_count": draft_traceable_count,
        "current_publication_draft_missing_source_key_count": (
            draft_missing_source_key_count
        ),
        "current_publication_draft_missing_artifact_count": (
            draft_missing_artifact_count
        ),
        "current_publication_draft_authorization_violation_count": (
            draft_authorization_violation_count
        ),
        "current_publication_draft_failed_upstream_check_count": (
            draft_failed_upstream_check_count
        ),
        "current_publication_draft_status_counts": dict(
            sorted(draft_status_counts.items())
        ),
        "private_review_surface_count": len(private_review_surface_rows),
        "private_review_surface_pass_count": private_review_surface_pass_count,
        "private_review_surface_missing_count": private_review_surface_missing_count,
        "private_review_surface_phrase_issue_count": (
            private_review_surface_phrase_issue_count
        ),
        "private_review_surface_authorization_violation_count": (
            private_review_surface_authorization_violation_count
        ),
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
        "verification_rows": rows,
        "claim_review_rows": claim_review_rows,
        "current_publication_draft_artifact_rows": draft_rows,
        "private_review_surface_rows": private_review_surface_rows,
        "authorization_violations": {
            "source_authorization_violations": source_auth_violations,
            "row_authorization_violations": row_auth_violations,
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This matrix verifies evidence and claim boundaries only; it is not final manuscript prose.",
            "Main-result positive claims remain blocked while Venn-Abers negative evidence remains reportable as negative/failure-mode evidence.",
            "CQR/CV+ and all methods may be described only as observed diagnostic patterns under audited scope, never as champions or recommendations.",
            "Final prose, retained figures/tables, LaTeX/HTML outputs, KG/site release, sterile repository creation, and positive claims remain unauthorized.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Publication Claim Evidence Verification Matrix",
        "",
        "This pre-prose artifact verifies claim/evidence alignment. It does not write final prose, retain final visuals/tables, authorize release, recommend a method, or promote a positive claim.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Phase state: `{summary_payload['phase_state']}`",
        f"- Verification rows: {summary_payload['verification_row_count']}",
        f"- Verification pass rows: {summary_payload['verification_pass_count']}",
        f"- Boundary/navigation aligned rows: {summary_payload['boundary_aligned_row_count']} / {summary_payload['navigation_aligned_row_count']}",
        f"- KG reference issues: {summary_payload['kg_reference_issue_count']}",
        f"- Safe pre-prose rows: {summary_payload['safe_pre_prose_evidence_row_count']}",
        f"- Blocked positive rows: {summary_payload['blocked_positive_row_count']}",
        f"- Venn-Abers negative-ready rows: {summary_payload['venn_abers_negative_ready_row_count']}",
        f"- Claim-review supported rows: {summary_payload['claim_review_supported_count']} / {summary_payload['claim_review_row_count']}",
        f"- Claim-review citation/source gates: {summary_payload['claim_review_citation_gate_count']}",
        f"- Claim-review overclaim blocks: {summary_payload['claim_review_overclaim_blocked_count']}",
        f"- Claim-review non-specialist explanations: {summary_payload['claim_review_non_specialist_explanation_count']}",
        f"- Current draft artifacts covered: {summary_payload['current_publication_draft_artifact_pass_count']} / {summary_payload['current_publication_draft_artifact_count']}",
        f"- Private review surfaces covered: {summary_payload['private_review_surface_pass_count']} / {summary_payload['private_review_surface_count']}",
        f"- Private review surface phrase issues: {summary_payload['private_review_surface_phrase_issue_count']}",
        f"- Result reporting policy: `{summary_payload['result_reporting_policy']}`",
        f"- Method champion authorized: `{summary_payload['method_champion_authorized']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive-claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        f"- Failed checks: {summary_payload['failed_check_count']}",
        "",
        "## Verification Rows",
        "",
        "| Row | Target | Surface | Status | Boundary | Navigation | Blocked positive | Negative preserved |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["verification_rows"]:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                row["verification_id"],
                row["target_document"],
                row["claim_safe_surface_id"],
                row["verification_status"],
                row["boundary_linked"],
                row["navigation_linked"],
                row["positive_claim_packet_blocked"],
                row["venn_abers_negative_boundary_preserved"],
            )
        )
    lines.extend(
        [
            "",
            "## Claim Review Rows",
            "",
            (
                "These rows translate the verification matrix into writing rules: "
                "what can be claimed, what support must travel with the claim, "
                "and what overclaim remains blocked."
            ),
            "",
            "| Row | Type | Claim-review status | Allowed sentence | Citation/source gate | Overclaim blocked |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in payload["claim_review_rows"]:
        lines.append(
            "| `{}` | `{}` | `{}` | {} | {} | {} |".format(
                row["claim_review_id"],
                row["claim_type"],
                row["claim_review_status"],
                row["allowed_publication_sentence"],
                row["citation_gate"],
                row["overclaim_blocked"],
            )
        )
    lines.extend(
        [
            "",
            "## Current Draft Artifact Coverage",
            "",
            "| Artifact | Target | Status | Traceability | Missing source keys | Upstream failed checks |",
            "|---|---|---|---|---:|---:|",
        ]
    )
    for row in payload["current_publication_draft_artifact_rows"]:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                row["artifact_id"],
                row["target_document"],
                row["verification_status"],
                row["source_traceability_status"],
                len(row["missing_required_source_keys"]),
                row["failed_check_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Private Review Surface Coverage",
            "",
            "| Surface | Package path | Status | Missing phrases |",
            "|---|---|---|---:|",
        ]
    )
    for row in payload["private_review_surface_rows"]:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` |".format(
                row["surface_id"],
                row["package_path"],
                row["verification_status"],
                len(row["missing_required_phrases"]),
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Blocker |", "|---|---|---|"])
    for row in payload["checks"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['blocker']}` |")
    lines.extend(["", "## Boundaries", ""])
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
                "verification_row_count": payload["summary"][
                    "verification_row_count"
                ],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
