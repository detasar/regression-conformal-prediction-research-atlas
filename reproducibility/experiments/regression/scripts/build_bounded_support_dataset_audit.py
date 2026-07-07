"""Build dataset-level bounded-support audit for manuscript bundles.

This artifact applies the bounded-support protocol to current manuscript
bundles. It classifies target domains and endpoint-domain evidence without
promoting any bounded-support validity claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_bounded_support_dataset_audit_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/bounded_support_dataset_audit.json")
BOUNDED_SUPPORT_PROTOCOL = Path("experiments/regression/manuscript/bounded_support_protocol.json")
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
EVIDENCE_VIEW = Path("experiments/regression/manuscript/evidence_view.json")
FINAL_SELECTION = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "final_selection_claim_boundary_audit.json"
)
TARGET_DOMAIN_PROVENANCE = Path(
    "experiments/regression/catalogs/target_domain_provenance.json"
)
POSTHANDLING_VALIDATION = Path(
    "experiments/regression/manuscript/bounded_support_posthandling_validation.json"
)


DOMAIN_RULES: dict[tuple[str, str], dict[str, Any]] = {
    ("nhanes_2017_2018_bmi", "BMXBMI"): {
        "target_domain_class": "nonnegative",
        "natural_lower": 0.0,
        "natural_upper": None,
        "natural_bound_status": "lower_bound_provenance_present",
        "natural_bound_provenance": [
            "NHANES BMI audit target policy",
            "endpoint audit lower_floor",
        ],
        "target_transform_inverse_policy": "identity",
    },
    ("nhanes_2017_2018_glycohemoglobin", "LBXGH"): {
        "target_domain_class": "bounded_continuous",
        "natural_lower": 0.0,
        "natural_upper": 100.0,
        "natural_bound_status": "bounded_percentage_provenance_present",
        "natural_bound_provenance": [
            "NHANES glycohemoglobin audit target policy describes LBXGH as percentage",
            "endpoint audit lower_floor and upper_warning",
        ],
        "target_transform_inverse_policy": "identity",
    },
    ("nhanes_2017_2018_systolic_bp", "SYSBP_MEAN_3"): {
        "target_domain_class": "nonnegative",
        "natural_lower": 0.0,
        "natural_upper": None,
        "natural_bound_status": "lower_bound_provenance_present",
        "natural_bound_provenance": [
            "NHANES systolic BP audit target policy",
            "endpoint audit lower_floor",
        ],
        "target_transform_inverse_policy": "identity",
    },
    ("stackoverflow_2025_compensation", "ConvertedCompYearly"): {
        "target_domain_class": "nonnegative",
        "natural_lower": 0.0,
        "natural_upper": None,
        "natural_bound_status": "lower_bound_provenance_present",
        "natural_bound_provenance": [
            "StackOverflow compensation audit drops nonpositive target values",
            "endpoint audit lower_floor",
        ],
        "target_transform_inverse_policy": "log1p inverse uses expm1 on interval endpoints",
    },
    ("uci_wine_quality", "quality"): {
        "target_domain_class": "bounded_ordinal",
        "natural_lower": None,
        "natural_upper": None,
        "natural_bound_status": "missing_natural_bound_provenance",
        "natural_bound_provenance": [
            "local audit records observed ordinal target range only",
            "source-level allowed quality-scale bounds are not committed in the current audit",
        ],
        "target_transform_inverse_policy": "identity on ordinal score scale",
    },
}


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


def read_text_if_present(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def target_rule(
    dataset_id: str,
    target: str,
    provenance_by_key: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    provenance = provenance_by_key.get((dataset_id, target))
    if provenance:
        return {
            "target_domain_class": provenance.get("target_domain_class"),
            "natural_lower": provenance.get("natural_lower"),
            "natural_upper": provenance.get("natural_upper"),
            "natural_bound_status": provenance.get("natural_bound_status"),
            "natural_bound_provenance": provenance.get("provenance_notes", []),
            "target_transform_inverse_policy": provenance.get(
                "target_transform_inverse_policy"
            ),
            "source_urls": provenance.get("source_urls", []),
            "source_artifacts": provenance.get("source_artifacts", []),
        }
    rule = DOMAIN_RULES.get((dataset_id, target))
    if rule:
        return dict(rule)
    return {
        "target_domain_class": "unbounded_real",
        "natural_lower": None,
        "natural_upper": None,
        "natural_bound_status": "not_declared_for_current_audit",
        "natural_bound_provenance": [],
        "target_transform_inverse_policy": "identity unless the bundle declares a transform",
    }


def audit_paths(root: Path, dataset_id: str) -> dict[str, Path]:
    base = root / "experiments/regression/audits" / dataset_id
    return {
        "audit": base / "audit.json",
        "profile": base / "profile.json",
    }


def endpoint_audit_path(root: Path, manifest_path: str) -> Path:
    return root / Path(manifest_path).parent / "endpoint_audit.json"


def report_id_from_endpoint_path(path: Path) -> str:
    report_dir = path.parent.name
    return f"report:{report_dir}:endpoint_audit"


def target_summary(audit: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    profile_summary = profile.get("target_summary") or {}
    return {
        "n": profile_summary.get("n") or audit.get("n_rows"),
        "min": profile_summary.get("min") if "min" in profile_summary else audit.get("target_min"),
        "max": profile_summary.get("max") if "max" in profile_summary else audit.get("target_max"),
        "mean": profile_summary.get("mean")
        if "mean" in profile_summary
        else audit.get("target_mean"),
        "std": profile_summary.get("std") if "std" in profile_summary else audit.get("target_std"),
        "missing_rate": profile_summary.get("missing_rate")
        if "missing_rate" in profile_summary
        else audit.get("target_missing_rate"),
        "quantiles": profile_summary.get("quantiles") or audit.get("target_quantiles", {}),
    }


def int_value(value: Any) -> int:
    return int(value or 0)


def rate(count: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return count / denominator


def threshold_audit(
    *,
    natural_bound: Any,
    configured_threshold: Any,
    exact_count: int,
    extreme_value: Any,
    direction: str,
) -> dict[str, Any]:
    if natural_bound is None:
        return {
            "count": 0,
            "present": False,
            "status": "no_natural_bound",
        }
    if configured_threshold == natural_bound:
        return {
            "count": exact_count,
            "present": exact_count > 0,
            "status": "exact_count_from_endpoint_audit",
        }
    if extreme_value is None:
        return {
            "count": None,
            "present": False,
            "status": "not_computed_no_extreme_available",
        }
    if direction == "lower":
        present = float(extreme_value) < float(natural_bound)
    else:
        present = float(extreme_value) > float(natural_bound)
    return {
        "count": None if present else 0,
        "present": present,
        "status": "not_computed_extreme_crossing"
        if present
        else "not_computed_no_extreme_crossing",
    }


def endpoint_summary(endpoint: dict[str, Any], natural_lower: Any, natural_upper: Any) -> dict[str, Any]:
    totals = endpoint.get("totals") or {}
    intervals = int_value(totals.get("intervals"))
    lower_floor_count = int_value(totals.get("lower_below_floor"))
    upper_warning_count = int_value(totals.get("upper_above_warning"))
    lower_observed_count = int_value(totals.get("lower_below_observed_min"))
    upper_observed_count = int_value(totals.get("upper_above_observed_max"))
    lower_natural = threshold_audit(
        natural_bound=natural_lower,
        configured_threshold=endpoint.get("lower_floor"),
        exact_count=lower_floor_count,
        extreme_value=totals.get("min_lower"),
        direction="lower",
    )
    upper_natural = threshold_audit(
        natural_bound=natural_upper,
        configured_threshold=endpoint.get("upper_warning"),
        exact_count=upper_warning_count,
        extreme_value=totals.get("max_upper"),
        direction="upper",
    )
    natural_present = bool(lower_natural["present"] or upper_natural["present"])
    natural_counts = [lower_natural["count"], upper_natural["count"]]
    natural_excursion_count = (
        None
        if any(count is None for count in natural_counts) and natural_present
        else sum(int_value(count) for count in natural_counts)
    )
    observed_excursion_count = lower_observed_count + upper_observed_count
    return {
        "audit_schema": endpoint.get("audit_schema"),
        "report_id": report_id_from_endpoint_path(Path(str(endpoint.get("_path", "")))),
        "completed_ledger_rows": endpoint.get("completed_ledger_rows"),
        "reconstructed_runs": endpoint.get("reconstructed_runs"),
        "missing_artifacts": endpoint.get("missing_artifacts"),
        "reconstruction_failures": endpoint.get("reconstruction_failures"),
        "failure_count_total": endpoint.get("failure_count_total"),
        "intervals": intervals,
        "observed_target_min": endpoint.get("observed_target_min"),
        "observed_target_max": endpoint.get("observed_target_max"),
        "lower_floor": endpoint.get("lower_floor"),
        "upper_warning": endpoint.get("upper_warning"),
        "min_lower": totals.get("min_lower"),
        "max_upper": totals.get("max_upper"),
        "lower_below_floor": lower_floor_count,
        "upper_above_warning": upper_warning_count,
        "lower_below_observed_min": lower_observed_count,
        "upper_above_observed_max": upper_observed_count,
        "observed_range_endpoint_excursion_count": observed_excursion_count,
        "observed_range_endpoint_excursion_rate": rate(observed_excursion_count, intervals),
        "natural_domain_endpoint_excursion_count": natural_excursion_count,
        "natural_domain_endpoint_excursion_count_status": "exact"
        if natural_excursion_count is not None
        else "not_computed_extreme_crossing",
        "natural_domain_endpoint_excursion_present": natural_present,
        "natural_lower_audit": lower_natural,
        "natural_upper_audit": upper_natural,
        "natural_domain_endpoint_excursion_rate": rate(natural_excursion_count, intervals)
        if natural_excursion_count is not None
        else None,
        "width_above_observed_range": int_value(totals.get("width_above_observed_range")),
        "width_above_twice_observed_range": int_value(
            totals.get("width_above_twice_observed_range")
        ),
        "crossings": int_value(totals.get("crossings")),
        "nonfinite_endpoint_count": int_value(totals.get("nonfinite_lower"))
        + int_value(totals.get("nonfinite_upper")),
    }


def row_status(
    *,
    endpoint: dict[str, Any],
    natural_bound_status: str,
    posthandling_validation: dict[str, Any],
    posthandling_scope: dict[str, Any],
    manifest_text: str,
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if not endpoint:
        blockers.append("missing_endpoint_audit")
    else:
        if int_value(endpoint.get("missing_artifacts")) > 0:
            blockers.append("missing_endpoint_artifacts")
        if int_value(endpoint.get("reconstruction_failures")) > 0:
            blockers.append("endpoint_reconstruction_failures")
        if int_value(endpoint.get("nonfinite_endpoint_count")) > 0:
            blockers.append("nonfinite_endpoint_values")
        if endpoint.get("natural_domain_endpoint_excursion_present") is True:
            blockers.append("natural_domain_endpoint_excursions")
    if natural_bound_status == "missing_natural_bound_provenance":
        blockers.append("missing_natural_bound_provenance")
    lower_manifest = " ".join(manifest_text.lower().split())
    policy_index = lower_manifest.find("bounded-support policy:")
    policy_window = (
        lower_manifest[policy_index : policy_index + 300] if policy_index >= 0 else ""
    )
    has_explicit_nonclaim = (
        "bounded-support policy:" in policy_window
        and "claim" in policy_window
        and (" no " in f" {policy_window} " or " not " in f" {policy_window} ")
    )
    if not has_explicit_nonclaim:
        blockers.append("manifest_bounded_support_policy_not_explicit")
    if not posthandling_validation:
        blockers.append("positive_bounded_support_validation_not_run")
    elif (
        posthandling_validation.get("status") == "validated"
        and not posthandling_scope.get("include_methods")
        and posthandling_scope.get("max_completed_per_bundle") is None
        and int(posthandling_validation.get("completed_ledger_rows") or 0)
        == int(posthandling_validation.get("total_completed_ledger_rows") or -1)
    ):
        pass
    else:
        blockers.append("positive_bounded_support_validation_incomplete_scope")
    blockers.append("global_bounded_support_validity_claim_disabled")
    return "blocked_no_bounded_support_validity_claim", blockers


def endpoint_support_status(
    *,
    endpoint: dict[str, Any],
    target_domain_class: str | None,
    natural_bound_status: str,
    blockers: list[str],
) -> str:
    if not endpoint:
        return "incomplete_missing_endpoint_audit"
    if any(
        blocker in blockers
        for blocker in (
            "missing_endpoint_artifacts",
            "endpoint_reconstruction_failures",
            "nonfinite_endpoint_values",
        )
    ):
        return "incomplete_endpoint_hygiene_failure"
    if natural_bound_status == "missing_natural_bound_provenance":
        return "incomplete_missing_natural_bound_provenance"
    if (
        target_domain_class == "unbounded_real"
        and endpoint.get("natural_lower_audit", {}).get("status") == "no_natural_bound"
        and endpoint.get("natural_upper_audit", {}).get("status") == "no_natural_bound"
    ):
        return "not_applicable_unbounded_target_endpoint_hygiene_recorded"
    if endpoint.get("natural_domain_endpoint_excursion_present") is True:
        if endpoint.get("natural_domain_endpoint_excursion_count") is None:
            return "blocked_natural_domain_endpoint_excursion_count_unknown"
        return "blocked_natural_domain_endpoint_excursions"
    return "clean_no_natural_domain_endpoint_excursions"


def posthandling_support_status(
    posthandling_validation: dict[str, Any],
    posthandling_scope: dict[str, Any],
) -> str:
    if not posthandling_validation:
        return "not_run"
    if (
        posthandling_validation.get("status") == "validated"
        and not posthandling_scope.get("include_methods")
        and posthandling_scope.get("max_completed_per_bundle") is None
        and int(posthandling_validation.get("completed_ledger_rows") or 0)
        == int(posthandling_validation.get("total_completed_ledger_rows") or -1)
    ):
        return "validated_all_completed_rows"
    return "incomplete_scope"


def build_rows(
    root: Path,
    bundle_index: dict[str, Any],
    provenance_by_key: dict[tuple[str, str], dict[str, Any]],
    posthandling_by_bundle: dict[str, dict[str, Any]],
    posthandling_scope: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bundle in bundle_index.get("bundles", []) or []:
        if not isinstance(bundle, dict):
            continue
        dataset_id = str(bundle.get("dataset_id"))
        target = str(bundle.get("target"))
        paired_dataset_id = bundle.get("paired_dataset_id")
        rule = target_rule(dataset_id, target, provenance_by_key)
        audit_file = audit_paths(root, dataset_id)["audit"]
        profile_file = audit_paths(root, dataset_id)["profile"]
        audit = read_json(audit_file) if audit_file.exists() else {}
        profile = read_json(profile_file) if profile_file.exists() else {}
        endpoint_file = endpoint_audit_path(root, str(bundle.get("manifest_path")))
        endpoint = read_json(endpoint_file) if endpoint_file.exists() else {}
        if endpoint:
            endpoint["_path"] = rel(endpoint_file, root)
        endpoint_payload = endpoint_summary(
            endpoint,
            rule.get("natural_lower"),
            rule.get("natural_upper"),
        ) if endpoint else {}
        posthandling_validation = posthandling_by_bundle.get(str(bundle.get("bundle_id")), {})
        manifest_text = read_text_if_present(root / str(bundle.get("manifest_path")))
        status, blockers = row_status(
            endpoint=endpoint_payload,
            natural_bound_status=str(rule.get("natural_bound_status")),
            posthandling_validation=posthandling_validation,
            posthandling_scope=posthandling_scope,
            manifest_text=manifest_text,
        )
        endpoint_status = endpoint_support_status(
            endpoint=endpoint_payload,
            target_domain_class=rule.get("target_domain_class"),
            natural_bound_status=str(rule.get("natural_bound_status")),
            blockers=blockers,
        )
        posthandling_status = posthandling_support_status(
            posthandling_validation,
            posthandling_scope,
        )
        paths = {
            "manifest_path": str(bundle.get("manifest_path")),
            "dataset_audit_json": rel(audit_file, root) if audit_file.exists() else None,
            "dataset_profile_json": rel(profile_file, root) if profile_file.exists() else None,
            "endpoint_audit_json": rel(endpoint_file, root) if endpoint_file.exists() else None,
        }
        if paired_dataset_id:
            paired = audit_paths(root, str(paired_dataset_id))
            paths["paired_dataset_audit_json"] = (
                rel(paired["audit"], root) if paired["audit"].exists() else None
            )
            paths["paired_dataset_profile_json"] = (
                rel(paired["profile"], root) if paired["profile"].exists() else None
            )
        rows.append(
            {
                "bundle_id": bundle.get("bundle_id"),
                "dataset_id": dataset_id,
                "paired_dataset_id": paired_dataset_id,
                "target": target,
                "target_transform": bundle.get("target_transform"),
                "diagnostic_group": bundle.get("diagnostic_group"),
                "target_domain_class": rule.get("target_domain_class"),
                "natural_lower": rule.get("natural_lower"),
                "natural_upper": rule.get("natural_upper"),
                "natural_bound_status": rule.get("natural_bound_status"),
                "natural_bound_provenance": rule.get("natural_bound_provenance", []),
                "natural_bound_source_urls": rule.get("source_urls", []),
                "natural_bound_source_artifacts": rule.get("source_artifacts", []),
                "target_transform_inverse_policy": rule.get(
                    "target_transform_inverse_policy"
                ),
                "interval_handling_policy": "report_raw_unclipped_with_excursion_audit",
                "target_summary": target_summary(audit, profile),
                "endpoint_audit": endpoint_payload,
                "endpoint_support_status": endpoint_status,
                "posthandling_support_status": posthandling_status,
                "bounded_support_posthandling_validation": {
                    "status": posthandling_validation.get("status"),
                    "scope_note": posthandling_scope.get("scope_note"),
                    "include_methods": posthandling_scope.get("include_methods", []),
                    "max_completed_per_bundle": posthandling_scope.get(
                        "max_completed_per_bundle"
                    ),
                    "completed_ledger_rows": posthandling_validation.get(
                        "completed_ledger_rows"
                    ),
                    "total_completed_ledger_rows": posthandling_validation.get(
                        "total_completed_ledger_rows"
                    ),
                    "clip_policy": (
                        posthandling_validation.get("policies") or {}
                    ).get("clip_to_natural_bounds"),
                }
                if posthandling_validation
                else {},
                "claim_status": status,
                "blockers": blockers,
                "can_support_bounded_support_validity": False,
                "paths": paths,
            }
        )
    return rows


def build_checks(
    *,
    bounded_protocol: dict[str, Any],
    bundle_index: dict[str, Any],
    final_selection: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, bool]:
    protocol_summary = bounded_protocol.get("summary") or {}
    final_summary = final_selection.get("summary") or {}
    final_requirements = final_selection.get("requirement_statuses") or {}
    bundle_count = len(bundle_index.get("bundles", []) or [])
    return {
        "bounded_support_protocol_available": protocol_summary.get("overall_status")
        == "bounded_support_protocol_defined_no_validity_claim",
        "all_manifest_bundles_audited": len(rows) == bundle_count and bundle_count > 0,
        "all_rows_have_endpoint_audit": all(
            bool(row.get("paths", {}).get("endpoint_audit_json")) for row in rows
        ),
        "all_rows_have_dataset_audit": all(
            bool(row.get("paths", {}).get("dataset_audit_json")) for row in rows
        ),
        "all_rows_have_target_domain_class": all(
            row.get("target_domain_class") in (bounded_protocol.get("target_domain_classes") or {})
            for row in rows
        ),
        "all_rows_use_protocol_interval_policy": all(
            row.get("interval_handling_policy")
            in (bounded_protocol.get("interval_handling_policies") or {})
            for row in rows
        ),
        "positive_bounded_support_claims_remain_blocked": all(
            row.get("can_support_bounded_support_validity") is False for row in rows
        )
        and final_requirements.get("endpoint_bounded_support_gate") == "blocked"
        and final_summary.get("claim_status") == "blocked",
        "endpoint_excursions_or_missing_bound_provenance_are_visible": any(
            "natural_domain_endpoint_excursions" in row.get("blockers", [])
            or "missing_natural_bound_provenance" in row.get("blockers", [])
            for row in rows
        ),
    }


def build_payload(root: Path) -> dict[str, Any]:
    sources = {
        "bounded_support_protocol": root / BOUNDED_SUPPORT_PROTOCOL,
        "manuscript_bundle_index": root / BUNDLE_INDEX,
        "manuscript_evidence_view": root / EVIDENCE_VIEW,
        "final_selection_claim_boundary": root / FINAL_SELECTION,
        "target_domain_provenance": root / TARGET_DOMAIN_PROVENANCE,
        "bounded_support_posthandling_validation": root / POSTHANDLING_VALIDATION,
    }
    bounded_protocol = read_json(sources["bounded_support_protocol"])
    bundle_index = read_json(sources["manuscript_bundle_index"])
    evidence_view = read_json(sources["manuscript_evidence_view"])
    final_selection = read_json(sources["final_selection_claim_boundary"])
    target_domain_provenance = read_json(sources["target_domain_provenance"])
    posthandling_validation = read_json(
        sources["bounded_support_posthandling_validation"]
    )
    provenance_by_key = {
        (str(row.get("dataset_id")), str(row.get("target"))): row
        for row in target_domain_provenance.get("rows", []) or []
        if isinstance(row, dict)
    }
    posthandling_by_bundle = {
        str(row.get("bundle_id")): row
        for row in posthandling_validation.get("rows", []) or []
        if isinstance(row, dict)
    }
    posthandling_scope = posthandling_validation.get("scope") or {}
    rows = build_rows(
        root,
        bundle_index,
        provenance_by_key,
        posthandling_by_bundle,
        posthandling_scope,
    )
    checks = build_checks(
        bounded_protocol=bounded_protocol,
        bundle_index=bundle_index,
        final_selection=final_selection,
        rows=rows,
    )
    failed_checks = [key for key, value in checks.items() if not value]
    class_counts = Counter(str(row.get("target_domain_class")) for row in rows)
    status_counts = Counter(str(row.get("claim_status")) for row in rows)
    endpoint_status_counts = Counter(
        str(row.get("endpoint_support_status")) for row in rows
    )
    posthandling_status_counts = Counter(
        str(row.get("posthandling_support_status")) for row in rows
    )
    blocker_counts = Counter(
        blocker for row in rows for blocker in row.get("blockers", []) or []
    )
    endpoint_audited_rows = [
        row for row in rows if row.get("paths", {}).get("endpoint_audit_json")
    ]
    natural_excursion_rows = [
        row
        for row in rows
        if (row.get("endpoint_audit") or {}).get(
            "natural_domain_endpoint_excursion_present"
        )
        is True
    ]
    unknown_natural_excursion_count_rows = [
        row
        for row in natural_excursion_rows
        if (row.get("endpoint_audit") or {}).get(
            "natural_domain_endpoint_excursion_count"
        )
        is None
    ]
    observed_excursion_rows = [
        row
        for row in rows
        if int_value(
            (row.get("endpoint_audit") or {}).get(
                "observed_range_endpoint_excursion_count"
            )
        )
        > 0
    ]
    endpoint_clean_rows = [
        row
        for row in rows
        if row.get("endpoint_support_status")
        == "clean_no_natural_domain_endpoint_excursions"
    ]
    endpoint_not_applicable_rows = [
        row
        for row in rows
        if row.get("endpoint_support_status")
        == "not_applicable_unbounded_target_endpoint_hygiene_recorded"
    ]
    endpoint_blocked_rows = [
        row
        for row in rows
        if str(row.get("endpoint_support_status", "")).startswith("blocked_")
        or str(row.get("endpoint_support_status", "")).startswith("incomplete_")
    ]
    evidence_summary = evidence_view.get("summary") or {}
    overall_status = (
        "dataset_bounded_support_audit_completed_no_validity_claim"
        if not failed_checks
        else "dataset_bounded_support_audit_incomplete"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {key: rel(path, root) for key, path in sources.items()},
        "summary": {
            "overall_status": overall_status,
            "failed_check_count": len(failed_checks),
            "bundle_count": len(rows),
            "unique_dataset_count": len(
                {
                    str(row.get("dataset_id"))
                    for row in rows
                    if row.get("dataset_id")
                }
            ),
            "endpoint_audited_bundle_count": len(endpoint_audited_rows),
            "bounded_support_ready_bundle_count": sum(
                1 for row in rows if row.get("can_support_bounded_support_validity")
            ),
            "target_domain_class_counts": dict(sorted(class_counts.items())),
            "claim_status_counts": dict(sorted(status_counts.items())),
            "endpoint_support_status_counts": dict(
                sorted(endpoint_status_counts.items())
            ),
            "posthandling_support_status_counts": dict(
                sorted(posthandling_status_counts.items())
            ),
            "blocker_counts": dict(sorted(blocker_counts.items())),
            "endpoint_support_clean_bundle_count": len(endpoint_clean_rows),
            "endpoint_support_not_applicable_bundle_count": len(
                endpoint_not_applicable_rows
            ),
            "endpoint_support_blocked_or_incomplete_bundle_count": len(
                endpoint_blocked_rows
            ),
            "natural_domain_excursion_bundle_count": len(natural_excursion_rows),
            "natural_domain_excursion_unknown_count_bundle_count": len(
                unknown_natural_excursion_count_rows
            ),
            "observed_range_excursion_bundle_count": len(observed_excursion_rows),
            "target_domain_provenance_status": (
                target_domain_provenance.get("summary") or {}
            ).get("overall_status"),
            "bounded_support_posthandling_validation_status": (
                posthandling_validation.get("summary") or {}
            ).get("overall_status"),
            "posthandling_validated_bundle_count": (
                posthandling_validation.get("summary") or {}
            ).get("validated_bundle_count"),
            "posthandling_unvalidated_bundle_count": (
                posthandling_validation.get("summary") or {}
            ).get("unvalidated_bundle_count"),
            "posthandling_scope_note": posthandling_scope.get("scope_note"),
            "manuscript_endpoint_result_count": evidence_summary.get(
                "endpoint_result_count"
            ),
            "manuscript_endpoint_caveat_count": evidence_summary.get(
                "endpoint_caveat_count"
            ),
            "can_support_bounded_support_validity": False,
            "final_selection_claim_status": (final_selection.get("summary") or {}).get(
                "claim_status"
            ),
            "endpoint_bounded_support_gate_status": (
                final_selection.get("requirement_statuses") or {}
            ).get("endpoint_bounded_support_gate"),
        },
        "claim_boundaries": [
            "This audit classifies dataset target domains and endpoint-domain evidence for current manuscript bundles.",
            "It does not validate bounded-support coverage for any current bundle.",
            "Endpoint support status separates endpoint-domain hygiene from the global no-bounded-support-validity-claim boundary.",
            "Raw unclipped endpoint reporting is the current interval-handling policy; positive bounded-support language still requires post-handling metrics and validation evidence.",
        ],
        "checks": checks,
        "failed_checks": failed_checks,
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Bounded Support Dataset Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Bundles audited: {summary['bundle_count']}",
        f"- Unique datasets audited: {summary['unique_dataset_count']}",
        f"- Endpoint-audited bundles: {summary['endpoint_audited_bundle_count']}",
        f"- Bounded-support-ready bundles: {summary['bounded_support_ready_bundle_count']}",
        f"- Target-domain class counts: `{summary['target_domain_class_counts']}`",
        f"- Endpoint support status counts: `{summary['endpoint_support_status_counts']}`",
        f"- Posthandling support status counts: `{summary['posthandling_support_status_counts']}`",
        f"- Endpoint-clean bundles: {summary['endpoint_support_clean_bundle_count']}",
        f"- Endpoint not-applicable bundles: {summary['endpoint_support_not_applicable_bundle_count']}",
        f"- Endpoint blocked/incomplete bundles: {summary['endpoint_support_blocked_or_incomplete_bundle_count']}",
        f"- Natural-domain excursion bundles: {summary['natural_domain_excursion_bundle_count']}",
        f"- Natural-domain excursion bundles with count not computed: {summary['natural_domain_excursion_unknown_count_bundle_count']}",
        f"- Observed-range excursion bundles: {summary['observed_range_excursion_bundle_count']}",
        f"- Target-domain provenance status: `{summary['target_domain_provenance_status']}`",
        f"- Bounded-support post-handling validation status: `{summary['bounded_support_posthandling_validation_status']}` with {summary['posthandling_validated_bundle_count']} validated bundles",
        f"- Can support bounded-support validity now: `{summary['can_support_bounded_support_validity']}`",
        f"- Endpoint bounded-support gate status: `{summary['endpoint_bounded_support_gate_status']}`",
        f"- Final-selection claim status: `{summary['final_selection_claim_status']}`",
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
            "| Bundle | Dataset | Target | Domain class | Natural bounds | Endpoint support | Endpoint excursions | Status | Blockers |",
            "| --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        endpoint = row.get("endpoint_audit") or {}
        bounds = f"{row.get('natural_lower')} / {row.get('natural_upper')}"
        blockers = ", ".join(f"`{item}`" for item in row.get("blockers", []))
        excursion_count = endpoint.get("natural_domain_endpoint_excursion_count")
        excursion_text = (
            str(excursion_count)
            if excursion_count is not None
            else endpoint.get("natural_domain_endpoint_excursion_count_status")
        )
        lines.append(
            "| "
            f"`{row['bundle_id']}` | "
            f"`{row['dataset_id']}` | "
            f"`{row['target']}` | "
            f"`{row['target_domain_class']}` | "
            f"{bounds} | "
            f"`{row['endpoint_support_status']}` | "
            f"{excursion_text} | "
            f"`{row['claim_status']}` | "
            f"{blockers} |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status |",
            "| --- | --- |",
        ]
    )
    for key, value in payload["checks"].items():
        lines.append(f"| `{key}` | `{'pass' if value else 'fail'}` |")
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
                "status": "ok" if not payload["failed_checks"] else "fail",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )
    return 1 if payload["failed_checks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
