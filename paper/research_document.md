# Research Document

## Regression Conformal Prediction Under Neutral Interpretation Scope

Author: Emre Tasar, Data Scientist
Contact: detasar@gmail.com

## Abstract

This Research Document reports a neutral empirical study of regression conformal prediction. The study aggregates 145,839 publication-scoped completed rows across 67 datasets, 95 dataset-alpha cells, and 28 conformal-method labels. The document focuses on what the audited experiment observed, what the evidence supports, and which broader readings would require separate validation.

Within this retrospective and imbalanced experiment surface, the fixed-GBM CQR pipeline was selected most often under the coverage-gated interval-score rule; Mondrian calibration and CV+ were secondary practical candidates. CQR has the largest current coverage-gated selected-cell count (56 cells), while CV+ contributes 13 coverage-gated selected cells. The evaluated backend-confound check completed 4,564 model-matched CQR rows and compared 224 paired dataset-alpha-model-family cells; it is reported as backend-sensitivity evidence. The evaluated Venn-Abers regression bridge did not behave as the expected strong regression solution: it produced 14 undercoverage runs and a low quantile-coverage mean in the current diagnostic bridge. These statements are descriptive and tied to the audited experiment.

Read this document in four layers. First, identify the empirical object that was audited. Second, separate observed practical-candidate patterns from deployment rules. Third, keep negative Venn-Abers bridge evidence separate from the broader Venn-Abers literature. Fourth, use the package, KG, and site as traceability surfaces for inspecting how claims connect to evidence.

| Reading layer | Reader question | Safe reading | Scope |
|---|---|---|---|
| Empirical object | What was actually measured? | A publication-scoped regression conformal prediction audit over completed dataset-alpha-method result rows. | The scope is an audited experiment surface rather than exhaustive internet coverage, a product benchmark, or deployment evidence. |
| Observed pattern | Which methods looked practically useful here? | Within this retrospective and imbalanced experiment surface, the fixed-GBM CQR pipeline was selected most often under the coverage-gated interval-score rule; Mondrian calibration and CV+ were secondary practical candidates. | Universal method selection and deployment use would require a separate validation protocol. |
| Negative evidence | What happened to the Venn-Abers regression bridge? | The evaluated bridge did not emerge as the expected strong regression interval solution in this experiment. | The bridge-specific result should be read separately from predictive-distribution and generalized Venn-Abers research. |
| Traceability | How should the package, KG, and site be treated? | They are Research Atlas surfaces for tracing claims to evidence, citations, and study scope. | The KG is a navigation and traceability layer for source inspection. |

## Executive Synthesis

This synthesis states the document's position before the detailed tables. It is written for a reviewer who needs to understand the scientific result, the negative evidence, and the study scope without first reading every audit artifact.

### What this document is

This Research Document is an evidence-linked synthesis of a regression conformal prediction audit. It summarizes 145,839 completed rows across 67 datasets, 95 dataset-alpha cells, and 28 conformal-method labels. The unit of evidence is therefore an audited result surface, not a single showcase run.

Boundary: The study identity describes the audited experiment surface rather than exhaustive internet coverage or deployment validation.

### What the evidence supports

The central supported wording is deliberately narrow: Within this retrospective and imbalanced experiment surface, the fixed-GBM CQR pipeline was selected most often under the coverage-gated interval-score rule; Mondrian calibration and CV+ were secondary practical candidates. CQR has 56 descriptive coverage-gated selected cells, and CV+ has 13. These counts support a practical-candidate reading within the audited experiment.

Boundary: Universal best-method and deployment readings require separate validation.

### What the CQR backend check adds

The completed backend-confound check adds a model-matched CQR rerun rather than a new method-selection claim. It completed 4,564 model-matched CQR rows and paired 224 dataset-alpha-model-family cells against the historical fixed-GBM CQR pipeline. Coverage-eligible interval-score selections were fixed-GBM CQR=116, model-matched CQR=71, and neither=37.

Boundary: The check keeps CQR as an experiment-scoped practical signal; method selection or deployment use would require separate validation.

### Which broader readings require separate validation

The evaluated Venn-Abers regression bridge did not become the expected strong interval solution in this experiment. The bridge has 14 undercoverage runs, a quantile-coverage mean of 0.6503, and validated-regression support flag `False`.

Scope: This bridge-specific negative evidence should be read separately from predictive-distribution and generalized Venn-Abers research.

### Which claims remain beyond this study

Several broader readings require evidence that was not produced in this study. The current record contains 0 bounded-support-validity-ready bundles and 0 population-group-inference-ready bundles. These zeros are not gaps to hide; they are part of the scientific result.

Boundary: Endpoint-validity, group-inference, and deployment readings require separate validation.

### How a reviewer should inspect it

The review path is intentionally traceable. The Research Atlas package and KG connect the Research Document to source artifacts, scripts, interpretation boundaries, and citation boundaries. The current KG has 3,643 nodes, 21,019 edges, 0 isolated nodes, and edge selector provenance coverage 1.0000.

Boundary: The KG supports navigation and traceability; scientific claims remain anchored in the underlying evidence.

## Plain-Language Summary

This section gives the shortest reader-safe interpretation before the technical tables. It is written for a reader who may not know conformal prediction. Each answer is paired with the evidence that supports it and the stronger reading that remains beyond this study.

| Reader question | Plain-language answer | Evidence anchor | Boundary |
|---|---|---|---|
| What is the shortest correct reading of the study? | This is an audited measurement record for regression conformal prediction. | 145,839 completed rows across 67 datasets, 95 dataset-alpha cells, and 28 method labels. | The study is an audited experiment surface rather than exhaustive internet coverage, a product benchmark, or deployment advice. |
| What does the CQR/CV+ finding mean? | The fixed-GBM CQR pipeline, Mondrian calibration, and CV+ looked practically useful within this experiment, with CQR carried the largest coverage-gated selected-cell signal and a completed backend-sensitivity check. | CQR has 56 coverage-gated selected cells and CV+ has 13 coverage-gated selected cells; the model-matched CQR rerun completed 4,564 rows and 224 paired cells. | Final method selection, universal best-method statements, and deployment use require separate validation. |
| What does `1 - alpha` mean here? | `1 - alpha` is the target coverage level; observed coverage still has to be measured in the audited cells. | The document reports coverage means, coverage lower-bound pass rates, coverage-gated selected cells, and undercoverage runs after the target is fixed. | Every-dataset, endpoint, and subgroup coverage require observed evidence beyond the nominal target. |
| How should the Venn-Abers bridge result be read? | The evaluated regression bridge produced negative failure-mode evidence in this experiment. | 14 undercoverage runs, quantile-coverage mean 0.6503, and validated-regression support flag `False`. | The bridge-specific result should be read separately from predictive-distribution and generalized Venn-Abers research. |
| Why keep the KG and Research Atlas package in the review path? | They let a reviewer trace claims to reports, scripts, citations, quality checks, and interpretation scope. | 3,643 KG nodes, 21,019 edges, 0 isolated nodes, and edge selector provenance coverage 1.0000. | Use the KG and site to inspect how claims connect to evidence. |

## Research Questions And Answers

The table below gives the reader a compact map of the study's research questions, the answer currently supported by the evidence, the artifact family that supports the answer, and the stronger interpretation that remains beyond this study. It is a writing and review map, not a new experiment.

| Research question | Evidence-supported answer | Evidence anchor | Stronger reading requiring validation |
|---|---|---|---|
| What empirical object does this Research Document evaluate? | It evaluates a publication-scoped regression conformal prediction audit over 145,839 completed rows, 67 datasets, 95 dataset-alpha cells, and 28 method labels. | Experimental scope table, individual experiment report facts, completed-row accounting, and dataset/source audit lineage. | The scope is an audited experiment surface rather than exhaustive internet coverage or deployment generality. |
| Which conformal approaches looked practically useful in the audited experiments? | Within this retrospective and imbalanced experiment surface, the fixed-GBM CQR pipeline was selected most often under the coverage-gated interval-score rule; Mondrian calibration and CV+ were secondary practical candidates; CQR has 56 descriptive coverage-gated selected cells and CV+ has 13. | Observed method behavior table, result reading guide, row-weighted coverage summaries, and robustness diagnostics. | Selected-method, best-method, and deployment-rule readings require separate validation. |
| Was the observed CQR signal robust to matching the CQR backend to the model-family sweep? | The backend sensitivity check completed 4,564 model-matched CQR rows and compared 224 paired dataset-alpha-model-family cells. Selected cells were fixed-GBM CQR=116, model-matched CQR=71, and neither=37. | CQR fixed-vs-model-matched synthesis, rerun manifest, article backend-sensitivity section, and supplement S1b. | The check is backend-sensitivity evidence for the CQR pipeline signal. |
| What was learned from the evaluated Venn-Abers regression bridge? | The evaluated bridge produced negative failure-mode evidence: 14 undercoverage runs, quantile-coverage mean 0.6503, and validated-regression support flag `False`. | Venn-Abers bridge diagnostics, undercoverage accounting, negative-evidence section, and Venn-Abers citation boundary. | The bridge result leaves predictive-distribution and generalized Venn-Abers research separate. |
| Which stronger scientific claims remain beyond this study? | Bounded-support validity and population-group-inference claims remain beyond this study, with 0 bounded-support-validity-ready bundles and 0 population-group-inference-ready bundles. | Paper gate map, bounded-support audit, group diagnostic scope, and publication claim/evidence matrix. | Positive bounded-support, endpoint-validity, and group-inference claims require separate validation. |
| How can a reviewer audit or navigate the evidence? | The Research Atlas KG and package provide a traceability surface with 3,643 KG nodes, 21,019 edges, 0 isolated nodes, and edge selector provenance coverage 1.0000. | Knowledge-graph quality audit, Research Atlas package manifest, README review router, and KG browser. | Use the KG and site to inspect how claims connect to evidence; cite the Research Atlas repository rather than the source repository. |

## Contribution And Finding Map

This map states the document's contribution and core empirical findings in a form that can be read before the technical sections. Each row includes the evidence anchor and the stronger reading that remains beyond this study.

| Contribution or finding | Reader-safe statement | Evidence anchor | Stronger reading requiring validation |
|---|---|---|---|
| Audited regression-CP experiment scope | The study reports a publication-scoped regression conformal prediction audit over 145,839 completed rows, 67 datasets, 95 dataset-alpha cells, and 28 method labels. | Individual experiment report facts, main article scope summary, and completed-row accounting. | The dataset scope is audited rather than exhaustive or deployment-general. |
| Practical candidate pattern | Within this retrospective and imbalanced experiment surface, the fixed-GBM CQR pipeline was selected most often under the coverage-gated interval-score rule; Mondrian calibration and CV+ were secondary practical candidates; CQR carried the largest coverage-gated selected-cell count (56) and CV+ contributed 13 coverage-gated selected cells. | Main article claim-evidence map, result reading guide, and supplementary robustness diagnostics. | Broader selection, superiority, and deployment readings require separate validation. |
| CQR backend sensitivity check | The completed model-matched CQR rerun tested whether the CQR signal was only a fixed-GBM pipeline artifact. It produced 4,564 model-matched CQR rows and 224 paired dataset-alpha-model-family cells. | Fixed-vs-model-matched CQR synthesis and model-matched CQR rerun manifest. | This check gives backend-sensitivity context for the CQR pipeline signal. |
| Venn-Abers bridge negative evidence | The evaluated Venn-Abers regression bridge produced negative failure-mode evidence, including 14 undercoverage runs and quantile-coverage mean 0.6503. | Bridge diagnostics, undercoverage accounting, and Venn-Abers citation boundary rows. | The broader predictive-distribution and generalized Venn-Abers literature remains separate. |
| Stronger claims requiring validation are part of the result | Bounded-support validity and population-group-inference stronger readings require separate validation, with 0 bounded-support-validity-ready bundles and 0 population-group-inference-ready bundles. | Paper gate map, publication claim/evidence matrix, bounded-support audit, and group diagnostic scope. | These gaps are reported as part of the scientific result. |
| Traceability and reproducibility surface | The knowledge graph is usable as a Research Atlas traceability surface with 3,643 nodes, 21,019 edges, 0 isolated nodes, and edge selector provenance coverage 1.0000. | Knowledge-graph quality audit and Research Atlas package manifest. | The KG supports navigation and traceability; scientific claims remain anchored in the underlying evidence. |
| Publication package architecture | The package separates a minimal main article, broad supplement, integrated Research Document, README review router, Research Atlas site, and evidence-scope checks. | Publication exemplar review, README, Research Atlas site manifest, and final-output scope protocol. | This row describes the Research Atlas architecture and its evidence-scope checks. |

## Scientific Method Audit Trail

This table rewrites the study as a scientific-method chain: question, measurement, comparison, falsification, stronger claims requiring validation, and reproducibility. It is included so a reader can see why the document reports both strong practical candidate patterns and negative or scope-limited conclusions.

| Stage | Reader question | Evidence anchor | Scientific boundary |
|---|---|---|---|
| Question and empirical object | What exactly is being measured before any method interpretation? | 145,839 publication-scoped rows, 67 datasets, 95 dataset-alpha cells, and 28 method labels. | Scope size is audit evidence, not proof of exhaustive internet coverage or deployment generality. |
| Measurement protocol | Which quantities turn model outputs into comparable evidence? | Coverage, width, coverage-gated selected cells, coverage lower-bound pass rates, and undercoverage runs are read within dataset-alpha-method cells. | Empirical metrics are not theorem-level guarantees and do not open conditional, endpoint, or subgroup claims. |
| Candidate-method comparison | Which practical patterns survived the audited comparison? | CQR has 56 coverage-gated selected cells and CV+ has 13; CQR row-weighted coverage mean is 0.9059. | This supports the wording 'observed as strong practical candidates in these experiments', an experiment-scoped practical-candidate reading. |
| CQR backend sensitivity control | Was the CQR signal only an artifact of the fixed-GBM CQR backend? | The model-matched CQR rerun completed 4,564 rows and formed 224 paired dataset-alpha-model-family cells. Coverage-eligible interval-score selected cells were fixed-GBM CQR=116, model-matched CQR=71, and neither=37. | The check supports a backend-sensitivity reading only; it does not open a CQR selection, CQR deployment rule, or universal method claim. |
| Falsification and negative evidence | Which attractive claims failed to close under the current evidence? | The evaluated Venn-Abers bridge has 14 undercoverage runs and validated-regression support flag `False`. | The negative result is bridge-specific and does not reject predictive-distribution or generalized Venn-Abers research. |
| Beyond this study stronger-claim checks | Which stronger conclusions must remain absent from the prose? | 0 bounded-support-validity-ready bundles and 0 population-group-inference-ready bundles. | A zero-ready gate is reported as a result; prose cannot convert it into bounded-support validity or population-level group inference. |
| Reproducibility and traceability | How can a reviewer trace the evidence? | 3,643 KG nodes, 21,019 KG edges, 0 isolated nodes, and edge selector provenance coverage 1.0000. | The KG and Research Atlas package are navigation and traceability infrastructure for this study. |

## Review Protocol

This table explains how to read the current evidence and which broader uses would require separate validation.

| Decision point | Reader-facing criterion | Evidence to check | Still requires validation |
|---|---|---|---|
| Reader-facing readability | The Research Document, main article, supplement, README, and Research Atlas site keep the empirical wording scoped and readable. | 6 of 6 reader-facing surfaces pass required phrase and boundary checks. | Reader-facing readability does not establish stronger scientific claims or deployment use. |
| Empirical result wording | CQR/CV+ are written only as strong practical candidates observed in these experiments. | CQR coverage-gated selected cells 56; CV+ coverage-gated selected cells 13; claim/evidence matrix status pass. | Final selected-method, best-method, deployment, and universal-superiority readings require separate validation. |
| CQR backend sensitivity wording | The model-matched CQR rerun is reported as a backend-confound diagnostic and as a backend-confound diagnostic. | Completed fixed-GBM rows 4,564; completed model-matched rows 4,564; paired cells 224; coverage-eligible interval-score selections fixed-GBM=116, model-matched=71, neither=37. | Method selection and deployment use require separate validation. |
| Venn-Abers negative evidence | The evaluated bridge is reported as bridge-specific negative or failure-mode evidence. | 14 undercoverage runs and validated-regression support flag `False`. | No validated Venn-Abers regression interval claim and no literature-wide rejection of Venn-Abers research. |
| Stronger scientific claims requiring validation | Bounded-support validity and population-group-inference claims are reported as beyond this study rather than softened into optimistic prose. | Bounded-support-validity-ready bundles 0; population-group-inference-ready bundles 0. | No bounded-support validity, endpoint validity, population-level group inference, or deployment-group-inference conclusion. |
| KG and site publication | The KG and Research Atlas site are useful for review navigation and claim tracing. | 3,643 KG nodes, 21,019 edges, 0 isolated nodes, and edge selector provenance coverage 1.0000. | The KG and GitHub Pages site are included as navigation and traceability surfaces. |

## 1. Reader Primer

Regression conformal prediction wraps a regression model with a prediction interval calibrated to a target coverage level. The usual notation is `1 - alpha`, where `alpha` is the target miscoverage rate [@lei2017distribution_free_regression]. Split conformal regression uses a calibration set to estimate a score quantile. Conformalized quantile regression, or CQR, instead starts from lower and upper quantile models and then conformalizes the resulting interval [@romano2019conformalized_quantile_regression]. Jackknife+ and CV+ use leave-one-out or out-of-fold predictions to account for fitted-model variability [@barber2020jackknife_plus; @kim2020jackknife_after_bootstrap].

Venn-Abers methods belong to a related but distinct calibration family. The literature includes Venn-Abers predictive distributions and generalized formulations, not merely ordinary interval wrappers [@nouretdinov2018ivapd; @nouretdinov2024ivapd_applications; @vanderlaan2025generalized_venn_abers; @petej2026inductive_venn_abers_regressors]. For that reason, the present study does not claim to invalidate the Venn-Abers literature. It reports that the evaluated regression bridge did not validate as a strong interval solution in this experiment.

### Citation-Backed Concept Map

The concept map below links the plain-language idea, its literature basis, the experiment anchor in this study, and the reading that remains beyond this study. It is included so non-specialist readers can see which parts are conformal prediction background, which parts are empirical observations, and which parts are governance boundaries.

| Concept | Reader question | Literature basis | Experiment anchor | Stronger reading requiring validation |
|---|---|---|---|---|
| Regression conformal prediction | What kind of uncertainty statement is being audited? | Distribution-free predictive inference for regression motivates calibrated prediction intervals under stated assumptions. [@lei2017distribution_free_regression] | Coverage, width, interval score, and target `1 - alpha` are reported inside audited dataset-alpha-method cells. | Conditional, endpoint, subgroup, and deployment validity require separate validation. |
| `1 - alpha` and `alpha` | Is the nominal target the same as observed coverage? | `1 - alpha` is the target coverage level and `alpha` is the target miscoverage rate used by the calibration rule. [@lei2017distribution_free_regression; @romano2019conformalized_quantile_regression] | The experiment evaluates observed coverage and coverage lower-bound behavior after the target level is fixed. | Every-cell and subgroup coverage require observed evidence beyond the nominal target. |
| Calibration data and conformity scores | Where does the interval correction come from? | Conformal regression uses held-out calibration evidence to map model errors or scores into interval adjustments. [@lei2017distribution_free_regression] | Split, normalized, Mondrian, and related rows differ partly by how calibration scores are pooled or stratified. | Covariate shift, bounded support, and group-inference validity require separate analysis. |
| Conformalized Quantile Regression (CQR) | Why does CQR use two quantile models before calibration? | CQR starts from lower and upper quantile estimates and then conformalizes the interval using calibration residual evidence. [@romano2019conformalized_quantile_regression] | CQR has 56 descriptive coverage-gated selected cells and is written only as a strong practical candidate observed in these experiments. | Universal CQR best-method or deployment readings require separate validation. |
| CV+ and jackknife-style resampling | Why do CV+ rows use out-of-fold predictions? | Jackknife+ and related cross-validation conformal methods use resampling predictions to account for model-fitting variability. [@barber2020jackknife_plus; @kim2020jackknife_after_bootstrap] | CV+ has 13 descriptive coverage-gated selected cells and is written as a strong practical candidate observed in these experiments. | CV+ remains an experiment-scoped signal; resampling effects require context-specific validation. |
| Group and Mondrian diagnostics | Why are group-calibrated rows not group-inference claims? | Group or stratified calibration changes how calibration evidence is pooled; it is separate from a population-group-inference estimand. [@lei2017distribution_free_regression] | Mondrian absolute-residual calibration has 15 coverage-gated selected cells and 187 pairwise group comparisons are retained as diagnostics. | Population-level group inference requires a ready inference bundle. |
| Venn-Abers predictive distributions | Why is the Venn-Abers result described narrowly? | Venn-Abers predictive distributions and generalized Venn-Abers calibration are broader than the interval bridge evaluated here. [@nouretdinov2018ivapd; @nouretdinov2024ivapd_applications; @vanderlaan2025generalized_venn_abers; @petej2026inductive_venn_abers_regressors] | The evaluated bridge has 14 undercoverage runs and validated regression support flag `False`. | The bridge-specific negative evidence leaves predictive-distribution and generalized Venn-Abers research separate. |
| Interpretation boundaries and scope limits | Why does the document report stronger claims requiring validation as results? | The literature citations support method definitions; the release and interpretation boundaries are project evidence controls, not new theory. [@lei2017distribution_free_regression; @romano2019conformalized_quantile_regression] | Final method selection, bounded-support validity, population-level group inference, KG citation, and Research Atlas remain beyond this study. | Do not open a stronger scientific or unsupported scope-expansion claim by wording it more optimistically in prose. |

### Terminology Compass

The following table fixes the meaning of recurring terms before the results are interpreted. Each term is defined as it is used in this Research Document. The last column states the boundary that prevents a descriptive result from becoming a deployment rule.

| Term | Plain-language meaning | Role in this document | Boundary |
|---|---|---|---|
| `prediction interval` | A lower-to-upper range around a regression prediction. | The interval is the object whose empirical coverage and width are audited. | A useful interval in this study is not a production guarantee. |
| `coverage` | The fraction of held-out outcomes that fall inside the interval. | Coverage is reported as an empirical diagnostic by dataset, alpha, and method family. | Observed coverage is not treated as proof of universal validity. |
| `1 - alpha` | The target coverage level; alpha is the target miscoverage rate. | Dataset-alpha cells define the main calibration comparison unit. | Near-target behavior is reported within the audited scope only. |
| `calibration set` | Data reserved to tune interval size after the base model is fit. | Calibration is the mechanism that turns model errors into interval adjustments. | Calibration diagnostics do not establish deployment validity. |
| `CQR` | Conformalized Quantile Regression: quantile models plus conformal calibration. | CQR is reported as a strong practical candidate observed in these experiments. | General CQR best-method readings require separate validation. |
| `CV+` | A cross-validation-style conformal method using out-of-fold predictions. | CV+ is reported as a strong practical candidate observed in these experiments. | The document reports the observed experiment pattern. |
| `coverage-gated selected cell` | A dataset-alpha comparison where a method appears on the descriptive selected trade-off set. | Coverage-gated selected-cell counts summarize observed coverage/width trade-offs. | A coverage-gated selected-cell count is descriptive evidence for the audited result surface. |
| `Venn-Abers regression bridge` | The evaluated bridge from Venn-Abers-style calibration evidence to regression intervals. | It is reported as negative/failure-mode evidence in this study. | This does not invalidate the broader Venn-Abers literature. |

### How To Interpret `1 - alpha`

`1 - alpha` is the target coverage level, not an observed success rate. For example, if `alpha = 0.10`, the target coverage is 0.90. A conformal method can be judged against that target only after specifying the dataset, split policy, calibration method, and scoring rule. This Research Document therefore reports coverage, coverage lower-bound behavior, coverage-gated selection, and evidence limits as scoped empirical diagnostics rather than theorem claims [@lei2017distribution_free_regression; @romano2019conformalized_quantile_regression].

This distinction matters for non-specialist readers. A method can show attractive empirical coverage in this study and still remain inappropriate as a general deployment rule. Conversely, a failure mode for one evaluated bridge does not reject an entire research family. The document keeps both sides visible so the later article, supplement, and KG can cite exactly what was observed.

### Evidence Interpretation Ledger

The ledger below separates three layers that are easy to confuse: the conformal prediction theorem layer, the empirical audit layer, and the interpretation-boundary layer. It is a reader-safety device, not a new theorem and not a new experiment. The marginal coverage language follows the regression conformal prediction sources [@lei2017distribution_free_regression; @romano2019conformalized_quantile_regression], while the Venn-Abers row is bounded by the predictive-distribution and generalized-calibration sources [@nouretdinov2018ivapd; @nouretdinov2024ivapd_applications; @vanderlaan2025generalized_venn_abers; @petej2026inductive_venn_abers_regressors].

| Topic | Reader-safe statement | Required condition or evidence | Stronger reading requiring validation |
|---|---|---|---|
| Marginal conformal coverage | The conformal regression guarantee is a marginal coverage statement for future exchangeable draws, not a pointwise promise for every individual row. | Exchangeability, a fixed calibration protocol, and a stated `1 - alpha` target. | Conditional, subgroup, endpoint, and deployment coverage require separate validation. |
| Empirical coverage in this study | Observed coverage summarizes held-out behavior inside the audited dataset, split, method, and alpha scope. | Completed-row accounting, dataset-alpha cells, split policy, and result audits. | An empirical coverage mean is descriptive evidence, separate from theorem-level or deployment claims. |
| Conditional and group behavior | Group and Mondrian diagnostics can reveal heterogeneity, but they do not by themselves prove population-level group inference. | Group definitions, calibration sample sizes, pairwise comparisons, and the population-group-inference gate. | Population-level group inference requires a ready inference bundle. |
| Efficiency and coverage-gated selection evidence | Coverage-width coverage-gated selected-cell counts describe the observed trade-off surface among audited methods. | Coverage, width, interval-score, and robustness diagnostics under the same comparison policy. | Coverage-gated selection summarizes a descriptive trade-off surface. |
| Venn-Abers regression bridge | The negative result concerns the evaluated interval bridge, while Venn-Abers predictive-distribution and generalized calibration work remain separate literature objects. | Bridge implementation details, undercoverage diagnostics, and the Venn-Abers citation boundary. | The bridge failure mode is separate from the broader Venn-Abers literature. |

### Method Mechanics At A Glance

The table below explains how each method family creates or adjusts prediction intervals before the empirical results are read. It is intentionally operational: the goal is to show what changes the interval, and what this study is not allowed to claim from that mechanism.

| Method family | What it does | What the interval depends on | Study boundary |
|---|---|---|---|
| Split conformal regression | Fits a regression model, measures held-out calibration errors, and expands future predictions by a calibration quantile. | The split policy, the residual score, and the empirical score quantile tied to `1 - alpha`. | It is a baseline calibration mechanism, not a complete answer to heterogeneity or endpoint validity. |
| CQR | Fits lower and upper quantile models, then conformalizes the two-sided quantile interval with calibration scores. | Quantile-model quality, lower/upper quantile levels, calibration scores, and the target miscoverage rate. | Observed here as a strong practical candidate; universal regression-CP use would require separate validation. |
| CV+ / jackknife-style methods | Uses out-of-fold or leave-one-out predictions so interval construction reflects model-fitting variability. | Fold design, base-model stability, conformity scores, and the cross-validated aggregation rule. | Observed here as a strong practical candidate within the audited experiment. |
| Mondrian calibration | Calibrates scores within groups or strata rather than using a single pooled calibration quantile. | The grouping rule, group sample sizes, residual scores, and the same `1 - alpha` coverage target. | Useful as a diagnostic comparator; group diagnostics do not become population-level group inference claims. |
| Venn-Abers regression bridge | Maps Venn-Abers-style calibration evidence into interval-style regression diagnostics for this experiment. | The bridge design, its calibration object, and the diagnostic conversion into coverage/interval evidence. | The evaluated bridge produced negative evidence here; this does not reject the broader Venn-Abers literature. |

## Publication Design Basis

Before the Research Document, supplement, README, and site are treated as reviewable publication surfaces, their structure is checked against a small source-backed review of comparable conformal prediction papers, repositories, docs, and sites. This review contributes navigation and traceability decisions only. It does not add experiments and does not recommend a conformal method.

| Design decision | Project application |
|---|---|
| Use a minimal main article and a broad supplementary document. | The main article keeps the claim-evidence map and headline results; the supplement carries broad method, dataset, audit, robustness, and negative-evidence material. |
| Make the README a review router, not a dense methods dump. | The README starts with status, plain-language summary, review path, evidence snapshot, repository map, KG entry, and citation surface. |
| Use the site as a Research Atlas portal with explicit lanes. | The Research Atlas site should expose the handoff, Research Document, rendered article/supplement, KG browser, and governance checks. |
| Pair every reader-facing claim with evidence and a boundary. | The article, Research Document, and README retain neutral language: observed practical candidates are not deployment rules, and bridge-specific failures are not literature-wide rejections. |
| Give the Research Document a checklist-like transparency spine. | The Research Document should visibly cover claims, limitations, assumptions, reproducibility route, compute, license and source provenance, and beyond this study scope limits. |
| Expose reproduction structure while excluding raw data and secrets. | The Research Atlas package records source, configs, tests, reports, and metadata, while excluding raw data, caches, local databases, and secret-like material. |
| Treat the knowledge graph as a browsable supplementary/web artifact. | The KG browser is part of the evidence path when its quality and provenance checks pass. |
| Make result verification commands and expected outputs explicit. | The README should connect headline results to exact commands, manifest paths, and expected pass/fail statuses rather than relying on prose-only reproducibility claims. |
| Keep Venn-Abers wording bridge-specific and conservative. | The Research Document reports that the evaluated bridge did not emerge as the expected strong regression solution in these experiments. |
| Keep reader review and Research Atlas as separate states. | The Research Atlas package gives readers the article, supplement, KG browser, and reproducibility materials under the stated evidence scope. |

## 2. Experimental Scope

| Scope item | Value | Interpretation |
|---|---:|---|
| Publication-scoped completed rows | 145,839 | Audited empirical accounting scope |
| Datasets | 67 | Public regression dataset scope |
| Dataset-alpha cells | 95 | Calibration comparison cells |
| Conformal-method labels | 28 | Broad conformal method surface |
| Model-matched CQR completed rows | 4,564 | Backend-confound sensitivity check |
| CQR fixed-vs-model-matched paired cells | 224 | Dataset-alpha-model-family comparison cells |
| Supplement sections | 6 | Broad supplementary evidence plan |

The design emphasizes resumability, source traceability, duplicate and leakage controls, and conservative interpretation scope. The study therefore treats stronger claims requiring validation as part of the result rather than as missing decoration. If an endpoint, group inference, or validation gate does not close, the Research Document reports that gate as beyond this study against the stronger claim.

### Audit Controls

The publication-scoped accounting separates empirical observations from unsupported scope-expansion claims. The current source artifacts record 6 of 6 reader-facing surfaces passing their required phrase and boundary checks. Cross-run leakage status is `hard_leakage_not_detected_in_scanned_artifacts`, with 0 unsupported-claim hits in the scanned cross-run artifacts. These controls support the Research Atlas document; deployment use requires separate validation.

Duplicate handling is also reported as evidence rather than hidden. The supplement records 29 duplicate actions, 46 quarantined actions, and 0 unquarantined actions. The Research Document therefore keeps the interpretation conditional on the audited data-integrity state.

## 3. Observed Method Behavior

### Result Reading Guide

The result tables combine several diagnostic quantities. The guide below states how each quantity should be read before the method rows are interpreted. This prevents a descriptive metric from being mistaken for a final method selection, a group-inference claim, an endpoint-validity claim, or a Venn-Abers validation claim.

| Metric | Plain-language meaning | How to read it | Boundary |
|---|---|---|---|
| `row-weighted coverage mean` | Average empirical coverage after giving larger completed-result blocks proportionally more influence. | Use it as a broad descriptive coverage summary within the audited experiment scope. | It is not a theorem-level coverage guarantee and not a deployment claim. |
| `diagnostic row-weighted coverage band` | A quantified uncertainty band around the observed aggregate coverage estimate. | Use it to judge the precision of the descriptive aggregate, not only the point estimate. | It does not remove split, dataset, endpoint, or selection caveats. |
| `coverage-gated selected cell` | A dataset-alpha comparison where a method sits on the observed coverage-gated selected comparison set. | Use coverage-gated selected-cell counts as a compact map of practical trade-offs seen in the study. | A coverage-gated selected-cell count is descriptive evidence, not a final selection or general deployment rule. |
| `coverage lower-bound pass rate` | The share of comparison cells where empirical coverage is close to the target `1 - alpha` level. | Use it to separate approximate calibration behavior from raw coverage averages. | Coverage lower-bound behavior remains scoped to the audited cells. |
| `undercoverage run` | A run where empirical coverage falls below the target coverage level by the audit rule. | Use it as failure-mode evidence, especially for methods or bridges that do not close validation gates. | It is bridge- or run-specific evidence, not a rejection of a whole research literature. |
| `evidence limit` | An explicit record that the current evidence cannot support a stronger claim. | Use evidence limits as results: they identify which stronger readings require separate evidence. | Evidence limits can be revised only by later evidence and the published evidence scope, not by prose. |

### Evidence-To-Claim Interpretation Ladder

The ladder below connects each result type to the strongest claim it can support and the claim it still cannot support. It is the reader-facing bridge between the numeric tables and the neutral prose used in the Research Document.

| Evidence layer | What it can support | Evidence in this study | What it cannot support | Reader action |
|---|---|---|---|---|
| Nominal target | `1 - alpha` states the coverage target that a method is evaluated against. | 95 dataset-alpha cells define the main target/coverage comparison surface. | It cannot prove that every dataset, endpoint, or group achieved the nominal target. | Compare observed coverage and coverage-lower-bound rates after reading the target. |
| Observed aggregate coverage | Coverage means and diagnostic bands summarize empirical interval behavior inside the audited scope. | CQR row-weighted coverage mean is 0.9059; CV+ row-weighted coverage mean is 0.8997. | It cannot be rewritten as theorem-level conditional coverage or deployment validity. | Use coverage as one descriptive axis, not as a standalone deployment rule. |
| Coverage-width trade-off | Coverage-gated selected cells identify methods that looked practically efficient under the audited comparison policy. | CQR has 56 coverage-gated selected cells; CV+ has 13. | Coverage-gated selection evidence cannot be promoted to a universal best-method claim. | Read the fixed-GBM CQR pipeline as the largest selected-cell signal, with Mondrian and CV+ as secondary candidates in this experiment. |
| Robustness retention | Bootstrap and leave-one diagnostics test whether the practical candidate pattern is fragile. | Bootstrap selection counts are cqr=1,000; leave-one-dataset and leave-one-alpha retention rates are 1.0000 and 1.0000. | Robustness retention cannot open final method selection or deployment guidance gates. | Use robustness as support for cautious wording, not for a final selection sentence. |
| CQR backend sensitivity | The model-matched rerun tests whether the fixed-GBM CQR signal was only a backend artifact. | 4,564 model-matched CQR rows, 224 paired cells, selected cells fixed-GBM CQR=116, model-matched CQR=71, neither=37. | It cannot promote CQR from experiment-scoped practical signal to universal method-selection or deployment guidance. | Read the check as backend-confound evidence and keep the final claim descriptive. |
| Negative bridge evidence | Undercoverage and a unvalidated-regression flag support a narrow failure-mode reading for the evaluated bridge. | The evaluated Venn-Abers bridge has 14 undercoverage runs and validated-regression support flag `False`. | It cannot reject predictive-distribution or generalized Venn-Abers research. | Report the bridge result as negative evidence exactly at the evaluated bridge scope. |
| Evidence limits | Evidence limits identify claims that the current evidence is not allowed to make. | Bounded-support-validity-ready bundles 0; population-group-inference-ready bundles 0; KG citable component in scope `False`. | Evidence limits cannot be reopened by optimistic prose, README wording, or site polish. | Treat evidence limits as scientific results and study scope. |

### Claim Language Guardrails

The rows below are writing controls derived from the claim/evidence verification matrix. They are not final report text. They state the safe sentence currently allowed, the source or citation gate that must stay attached to it, the overclaim that remains beyond this study, and the plain-language reason a non-specialist reader should not read more into the evidence than the study can support.

| Target | Claim type | Allowed sentence | Source/citation gate | Stronger reading requiring validation | Plain-language note |
|---|---|---|---|---|---|
| `main_article` | `scope_claim` | The dataset/source audit defines the studied scope under the recorded review policy. | Dataset/source descriptions need source citations before final report text; the matrix does not certify exhaustive internet coverage. | The dataset/source audit is a scoped study surface rather than exhaustive internet coverage or final dataset-level result promotion. | This row tells a reader what data sources were inspected; the dataset list defines study scope rather than a final dataset-level result. |
| `main_article` | `descriptive_empirical_claim` | Within this retrospective and imbalanced experiment surface, the fixed-GBM CQR pipeline was selected most often under the coverage-gated interval-score rule; Mondrian calibration and CV+ were secondary practical candidates. | Method descriptions need literature citations; empirical language must stay limited to these experiments. | Method behavior is reported as experiment-scoped evidence rather than deployment guidance. | This row permits a careful description of what looked useful in the experiment; deployment rules for new regression problems require separate validation. |
| `main_article` | `stronger_reading_requiring_validation` | The current evidence does not establish a final method selection, final main result, or deployment rule. | This reading would require a separate pre-specified validation protocol. | Keep method-selection conclusions beyond this study. | This row prevents a reader from mistaking promising diagnostic patterns for a final answer. |
| `supplementary_document` | `caveated_diagnostic_claim` | Robustness rows are post-selection diagnostics and should be read with their multiplicity caveats. | Statistical or robustness interpretations need the documented audit context; they are not confirmatory superiority claims. | Robustness diagnostics are descriptive rather than confirmatory superiority evidence. | This row says the extra checks are useful diagnostics, not proof that one method is definitively preferred. |
| `supplementary_document` | `negative_failure_mode_claim` | In these experiments, the evaluated fast Venn-Abers regression bridge did not validate as the expected strong regression interval solution. | The claim is bridge-specific negative evidence and leaves the broader Venn-Abers literature separate. | Validated Venn-Abers regression interval support would require separate evidence. | This row records that one tested bridge behaved poorly while the broader Venn-Abers literature remains separate. |
| `supplementary_document` | `methodology_record_claim` | The study includes audit controls for traceability, neutrality, and reproducibility. | Control descriptions support reproducibility claims; scientific validity rests on the empirical evidence. | Treat controls as traceability evidence, not validity proof. | This row explains the guardrails around the study rather than claiming the guardrails make every result final. |
| `supplementary_document` | `reproducibility_traceability_claim` | The Research Atlas package records completed-row accounting, resume-safety controls, and knowledge-graph traceability. | Use the public Research Atlas repository as the citable artifact for this study. | Cite the public Research Atlas repository for this study. | This row tells a reader how the work can be audited and resumed while keeping the source provenance separate from the public Research Atlas. |
| `individual_experiment_report` | `authoring_blueprint_claim` | The individual report blueprint records the author-stamped section map for later review. | This is an authoring map for the individual experiment report. | Keep the individual-report blueprint separate from generated publication outputs. | This row preserves the report plan and author metadata for traceable review. |

| Method family | Key observed evidence | In scope interpretation |
|---|---:|---|
| CQR | 56 descriptive coverage-gated selected cells; row-weighted coverage mean 0.9059 | Strong practical candidate observed in this experiment |
| Model-matched CQR check | 4,564 completed model-matched rows; 224 paired cells; selected cells fixed-GBM=116, model-matched=71, neither=37 | Backend sensitivity evidence; no method-selection claim |
| CV+ | 13 descriptive coverage-gated selected cells; row-weighted coverage mean 0.8997 | Strong practical candidate observed in this experiment |
| Mondrian absolute-residual calibration | 15 descriptive coverage-gated selected cells; row-weighted coverage mean 0.9073 | Useful diagnostic comparator |
| Venn-Abers regression bridge | 14 undercoverage runs; quantile-coverage mean 0.6503 | Negative/failure-mode evidence for the evaluated bridge |

Robustness diagnostics are aligned with that descriptive reading. The common-cell selected method is `cqr`; common-cell counts are CQR=58, CV+=15, and Mondrian=21. Bootstrap selection counts are cqr=1,000. Leave-one-dataset and leave-one-alpha retention rates are 1.0000 and 1.0000. These numbers support a practical-candidate description; they do not establish final selection language.

Coverage summaries provide additional context. CQR has nominal and coverage lower-bound pass rates of 0.6118 and 0.8076; CV+ has coverage lower-bound pass rate 0.8136; Mondrian absolute-residual calibration has coverage lower-bound pass rate 0.8586. The document reports these values as diagnostics at the audited scope.

## 4. Negative And Beyond this study Claims

The Research Document keeps three high-risk claims beyond this study. First, bounded-support validity is not supported: 0 bundles are validity-ready, despite 15 bounded-support bundles and 11 raw endpoint-excursion bundles being recorded. Second, population-level group inference is not supported: 0 bundles are population-group-inference-ready, even though 15 group inference bundles and 187 pairwise group comparisons are available as diagnostics. Third, the evaluated Venn-Abers bridge is reported as negative evidence rather than as a validated regression solution.

The Venn-Abers result is intentionally narrow. The evaluated bridge has quantile-coverage mean 0.6503, coverage lower-bound pass rate 0.0337, and validated-regression support flag `False`. This does not reject Venn-Abers research. It only records that the current regression interval bridge did not close the validation gate in this experiment.

## 5. Knowledge Graph And Reproducibility

The current knowledge graph has 3,643 nodes, 21,019 edges, and 0 isolated nodes. Average edge confidence is 0.9917, and edge selector provenance coverage is 1.0000. In the Research Atlas package, the KG browser exposes 3,643 nodes, 21,019 edges, 39 node types, and 58 relation types. The browser is intended to let reviewers move from claims to source reports, tables, scripts, and quality gates. It belongs to the Research Atlas navigation and traceability surface.

## 6. How To Read The Artifact Set

The review order is deliberately simple. Read this Research Document first, then inspect the rendered main article and broad supplement, then use the individual experiment report for the author-stamped experiment summary. The KG browser should be used when a reader wants to trace a claim to reports, source artifacts, scripts, or quality gates. Governance files should be checked before any publication decision because they encode the stronger claims requiring validation.

| Artifact | Role | Study scope |
|---|---|---|
| `Research Document/research_document.md` | Integrated Research Atlas narrative | Descriptive, experiment-scoped interpretation |
| `rendered_outputs/main_article_review.html` | Main article surface | Conservative scientific wording |
| `rendered_outputs/supplementary_document_review.html` | Broad supplementary surface | Methods, diagnostics, and estimator conventions |
| `site/kg_browser.html` | Browsable KG surface | Navigation and traceability, not a standalone claim |
| `governance/publication_authoring_decision_record.md` | Decision scope record | Scientific interpretation scope and evidence scope |

## 7. Publication Scope

This document is intentionally strict about which broader readings require separate validation:

- This Research Document is a Research Atlas narrative for experiment-scoped interpretation.
- CQR/CV+ are described as strong practical candidates observed in this experiment.
- The model-matched CQR rerun is reported as backend-sensitivity evidence.
- The evaluated Venn-Abers regression bridge is described as negative/failure-mode evidence.
- Positive group inference, bounded-support validity, validated Venn-Abers regression, production, and best-method claims remain beyond this study.
- The KG is a browsable supplementary traceability layer for source inspection.
- No new experiments are established or required for this document.
- Publication-package design examples are used only to improve navigation and source traceability.

## References

- `@barber2020jackknife_plus`: https://arxiv.org/abs/1905.02928
- `@kim2020jackknife_after_bootstrap`: https://arxiv.org/abs/2002.09025
- `@lei2017distribution_free_regression`: https://arxiv.org/abs/1604.04173
- `@nouretdinov2018ivapd`: https://proceedings.mlr.press/v91/nouretdinov18a.html
- `@nouretdinov2024ivapd_applications`: https://proceedings.mlr.press/v230/nouretdinov24a.html
- `@petej2026inductive_venn_abers_regressors`: https://arxiv.org/html/2605.06646v1
- `@romano2019conformalized_quantile_regression`: https://arxiv.org/abs/1905.03222
- `@vanderlaan2025generalized_venn_abers`: https://proceedings.mlr.press/v267/van-der-laan25a.html

## Source Artifacts

- `publication_authoring_decision_record`: `experiments/regression/Research Document/publication_authoring_decision_record.json`
- `main_article_source`: `experiments/regression/Research Document/main_article_source.json`
- `supplement_source`: `experiments/regression/Research Document/supplement_source.json`
- `individual_experiment_report_source`: `experiments/regression/Research Document/individual_experiment_report_source.json`
- `claim_evidence_verification_matrix`: `experiments/regression/Research Document/claim_evidence_verification_matrix.json`
- `publication_citation_registry`: `experiments/regression/Research Document/publication_citation_registry.json`
- `knowledge_graph_quality_summary`: `experiments/regression/reports/knowledge_graph_quality/quality_summary.json`
- `research_atlas_package_manifest`: `experiments/regression/Research Document/research_atlas_package_manifest.json`
- `publication_exemplar_review`: `experiments/regression/Research Document/publication_exemplar_review.json`
- `cqr_fixed_vs_model_matched_synthesis`: `experiments/regression/reports/model_matched_cqr_rerun_plan/cqr_fixed_vs_model_matched_synthesis.json`
