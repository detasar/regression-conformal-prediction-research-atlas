import pandas as pd

from experiments.regression.scripts import audit_nhanes_bmi
from experiments.regression.scripts import run_regression_pilot as pilot


def test_build_profile_records_bmi_target_component_and_survey_policy():
    joined = pd.DataFrame(
        {
            "SEQN": [1, 2, 3],
            "BMXBMI": [25.0, None, 31.5],
            "RIDAGEYR": [25, 40, 80],
            "RIAGENDR": [1, 2, 1],
            "RIDRETH3": [3, 4, 6],
            "INDFMPIR": [2.0, 1.0, 5.0],
            "DMDEDUC2": [4, 3, 5],
            "DMDMARTL": [1, 5, 1],
            "BMXWT": [70.0, 80.0, 90.0],
            "BMXHT": [170.0, 165.0, 160.0],
            "BMXWAIST": [85.0, 90.0, 110.0],
            "BMXHIP": [95.0, 100.0, 120.0],
            "WTMEC2YR": [1.0, 2.0, 3.0],
            "SDMVSTRA": [100, 100, 101],
            "SDMVPSU": [1, 2, 1],
        }
    )

    profile = audit_nhanes_bmi.build_profile(joined, manifest=[])

    assert profile["dataset_id"] == audit_nhanes_bmi.DATASET_ID
    assert profile["shape"]["model_rows_after_target_drop"] == 2
    assert profile["audit"]["target_missing_rate_before_drop"] == 1 / 3
    assert profile["audit"]["target_component_drop_columns"] == ["BMXWT", "BMXHT"]
    assert "WTMEC2YR" in profile["audit"]["survey_design_columns"]
    assert profile["audit"]["sensitive_candidates"] == [
        "RIAGENDR",
        "RIDRETH3",
        "RIDAGEYR",
        "INDFMPIR",
    ]
    assert "never use BMXWT/BMXHT as model features" in profile["audit"]["target_policy"]


def test_nhanes_bmi_runner_frame_excludes_body_measurement_proxies(monkeypatch):
    source = pd.DataFrame(
        {
            "SEQN": [1, 2],
            "BMXBMI": [25.0, 31.5],
            "RIDAGEYR": [25, 80],
            "RIAGENDR": [1, 2],
            "RIDRETH3": [3, 4],
            "INDFMPIR": [2.0, 5.0],
            "DMDEDUC2": [4, 5],
            "DMDMARTL": [1, 1],
            "BMXWT": [70.0, 90.0],
            "BMXHT": [170.0, 160.0],
            "BMXWAIST": [85.0, 110.0],
            "BMXHIP": [95.0, 120.0],
            "WTMEC2YR": [1.0, 3.0],
            "SDMVSTRA": [100, 101],
            "SDMVPSU": [1, 1],
        }
    )

    monkeypatch.setattr(
        pilot,
        "load_nhanes_2017_2018_bmi_frame",
        lambda raw_dir, target: source.copy(),
    )

    df, target, group = pilot.load_dataset_frame("nhanes_2017_2018_bmi")

    assert target == "BMXBMI"
    assert group == "RIDRETH3"
    assert set(df.columns) == {
        "BMXBMI",
        "RIDAGEYR",
        "RIAGENDR",
        "RIDRETH3",
        "INDFMPIR",
        "DMDEDUC2",
        "DMDMARTL",
    }
    assert {"BMXWT", "BMXHT", "BMXWAIST", "BMXHIP"}.isdisjoint(df.columns)
    assert {"WTMEC2YR", "SDMVSTRA", "SDMVPSU"}.isdisjoint(df.columns)
