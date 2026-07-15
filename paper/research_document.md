# Research Document

## Regression Conformal Prediction: Evidence From an Audited Study

Author: Emre Tasar, Data Scientist
Contact: detasar@gmail.com

## Abstract

This Research Document reports a neutral empirical study of regression conformal prediction. The study aggregates 145,839 audited completed rows across 67 datasets, 95 dataset-alpha cells, and 28 conformal-method labels. The document focuses on what the audited experiment observed, what the evidence can support, and which broader readings require separate validation.

Under the current coverage criterion, the fixed-GBM CQR pipeline was most frequently selected; Mondrian calibration and CV+ were secondary candidates. CQR has the largest current descriptive coverage-gated selected-cell count (56 cells), while CV+ contributes 13 selected cells. The evaluated backend-confound check completed 4,564 model-matched CQR rows and compared 224 paired dataset-alpha-model-family cells; it documents backend sensitivity while leaving study-wide method choice unresolved. The evaluated Venn-Abers regression bridge did not behave as the expected strong regression solution: it produced 14 undercoverage runs and a low quantile-coverage mean in the current diagnostic bridge. These statements are descriptive and tied to the audited experiment.

Read this document in four layers. First, identify the empirical object that was audited. Second, separate observed practical-candidate patterns from deployment rules. Third, keep negative Venn-Abers bridge evidence separate from the broader Venn-Abers literature. Fourth, use the package, KG, and site as traceability surfaces for inspecting how claims connect to evidence.

| Reading layer | Reader question | Safe reading | Scope |
|---|---|---|---|
| Empirical object | What was actually measured? | An audited regression conformal prediction study over completed dataset-alpha-method result rows. | The scope is an audited experiment surface rather than exhaustive internet coverage, a product benchmark, or evidence for future deployments. |
| Observed pattern | Which methods looked practically useful here? | The fixed-GBM CQR pipeline had the largest selected-cell signal; Mondrian calibration and CV+ were secondary signals in this study. | Choosing a method for a new setting would require a prospective validation protocol. |
| Negative evidence | What happened to the Venn-Abers regression bridge? | The evaluated bridge did not emerge as the expected strong regression interval solution in this experiment. | The bridge-specific result should be read separately from predictive-distribution and generalized Venn-Abers research. |
| Traceability | How should the package, KG, and site be treated? | They are Research Atlas surfaces for tracing claims to evidence, citations, and study limits. | The KG lets readers follow claims to source artifacts and evidence tables. |

## Executive Synthesis

This synthesis states the document's position before the detailed tables. It is written for a reviewer who needs to understand the scientific result, the negative evidence, and the study scope without first reading every audit artifact.

### What this document is

This Research Document is an evidence-linked synthesis of a regression conformal prediction audit. It summarizes 145,839 completed rows across 67 datasets, 95 dataset-alpha cells, and 28 conformal-method labels. The unit of evidence is therefore an audited result surface, not a single showcase run.

Scope: The study identity describes the audited experiment surface rather than exhaustive internet coverage or validation for a future deployment.

### What the evidence supports

The central supported wording is deliberately narrow. The fixed-GBM CQR pipeline had the largest selected-cell signal, while Mondrian calibration and CV+ were secondary signals. CQR has 56 coverage-eligible selected cells, and CV+ has 13. These counts describe what happened inside the audited experiment.

Scope: A universal best-method statement or a new-setting deployment use would need its own validation plan.

### What the CQR backend check adds

The completed backend-confound check adds a model-matched CQR rerun to test how much the CQR signal depends on its backend model. It completed 4,564 model-matched CQR rows and paired 224 dataset-alpha-model-family cells against the historical fixed-GBM CQR pipeline. Coverage-eligible interval-score selections were fixed-GBM CQR=116, model-matched CQR=71, and neither=37.

Scope: The check keeps CQR as an experiment-scoped practical signal; choosing a method for a new setting would need a separate validation protocol.

### Which broader readings require separate validation

The evaluated Venn-Abers regression bridge did not become the expected strong interval solution in this experiment. The bridge has 14 undercoverage runs, a quantile-coverage mean of 0.6503, and validated-regression support flag `False`.

Scope: Avoid generalizing this bridge-specific negative evidence into a rejection of predictive-distribution or generalized Venn-Abers research.

### Which broader readings require separate validation

Several broader readings require evidence that was not produced in this study. The current record contains 0 bounded-support-validity-ready bundles and 0 population-inference-ready bundles. These zeros are not gaps to hide; they are part of the scientific result.

Scope: Endpoint-validity, group-inference, and deployment readings require separate validation.

### How a reviewer should inspect it

The review path is intentionally traceable. The Research Atlas package and KG connect the Research Document to source artifacts, scripts, claim scope limits, and citation scope limits. The current KG has 3,643 nodes, 21,019 edges, 0 isolated nodes, and manifest reference resolution rate 1.0000.

Scope: The KG supports evidence exploration; scientific claims remain anchored in the underlying evidence.

## Plain-Language Summary

This section gives the shortest reader-facing interpretation before the technical tables. It is written for a reader who may not know conformal prediction. Each answer is paired with the evidence that supports it and the stronger reading that requires separate validation.

| Reader question | Plain-language answer | Evidence anchor | Scope |
|---|---|---|---|
| What is the shortest correct reading of the study? | This is an audited measurement record for regression conformal prediction. | 145,839 completed rows across 67 datasets, 95 dataset-alpha cells, and 28 method labels. | The study is an audited experiment surface rather than exhaustive internet coverage, a product benchmark, or deployment advice. |
| What does the practical-candidate pattern mean? | The fixed-GBM CQR, Mondrian, and CV+ pattern looked practically useful in these experiments, with CQR carrying the largest descriptive coverage-gated selection signal and a completed backend-sensitivity check. | CQR has 56 coverage-gated selected cells and CV+ has 13 coverage-gated selected cells; the model-matched CQR rerun completed 4,564 rows and 224 paired cells. | Method choice, universal best-method statements, and deployment use require separate validation. |
| What does `1 - alpha` mean here? | `1 - alpha` is the target coverage level; observed coverage still has to be measured in the audited cells. | The document reports coverage means, coverage-tolerance pass rates, coverage-gated selected cells, and undercoverage runs after the target is fixed. | Every-dataset, endpoint, and subgroup coverage require observed evidence beyond the nominal target. |
| How should the Venn-Abers bridge result be read? | The evaluated regression bridge produced negative failure-mode evidence in this experiment. | 14 undercoverage runs, quantile-coverage mean 0.6503, and validated-regression support flag `False`. | The bridge-specific result should be read separately from predictive-distribution and generalized Venn-Abers research. |
| Why keep the KG and Research Atlas package in the review path? | They let a reviewer trace claims to reports, scripts, citations, quality checks, and interpretation scope. | 3,643 KG nodes, 21,019 edges, 0 isolated nodes, and manifest reference resolution rate 1.0000. | Use the KG and site to inspect how claims connect to evidence. |

## Research Questions And Answers

The table below gives the reader a compact map of the study's research questions, the answer currently supported by the evidence, the evidence family that supports the answer, and the stronger interpretation that requires separate validation. It is a writing and review map, not a new experiment.

| Research question | Evidence-supported answer | Evidence anchor | Scope limit |
|---|---|---|---|
| What empirical object does this Research Document evaluate? | It evaluates an audited regression conformal prediction audit over 145,839 completed rows, 67 datasets, 95 dataset-alpha cells, and 28 method labels. | Experimental scope table, individual experiment report facts, completed-row accounting, and dataset/source audit lineage. | Avoid reading the scope as exhaustive internet coverage or as deployment generality. |
| Which conformal approaches looked practically useful in the audited experiments? | Under the current coverage criterion, the fixed-GBM CQR pipeline was most frequently selected; Mondrian calibration and CV+ were secondary candidates. The comparison is experiment-scoped; using the pattern in a new setting would need its own validation plan; CQR has 56 descriptive coverage-gated selected cells and CV+ has 13. | Observed method behavior table, result reading guide, row-weighted coverage summaries, and robustness diagnostics. | Present CQR, CV+, and other methods as experiment-scoped patterns rather than method choices or general deployment rules. |
| Was the observed CQR signal robust to matching the CQR backend to the model-family sweep? | The backend sensitivity check completed 4,564 model-matched CQR rows and compared 224 paired dataset-alpha-model-family cells. Selected cells were fixed-GBM CQR=116, model-matched CQR=71, and neither=37. | CQR fixed-vs-model-matched synthesis, rerun manifest, article backend-sensitivity section, and supplement S1b. | Avoid reading the check as resolving a universal CQR selection claim. |
| What was learned from the evaluated Venn-Abers regression bridge? | The evaluated bridge produced negative failure-mode evidence: 14 undercoverage runs, quantile-coverage mean 0.6503, and validated-regression support flag `False`. | Venn-Abers bridge diagnostics, undercoverage accounting, negative-evidence section, and Venn-Abers citation scope. | Read this bridge result separately from predictive-distribution and generalized Venn-Abers research. |
| Which stronger scientific readings require separate validation? | Bounded-support validity and population-level group inference would require separate validation; the current record contains 0 bounded-support-validity-ready bundles and 0 population-inference-ready bundles. | Paper evidence map, bounded-support audit, group diagnostic scope, and publication claim/evidence matrix. | Diagnostic bounded-support, endpoint, and group rows should stay separate from validity or population-inference conclusions. |
| How can a reviewer audit or navigate the evidence? | The KG and Research Atlas package provide a traceability surface with 3,643 KG nodes, 21,019 edges, 0 isolated nodes, and manifest reference resolution rate 1.0000. | Knowledge-graph quality audit, Research Atlas package manifest, README review router, and KG browser. | Use the Research Atlas repository as the citation surface; source provenance is tracked separately. |

## Contribution And Finding Map

This map states the document's contribution and core empirical findings in a form that can be read before the technical sections. Each row includes the evidence anchor and the stronger reading that requires separate validation.

| Contribution or finding | Reader-facing statement | Evidence anchor | Scope limit |
|---|---|---|---|
| Audited regression-CP experiment scope | The study reports an audited regression conformal prediction audit over 145,839 completed rows, 67 datasets, 95 dataset-alpha cells, and 28 method labels. | Individual experiment report facts, main article scope summary, and completed-row accounting. | The dataset scope is audited rather than exhaustive or deployment-general. |
| Practical candidate pattern | Under the current coverage criterion, the fixed-GBM CQR pipeline was most frequently selected; Mondrian calibration and CV+ were secondary candidates. The comparison is experiment-scoped; using the pattern in a new setting would need its own validation plan, with CQR carrying the largest descriptive coverage-gated selected-cell count (56) and CV+ contributed 13 coverage-gated selected cells. | Main article claim-evidence map, result reading guide, and supplementary robustness diagnostics. | Broader selection, superiority, and deployment readings require separate validation. |
| CQR backend sensitivity check | The completed model-matched CQR rerun tested whether the CQR signal was only caused by the fixed-GBM pipeline. It produced 4,564 model-matched CQR rows and 224 paired dataset-alpha-model-family cells. | Fixed-vs-model-matched CQR synthesis and model-matched CQR rerun manifest. | This check is evidence about backend sensitivity. Universal CQR selection or deployment use would require a separate validation protocol. |
| Venn-Abers bridge negative evidence | The evaluated Venn-Abers regression bridge produced negative failure-mode evidence, including 14 undercoverage runs and quantile-coverage mean 0.6503. | Bridge diagnostics, undercoverage accounting, and Venn-Abers citation scope rows. | The bridge result should be read separately from predictive-distribution and generalized Venn-Abers research. |
| Unvalidated stronger claims are part of the result | Bounded-support validity and population-level group inference would require separate validation; the current record contains 0 bounded-support-validity-ready bundles and 0 population-inference-ready bundles. | Paper evidence map, publication claim/evidence matrix, bounded-support audit, and group diagnostic scope. | These gaps are reported as part of the scientific result. |
| Traceability and reproducibility surface | The knowledge graph is usable as a traceability surface with 3,643 nodes, 21,019 edges, 0 isolated nodes, and manifest reference resolution rate 1.0000. | Knowledge-graph quality audit and Research Atlas package manifest. | The KG is an evidence exploration layer for source inspection. |
| Publication package architecture | The Research Atlas package separates a concise main article, broad supplement, integrated Research Document, README review router, publication site, and evidence-scope checks. | Publication exemplar review, README, Research Atlas site manifest, and final-output scope protocol. | This row explains how the publication surfaces fit together. |

## Scientific Method Audit Trail

This table rewrites the study as a scientific-method chain: question, measurement, comparison, falsification, unsupported stronger claims, and reproducibility. It is included so a reader can see why the document reports both experiment-scoped practical signal patterns and negative or unsupported stronger conclusions.

| Stage | Reader question | Evidence anchor | Scientific scope |
|---|---|---|---|
| Question and empirical object | What exactly is being measured before any method interpretation? | 145,839 audited result rows, 67 datasets, 95 dataset-alpha cells, and 28 method labels. | Scope size is audit evidence, not proof of exhaustive internet coverage or performance in a future deployment setting. |
| Measurement protocol | Which quantities turn model outputs into comparable evidence? | Coverage, width, coverage-gated selected cells, coverage-tolerance pass rates, and undercoverage runs are read within dataset-alpha-method cells. | Empirical metrics are not theorem-level guarantees and do not imply conditional, endpoint, or subgroup claims. |
| Candidate-method comparison | Which practical patterns survived the audited comparison? | CQR has 56 coverage-gated selected cells and CV+ has 13; CQR row-weighted coverage mean is 0.9059. | This supports an experiment-scoped practical-signal reading under the current coverage criterion. |
| CQR backend sensitivity control | Was the CQR signal only caused by the fixed-GBM CQR backend? | The model-matched CQR rerun completed 4,564 rows and formed 224 paired dataset-alpha-model-family cells. Coverage-eligible interval-score selected cells were fixed-GBM CQR=116, model-matched CQR=71, and neither=37. | The check supports a backend-sensitivity reading. Broader CQR selection, deployment, or universal method-scope metadata would need a separate validation protocol. |
| Falsification and negative evidence | Which attractive readings still require validation? | The evaluated Venn-Abers bridge has 14 undercoverage runs and validated-regression support flag `False`. | The negative result is bridge-specific and does not reject predictive-distribution or generalized Venn-Abers research. |
| Stronger-claim limits | Which stronger conclusions must remain absent from the prose? | 0 bounded-support-validity-ready bundles and 0 population-inference-ready bundles. | A zero-ready evidence state is reported as a result; prose cannot convert it into bounded-support validity or population-level group inference. |
| Reproducibility and traceability | How can a reviewer trace the evidence? | 3,643 KG nodes, 21,019 KG edges, 0 isolated nodes, and manifest reference resolution rate 1.0000. | The KG and Research Atlas package are evidence-navigation surfaces for source tracing. |

## Review Decision Protocol

This protocol states what a reviewer can evaluate from the current evidence and which interpretations require separate validation. It is deliberately stricter than a normal report checklist because a polished artifact set can otherwise make scope-limited findings look broader than they are.

| Decision point | Accept review if | Evidence to check | Scope limit |
|---|---|---|---|
| Reader-facing readability | The Research Document, main article, supplement, README, and Research Atlas site keep the empirical wording scoped and readable. | 6 of 6 reader-facing surfaces pass the required language and scope checks. | Reader-facing readability does not establish stronger scientific claims or deployment use. |
| Empirical result wording | The fixed-GBM CQR, Mondrian, and CV+ pattern is written as experiment-scoped evidence. | CQR coverage-gated selected cells 56; CV+ coverage-gated selected cells 13; claim/evidence matrix status pass. | Method-choice, best-method, deployment, and universal-superiority readings require separate validation. |
| CQR backend sensitivity wording | The model-matched CQR rerun is reported as backend-sensitivity evidence for the CQR pipeline signal. | Completed fixed-GBM rows 4,564; completed model-matched rows 4,564; paired cells 224; coverage-eligible interval-score selections fixed-GBM=116, model-matched=71, neither=37. | Method selection and deployment use require separate validation. |
| Venn-Abers negative evidence | The evaluated bridge is reported as bridge-specific negative or failure-mode evidence. | 14 undercoverage runs and validated-regression support flag `False`. | No validated Venn-Abers regression interval claim and no literature-wide rejection of Venn-Abers research. |
| Unsupported stronger scientific claims | Bounded-support validity and population-group-inference claims are reported as unsupported rather than softened into optimistic prose. | Bounded-support-validity-ready bundles 0; population-inference-ready bundles 0. | No bounded-support validity, endpoint validity, population group-inference, or deployment-group-inference conclusion. |
| Evidence map and Research Atlas navigation | The KG and Research Atlas site help readers inspect claim-to-evidence routes. | 3,643 KG nodes, 21,019 edges, 0 isolated nodes, and manifest reference resolution rate 1.0000. | The KG is an evidence map for source inspection, not additional empirical evidence. |

## 1. Reader Primer

Regression conformal prediction wraps a regression model with a prediction interval calibrated to a target coverage level. The usual notation is `1 - alpha`, where `alpha` is the target miscoverage rate [Lei et al. (2017)]. Split conformal regression uses a calibration set to estimate a score quantile. Conformalized quantile regression, or CQR, instead starts from lower and upper quantile models and then conformalizes the resulting interval [Romano et al. (2019)]. Jackknife+ and CV+ use leave-one-out or out-of-fold predictions to account for fitted-model variability [Barber et al. (2020); Kim et al. (2020)].

Venn-Abers methods belong to a related but distinct calibration family. The literature includes Venn-Abers predictive distributions and generalized formulations, not merely ordinary interval wrappers [Nouretdinov et al. (2018); Nouretdinov and Gammerman (2024); Van Der Laan and Alaa (2025); Petej and Vovk (2026)]. For that reason, the present study does not claim to invalidate the Venn-Abers literature. It reports that the evaluated regression bridge did not validate as a strong interval solution in this experiment.

### Citation-Backed Concept Map

The concept map below links the plain-language idea, its literature basis, the experiment anchor in this study, and the reading that requires separate validation. It is included so non-specialist readers can see which parts are conformal prediction background, which parts are empirical observations, and which parts are evidence-scope limits.

| Concept | Reader question | Literature basis | Experiment anchor | Scope limit |
|---|---|---|---|---|
| Regression conformal prediction | What kind of uncertainty statement is being audited? | Distribution-free predictive inference for regression motivates calibrated prediction intervals under stated assumptions. [Lei et al. (2017)] | Coverage, width, interval score, and target `1 - alpha` are reported inside audited dataset-alpha-method cells. | Avoid reading marginal interval calibration as conditional, endpoint, subgroup, or deployment validity. |
| `1 - alpha` and `alpha` | Is the nominal target the same as observed coverage? | `1 - alpha` is the target coverage level and `alpha` is the target miscoverage rate used by the calibration rule. [Lei et al. (2017); Romano et al. (2019)] | The experiment evaluates observed coverage and coverage-tolerance behavior after the target level is fixed. | Avoid treating a nominal target as proof that every audited cell or subgroup achieved that target. |
| Calibration data and conformity scores | Where does the interval correction come from? | Conformal regression uses held-out calibration evidence to map model errors or scores into interval adjustments. [Lei et al. (2017)] | Split, normalized, Mondrian, and related rows differ partly by how calibration scores are pooled or stratified. | Avoid inferring that a calibration mechanism alone solves covariate shift, bounded support, or group-inference validity. |
| Conformalized Quantile Regression (CQR) | Why does CQR use two quantile models before calibration? | CQR starts from lower and upper quantile estimates and then conformalizes the interval using calibration residual evidence. [Romano et al. (2019)] | CQR has 56 coverage-eligible selected cells and is reported as an experiment-scoped practical signal. | The observed CQR pattern should not be converted into a universal best-method statement. |
| CV+ and jackknife-style resampling | Why do CV+ rows use out-of-fold predictions? | Jackknife+ and related cross-validation conformal methods use resampling predictions to account for model-fitting variability. [Barber et al. (2020); Kim et al. (2020)] | CV+ has 13 descriptive coverage-gated selected cells and is written as an experiment-scoped practical signal observed in these experiments. | Avoid treating CV+ evidence as a study-wide method choice or a claim that resampling always improves interval quality. |
| Group and Mondrian diagnostics | Why are group-calibrated rows not group-inference claims? | Group or stratified calibration changes how calibration evidence is pooled; it is separate from a population-group-inference estimand. [Lei et al. (2017)] | Mondrian absolute-residual calibration has 15 coverage-gated selected cells and 187 pairwise group comparisons are retained as diagnostics. | Avoid stating that group inference is solved while the population-group-inference ready bundle count is zero. |
| Venn-Abers predictive distributions | Why is the Venn-Abers result described narrowly? | Venn-Abers predictive distributions and generalized Venn-Abers calibration are broader than the interval bridge evaluated here. [Nouretdinov et al. (2018); Nouretdinov and Gammerman (2024); Van Der Laan and Alaa (2025); Petej and Vovk (2026)] | The evaluated bridge has 14 undercoverage runs and validated regression support flag `False`. | Avoid rejecting predictive-distribution or generalized Venn-Abers research from this bridge-specific negative evidence. |
| Evidence limits and scope | Why does the document report unsupported stronger readings? | The literature citations support method definitions; the evidence-scope checks are project controls, not new theory. [Lei et al. (2017); Romano et al. (2019)] | Study-wide method choice, bounded-support validity, and population-level group inference are outside the evidence in this study; the KG and Research Atlas support evidence inspection. | Avoid opening an unsupported stronger claim by wording it more optimistically in prose. |

### Terminology Compass

The following table fixes the meaning of recurring terms before the results are interpreted. Each term is defined as it is used in this Research Document. The last column states the scope limit that prevents a descriptive result from becoming a deployment rule.

| Term | Plain-language meaning | Role in this document | Scope |
|---|---|---|---|
| `prediction interval` | A lower-to-upper range around a regression prediction. | The interval is the object whose empirical coverage and width are audited. | Production use would require separate validation. |
| `coverage` | The fraction of held-out outcomes that fall inside the interval. | Coverage is reported as an empirical diagnostic by dataset, alpha, and method family. | Observed coverage is interpreted within the audited experiment. |
| `1 - alpha` | The target coverage level; alpha is the target miscoverage rate. | Dataset-alpha cells define the main calibration comparison unit. | Near-target behavior is reported within the audited scope only. |
| `calibration set` | Data reserved to tune interval size after the base model is fit. | Calibration is the mechanism that turns model errors into interval adjustments. | Calibration diagnostics do not establish deployment validity. |
| `CQR` | Conformalized Quantile Regression: quantile models plus conformal calibration. | CQR is reported as an experiment-scoped practical signal observed in these experiments. | General CQR best-method readings require separate validation. |
| `CV+` | A cross-validation-style conformal method using out-of-fold predictions. | CV+ is reported as an experiment-scoped practical signal observed in these experiments. | The document reports the observed experiment pattern. |
| `coverage-gated selected cell` | A dataset-alpha comparison where a method appears on the descriptive trade-off set. | Coverage-gated selected-cell counts summarize observed coverage/width trade-offs. | A coverage-gated selected-cell count is descriptive evidence for the audited result surface. |
| `Venn-Abers regression bridge` | The evaluated bridge from Venn-Abers-style calibration evidence to regression intervals. | It is reported as negative/failure-mode evidence in this study. | This does not invalidate the broader Venn-Abers literature. |

### How To Interpret `1 - alpha`

`1 - alpha` is the target coverage level, not an observed success rate. For example, if `alpha = 0.10`, the target coverage is 0.90. A conformal method can be judged against that target only after specifying the dataset, split policy, calibration method, and scoring rule. This Research Document therefore reports coverage, coverage-tolerance behavior, coverage-gated selection, and evidence limits as scoped empirical diagnostics rather than theorem claims [Lei et al. (2017); Romano et al. (2019)].

This distinction matters for non-specialist readers. A method can show attractive empirical coverage in this study and still remain inappropriate as a general deployment rule. Conversely, a failure mode for one evaluated bridge does not reject an entire research family. The document keeps both sides visible so the later article, supplement, and KG can cite exactly what was observed.

### Evidence Interpretation Ledger

The guide below separates three layers that are easy to confuse: the conformal prediction theorem layer, the empirical audit layer, and the evidence-limit layer. It is an interpretation guide, not a new theorem and not a new experiment. The marginal coverage language follows the regression conformal prediction sources [Lei et al. (2017); Romano et al. (2019)], while the Venn-Abers row is bounded by the predictive-distribution and generalized-calibration sources [Nouretdinov et al. (2018); Nouretdinov and Gammerman (2024); Van Der Laan and Alaa (2025); Petej and Vovk (2026)].

| Topic | Reader-facing statement | Required condition or evidence | Scope limit |
|---|---|---|---|
| Marginal conformal coverage | The conformal regression guarantee is a marginal coverage statement for future exchangeable draws, not a pointwise promise for every individual row. | Exchangeability, a fixed calibration protocol, and a stated `1 - alpha` target. | Avoid reading marginal coverage as conditional, subgroup, endpoint, or deployment coverage. |
| Empirical coverage in this study | Observed coverage summarizes held-out behavior inside the audited dataset, split, method, and alpha scope. | Completed-row accounting, dataset-alpha cells, split policy, and result audits. | Avoid converting an empirical coverage mean into a theorem or a general product deployment rule. |
| Conditional and group behavior | Group and Mondrian diagnostics can reveal heterogeneity, but they do not by themselves prove population-level group inference. | Group definitions, calibration sample sizes, pairwise comparisons, and the population-group-inference evidence criterion. | Avoid stating that group inference is solved when the population-group-inference ready bundle count is zero. |
| Efficiency and coverage-gated selection evidence | Coverage-width coverage-gated selected-cell counts describe the observed trade-off surface among audited methods. | Coverage, width, interval-score, and robustness diagnostics under the same comparison policy. | Avoid treating coverage-gated selection as a study-wide method choice or as evidence of universal superiority. |
| Venn-Abers regression bridge | The negative result concerns the evaluated interval bridge, while Venn-Abers predictive-distribution and generalized calibration work remain separate literature objects. | Bridge implementation details, undercoverage diagnostics, and the Venn-Abers citation scope. | Avoid rejecting the broader Venn-Abers literature from this bridge failure mode. |

### Method Mechanics At A Glance

The table below explains how each method family creates or adjusts prediction intervals before the empirical results are read. It is intentionally operational: the goal is to show what changes the interval, and which interpretation limits remain attached to that mechanism.

| Method family | What it does | What the interval depends on | Study scope |
|---|---|---|---|
| Split conformal regression | Fits a regression model, measures held-out calibration errors, and expands future predictions by a calibration quantile. | The split policy, the residual score, and the empirical score quantile tied to `1 - alpha`. | It is a baseline calibration mechanism; heterogeneity and endpoint validity require additional analysis. |
| CQR | Fits lower and upper quantile models, then conformalizes the two-sided quantile interval with calibration scores. | Quantile-model quality, lower/upper quantile levels, calibration scores, and the target miscoverage rate. | Observed here as an experiment-scoped practical signal; universal regression-CP use would require separate validation. |
| CV+ / jackknife-style methods | Uses out-of-fold or leave-one-out predictions so interval construction reflects model-fitting variability. | Fold design, base-model stability, conformity scores, and the cross-validated aggregation rule. | Observed here as an experiment-scoped practical signal within the audited experiment. |
| Mondrian calibration | Calibrates scores within groups or strata rather than using a single pooled calibration quantile. | The grouping rule, group sample sizes, residual scores, and the same `1 - alpha` coverage target. | Useful as a diagnostic comparator; group diagnostics avoid becoming population-group-inference claims. |
| Venn-Abers regression bridge | Maps Venn-Abers-style calibration evidence into interval-style regression diagnostics for this experiment. | The bridge design, its calibration object, and the diagnostic conversion into coverage/interval evidence. | The evaluated bridge produced negative evidence here; this does not reject the broader Venn-Abers literature. |

## Publication Design Basis

The Research Document, supplement, README, and site follow a small source-backed review of comparable conformal prediction papers, repositories, docs, and sites. That review shapes the evidence-exploration structure; it does not add experiments or change the empirical method comparison.

| Design decision | Project application |
|---|---|
| Use a minimal main article and a broad supplementary document. | The main article keeps the claim-evidence map and headline results; the supplement carries broad method, dataset, audit, robustness, and negative-evidence material. |
| Make the README a review router, not a dense methods dump. | The README starts with status, plain-language summary, review path, evidence snapshot, repository map, KG entry, and citation surface. |
| Use the site as a Research Atlas review portal with explicit lanes. | The Research Atlas site should expose the handoff, Research Document, rendered article/supplement, KG browser, and governance checks. |
| Pair every reader-facing claim with evidence and a scope limit. | The article, Research Document, and README retain neutral language: observed practical candidates are not deployment rules, and bridge-specific failures are not literature-wide rejections. |
| Give the Research Document a checklist-like transparency spine. | The Research Document should visibly cover claims, limitations, assumptions, reproducibility route, compute, license and source provenance, and publication-scope checks. |
| Expose reproduction structure while excluding raw data and secrets. | The Research Atlas package records source, configs, tests, reports, and metadata, while excluding raw data, caches, local databases, and secret-like material. |
| Treat the knowledge graph as a browsable supplementary evidence surface. | The KG browser is an evidence map for source inspection. |
| Make result verification commands and expected outputs explicit. | The Research Atlas README should connect headline results to exact commands, manifest paths, and expected pass/fail statuses rather than relying on prose-only reproducibility claims. |
| Keep Venn-Abers wording bridge-specific and conservative. | The Research Document reports that the evaluated bridge did not emerge as the expected strong regression solution in these experiments. |
| Keep evidence navigation and interpretation scope explicit. | The Research Atlas package gives readers the article, supplement, KG browser, and reproducibility materials with clear evidence links. |

## 2. Experimental Scope

| Scope item | Value | Interpretation |
|---|---:|---|
| Audited synthesis rows | 145,839 | Audited empirical accounting scope |
| Datasets | 67 | Public regression dataset scope |
| Dataset-alpha cells | 95 | Calibration comparison cells |
| Conformal-method labels | 28 | Broad conformal method surface |
| Model-matched CQR completed rows | 4,564 | Backend-confound sensitivity check |
| CQR fixed-vs-model-matched paired cells | 224 | Dataset-alpha-model-family comparison cells |
| Supplement sections | 6 | Broad supplementary evidence plan |

The design emphasizes resumability, source traceability, duplicate and leakage controls, and conservative interpretation limits. The study therefore treats unsupported stronger readings as part of the result rather than as missing decoration. If endpoint, group inference, or validation evidence is not satisfied, the Research Document reports the stronger reading as beyond this study.

### Audit Controls

The study accounting separates empirical observations from broader interpretations. The current source artifacts record 6 of 6 reader-facing surfaces passing the required language and scope checks. Cross-run leakage status is `hard_leakage_not_detected_in_scanned_artifacts`, with 0 unsupported-claim hits in the scanned cross-run artifacts. These controls support the Research Atlas document and keep future-setting use as a separate validation question.

Duplicate handling is also reported as evidence rather than hidden. The supplement records 29 duplicate actions, 46 quarantined actions, and 0 unquarantined actions. The Research Document therefore keeps the interpretation conditional on the audited data-integrity state.

## 3. Observed Method Behavior

### Result Reading Guide

The result tables combine several diagnostic quantities. The guide below states how each quantity should be read before the method rows are interpreted. This prevents a descriptive metric from being mistaken for a study-wide method choice, a group-inference claim, an endpoint-validity claim, or a Venn-Abers validation claim.

| Metric | Plain-language meaning | How to read it | Scope |
|---|---|---|---|
| `row-weighted coverage mean` | Average empirical coverage after giving larger completed-result blocks proportionally more influence. | Use it as a broad descriptive coverage summary within the audited experiment scope. | It is a descriptive coverage summary within the audited experiment. |
| `diagnostic row-weighted coverage band` | A quantified uncertainty band around the observed aggregate coverage estimate. | Use it to judge the precision of the descriptive aggregate, not only the point estimate. | It does not remove split, dataset, endpoint, or selection caveats. |
| `coverage-gated selected cell` | A dataset-alpha comparison where a method sits on the observed coverage/width trade-off set. | Use coverage-gated selected-cell counts as a compact map of practical trade-offs seen in the study. | A coverage-gated selected-cell count is descriptive evidence, descriptive evidence rather than a general deployment rule. |
| `coverage-tolerance hit rate` | The share of comparison cells where empirical coverage is close to the target `1 - alpha` level. | Use it to separate approximate calibration behavior from raw coverage averages. | Coverage tolerance behavior remains scoped to the audited cells. |
| `undercoverage run` | A run where empirical coverage falls below the target coverage level by the audit rule. | Use it as failure-mode evidence, especially for methods or bridges that do not satisfy validation evidence checks. | It is bridge- or run-specific evidence; the broader literature remains separate. |
| `evidence limit` | A recorded limit on the strongest conclusion supported by the current evidence. | Use evidence limits as part of the result: they identify which broader readings need separate validation. | Evidence limits can change only when new evidence changes the study record. |

### Evidence-To-Claim Interpretation Ladder

The ladder below connects each result type to the strongest claim it can support and the claim it still cannot support. It is the reader-facing bridge between the numeric tables and the neutral prose used in the Research Document.

| Evidence layer | What it can support | Evidence in this study | What it cannot support | Reader action |
|---|---|---|---|---|
| Nominal target | `1 - alpha` states the coverage target that a method is evaluated against. | 95 dataset-alpha cells define the main target/coverage comparison surface. | It cannot prove that every dataset, endpoint, or group achieved the nominal target. | Compare observed coverage and coverage-tolerance rates after reading the target. |
| Observed aggregate coverage | Coverage means and descriptive ranges summarize empirical interval behavior inside the audited scope. | CQR row-weighted coverage mean is 0.9059; CV+ row-weighted coverage mean is 0.8997. | It cannot be rewritten as theorem-level conditional coverage or deployment validity. | Use coverage as one descriptive axis, not as a standalone deployment rule. |
| Coverage-width trade-off | Coverage-gated selected cells identify methods that looked practically efficient under the audited comparison policy. | CQR has 56 coverage-gated selected cells; CV+ has 13. | Coverage-gated selection evidence cannot be promoted to a universal best-method claim. | Read the fixed-GBM CQR, Mondrian, and CV+ pattern as experiment-scoped evidence. |
| Robustness retention | Bootstrap and leave-one diagnostics test whether the practical candidate pattern is fragile. | Bootstrap selection counts are cqr=1,000; leave-one-dataset and leave-one-alpha retention rates are 1.0000 and 1.0000. | Robustness retention cannot by itself choose a universal method or validate a new deployment setting. | Use robustness as support for cautious wording, not for a method-choice sentence. |
| CQR backend sensitivity | The model-matched rerun tests whether the fixed-GBM CQR signal was only a backend artifact. | 4,564 model-matched CQR rows, 224 paired cells, selected cells fixed-GBM CQR=116, model-matched CQR=71, neither=37. | It cannot promote CQR from experiment-scoped practical signal to a universal method choice. | Read the check as backend-confound evidence and keep the claim descriptive. |
| Negative bridge evidence | Undercoverage and a validation flag set to false support a narrow failure-mode reading for the evaluated bridge. | The evaluated Venn-Abers bridge has 14 undercoverage runs and validated-regression support flag `False`. | It cannot reject predictive-distribution or generalized Venn-Abers research. | Report the bridge result as negative evidence exactly at the evaluated bridge scope. |
| Evidence limits | Evidence limits identify broader readings that need separate validation before they are used as conclusions. | Bounded-support-validity-ready bundles 0; population-inference-ready bundles 0; the KG is available as an evidence map for source inspection. | A polished site, README, or evidence map cannot by itself turn a broader reading into an empirical conclusion. | Treat evidence limits as part of the study scope. |

### Claim Language Guide

The rows below are writing guide rows derived from the claim/evidence verification matrix. They state the study wording currently supported, the source or citation evidence that must stay attached to it, the stronger reading requiring validation, and the plain-language reason a non-specialist reader should not read more into the evidence than the study can support.

| Target | Claim type | Supported wording | Source/citation evidence | Stronger reading requiring validation | Plain-language note |
|---|---|---|---|---|---|
| `main_article` | `scope_claim` | The dataset/source audit defines the studied scope under the recorded review policy. | Dataset/source descriptions need source citations before report prose; the matrix does not certify exhaustive internet coverage. | Avoid implying exhaustive internet coverage or final dataset-level result overstatement. | This row tells a reader what data sources were inspected; the dataset list defines study scope rather than a final dataset-level result. |
| `main_article` | `descriptive_empirical_claim` | Under the current coverage criterion, the fixed-GBM CQR pipeline was most frequently selected; Mondrian calibration and CV+ were secondary candidates. The comparison is experiment-scoped; using the pattern in a new setting would need its own validation plan. | Method descriptions need literature citations; empirical language must stay limited to these experiments. | Keep CQR, CV+, and other methods within experiment-scoped interpretation. | This row permits a careful description of what looked useful in the experiment, bounded to the audited experiment for every regression problem. |
| `main_article` | `stronger_claim_requires_validation` | The current evidence does not establish a study-wide method choice, final main result, or deployment rule. | A stronger reading would need a later pre-specified selection protocol if the scientific state changes. | Avoid presenting a final main-results table, method choice, or positive method conclusion. | This row prevents a reader from mistaking promising diagnostic patterns for a final answer. |
| `supplementary_document` | `caveated_diagnostic_claim` | Robustness rows are post-selection diagnostics and should be read with their multiplicity caveats. | Statistical or robustness interpretations need the documented audit context; they are not confirmatory superiority claims. | Avoid converting robustness diagnostics into confirmatory superiority. | This row says the extra checks are useful diagnostics, not proof that one method is definitively preferred. |
| `supplementary_document` | `negative_failure_mode_claim` | In these experiments, the evaluated fast Venn-Abers regression bridge did not validate as the expected strong regression interval solution. | The claim is bridge-specific negative evidence and leaves the broader Venn-Abers literature separate. | Avoid stating or imply validated Venn-Abers regression. | This row records that one tested bridge behaved poorly while the broader Venn-Abers literature remains separate. |
| `supplementary_document` | `methodology_record_claim` | The study includes audit controls for traceability, neutrality, and reproducibility. | Control descriptions support reproducibility claims; scientific validity rests on the empirical evidence. | Avoid treating control presence as proof of validity or production readiness. | This row explains the guardrails around the study rather than claiming the guardrails make every result final. |
| `supplementary_document` | `reproducibility_traceability_claim` | The Research Atlas package records completed-row accounting, resume-safety controls, and knowledge-graph traceability. | Cite the Research Atlas repository; source provenance is tracked separately. | Cite the Research Atlas repository. | This row tells a reader how the work can be audited and resumed, source provenance is tracked separately. |
| `individual_experiment_report` | `authoring_blueprint_claim` | The individual report blueprint records the author-stamped section map for later review. | This is a section map for review. | Keep generated report formats tied to the evidence recorded here. | This row preserves the report plan and author metadata for traceable review. |

| Method family | Key observed evidence | Supported interpretation |
|---|---:|---|
| CQR | 56 descriptive coverage-gated selected cells; row-weighted coverage mean 0.9059 | Experiment-scoped practical signal observed in this experiment |
| Model-matched CQR check | 4,564 completed model-matched rows; 224 paired cells; selected cells fixed-GBM=116, model-matched=71, neither=37 | Backend sensitivity evidence for the CQR pipeline signal |
| CV+ | 13 descriptive coverage-gated selected cells; row-weighted coverage mean 0.8997 | Experiment-scoped practical signal observed in this experiment |
| Mondrian absolute-residual calibration | 15 descriptive coverage-gated selected cells; row-weighted coverage mean 0.9073 | Useful diagnostic comparator |
| Venn-Abers regression bridge | 14 undercoverage runs; quantile-coverage mean 0.6503 | Negative/failure-mode evidence for the evaluated bridge |

The CQR row-weighted coverage mean is 0.9059, with a diagnostic row-weighted band from 0.9050 to 0.9068. This is evidence of strong empirical behavior inside the audited scope. It is not a proof that CQR is generally best; applying the pattern in a new setting would need its own validation plan.

Robustness diagnostics are aligned with that descriptive reading. The common-cell method choice is `cqr`; common-cell counts are CQR=58, CV+=15, and Mondrian=21. Bootstrap selection counts are cqr=1,000. Leave-one-dataset and leave-one-alpha retention rates are 1.0000 and 1.0000. These numbers support a practical-candidate description; they do not turn the result into a universal method choice.

Coverage summaries provide additional context. CQR has nominal and coverage-tolerance pass rates of 0.6118 and 0.8076; CV+ has coverage-tolerance hit rate 0.8136; Mondrian absolute-residual calibration has coverage-tolerance hit rate 0.8586. The document reports these values as diagnostics at the audited scope.

## 4. Negative Evidence And Unsupported Stronger Claims

Three high-risk readings require separate validation. First, bounded-support validity has 0 bundles are validity-ready, despite 15 bounded-support bundles and 11 raw endpoint-excursion bundles being recorded. Second, population-level group inference has 0 bundles are population-inference-ready, even though 15 group-inference bundles and 187 pairwise group comparisons are available as diagnostics. Third, the evaluated Venn-Abers bridge is reported as negative evidence rather than as a validated regression solution.

The Venn-Abers result is intentionally narrow. The evaluated bridge has quantile-coverage mean 0.6503, coverage-tolerance hit rate 0.0337, and validated-regression support flag `False`. This does not reject Venn-Abers research. It only records that the current regression interval bridge did not satisfy the validation evidence needed in this experiment.

## 5. Knowledge Graph And Reproducibility

The current knowledge graph has 3,643 nodes, 21,019 edges, and 0 isolated nodes. Average edge confidence is 0.9917, and manifest reference resolution rate is 1.0000. In the Research Atlas package, the KG browser exposes 3,643 nodes, 21,019 edges, 39 node types, and 58 relation types. The browser lets readers move from claims to source reports, tables, scripts, and quality checks.

## 6. How To Read The Artifact Set

The review order is deliberately simple. Read this Research Document first, then inspect the rendered main article and broad supplement, then use the individual experiment report for the author-stamped experiment summary. The KG browser should be used when a reader wants to trace a claim to reports, source artifacts, scripts, or quality checks. Governance files record which broader readings need separate validation.

| Artifact | Role | Study scope |
|---|---|---|
| `Research Document/research_document.md` | Integrated Research Atlas narrative | Descriptive, experiment-scoped interpretation |
| `rendered_outputs/main_article_review.html` | Main article surface | Conservative scientific wording |
| `rendered_outputs/supplementary_document_review.html` | Broad supplementary surface | Methods, diagnostics, and estimator conventions |
| `site/kg_browser.html` | Browsable KG surface | Evidence navigation and source traceability |
| `governance/publication_authoring_decision_record.md` | Study scope record | Scientific scope limits and publication context |

## 7. How To Read The Evidence

This document is intentionally strict about which broader readings need evidence beyond this study:

- This Research Document is a Research Atlas narrative for experiment-scoped interpretation.
- Under the current coverage criterion, the fixed-GBM CQR pipeline was most frequently selected; Mondrian calibration and CV+ were secondary candidates. The comparison is experiment-scoped; using the pattern in a new setting would need its own validation plan.
- The model-matched CQR rerun evaluates backend sensitivity.
- The evaluated Venn-Abers regression bridge is described as negative/failure-mode evidence.
- Population-level group inference, bounded-support validity, validated Venn-Abers regression, production, and best-method readings require separate validation.
- The KG is an evidence map for source inspection.
- No new experiments are introduced by this document.
- Publication-package design examples are used only to improve navigation and source traceability.

## References

- Barber et al. (2020). *Predictive inference with the jackknife+*. [https://arxiv.org/abs/1905.02928](https://arxiv.org/abs/1905.02928).
- Kim et al. (2020). *Predictive Inference Is Free with the Jackknife+-after-Bootstrap*. [https://arxiv.org/abs/2002.09025](https://arxiv.org/abs/2002.09025).
- Lei et al. (2017). *Distribution-Free Predictive Inference for Regression*. [https://arxiv.org/abs/1604.04173](https://arxiv.org/abs/1604.04173).
- Nouretdinov et al. (2018). *Inductive Venn-Abers predictive distribution*. [https://proceedings.mlr.press/v91/nouretdinov18a.html](https://proceedings.mlr.press/v91/nouretdinov18a.html).
- Nouretdinov and Gammerman (2024). *Inductive Venn-Abers Predictive Distributions: New Applications and Evaluation*. [https://proceedings.mlr.press/v230/nouretdinov24a.html](https://proceedings.mlr.press/v230/nouretdinov24a.html).
- Petej and Vovk (2026). *Inductive Venn-Abers and related regressors*. [https://arxiv.org/html/2605.06646v1](https://arxiv.org/html/2605.06646v1).
- Romano et al. (2019). *Conformalized Quantile Regression*. [https://arxiv.org/abs/1905.03222](https://arxiv.org/abs/1905.03222).
- Van Der Laan and Alaa (2025). *Generalized Venn and Venn-Abers Calibration with Applications in Conformal Prediction*. [https://proceedings.mlr.press/v267/van-der-laan25a.html](https://proceedings.mlr.press/v267/van-der-laan25a.html).

## Source Artifacts

- `publication_authoring_decision_record`: `study/research_document/publication_authoring_decision_record.json`
- `main_article_source`: `study/research_document/main_article_source.json`
- `supplement_source`: `study/research_document/supplement_source.json`
- `individual_experiment_report_source`: `study/research_document/individual_experiment_report_source.json`
- `claim_evidence_verification_matrix`: `study/research_document/claim_evidence_verification_matrix.json`
- `publication_citation_registry`: `study/research_document/publication_citation_registry.json`
- `knowledge_graph_quality_summary`: `study/reports/knowledge_graph_quality/quality_summary.json`
- `research_atlas_package_manifest`: `study/research_document/research_atlas_package_manifest.json`
- `publication_exemplar_review`: `study/research_document/publication_exemplar_review.json`
- `cqr_fixed_vs_model_matched_synthesis`: `study/reports/model_matched_cqr_rerun_plan/cqr_fixed_vs_model_matched_synthesis.json`
