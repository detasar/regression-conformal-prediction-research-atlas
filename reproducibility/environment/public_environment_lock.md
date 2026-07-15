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
python -m pytest -m "unit or artifact_public or smoke" -q -k "reader_surfaces or html_metadata or seo_and_citation or pdfs_include or pipeline_level or legacy_frontier or public_source_references or literature_citations or diagnostic_bands or repository_text"
python -m pytest -m "unit or artifact_public or smoke" -q
python -m experiments.regression.scripts.run_regression_pilot --help
python -m experiments.regression.scripts.run_regression_pilot --max-runs 0
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

## Excluded From This Public Lock

- Raw datasets
- Local caches
- Credentials
- Full source ledgers
- Prediction bundles
- Nonredistributable source artifacts
