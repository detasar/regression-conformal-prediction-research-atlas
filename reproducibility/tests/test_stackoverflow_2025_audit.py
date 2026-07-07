import pandas as pd

from experiments.regression.scripts.audit_stackoverflow_2025_compensation import (
    DATASET_ID,
    TARGET_COMPONENT_DROP_COLUMNS,
    build_profile,
    parse_numeric_response,
)


def test_parse_numeric_response_handles_stackoverflow_year_tokens():
    parsed = parse_numeric_response(
        pd.Series(["Less than 1 year", "More than 50 years", "12", None])
    )

    assert parsed.tolist()[:3] == [0.5, 51.0, 12.0]
    assert pd.isna(parsed.iloc[3])


def test_build_profile_drops_missing_and_nonpositive_compensation_targets():
    results = pd.DataFrame(
        {
            "ResponseId": [1, 2, 3, 4],
            "ConvertedCompYearly": [100000.0, None, 0.0, 200000.0],
            "CompTotal": [100000.0, None, 0.0, 180000.0],
            "Currency": [
                "USD United States dollar",
                None,
                "USD United States dollar",
                "EUR European Euro",
            ],
            "Age": [
                "25-34 years old",
                "35-44 years old",
                "25-34 years old",
                "45-54 years old",
            ],
            "EdLevel": ["Bachelor", "Master", "Bachelor", "Doctoral"],
            "Employment": ["Employed", "Employed", "Student", "Employed"],
            "WorkExp": ["5", "10", "Less than 1 year", "More than 50 years"],
            "YearsCode": ["8", "12", "1", "30"],
            "DevType": [
                "Developer, back-end",
                "Developer, front-end",
                "Student",
                "Manager",
            ],
            "OrgSize": [
                "20 to 99 employees",
                "100 to 499 employees",
                None,
                "10,000 or more employees",
            ],
            "RemoteWork": ["Remote", "Hybrid", None, "In-person"],
            "Industry": ["Software Development", "Fintech", None, "Manufacturing"],
            "Country": ["United States of America", "Germany", "India", "France"],
            "MainBranch": ["I am a developer by profession"] * 4,
            "AISelect": ["Yes", "No", "Yes", "No"],
            "SOVisitFreq": ["Daily", "Weekly", "Monthly", "Daily"],
        }
    )
    schema = pd.DataFrame(
        {
            "qid": ["QID22"],
            "qname": ["CompTotal"],
            "question": ["What is your current total annual compensation?"],
            "type": ["TE"],
            "sub": [None],
            "sq_id": [None],
        }
    )

    profile = build_profile(results, schema, manifest=[])

    assert profile["dataset_id"] == DATASET_ID
    assert profile["shape"]["source_rows"] == 4
    assert profile["shape"]["model_rows_after_target_drop"] == 2
    assert profile["audit"]["target_missing_rate_before_drop"] == 0.25
    assert profile["audit"]["target_nonpositive_rate_before_drop"] == 0.25
    assert (
        profile["audit"]["target_component_drop_columns"]
        == TARGET_COMPONENT_DROP_COLUMNS
    )
    assert "Gender" in profile["audit"]["unavailable_protected_columns"]
