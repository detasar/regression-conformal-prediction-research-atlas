# Public Environment Lock

This file records the dependency surface used for Research Atlas smoke tests. It is a reproducibility snapshot for this package, not a full lock for restricted long-running experiments or external data acquisition.

## Python

- Required Python: `>=3.10`
- Recommended Python: `3.11`
- Execution mode: `CPU`
- GPU required: `False`

## Install And Smoke Test

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest -m "unit or artifact_public or smoke" -q -k "core_imports or package_data or wheel_contains or root_command or rebuild_commands"
python -m pytest -m "unit or artifact_public or smoke" -q -k "kg_and_artifact_manifest or scope_catalogs or source_metadata or benchmark_v2 or audit_response or maintenance_quality or schema_registry or result_cube_schema or results_page or provenance_page or accounting_matrix or html_links"
python -m pytest -m "unit or artifact_public or smoke" -q -k "reader_surfaces or html_metadata or seo_and_citation or pdfs_include or pipeline_level or selection_language or public_source_references or literature_citations or diagnostic_bands or repository_text"
python -m pytest -m "unit or artifact_public or smoke" -q
python -m experiments.regression.scripts.run_regression_pilot --help
python -m experiments.regression.scripts.run_regression_pilot --max-runs 0
python -m experiments.regression.scripts.run_benchmark_v2_chunk --chunk-id benchmark_v2_chunk_0001 --package-root . --dry-run
```

## Locked Public Smoke Dependencies

| Package | Version |
|---|---:|
| `numpy` | `2.3.5` |
| `pandas` | `3.0.3` |
| `scipy` | `1.16.3` |
| `scikit-learn` | `1.9.0` |
| `PyYAML` | `6.0.3` |
| `matplotlib` | `3.11.0` |
| `loguru` | `0.7.3` |
| `pytest` | `8.4.2` |
| `setuptools` | `80.9.0` |
| `wheel` | `0.45.1` |

## Optional Model Dependencies

These packages are optional in the public package and are not required by the public CI smoke path.

| Package | Constraint |
|---|---:|
| `xgboost` | `>=2.0` |
| `lightgbm` | `>=4.0` |
| `catboost` | `>=1.2` |

## External Data Execution Dependencies

These packages are needed only when executing Benchmark v2 rows that fetch external datasets. They are intentionally outside the public smoke lock, which verifies the packaged atlas, manifests, schemas, links, and dry-run execution contracts without downloading external data.

Install them with:

```bash
python -m pip install -e ".[external-data]"
```

| Package | Constraint |
|---|---:|
| `openml` | `>=0.14` |
| `fairlearn` | `>=0.10` |
| `folktables` | `>=0.0.12` |
| `aif360` | `>=0.6` |

## Benchmark v2 Execution Snapshot

This section records the observed local environment for the long-running Benchmark v2 execution surface. It is separate from the lightweight public smoke-test lock.

- Snapshot date: `2026-07-16`
- Python: `3.13.11`
- Platform: `Linux-6.8.0-134-generic-x86_64-with-glibc2.39`

| Package | Observed version |
|---|---:|
| `numpy` | `2.3.5` |
| `pandas` | `3.0.3` |
| `scipy` | `1.16.3` |
| `scikit-learn` | `1.9.0` |
| `PyYAML` | `6.0.3` |
| `loguru` | `0.7.3` |
| `openml` | `0.15.1` |
| `fairlearn` | `0.14.0` |
| `folktables` | `0.0.12` |
| `aif360` | `0.6.1` |
| `xgboost` | `3.3.0` |
| `lightgbm` | `4.6.0` |
| `catboost` | `1.2.10` |
| `tqdm` | `4.67.1` |
| `joblib` | `1.5.3` |

## Excluded From This Public Lock

- Raw datasets
- Local caches
- Credentials
- Full source ledgers
- Prediction bundles
- Nonredistributable source artifacts
