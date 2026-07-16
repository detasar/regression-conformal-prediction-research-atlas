# Benchmark v2 Candidate Selection Rationale

- Status: `candidate_registries_published`
- Source candidates: `12`
- Task-variant candidates: `24`

## Selection Rules

1. Use at most two source datasets from any source family.
2. Keep task variants nested under source datasets rather than counted as independent datasets.
3. Prefer sources with existing audit profiles, clear target policies, and enough rows for paired wrapper comparisons.
4. Publish metadata gaps explicitly before execution rather than treating the candidate list as final source validation.

## Source Family Counts

| Source family | Candidate source count |
|---|---:|
| `aif360` | 1 |
| `college_scorecard` | 1 |
| `hmda` | 1 |
| `meps` | 1 |
| `nhanes` | 1 |
| `openml` | 2 |
| `pisa` | 1 |
| `scf` | 1 |
| `stackoverflow` | 1 |
| `uci` | 2 |

## Scope

These are candidate registries for Benchmark v2 planning; completed Benchmark v2 result rows are recorded separately.
