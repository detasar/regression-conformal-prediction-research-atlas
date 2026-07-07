"""Audit manuscript draft claim and citation readiness.

This audit is intentionally pre-final-prose. It checks that the current main
article and supplementary document drafts use registered citation keys, cover
their required reader-primer concepts with primary-source citations, and keep
all final-output and method-promotion authorizations closed.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_manuscript_claim_citation_readiness_audit_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/"
    "manuscript_claim_citation_readiness_audit.json"
)

MAIN_ARTICLE_JSON = Path("experiments/regression/manuscript/main_article_draft.json")
MAIN_ARTICLE_MD = Path("experiments/regression/manuscript/main_article_draft.md")
SUPPLEMENT_JSON = Path(
    "experiments/regression/manuscript/supplementary_document_draft.json"
)
SUPPLEMENT_MD = Path("experiments/regression/manuscript/supplementary_document_draft.md")
CITATION_REGISTRY = Path(
    "experiments/regression/manuscript/publication_citation_registry.json"
)
PRIMER_MAP = Path(
    "experiments/regression/manuscript/reader_method_primer_citation_map.json"
)
CLAIM_MATRIX = Path(
    "experiments/regression/manuscript/publication_claim_evidence_verification_matrix.json"
)
FINAL_AUTHORIZATION = Path(
    "experiments/regression/manuscript/"
    "final_publication_output_authorization_protocol.json"
)
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")

SOURCE_PATHS = {
    "main_article_draft": MAIN_ARTICLE_JSON,
    "main_article_markdown": MAIN_ARTICLE_MD,
    "supplementary_document_draft": SUPPLEMENT_JSON,
    "supplementary_document_markdown": SUPPLEMENT_MD,
    "publication_citation_registry": CITATION_REGISTRY,
    "reader_method_primer_citation_map": PRIMER_MAP,
    "publication_claim_evidence_verification_matrix": CLAIM_MATRIX,
    "final_publication_output_authorization_protocol": FINAL_AUTHORIZATION,
    "knowledge_graph_quality_summary": KG_QUALITY,
}

JSON_SOURCE_KEYS = (
    "main_article_draft",
    "supplementary_document_draft",
    "publication_citation_registry",
    "reader_method_primer_citation_map",
    "publication_claim_evidence_verification_matrix",
    "final_publication_output_authorization_protocol",
    "knowledge_graph_quality_summary",
)

DOCUMENT_SPECS = (
    {
        "document_id": "main_article_draft",
        "json_key": "main_article_draft",
        "markdown_key": "main_article_markdown",
        "expected_status": "main_article_draft_ready",
        "section_key": "article_sections",
        "required_concept_ids": (
            "conformal_prediction_regression",
            "alpha_and_nominal_coverage",
            "split_conformal_regression",
            "conformalized_quantile_regression_cqr",
            "jackknife_plus_and_cv_plus",
            "venn_abers_predictive_distributions",
            "result_metrics_and_claim_boundaries",
        ),
        "required_source_keys": (
            "individual_experiment_report_draft",
            "publication_citation_registry",
            "publication_claim_evidence_verification_matrix",
            "knowledge_graph_quality_summary",
        ),
    },
    {
        "document_id": "supplementary_document_draft",
        "json_key": "supplementary_document_draft",
        "markdown_key": "supplementary_document_markdown",
        "expected_status": "supplementary_document_draft_ready",
        "section_key": "supplement_sections",
        "required_concept_ids": (
            "conformal_prediction_regression",
            "alpha_and_nominal_coverage",
            "conformalized_quantile_regression_cqr",
            "jackknife_plus_and_cv_plus",
            "mondrian_and_group_calibration",
            "normalized_and_locally_adaptive_split",
            "weighted_conformal_covariate_shift",
            "venn_abers_predictive_distributions",
            "result_metrics_and_claim_boundaries",
        ),
        "required_source_keys": (
            "main_article_draft",
            "individual_experiment_report_draft",
            "publication_citation_registry",
            "knowledge_graph_quality_summary",
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

CITATION_RE = re.compile(r"(?<![A-Za-z0-9._%+-])@([A-Za-z0-9_:-]+)")
REFERENCE_RE = re.compile(r"^- `@([^`]+)`:", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary") if isinstance(payload, dict) else {}
    return value if isinstance(value, dict) else {}


def citation_keys_from_text(text: str) -> set[str]:
    return set(CITATION_RE.findall(text))


def reference_keys_from_text(text: str) -> set[str]:
    return set(REFERENCE_RE.findall(text))


def body_text_before_references(text: str) -> str:
    return text.split("\n## References", 1)[0]


def citation_registry_maps(
    registry: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    rows = registry.get("citation_rows") or []
    by_key = {
        str(row.get("citation_key")): row
        for row in rows
        if isinstance(row, dict) and row.get("citation_key")
    }
    key_by_url = {
        str(row.get("url")): str(row.get("citation_key"))
        for row in rows
        if isinstance(row, dict) and row.get("url") and row.get("citation_key")
    }
    return by_key, key_by_url


def primer_concept_sources(
    primer: dict[str, Any], key_by_url: dict[str, str]
) -> dict[str, set[str]]:
    concept_sources: dict[str, set[str]] = {}
    for row in primer.get("concept_rows") or []:
        if not isinstance(row, dict) or not row.get("concept_id"):
            continue
        keys = {
            key_by_url[url]
            for url in row.get("primary_source_urls") or []
            if url in key_by_url
        }
        concept_sources[str(row["concept_id"])] = keys
    return concept_sources


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


def row_authorization_violations(payload: dict[str, Any]) -> list[str]:
    doc_summary = summary(payload)
    return [field for field in FINAL_AUTHORIZATION_FIELDS if doc_summary.get(field) is True]


def build_document_rows(
    root: Path,
    payloads: dict[str, dict[str, Any]],
    texts: dict[str, str],
    registry_by_key: dict[str, dict[str, Any]],
    concept_sources: dict[str, set[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, spec in enumerate(DOCUMENT_SPECS):
        document_id = str(spec["document_id"])
        payload = payloads[str(spec["json_key"])]
        doc_summary = summary(payload)
        text = texts[str(spec["markdown_key"])]
        body_text = body_text_before_references(text)
        used_keys = sorted(citation_keys_from_text(body_text))
        reference_keys = sorted(reference_keys_from_text(text))
        registered_used_keys = sorted(key for key in used_keys if key in registry_by_key)
        unregistered_used_keys = sorted(set(used_keys) - set(registry_by_key))
        missing_reference_keys = sorted(set(used_keys) - set(reference_keys))
        unused_reference_keys = sorted(set(reference_keys) - set(used_keys))
        bibtex_missing_keys = sorted(
            key for key in used_keys if not registry_by_key.get(key, {}).get("bibtex")
        )
        metadata_incomplete_keys = sorted(
            key
            for key in used_keys
            if not (
                registry_by_key.get(key, {}).get("url")
                or registry_by_key.get(key, {}).get("doi")
                or registry_by_key.get(key, {}).get("eprint")
            )
        )
        missing_concepts: list[str] = []
        concept_rows: list[dict[str, Any]] = []
        used_key_set = set(used_keys)
        for concept_id in spec["required_concept_ids"]:
            candidate_keys = concept_sources.get(str(concept_id), set())
            covered_keys = sorted(candidate_keys & used_key_set)
            if not covered_keys:
                missing_concepts.append(str(concept_id))
            concept_rows.append(
                {
                    "concept_id": str(concept_id),
                    "candidate_citation_keys": sorted(candidate_keys),
                    "covered_citation_keys": covered_keys,
                    "coverage_status": "pass" if covered_keys else "fail",
                }
            )
        sources = payload.get("sources") if isinstance(payload, dict) else {}
        sources = sources if isinstance(sources, dict) else {}
        missing_required_source_keys = sorted(
            key for key in spec["required_source_keys"] if key not in sources
        )
        markdown_path = SOURCE_PATHS[str(spec["markdown_key"])]
        json_path = SOURCE_PATHS[str(spec["json_key"])]
        authorization_violations = row_authorization_violations(payload)
        checks_pass = (
            (root / markdown_path).exists()
            and (root / json_path).exists()
            and doc_summary.get("overall_status") == spec["expected_status"]
            and doc_summary.get("failed_check_count") == 0
            and not unregistered_used_keys
            and not missing_reference_keys
            and not bibtex_missing_keys
            and not metadata_incomplete_keys
            and not missing_concepts
            and not missing_required_source_keys
            and not authorization_violations
        )
        rows.append(
            {
                "document_id": document_id,
                "row_index": index,
                "markdown_path": rel(root / markdown_path, root),
                "json_path": rel(root / json_path, root),
                "expected_overall_status": spec["expected_status"],
                "overall_status": doc_summary.get("overall_status"),
                "failed_check_count": doc_summary.get("failed_check_count"),
                "used_citation_keys": used_keys,
                "reference_keys": reference_keys,
                "registered_used_citation_keys": registered_used_keys,
                "unregistered_used_citation_keys": unregistered_used_keys,
                "missing_reference_keys": missing_reference_keys,
                "unused_reference_keys": unused_reference_keys,
                "bibtex_missing_keys": bibtex_missing_keys,
                "metadata_incomplete_keys": metadata_incomplete_keys,
                "required_concept_ids": list(spec["required_concept_ids"]),
                "concept_rows": concept_rows,
                "missing_concept_ids": missing_concepts,
                "required_source_keys": list(spec["required_source_keys"]),
                "missing_required_source_keys": missing_required_source_keys,
                "authorization_violations": authorization_violations,
                "final_manuscript_prose_permission": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "positive_claim_promotion_authorized": False,
                "readiness_status": "pass" if checks_pass else "fail",
                "claim_boundary": (
                    "This document row verifies draft claim/citation readiness "
                    "only. It does not authorize final manuscript prose, method "
                    "recommendation, method advocacy, release, or positive-claim "
                    "promotion."
                ),
            }
        )
    return rows


def check_row(check_id: str, passed: bool, evidence: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "blocker": blocker,
    }


def build_payload(root: Path) -> dict[str, Any]:
    payloads = {
        name: read_json(root / SOURCE_PATHS[name]) for name in JSON_SOURCE_KEYS
    }
    texts = {
        "main_article_markdown": read_text(root / MAIN_ARTICLE_MD),
        "supplementary_document_markdown": read_text(root / SUPPLEMENT_MD),
    }
    registry = payloads["publication_citation_registry"]
    primer = payloads["reader_method_primer_citation_map"]
    claim_matrix = payloads["publication_claim_evidence_verification_matrix"]
    final_auth = payloads["final_publication_output_authorization_protocol"]
    kg_quality = payloads["knowledge_graph_quality_summary"]
    registry_by_key, key_by_url = citation_registry_maps(registry)
    concept_sources = primer_concept_sources(primer, key_by_url)
    present_sources, missing_sources = source_status(root)
    document_rows = build_document_rows(
        root, payloads, texts, registry_by_key, concept_sources
    )
    readiness_counts = Counter(row["readiness_status"] for row in document_rows)
    all_used_keys = sorted(
        {key for row in document_rows for key in row["used_citation_keys"]}
    )
    unregistered_key_count = sum(
        len(row["unregistered_used_citation_keys"]) for row in document_rows
    )
    missing_reference_key_count = sum(
        len(row["missing_reference_keys"]) for row in document_rows
    )
    missing_concept_count = sum(len(row["missing_concept_ids"]) for row in document_rows)
    missing_doc_source_key_count = sum(
        len(row["missing_required_source_keys"]) for row in document_rows
    )
    authorization_violation_count = sum(
        len(row["authorization_violations"]) for row in document_rows
    )
    bibtex_missing_key_count = sum(len(row["bibtex_missing_keys"]) for row in document_rows)
    metadata_incomplete_key_count = sum(
        len(row["metadata_incomplete_keys"]) for row in document_rows
    )
    registry_summary = summary(registry)
    primer_summary = summary(primer)
    claim_summary = summary(claim_matrix)
    final_summary = summary(final_auth)
    kg_graph = kg_quality.get("graph") or {}
    checks = [
        check_row(
            "source_artifacts_present",
            not missing_sources,
            {
                "source_artifact_count": len(present_sources),
                "missing_source_artifacts": missing_sources,
            },
            "missing_manuscript_claim_citation_source",
        ),
        check_row(
            "citation_registry_ready",
            registry_summary.get("overall_status")
            == "publication_citation_registry_ready_no_final_prose"
            and registry_summary.get("failed_check_count") == 0
            and registry_summary.get("bibtex_entry_count") == registry_summary.get(
                "citation_row_count"
            ),
            {
                "registry_status": registry_summary.get("overall_status"),
                "citation_row_count": registry_summary.get("citation_row_count"),
                "bibtex_entry_count": registry_summary.get("bibtex_entry_count"),
                "failed_check_count": registry_summary.get("failed_check_count"),
            },
            "citation_registry_not_ready",
        ),
        check_row(
            "reader_primer_ready",
            primer_summary.get("overall_status")
            == "reader_method_primer_citation_map_ready_no_final_prose"
            and primer_summary.get("failed_check_count") == 0
            and len(concept_sources) >= 12,
            {
                "primer_status": primer_summary.get("overall_status"),
                "concept_source_count": len(concept_sources),
                "failed_check_count": primer_summary.get("failed_check_count"),
            },
            "reader_primer_not_ready",
        ),
        check_row(
            "document_citations_registered_and_referenced",
            unregistered_key_count == 0
            and missing_reference_key_count == 0
            and bibtex_missing_key_count == 0
            and metadata_incomplete_key_count == 0,
            {
                "used_unique_citation_key_count": len(all_used_keys),
                "unregistered_key_count": unregistered_key_count,
                "missing_reference_key_count": missing_reference_key_count,
                "bibtex_missing_key_count": bibtex_missing_key_count,
                "metadata_incomplete_key_count": metadata_incomplete_key_count,
            },
            "manuscript_citation_registration_gap",
        ),
        check_row(
            "reader_concept_citations_covered",
            missing_concept_count == 0,
            {"missing_concept_count": missing_concept_count},
            "reader_concept_citation_gap",
        ),
        check_row(
            "document_source_keys_traceable",
            missing_doc_source_key_count == 0,
            {"missing_document_source_key_count": missing_doc_source_key_count},
            "document_source_key_traceability_gap",
        ),
        check_row(
            "claim_matrix_current_and_clean",
            claim_summary.get("overall_status")
            == "publication_claim_evidence_verification_ready_no_final_prose"
            and claim_summary.get("verification_pass_count")
            == claim_summary.get("verification_row_count")
            and claim_summary.get("current_publication_draft_artifact_pass_count")
            == claim_summary.get("current_publication_draft_artifact_count")
            and claim_summary.get("failed_check_count") == 0,
            {
                "claim_matrix_status": claim_summary.get("overall_status"),
                "verification_row_count": claim_summary.get("verification_row_count"),
                "verification_pass_count": claim_summary.get("verification_pass_count"),
                "draft_artifact_count": claim_summary.get(
                    "current_publication_draft_artifact_count"
                ),
                "draft_artifact_pass_count": claim_summary.get(
                    "current_publication_draft_artifact_pass_count"
                ),
                "failed_check_count": claim_summary.get("failed_check_count"),
            },
            "claim_matrix_not_current_clean",
        ),
        check_row(
            "final_outputs_remain_blocked",
            authorization_violation_count == 0
            and final_summary.get("final_manuscript_prose_permission") is False
            and final_summary.get("latex_html_authoring_authorized") is False
            and final_summary.get("method_recommendation_authorized") is False
            and final_summary.get("positive_claim_promotion_authorized") is False,
            {
                "document_authorization_violation_count": authorization_violation_count,
                "final_manuscript_prose_permission": final_summary.get(
                    "final_manuscript_prose_permission"
                ),
                "latex_html_authoring_authorized": final_summary.get(
                    "latex_html_authoring_authorized"
                ),
                "method_recommendation_authorized": final_summary.get(
                    "method_recommendation_authorized"
                ),
                "positive_claim_promotion_authorized": final_summary.get(
                    "positive_claim_promotion_authorized"
                ),
            },
            "final_output_authorization_opened",
        ),
        check_row(
            "kg_traceability_current",
            int(kg_graph.get("isolated_node_count") or 0) == 0
            and int(kg_graph.get("node_count") or 0) >= 3535
            and int(kg_graph.get("edge_count") or 0) >= 20027,
            {
                "kg_node_count": kg_graph.get("node_count"),
                "kg_edge_count": kg_graph.get("edge_count"),
                "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
            },
            "kg_traceability_not_current",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    summary_payload = {
        "overall_status": (
            "manuscript_claim_citation_readiness_ready_no_final_prose"
            if not failed_checks
            else "manuscript_claim_citation_readiness_blocked"
        ),
        "phase_state": "pre_final_prose_claim_citation_readiness_final_outputs_blocked",
        "document_count": len(document_rows),
        "document_pass_count": readiness_counts.get("pass", 0),
        "used_unique_citation_key_count": len(all_used_keys),
        "unregistered_citation_key_count": unregistered_key_count,
        "missing_reference_key_count": missing_reference_key_count,
        "bibtex_missing_key_count": bibtex_missing_key_count,
        "metadata_incomplete_key_count": metadata_incomplete_key_count,
        "missing_reader_concept_count": missing_concept_count,
        "missing_document_source_key_count": missing_doc_source_key_count,
        "document_authorization_violation_count": authorization_violation_count,
        "citation_registry_row_count": registry_summary.get("citation_row_count"),
        "citation_registry_bibtex_entry_count": registry_summary.get(
            "bibtex_entry_count"
        ),
        "reader_primer_concept_count": primer_summary.get("concept_row_count"),
        "claim_matrix_verification_row_count": claim_summary.get(
            "verification_row_count"
        ),
        "claim_matrix_current_draft_artifact_count": claim_summary.get(
            "current_publication_draft_artifact_count"
        ),
        "final_manuscript_prose_permission": False,
        "latex_html_authoring_authorized": False,
        "method_recommendation_authorized": False,
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "positive_claim_promotion_authorized": False,
        "release_authorized": False,
        "kg_node_count": kg_graph.get("node_count"),
        "kg_edge_count": kg_graph.get("edge_count"),
        "kg_isolated_node_count": kg_graph.get("isolated_node_count"),
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
        "document_rows": document_rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This audit checks draft claim/citation readiness only; it does not write final prose.",
            "Registered citations support reader explanation and literature context, not empirical claim promotion.",
            "Empirical claims remain tied to audited source artifacts and claim/evidence matrix rows.",
            "Final manuscript prose, LaTeX/HTML authoring, release, method recommendation, and positive claims remain unauthorized.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# Manuscript Claim/Citation Readiness Audit",
        "",
        "This pre-final-prose audit checks whether the current main article and supplementary document drafts have registered citations, reader-primer concept coverage, source traceability, and closed final-output authorizations.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{s['overall_status']}`",
        f"- Phase state: `{s['phase_state']}`",
        f"- Documents passing: {s['document_pass_count']} / {s['document_count']}",
        f"- Unique used citation keys: {s['used_unique_citation_key_count']}",
        f"- Unregistered citation keys: {s['unregistered_citation_key_count']}",
        f"- Missing reference keys: {s['missing_reference_key_count']}",
        f"- Missing reader concepts: {s['missing_reader_concept_count']}",
        f"- Missing document source keys: {s['missing_document_source_key_count']}",
        f"- Document authorization violations: {s['document_authorization_violation_count']}",
        f"- KG snapshot: {s['kg_node_count']} nodes / {s['kg_edge_count']} edges / {s['kg_isolated_node_count']} isolated",
        f"- Failed checks: {s['failed_check_count']}",
        "",
        "## Document Rows",
        "",
        "| Document | Status | Citations | Missing concepts | Missing refs | Authorization violations |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["document_rows"]:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                row["document_id"],
                row["readiness_status"],
                len(row["used_citation_keys"]),
                len(row["missing_concept_ids"]),
                len(row["missing_reference_keys"]),
                len(row["authorization_violations"]),
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
                "document_count": payload["summary"]["document_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
