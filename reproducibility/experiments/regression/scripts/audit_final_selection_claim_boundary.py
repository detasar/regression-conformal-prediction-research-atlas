"""Audit the study-wide final-selection blocked claim boundary.

This audit keeps the manuscript claim register aligned with the current
methodology state. It is intentionally not a model-selection script; it checks
that final method/model, fairness, bounded-support, production, and
Venn-Abers-validation claims remain blocked for explicit gate reasons rather
than stale backlog wording.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_final_selection_claim_boundary_audit_v1"
CLAIM_ID = "final_selection_and_fairness_claims_blocked"
DEFAULT_REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = DEFAULT_REPORT_DIR / "final_selection_claim_boundary_audit.json"
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
CLAIM_REGISTER_MD = Path("experiments/regression/catalogs/manuscript_claim_register.md")
PROTOCOL = Path("experiments/regression/PUBLICATION_READINESS_PROTOCOL.md")
REMEDIATION_BACKLOG = DEFAULT_REPORT_DIR / "integrity_remediation_backlog.json"
RETROSPECTIVE_CONTROLS = DEFAULT_REPORT_DIR / "retrospective_methodology_controls.json"
MANIFEST_COMPLETENESS = DEFAULT_REPORT_DIR / "manuscript_manifest_completeness_audit.json"

PASS_REQUIREMENTS = {
    "remediation_backlog_closed_or_scoped",
}
BLOCKED_REQUIREMENTS = {
    "final_method_model_selection_gate",
    "multiplicity_selection_record",
    "dataset_specific_final_gates",
    "endpoint_bounded_support_gate",
    "fairness_population_inference_gate",
    "venn_abers_regression_validation_gate",
}
BROAD_NONCLAIM_TOKENS = (
    "final",
    "method/model",
    "fairness",
    "population",
    "legal",
    "policy",
    "production",
    "bounded-support",
    "Venn-Abers",
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def status_map(claim: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("requirement_id")): str(item.get("status"))
        for item in claim.get("requirements", []) or []
        if isinstance(item, dict) and item.get("requirement_id")
    }


def find_claim(claim_register: dict[str, Any]) -> dict[str, Any]:
    for claim in claim_register.get("claims", []) or []:
        if isinstance(claim, dict) and claim.get("claim_id") == CLAIM_ID:
            return claim
    return {}


def contains_all(text: str, tokens: tuple[str, ...]) -> bool:
    folded = text.lower()
    return all(token.lower() in folded for token in tokens)


def build_payload(root: Path) -> dict[str, Any]:
    claim_register_path = root / CLAIM_REGISTER
    claim_register_md_path = root / CLAIM_REGISTER_MD
    protocol_path = root / PROTOCOL
    backlog_path = root / REMEDIATION_BACKLOG
    controls_path = root / RETROSPECTIVE_CONTROLS
    manifest_path = root / MANIFEST_COMPLETENESS

    claim_register = read_json(claim_register_path)
    claim = find_claim(claim_register)
    requirements = status_map(claim)
    backlog = read_json(backlog_path)
    controls = read_json(controls_path)
    manifest = read_json(manifest_path)
    backlog_summary = backlog.get("summary") or {}
    controls_summary = controls.get("summary") or {}
    manifest_summary = manifest.get("summary") or {}
    open_actions = int(backlog_summary.get("open_action_count") or 0)
    control_status_counts = controls_summary.get("control_status_counts") or {}
    md_text = claim_register_md_path.read_text(encoding="utf-8")
    protocol_text = protocol_path.read_text(encoding="utf-8")
    claim_nonclaim_text = " ".join(str(item) for item in claim.get("not_claiming", []) or [])

    checks = {
        "claim_present": bool(claim),
        "claim_status_blocked": claim.get("status") == "blocked",
        "protocol_defines_selection_multiplicity": contains_all(
            protocol_text,
            (
                "Model Selection And Multiplicity",
                "predeclared operating criterion",
                "multiplicity scope",
                "post-selection claim boundary",
            ),
        ),
        "remediation_backlog_closed_or_scoped_current": (
            open_actions == 0
            and requirements.get("remediation_backlog_closed_or_scoped") == "pass"
        ),
        "no_stale_backlog_blocker_when_backlog_closed": not (
            open_actions == 0
            and (
                requirements.get("all_backlog_actions_closed_or_scoped") == "blocked"
                or "report:integrity_remediation_backlog"
                in set(claim.get("blocking_node_ids", []) or [])
            )
        ),
        "required_blocked_gates_recorded": all(
            requirements.get(requirement_id) == "blocked"
            for requirement_id in sorted(BLOCKED_REQUIREMENTS)
        ),
        "no_final_selection_requirement_promoted": not any(
            requirements.get(requirement_id) in {"pass", "present", "complete"}
            for requirement_id in BLOCKED_REQUIREMENTS
        ),
        "broad_nonclaims_recorded": contains_all(
            claim.get("claim_text", "") + " " + claim_nonclaim_text,
            BROAD_NONCLAIM_TOKENS,
        ),
        "markdown_register_mentions_same_gate": contains_all(
            md_text,
            (
                CLAIM_ID,
                "remediation_backlog_closed_or_scoped",
                "final_method_model_selection_gate",
                "venn_abers_regression_validation_gate",
            ),
        ),
        "retrospective_controls_still_caveated": int(
            control_status_counts.get("caveat") or 0
        )
        >= 1,
        "manifest_completeness_is_not_final_selection": (
            manifest_summary.get("overall_status") == "pass"
            and manifest_summary.get("bundle_index_status") == "pass"
            and claim.get("status") == "blocked"
        ),
    }
    missing_blocked = sorted(
        requirement_id
        for requirement_id in BLOCKED_REQUIREMENTS
        if requirements.get(requirement_id) != "blocked"
    )
    missing_pass = sorted(
        requirement_id
        for requirement_id in PASS_REQUIREMENTS
        if requirements.get(requirement_id) != "pass"
    )
    failed_checks = [key for key, value in checks.items() if not value]
    status = "pass" if not failed_checks else "fail"
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim_register": rel(claim_register_path, root),
        "claim_register_markdown": rel(claim_register_md_path, root),
        "protocol": rel(protocol_path, root),
        "source_artifacts": {
            "integrity_remediation_backlog": rel(backlog_path, root),
            "retrospective_methodology_controls": rel(controls_path, root),
            "manuscript_manifest_completeness": rel(manifest_path, root),
        },
        "summary": {
            "overall_status": status,
            "claim_id": CLAIM_ID,
            "claim_status": claim.get("status"),
            "open_remediation_actions": open_actions,
            "blocked_requirement_count": len(
                [
                    requirement_id
                    for requirement_id in BLOCKED_REQUIREMENTS
                    if requirements.get(requirement_id) == "blocked"
                ]
            ),
            "pass_requirement_count": len(
                [
                    requirement_id
                    for requirement_id in PASS_REQUIREMENTS
                    if requirements.get(requirement_id) == "pass"
                ]
            ),
            "failed_check_count": len(failed_checks),
            "control_status_counts": dict(sorted(Counter(control_status_counts).items())),
            "manifest_overall_status": manifest_summary.get("overall_status"),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "missing_blocked_requirements": missing_blocked,
        "missing_pass_requirements": missing_pass,
        "requirement_statuses": requirements,
        "claim_boundaries": [
            "This audit checks final-selection claim hygiene; it is not a model-selection result.",
            "A pass means final method/model, fairness, endpoint-validity, production, and Venn-Abers-validation claims remain blocked for current explicit gate reasons.",
            "A closed remediation backlog is not sufficient to promote a final-selection claim.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Final Selection Claim Boundary Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Claim id: `{summary['claim_id']}`",
        f"- Claim status: `{summary['claim_status']}`",
        f"- Open remediation actions: {summary['open_remediation_actions']}",
        f"- Blocked requirement count: {summary['blocked_requirement_count']}",
        f"- Pass requirement count: {summary['pass_requirement_count']}",
        f"- Failed checks: {summary['failed_check_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status |",
            "| --- | --- |",
        ]
    )
    for check, passed in payload["checks"].items():
        lines.append(f"| `{check}` | `{passed}` |")
    lines.extend(
        [
            "",
            "## Requirement Statuses",
            "",
            "| Requirement | Status |",
            "| --- | --- |",
        ]
    )
    for requirement_id, status in sorted(payload["requirement_statuses"].items()):
        lines.append(f"| `{requirement_id}` | `{status}` |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "out": rel(out_path, root),
                "failed_checks": payload["failed_checks"],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
