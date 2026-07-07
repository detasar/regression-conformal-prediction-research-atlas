"""Build the private sterile publication review package.

This is a local/private package step, not a public release. It copies only the
allow-listed publication, governance, knowledge-graph, and reproducibility
sources into a clean sibling directory, scans the copied files for high-confidence
secret/raw/cache risks, and records a checksum manifest.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts import (
    build_sterile_repository_staging_manifest as staging,
)


SCHEMA = "cpfi_regression_private_sterile_publication_package_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/"
    "private_sterile_publication_package_manifest.json"
)
DEFAULT_PACKAGE_ROOT = Path("../regression-conformal-prediction-research-atlas-private")
AUTHOR_NAME = "Emre Tasar"
AUTHOR_ROLE = "Data Scientist"
AUTHOR_EMAIL = "detasar@gmail.com"

STAGING_MANIFEST = Path(
    "experiments/regression/manuscript/sterile_repository_staging_manifest.json"
)
RELEASE_CUT = Path(
    "experiments/regression/manuscript/neutral_publication_release_cut_decision.json"
)
LATEX_HTML_OUTPUTS_MANIFEST = Path(
    "experiments/regression/manuscript/private_latex_html_review_outputs_manifest.json"
)
LATEX_HTML_OUTPUT_AUDIT = Path(
    "experiments/regression/manuscript/private_latex_html_review_output_audit.json"
)
README_DRAFT = Path(
    "experiments/regression/manuscript/sterile_repository_readme_draft.md"
)
README_DRAFT_JSON = Path(
    "experiments/regression/manuscript/sterile_repository_readme_draft.json"
)
RESEARCH_DOCUMENT_JSON = Path(
    "experiments/regression/manuscript/research_document.json"
)
CLAIM_EVIDENCE_MATRIX_JSON = Path(
    "experiments/regression/manuscript/publication_claim_evidence_verification_matrix.json"
)
MAX_SECRET_SCAN_BYTES = 2 * 1024 * 1024

GOVERNANCE_SOURCES = [
    "experiments/regression/manuscript/research_document.md",
    "experiments/regression/manuscript/research_document.json",
    "experiments/regression/manuscript/publication_authoring_decision_record.md",
    "experiments/regression/manuscript/publication_authoring_decision_record.json",
    "experiments/regression/manuscript/neutral_publication_release_cut_decision.md",
    "experiments/regression/manuscript/neutral_publication_release_cut_decision.json",
    "experiments/regression/manuscript/private_latex_html_review_outputs_manifest.md",
    "experiments/regression/manuscript/private_latex_html_review_outputs_manifest.json",
    "experiments/regression/manuscript/private_latex_html_review_output_audit.md",
    "experiments/regression/manuscript/private_latex_html_review_output_audit.json",
    "experiments/regression/manuscript/review_latex_html_outputs",
    "experiments/regression/manuscript/final_publication_output_authorization_protocol.json",
    "experiments/regression/manuscript/manuscript_claim_citation_readiness_audit.md",
    "experiments/regression/manuscript/manuscript_claim_citation_readiness_audit.json",
    "experiments/regression/manuscript/publication_claim_evidence_verification_matrix.json",
    "experiments/regression/manuscript/publication_exemplar_review.md",
    "experiments/regression/manuscript/publication_exemplar_review.json",
]
PROVENANCE_SOURCES = [
    "experiments/regression/diary/data_scientist_log.md",
    "experiments/regression/graphs/data_flow.mmd",
    "experiments/regression/graphs/control_flow.mmd",
    "experiments/regression/graphs/dependency_graph.mmd",
    "experiments/regression/graphs/system_ontology.mmd",
]

EXCLUDED_PARTS = {
    ".cache",
    ".git",
    ".hypothesis",
    ".ipynb_checkpoints",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
}
EXCLUDED_SUFFIXES = {
    ".csv",
    ".db",
    ".feather",
    ".h5",
    ".joblib",
    ".log",
    ".parquet",
    ".pkl",
    ".pyc",
    ".pyo",
    ".sqlite",
}
RISK_PATTERNS = tuple(staging.RISK_PATTERNS)
SECRET_PATTERNS = {
    "openai_api_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
SITE_HTML_REQUIRED_PHRASES = {
    "site/index.html": (
        "CPFI Regression Private Review Package",
        "One-Minute Thesis",
        "expected strong regression solution did not emerge",
        "browsable traceability surface",
        "Evidence snapshot",
        "Reviewer Front Door",
        "first 60-second route",
        "Review At A Glance",
        "first 30-second review map",
        "First 10 Minutes Review Protocol",
        "acceptance-check driven route",
        "public release still requires a separate authorization record",
        "Reader Contract",
        "Read this document in four layers",
        "Article / Supplement / Knowledge Graph review triad",
        "Minimal main article",
        "Broad supplementary document",
        "Browsable knowledge graph",
        "Review lanes",
        "Reviewer decision queue",
        "Research Question Answer Map",
        "Contribution And Finding Snapshot",
        "Paper Architecture And Review Contract",
        "README-level route into the main article review contract",
        "Method Primer For Non-Specialist Readers",
        "Reader Safety Checklist",
        "Result interpretation guide",
        "Guarantee Boundary Snapshot",
        "Artifact entry points",
        "Article-supplement evidence crosswalk",
        "Repository Map",
        "Package path",
        "Claim-Safe Reading Map",
        "Claim-Evidence Verification Snapshot",
        "publication_claim_evidence_verification_matrix",
        "Claim boundaries",
        "Publication exemplar review",
        "Public release review checklist",
        "Knowledge graph browser",
        "Public release</dt>",
        "Method recommendation</dt>",
    ),
    "site/kg_browser.html": (
        "CPFI Knowledge Graph Browser",
        "Research Atlas Graph Canvas",
        "Guided trace presets",
        "Final selected-method gate",
        "Venn-Abers bridge gate",
        "Claim-safe README map",
        "Search nodes",
        "Relation filter",
        "Confidence floor",
        "Graph depth",
        "Edge provenance",
        "Fallback evidence table",
        "kg_browser_data.json",
    ),
}
SITE_BOUNDARY_LABELS = (
    "Public release",
    "Method recommendation",
    "Positive claim promotion",
    "Raw data or secret inclusion",
)
SITE_VISUAL_SMOKE_LAYOUT_GUARDS = (
    "overflow-wrap: anywhere",
    ".reviewer-front-door-table, .review-glance-table, .paper-architecture-table",
    "table-layout: fixed",
    ".reviewer-front-door-table th:nth-child(5)",
    ".review-glance-table th:nth-child(4)",
)
SITE_VISUAL_SMOKE_FIRST_SCREEN_PHRASES = (
    "One-Minute Thesis",
    "Evidence snapshot",
    "Reviewer Front Door",
    "CQR/CV+ were observed as strong practical candidates in these experiments",
    "expected strong regression solution did not emerge",
    "browsable traceability surface",
)
GENERATED_REVIEW_SURFACE_SPECS = (
    {
        "package_path": "README.md",
        "surface_role": "private_review_readme",
        "required_phrases": (
            "This private review package contains",
            "USER_REVIEW_HANDOFF.md",
            "Reviewer Acceptance Checklist",
            "Reviewer Front Door",
            "first 60-second route",
            "Review At A Glance",
            "first 30-second review map",
            "First 10 Minutes Review Protocol",
            "acceptance-check driven route",
            "Research Document Entry Point",
            "manuscript/research_document.md",
            "Provenance Graph And Log Entry Points",
            "provenance/data_scientist_log.md",
            "provenance/graphs/data_flow.mmd",
            "Method Primer For Non-Specialist Readers",
            "Reader Safety Checklist",
            "Guarantee Boundary Snapshot",
            "Paper Architecture And Review Contract",
            "Public release and final citable status remain closed",
        ),
    },
    {
        "package_path": "PRIVATE_REVIEW_BOUNDARIES.md",
        "surface_role": "private_review_boundaries",
        "required_phrases": (
            "This package is generated for private review only.",
            "Public release authorized: `False`",
            "Method recommendation authorized: `False`",
        ),
    },
    {
        "package_path": "USER_REVIEW_HANDOFF.md",
        "surface_role": "private_user_review_handoff",
        "required_phrases": (
            "Recommended Review Order",
            "Reviewer Acceptance Checklist",
            "Reviewer Front Door",
            "first 60-second route",
            "First 10 Minutes Review Protocol",
            "Reviewer Decision Matrix",
            "Research Question Answer Map",
            "Provenance Graph And Log Entry Points",
            "provenance/data_scientist_log.md",
            "Result Interpretation Guide",
            "Research Document",
            "Public release requires explicit user approval after review.",
            "Method recommendation authorized: `False`",
        ),
    },
    {
        "package_path": "PUBLIC_RELEASE_REVIEW_CHECKLIST.md",
        "surface_role": "private_public_release_review_checklist",
        "required_phrases": (
            "Public Release Review Checklist",
            "This checklist does not authorize public release.",
            "Public release authorized: `False`",
            "Method recommendation authorized: `False`",
            "Claim-Safe Reading Map has been checked against the Research Document guardrails.",
            "KG browser guided trace presets have been reviewed before public release",
            "Final selected-method gate",
            "Venn-Abers bridge gate",
            "Claim/evidence matrix",
            "Private GitHub visibility and remote/local commit match remain verified.",
            "Reviewer approval required before any public repository or GitHub Pages publication.",
            "Release Authorization Record Inputs",
            "Public repository visibility",
            "GitHub Pages site",
            "KG as supplementary/web artifact",
            "A release record cannot silently open positive claims.",
        ),
    },
    {
        "package_path": "site/index.html",
        "surface_role": "private_review_site_index",
        "required_phrases": (
            "CPFI Regression Private Review Package",
            "../USER_REVIEW_HANDOFF.md",
            "User review handoff",
            "Reviewer Front Door",
            "first 60-second route",
            "Reviewer Acceptance Checklist",
            "Private review status is unambiguous.",
            "Research Document",
            "Article / Supplement / Knowledge Graph review triad",
            "Review At A Glance",
            "first 30-second review map",
            "First 10 Minutes Review Protocol",
            "acceptance-check driven route",
            "public release still requires a separate authorization record",
            "Minimal main article",
            "Broad supplementary document",
            "Browsable knowledge graph",
            "Review lanes",
            "Reviewer decision queue",
            "Research Question Answer Map",
            "Contribution And Finding Snapshot",
            "Research Document route into the research question answer map",
            "Research Document route into the contribution and finding map",
            "Paper Architecture And Review Contract",
            "README-level route into the main article review contract",
            "Method Primer For Non-Specialist Readers",
            "Reader Safety Checklist",
            "Result interpretation guide",
            "Guarantee Boundary Snapshot",
            "Main-article route into the Research Document guarantee boundary ledger",
            "Artifact entry points",
            "Provenance graph and log entry points",
            "Article-supplement evidence crosswalk",
            "Claim-Safe Reading Map",
            "Claim-Evidence Verification Snapshot",
            "publication_claim_evidence_verification_matrix",
            "README-level route into the Research Document guardrails",
            "CQR/CV+ were observed as strong practical candidates in these experiments",
            "final selected method",
            "bridge-specific negative evidence",
            "broader Venn-Abers literature",
            "Evidence snapshot",
            "Claim boundaries",
            "Publication exemplar review",
            "Publication authoring decision record",
        ),
    },
    {
        "package_path": "site/kg_browser.html",
        "surface_role": "private_kg_browser",
        "required_phrases": (
            "CPFI Knowledge Graph Browser",
            "Guided trace presets",
            "Final selected-method gate",
            "Venn-Abers bridge gate",
            "Claim-safe README map",
            "Search nodes",
            "Edge provenance",
            "kg_browser_data.json",
        ),
    },
)

KG_GUIDED_TRACE_PRESET_SPECS = (
    {
        "preset_id": "final_selected_method_gate",
        "label": "Final selected-method gate",
        "node_id": "paper_gate:final_method_model_selection_gate",
        "reader_job": (
            "Start here to inspect why no final method recommendation is open."
        ),
    },
    {
        "preset_id": "venn_abers_bridge_gate",
        "label": "Venn-Abers bridge gate",
        "node_id": "paper_gate:venn_abers_regression_validation_gate",
        "reader_job": (
            "Trace the bridge-specific negative evidence without rejecting the broader literature."
        ),
    },
    {
        "preset_id": "claim_matrix",
        "label": "Claim/evidence matrix",
        "node_id": "report:publication_claim_evidence_verification_matrix",
        "reader_job": "Inspect the claim rows, evidence gates, and blocked readings.",
    },
    {
        "preset_id": "claim_safe_readme_map",
        "label": "Claim-safe README map",
        "node_id": "methodology_control:sterile_repository_readme_draft:claim_safe_reading_map",
        "reader_job": "Trace the README-level route into Research Document guardrails.",
    },
    {
        "preset_id": "research_document_guardrail",
        "label": "Research Document guardrail",
        "node_id": "methodology_control:publication_claim_evidence_draft_artifact:research_document",
        "reader_job": "Review the private Research Document evidence boundary.",
    },
    {
        "preset_id": "private_package_manifest",
        "label": "Private package manifest",
        "node_id": "report:private_sterile_publication_package_manifest",
        "reader_job": "Verify package contents, release boundaries, and provenance.",
    },
    {
        "preset_id": "kg_quality_summary",
        "label": "KG quality summary",
        "node_id": "report:knowledge_graph_quality_summary",
        "reader_job": "Inspect graph quality, orphan-node, summary, and provenance metrics.",
    },
)


class LinkTargetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in {"href", "src"} and value:
                self.targets.append(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Source repository root.")
    parser.add_argument(
        "--package-root",
        default=str(DEFAULT_PACKAGE_ROOT),
        help="Local private package root, relative to repo root unless absolute.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output manifest JSON.")
    parser.add_argument(
        "--skip-git",
        action="store_true",
        help="Do not initialize and commit the generated local package.",
    )
    parser.add_argument(
        "--replace-existing-package",
        action="store_true",
        help=(
            "Replace an existing package root even when the generated-package marker "
            "was removed by a later public overlay."
        ),
    )
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


def fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return "n/a"
    return str(value)


def escape_markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def count_empty_markdown_table_cells(text: str) -> int:
    empty_count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if all(cell and set(cell) <= {"-", ":"} for cell in cells):
            continue
        empty_count += sum(1 for cell in cells if not cell)
    return empty_count


def resolve_package_root(repo_root: Path, package_root: Path) -> Path:
    if package_root.is_absolute():
        return package_root.resolve()
    return (repo_root / package_root).resolve()


def should_exclude_source(relative_path: str) -> tuple[bool, str | None]:
    if "private_publication_repository_remote_audit" in relative_path:
        return True, "source_remote_state_audit"
    path = Path(relative_path)
    parts = set(path.parts)
    suffix = path.suffix.lower()
    if parts & EXCLUDED_PARTS:
        return True, "cache_or_local_metadata"
    if suffix in EXCLUDED_SUFFIXES:
        return True, "raw_large_or_generated_suffix"
    if staging.matches_any(relative_path, RISK_PATTERNS):
        return True, "sterile_exclusion_policy"
    return False, None


def destination_for(source: str) -> Path:
    path = Path(source)
    if source == "LICENSE":
        return Path("LICENSE")
    if source == "requirements.txt":
        return Path("requirements.txt")
    if source == "README.md":
        return Path("source_snapshots/working_repository_README.md")
    if source == "experiments/regression/CHANGELOG.md":
        return Path("CHANGELOG.md")
    if source == "experiments/regression/diary/data_scientist_log.md":
        return Path("provenance/data_scientist_log.md")
    if source.startswith("experiments/regression/graphs/"):
        return Path("provenance/graphs") / path.name
    if source == "cpfi":
        return Path("reproducibility/cpfi")
    if source.startswith("cpfi/"):
        return Path("reproducibility") / path
    if source.startswith("experiments/regression/scripts"):
        return Path("reproducibility/experiments/regression/scripts") / path.relative_to(
            "experiments/regression/scripts"
        )
    if source.startswith("experiments/regression/configs"):
        return Path("reproducibility/experiments/regression/configs") / path.relative_to(
            "experiments/regression/configs"
        )
    if source.startswith("experiments/regression/policies"):
        return Path("reproducibility/experiments/regression/policies") / path.relative_to(
            "experiments/regression/policies"
        )
    if source == "tests":
        return Path("reproducibility/tests")
    if source.startswith("tests/"):
        return Path("reproducibility") / path
    if source.startswith("experiments/regression/catalogs/"):
        return Path("knowledge_graph") / path.name
    if source.endswith("knowledge_graph_quality/quality_summary.json"):
        return Path("knowledge_graph/quality_summary.json")
    if source.endswith("kg_publication_quality_audit.json"):
        return Path("knowledge_graph/kg_publication_quality_audit.json")
    if source.startswith("experiments/regression/reports/"):
        return Path("audits") / path.name
    if source == (
        "experiments/regression/manuscript/"
        "private_latex_html_review_outputs_manifest.json"
    ):
        return Path("metadata/private_latex_html_review_outputs_manifest.json")
    if source == (
        "experiments/regression/manuscript/"
        "private_latex_html_review_outputs_manifest.md"
    ):
        return Path("metadata/private_latex_html_review_outputs_manifest.md")
    if source == (
        "experiments/regression/manuscript/"
        "private_latex_html_review_output_audit.json"
    ):
        return Path("metadata/private_latex_html_review_output_audit.json")
    if source == (
        "experiments/regression/manuscript/"
        "private_latex_html_review_output_audit.md"
    ):
        return Path("metadata/private_latex_html_review_output_audit.md")
    if source.startswith(
        "experiments/regression/manuscript/review_latex_html_outputs/"
    ):
        return Path("rendered_outputs") / path.relative_to(
            "experiments/regression/manuscript/review_latex_html_outputs"
        )
    if source.startswith("experiments/regression/manuscript/draft_visual_table_artifacts"):
        return Path("review_only/draft_visual_table_artifacts") / path.relative_to(
            "experiments/regression/manuscript/draft_visual_table_artifacts"
        )
    if source.startswith("experiments/regression/manuscript/"):
        name = path.name
        if "visual" in name or "table" in name:
            return Path("audits/visual_table") / name
        if "publication_site" in name or "triptych" in name or "navigation" in name:
            return Path("site") / name
        if "citation" in name or name == "references.bib":
            return Path("citation") / name
        if (
            "release" in name
            or "authorization" in name
            or "claim" in name
            or "authoring_decision" in name
        ):
            return Path("governance") / name
        return Path("manuscript") / name
    return Path("source_snapshots") / path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_generated_review_surface_rows(package_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, spec in enumerate(GENERATED_REVIEW_SURFACE_SPECS):
        package_path = Path(str(spec["package_path"]))
        path = package_root / package_path
        exists = path.exists() and path.is_file()
        text = ""
        if exists and path.stat().st_size <= 1024 * 1024:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = ""
        required_phrases = tuple(str(value) for value in spec["required_phrases"])
        missing_required_phrases = [
            phrase for phrase in required_phrases if phrase not in text
        ]
        empty_markdown_table_cell_count = (
            count_empty_markdown_table_cells(text)
            if package_path.suffix.lower() == ".md"
            else 0
        )
        rows.append(
            {
                "surface_id": str(spec["surface_role"]),
                "row_index": index,
                "package_path": package_path.as_posix(),
                "exists": exists,
                "bytes": path.stat().st_size if exists else 0,
                "sha256": sha256(path) if exists else None,
                "required_phrases": list(required_phrases),
                "missing_required_phrases": missing_required_phrases,
                "empty_markdown_table_cell_count": empty_markdown_table_cell_count,
                "verification_status": (
                    "pass"
                    if (
                        exists
                        and not missing_required_phrases
                        and empty_markdown_table_cell_count == 0
                    )
                    else "fail"
                ),
                "public_release_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "positive_claim_promotion_authorized": False,
                "claim_boundary": (
                    "Generated private-review package surface only; it supports "
                    "user review and does not authorize public release, final "
                    "citable status, method recommendation, method advocacy, or "
                    "positive-claim promotion."
                ),
            }
        )
    return rows


def prepare_package_root(package_root: Path, *, replace_existing_package: bool = False) -> None:
    marker = package_root / ".cpfi_sterile_publication_package"
    if package_root.exists():
        if marker.exists() or (
            replace_existing_package and package_root.name == DEFAULT_PACKAGE_ROOT.name
        ):
            shutil.rmtree(package_root)
        elif any(package_root.iterdir()):
            raise RuntimeError(
                f"Refusing to overwrite non-generated package root: {package_root}"
            )
    package_root.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        "generated_by=build_private_sterile_publication_package.py\n",
        encoding="utf-8",
    )


def iter_source_files(repo_root: Path, source: str) -> list[tuple[Path, str]]:
    source_path = repo_root / source
    if not source_path.exists():
        return []
    if source_path.is_file():
        return [(source_path, source)]
    files: list[tuple[Path, str]] = []
    for path in sorted(source_path.rglob("*")):
        if not path.is_file():
            continue
        files.append((path, rel(path, repo_root)))
    return files


def copy_one_file(
    source_path: Path,
    source_rel: str,
    package_root: Path,
) -> dict[str, Any] | None:
    excluded, reason = should_exclude_source(source_rel)
    if excluded:
        return {
            "source_path": source_rel,
            "status": "excluded",
            "reason": reason,
        }
    dest_rel = destination_for(source_rel)
    dest_path = package_root / dest_rel
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest_path)
    return {
        "source_path": source_rel,
        "package_path": dest_rel.as_posix(),
        "status": "copied",
        "bytes": dest_path.stat().st_size,
        "sha256": sha256(dest_path),
    }


def render_private_readme(
    readme_draft: str,
    *,
    copied_file_count: int,
    excluded_file_count: int,
) -> str:
    text = readme_draft
    replacements = {
        "> Draft README for the future sterile publication repository. This file does not create a repository, authorize release, recommend a method, or make final manuscript claims.": (
            "> Private review README for the generated sterile publication package. "
            "This package is local/private, not a public release, method "
            "recommendation, or final manuscript claim."
        ),
        "- Sterile repository created: `False`.": "- Private local package created: `True`.",
        "- Sterile repository creation authorized: `False`.": (
            "- Private package preparation authorized: `True`."
        ),
        "- The clean repository has not been created in this artifact.": (
            "- This is a private local review package, not a public release repository."
        ),
        "The future sterile repository is planned to contain a polished README, article outputs, supplementary outputs, an individual experiment report, a knowledge-graph export, reproducibility commands, citation metadata, and curated figures/tables after their final gates close.": (
            "This private review package contains a polished review README, article "
            "drafts, supplementary drafts, an individual experiment report, a "
            "knowledge-graph export, reproducibility material, citation metadata, "
            "and governed review outputs. Public release and final citable status "
            "remain closed until explicit user approval."
        ),
        "The package manifest records the exact copied/excluded file counts and failed-check state.": (
            "The package manifest reports status "
            "`private_sterile_publication_package_ready`, "
            f"{copied_file_count} copied files, {excluded_file_count} excluded "
            "files, and 0 failed checks."
        ),
        "| Planned clean-repo item | Current staging status |": (
            "| Private review package item | Current review status |"
        ),
        "- This README is a draft for the future sterile repository, not the final release README.": (
            "- This README describes the private review package, not the final public release README."
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(
        (
            r"The package manifest reports status "
            r"`private_sterile_publication_package_ready`, \d+ copied files, "
            r"\d+ excluded files, and 0 failed checks\."
        ),
        (
            "The package manifest reports status "
            "`private_sterile_publication_package_ready`, "
            f"{copied_file_count} copied files, {excluded_file_count} excluded "
            "files, and 0 failed checks."
        ),
        text,
    )
    research_document_section = (
        "## Research Document Entry Point\n\n"
        "Use `manuscript/research_document.md` as the primary reader-facing "
        "review surface. It is written for private review, explains the core "
        "conformal prediction concepts for non-specialist readers, reports "
        "CQR/CV+ only as strong practical candidates observed in these "
        "experiments, and reports the evaluated Venn-Abers regression bridge as "
        "negative/failure-mode evidence. The governing decision record is "
        "`governance/publication_authoring_decision_record.md`.\n\n"
    )
    handoff_section = (
        "## Review Handoff\n\n"
        "Start with `USER_REVIEW_HANDOFF.md` for the private review order, "
        "approval boundaries, and questions to answer before any public-release "
        "decision.\n\n"
    )
    text = text.replace(
        "## Claim Boundaries\n",
        research_document_section + handoff_section + "## Claim Boundaries\n",
    )
    return text


def render_boundaries(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Private Review Boundaries",
        "",
        "This package is generated for private review only.",
        "",
        f"- Package status: `{summary_payload['overall_status']}`",
        f"- Public release authorized: `{summary_payload['public_release_authorized']}`",
        f"- Working repository final-citable: `{summary_payload['working_repository_final_citable']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        f"- Raw data or secret inclusion authorized: `{summary_payload['raw_data_or_secret_inclusion_authorized']}`",
        "",
        "The package preserves observed-evidence language only. It must not be used as a public release until user review explicitly approves that step.",
        "",
    ]
    return "\n".join(lines)


def render_user_review_handoff(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    reviewer_acceptance_rows = [
        row
        for row in payload.get("reviewer_acceptance_rows", [])
        if isinstance(row, dict)
    ]
    reviewer_front_door_rows = [
        row
        for row in payload.get("reviewer_front_door_rows", [])
        if isinstance(row, dict)
    ]
    first_ten_minute_rows = [
        row
        for row in payload.get("first_ten_minute_review_rows", [])
        if isinstance(row, dict)
    ]
    research_question_rows = [
        row for row in payload.get("research_question_rows", []) if isinstance(row, dict)
    ]
    provenance_graph_log_rows = [
        row
        for row in payload.get("provenance_graph_log_rows", [])
        if isinstance(row, dict)
    ]
    lines = [
        "# User Review Handoff",
        "",
        "This handoff is for private review of the sterile publication package and private final-prose review drafts. It does not authorize public release, final manuscript prose for public submission, method recommendation, or positive claim promotion.",
        "",
        "## Package State",
        "",
        f"- Package status: `{summary_payload['overall_status']}`",
        f"- Copied source files: {summary_payload['copied_file_count']}",
        f"- Excluded source files: {summary_payload['excluded_file_count']}",
        f"- Failed checks: {summary_payload['failed_check_count']}",
        f"- Public release authorized: `{summary_payload['public_release_authorized']}`",
        f"- Working repository final-citable: `{summary_payload['working_repository_final_citable']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        "",
        "## Reviewer Acceptance Checklist",
        "",
        "Use this checklist before treating the package as reader-ready for private review. These checks do not authorize public release, KG citation, final prose, or method recommendation.",
        "",
        "| Acceptance item | Evidence to inspect | Reject private review readiness if |",
        "|---|---|---|",
        *[
            "| [ ] {item} | {evidence} | {reject_if} |".format(
                item=escape_markdown_cell(row.get("acceptance_item")),
                evidence=escape_markdown_cell(row.get("evidence")),
                reject_if=escape_markdown_cell(row.get("reject_if")),
            )
            for row in reviewer_acceptance_rows
        ],
        "",
        "## Reviewer Front Door",
        "",
        "Use this as the first 60-second route through the private package before making any release or wording decision.",
        "",
        "| Lane | Open first | Reader action | Safe takeaway | Closed boundary |",
        "|---|---|---|---|---|",
        *[
            "| {lane} | {open_first} | {action} | {takeaway} | {boundary} |".format(
                lane=escape_markdown_cell(row.get("lane")),
                open_first=escape_markdown_cell(row.get("open_first")),
                action=escape_markdown_cell(row.get("reader_action")),
                takeaway=escape_markdown_cell(row.get("safe_takeaway")),
                boundary=escape_markdown_cell(row.get("closed_boundary")),
            )
            for row in reviewer_front_door_rows
        ],
        "",
        "## First 10 Minutes Review Protocol",
        "",
        "Use this acceptance-check driven route before accepting the private package as reader-ready.",
        "",
        "| Minute | Review action | Artifact | Acceptance check | Stop if missing |",
        "|---|---|---|---|---|",
        *[
            "| {minute} | {action} | {artifact} | {check} | {stop} |".format(
                minute=escape_markdown_cell(row.get("minute")),
                action=escape_markdown_cell(row.get("review_action")),
                artifact=escape_markdown_cell(row.get("artifact")),
                check=escape_markdown_cell(row.get("acceptance_check")),
                stop=escape_markdown_cell(row.get("stop_if_missing")),
            )
            for row in first_ten_minute_rows
        ],
        "",
        "## Reviewer Decision Matrix",
        "",
        "| Decision | Current default | What approval would mean | Boundary |",
        "|---|---|---|---|",
        "| Scientific framing | Keep neutral wording | Accept CQR/CV+ as experiment-scoped practical candidates only | No method recommendation opens |",
        "| Venn-Abers wording | Keep bridge-specific negative evidence | Accept that the evaluated bridge did not validate as a strong regression interval solution | Broader Venn-Abers literature is not rejected |",
        "| Reader readiness | Revise privately until clear | Accept Research Document, main article, and supplement as review-ready surfaces | Final manuscript prose remains closed |",
        "| KG/site value | Keep private review only | Accept KG browser/site as useful later supplementary or web artifacts | KG citation and GitHub Pages remain closed |",
        "| Public repository release | Keep private | Approve only after article, supplement, site, and README review | Requires separate release authorization |",
        "",
        "## Research Question Answer Map",
        "",
        "Research Document route into the research question answer map. Use this private-review table to keep each answer tied to an evidence anchor and a closed stronger reading.",
        "",
        "| Research question | Evidence-supported answer | Evidence anchor | Closed reading |",
        "|---|---|---|---|",
        *[
            "| {question} | {answer} | {anchor} | {closed} |".format(
                question=escape_markdown_cell(row.get("research_question")),
                answer=escape_markdown_cell(row.get("short_answer")),
                anchor=escape_markdown_cell(row.get("evidence_anchor")),
                closed=escape_markdown_cell(row.get("closed_reading")),
            )
            for row in research_question_rows
        ],
        "",
        "## Result Interpretation Guide",
        "",
        "| Quantity | Private-review reading | Boundary |",
        "|---|---|---|",
        "| Frontier cells | Observed coverage/width trade-off cells | Descriptive signal, not final method selection |",
        "| Row-weighted coverage | Broad empirical coverage summary across completed result blocks | Not theorem-level coverage or deployment evidence |",
        "| Undercoverage runs | Failure-mode evidence for a run, method, or bridge | Not a literature-wide rejection |",
        "| Closed claim gates | Explicit records of unsupported stronger claims | Cannot be opened by prose alone |",
        "",
        "## Provenance Graph And Log Entry Points",
        "",
        "Use this table when the review question is how the experiment was executed, resumed, audited, or packaged. These files are review-only provenance surfaces; they do not create new empirical evidence, method recommendation, public release, or final citable KG status.",
        "",
        "| Review task | Private package artifact | Reader job | Boundary |",
        "|---|---|---|---|",
        *[
            "| {task} | {artifact} | {job} | {boundary} |".format(
                task=escape_markdown_cell(row.get("review_task")),
                artifact=escape_markdown_cell(row.get("package_artifact")),
                job=escape_markdown_cell(row.get("reader_job")),
                boundary=escape_markdown_cell(row.get("boundary")),
            )
            for row in provenance_graph_log_rows
        ],
        "",
        "## Recommended Review Order",
        "",
        "1. `README.md` for the plain-language study summary and claim boundaries.",
        "2. `PUBLIC_RELEASE_REVIEW_CHECKLIST.md` for the public-release approval checklist.",
        "3. `manuscript/research_document.md` for the integrated Research Document.",
        "4. `rendered_outputs/index.html` for the private review entry point.",
        "5. `rendered_outputs/main_article_review.html` and `rendered_outputs/supplementary_document_review.html` for rendered article/supplement review.",
        "6. `manuscript/individual_experiment_report_draft.md` for the author-stamped individual experiment report.",
        "7. `site/kg_browser.html` for guided KG trace presets: Final selected-method gate, Venn-Abers bridge gate, Claim/evidence matrix, Claim-safe README map, Research Document guardrail, Private package manifest, and KG quality summary.",
        "8. `provenance/data_scientist_log.md` and `provenance/graphs/*.mmd` for data-flow, control-flow, dependency, ontology, and scientific-diary traceability.",
        "9. `knowledge_graph/quality_summary.json` and `knowledge_graph/knowledge_graph.json` for graph quality and traceability.",
        "10. `governance/publication_authoring_decision_record.md`, `governance/final_publication_output_authorization_protocol.json`, `governance/publication_release_gap_register.json`, and `PRIVATE_REVIEW_BOUNDARIES.md` before any release decision.",
        "",
        "## Approval Boundaries",
        "",
        "- Approving this private review package is not the same as making the repository public.",
        "- Public release requires explicit user approval after review.",
        "- Method recommendation, final selected-method language, positive fairness claims, bounded-support validity claims, and validated Venn-Abers regression claims remain closed unless a later audit explicitly authorizes them.",
        "- The working experiment repository is not the final citable repository.",
        "",
        "## Reviewer Questions",
        "",
        "- Is the neutral/no-promotion framing acceptable for a paper or supplementary report?",
        "- Are the article, supplement, and individual report readable enough for a non-specialist reader?",
        "- Are the Venn-Abers negative/failure-mode results stated without overgeneralizing?",
        "- Are the KG and package contents useful enough to expose after public-release approval?",
        "- Are any files missing from the private package before public-release preparation starts?",
        "",
    ]
    return "\n".join(lines)


def render_public_release_review_checklist(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Public Release Review Checklist",
        "",
        "This checklist does not authorize public release.",
        "",
        "## Current Boundary State",
        "",
        f"- Public release authorized: `{summary_payload['public_release_authorized']}`",
        f"- Working repository final-citable: `{summary_payload['working_repository_final_citable']}`",
        f"- Method recommendation authorized: `{summary_payload['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{summary_payload['positive_claim_promotion_authorized']}`",
        f"- Raw data or secret inclusion authorized: `{summary_payload['raw_data_or_secret_inclusion_authorized']}`",
        f"- Package failed checks: {summary_payload['failed_check_count']}",
        f"- Secret pattern hits: {summary_payload['secret_pattern_hit_count']}",
        f"- Path risk hits: {summary_payload['path_risk_hit_count']}",
        "",
        "## Reviewer Approval Checklist",
        "",
        "- [ ] Research Document wording is neutral and understandable.",
        "- [ ] Main article and supplement review HTML are readable enough for external readers.",
        "- [ ] CQR/CV+ wording is accepted as experiment-scoped practical-candidate language only.",
        "- [ ] Venn-Abers wording is accepted as bridge-specific negative evidence only.",
        "- [ ] Claim-Safe Reading Map has been checked against the Research Document guardrails.",
        "- [ ] KG browser guided trace presets have been reviewed before public release: Final selected-method gate, Venn-Abers bridge gate, Claim/evidence matrix, Claim-safe README map, Research Document guardrail, Private package manifest, and KG quality summary.",
        "- [ ] Private GitHub visibility and remote/local commit match remain verified.",
        "- [ ] No raw data, local database, cache, or secret-like material is present in the package.",
        "- [ ] Public README, site, and repository title are acceptable for later public visibility.",
        "- [ ] Reviewer approval required before any public repository or GitHub Pages publication.",
        "",
        "## Release Authorization Record Inputs",
        "",
        "Do not change repository visibility or enable GitHub Pages from this checklist alone. If every item above is accepted, create a separate release authorization record that explicitly answers the decisions below.",
        "",
        "| Decision input | Required reviewer answer | Current default | Boundary |",
        "|---|---|---|---|",
        "| Public repository visibility | Approve or reject making the sterile repository public | Keep private | Private review approval is not public release approval. |",
        "| GitHub Pages site | Approve or reject publishing the private review site as a public site | Keep unpublished | Site publication requires the same release record as repository visibility. |",
        "| KG as supplementary/web artifact | Approve or reject citing the KG browser as a supplementary artifact | Keep private review only | KG citation remains closed until release authorization. |",
        "| Article and supplement wording | Approve or request revisions to neutral public-facing prose | Revise privately | Approval must preserve experiment-scoped CQR/CV+ and bridge-specific Venn-Abers language. |",
        "| Claim boundaries | Confirm that method recommendation, population fairness, bounded-support validity, and validated Venn-Abers claims stay closed | Keep closed | A release record cannot silently open positive claims. |",
        "",
        "## Required Action After Approval",
        "",
        "If every checklist item is approved, create a new release authorization record before changing repository visibility or enabling GitHub Pages. Until that separate authorization exists, this package remains private review material only.",
        "",
    ]
    return "\n".join(lines)


def render_site_index(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    canonical_kg_nodes = fmt(summary_payload.get("kg_browser_node_count"))
    canonical_kg_edges = fmt(summary_payload.get("kg_browser_edge_count"))

    def normalize_site_kg_counts(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: normalize_site_kg_counts(child)
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [normalize_site_kg_counts(child) for child in value]
        if not isinstance(value, str):
            return value
        text = re.sub(
            r"\b\d[\d,]*\s+KG browser nodes,\s+\d[\d,]*\s+KG browser edges",
            f"{canonical_kg_nodes} KG browser nodes, "
            f"{canonical_kg_edges} KG browser edges",
            value,
        )
        text = re.sub(
            r"\b\d[\d,]*\s+nodes,\s+\d[\d,]*\s+edges",
            f"{canonical_kg_nodes} nodes, {canonical_kg_edges} edges",
            text,
        )
        return text

    def normalize_site_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            normalize_site_kg_counts(row)
            for row in rows
            if isinstance(row, dict)
        ]

    package_state = (
        "ready"
        if summary_payload.get("overall_status")
        == "private_sterile_publication_package_ready"
        else summary_payload.get("overall_status")
    )
    metrics = [
        ("Package state", package_state),
        ("Copied files", summary_payload.get("copied_file_count")),
        ("Excluded files", summary_payload.get("excluded_file_count")),
        ("Failed checks", summary_payload.get("failed_check_count")),
        ("KG nodes", summary_payload.get("kg_browser_node_count")),
        ("KG edges", summary_payload.get("kg_browser_edge_count")),
        (
            "Review surfaces",
            "{} / {}".format(
                fmt(summary_payload.get("generated_review_surface_pass_count")),
                fmt(summary_payload.get("generated_review_surface_count")),
            ),
        ),
        ("Secret hits", summary_payload.get("secret_pattern_hit_count")),
    ]
    metric_html = "\n".join(
        "<article class=\"metric\"><span>{}</span><strong>{}</strong></article>".format(
            html.escape(label),
            html.escape(fmt(value)),
        )
        for label, value in metrics
    )
    decision_rows = [
        (
            "Scientific framing",
            "Keep neutral wording",
            "CQR/CV+ remain experiment-scoped practical candidates, not recommendations.",
        ),
        (
            "Venn-Abers wording",
            "Keep bridge-specific negative evidence",
            "The evaluated bridge did not validate as a strong regression interval solution.",
        ),
        (
            "Reader readiness",
            "Revise privately until clear",
            "Research Document, article, and supplement can be accepted as review-ready surfaces.",
        ),
        (
            "KG/site value",
            "Keep private review only",
            "KG browser and site can be considered later supplementary or web artifacts.",
        ),
        (
            "Public repository release",
            "Keep private",
            "Public visibility requires a separate release authorization after review.",
        ),
    ]
    decision_html = "\n".join(
        """
      <article class="decision">
        <h3>{title}</h3>
        <p><strong>{default}</strong></p>
        <p>{description}</p>
      </article>""".format(
            title=html.escape(title),
            default=html.escape(default),
            description=html.escape(description),
        )
        for title, default, description in decision_rows
    )
    interpretation_rows = [
        (
            "Frontier cells",
            "Observed coverage/width trade-off cells",
            "Descriptive signal, not final method selection.",
        ),
        (
            "Row-weighted coverage",
            "Broad empirical coverage summary across completed result blocks",
            "Not theorem-level coverage or deployment evidence.",
        ),
        (
            "Undercoverage runs",
            "Failure-mode evidence for a run, method, or bridge",
            "Not a literature-wide rejection.",
        ),
        (
            "Closed claim gates",
            "Explicit records of unsupported stronger claims",
            "Cannot be opened by prose alone.",
        ),
    ]
    interpretation_html = "\n".join(
        """
      <article class="interpretation">
        <h3>{title}</h3>
        <p>{reading}</p>
        <p><strong>{boundary}</strong></p>
      </article>""".format(
            title=html.escape(title),
            reading=html.escape(reading),
            boundary=html.escape(boundary),
        )
        for title, reading, boundary in interpretation_rows
    )
    review_at_a_glance_rows = normalize_site_rows(
        payload.get("review_at_a_glance_rows", [])
    )
    first_ten_minute_rows = normalize_site_rows(
        payload.get("first_ten_minute_review_rows", [])
    )
    reviewer_acceptance_rows = normalize_site_rows(
        payload.get("reviewer_acceptance_rows", [])
    )
    reviewer_front_door_rows = normalize_site_rows(
        payload.get("reviewer_front_door_rows", [])
    )
    result_verification_command_rows = normalize_site_rows(
        payload.get("result_verification_command_rows", [])
    )
    environment_data_access_rows = normalize_site_rows(
        payload.get("environment_data_access_rows", [])
    )

    artifact_label_to_package_path = {
        "README.md": "README.md",
        "PUBLIC_RELEASE_REVIEW_CHECKLIST.md": "PUBLIC_RELEASE_REVIEW_CHECKLIST.md",
        "PRIVATE_REVIEW_BOUNDARIES.md": "PRIVATE_REVIEW_BOUNDARIES.md",
        "USER_REVIEW_HANDOFF.md": "USER_REVIEW_HANDOFF.md",
        "supplementary_document_draft.md": "manuscript/supplementary_document_draft.md",
        "individual_experiment_report_draft.md": (
            "manuscript/individual_experiment_report_draft.md"
        ),
    }

    def package_href(package_path: Any) -> str:
        path = str(package_path or "")
        if path == "site/index.html":
            return "index.html"
        if path.startswith("site/"):
            return path.removeprefix("site/")
        return f"../{path}"

    def artifact_href(cleaned_label: str) -> tuple[str, str] | None:
        cleaned = cleaned_label.strip().strip("`")
        package_path = artifact_label_to_package_path.get(cleaned, cleaned)
        is_package_path = (
            package_path in artifact_label_to_package_path.values()
            or package_path == "README.md"
            or package_path == "PUBLIC_RELEASE_REVIEW_CHECKLIST.md"
            or package_path == "PRIVATE_REVIEW_BOUNDARIES.md"
            or package_path == "USER_REVIEW_HANDOFF.md"
            or package_path.startswith(
                (
                    "governance/",
                    "knowledge_graph/",
                    "manuscript/",
                    "metadata/",
                    "provenance/",
                    "rendered_outputs/",
                    "site/",
                )
            )
        )
        if not is_package_path:
            return None
        return package_href(package_path), cleaned

    def site_artifact_link(text: Any, *, preserve_code: bool = False) -> str:
        raw = str(text or "")
        href_label = artifact_href(raw)
        if href_label is None:
            if preserve_code:
                return f"<code>{html.escape(raw)}</code>"
            return html.escape(raw)
        href, label = href_label
        return '<a href="{href}">{label}</a>'.format(
            href=html.escape(href),
            label=html.escape(label),
        )

    def site_artifact_links(text: Any) -> str:
        raw = str(text or "")
        if "`" in raw:
            rendered: list[str] = []
            cursor = 0
            for match in re.finditer(r"`([^`]+)`", raw):
                rendered.append(html.escape(raw[cursor : match.start()]))
                rendered.append(site_artifact_link(match.group(1), preserve_code=True))
                cursor = match.end()
            rendered.append(html.escape(raw[cursor:]))
            return "".join(rendered)
        parts = re.split(r"(\s*;\s*)", raw)
        return "".join(
            html.escape(part) if part.strip("; ") == "" else site_artifact_link(part)
            for part in parts
        )

    reviewer_acceptance_html = "\n".join(
        (
            "<tr><th>{item}</th><td>{evidence}</td><td>{reject_if}</td></tr>"
        ).format(
            item=html.escape(str(row.get("acceptance_item") or "")),
            evidence=html.escape(str(row.get("evidence") or "")),
            reject_if=html.escape(str(row.get("reject_if") or "")),
        )
        for row in reviewer_acceptance_rows
    )
    reviewer_front_door_html = "\n".join(
        (
            "<tr><th>{lane}</th><td>{open_first}</td>"
            "<td>{action}</td><td>{takeaway}</td><td>{boundary}</td></tr>"
        ).format(
            lane=html.escape(str(row.get("lane") or "")),
            open_first=site_artifact_links(row.get("open_first")),
            action=html.escape(str(row.get("reader_action") or "")),
            takeaway=html.escape(str(row.get("safe_takeaway") or "")),
            boundary=html.escape(str(row.get("closed_boundary") or "")),
        )
        for row in reviewer_front_door_rows
    )
    result_verification_command_html = "\n".join(
        (
            "<tr><th>{task}</th><td><code>{command}</code></td>"
            "<td>{expected}</td><td><code>{artifact}</code></td>"
            "<td>{boundary}</td></tr>"
        ).format(
            task=html.escape(str(row.get("verification_task") or "")),
            command=html.escape(str(row.get("command") or "")),
            expected=html.escape(str(row.get("expected_evidence") or "")),
            artifact=html.escape(str(row.get("primary_artifact") or "")),
            boundary=html.escape(str(row.get("boundary") or "")),
        )
        for row in result_verification_command_rows
    )
    environment_data_access_html = "\n".join(
        (
            "<tr><th>{surface}</th><td><code>{path}</code></td>"
            "<td>{use}</td><td>{evidence}</td><td>{boundary}</td></tr>"
        ).format(
            surface=html.escape(str(row.get("surface") or "")),
            path=html.escape(str(row.get("package_path") or "")),
            use=html.escape(str(row.get("reader_use") or "")),
            evidence=html.escape(str(row.get("evidence") or "")),
            boundary=html.escape(str(row.get("boundary") or "")),
        )
        for row in environment_data_access_rows
    )
    review_at_a_glance_html = "\n".join(
        (
            "<tr><th>{need}</th><td>{read}</td>"
            "<td>{answer}</td><td>{boundary}</td></tr>"
        ).format(
            need=html.escape(str(row.get("review_need") or "")),
            read=site_artifact_links(row.get("what_to_read")),
            answer=html.escape(str(row.get("what_it_answers") or "")),
            boundary=html.escape(str(row.get("boundary") or "")),
        )
        for row in review_at_a_glance_rows
    )
    first_ten_minute_html = "\n".join(
        (
            "<tr><th>{minute}</th><td>{action}</td><td>{artifact}</td>"
            "<td>{check}</td><td>{stop}</td></tr>"
        ).format(
            minute=html.escape(str(row.get("minute") or "")),
            action=html.escape(str(row.get("review_action") or "")),
            artifact=site_artifact_links(row.get("artifact")),
            check=html.escape(str(row.get("acceptance_check") or "")),
            stop=html.escape(str(row.get("stop_if_missing") or "")),
        )
        for row in first_ten_minute_rows
    )
    contribution_rows = normalize_site_rows(
        payload.get("contribution_finding_rows", [])
    )
    research_question_rows = normalize_site_rows(
        payload.get("research_question_rows", [])
    )
    research_question_html = "\n".join(
        (
            "<tr><th>{question}</th><td>{answer}</td>"
            "<td>{anchor}</td><td>{closed}</td></tr>"
        ).format(
            question=html.escape(str(row.get("research_question") or "")),
            answer=html.escape(str(row.get("short_answer") or "")),
            anchor=html.escape(str(row.get("evidence_anchor") or "")),
            closed=html.escape(str(row.get("closed_reading") or "")),
        )
        for row in research_question_rows
    )
    contribution_html = "\n".join(
        (
            "<tr><th>{finding}</th><td>{statement}</td>"
            "<td>{anchor}</td><td>{closed}</td></tr>"
        ).format(
            finding=html.escape(str(row.get("contribution_or_finding") or "")),
            statement=html.escape(str(row.get("reader_safe_statement") or "")),
            anchor=html.escape(str(row.get("evidence_anchor") or "")),
            closed=html.escape(str(row.get("closed_reading") or "")),
        )
        for row in contribution_rows
    )
    paper_architecture_rows = normalize_site_rows(
        payload.get("paper_architecture_rows", [])
    )
    paper_architecture_html = "\n".join(
        (
            "<tr><th>{surface}</th><td>{reader_job}</td>"
            "<td>{boundary}</td><td>{basis}</td></tr>"
        ).format(
            surface=html.escape(str(row.get("surface") or "")),
            reader_job=html.escape(str(row.get("reader_job") or "")),
            boundary=html.escape(str(row.get("boundary") or "")),
            basis=html.escape(
                str(row.get("source_basis") or row.get("source_decision_id") or "")
            ),
        )
        for row in paper_architecture_rows
    )
    claim_safe_rows = normalize_site_rows(
        payload.get("claim_safe_reading_rows", [])
    )
    claim_safe_html = "\n".join(
        (
            "<tr><th>{question}</th><td>{allowed}</td>"
            "<td>{gate}</td><td>{blocked}</td></tr>"
        ).format(
            question=html.escape(str(row.get("reader_question") or "")),
            allowed=html.escape(str(row.get("allowed_publication_sentence") or "")),
            gate=html.escape(str(row.get("evidence_gate") or "")),
            blocked=html.escape(str(row.get("blocked_reading") or "")),
        )
        for row in claim_safe_rows
    )
    claim_evidence_rows = normalize_site_rows(
        payload.get("claim_evidence_review_rows", [])
    )
    claim_evidence_html = "\n".join(
        (
            "<tr><th>{row_id}</th><td>{claim_type}</td>"
            "<td>{allowed}</td><td>{gate}</td><td>{blocked}</td></tr>"
        ).format(
            row_id=html.escape(str(row.get("claim_review_id") or "")),
            claim_type=html.escape(str(row.get("claim_type") or "")),
            allowed=html.escape(
                site_claim_text(row.get("allowed_publication_sentence"))
            ),
            gate=html.escape(site_claim_text(row.get("citation_gate"))),
            blocked=html.escape(site_claim_text(row.get("overclaim_blocked"))),
        )
        for row in claim_evidence_rows
    )
    guarantee_rows = normalize_site_rows(
        payload.get("main_article_guarantee_boundary_rows", [])
    )
    guarantee_html = "\n".join(
        (
            "<tr><th>{topic}</th><td>{statement}</td><td>{closed}</td></tr>"
        ).format(
            topic=html.escape(str(row.get("topic") or "")),
            statement=html.escape(str(row.get("article_statement") or "")),
            closed=html.escape(str(row.get("closed_reading") or "")),
        )
        for row in guarantee_rows
    )
    provenance_graph_log_rows = normalize_site_rows(
        payload.get("provenance_graph_log_rows", [])
    )
    provenance_graph_log_html = "\n".join(
        (
            "<tr><th>{task}</th><td><a href=\"../{artifact}\">{artifact}</a></td>"
            "<td>{job}</td><td>{boundary}</td></tr>"
        ).format(
            task=html.escape(str(row.get("review_task") or "")),
            artifact=html.escape(str(row.get("package_artifact") or "")),
            job=html.escape(str(row.get("reader_job") or "")),
            boundary=html.escape(str(row.get("boundary") or "")),
        )
        for row in provenance_graph_log_rows
    )
    reader_contract_rows = normalize_site_rows(payload.get("reader_contract_rows", []))
    reader_contract_html = "\n".join(
        (
            "<tr><th>{layer}</th><td>{question}</td>"
            "<td>{safe}</td><td>{boundary}</td></tr>"
        ).format(
            layer=html.escape(str(row.get("reading_layer") or "")),
            question=html.escape(str(row.get("reader_question") or "")),
            safe=html.escape(str(row.get("safe_reading") or "")),
            boundary=html.escape(str(row.get("boundary") or "")),
        )
        for row in reader_contract_rows
    )
    repository_map_rows = normalize_site_rows(payload.get("repository_map_rows", []))

    repository_map_html = "\n".join(
        (
            "<tr><th>{item}</th><td><a href=\"{href}\">{path}</a></td>"
            "<td>{job}</td><td>{status}</td></tr>"
        ).format(
            item=html.escape(str(row.get("package_item") or "")),
            href=html.escape(package_href(row.get("package_path"))),
            path=html.escape(str(row.get("package_path") or "")),
            job=html.escape(str(row.get("review_job") or "")),
            status=html.escape(str(row.get("current_review_status") or "")),
        )
        for row in repository_map_rows
    )
    artifact_entry_rows = [
        (
            "Research Document Entry Point",
            "../manuscript/research_document.md",
            "Start with the integrated narrative for non-specialist readers and the experiment-scoped interpretation.",
            "Private final-prose review only; public/submission final manuscript remains closed.",
        ),
        (
            "Main article",
            "../rendered_outputs/main_article_review.html",
            "Review the compact article surface, including the Method Primer, Reader Safety Checklist, and Guarantee And Claim Boundary Snapshot.",
            "Minimal article draft, not a public release manuscript.",
        ),
        (
            "Supplement",
            "../rendered_outputs/supplementary_document_review.html",
            "Inspect extended methods, dataset audits, robustness, negative evidence, and reproducibility support.",
            "Broad supplementary draft; retained final tables remain closed.",
        ),
        (
            "Knowledge graph browser",
            "kg_browser.html",
            "Start from guided trace presets for claim gates, then navigate nodes, relations, edge confidence, and provenance.",
            "Supplementary/web artifact candidate; KG citation and GitHub Pages remain closed.",
        ),
        (
            "Release gate",
            "../PUBLIC_RELEASE_REVIEW_CHECKLIST.md",
            "Confirm the private package remains closed before any later publication decision.",
            "Checklist does not authorize public release.",
        ),
    ]
    artifact_entry_html = "\n".join(
        "<tr><th><a href=\"{url}\">{entry}</a></th><td>{job}</td><td>{boundary}</td></tr>".format(
            url=html.escape(url),
            entry=html.escape(entry),
            job=html.escape(job),
            boundary=html.escape(boundary),
        )
        for entry, url, job, boundary in artifact_entry_rows
    )
    crosswalk_rows = [
        (
            "Non-specialist method primer",
            "Method Reading Guide plus main article Method Primer For Non-Specialist Readers and Reader Safety Checklist",
            "Supplement Reader Crosswalk and method-detail sections",
            "Orientation does not open method recommendation, final selection, population fairness, or validated Venn-Abers regression claims.",
        ),
        (
            "Method mechanics and notation",
            "Method Reading Guide plus Artifact Entry Points",
            "Supplement Reader Crosswalk and detailed method sections",
            "No final tutorial or deployment recipe is opened by the draft prose.",
        ),
        (
            "CQR/CV+ descriptive evidence",
            "Current Evidence Snapshot and Result Interpretation Guide",
            "Supplement sections on frontier cells, coverage, and width evidence",
            "No general best-method recommendation is authorized.",
        ),
        (
            "Venn-Abers bridge negative evidence",
            "Reviewer Decision Matrix and claim boundaries",
            "Supplement negative-evidence and failure-mode support",
            "The broader Venn-Abers literature is not rejected.",
        ),
        (
            "Bounded-support and fairness gates",
            "Evidence Snapshot Reading Notes and release checklist",
            "Supplement validity/fairness audit sections",
            "Zero-ready bundles keep stronger validity and fairness claims closed.",
        ),
        (
            "KG and release state",
            "Repository Map, KG browser, and governance files",
            "Supplement provenance and reproducibility support",
            "KG citation, GitHub Pages, and public repository release remain closed.",
        ),
    ]
    crosswalk_html = "\n".join(
        "<tr><th>{surface}</th><td>{readme}</td><td>{supplement}</td><td>{closed}</td></tr>".format(
            surface=html.escape(surface),
            readme=html.escape(readme),
            supplement=html.escape(supplement),
            closed=html.escape(closed),
        )
        for surface, readme, supplement, closed in crosswalk_rows
    )
    lanes = [
        (
            "Start here",
            "Orientation and approval boundaries before reading results.",
            [
                ("README", "../README.md"),
                (
                    "Public release review checklist",
                    "../PUBLIC_RELEASE_REVIEW_CHECKLIST.md",
                ),
                ("User review handoff", "../USER_REVIEW_HANDOFF.md"),
                ("Private boundaries", "../PRIVATE_REVIEW_BOUNDARIES.md"),
            ],
        ),
        (
            "Research narrative",
            "Reader-facing manuscript surfaces for scientific review.",
            [
                ("Research Document", "../manuscript/research_document.md"),
                ("Main article review HTML", "../rendered_outputs/main_article_review.html"),
                (
                    "Supplementary review HTML",
                    "../rendered_outputs/supplementary_document_review.html",
                ),
                (
                    "Individual experiment report",
                    "../manuscript/individual_experiment_report_draft.md",
                ),
                (
                    "Publication exemplar review",
                    "../manuscript/publication_exemplar_review.md",
                ),
            ],
        ),
        (
            "Evidence and graph",
            "Trace claims to graph nodes, package manifests, and source evidence.",
            [
                ("Knowledge graph browser", "kg_browser.html"),
                ("Knowledge graph JSON", "../knowledge_graph/knowledge_graph.json"),
                ("KG quality summary", "../knowledge_graph/quality_summary.json"),
                ("Data flow graph", "../provenance/graphs/data_flow.mmd"),
                ("Control flow graph", "../provenance/graphs/control_flow.mmd"),
                (
                    "Data scientist log",
                    "../provenance/data_scientist_log.md",
                ),
                (
                    "Package manifest",
                    "../metadata/private_sterile_publication_package_manifest.json",
                ),
            ],
        ),
        (
            "Governance",
            "Review gates that keep public release and method promotion closed.",
            [
                (
                    "Publication authoring decision record",
                    "../governance/publication_authoring_decision_record.md",
                ),
                (
                    "Release-cut decision",
                    "../governance/neutral_publication_release_cut_decision.md",
                ),
                (
                    "Final authorization protocol",
                    "../governance/final_publication_output_authorization_protocol.json",
                ),
            ],
        ),
    ]
    lane_html = "\n".join(
        """
      <section class="lane">
        <h3>{title}</h3>
        <p>{description}</p>
        <ul>
{links}
        </ul>
      </section>""".format(
            title=html.escape(title),
            description=html.escape(description),
            links="\n".join(
                '          <li><a href="{}">{}</a></li>'.format(
                    html.escape(url),
                    html.escape(label),
                )
                for label, url in links
            ),
        )
        for title, description, links in lanes
    )
    triptych_cards = [
        (
            "Minimal main article",
            "../rendered_outputs/main_article_review.html",
            "Compact reader-facing article surface for the central result narrative, claim-evidence map, and neutral interpretation boundaries.",
            "Final manuscript prose and public release remain closed.",
        ),
        (
            "Broad supplementary document",
            "../rendered_outputs/supplementary_document_review.html",
            "Extended evidence surface for methods, datasets, audit controls, robustness, negative evidence, and reproducibility detail.",
            "Supplementary release and retained final tables remain closed.",
        ),
        (
            "Browsable knowledge graph",
            "kg_browser.html",
            (
                "Interactive provenance surface over "
                f"{fmt(summary_payload.get('kg_browser_node_count'))} nodes, "
                f"{fmt(summary_payload.get('kg_browser_edge_count'))} edges, "
                f"{fmt(summary_payload.get('kg_browser_node_type_count'))} node types, "
                f"and {fmt(summary_payload.get('kg_browser_relation_type_count'))} relation types."
            ),
            "KG citation and GitHub Pages deployment remain closed.",
        ),
    ]
    triptych_html = "\n".join(
        """
      <article class="triad-card">
        <h3>{title}</h3>
        <p>{description}</p>
        <p class="triad-boundary">{boundary}</p>
        <a href="{url}">Open review surface</a>
      </article>""".format(
            title=html.escape(title),
            description=html.escape(description),
            boundary=html.escape(boundary),
            url=html.escape(url),
        )
        for title, url, description, boundary in triptych_cards
    )
    boundary_rows = [
        ("Public release authorized", summary_payload.get("public_release_authorized")),
        (
            "Working repository final-citable",
            summary_payload.get("working_repository_final_citable"),
        ),
        (
            "Method recommendation authorized",
            summary_payload.get("method_recommendation_authorized"),
        ),
        (
            "Positive claim promotion authorized",
            summary_payload.get("positive_claim_promotion_authorized"),
        ),
        (
            "Raw data or secret inclusion authorized",
            summary_payload.get("raw_data_or_secret_inclusion_authorized"),
        ),
    ]
    boundary_html = "\n".join(
        "<tr><th>{}</th><td><code>{}</code></td></tr>".format(
            html.escape(label),
            html.escape(fmt(value)),
        )
        for label, value in boundary_rows
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CPFI Regression Private Review Package</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #5d6678;
      --line: #d8dde7;
      --panel: #ffffff;
      --soft: #f6f8fb;
      --blue: #2251a4;
      --green: #1f7a55;
      --amber: #8a5a00;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #eef2f7;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 36px 24px 48px; }}
    a {{ color: var(--blue); font-weight: 650; text-decoration-thickness: 1px; text-underline-offset: 3px; }}
    code {{ background: #eef1f6; border: 1px solid var(--line); padding: 2px 5px; border-radius: 4px; overflow-wrap: anywhere; }}
    h1 {{ margin: 0; font-size: clamp(2rem, 4vw, 3.25rem); line-height: 1.02; letter-spacing: 0; }}
    h2 {{ margin: 34px 0 14px; font-size: 1.3rem; letter-spacing: 0; }}
    h3 {{ margin: 0 0 6px; font-size: 1rem; letter-spacing: 0; }}
    p {{ margin: 0; color: var(--muted); }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(280px, .8fr);
      gap: 24px;
      align-items: end;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }}
    .eyebrow {{ margin-bottom: 10px; color: var(--green); font-weight: 760; text-transform: uppercase; font-size: .78rem; letter-spacing: .08em; }}
    .sub {{ margin-top: 16px; max-width: 760px; font-size: 1.02rem; }}
    .status {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 1px 2px rgba(23, 32, 51, .05);
    }}
    .status dl {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px 16px; margin: 0; }}
    .status dt {{ color: var(--muted); }}
    .status dd {{ margin: 0; font-weight: 720; text-align: right; min-width: 0; }}
    .status code {{ display: inline-block; max-width: 100%; text-align: left; white-space: normal; }}
    .thesis-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .thesis-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    .thesis-card p {{ margin-top: 8px; }}
    .thesis-card strong {{ color: var(--ink); }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 22px; }}
    .metric {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; min-height: 86px; }}
    .metric span {{ display: block; color: var(--muted); font-size: .86rem; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 1.2rem; line-height: 1.25; overflow-wrap: anywhere; }}
    .decision-grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }}
    .decision {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .decision p {{ margin-top: 8px; }}
    .decision strong {{ color: var(--amber); font-weight: 720; }}
    .interpretation-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .interpretation {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .interpretation p {{ margin-top: 8px; }}
    .interpretation strong {{ color: var(--amber); font-weight: 700; }}
    .wide-panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; overflow-x: auto; }}
    .wide-panel p {{ margin-bottom: 12px; max-width: 920px; }}
    .wide-table th {{ min-width: 180px; }}
    .wide-table td {{ min-width: 210px; }}
    .acceptance-checklist-table th {{ min-width: 240px; }}
    .acceptance-checklist-table td {{ min-width: 300px; }}
    .claim-map-table th {{ min-width: 220px; }}
    .claim-map-table td {{ min-width: 260px; }}
    .claim-evidence-table th {{ min-width: 220px; }}
    .claim-evidence-table td {{ min-width: 250px; }}
    .reader-contract-table th {{ min-width: 190px; }}
    .reader-contract-table td {{ min-width: 230px; }}
    .repository-map-table th {{ min-width: 180px; }}
    .repository-map-table td {{ min-width: 220px; }}
    .contribution-table th {{ min-width: 220px; }}
    .contribution-table td {{ min-width: 250px; }}
    .lanes {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }}
    .lane {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    .lane p {{ min-height: 48px; }}
    .lane ul {{ margin: 14px 0 0; padding-left: 18px; }}
    .lane li + li {{ margin-top: 8px; }}
    .triad {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .triad-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    .triad-card p {{ margin-top: 8px; }}
    .triad-boundary {{ color: var(--amber); font-weight: 650; }}
    .evidence {{
      display: grid;
      grid-template-columns: minmax(0, .9fr) minmax(0, 1.1fr);
      gap: 16px;
      align-items: start;
    }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px 0; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; overflow-wrap: anywhere; }}
    th {{ color: var(--muted); font-weight: 620; }}
    tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
    .reviewer-front-door-table, .review-glance-table, .paper-architecture-table {{ table-layout: fixed; }}
    .reviewer-front-door-table th, .reviewer-front-door-table td,
    .review-glance-table th, .review-glance-table td,
    .paper-architecture-table th, .paper-architecture-table td {{ min-width: 0; padding-right: 14px; }}
    .reviewer-front-door-table th:nth-child(1) {{ width: 10%; }}
    .reviewer-front-door-table th:nth-child(2) {{ width: 22%; }}
    .reviewer-front-door-table th:nth-child(3) {{ width: 24%; }}
    .reviewer-front-door-table th:nth-child(4) {{ width: 24%; }}
    .reviewer-front-door-table th:nth-child(5) {{ width: 20%; }}
    .review-glance-table th:nth-child(1) {{ width: 18%; }}
    .review-glance-table th:nth-child(2) {{ width: 24%; }}
    .review-glance-table th:nth-child(3) {{ width: 34%; }}
    .review-glance-table th:nth-child(4) {{ width: 24%; }}
    .note {{ margin-top: 12px; color: var(--amber); font-weight: 650; }}
    @media (max-width: 900px) {{
      main {{ padding: 26px 16px 36px; }}
      .hero, .evidence {{ grid-template-columns: 1fr; }}
      .metrics, .lanes, .triad, .decision-grid, .interpretation-grid, .thesis-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 560px) {{
      .metrics, .lanes, .triad, .decision-grid, .interpretation-grid, .thesis-grid {{ grid-template-columns: 1fr; }}
      .status dl {{ grid-template-columns: 1fr; }}
      .status dd {{ text-align: left; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div>
        <p class="eyebrow">Private review package</p>
        <h1>CPFI Regression Private Review Package</h1>
        <p class="sub">A governed review portal for the regression conformal prediction study. It connects the Research Document, rendered manuscript surfaces, knowledge graph browser, and release-boundary evidence without authorizing public release or method recommendation.</p>
      </div>
      <aside class="status" aria-label="Current authorization status">
        <dl>
          <dt>Status</dt>
          <dd><code>{html.escape(fmt(package_state))}</code></dd>
          <dt>Author</dt>
          <dd>{html.escape(str(summary_payload.get('author_name')))}, {html.escape(str(summary_payload.get('author_role')))}</dd>
          <dt>Contact</dt>
          <dd><a href="mailto:{html.escape(str(summary_payload.get('author_email')))}">{html.escape(str(summary_payload.get('author_email')))}</a></dd>
          <dt>Public release</dt>
          <dd><code>{html.escape(fmt(summary_payload.get('public_release_authorized')))}</code></dd>
          <dt>Method recommendation</dt>
          <dd><code>{html.escape(fmt(summary_payload.get('method_recommendation_authorized')))}</code></dd>
          <dt>Positive claim promotion</dt>
          <dd><code>{html.escape(fmt(summary_payload.get('positive_claim_promotion_authorized')))}</code></dd>
        </dl>
      </aside>
    </section>

    <section aria-labelledby="one-minute-thesis">
      <h2 id="one-minute-thesis">One-Minute Thesis</h2>
      <div class="thesis-grid">
        <article class="thesis-card">
          <h3>Empirical result</h3>
          <p><strong>CQR/CV+ were observed as strong practical candidates in these experiments.</strong> This is a scoped diagnostic statement; method recommendation and final selection remain closed.</p>
        </article>
        <article class="thesis-card">
          <h3>Negative evidence</h3>
          <p>The evaluated Venn-Abers regression bridge is reported as bridge-specific negative evidence: the expected strong regression solution did not emerge in these experiments.</p>
        </article>
        <article class="thesis-card">
          <h3>Traceability surface</h3>
          <p>The knowledge graph is a browsable traceability surface linking claims, reports, methods, citations, quality gates, and source artifacts. Public KG citation and GitHub Pages publication remain closed.</p>
        </article>
      </div>
    </section>

    <section aria-labelledby="evidence-snapshot">
      <h2 id="evidence-snapshot">Evidence snapshot</h2>
      <div class="metrics">
{metric_html}
      </div>
    </section>

    <section aria-labelledby="result-verification-commands">
      <h2 id="result-verification-commands">Result Verification Commands</h2>
      <div class="wide-panel">
        <p>Private-site version of the README verification command table. Run these commands from the source repository root before refreshing the private package; they verify reader-facing numbers and review surfaces without authorizing public release.</p>
        <table class="wide-table result-verification-table">
          <thead>
            <tr><th>Verification task</th><th>Command</th><th>Expected evidence</th><th>Primary artifact</th><th>Boundary</th></tr>
          </thead>
          <tbody>
{result_verification_command_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="environment-data-access">
      <h2 id="environment-data-access">Environment And Data Access</h2>
      <div class="wide-panel">
        <p>Private-site version of the README environment and data-access contract. Use it before running verification commands so the dependency, raw-data, cache, and secret boundaries stay visible.</p>
        <table class="wide-table environment-data-access-table">
          <thead>
            <tr><th>Surface</th><th>Package path</th><th>Reader use</th><th>Evidence</th><th>Boundary</th></tr>
          </thead>
          <tbody>
{environment_data_access_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="reviewer-acceptance-checklist">
      <h2 id="reviewer-acceptance-checklist">Reviewer Acceptance Checklist</h2>
      <div class="wide-panel">
        <p>Private-site version of the README readiness checklist. Use it before accepting the package as reader-ready; it does not authorize public release, KG citation, final prose, or method recommendation.</p>
        <table class="wide-table acceptance-checklist-table">
          <thead>
            <tr><th>Acceptance item</th><th>Evidence to inspect</th><th>Reject private review readiness if</th></tr>
          </thead>
          <tbody>
{reviewer_acceptance_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="reviewer-front-door">
      <h2 id="reviewer-front-door">Reviewer Front Door</h2>
      <div class="wide-panel">
        <p>Private-site version of the README first 60-second route. Use it to separate reading, checking, tracing, and release decisions before interpreting the empirical evidence.</p>
        <table class="wide-table reviewer-front-door-table">
          <thead>
            <tr><th>Lane</th><th>Open first</th><th>Reader action</th><th>Safe takeaway</th><th>Closed boundary</th></tr>
          </thead>
          <tbody>
{reviewer_front_door_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="review-at-a-glance">
      <h2 id="review-at-a-glance">Review At A Glance</h2>
      <div class="wide-panel">
        <p>Private-site version of the README first 30-second review map. Use this table to decide where to start, which question the surface answers, and which boundary remains closed before interpreting method evidence.</p>
        <table class="wide-table review-glance-table">
          <thead>
            <tr><th>Review need</th><th>What to read</th><th>What it answers</th><th>Boundary</th></tr>
          </thead>
          <tbody>
{review_at_a_glance_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="first-ten-minutes-review-protocol">
      <h2 id="first-ten-minutes-review-protocol">First 10 Minutes Review Protocol</h2>
      <div class="wide-panel">
        <p>Private-site version of the README acceptance-check driven route. Use it before accepting the package as reader-ready, and keep public release, final method selection, KG citation, and GitHub Pages publication closed unless a separate authorization record opens them.</p>
        <table class="wide-table ten-minute-table">
          <thead>
            <tr><th>Minute</th><th>Review action</th><th>Artifact</th><th>Acceptance check</th><th>Stop if missing</th></tr>
          </thead>
          <tbody>
{first_ten_minute_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="reader-contract">
      <h2 id="reader-contract">Reader Contract</h2>
      <div class="wide-panel">
        <p>Read this document in four layers before interpreting results or release state. This private-site table mirrors the Research Document contract and keeps the empirical object, observed pattern, negative evidence, and traceability/release boundary separate.</p>
        <table class="wide-table reader-contract-table">
          <thead>
            <tr><th>Reading layer</th><th>Reader question</th><th>Safe reading</th><th>Boundary</th></tr>
          </thead>
          <tbody>
{reader_contract_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="result-interpretation-guide">
      <h2 id="result-interpretation-guide">Result interpretation guide</h2>
      <div class="interpretation-grid">
{interpretation_html}
      </div>
    </section>

    <section aria-labelledby="research-question-answer-map">
      <h2 id="research-question-answer-map">Research Question Answer Map</h2>
      <div class="wide-panel">
        <p>Research Document route into the research question answer map. Use this table to inspect each study question, the evidence-supported answer, the evidence anchor, and the stronger reading that remains closed.</p>
        <table class="wide-table">
          <thead>
            <tr><th>Research question</th><th>Evidence-supported answer</th><th>Evidence anchor</th><th>Closed reading</th></tr>
          </thead>
          <tbody>
{research_question_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="contribution-finding-snapshot">
      <h2 id="contribution-finding-snapshot">Contribution And Finding Snapshot</h2>
      <div class="wide-panel">
        <p>Research Document route into the contribution and finding map. Use this table to inspect the reader-safe statement, evidence anchor, and closed reading for each core study contribution before interpreting method or release claims.</p>
        <table class="wide-table contribution-table">
          <thead>
            <tr><th>Contribution or finding</th><th>Reader-safe statement</th><th>Evidence anchor</th><th>Closed reading</th></tr>
          </thead>
          <tbody>
{contribution_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="paper-architecture-review-contract">
      <h2 id="paper-architecture-review-contract">Paper Architecture And Review Contract</h2>
      <div class="wide-panel">
        <p>README-level route into the main article review contract. Use this table to choose the right review surface, reader job, and closed boundary before reading method evidence or release state.</p>
        <table class="wide-table paper-architecture-table">
          <thead>
            <tr><th>Surface</th><th>Reader job</th><th>Boundary</th><th>Source basis</th></tr>
          </thead>
          <tbody>
{paper_architecture_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="guarantee-boundary-snapshot">
      <h2 id="guarantee-boundary-snapshot">Guarantee Boundary Snapshot</h2>
      <div class="wide-panel">
        <p>Main-article route into the Research Document guarantee boundary ledger. Use this table before interpreting marginal coverage, empirical coverage, group diagnostics, frontier evidence, or Venn-Abers bridge evidence.</p>
        <table class="wide-table">
          <thead>
            <tr><th>Topic</th><th>Article statement</th><th>Closed reading</th></tr>
          </thead>
          <tbody>
{guarantee_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="reviewer-decision-queue">
      <h2 id="reviewer-decision-queue">Reviewer decision queue</h2>
      <div class="decision-grid">
{decision_html}
      </div>
    </section>

    <section aria-labelledby="claim-safe-reading-map">
      <h2 id="claim-safe-reading-map">Claim-Safe Reading Map</h2>
      <div class="wide-panel">
        <p>README-level route into the Research Document guardrails. Use this table before converting descriptive evidence into article, supplement, README, site, or KG language.</p>
        <table class="wide-table claim-map-table">
          <thead>
            <tr><th>Reader question</th><th>Allowed wording</th><th>Evidence gate</th><th>Blocked reading</th></tr>
          </thead>
          <tbody>
{claim_safe_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="claim-evidence-verification-snapshot">
      <h2 id="claim-evidence-verification-snapshot">Claim-Evidence Verification Snapshot</h2>
      <div class="wide-panel">
        <p>Private-site route into <code>publication_claim_evidence_verification_matrix</code>. Each row shows the reader-safe sentence, the support gate that must travel with it, and the overclaim that remains blocked.</p>
        <table class="wide-table claim-evidence-table">
          <thead>
            <tr><th>Matrix row</th><th>Claim type</th><th>Allowed sentence</th><th>Support gate</th><th>Overclaim blocked</th></tr>
          </thead>
          <tbody>
{claim_evidence_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="repository-map">
      <h2 id="repository-map">Repository Map</h2>
      <div class="wide-panel">
        <p>Use this table to choose the concrete private-package path for each review job. Package path links are review aids only; they do not authorize public visibility, citable status, or GitHub Pages publication.</p>
        <table class="wide-table repository-map-table">
          <thead>
            <tr><th>Private review package item</th><th>Package path</th><th>Review job</th><th>Current review status</th></tr>
          </thead>
          <tbody>
{repository_map_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="artifact-entry-points">
      <h2 id="artifact-entry-points">Artifact entry points</h2>
      <div class="wide-panel">
        <p>Use this map to choose the right file for each review task before treating any draft surface as publication-ready.</p>
        <table class="wide-table">
          <thead>
            <tr><th>Entry point</th><th>Reader job</th><th>Boundary</th></tr>
          </thead>
          <tbody>
{artifact_entry_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="provenance-graph-log-entry-points">
      <h2 id="provenance-graph-log-entry-points">Provenance graph and log entry points</h2>
      <div class="wide-panel">
        <p>Use these review-only files to inspect data flow, control flow, dependency structure, ontology, and the data scientist log. They improve auditability without opening new experiments, method recommendation, public release, or final citable KG status.</p>
        <table class="wide-table">
          <thead>
            <tr><th>Review task</th><th>Artifact</th><th>Reader job</th><th>Boundary</th></tr>
          </thead>
          <tbody>
{provenance_graph_log_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="review-triad">
      <h2 id="review-triad">Article / Supplement / Knowledge Graph review triad</h2>
      <div class="triad">
{triptych_html}
      </div>
    </section>

    <section aria-labelledby="article-supplement-evidence-crosswalk">
      <h2 id="article-supplement-evidence-crosswalk">Article-supplement evidence crosswalk</h2>
      <div class="wide-panel">
        <p>The main article stays compact. This table points each major reader-facing surface to the supporting supplement area and the stronger claim that remains closed.</p>
        <table class="wide-table">
          <thead>
            <tr><th>Main article surface</th><th>README pointer</th><th>Supplement pointer</th><th>Closed claim</th></tr>
          </thead>
          <tbody>
{crosswalk_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="review-lanes">
      <h2 id="review-lanes">Review lanes</h2>
      <div class="lanes">
{lane_html}
      </div>
    </section>

    <section class="evidence" aria-labelledby="claim-boundaries">
      <div class="panel">
        <h2 id="claim-boundaries">Claim boundaries</h2>
        <table>
          <tbody>
{boundary_html}
          </tbody>
        </table>
        <p class="note">These boundaries are package-level controls. They do not alter the empirical results.</p>
      </div>
      <div class="panel">
        <h2>Knowledge graph entry point</h2>
        <p>The KG browser is the primary navigable supplement candidate for tracing nodes, relations, edge confidence, and provenance. Start with <a href="kg_browser.html">Knowledge graph browser</a> guided presets for the Final selected-method gate, Venn-Abers bridge gate, Claim/evidence matrix, Claim-safe README map, Research Document guardrail, Private package manifest, and KG quality summary; then inspect <a href="../knowledge_graph/quality_summary.json">KG quality summary</a> for graph-level audit metrics.</p>
      </div>
    </section>
  </main>
</body>
</html>
"""


def first_text(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def clipped(value: Any, max_chars: int = 420) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def site_claim_text(value: Any, max_chars: int = 260) -> str:
    text = clipped(value, max_chars=max_chars)
    return re.sub(r"\bwinner\b", "selected method", text, flags=re.IGNORECASE)


KG_SEMANTIC_ZONE_BY_TYPE = {
    "audit": "evidence",
    "catalog": "governance",
    "claim_requirement": "claim",
    "commit": "governance",
    "config": "execution",
    "dataset": "data",
    "dataset_family": "data",
    "dataset_profile": "data",
    "decision": "governance",
    "endpoint_caveat": "diagnostic",
    "endpoint_result": "diagnostic",
    "endpoint_state": "diagnostic",
    "graph": "governance",
    "log": "execution",
    "manifest": "governance",
    "manuscript_claim": "claim",
    "method": "method",
    "method_config": "method",
    "method_report": "method",
    "method_spec": "method",
    "methodology_control": "governance",
    "metric": "metric",
    "model": "method",
    "module": "execution",
    "openml_review_decision": "data",
    "paper_gate": "claim",
    "policy": "governance",
    "publication_activation_check": "governance",
    "publication_audit_artifact": "governance",
    "publication_auditor_contract_rule": "governance",
    "publication_deliverable": "governance",
    "publication_design_requirement": "governance",
    "publication_quality_check": "governance",
    "publication_surface": "governance",
    "publication_triptych_component": "governance",
    "report": "evidence",
    "reviewer_perspective": "governance",
    "run_registry": "execution",
    "source": "data",
}

KG_ZONE_ORDER = (
    "claim",
    "method",
    "data",
    "evidence",
    "diagnostic",
    "metric",
    "governance",
    "execution",
    "other",
)

KG_ZONE_PALETTE = {
    "claim": "#8a5a00",
    "method": "#0f766e",
    "data": "#2563a8",
    "evidence": "#3f3a2f",
    "diagnostic": "#a0442f",
    "metric": "#5f6472",
    "governance": "#273449",
    "execution": "#6f5a2a",
    "other": "#7a7f89",
}


def semantic_zone(node_type_value: str) -> str:
    return KG_SEMANTIC_ZONE_BY_TYPE.get(node_type_value, "other")


def node_type(node_id: str) -> str:
    if ":" not in node_id:
        return "node"
    return node_id.split(":", 1)[0]


def compact_node(row: dict[str, Any]) -> dict[str, Any]:
    node_id = str(row.get("id") or "")
    observations = row.get("observations") if isinstance(row.get("observations"), list) else []
    label = (
        first_text(row, ("label", "name", "title", "dataset_id", "method_id"))
        or node_id
    )
    source_path = first_text(
        row,
        (
            "path",
            "source_path",
            "audit_path",
            "report_path",
            "profile_path",
            "config_path",
            "artifact_path",
        ),
    )
    summary = (
        first_text(row, ("summary", "notes", "description"))
        or (str(observations[0]) if observations else "")
    )
    return {
        "id": node_id,
        "type": str(row.get("type") or node_type(node_id)),
        "label": clipped(label, 160),
        "summary": clipped(summary, 700),
        "source_path": source_path,
        "observation_count": len(observations),
    }


def compact_edge(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": str(row.get("source") or ""),
        "target": str(row.get("target") or ""),
        "relation": str(row.get("relation") or ""),
        "confidence": row.get("confidence"),
        "provenance_id": row.get("provenance_id"),
        "evidence_kind": row.get("evidence_kind"),
        "evidence_path": row.get("evidence_path"),
        "evidence": row.get("evidence"),
        "multiplicity": row.get("multiplicity"),
    }


def build_kg_browser_payload(package_root: Path) -> dict[str, Any]:
    graph_path = package_root / "knowledge_graph/knowledge_graph.json"
    quality_path = package_root / "knowledge_graph/quality_summary.json"
    graph = read_json(graph_path)
    quality = read_json(quality_path)
    nodes = [compact_node(row) for row in graph.get("nodes", []) if row.get("id")]
    edges = [
        compact_edge(row)
        for row in graph.get("edges", [])
        if row.get("source") and row.get("target") and row.get("relation")
    ]
    type_counts = Counter(row["type"] for row in nodes)
    relation_counts = Counter(row["relation"] for row in edges)
    adjacency: dict[str, int] = defaultdict(int)
    for edge in edges:
        adjacency[edge["source"]] += 1
        adjacency[edge["target"]] += 1
    zone_offsets: dict[str, int] = defaultdict(int)
    zone_totals = Counter(semantic_zone(row["type"]) for row in nodes)
    zone_index = {zone: index for index, zone in enumerate(KG_ZONE_ORDER)}
    for node in nodes:
        zone = semantic_zone(node["type"])
        slot = zone_offsets[zone]
        zone_offsets[zone] += 1
        ring = zone_index.get(zone, len(KG_ZONE_ORDER) - 1)
        zone_total = max(1, zone_totals[zone])
        angle = (2 * math.pi * ring / len(KG_ZONE_ORDER)) + (
            2 * math.pi * slot / zone_total
        )
        radius = 135 + (ring * 42) + ((slot % 7) * 9)
        degree = int(adjacency[node["id"]])
        node.update(
            {
                "degree": degree,
                "semantic_zone": zone,
                "x": round(math.cos(angle) * radius, 3),
                "y": round(math.sin(angle) * radius, 3),
                "size": round(min(18.0, 4.0 + math.sqrt(max(1, degree)) / 1.7), 3),
                "color": KG_ZONE_PALETTE.get(zone, KG_ZONE_PALETTE["other"]),
            }
        )
    high_degree_nodes = sorted(
        (
            {
                "id": node["id"],
                "label": node["label"],
                "type": node["type"],
                "degree": adjacency[node["id"]],
            }
            for node in nodes
        ),
        key=lambda row: (-int(row["degree"]), row["id"]),
    )[:50]
    node_by_id = {node["id"]: node for node in nodes}
    guided_trace_presets = []
    for row in KG_GUIDED_TRACE_PRESET_SPECS:
        node = node_by_id.get(str(row["node_id"]))
        if not node:
            continue
        preset_edges = [
            edge
            for edge in edges
            if edge["source"] == node["id"] or edge["target"] == node["id"]
        ]
        route_node_ids = [node["id"]]
        for edge in sorted(
            preset_edges,
            key=lambda edge: (
                0
                if edge["relation"]
                in {"SUPPORTED_BY", "BLOCKED_BY", "DERIVED_FROM", "RECORDED_IN"}
                else 1,
                -float(edge.get("confidence") or 0.0),
                edge["relation"],
                edge["source"],
                edge["target"],
            ),
        ):
            other_id = edge["target"] if edge["source"] == node["id"] else edge["source"]
            if other_id not in route_node_ids and other_id in node_by_id:
                route_node_ids.append(other_id)
            if len(route_node_ids) >= 14:
                break
        guided_trace_presets.append(
            {
                "preset_id": str(row["preset_id"]),
                "label": str(row["label"]),
                "node_id": str(row["node_id"]),
                "node_type": node["type"],
                "node_label": node["label"],
                "reader_job": str(row["reader_job"]),
                "route_node_ids": route_node_ids,
                "route_edge_count": len(preset_edges),
                "default_depth": 1,
            }
        )
    return {
        "schema": "cpfi_publication_kg_browser_data_v2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_type_count": len(type_counts),
            "relation_type_count": len(relation_counts),
            "isolated_node_count": (
                quality.get("graph", {}).get("isolated_node_count")
            ),
            "average_edge_confidence": (
                quality.get("traceability", {}).get("average_edge_confidence")
            ),
            "edge_selector_provenance_coverage": (
                quality.get("traceability", {}).get(
                    "edge_selector_provenance_coverage"
                )
            ),
            "guided_trace_preset_count": len(guided_trace_presets),
        },
        "visual_palette": {
            "background": "#f7f3ea",
            "ink": "#1d2430",
            "muted": "#667085",
            "zones": KG_ZONE_PALETTE,
            "zone_order": list(KG_ZONE_ORDER),
        },
        "type_counts": dict(sorted(type_counts.items())),
        "semantic_zone_counts": dict(sorted(zone_totals.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "high_degree_nodes": high_degree_nodes,
        "guided_trace_presets": guided_trace_presets,
        "nodes": nodes,
        "edges": edges,
    }


def render_kg_browser_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CPFI Knowledge Graph Browser</title>
  <script defer src="https://cdn.jsdelivr.net/npm/graphology@0.25.4/dist/graphology.umd.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/sigma@2.4.0/build/sigma.min.js"></script>
  <style>
    :root { color-scheme: light; --paper: #f7f3ea; --paper-2: #eee7d9; --ink: #1d2430; --muted: #667085; --line: #d8cfbd; --panel: #fffdf8; --accent: #0f766e; --amber: #9a6500; --danger: #a0442f; --blue: #2563a8; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Aptos", "Segoe UI", ui-sans-serif, system-ui, sans-serif; color: var(--ink); background: var(--paper); }
    body::before { content: ""; position: fixed; inset: 0; pointer-events: none; opacity: .28; background-image: linear-gradient(rgba(29,36,48,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(29,36,48,.025) 1px, transparent 1px); background-size: 28px 28px; }
    header { position: relative; z-index: 1; padding: 26px 32px 18px; border-bottom: 1px solid var(--line); background: rgba(255,253,248,.94); }
    h1 { margin: 0 0 8px; font-family: Georgia, "Times New Roman", serif; font-size: clamp(26px, 3vw, 42px); line-height: 1.05; letter-spacing: 0; }
    h2 { margin: 0 0 10px; font-size: 15px; letter-spacing: 0; }
    h3 { margin: 0; font-size: 14px; letter-spacing: 0; }
    a { color: #165aa7; font-weight: 720; }
    button, input, select { font: inherit; }
    .sub { color: var(--muted); margin: 0; max-width: 1120px; line-height: 1.55; }
    .topline { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; color: var(--muted); font-size: 13px; margin-bottom: 8px; }
    .pill { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--line); border-radius: 999px; padding: 5px 9px; background: #fffaf0; color: #4e3d1c; font-weight: 720; }
    .stats { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 1px; padding: 0 32px; background: var(--line); border-bottom: 1px solid var(--line); }
    .stat { background: var(--panel); padding: 14px 16px; min-width: 0; }
    .stat b { display: block; font-family: Georgia, "Times New Roman", serif; font-size: 24px; line-height: 1; overflow-wrap: anywhere; }
    .stat span { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
    main { position: relative; z-index: 1; display: grid; grid-template-columns: minmax(280px, 360px) minmax(420px, 1fr) minmax(300px, 420px); gap: 0; min-height: calc(100vh - 178px); }
    aside, section { min-width: 0; }
    aside { border-right: 1px solid var(--line); background: rgba(255,253,248,.88); padding: 18px; overflow: auto; max-height: calc(100vh - 178px); }
    .right { border-left: 1px solid var(--line); border-right: 0; }
    .canvas-column { display: grid; grid-template-rows: auto minmax(420px, 1fr) auto; min-height: calc(100vh - 178px); background: #f4efe4; }
    .graph-toolbar { display: flex; gap: 10px; align-items: center; justify-content: space-between; flex-wrap: wrap; padding: 12px 16px; border-bottom: 1px solid var(--line); background: rgba(255,253,248,.9); }
    .graph-toolbar strong { font-size: 14px; }
    .toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .graph-stage { position: relative; min-height: 440px; overflow: hidden; background: radial-gradient(circle at 50% 46%, rgba(255,253,248,.98), rgba(238,231,217,.72)); }
    #sigmaLayer, #fallbackCanvas { position: absolute; inset: 0; width: 100%; height: 100%; }
    #sigmaLayer { display: none; }
    #sigmaLayer.active { display: block; }
    #fallbackCanvas { display: block; }
    .canvas-footer { padding: 12px 16px; border-top: 1px solid var(--line); background: rgba(255,253,248,.9); color: var(--muted); font-size: 13px; display: flex; gap: 14px; flex-wrap: wrap; }
    .presets, .controls, .results, .edges, .fallback-table-wrap { display: grid; gap: 10px; }
    .presets { margin-bottom: 16px; }
    .preset, .result, .edge, .detail, .guide-row { border: 1px solid var(--line); border-radius: 8px; background: rgba(255,253,248,.92); }
    .preset, .result { text-align: left; padding: 11px; cursor: pointer; }
    .preset { font: inherit; }
    .preset:hover, .result:hover, .result.active { border-color: var(--accent); box-shadow: inset 3px 0 0 var(--accent); }
    .preset strong, .result strong { display: block; overflow-wrap: anywhere; }
    .preset span, .summary { display: block; color: var(--muted); font-size: 12px; margin-top: 5px; line-height: 1.45; }
    .controls { margin-bottom: 16px; }
    label { display: grid; gap: 5px; color: var(--muted); font-size: 12px; font-weight: 720; text-transform: uppercase; letter-spacing: .04em; }
    input, select { width: 100%; border: 1px solid var(--line); border-radius: 7px; padding: 9px 10px; background: #fffdf8; color: var(--ink); }
    input[type="range"] { padding: 0; accent-color: var(--accent); }
    .button { border: 1px solid var(--line); border-radius: 7px; background: #fffdf8; color: var(--ink); padding: 8px 10px; cursor: pointer; font-weight: 720; }
    .button:hover { border-color: var(--accent); color: var(--accent); }
    .type { color: var(--accent); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; }
    .detail { padding: 16px; margin-bottom: 14px; }
    .detail h2 { font-family: Georgia, "Times New Roman", serif; font-size: 22px; line-height: 1.1; margin-top: 4px; overflow-wrap: anywhere; }
    .detail p { color: var(--muted); line-height: 1.55; }
    .edge { padding: 11px; }
    .edge strong { display: block; margin: 4px 0; overflow-wrap: anywhere; }
    .guide { display: grid; gap: 10px; margin-top: 12px; }
    .guide-row { padding: 10px; }
    .guide-row strong { display: block; }
    .guide-row span { color: var(--muted); font-size: 13px; line-height: 1.45; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 12px; background: #fffdf8; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
    th, td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
    th { color: #4e3d1c; background: #f7eddc; }
    tr:last-child td { border-bottom: 0; }
    code { background: #f5efe3; border: 1px solid #e5dccb; padding: 2px 4px; border-radius: 4px; overflow-wrap: anywhere; }
    .muted { color: var(--muted); }
    @media (max-width: 1120px) {
      .stats { grid-template-columns: repeat(2, minmax(120px, 1fr)); padding: 0; }
      main { grid-template-columns: 1fr; }
      aside, .right { max-height: none; border: 0; border-bottom: 1px solid var(--line); }
      .canvas-column { min-height: 560px; order: -1; }
      .graph-stage { min-height: 460px; }
    }
    @media (max-width: 520px) {
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .stat:last-child { grid-column: 1 / -1; }
    }
  </style>
</head>
<body>
  <header>
    <div class="topline"><span class="pill">Research Atlas</span><span class="pill">Traversable KG v2</span><span class="pill">No method recommendation</span></div>
    <h1>CPFI Knowledge Graph Browser</h1>
    <p class="sub">Private supplementary graph surface backed by <code>kg_browser_data.json</code>. Public release, final citable status, and method recommendation remain closed. Use the Research Atlas Graph Canvas to traverse claim, method, dataset, report, audit, metric, and provenance neighborhoods without turning the graph into a claim generator.</p>
    <p class="sub"><a href="index.html">Back to private review portal</a> · <a href="../knowledge_graph/quality_summary.json">Open KG quality summary</a></p>
  </header>
  <div class="stats" id="stats"></div>
  <main>
    <aside>
      <div class="presets" id="presets" aria-label="Guided trace presets">
        <h2>Guided trace presets</h2>
        <p class="muted">Start with Final selected-method gate, Venn-Abers bridge gate, or Claim-safe README map; interactive buttons load from <code>kg_browser_data.json</code>.</p>
      </div>
      <div class="controls">
        <label>Search nodes<input id="search" placeholder="dataset, method, claim, report..."></label>
        <label>Node type<select id="typeFilter"><option value="">All types</option></select></label>
        <label>Relation filter<select id="relationFilter"><option value="">All relations</option></select></label>
        <label>Graph depth<select id="depthFilter"><option value="1">One hop</option><option value="2">Two hops</option></select></label>
        <label>Confidence floor <span id="confidenceReadout">0.00</span><input id="confidenceFilter" type="range" min="0" max="1" step="0.01" value="0"></label>
      </div>
      <div id="results" aria-live="polite"></div>
    </aside>
    <section class="canvas-column" aria-label="Research Atlas Graph Canvas">
      <div class="graph-toolbar">
        <strong>Research Atlas Graph Canvas</strong>
        <div class="toolbar-actions">
          <button class="button" id="fitGraph" type="button">Fit graph</button>
          <button class="button" id="resetGraph" type="button">Reset view</button>
        </div>
      </div>
      <div class="graph-stage">
        <canvas id="fallbackCanvas" aria-label="Interactive fallback graph canvas"></canvas>
        <div id="sigmaLayer" aria-hidden="true"></div>
      </div>
      <div class="canvas-footer">
        <span id="rendererStatus">Renderer: initializing</span>
        <span id="subgraphStatus">Subgraph: n/a</span>
        <span>Drag to pan, wheel to zoom, click a node to traverse.</span>
      </div>
    </section>
    <aside class="right">
      <div class="detail" id="detail">
        <h2>How to read this graph</h2>
        <p class="muted">Use this browser as a traceability surface, not as a claim generator. Start with a guided preset, inspect the selected node, then use neighboring edges to move from a claim or gate to the reports, datasets, methods, citations, scripts, and audits that support or block it.</p>
        <div class="guide">
          <div class="guide-row"><strong>Node</strong><span class="muted">A typed object such as a dataset, method, report, claim, paper gate, source, or manifest.</span></div>
          <div class="guide-row"><strong>Edge</strong><span class="muted">A directed relation between two nodes, for example <code>SUPPORTED_BY</code>, <code>BLOCKED_BY</code>, <code>EVALUATES_METHOD</code>, or <code>RECORDED_IN</code>.</span></div>
          <div class="guide-row"><strong>Confidence and provenance</strong><span class="muted">Each edge carries confidence plus an evidence path or selector so the relation can be traced back to a source artifact.</span></div>
          <div class="guide-row"><strong>Reader route</strong><span class="muted">For claims, follow <code>SUPPORTED_BY</code> and <code>BLOCKED_BY</code>. For method behavior, follow method, report, dataset, metric, and paper-gate neighborhoods. Public release and method recommendation remain closed.</span></div>
        </div>
      </div>
      <h2>Neighborhood Edges</h2>
      <div class="edges" id="edges"></div>
      <h2 style="margin-top:16px">Fallback evidence table</h2>
      <div class="fallback-table-wrap" id="fallbackTable"></div>
    </aside>
  </main>
  <script>
    const state = {
      data: null,
      selected: null,
      nodeById: new Map(),
      edgeByNode: new Map(),
      relationFilter: '',
      typeFilter: '',
      confidenceFloor: 0,
      depth: 1,
      subgraph: { nodes: [], edges: [] },
      renderer: null,
      screenNodes: [],
      view: { zoom: 1, dx: 0, dy: 0 },
      dragging: false,
      lastPointer: null
    };
    const fmt = value => typeof value === 'number' ? value.toLocaleString() : String(value ?? 'n/a');
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const confidenceValue = edge => Number(edge.confidence ?? 0);
    const edgePasses = edge => {
      if (state.relationFilter && edge.relation !== state.relationFilter) return false;
      return confidenceValue(edge) >= state.confidenceFloor;
    };
    function addEdgeIndex(edge) {
      for (const id of [edge.source, edge.target]) {
        if (!state.edgeByNode.has(id)) state.edgeByNode.set(id, []);
        state.edgeByNode.get(id).push(edge);
      }
    }
    function renderStats() {
      const s = state.data.summary;
      const cards = [
        ['Nodes', s.node_count],
        ['Edges', s.edge_count],
        ['Node types', s.node_type_count],
        ['Relation types', s.relation_type_count],
        ['Avg. edge confidence', Number(s.average_edge_confidence || 0).toFixed(4)]
      ];
      document.getElementById('stats').innerHTML = cards.map(([k,v]) => `<div class="stat"><b>${fmt(v)}</b><span>${escapeHtml(k)}</span></div>`).join('');
    }
    function renderPresets() {
      const presets = state.data.guided_trace_presets || [];
      const body = presets.map(preset => `
        <button class="preset" data-node-id="${escapeHtml(preset.node_id)}">
          <strong>${escapeHtml(preset.label)}</strong>
          <span>${escapeHtml(preset.reader_job)}</span>
          <span><code>${escapeHtml(preset.node_id)}</code></span>
          <span>${fmt(preset.route_edge_count)} adjacent edges in route seed</span>
        </button>`).join('');
      document.getElementById('presets').innerHTML = `<h2>Guided trace presets</h2>${body}`;
      document.querySelectorAll('.preset').forEach(el => el.addEventListener('click', () => {
        document.getElementById('search').value = '';
        document.getElementById('typeFilter').value = '';
        document.getElementById('relationFilter').value = '';
        state.relationFilter = '';
        selectNode(el.dataset.nodeId);
      }));
    }
    function renderTypeFilter() {
      const select = document.getElementById('typeFilter');
      Object.entries(state.data.type_counts).forEach(([type, count]) => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = `${type} (${count})`;
        select.appendChild(option);
      });
    }
    function renderRelationFilter() {
      const select = document.getElementById('relationFilter');
      Object.entries(state.data.relation_counts).forEach(([relation, count]) => {
        const option = document.createElement('option');
        option.value = relation;
        option.textContent = `${relation} (${count})`;
        select.appendChild(option);
      });
    }
    function matches(node, query, type) {
      if (type && node.type !== type) return false;
      if (!query) return true;
      const haystack = `${node.id} ${node.label} ${node.summary} ${node.source_path || ''}`.toLowerCase();
      return haystack.includes(query.toLowerCase());
    }
    function renderResults() {
      const query = document.getElementById('search').value.trim();
      const type = document.getElementById('typeFilter').value;
      const nodes = state.data.nodes.filter(node => matches(node, query, type)).slice(0, 100);
      document.getElementById('results').innerHTML = nodes.map(node => `
        <div class="result ${state.selected === node.id ? 'active' : ''}" data-id="${escapeHtml(node.id)}">
          <div class="type">${escapeHtml(node.type)}</div>
          <strong>${escapeHtml(node.label)}</strong>
          <div><code>${escapeHtml(node.id)}</code></div>
          <div class="summary">${escapeHtml(node.summary)}</div>
        </div>`).join('');
      document.querySelectorAll('.result').forEach(el => el.addEventListener('click', () => selectNode(el.dataset.id)));
    }
    function neighborhood(rootId) {
      const visited = new Set();
      const queue = [{ id: rootId, depth: 0 }];
      const edgeKeys = new Set();
      const chosenEdges = [];
      while (queue.length && visited.size < 180) {
        const current = queue.shift();
        if (!current || visited.has(current.id)) continue;
        visited.add(current.id);
        if (current.depth >= state.depth) continue;
        for (const edge of state.edgeByNode.get(current.id) || []) {
          if (!edgePasses(edge)) continue;
          const otherId = edge.source === current.id ? edge.target : edge.source;
          const key = `${edge.source}|${edge.relation}|${edge.target}|${edge.provenance_id || ''}`;
          if (!edgeKeys.has(key)) {
            edgeKeys.add(key);
            chosenEdges.push(edge);
          }
          if (!visited.has(otherId) && queue.length < 320) {
            queue.push({ id: otherId, depth: current.depth + 1 });
          }
        }
      }
      const nodes = Array.from(visited).map(id => state.nodeById.get(id)).filter(Boolean);
      return { nodes, edges: chosenEdges.slice(0, 520) };
    }
    function defaultSubgraph() {
      const ids = new Set();
      (state.data.guided_trace_presets || []).forEach(p => ids.add(p.node_id));
      (state.data.high_degree_nodes || []).slice(0, 42).forEach(row => ids.add(row.id));
      const nodes = Array.from(ids).map(id => state.nodeById.get(id)).filter(Boolean);
      const idSet = new Set(nodes.map(node => node.id));
      const edges = state.data.edges.filter(edge => idSet.has(edge.source) && idSet.has(edge.target)).slice(0, 180);
      return { nodes, edges };
    }
    function updateSubgraph() {
      state.subgraph = state.selected ? neighborhood(state.selected) : defaultSubgraph();
      document.getElementById('subgraphStatus').textContent = `Subgraph: ${fmt(state.subgraph.nodes.length)} nodes, ${fmt(state.subgraph.edges.length)} edges`;
      renderGraph();
      renderFallbackTable();
    }
    function selectNode(id, pushHistory = true) {
      state.selected = id;
      const node = state.nodeById.get(id);
      if (!node) return;
      const edges = (state.edgeByNode.get(id) || []).slice(0, 250);
      document.getElementById('detail').innerHTML = `
        <div class="type">${escapeHtml(node.type)}</div>
        <h2>${escapeHtml(node.label)}</h2>
        <p><code>${escapeHtml(node.id)}</code></p>
        <p>${escapeHtml(node.summary)}</p>
        <p class="muted">Zone: ${escapeHtml(node.semantic_zone)} | Degree: ${fmt(node.degree)} | Observations: ${fmt(node.observation_count)}${node.source_path ? ` | Source: <code>${escapeHtml(node.source_path)}</code>` : ''}</p>`;
      document.getElementById('edges').innerHTML = edges.map(edge => {
        const otherId = edge.source === id ? edge.target : edge.source;
        const other = state.nodeById.get(otherId) || { label: otherId, type: 'node' };
        return `<div class="edge">
          <div class="type">${escapeHtml(edge.relation)}</div>
          <div><code>${escapeHtml(edge.source)}</code> -> <code>${escapeHtml(edge.target)}</code></div>
          <strong>${escapeHtml(other.label)}</strong> <span class="muted">(${escapeHtml(other.type)})</span>
          <div class="summary">Confidence: ${fmt(edge.confidence)} | Evidence: <code>${escapeHtml(edge.evidence_path || edge.evidence || 'n/a')}</code></div>
          <div class="summary">Edge provenance: <code>${escapeHtml(edge.provenance_id || 'n/a')}</code>; kind: <code>${escapeHtml(edge.evidence_kind || 'n/a')}</code></div>
        </div>`;
      }).join('') || '<p class="muted">No neighborhood edges found.</p>';
      if (pushHistory) {
        const url = new URL(window.location.href);
        url.searchParams.set('node', id);
        window.history.replaceState({}, '', url);
      }
      renderResults();
      updateSubgraph();
    }
    function renderFallbackTable() {
      const rows = state.subgraph.edges.slice(0, 24).map(edge => `
        <tr>
          <td><code>${escapeHtml(edge.source)}</code></td>
          <td>${escapeHtml(edge.relation)}</td>
          <td><code>${escapeHtml(edge.target)}</code></td>
          <td>${fmt(edge.confidence)}</td>
        </tr>`).join('');
      document.getElementById('fallbackTable').innerHTML = `
        <table aria-label="Fallback evidence table">
          <thead><tr><th>Source</th><th>Relation</th><th>Target</th><th>Confidence</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="4">No filtered edges.</td></tr>'}</tbody>
        </table>`;
    }
    function renderGraph() {
      drawCanvasGraph();
      tryRenderSigma();
    }
    function tryRenderSigma() {
      const layer = document.getElementById('sigmaLayer');
      const Graphology = window.graphology && (window.graphology.Graph || window.graphology);
      const SigmaCtor = window.Sigma || window.sigma;
      if (!Graphology || !SigmaCtor || !state.subgraph.nodes.length) {
        layer.classList.remove('active');
        document.getElementById('rendererStatus').textContent = 'Renderer: Canvas fallback active';
        return;
      }
      try {
        if (state.renderer && typeof state.renderer.kill === 'function') state.renderer.kill();
        layer.innerHTML = '';
        const graph = new Graphology({ type: 'directed', multi: true });
        state.subgraph.nodes.forEach(node => {
          graph.addNode(node.id, {
            label: node.label,
            x: Number(node.x || 0),
            y: Number(node.y || 0),
            size: Number(node.size || 5),
            color: node.color || '#667085'
          });
        });
        state.subgraph.edges.forEach((edge, index) => {
          if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
            graph.addDirectedEdgeWithKey(`e${index}`, edge.source, edge.target, {
              size: 1 + Math.max(0, confidenceValue(edge) * 2),
              color: edge.relation === 'BLOCKED_BY' ? '#a0442f' : '#8f8a7f'
            });
          }
        });
        state.renderer = new SigmaCtor(graph, layer, { renderEdgeLabels: false, defaultEdgeType: 'line' });
        layer.classList.add('active');
        document.getElementById('rendererStatus').textContent = 'Renderer: Sigma.js WebGL active, Canvas fallback retained';
      } catch (error) {
        layer.classList.remove('active');
        document.getElementById('rendererStatus').textContent = 'Renderer: Canvas fallback active';
      }
    }
    function drawCanvasGraph() {
      const canvas = document.getElementById('fallbackCanvas');
      const stage = canvas.parentElement;
      const rect = stage.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, rect.width, rect.height);
      const nodes = state.subgraph.nodes;
      const edges = state.subgraph.edges;
      if (!nodes.length) return;
      const xs = nodes.map(node => Number(node.x || 0));
      const ys = nodes.map(node => Number(node.y || 0));
      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      const scale = Math.min(rect.width / Math.max(1, maxX - minX + 160), rect.height / Math.max(1, maxY - minY + 160)) * state.view.zoom;
      const cx = (minX + maxX) / 2;
      const cy = (minY + maxY) / 2;
      const project = node => ({
        x: rect.width / 2 + (Number(node.x || 0) - cx) * scale + state.view.dx,
        y: rect.height / 2 + (Number(node.y || 0) - cy) * scale + state.view.dy
      });
      const positions = new Map(nodes.map(node => [node.id, project(node)]));
      state.screenNodes = nodes.map(node => ({ node, ...positions.get(node.id) }));
      ctx.lineCap = 'round';
      edges.forEach(edge => {
        const a = positions.get(edge.source);
        const b = positions.get(edge.target);
        if (!a || !b) return;
        ctx.beginPath();
        ctx.strokeStyle = edge.relation === 'BLOCKED_BY' ? 'rgba(160,68,47,.42)' : 'rgba(96,88,73,.28)';
        ctx.lineWidth = edge.source === state.selected || edge.target === state.selected ? 1.8 : 1;
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      });
      nodes.forEach(node => {
        const p = positions.get(node.id);
        const selected = node.id === state.selected;
        const radius = selected ? Math.max(8, Number(node.size || 6) + 4) : Math.max(4, Number(node.size || 5));
        ctx.beginPath();
        ctx.fillStyle = node.color || '#667085';
        ctx.strokeStyle = selected ? '#1d2430' : '#fffdf8';
        ctx.lineWidth = selected ? 3 : 1.5;
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        if (selected || node.degree > 300 || nodes.length < 42) {
          ctx.font = selected ? '700 13px Aptos, Segoe UI, sans-serif' : '600 11px Aptos, Segoe UI, sans-serif';
          ctx.fillStyle = '#1d2430';
          ctx.fillText(node.label.slice(0, 34), p.x + radius + 5, p.y + 4);
        }
      });
    }
    function resetView() {
      state.view = { zoom: 1, dx: 0, dy: 0 };
      renderGraph();
    }
    fetch('kg_browser_data.json')
      .then(response => response.json())
      .then(data => {
        state.data = data;
        data.nodes.forEach(node => state.nodeById.set(node.id, node));
        data.edges.forEach(addEdgeIndex);
        renderStats();
        renderPresets();
        renderTypeFilter();
        renderRelationFilter();
        renderResults();
        const params = new URLSearchParams(window.location.search);
        const preset = params.get('preset');
        const presetRow = (data.guided_trace_presets || []).find(row => row.preset_id === preset);
        const startNode = params.get('node') || (presetRow && presetRow.node_id) || (data.guided_trace_presets || [])[0]?.node_id;
        if (startNode) selectNode(startNode, false);
        else updateSubgraph();
      });
    document.getElementById('search').addEventListener('input', renderResults);
    document.getElementById('typeFilter').addEventListener('change', event => { state.typeFilter = event.target.value; renderResults(); });
    document.getElementById('relationFilter').addEventListener('change', event => { state.relationFilter = event.target.value; updateSubgraph(); });
    document.getElementById('depthFilter').addEventListener('change', event => { state.depth = Number(event.target.value || 1); updateSubgraph(); });
    document.getElementById('confidenceFilter').addEventListener('input', event => {
      state.confidenceFloor = Number(event.target.value || 0);
      document.getElementById('confidenceReadout').textContent = state.confidenceFloor.toFixed(2);
      updateSubgraph();
    });
    document.getElementById('fitGraph').addEventListener('click', resetView);
    document.getElementById('resetGraph').addEventListener('click', () => {
      document.getElementById('relationFilter').value = '';
      document.getElementById('confidenceFilter').value = '0';
      document.getElementById('confidenceReadout').textContent = '0.00';
      state.relationFilter = '';
      state.confidenceFloor = 0;
      resetView();
      updateSubgraph();
    });
    const canvas = document.getElementById('fallbackCanvas');
    canvas.addEventListener('click', event => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const hit = state.screenNodes
        .map(row => ({ ...row, d: Math.hypot(row.x - x, row.y - y) }))
        .sort((a, b) => a.d - b.d)[0];
      if (hit && hit.d < 18) selectNode(hit.node.id);
    });
    canvas.addEventListener('wheel', event => {
      event.preventDefault();
      state.view.zoom = Math.max(.35, Math.min(4, state.view.zoom * (event.deltaY < 0 ? 1.08 : .92)));
      renderGraph();
    }, { passive: false });
    canvas.addEventListener('pointerdown', event => {
      state.dragging = true;
      state.lastPointer = { x: event.clientX, y: event.clientY };
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener('pointermove', event => {
      if (!state.dragging || !state.lastPointer) return;
      state.view.dx += event.clientX - state.lastPointer.x;
      state.view.dy += event.clientY - state.lastPointer.y;
      state.lastPointer = { x: event.clientX, y: event.clientY };
      renderGraph();
    });
    canvas.addEventListener('pointerup', () => { state.dragging = false; state.lastPointer = null; });
    window.addEventListener('resize', renderGraph);
  </script>
</body>
</html>
"""


def scan_for_secret_patterns(package_root: Path) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for path in sorted(package_root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.stat().st_size > MAX_SECRET_SCAN_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern_id, regex in SECRET_PATTERNS.items():
            if regex.search(text):
                hits.append(
                    {
                        "package_path": rel(path, package_root),
                        "pattern_id": pattern_id,
                    }
                )
    return hits


def scan_packaged_path_risks(package_root: Path) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for path in sorted(package_root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = rel(path, package_root)
        parts = set(Path(relative).parts)
        suffix = path.suffix.lower()
        if parts & EXCLUDED_PARTS or suffix in EXCLUDED_SUFFIXES:
            hits.append({"package_path": relative, "reason": "cache_raw_or_large_file"})
    return hits


def is_external_or_fragment_link(target: str) -> bool:
    lowered = target.lower()
    return (
        lowered.startswith(("http://", "https://", "mailto:", "javascript:"))
        or lowered.startswith("#")
        or not target
    )


def normalize_local_link(target: str) -> str:
    return target.split("#", 1)[0].split("?", 1)[0]


def boundary_violations_for_text(package_path: str, text: str) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for label in SITE_BOUNDARY_LABELS:
        for match in re.finditer(re.escape(label), text, flags=re.IGNORECASE):
            window = text[match.start() : match.start() + 320]
            if "<code>True</code>" in window or "`True`" in window or ">True<" in window:
                hits.append({"package_path": package_path, "label": label})
                break
    return hits


def audit_html_page_links(package_root: Path, package_path: str) -> dict[str, Any]:
    path = package_root / package_path
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    parser = LinkTargetParser()
    parser.feed(text)
    local_targets = [
        target for target in parser.targets if not is_external_or_fragment_link(target)
    ]
    broken_local_links = []
    for target in local_targets:
        normalized = normalize_local_link(target)
        if not normalized:
            continue
        resolved = (path.parent / normalized).resolve()
        try:
            resolved.relative_to(package_root.resolve())
        except ValueError:
            broken_local_links.append(
                {"target": target, "reason": "link_escapes_package_root"}
            )
            continue
        if not resolved.exists():
            broken_local_links.append(
                {"target": target, "reason": "target_missing"}
            )
    required_phrases = SITE_HTML_REQUIRED_PHRASES.get(package_path, ())
    missing_required_phrases = [
        phrase for phrase in required_phrases if phrase not in text
    ]
    return {
        "package_path": package_path,
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "link_count": len(parser.targets),
        "local_link_count": len(local_targets),
        "broken_local_links": broken_local_links,
        "missing_required_phrases": missing_required_phrases,
        "boundary_violations": boundary_violations_for_text(package_path, text),
        "status": (
            "pass"
            if path.exists()
            and not broken_local_links
            and not missing_required_phrases
            else "fail"
        ),
    }


def audit_private_static_site(
    package_root: Path,
    kg_browser_payload: dict[str, Any],
) -> dict[str, Any]:
    html_rows = [
        audit_html_page_links(package_root, "site/index.html"),
        audit_html_page_links(package_root, "site/kg_browser.html"),
    ]
    kg_data_path = package_root / "site/kg_browser_data.json"
    kg_data_status = "missing"
    kg_data_summary: dict[str, Any] = {}
    if kg_data_path.exists():
        try:
            kg_data = json.loads(kg_data_path.read_text(encoding="utf-8"))
            kg_data_summary = kg_data.get("summary") or {}
            kg_data_status = "pass"
        except json.JSONDecodeError:
            kg_data_status = "json_decode_error"
    expected_kg_summary = kg_browser_payload.get("summary") or {}
    kg_summary_matches = all(
        kg_data_summary.get(key) == expected_kg_summary.get(key)
        for key in ("node_count", "edge_count", "node_type_count", "relation_type_count")
    )
    broken_local_links = [
        {"package_path": row["package_path"], **link}
        for row in html_rows
        for link in row["broken_local_links"]
    ]
    missing_required_phrases = [
        {"package_path": row["package_path"], "phrase": phrase}
        for row in html_rows
        for phrase in row["missing_required_phrases"]
    ]
    boundary_violations = [
        hit for row in html_rows for hit in row["boundary_violations"]
    ]
    index_path = package_root / "site/index.html"
    index_text = (
        index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    )
    missing_visual_layout_guards = [
        guard
        for guard in SITE_VISUAL_SMOKE_LAYOUT_GUARDS
        if guard not in index_text
    ]
    missing_visual_first_screen_phrases = [
        phrase
        for phrase in SITE_VISUAL_SMOKE_FIRST_SCREEN_PHRASES
        if phrase not in index_text
    ]
    visual_smoke_issue_count = (
        len(missing_visual_layout_guards)
        + len(missing_visual_first_screen_phrases)
    )
    visual_smoke_layout_guard_status = (
        "pass" if not missing_visual_layout_guards else "fail"
    )
    visual_smoke_first_screen_status = (
        "pass" if not missing_visual_first_screen_phrases else "fail"
    )
    visual_smoke_status = (
        "pass"
        if visual_smoke_layout_guard_status == "pass"
        and visual_smoke_first_screen_status == "pass"
        else "fail"
    )
    overall_status = (
        "pass"
        if all(row["status"] == "pass" for row in html_rows)
        and kg_data_status == "pass"
        and kg_summary_matches
        and not boundary_violations
        and visual_smoke_status == "pass"
        else "fail"
    )
    return {
        "overall_status": overall_status,
        "html_rows": html_rows,
        "kg_browser_data_status": kg_data_status,
        "kg_browser_summary_matches_payload": kg_summary_matches,
        "kg_browser_data_summary": kg_data_summary,
        "broken_local_links": broken_local_links,
        "missing_required_phrases": missing_required_phrases,
        "boundary_violations": boundary_violations,
        "html_page_count": len(html_rows),
        "local_link_count": sum(row["local_link_count"] for row in html_rows),
        "broken_local_link_count": len(broken_local_links),
        "missing_required_phrase_count": len(missing_required_phrases),
        "boundary_violation_count": len(boundary_violations),
        "visual_smoke_status": visual_smoke_status,
        "visual_smoke_layout_guard_status": visual_smoke_layout_guard_status,
        "visual_smoke_first_screen_status": visual_smoke_first_screen_status,
        "visual_smoke_issue_count": visual_smoke_issue_count,
        "visual_smoke_basis": (
            "static_layout_guards_plus_chromium_desktop_mobile_spot_check"
        ),
        "missing_visual_layout_guards": missing_visual_layout_guards,
        "missing_visual_first_screen_phrases": missing_visual_first_screen_phrases,
    }


def build_private_static_site_navigation_rows(
    private_site_quality: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for html_row in private_site_quality.get("html_rows") or []:
        package_path = str(html_row.get("package_path") or "")
        rows.append(
            {
                "surface_id": package_path.replace("/", "_").replace(".", "_"),
                "package_path": package_path,
                "surface_role": (
                    "private_review_portal"
                    if package_path == "site/index.html"
                    else "private_kg_browser"
                ),
                "local_link_count": int(html_row.get("local_link_count") or 0),
                "broken_local_link_count": len(
                    html_row.get("broken_local_links") or []
                ),
                "missing_required_phrase_count": len(
                    html_row.get("missing_required_phrases") or []
                ),
                "boundary_violation_count": len(
                    html_row.get("boundary_violations") or []
                ),
                "status": html_row.get("status"),
                "reader_job": (
                    "Open the private review portal and follow local package links."
                    if package_path == "site/index.html"
                    else "Use guided KG presets and inspect edge provenance."
                ),
                "boundary": (
                    "Navigation integrity supports private review only; it does "
                    "not authorize public release, GitHub Pages, KG citation, or "
                    "method recommendation."
                ),
            }
        )
    kg_summary = private_site_quality.get("kg_browser_data_summary") or {}
    rows.append(
        {
            "surface_id": "site_kg_browser_data_json",
            "package_path": "site/kg_browser_data.json",
            "surface_role": "private_kg_browser_data",
            "local_link_count": 0,
            "broken_local_link_count": 0,
            "missing_required_phrase_count": 0,
            "boundary_violation_count": 0,
            "status": (
                "pass"
                if private_site_quality.get("kg_browser_data_status") == "pass"
                and private_site_quality.get("kg_browser_summary_matches_payload")
                is True
                else "fail"
            ),
            "reader_job": (
                "Verify that KG browser data exist and match the package KG summary."
            ),
            "node_count": kg_summary.get("node_count"),
            "edge_count": kg_summary.get("edge_count"),
            "boundary": (
                "KG browser data support private navigation; citable KG status "
                "and public web artifact status remain closed."
            ),
        }
    )
    rows.append(
        {
            "surface_id": "site_visual_smoke_static_guards",
            "package_path": "site/index.html",
            "surface_role": "private_site_static_visual_smoke",
            "local_link_count": 0,
            "broken_local_link_count": 0,
            "missing_required_phrase_count": len(
                private_site_quality.get("missing_visual_first_screen_phrases") or []
            ),
            "boundary_violation_count": 0,
            "status": private_site_quality.get("visual_smoke_status"),
            "reader_job": (
                "Confirm that layout guards and first-screen review phrases are present."
            ),
            "missing_layout_guard_count": len(
                private_site_quality.get("missing_visual_layout_guards") or []
            ),
            "missing_first_screen_phrase_count": len(
                private_site_quality.get("missing_visual_first_screen_phrases") or []
            ),
            "boundary": (
                "Static smoke checks are private publication-site hygiene checks; "
                "they do not replace final visual/table retention review."
            ),
        }
    )
    return rows


def release_cut_allows_private_package(release_summary: dict[str, Any]) -> bool:
    return (
        release_summary.get("overall_status") == "neutral_publication_release_cut_ready"
        and release_summary.get("neutral_private_sterile_repository_preparation_authorized")
        is True
        and release_summary.get("public_release_authorized") is False
        and release_summary.get("working_repository_final_citable") is False
        and release_summary.get("method_recommendation_authorized") is False
        and release_summary.get("positive_claim_promotion_authorized") is False
        and release_summary.get("raw_data_or_secret_inclusion_authorized") is False
    )


def initialize_git_repo(package_root: Path) -> dict[str, Any]:
    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            cwd=package_root,
            check=True,
            capture_output=True,
            text=True,
        )

    run(["git", "init", "-b", "main"])
    run(["git", "config", "user.name", "Emre Tasar"])
    run(["git", "config", "user.email", "detasar@gmail.com"])
    run(["git", "add", "."])
    run(["git", "commit", "-m", "Create private sterile publication review package"])
    commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    return {"initialized": True, "commit": commit}


def check_row(check_id: str, passed: bool, evidence: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "blocker": blocker,
    }


def build_payload(
    repo_root: Path,
    package_root: Path,
    initialize_git: bool = True,
    replace_existing_package: bool = False,
    release_cut_path: Path | None = None,
    staging_manifest_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    package_root = resolve_package_root(repo_root, package_root)
    release_cut_path = release_cut_path or RELEASE_CUT
    staging_manifest_path = staging_manifest_path or STAGING_MANIFEST
    release_cut = read_json(repo_root / release_cut_path)
    staging_manifest = read_json(repo_root / staging_manifest_path)
    latex_html_outputs = read_json(repo_root / LATEX_HTML_OUTPUTS_MANIFEST)
    latex_html_audit = read_json(repo_root / LATEX_HTML_OUTPUT_AUDIT)
    release_summary = summary(release_cut)
    staging_summary = summary(staging_manifest)
    latex_html_summary = summary(latex_html_outputs)
    latex_html_audit_summary = summary(latex_html_audit)
    release_allows_private_package = release_cut_allows_private_package(
        release_summary
    )
    staging_ready = (
        staging_summary.get("overall_status")
        == "sterile_repository_staging_manifest_ready_no_repository_created"
        and staging_summary.get("failed_check_count") == 0
    )
    latex_html_outputs_ready = (
        latex_html_summary.get("overall_status")
        == "private_latex_html_review_outputs_ready"
        and latex_html_summary.get("failed_check_count") == 0
        and latex_html_summary.get("public_release_authorized") is False
        and latex_html_summary.get("method_recommendation_authorized") is False
        and latex_html_summary.get("positive_claim_promotion_authorized") is False
    )
    latex_html_audit_ready = (
        latex_html_audit_summary.get("overall_status")
        == "private_latex_html_review_output_audit_pass"
        and latex_html_audit_summary.get("failed_check_count") == 0
        and latex_html_audit_summary.get("secret_pattern_hit_count") == 0
        and latex_html_audit_summary.get("authorization_violation_count") == 0
        and latex_html_audit_summary.get("public_release_authorized") is False
        and latex_html_audit_summary.get("working_repository_final_citable") is False
        and latex_html_audit_summary.get("final_manuscript_prose_permission") is False
        and latex_html_audit_summary.get("method_recommendation_authorized") is False
        and latex_html_audit_summary.get("positive_claim_promotion_authorized") is False
        and (
            latex_html_audit_summary.get("raw_data_or_secret_inclusion_authorized")
            is False
        )
    )

    preflight_checks = [
        check_row(
            "release_cut_authorizes_private_package_only",
            release_allows_private_package,
            {
                "release_cut_status": release_summary.get("overall_status"),
                "public_release_authorized": release_summary.get(
                    "public_release_authorized"
                ),
                "method_recommendation_authorized": release_summary.get(
                    "method_recommendation_authorized"
                ),
            },
            "private_package_not_authorized_by_release_cut",
        ),
        check_row(
            "staging_manifest_ready",
            staging_ready,
            {
                "staging_status": staging_summary.get("overall_status"),
                "failed_check_count": staging_summary.get("failed_check_count"),
            },
            "staging_manifest_not_ready",
        ),
        check_row(
            "private_latex_html_outputs_ready",
            latex_html_outputs_ready,
            {
                "latex_html_outputs_status": latex_html_summary.get("overall_status"),
                "failed_check_count": latex_html_summary.get("failed_check_count"),
                "public_release_authorized": latex_html_summary.get(
                    "public_release_authorized"
                ),
            },
            "private_latex_html_outputs_not_ready",
        ),
        check_row(
            "private_latex_html_output_audit_ready",
            latex_html_audit_ready,
            {
                "latex_html_output_audit_status": latex_html_audit_summary.get(
                    "overall_status"
                ),
                "failed_check_count": latex_html_audit_summary.get(
                    "failed_check_count"
                ),
                "secret_pattern_hit_count": latex_html_audit_summary.get(
                    "secret_pattern_hit_count"
                ),
                "authorization_violation_count": latex_html_audit_summary.get(
                    "authorization_violation_count"
                ),
            },
            "private_latex_html_output_audit_not_ready",
        ),
    ]
    if (
        not release_allows_private_package
        or not staging_ready
        or not latex_html_outputs_ready
        or not latex_html_audit_ready
    ):
        failed_checks = [row for row in preflight_checks if row["status"] != "pass"]
        return {
            "schema": SCHEMA,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "sources": {
                "sterile_repository_staging_manifest": rel(
                    repo_root / staging_manifest_path, repo_root
                ),
                "neutral_publication_release_cut_decision": rel(
                    repo_root / release_cut_path, repo_root
                ),
                "private_latex_html_review_outputs_manifest": rel(
                    repo_root / LATEX_HTML_OUTPUTS_MANIFEST, repo_root
                ),
                "private_latex_html_review_output_audit": rel(
                    repo_root / LATEX_HTML_OUTPUT_AUDIT, repo_root
                ),
            },
            "summary": {
                "overall_status": "private_sterile_publication_package_blocked",
                "package_root": package_root.as_posix(),
                "source_artifact_count": 0,
                "missing_source_count": 0,
                "copied_file_count": 0,
                "excluded_file_count": 0,
                "packaged_bytes": 0,
                "release_cut_status": release_summary.get("overall_status"),
                "staging_manifest_status": staging_summary.get("overall_status"),
                "private_latex_html_outputs_status": latex_html_summary.get(
                    "overall_status"
                ),
                "private_latex_html_output_audit_status": (
                    latex_html_audit_summary.get("overall_status")
                ),
                "public_release_authorized": False,
                "working_repository_final_citable": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "positive_claim_promotion_authorized": False,
                "raw_data_or_secret_inclusion_authorized": False,
                "path_risk_hit_count": 0,
                "secret_pattern_hit_count": 0,
                "check_count": len(preflight_checks),
                "failed_check_count": len(failed_checks),
                "local_git_initialized": False,
                "local_git_commit": None,
            },
            "checks": preflight_checks,
            "failed_checks": failed_checks,
            "copied_files": [],
            "excluded_files": [],
            "missing_sources": [],
            "path_risk_hits": [],
            "secret_pattern_hits": [],
        }

    prepare_package_root(
        package_root,
        replace_existing_package=replace_existing_package,
    )
    all_sources: list[str] = []
    for row in staging_manifest.get("required_content_rows") or []:
        all_sources.extend(str(path) for path in row.get("source_artifacts") or [])
    all_sources.extend(GOVERNANCE_SOURCES)
    all_sources.extend(PROVENANCE_SOURCES)
    unique_sources = sorted(dict.fromkeys(all_sources))

    file_rows: list[dict[str, Any]] = []
    missing_sources: list[str] = []
    for source in unique_sources:
        source_path = repo_root / source
        if not source_path.exists():
            missing_sources.append(source)
            continue
        for source_file, source_rel in iter_source_files(repo_root, source):
            row = copy_one_file(source_file, source_rel, package_root)
            if row:
                file_rows.append(row)

    copied_rows = [row for row in file_rows if row["status"] == "copied"]
    excluded_rows = [row for row in file_rows if row["status"] == "excluded"]
    readme_source = repo_root / README_DRAFT
    if readme_source.exists():
        atomic_write_text(
            package_root / "README.md",
            render_private_readme(
                readme_source.read_text(encoding="utf-8"),
                copied_file_count=len(copied_rows),
                excluded_file_count=len(excluded_rows),
            ),
        )
    readme_json = read_json(repo_root / README_DRAFT_JSON)
    research_document_json = read_json(repo_root / RESEARCH_DOCUMENT_JSON)
    claim_evidence_matrix = read_json(repo_root / CLAIM_EVIDENCE_MATRIX_JSON)
    claim_safe_reading_rows = [
        row
        for row in readme_json.get("claim_safe_reading_rows", [])
        if isinstance(row, dict)
    ]
    claim_evidence_review_rows = [
        row
        for row in claim_evidence_matrix.get("claim_review_rows", [])
        if isinstance(row, dict)
    ]
    review_at_a_glance_rows = [
        row
        for row in readme_json.get("review_at_a_glance_rows", [])
        if isinstance(row, dict)
    ]
    first_ten_minute_rows = [
        row
        for row in readme_json.get("first_ten_minute_review_rows", [])
        if isinstance(row, dict)
    ]
    reviewer_acceptance_rows = [
        row
        for row in readme_json.get("reviewer_acceptance_rows", [])
        if isinstance(row, dict)
    ]
    reviewer_front_door_rows = [
        row
        for row in readme_json.get("reviewer_front_door_rows", [])
        if isinstance(row, dict)
    ]
    result_verification_command_rows = [
        row
        for row in readme_json.get("result_verification_command_rows", [])
        if isinstance(row, dict)
    ]
    environment_data_access_rows = [
        row
        for row in readme_json.get("environment_data_access_rows", [])
        if isinstance(row, dict)
    ]
    research_question_rows = [
        row
        for row in readme_json.get("research_question_rows", [])
        if isinstance(row, dict)
    ]
    contribution_finding_rows = [
        row
        for row in readme_json.get("contribution_finding_rows", [])
        if isinstance(row, dict)
    ]
    paper_architecture_rows = [
        row
        for row in readme_json.get("paper_architecture_rows", [])
        if isinstance(row, dict)
    ]
    main_article_guarantee_rows = [
        row
        for row in readme_json.get("main_article_guarantee_boundary_rows", [])
        if isinstance(row, dict)
    ]
    provenance_graph_log_rows = [
        row
        for row in readme_json.get("provenance_graph_log_rows", [])
        if isinstance(row, dict)
    ]
    repository_map_rows = [
        row
        for row in readme_json.get("repository_map_rows", [])
        if isinstance(row, dict)
    ]
    reader_contract_rows = [
        row
        for row in research_document_json.get("reader_contract_rows", [])
        if isinstance(row, dict)
    ]
    kg_browser_payload = build_kg_browser_payload(package_root)
    atomic_write_json(package_root / "site/kg_browser_data.json", kg_browser_payload)
    atomic_write_text(package_root / "site/kg_browser.html", render_kg_browser_html())
    path_risk_hits = scan_packaged_path_risks(package_root)
    secret_hits = scan_for_secret_patterns(package_root)
    status_counts = Counter(row["status"] for row in file_rows)
    checks = [
        *preflight_checks,
        check_row(
            "source_artifacts_available",
            not missing_sources,
            {"missing_sources": missing_sources},
            "package_source_missing",
        ),
        check_row(
            "package_has_copied_files",
            bool(copied_rows),
            {"copied_file_count": len(copied_rows)},
            "package_empty",
        ),
        check_row(
            "no_packaged_raw_cache_or_large_file_risks",
            not path_risk_hits,
            {"path_risk_hits": path_risk_hits[:20]},
            "packaged_path_risk_detected",
        ),
        check_row(
            "no_high_confidence_secret_patterns",
            not secret_hits,
            {"secret_hits": secret_hits[:20]},
            "secret_pattern_detected",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    package_ready = not failed_checks

    summary_payload = {
        "overall_status": (
            "private_sterile_publication_package_ready"
            if package_ready
            else "private_sterile_publication_package_blocked"
        ),
        "package_root": package_root.as_posix(),
        "author_name": AUTHOR_NAME,
        "author_role": AUTHOR_ROLE,
        "author_email": AUTHOR_EMAIL,
        "author_header": f"Author: {AUTHOR_NAME}, {AUTHOR_ROLE}",
        "source_artifact_count": len(unique_sources),
        "missing_source_count": len(missing_sources),
        "copied_file_count": len(copied_rows),
        "excluded_file_count": len(excluded_rows),
        "packaged_bytes": sum(int(row.get("bytes") or 0) for row in copied_rows),
        "release_cut_status": release_summary.get("overall_status"),
        "staging_manifest_status": staging_summary.get("overall_status"),
        "private_latex_html_outputs_status": latex_html_summary.get("overall_status"),
        "private_latex_html_output_audit_status": latex_html_audit_summary.get(
            "overall_status"
        ),
        "kg_browser_node_count": kg_browser_payload["summary"]["node_count"],
        "kg_browser_edge_count": kg_browser_payload["summary"]["edge_count"],
        "kg_browser_relation_type_count": (
            kg_browser_payload["summary"]["relation_type_count"]
        ),
        "kg_browser_node_type_count": kg_browser_payload["summary"]["node_type_count"],
        "kg_browser_guided_trace_preset_count": kg_browser_payload["summary"][
            "guided_trace_preset_count"
        ],
        "reviewer_front_door_row_count": len(reviewer_front_door_rows),
        "review_at_a_glance_row_count": len(review_at_a_glance_rows),
        "first_ten_minute_review_row_count": len(first_ten_minute_rows),
        "reviewer_acceptance_row_count": len(reviewer_acceptance_rows),
        "result_verification_command_row_count": len(
            result_verification_command_rows
        ),
        "environment_data_access_row_count": len(environment_data_access_rows),
        "research_question_row_count": len(research_question_rows),
        "contribution_finding_row_count": len(contribution_finding_rows),
        "paper_architecture_row_count": len(paper_architecture_rows),
        "claim_safe_reading_row_count": len(claim_safe_reading_rows),
        "claim_evidence_review_row_count": len(claim_evidence_review_rows),
        "main_article_guarantee_boundary_row_count": len(
            main_article_guarantee_rows
        ),
        "provenance_graph_log_row_count": len(provenance_graph_log_rows),
        "repository_map_row_count": len(repository_map_rows),
        "reader_contract_row_count": len(reader_contract_rows),
        "public_release_authorized": False,
        "working_repository_final_citable": False,
        "method_recommendation_authorized": False,
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "positive_claim_promotion_authorized": False,
        "raw_data_or_secret_inclusion_authorized": False,
        "path_risk_hit_count": len(path_risk_hits),
        "secret_pattern_hit_count": len(secret_hits),
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
        "local_git_initialized": bool(initialize_git and package_ready),
        "local_git_commit": (
            "recorded_in_source_manifest_after_commit"
            if initialize_git and package_ready
            else None
        ),
    }
    atomic_write_text(
        package_root / "PRIVATE_REVIEW_BOUNDARIES.md",
        render_boundaries({"summary": summary_payload}),
    )
    atomic_write_text(
        package_root / "USER_REVIEW_HANDOFF.md",
        render_user_review_handoff(
            {
                "summary": summary_payload,
                "reviewer_acceptance_rows": reviewer_acceptance_rows,
                "reviewer_front_door_rows": reviewer_front_door_rows,
                "first_ten_minute_review_rows": first_ten_minute_rows,
                "research_question_rows": research_question_rows,
                "provenance_graph_log_rows": provenance_graph_log_rows,
                "repository_map_rows": repository_map_rows,
                "reader_contract_rows": reader_contract_rows,
            }
        ),
    )
    atomic_write_text(
        package_root / "PUBLIC_RELEASE_REVIEW_CHECKLIST.md",
        render_public_release_review_checklist({"summary": summary_payload}),
    )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "sterile_repository_staging_manifest": rel(
                repo_root / staging_manifest_path, repo_root
            ),
            "neutral_publication_release_cut_decision": rel(
                repo_root / release_cut_path, repo_root
            ),
            "private_latex_html_review_outputs_manifest": rel(
                repo_root / LATEX_HTML_OUTPUTS_MANIFEST, repo_root
            ),
            "private_latex_html_review_output_audit": rel(
                repo_root / LATEX_HTML_OUTPUT_AUDIT, repo_root
            ),
            "sterile_repository_readme_draft": rel(
                repo_root / README_DRAFT_JSON, repo_root
            ),
            "publication_claim_evidence_verification_matrix": rel(
                repo_root / CLAIM_EVIDENCE_MATRIX_JSON, repo_root
            ),
            "research_document": rel(repo_root / RESEARCH_DOCUMENT_JSON, repo_root),
        },
        "summary": summary_payload,
        "checks": checks,
        "failed_checks": failed_checks,
        "copied_files": copied_rows,
        "excluded_files": excluded_rows,
        "missing_sources": missing_sources,
        "path_risk_hits": path_risk_hits,
        "secret_pattern_hits": secret_hits,
        "reviewer_front_door_rows": reviewer_front_door_rows,
        "result_verification_command_rows": result_verification_command_rows,
        "environment_data_access_rows": environment_data_access_rows,
        "review_at_a_glance_rows": review_at_a_glance_rows,
        "first_ten_minute_review_rows": first_ten_minute_rows,
        "reviewer_acceptance_rows": reviewer_acceptance_rows,
        "research_question_rows": research_question_rows,
        "contribution_finding_rows": contribution_finding_rows,
        "paper_architecture_rows": paper_architecture_rows,
        "provenance_graph_log_rows": provenance_graph_log_rows,
        "repository_map_rows": repository_map_rows,
        "reader_contract_rows": reader_contract_rows,
        "claim_safe_reading_rows": claim_safe_reading_rows,
        "claim_evidence_review_rows": claim_evidence_review_rows,
        "main_article_guarantee_boundary_rows": main_article_guarantee_rows,
    }
    atomic_write_text(package_root / "site/index.html", render_site_index(payload))

    generated_review_surface_rows = build_generated_review_surface_rows(package_root)
    generated_review_surface_pass_count = sum(
        row["verification_status"] == "pass" for row in generated_review_surface_rows
    )
    generated_review_surface_missing_count = sum(
        not row["exists"] for row in generated_review_surface_rows
    )
    generated_review_surface_phrase_issue_count = sum(
        len(row["missing_required_phrases"])
        for row in generated_review_surface_rows
    )
    generated_review_surface_empty_table_cell_count = sum(
        int(row["empty_markdown_table_cell_count"])
        for row in generated_review_surface_rows
    )
    checks.append(
        check_row(
            "generated_private_review_surfaces_ready",
            len(generated_review_surface_rows) == len(GENERATED_REVIEW_SURFACE_SPECS)
            and generated_review_surface_pass_count
            == len(GENERATED_REVIEW_SURFACE_SPECS)
            and generated_review_surface_missing_count == 0
            and generated_review_surface_phrase_issue_count == 0
            and generated_review_surface_empty_table_cell_count == 0,
            {
                "generated_review_surface_count": len(generated_review_surface_rows),
                "generated_review_surface_pass_count": (
                    generated_review_surface_pass_count
                ),
                "generated_review_surface_missing_count": (
                    generated_review_surface_missing_count
                ),
                "generated_review_surface_phrase_issue_count": (
                    generated_review_surface_phrase_issue_count
                ),
                "generated_review_surface_empty_table_cell_count": (
                    generated_review_surface_empty_table_cell_count
                ),
            },
            "generated_private_review_surface_missing_or_stale",
        )
    )
    failed_checks = [row for row in checks if row["status"] != "pass"]
    package_ready = not failed_checks
    summary_payload.update(
        {
            "overall_status": (
                "private_sterile_publication_package_ready"
                if package_ready
                else "private_sterile_publication_package_blocked"
            ),
            "generated_review_surface_count": len(generated_review_surface_rows),
            "generated_review_surface_pass_count": (
                generated_review_surface_pass_count
            ),
            "generated_review_surface_missing_count": (
                generated_review_surface_missing_count
            ),
            "generated_review_surface_phrase_issue_count": (
                generated_review_surface_phrase_issue_count
            ),
            "generated_review_surface_empty_table_cell_count": (
                generated_review_surface_empty_table_cell_count
            ),
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
            "local_git_initialized": bool(initialize_git and package_ready),
            "local_git_commit": (
                "recorded_in_source_manifest_after_commit"
                if initialize_git and package_ready
                else None
            ),
        }
    )
    payload["checks"] = checks
    payload["failed_checks"] = failed_checks
    payload["generated_review_surface_rows"] = generated_review_surface_rows
    atomic_write_text(package_root / "site/index.html", render_site_index(payload))
    generated_review_surface_rows = build_generated_review_surface_rows(package_root)
    generated_review_surface_pass_count = sum(
        row["verification_status"] == "pass" for row in generated_review_surface_rows
    )
    generated_review_surface_missing_count = sum(
        not row["exists"] for row in generated_review_surface_rows
    )
    generated_review_surface_phrase_issue_count = sum(
        len(row["missing_required_phrases"])
        for row in generated_review_surface_rows
    )
    generated_review_surface_empty_table_cell_count = sum(
        int(row["empty_markdown_table_cell_count"])
        for row in generated_review_surface_rows
    )
    payload["generated_review_surface_rows"] = generated_review_surface_rows
    atomic_write_json(
        package_root / "metadata/private_sterile_publication_package_manifest.json",
        payload,
    )
    private_site_quality = audit_private_static_site(package_root, kg_browser_payload)
    checks[-1] = check_row(
        "generated_private_review_surfaces_ready",
        len(generated_review_surface_rows) == len(GENERATED_REVIEW_SURFACE_SPECS)
        and generated_review_surface_pass_count
        == len(GENERATED_REVIEW_SURFACE_SPECS)
        and generated_review_surface_missing_count == 0
        and generated_review_surface_phrase_issue_count == 0
        and generated_review_surface_empty_table_cell_count == 0,
        {
            "generated_review_surface_count": len(generated_review_surface_rows),
            "generated_review_surface_pass_count": (
                generated_review_surface_pass_count
            ),
            "generated_review_surface_missing_count": (
                generated_review_surface_missing_count
            ),
            "generated_review_surface_phrase_issue_count": (
                generated_review_surface_phrase_issue_count
            ),
            "generated_review_surface_empty_table_cell_count": (
                generated_review_surface_empty_table_cell_count
            ),
        },
        "generated_private_review_surface_missing_or_stale",
    )
    checks.append(
        check_row(
            "private_static_site_quality_passes",
            private_site_quality["overall_status"] == "pass",
            {
                "html_page_count": private_site_quality["html_page_count"],
                "local_link_count": private_site_quality["local_link_count"],
                "broken_local_link_count": private_site_quality[
                    "broken_local_link_count"
                ],
                "missing_required_phrase_count": private_site_quality[
                    "missing_required_phrase_count"
                ],
                "kg_browser_data_status": private_site_quality[
                    "kg_browser_data_status"
                ],
                "kg_browser_summary_matches_payload": private_site_quality[
                    "kg_browser_summary_matches_payload"
                ],
                "boundary_violation_count": private_site_quality[
                    "boundary_violation_count"
                ],
                "visual_smoke_status": private_site_quality[
                    "visual_smoke_status"
                ],
                "visual_smoke_issue_count": private_site_quality[
                    "visual_smoke_issue_count"
                ],
                "visual_smoke_layout_guard_status": private_site_quality[
                    "visual_smoke_layout_guard_status"
                ],
                "visual_smoke_first_screen_status": private_site_quality[
                    "visual_smoke_first_screen_status"
                ],
            },
            "private_static_site_quality_failed",
        )
    )
    private_static_site_navigation_rows = build_private_static_site_navigation_rows(
        private_site_quality
    )
    private_static_site_navigation_pass_count = sum(
        row.get("status") == "pass" for row in private_static_site_navigation_rows
    )
    private_static_site_navigation_issue_count = sum(
        int(row.get("broken_local_link_count") or 0)
        + int(row.get("missing_required_phrase_count") or 0)
        + int(row.get("boundary_violation_count") or 0)
        + int(row.get("missing_layout_guard_count") or 0)
        + int(row.get("missing_first_screen_phrase_count") or 0)
        for row in private_static_site_navigation_rows
    )
    failed_checks = [row for row in checks if row["status"] != "pass"]
    package_ready = not failed_checks
    summary_payload.update(
        {
            "overall_status": (
                "private_sterile_publication_package_ready"
                if package_ready
                else "private_sterile_publication_package_blocked"
            ),
            "generated_review_surface_count": len(generated_review_surface_rows),
            "generated_review_surface_pass_count": (
                generated_review_surface_pass_count
            ),
            "generated_review_surface_missing_count": (
                generated_review_surface_missing_count
            ),
            "generated_review_surface_phrase_issue_count": (
                generated_review_surface_phrase_issue_count
            ),
            "generated_review_surface_empty_table_cell_count": (
                generated_review_surface_empty_table_cell_count
            ),
            "private_static_site_quality_status": private_site_quality[
                "overall_status"
            ],
            "private_static_site_html_page_count": private_site_quality[
                "html_page_count"
            ],
            "private_static_site_local_link_count": private_site_quality[
                "local_link_count"
            ],
            "private_static_site_broken_local_link_count": private_site_quality[
                "broken_local_link_count"
            ],
            "private_static_site_missing_required_phrase_count": private_site_quality[
                "missing_required_phrase_count"
            ],
            "private_static_site_boundary_violation_count": private_site_quality[
                "boundary_violation_count"
            ],
            "private_static_site_kg_data_status": private_site_quality[
                "kg_browser_data_status"
            ],
            "private_static_site_visual_smoke_status": private_site_quality[
                "visual_smoke_status"
            ],
            "private_static_site_visual_smoke_issue_count": private_site_quality[
                "visual_smoke_issue_count"
            ],
            "private_static_site_layout_guard_status": private_site_quality[
                "visual_smoke_layout_guard_status"
            ],
            "private_static_site_first_screen_status": private_site_quality[
                "visual_smoke_first_screen_status"
            ],
            "private_static_site_visual_smoke_basis": private_site_quality[
                "visual_smoke_basis"
            ],
            "private_static_site_navigation_row_count": len(
                private_static_site_navigation_rows
            ),
            "private_static_site_navigation_pass_count": (
                private_static_site_navigation_pass_count
            ),
            "private_static_site_navigation_issue_count": (
                private_static_site_navigation_issue_count
            ),
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
            "local_git_initialized": bool(initialize_git and package_ready),
            "local_git_commit": (
                "recorded_in_source_manifest_after_commit"
                if initialize_git and package_ready
                else None
            ),
        }
    )
    payload["checks"] = checks
    payload["failed_checks"] = failed_checks
    payload["generated_review_surface_rows"] = generated_review_surface_rows
    payload["private_static_site_quality"] = private_site_quality
    payload["private_static_site_navigation_rows"] = private_static_site_navigation_rows
    atomic_write_json(
        package_root / "metadata/private_sterile_publication_package_manifest.json",
        payload,
    )

    if initialize_git and package_ready:
        git_result = initialize_git_repo(package_root)
        summary_payload["local_git_commit"] = git_result["commit"]
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# Private Sterile Publication Package Manifest",
        "",
        "This manifest records the local/private sterile publication package. It does not authorize public release.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{s['overall_status']}`",
        f"- Package root: `{s['package_root']}`",
        f"- Copied files: {s['copied_file_count']}",
        f"- Excluded files: {s['excluded_file_count']}",
        f"- Packaged bytes: {s['packaged_bytes']}",
        f"- Public release authorized: `{s['public_release_authorized']}`",
        f"- Method recommendation authorized: `{s['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{s['positive_claim_promotion_authorized']}`",
        f"- Raw data or secret inclusion authorized: `{s['raw_data_or_secret_inclusion_authorized']}`",
        f"- Path risk hits: {s['path_risk_hit_count']}",
        f"- Secret pattern hits: {s['secret_pattern_hit_count']}",
        f"- Generated review surfaces: {s.get('generated_review_surface_pass_count', 0)} / {s.get('generated_review_surface_count', 0)}",
        f"- Generated review surface phrase issues: {s.get('generated_review_surface_phrase_issue_count', 0)}",
        f"- Generated review surface empty table cells: {s.get('generated_review_surface_empty_table_cell_count', 0)}",
        f"- Private static site quality: `{s.get('private_static_site_quality_status', 'n/a')}`",
        f"- Private static site local links / broken links: {s.get('private_static_site_local_link_count', 'n/a')} / {s.get('private_static_site_broken_local_link_count', 'n/a')}",
        f"- Private static site boundary violations: {s.get('private_static_site_boundary_violation_count', 'n/a')}",
        f"- Private static site KG data status: `{s.get('private_static_site_kg_data_status', 'n/a')}`",
        f"- Private static site visual smoke: `{s.get('private_static_site_visual_smoke_status', 'n/a')}`; issues: {s.get('private_static_site_visual_smoke_issue_count', 'n/a')}",
        f"- Private static site layout / first screen: `{s.get('private_static_site_layout_guard_status', 'n/a')}` / `{s.get('private_static_site_first_screen_status', 'n/a')}`",
        f"- Private static site navigation rows: {s.get('private_static_site_navigation_pass_count', 'n/a')} / {s.get('private_static_site_navigation_row_count', 'n/a')}",
        f"- Private static site navigation issues: {s.get('private_static_site_navigation_issue_count', 'n/a')}",
        f"- KG browser nodes / edges: {s.get('kg_browser_node_count', 'n/a')} / {s.get('kg_browser_edge_count', 'n/a')}",
        f"- KG browser node / relation types: {s.get('kg_browser_node_type_count', 'n/a')} / {s.get('kg_browser_relation_type_count', 'n/a')}",
        f"- Local git initialized: `{s['local_git_initialized']}`",
        f"- Local git commit: `{s['local_git_commit']}`",
        f"- Failed checks: {s['failed_check_count']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Blocker |",
        "|---|---|---|",
    ]
    for row in payload["checks"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['blocker']}` |")
    lines.extend(
        [
            "",
            "## Private Static Site Navigation Integrity",
            "",
            "| Surface | Package path | Status | Local links | Broken links | Missing phrases | Boundary violations | Reader job | Boundary |",
            "|---|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in payload.get("private_static_site_navigation_rows") or []:
        lines.append(
            "| {surface} | `{path}` | `{status}` | {links} | {broken} | {missing} | {violations} | {job} | {boundary} |".format(
                surface=escape_markdown_cell(row.get("surface_role")),
                path=escape_markdown_cell(row.get("package_path")),
                status=escape_markdown_cell(row.get("status")),
                links=escape_markdown_cell(row.get("local_link_count")),
                broken=escape_markdown_cell(row.get("broken_local_link_count")),
                missing=escape_markdown_cell(row.get("missing_required_phrase_count")),
                violations=escape_markdown_cell(row.get("boundary_violation_count")),
                job=escape_markdown_cell(row.get("reader_job")),
                boundary=escape_markdown_cell(row.get("boundary")),
            )
        )
    lines.extend(["", "## Excluded File Reasons", ""])
    counts = Counter(row["reason"] for row in payload["excluded_files"])
    for reason, count in sorted(counts.items()):
        lines.append(f"- `{reason}`: {count}")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    out = repo_root / args.out
    payload = build_payload(
        repo_root=repo_root,
        package_root=Path(args.package_root),
        initialize_git=not args.skip_git,
        replace_existing_package=args.replace_existing_package,
    )
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "overall_status": payload["summary"]["overall_status"],
                "package_root": payload["summary"]["package_root"],
                "copied_file_count": payload["summary"]["copied_file_count"],
                "excluded_file_count": payload["summary"]["excluded_file_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "local_git_commit": payload["summary"]["local_git_commit"],
                "out": rel(out, repo_root),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
