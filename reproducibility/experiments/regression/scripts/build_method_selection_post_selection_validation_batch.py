"""Materialize an independent post-selection validation batch.

The current method-selection surface supports a practical shortlist, not a
final winner claim. This script turns that shortlist into resumable validation
configs with independent seeds and a fixed common alpha grid. The output is a
predeclared validation work queue; it must be run and re-audited before any
paper-facing final method or model-selection claim is promoted.
"""

from __future__ import annotations

import argparse
import json
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
    representative_model,
    slugify,
)


SCHEMA = "cpfi_regression_method_selection_post_selection_validation_batch_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_SOURCE_BATCH = REPORT_DIR / "method_selection_alpha_expansion_batch.json"
DEFAULT_CANDIDATE_AUDIT = REPORT_DIR / "method_selection_candidate_audit.json"
DEFAULT_ROBUSTNESS_AUDIT = REPORT_DIR / "method_selection_robustness_audit.json"
DEFAULT_ALPHA_PLAN = REPORT_DIR / "method_selection_alpha_expansion_plan.json"
DEFAULT_MULTIPLICITY_PROTOCOL = Path(
    "experiments/regression/manuscript/selection_multiplicity_protocol.json"
)
DEFAULT_OUT = REPORT_DIR / "method_selection_post_selection_validation_batch.json"
DEFAULT_CONFIG_DIR = Path("experiments/regression/configs")
DEFAULT_RESULTS_ROOT = Path("experiments/regression/results")
DEFAULT_BATCH_ID = "method_selection_post_selection_validation_v1"
DEFAULT_VALIDATION_SEEDS = (101, 211, 307)
DEFAULT_VALIDATION_ALPHAS = ("0.01", "0.05", "0.1", "0.15", "0.2")
DEFAULT_SHORTLIST_METHODS = ("cqr", "cv_plus", "mondrian_abs")

CLAIM_BOUNDARIES = [
    "This batch is an independent post-selection validation work queue; it does not select a final conformal method.",
    "Validation seeds are deliberately disjoint from the alpha-expansion and source selection seeds recorded in each source config.",
    "Candidate methods are restricted to the current practical shortlist: CQR, CV+, and Mondrian absolute-residual intervals.",
    "The fixed alpha grid is common across every generated config so post-run synthesis can use matched dataset-alpha-method support.",
    "Rows produced by this batch must be executed, synthesized, leakage-checked, and re-audited before any final method-selection, fairness, endpoint, bounded-support, or Venn-Abers validation claim is promoted.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument(
        "--source-batch",
        default=str(DEFAULT_SOURCE_BATCH),
        help="Alpha-expansion batch manifest used as the validation source surface.",
    )
    parser.add_argument(
        "--candidate-audit",
        default=str(DEFAULT_CANDIDATE_AUDIT),
        help="Method-selection candidate audit JSON path.",
    )
    parser.add_argument(
        "--robustness-audit",
        default=str(DEFAULT_ROBUSTNESS_AUDIT),
        help="Method-selection robustness audit JSON path.",
    )
    parser.add_argument(
        "--alpha-plan",
        default=str(DEFAULT_ALPHA_PLAN),
        help="Alpha-expansion plan JSON path.",
    )
    parser.add_argument(
        "--multiplicity-protocol",
        default=str(DEFAULT_MULTIPLICITY_PROTOCOL),
        help="Selection multiplicity protocol JSON path.",
    )
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
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Manifest JSON path.")
    parser.add_argument("--batch-id", default=DEFAULT_BATCH_ID)
    return parser.parse_args()


def generated_config_path(config_dir: Path, dataset_id: str) -> Path:
    return config_dir / (
        f"method_selection_post_selection_validation_{slugify(dataset_id)}.yaml"
    )


def result_slug(dataset_id: str) -> str:
    return f"method_selection_post_selection_validation_{slugify(dataset_id)}"


def source_seed_values(source_row: dict[str, Any], source_config: dict[str, Any]) -> list[Any]:
    values: list[Any] = []
    for value in source_row.get("random_seeds") or []:
        if value not in values:
            values.append(value)
    for value in source_config.get("random_seeds") or []:
        if value not in values:
            values.append(value)
    return values


def build_generated_config(
    *,
    batch_id: str,
    source_batch_path: Path,
    source_row: dict[str, Any],
    source_row_index: int,
    source_config: dict[str, Any],
    source_config_path: Path,
    out_config_path: Path,
    results_root: Path,
    root: Path,
    validation_seeds: list[int],
    validation_alphas: list[str],
    shortlist_methods: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    dataset_id = str(source_row.get("dataset_id") or "").strip()
    model = representative_model(source_config)
    source_seeds = source_seed_values(source_row, source_config)
    seed_overlap = sorted(set(source_seeds).intersection(validation_seeds))
    source_rel = rel(source_config_path, root)
    source_batch_rel = rel(source_batch_path, root)
    config_rel = rel(out_config_path, root)
    result_dir = results_root / result_slug(dataset_id)
    experiment_id = (
        f"regression_method_selection_post_selection_validation_"
        f"{slugify(dataset_id)}_v1"
    )
    quality_controls = dict(source_config.get("quality_controls") or {})
    quality_controls.update(
        {
            "method_selection_post_selection_validation_batch": True,
            "post_selection_validation_only_no_final_selection": True,
            "no_final_method_selection_claim": True,
            "candidate_methods_restricted_to_current_shortlist": True,
            "validation_seeds_independent_from_selection_surface": not seed_overlap,
            "fixed_common_alpha_grid_for_validation": True,
            "representative_source_model_only": True,
            "full_model_family_sweep_not_rerun": True,
            "requires_post_validation_resynthesis_and_reaudit": True,
            "forbid_final_model_selection_claims": True,
            "forbid_validated_venn_abers_regression_claims": True,
            "forbid_fairness_population_claims_without_population_gate": True,
            "forbid_bounded_support_claims_without_endpoint_gate": True,
        }
    )
    ledger_path = rel(result_dir / "ledger.jsonl", root)
    checkpoint_root = rel(result_dir / "checkpoints", root)
    prediction_cache_root = rel(result_dir / "checkpoints/predictions", root)
    config = {
        "experiment_id": experiment_id,
        "purpose": (
            "Independent post-selection validation batch for "
            f"{dataset_id}. The config clones audited preprocessing, split, "
            "target-transform, and runtime settings from the completed "
            "alpha-expansion support config, fixes an independent seed set and "
            "common alpha grid, and keeps claims limited to validation-work-queue "
            "evidence until the runs are executed and re-audited."
        ),
        "random_seeds": validation_seeds,
        "alphas": [alpha_float(alpha) for alpha in validation_alphas],
        "target_transform": source_config.get("target_transform", "identity"),
        "splits": deepcopy(source_config.get("splits") or {}),
        "conformal": deepcopy(source_config.get("conformal") or {}),
        "datasets": [dataset_id],
        "models": [model] if model else [],
        "cp_methods": shortlist_methods,
        "quality_controls": quality_controls,
        "post_selection_validation_provenance": {
            "schema": SCHEMA,
            "batch_id": batch_id,
            "source_alpha_expansion_batch": source_batch_rel,
            "source_alpha_expansion_config": source_rel,
            "source_alpha_expansion_experiment_id": source_config.get("experiment_id"),
            "source_alpha_expansion_generated_config_index": source_row_index,
            "source_selection_seeds": source_seeds,
            "validation_seeds": validation_seeds,
            "seed_overlap": seed_overlap,
            "claim_boundary": "post_selection_validation_only_no_final_selection",
        },
        "logging": {
            "ledger": ledger_path,
            "checkpoint_root": checkpoint_root,
            "prediction_cache_root": prediction_cache_root,
        },
    }
    expected_runs = (
        len(validation_seeds)
        * len(validation_alphas)
        * max(model_grid_size(model), 0)
        * len(shortlist_methods)
    )
    manifest_row = {
        "dataset_id": dataset_id,
        "config_path": config_rel,
        "experiment_id": experiment_id,
        "source_alpha_expansion_config": source_rel,
        "source_alpha_expansion_experiment_id": source_config.get("experiment_id"),
        "source_alpha_expansion_batch_row_index": source_row_index,
        "source_random_seeds": source_seeds,
        "validation_seeds": validation_seeds,
        "seed_overlap": seed_overlap,
        "target_alphas": validation_alphas,
        "source_target_alphas": [
            canonical_alpha(alpha) for alpha in source_row.get("target_alphas") or []
        ],
        "cp_methods": shortlist_methods,
        "source_cp_methods": list(source_row.get("cp_methods") or []),
        "model_id": model.get("model_id"),
        "model_family": model.get("family"),
        "model_grid": model.get("grid"),
        "model_grid_size": model_grid_size(model) if model else 0,
        "expected_atomic_run_count": expected_runs,
        "ledger": config["logging"]["ledger"],
        "checkpoint_root": config["logging"]["checkpoint_root"],
        "prediction_cache_root": config["logging"]["prediction_cache_root"],
        "runner_command": (
            "PYTHONPATH=. python "
            f"experiments/regression/scripts/run_regression_pilot.py --config {config_rel}"
        ),
    }
    return config, manifest_row


def validation_inputs(
    *,
    validation_seeds: tuple[int, ...] = DEFAULT_VALIDATION_SEEDS,
    validation_alphas: tuple[str, ...] = DEFAULT_VALIDATION_ALPHAS,
    shortlist_methods: tuple[str, ...] = DEFAULT_SHORTLIST_METHODS,
) -> tuple[list[int], list[str], list[str]]:
    seeds = list(validation_seeds)
    alphas = sorted({canonical_alpha(alpha) for alpha in validation_alphas}, key=alpha_sort_key)
    methods = list(shortlist_methods)
    return seeds, alphas, methods


def validate_manifest(
    *,
    source_batch: dict[str, Any],
    candidate_audit: dict[str, Any],
    robustness_audit: dict[str, Any],
    alpha_plan: dict[str, Any],
    multiplicity_protocol: dict[str, Any],
    generated_configs: list[dict[str, Any]],
    validation_seeds: list[int],
    validation_alphas: list[str],
    shortlist_methods: list[str],
) -> list[dict[str, Any]]:
    source_summary = source_batch.get("summary") or {}
    candidate_summary = candidate_audit.get("summary") or {}
    robustness_summary = robustness_audit.get("summary") or {}
    alpha_plan_summary = alpha_plan.get("summary") or {}
    multiplicity_summary = multiplicity_protocol.get("summary") or {}
    expected_runs_per_config = len(validation_seeds) * len(validation_alphas) * len(shortlist_methods)
    checks = [
        {
            "check_id": "source_alpha_expansion_batch_available",
            "status": (
                "pass"
                if source_summary.get("overall_status")
                == "method_selection_alpha_expansion_batch_ready"
                and source_batch.get("generated_configs")
                else "fail"
            ),
            "observed": {
                "overall_status": source_summary.get("overall_status"),
                "generated_config_count": source_summary.get("generated_config_count"),
            },
        },
        {
            "check_id": "candidate_audit_blocks_final_selection",
            "status": (
                "pass"
                if candidate_summary.get("overall_status")
                == "method_selection_candidate_audit_ready_no_final_selection"
                and candidate_summary.get("can_support_final_method_selection") is False
                else "fail"
            ),
            "observed": {
                "overall_status": candidate_summary.get("overall_status"),
                "can_support_final_method_selection": candidate_summary.get(
                    "can_support_final_method_selection"
                ),
                "primary_candidate_method": candidate_summary.get(
                    "primary_candidate_method"
                ),
            },
        },
        {
            "check_id": "robustness_audit_shortlist_matches_validation_methods",
            "status": (
                "pass"
                if set(robustness_summary.get("candidate_methods") or [])
                == set(shortlist_methods)
                and robustness_summary.get("can_support_final_method_selection") is False
                else "fail"
            ),
            "observed": {
                "candidate_methods": robustness_summary.get("candidate_methods"),
                "validation_methods": shortlist_methods,
                "can_support_final_method_selection": robustness_summary.get(
                    "can_support_final_method_selection"
                ),
                "common_cell_winner_counts": robustness_summary.get(
                    "common_cell_winner_counts"
                ),
            },
        },
        {
            "check_id": "alpha_plan_no_final_claim_boundary_preserved",
            "status": (
                "pass"
                if alpha_plan_summary.get("can_support_final_method_selection") is False
                and int(alpha_plan_summary.get("failed_check_count") or 0) == 0
                else "fail"
            ),
            "observed": {
                "overall_status": alpha_plan_summary.get("overall_status"),
                "failed_check_count": alpha_plan_summary.get("failed_check_count"),
                "can_support_final_method_selection": alpha_plan_summary.get(
                    "can_support_final_method_selection"
                ),
            },
        },
        {
            "check_id": "multiplicity_protocol_requires_post_selection_record",
            "status": (
                "pass"
                if multiplicity_summary.get(
                    "selection_protocol_can_support_final_method_selection"
                )
                is False
                or multiplicity_summary.get("can_support_final_method_selection") is False
                else "fail"
            ),
            "observed": {
                "overall_status": multiplicity_summary.get("overall_status"),
                "selection_protocol_can_support_final_method_selection": (
                    multiplicity_summary.get(
                        "selection_protocol_can_support_final_method_selection"
                    )
                ),
                "can_support_final_method_selection": multiplicity_summary.get(
                    "can_support_final_method_selection"
                ),
            },
        },
        {
            "check_id": "validation_seeds_disjoint_from_selection_surface",
            "status": (
                "pass"
                if generated_configs
                and all(not row.get("seed_overlap") for row in generated_configs)
                else "fail"
            ),
            "observed": {
                row.get("dataset_id"): row.get("seed_overlap")
                for row in generated_configs
            },
        },
        {
            "check_id": "fixed_common_alpha_grid_everywhere",
            "status": (
                "pass"
                if generated_configs
                and all(row.get("target_alphas") == validation_alphas for row in generated_configs)
                else "fail"
            ),
            "observed": {
                row.get("dataset_id"): row.get("target_alphas")
                for row in generated_configs
            },
        },
        {
            "check_id": "shortlist_methods_everywhere",
            "status": (
                "pass"
                if generated_configs
                and all(row.get("cp_methods") == shortlist_methods for row in generated_configs)
                else "fail"
            ),
            "observed": {
                row.get("dataset_id"): row.get("cp_methods")
                for row in generated_configs
            },
        },
        {
            "check_id": "representative_model_scope_enforced",
            "status": (
                "pass"
                if generated_configs
                and all(int(row.get("model_grid_size") or 0) == 1 for row in generated_configs)
                else "fail"
            ),
            "observed": {
                row.get("dataset_id"): row.get("model_grid_size")
                for row in generated_configs
            },
        },
        {
            "check_id": "expected_atomic_runs_match_common_grid",
            "status": (
                "pass"
                if generated_configs
                and all(
                    int(row.get("expected_atomic_run_count") or 0)
                    == expected_runs_per_config
                    for row in generated_configs
                )
                else "fail"
            ),
            "observed": {
                "expected_runs_per_config": expected_runs_per_config,
                "per_dataset": {
                    row.get("dataset_id"): row.get("expected_atomic_run_count")
                    for row in generated_configs
                },
            },
        },
        {
            "check_id": "resumable_logging_present",
            "status": (
                "pass"
                if generated_configs
                and all(
                    row.get("ledger")
                    and row.get("checkpoint_root")
                    and row.get("prediction_cache_root")
                    for row in generated_configs
                )
                else "fail"
            ),
            "observed": {"generated_config_count": len(generated_configs)},
        },
        {
            "check_id": "no_final_selection_claim",
            "status": "pass",
            "observed": {
                "batch_claim_status": "post_selection_validation_batch_ready_no_final_selection",
                "can_support_final_method_selection": False,
            },
        },
    ]
    return checks


def build_payload(
    *,
    root: Path,
    source_batch_path: Path,
    candidate_audit_path: Path,
    robustness_audit_path: Path,
    alpha_plan_path: Path,
    multiplicity_protocol_path: Path,
    config_dir: Path,
    results_root: Path,
    batch_id: str,
    validation_seed_values: tuple[int, ...] = DEFAULT_VALIDATION_SEEDS,
    validation_alpha_values: tuple[str, ...] = DEFAULT_VALIDATION_ALPHAS,
    shortlist_method_values: tuple[str, ...] = DEFAULT_SHORTLIST_METHODS,
) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    source_batch = read_json(source_batch_path)
    candidate_audit = read_json(candidate_audit_path)
    robustness_audit = read_json(robustness_audit_path)
    alpha_plan = read_json(alpha_plan_path)
    multiplicity_protocol = read_json(multiplicity_protocol_path)
    validation_seeds, validation_alphas, shortlist_methods = validation_inputs(
        validation_seeds=validation_seed_values,
        validation_alphas=validation_alpha_values,
        shortlist_methods=shortlist_method_values,
    )
    config_writes: list[tuple[Path, dict[str, Any]]] = []
    generated_configs: list[dict[str, Any]] = []
    for row_index, source_row in enumerate(source_batch.get("generated_configs") or []):
        dataset_id = str(source_row.get("dataset_id") or "").strip()
        source_config_value = source_row.get("config_path")
        if not dataset_id or not source_config_value:
            continue
        source_config_path = root / str(source_config_value)
        source_config = read_yaml(source_config_path)
        out_config_path = generated_config_path(config_dir, dataset_id)
        config, manifest_row = build_generated_config(
            batch_id=batch_id,
            source_batch_path=source_batch_path,
            source_row=source_row,
            source_row_index=row_index,
            source_config=source_config,
            source_config_path=source_config_path,
            out_config_path=out_config_path,
            results_root=results_root,
            root=root,
            validation_seeds=validation_seeds,
            validation_alphas=validation_alphas,
            shortlist_methods=shortlist_methods,
        )
        config_writes.append((out_config_path, config))
        generated_configs.append(manifest_row)
    checks = validate_manifest(
        source_batch=source_batch,
        candidate_audit=candidate_audit,
        robustness_audit=robustness_audit,
        alpha_plan=alpha_plan,
        multiplicity_protocol=multiplicity_protocol,
        generated_configs=generated_configs,
        validation_seeds=validation_seeds,
        validation_alphas=validation_alphas,
        shortlist_methods=shortlist_methods,
    )
    failed_checks = [check for check in checks if check["status"] != "pass"]
    status = (
        "method_selection_post_selection_validation_batch_ready"
        if not failed_checks and generated_configs
        else "method_selection_post_selection_validation_batch_failed"
    )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "source_artifacts": {
            "method_selection_alpha_expansion_batch": rel(source_batch_path, root),
            "method_selection_candidate_audit": rel(candidate_audit_path, root),
            "method_selection_robustness_audit": rel(robustness_audit_path, root),
            "method_selection_alpha_expansion_plan": rel(alpha_plan_path, root),
            "selection_multiplicity_protocol": rel(
                multiplicity_protocol_path, root
            ),
        },
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "overall_status": status,
            "failed_check_count": len(failed_checks),
            "execution_status": "configs_generated_not_yet_run",
            "claim_status": "post_selection_validation_batch_ready_no_final_selection",
            "can_support_final_method_selection": False,
            "generated_config_count": len(generated_configs),
            "dataset_count": len(generated_configs),
            "validation_seed_count": len(validation_seeds),
            "validation_seeds": validation_seeds,
            "validation_alpha_count": len(validation_alphas),
            "target_alphas": validation_alphas,
            "candidate_methods": shortlist_methods,
            "expected_atomic_run_count": sum(
                int(row.get("expected_atomic_run_count") or 0)
                for row in generated_configs
            ),
            "source_batch_expected_atomic_run_count": (
                source_batch.get("summary") or {}
            ).get("expected_atomic_run_count"),
            "validation_design": (
                "5 datasets x 3 independent seeds x 5 alphas x 3 candidate "
                "methods x 1 representative source model"
            ),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "generated_configs": generated_configs,
        "run_commands": [row["runner_command"] for row in generated_configs],
    }
    return payload, config_writes


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Method Selection Post-Selection Validation Batch",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Execution status: `{summary['execution_status']}`",
        f"- Generated configs: {summary['generated_config_count']}",
        f"- Expected atomic runs: {summary['expected_atomic_run_count']}",
        f"- Validation seeds: `{summary['validation_seeds']}`",
        f"- Target alphas: `{summary['target_alphas']}`",
        f"- Candidate methods: `{summary['candidate_methods']}`",
        f"- Claim status: `{summary['claim_status']}`",
        "",
        "This artifact is a validation work queue, not a final method-selection record.",
        "",
        "## Generated Configs",
        "",
        "| dataset | config | source config | alphas | methods | validation seeds | expected runs |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in payload["generated_configs"]:
        lines.append(
            "| `{dataset}` | `{config}` | `{source}` | `{alphas}` | `{methods}` | `{seeds}` | {runs} |".format(
                dataset=row["dataset_id"],
                config=row["config_path"],
                source=row["source_alpha_expansion_config"],
                alphas=row["target_alphas"],
                methods=row["cp_methods"],
                seeds=row["validation_seeds"],
                runs=row["expected_atomic_run_count"],
            )
        )
    lines.extend(["", "## Checks", ""])
    lines.append("| check | status | observed |")
    lines.append("| --- | --- | --- |")
    for check in payload["checks"]:
        lines.append(
            f"| `{check['check_id']}` | `{check['status']}` | `{check.get('observed', {})}` |"
        )
    lines.extend(["", "## Run Commands", ""])
    lines.extend(f"- `{command}`" for command in payload["run_commands"])
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    payload, config_writes = build_payload(
        root=root,
        source_batch_path=(root / args.source_batch).resolve(),
        candidate_audit_path=(root / args.candidate_audit).resolve(),
        robustness_audit_path=(root / args.robustness_audit).resolve(),
        alpha_plan_path=(root / args.alpha_plan).resolve(),
        multiplicity_protocol_path=(root / args.multiplicity_protocol).resolve(),
        config_dir=(root / args.config_dir).resolve(),
        results_root=(root / args.results_root).resolve(),
        batch_id=str(args.batch_id),
    )
    for path, config in config_writes:
        atomic_write_text(
            path,
            yaml.safe_dump(config, sort_keys=False, allow_unicode=False),
        )
    out_path = (root / args.out).resolve()
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "generated_config_count": payload["summary"]["generated_config_count"],
                "expected_atomic_run_count": payload["summary"][
                    "expected_atomic_run_count"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
