"""Audit prediction-bundle metadata for feature leakage guardrails."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


LEGACY_PREPROCESSED_FEATURE_NAME_SCHEMAS = {
    "prediction_bundle_v2",
    "prediction_bundle_v3",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prediction-cache-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--config")
    parser.add_argument("--title", default="Prediction Feature Leakage Audit")
    parser.add_argument("--output-prefix", default="feature_leakage_audit")
    parser.add_argument("--forbidden-feature", action="append", default=[])
    parser.add_argument("--required-feature", action="append", default=[])
    parser.add_argument("--expected-feature", action="append", default=[])
    parser.add_argument("--expected-drop-column", action="append", default=[])
    parser.add_argument("--expected-target")
    parser.add_argument("--expected-group-col")
    parser.add_argument("--expected-target-transform")
    parser.add_argument(
        "--close-missing-preprocessed-feature-names-from-feature-names",
        action="store_true",
        help=(
            "For legacy no-reducer bundles, treat feature_names as audited "
            "preprocessing-output feature names while preserving raw missingness."
        ),
    )
    parser.add_argument(
        "--close-missing-drop-metadata-from-expected-policy",
        action="store_true",
        help=(
            "For legacy bundles, close missing feature_drop_columns and "
            "feature_drop_policy using explicit expected target/group/drop "
            "arguments while preserving raw missingness."
        ),
    )
    return parser.parse_args()


def _counter_rows(counter: Counter[tuple[str, ...]]) -> list[dict[str, Any]]:
    return [
        {"count": int(count), "values": list(values)}
        for values, count in sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {str(key): int(value) for key, value in sorted(counter.items())}


def _feature_reducer_method(metadata: dict[str, Any]) -> str:
    reducer = metadata.get("feature_reducer")
    if reducer is None:
        return "none"
    if isinstance(reducer, dict):
        return str(reducer.get("method", "none")).lower()
    return str(reducer).lower()


def effective_preprocessed_feature_names(
    metadata: dict[str, Any],
) -> tuple[list[Any], bool]:
    """Return audited preprocessing-output names and whether they were inferred.

    Legacy v2/v3 bundles predate the explicit `preprocessed_feature_names`
    field. In those schemas, when no feature reducer is configured, the stored
    `feature_names` field is the model-input feature vector and is equivalent
    to preprocessing-output names. Do not apply this to v1 bundles or any
    reducer-backed bundle.
    """

    preprocessed = metadata.get("preprocessed_feature_names")
    if preprocessed is not None:
        return list(preprocessed), False

    schema = str(metadata.get("artifact_schema") or "")
    feature_names = metadata.get("feature_names")
    if (
        schema in LEGACY_PREPROCESSED_FEATURE_NAME_SCHEMAS
        and feature_names is not None
        and _feature_reducer_method(metadata) in {"", "none"}
    ):
        return list(feature_names), True
    return [], False


def _render_list(values: list[str]) -> str:
    return ", ".join(values) if values else "not requested"


def _render_optional(value: Any) -> str:
    return str(value) if value is not None else "not requested"


def scan_metadata(
    prediction_cache_root: Path,
    *,
    forbidden_features: set[str],
    required_features: set[str],
    expected_features: set[str],
    expected_drop_columns: set[str],
    expected_target: str | None,
    expected_group_col: str | None,
    expected_target_transform: str | None,
    config_path: str | None = None,
    metadata_paths: list[Path] | None = None,
    close_missing_preprocessed_feature_names_from_feature_names: bool = False,
    close_missing_drop_metadata_from_expected_policy: bool = False,
) -> dict[str, Any]:
    if close_missing_drop_metadata_from_expected_policy and (
        expected_target is None
        or expected_group_col is None
        or not expected_drop_columns
    ):
        raise ValueError(
            "drop-metadata closure requires expected target, group, and drop columns"
        )
    paths = (
        sorted(metadata_paths)
        if metadata_paths is not None
        else sorted(prediction_cache_root.glob("*/*/metadata.json"))
    )
    violations: list[dict[str, Any]] = []
    feature_sets: Counter[tuple[str, ...]] = Counter()
    preprocessed_feature_sets: Counter[tuple[str, ...]] = Counter()
    drop_sets: Counter[tuple[str, ...]] = Counter()
    datasets: Counter[str] = Counter()
    models: Counter[str] = Counter()
    seeds: Counter[str] = Counter()
    target_transforms: Counter[str] = Counter()
    dataset_seed_counts: Counter[tuple[str, str]] = Counter()
    dataset_seed_model_configs: dict[tuple[str, str], set[str]] = {}
    missing_feature_names = 0
    missing_preprocessed_feature_names = 0
    missing_feature_drop_columns = 0
    missing_feature_drop_policy = 0
    raw_missing_feature_names = 0
    raw_missing_preprocessed_feature_names = 0
    raw_missing_feature_drop_columns = 0
    raw_missing_feature_drop_policy = 0
    inferred_preprocessed_feature_names = 0
    closed_preprocessed_feature_names = 0
    closed_feature_drop_columns = 0
    closed_feature_drop_policy = 0

    for path in paths:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if metadata.get("feature_names") is None:
            missing_feature_names += 1
            raw_missing_feature_names += 1
        (
            audited_preprocessed_feature_names,
            inferred_preprocessed_names,
        ) = effective_preprocessed_feature_names(metadata)
        if metadata.get("preprocessed_feature_names") is None:
            raw_missing_preprocessed_feature_names += 1
            if inferred_preprocessed_names:
                inferred_preprocessed_feature_names += 1
            elif (
                close_missing_preprocessed_feature_names_from_feature_names
                and metadata.get("feature_names") is not None
                and _feature_reducer_method(metadata) in {"", "none"}
            ):
                audited_preprocessed_feature_names = list(metadata["feature_names"])
                closed_preprocessed_feature_names += 1
            else:
                missing_preprocessed_feature_names += 1
        feature_drop_columns_raw = metadata.get("feature_drop_columns")
        feature_drop_policy_raw = metadata.get("feature_drop_policy")
        if metadata.get("feature_drop_columns") is None:
            raw_missing_feature_drop_columns += 1
            if close_missing_drop_metadata_from_expected_policy:
                feature_drop_columns_raw = sorted(expected_drop_columns)
                closed_feature_drop_columns += 1
            else:
                missing_feature_drop_columns += 1
        if metadata.get("feature_drop_policy") is None:
            raw_missing_feature_drop_policy += 1
            if close_missing_drop_metadata_from_expected_policy:
                feature_drop_policy_raw = {
                    "target": expected_target,
                    "primary_group_col": expected_group_col,
                }
                closed_feature_drop_policy += 1
            else:
                missing_feature_drop_policy += 1
        feature_names = {str(value) for value in metadata.get("feature_names", [])}
        preprocessed_feature_names = {
            str(value) for value in audited_preprocessed_feature_names
        }
        drop_columns = {str(value) for value in feature_drop_columns_raw or []}
        policy = feature_drop_policy_raw or {}

        bad_feature_names = sorted(forbidden_features & feature_names)
        bad_preprocessed_feature_names = sorted(
            forbidden_features & preprocessed_feature_names
        )
        missing_required_features = sorted(required_features - feature_names)
        missing_expected_features = sorted(expected_features - feature_names)
        extra_features = (
            sorted(feature_names - expected_features) if expected_features else []
        )
        missing_expected_drop_columns = sorted(expected_drop_columns - drop_columns)
        target_policy_ok = (
            True
            if expected_target is None
            else metadata.get("target") == expected_target
            and policy.get("target") == expected_target
        )
        group_policy_ok = (
            True
            if expected_group_col is None
            else metadata.get("group_col") == expected_group_col
            and policy.get("primary_group_col") == expected_group_col
        )
        transform_ok = (
            True
            if expected_target_transform is None
            else metadata.get("target_transform") == expected_target_transform
        )

        if (
            bad_feature_names
            or bad_preprocessed_feature_names
            or missing_required_features
            or missing_expected_features
            or extra_features
            or missing_expected_drop_columns
            or not target_policy_ok
            or not group_policy_ok
            or not transform_ok
        ):
            violations.append(
                {
                    "path": str(path),
                    "artifact_id": metadata.get("artifact_id"),
                    "dataset_id": metadata.get("dataset_id"),
                    "model_id": metadata.get("model_id"),
                    "seed": metadata.get("seed"),
                    "bad_feature_names": bad_feature_names,
                    "bad_preprocessed_feature_names": bad_preprocessed_feature_names,
                    "missing_required_features": missing_required_features,
                    "missing_expected_features": missing_expected_features,
                    "extra_features": extra_features,
                    "missing_expected_drop_columns": missing_expected_drop_columns,
                    "target_policy_ok": target_policy_ok,
                    "group_policy_ok": group_policy_ok,
                    "target_transform_ok": transform_ok,
                    "feature_drop_policy": policy,
                }
            )

        feature_sets[tuple(sorted(feature_names))] += 1
        preprocessed_feature_sets[tuple(sorted(preprocessed_feature_names))] += 1
        drop_sets[tuple(sorted(drop_columns))] += 1
        datasets[str(metadata.get("dataset_id"))] += 1
        models[str(metadata.get("model_id"))] += 1
        seeds[str(metadata.get("seed"))] += 1
        target_transforms[str(metadata.get("target_transform"))] += 1
        dataset_seed = (str(metadata.get("dataset_id")), str(metadata.get("seed")))
        dataset_seed_counts[dataset_seed] += 1
        model_config_key = json.dumps(
            {
                "model_id": metadata.get("model_id"),
                "model_params": metadata.get("model_params") or {},
            },
            sort_keys=True,
        )
        dataset_seed_model_configs.setdefault(dataset_seed, set()).add(model_config_key)

    dataset_counts = _counter_dict(datasets)
    dataset_seed_cells = [
        {
            "dataset_id": dataset_id,
            "seed": seed,
            "metadata_files": int(count),
            "unique_model_configs": len(dataset_seed_model_configs[(dataset_id, seed)]),
        }
        for (dataset_id, seed), count in sorted(dataset_seed_counts.items())
    ]
    return {
        "schema": "cpfi_prediction_feature_leakage_audit_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": config_path,
        "prediction_cache_root": str(prediction_cache_root),
        "metadata_files_scanned": len(paths),
        "forbidden_features": sorted(forbidden_features),
        "required_features": sorted(required_features),
        "expected_features": sorted(expected_features),
        "expected_drop_columns": sorted(expected_drop_columns),
        "expected_target": expected_target,
        "expected_group_col": expected_group_col,
        "expected_target_transform": expected_target_transform,
        "violations_count": len(violations),
        "violations": violations[:100],
        "unique_feature_sets": _counter_rows(feature_sets),
        "unique_preprocessed_feature_sets": _counter_rows(preprocessed_feature_sets),
        "unique_drop_sets": _counter_rows(drop_sets),
        "dataset_ids": sorted(key for key in dataset_counts if key != "None"),
        "dataset_counts": dataset_counts,
        "dataset_seed_cells": dataset_seed_cells,
        "model_counts": _counter_dict(models),
        "seed_counts": _counter_dict(seeds),
        "target_transform_counts": _counter_dict(target_transforms),
        "metadata_completeness": {
            "missing_feature_names": missing_feature_names,
            "missing_preprocessed_feature_names": missing_preprocessed_feature_names,
            "missing_feature_drop_columns": missing_feature_drop_columns,
            "missing_feature_drop_policy": missing_feature_drop_policy,
        },
        "raw_metadata_completeness": {
            "missing_feature_names": raw_missing_feature_names,
            "missing_preprocessed_feature_names": raw_missing_preprocessed_feature_names,
            "missing_feature_drop_columns": raw_missing_feature_drop_columns,
            "missing_feature_drop_policy": raw_missing_feature_drop_policy,
        },
        "metadata_inference": {
            "preprocessed_feature_names_from_legacy_feature_names": (
                inferred_preprocessed_feature_names
            ),
            "legacy_preprocessed_feature_name_schemas": sorted(
                LEGACY_PREPROCESSED_FEATURE_NAME_SCHEMAS
            ),
        },
        "metadata_closure": {
            "enabled": bool(
                close_missing_preprocessed_feature_names_from_feature_names
                or close_missing_drop_metadata_from_expected_policy
            ),
            "closed_preprocessed_feature_names_from_feature_names": (
                closed_preprocessed_feature_names
            ),
            "closed_feature_drop_columns_from_expected_policy": (
                closed_feature_drop_columns
            ),
            "closed_feature_drop_policy_from_expected_policy": (
                closed_feature_drop_policy
            ),
            "close_missing_preprocessed_feature_names_from_feature_names": bool(
                close_missing_preprocessed_feature_names_from_feature_names
            ),
            "close_missing_drop_metadata_from_expected_policy": bool(
                close_missing_drop_metadata_from_expected_policy
            ),
        },
    }


def render_markdown(payload: dict[str, Any], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Config: `{payload['config_path']}`",
        f"- Prediction metadata files scanned: {payload['metadata_files_scanned']}",
        f"- Violations: {payload['violations_count']}",
        f"- Dataset counts: `{payload['dataset_counts']}`",
        f"- Dataset x seed cells: `{payload['dataset_seed_cells']}`",
        f"- Seed counts: `{payload['seed_counts']}`",
        f"- Target transform counts: `{payload['target_transform_counts']}`",
        f"- Metadata completeness: `{payload['metadata_completeness']}`",
        "",
        "## Feature Policy",
        "",
        "- Forbidden features: " + _render_list(payload["forbidden_features"]),
        "- Required features: " + _render_list(payload["required_features"]),
        "- Expected exact feature set: " + _render_list(payload["expected_features"]),
        "- Expected drop columns: " + _render_list(payload["expected_drop_columns"]),
        f"- Expected target: `{_render_optional(payload['expected_target'])}`",
        f"- Expected group column: `{_render_optional(payload['expected_group_col'])}`",
        f"- Expected target transform: `{_render_optional(payload['expected_target_transform'])}`",
        "",
        "## Observed Feature Sets",
        "",
    ]
    for row in payload["unique_feature_sets"]:
        lines.append(f"- count={row['count']}: `{row['values']}`")
    completeness = payload["metadata_completeness"]
    inference = payload.get("metadata_inference") or {}
    raw_completeness = payload.get("raw_metadata_completeness") or {}
    closure = payload.get("metadata_closure") or {}
    missing_metadata_fields = {
        key: value for key, value in completeness.items() if int(value) > 0
    }
    lines.extend(["", "## Metadata Completeness Caveat", ""])
    raw_missing_metadata_fields = {
        key: value for key, value in raw_completeness.items() if int(value) > 0
    }
    if closure.get("enabled"):
        lines.append(
            "Raw legacy metadata missingness before explicit closure: "
            f"`{raw_missing_metadata_fields}`."
        )
        lines.append("")
        lines.append(f"Config-derived closure counts: `{closure}`.")
        lines.append("")
    inferred_preprocessed = int(
        inference.get("preprocessed_feature_names_from_legacy_feature_names") or 0
    )
    if inferred_preprocessed:
        lines.append(
            "Legacy preprocessing-output feature names inferred from "
            f"`feature_names` for {inferred_preprocessed} no-reducer v2/v3 "
            "prediction metadata files."
        )
        lines.append("")
    if missing_metadata_fields:
        lines.append(
            "Some prediction metadata fields are absent: "
            f"`{missing_metadata_fields}`. Interpret zero violations as applying "
            "to the available metadata fields and explicitly requested checks, "
            "not as proof that unavailable metadata fields were validated."
        )
    else:
        if closure.get("enabled"):
            lines.append(
                "All tracked feature/drop-policy checks are closed after applying "
                "the explicit config-derived closure above."
            )
        else:
            lines.append(
                "All tracked prediction metadata fields are present for the scanned files."
            )
    lines.extend(["", "## Violations", ""])
    if payload["violations_count"]:
        lines.append(json.dumps(payload["violations"], indent=2, sort_keys=True))
    else:
        lines.append(
            "No forbidden feature, missing required feature, unexpected exact "
            "feature-set, expected-drop, target/group policy, or target-transform "
            "violation was found."
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "This is a prediction-metadata feature/drop-policy audit only. It is "
            "not fairness evidence, legal/admissions guidance, causal evidence, "
            "production evidence, final-model selection evidence, or proof that "
            "all proxy leakage has been removed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    payload = scan_metadata(
        Path(args.prediction_cache_root),
        forbidden_features={str(value) for value in args.forbidden_feature},
        required_features={str(value) for value in args.required_feature},
        expected_features={str(value) for value in args.expected_feature},
        expected_drop_columns={str(value) for value in args.expected_drop_column},
        expected_target=args.expected_target,
        expected_group_col=args.expected_group_col,
        expected_target_transform=args.expected_target_transform,
        config_path=args.config,
        close_missing_preprocessed_feature_names_from_feature_names=(
            args.close_missing_preprocessed_feature_names_from_feature_names
        ),
        close_missing_drop_metadata_from_expected_policy=(
            args.close_missing_drop_metadata_from_expected_policy
        ),
    )
    atomic_write_json(out_dir / f"{args.output_prefix}.json", payload)
    atomic_write_text(
        out_dir / f"{args.output_prefix}.md",
        render_markdown(payload, args.title),
    )
    print(json.dumps({"status": "ok", "violations_count": payload["violations_count"]}))


if __name__ == "__main__":
    main()
