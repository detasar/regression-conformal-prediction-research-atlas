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
    assert "public_status_counts" in manifest["summary"]
    assert all(row.get("public_status") for row in manifest["artifacts"])


def test_public_atlas_scope_catalogs_and_claims_are_consistent() -> None:
    root = repo_root()
    assert (root / "paper/research_document.html").exists()
    assert (root / "atlas/index.html").exists()
    scope = json.loads((root / "atlas/scope/experiment_scope.json").read_text(encoding="utf-8"))
    dataset_catalog = json.loads((root / "atlas/datasets/dataset_catalog.json").read_text(encoding="utf-8"))
    method_ontology = json.loads((root / "atlas/methods/method_ontology.json").read_text(encoding="utf-8"))
    claim_registry = json.loads((root / "atlas/claims/claim_registry.json").read_text(encoding="utf-8"))
    kg = json.loads((root / "site/kg_browser_data.json").read_text(encoding="utf-8"))

    assert scope["publication_scoped_completed_rows"] == 145839
    assert scope["publication_dataset_count"] == 67
    assert scope["publication_dataset_alpha_cell_count"] == 95
    assert scope["publication_method_label_count"] == 28
    assert scope["kg_node_count"] == len(kg["nodes"])
    assert scope["kg_edge_count"] == len(kg["edges"])

    included_datasets = [
        row for row in dataset_catalog["datasets"] if row["publication_included"]
    ]
    assert len(included_datasets) == scope["publication_dataset_count"]
    for row in included_datasets:
        assert (root / row["public_card_path"]).exists()

    result_methods = set()
    with (root / "atlas/results/result_cube_public.csv").open(encoding="utf-8", newline="") as handle:
        import csv

        for row in csv.DictReader(handle):
            result_methods.add(row["method_label"])
    ontology_methods = {row["method_label"] for row in method_ontology["methods"]}
    assert result_methods <= ontology_methods
    assert all(row.get("evidence_gate") for row in claim_registry["claims"])
    assert {route["route_id"] for route in kg["research_map"]} >= {
        "experiment_scope",
        "method_universe",
        "cqr_cvplus_signal",
        "venn_abers_bridge",
        "closed_gates",
    }


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
