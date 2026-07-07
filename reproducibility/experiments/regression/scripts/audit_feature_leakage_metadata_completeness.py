"""Triage legacy feature-leakage metadata completeness and provenance caveats.

This audit does not edit prediction metadata and does not rerun models. It
classifies reports whose feature-leakage sidecars record missing metadata
fields or legacy provenance-label gaps, so downstream summaries can distinguish
bounded available-metadata evidence from full preprocessing-level leakage
closure.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts import audit_methodology_sanity as sanity


SCHEMA = "cpfi_feature_leakage_metadata_completeness_triage_v2"
DEFAULT_CROSS_RUN = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "cross_run_integrity_audit.json"
)
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "feature_leakage_metadata_completeness_triage.json"
)
FIELD_METADATA_CAVEAT = "feature_leakage_metadata_completeness_caveat"


CLAIM_BOUNDARIES = [
    "This triage is methodology-debt evidence, not new model-performance evidence.",
    "Zero feature-leakage violations remain limited to the metadata fields available in each sidecar.",
    "Missing preprocessed_feature_names means full preprocessing-output feature-name closure is not claimed.",
    "Missing feature_drop_columns or feature_drop_policy means target/group drop-policy metadata was absent in the legacy prediction bundle.",
    "Missing metadata_selection or backfill_policy_inference provenance labels preserve a legacy scope caveat even when recorded field-missing counts are zero.",
    "Incomplete policy inference preserves a raw metadata caveat even when explicit metadata-closure fields reduce audited missing counts to zero.",
    "This triage is not fairness, causal, legal, production, or final-model-selection evidence.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--cross-run-audit", default=DEFAULT_CROSS_RUN)
    parser.add_argument("--out", default=DEFAULT_OUT)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        return str(resolved_path.relative_to(resolved_root))
    except ValueError:
        return str(resolved_path)


def resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def metadata_limitation_class(completeness: dict[str, Any]) -> str:
    if not completeness:
        return "metadata_completeness_not_recorded"
    missing = {key for key, value in completeness.items() if int(value or 0) > 0}
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


def metadata_selection_status(feature: dict[str, Any], sidecar: dict[str, Any]) -> str:
    selection = sidecar.get("metadata_selection") or feature.get("metadata_selection")
    if selection:
        return str(selection)
    metadata_files = int(
        sidecar.get("metadata_files_scanned")
        or feature.get("metadata_files_scanned")
        or 0
    )
    if metadata_files > 0:
        return "legacy_selection_label_not_recorded"
    return "not_recorded"


def policy_inference_status(feature: dict[str, Any], sidecar: dict[str, Any]) -> str:
    policy = sidecar.get("backfill_policy_inference") or feature.get(
        "backfill_policy_inference"
    ) or {}
    closure = sidecar.get("metadata_closure") or feature.get("metadata_closure") or {}
    completeness = sidecar.get("metadata_completeness") or feature.get(
        "metadata_completeness"
    ) or {}
    if not isinstance(policy, dict):
        policy = {}
    if not isinstance(closure, dict):
        closure = {}
    if policy:
        if (
            policy.get("complete_drop_metadata") is True
            and policy.get("complete_policy_metadata") is True
        ):
            return "complete_drop_and_policy_metadata"
        return "incomplete_drop_or_policy_metadata"
    if closure.get("enabled"):
        if not any(int(value or 0) > 0 for value in completeness.values()):
            return "config_derived_metadata_closure"
        return "incomplete_config_derived_metadata_closure"
    metadata_files = int(
        sidecar.get("metadata_files_scanned")
        or feature.get("metadata_files_scanned")
        or 0
    )
    if metadata_files > 0:
        return "legacy_policy_inference_label_not_recorded"
    return "not_recorded"


def provenance_limitation_class(
    *,
    completeness: dict[str, Any],
    metadata_selection: str,
    policy_inference: str,
    violations_count: int,
) -> str:
    if violations_count:
        return "feature_leakage_violation_recorded"
    limitation = metadata_limitation_class(completeness)
    if limitation != "complete_metadata":
        return limitation
    selection_gap = metadata_selection in {
        "legacy_selection_label_not_recorded",
        "not_recorded",
    }
    policy_gap = policy_inference in {
        "legacy_policy_inference_label_not_recorded",
        "not_recorded",
    }
    if selection_gap and policy_gap:
        return "legacy_selection_and_policy_provenance_labels_missing"
    if selection_gap:
        return "legacy_selection_provenance_label_missing"
    if policy_gap:
        return "legacy_policy_inference_label_missing"
    if policy_inference in {
        "incomplete_drop_or_policy_metadata",
        "incomplete_config_derived_metadata_closure",
    }:
        return "policy_inference_incomplete"
    return "complete_metadata_and_provenance_recorded"


def claim_status(
    *,
    completeness: dict[str, Any],
    metadata_selection: str,
    policy_inference: str,
    violations_count: int,
    runner_drop_guard_ok: bool,
) -> str:
    if violations_count:
        return "blocking_feature_leakage_violation_recorded"
    limitation = metadata_limitation_class(completeness)
    if limitation == "complete_metadata":
        provenance = provenance_limitation_class(
            completeness=completeness,
            metadata_selection=metadata_selection,
            policy_inference=policy_inference,
            violations_count=violations_count,
        )
        if "provenance_label" in provenance:
            return "legacy_complete_metadata_provenance_label_gap_no_violation_recorded"
        if provenance == "policy_inference_incomplete":
            return "incomplete_policy_inference_no_violation_recorded"
        return "complete_sidecar_no_violation_recorded"
    if limitation == "preprocessed_feature_names_missing_only" and runner_drop_guard_ok:
        return "bounded_raw_feature_and_runner_drop_check_no_violation_recorded"
    if "drop_policy" in limitation:
        return "legacy_drop_policy_metadata_missing_no_violation_recorded"
    return "legacy_metadata_incomplete_no_violation_recorded"


def recommended_next_action(status: str) -> str:
    if status == "blocking_feature_leakage_violation_recorded":
        return "Inspect and remediate the violating prediction metadata before interpreting the affected report."
    if status == "bounded_raw_feature_and_runner_drop_check_no_violation_recorded":
        return "Keep the legacy preprocessing-name caveat unless the affected runs are regenerated with current prediction metadata."
    if status == "legacy_drop_policy_metadata_missing_no_violation_recorded":
        return "Regenerate affected prediction bundles if full target/group drop-policy metadata closure is needed."
    if status == "legacy_complete_metadata_provenance_label_gap_no_violation_recorded":
        return "Keep the legacy provenance-label caveat unless affected sidecars are regenerated with current selection and policy-inference labels."
    if status == "incomplete_policy_inference_no_violation_recorded":
        return "Keep the raw drop-policy metadata caveat unless affected prediction bundles are regenerated with explicit drop metadata."
    if status == "complete_sidecar_no_violation_recorded":
        return "No feature-leakage completeness remediation is needed for this sidecar."
    return "Regenerate the sidecar or affected prediction bundles before making full metadata-completeness claims."


def row_from_cross_run(
    *,
    root: Path,
    cross_row: dict[str, Any],
    runner_drop_guard_ok: bool,
) -> dict[str, Any]:
    feature = cross_row.get("feature_leakage_audit") or {}
    sidecar_path = resolve_path(root, feature.get("path"))
    sidecar = read_json(sidecar_path) if sidecar_path and sidecar_path.exists() else {}
    completeness = sidecar.get("metadata_completeness") or feature.get("metadata_completeness") or {}
    violations_count = int(sidecar.get("violations_count", feature.get("violations_count") or 0))
    selection_status = metadata_selection_status(feature, sidecar)
    policy_status = policy_inference_status(feature, sidecar)
    status = claim_status(
        completeness=completeness,
        metadata_selection=selection_status,
        policy_inference=policy_status,
        violations_count=violations_count,
        runner_drop_guard_ok=runner_drop_guard_ok,
    )
    inference = sidecar.get("backfill_policy_inference") or {}
    provenance_class = provenance_limitation_class(
        completeness=completeness,
        metadata_selection=selection_status,
        policy_inference=policy_status,
        violations_count=violations_count,
    )
    return {
        "report_id": cross_row.get("report_id"),
        "report_name": cross_row.get("report_name"),
        "config_path": cross_row.get("config_path"),
        "dataset_ids": cross_row.get("dataset_ids") or [],
        "pilot_summary_path": cross_row.get("pilot_summary_path"),
        "feature_leakage_audit_path": None if sidecar_path is None else rel(sidecar_path, root),
        "metadata_files_scanned": int(sidecar.get("metadata_files_scanned") or 0),
        "metadata_completeness": completeness,
        "metadata_limitation_class": metadata_limitation_class(completeness),
        "metadata_selection_status": selection_status,
        "policy_inference_status": policy_status,
        "provenance_limitation_class": provenance_class,
        "violations_count": violations_count,
        "claim_status": status,
        "recommended_next_action": recommended_next_action(status),
        "available_checks": {
            "expected_features_count": len(sidecar.get("expected_features") or []),
            "expected_drop_columns_count": len(sidecar.get("expected_drop_columns") or []),
            "forbidden_features_count": len(sidecar.get("forbidden_features") or []),
            "expected_target_set": sidecar.get("expected_target") is not None,
            "expected_group_col_set": sidecar.get("expected_group_col") is not None,
            "exact_feature_set_enforced": bool(inference.get("exact_feature_set_enforced")),
            "exact_drop_set_enforced": bool(inference.get("exact_drop_set_enforced")),
            "complete_drop_metadata": bool(inference.get("complete_drop_metadata")),
            "complete_policy_metadata": bool(inference.get("complete_policy_metadata")),
        },
    }


def needs_triage(cross_row: dict[str, Any]) -> bool:
    feature = cross_row.get("feature_leakage_audit") or {}
    if not feature.get("present"):
        return False
    if FIELD_METADATA_CAVEAT in set(cross_row.get("caveats", []) or []):
        return True
    if int(feature.get("violations_count") or 0) > 0:
        return True
    if not feature.get("metadata_selection"):
        return True
    policy = feature.get("backfill_policy_inference") or {}
    closure = feature.get("metadata_closure") or {}
    completeness = feature.get("metadata_completeness") or {}
    if not policy and not (isinstance(closure, dict) and closure.get("enabled")):
        return True
    if policy and (
        policy.get("complete_drop_metadata") is not True
        or policy.get("complete_policy_metadata") is not True
    ):
        return True
    if isinstance(closure, dict) and closure.get("enabled"):
        if any(int(value or 0) > 0 for value in completeness.values()):
            return True
    if not feature.get("metadata_completeness"):
        return True
    return False


def build_payload(root: Path, cross_run_path: Path) -> dict[str, Any]:
    cross_run = read_json(cross_run_path)
    feature_drop_guard = sanity.runner_feature_drop_guard_scan(root)
    runner_drop_guard_ok = all(
        bool(feature_drop_guard.get(key))
        for key in [
            "fit_block_found",
            "drops_target_before_preprocessing",
            "drops_primary_group_when_present",
            "drops_split_group_when_present",
            "drops_loader_extra_feature_drop_columns",
            "deduplicates_feature_drop_columns",
        ]
    )
    rows = [
        row_from_cross_run(
            root=root,
            cross_row=row,
            runner_drop_guard_ok=runner_drop_guard_ok,
        )
        for row in cross_run.get("rows", []) or []
        if needs_triage(row)
    ]
    class_counts = Counter(row["metadata_limitation_class"] for row in rows)
    provenance_class_counts = Counter(
        row["provenance_limitation_class"] for row in rows
    )
    selection_counts = Counter(row["metadata_selection_status"] for row in rows)
    policy_counts = Counter(row["policy_inference_status"] for row in rows)
    status_counts = Counter(row["claim_status"] for row in rows)
    missing_field_totals: Counter[str] = Counter()
    for row in rows:
        for key, value in (row.get("metadata_completeness") or {}).items():
            missing_field_totals[key] += int(value or 0)

    hard_violation_rows = [
        row["report_name"] for row in rows if int(row.get("violations_count") or 0) > 0
    ]
    legacy_provenance_gap_rows = [
        row["report_name"]
        for row in rows
        if row["provenance_limitation_class"]
        in {
            "legacy_selection_and_policy_provenance_labels_missing",
            "legacy_selection_provenance_label_missing",
            "legacy_policy_inference_label_missing",
        }
    ]
    policy_inference_incomplete_rows = [
        row["report_name"]
        for row in rows
        if row["provenance_limitation_class"] == "policy_inference_incomplete"
    ]
    field_metadata_incomplete_rows = [
        row["report_name"]
        for row in rows
        if row["metadata_limitation_class"] != "complete_metadata"
    ]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_cross_run_integrity_audit_path": rel(cross_run_path, root),
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "caveat_rows_triaged": len(rows),
            "triaged_report_count": len(rows),
            "runner_feature_drop_guard_ok": runner_drop_guard_ok,
            "metadata_limitation_class_counts": dict(sorted(class_counts.items())),
            "provenance_limitation_class_counts": dict(
                sorted(provenance_class_counts.items())
            ),
            "metadata_selection_status_counts": dict(sorted(selection_counts.items())),
            "policy_inference_status_counts": dict(sorted(policy_counts.items())),
            "claim_status_counts": dict(sorted(status_counts.items())),
            "missing_metadata_field_totals": dict(sorted(missing_field_totals.items())),
            "hard_feature_leakage_violation_rows": hard_violation_rows,
            "hard_feature_leakage_violation_row_count": len(hard_violation_rows),
            "legacy_provenance_gap_rows": legacy_provenance_gap_rows,
            "legacy_provenance_gap_row_count": len(legacy_provenance_gap_rows),
            "policy_inference_incomplete_rows": policy_inference_incomplete_rows,
            "policy_inference_incomplete_row_count": len(
                policy_inference_incomplete_rows
            ),
            "field_metadata_incomplete_rows": field_metadata_incomplete_rows,
            "field_metadata_incomplete_row_count": len(field_metadata_incomplete_rows),
            "full_preprocessing_lineage_claim_supported": (
                not hard_violation_rows
                and not legacy_provenance_gap_rows
                and not policy_inference_incomplete_rows
                and not field_metadata_incomplete_rows
                and runner_drop_guard_ok
            ),
            "scientific_status": (
                "feature_leakage_violations_require_remediation"
                if hard_violation_rows
                else "hard_feature_leakage_not_detected_but_legacy_provenance_or_metadata_scope_caveats_remain"
                if (
                    legacy_provenance_gap_rows
                    or policy_inference_incomplete_rows
                    or field_metadata_incomplete_rows
                )
                else "hard_feature_leakage_not_detected_and_feature_metadata_provenance_triaged"
            ),
        },
        "feature_drop_guard": feature_drop_guard,
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Feature Leakage Metadata Completeness Triage",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source cross-run audit: `{payload['source_cross_run_integrity_audit_path']}`",
        f"- Caveat rows triaged: {summary['caveat_rows_triaged']}",
        f"- Runner feature-drop guard ok: {summary['runner_feature_drop_guard_ok']}",
        f"- Metadata limitation classes: `{summary['metadata_limitation_class_counts']}`",
        f"- Provenance limitation classes: `{summary['provenance_limitation_class_counts']}`",
        f"- Metadata-selection statuses: `{summary['metadata_selection_status_counts']}`",
        f"- Policy-inference statuses: `{summary['policy_inference_status_counts']}`",
        f"- Claim statuses: `{summary['claim_status_counts']}`",
        f"- Missing metadata field totals: `{summary['missing_metadata_field_totals']}`",
        f"- Hard feature-leakage violation rows: {summary['hard_feature_leakage_violation_row_count']}",
        f"- Legacy provenance-gap rows: {summary['legacy_provenance_gap_row_count']}",
        f"- Policy-inference incomplete rows: {summary.get('policy_inference_incomplete_row_count', 0)}",
        f"- Field metadata-incomplete rows: {summary['field_metadata_incomplete_row_count']}",
        f"- Full preprocessing-lineage claim supported: `{summary['full_preprocessing_lineage_claim_supported']}`",
        f"- Scientific status: `{summary['scientific_status']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Report | Field class | Provenance class | Claim status | Missing metadata | Next action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row['report_name']}` | "
            f"`{row['metadata_limitation_class']}` | "
            f"`{row['provenance_limitation_class']}` | "
            f"`{row['claim_status']}` | "
            f"`{row['metadata_completeness']}` | "
            f"{row['recommended_next_action']} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    cross_run_path = resolve_path(root, args.cross_run_audit) or Path(args.cross_run_audit)
    out_path = resolve_path(root, args.out) or Path(args.out)
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
