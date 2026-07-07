"""Audit College Scorecard 2026 institution median-earnings source."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

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


DATASET_ID = "college_scorecard_2026_median_earnings"
TARGET = "MD_EARN_WNE_P10"
RAW_ZIP = "Most-Recent-Cohorts-Institution_06102026.zip"
DICTIONARY_XLSX = "CollegeScorecardDataDictionary.xlsx"
INSTITUTION_DOC_PDF = "InstitutionDataDocumentation.pdf"
RAW_FILES = [RAW_ZIP, DICTIONARY_XLSX, INSTITUTION_DOC_PDF]

DATA_PAGE = "https://collegescorecard.ed.gov/data/"
DATA_DOCUMENTATION_PAGE = "https://collegescorecard.ed.gov/data/data-documentation/"
CHANGELOG_PAGE = "https://collegescorecard.ed.gov/data/changelog/"
DATA_URL = (
    "https://ed-public-download.scorecard.network/downloads/"
    "Most-Recent-Cohorts-Institution_06102026.zip"
)
DICTIONARY_URL = (
    "https://collegescorecard.ed.gov/assets/CollegeScorecardDataDictionary.xlsx"
)
INSTITUTION_DOC_URL = (
    "https://collegescorecard.ed.gov/assets/InstitutionDataDocumentation.pdf"
)
SOURCE_LAST_UPDATED = "2026-06-10"

SOURCE_ID_COLUMNS = ["UNITID", "INSTNM", "CITY"]
INSTITUTION_COLUMNS = [
    "STABBR",
    "SCH_DEG",
    "MAIN",
    "NUMBRANCH",
    "PREDDEG",
    "HIGHDEG",
    "CONTROL",
    "REGION",
    "LOCALE",
    "CCBASIC",
    "CCUGPROF",
    "CCSIZSET",
    "RELAFFIL",
]
MINORITY_SERVING_COLUMNS = [
    "HBCU",
    "PBI",
    "ANNHI",
    "TRIBAL",
    "AANAPII",
    "HSI",
    "NANTI",
]
SINGLE_SEX_COLUMNS = ["MENONLY", "WOMENONLY"]
ADMISSIONS_COLUMNS = ["ADM_RATE", "ADM_RATE_ALL", "OPENADMP", "SAT_AVG", "ACTCMMID"]
STUDENT_BODY_COLUMNS = [
    "UGDS",
    "UGDS_WHITE",
    "UGDS_BLACK",
    "UGDS_HISP",
    "UGDS_ASIAN",
    "UGDS_AIAN",
    "UGDS_NHPI",
    "UGDS_2MOR",
    "UGDS_NRA",
    "UGDS_UNKN",
    "UGDS_MEN",
    "UGDS_WOMEN",
    "PPTUG_EF",
    "FEMALE",
    "AGE_ENTRY",
    "AGEGE24",
    "FIRST_GEN",
    "PAR_ED_PCT_1STGEN",
    "INC_PCT_LO",
    "DEP_STAT_PCT_IND",
]
AID_COST_COLUMNS = [
    "PCTPELL",
    "PCTFLOAN",
    "COSTT4_A",
    "COSTT4_P",
    "TUITIONFEE_IN",
    "TUITIONFEE_OUT",
    "TUITIONFEE_PROG",
    "NPT4_PUB",
    "NPT4_PRIV",
    "AVGFACSAL",
    "INEXPFTE",
    "TUITFTE",
]
PROGRAM_MIX_PREFIX = "PCIP"
FEATURE_COLUMNS = [
    *INSTITUTION_COLUMNS,
    *MINORITY_SERVING_COLUMNS,
    *SINGLE_SEX_COLUMNS,
    *ADMISSIONS_COLUMNS,
    *STUDENT_BODY_COLUMNS,
    *AID_COST_COLUMNS,
]
GROUP_COLUMNS = [
    "CONTROL",
    "REGION",
    "LOCALE",
    "CCBASIC",
    "HBCU",
    "PBI",
    "ANNHI",
    "TRIBAL",
    "AANAPII",
    "HSI",
    "NANTI",
    "MENONLY",
    "WOMENONLY",
    "PCTPELL",
    "INC_PCT_LO",
    "FIRST_GEN",
    "UGDS_BLACK",
    "UGDS_HISP",
    "UGDS_ASIAN",
    "UGDS_WHITE",
    "UGDS_MEN",
    "UGDS_WOMEN",
    "STABBR",
]
TARGET_COOUTCOME_PATTERNS = [
    r"EARN",
    r"DEBT",
    r"RPY",
    r"LOAN.*RPY",
    r"COMP_",
    r"_COMP_",
    r"WDRAW",
    r"ENRL_",
    r"DEATH_",
    r"C150",
    r"C200",
    r"RET_FT",
]
PRIVACY_MISSING_TOKENS = ("PrivacySuppressed", "PS", "NULL", "NA", "N/A", "")
NUMERIC_EXCEPTIONS = {"STABBR"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/college_scorecard/2026-06-10")
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    return parser.parse_args()


def require_raw_files(raw_dir: Path) -> None:
    missing = [name for name in RAW_FILES if not (raw_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing College Scorecard raw files under {raw_dir}: {missing}. "
            f"Download {DATA_URL}, {DICTIONARY_URL}, and {INSTITUTION_DOC_URL} "
            "into ignored local cache first."
        )


def raw_manifest(raw_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for name in RAW_FILES:
        path = raw_dir / name
        rows.append({"name": name, "bytes": path.stat().st_size})
    return rows


def csv_member(zip_path: Path) -> tuple[str, int]:
    with zipfile.ZipFile(zip_path) as archive:
        candidates = [
            info
            for info in archive.infolist()
            if info.filename.endswith(".csv") and not info.filename.startswith("__MACOSX")
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"Expected exactly one College Scorecard CSV in {zip_path}, "
                f"found {[info.filename for info in candidates]}"
            )
        info = candidates[0]
        return info.filename, int(info.file_size)


def zip_integrity(zip_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as archive:
        bad_member = archive.testzip()
        member, uncompressed_bytes = csv_member(zip_path)
        return {
            "bad_member": bad_member,
            "csv_member": member,
            "csv_uncompressed_bytes": uncompressed_bytes,
            "zip_members": [info.filename for info in archive.infolist()],
        }


def read_header(raw_dir: Path) -> list[str]:
    zip_path = raw_dir / RAW_ZIP
    member, _ = csv_member(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(member) as handle:
            return pd.read_csv(handle, nrows=0).columns.astype(str).tolist()


def selected_columns(header: list[str]) -> list[str]:
    program_mix = [column for column in header if column.startswith(PROGRAM_MIX_PREFIX)]
    columns = [
        TARGET,
        *SOURCE_ID_COLUMNS,
        *FEATURE_COLUMNS,
        *program_mix,
    ]
    return list(dict.fromkeys([column for column in columns if column in header]))


def load_source_frame(raw_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    header = read_header(raw_dir)
    columns = selected_columns(header)
    zip_path = raw_dir / RAW_ZIP
    member, _ = csv_member(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(member) as handle:
            frame = pd.read_csv(
                handle,
                usecols=columns,
                low_memory=False,
                na_values=list(PRIVACY_MISSING_TOKENS),
                keep_default_na=True,
            )
    return frame, header


def xlsx_col_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter.upper()) - 64
    return index - 1


def xlsx_sheet_rows(path: Path, sheet_name: str) -> list[list[str]]:
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    with zipfile.ZipFile(path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        sheet_targets = {}
        for sheet in workbook.find("a:sheets", ns):
            rel_id = sheet.attrib[
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            ]
            sheet_targets[sheet.attrib["name"]] = relmap[rel_id]
        if sheet_name not in sheet_targets:
            raise ValueError(f"Sheet {sheet_name!r} not found in {path}")

        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared.findall("a:si", ns):
                shared_strings.append(
                    "".join(text.text or "" for text in item.findall(".//a:t", ns))
                )

        target = sheet_targets[sheet_name]
        sheet_path = target if target.startswith("xl/") else f"xl/{target}"
        root = ElementTree.fromstring(archive.read(sheet_path))
        rows = []
        for row in root.findall(".//a:row", ns):
            values: dict[int, str] = {}
            for cell in row.findall("a:c", ns):
                raw_value = cell.find("a:v", ns)
                if raw_value is None:
                    continue
                text = raw_value.text or ""
                if cell.attrib.get("t") == "s":
                    text = shared_strings[int(text)]
                values[xlsx_col_index(cell.attrib["r"])] = text
            if values:
                rows.append([values.get(index, "") for index in range(max(values) + 1)])
        return rows


def data_dictionary(raw_dir: Path, variables: list[str]) -> dict[str, Any]:
    rows = xlsx_sheet_rows(raw_dir / DICTIONARY_XLSX, "Institution_Data_Dictionary")
    header = rows[0]
    index = {column: i for i, column in enumerate(header)}
    wanted = set(variables)
    entries: dict[str, dict[str, Any]] = {}
    for row in rows[1:]:
        variable = row[index["VARIABLE NAME"]] if len(row) > index["VARIABLE NAME"] else ""
        if variable not in wanted:
            continue
        entry = entries.setdefault(
            variable,
            {
                "name": "",
                "developer_category": "",
                "developer_friendly_name": "",
                "api_data_type": "",
                "source": "",
                "notes": "",
                "value_labels": [],
            },
        )
        entry["name"] = entry["name"] or row[index["NAME OF DATA ELEMENT"]]
        entry["developer_category"] = entry["developer_category"] or row[
            index["dev-category"]
        ]
        entry["developer_friendly_name"] = entry[
            "developer_friendly_name"
        ] or row[index["developer-friendly name"]]
        entry["api_data_type"] = entry["api_data_type"] or row[index["API data type"]]
        entry["source"] = entry["source"] or row[index["SOURCE"]]
        if len(row) > index["NOTES"] and row[index["NOTES"]]:
            entry["notes"] = entry["notes"] or row[index["NOTES"]]
        value = row[index["VALUE"]] if len(row) > index["VALUE"] else ""
        label = row[index["LABEL"]] if len(row) > index["LABEL"] else ""
        if value or label:
            entry["value_labels"].append({"value": value, "label": label})
    return entries


def normalize_model_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in normalized.select_dtypes(include=["object"]).columns:
        normalized[column] = normalized[column].where(
            ~normalized[column].isin(PRIVACY_MISSING_TOKENS),
            np.nan,
        )
    for column in normalized.columns:
        if column in NUMERIC_EXCEPTIONS:
            continue
        converted = pd.to_numeric(normalized[column], errors="coerce")
        if converted.notna().sum() > 0:
            normalized[column] = converted
    return normalized


def build_model_frame(source: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    working = normalize_model_frame(source)
    target = pd.to_numeric(working[TARGET], errors="coerce")
    target_missing = target.isna()
    target_nonpositive = target.notna() & (target <= 0)
    valid_target = target.notna() & (target > 0)
    feature_columns = [
        column
        for column in working.columns
        if column not in {TARGET, *SOURCE_ID_COLUMNS} and not is_leakage_column(column)
    ]
    model_frame = working.loc[valid_target, [TARGET, *feature_columns]].copy()
    model_frame[TARGET] = target.loc[valid_target].astype(float)
    target_filter = {
        "source_rows": int(source.shape[0]),
        "source_columns_loaded": int(source.shape[1]),
        "model_rows_after_target_filter": int(model_frame.shape[0]),
        "target_missing_rows_before_drop": int(target_missing.sum()),
        "target_missing_rate_before_drop": float(target_missing.mean()),
        "target_nonpositive_rows_before_drop": int(target_nonpositive.sum()),
        "target_nonpositive_rate_before_drop": float(target_nonpositive.mean()),
        "excluded_identifier_columns": [
            column for column in SOURCE_ID_COLUMNS if column in source.columns
        ],
    }
    return model_frame, target_filter


def leakage_manifest(header: list[str]) -> dict[str, Any]:
    matching_columns = sorted(
        {
            column
            for column in header
            if is_leakage_column(column)
        }
    )
    return {
        "target": TARGET,
        "excluded_patterns": TARGET_COOUTCOME_PATTERNS,
        "matching_column_count": len(matching_columns),
        "sample_matching_columns": matching_columns[:80],
    }


def is_leakage_column(column: str) -> bool:
    if column == TARGET:
        return False
    return any(
        re.search(pattern, column) for pattern in TARGET_COOUTCOME_PATTERNS
    )


def build_profile(
    source: pd.DataFrame,
    header: list[str] | None = None,
    manifest: list[dict[str, Any]] | None = None,
    dictionary: dict[str, Any] | None = None,
    integrity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if header is None:
        header = source.columns.astype(str).tolist()
    if manifest is None:
        manifest = []
    if dictionary is None:
        dictionary = {}
    if integrity is None:
        integrity = {}

    model_frame, target_filter = build_model_frame(source)
    audit = audit_regression_frame(
        model_frame,
        target=TARGET,
        dataset_id=DATASET_ID,
    ).to_dict()
    proxy_candidates = [
        "STABBR",
        "CONTROL",
        "REGION",
        "LOCALE",
        "HBCU",
        "PBI",
        "ANNHI",
        "TRIBAL",
        "AANAPII",
        "HSI",
        "NANTI",
        "MENONLY",
        "WOMENONLY",
        "UGDS_WHITE",
        "UGDS_BLACK",
        "UGDS_HISP",
        "UGDS_ASIAN",
        "UGDS_AIAN",
        "UGDS_NHPI",
        "UGDS_MEN",
        "UGDS_WOMEN",
        "PCTPELL",
        "INC_PCT_LO",
        "FIRST_GEN",
    ]
    audit.update(
        {
            **target_filter,
            "source_columns_total": int(len(header)),
            "source_last_updated": SOURCE_LAST_UPDATED,
            "sensitive_candidates": list(
                dict.fromkeys([*audit["sensitive_candidates"], *proxy_candidates])
            ),
            "raw_files": manifest,
            "zip_integrity": integrity,
            "target_policy": (
                "Use College Scorecard institution-level MD_EARN_WNE_P10: median "
                "earnings of students working and not enrolled 10 years after "
                "entry. Drop missing and nonpositive target values for audit "
                "profiling. Runner use requires cohort-alignment review, "
                "privacy-suppression policy, and raw/log target sensitivity."
            ),
            "group_policy": (
                "Profile institution control, geography, locale, Carnegie class, "
                "minority-serving institution flags, single-sex flags, student "
                "race/ethnicity shares, Pell/low-income/first-generation shares, "
                "and gender composition as group or proxy diagnostics. These are "
                "institution-level composition/proxy fields, not individual "
                "protected attributes."
            ),
            "leakage_policy": (
                "Exclude all earnings fields other than the target, all debt and "
                "repayment fields, and post-entry completion/withdrawal/enrollment "
                "outcome fields from this audit model frame. Cost, aid, admissions, "
                "program mix, and institution descriptors are retained only for "
                "source profiling and require timing review before runner use."
            ),
            "license_notes": (
                "College Scorecard is an official U.S. Department of Education "
                "public dataset. Raw ZIP, dictionary, and technical PDF remain in "
                "ignored local cache."
            ),
        }
    )
    return {
        "dataset_id": DATASET_ID,
        "target": TARGET,
        "source": {
            "name": "College Scorecard Most Recent Institution-Level Data",
            "data_page": DATA_PAGE,
            "data_documentation": DATA_DOCUMENTATION_PAGE,
            "change_log": CHANGELOG_PAGE,
            "data_url": DATA_URL,
            "dictionary_url": DICTIONARY_URL,
            "institution_documentation": INSTITUTION_DOC_URL,
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
        "dictionary": dictionary,
        "target_summary": target_summary(model_frame[TARGET]),
        "log1p_target_summary": target_summary(np.log1p(model_frame[TARGET])),
        "group_profiles": [
            group_profile(model_frame, TARGET, column) for column in GROUP_COLUMNS
        ],
        "top_abs_correlations": top_abs_correlations(model_frame, TARGET),
        "leakage_manifest": leakage_manifest(header),
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
        f"- Data page: {source['data_page']}",
        f"- Data documentation: {source['data_documentation']}",
        f"- Change log: {source['change_log']}",
        f"- Data URL: {source['data_url']}",
        f"- Dictionary: {source['dictionary_url']}",
        f"- Institution documentation: {source['institution_documentation']}",
        f"- Source last updated: {source['last_updated']}",
        f"- Target: `{profile['target']}`",
        "",
        "## Shape And Target Policy",
        "",
        "- Source rows / loaded columns / total columns: "
        f"{shape['source_rows']} / {shape['source_columns_loaded']} / "
        f"{shape['source_columns_total']}",
        "- Model rows/columns after target filter: "
        f"{shape['model_rows_after_target_filter']} / {shape['model_columns']}",
        "- Target missing rows/rate before drop: "
        f"{audit['target_missing_rows_before_drop']} / "
        f"{audit['target_missing_rate_before_drop']:.4f}",
        "- Target nonpositive rows/rate before drop: "
        f"{audit['target_nonpositive_rows_before_drop']} / "
        f"{audit['target_nonpositive_rate_before_drop']:.4f}",
        f"- Target policy: {audit['target_policy']}",
        f"- Group policy: {audit['group_policy']}",
        f"- Leakage policy: {audit['leakage_policy']}",
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

    lines.extend(["", "## Selected Data Dictionary Entries", ""])
    lines.extend(["| Variable | Name | Source | Value labels |", "|---|---|---|---|"])
    for variable, entry in sorted(profile["dictionary"].items()):
        value_labels = "; ".join(
            f"{label['value']}={label['label']}"
            for label in entry.get("value_labels", [])[:8]
            if label.get("value") or label.get("label")
        )
        lines.append(
            f"| `{variable}` | {entry.get('name', '').replace('|', '/')} | "
            f"{entry.get('source', '').replace('|', '/')} | "
            f"{value_labels.replace('|', '/')} |"
        )

    leakage = profile["leakage_manifest"]
    lines.extend(
        [
            "",
            "## Leakage Exclusion Manifest",
            "",
            f"- Matching excluded column count: {leakage['matching_column_count']}",
            "- Excluded patterns: "
            f"{', '.join(f'`{pattern}`' for pattern in leakage['excluded_patterns'])}",
            "- Sample excluded columns: "
            f"{', '.join(f'`{column}`' for column in leakage['sample_matching_columns'][:30])}",
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
    dictionary_variables = [
        TARGET,
        *GROUP_COLUMNS,
        *ADMISSIONS_COLUMNS,
        *AID_COST_COLUMNS,
        "UGDS",
        "AGE_ENTRY",
        "PAR_ED_PCT_1STGEN",
    ]
    dictionary = data_dictionary(raw_dir, dictionary_variables)
    profile = json_safe(
        build_profile(
            source,
            header=header,
            manifest=manifest,
            dictionary=dictionary,
            integrity=integrity,
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
