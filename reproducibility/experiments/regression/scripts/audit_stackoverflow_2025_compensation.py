"""Audit Stack Overflow Developer Survey 2025 compensation regression source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
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


DATASET_ID = "stackoverflow_2025_compensation"
TARGET = "ConvertedCompYearly"
RAW_FILES = ["results.csv", "schema.csv"]
RAW_TARGET_COLUMNS = ["CompTotal", "Currency"]
TARGET_COMPONENT_DROP_COLUMNS = ["CompTotal", "Currency"]
UNAVAILABLE_PROTECTED_COLUMNS = ["Gender", "RaceEthnicity", "Disability"]
GROUP_COLUMNS = [
    "Age",
    "Country",
    "EdLevel",
    "Employment",
    "RemoteWork",
    "DevType",
    "OrgSize",
    "Industry",
    "WorkExp_numeric",
    "YearsCode_numeric",
]
FEATURE_COLUMNS = [
    "Age",
    "EdLevel",
    "Employment",
    "WorkExp_numeric",
    "YearsCode_numeric",
    "DevType",
    "OrgSize",
    "RemoteWork",
    "Industry",
    "Country",
    "MainBranch",
    "AISelect",
    "SOVisitFreq",
]
SCHEMA_QNAMES = [
    "Age",
    "EdLevel",
    "Employment",
    "WorkExp",
    "YearsCode",
    "DevType",
    "OrgSize",
    "RemoteWork",
    "Industry",
    "Country",
    "Currency",
    "CompTotal",
]
OFFICIAL_PAGE = "https://survey.stackoverflow.co/"
REPO_URL = "https://github.com/StackExchange/Survey"
ARCHIVE_URL = "https://github.com/StackExchange/Survey/tree/main/packages/archive/2025"
RESULTS_CSV_URL = (
    "https://media.githubusercontent.com/media/StackExchange/Survey/refs/heads/main/"
    "packages/archive/2025/results.csv"
)
SCHEMA_CSV_URL = (
    "https://media.githubusercontent.com/media/StackExchange/Survey/refs/heads/main/"
    "packages/archive/2025/schema.csv"
)
README_URL = "https://raw.githubusercontent.com/StackExchange/Survey/main/README.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/stackoverflow/2025")
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    return parser.parse_args()


def require_raw_files(raw_dir: Path) -> None:
    missing = [name for name in RAW_FILES if not (raw_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing Stack Overflow 2025 raw files under {raw_dir}: {missing}. "
            f"Download results.csv and schema.csv from {ARCHIVE_URL} into ignored "
            "local cache first."
        )


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def raw_manifest(raw_dir: Path) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "bytes": (raw_dir / name).stat().st_size,
            "line_count": line_count(raw_dir / name),
        }
        for name in RAW_FILES
    ]


def parse_numeric_response(series: pd.Series) -> pd.Series:
    replacements = {
        "Less than 1 year": 0.5,
        "More than 50 years": 51,
        "Prefer not to say": np.nan,
    }
    return pd.to_numeric(series.replace(replacements), errors="coerce")


def load_source_frames(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    header = pd.read_csv(raw_dir / "results.csv", nrows=0).columns.tolist()
    source_columns = [
        column
        for column in [
            "ResponseId",
            TARGET,
            *RAW_TARGET_COLUMNS,
            "Age",
            "EdLevel",
            "Employment",
            "WorkExp",
            "YearsCode",
            "DevType",
            "OrgSize",
            "RemoteWork",
            "Industry",
            "Country",
            "MainBranch",
            "AISelect",
            "SOVisitFreq",
        ]
        if column in header
    ]
    results = pd.read_csv(
        raw_dir / "results.csv",
        usecols=source_columns,
        low_memory=False,
    )
    schema = pd.read_csv(raw_dir / "schema.csv")
    return results, schema


def build_model_frame(results: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    source_columns_loaded = int(results.shape[1])
    working = results.copy()
    working[TARGET] = pd.to_numeric(working[TARGET], errors="coerce")
    if "WorkExp" in working:
        working["WorkExp_numeric"] = parse_numeric_response(working["WorkExp"])
    if "YearsCode" in working:
        working["YearsCode_numeric"] = parse_numeric_response(working["YearsCode"])

    target_missing = working[TARGET].isna()
    target_nonpositive = working[TARGET].notna() & (working[TARGET] <= 0)
    valid_target = working[TARGET].notna() & (working[TARGET] > 0)
    model_columns = [
        TARGET,
        *[column for column in FEATURE_COLUMNS if column in working],
    ]
    model_frame = working.loc[valid_target, model_columns].copy()
    target_filter = {
        "source_rows": int(working.shape[0]),
        "source_columns_loaded": source_columns_loaded,
        "derived_feature_columns": ["WorkExp_numeric", "YearsCode_numeric"],
        "model_rows_after_target_drop": int(model_frame.shape[0]),
        "target_missing_rate_before_drop": float(target_missing.mean()),
        "target_nonpositive_rate_before_drop": float(target_nonpositive.mean()),
        "target_nonpositive_rows_before_drop": int(target_nonpositive.sum()),
    }
    return model_frame, target_filter


def schema_questions(schema: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for _, row in schema[schema["qname"].isin(SCHEMA_QNAMES)].iterrows():
        rows.append(
            {
                "qname": str(row["qname"]),
                "qid": str(row["qid"]),
                "type": str(row["type"]),
                "question": str(row["question"])
                .replace("<br>", " ")
                .replace("<b>", "")
                .replace("</b>", ""),
            }
        )
    return rows


def build_profile(
    results: pd.DataFrame,
    schema: pd.DataFrame,
    manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    model_frame, target_filter = build_model_frame(results)
    audit = audit_regression_frame(
        model_frame, target=TARGET, dataset_id=DATASET_ID
    ).to_dict()
    proxy_candidates = [
        "Age",
        "Country",
        "EdLevel",
        "WorkExp_numeric",
        "YearsCode_numeric",
        "Employment",
        "RemoteWork",
    ]
    audit.update(
        {
            **target_filter,
            "full_source_rows": int(results.shape[0]),
            "schema_rows": int(schema.shape[0]),
            "target_component_drop_columns": TARGET_COMPONENT_DROP_COLUMNS,
            "unavailable_protected_columns": UNAVAILABLE_PROTECTED_COLUMNS,
            "sensitive_candidates": list(
                dict.fromkeys([*audit["sensitive_candidates"], *proxy_candidates])
            ),
            "raw_files": manifest,
            "target_policy": (
                "Use Stack Overflow's provided ConvertedCompYearly annual "
                "compensation target, drop missing and nonpositive targets for "
                "audit profiling, and keep CompTotal/Currency out of model "
                "features because they are target-construction inputs. Runner "
                "use requires log1p/raw sensitivity, outlier/winsor policy, "
                "country-aware reporting, and explicit self-selection limits."
            ),
            "group_policy": (
                "The 2025 public file does not expose gender, race/ethnicity, "
                "or disability fields. Audit Age, Country, education, work "
                "experience, employment, and remote-work columns as proxy or "
                "segment diagnostics only."
            ),
            "license_notes": (
                "Stack Exchange README states survey data is published under "
                "ODbL 1.0 and cell contents under DbCL 1.0; raw CSVs stay in "
                "ignored local cache."
            ),
        }
    )
    return {
        "dataset_id": DATASET_ID,
        "target": TARGET,
        "source": {
            "name": "Stack Overflow Developer Survey 2025 compensation",
            "official_page": OFFICIAL_PAGE,
            "repo": REPO_URL,
            "archive": ARCHIVE_URL,
            "results_csv": RESULTS_CSV_URL,
            "schema_csv": SCHEMA_CSV_URL,
            "readme": README_URL,
            "raw_files": manifest,
        },
        "shape": {
            "source_rows": int(results.shape[0]),
            "source_columns_loaded": int(results.shape[1]),
            "schema_rows": int(schema.shape[0]),
            "model_rows_after_target_drop": target_filter[
                "model_rows_after_target_drop"
            ],
            "model_columns": int(model_frame.shape[1]),
        },
        "audit": audit,
        "schema_questions": schema_questions(schema),
        "target_summary": target_summary(model_frame[TARGET]),
        "log1p_target_summary": target_summary(np.log1p(model_frame[TARGET])),
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
        f"- Official page: {source['official_page']}",
        f"- Archive: {source['archive']}",
        f"- Results CSV: {source['results_csv']}",
        f"- Schema CSV: {source['schema_csv']}",
        f"- README/license context: {source['readme']}",
        f"- Target: `{profile['target']}`",
        "",
        "## Shape And Target Policy",
        "",
        f"- Source rows / loaded columns: {shape['source_rows']} / {shape['source_columns_loaded']}",
        f"- Schema rows: {shape['schema_rows']}",
        f"- Model rows/columns after target drop: {shape['model_rows_after_target_drop']} / {shape['model_columns']}",
        f"- Target missing rate before drop: {audit['target_missing_rate_before_drop']:.4f}",
        f"- Target nonpositive rate before drop: {audit['target_nonpositive_rate_before_drop']:.4f}",
        f"- Target-construction drops: {', '.join(audit['target_component_drop_columns'])}",
        f"- Unavailable protected columns: {', '.join(audit['unavailable_protected_columns'])}",
        f"- Target policy: {audit['target_policy']}",
        f"- Group policy: {audit['group_policy']}",
        f"- License notes: {audit['license_notes']}",
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
        "| File | bytes | line count |",
        "|---|---:|---:|",
    ]
    for row in source["raw_files"]:
        lines.append(f"| `{row['name']}` | {row['bytes']} | {row['line_count']} |")

    lines.extend(["", "## Schema Questions Used", ""])
    if profile["schema_questions"]:
        lines.extend(["| qname | qid | type | question |", "|---|---|---|---|"])
        for row in profile["schema_questions"]:
            question = row["question"].replace("|", "\\|")
            lines.append(
                f"| `{row['qname']}` | {row['qid']} | {row['type']} | {question} |"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Log1p Target Summary", ""])
    log_summary = profile["log1p_target_summary"]
    lines.extend(
        [
            f"- mean/std: {log_summary['mean']:.4f} / {log_summary['std']:.4f}",
            f"- skew: {log_summary['skew']:.4f}",
            f"- min/max: {log_summary['min']:.4f} / {log_summary['max']:.4f}",
        ]
    )

    lines.extend(["", "## Group Target Profiles", ""])
    for group in profile["group_profiles"]:
        if group.get("status") == "missing_from_frame":
            lines.extend([f"### `{group['column']}`", "", "- missing from frame", ""])
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
            median = (
                "" if row["target_median"] is None else f"{row['target_median']:.4f}"
            )
            lines.append(
                f"| {row['level']} | {row['n']} | {row['share']:.4f} | {mean} | {median} |"
            )
        lines.append("")

    lines.extend(["## Top Numeric Correlations With Target", ""])
    if profile["top_abs_correlations"]:
        lines.extend(["| Column | Pearson r | n |", "|---|---:|---:|"])
        for row in profile["top_abs_correlations"]:
            lines.append(
                f"| `{row['column']}` | {row['pearson_corr']:.4f} | {row['n']} |"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    require_raw_files(raw_dir)
    manifest = raw_manifest(raw_dir)
    results, schema = load_source_frames(raw_dir)
    profile = json_safe(build_profile(results, schema, manifest))
    audit = profile["audit"]
    out_dir = Path(args.out_dir) / DATASET_ID
    atomic_write_json(out_dir / "audit.json", audit)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(audit))
    atomic_write_json(out_dir / "profile.json", profile)
    atomic_write_text(out_dir / "profile.md", render_profile_markdown(profile))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
