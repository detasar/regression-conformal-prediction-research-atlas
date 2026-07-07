import pandas as pd

from experiments.regression.scripts.audit_college_scorecard_2026_earnings import (
    DATASET_ID,
    TARGET,
    build_model_frame,
    build_profile,
)


def test_build_profile_filters_scorecard_target_and_records_policy():
    source = pd.DataFrame(
        {
            "UNITID": [1, 2, 3, 4],
            "INSTNM": ["A", "B", "C", "D"],
            "CITY": ["x", "y", "z", "q"],
            "STABBR": ["CA", "TX", "NY", "CA"],
            "CONTROL": [1, 2, 1, 3],
            "REGION": [8, 6, 2, 8],
            "LOCALE": [11, 21, 12, 41],
            "CCBASIC": [15, 18, 20, 22],
            "HBCU": [0, 1, 0, 0],
            "PBI": [0, 1, 0, 0],
            "HSI": [1, 0, 0, 1],
            "MENONLY": [0, 0, 0, 0],
            "WOMENONLY": [0, 1, 0, 0],
            "UGDS": [1000, 2000, 1500, 800],
            "UGDS_BLACK": [0.1, 0.8, 0.2, 0.05],
            "UGDS_HISP": [0.5, 0.1, 0.2, 0.6],
            "UGDS_WHITE": [0.25, 0.05, 0.45, 0.2],
            "UGDS_ASIAN": [0.1, 0.02, 0.1, 0.08],
            "UGDS_MEN": [0.48, 0.4, 0.51, 0.47],
            "UGDS_WOMEN": [0.52, 0.6, 0.49, 0.53],
            "PCTPELL": [0.3, 0.7, 0.4, 0.5],
            "INC_PCT_LO": [0.35, 0.6, 0.25, 0.45],
            "FIRST_GEN": [0.2, 0.5, 0.3, 0.4],
            "ADM_RATE": [0.4, 0.8, 0.5, 0.7],
            "SAT_AVG": [1200, 900, 1100, 1000],
            "COSTT4_A": [30000, 22000, 41000, 18000],
            "PCIP11": [0.15, 0.02, 0.2, 0.01],
            TARGET: [60000, "PrivacySuppressed", 45000, 0],
            "MN_EARN_WNE_P10": [65000, 50000, 48000, 25000],
            "C150_4": [0.7, 0.4, 0.6, 0.2],
        }
    )

    model_frame, target_filter = build_model_frame(source)
    profile = build_profile(source, header=list(source.columns))

    assert profile["dataset_id"] == DATASET_ID
    assert model_frame.shape[0] == 2
    assert target_filter["target_missing_rows_before_drop"] == 1
    assert target_filter["target_nonpositive_rows_before_drop"] == 1
    assert "UNITID" not in model_frame.columns
    assert "STABBR" in model_frame.columns
    assert "MN_EARN_WNE_P10" not in model_frame.columns
    assert "C150_4" not in model_frame.columns
    assert "MN_EARN_WNE_P10" in profile["leakage_manifest"]["sample_matching_columns"]
    assert "HBCU" in profile["audit"]["sensitive_candidates"]
    assert "UGDS_BLACK" in profile["audit"]["sensitive_candidates"]
    assert "institution-level composition/proxy fields" in profile["audit"]["group_policy"]
    assert "Exclude all earnings fields" in profile["audit"]["leakage_policy"]
