import pandas as pd

from experiments.regression.scripts.audit_hmda_2025_wy_interest_rate import (
    DATASET_ID,
    TARGET,
    TARGET_COMPONENT_DROP_COLUMNS,
    build_model_frame,
    build_profile,
    leakage_correlation,
)


def test_build_model_frame_keeps_only_positive_numeric_interest_rate():
    source = pd.DataFrame(
        {
            TARGET: ["6.5", "Exempt", "0", None, "7.25"],
            "rate_spread": ["0.3", "0.1", "0", None, "0.8"],
            "derived_race": ["White", "Asian", "White", "Joint", "Black"],
            "derived_ethnicity": ["Not Hispanic or Latino"] * 5,
            "derived_sex": ["Male", "Female", "Joint", "Male", "Female"],
            "applicant_age": ["35-44", "45-54", "35-44", "55-64", "25-34"],
            "loan_amount": [200000, 150000, 100000, 120000, 300000],
            "loan_to_value_ratio": ["80", "75", "70", "NA", "65"],
            "property_value": ["250000", "200000", "150000", "180000", "450000"],
            "income": ["100", "90", "80", "Exempt", "120"],
        }
    )

    model_frame, target_filter = build_model_frame(source)

    assert model_frame[TARGET].tolist() == [6.5, 7.25]
    assert target_filter["source_rows"] == 5
    assert target_filter["model_rows_after_target_filter"] == 2
    assert target_filter["target_exempt_rows_before_drop"] == 1
    assert target_filter["target_nonpositive_rows_before_drop"] == 1
    assert "rate_spread" not in model_frame.columns
    assert pd.api.types.is_numeric_dtype(model_frame["loan_to_value_ratio"])


def test_build_profile_records_hmda_source_review_policies():
    source = pd.DataFrame(
        {
            TARGET: ["6.5", "7.25", "Exempt"],
            "rate_spread": ["0.3", "0.8", "0.2"],
            "derived_race": ["White", "Black or African American", "Asian"],
            "derived_ethnicity": [
                "Not Hispanic or Latino",
                "Hispanic or Latino",
                "Joint",
            ],
            "derived_sex": ["Male", "Female", "Joint"],
            "applicant_age": ["35-44", "25-34", "45-54"],
            "loan_amount": [200000, 300000, 150000],
            "loan_to_value_ratio": ["80", "65", "75"],
            "property_value": ["250000", "450000", "200000"],
            "income": ["100", "120", "90"],
        }
    )

    profile = build_profile(source, manifest=[])

    assert profile["dataset_id"] == DATASET_ID
    assert profile["shape"]["model_rows_after_target_filter"] == 2
    assert (
        profile["audit"]["target_component_drop_columns"]
        == TARGET_COMPONENT_DROP_COLUMNS
    )
    assert "derived_race" in profile["audit"]["sensitive_candidates"]
    assert "rate_spread" in profile["audit"]["leakage_policy"]


def test_leakage_correlation_reports_rate_spread_strength():
    source = pd.DataFrame(
        {
            TARGET: ["6", "7", "8", "Exempt"],
            "rate_spread": ["0.1", "0.2", "0.3", "0.4"],
        }
    )

    check = leakage_correlation(source)

    assert check["column"] == "rate_spread"
    assert check["valid_pair_rows"] == 3
    assert check["pearson_corr_with_interest_rate"] > 0.99
