"""Build a retrospective scientific-control dashboard for regression CP runs.

This script compresses the cross-run integrity matrix into a smaller set of
study-level control checks. It is deliberately read-only over experiment
outputs: it does not rerun models, edit ledgers, or reinterpret performance
frontiers.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts import audit_cross_run_integrity as cross_run


SCHEMA = "cpfi_retrospective_methodology_controls_v1"
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "retrospective_methodology_controls.json"
)

CLAIM_BOUNDARIES = [
    "This dashboard audits methodology controls; it is not a new model-performance result.",
    "Duplicate-signature overlaps are tracked as interpretation caveats, not hard data leakage without row-id or split-group overlap evidence.",
    "Feature-leakage closure is limited to the prediction metadata and loader/drop-policy evidence available in scanned artifacts.",
    "Endpoint v2 closure means endpoint reconstruction integrity for completed ledger rows, not bounded-support validity or production readiness.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output JSON path.")
    return parser.parse_args()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def counter_get(counter: dict[str, Any], *keys: str) -> int:
    return sum(safe_int(counter.get(key)) for key in keys)


def rows_with_labels(
    rows: list[dict[str, Any]],
    *,
    field: str,
    labels: set[str],
    limit: int = 12,
) -> list[dict[str, Any]]:
    examples = []
    for row in rows:
        row_labels = {str(value) for value in row.get(field, []) or []}
        matched = sorted(row_labels.intersection(labels))
        if not matched:
            continue
        examples.append(
            {
                "report_id": row.get("report_id"),
                "report_name": row.get("report_name"),
                "matched_labels": matched,
                "completed": safe_int((row.get("status_counts") or {}).get("completed")),
            }
        )
        if len(examples) >= limit:
            break
    return examples


def endpoint_schema_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        endpoint = row.get("endpoint_audit") or {}
        if not endpoint.get("present"):
            counts["missing"] += 1
            continue
        schema = str(endpoint.get("schema") or "unknown")
        if schema == "cpfi_regression_endpoint_audit_v2":
            if endpoint.get("full_method_coverage") is True:
                counts["v2_full_method_coverage"] += 1
            else:
                counts["v2_partial_method_coverage"] += 1
        else:
            counts["legacy_or_unknown_schema"] += 1
    return dict(sorted(counts.items()))


def split_schema_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        split = row.get("split_profile") or {}
        if not split.get("present"):
            counts["missing"] += 1
            continue
        schema = str(split.get("schema") or "unknown")
        if schema == "cpfi_regression_split_profile_v2":
            counts["v2"] += 1
        else:
            counts["legacy_or_unknown_schema"] += 1
    return dict(sorted(counts.items()))


def feature_sidecar_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        feature = row.get("feature_leakage_audit") or {}
        if not feature.get("present"):
            counts["missing"] += 1
            continue
        if safe_int(feature.get("violations_count")):
            counts["present_with_violation"] += 1
        elif safe_int(feature.get("missing_metadata_field_total")):
            counts["present_with_metadata_caveat"] += 1
        else:
            counts["present_clean_available_metadata"] += 1
    return dict(sorted(counts.items()))


def control(
    control_id: str,
    family: str,
    status: str,
    severity: str,
    evidence: dict[str, Any],
    next_action: str,
) -> dict[str, Any]:
    return {
        "control_id": control_id,
        "family": family,
        "status": status,
        "severity": severity,
        "evidence": evidence,
        "next_action": next_action,
    }


def status_from_fail_caveat(fail_count: int, caveat_count: int) -> tuple[str, str]:
    if fail_count:
        return "fail", "high"
    if caveat_count:
        return "caveat", "medium"
    return "pass", "none"


def build_controls_from_cross_run(cross_payload: dict[str, Any]) -> list[dict[str, Any]]:
    summary = cross_payload.get("summary") or {}
    rows = cross_payload.get("rows") or []
    blocking = summary.get("blocking_issue_counts") or {}
    caveats = summary.get("caveat_counts") or {}
    layers = cross_payload.get("study_level_layers") or {}

    failed_rows = counter_get(blocking, "failed_rows_present")
    status, severity = status_from_fail_caveat(failed_rows, 0)
    controls = [
        control(
            "ledger_status_integrity",
            "ledger",
            status,
            severity,
            {
                "failed_rows_present": failed_rows,
                "examples": rows_with_labels(
                    rows,
                    field="blocking_issues",
                    labels={"failed_rows_present"},
                ),
            },
            "Inspect failed rows and document controlled skip semantics before interpreting affected reports.",
        )
    ]

    hard_split = counter_get(
        blocking,
        "row_id_overlap_detected",
        "split_group_overlap_detected",
    )
    status, severity = status_from_fail_caveat(hard_split, 0)
    split_scan = layers.get("split_profile_integrity_scan") or {}
    controls.append(
        control(
            "hard_split_leakage_absence",
            "split",
            status,
            severity,
            {
                "row_id_overlap_detected_reports": counter_get(
                    blocking, "row_id_overlap_detected"
                ),
                "split_group_overlap_detected_reports": counter_get(
                    blocking, "split_group_overlap_detected"
                ),
                "seed_profile_row_id_overlap_violations": safe_int(
                    split_scan.get("row_id_overlap_violations")
                ),
                "seed_profile_split_group_overlap_violations": safe_int(
                    split_scan.get("split_group_overlap_violations")
                ),
                "examples": rows_with_labels(
                    rows,
                    field="blocking_issues",
                    labels={"row_id_overlap_detected", "split_group_overlap_detected"},
                ),
            },
            "Regenerate affected splits and block interpretation until row-id and split-group overlaps are zero.",
        )
    )

    split_schema_caveats = counter_get(
        caveats,
        "legacy_split_profile_schema_partial_integrity",
        "large_sweep_missing_split_profile",
    )
    status, severity = status_from_fail_caveat(
        counter_get(blocking, "split_profile_malformed"),
        split_schema_caveats,
    )
    controls.append(
        control(
            "split_profile_schema_closure",
            "split",
            status,
            severity,
            {
                "split_schema_counts": split_schema_counts(rows),
                "legacy_or_missing_caveats": split_schema_caveats,
                "malformed_profiles": counter_get(blocking, "split_profile_malformed"),
                "examples": rows_with_labels(
                    rows,
                    field="caveats",
                    labels={
                        "legacy_split_profile_schema_partial_integrity",
                        "large_sweep_missing_split_profile",
                    },
                ),
            },
            "Regenerate missing or legacy split profiles through the v2 split audit path.",
        )
    )

    duplicate_caveats = counter_get(
        caveats,
        "duplicate_signature_cross_split_caveat",
        "model_visible_signature_cross_split_caveat",
    )
    status, severity = status_from_fail_caveat(0, duplicate_caveats)
    controls.append(
        control(
            "duplicate_signature_sensitivity_tracking",
            "split",
            status,
            severity,
            {
                "duplicate_caveated_reports": duplicate_caveats,
                "seed_profile_duplicate_signature_warnings": safe_int(
                    split_scan.get("duplicate_signature_warnings")
                ),
                "duplicate_signature_pair_overlaps": safe_int(
                    split_scan.get("total_duplicate_signature_pair_overlaps")
                ),
                "examples": rows_with_labels(
                    rows,
                    field="caveats",
                    labels={
                        "duplicate_signature_cross_split_caveat",
                        "model_visible_signature_cross_split_caveat",
                    },
                ),
            },
            "Keep duplicate-aware sensitivity rows in the backlog; do not call these hard leakage unless row-id or split-group overlap appears.",
        )
    )

    plus_internal_fold_caveats = counter_get(
        caveats,
        "duplicate_cluster_plus_family_internal_fold_caveat",
    )
    status, severity = status_from_fail_caveat(0, plus_internal_fold_caveats)
    controls.append(
        control(
            "plus_family_duplicate_cluster_internal_fold_boundary",
            "split",
            status,
            severity,
            {
                "duplicate_cluster_plus_family_caveated_reports": plus_internal_fold_caveats,
                "affected_methods": sorted(cross_run.PLUS_FAMILY_METHODS),
                "examples": rows_with_labels(
                    rows,
                    field="caveats",
                    labels={"duplicate_cluster_plus_family_internal_fold_caveat"},
                ),
            },
            "Treat CV+/CV-minmax/jackknife rows in duplicate-cluster sensitivity reports as caveated until a cluster-aware internal-fold variant is run or explicitly ruled unnecessary.",
        )
    )

    feature_violations = counter_get(blocking, "feature_leakage_violation_recorded")
    status, severity = status_from_fail_caveat(feature_violations, 0)
    feature_scan = layers.get("feature_leakage_sidecar_scan") or {}
    controls.append(
        control(
            "prediction_feature_leakage_absence",
            "feature_leakage",
            status,
            severity,
            {
                "feature_leakage_violation_reports": feature_violations,
                "sidecar_violation_count": safe_int(feature_scan.get("violations_count")),
                "feature_sidecar_counts": feature_sidecar_counts(rows),
                "examples": rows_with_labels(
                    rows,
                    field="blocking_issues",
                    labels={"feature_leakage_violation_recorded"},
                ),
            },
            "Inspect affected prediction metadata, remove leakage sources, and regenerate affected bundles.",
        )
    )

    feature_coverage_caveats = counter_get(
        caveats,
        "no_prediction_metadata_feature_leakage_sidecar",
        "feature_leakage_metadata_completeness_caveat",
    )
    feature_metadata_selection_counts = summary.get(
        "feature_metadata_selection_counts", {}
    )
    feature_policy_inference_counts = summary.get(
        "feature_policy_inference_counts", {}
    )
    metadata_not_recorded = safe_int(
        feature_metadata_selection_counts.get("not_recorded")
    )
    policy_not_recorded = safe_int(feature_policy_inference_counts.get("not_recorded"))
    metadata_scope_caveats = (
        feature_coverage_caveats + metadata_not_recorded + policy_not_recorded
    )
    status, severity = status_from_fail_caveat(0, metadata_scope_caveats)
    controls.append(
        control(
            "prediction_metadata_leakage_coverage",
            "feature_leakage",
            status,
            severity,
            {
                "feature_coverage_caveats": feature_coverage_caveats,
                "metadata_scope_caveats": metadata_scope_caveats,
                "metadata_selection_not_recorded": metadata_not_recorded,
                "policy_inference_not_recorded": policy_not_recorded,
                "feature_metadata_selection_counts": feature_metadata_selection_counts,
                "feature_policy_inference_counts": feature_policy_inference_counts,
                "feature_sidecar_counts": feature_sidecar_counts(rows),
                "examples": rows_with_labels(
                    rows,
                    field="caveats",
                    labels={
                        "no_prediction_metadata_feature_leakage_sidecar",
                        "feature_leakage_metadata_completeness_caveat",
                    },
                ),
            },
            "Backfill or regenerate prediction metadata before claiming full preprocessing-output leakage closure.",
        )
    )

    endpoint_failures = counter_get(
        blocking,
        "endpoint_audit_integrity_problem",
        "endpoint_reconstructed_runs_mismatch_completed",
    )
    endpoint_caveats = counter_get(
        caveats,
        "legacy_endpoint_schema_not_full_closure",
        "endpoint_audit_not_full_method_coverage",
        "large_sweep_missing_endpoint_audit",
    )
    status, severity = status_from_fail_caveat(endpoint_failures, endpoint_caveats)
    controls.append(
        control(
            "endpoint_reconstruction_closure",
            "endpoint",
            status,
            severity,
            {
                "endpoint_schema_counts": endpoint_schema_counts(rows),
                "endpoint_failure_reports": endpoint_failures,
                "endpoint_schema_or_coverage_caveats": endpoint_caveats,
                "failure_examples": rows_with_labels(
                    rows,
                    field="blocking_issues",
                    labels={
                        "endpoint_audit_integrity_problem",
                        "endpoint_reconstructed_runs_mismatch_completed",
                    },
                ),
                "caveat_examples": rows_with_labels(
                    rows,
                    field="caveats",
                    labels={
                        "legacy_endpoint_schema_not_full_closure",
                        "endpoint_audit_not_full_method_coverage",
                        "large_sweep_missing_endpoint_audit",
                    },
                ),
            },
            "Rebuild endpoint audits with v2 full-method coverage and zero reconstruction failures before endpoint-level interpretation.",
        )
    )

    unsupported_claim_hits = safe_int(summary.get("unsupported_claim_hits"))
    claim_caveats = sum(
        safe_int(value)
        for key, value in caveats.items()
        if "claim_guard" in str(key)
        or "cqr_fixed_backend_guard" in str(key)
        or "venn_abers" in str(key)
        or str(key).startswith("missing_model_family_controls")
    )
    status, severity = status_from_fail_caveat(unsupported_claim_hits, claim_caveats)
    controls.append(
        control(
            "claim_boundary_guardrails",
            "claims",
            status,
            severity,
            {
                "unsupported_claim_hits": unsupported_claim_hits,
                "claim_guard_caveats": claim_caveats,
                "claim_related_caveats": {
                    key: value
                    for key, value in sorted(caveats.items())
                    if "claim_guard" in str(key)
                    or "cqr_fixed_backend_guard" in str(key)
                    or "venn_abers" in str(key)
                    or str(key).startswith("missing_model_family_controls")
                },
            },
            "Patch configs/reports so CQR, Venn-Abers, production, causal, and final-selection boundaries remain explicit.",
        )
    )

    runner_guard = layers.get("runner_feature_drop_guard_scan") or {}
    required_runner_flags = [
        "fit_block_found",
        "drops_target_before_preprocessing",
        "drops_primary_group_when_present",
        "drops_split_group_when_present",
        "deduplicates_feature_drop_columns",
    ]
    missing_runner_flags = [
        key for key in required_runner_flags if runner_guard.get(key) is not True
    ]
    status, severity = status_from_fail_caveat(len(missing_runner_flags), 0)
    controls.append(
        control(
            "runner_feature_drop_guard",
            "feature_leakage",
            status,
            severity,
            {
                "runner_path": runner_guard.get("runner_path"),
                "required_flags": required_runner_flags,
                "missing_or_false_flags": missing_runner_flags,
            },
            "Repair the runner's target/group/drop-column guard before generating new prediction bundles.",
        )
    )

    loader_policy = layers.get("config_loader_leakage_policy_scan") or {}
    loader_failures = sum(
        len(loader_policy.get(key, []) or [])
        for key in ("unknown_dataset_refs", "missing_loader_target_or_group")
    )
    loader_caveats = sum(
        len(loader_policy.get(key, []) or [])
        for key in (
            "model_family_extra_target_boundary_missing",
            "legacy_extra_target_boundary_weak",
            "model_family_derived_group_source_policy_missing",
            "legacy_derived_group_source_policy_weak",
        )
    )
    status, severity = status_from_fail_caveat(loader_failures, loader_caveats)
    controls.append(
        control(
            "config_loader_leakage_policy",
            "feature_leakage",
            status,
            severity,
            {
                "dataset_refs_scanned": safe_int(loader_policy.get("dataset_refs_scanned")),
                "loader_failures": loader_failures,
                "loader_caveats": loader_caveats,
                "unknown_dataset_refs": loader_policy.get("unknown_dataset_refs", []),
                "missing_loader_target_or_group": loader_policy.get(
                    "missing_loader_target_or_group", []
                ),
            },
            "Fix loader target/group specs or document retained target/group-source boundaries in configs.",
        )
    )

    return controls


def build_payload(root: Path) -> dict[str, Any]:
    cross_payload = cross_run.build_payload(root)
    controls = build_controls_from_cross_run(cross_payload)
    status_counts = Counter(control["status"] for control in controls)
    severity_counts = Counter(control["severity"] for control in controls)
    summary = cross_payload.get("summary") or {}
    leakage_controls = {
        item["control_id"]: item["status"]
        for item in controls
        if item["family"] in {"split", "feature_leakage"}
    }
    hard_leakage_clean = (
        leakage_controls.get("hard_split_leakage_absence") == "pass"
        and leakage_controls.get("prediction_feature_leakage_absence") == "pass"
        and leakage_controls.get("runner_feature_drop_guard") == "pass"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_cross_run_schema": cross_payload.get("schema"),
        "source_cross_run_path": (
            "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "cross_run_integrity_audit.json"
        ),
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "reports_scanned": safe_int(summary.get("reports_scanned")),
            "configs_scanned": safe_int(summary.get("configs_scanned")),
            "total_completed_rows": safe_int(summary.get("total_completed_rows")),
            "control_count": len(controls),
            "control_status_counts": dict(sorted(status_counts.items())),
            "control_severity_counts": dict(sorted(severity_counts.items())),
            "hard_leakage_status": "no_hard_leakage_detected_in_scanned_artifacts"
            if hard_leakage_clean
            else "hard_leakage_or_guard_failure_detected",
        },
        "controls": controls,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Retrospective Methodology Controls",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Reports scanned: {summary['reports_scanned']}",
        f"- Configs scanned: {summary['configs_scanned']}",
        f"- Completed ledger rows represented: {summary['total_completed_rows']}",
        f"- Control status counts: `{summary['control_status_counts']}`",
        f"- Hard leakage status: `{summary['hard_leakage_status']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(
        [
            "",
            "## Control Matrix",
            "",
            "| Control | Family | Status | Severity | Key Evidence | Next action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in payload["controls"]:
        evidence_keys = ", ".join(sorted(item["evidence"].keys())[:6])
        lines.append(
            "| "
            f"`{item['control_id']}` | "
            f"{item['family']} | "
            f"{item['status']} | "
            f"{item['severity']} | "
            f"{evidence_keys} | "
            f"{item['next_action']} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path
    payload = build_payload(root)
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
