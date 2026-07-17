# Benchmark v2 Execution Status

This page reports the aggregate execution state for the balanced Benchmark v2 run. It is a progress snapshot, not a result interpretation.

## Snapshot

- Status: `execution_in_progress`
- Result generation status: `in_progress`
- Selected method rows: `42000`
- Observed method rows: `33407`
- Terminal method rows: `33407`
- Completed method rows: `22809`
- Skipped method rows: `10598`
- Failed method rows: `0`
- Pending method rows: `8593`
- Terminal progress fraction: `0.79540476`
- Historical attempt records: `26875`
- Historical failed attempts: `4322`
- Method rows with recovered failed attempts: `4322`

## Status Counts

| Status | Rows |
|---|---:|
| `completed` | 22809 |
| `skipped_infeasible_grouped_regime` | 5250 |
| `skipped_method` | 5348 |

## Historical Attempt Diagnostics

These counts describe raw execution attempts before latest-status resume accounting. A row can have an earlier failed attempt and a later completed or skipped latest status.

| Diagnostic | Rows |
|---|---:|
| Historical attempt records | 26875 |
| Historical failed attempts | 4322 |
| Method rows with historical failed attempts | 4322 |
| Method rows with recovered failed attempts | 4322 |
| Method rows still latest-failed after a historical failed attempt | 0 |
| Method rows with multiple attempt records | 3502 |

### Historical Failed Attempt Reasons

| Reason | Attempts |
|---|---:|
| `infeasible_grouped_split` | 3500 |
| `missing_split_order_column` | 822 |

## Execution Resource Preflight

- Resource state: `paused_until_disk_capacity_restored`
- Pause reason: `free disk below Benchmark v2 guarded-execution minimum`
- Available free disk MiB: `382.797`
- Guard minimum free disk MiB: `1024.0`

## Public Scope

Aggregate Benchmark v2 execution status snapshot. Raw execution ledgers, local caches, and prediction bundles are not included in the public package.
