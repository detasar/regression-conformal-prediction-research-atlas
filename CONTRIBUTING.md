# Contributing

This repository is a Research Atlas for an audited regression conformal prediction study.

## Scope

Contributions should preserve the published evidence boundary:

- Keep reader-facing prose English-only.
- Keep empirical language descriptive and tied to this experiment.
- Do not add raw data, credentials, caches, restricted ledgers, or nonredistributable artifacts.
- Regenerate atlas outputs from the source builders instead of editing generated files by hand.

## Local Validation

```bash
python -m pip install -e ".[test]"
python -m pytest -m "unit or artifact_public or smoke" -q -k "core_imports or package_data or wheel_contains or root_command or rebuild_commands"
python -m pytest -m "unit or artifact_public or smoke" -q -k "kg_and_artifact_manifest or scope_catalogs or source_metadata or benchmark_v2 or audit_response or maintenance_quality or schema_registry or result_cube_schema or results_page or provenance_page or accounting_matrix or html_links"
python -m pytest -m "unit or artifact_public or smoke" -q -k "reader_surfaces or html_metadata or seo_and_citation or pdfs_include or pipeline_level or legacy_frontier or public_source_references or literature_citations or diagnostic_bands or repository_text"
python -m pytest -m "unit or artifact_public or smoke"
python -m experiments.regression.scripts.run_regression_pilot --help
python -m experiments.regression.scripts.run_regression_pilot --max-runs 0
sha256sum -c CHECKSUMS.sha256
```

## Artifact Integrity

`CHECKSUMS.sha256` records file hashes for the published repository snapshot. If generated files change, regenerate the package and update the checksum file in the same commit.
