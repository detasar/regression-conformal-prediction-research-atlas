"""Audit OECD PISA 2022 mathematics plausible-value regression source."""

from __future__ import annotations

import argparse
import json
import zipfile
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


DATASET_ID = "pisa_2022_math_pv_mean"
TARGET = "MATH_PV_MEAN"
RAW_ZIP = "STU_QQQ_SAS.zip"
MATH_PV_COLUMNS = [f"PV{i}MATH" for i in range(1, 11)]
READING_PV_COLUMNS = [f"PV{i}READ" for i in range(1, 11)]
SCIENCE_PV_COLUMNS = [f"PV{i}SCIE" for i in range(1, 11)]
WEIGHT_COLUMNS = ["W_FSTUWT", *[f"W_FSTURWT{i}" for i in range(1, 81)]]
IDENTIFIER_COLUMNS = ["CNT", "CNTRYID", "CNTSCHID", "CNTSTUID"]
GROUP_COLUMNS = ["ST004D01T", "IMMIG", "ESCS", "AGE", "CNT", "LANGN"]
FEATURE_CANDIDATES = [
    "CNT",
    "CNTRYID",
    "AGE",
    "ST004D01T",
    "GRADE",
    "IMMIG",
    "LANGN",
    "ESCS",
    "HOMEPOS",
    "HISEI",
    "PAREDINT",
    "BMMJ1",
    "BFMJ2",
    "MISCED",
    "FISCED",
    "BELONG",
    "BULLIED",
    "FEELSAFE",
    "ANXMAT",
    "MATHEFF",
    "MATHPERS",
    "MATHMOT",
    "ICTHOME",
    "ICTSCH",
    *WEIGHT_COLUMNS,
]
SOURCE_DOC = "https://www.oecd.org/en/data/datasets/pisa-2022-database.html"
METHODOLOGY_DOC = (
    "https://www.oecd.org/en/about/programmes/pisa/"
    "how-to-prepare-and-analyse-the-pisa-database.html"
)
DATA_INDEX = "https://webfs.oecd.org/pisa2022/index.html"
SAS_ZIP_URL = "https://webfs.oecd.org/pisa2022/STU_QQQ_SAS.zip"
SPSS_ZIP_URL = "https://webfs.oecd.org/pisa2022/STU_QQQ_SPSS.zip"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/pisa/2022")
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    parser.add_argument("--chunksize", type=int, default=25_000)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional development-only row cap; omit for committed full audits.",
    )
    return parser.parse_args()


def require_raw_files(raw_dir: Path) -> None:
    if not (raw_dir / RAW_ZIP).exists():
        raise FileNotFoundError(
            f"Missing PISA raw file {raw_dir / RAW_ZIP}. Download from {SAS_ZIP_URL}"
        )


def raw_manifest(raw_dir: Path) -> list[dict[str, Any]]:
    zip_path = raw_dir / RAW_ZIP
    rows = [{"name": RAW_ZIP, "bytes": zip_path.stat().st_size}]
    extracted = raw_dir / sas_member_name(zip_path)
    if extracted.exists():
        rows.append({"name": extracted.name, "bytes": extracted.stat().st_size})
    return rows


def sas_member(zip_path: Path) -> tuple[str, int]:
    with zipfile.ZipFile(zip_path) as archive:
        members = [
            (info.filename, info.file_size)
            for info in archive.infolist()
            if info.filename.lower().endswith(".sas7bdat")
        ]
    if len(members) != 1:
        raise ValueError(f"Expected exactly one SAS7BDAT member in {zip_path}: {members}")
    filename, file_size = members[0]
    return Path(filename).name, int(file_size)


def sas_member_name(zip_path: Path) -> str:
    return sas_member(zip_path)[0]


def extract_sas_file(raw_dir: Path) -> Path:
    zip_path = raw_dir / RAW_ZIP
    member, expected_size = sas_member(zip_path)
    out_path = raw_dir / member
    if out_path.exists() and out_path.stat().st_size == expected_size:
        return out_path
    if out_path.exists():
        out_path.unlink()
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(member) as src, tmp_path.open("wb") as dst:
            while True:
                chunk = src.read(1024 * 1024 * 16)
                if not chunk:
                    break
                dst.write(chunk)
    if tmp_path.stat().st_size != expected_size:
        raise IOError(
            f"Extracted {tmp_path} has {tmp_path.stat().st_size} bytes; "
            f"expected {expected_size}"
        )
    tmp_path.replace(out_path)
    return out_path


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {
        col: col.decode("latin1") if isinstance(col, bytes) else str(col)
        for col in df.columns
    }
    return df.rename(columns=renamed)


def selected_columns_from(chunk: pd.DataFrame) -> list[str]:
    wanted = [
        *IDENTIFIER_COLUMNS,
        *FEATURE_CANDIDATES,
        *MATH_PV_COLUMNS,
        *READING_PV_COLUMNS,
        *SCIENCE_PV_COLUMNS,
    ]
    return [col for col in dict.fromkeys(wanted) if col in chunk.columns]


def load_student_frame(
    raw_dir: Path,
    *,
    chunksize: int = 25_000,
    max_rows: int | None = None,
) -> pd.DataFrame:
    sas_path = extract_sas_file(raw_dir)
    chunks: list[pd.DataFrame] = []
    rows_read = 0
    reader = pd.read_sas(
        sas_path,
        format="sas7bdat",
        encoding="latin1",
        chunksize=chunksize,
    )
    for chunk in reader:
        chunk = normalize_column_names(chunk)
        selected = selected_columns_from(chunk)
        if not selected:
            raise ValueError("No expected PISA columns were found in the student file")
        if max_rows is not None:
            remaining = max_rows - rows_read
            if remaining <= 0:
                break
            chunk = chunk.head(remaining)
        chunks.append(chunk.loc[:, selected].copy())
        rows_read += int(chunk.shape[0])
        if max_rows is not None and rows_read >= max_rows:
            break
    if not chunks:
        raise ValueError("PISA student file yielded no rows")
    frame = pd.concat(chunks, ignore_index=True)
    missing_pvs = [col for col in MATH_PV_COLUMNS if col not in frame.columns]
    if missing_pvs:
        raise ValueError(f"Missing required math plausible-value columns: {missing_pvs}")
    return frame


def build_model_frame(student: pd.DataFrame) -> pd.DataFrame:
    frame = student.copy()
    for col in MATH_PV_COLUMNS:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame[TARGET] = frame[MATH_PV_COLUMNS].mean(axis=1, skipna=True)
    retained = [
        TARGET,
        *[
            col
            for col in FEATURE_CANDIDATES
            if col in frame.columns and col not in MATH_PV_COLUMNS
        ],
    ]
    return frame.loc[frame[TARGET].notna(), list(dict.fromkeys(retained))].copy()


def build_profile(
    student: pd.DataFrame,
    manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    model_frame = build_model_frame(student)
    audit = audit_regression_frame(
        model_frame,
        target=TARGET,
        dataset_id=DATASET_ID,
    ).to_dict()
    available_group_columns = [col for col in GROUP_COLUMNS if col in model_frame.columns]
    available_weight_columns = [col for col in WEIGHT_COLUMNS if col in student.columns]
    audit.update(
        {
            "source_rows": int(student.shape[0]),
            "model_rows_after_target_drop": int(model_frame.shape[0]),
            "math_plausible_value_columns": MATH_PV_COLUMNS,
            "available_weight_columns": available_weight_columns,
            "replicate_weight_count": int(
                sum(col.startswith("W_FSTURWT") for col in available_weight_columns)
            ),
            "sensitive_candidates": list(
                dict.fromkeys([*audit["sensitive_candidates"], *available_group_columns])
            ),
            "target_policy": (
                "Use the row-wise mean of PV1MATH-PV10MATH only for source "
                "profiling and conformal-regression method prototyping. "
                "Publication-grade PISA analysis must run across all plausible "
                "values and combine estimates according to PISA methodology."
            ),
            "survey_policy": (
                "Source-review only until final student weights and replicate "
                "weights are integrated into metrics or explicitly excluded by "
                "a benchmark-only protocol."
            ),
            "education_policy": (
                "Treat students as nested within schools and countries. Ordinary "
                "iid splits are not valid for headline country, school, or "
                "demographic fairness claims without grouped-split sensitivity."
            ),
            "leakage_policy": (
                "Raw plausible values for math, reading, and science are target "
                "components or co-outcomes and are excluded from the audit model "
                "frame after deriving the profiling target."
            ),
        }
    )
    return {
        "dataset_id": DATASET_ID,
        "target": TARGET,
        "source": {
            "name": "OECD PISA 2022 student questionnaire mathematics plausible values",
            "source_doc": SOURCE_DOC,
            "methodology_doc": METHODOLOGY_DOC,
            "data_index": DATA_INDEX,
            "sas_zip_url": SAS_ZIP_URL,
            "spss_zip_url": SPSS_ZIP_URL,
            "raw_files": manifest,
        },
        "shape": {
            "source_rows": int(student.shape[0]),
            "source_columns_loaded": int(student.shape[1]),
            "model_rows_after_target_drop": int(model_frame.shape[0]),
            "model_columns": int(model_frame.shape[1]),
        },
        "audit": audit,
        "target_summary": target_summary(model_frame[TARGET]),
        "group_profiles": [
            group_profile(model_frame, TARGET, column) for column in available_group_columns
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
        f"- OECD database page: {source['source_doc']}",
        f"- OECD methodology page: {source['methodology_doc']}",
        f"- PISA 2022 data index: {source['data_index']}",
        f"- Target: `{profile['target']}`",
        "",
        "## Shape And Target Policy",
        "",
        f"- Source rows / loaded columns: {shape['source_rows']} / {shape['source_columns_loaded']}",
        "- Model rows / columns after target construction: "
        f"{shape['model_rows_after_target_drop']} / {shape['model_columns']}",
        "- Math plausible-value columns: "
        f"{', '.join(audit['math_plausible_value_columns'])}",
        "- Available weight columns: "
        f"{len(audit['available_weight_columns'])} "
        f"({audit['replicate_weight_count']} replicate weights)",
        f"- Target policy: {audit['target_policy']}",
        f"- Survey policy: {audit['survey_policy']}",
        f"- Education policy: {audit['education_policy']}",
        f"- Leakage policy: {audit['leakage_policy']}",
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
    student = load_student_frame(
        raw_dir,
        chunksize=args.chunksize,
        max_rows=args.max_rows,
    )
    manifest = raw_manifest(raw_dir)
    profile = json_safe(build_profile(student, manifest))
    audit = profile["audit"]
    out_dir = Path(args.out_dir) / DATASET_ID
    atomic_write_json(out_dir / "audit.json", audit)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(audit))
    atomic_write_json(out_dir / "profile.json", profile)
    atomic_write_text(out_dir / "profile.md", render_profile_markdown(profile))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
