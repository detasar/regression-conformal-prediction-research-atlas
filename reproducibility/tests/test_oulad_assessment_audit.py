import pandas as pd

from experiments.regression.scripts.audit_oulad_assessment_score import (
    DATASET_ID,
    LEAKAGE_DROP_COLUMNS,
    MODEL_COLUMNS,
    build_assessment_profile,
)


def test_build_assessment_profile_drops_missing_target_and_final_result():
    joined = pd.DataFrame(
        {
            "code_module": ["AAA", "AAA", "BBB"],
            "code_presentation": ["2013J", "2013J", "2014B"],
            "id_assessment": [1, 2, 3],
            "id_student": [10, 10, 20],
            "date_submitted": [5, 10, 12],
            "is_banked": [0, 0, 1],
            "score": [70.0, None, 90.0],
            "assessment_type": ["TMA", "TMA", "CMA"],
            "date": [20, 30, 40],
            "weight": [10.0, 20.0, 30.0],
            "gender": ["M", "M", "F"],
            "region": ["X", "X", "Y"],
            "highest_education": ["A", "A", "B"],
            "imd_band": ["0-10%", "0-10%", "90-100%"],
            "age_band": ["0-35", "0-35", "35-55"],
            "num_of_prev_attempts": [0, 0, 1],
            "studied_credits": [60, 60, 120],
            "disability": ["N", "N", "Y"],
            "final_result": ["Pass", "Pass", "Fail"],
        }
    )

    profile = build_assessment_profile(joined, manifest=[])

    assert profile["dataset_id"] == DATASET_ID
    assert profile["shape"]["joined_rows"] == 3
    assert profile["shape"]["model_rows_after_target_drop"] == 2
    assert profile["audit"]["target_missing_rate_before_drop"] == 1 / 3
    assert profile["audit"]["leakage_drop_columns"] == LEAKAGE_DROP_COLUMNS
    assert "final_result" not in MODEL_COLUMNS
