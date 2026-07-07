import pandas as pd

from experiments.regression.scripts.audit_folktables_acs_custom_regression import (
    FolktablesTaskSpec,
    build_task_profile,
    variable_definitions,
)


def test_variable_definitions_extracts_name_and_value_rows():
    definitions = pd.DataFrame(
        [
            ["NAME", "RAC1P", "C", "1", "Race recode", None, None],
            ["VAL", "RAC1P", "C", "1", "1", "1", "White alone"],
            ["VAL", "RAC1P", "C", "1", "2", "2", "Black alone"],
            ["NAME", "SEX", "C", "1", "Sex", None, None],
        ]
    )

    extracted = variable_definitions(definitions, ["RAC1P"])

    assert extracted["RAC1P"]["description"] == "Race recode"
    assert extracted["RAC1P"]["values"][0]["label"] == "White alone"


def test_build_task_profile_records_universe_and_disabled_transform():
    raw = pd.DataFrame(
        {
            "AGEP": [15, 20, 30, 40, 50],
            "RAC1P": [1, 1, 2, 2, 1],
            "SEX": [1, 2, 1, 2, 1],
            "PWGTP": [1, 2, 3, 4, 5],
            "x": [0.0, 1.0, 2.0, 3.0, 4.0],
            "target": [10.0, 20.0, None, 40.0, 80.0],
        }
    )
    spec = FolktablesTaskSpec(
        dataset_id="toy_folktables",
        name="Toy Folktables",
        source_task="ToyTask",
        target="target",
        features=["AGEP", "RAC1P", "SEX", "x"],
        group="RAC1P",
        group_columns=["RAC1P", "SEX", "AGEP"],
        preprocess=lambda df: df[df["AGEP"] > 16].copy(),
        predefined_target_transform="target > 0, disabled here",
        target_policy="Toy target policy.",
        extra_context_columns=["PWGTP"],
    )

    profile = build_task_profile(
        raw,
        spec,
        definitions=None,
        states=["WY"],
        survey_year="test-year",
    )

    assert profile["shape"]["source_rows"] == 5
    assert profile["shape"]["preprocess_universe_rows"] == 4
    assert profile["shape"]["model_rows_after_target_drop"] == 3
    assert profile["audit"]["target_missing_rate_before_drop"] == 0.25
    assert profile["audit"]["target_transform_used"] is None
    assert profile["audit"]["predefined_target_transform"] == "target > 0, disabled here"
    assert [group["column"] for group in profile["group_profiles"]] == ["RAC1P", "SEX", "AGEP"]
