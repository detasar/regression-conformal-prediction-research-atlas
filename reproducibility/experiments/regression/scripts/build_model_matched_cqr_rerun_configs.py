"""Generate model-matched CQR rerun configs from model-family sweeps."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_model_matched_cqr_rerun_manifest_v1"
SUFFIX = "_model_matched_cqr_v1"
DEFAULT_CONFIG_DIR = Path("experiments/regression/configs")
DEFAULT_MANIFEST_JSON = Path(
    "experiments/regression/reports/model_matched_cqr_rerun_plan/"
    "model_matched_cqr_rerun_manifest.json"
)
DEFAULT_SOURCE_GLOB = "model_family_sweep_*.yaml"
MODEL_MATCHED_CQR_PARAMS = {
    "quantile_regressor_alpha": 0.0001,
    "quantile_solver": "highs",
    "nystroem_components": 200,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument(
        "--source-glob",
        default=DEFAULT_SOURCE_GLOB,
        help="Glob under the config directory for source model-family configs.",
    )
    parser.add_argument(
        "--config-dir",
        default=str(DEFAULT_CONFIG_DIR),
        help="Config directory, relative to repo root unless absolute.",
    )
    parser.add_argument(
        "--manifest-json",
        default=str(DEFAULT_MANIFEST_JSON),
        help="Output manifest JSON path, relative to repo root unless absolute.",
    )
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def grid_size(grid: dict[str, Any]) -> int:
    size = 1
    for values in (grid or {}).values():
        size *= len(values or [])
    return size


def model_grid_size(config: dict[str, Any]) -> int:
    return sum(grid_size(model.get("grid") or {}) for model in config.get("models") or [])


def expected_run_count(config: dict[str, Any]) -> int:
    return (
        len(config.get("datasets") or [])
        * len(config.get("random_seeds") or [])
        * len(config.get("alphas") or [])
        * model_grid_size(config)
        * len(config.get("cp_methods") or [])
    )


def source_has_cqr(config: dict[str, Any]) -> bool:
    if "cqr" in set(config.get("cp_methods") or []):
        return True
    method_configs = config.get("cp_method_configs") or {}
    if isinstance(method_configs, dict):
        return any(
            str(value.get("method_id", key)) == "cqr"
            for key, value in method_configs.items()
            if isinstance(value, dict)
        )
    return False


def generated_stem(source_path: Path) -> str:
    stem = source_path.stem
    return stem if stem.endswith(SUFFIX) else f"{stem}{SUFFIX}"


def generated_experiment_id(source_config: dict[str, Any], source_path: Path) -> str:
    source_id = str(source_config.get("experiment_id") or source_path.stem)
    if source_id.endswith("_v0"):
        source_id = source_id[:-3]
    if source_id.endswith(SUFFIX):
        return source_id
    return f"{source_id}{SUFFIX}"


def clone_config(source_path: Path, config: dict[str, Any], root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    stem = generated_stem(source_path)
    experiment_id = generated_experiment_id(config, source_path)
    result_dir = Path("experiments/regression/results") / stem
    generated_path = Path("experiments/regression/configs") / f"{stem}.yaml"

    methods = []
    for method in config.get("cp_methods") or []:
        if str(method) == "cqr":
            methods.append("cqr_model_matched")
        else:
            methods.append(str(method))
    if "cqr_model_matched" not in methods:
        methods.append("cqr_model_matched")

    method_configs = dict(config.get("cp_method_configs") or {})
    cleaned_method_configs = {}
    for label, value in method_configs.items():
        if str(label) == "cqr":
            continue
        if isinstance(value, dict) and str(value.get("method_id", label)) == "cqr":
            continue
        cleaned_method_configs[label] = value
    cleaned_method_configs["cqr_model_matched"] = {
        "method_id": "cqr_model_matched",
        "params": dict(MODEL_MATCHED_CQR_PARAMS),
    }

    quality_controls = dict(config.get("quality_controls") or {})
    quality_controls.pop("interpret_cqr_as_fixed_quantile_backend", None)
    quality_controls.update(
        {
            "interpret_cqr_as_model_matched_quantile_backend": True,
            "historical_fixed_gbm_cqr_preserved_as_comparator": True,
            "requires_cqr_fixed_vs_model_matched_synthesis": True,
            "no_method_winner_claim": True,
        }
    )

    generated = dict(config)
    generated["experiment_id"] = experiment_id
    generated["purpose"] = (
        "Model-matched CQR backend rerun cloned from "
        f"{source_path.as_posix()}. Historical fixed-GBM CQR rows remain "
        "unchanged as comparator evidence; this rerun tests whether the CQR "
        "backend confounded the original model-family sweep surface. The output "
        "is descriptive pipeline-level evidence only and does not authorize a "
        "method winner or production recommendation."
    )
    generated["cp_methods"] = methods
    generated["cp_method_configs"] = cleaned_method_configs
    generated["quality_controls"] = quality_controls
    generated["rerun_metadata"] = {
        "schema": "cpfi_regression_model_matched_cqr_rerun_config_v1",
        "source_config": source_path.as_posix(),
        "source_experiment_id": config.get("experiment_id"),
        "generated_from_method": "replace_cqr_with_cqr_model_matched",
        "historical_cqr_method_id": "cqr",
        "new_method_id": "cqr_model_matched",
        "config_suffix": SUFFIX,
        "fixed_gbm_cqr_rows_preserved": True,
        "final_prose_boundary": "pipeline_level_descriptive_signal_only",
    }
    generated["logging"] = {
        "ledger": (result_dir / "ledger.jsonl").as_posix(),
        "checkpoint_root": (result_dir / "checkpoints").as_posix(),
        "prediction_cache_root": (result_dir / "checkpoints" / "predictions").as_posix(),
    }

    cqr_run_count = (
        len(generated.get("datasets") or [])
        * len(generated.get("random_seeds") or [])
        * len(generated.get("alphas") or [])
        * model_grid_size(generated)
    )
    manifest_row = {
        "source_config": source_path.as_posix(),
        "generated_config": generated_path.as_posix(),
        "source_experiment_id": config.get("experiment_id"),
        "experiment_id": experiment_id,
        "datasets": list(generated.get("datasets") or []),
        "alphas": list(generated.get("alphas") or []),
        "random_seeds": list(generated.get("random_seeds") or []),
        "model_grid_size": model_grid_size(generated),
        "cp_methods": list(generated.get("cp_methods") or []),
        "expected_atomic_run_count": expected_run_count(generated),
        "expected_cqr_model_matched_run_count": cqr_run_count,
        "ledger": generated["logging"]["ledger"],
        "checkpoint_root": generated["logging"]["checkpoint_root"],
        "runner_command": (
            "python -m experiments.regression.scripts.run_regression_pilot "
            f"--config {generated_path.as_posix()}"
        ),
    }
    return generated, manifest_row


def build_payload(root: Path, config_dir: Path, source_glob: str) -> tuple[dict[str, Any], dict[Path, dict[str, Any]]]:
    generated_configs: dict[Path, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for source_path in sorted(config_dir.glob(source_glob)):
        if source_path.stem.endswith(SUFFIX):
            skipped.append(
                {
                    "source_config": rel(source_path, root),
                    "reason": "already_generated_model_matched_cqr_config",
                }
            )
            continue
        source_rel = Path(rel(source_path, root))
        config = read_yaml(source_path)
        if not source_has_cqr(config):
            skipped.append(
                {
                    "source_config": source_rel.as_posix(),
                    "reason": "source_config_has_no_cqr_surface",
                }
            )
            continue
        generated, row = clone_config(source_rel, config, root)
        generated_path = root / row["generated_config"]
        generated_configs[generated_path] = generated
        rows.append(row)

    total_expected = sum(int(row["expected_atomic_run_count"]) for row in rows)
    total_cqr_expected = sum(
        int(row["expected_cqr_model_matched_run_count"]) for row in rows
    )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "status": "ready" if rows else "empty",
            "source_glob": source_glob,
            "generated_config_count": len(rows),
            "skipped_source_count": len(skipped),
            "expected_atomic_run_count": total_expected,
            "expected_cqr_model_matched_run_count": total_cqr_expected,
            "method_boundary": "descriptive_pipeline_level_signal_only",
            "fixed_gbm_cqr_rows_preserved": True,
        },
        "generated_configs": rows,
        "skipped_sources": skipped,
        "run_commands": [row["runner_command"] for row in rows],
    }
    return payload, generated_configs


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Model-Matched CQR Rerun Manifest",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated configs: {summary['generated_config_count']}",
        f"- Expected atomic runs: {summary['expected_atomic_run_count']}",
        (
            "- Expected `cqr_model_matched` runs: "
            f"{summary['expected_cqr_model_matched_run_count']}"
        ),
        "- Boundary: descriptive pipeline-level signal only; no method winner claim.",
        "- Historical fixed-GBM CQR rows are preserved as comparator evidence.",
        "",
        "## Generated Configs",
        "",
    ]
    rows = payload.get("generated_configs") or []
    if rows:
        lines.append(
            "| generated_config | source_config | expected_atomic_run_count | expected_cqr_model_matched_run_count |"
        )
        lines.append("| --- | --- | ---: | ---: |")
        for row in rows:
            lines.append(
                "| {generated_config} | {source_config} | {runs} | {cqr_runs} |".format(
                    generated_config=row["generated_config"],
                    source_config=row["source_config"],
                    runs=row["expected_atomic_run_count"],
                    cqr_runs=row["expected_cqr_model_matched_run_count"],
                )
            )
    else:
        lines.append("No generated configs.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    config_dir = resolve(root, args.config_dir)
    manifest_json = resolve(root, args.manifest_json)
    payload, generated_configs = build_payload(root, config_dir, args.source_glob)
    for path, config in generated_configs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
    atomic_write_json(manifest_json, payload)
    atomic_write_text(manifest_json.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["status"],
                "generated_config_count": payload["summary"]["generated_config_count"],
                "expected_atomic_run_count": payload["summary"][
                    "expected_atomic_run_count"
                ],
                "expected_cqr_model_matched_run_count": payload["summary"][
                    "expected_cqr_model_matched_run_count"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
