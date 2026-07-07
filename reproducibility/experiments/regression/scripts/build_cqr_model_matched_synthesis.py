"""Compare historical fixed-GBM CQR with model-matched CQR reruns."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.audit_cross_run_integrity import (
    canonical_ledger_rows,
    load_jsonl_rows,
    stable_params_key,
)


SCHEMA = "cpfi_regression_cqr_model_matched_synthesis_v1"
DEFAULT_MANIFEST_JSON = Path(
    "experiments/regression/reports/model_matched_cqr_rerun_plan/"
    "model_matched_cqr_rerun_manifest.json"
)
DEFAULT_OUT = Path(
    "experiments/regression/reports/model_matched_cqr_rerun_plan/"
    "cqr_fixed_vs_model_matched_synthesis.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument(
        "--manifest-json",
        default=str(DEFAULT_MANIFEST_JSON),
        help="Model-matched CQR rerun manifest JSON.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def metric_mean(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [as_float(row.get(field)) for row in rows]
    clean = [value for value in values if value is not None]
    return mean(clean) if clean else None


def source_ledger_from_config(root: Path, source_config: str) -> str | None:
    path = resolve(root, source_config)
    if not path.exists():
        return None
    config = read_yaml(path)
    logging = config.get("logging") or {}
    ledger = logging.get("ledger")
    return str(ledger) if ledger else None


def completed_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        row
        for row in canonical_ledger_rows(load_jsonl_rows(path))
        if str(row.get("status")) == "completed"
    ]


def collect_variant_rows(root: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    seen_sources: set[tuple[str, str]] = set()
    for config_row in manifest.get("generated_configs") or []:
        source_config = str(config_row.get("source_config"))
        source_ledger = source_ledger_from_config(root, source_config)
        generated_ledger = str(config_row.get("ledger"))
        source_pairs = [
            ("fixed_gbm_cqr", source_config, source_ledger, "cqr"),
            (
                "model_matched_cqr",
                str(config_row.get("generated_config")),
                generated_ledger,
                "cqr_model_matched",
            ),
        ]
        for variant, config_path, ledger, cp_method in source_pairs:
            if not ledger:
                sources.append(
                    {
                        "variant": variant,
                        "config": config_path,
                        "ledger": None,
                        "completed_rows": 0,
                        "status": "missing_ledger_reference",
                    }
                )
                continue
            source_key = (variant, ledger)
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            ledger_path = resolve(root, ledger)
            ledger_rows = [
                row
                for row in completed_rows(ledger_path)
                if str(row.get("cp_method")) == cp_method
            ]
            sources.append(
                {
                    "variant": variant,
                    "config": config_path,
                    "ledger": rel(ledger_path, root),
                    "completed_rows": len(ledger_rows),
                    "status": "present" if ledger_path.exists() else "missing_file",
                }
            )
            for row in ledger_rows:
                out = dict(row)
                out["cqr_variant"] = variant
                out["source_config"] = config_path
                out["ledger_path"] = rel(ledger_path, root)
                rows.append(out)
    return rows, sources


def cell_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("dataset_id")),
        str(row.get("alpha")),
        str(row.get("model_family")),
        str(row.get("cqr_variant")),
    )


def paired_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("dataset_id")),
        str(row.get("alpha")),
        str(row.get("model_family")),
    )


def summarize_cells(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[cell_key(row)].append(row)
    cells = []
    for (dataset_id, alpha, model_family, variant), group_rows in sorted(grouped.items()):
        target = None
        try:
            target = 1.0 - float(alpha)
        except ValueError:
            pass
        coverage_mean = metric_mean(group_rows, "coverage")
        coverage_margin = (
            None if target is None or coverage_mean is None else coverage_mean - target
        )
        cells.append(
            {
                "dataset_id": dataset_id,
                "alpha": alpha,
                "model_family": model_family,
                "cqr_variant": variant,
                "row_count": len(group_rows),
                "model_count": len(
                    {
                        (
                            str(row.get("model_id")),
                            stable_params_key(row.get("model_params")),
                        )
                        for row in group_rows
                    }
                ),
                "seed_count": len({str(row.get("seed")) for row in group_rows}),
                "target_coverage": target,
                "coverage_mean": coverage_mean,
                "coverage_margin_mean": coverage_margin,
                "coverage_eligible": (
                    coverage_margin is not None and coverage_margin >= 0.0
                ),
                "mean_width_mean": metric_mean(group_rows, "mean_width"),
                "interval_score_mean": metric_mean(group_rows, "interval_score"),
            }
        )
    return cells


def paired_deltas(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for cell in cells:
        by_key[
            (cell["dataset_id"], cell["alpha"], cell["model_family"])
        ][cell["cqr_variant"]] = cell
    deltas = []
    for (dataset_id, alpha, model_family), variants in sorted(by_key.items()):
        fixed = variants.get("fixed_gbm_cqr")
        matched = variants.get("model_matched_cqr")
        if not fixed or not matched:
            continue
        deltas.append(
            {
                "dataset_id": dataset_id,
                "alpha": alpha,
                "model_family": model_family,
                "fixed_row_count": fixed["row_count"],
                "model_matched_row_count": matched["row_count"],
                "coverage_delta_model_matched_minus_fixed": (
                    None
                    if fixed["coverage_mean"] is None
                    or matched["coverage_mean"] is None
                    else matched["coverage_mean"] - fixed["coverage_mean"]
                ),
                "mean_width_delta_model_matched_minus_fixed": (
                    None
                    if fixed["mean_width_mean"] is None
                    or matched["mean_width_mean"] is None
                    else matched["mean_width_mean"] - fixed["mean_width_mean"]
                ),
                "interval_score_delta_model_matched_minus_fixed": (
                    None
                    if fixed["interval_score_mean"] is None
                    or matched["interval_score_mean"] is None
                    else matched["interval_score_mean"] - fixed["interval_score_mean"]
                ),
            }
        )
    return deltas


def selected_counts(cells: list[dict[str, Any]]) -> dict[str, Any]:
    by_group: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        by_group[(cell["dataset_id"], cell["alpha"], cell["model_family"])].append(cell)
    counts: Counter[str] = Counter()
    selected_rows = []
    for key, group_cells in sorted(by_group.items()):
        eligible = [
            cell
            for cell in group_cells
            if cell.get("coverage_eligible")
            and cell.get("interval_score_mean") is not None
        ]
        if not eligible:
            counts["no_coverage_eligible_variant"] += 1
            continue
        selected = sorted(
            eligible,
            key=lambda cell: (
                float(cell["interval_score_mean"]),
                float(cell["mean_width_mean"] or float("inf")),
                str(cell["cqr_variant"]),
            ),
        )[0]
        counts[str(selected["cqr_variant"])] += 1
        selected_rows.append(
            {
                "dataset_id": key[0],
                "alpha": key[1],
                "model_family": key[2],
                "selected_variant": selected["cqr_variant"],
                "selection_rule": "coverage_eligible_min_interval_score",
                "interval_score_mean": selected["interval_score_mean"],
                "coverage_mean": selected["coverage_mean"],
            }
        )
    return {
        "counts": {key: int(value) for key, value in sorted(counts.items())},
        "rows": selected_rows,
    }


def build_payload(root: Path, manifest_json: Path) -> dict[str, Any]:
    manifest = read_json(manifest_json)
    rows, source_ledgers = collect_variant_rows(root, manifest)
    cells = summarize_cells(rows)
    deltas = paired_deltas(cells)
    selections = selected_counts(cells)
    variant_counts = Counter(str(row.get("cqr_variant")) for row in rows)
    model_matched_rows = int(variant_counts.get("model_matched_cqr", 0))
    fixed_rows = int(variant_counts.get("fixed_gbm_cqr", 0))
    status = (
        "pending_model_matched_rerun_rows"
        if model_matched_rows == 0
        else "descriptive_fixed_vs_model_matched_cqr_synthesis"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "model_matched_cqr_rerun_manifest": rel(manifest_json, root),
        },
        "summary": {
            "status": status,
            "fixed_gbm_cqr_completed_rows": fixed_rows,
            "model_matched_cqr_completed_rows": model_matched_rows,
            "cell_count": len(cells),
            "paired_cell_count": len(deltas),
            "method_boundary": "pipeline_level_descriptive_signal_only",
            "can_support_method_winner_claim": False,
            "coverage_eligible_interval_score_selected_counts": selections["counts"],
        },
        "source_ledgers": source_ledgers,
        "cell_summaries": cells,
        "paired_deltas": deltas,
        "coverage_eligible_interval_score_selected_cells": selections["rows"],
        "claim_boundaries": [
            "This synthesis compares historical fixed-GBM CQR and model-matched CQR as pipeline-level evidence only.",
            "It does not select a universal best conformal method and does not authorize production guidance.",
            "Coverage-eligible interval-score selections are descriptive cells, not inferential superiority claims.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Fixed-GBM CQR vs Model-Matched CQR Synthesis",
        "",
        f"- Status: `{summary['status']}`",
        f"- Fixed-GBM CQR completed rows: {summary['fixed_gbm_cqr_completed_rows']}",
        f"- Model-matched CQR completed rows: {summary['model_matched_cqr_completed_rows']}",
        f"- Paired dataset-alpha-family cells: {summary['paired_cell_count']}",
        "- Boundary: pipeline-level descriptive signal only; no method winner claim.",
        "",
        "## Selected Cell Counts",
        "",
        "Selection rule: coverage-eligible variant with the lower mean interval score.",
        "",
        "```json",
        json.dumps(
            summary["coverage_eligible_interval_score_selected_counts"],
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        "## Claim Boundaries",
        "",
        *[f"- {item}" for item in payload["claim_boundaries"]],
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    manifest_json = resolve(root, args.manifest_json)
    out_path = resolve(root, args.out)
    payload = build_payload(root, manifest_json)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["status"],
                "fixed_gbm_cqr_completed_rows": payload["summary"][
                    "fixed_gbm_cqr_completed_rows"
                ],
                "model_matched_cqr_completed_rows": payload["summary"][
                    "model_matched_cqr_completed_rows"
                ],
                "paired_cell_count": payload["summary"]["paired_cell_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
