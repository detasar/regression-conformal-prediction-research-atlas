"""Audit custom Folktables ACS regression tasks without binary target transforms."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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


SURVEY_YEAR = "2018"
HORIZON = "1-Year"
SURVEY = "person"
DEFAULT_STATE = "WY"
WEIGHT_COLUMN = "PWGTP"
CENSUS_2018_DICTIONARY_URL = (
    "https://www2.census.gov/programs-surveys/acs/tech_docs/pums/"
    "data_dict/PUMS_Data_Dictionary_2018.pdf"
)
FOLKTABLES_URL = "https://github.com/socialfoundations/folktables"
CENSUS_PUMS_DOCS_URL = (
    "https://www.census.gov/programs-surveys/acs/microdata/documentation.html"
)


@dataclass(frozen=True)
class FolktablesTaskSpec:
    dataset_id: str
    name: str
    source_task: str
    target: str
    features: list[str]
    group: str
    group_columns: list[str]
    preprocess: Callable[[pd.DataFrame], pd.DataFrame]
    predefined_target_transform: str
    target_policy: str
    extra_context_columns: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", action="append", default=None)
    parser.add_argument("--task", action="append", default=None)
    parser.add_argument("--root-dir", default="data/raw/folktables")
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    parser.add_argument("--no-download", action="store_true")
    return parser.parse_args()


def unique_existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    seen = set()
    selected = []
    for column in columns:
        if column in df.columns and column not in seen:
            selected.append(column)
            seen.add(column)
    return selected


def variable_definitions(
    definitions: pd.DataFrame | None,
    variables: list[str],
    *,
    max_values: int = 12,
) -> dict[str, dict[str, Any]]:
    if definitions is None or definitions.empty:
        return {}

    wanted = set(variables)
    entries: dict[str, dict[str, Any]] = {}
    current_name = None
    for row in definitions.itertuples(index=False, name=None):
        marker = str(row[0])
        variable = str(row[1])
        if marker == "NAME":
            current_name = variable
            if variable in wanted:
                entries[variable] = {
                    "type": None if pd.isna(row[2]) else str(row[2]),
                    "width": None if pd.isna(row[3]) else str(row[3]),
                    "description": None if pd.isna(row[4]) else str(row[4]),
                    "values": [],
                }
        elif marker == "VAL" and current_name in entries:
            values = entries[current_name]["values"]
            if len(values) < max_values:
                values.append(
                    {
                        "from": None if pd.isna(row[4]) else str(row[4]),
                        "to": None if pd.isna(row[5]) else str(row[5]),
                        "label": None if pd.isna(row[6]) else str(row[6]),
                    }
                )
    return entries


def build_task_specs() -> dict[str, FolktablesTaskSpec]:
    from folktables import ACSIncomePovertyRatio, ACSTravelTime

    return {
        "travel_time": FolktablesTaskSpec(
            dataset_id="folktables_acs_travel_time_wy",
            name="Folktables ACS Travel Time Regression WY",
            source_task="ACSTravelTime",
            target="JWMNP",
            features=list(ACSTravelTime.features),
            group=str(ACSTravelTime.group),
            group_columns=["RAC1P", "SEX", "AGEP", "DIS", "POVPIP"],
            preprocess=ACSTravelTime._preprocess,
            predefined_target_transform="JWMNP > 20 binary threshold, disabled here",
            target_policy=(
                "Continuous travel time in minutes for the Folktables travel-time "
                "universe. Drop rows with missing JWMNP after the age, positive "
                "person-weight, and employed-civilian filters; keep survey-weight "
                "policy unresolved before runner use."
            ),
            extra_context_columns=[WEIGHT_COLUMN, "ESR"],
        ),
        "poverty_ratio": FolktablesTaskSpec(
            dataset_id="folktables_acs_poverty_ratio_wy",
            name="Folktables ACS Income-to-Poverty Ratio Regression WY",
            source_task="ACSIncomePovertyRatio",
            target="POVPIP",
            features=list(ACSIncomePovertyRatio.features),
            group=str(ACSIncomePovertyRatio.group),
            group_columns=["RAC1P", "SEX", "AGEP", "DIS", "NATIVITY", "DEAR", "DEYE", "DREM"],
            preprocess=ACSIncomePovertyRatio._preprocess,
            predefined_target_transform="POVPIP < 250 binary threshold, disabled here",
            target_policy=(
                "Continuous income-to-poverty ratio recode. Drop rows with missing "
                "POVPIP for audit profiling; document top-code at 501 and person "
                "survey-weight policy before runner use."
            ),
            extra_context_columns=[WEIGHT_COLUMN],
        ),
    }


def build_task_profile(
    raw_frame: pd.DataFrame,
    spec: FolktablesTaskSpec,
    *,
    definitions: pd.DataFrame | None,
    states: list[str],
    survey_year: str = SURVEY_YEAR,
    horizon: str = HORIZON,
) -> dict[str, Any]:
    universe = spec.preprocess(raw_frame.copy())
    audit_columns = unique_existing_columns(
        universe,
        [*spec.features, *spec.extra_context_columns, spec.target, spec.group],
    )
    universe_frame = universe[audit_columns].copy()
    numeric_target = pd.to_numeric(universe_frame[spec.target], errors="coerce")
    model_frame = universe_frame[numeric_target.notna()].copy()

    audit = audit_regression_frame(
        model_frame,
        target=spec.target,
        dataset_id=spec.dataset_id,
    ).to_dict()
    audit.update(
        {
            "source_loader": "folktables.ACSDataSource",
            "folktables_source_task": spec.source_task,
            "states": states,
            "survey_year": survey_year,
            "horizon": horizon,
            "survey": SURVEY,
            "source_rows": int(raw_frame.shape[0]),
            "preprocess_universe_rows": int(universe_frame.shape[0]),
            "model_rows_after_target_drop": int(model_frame.shape[0]),
            "target_missing_rate_before_drop": float(numeric_target.isna().mean()),
            "features": spec.features,
            "group": spec.group,
            "group_columns": spec.group_columns,
            "survey_weight_column": WEIGHT_COLUMN if WEIGHT_COLUMN in audit_columns else None,
            "predefined_target_transform": spec.predefined_target_transform,
            "target_transform_used": None,
            "target_policy": spec.target_policy,
        }
    )

    definition_variables = unique_existing_columns(
        universe,
        [spec.target, spec.group, WEIGHT_COLUMN, *spec.group_columns, *spec.extra_context_columns],
    )
    return {
        "dataset_id": spec.dataset_id,
        "name": spec.name,
        "target": spec.target,
        "source": {
            "name": "Folktables ACS PUMS custom regression",
            "folktables_task": spec.source_task,
            "folktables_url": FOLKTABLES_URL,
            "census_pums_docs": CENSUS_PUMS_DOCS_URL,
            "census_2018_dictionary": CENSUS_2018_DICTIONARY_URL,
            "states": states,
            "survey_year": survey_year,
            "horizon": horizon,
            "survey": SURVEY,
        },
        "shape": {
            "source_rows": int(raw_frame.shape[0]),
            "preprocess_universe_rows": int(universe_frame.shape[0]),
            "model_rows_after_target_drop": int(model_frame.shape[0]),
            "columns": int(model_frame.shape[1]),
        },
        "audit": audit,
        "target_summary": target_summary(model_frame[spec.target]),
        "group_profiles": [
            group_profile(model_frame, spec.target, column)
            for column in spec.group_columns
            if column in model_frame.columns
        ],
        "top_abs_correlations": top_abs_correlations(model_frame, spec.target),
        "variable_definitions": variable_definitions(definitions, definition_variables),
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    audit = profile["audit"]
    source = profile["source"]
    lines = [
        f"# Dataset Profile: {profile['dataset_id']}",
        "",
        "## Source",
        "",
        f"- Name: {profile['name']}",
        f"- Folktables task: `{source['folktables_task']}`",
        f"- Folktables source: {source['folktables_url']}",
        f"- Census PUMS docs: {source['census_pums_docs']}",
        f"- Census 2018 dictionary: {source['census_2018_dictionary']}",
        f"- State(s): {', '.join(source['states'])}",
        f"- Survey: {source['survey_year']} {source['horizon']} {source['survey']}",
        f"- Target: `{profile['target']}`",
        f"- Target transform used: {audit['target_transform_used'] or 'none'}",
        f"- Predefined transform disabled: {audit['predefined_target_transform']}",
        "",
        "## Universe And Target Policy",
        "",
        f"- Source rows: {audit['source_rows']}",
        f"- Rows after Folktables preprocess: {audit['preprocess_universe_rows']}",
        f"- Rows after missing-target drop: {audit['model_rows_after_target_drop']}",
        f"- Target missing rate before drop: {audit['target_missing_rate_before_drop']:.4f}",
        f"- Survey weight column: `{audit['survey_weight_column']}`",
        f"- Policy: {audit['target_policy']}",
        "",
        "## Audit Summary",
        "",
        f"- Target missing rate after drop: {audit['target_missing_rate']:.4f}",
        f"- Target mean/std: {audit['target_mean']:.4f} / {audit['target_std']:.4f}",
        f"- Target skew: {audit['target_skew']:.4f}",
        f"- Target range: {audit['target_min']:.4f} to {audit['target_max']:.4f}",
        f"- Duplicate row rate: {audit['duplicate_row_rate']:.4f}",
        f"- Sensitive/proxy candidates: {', '.join(audit['sensitive_candidates']) or 'none_detected'}",
        f"- Recommended actions: {', '.join(audit['recommended_actions']) or 'none'}",
        "",
        "## Group Target Profiles",
        "",
    ]
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

    lines.extend(["", "## Variable Definitions", ""])
    for variable, entry in profile["variable_definitions"].items():
        lines.extend(
            [
                f"### `{variable}`",
                "",
                f"- Type: {entry['type']}",
                f"- Width: {entry['width']}",
                f"- Description: {entry['description']}",
                "",
            ]
        )
        if entry["values"]:
            lines.extend(["| From | To | Label |", "|---|---|---|"])
            for value in entry["values"]:
                lines.append(f"| {value['from']} | {value['to']} | {value['label']} |")
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    from folktables import ACSDataSource

    args = parse_args()
    states = sorted({state.upper() for state in (args.state or [DEFAULT_STATE])})
    task_specs = build_task_specs()
    selected_tasks = args.task or sorted(task_specs)

    data_source = ACSDataSource(
        survey_year=SURVEY_YEAR,
        horizon=HORIZON,
        survey=SURVEY,
        root_dir=args.root_dir,
    )
    raw_frame = data_source.get_data(states=states, download=not args.no_download)
    definitions = data_source.get_definitions(download=not args.no_download)

    outputs = []
    for task_name in selected_tasks:
        if task_name not in task_specs:
            raise ValueError(f"unknown task {task_name!r}; choose one of {sorted(task_specs)}")
        spec = task_specs[task_name]
        profile = json_safe(
            build_task_profile(
                raw_frame,
                spec,
                definitions=definitions,
                states=states,
            )
        )
        audit = profile["audit"]
        out_dir = Path(args.out_dir) / spec.dataset_id
        atomic_write_json(out_dir / "audit.json", audit)
        atomic_write_text(out_dir / "audit.md", render_audit_markdown(audit))
        atomic_write_json(out_dir / "profile.json", profile)
        atomic_write_text(out_dir / "profile.md", render_profile_markdown(profile))
        outputs.append(
            {
                "dataset_id": spec.dataset_id,
                "audit_path": str(out_dir / "audit.json"),
                "profile_path": str(out_dir / "profile.json"),
            }
        )

    print(json.dumps({"status": "ok", "materialized": len(outputs), "outputs": outputs}))


if __name__ == "__main__":
    main()
