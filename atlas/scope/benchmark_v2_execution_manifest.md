# Benchmark v2 Execution Manifest

Status: execution contract defined not executed.

Turn the Benchmark v2 design requirements into a runnable contract before any new result rows are generated.

## Paired Cell Key

`source_dataset_id`, `task_variant_id`, `split_regime`, `alpha`, `seed`, `split_hash`, `learner_family`, `learner_config_id`, `preprocessing_policy_id`

## Run Grid

- Alpha grid: 0.01, 0.05, 0.1, 0.15, 0.2
- Random seeds: 101, 211, 307, 409, 503, 607, 709, 811, 907, 1009
- Learner families: ridge, elastic_net, hist_gradient_boosting, random_forest, extra_trees, knn, nystroem_svr
- Primary conformal methods: split_abs, cqr_model_matched, cv_plus, jackknife_plus, mondrian_abs
- Regimes: iid, grouped, temporal, spatial, covariate_shift

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
