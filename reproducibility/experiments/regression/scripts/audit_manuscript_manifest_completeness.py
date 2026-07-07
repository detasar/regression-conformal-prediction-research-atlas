"""Audit manuscript-facing regression evidence manifests.

This audit is intentionally lightweight: the manifests are Markdown control
documents, not machine-only JSON. The goal is to make missing paper-readiness
concepts visible before claims are promoted into manuscript tables.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_manuscript_manifest_completeness_audit_v1"
SCHEMA_TOKEN = "cpfi_regression_manuscript_evidence_manifest_v1"
DEFAULT_REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = DEFAULT_REPORT_DIR / "manuscript_manifest_completeness_audit.json"
MANIFEST_GLOB = "experiments/regression/reports/*/publication_readiness_manifest.md"
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")

REQUIRED_SECTIONS = (
    "## Identity",
    "## Scientific Question",
    "## Design",
    "## Data Evidence",
    "## Model Evidence",
    "## Conformal Evidence",
    "## Selection And Multiplicity Status",
    "## Split, Leakage, And Duplicate Controls",
    "## Metric Contract",
    "## Promotion Gates",
)

REQUIRED_TOKENS = (
    "Status:",
    "Out of scope:",
    "CQR boundary",
    "Venn-Abers boundary",
    "feature-leakage audit",
    "endpoint audit",
    "claim-register",
    "Predeclared operating criterion",
    "Ranking scope",
    "Multiplicity scope",
    "Tie-break rule",
    "Post-selection claim boundary",
    "No method",
)

CANONICAL_SELECTION_MULTIPLICITY_SECTION_ID = "selection_multiplicity_evidence"
SELECTION_MULTIPLICITY_SECTION = "## Selection And Multiplicity Status"
SELECTION_MULTIPLICITY_FIELD_TOKENS = {
    "predeclared_operating_criterion": ("Predeclared operating criterion",),
    "ranking_scope": ("Ranking scope",),
    "multiplicity_scope": ("Multiplicity scope",),
    "tie_break_rule": ("Tie-break rule",),
    "nominal_coverage_requirement": (
        "nominal 0.90",
        "nominal coverage",
        "coverage target",
    ),
    "post_selection_claim_boundary": ("Post-selection claim boundary",),
    "exploratory_ranking_label": (
        "Exploratory ranking label",
        "remains exploratory",
        "exploratory sidecar",
    ),
    "sensitivity_or_holdout_validation": ("Sensitivity or holdout validation",),
}

NEGATIVE_EVIDENCE_GROUPS = {
    "diagnostic_negative_evidence": (
        "diagnostic negative evidence",
        "negative diagnostic evidence",
    ),
    "undercoverage_language": (
        "undercover",
    ),
    "no_venn_abers_validation_claim": (
        "not Venn-Abers regression validation evidence",
        "not validated Venn-Abers regression",
        "not a validated Venn-Abers bridge",
        "not evidence that the Venn-Abers regression bridge is validated",
    ),
}

SEVERITY_ORDER = {"pass": 0, "caveat": 1, "fail": 2}


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


def find_missing(text: str, tokens: tuple[str, ...]) -> list[str]:
    folded = " ".join(text.lower().split())
    return [
        token
        for token in tokens
        if " ".join(token.lower().split()) not in folded
    ]


def find_missing_groups(text: str, groups: dict[str, tuple[str, ...]]) -> list[str]:
    folded = " ".join(text.lower().split())
    missing = []
    for group_name, options in groups.items():
        if not any(" ".join(option.lower().split()) in folded for option in options):
            missing.append(group_name)
    return missing


def extract_section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    next_start = text.find("\n## ", start + len(heading))
    if next_start < 0:
        return text[start:]
    return text[start:next_start]


def selection_multiplicity_evidence(text: str) -> dict[str, Any]:
    section = extract_section(text, SELECTION_MULTIPLICITY_SECTION)
    missing_fields = []
    field_statuses = {}
    for field, tokens in SELECTION_MULTIPLICITY_FIELD_TOKENS.items():
        missing_options = find_missing(section, tokens)
        covered = len(missing_options) < len(tokens)
        field_statuses[field] = {
            "status": "pass" if covered else "fail",
            "accepted_tokens": list(tokens),
        }
        if not covered:
            missing_fields.append(field)
    covered_field_count = len(SELECTION_MULTIPLICITY_FIELD_TOKENS) - len(
        missing_fields
    )
    return {
        "canonical_section_id": CANONICAL_SELECTION_MULTIPLICITY_SECTION_ID,
        "source_heading": SELECTION_MULTIPLICITY_SECTION,
        "source_heading_present": bool(section),
        "status": "pass" if section and not missing_fields else "fail",
        "field_count": len(SELECTION_MULTIPLICITY_FIELD_TOKENS),
        "covered_field_count": covered_field_count,
        "field_coverage": covered_field_count
        / len(SELECTION_MULTIPLICITY_FIELD_TOKENS),
        "missing_fields": missing_fields,
        "field_statuses": field_statuses,
        "claim_boundary": (
            "Manifest-level selection/multiplicity evidence remains scoped to "
            "the manifest claim boundary and does not promote a final winner."
        ),
    }


def status_for(missing_sections: list[str], missing_tokens: list[str]) -> str:
    if missing_sections or missing_tokens:
        return "fail"
    return "pass"


def read_bundle_index(root: Path) -> dict[str, Any]:
    path = root / BUNDLE_INDEX
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def audit_manifest(path: Path, root: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    missing_sections = find_missing(text, REQUIRED_SECTIONS)
    missing_tokens = find_missing(text, REQUIRED_TOKENS)
    missing_negative_tokens = find_missing_groups(text, NEGATIVE_EVIDENCE_GROUPS)
    selection_evidence = selection_multiplicity_evidence(text)
    schema_present = SCHEMA_TOKEN in text
    if not schema_present:
        missing_tokens.append(SCHEMA_TOKEN)
    status = status_for(missing_sections, missing_tokens)
    if status == "pass" and selection_evidence["status"] != "pass":
        status = "fail"
    if status == "pass" and missing_negative_tokens:
        status = "caveat"
    return {
        "path": rel(path, root),
        "status": status,
        "schema_token_present": schema_present,
        "missing_required_sections": missing_sections,
        "missing_required_tokens": missing_tokens,
        "missing_negative_evidence_tokens": missing_negative_tokens,
        "selection_multiplicity_evidence": selection_evidence,
        "required_section_coverage": (
            (len(REQUIRED_SECTIONS) - len(missing_sections)) / len(REQUIRED_SECTIONS)
        ),
        "required_token_coverage": (
            (len(REQUIRED_TOKENS) - len(missing_tokens)) / len(REQUIRED_TOKENS)
        ),
    }


def bundle_index_rows(root: Path, manifest_paths: set[str]) -> dict[str, Any]:
    index = read_bundle_index(root)
    bundles = index.get("bundles") if isinstance(index, dict) else None
    if not isinstance(bundles, list):
        return {
            "index_path": rel(root / BUNDLE_INDEX, root),
            "status": "fail",
            "bundle_count": 0,
            "missing_from_index": sorted(manifest_paths),
            "index_paths_without_manifest": [],
            "declared_bundle_summary": {},
            "computed_bundle_summary": {},
            "summary_mismatches": {},
        }
    indexed_paths = {
        str(row.get("manifest_path"))
        for row in bundles
        if isinstance(row, dict) and row.get("manifest_path")
    }
    missing_from_index = sorted(manifest_paths - indexed_paths)
    index_without_manifest = sorted(indexed_paths - manifest_paths)
    statuses = [
        str(row.get("status", ""))
        for row in bundles
        if isinstance(row, dict)
    ]
    computed_summary = {
        "manifest_count": len(bundles),
        "completed_with_caveats_count": sum(
            status.startswith("completed") for status in statuses
        ),
        "active_run_count": sum(
            "active" in status or "setup" in status for status in statuses
        ),
        "blocked_or_pending_count": sum(
            "blocked" in status or "pending" in status for status in statuses
        ),
    }
    declared_summary = index.get("bundle_summary")
    if not isinstance(declared_summary, dict):
        declared_summary = {}
    summary_mismatches = {
        key: {
            "declared": declared_summary.get(key),
            "computed": value,
        }
        for key, value in computed_summary.items()
        if key in declared_summary and declared_summary.get(key) != value
    }
    return {
        "index_path": rel(root / BUNDLE_INDEX, root),
        "status": "fail" if (
            missing_from_index or index_without_manifest or summary_mismatches
        ) else "pass",
        "bundle_count": len(bundles),
        "missing_from_index": missing_from_index,
        "index_paths_without_manifest": index_without_manifest,
        "declared_bundle_summary": declared_summary,
        "computed_bundle_summary": computed_summary,
        "summary_mismatches": summary_mismatches,
    }


def build_payload(root: Path) -> dict[str, Any]:
    manifest_files = sorted(root.glob(MANIFEST_GLOB))
    rows = [audit_manifest(path, root) for path in manifest_files]
    manifest_paths = {row["path"] for row in rows}
    index_status = bundle_index_rows(root, manifest_paths)
    status_counts = Counter(row["status"] for row in rows)
    selection_status_counts = Counter(
        row["selection_multiplicity_evidence"]["status"] for row in rows
    )
    worst = max((SEVERITY_ORDER[row["status"]] for row in rows), default=2)
    overall_status = {value: key for key, value in SEVERITY_ORDER.items()}[worst]
    if index_status["status"] == "fail":
        overall_status = "fail"
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_glob": MANIFEST_GLOB,
        "summary": {
            "overall_status": overall_status,
            "manifest_count": len(rows),
            "status_counts": dict(sorted(status_counts.items())),
            "required_section_count": len(REQUIRED_SECTIONS),
            "required_token_count": len(REQUIRED_TOKENS),
            "bundle_index_status": index_status["status"],
            "bundle_index_manifest_count": index_status["bundle_count"],
            "selection_multiplicity_manifest_status_counts": dict(
                sorted(selection_status_counts.items())
            ),
            "selection_multiplicity_manifest_pass_count": selection_status_counts.get(
                "pass", 0
            ),
            "selection_multiplicity_manifest_fail_count": selection_status_counts.get(
                "fail", 0
            ),
            "selection_multiplicity_field_count": len(
                SELECTION_MULTIPLICITY_FIELD_TOKENS
            ),
            "selection_multiplicity_all_fields_covered": all(
                row["selection_multiplicity_evidence"]["status"] == "pass"
                for row in rows
            ),
        },
        "bundle_index": index_status,
        "required_sections": list(REQUIRED_SECTIONS),
        "required_tokens": list(REQUIRED_TOKENS),
        "selection_multiplicity_evidence_contract": {
            "canonical_section_id": CANONICAL_SELECTION_MULTIPLICITY_SECTION_ID,
            "source_heading": SELECTION_MULTIPLICITY_SECTION,
            "field_tokens": {
                field: list(tokens)
                for field, tokens in SELECTION_MULTIPLICITY_FIELD_TOKENS.items()
            },
        },
        "rows": rows,
        "claim_boundaries": [
            "This audit checks paper-readiness manifest completeness, not empirical correctness.",
            "Passing this audit does not promote any active run to a final result.",
            "Selection and multiplicity text must stay exploratory unless the claim register and sidecars promote it.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Manuscript Manifest Completeness Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Manifest count: {summary['manifest_count']}",
        f"- Status counts: `{summary['status_counts']}`",
        f"- Bundle index status: `{summary['bundle_index_status']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Manifest Rows",
            "",
            "| Manifest | Status | Missing sections | Missing tokens | Selection fields |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in payload["rows"]:
        selection = row["selection_multiplicity_evidence"]
        lines.append(
            "| "
            f"`{row['path']}` | "
            f"`{row['status']}` | "
            f"{len(row['missing_required_sections'])} | "
            f"{len(row['missing_required_tokens'])} | "
            f"{selection['covered_field_count']} / {selection['field_count']} |"
        )
    lines.extend(
        [
            "",
            "## Selection Multiplicity Evidence Coverage",
            "",
            f"- Canonical section id: `{payload['selection_multiplicity_evidence_contract']['canonical_section_id']}`",
            f"- Source heading: `{payload['selection_multiplicity_evidence_contract']['source_heading']}`",
            f"- Status counts: `{summary['selection_multiplicity_manifest_status_counts']}`",
            f"- All fields covered: `{summary['selection_multiplicity_all_fields_covered']}`",
        ]
    )
    index = payload["bundle_index"]
    lines.extend(
        [
            "",
            "## Bundle Index",
            "",
            f"- Index path: `{index['index_path']}`",
            f"- Status: `{index['status']}`",
            f"- Bundle count: {index['bundle_count']}",
            f"- Missing from index: `{index['missing_from_index']}`",
            f"- Index paths without manifest: `{index['index_paths_without_manifest']}`",
            f"- Declared bundle summary: `{index['declared_bundle_summary']}`",
            f"- Computed bundle summary: `{index['computed_bundle_summary']}`",
            f"- Summary mismatches: `{index['summary_mismatches']}`",
        ]
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
