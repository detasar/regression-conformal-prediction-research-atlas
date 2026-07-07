import pandas as pd

from experiments.regression.scripts.profile_openml_regression_dataset import (
    build_profile,
    group_profile,
    target_summary,
    top_abs_correlations,
)


def test_target_summary_reports_skew_and_quantiles():
    summary = target_summary(pd.Series([1, 2, 3, 4, None]))

    assert summary["n"] == 5
    assert summary["n_observed"] == 4
    assert summary["missing_rate"] == 0.2
    assert summary["quantiles"]["0.5"] == 2.5


def test_group_profile_uses_quantile_bins_for_many_numeric_values():
    df = pd.DataFrame({"age": range(24), "target": range(24)})

    profile = group_profile(df, "target", "age", max_levels=5)

    assert profile["mode"] == "numeric_quantile_bins"
    assert profile["levels_profiled"] == 4


def test_top_abs_correlations_sorts_by_absolute_value():
    df = pd.DataFrame(
        {
            "weak": [1, 1, 2, 2, 3, 3],
            "strong": [10, 20, 30, 40, 50, 60],
            "target": [9, 19, 31, 41, 49, 61],
        }
    )

    correlations = top_abs_correlations(df, "target")

    assert correlations[0]["column"] == "strong"


def test_build_profile_combines_requested_and_inferred_groups():
    df = pd.DataFrame(
        {
            "SEX": ["female", "male", "female"],
            "RACE": ["A", "B", "A"],
            "education": [12, 16, 14],
            "WAGE": [8.0, 20.0, 12.0],
        }
    )
    metadata = {
        "openml_id": 1,
        "name": "toy",
        "url": "https://example.test",
        "licence": "Public",
    }

    profile = build_profile(
        df,
        dataset_id="toy",
        target="WAGE",
        group_columns=["SEX"],
        metadata=metadata,
    )

    assert [group["column"] for group in profile["group_profiles"]] == ["SEX", "RACE"]
    assert profile["audit"]["sensitive_candidates"] == ["SEX", "RACE"]
