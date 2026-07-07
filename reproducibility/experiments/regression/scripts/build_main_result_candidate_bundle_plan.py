"""Build the next main-result candidate bundle work queue.

The current paper gates explicitly say that no robustness bundle can be
promoted to a main-result row. This builder materializes the next executable
step: fresh, resumable candidate-bundle configs derived from the completed
post-selection validation surface. The output is a work queue and closure plan,
not a final method/model/dataset result.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.build_method_selection_alpha_expansion_batch import (
    alpha_float,
    alpha_sort_key,
    canonical_alpha,
    model_grid_size,
    read_json,
    read_yaml,
    rel,
    slugify,
)


SCHEMA = "cpfi_regression_main_result_candidate_bundle_plan_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "main_result_candidate_bundle_plan.json"
DEFAULT_CONFIG_DIR = Path("experiments/regression/configs")
DEFAULT_RESULTS_ROOT = Path("experiments/regression/results")
DEFAULT_BATCH_ID = "main_result_candidate_bundle_v1"
DEFAULT_MAIN_RESULT_SEEDS = (401, 503, 701)
DEFAULT_ALPHA_GRID = ("0.01", "0.05", "0.1", "0.15", "0.2")

VALIDATION_RESULTS = REPORT_DIR / "method_selection_post_selection_validation_results.json"
VALIDATION_BATCH = REPORT_DIR / "method_selection_post_selection_validation_batch.json"
DATASET_FINAL_GATE_POST_SELECTION_VALIDATION_BRIDGE_RESULTS = (
    REPORT_DIR / "dataset_final_gate_post_selection_validation_bridge_results.json"
)
DATASET_FINAL_GATE = REPORT_DIR / "dataset_specific_final_gate_audit.json"
SELECTION_RECORD = Path("experiments/regression/manuscript/selection_multiplicity_evidence_record.json")
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")

CLAIM_BOUNDARIES = [
    "This artifact is an executable main-result candidate work queue; it does not promote a main-result row.",
    "CQR is carried forward only as the diagnostic primary candidate from the completed validation evidence.",
    "CV+ and Mondrian_abs remain challenger controls so the multiplicity record stays explicit.",
    "Generated configs use fresh seeds disjoint from selection and validation seeds.",
    "A candidate bundle can be promoted only after the new runs execute and split, leakage, endpoint, bounded-support, fairness/population, final-selection, manifest, and KG gates pass.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument(
        "--config-dir",
        default=str(DEFAULT_CONFIG_DIR),
        help="Directory for generated YAML configs.",
    )
    parser.add_argument(
        "--results-root",
        default=str(DEFAULT_RESULTS_ROOT),
        help="Root directory for generated run ledgers and checkpoints.",
    )
    parser.add_argument("--batch-id", default=DEFAULT_BATCH_ID)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def generated_config_path(config_dir: Path, dataset_id: str) -> Path:
    return config_dir / f"main_result_candidate_bundle_{slugify(dataset_id)}.yaml"


def result_slug(dataset_id: str) -> str:
    return f"main_result_candidate_bundle_{slugify(dataset_id)}"


def validation_source_seed_values(config: dict[str, Any]) -> list[int]:
    values: list[int] = []
    for key in ("random_seeds",):
        for value in config.get(key) or []:
            if value not in values:
                values.append(value)
    provenance = config.get("post_selection_validation_provenance") or {}
    for key in ("source_selection_seeds", "validation_seeds"):
        for value in provenance.get(key) or []:
            if value not in values:
                values.append(value)
    return values


def diagnostic_winners_by_dataset(validation_results: dict[str, Any]) -> dict[str, Counter[str]]:
    diagnostic = validation_results.get("diagnostic_selection") or {}
    explicit = diagnostic.get("diagnostic_winners_by_dataset") or {}
    if explicit:
        return {
            str(dataset_id): Counter(
                {str(method): int(count) for method, count in counts.items()}
            )
            for dataset_id, counts in explicit.items()
            if isinstance(counts, dict)
        }
    counters: dict[str, Counter[str]] = {}
    for row in diagnostic.get("per_cell") or []:
        dataset_id = str(row.get("dataset_id") or "").strip()
        winner = str(row.get("diagnostic_winner") or "").strip()
        if dataset_id and winner:
            counters.setdefault(dataset_id, Counter())[winner] += 1
    return counters


def ordered_unique(values: list[Any]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in ordered:
            ordered.append(item)
    return ordered


def merge_winner_counts(
    *validation_payloads: dict[str, Any],
) -> dict[str, Counter[str]]:
    merged: dict[str, Counter[str]] = {}
    for payload in validation_payloads:
        for dataset_id, counts in diagnostic_winners_by_dataset(payload).items():
            merged.setdefault(dataset_id, Counter()).update(counts)
    return merged


def combined_source_rows(
    validation_results: dict[str, Any],
    bridge_results: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    seen_dataset_ids: set[str] = set()
    counts = {
        "standard_dataset_count": 0,
        "bridge_dataset_count": 0,
        "bridge_duplicate_dataset_count": 0,
    }

    for source_row in validation_results.get("dataset_rows") or []:
        if not isinstance(source_row, dict) or not source_row.get("dataset_id"):
            continue
        dataset_id = str(source_row["dataset_id"])
        row = dict(source_row)
        row["source_validation_kind"] = "standard_post_selection_validation"
        rows.append(row)
        seen_dataset_ids.add(dataset_id)
        counts["standard_dataset_count"] += 1

    for source_row in bridge_results.get("dataset_rows") or []:
        if not isinstance(source_row, dict) or not source_row.get("dataset_id"):
            continue
        dataset_id = str(source_row["dataset_id"])
        if dataset_id in seen_dataset_ids:
            counts["bridge_duplicate_dataset_count"] += 1
            continue
        row = dict(source_row)
        row["source_validation_kind"] = "dataset_final_gate_bridge_post_selection_validation"
        rows.append(row)
        seen_dataset_ids.add(dataset_id)
        counts["bridge_dataset_count"] += 1

    return rows, counts


def priority_for_dataset(
    counts: Counter[str], primary_method: str, alpha_count: int
) -> str:
    primary_count = int(counts.get(primary_method) or 0)
    runner_up = max((count for method, count in counts.items() if method != primary_method), default=0)
    if primary_count >= max(1, alpha_count - 1) and primary_count > runner_up:
        return "candidate_primary_consistent"
    if primary_count > runner_up:
        return "candidate_primary_supported_with_challenger_controls"
    return "candidate_primary_ambiguous_challenger_controls_required"


def build_generated_config(
    *,
    batch_id: str,
    source_row: dict[str, Any],
    source_config: dict[str, Any],
    out_config_path: Path,
    results_root: Path,
    root: Path,
    seeds: list[int],
    alphas: list[str],
    methods: list[str],
    primary_method: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    dataset_id = str(source_row["dataset_id"])
    experiment_id = f"regression_main_result_candidate_bundle_{slugify(dataset_id)}_v1"
    result_dir = results_root / result_slug(dataset_id)
    source_seeds = validation_source_seed_values(source_config)
    seed_overlap = sorted(set(source_seeds).intersection(seeds))
    quality_controls = dict(source_config.get("quality_controls") or {})
    quality_controls.update(
        {
            "main_result_candidate_bundle_batch": True,
            "candidate_main_result_work_queue_only": True,
            "no_main_result_promotion": True,
            "no_final_method_selection_claim": True,
            "diagnostic_primary_method_carried_forward": primary_method,
            "challenger_methods_retained_for_multiplicity": True,
            "main_result_candidate_seeds_independent_from_selection_and_validation": not seed_overlap,
            "fixed_common_alpha_grid_for_main_result_candidate": True,
            "requires_completed_candidate_runs_before_manifest_promotion": True,
            "requires_dataset_specific_final_gate_before_claim": True,
            "requires_endpoint_bounded_support_gate_before_claim": True,
            "requires_fairness_population_gate_before_claim": True,
            "requires_validated_venn_abers_gate_before_claim": True,
            "forbid_final_model_selection_claims": True,
            "forbid_final_method_selection_claims": True,
            "forbid_main_result_claims_until_all_paper_gates_pass": True,
            "forbid_validated_venn_abers_regression_claims": True,
            "forbid_fairness_population_claims_without_population_gate": True,
            "forbid_bounded_support_claims_without_endpoint_gate": True,
        }
    )
    config = {
        "experiment_id": experiment_id,
        "purpose": (
            "Fresh-seed main-result candidate bundle for "
            f"{dataset_id}. This config reuses the audited post-selection "
            "validation preprocessing/split/model scaffold, carries CQR only "
            "as a diagnostic primary candidate, retains challenger methods for "
            "multiplicity, and forbids any final main-result claim until the "
            "candidate batch is executed and all paper gates pass."
        ),
        "random_seeds": seeds,
        "alphas": [alpha_float(alpha) for alpha in alphas],
        "target_transform": source_config.get("target_transform", "identity"),
        "splits": deepcopy(source_config.get("splits") or {}),
        "conformal": deepcopy(source_config.get("conformal") or {}),
        "datasets": [dataset_id],
        "models": deepcopy(source_config.get("models") or []),
        "cp_methods": methods,
        "quality_controls": quality_controls,
        "main_result_candidate_provenance": {
            "schema": SCHEMA,
            "batch_id": batch_id,
            "source_validation_kind": source_row.get("source_validation_kind"),
            "source_validation_config": source_row.get("config_path"),
            "source_validation_experiment_id": source_row.get("experiment_id"),
            "source_validation_ledger": source_row.get("ledger"),
            "source_validation_pilot_summary": source_row.get("pilot_summary"),
            "source_selection_and_validation_seeds": source_seeds,
            "main_result_candidate_seeds": seeds,
            "seed_overlap": seed_overlap,
            "primary_candidate_method": primary_method,
            "claim_boundary": "candidate_work_queue_only_no_main_result_promotion",
        },
        "logging": {
            "ledger": rel(result_dir / "ledger.jsonl", root),
            "checkpoint_root": rel(result_dir / "checkpoints", root),
            "prediction_cache_root": rel(result_dir / "checkpoints/predictions", root),
        },
    }
    expected_runs = (
        len(seeds)
        * len(alphas)
        * sum(model_grid_size(model) for model in config["models"])
        * len(methods)
    )
    manifest_row = {
        "dataset_id": dataset_id,
        "planned_bundle_id": f"main_result_candidate_{slugify(dataset_id)}",
        "config_path": rel(out_config_path, root),
        "experiment_id": experiment_id,
        "source_validation_kind": source_row.get("source_validation_kind"),
        "source_validation_config": source_row.get("config_path"),
        "source_validation_experiment_id": source_row.get("experiment_id"),
        "source_validation_ledger": source_row.get("ledger"),
        "source_validation_pilot_summary": source_row.get("pilot_summary"),
        "source_seed_values": source_seeds,
        "main_result_candidate_seeds": seeds,
        "seed_overlap": seed_overlap,
        "target_alphas": alphas,
        "cp_methods": methods,
        "primary_candidate_method": primary_method,
        "challenger_methods": [method for method in methods if method != primary_method],
        "model_count": len(config["models"]),
        "model_grid_size_total": sum(model_grid_size(model) for model in config["models"]),
        "expected_atomic_run_count": expected_runs,
        "ledger": config["logging"]["ledger"],
        "checkpoint_root": config["logging"]["checkpoint_root"],
        "prediction_cache_root": config["logging"]["prediction_cache_root"],
        "runner_command": (
            "PYTHONPATH=. python "
            f"experiments/regression/scripts/run_regression_pilot.py --config {rel(out_config_path, root)}"
        ),
        "promotion_status": "queued_candidate_not_main_result",
        "required_post_run_artifacts": [
            "completed ledger",
            "pilot summary",
            "split audit",
            "feature-leakage audit",
            "endpoint audit",
            "publication-readiness manifest",
            "claim-register refresh",
            "bundle eligibility refresh",
            "paper-readiness refresh",
            "KG refresh",
        ],
    }
    return config, manifest_row


def source_paths(root: Path) -> dict[str, Path]:
    return {
        "method_selection_post_selection_validation_results": root / VALIDATION_RESULTS,
        "method_selection_post_selection_validation_batch": root / VALIDATION_BATCH,
        "dataset_final_gate_post_selection_validation_bridge_results": (
            root / DATASET_FINAL_GATE_POST_SELECTION_VALIDATION_BRIDGE_RESULTS
        ),
        "dataset_specific_final_gate_audit": root / DATASET_FINAL_GATE,
        "selection_multiplicity_evidence_record": root / SELECTION_RECORD,
        "paper_readiness_map": root / PAPER_READINESS,
    }


def build_payload_and_configs(
    root: Path,
    *,
    config_dir: Path,
    results_root: Path,
    batch_id: str = DEFAULT_BATCH_ID,
    seeds: tuple[int, ...] = DEFAULT_MAIN_RESULT_SEEDS,
    alpha_grid: tuple[str, ...] = DEFAULT_ALPHA_GRID,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    paths = source_paths(root)
    validation_results = read_json(paths["method_selection_post_selection_validation_results"])
    validation_batch = read_json(paths["method_selection_post_selection_validation_batch"])
    bridge_results_path = paths["dataset_final_gate_post_selection_validation_bridge_results"]
    bridge_results = read_json(bridge_results_path) if bridge_results_path.exists() else {}
    dataset_gate = read_json(paths["dataset_specific_final_gate_audit"])
    selection_record = read_json(paths["selection_multiplicity_evidence_record"])
    readiness = read_json(paths["paper_readiness_map"])

    validation_summary = validation_results.get("summary") or {}
    bridge_summary = bridge_results.get("summary") or {}
    selection_summary = selection_record.get("summary") or {}
    dataset_gate_summary = dataset_gate.get("summary") or {}
    readiness_summary = readiness.get("summary") or {}
    primary_method = str(
        selection_summary.get("diagnostic_primary_method")
        or validation_summary.get("diagnostic_primary_method")
        or "cqr"
    )
    methods = ordered_unique(
        list(validation_summary.get("candidate_methods") or [])
        + list(bridge_summary.get("candidate_methods") or [])
    )
    if primary_method and primary_method not in methods:
        methods.insert(0, primary_method)
    alphas = sorted({canonical_alpha(alpha) for alpha in alpha_grid}, key=alpha_sort_key)
    seed_values = list(seeds)
    source_rows, source_row_counts = combined_source_rows(validation_results, bridge_results)
    winner_counts = merge_winner_counts(validation_results, bridge_results)
    blocked_gate_ids = [
        str(row.get("gate_id"))
        for row in readiness.get("blocked_gates") or []
        if row.get("status") == "blocked" and row.get("gate_id")
    ]

    rows: list[dict[str, Any]] = []
    configs: dict[str, dict[str, Any]] = {}
    for source_row in source_rows:
        if not isinstance(source_row, dict) or not source_row.get("dataset_id"):
            continue
        source_config_path = root / str(source_row.get("config_path") or "")
        source_config = read_yaml(source_config_path)
        out_config_path = generated_config_path(config_dir, str(source_row["dataset_id"]))
        config, row = build_generated_config(
            batch_id=batch_id,
            source_row=source_row,
            source_config=source_config,
            out_config_path=out_config_path,
            results_root=results_root,
            root=root,
            seeds=seed_values,
            alphas=alphas,
            methods=methods,
            primary_method=primary_method,
        )
        counts = winner_counts.get(str(source_row["dataset_id"]), Counter())
        row["diagnostic_winner_counts"] = dict(sorted(counts.items()))
        row["diagnostic_primary_win_count"] = int(counts.get(primary_method) or 0)
        row["diagnostic_alpha_count"] = len(alphas)
        row["promotion_priority"] = priority_for_dataset(
            counts, primary_method, len(alphas)
        )
        row["required_closure_gates"] = blocked_gate_ids
        rows.append(row)
        configs[row["config_path"]] = config

    source_validation_combined_failed_check_count = int(
        validation_summary.get("failed_check_count") or 0
    ) + int(bridge_summary.get("failed_check_count") or 0)
    source_validation_combined_feature_leakage_violation_count = int(
        validation_summary.get("feature_leakage_violation_count") or 0
    ) + int(bridge_summary.get("feature_leakage_violation_count") or 0)
    failed_checks: list[str] = []
    if not rows:
        failed_checks.append("no_candidate_rows")
    if not methods:
        failed_checks.append("no_candidate_methods")
    if source_validation_combined_failed_check_count:
        failed_checks.append("source_validation_failed_checks")
    if source_validation_combined_feature_leakage_violation_count:
        failed_checks.append("source_validation_feature_leakage_violations")
    if any(row["seed_overlap"] for row in rows):
        failed_checks.append("candidate_seed_overlap")
    if any(row["expected_atomic_run_count"] <= 0 for row in rows):
        failed_checks.append("non_positive_expected_run_count")
    if primary_method not in methods:
        failed_checks.append("primary_method_missing_from_candidate_methods")
    status = (
        "main_result_candidate_bundle_plan_failed"
        if failed_checks
        else "main_result_candidate_bundle_plan_ready_no_promotions"
    )
    priority_counts = Counter(row["promotion_priority"] for row in rows)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "source_artifacts": {key: rel(path, root) for key, path in paths.items()},
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "overall_status": status,
            "can_support_main_result_promotion": False,
            "candidate_dataset_count": len(rows),
            "generated_config_count": len(rows),
            "candidate_method_count": len(methods),
            "candidate_methods": methods,
            "diagnostic_primary_method": primary_method,
            "challenger_methods": [method for method in methods if method != primary_method],
            "alpha_count": len(alphas),
            "alphas": alphas,
            "fresh_seed_count": len(seed_values),
            "fresh_seeds": seed_values,
            "expected_atomic_run_count": sum(
                int(row["expected_atomic_run_count"]) for row in rows
            ),
            "priority_counts": dict(sorted(priority_counts.items())),
            "candidate_primary_consistent_dataset_count": int(
                priority_counts.get("candidate_primary_consistent") or 0
            ),
            "ambiguous_challenger_control_dataset_count": int(
                priority_counts.get(
                    "candidate_primary_ambiguous_challenger_controls_required"
                )
                or 0
            ),
            "source_validation_completed_atomic_rows": validation_summary.get(
                "completed_atomic_run_count"
            ),
            "source_validation_combined_completed_atomic_rows": sum(
                int(row.get("completed_atomic_run_count") or 0) for row in source_rows
            ),
            "source_validation_standard_dataset_count": source_row_counts[
                "standard_dataset_count"
            ],
            "source_validation_bridge_dataset_count": source_row_counts[
                "bridge_dataset_count"
            ],
            "source_validation_bridge_duplicate_dataset_count": source_row_counts[
                "bridge_duplicate_dataset_count"
            ],
            "source_validation_bridge_completed_atomic_rows": bridge_summary.get(
                "completed_atomic_run_count"
            ),
            "source_validation_failed_check_count": validation_summary.get(
                "failed_check_count"
            ),
            "source_validation_combined_failed_check_count": (
                source_validation_combined_failed_check_count
            ),
            "source_validation_feature_leakage_violation_count": validation_summary.get(
                "feature_leakage_violation_count"
            ),
            "source_validation_combined_feature_leakage_violation_count": (
                source_validation_combined_feature_leakage_violation_count
            ),
            "selection_record_status": selection_summary.get("overall_status"),
            "dataset_specific_final_gate_status": dataset_gate_summary.get(
                "overall_status"
            ),
            "dataset_specific_ready_dataset_count": dataset_gate_summary.get(
                "main_result_ready_dataset_count"
            ),
            "paper_readiness_status": readiness_summary.get("overall_status"),
            "paper_blocked_gate_count": readiness_summary.get("blocked_gate_count"),
            "failed_check_count": len(failed_checks),
        },
        "failed_checks": failed_checks,
        "candidate_rows": rows,
    }
    return payload, configs


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Main-Result Candidate Bundle Plan",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Candidate datasets: {summary['candidate_dataset_count']}",
        f"- Generated configs: {summary['generated_config_count']}",
        f"- Candidate methods: `{summary['candidate_methods']}`",
        f"- Diagnostic primary method: `{summary['diagnostic_primary_method']}`",
        f"- Fresh seeds: `{summary['fresh_seeds']}`",
        f"- Alphas: `{summary['alphas']}`",
        f"- Expected atomic runs: {summary['expected_atomic_run_count']}",
        f"- Main-result promotion supported: `{summary['can_support_main_result_promotion']}`",
        f"- Paper readiness: `{summary['paper_readiness_status']}` with {summary['paper_blocked_gate_count']} blocked gates",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Candidate Rows",
            "",
            "| Dataset | Source | Priority | Primary wins | Expected rows | Config |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in payload["candidate_rows"]:
        lines.append(
            "| "
            f"`{row['dataset_id']}` | "
            f"`{row['source_validation_kind']}` | "
            f"`{row['promotion_priority']}` | "
            f"{row['diagnostic_primary_win_count']} / {row['diagnostic_alpha_count']} | "
            f"{row['expected_atomic_run_count']} | "
            f"`{row['config_path']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    config_dir = resolve(root, args.config_dir)
    results_root = resolve(root, args.results_root)
    payload, configs = build_payload_and_configs(
        root,
        config_dir=config_dir,
        results_root=results_root,
        batch_id=args.batch_id,
    )
    for config_path, config in configs.items():
        atomic_write_text(
            resolve(root, config_path),
            yaml.safe_dump(config, sort_keys=False),
        )
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(json.dumps({"out": rel(out_path, root), **payload["summary"]}, sort_keys=True))
    return 0 if not payload["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
