"""Build the diagnostic group-comparison multiplicity scope.

The current fairness artifacts contain group-stratified diagnostics, not a
population or protected-class fairness claim. This artifact closes the paper-gate
action that declares how those diagnostic group comparisons are grouped,
controlled, and cited without promoting fairness language.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_fairness_group_multiplicity_scope_v1"
ACTION_ID = (
    "fairness_population_inference_gate."
    "declare_group_comparison_multiplicity_scope"
)
GATE_ID = "fairness_population_inference_gate"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/fairness_group_multiplicity_scope.json"
)
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
FAIRNESS_GROUP_DIAGNOSTIC_AUDIT = REPORT_DIR / "fairness_group_diagnostic_audit.json"
FAIRNESS_SAMPLING_WEIGHT_POLICY = Path(
    "experiments/regression/manuscript/fairness_sampling_weight_policy.json"
)
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
CLAIM_REGISTER_MD = Path("experiments/regression/catalogs/manuscript_claim_register.md")
CLAIM_ID = "final_selection_and_fairness_claims_blocked"
REQUIREMENT_ID = "fairness_population_inference_gate"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def claim_requirement(claim_register: dict[str, Any]) -> dict[str, Any]:
    for claim in claim_register.get("claims", []) or []:
        if not isinstance(claim, dict) or claim.get("claim_id") != CLAIM_ID:
            continue
        for requirement in claim.get("requirements", []) or []:
            if (
                isinstance(requirement, dict)
                and requirement.get("requirement_id") == REQUIREMENT_ID
            ):
                return requirement
    return {}


def artifact_cited_by_claim_register(requirement: dict[str, Any], *, out_path: Path) -> bool:
    artifact_paths = {str(path) for path in requirement.get("artifact_paths", []) or []}
    supporting_nodes = {
        str(node) for node in requirement.get("supporting_node_ids", []) or []
    }
    return (
        out_path.as_posix() in artifact_paths
        and "report:fairness_group_multiplicity_scope" in supporting_nodes
    )


def comparison_count(row: dict[str, Any]) -> int:
    group_count = int(row.get("group_count") or len(row.get("group_counts") or {}))
    return max(group_count * (group_count - 1) // 2, 0)


def scope_row(row: dict[str, Any]) -> dict[str, Any]:
    bundle_id = str(row.get("bundle_id") or "")
    dataset_id = str(row.get("dataset_id") or "")
    diagnostic_group = str(row.get("diagnostic_group") or "")
    family_id = (
        "diagnostic_group_gap_family:"
        f"{dataset_id}:{diagnostic_group}:{bundle_id}"
    )
    group_count = int(row.get("group_count") or len(row.get("group_counts") or {}))
    return {
        "action_id": ACTION_ID,
        "gate_id": GATE_ID,
        "bundle_id": bundle_id,
        "dataset_id": dataset_id,
        "target": row.get("target"),
        "target_transform": row.get("target_transform"),
        "diagnostic_group": diagnostic_group,
        "group_source_column": row.get("group_source_column") or diagnostic_group,
        "comparison_family_id": family_id,
        "family_role": "exploratory_diagnostic_group_gap_family",
        "metric_family": "coverage_width_and_target_gap_diagnostics",
        "group_count": group_count,
        "pairwise_group_comparison_count": comparison_count(row),
        "min_group_count": row.get("min_group_count"),
        "gap_uncertainty_recorded": bool(row.get("group_gap_uncertainty_recorded")),
        "multiplicity_scope_declared_for_group_comparisons": True,
        "multiplicity_policy": (
            "single_exploratory_family_no_significance_or_winner_decisions"
        ),
        "correction_or_selective_inference_policy": (
            "No hypothesis-test rejection, winner selection, protected-class "
            "fairness pass/fail, or population conclusion is made from these "
            "diagnostic comparisons. Any future confirmatory claim must create a "
            "separate pre-registered multiplicity record with its own error-rate "
            "contract."
        ),
        "decision_rule": "descriptive_diagnostics_only_no_claim_promotion",
        "claim_effect": "multiplicity_scope_declared_no_fairness_claim",
        "fairness_population_claim_status": (
            "blocked_diagnostic_only_no_population_claim"
        ),
        "allowed_claim_language": [
            "diagnostic group-stratified coverage/width/gap evidence within the scoped bundle",
            "exploratory comparison family declared with no significance or winner decision",
        ],
        "prohibited_claim_language": [
            "population fairness",
            "protected-class fairness",
            "legal or policy fairness conclusion",
            "clinical subgroup validity",
            "causal disparity conclusion",
            "statistically significant group disparity",
            "best or worst group conclusion after multiplicity correction",
        ],
        "source_artifacts": [
            FAIRNESS_GROUP_DIAGNOSTIC_AUDIT.as_posix(),
            FAIRNESS_SAMPLING_WEIGHT_POLICY.as_posix(),
            CLAIM_REGISTER.as_posix(),
        ],
    }


def build_payload(root: Path, *, out_path: Path) -> dict[str, Any]:
    diagnostic_path = root / FAIRNESS_GROUP_DIAGNOSTIC_AUDIT
    sampling_policy_path = root / FAIRNESS_SAMPLING_WEIGHT_POLICY
    claim_register_path = root / CLAIM_REGISTER
    claim_register_md_path = root / CLAIM_REGISTER_MD
    diagnostic = read_json(diagnostic_path)
    claim_register = read_json(claim_register_path)
    requirement = claim_requirement(claim_register)
    claim_register_md = (
        claim_register_md_path.read_text(encoding="utf-8")
        if claim_register_md_path.exists()
        else ""
    )
    rows = [
        scope_row(row)
        for row in diagnostic.get("rows", []) or []
        if isinstance(row, dict) and row.get("bundle_id")
    ]
    dataset_counts = Counter(row["dataset_id"] for row in rows)
    citation_present = artifact_cited_by_claim_register(
        requirement, out_path=out_path
    ) and "fairness_group_multiplicity_scope" in claim_register_md
    failed_checks: list[dict[str, Any]] = []
    if not rows:
        failed_checks.append(
            {"check_id": "diagnostic_group_rows_present", "status": "fail"}
        )
    if not all(row["comparison_family_id"] for row in rows):
        failed_checks.append(
            {"check_id": "all_rows_have_comparison_family_id", "status": "fail"}
        )
    if not all(row["gap_uncertainty_recorded"] for row in rows):
        failed_checks.append(
            {"check_id": "all_rows_have_gap_uncertainty", "status": "fail"}
        )
    if not all(
        row["multiplicity_scope_declared_for_group_comparisons"] for row in rows
    ):
        failed_checks.append(
            {
                "check_id": "multiplicity_scope_declared_for_group_comparisons",
                "status": "fail",
            }
        )
    if not citation_present:
        failed_checks.append(
            {
                "check_id": "claim_register_cites_multiplicity_record",
                "status": "fail",
            }
        )
    if not requirement or requirement.get("status") != "blocked":
        failed_checks.append(
            {
                "check_id": "fairness_claim_register_requirement_remains_blocked",
                "status": "fail",
            }
        )
    if not sampling_policy_path.exists():
        failed_checks.append(
            {"check_id": "sampling_weight_policy_source_present", "status": "fail"}
        )
    if any(
        row["claim_effect"] != "multiplicity_scope_declared_no_fairness_claim"
        for row in rows
    ):
        failed_checks.append(
            {"check_id": "no_population_fairness_claim_promoted", "status": "fail"}
        )

    overall_status = (
        "fairness_group_multiplicity_scope_failed"
        if failed_checks
        else "fairness_group_multiplicity_scope_declared_no_fairness_claim"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "action_id": ACTION_ID,
            "gate_id": GATE_ID,
            "action_status": "multiplicity_control_complete"
            if not failed_checks
            else "incomplete",
            "claim_promoted_action_count": 0,
            "failed_check_count": len(failed_checks),
            "bundle_count": len(rows),
            "dataset_count": len(dataset_counts),
            "dataset_counts": dict(sorted(dataset_counts.items())),
            "comparison_family_count": len(
                {row["comparison_family_id"] for row in rows}
            ),
            "pairwise_group_comparison_count": sum(
                row["pairwise_group_comparison_count"] for row in rows
            ),
            "multiplicity_scope_declared_bundle_count": sum(
                1
                for row in rows
                if row["multiplicity_scope_declared_for_group_comparisons"]
            ),
            "claim_register_cites_multiplicity_record": citation_present,
            "fairness_requirement_status": requirement.get("status"),
            "population_fairness_ready_bundle_count": 0,
            "current_manuscript_fairness_population_claim_ready": False,
        },
        "completed_action_ids": [ACTION_ID] if not failed_checks else [],
        "checks": {
            "diagnostic_group_rows_present": bool(rows),
            "all_rows_have_comparison_family_id": all(
                row["comparison_family_id"] for row in rows
            ),
            "all_rows_have_gap_uncertainty": all(
                row["gap_uncertainty_recorded"] for row in rows
            ),
            "multiplicity_scope_declared_for_group_comparisons": all(
                row["multiplicity_scope_declared_for_group_comparisons"]
                for row in rows
            ),
            "claim_register_cites_multiplicity_record": citation_present,
            "fairness_claim_register_requirement_remains_blocked": (
                requirement.get("status") == "blocked"
            ),
            "sampling_weight_policy_source_present": sampling_policy_path.exists(),
            "no_population_fairness_claim_promoted": not any(
                row["claim_effect"] != "multiplicity_scope_declared_no_fairness_claim"
                for row in rows
            ),
        },
        "failed_checks": failed_checks,
        "multiplicity_policy": {
            "scope": "diagnostic_group_comparisons_across_current_manuscript_bundles",
            "family_unit": "bundle_dataset_group_metric_family",
            "correction_or_selective_inference_policy": (
                "Exploratory descriptive family only. No alpha-spending, p-value "
                "adjustment, FWER/FDR decision, protected-group pass/fail, or "
                "method winner is inferred from these group comparisons."
            ),
            "future_confirmatory_requirement": (
                "Any future population or protected-class fairness claim requires "
                "a pre-registered estimand, protected attribute scope, sampling or "
                "weighting policy, confirmatory comparison family, and explicit "
                "error-rate control before claim-register promotion."
            ),
        },
        "claim_boundaries": [
            "The multiplicity scope is declared for diagnostic group comparisons only.",
            "No population, protected-class, legal, policy, clinical, causal, production, or final-selection fairness claim is promoted.",
            "The claim register remains blocked for the fairness population inference gate.",
        ],
        "rows": rows,
        "sources": {
            "fairness_group_diagnostic_audit": rel(diagnostic_path, root),
            "fairness_sampling_weight_policy": rel(sampling_policy_path, root),
            "manuscript_claim_register": rel(claim_register_path, root),
            "manuscript_claim_register_markdown": rel(claim_register_md_path, root),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    policy = payload["multiplicity_policy"]
    lines = [
        "# Fairness Group Multiplicity Scope",
        "",
        "This artifact declares the diagnostic comparison family for group-stratified evidence. It does not promote a fairness claim.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Action: `{summary['action_id']}`",
        f"- Bundles: {summary['bundle_count']}",
        f"- Datasets: {summary['dataset_count']}",
        f"- Comparison families: {summary['comparison_family_count']}",
        f"- Pairwise group comparisons: {summary['pairwise_group_comparison_count']}",
        f"- Claim register cites record: `{summary['claim_register_cites_multiplicity_record']}`",
        f"- Population-fairness-ready bundles: {summary['population_fairness_ready_bundle_count']}",
        f"- Failed checks: {summary['failed_check_count']}",
        "",
        "## Multiplicity Policy",
        "",
        f"- Scope: `{policy['scope']}`",
        f"- Family unit: `{policy['family_unit']}`",
        f"- Policy: {policy['correction_or_selective_inference_policy']}",
        f"- Future confirmatory requirement: {policy['future_confirmatory_requirement']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Bundle Rows",
            "",
            "| Bundle | Dataset | Group | Family | Pairwise comparisons | Claim effect |",
            "|---|---|---|---|---:|---|",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['bundle_id']}`",
                    f"`{row['dataset_id']}`",
                    f"`{row['diagnostic_group']}`",
                    f"`{row['comparison_family_id']}`",
                    str(row["pairwise_group_comparison_count"]),
                    f"`{row['claim_effect']}`",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = root / args.out
    payload = build_payload(root, out_path=Path(args.out))
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
