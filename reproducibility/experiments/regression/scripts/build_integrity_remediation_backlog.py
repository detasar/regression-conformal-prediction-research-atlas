"""Build an action backlog from the cross-run integrity audit.

The cross-run audit is a report-level status matrix. This script converts its
blocking issues and caveats into a deterministic remediation queue so the study
can retire methodology debt incrementally without losing provenance.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_integrity_remediation_backlog_v1"
DEFAULT_CROSS_RUN_AUDIT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "cross_run_integrity_audit.json"
)
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "integrity_remediation_backlog.json"
)

CLAIM_BOUNDARIES = [
    "This backlog is a methodology-debt queue, not new performance evidence.",
    "Open caveats do not imply confirmed data leakage unless the issue category is a hard blocking leakage issue.",
    "Rows marked as duplicate-signature caveats must not be described as row-id leakage without row-id overlap evidence.",
    "Plus-family duplicate-cluster internal-fold caveats are tracked methodology-scope limits, not completed duplicate-sensitivity failures.",
    "Legacy endpoint or split sidecars should not be treated as full current-schema closure.",
    "Closing a row requires regenerating the relevant sidecar/audit and then rebuilding cross-run integrity and methodology sanity artifacts.",
]

TRACKED_METHODOLOGY_CAVEATS = {
    "duplicate_cluster_plus_family_internal_fold_caveat",
}
TRACKED_DIAGNOSTIC_CAVEAT_STATUS = "tracked_diagnostic_caveat"
SENSITIVITY_COMPARISON_FILENAMES = (
    "sensitivity_comparison.json",
    "candidate_duplicate_sensitivity_comparison.json",
    "ordinary_vs_grouped_cv_comparison.json",
)

ISSUE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "failed_rows_present": {
        "severity": "high",
        "category": "pilot_summary_integrity",
        "next_action": "Inspect failed ledger rows and either fix the run or document controlled skip semantics.",
    },
    "row_id_overlap_detected": {
        "severity": "high",
        "category": "hard_split_leakage",
        "next_action": "Regenerate split profiles and block interpretation until row-id overlap is eliminated.",
    },
    "split_group_overlap_detected": {
        "severity": "high",
        "category": "hard_split_leakage",
        "next_action": "Regenerate grouped split allocation so split groups are disjoint.",
    },
    "feature_leakage_violation_recorded": {
        "severity": "high",
        "category": "feature_leakage",
        "next_action": "Inspect prediction metadata, remove target/group/proxy leakage, and regenerate affected bundles.",
    },
    "endpoint_audit_integrity_problem": {
        "severity": "high",
        "category": "endpoint_integrity",
        "next_action": "Rebuild endpoint audit and resolve missing artifacts, reconstruction failures, or endpoint failures.",
    },
    "endpoint_reconstructed_runs_mismatch_completed": {
        "severity": "high",
        "category": "endpoint_integrity",
        "next_action": "Reconcile pilot completed rows with endpoint reconstructed runs before original-scale endpoint interpretation.",
    },
    "split_profile_malformed": {
        "severity": "high",
        "category": "split_profile_integrity",
        "next_action": "Regenerate or repair malformed split profile JSON.",
    },
    "feature_leakage_audit_malformed": {
        "severity": "high",
        "category": "feature_leakage",
        "next_action": "Regenerate malformed feature-leakage audit sidecar.",
    },
    "no_prediction_metadata_feature_leakage_sidecar": {
        "severity": "medium",
        "category": "feature_leakage_sidecar_coverage",
        "next_action": "Generate prediction-metadata feature-leakage sidecar when prediction metadata is available.",
    },
    "legacy_endpoint_schema_not_full_closure": {
        "severity": "medium",
        "category": "endpoint_schema_upgrade",
        "next_action": "Regenerate endpoint audit with cpfi_regression_endpoint_audit_v2 and full-method coverage where feasible.",
    },
    "endpoint_audit_not_full_method_coverage": {
        "severity": "medium",
        "category": "endpoint_method_coverage",
        "next_action": "Aggregate or regenerate partial endpoint audits until full_method_coverage is true.",
    },
    "legacy_split_profile_schema_partial_integrity": {
        "severity": "medium",
        "category": "split_profile_schema_upgrade",
        "next_action": "Regenerate split profile with cpfi_regression_split_profile_v2 when the loader/config is still current.",
    },
    "duplicate_signature_cross_split_caveat": {
        "severity": "medium",
        "category": "duplicate_sensitivity",
        "next_action": "Run duplicate-aware split or exact-dedup sensitivity before making strong split-independence claims.",
    },
    "model_visible_signature_cross_split_caveat": {
        "severity": "medium",
        "category": "model_visible_duplicate_sensitivity",
        "next_action": "Inspect model-visible feature-plus-target duplicate signatures and run a grouped/dedup sensitivity if interpretation depends on independence.",
    },
    "feature_leakage_metadata_completeness_caveat": {
        "severity": "medium",
        "category": "feature_leakage_metadata_completeness",
        "next_action": "Backfill prediction metadata fields for preprocessed features and feature-drop policy, then rerun feature-leakage audit.",
    },
    "duplicate_cluster_plus_family_internal_fold_caveat": {
        "severity": "medium",
        "category": "plus_family_internal_fold_scope",
        "next_action": "Keep plus-family duplicate-cluster rows as methodology-caveated evidence unless a cluster-aware internal-fold variant is implemented.",
    },
    "legacy_cqr_fixed_backend_guard_not_backfilled": {
        "severity": "low",
        "category": "legacy_claim_guard",
        "next_action": "Backfill CQR fixed-backend wording/controls when the legacy config/report is next touched.",
    },
    "legacy_venn_abers_claim_guard_not_backfilled": {
        "severity": "low",
        "category": "legacy_claim_guard",
        "next_action": "Backfill Venn-Abers diagnostic-only claim guard when the legacy config/report is next touched.",
    },
    "legacy_best_rows_key_present": {
        "severity": "low",
        "category": "legacy_summary_schema",
        "next_action": "Migrate pilot summary from best_rows to candidate_frontier_rows.",
    },
    "config_not_matched_by_report_directory": {
        "severity": "low",
        "category": "config_traceability",
        "next_action": "Record explicit config path or alias for this report directory.",
    },
}

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument(
        "--cross-run-audit",
        default=DEFAULT_CROSS_RUN_AUDIT,
        help="Cross-run integrity audit JSON path.",
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output JSON path.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def metadata_limitation_class(completeness: dict[str, Any]) -> str:
    missing = {key for key, value in completeness.items() if safe_int(value) > 0}
    if missing == {"missing_preprocessed_feature_names"}:
        return "preprocessed_feature_names_missing_only"
    if {
        "missing_feature_drop_columns",
        "missing_feature_drop_policy",
    }.issubset(missing):
        if "missing_preprocessed_feature_names" in missing:
            return "drop_policy_and_preprocessed_feature_names_missing"
        return "drop_policy_metadata_missing"
    if missing:
        return "other_metadata_missing"
    return "complete_metadata"


def feature_metadata_completeness_profile(row: dict[str, Any]) -> dict[str, Any]:
    feature = row.get("feature_leakage_audit") or {}
    completeness = feature.get("metadata_completeness") or {}
    policy = feature.get("backfill_policy_inference") or {}
    limitation = metadata_limitation_class(completeness)
    policy_complete = (
        bool(policy.get("complete_drop_metadata"))
        and bool(policy.get("complete_policy_metadata"))
    )
    exact_drop_set_enforced = bool(policy.get("exact_drop_set_enforced"))
    exact_feature_set_enforced = bool(policy.get("exact_feature_set_enforced"))
    preprocessed_only = limitation == "preprocessed_feature_names_missing_only"
    bounded_raw_policy_evidence = (
        preprocessed_only
        and policy_complete
        and exact_drop_set_enforced
        and safe_int(feature.get("violations_count")) == 0
    )
    if bounded_raw_policy_evidence:
        severity = "low"
        category = "feature_leakage_preprocessed_name_closure"
        next_action = (
            "Keep the bounded raw-feature/drop-policy caveat unless the affected "
            "runs are regenerated with current preprocessed feature-name metadata."
        )
    elif "drop_policy" in limitation:
        severity = "medium"
        category = "feature_leakage_drop_policy_metadata"
        next_action = (
            "Regenerate affected prediction bundles if full target/group "
            "drop-policy metadata closure is needed."
        )
    else:
        severity = "medium"
        category = "feature_leakage_metadata_completeness"
        next_action = (
            "Regenerate the sidecar or affected prediction bundles before making "
            "full metadata-completeness claims."
        )
    return {
        "metadata_limitation_class": limitation,
        "bounded_raw_policy_evidence": bounded_raw_policy_evidence,
        "complete_drop_metadata": bool(policy.get("complete_drop_metadata")),
        "complete_policy_metadata": bool(policy.get("complete_policy_metadata")),
        "exact_drop_set_enforced": exact_drop_set_enforced,
        "exact_feature_set_enforced": exact_feature_set_enforced,
        "metadata_selection": feature.get("metadata_selection"),
        "severity": severity,
        "category": category,
        "next_action": next_action,
    }


def severity_for(issue: str, row: dict[str, Any] | None = None) -> str:
    if issue == "feature_leakage_metadata_completeness_caveat" and row is not None:
        return str(feature_metadata_completeness_profile(row)["severity"])
    definition = ISSUE_DEFINITIONS.get(issue)
    if definition:
        return str(definition["severity"])
    return "medium"


def category_for(issue: str, row: dict[str, Any] | None = None) -> str:
    if issue == "feature_leakage_metadata_completeness_caveat" and row is not None:
        return str(feature_metadata_completeness_profile(row)["category"])
    definition = ISSUE_DEFINITIONS.get(issue)
    if definition:
        return str(definition["category"])
    if issue.startswith("missing_model_family_controls:"):
        return "model_family_control_contract"
    return "unclassified_integrity_issue"


def next_action_for(issue: str, row: dict[str, Any] | None = None) -> str:
    if issue == "feature_leakage_metadata_completeness_caveat" and row is not None:
        return str(feature_metadata_completeness_profile(row)["next_action"])
    definition = ISSUE_DEFINITIONS.get(issue)
    if definition:
        return str(definition["next_action"])
    if issue.startswith("missing_model_family_controls:"):
        return "Backfill missing model-family quality_controls before treating affected config as current primary evidence."
    return "Inspect the cross-run integrity audit evidence and add a specific remediation action."


def sidecar_sources(row: dict[str, Any], issue: str) -> list[str]:
    sidecars = []
    if "split" in issue or "duplicate" in issue or "signature" in issue:
        path = (row.get("split_profile") or {}).get("path")
        if path:
            sidecars.append(str(path))
    if "endpoint" in issue:
        path = (row.get("endpoint_audit") or {}).get("path")
        if path:
            sidecars.append(str(path))
    if "feature" in issue:
        path = (row.get("feature_leakage_audit") or {}).get("path")
        if path:
            sidecars.append(str(path))
    return sorted(set(sidecars))


def _ledger_parent_name(path_value: Any) -> str | None:
    if not path_value:
        return None
    return Path(str(path_value)).parent.name or None


def _seed_profiles(split_payload: dict[str, Any]) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for profile in split_payload.get("profiles", []) or []:
        for key in ("seeds", "seed_profiles"):
            values = profile.get(key)
            if isinstance(values, list):
                seeds.extend(value for value in values if isinstance(value, dict))
    return seeds


def _duplicate_scope(split_payload: dict[str, Any]) -> str | None:
    split_config = split_payload.get("split_config") or {}
    scope = split_config.get("duplicate_cluster_scope")
    if scope:
        return str(scope)
    for profile in split_payload.get("profiles", []) or []:
        scope = profile.get("duplicate_cluster_scope")
        if scope:
            return str(scope)
    return None


def _model_visible_feature_target_cleared(split_payload: dict[str, Any]) -> bool:
    seeds = _seed_profiles(split_payload)
    if not seeds:
        return False
    return all(
        seed.get("all_model_visible_feature_plus_target_signature_overlaps_zero")
        is True
        for seed in seeds
    )


def _row_signature_cleared(split_payload: dict[str, Any]) -> bool:
    seeds = _seed_profiles(split_payload)
    if not seeds:
        return False
    return all(
        seed.get("all_row_signature_overlaps_zero") is True
        and _all_zero(seed.get("row_signature_overlaps"))
        for seed in seeds
    )


def _all_zero(values: dict[str, Any] | None) -> bool:
    if not isinstance(values, dict):
        return False
    return all(safe_int(value) == 0 for value in values.values())


def _positive_overlap(values: dict[str, Any] | None) -> bool:
    if not isinstance(values, dict):
        return False
    return any(safe_int(value) > 0 for value in values.values())


def _int_set(values: Any) -> set[int]:
    if not isinstance(values, list):
        return set()
    result = set()
    for value in values:
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue
    return result


def _evidence_seed_set(evidence: dict[str, Any], filter_key: str) -> set[int]:
    seeds = _int_set(evidence.get(filter_key))
    if seeds:
        return seeds
    seed_summaries = evidence.get("split_seed_summaries")
    if not isinstance(seed_summaries, list):
        return set()
    result = set()
    for summary in seed_summaries:
        if not isinstance(summary, dict):
            continue
        try:
            result.add(int(summary.get("seed")))
        except (TypeError, ValueError):
            continue
    return result


def model_visible_offending_seeds(root: Path, row: dict[str, Any]) -> list[int]:
    split_path = (row.get("split_profile") or {}).get("path")
    if not split_path:
        return []
    path = root / str(split_path)
    if not path.exists():
        return []
    try:
        split_payload = read_json(path)
    except json.JSONDecodeError:
        return []
    seeds = []
    for seed in _seed_profiles(split_payload):
        if _positive_overlap(
            seed.get("model_visible_feature_plus_target_signature_cross_split_overlaps")
        ):
            try:
                seeds.append(int(seed.get("seed")))
            except (TypeError, ValueError):
                continue
    return sorted(set(seeds))


def row_signature_offending_seeds(root: Path, row: dict[str, Any]) -> list[int]:
    split_path = (row.get("split_profile") or {}).get("path")
    if not split_path:
        return []
    path = root / str(split_path)
    if not path.exists():
        return []
    try:
        split_payload = read_json(path)
    except json.JSONDecodeError:
        return []
    seeds = []
    for seed in _seed_profiles(split_payload):
        if _positive_overlap(seed.get("row_signature_overlaps")):
            try:
                seeds.append(int(seed.get("seed")))
            except (TypeError, ValueError):
                continue
    return sorted(set(seeds))


def discover_model_visible_sensitivity_evidence(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Find completed duplicate-cluster reports that cover baseline caveats."""

    evidence_by_report: dict[str, list[dict[str, Any]]] = {}
    reports_root = root / "experiments/regression/reports"
    comparison_paths = sorted(
        path
        for filename in SENSITIVITY_COMPARISON_FILENAMES
        for path in reports_root.glob(f"*/{filename}")
    )
    for comparison_path in comparison_paths:
        report_dir = comparison_path.parent
        try:
            comparison = read_json(comparison_path)
        except json.JSONDecodeError:
            continue
        baseline_report = _ledger_parent_name(
            (comparison.get("baseline") or {}).get("ledger")
        )
        sensitivity_report = _ledger_parent_name(
            (comparison.get("sensitivity") or {}).get("ledger")
        )
        if not baseline_report:
            continue
        summary = comparison.get("summary") or {}
        if (
            safe_int(summary.get("paired_rows")) <= 0
            or safe_int(summary.get("seed_imbalanced_paired_rows")) != 0
            or safe_int(summary.get("baseline_only_rows")) != 0
            or safe_int(summary.get("sensitivity_only_rows")) != 0
        ):
            continue

        split_path = report_dir / "split_profile.json"
        if not split_path.exists():
            continue
        try:
            split_payload = read_json(split_path)
        except json.JSONDecodeError:
            continue
        if _duplicate_scope(split_payload) != "model_visible_features_plus_target":
            continue
        if not _model_visible_feature_target_cleared(split_payload):
            continue

        feature_path = report_dir / "feature_leakage_audit.json"
        feature_payload = {}
        feature_violations = None
        if feature_path.exists():
            try:
                feature_payload = read_json(feature_path)
                feature_violations = safe_int(feature_payload.get("violations_count"))
            except json.JSONDecodeError:
                feature_violations = None
        if feature_violations not in {0, None}:
            continue

        split_seed_summaries = []
        for seed in _seed_profiles(split_payload):
            split_seed_summaries.append(
                {
                    "seed": seed.get("seed"),
                    "model_visible_feature_plus_target_overlaps": seed.get(
                        "model_visible_feature_plus_target_signature_cross_split_overlaps"
                    ),
                    "model_visible_feature_overlaps": seed.get(
                        "model_visible_feature_signature_cross_split_overlaps"
                    ),
                    "feature_plus_target_cleared": bool(
                        seed.get(
                            "all_model_visible_feature_plus_target_signature_overlaps_zero"
                        )
                    )
                    and _all_zero(
                        seed.get(
                            "model_visible_feature_plus_target_signature_cross_split_overlaps"
                        )
                    ),
                }
            )

        evidence_by_report.setdefault(baseline_report, []).append(
            {
                "status": "completed_duplicate_cluster_sensitivity",
                "report_name": report_dir.name,
                "sensitivity_report_from_ledger": sensitivity_report,
                "comparison_path": rel(comparison_path, root),
                "split_profile_path": rel(split_path, root),
                "feature_leakage_audit_path": (
                    rel(feature_path, root) if feature_path.exists() else None
                ),
                "endpoint_audit_path": (
                    rel(report_dir / "endpoint_audit.json", root)
                    if (report_dir / "endpoint_audit.json").exists()
                    else None
                ),
                "experiment_notes_path": (
                    rel(report_dir / "experiment_notes.md", root)
                    if (report_dir / "experiment_notes.md").exists()
                    else None
                ),
                "baseline_seed_filter": (comparison.get("baseline") or {}).get(
                    "seed_filter"
                )
                or [],
                "sensitivity_seed_filter": (comparison.get("sensitivity") or {}).get(
                    "seed_filter"
                )
                or [],
                "paired_rows": safe_int(summary.get("paired_rows")),
                "seed_imbalanced_paired_rows": safe_int(
                    summary.get("seed_imbalanced_paired_rows")
                ),
                "baseline_nominal_count": safe_int(
                    summary.get("baseline_nominal_count")
                ),
                "sensitivity_nominal_count": safe_int(
                    summary.get("sensitivity_nominal_count")
                ),
                "nominal_status_change_count": safe_int(
                    summary.get("nominal_status_change_count")
                ),
                "coverage_delta_abs": summary.get("coverage_delta_abs") or {},
                "split_seed_summaries": split_seed_summaries,
                "feature_leakage_violations_count": feature_violations,
            }
        )
    return evidence_by_report


def discover_row_signature_sensitivity_evidence(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Find completed duplicate-cluster reports that cover full-row duplicate caveats."""

    evidence_by_report: dict[str, list[dict[str, Any]]] = {}
    reports_root = root / "experiments/regression/reports"
    comparison_paths = sorted(
        path
        for filename in SENSITIVITY_COMPARISON_FILENAMES
        for path in reports_root.glob(f"*/{filename}")
    )
    for comparison_path in comparison_paths:
        report_dir = comparison_path.parent
        try:
            comparison = read_json(comparison_path)
        except json.JSONDecodeError:
            continue
        baseline_report = _ledger_parent_name(
            (comparison.get("baseline") or {}).get("ledger")
        )
        sensitivity_report = _ledger_parent_name(
            (comparison.get("sensitivity") or {}).get("ledger")
        )
        if not baseline_report:
            continue
        summary = comparison.get("summary") or {}
        if (
            safe_int(summary.get("paired_rows")) <= 0
            or safe_int(summary.get("seed_imbalanced_paired_rows")) != 0
            or safe_int(summary.get("baseline_only_rows")) != 0
            or safe_int(summary.get("sensitivity_only_rows")) != 0
        ):
            continue

        split_path = report_dir / "split_profile.json"
        if not split_path.exists():
            continue
        try:
            split_payload = read_json(split_path)
        except json.JSONDecodeError:
            continue
        if _duplicate_scope(split_payload) != "row_signature":
            continue
        if not _row_signature_cleared(split_payload):
            continue

        feature_path = report_dir / "feature_leakage_audit.json"
        feature_payload = {}
        feature_violations = None
        if feature_path.exists():
            try:
                feature_payload = read_json(feature_path)
                feature_violations = safe_int(feature_payload.get("violations_count"))
            except json.JSONDecodeError:
                feature_violations = None
        if feature_violations not in {0, None}:
            continue

        split_seed_summaries = []
        for seed in _seed_profiles(split_payload):
            split_seed_summaries.append(
                {
                    "seed": seed.get("seed"),
                    "row_signature_overlaps": seed.get("row_signature_overlaps"),
                    "row_signature_cleared": bool(
                        seed.get("all_row_signature_overlaps_zero")
                    )
                    and _all_zero(seed.get("row_signature_overlaps")),
                    "model_visible_feature_plus_target_overlaps": seed.get(
                        "model_visible_feature_plus_target_signature_cross_split_overlaps"
                    ),
                }
            )

        evidence_by_report.setdefault(baseline_report, []).append(
            {
                "status": "completed_row_signature_duplicate_cluster_sensitivity",
                "report_name": report_dir.name,
                "sensitivity_report_from_ledger": sensitivity_report,
                "comparison_path": rel(comparison_path, root),
                "split_profile_path": rel(split_path, root),
                "feature_leakage_audit_path": (
                    rel(feature_path, root) if feature_path.exists() else None
                ),
                "endpoint_audit_path": (
                    rel(report_dir / "endpoint_audit.json", root)
                    if (report_dir / "endpoint_audit.json").exists()
                    else None
                ),
                "experiment_notes_path": (
                    rel(report_dir / "experiment_notes.md", root)
                    if (report_dir / "experiment_notes.md").exists()
                    else None
                ),
                "baseline_seed_filter": (comparison.get("baseline") or {}).get(
                    "seed_filter"
                )
                or [],
                "sensitivity_seed_filter": (comparison.get("sensitivity") or {}).get(
                    "seed_filter"
                )
                or [],
                "paired_rows": safe_int(summary.get("paired_rows")),
                "seed_imbalanced_paired_rows": safe_int(
                    summary.get("seed_imbalanced_paired_rows")
                ),
                "baseline_nominal_count": safe_int(
                    summary.get("baseline_nominal_count")
                ),
                "sensitivity_nominal_count": safe_int(
                    summary.get("sensitivity_nominal_count")
                ),
                "nominal_status_change_count": safe_int(
                    summary.get("nominal_status_change_count")
                ),
                "coverage_delta_abs": summary.get("coverage_delta_abs") or {},
                "split_seed_summaries": split_seed_summaries,
                "feature_leakage_violations_count": feature_violations,
            }
        )
    return evidence_by_report


def sensitivity_evidence_for_row(
    root: Path,
    row: dict[str, Any],
    sensitivity_evidence_by_report: dict[str, list[dict[str, Any]]] | None,
    issue: str,
) -> list[dict[str, Any]]:
    report_name = str(row.get("report_name"))
    if issue == "duplicate_signature_cross_split_caveat":
        required_seeds = set(row_signature_offending_seeds(root, row))
    elif issue == "model_visible_signature_cross_split_caveat":
        required_seeds = set(model_visible_offending_seeds(root, row))
    else:
        required_seeds = set()
    if not required_seeds:
        return []
    matched = []
    for evidence in (sensitivity_evidence_by_report or {}).get(report_name, []):
        baseline_seeds = _evidence_seed_set(evidence, "baseline_seed_filter")
        sensitivity_seeds = _evidence_seed_set(evidence, "sensitivity_seed_filter")
        if required_seeds.issubset(baseline_seeds) and required_seeds.issubset(
            sensitivity_seeds
        ):
            item = dict(evidence)
            item["required_offending_seeds"] = sorted(required_seeds)
            item["offending_seed_coverage_complete"] = True
            matched.append(item)
    return matched


def is_scoped_main_result_candidate_duplicate_caveat(row: dict[str, Any], issue: str) -> bool:
    if issue != "duplicate_signature_cross_split_caveat":
        return False
    report_name = str(row.get("report_name") or "")
    if not report_name.startswith("main_result_candidate_bundle_"):
        return False
    split = row.get("split_profile") or {}
    endpoint = row.get("endpoint_audit") or {}
    feature = row.get("feature_leakage_audit") or {}
    return (
        split.get("present") is True
        and split.get("schema") == "cpfi_regression_split_profile_v2"
        and safe_int(split.get("row_id_overlap_violations")) == 0
        and safe_int(split.get("split_group_overlap_violations")) == 0
        and endpoint.get("present") is True
        and feature.get("present") is True
        and safe_int(feature.get("violations_count")) == 0
    )


def is_scoped_candidate_sensitivity_artifact_caveat(
    row: dict[str, Any],
    issue: str,
) -> bool:
    if issue != "model_visible_signature_cross_split_caveat":
        return False
    report_name = str(row.get("report_name") or "")
    if not report_name.startswith("main_result_candidate_duplicate_sensitivity_"):
        return False
    split = row.get("split_profile") or {}
    endpoint = row.get("endpoint_audit") or {}
    feature = row.get("feature_leakage_audit") or {}
    return (
        split.get("present") is True
        and split.get("schema") == "cpfi_regression_split_profile_v2"
        and safe_int(split.get("row_id_overlap_violations")) == 0
        and safe_int(split.get("split_group_overlap_violations")) == 0
        and endpoint.get("present") is True
        and feature.get("present") is True
        and safe_int(feature.get("violations_count")) == 0
    )


def row_evidence(row: dict[str, Any], issue: str) -> dict[str, Any]:
    evidence = {
        "status_counts": row.get("status_counts") or {},
        "large_sweep": bool(row.get("large_sweep")),
        "summary_rows": row.get("summary_rows"),
        "ledger_rows": row.get("ledger_rows"),
    }
    if "split" in issue or "duplicate" in issue or "signature" in issue:
        evidence["split_profile"] = row.get("split_profile") or {}
    if "endpoint" in issue:
        evidence["endpoint_audit"] = row.get("endpoint_audit") or {}
    if "feature" in issue:
        evidence["feature_leakage_audit"] = row.get("feature_leakage_audit") or {}
    if issue == "feature_leakage_metadata_completeness_caveat":
        evidence["feature_metadata_completeness_profile"] = (
            feature_metadata_completeness_profile(row)
        )
    if issue.startswith("legacy_") or issue.startswith("missing_model_family_controls"):
        evidence["cp_methods"] = row.get("cp_methods") or []
    return evidence


def action_id(report_name: str, issue_kind: str, issue: str) -> str:
    safe_issue = (
        issue.replace(":", "_")
        .replace(",", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )
    return f"{report_name}:{issue_kind}:{safe_issue}"


def build_action(
    root: Path,
    row: dict[str, Any],
    issue: str,
    issue_kind: str,
    sensitivity_evidence_by_report: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    severity = severity_for(issue, row)
    report_name = str(row.get("report_name"))
    sensitivity_evidence = (
        sensitivity_evidence_for_row(
            root,
            row,
            sensitivity_evidence_by_report,
            issue,
        )
        if issue
        in {
            "duplicate_signature_cross_split_caveat",
            "model_visible_signature_cross_split_caveat",
        }
        else []
    )
    status = "covered_by_sensitivity" if sensitivity_evidence else "open"
    if issue in TRACKED_METHODOLOGY_CAVEATS:
        status = "tracked_methodology_caveat"
    elif (
        not sensitivity_evidence
        and is_scoped_main_result_candidate_duplicate_caveat(row, issue)
    ):
        status = TRACKED_DIAGNOSTIC_CAVEAT_STATUS
    elif (
        not sensitivity_evidence
        and is_scoped_candidate_sensitivity_artifact_caveat(row, issue)
    ):
        status = TRACKED_DIAGNOSTIC_CAVEAT_STATUS
    if sensitivity_evidence:
        severity = "low"
    if status == TRACKED_DIAGNOSTIC_CAVEAT_STATUS:
        severity = "low"
    recommended_next_action = next_action_for(issue, row)
    if sensitivity_evidence:
        recommended_next_action = (
            "Review the linked duplicate-cluster sensitivity evidence before "
            "making split-independence claims; run broader sensitivity only if "
            "substantive interpretation depends on the historical split."
        )
    elif status == TRACKED_DIAGNOSTIC_CAVEAT_STATUS:
        if is_scoped_candidate_sensitivity_artifact_caveat(row, issue):
            recommended_next_action = (
                "Keep this sensitivity artifact diagnostic-only; do not use it "
                "for model-visible split-independence, final selection, or "
                "main-result promotion claims."
            )
        else:
            recommended_next_action = (
                "Keep this main-result candidate bundle diagnostic-only; run a "
                "seed-matched duplicate-aware sensitivity before promoting any "
                "split-independence or final main-result claim."
            )
    return {
        "action_id": action_id(report_name, issue_kind, issue),
        "status": status,
        "severity": severity,
        "priority_rank": None,
        "issue_kind": issue_kind,
        "issue_type": issue,
        "action_category": category_for(issue, row),
        "report_id": row.get("report_id"),
        "report_name": report_name,
        "pilot_summary_path": row.get("pilot_summary_path"),
        "config_path": row.get("config_path"),
        "experiment_id": row.get("experiment_id"),
        "dataset_ids": row.get("dataset_ids") or [],
        "cp_methods": row.get("cp_methods") or [],
        "source_sidecar_paths": sidecar_sources(row, issue),
        "evidence": row_evidence(row, issue),
        "sensitivity_evidence": sensitivity_evidence,
        "recommended_next_action": recommended_next_action,
        "claim_boundaries": CLAIM_BOUNDARIES,
    }


def build_payload(root: Path, cross_run_path: Path) -> dict[str, Any]:
    cross_run = read_json(cross_run_path)
    model_visible_sensitivity_evidence = discover_model_visible_sensitivity_evidence(root)
    row_signature_sensitivity_evidence = discover_row_signature_sensitivity_evidence(root)
    actions = []
    for row in cross_run.get("rows", []) or []:
        for issue in row.get("blocking_issues", []) or []:
            issue_text = str(issue)
            actions.append(
                build_action(
                    root,
                    row,
                    issue_text,
                    "blocking_issue",
                    row_signature_sensitivity_evidence
                    if issue_text == "duplicate_signature_cross_split_caveat"
                    else model_visible_sensitivity_evidence,
                )
            )
        for caveat in row.get("caveats", []) or []:
            caveat_text = str(caveat)
            actions.append(
                build_action(
                    root,
                    row,
                    caveat_text,
                    "caveat",
                    row_signature_sensitivity_evidence
                    if caveat_text == "duplicate_signature_cross_split_caveat"
                    else model_visible_sensitivity_evidence,
                )
            )

    actions.sort(
        key=lambda item: (
            -SEVERITY_RANK.get(item["severity"], 0),
            item["action_category"],
            item["issue_type"],
            item["report_name"],
        )
    )
    for index, action in enumerate(actions, start=1):
        action["priority_rank"] = index

    open_actions = [action for action in actions if action["status"] == "open"]
    issue_counts = Counter(action["issue_type"] for action in actions)
    severity_counts = Counter(action["severity"] for action in actions)
    category_counts = Counter(action["action_category"] for action in actions)
    status_counts = Counter(action["status"] for action in actions)
    open_severity_counts = Counter(action["severity"] for action in open_actions)
    open_category_counts = Counter(action["action_category"] for action in open_actions)
    report_counts = Counter(action["report_name"] for action in actions)
    open_report_counts = Counter(action["report_name"] for action in open_actions)
    dataset_counts: Counter[str] = Counter()
    for action in actions:
        dataset_counts.update(str(value) for value in action["dataset_ids"])

    expected_issue_counts = {}
    summary = cross_run.get("summary", {}) or {}
    for key in ("blocking_issue_counts", "caveat_counts"):
        for issue, count in (summary.get(key) or {}).items():
            expected_issue_counts[str(issue)] = expected_issue_counts.get(str(issue), 0) + int(count)

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_cross_run_integrity_audit_path": rel(cross_run_path, root),
        "methodology_sanity_audit_path": (
            "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "sanity_audit.json"
        ),
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "source_reports_scanned": int(summary.get("reports_scanned") or 0),
            "source_total_completed_rows": int(summary.get("total_completed_rows") or 0),
            "action_count": len(actions),
            "open_action_count": len(open_actions),
            "covered_action_count": len(actions) - len(open_actions),
            "open_report_count": len(open_report_counts),
            "status_counts": dict(sorted(status_counts.items())),
            "severity_counts": dict(sorted(severity_counts.items())),
            "category_counts": dict(sorted(category_counts.items())),
            "open_severity_counts": dict(sorted(open_severity_counts.items())),
            "open_category_counts": dict(sorted(open_category_counts.items())),
            "issue_counts": dict(sorted(issue_counts.items())),
            "expected_issue_counts_from_cross_run": dict(sorted(expected_issue_counts.items())),
            "issue_counts_match_cross_run": dict(sorted(issue_counts.items()))
            == dict(sorted(expected_issue_counts.items())),
            "top_reports_by_action_count": [
                {"report_name": report, "action_count": int(count)}
                for report, count in report_counts.most_common(20)
            ],
            "top_datasets_by_action_count": [
                {"dataset_id": dataset_id, "action_count": int(count)}
                for dataset_id, count in dataset_counts.most_common(20)
            ],
        },
        "rows": actions,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Integrity Remediation Backlog",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source audit: `{payload['source_cross_run_integrity_audit_path']}`",
        f"- Source reports scanned: {summary['source_reports_scanned']}",
        f"- Source completed rows represented: {summary['source_total_completed_rows']}",
        f"- Total actions: {summary['action_count']}",
        f"- Open actions: {summary['open_action_count']}",
        f"- Covered actions: {summary['covered_action_count']}",
        f"- Open reports: {summary['open_report_count']}",
        f"- Status counts: `{summary['status_counts']}`",
        f"- Severity counts: `{summary['severity_counts']}`",
        f"- Category counts: `{summary['category_counts']}`",
        f"- Issue counts match cross-run audit: `{summary['issue_counts_match_cross_run']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(
        [
            "",
            "## Top Reports",
            "",
            "| Report | Open actions |",
            "| --- | ---: |",
        ]
    )
    for item in summary["top_reports_by_action_count"]:
        lines.append(f"| `{item['report_name']}` | {item['action_count']} |")
    lines.extend(
        [
            "",
            "## Action Queue",
            "",
            "| Rank | Severity | Category | Issue | Report | Next action |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"{row['priority_rank']} | "
            f"{row['severity']} | "
            f"`{row['action_category']}` | "
            f"`{row['issue_type']}` | "
            f"`{row['report_name']}` | "
            f"{row['status']}: {row['recommended_next_action']} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    cross_run_path = Path(args.cross_run_audit)
    if not cross_run_path.is_absolute():
        cross_run_path = root / cross_run_path
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path
    payload = build_payload(root, cross_run_path)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
