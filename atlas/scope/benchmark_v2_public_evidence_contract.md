# Benchmark v2 Public Evidence Contract

Status: contract defined not populated.

State the minimum public evidence required before Benchmark v2 results can be interpreted beyond traceability.

## Required Public Artifacts

| Artifact | Path | Minimum columns |
|---|---|---|
| `source_dataset_registry` | `benchmark_v2/source_dataset_registry.csv` | `source_dataset_id`, `source_family`, `version`, `license`, `retrieval_command_or_url`, `content_hash_or_accession`, `redistribution_status` |
| `task_variant_registry` | `benchmark_v2/task_variant_registry.csv` | `task_variant_id`, `source_dataset_id`, `target_name`, `target_transform`, `split_regime`, `eligibility_reason` |
| `run_grid_manifest` | `benchmark_v2/run_grid_manifest.parquet` | `method_row_key`, `paired_cell_key`, `alpha`, `seed`, `split_hash`, `learner_config_id`, `model_id`, `learner_params_json`, `learner_params_hash`, `conformal_method_config_id`, `planned_status` |
| `run_status_ledger` | `benchmark_v2/run_status_ledger.parquet` | `method_row_key`, `paired_cell_key`, `conformal_method_config_id`, `attempted`, `completed`, `failed`, `skipped`, `failure_reason`, `checkpoint_path_hash` |
| `aggregate_result_cube` | `benchmark_v2/aggregate_result_cube.parquet` | `source_dataset_id`, `task_variant_id`, `alpha`, `learner_config_id`, `conformal_method_config_id`, `coverage`, `width`, `interval_score`, `numerical_pathology_flag` |
| `clustered_uncertainty_summary` | `benchmark_v2/clustered_uncertainty_summary.json` | `summary_unit`, `bootstrap_policy`, `method_comparison`, `estimate`, `diagnostic_band` |
| `environment_lock` | `benchmark_v2/environment_lock.json` | `python_version`, `platform`, `package_locks`, `runner_commit`, `config_hash` |

## Publishability Gates

1. Every planned/attempted/completed/failed/skipped count is public or has a documented exclusion reason.
2. Every source dataset has version, license, retrieval, and hash/accession metadata.
3. Every run row has a paired-cell key and split hash.
4. Every CV+/jackknife row records fold-local preprocessing policy.
5. Every excluded raw artifact is represented by a public manifest row.
6. No primary result is reported before the aggregate cube and status ledger agree on completed cells.
