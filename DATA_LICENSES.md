# Data Licenses And Redistribution Scope

This Research Atlas publishes aggregate study outputs, source metadata, and reproducibility code. It does not redistribute raw external datasets, restricted ledgers, local caches, prediction bundles, credentials, or nonredistributable source artifacts.

## Public Dataset Metadata

Dataset provenance is documented in:

- `atlas/datasets/source_metadata_matrix.md`
- `atlas/datasets/source_metadata_matrix.csv`
- `atlas/datasets/source_metadata_matrix.json`

Those files record source names, retrieval status, license notes when available, public-source indicators, and whether this package includes the raw source data.

## Artifact Classes

| Artifact class | Included here? | License / status | Notes |
|---|---:|---|---|
| Reproducibility code and tests | Yes | Repository `LICENSE` | Public smoke and artifact checks run without private ledgers. |
| Article, supplement, site, and README | Yes | Repository `LICENSE` unless an upstream citation says otherwise | Scholarly citations remain attached to method and dataset descriptions. |
| Aggregate result tables and atlas metadata | Yes | Public Research Atlas release data | These are derived aggregate outputs, not raw external datasets. |
| Raw external datasets | No | Governed by upstream providers | Use the source metadata matrix to locate upstream terms. |
| Restricted ledgers, caches, and prediction bundles | No | Not redistributed | Public manifests summarize their role without copying restricted files. |
| Public hash receipts and provenance summaries | Yes | Repository `LICENSE` | Content hashes apply only to files included in this public package. |

## Citation And Reuse

Cite the Research Atlas repository for this release. Cite upstream dataset and method sources according to their own terms when reusing or extending the study.
