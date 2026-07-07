import pandas as pd

from cpfi.regression.datasets import infer_sensitive_candidates, sensitive_name_matches
from experiments.regression.scripts import audit_college_scorecard_2026_earnings
from experiments.regression.scripts import audit_meps_2023_total_expenditure
from experiments.regression.scripts import audit_nhanes_glycohemoglobin
from experiments.regression.scripts import audit_nhanes_systolic_bp
from experiments.regression.scripts import audit_oulad_assessment_score
from experiments.regression.scripts import audit_scf_2022_networth
from experiments.regression.scripts import run_regression_pilot as pilot
from experiments.regression.scripts.run_regression_pilot import (
    DATASET_LOADERS,
    add_interaction_group,
    add_quantile_group,
)


def test_sensitive_name_matching_avoids_age_inside_average():
    assert sensitive_name_matches("age")
    assert sensitive_name_matches("SEX")
    assert sensitive_name_matches("racePctBlack")
    assert sensitive_name_matches("RAC1P")
    assert sensitive_name_matches("blackPerCap")
    assert sensitive_name_matches("PctPolicWhite")
    assert sensitive_name_matches("medIncome")
    assert not sensitive_name_matches("grade_point_average")
    assert not sensitive_name_matches("brace")
    assert not sensitive_name_matches("trace")
    assert not sensitive_name_matches("grace")
    assert not sensitive_name_matches("blackmail")
    assert not sensitive_name_matches("whitewash")
    assert not sensitive_name_matches("contracept")
    assert not sensitive_name_matches("DIS")


def test_infer_sensitive_candidates_uses_conservative_name_matching():
    df = pd.DataFrame(
        {
            "grade_point_average": [3.1, 3.4],
            "AGEP": [31, 44],
            "income": [100.0, 200.0],
        }
    )

    assert infer_sensitive_candidates(df) == ["AGEP", "income"]


def test_add_quantile_group_creates_string_bins_and_missing_bucket():
    df = pd.DataFrame({"proxy": [0.1, 0.2, 0.8, 0.9, None]})

    grouped = add_quantile_group(df, source_col="proxy", group_col="proxy_bin", q=2)

    assert grouped["proxy_bin"].dtype == object
    assert grouped["proxy_bin"].iloc[-1] == "missing"
    assert grouped["proxy_bin"].nunique() == 3


def test_add_interaction_group_crosses_string_groups_and_missing_bucket():
    df = pd.DataFrame(
        {
            "lat_bin": ["south", "north", None],
            "lon_bin": ["west", "east", "west"],
        }
    )

    grouped = add_interaction_group(
        df,
        source_cols=["lat_bin", "lon_bin"],
        group_col="spatial_cell",
    )

    assert grouped["spatial_cell"].tolist() == [
        "south|west",
        "north|east",
        "missing|west",
    ]


def test_openml_cps_85_wages_loader_is_registered_with_sex_group():
    spec = DATASET_LOADERS["openml_cps_85_wages"]

    assert spec["source"] == "openml"
    assert spec["openml_id"] == 534
    assert spec["target"] == "WAGE"
    assert spec["group"] == "SEX"


def test_uci_auto_mpg_loader_keeps_origin_group_and_horsepower_missingness(
    monkeypatch,
):
    source = pd.DataFrame(
        {
            "displacement": [307.0, 350.0, 318.0, 304.0],
            "cylinders": [8, 8, 8, 8],
            "horsepower": [130.0, 165.0, None, 150.0],
            "weight": [3504, 3693, 3436, 3433],
            "acceleration": [12.0, 11.5, 11.0, 12.0],
            "model_year": [70, 70, 70, 70],
            "origin": [1, 1, 1, 2],
            "mpg": [18.0, 15.0, 18.0, 16.0],
        }
    )

    def fake_load_uci(uci_id, target, extra_target_columns=()):
        assert uci_id == 9
        assert target == "mpg"
        assert list(extra_target_columns) == []
        return source.copy()

    monkeypatch.setattr(pilot, "load_uci_frame", fake_load_uci)

    df, target, group = pilot.load_dataset_frame("uci_auto_mpg")

    assert target == "mpg"
    assert group == "origin"
    assert "origin" in df.columns
    assert "horsepower" in df.columns
    assert df["horsepower"].isna().sum() == 1
    assert set(df.columns) == {
        "displacement",
        "cylinders",
        "horsepower",
        "weight",
        "acceleration",
        "model_year",
        "origin",
        "mpg",
    }


def test_openml_california_spatial_cell_loader_derives_holdout_groups(monkeypatch):
    n = 64
    source = pd.DataFrame(
        {
            "longitude": [-124.0 + idx * 0.1 for idx in range(n)],
            "latitude": [32.0 + (idx % 16) * 0.1 for idx in range(n)],
            "housing_median_age": [20 + idx % 10 for idx in range(n)],
            "total_rooms": [500 + idx for idx in range(n)],
            "total_bedrooms": [100 + idx if idx % 7 else None for idx in range(n)],
            "population": [800 + idx for idx in range(n)],
            "households": [200 + idx for idx in range(n)],
            "median_income": [2.0 + (idx % 8) * 0.5 for idx in range(n)],
            "ocean_proximity": ["INLAND" if idx % 2 else "<1H OCEAN" for idx in range(n)],
            "median_house_value": [100000 + idx * 1000 for idx in range(n)],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 43939
        assert target == "median_house_value"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_california_housing_spatial_cell")

    assert target == "median_house_value"
    assert group == "ocean_proximity"
    assert {"latitude_bin", "longitude_bin", "spatial_cell"}.issubset(df.columns)
    assert df["spatial_cell"].str.contains("|", regex=False).all()
    assert df["spatial_cell"].nunique() > 8
    assert DATASET_LOADERS["openml_california_housing"]["drop_columns"] == []
    assert DATASET_LOADERS["openml_california_housing_spatial_cell"][
        "feature_drop_columns"
    ] == ["latitude_bin", "longitude_bin", "spatial_cell"]


def test_openml_chlamydia_loader_is_registered_as_count_benchmark():
    spec = DATASET_LOADERS["openml_analcatdata_chlamydia"]

    assert spec["source"] == "openml"
    assert spec["openml_id"] == 535
    assert spec["target"] == "Count"
    assert spec["group"] == "Gender"


def test_openml_gsssexsurvey_loader_drops_sensitive_proxy_fields(monkeypatch):
    source = pd.DataFrame(
        {
            "Married": [1, 0, 1, 0, 1, 0, 1, 0],
            "Age": [22, 28, 34, 39, 45, 51, 62, 77],
            "Years_of_education": [12, 14, 16, 12, 18, 13, 15, 11],
            "Male": [1, 0, 1, 0, 1, 0, 1, 0],
            "Religious": [1, 1, 0, 1, 1, 0, 1, 1],
            "Sex_partners": [1, 2, 3, 1, 5, 2, 1, 4],
            "Income": [9000, None, 16250, 27500, 32500, 37500, 45000, 55000],
            "Drug_use": [0, 0, 1, 0, 0, 1, 0, 0],
            "Same_sex_relations": [0, 1, 0, 0, 1, 0, 0, 0],
            "AIDS_know": [0, 1, 0, 2, 0, 3, 0, 4],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 506
        assert target == "AIDS_know"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_analcatdata_gsssexsurvey")

    assert target == "AIDS_know"
    assert group == "Male"
    assert set(df.columns) == {
        "Years_of_education",
        "Male",
        "AIDS_know",
        "age_bin",
    }
    assert df["age_bin"].nunique() == 4
    assert pilot.DATASET_LOADERS["openml_analcatdata_gsssexsurvey"][
        "feature_drop_columns"
    ] == ["age_bin"]


def test_openml_sensory_loader_keeps_method_and_judges(monkeypatch):
    source = pd.DataFrame(
        {
            "Occasion": ["1", "1", "2", "2"],
            "Judges": ["1", "2", "1", "2"],
            "Interval": ["1", "2", "1", "2"],
            "Sittings": ["1", "1", "2", "2"],
            "Position": ["1", "2", "3", "4"],
            "Squares": ["1", "2", "1", "2"],
            "Rows": ["1", "2", "3", "1"],
            "Columns": ["1", "2", "3", "4"],
            "Halfplot": ["1", "2", "1", "2"],
            "Trellis": ["1", "2", "3", "4"],
            "Method": ["1", "2", "1", "2"],
            "Score": [14.5, 15.0, 15.5, 16.0],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 546
        assert target == "Score"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_sensory_score")

    assert target == "Score"
    assert group == "Method"
    assert "Method" in df.columns
    assert "Judges" in df.columns
    assert "Score" in df.columns
    assert pilot.DATASET_LOADERS["openml_sensory_score"]["openml_id"] == 546


def test_openml_gascons_loader_drops_income_after_income_bin(monkeypatch):
    source = pd.DataFrame(
        {
            "year": [1960, 1961, 1962, 1963, 1964, 1965, 1966, 1967],
            "price_index_for_casoline": [
                0.925,
                0.914,
                0.919,
                0.918,
                0.914,
                0.949,
                0.970,
                1.000,
            ],
            "disposable_income": [6036, 6113, 6271, 6378, 6727, 7027, 7280, 7513],
            "price_index_for_used_cars": [
                0.836,
                0.869,
                0.948,
                0.960,
                1.001,
                0.994,
                0.970,
                1.000,
            ],
            "gasoline_consumption": [
                129.7,
                131.3,
                137.1,
                141.6,
                148.8,
                155.9,
                164.9,
                171.0,
            ],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 226
        assert target == "gasoline_consumption"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_gascons_consumption")

    assert target == "gasoline_consumption"
    assert group == "income_bin"
    assert "income_bin" in df.columns
    assert "disposable_income" not in df.columns
    assert "year" in df.columns
    assert pilot.DATASET_LOADERS["openml_gascons_consumption"]["openml_id"] == 226


def test_openml_plasma_retinol_loader_drops_age_and_co_analyte_after_bins(
    monkeypatch,
):
    source = pd.DataFrame(
        {
            "AGE": [30, 40, 50, 60, 70, 80, 35, 45],
            "SEX": [
                "Female",
                "Male",
                "Female",
                "Male",
                "Female",
                "Female",
                "Male",
                "Female",
            ],
            "SMOKSTAT": [
                "Never",
                "Former",
                "Never",
                "Current_Smoker",
                "Former",
                "Never",
                "Current_Smoker",
                "Former",
            ],
            "QUETELET": [21.0, 24.0, 25.0, 27.0, 22.0, 23.0, 26.0, 28.0],
            "VITUSE": [
                "No",
                "Yes_fairly_often",
                "Yes_not_often",
                "No",
                "Yes_fairly_often",
                "No",
                "Yes_not_often",
                "No",
            ],
            "CALORIES": [1500, 1800, 1900, 2100, 1600, 1700, 2200, 2000],
            "FAT": [50, 60, 70, 80, 55, 65, 75, 85],
            "FIBER": [10, 12, 14, 16, 11, 13, 15, 17],
            "ALCOHOL": [0, 1, 0, 2, 1, 0, 3, 1],
            "CHOLESTEROL": [150, 170, 190, 210, 160, 180, 200, 220],
            "BETADIET": [1000, 1200, 1400, 1600, 1100, 1300, 1500, 1700],
            "RETDIET": [400, 500, 600, 700, 450, 550, 650, 750],
            "BETAPLASMA": [100, 110, 120, 130, 140, 150, 160, 170],
            "RETPLASMA": [500, 550, 600, 650, 700, 750, 800, 850],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 511
        assert target == "RETPLASMA"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_plasma_retinol")

    assert target == "RETPLASMA"
    assert group == "SEX"
    assert "SEX" in df.columns
    assert "age_bin" in df.columns
    assert "AGE" not in df.columns
    assert "BETAPLASMA" not in df.columns
    assert pilot.DATASET_LOADERS["openml_plasma_retinol"]["feature_drop_columns"] == [
        "age_bin"
    ]
    assert pilot.DATASET_LOADERS["openml_plasma_retinol"]["openml_id"] == 511


def test_openml_disclosure_z_loader_drops_age_after_age_bin(monkeypatch):
    source = pd.DataFrame(
        {
            "Age": [20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0],
            "Civil": [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0],
            "Can/US": [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0],
            "Income": [
                40000.0,
                45000.0,
                50000.0,
                55000.0,
                60000.0,
                65000.0,
                70000.0,
                75000.0,
            ],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 699
        assert target == "Income"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_disclosure_z")

    assert target == "Income"
    assert group == "age_bin"
    assert "age_bin" in df.columns
    assert "Age" not in df.columns
    assert list(df.drop(columns=["Income", "age_bin"]).columns) == ["Civil", "Can/US"]
    assert pilot.DATASET_LOADERS["openml_disclosure_z"]["openml_id"] == 699


def test_openml_disclosure_x_bias_loader_drops_age_after_age_bin(monkeypatch):
    source = pd.DataFrame(
        {
            "Age": [21.0, 31.0, 41.0, 51.0, 61.0, 71.0, 81.0, 91.0],
            "Civil": [11.0, 13.0, 15.0, 17.0, 19.0, 21.0, 23.0, 25.0],
            "Can/US": [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0],
            "Income": [
                41000.0,
                46000.0,
                51000.0,
                56000.0,
                61000.0,
                66000.0,
                71000.0,
                76000.0,
            ],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 709
        assert target == "Income"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_disclosure_x_bias")

    assert target == "Income"
    assert group == "age_bin"
    assert "age_bin" in df.columns
    assert "Age" not in df.columns
    assert list(df.drop(columns=["Income", "age_bin"]).columns) == ["Civil", "Can/US"]
    assert pilot.DATASET_LOADERS["openml_disclosure_x_bias"]["openml_id"] == 709


def test_openml_disclosure_x_noise_loader_drops_age_after_age_bin(monkeypatch):
    source = pd.DataFrame(
        {
            "Age": [22.0, 32.0, 42.0, 52.0, 62.0, 72.0, 82.0, 92.0],
            "Civil": [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0],
            "Can/US": [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
            "Income": [
                -12000.0,
                38000.0,
                43000.0,
                51000.0,
                67000.0,
                79000.0,
                105000.0,
                150000.0,
            ],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 704
        assert target == "Income"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_disclosure_x_noise")

    assert target == "Income"
    assert group == "age_bin"
    assert "age_bin" in df.columns
    assert "Age" not in df.columns
    assert list(df.drop(columns=["Income", "age_bin"]).columns) == ["Civil", "Can/US"]
    assert df["Income"].min() < 0.0
    assert pilot.DATASET_LOADERS["openml_disclosure_x_noise"]["openml_id"] == 704


def test_openml_disclosure_x_tampered_loader_drops_age_after_age_bin(monkeypatch):
    source = pd.DataFrame(
        {
            "Age": [23.0, 33.0, 43.0, 53.0, 63.0, 73.0, 83.0, 93.0],
            "Civil": [9.0, 11.0, 13.0, 15.0, 17.0, 19.0, 21.0, 23.0],
            "Can/US": [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
            "Income": [
                -15000.0,
                35000.0,
                44000.0,
                52000.0,
                69000.0,
                81000.0,
                108000.0,
                152000.0,
            ],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 676
        assert target == "Income"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_disclosure_x_tampered")

    assert target == "Income"
    assert group == "age_bin"
    assert "age_bin" in df.columns
    assert "Age" not in df.columns
    assert list(df.drop(columns=["Income", "age_bin"]).columns) == ["Civil", "Can/US"]
    assert df["Income"].min() < 0.0
    assert pilot.DATASET_LOADERS["openml_disclosure_x_tampered"]["openml_id"] == 676


def test_openml_cholesterol_loader_bins_age_and_drops_diagnosis(
    monkeypatch,
):
    source = pd.DataFrame(
        {
            "age": [42, 48, 52, 56, 60, 64, 68, 72],
            "sex": ["1", "0", "1", "0", "1", "0", "1", "0"],
            "cp": ["1", "2", "3", "4", "1", "2", "3", "4"],
            "trestbps": [120, 128, 135, 140, 132, 138, 145, 150],
            "fbs": ["0", "0", "1", "0", "1", "0", "1", "0"],
            "restecg": ["0", "1", "2", "0", "1", "2", "0", "1"],
            "thalach": [160, 155, 150, 145, 140, 135, 130, 125],
            "exang": ["0", "0", "1", "0", "1", "0", "1", "0"],
            "oldpeak": [0.0, 0.5, 1.0, 1.5, 0.2, 0.8, 1.2, 1.8],
            "slope": ["1", "2", "3", "1", "2", "3", "1", "2"],
            "ca": ["0", "1", "2", "3", "0", "1", "2", "3"],
            "thal": ["3", "6", "7", "3", "6", "7", "3", "6"],
            "num": ["0", "1", "2", "3", "4", "0", "1", "2"],
            "chol": [190, 205, 220, 235, 250, 265, 280, 295],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 204
        assert target == "chol"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_cholesterol_chol")

    assert target == "chol"
    assert group == "sex"
    assert "sex" in df.columns
    assert "age_bin" in df.columns
    assert {"age", "num"}.isdisjoint(df.columns)
    assert pilot.DATASET_LOADERS["openml_cholesterol_chol"]["feature_drop_columns"] == [
        "age_bin"
    ]
    assert pilot.DATASET_LOADERS["openml_cholesterol_chol"]["openml_id"] == 204


def test_openml_vehicle_count_loader_drops_age_and_keeps_gender_group(
    monkeypatch,
):
    source = pd.DataFrame(
        {
            "Alcohol-related": ["No", "Yes", "No", "Yes"],
            "Gender": ["Female", "Female", "Male", "Male"],
            "Type": [
                "Passenger",
                "Pedestrian/bicyclist",
                "Passenger",
                "Pedestrian/bicyclist",
            ],
            "Age": ["0-2", "3-5", "6-8", "9-11"],
            "Count": [320, 75, 410, 120],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 485
        assert target == "Count"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_analcatdata_vehicle_count")

    assert target == "Count"
    assert group == "Gender"
    assert "Gender" in df.columns
    assert "Age" not in df.columns
    assert {"Alcohol-related", "Type", "Count"} <= set(df.columns)


def test_openml_runshoes_loader_drops_demographic_proxies_and_keeps_male_group(
    monkeypatch,
):
    source = pd.DataFrame(
        {
            "Male": ["1", "0", "1", "0"],
            "Married": ["0", "1", "0", "1"],
            "Runs.per.week": [3, 4, 5, 2],
            "Age": [22.5, 29.5, 36.5, 43.5],
            "Income": [42.5, None, 57.5, 30.0],
            "College": ["1", "0", "1", "0"],
            "Distance": ["0", "1", "0", "1"],
            "Treadmill": ["0", "0", "1", "1"],
            "Miles.per.week": [12.5, 27.5, 32.5, 5.0],
            "Type.of.running": [
                "5Other",
                "1Marathon",
                "3Treadmill",
                "4Just_for_fun",
            ],
            "Shoes": [2, 4, 3, 1],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 498
        assert target == "Shoes"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_analcatdata_runshoes")

    assert target == "Shoes"
    assert group == "Male"
    assert "Male" in df.columns
    assert {"Age", "Income", "College", "Married"}.isdisjoint(df.columns)
    assert {
        "Runs.per.week",
        "Distance",
        "Treadmill",
        "Miles.per.week",
        "Type.of.running",
        "Shoes",
    } <= set(df.columns)


def test_openml_fishcatch_loader_drops_sex_and_keeps_species_group(monkeypatch):
    source = pd.DataFrame(
        {
            "Species": ["1", "1", "2", "7"],
            "Length1": [23.2, 24.0, 23.6, 41.1],
            "Length2": [25.4, 26.3, 26.0, 44.0],
            "Length3": [30.0, 31.2, 28.7, 46.6],
            "Height": [38.4, 40.0, 29.2, 26.8],
            "Width": [13.4, 13.8, 14.8, 16.3],
            "Sex": [None, "1", None, "0"],
            "class": [242.0, 290.0, 270.0, 1000.0],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 232
        assert target == "class"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_fishcatch_weight")

    assert target == "class"
    assert group == "Species"
    assert "Species" in df.columns
    assert "Sex" not in df.columns
    assert {
        "Length1",
        "Length2",
        "Length3",
        "Height",
        "Width",
        "class",
    } <= set(df.columns)


def test_openml_auto_price_loader_keeps_symboling_group(monkeypatch):
    source = pd.DataFrame(
        {
            "symboling": ["-1", "0", "1", "2"],
            "normalized-losses": [85.0, 122.0, 150.0, 188.0],
            "wheel-base": [96.3, 99.8, 101.2, 95.9],
            "length": [172.4, 176.6, 190.9, 173.2],
            "width": [65.4, 66.2, 70.3, 66.3],
            "height": [54.3, 54.9, 56.5, 50.2],
            "curb-weight": [2337, 2507, 3495, 2808],
            "engine-size": [109, 136, 183, 156],
            "bore": [3.19, 3.19, 3.58, 3.59],
            "stroke": [3.40, 3.40, 3.64, 3.86],
            "compression-ratio": [9.0, 8.5, 21.5, 7.0],
            "horsepower": [102, 115, 123, 145],
            "peak-rpm": [5500, 5500, 4350, 5000],
            "city-mpg": [24, 22, 22, 19],
            "highway-mpg": [30, 28, 25, 24],
            "price": [7957.0, 9295.0, 25552.0, 14489.0],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 195
        assert target == "price"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_auto_price")

    assert target == "price"
    assert group == "symboling"
    assert "symboling" in df.columns
    assert "price" in df.columns
    assert "curb-weight" in df.columns


def test_openml_faculty_salaries_loader_drops_salary_cooutcomes(monkeypatch):
    source = pd.DataFrame(
        {
            "University": ["A", "B", "C", "D"],
            "CIC.institutions": [1, 0, 1, 0],
            "average.salary": [55.0, 52.0, 60.0, 49.0],
            "full.prof.salary": [70.0, 68.0, 75.0, 63.0],
            "assoc.prof.salary": [48.0, 46.0, 52.0, 44.0],
            "asst.prof.salary": [40.0, 39.0, 45.0, 37.0],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 1096
        assert target == "asst.prof.salary"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_faculty_salaries_asst_prof")

    assert target == "asst.prof.salary"
    assert group == "CIC.institutions"
    assert "CIC.institutions" in df.columns
    assert "University" in df.columns
    assert {
        "average.salary",
        "full.prof.salary",
        "assoc.prof.salary",
    }.isdisjoint(df.columns)
    assert pilot.DATASET_LOADERS["openml_faculty_salaries_asst_prof"][
        "feature_drop_columns"
    ] == ["University"]


def test_openml_baseball_hitter_loader_drops_identity_and_roster_fields(
    monkeypatch,
):
    target = "1987_annual_salary_on_opening_day_in_thousands_of_dollars"
    source = pd.DataFrame(
        {
            "hitters_name": ["A", "B", "C", "D"],
            "number_of_times_at_bat_in_1986": [293, 315, 479, 496],
            "number_of_hits_in_1986": [66, 81, 130, 141],
            "number_of_home_runs_in_1986": [1, 7, 18, 20],
            "number_of_runs_in_1986": [30, 24, 66, 65],
            "number_of_runs_batted_in_in_1986": [29, 38, 72, 78],
            "number_of_walks_in_1986": [14, 39, 76, 37],
            "number_of_years_in_the_major_leagues": [1, 14, 3, 11],
            "number_of_times_at_bat_during_his_career": [293, 3449, 1624, 5628],
            "number_of_hits_during_his_career": [66, 835, 457, 1575],
            "number_of_home_runs_during_his_career": [1, 69, 63, 225],
            "number_of_runs_during_his_career": [30, 321, 224, 828],
            "number_of_runs_batted_in_during_his_career": [29, 414, 266, 838],
            "number_of_walks_during_his_career": [14, 375, 263, 354],
            "players_league_at_the_end_of_1986": ["A", "N", "A", "N"],
            "players_division_at_the_end_of_1986": ["E", "W", "W", "E"],
            "players_team_at_the_end_of_1986": ["Cle.", "Hou.", "Oak.", "Bos."],
            "players_position(s)_in_1986": ["C", "C", "OF", "1B"],
            "number_of_put_outs_in_1986": [446, 632, 880, 200],
            "number_of_assists_in_1986": [33, 43, 82, 11],
            "number_of_errors_in_1986": [20, 10, 14, 3],
            "players_league_at_the_beginning_of_1987": ["A", "N", "A", "N"],
            "players_team_at_the_beginning_of_1987": ["Cle.", "Hou.", "Oak.", "Bos."],
            target: [None, 475.0, 480.0, 500.0],
        }
    )

    def fake_load_openml(openml_id, requested_target):
        assert openml_id == 525
        assert requested_target == target
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, loaded_target, group = pilot.load_dataset_frame("openml_baseball_hitter_salary")

    assert loaded_target == target
    assert group == "players_league_at_the_end_of_1986"
    assert "players_league_at_the_end_of_1986" in df.columns
    assert "players_division_at_the_end_of_1986" in df.columns
    assert "players_position(s)_in_1986" in df.columns
    assert target in df.columns
    assert {
        "hitters_name",
        "players_team_at_the_end_of_1986",
        "players_league_at_the_beginning_of_1987",
        "players_team_at_the_beginning_of_1987",
    }.isdisjoint(df.columns)


def test_openml_baseball_pitcher_loader_drops_team_and_roster_fields(
    monkeypatch,
):
    target = "1987_annual_salary_on_opening_day_in_thousands_of_dollars"
    source = pd.DataFrame(
        {
            "players_team_at_the_end_of_in_1986": ["Bos.", "Cle.", "Hou.", "Oak."],
            "players_league_at_the_end_of_1986": ["A", "A", "N", "A"],
            "number_of_wins_in_1986": [12, 8, 20, 9],
            "number_of_losses_in_1986": [9, 10, 8, 7],
            "earned_run_average_in_1986": [3.2, 4.1, 2.8, 3.6],
            "number_of_games_in_1986": [30, 27, 36, 25],
            "number_of_innings_pitched_in_1986": [180.1, 140.2, 220.0, 110.0],
            "number_of_saves_in_1986": [0, 2, 0, 12],
            "number_of_years_in_the_major_leagues": [5, 3, 11, 8],
            "number_of_wins_during_his_career": [50, 24, 150, 62],
            "number_of_losses_during_his_career": [44, 28, 98, 55],
            "earned_run_average_during_his_career": [3.5, 4.0, 3.1, 3.7],
            "number_of_games_during_his_career": [190, 88, 410, 300],
            "number_of_innings_pitched_during_his_career": [
                900.0,
                420.2,
                2500.1,
                980.0,
            ],
            "number_of_saves_during_his_career": [4, 6, 2, 120],
            "players_league_at_the_beginning_of_1987": ["A", "A", "N", "A"],
            "players_team_at_the_beginning_of_1987": ["Bos.", "Cle.", "Hou.", "Oak."],
            target: [550.0, None, 900.0, 640.0],
        }
    )

    def fake_load_openml(openml_id, requested_target):
        assert openml_id == 495
        assert requested_target == target
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, loaded_target, group = pilot.load_dataset_frame("openml_baseball_pitcher_salary")

    assert loaded_target == target
    assert group == "players_league_at_the_end_of_1986"
    assert "players_league_at_the_end_of_1986" in df.columns
    assert "number_of_wins_in_1986" in df.columns
    assert target in df.columns
    assert {
        "players_team_at_the_end_of_in_1986",
        "players_league_at_the_beginning_of_1987",
        "players_team_at_the_beginning_of_1987",
    }.isdisjoint(df.columns)


def test_openml_baseball_team_loader_uses_league_and_drops_team_identity(
    monkeypatch,
):
    target = "1987_average_salary"
    source = pd.DataFrame(
        {
            "league": ["A", "A", "N", "N"],
            "division": ["E", "W", "E", "W"],
            "position_in_final_league_standings_in_1986": ["1", "2", "3", "4"],
            "team": ["Bos.", "Oak.", "Atl.", "L.A."],
            "number_of_wins_in_1986": [95, 76, 108, 73],
            "number_of_losses_in_1986": [66, 86, 54, 89],
            "attendance_for_home_games_in_1986": [2147641, 1314895, 2767601, 3023208],
            "attendance_for_away_games_in_1986": [2012187, 1801122, 2176615, 2139312],
            target: [445978.0, 405340.0, 526899.0, 580250.0],
        }
    )

    def fake_load_openml(openml_id, requested_target):
        assert openml_id == 515
        assert requested_target == target
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, loaded_target, group = pilot.load_dataset_frame("openml_baseball_team_salary")

    assert loaded_target == target
    assert group == "league"
    assert "league" in df.columns
    assert "division" in df.columns
    assert "position_in_final_league_standings_in_1986" in df.columns
    assert target in df.columns
    assert "team" not in df.columns


def test_openml_house_16h_loader_bins_and_drops_p14p9_proxy(monkeypatch):
    source = pd.DataFrame(
        {
            "P1": [1000.0, 2000.0, 3000.0, 4000.0, 5000.0],
            "P5p1": [0.1, 0.2, 0.3, 0.4, 0.5],
            "P6p2": [0.05, 0.04, 0.03, 0.02, 0.01],
            "P11p4": [0.2, 0.3, 0.4, 0.5, 0.6],
            "P14p9": [0.9, 0.7, 0.5, 0.3, 0.1],
            "P15p1": [0.1, 0.2, 0.1, 0.2, 0.1],
            "P15p3": [0.0, 0.1, 0.0, 0.1, 0.0],
            "P16p2": [0.5, 0.6, 0.7, 0.8, 0.9],
            "P18p2": [0.01, 0.02, 0.03, 0.04, 0.05],
            "P27p4": [0.2, 0.25, 0.3, 0.35, 0.4],
            "H2p2": [0.1, 0.2, 0.3, 0.4, 0.5],
            "H8p2": [0.0, 0.1, 0.2, 0.3, 0.4],
            "H10p1": [0.9, 0.8, 0.7, 0.6, 0.5],
            "H13p1": [0.4, 0.3, 0.2, 0.1, 0.0],
            "H18pA": [0.01, 0.02, 0.03, 0.04, 0.05],
            "H40p4": [0.7, 0.6, 0.5, 0.4, 0.3],
            "price": [0.0, 15000.0, 30000.0, 60000.0, 120000.0],
        }
    )

    def fake_load_openml(openml_id, requested_target):
        assert openml_id == 574
        assert requested_target == "price"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, loaded_target, group = pilot.load_dataset_frame("openml_house_16h_price")

    assert loaded_target == "price"
    assert group == "p14p9_bin"
    assert "p14p9_bin" in df.columns
    assert "P14p9" not in df.columns
    assert "price" in df.columns
    assert "P1" in df.columns
    assert df["p14p9_bin"].dtype == object
    assert df["p14p9_bin"].nunique() == 4


def test_openml_kin8nm_loader_bins_and_drops_theta3_proxy(monkeypatch):
    source = pd.DataFrame(
        {
            "theta1": [0.1, 0.2, 0.3, 0.4, 0.5],
            "theta2": [0.5, 0.4, 0.3, 0.2, 0.1],
            "theta3": [0.9, 0.7, 0.5, 0.3, 0.1],
            "theta4": [0.2, 0.3, 0.4, 0.5, 0.6],
            "theta5": [0.0, 0.1, 0.2, 0.3, 0.4],
            "theta6": [0.6, 0.5, 0.4, 0.3, 0.2],
            "theta7": [0.3, 0.2, 0.1, 0.0, -0.1],
            "theta8": [0.05, 0.15, 0.25, 0.35, 0.45],
            "y": [0.2, 0.4, 0.6, 0.8, 1.0],
        }
    )

    def fake_load_openml(openml_id, requested_target):
        assert openml_id == 189
        assert requested_target == "y"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, loaded_target, group = pilot.load_dataset_frame("openml_kin8nm_y")

    assert loaded_target == "y"
    assert group == "theta3_bin"
    assert "theta3_bin" in df.columns
    assert "theta3" not in df.columns
    assert "y" in df.columns
    assert "theta1" in df.columns
    assert df["theta3_bin"].dtype == object
    assert df["theta3_bin"].nunique() == 4


def test_openml_delta_elevators_loader_bins_and_drops_climbrate_proxy(monkeypatch):
    source = pd.DataFrame(
        {
            "climbRate": [-2.0, -1.0, 0.0, 1.0, 2.0],
            "Altitude": [1000.0, 1100.0, 1200.0, 1300.0, 1400.0],
            "RollRate": [0.1, 0.2, 0.1, 0.2, 0.1],
            "curRoll": [1.0, 0.5, 0.0, -0.5, -1.0],
            "diffClb": [-0.2, -0.1, 0.0, 0.1, 0.2],
            "diffDiffClb": [0.01, 0.02, 0.03, 0.04, 0.05],
            "Se": [-0.003, -0.001, 0.0, 0.001, 0.003],
        }
    )

    def fake_load_openml(openml_id, requested_target):
        assert openml_id == 198
        assert requested_target == "Se"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, loaded_target, group = pilot.load_dataset_frame(
        "openml_delta_elevators_se"
    )

    assert loaded_target == "Se"
    assert group == "climbRate_bin"
    assert "climbRate_bin" in df.columns
    assert "climbRate" not in df.columns
    assert "Se" in df.columns
    assert "Altitude" in df.columns
    assert df["climbRate_bin"].dtype == object
    assert df["climbRate_bin"].nunique() == 4


def test_openml_arsenic_event_rate_panel_derives_rate_and_drops_exposure(
    monkeypatch,
):
    frames = {}
    for openml_id in [533, 513, 482, 536]:
        frames[openml_id] = pd.DataFrame(
            {
                "group": ["1", "2"],
                "conc": [0, 50],
                "age": [42.5, 67.5],
                "at.risk": [100000, 50000],
                "events": [10, 5],
            }
        )

    def fake_load_openml(openml_id, requested_target):
        assert requested_target == "events"
        return frames[openml_id].copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, loaded_target, group = pilot.load_dataset_frame(
        "openml_arsenic_event_rate_panel"
    )

    assert loaded_target == "event_rate_per_100k"
    assert group == "sex"
    assert len(df) == 8
    assert set(df["sex"]) == {"female", "male"}
    assert set(df["cancer_site"]) == {"bladder", "lung"}
    assert df["event_rate_per_100k"].tolist() == [10.0, 10.0] * 4
    assert not {"events", "at.risk", "group", "openml_id"} & set(df.columns)
    assert {"conc", "age", "sex", "cancer_site", "event_rate_per_100k"} <= set(
        df.columns
    )


def test_openml_hiroshima_rate_loader_derives_rate_and_dedup_variant(monkeypatch):
    source = pd.DataFrame(
        {
            "Dose": [0.0, 0.0, 38.0, 143.9, 244.1, 346.9, 666.6],
            "Total_cells": ["100", "100", "100", "100", "100", "100", "100"],
            "Aberrant_cells": [0, 0, 6, 12, 24, 35, 42],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 494
        assert target == "Aberrant_cells"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    raw, target, group = pilot.load_dataset_frame(
        "openml_analcatdata_hiroshima_rate"
    )
    dedup, dedup_target, dedup_group = pilot.load_dataset_frame(
        "openml_analcatdata_hiroshima_rate_dedup"
    )

    assert target == dedup_target == "aberrant_rate_per_100"
    assert group == dedup_group == "dose_band"
    assert len(raw) == 7
    assert len(dedup) == 6
    assert raw["aberrant_rate_per_100"].tolist() == [
        0.0,
        0.0,
        6.0,
        12.0,
        24.0,
        35.0,
        42.0,
    ]
    assert not {"Aberrant_cells", "Total_cells"} & set(raw.columns)
    assert set(raw["dose_band"]) == {"low_0_38", "mid_144_244", "high_347_667"}
    assert raw.loc[raw["Dose"].eq(143.9), "dose_band"].item() == "mid_144_244"
    assert raw.loc[raw["Dose"].eq(346.9), "dose_band"].item() == "high_347_667"
    assert {"Dose", "dose_band", "aberrant_rate_per_100"} <= set(raw.columns)


def test_openml_sleuth_case1202_experience_loader_drops_age_and_salary(monkeypatch):
    source = pd.DataFrame(
        {
            "bsal": [12000, 13000, 13500, 15000, 15500, 16000],
            "sal77": [18000, 19000, 21000, 23000, 24000, 26000],
            "fsex": ["0", "1", "0", "1", "0", "1"],
            "senior": [1, 2, 3, 4, 5, 6],
            "age": [280, 360, 460, 560, 650, 770],
            "educ": ["8", "10", "12", "15", "16", "16"],
            "exper": [0.0, 25.0, 75.0, 130.0, 220.0, 381.0],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 706
        assert target == "exper"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame(
        "openml_sleuth_case1202_experience"
    )

    assert target == "exper"
    assert group == "fsex"
    assert "age_bin" in df.columns
    assert "age" not in df.columns
    assert not {"bsal", "sal77"} & set(df.columns)
    assert {"fsex", "senior", "educ", "exper", "age_bin"} <= set(df.columns)
    assert df["age_bin"].dtype == object
    assert df["age_bin"].nunique() == 4


def test_openml_sleuth_case1201_rank_loader_bins_and_drops_income(monkeypatch):
    source = pd.DataFrame(
        {
            "sat": [790, 850, 910, 970, 1030, 1088],
            "takers": [69, 55, 35, 16, 5, 2],
            "income": [208, 240, 270, 300, 330, 401],
            "years": [14.39, 15.5, 16.0, 16.4, 16.9, 17.41],
            "public": [44.8, 70.0, 80.0, 86.0, 90.0, 97.0],
            "expend": [13.84, 18.0, 21.0, 25.0, 30.0, 50.1],
            "rank": [69.8, 74.0, 79.5, 82.0, 86.0, 90.6],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 707
        assert target == "rank"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_sleuth_case1201_rank")

    assert target == "rank"
    assert group == "income_bin"
    assert "income_bin" in df.columns
    assert "income" not in df.columns
    assert {"sat", "takers", "years", "public", "expend", "rank", "income_bin"} <= set(
        df.columns
    )
    assert df["income_bin"].dtype == object
    assert df["income_bin"].nunique() == 4


def test_openml_sleuth_ex1714_invol_loader_bins_race_and_drops_leakage(
    monkeypatch,
):
    source = pd.DataFrame(
        {
            "zip": [26, 40, 13, 57, 14, 10, 11, 25],
            "fire": [6.2, 9.5, 10.5, 7.7, 8.6, 34.1, 11.0, 6.9],
            "theft": [29, 44, 36, 37, 53, 68, 75, 18],
            "age": [60.4, 76.5, 73.5, 66.9, 81.4, 52.6, 42.6, 78.5],
            "income": [11744, 9323, 9948, 10656, 9730, 5583, 8864, 11878],
            "race": [10.0, 22.2, 19.6, 17.3, 24.5, 81.3, 86.2, 13.2],
            "vol": [5.3, 3.1, 4.8, 5.7, 5.9, 0.5, 1.2, 6.1],
            "invol": [0.0, 0.1, 1.2, 0.5, 0.7, 2.2, 1.9, 0.0],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 659
        assert target == "invol"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_sleuth_ex1714_invol")

    assert target == "invol"
    assert group == "race_bin"
    assert "race_bin" in df.columns
    assert {"zip", "race", "vol"}.isdisjoint(df.columns)
    assert {"fire", "theft", "age", "income", "invol", "race_bin"} <= set(
        df.columns
    )
    assert df["race_bin"].dtype == object
    assert df["race_bin"].nunique() == 4


def test_openml_icu_loc_loader_drops_outcome_and_sensitive_proxies(monkeypatch):
    source = pd.DataFrame(
        {
            "ID": list(range(8)),
            "STA": [0, 0, 1, 0, 1, 0, 0, 1],
            "AGE": [27, 59, 77, 54, 87, 35, 63, 72],
            "SEX": [2, 1, 1, 1, 2, 2, 1, 2],
            "RAC": [1, 1, 2, 1, 3, 1, 1, 2],
            "SER": [1, 1, 2, 1, 2, 1, 2, 1],
            "CAN": [1, 1, 1, 1, 1, 2, 1, 2],
            "CRN": [1, 1, 1, 1, 2, 1, 2, 1],
            "INF": [2, 1, 1, 2, 2, 1, 2, 1],
            "CPR": [1, 1, 1, 1, 2, 1, 1, 2],
            "SYS": [142.0, 112.0, 100.0, 142.0, 110.0, 128.0, 92.0, 140.0],
            "HRA": [88, 80, 70, 103, 154, 91, 122, 78],
            "PRE": [1, 2, 1, 1, 2, 1, 1, 2],
            "TYP": [2, 2, 1, 2, 2, 1, 2, 1],
            "FRA": [1, 1, 1, 2, 1, 1, 2, 1],
            "PO2": [1, 1, 1, 1, 2, 1, 2, 1],
            "PH": [1, 1, 1, 1, 2, 1, 1, 2],
            "PCO": [1, 1, 1, 1, 2, 1, 2, 1],
            "BIC": [1, 1, 1, 1, 2, 1, 1, 2],
            "CRE": [1, 1, 1, 1, 2, 1, 2, 1],
            "LOC": [1, 1, 2, 1, 3, 1, 2, 1],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 1097
        assert target == "LOC"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_icu_loc")

    assert target == "LOC"
    assert group == "SEX"
    assert "age_bin" in df.columns
    assert {"ID", "STA", "AGE", "RAC"}.isdisjoint(df.columns)
    assert {"SEX", "SER", "CAN", "CRN", "INF", "CPR", "SYS", "LOC", "age_bin"} <= set(
        df.columns
    )
    assert df["age_bin"].dtype == object
    assert df["age_bin"].nunique() == 4


def test_openml_newton_hema_loader_bins_weeks_and_drops_sample_size(monkeypatch):
    source = pd.DataFrame(
        {
            "id": ["40004", "40004", "40005a", "40005a", "63132", "65044"],
            "weeks": [0.0, 12.0, 24.0, 60.0, 120.0, 240.0],
            "cells_percentage": [18, 24, 31, 42, 66, 80],
            "sample_size": [50, 55, 48, 60, 52, 57],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 492
        assert target == "cells_percentage"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_newton_hema_cells")

    assert target == "cells_percentage"
    assert group == "weeks_bin"
    assert "weeks_bin" in df.columns
    assert "sample_size" not in df.columns
    assert {"id", "weeks", "cells_percentage", "weeks_bin"} <= set(df.columns)
    assert df["weeks_bin"].dtype == object
    assert df["weeks_bin"].nunique() == 4


def test_openml_basketball_loader_bins_age_and_drops_raw_age(monkeypatch):
    source = pd.DataFrame(
        {
            "assists_per_minute": [0.08, 0.12, 0.03, 0.15, 0.09, 0.02],
            "height": [185, 193, 188, 196, 180, 201],
            "time_played": [18.2, 31.4, 25.7, 40.1, 12.0, 36.5],
            "age": [22, 24, 26, 28, 30, 34],
            "points_per_minute": [0.31, 0.45, 0.39, 0.58, 0.25, 0.62],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 214
        assert target == "points_per_minute"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_basketball_points_per_minute")

    assert target == "points_per_minute"
    assert group == "age_bin"
    assert "age_bin" in df.columns
    assert "age" not in df.columns
    assert {
        "assists_per_minute",
        "height",
        "time_played",
        "points_per_minute",
    } <= set(df.columns)


def test_openml_galapagos_loader_bins_area_and_drops_native_species(monkeypatch):
    source = pd.DataFrame(
        {
            "Observed.species": [2, 18, 58, 444, 31, 10],
            "Native.species": [1.0, 11.0, 23.0, 95.0, 21.0, 7.0],
            "Area(km^2)": [0.05, 0.34, 25.09, 4669.32, 1.24, 2.33],
            "Elevation(m)": [None, 119.0, None, 1707.0, 109.0, 168.0],
            "Distance.nearest.island(km)": [1.9, 8.0, 0.6, 0.7, 0.6, 34.1],
            "Distance.Santa.Cruz(km)": [1.9, 8.0, 0.6, 0.7, 26.3, 290.2],
            "Area.adj.island(km^2)": [903.82, 1.84, 1.84, 0.52, 572.33, 2.85],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 539
        assert target == "Observed.species"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_analcatdata_galapagos")

    assert target == "Observed.species"
    assert group == "area_bin"
    assert "area_bin" in df.columns
    assert "Native.species" not in df.columns
    assert {
        "Observed.species",
        "Area(km^2)",
        "Elevation(m)",
        "Distance.nearest.island(km)",
        "Distance.Santa.Cruz(km)",
        "Area.adj.island(km^2)",
    } <= set(df.columns)


def test_openml_mercury_loader_drops_mercury_summaries_and_sample_count(
    monkeypatch,
):
    source = pd.DataFrame(
        {
            "Alkalinity": [5.9, 3.5, 116.0, 39.4],
            "pH": [6.1, 5.1, 9.1, 6.9],
            "Calcium": [3.0, 1.9, 44.1, 16.4],
            "Chlorophyll": [0.7, 3.2, 128.3, 3.5],
            "Avg_Mercury": [1.23, 1.33, 0.04, 0.44],
            "No.samples": [5, 7, 6, 12],
            "min": [0.85, 0.92, 0.04, 0.13],
            "max": [1.43, 1.90, 0.06, 0.84],
            "age_data": [1, 0, 0, 0],
            "3_yr_Standard_Mercury": [1.53, 1.33, 0.04, 0.44],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 1090
        assert target == "3_yr_Standard_Mercury"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_mercury_in_bass")

    assert target == "3_yr_Standard_Mercury"
    assert group == "age_data"
    assert "age_data" in df.columns
    assert {"Avg_Mercury", "min", "max", "No.samples"}.isdisjoint(df.columns)
    assert {
        "Alkalinity",
        "pH",
        "Calcium",
        "Chlorophyll",
        "3_yr_Standard_Mercury",
    } <= set(df.columns)


def test_openml_mtp2_loader_bins_descriptor_and_drops_raw_group(monkeypatch):
    source = pd.DataFrame(
        {
            "oz1": [0.2, 0.4, 0.3, 0.5, 0.7, 0.1, 0.9, 0.6],
            "oz2": [0.01, 0.12, 0.23, 0.34, 0.45, 0.56, 0.67, 0.78],
            "oz3": [1.0, 1.2, 1.1, 1.3, 1.4, 1.5, 1.6, 1.7],
            "oz1143": [0.05, 0.12, 0.18, 0.26, 0.33, 0.44, 0.58, 0.72],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 430
        assert target == "oz1143"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_mtp2_oz1143")

    assert target == "oz1143"
    assert group == "oz2_bin"
    assert "oz2_bin" in df.columns
    assert "oz2" not in df.columns
    assert {"oz1", "oz3", "oz1143"} <= set(df.columns)


def test_openml_hutsof99_loader_drops_age_and_keeps_gender_group(monkeypatch):
    source = pd.DataFrame(
        {
            "Age": ["0", "1", "0", "1"],
            "Gender": ["0", "0", "1", "1"],
            "Location": ["1", "2", "3", "4"],
            "Coherence": [4.2, 3.7, 5.1, 4.8],
            "Maturity": [2.0, 2.5, 3.0, 3.5],
            "Delay": [12.0, 35.0, 67.0, 101.0],
            "Prosecute": ["0", "1", "0", "1"],
            "Quality": [53.4, 66.2, 59.9, 72.1],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 681
        assert target == "Quality"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_hutsof99_quality")

    assert target == "Quality"
    assert group == "Gender"
    assert "Gender" in df.columns
    assert "Age" not in df.columns
    assert {"Location", "Coherence", "Maturity", "Delay", "Prosecute", "Quality"} <= set(
        df.columns
    )


def test_openml_mba_grade_loader_supports_raw_and_dedup_variants(monkeypatch):
    source = pd.DataFrame(
        {
            "sex": ["0", "0", "1", "1", "0"],
            "GMAT": [560, 560, 610, 640, 520],
            "grade_point_average": [3.2, 3.2, 3.6, 3.8, 3.0],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 190
        assert target == "grade_point_average"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    raw, target, group = pilot.load_dataset_frame("openml_mba_grade_gpa")
    dedup, dedup_target, dedup_group = pilot.load_dataset_frame(
        "openml_mba_grade_gpa_dedup"
    )

    assert target == dedup_target == "grade_point_average"
    assert group == dedup_group == "sex"
    assert len(raw) == 5
    assert len(dedup) == 4
    assert {"sex", "GMAT", "grade_point_average"} <= set(raw.columns)
    assert {"sex", "GMAT", "grade_point_average"} <= set(dedup.columns)


def test_openml_seropositive_loader_derives_age_bin_and_drops_denominator(
    monkeypatch,
):
    source = pd.DataFrame(
        {
            "Age": [1, 6, 12, 18, 24, 30, 36, 44],
            "Disease": [
                "Mumps",
                "Mumps",
                "Rubella",
                "Rubella",
                "Parvovirus",
                "Parvovirus",
                "Mumps",
                "Rubella",
            ],
            "Total": [50, 60, 90, 100, 120, 140, 180, 220],
            "Positive": [20, 30, 50, 65, 40, 45, 160, 170],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 526
        assert target == "Positive"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_analcatdata_seropositive")

    assert target == "Positive"
    assert group == "age_bin"
    assert "age_bin" in df.columns
    assert {"Age", "Total"}.isdisjoint(df.columns)
    assert {"Disease", "Positive"} <= set(df.columns)


def test_openml_bodyfat_loader_derives_age_bin_and_drops_density_leakage(
    monkeypatch,
):
    source = pd.DataFrame(
        {
            "Density": [1.07, 1.08, 1.04, 1.03, 1.06, 1.05, 1.02, 1.09],
            "Age": [22, 30, 37, 42, 48, 55, 63, 81],
            "Weight": [154.25, 173.25, 184.75, 190.25, 210.0, 180.0, 165.0, 150.0],
            "Height": [67.75, 72.25, 72.25, 69.5, 70.0, 68.0, 66.5, 65.0],
            "Neck": [36.2, 38.5, 37.4, 39.0, 40.0, 38.0, 36.0, 35.5],
            "Chest": [93.1, 93.6, 101.8, 105.0, 110.0, 100.0, 95.0, 92.0],
            "Abdomen": [85.2, 83.0, 86.4, 95.0, 102.0, 92.0, 88.0, 84.0],
            "Hip": [94.5, 98.7, 101.2, 105.0, 108.0, 100.0, 97.0, 94.0],
            "Thigh": [59.0, 58.7, 60.1, 61.0, 64.0, 59.0, 57.0, 55.0],
            "Knee": [37.3, 37.3, 37.3, 39.0, 40.0, 38.0, 37.0, 36.0],
            "Ankle": [21.9, 23.4, 22.8, 24.0, 25.0, 23.0, 22.0, 21.5],
            "Biceps": [32.0, 30.5, 32.4, 33.0, 34.0, 32.0, 31.0, 30.0],
            "Forearm": [27.4, 28.9, 29.4, 30.0, 31.0, 29.0, 28.0, 27.0],
            "Wrist": [17.1, 18.2, 18.2, 18.5, 19.0, 18.0, 17.5, 17.0],
            "class": [12.3, 6.1, 10.4, 18.2, 24.4, 21.0, 27.5, 32.0],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 560
        assert target == "class"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_bodyfat_percentage")

    assert target == "class"
    assert group == "age_bin"
    assert "age_bin" in df.columns
    assert {"Age", "Density"}.isdisjoint(df.columns)
    assert {"Weight", "Abdomen", "Wrist", "class"} <= set(df.columns)


def test_openml_space_ga_loader_derives_income_and_spatial_bins(monkeypatch):
    source = pd.DataFrame(
        {
            "POP": [9.0, 10.0, 11.0, 12.0, 13.0],
            "EDUCATION": [8.0, 9.0, 10.0, 11.0, 12.0],
            "HOUSES": [7.0, 8.0, 9.0, 10.0, 11.0],
            "INCOME": [10.0, 11.0, 12.0, 13.0, 14.0],
            "XCOORD": [-5.0, -4.0, -3.0, -2.0, -1.0],
            "YCOORD": [30.0, 31.0, 32.0, 33.0, 34.0],
            "ln(VOTES/POP)": [-0.8, -0.7, -0.6, -0.5, -0.4],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 507
        assert target == "ln(VOTES/POP)"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_space_ga_log_votes_pop")

    assert target == "ln(VOTES/POP)"
    assert group == "income_bin"
    assert group in df.columns
    assert "xcoord_bin" in df.columns
    assert "INCOME" not in df.columns
    assert {"XCOORD", "YCOORD"} <= set(df.columns)
    assert pilot.DATASET_LOADERS["openml_space_ga_log_votes_pop"][
        "feature_drop_columns"
    ] == ["XCOORD", "YCOORD"]


def test_openml_smsa_nox_loader_derives_proxy_bins_and_drops_leakage(monkeypatch):
    source = pd.DataFrame(
        {
            "JanTemp": [20, 25, 30, 35, 40, 45, 50, 55],
            "JulyTemp": [70, 71, 72, 73, 74, 75, 76, 77],
            "RelHum": [50, 51, 52, 53, 54, 55, 56, 57],
            "Rain": [30, 31, 32, 33, 34, 35, 36, 37],
            "Mortality": [900.0, 910.0, 920.0, 930.0, 940.0, 950.0, 960.0, 970.0],
            "Education": [9.0, 9.5, 10.0, 10.5, 11.0, 11.5, 12.0, 12.5],
            "PopDensity": [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000],
            "%NonWhite": [1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0],
            "%WC": [40.0, 41.0, 42.0, 43.0, 44.0, 45.0, 46.0, 47.0],
            "pop": [100_000, 110_000, 120_000, 130_000, 140_000, 150_000, 160_000, 170_000],
            "pop/house": [3.0, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7],
            "income": [25_000, 27_000, 29_000, 31_000, 33_000, 35_000, 37_000, 39_000],
            "HCPot": [5, 6, 7, 8, 9, 10, 11, 12],
            "NOxPot": [1, 2, 3, 4, 5, 6, 7, 8],
            "S02Pot": [15, 16, 17, 18, 19, 20, 21, 22],
            "NOx": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 1091
        assert target == "NOx"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_smsa_nox")

    assert target == "NOx"
    assert group == "nonwhite_bin"
    assert "nonwhite_bin" in df.columns
    assert "income_bin" in df.columns
    assert {
        "%NonWhite",
        "income",
        "Mortality",
        "HCPot",
        "NOxPot",
        "S02Pot",
    }.isdisjoint(df.columns)
    assert {"JanTemp", "JulyTemp", "Education", "PopDensity", "NOx"} <= set(
        df.columns
    )
    assert pilot.DATASET_LOADERS["openml_smsa_nox"]["feature_drop_columns"] == [
        "income_bin"
    ]


def test_openml_socmob_loader_drops_first_occupation_co_outcome(monkeypatch):
    source = pd.DataFrame(
        {
            "fathers_occupation": [
                "Professional_Self-Employed",
                "Professional-Salaried",
                "Manager",
                "Clerical_and_Sales",
            ],
            "sons_occupation": [
                "Professional-Salaried",
                "Manager",
                "Clerical_and_Sales",
                "Manual",
            ],
            "family_structure": ["intact", "intact", "broken", "broken"],
            "race": ["white", "black", "white", "black"],
            "counts_for_sons_first_occupation": [96.2, 2.3, 18.1, 0.6],
            "counts_for_sons_current_occupation": [86.6, 1.8, 47.2, 0.4],
        }
    )

    def fake_load_openml(openml_id, target):
        assert openml_id == 541
        assert target == "counts_for_sons_current_occupation"
        return source.copy()

    monkeypatch.setattr(pilot, "load_openml_regression_frame", fake_load_openml)

    df, target, group = pilot.load_dataset_frame("openml_socmob_sons_occupation")

    assert target == "counts_for_sons_current_occupation"
    assert group == "race"
    assert "counts_for_sons_first_occupation" not in df.columns
    assert {
        "fathers_occupation",
        "sons_occupation",
        "family_structure",
        "race",
        "counts_for_sons_current_occupation",
    } <= set(df.columns)


def test_openml_california_housing_loader_is_registered_as_ocean_proxy_benchmark():
    spec = DATASET_LOADERS["openml_california_housing"]

    assert spec["source"] == "openml"
    assert spec["openml_id"] == 43939
    assert spec["target"] == "median_house_value"
    assert spec["group"] == "ocean_proximity"


def test_uci_wine_quality_loader_keeps_color_and_dedup_variant(monkeypatch):
    source = pd.DataFrame(
        {
            "fixed_acidity": [7.4, 7.4, 7.8, 6.3],
            "volatile_acidity": [0.7, 0.7, 0.88, 0.3],
            "alcohol": [9.4, 9.4, 9.8, 9.5],
            "quality": [5, 5, 5, 6],
            "wine_color": ["red", "red", "red", "white"],
        }
    )

    def fake_load(raw_dir, target):
        assert raw_dir == "data/raw/uci/wine_quality"
        assert target == "quality"
        return source.copy()

    monkeypatch.setattr(pilot, "load_uci_wine_quality_frame", fake_load)

    raw_df, target, group = pilot.load_dataset_frame("uci_wine_quality")
    dedup_df, dedup_target, dedup_group = pilot.load_dataset_frame(
        "uci_wine_quality_dedup"
    )

    assert target == dedup_target == "quality"
    assert group == dedup_group == "wine_color"
    assert raw_df["wine_color"].tolist() == ["red", "red", "red", "white"]
    assert len(raw_df) == 4
    assert len(dedup_df) == 3
    assert dedup_df.duplicated().sum() == 0


def test_uci_student_performance_prior_grade_variants(monkeypatch):
    source = pd.DataFrame(
        {
            "school": ["GP", "MS"],
            "sex": ["F", "M"],
            "age": [17, 18],
            "studytime": [2, 3],
            "G1": [10, 13],
            "G2": [11, 14],
            "G3": [12, 15],
        }
    )

    def fake_load_uci_frame(uci_id, target, extra_target_columns=()):
        assert uci_id == 320
        assert target == "G3"
        assert list(extra_target_columns) == ["G1", "G2"]
        return source.copy()

    monkeypatch.setattr(pilot, "load_uci_frame", fake_load_uci_frame)

    with_prior, target, group = pilot.load_dataset_frame(
        "uci_student_performance_with_prior_grades"
    )
    no_prior, no_prior_target, no_prior_group = pilot.load_dataset_frame(
        "uci_student_performance_no_prior_grades"
    )

    assert target == no_prior_target == "G3"
    assert group == no_prior_group == "sex"
    assert {"G1", "G2"} <= set(with_prior.columns)
    assert {"G1", "G2"} & set(no_prior.columns) == set()
    assert no_prior["G3"].tolist() == [12, 15]


def test_lawschool_dedup_loader_drops_exact_duplicate_rows(monkeypatch):
    X = pd.DataFrame(
        {
            "race": ["white", "white", "black", "white"],
            "gender": ["male", "male", "female", "male"],
            "lsat": [160.0, 160.0, 150.0, 160.0],
            "ugpa": [3.4, 3.4, 3.1, 3.4],
        }
    )
    y = pd.Series([0.7, 0.7, -0.2, 0.8], name="zfygpa")

    def fake_load(target, binary_race):
        assert target == "zfygpa"
        assert binary_race is True
        df = X.reset_index(drop=True).copy()
        df[target] = y.reset_index(drop=True).astype(float)
        return df

    monkeypatch.setattr(pilot, "load_aif360_lawschool_frame", fake_load)

    raw_df, raw_target, raw_group = pilot.load_dataset_frame("aif360_lawschool_gpa")
    dedup_df, dedup_target, dedup_group = pilot.load_dataset_frame(
        "aif360_lawschool_gpa_dedup"
    )

    assert raw_target == dedup_target == "zfygpa"
    assert raw_group == dedup_group == "race"
    assert len(raw_df) == 4
    assert len(dedup_df) == 3
    assert dedup_df.duplicated().sum() == 0
    assert dedup_df["zfygpa"].tolist() == [0.7, -0.2, 0.8]


def test_nhanes_bmi_loader_uses_demographic_smoke_policy(monkeypatch, tmp_path):
    raw_dir = tmp_path / "nhanes"
    raw_dir.mkdir()
    (raw_dir / "DEMO_J.XPT").write_text("placeholder")
    (raw_dir / "BMX_J.XPT").write_text("placeholder")
    monkeypatch.setitem(
        pilot.DATASET_LOADERS["nhanes_2017_2018_bmi"],
        "raw_dir",
        str(raw_dir),
    )

    demo = pd.DataFrame(
        {
            "SEQN": [1.0, 2.0, 3.0],
            "RIAGENDR": [1.0, 2.0, 1.0],
            "RIDRETH3": [3.0, 4.0, 3.0],
            "RIDAGEYR": [30.0, 40.0, 50.0],
            "INDFMPIR": [1.2, None, 4.0],
            "DMDEDUC2": [4.0, 3.0, 5.0],
            "DMDMARTL": [1.0, 5.0, 1.0],
            "WTMEC2YR": [10.0, 20.0, 30.0],
            "SDMVSTRA": [1.0, 1.0, 2.0],
            "SDMVPSU": [1.0, 2.0, 1.0],
        }
    )
    bmx = pd.DataFrame(
        {
            "SEQN": [1.0, 2.0, 3.0],
            "BMXBMI": [21.0, None, 34.0],
            "BMXWT": [60.0, 70.0, 80.0],
            "BMXHT": [170.0, 175.0, 160.0],
            "BMXWAIST": [80.0, 90.0, 100.0],
            "BMXHIP": [90.0, 100.0, 110.0],
        }
    )

    def fake_read_sas(path):
        if path.name == "DEMO_J.XPT":
            return demo
        if path.name == "BMX_J.XPT":
            return bmx
        raise AssertionError(path)

    monkeypatch.setattr(pilot.pd, "read_sas", fake_read_sas)

    df, target, group = pilot.load_dataset_frame("nhanes_2017_2018_bmi")

    assert target == "BMXBMI"
    assert group == "RIDRETH3"
    assert len(df) == 2
    assert df[target].notna().all()
    assert not {
        "SEQN",
        "BMXWT",
        "BMXHT",
        "BMXWAIST",
        "BMXHIP",
        "WTMEC2YR",
        "SDMVSTRA",
        "SDMVPSU",
    } & set(df.columns)
    assert set(df.columns) == {
        "BMXBMI",
        "RIDAGEYR",
        "RIAGENDR",
        "RIDRETH3",
        "INDFMPIR",
        "DMDEDUC2",
        "DMDMARTL",
    }


def test_nhanes_systolic_bp_loader_reuses_audit_policy(monkeypatch, tmp_path):
    raw_dir = tmp_path / "nhanes"
    raw_dir.mkdir()
    monkeypatch.setitem(
        pilot.DATASET_LOADERS["nhanes_2017_2018_systolic_bp"],
        "raw_dir",
        str(raw_dir),
    )
    source = pd.DataFrame(
        {
            "SYSBP_MEAN_3": [120.0, None, 145.0],
            "RIDAGEYR": [30.0, 40.0, 50.0],
            "RIAGENDR": [1.0, 2.0, 1.0],
            "RIDRETH3": [3.0, 4.0, 3.0],
            "INDFMPIR": [1.2, None, 4.0],
            "DMDEDUC2": [4.0, 3.0, 5.0],
            "DMDMARTL": [1.0, 5.0, 1.0],
            "WTMEC2YR": [10.0, 20.0, 30.0],
            "SDMVSTRA": [1.0, 1.0, 2.0],
            "SDMVPSU": [1.0, 2.0, 1.0],
            "BPXSY1": [118.0, None, 142.0],
            "BPXSY2": [122.0, None, 148.0],
            "BPXSY3": [120.0, None, 145.0],
        }
    )

    def fake_load_joined_frame(path):
        assert path == raw_dir
        return source

    monkeypatch.setattr(
        audit_nhanes_systolic_bp,
        "load_joined_frame",
        fake_load_joined_frame,
    )

    df, target, group = pilot.load_dataset_frame("nhanes_2017_2018_systolic_bp")

    assert target == "SYSBP_MEAN_3"
    assert group == "RIDRETH3"
    assert df[target].tolist() == [120.0, 145.0]
    assert set(df.columns) == {
        "SYSBP_MEAN_3",
        "RIDAGEYR",
        "RIAGENDR",
        "RIDRETH3",
        "INDFMPIR",
        "DMDEDUC2",
        "DMDMARTL",
    }
    assert not {
        "WTMEC2YR",
        "SDMVSTRA",
        "SDMVPSU",
        "BPXSY1",
        "BPXSY2",
        "BPXSY3",
    } & set(df.columns)


def test_nhanes_glycohemoglobin_loader_reuses_audit_policy(monkeypatch, tmp_path):
    raw_dir = tmp_path / "nhanes"
    raw_dir.mkdir()
    monkeypatch.setitem(
        pilot.DATASET_LOADERS["nhanes_2017_2018_glycohemoglobin"],
        "raw_dir",
        str(raw_dir),
    )
    source = pd.DataFrame(
        {
            "LBXGH": [5.4, None, 7.2],
            "RIDAGEYR": [30.0, 40.0, 50.0],
            "RIAGENDR": [1.0, 2.0, 1.0],
            "RIDRETH3": [3.0, 4.0, 3.0],
            "INDFMPIR": [1.2, None, 4.0],
            "DMDEDUC2": [4.0, 3.0, 5.0],
            "DMDMARTL": [1.0, 5.0, 1.0],
            "WTMEC2YR": [10.0, 20.0, 30.0],
            "SDMVSTRA": [1.0, 1.0, 2.0],
            "SDMVPSU": [1.0, 2.0, 1.0],
        }
    )

    def fake_load_joined_frame(path):
        assert path == raw_dir
        return source

    monkeypatch.setattr(
        audit_nhanes_glycohemoglobin,
        "load_joined_frame",
        fake_load_joined_frame,
    )

    df, target, group = pilot.load_dataset_frame("nhanes_2017_2018_glycohemoglobin")

    assert target == "LBXGH"
    assert group == "RIDRETH3"
    assert df[target].tolist() == [5.4, 7.2]
    assert set(df.columns) == {
        "LBXGH",
        "RIDAGEYR",
        "RIAGENDR",
        "RIDRETH3",
        "INDFMPIR",
        "DMDEDUC2",
        "DMDMARTL",
    }
    assert not {"WTMEC2YR", "SDMVSTRA", "SDMVPSU"} & set(df.columns)


def test_stackoverflow_compensation_loader_uses_log1p_smoke_policy(
    monkeypatch, tmp_path
):
    raw_dir = tmp_path / "stackoverflow"
    raw_dir.mkdir()
    (raw_dir / "schema.csv").write_text("qid,qname,question,type\n")
    results_path = raw_dir / "results.csv"
    pd.DataFrame(
        {
            "ResponseId": [1, 2, 3, 4],
            "ConvertedCompYearly": [100000.0, None, 0.0, 200000.0],
            "CompTotal": [100000.0, None, 0.0, 180000.0],
            "Currency": ["USD", None, "USD", "EUR"],
            "Age": [
                "25-34 years old",
                "35-44 years old",
                "25-34 years old",
                "45-54 years old",
            ],
            "Country": ["United States of America", "Germany", "India", "France"],
            "EdLevel": ["Bachelor", "Master", "Bachelor", "Doctoral"],
            "Employment": ["Employed", "Employed", "Student", "Employed"],
            "WorkExp": ["5", "10", "Less than 1 year", "More than 50 years"],
            "YearsCode": ["8", "12", "1", "30"],
            "DevType": ["Developer", "Manager", "Student", "Developer"],
            "OrgSize": ["20 to 99 employees", "100 to 499 employees", None, "10,000+"],
            "RemoteWork": ["Remote", "Hybrid", None, "In-person"],
            "Industry": ["Software Development", "Fintech", None, "Manufacturing"],
            "MainBranch": ["I am a developer by profession"] * 4,
            "AISelect": ["Yes", "No", "Yes", "No"],
            "SOVisitFreq": ["Daily", "Weekly", "Monthly", "Daily"],
        }
    ).to_csv(results_path, index=False)
    monkeypatch.setitem(
        pilot.DATASET_LOADERS["stackoverflow_2025_compensation"],
        "raw_dir",
        str(raw_dir),
    )

    df, target, group = pilot.load_dataset_frame("stackoverflow_2025_compensation")

    assert target == "ConvertedCompYearly"
    assert group == "Age"
    assert len(df) == 2
    assert df[target].tolist() == [100000.0, 200000.0]
    assert df["WorkExp_numeric"].tolist() == [5.0, 51.0]
    assert df["YearsCode_numeric"].tolist() == [8.0, 30.0]
    assert not {
        "ResponseId",
        "CompTotal",
        "Currency",
        "WorkExp",
        "YearsCode",
    } & set(df.columns)
    assert set(df.columns) == {
        "ConvertedCompYearly",
        "Age",
        "Country",
        "EdLevel",
        "Employment",
        "WorkExp_numeric",
        "YearsCode_numeric",
        "DevType",
        "OrgSize",
        "RemoteWork",
        "Industry",
        "MainBranch",
        "AISelect",
        "SOVisitFreq",
    }


def test_hmda_interest_rate_loader_reuses_audit_policy(monkeypatch, tmp_path):
    raw_dir = tmp_path / "hmda"
    raw_dir.mkdir()
    raw_path = raw_dir / "hmda_2025_wy_action_taken_1.csv"
    pd.DataFrame(
        {
            "interest_rate": ["6.5", "Exempt", "0", "7.25"],
            "rate_spread": ["0.3", "0.1", "0.0", "0.8"],
            "derived_race": ["White", "Asian", "White", "Black or African American"],
            "derived_ethnicity": ["Not Hispanic or Latino"] * 4,
            "derived_sex": ["Male", "Female", "Joint", "Female"],
            "applicant_age": ["35-44", "45-54", "35-44", "25-34"],
            "county_code": ["56001", "56003", "56001", "56005"],
            "lei": ["L1", "L2", "L1", "L3"],
            "loan_amount": [200000, 150000, 100000, 300000],
            "loan_to_value_ratio": ["80", "75", "70", "65"],
            "property_value": ["250000", "200000", "150000", "450000"],
            "income": ["100", "90", "80", "120"],
        }
    ).to_csv(raw_path, index=False)
    monkeypatch.setitem(
        pilot.DATASET_LOADERS["hmda_2025_wy_interest_rate"],
        "raw_dir",
        str(raw_dir),
    )

    df, target, group = pilot.load_dataset_frame("hmda_2025_wy_interest_rate")

    assert target == "interest_rate"
    assert group == "derived_race"
    assert df[target].tolist() == [6.5, 7.25]
    assert "rate_spread" not in df.columns
    assert "county_code" in df.columns
    assert pd.api.types.is_numeric_dtype(df["loan_to_value_ratio"])


def test_college_scorecard_loader_reuses_audit_policy(monkeypatch, tmp_path):
    raw_dir = tmp_path / "scorecard"
    raw_dir.mkdir()
    monkeypatch.setitem(
        pilot.DATASET_LOADERS["college_scorecard_2026_median_earnings"],
        "raw_dir",
        str(raw_dir),
    )
    source = pd.DataFrame(
        {
            "UNITID": [1, 2, 3, 4],
            "INSTNM": ["A", "B", "C", "D"],
            "CITY": ["x", "y", "z", "q"],
            "STABBR": ["CA", "TX", "NY", "CA"],
            "CONTROL": [1, 2, 1, 3],
            "REGION": [8, 6, 2, 8],
            "LOCALE": [11, 21, 12, 41],
            "UGDS": [1000, 2000, 1500, 800],
            "UGDS_BLACK": [0.1, 0.8, 0.2, 0.05],
            "UGDS_HISP": [0.5, 0.1, 0.2, 0.6],
            "UGDS_WHITE": [0.25, 0.05, 0.45, 0.2],
            "PCTPELL": [0.3, 0.7, 0.4, 0.5],
            "FIRST_GEN": [0.2, 0.5, 0.3, 0.4],
            "MD_EARN_WNE_P10": [60000, "PrivacySuppressed", 45000, 0],
            "MN_EARN_WNE_P10": [65000, 50000, 48000, 25000],
            "C150_4": [0.7, 0.4, 0.6, 0.2],
        }
    )

    def fake_load_source_frame(path):
        assert path == raw_dir
        return source, list(source.columns)

    monkeypatch.setattr(
        audit_college_scorecard_2026_earnings,
        "load_source_frame",
        fake_load_source_frame,
    )

    df, target, group = pilot.load_dataset_frame(
        "college_scorecard_2026_median_earnings"
    )

    assert target == "MD_EARN_WNE_P10"
    assert group == "CONTROL"
    assert df[target].tolist() == [60000.0, 45000.0]
    assert "STABBR" in df.columns
    assert "CONTROL" in df.columns
    assert not {"UNITID", "INSTNM", "CITY", "MN_EARN_WNE_P10", "C150_4"} & set(
        df.columns
    )


def test_meps_expenditure_loader_reuses_audit_policy(monkeypatch, tmp_path):
    raw_dir = tmp_path / "meps"
    raw_dir.mkdir()
    monkeypatch.setitem(
        pilot.DATASET_LOADERS["meps_2023_total_expenditure"],
        "raw_dir",
        str(raw_dir),
    )
    source = pd.DataFrame(
        {
            "DUPERSID": ["a", "b", "c", "d"],
            "TOTEXP23": [0.0, 1000.0, -1.0, 500.0],
            "TOTSLF23": [0.0, 100.0, 0.0, 25.0],
            "ERTOT23": [0.0, 1.0, 0.0, 2.0],
            "PERWT23F": [10.0, 20.0, 30.0, 40.0],
            "VARSTR": [101, 102, 103, 104],
            "VARPSU": [1, 2, 1, 2],
            "PANEL": [27, 27, 28, 28],
            "AGE23X": [25, 45, 65, -1],
            "SEX": [1, 2, 1, 2],
            "RACETHX": [1, 2, 3, 2],
            "POVCAT23": [1, 3, 4, 2],
            "INSCOV23": [1, 2, 3, 1],
            "REGION23": [1, 2, 3, 4],
            "CHOLDX": [-1, 1, 2, -8],
        }
    )

    def fake_load_source_frame(path):
        assert path == raw_dir
        return source, {column: column for column in source.columns}

    monkeypatch.setattr(
        audit_meps_2023_total_expenditure,
        "load_source_frame",
        fake_load_source_frame,
    )

    df, target, group = pilot.load_dataset_frame("meps_2023_total_expenditure")

    assert target == "TOTEXP23"
    assert group == "RACETHX"
    assert df[target].tolist() == [0.0, 1000.0, 500.0]
    assert "RACETHX" in df.columns
    assert "VARSTR" in df.columns
    assert df["CHOLDX"].isna().tolist() == [True, False, True]
    assert not {"DUPERSID", "TOTSLF23", "ERTOT23"} & set(df.columns)
    assert not {"PERWT23F", "VARPSU", "PANEL"} & set(df.columns)


def test_scf_networth_loader_reuses_audit_policy(monkeypatch, tmp_path):
    raw_dir = tmp_path / "scf"
    raw_dir.mkdir()
    monkeypatch.setitem(
        pilot.DATASET_LOADERS["scf_2022_networth"],
        "raw_dir",
        str(raw_dir),
    )
    source = pd.DataFrame(
        {
            "YY1": [1001, 1001, 1002, 1002],
            "Y1": [10011, 10012, 10021, 10022],
            "NETWORTH": [-500.0, 0.0, 250000.0, None],
            "WGT": [10.0, 10.0, 20.0, 20.0],
            "RACECL": [1, 1, 2, 2],
            "RACECL4": [1, 1, 2, 2],
            "RACECL5": [1, 1, 2, 2],
            "RACE": [1, 1, 2, 2],
            "HHSEX": [1, 1, 2, 2],
            "AGE": [45, 45, 60, 60],
            "INCOME": [100000.0, 100000.0, 50000.0, 50000.0],
            "ASSET": [5000.0, 5500.0, 300000.0, 300000.0],
            "DEBT": [5500.0, 5500.0, 50000.0, 50000.0],
        }
    )

    def fake_load_source_frame(path):
        assert path == raw_dir
        return source, list(source.columns)

    monkeypatch.setattr(
        audit_scf_2022_networth,
        "load_source_frame",
        fake_load_source_frame,
    )

    df, target, group = pilot.load_dataset_frame("scf_2022_networth")

    assert target == "NETWORTH"
    assert group == "RACECL"
    assert df[target].tolist() == [-500.0, 0.0, 250000.0]
    assert df["YY1"].tolist() == [1001, 1001, 1002]
    assert "RACECL" in df.columns
    assert "HHSEX" in df.columns
    assert "INCOME" in df.columns
    assert not {"Y1", "WGT", "RACE", "RACECL4", "RACECL5"} & set(df.columns)
    assert not {"ASSET", "DEBT"} & set(df.columns)


def test_oulad_assessment_loader_reuses_audit_policy(monkeypatch, tmp_path):
    raw_dir = tmp_path / "oulad"
    raw_dir.mkdir()
    monkeypatch.setitem(
        pilot.DATASET_LOADERS["oulad_assessment_score"],
        "raw_dir",
        str(raw_dir),
    )
    source = pd.DataFrame(
        {
            "id_student": [1001, 1001, 1002, 1003],
            "id_assessment": [2001, 2002, 2001, 2003],
            "code_module": ["AAA", "AAA", "AAA", "BBB"],
            "code_presentation": ["2013J", "2013J", "2013J", "2014B"],
            "assessment_type": ["TMA", "CMA", "TMA", "Exam"],
            "date": [19.0, 54.0, 19.0, None],
            "weight": [10.0, 20.0, 10.0, 100.0],
            "date_submitted": [18.0, 53.0, 20.0, 120.0],
            "is_banked": [0, 0, 1, 0],
            "gender": ["F", "F", "M", "M"],
            "region": ["London Region", "London Region", "Scotland", "Wales"],
            "highest_education": [
                "HE Qualification",
                "HE Qualification",
                "A Level or Equivalent",
                "Lower Than A Level",
            ],
            "imd_band": ["20-30%", "20-30%", None, "80-90%"],
            "age_band": ["35-55", "35-55", "0-35", "0-35"],
            "num_of_prev_attempts": [0, 0, 1, 0],
            "studied_credits": [60, 60, 120, 90],
            "disability": ["N", "N", "Y", "N"],
            "final_result": ["Pass", "Pass", "Fail", "Distinction"],
            "score": [80.0, None, 55.0, 100.0],
        }
    )

    def fake_load_joined_tables(path):
        assert path == raw_dir
        return source

    monkeypatch.setattr(
        audit_oulad_assessment_score,
        "load_joined_tables",
        fake_load_joined_tables,
    )

    df, target, group = pilot.load_dataset_frame("oulad_assessment_score")

    assert target == "score"
    assert group == "disability"
    assert df[target].tolist() == [80.0, 55.0, 100.0]
    assert df["id_student"].tolist() == [1001, 1002, 1003]
    assert "disability" in df.columns
    assert "id_assessment" not in df.columns
    assert not {"final_result", "date_submitted", "is_banked"} & set(df.columns)


def test_split_frame_can_hold_out_whole_split_groups():
    df = pd.DataFrame(
        {
            "target": range(24),
            "primary_group": ["A", "B", "C", "D"] * 6,
            "county_code": [f"county_{idx // 4}" for idx in range(24)],
            "feature": range(100, 124),
        }
    )

    splits = pilot.split_frame(
        df,
        target="target",
        group_col="primary_group",
        seed=42,
        train_size=0.5,
        calibration_size=0.25,
        split_group_col="county_code",
    )

    split_group_sets = [
        set(splits[name]["county_code"].astype(str)) for name in ["train", "cal", "test"]
    ]
    assert split_group_sets[0].isdisjoint(split_group_sets[1])
    assert split_group_sets[0].isdisjoint(split_group_sets[2])
    assert split_group_sets[1].isdisjoint(split_group_sets[2])
    assert sum(len(splits[name]) for name in ["train", "cal", "test"]) == len(df)
    assert splits["split_group_col"] == "county_code"


def test_split_frame_can_order_holdout_groups_by_time():
    df = pd.DataFrame(
        {
            "target": range(10),
            "primary_group": ["A", "B"] * 5,
            "day": [f"2024-01-{idx + 1:02d}" for idx in range(10)],
            "feature": range(100, 110),
        }
    )

    splits = pilot.split_frame(
        df,
        target="target",
        group_col="primary_group",
        seed=42,
        train_size=0.6,
        calibration_size=0.2,
        split_group_col="day",
        split_strategy="ordered",
        split_order_col="day",
    )

    assert splits["split_strategy"] == "ordered"
    assert splits["split_order_col"] == "day"
    assert splits["train"]["day"].tolist() == [f"2024-01-{idx:02d}" for idx in range(1, 7)]
    assert splits["cal"]["day"].tolist() == ["2024-01-07", "2024-01-08"]
    assert splits["test"]["day"].tolist() == ["2024-01-09", "2024-01-10"]


def test_duplicate_cluster_split_groups_exact_model_visible_repeats():
    df = pd.DataFrame(
        {
            "y": [1.0, 1.0, 2.0, 3.0, 4.0, 4.0],
            "group": ["a", "b", "a", "b", "c", "d"],
            "feature": [10, 10, 20, 30, 40, 40],
            "noise": [0, 0, 1, 2, 3, 3],
        }
    )

    clustered, split_col = pilot.add_duplicate_cluster_split_group(
        df,
        dataset_id="unit_duplicate_cluster",
        target="y",
        group_col="group",
        split_group_col=None,
        scope="model_visible_features_plus_target",
    )
    splits = pilot.split_frame(
        clustered,
        target="y",
        group_col="group",
        seed=3,
        train_size=0.5,
        calibration_size=0.25,
        split_group_col=split_col,
    )

    memberships = {}
    for split_name in ("train", "cal", "test"):
        for _, row in splits[split_name].iterrows():
            memberships.setdefault(row[split_col], set()).add(split_name)

    assert split_col == pilot.DUPLICATE_CLUSTER_SPLIT_COL
    assert all(len(split_names) == 1 for split_names in memberships.values())
    assert clustered.loc[0, split_col] == clustered.loc[1, split_col]
    assert clustered.loc[4, split_col] == clustered.loc[5, split_col]


def test_duplicate_cluster_row_signature_uses_exact_full_rows():
    df = pd.DataFrame(
        {
            "y": [1.0, 1.0, 1.0, 2.0],
            "group": ["a", "a", "b", "b"],
            "feature": [10, 10, 10, 20],
            "noise": [0, 0, 0, 1],
        }
    )

    clustered, split_col = pilot.add_duplicate_cluster_split_group(
        df,
        dataset_id="unit_duplicate_cluster",
        target="y",
        group_col="group",
        split_group_col=None,
        scope="row_signature",
    )

    assert split_col == pilot.DUPLICATE_CLUSTER_SPLIT_COL
    assert clustered.loc[0, split_col] == clustered.loc[1, split_col]
    assert clustered.loc[0, split_col] != clustered.loc[2, split_col]
    assert clustered.loc[2, split_col] != clustered.loc[3, split_col]


def test_duplicate_cluster_split_preserves_base_group_components():
    df = pd.DataFrame(
        {
            "y": [1.0, 2.0, 1.0, 3.0, 4.0, 5.0],
            "primary_group": ["p", "p", "q", "q", "r", "r"],
            "household": ["h1", "h1", "h2", "h2", "h3", "h3"],
            "feature": [7, 8, 7, 9, 10, 11],
        }
    )

    clustered, split_col = pilot.add_duplicate_cluster_split_group(
        df,
        dataset_id="unit_duplicate_cluster",
        target="y",
        group_col="primary_group",
        split_group_col="household",
        scope="model_visible_features_plus_target",
    )

    assert split_col == pilot.DUPLICATE_CLUSTER_SPLIT_COL
    assert clustered.loc[0, split_col] == clustered.loc[2, split_col]
    assert clustered.loc[0, split_col] == clustered.loc[1, split_col]
    assert clustered.loc[2, split_col] == clustered.loc[3, split_col]
    assert clustered.loc[4, split_col] == clustered.loc[5, split_col]
    assert clustered.loc[0, split_col] != clustered.loc[4, split_col]


def test_duplicate_cluster_feature_drop_removes_base_and_cluster_groups():
    df = pd.DataFrame(
        {
            "y": [1.0, 2.0, 1.0, 3.0],
            "primary_group": ["p", "p", "q", "q"],
            "household": ["h1", "h1", "h2", "h2"],
            "feature": [7, 8, 7, 9],
        }
    )

    clustered, split_col = pilot.add_duplicate_cluster_split_group(
        df,
        dataset_id="unit_duplicate_cluster",
        target="y",
        group_col="primary_group",
        split_group_col="household",
        scope="model_visible_features_plus_target",
    )

    assert pilot.runner_feature_drop_columns(
        "unit_duplicate_cluster",
        "y",
        "primary_group",
        split_col,
        clustered,
        base_split_group_col="household",
    ) == ["y", "primary_group", split_col, "household"]


def test_uci_bike_sharing_loader_applies_temporal_leakage_policy(monkeypatch):
    source = pd.DataFrame(
        {
            "instant": [1, 2, 3, 4],
            "dteday": ["2011-01-01", "2011-01-01", "2011-01-02", "2011-01-02"],
            "season": [1, 1, 1, 1],
            "yr": [0, 0, 0, 0],
            "mnth": [1, 1, 1, 1],
            "hr": [0, 1, 2, 3],
            "holiday": [0, 0, 0, 0],
            "weekday": [6, 6, 0, 0],
            "workingday": [0, 0, 0, 0],
            "weathersit": [1, 1, 2, 2],
            "temp": [0.24, 0.22, 0.20, 0.18],
            "atemp": [0.2879, 0.2727, 0.2576, 0.2424],
            "hum": [0.81, 0.80, 0.75, 0.74],
            "windspeed": [0.0, 0.0, 0.1, 0.1],
            "casual": [3, 8, 5, 2],
            "registered": [13, 32, 27, 11],
            "cnt": [16, 40, 32, 13],
        }
    )

    def fake_load_uci_frame(uci_id, target, extra_target_columns=()):
        assert uci_id == 275
        assert target == "cnt"
        assert list(extra_target_columns) == []
        return source.copy()

    monkeypatch.setattr(pilot, "load_uci_frame", fake_load_uci_frame)

    df, target, group = pilot.load_dataset_frame("uci_bike_sharing")

    assert target == "cnt"
    assert group == "season"
    assert "dteday" in df.columns
    assert "season" in df.columns
    assert not {"instant", "casual", "registered"} & set(df.columns)
    assert pilot.DATASET_LOADERS["uci_bike_sharing"]["feature_drop_columns"] == [
        "dteday"
    ]


def test_uci_communities_crime_loader_applies_ecological_smoke_policy(monkeypatch):
    source = pd.DataFrame(
        {
            "state": [1, 1, 2, 2, 3, 3, 4, 4],
            "county": [10, 11, 12, 13, 14, 15, 16, 17],
            "community": [100, 101, 102, 103, 104, 105, 106, 107],
            "communityname": [f"c{i}" for i in range(8)],
            "fold": [1, 1, 2, 2, 3, 3, 4, 4],
            "racepctblack": [0.01, 0.02, 0.04, 0.06, 0.12, 0.2, 0.35, 0.8],
            "racePctWhite": [0.9, 0.85, 0.8, 0.7, 0.6, 0.5, 0.4, 0.2],
            "PctPolicWhite": [None] * 8,
            "LemasSwornFT": [None] * 8,
            "PolicBudgPerPop": [None] * 8,
            "population": [0.1, 0.2, 0.15, 0.3, 0.4, 0.5, 0.6, 0.7],
            "ViolentCrimesPerPop": [0.01, 0.02, 0.08, 0.12, 0.2, 0.3, 0.5, 0.9],
        }
    )

    def fake_load_uci_frame(uci_id, target, extra_target_columns=()):
        assert uci_id == 183
        assert target == "ViolentCrimesPerPop"
        assert list(extra_target_columns) == []
        return source.copy()

    monkeypatch.setattr(pilot, "load_uci_frame", fake_load_uci_frame)

    df, target, group = pilot.load_dataset_frame("uci_communities_crime")

    assert target == "ViolentCrimesPerPop"
    assert group == "racepctblack_bin"
    assert group in df.columns
    assert df[group].nunique() == 4
    assert "ViolentCrimesPerPop" in df.columns
    assert "racePctWhite" in df.columns
    assert "population" in df.columns
    assert not {
        "state",
        "county",
        "community",
        "communityname",
        "fold",
        "racepctblack",
        "PctPolicWhite",
        "LemasSwornFT",
        "PolicBudgPerPop",
    } & set(df.columns)


def test_folktables_poverty_ratio_loader_applies_unweighted_policy(monkeypatch):
    source = pd.DataFrame(
        {
            "POVPIP": [0.0, 120.0, 250.0, 501.0],
            "RAC1P": [1, 1, 3, 8],
            "SEX": [1, 2, 1, 2],
            "AGEP": [18, 35, 50, 80],
            "PWGTP": [10.0, 20.0, 30.0, 40.0],
            "WKHP": [None, 40.0, 20.0, None],
        }
    )

    def fake_loader(raw_dir, target):
        assert raw_dir == "data/raw/folktables"
        assert target == "POVPIP"
        return source.copy()

    monkeypatch.setattr(
        pilot,
        "load_folktables_acs_poverty_ratio_wy_frame",
        fake_loader,
    )

    df, target, group = pilot.load_dataset_frame("folktables_acs_poverty_ratio_wy")

    assert target == "POVPIP"
    assert group == "RAC1P"
    assert df[target].tolist() == [0.0, 120.0, 250.0, 501.0]
    assert "RAC1P" in df.columns
    assert "WKHP" in df.columns
    assert "PWGTP" not in df.columns
