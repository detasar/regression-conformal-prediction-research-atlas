# Benchmark v2 Protocol

Status: protocol defined, not executed.

Benchmark v2 is the forward protocol for a smaller, balanced, paired, leakage-safe regression conformal prediction benchmark. It is included here so the next result-generation phase starts from a frozen scientific design rather than retrospective cleanup.

## Primary Estimand

- Primary comparison unit: `source_dataset_task_alpha_learner_config_split_hash`
- Primary utility rule: pre-specified coverage-lower-bound gate followed by interval score, reported with sensitivity to absolute coverage error and width.
- Unit hierarchy:
  - `source_dataset`
  - `task_variant`
  - `split_regime`
  - `split_hash`
  - `learner_config`
  - `conformal_method_config`

## Design Requirements

1. Use fewer but independently sourced datasets with explicit source/version/license records.
2. Represent task variants under their source dataset instead of counting them as independent datasets.
3. Use the same alpha grid, seed count, split policy, learner/config surface, and conformal wrappers within each paired task.
4. Compare conformal wrappers within exact learner/config/split cells rather than averaging across mismatched model grids.
5. Do not recount a fixed CQR backend across unrelated outer model-grid rows.
6. Fit imputation, scaling, capping, feature selection, and dimensionality reduction inside each CV+/jackknife fold.
7. Separate IID, grouped, temporal, spatial, and shift regimes before aggregation.
8. Freeze the primary utility rule, exclusion rules, and pathology-display policy before compute starts.
9. Report source-dataset-clustered bootstrap or hierarchical meta-analysis rather than row-level pseudo-inference.
10. Reserve untouched post-protocol datasets for external validation.
11. Publish planned, attempted, completed, failed, skipped, and publication-scoped accounting matrices.
12. Publish enough run-level ledger, split hash, environment lock, and aggregate cube material to audit the synthesis.

## Interpretation

Benchmark v2 is a forward protocol. It does not revise the Atlas v0 retrospective results until new, separately versioned runs are completed.
