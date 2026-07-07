# Regression Data Policy Registry

These policies are binding defaults for regression conformal experiments unless
a dataset audit records a more specific override.

## Policy Gates

Every dataset must pass these gates before headline model sweeps:

1. Source and license/access note recorded in `catalogs/source_registry.md` or
   the dataset audit.
2. Target policy recorded: raw scale, transformed scale, censoring/top-coding,
   and invalid/missing target handling.
3. Group policy recorded: protected attribute, proxy attribute, aggregate
   demographic rate, operational group, or benchmark-only grouping.
4. Leakage policy recorded: target descendants, post-outcome variables, IDs,
   near-duplicates, and known deterministic target components.
5. Missingness policy recorded: placeholder tokens, high-missing features, and
   train-only imputation rule.
6. Duplicate policy recorded when duplicate row rate is above 5%.
7. Split policy recorded: random, time-aware, geography-aware, group-aware, or
   benchmark-only random split.

## Defaults

- Missing targets are dropped before splitting.
- Feature preprocessing is fit only on the training split.
- Numeric features use train-fitted median imputation, train-fitted 1%/99%
  winsorization, and train-fitted standard scaling.
- Categorical features use train-fitted most-frequent imputation and label
  encoding with unseen categories mapped to `-1`.
- The primary group column is excluded from model features in the pilot runner.
- Columns with more than 95% missingness on the training split are dropped by
  default and must be reported.
- Duplicate row rates above 5% require either deduplication or a raw-vs-dedup
  sensitivity run before the dataset can be used for headline evidence.
- Highly skewed targets, using `abs(skew) > 1` from the audit helper, require a
  target-transform sensitivity plan. For monotone transforms, intervals must be
  inverted back to the original unit before reporting width and coverage.
- Postsecondary institution outcome datasets require cohort-alignment,
  privacy-suppression, post-entry outcome leakage, and ecological/proxy
  interpretation policies before runner use or publication-grade fairness
  interpretation.
- Household-finance survey datasets require multiple-imputation pooling,
  main/replicate-weight handling, family-level grouped split, target-component
  exclusion, and extreme-tail target-transform policy before runner use or
  population claims.

## Dataset-Specific Current Decisions

- `uci_student_performance`: prior-grade sensitivity smoke and model-family
  sweep complete, headline claims still gated. UCI explicitly states that
  `G1` and `G2` are prior-period grades strongly correlated with final grade
  `G3`; the runner keeps two explicit variants:
  `uci_student_performance_with_prior_grades` carries `G1` and `G2`, while
  `uci_student_performance_no_prior_grades` drops both. Local source check
  records `G1`-`G3` correlation 0.8264 and `G2`-`G3` correlation 0.9185. The
  three-seed ridge smoke completed 36/36 runs and resume returned 36/36
  `skipped_completed`. The follow-on two-seed model-family sweep completed
  1428/1428 runs across both variants, 51 model configurations, and seven
  conformal methods; a no-force rerun returned 1428/1428
  `skipped_completed`. No-prior CQR is nominal in 51/51 seed-aggregated rows
  with coverage 0.9077 and score 12.6801, and no-prior XGBoost with
  `venn_abers_split_fallback` has the best nominal-or-above score at coverage
  0.9038, gap 0.0164, width 9.2353, and score 12.6733. With-prior LightGBM
  with `normalized_abs` has the best nominal-or-above score at coverage
  0.9077, gap 0.0194, width 4.0431, and score 5.5375, but the with-prior
  variant has only 15/357 nominal-or-above rows versus 175/357 for no-prior.
  Fast `venn_abers_quantile` is nominal in 0/51 rows for both variants. Treat
  as a small education benchmark and prior-grade availability sensitivity
  study only, not causal, intervention, student-policy, sex/gender fairness,
  leakage-proof, final model-selection, bounded-grade-clipping, or validated
  Venn-Abers regression evidence. Broad use still requires bounded/discrete
  target interval sensitivity, prior-grade inclusion/drop sensitivity across
  additional split policies, subject/course sensitivity, and exact/reference
  Venn-Abers diagnostics.
- `uci_auto_mpg`: small vehicle fuel-economy benchmark smoke and model-family
  sweep complete; protected-class fairness, emissions-regulatory, and
  vehicle-engineering claims are out of scope. The official UCI source has 398
  rows, target `mpg`, 7 feature columns, missing `horsepower`, and `car_name`
  as an ID column. The runner loads UCI id 9 through `ucimlrepo`, uses
  `origin` only as a vehicle-source diagnostic group, excludes `mpg` and
  `origin` from model features, and leaves `horsepower` missingness to
  train-fitted numeric median imputation. Current `ucimlrepo` payload has no
  `car_name`; sampled prediction metadata confirms six final model features:
  `displacement`, `cylinders`, `horsepower`, `weight`, `acceleration`, and
  `model_year`. The five-seed ridge identity-scale smoke completed 30/30 runs
  and resume returned 30/30 `skipped_completed`. The two-seed 51-config
  model-family sweep completed 714/714 runs and resume returned 714/714
  `skipped_completed`. The sweep's best nominal-or-above score is XGBoost
  `max_depth=2, learning_rate=0.03, n_estimators=120` with `cv_plus`:
  coverage 0.9438, `origin` diagnostic gap 0.0854, mean width 10.0858, and
  score 12.4140. Repeated fixed-backend CQR is nominal in 51/51 rows with
  mean score 12.7283, but these rows are fixed quantile-backend baselines
  repeated under outer model labels. `venn_abers_quantile` remains
  diagnostic-only, nominal in 0/51 rows with mean coverage 0.7305. Broad use
  still requires origin-as-feature sensitivity, missing-horsepower
  drop-vs-impute sensitivity, grouped or temporal model-year sensitivity, and
  nonnegative interval clipping.
- `openml_kin8nm_y`: synthetic robot-arm benchmark smoke and model-family
  sweep complete. OpenML id
  189 has 8,192 rows, target `y`, eight numeric `theta*` features, no missing
  values, no duplicate rows, and no sensitive-name hits. The runner derives
  `theta3_bin` diagnostics from `theta3`, drops raw `theta3`, uses identity
  target modeling, and keeps the remaining seven `theta*` fields as benchmark
  features. The five-seed ridge smoke completed 30/30 runs and resume returned
  30/30 `skipped_completed`. CQR has the lowest nominal-or-above interval
  score 0.8428 with coverage 0.9024 and gap 0.0889; Mondrian has the smallest
  gap 0.0416 with coverage 0.9046; CV+ is closest to nominal at coverage
  0.9073; `venn_abers_quantile` undercovers at 0.5656. The follow-on
  model-family sweep completed 714/714 runs across 51 model configurations,
  seven conformal methods, and seeds 11/23; a no-force rerun returned 714/714
  `skipped_completed` records. The sweep corrected the CV+ train-row cap to
  5000 so all 102 CV+ atomic rows completed. It improves the ridge-smoke
  score frontier with RBF SVR `C=0.3, epsilon=0.1, gamma=scale` plus
  `normalized_abs`: coverage 0.9079, `theta3_bin` diagnostic gap 0.1576,
  mean width 0.5888, and score 0.7291. It also improves the diagnostic-gap
  frontier with RBF SVR `C=1.0, epsilon=0.03, gamma=0.01` plus
  `mondrian_abs`: coverage 0.9131, gap 0.0191, mean width 0.7320, and score
  0.9008. Fast `venn_abers_quantile` is nominal in 0/51 seed-aggregated rows.
  Treat as synthetic benchmark diagnostics and post-hoc model-family triage
  only, not protected-class fairness evidence, robotics control guidance,
  physical-system validation, final model selection, or validated Venn-Abers
  regression evidence.
- `openml_delta_elevators_se`: tabular control benchmark model-family sweep
  complete.
  OpenML id 198 has 9,517 rows, target `Se`, six numeric control features, no
  missing values, no duplicate rows, and no sensitive-name hits. The runner
  derives `climbRate_bin` diagnostics from `climbRate`, drops raw
  `climbRate`, uses identity target modeling, and keeps the remaining five
  control fields as benchmark features. The five-seed ridge smoke completed
  30/30 runs and resume returned 30/30 `skipped_completed`. The follow-on
  two-seed model-family sweep completed 714/714 runs across 51 model
  configurations and seven conformal methods; a no-force rerun returned
  714/714 `skipped_completed` records. The sweep sets
  `cv_plus_max_train_rows` to 6000 so CV+ completes on the 5,710-row training
  split. It slightly improves the ridge-smoke score frontier with RBF kernel
  ridge `alpha=0.1, gamma=0.01` plus `cv_plus`: coverage 0.9013,
  `climbRate_bin` diagnostic gap 0.0534, mean width 0.0055408, and score
  0.0073378. It improves the nominal diagnostic-gap frontier with elastic net
  `alpha=0.01, l1_ratio=0.25` plus `mondrian_abs`: coverage 0.9341, gap
  0.0300, mean width 0.0075032, and score 0.0099254, which is a
  gap/width/overcoverage tradeoff rather than the score frontier. Fast
  `venn_abers_quantile` is nominal in 0/51 seed-aggregated rows with mean
  coverage 0.6073. Treat as tabular control benchmark diagnostics and
  post-hoc model-family triage only, not protected-class fairness evidence,
  aircraft-control guidance, safety validation, physical-system validation,
  final model selection, or validated Venn-Abers regression evidence.
- `openml_arsenic_event_rate_panel`: aggregate epidemiology event-rate
  benchmark smoke and model-family sweep complete. The runner combines OpenML
  ids 533, 513, 482, and
  536, each with 559 aggregate rows and common columns `group`, `conc`, `age`,
  `at.risk`, and `events`. The target is derived as `event_rate_per_100k =
  events / at.risk * 100000`; the derived rate is zero-inflated and heavily
  right-skewed, so the smoke uses `log1p` target modeling and reports metrics
  after inverse transformation to rate-per-100k units. `sex` is the primary
  diagnostic group. Raw `events`, `at.risk`, source `group`, and `openml_id`
  are dropped before modeling, leaving `conc`, `age`, and `cancer_site` as
  model features. The five-seed ridge smoke completed 30/30 runs and resume
  returned 30/30 `skipped_completed`. CQR has the lowest nominal-or-above
  interval score, with coverage 0.9446, sex gap 0.0107, mean width 608.00, and
  score 1041.20. `normalized_abs` has the smallest sex gap 0.0097 but much
  wider intervals, with mean width 2069.39 and score 2932.01. CV+ is closest
  to nominal by absolute error but is just below target at coverage 0.8951.
  `venn_abers_quantile` undercovers at 0.7991. The follow-on two-seed
  model-family sweep completed 714/714 runs across 51 model configurations and
  seven conformal methods; a no-force rerun returned 714/714
  `skipped_completed` records. The sweep records inverse-transform metadata
  and has 154 saturated `log1p` inverse endpoints, all in `normalized_abs`
  rows; saturation keeps finite metrics and marks pathological numerical
  intervals. The repeated fixed CQR quantile backend has the lowest
  nominal-or-above interval score: coverage 0.9576, sex gap 0.0184, mean width
  608.7144, and score 933.0240. XGBoost with `cv_plus` is the tightest
  nominal-or-above row: coverage 0.9007, gap 0.0317, mean width 274.1785, and
  score 1668.0485. Histogram gradient boosting with `split_abs` has the
  smallest non-`normalized_abs` nominal diagnostic gap: coverage 0.9107, gap
  0.0034, mean width 391.8521, and score 1629.4065. Fast
  `venn_abers_quantile` is nominal in 0/51 seed-aggregated sweep rows with
  mean coverage 0.7796. Treat as aggregate epidemiology rate benchmark
  diagnostics only, not individual fairness evidence, clinical or
  epidemiological inference, source-family generalization,
  exposure-adjusted count-model validation, cancer-risk evidence, or validated
  Venn-Abers regression evidence. Broad use still requires exposure/offset
  count-model sensitivity, raw-count vs derived-rate target sensitivity,
  sex-feature inclusion/drop sensitivity, source-family grouped splitting, and
  Venn-Abers grid/reference diagnostics.
- `openml_analcatdata_hiroshima_rate`: radiation biology derived-rate
  duplicate-sensitivity smoke and model-family sweep complete. The source
  OpenML id 494 frame has
  649 rows, `Dose`, constant `Total_cells` equal to 100, and raw count target
  `Aberrant_cells`. The runner derives `aberrant_rate_per_100 =
  Aberrant_cells / Total_cells * 100`, derives `dose_band` diagnostics from
  `Dose`, drops raw `Aberrant_cells` and `Total_cells`, keeps `Dose` as the
  single scientific predictor, and applies `log1p` target modeling. Because
  the raw frame has 81.51% exact duplicate rows, the approved smoke always
  pairs raw `openml_analcatdata_hiroshima_rate` with
  `openml_analcatdata_hiroshima_rate_dedup`. The five-seed ridge smoke
  completed 60/60 runs and resume returned 60/60 `skipped_completed`. Raw CQR
  has the lowest interval score with coverage 0.9585, `dose_band` gap 0.1081,
  mean width 11.4184, and score 16.2025. Raw CV+ is closest to nominal at
  coverage 0.8985. Dedup CV+ has the lowest score with coverage 0.9250,
  `dose_band` gap 0.1582, mean width 33.9851, and score 35.0310. Fast
  `venn_abers_quantile` undercovers at 0.4969 raw and 0.5417 dedup. The
  follow-on two-seed model-family duplicate-sensitivity sweep completed
  1428/1428 runs across 51 model configurations, two dataset variants, and
  seven conformal methods; a no-force rerun returned 1428/1428
  `skipped_completed` records. Raw random splits are duplicate-contaminated:
  121/130 and 114/130 test rows have exact duplicates in train for seeds 11
  and 23. Dedup splits remove exact duplicate overlap but are tiny at
  72/24/24 rows. Raw best nominal-or-above score is the repeated fixed CQR
  quantile backend with coverage 0.9692, `dose_band` gap 0.0418, mean width
  11.6883, and score 13.1600. Dedup best nominal-or-above score is RBF kernel
  ridge `alpha=1.0, gamma=0.01` with `cv_plus`: coverage 0.9375, gap 0.0982,
  mean width 34.7114, and score 35.5457. Fast `venn_abers_quantile` is
  nominal in 0/51 seed-aggregated rows for both variants. Treat as radiation
  biology benchmark duplicate-sensitivity diagnostics only, not
  protected-class fairness, radiation-risk inference, clinical inference,
  count/exposure model validation, independent raw-split generalization, or
  validated Venn-Abers regression evidence. Broad use still requires
  raw-count versus rate sensitivity, dose inclusion/drop sensitivity,
  alternative dose-band policy, count/exposure baselines, exact/reference
  Venn-Abers diagnostics, and tiny-sample uncertainty treatment.
- `uci_communities_crime`: ecological/proxy smoke and model-family sweep
  complete, headline claims still gated. Rows are communities, not people;
  `racepctblack_bin` is an aggregate composition diagnostic, not an individual
  protected-class label. The runner drops identifiers, raw `racepctblack`, and
  the 84% missing police/LEMAS block from model features, but remaining
  features may still contain demographic proxies and the design is not
  race-blind, proxy-free, or debiased. The three-seed ridge smoke completed
  18/18 runs. The follow-on two-seed model-family sweep completed 714/714
  runs across 51 model configurations and seven conformal methods, and a
  no-force rerun returned 714/714 `skipped_completed`. The sweep's best strict
  nominal-or-above score is CatBoost `depth=2, iterations=120, l2_leaf_reg=3.0,
  learning_rate=0.1` with `normalized_abs`: coverage 0.9048, diagnostic gap
  0.0895, mean width 0.3853, and score 0.5778. The smallest nominal-or-above
  diagnostic gap is elastic net `alpha=0.01, l1_ratio=0.75` with
  `mondrian_abs`: coverage 0.9198, gap 0.0331, mean width 0.4629, and score
  0.6211. CQR is just below strict nominal at coverage 0.8997 and is nominal
  in 0/51 rows; fast `venn_abers_quantile` is nominal in 0/51 rows with mean
  coverage 0.7046. Broad use still requires ecological/proxy sensitivity,
  race-composition feature inclusion/drop sensitivity, spatial or grouped
  holdout design, source/license reuse review, and exact/reference
  Venn-Abers diagnostics.
- `openml_us_crime`: source-mirror gated. This is the OpenML mirror of
  `uci_communities_crime`; retain audit/profile metadata for discovery
  traceability, but do not queue separate runner sweeps or count it as
  independent evidence unless doing explicit loader parity testing.
- `openml_houses_california_variant`: source-variant gated. This is a
  StatLib/Pace-Barry California Housing variant of `openml_california_housing`;
  retain audit/profile metadata for traceability, but do not queue separate
  runner sweeps or count it independently unless doing explicit loader parity
  or missingness-policy sensitivity.
- `openml_california_housing`: iid geographic-proxy smoke and spatial-cell
  diagnostic sweep complete, headline claims still gated. The OpenML frame has
  20,640 rows, target `median_house_value`, 207 missing `total_bedrooms`
  values handled by the runner's train-fitted imputation, 965 rows at the
  `500001` upper target cap/top-code, and `ocean_proximity` diagnostics with
  only five `ISLAND` rows. The three-seed random-split ridge smoke completed
  18/18 runs and resume returned 18/18 `skipped_completed`; CQR has coverage
  0.9029 and fast `venn_abers_quantile` undercovers at 0.5997. The derived
  `openml_california_housing_spatial_cell` variant completed a 52-model,
  14-method, 3-seed spatial-cell holdout sweep with 1,716 completed rows and
  468 controlled jackknife-family skips; all 572 aggregate completed-method
  rows are below nominal coverage. Treat both runs as heteroscedastic interval
  benchmarks with geographic/coastal proxy diagnostics only. They are not
  protected-class fairness evidence; the iid split is not spatial
  generalization evidence, and the spatial-cell split is not a
  location-blind/geography-free or arbitrary-shift exchangeability proof
  because raw latitude and longitude remain model-visible. Broad use still
  requires target-cap sensitivity, endpoint clipping or constrained-support
  policy, sparse `ISLAND` handling, raw-location sensitivity, stronger spatial
  validation, CQR backend sensitivity, and exact/reference Venn-Abers or IVAPD
  diagnostics.
- `aif360_lawschool_gpa`: policy-gated with duplicate sensitivity and
  model-family sweep complete; headline claims remain gated. The raw audit has
  22,342 rows and duplicate rate 5.3%; the deduplicated sensitivity variant
  has 21,157 rows and duplicate rate 0.0%. The three-seed raw-vs-dedup ridge
  smoke completed 36/36 runs. The follow-on two-seed model-family sweep
  completed 1316/1316 runs across raw/dedup variants, 47 model configurations,
  and seven conformal methods; a no-force rerun returned 1316/1316
  `skipped_completed`. Runtime metadata confirms `zfygpa` and primary group
  `race` are dropped from model features while `gender`, `lsat`, and `ugpa`
  remain features, so this is race-primary only under the existing loader
  policy, not a dual-protected-attribute drop study. Raw has 15/329 strict
  nominal-or-above rows, with random forest plus `mondrian_abs` the lowest
  strict nominal score at coverage 0.9006, race gap 0.0127, mean width
  3.0224, and score 3.7883. Dedup has 272/329 strict nominal-or-above rows,
  with ExtraTrees plus `mondrian_abs` the lowest strict nominal score at
  coverage 0.9070, race gap 0.0178, mean width 3.0851, and score 3.7752. Fast
  `venn_abers_quantile` is nominal in 0/94 rows and remains diagnostic only.
  LSAT and UGPA encode upstream selection pipeline effects; broad use still
  requires gender-drop or dual-protected-drop sensitivity, LSAT/UGPA
  inclusion/drop sensitivity, grouped/source provenance review, and
  exact/reference Venn-Abers diagnostics before any paper-level Law School GPA
  claim.
- `fairlearn_acs_income_wy`: transform-gated. `PINCP` is heavily right-skewed.
  The committed log1p sweep is approved only as an unweighted diagnostic method
  sweep on the WY sample. Headline ACS fairness claims still require raw/log
  sensitivity and a documented survey-weight treatment.
- `folktables_acs_poverty_ratio_wy`: unweighted ACS engineering smoke
  complete, headline claims still gated. The audit intentionally disables
  Folktables' predefined `POVPIP < 250` binary target transform and keeps
  continuous `POVPIP`. The runner drops `PWGTP` from model features, keeps
  identity target scale, and reports `RAC1P` diagnostics. The three-seed ridge
  smoke completed six conformal methods: CQR has coverage 0.9313 with the
  lowest interval score 441.8537 and the smallest RAC1P coverage gap 0.3952,
  CV+ is closest to nominal at coverage 0.9031, and fast
  `venn_abers_quantile` undercovers at 0.5608. Broad ACS claims still require
  person weights, replicate-weight uncertainty, top-code behavior, state-panel
  sampling, income-to-poverty universe policy, structural missingness policy,
  and sparse RAC1P handling. The WY audit has p75/p95/p99 all at the 501
  top-code.
- `folktables_acs_travel_time_wy`: unweighted commute-time engineering smoke
  approved, not a survey-weighted ACS commute conclusion. The audit disables
  Folktables' predefined `JWMNP > 20` binary target transform and keeps
  continuous travel time in minutes for the Folktables commuter/employed
  universe. The runner uses `log1p`, `RAC1P` diagnostics, random splits, and
  drops `PWGTP`, high-missing `ESP`, constant `ESR`, and constant `ST` from
  smoke features. The three-seed ridge smoke completed six conformal methods:
  CQR has coverage 0.9150 with the lowest interval score, CV+ is closest to
  nominal at 0.9044, split/Mondrian have the smallest RAC1P coverage gap at
  0.1184, and fast `venn_abers_quantile` undercovers at 0.5784. Broad claims
  still require person weights, replicate weights, top-code sensitivity,
  state-panel sampling, commute-universe policy, and sparse RAC1P handling.
- `openml_cps_85_wages`: transform-gated but smoke-approved. Use `SEX` as the
  primary runner group and keep `RACE`/`AGE` in the audit profile for secondary
  diagnostics. `WAGE` is right-skewed, so log1p smoke runs are approved before
  raw/log sensitivity and any headline wage fairness claim. A two-seed
  model-family sweep now exists for the `log1p` first pass. Runtime metadata
  confirms `WAGE` and `SEX` are dropped while `AGE` and `RACE` remain features,
  so this is not a proxy-free or protected-attribute-free design. CQR rows are
  fixed-backend baselines repeated under outer model labels. Tail-specific
  split rows are tail-allocation diagnostics only, and the endpoint audit shows
  `split_tail_0.25` can produce negative original-scale wage lower endpoints.
  Continue to forbid labor-market causal, population survey, sex/gender
  fairness, wage-gap, raw/log robustness, final model-selection, tail fairness,
  and validated Venn-Abers regression claims.
- `openml_analcatdata_chlamydia`: aggregate-count and transform-gated. Rows are
  Age/Gender/Race strata, not individuals. Use `Gender` only for runner
  grouping, keep `Age` and `Race` in the audit profile, and require raw/log
  sensitivity before interpreting count intervals. A five-seed log1p
  model-family sweep now exists with 3570/3570 completed atomic rows and
  3570/3570 resume skips across 51 model configurations and 14 conformal
  variants. Runtime metadata confirms `Count` and `Gender` are dropped while
  `Age` and `Race` remain features, so this is not a proxy-free or fairness
  design. Strict nominal-or-above rows are 474/714. The lowest strict-nominal
  score is XGBoost with `jackknife_plus_after_bootstrap` at coverage 0.9200,
  `Gender` gap 0.1140, width 8947.0502, and score 14710.2849; treat this as
  an exploratory row, not a final model. Fixed-backend CQR is nominal in 51/51
  rows but is one wide repeated quantile-backend tuple. `normalized_abs` is
  nominal in 51/51 rows but endpoint-audit pathological, including inverse
  saturation and upper endpoints around 1.014e304; do not present it as a
  strong candidate. Fast `venn_abers_quantile` is nominal in 0/51 rows with
  mean coverage 0.6935. Continue to forbid public-health rate, prevalence,
  incidence, population disease-burden, causal, sex/race/age fairness,
  raw/log robustness, final model-selection, and validated Venn-Abers
  regression claims.
- `openml_analcatdata_gsssexsurvey`: sensitive-survey ordinal/count-like smoke
  approved only for the conservative `male_identity_sensitive_proxy_drop`
  variant. Target `AIDS_know` is zero-inflated on a 0 to 4 scale, so identity
  target modeling is diagnostic only, not an ordinal conformal solution.
  `Male` is the primary diagnostic group; raw `Age` is used only to derive
  `age_bin` audit context; `Age`, `Income`, `Sex_partners`,
  `Same_sex_relations`, `Drug_use`, `Religious`, and `Married` are dropped
  before modeling; `age_bin` is excluded from features; the final model feature
  is `Years_of_education`. The five-seed ridge smoke completed 30/30 runs and
  a no-force rerun returned 30/30 `skipped_completed` records. Broader claims
  still require original variable-codebook review, ordinal/bounded target
  sensitivity, sparse sensitive-group reporting, survey-design/weight policy,
  model-family sweeps, and exact/reference Venn-Abers diagnostics.
- `openml_disclosure_z`: privacy/disclosure simulation benchmark smoke only.
  The approved first smoke uses `age_bin` diagnostics derived from raw `Age`,
  drops raw `Age` before modeling, applies `log1p` to target `Income`, and
  models only `Civil` and `Can/US`. The five-seed ridge smoke completed 30/30
  runs across six conformal methods and a no-force rerun returned 30/30
  `skipped_completed` records. CQR is closest to nominal and has the smallest
  average `age_bin` gap, with coverage 0.8857, absolute coverage error 0.0152,
  gap 0.0832, and interval score 112983.57. CV+ has the lowest interval score
  105181.99 with coverage 0.8827. Fast `venn_abers_quantile` undercovers at
  0.6421. This is not fairness evidence, income-survey inference,
  privacy-risk inference, or validated Venn-Abers regression evidence. Broad
  use still requires raw-vs-log1p sensitivity, `Age` inclusion/drop
  sensitivity, variant-family comparison across Z/X_NOISE/X_BIAS/X_TAMPERED,
  source-variable semantics review, nonnegative interval policy, broader
  model-family sweeps, and exact/reference Venn-Abers diagnostics.
- `openml_disclosure_x_bias`: disclosure-variant sensitivity smoke only. The
  approved first smoke uses the same age-bin/log1p/drop-Age policy as
  `openml_disclosure_z`: derive `age_bin` from raw `Age`, drop raw `Age`, apply
  `log1p` to positive `Income`, and model only `Civil` and `Can/US`. The
  five-seed ridge smoke completed 30/30 runs across six conformal methods and
  a no-force rerun returned 30/30 `skipped_completed` records. Mondrian is
  closest to nominal at coverage 0.9083 but has the widest intervals and
  age-bin gap 0.1826. CV+ has the lowest interval score 106517.68 with
  coverage 0.8857, and `normalized_abs` has the smallest average `age_bin` gap
  0.0790 with coverage 0.8932. Fast `venn_abers_quantile` undercovers at
  0.6541. Do not count X_BIAS as independent evidence from the disclosure
  family.
- `openml_disclosure_x_noise`: signed-target disclosure-variant sensitivity
  smoke only. The approved first smoke uses `age_bin` diagnostics derived from
  raw `Age`, drops raw `Age`, models only `Civil` and `Can/US`, and uses
  `signed_log1p` because the released perturbation has four negative `Income`
  rows. Intervals are inverted back to the original signed target scale before
  metrics, and no nonnegative clipping is applied. The five-seed ridge smoke
  completed 30/30 runs across six conformal methods and a no-force rerun
  returned 30/30 `skipped_completed` records. CQR is closest to nominal with
  coverage 0.8902, absolute coverage error 0.0155, gap 0.1006, and interval
  score 142872.69. CV+ has the lowest non-VA interval score 140719.07 with
  coverage 0.8797. Fast `venn_abers_quantile` undercovers at 0.7895 and has
  extreme original-scale mean width 7.5575e11 after signed-log inverse
  transformation. Do not count X_NOISE as independent evidence from the
  disclosure family.
- `openml_disclosure_x_tampered`: signed-target bias-plus-noise
  disclosure-variant sensitivity smoke only. The approved first smoke uses
  `age_bin` diagnostics derived from raw `Age`, drops raw `Age`, models only
  `Civil` and `Can/US`, and uses `signed_log1p` because the released
  perturbation has negative `Income` rows. Intervals are inverted back to the
  original signed target scale before metrics, and no nonnegative clipping is
  applied. The five-seed ridge smoke completed 30/30 runs across six conformal
  methods and a no-force rerun returned 30/30 `skipped_completed` records. CQR
  is closest to nominal and has the lowest interval score, with coverage
  0.8992, age-bin gap 0.1044, mean width 110773.32, and score 140240.33.
  Mondrian is the only above-nominal row at coverage 0.9248 but is much wider,
  with score 196956.69. Fast `venn_abers_quantile` covers 0.8090 and produces
  very wide original-scale intervals after signed-log inverse transformation.
  Do not count X_TAMPERED as independent evidence from the disclosure family.
- `openml_cholesterol_chol`: policy-gated clinical benchmark smoke and first
  controlled model-family sweep complete, headline claims still gated. The
  OpenML frame has 303 rows, target `chol`, no missing targets, no duplicate
  rows, `sex` diagnostics, and an `age_bin` secondary audit group derived from
  raw `age`. The runner drops raw `age`, diagnosis/status field `num`, target
  `chol`, group `sex`, and audit group `age_bin` from model features; `ca` and
  `thal` missing cells are handled by train-fitted imputation. The five-seed
  ridge `log1p` smoke completed 30/30 runs and resume returned 30/30
  `skipped_completed`. The two-seed 32-config model-family sweep completed
  384/384 runs and resume returned 384/384 `skipped_completed`; the summary is
  grouped by `model_params_key`. Among nominal-or-above sweep rows, hist-
  gradient-boosting with `learning_rate=0.03` and `cv_plus` has the lowest
  interval score, coverage 0.9180, sex gap 0.0610, and score 234.25.
  Random_forest depth 8/leaf 1 with `mondrian_abs` has the smallest sweep sex
  gap at 0.0030 with coverage 0.9016. Fast `venn_abers_quantile` undercovers
  in the smoke at 0.6197 and in every sweep model configuration, with mean
  sweep coverage 0.6319 and max 0.7459. The three-seed CQR backend sweep
  completed 27/27 runs and 27/27 resume skips; the best nominal-or-above CQR
  backend is `cqr_gb_deep_n200_d4_lr003` with coverage 0.9071, sex gap
  0.0225, mean width 161.87, and score 225.21. Treat as clinical benchmark
  diagnostics only, not clinical inference, medical decision support evidence,
  population health evidence, sex/gender fairness evidence, final method
  ranking, final CQR backend selection, or validated Venn-Abers regression
  evidence. Broad use still requires raw-vs-log1p target sensitivity, age
  inclusion/drop sensitivity, diagnosis-field sensitivity, original
  source-variable semantics, and CQR backend replication across additional
  datasets.
- `openml_icu_loc`: policy-gated clinical ordinal benchmark smoke only.
  `LOC` is level of consciousness at ICU admission, not length of care. The
  original DASL/OpenML source framing uses `STA` vital status as the dependent
  variable, so the runner drops `STA` as outcome/leakage, drops `ID`, derives
  `age_bin` audit context from `AGE`, drops raw `AGE` and `RAC`, uses `SEX`
  diagnostics, excludes `age_bin` from model features, and applies identity
  target modeling on the bounded 1-3 `LOC` scale. The five-seed ridge smoke
  completed 30/30 runs and 30/30 resume skips. CQR has the lowest
  nominal-or-above interval score with coverage 0.9650, `SEX` gap 0.0282, and
  score 1.9602; CV+ and normalized_abs cover 0.9050; fast
  `venn_abers_quantile` undercovers at 0.8350. Treat as clinical interval
  machinery diagnostics only, not clinical decision support, mortality
  modeling, ICU triage guidance, length-of-stay evidence, sex/gender fairness
  evidence, race fairness evidence, or validated Venn-Abers regression
  evidence. Broad use still requires ordinal target sensitivity,
  source-codebook review for numeric `SEX`/`RAC` codes, raw AGE/RAC
  inclusion/drop sensitivity, clinical leakage review, model-family sweeps,
  sparse-group policy, and exact/reference Venn-Abers diagnostics.
- `fairlearn_diabetes_hospital_los`: clinical bounded-regression smoke only.
  Target `time_in_hospital` is bounded from 1 to 14 and should be treated as
  count/ordinal-like; ordinary numeric intervals are acceptable only for
  runner smoke diagnostics. Single-seed and three-seed repeated ridge smokes
  are complete, including CQR and CV+ in the repeated config. The smoke loader
  drops readmission outcome columns `readmitted`, `readmit_binary`, and
  `readmit_30_days`, but process-of-care variables such as procedures, labs,
  medications, and diagnoses may be post-admission leakage for early-prediction
  framing. Use `race` as the primary smoke group and keep `gender`/`age` in
  the audit profile for secondary review. Unknown/invalid demographic levels
  remain explicit levels;
  do not pool or suppress them before a sparse-group policy is written.
  `max_glu_serum` and `A1Cresult` have high clinically meaningful missingness.
  No broad sweep or paper-ready clinical fairness claim is approved until
  target-scale/count modeling, clinical leakage, high-missingness semantics,
  sparse-group policy, and clinical interpretation gates are upgraded.
- `openml_analcatdata_runshoes`: tiny consumer count-like smoke only. The
  approved first smoke uses `Male` as the primary diagnostic group, drops raw
  `Age`, `Income`, `College`, and `Married` before modeling as demographic/
  socioeconomic proxy fields, applies `log1p` to target `Shoes`, and leaves
  running-behavior/source fields as model features. This also avoids
  train-time imputation of the 23.3333% missing `Income` field in the first
  smoke. The five-seed ridge smoke completed 30/30 runs across six conformal
  methods and a no-force rerun returned 30/30 `skipped_completed` records.
  CQR covers 0.9667 with the smallest `Male` coverage gap 0.0472 and interval
  score 6.2369. CV+ covers 0.8500 with interval score 5.9796. Split,
  Mondrian, and normalized residual intervals cover 0.8167 with gap 0.1916.
  Fast `venn_abers_quantile` undercovers at 0.5667. This is not paper-level
  consumer, sex/gender, socioeconomic, count-model, or validated Venn-Abers
  regression evidence. Broad use still requires primary-source variable
  semantics, `Income` imputation/proxy sensitivity, count/ordinal target
  policy, tiny-sample uncertainty treatment, and broader model-family sweeps.
- `openml_hutsof99_quality`: tiny social-science quality-score smoke only.
  The approved first smoke uses `Gender` as the primary diagnostic group,
  drops raw `Age` before modeling because it is both a sensitive/proxy
  candidate and has Pearson r=0.5697 with target `Quality`, and keeps the
  target on the identity scale. The five-seed ridge smoke completed 30/30 runs
  across six conformal methods and a no-force rerun returned 30/30
  `skipped_completed` records. CV+ is closest to nominal coverage at 0.9000
  with `Gender` coverage gap 0.0841 and interval score 41.7247. Split and
  Mondrian residual intervals have the smallest `Gender` gap at 0.0547 but
  under-cover at 0.8286. `normalized_abs` covers 0.9286 with wider intervals
  and gap 0.1329. CQR covers 0.8429. Fast `venn_abers_quantile` undercovers at
  0.4857. This is not paper-level social-science, psychometric, fairness, or
  validated Venn-Abers regression evidence. Broad use still requires
  primary-source variable semantics, bounded/quality-score interval policy,
  tiny-sample uncertainty treatment, and broader model-family sweeps.
- `openml_kidney_frailty`: survival/frailty source-review only. The target is
  an author-derived random-effect quantity with repeated patient observations;
  keep out of ordinary regression sweeps unless survival/frailty conformal
  methods are explicitly scoped.
- `openml_plasma_retinol`: biomarker benchmark smoke only. The approved first
  smoke uses `SEX` as the primary diagnostic group, derives `age_bin` from
  raw `AGE` for audit traceability, drops raw `AGE` before modeling, excludes
  `age_bin` from model features, drops `BETAPLASMA` as a contemporaneous
  co-analyte/co-outcome field, and applies `log1p` to target `RETPLASMA`. The
  five-seed ridge smoke completed 30/30 runs across six conformal methods and
  a no-force rerun returned 30/30 `skipped_completed` records. CV+ has the
  lowest interval score 844.6949 and is closest to nominal by absolute coverage
  error at coverage 0.9206, but CQR has the smallest average `SEX` coverage
  gap 0.0753 with coverage 0.9556. Fast `venn_abers_quantile` undercovers at
  0.6794. The three-seed CQR backend sweep completed 27/27 runs and 27/27
  resume skips. `cv_plus` remains the lowest-score row overall with coverage
  0.9101 and score 863.79; among CQR backends,
  `cqr_gb_shallow_n240_d2_lr005` has the lowest nominal-or-above score at
  971.79 with coverage 0.9524 and SEX gap 0.0834, while
  `cqr_gb_leaf5_n300_d3_lr005` has the smallest nominal-or-above SEX gap
  0.0594. The two-seed model-family sweep completed 384/384 runs and 384/384
  resume skips across 32 model configurations and six conformal methods. Among
  nominal-or-above rows, ElasticNet `alpha=0.01`, `l1_ratio=0.25` with
  `cv_plus` has the lowest interval score: coverage 0.9524, SEX gap 0.0864,
  width 683.16, score 861.34. Kernel ridge RBF `alpha=0.1`, `gamma=0.01` with
  `cv_plus` has the smallest nominal-or-above SEX gap at 0.0049. CQR is
  nominal for all 32 model configurations, while fast `venn_abers_quantile`
  remains below nominal for all 32. This is not clinical inference, population
  health evidence, cancer-risk evidence, sex/gender fairness evidence, final
  CQR backend selection, final model selection, or validated Venn-Abers
  regression evidence. Broad use still requires raw-vs-log1p sensitivity,
  `AGE` inclusion/drop sensitivity, `BETAPLASMA` co-analyte sensitivity,
  source-variable coding review, nonnegative interval policy,
  stratified/grouped split sensitivity, and exact/reference Venn-Abers
  diagnostics.
- `openml_iq_brain_size_fiq`, `openml_brainsize_mri_count`: sensitive IQ/
  neuroanatomy source-review only. Do not queue until ethical target framing,
  paired-split or missingness policies, and target-derived leakage policies are
  explicit.
- `openml_uscrime_x`, `openml_boston_medv`: aggregate or legacy
  social/geographic benchmarks. Keep source-review only until aggregate proxy,
  leakage, and ethics policies are explicit; Boston Housing must not be
  fairness evidence without a written ethics note.
- `openml_smsa_nox`: aggregate metropolitan air-pollution proxy smoke only.
  The approved smoke derives `nonwhite_bin` from `%NonWhite` for primary
  diagnostics and derives `income_bin` from `income` for secondary audit
  profiling. Raw `%NonWhite`, `income`, `Mortality`, `HCPot`, `NOxPot`, and
  `S02Pot` are dropped before modeling; `income_bin` is also excluded from
  model features. `NOxPot` is target leakage in the source profile with
  Pearson correlation 1.0000 to `NOx`. The current five-seed ridge `log1p`
  smoke is engineering evidence only: it is not individual protected-class
  fairness evidence and not environmental-health inference evidence. Broad use
  still requires spatial/grouped split sensitivity, raw-vs-log1p target
  sensitivity, broader model families, aggregate proxy interpretation, and
  tiny-sample uncertainty treatment.
- `openml_analcatdata_seropositive`: aggregate health count-stratum smoke
  only. The approved first smoke derives `age_bin` from raw `Age`, drops raw
  `Age` and `Total` before modeling, applies `log1p` to the `Positive` count
  target, and leaves `Disease` as the only model feature. `Total` is treated as
  a denominator/exposure variable and not as an ordinary predictor. This is not
  individual fairness, clinical, or population seroprevalence evidence. Broad
  use still requires exposure/offset policy, raw-vs-log1p target sensitivity,
  Total-denominator sensitivity, disease/age policy, source-codebook review,
  and broader model-family sweeps.
- `openml_analcatdata_vehicle_count`: tiny aggregate count-stratum smoke only.
  The approved first smoke uses `Gender` as the primary diagnostic group,
  drops raw `Age`, applies `log1p` to `Count`, and models only
  `Alcohol-related` plus `Type`. Per-seed test splits have only 10 rows, so
  coverage and gap values are smoke diagnostics only. This is not individual
  fairness, traffic-safety, or exposure-adjusted count evidence. Broad use
  still requires source-variable semantics, denominator/exposure policy,
  raw-vs-log1p sensitivity, Age-stratum sensitivity, tiny-sample uncertainty
  treatment, and broader model-family sweeps.
- `openml_bodyfat_percentage`: small anthropometry model-family benchmark
  only. The completed sweep derives `age_bin` from raw `Age`, drops raw `Age`
  and `Density` before modeling, keeps the target on the identity scale, and
  models 12 anthropometric circumference/size features across 51 model
  configurations and 14 conformal variants. `Density` is target-derived
  leakage for this policy because the source audit records Pearson r=-0.9878
  with the body-fat percentage target; this sweep controls leakage by
  exclusion and does not resolve a Density-included sensitivity. The 3570-run
  sweep completed with 508/714 strict nominal-or-above seed-aggregated rows;
  fast `venn_abers_quantile` remains diagnostic-only at 0/51 strict rows.
  Endpoint audit found lower endpoints below zero and upper endpoints above
  the observed 47.5 maximum, though no reconstructed upper endpoint exceeds
  100. This is not population-health, clinical, sex/gender fairness,
  demographic parity, individualized health advice, external-validity,
  production, bounded-interval validity, final model-selection, or validated
  Venn-Abers regression evidence. Broad use still requires bounded-percentage
  clipping policy, Density-inclusion sensitivity, source measurement review,
  and external validation.
- `openml_mba_grade_gpa`: tiny education duplicate-sensitivity smoke only.
  The approved first smoke uses `sex` as the primary diagnostic group, keeps
  target `grade_point_average` on the identity scale, and compares the raw
  61-row frame with a 60-row exact-deduplicated variant. The common feature
  policy excludes `sex` and the target, leaving `GMAT` as the only model
  feature. Per-seed test splits have only 13 raw rows or 12 deduplicated rows,
  so coverage and group-gap values are smoke diagnostics only. The 60-run
  ridge smoke completed across six conformal methods: raw split/Mondrian/
  normalized cover 0.9385 with `sex` gap 0.0764, raw CQR covers 0.9077, dedup
  CQR covers 0.9667 with the smallest `sex` gap 0.0422, and
  `venn_abers_quantile` undercovers at 0.7077 raw and 0.6667 dedup. This is
  not publication-grade education fairness, not an individual sex fairness
  conclusion, and not validated Venn-Abers regression coverage evidence. Broad
  use still requires source-variable semantics for `sex` coding, bounded GPA
  interval clipping/saturation policy, tiny-sample uncertainty treatment,
  source citation review, and broader model-family sweeps.
- `openml_analcatdata_galapagos`: tiny ecological count-regression smoke only.
  The approved first smoke derives `area_bin` from `Area(km^2)`, drops
  `Native.species` before modeling as target-adjacent leakage, applies
  `log1p` to target `Observed.species`, and retains `Elevation(m)` with shared
  numeric imputation despite 16.7% missingness. The common feature policy
  excludes target `Observed.species` and diagnostic group `area_bin`, leaving
  five ecological/geographic numeric features. Per-seed test splits have only
  six rows, so coverage and group-gap values are smoke diagnostics only. This
  is not human fairness, biodiversity-inference, conservation-policy, or
  validated Venn-Abers regression evidence. Broad use still requires
  repeated-split uncertainty, raw-vs-log1p sensitivity, `Native.species`
  leakage sensitivity, area-as-feature policy, alternative ecological groupings,
  and broader model-family sweeps.
- `openml_mercury_in_bass`: tiny environmental concentration smoke only. The
  approved first smoke uses `age_data` as the primary diagnostic group, drops
  `Avg_Mercury`, `min`, and `max` before modeling as target-adjacent mercury
  co-summary leakage, drops `No.samples` as sampling-design metadata, applies
  `log1p` to target `3_yr_Standard_Mercury`, and models only water-chemistry
  fields: `Alkalinity`, `pH`, `Calcium`, and `Chlorophyll`. This is not human
  fairness, environmental-health inference, regulatory evidence, or validated
  Venn-Abers regression evidence. The `age_data=0` group has only 10 full-frame
  rows, so group-gap values are sparse smoke diagnostics only. Broad use still
  requires raw-vs-log1p sensitivity, mercury co-summary inclusion/drop
  sensitivity, `No.samples` sensitivity, alternative water-chemistry groupings,
  nonnegative interval policy, and broader model-family sweeps.
- `openml_sensory_score`: repeated sensory-evaluation benchmark diagnostics
  only. The promoted model-family sweep uses `Method` as the primary
  diagnostic group and `Judges` as the grouped split key. The common feature
  policy excludes target `Score`, diagnostic group `Method`, and split group
  `Judges`, leaving nine categorical design-factor features: `Occasion`,
  `Interval`, `Sittings`, `Position`, `Squares`, `Rows`, `Columns`,
  `Halfplot`, and `Trellis`. All rows are factor-level experimental
  observations, not people-level fairness records. The held-out-judge grouped
  sweep completed 3570/3570 runs and resume returned 3570/3570
  `skipped_completed`; the summary has 714 rows with `coverage_count=5` and
  444 strict nominal-or-above rows. The lowest strict-nominal exploratory
  interval score is SVR `C=0.3, epsilon=0.03, gamma=0.01, kernel=rbf` with
  `jackknife_plus`: coverage 0.9042, `Method` gap 0.0333, mean width 2.9293,
  and score 3.2857. The smallest strict-nominal `Method` gap is histogram
  gradient boosting `l2_regularization=0.0, learning_rate=0.1,
  max_leaf_nodes=15/31` with `split_tail_0.25`: coverage 0.9344, gap 0.00625,
  width 3.3319, and score 3.7701. Fixed-backend CQR is strict nominal in
  51/51 rows with mean coverage 0.9083, but it is the repeated fixed quantile
  backend. `venn_abers_quantile` is strict nominal in 0/51 rows with mean
  coverage 0.6262 and remains diagnostic-only; `venn_abers_split_fallback` is
  strict in 50/51 rows through the ordinary split-envelope fallback, not
  validated Venn-Abers regression. Endpoint reconstruction found bounded
  score-scale overshoot and a pathological `normalized_abs` ExtraTrees
  scale-model failure. This is not protected-class fairness, demographic
  parity, sensory-science inference, wine-quality inference, product-ranking
  evidence, causal evidence, external-validity evidence, production evidence,
  bounded-interval validity, final model selection, or validated Venn-Abers
  regression evidence. Broad use still requires leave-one-judge-out or
  random-effects sensitivity, Method-as-feature sensitivity, factor-design
  leakage review, ordinal/narrow-target interval policy, and exact/reference
  Venn-Abers diagnostics.
- `openml_gascons_consumption`: tiny economic time-series benchmark smoke only.
  The approved first smoke uses deterministic `year`-ordered train/calibration/
  test splitting, derives `income_bin` from `disposable_income`, and drops raw
  `disposable_income` before modeling because the 1984-1986 values show a
  source-scale/semantic break relative to the earlier series. The common feature
  policy excludes target `gasoline_consumption` and group `income_bin`, leaving
  `year`, `price_index_for_casoline`, and `price_index_for_used_cars` as model
  features. The 6-run ridge smoke completed across six conformal methods and
  resume returned 6/6 `skipped_completed`. Split, Mondrian, and normalized
  residual intervals cover 0.8750 with `income_bin` gap 0.3333 and interval
  score 103.9077; CQR also covers 0.8750 but is wider; CV+ covers 0.2500; and
  `venn_abers_quantile` covers 0.6250. This is not protected-class fairness,
  energy-demand inference, gasoline-policy forecasting, or validated
  Venn-Abers regression evidence. Broad use still requires alternative ordered
  cut points, rolling-origin evaluation, raw-income inclusion/drop sensitivity,
  income source-scale review, nonnegative interval policy, broader model-family
  sweeps, and exact/reference Venn-Abers diagnostics.
- `openml_arsenic_female_bladder`, `openml_arsenic_female_lung`,
  `openml_arsenic_male_bladder`, and `openml_arsenic_male_lung`: retain as
  source-review records for the raw event-count variants. The promoted runner
  evidence is the combined `openml_arsenic_event_rate_panel` entry above, not
  separate raw-count runs for each variant.
- `openml_basketball_points_per_minute`: tiny sports-performance benchmark
  with a policy-gated age-bin smoke. Raw `age` is a sensitive/proxy candidate
  and is used only to derive `age_bin`; raw `age` is excluded before modeling.
  The smoke keeps target `points_per_minute` on the identity scale and models
  `assists_per_minute`, `height`, and `time_played`. Treat all rows as smoke
  diagnostics only, not protected-class fairness, player-ranking,
  player-aging, or validated Venn-Abers regression evidence. Broad use still
  requires repeated-split uncertainty, raw-age sensitivity, age-bin policy,
  box-score-derived feature policy, and broader model-family sweeps.
- `oulad_assessment_score`: education assessment source with an approved
  policy-gated student-grouped engineering smoke. Target `score` is a bounded
  0-100 assessment result with p95/p99 at 100. `final_result` is a target
  descendant and stays dropped. `date_submitted` and `is_banked` are excluded
  from the runner until a prediction-time policy is written. The smoke uses
  `disability` diagnostics and holds out whole `id_student` groups; both are
  dropped from model features. `studentVle` clickstream must be modeled only
  through a separate time-aware feature pipeline. Publication-grade claims
  still require temporal assessment cutoff, bounded interval
  clipping/saturation policy, module/presentation sensitivity, and
  student-level interpretation limits.
- `pisa_2022_math_pv_mean`: large-scale assessment benchmark source, not
  PISA-inferential evidence. `MATH_PV_MEAN` is derived from
  `PV1MATH`-`PV10MATH` for profiling and conformal-method prototyping only; it
  is not a single directly observed achievement score. The approved smoke uses
  a deterministic country-balanced sample of up to 75 students per `CNT`
  country/economy, `ST004D01T` diagnostics, and `CNTSCHID` school-grouped
  train/calibration/test splits. `CNTSCHID` is split-only and dropped from
  model features; `W_FSTUWT` and `W_FSTURWT1`-`W_FSTURWT80` are dropped because
  final/replicate weights are not integrated into benchmark metrics. The
  follow-up 51-model-family sweep completed 1,683/2,142 configured rows with
  459 jackknife-family runtime-cap skips. Strict nominal-or-above rows are
  440/561. The lowest strict-nominal exploratory interval score is LightGBM
  with `cv_plus` (coverage 0.9078, `ST004D01T` gap 0.0251, width 223.5469,
  score 273.2703). The smallest strict diagnostic gap is CatBoost with
  `mondrian_abs` (coverage 0.9039, gap 0.0028, width 251.9487, score
  309.2088). Fixed-backend CQR is strict in 51/51 rows with mean coverage
  0.9056 and score 286.8327, but remains a repeated fixed-backend baseline.
  `venn_abers_quantile` undercovers with mean coverage 0.5777 and strict rows
  0/51. Endpoint audit reconstructed 4,100,910 endpoints with zero failures,
  missing artifacts, nonfinite endpoints, crossings, inverse saturation, lower
  endpoints below 0, or upper endpoints above 1000. Publication-grade PISA
  analysis must use all plausible values and combine estimates according to
  PISA methodology. Broad claims remain gated on plausible-value pooling,
  final student weight and 80 replicate-weight handling, country/school
  inference policy, codebook-label documentation for categorical codes,
  endpoint clipping policy for bounded-score claims, CQR backend sensitivity,
  and exact/reference Venn-Abers or IVAPD diagnostics.
- `college_scorecard_2026_median_earnings`: postsecondary institution earnings
  source with an approved policy-gated institution-level proxy model-family
  sweep, not an individual earnings fairness conclusion. Target
  `MD_EARN_WNE_P10` is an institution-level median earnings outcome for
  students working and not enrolled 10 years after entry. The runner reuses the
  audit model-frame builder, keeps observed positive targets only, uses
  `log1p` target modeling, uses `CONTROL` as the primary diagnostic group, and
  holds out whole `STABBR` state/territory groups. All non-target earnings
  fields, debt, repayment, completion, withdrawal, enrollment, death, and
  retention-like fields are excluded as target co-outcomes, target
  descendants, or post-entry outcomes. Minority-serving institution flags,
  student race/ethnicity/gender shares, Pell/low-income/first-generation
  composition, control, region, locale, Carnegie class, and state are
  institution-level proxy diagnostics, not individual protected attributes.
  The current model-family sweep has 2,142 configured rows: 1,377 completed
  rows across nine empirical methods and 765 controlled `skipped_method` rows
  for CV+/jackknife-family runtime caps. The cap-skipped rows are not failed
  fits and not empirical coverage/width evidence for those methods. The
  compact summary has 459 seed-aggregated rows and 388/459 strict
  nominal-or-above rows among completed methods. Endpoint audit reconstructs
  1,567,485 original-scale endpoints with zero failures or missing artifacts,
  but rare lower-below-zero endpoints and extreme upper outliers up to about
  782,361,312.5763 are endpoint-shape caveats. Fast
  `venn_abers_quantile` undercovers with mean coverage 0.6559 and remains
  diagnostic-only; `venn_abers_split_fallback` is an ordinary split-envelope
  fallback, not validated Venn-Abers regression. Publication-grade
  interpretation still requires cohort alignment, privacy-suppression
  handling, timing review for cost/aid and admissions features, raw/log target
  sensitivity, endpoint clipping/nonnegative policy, duplicate sensitivity,
  full-data plus/jackknife design, CQR backend sensitivity, and ecological
  interpretation limits.
- `scf_2022_networth`: household-wealth survey source with an approved
  policy-gated unweighted family-grouped engineering smoke. Target `NETWORTH`
  is family net worth in 2022 dollars and is defined in the Federal Reserve
  Bulletin macro as `ASSET-DEBT`. All balance-sheet asset/debt components,
  mortgage/debt/payment fields, capital-gain/asset fields, net-worth
  percentile/category fields, and direct target descendants are excluded from
  the audit model frame. The runner keeps negative, zero, and positive
  net-worth outcomes; uses `signed_log1p` target modeling; uses `RACECL` as the
  primary diagnostic group; holds out whole `YY1` family groups; excludes
  `WGT`, `RACE`, `RACECL4`, and `RACECL5` from model features; and drops both
  `RACECL` and `YY1` through the common runner feature policy. This does not
  resolve SCF population inference. Five-imputation pooling, `WGT` and 999
  replicate-weight integration, raw-target sensitivity, robust extreme-tail
  treatment, and population wealth interpretation remain required before broad
  claims.
- `nhanes_2017_2018_bmi`: survey biometric source with an approved
  unweighted demographic-only smoke protocol and a policy-gated identity-scale
  model-family sweep. `BMXBMI` is calculated from measured weight and height,
  so `BMXWT` and `BMXHT` stay dropped. `BMXWAIST` and `BMXHIP` are near-target
  body-measure proxies and are excluded from the runner model frame. MEC
  sample weights `WTMEC2YR`, strata `SDMVSTRA`, and PSU `SDMVPSU` are also
  excluded from the runner model frame and not used in metrics. The model-
  family sweep may compare conformal interval behavior across `RIDRETH3`
  diagnostic groups using `RIDAGEYR`, `RIAGENDR`, `INDFMPIR`, `DMDEDUC2`, and
  `DMDMARTL` as features. It must not be described as a population-weighted
  NHANES prevalence, obesity screening/diagnosis, clinical, health-disparity,
  protected-class fairness, or national health estimate. Endpoint audits are
  raw and unclipped and do not establish bounded BMI interval validity.
  Paper-ready use still requires MEC sample-weight/strata/PSU integration,
  age-domain handling, target/item nonresponse adjustment, raw/log target
  sensitivity, endpoint-support policy, and missingness treatment for
  income-to-poverty and adult-only demographics.
- `nhanes_2017_2018_systolic_bp`: survey clinical-measure source with an
  approved unweighted engineering smoke protocol. `SYSBP_MEAN_3` is derived
  from available first-three systolic readings (`BPXSY1`-`BPXSY3`), so all raw
  systolic readings, fourth readings, diastolic readings, and BP measurement-
  process fields stay out of the runner model frame. The current smoke uses
  `RIDRETH3` group diagnostics and features `RIDAGEYR`, `RIAGENDR`,
  `INDFMPIR`, `DMDEDUC2`, and `DMDMARTL`; it excludes MEC weights, strata, and
  PSU from features and metrics. It must not be described as a population-
  weighted or clinical health conclusion. Paper-ready use still requires
  MEC exam-weight policy (`WTMEC2YR`, `SDMVSTRA`, `SDMVPSU`), age-domain
  handling for the 8+ BP exam universe, target-missingness policy for
  incomplete BP exams, and measurement-process leakage review.
- `nhanes_2017_2018_glycohemoglobin`: survey laboratory-biomarker source with
  an approved unweighted engineering smoke protocol. Target `LBXGH` is
  glycohemoglobin percentage for the 12+ eligible lab sample. The current
  smoke drops missing `LBXGH` rows, uses `RIDRETH3` group diagnostics and
  features `RIDAGEYR`, `RIAGENDR`, `INDFMPIR`, `DMDEDUC2`, and `DMDMARTL`,
  and excludes MEC weights, strata, and PSU from features and metrics. It must
  not be described as a population-weighted or clinical biomarker conclusion.
  Paper-ready use still requires lab-item nonresponse policy, age-domain
  handling, MEC exam-weight policy (`WTMEC2YR`, `SDMVSTRA`, `SDMVPSU`),
  target-transform sensitivity for the right tail, and code-label
  documentation before interpretation.
- `stackoverflow_2025_compensation`: self-selected developer-survey
  compensation log1p model-family sweep approved as interval-calibration
  engineering evidence only, not a population compensation estimate.
  `ConvertedCompYearly` is the target, while `CompTotal` and `Currency` are
  target-construction inputs and must stay out of the model frame. The runner
  keeps positive observed targets only, uses `Age` as the primary diagnostic
  group, derives `WorkExp_numeric` and `YearsCode_numeric`, and retains
  `Country`, education, employment, remote-work, developer-type,
  organization-size, industry, AI-selection, Stack Overflow visit frequency,
  and main-branch columns as features/proxies. The public 2025 file does not
  expose gender, race/ethnicity, or disability fields, so all group readings
  are segment/proxy diagnostics only. The 52-model, 14-method, three-seed
  sweep completed 1,404 empirical rows with 780 controlled runtime-cap skips.
  Prediction-metadata leakage audit found 0 violations across 156 bundles.
  Endpoint audit reconstructed all completed rows with 0 missing artifacts,
  0 failures, 0 nonfinite endpoints, and 0 crossings, but raw unclipped
  endpoints include negative lower bounds and upper-tail support flags.
  Raw-target, target-winsor, country-aware, sparse Age-group, and
  missing-compensation sensitivity remain required before any broad
  compensation or developer-population inference.
- `hmda_2025_wy_interest_rate`: fair-lending mortgage pricing source with an
  approved single-state engineering smoke protocol, not a fair-lending
  conclusion. The audit uses official HMDA 2025 Wyoming originated loans
  (`actions_taken=1`) and keeps only positive numeric `interest_rate` targets.
  `Exempt`, blank/non-numeric, and zero targets are dropped for audit profiling
  and smoke modeling. `rate_spread` is a target-adjacent pricing spread and
  must stay out of the model frame; HOEPA status, loan costs, points, fees,
  lender credits, purchaser type, denial reasons, and constant action/year/state
  context are excluded for leakage control. The committed smokes use
  `derived_race` as the primary diagnostic group and either `county_code` or
  `lei` as the split-group column, so train/calibration/test contain disjoint
  geography or lender groups rather than an ordinary iid row split. The runner
  drops both the primary group column and the split-group column from model
  features. Single-seed and five-seed repeated county/LEI smokes are now
  available as engineering evidence only. Broader sweeps or fair-lending
  claims still require sparse protected-group pooling, treatment of
  regulatory-exemption missingness, product/loan-purpose conditioning, stronger
  pricing co-outcome policy, and geography/lender/state sensitivity beyond the
  current Wyoming repeated smokes.
- `meps_2023_total_expenditure`: survey health-expenditure source with an
  approved unweighted policy-gated engineering smoke, not a population-weighted
  MEPS expenditure estimate or clinical fairness conclusion. The audit uses
  official AHRQ MEPS HC-251 2023 Full Year Consolidated public-use data with
  target `TOTEXP23`. Zero annual expenditures are kept as substantive outcomes,
  while missing or negative target codes would be dropped. The smoke reuses the
  audit model-frame builder, uses `log1p` target modeling, uses `RACETHX` as
  the primary diagnostic group, and holds out whole `VARSTR` survey-stratum
  groups. Expenditure components, `TOTSLF23`, and same-year utilization counts
  are target components or co-outcomes and must stay out of the model frame.
  `PERWT23F`, `VARPSU`, and `PANEL` are excluded from smoke model features;
  `VARSTR` is used only for grouped splitting and is dropped from features by
  the runner. MEPS negative special codes are treated as missing for feature
  profiling, but broader sweeps or publication-grade interpretation still
  require separating structural not-in-universe from refused, don't-know, or
  not-ascertained codes. Remaining gates: survey weights and variance design,
  raw/log1p sensitivity, zero-mass or two-part target handling, code-label
  documentation, and clinical/population interpretation limits.
- OpenML ranked source-review completion batch:
  - Numeric `class` targets in `openml_breast_tumor_size`,
    `openml_echo_months_survival`, and `openml_autoprice_class` are
    source-review only until target-name conversion semantics are explicitly
    documented. `openml_fishcatch_weight` is the first policy-gated numeric
    `class` conversion smoke in this batch and now has a 3570-row
    model-family sweep: OpenML target `class` is treated as fish weight in
    grams, `Sex` is dropped because it is missing for 55.1% of rows, `Species`
    is used only for sparse diagnostics, and the runner models `log1p` weight
    from the five morphometric measurement fields. The model-family sweep has
    714 seed-aggregated rows, 654/714 strict nominal-or-above rows, repeated
    fixed-backend CQR, diagnostic-only Venn-Abers variants, and endpoint-shape
    caveats including original-scale negative lower endpoints and large upper
    endpoint overshoot. It remains a morphometric interval benchmark, not
    protected-class fairness evidence, sex-fairness evidence, biological
    inference, species-generalization evidence, fishery/lake population
    inference, fisheries management guidance, final model selection, or
    validated Venn-Abers regression evidence.
  - Survival/censoring datasets `openml_echo_months_survival` and
    `openml_veteran_survival` are out of ordinary regression sweeps until
    censored-survival conformal methods are in scope.
  - Aggregate/spatial/count datasets require explicit row-unit and split
    policies. `openml_space_ga_log_votes_pop` now has a policy-gated aggregate
    smoke using `income_bin` diagnostics and `xcoord_bin` grouped holdouts, but
    it remains non-individual and non-electoral-inference evidence. Raw
    `INCOME`, `XCOORD`, and `YCOORD` are excluded from model features in that
    smoke. `openml_smsa_nox` now has a policy-gated aggregate air-pollution
    smoke using `nonwhite_bin` diagnostics and `income_bin` secondary audit
    profiling, with raw proxy/leakage/co-outcome fields excluded from model
    features. `openml_socmob_sons_occupation` now has a policy-gated aggregate
    count-cell smoke using `race` diagnostics, `log1p` target scale, and a
    first-occupation co-outcome drop; it remains non-individual evidence and
    still needs exposure/offset and source-codebook policy before broader use.
    `openml_house_16h_price` now has a policy-gated aggregate Census
    housing-price smoke using `p14p9_bin` diagnostics derived from opaque
    `P14p9`, `log1p` target modeling, and a raw `P14p9` feature drop. The
    remaining 15 Census-coded numeric features are benchmark features only
    until the source dictionary is resolved. This smoke is not protected-class
    fairness evidence, housing-policy inference, appraisal guidance, or
    census-demographic effect evidence. `openml_house_8l_price` remains a
    source variant of `house_16H`. `openml_analcatdata_hiroshima_cells` remains
    raw-count source-review evidence, while the promoted
    `openml_analcatdata_hiroshima_rate` smoke uses a derived denominator-aware
    rate plus raw-vs-dedup sensitivity.
  - Tiny or repeated-measure datasets such as `openml_sleuth_case1102_tumor`,
    `openml_sleuth_ex1605_age13iq`, and `openml_siddiqi_oz1143` remain
    source-review only until repeated-split, blocked-split, p>>n, and
    sensitive-target policies are written.
    `openml_sensory_score`, `openml_gascons_consumption`,
    `openml_sleuth_case1201_rank`, `openml_sleuth_case1202_experience`, and
    `openml_newton_hema_cells` are the first promotions from this
    tiny/repeated/ordered batch: Sensory uses `Judges` grouped splitting and
    `Method` diagnostics, Gascons uses `year` ordered splitting and
    `income_bin` diagnostics, Sleuth case1201 uses `income_bin` diagnostics
    with raw `income` dropped and retains only aggregate benchmark features,
    Sleuth case1202 uses `fsex` diagnostics with raw `age` plus salary
    co-outcome drops, and Newton Hema uses `id` grouped splitting with
    `weeks_bin` diagnostics, `sample_size` dropped, and `weeks` as the sole
    model feature. `openml_sleuth_ex1714_invol` is now added only as an
    aggregate redlining benchmark smoke: it targets involuntary insurance
    activity, derives `race_bin` diagnostics from ZIP-level percent-minority
    `race`, drops raw `race`, `zip`, and voluntary-insurance co-outcome `vol`,
    and keeps `fire`, `theft`, housing-stock `age`, and median-family-income
    `income` as aggregate benchmark features. All remain smoke-only benchmark
    evidence.
  - Salary/price families `openml_faculty_salaries_asst_prof`,
    `openml_auto_price`, `openml_autoprice_class`, `openml_baseball_*`, and
    BNG auto price are not protected-attribute fairness evidence without a
    separate benchmark protocol and leakage review.
    `openml_faculty_salaries_asst_prof` now has a leakage-control smoke using
    `CIC.institutions` diagnostics, identity-scale `asst.prof.salary`, salary
    co-outcome drops for `average.salary`, `full.prof.salary`, and
    `assoc.prof.salary`, and `University` identity exclusion when present. The
    resulting prediction bundles have zero model features and use a
    `dummy_mean` baseline, so this is interval-machinery evidence only.
    Canonical `openml_auto_price` now has a policy-gated vehicle-price interval
    smoke and a follow-on 3570-row model-family sweep with `symboling`
    insurance-risk diagnostics, `log1p(price)`, target/group exclusion from
    features, and 14 numeric vehicle/loss/performance features. The model-family
    sweep reports 714 seed-aggregated rows, 621/714 strict nominal-or-above
    rows, fixed-backend repeated CQR overcoverage, `venn_abers_quantile`
    undercoverage, and raw-scale endpoint overshoot caveats. This promotion does
    not change the non-fairness, non-insurance-pricing, non-vehicle-valuation,
    and non-independent-variant policy boundary for the price family.
    `openml_baseball_hitter_salary` now has a policy-gated sports salary
    interval smoke with `players_league_at_the_end_of_1986` diagnostics,
    `log1p` target modeling, missing-target rows dropped before splitting, and
    player identity, 1986 team identity, and 1987 beginning roster fields
    excluded from model features. Prediction metadata confirms 18 final model
    features and 157/53/53 train/calibration/test rows per seed. This
    promotion does not make the baseball salary family protected-class
    fairness evidence, labor-market inference, player valuation, or
    player/team ranking evidence.
    `openml_baseball_pitcher_salary` now has the same family-level policy
    boundary with a separate pitcher-specific smoke: `players_league_at_the_end_of_1986`
    diagnostics, `log1p` target modeling, missing-target rows dropped before
    splitting, 1986 team identity and 1987 beginning roster fields excluded
    from model features, and 13 final pitching/career numeric features in
    prediction metadata.
    `openml_baseball_team_salary` is now promoted only as a tiny aggregate
    sports salary interval smoke: `league` diagnostics, `log1p` target
    modeling, `team` identity dropped when present, target/group exclusion,
    and six aggregate model features in prediction metadata. Because it has
    only 26 team rows, it remains high-variance benchmark diagnostics only and
    does not change the non-fairness, non-labor-market, non-valuation, and
    non-ranking boundary for the baseball salary family.
  - OpenML `mtp2` drug-design descriptor benchmark:
    `openml_mtp2_oz1143` is approved and completed only as a
    high-dimensional interval benchmark smoke. OpenML metadata describes
    `mtp2` as one of the drug-design datasets with 1,143 Adriana.Code
    descriptor features. The audit has 274 rows, target `oz1143`, no missing
    targets, no duplicate rows, no sensitive/proxy candidates, and 54
    full-frame constant descriptors. Use `oz2_bin` diagnostics derived from
    the strongest audited target-correlated descriptor `oz2`, drop raw `oz2`
    after group derivation, rely on train-fitted preprocessing to drop
    train-constant descriptors, and model the bounded 0-1 target on the
    identity scale. The ridge alpha-grid smoke completed 84/84 runs with a
    complete no-force resume check. The follow-on model-family sweep completed
    714/714 runs across 51 model configurations, seven conformal methods, and
    seeds 11/23, with a complete no-force resume check. In the sweep, RBF SVR
    `C=1.0, epsilon=0.03, gamma=scale` with `normalized_abs` has the lowest
    nominal-or-above interval score. CQR is nominal in 51/51 repeated
    fixed-backend rows, but those rows use the runner's fixed
    `GradientBoostingRegressor` quantile backend and are not 51 distinct
    base-model CQR evaluations. Fast `venn_abers_quantile` is nominal in 0/51
    configurations. A train-only PCA50 sensitivity panel now also completed
    490/490 runs across 14 model configurations, seven conformal methods, and
    seeds 11/23/47/71/89, with a complete no-force resume check. Prediction
    metadata confirms 1087 train-preprocessed descriptors reduced to 50 PCA
    components with explained variance ratio sum 0.8981 in the sampled
    bundle. PCA50 did not improve the all-descriptor score frontier: its best
    nominal-or-above row is RBF SVR `C=1.0, epsilon=0.03, gamma=scale` with
    `mondrian_abs`, coverage 0.9309, `oz2_bin` gap 0.1623, mean width 0.5691,
    and score 0.6806. A train-only SelectKBest100 sensitivity panel also
    completed 490/490 runs across the same 14 model configurations, seven
    conformal methods, and seeds 11/23/47/71/89, with a complete no-force
    resume check. Sampled prediction metadata confirms 1087
    train-preprocessed descriptors reduced to 100 selected descriptors, with
    no selected `oz2`, `oz2_bin`, or `oz1143`. SelectKBest100 did not improve
    the score frontier: its best nominal-or-above row is RBF SVR
    `C=1.0, epsilon=0.1, gamma=scale` with `normalized_abs`, coverage 0.9127,
    `oz2_bin` diagnostic gap 0.1710, mean width 0.5864, and score 0.7392.
    Its best nominal-or-above diagnostic gap is ridge `alpha=1.0` with
    `split_abs`, coverage 0.9164, gap 0.1277, mean width 0.6778, and score
    0.8328. SelectKBest is fit once on the outer training split; CV+ rows
    operate on this selected representation and are not fold-local supervised
    feature-selection evidence. Treat all frontier rows as post-hoc triage
    signals from small test/group cells, and treat this as high-dimensional
    QSAR interval-machinery and descriptor-representation sensitivity evidence
    only, not protected-class fairness evidence, molecular-design guidance,
    pharmacological inference, drug-safety evidence, final QSAR model
    selection, or validated Venn-Abers regression evidence.
- `uci_bike_sharing`: operational temporal-demand benchmark model-family
  sweep complete, protected-class fairness out of scope. Target `cnt` is a
  right-skewed hourly rental count, so the runner models `log1p(cnt)` and
  reports intervals on the original count scale. Drop `casual` and
  `registered` whenever present because they sum to `cnt`; drop `instant`
  because it is a row identifier. Keep `dteday` only for ordered grouped
  splitting and exclude it from model features. The day-ordered split is train
  2011-01-01 to 2012-03-13, calibration 2012-03-14 to 2012-08-06, and test
  2012-08-07 to 2012-12-31 with no day overlap. The follow-on model-family
  sweep completed 714/714 rows across 51 model configurations, seven conformal
  methods, and seeds 11/23, with a complete no-force resume check. The lowest
  strict nominal-or-above score is XGBoost `max_depth=4, learning_rate=0.1`
  with `normalized_abs`: coverage 0.9060, `season` gap 0.0738, mean width
  239.07, and score 295.48. The smallest strict nominal-or-above season gap is
  SVR `C=1.0, epsilon=0.1, gamma=scale` with `mondrian_abs`: coverage 0.9002,
  gap 0.0063, mean width 494.63, and score 740.91. CQR and CV+ have 0/51
  strict nominal rows; fast `venn_abers_quantile` has mean coverage 0.5021
  and is nominal in 0/51 rows. The ordered split is empirical future-block
  evidence only, not an exchangeability guarantee, production forecasting
  validation, transport policy guidance, or validated Venn-Abers regression
  evidence. Stronger time-series conformal baselines and weather/season
  sensitivity remain follow-ups.
- `uci_wine_quality`: duplicate-sensitivity model-family sweep completed,
  still ordinal/bounded-target gated. The official red and white UCI CSV files
  are merged with a derived `wine_color` diagnostic group. The raw frame has
  6,497 rows, no missing values, and 18.1161% exact duplicate rows; raw random
  splits have duplicate signature overlap across train/calibration/test, so
  raw rows are duplicate-contamination sensitivity evidence. The
  `uci_wine_quality_dedup` variant removes exact duplicates after target and
  `wine_color` attachment, leaving 5,320 rows, 0.0% duplicate rate, and zero
  duplicate signature split overlap; it is a paired sensitivity variant, not
  an independent source dataset. The follow-on 1428-run model-family sweep
  completed across raw and dedup frames with resume confirmed. Raw CV+ is
  strict nominal in 49/51 rows, while fixed-backend CQR is just below nominal
  at coverage 0.8954. Dedup CQR and CV+ are both strict nominal in 51/51 rows;
  dedup lowest strict nominal-or-above score is histogram gradient boosting
  with `cv_plus` at coverage 0.9164 and score 2.9132. Fast
  `venn_abers_quantile` is nominal in 0/102 rows across both variants with
  mean coverage 0.6007. Endpoint audit records unclipped out-of-range bounds
  against the observed 3-9 quality scale, including fast-VA min lower 0.7043
  raw and max upper 10.5739 dedup. Treat this as an ordinal benchmark with
  source-file color diagnostics only, not protected-attribute fairness
  evidence. Broad use still requires bounded/ordinal interval policy,
  clipping/saturation sensitivity, ordinal-regression-aware baselines, and
  duplicate-aware split sensitivity.
- OpenML `disclosure_*` income family: privacy/disclosure simulation and
  variant-sensitivity evidence only.
  The variants are derived from a 662-case survey disclosure simulation with
  `Age`, `Civil`, `Can/US`, and `Income`; `x_noise` and `x_tampered` include
  negative perturbed income values. `z` and `x_bias` have policy-gated age-bin
  `log1p` smokes; `x_noise` and `x_tampered` have policy-gated age-bin
  `signed_log1p` smokes. Never count the four variants as independent
  evidence.
