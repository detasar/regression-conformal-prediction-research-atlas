"""Public Research Atlas smoke tests."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.artifact_public]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_public_research_atlas_core_imports() -> None:
    assert importlib.import_module("cpfi")
    assert importlib.import_module("cpfi.models")
    assert importlib.import_module("cpfi.models.trainers")
    assert importlib.import_module("cpfi.regression.conformal")
    assert importlib.import_module("experiments.regression.scripts.run_regression_pilot")


def test_public_kg_and_artifact_manifest_are_consistent() -> None:
    root = repo_root()
    kg_path = root / "site" / "kg_browser_data.json"
    manifest_path = root / "evidence" / "public_artifact_manifest.json"
    assert kg_path.exists()
    assert manifest_path.exists()
    kg = json.loads(kg_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(kg["nodes"]) == kg["summary"]["node_count"]
    assert len(kg["edges"]) == kg["summary"]["edge_count"]
    assert kg["summary"]["public_artifact_manifest"] == "evidence/public_artifact_manifest.json"
    assert manifest["strategy"] == "manifest_plus_summary_not_full_artifact_dump"
    assert manifest["summary"]["kg_source_and_evidence_path_coverage"] == 1.0


def test_public_root_command_help_runs() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root() / "reproducibility")
    result = subprocess.run(
        [sys.executable, "-m", "experiments.regression.scripts.run_regression_pilot", "--help"],
        cwd=repo_root(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage: run_regression_pilot.py" in result.stdout
    assert "--config CONFIG" in result.stdout
    assert "--max-runs MAX_RUNS" in result.stdout
