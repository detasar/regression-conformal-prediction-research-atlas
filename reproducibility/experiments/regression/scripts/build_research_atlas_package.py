"""Validate the Research Atlas package from a clean checkout."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def validate_package(package_root: Path) -> dict:
    required = {
        "README.md": "reader entry point",
        "CITATION.cff": "citation metadata",
        "paper/research_document.html": "integrated Research Document",
        "paper/article.pdf": "compact report PDF",
        "paper/supplement.pdf": "supplement PDF",
        "site/kg_browser.html": "knowledge graph browser",
        "site/kg_browser_data.json": "knowledge graph data",
        "site/kg_browser_index.json": "knowledge graph index data",
        "site/kg_browser_edges.json": "knowledge graph edge bundle",
        "evidence/claim_evidence_matrix.md": "claim-evidence matrix",
        "evidence/public_artifact_manifest.json": "artifact manifest",
        "atlas/index.html": "Research Atlas site",
        "pyproject.toml": "install metadata",
        "pytest.ini": "public test config",
        "reproducibility/environment/public_environment_lock.json": "public smoke environment lock",
        "reproducibility/environment/public_environment_lock.md": "public smoke environment lock documentation",
        "reproducibility/environment/requirements-public-lock.txt": "public smoke dependency pins",
    }
    rows = []
    for rel, role in required.items():
        path = package_root / rel
        rows.append({"path": rel, "role": role, "exists": path.exists()})
    missing = [row["path"] for row in rows if not row["exists"]]
    config_dir = package_root / "reproducibility/experiments/regression/configs"
    config_files = sorted(config_dir.glob("*.yaml")) if config_dir.exists() else []
    pilot_config = config_dir / "pilot.yaml"
    runner_script = (
        package_root
        / "reproducibility/experiments/regression/scripts/run_regression_pilot.py"
    )
    expected_config_count = 184
    config_failures = []
    if not config_dir.exists():
        config_failures.append("missing reproducibility/experiments/regression/configs")
    if len(config_files) != expected_config_count:
        config_failures.append(
            f"expected {expected_config_count} YAML configs, found {len(config_files)}"
        )
    if not pilot_config.exists():
        config_failures.append("missing pilot.yaml")
    if not runner_script.exists():
        config_failures.append("missing run_regression_pilot.py")
    payload = {
        "schema": "regression_cp_public_research_atlas_package_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not missing and not config_failures else "fail",
        "required_file_count": len(required),
        "missing": missing,
        "files": rows,
        "package_data": {
            "experiment_config_count": len(config_files),
            "expected_experiment_config_count": expected_config_count,
            "pilot_config_exists": pilot_config.exists(),
            "runner_script_exists": runner_script.exists(),
            "default_config_resolution": (
                "packaged_layout" if pilot_config.exists() else "missing"
            ),
            "default_config_path": (
                "reproducibility/experiments/regression/configs/pilot.yaml"
                if pilot_config.exists()
                else None
            ),
            "config_failures": config_failures,
        },
        "rebuild_commands": [
            "python -m experiments.regression.scripts.build_public_release_scope --package-root .",
            "python -m experiments.regression.scripts.build_public_research_atlas --package-root .",
            "python -m experiments.regression.scripts.build_research_atlas_package --package-root .",
            "python -m pytest -m \"unit or artifact_public or smoke\"",
        ],
    }
    if missing:
        raise FileNotFoundError(f"Missing public package files: {missing}")
    if config_failures:
        raise ValueError(f"Public package config-data failures: {config_failures}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", default=".")
    parser.add_argument(
        "--out",
        default="atlas/provenance/public_rebuild_manifest.json",
        help="Path relative to the package root.",
    )
    args = parser.parse_args()
    root = Path(args.package_root).resolve()
    payload = validate_package(root)
    atomic_write_json(root / args.out, payload)
    print(json.dumps({"status": payload["status"], "out": args.out}, sort_keys=True))


if __name__ == "__main__":
    main()
