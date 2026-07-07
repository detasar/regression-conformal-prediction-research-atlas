import pandas as pd

from experiments.regression.scripts.audit_meps_2023_total_expenditure import (
    DATASET_ID,
    TARGET,
    TARGET_COMPONENT_DROP_COLUMNS,
    build_model_frame,
    build_profile,
    normalize_meps_missingness,
    target_component_manifest,
)


def test_normalize_meps_missingness_preserves_target_but_masks_feature_codes():
    frame = pd.DataFrame(
        {
            TARGET: [0, 100, -1],
            "AGE23X": [35, -1, 70],
            "SEX": [1, -7, 2],
        }
    )

    normalized = normalize_meps_missingness(frame)

    assert normalized[TARGET].tolist() == [0, 100, -1]
    assert pd.isna(normalized.loc[1, "AGE23X"])
    assert pd.isna(normalized.loc[1, "SEX"])


def test_build_model_frame_keeps_zero_expenditures_and_drops_negative_targets():
    source = pd.DataFrame(
        {
            TARGET: [0, 1000, -1, None],
            "PERWT23F": [1.0, 2.0, 3.0, 4.0],
            "VARSTR": [101, 101, 102, 102],
            "VARPSU": [1, 2, 1, 2],
            "PANEL": [27, 27, 28, 28],
            "AGE23X": [20, 65, 40, 50],
            "SEX": [1, 2, 1, 2],
            "RACETHX": [2, 1, 3, 4],
            "POVCAT23": [5, 1, 2, 3],
            "INSCOV23": [1, 2, 3, 1],
        }
    )

    model_frame, target_filter = build_model_frame(source)

    assert model_frame[TARGET].tolist() == [0.0, 1000.0]
    assert target_filter["source_rows"] == 4
    assert target_filter["model_rows_after_target_filter"] == 2
    assert target_filter["target_zero_rows_after_filter"] == 1
    assert target_filter["target_negative_or_missing_rows_before_drop"] == 2


def test_build_profile_records_survey_and_target_component_policies():
    source = pd.DataFrame(
        {
            TARGET: [0, 1000, 5000],
            "TOTSLF23": [0, 100, 500],
            "PERWT23F": [1.0, 2.0, 3.0],
            "VARSTR": [101, 101, 102],
            "VARPSU": [1, 2, 1],
            "PANEL": [27, 27, 28],
            "AGE23X": [20, 65, 40],
            "SEX": [1, 2, 1],
            "RACETHX": [2, 1, 3],
            "POVCAT23": [5, 1, 2],
            "INSCOV23": [1, 2, 3],
            "REGION23": [1, 2, 3],
            "RTHLTH53": [1, 2, -1],
            "MNHLTH53": [1, 3, -8],
        }
    )
    labels = {column: column for column in source.columns}

    profile = build_profile(source, labels, manifest=[])

    assert profile["dataset_id"] == DATASET_ID
    assert profile["shape"]["model_rows_after_target_filter"] == 3
    assert "PERWT23F" in profile["audit"]["survey_design_columns"]
    assert (
        profile["audit"]["target_component_drop_columns"]
        == TARGET_COMPONENT_DROP_COLUMNS
    )
    assert "raw/log1p" in profile["audit"]["target_policy"]


def test_target_component_manifest_reports_loaded_and_unloaded_components():
    source = pd.DataFrame({TARGET: [0, 10, 20], "TOTSLF23": [0, 5, 10]})

    manifest = target_component_manifest(source)

    loaded = next(row for row in manifest if row["column"] == "TOTSLF23")
    unloaded = next(row for row in manifest if row["column"] == "RXEXP23")
    assert loaded["valid_pair_rows"] == 3
    assert loaded["pearson_corr_with_target"] > 0.99
    assert unloaded["status"] == "not_loaded_by_audit"
