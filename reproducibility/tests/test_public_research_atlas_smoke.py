"""Public Research Atlas smoke tests."""

from __future__ import annotations

import importlib
import importlib.resources as resources
import csv
import json
import os
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urlparse

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.artifact_public]

FORBIDDEN_PUBLIC_PHRASES = tuple(
    " ".join(parts)
    for parts in (
        ("Document", "status"),
        ("Research", "Document", "release", "render"),
        ("private", "final-prose"),
        ("not", "final", "manuscript", "prose"),
        ("not", "a", "release", "artifact"),
        ("not", "a", "method", "recommendation"),
        ("not", "method", "recommendations"),
        ("not", "a", "method-selection", "claim"),
        ("not", "as", "recommended", "methods"),
        ("not", "as", "a", "ranking", "rule"),
        ("CQR/CV+", "were", "observed", "as", "strong", "practical", "candidates"),
        ("Read", "CQR/CV+", "as", "strong", "practical", "candidates"),
        ("CQR/CV+", "can", "be", "described", "as", "strong", "practical", "candidates"),
        ("Reading", "note"),
        ("Boundary:", "Do", "not"),
        ("not", "an", "independent", "scientific", "claim"),
        ("Do", "not", "cite"),
        ("not", "yet", "the", "final", "public", "citable", "repository"),
        ("recommendation", "engine"),
        ("claim", "generator"),
        ("public", "release", "remains", "closed"),
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
    kg_text = kg_path.read_text(encoding="utf-8")
    legacy_source_key = "source_key" + "_hash"
    assert legacy_source_key not in kg_text
    assert "source_key_fingerprint" in kg_text


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
    assert "map-legend" in browser


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


def test_public_rebuild_commands_run() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root() / "reproducibility")
    modules = [
        "experiments.regression.scripts.build_public_release_scope",
        "experiments.regression.scripts.build_public_research_atlas",
        "experiments.regression.scripts.build_research_atlas_package",
    ]
    for module in modules:
        result = subprocess.run(
            [sys.executable, "-m", module, "--package-root", str(repo_root())],
            cwd=repo_root(),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "\"status\": \"pass\"" in result.stdout


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
        "display_interval_policy",
    } <= fieldnames
    legacy_coverage_status = "near" + "_nominal"
    legacy_selection_flag = "frontier" + "_flag"
    assert legacy_coverage_status not in fieldnames
    assert legacy_selection_flag not in fieldnames
    assert any(row["numerical_pathology_flag"] == "true" for row in rows)
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
        "Method-Family Selection Density",
        "Coverage-Width Map",
        "CQR Backend Sensitivity Map",
        'id="explorer-summary"',
        'id="coverage-width-map"',
        'id="cqr-delta-wrap"',
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
            ("atlas/", "paper/", "site/", "evidence/")
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
        root / "atlas/index.html",
        root / "atlas/results/index.html",
        root / "site/kg_browser.html",
    ]
    for page in pages:
        text = page.read_text(encoding="utf-8")
        assert '<meta name="description"' in text
        assert '<link rel="canonical"' in text
        assert 'type="application/ld+json"' in text
        assert "skip-link" in text
        assert ":focus-visible" in text
    assert "<caption>" in (root / "atlas/results/index.html").read_text(encoding="utf-8")
    kg_text = (root / "site/kg_browser.html").read_text(encoding="utf-8")
    assert "aria-live" in kg_text
    assert "fallback" in kg_text.lower()


def test_public_surfaces_use_pipeline_level_empirical_headline() -> None:
    root = repo_root()
    headline = (
        "Within this retrospective and imbalanced experiment surface, the fixed-GBM "
        "CQR pipeline was selected most often under the coverage-gated interval-score "
        "rule; Mondrian calibration and CV+ were secondary practical candidates."
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
