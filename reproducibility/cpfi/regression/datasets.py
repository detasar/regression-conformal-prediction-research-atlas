"""Dataset metadata and audit helpers for regression experiments."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


SENSITIVE_NAME_HINTS = (
    "age",
    "sex",
    "gender",
    "race",
    "ethnic",
    "black",
    "white",
    "hispanic",
    "asian",
    "marital",
    "native",
    "foreign",
    "disability",
    "income",
)

MISSING_TOKENS = ("?", "", "NA", "N/A", "nan", "NaN", "None", "null")

_EXACT_SENSITIVE_TOKENS = {
    "asian",
    "black",
    "ethnic",
    "ethnicity",
    "foreign",
    "gender",
    "hispanic",
    "marital",
    "native",
    "race",
    "white",
}

_DEMOGRAPHIC_RATE_TERMS = ("asian", "black", "hisp", "white")
_DEMOGRAPHIC_RATE_MARKERS = ("percap", "polic", "pct")


def sensitive_name_matches(name: str) -> bool:
    """Return whether a field name plausibly denotes a sensitive attribute.

    Short strings such as ``age`` and ``sex`` are matched as tokens to avoid
    false positives like ``average`` while still catching ACS-style codes.
    """

    normalized = str(name).lower().replace("-", "_").replace(" ", "_")
    tokens = [token for token in re.split(r"[^a-z0-9]+", normalized) if token]
    compact = "".join(tokens)

    if any(token in _EXACT_SENSITIVE_TOKENS for token in tokens):
        return True
    if compact in {"rac1p", "rac2p"}:
        return True
    if compact.startswith("racepct"):
        return True
    if compact.startswith("race") and any(
        marker in compact for marker in _DEMOGRAPHIC_RATE_MARKERS
    ):
        return True
    if any(term in compact for term in _DEMOGRAPHIC_RATE_TERMS) and any(
        marker in compact for marker in _DEMOGRAPHIC_RATE_MARKERS
    ):
        return True
    if "age" in tokens or compact in {"agep", "age"}:
        return True
    if "sex" in tokens or compact in {"sex", "sexp"}:
        return True
    if "disability" in tokens or compact == "disabled":
        return True
    if "income" in compact:
        return True
    return False


@dataclass(frozen=True)
class RegressionDatasetSpec:
    """Metadata for a candidate regression dataset."""

    dataset_id: str
    name: str
    source: str
    source_url: str
    target: str
    sensitive_candidates: List[str] = field(default_factory=list)
    task_type: str = "regression"
    priority: str = "candidate"
    license_notes: str = "manual_review_required"
    fairness_relevance: str = ""
    leakage_risks: List[str] = field(default_factory=list)
    status: str = "queued_manual_audit"
    notes: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass(frozen=True)
class DatasetAudit:
    """Data quality profile generated before model training."""

    dataset_id: str
    n_rows: int
    n_columns: int
    target: str
    target_missing_rate: float
    target_mean: float
    target_std: float
    target_min: float
    target_max: float
    target_skew: float
    target_quantiles: Dict[str, float]
    duplicate_row_rate: float
    numeric_columns: List[str]
    categorical_columns: List[str]
    missing_columns: Dict[str, float]
    high_missing_columns: Dict[str, float]
    constant_columns: List[str]
    sensitive_candidates: List[str]
    recommended_actions: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


def infer_sensitive_candidates(df: pd.DataFrame) -> List[str]:
    """Find columns that look like protected or fairness-relevant attributes."""

    candidates = []
    for col in df.columns:
        if sensitive_name_matches(str(col)):
            candidates.append(str(col))
    return candidates


def audit_regression_frame(
    df: pd.DataFrame,
    target: str,
    dataset_id: str,
    missing_threshold: float = 0.95,
) -> DatasetAudit:
    """Profile a raw regression frame before preprocessing decisions."""

    if target not in df.columns:
        raise ValueError(f"target column {target!r} not found")

    df_missing = df.replace(list(MISSING_TOKENS), np.nan)
    y = pd.to_numeric(df_missing[target], errors="coerce")
    feature_df = df_missing.drop(columns=[target])
    numeric_columns = feature_df.select_dtypes(include=[np.number]).columns.astype(str).tolist()
    categorical_columns = feature_df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.astype(str).tolist()
    missing_rates = df_missing.isna().mean().sort_values(ascending=False)
    missing_columns = {
        str(col): float(rate)
        for col, rate in missing_rates.items()
        if float(rate) > 0
    }
    high_missing_columns = {
        str(col): float(rate)
        for col, rate in missing_rates.items()
        if float(rate) > missing_threshold
    }
    constant_columns = [
        str(col)
        for col in feature_df.columns
        if feature_df[col].nunique(dropna=True) <= 1
    ]
    sensitive_candidates = infer_sensitive_candidates(feature_df)
    quantiles = y.quantile([0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99])

    recommended_actions = []
    if y.isna().any():
        recommended_actions.append("drop_rows_with_missing_target")
    duplicate_row_rate = float(df_missing.duplicated().mean())
    target_skew = float(y.skew(skipna=True))

    if high_missing_columns:
        recommended_actions.append("drop_or_document_high_missing_columns")
    elif missing_columns:
        recommended_actions.append("impute_or_document_missing_columns")
    if constant_columns:
        recommended_actions.append("drop_constant_columns")
    if sensitive_candidates:
        recommended_actions.append("audit_sensitive_columns_before_drop_policy")
    if duplicate_row_rate > 0.05:
        recommended_actions.append("deduplicate_or_document_repeated_rows")
    if abs(target_skew) > 1:
        recommended_actions.append("evaluate_target_transform_or_stratified_bins")

    return DatasetAudit(
        dataset_id=dataset_id,
        n_rows=int(len(df)),
        n_columns=int(df.shape[1]),
        target=target,
        target_missing_rate=float(y.isna().mean()),
        target_mean=float(y.mean(skipna=True)),
        target_std=float(y.std(skipna=True)),
        target_min=float(y.min(skipna=True)),
        target_max=float(y.max(skipna=True)),
        target_skew=target_skew,
        target_quantiles={str(q): float(v) for q, v in quantiles.items()},
        duplicate_row_rate=duplicate_row_rate,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        missing_columns=missing_columns,
        high_missing_columns=high_missing_columns,
        constant_columns=constant_columns,
        sensitive_candidates=sensitive_candidates,
        recommended_actions=recommended_actions,
    )


def render_audit_markdown(audit: Dict) -> str:
    """Render a compact human-readable dataset audit."""

    lines = [
        f"# Dataset Audit: {audit['dataset_id']}",
        "",
        f"- Rows: {audit['n_rows']}",
        f"- Columns: {audit['n_columns']}",
        f"- Target: `{audit['target']}`",
        f"- Target missing rate: {audit['target_missing_rate']:.4f}",
        f"- Target mean/std: {audit['target_mean']:.4f} / {audit['target_std']:.4f}",
        f"- Target skew: {audit['target_skew']:.4f}",
        f"- Target range: {audit['target_min']:.4f} to {audit['target_max']:.4f}",
        f"- Duplicate row rate: {audit['duplicate_row_rate']:.4f}",
        f"- Numeric columns: {len(audit['numeric_columns'])}",
        f"- Categorical columns: {len(audit['categorical_columns'])}",
        "",
        "## Target Quantiles",
        "",
    ]
    lines.extend(
        f"- p{float(q) * 100:.0f}: {value:.4f}"
        for q, value in audit["target_quantiles"].items()
    )
    lines.extend(["", "## Sensitive Candidates", ""])
    lines.extend(f"- `{col}`" for col in audit["sensitive_candidates"] or ["none_detected"])
    lines.extend(["", "## Recommended Actions", ""])
    lines.extend(f"- {action}" for action in audit["recommended_actions"] or ["none"])
    lines.extend(["", "## Missing Columns", ""])
    if audit["missing_columns"]:
        lines.extend(
            f"- `{col}`: {rate:.4f}"
            for col, rate in audit["missing_columns"].items()
        )
    else:
        lines.append("- none")
    lines.extend(["", "## High Missing Columns", ""])
    if audit["high_missing_columns"]:
        lines.extend(
            f"- `{col}`: {rate:.4f}"
            for col, rate in audit["high_missing_columns"].items()
        )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def load_openml_regression_frame(openml_id: int, target: Optional[str] = None) -> pd.DataFrame:
    """Load an OpenML dataset as a DataFrame with target included.

    OpenML is imported lazily so package import stays lightweight.
    """

    import openml

    dataset = openml.datasets.get_dataset(openml_id)
    target_name = target or dataset.default_target_attribute
    X, y, _, _ = dataset.get_data(target=target_name, dataset_format="dataframe")
    df = X.copy()
    df[target_name] = y
    return df
