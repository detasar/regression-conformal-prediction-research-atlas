"""Generate split-profile sidecars for regression experiment configs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.run_regression_pilot import (
    DATASET_LOADERS,
    DUPLICATE_CLUSTER_SPLIT_COL,
    add_duplicate_cluster_split_group,
    load_dataset_frame,
    runner_feature_drop_columns,
    split_frame,
)


SPARSE_PRIMARY_GROUP_THRESHOLD = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Regression experiment YAML config.")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output report directory. Defaults to reports/<config stem>.",
    )
    return parser.parse_args()


def target_summary(frame: pd.DataFrame, target: str) -> dict[str, Any]:
    values = pd.to_numeric(frame[target], errors="coerce").dropna()
    if values.empty:
        return {
            "target_min": None,
            "target_p50": None,
            "target_mean": None,
            "target_p95": None,
            "target_max": None,
        }
    return {
        "target_min": float(values.min()),
        "target_p50": float(values.quantile(0.50)),
        "target_mean": float(values.mean()),
        "target_p95": float(values.quantile(0.95)),
        "target_max": float(values.max()),
    }


def value_counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in frame.columns:
        return {}
    values = (
        frame[column]
        .astype("object")
        .where(frame[column].notna(), "__missing__")
        .astype(str)
    )
    return {str(key): int(value) for key, value in values.value_counts().sort_index().items()}


def row_signature_set(
    frame: pd.DataFrame,
    exclude_columns: set[str] | None = None,
) -> set[str]:
    comparable = frame.copy()
    if exclude_columns:
        comparable = comparable.drop(
            columns=[column for column in exclude_columns if column in comparable.columns]
        )
    comparable = comparable.reindex(sorted(comparable.columns), axis=1)
    comparable = comparable.astype("object").where(comparable.notna(), "__missing__")
    hashes = pd.util.hash_pandas_object(comparable, index=False).astype(str)
    return set(hashes)


def split_group_values(frame: pd.DataFrame, column: str | None) -> set[str]:
    if not column or column not in frame.columns:
        return set()
    values = (
        frame[column]
        .astype("object")
        .where(frame[column].notna(), "__missing__")
        .astype(str)
    )
    return set(values)


def row_id_set(frame: pd.DataFrame, row_id_col: str) -> set[str]:
    if row_id_col not in frame.columns:
        return set()
    return set(frame[row_id_col].astype(str))


def overlap_count(left: set[str], right: set[str]) -> int:
    return len(left.intersection(right))


def sparse_primary_group_cells(
    split_rows: dict[str, dict[str, Any]],
    *,
    threshold: int = SPARSE_PRIMARY_GROUP_THRESHOLD,
) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for split_name in ("train", "cal", "test"):
        group_counts = split_rows.get(split_name, {}).get("group_counts", {})
        for group, count in sorted(group_counts.items()):
            if int(count) < threshold:
                cells.append(
                    {
                        "split": split_name,
                        "group": str(group),
                        "count": int(count),
                        "threshold": int(threshold),
                    }
                )
    return cells


def profile_one_dataset(
    dataset_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    df, target, primary_group = load_dataset_frame(dataset_id)
    row_id_col = "__cpfi_audit_row_id__"
    while row_id_col in df.columns:
        row_id_col = f"_{row_id_col}"
    split_config = config.get("splits", {})
    train_size = float(split_config["train"])
    calibration_size = float(split_config["calibration"])
    split_group_col = split_config.get("group_col")
    split_strategy = split_config.get("strategy")
    split_order_col = split_config.get("order_col")
    duplicate_cluster_scope = split_config.get("duplicate_cluster_scope")

    rows_before_target_drop = int(len(df))
    rows_after_target_drop = int(df[target].notna().sum())
    base_split_group_col = None if split_group_col is None else str(split_group_col)
    split_df, effective_split_group_col = add_duplicate_cluster_split_group(
        df,
        dataset_id=dataset_id,
        target=target,
        group_col=primary_group,
        split_group_col=base_split_group_col,
        scope=None if duplicate_cluster_scope is None else str(duplicate_cluster_scope),
    )
    split_df = split_df.copy()
    split_df[row_id_col] = np.arange(len(split_df), dtype=np.int64)
    model_feature_drop = runner_feature_drop_columns(
        dataset_id,
        target,
        primary_group,
        effective_split_group_col,
        split_df,
        base_split_group_col=(
            None
            if duplicate_cluster_scope is None or base_split_group_col is None
            else str(base_split_group_col)
        ),
    )
    dataset_profile = {
        "dataset_id": dataset_id,
        "target": target,
        "primary_group": primary_group,
        "source": DATASET_LOADERS.get(dataset_id, {}).get("source"),
        "rows_before_target_drop": rows_before_target_drop,
        "rows_after_target_drop": rows_after_target_drop,
        "target_missing_before_split": rows_before_target_drop - rows_after_target_drop,
        "target_missing_rate_before_split": (
            (rows_before_target_drop - rows_after_target_drop) / rows_before_target_drop
            if rows_before_target_drop
            else None
        ),
        "split_group_col": effective_split_group_col,
        "base_split_group_col": base_split_group_col,
        "split_strategy": "random" if split_strategy is None else str(split_strategy),
        "split_order_col": None if split_order_col is None else str(split_order_col),
        "duplicate_cluster_scope": (
            None if duplicate_cluster_scope is None else str(duplicate_cluster_scope)
        ),
        "duplicate_cluster_split_col": (
            DUPLICATE_CLUSTER_SPLIT_COL
            if duplicate_cluster_scope is not None
            else None
        ),
        "model_visible_feature_drop_columns": model_feature_drop,
        "seeds": [],
    }

    for seed in config.get("random_seeds", []):
        splits = split_frame(
            split_df,
            target=target,
            group_col=primary_group,
            seed=int(seed),
            train_size=train_size,
            calibration_size=calibration_size,
            split_group_col=effective_split_group_col,
            split_strategy=split_strategy,
            split_order_col=split_order_col,
        )
        split_rows = {}
        split_group_sets = {}
        row_id_sets = {}
        row_signature_sets = {}
        model_visible_feature_signature_sets = {}
        model_visible_feature_plus_target_signature_sets = {}
        for split_name in ("train", "cal", "test"):
            frame = splits[split_name]
            split_rows[split_name] = {
                "rows": int(len(frame)),
                "group_counts": value_counts(frame, primary_group),
                "split_group_counts": value_counts(frame, str(effective_split_group_col))
                if effective_split_group_col
                else {},
                **target_summary(frame, target),
            }
            split_group_sets[split_name] = split_group_values(
                frame,
                effective_split_group_col,
            )
            row_id_sets[split_name] = row_id_set(frame, row_id_col)
            row_signature_sets[split_name] = row_signature_set(
                frame,
                exclude_columns={row_id_col},
            )
            model_visible_feature_signature_sets[split_name] = row_signature_set(
                frame,
                exclude_columns={row_id_col, *model_feature_drop},
            )
            model_visible_feature_plus_target_signature_sets[split_name] = (
                row_signature_set(
                    frame,
                    exclude_columns={
                        row_id_col,
                        *[column for column in model_feature_drop if column != target],
                    },
                )
            )

        pair_names = [("train", "cal"), ("train", "test"), ("cal", "test")]
        split_group_overlaps = {
            f"{left}_{right}": overlap_count(split_group_sets[left], split_group_sets[right])
            for left, right in pair_names
        }
        row_id_overlaps = {
            f"{left}_{right}": overlap_count(row_id_sets[left], row_id_sets[right])
            for left, right in pair_names
        }
        row_signature_overlaps = {
            f"{left}_{right}": overlap_count(
                row_signature_sets[left],
                row_signature_sets[right],
            )
            for left, right in pair_names
        }
        model_visible_feature_signature_overlaps = {
            f"{left}_{right}": overlap_count(
                model_visible_feature_signature_sets[left],
                model_visible_feature_signature_sets[right],
            )
            for left, right in pair_names
        }
        model_visible_feature_plus_target_signature_overlaps = {
            f"{left}_{right}": overlap_count(
                model_visible_feature_plus_target_signature_sets[left],
                model_visible_feature_plus_target_signature_sets[right],
            )
            for left, right in pair_names
        }
        sparse_cells = sparse_primary_group_cells(split_rows)
        dataset_profile["seeds"].append(
            {
                "seed": int(seed),
                "splits": split_rows,
                "sparse_primary_group_cells": sparse_cells,
                "sparse_primary_group_cell_count": len(sparse_cells),
                "all_primary_group_cells_at_least_threshold": len(sparse_cells) == 0,
                "sparse_primary_group_threshold": SPARSE_PRIMARY_GROUP_THRESHOLD,
                "split_group_overlaps": split_group_overlaps,
                "row_id_overlaps": row_id_overlaps,
                "row_signature_overlaps": row_signature_overlaps,
                "model_visible_feature_signature_cross_split_overlaps": (
                    model_visible_feature_signature_overlaps
                ),
                "model_visible_feature_plus_target_signature_cross_split_overlaps": (
                    model_visible_feature_plus_target_signature_overlaps
                ),
                "all_split_group_overlaps_zero": all(
                    value == 0 for value in split_group_overlaps.values()
                )
                if effective_split_group_col
                else None,
                "all_row_id_overlaps_zero": all(
                    value == 0 for value in row_id_overlaps.values()
                ),
                "all_row_signature_overlaps_zero": all(
                    value == 0 for value in row_signature_overlaps.values()
                ),
                "all_model_visible_feature_signature_overlaps_zero": all(
                    value == 0
                    for value in model_visible_feature_signature_overlaps.values()
                ),
                "all_model_visible_feature_plus_target_signature_overlaps_zero": all(
                    value == 0
                    for value in model_visible_feature_plus_target_signature_overlaps.values()
                ),
            }
        )
    return dataset_profile


def build_payload(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    dataset_ids = [str(dataset_id) for dataset_id in config.get("datasets", [])]
    profiles = [profile_one_dataset(dataset_id, config) for dataset_id in dataset_ids]
    split_config = config.get("splits", {})
    payload = {
        "schema": "cpfi_regression_split_profile_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path),
        "experiment_id": config.get("experiment_id"),
        "run_id": config_path.stem,
        "dataset_ids": dataset_ids,
        "dataset_id": dataset_ids[0] if len(dataset_ids) == 1 else None,
        "target_transform": config.get("target_transform", "identity"),
        "split_config": {
            "train": float(split_config["train"]),
            "calibration": float(split_config["calibration"]),
            "test": float(
                split_config.get(
                    "test",
                    1.0
                    - float(split_config["train"])
                    - float(split_config["calibration"]),
                )
            ),
            "group_col": split_config.get("group_col"),
            "strategy": split_config.get("strategy", "random"),
            "order_col": split_config.get("order_col"),
            "duplicate_cluster_scope": split_config.get("duplicate_cluster_scope"),
            "duplicate_cluster_split_col": (
                DUPLICATE_CLUSTER_SPLIT_COL
                if split_config.get("duplicate_cluster_scope") is not None
                else None
            ),
        },
        "profiles": profiles,
    }
    if len(profiles) == 1:
        first = profiles[0]
        payload["primary_group"] = first["primary_group"]
        payload["target"] = first["target"]
        payload["seeds"] = first["seeds"]
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Regression Split Profile",
        "",
        f"- Generated UTC: {payload['created_at_utc']}",
        f"- Config: `{payload['config_path']}`",
        f"- Experiment id: `{payload.get('experiment_id')}`",
        f"- Target transform: `{payload.get('target_transform')}`",
        f"- Datasets: {', '.join(f'`{item}`' for item in payload['dataset_ids'])}",
        "",
        "## Split Config",
        "",
    ]
    for key, value in payload["split_config"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Dataset Profiles", ""])
    for profile in payload["profiles"]:
        lines.extend(
            [
                f"### {profile['dataset_id']}",
                "",
                f"- Target: `{profile['target']}`",
                f"- Primary group: `{profile['primary_group']}`",
                f"- Rows before target drop: {profile['rows_before_target_drop']}",
                f"- Rows after target drop: {profile['rows_after_target_drop']}",
                f"- Target missing before split: {profile['target_missing_before_split']}",
                f"- Split strategy: `{profile['split_strategy']}`",
                f"- Split group column: `{profile['split_group_col']}`",
                f"- Split order column: `{profile['split_order_col']}`",
                "- Model-visible feature drop columns: "
                f"`{json.dumps(profile.get('model_visible_feature_drop_columns', []), sort_keys=True)}`",
                "",
            ]
        )
        for seed_profile in profile["seeds"]:
            lines.append(f"#### Seed {seed_profile['seed']}")
            lines.append("")
            for split_name in ("train", "cal", "test"):
                split = seed_profile["splits"][split_name]
                lines.append(
                    "- "
                    f"{split_name}: rows={split['rows']}, "
                    f"target_mean={split['target_mean']}, "
                    f"target_p50={split['target_p50']}, "
                    f"groups={json.dumps(split['group_counts'], sort_keys=True)}"
                )
            lines.append(
                "- split_group_overlaps: "
                f"`{json.dumps(seed_profile['split_group_overlaps'], sort_keys=True)}`"
            )
            lines.append(
                "- row_signature_overlaps: "
                f"`{json.dumps(seed_profile['row_signature_overlaps'], sort_keys=True)}`"
            )
            lines.append(
                "- model_visible_feature_signature_overlaps: "
                f"`{json.dumps(seed_profile['model_visible_feature_signature_cross_split_overlaps'], sort_keys=True)}`"
            )
            lines.append(
                "- model_visible_feature_plus_target_signature_overlaps: "
                f"`{json.dumps(seed_profile['model_visible_feature_plus_target_signature_cross_split_overlaps'], sort_keys=True)}`"
            )
            lines.append(
                "- row_id_overlaps: "
                f"`{json.dumps(seed_profile['row_id_overlaps'], sort_keys=True)}`"
            )
            sparse_cells = seed_profile.get("sparse_primary_group_cells") or []
            if sparse_cells:
                threshold = seed_profile.get(
                    "sparse_primary_group_threshold",
                    SPARSE_PRIMARY_GROUP_THRESHOLD,
                )
                lines.append(
                    "- sparse_primary_group_cells: "
                    f"`{json.dumps(sparse_cells, sort_keys=True)}`"
                )
                lines.append(
                    "- sparse_primary_group_caveat: "
                    f"primary-group cells below {threshold} rows are sparse "
                    "diagnostics only; do not treat their group coverage or gap "
                    "estimates as stable."
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else Path("experiments/regression/reports") / config_path.stem
    )
    payload = build_payload(config_path, config)
    atomic_write_json(out_dir / "split_profile.json", payload)
    atomic_write_text(out_dir / "split_profile.md", render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out_dir": str(out_dir),
                "datasets": payload["dataset_ids"],
                "seeds": len(config.get("random_seeds", [])),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
