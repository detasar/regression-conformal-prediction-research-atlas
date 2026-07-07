"""Audit private LaTeX/HTML review outputs.

The audit verifies generated private review renders without turning them into
final manuscript prose or a public release.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_private_latex_html_review_output_audit_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/private_latex_html_review_output_audit.json"
)
RENDER_MANIFEST = Path(
    "experiments/regression/manuscript/private_latex_html_review_outputs_manifest.json"
)
REFERENCES_BIB = Path("experiments/regression/manuscript/review_latex_html_outputs/references.bib")

SECRET_PATTERNS = {
    "openai_api_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


class HTMLQualityParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.h1_count = 0
        self.table_count = 0
        self.link_hrefs: list[str] = []
        self.boundary_text_seen = False
        self._in_boundary = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value for key, value in attrs}
        if tag == "h1":
            self.h1_count += 1
        if tag == "table":
            self.table_count += 1
        if tag == "a" and attrs_dict.get("href"):
            self.link_hrefs.append(str(attrs_dict["href"]))
        if attrs_dict.get("class") == "boundary":
            self._in_boundary = True

    def handle_endtag(self, tag: str) -> None:
        if self._in_boundary and tag == "div":
            self._in_boundary = False

    def handle_data(self, data: str) -> None:
        if self._in_boundary and "Private review draft" in data:
            self.boundary_text_seen = True


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_secret_patterns(paths: list[Path], root: Path) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern_id, regex in SECRET_PATTERNS.items():
            if regex.search(text):
                hits.append({"path": rel(path, root), "pattern_id": pattern_id})
    return hits


def check_row(check_id: str, passed: bool, evidence: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "blocker": blocker,
    }


def html_quality(path: Path, root: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    parser = HTMLQualityParser()
    parser.feed(text)
    unresolved_tokens = [
        token for token in ("@@CPFI_TOKEN_", "[@", "\\cite{") if token in text
    ]
    broken_local_links: list[str] = []
    for href in parser.link_hrefs:
        if href.startswith(("http://", "https://", "mailto:")):
            continue
        target = (path.parent / href).resolve()
        if not target.exists():
            broken_local_links.append(href)
    return {
        "path": rel(path, root),
        "h1_count": parser.h1_count,
        "table_count": parser.table_count,
        "link_count": len(parser.link_hrefs),
        "broken_local_links": broken_local_links,
        "boundary_text_seen": parser.boundary_text_seen,
        "unresolved_tokens": unresolved_tokens,
        "status": (
            "pass"
            if parser.h1_count >= 1
            and not broken_local_links
            and not unresolved_tokens
            and (
                parser.boundary_text_seen
                or path.name == "index.html"
            )
            else "fail"
        ),
    }


def run_command(args: list[str], cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "args": args,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-1500:],
        "stderr_tail": result.stderr[-1500:],
    }


def compile_latex(path: Path, references: Path, root: Path) -> dict[str, Any]:
    compiler = shutil.which("pdflatex")
    bibtex = shutil.which("bibtex")
    if not compiler or not bibtex:
        return {
            "path": rel(path, root),
            "status": "fail",
            "compiler_available": bool(compiler),
            "bibtex_available": bool(bibtex),
            "commands": [],
            "undefined_reference_hits": [],
            "pdf_created": False,
        }
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tex_path = tmp_path / path.name
        bib_path = tmp_path / "references.bib"
        shutil.copy2(path, tex_path)
        shutil.copy2(references, bib_path)
        stem = path.stem
        commands = [
            run_command([compiler, "-interaction=nonstopmode", "-halt-on-error", tex_path.name], tmp_path),
            run_command([bibtex, stem], tmp_path),
            run_command([compiler, "-interaction=nonstopmode", "-halt-on-error", tex_path.name], tmp_path),
            run_command([compiler, "-interaction=nonstopmode", "-halt-on-error", tex_path.name], tmp_path),
        ]
        log_path = tmp_path / f"{stem}.log"
        log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
        undefined_hits = [
            line.strip()
            for line in log_text.splitlines()
            if "undefined" in line.lower() or "Citation" in line and "undefined" in line
        ]
        pdf_path = tmp_path / f"{stem}.pdf"
        return {
            "path": rel(path, root),
            "status": (
                "pass"
                if all(command["returncode"] == 0 for command in commands)
                and pdf_path.exists()
                and not undefined_hits
                else "fail"
            ),
            "compiler_available": True,
            "bibtex_available": True,
            "commands": commands,
            "undefined_reference_hits": undefined_hits[:20],
            "pdf_created": pdf_path.exists(),
            "pdf_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
        }


def output_file_rows(manifest: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in manifest.get("output_rows") or []:
        path = root / str(row.get("output_path") or "")
        exists = path.exists()
        actual_sha = sha256(path) if exists else None
        rows.append(
            {
                "output_id": row.get("output_id"),
                "format": row.get("format"),
                "path": rel(path, root),
                "exists": exists,
                "declared_sha256": row.get("sha256"),
                "actual_sha256": actual_sha,
                "sha256_matches": exists and row.get("sha256") == actual_sha,
                "public_release_authorized": row.get("public_release_authorized"),
                "final_manuscript_prose_permission": row.get(
                    "final_manuscript_prose_permission"
                ),
                "method_recommendation_authorized": row.get(
                    "method_recommendation_authorized"
                ),
                "positive_claim_promotion_authorized": row.get(
                    "positive_claim_promotion_authorized"
                ),
            }
        )
    return rows


def build_payload(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = read_json(root / RENDER_MANIFEST)
    manifest_summary = summary(manifest)
    file_rows = output_file_rows(manifest, root)
    output_paths = [root / row["path"] for row in file_rows if row["exists"]]
    html_rows = [
        html_quality(root / row["path"], root)
        for row in file_rows
        if row["format"] == "html" and row["exists"]
    ]
    latex_rows = [
        compile_latex(root / row["path"], root / REFERENCES_BIB, root)
        for row in file_rows
        if row["format"] == "latex" and row["exists"]
    ]
    secret_hits = scan_secret_patterns(output_paths, root)
    auth_violations = [
        row
        for row in file_rows
        if row.get("public_release_authorized") is not False
        or row.get("final_manuscript_prose_permission") is not False
        or row.get("method_recommendation_authorized") is not False
        or row.get("positive_claim_promotion_authorized") is not False
    ]
    format_counts = Counter(row.get("format") for row in file_rows)
    checks = [
        check_row(
            "render_manifest_ready",
            manifest_summary.get("overall_status")
            == "private_latex_html_review_outputs_ready"
            and manifest_summary.get("failed_check_count") == 0,
            {
                "manifest_status": manifest_summary.get("overall_status"),
                "failed_check_count": manifest_summary.get("failed_check_count"),
            },
            "private_latex_html_manifest_not_ready",
        ),
        check_row(
            "declared_outputs_exist_and_match_hash",
            all(row["exists"] and row["sha256_matches"] for row in file_rows),
            {"missing_or_mismatch_rows": [row for row in file_rows if not row["exists"] or not row["sha256_matches"]]},
            "private_render_output_missing_or_hash_mismatch",
        ),
        check_row(
            "expected_formats_present",
            format_counts.get("latex", 0) == 2
            and format_counts.get("html", 0) == 3
            and format_counts.get("bibtex", 0) == 1,
            {"format_counts": dict(format_counts)},
            "private_render_format_count_mismatch",
        ),
        check_row(
            "html_quality_checks_pass",
            all(row["status"] == "pass" for row in html_rows),
            {"html_rows": html_rows},
            "private_render_html_quality_failed",
        ),
        check_row(
            "latex_compile_checks_pass",
            all(row["status"] == "pass" for row in latex_rows),
            {"latex_rows": latex_rows},
            "private_render_latex_compile_failed",
        ),
        check_row(
            "no_high_confidence_secret_patterns",
            not secret_hits,
            {"secret_hits": secret_hits},
            "secret_pattern_detected_in_private_render",
        ),
        check_row(
            "authorization_boundaries_remain_closed",
            not auth_violations
            and manifest_summary.get("public_release_authorized") is False
            and manifest_summary.get("final_manuscript_prose_permission") is False
            and manifest_summary.get("method_recommendation_authorized") is False
            and manifest_summary.get("positive_claim_promotion_authorized") is False,
            {"authorization_violations": auth_violations},
            "private_render_authorization_boundary_opened",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    summary_payload = {
        "overall_status": (
            "private_latex_html_review_output_audit_pass"
            if not failed_checks
            else "private_latex_html_review_output_audit_fail"
        ),
        "render_manifest_status": manifest_summary.get("overall_status"),
        "output_count": len(file_rows),
        "latex_output_count": format_counts.get("latex", 0),
        "html_output_count": format_counts.get("html", 0),
        "bibtex_output_count": format_counts.get("bibtex", 0),
        "html_quality_pass_count": sum(row["status"] == "pass" for row in html_rows),
        "latex_compile_pass_count": sum(row["status"] == "pass" for row in latex_rows),
        "secret_pattern_hit_count": len(secret_hits),
        "authorization_violation_count": len(auth_violations),
        "public_release_authorized": False,
        "working_repository_final_citable": False,
        "final_manuscript_prose_permission": False,
        "method_recommendation_authorized": False,
        "method_champion_authorized": False,
        "method_advocacy_authorized": False,
        "positive_claim_promotion_authorized": False,
        "raw_data_or_secret_inclusion_authorized": False,
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "private_latex_html_review_outputs_manifest": rel(root / RENDER_MANIFEST, root),
            "references_bib": rel(root / REFERENCES_BIB, root),
        },
        "summary": summary_payload,
        "checks": checks,
        "failed_checks": failed_checks,
        "output_file_rows": file_rows,
        "html_quality_rows": html_rows,
        "latex_compile_rows": latex_rows,
        "secret_pattern_hits": secret_hits,
        "authorization_violations": auth_violations,
        "claim_boundaries": [
            "The audited outputs are private review artifacts only.",
            "Successful LaTeX compilation does not authorize final manuscript prose.",
            "Successful HTML checks do not authorize public deployment.",
            "Method recommendation, method advocacy, positive claim promotion, raw data, and secrets remain blocked.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# Private LaTeX/HTML Review Output Audit",
        "",
        "This audit checks private article/supplement review renders. It does not authorize final prose or public release.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{s['overall_status']}`",
        f"- Outputs: {s['output_count']} total; LaTeX / HTML / BibTeX = {s['latex_output_count']} / {s['html_output_count']} / {s['bibtex_output_count']}",
        f"- HTML quality pass count: {s['html_quality_pass_count']}",
        f"- LaTeX compile pass count: {s['latex_compile_pass_count']}",
        f"- Secret-pattern hits: {s['secret_pattern_hit_count']}",
        f"- Authorization violations: {s['authorization_violation_count']}",
        f"- Failed checks: {s['failed_check_count']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Blocker |",
        "|---|---|---|",
    ]
    for row in payload["checks"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['blocker']}` |")
    lines.extend(["", "## LaTeX Compile Rows", "", "| Path | Status | PDF bytes | Undefined refs |", "|---|---|---:|---:|"])
    for row in payload["latex_compile_rows"]:
        lines.append(
            f"| `{row['path']}` | `{row['status']}` | {row.get('pdf_bytes', 0)} | {len(row.get('undefined_reference_hits') or [])} |"
        )
    lines.extend(["", "## HTML Quality Rows", "", "| Path | Status | H1 | Tables | Broken local links |", "|---|---|---:|---:|---:|"])
    for row in payload["html_quality_rows"]:
        lines.append(
            f"| `{row['path']}` | `{row['status']}` | {row['h1_count']} | {row['table_count']} | {len(row['broken_local_links'])} |"
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
                "overall_status": payload["summary"]["overall_status"],
                "latex_compile_pass_count": payload["summary"][
                    "latex_compile_pass_count"
                ],
                "html_quality_pass_count": payload["summary"][
                    "html_quality_pass_count"
                ],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
