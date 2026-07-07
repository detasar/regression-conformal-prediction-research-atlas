"""Build the fairness sampling/weighting policy contract.

The current regression manuscript bundles contain group-stratified diagnostics,
but they do not support population-weighted or protected-class fairness claims.
This artifact completes the paper-gate action that defines the sampling-weight
policy needed before any future fairness population inference can be promoted.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_fairness_sampling_weight_policy_v1"
ACTION_ID = "fairness_population_inference_gate.define_sampling_weight_policy"
GATE_ID = "fairness_population_inference_gate"
DEFAULT_OUT = Path("experiments/regression/manuscript/fairness_sampling_weight_policy.json")
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
PAPER_GATE_PROTOCOL_DESIGN_BUNDLE = Path(
    "experiments/regression/manuscript/paper_gate_protocol_design_bundle.json"
)
FAIRNESS_POPULATION_READINESS = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "fairness_population_readiness_audit.json"
)
AUDIT_ROOT = Path("experiments/regression/audits")


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


def dataset_audit_payload(root: Path, dataset_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name in ("audit.json", "profile.json", "duplicate_sensitivity_profile.json"):
        path = root / AUDIT_ROOT / dataset_id / name
        if path.exists():
            payload.update(read_json(path))
    return payload


def survey_design_columns(payload: dict[str, Any]) -> list[str]:
    values = payload.get("survey_design_columns")
    if isinstance(values, list):
        return [str(value) for value in values if value]
    return []


def dataset_policy(dataset_id: str, audit_payload: dict[str, Any]) -> dict[str, Any]:
    columns = survey_design_columns(audit_payload)
    source_name = str((audit_payload.get("source") or {}).get("name") or dataset_id)
    if dataset_id.startswith("nhanes_"):
        return {
            "dataset_policy_class": "complex_survey_design_available_not_applied",
            "sampling_frame_policy": "NHANES 2017-2018 MEC exam benchmark rows used by the current runner.",
            "current_estimand_policy": "unweighted_method_engineering_diagnostic_only",
            "required_weight_columns_for_population_claim": columns
            or ["WTMEC2YR", "SDMVSTRA", "SDMVPSU"],
            "variance_policy_for_population_claim": (
                "Population inference requires MEC exam weights, strata, and PSU "
                "handling in coverage, width, group-gap, and uncertainty metrics."
            ),
            "claim_blocker": (
                "Current NHANES rows remain unweighted method-engineering "
                "diagnostics; they cannot support population-weighted health, "
                "clinical, disparity, or protected-class fairness conclusions."
            ),
            "source_name": source_name,
        }
    if dataset_id == "stackoverflow_2025_compensation":
        return {
            "dataset_policy_class": "self_selected_survey_no_design_weights",
            "sampling_frame_policy": "Respondent sample from the Stack Overflow Developer Survey archive.",
            "current_estimand_policy": "unweighted_respondent_sample_diagnostic_only",
            "required_weight_columns_for_population_claim": [],
            "variance_policy_for_population_claim": (
                "A developer-population claim would require a declared target "
                "population plus external calibration, post-stratification, or "
                "survey-weight construction that is absent from the current runner."
            ),
            "claim_blocker": (
                "Current Stack Overflow rows are self-selected respondent-sample "
                "diagnostics, not population compensation or wage-gap evidence."
            ),
            "source_name": source_name,
        }
    if dataset_id == "uci_wine_quality":
        return {
            "dataset_policy_class": "nonhuman_product_benchmark_no_protected_class",
            "sampling_frame_policy": "UCI wine-quality product rows used as interval-calibration benchmark data.",
            "current_estimand_policy": "unweighted_product_sample_diagnostic_only",
            "required_weight_columns_for_population_claim": [],
            "variance_policy_for_population_claim": (
                "Protected-class fairness is not a coherent claim for the current "
                "wine-color diagnostic grouping; any product-stratum claim would "
                "need a separate product sampling-frame protocol."
            ),
            "claim_blocker": (
                "Current wine-color rows are product benchmark diagnostics, not "
                "protected-class or population fairness evidence."
            ),
            "source_name": source_name,
        }
    if dataset_id == "openml_analcatdata_chlamydia":
        return {
            "dataset_policy_class": "published_count_table_no_design_weights",
            "sampling_frame_policy": "OpenML StatLib count table cells as published benchmark rows.",
            "current_estimand_policy": "unweighted_table_cell_diagnostic_only",
            "required_weight_columns_for_population_claim": [],
            "variance_policy_for_population_claim": (
                "A population or protected-group claim would require source "
                "denominators, exposure/universe definitions, and sampling design "
                "metadata not present in the current OpenML artifact."
            ),
            "claim_blocker": (
                "Current count-table diagnostics do not support population, "
                "clinical, policy, or protected-class fairness conclusions."
            ),
            "source_name": source_name,
        }
    return {
        "dataset_policy_class": "unweighted_benchmark_no_population_claim",
        "sampling_frame_policy": "Current benchmark rows as loaded by the regression runner.",
        "current_estimand_policy": "unweighted_method_engineering_diagnostic_only",
        "required_weight_columns_for_population_claim": columns,
        "variance_policy_for_population_claim": (
            "Population inference requires an explicit sampling frame, weight "
            "policy, and uncertainty estimator before claim promotion."
        ),
        "claim_blocker": "Current rows are diagnostic benchmark evidence only.",
        "source_name": source_name,
    }


def bundle_policy_row(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    dataset_id = str(row.get("dataset_id") or "")
    bundle_id = str(row.get("bundle_id") or "")
    audit_payload = dataset_audit_payload(root, dataset_id)
    policy = dataset_policy(dataset_id, audit_payload)
    survey_columns = policy["required_weight_columns_for_population_claim"]
    policy_id = f"sampling_weight_policy:{bundle_id}"
    return {
        "bundle_id": bundle_id,
        "dataset_id": dataset_id,
        "target": row.get("target"),
        "target_transform": row.get("target_transform"),
        "diagnostic_group": row.get("diagnostic_group"),
        "group_source_column": row.get("group_source_column") or row.get("diagnostic_group"),
        "policy_id": policy_id,
        "policy_status": "declared_diagnostic_only",
        "sampling_weight_policy_declared": True,
        "weighted_estimand_applied": False,
        "current_estimand_policy": policy["current_estimand_policy"],
        "dataset_policy_class": policy["dataset_policy_class"],
        "sampling_frame_policy": policy["sampling_frame_policy"],
        "required_weight_columns_for_population_claim": survey_columns,
        "survey_design_columns_available": survey_columns,
        "variance_policy_for_population_claim": policy[
            "variance_policy_for_population_claim"
        ],
        "claim_blocker": policy["claim_blocker"],
        "claim_effect": "policy_declared_no_population_fairness_claim",
        "source_name": policy["source_name"],
        "source_artifacts": [
            rel(root / BUNDLE_INDEX, root),
            rel(root / AUDIT_ROOT / dataset_id / "audit.json", root),
            rel(root / AUDIT_ROOT / dataset_id / "profile.json", root),
        ],
    }


def build_payload(root: Path) -> dict[str, Any]:
    bundle_index = read_json(root / BUNDLE_INDEX)
    protocol_design = read_json(root / PAPER_GATE_PROTOCOL_DESIGN_BUNDLE)
    bundles = [
        row
        for row in bundle_index.get("bundles", []) or []
        if isinstance(row, dict) and row.get("diagnostic_group")
    ]
    rows = [bundle_policy_row(root, row) for row in bundles]
    policy_counts = Counter(row["current_estimand_policy"] for row in rows)
    dataset_policy_counts = Counter(row["dataset_policy_class"] for row in rows)
    dataset_ids = sorted({row["dataset_id"] for row in rows})
    survey_required_rows = [
        row for row in rows if row["required_weight_columns_for_population_claim"]
    ]
    weighted_rows = [row for row in rows if row["weighted_estimand_applied"]]

    completed_action_ids = {
        str(row.get("action_id"))
        for row in protocol_design.get("protocol_design_rows", []) or []
        if isinstance(row, dict) and row.get("status") == "protocol_design_complete"
    }
    upstream_complete = (
        "fairness_population_inference_gate.define_population_and_protected_scope"
        in completed_action_ids
    )
    failed_checks: list[dict[str, Any]] = []
    if not upstream_complete:
        failed_checks.append(
            {
                "check_id": "population_and_protected_scope_protocol_complete",
                "status": "fail",
            }
        )
    if not rows:
        failed_checks.append(
            {"check_id": "diagnostic_group_bundle_policies_present", "status": "fail"}
        )
    if not all(row["sampling_weight_policy_declared"] for row in rows):
        failed_checks.append(
            {"check_id": "all_bundle_rows_have_sampling_weight_policy", "status": "fail"}
        )
    if weighted_rows:
        failed_checks.append(
            {
                "check_id": "no_weighted_estimand_applied_without_population_claim",
                "status": "fail",
                "weighted_bundle_ids": [row["bundle_id"] for row in weighted_rows],
            }
        )

    overall_status = (
        "fairness_sampling_weight_policy_failed"
        if failed_checks
        else "fairness_sampling_weight_policy_defined_no_fairness_claim"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "action_id": ACTION_ID,
            "gate_id": GATE_ID,
            "action_status": "protocol_design_complete"
            if not failed_checks
            else "incomplete",
            "claim_promoted_action_count": 0,
            "failed_check_count": len(failed_checks),
            "candidate_bundle_count": len(rows),
            "dataset_count": len(dataset_ids),
            "policy_declared_bundle_count": sum(
                1 for row in rows if row["sampling_weight_policy_declared"]
            ),
            "weighted_estimand_applied_bundle_count": len(weighted_rows),
            "unweighted_diagnostic_only_bundle_count": len(rows) - len(weighted_rows),
            "population_fairness_ready_bundle_count": 0,
            "survey_design_required_before_population_claim_bundle_count": len(
                survey_required_rows
            ),
            "dataset_policy_counts": dict(sorted(dataset_policy_counts.items())),
            "current_estimand_policy_counts": dict(sorted(policy_counts.items())),
            "dataset_ids": dataset_ids,
        },
        "completed_action_ids": [ACTION_ID] if not failed_checks else [],
        "claim_boundaries": [
            "This policy declares sampling and weighting contracts only; it does not promote a fairness claim.",
            "All current candidate bundles remain unweighted diagnostic evidence.",
            "Weighted and unweighted estimands cannot be mixed in one population fairness claim.",
            "Population, protected-class, legal, policy, clinical, and causal fairness language remains blocked until the downstream group-count, missingness, gap-uncertainty, and multiplicity audits pass.",
        ],
        "acceptance_criteria": [
            "Every diagnostic-group manuscript bundle has an explicit sampling-weight policy row.",
            "No current bundle applies a weighted population estimand.",
            "NHANES rows record MEC survey-design requirements before any population claim.",
            "The downstream group-count and group-gap audit can consume a single declared estimand policy per bundle.",
        ],
        "failed_checks": failed_checks,
        "bundle_policy_rows": rows,
        "sources": {
            "manuscript_bundle_index": rel(root / BUNDLE_INDEX, root),
            "paper_gate_protocol_design_bundle": rel(
                root / PAPER_GATE_PROTOCOL_DESIGN_BUNDLE, root
            ),
            "fairness_population_readiness": rel(
                root / FAIRNESS_POPULATION_READINESS, root
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Fairness Sampling Weight Policy",
        "",
        "This artifact completes the sampling/weighting policy action for the fairness population gate. It does not promote a fairness claim.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Action: `{summary['action_id']}`",
        f"- Candidate bundles: {summary['candidate_bundle_count']}",
        f"- Policy-declared bundles: {summary['policy_declared_bundle_count']}",
        f"- Weighted estimands applied: {summary['weighted_estimand_applied_bundle_count']}",
        f"- Population-fairness-ready bundles: {summary['population_fairness_ready_bundle_count']}",
        f"- Dataset policy counts: `{summary['dataset_policy_counts']}`",
        "",
        "## Bundle Policies",
        "",
        "| Bundle | Dataset | Group | Current Estimand | Dataset Policy | Population Claim Requirement |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["bundle_policy_rows"]:
        requirement = row["variance_policy_for_population_claim"].replace("|", "/")
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['bundle_id']}`",
                    f"`{row['dataset_id']}`",
                    f"`{row['diagnostic_group']}`",
                    f"`{row['current_estimand_policy']}`",
                    f"`{row['dataset_policy_class']}`",
                    requirement,
                ]
            )
            + " |"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "out": rel(out, root),
                "failed_checks": payload["failed_checks"],
            },
            sort_keys=True,
        )
    )
    return 0 if not payload["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
