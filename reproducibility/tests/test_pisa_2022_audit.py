import pandas as pd

from experiments.regression.scripts.audit_pisa_2022_math import (
    DATASET_ID,
    MATH_PV_COLUMNS,
    TARGET,
    build_model_frame,
    build_profile,
)
from experiments.regression.scripts.run_regression_pilot import (
    load_pisa_2022_math_pv_mean_frame,
)


def _toy_pisa_student_frame() -> pd.DataFrame:
    rows = []
    countries = ["ESP", "ESP", "ESP", "TUR", "TUR", "USA"]
    for i, country in enumerate(countries):
        row = {
            "CNT": country,
            "CNTRYID": [724, 724, 724, 792, 792, 840][i],
            "CNTSCHID": [101, 101, 102, 201, 202, 301][i],
            "CNTSTUID": 1000 + i,
            "AGE": 15.5 + i / 10,
            "ST004D01T": [1, 2, 1, 2, 1, 2][i],
            "IMMIG": [1, 1, 2, 1, 3, 2][i],
            "ESCS": [-0.2, 0.1, 1.1, -1.2, 0.3, 0.7][i],
            "LANGN": [1, 1, 2, 1, 1, 2][i],
            "W_FSTUWT": [12.0, 10.0, 9.0, 8.0, 11.0, 7.0][i],
            "W_FSTURWT1": [11.5, 10.2, 8.8, 8.3, 10.9, 7.2][i],
        }
        for pv_index, column in enumerate(MATH_PV_COLUMNS, start=1):
            row[column] = 400 + i * 20 + pv_index
        row["PV1READ"] = 390 + i
        row["PV1SCIE"] = 410 + i
        rows.append(row)
    return pd.DataFrame(rows)


def test_build_profile_constructs_math_pv_mean_and_records_pisa_policy():
    rows = []
    for i in range(4):
        row = {
            "CNT": ["ESP", "TUR", "USA", "ESP"][i],
            "CNTRYID": [724, 792, 840, 724][i],
            "CNTSCHID": [1, 1, 2, 3][i],
            "CNTSTUID": [10, 11, 12, 13][i],
            "AGE": [15.5, 15.7, 15.4, 15.9][i],
            "ST004D01T": [1, 2, 1, 2][i],
            "IMMIG": [1, 1, 2, 3][i],
            "ESCS": [-0.2, 0.1, 1.1, -1.2][i],
            "LANGN": [1, 1, 2, 1][i],
            "W_FSTUWT": [12.0, 10.0, 9.0, 8.0][i],
            "W_FSTURWT1": [11.5, 10.2, 8.8, 8.3][i],
        }
        for pv_index, column in enumerate(MATH_PV_COLUMNS, start=1):
            row[column] = 400 + i * 20 + pv_index
        row["PV1READ"] = 390 + i
        row["PV1SCIE"] = 410 + i
        rows.append(row)
    student = pd.DataFrame(rows)

    model_frame = build_model_frame(student)
    profile = build_profile(student, manifest=[])

    assert profile["dataset_id"] == DATASET_ID
    assert TARGET in model_frame.columns
    assert MATH_PV_COLUMNS[0] not in model_frame.columns
    assert model_frame[TARGET].iloc[0] == 405.5
    assert profile["shape"]["model_rows_after_target_drop"] == 4
    assert profile["audit"]["replicate_weight_count"] == 1
    assert "ST004D01T" in profile["audit"]["sensitive_candidates"]
    assert "plausible" in profile["audit"]["target_policy"]
    assert "replicate weights" in profile["audit"]["survey_policy"]
    assert "nested within schools and countries" in profile["audit"]["education_policy"]


def test_pisa_runner_loader_adds_school_split_and_country_balanced_sample(monkeypatch):
    from experiments.regression.scripts import audit_pisa_2022_math

    monkeypatch.setattr(
        audit_pisa_2022_math,
        "load_student_frame",
        lambda raw_dir: _toy_pisa_student_frame(),
    )

    frame = load_pisa_2022_math_pv_mean_frame(
        "unused/raw/path",
        TARGET,
        sample_per_country=2,
        sample_seed=123,
    )

    assert TARGET in frame.columns
    assert "CNTSCHID" in frame.columns
    assert MATH_PV_COLUMNS[0] not in frame.columns
    assert frame.groupby("CNT").size().to_dict() == {"ESP": 2, "TUR": 2, "USA": 1}
    assert frame[TARGET].notna().all()
