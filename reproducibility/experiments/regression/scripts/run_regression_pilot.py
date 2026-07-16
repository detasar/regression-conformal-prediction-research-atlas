"""Run resumable regression conformal pilot experiments.

This runner is intentionally conservative: it supports a small audited dataset
set first, writes one checkpoint per atomic run, and appends a compact JSONL
ledger. Long sweeps can reuse the same control flow.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import platform
import subprocess
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Tuple
from urllib.request import urlopen

import numpy as np
import pandas as pd
import sklearn
import yaml
from sklearn.decomposition import PCA
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.kernel_approximation import Nystroem
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import (
    BayesianRidge,
    ElasticNet,
    LogisticRegression,
    QuantileRegressor,
    Ridge,
)
from sklearn.model_selection import KFold, train_test_split
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import make_pipeline
from sklearn.svm import SVR

from cpfi.preprocessing.pipeline import PreprocessingConfig, apply_preprocessing, fit_preprocessing
from cpfi.regression.conformal import (
    conformalized_quantile_interval,
    cv_plus_interval,
    cv_minmax_interval,
    jackknife_after_bootstrap_interval,
    jackknife_plus_interval,
    jackknife_minmax_interval,
    mondrian_conformal_interval,
    normalized_conformal_interval,
    shrinkage_conformal_interval,
    split_conformal_interval,
    split_tail_grid_shortest_interval,
    split_tail_conformal_interval,
    venn_abers_quantile_interval,
    venn_abers_split_fallback_interval,
    weighted_split_conformal_interval,
)
from cpfi.regression.datasets import (
    MISSING_TOKENS,
    audit_regression_frame,
    load_openml_regression_frame,
    render_audit_markdown,
)
from cpfi.regression.experiment import (
    RunRecord,
    append_jsonl,
    atomic_write_json,
    atomic_write_text,
    checkpoint_run,
    load_run_record,
)
from cpfi.regression.metrics import compute_interval_metrics
from cpfi.regression.target import (
    inverse_transform_target_with_metadata,
    transform_target,
)


DATASET_LOADERS = {
    "uci_student_performance": {
        "source": "uci",
        "uci_id": 320,
        "target": "G3",
        "group": "sex",
        "drop_columns": [],
    },
    "uci_student_performance_with_prior_grades": {
        "source": "uci",
        "uci_id": 320,
        "target": "G3",
        "group": "sex",
        "extra_target_columns": ["G1", "G2"],
        "drop_columns": [],
    },
    "uci_student_performance_no_prior_grades": {
        "source": "uci",
        "uci_id": 320,
        "target": "G3",
        "group": "sex",
        "extra_target_columns": ["G1", "G2"],
        "drop_columns": ["G1", "G2"],
    },
    "uci_auto_mpg": {
        "source": "uci",
        "uci_id": 9,
        "target": "mpg",
        "group": "origin",
        "drop_columns": [],
    },
    "uci_wine_quality": {
        "source": "uci_wine_quality_csv",
        "raw_dir": "data/raw/uci/wine_quality",
        "target": "quality",
        "group": "wine_color",
        "drop_columns": [],
    },
    "uci_wine_quality_dedup": {
        "source": "uci_wine_quality_csv",
        "raw_dir": "data/raw/uci/wine_quality",
        "target": "quality",
        "group": "wine_color",
        "deduplicate_rows": True,
        "drop_columns": [],
    },
    "openml_california_housing": {
        "source": "openml",
        "openml_id": 43939,
        "target": "median_house_value",
        "group": "ocean_proximity",
        "drop_columns": [],
    },
    "openml_california_housing_spatial_cell": {
        "source": "openml",
        "openml_id": 43939,
        "target": "median_house_value",
        "group": "ocean_proximity",
        "quantile_groups": [
            {"source_col": "latitude", "group_col": "latitude_bin", "q": 10},
            {"source_col": "longitude", "group_col": "longitude_bin", "q": 10},
        ],
        "interaction_groups": [
            {
                "source_cols": ["latitude_bin", "longitude_bin"],
                "group_col": "spatial_cell",
            }
        ],
        "feature_drop_columns": ["latitude_bin", "longitude_bin", "spatial_cell"],
        "drop_columns": [],
    },
    "openml_cps_85_wages": {
        "source": "openml",
        "openml_id": 534,
        "target": "WAGE",
        "group": "SEX",
        "drop_columns": [],
    },
    "openml_analcatdata_chlamydia": {
        "source": "openml",
        "openml_id": 535,
        "target": "Count",
        "group": "Gender",
        "drop_columns": [],
    },
    "openml_analcatdata_gsssexsurvey": {
        "source": "openml",
        "openml_id": 506,
        "target": "AIDS_know",
        "group": "Male",
        "quantile_groups": [
            {"source_col": "Age", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": [
            "Age",
            "Income",
            "Sex_partners",
            "Same_sex_relations",
            "Drug_use",
            "Religious",
            "Married",
        ],
        "feature_drop_columns": ["age_bin"],
    },
    "openml_cholesterol_chol": {
        "source": "openml",
        "openml_id": 204,
        "target": "chol",
        "group": "sex",
        "quantile_groups": [
            {"source_col": "age", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["age", "num"],
        "feature_drop_columns": ["age_bin"],
    },
    "openml_analcatdata_vehicle_count": {
        "source": "openml",
        "openml_id": 485,
        "target": "Count",
        "group": "Gender",
        "drop_columns": ["Age"],
    },
    "openml_analcatdata_runshoes": {
        "source": "openml",
        "openml_id": 498,
        "target": "Shoes",
        "group": "Male",
        "drop_columns": ["Age", "Income", "College", "Married"],
    },
    "openml_fishcatch_weight": {
        "source": "openml",
        "openml_id": 232,
        "target": "class",
        "group": "Species",
        "drop_columns": ["Sex"],
    },
    "openml_auto_price": {
        "source": "openml",
        "openml_id": 195,
        "target": "price",
        "group": "symboling",
        "drop_columns": [],
    },
    "openml_basketball_points_per_minute": {
        "source": "openml",
        "openml_id": 214,
        "target": "points_per_minute",
        "group": "age_bin",
        "quantile_groups": [
            {"source_col": "age", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["age"],
    },
    "openml_hutsof99_quality": {
        "source": "openml",
        "openml_id": 681,
        "target": "Quality",
        "group": "Gender",
        "drop_columns": ["Age"],
    },
    "openml_mba_grade_gpa": {
        "source": "openml",
        "openml_id": 190,
        "target": "grade_point_average",
        "group": "sex",
        "drop_columns": [],
    },
    "openml_mba_grade_gpa_dedup": {
        "source": "openml",
        "openml_id": 190,
        "target": "grade_point_average",
        "group": "sex",
        "deduplicate_rows": True,
        "drop_columns": [],
    },
    "openml_analcatdata_seropositive": {
        "source": "openml",
        "openml_id": 526,
        "target": "Positive",
        "group": "age_bin",
        "quantile_groups": [
            {"source_col": "Age", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["Age", "Total"],
    },
    "openml_analcatdata_galapagos": {
        "source": "openml",
        "openml_id": 539,
        "target": "Observed.species",
        "group": "area_bin",
        "quantile_groups": [
            {"source_col": "Area(km^2)", "group_col": "area_bin", "q": 4},
        ],
        "drop_columns": ["Native.species"],
    },
    "openml_mercury_in_bass": {
        "source": "openml",
        "openml_id": 1090,
        "target": "3_yr_Standard_Mercury",
        "group": "age_data",
        "drop_columns": ["Avg_Mercury", "min", "max", "No.samples"],
    },
    "openml_mtp2_oz1143": {
        "source": "openml",
        "openml_id": 430,
        "target": "oz1143",
        "group": "oz2_bin",
        "quantile_groups": [
            {"source_col": "oz2", "group_col": "oz2_bin", "q": 4},
        ],
        "drop_columns": ["oz2"],
    },
    "openml_faculty_salaries_asst_prof": {
        "source": "openml",
        "openml_id": 1096,
        "target": "asst.prof.salary",
        "group": "CIC.institutions",
        "drop_columns": [
            "average.salary",
            "full.prof.salary",
            "assoc.prof.salary",
        ],
        "feature_drop_columns": ["University"],
    },
    "openml_baseball_hitter_salary": {
        "source": "openml",
        "openml_id": 525,
        "target": "1987_annual_salary_on_opening_day_in_thousands_of_dollars",
        "group": "players_league_at_the_end_of_1986",
        "drop_columns": [
            "hitters_name",
            "players_team_at_the_end_of_1986",
            "players_league_at_the_beginning_of_1987",
            "players_team_at_the_beginning_of_1987",
        ],
    },
    "openml_baseball_pitcher_salary": {
        "source": "openml",
        "openml_id": 495,
        "target": "1987_annual_salary_on_opening_day_in_thousands_of_dollars",
        "group": "players_league_at_the_end_of_1986",
        "drop_columns": [
            "players_team_at_the_end_of_in_1986",
            "players_league_at_the_beginning_of_1987",
            "players_team_at_the_beginning_of_1987",
        ],
    },
    "openml_baseball_team_salary": {
        "source": "openml",
        "openml_id": 515,
        "target": "1987_average_salary",
        "group": "league",
        "drop_columns": ["team"],
    },
    "openml_house_16h_price": {
        "source": "openml",
        "openml_id": 574,
        "target": "price",
        "group": "p14p9_bin",
        "quantile_groups": [
            {"source_col": "P14p9", "group_col": "p14p9_bin", "q": 4},
        ],
        "drop_columns": ["P14p9"],
    },
    "openml_kin8nm_y": {
        "source": "openml",
        "openml_id": 189,
        "target": "y",
        "group": "theta3_bin",
        "quantile_groups": [
            {"source_col": "theta3", "group_col": "theta3_bin", "q": 4},
        ],
        "drop_columns": ["theta3"],
    },
    "openml_delta_elevators_se": {
        "source": "openml",
        "openml_id": 198,
        "target": "Se",
        "group": "climbRate_bin",
        "quantile_groups": [
            {"source_col": "climbRate", "group_col": "climbRate_bin", "q": 4},
        ],
        "drop_columns": ["climbRate"],
    },
    "openml_arsenic_event_rate_panel": {
        "source": "openml_arsenic_event_rate_panel",
        "target": "event_rate_per_100k",
        "group": "sex",
        "drop_columns": ["events", "at.risk", "group", "openml_id"],
    },
    "openml_analcatdata_hiroshima_rate": {
        "source": "openml_analcatdata_hiroshima_rate",
        "target": "aberrant_rate_per_100",
        "group": "dose_band",
        "drop_columns": ["Aberrant_cells", "Total_cells"],
    },
    "openml_analcatdata_hiroshima_rate_dedup": {
        "source": "openml_analcatdata_hiroshima_rate",
        "target": "aberrant_rate_per_100",
        "group": "dose_band",
        "deduplicate_rows": True,
        "drop_columns": ["Aberrant_cells", "Total_cells"],
    },
    "openml_sleuth_case1202_experience": {
        "source": "openml",
        "openml_id": 706,
        "target": "exper",
        "group": "fsex",
        "quantile_groups": [
            {"source_col": "age", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["age", "bsal", "sal77"],
        "feature_drop_columns": ["age_bin"],
    },
    "openml_sleuth_case1201_rank": {
        "source": "openml",
        "openml_id": 707,
        "target": "rank",
        "group": "income_bin",
        "quantile_groups": [
            {"source_col": "income", "group_col": "income_bin", "q": 4},
        ],
        "drop_columns": ["income"],
    },
    "openml_sleuth_ex1714_invol": {
        "source": "openml",
        "openml_id": 659,
        "target": "invol",
        "group": "race_bin",
        "quantile_groups": [
            {"source_col": "race", "group_col": "race_bin", "q": 4},
        ],
        "drop_columns": ["zip", "race", "vol"],
    },
    "openml_icu_loc": {
        "source": "openml",
        "openml_id": 1097,
        "target": "LOC",
        "group": "SEX",
        "quantile_groups": [
            {"source_col": "AGE", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["ID", "STA", "AGE", "RAC"],
        "feature_drop_columns": ["age_bin"],
    },
    "openml_newton_hema_cells": {
        "source": "openml",
        "openml_id": 492,
        "target": "cells_percentage",
        "group": "weeks_bin",
        "quantile_groups": [
            {"source_col": "weeks", "group_col": "weeks_bin", "q": 4},
        ],
        "drop_columns": ["sample_size"],
    },
    "openml_bodyfat_percentage": {
        "source": "openml",
        "openml_id": 560,
        "target": "class",
        "group": "age_bin",
        "quantile_groups": [
            {"source_col": "Age", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["Age", "Density"],
    },
    "openml_socmob_sons_occupation": {
        "source": "openml",
        "openml_id": 541,
        "target": "counts_for_sons_current_occupation",
        "group": "race",
        "drop_columns": ["counts_for_sons_first_occupation"],
    },
    "openml_space_ga_log_votes_pop": {
        "source": "openml",
        "openml_id": 507,
        "target": "ln(VOTES/POP)",
        "group": "income_bin",
        "quantile_groups": [
            {"source_col": "INCOME", "group_col": "income_bin", "q": 4},
            {"source_col": "XCOORD", "group_col": "xcoord_bin", "q": 10},
        ],
        "drop_columns": ["INCOME"],
        "feature_drop_columns": ["XCOORD", "YCOORD"],
    },
    "openml_smsa_nox": {
        "source": "openml",
        "openml_id": 1091,
        "target": "NOx",
        "group": "nonwhite_bin",
        "quantile_groups": [
            {"source_col": "%NonWhite", "group_col": "nonwhite_bin", "q": 4},
            {"source_col": "income", "group_col": "income_bin", "q": 4},
        ],
        "drop_columns": [
            "%NonWhite",
            "income",
            "Mortality",
            "HCPot",
            "NOxPot",
            "S02Pot",
        ],
        "feature_drop_columns": ["income_bin"],
    },
    "openml_sensory_score": {
        "source": "openml",
        "openml_id": 546,
        "target": "Score",
        "group": "Method",
        "drop_columns": [],
    },
    "openml_gascons_consumption": {
        "source": "openml",
        "openml_id": 226,
        "target": "gasoline_consumption",
        "group": "income_bin",
        "quantile_groups": [
            {"source_col": "disposable_income", "group_col": "income_bin", "q": 4},
        ],
        "drop_columns": ["disposable_income"],
    },
    "openml_plasma_retinol": {
        "source": "openml",
        "openml_id": 511,
        "target": "RETPLASMA",
        "group": "SEX",
        "quantile_groups": [
            {"source_col": "AGE", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["AGE", "BETAPLASMA"],
        "feature_drop_columns": ["age_bin"],
    },
    "openml_disclosure_z": {
        "source": "openml",
        "openml_id": 699,
        "target": "Income",
        "group": "age_bin",
        "quantile_groups": [
            {"source_col": "Age", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["Age"],
    },
    "openml_disclosure_x_noise": {
        "source": "openml",
        "openml_id": 704,
        "target": "Income",
        "group": "age_bin",
        "quantile_groups": [
            {"source_col": "Age", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["Age"],
    },
    "openml_disclosure_x_tampered": {
        "source": "openml",
        "openml_id": 676,
        "target": "Income",
        "group": "age_bin",
        "quantile_groups": [
            {"source_col": "Age", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["Age"],
    },
    "openml_disclosure_x_bias": {
        "source": "openml",
        "openml_id": 709,
        "target": "Income",
        "group": "age_bin",
        "quantile_groups": [
            {"source_col": "Age", "group_col": "age_bin", "q": 4},
        ],
        "drop_columns": ["Age"],
    },
    "aif360_lawschool_gpa": {
        "source": "aif360_lawschool_gpa",
        "target": "zfygpa",
        "group": "race",
        "binary_race": True,
        "drop_columns": [],
    },
    "aif360_lawschool_gpa_dedup": {
        "source": "aif360_lawschool_gpa",
        "target": "zfygpa",
        "group": "race",
        "binary_race": True,
        "deduplicate_rows": True,
        "drop_columns": [],
    },
    "fairlearn_acs_income_wy": {
        "source": "fairlearn_acs_income",
        "states": ["WY"],
        "target": "PINCP",
        "group": "SEX",
        "drop_columns": [],
    },
    "folktables_acs_travel_time_wy": {
        "source": "folktables_acs_travel_time_wy",
        "raw_dir": "data/raw/folktables",
        "target": "JWMNP",
        "group": "RAC1P",
        "drop_columns": ["PWGTP", "ESP", "ESR", "ST"],
    },
    "folktables_acs_poverty_ratio_wy": {
        "source": "folktables_acs_poverty_ratio_wy",
        "raw_dir": "data/raw/folktables",
        "target": "POVPIP",
        "group": "RAC1P",
        "drop_columns": ["PWGTP"],
    },
    "fairlearn_diabetes_hospital_los": {
        "source": "fairlearn_diabetes_hospital_los",
        "target": "time_in_hospital",
        "group": "race",
        "drop_columns": ["readmitted", "readmit_binary", "readmit_30_days"],
    },
    "nhanes_2017_2018_bmi": {
        "source": "nhanes_2017_2018_bmi",
        "raw_dir": "data/raw/nhanes/2017-2018",
        "target": "BMXBMI",
        "group": "RIDRETH3",
        "keep_columns": [
            "BMXBMI",
            "RIDAGEYR",
            "RIAGENDR",
            "RIDRETH3",
            "INDFMPIR",
            "DMDEDUC2",
            "DMDMARTL",
        ],
        "drop_columns": [],
    },
    "nhanes_2017_2018_systolic_bp": {
        "source": "nhanes_2017_2018_systolic_bp",
        "raw_dir": "data/raw/nhanes/2017-2018",
        "target": "SYSBP_MEAN_3",
        "group": "RIDRETH3",
        "drop_columns": [],
    },
    "nhanes_2017_2018_glycohemoglobin": {
        "source": "nhanes_2017_2018_glycohemoglobin",
        "raw_dir": "data/raw/nhanes/2017-2018",
        "target": "LBXGH",
        "group": "RIDRETH3",
        "drop_columns": [],
    },
    "stackoverflow_2025_compensation": {
        "source": "stackoverflow_2025_compensation",
        "raw_dir": "data/raw/stackoverflow/2025",
        "target": "ConvertedCompYearly",
        "group": "Age",
        "keep_columns": [
            "ConvertedCompYearly",
            "Age",
            "Country",
            "EdLevel",
            "Employment",
            "WorkExp_numeric",
            "YearsCode_numeric",
            "DevType",
            "OrgSize",
            "RemoteWork",
            "Industry",
            "MainBranch",
            "AISelect",
            "SOVisitFreq",
        ],
        "drop_columns": [],
    },
    "hmda_2025_wy_interest_rate": {
        "source": "hmda_2025_wy_interest_rate",
        "raw_dir": "data/raw/hmda/2025",
        "target": "interest_rate",
        "group": "derived_race",
        "drop_columns": [],
    },
    "college_scorecard_2026_median_earnings": {
        "source": "college_scorecard_2026_median_earnings",
        "raw_dir": "data/raw/college_scorecard/2026-06-10",
        "target": "MD_EARN_WNE_P10",
        "group": "CONTROL",
        "drop_columns": [],
    },
    "meps_2023_total_expenditure": {
        "source": "meps_2023_total_expenditure",
        "raw_dir": "data/raw/meps/2023",
        "target": "TOTEXP23",
        "group": "RACETHX",
        "drop_columns": ["PERWT23F", "VARPSU", "PANEL"],
    },
    "scf_2022_networth": {
        "source": "scf_2022_networth",
        "raw_dir": "data/raw/scf/2022",
        "target": "NETWORTH",
        "group": "RACECL",
        "drop_columns": ["WGT", "RACE", "RACECL4", "RACECL5"],
    },
    "oulad_assessment_score": {
        "source": "oulad_assessment_score",
        "raw_dir": "data/raw/oulad",
        "target": "score",
        "group": "disability",
        "drop_columns": ["date_submitted", "is_banked"],
    },
    "pisa_2022_math_pv_mean": {
        "source": "pisa_2022_math_pv_mean",
        "raw_dir": "data/raw/pisa/2022",
        "target": "MATH_PV_MEAN",
        "group": "ST004D01T",
        "sample_per_country": 75,
        "sample_seed": 20260625,
        "split_group_col": "CNTSCHID",
        "drop_columns": [
            "W_FSTUWT",
            *[f"W_FSTURWT{i}" for i in range(1, 81)],
        ],
    },
    "uci_bike_sharing": {
        "source": "uci",
        "uci_id": 275,
        "target": "cnt",
        "group": "season",
        "drop_columns": ["instant", "casual", "registered"],
        "feature_drop_columns": ["dteday"],
    },
    "uci_communities_crime": {
        "source": "uci",
        "uci_id": 183,
        "target": "ViolentCrimesPerPop",
        "group": "racepctblack_bin",
        "group_quantile_source": "racepctblack",
        "group_quantiles": 4,
        "drop_columns": [
            "state",
            "county",
            "community",
            "communityname",
            "fold",
            "racepctblack",
            "LemasSwornFT",
            "LemasSwFTPerPop",
            "LemasSwFTFieldOps",
            "LemasSwFTFieldPerPop",
            "LemasTotalReq",
            "LemasTotReqPerPop",
            "PolicReqPerOffic",
            "PolicPerPop",
            "RacialMatchCommPol",
            "PctPolicWhite",
            "PctPolicBlack",
            "PctPolicHisp",
            "PctPolicAsian",
            "PctPolicMinor",
            "OfficAssgnDrugUnits",
            "NumKindsDrugsSeiz",
            "PolicAveOTWorked",
            "PolicCars",
            "PolicOperBudg",
            "LemasPctPolicOnPatr",
            "LemasGangUnitDeploy",
            "PolicBudgPerPop",
        ],
    },
}

DATASET_LOADER_SCHEMA = "cpfi_regression_dataset_loader_v2"
RUNTIME_PROVENANCE_SCHEMA = "cpfi_regression_runtime_provenance_v2"
RUNTIME_PROVENANCE_RELEVANT_PATH_PREFIXES = (
    "cpfi/",
    "experiments/regression/catalogs/",
    "experiments/regression/configs/",
    "experiments/regression/method_specs/",
    "experiments/regression/policies/",
    "experiments/regression/scripts/",
    "tests/",
    "pyproject.toml",
    "requirements",
    "environment",
    "setup.cfg",
    "setup.py",
)
RUNTIME_PROVENANCE_PATH_SAMPLE_LIMIT = 50
_RUNTIME_PROVENANCE_CACHE: Dict[str, Any] | None = None


DUPLICATE_CLUSTER_SPLIT_COL = "__cpfi_duplicate_cluster_split_group__"
DUPLICATE_CLUSTER_SCOPES = {
    "model_visible_features",
    "model_visible_features_plus_target",
    "row_signature",
}


class MethodSkipped(RuntimeError):
    """Raised when a configured method is intentionally skipped for a run."""


RESUME_SKIP_STATUSES = {"skipped_completed", "skipped_failed", "skipped_skipped_method"}
TERMINAL_CHECKPOINT_STATUSES = {"completed", "failed", "skipped_method"}


@dataclass(frozen=True)
class PredictionBundle:
    """Cached split, preprocessing, model prediction, and scale arrays."""

    artifact_id: str
    artifact_dir: Path
    cache_status: str
    fit_seconds: float
    y_train: np.ndarray
    y_cal: np.ndarray
    y_test: np.ndarray
    yhat_train: np.ndarray
    yhat_cal: np.ndarray
    yhat_test: np.ndarray
    groups_cal: np.ndarray
    groups_test: np.ndarray
    split_groups_train: np.ndarray | None
    X_train: np.ndarray
    X_cal: np.ndarray
    X_test: np.ndarray
    X_train_pre_feature_reducer: np.ndarray | None
    X_cal_pre_feature_reducer: np.ndarray | None
    X_test_pre_feature_reducer: np.ndarray | None
    scale_cal: np.ndarray
    scale_test: np.ndarray
    target_transform: str
    preprocessed_feature_names: List[str]
    X_train_raw: pd.DataFrame | None = None
    X_test_raw: pd.DataFrame | None = None

    @property
    def artifact_paths(self) -> Dict[str, str]:
        return {
            "prediction_bundle": str(self.artifact_dir / "bundle.npz"),
            "prediction_metadata": str(self.artifact_dir / "metadata.json"),
        }


def default_config_path() -> str:
    """Return a config path that works in both source and public package layouts."""

    source_layout = Path("experiments/regression/configs/pilot.yaml")
    if source_layout.exists():
        return source_layout.as_posix()
    packaged_layout = Path(__file__).resolve().parents[1] / "configs" / "pilot.yaml"
    return packaged_layout.as_posix()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=default_config_path(),
        help="Regression experiment YAML config.",
    )
    parser.add_argument("--max-runs", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite completed checkpoints.")
    parser.add_argument("--dataset", action="append", default=None, help="Dataset id filter.")
    parser.add_argument("--model-id", action="append", default=None, help="Model id filter.")
    parser.add_argument("--cp-method", action="append", default=None, help="CP method filter.")
    parser.add_argument("--seed", action="append", type=int, default=None, help="Seed filter.")
    parser.add_argument("--alpha", action="append", type=float, default=None, help="Alpha filter.")
    return parser.parse_args()


def load_uci_frame(
    uci_id: int,
    target: str,
    extra_target_columns: Iterable[str] = (),
) -> pd.DataFrame:
    from ucimlrepo import fetch_ucirepo

    dataset = fetch_ucirepo(id=uci_id)
    df = dataset.data.features.copy()
    targets = dataset.data.targets.copy()
    if target not in targets.columns:
        raise ValueError(f"target {target!r} not found in UCI dataset {uci_id}")
    for column in extra_target_columns:
        column = str(column)
        if column == target:
            continue
        if column not in targets.columns:
            raise ValueError(f"target column {column!r} not found in UCI dataset {uci_id}")
        df[column] = targets[column]
    df[target] = targets[target]
    return df


ARSENIC_EVENT_RATE_SOURCES = (
    (533, "female", "bladder"),
    (513, "female", "lung"),
    (482, "male", "bladder"),
    (536, "male", "lung"),
)


def load_openml_arsenic_event_rate_panel(target: str) -> pd.DataFrame:
    """Combine four OpenML arsenic event-count variants into an exposure rate frame."""

    if target != "event_rate_per_100k":
        raise ValueError(f"Arsenic panel target must be 'event_rate_per_100k', got {target!r}")

    frames = []
    for openml_id, sex, cancer_site in ARSENIC_EVENT_RATE_SOURCES:
        frame = load_openml_regression_frame(openml_id, "events").copy()
        required = {"group", "conc", "age", "at.risk", "events"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(f"OpenML arsenic dataset {openml_id} missing columns: {missing}")
        events = pd.to_numeric(frame["events"], errors="raise").astype(float)
        at_risk = pd.to_numeric(frame["at.risk"], errors="raise").astype(float)
        if (at_risk <= 0).any():
            raise ValueError(f"OpenML arsenic dataset {openml_id} has nonpositive at.risk")
        frame["sex"] = sex
        frame["cancer_site"] = cancer_site
        frame["openml_id"] = openml_id
        frame[target] = events / at_risk * 100000.0
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _hiroshima_dose_band(dose: pd.Series) -> pd.Series:
    """Map the seven source dose levels into stable diagnostic strata."""

    numeric = pd.to_numeric(dose, errors="raise")
    return pd.Series(
        np.select(
            [
                numeric <= 38.0,
                numeric <= 244.1,
                numeric > 244.1,
            ],
            [
                "low_0_38",
                "mid_144_244",
                "high_347_667",
            ],
            default="missing",
        ),
        index=dose.index,
        dtype="object",
    )


def load_openml_hiroshima_rate_frame(target: str) -> pd.DataFrame:
    """Load OpenML Hiroshima and derive aberrant cells per 100 scored cells."""

    if target != "aberrant_rate_per_100":
        raise ValueError(
            f"Hiroshima target must be 'aberrant_rate_per_100', got {target!r}"
        )
    frame = load_openml_regression_frame(494, "Aberrant_cells").copy()
    required = {"Dose", "Total_cells", "Aberrant_cells"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"OpenML Hiroshima dataset missing columns: {missing}")
    total_cells = pd.to_numeric(frame["Total_cells"], errors="raise").astype(float)
    if (total_cells <= 0).any():
        raise ValueError("OpenML Hiroshima dataset has nonpositive Total_cells")
    aberrant_cells = pd.to_numeric(frame["Aberrant_cells"], errors="raise").astype(float)
    frame["dose_band"] = _hiroshima_dose_band(frame["Dose"])
    frame[target] = aberrant_cells / total_cells * 100.0
    return frame


def atomic_download(url: str, destination: Path) -> None:
    """Download a small source file through an atomic rename."""

    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with urlopen(url, timeout=60) as response:
            with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent) as tmp:
                tmp.write(response.read())
                tmp_path = Path(tmp.name)
        os.replace(tmp_path, destination)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
        raise


def load_uci_wine_quality_frame(raw_dir: str, target: str) -> pd.DataFrame:
    """Load official UCI red/white Wine Quality CSVs with an explicit color group."""

    if target != "quality":
        raise ValueError(f"Wine Quality target must be 'quality', got {target!r}")
    sources = {
        "red": "https://archive.ics.uci.edu/ml/machine-learning-databases/wine-quality/winequality-red.csv",
        "white": "https://archive.ics.uci.edu/ml/machine-learning-databases/wine-quality/winequality-white.csv",
    }
    frames = []
    raw_root = Path(raw_dir)
    for color, url in sources.items():
        local_path = raw_root / f"winequality-{color}.csv"
        atomic_download(url, local_path)
        frame = pd.read_csv(local_path, sep=";")
        frame.columns = [str(col).strip().lower().replace(" ", "_") for col in frame.columns]
        if target not in frame.columns:
            raise ValueError(f"target {target!r} not found in {local_path}")
        frame["wine_color"] = color
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def load_aif360_lawschool_frame(target: str, binary_race: bool) -> pd.DataFrame:
    from aif360.sklearn.datasets import fetch_lawschool_gpa

    X, y = fetch_lawschool_gpa(subset="all", binary_race=binary_race)
    df = X.reset_index(drop=True).copy()
    if target != y.name:
        raise ValueError(f"target {target!r} does not match Law School target {y.name!r}")
    df[target] = y.reset_index(drop=True).astype(float)
    return df


def load_fairlearn_acs_income_frame(states: List[str], target: str) -> pd.DataFrame:
    from fairlearn.datasets import fetch_acs_income

    bunch = fetch_acs_income(states=states, as_frame=True)
    if target != bunch.target.name:
        raise ValueError(f"target {target!r} does not match ACS target {bunch.target.name!r}")
    return bunch.frame.copy()


def load_folktables_acs_task_wy_frame(
    raw_dir: str,
    target: str,
    task_name: str,
) -> pd.DataFrame:
    """Load an audited Folktables ACS WY custom-regression smoke frame."""

    try:
        from audit_folktables_acs_custom_regression import build_task_specs
    except ModuleNotFoundError:
        from experiments.regression.scripts.audit_folktables_acs_custom_regression import (
            build_task_specs,
        )

    raw_path = Path(raw_dir) / "2018" / "1-Year" / "psam_p56.csv"
    if not raw_path.exists():
        raise FileNotFoundError(
            "Folktables ACS WY raw PUMS file is not in the ignored local cache: "
            f"{raw_path}"
        )
    spec = build_task_specs()[task_name]
    if target != spec.target:
        raise ValueError(f"target {target!r} does not match Folktables target {spec.target!r}")

    raw = pd.read_csv(raw_path)
    universe = spec.preprocess(raw.copy())
    selected_columns = []
    for column in [*spec.features, *spec.extra_context_columns, spec.target, spec.group]:
        if column in universe.columns and column not in selected_columns:
            selected_columns.append(column)
    df = universe.loc[:, selected_columns].copy()
    df[target] = pd.to_numeric(df[target], errors="coerce")
    return df.loc[df[target].notna()].copy()


def load_folktables_acs_travel_time_wy_frame(raw_dir: str, target: str) -> pd.DataFrame:
    """Load the audited Folktables ACS WY continuous travel-time smoke frame."""

    return load_folktables_acs_task_wy_frame(raw_dir, target, "travel_time")


def load_folktables_acs_poverty_ratio_wy_frame(raw_dir: str, target: str) -> pd.DataFrame:
    """Load the audited Folktables ACS WY continuous poverty-ratio smoke frame."""

    return load_folktables_acs_task_wy_frame(raw_dir, target, "poverty_ratio")


def load_fairlearn_diabetes_hospital_los_frame(target: str) -> pd.DataFrame:
    from fairlearn.datasets import fetch_diabetes_hospital

    bunch = fetch_diabetes_hospital(as_frame=True)
    df = bunch.frame.copy()
    if target not in df.columns:
        raise ValueError(f"target {target!r} not found in Fairlearn diabetes frame")
    return df


def load_nhanes_2017_2018_bmi_frame(raw_dir: str, target: str) -> pd.DataFrame:
    """Load the audited NHANES BMI smoke frame from ignored local XPT cache."""

    raw_path = Path(raw_dir)
    demo_path = raw_path / "DEMO_J.XPT"
    bmx_path = raw_path / "BMX_J.XPT"
    missing = [str(path) for path in [demo_path, bmx_path] if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "NHANES BMI raw files are not in the ignored local cache: "
            + ", ".join(missing)
        )
    demo = pd.read_sas(demo_path)
    bmx = pd.read_sas(bmx_path)
    df = demo.merge(bmx, on="SEQN", how="inner")
    if target not in df.columns:
        raise ValueError(f"target {target!r} not found in NHANES BMI frame")
    return df.loc[df[target].notna()].copy()


def load_nhanes_2017_2018_systolic_bp_frame(raw_dir: str, target: str) -> pd.DataFrame:
    """Load the audited unweighted NHANES mean systolic BP smoke frame."""

    try:
        from audit_nhanes_systolic_bp import build_model_frame, load_joined_frame
    except ModuleNotFoundError:
        from experiments.regression.scripts.audit_nhanes_systolic_bp import (
            build_model_frame,
            load_joined_frame,
        )

    df = build_model_frame(
        load_joined_frame(Path(raw_dir)),
        include_survey_design=False,
    )
    if target not in df.columns:
        raise ValueError(f"target {target!r} not found in NHANES systolic BP frame")
    return df.copy()


def load_nhanes_2017_2018_glycohemoglobin_frame(
    raw_dir: str,
    target: str,
) -> pd.DataFrame:
    """Load the audited unweighted NHANES glycohemoglobin smoke frame."""

    try:
        from audit_nhanes_glycohemoglobin import build_model_frame, load_joined_frame
    except ModuleNotFoundError:
        from experiments.regression.scripts.audit_nhanes_glycohemoglobin import (
            build_model_frame,
            load_joined_frame,
        )

    df = build_model_frame(
        load_joined_frame(Path(raw_dir)),
        include_survey_design=False,
    )
    if target not in df.columns:
        raise ValueError(
            f"target {target!r} not found in NHANES glycohemoglobin frame"
        )
    return df.copy()


def parse_stackoverflow_numeric_response(series: pd.Series) -> pd.Series:
    """Parse Stack Overflow year-count responses used by the compensation audit."""

    replacements = {
        "Less than 1 year": 0.5,
        "More than 50 years": 51,
        "Prefer not to say": np.nan,
    }
    return pd.to_numeric(series.replace(replacements), errors="coerce")


def load_stackoverflow_2025_compensation_frame(raw_dir: str, target: str) -> pd.DataFrame:
    """Load the audited Stack Overflow 2025 compensation smoke frame."""

    raw_path = Path(raw_dir)
    results_path = raw_path / "results.csv"
    schema_path = raw_path / "schema.csv"
    missing = [str(path) for path in [results_path, schema_path] if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Stack Overflow 2025 raw files are not in the ignored local cache: "
            + ", ".join(missing)
        )
    header = pd.read_csv(results_path, nrows=0).columns.tolist()
    source_columns = [
        column
        for column in [
            target,
            "Age",
            "Country",
            "EdLevel",
            "Employment",
            "WorkExp",
            "YearsCode",
            "DevType",
            "OrgSize",
            "RemoteWork",
            "Industry",
            "MainBranch",
            "AISelect",
            "SOVisitFreq",
        ]
        if column in header
    ]
    df = pd.read_csv(results_path, usecols=source_columns, low_memory=False)
    if target not in df.columns:
        raise ValueError(f"target {target!r} not found in Stack Overflow 2025 frame")
    df[target] = pd.to_numeric(df[target], errors="coerce")
    if "WorkExp" in df.columns:
        df["WorkExp_numeric"] = parse_stackoverflow_numeric_response(df["WorkExp"])
    if "YearsCode" in df.columns:
        df["YearsCode_numeric"] = parse_stackoverflow_numeric_response(df["YearsCode"])
    df = df.loc[df[target].notna() & (df[target] > 0)].copy()
    return df.drop(columns=["WorkExp", "YearsCode"], errors="ignore")


def load_hmda_2025_wy_interest_rate_frame(raw_dir: str, target: str) -> pd.DataFrame:
    """Load the audited HMDA 2025 Wyoming interest-rate smoke frame."""

    try:
        from audit_hmda_2025_wy_interest_rate import build_model_frame, load_source_frame
    except ModuleNotFoundError:
        from experiments.regression.scripts.audit_hmda_2025_wy_interest_rate import (
            build_model_frame,
            load_source_frame,
        )

    source = load_source_frame(Path(raw_dir))
    df, _target_filter = build_model_frame(source)
    if target not in df.columns:
        raise ValueError(f"target {target!r} not found in HMDA 2025 WY frame")
    return df.copy()


def load_college_scorecard_2026_median_earnings_frame(
    raw_dir: str,
    target: str,
) -> pd.DataFrame:
    """Load the audited College Scorecard institution median-earnings frame."""

    try:
        from audit_college_scorecard_2026_earnings import (
            build_model_frame,
            load_source_frame,
        )
    except ModuleNotFoundError:
        from experiments.regression.scripts.audit_college_scorecard_2026_earnings import (
            build_model_frame,
            load_source_frame,
        )

    source, _header = load_source_frame(Path(raw_dir))
    df, _target_filter = build_model_frame(source)
    if target not in df.columns:
        raise ValueError(f"target {target!r} not found in College Scorecard frame")
    return df.copy()


def load_meps_2023_total_expenditure_frame(raw_dir: str, target: str) -> pd.DataFrame:
    """Load the audited MEPS HC-251 total-expenditure smoke frame."""

    try:
        from audit_meps_2023_total_expenditure import (
            build_model_frame,
            load_source_frame,
        )
    except ModuleNotFoundError:
        from experiments.regression.scripts.audit_meps_2023_total_expenditure import (
            build_model_frame,
            load_source_frame,
        )

    source, _labels = load_source_frame(Path(raw_dir))
    df, _target_filter = build_model_frame(source)
    if target not in df.columns:
        raise ValueError(f"target {target!r} not found in MEPS HC-251 frame")
    return df.copy()


def load_scf_2022_networth_frame(raw_dir: str, target: str) -> pd.DataFrame:
    """Load the audited SCF 2022 net-worth engineering-smoke frame."""

    try:
        from audit_scf_2022_networth import build_model_frame, load_source_frame
    except ModuleNotFoundError:
        from experiments.regression.scripts.audit_scf_2022_networth import (
            build_model_frame,
            load_source_frame,
        )

    source, _header = load_source_frame(Path(raw_dir))
    df, _target_filter = build_model_frame(source)
    if target not in df.columns:
        raise ValueError(f"target {target!r} not found in SCF 2022 frame")
    if "YY1" not in source.columns:
        raise ValueError("SCF 2022 frame requires YY1 for family-grouped splitting")
    df = df.copy()
    df["YY1"] = source.loc[df.index, "YY1"].to_numpy()
    return df


def load_oulad_assessment_score_frame(raw_dir: str, target: str) -> pd.DataFrame:
    """Load the audited OULAD assessment-score engineering-smoke frame."""

    try:
        from audit_oulad_assessment_score import build_model_frame, load_joined_tables
    except ModuleNotFoundError:
        from experiments.regression.scripts.audit_oulad_assessment_score import (
            build_model_frame,
            load_joined_tables,
        )

    joined = load_joined_tables(Path(raw_dir))
    df = build_model_frame(joined, include_split_columns=True)
    if target not in df.columns:
        raise ValueError(f"target {target!r} not found in OULAD assessment frame")
    if "id_student" not in df.columns:
        raise ValueError("OULAD assessment frame requires id_student for grouped splitting")
    return df.copy()


def load_pisa_2022_math_pv_mean_frame(
    raw_dir: str,
    target: str,
    sample_per_country: int,
    sample_seed: int,
) -> pd.DataFrame:
    """Load a deterministic PISA 2022 math PV-mean benchmark-smoke frame."""

    try:
        from audit_pisa_2022_math import build_model_frame, load_student_frame
    except ModuleNotFoundError:
        from experiments.regression.scripts.audit_pisa_2022_math import (
            build_model_frame,
            load_student_frame,
        )

    student = load_student_frame(Path(raw_dir))
    df = build_model_frame(student)
    if target not in df.columns:
        raise ValueError(f"target {target!r} not found in PISA 2022 math frame")
    if "CNTSCHID" not in student.columns:
        raise ValueError("PISA 2022 frame requires CNTSCHID for school-grouped splitting")
    df = df.copy()
    df["CNTSCHID"] = student.loc[df.index, "CNTSCHID"].astype("object").to_numpy()
    if sample_per_country > 0 and "CNT" in df.columns:
        samples = [
            group.sample(
                n=min(sample_per_country, len(group)),
                random_state=sample_seed,
            )
            for _country, group in df.groupby("CNT", dropna=False, sort=False)
        ]
        df = pd.concat(samples, axis=0).sort_index()
    return df.reset_index(drop=True)


def add_quantile_group(
    df: pd.DataFrame,
    source_col: str,
    group_col: str,
    q: int,
) -> pd.DataFrame:
    if source_col not in df.columns:
        raise ValueError(f"group quantile source {source_col!r} not found")
    df = df.copy()
    source = pd.to_numeric(df[source_col], errors="coerce")
    binned = pd.qcut(source, q=q, duplicates="drop")
    labels = binned.astype("object").where(binned.notna(), "missing")
    df[group_col] = pd.Series(
        [str(value) for value in labels],
        index=df.index,
        dtype=object,
    )
    return df


def add_interaction_group(
    df: pd.DataFrame,
    source_cols: Iterable[str],
    group_col: str,
    separator: str = "|",
) -> pd.DataFrame:
    """Create a string group by crossing already-derived group columns."""

    cols = [str(col) for col in source_cols]
    if not cols:
        raise ValueError("source_cols must contain at least one column")
    missing = [col for col in cols if col not in df.columns]
    if missing:
        raise ValueError(f"source_cols {missing!r} not found for interaction group")
    df = df.copy()
    values = (
        df[cols]
        .astype("object")
        .where(df[cols].notna(), "missing")
        .astype(str)
    )
    df[group_col] = values.agg(separator.join, axis=1)
    return df


def load_dataset_frame(dataset_id: str) -> Tuple[pd.DataFrame, str, str]:
    if dataset_id not in DATASET_LOADERS:
        raise ValueError(f"Unsupported pilot dataset: {dataset_id}")
    spec = DATASET_LOADERS[dataset_id]
    target = spec["target"]
    if spec["source"] == "uci":
        df = load_uci_frame(
            spec["uci_id"],
            target,
            extra_target_columns=spec.get("extra_target_columns", []),
        )
    elif spec["source"] == "uci_wine_quality_csv":
        df = load_uci_wine_quality_frame(str(spec["raw_dir"]), target)
    elif spec["source"] == "openml":
        df = load_openml_regression_frame(spec["openml_id"], target)
    elif spec["source"] == "openml_arsenic_event_rate_panel":
        df = load_openml_arsenic_event_rate_panel(target)
    elif spec["source"] == "openml_analcatdata_hiroshima_rate":
        df = load_openml_hiroshima_rate_frame(target)
    elif spec["source"] == "aif360_lawschool_gpa":
        df = load_aif360_lawschool_frame(target, bool(spec.get("binary_race", True)))
    elif spec["source"] == "fairlearn_acs_income":
        df = load_fairlearn_acs_income_frame(list(spec["states"]), target)
    elif spec["source"] == "folktables_acs_travel_time_wy":
        df = load_folktables_acs_travel_time_wy_frame(str(spec["raw_dir"]), target)
    elif spec["source"] == "folktables_acs_poverty_ratio_wy":
        df = load_folktables_acs_poverty_ratio_wy_frame(str(spec["raw_dir"]), target)
    elif spec["source"] == "fairlearn_diabetes_hospital_los":
        df = load_fairlearn_diabetes_hospital_los_frame(target)
    elif spec["source"] == "nhanes_2017_2018_bmi":
        df = load_nhanes_2017_2018_bmi_frame(str(spec["raw_dir"]), target)
    elif spec["source"] == "nhanes_2017_2018_systolic_bp":
        df = load_nhanes_2017_2018_systolic_bp_frame(str(spec["raw_dir"]), target)
    elif spec["source"] == "nhanes_2017_2018_glycohemoglobin":
        df = load_nhanes_2017_2018_glycohemoglobin_frame(
            str(spec["raw_dir"]), target
        )
    elif spec["source"] == "stackoverflow_2025_compensation":
        df = load_stackoverflow_2025_compensation_frame(str(spec["raw_dir"]), target)
    elif spec["source"] == "hmda_2025_wy_interest_rate":
        df = load_hmda_2025_wy_interest_rate_frame(str(spec["raw_dir"]), target)
    elif spec["source"] == "college_scorecard_2026_median_earnings":
        df = load_college_scorecard_2026_median_earnings_frame(
            str(spec["raw_dir"]), target
        )
    elif spec["source"] == "meps_2023_total_expenditure":
        df = load_meps_2023_total_expenditure_frame(str(spec["raw_dir"]), target)
    elif spec["source"] == "scf_2022_networth":
        df = load_scf_2022_networth_frame(str(spec["raw_dir"]), target)
    elif spec["source"] == "oulad_assessment_score":
        df = load_oulad_assessment_score_frame(str(spec["raw_dir"]), target)
    elif spec["source"] == "pisa_2022_math_pv_mean":
        df = load_pisa_2022_math_pv_mean_frame(
            str(spec["raw_dir"]),
            target,
            sample_per_country=int(spec.get("sample_per_country", 0)),
            sample_seed=int(spec.get("sample_seed", 20260625)),
        )
    else:
        raise ValueError(f"Unsupported source: {spec['source']}")

    with pd.option_context("future.no_silent_downcasting", True):
        df = df.replace(list(MISSING_TOKENS), np.nan)
    df = df.infer_objects(copy=False)
    if spec.get("deduplicate_rows"):
        df = df.drop_duplicates().reset_index(drop=True)
    if "group_quantile_source" in spec:
        df = add_quantile_group(
            df,
            source_col=str(spec["group_quantile_source"]),
            group_col=str(spec["group"]),
            q=int(spec.get("group_quantiles", 4)),
        )
    for quantile_group in spec.get("quantile_groups", []):
        df = add_quantile_group(
            df,
            source_col=str(quantile_group["source_col"]),
            group_col=str(quantile_group["group_col"]),
            q=int(quantile_group.get("q", 4)),
        )
    for interaction_group in spec.get("interaction_groups", []):
        df = add_interaction_group(
            df,
            source_cols=interaction_group["source_cols"],
            group_col=str(interaction_group["group_col"]),
            separator=str(interaction_group.get("separator", "|")),
        )
    if "keep_columns" in spec:
        keep_columns = [str(col) for col in spec["keep_columns"]]
        missing_keep = [col for col in keep_columns if col not in df.columns]
        if missing_keep:
            raise ValueError(f"Dataset {dataset_id} missing keep_columns: {missing_keep}")
        df = df.loc[:, keep_columns].copy()
    drop_columns = [col for col in spec.get("drop_columns", []) if col in df.columns]
    if drop_columns:
        df = df.drop(columns=drop_columns)
    return df, target, spec["group"]


def runner_feature_drop_columns(
    dataset_id: str,
    target: str,
    group_col: str,
    split_group_col: str | None,
    frame: pd.DataFrame,
    base_split_group_col: str | None = None,
) -> List[str]:
    """Columns removed before fitting the regression model."""
    feature_drop = [target]
    for column in [group_col, split_group_col, base_split_group_col]:
        if column is not None:
            feature_drop.append(str(column))
    for column in DATASET_LOADERS.get(dataset_id, {}).get("feature_drop_columns", []):
        feature_drop.append(str(column))
    return [column for column in dict.fromkeys(feature_drop) if column in frame.columns]


def model_visible_signature_series(
    frame: pd.DataFrame,
    *,
    dataset_id: str,
    target: str,
    group_col: str,
    split_group_col: str | None,
    scope: str,
) -> pd.Series:
    if scope not in DUPLICATE_CLUSTER_SCOPES:
        raise ValueError(
            f"unsupported duplicate_cluster_scope {scope!r}; expected one of "
            f"{sorted(DUPLICATE_CLUSTER_SCOPES)}"
        )
    if scope == "row_signature":
        drop_columns = []
    else:
        drop_columns = runner_feature_drop_columns(
            dataset_id,
            target,
            group_col,
            split_group_col,
            frame,
        )
        if scope == "model_visible_features_plus_target":
            drop_columns = [column for column in drop_columns if column != target]
    comparable = frame.drop(
        columns=[column for column in drop_columns if column in frame.columns]
    )
    comparable = comparable.reindex(sorted(comparable.columns), axis=1)
    comparable = comparable.astype("object").where(comparable.notna(), "__missing__")
    return pd.util.hash_pandas_object(comparable, index=False).astype(str)


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        if item not in self.parent:
            self.parent[item] = item
            return item
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def duplicate_cluster_labels(
    frame: pd.DataFrame,
    *,
    dataset_id: str,
    target: str,
    group_col: str,
    split_group_col: str | None,
    scope: str,
) -> pd.Series:
    signatures = model_visible_signature_series(
        frame,
        dataset_id=dataset_id,
        target=target,
        group_col=group_col,
        split_group_col=split_group_col,
        scope=scope,
    )
    if split_group_col is None:
        return signatures.map(lambda value: f"dup:{value}")
    split_group_col = str(split_group_col)
    if split_group_col not in frame.columns:
        raise ValueError(f"split_group_col {split_group_col!r} not found")
    split_groups = (
        frame[split_group_col]
        .astype("object")
        .where(frame[split_group_col].notna(), "__missing__")
        .astype(str)
    )
    union_find = _UnionFind()
    for group_value, signature in zip(split_groups, signatures):
        union_find.union(f"group:{group_value}", f"dup:{signature}")
    roots = [union_find.find(f"group:{value}") for value in split_groups]
    root_to_label = {
        root: f"component:{index:08d}"
        for index, root in enumerate(sorted(set(roots)))
    }
    return pd.Series([root_to_label[root] for root in roots], index=frame.index)


def add_duplicate_cluster_split_group(
    frame: pd.DataFrame,
    *,
    dataset_id: str,
    target: str,
    group_col: str,
    split_group_col: str | None,
    scope: str | None,
) -> tuple[pd.DataFrame, str | None]:
    if scope is None:
        return frame, split_group_col
    if DUPLICATE_CLUSTER_SPLIT_COL in frame.columns:
        raise ValueError(f"reserved split column already present: {DUPLICATE_CLUSTER_SPLIT_COL}")
    working = frame.copy()
    working[DUPLICATE_CLUSTER_SPLIT_COL] = duplicate_cluster_labels(
        working,
        dataset_id=dataset_id,
        target=target,
        group_col=group_col,
        split_group_col=split_group_col,
        scope=str(scope),
    )
    return working, DUPLICATE_CLUSTER_SPLIT_COL


def expand_grid(grid: Dict) -> Iterator[Dict]:
    keys = list(grid)
    values = [grid[key] for key in keys]
    for combo in itertools.product(*values):
        yield dict(zip(keys, combo))


def iter_model_configs(config: Dict) -> Iterator[Tuple[str, str, Dict]]:
    for model in config["models"]:
        model_id = model["model_id"]
        family = model["family"]
        for params in expand_grid(model["grid"]):
            yield model_id, family, params


def stable_run_id(payload: Dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def dataframe_fingerprint(df: pd.DataFrame) -> Dict[str, Any]:
    comparable = df.reindex(sorted(df.columns), axis=1)
    comparable = comparable.astype("object").where(comparable.notna(), "__missing__")
    row_hashes = pd.util.hash_pandas_object(comparable, index=True).to_numpy(
        dtype=np.uint64,
        copy=False,
    )
    digest = hashlib.sha256()
    digest.update(row_hashes.tobytes())
    digest.update(
        json.dumps(
            {
                "columns": list(comparable.columns),
                "dtypes": {column: str(df[column].dtype) for column in comparable.columns},
                "shape": [int(df.shape[0]), int(df.shape[1])],
            },
            sort_keys=True,
        ).encode("utf-8")
    )
    return {
        "schema": "cpfi_dataframe_fingerprint_v1",
        "row_count": int(df.shape[0]),
        "column_count": int(df.shape[1]),
        "columns_sha256": hashlib.sha256(
            json.dumps(list(comparable.columns), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "frame_sha256": digest.hexdigest(),
    }


def git_output(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def git_value(args: list[str]) -> str | None:
    value = git_output(args)
    if value is None:
        return None
    value = value.strip()
    return value or None


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _porcelain_paths(raw_path: str) -> List[str]:
    path = raw_path.strip()
    if " -> " in path:
        parts = path.split(" -> ")
    else:
        parts = [path]
    return [part.strip().strip('"').lstrip("./") for part in parts if part.strip()]


def _parse_porcelain_status(status: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        status_code = line[:2].strip() or line[:2]
        for path in _porcelain_paths(line[3:]):
            rows.append({"status": status_code, "path": path})
    return rows


def _unique_ordered(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _runtime_relevant_dirty_path(path: str) -> bool:
    return path.startswith(RUNTIME_PROVENANCE_RELEVANT_PATH_PREFIXES)


def runtime_provenance() -> Dict[str, Any]:
    global _RUNTIME_PROVENANCE_CACHE
    if _RUNTIME_PROVENANCE_CACHE is not None:
        return dict(_RUNTIME_PROVENANCE_CACHE)

    status_all = git_output(["status", "--porcelain", "--untracked-files=all"]) or ""
    status_tracked = git_output(["status", "--porcelain", "--untracked-files=no"]) or ""
    diff_stat = git_output(["diff", "--stat"]) or ""
    diff_name_status = git_output(["diff", "--name-status"]) or ""
    diff_patch = git_output(["diff", "--binary"]) or ""

    status_rows = _parse_porcelain_status(status_all)
    tracked_status_rows = _parse_porcelain_status(status_tracked)
    dirty_paths = _unique_ordered(row["path"] for row in status_rows)
    tracked_dirty_paths = _unique_ordered(row["path"] for row in tracked_status_rows)
    untracked_paths = _unique_ordered(
        row["path"] for row in status_rows if row["status"] == "??"
    )
    relevant_dirty_paths = [
        path for path in dirty_paths if _runtime_relevant_dirty_path(path)
    ]
    relevant_diff_patch = ""
    if relevant_dirty_paths:
        relevant_diff_patch = (
            git_output(["diff", "--binary", "--", *relevant_dirty_paths]) or ""
        )

    dirty_digest = sha256_text(
        "\n".join(
            [
                "schema=runtime_dirty_digest_v2",
                "[status_all]",
                status_all,
                "[status_tracked]",
                status_tracked,
                "[diff_stat]",
                diff_stat,
                "[diff_name_status]",
                diff_name_status,
                "[diff_patch]",
                diff_patch,
                "[relevant_diff_patch]",
                relevant_diff_patch,
            ]
        )
    )
    _RUNTIME_PROVENANCE_CACHE = {
        "schema": RUNTIME_PROVENANCE_SCHEMA,
        "git_commit": git_value(["rev-parse", "--short=12", "HEAD"]),
        "git_dirty": bool(status_all),
        "git_dirty_tracked": bool(status_tracked),
        "git_dirty_digest": dirty_digest,
        "git_dirty_status_sha256": sha256_text(status_all),
        "git_dirty_tracked_status_sha256": sha256_text(status_tracked),
        "git_dirty_stat_sha256": sha256_text(diff_stat),
        "git_dirty_name_status_sha256": sha256_text(diff_name_status),
        "git_dirty_patch_sha256": sha256_text(diff_patch),
        "git_relevant_dirty_patch_sha256": sha256_text(relevant_diff_patch),
        "git_dirty_path_count": len(dirty_paths),
        "git_tracked_dirty_path_count": len(tracked_dirty_paths),
        "git_untracked_path_count": len(untracked_paths),
        "git_relevant_dirty_path_count": len(relevant_dirty_paths),
        "git_dirty_path_samples": dirty_paths[:RUNTIME_PROVENANCE_PATH_SAMPLE_LIMIT],
        "git_untracked_path_samples": untracked_paths[
            :RUNTIME_PROVENANCE_PATH_SAMPLE_LIMIT
        ],
        "git_relevant_dirty_paths": relevant_dirty_paths,
        "untracked_content_policy": (
            "untracked_path_names_recorded_but_untracked_file_contents_not_hashed"
        ),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "sklearn_version": sklearn.__version__,
    }
    return dict(_RUNTIME_PROVENANCE_CACHE)


def cp_method_settings(config: Dict | None, cp_method: str) -> Tuple[str, Dict]:
    """Return the base method id and method-specific params for a run label."""

    if config is None:
        return str(cp_method), {}
    method_configs = config.get("cp_method_configs", {})
    entry = None
    if isinstance(method_configs, dict):
        entry = method_configs.get(str(cp_method))
    elif isinstance(method_configs, list):
        for candidate in method_configs:
            if str(candidate.get("label", candidate.get("method_id"))) == str(cp_method):
                entry = candidate
                break
    if not entry:
        return str(cp_method), {}
    method_id = str(entry.get("method_id", cp_method))
    params = dict(entry.get("params", {}))
    return method_id, params


def run_payload(
    dataset_id: str,
    model_id: str,
    model_params: Dict,
    cp_method: str,
    alpha: float,
    seed: int,
    config: Dict | None = None,
) -> Dict:
    payload = {
        "dataset_id": dataset_id,
        "model_id": model_id,
        "model_params": model_params,
        "cp_method": cp_method,
        "alpha": alpha,
        "seed": seed,
    }
    if config is not None:
        split_config = config.get("splits", {})
        split_group_col = split_config.get("group_col")
        split_strategy = split_config.get("strategy")
        split_order_col = split_config.get("order_col")
        source_target_col = split_config.get("source_target_col")
        source_values = split_config.get("source_values")
        target_values = split_config.get("target_values")
        covariate_shift_policy_id = split_config.get("covariate_shift_policy_id")
        duplicate_cluster_scope = split_config.get("duplicate_cluster_scope")
        target_transform = target_transform_for_dataset(config, dataset_id)
        run_context = {
            "schema": "regression_run_context_v2",
            "target_transform": target_transform,
            "primary_group_col": DATASET_LOADERS.get(dataset_id, {}).get("group"),
            "splits": {
                "train": float(split_config["train"]),
                "calibration": float(split_config["calibration"]),
                "test": 1.0
                - float(split_config["train"])
                - float(split_config["calibration"]),
                "group_col": None if split_group_col is None else str(split_group_col),
            },
        }
        if split_strategy is not None:
            run_context["splits"]["strategy"] = str(split_strategy)
        if split_order_col is not None:
            run_context["splits"]["order_col"] = str(split_order_col)
        if source_target_col is not None:
            run_context["splits"]["source_target_col"] = str(source_target_col)
        if source_values is not None:
            run_context["splits"]["source_values"] = [str(item) for item in source_values]
        if target_values is not None:
            run_context["splits"]["target_values"] = [str(item) for item in target_values]
        if covariate_shift_policy_id is not None:
            run_context["splits"]["covariate_shift_policy_id"] = str(
                covariate_shift_policy_id
            )
        if duplicate_cluster_scope is not None:
            run_context["splits"]["duplicate_cluster_scope"] = str(
                duplicate_cluster_scope
            )
            run_context["splits"]["duplicate_cluster_split_col"] = (
                DUPLICATE_CLUSTER_SPLIT_COL
            )
        feature_drop_columns = DATASET_LOADERS.get(dataset_id, {}).get(
            "feature_drop_columns",
            [],
        )
        if feature_drop_columns:
            run_context["feature_drop_columns"] = [str(col) for col in feature_drop_columns]
        reducer_config = feature_reducer_config(config)
        if reducer_config["method"] not in {"none", ""}:
            run_context["feature_reducer"] = reducer_config
        method_id, method_params = cp_method_settings(config, cp_method)
        if method_id != str(cp_method) or method_params:
            run_context["cp_method"] = {
                "label": str(cp_method),
                "method_id": method_id,
                "params": method_params,
            }
        payload["run_context"] = run_context
    return payload


def failed_result_from_exception(
    run: Tuple,
    checkpoint_root: Path,
    exc: Exception,
    config: Dict | None = None,
) -> Dict:
    dataset_id, model_id, model_family, model_params, cp_method, alpha, seed = run
    payload = run_payload(
        dataset_id, model_id, model_params, cp_method, alpha, seed, config=config
    )
    run_id = stable_run_id(payload)
    cp_method_id, cp_method_params = cp_method_settings(config, cp_method)
    trace = traceback.format_exc()
    error_type = type(exc).__name__
    error_message = str(exc)
    record = RunRecord(
        run_id=run_id,
        dataset_id=dataset_id,
        model_id=model_id,
        cp_method=cp_method,
        split_seed=seed,
        alpha=alpha,
        status="failed",
        artifact_paths={},
        metrics={},
        notes=(
            f"family={model_family}; params={json.dumps(model_params, sort_keys=True)}; "
            f"cp_method_id={cp_method_id}; "
            f"cp_params={json.dumps(cp_method_params, sort_keys=True)}; "
            f"error_type={error_type}; error_message={error_message}; "
            f"traceback_tail={trace[-6000:]}"
        ),
    )
    checkpoint_path = checkpoint_run(checkpoint_root, record)
    return {
        "status": "failed",
        "run_id": run_id,
        "dataset_id": dataset_id,
        "model_id": model_id,
        "model_family": model_family,
        "model_params": model_params,
        "cp_method": cp_method,
        "cp_method_id": cp_method_id,
        "cp_method_params": cp_method_params,
        "alpha": alpha,
        "seed": seed,
        "error_type": error_type,
        "error_message": error_message,
        "traceback_tail": trace[-6000:],
        "checkpoint": str(checkpoint_path),
    }


def prediction_artifact_dir(cache_root: Path, artifact_id: str) -> Path:
    return cache_root / artifact_id[:2] / artifact_id


def _atomic_save_npz(path: Path, arrays: Dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".npz", dir=path.parent, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        np.savez_compressed(tmp_path, **arrays)
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def load_prediction_bundle(cache_root: Path, artifact_id: str) -> PredictionBundle | None:
    artifact_dir = prediction_artifact_dir(cache_root, artifact_id)
    bundle_path = artifact_dir / "bundle.npz"
    metadata_path = artifact_dir / "metadata.json"
    if not bundle_path.exists() or not metadata_path.exists():
        return None

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("artifact_id") != artifact_id:
        return None
    if not isinstance(metadata.get("data_provenance"), dict):
        return None
    if not isinstance(metadata.get("code_provenance"), dict):
        return None
    with np.load(bundle_path, allow_pickle=False) as data:
        return PredictionBundle(
            artifact_id=artifact_id,
            artifact_dir=artifact_dir,
            cache_status="hit",
            fit_seconds=float(metadata.get("fit_seconds", 0.0)),
            y_train=data["y_train"],
            y_cal=data["y_cal"],
            y_test=data["y_test"],
            yhat_train=data["yhat_train"],
            yhat_cal=data["yhat_cal"],
            yhat_test=data["yhat_test"],
            groups_cal=data["groups_cal"].astype(str),
            groups_test=data["groups_test"].astype(str),
            split_groups_train=(
                data["split_groups_train"].astype(str)
                if "split_groups_train" in data.files
                else None
            ),
            X_train=data["X_train"],
            X_cal=data["X_cal"],
            X_test=data["X_test"],
            X_train_pre_feature_reducer=(
                data["X_train_pre_feature_reducer"]
                if "X_train_pre_feature_reducer" in data.files
                else None
            ),
            X_cal_pre_feature_reducer=(
                data["X_cal_pre_feature_reducer"]
                if "X_cal_pre_feature_reducer" in data.files
                else None
            ),
            X_test_pre_feature_reducer=(
                data["X_test_pre_feature_reducer"]
                if "X_test_pre_feature_reducer" in data.files
                else None
            ),
            scale_cal=data["scale_cal"],
            scale_test=data["scale_test"],
            target_transform=str(metadata.get("target_transform", "identity")),
            preprocessed_feature_names=[
                str(name) for name in metadata.get("preprocessed_feature_names", [])
            ],
            X_train_raw=None,
            X_test_raw=None,
        )


def write_prediction_bundle(
    cache_root: Path,
    artifact_id: str,
    metadata: Dict,
    arrays: Dict[str, np.ndarray],
) -> Path:
    artifact_dir = prediction_artifact_dir(cache_root, artifact_id)
    _atomic_save_npz(artifact_dir / "bundle.npz", arrays)
    atomic_write_json(artifact_dir / "metadata.json", metadata)
    return artifact_dir


def make_model(model_id: str, params: Dict, seed: int):
    params = dict(params)
    if model_id == "dummy_mean":
        params.setdefault("strategy", "mean")
        return DummyRegressor(**params)
    if model_id == "ridge":
        return Ridge(**params)
    if model_id == "elasticnet":
        params.setdefault("max_iter", 20000)
        params.setdefault("random_state", seed)
        return ElasticNet(**params)
    if model_id == "bayesian_ridge":
        return BayesianRidge(**params)
    if model_id == "svr":
        return SVR(**params)
    if model_id == "kernel_ridge":
        return KernelRidge(**params)
    if model_id == "knn":
        return KNeighborsRegressor(**params)
    if model_id == "random_forest":
        params.setdefault("n_jobs", -1)
        params.setdefault("random_state", seed)
        return RandomForestRegressor(**params)
    if model_id == "extra_trees":
        params.setdefault("n_jobs", -1)
        params.setdefault("random_state", seed)
        return ExtraTreesRegressor(**params)
    if model_id == "hist_gradient_boosting":
        params.setdefault("random_state", seed)
        return HistGradientBoostingRegressor(**params)
    if model_id == "xgboost":
        from xgboost import XGBRegressor

        params.setdefault("n_jobs", -1)
        params.setdefault("objective", "reg:squarederror")
        params.setdefault("random_state", seed)
        params.setdefault("tree_method", "hist")
        params.setdefault("verbosity", 0)
        return XGBRegressor(**params)
    if model_id == "lightgbm":
        from lightgbm import LGBMRegressor

        params.setdefault("n_jobs", -1)
        params.setdefault("random_state", seed)
        params.setdefault("verbose", -1)
        return LGBMRegressor(**params)
    if model_id == "catboost":
        from catboost import CatBoostRegressor

        params.setdefault("allow_writing_files", False)
        params.setdefault("random_seed", seed)
        params.setdefault("verbose", False)
        return CatBoostRegressor(**params)
    raise ValueError(f"Unsupported model_id: {model_id}")


def fit_cqr_models(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_cal: pd.DataFrame,
    X_test: pd.DataFrame,
    alpha: float,
    seed: int,
    cqr_params: Dict | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    lower_q = alpha / 2.0
    upper_q = 1.0 - alpha / 2.0
    if np.shape(X_train)[1] == 0:
        lower_value = float(np.quantile(y_train, lower_q))
        upper_value = float(np.quantile(y_train, upper_q))
        metadata = {
            "cqr_backend": "constant_quantile_zero_feature",
            "cqr_backend_params": {},
            "lower_quantile": float(lower_q),
            "upper_quantile": float(upper_q),
            "zero_feature_constant_quantiles": True,
        }
        return (
            np.full(len(X_cal), lower_value, dtype=float),
            np.full(len(X_cal), upper_value, dtype=float),
            np.full(len(X_test), lower_value, dtype=float),
            np.full(len(X_test), upper_value, dtype=float),
            metadata,
        )
    common = {
        "loss": "quantile",
        "n_estimators": 300,
        "max_depth": 3,
        "learning_rate": 0.1,
        "random_state": seed,
    }
    cqr_params = dict(cqr_params or {})
    backend = str(cqr_params.pop("backend", "gradient_boosting"))
    if backend != "gradient_boosting":
        raise ValueError(f"Unsupported CQR backend: {backend}")
    reserved = {"loss", "alpha", "random_state"}
    forbidden = sorted(reserved.intersection(cqr_params))
    if forbidden:
        raise ValueError(f"CQR backend params cannot override reserved keys: {forbidden}")
    common.update(cqr_params)
    lower_model = GradientBoostingRegressor(alpha=lower_q, **common)
    upper_model = GradientBoostingRegressor(alpha=upper_q, **common)
    lower_model.fit(X_train, y_train)
    upper_model.fit(X_train, y_train)
    backend_params = {
        key: value
        for key, value in common.items()
        if key not in {"loss", "random_state"}
    }
    metadata = {
        "cqr_backend": backend,
        "cqr_backend_params": backend_params,
        "lower_quantile": float(lower_q),
        "upper_quantile": float(upper_q),
    }
    return (
        lower_model.predict(X_cal),
        upper_model.predict(X_cal),
        lower_model.predict(X_test),
        upper_model.predict(X_test),
        metadata,
    )


def _jsonable_params(params: Dict) -> Dict:
    """Return a compact JSON-serializable copy of estimator parameters."""

    jsonable = {}
    for key, value in dict(params).items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            jsonable[key] = value
        elif isinstance(value, (list, tuple)):
            jsonable[key] = list(value)
        else:
            jsonable[key] = str(value)
    return jsonable


def _quantile_regressor(alpha: float, cqr_params: Dict | None = None) -> QuantileRegressor:
    params = dict(cqr_params or {})
    qr_alpha = float(params.get("quantile_regressor_alpha", 1e-4))
    solver = str(params.get("quantile_solver", "highs"))
    return QuantileRegressor(quantile=float(alpha), alpha=qr_alpha, solver=solver)


def _fit_quantile_regressor_pair(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cal: np.ndarray,
    X_test: np.ndarray,
    lower_q: float,
    upper_q: float,
    *,
    cqr_params: Dict | None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    lower_model = _quantile_regressor(lower_q, cqr_params)
    upper_model = _quantile_regressor(upper_q, cqr_params)
    lower_model.fit(X_train, y_train)
    upper_model.fit(X_train, y_train)
    metadata = {
        "cqr_backend": "quantile_regressor",
        "cqr_backend_family": "linear_quantile_programming",
        "cqr_backend_params": {
            "quantile_regressor_alpha": float(lower_model.alpha),
            "quantile_solver": str(lower_model.solver),
        },
    }
    return (
        lower_model.predict(X_cal),
        upper_model.predict(X_cal),
        lower_model.predict(X_test),
        upper_model.predict(X_test),
        metadata,
    )


def _fit_nystroem_quantile_regressor_pair(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cal: np.ndarray,
    X_test: np.ndarray,
    lower_q: float,
    upper_q: float,
    *,
    model_id: str,
    model_params: Dict,
    seed: int,
    cqr_params: Dict | None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    params = dict(model_params)
    cqr_params = dict(cqr_params or {})
    kernel = str(params.get("kernel", "rbf"))
    gamma = params.get("gamma", None)
    if gamma == "scale":
        feature_var = float(np.var(X_train))
        gamma = 1.0 / max(X_train.shape[1] * feature_var, 1e-12)
    elif gamma == "auto" or gamma is None:
        gamma = 1.0 / max(X_train.shape[1], 1)
    n_components = int(
        min(
            max(1, X_train.shape[0]),
            int(cqr_params.get("nystroem_components", 200)),
        )
    )

    def make_model_for_quantile(q: float):
        return make_pipeline(
            Nystroem(
                kernel=kernel,
                gamma=float(gamma),
                degree=int(params.get("degree", 3)),
                coef0=float(params.get("coef0", 1.0)),
                n_components=n_components,
                random_state=seed,
            ),
            _quantile_regressor(q, cqr_params),
        )

    lower_model = make_model_for_quantile(lower_q)
    upper_model = make_model_for_quantile(upper_q)
    lower_model.fit(X_train, y_train)
    upper_model.fit(X_train, y_train)
    metadata = {
        "cqr_backend": "nystroem_quantile_regressor",
        "cqr_backend_family": "kernel_feature_quantile_programming",
        "cqr_backend_params": {
            "source_model_id": model_id,
            "kernel": kernel,
            "gamma": float(gamma),
            "degree": int(params.get("degree", 3)),
            "coef0": float(params.get("coef0", 1.0)),
            "nystroem_components": n_components,
            "quantile_regressor_alpha": float(
                lower_model.named_steps["quantileregressor"].alpha
            ),
            "quantile_solver": str(
                lower_model.named_steps["quantileregressor"].solver
            ),
        },
    }
    return (
        lower_model.predict(X_cal),
        upper_model.predict(X_cal),
        lower_model.predict(X_test),
        upper_model.predict(X_test),
        metadata,
    )


def _fit_hist_gradient_quantile_pair(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cal: np.ndarray,
    X_test: np.ndarray,
    lower_q: float,
    upper_q: float,
    *,
    model_params: Dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    reserved = {"loss", "quantile", "random_state"}
    params = {key: value for key, value in dict(model_params).items() if key not in reserved}

    def make_quantile_model(q: float):
        return HistGradientBoostingRegressor(
            **params,
            loss="quantile",
            quantile=float(q),
            random_state=seed,
        )

    lower_model = make_quantile_model(lower_q)
    upper_model = make_quantile_model(upper_q)
    lower_model.fit(X_train, y_train)
    upper_model.fit(X_train, y_train)
    metadata = {
        "cqr_backend": "hist_gradient_boosting_quantile",
        "cqr_backend_family": "native_histogram_boosting_quantile",
        "cqr_backend_params": _jsonable_params(params),
    }
    return (
        lower_model.predict(X_cal),
        upper_model.predict(X_cal),
        lower_model.predict(X_test),
        upper_model.predict(X_test),
        metadata,
    )


def _tree_empirical_quantiles(
    model,
    X: np.ndarray,
    lower_q: float,
    upper_q: float,
) -> Tuple[np.ndarray, np.ndarray]:
    predictions = np.column_stack([tree.predict(X) for tree in model.estimators_])
    return (
        np.quantile(predictions, lower_q, axis=1),
        np.quantile(predictions, upper_q, axis=1),
    )


def _fit_tree_empirical_quantile_pair(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cal: np.ndarray,
    X_test: np.ndarray,
    lower_q: float,
    upper_q: float,
    *,
    model_id: str,
    model_params: Dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    params = dict(model_params)
    params.setdefault("n_jobs", -1)
    params.setdefault("random_state", seed)
    if model_id == "random_forest":
        model = RandomForestRegressor(**params)
    elif model_id == "extra_trees":
        model = ExtraTreesRegressor(**params)
    else:
        raise ValueError(f"Unsupported tree empirical CQR backend: {model_id}")
    model.fit(X_train, y_train)
    lower_cal, upper_cal = _tree_empirical_quantiles(model, X_cal, lower_q, upper_q)
    lower_test, upper_test = _tree_empirical_quantiles(model, X_test, lower_q, upper_q)
    metadata = {
        "cqr_backend": f"{model_id}_per_tree_empirical_quantile",
        "cqr_backend_family": "tree_ensemble_empirical_quantile",
        "cqr_backend_params": _jsonable_params(params),
        "cqr_empirical_quantile_draws": int(len(model.estimators_)),
    }
    return lower_cal, upper_cal, lower_test, upper_test, metadata


def _fit_knn_empirical_quantile_pair(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cal: np.ndarray,
    X_test: np.ndarray,
    lower_q: float,
    upper_q: float,
    *,
    model_params: Dict,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    params = dict(model_params)
    params.setdefault("n_neighbors", min(5, len(y_train)))
    params["n_neighbors"] = min(int(params["n_neighbors"]), len(y_train))
    model = KNeighborsRegressor(**params)
    model.fit(X_train, y_train)

    def quantiles(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        neighbor_indices = model.kneighbors(X, return_distance=False)
        neighbor_targets = y_train[neighbor_indices]
        return (
            np.quantile(neighbor_targets, lower_q, axis=1),
            np.quantile(neighbor_targets, upper_q, axis=1),
        )

    lower_cal, upper_cal = quantiles(X_cal)
    lower_test, upper_test = quantiles(X_test)
    metadata = {
        "cqr_backend": "knn_neighbor_target_empirical_quantile",
        "cqr_backend_family": "local_neighbor_empirical_quantile",
        "cqr_backend_params": _jsonable_params(params),
        "cqr_neighbor_quantile_weighting": "unweighted_empirical_neighbor_targets",
    }
    return lower_cal, upper_cal, lower_test, upper_test, metadata


def _fit_xgboost_quantile_pair(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cal: np.ndarray,
    X_test: np.ndarray,
    lower_q: float,
    upper_q: float,
    *,
    model_params: Dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    try:
        from xgboost import XGBRegressor
    except Exception as exc:
        raise MethodSkipped(f"cqr_model_matched xgboost skipped: import failed: {exc}") from exc

    params = dict(model_params)
    params.setdefault("n_jobs", -1)
    params.setdefault("random_state", seed)
    params.setdefault("tree_method", "hist")
    params.setdefault("verbosity", 0)
    params.pop("objective", None)

    def make_quantile_model(q: float):
        return XGBRegressor(
            **params,
            objective="reg:quantileerror",
            quantile_alpha=float(q),
        )

    try:
        lower_model = make_quantile_model(lower_q)
        upper_model = make_quantile_model(upper_q)
        lower_model.fit(X_train, y_train)
        upper_model.fit(X_train, y_train)
    except Exception as exc:
        raise MethodSkipped(
            "cqr_model_matched xgboost skipped: native quantile objective "
            f"not supported or failed in installed xgboost; reason={exc}"
        ) from exc
    metadata = {
        "cqr_backend": "xgboost_native_quantile",
        "cqr_backend_family": "native_gradient_boosting_quantile",
        "cqr_backend_params": _jsonable_params(params),
        "cqr_xgboost_objective": "reg:quantileerror",
    }
    return (
        lower_model.predict(X_cal),
        upper_model.predict(X_cal),
        lower_model.predict(X_test),
        upper_model.predict(X_test),
        metadata,
    )


def _fit_lightgbm_quantile_pair(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cal: np.ndarray,
    X_test: np.ndarray,
    lower_q: float,
    upper_q: float,
    *,
    model_params: Dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    try:
        from lightgbm import LGBMRegressor
    except Exception as exc:
        raise MethodSkipped(f"cqr_model_matched lightgbm skipped: import failed: {exc}") from exc

    params = dict(model_params)
    params.setdefault("n_jobs", -1)
    params.setdefault("random_state", seed)
    params.setdefault("verbose", -1)
    params.pop("objective", None)
    params.pop("alpha", None)

    def make_quantile_model(q: float):
        return LGBMRegressor(**params, objective="quantile", alpha=float(q))

    lower_model = make_quantile_model(lower_q)
    upper_model = make_quantile_model(upper_q)
    lower_model.fit(X_train, y_train)
    upper_model.fit(X_train, y_train)
    metadata = {
        "cqr_backend": "lightgbm_native_quantile",
        "cqr_backend_family": "native_gradient_boosting_quantile",
        "cqr_backend_params": _jsonable_params(params),
        "cqr_lightgbm_objective": "quantile",
    }
    return (
        lower_model.predict(X_cal),
        upper_model.predict(X_cal),
        lower_model.predict(X_test),
        upper_model.predict(X_test),
        metadata,
    )


def _fit_catboost_quantile_pair(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cal: np.ndarray,
    X_test: np.ndarray,
    lower_q: float,
    upper_q: float,
    *,
    model_params: Dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    try:
        from catboost import CatBoostRegressor
    except Exception as exc:
        raise MethodSkipped(f"cqr_model_matched catboost skipped: import failed: {exc}") from exc

    params = dict(model_params)
    params.setdefault("allow_writing_files", False)
    params.setdefault("random_seed", seed)
    params.setdefault("verbose", False)
    params.pop("loss_function", None)

    def make_quantile_model(q: float):
        return CatBoostRegressor(**params, loss_function=f"Quantile:alpha={float(q)}")

    lower_model = make_quantile_model(lower_q)
    upper_model = make_quantile_model(upper_q)
    lower_model.fit(X_train, y_train)
    upper_model.fit(X_train, y_train)
    metadata = {
        "cqr_backend": "catboost_native_quantile",
        "cqr_backend_family": "native_gradient_boosting_quantile",
        "cqr_backend_params": _jsonable_params(params),
        "cqr_catboost_loss_function": "Quantile:alpha=<lower_or_upper_quantile>",
    }
    return (
        lower_model.predict(X_cal),
        upper_model.predict(X_cal),
        lower_model.predict(X_test),
        upper_model.predict(X_test),
        metadata,
    )


def fit_cqr_model_matched_models(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_cal: pd.DataFrame,
    X_test: pd.DataFrame,
    alpha: float,
    seed: int,
    model_id: str,
    model_params: Dict,
    cqr_params: Dict | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    """Fit CQR quantile backends matched to the base model family."""

    lower_q = alpha / 2.0
    upper_q = 1.0 - alpha / 2.0
    model_params = dict(model_params)
    cqr_params = dict(cqr_params or {})
    if np.shape(X_train)[1] == 0 or model_id == "dummy_mean":
        lower_value = float(np.quantile(y_train, lower_q))
        upper_value = float(np.quantile(y_train, upper_q))
        metadata = {
            "cqr_backend": "constant_quantile_model_matched",
            "cqr_backend_family": "constant_empirical_quantile",
            "cqr_backend_params": {},
            "lower_quantile": float(lower_q),
            "upper_quantile": float(upper_q),
            "zero_feature_constant_quantiles": bool(np.shape(X_train)[1] == 0),
            "cqr_method_id": "cqr_model_matched",
            "source_model_id": model_id,
            "source_model_params": _jsonable_params(model_params),
        }
        return (
            np.full(len(X_cal), lower_value, dtype=float),
            np.full(len(X_cal), upper_value, dtype=float),
            np.full(len(X_test), lower_value, dtype=float),
            np.full(len(X_test), upper_value, dtype=float),
            metadata,
        )

    if model_id in {"ridge", "elasticnet", "bayesian_ridge"}:
        outputs = _fit_quantile_regressor_pair(
            X_train,
            y_train,
            X_cal,
            X_test,
            lower_q,
            upper_q,
            cqr_params=cqr_params,
        )
    elif model_id == "hist_gradient_boosting":
        outputs = _fit_hist_gradient_quantile_pair(
            X_train,
            y_train,
            X_cal,
            X_test,
            lower_q,
            upper_q,
            model_params=model_params,
            seed=seed,
        )
    elif model_id in {"random_forest", "extra_trees"}:
        outputs = _fit_tree_empirical_quantile_pair(
            X_train,
            y_train,
            X_cal,
            X_test,
            lower_q,
            upper_q,
            model_id=model_id,
            model_params=model_params,
            seed=seed,
        )
    elif model_id == "knn":
        outputs = _fit_knn_empirical_quantile_pair(
            X_train,
            y_train,
            X_cal,
            X_test,
            lower_q,
            upper_q,
            model_params=model_params,
        )
    elif model_id in {"kernel_ridge", "svr"}:
        outputs = _fit_nystroem_quantile_regressor_pair(
            X_train,
            y_train,
            X_cal,
            X_test,
            lower_q,
            upper_q,
            model_id=model_id,
            model_params=model_params,
            seed=seed,
            cqr_params=cqr_params,
        )
    elif model_id == "xgboost":
        outputs = _fit_xgboost_quantile_pair(
            X_train,
            y_train,
            X_cal,
            X_test,
            lower_q,
            upper_q,
            model_params=model_params,
            seed=seed,
        )
    elif model_id == "lightgbm":
        outputs = _fit_lightgbm_quantile_pair(
            X_train,
            y_train,
            X_cal,
            X_test,
            lower_q,
            upper_q,
            model_params=model_params,
            seed=seed,
        )
    elif model_id == "catboost":
        outputs = _fit_catboost_quantile_pair(
            X_train,
            y_train,
            X_cal,
            X_test,
            lower_q,
            upper_q,
            model_params=model_params,
            seed=seed,
        )
    else:
        raise MethodSkipped(
            f"cqr_model_matched skipped: no model-matched quantile backend for {model_id}"
        )

    lower_cal, upper_cal, lower_test, upper_test, metadata = outputs
    metadata = {
        **metadata,
        "lower_quantile": float(lower_q),
        "upper_quantile": float(upper_q),
        "cqr_method_id": "cqr_model_matched",
        "source_model_id": model_id,
        "source_model_params": _jsonable_params(model_params),
        "cqr_backend_matching_policy": "model_family_matched_quantile_backend_v1",
    }
    return lower_cal, upper_cal, lower_test, upper_test, metadata


def fit_residual_scale(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    yhat_train: np.ndarray,
    X_cal: pd.DataFrame,
    X_test: pd.DataFrame,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    residuals = np.abs(y_train - yhat_train)
    if np.shape(X_train)[1] == 0:
        constant = float(max(np.quantile(residuals, 0.75), 1e-8))
        return (
            np.full(len(X_cal), constant, dtype=float),
            np.full(len(X_test), constant, dtype=float),
        )
    model = HistGradientBoostingRegressor(
        loss="absolute_error",
        max_leaf_nodes=31,
        learning_rate=0.05,
        random_state=seed,
    )
    model.fit(X_train, residuals)
    return np.maximum(model.predict(X_cal), 1e-8), np.maximum(model.predict(X_test), 1e-8)


def fit_residual_quantile_scores(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    yhat_train: np.ndarray,
    X_cal: pd.DataFrame,
    X_test: pd.DataFrame,
    alpha: float,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    residuals = np.abs(y_train - yhat_train)
    quantile_level = 1.0 - alpha
    if np.shape(X_train)[1] == 0:
        constant = float(max(np.quantile(residuals, quantile_level), 0.0))
        return (
            np.full(len(X_cal), constant, dtype=float),
            np.full(len(X_test), constant, dtype=float),
        )
    if np.allclose(residuals, residuals[0]):
        constant = float(max(residuals[0], 0.0))
        return (
            np.full(len(X_cal), constant, dtype=float),
            np.full(len(X_test), constant, dtype=float),
        )

    if len(y_train) >= 20_000:
        model = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=quantile_level,
            max_iter=120,
            max_leaf_nodes=31,
            learning_rate=0.05,
            random_state=seed,
        )
    else:
        model = GradientBoostingRegressor(
            loss="quantile",
            alpha=quantile_level,
            n_estimators=200,
            max_depth=3,
            random_state=seed,
        )
    model.fit(X_train, residuals)
    return np.maximum(model.predict(X_cal), 0.0), np.maximum(model.predict(X_test), 0.0)


def estimate_covariate_shift_weights(
    X_cal: np.ndarray,
    X_test: np.ndarray,
    seed: int,
    probability_clip: float = 0.01,
    weight_clip: float = 20.0,
) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """Estimate target/source covariate density ratios from unlabeled features."""

    if not 0 < probability_clip < 0.5:
        raise ValueError(f"probability_clip must be in (0, 0.5), got {probability_clip}")
    if weight_clip <= 1:
        raise ValueError(f"weight_clip must be greater than 1, got {weight_clip}")
    if len(X_cal) == 0 or len(X_test) == 0:
        raise MethodSkipped("weighted_abs_covariate_shift requires calibration and test rows")

    X_domain = np.vstack([X_cal, X_test])
    y_domain = np.concatenate(
        [np.zeros(len(X_cal), dtype=int), np.ones(len(X_test), dtype=int)]
    )
    model = LogisticRegression(max_iter=1000, random_state=seed)
    model.fit(X_domain, y_domain)
    prob_test = np.clip(
        model.predict_proba(X_domain)[:, 1],
        probability_clip,
        1.0 - probability_clip,
    )
    odds = prob_test / (1.0 - prob_test)
    prior_correction = len(X_cal) / len(X_test)
    weights = np.clip(odds * prior_correction, 1.0 / weight_clip, weight_clip)
    cal_weights = weights[: len(X_cal)]
    test_weights = weights[len(X_cal) :]
    metadata = {
        "density_ratio_model": "logistic_regression_calibration_vs_test",
        "probability_clip": float(probability_clip),
        "weight_clip": float(weight_clip),
        "prior_correction": float(prior_correction),
        "mean_calibration_weight": float(cal_weights.mean()),
        "mean_test_weight": float(test_weights.mean()),
        "min_calibration_weight": float(cal_weights.min()),
        "max_calibration_weight": float(cal_weights.max()),
        "min_test_weight": float(test_weights.min()),
        "max_test_weight": float(test_weights.max()),
    }
    return cal_weights, test_weights, metadata


def fold_local_feature_reducer_available(
    X_train_pre_feature_reducer: np.ndarray | None,
    X_test_pre_feature_reducer: np.ndarray | None,
    preprocessed_feature_names: List[str] | None,
    config: Dict | None,
) -> bool:
    """Return whether plus-family resampling can refit the feature reducer per fold."""

    return (
        X_train_pre_feature_reducer is not None
        and X_test_pre_feature_reducer is not None
        and preprocessed_feature_names is not None
        and config is not None
    )


def plus_fold_local_preprocessing_enabled(config: Dict | None) -> bool:
    """Return whether plus-family methods should refit preprocessing per fold."""

    if not isinstance(config, dict):
        return False
    conformal = config.get("conformal", {})
    if not isinstance(conformal, dict):
        return False
    return bool(conformal.get("plus_fold_local_preprocessing", False))


def fold_local_preprocessing_available(
    X_train_raw: pd.DataFrame | None,
    X_test_raw: pd.DataFrame | None,
    config: Dict | None,
) -> bool:
    """Return whether raw feature frames are available for fold-local preprocessing."""

    return (
        plus_fold_local_preprocessing_enabled(config)
        and isinstance(X_train_raw, pd.DataFrame)
        and isinstance(X_test_raw, pd.DataFrame)
    )


def plus_feature_reducer_fold_local_applied(
    X_train_pre_feature_reducer: np.ndarray | None,
    X_test_pre_feature_reducer: np.ndarray | None,
    X_train_raw: pd.DataFrame | None,
    X_test_raw: pd.DataFrame | None,
    preprocessed_feature_names: List[str] | None,
    config: Dict | None,
) -> bool:
    """Return whether a configured feature reducer is refit inside plus folds."""

    if feature_reducer_config(config)["method"] in {"none", ""}:
        return False
    return fold_local_preprocessing_available(
        X_train_raw,
        X_test_raw,
        config,
    ) or fold_local_feature_reducer_available(
        X_train_pre_feature_reducer,
        X_test_pre_feature_reducer,
        preprocessed_feature_names,
        config,
    )


def plus_fold_feature_reducer_metadata(
    *,
    applied: bool,
    config: Dict | None,
    preprocessing_applied: bool = False,
) -> Dict[str, Any]:
    reducer = feature_reducer_config(config)
    reducer_method = reducer["method"]
    reducer_uses_labels = reducer_method == "select_k_best_f_regression"
    if reducer_uses_labels:
        reducer_label_scope = (
            "internal_fit_fold_only" if applied else "prediction_bundle_outer_train"
        )
    else:
        reducer_label_scope = "not_applicable_unsupervised_or_none"
    base = {
        "plus_preprocessing_fit_scope": (
            "internal_resampling_fit_fold_only"
            if preprocessing_applied
            else "prediction_bundle_outer_train"
        ),
        "plus_preprocessing_fold_local": bool(preprocessing_applied),
        "plus_preprocessing_label_access": "none",
        "plus_preprocessing_note": (
            "The preprocessor is refit inside each CV+/jackknife fit fold."
            if preprocessing_applied
            else (
                "The prediction-bundle preprocessor is unsupervised and fitted once "
                "on the outer training split. Benchmark v2 requires fully fold-local "
                "preprocessing, encoding, dimensionality reduction, and supervised "
                "feature selection for confirmatory plus-family comparisons."
            )
        ),
        "plus_feature_reducer_method": reducer_method,
        "plus_feature_reducer_uses_labels": reducer_uses_labels,
        "plus_feature_reducer_label_access_scope": reducer_label_scope,
    }
    if not applied:
        return {
            **base,
            "plus_feature_reducer_fit_scope": "pre_reduced_prediction_bundle",
            "plus_feature_reducer_fold_local": False,
        }
    return {
        **base,
        "plus_feature_reducer_fit_scope": "internal_resampling_fit_fold_only",
        "plus_feature_reducer_fold_local": True,
        "plus_feature_reducer_note": (
            "The optional feature reducer is refit inside each CV+/jackknife "
            "fit fold. If the reducer uses labels, only the internal fit-fold "
            "labels are visible to that reducer. The preprocessing transformer "
            "is still the prediction-bundle preprocessor fitted on the outer "
            "training split."
        ),
    }


def fold_local_resampling_matrices(
    *,
    X_train: np.ndarray,
    X_test: np.ndarray,
    y_train: np.ndarray,
    fit_idx: np.ndarray,
    heldout_idx: np.ndarray,
    seed: int,
    X_train_pre_feature_reducer: np.ndarray | None = None,
    X_test_pre_feature_reducer: np.ndarray | None = None,
    X_train_raw: pd.DataFrame | None = None,
    X_test_raw: pd.DataFrame | None = None,
    preprocessed_feature_names: List[str] | None = None,
    config: Dict | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool]:
    """Return fold-local train, heldout, and test matrices for plus-family methods."""

    if fold_local_preprocessing_available(X_train_raw, X_test_raw, config):
        preprocessor = fit_preprocessing(
            X_train_raw.iloc[fit_idx].copy(),
            PreprocessingConfig(),
        )
        X_fit_p = apply_preprocessing(X_train_raw.iloc[fit_idx].copy(), preprocessor)
        X_heldout_p = apply_preprocessing(
            X_train_raw.iloc[heldout_idx].copy(), preprocessor
        )
        X_test_p = apply_preprocessing(X_test_raw.copy(), preprocessor)
        feature_names = list(X_fit_p.columns)
        X_fit, X_heldout, X_test_fold, _, _ = apply_feature_reducer(
            X_fit_p.to_numpy(dtype=float),
            y_train[fit_idx],
            X_heldout_p.to_numpy(dtype=float),
            X_test_p.to_numpy(dtype=float),
            feature_names,
            config or {},
            seed,
        )
        reducer_applied = feature_reducer_config(config)["method"] not in {"none", ""}
        return X_fit, X_heldout, X_test_fold, reducer_applied, True

    if not fold_local_feature_reducer_available(
        X_train_pre_feature_reducer,
        X_test_pre_feature_reducer,
        preprocessed_feature_names,
        config,
    ):
        return X_train[fit_idx], X_train[heldout_idx], X_test, False, False

    X_fit, X_heldout, X_test_fold, _, _ = apply_feature_reducer(
        X_train_pre_feature_reducer[fit_idx],
        y_train[fit_idx],
        X_train_pre_feature_reducer[heldout_idx],
        X_test_pre_feature_reducer,
        preprocessed_feature_names,
        config,
        seed,
    )
    return X_fit, X_heldout, X_test_fold, True, False


def fit_cv_plus_predictions(
    model_id: str,
    model_params: Dict,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    seed: int,
    n_folds: int,
    *,
    X_train_pre_feature_reducer: np.ndarray | None = None,
    X_test_pre_feature_reducer: np.ndarray | None = None,
    X_train_raw: pd.DataFrame | None = None,
    X_test_raw: pd.DataFrame | None = None,
    preprocessed_feature_names: List[str] | None = None,
    config: Dict | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit fold-excluded models for CV+."""

    if n_folds < 2:
        raise ValueError(f"n_folds must be at least 2, got {n_folds}")
    if len(y_train) < n_folds:
        raise MethodSkipped(
            f"cv_plus requires at least {n_folds} training rows, got {len(y_train)}"
        )

    splitter = KFold(n_splits=n_folds, shuffle=True, random_state=seed)
    yhat_oof = np.empty(len(y_train), dtype=float)
    fold_ids = np.empty(len(y_train), dtype=int)
    yhat_test_by_fold = []

    for fold_idx, (fit_idx, heldout_idx) in enumerate(splitter.split(X_train)):
        model = make_model(model_id, model_params, seed + fold_idx)
        X_fit, X_heldout, X_test_fold, _, _ = fold_local_resampling_matrices(
            X_train=X_train,
            X_test=X_test,
            y_train=y_train,
            fit_idx=fit_idx,
            heldout_idx=heldout_idx,
            seed=seed + fold_idx,
            X_train_pre_feature_reducer=X_train_pre_feature_reducer,
            X_test_pre_feature_reducer=X_test_pre_feature_reducer,
            X_train_raw=X_train_raw,
            X_test_raw=X_test_raw,
            preprocessed_feature_names=preprocessed_feature_names,
            config=config,
        )
        model.fit(X_fit, y_train[fit_idx])
        yhat_oof[heldout_idx] = model.predict(X_heldout)
        fold_ids[heldout_idx] = fold_idx
        yhat_test_by_fold.append(model.predict(X_test_fold))

    return yhat_oof, np.vstack(yhat_test_by_fold), fold_ids


def _normalize_split_groups(
    split_groups_train: Iterable,
    *,
    expected_length: int,
    method_name: str,
) -> np.ndarray:
    groups = np.asarray(split_groups_train, dtype=object)
    if groups.ndim != 1:
        raise ValueError(
            f"{method_name} split_groups_train must be 1D, got shape {groups.shape}"
        )
    if len(groups) != expected_length:
        raise ValueError(
            f"{method_name} split_groups_train length {len(groups)} does not match "
            f"n_train={expected_length}"
        )
    return (
        pd.Series(groups, dtype="object")
        .where(pd.Series(groups, dtype="object").notna(), "__missing__")
        .astype(str)
        .to_numpy()
    )


def grouped_cv_fold_indices(
    split_groups_train: Iterable,
    *,
    n_folds: int,
    seed: int,
    method_name: str = "grouped_cv",
) -> Tuple[List[Tuple[np.ndarray, np.ndarray]], np.ndarray, Dict]:
    """Return deterministic group-held-out CV folds for training rows.

    Groups are assigned greedily by descending group size with seeded tie
    breaking. The assignment balances row counts while guaranteeing each split
    group appears in exactly one held-out fold.
    """

    if n_folds < 2:
        raise ValueError(f"n_folds must be at least 2, got {n_folds}")
    groups = _normalize_split_groups(
        split_groups_train,
        expected_length=len(split_groups_train),
        method_name=method_name,
    )
    unique_groups, group_inverse = np.unique(groups, return_inverse=True)
    n_groups = len(unique_groups)
    if n_groups < n_folds:
        raise MethodSkipped(
            f"{method_name} requires at least {n_folds} split groups, got {n_groups}"
        )

    group_sizes = np.bincount(group_inverse)
    rng = np.random.default_rng(seed)
    tie_breakers = rng.random(n_groups)
    group_order = np.lexsort((tie_breakers, -group_sizes))
    group_to_fold = np.empty(n_groups, dtype=int)
    fold_row_counts = np.zeros(n_folds, dtype=int)

    for group_idx in group_order:
        fold_idx = int(np.argmin(fold_row_counts))
        group_to_fold[group_idx] = fold_idx
        fold_row_counts[fold_idx] += int(group_sizes[group_idx])

    row_fold_ids = group_to_fold[group_inverse]
    all_indices = np.arange(len(groups))
    folds: List[Tuple[np.ndarray, np.ndarray]] = []
    for fold_idx in range(n_folds):
        heldout_idx = all_indices[row_fold_ids == fold_idx]
        fit_idx = all_indices[row_fold_ids != fold_idx]
        if len(heldout_idx) == 0 or len(fit_idx) == 0:
            raise MethodSkipped(
                f"{method_name} produced an empty internal fold at fold={fold_idx}; "
                "reduce n_folds or review split-group cardinality"
            )
        folds.append((fit_idx, heldout_idx))

    group_split_violations = 0
    for group_idx in range(n_groups):
        if len(np.unique(row_fold_ids[group_inverse == group_idx])) != 1:
            group_split_violations += 1
    if group_split_violations:
        raise ValueError(
            f"{method_name} split {group_split_violations} groups across internal folds"
        )

    fold_group_counts = np.bincount(group_to_fold, minlength=n_folds)
    metadata = {
        "internal_resampling_unit": "split_group",
        "internal_fold_assignment": "seeded_greedy_group_kfold",
        "n_internal_groups": int(n_groups),
        "internal_fold_row_counts": [int(value) for value in fold_row_counts],
        "internal_fold_group_counts": [int(value) for value in fold_group_counts],
        "min_internal_fold_rows": int(fold_row_counts.min()),
        "max_internal_fold_rows": int(fold_row_counts.max()),
        "min_internal_fold_groups": int(fold_group_counts.min()),
        "max_internal_fold_groups": int(fold_group_counts.max()),
        "groups_split_across_internal_folds": False,
    }
    return folds, row_fold_ids, metadata


def fit_grouped_cv_plus_predictions(
    model_id: str,
    model_params: Dict,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    split_groups_train: Iterable,
    seed: int,
    n_folds: int,
    *,
    method_name: str = "cv_plus_grouped",
    X_train_pre_feature_reducer: np.ndarray | None = None,
    X_test_pre_feature_reducer: np.ndarray | None = None,
    X_train_raw: pd.DataFrame | None = None,
    X_test_raw: pd.DataFrame | None = None,
    preprocessed_feature_names: List[str] | None = None,
    config: Dict | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict]:
    """Fit fold-excluded CV+ predictions without splitting train groups."""

    if len(y_train) < 2:
        raise MethodSkipped(f"{method_name} requires at least two training rows")
    groups = _normalize_split_groups(
        split_groups_train,
        expected_length=len(y_train),
        method_name=method_name,
    )
    folds, fold_ids, metadata = grouped_cv_fold_indices(
        groups,
        n_folds=n_folds,
        seed=seed,
        method_name=method_name,
    )
    yhat_oof = np.empty(len(y_train), dtype=float)
    yhat_test_by_fold = []
    preprocessing_applied_any = False

    for fold_idx, (fit_idx, heldout_idx) in enumerate(folds):
        model = make_model(model_id, model_params, seed + fold_idx)
        X_fit, X_heldout, X_test_fold, fold_local_applied, preprocessing_applied = (
            fold_local_resampling_matrices(
                X_train=X_train,
                X_test=X_test,
                y_train=y_train,
                fit_idx=fit_idx,
                heldout_idx=heldout_idx,
                seed=seed + fold_idx,
                X_train_pre_feature_reducer=X_train_pre_feature_reducer,
                X_test_pre_feature_reducer=X_test_pre_feature_reducer,
                X_train_raw=X_train_raw,
                X_test_raw=X_test_raw,
                preprocessed_feature_names=preprocessed_feature_names,
                config=config,
            )
        )
        model.fit(X_fit, y_train[fit_idx])
        yhat_oof[heldout_idx] = model.predict(X_heldout)
        yhat_test_by_fold.append(model.predict(X_test_fold))
        metadata["plus_feature_reducer_fold_local"] = bool(
            metadata.get("plus_feature_reducer_fold_local", False) or fold_local_applied
        )
        preprocessing_applied_any = bool(
            preprocessing_applied_any or preprocessing_applied
        )

    metadata.update(
        plus_fold_feature_reducer_metadata(
            applied=bool(metadata.get("plus_feature_reducer_fold_local", False)),
            config=config,
            preprocessing_applied=preprocessing_applied_any,
        )
    )

    return yhat_oof, np.vstack(yhat_test_by_fold), fold_ids, metadata


def fit_jackknife_plus_predictions(
    model_id: str,
    model_params: Dict,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    seed: int,
    max_train_rows: int | None,
    *,
    X_train_pre_feature_reducer: np.ndarray | None = None,
    X_test_pre_feature_reducer: np.ndarray | None = None,
    X_train_raw: pd.DataFrame | None = None,
    X_test_raw: pd.DataFrame | None = None,
    preprocessed_feature_names: List[str] | None = None,
    config: Dict | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Fit leave-one-out models for jackknife+."""

    n_train = len(y_train)
    if max_train_rows is not None and n_train > max_train_rows:
        raise MethodSkipped(
            f"jackknife_plus skipped: n_train={n_train} exceeds max_train_rows={max_train_rows}"
        )
    if n_train < 2:
        raise MethodSkipped("jackknife_plus requires at least two training rows")

    yhat_train_loo = np.empty(n_train, dtype=float)
    yhat_test_loo = np.empty((n_train, len(X_test)), dtype=float)
    all_indices = np.arange(n_train)
    for row_idx in range(n_train):
        fit_idx = all_indices != row_idx
        heldout_idx = np.array([row_idx], dtype=int)
        model = make_model(model_id, model_params, seed + row_idx)
        X_fit, X_heldout, X_test_fold, _, _ = fold_local_resampling_matrices(
            X_train=X_train,
            X_test=X_test,
            y_train=y_train,
            fit_idx=np.flatnonzero(fit_idx),
            heldout_idx=heldout_idx,
            seed=seed + row_idx,
            X_train_pre_feature_reducer=X_train_pre_feature_reducer,
            X_test_pre_feature_reducer=X_test_pre_feature_reducer,
            X_train_raw=X_train_raw,
            X_test_raw=X_test_raw,
            preprocessed_feature_names=preprocessed_feature_names,
            config=config,
        )
        model.fit(X_fit, y_train[fit_idx])
        yhat_train_loo[row_idx] = model.predict(X_heldout)[0]
        yhat_test_loo[row_idx] = model.predict(X_test_fold)

    return yhat_train_loo, yhat_test_loo


def fit_jackknife_after_bootstrap_predictions(
    model_id: str,
    model_params: Dict,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    seed: int,
    n_resamples: int,
    sample_fraction: float,
    min_oob_models: int,
    max_train_rows: int | None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit bootstrap models and aggregate out-of-bag predictions for J+aB."""

    n_train = len(y_train)
    if max_train_rows is not None and n_train > max_train_rows:
        raise MethodSkipped(
            "jackknife_plus_after_bootstrap skipped: "
            f"n_train={n_train} exceeds max_train_rows={max_train_rows}"
        )
    if n_train < 2:
        raise MethodSkipped("jackknife_plus_after_bootstrap requires at least two training rows")
    if n_resamples < 2:
        raise ValueError(f"n_resamples must be at least 2, got {n_resamples}")
    if not 0 < sample_fraction <= 1:
        raise ValueError(f"sample_fraction must be in (0, 1], got {sample_fraction}")
    if min_oob_models < 1:
        raise ValueError(f"min_oob_models must be at least 1, got {min_oob_models}")

    sample_size = max(1, int(round(sample_fraction * n_train)))
    rng = np.random.default_rng(seed)
    train_pred_sum = np.zeros(n_train, dtype=float)
    test_pred_sum = np.zeros((n_train, len(X_test)), dtype=float)
    oob_counts = np.zeros(n_train, dtype=int)

    for bootstrap_idx in range(n_resamples):
        sample_idx = rng.integers(0, n_train, size=sample_size)
        oob_mask = np.ones(n_train, dtype=bool)
        oob_mask[np.unique(sample_idx)] = False
        if not np.any(oob_mask):
            continue

        model = make_model(model_id, model_params, seed + 10_000 + bootstrap_idx)
        model.fit(X_train[sample_idx], y_train[sample_idx])
        train_pred_sum[oob_mask] += model.predict(X_train[oob_mask])
        test_pred_sum[oob_mask] += model.predict(X_test)
        oob_counts[oob_mask] += 1

    if np.any(oob_counts < min_oob_models):
        min_count = int(oob_counts.min())
        bad_rows = int(np.sum(oob_counts < min_oob_models))
        raise MethodSkipped(
            "jackknife_plus_after_bootstrap skipped: "
            f"{bad_rows} training rows have fewer than {min_oob_models} "
            f"out-of-bag models; min_oob_count={min_count}, "
            "increase n_resamples or lower sample_fraction"
        )

    yhat_train_oob = train_pred_sum / oob_counts
    yhat_test_oob = test_pred_sum / oob_counts[:, None]
    return yhat_train_oob, yhat_test_oob, oob_counts


def target_transform_for_dataset(config: Dict, dataset_id: str) -> str:
    """Return the target transform, allowing dataset-level config overrides."""

    overrides = config.get("dataset_target_transforms", {})
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise ValueError("dataset_target_transforms must be a mapping when provided")
    return str(overrides.get(dataset_id, config.get("target_transform", "identity")))


def feature_reducer_config(config: Dict | None) -> Dict:
    """Return normalized feature-reducer config for cache and run identity."""

    if config is None:
        return {"method": "none"}
    reducer = config.get("feature_reducer", {})
    if reducer is None:
        reducer = {}
    if not isinstance(reducer, dict):
        raise ValueError("feature_reducer must be a mapping when provided")
    normalized = dict(reducer)
    normalized["method"] = str(normalized.get("method", "none"))
    return normalized


def apply_feature_reducer(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cal: np.ndarray,
    X_test: np.ndarray,
    feature_names: List[str],
    config: Dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str], Dict]:
    """Fit an optional dimensionality reducer on train only and transform all splits."""

    reducer = feature_reducer_config(config)
    method = reducer["method"]
    original_feature_count = int(X_train.shape[1])
    base_metadata = {
        "method": method,
        "fit_scope": "train_only",
        "original_feature_count": original_feature_count,
    }
    if method in {"none", ""}:
        return (
            X_train,
            X_cal,
            X_test,
            list(feature_names),
            {**base_metadata, "reduced_feature_count": original_feature_count},
        )
    if original_feature_count == 0:
        metadata = {
            **base_metadata,
            "reduced_feature_count": 0,
            "skipped_reason": "no_features_after_preprocessing",
        }
        return X_train, X_cal, X_test, list(feature_names), metadata

    if method == "pca":
        requested = reducer.get("n_components", min(50, original_feature_count))
        max_components = min(original_feature_count, int(X_train.shape[0]))
        if isinstance(requested, float) and 0.0 < requested < 1.0:
            effective = requested
        else:
            effective = max(1, min(int(requested), max_components))
        model = PCA(
            n_components=effective,
            random_state=seed,
            svd_solver=str(reducer.get("svd_solver", "auto")),
        )
        X_train_r = model.fit_transform(X_train)
        X_cal_r = model.transform(X_cal)
        X_test_r = model.transform(X_test)
        reduced_feature_count = int(X_train_r.shape[1])
        reduced_names = [f"pca_{idx:03d}" for idx in range(1, reduced_feature_count + 1)]
        metadata = {
            **base_metadata,
            "requested_n_components": requested,
            "effective_n_components": (
                float(effective) if isinstance(effective, float) else int(effective)
            ),
            "svd_solver": str(reducer.get("svd_solver", "auto")),
            "reduced_feature_count": reduced_feature_count,
            "explained_variance_ratio_sum": float(
                np.sum(getattr(model, "explained_variance_ratio_", np.array([])))
            ),
        }
        return X_train_r, X_cal_r, X_test_r, reduced_names, metadata

    if method == "select_k_best_f_regression":
        requested_k = int(reducer.get("k", min(50, original_feature_count)))
        effective_k = max(1, min(requested_k, original_feature_count))
        model = SelectKBest(score_func=f_regression, k=effective_k)
        X_train_r = model.fit_transform(X_train, y_train)
        X_cal_r = model.transform(X_cal)
        X_test_r = model.transform(X_test)
        support = model.get_support(indices=True)
        reduced_names = [str(feature_names[idx]) for idx in support]
        metadata = {
            **base_metadata,
            "requested_k": requested_k,
            "effective_k": effective_k,
            "reduced_feature_count": int(X_train_r.shape[1]),
            "selected_feature_names": reduced_names,
            "score_function": "f_regression",
        }
        return X_train_r, X_cal_r, X_test_r, reduced_names, metadata

    raise ValueError(f"Unsupported feature_reducer method: {method}")


def allows_legacy_run_id_resume(config: Dict | None) -> bool:
    """Return whether legacy v1 checkpoint IDs may skip a modern run.

    This is intentionally opt-in. A legacy checkpoint lacks modern target,
    split-policy, duplicate-scope, and CP-parameter context, so silently
    accepting it can hide a scientifically different rerun.
    """

    resume_config = (config or {}).get("resume", {})
    if not isinstance(resume_config, dict) or not resume_config.get(
        "allow_legacy_run_id_v1",
        False,
    ):
        return False

    reducer = feature_reducer_config(config)
    return reducer["method"] in {"none", ""}


def prediction_artifact_payload(
    dataset_id: str,
    target: str,
    group_col: str,
    model_id: str,
    model_family: str,
    model_params: Dict,
    seed: int,
    config: Dict,
    data_provenance: Dict[str, Any] | None = None,
    code_provenance: Dict[str, Any] | None = None,
) -> Dict:
    target_transform = target_transform_for_dataset(config, dataset_id)
    split_group_col = config.get("splits", {}).get("group_col")
    split_strategy = config.get("splits", {}).get("strategy")
    split_order_col = config.get("splits", {}).get("order_col")
    source_target_col = config.get("splits", {}).get("source_target_col")
    source_values = config.get("splits", {}).get("source_values")
    target_values = config.get("splits", {}).get("target_values")
    covariate_shift_policy_id = config.get("splits", {}).get(
        "covariate_shift_policy_id"
    )
    duplicate_cluster_scope = config.get("splits", {}).get("duplicate_cluster_scope")
    feature_drop_columns = [
        str(col)
        for col in DATASET_LOADERS.get(dataset_id, {}).get("feature_drop_columns", [])
    ]
    payload = {
        "artifact_schema": "prediction_bundle_v5",
        "dataset_id": dataset_id,
        "target": target,
        "group_col": group_col,
        "model_id": model_id,
        "model_family": model_family,
        "model_params": model_params,
        "seed": seed,
        "target_transform": target_transform,
        "splits": {
            "train": float(config["splits"]["train"]),
            "calibration": float(config["splits"]["calibration"]),
            "test": 1.0
            - float(config["splits"]["train"])
            - float(config["splits"]["calibration"]),
            "group_col": None if split_group_col is None else str(split_group_col),
        },
        "feature_drop_policy": {
            "target": target,
            "primary_group_col": group_col,
            "split_group_col": None if split_group_col is None else str(split_group_col),
            "drop_split_group_col": split_group_col is not None,
        },
        "preprocessing": asdict(PreprocessingConfig()),
        "feature_reducer": feature_reducer_config(config),
        "data_provenance": data_provenance,
        "code_provenance": code_provenance,
    }
    if split_strategy is not None:
        payload["splits"]["strategy"] = str(split_strategy)
    if split_order_col is not None:
        payload["splits"]["order_col"] = str(split_order_col)
    if source_target_col is not None:
        payload["splits"]["source_target_col"] = str(source_target_col)
    if source_values is not None:
        payload["splits"]["source_values"] = [str(item) for item in source_values]
    if target_values is not None:
        payload["splits"]["target_values"] = [str(item) for item in target_values]
    if covariate_shift_policy_id is not None:
        payload["splits"]["covariate_shift_policy_id"] = str(
            covariate_shift_policy_id
        )
    if duplicate_cluster_scope is not None:
        payload["splits"]["duplicate_cluster_scope"] = str(duplicate_cluster_scope)
        payload["feature_drop_policy"]["duplicate_cluster_split_col"] = (
            DUPLICATE_CLUSTER_SPLIT_COL
        )
        payload["feature_drop_policy"]["base_split_group_col"] = (
            None if split_group_col is None else str(split_group_col)
        )
        payload["feature_drop_policy"]["drop_base_split_group_col"] = (
            split_group_col is not None
        )
    if feature_drop_columns:
        payload["feature_drop_policy"]["extra_feature_drop_columns"] = (
            feature_drop_columns
        )
    return payload


def fit_or_load_prediction_bundle(
    dataset_id: str,
    df: pd.DataFrame,
    target: str,
    group_col: str,
    model_id: str,
    model_family: str,
    model_params: Dict,
    seed: int,
    config: Dict,
    cache_root: Path,
    force: bool,
) -> PredictionBundle:
    split_group_col = config.get("splits", {}).get("group_col")
    split_strategy = config.get("splits", {}).get("strategy")
    split_order_col = config.get("splits", {}).get("order_col")
    source_target_col = config.get("splits", {}).get("source_target_col")
    source_values = config.get("splits", {}).get("source_values")
    target_values = config.get("splits", {}).get("target_values")
    duplicate_cluster_scope = config.get("splits", {}).get("duplicate_cluster_scope")
    data_provenance = {
        "schema": "cpfi_regression_data_provenance_v1",
        "dataset_loader_schema": DATASET_LOADER_SCHEMA,
        "dataset_id": dataset_id,
        "source": DATASET_LOADERS.get(dataset_id, {}).get("source"),
        "target": target,
        "group_col": group_col,
        "frame_fingerprint": dataframe_fingerprint(df),
    }
    code_provenance = runtime_provenance()
    payload = prediction_artifact_payload(
        dataset_id,
        target,
        group_col,
        model_id,
        model_family,
        model_params,
        seed,
        config,
        data_provenance=data_provenance,
        code_provenance=code_provenance,
    )
    artifact_id = stable_run_id(payload)
    cached = None if force else load_prediction_bundle(cache_root, artifact_id)

    split_df, effective_split_group_col = add_duplicate_cluster_split_group(
        df,
        dataset_id=dataset_id,
        target=target,
        group_col=group_col,
        split_group_col=None if split_group_col is None else str(split_group_col),
        scope=None if duplicate_cluster_scope is None else str(duplicate_cluster_scope),
    )
    splits = split_frame(
        split_df,
        target=target,
        group_col=group_col,
        seed=seed,
        train_size=float(config["splits"]["train"]),
        calibration_size=float(config["splits"]["calibration"]),
        split_group_col=effective_split_group_col,
        split_strategy=None if split_strategy is None else str(split_strategy),
        split_order_col=None if split_order_col is None else str(split_order_col),
        source_target_col=(
            None if source_target_col is None else str(source_target_col)
        ),
        source_values=None if source_values is None else list(source_values),
        target_values=None if target_values is None else list(target_values),
    )
    train_df, cal_df, test_df = splits["train"], splits["cal"], splits["test"]
    groups_cal = cal_df[group_col].astype(str).to_numpy()
    groups_test = test_df[group_col].astype(str).to_numpy()
    split_groups_train = None
    if effective_split_group_col is not None:
        split_groups_train = (
            train_df[str(effective_split_group_col)]
            .astype("object")
            .where(train_df[str(effective_split_group_col)].notna(), "__missing__")
            .astype(str)
            .to_numpy()
        )
    target_transform = target_transform_for_dataset(config, dataset_id)
    y_train_raw = pd.to_numeric(train_df[target], errors="coerce").to_numpy(dtype=float)
    y_cal_raw = pd.to_numeric(cal_df[target], errors="coerce").to_numpy(dtype=float)
    y_test_raw = pd.to_numeric(test_df[target], errors="coerce").to_numpy(dtype=float)
    y_train = transform_target(y_train_raw, target_transform)
    y_cal = transform_target(y_cal_raw, target_transform)

    feature_drop = runner_feature_drop_columns(
        dataset_id,
        target,
        group_col,
        effective_split_group_col,
        train_df,
        base_split_group_col=(
            None
            if duplicate_cluster_scope is None or split_group_col is None
            else str(split_group_col)
        ),
    )
    X_train = train_df.drop(columns=feature_drop)
    X_cal = cal_df.drop(columns=feature_drop)
    X_test = test_df.drop(columns=feature_drop)
    if cached is not None:
        return replace(
            cached,
            X_train_raw=X_train.copy(),
            X_test_raw=X_test.copy(),
        )
    preprocessor = fit_preprocessing(X_train, PreprocessingConfig())
    X_train_p = apply_preprocessing(X_train, preprocessor)
    X_cal_p = apply_preprocessing(X_cal, preprocessor)
    X_test_p = apply_preprocessing(X_test, preprocessor)
    X_train_arr = X_train_p.to_numpy(dtype=float)
    X_cal_arr = X_cal_p.to_numpy(dtype=float)
    X_test_arr = X_test_p.to_numpy(dtype=float)
    preprocessed_feature_names = list(X_train_p.columns)
    X_train_pre_feature_reducer = X_train_arr.copy()
    X_cal_pre_feature_reducer = X_cal_arr.copy()
    X_test_pre_feature_reducer = X_test_arr.copy()
    (
        X_train_arr,
        X_cal_arr,
        X_test_arr,
        feature_names,
        feature_reducer_metadata,
    ) = apply_feature_reducer(
        X_train_arr,
        y_train,
        X_cal_arr,
        X_test_arr,
        preprocessed_feature_names,
        config,
        seed,
    )

    start = time.time()
    model = make_model(model_id, model_params, seed)
    model.fit(X_train_arr, y_train)
    yhat_train = model.predict(X_train_arr)
    yhat_cal = model.predict(X_cal_arr)
    yhat_test = model.predict(X_test_arr)
    scale_cal, scale_test = fit_residual_scale(
        X_train_arr, y_train, yhat_train, X_cal_arr, X_test_arr, seed
    )
    fit_seconds = time.time() - start

    split_group_counts = {"train": None, "cal": None, "test": None}
    if effective_split_group_col is not None:
        split_group_col_for_counts = str(effective_split_group_col)
        split_group_counts = {
            split_name: int(
                splits[split_name][split_group_col_for_counts].nunique(dropna=False)
            )
            for split_name in ["train", "cal", "test"]
        }

    arrays = {
        "y_train": y_train,
        "y_cal": y_cal,
        "y_test": y_test_raw,
        "y_train_raw": y_train_raw,
        "y_cal_raw": y_cal_raw,
        "y_test_raw": y_test_raw,
        "yhat_train": yhat_train,
        "yhat_cal": yhat_cal,
        "yhat_test": yhat_test,
        "groups_cal": groups_cal.astype(str),
        "groups_test": groups_test.astype(str),
        "X_train": X_train_arr,
        "X_cal": X_cal_arr,
        "X_test": X_test_arr,
        "X_train_pre_feature_reducer": X_train_pre_feature_reducer,
        "X_cal_pre_feature_reducer": X_cal_pre_feature_reducer,
        "X_test_pre_feature_reducer": X_test_pre_feature_reducer,
        "scale_cal": scale_cal,
        "scale_test": scale_test,
    }
    if split_groups_train is not None:
        arrays["split_groups_train"] = split_groups_train.astype(str)
    metadata = {
        **payload,
        "artifact_id": artifact_id,
        "fit_seconds": fit_seconds,
        "feature_count": int(X_train_arr.shape[1]),
        "feature_names": feature_names,
        "preprocessed_feature_count": int(X_train_p.shape[1]),
        "preprocessed_feature_names": preprocessed_feature_names,
        "feature_reducer_metadata": feature_reducer_metadata,
        "feature_drop_columns": feature_drop,
        "row_counts": {
            "train": int(len(y_train)),
            "calibration": int(len(y_cal)),
            "test": int(len(y_test_raw)),
        },
        "split_group_counts": split_group_counts,
        "split_group_col": (
            None if effective_split_group_col is None else str(effective_split_group_col)
        ),
        "split_groups_train_available": split_groups_train is not None,
        "split_groups_train_unique": (
            None if split_groups_train is None else int(pd.Series(split_groups_train).nunique())
        ),
        "created_at": time.time(),
    }
    artifact_dir = write_prediction_bundle(cache_root, artifact_id, metadata, arrays)
    return PredictionBundle(
        artifact_id=artifact_id,
        artifact_dir=artifact_dir,
        cache_status="miss",
        fit_seconds=fit_seconds,
        y_train=y_train,
        y_cal=y_cal,
        y_test=y_test_raw,
        yhat_train=yhat_train,
        yhat_cal=yhat_cal,
        yhat_test=yhat_test,
        groups_cal=groups_cal,
        groups_test=groups_test,
        split_groups_train=split_groups_train,
        X_train=X_train_arr,
        X_cal=X_cal_arr,
        X_test=X_test_arr,
        X_train_pre_feature_reducer=X_train_pre_feature_reducer,
        X_cal_pre_feature_reducer=X_cal_pre_feature_reducer,
        X_test_pre_feature_reducer=X_test_pre_feature_reducer,
        scale_cal=scale_cal,
        scale_test=scale_test,
        target_transform=target_transform,
        preprocessed_feature_names=preprocessed_feature_names,
        X_train_raw=X_train.copy(),
        X_test_raw=X_test.copy(),
    )


def build_interval(
    cp_method: str,
    alpha: float,
    y_cal: np.ndarray,
    yhat_cal: np.ndarray,
    yhat_test: np.ndarray,
    groups_cal: np.ndarray,
    groups_test: np.ndarray,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    yhat_train: np.ndarray,
    X_cal: pd.DataFrame,
    X_test: pd.DataFrame,
    seed: int,
    model_id: str,
    model_params: Dict,
    scale_cal: np.ndarray | None = None,
    scale_test: np.ndarray | None = None,
    cv_plus_folds: int = 5,
    cv_plus_max_train_rows: int | None = None,
    jackknife_plus_max_train_rows: int | None = None,
    jackknife_after_bootstrap_n_resamples: int = 50,
    jackknife_after_bootstrap_sample_fraction: float = 1.0,
    jackknife_after_bootstrap_min_oob: int = 1,
    jackknife_after_bootstrap_max_train_rows: int | None = None,
    covariate_shift_probability_clip: float = 0.01,
    covariate_shift_weight_clip: float = 20.0,
    venn_abers_m: int = 1,
    cqr_params: Dict | None = None,
    split_groups_train: np.ndarray | None = None,
    X_train_pre_feature_reducer: np.ndarray | None = None,
    X_test_pre_feature_reducer: np.ndarray | None = None,
    X_train_raw: pd.DataFrame | None = None,
    X_test_raw: pd.DataFrame | None = None,
    preprocessed_feature_names: List[str] | None = None,
    feature_reducer_source_config: Dict | None = None,
):
    if cp_method == "split_abs":
        return split_conformal_interval(y_cal, yhat_cal, yhat_test, alpha)
    if cp_method == "split_tail_grid_shortest":
        return split_tail_grid_shortest_interval(y_cal, yhat_cal, yhat_test, alpha)
    if cp_method.startswith("split_tail_"):
        lower_tail_alpha_fraction = float(cp_method.rsplit("_", 1)[1])
        return split_tail_conformal_interval(
            y_cal,
            yhat_cal,
            yhat_test,
            alpha,
            lower_tail_alpha_fraction=lower_tail_alpha_fraction,
        )
    if cp_method == "mondrian_abs":
        return mondrian_conformal_interval(
            y_cal, yhat_cal, yhat_test, groups_cal, groups_test, alpha
        )
    if cp_method.startswith("shrink_"):
        gamma = float(cp_method.split("_", 1)[1])
        return shrinkage_conformal_interval(
            y_cal, yhat_cal, yhat_test, groups_cal, groups_test, alpha, gamma=gamma
        )
    if cp_method == "normalized_abs":
        if scale_cal is None or scale_test is None:
            scale_cal, scale_test = fit_residual_scale(
                X_train, y_train, yhat_train, X_cal, X_test, seed
            )
        return normalized_conformal_interval(
            y_cal, yhat_cal, yhat_test, scale_cal, scale_test, alpha
        )
    if cp_method == "weighted_abs_covariate_shift":
        cal_weights, test_weights, weight_metadata = estimate_covariate_shift_weights(
            X_cal,
            X_test,
            seed,
            probability_clip=covariate_shift_probability_clip,
            weight_clip=covariate_shift_weight_clip,
        )
        result = weighted_split_conformal_interval(
            y_cal,
            yhat_cal,
            yhat_test,
            cal_weights,
            test_weights,
            alpha,
        )
        infinite_radius_count = int(np.sum(~np.isfinite(result.radii)))
        if infinite_radius_count:
            raise MethodSkipped(
                "weighted_abs_covariate_shift skipped: "
                f"{infinite_radius_count} test rows received infinite radii; "
                "review density-ratio estimation, weight clipping, or calibration coverage "
                "before finite interval metrics are reported"
            )
        metadata = {
            **result.metadata,
            **weight_metadata,
            "weight_estimation": "estimated_from_unlabeled_calibration_and_test_covariates",
        }
        return type(result)(
            lower=result.lower,
            upper=result.upper,
            radii=result.radii,
            thresholds=result.thresholds,
            metadata=metadata,
        )
    if cp_method == "cqr":
        lower_cal, upper_cal, lower_test, upper_test, cqr_metadata = fit_cqr_models(
            X_train, y_train, X_cal, X_test, alpha, seed, cqr_params=cqr_params
        )
        result = conformalized_quantile_interval(
            y_cal, lower_cal, upper_cal, lower_test, upper_test, alpha
        )
        return type(result)(
            lower=result.lower,
            upper=result.upper,
            radii=result.radii,
            thresholds=result.thresholds,
            metadata={**result.metadata, **cqr_metadata},
        )
    if cp_method == "cqr_model_matched":
        lower_cal, upper_cal, lower_test, upper_test, cqr_metadata = (
            fit_cqr_model_matched_models(
                X_train,
                y_train,
                X_cal,
                X_test,
                alpha,
                seed,
                model_id=model_id,
                model_params=model_params,
                cqr_params=cqr_params,
            )
        )
        result = conformalized_quantile_interval(
            y_cal, lower_cal, upper_cal, lower_test, upper_test, alpha
        )
        return type(result)(
            lower=result.lower,
            upper=result.upper,
            radii=result.radii,
            thresholds=result.thresholds,
            metadata={
                **result.metadata,
                **cqr_metadata,
                "method": "cqr_model_matched",
                "base_conformal_method": "conformalized_quantile_regression",
                "historical_cqr_comparator": "cqr_fixed_gradient_boosting_backend",
            },
        )
    if cp_method == "venn_abers_quantile":
        qhat_cal, qhat_test = fit_residual_quantile_scores(
            X_train, y_train, yhat_train, X_cal, X_test, alpha, seed
        )
        return venn_abers_quantile_interval(
            y_cal,
            yhat_cal,
            yhat_test,
            qhat_cal,
            qhat_test,
            alpha,
            m=venn_abers_m,
        )
    if cp_method == "venn_abers_split_fallback":
        qhat_cal, qhat_test = fit_residual_quantile_scores(
            X_train, y_train, yhat_train, X_cal, X_test, alpha, seed
        )
        return venn_abers_split_fallback_interval(
            y_cal,
            yhat_cal,
            yhat_test,
            qhat_cal,
            qhat_test,
            alpha,
            m=venn_abers_m,
        )
    if cp_method == "cv_plus":
        if cv_plus_max_train_rows is not None and len(y_train) > cv_plus_max_train_rows:
            raise MethodSkipped(
                f"cv_plus skipped: n_train={len(y_train)} exceeds "
                f"cv_plus_max_train_rows={cv_plus_max_train_rows}"
            )
        yhat_train_oof, yhat_test_by_fold, fold_ids = fit_cv_plus_predictions(
            model_id,
            model_params,
            X_train,
            y_train,
            X_test,
            seed,
            n_folds=cv_plus_folds,
            X_train_pre_feature_reducer=X_train_pre_feature_reducer,
            X_test_pre_feature_reducer=X_test_pre_feature_reducer,
            X_train_raw=X_train_raw,
            X_test_raw=X_test_raw,
            preprocessed_feature_names=preprocessed_feature_names,
            config=feature_reducer_source_config,
        )
        result = cv_plus_interval(
            y_train, yhat_train_oof, yhat_test_by_fold, fold_ids, alpha
        )
        metadata = {
            **result.metadata,
            **plus_fold_feature_reducer_metadata(
                applied=plus_feature_reducer_fold_local_applied(
                    X_train_pre_feature_reducer,
                    X_test_pre_feature_reducer,
                    X_train_raw,
                    X_test_raw,
                    preprocessed_feature_names,
                    feature_reducer_source_config,
                ),
                config=feature_reducer_source_config,
                preprocessing_applied=fold_local_preprocessing_available(
                    X_train_raw,
                    X_test_raw,
                    feature_reducer_source_config,
                ),
            ),
        }
        return type(result)(
            lower=result.lower,
            upper=result.upper,
            radii=result.radii,
            thresholds=result.thresholds,
            metadata=metadata,
        )
    if cp_method == "cv_minmax":
        if cv_plus_max_train_rows is not None and len(y_train) > cv_plus_max_train_rows:
            raise MethodSkipped(
                f"cv_minmax skipped: n_train={len(y_train)} exceeds "
                f"cv_plus_max_train_rows={cv_plus_max_train_rows}"
            )
        yhat_train_oof, yhat_test_by_fold, fold_ids = fit_cv_plus_predictions(
            model_id,
            model_params,
            X_train,
            y_train,
            X_test,
            seed,
            n_folds=cv_plus_folds,
            X_train_pre_feature_reducer=X_train_pre_feature_reducer,
            X_test_pre_feature_reducer=X_test_pre_feature_reducer,
            X_train_raw=X_train_raw,
            X_test_raw=X_test_raw,
            preprocessed_feature_names=preprocessed_feature_names,
            config=feature_reducer_source_config,
        )
        result = cv_minmax_interval(
            y_train, yhat_train_oof, yhat_test_by_fold, fold_ids, alpha
        )
        metadata = {
            **result.metadata,
            **plus_fold_feature_reducer_metadata(
                applied=plus_feature_reducer_fold_local_applied(
                    X_train_pre_feature_reducer,
                    X_test_pre_feature_reducer,
                    X_train_raw,
                    X_test_raw,
                    preprocessed_feature_names,
                    feature_reducer_source_config,
                ),
                config=feature_reducer_source_config,
                preprocessing_applied=fold_local_preprocessing_available(
                    X_train_raw,
                    X_test_raw,
                    feature_reducer_source_config,
                ),
            ),
        }
        return type(result)(
            lower=result.lower,
            upper=result.upper,
            radii=result.radii,
            thresholds=result.thresholds,
            metadata=metadata,
        )
    if cp_method in {"cv_plus_grouped", "cv_minmax_grouped"}:
        if cv_plus_max_train_rows is not None and len(y_train) > cv_plus_max_train_rows:
            raise MethodSkipped(
                f"{cp_method} skipped: n_train={len(y_train)} exceeds "
                f"cv_plus_max_train_rows={cv_plus_max_train_rows}"
            )
        if split_groups_train is None:
            raise MethodSkipped(
                f"{cp_method} skipped: split_groups_train is unavailable in the "
                "prediction bundle; rebuild the bundle with a split_group_col or "
                "duplicate_cluster_split scope"
            )
        yhat_train_oof, yhat_test_by_fold, fold_ids, grouped_metadata = (
            fit_grouped_cv_plus_predictions(
                model_id,
                model_params,
                X_train,
                y_train,
                X_test,
                split_groups_train,
                seed,
                n_folds=cv_plus_folds,
                method_name=cp_method,
                X_train_pre_feature_reducer=X_train_pre_feature_reducer,
                X_test_pre_feature_reducer=X_test_pre_feature_reducer,
                X_train_raw=X_train_raw,
                X_test_raw=X_test_raw,
                preprocessed_feature_names=preprocessed_feature_names,
                config=feature_reducer_source_config,
            )
        )
        if cp_method == "cv_plus_grouped":
            result = cv_plus_interval(
                y_train, yhat_train_oof, yhat_test_by_fold, fold_ids, alpha
            )
            base_method = "cv_plus"
        else:
            result = cv_minmax_interval(
                y_train, yhat_train_oof, yhat_test_by_fold, fold_ids, alpha
            )
            base_method = "cv_minmax"
        metadata = {
            **result.metadata,
            **grouped_metadata,
            "method": cp_method,
            "base_method": base_method,
            "grouped_variant_role": "split_group_preserving_internal_cv",
        }
        return type(result)(
            lower=result.lower,
            upper=result.upper,
            radii=result.radii,
            thresholds=result.thresholds,
            metadata=metadata,
        )
    if cp_method == "jackknife_plus":
        yhat_train_loo, yhat_test_loo = fit_jackknife_plus_predictions(
            model_id,
            model_params,
            X_train,
            y_train,
            X_test,
            seed,
            max_train_rows=jackknife_plus_max_train_rows,
            X_train_pre_feature_reducer=X_train_pre_feature_reducer,
            X_test_pre_feature_reducer=X_test_pre_feature_reducer,
            X_train_raw=X_train_raw,
            X_test_raw=X_test_raw,
            preprocessed_feature_names=preprocessed_feature_names,
            config=feature_reducer_source_config,
        )
        result = jackknife_plus_interval(y_train, yhat_train_loo, yhat_test_loo, alpha)
        metadata = {
            **result.metadata,
            **plus_fold_feature_reducer_metadata(
                applied=plus_feature_reducer_fold_local_applied(
                    X_train_pre_feature_reducer,
                    X_test_pre_feature_reducer,
                    X_train_raw,
                    X_test_raw,
                    preprocessed_feature_names,
                    feature_reducer_source_config,
                ),
                config=feature_reducer_source_config,
                preprocessing_applied=fold_local_preprocessing_available(
                    X_train_raw,
                    X_test_raw,
                    feature_reducer_source_config,
                ),
            ),
        }
        return type(result)(
            lower=result.lower,
            upper=result.upper,
            radii=result.radii,
            thresholds=result.thresholds,
            metadata=metadata,
        )
    if cp_method == "jackknife_minmax":
        yhat_train_loo, yhat_test_loo = fit_jackknife_plus_predictions(
            model_id,
            model_params,
            X_train,
            y_train,
            X_test,
            seed,
            max_train_rows=jackknife_plus_max_train_rows,
            X_train_pre_feature_reducer=X_train_pre_feature_reducer,
            X_test_pre_feature_reducer=X_test_pre_feature_reducer,
            X_train_raw=X_train_raw,
            X_test_raw=X_test_raw,
            preprocessed_feature_names=preprocessed_feature_names,
            config=feature_reducer_source_config,
        )
        result = jackknife_minmax_interval(y_train, yhat_train_loo, yhat_test_loo, alpha)
        metadata = {
            **result.metadata,
            **plus_fold_feature_reducer_metadata(
                applied=plus_feature_reducer_fold_local_applied(
                    X_train_pre_feature_reducer,
                    X_test_pre_feature_reducer,
                    X_train_raw,
                    X_test_raw,
                    preprocessed_feature_names,
                    feature_reducer_source_config,
                ),
                config=feature_reducer_source_config,
                preprocessing_applied=fold_local_preprocessing_available(
                    X_train_raw,
                    X_test_raw,
                    feature_reducer_source_config,
                ),
            ),
        }
        return type(result)(
            lower=result.lower,
            upper=result.upper,
            radii=result.radii,
            thresholds=result.thresholds,
            metadata=metadata,
        )
    if cp_method == "jackknife_plus_after_bootstrap":
        yhat_train_oob, yhat_test_oob, oob_counts = fit_jackknife_after_bootstrap_predictions(
            model_id,
            model_params,
            X_train,
            y_train,
            X_test,
            seed,
            n_resamples=jackknife_after_bootstrap_n_resamples,
            sample_fraction=jackknife_after_bootstrap_sample_fraction,
            min_oob_models=jackknife_after_bootstrap_min_oob,
            max_train_rows=jackknife_after_bootstrap_max_train_rows,
        )
        result = jackknife_after_bootstrap_interval(
            y_train,
            yhat_train_oob,
            yhat_test_oob,
            alpha,
            oob_counts=oob_counts,
        )
        metadata = {
            **result.metadata,
            "n_resamples": int(jackknife_after_bootstrap_n_resamples),
            "sample_fraction": float(jackknife_after_bootstrap_sample_fraction),
            "min_oob_models_required": int(jackknife_after_bootstrap_min_oob),
        }
        return type(result)(
            lower=result.lower,
            upper=result.upper,
            radii=result.radii,
            thresholds=result.thresholds,
            metadata=metadata,
        )
    raise ValueError(f"Unsupported cp_method: {cp_method}")


def split_frame(
    df: pd.DataFrame,
    target: str,
    group_col: str,
    seed: int,
    train_size: float,
    calibration_size: float,
    split_group_col: str | None = None,
    split_strategy: str | None = None,
    split_order_col: str | None = None,
    source_target_col: str | None = None,
    source_values: list[Any] | tuple[Any, ...] | None = None,
    target_values: list[Any] | tuple[Any, ...] | None = None,
) -> Dict[str, pd.DataFrame]:
    df = df.dropna(subset=[target]).reset_index(drop=True)
    if not 0 < train_size < 1:
        raise ValueError(f"train_size must be in (0, 1), got {train_size}")
    if not 0 < calibration_size < 1:
        raise ValueError(f"calibration_size must be in (0, 1), got {calibration_size}")
    if train_size + calibration_size >= 1:
        raise ValueError(
            "train_size + calibration_size must leave a positive test split, "
            f"got {train_size + calibration_size}"
        )

    relative_cal_size = calibration_size / (1.0 - train_size)
    strategy = "random" if split_strategy is None else str(split_strategy)
    if strategy not in {"random", "ordered", "source_target"}:
        raise ValueError(f"unsupported split strategy {strategy!r}")

    if strategy == "source_target":
        if source_target_col is None:
            raise ValueError("source_target split strategy requires source_target_col")
        if target_values is None:
            raise ValueError("source_target split strategy requires target_values")
        source_target_col = str(source_target_col)
        if source_target_col not in df.columns:
            raise ValueError(f"source_target_col {source_target_col!r} not found")

        domain = (
            df[source_target_col]
            .astype("object")
            .where(df[source_target_col].notna(), "__missing__")
            .astype(str)
        )
        target_value_set = {str(value) for value in target_values}
        if not target_value_set:
            raise ValueError("source_target split strategy received empty target_values")
        if source_values is None:
            source_value_set = set(domain.unique()) - target_value_set
        else:
            source_value_set = {str(value) for value in source_values}
        if not source_value_set:
            raise ValueError("source_target split strategy received empty source_values")
        if source_value_set & target_value_set:
            overlap = sorted(source_value_set & target_value_set)
            raise ValueError(
                "source_target split strategy requires disjoint source/target "
                f"values, overlap={overlap}"
            )

        source_df = df.loc[domain.isin(source_value_set)].copy()
        target_df = df.loc[domain.isin(target_value_set)].copy()
        if min(len(source_df), len(target_df)) == 0:
            raise ValueError(
                "source_target split produced an empty domain: "
                f"source={len(source_df)}, target={len(target_df)}"
            )
        source_train_fraction = train_size / (train_size + calibration_size)
        train_df, cal_df = train_test_split(
            source_df,
            train_size=source_train_fraction,
            random_state=seed,
        )
        test_df = target_df
        if min(len(train_df), len(cal_df), len(test_df)) == 0:
            raise ValueError(
                "source_target split produced an empty split: "
                f"train={len(train_df)}, calibration={len(cal_df)}, "
                f"test={len(test_df)}"
            )
    elif strategy == "ordered":
        if split_order_col is None:
            raise ValueError("ordered split strategy requires split_order_col")
        split_order_col = str(split_order_col)
        if split_order_col not in df.columns:
            raise ValueError(f"split_order_col {split_order_col!r} not found")
        if split_group_col is None:
            ordered_df = df.sort_values(split_order_col, kind="mergesort")
            n_rows = len(ordered_df)
            train_end = int(np.floor(train_size * n_rows))
            cal_end = train_end + int(np.floor(calibration_size * n_rows))
            if min(train_end, cal_end - train_end, n_rows - cal_end) <= 0:
                raise ValueError(
                    "ordered row split produced an empty split: "
                    f"train={train_end}, calibration={cal_end - train_end}, "
                    f"test={n_rows - cal_end}"
                )
            train_df = ordered_df.iloc[:train_end].copy()
            cal_df = ordered_df.iloc[train_end:cal_end].copy()
            test_df = ordered_df.iloc[cal_end:].copy()
        else:
            split_group_col = str(split_group_col)
            if split_group_col not in df.columns:
                raise ValueError(f"split_group_col {split_group_col!r} not found")
            group_order_frame = pd.DataFrame(
                {
                    "_split_group_key": (
                        df[split_group_col]
                        .astype("object")
                        .where(df[split_group_col].notna(), "__missing__")
                        .astype(str)
                    ),
                    "_split_order_key": df[split_order_col],
                }
            )
            group_order = (
                group_order_frame.groupby("_split_group_key", dropna=False)[
                    "_split_order_key"
                ]
                .min()
                .sort_values(kind="mergesort")
            )
            ordered_groups = np.array(group_order.index, dtype=object)
            n_groups = len(ordered_groups)
            train_group_end = int(np.floor(train_size * n_groups))
            cal_group_end = train_group_end + int(np.floor(calibration_size * n_groups))
            if min(
                train_group_end,
                cal_group_end - train_group_end,
                n_groups - cal_group_end,
            ) <= 0:
                raise ValueError(
                    "ordered grouped split produced an empty split: "
                    f"train_groups={train_group_end}, "
                    f"calibration_groups={cal_group_end - train_group_end}, "
                    f"test_groups={n_groups - cal_group_end}"
                )
            split_groups = (
                df[split_group_col]
                .astype("object")
                .where(df[split_group_col].notna(), "__missing__")
                .astype(str)
            )
            train_groups = ordered_groups[:train_group_end]
            cal_groups = ordered_groups[train_group_end:cal_group_end]
            test_groups = ordered_groups[cal_group_end:]
            train_df = df.loc[split_groups.isin(train_groups)].copy()
            cal_df = df.loc[split_groups.isin(cal_groups)].copy()
            test_df = df.loc[split_groups.isin(test_groups)].copy()
            if min(len(train_df), len(cal_df), len(test_df)) == 0:
                raise ValueError(
                    "ordered grouped split produced an empty row split: "
                    f"train={len(train_df)}, calibration={len(cal_df)}, "
                    f"test={len(test_df)}"
                )
    elif split_group_col is None:
        train_df, rest_df = train_test_split(df, train_size=train_size, random_state=seed)
        cal_df, test_df = train_test_split(
            rest_df, train_size=relative_cal_size, random_state=seed
        )
    else:
        split_group_col = str(split_group_col)
        if split_group_col not in df.columns:
            raise ValueError(f"split_group_col {split_group_col!r} not found")
        split_groups = (
            df[split_group_col]
            .astype("object")
            .where(df[split_group_col].notna(), "__missing__")
            .astype(str)
        )
        unique_groups = np.array(sorted(split_groups.unique()), dtype=object)
        if len(unique_groups) < 3:
            raise ValueError(
                f"grouped split on {split_group_col!r} requires at least 3 groups, "
                f"got {len(unique_groups)}"
            )
        train_groups, rest_groups = train_test_split(
            unique_groups,
            train_size=train_size,
            random_state=seed,
        )
        if len(rest_groups) < 2:
            raise ValueError(
                f"grouped split on {split_group_col!r} left fewer than 2 rest groups"
            )
        cal_groups, test_groups = train_test_split(
            rest_groups,
            train_size=relative_cal_size,
            random_state=seed,
        )
        train_mask = split_groups.isin(train_groups)
        cal_mask = split_groups.isin(cal_groups)
        test_mask = split_groups.isin(test_groups)
        train_df = df.loc[train_mask].copy()
        cal_df = df.loc[cal_mask].copy()
        test_df = df.loc[test_mask].copy()
        if min(len(train_df), len(cal_df), len(test_df)) == 0:
            raise ValueError(
                f"grouped split on {split_group_col!r} produced an empty split: "
                f"train={len(train_df)}, calibration={len(cal_df)}, test={len(test_df)}"
            )

    return {
        "train": train_df.reset_index(drop=True),
        "cal": cal_df.reset_index(drop=True),
        "test": test_df.reset_index(drop=True),
        "group_col": group_col,
        "split_group_col": split_group_col,
        "split_strategy": strategy,
        "split_order_col": split_order_col,
        "source_target_col": source_target_col,
        "source_values": None
        if source_values is None
        else [str(value) for value in source_values],
        "target_values": None
        if target_values is None
        else [str(value) for value in target_values],
    }


def run_one(
    dataset_id: str,
    model_id: str,
    model_family: str,
    model_params: Dict,
    cp_method: str,
    alpha: float,
    seed: int,
    config: Dict,
    checkpoint_root: Path,
    prediction_cache_root: Path,
    audit_root: Path,
    force: bool,
    dataset_cache: Dict[str, Tuple[pd.DataFrame, str, str]],
    audited_datasets: set[str],
) -> Dict:
    payload = run_payload(
        dataset_id, model_id, model_params, cp_method, alpha, seed, config=config
    )
    run_id = stable_run_id(payload)
    existing = load_run_record(checkpoint_root, run_id)
    existing_status = existing.get("status") if existing else None
    if existing_status in TERMINAL_CHECKPOINT_STATUSES and not force:
        return {"status": f"skipped_{existing_status}", "run_id": run_id}

    legacy_payload = run_payload(
        dataset_id, model_id, model_params, cp_method, alpha, seed
    )
    legacy_run_id = stable_run_id(legacy_payload)
    if legacy_run_id != run_id and not force and allows_legacy_run_id_resume(config):
        legacy_existing = load_run_record(checkpoint_root, legacy_run_id)
        legacy_status = legacy_existing.get("status") if legacy_existing else None
        if legacy_status in TERMINAL_CHECKPOINT_STATUSES:
            return {
                "status": f"skipped_{legacy_status}",
                "run_id": run_id,
                "legacy_run_id": legacy_run_id,
                "resume_source": "legacy_run_id_v1",
            }

    if dataset_id not in dataset_cache:
        dataset_cache[dataset_id] = load_dataset_frame(dataset_id)
    df, target, group_col = dataset_cache[dataset_id]

    audit_json_path = audit_root / dataset_id / "audit.json"
    audit_md_path = audit_root / dataset_id / "audit.md"
    if dataset_id not in audited_datasets and not audit_json_path.exists():
        audit = audit_regression_frame(df, target=target, dataset_id=dataset_id)
        audit_payload = audit.to_dict()
        atomic_write_json(audit_json_path, audit_payload)
        atomic_write_text(audit_md_path, render_audit_markdown(audit_payload))
        audited_datasets.add(dataset_id)

    bundle = fit_or_load_prediction_bundle(
        dataset_id=dataset_id,
        df=df,
        target=target,
        group_col=group_col,
        model_id=model_id,
        model_family=model_family,
        model_params=model_params,
        seed=seed,
        config=config,
        cache_root=prediction_cache_root,
        force=force,
    )
    interval_start = time.time()
    cp_method_id, cp_method_params = cp_method_settings(config, cp_method)
    try:
        interval = build_interval(
            cp_method_id,
            alpha,
            bundle.y_cal,
            bundle.yhat_cal,
            bundle.yhat_test,
            bundle.groups_cal,
            bundle.groups_test,
            bundle.X_train,
            bundle.y_train,
            bundle.yhat_train,
            bundle.X_cal,
            bundle.X_test,
            seed,
            model_id=model_id,
            model_params=model_params,
            scale_cal=bundle.scale_cal,
            scale_test=bundle.scale_test,
            cv_plus_folds=int(config.get("conformal", {}).get("cv_plus_folds", 5)),
            cv_plus_max_train_rows=config.get("conformal", {}).get(
                "cv_plus_max_train_rows"
            ),
            jackknife_plus_max_train_rows=config.get("conformal", {}).get(
                "jackknife_plus_max_train_rows"
            ),
            jackknife_after_bootstrap_n_resamples=int(
                config.get("conformal", {}).get("jackknife_after_bootstrap_n_resamples", 50)
            ),
            jackknife_after_bootstrap_sample_fraction=float(
                config.get("conformal", {}).get(
                    "jackknife_after_bootstrap_sample_fraction", 1.0
                )
            ),
            jackknife_after_bootstrap_min_oob=int(
                config.get("conformal", {}).get("jackknife_after_bootstrap_min_oob", 1)
            ),
            jackknife_after_bootstrap_max_train_rows=config.get("conformal", {}).get(
                "jackknife_after_bootstrap_max_train_rows"
            ),
            covariate_shift_probability_clip=float(
                config.get("conformal", {}).get("covariate_shift_probability_clip", 0.01)
            ),
            covariate_shift_weight_clip=float(
                config.get("conformal", {}).get("covariate_shift_weight_clip", 20.0)
            ),
            venn_abers_m=int(config.get("conformal", {}).get("venn_abers_m", 1)),
            cqr_params=(
                cp_method_params
                if cp_method_id in {"cqr", "cqr_model_matched"}
                else None
            ),
            split_groups_train=bundle.split_groups_train,
            X_train_pre_feature_reducer=bundle.X_train_pre_feature_reducer,
            X_test_pre_feature_reducer=bundle.X_test_pre_feature_reducer,
            X_train_raw=bundle.X_train_raw,
            X_test_raw=bundle.X_test_raw,
            preprocessed_feature_names=bundle.preprocessed_feature_names,
            feature_reducer_source_config=config,
        )
    except MethodSkipped as exc:
        record = RunRecord(
            run_id=run_id,
            dataset_id=dataset_id,
            model_id=model_id,
            cp_method=cp_method,
            split_seed=seed,
            alpha=alpha,
            status="skipped_method",
            artifact_paths=bundle.artifact_paths,
            metrics={},
            notes=(
                f"family={model_family}; params={json.dumps(model_params, sort_keys=True)}; "
                f"cp_method_id={cp_method_id}; "
                f"cp_params={json.dumps(cp_method_params, sort_keys=True)}; "
                f"prediction_artifact={bundle.artifact_id}; cache={bundle.cache_status}; "
                f"reason={exc}"
            ),
        )
        checkpoint_path = checkpoint_run(checkpoint_root, record)
        return {
            "status": "skipped_method",
            "run_id": run_id,
            "dataset_id": dataset_id,
            "model_id": model_id,
            "model_family": model_family,
            "model_params": model_params,
            "cp_method": cp_method,
            "cp_method_id": cp_method_id,
            "cp_method_params": cp_method_params,
            "alpha": alpha,
            "seed": seed,
            "fit_seconds": bundle.fit_seconds,
            "interval_seconds": time.time() - interval_start,
            "prediction_artifact": bundle.artifact_id,
            "prediction_cache_status": bundle.cache_status,
            "checkpoint": str(checkpoint_path),
            "skip_reason": str(exc),
        }
    interval_seconds = time.time() - interval_start
    lower_metric, lower_inverse_metadata = inverse_transform_target_with_metadata(
        interval.lower, bundle.target_transform
    )
    upper_metric, upper_inverse_metadata = inverse_transform_target_with_metadata(
        interval.upper, bundle.target_transform
    )
    cp_metadata = {
        **interval.metadata,
        "target_inverse_transform": {
            "target_transform": bundle.target_transform,
            "lower": lower_inverse_metadata,
            "upper": upper_inverse_metadata,
        },
    }
    metrics = compute_interval_metrics(
        y_true=bundle.y_test,
        lower=lower_metric,
        upper=upper_metric,
        alpha=alpha,
        groups=bundle.groups_test,
    )
    record = RunRecord(
        run_id=run_id,
        dataset_id=dataset_id,
        model_id=model_id,
        cp_method=cp_method,
        split_seed=seed,
        alpha=alpha,
        status="completed",
        artifact_paths=bundle.artifact_paths,
        metrics=asdict(metrics),
        cp_thresholds=interval.thresholds,
        cp_metadata=cp_metadata,
        notes=(
            f"family={model_family}; params={json.dumps(model_params, sort_keys=True)}; "
            f"cp_method_id={cp_method_id}; "
            f"cp_params={json.dumps(cp_method_params, sort_keys=True)}; "
            f"prediction_artifact={bundle.artifact_id}; cache={bundle.cache_status}"
        ),
    )
    checkpoint_path = checkpoint_run(checkpoint_root, record)

    return {
        "status": "completed",
        "run_id": run_id,
        "dataset_id": dataset_id,
        "model_id": model_id,
        "model_family": model_family,
        "model_params": model_params,
        "cp_method": cp_method,
        "cp_method_id": cp_method_id,
        "cp_method_params": cp_method_params,
        "alpha": alpha,
        "seed": seed,
        "fit_seconds": bundle.fit_seconds,
        "interval_seconds": interval_seconds,
        "prediction_artifact": bundle.artifact_id,
        "prediction_cache_status": bundle.cache_status,
        "checkpoint": str(checkpoint_path),
        "cp_thresholds": interval.thresholds,
        "cp_metadata": cp_metadata,
        **asdict(metrics),
    }


def _allowed(value, selected: Iterable | None) -> bool:
    if not selected:
        return True
    return str(value) in {str(item) for item in selected}


def iter_runs(config: Dict, args: argparse.Namespace) -> Iterator[Tuple]:
    for dataset_id in config["datasets"]:
        if not _allowed(dataset_id, args.dataset):
            continue
        for seed in config["random_seeds"]:
            if not _allowed(seed, args.seed):
                continue
            for model_id, family, params in iter_model_configs(config):
                if not _allowed(model_id, args.model_id):
                    continue
                for alpha in config["alphas"]:
                    if not _allowed(float(alpha), args.alpha):
                        continue
                    for cp_method in config["cp_methods"]:
                        if not _allowed(cp_method, args.cp_method):
                            continue
                        yield dataset_id, model_id, family, params, cp_method, float(alpha), int(seed)


def main() -> None:
    args = parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    ledger_path = Path(config["logging"]["ledger"])
    checkpoint_root = Path(config["logging"]["checkpoint_root"])
    prediction_cache_root = Path(
        config["logging"].get("prediction_cache_root", checkpoint_root / "predictions")
    )
    audit_root = Path("experiments/regression/audits")

    completed = 0
    dataset_cache: Dict[str, Tuple[pd.DataFrame, str, str]] = {}
    audited_datasets: set[str] = set()
    for run in iter_runs(config, args):
        if args.max_runs is not None and completed >= args.max_runs:
            break
        try:
            result = run_one(
                *run,
                config=config,
                checkpoint_root=checkpoint_root,
                prediction_cache_root=prediction_cache_root,
                audit_root=audit_root,
                force=args.force,
                dataset_cache=dataset_cache,
                audited_datasets=audited_datasets,
            )
        except Exception as exc:
            result = failed_result_from_exception(run, checkpoint_root, exc, config=config)
        if result["status"] not in RESUME_SKIP_STATUSES:
            append_jsonl(ledger_path, [result])
        print(json.dumps(result, sort_keys=True, default=str))
        if result["status"] == "completed":
            completed += 1


if __name__ == "__main__":
    main()
