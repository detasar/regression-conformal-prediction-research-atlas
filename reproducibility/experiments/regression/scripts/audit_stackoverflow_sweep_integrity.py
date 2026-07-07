"""Audit StackOverflow sweep prediction metadata and runtime-cap skips."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.backfill_feature_leakage_metadata_completeness_fields import (
    standard_metadata_completeness_fields,
)


FORBIDDEN_EXACT_COLUMNS = {
    "Age",
    "CompTotal",
    "ConvertedCompYearly",
    "Currency",
    "WorkExp",
    "YearsCode",
}
EXPECTED_RUNTIME_CAP_METHODS = {
    "cv_minmax",
    "cv_plus",
    "jackknife_minmax",
    "jackknife_plus",
    "jackknife_plus_after_bootstrap",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pre-run-profile",
        default=(
            "experiments/regression/reports/"
            "model_family_sweep_stackoverflow_2025_compensation_log1p_age/"
            "pre_run_profile.json"
        ),
    )
    parser.add_argument(
        "--ledger",
        default=(
            "experiments/regression/results/"
            "model_family_sweep_stackoverflow_2025_compensation_log1p_age/"
            "ledger.jsonl"
        ),
    )
    parser.add_argument(
        "--prediction-cache-root",
        default=(
            "experiments/regression/results/"
            "model_family_sweep_stackoverflow_2025_compensation_log1p_age/"
            "checkpoints/predictions"
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=(
            "experiments/regression/reports/"
            "model_family_sweep_stackoverflow_2025_compensation_log1p_age"
        ),
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def audit_feature_leakage(
    *,
    pre_run_profile: dict[str, Any],
    prediction_cache_root: Path,
) -> dict[str, Any]:
    expected_features = set(pre_run_profile["features_after_target_group_drop"])
    paths = sorted(prediction_cache_root.glob("*/*/metadata.json"))
    violations = []
    feature_sets: Counter[tuple[str, ...]] = Counter()
    row_counts: Counter[tuple[tuple[str, Any], ...]] = Counter()
    transforms: Counter[str] = Counter()
    models: Counter[str] = Counter()
    seeds: Counter[str] = Counter()

    for path in paths:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        features = set(metadata.get("feature_names", []))
        preprocessed_features = set(metadata.get("preprocessed_feature_names", []))
        policy = metadata.get("feature_drop_policy", {})
        bad_features = sorted(FORBIDDEN_EXACT_COLUMNS & features)
        bad_preprocessed = sorted(FORBIDDEN_EXACT_COLUMNS & preprocessed_features)
        missing_expected = sorted(expected_features - features)
        extra_features = sorted(features - expected_features)
        policy_ok = (
            policy.get("target") == "ConvertedCompYearly"
            and policy.get("primary_group_col") == "Age"
        )
        if (
            bad_features
            or bad_preprocessed
            or missing_expected
            or extra_features
            or not policy_ok
        ):
            violations.append(
                {
                    "path": str(path),
                    "artifact_id": metadata.get("artifact_id"),
                    "model_id": metadata.get("model_id"),
                    "seed": metadata.get("seed"),
                    "bad_feature_names": bad_features,
                    "bad_preprocessed_feature_names": bad_preprocessed,
                    "missing_expected_features": missing_expected,
                    "extra_features": extra_features,
                    "feature_drop_policy": policy,
                }
            )
        feature_sets[tuple(sorted(features))] += 1
        row_counts[tuple(sorted((metadata.get("row_counts") or {}).items()))] += 1
        transforms[str(metadata.get("target_transform"))] += 1
        models[str(metadata.get("model_id"))] += 1
        seeds[str(metadata.get("seed"))] += 1

    return {
        "schema": "cpfi_stackoverflow_feature_leakage_audit_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metadata_files_scanned": len(paths),
        "forbidden_exact_columns": sorted(FORBIDDEN_EXACT_COLUMNS),
        "expected_model_visible_features": sorted(expected_features),
        "violations_count": len(violations),
        "violations": violations[:25],
        "unique_feature_sets": [
            {"count": count, "features": list(features)}
            for features, count in feature_sets.items()
        ],
        "row_count_patterns": [
            {"count": count, "row_counts": dict(row_count)}
            for row_count, count in row_counts.items()
        ],
        **standard_metadata_completeness_fields(paths),
        "target_transform_counts": dict(sorted(transforms.items())),
        "model_counts": dict(sorted(models.items())),
        "seed_counts": dict(sorted(seeds.items())),
    }


def audit_runtime_caps(ledger_rows: list[dict[str, Any]], ledger_path: Path) -> dict[str, Any]:
    completed = [row for row in ledger_rows if row.get("status") == "completed"]
    skipped = [row for row in ledger_rows if row.get("status") == "skipped_method"]
    by_method = Counter(str(row.get("cp_method")) for row in skipped)
    messages = Counter(
        str(row.get("error_message") or row.get("skip_reason") or row.get("message") or "")
        for row in skipped
    )
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in skipped:
        method = str(row.get("cp_method"))
        if len(examples[method]) < 3:
            examples[method].append(
                {
                    key: row.get(key)
                    for key in [
                        "run_id",
                        "model_id",
                        "cp_method",
                        "seed",
                        "error_type",
                        "error_message",
                        "skip_reason",
                        "message",
                    ]
                    if key in row
                }
            )
    return {
        "schema": "cpfi_stackoverflow_runtime_cap_audit_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "ledger": str(ledger_path),
        "completed_rows": len(completed),
        "skipped_method_rows": len(skipped),
        "skipped_methods": dict(sorted(by_method.items())),
        "expected_runtime_cap_methods": sorted(EXPECTED_RUNTIME_CAP_METHODS),
        "unexpected_skipped_methods": sorted(set(by_method) - EXPECTED_RUNTIME_CAP_METHODS),
        "missing_expected_skipped_methods": sorted(EXPECTED_RUNTIME_CAP_METHODS - set(by_method)),
        "skip_messages": dict(sorted(messages.items())),
        "examples": dict(examples),
    }


def render_feature_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# StackOverflow Feature Leakage Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Prediction metadata files scanned: {payload['metadata_files_scanned']}",
        f"- Violations: {payload['violations_count']}",
        f"- Target transform counts: `{payload['target_transform_counts']}`",
        f"- Seed counts: `{payload['seed_counts']}`",
        f"- Model counts: `{payload['model_counts']}`",
        "",
        "## Feature Policy",
        "",
        "- Expected model-visible features: "
        + ", ".join(payload["expected_model_visible_features"]),
        "- Forbidden exact columns: " + ", ".join(payload["forbidden_exact_columns"]),
        "",
        "## Violations",
        "",
    ]
    if payload["violations_count"]:
        lines.append(json.dumps(payload["violations"], indent=2, sort_keys=True))
    else:
        lines.append(
            "No forbidden exact feature-name, missing expected feature, extra raw "
            "feature, or target/group drop-policy violation was found."
        )
    return "\n".join(lines) + "\n"


def render_runtime_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# StackOverflow Runtime-Cap Skip Audit",
            "",
            f"- Generated UTC: {payload['generated_at_utc']}",
            f"- Completed rows: {payload['completed_rows']}",
            f"- Skipped-method rows: {payload['skipped_method_rows']}",
            f"- Skipped methods: `{payload['skipped_methods']}`",
            f"- Unexpected skipped methods: `{payload['unexpected_skipped_methods']}`",
            f"- Missing expected skipped methods: `{payload['missing_expected_skipped_methods']}`",
            "",
            "## Interpretation",
            "",
            "All skipped-method rows are expected runtime-cap controls if the two "
            "unexpected/missing lists above are empty. These rows must not be "
            "described as completed full-data plus/jackknife evidence.",
            "",
        ]
    )


def main() -> None:
    args = parse_args()
    pre_run_profile_path = Path(args.pre_run_profile)
    ledger_path = Path(args.ledger)
    prediction_cache_root = Path(args.prediction_cache_root)
    out_dir = Path(args.out_dir)

    pre_run_profile = json.loads(pre_run_profile_path.read_text(encoding="utf-8"))
    ledger_rows = load_jsonl(ledger_path)
    feature_payload = audit_feature_leakage(
        pre_run_profile=pre_run_profile,
        prediction_cache_root=prediction_cache_root,
    )
    runtime_payload = audit_runtime_caps(ledger_rows, ledger_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "feature_leakage_audit.json", feature_payload)
    atomic_write_text(
        out_dir / "feature_leakage_audit.md",
        render_feature_markdown(feature_payload),
    )
    atomic_write_json(out_dir / "runtime_cap_audit.json", runtime_payload)
    atomic_write_text(
        out_dir / "runtime_cap_audit.md",
        render_runtime_markdown(runtime_payload),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "metadata_files_scanned": feature_payload["metadata_files_scanned"],
                "feature_violations": feature_payload["violations_count"],
                "skipped_method_rows": runtime_payload["skipped_method_rows"],
                "unexpected_skipped_methods": runtime_payload[
                    "unexpected_skipped_methods"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
