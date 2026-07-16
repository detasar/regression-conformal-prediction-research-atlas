# Benchmark v2 Execution Manifest

Status: execution started resumable.

Turn the Benchmark v2 design requirements into a runnable contract and record the execution controls used by the resumable runner.

## Paired Cell Key

`source_dataset_id`, `task_variant_id`, `split_regime`, `alpha`, `seed`, `split_hash`, `learner_family`, `learner_config_id`, `preprocessing_policy_id`

## Run Grid

- Alpha grid: 0.01, 0.05, 0.1, 0.15, 0.2
- Random seeds: 101, 211, 307, 409, 503, 607, 709, 811, 907, 1009
- Learner families: ridge, elastic_net, hist_gradient_boosting, random_forest, extra_trees, knn, nystroem_svr
- Primary conformal methods: split_abs, cqr_model_matched, cv_plus, jackknife_plus, mondrian_abs
- Regimes: iid, grouped, temporal, spatial, covariate_shift

## Computational Execution Policy

- CV+ max train rows: `None`
- Jackknife+ max train rows: `500`
- Reason: Exact jackknife+ refits one model per training row. Rows above the cap are recorded as skipped_method with the threshold in the run notes rather than silently approximated.
- Restart command suffix: `--jackknife-plus-max-train-rows 500 --retry-skipped-status skipped_unsupported_regime`
- Retry skipped statuses after policy upgrade: `skipped_unsupported_regime`
- Covariate shift split policies: `theta3_bin_upper_quartile_target_v1` for `openml_kin8nm:openml_kin8nm_y:covariate_shift`; `wine_color_white_source_red_target_v1` for `uci_wine_quality:uci_wine_quality_dedup:covariate_shift`
- Parallel workers: `4` workers over disjoint chunk-index ranges.
- Worker ranges: `benchmark_v2_worker_01` chunks 1-10; `benchmark_v2_worker_02` chunks 11-21; `benchmark_v2_worker_03` chunks 22-32; `benchmark_v2_worker_04` chunks 33-42
- Ledger contract: Each chunk owns one execution ledger and checkpoint tree. Workers must use non-overlapping chunk-index ranges; summaries and logs are worker-specific, while chunk ledgers remain the authoritative resume state.

## Frozen Learner Configurations

| Learner family | Runner model id | Learner config id | Parameters |
|---|---|---|---|
| `ridge` | `ridge` | `ridge_benchmark_v2_primary_v1` | `{"alpha": 1.0}` |
| `elastic_net` | `elasticnet` | `elastic_net_benchmark_v2_primary_v1` | `{"alpha": 0.01, "l1_ratio": 0.5}` |
| `hist_gradient_boosting` | `hist_gradient_boosting` | `hist_gradient_boosting_benchmark_v2_primary_v1` | `{"l2_regularization": 0.1, "learning_rate": 0.06, "max_leaf_nodes": 31}` |
| `random_forest` | `random_forest` | `random_forest_benchmark_v2_primary_v1` | `{"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 5, "n_estimators": 300}` |
| `extra_trees` | `extra_trees` | `extra_trees_benchmark_v2_primary_v1` | `{"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 5, "n_estimators": 300}` |
| `knn` | `knn` | `knn_benchmark_v2_primary_v1` | `{"n_neighbors": 15, "p": 2, "weights": "distance"}` |
| `nystroem_svr` | `svr` | `nystroem_svr_benchmark_v2_primary_v1` | `{"C": 1.0, "epsilon": 0.1, "gamma": "scale", "kernel": "rbf"}` |

## Mandatory Invariants

1. Every conformal method is evaluated inside the same learner/config/split cell.
2. CQR is model-matched inside each learner family and is not repeated across unrelated outer model-grid rows.
3. CV+/jackknife preprocessing, feature selection, scaling, capping, and reducers are fit inside each fold.
4. All primary tasks use the same alpha grid and seed list unless a pre-run exclusion is recorded.
5. Regime-specific analyses are aggregated separately before any cross-regime summary.
6. The primary utility rule and sensitivity rules are frozen before execution starts.

## Preprocessing Contract

- Policy ID: `benchmark_v2_fold_local_preprocessing_v1`
- Runner flag: `conformal.plus_fold_local_preprocessing=true`
- Fold-local steps: imputation, scaling, target capping or transformation parameters, supervised feature selection, unsupervised dimensionality reduction, categorical encoding learned from the training fold

## Analysis Plan

- Primary summary unit: `source_dataset_id`
- Primary interval summary: source-dataset-clustered bootstrap.
- Selection rule: coverage tolerance pass, then interval score, with sensitivity to absolute coverage error plus width.
