# Benchmark v2 Execution Resume Contract

This contract makes the Benchmark v2 grid chunkable and restartable. Aggregate progress is reported separately from raw execution ledgers.

## Status

- Chunk manifest status: `chunk_manifest_ready_execution_in_progress`
- Result generation status: `in_progress`
- Chunk count: `42`
- Paired cells: `8400`
- Method rows: `42000`
- Paired-cell chunk size: `200`
- Method rows per paired cell: `5`

## Resume Semantics

1. A chunk is the resumable unit for execution monitoring and checkpoint storage.
2. A paired cell is never split across chunks.
3. Each initial chunk starts as planned, not attempted, not completed, not failed, and not skipped.
4. Chunk status must be reconciled against the run-status ledger before any result interpretation.
5. Checkpoints are stored under the chunk-specific checkpoint directory recorded in the manifest.

## Dry-Run Inspection

The public package includes a dry-run chunk inspector. It validates chunk metadata and reports the planned row range without running ML experiments.

```bash
python -m experiments.regression.scripts.run_benchmark_v2_chunk --chunk-id benchmark_v2_chunk_0001 --package-root . --dry-run
```

## Invariants

- `sum(chunks.paired_cell_count)` equals the manifest paired-cell count.
- `sum(chunks.method_row_count)` equals the manifest method-row count.
- `first_paired_cell_key` and `last_paired_cell_key` define inclusive paired-cell boundaries.
- `first_method_row_key` and `last_method_row_key` define inclusive method-row boundaries inside those paired cells.
- The source run grid and initial status ledger paths are recorded on every chunk row.
- Aggregate execution progress is reported in `atlas/benchmark_v2/execution_status.json`; raw execution ledgers remain outside the public package.
