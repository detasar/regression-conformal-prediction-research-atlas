# Individual Experiment Report

Author: Emre Tasar, Data Scientist
Contact: detasar@gmail.com

## Executive Summary

This regression conformal prediction study evaluated a broad set of audited experiment rows: 145,839 publication-scoped completed rows after accounting controls. The method synthesis covers 67 datasets, 95 dataset-alpha cells, 5 alpha levels, 28 conformal-method labels, and 148 source reports.

The main empirical pattern is descriptive: CQR has the largest current coverage-gated selected-cell share in the audited synthesis, but the final-selection claim remains outside current evidence. CQR appears on 56 coverage-gated selected cells, compared with 15 for Mondrian absolute-residual calibration and 13 for CV+. The robustness audit also retains CQR under common-cell, leave-one-dataset, leave-one-alpha, and bootstrap views; this is diagnostic robustness evidence, not a final method-selection claim.

The Venn-Abers regression bridge is not validated as an interval method in the current evidence. The negative disposition audit records 14 undercoverage runs, and the grid failure decomposition reports 6,001 scored grid-reference rows with an upper-boundary hit pattern. This supports reporting Venn-Abers as negative/failure-mode evidence for this bridge.

## Reader Primer

Conformal prediction is a wrapper for producing prediction sets or intervals with finite-sample marginal coverage under exchangeability. In regression, a prediction interval is intended to contain the next response value with target coverage `1 - alpha` [@lei2017distribution_free_regression]. `alpha` is the target miscoverage rate, so `alpha = 0.1` corresponds to nominal 90% coverage. Nominal coverage is the target; empirical coverage is what the experiment actually observed.

Split conformal regression calibrates residuals on a held-out calibration split. CQR changes the score: it first fits lower and upper quantile functions, then applies a conformal correction so interval width can adapt to heteroscedasticity [@romano2019conformalized_quantile_regression]. CV+ and jackknife+ use out-of-fold or leave-one-out predictions to account for fitted-model variability [@barber2020jackknife_plus; @kim2020jackknife_after_bootstrap].

Venn-Abers methods are related but not identical to ordinary split interval conformal regression. The cited Venn-Abers regression and calibration literature focuses on predictive distributions, auto-calibration, generalized calibration, and regression-related extensions [@nouretdinov2018ivapd; @nouretdinov2024ivapd_applications; @vanderlaan2025generalized_venn_abers; @petej2026inductive_venn_abers_regressors]. Therefore, converting a Venn-Abers object into the same interval contract used by CQR or CV+ is an extra design decision, not a free positive validation.

## Empirical Scope

| Quantity | Value | Source |
|---|---:|---|
| Canonical completed rows | 156,233 | `experiment_accounting_audit.json` |
| Publication-scoped completed rows | 145,839 | `experiment_accounting_audit.json` |
| Datasets in method synthesis | 67 | `method_performance_synthesis.json` |
| Dataset-alpha cells | 95 | `method_performance_synthesis.json` |
| Alpha levels | 5 | `method_performance_synthesis.json` |
| Conformal method labels | 28 | `method_performance_synthesis.json` |
| Broad-support methods | 11 | `method_performance_synthesis.json` |

## Method Findings

| Method | Coverage-gated selected cells | Row-weighted coverage mean | Row-weighted nominal hit rate | Row-weighted coverage lower-bound pass rate | Claim status |
|---|---:|---:|---:|---:|---|
| CQR | 56 | 0.9059 | 0.6118 | 0.8076 | descriptive diagnostic only |
| Mondrian absolute residual | 15 | 0.9073 | 0.6839 | 0.8586 | descriptive diagnostic only |
| CV+ | 13 | 0.8997 | 0.6038 | 0.8136 | descriptive diagnostic only |

### CQR Backend Sensitivity Check

After the broad method synthesis, a model-matched CQR rerun checked whether the historical fixed-GBM CQR pipeline was driving the CQR signal. This is a backend-confound diagnostic, not a new deployment guidance.

| Quantity | Value | Interpretation |
|---|---:|---|
| Fixed-GBM CQR completed rows | 4,564 | Historical CQR comparator rows |
| Model-matched CQR completed rows | 4,564 | Completed backend-matched rerun rows |
| Paired dataset-alpha-model-family cells | 224 | Direct fixed-vs-matched comparison cells |
| Fixed-GBM CQR selected cells | 116 | Coverage-eligible lower interval-score cells |
| Model-matched CQR selected cells | 71 | Coverage-eligible lower interval-score cells |
| Neither coverage-eligible variant | 37 | Cells where both CQR variants fail the coverage-eligibility rule |

For CQR, the row-weighted coverage mean is 0.9059, with a diagnostic row-weighted band from 0.9050 to 0.9068. The row-weighted absolute coverage error mean is 0.0210. These values support a descriptive statement that CQR has the largest current coverage-gated selected-cell share in this study; they do not support a general deployment rule that all regression conformal prediction users should choose CQR.

## Selection Robustness Diagnostics

| Diagnostic | Result | Source |
|---|---:|---|
| Common-cell selected method | `cqr` | `method_selection_robustness_audit.json` |
| Common-cell CQR selected diagnostic cells | 58 | `method_selection_robustness_audit.json` |
| Common-cell CV+ selected diagnostic cells | 15 | `method_selection_robustness_audit.json` |
| Common-cell Mondrian selected diagnostic cells | 21 | `method_selection_robustness_audit.json` |
| Bootstrap CQR selections | 1,000 | `method_selection_robustness_audit.json` |
| Leave-one-dataset CQR retention rate | 1.0000 | `method_selection_robustness_audit.json` |
| Leave-one-alpha CQR retention rate | 1.0000 | `method_selection_robustness_audit.json` |
| Final-selection claim status | `outside current evidence` | `method_selection_robustness_audit.json` |

The robustness diagnostics point in the same direction as the coverage-gated selected-cell table: CQR is stable under the current diagnostic protocol. The correct interpretation is still cautious. The audit explicitly keeps the final-selection claim outside current evidence.

## Negative And Outside current evidence Claims

| Claim area | Observed evidence | Current claim state |
|---|---|---|
| Venn-Abers bridge | 14 undercoverage runs; quantile bridge coverage mean 0.6503; max run grid upper-hit rate 0.1803 | negative/failure-mode evidence, no validated regression interval claim |
| Bounded support | 11 raw endpoint-excursion bundles; 0 validity-ready bundles | no bounded-support validity claim |
| Group inference | 15 diagnostic group bundles; 0 population-group-inference-ready bundles | group diagnostics only, no population-level group inference claim |
| Positive method selection | 0 positive-claim-ready gates | outside current evidence |

## Traceability And Release State

The current knowledge graph snapshot contains 3,643 nodes and 21,019 edges, with 0 isolated nodes and 0 quality issues in the latest quality summary. The graph is evidence infrastructure for navigating the experiment; it is not yet the final citable public artifact.

The release register records 0 in scope release rows. The goal-completion audit says `can_mark_goal_complete = false`. The next publication work should therefore stay in draft/reporting mode until the sterile repository, final article/supplement outputs, and release review are completed.

## Evidence Sources

- `experiment_accounting_audit`: `experiments/regression/reports/methodology_sanity_audit_20260627/experiment_accounting_audit.json`
- `method_performance_synthesis`: `experiments/regression/reports/methodology_sanity_audit_20260627/method_performance_synthesis.json`
- `cqr_fixed_vs_model_matched_synthesis`: `experiments/regression/reports/model_matched_cqr_rerun_plan/cqr_fixed_vs_model_matched_synthesis.json`
- `method_selection_robustness_audit`: `experiments/regression/reports/methodology_sanity_audit_20260627/method_selection_robustness_audit.json`
- `venn_abers_negative_evidence_disposition_audit`: `experiments/regression/reports/methodology_sanity_audit_20260627/venn_abers_negative_evidence_disposition_audit.json`
- `venn_abers_grid_failure_mode_decomposition`: `experiments/regression/reports/methodology_sanity_audit_20260627/venn_abers_grid_failure_mode_decomposition.json`
- `bounded_support_endpoint_closure_audit`: `experiments/regression/reports/methodology_sanity_audit_20260627/bounded_support_endpoint_closure_audit.json`
- `group inference_population_readiness_audit`: `experiments/regression/reports/methodology_sanity_audit_20260627/group inference_population_readiness_audit.json`
- `goal_completion_audit`: `experiments/regression/Research Document/goal_completion_audit.json`
- `publication_release_gap_register`: `experiments/regression/Research Document/publication_release_gap_register.json`
- `knowledge_graph_quality_summary`: `experiments/regression/reports/knowledge_graph_quality/quality_summary.json`
- `publication_citation_registry`: `experiments/regression/Research Document/publication_citation_registry.json`
- `reader_primer_section_alignment`: `experiments/regression/Research Document/reader_primer_section_alignment.json`

## References

- `@barber2020jackknife_plus`: https://arxiv.org/abs/1905.02928
- `@kim2020jackknife_after_bootstrap`: https://arxiv.org/abs/2002.09025
- `@lei2017distribution_free_regression`: https://arxiv.org/abs/1604.04173
- `@nouretdinov2018ivapd`: https://proceedings.mlr.press/v91/nouretdinov18a.html
- `@nouretdinov2024ivapd_applications`: https://proceedings.mlr.press/v230/nouretdinov24a.html
- `@petej2026inductive_venn_abers_regressors`: https://arxiv.org/html/2605.06646v1
- `@romano2019conformalized_quantile_regression`: https://arxiv.org/abs/1905.03222
- `@vanderlaan2025generalized_venn_abers`: https://proceedings.mlr.press/v267/van-der-laan25a.html
