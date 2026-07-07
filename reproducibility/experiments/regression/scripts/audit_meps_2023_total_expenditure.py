"""Audit MEPS 2023 total health-care expenditure regression source."""

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


DATASET_ID = "meps_2023_total_expenditure"
TARGET = "TOTEXP23"
RAW_FILES = ["h251dta.zip", "h251.dta", "h251doc.pdf", "h251cb.pdf", "h251su.txt"]
DETAIL_PAGE = (
    "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files_detail.jsp?"
    "cboPufNumber=HC-251"
)
DATA_FILE_URL = "https://meps.ahrq.gov/mepsweb/data_files/pufs/h251/h251dta.zip"
DOC_URL = "https://meps.ahrq.gov/mepsweb/data_stats/download_data/pufs/h251/h251doc.pdf"
CODEBOOK_URL = (
    "https://meps.ahrq.gov/mepsweb/data_stats/download_data/pufs/h251/h251cb.pdf"
)
SAS_STATEMENTS_URL = (
    "https://meps.ahrq.gov/mepsweb/data_stats/download_data/pufs/h251/h251su.txt"
)
MEPS_GITHUB = "https://github.com/HHS-AHRQ/MEPS"
SOURCE_ROWS_EXPECTED = 18919

ID_COLUMNS = ["DUPERSID"]
SURVEY_DESIGN_COLUMNS = ["PERWT23F", "VARSTR", "VARPSU", "PANEL"]
GROUP_COLUMNS = [
    "SEX",
    "RACETHX",
    "AGE23X",
    "POVCAT23",
    "INSCOV23",
    "REGION23",
    "RTHLTH53",
    "MNHLTH53",
]
FEATURE_COLUMNS = [
    "AGE23X",
    "SEX",
    "RACETHX",
    "RACEV1X",
    "RACEV2X",
    "HISPANX",
    "HISPNCAT",
    "POVCAT23",
    "INSCOV23",
    "REGION23",
    "RTHLTH31",
    "RTHLTH42",
    "RTHLTH53",
    "MNHLTH31",
    "MNHLTH42",
    "MNHLTH53",
    "HIBPDX",
    "CHDDX",
    "ANGIDX",
    "MIDX",
    "OHRTDX",
    "STRKDX",
    "EMPHDX",
    "CHOLDX",
    "CANCERDX",
    "DIABDX_M18",
    "ARTHDX",
    "ASTHDX",
    "ADHDADDX",
]
TARGET_COMPONENT_DROP_COLUMNS = [
    "TOTSLF23",
    "OBVEXP23",
    "OBDEXP23",
    "OPTEXP23",
    "OPFEXP23",
    "OPDEXP23",
    "OPVEXP23",
    "OPSEXP23",
    "ERTEXP23",
    "ERFEXP23",
    "ERDEXP23",
    "IPTEXP23",
    "IPFEXP23",
    "IPDEXP23",
    "DVTEXP23",
    "HHAEXP23",
    "HHNEXP23",
    "VISEXP23",
    "OTHEXP23",
    "RXEXP23",
]
UTILIZATION_COOUTCOME_DROP_PREFIXES = ("OBTOT", "ERTOT", "IPTOT", "OPTOT", "RXTOT")
NEGATIVE_MISSING_CODES = {-1, -7, -8, -9, -10, -15}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/meps/2023")
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    return parser.parse_args()


def require_raw_files(raw_dir: Path) -> None:
    missing = [name for name in RAW_FILES if not (raw_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing MEPS HC-251 raw files under {raw_dir}: {missing}. "
            f"Download the Stata zip from {DATA_FILE_URL} and extract h251.dta."
        )


def raw_manifest(raw_dir: Path) -> list[dict[str, Any]]:
    return [
        {"name": name, "bytes": (raw_dir / name).stat().st_size}
        for name in RAW_FILES
    ]


def selected_columns(path: Path) -> list[str]:
    reader = pd.read_stata(path, iterator=True, convert_categoricals=False)
    available = set(reader.read(nrows=1).columns)
    return [
        column
        for column in [
            TARGET,
            *ID_COLUMNS,
            *SURVEY_DESIGN_COLUMNS,
            *FEATURE_COLUMNS,
        ]
        if column in available
    ]


def variable_labels(path: Path, columns: list[str]) -> dict[str, str]:
    reader = pd.read_stata(path, iterator=True, convert_categoricals=False)
    labels = reader.variable_labels()
    return {column: labels.get(column, "") for column in columns}


def load_source_frame(raw_dir: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    path = raw_dir / "h251.dta"
    columns = selected_columns(path)
    frame = pd.read_stata(path, convert_categoricals=False, columns=columns)
    return frame, variable_labels(path, columns)


def normalize_meps_missingness(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in normalized.columns:
        if column == TARGET:
            continue
        numeric = pd.to_numeric(normalized[column], errors="coerce")
        if numeric.notna().sum() == len(normalized[column]):
            normalized[column] = normalized[column].where(
                ~numeric.isin(NEGATIVE_MISSING_CODES),
                np.nan,
            )
    return normalized


def build_model_frame(source: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    working = source.copy()
    working[TARGET] = pd.to_numeric(working[TARGET], errors="coerce")
    invalid_target = working[TARGET].isna() | (working[TARGET] < 0)
    model_columns = [
        TARGET,
        *[column for column in SURVEY_DESIGN_COLUMNS if column in working.columns],
        *[column for column in FEATURE_COLUMNS if column in working.columns],
    ]
    model_frame = working.loc[~invalid_target, model_columns].copy()
    model_frame = normalize_meps_missingness(model_frame)
    target = model_frame[TARGET]
    target_filter = {
        "source_rows": int(working.shape[0]),
        "source_columns_loaded": int(working.shape[1]),
        "source_rows_expected": SOURCE_ROWS_EXPECTED,
        "source_count_matches_expected": bool(
            int(working.shape[0]) == SOURCE_ROWS_EXPECTED
        ),
        "model_rows_after_target_filter": int(model_frame.shape[0]),
        "target_negative_or_missing_rows_before_drop": int(invalid_target.sum()),
        "target_zero_rows_after_filter": int((target == 0).sum()),
        "target_zero_rate_after_filter": float((target == 0).mean()),
    }
    return model_frame, target_filter


def target_component_manifest(source: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    target = pd.to_numeric(source[TARGET], errors="coerce")
    for column in TARGET_COMPONENT_DROP_COLUMNS:
        if column not in source.columns:
            rows.append({"column": column, "status": "not_loaded_by_audit"})
            continue
        values = pd.to_numeric(source[column], errors="coerce")
        valid = target.notna() & values.notna()
        rows.append(
            {
                "column": column,
                "valid_pair_rows": int(valid.sum()),
                "pearson_corr_with_target": (
                    float(target[valid].corr(values[valid]))
                    if int(valid.sum()) > 1 and values[valid].nunique() > 1
                    else None
                ),
            }
        )
    return rows


def build_profile(
    source: pd.DataFrame,
    labels: dict[str, str],
    manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    model_frame, target_filter = build_model_frame(source)
    audit = audit_regression_frame(
        model_frame,
        target=TARGET,
        dataset_id=DATASET_ID,
    ).to_dict()
    proxy_candidates = [
        "SEX",
        "RACETHX",
        "RACEV1X",
        "RACEV2X",
        "HISPANX",
        "POVCAT23",
        "INSCOV23",
        "AGE23X",
        "REGION23",
    ]
    audit.update(
        {
            **target_filter,
            "target_component_drop_columns": TARGET_COMPONENT_DROP_COLUMNS,
            "utilization_cooutcome_drop_prefixes": list(
                UTILIZATION_COOUTCOME_DROP_PREFIXES
            ),
            "survey_design_columns": SURVEY_DESIGN_COLUMNS,
            "negative_missing_codes": sorted(NEGATIVE_MISSING_CODES),
            "sensitive_candidates": list(
                dict.fromkeys([*audit["sensitive_candidates"], *proxy_candidates])
            ),
            "raw_files": manifest,
            "target_policy": (
                "Use MEPS HC-251 person-level total health-care expenditure "
                "TOTEXP23 for 2023. Keep zero expenditures because they are "
                "substantive annual outcomes; drop only missing or negative target "
                "codes if present. Runner use requires raw/log1p and zero-mass "
                "sensitivity."
            ),
            "group_policy": (
                "Profile sex, race/ethnicity, age, poverty category, insurance "
                "coverage, region, and perceived health/mental-health status as "
                "group or proxy diagnostics. MEPS code labels must be carried into "
                "publication tables before interpretation."
            ),
            "missingness_policy": (
                "Treat negative MEPS special codes such as -1, -7, -8, -9, -10, "
                "and -15 as missing for feature profiling. Distinguish structural "
                "not-in-universe missingness from refused/don't-know before runner "
                "use."
            ),
            "leakage_policy": (
                "Do not use expenditure component variables, self/family payment, "
                "or same-year utilization counts when predicting total annual "
                "expenditures; they are target components or co-outcomes."
            ),
            "survey_policy": (
                "Source-review only until PERWT23F, VARSTR, and VARPSU are "
                "integrated into weighted metrics or explicitly excluded from a "
                "benchmark-only protocol."
            ),
            "license_notes": (
                "AHRQ MEPS HC public-use files are official public data. Raw DTA, "
                "zip, PDF, and setup files remain in ignored local cache."
            ),
        }
    )
    return {
        "dataset_id": DATASET_ID,
        "target": TARGET,
        "source": {
            "name": "MEPS HC-251 2023 Full Year Consolidated Data File",
            "detail_page": DETAIL_PAGE,
            "data_file_url": DATA_FILE_URL,
            "documentation": DOC_URL,
            "codebook": CODEBOOK_URL,
            "sas_statements": SAS_STATEMENTS_URL,
            "meps_github": MEPS_GITHUB,
            "raw_files": manifest,
        },
        "shape": {
            "source_rows": int(source.shape[0]),
            "source_columns_loaded": int(source.shape[1]),
            "model_rows_after_target_filter": int(model_frame.shape[0]),
            "model_columns": int(model_frame.shape[1]),
        },
        "audit": audit,
        "variable_labels": {
            column: labels.get(column, "") for column in model_frame.columns
        },
        "target_summary": target_summary(model_frame[TARGET]),
        "log1p_target_summary": target_summary(np.log1p(model_frame[TARGET])),
        "group_profiles": [
            group_profile(model_frame, TARGET, column) for column in GROUP_COLUMNS
        ],
        "top_abs_correlations": top_abs_correlations(model_frame, TARGET),
        "target_component_manifest": target_component_manifest(source),
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
        f"- Detail page: {source['detail_page']}",
        f"- Data file: {source['data_file_url']}",
        f"- Documentation: {source['documentation']}",
        f"- Codebook: {source['codebook']}",
        f"- MEPS GitHub: {source['meps_github']}",
        f"- Target: `{profile['target']}`",
        "",
        "## Shape And Target Policy",
        "",
        "- Source rows / loaded columns: "
        f"{shape['source_rows']} / {shape['source_columns_loaded']}",
        f"- Source rows expected: {audit['source_rows_expected']}",
        f"- Source count matches expected: {audit['source_count_matches_expected']}",
        "- Model rows/columns after target filter: "
        f"{shape['model_rows_after_target_filter']} / {shape['model_columns']}",
        "- Target negative/missing rows before drop: "
        f"{audit['target_negative_or_missing_rows_before_drop']}",
        "- Target zero rows/rate after filter: "
        f"{audit['target_zero_rows_after_filter']} / "
        f"{audit['target_zero_rate_after_filter']:.4f}",
        f"- Target policy: {audit['target_policy']}",
        f"- Group policy: {audit['group_policy']}",
        f"- Missingness policy: {audit['missingness_policy']}",
        f"- Leakage policy: {audit['leakage_policy']}",
        f"- Survey policy: {audit['survey_policy']}",
        f"- License notes: {audit['license_notes']}",
        "",
        "## Audit Summary",
        "",
        f"- Target mean/std: {audit['target_mean']:.4f} / {audit['target_std']:.4f}",
        f"- Target skew: {audit['target_skew']:.4f}",
        f"- Target range: {audit['target_min']:.4f} to {audit['target_max']:.4f}",
        f"- Duplicate row rate: {audit['duplicate_row_rate']:.4f}",
        "- Sensitive/proxy candidates: "
        f"{', '.join(audit['sensitive_candidates']) or 'none_detected'}",
        f"- Recommended actions: {', '.join(audit['recommended_actions']) or 'none'}",
        "",
        "## Log1p Target Summary",
        "",
    ]
    log_summary = profile["log1p_target_summary"]
    lines.extend(
        [
            f"- mean/std: {log_summary['mean']:.4f} / {log_summary['std']:.4f}",
            f"- skew: {log_summary['skew']:.4f}",
            f"- min/max: {log_summary['min']:.4f} / {log_summary['max']:.4f}",
        ]
    )

    lines.extend(["", "## Raw File Manifest", "", "| File | bytes |", "|---|---:|"])
    for row in source["raw_files"]:
        lines.append(f"| `{row['name']}` | {row['bytes']} |")

    lines.extend(["", "## Selected Variable Labels", ""])
    lines.extend(["| Variable | Label |", "|---|---|"])
    for column, label in profile["variable_labels"].items():
        lines.append(f"| `{column}` | {label.replace('|', '/')} |")

    lines.extend(["", "## Target Component Drops", ""])
    lines.append(f"- Drop columns: {', '.join(audit['target_component_drop_columns'])}")
    lines.append(
        "- Utilization co-outcome prefixes: "
        f"{', '.join(audit['utilization_cooutcome_drop_prefixes'])}"
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
                f"| {row['level']} | {row['n']} | {row['share']:.4f} | "
                f"{mean} | {median} |"
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
    source, labels = load_source_frame(raw_dir)
    profile = json_safe(build_profile(source, labels, manifest))
    audit = profile["audit"]
    out_dir = Path(args.out_dir) / DATASET_ID
    atomic_write_json(out_dir / "audit.json", audit)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(audit))
    atomic_write_json(out_dir / "profile.json", profile)
    atomic_write_text(out_dir / "profile.md", render_profile_markdown(profile))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
