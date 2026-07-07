"""Build private LaTeX/HTML review outputs from evidence-linked drafts.

The outputs produced by this script are private final-prose review artifacts
inside the private sterile package. They are not final manuscript prose for
public submission, not a public release, and not a method recommendation.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_private_latex_html_review_outputs_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/private_latex_html_review_outputs_manifest.json"
)
DEFAULT_OUTPUT_DIR = Path("experiments/regression/manuscript/review_latex_html_outputs")

RELEASE_CUT = Path(
    "experiments/regression/manuscript/neutral_publication_release_cut_decision.json"
)
MAIN_ARTICLE = Path("experiments/regression/manuscript/main_article_draft.json")
MAIN_ARTICLE_MD = Path("experiments/regression/manuscript/main_article_draft.md")
SUPPLEMENT = Path("experiments/regression/manuscript/supplementary_document_draft.json")
SUPPLEMENT_MD = Path("experiments/regression/manuscript/supplementary_document_draft.md")
CITATION_REGISTRY = Path(
    "experiments/regression/manuscript/publication_citation_registry.json"
)
REFERENCES_BIB = Path("experiments/regression/manuscript/references.bib")

SOURCE_PATHS = {
    "neutral_publication_release_cut_decision": RELEASE_CUT,
    "main_article_draft": MAIN_ARTICLE,
    "main_article_markdown": MAIN_ARTICLE_MD,
    "supplementary_document_draft": SUPPLEMENT,
    "supplementary_document_markdown": SUPPLEMENT_MD,
    "publication_citation_registry": CITATION_REGISTRY,
    "references_bib": REFERENCES_BIB,
}

SECRET_PATTERNS = {
    "openai_api_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}

LATEX_ESCAPE = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Manifest JSON path.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for generated LaTeX/HTML review outputs.",
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def citation_map(registry: dict[str, Any]) -> dict[str, str]:
    rows = registry.get("citation_rows") or registry.get("rows") or []
    out: dict[str, str] = {}
    for row in rows:
        key = str(row.get("citation_key") or "").strip()
        url = str(row.get("url") or "").strip()
        if key and url:
            out[key] = url
    return out


def extract_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def extract_author(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("Author:"):
            return line.replace("Author:", "", 1).strip()
    return "Emre Tasar, Data Scientist"


def protect(
    pattern: re.Pattern[str],
    text: str,
    renderer,
    token_namespace: str,
) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        key = f"@@CPFI_{token_namespace}_{len(placeholders)}@@"
        placeholders[key] = renderer(match)
        return key

    return pattern.sub(repl, text), placeholders


def escape_latex_text(text: str) -> str:
    return "".join(LATEX_ESCAPE.get(char, char) for char in text)


def citation_keys(raw: str) -> list[str]:
    return [
        part.strip().lstrip("@")
        for part in raw.split(";")
        if part.strip().lstrip("@")
    ]


def latex_inline(text: str) -> str:
    protected, tokens = protect(
        re.compile(r"`([^`]+)`"),
        text,
        lambda match: r"\texttt{" + escape_latex_text(match.group(1)) + "}",
        "LATEX_CODE",
    )
    protected, cite_tokens = protect(
        re.compile(r"\[@([^\]]+)\]"),
        protected,
        lambda match: r"\cite{" + ",".join(citation_keys(match.group(1))) + "}",
        "LATEX_CITE",
    )
    tokens.update(cite_tokens)
    escaped = escape_latex_text(protected)
    for key, value in tokens.items():
        escaped = escaped.replace(escape_latex_text(key), value)
    return escaped


def html_inline(text: str, citations: dict[str, str]) -> str:
    protected, tokens = protect(
        re.compile(r"`([^`]+)`"),
        text,
        lambda match: "<code>" + html.escape(match.group(1)) + "</code>",
        "HTML_CODE",
    )

    def render_citation(match: re.Match[str]) -> str:
        links = []
        for key in citation_keys(match.group(1)):
            url = citations.get(key)
            if url:
                links.append(
                    '<a href="{}">@{}</a>'.format(html.escape(url), html.escape(key))
                )
            else:
                links.append("@" + html.escape(key))
        return "[" + "; ".join(links) + "]"

    protected, cite_tokens = protect(
        re.compile(r"\[@([^\]]+)\]"),
        protected,
        render_citation,
        "HTML_CITE",
    )
    tokens.update(cite_tokens)
    escaped = html.escape(protected)
    url_re = re.compile(r"(https?://[^\s<]+)")
    escaped = url_re.sub(
        lambda match: '<a href="{}">{}</a>'.format(
            html.escape(match.group(1)), html.escape(match.group(1))
        ),
        escaped,
    )
    for key, value in tokens.items():
        escaped = escaped.replace(html.escape(key), value)
    return escaped


def is_table_start(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and lines[index].lstrip().startswith("|")
        and lines[index + 1].lstrip().startswith("|")
        and set(lines[index + 1].replace("|", "").replace(":", "").replace("-", "").strip())
        == set()
    )


def parse_table(lines: list[str], index: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    cursor = index
    while cursor < len(lines) and lines[cursor].lstrip().startswith("|"):
        if cursor == index + 1:
            cursor += 1
            continue
        cells = [cell.strip() for cell in lines[cursor].strip().strip("|").split("|")]
        rows.append(cells)
        cursor += 1
    return rows, cursor


def latex_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    col_spec = "l" * width
    output = [r"\begin{longtable}{" + col_spec + "}", r"\toprule"]
    header = rows[0] + [""] * (width - len(rows[0]))
    output.append(" & ".join(latex_inline(cell) for cell in header) + r" \\")
    output.append(r"\midrule")
    for row in rows[1:]:
        cells = row + [""] * (width - len(row))
        output.append(" & ".join(latex_inline(cell) for cell in cells) + r" \\")
    output.extend([r"\bottomrule", r"\end{longtable}"])
    return "\n".join(output)


def html_table(rows: list[list[str]], citations: dict[str, str]) -> str:
    if not rows:
        return ""
    header = "".join(f"<th>{html_inline(cell, citations)}</th>" for cell in rows[0])
    body_rows = []
    for row in rows[1:]:
        body_rows.append(
            "<tr>"
            + "".join(f"<td>{html_inline(cell, citations)}</td>" for cell in row)
            + "</tr>"
        )
    return (
        "<table>\n<thead><tr>"
        + header
        + "</tr></thead>\n<tbody>\n"
        + "\n".join(body_rows)
        + "\n</tbody>\n</table>"
    )


def markdown_to_latex_body(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    index = 0
    first_title_skipped = False
    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            index += 1
            continue
        if line.startswith("Author:"):
            index += 1
            continue
        if is_table_start(lines, index):
            rows, index = parse_table(lines, index)
            out.append(latex_table(rows))
            continue
        if line.startswith("# "):
            if first_title_skipped:
                out.append(r"\section{" + latex_inline(line[2:].strip()) + "}")
            first_title_skipped = True
            index += 1
            continue
        if line.startswith("## "):
            out.append(r"\section{" + latex_inline(line[3:].strip()) + "}")
            index += 1
            continue
        if line.startswith("### "):
            out.append(r"\subsection{" + latex_inline(line[4:].strip()) + "}")
            index += 1
            continue
        if line.startswith("> "):
            out.append(r"\begin{quote}" + latex_inline(line[2:].strip()) + r"\end{quote}")
            index += 1
            continue
        if line.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].startswith("- "):
                items.append(latex_inline(lines[index][2:].strip()))
                index += 1
            out.append("\\begin{itemize}\n" + "\n".join(f"\\item {item}" for item in items) + "\n\\end{itemize}")
            continue
        out.append(latex_inline(line) + "\n")
        index += 1
    return "\n\n".join(out)


def markdown_to_html_body(markdown: str, citations: dict[str, str]) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            index += 1
            continue
        if line.startswith("Author:"):
            out.append("<p><strong>Author:</strong> " + html_inline(line.replace("Author:", "", 1).strip(), citations) + "</p>")
            index += 1
            continue
        if is_table_start(lines, index):
            rows, index = parse_table(lines, index)
            out.append(html_table(rows, citations))
            continue
        if line.startswith("# "):
            out.append("<h1>" + html_inline(line[2:].strip(), citations) + "</h1>")
            index += 1
            continue
        if line.startswith("## "):
            out.append("<h2>" + html_inline(line[3:].strip(), citations) + "</h2>")
            index += 1
            continue
        if line.startswith("### "):
            out.append("<h3>" + html_inline(line[4:].strip(), citations) + "</h3>")
            index += 1
            continue
        if line.startswith("> "):
            out.append("<blockquote>" + html_inline(line[2:].strip(), citations) + "</blockquote>")
            index += 1
            continue
        if line.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].startswith("- "):
                items.append("<li>" + html_inline(lines[index][2:].strip(), citations) + "</li>")
                index += 1
            out.append("<ul>\n" + "\n".join(items) + "\n</ul>")
            continue
        out.append("<p>" + html_inline(line, citations) + "</p>")
        index += 1
    return "\n".join(out)


def render_latex_document(markdown: str, title: str, author: str) -> str:
    body = markdown_to_latex_body(markdown)
    return "\n".join(
        [
            r"\documentclass[11pt]{article}",
            r"\usepackage[margin=1in]{geometry}",
            r"\usepackage{booktabs}",
            r"\usepackage{longtable}",
            r"\usepackage{hyperref}",
            r"\usepackage[T1]{fontenc}",
            r"\usepackage{lmodern}",
            r"\title{" + latex_inline(title) + "}",
            r"\author{" + latex_inline(author) + "}",
            r"\date{Private final-prose review draft; not final manuscript prose for public submission}",
            r"\begin{document}",
            r"\maketitle",
            r"\noindent\textbf{Review boundary:} This output is generated for private review only. It does not authorize public release, method recommendation, or positive claim promotion.",
            "",
            body,
            "",
            r"\bibliographystyle{plain}",
            r"\bibliography{references}",
            "",
            r"\end{document}",
            "",
        ]
    )


def render_html_document(markdown: str, title: str, citations: dict[str, str]) -> str:
    body = markdown_to_html_body(markdown, citations)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 980px; margin: 40px auto; padding: 0 24px; line-height: 1.55; color: #18181b; }}
    table {{ border-collapse: collapse; width: 100%; margin: 18px 0; font-size: 0.95rem; }}
    th, td {{ border: 1px solid #d4d4d8; padding: 8px; vertical-align: top; }}
    th {{ background: #f4f4f5; text-align: left; }}
    code {{ background: #f4f4f5; padding: 2px 4px; border-radius: 4px; }}
    blockquote {{ border-left: 4px solid #2563eb; padding-left: 16px; color: #3f3f46; }}
    .boundary {{ border: 1px solid #d4d4d8; padding: 12px 14px; background: #fafafa; }}
  </style>
</head>
<body>
  <div class="boundary"><strong>Private review draft.</strong> Private final-prose review draft; not final manuscript prose for public submission, not a public release, and not a method recommendation.</div>
{body}
</body>
</html>
"""


def render_index(output_rows: list[dict[str, Any]]) -> str:
    links = "\n".join(
        '<li><a href="{}">{}</a> ({})</li>'.format(
            html.escape(Path(row["output_path"]).name),
            html.escape(row["output_id"]),
            html.escape(row["format"]),
        )
        for row in output_rows
        if row["format"] in {"html", "latex"}
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Private LaTeX/HTML Review Outputs</title>
</head>
<body>
  <h1>Private LaTeX/HTML Review Outputs</h1>
  <p>These files are generated for private review only. Public release and final manuscript claims remain blocked.</p>
  <ul>
{links}
  </ul>
</body>
</html>
"""


def scan_secret_patterns(paths: list[Path]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern_id, regex in SECRET_PATTERNS.items():
            if regex.search(text):
                hits.append({"path": path.as_posix(), "pattern_id": pattern_id})
    return hits


def release_cut_allows_private_render(summary_payload: dict[str, Any]) -> bool:
    return (
        summary_payload.get("overall_status") == "neutral_publication_release_cut_ready"
        and summary_payload.get("neutral_latex_html_static_site_package_authorized")
        is True
        and summary_payload.get("public_release_authorized") is False
        and summary_payload.get("working_repository_final_citable") is False
        and summary_payload.get("method_recommendation_authorized") is False
        and summary_payload.get("positive_claim_promotion_authorized") is False
        and summary_payload.get("raw_data_or_secret_inclusion_authorized") is False
    )


def check_row(check_id: str, passed: bool, evidence: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "blocker": blocker,
    }


def output_row(output_id: str, source_id: str, fmt: str, path: Path, root: Path) -> dict[str, Any]:
    return {
        "output_id": output_id,
        "source_id": source_id,
        "format": fmt,
        "output_path": rel(path, root),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "public_release_authorized": False,
        "final_manuscript_prose_permission": False,
        "method_recommendation_authorized": False,
        "positive_claim_promotion_authorized": False,
    }


def build_payload(root: Path, output_dir: Path) -> dict[str, Any]:
    root = root.resolve()
    output_dir = (root / output_dir).resolve() if not output_dir.is_absolute() else output_dir.resolve()
    release_cut = read_json(root / RELEASE_CUT)
    main_article = read_json(root / MAIN_ARTICLE)
    supplement = read_json(root / SUPPLEMENT)
    citation_registry = read_json(root / CITATION_REGISTRY)
    release_summary = summary(release_cut)
    main_summary = summary(main_article)
    supplement_summary = summary(supplement)
    citation_summary = summary(citation_registry)
    present_sources, missing_sources = source_status(root)

    preflight_checks = [
        check_row(
            "release_cut_authorizes_private_latex_html_only",
            release_cut_allows_private_render(release_summary),
            {
                "release_cut_status": release_summary.get("overall_status"),
                "private_render_authorized": release_summary.get(
                    "neutral_latex_html_static_site_package_authorized"
                ),
                "public_release_authorized": release_summary.get(
                    "public_release_authorized"
                ),
            },
            "private_latex_html_render_not_authorized",
        ),
        check_row(
            "draft_sources_ready",
            main_summary.get("overall_status") == "main_article_draft_ready"
            and supplement_summary.get("overall_status")
            == "supplementary_document_draft_ready"
            and int(main_summary.get("failed_check_count") or 0) == 0
            and int(supplement_summary.get("failed_check_count") or 0) == 0,
            {
                "main_article_status": main_summary.get("overall_status"),
                "supplement_status": supplement_summary.get("overall_status"),
            },
            "draft_source_not_ready",
        ),
        check_row(
            "citation_registry_ready",
            citation_summary.get("overall_status")
            == "publication_citation_registry_ready_no_final_prose"
            and int(citation_summary.get("failed_check_count") or 0) == 0,
            {"citation_registry_status": citation_summary.get("overall_status")},
            "citation_registry_not_ready",
        ),
        check_row(
            "source_artifacts_present",
            not missing_sources,
            {"missing_sources": missing_sources},
            "private_latex_html_source_missing",
        ),
    ]
    if any(row["status"] != "pass" for row in preflight_checks):
        failed_checks = [row for row in preflight_checks if row["status"] != "pass"]
        return {
            "schema": SCHEMA,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "sources": {name: rel(root / path, root) for name, path in SOURCE_PATHS.items()},
            "summary": {
                "overall_status": "private_latex_html_review_outputs_blocked",
                "output_dir": rel(output_dir, root),
                "output_count": 0,
                "latex_output_count": 0,
                "html_output_count": 0,
                "bibtex_output_count": 0,
                "failed_check_count": len(failed_checks),
                "check_count": len(preflight_checks),
                "public_release_authorized": False,
                "working_repository_final_citable": False,
                "final_manuscript_prose_permission": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "positive_claim_promotion_authorized": False,
                "raw_data_or_secret_inclusion_authorized": False,
                "private_latex_html_static_site_package_authorized": False,
                "secret_pattern_hit_count": 0,
            },
            "checks": preflight_checks,
            "failed_checks": failed_checks,
            "output_rows": [],
            "secret_pattern_hits": [],
            "claim_boundaries": [
                "Generated outputs are private review artifacts only.",
                "Final manuscript prose and public release remain unauthorized.",
                "Method recommendation, method advocacy, and positive claim promotion remain unauthorized.",
                "Raw data, secrets, and nonredistributable source files remain excluded.",
            ],
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    citations = citation_map(citation_registry)
    main_markdown = (root / MAIN_ARTICLE_MD).read_text(encoding="utf-8")
    supplement_markdown = (root / SUPPLEMENT_MD).read_text(encoding="utf-8")
    docs = [
        (
            "main_article",
            "main_article_draft",
            main_markdown,
            extract_title(main_markdown, "Regression Conformal Prediction Study"),
        ),
        (
            "supplementary_document",
            "supplementary_document_draft",
            supplement_markdown,
            extract_title(supplement_markdown, "Supplementary Document Draft"),
        ),
    ]
    output_rows: list[dict[str, Any]] = []
    generated_paths: list[Path] = []
    for prefix, source_id, markdown, title in docs:
        author = extract_author(markdown)
        tex_path = output_dir / f"{prefix}_review.tex"
        html_path = output_dir / f"{prefix}_review.html"
        atomic_write_text(tex_path, render_latex_document(markdown, title, author))
        atomic_write_text(html_path, render_html_document(markdown, title, citations))
        generated_paths.extend([tex_path, html_path])
        output_rows.append(output_row(f"{prefix}_latex", source_id, "latex", tex_path, root))
        output_rows.append(output_row(f"{prefix}_html", source_id, "html", html_path, root))

    references_out = output_dir / "references.bib"
    atomic_write_text(references_out, (root / REFERENCES_BIB).read_text(encoding="utf-8"))
    generated_paths.append(references_out)
    output_rows.append(output_row("references_bib", "publication_citation_registry", "bibtex", references_out, root))
    index_path = output_dir / "index.html"
    atomic_write_text(index_path, render_index(output_rows))
    generated_paths.append(index_path)
    output_rows.append(output_row("private_review_index", "private_latex_html_review_outputs", "html", index_path, root))

    secret_hits = scan_secret_patterns(generated_paths)
    output_formats = Counter(row["format"] for row in output_rows)
    checks = [
        *preflight_checks,
        check_row(
            "expected_outputs_generated",
            {"latex": 2, "html": 3, "bibtex": 1}.items() <= output_formats.items(),
            {"output_formats": dict(output_formats)},
            "expected_private_latex_html_output_missing",
        ),
        check_row(
            "no_high_confidence_secret_patterns",
            not secret_hits,
            {"secret_hits": secret_hits},
            "secret_pattern_detected_in_private_latex_html_output",
        ),
        check_row(
            "claim_boundaries_remain_closed",
            release_summary.get("public_release_authorized") is False
            and release_summary.get("method_recommendation_authorized") is False
            and release_summary.get("positive_claim_promotion_authorized") is False,
            {
                "public_release_authorized": release_summary.get(
                    "public_release_authorized"
                ),
                "method_recommendation_authorized": release_summary.get(
                    "method_recommendation_authorized"
                ),
                "positive_claim_promotion_authorized": release_summary.get(
                    "positive_claim_promotion_authorized"
                ),
            },
            "private_latex_html_claim_boundary_opened",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    summary_payload = {
        "overall_status": (
            "private_latex_html_review_outputs_ready"
            if not failed_checks
            else "private_latex_html_review_outputs_blocked"
        ),
        "output_dir": rel(output_dir, root),
        "output_count": len(output_rows),
        "latex_output_count": output_formats.get("latex", 0),
        "html_output_count": output_formats.get("html", 0),
        "bibtex_output_count": output_formats.get("bibtex", 0),
        "release_cut_status": release_summary.get("overall_status"),
        "main_article_status": main_summary.get("overall_status"),
        "supplement_status": supplement_summary.get("overall_status"),
        "citation_registry_status": citation_summary.get("overall_status"),
        "public_release_authorized": False,
        "working_repository_final_citable": False,
        "final_manuscript_prose_permission": False,
        "method_recommendation_authorized": False,
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "positive_claim_promotion_authorized": False,
        "raw_data_or_secret_inclusion_authorized": False,
        "private_latex_html_static_site_package_authorized": not failed_checks,
        "secret_pattern_hit_count": len(secret_hits),
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
        "checks": checks,
        "failed_checks": failed_checks,
        "output_rows": output_rows,
        "secret_pattern_hits": secret_hits,
        "claim_boundaries": [
            "Generated outputs are private review artifacts only.",
            "Final manuscript prose and public release remain unauthorized.",
            "Method recommendation, method advocacy, and positive claim promotion remain unauthorized.",
            "Raw data, secrets, and nonredistributable source files remain excluded.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# Private LaTeX/HTML Review Output Manifest",
        "",
        "This manifest records private review renders of the current evidence-linked article and supplement drafts.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{s['overall_status']}`",
        f"- Output directory: `{s['output_dir']}`",
        f"- Output count: {s['output_count']}",
        f"- LaTeX / HTML / BibTeX outputs: {s['latex_output_count']} / {s['html_output_count']} / {s['bibtex_output_count']}",
        f"- Public release authorized: `{s['public_release_authorized']}`",
        f"- Final manuscript prose permission: `{s['final_manuscript_prose_permission']}`",
        f"- Method recommendation authorized: `{s['method_recommendation_authorized']}`",
        f"- Positive claim promotion authorized: `{s['positive_claim_promotion_authorized']}`",
        f"- Secret-pattern hits: {s['secret_pattern_hit_count']}",
        f"- Failed checks: {s['failed_check_count']}",
        "",
        "## Outputs",
        "",
        "| Output | Format | Path | Bytes |",
        "|---|---|---|---:|",
    ]
    for row in payload["output_rows"]:
        lines.append(
            f"| `{row['output_id']}` | `{row['format']}` | `{row['output_path']}` | {row['bytes']} |"
        )
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
    payload = build_payload(root, Path(args.output_dir))
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "overall_status": payload["summary"]["overall_status"],
                "output_count": payload["summary"]["output_count"],
                "latex_output_count": payload["summary"]["latex_output_count"],
                "html_output_count": payload["summary"]["html_output_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
