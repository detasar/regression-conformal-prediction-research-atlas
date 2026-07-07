"""Audit Federal Reserve SCF 2022 net-worth regression source."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
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


DATASET_ID = "scf_2022_networth"
TARGET = "NETWORTH"
RAW_ZIP = "scfp2022excel.zip"
CSV_MEMBER = "SCFP2022.csv"
MACRO_FILE = "bulletin.macro.txt"
CODEBOOK_FILE = "codebk2022.txt"
RAW_FILES = [RAW_ZIP, MACRO_FILE, CODEBOOK_FILE]

SCF_PAGE = "https://www.federalreserve.gov/econres/scfindex.htm"
DATA_URL = "https://www.federalreserve.gov/econres/files/scfp2022excel.zip"
MACRO_URL = "https://www.federalreserve.gov/econres/files/bulletin.macro.txt"
CODEBOOK_URL = "https://www.federalreserve.gov/econres/files/codebk2022.txt"
REPLICATE_WEIGHT_URL = "https://www.federalreserve.gov/econres/files/scf2022rw1s.zip"
STANDARD_ERROR_DOC = "https://www.federalreserve.gov/econres/files/Standard_Error_Documentation.pdf"
SOURCE_LAST_UPDATED = "2024-04-03"

ID_COLUMNS = ["YY1", "Y1"]
SURVEY_DESIGN_COLUMNS = ["WGT"]
GROUP_COLUMNS = [
    "RACECL",
    "RACECL4",
    "RACECL5",
    "RACE",
    "HHSEX",
    "AGECL",
    "AGE",
    "EDCL",
    "EDUC",
    "MARRIED",
    "FAMSTRUCT",
    "KIDS",
    "LF",
    "LIFECL",
    "OCCAT1",
    "OCCAT2",
    "INDCAT",
]
INCOME_COLUMNS = [
    "INCOME",
    "NORMINC",
    "WAGEINC",
    "BUSSEFARMINC",
    "INTDIVINC",
    "KGINC",
    "SSRETINC",
    "TRANSFOTHINC",
    "PENACCTWD",
]
FINANCIAL_BEHAVIOR_COLUMNS = [
    "WSAVED",
    "SAVED",
    "SAVRES1",
    "SAVRES2",
    "SAVRES3",
    "SAVRES4",
    "SAVRES5",
    "SAVRES6",
    "SAVRES7",
    "SAVRES8",
    "SAVRES9",
    "SPENDMOR",
    "SPENDLESS",
    "EXPENSHILO",
    "LATE",
    "LATE60",
    "BNKRUPLAST5",
    "FINLIT",
    "YESFINRISK",
    "NOFINRISK",
    "CRDAPP",
    "TURNDOWN",
    "FEARDENIAL",
    "TURNFEAR",
]
FEATURE_COLUMNS = [
    *SURVEY_DESIGN_COLUMNS,
    *GROUP_COLUMNS,
    *INCOME_COLUMNS,
    *FINANCIAL_BEHAVIOR_COLUMNS,
]
TARGET_COMPONENT_COLUMNS = ["ASSET", "FIN", "NFIN", "DEBT", "NETWORTH"]
TARGET_DESCENDANT_PATTERNS = [
    r"^FIN$",
    r"^NFIN$",
    r"ASSET",
    r"DEBT",
    r"NETWORTH",
    r"NW",
    r"NWPCTLE",
    r"ASSETCAT",
    r"LEVRATIO",
    r"DEBT2INC",
    r"PAY",
    r"MORT",
    r"LOAN",
    r"BNPL",
    r"CCBAL",
    r"INSTALL",
    r"ODEBT",
    r"EQUITY",
    r"RETEQ",
    r"KGTOTAL",
    r"KG[A-Z_]*",
    r"LIQ",
    r"CDS",
    r"SAVING",
    r"STOCK",
    r"BOND",
    r"RETQLIQ",
    r"PEN",
    r"VEHIC",
    r"HOUSE",
    r"BUS",
]

AGECL_LABELS = {
    "1": "<35",
    "2": "35-44",
    "3": "45-54",
    "4": "55-64",
    "5": "65-74",
    "6": "75+",
}
EDCL_LABELS = {
    "1": "no_high_school_diploma",
    "2": "high_school_diploma",
    "3": "some_college",
    "4": "college_degree",
}
MARRIED_LABELS = {"1": "married_or_living_with_partner", "2": "not_married"}
HHSEX_LABELS = {"1": "male", "2": "female"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/scf/2022")
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    return parser.parse_args()


def require_raw_files(raw_dir: Path) -> None:
    missing = [name for name in RAW_FILES if not (raw_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing SCF 2022 raw files under {raw_dir}: {missing}. "
            f"Download {DATA_URL}, {MACRO_URL}, and {CODEBOOK_URL} into ignored "
            "local cache first."
        )


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def raw_manifest(raw_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for name in RAW_FILES:
        path = raw_dir / name
        row = {"name": name, "bytes": path.stat().st_size}
        if path.suffix.lower() == ".txt":
            row["line_count"] = line_count(path)
        rows.append(row)
    return rows


def zip_integrity(zip_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as archive:
        bad_member = archive.testzip()
        members = archive.infolist()
        csv_members = [info for info in members if info.filename == CSV_MEMBER]
        if len(csv_members) != 1:
            raise ValueError(f"Expected {CSV_MEMBER} in {zip_path}, found {csv_members}")
        return {
            "bad_member": bad_member,
            "csv_member": CSV_MEMBER,
            "csv_uncompressed_bytes": int(csv_members[0].file_size),
            "zip_members": [info.filename for info in members],
        }


def read_header(raw_dir: Path) -> list[str]:
    with zipfile.ZipFile(raw_dir / RAW_ZIP) as archive:
        with archive.open(CSV_MEMBER) as handle:
            return pd.read_csv(handle, nrows=0).columns.astype(str).tolist()


def selected_columns(header: list[str]) -> list[str]:
    columns = [
        TARGET,
        *ID_COLUMNS,
        *FEATURE_COLUMNS,
        *TARGET_COMPONENT_COLUMNS,
    ]
    return list(dict.fromkeys([column for column in columns if column in header]))


def load_source_frame(raw_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    header = read_header(raw_dir)
    columns = selected_columns(header)
    with zipfile.ZipFile(raw_dir / RAW_ZIP) as archive:
        with archive.open(CSV_MEMBER) as handle:
            frame = pd.read_csv(handle, usecols=columns, low_memory=False)
    return frame, header


def is_target_descendant_column(column: str) -> bool:
    if column == TARGET:
        return False
    return any(re.search(pattern, column) for pattern in TARGET_DESCENDANT_PATTERNS)


def normalize_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in normalized.columns:
        converted = pd.to_numeric(normalized[column], errors="coerce")
        if converted.notna().sum() > 0:
            normalized[column] = converted
    return normalized


def build_model_frame(source: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    working = normalize_numeric(source)
    target = pd.to_numeric(working[TARGET], errors="coerce")
    valid_target = target.notna()
    feature_columns = [
        column
        for column in working.columns
        if column not in {TARGET, *ID_COLUMNS} and not is_target_descendant_column(column)
    ]
    model_frame = working.loc[valid_target, [TARGET, *feature_columns]].copy()
    model_frame[TARGET] = target.loc[valid_target].astype(float)

    family_sizes = working.groupby("YY1").size() if "YY1" in working.columns else pd.Series(dtype=int)
    implicate = (
        pd.to_numeric(working["Y1"], errors="coerce")
        - 10 * pd.to_numeric(working["YY1"], errors="coerce")
        if {"Y1", "YY1"}.issubset(working.columns)
        else pd.Series(dtype=float)
    )
    target_filter = {
        "source_rows": int(working.shape[0]),
        "source_columns_loaded": int(working.shape[1]),
        "model_rows_after_target_filter": int(model_frame.shape[0]),
        "target_missing_rows_before_drop": int(target.isna().sum()),
        "target_missing_rate_before_drop": float(target.isna().mean()),
        "target_negative_rows_after_filter": int((model_frame[TARGET] < 0).sum()),
        "target_zero_rows_after_filter": int((model_frame[TARGET] == 0).sum()),
        "family_count": int(working["YY1"].nunique()) if "YY1" in working.columns else None,
        "implicate_count_profile": {
            str(int(key)): int(value)
            for key, value in family_sizes.value_counts().sort_index().items()
        },
        "implicate_values": [
            int(value) for value in sorted(implicate.dropna().unique().tolist())
        ],
        "excluded_identifier_columns": [column for column in ID_COLUMNS if column in source],
    }
    return model_frame, target_filter


def signed_log1p(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return np.sign(numeric) * np.log1p(np.abs(numeric))


def leakage_manifest(header: list[str]) -> dict[str, Any]:
    matching_columns = sorted(
        {
            column
            for column in header
            if is_target_descendant_column(column)
        }
    )
    return {
        "target": TARGET,
        "target_definition": "NETWORTH=ASSET-DEBT in the Federal Reserve bulletin macro",
        "excluded_patterns": TARGET_DESCENDANT_PATTERNS,
        "matching_column_count": len(matching_columns),
        "sample_matching_columns": matching_columns[:100],
    }


def macro_evidence(raw_dir: Path) -> list[dict[str, Any]]:
    patterns = {
        "target_definition": "NETWORTH=ASSET-DEBT",
        "main_weight": "WGT=X42001/5",
        "age_class": "AGECL=1+",
        "education_class": "EDCL=4",
        "family_structure": "FAMSTRUCT=1",
        "race_class": "RACECL4=",
    }
    lines = (raw_dir / MACRO_FILE).read_text(encoding="utf-8", errors="replace").splitlines()
    evidence = []
    for name, pattern in patterns.items():
        for index, line in enumerate(lines, start=1):
            if pattern in line.replace(" ", "") or pattern in line:
                evidence.append({"name": name, "line": index, "text": line.strip()})
                break
    return evidence


def codebook_evidence(raw_dir: Path) -> list[dict[str, Any]]:
    patterns = {
        "five_implicates": "imputed five times",
        "public_records": "22,975",
        "analysis_weights": "weights play a critical role",
        "replicate_weights": "999 sample replicates",
        "standard_error": "SQRT((6/5)*imputation variance + sampling variance)",
    }
    lines = (raw_dir / CODEBOOK_FILE).read_text(encoding="utf-8", errors="replace").splitlines()
    evidence = []
    for name, pattern in patterns.items():
        lowered = pattern.lower()
        for index, line in enumerate(lines, start=1):
            if lowered in line.lower():
                evidence.append({"name": name, "line": index, "text": line.strip()})
                break
    return evidence


def build_profile(
    source: pd.DataFrame,
    header: list[str] | None = None,
    manifest: list[dict[str, Any]] | None = None,
    integrity: dict[str, Any] | None = None,
    raw_dir: Path | None = None,
) -> dict[str, Any]:
    if header is None:
        header = source.columns.astype(str).tolist()
    if manifest is None:
        manifest = []
    if integrity is None:
        integrity = {}
    model_frame, target_filter = build_model_frame(source)
    audit = audit_regression_frame(
        model_frame,
        target=TARGET,
        dataset_id=DATASET_ID,
    ).to_dict()
    proxy_candidates = [
        "RACECL",
        "RACECL4",
        "RACECL5",
        "RACE",
        "HHSEX",
        "AGE",
        "AGECL",
        "EDUC",
        "EDCL",
        "MARRIED",
        "FAMSTRUCT",
        "KIDS",
        "OCCAT1",
        "OCCAT2",
        "INDCAT",
        "INCOME",
        "NORMINC",
    ]
    audit.update(
        {
            **target_filter,
            "source_columns_total": int(len(header)),
            "source_last_updated": SOURCE_LAST_UPDATED,
            "survey_design_columns": SURVEY_DESIGN_COLUMNS,
            "multiple_imputation_columns": ID_COLUMNS,
            "sensitive_candidates": list(
                dict.fromkeys([*audit["sensitive_candidates"], *proxy_candidates])
            ),
            "raw_files": manifest,
            "zip_integrity": integrity,
            "target_policy": (
                "Use SCF 2022 summary extract NETWORTH as family net worth in "
                "2022 dollars. Keep negative, zero, and positive net worth values "
                "because all are substantive balance-sheet outcomes. Runner use "
                "requires raw/signed-log target sensitivity and robust outlier "
                "diagnostics for the extreme right tail."
            ),
            "group_policy": (
                "Profile race/ethnicity class, respondent sex, age, education, "
                "marital status, family structure, labor-force status, occupation, "
                "industry, and income as group or proxy diagnostics. Race and sex "
                "are household-respondent/family-level public-use variables, not "
                "individual-level causal attributes."
            ),
            "leakage_policy": (
                "Do not use ASSET, FIN, NFIN, DEBT, housing/mortgage/debt/payment "
                "fields, net-worth percentile/category fields, or any balance-sheet "
                "component when predicting NETWORTH. The audit model frame keeps "
                "demographics, income, and selected financial-behavior fields only "
                "for source profiling."
            ),
            "survey_policy": (
                "Source-review only until the SCF main weight WGT, five implicates, "
                "999 replicate weights, and grouped split by YY1 are integrated or "
                "explicitly excluded in a benchmark-only protocol."
            ),
            "license_notes": (
                "Federal Reserve SCF public summary extract and documentation are "
                "official public data. Raw ZIP, macro, and codebook stay in ignored "
                "local cache."
            ),
        }
    )
    return {
        "dataset_id": DATASET_ID,
        "target": TARGET,
        "source": {
            "name": "Federal Reserve 2022 Survey of Consumer Finances Summary Extract",
            "scf_page": SCF_PAGE,
            "data_url": DATA_URL,
            "macro_url": MACRO_URL,
            "codebook_url": CODEBOOK_URL,
            "replicate_weight_url": REPLICATE_WEIGHT_URL,
            "standard_error_documentation": STANDARD_ERROR_DOC,
            "last_updated": SOURCE_LAST_UPDATED,
            "raw_files": manifest,
        },
        "shape": {
            "source_rows": int(source.shape[0]),
            "source_columns_loaded": int(source.shape[1]),
            "source_columns_total": int(len(header)),
            "model_rows_after_target_filter": int(model_frame.shape[0]),
            "model_columns": int(model_frame.shape[1]),
        },
        "audit": audit,
        "target_summary": target_summary(model_frame[TARGET]),
        "signed_log1p_target_summary": target_summary(signed_log1p(model_frame[TARGET])),
        "group_profiles": [
            group_profile(model_frame, TARGET, column) for column in GROUP_COLUMNS
        ],
        "top_abs_correlations": top_abs_correlations(model_frame, TARGET),
        "leakage_manifest": leakage_manifest(header),
        "macro_evidence": macro_evidence(raw_dir) if raw_dir else [],
        "codebook_evidence": codebook_evidence(raw_dir) if raw_dir else [],
        "categorical_label_notes": {
            "AGECL": AGECL_LABELS,
            "EDCL": EDCL_LABELS,
            "MARRIED": MARRIED_LABELS,
            "HHSEX": HHSEX_LABELS,
        },
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
        f"- SCF page: {source['scf_page']}",
        f"- Data URL: {source['data_url']}",
        f"- Variable definitions macro: {source['macro_url']}",
        f"- Codebook: {source['codebook_url']}",
        f"- Replicate weight file: {source['replicate_weight_url']}",
        f"- Standard-error documentation: {source['standard_error_documentation']}",
        f"- Source last updated: {source['last_updated']}",
        f"- Target: `{profile['target']}`",
        "",
        "## Shape And Survey Policy",
        "",
        "- Source rows / loaded columns / total columns: "
        f"{shape['source_rows']} / {shape['source_columns_loaded']} / "
        f"{shape['source_columns_total']}",
        "- Model rows/columns after target filter: "
        f"{shape['model_rows_after_target_filter']} / {shape['model_columns']}",
        f"- Family count: {audit['family_count']}",
        f"- Implicate count profile: {audit['implicate_count_profile']}",
        f"- Implicate values: {audit['implicate_values']}",
        "- Target missing rows/rate before drop: "
        f"{audit['target_missing_rows_before_drop']} / "
        f"{audit['target_missing_rate_before_drop']:.4f}",
        "- Target negative/zero rows after filter: "
        f"{audit['target_negative_rows_after_filter']} / "
        f"{audit['target_zero_rows_after_filter']}",
        f"- Target policy: {audit['target_policy']}",
        f"- Group policy: {audit['group_policy']}",
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
        "## Signed Log1p Target Summary",
        "",
    ]
    signed_summary = profile["signed_log1p_target_summary"]
    lines.extend(
        [
            f"- mean/std: {signed_summary['mean']:.4f} / {signed_summary['std']:.4f}",
            f"- skew: {signed_summary['skew']:.4f}",
            f"- min/max: {signed_summary['min']:.4f} / {signed_summary['max']:.4f}",
        ]
    )

    lines.extend(["", "## Raw File Manifest", "", "| File | bytes | lines |", "|---|---:|---:|"])
    for row in source["raw_files"]:
        lines.append(f"| `{row['name']}` | {row['bytes']} | {row.get('line_count', '')} |")

    lines.extend(["", "## Macro And Codebook Evidence", ""])
    lines.extend(["| Evidence | Line | Text |", "|---|---:|---|"])
    for row in [*profile["macro_evidence"], *profile["codebook_evidence"]]:
        lines.append(
            f"| {row['name']} | {row['line']} | {row['text'].replace('|', '/')} |"
        )

    leakage = profile["leakage_manifest"]
    lines.extend(
        [
            "",
            "## Leakage Exclusion Manifest",
            "",
            f"- Target definition: {leakage['target_definition']}",
            f"- Matching excluded column count: {leakage['matching_column_count']}",
            "- Sample excluded columns: "
            f"{', '.join(f'`{column}`' for column in leakage['sample_matching_columns'][:35])}",
            "",
            "## Group Target Profiles",
            "",
        ]
    )
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
    integrity = zip_integrity(raw_dir / RAW_ZIP)
    source, header = load_source_frame(raw_dir)
    profile = json_safe(
        build_profile(
            source,
            header=header,
            manifest=manifest,
            integrity=integrity,
            raw_dir=raw_dir,
        )
    )
    audit = profile["audit"]
    out_dir = Path(args.out_dir) / DATASET_ID
    atomic_write_json(out_dir / "audit.json", audit)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(audit))
    atomic_write_json(out_dir / "profile.json", profile)
    atomic_write_text(out_dir / "profile.md", render_profile_markdown(profile))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
