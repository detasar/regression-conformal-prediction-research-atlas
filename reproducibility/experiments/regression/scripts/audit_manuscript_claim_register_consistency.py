"""Audit consistency between manuscript claim-register JSON and Markdown.

The JSON file is the machine-readable source for gates and KG extraction; the
Markdown file is the human-facing paper-control surface. This audit prevents a
claim from being promoted in one representation while remaining pending in the
other.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_manuscript_claim_register_consistency_v1"
DEFAULT_REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = DEFAULT_REPORT_DIR / "manuscript_claim_register_consistency_audit.json"
CLAIM_REGISTER_JSON = Path("experiments/regression/catalogs/manuscript_claim_register.json")
CLAIM_REGISTER_MD = Path("experiments/regression/catalogs/manuscript_claim_register.md")

CLAIM_HEADER_RE = re.compile(r"^## Claim: (?P<claim_id>\S+)\s*$", re.MULTILINE)
STATUS_RE = re.compile(r"^Status:\s*`(?P<status>[^`]+)`\s*$", re.MULTILINE)
REQUIREMENT_RE = re.compile(
    r"^-\s*`(?P<requirement_id>[^`]+)`:\s*(?P<status>.+?)\s*$",
    re.MULTILINE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def parse_md_claims(text: str) -> dict[str, dict[str, Any]]:
    claims: dict[str, dict[str, Any]] = {}
    matches = list(CLAIM_HEADER_RE.finditer(text))
    for index, match in enumerate(matches):
        claim_id = match.group("claim_id")
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end]
        status_match = STATUS_RE.search(section)
        requirements = {
            req.group("requirement_id"): normalize_status(req.group("status"))
            for req in REQUIREMENT_RE.finditer(section)
        }
        claims[claim_id] = {
            "status": status_match.group("status") if status_match else None,
            "requirements": requirements,
        }
    return claims


def normalize_status(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().strip(".").split())
    text = text.split(";")[0].strip().rstrip(".:")
    folded = text.lower()
    if "_" in folded and " " not in folded:
        return folded
    replacements = {
        "present with caveats": "present_with_caveats",
        "blocked until each dataset bundle passes": "blocked_until_each_dataset_bundle_passes",
        "present with scope limits": "present_with_scope_limits",
        "pass with scope limits": "pass_with_scope_limits",
        "present with endpoint caveats": "present_with_endpoint_caveats",
        "pass with endpoint caveats": "pass_with_endpoint_caveats",
        "pass with caveats": "pass_with_caveats",
        "recorded with no method/model selected": "recorded_no_selection",
        "recorded with no final method/model selected": "recorded_no_selection",
        "recorded with no method/model": "recorded_no_selection",
        "recorded with no final method/model": "recorded_no_selection",
    }
    for prefix, normalized in replacements.items():
        if folded.startswith(prefix):
            return normalized
    if folded.startswith("complete"):
        return "complete"
    if folded.startswith("present"):
        return "present"
    if folded.startswith("pass"):
        return "pass"
    if folded.startswith("recorded"):
        return "recorded"
    if folded.startswith("blocked"):
        return "blocked"
    return text


def json_claim_summary(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": claim.get("status"),
        "requirements": {
            str(req.get("requirement_id")): normalize_status(req.get("status"))
            for req in claim.get("requirements", []) or []
            if isinstance(req, dict) and req.get("requirement_id")
        },
    }


def compare_claims(json_claims: list[dict[str, Any]], md_claims: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for claim in json_claims:
        claim_id = str(claim.get("claim_id") or "")
        json_summary = json_claim_summary(claim)
        md_summary = md_claims.get(claim_id)
        issues: list[dict[str, Any]] = []
        if not md_summary:
            issues.append({"kind": "missing_markdown_claim"})
            rows.append(
                {
                    "claim_id": claim_id,
                    "status": "fail",
                    "json_status": json_summary["status"],
                    "markdown_status": None,
                    "requirement_mismatches": [],
                    "issues": issues,
                }
            )
            continue
        if json_summary["status"] != md_summary["status"]:
            issues.append(
                {
                    "kind": "claim_status_mismatch",
                    "json": json_summary["status"],
                    "markdown": md_summary["status"],
                }
            )
        requirement_mismatches = []
        for req_id, json_status in json_summary["requirements"].items():
            md_status = md_summary["requirements"].get(req_id)
            if md_status != json_status:
                requirement_mismatches.append(
                    {
                        "requirement_id": req_id,
                        "json": json_status,
                        "markdown": md_status,
                    }
                )
        if requirement_mismatches:
            issues.append({"kind": "requirement_status_mismatch"})
        rows.append(
            {
                "claim_id": claim_id,
                "status": "fail" if issues else "pass",
                "json_status": json_summary["status"],
                "markdown_status": md_summary["status"],
                "requirement_mismatches": requirement_mismatches,
                "issues": issues,
            }
        )
    json_claim_ids = {str(claim.get("claim_id") or "") for claim in json_claims}
    for claim_id in sorted(set(md_claims) - json_claim_ids):
        rows.append(
            {
                "claim_id": claim_id,
                "status": "fail",
                "json_status": None,
                "markdown_status": md_claims[claim_id]["status"],
                "requirement_mismatches": [],
                "issues": [{"kind": "missing_json_claim"}],
            }
        )
    return rows


def build_payload(root: Path) -> dict[str, Any]:
    json_path = root / CLAIM_REGISTER_JSON
    md_path = root / CLAIM_REGISTER_MD
    claim_register = json.loads(json_path.read_text(encoding="utf-8"))
    md_claims = parse_md_claims(md_path.read_text(encoding="utf-8"))
    json_claims = [
        claim
        for claim in claim_register.get("claims", []) or []
        if isinstance(claim, dict) and claim.get("claim_id")
    ]
    rows = compare_claims(json_claims, md_claims)
    status_counts = Counter(row["status"] for row in rows)
    failed_rows = [row for row in rows if row["status"] != "pass"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim_register_json": rel(json_path, root),
        "claim_register_markdown": rel(md_path, root),
        "summary": {
            "overall_status": "fail" if failed_rows else "pass",
            "claim_count": len(rows),
            "status_counts": dict(sorted(status_counts.items())),
            "failed_claim_count": len(failed_rows),
        },
        "rows": rows,
        "claim_boundaries": [
            "This audit checks JSON/Markdown claim-register synchronization, not empirical correctness.",
            "A passing result means claim statuses and requirement statuses match across both claim-register views.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Manuscript Claim Register Consistency Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Claim count: {summary['claim_count']}",
        f"- Status counts: `{summary['status_counts']}`",
        f"- Failed claims: {summary['failed_claim_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Claim Rows",
            "",
            "| Claim | Status | JSON status | Markdown status | Requirement mismatches |",
            "| --- | --- | --- | --- | ---: |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row['claim_id']}` | "
            f"`{row['status']}` | "
            f"`{row['json_status']}` | "
            f"`{row['markdown_status']}` | "
            f"{len(row['requirement_mismatches'])} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(json.dumps({"out": rel(out_path, root), **payload["summary"]}, sort_keys=True))
    return 1 if payload["summary"]["overall_status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
