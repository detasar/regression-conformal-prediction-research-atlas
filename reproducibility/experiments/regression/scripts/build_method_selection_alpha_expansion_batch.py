"""Materialize the next alpha-support expansion batch.

The alpha-expansion planner produces dataset-alpha-method work items. This
script turns that plan into resumable runner configs plus a manifest. It keeps
the batch deliberately scoped: representative source models, current shortlisted
methods, and target alphas only. The output is execution support evidence, not a
final method-selection claim.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_method_selection_alpha_expansion_batch_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_PLAN = REPORT_DIR / "method_selection_alpha_expansion_plan.json"
DEFAULT_OUT = REPORT_DIR / "method_selection_alpha_expansion_batch.json"
DEFAULT_CONFIG_DIR = Path("experiments/regression/configs")
DEFAULT_RESULTS_ROOT = Path("experiments/regression/results")
DEFAULT_BATCH_ID = "method_selection_alpha_expansion_next_batch_v1"

CLAIM_BOUNDARIES = [
    "This batch materializes the planner's next dataset-alpha tasks; it does not select a final conformal method.",
    "Generated configs are restricted to the current shortlisted methods and target alphas from the plan.",
    "Generated configs use one representative source model configuration per dataset to expand common support without rerunning full exploratory model-family grids.",
    "Rows produced by this batch must be re-synthesized and re-audited before any final method-selection, fairness, endpoint, bounded-support, or Venn-Abers validation claim is promoted.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="Plan JSON path.")
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


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def canonical_alpha(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    if math.isnan(number) or math.isinf(number):
        return str(value).strip()
    return f"{number:.12g}"


def alpha_sort_key(value: Any) -> tuple[int, float | str]:
    text = canonical_alpha(value)
    try:
        return (0, float(text))
    except ValueError:
        return (1, text)


def alpha_float(value: Any) -> float:
    return float(canonical_alpha(value))


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "unnamed"


def listify_grid_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value[:1] if value else []
    return [value]


def representative_model(source_config: dict[str, Any]) -> dict[str, Any]:
    models = source_config.get("models") or []
    if not isinstance(models, list) or not models:
        return {}
    selected = None
    for model in models:
        if str(model.get("model_id")) == "ridge":
            selected = model
            break
    if selected is None:
        selected = models[0]
    selected = deepcopy(selected)
    grid = selected.get("grid") or {}
    selected["grid"] = {
        str(key): listify_grid_value(value) for key, value in grid.items()
    }
    return selected


def model_grid_size(model: dict[str, Any]) -> int:
    size = 1
    for value in (model.get("grid") or {}).values():
        size *= len(value if isinstance(value, list) else [value])
    return size


def task_groups(plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in plan.get("next_batch_dataset_alpha_tasks") or []:
        dataset_id = str(task.get("dataset_id") or "").strip()
        if dataset_id:
            grouped[dataset_id].append(task)
    return dict(sorted(grouped.items()))


def choose_source_config(
    root: Path, tasks: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any], Path | None]:
    for task in tasks:
        for source in task.get("source_configs") or []:
            config_path_value = source.get("config_path")
            if not config_path_value:
                continue
            config_path = root / str(config_path_value)
            source_config = read_yaml(config_path)
            if source_config:
                return source, source_config, config_path
    return {}, {}, None


def generated_config_path(config_dir: Path, dataset_id: str) -> Path:
    return config_dir / f"method_selection_alpha_expansion_{slugify(dataset_id)}.yaml"


def result_slug(dataset_id: str) -> str:
    return f"method_selection_alpha_expansion_{slugify(dataset_id)}"


def build_generated_config(
    *,
    batch_id: str,
    dataset_id: str,
    tasks: list[dict[str, Any]],
    source: dict[str, Any],
    source_config: dict[str, Any],
    source_config_path: Path | None,
    plan_path: Path,
    out_config_path: Path,
    results_root: Path,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    target_alphas = sorted(
        {canonical_alpha(task.get("target_alpha")) for task in tasks},
        key=alpha_sort_key,
    )
    cp_methods: list[str] = []
    for task in sorted(tasks, key=lambda row: alpha_sort_key(row.get("target_alpha"))):
        for method in task.get("missing_candidate_methods") or []:
            method = str(method)
            if method not in cp_methods:
                cp_methods.append(method)
    model = representative_model(source_config)
    seeds = list(source_config.get("random_seeds") or [])
    result_dir = results_root / result_slug(dataset_id)
    source_rel = rel(source_config_path, root) if source_config_path else None
    plan_rel = rel(plan_path, root)
    config_rel = rel(out_config_path, root)
    source_experiment_id = source_config.get("experiment_id")
    experiment_id = f"regression_method_selection_alpha_expansion_{slugify(dataset_id)}_v1"
    quality_controls = dict(source_config.get("quality_controls") or {})
    quality_controls.update(
        {
            "method_selection_alpha_expansion_batch": True,
            "support_expansion_only_no_final_selection": True,
            "no_final_method_selection_claim": True,
            "candidate_methods_restricted_to_current_shortlist": True,
            "target_alphas_from_alpha_expansion_plan": True,
            "representative_source_model_only": True,
            "full_model_family_sweep_not_rerun": True,
            "requires_post_batch_resynthesis_and_reaudit": True,
            "forbid_final_model_selection_claims": True,
            "forbid_validated_venn_abers_regression_claims": True,
        }
    )
    ledger_path = rel(result_dir / "ledger.jsonl", root)
    checkpoint_root = rel(result_dir / "checkpoints", root)
    prediction_cache_root = rel(result_dir / "checkpoints/predictions", root)
    config = {
        "experiment_id": experiment_id,
        "purpose": (
            "Method-selection alpha-support expansion batch for "
            f"{dataset_id}. The config clones audited split/preprocessing/runtime "
            "settings from a traced source config, restricts methods to the current "
            "shortlist, and expands target alpha support only. It is support "
            "evidence, not final model or conformal-method selection evidence."
        ),
        "random_seeds": seeds,
        "alphas": [alpha_float(alpha) for alpha in target_alphas],
        "target_transform": source_config.get("target_transform", "identity"),
        "splits": deepcopy(source_config.get("splits") or {}),
        "conformal": deepcopy(source_config.get("conformal") or {}),
        "datasets": [dataset_id],
        "models": [model] if model else [],
        "cp_methods": cp_methods,
        "quality_controls": quality_controls,
        "alpha_expansion_provenance": {
            "schema": SCHEMA,
            "batch_id": batch_id,
            "source_plan": plan_rel,
            "source_config": source_rel,
            "source_experiment_id": source_experiment_id,
            "dataset_alpha_task_ids": [task.get("task_id") for task in tasks],
            "claim_boundary": "support_expansion_only_no_final_selection",
        },
        "logging": {
            "ledger": ledger_path,
            "checkpoint_root": checkpoint_root,
            "prediction_cache_root": prediction_cache_root,
        },
    }
    expected_runs = (
        len(seeds)
        * len(target_alphas)
        * max(model_grid_size(model), 0)
        * len(cp_methods)
    )
    manifest_row = {
        "dataset_id": dataset_id,
        "config_path": config_rel,
        "experiment_id": experiment_id,
        "source_config_path": source_rel,
        "source_config_id": source.get("config_id"),
        "source_experiment_id": source_experiment_id,
        "target_alphas": target_alphas,
        "cp_methods": cp_methods,
        "random_seeds": seeds,
        "model_id": model.get("model_id"),
        "model_family": model.get("family"),
        "model_grid": model.get("grid"),
        "model_grid_size": model_grid_size(model) if model else 0,
        "planned_dataset_alpha_task_ids": [task.get("task_id") for task in tasks],
        "planned_dataset_alpha_task_count": len(tasks),
        "planned_method_run_task_count": sum(
            int(task.get("method_run_task_count") or 0) for task in tasks
        ),
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


def validate_manifest(
    plan: dict[str, Any],
    generated_configs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    plan_tasks = plan.get("next_batch_dataset_alpha_tasks") or []
    plan_task_ids = {str(task.get("task_id")) for task in plan_tasks}
    covered_task_ids = {
        str(task_id)
        for row in generated_configs
        for task_id in row.get("planned_dataset_alpha_task_ids") or []
    }
    expected_methods = {
        method
        for task in plan_tasks
        for method in (task.get("missing_candidate_methods") or [])
    }
    config_methods = {
        method
        for row in generated_configs
        for method in (row.get("cp_methods") or [])
    }
    checks = [
        {
            "check_id": "plan_ready",
            "status": (
                "pass"
                if (plan.get("summary") or {}).get("overall_status")
                == "method_selection_alpha_expansion_plan_ready"
                else "fail"
            ),
            "observed": {
                "overall_status": (plan.get("summary") or {}).get("overall_status")
            },
        },
        {
            "check_id": "all_next_batch_tasks_covered_once",
            "status": "pass" if plan_task_ids == covered_task_ids else "fail",
            "observed": {
                "plan_task_count": len(plan_task_ids),
                "covered_task_count": len(covered_task_ids),
                "missing_task_ids": sorted(plan_task_ids - covered_task_ids),
                "extra_task_ids": sorted(covered_task_ids - plan_task_ids),
            },
        },
        {
            "check_id": "configs_restrict_to_missing_methods",
            "status": "pass" if config_methods == expected_methods else "fail",
            "observed": {
                "expected_methods": sorted(expected_methods),
                "config_methods": sorted(config_methods),
            },
        },
        {
            "check_id": "source_config_traceability_present",
            "status": (
                "pass"
                if generated_configs
                and all(row.get("source_config_path") for row in generated_configs)
                else "fail"
            ),
            "observed": {
                "generated_config_count": len(generated_configs),
                "without_source_config": [
                    row["config_path"]
                    for row in generated_configs
                    if not row.get("source_config_path")
                ],
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
                row["dataset_id"]: row.get("model_grid_size")
                for row in generated_configs
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
            "status": (
                "pass"
                if (plan.get("summary") or {}).get("can_support_final_method_selection")
                is False
                else "fail"
            ),
            "observed": {
                "plan_can_support_final_method_selection": (
                    plan.get("summary") or {}
                ).get("can_support_final_method_selection"),
                "batch_claim_status": "support_expansion_batch_ready_no_final_selection",
            },
        },
    ]
    return checks


def build_payload(
    root: Path,
    plan_path: Path,
    config_dir: Path,
    results_root: Path,
    batch_id: str,
) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    plan = read_json(plan_path)
    grouped = task_groups(plan)
    config_writes: list[tuple[Path, dict[str, Any]]] = []
    generated_configs: list[dict[str, Any]] = []
    for dataset_id, tasks in grouped.items():
        source, source_config, source_config_path = choose_source_config(root, tasks)
        out_config_path = generated_config_path(config_dir, dataset_id)
        config, manifest_row = build_generated_config(
            batch_id=batch_id,
            dataset_id=dataset_id,
            tasks=tasks,
            source=source,
            source_config=source_config,
            source_config_path=source_config_path,
            plan_path=plan_path,
            out_config_path=out_config_path,
            results_root=results_root,
            root=root,
        )
        config_writes.append((out_config_path, config))
        generated_configs.append(manifest_row)
    alpha_counts = Counter(
        alpha for row in generated_configs for alpha in (row.get("target_alphas") or [])
    )
    checks = validate_manifest(plan, generated_configs)
    failed_checks = [check for check in checks if check["status"] != "pass"]
    status = (
        "method_selection_alpha_expansion_batch_ready"
        if not failed_checks and generated_configs
        else "method_selection_alpha_expansion_batch_failed"
    )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "source_artifacts": {
            "method_selection_alpha_expansion_plan": rel(plan_path, root),
        },
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "overall_status": status,
            "failed_check_count": len(failed_checks),
            "execution_status": "configs_generated_not_yet_run",
            "claim_status": "support_expansion_batch_ready_no_final_selection",
            "can_support_final_method_selection": False,
            "generated_config_count": len(generated_configs),
            "dataset_count": len(generated_configs),
            "planned_dataset_alpha_task_count": sum(
                int(row.get("planned_dataset_alpha_task_count") or 0)
                for row in generated_configs
            ),
            "planned_method_run_task_count": sum(
                int(row.get("planned_method_run_task_count") or 0)
                for row in generated_configs
            ),
            "expected_atomic_run_count": sum(
                int(row.get("expected_atomic_run_count") or 0)
                for row in generated_configs
            ),
            "candidate_methods": sorted(
                {
                    method
                    for row in generated_configs
                    for method in (row.get("cp_methods") or [])
                }
            ),
            "target_alpha_counts_by_generated_config": dict(
                sorted(alpha_counts.items(), key=lambda item: alpha_sort_key(item[0]))
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
        "# Method Selection Alpha Expansion Batch",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Execution status: `{summary['execution_status']}`",
        f"- Generated configs: {summary['generated_config_count']}",
        f"- Planned dataset-alpha tasks: {summary['planned_dataset_alpha_task_count']}",
        f"- Planned method-run tasks: {summary['planned_method_run_task_count']}",
        f"- Expected atomic runs: {summary['expected_atomic_run_count']}",
        f"- Candidate methods: `{summary['candidate_methods']}`",
        f"- Target alpha coverage: `{summary['target_alpha_counts_by_generated_config']}`",
        f"- Claim status: `{summary['claim_status']}`",
        "",
        "This batch does not select a final conformal method.",
        "",
        "## Generated Configs",
        "",
        "| dataset | config | target alphas | methods | seeds | model | expected runs |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in payload["generated_configs"]:
        lines.append(
            "| `{dataset}` | `{config}` | `{alphas}` | `{methods}` | `{seeds}` | `{model}` | {runs} |".format(
                dataset=row["dataset_id"],
                config=row["config_path"],
                alphas=row["target_alphas"],
                methods=row["cp_methods"],
                seeds=row["random_seeds"],
                model=row["model_id"],
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
    plan_path = (root / args.plan).resolve()
    config_dir = (root / args.config_dir).resolve()
    results_root = (root / args.results_root).resolve()
    payload, config_writes = build_payload(
        root=root,
        plan_path=plan_path,
        config_dir=config_dir,
        results_root=results_root,
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
