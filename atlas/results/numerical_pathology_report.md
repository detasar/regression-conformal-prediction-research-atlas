# Numerical Pathology Report

This report is derived from `atlas/results/result_cube_public.csv`. It does not add new experiment results; it records finite-domain display checks for the public aggregate result surface.

## Summary

| Quantity | Value |
|---|---:|
| Result rows checked | 641 |
| Flagged rows | 29 |
| Coverage diagnostic bands clipped for display | 23 |
| Raw coverage upper bounds above 1 | 23 |
| Raw coverage lower bounds below 0 | 0 |
| Extreme width or interval-score rows | 6 |

Raw diagnostic-band bounds are kept in the CSV/JSON. The clipped fields are display-only probability-domain values for plots and tables.

## Reason Counts

| Reason | Rows |
|---|---:|
| coverage_ci_high_above_1 | 23 |
| none | 612 |
| width_mean_abs_gt_1e+12;interval_score_mean_abs_gt_1e+12 | 6 |

## Display Policy Counts

| Policy | Rows |
|---|---:|
| display_raw_value | 612 |
| display_raw_value_with_pathology_flag | 29 |

## Finite-Domain Status Counts

| Status | Rows |
|---|---:|
| coverage_ci_raw_outside_probability_domain | 23 |
| coverage_ci_within_probability_domain | 618 |
