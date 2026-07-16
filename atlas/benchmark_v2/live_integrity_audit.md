# Benchmark v2 Live Integrity Audit

This page reports aggregate integrity checks over the live Benchmark v2 ledgers. It is a contract audit, not a result interpretation.

## Snapshot

- Status: `pass`
- Critical violations: `0`
- Warnings: `0`
- Planned method rows: `42000`
- Observed method rows: `24974`
- Completed method rows: `15802`
- Pending method rows: `17026`
- Fully terminal paired cells: `4973`
- Partially observed paired cells: `37`

## Contract Checks

| Check | Count |
|---|---:|
| Duplicate planned method-row keys | 0 |
| Out-of-plan latest method rows | 0 |
| Latest failed method rows | 0 |
| Completed core-field violations | 0 |
| Benchmark v2 config violations | 0 |
| Plus-family metadata violations | 0 |
| Model-matched CQR metadata violations | 0 |

## Status Counts

| Status | Rows |
|---|---:|
| `completed` | 15802 |
| `skipped_infeasible_grouped_regime` | 5250 |
| `skipped_method` | 3922 |

## Public Scope

Aggregate Benchmark v2 live integrity audit snapshot. It reports contract-check counts only; raw execution ledgers, prediction bundles, and row-level examples remain outside the public package.
