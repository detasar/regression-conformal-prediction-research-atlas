"""Audit OULAD assessment score as an education regression source."""

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


DATASET_ID = "oulad_assessment_score"
TARGET = "score"
RAW_TABLES = [
    "assessments.csv",
    "courses.csv",
    "studentAssessment.csv",
    "studentInfo.csv",
    "studentRegistration.csv",
    "studentVle.csv",
    "vle.csv",
    "OULAD.names",
]
GROUP_COLUMNS = [
    "gender",
    "age_band",
    "disability",
    "imd_band",
    "highest_education",
    "region",
]
LEAKAGE_DROP_COLUMNS = ["final_result"]
IDENTIFIER_COLUMNS = ["id_student", "id_assessment"]
GROUP_SPLIT_COLUMNS = ["id_student", "code_module", "code_presentation"]
POST_ASSESSMENT_RISK_COLUMNS = ["date_submitted", "is_banked"]
MODEL_COLUMNS = [
    "code_module",
    "code_presentation",
    "assessment_type",
    "date",
    "weight",
    "date_submitted",
    "is_banked",
    "gender",
    "region",
    "highest_education",
    "imd_band",
    "age_band",
    "num_of_prev_attempts",
    "studied_credits",
    "disability",
    TARGET,
]
UCI_URL = "https://archive.ics.uci.edu/dataset/349/open+university+learning+analytics+dataset"
UCI_ZIP_URL = "https://archive.ics.uci.edu/static/public/349/open+university+learning+analytics+dataset.zip"
NATURE_URL = "https://www.nature.com/articles/sdata2017171"
FIGSHARE_URL = "https://figshare.com/articles/dataset/OULAD_Open_University_Learning_Analytics_Dataset/5081998"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/oulad")
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    return parser.parse_args()


def require_raw_files(raw_dir: Path) -> None:
    missing = [name for name in RAW_TABLES if not (raw_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing OULAD raw files under {raw_dir}: {missing}. "
            f"Download from {UCI_ZIP_URL} into an ignored local cache first."
        )


def table_manifest(raw_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for name in RAW_TABLES:
        path = raw_dir / name
        line_count = None
        if path.suffix == ".csv":
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                line_count = sum(1 for _ in handle)
        rows.append(
            {
                "name": name,
                "bytes": path.stat().st_size if path.exists() else None,
                "line_count": line_count,
            }
        )
    return rows


def load_joined_tables(raw_dir: Path) -> pd.DataFrame:
    student_assessment = pd.read_csv(raw_dir / "studentAssessment.csv", na_values=["?"])
    assessments = pd.read_csv(raw_dir / "assessments.csv", na_values=["?"])
    student_info = pd.read_csv(raw_dir / "studentInfo.csv", na_values=["?"])
    joined = student_assessment.merge(assessments, on="id_assessment", how="left")
    joined = joined.merge(
        student_info,
        on=["code_module", "code_presentation", "id_student"],
        how="left",
    )
    joined[TARGET] = pd.to_numeric(joined[TARGET], errors="coerce")
    return joined


def build_model_frame(joined: pd.DataFrame, include_split_columns: bool = False) -> pd.DataFrame:
    """Build the audited OULAD assessment-score frame used by audits and runner."""

    valid_target = joined[TARGET].notna()
    missing_columns = [column for column in MODEL_COLUMNS if column not in joined.columns]
    if missing_columns:
        raise ValueError(f"OULAD joined frame missing model columns: {missing_columns}")
    model_frame = joined.loc[valid_target, MODEL_COLUMNS].copy()
    if include_split_columns:
        for column in GROUP_SPLIT_COLUMNS:
            if column not in model_frame.columns and column in joined.columns:
                model_frame[column] = joined.loc[valid_target, column].to_numpy()
    return model_frame


def build_assessment_profile(joined: pd.DataFrame, manifest: list[dict[str, Any]]) -> dict[str, Any]:
    target_missing_before_drop = float(joined[TARGET].isna().mean())
    model_frame = build_model_frame(joined)
    audit = audit_regression_frame(model_frame, target=TARGET, dataset_id=DATASET_ID).to_dict()
    audit.update(
        {
            "source_rows": int(joined.shape[0]),
            "model_rows_after_target_drop": int(model_frame.shape[0]),
            "target_missing_rate_before_drop": target_missing_before_drop,
            "leakage_drop_columns": LEAKAGE_DROP_COLUMNS,
            "identifier_columns": IDENTIFIER_COLUMNS,
            "group_split_columns": GROUP_SPLIT_COLUMNS,
            "post_assessment_risk_columns": POST_ASSESSMENT_RISK_COLUMNS,
            "raw_tables": manifest,
            "target_policy": (
                "Bounded 0-100 assessment score. Drop missing/non-numeric score rows "
                "for audit profiling; keep final_result out as a target descendant; "
                "require student/module grouped split and temporal assessment policy "
                "before runner use."
            ),
        }
    )
    return {
        "dataset_id": DATASET_ID,
        "target": TARGET,
        "source": {
            "name": "Open University Learning Analytics Dataset",
            "uci_page": UCI_URL,
            "uci_zip": UCI_ZIP_URL,
            "nature_paper": NATURE_URL,
            "figshare_page": FIGSHARE_URL,
            "local_raw_tables": manifest,
        },
        "shape": {
            "joined_rows": int(joined.shape[0]),
            "joined_columns": int(joined.shape[1]),
            "model_rows_after_target_drop": int(model_frame.shape[0]),
            "model_columns": int(model_frame.shape[1]),
            "unique_students": int(joined["id_student"].nunique()),
            "unique_module_presentations": int(
                joined[["code_module", "code_presentation"]].drop_duplicates().shape[0]
            ),
            "unique_assessments": int(joined["id_assessment"].nunique()),
        },
        "audit": audit,
        "target_summary": target_summary(model_frame[TARGET]),
        "group_profiles": [
            group_profile(model_frame, TARGET, column) for column in GROUP_COLUMNS
        ],
        "top_abs_correlations": top_abs_correlations(model_frame, TARGET),
        "student_repetition_summary": {
            key: float(value)
            for key, value in joined.groupby("id_student").size().describe().to_dict().items()
        },
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    audit = profile["audit"]
    shape = profile["shape"]
    source = profile["source"]
    lines = [
        f"# Dataset Profile: {profile['dataset_id']}",
        "",
        "## Source",
        "",
        f"- Name: {source['name']}",
        f"- UCI page: {source['uci_page']}",
        f"- UCI zip: {source['uci_zip']}",
        f"- Nature paper: {source['nature_paper']}",
        f"- Figshare page: {source['figshare_page']}",
        f"- Target: `{profile['target']}`",
        "",
        "## Shape And Target Policy",
        "",
        f"- Joined rows/columns: {shape['joined_rows']} / {shape['joined_columns']}",
        f"- Model rows/columns after target drop: {shape['model_rows_after_target_drop']} / {shape['model_columns']}",
        f"- Unique students: {shape['unique_students']}",
        f"- Unique module-presentations: {shape['unique_module_presentations']}",
        f"- Unique assessments: {shape['unique_assessments']}",
        f"- Target missing rate before drop: {audit['target_missing_rate_before_drop']:.4f}",
        f"- Leakage drop columns: {', '.join(audit['leakage_drop_columns'])}",
        f"- Post-assessment risk columns: {', '.join(audit['post_assessment_risk_columns'])}",
        f"- Group split columns: {', '.join(audit['group_split_columns'])}",
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
        "## Raw Table Manifest",
        "",
        "| Table | bytes | line count |",
        "|---|---:|---:|",
    ]
    for row in source["local_raw_tables"]:
        lines.append(f"| `{row['name']}` | {row['bytes']} | {row['line_count'] or ''} |")

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
    manifest = table_manifest(raw_dir)
    joined = load_joined_tables(raw_dir)
    profile = json_safe(build_assessment_profile(joined, manifest))
    audit = profile["audit"]
    out_dir = Path(args.out_dir) / DATASET_ID
    atomic_write_json(out_dir / "audit.json", audit)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(audit))
    atomic_write_json(out_dir / "profile.json", profile)
    atomic_write_text(out_dir / "profile.md", render_profile_markdown(profile))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
