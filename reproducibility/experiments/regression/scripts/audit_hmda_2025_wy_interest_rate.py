"""Audit HMDA 2025 Wyoming originated-loan interest-rate regression source."""

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
    render_audit_markdown,
)
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


DATASET_ID = "hmda_2025_wy_interest_rate"
TARGET = "interest_rate"
RAW_FILES = ["hmda_2025_wy_action_taken_1.csv"]
SOURCE_URL = "https://ffiec.cfpb.gov/data-browser/data/2025"
DATA_BROWSER_API_DOC = "https://ffiec.cfpb.gov/documentation/api/data-browser/"
PUBLIC_LAR_SCHEMA = (
    "https://ffiec.cfpb.gov/documentation/publications/loan-level-datasets/"
    "public-lar-schema"
)
CFPB_2025_RELEASE = (
    "https://www.consumerfinance.gov/about-us/newsroom/"
    "2025-hmda-data-on-mortgage-lending-now-available/"
)
API_QUERY = (
    "https://ffiec.cfpb.gov/v2/data-browser-api/view/csv?"
    "states=WY&years=2025&actions_taken=1"
)
AGGREGATION_QUERY = (
    "https://ffiec.cfpb.gov/v2/data-browser-api/view/aggregations?"
    "states=WY&years=2025&actions_taken=1"
)
SOURCE_AGGREGATION_COUNT = 13328

EXTRA_MISSING_TOKENS = ("Exempt",)
TARGET_COMPONENT_DROP_COLUMNS = ["rate_spread"]
POST_PRICING_DROP_COLUMNS = [
    "hoepa_status",
    "total_loan_costs",
    "total_points_and_fees",
    "origination_charges",
    "discount_points",
    "lender_credits",
]
POST_OUTCOME_DROP_COLUMNS = [
    "purchaser_type",
    "denial_reason-1",
    "denial_reason-2",
    "denial_reason-3",
    "denial_reason-4",
]
CONSTANT_CONTEXT_DROP_COLUMNS = ["activity_year", "state_code", "action_taken"]
GROUP_COLUMNS = [
    "derived_race",
    "derived_ethnicity",
    "derived_sex",
    "applicant_age",
    "applicant_age_above_62",
    "debt_to_income_ratio",
    "county_code",
    "derived_loan_product_type",
    "loan_type",
    "loan_purpose",
]
FEATURE_COLUMNS = [
    "lei",
    "derived_msa-md",
    "county_code",
    "census_tract",
    "conforming_loan_limit",
    "derived_loan_product_type",
    "derived_dwelling_category",
    "derived_ethnicity",
    "derived_race",
    "derived_sex",
    "preapproval",
    "loan_type",
    "loan_purpose",
    "lien_status",
    "reverse_mortgage",
    "open-end_line_of_credit",
    "business_or_commercial_purpose",
    "loan_amount",
    "loan_to_value_ratio",
    "loan_term",
    "intro_rate_period",
    "negative_amortization",
    "interest_only_payment",
    "balloon_payment",
    "other_nonamortizing_features",
    "property_value",
    "construction_method",
    "occupancy_type",
    "manufactured_home_secured_property_type",
    "manufactured_home_land_property_interest",
    "total_units",
    "multifamily_affordable_units",
    "income",
    "debt_to_income_ratio",
    "applicant_credit_score_type",
    "co-applicant_credit_score_type",
    "applicant_ethnicity-1",
    "co-applicant_ethnicity-1",
    "applicant_ethnicity_observed",
    "co-applicant_ethnicity_observed",
    "applicant_race-1",
    "co-applicant_race-1",
    "applicant_race_observed",
    "co-applicant_race_observed",
    "applicant_sex",
    "co-applicant_sex",
    "applicant_sex_observed",
    "co-applicant_sex_observed",
    "applicant_age",
    "co-applicant_age",
    "applicant_age_above_62",
    "co-applicant_age_above_62",
    "submission_of_application",
    "initially_payable_to_institution",
    "aus-1",
    "tract_population",
    "tract_minority_population_percent",
    "ffiec_msa_md_median_family_income",
    "tract_to_msa_income_percentage",
    "tract_owner_occupied_units",
    "tract_one_to_four_family_homes",
    "tract_median_age_of_housing_units",
]
NUMERIC_FEATURE_COLUMNS = [
    "loan_amount",
    "loan_to_value_ratio",
    "loan_term",
    "intro_rate_period",
    "property_value",
    "income",
    "tract_population",
    "tract_minority_population_percent",
    "ffiec_msa_md_median_family_income",
    "tract_to_msa_income_percentage",
    "tract_owner_occupied_units",
    "tract_one_to_four_family_homes",
    "tract_median_age_of_housing_units",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/hmda/2025")
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    return parser.parse_args()


def require_raw_files(raw_dir: Path) -> None:
    missing = [name for name in RAW_FILES if not (raw_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing HMDA raw files under {raw_dir}: {missing}. "
            f"Download the official API subset with: curl -L -o "
            f"{raw_dir / RAW_FILES[0]} '{API_QUERY}'"
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


def normalize_source_missingness(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.replace([*MISSING_TOKENS, *EXTRA_MISSING_TOKENS], np.nan)


def load_source_frame(raw_dir: Path) -> pd.DataFrame:
    return pd.read_csv(raw_dir / RAW_FILES[0], low_memory=False)


def build_model_frame(source: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    working = source.copy()
    target_raw = working[TARGET]
    target_numeric = pd.to_numeric(target_raw, errors="coerce")
    target_exempt = target_raw.astype("object").astype(str).str.strip().eq("Exempt")
    target_non_numeric = target_numeric.isna()
    target_nonpositive = target_numeric.notna() & (target_numeric <= 0)
    valid_target = target_numeric.notna() & (target_numeric > 0)

    model_columns = [
        TARGET,
        *[column for column in FEATURE_COLUMNS if column in working.columns],
    ]
    model_frame = working.loc[valid_target, model_columns].copy()
    model_frame[TARGET] = target_numeric.loc[valid_target].astype(float)
    model_frame = normalize_source_missingness(model_frame)
    for column in NUMERIC_FEATURE_COLUMNS:
        if column in model_frame.columns:
            model_frame[column] = pd.to_numeric(model_frame[column], errors="coerce")

    target_filter = {
        "source_rows": int(working.shape[0]),
        "source_columns": int(working.shape[1]),
        "official_aggregation_count": SOURCE_AGGREGATION_COUNT,
        "source_count_matches_official_aggregation": bool(
            int(working.shape[0]) == SOURCE_AGGREGATION_COUNT
        ),
        "model_rows_after_target_filter": int(model_frame.shape[0]),
        "target_non_numeric_or_missing_rate_before_drop": float(
            target_non_numeric.mean()
        ),
        "target_non_numeric_or_missing_rows_before_drop": int(target_non_numeric.sum()),
        "target_exempt_rows_before_drop": int(target_exempt.sum()),
        "target_nonpositive_rate_before_drop": float(target_nonpositive.mean()),
        "target_nonpositive_rows_before_drop": int(target_nonpositive.sum()),
        "target_filter_policy": (
            "Keep only originated-loan records from the official API subset "
            "(actions_taken=1) with positive numeric interest_rate. Drop Exempt, "
            "blank/non-numeric, and zero interest-rate records for this audit."
        ),
    }
    return model_frame, target_filter


def leakage_correlation(source: pd.DataFrame) -> dict[str, Any]:
    interest = pd.to_numeric(source[TARGET], errors="coerce")
    spread = pd.to_numeric(source.get("rate_spread"), errors="coerce")
    valid = interest.notna() & (interest > 0) & spread.notna()
    return {
        "column": "rate_spread",
        "valid_pair_rows": int(valid.sum()),
        "pearson_corr_with_interest_rate": (
            float(interest[valid].corr(spread[valid])) if int(valid.sum()) > 1 else None
        ),
        "policy": (
            "Drop rate_spread because it is a pricing spread reported alongside "
            "interest_rate and is empirically near-deterministic for this target."
        ),
    }


def build_profile(
    source: pd.DataFrame,
    manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    model_frame, target_filter = build_model_frame(source)
    audit = audit_regression_frame(
        model_frame,
        target=TARGET,
        dataset_id=DATASET_ID,
    ).to_dict()
    proxy_candidates = [
        "derived_race",
        "derived_ethnicity",
        "derived_sex",
        "applicant_age",
        "applicant_age_above_62",
        "debt_to_income_ratio",
        "tract_minority_population_percent",
        "tract_to_msa_income_percentage",
    ]
    audit.update(
        {
            **target_filter,
            "target_component_drop_columns": TARGET_COMPONENT_DROP_COLUMNS,
            "post_pricing_drop_columns": POST_PRICING_DROP_COLUMNS,
            "post_outcome_drop_columns": POST_OUTCOME_DROP_COLUMNS,
            "constant_context_drop_columns": CONSTANT_CONTEXT_DROP_COLUMNS,
            "sensitive_candidates": list(
                dict.fromkeys([*audit["sensitive_candidates"], *proxy_candidates])
            ),
            "raw_files": manifest,
            "api_query": API_QUERY,
            "target_policy": target_filter["target_filter_policy"],
            "group_policy": (
                "Use HMDA derived race, ethnicity, sex, applicant age, age-above-62, "
                "county, product, purpose, and DTI bands as audit group/proxy "
                "diagnostics. Sparse levels must be pooled or reported separately "
                "before runner use."
            ),
            "missingness_policy": (
                "Treat NA, blank tokens, and Exempt as missing for audit profiling. "
                "Runner use requires train-fit imputers and an explicit policy for "
                "regulatory-exemption missingness."
            ),
            "leakage_policy": (
                "Exclude rate_spread, HOEPA status, loan-cost/points/fee fields, "
                "lender credits, purchaser type, denial reasons, and constant "
                "action/year/state context from the audit model frame."
            ),
            "split_policy": (
                "Source-review only. Any runner queue must use institution/county "
                "or temporal split sensitivity; ordinary iid splits are not enough "
                "for headline fair-lending claims."
            ),
            "license_notes": (
                "HMDA public LAR data are official US government public-use data "
                "served through FFIEC/CFPB. Raw CSV subsets remain in ignored local "
                "cache and are not committed."
            ),
        }
    )
    return {
        "dataset_id": DATASET_ID,
        "target": TARGET,
        "source": {
            "name": "HMDA 2025 Wyoming originated-loan interest-rate regression",
            "source_url": SOURCE_URL,
            "api_query": API_QUERY,
            "aggregation_query": AGGREGATION_QUERY,
            "data_browser_api_doc": DATA_BROWSER_API_DOC,
            "public_lar_schema": PUBLIC_LAR_SCHEMA,
            "cfpb_2025_release": CFPB_2025_RELEASE,
            "raw_files": manifest,
        },
        "shape": {
            "source_rows": int(source.shape[0]),
            "source_columns": int(source.shape[1]),
            "model_rows_after_target_filter": int(model_frame.shape[0]),
            "model_columns": int(model_frame.shape[1]),
        },
        "audit": audit,
        "target_summary": target_summary(model_frame[TARGET]),
        "group_profiles": [
            group_profile(model_frame, TARGET, column) for column in GROUP_COLUMNS
        ],
        "top_abs_correlations": top_abs_correlations(model_frame, TARGET),
        "leakage_checks": [leakage_correlation(source)],
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
        f"- Source URL: {source['source_url']}",
        f"- API query: {source['api_query']}",
        f"- Aggregation query: {source['aggregation_query']}",
        f"- API documentation: {source['data_browser_api_doc']}",
        f"- Public LAR schema: {source['public_lar_schema']}",
        f"- CFPB 2025 release: {source['cfpb_2025_release']}",
        f"- Target: `{profile['target']}`",
        "",
        "## Shape And Target Policy",
        "",
        f"- Source rows / columns: {shape['source_rows']} / {shape['source_columns']}",
        f"- Official aggregation count: {audit['official_aggregation_count']}",
        "- Source count matches official aggregation: "
        f"{audit['source_count_matches_official_aggregation']}",
        "- Model rows/columns after target filter: "
        f"{shape['model_rows_after_target_filter']} / {shape['model_columns']}",
        "- Target non-numeric or missing rate before drop: "
        f"{audit['target_non_numeric_or_missing_rate_before_drop']:.4f}",
        f"- Target exempt rows before drop: {audit['target_exempt_rows_before_drop']}",
        "- Target nonpositive rows before drop: "
        f"{audit['target_nonpositive_rows_before_drop']}",
        f"- Target policy: {audit['target_policy']}",
        f"- Group policy: {audit['group_policy']}",
        f"- Missingness policy: {audit['missingness_policy']}",
        f"- Leakage policy: {audit['leakage_policy']}",
        f"- Split policy: {audit['split_policy']}",
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
        "## Drop Policies",
        "",
        f"- Target descendants: {', '.join(audit['target_component_drop_columns'])}",
        "- Post-pricing/co-outcome fields: "
        f"{', '.join(audit['post_pricing_drop_columns'])}",
        f"- Post-outcome fields: {', '.join(audit['post_outcome_drop_columns'])}",
        "- Constant context fields: "
        f"{', '.join(audit['constant_context_drop_columns'])}",
        "",
        "## Raw File Manifest",
        "",
        "| File | bytes | line count |",
        "|---|---:|---:|",
    ]
    for row in source["raw_files"]:
        lines.append(f"| `{row['name']}` | {row['bytes']} | {row['line_count']} |")

    lines.extend(["", "## Leakage Checks", ""])
    for check in profile["leakage_checks"]:
        corr = check["pearson_corr_with_interest_rate"]
        corr_text = "" if corr is None else f"{corr:.4f}"
        lines.extend(
            [
                f"- `{check['column']}` valid pairs: {check['valid_pair_rows']}",
                f"- `{check['column']}` Pearson r with target: {corr_text}",
                f"- Policy: {check['policy']}",
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
    source = load_source_frame(raw_dir)
    profile = json_safe(build_profile(source, manifest))
    audit = profile["audit"]
    out_dir = Path(args.out_dir) / DATASET_ID
    atomic_write_json(out_dir / "audit.json", audit)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(audit))
    atomic_write_json(out_dir / "profile.json", profile)
    atomic_write_text(out_dir / "profile.md", render_profile_markdown(profile))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
