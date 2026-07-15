"""Research Atlas smoke tests."""

from __future__ import annotations

import importlib
import importlib.resources as resources
import csv
import gzip
import json
import os
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urlparse

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.artifact_public]

FORBIDDEN_PUBLIC_PHRASES = tuple(
    " ".join(parts)
    for parts in (
        ("Document", "status"),
        (
            "Document",
            "status:",
            "Research",
            "Document",
            "release",
            "render,",
            "part",
            "of",
            "the",
            "public",
            "Research",
            "Atlas,",
            "and",
            "not",
            "a",
            "method",
            "recommendation.",
        ),
        ("Research", "Document", "release", "render"),
        ("private", "final-prose"),
        ("not", "final", "manuscript", "prose"),
        ("not", "a", "release", "artifact"),
        ("not", "a", "method", "recommendation"),
        ("not", "method", "recommendations"),
        ("not", "a", "method-selection", "claim"),
        ("not", "a", "method-selection", "result"),
        ("not", "a", "final", "selected", "method"),
        ("not", "as", "recommended", "methods"),
        ("not", "as", "a", "ranking", "rule"),
        ("navigation", "and", "traceability"),
        ("navigation", "and", "traceability", "artifact"),
        ("navigation", "and", "traceability", "artifacts"),
        ("navigation", "artifacts"),
        ("does", "not", "recommend", "a", "conformal", "method"),
        ("supplementary/web", "artifact"),
        ("KG", "browser", "accepted"),
        ("Current", "release", "status"),
        ("Public", "repository", "released"),
        ("edge", "selector", "provenance", "coverage"),
        ("Edge", "selector", "provenance", "coverage"),
        ("Claim-edge", "selector", "provenance", "coverage"),
        ("reader", "review", "package"),
        ("reader" + "-safe",),
        ("Reader" + "-safe", "statement"),
        ("Reader" + "-safe", "statements"),
        ("working", "claim", "tracing"),
        ("traceability", "artifacts", "are", "review", "infrastructure"),
        ("citable", "web-artifact"),
        ("artifact", "family"),
        ("Guarantee", "Boundary", "Ledger"),
        ("guarantee", "boundary", "ledger"),
        ("working", "review", "architecture"),
        ("working", "review", "only"),
        ("This", "output", "is", "generated", "for", "working", "review"),
        ("not", "Research", "Atlas"),
        ("Working", "site"),
        ("working", "navigation", "artifacts"),
        ("working", "reviewer"),
        ("working", "package"),
        ("working", "source"),
        ("internal", "evidence", "artifact"),
        ("sterile", "repository"),
        ("sterile" + "-repository",),
        ("release", "review"),
        ("sterile", "package", "can", "be", "reviewed", "privately"),
        ("can", "be", "reviewed", "privately"),
        ("private", "review"),
        ("private", "site"),
        ("private", "package"),
        ("public", "site", "deployment"),
        ("without", "opening", "release"),
        ("separate", "publication", "decision"),
        ("citation", "metadata", "require", "separate", "validation"),
        ("Research", "Atlas", "review", "and", "Research", "Atlas", "publication"),
        ("when", "its", "quality", "and", "provenance", "checks", "pass"),
        ("No", "public", "KG", "citation"),
        ("reviewable", "publication", "surfaces"),
        ("not", "a", "deployment", "recommendation"),
        ("reader" + "-facingty",),
        ("reader" + "-safety",),
        ("CQR/CV+", "were", "observed", "as", "strong", "practical", "candidates"),
        ("Read", "CQR/CV+", "as", "strong", "practical", "candidates"),
        ("CQR/CV+", "can", "be", "described", "as", "strong", "practical", "candidates"),
        ("Reading", "note"),
        ("Boundary" + ":", "Do", "not"),
        ("not", "an", "independent", "scientific", "claim"),
        ("Do", "not", "cite"),
        ("not", "yet"),
        ("public", "citation", "waits"),
        ("public", "citable", "component"),
        ("citable", "component"),
        ("citation", "target"),
        ("final", "citable", "public", "artifact"),
        ("release", "state"),
        ("not", "yet", "the", "final", "public", "citable", "repository"),
        ("recommendation", "engine"),
        ("claim", "generator"),
        ("public", "release", "remains", "closed"),
        ("public", "release"),
        ("release", "gate"),
        ("outside", "current", "evidence"),
        ("method", "recommendation"),
        ("method", "guidance"),
        ("positive", "claim", "promotion"),
        ("positive" + "-claim", "promotion"),
        ("positive", "claim"),
        ("positive" + "-claim",),
        ("claim", "promotion"),
        ("claim" + "-promotion",),
        ("Main-claim", "promotion"),
        ("promotion", "beyond", "this", "study"),
        ("part", "of", "the", "public", "Research", "Atlas"),
        ("GitHub", "Pages", "remain", "closed"),
    )
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag in {"a", "link", "script", "img"}:
            value = attr.get("href") or attr.get("src")
            if value:
                self.links.append(value)


class _TableAccessibilityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables = 0
        self.captions = 0
        self.header_cells = 0
        self.scoped_header_cells = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "table":
            self.tables += 1
        elif tag == "caption":
            self.captions += 1
        elif tag == "th":
            self.header_cells += 1
            if attr.get("scope"):
                self.scoped_header_cells += 1


def test_public_research_atlas_core_imports() -> None:
    assert importlib.import_module("cpfi")
    assert importlib.import_module("cpfi.models")
    assert importlib.import_module("cpfi.models.trainers")
    assert importlib.import_module("cpfi.regression.conformal")
    assert importlib.import_module("experiments.regression.scripts.run_regression_pilot")
    assert importlib.import_module("experiments.regression.scripts.build_public_release_scope")
    assert importlib.import_module("experiments.regression.scripts.build_public_research_atlas")
    assert importlib.import_module("experiments.regression.scripts.build_research_atlas_package")


def test_public_package_data_includes_experiment_configs() -> None:
    config_root = resources.files("experiments.regression").joinpath("configs")
    config_names = sorted(
        path.name
        for path in config_root.iterdir()
        if path.name.endswith((".yaml", ".yml"))
    )
    assert "pilot.yaml" in config_names
    assert len(config_names) == 184
    assert any(name.endswith("_model_matched_cqr_v1.yaml") for name in config_names)


def test_public_wheel_contains_experiment_configs(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--wheel-dir",
            str(tmp_path),
        ],
        cwd=repo_root(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    wheels = sorted(tmp_path.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
    config_names = sorted(
        name
        for name in names
        if name.startswith("experiments/regression/configs/")
        and name.endswith((".yaml", ".yml"))
    )
    assert "experiments/regression/configs/pilot.yaml" in names
    assert "experiments/regression/scripts/run_regression_pilot.py" in names
    assert "experiments/regression/policies/data_policy_registry.md" in names
    assert len(config_names) == 184
    assert any(name.endswith("_model_matched_cqr_v1.yaml") for name in config_names)


def test_public_kg_and_artifact_manifest_are_consistent() -> None:
    root = repo_root()
    kg_path = root / "site" / "kg_browser_data.json"
    index_path = root / "site" / "kg_browser_index.json"
    edge_path = root / "site" / "kg_browser_edges.json"
    manifest_path = root / "evidence" / "public_artifact_manifest.json"
    assert kg_path.exists()
    assert index_path.exists()
    assert edge_path.exists()
    assert manifest_path.exists()
    kg = json.loads(kg_path.read_text(encoding="utf-8"))
    kg_index = json.loads(index_path.read_text(encoding="utf-8"))
    kg_edges = json.loads(edge_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(kg["nodes"]) == kg["summary"]["node_count"]
    assert len(kg["edges"]) == kg["summary"]["edge_count"]
    assert kg_index["schema"] == "regression_cp_evidence_graph_index_v1"
    assert kg_edges["schema"] == "regression_cp_evidence_graph_edges_v1"
    assert len(kg_index["nodes"]) == len(kg["nodes"])
    assert "edges" not in kg_index
    assert len(kg_edges["edges"]) == len(kg["edges"])
    assert kg_index["summary"]["loading_policy"] == "index_first_edges_on_demand"
    assert index_path.stat().st_size < kg_path.stat().st_size
    assert kg["summary"]["public_artifact_manifest"] == "evidence/public_artifact_manifest.json"
    assert manifest["strategy"] == "manifest_plus_summary_not_full_artifact_dump"
    assert manifest["summary"]["manifest_reference_resolution_rate"] == 1.0
    legacy_kg_summary_key = "edge_selector" + "_provenance_coverage"
    assert legacy_kg_summary_key not in kg["summary"]
    assert kg["summary"]["manifest_reference_resolution_rate"] == 1.0
    assert "public_status_counts" in manifest["summary"]
    assert all(row.get("public_status") for row in manifest["artifacts"])
    assert all("included" not in row for row in manifest["artifacts"])
    assert all("file_included" in row for row in manifest["artifacts"])
    assert all("represented_in_aggregate" in row for row in manifest["artifacts"])
    assert all("content_hash_verifiable" in row for row in manifest["artifacts"])
    assert all("public_content_sha256" in row for row in manifest["artifacts"])
    assert all("source_hash" not in row for row in manifest["artifacts"])
    manifest_text = json.dumps(manifest)
    forbidden_private_builders = [
        "build_private_sterile_publication_package",
        "build_public_release_authorization",
    ]
    assert all(name not in manifest_text for name in forbidden_private_builders)
    assert all(
        "build_public_release_scope" in row.get("rebuild_command", "")
        and "build_public_research_atlas" in row.get("rebuild_command", "")
        and "build_research_atlas_package" in row.get("rebuild_command", "")
        for row in manifest["artifacts"]
    )
    kg_text = kg_path.read_text(encoding="utf-8")
    index_text = index_path.read_text(encoding="utf-8")
    edge_text = edge_path.read_text(encoding="utf-8")
    artifact_manifest_text = manifest_path.read_text(encoding="utf-8")
    legacy_source_key = "source_key" + "_hash"
    assert legacy_source_key not in kg_text
    assert "source_key_fingerprint" in kg_text
    raw_public_graph_text = "\n".join(
        [kg_text, index_text, edge_text, artifact_manifest_text]
    ).lower()
    assert '"source_hash"' not in raw_public_graph_text
    assert "public_content_sha256" in raw_public_graph_text
    for legacy in ("frontier", "near_nominal", "near nominal", "near-nominal"):
        assert legacy not in raw_public_graph_text
    node_ids = {str(node["id"]) for node in kg["nodes"]}
    assert {str(node["id"]) for node in kg_index["nodes"]} == node_ids
    assert {
        str(edge["source"]) for edge in kg_edges["edges"]
    } <= node_ids
    assert {
        str(edge["target"]) for edge in kg_edges["edges"]
    } <= node_ids
    visible_values = []
    for node in kg["nodes"]:
        visible_values.extend(
            str(node.get(key) or "")
            for key in ("label", "summary", "display_id")
        )
    for edge in kg["edges"]:
        visible_values.extend(
            str(edge.get(key) or "")
            for key in ("label", "summary", "evidence")
        )
    for route in kg.get("research_map", []):
        visible_values.extend(
            str(route.get(key) or "")
            for key in ("title", "summary", "description")
        )
    visible_text = "\n".join(visible_values).lower()
    def phrase(*parts: str) -> str:
        return " ".join(parts)

    for legacy in (
        "frontier",
        "near_nominal",
        "near nominal",
        "near-nominal",
        phrase("document", "status:"),
        phrase("release", "render"),
        "release" + "_" + "boundary",
        phrase("not", "a", "method", "recommendation"),
        phrase("method", "recommendation"),
        phrase("part", "of", "the", "public", "Research", "Atlas"),
        phrase("release", "boundary", "ledger"),
        phrase("positive", "claim"),
        "positive" + "-claim",
        phrase("claim", "promotion"),
        "claim" + "-promotion",
        "claim-prom",
        phrase("positive", "claims", "remain", "beyond", "this", "study"),
        phrase("positive", "claims", "remain", "gated"),
    ):
        assert legacy not in visible_text


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
        assert (root / row["public_card_html_path"]).exists()
    dataset_index = (root / "atlas/datasets/index.html").read_text(encoding="utf-8")
    assert "cards/fairlearn_acs_income_wy.html" in dataset_index

    result_methods = set()
    with (root / "atlas/results/result_cube_public.csv").open(encoding="utf-8", newline="") as handle:
        import csv

        for row in csv.DictReader(handle):
            result_methods.add(row["method_label"])
    ontology_methods = {row["method_label"] for row in method_ontology["methods"]}
    assert result_methods <= ontology_methods
    for row in method_ontology["methods"]:
        assert (root / row["public_card_html_path"]).exists()
    method_index = (root / "atlas/methods/index.html").read_text(encoding="utf-8")
    assert "cards/cqr.html" in method_index
    assert "cards/cqr_model_matched.html" in method_index
    assert all(row.get("evidence_gate") for row in claim_registry["claims"])
    assert {route["route_id"] for route in kg["research_map"]} >= {
        "experiment_scope",
        "method_universe",
        "cqr_cvplus_signal",
        "venn_abers_bridge",
        "closed_gates",
    }
    browser = (root / "site/kg_browser.html").read_text(encoding="utf-8")
    assert 'role="list" aria-label="Guided research routes"' in browser
    assert '<button type="button" class="route"' in browser
    assert '<button type="button" class="result' in browser
    assert 'aria-current="' in browser
    assert 'aria-pressed="true"' in browser
    assert 'id="resultCount" role="status" aria-live="polite"' in browser
    assert 'id="graphNotice" class="graph-notice" role="status" aria-live="polite"' in browser
    assert "if(!r.ok) throw new Error" in browser
    assert ".catch(error=>" in browser
    assert "Node not found:" in browser
    assert "Route not found:" in browser
    assert "data-node=" in browser
    assert "data-route-action=" in browser
    assert "activateRouteButtons" in browser
    assert "Open evidence route" in browser
    assert ".table-action:hover" in browser
    assert "map-legend" in browser
    assert 'id="mapCanvas" tabindex="0" role="img"' in browser
    assert 'aria-describedby="canvasHelp"' in browser
    assert "Canvas focus" in browser
    assert "canvas.onkeydown" in browser
    assert "fetchJson('kg_browser_index.json')" in browser
    assert "Compact graph index unavailable" in browser
    assert "loading full graph data" in browser
    assert "kg_browser_edges.json" in browser
    assert "function ensureEdges(force=false)" in browser
    assert "Loading edge provenance on demand" in browser
    assert 'id="edgeRetry"' in browser
    assert "Retry edge bundle" in browser
    assert "ensureEdges(true)" in browser
    assert "Edge bundle unavailable; overview remains usable." in browser
    assert "Guided route anchor nodes" in browser
    assert 'scope="col">Anchor' in browser
    assert "Guided evidence routes" in browser
    assert "Selected node neighborhood" in browser
    assert "hidden matches" in browser
    assert "incident edges" in browser
    assert "loaded neighborhood nodes" in browser
    assert '<details class="edge">' in browser
    assert "expand provenance receipt" in browser
    assert "<strong>Evidence path:</strong>" in browser
    assert "<strong>Manifest:</strong>" in browser
    assert "<strong>Hash verifiable:</strong>" in browser
    assert "<strong>represented in aggregate:</strong>" in browser
    assert "Open public artifact" in browser
    assert "fetch('kg_browser_data.json').then" not in browser


def test_public_dataset_source_metadata_matrix_is_published_and_scoped() -> None:
    root = repo_root()
    base = root / "atlas/datasets/source_metadata_matrix"
    for suffix in (".csv", ".json", ".md"):
        assert base.with_suffix(suffix).exists()

    matrix = json.loads(base.with_suffix(".json").read_text(encoding="utf-8"))
    catalog = json.loads((root / "atlas/datasets/dataset_catalog.json").read_text(encoding="utf-8"))
    artifact_index = json.loads(
        (root / "atlas/artifacts/public_artifact_index.json").read_text(encoding="utf-8")
    )
    markdown = base.with_suffix(".md").read_text(encoding="utf-8")
    with base.with_suffix(".csv").open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))

    assert matrix["schema"] == "regression_cp_dataset_source_metadata_matrix_v1"
    assert matrix["summary"]["dataset_count"] == len(catalog["datasets"])
    assert matrix["summary"]["profile_metadata_available_count"] > 0
    assert matrix["summary"]["benchmark_v2_candidate_dataset_count"] > 0
    assert len(matrix["rows"]) == len(catalog["datasets"]) == len(csv_rows)
    assert "# Dataset Source Metadata Matrix" in markdown

    required = {
        "dataset_id",
        "source_dataset_id",
        "dataset_family",
        "version",
        "license_or_terms",
        "retrieval_command_or_url",
        "content_hash_scope",
        "raw_content_hash_status",
        "metadata_status",
    }
    for row in matrix["rows"]:
        assert required <= set(row)
        assert row["dataset_id"]
        assert row["dataset_family"]
        assert row["metadata_status"] in {
            "profile_metadata_available",
            "profile_missing_public_aggregate_only",
        }
        assert row["content_hash_scope"] in {
            "profile_metadata_not_raw_dataset",
            "no_public_profile_metadata",
        }
        assert row["raw_content_hash_status"] == (
            "raw_data_not_redistributed_or_not_publicly_hashed"
        )
    assert any(row["source_profile_sha256"] for row in matrix["rows"])
    assert not any(
        row["content_hash_scope"] == "raw_dataset_content_hash"
        for row in matrix["rows"]
    )

    indexed_paths = {row["artifact_path"] for row in artifact_index["artifacts"]}
    assert "atlas/datasets/source_metadata_matrix.csv" in indexed_paths
    assert "atlas/datasets/source_metadata_matrix.json" in indexed_paths
    assert "atlas/datasets/source_metadata_matrix.md" in indexed_paths
    dataset_index = (root / "atlas/datasets/index.html").read_text(encoding="utf-8")
    assert "source_metadata_matrix.md" in dataset_index


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


def test_public_root_command_default_config_resolves() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root() / "reproducibility")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "experiments.regression.scripts.run_regression_pilot",
            "--max-runs",
            "0",
        ],
        cwd=repo_root(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_public_environment_lock_documents_install_surface() -> None:
    root = repo_root()
    lock_path = root / "reproducibility/environment/public_environment_lock.json"
    md_path = root / "reproducibility/environment/public_environment_lock.md"
    req_path = root / "reproducibility/environment/requirements-public-lock.txt"
    assert lock_path.exists()
    assert md_path.exists()
    assert req_path.exists()

    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock["schema"] == "regression_cp_public_environment_lock_v1"
    assert lock["python_requires"] == ">=3.10"
    assert lock["recommended_python"] == "3.11"
    assert lock["platform"]["gpu_required"] is False
    assert "python -m pip install -e \".[test]\"" in lock["install_commands"]
    assert "python -m pytest -m \"unit or artifact_public or smoke\" -q" in lock["install_commands"]

    locked = lock["locked_dependencies"]
    for name in [
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "PyYAML",
        "matplotlib",
        "loguru",
        "pytest",
    ]:
        assert name in locked
        assert locked[name]
    assert lock["optional_model_dependencies"]["xgboost"] == ">=2.0"

    req_text = req_path.read_text(encoding="utf-8")
    assert "numpy==2.3.5" in req_text
    assert "scikit-learn==1.9.0" in req_text
    assert "pytest==8.4.2" in req_text
    assert "pyyaml==6.0.3" in req_text

    md_text = md_path.read_text(encoding="utf-8")
    assert "# Public Environment Lock" in md_text
    assert "Locked Public Smoke Dependencies" in md_text
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "reproducibility/environment/public_environment_lock.md" in readme
    assert "reproducibility/environment/requirements-public-lock.txt" in readme


def test_public_repository_maintenance_files_are_present() -> None:
    root = repo_root()
    contributing = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    security = (root / "SECURITY.md").read_text(encoding="utf-8")
    codeowners = (root / "CODEOWNERS").read_text(encoding="utf-8")
    github_codeowners = (root / ".github/CODEOWNERS").read_text(encoding="utf-8")
    data_licenses = (root / "DATA_LICENSES.md").read_text(encoding="utf-8")
    editorconfig = (root / ".editorconfig").read_text(encoding="utf-8")
    checksums = (root / "CHECKSUMS.sha256").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/public-ci.yml").read_text(encoding="utf-8")
    artifact_index = json.loads(
        (root / "atlas/artifacts/public_artifact_index.json").read_text(
            encoding="utf-8"
        )
    )
    indexed_paths = {row["artifact_path"] for row in artifact_index["artifacts"]}

    assert 'python -m pip install -e ".[test]"' in contributing
    assert 'python -m pytest -m "unit or artifact_public or smoke"' in contributing
    assert "sha256sum -c CHECKSUMS.sha256" in contributing
    assert "detasar@gmail.com" in security
    assert "restricted ledgers" in security
    assert "nonredistributable datasets" in security
    assert "@detasar" in codeowners
    assert github_codeowners == codeowners
    assert "Data Licenses And Redistribution Scope" in data_licenses
    assert "atlas/datasets/source_metadata_matrix.md" in data_licenses
    assert "Raw external datasets" in data_licenses
    assert "Restricted ledgers, caches, and prediction bundles" in data_licenses
    assert "root = true" in editorconfig
    assert "indent_size = 4" in editorconfig
    assert "permissions:" in workflow
    assert workflow.count("contents: read") >= 2
    assert "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0" in workflow
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in workflow
    assert "actions/checkout@v7" not in workflow
    assert "actions/setup-python@v6" not in workflow
    assert "actions/checkout@v4" not in workflow
    assert "actions/setup-python@v5" not in workflow
    assert "sha256sum -c CHECKSUMS.sha256" in workflow
    for expected_path in [
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODEOWNERS",
        ".github/CODEOWNERS",
        "DATA_LICENSES.md",
        ".editorconfig",
        "CHECKSUMS.sha256",
        "site/index.html",
        "atlas/provenance/index.html",
        "paper/article.pdf",
        "reproducibility/tests/test_public_research_atlas_smoke.py",
    ]:
        assert expected_path in indexed_paths or expected_path in checksums


def test_public_benchmark_v2_protocol_is_frozen_and_linked() -> None:
    root = repo_root()
    protocol_path = root / "atlas/scope/benchmark_v2_protocol.json"
    markdown_path = root / "atlas/scope/benchmark_v2_protocol.md"
    execution_path = root / "atlas/scope/benchmark_v2_execution_manifest.json"
    execution_markdown_path = root / "atlas/scope/benchmark_v2_execution_manifest.md"
    evidence_path = root / "atlas/scope/benchmark_v2_public_evidence_contract.json"
    evidence_markdown_path = root / "atlas/scope/benchmark_v2_public_evidence_contract.md"
    artifact_index_path = root / "atlas/artifacts/public_artifact_index.json"
    assert protocol_path.exists()
    assert markdown_path.exists()
    assert execution_path.exists()
    assert execution_markdown_path.exists()
    assert evidence_path.exists()
    assert evidence_markdown_path.exists()

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert protocol["schema"] == "regression_cp_benchmark_v2_protocol_v1"
    assert protocol["status"] == "protocol_defined_not_executed"
    assert execution["schema"] == "regression_cp_benchmark_v2_execution_manifest_v1"
    assert execution["status"] == "execution_contract_defined_not_executed"
    assert evidence["schema"] == "regression_cp_benchmark_v2_public_evidence_contract_v1"
    assert evidence["status"] == "contract_defined_not_populated"
    assert (
        protocol["primary_estimand"]["primary_comparison_unit"]
        == "source_dataset_task_alpha_learner_config_split_hash"
    )
    assert execution["run_grid"]["alpha_grid"] == [0.01, 0.05, 0.1, 0.15, 0.2]
    assert len(execution["run_grid"]["random_seeds"]) == 10
    assert "cqr_model_matched" in execution["run_grid"]["conformal_methods"]
    assert "venn_abers_quantile_bridge" in execution["run_grid"]["diagnostic_methods_excluded_from_primary_ranking"]
    assert "source_dataset_id" in execution["paired_cell_key"]
    assert "split_hash" in execution["paired_cell_key"]
    assert any("fold" in step for step in execution["preprocessing_contract"]["fold_local_steps"])
    required_artifacts = {row["artifact_id"] for row in evidence["required_public_artifacts"]}
    assert {
        "source_dataset_registry",
        "run_grid_manifest",
        "run_status_ledger",
        "aggregate_result_cube",
        "environment_lock",
    } <= required_artifacts
    requirements = "\n".join(protocol["design_requirements"]).lower()
    assert "exact learner/config/split cells" in requirements
    assert "inside each cv+/jackknife fold" in requirements
    assert "planned, attempted, completed, failed, skipped" in requirements

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Benchmark v2 Protocol" in markdown
    assert "Status: protocol defined, not executed." in markdown
    assert "retrospective cleanup" in markdown

    artifact_index = json.loads(artifact_index_path.read_text(encoding="utf-8"))
    indexed_paths = {row["artifact_path"] for row in artifact_index["artifacts"]}
    assert "atlas/scope/benchmark_v2_protocol.json" in indexed_paths
    assert "atlas/scope/benchmark_v2_protocol.md" in indexed_paths
    assert "atlas/scope/benchmark_v2_execution_manifest.json" in indexed_paths
    assert "atlas/scope/benchmark_v2_execution_manifest.md" in indexed_paths
    assert "atlas/scope/benchmark_v2_public_evidence_contract.json" in indexed_paths
    assert "atlas/scope/benchmark_v2_public_evidence_contract.md" in indexed_paths
    assert "atlas/benchmark_v2/preflight/README.md" in indexed_paths
    assert "atlas/benchmark_v2/preflight/run_grid_cardinality.json" in indexed_paths
    assert "atlas/benchmark_v2/preflight/preflight_readiness_checklist.json" in indexed_paths
    assert "atlas/benchmark_v2/candidates/source_dataset_registry_candidate.csv" in indexed_paths
    assert "atlas/benchmark_v2/candidates/task_variant_registry_candidate.csv" in indexed_paths
    assert "atlas/benchmark_v2/candidates/candidate_selection_rationale.json" in indexed_paths


def test_public_benchmark_v2_preflight_templates_are_published() -> None:
    root = repo_root()
    preflight = root / "atlas/benchmark_v2/preflight"
    cardinality_path = preflight / "run_grid_cardinality.json"
    checklist_path = preflight / "preflight_readiness_checklist.json"
    run_grid_path = preflight / "run_grid_manifest_preview.csv"
    candidate_run_grid_path = preflight / "run_grid_manifest_candidate.csv.gz"
    source_template_path = preflight / "source_dataset_registry_template.csv"
    task_template_path = preflight / "task_variant_registry_template.csv"
    status_template_path = preflight / "run_status_ledger_template.csv"
    for path in [
        preflight / "README.md",
        cardinality_path,
        checklist_path,
        preflight / "preflight_readiness_checklist.md",
        run_grid_path,
        candidate_run_grid_path,
        source_template_path,
        task_template_path,
        status_template_path,
    ]:
        assert path.exists()

    cardinality = json.loads(cardinality_path.read_text(encoding="utf-8"))
    assert cardinality["schema"] == "regression_cp_benchmark_v2_run_grid_cardinality_v1"
    assert cardinality["status"] == "preflight_template_not_executed"
    assert cardinality["estimated_task_variant_count"] == 24
    assert cardinality["primary_rows_per_task_variant"] == 8750
    assert cardinality["diagnostic_rows_per_task_variant"] == 3500
    assert cardinality["estimated_primary_planned_rows"] == 210000
    assert cardinality["estimated_diagnostic_planned_rows"] == 84000
    assert cardinality["estimated_total_planned_rows"] == 294000
    assert cardinality["candidate_task_variant_count"] == 24
    assert cardinality["candidate_primary_planned_run_grid_row_count"] == 210000

    checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
    assert checklist["schema"] == "regression_cp_benchmark_v2_preflight_readiness_checklist_v1"
    assert checklist["overall_status"] == "preflight_templates_ready_execution_not_started"
    assert checklist["result_generation_status"] == "not_started"
    statuses = {row["gate_id"]: row["status"] for row in checklist["checklist"]}
    assert statuses["preflight_templates_published"] == "pass"
    assert statuses["candidate_run_grid_manifest_published"] == "pass"
    assert statuses["benchmark_v2_results_generated"] == "not_started"

    with run_grid_path.open(encoding="utf-8", newline="") as handle:
        preview_rows = list(csv.DictReader(handle))
    assert len(preview_rows) == cardinality["primary_rows_per_task_variant"]
    assert {"paired_cell_key", "split_hash", "conformal_method_config_id"} <= set(
        preview_rows[0]
    )
    assert {row["ranking_role"] for row in preview_rows} == {"primary"}
    assert all(row["planned_status"] == "template_pending_task_registry" for row in preview_rows)

    with gzip.open(candidate_run_grid_path, "rt", encoding="utf-8", newline="") as handle:
        candidate_rows = list(csv.DictReader(handle))
    assert len(candidate_rows) == cardinality["candidate_primary_planned_run_grid_row_count"]
    assert {"paired_cell_key", "source_dataset_id", "task_variant_id", "split_hash"} <= set(
        candidate_rows[0]
    )
    assert {row["ranking_role"] for row in candidate_rows} == {"primary"}
    assert {row["planned_status"] for row in candidate_rows} == {
        "candidate_task_registry_planned"
    }
    assert all("<pending" not in row["paired_cell_key"] for row in candidate_rows[:200])
    assert len({row["task_variant_id"] for row in candidate_rows}) == 24
    assert len({row["source_dataset_id"] for row in candidate_rows}) == 12

    with source_template_path.open(encoding="utf-8", newline="") as handle:
        source_fields = next(csv.reader(handle))
    assert {
        "source_dataset_id",
        "license",
        "retrieval_command_or_url",
        "content_hash_or_accession",
    } <= set(source_fields)
    with task_template_path.open(encoding="utf-8", newline="") as handle:
        task_fields = next(csv.reader(handle))
    assert {"task_variant_id", "source_dataset_id", "split_regime"} <= set(task_fields)
    with status_template_path.open(encoding="utf-8", newline="") as handle:
        status_fields = next(csv.reader(handle))
    assert {"paired_cell_key", "attempted", "completed", "failed", "skipped"} <= set(
        status_fields
    )


def test_public_benchmark_v2_candidate_registries_are_scoped_and_balanced() -> None:
    root = repo_root()
    candidate_root = root / "atlas/benchmark_v2/candidates"
    source_path = candidate_root / "source_dataset_registry_candidate.csv"
    task_path = candidate_root / "task_variant_registry_candidate.csv"
    rationale_path = candidate_root / "candidate_selection_rationale.json"
    rationale_md_path = candidate_root / "candidate_selection_rationale.md"
    assert source_path.exists()
    assert task_path.exists()
    assert rationale_path.exists()
    assert rationale_md_path.exists()

    with source_path.open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    with task_path.open(encoding="utf-8", newline="") as handle:
        task_rows = list(csv.DictReader(handle))
    rationale = json.loads(rationale_path.read_text(encoding="utf-8"))

    assert len(source_rows) == 12
    assert len(task_rows) == 24
    assert rationale["schema"] == "regression_cp_benchmark_v2_candidate_selection_rationale_v1"
    assert rationale["status"] == "candidate_registries_published_execution_not_started"
    assert rationale["source_candidate_count"] == 12
    assert rationale["task_variant_candidate_count"] == 24
    assert "do not contain completed Benchmark v2 result rows" in rationale_md_path.read_text(
        encoding="utf-8"
    )
    family_counts = Counter(row["source_family"] for row in source_rows)
    assert max(family_counts.values()) <= 2
    task_counts = Counter(row["source_dataset_id"] for row in task_rows)
    assert set(task_counts.values()) == {2}
    assert all(
        row["candidate_status"] == "candidate_pending_pre_execution_verification"
        for row in source_rows
    )
    assert all(
        row["candidate_status"] == "candidate_pending_pre_execution_verification"
        for row in task_rows
    )
    assert all(
        row["content_hash_scope"] == "profile_metadata_bundle_not_raw_dataset"
        for row in source_rows
    )
    assert {"iid", "grouped", "temporal", "covariate_shift"} <= {
        row["split_regime"] for row in task_rows
    }
    assert all(row["metadata_status"] for row in source_rows)
    assert any("pending_final_terms_review" in row["license"] for row in source_rows)
    assert all(row["fold_policy"] for row in task_rows)
    assert all(row["leakage_guard"] for row in task_rows)


def test_public_final_audit_response_matrix_tracks_remaining_work() -> None:
    root = repo_root()
    matrix_path = root / "atlas/scope/audit_response_matrix.json"
    markdown_path = root / "atlas/scope/audit_response_matrix.md"
    artifact_index_path = root / "atlas/artifacts/public_artifact_index.json"
    assert matrix_path.exists()
    assert markdown_path.exists()

    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    assert matrix["schema"] == "regression_cp_final_audit_response_matrix_v1"
    assert matrix["summary"]["p0_status"] == "completed"
    assert (
        matrix["summary"]["benchmark_v2_status"]
        == "candidate_registries_published_execution_not_started"
    )
    assert (
        matrix["summary"]["atlas_product_status"]
        == "completed_current_public_atlas_layer"
    )
    assert (
        matrix["summary"]["kg_product_status"]
        == "completed_current_public_kg_layer"
    )
    assert (
        matrix["summary"]["maintenance_status"]
        == "schema_migration_seeded_modularization_pending"
    )
    statuses = {(row["priority"], row["status"]) for row in matrix["rows"]}
    assert ("P0", "completed") in statuses
    assert ("P1", "candidate_registries_published_execution_not_started") in statuses
    assert ("P1", "completed_current_public_atlas_layer") in statuses
    assert ("P1", "completed_current_public_kg_layer") in statuses
    assert ("P2", "schema_migration_seeded_modularization_pending") in statuses
    assert any(
        "KG loading architecture" in row["item"]
        and row["status"] == "completed_current_public_kg_layer"
        for row in matrix["rows"]
    )
    assert any(
        "interactive result-atlas layer" in row["item"]
        and row["status"] == "completed_current_public_atlas_layer"
        and "atlas/results/cqr_backend_sensitivity.csv" in row["evidence_paths"]
        for row in matrix["rows"]
    )
    assert any(
        "separate source fingerprints and public content hashes" in row["item"]
        and row["status"] == "completed"
        and "site/kg_browser_index.json" in row["evidence_paths"]
        and "site/kg_browser_edges.json" in row["evidence_paths"]
        for row in matrix["rows"]
    )

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Final Audit Response Matrix" in markdown
    assert "P0 items are required public-readiness repairs" in markdown

    artifact_index = json.loads(artifact_index_path.read_text(encoding="utf-8"))
    indexed_paths = {row["artifact_path"] for row in artifact_index["artifacts"]}
    assert "atlas/scope/audit_response_matrix.json" in indexed_paths
    assert "atlas/scope/audit_response_matrix.md" in indexed_paths
    assert "atlas/maintenance/maintenance_gate_matrix.json" in indexed_paths
    assert "atlas/maintenance/maintenance_gate_matrix.md" in indexed_paths
    assert "atlas/maintenance/schema_registry.json" in indexed_paths
    assert "atlas/maintenance/schema_migration_fixtures.json" in indexed_paths


def test_public_maintenance_gate_matrix_tracks_ci_and_debt() -> None:
    root = repo_root()
    matrix_path = root / "atlas/maintenance/maintenance_gate_matrix.json"
    markdown_path = root / "atlas/maintenance/maintenance_gate_matrix.md"
    assert matrix_path.exists()
    assert markdown_path.exists()

    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    assert matrix["schema"] == "regression_cp_public_maintenance_gate_matrix_v1"
    assert (
        matrix["summary"]["overall_status"]
        == "schema_migration_seeded_modularization_pending"
    )
    gate_by_id = {row["gate_id"]: row for row in matrix["gates"]}
    assert gate_by_id["public_smoke_ci"]["ci_enforced"] is True
    assert gate_by_id["package_content"]["status"] == "implemented"
    assert gate_by_id["public_forbidden_language"]["status"] == "implemented"
    assert gate_by_id["environment_lock"]["status"] == "implemented"
    assert gate_by_id["accessibility_metadata"]["status"] == "partial"
    assert gate_by_id["builder_modularization"]["status"] == "planned"
    assert gate_by_id["schema_migration"]["status"] == "implemented"
    assert gate_by_id["schema_migration"]["ci_enforced"] is True
    assert gate_by_id["lint_type_security"]["ci_enforced"] is False
    assert matrix["summary"]["ci_enforced_gate_count"] >= 6

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Maintenance Gate Matrix" in markdown
    assert "Builder modularization gate" in markdown


def test_public_schema_registry_and_migration_fixtures_are_enforced() -> None:
    root = repo_root()
    registry_path = root / "atlas/maintenance/schema_registry.json"
    fixtures_path = root / "atlas/maintenance/schema_migration_fixtures.json"
    registry_md = root / "atlas/maintenance/schema_registry.md"
    fixtures_md = root / "atlas/maintenance/schema_migration_fixtures.md"
    artifact_index_path = root / "atlas/artifacts/public_artifact_index.json"
    assert registry_path.exists()
    assert fixtures_path.exists()
    assert registry_md.exists()
    assert fixtures_md.exists()

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
    fixtures_text = fixtures_path.read_text(encoding="utf-8").lower()
    fixtures_md_text = fixtures_md.read_text(encoding="utf-8").lower()
    for legacy in (
        "front" + "ier",
        "near" + "_nominal",
        "near " + "nominal",
        "near" + "-nominal",
        "source_key" + "_hash",
        "edge_selector" + "_provenance_coverage",
    ):
        assert legacy not in fixtures_text
        assert legacy not in fixtures_md_text
    assert registry["schema"] == "regression_cp_public_schema_registry_v1"
    assert registry["status"] == "schema_registry_seeded"
    assert fixtures["schema"] == "regression_cp_public_schema_migration_fixtures_v1"
    assert fixtures["status"] == "schema_migration_fixtures_seeded"

    fixture_by_id = {row["fixture_id"]: row for row in fixtures["fixtures"]}
    schema_by_path = {row["artifact_path"]: row for row in registry["schemas"]}
    assert {
        "site/kg_browser_data.json",
        "site/kg_browser_index.json",
        "site/kg_browser_edges.json",
        "evidence/public_artifact_manifest.json",
        "atlas/results/result_cube_public.csv",
        "atlas/artifacts/public_artifact_index.json",
        "atlas/maintenance/maintenance_gate_matrix.json",
    } <= set(schema_by_path)
    assert {
        row["migration_fixture_id"] for row in registry["schemas"]
    } <= set(fixture_by_id)
    assert (
        schema_by_path["atlas/results/result_cube_public.csv"]["schema"]
        == "regression_cp_result_cube_public_v1"
    )
    assert {
        "coverage_lower_bound_pass",
        "selected_under_coverage_gate",
        "numerical_pathology_flag",
    } <= set(schema_by_path["atlas/results/result_cube_public.csv"]["required_fields"])

    result_fixture = fixture_by_id["result_cube_selection_labels_v0_to_v1"]
    assert result_fixture["field_role_migrations"] == {
        "legacy_coverage_gate_label": "coverage_lower_bound_pass",
        "legacy_selection_label": "selected_under_coverage_gate",
    }
    result_fixture_text = json.dumps(result_fixture)
    assert "near" + "_nominal" not in result_fixture_text
    assert "front" + "ier" not in result_fixture_text
    assert "coverage_lower_bound_pass" in result_fixture["expected_output_example"]
    assert "selected_under_coverage_gate" in result_fixture["expected_output_example"]
    kg_fixture = fixture_by_id["kg_provenance_label_v0_to_v1"]
    assert kg_fixture["field_role_migrations"]["source_fingerprint"] == "source_key_fingerprint"
    assert (
        kg_fixture["field_role_migrations"]["selector_reference_resolution_rate"]
        == "manifest_reference_resolution_rate"
    )
    manifest_fixture = fixture_by_id["public_manifest_included_to_file_included_v1"]
    assert (
        manifest_fixture["field_role_migrations"]["legacy_file_presence"]
        == "file_included"
    )
    assert "included" not in manifest_fixture["expected_output_example"]["artifacts"][0]
    assert "file_included" in manifest_fixture["expected_output_example"]["artifacts"][0]

    artifact_index = json.loads(artifact_index_path.read_text(encoding="utf-8"))
    indexed_paths = {row["artifact_path"] for row in artifact_index["artifacts"]}
    assert "atlas/maintenance/schema_registry.json" in indexed_paths
    assert "atlas/maintenance/schema_registry.md" in indexed_paths
    assert "atlas/maintenance/schema_migration_fixtures.json" in indexed_paths
    assert "atlas/maintenance/schema_migration_fixtures.md" in indexed_paths


def test_public_rebuild_commands_run(tmp_path: Path) -> None:
    scratch = tmp_path / "atlas_package"
    shutil.copytree(
        repo_root(),
        scratch,
        ignore=shutil.ignore_patterns(
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            "__pycache__",
            "build",
            "dist",
            "*.egg-info",
        ),
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(scratch / "reproducibility")
    modules = [
        "experiments.regression.scripts.build_public_release_scope",
        "experiments.regression.scripts.build_public_research_atlas",
        "experiments.regression.scripts.build_research_atlas_package",
    ]
    for module in modules:
        result = subprocess.run(
            [sys.executable, "-m", module, "--package-root", str(scratch)],
            cwd=scratch,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "\"status\": \"pass\"" in result.stdout
    rebuild_manifest = json.loads(
        (scratch / "atlas/provenance/public_rebuild_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    package_data = rebuild_manifest["package_data"]
    assert package_data["experiment_config_count"] == 184
    assert package_data["expected_experiment_config_count"] == 184
    assert package_data["pilot_config_exists"] is True
    assert package_data["runner_script_exists"] is True
    assert package_data["default_config_resolution"] == "packaged_layout"
    assert (
        package_data["default_config_path"]
        == "reproducibility/experiments/regression/configs/pilot.yaml"
    )
    assert package_data["config_failures"] == []


def test_public_result_cube_schema_preserves_scientific_labels() -> None:
    root = repo_root()
    with (root / "atlas/results/result_cube_public.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = set(reader.fieldnames or [])
    assert rows
    assert {
        "coverage_lower_bound_pass",
        "selected_under_coverage_gate",
        "numerical_pathology_flag",
        "numerical_pathology_reason",
        "display_interval_policy",
    } <= fieldnames
    legacy_coverage_status = "near" + "_nominal"
    legacy_selection_flag = "frontier" + "_flag"
    assert legacy_coverage_status not in fieldnames
    assert legacy_selection_flag not in fieldnames
    assert any(row["numerical_pathology_flag"] == "true" for row in rows)
    assert any(
        row["numerical_pathology_reason"] and row["display_interval_policy"]
        for row in rows
        if row["numerical_pathology_flag"] == "true"
    )
    heatmap = json.loads(
        (root / "atlas/ui_data/dataset_method_heatmap.json").read_text(
            encoding="utf-8"
        )
    )
    heatmap_rows = heatmap["rows"]
    assert {
        "numerical_pathology_flag",
        "numerical_pathology_reason",
        "display_interval_policy",
    } <= set(heatmap_rows[0])
    assert any(row["numerical_pathology_flag"] is True for row in heatmap_rows)
    assert any(
        row["numerical_pathology_reason"] and row["display_interval_policy"]
        for row in heatmap_rows
        if row["numerical_pathology_flag"] is True
    )
    selected_path = root / "atlas/results/selected_under_coverage_gate_cells.csv"
    selected_text = selected_path.read_text(encoding="utf-8")
    assert legacy_coverage_status not in selected_text
    with selected_path.open(encoding="utf-8", newline="") as handle:
        selected_rows = list(csv.DictReader(handle))
    assert selected_rows
    statuses = {row["candidate_status"] for row in selected_rows}
    assert "coverage_lower_bound_pass_mean" in statuses
    assert "coverage_lower_bound_fail" in statuses


def test_public_results_page_exposes_interactive_atlas_layers() -> None:
    root = repo_root()
    results = (root / "atlas/results/index.html").read_text(encoding="utf-8")
    for fragment in [
        "Result Explorer",
        "Experiment Accounting Funnel",
        "Venn-Abers Bridge Diagnostic",
        "Method-Family Selection Density",
        "Coverage-Width Map",
        "Coverage Deviation",
        "Relative Interval-Score Efficiency",
        "Coverage-Width Pareto Summary",
        "CQR Backend Sensitivity Map",
        "Copy Current View",
        "Share filtered result view",
        "Numerical pathology",
        "numerical_pathology_reason",
        "display_interval_policy",
        "planned_attempted_completed_matrix.json",
        "not_atomically_reconstructable_from_public_package",
        'id="accounting-funnel"',
        'id="venn-bridge-diagnostic"',
        'id="explorer-summary"',
        'id="copy-result-view"',
        'id="result-view-link"',
        'id="copy-result-status"',
        'id="coverage-width-map"',
        'id="coverage-deviation-bars"',
        'id="efficiency-bars"',
        'id="pareto-summary"',
        'id="cqr-delta-wrap"',
        "renderCoverageDeviation",
        "renderEfficiency",
        "renderParetoSummary",
        "currentExplorerUrl",
        "navigator.clipboard",
        "fallbackCopy",
        "datasetCardHref",
        "methodCardHref",
        "detailLink",
        "Open dataset detail for",
        "Open method detail for",
        "../datasets/cards/",
        "../methods/cards/",
        "Current view link copied.",
        "Copy unavailable; link is shown.",
        "window.history.replaceState",
        "new URLSearchParams",
        "nondominatedKeys",
        "const cqrRows = [",
        "coverage-width nondominated",
    ]:
        assert fragment in results
    assert "__RESULT_ROWS__" not in results
    assert "__CQR_ROWS__" not in results
    assert "{{row.dataset_id}}" not in results


def test_public_provenance_page_exposes_receipt_explorer() -> None:
    root = repo_root()
    provenance = (root / "atlas/provenance/index.html").read_text(encoding="utf-8")
    hash_receipts = json.loads((root / "atlas/provenance/hash_receipts.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((root / "atlas/provenance/artifact_manifest.json").read_text(encoding="utf-8"))
    kg_manifest = json.loads((root / "evidence/public_artifact_manifest.json").read_text(encoding="utf-8"))
    for fragment in [
        "Provenance Receipt Explorer",
        'id="provenance-explorer"',
        'id="provenance-summary"',
        'id="source-receipt-table"',
        'id="hash-receipt-table"',
        'id="provenance-status"',
        'id="receipt-search"',
        "Filtered public source-manifest rows",
        "Generated public file hash receipts",
        "hash_receipts.json",
        "artifact_manifest.json",
        "public_rebuild_manifest.json",
        "public_release_scope.json",
        "ro-crate-metadata.json",
        "../../evidence/public_artifact_manifest.json",
        "fetch('hash_receipts.json')",
        "window.history.replaceState",
        "source_reference_fingerprint",
        "content_hash_verifiable",
    ]:
        assert fragment in provenance
    assert len(hash_receipts["files"]) >= 200
    assert source_manifest["summary"]["source_artifact_count"] == len(source_manifest["artifacts"])
    assert source_manifest["summary"]["source_artifact_count"] >= 8
    assert kg_manifest["summary"]["manifest_reference_resolution_rate"] == 1.0


def test_public_accounting_matrix_artifacts_are_present() -> None:
    root = repo_root()
    base = root / "atlas/scope/planned_attempted_completed_matrix"
    for suffix in (".json", ".md", ".csv"):
        assert base.with_suffix(suffix).exists()

    payload = json.loads(base.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["schema"] == "regression_cp_public_accounting_matrix_v1"
    rows = payload["rows"]
    phases = {row["phase"] for row in rows}
    assert {"attempted_rows", "failed_rows", "skipped_rows"} <= phases
    unavailable = [
        row
        for row in rows
        if row["phase"] in {"attempted_rows", "failed_rows", "skipped_rows"}
    ]
    assert unavailable
    assert all(
        row["public_status"] == "not_atomically_reconstructable_from_public_package"
        for row in unavailable
    )


def test_public_reader_surfaces_avoid_machine_gate_language() -> None:
    root = repo_root()
    def phrase(*parts: str) -> str:
        return " ".join(parts)

    paths = [
        root / "README.md",
        root / "EVIDENCE_SCOPE.md",
        root / "site/index.html",
        root / "site/kg_browser.html",
        root / "site/kg_browser_index.json",
        root / "site/kg_browser_data.json",
        root / "paper/research_document.md",
        root / "paper/research_document.html",
        root / "paper/individual_experiment_report.md",
        root / "paper/article.html",
        root / "paper/article.tex",
        root / "paper/supplement.html",
        root / "paper/supplement.tex",
        root / "atlas/index.html",
        root / "atlas/results/index.html",
        root / "evidence/claim_evidence_matrix.md",
    ]
    forbidden = [
        phrase("Document", "status:"),
        phrase("Research", "Document", "release", "render"),
        phrase("release", "render"),
        "release" + "_" + "boundary",
        phrase("not", "a", "method", "recommendation"),
        phrase("not", "an", "independent", "scientific", "claim"),
        phrase("private", "final-prose"),
        phrase("do", "not", "cite"),
        phrase("not", "yet"),
        phrase("public", "citation", "waits"),
        phrase("public", "citable", "component"),
        phrase("citable", "component"),
        phrase("citation", "target"),
        phrase("final", "citable", "public", "artifact"),
        phrase("release", "state"),
        "not-" + "authoriz",
        "not_" + "authoriz",
        phrase("without", "authorizing"),
        phrase("authorizing", "Research", "Atlas"),
        phrase("method", "claims"),
        phrase("citable", "status"),
        phrase("final", "report", "text", "remains", "beyond", "this", "study"),
        phrase("public", "release", "remains", "closed"),
        phrase("GitHub", "Pages", "remain", "closed"),
        phrase("Release", "Boundary", "Ledger"),
        phrase("positive", "claim"),
        "positive" + "-claim",
        phrase("claim", "promotion"),
        "claim" + "-promotion",
        phrase("Main-claim", "promotion"),
        phrase("promotion", "beyond", "this", "study"),
        phrase("positive", "claims", "remain", "beyond", "this", "study"),
        phrase("positive", "claims", "remain", "gated"),
        phrase("working", "final-prose"),
        phrase("not", "final", "Research", "Document", "prose"),
        phrase("not", "final", "manuscript"),
        phrase("private", "review", "draft"),
        phrase("private", "review"),
        phrase("private", "site"),
        phrase("private", "package"),
        phrase("can", "be", "reviewed", "privately"),
        phrase("separate", "publication", "decision"),
        phrase("citation", "metadata", "require", "separate", "validation"),
        phrase("Research", "Atlas", "review", "and", "Research", "Atlas", "publication"),
        phrase("when", "its", "quality", "and", "provenance", "checks", "pass"),
        phrase("No", "public", "KG", "citation"),
        phrase("reviewable", "publication", "surfaces"),
        phrase("not", "a", "deployment", "recommendation"),
        "reader" + "-facingty",
        "reader" + "-safety",
        phrase("not", "a", "Research", "Atlas"),
        phrase("not", "a", "deployment", "guidance"),
        phrase("public", "research", "report"),
    ]
    violations = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in forbidden:
            if phrase.lower() in text:
                violations.append((path.relative_to(root).as_posix(), phrase))
    assert violations == []


def test_public_html_links_and_artifact_index_are_complete() -> None:
    root = repo_root()
    html_paths = [path for path in root.rglob("*.html") if ".git" not in path.parts]
    linked: set[str] = set()
    missing: list[tuple[str, str, str]] = []
    for path in html_paths:
        parser = _LinkParser()
        parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
        for raw_link in parser.links:
            href = urldefrag(raw_link)[0]
            parsed = urlparse(href)
            if (
                not href
                or parsed.scheme
                or href.startswith("#")
                or href.startswith("mailto:")
            ):
                continue
            target = (path.parent / href).resolve()
            try:
                relative = target.relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
            linked.add(relative)
            if not target.exists():
                missing.append((path.relative_to(root).as_posix(), raw_link, relative))
    assert not missing

    artifact_index = json.loads(
        (root / "atlas/artifacts/public_artifact_index.json").read_text(encoding="utf-8")
    )
    indexed = {
        row["artifact_path"]
        for row in artifact_index["artifacts"]
    }
    artifact_page = (root / "atlas/artifacts/index.html").read_text(encoding="utf-8")
    substantive_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and path.relative_to(root).as_posix().startswith(
            ("atlas/", "paper/", "site/", "evidence/", "reproducibility/environment/")
        )
    }
    assert substantive_files <= indexed
    for artifact_path in substantive_files:
        assert artifact_path in linked or artifact_path.endswith(".html")
        assert artifact_path in artifact_page


def test_public_html_metadata_and_accessibility_basics() -> None:
    root = repo_root()
    pages = [
        root / "site/index.html",
        root / "paper/research_document.html",
        root / "paper/article.html",
        root / "paper/supplement.html",
        root / "atlas/index.html",
        root / "atlas/results/index.html",
        root / "atlas/provenance/index.html",
        root / "site/kg_browser.html",
    ]
    for page in pages:
        text = page.read_text(encoding="utf-8")
        assert '<meta name="description"' in text
        assert '<link rel="canonical"' in text
        assert 'type="application/ld+json"' in text
        assert "skip-link" in text
        assert ":focus-visible" in text
        assert 'rel="icon"' in text
        table_parser = _TableAccessibilityParser()
        table_parser.feed(text)
        assert table_parser.captions == table_parser.tables
        assert table_parser.scoped_header_cells == table_parser.header_cells
    kg_text = (root / "site/kg_browser.html").read_text(encoding="utf-8")
    assert "aria-live" in kg_text
    assert "fallback" in kg_text.lower()
    assert "Guided route anchor nodes" in kg_text
    assert 'scope="col">Anchor' in kg_text
    assert "Guided evidence routes" in kg_text
    assert "Selected node neighborhood" in kg_text


def test_public_seo_and_citation_discovery_files() -> None:
    root = repo_root()
    robots = (root / "robots.txt").read_text(encoding="utf-8")
    sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
    seo_manifest = json.loads(
        (root / "atlas/provenance/public_seo_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    favicon = (root / "favicon.svg").read_text(encoding="utf-8")
    citation_cff = (root / "CITATION.cff").read_text(encoding="utf-8")
    citation_bib = (root / "paper/citation.bib").read_text(encoding="utf-8")
    citation_ris = (root / "paper/citation.ris").read_text(encoding="utf-8")
    assert "Sitemap: https://detasar.github.io/regression-conformal-prediction-research-atlas/sitemap.xml" in robots
    assert seo_manifest["schema"] == "regression_cp_public_seo_manifest_v1"
    assert seo_manifest["canonical_base_url"] == "https://detasar.github.io/regression-conformal-prediction-research-atlas/"
    assert seo_manifest["summary"]["html_page_count"] == seo_manifest["summary"]["sitemap_url_count"]
    assert seo_manifest["summary"]["html_page_count"] >= 100
    assert seo_manifest["summary"]["dataset_card_page_count"] >= 60
    assert seo_manifest["summary"]["method_card_page_count"] >= 25
    sitemap_url_count = sitemap.count("<url>")
    assert sitemap_url_count == seo_manifest["summary"]["sitemap_url_count"]
    for page in seo_manifest["pages"]:
        assert f"<loc>{page['url']}</loc>" in sitemap
    for url in [
        "https://detasar.github.io/regression-conformal-prediction-research-atlas/site/index.html",
        "https://detasar.github.io/regression-conformal-prediction-research-atlas/paper/article.html",
        "https://detasar.github.io/regression-conformal-prediction-research-atlas/paper/supplement.html",
        "https://detasar.github.io/regression-conformal-prediction-research-atlas/site/kg_browser.html",
        "https://detasar.github.io/regression-conformal-prediction-research-atlas/atlas/results/index.html",
        "https://detasar.github.io/regression-conformal-prediction-research-atlas/atlas/scope/index.html",
    ]:
        assert f"<loc>{url}</loc>" in sitemap
    assert "<svg" in favicon and "#151922" in favicon
    assert "preferred-citation:" in citation_cff
    assert "repository-code:" in citation_cff
    assert "@misc{tasar2026regression_cp_research_atlas" in citation_bib
    assert "TY  - GEN" in citation_ris
    for page, pdf in [
        ("paper/article.html", "paper/article.pdf"),
        ("paper/supplement.html", "paper/supplement.pdf"),
        ("paper/research_document.html", "paper/article.pdf"),
    ]:
        text = (root / page).read_text(encoding="utf-8")
        assert 'name="citation_title"' in text
        assert 'name="citation_author" content="Tasar, Emre"' in text
        assert 'name="citation_publication_date" content="2026/07/10"' in text
        assert 'name="citation_keywords"' in text
        assert 'name="DC.title"' in text
        assert 'type="application/ld+json"' in text
        assert 'type="application/x-bibtex"' in text
        assert 'type="application/x-research-info-systems"' in text
        assert pdf in text


def test_public_pdfs_include_scholarly_metadata() -> None:
    root = repo_root()
    expected = {
        "paper/article": [
            "Regression Conformal Prediction Under Neutral Interpretation Scope",
            "Emre Tasar, Data Scientist",
            "conformal prediction, regression, prediction intervals",
        ],
        "paper/supplement": [
            "Supplementary Document for the Regression CP Research Atlas",
            "Emre Tasar, Data Scientist",
            "conformal prediction, regression, prediction intervals",
        ],
    }
    for stem, tokens in expected.items():
        tex = (root / f"{stem}.tex").read_text(encoding="utf-8")
        assert "% public-pdf-tagged-tabular-v1" in tex
        assert "\\begin{longtable}" not in tex
        assert "\\begin{tabular}" in tex
        assert "% public-pdf-tagging-v1" in tex
        assert "\\DocumentMetadata{testphase={phase-III},pdfstandard=ua-2,lang=en-US}" in tex
        assert "% public-pdf-metadata-v1" in tex
        assert "\\hypersetup{%" in tex
        assert "pdftitle={" in tex
        assert "pdfauthor={Emre Tasar, Data Scientist}" in tex
        assert "pdfsubject={Audited regression conformal prediction Research Atlas" in tex
        assert "pdfkeywords={conformal prediction, regression, prediction intervals" in tex
        assert "pdflang={en-US}" in tex
        pdfinfo = shutil.which("pdfinfo")
        if pdfinfo:
            result = subprocess.run(
                [pdfinfo, str(root / f"{stem}.pdf")],
                check=True,
                capture_output=True,
                text=True,
            )
            for token in tokens:
                assert token in result.stdout
            assert "Tagged:          yes" in result.stdout


def test_public_surfaces_use_pipeline_level_empirical_headline() -> None:
    root = repo_root()
    headline = (
        "Under the current coverage criterion, the fixed-GBM CQR pipeline was most "
        "frequently selected; Mondrian calibration and CV+ were secondary candidates. "
        "These results do not identify a universally superior conformal method."
    )
    pages = [
        root / "README.md",
        root / "site/index.html",
        root / "paper/research_document.html",
        root / "paper/article.html",
        root / "paper/supplement.html",
        root / "atlas/index.html",
        root / "atlas/results/index.html",
    ]
    missing = [
        str(path.relative_to(root))
        for path in pages
        if headline not in path.read_text(encoding="utf-8")
    ]
    assert not missing


def test_public_reader_surfaces_avoid_legacy_frontier_language() -> None:
    root = repo_root()
    pages = [
        root / "README.md",
        root / "EVIDENCE_SCOPE.md",
        root / "site/index.html",
        root / "site/kg_browser.html",
        root / "paper/research_document.md",
        root / "paper/research_document.html",
        root / "paper/individual_experiment_report.md",
        root / "paper/article.tex",
        root / "paper/article.html",
        root / "paper/supplement.tex",
        root / "paper/supplement.html",
        root / "atlas/index.html",
        root / "atlas/results/index.html",
        root / "evidence/claim_evidence_matrix.md",
    ]
    violations = []
    for path in pages:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in ("frontier", "near nominal", "near-nominal", "near_nominal"):
            if phrase in text:
                violations.append((str(path.relative_to(root)), phrase))
    assert not violations


def test_public_paper_surfaces_use_public_source_references() -> None:
    root = repo_root()
    pages = [
        root / "paper/research_document.md",
        root / "paper/research_document.html",
        root / "paper/individual_experiment_report.md",
        root / "paper/article.tex",
        root / "paper/article.html",
        root / "paper/supplement.tex",
        root / "paper/supplement.html",
    ]
    forbidden = [
        "experiments/regression/Research Document/",
        "experiments/regression/manuscript/",
        "experiments/regression/reports/",
        "experiments/regression/catalogs/",
        "study/research_document/Research Document_",
        "study/catalogs/Research Document_",
        "Research Document_",
        "group inference_",
    ]
    violations = []
    for path in pages:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for phrase in forbidden:
            if phrase in text:
                violations.append((str(path.relative_to(root)), phrase))
    assert not violations


def test_public_paper_surfaces_humanize_literature_citations() -> None:
    root = repo_root()
    pages = [
        root / "paper/research_document.md",
        root / "paper/research_document.html",
        root / "paper/individual_experiment_report.md",
        root / "paper/article.tex",
        root / "paper/article.html",
        root / "paper/supplement.tex",
        root / "paper/supplement.html",
    ]
    citation_keys = [
        "barber2020jackknife_plus",
        "kim2020jackknife_after_bootstrap",
        "lei2017distribution_free_regression",
        "nouretdinov2018ivapd",
        "nouretdinov2024ivapd_applications",
        "petej2026inductive_venn_abers_regressors",
        "romano2019conformalized_quantile_regression",
        "vanderlaan2025generalized_venn_abers",
    ]
    violations = []
    combined = []
    for path in pages:
        text = path.read_text(encoding="utf-8", errors="ignore")
        combined.append(text)
        for key in citation_keys:
            if f"@{key}" in text:
                violations.append((str(path.relative_to(root)), key))
    assert not violations
    joined = "\n".join(combined)
    for label in [
        "Lei et al. (2017)",
        "Romano et al. (2019)",
        "Barber et al. (2020)",
        "Kim et al. (2020)",
        "Nouretdinov et al. (2018)",
        "Petej and Vovk (2026)",
        "Van Der Laan and Alaa (2025)",
    ]:
        assert label in joined
    research_html = (root / "paper/research_document.html").read_text(
        encoding="utf-8"
    )
    assert "*Predictive inference with the jackknife+*" not in research_html
    assert "<em>Predictive inference with the jackknife+</em>" in research_html
    assert '<a href="https://arxiv.org/abs/1905.02928">' in research_html


def test_public_reader_surfaces_label_intervals_as_diagnostic_bands() -> None:
    root = repo_root()
    pages = [
        root / "paper/research_document.md",
        root / "paper/research_document.html",
        root / "paper/individual_experiment_report.md",
        root / "paper/article.tex",
        root / "paper/article.html",
        root / "paper/supplement.tex",
        root / "paper/supplement.html",
    ]
    violations = []
    for path in pages:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in (
            "95% interval",
            "95\\% interval",
            "95% ci",
            "95\\% ci",
            "audited 95%",
            "confidence intervals",
            "uncertainty intervals",
        ):
            if phrase in text:
                violations.append((str(path.relative_to(root)), phrase))
    assert not violations


def test_public_repository_text_has_no_private_review_boilerplate() -> None:
    root = repo_root()
    checked_suffixes = {".md", ".html", ".tex", ".py", ".toml", ".yml", ".yaml", ".cff"}
    skipped = {
        root / "site" / "kg_browser_data.json",
    }
    violations = []
    for path in root.rglob("*"):
        if ".git" in path.parts or path in skipped or not path.is_file():
            continue
        if path.suffix.lower() not in checked_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for phrase in FORBIDDEN_PUBLIC_PHRASES:
            if phrase in text:
                violations.append((str(path.relative_to(root)), phrase))
    assert not violations
