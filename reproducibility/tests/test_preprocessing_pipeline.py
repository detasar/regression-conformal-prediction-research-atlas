import pandas as pd

from cpfi.preprocessing.pipeline import PreprocessingConfig, apply_preprocessing, fit_preprocessing


def test_preprocessing_handles_pandas_categorical_columns_without_missing_category():
    train = pd.DataFrame(
        {
            "race": pd.Categorical(["white", "black", "white"]),
            "score": [1.0, 2.0, 3.0],
        }
    )
    test = pd.DataFrame(
        {
            "race": pd.Categorical(["black", None]),
            "score": [4.0, 5.0],
        }
    )

    preprocessor = fit_preprocessing(train, PreprocessingConfig())
    transformed = apply_preprocessing(test, preprocessor)

    assert transformed["race"].tolist()[0] >= 0
    assert transformed["race"].tolist()[1] == -1
