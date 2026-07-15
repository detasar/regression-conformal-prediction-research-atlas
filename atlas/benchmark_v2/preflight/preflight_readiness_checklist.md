# Benchmark v2 Preflight Readiness Checklist

- Overall status: `pre_execution_ledger_ready_results_not_started`
- Result generation status: `not_started`

| Check | Status | Evidence |
|---|---|---|
| `protocol_frozen` | `pass` | `atlas/scope/benchmark_v2_protocol.json` |
| `execution_manifest_defined` | `pass` | `atlas/scope/benchmark_v2_execution_manifest.json` |
| `public_evidence_contract_defined` | `pass` | `atlas/scope/benchmark_v2_public_evidence_contract.json` |
| `preflight_templates_published` | `pass` | `atlas/benchmark_v2/preflight/` |
| `source_dataset_registry_populated` | `pass` | `atlas/benchmark_v2/preflight/source_dataset_registry.csv` |
| `task_variant_registry_populated` | `pass` | `atlas/benchmark_v2/preflight/task_variant_registry.csv` |
| `run_status_ledger_populated` | `pass` | `atlas/benchmark_v2/preflight/run_status_ledger_initial.csv.gz` |
| `benchmark_v2_results_generated` | `not_started` | `benchmark_v2/aggregate_result_cube.parquet` |
| `candidate_run_grid_manifest_published` | `pass` | `atlas/benchmark_v2/preflight/run_grid_manifest_candidate.csv.gz` |
| `execution_chunks_published` | `pass` | `atlas/benchmark_v2/preflight/execution_chunks.json` |
