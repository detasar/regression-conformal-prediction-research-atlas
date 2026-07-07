import pandas as pd

from experiments.regression.scripts.audit_nhanes_systolic_bp import (
    DATASET_ID,
    TARGET,
    build_profile,
    derive_systolic_target,
)


def test_derive_systolic_target_averages_available_first_three_readings():
    bpx = pd.DataFrame(
        {
            "BPXSY1": [120, None, None],
            "BPXSY2": [122, 130, None],
            "BPXSY3": [124, 132, None],
        }
    )

    target = derive_systolic_target(bpx)

    assert target.iloc[0] == 122
    assert target.iloc[1] == 131
    assert pd.isna(target.iloc[2])


def test_build_profile_drops_rows_without_systolic_target_and_records_policy():
    joined = pd.DataFrame(
        {
            "SEQN": [1, 2, 3],
            TARGET: [122.0, None, 140.0],
            "BPXSY1": [120.0, None, 138.0],
            "BPXSY2": [122.0, None, 140.0],
            "BPXSY3": [124.0, None, 142.0],
            "RIDAGEYR": [25, 40, 80],
            "RIAGENDR": [1, 2, 1],
            "RIDRETH3": [3, 4, 6],
            "INDFMPIR": [2.0, 1.0, 5.0],
            "DMDEDUC2": [4, 3, 5],
            "DMDMARTL": [1, 5, 1],
            "WTMEC2YR": [1.0, 2.0, 3.0],
            "SDMVSTRA": [100, 100, 101],
            "SDMVPSU": [1, 2, 1],
        }
    )

    profile = build_profile(joined, manifest=[])

    assert profile["dataset_id"] == DATASET_ID
    assert profile["shape"]["model_rows_after_target_drop"] == 2
    assert profile["audit"]["target_missing_rate_before_drop"] == 1 / 3
    assert "BPXSY1" in profile["audit"]["target_component_drop_columns"]
    assert "WTMEC2YR" in profile["audit"]["survey_design_columns"]
