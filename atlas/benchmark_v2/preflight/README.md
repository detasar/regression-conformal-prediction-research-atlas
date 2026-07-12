# Benchmark v2 Preflight

This directory contains public preflight artifacts for the forward Benchmark v2 protocol. They do not contain completed Benchmark v2 result rows.

## Status

- Overall status: `preflight_templates_ready_execution_not_started`
- Result generation status: `not_started`
- Estimated primary planned rows: `210000`
- Estimated diagnostic planned rows: `84000`
- Estimated total planned rows: `294000`

## Files

- `source_dataset_registry_template.csv`: required source-dataset registry columns.
- `task_variant_registry_template.csv`: required task-variant registry columns.
- `run_grid_manifest_preview.csv`: paired-grid preview for one placeholder task variant.
- `run_status_ledger_template.csv`: required run-status ledger columns before execution.
- `run_grid_cardinality.json`: deterministic cardinality calculation from the frozen execution manifest.
- `preflight_readiness_checklist.*`: preflight gates and current statuses.
