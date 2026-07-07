"""Audit publication-methodology readiness boundaries for regression CP.

This audit is deliberately narrower than a manuscript acceptance decision. It
turns the publication-methodology note into a reproducible source-derived
artifact, so stale snapshots cannot contradict the current retrospective gate.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_publication_methodology_audit_v2"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "publication_methodology_audit.json"
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
CLAIM_REGISTER_MD = Path("experiments/regression/catalogs/manuscript_claim_register.md")
MANUSCRIPT_BUNDLE_INDEX = Path(
    "experiments/regression/catalogs/manuscript_bundle_index.json"
)
PROTOCOL = Path("experiments/regression/PUBLICATION_READINESS_PROTOCOL.md")
FINAL_SELECTION_CLAIM_ID = "final_selection_and_fairness_claims_blocked"
FAIRNESS_POPULATION_READINESS = REPORT_DIR / "fairness_population_readiness_audit.json"
VENN_ABERS_NEGATIVE_DISPOSITION = (
    REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
)

BLOCKED_FINAL_REQUIREMENTS = {
    "final_method_model_selection_gate",
    "multiplicity_selection_record",
    "dataset_specific_final_gates",
    "endpoint_bounded_support_gate",
    "fairness_population_inference_gate",
    "venn_abers_regression_validation_gate",
}
STALE_TOKENS = (
    "8 open actions",
    "8 open",
    "17:05 retrospective gate",
    "not yet included",
    "uncommitted sidecar evidence",
    "lawschool sidecars are uncommitted",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def count_by_status(rows: list[dict[str, Any]]) -> dict[str, int]:
    statuses = [str(row.get("status")) for row in rows if row.get("status")]
    return dict(sorted(Counter(statuses).items()))


def find_claim(claim_register: dict[str, Any]) -> dict[str, Any]:
    for claim in claim_register.get("claims", []) or []:
        if (
            isinstance(claim, dict)
            and claim.get("claim_id") == FINAL_SELECTION_CLAIM_ID
        ):
            return claim
    return {}


def requirement_statuses(claim: dict[str, Any]) -> dict[str, str]:
    statuses = {}
    for item in claim.get("requirements", []) or []:
        if isinstance(item, dict) and item.get("requirement_id"):
            statuses[str(item["requirement_id"])] = str(item.get("status"))
    return statuses


def contains_all(text: str, tokens: tuple[str, ...]) -> bool:
    folded = text.lower()
    return all(token.lower() in folded for token in tokens)


def contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    folded = text.lower()
    return any(token.lower() in folded for token in tokens)


def build_payload(root: Path) -> dict[str, Any]:
    cross_path = root / REPORT_DIR / "cross_run_integrity_audit.json"
    controls_path = root / REPORT_DIR / "retrospective_methodology_controls.json"
    backlog_path = root / REPORT_DIR / "integrity_remediation_backlog.json"
    manifest_path = root / REPORT_DIR / "manuscript_manifest_completeness_audit.json"
    claim_consistency_path = (
        root / REPORT_DIR / "manuscript_claim_register_consistency_audit.json"
    )
    final_selection_path = (
        root / REPORT_DIR / "final_selection_claim_boundary_audit.json"
    )
    fairness_population_path = root / FAIRNESS_POPULATION_READINESS
    venn_abers_negative_path = root / VENN_ABERS_NEGATIVE_DISPOSITION
    claim_register_path = root / CLAIM_REGISTER
    claim_register_md_path = root / CLAIM_REGISTER_MD
    bundle_index_path = root / MANUSCRIPT_BUNDLE_INDEX
    protocol_path = root / PROTOCOL

    cross = read_json(cross_path)
    controls = read_json(controls_path)
    backlog = read_json(backlog_path)
    manifest = read_json(manifest_path)
    claim_consistency = read_json(claim_consistency_path)
    final_selection = read_json(final_selection_path)
    fairness_population = read_json(fairness_population_path)
    venn_abers_negative = read_json_if_present(venn_abers_negative_path)
    claim_register = read_json(claim_register_path)
    bundle_index = read_json(bundle_index_path)
    protocol_text = protocol_path.read_text(encoding="utf-8")
    claim_register_md = claim_register_md_path.read_text(encoding="utf-8")

    cross_summary = cross.get("summary") or {}
    controls_summary = controls.get("summary") or {}
    backlog_summary = backlog.get("summary") or {}
    manifest_summary = manifest.get("summary") or {}
    claim_consistency_summary = claim_consistency.get("summary") or {}
    final_selection_summary = final_selection.get("summary") or {}
    fairness_population_summary = fairness_population.get("summary") or {}
    venn_abers_negative_summary = venn_abers_negative.get("summary") or {}
    final_claim = find_claim(claim_register)
    req_statuses = requirement_statuses(final_claim)
    bundles = [
        row for row in bundle_index.get("bundles", []) or [] if isinstance(row, dict)
    ]
    open_actions = int(backlog_summary.get("open_action_count") or 0)
    unsupported_claim_hits = int(cross_summary.get("unsupported_claim_hits") or 0)
    control_caveats = int(
        (controls_summary.get("control_status_counts") or {}).get("caveat") or 0
    )
    blocked_final_requirements = sorted(
        requirement_id
        for requirement_id in BLOCKED_FINAL_REQUIREMENTS
        if req_statuses.get(requirement_id) == "blocked"
    )
    stale_text = "\n".join(
        [
            json.dumps(
                {
                    "cross_summary": cross_summary,
                    "backlog_summary": backlog_summary,
                    "final_selection_summary": final_selection_summary,
                },
                sort_keys=True,
            ),
            claim_register_md,
            protocol_text,
        ]
    )
    checks = {
        "cross_run_has_no_blocking_issues": not bool(
            cross_summary.get("blocking_issue_counts") or {}
        ),
        "hard_leakage_not_detected": (
            cross_summary.get("leakage_status")
            == "hard_leakage_not_detected_in_scanned_artifacts"
            and controls_summary.get("hard_leakage_status")
            == "no_hard_leakage_detected_in_scanned_artifacts"
        ),
        "unsupported_claim_hits_zero": unsupported_claim_hits == 0,
        "remediation_backlog_has_no_open_actions": open_actions == 0,
        "remediation_backlog_actions_are_covered": (
            int(backlog_summary.get("action_count") or 0)
            == int(backlog_summary.get("covered_action_count") or 0)
            and open_actions == 0
        ),
        "manifest_completeness_passes": manifest_summary.get("overall_status")
        == "pass",
        "claim_register_consistency_passes": (
            claim_consistency_summary.get("overall_status") == "pass"
        ),
        "final_selection_boundary_passes": (
            final_selection_summary.get("overall_status") == "pass"
        ),
        "final_selection_claim_remains_blocked": (
            final_selection_summary.get("claim_status") == "blocked"
            and len(blocked_final_requirements) == len(BLOCKED_FINAL_REQUIREMENTS)
        ),
        "fairness_population_readiness_keeps_claim_blocked": (
            fairness_population_summary.get("overall_status")
            == "fairness_population_readiness_audit_completed_no_fairness_claim"
            and int(fairness_population_summary.get("failed_check_count") or 0) == 0
            and fairness_population_summary.get(
                "can_support_publication_ready_fairness"
            )
            is False
            and fairness_population_summary.get("fairness_requirement_status")
            == "blocked"
            and fairness_population_summary.get("fairness_population_claim_status")
            == "blocked_diagnostic_only"
        ),
        "retrospective_controls_keep_caveats_visible": control_caveats >= 1,
        "bundle_index_has_no_active_or_pending_bundle": all(
            "active" not in str(row.get("status", "")).lower()
            and "pending" not in str(row.get("status", "")).lower()
            for row in bundles
        ),
        "protocol_declares_selection_multiplicity_boundary": contains_all(
            protocol_text,
            (
                "Model Selection And Multiplicity",
                "predeclared operating criterion",
                "multiplicity scope",
                "post-selection claim boundary",
            ),
        ),
        "source_claims_do_not_contain_stale_snapshot_tokens": not contains_any(
            stale_text,
            STALE_TOKENS,
        ),
    }
    failed_checks = [key for key, value in checks.items() if not value]
    if failed_checks:
        overall_status = "fail"
    elif control_caveats:
        overall_status = "publication_workbench_ready_with_caveats"
    else:
        overall_status = "publication_workbench_ready"

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "cross_run_integrity": rel(cross_path, root),
            "retrospective_methodology_controls": rel(controls_path, root),
            "integrity_remediation_backlog": rel(backlog_path, root),
            "manuscript_manifest_completeness": rel(manifest_path, root),
            "manuscript_claim_register_consistency": rel(claim_consistency_path, root),
            "final_selection_claim_boundary": rel(final_selection_path, root),
            "fairness_population_readiness": rel(fairness_population_path, root),
            "venn_abers_negative_evidence_disposition": rel(
                venn_abers_negative_path, root
            ),
            "manuscript_claim_register": rel(claim_register_path, root),
            "manuscript_claim_register_markdown": rel(claim_register_md_path, root),
            "manuscript_bundle_index": rel(bundle_index_path, root),
            "publication_readiness_protocol": rel(protocol_path, root),
        },
        "summary": {
            "overall_status": overall_status,
            "reports_scanned": cross_summary.get("reports_scanned"),
            "configs_scanned": cross_summary.get("configs_scanned"),
            "total_completed_rows": cross_summary.get("total_completed_rows"),
            "unsupported_claim_hits": unsupported_claim_hits,
            "blocking_issue_counts": cross_summary.get("blocking_issue_counts", {}),
            "caveat_counts": cross_summary.get("caveat_counts", {}),
            "hard_leakage_status": cross_summary.get("leakage_status"),
            "control_status_counts": controls_summary.get("control_status_counts", {}),
            "open_remediation_actions": open_actions,
            "covered_remediation_actions": backlog_summary.get("covered_action_count"),
            "remediation_action_count": backlog_summary.get("action_count"),
            "manifest_count": manifest_summary.get("manifest_count"),
            "bundle_index_manifest_count": manifest_summary.get(
                "bundle_index_manifest_count"
            ),
            "bundle_status_counts": count_by_status(bundles),
            "claim_register_status": claim_consistency_summary.get("overall_status"),
            "claim_count": claim_consistency_summary.get("claim_count"),
            "final_selection_boundary_status": final_selection_summary.get(
                "overall_status"
            ),
            "final_selection_claim_status": final_selection_summary.get("claim_status"),
            "fairness_population_readiness_status": fairness_population_summary.get(
                "overall_status"
            ),
            "fairness_population_claim_status": fairness_population_summary.get(
                "fairness_population_claim_status"
            ),
            "diagnostic_group_bundle_count": fairness_population_summary.get(
                "diagnostic_group_bundle_count"
            ),
            "population_fairness_ready_bundle_count": fairness_population_summary.get(
                "population_fairness_ready_bundle_count"
            ),
            "blocked_final_requirement_count": len(blocked_final_requirements),
            "current_paper_mandatory_blocked_requirement_count": len(
                [
                    requirement_id
                    for requirement_id in blocked_final_requirements
                    if requirement_id != "venn_abers_regression_validation_gate"
                ]
            ),
            "failed_check_count": len(failed_checks),
            "can_support_final_method_selection": False,
            "can_support_publication_ready_fairness": False,
            "can_support_bounded_support_validity": False,
            "can_support_venn_abers_regression_validation": False,
            "venn_abers_negative_result_reporting_ready": (
                venn_abers_negative_summary.get("negative_result_reporting_ready")
            ),
            "current_manuscript_positive_venn_abers_validation_required": (
                venn_abers_negative_summary.get(
                    "current_manuscript_positive_validation_required"
                )
            ),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "blocked_final_requirements": blocked_final_requirements,
        "requirement_statuses": req_statuses,
        "claim_boundaries": [
            "This audit supports publication-methodology triage, not final paper acceptance.",
            "A pass or caveated pass means the workbench evidence is organized and claim-gated.",
            "Final model/method selection, fairness conclusions, bounded-support validity, and validated Venn-Abers regression remain blocked until their dedicated gates pass.",
            "The current manuscript may still report the observed Venn-Abers negative result when the negative-evidence disposition audit is clean.",
            "A closed remediation backlog does not by itself promote final scientific claims.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    blocking_issues = json.dumps(summary["blocking_issue_counts"], sort_keys=True)
    caveat_counts = json.dumps(summary["caveat_counts"], sort_keys=True)
    control_status_counts = json.dumps(
        summary["control_status_counts"],
        sort_keys=True,
    )
    bundle_status_counts = json.dumps(summary["bundle_status_counts"], sort_keys=True)
    lines = [
        "# Publication Methodology Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Reports scanned: {summary['reports_scanned']}",
        f"- Completed ledger rows represented: {summary['total_completed_rows']}",
        f"- Unsupported claim hits: {summary['unsupported_claim_hits']}",
        f"- Open remediation actions: {summary['open_remediation_actions']}",
        f"- Final-selection boundary: `{summary['final_selection_boundary_status']}`",
        f"- Fairness/population readiness: `{summary['fairness_population_readiness_status']}`",
        f"- Blocked final-selection requirements: {summary['blocked_final_requirement_count']}",
        f"- Current-paper mandatory blocked requirements: {summary['current_paper_mandatory_blocked_requirement_count']}",
        f"- Venn-Abers negative result reporting ready: `{summary['venn_abers_negative_result_reporting_ready']}`",
        "",
        "## Verdict",
        "",
        (
            "The current regression conformal-prediction system is usable as a "
            "reproducible exploratory and benchmark workbench for manuscript "
            "evidence extraction. It is still not evidence for final method/model "
            "selection, publication-ready fairness conclusions, bounded-support "
            "validity, production guidance, or validated Venn-Abers regression."
        ),
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Readiness Summary",
            "",
            "| Area | Current value |",
            "| --- | --- |",
            f"| Cross-run blocking issues | `{blocking_issues}` |",
            f"| Cross-run caveats | `{caveat_counts}` |",
            f"| Retrospective controls | `{control_status_counts}` |",
            f"| Remediation actions | {summary['covered_remediation_actions']} / {summary['remediation_action_count']} covered, {summary['open_remediation_actions']} open |",
            f"| Manifest count | {summary['manifest_count']} |",
            f"| Bundle status counts | `{bundle_status_counts}` |",
            f"| Claim-register status | `{summary['claim_register_status']}` |",
            f"| Final-selection claim status | `{summary['final_selection_claim_status']}` |",
            f"| Fairness/population claim status | `{summary['fairness_population_claim_status']}` |",
            f"| Diagnostic-group bundles | {summary['diagnostic_group_bundle_count']} |",
            f"| Population-fairness ready bundles | {summary['population_fairness_ready_bundle_count']} |",
            "",
            "## Blocked Final Claims",
            "",
            "| Claim family | Supported now? | Reason |",
            "| --- | --- | --- |",
            "| Final method/model selection | `False` | Dedicated final-selection and multiplicity gates remain blocked. |",
            "| Publication-ready fairness conclusions | `False` | Population/fairness inference gate remains blocked. |",
            "| Bounded-support validity | `False` | Endpoint reconstruction is hygiene evidence, not bounded-support proof. |",
            "| Validated Venn-Abers regression | `False` | Venn-Abers regression validation gate remains blocked. |",
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
            "## Blocked Requirements",
            "",
            "| Requirement | Status |",
            "| --- | --- |",
        ]
    )
    for requirement_id in payload["blocked_final_requirements"]:
        lines.append(f"| `{requirement_id}` | `blocked` |")
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
    return 0 if not payload["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
