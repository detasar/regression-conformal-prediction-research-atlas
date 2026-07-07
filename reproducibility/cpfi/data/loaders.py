"""
Dataset loaders for CPFI experiments.

All datasets are BINARY classification (credit scoring focus).
Returns: (X: DataFrame, y: ndarray, sens: dict[attr -> ndarray], source: str)
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, NamedTuple
from sklearn.preprocessing import StandardScaler, LabelEncoder
from loguru import logger

from cpfi import DATA_RAW

# Try optional imports
try:
    import openml
    OPENML_AVAILABLE = True
except ImportError:
    OPENML_AVAILABLE = False
    logger.warning("openml not available")

try:
    from folktables import ACSDataSource, ACSIncome
    FOLKTABLES_AVAILABLE = True
except ImportError:
    FOLKTABLES_AVAILABLE = False
    logger.warning("folktables not available")

try:
    from fairlearn.datasets import fetch_adult
    FAIRLEARN_AVAILABLE = True
except ImportError:
    FAIRLEARN_AVAILABLE = False


class DatasetResult(NamedTuple):
    """Result from loading a dataset."""
    X: pd.DataFrame
    y: np.ndarray
    sensitive: Dict[str, np.ndarray]
    source: str
    metadata: Dict


def _binarize_age(age_series: pd.Series, threshold: int = 25) -> np.ndarray:
    """Binarize age into young (0) vs old (1)."""
    return (age_series >= threshold).astype(int).values


def load_german_credit(
    sensitive_attrs: List[str],
    drop_sensitive: bool = True,
    **kwargs
) -> DatasetResult:
    """
    Load German Credit dataset from OpenML.

    Target: class='bad' -> y=1 (default)
    Sensitive: sex (from personal_status), age_group
    """
    if not OPENML_AVAILABLE:
        raise ImportError("openml required for german_credit")

    logger.info("Loading german_credit from OpenML...")
    dataset = openml.datasets.get_dataset(31)  # credit-g
    X, y, _, _ = dataset.get_data(target=dataset.default_target_attribute)

    # Convert to DataFrame
    df = X.copy()

    # Extract sensitive attributes
    sens = {}

    # Sex from personal_status
    if 'sex' in sensitive_attrs:
        if 'personal_status' in df.columns:
            # OpenML values: 'male single', 'female div/dep/mar', 'male div/sep', 'male mar/wid'
            # Check for 'female' first since 'female' contains 'male' as substring
            sens['sex'] = df['personal_status'].astype(str).apply(
                lambda x: 0 if 'female' in x.lower() else 1  # 0=female, 1=male
            ).values
            logger.info(f"German Credit sex distribution: {np.bincount(sens['sex'])}")

    # Age group
    if 'age_group' in sensitive_attrs:
        if 'age' in df.columns:
            sens['age_group'] = _binarize_age(df['age'], 25)

    # Drop sensitive from features if requested
    if drop_sensitive:
        drop_cols = ['personal_status', 'age'] if 'sex' in sensitive_attrs else []
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    # Encode categoricals
    for col in df.select_dtypes(include=['object', 'category']).columns:
        df[col] = LabelEncoder().fit_transform(df[col].astype(str))

    # Target: 'bad' = 1, 'good' = 0
    y_binary = (y == 'bad').astype(int).values

    return DatasetResult(
        X=df,
        y=y_binary,
        sensitive=sens,
        source='openml:31',
        metadata={'n_samples': len(y_binary), 'base_rate': y_binary.mean()}
    )


def load_taiwan_credit(
    sensitive_attrs: List[str],
    drop_sensitive: bool = True,
    **kwargs
) -> DatasetResult:
    """
    Load Taiwan Credit dataset from OpenML.

    Target: default=1
    Sensitive: SEX, EDUCATION, MARRIAGE

    Note: OpenML dataset 42477 uses x1-x23 column names:
    x1=LIMIT_BAL, x2=SEX, x3=EDUCATION, x4=MARRIAGE, x5=AGE,
    x6-x11=PAY, x12-x17=BILL_AMT, x18-x23=PAY_AMT
    """
    if not OPENML_AVAILABLE:
        raise ImportError("openml required for taiwan_credit")

    logger.info("Loading taiwan_credit from OpenML...")
    dataset = openml.datasets.get_dataset(42477)
    X, y, _, _ = dataset.get_data(target=dataset.default_target_attribute)

    df = X.copy()

    # Rename columns to meaningful names if they're x1, x2, etc
    if 'x1' in df.columns:
        col_map = {
            'x1': 'LIMIT_BAL', 'x2': 'SEX', 'x3': 'EDUCATION', 'x4': 'MARRIAGE',
            'x5': 'AGE', 'x6': 'PAY_0', 'x7': 'PAY_2', 'x8': 'PAY_3',
            'x9': 'PAY_4', 'x10': 'PAY_5', 'x11': 'PAY_6',
            'x12': 'BILL_AMT1', 'x13': 'BILL_AMT2', 'x14': 'BILL_AMT3',
            'x15': 'BILL_AMT4', 'x16': 'BILL_AMT5', 'x17': 'BILL_AMT6',
            'x18': 'PAY_AMT1', 'x19': 'PAY_AMT2', 'x20': 'PAY_AMT3',
            'x21': 'PAY_AMT4', 'x22': 'PAY_AMT5', 'x23': 'PAY_AMT6'
        }
        df = df.rename(columns=col_map)

    sens = {}

    # SEX: 1=male, 2=female -> 0=female, 1=male (standard: 1=disadvantaged)
    if 'sex' in sensitive_attrs and 'SEX' in df.columns:
        sens['sex'] = (df['SEX'] == 1).astype(int).values  # 1=male
        logger.info(f"Taiwan Credit sex distribution: {np.bincount(sens['sex'])}")

    # EDUCATION: 1=grad, 2=university, 3=high school, 4+=other
    if 'education' in sensitive_attrs and 'EDUCATION' in df.columns:
        # Higher education (1,2) vs lower (3+) -> 0=higher, 1=lower
        sens['education'] = (df['EDUCATION'] > 2).astype(int).values
        logger.info(f"Taiwan Credit education distribution: {np.bincount(sens['education'])}")

    # MARRIAGE: 1=married, 2=single, 3=other
    if 'marriage' in sensitive_attrs and 'MARRIAGE' in df.columns:
        sens['marriage'] = (df['MARRIAGE'] == 1).astype(int).values

    # Drop sensitive columns
    if drop_sensitive:
        drop_cols = ['SEX', 'EDUCATION', 'MARRIAGE']
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    # Encode remaining categoricals
    for col in df.select_dtypes(include=['object', 'category']).columns:
        df[col] = LabelEncoder().fit_transform(df[col].astype(str))

    y_binary = y.astype(int).values

    return DatasetResult(
        X=df,
        y=y_binary,
        sensitive=sens,
        source='openml:42477',
        metadata={'n_samples': len(y_binary), 'base_rate': y_binary.mean()}
    )


def load_adult(
    sensitive_attrs: List[str],
    drop_sensitive: bool = True,
    max_samples: Optional[int] = None,
    **kwargs
) -> DatasetResult:
    """
    Load Adult Census Income dataset.

    Target: income>50K -> y=1
    Sensitive: sex, race, sex_race (intersection)
    """
    logger.info("Loading adult dataset...")

    if FAIRLEARN_AVAILABLE:
        data = fetch_adult(as_frame=True)
        df = data.data
        y = data.target
    elif OPENML_AVAILABLE:
        dataset = openml.datasets.get_dataset(179)  # adult
        X, y, _, _ = dataset.get_data(target=dataset.default_target_attribute)
        df = X.copy()
    else:
        raise ImportError("fairlearn or openml required for adult dataset")

    # Subsample if needed
    if max_samples and len(df) > max_samples:
        idx = np.random.choice(len(df), max_samples, replace=False)
        df = df.iloc[idx].reset_index(drop=True)
        y = y.iloc[idx].reset_index(drop=True) if hasattr(y, 'iloc') else y[idx]

    sens = {}

    # Sex
    if 'sex' in sensitive_attrs:
        sex_col = 'sex' if 'sex' in df.columns else 'Sex'
        if sex_col in df.columns:
            sens['sex'] = (df[sex_col].astype(str).str.lower().str.contains('male') &
                          ~df[sex_col].astype(str).str.lower().str.contains('female')).astype(int).values

    # Race: White vs Non-White
    if 'race' in sensitive_attrs:
        race_col = 'race' if 'race' in df.columns else 'Race'
        if race_col in df.columns:
            sens['race'] = (df[race_col].astype(str).str.lower().str.contains('white') &
                          ~df[race_col].astype(str).str.lower().str.contains('non')).astype(int).values

    # Intersection
    if 'sex_race' in sensitive_attrs and 'sex' in sens and 'race' in sens:
        # 0=female_nonwhite, 1=female_white, 2=male_nonwhite, 3=male_white
        sens['sex_race'] = sens['sex'] * 2 + sens['race']

    # Drop sensitive
    if drop_sensitive:
        drop_cols = ['sex', 'Sex', 'race', 'Race']
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    # Encode categoricals
    for col in df.select_dtypes(include=['object', 'category']).columns:
        df[col] = LabelEncoder().fit_transform(df[col].astype(str))

    # Target
    if hasattr(y, 'values'):
        y_vals = y.values
    else:
        y_vals = np.array(y)

    if y_vals.dtype == object or str(y_vals.dtype) == 'category':
        y_binary = (pd.Series(y_vals).astype(str).str.contains('>50K')).astype(int).values
    else:
        y_binary = y_vals.astype(int)

    return DatasetResult(
        X=df,
        y=y_binary,
        sensitive=sens,
        source='fairlearn/openml',
        metadata={'n_samples': len(y_binary), 'base_rate': y_binary.mean()}
    )


def load_acs_income(
    sensitive_attrs: List[str],
    drop_sensitive: bool = True,
    max_samples: Optional[int] = None,
    year: int = 2018,
    states: Optional[List[str]] = None,
    **kwargs
) -> DatasetResult:
    """
    Load ACS Income dataset from folktables.

    Target: income>threshold -> y=1
    Sensitive: SEX, RAC1P_binary, SEX_RAC1P
    """
    if not FOLKTABLES_AVAILABLE:
        raise ImportError("folktables required for acs_income")

    states = states or ['CA', 'TX', 'NY', 'FL', 'PA', 'IL']
    logger.info(f"Loading acs_income for states={states}, year={year}...")

    data_source = ACSDataSource(survey_year=str(year), horizon='1-Year', survey='person')

    all_data = []
    for state in states:
        try:
            acs_data = data_source.get_data(states=[state], download=True)
            features, labels, _ = ACSIncome.df_to_numpy(acs_data)
            feature_names = ACSIncome.features
            df_state = pd.DataFrame(features, columns=feature_names)
            df_state['_target'] = labels
            all_data.append(df_state)
        except Exception as e:
            logger.warning(f"Failed to load ACS data for {state}: {e}")

    if not all_data:
        raise ValueError("No ACS data loaded")

    df = pd.concat(all_data, ignore_index=True)
    y = df.pop('_target').values

    # Subsample
    if max_samples and len(df) > max_samples:
        idx = np.random.choice(len(df), max_samples, replace=False)
        df = df.iloc[idx].reset_index(drop=True)
        y = y[idx]

    sens = {}

    # SEX: 1=Male, 2=Female -> 0=Male, 1=Female
    if 'SEX' in sensitive_attrs and 'SEX' in df.columns:
        sens['SEX'] = (df['SEX'] == 2).astype(int).values

    # RAC1P: 1=White alone -> binary
    if 'RAC1P_binary' in sensitive_attrs and 'RAC1P' in df.columns:
        sens['RAC1P_binary'] = (df['RAC1P'] == 1).astype(int).values

    # Intersection
    if 'SEX_RAC1P' in sensitive_attrs and 'SEX' in sens and 'RAC1P_binary' in sens:
        sens['SEX_RAC1P'] = sens['SEX'] * 2 + sens['RAC1P_binary']

    # Drop sensitive
    if drop_sensitive:
        drop_cols = ['SEX', 'RAC1P']
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    return DatasetResult(
        X=df,
        y=y.astype(int),
        sensitive=sens,
        source=f'folktables:acs_income:{year}',
        metadata={'n_samples': len(y), 'base_rate': y.mean(), 'states': states}
    )


def load_bank_marketing(
    sensitive_attrs: List[str],
    drop_sensitive: bool = True,
    **kwargs
) -> DatasetResult:
    """
    Load Bank Marketing dataset from OpenML.

    Target: y='yes' -> y=1
    Sensitive: age_group, marital
    """
    if not OPENML_AVAILABLE:
        raise ImportError("openml required for bank_marketing")

    logger.info("Loading bank_marketing from OpenML...")
    dataset = openml.datasets.get_dataset(1461)  # bank-marketing
    X, y, _, _ = dataset.get_data(target=dataset.default_target_attribute)

    df = X.copy()
    sens = {}

    # OpenML Bank Marketing may use V1, V2, ... column names
    # Map to proper column names based on position
    column_mapping = {
        'V1': 'age', 'V2': 'job', 'V3': 'marital', 'V4': 'education',
        'V5': 'default', 'V6': 'balance', 'V7': 'housing', 'V8': 'loan',
        'V9': 'contact', 'V10': 'day', 'V11': 'month', 'V12': 'duration',
        'V13': 'campaign', 'V14': 'pdays', 'V15': 'previous', 'V16': 'poutcome'
    }
    if 'V1' in df.columns and 'age' not in df.columns:
        df = df.rename(columns=column_mapping)

    # Age group
    if 'age_group' in sensitive_attrs and 'age' in df.columns:
        sens['age_group'] = _binarize_age(df['age'], 35)

    # Marital status
    if 'marital' in sensitive_attrs and 'marital' in df.columns:
        sens['marital'] = (df['marital'] == 'married').astype(int).values

    # Drop sensitive
    if drop_sensitive:
        drop_cols = ['age', 'marital']
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    # Encode categoricals
    for col in df.select_dtypes(include=['object', 'category']).columns:
        df[col] = LabelEncoder().fit_transform(df[col].astype(str))

    # Target - OpenML uses '1'=no, '2'=yes (subscribed to term deposit)
    y_arr = np.array(y).astype(str)  # Ensure string type
    y_binary = (y_arr == '2').astype(int)  # '2' means subscribed

    return DatasetResult(
        X=df,
        y=y_binary,
        sensitive=sens,
        source='openml:1461',
        metadata={'n_samples': len(y_binary), 'base_rate': y_binary.mean()}
    )


def load_home_credit(
    sensitive_attrs: List[str],
    drop_sensitive: bool = True,
    max_samples: Optional[int] = None,
    **kwargs
) -> DatasetResult:
    """
    Load Home Credit dataset from local file.

    Target: TARGET=1
    Sensitive: CODE_GENDER, age_group
    """
    data_path = DATA_RAW / "home_credit" / "application_train.csv"

    if not data_path.exists():
        raise FileNotFoundError(
            f"Home Credit data not found at {data_path}. "
            "Download from: https://www.kaggle.com/c/home-credit-default-risk/data"
        )

    logger.info(f"Loading home_credit from {data_path}...")
    df = pd.read_csv(data_path)

    y = df.pop('TARGET').values
    df = df.drop('SK_ID_CURR', axis=1, errors='ignore')

    # Subsample
    if max_samples and len(df) > max_samples:
        idx = np.random.choice(len(df), max_samples, replace=False)
        df = df.iloc[idx].reset_index(drop=True)
        y = y[idx]

    sens = {}

    # Gender
    if 'CODE_GENDER' in sensitive_attrs and 'CODE_GENDER' in df.columns:
        sens['CODE_GENDER'] = (df['CODE_GENDER'] == 'M').astype(int).values

    # Age from DAYS_BIRTH
    if 'age_group' in sensitive_attrs and 'DAYS_BIRTH' in df.columns:
        age = -df['DAYS_BIRTH'] / 365.25
        sens['age_group'] = (age >= 35).astype(int).values

    # Drop sensitive
    if drop_sensitive:
        drop_cols = ['CODE_GENDER', 'DAYS_BIRTH']
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    # Handle missing values and encode
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = LabelEncoder().fit_transform(df[col].fillna('missing').astype(str))

    # Fill numeric NaN
    df = df.fillna(df.median(numeric_only=True))

    return DatasetResult(
        X=df,
        y=y.astype(int),
        sensitive=sens,
        source='kaggle:home_credit',
        metadata={'n_samples': len(y), 'base_rate': y.mean()}
    )


# Import COMPAS from datasets module
try:
    from cpfi.datasets.compas import load_compas as _load_compas_raw
    COMPAS_AVAILABLE = True
except ImportError:
    COMPAS_AVAILABLE = False
    logger.warning("COMPAS dataset module not available")


def load_compas(
    sensitive_attrs: List[str],
    drop_sensitive: bool = True,
    binary_race: bool = True,
    **kwargs
) -> DatasetResult:
    """
    Load COMPAS dataset from ProPublica.

    Target: 2-year recidivism (1 = recidivated)
    Sensitive: race (African-American vs Caucasian), sex
    """
    if not COMPAS_AVAILABLE:
        raise ImportError("COMPAS dataset module not available")

    logger.info("Loading COMPAS dataset...")

    X, y, sens_df = _load_compas_raw(
        data_dir=DATA_RAW,
        sensitive_attrs=sensitive_attrs,
        drop_sensitive_from_features=drop_sensitive,
        binary_race=binary_race
    )

    # Convert sensitive DataFrame to dict of arrays
    sens = {}
    if 'race' in sensitive_attrs and 'race' in sens_df.columns:
        # Binary: 1 = African-American, 0 = Caucasian
        sens['race'] = (sens_df['race'] == 'African-American').astype(int).values

    if 'sex' in sensitive_attrs and 'sex' in sens_df.columns:
        # Binary: 1 = Male, 0 = Female
        sens['sex'] = (sens_df['sex'] == 'Male').astype(int).values

    return DatasetResult(
        X=X,
        y=y,
        sensitive=sens,
        source='propublica:compas',
        metadata={
            'n_samples': len(y),
            'base_rate': y.mean(),
            'binary_race': binary_race
        }
    )


# Registry
AVAILABLE_DATASETS = {
    'german_credit': load_german_credit,
    'taiwan_credit': load_taiwan_credit,
    'adult': load_adult,
    'acs_income': load_acs_income,
    'bank_marketing': load_bank_marketing,
    'home_credit': load_home_credit,
    'compas': load_compas
}


def load_dataset(
    name: str,
    sensitive_attrs: List[str],
    drop_sensitive: bool = True,
    **kwargs
) -> DatasetResult:
    """
    Load a dataset by name.

    Args:
        name: Dataset name
        sensitive_attrs: List of sensitive attribute names
        drop_sensitive: Whether to drop sensitive attrs from features
        **kwargs: Additional arguments for specific loaders

    Returns:
        DatasetResult with X, y, sensitive dict, source, metadata
    """
    if name not in AVAILABLE_DATASETS:
        raise ValueError(f"Unknown dataset: {name}. Available: {list(AVAILABLE_DATASETS.keys())}")

    return AVAILABLE_DATASETS[name](
        sensitive_attrs=sensitive_attrs,
        drop_sensitive=drop_sensitive,
        **kwargs
    )
