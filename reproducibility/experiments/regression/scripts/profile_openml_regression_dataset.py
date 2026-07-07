"""Profile one OpenML regression dataset for manual source review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from cpfi.regression.datasets import (
    MISSING_TOKENS,
    audit_regression_frame,
    infer_sensitive_candidates,
    load_openml_regression_frame,
)
from cpfi.regression.experiment import atomic_write_json, atomic_write_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openml-id", type=int, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument(
        "--group-columns",
        default="",
        help="Comma-separated columns to profile as group or proxy attributes.",
    )
    parser.add_argument(
        "--out-dir",
        default="experiments/regression/audits",
        help="Directory where the dataset profile will be written.",
    )
    parser.add_argument("--max-description-chars", type=int, default=900)
    return parser.parse_args()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if value is pd.NA:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def target_summary(series: pd.Series) -> dict[str, Any]:
    numeric = pd.to_numeric(series, errors="coerce")
    observed = numeric.dropna()
    quantiles = observed.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    return {
        "n": int(len(series)),
        "n_observed": int(observed.shape[0]),
        "missing_rate": float(numeric.isna().mean()),
        "mean": float(observed.mean()) if not observed.empty else None,
        "std": float(observed.std()) if observed.shape[0] > 1 else None,
        "min": float(observed.min()) if not observed.empty else None,
        "max": float(observed.max()) if not observed.empty else None,
        "skew": float(observed.skew()) if observed.shape[0] > 2 else None,
        "quantiles": {str(q): float(value) for q, value in quantiles.items()},
    }


def top_abs_correlations(
    df: pd.DataFrame,
    target: str,
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    y = pd.to_numeric(df[target], errors="coerce")
    rows = []
    for col in df.columns:
        if col == target:
            continue
        x = pd.to_numeric(df[col], errors="coerce")
        valid = x.notna() & y.notna()
        if int(valid.sum()) < 5 or x[valid].nunique() <= 1:
            continue
        corr = x[valid].corr(y[valid])
        if pd.isna(corr):
            continue
        rows.append(
            {
                "column": str(col),
                "pearson_corr": float(corr),
                "abs_corr": float(abs(corr)),
                "n": int(valid.sum()),
            }
        )
    return sorted(rows, key=lambda item: (-item["abs_corr"], item["column"]))[:limit]


def group_profile(
    df: pd.DataFrame,
    target: str,
    group_col: str,
    *,
    max_levels: int = 20,
) -> dict[str, Any]:
    if group_col not in df.columns:
        return {"column": group_col, "status": "missing_from_frame"}

    y = pd.to_numeric(df[target], errors="coerce")
    raw_group = df[group_col].replace(list(MISSING_TOKENS), np.nan)
    numeric_group = pd.to_numeric(raw_group, errors="coerce")
    is_numeric = numeric_group.notna().sum() > 0 and raw_group.nunique(dropna=True) > max_levels

    if is_numeric:
        binned = pd.qcut(numeric_group, q=4, duplicates="drop")
        labels = binned.astype("object").where(numeric_group.notna(), "missing").astype(str)
        mode = "numeric_quantile_bins"
    else:
        labels = raw_group.astype("object").where(raw_group.notna(), "missing").astype(str)
        mode = "categorical_levels"

    value_counts = labels.value_counts(dropna=False)
    level_rows = []
    for level in value_counts.head(max_levels).index:
        mask = labels == level
        target_values = y[mask].dropna()
        level_rows.append(
            {
                "level": str(level),
                "n": int(mask.sum()),
                "share": float(mask.mean()),
                "target_mean": float(target_values.mean()) if not target_values.empty else None,
                "target_median": float(target_values.median()) if not target_values.empty else None,
                "target_std": float(target_values.std()) if target_values.shape[0] > 1 else None,
            }
        )

    return {
        "column": group_col,
        "mode": mode,
        "missing_rate": float(raw_group.isna().mean()),
        "unique_values": int(raw_group.nunique(dropna=True)),
        "levels_profiled": len(level_rows),
        "levels": level_rows,
    }


def openml_metadata(openml_id: int, description_chars: int) -> dict[str, Any]:
    import openml

    dataset = openml.datasets.get_dataset(
        openml_id,
        download_data=False,
        download_qualities=True,
        download_features_meta_data=True,
    )
    features = []
    for _, feature in sorted(dataset.features.items()):
        nominal_values = getattr(feature, "nominal_values", None)
        features.append(
            {
                "name": getattr(feature, "name", None),
                "data_type": getattr(feature, "data_type", None),
                "nominal_values": list(nominal_values) if nominal_values else None,
            }
        )

    qualities = getattr(dataset, "qualities", {}) or {}
    return {
        "openml_id": openml_id,
        "name": dataset.name,
        "version": dataset.version,
        "format": getattr(dataset, "format", None),
        "default_target_attribute": dataset.default_target_attribute,
        "openml_page": f"https://www.openml.org/d/{openml_id}",
        "url": dataset.url,
        "licence": dataset.licence,
        "description_excerpt": (dataset.description or "")[:description_chars],
        "qualities": {
            key: qualities.get(key)
            for key in [
                "NumberOfInstances",
                "NumberOfFeatures",
                "NumberOfMissingValues",
                "NumberOfNumericFeatures",
                "NumberOfSymbolicFeatures",
            ]
        },
        "features": features,
    }


def build_profile(
    df: pd.DataFrame,
    *,
    dataset_id: str,
    target: str,
    group_columns: list[str],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    normalized = df.replace(list(MISSING_TOKENS), np.nan)
    audit = audit_regression_frame(normalized, target=target, dataset_id=dataset_id)
    inferred_groups = infer_sensitive_candidates(normalized.drop(columns=[target]))
    groups = list(dict.fromkeys([*group_columns, *inferred_groups]))
    return {
        "dataset_id": dataset_id,
        "target": target,
        "source": metadata,
        "shape": {"rows": int(normalized.shape[0]), "columns": int(normalized.shape[1])},
        "audit": audit.to_dict(),
        "target_summary": target_summary(normalized[target]),
        "group_profiles": [
            group_profile(normalized, target, group_col) for group_col in groups
        ],
        "top_abs_correlations": top_abs_correlations(normalized, target),
    }


def render_markdown(profile: dict[str, Any]) -> str:
    source = profile["source"]
    audit = profile["audit"]
    lines = [
        f"# Dataset Profile: {profile['dataset_id']}",
        "",
        "## Source",
        "",
        f"- OpenML id: {source['openml_id']}",
        f"- OpenML name: `{source['name']}`",
        f"- OpenML page: {source.get('openml_page', '')}",
        f"- Download URL: {source['url']}",
        f"- Licence: {source['licence'] or 'not_reported'}",
        f"- Target: `{profile['target']}`",
        f"- Rows/columns: {profile['shape']['rows']} / {profile['shape']['columns']}",
        "",
        "## Audit Summary",
        "",
        f"- Target missing rate: {audit['target_missing_rate']:.4f}",
        f"- Target mean/std: {audit['target_mean']:.4f} / {audit['target_std']:.4f}",
        f"- Target skew: {audit['target_skew']:.4f}",
        f"- Duplicate row rate: {audit['duplicate_row_rate']:.4f}",
        f"- Sensitive/proxy candidates: {', '.join(audit['sensitive_candidates']) or 'none_detected'}",
        f"- Recommended actions: {', '.join(audit['recommended_actions']) or 'none'}",
        "",
        "## Group Target Profiles",
        "",
    ]
    for group in profile["group_profiles"]:
        if group.get("status") == "missing_from_frame":
            lines.extend([f"### `{group['column']}`", "", "- Missing from frame.", ""])
            continue
        lines.extend(
            [
                f"### `{group['column']}`",
                "",
                f"- Mode: {group['mode']}",
                f"- Missing rate: {group['missing_rate']:.4f}",
                f"- Unique values: {group['unique_values']}",
                "",
                "| Level | n | share | target mean | target median |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in group["levels"]:
            mean = "" if row["target_mean"] is None else f"{row['target_mean']:.4f}"
            median = "" if row["target_median"] is None else f"{row['target_median']:.4f}"
            lines.append(
                f"| {row['level']} | {row['n']} | {row['share']:.4f} | {mean} | {median} |"
            )
        lines.append("")

    lines.extend(["## Top Numeric Correlations With Target", ""])
    if profile["top_abs_correlations"]:
        lines.extend(["| Column | Pearson r | n |", "|---|---:|---:|"])
        for row in profile["top_abs_correlations"]:
            lines.append(f"| `{row['column']}` | {row['pearson_corr']:.4f} | {row['n']} |")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    group_columns = [col.strip() for col in args.group_columns.split(",") if col.strip()]
    out_dir = Path(args.out_dir) / args.dataset_id
    metadata = openml_metadata(args.openml_id, args.max_description_chars)
    df = load_openml_regression_frame(args.openml_id, args.target)
    profile = build_profile(
        df,
        dataset_id=args.dataset_id,
        target=args.target,
        group_columns=group_columns,
        metadata=metadata,
    )
    atomic_write_json(out_dir / "profile.json", json_safe(profile))
    atomic_write_text(out_dir / "profile.md", render_markdown(json_safe(profile)))
    print(json.dumps({"status": "ok", "profile_path": str(out_dir / "profile.json")}))


if __name__ == "__main__":
    main()
