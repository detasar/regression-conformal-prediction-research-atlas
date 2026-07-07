"""Build a cross-run scientific integrity matrix for regression CP reports.

The methodology sanity audit answers "does the study-level guardrail pass?".
This companion artifact answers "which report carries which integrity status?".
It intentionally works from committed sidecars and summaries only; it does not
touch raw data or prediction caches.
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
from experiments.regression.scripts import audit_methodology_sanity as sanity


SCHEMA = "cpfi_cross_run_integrity_audit_v1"
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "cross_run_integrity_audit.json"
)
CLAIM_BOUNDARIES = [
    "This audit is a retrospective sidecar and summary consistency check, not a new model result.",
    "A clean hard-leakage scan means no row-id or split-group contamination was detected in scanned sidecars; it is not proof that every semantic proxy has been removed.",
    "Duplicate-signature and model-visible-signature overlaps are caveats for interpretation, not row-id leakage evidence by themselves.",
    "Feature-leakage sidecars only validate the prediction metadata and explicit feature/drop policies available for scanned reports.",
    "Do not use this audit to choose a final model, claim production readiness, infer causal effects, give legal/admissions guidance, or claim protected-class fairness evidence.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output JSON path.")
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


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def config_report_aliases(path: Path, config: dict[str, Any]) -> list[str]:
    aliases = [path.stem]
    controls = config.get("quality_controls", {}) or {}
    provenance = config.get("post_selection_validation_bridge_provenance") or {}
    is_post_selection_bridge = bool(
        controls.get("dataset_final_gate_post_selection_validation_bridge")
        or provenance
    )
    if is_post_selection_bridge:
        for dataset_id in config.get("datasets") or []:
            aliases.append(
                f"method_selection_post_selection_validation_{slugify(str(dataset_id))}"
            )
        logging = config.get("logging", {}) or {}
        ledger = logging.get("ledger")
        if ledger:
            aliases.append(Path(str(ledger)).parent.name)
    return list(dict.fromkeys(alias for alias in aliases if alias))


def positive_overlap_count(overlaps: Any) -> int:
    if not isinstance(overlaps, dict):
        return 0
    total = 0
    for value in overlaps.values():
        count = safe_int(value)
        if count > 0:
            total += count
    return total


def pair_overlap_summary(left: set[str], right: set[str]) -> int:
    return len(left.intersection(right))


def allocation_group_overlap_count(seed_profile: dict[str, Any]) -> int:
    allocations = seed_profile.get("split_group_allocations")
    if not isinstance(allocations, dict):
        return 0
    groups = {
        split_name: {str(value) for value in values}
        for split_name, values in allocations.items()
        if isinstance(values, list)
    }
    return sum(
        pair_overlap_summary(groups.get(left, set()), groups.get(right, set()))
        for left, right in (("train", "cal"), ("train", "test"), ("cal", "test"))
    )


def summarize_split_profile(path: Path | None, root: Path) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "present": bool(path and path.exists()),
        "path": rel(path, root) if path and path.exists() else None,
        "schema": None,
        "dataset_ids": [],
        "seed_profiles_scanned": 0,
        "row_id_overlap_violations": 0,
        "split_group_overlap_violations": 0,
        "duplicate_signature_warnings": 0,
        "duplicate_signature_pair_overlaps": 0,
        "model_visible_feature_signature_warnings": 0,
        "model_visible_feature_signature_pair_overlaps": 0,
        "model_visible_feature_plus_target_signature_warnings": 0,
        "model_visible_feature_plus_target_signature_pair_overlaps": 0,
        "model_visible_signature_warnings": 0,
        "model_visible_signature_pair_overlaps": 0,
        "malformed": None,
    }
    if not path or not path.exists():
        return evidence
    try:
        payload = read_json(path)
    except json.JSONDecodeError as exc:
        evidence["malformed"] = f"{type(exc).__name__}: {exc}"
        return evidence

    evidence["schema"] = payload.get("schema") or payload.get("artifact_schema")
    dataset_ids: set[str] = set()
    if payload.get("dataset_id"):
        dataset_ids.add(str(payload["dataset_id"]))
    if isinstance(payload.get("dataset_ids"), list):
        dataset_ids.update(str(value) for value in payload["dataset_ids"])

    profiles = payload.get("profiles")
    if isinstance(profiles, list) and profiles:
        for profile in profiles:
            if not isinstance(profile, dict):
                evidence["malformed"] = "profile entry is not an object"
                continue
            if profile.get("dataset_id"):
                dataset_ids.add(str(profile["dataset_id"]))
            split_group_col = profile.get("split_group_col")
            for seed_profile in profile.get("seeds", []) or []:
                if not isinstance(seed_profile, dict):
                    evidence["malformed"] = "seed entry is not an object"
                    continue
                evidence["seed_profiles_scanned"] += 1
                row_id_count = positive_overlap_count(seed_profile.get("row_id_overlaps"))
                if row_id_count:
                    evidence["row_id_overlap_violations"] += 1
                split_group_count = positive_overlap_count(
                    seed_profile.get("split_group_overlaps")
                )
                if split_group_col and split_group_count:
                    evidence["split_group_overlap_violations"] += 1
                duplicate_count = positive_overlap_count(
                    seed_profile.get("row_signature_overlaps")
                )
                if duplicate_count:
                    evidence["duplicate_signature_warnings"] += 1
                    evidence["duplicate_signature_pair_overlaps"] += duplicate_count

                model_visible_feature_count = positive_overlap_count(
                    seed_profile.get(
                        "model_visible_feature_signature_cross_split_overlaps"
                    )
                )
                if model_visible_feature_count:
                    evidence["model_visible_feature_signature_warnings"] += 1
                    evidence["model_visible_feature_signature_pair_overlaps"] += (
                        model_visible_feature_count
                    )
                model_visible_feature_plus_target_count = positive_overlap_count(
                    seed_profile.get(
                        "model_visible_feature_plus_target_signature_cross_split_overlaps"
                    )
                )
                if model_visible_feature_plus_target_count:
                    evidence[
                        "model_visible_feature_plus_target_signature_warnings"
                    ] += 1
                    evidence[
                        "model_visible_feature_plus_target_signature_pair_overlaps"
                    ] += model_visible_feature_plus_target_count
                    evidence["model_visible_signature_warnings"] += 1
                    evidence["model_visible_signature_pair_overlaps"] += (
                        model_visible_feature_plus_target_count
                    )

    seed_profiles = payload.get("seed_profiles")
    if isinstance(seed_profiles, list) and seed_profiles:
        for seed_profile in seed_profiles:
            if not isinstance(seed_profile, dict):
                evidence["malformed"] = "seed_profile entry is not an object"
                continue
            evidence["seed_profiles_scanned"] += 1
            split_group_count = allocation_group_overlap_count(seed_profile)
            if split_group_count:
                evidence["split_group_overlap_violations"] += 1

            full_row_count = positive_overlap_count(
                seed_profile.get("full_row_signature_cross_split_overlaps")
            )
            if full_row_count:
                evidence["duplicate_signature_warnings"] += 1
                evidence["duplicate_signature_pair_overlaps"] += full_row_count

            model_visible_feature_count = positive_overlap_count(
                seed_profile.get("model_visible_feature_signature_cross_split_overlaps")
            )
            if model_visible_feature_count:
                evidence["model_visible_feature_signature_warnings"] += 1
                evidence["model_visible_feature_signature_pair_overlaps"] += (
                    model_visible_feature_count
                )
            model_visible_feature_plus_target_count = positive_overlap_count(
                seed_profile.get(
                    "model_visible_feature_plus_target_signature_cross_split_overlaps"
                )
            )
            if model_visible_feature_plus_target_count:
                evidence["model_visible_feature_plus_target_signature_warnings"] += 1
                evidence["model_visible_feature_plus_target_signature_pair_overlaps"] += (
                    model_visible_feature_plus_target_count
                )
                evidence["model_visible_signature_warnings"] += 1
                evidence["model_visible_signature_pair_overlaps"] += (
                    model_visible_feature_plus_target_count
                )

    evidence["dataset_ids"] = sorted(dataset_ids)
    return evidence


def summarize_endpoint_audit(path: Path | None, root: Path) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "present": bool(path and path.exists()),
        "path": rel(path, root) if path and path.exists() else None,
        "schema": None,
        "full_method_coverage": None,
        "completed_ledger_rows": None,
        "reconstructed_runs": None,
        "reconstruction_failures": None,
        "failure_count_total": None,
        "missing_artifacts_count": None,
        "malformed": None,
    }
    if not path or not path.exists():
        return evidence
    try:
        payload = read_json(path)
    except json.JSONDecodeError as exc:
        evidence["malformed"] = f"{type(exc).__name__}: {exc}"
        return evidence
    method_filter = payload.get("method_filter") or {}
    missing_artifacts = payload.get("missing_artifacts") or []
    if isinstance(missing_artifacts, bool):
        missing_artifacts_count = None
    elif isinstance(missing_artifacts, (int, float)):
        missing_artifacts_count = int(missing_artifacts)
    elif isinstance(missing_artifacts, list):
        missing_artifacts_count = len(missing_artifacts)
    else:
        missing_artifacts_count = None
    evidence.update(
        {
            "schema": payload.get("audit_schema") or payload.get("schema"),
            "full_method_coverage": method_filter.get("full_method_coverage")
            if isinstance(method_filter, dict)
            else None,
            "completed_ledger_rows": payload.get("completed_ledger_rows"),
            "reconstructed_runs": payload.get("reconstructed_runs"),
            "reconstruction_failures": payload.get("reconstruction_failures"),
            "failure_count_total": payload.get("failure_count_total"),
            "missing_artifacts_count": missing_artifacts_count,
        }
    )
    return evidence


def endpoint_integrity_problem(endpoint: dict[str, Any]) -> bool:
    if endpoint["malformed"]:
        return True
    for key in ("reconstruction_failures", "failure_count_total", "missing_artifacts_count"):
        value = endpoint.get(key)
        if value is not None and safe_int(value) > 0:
            return True
    return False


def summarize_feature_leakage_audit(path: Path | None, root: Path) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "present": bool(path and path.exists()),
        "path": rel(path, root) if path and path.exists() else None,
        "schema": None,
        "metadata_selection": None,
        "source_backlog_action_id": None,
        "source_cross_run_report_id": None,
        "backfill_policy_inference": {},
        "metadata_closure": {},
        "raw_metadata_completeness": {},
        "metadata_files_scanned": 0,
        "violations_count": 0,
        "metadata_completeness": {},
        "missing_metadata_field_total": 0,
        "malformed": None,
    }
    if not path or not path.exists():
        return evidence
    try:
        payload = read_json(path)
    except json.JSONDecodeError as exc:
        evidence["malformed"] = f"{type(exc).__name__}: {exc}"
        return evidence
    completeness = payload.get("metadata_completeness") or {}
    raw_completeness = payload.get("raw_metadata_completeness") or {}
    policy_inference = payload.get("backfill_policy_inference") or {}
    metadata_closure = payload.get("metadata_closure") or {}
    evidence.update(
        {
            "schema": payload.get("schema"),
            "metadata_selection": payload.get("metadata_selection"),
            "source_backlog_action_id": payload.get("source_backlog_action_id"),
            "source_cross_run_report_id": payload.get("source_cross_run_report_id"),
            "backfill_policy_inference": policy_inference
            if isinstance(policy_inference, dict)
            else {},
            "metadata_closure": metadata_closure
            if isinstance(metadata_closure, dict)
            else {},
            "metadata_files_scanned": safe_int(payload.get("metadata_files_scanned")),
            "violations_count": safe_int(payload.get("violations_count")),
            "metadata_completeness": completeness,
            "raw_metadata_completeness": raw_completeness,
            "missing_metadata_field_total": sum(
                safe_int(value) for value in completeness.values()
            )
            if isinstance(completeness, dict)
            else 0,
        }
    )
    return evidence


def feature_metadata_selection_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        feature = row["feature_leakage_audit"]
        if not feature["present"]:
            continue
        counts[str(feature.get("metadata_selection") or "not_recorded")] += 1
    return dict(sorted(counts.items()))


def feature_policy_inference_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        feature = row["feature_leakage_audit"]
        if not feature["present"]:
            continue
        policy = feature.get("backfill_policy_inference") or {}
        closure = feature.get("metadata_closure") or {}
        if not policy and closure.get("enabled"):
            completeness = feature.get("metadata_completeness") or {}
            if not any(safe_int(value) > 0 for value in completeness.values()):
                counts["config_derived_metadata_closure"] += 1
            else:
                counts["incomplete_config_derived_metadata_closure"] += 1
        elif not policy:
            counts["not_recorded"] += 1
        elif (
            policy.get("complete_drop_metadata") is True
            and policy.get("complete_policy_metadata") is True
        ):
            counts["complete_drop_and_policy_metadata"] += 1
        else:
            counts["incomplete_drop_or_policy_metadata"] += 1
    return dict(sorted(counts.items()))


def config_index(root: Path) -> dict[str, dict[str, Any]]:
    rows = {}
    for item in sanity.scan_configs(root):
        path = item["path"]
        config = item["config"]
        row = {"path": path, "config": config}
        for alias in config_report_aliases(path, config):
            rows.setdefault(alias, row)
    return rows


def dataset_ids_from_summary(payload: dict[str, Any]) -> list[str]:
    dataset_ids: set[str] = set()
    metadata = payload.get("metadata", {}) or {}
    for key in ("dataset_counts", "raw_dataset_counts"):
        if isinstance(metadata.get(key), dict):
            dataset_ids.update(str(value) for value in metadata[key].keys())
    for row in payload.get("rows", []) or []:
        if isinstance(row, dict) and row.get("dataset_id"):
            dataset_ids.add(str(row["dataset_id"]))
    return sorted(dataset_ids)


def cp_methods_from_summary(payload: dict[str, Any]) -> list[str]:
    methods = {
        str(row["cp_method"])
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and row.get("cp_method") is not None
    }
    return sorted(methods)


PLUS_FAMILY_METHODS = {
    "cv_plus",
    "cv_minmax",
    "jackknife_plus",
    "jackknife_minmax",
    "jackknife_plus_after_bootstrap",
}
GROUPED_CV_METHODS = {"cv_plus_grouped", "cv_minmax_grouped"}
GROUPED_CV_BASE_METHODS = {
    "cv_plus_grouped": "cv_plus",
    "cv_minmax_grouped": "cv_minmax",
}
STATUS_RANK = {
    "skipped_completed": 0,
    "skipped_method": 1,
    "failed": 2,
    "completed": 3,
}


def stable_key_part(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return str(value)


def stable_params_key(value: Any) -> str:
    text = stable_key_part(value)
    return "{}" if text == "" else text


def semantic_ledger_key(row: dict[str, Any]) -> tuple[str, ...] | None:
    required = ["dataset_id", "model_id", "cp_method", "alpha", "seed"]
    if any(stable_key_part(row.get(field)) == "" for field in required):
        return None
    return (
        stable_key_part(row.get("dataset_id")),
        stable_key_part(row.get("model_family")),
        stable_key_part(row.get("model_id")),
        stable_params_key(row.get("model_params")),
        stable_key_part(row.get("seed")),
        stable_key_part(row.get("cp_method")),
        stable_params_key(row.get("cp_method_params")),
        stable_key_part(row.get("alpha")),
    )


def canonical_ledger_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = [
        (
            stable_key_part(row.get("run_id", idx)),
            STATUS_RANK.get(str(row.get("status", "missing")), 1),
            idx,
            row,
        )
        for idx, row in enumerate(rows)
    ]
    indexed.sort(key=lambda item: (item[0], item[1], item[2]))
    by_run_id: dict[str, tuple[int, int, dict[str, Any]]] = {}
    for run_id, rank, idx, row in indexed:
        by_run_id[run_id] = (rank, idx, row)

    by_semantic: dict[tuple[str, ...], tuple[int, int, dict[str, Any]]] = {}
    without_semantic: list[tuple[int, int, dict[str, Any]]] = []
    for rank, idx, row in by_run_id.values():
        key = semantic_ledger_key(row)
        if key is None:
            without_semantic.append((rank, idx, row))
            continue
        current = by_semantic.get(key)
        if current is None or (rank, idx) >= (current[0], current[1]):
            by_semantic[key] = (rank, idx, row)

    canonical = [*without_semantic, *by_semantic.values()]
    canonical.sort(key=lambda item: item[1])
    return [row for _, _, row in canonical]


def has_duplicate_cluster_plus_family_internal_fold_caveat(
    report_name: str,
    methods: list[str],
) -> bool:
    return report_name.startswith("duplicate_cluster_sensitivity_") and bool(
        set(methods).intersection(PLUS_FAMILY_METHODS)
    )


def grouped_summary_completed_count(
    payload: dict[str, Any],
    methods: set[str],
) -> int | None:
    total = 0
    observed = False
    for row in payload.get("rows", []) or []:
        if not isinstance(row, dict) or str(row.get("cp_method")) not in methods:
            continue
        observed = True
        if "coverage_count" in row:
            total += safe_int(row.get("coverage_count"))
    return total if observed else None


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: {exc}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def expected_grouped_cv_folds(config_row: dict[str, Any] | None) -> int:
    if not config_row:
        return 5
    try:
        return int((config_row["config"].get("conformal") or {}).get("cv_plus_folds", 5))
    except (TypeError, ValueError):
        return 5


def validate_grouped_cv_row(
    row: dict[str, Any],
    *,
    expected_folds: int,
) -> list[str]:
    method = str(row.get("cp_method"))
    metadata = row.get("cp_metadata")
    failures: list[str] = []
    if not isinstance(metadata, dict):
        return ["missing_cp_metadata"]

    if metadata.get("method") != method:
        failures.append("cp_metadata_method_mismatch")
    if metadata.get("base_method") != GROUPED_CV_BASE_METHODS.get(method):
        failures.append("base_method_mismatch")
    if metadata.get("grouped_variant_role") != "split_group_preserving_internal_cv":
        failures.append("grouped_variant_role_missing")
    if metadata.get("internal_resampling_unit") != "split_group":
        failures.append("internal_resampling_unit_not_split_group")
    if metadata.get("internal_fold_assignment") != "seeded_greedy_group_kfold":
        failures.append("internal_fold_assignment_unexpected")
    if metadata.get("groups_split_across_internal_folds") is not False:
        failures.append("groups_split_across_internal_folds_not_false")

    row_counts = metadata.get("internal_fold_row_counts")
    group_counts = metadata.get("internal_fold_group_counts")
    if not isinstance(row_counts, list) or len(row_counts) != expected_folds:
        failures.append("internal_fold_row_counts_missing_or_wrong_length")
    elif any(safe_int(value) <= 0 for value in row_counts):
        failures.append("internal_fold_row_counts_nonpositive")
    if not isinstance(group_counts, list) or len(group_counts) != expected_folds:
        failures.append("internal_fold_group_counts_missing_or_wrong_length")
    elif any(safe_int(value) <= 0 for value in group_counts):
        failures.append("internal_fold_group_counts_nonpositive")
    if safe_int(metadata.get("n_internal_groups")) < expected_folds:
        failures.append("n_internal_groups_less_than_expected_folds")
    if safe_int(metadata.get("min_internal_fold_groups")) <= 0:
        failures.append("min_internal_fold_groups_nonpositive")
    if safe_int(metadata.get("min_internal_fold_rows")) <= 0:
        failures.append("min_internal_fold_rows_nonpositive")
    return failures


def summarize_grouped_cv_metadata(
    root: Path,
    payload: dict[str, Any],
    config_row: dict[str, Any] | None,
    cp_methods: list[str],
) -> dict[str, Any]:
    methods = sorted(set(cp_methods).intersection(GROUPED_CV_METHODS))
    evidence: dict[str, Any] = {
        "configured": bool(methods),
        "methods": methods,
        "ledger_path": None,
        "ledger_present": False,
        "expected_completed_rows_from_summary": None,
        "completed_rows_scanned": 0,
        "failure_count": 0,
        "failure_examples": [],
        "summary_ledger_mismatch": False,
        "malformed": None,
    }
    if not methods:
        return evidence

    ledger_value = payload.get("ledger")
    if not ledger_value:
        evidence["malformed"] = "pilot_summary_missing_ledger_path"
        return evidence
    ledger_path = Path(str(ledger_value))
    if not ledger_path.is_absolute():
        ledger_path = root / ledger_path
    evidence["ledger_path"] = rel(ledger_path, root)
    evidence["ledger_present"] = ledger_path.exists()
    if not ledger_path.exists():
        evidence["malformed"] = "ledger_not_found"
        return evidence

    try:
        rows = canonical_ledger_rows(load_jsonl_rows(ledger_path))
    except (OSError, ValueError) as exc:
        evidence["malformed"] = f"{type(exc).__name__}: {exc}"
        return evidence

    method_set = set(methods)
    completed = [
        row
        for row in rows
        if str(row.get("status")) == "completed"
        and str(row.get("cp_method")) in method_set
    ]
    expected_rows = grouped_summary_completed_count(payload, method_set)
    evidence["expected_completed_rows_from_summary"] = expected_rows
    evidence["completed_rows_scanned"] = len(completed)
    if expected_rows is not None and expected_rows != len(completed):
        evidence["summary_ledger_mismatch"] = True

    expected_folds = expected_grouped_cv_folds(config_row)
    for row in completed:
        failures = validate_grouped_cv_row(row, expected_folds=expected_folds)
        if not failures:
            continue
        evidence["failure_count"] += 1
        if len(evidence["failure_examples"]) < 20:
            evidence["failure_examples"].append(
                {
                    "run_id": row.get("run_id"),
                    "cp_method": row.get("cp_method"),
                    "model_id": row.get("model_id"),
                    "seed": row.get("seed"),
                    "failures": failures,
                }
            )
    return evidence


def config_control_caveats(config_row: dict[str, Any] | None) -> list[str]:
    if not config_row:
        return ["config_not_matched_by_report_directory"]
    path = config_row["path"]
    config = config_row["config"]
    controls = config.get("quality_controls", {}) or {}
    caveats: list[str] = []
    is_model_family = path.name.startswith("model_family_sweep_")
    if is_model_family:
        missing = [
            key for key in sanity.REQUIRED_MODEL_FAMILY_CONTROLS if not controls.get(key)
        ]
        if missing:
            caveats.append("missing_model_family_controls:" + ",".join(missing))
    methods = set(config.get("cp_methods", []) or [])
    if "cqr" in methods and not controls.get("interpret_cqr_as_fixed_quantile_backend"):
        caveats.append(
            "cqr_fixed_backend_guard_missing"
            if is_model_family
            else "legacy_cqr_fixed_backend_guard_not_backfilled"
        )
    if methods.intersection({"venn_abers_quantile", "venn_abers_split_fallback"}) and not controls.get(
        "forbid_validated_venn_abers_regression_claims"
    ):
        caveats.append(
            "venn_abers_validated_regression_claim_guard_missing"
            if is_model_family
            else "legacy_venn_abers_claim_guard_not_backfilled"
        )
    return caveats


def build_report_row(root: Path, pilot_path: Path, configs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    report_name = pilot_path.parent.name
    payload = read_json(pilot_path)
    metadata = payload.get("metadata", {}) or {}
    status_counts = {
        str(key): safe_int(value) for key, value in (metadata.get("status_counts") or {}).items()
    }
    completed = status_counts.get("completed", 0)
    failed = status_counts.get("failed", 0)
    large = completed >= sanity.LARGE_COMPLETED_THRESHOLD
    report_dir = pilot_path.parent
    config_row = configs.get(report_name)
    split = summarize_split_profile(report_dir / "split_profile.json", root)
    endpoint = summarize_endpoint_audit(report_dir / "endpoint_audit.json", root)
    feature = summarize_feature_leakage_audit(report_dir / "feature_leakage_audit.json", root)

    blocking_issues: list[str] = []
    caveats: list[str] = []
    if failed:
        blocking_issues.append("failed_rows_present")
    if "best_rows" in payload:
        caveats.append("legacy_best_rows_key_present")
    if large and not endpoint["present"]:
        caveats.append("large_sweep_missing_endpoint_audit")
    if large and not (report_dir / "split_profile.json").exists():
        caveats.append("large_sweep_missing_split_profile")
    if split["malformed"]:
        blocking_issues.append("split_profile_malformed")
    if split["present"] and split["schema"] != "cpfi_regression_split_profile_v2":
        caveats.append("legacy_split_profile_schema_partial_integrity")
    if split["row_id_overlap_violations"]:
        blocking_issues.append("row_id_overlap_detected")
    if split["split_group_overlap_violations"]:
        blocking_issues.append("split_group_overlap_detected")
    if split["duplicate_signature_warnings"]:
        caveats.append("duplicate_signature_cross_split_caveat")
    if split["model_visible_signature_warnings"] and not split[
        "duplicate_signature_warnings"
    ]:
        caveats.append("model_visible_signature_cross_split_caveat")
    if endpoint_integrity_problem(endpoint):
        blocking_issues.append("endpoint_audit_integrity_problem")
    if endpoint["present"] and endpoint["schema"] != "cpfi_regression_endpoint_audit_v2":
        caveats.append("legacy_endpoint_schema_not_full_closure")
    if (
        endpoint["schema"] == "cpfi_regression_endpoint_audit_v2"
        and endpoint["full_method_coverage"] is not True
    ):
        caveats.append("endpoint_audit_not_full_method_coverage")
    if (
        endpoint["schema"] == "cpfi_regression_endpoint_audit_v2"
        and endpoint["reconstructed_runs"] is not None
        and safe_int(endpoint["reconstructed_runs"]) != completed
    ):
        blocking_issues.append("endpoint_reconstructed_runs_mismatch_completed")
    if feature["malformed"]:
        blocking_issues.append("feature_leakage_audit_malformed")
    if feature["violations_count"]:
        blocking_issues.append("feature_leakage_violation_recorded")
    if feature["present"] and feature["missing_metadata_field_total"]:
        caveats.append("feature_leakage_metadata_completeness_caveat")
    if not feature["present"]:
        caveats.append("no_prediction_metadata_feature_leakage_sidecar")
    caveats.extend(config_control_caveats(config_row))
    cp_methods = cp_methods_from_summary(payload)
    grouped_cv = summarize_grouped_cv_metadata(root, payload, config_row, cp_methods)
    if has_duplicate_cluster_plus_family_internal_fold_caveat(report_name, cp_methods):
        caveats.append("duplicate_cluster_plus_family_internal_fold_caveat")
    if grouped_cv["configured"]:
        if grouped_cv["malformed"]:
            blocking_issues.append("grouped_cv_metadata_audit_malformed")
        if grouped_cv["summary_ledger_mismatch"]:
            blocking_issues.append("grouped_cv_summary_ledger_mismatch")
        if safe_int(grouped_cv["failure_count"]):
            blocking_issues.append("grouped_cv_internal_fold_metadata_invalid")

    risk_level = "high" if blocking_issues else "medium" if caveats else "pass"
    return {
        "report_id": f"report:{report_name}",
        "report_name": report_name,
        "pilot_summary_path": rel(pilot_path, root),
        "config_path": rel(config_row["path"], root) if config_row else None,
        "experiment_id": (config_row["config"].get("experiment_id") if config_row else None),
        "dataset_ids": dataset_ids_from_summary(payload),
        "cp_methods": cp_methods,
        "status_counts": status_counts,
        "ledger_rows": metadata.get("ledger_rows"),
        "unique_run_rows": metadata.get("unique_run_rows"),
        "summary_rows": len(payload.get("rows", []) or []),
        "large_sweep": large,
        "split_profile": split,
        "endpoint_audit": endpoint,
        "feature_leakage_audit": feature,
        "grouped_cv_audit": grouped_cv,
        "blocking_issues": sorted(set(blocking_issues)),
        "caveats": sorted(set(caveats)),
        "risk_level": risk_level,
    }


def build_payload(root: Path) -> dict[str, Any]:
    configs = config_index(root)
    pilot_paths = [
        path
        for path in sorted((root / "experiments/regression/reports").glob("**/pilot_summary.json"))
        if not sanity.is_root_aggregate_pilot_summary(path, root)
    ]
    report_rows = [build_report_row(root, path, configs) for path in pilot_paths]
    risk_counts = Counter(row["risk_level"] for row in report_rows)
    caveat_counts: Counter[str] = Counter()
    blocking_counts: Counter[str] = Counter()
    for row in report_rows:
        caveat_counts.update(row["caveats"])
        blocking_counts.update(row["blocking_issues"])

    split_integrity = sanity.split_profile_integrity_scan(root)
    feature_sidecars = sanity.feature_leakage_sidecar_scan(root)
    feature_drop_guard = sanity.runner_feature_drop_guard_scan(root)
    loader_policy = sanity.config_loader_leakage_policy_scan(
        sanity.scan_configs(root),
        root,
    )
    unsupported_hits = sanity.unsupported_claim_scan(root)
    leakage_status = (
        "blocking_issue_detected"
        if blocking_counts
        else "hard_leakage_not_detected_in_scanned_artifacts"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "methodology_sanity_audit_path": (
            "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "sanity_audit.json"
        ),
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "configs_scanned": len(configs),
            "reports_scanned": len(report_rows),
            "large_sweep_reports": sum(1 for row in report_rows if row["large_sweep"]),
            "risk_counts": dict(sorted(risk_counts.items())),
            "blocking_issue_counts": dict(sorted(blocking_counts.items())),
            "caveat_counts": dict(sorted(caveat_counts.items())),
            "total_completed_rows": sum(
                safe_int(row["status_counts"].get("completed")) for row in report_rows
            ),
            "feature_leakage_sidecar_reports": sum(
                1 for row in report_rows if row["feature_leakage_audit"]["present"]
            ),
            "feature_metadata_selection_counts": feature_metadata_selection_counts(
                report_rows
            ),
            "feature_policy_inference_counts": feature_policy_inference_counts(
                report_rows
            ),
            "split_profile_reports": sum(
                1 for row in report_rows if row["split_profile"]["present"]
            ),
            "endpoint_audit_reports": sum(
                1 for row in report_rows if row["endpoint_audit"]["present"]
            ),
            "grouped_cv_audit_reports": sum(
                1 for row in report_rows if row["grouped_cv_audit"]["configured"]
            ),
            "grouped_cv_metadata_failure_rows": sum(
                safe_int(row["grouped_cv_audit"]["failure_count"])
                for row in report_rows
            ),
            "unsupported_claim_hits": len(unsupported_hits),
            "leakage_status": leakage_status,
        },
        "study_level_layers": {
            "split_profile_integrity_scan": split_integrity,
            "feature_leakage_sidecar_scan": feature_sidecars,
            "runner_feature_drop_guard_scan": feature_drop_guard,
            "config_loader_leakage_policy_scan": loader_policy,
            "unsupported_claim_scan": unsupported_hits,
        },
        "rows": report_rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Cross-Run Scientific Integrity Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Reports scanned: {summary['reports_scanned']}",
        f"- Configs scanned: {summary['configs_scanned']}",
        f"- Large-sweep reports: {summary['large_sweep_reports']}",
        f"- Total completed rows represented: {summary['total_completed_rows']}",
        f"- Risk counts: `{summary['risk_counts']}`",
        f"- Leakage status: `{summary['leakage_status']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(
        [
            "",
            "## Study-Level Layers",
            "",
            f"- Split profiles scanned: {payload['study_level_layers']['split_profile_integrity_scan']['split_profiles_scanned']}",
            f"- Row-id overlap violation seed profiles: {payload['study_level_layers']['split_profile_integrity_scan']['row_id_overlap_violations']}",
            f"- Split-group overlap violation seed profiles: {payload['study_level_layers']['split_profile_integrity_scan']['split_group_overlap_violations']}",
            f"- Duplicate-signature warning seed profiles: {payload['study_level_layers']['split_profile_integrity_scan']['duplicate_signature_warnings']}",
            f"- Feature-leakage sidecars scanned: {payload['study_level_layers']['feature_leakage_sidecar_scan']['reports_scanned']}",
            f"- Feature-leakage sidecar violations: {payload['study_level_layers']['feature_leakage_sidecar_scan']['violations_count']}",
            f"- Feature metadata selection counts: `{summary['feature_metadata_selection_counts']}`",
            f"- Feature policy inference counts: `{summary['feature_policy_inference_counts']}`",
            f"- Grouped-CV audit reports: {summary['grouped_cv_audit_reports']}",
            f"- Grouped-CV metadata failure rows: {summary['grouped_cv_metadata_failure_rows']}",
            f"- Unsupported-claim hits: {len(payload['study_level_layers']['unsupported_claim_scan'])}",
            "",
            "## Report Matrix",
            "",
            "| Report | Risk | Completed | Split | Endpoint | Feature audit | Blocking issues | Caveats |",
            "| --- | --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in sorted(payload["rows"], key=lambda item: (item["risk_level"], item["report_name"])):
        split_status = "yes" if row["split_profile"]["present"] else "no"
        endpoint_status = "yes" if row["endpoint_audit"]["present"] else "no"
        feature_status = "yes" if row["feature_leakage_audit"]["present"] else "no"
        blocking = ", ".join(row["blocking_issues"]) if row["blocking_issues"] else "none"
        caveats = ", ".join(row["caveats"]) if row["caveats"] else "none"
        lines.append(
            "| "
            f"`{row['report_name']}` | "
            f"{row['risk_level']} | "
            f"{safe_int(row['status_counts'].get('completed'))} | "
            f"{split_status} | "
            f"{endpoint_status} | "
            f"{feature_status} | "
            f"{blocking} | "
            f"{caveats} |"
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
