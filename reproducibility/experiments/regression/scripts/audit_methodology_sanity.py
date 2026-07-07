"""Audit regression experiment methodology and reporting guardrails.

This script is intentionally read-only over experiment inputs. It scans configs,
pilot summaries, endpoint/split-profile coverage, and selected claim wording so
the regression CP study can keep a reproducible sanity-check trail while long
model sweeps run.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


DEFAULT_OUT_DIR = "experiments/regression/reports/methodology_sanity_audit_20260627"
DUPLICATE_SPLIT_CAVEAT_BACKLOG = (
    DEFAULT_OUT_DIR + "/duplicate_split_caveat_backlog.json"
)
PAIRED_DUPLICATE_SENSITIVITY_AUDIT = (
    DEFAULT_OUT_DIR + "/paired_duplicate_sensitivity_audit.json"
)
CROSS_RUN_INTEGRITY_AUDIT = DEFAULT_OUT_DIR + "/cross_run_integrity_audit.json"
INTEGRITY_REMEDIATION_BACKLOG = DEFAULT_OUT_DIR + "/integrity_remediation_backlog.json"
LARGE_COMPLETED_THRESHOLD = 700
STACKOVERFLOW_REPORT_DIR = (
    "experiments/regression/reports/"
    "model_family_sweep_stackoverflow_2025_compensation_log1p_age"
)
STACKOVERFLOW_MODEL_VISIBLE_REPORT_DIR = (
    "experiments/regression/reports/"
    "duplicate_cluster_sensitivity_stackoverflow_2025_compensation_log1p_age_model_visible"
)
STACKOVERFLOW_CONFIG = (
    "experiments/regression/configs/"
    "model_family_sweep_stackoverflow_2025_compensation_log1p_age.yaml"
)
STACKOVERFLOW_MODEL_VISIBLE_CLAIM_ID = (
    "stackoverflow_model_visible_duplicate_sensitivity_pending"
)
STACKOVERFLOW_LEDGER_ROWS = 2184
STACKOVERFLOW_COMPLETED = 1404
STACKOVERFLOW_SKIPPED_METHOD = 780
STACKOVERFLOW_MODEL_VISIBLE_REQUIRED_ARTIFACTS = (
    "pilot_summary.json",
    "split_profile.json",
    "feature_leakage_audit.json",
    "runtime_cap_audit.json",
    "sensitivity_comparison.json",
    "endpoint_audit.json",
    "publication_readiness_manifest.md",
)
REQUIRED_MODEL_FAMILY_CONTROLS = (
    "require_atomic_checkpoints",
    "require_prediction_bundle_cache",
    "require_dataset_audit",
    "require_model_params_summary_key",
    "interpret_rankings_as_triage_only",
)
FEATURE_LEAKAGE_AUDIT_SCHEMAS = {
    "cpfi_prediction_feature_leakage_audit_v1",
    "cpfi_stackoverflow_feature_leakage_audit_v1",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Output directory.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def pilot_completed_count(payload: dict[str, Any]) -> int:
    return int(payload.get("metadata", {}).get("status_counts", {}).get("completed", 0))


def finding(
    title: str,
    severity: str,
    evidence: Any,
    action: str,
) -> dict[str, Any]:
    return {
        "title": title,
        "severity": severity,
        "evidence": evidence,
        "action": action,
    }


def scan_pilot_summaries(root: Path) -> tuple[list[Path], list[dict[str, Any]]]:
    paths = sorted((root / "experiments/regression/reports").glob("**/pilot_summary.json"))
    payloads = []
    for path in paths:
        try:
            payloads.append({"path": path, "payload": read_json(path)})
        except json.JSONDecodeError as exc:
            payloads.append(
                {
                    "path": path,
                    "payload": {},
                    "json_error": f"{type(exc).__name__}: {exc}",
                }
            )
    return paths, payloads


def scan_configs(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((root / "experiments/regression/configs").glob("*.yaml")):
        try:
            config = read_yaml(path)
        except yaml.YAMLError as exc:
            config = {"yaml_error": f"{type(exc).__name__}: {exc}"}
        rows.append({"path": path, "config": config})
    return rows


def failed_summary_examples(payloads: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    examples = []
    for item in payloads:
        payload = item["payload"]
        failed = int(payload.get("metadata", {}).get("status_counts", {}).get("failed", 0))
        if failed:
            examples.append({"path": rel(item["path"], root), "failed": failed})
    return examples


def large_summary_backlog(
    payloads: list[dict[str, Any]],
    root: Path,
    artifact_name: str,
) -> list[dict[str, Any]]:
    backlog = []
    for item in payloads:
        completed = pilot_completed_count(item["payload"])
        if completed < LARGE_COMPLETED_THRESHOLD:
            continue
        if is_root_aggregate_pilot_summary(item["path"], root):
            continue
        report_dir = item["path"].parent
        artifact_path = report_dir / artifact_name
        if not artifact_satisfies_large_backlog(artifact_path, artifact_name):
            entry: dict[str, Any] = {
                "path": rel(item["path"], root),
                "completed": completed,
            }
            if artifact_name == "endpoint_audit.json":
                entry["partial_endpoint_progress"] = endpoint_partial_progress(
                    report_dir,
                    root,
                )
            backlog.append(entry)
    return backlog


def is_root_aggregate_pilot_summary(path: Path, root: Path) -> bool:
    reports_root = root / "experiments/regression/reports"
    try:
        return path.resolve() == (reports_root / "pilot_summary.json").resolve()
    except FileNotFoundError:
        return path == reports_root / "pilot_summary.json"


def artifact_satisfies_large_backlog(path: Path, artifact_name: str) -> bool:
    if not path.exists():
        return False
    if artifact_name != "endpoint_audit.json":
        return True
    try:
        payload = read_json(path)
    except json.JSONDecodeError:
        return False
    method_filter = payload.get("method_filter")
    if isinstance(method_filter, dict):
        return bool(method_filter.get("full_method_coverage", False))
    return True


def endpoint_partial_progress(report_dir: Path, root: Path) -> dict[str, Any]:
    paths = sorted(report_dir.glob("endpoint_audit__*.json"))
    if not paths:
        return {
            "partial_count": 0,
            "completed_ledger_rows": 0,
            "reconstructed_runs": 0,
            "reconstruction_failures": 0,
            "methods_completed": [],
            "omitted_completed_method_counts": {},
            "malformed_partials": [],
        }

    configured_counts: Counter[str] = Counter()
    available_counts: dict[str, int] | None = None
    methods_completed: set[str] = set()
    malformed: list[dict[str, str]] = []
    completed_ledger_rows = 0
    reconstructed_runs = 0
    reconstruction_failures = 0
    for path in paths:
        try:
            payload = read_json(path)
        except json.JSONDecodeError as exc:
            malformed.append({"path": rel(path, root), "error": str(exc)})
            continue
        if payload.get("audit_schema") != "cpfi_regression_endpoint_audit_v2":
            malformed.append({"path": rel(path, root), "error": "schema"})
            continue
        current_available = {
            str(key): int(value)
            for key, value in payload.get("available_completed_method_counts", {}).items()
        }
        if available_counts is None:
            available_counts = current_available
        elif current_available != available_counts:
            malformed.append({"path": rel(path, root), "error": "available_counts"})
            continue
        configured_counts.update(
            {
                str(key): int(value)
                for key, value in payload.get(
                    "configured_completed_method_counts",
                    {},
                ).items()
            }
        )
        methods_completed.update(str(method) for method in payload.get("method_summary", {}))
        completed_ledger_rows += int(payload.get("completed_ledger_rows", 0))
        reconstructed_runs += int(payload.get("reconstructed_runs", 0))
        reconstruction_failures += int(payload.get("reconstruction_failures", 0))

    omitted = Counter(available_counts or {}) - configured_counts
    return {
        "partial_count": len(paths),
        "completed_ledger_rows": completed_ledger_rows,
        "reconstructed_runs": reconstructed_runs,
        "reconstruction_failures": reconstruction_failures,
        "methods_completed": sorted(methods_completed),
        "omitted_completed_method_counts": dict(sorted(omitted.items())),
        "malformed_partials": malformed[:20],
    }


def guardrail_backlog(config_rows: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    cqr_missing = []
    va_missing = []
    legacy_cqr_missing = 0
    legacy_va_missing = 0
    for row in config_rows:
        path = row["path"]
        config = row["config"]
        cp_methods = set(config.get("cp_methods", []) or [])
        controls = config.get("quality_controls", {}) or {}
        is_model_family = path.name.startswith("model_family_sweep_")
        if "cqr" in cp_methods and not controls.get("interpret_cqr_as_fixed_quantile_backend"):
            if is_model_family:
                cqr_missing.append(rel(path, root))
            else:
                legacy_cqr_missing += 1
        if (
            {"venn_abers_quantile", "venn_abers_split_fallback"}.intersection(cp_methods)
            and not controls.get("forbid_validated_venn_abers_regression_claims")
        ):
            if is_model_family:
                va_missing.append(rel(path, root))
            else:
                legacy_va_missing += 1
    return {
        "model_family_cqr_missing": cqr_missing,
        "model_family_va_missing": va_missing,
        "legacy_cqr_missing_count": legacy_cqr_missing,
        "legacy_va_missing_count": legacy_va_missing,
    }


def model_family_control_contract_backlog(
    config_rows: list[dict[str, Any]], root: Path
) -> dict[str, Any]:
    missing_by_config = []
    scanned = 0
    for row in config_rows:
        path = row["path"]
        if not path.name.startswith("model_family_sweep_"):
            continue
        scanned += 1
        controls = row["config"].get("quality_controls", {}) or {}
        missing = [
            key for key in REQUIRED_MODEL_FAMILY_CONTROLS if not controls.get(key)
        ]
        if missing:
            missing_by_config.append(
                {
                    "path": rel(path, root),
                    "missing_controls": missing,
                }
            )
    return {
        "model_family_configs_scanned": scanned,
        "required_controls": list(REQUIRED_MODEL_FAMILY_CONTROLS),
        "missing_by_config": missing_by_config,
    }


def runner_feature_drop_guard_scan(root: Path) -> dict[str, Any]:
    runner_path = root / "experiments/regression/scripts/run_regression_pilot.py"
    runner_text = runner_path.read_text(encoding="utf-8") if runner_path.exists() else ""
    helper_match = re.search(
        (
            r"def runner_feature_drop_columns\(.*?"
            r"return \[column for column in dict\.fromkeys\(feature_drop\)"
        ),
        runner_text,
        flags=re.DOTALL,
    )
    helper_block = helper_match.group(0) if helper_match else ""
    fit_block_match = re.search(
        (
            r"def fit_or_load_prediction_bundle\(.*?"
            r"X_train = train_df\.drop\(columns=feature_drop\)"
        ),
        runner_text,
        flags=re.DOTALL,
    )
    fit_block = fit_block_match.group(0) if fit_block_match else ""
    fit_uses_helper = "feature_drop = runner_feature_drop_columns(" in fit_block
    helper_group_loop = (
        "for column in [group_col, split_group_col, base_split_group_col]" in helper_block
    )
    helper_appends_group = "feature_drop.append(str(column))" in helper_block
    return {
        "runner_path": rel(runner_path, root) if runner_path.exists() else str(runner_path),
        "helper_block_found": bool(helper_block),
        "fit_block_found": bool(fit_block) and fit_uses_helper,
        "drops_target_before_preprocessing": fit_uses_helper
        and "feature_drop = [target]" in helper_block,
        "drops_primary_group_when_present": helper_group_loop and helper_appends_group,
        "drops_split_group_when_present": helper_group_loop and helper_appends_group,
        "drops_base_split_group_when_present": helper_group_loop and helper_appends_group,
        "drops_loader_extra_feature_drop_columns": "feature_drop_columns" in helper_block
        and "DATASET_LOADERS.get(dataset_id, {})" in helper_block,
        "deduplicates_feature_drop_columns": "dict.fromkeys(feature_drop)" in helper_block,
    }


def config_loader_leakage_policy_scan(
    config_rows: list[dict[str, Any]], root: Path
) -> dict[str, Any]:
    from experiments.regression.scripts.run_regression_pilot import DATASET_LOADERS

    evidence: dict[str, Any] = {
        "configs_scanned": len(config_rows),
        "dataset_refs_scanned": 0,
        "model_family_dataset_refs_scanned": 0,
        "unknown_dataset_refs": [],
        "missing_loader_target_or_group": [],
        "model_family_extra_target_boundary_missing": [],
        "legacy_extra_target_boundary_weak": [],
        "model_family_derived_group_source_policy_missing": [],
        "legacy_derived_group_source_policy_weak": [],
    }
    for row in config_rows:
        path = row["path"]
        config = row["config"]
        is_model_family = path.name.startswith("model_family_sweep_")
        config_text = " ".join(
            [
                str(config.get("purpose", "")),
                " ".join(
                    key
                    for key, value in (config.get("quality_controls", {}) or {}).items()
                    if value
                ),
            ]
        ).lower()
        for dataset_id in config.get("datasets", []) or []:
            evidence["dataset_refs_scanned"] += 1
            if is_model_family:
                evidence["model_family_dataset_refs_scanned"] += 1
            spec = DATASET_LOADERS.get(str(dataset_id))
            if spec is None:
                _append_limited(
                    evidence["unknown_dataset_refs"],
                    {"path": rel(path, root), "dataset_id": dataset_id},
                )
                continue
            if not spec.get("target") or not spec.get("group"):
                _append_limited(
                    evidence["missing_loader_target_or_group"],
                    {
                        "path": rel(path, root),
                        "dataset_id": dataset_id,
                        "has_target": bool(spec.get("target")),
                        "has_group": bool(spec.get("group")),
                    },
                )
            _scan_extra_target_policy(
                evidence,
                path,
                root,
                str(dataset_id),
                spec,
                config_text,
                is_model_family,
            )
            _scan_derived_group_source_policy(
                evidence,
                path,
                root,
                str(dataset_id),
                spec,
                config_text,
                is_model_family,
            )
    return evidence


def _scan_extra_target_policy(
    evidence: dict[str, Any],
    path: Path,
    root: Path,
    dataset_id: str,
    spec: dict[str, Any],
    config_text: str,
    is_model_family: bool,
) -> None:
    extra_targets = [str(col) for col in spec.get("extra_target_columns", [])]
    if not extra_targets:
        return
    dropped = {str(col) for col in spec.get("drop_columns", [])}
    retained = [col for col in extra_targets if col not in dropped]
    if not retained:
        return
    documented = (
        "sensitivity" in config_text
        and ("prior" in config_text or "target" in config_text)
        and ("causal" in config_text or "intervention" in config_text)
    )
    if documented:
        return
    bucket = (
        "model_family_extra_target_boundary_missing"
        if is_model_family
        else "legacy_extra_target_boundary_weak"
    )
    _append_limited(
        evidence[bucket],
        {
            "path": rel(path, root),
            "dataset_id": dataset_id,
            "retained_extra_target_columns": retained,
        },
    )


def _scan_derived_group_source_policy(
    evidence: dict[str, Any],
    path: Path,
    root: Path,
    dataset_id: str,
    spec: dict[str, Any],
    config_text: str,
    is_model_family: bool,
) -> None:
    quantile_groups = spec.get("quantile_groups", []) or []
    if not quantile_groups:
        return
    dropped = {str(col) for col in spec.get("drop_columns", [])}
    dropped.update(str(col) for col in spec.get("feature_drop_columns", []))
    retained_sources = [
        {
            "source_col": str(item.get("source_col")),
            "group_col": str(item.get("group_col")),
        }
        for item in quantile_groups
        if str(item.get("source_col")) not in dropped
    ]
    if not retained_sources:
        return
    documented = any(
        token in config_text
        for token in (
            "model-visible",
            "remain_model_visible",
            "proxy",
            "diagnostic",
            "sensitivity",
        )
    )
    if documented:
        return
    bucket = (
        "model_family_derived_group_source_policy_missing"
        if is_model_family
        else "legacy_derived_group_source_policy_weak"
    )
    _append_limited(
        evidence[bucket],
        {
            "path": rel(path, root),
            "dataset_id": dataset_id,
            "retained_derived_group_source_columns": retained_sources,
        },
    )


def stackoverflow_model_visible_claim_boundary_status(root: Path) -> dict[str, Any]:
    report_dir = root / STACKOVERFLOW_MODEL_VISIBLE_REPORT_DIR
    claim_register_path = root / "experiments/regression/catalogs/manuscript_claim_register.json"
    evidence_view_path = root / "experiments/regression/manuscript/evidence_view.json"
    robustness_table_path = root / "experiments/regression/manuscript/robustness_results_table.md"
    manifest_path = report_dir / "publication_readiness_manifest.md"
    comparison_path = report_dir / "sensitivity_comparison.json"
    pilot_path = report_dir / "pilot_summary.json"
    feature_audit_path = report_dir / "feature_leakage_audit.json"
    runtime_audit_path = report_dir / "runtime_cap_audit.json"
    endpoint_audit_path = report_dir / "endpoint_audit.json"

    required_paths = [
        report_dir / filename
        for filename in STACKOVERFLOW_MODEL_VISIBLE_REQUIRED_ARTIFACTS
    ]
    manuscript_paths = [claim_register_path, evidence_view_path, robustness_table_path]
    missing_required = [rel(path, root) for path in required_paths if not path.exists()]
    missing_manuscript = [
        rel(path, root) for path in manuscript_paths if not path.exists()
    ]
    malformed: list[dict[str, str]] = []

    comparison = (
        _read_json_for_evidence(comparison_path, root, malformed)
        if comparison_path.exists()
        else {}
    )
    pilot = (
        _read_json_for_evidence(pilot_path, root, malformed)
        if pilot_path.exists()
        else {}
    )
    feature_audit = (
        _read_json_for_evidence(feature_audit_path, root, malformed)
        if feature_audit_path.exists()
        else {}
    )
    runtime_audit = (
        _read_json_for_evidence(runtime_audit_path, root, malformed)
        if runtime_audit_path.exists()
        else {}
    )
    endpoint_audit = (
        _read_json_for_evidence(endpoint_audit_path, root, malformed)
        if endpoint_audit_path.exists()
        else {}
    )
    claim_register = (
        _read_json_for_evidence(claim_register_path, root, malformed)
        if claim_register_path.exists()
        else {}
    )
    evidence_view = (
        _read_json_for_evidence(evidence_view_path, root, malformed)
        if evidence_view_path.exists()
        else {}
    )

    manifest_text = (
        manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else ""
    )
    robustness_text = (
        robustness_table_path.read_text(encoding="utf-8")
        if robustness_table_path.exists()
        else ""
    )
    summary = comparison.get("summary") or {}
    method_summaries = {
        str(row.get("cp_method")): row
        for row in summary.get("method_summaries", []) or []
        if isinstance(row, dict)
    }
    cqr_summary = method_summaries.get("cqr", {})
    va_summary = method_summaries.get("venn_abers_quantile", {})
    fallback_summary = method_summaries.get("venn_abers_split_fallback", {})
    frontier = summary.get("sensitivity_lowest_interval_score_nominal_row") or {}
    boundary_text = " ".join(
        str(item) for item in comparison.get("claim_boundaries", []) or []
    )

    claims = claim_register.get("claims", []) or []
    claim = next(
        (
            item
            for item in claims
            if item.get("claim_id") == STACKOVERFLOW_MODEL_VISIBLE_CLAIM_ID
        ),
        {},
    )
    claim_not_claiming = " ".join(
        str(item) for item in claim.get("not_claiming", []) or []
    )
    requirement_statuses = {
        str(item.get("requirement_id")): item.get("status")
        for item in claim.get("requirements", []) or []
        if isinstance(item, dict)
    }

    evidence_rows = evidence_view.get("rows", []) or []
    evidence_row = next(
        (
            item
            for item in evidence_rows
            if item.get("claim_id") == STACKOVERFLOW_MODEL_VISIBLE_CLAIM_ID
        ),
        {},
    )

    endpoint_method_summary = endpoint_audit.get("method_summary") or {}
    endpoint_caveat_fields = (
        "lower_below_floor",
        "lower_below_observed_min",
        "upper_above_observed_max",
        "upper_above_warning",
        "width_above_observed_range",
        "width_above_twice_observed_range",
    )
    endpoint_caveat_methods = sorted(
        method
        for method, stats in endpoint_method_summary.items()
        if isinstance(stats, dict)
        and any(int(stats.get(field) or 0) > 0 for field in endpoint_caveat_fields)
    )
    pilot_metadata = pilot.get("metadata") or {}

    checks = {
        "required_report_artifacts_present": not missing_required,
        "manuscript_artifacts_present": not missing_manuscript,
        "ledger_counts_complete": (
            pilot_metadata.get("ledger_rows") == STACKOVERFLOW_LEDGER_ROWS
            and pilot_metadata.get("unique_run_rows") == STACKOVERFLOW_LEDGER_ROWS
            and pilot_metadata.get("status_counts", {}).get("completed")
            == STACKOVERFLOW_COMPLETED
            and pilot_metadata.get("status_counts", {}).get("skipped_method")
            == STACKOVERFLOW_SKIPPED_METHOD
        ),
        "feature_leakage_audit_zero_violations": (
            feature_audit.get("metadata_files_scanned") == 156
            and feature_audit.get("violations_count") == 0
        ),
        "runtime_skip_audit_expected": (
            runtime_audit.get("skipped_method_rows") == STACKOVERFLOW_SKIPPED_METHOD
            and not runtime_audit.get("unexpected_skipped_methods")
            and not runtime_audit.get("missing_expected_skipped_methods")
        ),
        "paired_sensitivity_seed_balanced": (
            summary.get("paired_rows") == 468
            and summary.get("seed_imbalanced_paired_rows") == 0
            and summary.get("baseline_only_rows") == 0
            and summary.get("sensitivity_only_rows") == 0
        ),
        "cqr_not_supported_0_of_52": (
            cqr_summary.get("paired_rows") == 52
            and cqr_summary.get("baseline_nominal_count") == 0
            and cqr_summary.get("sensitivity_nominal_count") == 0
        ),
        "venn_abers_quantile_negative_0_of_52": (
            va_summary.get("paired_rows") == 52
            and va_summary.get("baseline_nominal_count") == 0
            and va_summary.get("sensitivity_nominal_count") == 0
        ),
        "venn_abers_split_fallback_recorded_as_fallback": (
            fallback_summary.get("paired_rows") == 52
            and _contains_all(
                boundary_text + " " + manifest_text + " " + claim_not_claiming,
                [
                    "venn-abers regression validation",
                    "ordinary split fallback",
                ],
            )
        ),
        "normalized_abs_xgboost_frontier_exploratory": (
            frontier.get("cp_method") == "normalized_abs"
            and frontier.get("model_id") == "xgboost"
            and _contains_all(
                manifest_text + " " + robustness_text,
                ["normalized_abs", "xgboost", "exploratory", "not a selected method"],
            )
        ),
        "sensitivity_claim_boundaries_cover_nonclaims": _contains_all(
            boundary_text,
            [
                "self-selected developer-survey method-engineering",
                "model-visible feature-plus-target duplicate-split sensitivity",
                "developer-population compensation",
                "wage-gap",
                "labor-market",
                "protected-class fairness",
                "causal",
                "policy",
                "production",
                "final-selection",
                "bounded-support",
                "full-data plus/jackknife",
                "venn-abers regression validation",
            ],
        ),
        "claim_register_status_and_requirements_caveated": (
            claim.get("status") == "robustness_evidence_gate_passed_with_caveats"
            and requirement_statuses.get("complete_model_ledger") == "complete"
            and requirement_statuses.get("post_run_sidecars")
            == "present_with_endpoint_caveats"
            and requirement_statuses.get("selection_multiplicity_record")
            == "recorded_no_selection"
            and requirement_statuses.get("methodology_gate_refresh")
            == "pass_with_caveats"
        ),
        "claim_register_not_claiming_blocks_broad_claims": _contains_all(
            claim_not_claiming,
            [
                "final method/model selection",
                "developer-population compensation",
                "wage-gap",
                "protected-class fairness",
                "labor-market",
                "causal",
                "policy",
                "production",
                "final-selection",
                "nonnegative interval validity",
                "full-data plus/jackknife",
                "venn-abers regression validation",
            ],
        ),
        "endpoint_audit_complete_with_caveats": (
            endpoint_audit.get("reconstructed_runs") == STACKOVERFLOW_COMPLETED
            and endpoint_audit.get("reconstruction_failures") == 0
            and len(endpoint_method_summary) == 9
            and len(endpoint_caveat_methods) == 6
        ),
        "evidence_view_links_endpoint_states": (
            evidence_row.get("bundle_ids")
            == [
                "duplicate_cluster_sensitivity_stackoverflow_2025_compensation_log1p_age_model_visible"
            ]
            and evidence_row.get("endpoint_result_count") == 9
            and evidence_row.get("endpoint_caveat_count") == 6
            and evidence_row.get("clean_endpoint_state_count") == 3
        ),
        "robustness_table_blocks_cqr_candidate_language": _contains_all(
            robustness_text,
            [
                "keeps cqr out",
                "0/52 nominal",
                "normalized_abs",
                "exploratory",
                "not a selected method",
            ],
        ),
    }
    failed_checks = [key for key, value in checks.items() if not value]

    return {
        "claim_id": STACKOVERFLOW_MODEL_VISIBLE_CLAIM_ID,
        "report_dir": STACKOVERFLOW_MODEL_VISIBLE_REPORT_DIR,
        "missing_required_artifacts": missing_required,
        "missing_manuscript_artifacts": missing_manuscript,
        "malformed_artifacts": malformed,
        "checks": checks,
        "failed_checks": failed_checks,
        "comparison_counts": {
            "paired_rows": summary.get("paired_rows"),
            "seed_imbalanced_paired_rows": summary.get(
                "seed_imbalanced_paired_rows"
            ),
            "baseline_nominal_count": summary.get("baseline_nominal_count"),
            "sensitivity_nominal_count": summary.get("sensitivity_nominal_count"),
        },
        "method_nominal_counts": {
            name: {
                "paired_rows": row.get("paired_rows"),
                "baseline_nominal_count": row.get("baseline_nominal_count"),
                "sensitivity_nominal_count": row.get("sensitivity_nominal_count"),
            }
            for name, row in sorted(method_summaries.items())
        },
        "sensitivity_frontier": {
            "cp_method": frontier.get("cp_method"),
            "model_id": frontier.get("model_id"),
            "coverage_mean": frontier.get("coverage_mean"),
            "interval_score_mean": frontier.get("interval_score_mean"),
        },
        "claim_status": claim.get("status"),
        "claim_requirement_statuses": requirement_statuses,
        "endpoint_caveat_methods": endpoint_caveat_methods,
        "evidence_view_endpoint_counts": {
            "endpoint_result_count": evidence_row.get("endpoint_result_count"),
            "endpoint_caveat_count": evidence_row.get("endpoint_caveat_count"),
            "clean_endpoint_state_count": evidence_row.get(
                "clean_endpoint_state_count"
            ),
        },
        "synchronized": (
            not missing_required
            and not missing_manuscript
            and not malformed
            and not failed_checks
        ),
    }


def stackoverflow_checks(root: Path) -> list[dict[str, Any]]:
    report_dir = root / STACKOVERFLOW_REPORT_DIR
    config_path = root / STACKOVERFLOW_CONFIG
    pilot_path = report_dir / "pilot_summary.json"
    split_path = report_dir / "split_profile.md"
    split_json_path = report_dir / "split_profile.json"
    audit_profile_path = root / "experiments/regression/audits/stackoverflow_2025_compensation/profile.md"
    runner_path = root / "experiments/regression/scripts/run_regression_pilot.py"

    findings = []
    if pilot_path.exists():
        payload = read_json(pilot_path)
        metadata = payload.get("metadata", {})
        cardinality_evidence = {
            "ledger_rows": metadata.get("ledger_rows"),
            "unique_run_rows": metadata.get("unique_run_rows"),
            "status_counts": metadata.get("status_counts"),
            "raw_status_counts": metadata.get("raw_status_counts"),
            "summary_rows": len(payload.get("rows", [])),
            "has_candidate_frontier_rows": "candidate_frontier_rows" in payload,
            "has_legacy_best_rows": "best_rows" in payload,
        }
        ok = (
            metadata.get("ledger_rows") == STACKOVERFLOW_LEDGER_ROWS
            and metadata.get("unique_run_rows") == STACKOVERFLOW_LEDGER_ROWS
            and metadata.get("status_counts", {}).get("completed") == STACKOVERFLOW_COMPLETED
            and metadata.get("status_counts", {}).get("skipped_method")
            == STACKOVERFLOW_SKIPPED_METHOD
            and not cardinality_evidence["has_legacy_best_rows"]
        )
        findings.append(
            finding(
                "StackOverflow cardinality and frontier naming",
                "pass" if ok else "high",
                cardinality_evidence,
                "Proceed after endpoint audit." if ok else "Fix summary/cardinality drift.",
            )
        )
    else:
        findings.append(
            finding(
                "StackOverflow cardinality and frontier naming",
                "high",
                {"missing": rel(pilot_path, root)},
                "Generate pilot summary before interpreting results.",
            )
        )

    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    runner_text = runner_path.read_text(encoding="utf-8") if runner_path.exists() else ""
    split_text = split_path.read_text(encoding="utf-8") if split_path.exists() else ""
    audit_text = (
        audit_profile_path.read_text(encoding="utf-8")
        if audit_profile_path.exists()
        else ""
    )
    sparse_age = stackoverflow_sparse_age_evidence(split_json_path, split_text)
    leakage_evidence = {
        "runner_keep_columns_excludes_CompTotal": '"CompTotal"' not in _stackoverflow_keep_column_block(runner_text),
        "runner_keep_columns_excludes_Currency": '"Currency"' not in _stackoverflow_keep_column_block(runner_text),
        "runner_keep_columns_includes_target_for_y_only": '"ConvertedCompYearly"' in _stackoverflow_keep_column_block(runner_text),
        "runner_feature_drop_removes_target": "feature_drop = [target]" in runner_text,
        "runner_feature_drop_removes_group": "feature_drop.append(str(column))" in runner_text,
        "audit_documents_target_construction_drops": (
            "Target-construction drops: CompTotal, Currency" in audit_text
        ),
        "split_profile_sparse_age_caveat_present": sparse_age[
            "sparse_age_policy_documented"
        ],
        "split_profile_sparse_age_evidence": sparse_age,
        "config_forbids_population_fairness_final_claims": all(
            token in config_text
            for token in [
                "forbid_developer_population_compensation_claims",
                "forbid_protected_class_fairness_claims",
                "forbid_final_model_selection_claims",
                "forbid_validated_venn_abers_regression_claims",
            ]
        ),
    }
    leakage_ok = all(
        value for value in leakage_evidence.values() if isinstance(value, bool)
    )
    findings.append(
        finding(
            "StackOverflow leakage/drop-policy controls",
            "pass" if leakage_ok else "high",
            leakage_evidence,
            "No action." if leakage_ok else "Fix target/group/drop-policy documentation or runner handling.",
        )
    )

    feature_audit_path = report_dir / "feature_leakage_audit.json"
    if feature_audit_path.exists():
        feature_audit = read_json(feature_audit_path)
        feature_evidence = {
            "metadata_files_scanned": feature_audit.get("metadata_files_scanned"),
            "violations_count": feature_audit.get("violations_count"),
        }
        feature_ok = (
            feature_audit.get("metadata_files_scanned") == 156
            and feature_audit.get("violations_count") == 0
        )
        findings.append(
            finding(
                "StackOverflow prediction-metadata feature leakage audit",
                "pass" if feature_ok else "high",
                feature_evidence,
                "No action."
                if feature_ok
                else "Inspect prediction metadata feature leakage violations.",
            )
        )
    else:
        findings.append(
            finding(
                "StackOverflow prediction-metadata feature leakage audit",
                "high",
                {"missing": rel(feature_audit_path, root)},
                "Generate feature leakage audit before final StackOverflow writeup.",
            )
        )

    runtime_audit_path = report_dir / "runtime_cap_audit.json"
    if runtime_audit_path.exists():
        runtime_audit = read_json(runtime_audit_path)
        runtime_evidence = {
            "skipped_method_rows": runtime_audit.get("skipped_method_rows"),
            "skipped_methods": runtime_audit.get("skipped_methods"),
            "unexpected_skipped_methods": runtime_audit.get("unexpected_skipped_methods"),
            "missing_expected_skipped_methods": runtime_audit.get(
                "missing_expected_skipped_methods"
            ),
        }
        runtime_ok = (
            runtime_audit.get("skipped_method_rows") == STACKOVERFLOW_SKIPPED_METHOD
            and not runtime_audit.get("unexpected_skipped_methods")
            and not runtime_audit.get("missing_expected_skipped_methods")
        )
        findings.append(
            finding(
                "StackOverflow runtime-cap skip audit",
                "pass" if runtime_ok else "high",
                runtime_evidence,
                "No action."
                if runtime_ok
                else "Inspect unexpected skipped-method rows before interpreting plus/jackknife coverage.",
            )
        )
    else:
        findings.append(
            finding(
                "StackOverflow runtime-cap skip audit",
                "high",
                {"missing": rel(runtime_audit_path, root)},
                "Generate runtime-cap audit before final StackOverflow writeup.",
            )
        )
    model_visible_boundary = stackoverflow_model_visible_claim_boundary_status(root)
    findings.append(
        finding(
            "StackOverflow model-visible claim-boundary controls",
            "pass" if model_visible_boundary["synchronized"] else "high",
            model_visible_boundary,
            "No action."
            if model_visible_boundary["synchronized"]
            else (
                "Fix StackOverflow model-visible sidecar, claim-register, "
                "endpoint, or manuscript-boundary drift before using this "
                "bundle as robustness evidence."
            ),
        )
    )
    return findings


def split_profile_integrity_scan(root: Path) -> dict[str, Any]:
    paths = sorted((root / "experiments/regression/reports").glob("**/split_profile.json"))
    evidence: dict[str, Any] = {
        "split_profiles_scanned": len(paths),
        "dataset_profiles_scanned": 0,
        "seed_profiles_scanned": 0,
        "row_id_overlap_violations": 0,
        "split_group_overlap_violations": 0,
        "duplicate_signature_warnings": 0,
        "total_duplicate_signature_pair_overlaps": 0,
        "duplicate_signature_by_dataset": {},
        "malformed_profiles": [],
        "row_id_examples": [],
        "split_group_examples": [],
        "duplicate_signature_examples": [],
    }
    for path in paths:
        try:
            payload = read_json(path)
        except json.JSONDecodeError as exc:
            evidence["malformed_profiles"].append(
                {"path": rel(path, root), "error": f"{type(exc).__name__}: {exc}"}
            )
            continue
        profiles = payload.get("profiles", [])
        if not isinstance(profiles, list):
            evidence["malformed_profiles"].append(
                {"path": rel(path, root), "error": "profiles is not a list"}
            )
            continue
        evidence["dataset_profiles_scanned"] += len(profiles)
        for profile in profiles:
            if not isinstance(profile, dict):
                evidence["malformed_profiles"].append(
                    {"path": rel(path, root), "error": "profile entry is not an object"}
                )
                continue
            dataset_id = profile.get("dataset_id")
            split_group_col = profile.get("split_group_col")
            seeds = profile.get("seeds", [])
            if not isinstance(seeds, list):
                evidence["malformed_profiles"].append(
                    {
                        "path": rel(path, root),
                        "dataset_id": dataset_id,
                        "error": "seeds is not a list",
                    }
                )
                continue
            for seed_profile in seeds:
                if not isinstance(seed_profile, dict):
                    evidence["malformed_profiles"].append(
                        {
                            "path": rel(path, root),
                            "dataset_id": dataset_id,
                            "error": "seed entry is not an object",
                        }
                    )
                    continue
                evidence["seed_profiles_scanned"] += 1
                seed = seed_profile.get("seed")
                row_id_overlaps = seed_profile.get("row_id_overlaps") or {}
                if _positive_overlap_count(row_id_overlaps):
                    evidence["row_id_overlap_violations"] += 1
                    _append_limited(
                        evidence["row_id_examples"],
                        {
                            "path": rel(path, root),
                            "dataset_id": dataset_id,
                            "seed": seed,
                            "overlaps": row_id_overlaps,
                        },
                    )
                split_group_overlaps = seed_profile.get("split_group_overlaps") or {}
                if split_group_col and _positive_overlap_count(split_group_overlaps):
                    evidence["split_group_overlap_violations"] += 1
                    _append_limited(
                        evidence["split_group_examples"],
                        {
                            "path": rel(path, root),
                            "dataset_id": dataset_id,
                            "seed": seed,
                            "split_group_col": split_group_col,
                            "overlaps": split_group_overlaps,
                        },
                    )
                row_signature_overlaps = seed_profile.get("row_signature_overlaps") or {}
                duplicate_count = _positive_overlap_count(row_signature_overlaps)
                if duplicate_count:
                    evidence["duplicate_signature_warnings"] += 1
                    evidence["total_duplicate_signature_pair_overlaps"] += duplicate_count
                    _record_duplicate_signature_dataset_summary(
                        evidence["duplicate_signature_by_dataset"],
                        dataset_id,
                        rel(path, root),
                        duplicate_count,
                    )
                    _append_limited(
                        evidence["duplicate_signature_examples"],
                        {
                            "path": rel(path, root),
                            "dataset_id": dataset_id,
                            "seed": seed,
                            "overlaps": row_signature_overlaps,
                        },
                    )
    return evidence


def duplicate_split_caveat_backlog_status(
    root: Path,
    split_integrity: dict[str, Any],
) -> dict[str, Any]:
    expected_by_dataset = split_integrity.get("duplicate_signature_by_dataset") or {}
    expected_datasets = sorted(str(key) for key in expected_by_dataset)
    expected_total = int(split_integrity.get("total_duplicate_signature_pair_overlaps") or 0)
    path = root / DUPLICATE_SPLIT_CAVEAT_BACKLOG
    evidence: dict[str, Any] = {
        "path": DUPLICATE_SPLIT_CAVEAT_BACKLOG,
        "expected_dataset_count": len(expected_datasets),
        "expected_datasets": expected_datasets,
        "expected_total_duplicate_signature_pair_overlaps": expected_total,
        "present": path.exists(),
        "schema": None,
        "actual_dataset_count": None,
        "actual_datasets": [],
        "actual_total_duplicate_signature_pair_overlaps": None,
        "row_id_overlap_violation_seed_profiles": None,
        "split_group_overlap_violation_seed_profiles": None,
        "malformed": None,
        "synchronized": False,
    }
    if not expected_datasets:
        evidence["synchronized"] = not path.exists()
        return evidence
    if not path.exists():
        return evidence
    try:
        payload = read_json(path)
    except json.JSONDecodeError as exc:
        evidence["malformed"] = f"{type(exc).__name__}: {exc}"
        return evidence
    rows = payload.get("rows", []) or []
    summary = payload.get("summary", {}) or {}
    actual_datasets = sorted(str(row.get("dataset_id")) for row in rows)
    evidence.update(
        {
            "schema": payload.get("schema"),
            "actual_dataset_count": len(actual_datasets),
            "actual_datasets": actual_datasets,
            "actual_total_duplicate_signature_pair_overlaps": int(
                summary.get("total_duplicate_signature_pair_overlaps") or 0
            ),
            "row_id_overlap_violation_seed_profiles": int(
                summary.get("row_id_overlap_violation_seed_profiles") or 0
            ),
            "split_group_overlap_violation_seed_profiles": int(
                summary.get("split_group_overlap_violation_seed_profiles") or 0
            ),
            "malformed": None,
        }
    )
    evidence["synchronized"] = (
        evidence["schema"] == "cpfi_duplicate_split_caveat_backlog_v1"
        and actual_datasets == expected_datasets
        and evidence["actual_total_duplicate_signature_pair_overlaps"] == expected_total
        and evidence["row_id_overlap_violation_seed_profiles"] == 0
        and evidence["split_group_overlap_violation_seed_profiles"] == 0
    )
    return evidence


def paired_duplicate_sensitivity_audit_status(root: Path) -> dict[str, Any]:
    backlog_path = root / DUPLICATE_SPLIT_CAVEAT_BACKLOG
    audit_path = root / PAIRED_DUPLICATE_SENSITIVITY_AUDIT
    evidence: dict[str, Any] = {
        "path": PAIRED_DUPLICATE_SENSITIVITY_AUDIT,
        "source_backlog_path": DUPLICATE_SPLIT_CAVEAT_BACKLOG,
        "expected_paired_datasets": [],
        "expected_paired_dataset_count": 0,
        "present": audit_path.exists(),
        "schema": None,
        "actual_paired_datasets": [],
        "actual_paired_dataset_count": None,
        "paired_comparison_rows": None,
        "raw_only_rows": None,
        "dedup_only_rows": None,
        "nominal_status_change_count": None,
        "malformed": None,
        "synchronized": False,
    }
    if not backlog_path.exists():
        evidence["malformed"] = "missing duplicate split caveat backlog"
        return evidence
    try:
        backlog = read_json(backlog_path)
    except json.JSONDecodeError as exc:
        evidence["malformed"] = f"backlog {type(exc).__name__}: {exc}"
        return evidence
    expected = sorted(
        str(row.get("dataset_id"))
        for row in backlog.get("rows", []) or []
        if row.get("paired_dedup_variant_available")
        and row.get("paired_dedup_variant_dataset_id")
    )
    evidence["expected_paired_datasets"] = expected
    evidence["expected_paired_dataset_count"] = len(expected)
    if not expected:
        evidence["synchronized"] = not audit_path.exists()
        return evidence
    if not audit_path.exists():
        return evidence
    try:
        audit = read_json(audit_path)
    except json.JSONDecodeError as exc:
        evidence["malformed"] = f"audit {type(exc).__name__}: {exc}"
        return evidence
    summary = audit.get("summary", {}) or {}
    actual = sorted(
        str(item.get("raw_dataset_id"))
        for item in summary.get("datasets", []) or []
    )
    evidence.update(
        {
            "schema": audit.get("schema"),
            "actual_paired_datasets": actual,
            "actual_paired_dataset_count": int(summary.get("paired_dataset_count") or 0),
            "paired_comparison_rows": int(summary.get("paired_comparison_rows") or 0),
            "raw_only_rows": int(summary.get("raw_only_rows") or 0),
            "dedup_only_rows": int(summary.get("dedup_only_rows") or 0),
            "nominal_status_change_count": int(
                summary.get("nominal_status_change_count") or 0
            ),
            "malformed": None,
        }
    )
    evidence["synchronized"] = (
        evidence["schema"] == "cpfi_paired_duplicate_sensitivity_audit_v1"
        and actual == expected
        and evidence["actual_paired_dataset_count"] == len(expected)
        and evidence["paired_comparison_rows"] > 0
        and evidence["raw_only_rows"] == 0
        and evidence["dedup_only_rows"] == 0
    )
    return evidence


def cross_run_integrity_audit_status(
    root: Path,
    pilot_paths: list[Path],
) -> dict[str, Any]:
    expected_report_paths = [
        path for path in pilot_paths if not is_root_aggregate_pilot_summary(path, root)
    ]
    path = root / CROSS_RUN_INTEGRITY_AUDIT
    evidence: dict[str, Any] = {
        "path": CROSS_RUN_INTEGRITY_AUDIT,
        "expected_report_count": len(expected_report_paths),
        "present": path.exists(),
        "schema": None,
        "actual_report_count": None,
        "risk_counts": {},
        "blocking_issue_counts": {},
        "caveat_counts": {},
        "unsupported_claim_hits": None,
        "leakage_status": None,
        "malformed": None,
        "synchronized": False,
    }
    if not path.exists():
        return evidence
    try:
        payload = read_json(path)
    except json.JSONDecodeError as exc:
        evidence["malformed"] = f"{type(exc).__name__}: {exc}"
        return evidence
    summary = payload.get("summary", {}) or {}
    blocking_issue_counts = summary.get("blocking_issue_counts") or {}
    evidence.update(
        {
            "schema": payload.get("schema"),
            "actual_report_count": int(summary.get("reports_scanned") or 0),
            "risk_counts": summary.get("risk_counts") or {},
            "blocking_issue_counts": blocking_issue_counts,
            "caveat_counts": summary.get("caveat_counts") or {},
            "unsupported_claim_hits": int(summary.get("unsupported_claim_hits") or 0),
            "leakage_status": summary.get("leakage_status"),
            "malformed": None,
        }
    )
    evidence["synchronized"] = (
        evidence["schema"] == "cpfi_cross_run_integrity_audit_v1"
        and evidence["actual_report_count"] == evidence["expected_report_count"]
        and not blocking_issue_counts
        and evidence["unsupported_claim_hits"] == 0
    )
    return evidence


def integrity_remediation_backlog_status(root: Path) -> dict[str, Any]:
    cross_run_path = root / CROSS_RUN_INTEGRITY_AUDIT
    backlog_path = root / INTEGRITY_REMEDIATION_BACKLOG
    evidence: dict[str, Any] = {
        "path": INTEGRITY_REMEDIATION_BACKLOG,
        "source_cross_run_integrity_audit_path": CROSS_RUN_INTEGRITY_AUDIT,
        "present": backlog_path.exists(),
        "schema": None,
        "expected_issue_counts": {},
        "actual_issue_counts": {},
        "expected_action_count": 0,
        "expected_open_action_count": 0,
        "actual_action_count": None,
        "actual_open_action_count": None,
        "actual_covered_action_count": None,
        "status_counts": {},
        "severity_counts": {},
        "category_counts": {},
        "malformed": None,
        "synchronized": False,
    }
    if not cross_run_path.exists():
        evidence["malformed"] = "missing cross-run integrity audit"
        return evidence
    try:
        cross_run = read_json(cross_run_path)
    except json.JSONDecodeError as exc:
        evidence["malformed"] = f"cross-run {type(exc).__name__}: {exc}"
        return evidence
    expected: Counter[str] = Counter()
    summary = cross_run.get("summary", {}) or {}
    for key in ("blocking_issue_counts", "caveat_counts"):
        expected.update(
            {
                str(issue): int(count)
                for issue, count in (summary.get(key) or {}).items()
            }
        )
    evidence["expected_issue_counts"] = dict(sorted(expected.items()))
    evidence["expected_action_count"] = sum(expected.values())
    evidence["expected_open_action_count"] = sum(expected.values())
    if not backlog_path.exists():
        return evidence
    try:
        backlog = read_json(backlog_path)
    except json.JSONDecodeError as exc:
        evidence["malformed"] = f"backlog {type(exc).__name__}: {exc}"
        return evidence
    backlog_summary = backlog.get("summary", {}) or {}
    actual_issue_counts = {
        str(issue): int(count)
        for issue, count in (backlog_summary.get("issue_counts") or {}).items()
    }
    evidence.update(
        {
            "schema": backlog.get("schema"),
            "actual_issue_counts": dict(sorted(actual_issue_counts.items())),
            "actual_action_count": int(
                backlog_summary.get("action_count")
                or backlog_summary.get("open_action_count")
                or 0
            ),
            "actual_open_action_count": int(
                backlog_summary.get("open_action_count") or 0
            ),
            "actual_covered_action_count": int(
                backlog_summary.get("covered_action_count") or 0
            ),
            "status_counts": backlog_summary.get("status_counts") or {},
            "severity_counts": backlog_summary.get("severity_counts") or {},
            "category_counts": backlog_summary.get("category_counts") or {},
            "malformed": None,
        }
    )
    evidence["synchronized"] = (
        evidence["schema"] == "cpfi_integrity_remediation_backlog_v1"
        and evidence["actual_issue_counts"] == evidence["expected_issue_counts"]
        and evidence["actual_action_count"] == evidence["expected_action_count"]
        and bool(backlog_summary.get("issue_counts_match_cross_run"))
    )
    return evidence


def _record_duplicate_signature_dataset_summary(
    by_dataset: dict[str, Any],
    dataset_id: Any,
    path: str,
    duplicate_count: int,
) -> None:
    key = str(dataset_id)
    item = by_dataset.setdefault(
        key,
        {"seed_profiles": 0, "total_pair_overlaps": 0, "paths": []},
    )
    item["seed_profiles"] += 1
    item["total_pair_overlaps"] += duplicate_count
    if path not in item["paths"] and len(item["paths"]) < 5:
        item["paths"].append(path)


def _positive_overlap_count(overlaps: Any) -> int:
    if not isinstance(overlaps, dict):
        return 0
    total = 0
    for value in overlaps.values():
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count > 0:
            total += count
    return total


def _append_limited(items: list[Any], item: Any, limit: int = 20) -> None:
    if len(items) < limit:
        items.append(item)


def _contains_all(text: str, tokens: list[str]) -> bool:
    lowered = text.lower()
    return all(token.lower() in lowered for token in tokens)


def _read_json_for_evidence(
    path: Path,
    root: Path,
    malformed: list[dict[str, str]],
) -> dict[str, Any]:
    try:
        return read_json(path)
    except json.JSONDecodeError as exc:
        malformed.append(
            {
                "path": rel(path, root),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return {}


def feature_leakage_sidecar_scan(root: Path) -> dict[str, Any]:
    paths = sorted((root / "experiments/regression/reports").glob("**/feature_leakage_audit.json"))
    evidence: dict[str, Any] = {
        "reports_scanned": len(paths),
        "metadata_files_scanned": 0,
        "metadata_completeness_totals": {
            "missing_feature_names": 0,
            "missing_preprocessed_feature_names": 0,
            "missing_feature_drop_columns": 0,
            "missing_feature_drop_policy": 0,
        },
        "violations_count": 0,
        "malformed_reports": [],
        "schema_violations": [],
        "empty_reports": [],
        "violation_examples": [],
        "report_summaries": [],
    }
    for path in paths:
        try:
            payload = read_json(path)
        except json.JSONDecodeError as exc:
            _append_limited(
                evidence["malformed_reports"],
                {"path": rel(path, root), "error": f"{type(exc).__name__}: {exc}"},
            )
            continue
        metadata_count = int(payload.get("metadata_files_scanned") or 0)
        violation_count = int(payload.get("violations_count") or 0)
        schema = payload.get("schema")
        metadata_completeness = payload.get("metadata_completeness") or {}
        for key in evidence["metadata_completeness_totals"]:
            evidence["metadata_completeness_totals"][key] += int(
                metadata_completeness.get(key) or 0
            )
        if schema not in FEATURE_LEAKAGE_AUDIT_SCHEMAS:
            _append_limited(
                evidence["schema_violations"],
                {"path": rel(path, root), "schema": schema},
            )
        if metadata_count <= 0:
            _append_limited(
                evidence["empty_reports"],
                {"path": rel(path, root), "metadata_files_scanned": metadata_count},
            )
        evidence["metadata_files_scanned"] += metadata_count
        evidence["violations_count"] += violation_count
        _append_limited(
            evidence["report_summaries"],
            {
                "path": rel(path, root),
                "schema": schema,
                "metadata_files_scanned": metadata_count,
                "metadata_completeness": metadata_completeness,
                "violations_count": violation_count,
            },
        )
        for violation in payload.get("violations", []) or []:
            _append_limited(
                evidence["violation_examples"],
                {"path": rel(path, root), "violation": violation},
            )
    return evidence


def _stackoverflow_keep_column_block(runner_text: str) -> str:
    match = re.search(
        r'"stackoverflow_2025_compensation":\s*\{.*?"keep_columns":\s*\[(.*?)\]\s*,',
        runner_text,
        flags=re.DOTALL,
    )
    return match.group(1) if match else ""


def stackoverflow_sparse_age_evidence(
    split_json_path: Path,
    split_text: str,
    *,
    threshold: int = 10,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "split_profile_json_present": split_json_path.exists(),
        "sparse_threshold": threshold,
        "sparse_age_cells": [],
        "sparse_age_cell_count": 0,
        "sparse_cal_or_test_age_cell_count": 0,
        "markdown_sparse_diagnostic_caveat_present": (
            "sparse" in split_text.lower() and "diagnostic" in split_text.lower()
        ),
        "malformed": None,
        "sparse_age_policy_documented": False,
    }
    if not split_json_path.exists():
        return evidence
    try:
        payload = read_json(split_json_path)
    except json.JSONDecodeError as exc:
        evidence["malformed"] = f"{type(exc).__name__}: {exc}"
        return evidence

    cells: list[dict[str, Any]] = []
    for profile in payload.get("profiles", []) or []:
        if profile.get("dataset_id") != "stackoverflow_2025_compensation":
            continue
        if profile.get("primary_group") != "Age":
            continue
        for seed_profile in profile.get("seeds", []) or []:
            seed = int(seed_profile.get("seed"))
            explicit_cells = seed_profile.get("sparse_primary_group_cells")
            if isinstance(explicit_cells, list):
                for cell in explicit_cells:
                    cells.append(
                        {
                            "seed": seed,
                            "split": cell.get("split"),
                            "group": cell.get("group"),
                            "count": int(cell.get("count") or 0),
                            "threshold": int(cell.get("threshold") or threshold),
                        }
                    )
                continue
            for split_name, split in (seed_profile.get("splits") or {}).items():
                group_counts = (split or {}).get("group_counts") or {}
                for group, count in group_counts.items():
                    count_int = int(count or 0)
                    if count_int < threshold:
                        cells.append(
                            {
                                "seed": seed,
                                "split": str(split_name),
                                "group": str(group),
                                "count": count_int,
                                "threshold": threshold,
                            }
                        )

    evidence["sparse_age_cells"] = cells[:24]
    evidence["sparse_age_cell_count"] = len(cells)
    evidence["sparse_cal_or_test_age_cell_count"] = sum(
        1 for cell in cells if cell["split"] in {"cal", "test"}
    )
    evidence["sparse_age_policy_documented"] = (
        evidence["sparse_cal_or_test_age_cell_count"] == 0
        or evidence["markdown_sparse_diagnostic_caveat_present"]
    )
    return evidence


UNSUPPORTED_CLAIM_SCAN_ROOTS = (
    "README.md",
    "experiments/regression/README.md",
    "experiments/regression/CHANGELOG.md",
    "experiments/regression/manuscript",
    "experiments/regression/reports",
    "experiments/regression/catalogs",
)


def unsupported_claim_scan(root: Path) -> list[dict[str, Any]]:
    patterns = [
        re.compile(r"\bvalidated Venn-Abers regression\b", re.IGNORECASE),
        re.compile(r"\bfinal model selection\b", re.IGNORECASE),
        re.compile(r"\bproduction evidence\b", re.IGNORECASE),
        re.compile(r"\bprotected-class fairness evidence\b", re.IGNORECASE),
        re.compile(r"\bcausal evidence\b", re.IGNORECASE),
    ]
    negators = (
        "avoid",
        "boundary",
        "cannot",
        "claim should",
        "claims should",
        "diagnostic",
        "do not",
        "forbid",
        "forbidden_claims",
        "forbidden claims",
        "no ",
        "non-claim",
        "not ",
        "not yet support",
        "not_",
        "only",
        "rather than",
        "triage",
        "without",
    )
    hits = []
    scan_roots = [root / path for path in UNSUPPORTED_CLAIM_SCAN_ROOTS]
    files: list[Path] = []
    for scan_root in scan_roots:
        if scan_root.is_file():
            files.append(scan_root)
        elif scan_root.exists():
            files.extend(
                path
                for path in scan_root.glob("**/*")
                if path.suffix in {".md", ".json", ".jsonl"}
            )
    for path in sorted(files):
        if "methodology_sanity_audit_20260627" in str(path):
            continue
        if rel(path, root) == "experiments/regression/catalogs/knowledge_graph.json":
            # KG is a generated derivative with a dedicated ontology/provenance audit.
            # Text-claim linting belongs on authoring surfaces to avoid stale
            # derivative snapshots breaking the gate before the KG rebuild step.
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, start=1):
            window = "\n".join(
                lines[max(0, line_no - 14) : min(len(lines), line_no + 3)]
            ).lower()
            for pattern in patterns:
                if pattern.search(line) and not any(token in window for token in negators):
                    hits.append(
                        {
                            "path": rel(path, root),
                            "line": line_no,
                            "pattern": pattern.pattern,
                            "text": line.strip()[:240],
                        }
                    )
    return hits[:100]


def legacy_best_rows_backlog(payloads: list[dict[str, Any]], root: Path) -> list[str]:
    paths = []
    for item in payloads:
        payload = item["payload"]
        if "best_rows" in payload:
            paths.append(rel(item["path"], root))
    return paths


def build_payload(root: Path) -> dict[str, Any]:
    config_rows = scan_configs(root)
    pilot_paths, pilot_payloads = scan_pilot_summaries(root)
    large_payloads = [
        item
        for item in pilot_payloads
        if pilot_completed_count(item["payload"]) >= LARGE_COMPLETED_THRESHOLD
    ]
    endpoint_path = root / STACKOVERFLOW_REPORT_DIR / "endpoint_audit.json"
    endpoint_status = "present" if endpoint_path.exists() else "missing_at_generation"

    findings = []
    failed_examples = failed_summary_examples(pilot_payloads, root)
    findings.append(
        finding(
            "Pilot summaries failed-run scan",
            "pass" if not failed_examples else "high",
            {"failed_summary_count": len(failed_examples), "examples": failed_examples[:20]},
            "No failed rows found in pilot summaries."
            if not failed_examples
            else "Inspect failed pilot summaries before using them as evidence.",
        )
    )
    findings.extend(stackoverflow_checks(root))

    endpoint_backlog = large_summary_backlog(pilot_payloads, root, "endpoint_audit.json")
    findings.append(
        finding(
            "Large-sweep endpoint-audit backlog",
            "pass" if not endpoint_backlog else "medium",
            endpoint_backlog,
            "All large sweeps have endpoint audits."
            if not endpoint_backlog
            else "Generate endpoint audits before original-scale support/boundedness interpretation.",
        )
    )

    split_backlog = large_summary_backlog(pilot_payloads, root, "split_profile.json")
    findings.append(
        finding(
            "Large-sweep split-profile backlog",
            "pass" if not split_backlog else "medium",
            split_backlog,
            "All large sweeps have split profiles."
            if not split_backlog
            else "Generate split profiles before group-gap stability interpretation.",
        )
    )

    split_integrity = split_profile_integrity_scan(root)
    hard_split_leakage = (
        split_integrity["row_id_overlap_violations"]
        or split_integrity["split_group_overlap_violations"]
        or split_integrity["malformed_profiles"]
    )
    duplicate_signature_warnings = split_integrity["duplicate_signature_warnings"]
    findings.append(
        finding(
            "Split-profile leakage integrity scan",
            "high"
            if hard_split_leakage
            else "medium"
            if duplicate_signature_warnings
            else "pass",
            split_integrity,
            "Fix row-id/group overlap or malformed split profiles before using affected reports."
            if hard_split_leakage
            else (
                "Treat duplicate-content overlaps as a duplicate-sensitivity caveat; "
                "avoid strong split-independence claims for affected datasets."
            )
            if duplicate_signature_warnings
            else "No row-id, split-group, or duplicate-signature overlaps detected.",
        )
    )
    duplicate_backlog = duplicate_split_caveat_backlog_status(root, split_integrity)
    findings.append(
        finding(
            "Duplicate split caveat backlog artifact",
            "pass"
            if duplicate_backlog["synchronized"]
            else "medium"
            if duplicate_backlog["expected_dataset_count"]
            else "pass",
            duplicate_backlog,
            "Duplicate-content caveat backlog is synchronized with the split-profile integrity scan."
            if duplicate_backlog["synchronized"]
            else "Generate duplicate_split_caveat_backlog.json from split profiles before treating duplicate-content caveats as tracked follow-up work."
            if duplicate_backlog["expected_dataset_count"]
            else "No duplicate-content caveat backlog is required.",
        )
    )
    paired_duplicate_audit = paired_duplicate_sensitivity_audit_status(root)
    findings.append(
        finding(
            "Paired duplicate sensitivity audit artifact",
            "pass"
            if paired_duplicate_audit["synchronized"]
            else "medium"
            if paired_duplicate_audit["expected_paired_dataset_count"]
            else "pass",
            paired_duplicate_audit,
            "Paired raw-vs-dedup duplicate sensitivity audit is synchronized with the duplicate caveat backlog."
            if paired_duplicate_audit["synchronized"]
            else "Generate paired_duplicate_sensitivity_audit.json for backlog rows that already have paired dedup variants."
            if paired_duplicate_audit["expected_paired_dataset_count"]
            else "No paired duplicate sensitivity audit is required.",
        )
    )
    cross_run_integrity = cross_run_integrity_audit_status(root, pilot_paths)
    findings.append(
        finding(
            "Cross-run scientific integrity audit artifact",
            "pass"
            if cross_run_integrity["synchronized"]
            else "high"
            if cross_run_integrity["blocking_issue_counts"]
            else "medium",
            cross_run_integrity,
            "Cross-run integrity audit is synchronized and records no blocking leakage or claim issues."
            if cross_run_integrity["synchronized"]
            else "Inspect cross_run_integrity_audit.json; blocking issues or stale report counts prevent treating the retrospective matrix as current.",
        )
    )
    remediation_backlog = integrity_remediation_backlog_status(root)
    findings.append(
        finding(
            "Integrity remediation backlog artifact",
            "pass"
            if remediation_backlog["synchronized"]
            else "medium"
            if remediation_backlog["expected_open_action_count"]
            else "pass",
            remediation_backlog,
            "Integrity remediation backlog is synchronized with the cross-run integrity audit issue counts."
            if remediation_backlog["synchronized"]
            else "Generate integrity_remediation_backlog.json from the cross-run audit before treating caveats as an actionable queue."
            if remediation_backlog["expected_open_action_count"]
            else "No integrity remediation backlog is required.",
        )
    )

    guardrails = guardrail_backlog(config_rows, root)
    findings.append(
        finding(
            "Model-family VA/CQR guardrail backfill backlog",
            "pass"
            if not guardrails["model_family_va_missing"]
            and not guardrails["model_family_cqr_missing"]
            else "medium",
            guardrails,
            "No model-family guardrail backfill required."
            if not guardrails["model_family_va_missing"]
            and not guardrails["model_family_cqr_missing"]
            else "Backfill before rerunning/reusing these configs as primary evidence.",
        )
    )

    control_contract = model_family_control_contract_backlog(config_rows, root)
    findings.append(
        finding(
            "Model-family scientific control contract backlog",
            "pass"
            if not control_contract["missing_by_config"]
            else "medium",
            control_contract,
            "All model-family configs carry the required resume, audit, cache, parameter-summary, and triage-only controls."
            if not control_contract["missing_by_config"]
            else "Backfill missing quality_controls before treating affected configs as current primary evidence.",
        )
    )

    feature_sidecars = feature_leakage_sidecar_scan(root)
    feature_sidecar_ok = (
        not feature_sidecars["malformed_reports"]
        and not feature_sidecars["schema_violations"]
        and not feature_sidecars["empty_reports"]
        and feature_sidecars["violations_count"] == 0
    )
    findings.append(
        finding(
            "Prediction-metadata feature leakage sidecar scan",
            "pass" if feature_sidecar_ok else "high",
            feature_sidecars,
            "All discovered feature-leakage sidecars are parseable and have zero recorded violations."
            if feature_sidecar_ok
            else "Inspect malformed feature-leakage sidecars or prediction-metadata violations before interpreting affected reports.",
        )
    )

    feature_drop_guard = runner_feature_drop_guard_scan(root)
    feature_drop_ok = (
        feature_drop_guard["fit_block_found"]
        and feature_drop_guard["drops_target_before_preprocessing"]
        and feature_drop_guard["drops_primary_group_when_present"]
        and feature_drop_guard["drops_split_group_when_present"]
        and feature_drop_guard["drops_base_split_group_when_present"]
        and feature_drop_guard["drops_loader_extra_feature_drop_columns"]
        and feature_drop_guard["deduplicates_feature_drop_columns"]
    )
    findings.append(
        finding(
            "Runner feature-matrix leakage guard scan",
            "pass" if feature_drop_ok else "high",
            feature_drop_guard,
            "Runner source still drops target, primary group, split group, and loader extra feature-drop columns before preprocessing."
            if feature_drop_ok
            else "Inspect run_regression_pilot.py feature_drop handling before trusting new sweeps.",
        )
    )

    loader_policy = config_loader_leakage_policy_scan(config_rows, root)
    model_family_policy_backlog = (
        loader_policy["unknown_dataset_refs"]
        or loader_policy["missing_loader_target_or_group"]
        or loader_policy["model_family_extra_target_boundary_missing"]
        or loader_policy["model_family_derived_group_source_policy_missing"]
    )
    legacy_policy_backlog = (
        loader_policy["legacy_extra_target_boundary_weak"]
        or loader_policy["legacy_derived_group_source_policy_weak"]
    )
    findings.append(
        finding(
            "Config/loader leakage-policy consistency scan",
            "high"
            if loader_policy["unknown_dataset_refs"]
            or loader_policy["missing_loader_target_or_group"]
            else "medium"
            if model_family_policy_backlog or legacy_policy_backlog
            else "pass",
            loader_policy,
            "No config/loader leakage-policy inconsistencies detected."
            if not model_family_policy_backlog and not legacy_policy_backlog
            else "Backfill model-family policy gaps before primary interpretation."
            if model_family_policy_backlog
            else "No model-family policy gaps; treat legacy smoke gaps as historical caveats.",
        )
    )

    legacy_best_rows = legacy_best_rows_backlog(pilot_payloads, root)
    findings.append(
        finding(
            "Legacy pilot_summary best_rows naming backlog",
            "pass" if not legacy_best_rows else "low",
            {"count": len(legacy_best_rows), "examples": legacy_best_rows[:20]},
            "No legacy naming backlog."
            if not legacy_best_rows
            else "Regenerate reports when touched so JSON uses candidate_frontier_rows.",
        )
    )

    unsupported_hits = unsupported_claim_scan(root)
    findings.append(
        finding(
            "High-confidence unsupported-claim wording scan",
            "pass" if not unsupported_hits else "medium",
            unsupported_hits,
            "No high-confidence unsupported assertive claims found by targeted scan."
            if not unsupported_hits
            else "Review claim wording and add explicit non-claim boundaries.",
        )
    )

    return {
        "schema": "cpfi_methodology_sanity_audit_v8",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "configs_scanned": len(config_rows),
        "pilot_summaries_scanned": len(pilot_paths),
        "large_summaries_scanned": len(large_payloads),
        "endpoint_audit_status": endpoint_status,
        "findings": findings,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Regression Methodology Sanity Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Configs scanned: {payload['configs_scanned']}",
        f"- Pilot summaries scanned: {payload['pilot_summaries_scanned']}",
        f"- Large summaries scanned: {payload['large_summaries_scanned']}",
        f"- StackOverflow endpoint audit status at generation: `{payload['endpoint_audit_status']}`",
        "",
        "## Findings",
        "",
    ]
    for item in payload["findings"]:
        lines.extend(
            [
                f"- **{item['severity']}** {item['title']}",
                f"  Evidence: `{json.dumps(item['evidence'], sort_keys=True, default=str)}`",
                f"  Action: {item['action']}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_dir = (root / args.out_dir).resolve()
    payload = build_payload(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "sanity_audit.json", payload)
    atomic_write_text(out_dir / "sanity_audit.md", render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "findings": len(payload["findings"]),
                "endpoint_audit_status": payload["endpoint_audit_status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
