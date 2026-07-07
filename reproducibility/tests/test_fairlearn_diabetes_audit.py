from types import SimpleNamespace
import sys
import types

import pandas as pd

from experiments.regression.scripts import audit_fairlearn_diabetes_hospital_los as los
from experiments.regression.scripts import run_regression_pilot as pilot


def test_build_profile_records_groups_and_source_metadata():
    frame = pd.DataFrame(
        {
            "race": ["A", "B", "A", "B"],
            "gender": ["F", "M", "F", "M"],
            "age": ["young", "older", "older", "young"],
            "num_medications": [1, 3, 5, 7],
            "time_in_hospital": [1, 2, 4, 8],
        }
    )
    bunch = SimpleNamespace(DESCR="toy diabetes source")

    profile = los.build_profile(frame, bunch)

    assert profile["dataset_id"] == los.DATASET_ID
    assert profile["source"]["dropped_leakage_columns"] == los.LEAKAGE_DROP_COLUMNS
    assert [group["column"] for group in profile["group_profiles"]] == los.GROUP_COLUMNS
    assert profile["audit"]["sensitive_candidates"] == los.GROUP_COLUMNS


def test_runner_loader_supports_diabetes_los_and_drops_readmission_columns(monkeypatch):
    fake_frame = pd.DataFrame(
        {
            "race": ["Caucasian", "AfricanAmerican"],
            "gender": ["Female", "Male"],
            "age": ["[50-60)", "[60-70)"],
            "num_medications": [8, 10],
            "time_in_hospital": [2, 5],
            "readmitted": [0, 1],
            "readmit_binary": [0, 1],
            "readmit_30_days": [0, 1],
        }
    )

    fake_datasets = types.ModuleType("fairlearn.datasets")

    def fake_fetch_diabetes_hospital(as_frame=True):
        assert as_frame is True
        return SimpleNamespace(frame=fake_frame)

    fake_datasets.fetch_diabetes_hospital = fake_fetch_diabetes_hospital
    fake_fairlearn = types.ModuleType("fairlearn")
    fake_fairlearn.datasets = fake_datasets
    monkeypatch.setitem(sys.modules, "fairlearn", fake_fairlearn)
    monkeypatch.setitem(sys.modules, "fairlearn.datasets", fake_datasets)

    df, target, group = pilot.load_dataset_frame("fairlearn_diabetes_hospital_los")

    assert target == "time_in_hospital"
    assert group == "race"
    assert "time_in_hospital" in df.columns
    assert not {"readmitted", "readmit_binary", "readmit_30_days"} & set(df.columns)
