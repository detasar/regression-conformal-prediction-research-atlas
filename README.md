# Regression Conformal Prediction Research Atlas

Author: Emre Tasar, Data Scientist
Contact: detasar@gmail.com

This repository is a scientific evidence atlas for a neutral empirical study of regression conformal prediction. It contains the Research Document, compact report, broad supplement, browsable knowledge graph, aggregate result cube, interpretation registry, provenance receipts, and reproducibility materials.

## Atlas At A Glance

| Surface | Public Count |
|---|---:|
| Audited synthesis rows | 145,839 |
| Canonical completed rows | 156,233 |
| Publication datasets | 67 |
| Dataset-alpha cells | 95 |
| Publication conformal-method labels | 28 |
| KG nodes | 3,643 |
| KG edges | 21,019 |
| KG isolated nodes | 0 |

## Short Result

Under the current coverage criterion, the fixed-GBM CQR pipeline was most frequently selected; Mondrian calibration and CV+ were secondary candidates. The comparison is experiment-scoped; using the pattern in a new setting would need its own validation plan. Broader use would require validation beyond this experiment.

The completed backend-confound check added `4,564` model-matched CQR runs and `224` paired dataset-alpha-model-family cells. Coverage-eligible interval-score selections were fixed-GBM CQR `116`, model-matched CQR `71`, and neither `37`. This comparison shows how much the CQR result depends on the model backend.

The expected strong regression solution did not emerge in these experiments. The Venn-Abers statement is bridge-specific negative evidence for the evaluated regression bridge. It should be read separately from the broader Venn-Abers, predictive-distribution, and generalized-calibration literatures.

## Package Contents

1. `atlas/index.html` is the HTML entry point for the evidence atlas.
2. `atlas/scope/experiment_scope.json` records the experiment accounting scope.
3. `atlas/results/result_cube_public.csv` is the aggregate result cube.
4. `atlas/datasets/dataset_catalog.csv` and `atlas/methods/method_catalog.csv` expose the dataset and method universes.
5. `atlas/claims/claim_registry.json` records interpretation scope and evidence-supported statements.
6. `paper/research_document.html` is the primary Research Document for web reading; `paper/research_document.md` is the Markdown source.
7. `paper/article.html` and `paper/article.pdf` are the compact report.
8. `paper/supplement.html` and `paper/supplement.pdf` are the broad supplementary document.
9. `site/index.html` is the web entry point.
10. `site/kg_browser.html` is the browsable evidence graph.
11. `evidence/public_artifact_manifest.json` resolves public KG source/evidence references.
12. `ACCESSIBILITY.md` records accessibility support, known limits, and feedback contact.

GitHub Pages: <https://detasar.github.io/regression-conformal-prediction-research-atlas/>
Public repository: <https://github.com/detasar/regression-conformal-prediction-research-atlas>

## What This Repository Contains

This repository summarizes a large audited regression conformal prediction experiment. It exposes the study as aggregate evidence: accounting summaries, dataset and method catalogs, result cube, backend sensitivity analysis, negative evidence, reading limits, and provenance receipts.

## Reading Guide

These materials support an experiment-scoped empirical reading. Production use, universal method selection, population-level group inference, bounded-support validity, and validated Venn-Abers regression interval claims would require separate, pre-specified validation work.

## Reproducibility

Reproducibility materials are under `reproducibility/`. Raw data, local caches, credentials, and nonredistributable files are excluded from the repository.

The public smoke environment is recorded in `reproducibility/environment/public_environment_lock.md`, with exact package pins in `reproducibility/environment/requirements-public-lock.txt`.

From the repository root:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest -m "unit or artifact_public or smoke"
python -m experiments.regression.scripts.run_regression_pilot --help
python -m experiments.regression.scripts.run_regression_pilot --max-runs 0
python -m experiments.regression.scripts.run_benchmark_v2_chunk --chunk-id benchmark_v2_chunk_0001 --package-root . --dry-run
```

The public CI runs the same marker-selected suite in named lanes: package and
rebuild checks, artifact/schema/link checks, reader SEO and accessibility
checks, and then the full public smoke suite. Full source ledgers, local caches,
external data pulls, and long reruns are intentionally outside the public smoke
test surface.

Benchmark v2 execution rows that fetch external datasets require the optional
external-data environment:

```bash
python -m pip install -e ".[external-data]"
```

## Citation

Use this repository and its `CITATION.cff` as the citation surface. The repository includes the Research Document, article, supplement, knowledge graph browser, and reproducibility files.
