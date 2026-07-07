import pandas as pd

from experiments.regression.scripts.audit_nhanes_glycohemoglobin import (
    DATASET_ID,
    TARGET,
    build_profile,
)


def test_build_profile_drops_missing_glycohemoglobin_and_records_policy():
    joined = pd.DataFrame(
        {
            "SEQN": [1, 2, 3],
            TARGET: [5.4, None, 8.1],
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
    assert "RIAGENDR" in profile["audit"]["sensitive_candidates"]
    assert "WTMEC2YR" in profile["audit"]["survey_design_columns"]
    assert "LBXGH" in profile["audit"]["target_policy"]
