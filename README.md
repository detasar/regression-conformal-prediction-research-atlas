# Regression Conformal Prediction Research Atlas

Author: Emre Tasar, Data Scientist
Contact: detasar@gmail.com

This repository is a public scientific evidence atlas for a neutral empirical study of regression conformal prediction. It contains the Research Document, compact report, broad supplement, browsable knowledge graph, public aggregate result cube, interpretation registry, provenance receipts, and reproducibility materials.

## Atlas At A Glance

| Surface | Public Count |
|---|---:|
| Publication-scoped completed rows | 145,839 |
| Canonical completed rows | 156,233 |
| Publication datasets | 67 |
| Dataset-alpha cells | 95 |
| Publication conformal-method labels | 28 |
| KG nodes | 3,643 |
| KG edges | 21,019 |
| KG isolated nodes | 0 |

## Short Result

Within this retrospective and imbalanced experiment surface, the fixed-GBM CQR pipeline was selected most often under the coverage-gated interval-score rule; Mondrian calibration and CV+ were secondary practical candidates. Broader use would require validation beyond this experiment.

The completed backend-confound check added `4,564` model-matched CQR runs and `224` paired dataset-alpha-model-family cells. Coverage-eligible interval-score selections were fixed-GBM CQR `116`, model-matched CQR `71`, and neither `37`. This comparison is the backend-sensitivity context for the CQR signal.

The expected strong regression solution did not emerge in these experiments. The Venn-Abers statement is bridge-specific negative evidence for the evaluated regression bridge. It should be read separately from the broader Venn-Abers, predictive-distribution, and generalized-calibration literatures.

## Artifacts

1. `atlas/index.html` is the HTML entry point for the public evidence atlas.
2. `atlas/scope/experiment_scope.json` records the experiment accounting scope.
3. `atlas/results/result_cube_public.csv` is the public aggregate result cube.
4. `atlas/datasets/dataset_catalog.csv` and `atlas/methods/method_catalog.csv` expose the dataset and method universes.
5. `atlas/claims/claim_registry.json` records interpretation boundaries and reader-safe evidence statements.
6. `paper/research_document.html` is the primary Research Document for web reading; `paper/research_document.md` is the Markdown source.
7. `paper/article.html` and `paper/article.pdf` are the compact report.
8. `paper/supplement.html` and `paper/supplement.pdf` are the broad supplementary document.
9. `site/index.html` is the public web entry point.
10. `site/kg_browser.html` is the browsable evidence graph.
11. `evidence/public_artifact_manifest.json` resolves public KG source/evidence references.

GitHub Pages: <https://detasar.github.io/regression-conformal-prediction-research-atlas/>
Public repository: <https://github.com/detasar/regression-conformal-prediction-research-atlas>

## What This Repository Establishes

The repository establishes that a large, audited regression conformal prediction experiment was run and reported under neutral scientific boundaries. It exposes the experiment universe as public aggregate evidence: scope accounting, dataset and method catalogs, result cube, backend sensitivity analysis, negative evidence, interpretation boundaries, and provenance receipts.

## Interpretation Scope

The public artifacts support experiment-scoped empirical reading. Production use, universal method selection, population-level group inference, bounded-support validity, and validated Venn-Abers regression interval claims would require separate, pre-specified validation work.

## Reproducibility

Reproducibility materials are under `reproducibility/`. Raw data, local caches, credentials, and nonredistributable files are excluded from the repository.

From the repository root:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest -m "unit or artifact_public or smoke"
python -m experiments.regression.scripts.run_regression_pilot --help
```

The public CI uses the same marker-selected smoke path. Full working ledgers, local caches, external data pulls, and long reruns are intentionally outside the public smoke test surface.

## Citation

Use this repository and its `CITATION.cff` as the citation surface. The integrated Research Document and supplementary knowledge graph are part of the Research Atlas.
