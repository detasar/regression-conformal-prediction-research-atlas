"""Build the UCI Wine post-selection validation bridge.

UCI Wine is present in the dataset final-gate audit, but it did not enter the
standard post-selection validation batch because its support surface came from
the duplicate-sensitivity model-family sweep rather than the alpha-expansion
batch. This script materializes a separate bridge config and manifest so that
the dataset can be validated on the same CQR/CV+/Mondrian_abs grid without
promoting a final method, model, dataset, fairness, bounded-support, or
Venn-Abers claim.
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


SCHEMA = "cpfi_regression_dataset_final_gate_post_selection_validation_bridge_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_SOURCE_CONFIG = Path(
    "experiments/regression/configs/"
    "model_family_sweep_uci_wine_quality_duplicate_sensitivity.yaml"
)
DEFAULT_SOURCE_REPORT = Path(
    "experiments/regression/reports/"
    "model_family_sweep_uci_wine_quality_duplicate_sensitivity/pilot_summary.json"
)
DEFAULT_SOURCE_FEATURE_AUDIT = Path(
    "experiments/regression/reports/"
    "model_family_sweep_uci_wine_quality_duplicate_sensitivity/feature_leakage_audit.json"
)
DEFAULT_REMEDIATION_PLAN = REPORT_DIR / "dataset_final_gate_remediation_plan.json"
DEFAULT_OUT = REPORT_DIR / "dataset_final_gate_post_selection_validation_bridge.json"
DEFAULT_BRIDGE_RESULTS = (
    REPORT_DIR / "dataset_final_gate_post_selection_validation_bridge_results.json"
)
DEFAULT_CONFIG_DIR = Path("experiments/regression/configs")
DEFAULT_RESULTS_ROOT = Path("experiments/regression/results")
DEFAULT_DATASET_ID = "uci_wine_quality"
DEFAULT_BATCH_ID = "dataset_final_gate_post_selection_validation_bridge_v1"
DEFAULT_VALIDATION_SEEDS = (101, 211, 307)
DEFAULT_VALIDATION_ALPHAS = ("0.01", "0.05", "0.1", "0.15", "0.2")
DEFAULT_SHORTLIST_METHODS = ("cqr", "cv_plus", "mondrian_abs")

CLAIM_BOUNDARIES = [
    "This bridge is a dataset final-gate validation work queue; it does not select a final conformal method.",
    "UCI Wine is bridged separately because its source support came from the duplicate-sensitivity model-family sweep, not the alpha-expansion batch.",
    "The generated bridge config uses the raw UCI Wine dataset only; the deduplicated variant remains duplicate-sensitivity evidence.",
    "Validation seeds are disjoint from the source model-family sweep seeds.",
    "Rows produced by this bridge must be executed, synthesized, leakage-checked, and re-audited before UCI Wine can enter a main-result candidate bundle.",
    "No final method/model selection, fairness/population, bounded-support, wine-domain, product-ranking, or validated Venn-Abers regression claim is promoted.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument(
        "--source-config",
        default=str(DEFAULT_SOURCE_CONFIG),
        help="Completed UCI Wine model-family sweep config.",
    )
    parser.add_argument(
        "--source-report",
        default=str(DEFAULT_SOURCE_REPORT),
        help="Completed UCI Wine model-family sweep pilot summary.",
    )
    parser.add_argument(
        "--source-feature-audit",
        default=str(DEFAULT_SOURCE_FEATURE_AUDIT),
        help="Feature-leakage audit for the UCI Wine source sweep.",
    )
    parser.add_argument(
        "--remediation-plan",
        default=str(DEFAULT_REMEDIATION_PLAN),
        help="Dataset final-gate remediation plan identifying the bridge gap.",
    )
    parser.add_argument(
        "--bridge-results",
        default=str(DEFAULT_BRIDGE_RESULTS),
        help="Optional completed bridge-results artifact for lifecycle reconciliation.",
    )
    parser.add_argument(
        "--config-dir",
        default=str(DEFAULT_CONFIG_DIR),
        help="Directory for the generated bridge YAML config.",
    )
    parser.add_argument(
        "--results-root",
        default=str(DEFAULT_RESULTS_ROOT),
        help="Root directory for generated bridge ledgers and checkpoints.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Manifest JSON path.")
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID)
    parser.add_argument("--batch-id", default=DEFAULT_BATCH_ID)
    return parser.parse_args()


def generated_config_path(config_dir: Path, dataset_id: str) -> Path:
    return config_dir / (
        f"method_selection_post_selection_validation_bridge_{slugify(dataset_id)}.yaml"
    )


def result_slug(dataset_id: str) -> str:
    return f"method_selection_post_selection_validation_{slugify(dataset_id)}"


def validation_inputs(
    *,
    validation_seeds: tuple[int, ...] = DEFAULT_VALIDATION_SEEDS,
    validation_alphas: tuple[str, ...] = DEFAULT_VALIDATION_ALPHAS,
    shortlist_methods: tuple[str, ...] = DEFAULT_SHORTLIST_METHODS,
) -> tuple[list[int], list[str], list[str]]:
    seeds = list(validation_seeds)
    alphas = sorted(
        {canonical_alpha(alpha) for alpha in validation_alphas},
        key=alpha_sort_key,
    )
    methods = list(shortlist_methods)
    return seeds, alphas, methods


def load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def feature_violation_count(feature_audit: dict[str, Any]) -> int:
    if "violations_count" in feature_audit:
        return int(feature_audit.get("violations_count") or 0)
    if "violation_count" in feature_audit:
        return int(feature_audit.get("violation_count") or 0)
    violations = feature_audit.get("violations")
    return len(violations) if isinstance(violations, list) else 0


def source_seed_values(source_config: dict[str, Any]) -> list[int]:
    values: list[int] = []
    for value in source_config.get("random_seeds") or []:
        int_value = int(value)
        if int_value not in values:
            values.append(int_value)
    return values


def source_ledger_path(root: Path, source_config: dict[str, Any]) -> Path:
    logging = source_config.get("logging") or {}
    value = logging.get("ledger")
    return root / str(value) if value else root / "__missing_ledger__.jsonl"


def build_generated_config(
    *,
    root: Path,
    batch_id: str,
    dataset_id: str,
    source_config: dict[str, Any],
    source_config_path: Path,
    source_report_path: Path,
    source_feature_audit_path: Path,
    remediation_plan_path: Path,
    source_report: dict[str, Any],
    source_feature_audit: dict[str, Any],
    out_config_path: Path,
    results_root: Path,
    validation_seeds: list[int],
    validation_alphas: list[str],
    shortlist_methods: list[str],
    source_ledger_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    model = representative_model(source_config)
    source_seeds = source_seed_values(source_config)
    seed_overlap = sorted(set(source_seeds).intersection(validation_seeds))
    result_dir = results_root / result_slug(dataset_id)
    experiment_id = (
        "regression_dataset_final_gate_post_selection_validation_bridge_"
        f"{slugify(dataset_id)}_v1"
    )
    source_logging = source_config.get("logging") or {}
    source_ledger = source_ledger_path(root, source_config)
    quality_controls = dict(source_config.get("quality_controls") or {})
    quality_controls.update(
        {
            "dataset_final_gate_post_selection_validation_bridge": True,
            "post_selection_validation_only_no_final_selection": True,
            "uci_wine_quality_source_model_family_sweep_bridge": True,
            "bridge_dataset_was_not_in_alpha_expansion_batch": True,
            "raw_uci_wine_variant_only": True,
            "dedup_variant_not_rerun_in_bridge": True,
            "candidate_methods_restricted_to_current_shortlist": True,
            "validation_seeds_independent_from_source_sweep": not seed_overlap,
            "fixed_common_alpha_grid_for_validation": True,
            "representative_source_model_only": True,
            "full_model_family_sweep_not_rerun": True,
            "requires_bridge_execution_and_post_run_audit": True,
            "no_final_method_selection_claim": True,
            "forbid_final_model_selection_claims": True,
            "forbid_validated_venn_abers_regression_claims": True,
            "forbid_fairness_population_claims_without_population_gate": True,
            "forbid_bounded_support_claims_without_endpoint_gate": True,
        }
    )
    ledger_path = rel(result_dir / "ledger.jsonl", root)
    checkpoint_root = rel(result_dir / "checkpoints", root)
    prediction_cache_root = rel(result_dir / "checkpoints/predictions", root)
    source_metadata = source_report.get("metadata") or {}
    config = {
        "experiment_id": experiment_id,
        "purpose": (
            "Dataset final-gate post-selection validation bridge for raw UCI "
            "Wine Quality. The config clones audited preprocessing, split, "
            "target-transform, and conformal runtime settings from the completed "
            "duplicate-sensitivity model-family sweep, then applies independent "
            "validation seeds, a common alpha grid, one representative ridge "
            "model, and the CQR/CV+/Mondrian_abs shortlist. It is validation "
            "work-queue evidence only."
        ),
        "random_seeds": list(validation_seeds),
        "alphas": [alpha_float(alpha) for alpha in validation_alphas],
        "target_transform": source_config.get("target_transform", "identity"),
        "splits": deepcopy(source_config.get("splits") or {}),
        "conformal": deepcopy(source_config.get("conformal") or {}),
        "datasets": [dataset_id],
        "models": [model] if model else [],
        "cp_methods": shortlist_methods,
        "quality_controls": quality_controls,
        "post_selection_validation_bridge_provenance": {
            "schema": SCHEMA,
            "batch_id": batch_id,
            "source_model_family_sweep_config": rel(source_config_path, root),
            "source_model_family_sweep_report": rel(source_report_path, root),
            "source_feature_leakage_audit": rel(source_feature_audit_path, root),
            "source_dataset_final_gate_remediation_plan": rel(
                remediation_plan_path, root
            ),
            "source_experiment_id": source_config.get("experiment_id"),
            "source_datasets": list(source_config.get("datasets") or []),
            "source_random_seeds": source_seeds,
            "validation_seeds": list(validation_seeds),
            "seed_overlap": seed_overlap,
            "source_alphas": [
                canonical_alpha(alpha) for alpha in source_config.get("alphas") or []
            ],
            "target_alphas": list(validation_alphas),
            "source_ledger": rel(source_ledger, root),
            "source_ledger_row_count": len(source_ledger_rows),
            "source_report_ledger_rows": source_metadata.get("ledger_rows"),
            "source_feature_leakage_violations": feature_violation_count(
                source_feature_audit
            ),
            "representative_model_rule": "prefer ridge and keep the first grid value per hyperparameter",
            "claim_boundary": "post_selection_validation_bridge_only_no_final_selection",
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
        "config_path": rel(out_config_path, root),
        "experiment_id": experiment_id,
        "source_model_family_sweep_config": rel(source_config_path, root),
        "source_model_family_sweep_experiment_id": source_config.get(
            "experiment_id"
        ),
        "source_model_family_sweep_report": rel(source_report_path, root),
        "source_feature_leakage_audit": rel(source_feature_audit_path, root),
        "source_dataset_final_gate_remediation_plan": rel(
            remediation_plan_path, root
        ),
        "source_random_seeds": source_seeds,
        "validation_seeds": validation_seeds,
        "seed_overlap": seed_overlap,
        "target_alphas": validation_alphas,
        "source_target_alphas": [
            canonical_alpha(alpha) for alpha in source_config.get("alphas") or []
        ],
        "cp_methods": shortlist_methods,
        "source_cp_methods": list(source_config.get("cp_methods") or []),
        "model_id": model.get("model_id"),
        "model_family": model.get("family"),
        "model_grid": model.get("grid"),
        "model_grid_size": model_grid_size(model) if model else 0,
        "expected_atomic_run_count": expected_runs,
        "ledger": config["logging"]["ledger"],
        "checkpoint_root": config["logging"]["checkpoint_root"],
        "prediction_cache_root": config["logging"]["prediction_cache_root"],
        "source_ledger": rel(source_ledger, root),
        "source_ledger_row_count": len(source_ledger_rows),
        "source_completed_ledger_row_count": sum(
            1 for row in source_ledger_rows if row.get("status") == "completed"
        ),
        "source_report_ledger_rows": source_metadata.get("ledger_rows"),
        "source_report_dataset_count": (
            source_metadata.get("dataset_counts") or {}
        ).get(dataset_id),
        "source_feature_leakage_violation_count": feature_violation_count(
            source_feature_audit
        ),
        "execution_status": "config_generated_not_yet_run",
        "can_support_final_method_selection": False,
        "runner_command": (
            "PYTHONPATH=. python "
            f"experiments/regression/scripts/run_regression_pilot.py --config {rel(out_config_path, root)}"
        ),
    }
    return config, manifest_row


def validate_manifest(
    *,
    dataset_id: str,
    source_config: dict[str, Any],
    source_report: dict[str, Any],
    source_feature_audit: dict[str, Any],
    remediation_plan: dict[str, Any],
    generated_configs: list[dict[str, Any]],
    bridge_results: dict[str, Any],
    validation_seeds: list[int],
    validation_alphas: list[str],
    shortlist_methods: list[str],
) -> list[dict[str, Any]]:
    source_metadata = source_report.get("metadata") or {}
    source_status_counts = source_metadata.get("status_counts") or {}
    source_dataset_counts = source_metadata.get("dataset_counts") or {}
    generated_row = generated_configs[0] if generated_configs else {}
    bridge_result_summary = bridge_results.get("summary") or {}
    bridge_result_rows = bridge_results.get("dataset_rows") or []
    bridge_result_row = next(
        (
            row
            for row in bridge_result_rows
            if isinstance(row, dict) and row.get("dataset_id") == dataset_id
        ),
        {},
    )
    expected_runs = len(validation_seeds) * len(validation_alphas) * len(
        shortlist_methods
    )
    bridge_results_available = bool(bridge_results)
    bridge_results_complete = (
        bridge_results_available
        and int(bridge_result_summary.get("completed_atomic_run_count") or 0)
        == expected_runs
        and int(bridge_result_summary.get("expected_atomic_run_count") or 0)
        == expected_runs
        and int(bridge_result_summary.get("feature_leakage_violation_count") or 0)
        == 0
        and bridge_result_summary.get("can_support_final_method_selection") is False
        and not bridge_results.get("failed_checks")
    )
    remediation_rows = {
        str(row.get("dataset_id")): row
        for row in remediation_plan.get("dataset_rows") or []
        if isinstance(row, dict) and row.get("dataset_id")
    }
    remediation_row = remediation_rows.get(dataset_id) or {}
    remediation_gap_open = (
        bool(remediation_row)
        and remediation_row.get("has_post_selection_validation_source") is False
    )
    remediation_gap_closed_by_bridge_results = (
        bool(remediation_row)
        and remediation_row.get("has_post_selection_validation_bridge_results") is True
        and remediation_row.get("post_selection_validation_source_kind")
        == "dataset_final_gate_bridge_results"
    )
    feature_missing = source_feature_audit.get("metadata_completeness") or {}
    backfill = source_feature_audit.get("backfill_policy_inference") or {}
    checks = [
        {
            "check_id": "source_config_contains_raw_uci_dataset",
            "status": (
                "pass"
                if dataset_id in (source_config.get("datasets") or [])
                and source_config.get("experiment_id")
                else "fail"
            ),
            "observed": {
                "experiment_id": source_config.get("experiment_id"),
                "datasets": source_config.get("datasets"),
            },
        },
        {
            "check_id": "source_sweep_completed",
            "status": (
                "pass"
                if int(source_metadata.get("ledger_rows") or 0) > 0
                and int(source_status_counts.get("completed") or 0)
                == int(source_metadata.get("ledger_rows") or 0)
                and int(generated_row.get("source_completed_ledger_row_count") or 0)
                == int(generated_row.get("source_ledger_row_count") or 0)
                else "fail"
            ),
            "observed": {
                "report_ledger_rows": source_metadata.get("ledger_rows"),
                "report_status_counts": source_status_counts,
                "ledger_row_count": generated_row.get("source_ledger_row_count"),
                "completed_ledger_row_count": generated_row.get(
                    "source_completed_ledger_row_count"
                ),
            },
        },
        {
            "check_id": "source_report_has_raw_uci_rows",
            "status": (
                "pass" if int(source_dataset_counts.get(dataset_id) or 0) > 0 else "fail"
            ),
            "observed": {"dataset_counts": source_dataset_counts},
        },
        {
            "check_id": "source_feature_leakage_audit_clean",
            "status": (
                "pass"
                if feature_violation_count(source_feature_audit) == 0
                and int(feature_missing.get("missing_feature_drop_columns") or 0) == 0
                and int(feature_missing.get("missing_feature_drop_policy") or 0) == 0
                and backfill.get("exact_feature_set_enforced") is True
                and backfill.get("exact_drop_set_enforced") is True
                else "fail"
            ),
            "observed": {
                "violations_count": feature_violation_count(source_feature_audit),
                "metadata_completeness": feature_missing,
                "exact_feature_set_enforced": backfill.get(
                    "exact_feature_set_enforced"
                ),
                "exact_drop_set_enforced": backfill.get("exact_drop_set_enforced"),
            },
        },
        {
            "check_id": "remediation_plan_bridge_lifecycle_consistent",
            "status": (
                "pass"
                if remediation_gap_open or remediation_gap_closed_by_bridge_results
                else "fail"
            ),
            "observed": {
                "readiness_status": remediation_row.get("readiness_status"),
                "primary_next_action": remediation_row.get("primary_next_action"),
                "has_post_selection_validation_source": remediation_row.get(
                    "has_post_selection_validation_source"
                ),
                "has_post_selection_validation_bridge_results": (
                    remediation_row.get("has_post_selection_validation_bridge_results")
                ),
                "post_selection_validation_source_kind": remediation_row.get(
                    "post_selection_validation_source_kind"
                ),
                "post_selection_validation_completed_atomic_run_count": (
                    remediation_row.get(
                        "post_selection_validation_completed_atomic_run_count"
                    )
                ),
                "post_selection_validation_expected_atomic_run_count": (
                    remediation_row.get(
                        "post_selection_validation_expected_atomic_run_count"
                    )
                ),
                "lifecycle_state": (
                    "validation_gap_open"
                    if remediation_gap_open
                    else (
                        "validation_gap_closed_by_bridge_results"
                        if remediation_gap_closed_by_bridge_results
                        else "unexpected_remediation_state"
                    )
                ),
            },
        },
        {
            "check_id": "raw_variant_only",
            "status": (
                "pass"
                if [row.get("dataset_id") for row in generated_configs] == [dataset_id]
                else "fail"
            ),
            "observed": {
                "generated_dataset_ids": [
                    row.get("dataset_id") for row in generated_configs
                ]
            },
        },
        {
            "check_id": "validation_seeds_disjoint_from_source_sweep",
            "status": (
                "pass"
                if generated_configs and all(not row.get("seed_overlap") for row in generated_configs)
                else "fail"
            ),
            "observed": {
                row.get("dataset_id"): row.get("seed_overlap")
                for row in generated_configs
            },
        },
        {
            "check_id": "fixed_common_alpha_grid",
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
            "check_id": "shortlist_methods_only",
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
            "check_id": "representative_ridge_model_scope",
            "status": (
                "pass"
                if generated_configs
                and all(
                    row.get("model_id") == "ridge"
                    and int(row.get("model_grid_size") or 0) == 1
                    for row in generated_configs
                )
                else "fail"
            ),
            "observed": {
                row.get("dataset_id"): {
                    "model_id": row.get("model_id"),
                    "model_grid": row.get("model_grid"),
                    "model_grid_size": row.get("model_grid_size"),
                }
                for row in generated_configs
            },
        },
        {
            "check_id": "expected_atomic_runs_match_bridge_grid",
            "status": (
                "pass"
                if generated_configs
                and all(
                    int(row.get("expected_atomic_run_count") or 0) == expected_runs
                    for row in generated_configs
                )
                else "fail"
            ),
            "observed": {
                "expected_runs_per_config": expected_runs,
                "per_dataset": {
                    row.get("dataset_id"): row.get("expected_atomic_run_count")
                    for row in generated_configs
                },
            },
        },
        {
            "check_id": "bridge_results_reconciled_when_available",
            "status": (
                "pass"
                if not bridge_results_available or bridge_results_complete
                else "fail"
            ),
            "observed": {
                "bridge_results_available": bridge_results_available,
                "overall_status": bridge_result_summary.get("overall_status"),
                "expected_atomic_run_count": bridge_result_summary.get(
                    "expected_atomic_run_count"
                ),
                "completed_atomic_run_count": bridge_result_summary.get(
                    "completed_atomic_run_count"
                ),
                "dataset_row_completed_atomic_run_count": bridge_result_row.get(
                    "completed_atomic_run_count"
                ),
                "feature_leakage_violation_count": bridge_result_summary.get(
                    "feature_leakage_violation_count"
                ),
                "can_support_final_method_selection": bridge_result_summary.get(
                    "can_support_final_method_selection"
                ),
            },
        },
        {
            "check_id": "no_final_claim_promoted",
            "status": (
                "pass"
                if generated_configs
                and all(
                    row.get("can_support_final_method_selection") is False
                    for row in generated_configs
                )
                else "fail"
            ),
            "observed": {
                "can_support_final_method_selection": [
                    row.get("can_support_final_method_selection")
                    for row in generated_configs
                ],
                "claim_status": "post_selection_validation_bridge_ready_no_promotions",
            },
        },
    ]
    return checks


def build_payload(
    *,
    root: Path,
    source_config_path: Path,
    source_report_path: Path,
    source_feature_audit_path: Path,
    remediation_plan_path: Path,
    bridge_results_path: Path,
    config_dir: Path,
    results_root: Path,
    dataset_id: str,
    batch_id: str,
    validation_seed_values: tuple[int, ...] = DEFAULT_VALIDATION_SEEDS,
    validation_alpha_values: tuple[str, ...] = DEFAULT_VALIDATION_ALPHAS,
    shortlist_method_values: tuple[str, ...] = DEFAULT_SHORTLIST_METHODS,
) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    source_config = read_yaml(source_config_path)
    source_report = read_json(source_report_path)
    source_feature_audit = read_json(source_feature_audit_path)
    remediation_plan = read_json(remediation_plan_path)
    bridge_results = read_json(bridge_results_path) if bridge_results_path.exists() else {}
    validation_seeds, validation_alphas, shortlist_methods = validation_inputs(
        validation_seeds=validation_seed_values,
        validation_alphas=validation_alpha_values,
        shortlist_methods=shortlist_method_values,
    )
    source_ledger_rows = load_ledger(source_ledger_path(root, source_config))
    out_config_path = generated_config_path(config_dir, dataset_id)
    config, manifest_row = build_generated_config(
        root=root,
        batch_id=batch_id,
        dataset_id=dataset_id,
        source_config=source_config,
        source_config_path=source_config_path,
        source_report_path=source_report_path,
        source_feature_audit_path=source_feature_audit_path,
        remediation_plan_path=remediation_plan_path,
        source_report=source_report,
        source_feature_audit=source_feature_audit,
        out_config_path=out_config_path,
        results_root=results_root,
        validation_seeds=validation_seeds,
        validation_alphas=validation_alphas,
        shortlist_methods=shortlist_methods,
        source_ledger_rows=source_ledger_rows,
    )
    generated_configs = [manifest_row]
    checks = validate_manifest(
        dataset_id=dataset_id,
        source_config=source_config,
        source_report=source_report,
        source_feature_audit=source_feature_audit,
        remediation_plan=remediation_plan,
        generated_configs=generated_configs,
        bridge_results=bridge_results,
        validation_seeds=validation_seeds,
        validation_alphas=validation_alphas,
        shortlist_methods=shortlist_methods,
    )
    failed_checks = [check for check in checks if check["status"] != "pass"]
    status = (
        "dataset_final_gate_post_selection_validation_bridge_ready_no_promotions"
        if not failed_checks and generated_configs
        else "dataset_final_gate_post_selection_validation_bridge_failed"
    )
    source_artifacts = {
        "source_model_family_sweep_config": rel(source_config_path, root),
        "source_model_family_sweep_report": rel(source_report_path, root),
        "source_feature_leakage_audit": rel(source_feature_audit_path, root),
        "dataset_final_gate_remediation_plan": rel(remediation_plan_path, root),
    }
    bridge_result_summary = bridge_results.get("summary") or {}
    bridge_results_complete = (
        bool(bridge_results)
        and int(bridge_result_summary.get("completed_atomic_run_count") or 0)
        == sum(int(row.get("expected_atomic_run_count") or 0) for row in generated_configs)
        and int(bridge_result_summary.get("expected_atomic_run_count") or 0)
        == sum(int(row.get("expected_atomic_run_count") or 0) for row in generated_configs)
        and int(bridge_result_summary.get("feature_leakage_violation_count") or 0) == 0
        and bridge_result_summary.get("can_support_final_method_selection") is False
        and not bridge_results.get("failed_checks")
    )
    if bridge_results:
        source_artifacts["dataset_final_gate_post_selection_validation_bridge_results"] = rel(
            bridge_results_path, root
        )
    reported_execution_status = "config_generated_not_yet_run"
    observed_execution_status = (
        "ledgers_completed" if bridge_results_complete else "results_not_complete"
    ) if bridge_results else "not_observed"
    reconciled_execution_status = (
        "completed_bridge_results" if bridge_results_complete else reported_execution_status
    )
    reconciliation_status = (
        "reconciled_bridge_results_completed"
        if bridge_results_complete
        else (
            "unreconciled_bridge_results_not_complete"
            if bridge_results
            else "no_bridge_results_to_reconcile"
        )
    )
    for row in generated_configs:
        row["reported_execution_status"] = reported_execution_status
        row["observed_execution_status"] = observed_execution_status
        row["reconciled_execution_status"] = reconciled_execution_status
        row["execution_status"] = reconciled_execution_status
        row["execution_reconciliation_status"] = reconciliation_status
        row["execution_reconciliation_requires_action"] = (
            reconciliation_status == "unreconciled_bridge_results_not_complete"
        )
        if bridge_results:
            row["bridge_results_path"] = rel(bridge_results_path, root)
            row["bridge_results_overall_status"] = bridge_result_summary.get(
                "overall_status"
            )
            row["bridge_results_expected_atomic_run_count"] = (
                bridge_result_summary.get("expected_atomic_run_count")
            )
            row["bridge_results_completed_atomic_run_count"] = (
                bridge_result_summary.get("completed_atomic_run_count")
            )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "source_artifacts": source_artifacts,
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "overall_status": status,
            "failed_check_count": len(failed_checks),
            "execution_status": reconciled_execution_status,
            "reported_execution_status": reported_execution_status,
            "observed_execution_status": observed_execution_status,
            "execution_reconciliation_status": reconciliation_status,
            "execution_reconciliation_requires_action": (
                reconciliation_status == "unreconciled_bridge_results_not_complete"
            ),
            "claim_status": "post_selection_validation_bridge_ready_no_promotions",
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
            "missing_from_standard_post_selection_batch": True,
            "bridge_source": "uci_wine_quality_duplicate_sensitivity_model_family_sweep",
            "source_ledger_row_count": manifest_row["source_ledger_row_count"],
            "source_completed_ledger_row_count": manifest_row[
                "source_completed_ledger_row_count"
            ],
            "source_feature_leakage_violation_count": manifest_row[
                "source_feature_leakage_violation_count"
            ],
            "bridge_results_available": bool(bridge_results),
            "bridge_results_overall_status": bridge_result_summary.get(
                "overall_status"
            ),
            "bridge_results_expected_atomic_run_count": bridge_result_summary.get(
                "expected_atomic_run_count"
            ),
            "bridge_results_completed_atomic_run_count": bridge_result_summary.get(
                "completed_atomic_run_count"
            ),
            "bridge_results_feature_leakage_violation_count": bridge_result_summary.get(
                "feature_leakage_violation_count"
            ),
            "validation_design": (
                "1 raw UCI Wine dataset x 3 independent seeds x 5 alphas x 3 "
                "candidate methods x 1 representative ridge model"
            ),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "generated_configs": generated_configs,
        "run_commands": [row["runner_command"] for row in generated_configs],
    }
    return payload, [(out_config_path, config)]


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Dataset Final Gate Post-Selection Validation Bridge",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Execution status: `{summary['execution_status']}`",
        f"- Reported execution status: `{summary['reported_execution_status']}`",
        f"- Observed execution status: `{summary['observed_execution_status']}`",
        f"- Execution reconciliation: `{summary['execution_reconciliation_status']}`",
        f"- Generated configs: {summary['generated_config_count']}",
        f"- Expected atomic runs: {summary['expected_atomic_run_count']}",
        f"- Bridge results completed atomic runs: {summary['bridge_results_completed_atomic_run_count']}",
        f"- Validation seeds: `{summary['validation_seeds']}`",
        f"- Target alphas: `{summary['target_alphas']}`",
        f"- Candidate methods: `{summary['candidate_methods']}`",
        f"- Source ledger rows: {summary['source_ledger_row_count']}",
        f"- Source feature-leakage violations: {summary['source_feature_leakage_violation_count']}",
        f"- Claim status: `{summary['claim_status']}`",
        "",
        "This artifact is a bridge work queue, not a final method-selection record.",
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
                source=row["source_model_family_sweep_config"],
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
        source_config_path=(root / args.source_config).resolve(),
        source_report_path=(root / args.source_report).resolve(),
        source_feature_audit_path=(root / args.source_feature_audit).resolve(),
        remediation_plan_path=(root / args.remediation_plan).resolve(),
        bridge_results_path=(root / args.bridge_results).resolve(),
        config_dir=(root / args.config_dir).resolve(),
        results_root=(root / args.results_root).resolve(),
        dataset_id=str(args.dataset_id),
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
