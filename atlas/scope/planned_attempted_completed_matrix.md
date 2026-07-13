# Planned, Attempted, Completed, Failed, And Skipped Matrix

This public matrix separates aggregate counts that are available in the Research Atlas from phases that require restricted source ledgers. It is intentionally conservative: unavailable attempted, failed, and skipped counts are recorded as unavailable rather than inferred from aggregate outputs.

| Phase | Public row count | Public status | Interpretation | Evidence |
|---|---:|---|---|---|
| `configured_run_cell_estimate` | 25012478 | `deterministic_from_public_yaml_configs` | Configured Cartesian run-cell estimate from public YAML configuration grids. | `atlas/scope/experiment_scope.json` |
| `attempted_rows` | not public | `not_atomically_reconstructable_from_public_package` | Attempted-row accounting requires restricted source ledgers that are not included in the Research Atlas package. | `atlas/scope/benchmark_v2_protocol.json` |
| `failed_rows` | not public | `not_atomically_reconstructable_from_public_package` | Failure counts are tracked in restricted source ledgers; Benchmark v2 requires a publishable attempted/completed/failed/skipped matrix before new result generation. | `atlas/scope/benchmark_v2_protocol.json` |
| `skipped_rows` | not public | `not_atomically_reconstructable_from_public_package` | Skip counts are not independently reconstructable from the public aggregate package. | `atlas/scope/benchmark_v2_protocol.json` |
| `canonical_completed_rows` | 156233 | `public_aggregate_count` | Broader canonical completed ledger accounting represented as an aggregate count. | `atlas/scope/run_accounting_summary.json` |
| `publication_scoped_completed_rows` | 145839 | `public_aggregate_count` | Rows used by the publication-scoped public synthesis. | `atlas/results/result_cube_public.csv` |
