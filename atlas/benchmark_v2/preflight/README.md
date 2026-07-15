# Benchmark v2 Preflight

This directory contains public preflight artifacts for the forward Benchmark v2 protocol. They do not contain completed Benchmark v2 result rows.

## Status

- Overall status: `pre_execution_ledger_ready_results_not_started`
- Result generation status: `not_started`
- Estimated primary planned rows: `210000`
- Estimated diagnostic planned rows: `84000`
- Estimated total planned rows: `294000`
- Candidate task variants represented in full primary grid: `24`
- Candidate primary planned run-grid rows: `210000`

## Files

- `source_dataset_registry_template.csv`: required source-dataset registry columns.
- `source_dataset_registry.csv`: frozen pre-execution source-dataset registry copied from the verified candidate registry.
- `task_variant_registry_template.csv`: required task-variant registry columns.
- `task_variant_registry.csv`: frozen pre-execution task-variant registry copied from the verified candidate registry.
- `run_grid_manifest_preview.csv`: paired-grid preview for one placeholder task variant.
- `run_grid_manifest_candidate.csv.gz`: full planned primary run-grid manifest for the current 24 Benchmark v2 candidate task variants.
- `run_status_ledger_template.csv`: required run-status ledger columns before execution.
- `run_status_ledger_initial.csv.gz`: initialized planned-row status ledger; no rows are attempted or completed.
- `run_grid_cardinality.json`: deterministic cardinality calculation from the frozen execution manifest.
- `preflight_readiness_checklist.*`: preflight checks and current statuses.
