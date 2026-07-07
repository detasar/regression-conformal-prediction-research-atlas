"""Audit duplicate-sensitivity closure without promoting final claims.

This audit sits between the remediation backlog and publication claim gates. It
checks that duplicate-signature caveats are covered by explicit sensitivity
evidence, while keeping final method-selection, fairness, bounded-support, and
Venn-Abers validation claims blocked.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_duplicate_sensitivity_closure_audit_v2"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "duplicate_sensitivity_closure_audit.json"

CROSS_RUN = REPORT_DIR / "cross_run_integrity_audit.json"
DUPLICATE_SPLIT_BACKLOG = REPORT_DIR / "duplicate_split_caveat_backlog.json"
PAIRED_DUPLICATE_AUDIT = REPORT_DIR / "paired_duplicate_sensitivity_audit.json"
REMEDIATION_BACKLOG = REPORT_DIR / "integrity_remediation_backlog.json"
FINAL_SELECTION_AUDIT = REPORT_DIR / "final_selection_claim_boundary_audit.json"
PUBLICATION_AUDIT = REPORT_DIR / "publication_methodology_audit.json"
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")

DUPLICATE_ISSUES = {
    "duplicate_signature_cross_split_caveat",
    "model_visible_signature_cross_split_caveat",
}
TRACKED_DIAGNOSTIC_CAVEAT_STATUS = "tracked_diagnostic_caveat"
TRACKED_CAVEAT_STATUSES = {
    "tracked_methodology_caveat",
    TRACKED_DIAGNOSTIC_CAVEAT_STATUS,
}
FINAL_CLAIM_ID = "final_selection_and_fairness_claims_blocked"
FINAL_BLOCKED_REQUIREMENTS = {
    "final_method_model_selection_gate",
    "multiplicity_selection_record",
    "dataset_specific_final_gates",
    "endpoint_bounded_support_gate",
    "fairness_population_inference_gate",
    "venn_abers_regression_validation_gate",
}
FINAL_SUPPORT_FLAGS = (
    "can_support_final_method_selection",
    "can_support_publication_ready_fairness",
    "can_support_bounded_support_validity",
    "can_support_venn_abers_regression_validation",
)
SENSITIVITY_PATH_FIELDS = (
    "comparison_path",
    "endpoint_audit_path",
    "experiment_notes_path",
    "feature_leakage_audit_path",
    "split_profile_path",
)

CLAIM_BOUNDARIES = [
    "This audit closes or scopes duplicate-signature caveats; it is not a model-performance result.",
    "Duplicate-signature and model-visible duplicate caveats are not hard leakage unless row-id or split-group overlap is detected.",
    "A closed duplicate-sensitivity backlog does not select a final conformal method, model, or dataset result.",
    "Dataset-level robustness evidence remains scoped to split-methodology sensitivity and must not be rewritten as fairness, policy, causal, production, bounded-support, or Venn-Abers regression validation evidence.",
]


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


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def caveat_issue_counts_from_cross_rows(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for caveat in as_list(row.get("caveats")):
            if caveat in DUPLICATE_ISSUES:
                counts[str(caveat)] += 1
    return counts


def duplicate_cross_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if set(str(item) for item in as_list(row.get("caveats"))).intersection(
            DUPLICATE_ISSUES
        )
    ]


def sensitivity_artifact_failures(
    rows: list[dict[str, Any]],
    root: Path,
) -> list[dict[str, Any]]:
    failures = []
    for row in rows:
        evidence_rows = as_list(row.get("sensitivity_evidence"))
        if not evidence_rows:
            failures.append(
                {
                    "report_id": row.get("report_id"),
                    "issue_type": row.get("issue_type"),
                    "reason": "missing_sensitivity_evidence",
                }
            )
            continue
        for index, evidence in enumerate(evidence_rows):
            if not isinstance(evidence, dict):
                failures.append(
                    {
                        "report_id": row.get("report_id"),
                        "issue_type": row.get("issue_type"),
                        "evidence_index": index,
                        "reason": "malformed_sensitivity_evidence",
                    }
                )
                continue
            missing_paths = [
                str(evidence.get(field))
                for field in SENSITIVITY_PATH_FIELDS
                if not evidence.get(field) or not resolve(root, str(evidence[field])).exists()
            ]
            reasons = []
            if safe_int(evidence.get("paired_rows")) <= 0:
                reasons.append("paired_rows_not_positive")
            if safe_int(evidence.get("seed_imbalanced_paired_rows")) != 0:
                reasons.append("seed_imbalanced_paired_rows_nonzero")
            if evidence.get("offending_seed_coverage_complete") is not True:
                reasons.append("offending_seed_coverage_incomplete")
            if safe_int(evidence.get("feature_leakage_violations_count")) != 0:
                reasons.append("feature_leakage_violation_in_sensitivity")
            if missing_paths:
                reasons.append("missing_sensitivity_artifact_paths")
            if reasons:
                failures.append(
                    {
                        "report_id": row.get("report_id"),
                        "issue_type": row.get("issue_type"),
                        "evidence_index": index,
                        "reasons": reasons,
                        "missing_paths": missing_paths,
                    }
                )
    return failures


def duplicate_cross_row_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = []
    for row in rows:
        split = row.get("split_profile") or {}
        endpoint = row.get("endpoint_audit") or {}
        feature = row.get("feature_leakage_audit") or {}
        reasons = []
        if not split.get("present"):
            reasons.append("missing_split_profile")
        if split.get("schema") != "cpfi_regression_split_profile_v2":
            reasons.append("split_profile_not_v2")
        if safe_int(split.get("row_id_overlap_violations")) != 0:
            reasons.append("row_id_overlap_violation")
        if safe_int(split.get("split_group_overlap_violations")) != 0:
            reasons.append("split_group_overlap_violation")
        if not endpoint.get("present"):
            reasons.append("missing_endpoint_audit")
        if not feature.get("present"):
            reasons.append("missing_feature_leakage_audit")
        if safe_int(feature.get("violations_count")) != 0:
            reasons.append("feature_leakage_violation")
        if reasons:
            failures.append(
                {
                    "report_id": row.get("report_id"),
                    "report_name": row.get("report_name"),
                    "caveats": [
                        value
                        for value in as_list(row.get("caveats"))
                        if value in DUPLICATE_ISSUES
                    ],
                    "reasons": reasons,
                }
            )
    return failures


def issue_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(row.get("issue_type")) for row in rows if row.get("issue_type"))


def final_claim(claim_register: dict[str, Any]) -> dict[str, Any]:
    for claim in as_list(claim_register.get("claims")):
        if isinstance(claim, dict) and claim.get("claim_id") == FINAL_CLAIM_ID:
            return claim
    return {}


def dataset_robustness_claims(claim_register: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        claim
        for claim in as_list(claim_register.get("claims"))
        if isinstance(claim, dict) and claim.get("claim_type") == "dataset_robustness_gate"
    ]


def requirement_statuses(claim: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("requirement_id")): str(item.get("status"))
        for item in as_list(claim.get("requirements"))
        if isinstance(item, dict) and item.get("requirement_id")
    }


def bundle_scope_failures(bundles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = []
    for bundle in bundles:
        evidence_role = str(bundle.get("evidence_role") or "")
        is_diagnostic_candidate = evidence_role == "main_result_candidate_diagnostic"
        text = " ".join(
            [
                str(bundle.get("claim_scope") or ""),
                " ".join(str(item) for item in as_list(bundle.get("promotion_blockers"))),
            ]
        ).lower()
        reasons = []
        if evidence_role != "robustness" and not is_diagnostic_candidate:
            reasons.append("evidence_role_not_robustness")
        if "caveat" not in str(bundle.get("status") or "").lower():
            reasons.append("status_does_not_record_caveats")
        if not bundle.get("claim_scope"):
            reasons.append("missing_claim_scope")
        if not as_list(bundle.get("promotion_blockers")):
            reasons.append("missing_promotion_blockers")
        if "final" not in text or "no " not in text:
            reasons.append("missing_final_nonclaim_language")
        if not any(token in text for token in ("fairness", "bounded", "venn-abers")):
            reasons.append("missing_broad_nonclaim_language")
        if reasons:
            failures.append({"bundle_id": bundle.get("bundle_id"), "reasons": reasons})
    return failures


def check(
    check_id: str,
    *,
    passed: bool,
    family: str,
    severity: str,
    evidence: dict[str, Any],
    fail_message: str,
    pass_message: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "family": family,
        "status": "pass" if passed else "fail",
        "severity": "none" if passed else severity,
        "message": pass_message if passed else fail_message,
        "evidence": evidence,
    }


def scoped_caveat(check_id: str, family: str, evidence: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "family": family,
        "status": "scoped_caveat",
        "severity": "low",
        "message": message,
        "evidence": evidence,
    }


def compact_action_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for row in rows:
        evidence_rows = [
            item for item in as_list(row.get("sensitivity_evidence")) if isinstance(item, dict)
        ]
        paired_rows = sum(safe_int(item.get("paired_rows")) for item in evidence_rows)
        nominal_changes = sum(
            safe_int(item.get("nominal_status_change_count")) for item in evidence_rows
        )
        coverage_delta_max_values = [
            float((item.get("coverage_delta_abs") or {}).get("max"))
            for item in evidence_rows
            if isinstance(item.get("coverage_delta_abs"), dict)
            and (item.get("coverage_delta_abs") or {}).get("max") is not None
        ]
        compact.append(
            {
                "action_id": row.get("action_id"),
                "report_id": row.get("report_id"),
                "report_name": row.get("report_name"),
                "issue_type": row.get("issue_type"),
                "status": row.get("status"),
                "dataset_ids": as_list(row.get("dataset_ids")),
                "config_path": row.get("config_path"),
                "sensitivity_evidence_count": len(evidence_rows),
                "paired_rows": paired_rows,
                "nominal_status_change_count": nominal_changes,
                "max_coverage_delta_abs": max(coverage_delta_max_values)
                if coverage_delta_max_values
                else None,
            }
        )
    return compact


def build_payload(root: Path) -> dict[str, Any]:
    cross = read_json(root / CROSS_RUN)
    duplicate_split = read_json(root / DUPLICATE_SPLIT_BACKLOG)
    paired = read_json(root / PAIRED_DUPLICATE_AUDIT)
    backlog = read_json(root / REMEDIATION_BACKLOG)
    final_selection = read_json(root / FINAL_SELECTION_AUDIT)
    publication = read_json(root / PUBLICATION_AUDIT)
    claim_register = read_json(root / CLAIM_REGISTER)
    bundle_index = read_json(root / BUNDLE_INDEX)

    cross_summary = cross.get("summary") or {}
    duplicate_split_summary = duplicate_split.get("summary") or {}
    paired_summary = paired.get("summary") or {}
    backlog_summary = backlog.get("summary") or {}
    final_selection_summary = final_selection.get("summary") or {}
    publication_summary = publication.get("summary") or {}
    bundle_summary = bundle_index.get("bundle_summary") or {}
    bundles = [item for item in as_list(bundle_index.get("bundles")) if isinstance(item, dict)]
    backlog_rows = [item for item in as_list(backlog.get("rows")) if isinstance(item, dict)]
    cross_rows = [item for item in as_list(cross.get("rows")) if isinstance(item, dict)]
    duplicate_rows = duplicate_cross_rows(cross_rows)
    cross_issue_counts = caveat_issue_counts_from_cross_rows(cross_rows)
    backlog_issue_counts = issue_counts(backlog_rows)
    final = final_claim(claim_register)
    final_requirements = requirement_statuses(final)
    dataset_claims = dataset_robustness_claims(claim_register)

    duplicate_backlog_rows = [
        row for row in backlog_rows if str(row.get("issue_type")) in DUPLICATE_ISSUES
    ]
    duplicate_action_count = len(duplicate_backlog_rows)
    duplicate_open_action_count = sum(
        1 for row in duplicate_backlog_rows if row.get("status") == "open"
    )
    duplicate_covered_action_count = sum(
        1
        for row in duplicate_backlog_rows
        if row.get("status") == "covered_by_sensitivity"
    )
    duplicate_tracked_diagnostic_count = sum(
        1
        for row in duplicate_backlog_rows
        if row.get("status") == TRACKED_DIAGNOSTIC_CAVEAT_STATUS
    )
    covered_action_rows = [
        row
        for row in duplicate_backlog_rows
        if row.get("status") == "covered_by_sensitivity"
    ]
    tracked_caveat_rows = [
        row
        for row in backlog_rows
        if row.get("status") in TRACKED_CAVEAT_STATUSES
    ]
    duplicate_status_counts = Counter(
        str(row.get("status")) for row in duplicate_backlog_rows
    )
    covered_action_status_counts = Counter(
        str(row.get("status")) for row in covered_action_rows
    )
    tracked_caveat_status_counts = Counter(
        str(row.get("status")) for row in tracked_caveat_rows
    )
    tracked_methodology_caveat_count = tracked_caveat_status_counts.get(
        "tracked_methodology_caveat", 0
    )
    covered_action_ids = {str(row.get("action_id")) for row in covered_action_rows}
    tracked_caveat_action_ids = {str(row.get("action_id")) for row in tracked_caveat_rows}
    covered_action_contract_leaks = sorted(
        covered_action_ids.intersection(tracked_caveat_action_ids)
    )
    expected_counts = {
        key: safe_int((cross_summary.get("caveat_counts") or {}).get(key))
        for key in sorted(DUPLICATE_ISSUES)
    }
    actual_cross_counts = {key: cross_issue_counts.get(key, 0) for key in sorted(DUPLICATE_ISSUES)}
    actual_backlog_counts = {
        key: backlog_issue_counts.get(key, 0) for key in sorted(DUPLICATE_ISSUES)
    }

    cross_failures = duplicate_cross_row_failures(duplicate_rows)
    evidence_failures = sensitivity_artifact_failures(covered_action_rows, root)
    bundle_failures = bundle_scope_failures(bundles)
    dataset_claim_failures = [
        {
            "claim_id": claim.get("claim_id"),
            "status": claim.get("status"),
        }
        for claim in dataset_claims
        if claim.get("status") != "robustness_evidence_gate_passed_with_caveats"
    ]
    final_missing_blocked = sorted(
        requirement_id
        for requirement_id in FINAL_BLOCKED_REQUIREMENTS
        if final_requirements.get(requirement_id) != "blocked"
    )
    publication_support_leaks = {
        key: publication_summary.get(key)
        for key in FINAL_SUPPORT_FLAGS
        if publication_summary.get(key) is not False
    }

    checks = [
        check(
            "cross_run_duplicate_counts_match_backlog",
            passed=actual_cross_counts == expected_counts
            and actual_backlog_counts == expected_counts
            and backlog_summary.get("issue_counts_match_cross_run") is True,
            family="count_reconciliation",
            severity="high",
            evidence={
                "expected_counts": expected_counts,
                "cross_issue_counts": actual_cross_counts,
                "backlog_issue_counts": actual_backlog_counts,
                "issue_counts_match_cross_run": backlog_summary.get(
                    "issue_counts_match_cross_run"
                ),
            },
            fail_message="Duplicate caveat counts disagree across cross-run, backlog, and expected summary counts.",
            pass_message="Duplicate caveat counts agree across cross-run, backlog, and expected summary counts.",
        ),
        check(
            "duplicate_rows_have_no_hard_split_or_feature_leakage",
            passed=not cross_failures,
            family="leakage",
            severity="high",
            evidence={
                "duplicate_cross_run_row_count": len(duplicate_rows),
                "failure_count": len(cross_failures),
                "failures": cross_failures[:12],
            },
            fail_message="A duplicate-caveated row has row-id/split-group overlap, missing sidecar, or feature-leakage violation.",
            pass_message="Duplicate-caveated rows have v2 split profiles, zero row-id/split-group overlaps, endpoint sidecars, and clean feature-leakage sidecars.",
        ),
        check(
            "all_duplicate_actions_are_covered_by_sensitivity",
            passed=(
                duplicate_action_count == sum(expected_counts.values())
                and duplicate_open_action_count == 0
                and (
                    duplicate_covered_action_count
                    + duplicate_tracked_diagnostic_count
                )
                == duplicate_action_count
                and set(duplicate_status_counts.keys())
                <= {"covered_by_sensitivity", TRACKED_DIAGNOSTIC_CAVEAT_STATUS}
                and duplicate_action_count > 0
            ),
            family="remediation_backlog",
            severity="high",
            evidence={
                "action_count": backlog_summary.get("action_count"),
                "duplicate_action_count": duplicate_action_count,
                "duplicate_open_action_count": duplicate_open_action_count,
                "duplicate_covered_action_count": duplicate_covered_action_count,
                "duplicate_tracked_diagnostic_count": duplicate_tracked_diagnostic_count,
                "open_action_count_total": backlog_summary.get("open_action_count"),
                "covered_action_count_total": backlog_summary.get(
                    "covered_action_count"
                ),
                "status_counts": backlog_summary.get("status_counts", {}),
                "duplicate_status_counts": dict(sorted(duplicate_status_counts.items())),
            },
            fail_message="At least one duplicate remediation action is open, not sensitivity-covered, or not explicitly scoped as diagnostic.",
            pass_message="Duplicate remediation actions are sensitivity-covered or explicitly scoped diagnostic caveats with zero open actions.",
        ),
        check(
            "covered_actions_output_contract_is_strict",
            passed=(
                len(covered_action_rows) == duplicate_covered_action_count
                and set(covered_action_status_counts.keys())
                <= {"covered_by_sensitivity"}
                and not covered_action_contract_leaks
            ),
            family="output_contract",
            severity="high",
            evidence={
                "covered_action_count": duplicate_covered_action_count,
                "covered_actions_payload_count": len(covered_action_rows),
                "covered_action_status_counts": dict(
                    sorted(covered_action_status_counts.items())
                ),
                "tracked_caveat_action_count": len(tracked_caveat_rows),
                "tracked_methodology_caveat_action_count": (
                    tracked_methodology_caveat_count
                ),
                "tracked_diagnostic_caveat_action_count": (
                    duplicate_tracked_diagnostic_count
                ),
                "tracked_caveat_status_counts": dict(
                    sorted(tracked_caveat_status_counts.items())
                ),
                "covered_tracked_action_id_overlap_count": len(
                    covered_action_contract_leaks
                ),
                "covered_tracked_action_id_overlap_sample": (
                    covered_action_contract_leaks[:12]
                ),
            },
            fail_message="The covered_actions payload mixes sensitivity-covered rows with tracked caveats.",
            pass_message="The covered_actions payload is restricted to sensitivity-covered actions; tracked caveats are emitted separately.",
        ),
        check(
            "sensitivity_evidence_artifacts_are_complete_and_clean",
            passed=not evidence_failures,
            family="sensitivity_evidence",
            severity="high",
            evidence={
                "failure_count": len(evidence_failures),
                "failures": evidence_failures[:12],
            },
            fail_message="Sensitivity evidence is missing, imbalanced, incomplete, path-broken, or has feature-leakage violations.",
            pass_message="Sensitivity-covered rows have paired rows, complete offending-seed coverage, balanced pairs, clean feature-leakage status, and existing sidecar paths.",
        ),
        check(
            "paired_raw_dedup_audit_is_available",
            passed=(
                safe_int(paired_summary.get("paired_dataset_count")) >= 3
                and safe_int(paired_summary.get("paired_comparison_rows")) > 0
                and safe_int(paired_summary.get("raw_only_rows")) == 0
                and safe_int(paired_summary.get("dedup_only_rows")) == 0
            ),
            family="paired_sensitivity",
            severity="medium",
            evidence=paired_summary,
            fail_message="Paired raw-vs-deduplicated duplicate-sensitivity audit is incomplete or unmatched.",
            pass_message="Paired raw-vs-deduplicated duplicate-sensitivity audit is present with matched rows.",
        ),
        check(
            "duplicate_split_backlog_has_no_hard_overlap_violations",
            passed=(
                safe_int(duplicate_split_summary.get("malformed_split_profile_count")) == 0
                and safe_int(
                    duplicate_split_summary.get("row_id_overlap_violation_seed_profiles")
                )
                == 0
                and safe_int(
                    duplicate_split_summary.get("split_group_overlap_violation_seed_profiles")
                )
                == 0
            ),
            family="split_profile",
            severity="high",
            evidence=duplicate_split_summary,
            fail_message="Duplicate split caveat backlog contains malformed split profiles or hard overlap violations.",
            pass_message="Duplicate split caveat backlog has zero malformed split profiles and zero hard row-id/split-group overlap violations.",
        ),
        check(
            "bundle_index_keeps_duplicate_evidence_scoped",
            passed=(
                safe_int(bundle_summary.get("manifest_count")) == len(bundles)
                and len(bundles) > 0
                and not bundle_failures
            ),
            family="claim_scope",
            severity="medium",
            evidence={
                "bundle_summary": bundle_summary,
                "bundle_failure_count": len(bundle_failures),
                "bundle_failures": bundle_failures,
            },
            fail_message="At least one manuscript bundle lacks robustness/caveat scope or nonclaim promotion blockers.",
            pass_message="Manuscript bundle index keeps duplicate evidence scoped as robustness evidence with promotion blockers.",
        ),
        check(
            "claim_register_keeps_dataset_evidence_as_robustness",
            passed=(len(dataset_claims) > 0 and not dataset_claim_failures),
            family="claim_scope",
            severity="medium",
            evidence={
                "dataset_robustness_claim_count": len(dataset_claims),
                "dataset_claim_failures": dataset_claim_failures,
            },
            fail_message="At least one dataset duplicate-sensitivity claim is promoted beyond scoped robustness evidence.",
            pass_message="Dataset duplicate-sensitivity claims remain scoped robustness evidence with caveats.",
        ),
        check(
            "final_selection_claims_remain_blocked",
            passed=(
                final.get("status") == "blocked"
                and not final_missing_blocked
                and final_selection_summary.get("overall_status") == "pass"
                and final_selection_summary.get("claim_status") == "blocked"
                and safe_int(final_selection_summary.get("blocked_requirement_count"))
                >= len(FINAL_BLOCKED_REQUIREMENTS)
            ),
            family="claim_scope",
            severity="high",
            evidence={
                "final_claim_status": final.get("status"),
                "final_selection_audit_summary": final_selection_summary,
                "missing_blocked_requirements": final_missing_blocked,
            },
            fail_message="Final-selection/fairness/bounded-support/Venn-Abers claim boundary is missing or promoted.",
            pass_message="Final-selection, fairness, bounded-support, production, and Venn-Abers validation claims remain blocked.",
        ),
        check(
            "publication_audit_does_not_promote_final_support",
            passed=(
                publication_summary.get("overall_status")
                in {"publication_workbench_ready", "publication_workbench_ready_with_caveats"}
                and safe_int(publication_summary.get("failed_check_count")) == 0
                and safe_int(publication_summary.get("open_remediation_actions")) == 0
                and not publication_support_leaks
            ),
            family="publication_scope",
            severity="high",
            evidence={
                "publication_summary": publication_summary,
                "publication_support_leaks": publication_support_leaks,
            },
            fail_message="Publication audit either failed, has open remediation, or promotes a broad final support flag.",
            pass_message="Publication audit remains workbench-ready with scoped caveats and no broad final-support flags.",
        ),
        scoped_caveat(
            "duplicate_caveats_remain_interpretation_scope",
            "claim_scope",
            {
                "duplicate_caveat_count": sum(expected_counts.values()),
                "row_signature_caveat_count": expected_counts.get(
                    "duplicate_signature_cross_split_caveat", 0
                ),
                "model_visible_caveat_count": expected_counts.get(
                    "model_visible_signature_cross_split_caveat", 0
                ),
            },
            "Duplicate caveats are closed by sensitivity evidence for current workbench scope, but remain interpretation caveats rather than final split-independence claims.",
        ),
        scoped_caveat(
            "final_claims_blocked_by_design",
            "publication_scope",
            {
                "blocked_requirement_count": final_selection_summary.get(
                    "blocked_requirement_count"
                ),
                "publication_overall_status": publication_summary.get("overall_status"),
            },
            "The workbench is suitable for robustness/methodology evidence, not final method selection or broad fairness/population claims.",
        ),
    ]

    check_counts = Counter(str(item["status"]) for item in checks)
    hard_failed_checks = [item for item in checks if item["status"] == "fail"]
    if hard_failed_checks:
        overall_status = "fail"
    elif check_counts.get("scoped_caveat"):
        overall_status = "scoped_duplicate_sensitivity_closure_pass_with_caveats"
    else:
        overall_status = "scoped_duplicate_sensitivity_closure_pass"

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "cross_run_integrity_audit": rel(root / CROSS_RUN, root),
            "duplicate_split_caveat_backlog": rel(root / DUPLICATE_SPLIT_BACKLOG, root),
            "paired_duplicate_sensitivity_audit": rel(root / PAIRED_DUPLICATE_AUDIT, root),
            "integrity_remediation_backlog": rel(root / REMEDIATION_BACKLOG, root),
            "final_selection_claim_boundary_audit": rel(root / FINAL_SELECTION_AUDIT, root),
            "publication_methodology_audit": rel(root / PUBLICATION_AUDIT, root),
            "manuscript_claim_register": rel(root / CLAIM_REGISTER, root),
            "manuscript_bundle_index": rel(root / BUNDLE_INDEX, root),
        },
        "summary": {
            "overall_status": overall_status,
            "duplicate_action_count": duplicate_action_count,
            "duplicate_caveat_count": sum(expected_counts.values()),
            "row_signature_caveat_count": expected_counts.get(
                "duplicate_signature_cross_split_caveat", 0
            ),
            "model_visible_caveat_count": expected_counts.get(
                "model_visible_signature_cross_split_caveat", 0
            ),
            "open_action_count": duplicate_open_action_count,
            "covered_action_count": duplicate_covered_action_count,
            "tracked_caveat_action_count": len(tracked_caveat_rows),
            "tracked_methodology_caveat_action_count": tracked_methodology_caveat_count,
            "tracked_diagnostic_caveat_action_count": duplicate_tracked_diagnostic_count,
            "backlog_open_action_count_total": backlog_summary.get("open_action_count"),
            "backlog_covered_action_count_total": backlog_summary.get(
                "covered_action_count"
            ),
            "covered_action_status_counts": dict(
                sorted(covered_action_status_counts.items())
            ),
            "tracked_caveat_status_counts": dict(
                sorted(tracked_caveat_status_counts.items())
            ),
            "hard_failed_check_count": len(hard_failed_checks),
            "scoped_caveat_check_count": check_counts.get("scoped_caveat", 0),
            "paired_dataset_count": paired_summary.get("paired_dataset_count"),
            "paired_comparison_rows": paired_summary.get("paired_comparison_rows"),
            "publication_manifest_count": bundle_summary.get("manifest_count"),
            "dataset_robustness_claim_count": len(dataset_claims),
            "final_blocked_requirement_count": final_selection_summary.get(
                "blocked_requirement_count"
            ),
            "can_support_final_method_selection": publication_summary.get(
                "can_support_final_method_selection"
            ),
            "can_support_publication_ready_fairness": publication_summary.get(
                "can_support_publication_ready_fairness"
            ),
            "can_support_bounded_support_validity": publication_summary.get(
                "can_support_bounded_support_validity"
            ),
            "can_support_venn_abers_regression_validation": publication_summary.get(
                "can_support_venn_abers_regression_validation"
            ),
            "check_status_counts": dict(sorted(check_counts.items())),
        },
        "checks": checks,
        "failed_checks": hard_failed_checks,
        "covered_actions": compact_action_rows(covered_action_rows),
        "tracked_caveat_actions": compact_action_rows(tracked_caveat_rows),
        "claim_boundaries": CLAIM_BOUNDARIES,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Duplicate Sensitivity Closure Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Duplicate actions: {summary['duplicate_action_count']}",
        f"- Duplicate caveats: {summary['duplicate_caveat_count']}",
        f"- Open actions: {summary['open_action_count']}",
        f"- Covered by sensitivity actions: {summary['covered_action_count']}",
        f"- Tracked caveat actions: {summary['tracked_caveat_action_count']}",
        f"- Tracked methodology caveat actions: {summary['tracked_methodology_caveat_action_count']}",
        f"- Tracked diagnostic caveat actions: {summary['tracked_diagnostic_caveat_action_count']}",
        f"- Hard failed checks: {summary['hard_failed_check_count']}",
        f"- Scoped caveat checks: {summary['scoped_caveat_check_count']}",
        f"- Paired raw/dedup datasets: {summary['paired_dataset_count']}",
        f"- Paired comparison rows: {summary['paired_comparison_rows']}",
        f"- Publication manifests: {summary['publication_manifest_count']}",
        f"- Dataset robustness claims: {summary['dataset_robustness_claim_count']}",
        f"- Final blocked requirements: {summary['final_blocked_requirement_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Severity |",
            "|---|---:|---:|",
        ]
    )
    for item in payload["checks"]:
        lines.append(
            f"| `{item['check_id']}` | `{item['status']}` | `{item['severity']}` |"
        )
    lines.extend(
        [
            "",
            "## Covered By Sensitivity Actions",
            "",
            "| Report | Issue | Paired Rows | Nominal Status Changes | Max Abs Coverage Delta |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for item in payload["covered_actions"]:
        max_delta = item["max_coverage_delta_abs"]
        max_delta_text = "" if max_delta is None else f"{max_delta:.6g}"
        lines.append(
            "| "
            f"`{item['report_name']}` | `{item['issue_type']}` | "
            f"{item['paired_rows']} | {item['nominal_status_change_count']} | "
            f"{max_delta_text} |"
        )
    lines.extend(
        [
            "",
            "## Tracked Methodology Caveat Actions",
            "",
            "| Report | Issue | Status |",
            "|---|---|---:|",
        ]
    )
    for item in payload["tracked_caveat_actions"]:
        lines.append(
            "| "
            f"`{item['report_name']}` | `{item['issue_type']}` | "
            f"`{item['status']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "hard_failed_check_count": payload["summary"]["hard_failed_check_count"],
                "scoped_caveat_check_count": payload["summary"][
                    "scoped_caveat_check_count"
                ],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
