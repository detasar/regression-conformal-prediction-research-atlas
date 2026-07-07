# Regression Conformal Prediction Study

Author: Emre Tasar, Data Scientist  
Contact: detasar@gmail.com

This repository is a public Research Atlas for a neutral empirical study of regression conformal prediction. It contains the Research Document, compact report, broad supplement, individual experiment report, browsable knowledge graph, citation metadata, and reproducibility materials.

## Short Result

CQR/CV+ were observed as strong practical candidates in these experiments. This means CQR and CV+ behaved as strong practical candidates inside this audited experiment surface. It is experiment-scoped evidence, not a universal best-method claim or production recipe.

The expected strong regression solution did not emerge in these experiments. The Venn-Abers statement is bridge-specific negative evidence for the evaluated regression bridge, not a rejection of the broader Venn-Abers, predictive-distribution, or generalized-calibration literature.

## Artifacts

1. `paper/research_document.md` is the primary Research Document.
2. `paper/article.html` is the compact report.
3. `paper/article.pdf` is the compiled PDF of the report.
4. `paper/supplement.html` is the broad supplementary document.
5. `paper/supplement.pdf` is the compiled supplementary PDF.
6. `site/index.html` is the public web entry point.
7. `site/kg_browser.html` is the browsable knowledge graph.
8. `evidence/claim_evidence_matrix.md` summarizes the claim-evidence map.

GitHub Pages: <https://detasar.github.io/regression-conformal-prediction-research-atlas/>  
Public repository: <https://github.com/detasar/regression-conformal-prediction-research-atlas>

## What This Repository Establishes

The repository establishes that a large, audited regression conformal prediction experiment was run and reported under neutral scientific boundaries. It reports observed coverage, width, robustness, negative evidence, and claim gates.

## What This Study Does Not Establish

- A general best-method recommendation or global winner.
- Population-level group inference claims.
- Bounded-support validity claims.
- Validated Venn-Abers regression interval claims.
- Production or deployment advice.
- Citation of the original working repository as the final public artifact.

## Reproducibility

Reproducibility materials are under `reproducibility/`. Raw data, local caches, credentials, and nonredistributable files are excluded from this public release.

From the repository root:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest -m "unit or artifact_public or smoke"
python -m experiments.regression.scripts.run_regression_pilot --help
```

The public CI uses the same marker-selected smoke path. Full private ledgers, local caches, external data pulls, and long reruns are intentionally outside the public smoke test surface.

## Citation

Use this repository and its `CITATION.cff` as the citation surface. The integrated Research Document and supplementary knowledge graph are part of the release.
