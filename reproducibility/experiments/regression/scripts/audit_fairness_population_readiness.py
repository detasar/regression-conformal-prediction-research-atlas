"""Audit the fairness/population inference claim boundary.

Current regression CP artifacts contain group-stratified diagnostics, but those
diagnostics are not population-weighted protected-class fairness evidence. This
audit keeps that distinction executable for manuscript extraction.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_fairness_population_readiness_audit_v1"
DEFAULT_REPORT_DIR = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627"
)
DEFAULT_OUT = DEFAULT_REPORT_DIR / "fairness_population_readiness_audit.json"
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
CLAIM_REGISTER_MD = Path("experiments/regression/catalogs/manuscript_claim_register.md")
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
EVIDENCE_VIEW = Path("experiments/regression/manuscript/evidence_view.json")
FINAL_SELECTION = DEFAULT_REPORT_DIR / "final_selection_claim_boundary_audit.json"
SAMPLING_WEIGHT_POLICY = Path(
    "experiments/regression/manuscript/fairness_sampling_weight_policy.json"
)
FAIRNESS_GROUP_DIAGNOSTIC_AUDIT = (
    DEFAULT_REPORT_DIR / "fairness_group_diagnostic_audit.json"
)
FAIRNESS_GROUP_MULTIPLICITY_SCOPE = Path(
    "experiments/regression/manuscript/fairness_group_multiplicity_scope.json"
)
PROTOCOL = Path("experiments/regression/PUBLICATION_READINESS_PROTOCOL.md")
FINAL_CLAIM_ID = "final_selection_and_fairness_claims_blocked"
FAIRNESS_REQUIREMENT_ID = "fairness_population_inference_gate"


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


def text_join(values: list[Any]) -> str:
    return " ".join(str(value) for value in values if value is not None).lower()


def find_claim(claim_register: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for claim in claim_register.get("claims", []) or []:
        if isinstance(claim, dict) and claim.get("claim_id") == claim_id:
            return claim
    return {}


def requirement_status(claim: dict[str, Any], requirement_id: str) -> str | None:
    for row in claim.get("requirements", []) or []:
        if isinstance(row, dict) and row.get("requirement_id") == requirement_id:
            return str(row.get("status"))
    return None


def claim_mentions_fairness_boundary(claim: dict[str, Any]) -> bool:
    haystack = text_join(
        [
            claim.get("claim_id"),
            claim.get("claim_type"),
            claim.get("claim_text"),
            claim.get("scope"),
            *(claim.get("not_claiming") or []),
        ]
    )
    return any(token in haystack for token in ("fairness", "population", "protected"))


def sampling_policy_by_bundle(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("bundle_id")): row
        for row in payload.get("bundle_policy_rows", []) or []
        if isinstance(row, dict) and row.get("bundle_id")
    }


def group_diagnostic_by_bundle(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("bundle_id")): row
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and row.get("bundle_id")
    }


def multiplicity_scope_by_bundle(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("bundle_id")): row
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and row.get("bundle_id")
    }


def bundle_row(
    row: dict[str, Any],
    policy_by_bundle: dict[str, dict[str, Any]],
    diagnostic_by_bundle: dict[str, dict[str, Any]],
    multiplicity_by_bundle: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    blockers = [str(value) for value in row.get("promotion_blockers", []) or []]
    blocker_text = text_join(blockers)
    diagnostic_group = row.get("diagnostic_group")
    group_role = (
        "diagnostic_coverage_stratification" if diagnostic_group else "not_grouped"
    )
    bundle_id = str(row.get("bundle_id") or "")
    sampling_policy = policy_by_bundle.get(bundle_id, {})
    group_diagnostic = diagnostic_by_bundle.get(bundle_id, {})
    multiplicity_scope = multiplicity_by_bundle.get(bundle_id, {})
    multiplicity_scope_declared = bool(
        multiplicity_scope.get("multiplicity_scope_declared_for_group_comparisons")
    )
    weighting_policy = (
        row.get("sampling_weight_policy")
        or row.get("weighting_policy")
        or sampling_policy.get("current_estimand_policy")
    )
    protected_attribute_scope = row.get("protected_attribute_scope")
    population_estimand = row.get("population_estimand")
    fairness_estimand = row.get("fairness_estimand")
    group_counts = row.get("group_counts") or group_diagnostic.get("group_counts") or {}
    missing_group_rate = row.get("missing_group_rate")
    if missing_group_rate is None:
        missing_group_rate = group_diagnostic.get("group_missing_rate")
    coverage_by_group = (
        row.get("coverage_by_group") or group_diagnostic.get("coverage_by_group") or {}
    )
    width_by_group = row.get("width_by_group") or group_diagnostic.get("width_by_group") or {}
    group_coverage_gap = row.get("group_coverage_gap")
    if group_coverage_gap is None:
        group_coverage_gap = (
            group_diagnostic.get("coverage_gap_completed_run_summary") or {}
        ).get("mean")
    uncertainty_interval_for_gap = (
        row.get("uncertainty_interval_for_gap")
        or group_diagnostic.get("coverage_gap_repeated_seed_uncertainty")
        or group_diagnostic.get("transformed_target_mean_gap_ci95")
    )
    group_gap_uncertainty_recorded = bool(
        row.get("uncertainty_interval_for_gap")
        or group_diagnostic.get("group_gap_uncertainty_recorded")
    )
    missingness_by_group_audited = (
        row.get("missingness_by_group_audited") is True
        or group_diagnostic.get("missingness_by_group_audited") is True
    )
    missing_evidence = [
        "population_estimand_not_declared",
        "protected_attribute_scope_not_approved",
        "claim_register_fairness_gate_blocked",
    ]
    if not multiplicity_scope_declared:
        missing_evidence.append("multiplicity_scope_for_group_comparisons_not_declared")
    if not group_gap_uncertainty_recorded:
        missing_evidence.append("group_gap_uncertainty_not_recorded")
    if not missingness_by_group_audited:
        missing_evidence.append("missingness_by_group_not_audited")
    if weighting_policy:
        missing_evidence.append("sampling_weight_policy_declared_diagnostic_only")
    else:
        missing_evidence.append("sampling_or_weighting_policy_not_declared")
    return {
        "bundle_id": row.get("bundle_id"),
        "dataset_id": row.get("dataset_id"),
        "target": row.get("target"),
        "target_transform": row.get("target_transform"),
        "diagnostic_group": diagnostic_group,
        "group_source_column": row.get("group_source_column") or diagnostic_group,
        "group_role": group_role,
        "protected_attribute_status": (
            "not_approved_for_fairness_claim"
            if not protected_attribute_scope
            else "source_backed_scope_declared"
        ),
        "protected_attribute_scope": protected_attribute_scope,
        "population_universe": row.get("population_universe"),
        "sampling_frame": row.get("sampling_frame")
        or sampling_policy.get("sampling_frame_policy"),
        "weighting_policy": weighting_policy,
        "survey_design_columns": row.get("survey_design_columns")
        or sampling_policy.get("survey_design_columns_available")
        or [],
        "sampling_policy_id": sampling_policy.get("policy_id"),
        "sampling_policy_status": sampling_policy.get("policy_status"),
        "sampling_policy_claim_effect": sampling_policy.get("claim_effect"),
        "weighted_estimand_applied": bool(
            sampling_policy.get("weighted_estimand_applied")
        ),
        "fairness_estimand": fairness_estimand,
        "population_estimand": population_estimand,
        "metric_contract": row.get("metric_contract")
        or "coverage_width_diagnostic_only",
        "group_counts": group_counts,
        "min_group_count": row.get("min_group_count")
        or group_diagnostic.get("min_group_count"),
        "missing_group_rate": missing_group_rate,
        "coverage_by_group": coverage_by_group,
        "group_coverage_gap": group_coverage_gap,
        "width_by_group": width_by_group,
        "uncertainty_interval_for_gap": uncertainty_interval_for_gap,
        "feature_policy_for_group_or_proxy": row.get(
            "feature_policy_for_group_or_proxy"
        )
        or "not_audited_for_fairness_claim",
        "evidence_role": row.get("evidence_role"),
        "status": row.get("status"),
        "paper_table_candidate": row.get("paper_table_candidate"),
        "claim_scope": row.get("claim_scope"),
        "diagnostic_group_declared": bool(diagnostic_group),
        "diagnostic_group_use": (
            "coverage_stratification_diagnostic_only"
            if diagnostic_group
            else "not_declared"
        ),
        "population_estimand_declared": bool(population_estimand),
        "sampling_weight_policy_declared": bool(weighting_policy),
        "protected_attribute_scope_declared": bool(protected_attribute_scope),
        "fairness_estimand_declared": bool(fairness_estimand),
        "group_counts_recorded": bool(group_counts),
        "group_gap_uncertainty_recorded": group_gap_uncertainty_recorded,
        "missingness_by_group_audited": missingness_by_group_audited,
        "fairness_group_diagnostic_audit_status": group_diagnostic.get(
            "claim_effect"
        ),
        "multiplicity_scope_id": multiplicity_scope.get("comparison_family_id"),
        "multiplicity_policy": multiplicity_scope.get("multiplicity_policy"),
        "multiplicity_scope_declared_for_group_comparisons": (
            multiplicity_scope_declared
        ),
        "nonclaim_boundary_mentions_fairness": (
            "no population" in blocker_text or "fairness" in blocker_text
        ),
        "fairness_population_claim_status": "blocked_diagnostic_only_no_population_claim",
        "missing_evidence": missing_evidence,
        "promotion_blockers": blockers,
        "allowed_claim_language": [
            "diagnostic group-stratified coverage/width evidence within the scoped robustness bundle"
        ],
        "prohibited_claim_language": [
            "population fairness",
            "protected-class fairness",
            "legal or policy fairness conclusion",
            "clinical subgroup validity",
            "causal disparity conclusion",
        ],
        "source_artifacts": [
            row.get("manifest_path"),
            "experiments/regression/catalogs/manuscript_bundle_index.json",
            "experiments/regression/manuscript/evidence_view.json",
            "experiments/regression/reports/methodology_sanity_audit_20260627/fairness_group_diagnostic_audit.json",
            "experiments/regression/manuscript/fairness_group_multiplicity_scope.json",
        ],
    }


def build_payload(root: Path) -> dict[str, Any]:
    claim_register_path = root / CLAIM_REGISTER
    claim_register_md_path = root / CLAIM_REGISTER_MD
    bundle_index_path = root / BUNDLE_INDEX
    evidence_view_path = root / EVIDENCE_VIEW
    final_selection_path = root / FINAL_SELECTION
    sampling_policy_path = root / SAMPLING_WEIGHT_POLICY
    group_diagnostic_path = root / FAIRNESS_GROUP_DIAGNOSTIC_AUDIT
    multiplicity_scope_path = root / FAIRNESS_GROUP_MULTIPLICITY_SCOPE
    protocol_path = root / PROTOCOL

    claim_register = read_json(claim_register_path)
    bundle_index = read_json(bundle_index_path)
    evidence_view = read_json(evidence_view_path)
    final_selection = read_json(final_selection_path)
    sampling_policy = (
        read_json(sampling_policy_path) if sampling_policy_path.exists() else {}
    )
    group_diagnostic = (
        read_json(group_diagnostic_path) if group_diagnostic_path.exists() else {}
    )
    multiplicity_scope = (
        read_json(multiplicity_scope_path) if multiplicity_scope_path.exists() else {}
    )
    claim_register_md = claim_register_md_path.read_text(encoding="utf-8")
    protocol_text = protocol_path.read_text(encoding="utf-8")

    final_claim = find_claim(claim_register, FINAL_CLAIM_ID)
    fairness_requirement_status = requirement_status(
        final_claim, FAIRNESS_REQUIREMENT_ID
    )
    final_summary = final_selection.get("summary") or {}
    bundles = [
        row for row in bundle_index.get("bundles", []) or [] if isinstance(row, dict)
    ]
    policy_by_bundle = sampling_policy_by_bundle(sampling_policy)
    diagnostic_by_bundle = group_diagnostic_by_bundle(group_diagnostic)
    multiplicity_by_bundle = multiplicity_scope_by_bundle(multiplicity_scope)
    rows = [
        bundle_row(
            row, policy_by_bundle, diagnostic_by_bundle, multiplicity_by_bundle
        )
        for row in bundles
    ]
    evidence_rows = [
        row for row in evidence_view.get("rows", []) or [] if isinstance(row, dict)
    ]
    claims = [
        row for row in claim_register.get("claims", []) or [] if isinstance(row, dict)
    ]
    boundary_claims = [row for row in claims if claim_mentions_fairness_boundary(row)]

    ready_rows = [
        row
        for row in rows
        if row["population_estimand_declared"]
        and row["sampling_weight_policy_declared"]
        and row["protected_attribute_scope_declared"]
        and fairness_requirement_status == "pass"
    ]
    diagnostic_rows = [row for row in rows if row["diagnostic_group_declared"]]
    explicit_nonclaim_rows = [
        row for row in rows if row["nonclaim_boundary_mentions_fairness"]
    ]
    evidence_status_counts = Counter(
        str(row.get("status")) for row in evidence_rows if row.get("status")
    )
    bundle_status_counts = Counter(
        str(row.get("status")) for row in rows if row.get("status")
    )

    population_claim_rows = ready_rows
    checks = {
        "source_artifacts_present": all(
            path.exists()
            for path in (
                claim_register_path,
                claim_register_md_path,
                bundle_index_path,
                evidence_view_path,
                final_selection_path,
                protocol_path,
            )
        ),
        "sampling_weight_policy_artifact_absent_or_valid": (
            not sampling_policy_path.exists()
            or (sampling_policy.get("summary") or {}).get("overall_status")
            == "fairness_sampling_weight_policy_defined_no_fairness_claim"
        ),
        "fairness_group_diagnostic_artifact_absent_or_valid": (
            not group_diagnostic_path.exists()
            or (group_diagnostic.get("summary") or {}).get("overall_status")
            == "fairness_group_diagnostic_audit_completed_no_fairness_claim"
        ),
        "fairness_group_multiplicity_scope_artifact_absent_or_valid": (
            not multiplicity_scope_path.exists()
            or (multiplicity_scope.get("summary") or {}).get("overall_status")
            == "fairness_group_multiplicity_scope_declared_no_fairness_claim"
        ),
        "final_claim_present": bool(final_claim),
        "fairness_population_requirement_remains_blocked": (
            fairness_requirement_status == "blocked"
        ),
        "final_selection_claim_remains_blocked": (
            final_summary.get("claim_status") == "blocked"
        ),
        "all_rows_have_group_role": all(row["group_role"] for row in rows),
        "diagnostic_group_rows_are_identified": len(diagnostic_rows) > 0,
        "diagnostic_group_not_promoted_to_fairness": all(
            row["fairness_population_claim_status"]
            == "blocked_diagnostic_only_no_population_claim"
            for row in rows
        ),
        "diagnostic_rows_have_explicit_nonclaim_boundary": (
            len(diagnostic_rows) == len(explicit_nonclaim_rows)
        ),
        "protected_attribute_source_backed_when_claimed": all(
            row["protected_attribute_scope_declared"] for row in population_claim_rows
        ),
        "population_universe_declared_for_population_claim": all(
            bool(row["population_universe"]) for row in population_claim_rows
        ),
        "sampling_frame_declared": all(
            bool(row["sampling_frame"]) for row in population_claim_rows
        ),
        "weighting_policy_declared_and_applied_for_population_claim": all(
            row["sampling_weight_policy_declared"] for row in population_claim_rows
        ),
        "survey_design_available_or_population_blocked": (
            not population_claim_rows
            or all(bool(row["survey_design_columns"]) for row in population_claim_rows)
        ),
        "estimand_present_for_fairness_claim": all(
            row["fairness_estimand_declared"] and row["population_estimand_declared"]
            for row in population_claim_rows
        ),
        "group_counts_and_sparsity_thresholds_recorded": (
            not population_claim_rows
            or all(
                row["group_counts_recorded"] and row["min_group_count"]
                for row in population_claim_rows
            )
        ),
        "group_gap_uncertainty_recorded": (
            not population_claim_rows
            or all(
                row["group_gap_uncertainty_recorded"] for row in population_claim_rows
            )
        ),
        "sensitive_feature_and_proxy_policy_audited": (
            not population_claim_rows
            or all(
                row["feature_policy_for_group_or_proxy"]
                != "not_audited_for_fairness_claim"
                for row in population_claim_rows
            )
        ),
        "missingness_by_group_audited": (
            not population_claim_rows
            or all(row["missingness_by_group_audited"] for row in population_claim_rows)
        ),
        "multiplicity_scope_declared_for_group_comparisons": (
            not population_claim_rows
            or all(
                row["multiplicity_scope_declared_for_group_comparisons"]
                for row in population_claim_rows
            )
        ),
        "claim_register_alignment": bool(boundary_claims)
        and fairness_requirement_status == "blocked",
        "paper_language_scan_blocks_unapproved_fairness_population_terms": all(
            row["nonclaim_boundary_mentions_fairness"] for row in diagnostic_rows
        ),
        "audit_does_not_override_selection_endpoint_or_venn_abers_gates": (
            final_summary.get("claim_status") == "blocked"
        ),
        "no_bundle_ready_for_population_fairness_claim": len(ready_rows) == 0,
        "claim_register_contains_fairness_boundary_language": bool(boundary_claims),
        "protocol_and_claim_register_keep_population_language_bounded": (
            "fairness" in (protocol_text + "\n" + claim_register_md).lower()
            or "population" in (protocol_text + "\n" + claim_register_md).lower()
        ),
    }
    failed_checks = [key for key, value in checks.items() if not value]
    if failed_checks:
        overall_status = "fairness_population_readiness_audit_fail"
    else:
        overall_status = (
            "fairness_population_readiness_audit_completed_no_fairness_claim"
        )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "manuscript_claim_register": rel(claim_register_path, root),
            "manuscript_claim_register_markdown": rel(claim_register_md_path, root),
            "manuscript_bundle_index": rel(bundle_index_path, root),
            "manuscript_evidence_view": rel(evidence_view_path, root),
            "final_selection_claim_boundary": rel(final_selection_path, root),
            "fairness_sampling_weight_policy": rel(sampling_policy_path, root),
            "fairness_group_diagnostic_audit": rel(group_diagnostic_path, root),
            "fairness_group_multiplicity_scope": rel(
                multiplicity_scope_path, root
            ),
            "publication_readiness_protocol": rel(protocol_path, root),
        },
        "summary": {
            "overall_status": overall_status,
            "failed_check_count": len(failed_checks),
            "can_support_publication_ready_fairness": False,
            "fairness_population_claim_status": "blocked_diagnostic_only",
            "fairness_requirement_status": fairness_requirement_status,
            "final_selection_claim_status": final_summary.get("claim_status"),
            "bundle_count": len(rows),
            "diagnostic_group_bundle_count": len(diagnostic_rows),
            "explicit_nonclaim_boundary_bundle_count": len(explicit_nonclaim_rows),
            "population_estimand_declared_bundle_count": sum(
                1 for row in rows if row["population_estimand_declared"]
            ),
            "sampling_weight_policy_declared_bundle_count": sum(
                1 for row in rows if row["sampling_weight_policy_declared"]
            ),
            "sampling_weight_policy_artifact_status": (
                (sampling_policy.get("summary") or {}).get("overall_status")
            ),
            "weighted_estimand_applied_bundle_count": sum(
                1 for row in rows if row["weighted_estimand_applied"]
            ),
            "fairness_group_diagnostic_audit_status": (
                (group_diagnostic.get("summary") or {}).get("overall_status")
            ),
            "fairness_group_multiplicity_scope_status": (
                (multiplicity_scope.get("summary") or {}).get("overall_status")
            ),
            "multiplicity_scope_declared_bundle_count": sum(
                1
                for row in rows
                if row["multiplicity_scope_declared_for_group_comparisons"]
            ),
            "claim_register_cites_multiplicity_record": (
                (multiplicity_scope.get("summary") or {}).get(
                    "claim_register_cites_multiplicity_record"
                )
            ),
            "group_counts_recorded_bundle_count": sum(
                1 for row in rows if row["group_counts_recorded"]
            ),
            "missingness_by_group_audited_bundle_count": sum(
                1 for row in rows if row["missingness_by_group_audited"]
            ),
            "group_gap_uncertainty_recorded_bundle_count": sum(
                1 for row in rows if row["group_gap_uncertainty_recorded"]
            ),
            "coverage_by_group_recorded_bundle_count": sum(
                1 for row in rows if row["coverage_by_group"]
            ),
            "width_by_group_recorded_bundle_count": sum(
                1 for row in rows if row["width_by_group"]
            ),
            "protected_attribute_scope_declared_bundle_count": sum(
                1 for row in rows if row["protected_attribute_scope_declared"]
            ),
            "population_fairness_ready_bundle_count": len(ready_rows),
            "evidence_claim_count": len(evidence_rows),
            "fairness_boundary_claim_count": len(boundary_claims),
            "bundle_status_counts": dict(sorted(bundle_status_counts.items())),
            "evidence_status_counts": dict(sorted(evidence_status_counts.items())),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "rows": rows,
        "claim_boundaries": [
            "Group-stratified coverage rows are diagnostic evidence only.",
            "No protected-class, legal, policy, clinical, causal, or population fairness conclusion is supported by the current artifacts.",
            "A future fairness claim requires a declared population, protected group scope, estimand, sampling or weighting policy, and claim-register approval.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Fairness Population Readiness Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Fairness claim status: `{summary['fairness_population_claim_status']}`",
        f"- Fairness requirement status: `{summary['fairness_requirement_status']}`",
        f"- Diagnostic-group bundles: {summary['diagnostic_group_bundle_count']} / {summary['bundle_count']}",
        f"- Multiplicity-scope-declared bundles: {summary['multiplicity_scope_declared_bundle_count']} / {summary['bundle_count']}",
        f"- Claim register cites multiplicity record: `{summary['claim_register_cites_multiplicity_record']}`",
        f"- Population fairness ready bundles: {summary['population_fairness_ready_bundle_count']}",
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
    for check_id, passed in payload["checks"].items():
        lines.append(f"| `{check_id}` | `{passed}` |")
    lines.extend(
        [
            "",
            "## Bundle Rows",
            "",
            "| Bundle | Dataset | Diagnostic group | Claim status | Missing evidence |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        missing = ", ".join(f"`{item}`" for item in row["missing_evidence"])
        lines.append(
            "| "
            f"`{row['bundle_id']}` | "
            f"`{row['dataset_id']}` | "
            f"`{row['diagnostic_group']}` | "
            f"`{row['fairness_population_claim_status']}` | "
            f"{missing} |"
        )
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
