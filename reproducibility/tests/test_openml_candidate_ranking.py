from experiments.regression.scripts.discover_openml_regression import dataset_feature_names
from experiments.regression.scripts.rank_openml_regression_candidates import (
    is_deprioritized_feature_bag,
    term_matches_token,
    themes_for,
)


def test_openml_ranking_avoids_substring_false_positives():
    assert not term_matches_token("age", "usage")
    assert not term_matches_token("age", "image")
    assert not term_matches_token("rent", "current")


def test_openml_ranking_matches_compound_target_terms():
    record = {"name": "sleuth_ex1605", "target_feature": "Age13IQ"}
    assert themes_for(record) == ["education_score", "age"]


def test_openml_ranking_matches_salary_and_house_price():
    salary = {"name": "FacultySalaries", "target_feature": "asst.prof.salary"}
    house = {"name": "house_16H", "target_feature": "price"}
    assert themes_for(salary) == ["income_wage_salary"]
    assert themes_for(house) == ["housing_price"]


def test_openml_discovery_uses_feature_names_not_numeric_feature_keys():
    class Feature:
        def __init__(self, name):
            self.name = name

    class Dataset:
        features = {
            0: Feature("SEX"),
            1: Feature("RACE"),
            2: Feature("WAGE"),
        }

    assert dataset_feature_names(Dataset()) == ["SEX", "RACE", "WAGE"]


def test_openml_ranking_deprioritizes_word_count_feature_bags():
    record = {
        "name": "new3s.wc",
        "target_feature": "class",
        "n_features": 26833,
    }

    assert is_deprioritized_feature_bag(record)
