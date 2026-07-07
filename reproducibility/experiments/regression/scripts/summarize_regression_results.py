"""Summarize regression pilot ledgers into compact reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


METRIC_COLUMNS = [
    "coverage_error_abs",
    "coverage",
    "coverage_gap",
    "mean_width",
    "normalized_mean_width",
    "interval_score",
    "lower_miss_rate",
    "upper_miss_rate",
    "width_gap",
    "fit_seconds",
    "interval_seconds",
]

STATUS_RANK = {
    "skipped_completed": 0,
    "skipped_method": 1,
    "failed": 2,
    "completed": 3,
}


def _stable_key_part(value) -> str:
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _stable_params_key(value) -> str:
    text = _stable_key_part(value)
    return "{}" if text == "" else text


def semantic_run_key(row: pd.Series) -> tuple[str, ...] | None:
    """Return a stable run key for schema-refresh rows with new run ids."""

    required = ["dataset_id", "model_id", "cp_method", "alpha", "seed"]
    if any(_stable_key_part(row.get(field)) == "" for field in required):
        return None
    return (
        _stable_key_part(row.get("dataset_id")),
        _stable_key_part(row.get("model_family")),
        _stable_key_part(row.get("model_id")),
        _stable_params_key(row.get("model_params")),
        _stable_key_part(row.get("seed")),
        _stable_key_part(row.get("cp_method")),
        _stable_params_key(row.get("cp_method_params")),
        _stable_key_part(row.get("alpha")),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ledger",
        default="experiments/regression/results/ledger.jsonl",
        help="Input JSONL ledger.",
    )
    parser.add_argument(
        "--out-dir",
        default="experiments/regression/reports",
        help="Output directory for summary artifacts.",
    )
    return parser.parse_args()


def load_ledger(path: Path) -> pd.DataFrame:
    rows = []
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def canonical_ledger(df: pd.DataFrame) -> pd.DataFrame:
    """Return one authoritative row per run_id, preferring completed records."""

    if df.empty or "run_id" not in df.columns:
        return df.copy()

    work = df.copy()
    work["_ledger_order"] = range(len(work))
    status = work.get("status", pd.Series(index=work.index, dtype=object)).fillna("missing")
    work["_status_rank"] = status.map(STATUS_RANK).fillna(1)
    work = work.sort_values(["run_id", "_status_rank", "_ledger_order"])
    canonical = work.drop_duplicates(subset=["run_id"], keep="last").copy()
    canonical["_semantic_run_key"] = [
        semantic_run_key(row) for _, row in canonical.iterrows()
    ]
    with_semantic_key = canonical[canonical["_semantic_run_key"].notna()].copy()
    without_semantic_key = canonical[canonical["_semantic_run_key"].isna()].copy()
    if not with_semantic_key.empty:
        with_semantic_key = with_semantic_key.sort_values(
            ["_semantic_run_key", "_status_rank", "_ledger_order"]
        ).drop_duplicates(subset=["_semantic_run_key"], keep="last")
        canonical = pd.concat(
            [without_semantic_key, with_semantic_key],
            ignore_index=True,
        ).sort_values("_ledger_order")
    return canonical.drop(
        columns=["_ledger_order", "_status_rank", "_semantic_run_key"]
    ).reset_index(drop=True)


def _counts(series: pd.Series) -> dict:
    return {
        str(key): int(value)
        for key, value in series.fillna("missing").value_counts().sort_index().items()
    }


def canonical_model_params(value) -> str:
    """Return a stable grouping key for model hyperparameters."""

    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if value is None:
        return "{}"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "{}"
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"), default=str)
    try:
        if pd.isna(value):
            return "{}"
    except (TypeError, ValueError):
        pass
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    df = canonical_ledger(df)
    completed = df[df["status"] == "completed"].copy()
    if completed.empty:
        return completed
    completed["coverage_error_abs"] = (
        completed["coverage"] - (1.0 - completed["alpha"])
    ).abs()
    if "model_params" in completed.columns:
        completed["model_params_key"] = completed["model_params"].map(canonical_model_params)
    else:
        completed["model_params_key"] = "{}"
    group_cols = ["dataset_id", "model_id", "model_params_key", "cp_method", "alpha"]
    metric_cols = [col for col in METRIC_COLUMNS if col in completed.columns]
    summary = completed.groupby(group_cols, dropna=False)[metric_cols].agg(["mean", "std", "count"])
    summary.columns = ["_".join(col).strip("_") for col in summary.columns]
    return summary.reset_index().sort_values(
        [
            "dataset_id",
            "model_id",
            "model_params_key",
            "alpha",
            "coverage_gap_mean",
            "coverage_error_abs_mean",
            "mean_width_mean",
        ],
        na_position="last",
    )


def summarize_ledger_metadata(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "ledger_rows": 0,
            "unique_run_rows": 0,
            "status_counts": {},
            "raw_status_counts": {},
            "dataset_counts": {},
            "raw_dataset_counts": {},
        }
    canonical = canonical_ledger(df)
    return {
        "ledger_rows": int(len(df)),
        "unique_run_rows": int(len(canonical)),
        "status_counts": _counts(canonical.get("status", pd.Series(dtype=object))),
        "raw_status_counts": _counts(df.get("status", pd.Series(dtype=object))),
        "dataset_counts": _counts(canonical.get("dataset_id", pd.Series(dtype=object))),
        "raw_dataset_counts": _counts(df.get("dataset_id", pd.Series(dtype=object))),
    }


def candidate_frontier_rows(summary: pd.DataFrame, per_group: int = 5) -> pd.DataFrame:
    if summary.empty:
        return summary
    sort_cols = [
        col
        for col in [
            "dataset_id",
            "alpha",
            "coverage_gap_mean",
            "coverage_error_abs_mean",
            "interval_score_mean",
            "mean_width_mean",
        ]
        if col in summary.columns
    ]
    ranked = summary.sort_values(sort_cols, na_position="last")
    return ranked.groupby(["dataset_id", "alpha"], dropna=False).head(per_group)


def render_markdown(df: pd.DataFrame, summary: pd.DataFrame) -> str:
    metadata = summarize_ledger_metadata(df)
    lines = [
        "# Regression Pilot Summary",
        "",
        f"- Ledger rows: {metadata['ledger_rows']}",
        f"- Unique run rows: {metadata['unique_run_rows']}",
        f"- Status counts: `{metadata['status_counts']}`",
        f"- Raw status counts: `{metadata['raw_status_counts']}`",
        f"- Dataset counts: `{metadata['dataset_counts']}`",
        "",
    ]
    if summary.empty:
        lines.append("No completed runs found.")
        return "\n".join(lines) + "\n"

    display_cols = [
        "dataset_id",
        "model_id",
        "model_params_key",
        "cp_method",
        "alpha",
        "coverage_mean",
        "coverage_error_abs_mean",
        "coverage_gap_mean",
        "mean_width_mean",
        "width_gap_mean",
        "lower_miss_rate_mean",
        "upper_miss_rate_mean",
        "interval_score_mean",
        "coverage_count",
    ]
    display_cols = [col for col in display_cols if col in summary.columns]
    lines.extend([
        "## Candidate Frontier By Dataset And Alpha",
        "",
        "Rows below are sorted by group coverage gap, nominal coverage error, "
        "interval score, and mean width. They are not method recommendations; "
        "check nominal coverage, group sparsity, and dataset policy gates before "
        "interpreting them.",
        "",
    ])
    lines.append(
        candidate_frontier_rows(summary, per_group=5)[display_cols].to_markdown(
            index=False
        )
    )
    lines.extend(["", "## Full Summary Preview", ""])
    lines.append(summary[display_cols].head(30).to_markdown(index=False))
    lines.append("")
    return "\n".join(lines)


def summary_payload(
    ledger_path: Path,
    metadata: dict,
    summary: pd.DataFrame,
    frontier: pd.DataFrame,
) -> dict:
    return {
        "ledger": str(ledger_path),
        "metadata": metadata,
        "rows": json.loads(summary.to_json(orient="records")),
        "candidate_frontier_rows": json.loads(frontier.to_json(orient="records")),
        "candidate_frontier_note": (
            "Rows are sorted diagnostics for triage, not method recommendations."
        ),
    }


def main() -> None:
    args = parse_args()
    ledger_path = Path(args.ledger)
    out_dir = Path(args.out_dir)
    df = load_ledger(ledger_path)
    summary = summarize(df)
    frontier = candidate_frontier_rows(summary, per_group=5)
    metadata = summarize_ledger_metadata(df)

    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        out_dir / "pilot_summary.json",
        summary_payload(ledger_path, metadata, summary, frontier),
    )
    atomic_write_text(out_dir / "pilot_summary.md", render_markdown(df, summary))
    print(json.dumps({"status": "ok", "rows": len(summary)}))


if __name__ == "__main__":
    main()
