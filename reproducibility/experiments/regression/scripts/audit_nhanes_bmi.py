"""Audit NHANES 2017-2018 BMI as a survey regression source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from cpfi.regression.datasets import audit_regression_frame, render_audit_markdown
from cpfi.regression.experiment import atomic_write_json, atomic_write_text

try:
    from profile_openml_regression_dataset import (
        group_profile,
        json_safe,
        target_summary,
        top_abs_correlations,
    )
except ModuleNotFoundError:
    from experiments.regression.scripts.profile_openml_regression_dataset import (
        group_profile,
        json_safe,
        target_summary,
        top_abs_correlations,
    )


DATASET_ID = "nhanes_2017_2018_bmi"
TARGET = "BMXBMI"
RAW_FILES = ["DEMO_J.XPT", "BMX_J.XPT"]
GROUP_COLUMNS = ["RIAGENDR", "RIDRETH3", "RIDAGEYR", "INDFMPIR"]
SURVEY_DESIGN_COLUMNS = ["WTMEC2YR", "SDMVSTRA", "SDMVPSU"]
TARGET_COMPONENT_DROP_COLUMNS = ["BMXWT", "BMXHT"]
MODEL_COLUMNS = [
    TARGET,
    "RIDAGEYR",
    "RIAGENDR",
    "RIDRETH3",
    "INDFMPIR",
    "DMDEDUC2",
    "DMDMARTL",
    "BMXWAIST",
    "BMXHIP",
    *SURVEY_DESIGN_COLUMNS,
]
DEMO_DOC = "https://wwwn.cdc.gov/nchs/data/nhanes/public/2017/datafiles/DEMO_J.htm"
BMX_DOC = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BMX_J.htm"
DEMO_XPT = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.XPT"
BMX_XPT = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BMX_J.XPT"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/nhanes/2017-2018")
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    return parser.parse_args()


def require_raw_files(raw_dir: Path) -> None:
    missing = [name for name in RAW_FILES if not (raw_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing NHANES raw files under {raw_dir}: {missing}")


def raw_manifest(raw_dir: Path) -> list[dict[str, Any]]:
    return [
        {"name": name, "bytes": (raw_dir / name).stat().st_size}
        for name in RAW_FILES
    ]


def load_joined_frame(raw_dir: Path) -> pd.DataFrame:
    demo = pd.read_sas(raw_dir / "DEMO_J.XPT")
    bmx = pd.read_sas(raw_dir / "BMX_J.XPT")
    joined = demo.merge(bmx, on="SEQN", how="inner")
    joined[TARGET] = pd.to_numeric(joined[TARGET], errors="coerce")
    return joined


def build_profile(joined: pd.DataFrame, manifest: list[dict[str, Any]]) -> dict[str, Any]:
    target_missing_before_drop = float(joined[TARGET].isna().mean())
    model_frame = joined.loc[joined[TARGET].notna(), MODEL_COLUMNS].copy()
    audit = audit_regression_frame(model_frame, target=TARGET, dataset_id=DATASET_ID).to_dict()
    proxy_candidates = ["RIAGENDR", "RIDRETH3", "RIDAGEYR", "INDFMPIR"]
    audit.update(
        {
            "source_rows": int(joined.shape[0]),
            "model_rows_after_target_drop": int(model_frame.shape[0]),
            "target_missing_rate_before_drop": target_missing_before_drop,
            "target_component_drop_columns": TARGET_COMPONENT_DROP_COLUMNS,
            "survey_design_columns": SURVEY_DESIGN_COLUMNS,
            "sensitive_candidates": list(
                dict.fromkeys([*audit["sensitive_candidates"], *proxy_candidates])
            ),
            "raw_files": manifest,
            "target_policy": (
                "BMI from NHANES body measures, observed after examination. Drop "
                "missing BMI for audit profiling; never use BMXWT/BMXHT as model "
                "features because BMI is calculated from weight and height; require "
                "MEC survey-weight/strata/PSU policy before runner use."
            ),
        }
    )
    return {
        "dataset_id": DATASET_ID,
        "target": TARGET,
        "source": {
            "name": "NHANES 2017-2018 Body Measures BMI",
            "demo_doc": DEMO_DOC,
            "bmx_doc": BMX_DOC,
            "demo_xpt": DEMO_XPT,
            "bmx_xpt": BMX_XPT,
            "raw_files": manifest,
        },
        "shape": {
            "joined_rows": int(joined.shape[0]),
            "joined_columns": int(joined.shape[1]),
            "model_rows_after_target_drop": int(model_frame.shape[0]),
            "model_columns": int(model_frame.shape[1]),
        },
        "audit": audit,
        "target_summary": target_summary(model_frame[TARGET]),
        "group_profiles": [
            group_profile(model_frame, TARGET, column) for column in GROUP_COLUMNS
        ],
        "top_abs_correlations": top_abs_correlations(model_frame, TARGET),
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    audit = profile["audit"]
    source = profile["source"]
    shape = profile["shape"]
    lines = [
        f"# Dataset Profile: {profile['dataset_id']}",
        "",
        "## Source",
        "",
        f"- Name: {source['name']}",
        f"- DEMO doc: {source['demo_doc']}",
        f"- BMX doc: {source['bmx_doc']}",
        f"- Target: `{profile['target']}`",
        "",
        "## Shape And Target Policy",
        "",
        f"- Joined rows/columns: {shape['joined_rows']} / {shape['joined_columns']}",
        f"- Model rows/columns after target drop: {shape['model_rows_after_target_drop']} / {shape['model_columns']}",
        f"- Target missing rate before drop: {audit['target_missing_rate_before_drop']:.4f}",
        f"- Target component drops: {', '.join(audit['target_component_drop_columns'])}",
        f"- Survey design columns: {', '.join(audit['survey_design_columns'])}",
        f"- Policy: {audit['target_policy']}",
        "",
        "## Audit Summary",
        "",
        f"- Target mean/std: {audit['target_mean']:.4f} / {audit['target_std']:.4f}",
        f"- Target skew: {audit['target_skew']:.4f}",
        f"- Target range: {audit['target_min']:.4f} to {audit['target_max']:.4f}",
        f"- Duplicate row rate: {audit['duplicate_row_rate']:.4f}",
        f"- Sensitive/proxy candidates: {', '.join(audit['sensitive_candidates']) or 'none_detected'}",
        f"- Recommended actions: {', '.join(audit['recommended_actions']) or 'none'}",
        "",
        "## Raw File Manifest",
        "",
        "| File | bytes |",
        "|---|---:|",
    ]
    for row in source["raw_files"]:
        lines.append(f"| `{row['name']}` | {row['bytes']} |")

    lines.extend(["", "## Group Target Profiles", ""])
    for group in profile["group_profiles"]:
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
    raw_dir = Path(args.raw_dir)
    require_raw_files(raw_dir)
    manifest = raw_manifest(raw_dir)
    joined = load_joined_frame(raw_dir)
    profile = json_safe(build_profile(joined, manifest))
    audit = profile["audit"]
    out_dir = Path(args.out_dir) / DATASET_ID
    atomic_write_json(out_dir / "audit.json", audit)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(audit))
    atomic_write_json(out_dir / "profile.json", profile)
    atomic_write_text(out_dir / "profile.md", render_profile_markdown(profile))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
