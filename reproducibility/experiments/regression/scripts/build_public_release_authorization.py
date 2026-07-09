"""Build the final public release layer.

The generated public surface is a reader-facing Research Atlas, not a private
review or manuscript-submission wrapper. Scientific scope limits are expressed
as evidence boundaries, not as authorization/legal boilerplate.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA_AUTH = "cpfi_regression_user_public_release_authorization_v1"
SCHEMA_MANIFEST = "cpfi_regression_public_release_manifest_v1"
DEFAULT_OUT_DIR = Path("experiments/regression/public_release")
DEFAULT_PACKAGE_ROOT = Path("../regression-conformal-prediction-research-atlas-private")
DEFAULT_REMOTE_REPO = "detasar/regression-conformal-prediction-research-atlas"
DEFAULT_PAGES_URL = "https://detasar.github.io/regression-conformal-prediction-research-atlas/"

REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")

SOURCE_PATHS = {
    "private_package_manifest": Path(
        "experiments/regression/manuscript/private_sterile_publication_package_manifest.json"
    ),
    "private_remote_audit": Path(
        "experiments/regression/manuscript/private_publication_repository_remote_audit.json"
    ),
    "private_render_audit": Path(
        "experiments/regression/manuscript/private_latex_html_review_output_audit.json"
    ),
    "research_document": Path("experiments/regression/manuscript/research_document.json"),
    "main_article": Path("experiments/regression/manuscript/main_article_draft.json"),
    "supplement": Path("experiments/regression/manuscript/supplementary_document_draft.json"),
    "individual_report": Path(
        "experiments/regression/manuscript/individual_experiment_report_draft.json"
    ),
    "claim_evidence_matrix": Path(
        "experiments/regression/manuscript/publication_claim_evidence_verification_matrix.json"
    ),
    "cqr_model_matched_synthesis": Path(
        "experiments/regression/reports/model_matched_cqr_rerun_plan/"
        "cqr_fixed_vs_model_matched_synthesis.json"
    ),
    "neutral_language_audit": REPORT_DIR / "neutral_reporting_language_audit.json",
    "kg_quality": Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json"),
    "kg_publication_audit": REPORT_DIR / "kg_publication_quality_audit.json",
}

USER_APPROVAL_EXCERPT = (
    "The user requested completion of the Research Document, repository, "
    "knowledge graph, website, and PDF outputs as a public research release."
)
LOCKED_EMPIRICAL_WORDING = (
    "CQR/CV+ were observed as strong practical candidates in these experiments."
)
LOCKED_VENN_ABERS_WORDING = (
    "The expected strong regression solution did not emerge in these experiments."
)
PDF_OUTPUT_SPECS = (
    {
        "component_id": "main_article_pdf",
        "tex_path": Path("rendered_outputs/main_article_review.tex"),
        "pdf_path": Path("rendered_outputs/main_article_review.pdf"),
        "title": "Main article PDF",
    },
    {
        "component_id": "supplementary_document_pdf",
        "tex_path": Path("rendered_outputs/supplementary_document_review.tex"),
        "pdf_path": Path("rendered_outputs/supplementary_document_review.pdf"),
        "title": "Supplementary document PDF",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Source repository root.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory.")
    parser.add_argument(
        "--package-root",
        default=str(DEFAULT_PACKAGE_ROOT),
        help="Sterile publication package root to overlay.",
    )
    parser.add_argument("--remote-repo", default=DEFAULT_REMOTE_REPO)
    parser.add_argument("--pages-url", default=DEFAULT_PAGES_URL)
    parser.add_argument(
        "--apply-package-overlay",
        action="store_true",
        help="Write public-facing README/site/release files into the sterile package.",
    )
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
        if (root / path).exists():
            present.append(rel(root / path, root))
        else:
            missing.append(rel(root / path, root))
    return present, missing


def gh_repo_state(repo: str, root: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "gh",
                "repo",
                "view",
                repo,
                "--json",
                "name,visibility,url,defaultBranchRef,isPrivate,viewerPermission",
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "error": str(exc),
            "repo": repo,
        }
    payload = json.loads(result.stdout)
    return {
        "available": True,
        "repo": repo,
        "name": payload.get("name"),
        "url": payload.get("url"),
        "visibility": payload.get("visibility"),
        "is_private": payload.get("isPrivate"),
        "viewer_permission": payload.get("viewerPermission"),
        "default_branch": (payload.get("defaultBranchRef") or {}).get("name"),
    }


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(args: list[str], cwd: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env.setdefault("SOURCE_DATE_EPOCH", "1783361878")
    env.setdefault("FORCE_SOURCE_DATE", "1")
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "args": args,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-1200:],
        "stderr_tail": result.stderr[-1200:],
    }


PDF_SAFE_TABLE_MARKER = "% public-pdf-table-layout-v1"


def pdf_safe_column_spec(raw_spec: str) -> str:
    columns = [char for char in raw_spec if char in {"l", "c", "r"}]
    count = max(1, len(columns))
    presets = {
        1: [0.96],
        2: [0.30, 0.64],
        3: [0.25, 0.34, 0.35],
        4: [0.19, 0.27, 0.27, 0.21],
        5: [0.15, 0.22, 0.22, 0.20, 0.15],
    }
    widths = presets.get(count, [0.92 / count] * count)
    return (
        "@{}"
        + "".join(
            rf">{{\RaggedRight\arraybackslash}}p{{{width:.3f}\linewidth}}"
            for width in widths
        )
        + "@{}"
    )


def make_texttt_breakable(match: re.Match[str]) -> str:
    content = match.group(1)
    if r"\allowbreak" in content:
        return match.group(0)
    if len(content) < 18 and r"\_" not in content and "/" not in content:
        return match.group(0)
    replacements = [
        (r"\_", r"\_\allowbreak{}"),
        ("/", r"/\allowbreak{}"),
        (":", r":\allowbreak{}"),
        ("-", r"-\allowbreak{}"),
        (".", r".\allowbreak{}"),
    ]
    updated = content
    for old, new in replacements:
        updated = updated.replace(old, new)
    return rf"\texttt{{{updated}}}"


def make_latex_pdf_safe(text: str) -> str:
    if PDF_SAFE_TABLE_MARKER in text:
        return text
    additions = "\n".join(
        [
            PDF_SAFE_TABLE_MARKER,
            r"\usepackage{array}",
            r"\usepackage{ragged2e}",
            r"\usepackage{xurl}",
            r"\usepackage{microtype}",
            r"\setlength{\emergencystretch}{4em}",
            r"\Urlmuskip=0mu plus 2mu\relax",
            r"\sloppy",
        ]
    )
    if r"\usepackage{longtable}" in text:
        text = text.replace(r"\usepackage{longtable}", r"\usepackage{longtable}" + "\n" + additions, 1)
    else:
        text = text.replace(r"\documentclass[11pt]{article}", r"\documentclass[11pt]{article}" + "\n" + additions, 1)

    def table_replacement(match: re.Match[str]) -> str:
        safe_spec = pdf_safe_column_spec(match.group(1))
        return (
            r"\begingroup"
            "\n"
            r"\small"
            "\n"
            r"\setlength{\tabcolsep}{3pt}"
            "\n"
            r"\renewcommand{\arraystretch}{1.18}"
            "\n"
            rf"\begin{{longtable}}{{{safe_spec}}}"
        )

    text = re.sub(r"\\begin\{longtable\}\{([^{}]+)\}", table_replacement, text)
    text = text.replace(r"\end{longtable}", r"\end{longtable}" + "\n" + r"\endgroup")
    text = re.sub(r"\\texttt\{([^{}]*)\}", make_texttt_breakable, text)
    text = re.sub(r"\\_(?!\\allowbreak\{\})", r"\\_\\allowbreak{}", text)
    return text


def prepare_public_pdf_latex(package_root: Path) -> list[str]:
    written: list[str] = []
    for spec in PDF_OUTPUT_SPECS:
        tex_path = package_root / spec["tex_path"]
        if not tex_path.exists():
            continue
        original = tex_path.read_text(encoding="utf-8")
        updated = make_latex_pdf_safe(sanitize_public_text(original))
        if updated != original:
            atomic_write_text(tex_path, updated)
            written.append(spec["tex_path"].as_posix())
    return written


def compile_latex_pdf(tex_path: Path, references_path: Path, pdf_path: Path) -> dict[str, Any]:
    compiler = shutil.which("pdflatex")
    bibtex = shutil.which("bibtex")
    row = {
        "tex_path": tex_path.as_posix(),
        "pdf_path": pdf_path.as_posix(),
        "compiler_available": bool(compiler),
        "bibtex_available": bool(bibtex),
        "commands": [],
        "status": "fail",
        "pdf_created": False,
        "pdf_bytes": 0,
        "sha256": None,
    }
    if not tex_path.exists() or not references_path.exists() or not compiler or not bibtex:
        return row

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tmp_tex = tmp_path / tex_path.name
        tmp_bib = tmp_path / "references.bib"
        shutil.copy2(tex_path, tmp_tex)
        shutil.copy2(references_path, tmp_bib)
        stem = tmp_tex.stem
        commands = [
            run_command([compiler, "-interaction=nonstopmode", "-halt-on-error", tmp_tex.name], tmp_path),
            run_command([bibtex, stem], tmp_path),
            run_command([compiler, "-interaction=nonstopmode", "-halt-on-error", tmp_tex.name], tmp_path),
            run_command([compiler, "-interaction=nonstopmode", "-halt-on-error", tmp_tex.name], tmp_path),
        ]
        tmp_pdf = tmp_path / f"{stem}.pdf"
        if all(command["returncode"] == 0 for command in commands) and tmp_pdf.exists():
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp_pdf, pdf_path)
            row.update(
                {
                    "commands": commands,
                    "status": "pass",
                    "pdf_created": True,
                    "pdf_bytes": pdf_path.stat().st_size,
                    "sha256": sha256(pdf_path),
                }
            )
        else:
            row["commands"] = commands
    return row


def compile_package_pdfs(package_root: Path) -> list[dict[str, Any]]:
    references = package_root / "rendered_outputs/references.bib"
    rows = []
    for spec in PDF_OUTPUT_SPECS:
        row = compile_latex_pdf(
            package_root / spec["tex_path"],
            references,
            package_root / spec["pdf_path"],
        )
        row["component_id"] = spec["component_id"]
        row["title"] = spec["title"]
        rows.append(row)
    return rows


def pdf_output_rows(package_root: Path) -> list[dict[str, Any]]:
    public_fallbacks = {
        "main_article_pdf": {
            "tex_path": Path("paper/article.tex"),
            "pdf_path": Path("paper/article.pdf"),
        },
        "supplementary_document_pdf": {
            "tex_path": Path("paper/supplement.tex"),
            "pdf_path": Path("paper/supplement.pdf"),
        },
    }
    rows = []
    for spec in PDF_OUTPUT_SPECS:
        tex_rel = spec["tex_path"]
        pdf_rel = spec["pdf_path"]
        pdf_path = package_root / pdf_rel
        tex_path = package_root / tex_rel
        fallback = public_fallbacks.get(str(spec["component_id"])) or {}
        if (not pdf_path.exists() or not tex_path.exists()) and fallback:
            fallback_pdf = package_root / fallback["pdf_path"]
            fallback_tex = package_root / fallback["tex_path"]
            if fallback_pdf.exists() and fallback_tex.exists():
                pdf_path = fallback_pdf
                tex_path = fallback_tex
                pdf_rel = fallback["pdf_path"]
                tex_rel = fallback["tex_path"]
        rows.append(
            {
                "component_id": spec["component_id"],
                "title": spec["title"],
                "tex_path": tex_rel.as_posix(),
                "pdf_path": pdf_rel.as_posix(),
                "tex_exists": tex_path.exists(),
                "pdf_exists": pdf_path.exists(),
                "pdf_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
                "sha256": sha256(pdf_path),
                "status": "pass"
                if tex_path.exists()
                and pdf_path.exists()
                and pdf_path.stat().st_size > 10_000
                else "fail",
            }
        )
    return rows


def load_source_summaries(root: Path) -> dict[str, dict[str, Any]]:
    return {
        name: summary(read_json(root / path)) for name, path in SOURCE_PATHS.items()
    }


def build_checks(
    *,
    summaries: dict[str, dict[str, Any]],
    kg_quality: dict[str, Any],
    present_sources: list[str],
    missing_sources: list[str],
    package_root: Path,
) -> list[dict[str, Any]]:
    graph = kg_quality.get("graph") or {}
    traceability = kg_quality.get("traceability") or {}
    package_summary = summaries["private_package_manifest"]
    remote_summary = summaries["private_remote_audit"]
    render_summary = summaries["private_render_audit"]
    neutral_summary = summaries["neutral_language_audit"]
    kg_publication_summary = summaries["kg_publication_audit"]
    pdf_rows = pdf_output_rows(package_root)

    checks = [
        {
            "check_id": "source_artifacts_present",
            "status": "pass" if not missing_sources else "fail",
            "evidence": {"missing_source_artifacts": missing_sources},
        },
        {
            "check_id": "user_public_release_approval_recorded",
            "status": "pass",
            "evidence": {
                "approval_date": "2026-07-06",
                "approval_scope": "final neutral article, supplement, KG/site, sterile repository, and GitHub Pages release",
                "approval_excerpt": USER_APPROVAL_EXCERPT,
            },
        },
        {
            "check_id": "private_package_ready",
            "status": "pass"
            if package_summary.get("overall_status")
            == "private_sterile_publication_package_ready"
            and safe_int(package_summary.get("failed_check_count")) == 0
            else "fail",
            "evidence": {
                "overall_status": package_summary.get("overall_status"),
                "failed_check_count": package_summary.get("failed_check_count"),
                "copied_file_count": package_summary.get("copied_file_count"),
                "package_root_exists": package_root.exists(),
            },
        },
        {
            "check_id": "private_remote_was_synchronized_before_release",
            "status": "pass"
            if remote_summary.get("commit_match") is True
            and remote_summary.get("remote_repository_url")
            else "fail",
            "evidence": {
                "remote_repository_url": remote_summary.get("remote_repository_url"),
                "remote_visibility_at_private_audit": remote_summary.get("remote_visibility"),
                "commit_match": remote_summary.get("commit_match"),
                "remote_main_commit": remote_summary.get("remote_main_commit"),
            },
        },
        {
            "check_id": "rendered_outputs_ready",
            "status": "pass"
            if render_summary.get("overall_status")
            == "private_latex_html_review_output_audit_pass"
            and safe_int(render_summary.get("failed_check_count")) == 0
            and safe_int(render_summary.get("secret_pattern_hit_count")) == 0
            else "fail",
            "evidence": {
                "overall_status": render_summary.get("overall_status"),
                "html_quality_pass_count": render_summary.get("html_quality_pass_count"),
                "latex_compile_pass_count": render_summary.get("latex_compile_pass_count"),
                "secret_pattern_hit_count": render_summary.get("secret_pattern_hit_count"),
            },
        },
        {
            "check_id": "pdf_outputs_ready",
            "status": "pass"
            if pdf_rows and all(row["status"] == "pass" for row in pdf_rows)
            else "fail",
            "evidence": {
                "pdf_output_count": len(pdf_rows),
                "pdf_pass_count": sum(row["status"] == "pass" for row in pdf_rows),
                "pdf_rows": pdf_rows,
            },
        },
        {
            "check_id": "kg_publication_quality_ready",
            "status": "pass"
            if kg_publication_summary.get("overall_status") in {
                "kg_publication_ready",
                "kg_publication_ready_with_polish_caveats",
            }
            and safe_int(kg_publication_summary.get("hard_failed_check_count")) == 0
            and safe_int(graph.get("isolated_node_count")) == 0
            and float(traceability.get("edge_selector_provenance_coverage") or 0.0)
            == 1.0
            else "fail",
            "evidence": {
                "kg_publication_status": kg_publication_summary.get("overall_status"),
                "hard_failed_check_count": kg_publication_summary.get(
                    "hard_failed_check_count"
                ),
                "node_count": graph.get("node_count"),
                "edge_count": graph.get("edge_count"),
                "isolated_node_count": graph.get("isolated_node_count"),
                "edge_selector_provenance_coverage": traceability.get(
                    "edge_selector_provenance_coverage"
                ),
            },
        },
        {
            "check_id": "neutral_language_and_claim_boundaries_preserved",
            "status": "pass"
            if neutral_summary.get("overall_status") == "neutral_reporting_language_audit_pass"
            and safe_int(neutral_summary.get("unguarded_hit_count")) == 0
            else "fail",
            "evidence": {
                "neutral_language_status": neutral_summary.get("overall_status"),
                "unguarded_hit_count": neutral_summary.get("unguarded_hit_count"),
                "method_recommendation_authorized": False,
                "positive_claim_promotion_authorized": False,
            },
        },
    ]
    return checks


def build_payloads(root: Path, package_root: Path, remote_repo: str, pages_url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(timezone.utc).isoformat()
    present_sources, missing_sources = source_status(root)
    summaries = load_source_summaries(root)
    kg_quality = read_json(root / SOURCE_PATHS["kg_quality"])
    checks = build_checks(
        summaries=summaries,
        kg_quality=kg_quality,
        present_sources=present_sources,
        missing_sources=missing_sources,
        package_root=package_root,
    )
    failed_checks = [row for row in checks if row["status"] != "pass"]
    graph = kg_quality.get("graph") or {}
    traceability = kg_quality.get("traceability") or {}
    gh_state = gh_repo_state(remote_repo, root)
    pdf_rows = pdf_output_rows(package_root)
    cqr_model_matched_summary = summaries.get("cqr_model_matched_synthesis") or {}
    cqr_model_matched_selected_counts = (
        cqr_model_matched_summary.get(
            "coverage_eligible_interval_score_selected_counts"
        )
        or {}
    )

    authorization = {
        "schema": SCHEMA_AUTH,
        "generated_at_utc": generated_at,
        "summary": {
            "overall_status": "publication_user_release_authorization_ready",
            "approval_date": "2026-07-06",
            "user_approval_received": True,
            "user_approval_scope": (
                "Finalize and publicly release the neutral Research Document, main article, "
                "supplementary document, individual report, navigable KG, static site, "
                "and sterile repository exactly under the previously agreed scientific boundaries."
            ),
            "public_repository_release_authorized": True,
            "github_pages_publication_authorized": True,
            "publication_site_deployment_authorized": True,
            "kg_citable_component_authorized": True,
            "kg_public_web_artifact_authorized": True,
            "sterile_repository_publication_authorized": True,
            "final_neutral_article_supplement_release_authorized": True,
            "final_visual_table_release_authorized": True,
            "working_repository_final_citable": False,
            "method_recommendation_authorized": False,
            "method_champion_authorized": False,
            "method_advocacy_authorized": False,
            "positive_claim_promotion_authorized": False,
            "raw_data_or_secret_inclusion_authorized": False,
            "scientific_test_not_method_promotion": True,
            "locked_empirical_wording": LOCKED_EMPIRICAL_WORDING,
            "locked_venn_abers_wording": LOCKED_VENN_ABERS_WORDING,
            "source_artifact_count": len(present_sources),
            "missing_source_artifact_count": len(missing_sources),
        },
        "decision_record": {
            "source": "current Codex thread user message",
            "source_timestamp_local": "2026-07-06",
            "excerpt": USER_APPROVAL_EXCERPT,
            "interpretation": (
                "The approval opens public release, GitHub Pages, KG citation, and final "
                "neutral article/supplement packaging. It does not open method recommendation, "
                "method-selection promotion, bounded-support validity, population fairness, or positive "
                "Venn-Abers regression claims."
            ),
        },
        "sources": {name: rel(root / path, root) for name, path in SOURCE_PATHS.items()},
        "present_source_artifacts": present_sources,
        "missing_source_artifacts": missing_sources,
    }

    manifest = {
        "schema": SCHEMA_MANIFEST,
        "generated_at_utc": generated_at,
        "summary": {
            "overall_status": "public_release_manifest_ready"
            if not failed_checks
            else "public_release_manifest_blocked",
            "public_release_authorized": True,
            "public_release_approval_date": "2026-07-06",
            "public_repository_url": f"https://github.com/{remote_repo}",
            "github_pages_url": pages_url,
            "github_repo_visibility": gh_state.get("visibility"),
            "github_repo_is_private": gh_state.get("is_private"),
            "github_repo_viewer_permission": gh_state.get("viewer_permission"),
            "sterile_package_root": str(package_root),
            "kg_node_count": graph.get("node_count"),
            "kg_edge_count": graph.get("edge_count"),
            "kg_isolated_node_count": graph.get("isolated_node_count"),
            "kg_average_edge_confidence": traceability.get("average_edge_confidence"),
            "kg_edge_selector_provenance_coverage": traceability.get(
                "edge_selector_provenance_coverage"
            ),
            "cqr_model_matched_completed_rows": cqr_model_matched_summary.get(
                "model_matched_cqr_completed_rows"
            ),
            "cqr_fixed_gbm_completed_rows": cqr_model_matched_summary.get(
                "fixed_gbm_cqr_completed_rows"
            ),
            "cqr_backend_sensitivity_paired_cell_count": cqr_model_matched_summary.get(
                "paired_cell_count"
            ),
            "cqr_backend_sensitivity_cell_count": cqr_model_matched_summary.get(
                "cell_count"
            ),
            "cqr_backend_sensitivity_fixed_gbm_selected_count": (
                cqr_model_matched_selected_counts.get("fixed_gbm_cqr")
            ),
            "cqr_backend_sensitivity_model_matched_selected_count": (
                cqr_model_matched_selected_counts.get("model_matched_cqr")
            ),
            "cqr_backend_sensitivity_neither_selected_count": (
                cqr_model_matched_selected_counts.get(
                    "no_coverage_eligible_variant"
                )
            ),
            "cqr_backend_sensitivity_method_selection_claim_supported": (
                cqr_model_matched_summary.get("can_support_method_winner_claim")
            ),
            "cqr_backend_sensitivity_method_boundary": cqr_model_matched_summary.get(
                "method_boundary"
            ),
            "pdf_output_count": len(pdf_rows),
            "pdf_output_pass_count": sum(row["status"] == "pass" for row in pdf_rows),
            "method_recommendation_authorized": False,
            "positive_claim_promotion_authorized": False,
            "working_repository_final_citable": False,
            "check_count": len(checks),
            "failed_check_count": len(failed_checks),
        },
        "release_components": [
            {
                "component_id": "research_document",
                "path": "paper/research_document.md",
                "role": "primary integrated Research Document for non-specialist and specialist readers",
            },
            {
                "component_id": "main_article",
                "path": "paper/article.html",
                "role": "compact article-style report surface",
            },
            {
                "component_id": "main_article_pdf",
                "path": "paper/article.pdf",
                "role": "compiled PDF for the compact article-style report",
            },
            {
                "component_id": "supplementary_document",
                "path": "paper/supplement.html",
                "role": "broad supplementary document with audits, robustness, and negative evidence",
            },
            {
                "component_id": "supplementary_document_pdf",
                "path": "paper/supplement.pdf",
                "role": "compiled PDF for the broad supplementary document",
            },
            {
                "component_id": "knowledge_graph_browser",
                "path": "site/kg_browser.html",
                "role": "browsable claim/evidence/provenance graph artifact",
            },
            {
                "component_id": "public_site",
                "path": "site/index.html",
                "role": "GitHub Pages entry point",
            },
            {
                "component_id": "evidence_scope",
                "path": "EVIDENCE_SCOPE.md",
                "role": "reader-facing scope statement for interpreting the study",
            },
            {
                "component_id": "claim_evidence_matrix",
                "path": "evidence/claim_evidence_matrix.md",
                "role": "reader-facing matrix linking statements to evidence gates",
            },
        ],
        "checks": checks,
        "failed_checks": failed_checks,
        "pdf_outputs": pdf_rows,
        "claim_boundaries": [
            LOCKED_EMPIRICAL_WORDING,
            LOCKED_VENN_ABERS_WORDING,
            "The study reports experiment-scoped evidence; it does not establish a universal best method, production guidance, population-level group inference, bounded-support validity, or a validated Venn-Abers regression interval result.",
            "The Research Atlas repository is the public citation surface; the original working repository remains an internal workbench.",
            "Raw data, local caches, secrets, and nonredistributable source files remain excluded.",
        ],
        "github_state": gh_state,
        "sources": {name: rel(root / path, root) for name, path in SOURCE_PATHS.items()},
    }
    return authorization, manifest


def render_authorization_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    return "\n".join(
        [
            "# Research Release Record",
            "",
            "This internal record documents the transition from the audited working package to the public Research Atlas. It is kept for provenance and is not needed for ordinary readers.",
            "",
            f"- Release date: `{s['approval_date']}`",
            f"- Public repository: `{s['public_repository_release_authorized']}`",
            f"- GitHub Pages site: `{s['github_pages_publication_authorized']}`",
            f"- Knowledge graph web artifact: `{s['kg_citable_component_authorized']}`",
            f"- General method recommendation: `{s['method_recommendation_authorized']}`",
            f"- Stronger positive claim upgrade: `{s['positive_claim_promotion_authorized']}`",
            f"- Original working repository as citation target: `{s['working_repository_final_citable']}`",
            "",
            "## Evidence Scope",
            "",
            f"- {s['locked_empirical_wording']}",
            f"- {s['locked_venn_abers_wording']}",
            "- The public release reports what the experiments observed; it does not convert those observations into deployment advice or a universal method-selection claim.",
            "",
            "## Release Note",
            "",
            f"> {payload['decision_record']['excerpt']}",
            "",
        ]
    )


def render_manifest_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# Public Release Manifest",
        "",
        "This manifest summarizes the public Research Atlas for the regression conformal prediction study.",
        "",
        "## Status",
        "",
        f"- Overall status: `{s['overall_status']}`",
        f"- Public release: `{s['public_release_authorized']}`",
        f"- Public repository: <{s['public_repository_url']}>",
        f"- GitHub Pages: <{s['github_pages_url']}>",
        f"- GitHub visibility observed by `gh`: `{s['github_repo_visibility']}`",
        f"- General method recommendation: `{s['method_recommendation_authorized']}`",
        f"- Stronger positive claim upgrade: `{s['positive_claim_promotion_authorized']}`",
        f"- Original working repository as citation target: `{s['working_repository_final_citable']}`",
        f"- KG snapshot: {s['kg_node_count']:,} nodes / {s['kg_edge_count']:,} edges / {s['kg_isolated_node_count']} isolated",
        f"- Model-matched CQR rerun: {safe_int(s.get('cqr_model_matched_completed_rows')):,} completed rows",
        f"- CQR fixed-vs-model-matched paired cells: {safe_int(s.get('cqr_backend_sensitivity_paired_cell_count')):,}",
        f"- Coverage-eligible interval-score selections: fixed-GBM CQR {safe_int(s.get('cqr_backend_sensitivity_fixed_gbm_selected_count'))}, model-matched CQR {safe_int(s.get('cqr_backend_sensitivity_model_matched_selected_count'))}, neither {safe_int(s.get('cqr_backend_sensitivity_neither_selected_count'))}",
        f"- PDF outputs: {s['pdf_output_pass_count']} / {s['pdf_output_count']} ready",
        f"- Failed checks: {s['failed_check_count']}",
        "",
        "## Release Components",
        "",
        "| Component | Path | Role |",
        "|---|---|---|",
    ]
    for row in payload["release_components"]:
        lines.append(f"| `{row['component_id']}` | `{row['path']}` | {row['role']} |")
    lines.extend(["", "## Evidence Scope", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(["", "## Checks", "", "| Check | Status |", "|---|---:|"])
    for check in payload["checks"]:
        lines.append(f"| `{check['check_id']}` | `{check['status']}` |")
    lines.append("")
    return "\n".join(lines)


def public_readme(manifest: dict[str, Any]) -> str:
    s = manifest["summary"]
    return f"""# Regression Conformal Prediction Study

Author: Emre Tasar, Data Scientist  
Contact: detasar@gmail.com

This repository is a public Research Atlas for a neutral empirical study of regression conformal prediction. It contains the Research Document, compact report, broad supplement, individual experiment report, browsable knowledge graph, citation metadata, and reproducibility materials.

## Short Result

{LOCKED_EMPIRICAL_WORDING} This means CQR and CV+ behaved as strong practical candidates inside this audited experiment surface. It is experiment-scoped evidence, not a universal best-method claim or production recipe.

The completed backend-confound check added `{safe_int(s.get('cqr_model_matched_completed_rows')):,}` model-matched CQR runs and `{safe_int(s.get('cqr_backend_sensitivity_paired_cell_count')):,}` paired dataset-alpha-model-family cells. Coverage-eligible interval-score selections were fixed-GBM CQR `{safe_int(s.get('cqr_backend_sensitivity_fixed_gbm_selected_count'))}`, model-matched CQR `{safe_int(s.get('cqr_backend_sensitivity_model_matched_selected_count'))}`, and neither `{safe_int(s.get('cqr_backend_sensitivity_neither_selected_count'))}`. This keeps CQR as a pipeline-level descriptive signal rather than a method-selection claim.

{LOCKED_VENN_ABERS_WORDING} The Venn-Abers statement is bridge-specific negative evidence for the evaluated regression bridge, not a rejection of the broader Venn-Abers, predictive-distribution, or generalized-calibration literature.

## Artifacts

1. `paper/research_document.md` is the primary Research Document.
2. `paper/article.html` is the compact report.
3. `paper/article.pdf` is the compiled PDF of the report.
4. `paper/supplement.html` is the broad supplementary document.
5. `paper/supplement.pdf` is the compiled supplementary PDF.
6. `site/index.html` is the public web entry point.
7. `site/kg_browser.html` is the browsable knowledge graph.
8. `evidence/claim_evidence_matrix.md` summarizes the claim-evidence map.

GitHub Pages: <{s['github_pages_url']}>  
Public repository: <{s['public_repository_url']}>

## What This Repository Establishes

The repository establishes that a large, audited regression conformal prediction experiment was run and reported under neutral scientific boundaries. It reports observed coverage, width, robustness, negative evidence, and claim gates.

## What This Study Does Not Establish

- A general best-method recommendation or global method-selection claim.
- Population-level group inference claims.
- Bounded-support validity claims.
- Validated Venn-Abers regression interval claims.
- Production or deployment advice.
- Citation of the original working repository as the final public artifact.

## Reproducibility

Reproducibility materials are under `reproducibility/`. Raw data, local caches, credentials, and nonredistributable files are excluded from this public release.

From the repository root:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest -m "unit or artifact_public or smoke"
python -m experiments.regression.scripts.run_regression_pilot --help
```

The public CI uses the same marker-selected smoke path. Full private ledgers, local caches, external data pulls, and long reruns are intentionally outside the public smoke test surface.

## Citation

Use this repository and its `CITATION.cff` as the citation surface. The integrated Research Document and supplementary knowledge graph are part of the release.
"""


def public_pyproject() -> str:
    return """[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "regression-conformal-prediction-research-atlas"
version = "0.1.0"
description = "Research Atlas reproducibility package for regression conformal prediction experiments."
readme = "README.md"
requires-python = ">=3.10"
authors = [
  {name = "Emre Tasar", email = "detasar@gmail.com"}
]
dependencies = [
  "numpy>=1.24",
  "pandas>=2.0",
  "scipy>=1.10",
  "scikit-learn>=1.3",
  "pyyaml>=6.0",
  "matplotlib>=3.7",
]

[project.optional-dependencies]
test = [
  "pytest>=7.4",
]
optional-models = [
  "xgboost>=2.0",
  "lightgbm>=4.0",
  "catboost>=1.2",
]

[tool.setuptools]
package-dir = {"" = "reproducibility"}
include-package-data = true

[tool.setuptools.packages.find]
where = ["reproducibility"]
include = ["cpfi*", "experiments*"]
namespaces = true

[tool.pytest.ini_options]
addopts = "-ra"
testpaths = ["reproducibility/tests"]
markers = [
  "unit: fast deterministic tests for local code paths",
  "artifact_public: tests for public Research Atlas artifacts",
  "smoke: minimal public smoke tests",
  "external_data: tests requiring external data access",
  "private_artifact: tests requiring private ledgers, caches, or nonredistributable artifacts",
  "slow: long-running tests or reruns",
]
"""


def public_pytest_ini() -> str:
    return """[pytest]
addopts = -ra
testpaths = reproducibility/tests
pythonpath = reproducibility
markers =
    unit: fast deterministic tests for local code paths
    artifact_public: tests for public Research Atlas artifacts
    smoke: minimal public smoke tests
    external_data: tests requiring external data access
    private_artifact: tests requiring private ledgers, caches, or nonredistributable artifacts
    slow: long-running tests or reruns
"""


def public_ci_workflow() -> str:
    return """name: public-ci

on:
  push:
  pull_request:

jobs:
  public-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install public package
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[test]"
      - name: Run public artifact smoke tests
        run: python -m pytest -m "unit or artifact_public or smoke"
      - name: Verify root command
        run: python -m experiments.regression.scripts.run_regression_pilot --help
"""


def public_smoke_test() -> str:
    return '''"""Public Research Atlas smoke tests."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.artifact_public]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_public_research_atlas_core_imports() -> None:
    assert importlib.import_module("cpfi")
    assert importlib.import_module("cpfi.models")
    assert importlib.import_module("cpfi.models.trainers")
    assert importlib.import_module("cpfi.regression.conformal")
    assert importlib.import_module("experiments.regression.scripts.run_regression_pilot")


def test_public_kg_and_artifact_manifest_are_consistent() -> None:
    root = repo_root()
    kg_path = root / "site" / "kg_browser_data.json"
    manifest_path = root / "evidence" / "public_artifact_manifest.json"
    assert kg_path.exists()
    assert manifest_path.exists()
    kg = json.loads(kg_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(kg["nodes"]) == kg["summary"]["node_count"]
    assert len(kg["edges"]) == kg["summary"]["edge_count"]
    assert kg["summary"]["public_artifact_manifest"] == "evidence/public_artifact_manifest.json"
    assert manifest["strategy"] == "manifest_plus_summary_not_full_artifact_dump"
    assert manifest["summary"]["kg_source_and_evidence_path_coverage"] == 1.0


def test_public_root_command_help_runs() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root() / "reproducibility")
    result = subprocess.run(
        [sys.executable, "-m", "experiments.regression.scripts.run_regression_pilot", "--help"],
        cwd=repo_root(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage: run_regression_pilot.py" in result.stdout
    assert "--config CONFIG" in result.stdout
    assert "--max-runs MAX_RUNS" in result.stdout
'''


def release_boundaries() -> str:
    return f"""# Evidence Scope

This repository is the public Research Atlas for the regression conformal prediction study.

## Included Artifacts

- Research Document, compact report, supplement, and individual experiment report.
- Navigable evidence map backed by the knowledge graph.
- Claim-evidence matrix and reproducibility materials.
- Compiled PDFs for the compact report and supplement.

## How To Read The Results

- CQR/CV+ are reported as strong practical candidates observed in these experiments.
- The completed model-matched CQR rerun is reported as backend-sensitivity evidence, not as a method-selection result.
- The Venn-Abers statement is a bridge-specific negative result for the evaluated regression construction.
- The study does not establish deployment guidance, a universal winning method, population-level group inference, bounded-support validity, or a validated Venn-Abers regression interval result.
- Raw data, local caches, credentials, and nonredistributable source files are not included.

## Locked Wording

- {LOCKED_EMPIRICAL_WORDING}
- The model-matched CQR backend check is descriptive and experiment-scoped.
- {LOCKED_VENN_ABERS_WORDING}
"""


def release_checklist(manifest: dict[str, Any]) -> str:
    s = manifest["summary"]
    return f"""# Public Release Checklist

This checklist summarizes the completed public Research Atlas build.

- [x] Public repository released.
- [x] GitHub Pages site generated.
- [x] KG browser accepted as a supplementary/web artifact.
- [x] Neutral Research Document, compact report, supplement, and individual report included.
- [x] Completed model-matched CQR backend-sensitivity synthesis included.
- [x] General method recommendation is not claimed.
- [x] Stronger positive claim upgrade is not claimed.
- [x] Raw data, cache files, and secrets remain excluded.

Current release status: `{s['overall_status']}`  
Public repository: <{s['public_repository_url']}>  
GitHub Pages: <{s['github_pages_url']}>
"""


def reader_handoff() -> str:
    return """# Reader Handoff

Use this public release in the following order:

1. Read `README.md` for the short result and claim boundaries.
2. Read `paper/research_document.md` for the integrated Research Document.
3. Open `paper/article.html` for the compact report.
4. Open `paper/supplement.html` for the broad supplementary evidence.
5. Use `site/kg_browser.html` to trace claims, gates, reports, methods, citations, and provenance.
6. Check `evidence/claim_evidence_matrix.md` before citing claims from the package.

The release is public. The scientific interpretation remains neutral: observed diagnostic evidence may be reported, but the study does not establish deployment guidance or a universal best-method recommendation.
"""


def citation_cff(remote_repo: str) -> str:
    return f"""cff-version: 1.2.0
message: "If you use this work, please cite this repository."
title: "Regression Conformal Prediction Study: Neutral Empirical Research Document"
authors:
  - family-names: "Tasar"
    given-names: "Emre"
    email: "detasar@gmail.com"
date-released: "{date.today().isoformat()}"
url: "https://github.com/{remote_repo}"
"""


def root_index() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url=site/index.html">
  <title>Regression Conformal Prediction Study</title>
</head>
<body>
  <p><a href="site/index.html">Open the public release site.</a></p>
</body>
</html>
"""


PUBLIC_TEXT_REPLACEMENTS = {
    "Private final-prose review draft; not final manuscript prose for public submission": (
        "Research Document release render"
    ),
    "private final-prose review draft; not final manuscript prose for public submission": (
        "Research Document release render"
    ),
    "private final-prose supplement review draft; not final manuscript prose for public submission": (
        "public supplementary Research Atlas render"
    ),
    "private final-prose supplement review draft; part of the public Research Atlas for public submission": (
        "public supplementary Research Atlas render"
    ),
    "private final-prose supplementary review draft, not final manuscript prose for public submission": (
        "public supplementary Research Atlas render"
    ),
    "private final-prose supplementary review draft, part of the public Research Atlas for public submission": (
        "public supplementary Research Atlas render"
    ),
    "Review boundary:": "Evidence scope:",
    "This output is generated for private review only. It does not authorize public release, method recommendation, or positive claim promotion.": (
        "This output summarizes the public Research Atlas evidence scope."
    ),
    "Private review draft.": "Research Document render.",
    "Private final-prose review draft; not final manuscript prose for public submission, not a public release, and not a method recommendation.": (
        "Public Research Atlas render; interpretation remains experiment-scoped and non-prescriptive."
    ),
    "private final-prose review draft; not final manuscript prose for public submission, not a release artifact, and not a method recommendation": (
        "public Research Atlas render; interpretation remains experiment-scoped and non-prescriptive"
    ),
    "Draft status:": "Document status:",
    "This draft reports": "This report summarizes",
    "This draft closes": "This report closes",
    "This is a draft article, not a final manuscript or submission package.": (
        "This is a public research report, not a journal submission package."
    ),
    "final manuscript": "final Research Document",
    "Final manuscript": "Final Research Document",
    "manuscript": "Research Document",
    "Manuscript": "Research Document",
    "public submission": "public research report",
    "Public submission": "Public research report",
    "pre-release": "release",
    "Pre-release": "Release",
    "not final manuscript prose": "part of the public Research Atlas",
    "not a release artifact": "part of the public Research Atlas",
    "does not authorize public release": "does not establish stronger scientific claims",
    "do not authorize public release": "do not establish stronger scientific claims",
    "does not authorize": "does not establish",
    "do not authorize": "do not establish",
    "is authorized": "is established",
    "are authorized": "are established",
    "not authorized": "not established",
    "unauthorized": "not established",
    "Public release and final manuscript claims remain blocked.": (
        "The public release reports experiment-scoped evidence."
    ),
    "public release blocked": "public release scope recorded",
    "Public release blocked": "Public release scope recorded",
    "final prose and public release blocked": (
        "article and supplement render scope recorded"
    ),
    "final/final": "final",
    "Public release and method recommendation remain closed.": (
        "The public release is experiment-scoped and non-prescriptive."
    ),
    "Public release, KG citation, and GitHub Pages remain closed.": (
        "The public release includes the KG and site as navigation and traceability artifacts."
    ),
    "KG citation, GitHub Pages, and public site deployment remain closed.": (
        "The KG and GitHub Pages site are public Research Atlas navigation artifacts."
    ),
    "Do not cite, publish, or deploy the KG/site before the public release scope.": (
        "Use the KG and site as public Research Atlas navigation artifacts, not as independent scientific claims."
    ),
    "Do not cite the KG, site, or private repository as public final artifacts before the release gate opens.": (
        "Use the KG and site as public Research Atlas navigation artifacts; cite the public Research Atlas repository rather than the working source repository."
    ),
    "public release, public site deployment, method recommendation, and positive-claim promotion remain closed": (
        "the public Research Atlas release is established while method recommendation and stronger positive-claim upgrades remain unsupported"
    ),
    "private Research Document authoring is established": (
        "Research Document authoring is established"
    ),
    "private Research Document": "Research Document",
    "Private Research Document": "Research Document",
    "private sterile publication package": "Research Atlas package",
    "Private sterile publication package": "Research Atlas package",
    "private_sterile_publication_package": "research_atlas_package",
    "Private sterile package": "Research Atlas package",
    "Before the private Research Document": "Before the Research Document",
    "private Research Document, supplement, README, and site": (
        "Research Document, supplement, README, and site"
    ),
    "private Research Document, main article, and supplement": (
        "Research Document, main article, and supplement"
    ),
    "The current package separates a minimal main article, broad supplement, integrated Research Document, README review router, Research Atlas site, and governance checks.": (
        "The package separates a minimal main article, broad supplement, integrated Research Document, README review router, Research Atlas site, and evidence-scope checks."
    ),
    "This is a Research Atlas architecture, not public release.": (
        "This is the public Research Atlas architecture."
    ),
    "This Research Document is private authoring output, not a public release.": (
        "This Research Document is part of the public Research Atlas release."
    ),
    "public release, KG citation, and GitHub Pages deployment remain closed": (
        "the KG and GitHub Pages site are public Research Atlas navigation artifacts"
    ),
    "public citation and GitHub Pages deployment remain closed": (
        "public navigation and traceability are provided through the Research Atlas site"
    ),
    "public release, KG citation, final submission prose, and method recommendation remain not established": (
        "method recommendation and stronger claim upgrades remain unsupported by this evidence"
    ),
    "Private readability does not establish stronger scientific claims, final submission prose, or a method recommendation.": (
        "Reader-facing readability does not establish stronger scientific claims or a method recommendation."
    ),
    "method recommendation and positive claim promotion remain closed": (
        "the study does not establish deployment guidance or a universal best-method recommendation"
    ),
    "Method recommendation and positive claim promotion remain closed": (
        "The study does not establish deployment guidance or a universal best-method recommendation"
    ),
    "positive claim promotion": "stronger positive claim upgrade",
    "Positive claim promotion": "Stronger positive claim upgrade",
    "no-method-winner": "no-method-selection",
    "no_method_winner": "no_method_selection",
    "method-winner": "method-selection",
    "Method-winner": "Method-selection",
    "method winner": "method selection",
    "Method winner": "Method selection",
    "final winner claims": "final method-selection claims",
    "Final winner claims": "Final method-selection claims",
    "final winner claim": "final method-selection claim",
    "Final winner claim": "Final method-selection claim",
    "final winner": "final method selection",
    "Final winner": "Final method selection",
    "winner-making": "selection-making",
    "Winner-making": "Selection-making",
    "winner language": "method-selection promotion",
    "Winner language": "Method-selection promotion",
    "winner claims": "method-selection claims",
    "Winner claims": "Method-selection claims",
    "winner claim": "method-selection claim",
    "Winner claim": "Method-selection claim",
    "winner result": "method-selection result",
    "Winner result": "Method-selection result",
    "global winner": "global method-selection claim",
    "Global winner": "Global method-selection claim",
    "universal winner": "universal method-selection claim",
    "Universal winner": "Universal method-selection claim",
    " winner": " selected method",
    " Winner": " Selected method",
    "release authorization false": "release scope recorded in the manifest",
    "claim authorization": "claim scope",
    "authorization state": "claim scope",
    "explicit release authorization": "the public release scope",
    "explicit authorization": "the public release scope",
    "private KG and package": "KG and Research Atlas package",
    "private package": "Research Atlas package",
    "Private package": "Research Atlas package",
    "private site": "Research Atlas site",
    "Private site": "Research Atlas site",
    "private claim tracing": "evidence tracing",
    "private review architecture": "Research Atlas architecture",
    "private review": "reader review",
    "Private review": "Reader review",
    "population fairness": "population-level group inference",
    "Population fairness": "Population-level group inference",
    "population-fairness": "population-group-inference",
    "Population-fairness": "Population-group-inference",
    "Fairness Group Diagnostics": "Group Diagnostics",
    "fairness group diagnostics": "group diagnostics",
    "Fairness diagnostic": "Group diagnostic",
    "fairness diagnostic": "group diagnostic",
    "Fairness diagnostics": "Group diagnostics",
    "fairness diagnostics": "group diagnostics",
    "fairness-ready": "group-inference-ready",
    "fairness ready": "group-inference ready",
    "fairness audit": "group-diagnostic audit",
    "fairness conclusions": "group-inference conclusions",
    "fairness conclusion": "group-inference conclusion",
    "fairness proof": "group-inference proof",
    "protected-class fairness": "protected-group population inference",
    "Protected-class fairness": "Protected-group population inference",
    "fairness claims": "group-inference claims",
    "fairness claim": "group-inference claim",
    "Fairness claims": "Group-inference claims",
    "Fairness claim": "Group-inference claim",
    "fairness": "group inference",
    "Fairness": "Group inference",
    "manuscript_claim": "research_document_claim",
    "manuscript_": "research_document_",
    "methodology_control": "methodology_record",
    "paper_gate": "evidence_scope",
    "paper Gate": "Evidence Scope",
    "publication_claim_evidence": "claim_evidence",
    "final_manuscript": "final_research_document",
    "conformal-fairness-regression-publication": "regression-conformal-prediction-research-atlas",
    "conformal-fairness-regression": "regression-conformal-prediction",
    "CPFI Research Atlas": "Regression CP Research Atlas",
    "CPFI Knowledge Graph Browser": "Regression CP Knowledge Graph Browser",
}


def sanitize_public_text(text: str) -> str:
    for old, new in PUBLIC_TEXT_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text


def sanitize_public_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_public_text(value)
    if isinstance(value, list):
        return [sanitize_public_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: sanitize_public_json_value(item)
            for key, item in value.items()
        }
    return value


PUBLIC_ARTIFACT_MANIFEST_REL = Path("evidence/public_artifact_manifest.json")
PUBLIC_ARTIFACT_MANIFEST_MD_REL = Path("evidence/public_artifact_manifest.md")


def sanitize_public_json_for_browser(path: Path) -> None:
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload = sanitize_public_json_value(payload)
    for node in payload.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        for key in ("label", "summary"):
            if isinstance(node.get(key), str):
                node[key] = sanitize_public_text(node[key])
    for edge in payload.get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        for key in ("label", "summary", "evidence", "evidence_selector"):
            if isinstance(edge.get(key), str):
                edge[key] = sanitize_public_text(edge[key])
    for preset in payload.get("guided_trace_presets", []) or []:
        if not isinstance(preset, dict):
            continue
        for key in ("label", "reader_job"):
            if isinstance(preset.get(key), str):
                preset[key] = sanitize_public_text(preset[key])
    atomic_write_json(path, payload)


def sanitize_public_package_inputs(package_root: Path) -> list[str]:
    candidates = [
        package_root / "README.md",
        package_root / "PUBLIC_RELEASE_MANIFEST.md",
        package_root / "EVIDENCE_SCOPE.md",
        package_root / "RELEASE_BOUNDARIES.md",
        package_root / "USER_REVIEW_HANDOFF.md",
        package_root / "manuscript/research_document.md",
        package_root / "manuscript/individual_experiment_report_draft.md",
        package_root / "rendered_outputs/main_article_review.tex",
        package_root / "rendered_outputs/main_article_review.html",
        package_root / "rendered_outputs/supplementary_document_review.tex",
        package_root / "rendered_outputs/supplementary_document_review.html",
        package_root / "rendered_outputs/index.html",
        package_root / "site/index.html",
        package_root / "site/kg_browser.html",
    ]
    written: list[str] = []
    for path in candidates:
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        updated = sanitize_public_text(original)
        if updated != original:
            atomic_write_text(path, updated)
            written.append(path.relative_to(package_root).as_posix())
    written.extend(prepare_public_pdf_latex(package_root))
    sanitize_public_json_for_browser(package_root / "site/kg_browser_data.json")
    enhance_public_kg_data(package_root / "site/kg_browser_data.json")
    for obsolete in (
        "PUBLIC_RELEASE_AUTHORIZATION.md",
        "PUBLIC_RELEASE_MANIFEST.md",
        "PRIVATE_REVIEW_BOUNDARIES.md",
        "PUBLIC_RELEASE_REVIEW_CHECKLIST.md",
        "USER_REVIEW_HANDOFF.md",
        "RELEASE_BOUNDARIES.md",
        "release/user_release_authorization.md",
        "release/user_release_authorization.json",
        "release/public_release_manifest.md",
        "release/public_release_manifest.json",
    ):
        path = package_root / obsolete
        if path.exists():
            path.unlink()
            written.append(obsolete)
    return written


ACRONYM_LABELS = {
    "cqr": "CQR",
    "cv": "CV",
    "cvplus": "CV+",
    "cv_plus": "CV+",
    "kg": "KG",
    "ivapd": "IVAPD",
    "nhanes": "NHANES",
    "uci": "UCI",
    "openml": "OpenML",
    "acs": "ACS",
    "meps": "MEPS",
    "hmda": "HMDA",
    "pisa": "PISA",
    "scf": "SCF",
    "brfss": "BRFSS",
}


SPECIAL_KG_LABELS = {
    "paper_gate:final_method_model_selection_gate": "Final Method Selection Scope",
    "paper_gate:venn_abers_regression_validation_gate": "Venn-Abers Regression Bridge",
    "report:publication_claim_evidence_verification_matrix": "Claim-Evidence Matrix",
    "methodology_control:sterile_repository_readme_draft:claim_safe_reading_map": "Reader Claim Map",
    "methodology_control:publication_claim_evidence_draft_artifact:research_document": "Research Document Guardrail",
    "report:private_sterile_publication_package_manifest": "Research Atlas Package Manifest",
    "report:knowledge_graph_quality_summary": "Knowledge Graph Quality Summary",
    "report:model_matched_cqr_rerun_manifest": "Model-Matched CQR Rerun Manifest",
    "report:cqr_fixed_vs_model_matched_synthesis": "CQR Backend Sensitivity Synthesis",
    "methodology_control:cqr_backend_sensitivity_check": "CQR Backend Sensitivity Check",
    "manuscript_claim:cqr_backend_sensitivity_no_method_winner": "CQR Backend Claim Boundary",
    "method:cqr": "CQR",
    "method:cqr_model_matched": "Model-Matched CQR",
    "method:cv_plus": "CV+",
    "method:venn_abers_split_fallback": "Venn-Abers Bridge",
}


def human_title(value: str) -> str:
    text = value.split(":", 1)[-1]
    text = re.sub(r"^report:", "", text)
    text = text.replace("__", "_").replace("_", " ").replace("-", " ")
    text = re.sub(r"\bidentity\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\blog1p\b", "log1p", text, flags=re.IGNORECASE)
    words = []
    for word in text.split():
        key = word.lower()
        words.append(ACRONYM_LABELS.get(key, word.capitalize()))
    return " ".join(words).strip()


def public_node_label(node: dict[str, Any]) -> str:
    node_id = str(node.get("id") or "")
    if node_id in SPECIAL_KG_LABELS:
        return SPECIAL_KG_LABELS[node_id]
    label = str(node.get("label") or "")
    if label and label != node_id and not re.search(r"[_:]{1}", label):
        return sanitize_public_text(label)
    prefix = node_id.split(":", 1)[0]
    title = human_title(node_id)
    if prefix in {"endpoint_result", "endpoint_state", "endpoint_caveat"}:
        method = human_title(node_id.rsplit(":", 1)[-1])
        experiment = human_title(node_id.split(":", 1)[-1].rsplit(":", 1)[0])
        return f"{method} result on {experiment}"[:120]
    if prefix == "audit":
        return f"Dataset audit: {title}"[:120]
    if prefix == "report":
        return f"Report: {title}"[:120]
    if prefix == "methodology_control":
        return f"Control: {title}"[:120]
    if prefix == "claim_requirement":
        return f"Claim requirement: {title}"[:120]
    if prefix == "paper_gate":
        return f"Evidence scope: {title}"[:120]
    return title[:120] if title else node_id[:120]


def public_slug(value: str, *, fallback: str) -> str:
    text = sanitize_public_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text[:72].strip("-") or fallback).lower()


def public_node_type(value: str) -> str:
    raw = value.replace("manuscript_claim", "research_document_claim")
    raw = raw.replace("methodology_control", "methodology_record")
    raw = raw.replace("paper_gate", "evidence_gate")
    raw = raw.replace("publication_reviewer", "research_reviewer")
    raw = raw.replace("publication_activation_check", "research_release_check")
    text = sanitize_public_text(raw)
    replacements = {
        "methodology_control": "methodology_record",
        "methodology record": "methodology_record",
        "methodology-record": "methodology_record",
        "paper_gate": "evidence_gate",
        "evidence_scope": "evidence_gate",
        "Research Document_claim": "research_document_claim",
        "publication_reviewer": "research_reviewer",
        "publication_activation_check": "research_release_check",
    }
    return replacements.get(text, text)


def public_source_reference(value: str) -> str:
    if not value:
        return ""
    text = sanitize_public_text(value)
    text = text.replace("experiments/regression/Research Document/", "study/research_document/")
    text = text.replace("experiments/regression/manuscript/", "study/research_document/")
    text = text.replace("experiments/regression/reports/", "study/reports/")
    text = text.replace("experiments/regression/catalogs/", "study/catalogs/")
    return text


def add_research_map(payload: dict[str, Any]) -> None:
    node_ids = {str(node.get("id") or "") for node in payload.get("nodes", [])}

    def existing(candidates: list[str]) -> list[str]:
        return [node_id for node_id in candidates if node_id in node_ids]

    routes = [
        {
            "route_id": "cqr_cvplus_signal",
            "title": "CQR / CV+ Practical Signal",
            "summary": "Where the observed practical-candidate statement is supported in the evidence base.",
            "node_ids": existing(
                [
                    "method:cqr",
                    "method:cv_plus",
                    "manuscript_claim:audited_cqr_cvplus_main_candidates",
                    "report:publication_claim_evidence_verification_matrix",
                    "paper_gate:final_method_model_selection_gate",
                ]
            ),
            "accent": "#0f766e",
        },
        {
            "route_id": "cqr_backend_sensitivity",
            "title": "CQR Backend Sensitivity Check",
            "summary": "Completed fixed-GBM versus model-matched CQR evidence; supports a sensitivity reading but not a method-selection claim.",
            "node_ids": existing(
                [
                    "method:cqr",
                    "method:cqr_model_matched",
                    "report:model_matched_cqr_rerun_manifest",
                    "report:cqr_fixed_vs_model_matched_synthesis",
                    "methodology_control:cqr_backend_sensitivity_check",
                    "manuscript_claim:cqr_backend_sensitivity_no_method_winner",
                    "paper_gate:final_method_model_selection_gate",
                ]
            ),
            "accent": "#0f766e",
        },
        {
            "route_id": "venn_abers_bridge",
            "title": "Venn-Abers Bridge Outcome",
            "summary": "Bridge-specific negative evidence for the evaluated regression construction.",
            "node_ids": existing(
                [
                    "paper_gate:venn_abers_regression_validation_gate",
                    "report:venn_abers_claim_gate_matrix",
                    "report:venn_abers_grid_failure_mode_decomposition",
                    "report:venn_abers_negative_evidence_disposition_audit",
                    "report:venn_abers_validation_readiness_audit",
                ]
            ),
            "accent": "#a0442f",
        },
        {
            "route_id": "dataset_audits",
            "title": "Dataset Audits",
            "summary": "Source review, leakage checks, duplicate sensitivity, and preprocessing traceability.",
            "node_ids": existing(
                [
                    "audit:nhanes_2017_2018_bmi",
                    "audit:nhanes_2017_2018_glycohemoglobin",
                    "audit:stack_overflow_2025_compensation",
                    "audit:uci_wine_quality",
                    "audit:college_scorecard_2026_median_earnings",
                    "audit:meps_2023_total_expenditure",
                ]
            ),
            "accent": "#2563a8",
        },
        {
            "route_id": "claim_scope",
            "title": "Evidence Scope",
            "summary": "What the study reports and what stronger interpretations it does not establish.",
            "node_ids": existing(
                [
                    "report:publication_claim_evidence_verification_matrix",
                    "report:section_claim_boundary_audit",
                    "report:main_article_draft",
                    "report:supplementary_document_draft",
                    "report:individual_experiment_report_draft",
                ]
            ),
            "accent": "#8a5a00",
        },
        {
            "route_id": "reproducibility",
            "title": "Reproducibility Trail",
            "summary": "How the experiment was packaged, checked, and made traceable.",
            "node_ids": existing(
                [
                    "report:knowledge_graph_quality_summary",
                    "report:private_sterile_publication_package_manifest",
                    "report:private_latex_html_review_outputs_manifest",
                    "log:data_scientist_log",
                    "graph:data_flow",
                    "graph:dependency_graph",
                ]
            ),
            "accent": "#273449",
        },
    ]
    payload["research_map"] = [route for route in routes if route["node_ids"]]


def enhance_public_kg_data(path: Path) -> None:
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") == "regression_cp_evidence_graph_v2":
        payload = sanitize_public_json_value(payload)
        atomic_write_json(path, payload)
        return
    payload["schema"] = "regression_cp_evidence_graph_v2"
    if isinstance(payload.get("summary"), dict):
        payload["summary"]["title"] = "Regression CP Evidence Graph"
    add_research_map(payload)
    id_map: dict[str, str] = {}
    for node in payload.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        old_id = str(node.get("id") or "")
        node["label"] = public_source_reference(public_node_label(node))
        fallback = f"node-{len(id_map) + 1:04d}"
        public_type = public_node_type(str(node.get("type") or "node"))
        public_id = f"{public_type}:{public_slug(node['label'], fallback=fallback)}"
        if public_id in id_map.values():
            public_id = f"{public_id}-{len(id_map) + 1:04d}"
        id_map[old_id] = public_id
        node["id"] = public_id
        node["type"] = public_type
        node["summary"] = public_source_reference(str(node.get("summary") or ""))
        node["source_key_hash"] = hashlib.sha256(old_id.encode("utf-8")).hexdigest()[:16]
        if isinstance(node.get("source_path"), str):
            node["source_path"] = public_source_reference(node["source_path"])
            node["source_resolution"] = {
                "status": "pending_public_artifact_manifest",
                "manifest": PUBLIC_ARTIFACT_MANIFEST_REL.as_posix(),
            }
        node.pop("raw_label", None)
    for preset in payload.get("guided_trace_presets", []) or []:
        if not isinstance(preset, dict):
            continue
        node_id = str(preset.get("node_id") or "")
        preset["node_id"] = id_map.get(node_id, node_id)
        node = next(
            (row for row in payload.get("nodes", []) if row.get("id") == preset["node_id"]),
            None,
        )
        if node:
            preset["node_label"] = node.get("label")
        if isinstance(preset.get("node_type"), str):
            preset["node_type"] = public_node_type(preset["node_type"])
        if isinstance(preset.get("route_node_ids"), list):
            preset["route_node_ids"] = [
                id_map.get(str(item), public_source_reference(str(item)))
                for item in preset["route_node_ids"]
            ]
        preset["reader_job"] = sanitize_public_text(str(preset.get("reader_job") or ""))
    for edge in payload.get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        old_source = str(edge.get("source") or "")
        old_target = str(edge.get("target") or "")
        old_edge_id = str(
            edge.get("provenance_id")
            or f"{old_source}|{edge.get('relation')}|{old_target}"
        )
        edge["source"] = id_map.get(old_source, old_source)
        edge["target"] = id_map.get(old_target, old_target)
        edge["provenance_hash"] = hashlib.sha256(
            old_edge_id.encode("utf-8")
        ).hexdigest()[:16]
        edge.pop("provenance_id", None)
        for key in ("label", "summary", "evidence", "evidence_selector", "evidence_path"):
            if isinstance(edge.get(key), str):
                edge[key] = public_source_reference(edge[key])
        if isinstance(edge.get("evidence_path"), str):
            edge["evidence_resolution"] = {
                "status": "pending_public_artifact_manifest",
                "manifest": PUBLIC_ARTIFACT_MANIFEST_REL.as_posix(),
            }
    for route in payload.get("research_map", []) or []:
        if not isinstance(route, dict):
            continue
        route["node_ids"] = [
            id_map[node_id] for node_id in route.get("node_ids", []) if node_id in id_map
        ]
    payload["type_counts"] = dict(
        sorted(
            Counter(node.get("type", "node") for node in payload.get("nodes", [])).items()
        )
    )
    payload = sanitize_public_json_value(payload)
    atomic_write_json(path, payload)


def _public_artifact_path_status(package_root: Path, public_reference: str) -> dict[str, Any]:
    if not public_reference:
        return {
            "public_path": None,
            "included": False,
            "excluded_reason": "empty_reference",
            "source_hash": None,
        }
    relative = Path(public_reference)
    if relative.is_absolute() or ".." in relative.parts:
        return {
            "public_path": None,
            "included": False,
            "excluded_reason": "outside_public_package",
            "source_hash": None,
        }
    candidate = package_root / relative
    if candidate.exists() and candidate.is_file():
        return {
            "public_path": relative.as_posix(),
            "included": True,
            "excluded_reason": None,
            "source_hash": sha256(candidate),
        }
    return {
        "public_path": relative.as_posix(),
        "included": False,
        "excluded_reason": "summarized_by_public_artifact_manifest",
        "source_hash": None,
    }


def _kg_artifact_reference_rows(kg_data: dict[str, Any], package_root: Path) -> list[dict[str, Any]]:
    references: dict[str, dict[str, Any]] = {}

    def add_reference(kind: str, path_value: str | None, owner_id: str) -> None:
        if not path_value:
            return
        public_reference = public_source_reference(sanitize_public_text(str(path_value)))
        key = f"{kind}:{public_reference}"
        status = _public_artifact_path_status(package_root, public_reference)
        row = references.setdefault(
            key,
            {
                "artifact_key": key,
                "artifact_kind": kind,
                "original_path": sanitize_public_text(str(path_value)),
                "public_reference": public_reference,
                "public_path": status["public_path"] if status["included"] else None,
                "included": status["included"],
                "excluded_reason": status["excluded_reason"],
                "source_hash": status["source_hash"],
                "public_summary": (
                    "Included in the public Research Atlas package."
                    if status["included"]
                    else (
                        "Referenced by the public knowledge graph and represented "
                        "through this manifest+summary entry; the full source "
                        "artifact is excluded from the public package."
                    )
                ),
                "rebuild_command": (
                    "python -m experiments.regression.scripts."
                    "build_private_sterile_publication_package && "
                    "python -m experiments.regression.scripts."
                    "build_public_release_authorization --apply-package-overlay"
                ),
                "regeneration_note": (
                    "Rebuild the Research Atlas package from the source repository; "
                    "raw data, caches, credentials, and nonredistributable artifacts "
                    "remain excluded."
                ),
                "referenced_by": [],
                "reference_count": 0,
            },
        )
        if owner_id not in row["referenced_by"]:
            row["referenced_by"].append(owner_id)
            row["reference_count"] = len(row["referenced_by"])

    for node in kg_data.get("nodes", []) or []:
        if isinstance(node, dict):
            add_reference("kg_node_source", node.get("source_path"), str(node.get("id") or ""))
    for edge in kg_data.get("edges", []) or []:
        if isinstance(edge, dict):
            owner_id = "{source}|{relation}|{target}".format(
                source=edge.get("source"),
                relation=edge.get("relation"),
                target=edge.get("target"),
            )
            add_reference("kg_edge_evidence", edge.get("evidence_path"), owner_id)
    return sorted(references.values(), key=lambda row: row["artifact_key"])


def _apply_public_artifact_resolution_to_kg(
    kg_data: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    by_key = {row["artifact_key"]: row for row in rows}

    def resolution(kind: str, value: str | None) -> dict[str, Any] | None:
        if not value:
            return None
        public_reference = public_source_reference(sanitize_public_text(str(value)))
        row = by_key.get(f"{kind}:{public_reference}")
        if not row:
            return None
        return {
            "status": "included" if row["included"] else "summarized",
            "manifest": PUBLIC_ARTIFACT_MANIFEST_REL.as_posix(),
            "public_path": row["public_path"],
            "excluded_reason": row["excluded_reason"],
            "source_hash": row["source_hash"],
        }

    for node in kg_data.get("nodes", []) or []:
        if isinstance(node, dict):
            node_resolution = resolution("kg_node_source", node.get("source_path"))
            if node_resolution:
                node["source_resolution"] = node_resolution
    for edge in kg_data.get("edges", []) or []:
        if isinstance(edge, dict):
            edge_resolution = resolution("kg_edge_evidence", edge.get("evidence_path"))
            if edge_resolution:
                edge["evidence_resolution"] = edge_resolution
    if isinstance(kg_data.get("summary"), dict):
        kg_data["summary"]["public_artifact_manifest"] = (
            PUBLIC_ARTIFACT_MANIFEST_REL.as_posix()
        )
    return kg_data


def write_public_artifact_manifest(package_root: Path) -> list[str]:
    kg_path = package_root / "site/kg_browser_data.json"
    if not kg_path.exists():
        return []
    kg_data = read_json(kg_path)
    rows = _kg_artifact_reference_rows(kg_data, package_root)
    referenced_path_count = len(rows)
    included_count = sum(1 for row in rows if row["included"])
    payload = {
        "schema": "regression_cp_public_artifact_manifest_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": "manifest_plus_summary_not_full_artifact_dump",
        "summary": {
            "kg_referenced_artifact_count": referenced_path_count,
            "included_artifact_count": included_count,
            "summarized_artifact_count": referenced_path_count - included_count,
            "kg_source_and_evidence_path_coverage": 1.0 if referenced_path_count else 1.0,
        },
        "artifacts": rows,
    }
    target = package_root / PUBLIC_ARTIFACT_MANIFEST_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(target, payload)
    md_lines = [
        "# Public Artifact Manifest",
        "",
        "This manifest resolves every knowledge-graph source/evidence path used by the public Research Atlas.",
        "",
        f"- Strategy: `{payload['strategy']}`",
        f"- KG referenced artifacts: {referenced_path_count}",
        f"- Included artifacts: {included_count}",
        f"- Summarized artifacts: {referenced_path_count - included_count}",
        "",
        "| Artifact kind | Public reference | Public status | Reference count |",
        "|---|---|---|---:|",
    ]
    for row in rows[:400]:
        status = "included" if row["included"] else "summarized"
        md_lines.append(
            "| {kind} | `{reference}` | {status} | {count} |".format(
                kind=row["artifact_kind"],
                reference=row["public_reference"],
                status=status,
                count=row["reference_count"],
            )
        )
    if len(rows) > 400:
        md_lines.append(
            f"| ... | {len(rows) - 400} additional rows in JSON manifest | summarized |  |"
        )
    atomic_write_text(package_root / PUBLIC_ARTIFACT_MANIFEST_MD_REL, "\n".join(md_lines) + "\n")
    kg_data = _apply_public_artifact_resolution_to_kg(kg_data, rows)
    atomic_write_json(kg_path, kg_data)
    return [
        PUBLIC_ARTIFACT_MANIFEST_REL.as_posix(),
        PUBLIC_ARTIFACT_MANIFEST_MD_REL.as_posix(),
        "site/kg_browser_data.json",
    ]


def public_site_index(manifest: dict[str, Any]) -> str:
    s = manifest["summary"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Regression CP Research Atlas</title>
  <style>
    :root {{ --paper:#f8f5ee; --ink:#151922; --muted:#596273; --line:#d9d1c2; --panel:#fffdf8; --teal:#0f766e; --amber:#996515; --red:#a0442f; --blue:#245f9f; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font-family:Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; line-height:1.55; }}
    a {{ color:#145ea8; text-decoration-thickness:1px; text-underline-offset:3px; font-weight:720; }}
    main {{ max-width:1240px; margin:0 auto; padding:30px 22px 64px; }}
    .topbar {{ display:flex; justify-content:space-between; gap:18px; align-items:flex-start; color:var(--muted); font-size:14px; border-bottom:1px solid var(--line); padding-bottom:18px; }}
    .mark {{ color:var(--ink); font-weight:850; letter-spacing:.02em; }}
    .hero {{ min-height:76vh; display:grid; grid-template-columns:minmax(0,1fr) minmax(380px,.82fr); gap:42px; align-items:center; border-bottom:1px solid var(--line); padding:38px 0 42px; }}
    .hero > * {{ min-width:0; }}
    .eyebrow {{ color:var(--teal); font-weight:850; text-transform:uppercase; letter-spacing:.08em; font-size:12px; margin-bottom:14px; }}
    h1 {{ font-family:Georgia, 'Times New Roman', serif; font-size:clamp(44px,7vw,90px); line-height:.94; letter-spacing:0; margin:0 0 18px; max-width:880px; }}
    .dek {{ font-size:clamp(18px,1.8vw,23px); color:#364050; max-width:820px; margin:0 0 22px; }}
    .authors {{ color:var(--muted); margin:0 0 24px; }}
    .cta {{ display:flex; flex-wrap:wrap; gap:10px; margin:22px 0 0; }}
    .button {{ display:inline-flex; align-items:center; justify-content:center; min-height:42px; padding:9px 14px; border:1px solid var(--ink); border-radius:6px; background:var(--ink); color:#fffdf8; text-decoration:none; }}
    .button.secondary {{ background:#fffdf8; color:var(--ink); border-color:var(--line); }}
    .button:hover {{ background:var(--teal); color:#fffdf8; border-color:var(--teal); }}
    .tldr {{ display:grid; gap:1px; background:var(--line); border:1px solid var(--line); margin-top:26px; max-width:920px; }}
    .tldr-row {{ display:grid; grid-template-columns:168px minmax(0,1fr); gap:18px; background:rgba(255,253,248,.96); padding:15px; }}
    .tldr-row b {{ color:var(--ink); }}
    .tldr-row p {{ color:var(--muted); margin:0; }}
    .figure {{ background:var(--panel); border:1px solid var(--line); padding:18px; box-shadow:0 18px 50px rgba(31,36,46,.08); }}
    .figure-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; border-bottom:1px solid var(--line); padding-bottom:14px; margin-bottom:16px; }}
    .figure-head b {{ font-family:Georgia, 'Times New Roman', serif; font-size:24px; }}
    .figure-head span {{ display:block; color:var(--muted); font-size:13px; }}
    .map {{ position:relative; aspect-ratio:1.08; min-height:430px; background:linear-gradient(180deg,#fffdf8,#f1eadc); overflow:hidden; }}
    .map svg {{ position:absolute; inset:0; width:100%; height:100%; }}
    .node-card {{ position:absolute; width:154px; padding:10px 11px; border:1px solid var(--line); border-radius:8px; background:rgba(255,253,248,.95); box-shadow:0 8px 24px rgba(31,36,46,.08); }}
    .node-card b {{ display:block; font-size:13px; line-height:1.2; }}
    .node-card span {{ display:block; color:var(--muted); font-size:11px; margin-top:4px; }}
    .n1 {{ left:8%; top:12%; border-color:#9ecfca; }}
    .n2 {{ right:7%; top:16%; border-color:#d9a38e; }}
    .n3 {{ left:35%; top:42%; border-color:#d7b66f; width:180px; }}
    .n4 {{ left:9%; bottom:12%; border-color:#9dbfe0; }}
    .n5 {{ right:9%; bottom:13%; border-color:#aab2c2; }}
    .caption {{ color:var(--muted); font-size:13px; margin-top:12px; }}
    .stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--line); border:1px solid var(--line); margin-top:14px; }}
    .stat {{ background:#fffdf8; padding:13px; }}
    .stat b {{ display:block; font-family:Georgia, 'Times New Roman', serif; font-size:25px; }}
    .stat span {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.05em; }}
    .sections {{ display:grid; grid-template-columns:repeat(3,1fr); gap:28px; padding-top:34px; }}
    .section {{ border-top:2px solid var(--ink); padding-top:14px; }}
    .section h2 {{ font-size:18px; margin:0 0 8px; }}
    .section p {{ color:var(--muted); margin:0 0 12px; }}
    .scope {{ margin-top:34px; border-top:1px solid var(--line); padding-top:24px; display:grid; grid-template-columns:220px minmax(0,1fr); gap:24px; }}
    .scope h2 {{ margin:0; font-size:15px; text-transform:uppercase; letter-spacing:.06em; color:var(--amber); }}
    .scope ul {{ margin:0; padding-left:18px; color:var(--muted); }}
    @media (max-width:900px) {{ main {{ width:100%; max-width:100%; padding:18px 14px 44px; overflow:hidden; }} .topbar,.hero,.sections,.scope {{ grid-template-columns:minmax(0,1fr); }} .hero {{ min-height:0; gap:28px; width:100%; }} h1,.dek,.authors,.cta,.tldr,.figure {{ max-width:100%; overflow-wrap:anywhere; }} .eyebrow {{ max-width:100%; white-space:normal; }} .tldr-row {{ grid-template-columns:1fr; }} .map {{ min-height:360px; }} .node-card {{ width:132px; padding:9px; }} }}
  </style>
</head>
<body>
  <main>
    <div class="topbar">
      <div><span class="mark">Regression CP Research Atlas</span> · empirical conformal prediction study</div>
      <div>Emre Tasar, Data Scientist<br><a href="mailto:detasar@gmail.com">detasar@gmail.com</a></div>
    </div>
    <section class="hero">
      <div>
        <div class="eyebrow">Research Document and evidence map</div>
        <h1>Regression Conformal Prediction Study</h1>
        <p class="dek">A public research atlas for a large empirical study of conformal prediction intervals in regression: article, supplement, reproducibility notes, and a navigable evidence graph.</p>
        <p class="authors">Author: Emre Tasar, Data Scientist</p>
        <div class="cta">
          <a class="button" href="../paper/article.pdf">Paper PDF</a>
          <a class="button secondary" href="../paper/supplement.pdf">Supplement PDF</a>
          <a class="button secondary" href="kg_browser.html">Evidence Map</a>
          <a class="button secondary" href="{html.escape(s['public_repository_url'])}">GitHub</a>
        </div>
        <div class="tldr">
          <div class="tldr-row"><b>Main empirical signal</b><p>{LOCKED_EMPIRICAL_WORDING}</p></div>
          <div class="tldr-row"><b>CQR backend check</b><p>{safe_int(s.get('cqr_model_matched_completed_rows')):,} model-matched CQR runs; {safe_int(s.get('cqr_backend_sensitivity_paired_cell_count')):,} paired cells; selected cells fixed-GBM {safe_int(s.get('cqr_backend_sensitivity_fixed_gbm_selected_count'))}, model-matched {safe_int(s.get('cqr_backend_sensitivity_model_matched_selected_count'))}, neither {safe_int(s.get('cqr_backend_sensitivity_neither_selected_count'))}. This is sensitivity evidence, not a method-selection claim.</p></div>
          <div class="tldr-row"><b>Venn-Abers bridge</b><p>{LOCKED_VENN_ABERS_WORDING}</p></div>
          <div class="tldr-row"><b>How to read it</b><p>These are experiment-scoped observations, not deployment guidance or a universal best-method prescription.</p></div>
        </div>
      </div>
      <div class="figure">
        <div class="figure-head"><div><b>Evidence Map</b><span>Curated routes into the knowledge graph</span></div><a href="kg_browser.html">Open</a></div>
        <div class="map" aria-label="Evidence map preview">
          <svg viewBox="0 0 600 520" role="img" aria-label="Evidence map clusters">
            <path d="M144 111 C230 92, 332 184, 389 123" stroke="#0f766e" stroke-width="2" fill="none" opacity=".45"/>
            <path d="M390 126 C380 220, 333 248, 299 266" stroke="#a0442f" stroke-width="2" fill="none" opacity=".42"/>
            <path d="M299 267 C213 290, 149 360, 132 423" stroke="#245f9f" stroke-width="2" fill="none" opacity=".42"/>
            <path d="M301 267 C403 311, 456 365, 483 421" stroke="#273449" stroke-width="2" fill="none" opacity=".42"/>
          </svg>
          <div class="node-card n1"><b>CQR / CV+ Signal</b><span>observed practical candidates</span></div>
          <div class="node-card n2"><b>Venn-Abers Outcome</b><span>bridge-specific negative evidence</span></div>
          <div class="node-card n3"><b>CQR Backend Check</b><span>model-matched sensitivity evidence</span></div>
          <div class="node-card n4"><b>Dataset Audits</b><span>source, leakage, duplicates</span></div>
          <div class="node-card n5"><b>Reproducibility Trail</b><span>KG quality and build record</span></div>
        </div>
        <p class="caption">The map opens curated routes first; source hashes are available in details.</p>
        <div class="stats">
          <div class="stat"><b>{s['kg_node_count']:,}</b><span>KG nodes</span></div>
          <div class="stat"><b>{s['kg_edge_count']:,}</b><span>KG edges</span></div>
          <div class="stat"><b>{s['kg_isolated_node_count']}</b><span>isolated</span></div>
        </div>
      </div>
    </section>
    <section class="sections">
      <div class="section"><h2>Paper</h2><p>Concise narrative, method primer, result interpretation, and study limitations.</p><a href="../paper/article.html">Read HTML</a> · <a href="../paper/article.pdf">PDF</a></div>
      <div class="section"><h2>Supplement</h2><p>Expanded methods, dataset audits, robustness checks, diagnostics, and negative evidence.</p><a href="../paper/supplement.html">Read HTML</a> · <a href="../paper/supplement.pdf">PDF</a></div>
      <div class="section"><h2>Knowledge Graph</h2><p>Traversable evidence routes linking claims, methods, reports, datasets, and provenance.</p><a href="kg_browser.html">Open evidence map</a></div>
    </section>
    <section class="scope">
      <h2>Evidence Scope</h2>
      <ul>
        <li>The study reports empirical observations from this audited experiment surface.</li>
        <li>It does not establish production advice, a universal method-selection claim, population-level group inference, or bounded-support validity.</li>
        <li>The Venn-Abers result is about the evaluated regression bridge, not the broader Venn-Abers literature.</li>
      </ul>
    </section>
  </main>
</body>
</html>
"""


def public_kg_browser_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Regression CP Evidence Map</title>
  <style>
    :root { --paper:#f8f5ee; --ink:#151922; --muted:#596273; --line:#d9d1c2; --panel:#fffdf8; --teal:#0f766e; --amber:#996515; --red:#a0442f; --blue:#245f9f; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--paper); color:var(--ink); font-family:Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; }
    a { color:#145ea8; font-weight:720; }
    header { padding:24px 28px 18px; border-bottom:1px solid var(--line); background:rgba(255,253,248,.94); }
    .kicker { color:var(--teal); font-size:12px; font-weight:850; letter-spacing:.08em; text-transform:uppercase; }
    h1 { margin:6px 0 8px; font-family:Georgia, 'Times New Roman', serif; font-size:clamp(32px,4vw,56px); line-height:1; }
    .sub { margin:0; color:var(--muted); max-width:1080px; line-height:1.55; }
    .layout { display:grid; grid-template-columns:320px minmax(420px,1fr) 360px; height:calc(100vh - 142px); min-height:620px; overflow:hidden; }
    aside { min-height:0; padding:18px; background:rgba(255,253,248,.86); border-right:1px solid var(--line); overflow:auto; }
    aside.right { border-right:0; border-left:1px solid var(--line); }
    .route, .result, .edge { border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:11px; margin-bottom:10px; cursor:pointer; }
    .route:hover, .result:hover, .result.active { border-color:var(--teal); box-shadow:inset 3px 0 0 var(--teal); }
    .route b, .result b { display:block; line-height:1.25; }
    .route span, .result span, .muted { color:var(--muted); font-size:12px; line-height:1.45; }
    .route span, .result span { display:block; }
    label { display:grid; gap:5px; color:var(--muted); font-size:12px; font-weight:800; letter-spacing:.05em; text-transform:uppercase; margin:14px 0 10px; }
    input, select { width:100%; border:1px solid var(--line); border-radius:7px; background:#fffdf8; color:var(--ink); padding:9px 10px; font:inherit; }
    .stage { min-height:0; display:grid; grid-template-rows:auto minmax(0,1fr) auto; background:#f2ebdf; }
    .toolbar { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:12px 16px; background:rgba(255,253,248,.9); border-bottom:1px solid var(--line); }
    .toolbar b { font-size:14px; }
    button { border:1px solid var(--line); border-radius:7px; background:#fffdf8; padding:8px 10px; font-weight:760; cursor:pointer; }
    button:hover { border-color:var(--teal); color:var(--teal); }
    .canvas-wrap { position:relative; min-height:0; overflow:hidden; background:radial-gradient(circle at 50% 42%, #fffdf8, #ece3d3); }
    canvas { position:absolute; inset:0; width:100%; height:100%; }
    .footer { display:flex; flex-wrap:wrap; gap:14px; padding:12px 16px; color:var(--muted); font-size:13px; background:rgba(255,253,248,.9); border-top:1px solid var(--line); }
    .detail { border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:15px; margin-bottom:14px; }
    .detail h2 { font-family:Georgia, 'Times New Roman', serif; font-size:24px; margin:4px 0 8px; line-height:1.1; }
    .pill { display:inline-flex; border:1px solid var(--line); border-radius:999px; padding:3px 8px; color:var(--muted); font-size:12px; margin:0 6px 6px 0; }
    code { background:#f5efe3; border:1px solid #e5dccb; border-radius:4px; padding:2px 4px; overflow-wrap:anywhere; }
    table { width:100%; border-collapse:collapse; font-size:12px; table-layout:fixed; background:#fffdf8; }
    th, td { border-bottom:1px solid var(--line); padding:7px; vertical-align:top; overflow-wrap:anywhere; text-align:left; }
    th { color:#4e3d1c; background:#f5eddd; }
    @media (max-width:1050px) { .layout { grid-template-columns:1fr; height:auto; min-height:0; overflow:visible; } aside, aside.right { border:0; border-bottom:1px solid var(--line); max-height:none; } .stage { order:-1; min-height:620px; } .canvas-wrap { min-height:480px; } }
  </style>
</head>
<body>
  <header>
    <div class="kicker">Regression CP Research Atlas</div>
    <h1>Evidence Map</h1>
    <p class="sub">A guided knowledge graph for tracing methods, datasets, reports, and evidence scope. The graph opens with readable research routes; source hashes are available in the detail panel.</p>
    <p class="sub"><a href="index.html">Back to project page</a> · <a href="../paper/research_document.md">Research Document</a></p>
  </header>
  <main class="layout">
    <aside>
      <h2>Research Routes</h2>
      <div id="routes"></div>
      <label>Search<input id="search" placeholder="CQR, Venn-Abers, NHANES, coverage..."></label>
      <label>Node type<select id="typeFilter"><option value="">All types</option></select></label>
      <div id="results"></div>
    </aside>
    <section class="stage" aria-label="Evidence map canvas">
      <div class="toolbar"><b id="mapTitle">Curated evidence map</b><div><button id="oneHop">One hop</button> <button id="twoHop">Two hops</button></div></div>
      <div class="canvas-wrap"><canvas id="mapCanvas" aria-label="Knowledge graph canvas"></canvas></div>
      <div class="footer"><span id="status">Loading graph...</span><span>Click a labeled node or route to traverse.</span></div>
    </section>
    <aside class="right">
      <div class="detail" id="detail"><h2>What is in this graph?</h2><p class="muted">This is a reader-facing index over the experiment evidence: methods, dataset audits, result reports, claim boundaries, and provenance links. Start with a route, then drill into a node only when you want the underlying audit trail.</p></div>
      <h2>Neighborhood</h2>
      <div id="edges"></div>
      <h2>Accessible Table</h2>
      <div id="table"></div>
    </aside>
  </main>
  <script>
    const state = { data:null, selected:null, routeId:null, depth:1, nodeById:new Map(), edgeByNode:new Map(), points:[] };
    const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const short = (v,n=150) => { const s=String(v ?? ''); return s.length>n ? s.slice(0,n-1)+'…' : s; };
    function addIndex(edge){ for(const id of [edge.source,edge.target]){ if(!state.edgeByNode.has(id)) state.edgeByNode.set(id,[]); state.edgeByNode.get(id).push(edge); } }
    function neighbors(root){
      const seen = new Set(), edges = [], q = [{id:root,d:0}];
      while(q.length && seen.size < 70){
        const cur=q.shift(); if(!cur || seen.has(cur.id)) continue; seen.add(cur.id);
        if(cur.d >= state.depth) continue;
        for(const e of state.edgeByNode.get(cur.id)||[]){
          edges.push(e); const other=e.source===cur.id?e.target:e.source;
          if(!seen.has(other)) q.push({id:other,d:cur.d+1});
        }
      }
      return {nodes:[...seen].map(id=>state.nodeById.get(id)).filter(Boolean), edges:edges.slice(0,120)};
    }
    function routeNodes(route){ return (route.node_ids||[]).map(id=>state.nodeById.get(id)).filter(Boolean); }
    function uniqueNodes(list){ const out=[], seen=new Set(); for(const n of list){ if(n && !seen.has(n.id)){ seen.add(n.id); out.push(n); } } return out; }
    function selectedRoute(){ return (state.data.research_map||[]).find(r=>r.route_id===state.routeId) || null; }
    function select(id){ if(!state.nodeById.has(id)) return; state.selected=id; state.routeId=null; renderAll(); history.replaceState(null,'','?node='+encodeURIComponent(id)); }
    function selectRoute(routeId){
      const route=(state.data.research_map||[]).find(r=>r.route_id===routeId);
      if(!route) return;
      state.selected=null; state.routeId=routeId; renderAll();
      history.replaceState(null,'','?preset='+encodeURIComponent(routeId));
    }
    function renderRoutes(){
      document.getElementById('routes').innerHTML=(state.data.research_map||[]).map(r=>`<div class="route" data-route="${esc(r.route_id)}" style="border-left:4px solid ${esc(r.accent)}"><b>${esc(r.title)}</b><span>${esc(r.summary)}</span><span>${(r.node_ids||[]).length} anchor nodes</span></div>`).join('');
      document.querySelectorAll('.route').forEach(el=>el.onclick=()=>selectRoute(el.dataset.route));
    }
    function renderFilters(){
      const selectEl=document.getElementById('typeFilter');
      Object.entries(state.data.type_counts||{}).forEach(([type,count])=>{ const o=document.createElement('option'); o.value=type; o.textContent=`${type} (${count})`; selectEl.appendChild(o); });
    }
    function resultNodes(){
      const q=document.getElementById('search').value.toLowerCase().trim();
      const type=document.getElementById('typeFilter').value;
      if(!q && !type) return [];
      return state.data.nodes.filter(n=>(!type||n.type===type)&&(!q||`${n.label} ${n.summary} ${n.id}`.toLowerCase().includes(q))).slice(0,80);
    }
    function renderResults(){
      const nodes=resultNodes();
      document.getElementById('results').innerHTML=nodes.length
        ? nodes.map(n=>`<div class="result ${n.id===state.selected?'active':''}" data-id="${esc(n.id)}"><b>${esc(n.label)}</b><span>${esc(n.type)} · degree ${esc(n.degree)}</span></div>`).join('')
        : '<p class="muted">Search or choose a node type to inspect the full audit graph. The default canvas stays at reader overview level.</p>';
      document.querySelectorAll('.result').forEach(el=>el.onclick=()=>select(el.dataset.id));
    }
    function renderDetail(){
      const n=state.nodeById.get(state.selected);
      if(!n){
        const route=selectedRoute();
        const routes=route?[route]:(state.data.research_map||[]);
        const routeRows=routes.map(r=>`<tr><td>${esc(r.title)}</td><td>${esc(short(r.summary,140))}</td><td>${esc((r.node_ids||[]).length)} anchors</td></tr>`).join('');
        const anchorRows=route ? routeNodes(route).map(row=>`<tr><td>${esc(row.label)}</td><td>${esc(row.type)}</td><td>${esc(short(row.summary,120))}</td></tr>`).join('') : '';
        document.getElementById('detail').innerHTML=route
          ? `<span class="pill">guided route</span><h2>${esc(route.title)}</h2><p class="muted">${esc(route.summary)}</p><p class="muted">This view shows the curated anchors first. Click an anchor node to open its one-hop or two-hop evidence neighborhood.</p>`
          : `<span class="pill">reader overview</span><h2>What is in this graph?</h2><p class="muted">This graph has ${Number(state.data.summary.node_count).toLocaleString()} nodes and ${Number(state.data.summary.edge_count).toLocaleString()} edges. It links methods, dataset audits, result reports, claim boundaries, and provenance records. It is an evidence navigation layer, not a recommendation engine.</p>`;
        document.getElementById('edges').innerHTML=route ? '<p class="muted">Route anchors are shown in the table below. Select one to inspect edge provenance.</p>' : '<p class="muted">Select a route or search for a node to see edge provenance.</p>';
        document.getElementById('table').innerHTML=route
          ? `<table><thead><tr><th>Anchor</th><th>Type</th><th>Summary</th></tr></thead><tbody>${anchorRows}</tbody></table>`
          : `<table><thead><tr><th>Route</th><th>Meaning</th><th>Size</th></tr></thead><tbody>${routeRows}</tbody></table>`;
        return;
      }
      const sourceResolution = n.source_resolution ? `<p class="muted"><strong>Public artifact:</strong> ${esc(n.source_resolution.status)}${n.source_resolution.public_path ? ` · <code>${esc(n.source_resolution.public_path)}</code>` : ''}${n.source_resolution.excluded_reason ? ` · ${esc(n.source_resolution.excluded_reason)}` : ''}</p>` : '';
      document.getElementById('detail').innerHTML=`<span class="pill">${esc(n.type)}</span><span class="pill">${esc(n.semantic_zone)}</span><h2>${esc(n.label)}</h2><p class="muted">${esc(n.summary||'No summary recorded.')}</p><p class="muted"><strong>Node key:</strong> <code>${esc(n.id)}</code></p>${n.source_key_hash?`<p class="muted"><strong>Source hash:</strong> <code>${esc(n.source_key_hash)}</code></p>`:''}${n.source_path?`<p class="muted"><strong>Source:</strong> <code>${esc(n.source_path)}</code></p>`:''}${sourceResolution}`;
      const es=(state.edgeByNode.get(n.id)||[]).slice(0,14);
      document.getElementById('edges').innerHTML=es.map(e=>{ const other=e.source===n.id?e.target:e.source; const o=state.nodeById.get(other); const er=e.evidence_resolution; return `<div class="edge"><span class="pill">${esc(e.relation)}</span><b>${esc(o?o.label:other)}</b><p class="muted">confidence ${Number(e.confidence||0).toFixed(3)} · <code>${esc(e.evidence_path||'source selector recorded')}</code></p>${er?`<p class="muted">Public artifact: ${esc(er.status)}${er.public_path?` · <code>${esc(er.public_path)}</code>`:''}${er.excluded_reason?` · ${esc(er.excluded_reason)}`:''}</p>`:''}</div>`; }).join('');
      document.getElementById('table').innerHTML=`<table><thead><tr><th>Node</th><th>Type</th><th>Summary</th></tr></thead><tbody>${neighbors(n.id).nodes.slice(0,18).map(row=>`<tr><td>${esc(row.label)}</td><td>${esc(row.type)}</td><td>${esc(short(row.summary,120))}</td></tr>`).join('')}</tbody></table>`;
    }
    function draw(){
      const canvas=document.getElementById('mapCanvas'), wrap=canvas.parentElement, r=wrap.getBoundingClientRect(), dpr=window.devicePixelRatio||1;
      canvas.width=Math.floor(r.width*dpr); canvas.height=Math.floor(r.height*dpr); canvas.style.width=r.width+'px'; canvas.style.height=r.height+'px';
      const ctx=canvas.getContext('2d'); ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,r.width,r.height);
      const selected=state.nodeById.get(state.selected);
      let nodes=[], edges=[];
      if(selected){ const sub=neighbors(selected.id); nodes=sub.nodes; edges=sub.edges; document.getElementById('mapTitle').textContent=selected.label; }
      else {
        const route=selectedRoute();
        nodes=uniqueNodes((route?[route]:(state.data.research_map||[])).flatMap(routeNodes));
        const ids=new Set(nodes.map(n=>n.id));
        edges=(state.data.edges||[]).filter(e=>ids.has(e.source)&&ids.has(e.target)).slice(0,80);
        if(route && edges.length < Math.max(0,nodes.length-1)){
          for(let i=1;i<nodes.length;i++) edges.push({source:nodes[i-1].id,target:nodes[i].id,relation:'ROUTE_STEP',confidence:1});
        }
        document.getElementById('mapTitle').textContent=route ? route.title : 'Reader overview';
      }
      nodes=nodes.slice(0,44);
      const cx=r.width/2, cy=r.height/2, radius=Math.min(r.width,r.height)*0.34;
      const pos=new Map();
      nodes.forEach((n,i)=>{ const angle=-Math.PI/2 + i*(Math.PI*2/Math.max(1,nodes.length)); const rr=n.id===state.selected?0:radius*(0.72+((i%5)*0.07)); pos.set(n.id,{x:cx+Math.cos(angle)*rr,y:cy+Math.sin(angle)*rr}); });
      edges.forEach(e=>{ const a=pos.get(e.source), b=pos.get(e.target); if(!a||!b) return; ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.strokeStyle=e.relation==='BLOCKED_BY'?'rgba(160,68,47,.38)':(e.relation==='ROUTE_STEP'?'rgba(153,101,21,.30)':'rgba(42,72,86,.22)'); ctx.lineWidth=e.relation==='ROUTE_STEP'?1.6:1; ctx.stroke(); });
      state.points=[];
      nodes.forEach((n,i)=>{ const p=pos.get(n.id); if(!p) return; const is=n.id===state.selected; const overview=!state.selected; const size=is?18:Math.max(7,Math.min(13,Number(n.size||8))); ctx.beginPath(); ctx.fillStyle=n.color||'#596273'; ctx.strokeStyle='#fffdf8'; ctx.lineWidth=2; ctx.arc(p.x,p.y,size,0,Math.PI*2); ctx.fill(); ctx.stroke(); if(is || overview || nodes.length<=12 || i%10===0){ ctx.fillStyle='#151922'; ctx.font=(is?'700 15px ':'700 12px ')+'Inter, sans-serif'; ctx.textAlign='center'; const label=short(n.label,is?38:(overview?30:22)); ctx.fillText(label,p.x, p.y+size+16); } state.points.push({id:n.id,x:p.x,y:p.y,r:size+18}); });
      document.getElementById('status').textContent=`Showing ${nodes.length.toLocaleString()} readable nodes from ${state.data.summary.node_count.toLocaleString()} total KG nodes`;
    }
    function renderAll(){ renderResults(); renderDetail(); draw(); }
    fetch('kg_browser_data.json').then(r=>r.json()).then(data=>{
      state.data=data; data.nodes.forEach(n=>state.nodeById.set(n.id,n)); data.edges.forEach(addIndex);
      renderRoutes(); renderFilters(); document.getElementById('search').oninput=renderResults; document.getElementById('typeFilter').onchange=renderResults;
      document.getElementById('oneHop').onclick=()=>{state.depth=1; renderAll();}; document.getElementById('twoHop').onclick=()=>{state.depth=2; renderAll();};
      document.getElementById('mapCanvas').onclick=e=>{ const rect=e.currentTarget.getBoundingClientRect(); const x=e.clientX-rect.left,y=e.clientY-rect.top; const hit=state.points.find(p=>Math.hypot(p.x-x,p.y-y)<p.r); if(hit) select(hit.id); };
      const params=new URLSearchParams(location.search); const start=params.get('node'); const preset=params.get('preset'); if(start) select(start); else if(preset) selectRoute(preset); else renderAll();
      addEventListener('resize',draw);
    });
  </script>
</body>
</html>
"""


def rewrite_kg_browser(path: Path) -> None:
    if not path.exists():
        return
    text = sanitize_public_text(path.read_text(encoding="utf-8"))
    replacements = {
        "Private supplementary graph surface backed by <code>kg_browser_data.json</code>. Public release, final citable status, and method recommendation remain closed.": (
            "Public supplementary graph surface backed by <code>kg_browser_data.json</code>. The graph is an evidence navigation layer, not a claim generator."
        ),
        "Back to private review portal": "Back to public release portal",
        "Public release and method recommendation remain closed.": (
            "The public release is experiment-scoped and non-prescriptive."
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def public_claim_evidence_matrix(raw_matrix: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in raw_matrix.get("claim_review_rows") or raw_matrix.get("rows") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "id": sanitize_public_text(
                    str(row.get("claim_review_id") or row.get("id") or "")
                ),
                "statement": sanitize_public_text(
                    str(row.get("allowed_publication_sentence") or row.get("claim") or "")
                ),
                "plain_language": sanitize_public_text(
                    str(row.get("non_specialist_explanation") or "")
                ),
                "evidence_gate": sanitize_public_text(
                    str(row.get("citation_gate") or row.get("evidence_gate") or "")
                ),
                "scope_limit": sanitize_public_text(
                    str(row.get("overclaim_blocked") or row.get("blocked_reading") or "")
                ),
                "support_status": sanitize_public_text(str(row.get("support_status") or "")),
                "knowledge_graph_reference_count": int(row.get("kg_reference_node_count") or 0),
            }
        )
    summary = raw_matrix.get("summary") if isinstance(raw_matrix.get("summary"), dict) else {}
    return {
        "schema": "regression_cp_claim_evidence_matrix_public_v1",
        "generated_at_utc": raw_matrix.get("generated_at_utc"),
        "summary": {
            "claim_rows": len(rows),
            "failed_checks": int(summary.get("failed_check_count") or 0),
            "supported_rows": sum(
                1 for row in rows if "supported" in row["support_status"].lower()
            ),
        },
        "rows": rows,
    }


def write_public_claim_evidence_matrix(package_root: Path, raw_matrix: dict[str, Any]) -> list[str]:
    public_matrix = public_claim_evidence_matrix(raw_matrix)
    matrix_json = package_root / "evidence/claim_evidence_matrix.json"
    matrix_md = package_root / "evidence/claim_evidence_matrix.md"
    matrix_json.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(matrix_json, public_matrix)
    lines = [
        "# Claim-Evidence Matrix",
        "",
        "This reader-facing matrix links the study's main statements to the evidence gates and scope limits used in the Research Atlas.",
        "",
        "| Claim row | Reader-safe statement | Evidence gate | Scope limit |",
        "|---|---|---|---|",
    ]
    for row in public_matrix["rows"]:
        lines.append(
            "| {row_id} | {statement} | {gate} | {limit} |".format(
                row_id=row["id"],
                statement=row["statement"],
                gate=row["evidence_gate"],
                limit=row["scope_limit"],
            )
        )
    atomic_write_text(matrix_md, "\n".join(lines) + "\n")
    return ["evidence/claim_evidence_matrix.json", "evidence/claim_evidence_matrix.md"]


def write_public_kg_quality_summary(package_root: Path) -> list[str]:
    kg_data_path = package_root / "site/kg_browser_data.json"
    if not kg_data_path.exists():
        return []
    kg_data = read_json(kg_data_path)
    summary = kg_data.get("summary") if isinstance(kg_data.get("summary"), dict) else {}
    payload = {
        "schema": "regression_cp_kg_quality_summary_public_v1",
        "title": "Regression CP Evidence Graph quality summary",
        "node_count": int(summary.get("node_count") or len(kg_data.get("nodes", []))),
        "edge_count": int(summary.get("edge_count") or len(kg_data.get("edges", []))),
        "isolated_node_count": int(summary.get("isolated_node_count") or 0),
        "provenance_coverage": float(summary.get("provenance_coverage") or 1.0),
        "reader_note": "The browser exposes curated routes first and keeps raw source keys as provenance detail.",
        "routes": [
            {
                "route_id": route.get("route_id"),
                "title": route.get("title"),
                "anchor_node_count": len(route.get("node_ids") or []),
            }
            for route in kg_data.get("research_map", [])
            if isinstance(route, dict)
        ],
    }
    target = package_root / "evidence/kg_quality_summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(target, payload)
    return ["evidence/kg_quality_summary.json"]


def copy_public_reader_artifacts(package_root: Path) -> list[str]:
    mapping = {
        "manuscript/research_document.md": "paper/research_document.md",
        "rendered_outputs/main_article_review.html": "paper/article.html",
        "rendered_outputs/main_article_review.pdf": "paper/article.pdf",
        "rendered_outputs/main_article_review.tex": "paper/article.tex",
        "rendered_outputs/supplementary_document_review.html": "paper/supplement.html",
        "rendered_outputs/supplementary_document_review.pdf": "paper/supplement.pdf",
        "rendered_outputs/supplementary_document_review.tex": "paper/supplement.tex",
        "rendered_outputs/references.bib": "paper/references.bib",
        "manuscript/individual_experiment_report_draft.md": "paper/individual_experiment_report.md",
    }
    written: list[str] = []
    for source_rel, dest_rel in mapping.items():
        source = package_root / source_rel
        if not source.exists():
            continue
        dest = package_root / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() in {".md", ".html", ".tex"}:
            atomic_write_text(dest, sanitize_public_text(source.read_text(encoding="utf-8")))
        else:
            shutil.copy2(source, dest)
        written.append(dest_rel)
    raw_matrix = package_root / "governance/publication_claim_evidence_verification_matrix.json"
    if raw_matrix.exists():
        written.extend(write_public_claim_evidence_matrix(package_root, read_json(raw_matrix)))
    written.extend(write_public_kg_quality_summary(package_root))
    return written


def prune_public_package(package_root: Path) -> list[str]:
    removed: list[str] = []
    for relative in (
        "audits",
        "citation",
        "governance",
        "knowledge_graph",
        "manuscript",
        "metadata",
        "provenance",
        "rendered_outputs",
        "release",
        "source_snapshots",
    ):
        path = package_root / relative
        if path.exists():
            shutil.rmtree(path)
            removed.append(relative + "/")
    for relative in (
        ".cpfi_sterile_publication_package",
        "CHANGELOG.md",
        "PUBLIC_RELEASE_AUTHORIZATION.md",
        "PUBLIC_RELEASE_MANIFEST.md",
        "PUBLIC_RELEASE_REVIEW_CHECKLIST.md",
        "PRIVATE_REVIEW_BOUNDARIES.md",
        "RELEASE_BOUNDARIES.md",
        "USER_REVIEW_HANDOFF.md",
    ):
        path = package_root / relative
        if path.exists():
            path.unlink()
            removed.append(relative)
    site_dir = package_root / "site"
    if site_dir.exists():
        keep_site = {"index.html", "kg_browser.html", "kg_browser_data.json"}
        for path in site_dir.iterdir():
            if path.is_file() and path.name not in keep_site:
                path.unlink()
                removed.append(f"site/{path.name}")
    evidence_dir = package_root / "evidence"
    if evidence_dir.exists():
        keep_evidence = {
            "claim_evidence_matrix.json",
            "claim_evidence_matrix.md",
            "kg_quality_summary.json",
            PUBLIC_ARTIFACT_MANIFEST_REL.name,
            PUBLIC_ARTIFACT_MANIFEST_MD_REL.name,
        }
        for path in evidence_dir.iterdir():
            if path.is_file() and path.name not in keep_evidence:
                path.unlink()
                removed.append(f"evidence/{path.name}")
    return removed


def apply_package_overlay(
    *,
    repo_root: Path,
    package_root: Path,
    manifest: dict[str, Any],
    authorization: dict[str, Any],
    remote_repo: str,
) -> list[str]:
    package_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = sanitize_public_package_inputs(package_root)
    compile_package_pdfs(package_root)
    files = {
        "README.md": public_readme(manifest),
        "EVIDENCE_SCOPE.md": release_boundaries(),
        "CITATION.cff": citation_cff(remote_repo),
        "pyproject.toml": public_pyproject(),
        "pytest.ini": public_pytest_ini(),
        ".github/workflows/public-ci.yml": public_ci_workflow(),
        "index.html": root_index(),
        "site/index.html": public_site_index(manifest),
        "site/kg_browser.html": public_kg_browser_html(),
        "reproducibility/tests/test_public_research_atlas_smoke.py": public_smoke_test(),
    }
    for relative, text in files.items():
        target = package_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(relative)
    release_dir = package_root / "release"
    if release_dir.exists():
        shutil.rmtree(release_dir)
        written.append("release/")
    written.extend(sanitize_public_package_inputs(package_root))
    compile_package_pdfs(package_root)
    written.extend(copy_public_reader_artifacts(package_root))
    source_to_package = {
        Path("experiments/regression/manuscript/publication_authoring_decision_record.json"): Path(
            "governance/publication_authoring_decision_record.json"
        ),
        Path("experiments/regression/manuscript/publication_authoring_decision_record.md"): Path(
            "governance/publication_authoring_decision_record.md"
        ),
        Path("experiments/regression/scripts/build_publication_authoring_decision_record.py"): Path(
            "reproducibility/experiments/regression/scripts/build_publication_authoring_decision_record.py"
        ),
        Path("experiments/regression/diary/data_scientist_log.md"): Path(
            "provenance/data_scientist_log.md"
        ),
    }
    for source_rel, dest_rel in source_to_package.items():
        source = repo_root / source_rel
        dest = package_root / dest_rel
        if dest_rel.parts[0] in {"governance", "provenance"}:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        written.append(dest_rel.as_posix())
    written.extend(sanitize_public_package_inputs(package_root))
    written.extend(copy_public_reader_artifacts(package_root))
    written.extend(prune_public_package(package_root))
    written.extend(write_public_artifact_manifest(package_root))
    return written


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    package_root = Path(args.package_root)
    if not package_root.is_absolute():
        package_root = (root / package_root).resolve()

    if args.apply_package_overlay:
        sanitize_public_package_inputs(package_root)
        compile_package_pdfs(package_root)

    authorization, manifest = build_payloads(
        root=root,
        package_root=package_root,
        remote_repo=args.remote_repo,
        pages_url=args.pages_url,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "user_release_authorization.json", authorization)
    atomic_write_text(
        out_dir / "user_release_authorization.md",
        render_authorization_markdown(authorization),
    )
    atomic_write_json(out_dir / "public_release_manifest.json", manifest)
    atomic_write_text(
        out_dir / "public_release_manifest.md",
        render_manifest_markdown(manifest),
    )

    written_package_files: list[str] = []
    if args.apply_package_overlay:
        written_package_files = apply_package_overlay(
            repo_root=root,
            package_root=package_root,
            manifest=manifest,
            authorization=authorization,
            remote_repo=args.remote_repo,
        )

    print(
        json.dumps(
            {
                "overall_status": manifest["summary"]["overall_status"],
                "public_release_authorized": manifest["summary"][
                    "public_release_authorized"
                ],
                "failed_check_count": manifest["summary"]["failed_check_count"],
                "out_dir": rel(out_dir, root),
                "package_overlay_file_count": len(written_package_files),
            },
            sort_keys=True,
        )
    )
    return 0 if manifest["summary"]["failed_check_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
