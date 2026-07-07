"""
HMDA (Home Mortgage Disclosure Act) Dataset Loader

Federal mortgage data from the Consumer Financial Protection Bureau (CFPB).
https://ffiec.cfpb.gov/data-publication/

Target: Loan approval (action_taken)
Sensitive: race, ethnicity, sex
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)

# HMDA data can be downloaded from CFPB
HMDA_URL_TEMPLATE = "https://ffiec.cfpb.gov/v2/data-browser-api/view/csv?years={year}&states=CA"


def load_hmda(
    data_dir: Path,
    sensitive_attrs: List[str] = ['derived_race', 'derived_sex'],
    drop_sensitive_from_features: bool = True,
    max_samples: Optional[int] = 100000,
    year: int = 2022,
    random_state: int = 42
) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    """
    Load and preprocess the HMDA dataset.

    Parameters
    ----------
    data_dir : Path
        Directory containing the dataset
    sensitive_attrs : list
        Sensitive attributes to extract
    drop_sensitive_from_features : bool
        Whether to remove sensitive attrs from features
    max_samples : int, optional
        Maximum samples to use
    year : int
        Year of data to use
    random_state : int
        Random state for reproducibility

    Returns
    -------
    X : pd.DataFrame
        Features
    y : np.ndarray
        Binary target (1 = loan approved/originated)
    sensitive : pd.DataFrame
        Sensitive attributes
    """
    logger.info(f"Loading HMDA dataset for year {year}...")

    data_path = Path(data_dir) / "hmda" / f"hmda_{year}.csv"

    if not data_path.exists():
        # Try to find any HMDA file
        hmda_dir = Path(data_dir) / "hmda"
        hmda_files = list(hmda_dir.glob("*.csv")) if hmda_dir.exists() else []

        if hmda_files:
            data_path = hmda_files[0]
            logger.info(f"Using found file: {data_path}")
        else:
            raise FileNotFoundError(
                f"HMDA dataset not found at {data_path}. "
                f"Download from: https://ffiec.cfpb.gov/data-publication/snapshot-national-loan-level-dataset/"
            )

    # Load with selected columns to reduce memory
    usecols = [
        'action_taken',
        'loan_amount',
        'loan_to_value_ratio',
        'interest_rate',
        'loan_term',
        'debt_to_income_ratio',
        'applicant_credit_score_type',
        'income',
        'property_value',
        'derived_race',
        'derived_sex',
        'derived_ethnicity',
        'applicant_age',
        'county_code',
        'tract_minority_population_percent',
        'tract_to_msa_income_percentage'
    ]

    try:
        df = pd.read_csv(data_path, usecols=usecols, low_memory=False)
    except ValueError:
        # If columns don't match, load all and select what's available
        df = pd.read_csv(data_path, low_memory=False)
        available = [c for c in usecols if c in df.columns]
        df = df[available]

    logger.info(f"Loaded {len(df)} rows")

    # Filter to clear outcomes (originated or denied)
    # action_taken: 1 = originated, 3 = denied
    df = df[df['action_taken'].isin([1, 3])].copy()
    logger.info(f"After filtering to originated/denied: {len(df)} rows")

    # Create binary target
    df['approved'] = (df['action_taken'] == 1).astype(int)

    # Clean race/ethnicity
    if 'derived_race' in df.columns:
        # Keep main categories
        main_races = ['White', 'Black or African American', 'Asian', 'Hispanic or Latino']
        df = df[df['derived_race'].isin(main_races)].copy()

    if 'derived_sex' in df.columns:
        df = df[df['derived_sex'].isin(['Male', 'Female'])].copy()

    logger.info(f"After filtering demographics: {len(df)} rows")

    # Subsample if needed
    if max_samples is not None and len(df) > max_samples:
        df = df.sample(n=max_samples, random_state=random_state)
        logger.info(f"Subsampled to {len(df)} rows")

    # Drop rows with missing critical values
    df = df.dropna(subset=['approved'])

    # Create age groups
    if 'applicant_age' in df.columns:
        df['age_group'] = df['applicant_age'].apply(_age_bucket)

    # Create race binary for simpler analysis
    if 'derived_race' in df.columns:
        df['race_binary'] = df['derived_race'].apply(
            lambda x: 'White' if x == 'White' else 'Non-White'
        )

    # Create intersectional attribute
    if 'derived_race' in df.columns and 'derived_sex' in df.columns:
        df['race_sex'] = df['derived_race'] + '_' + df['derived_sex']

    # Target
    y = df['approved'].values

    # Sensitive attributes
    sensitive_cols = [c for c in sensitive_attrs if c in df.columns]
    sensitive = df[sensitive_cols].copy()

    # Features
    exclude_cols = ['approved', 'action_taken']
    if drop_sensitive_from_features:
        exclude_cols.extend(sensitive_cols)
        exclude_cols.extend(['race_binary', 'race_sex', 'age_group'])

    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols].copy()

    # Handle missing values
    for col in X.select_dtypes(include=[np.number]).columns:
        X[col] = X[col].fillna(X[col].median())

    # Convert categoricals to numeric
    for col in X.select_dtypes(include=['object', 'category']).columns:
        X[col] = pd.Categorical(X[col]).codes

    logger.info(f"HMDA loaded: {len(X)} samples, {len(X.columns)} features")
    logger.info(f"Target balance: {y.mean():.3f} approval rate")
    logger.info(f"Sensitive attrs: {list(sensitive.columns)}")

    return X, y, sensitive


def _age_bucket(age):
    """Convert age string to bucket."""
    if pd.isna(age):
        return 'unknown'
    if isinstance(age, str):
        if '<25' in age or '25-34' in age:
            return 'young'
        elif '35-44' in age or '45-54' in age:
            return 'middle'
        elif '55-64' in age or '65-74' in age or '>74' in age:
            return 'senior'
    return 'unknown'


if __name__ == "__main__":
    # Test loading
    import os
    logging.basicConfig(level=logging.INFO)
    data_dir = Path(os.environ.get("CPFI_DATA_RAW", "./data/raw"))
    try:
        X, y, sensitive = load_hmda(data_dir)
        print(f"\nX shape: {X.shape}")
        print(f"y shape: {y.shape}")
        print(f"sensitive:\n{sensitive.value_counts()}")
    except FileNotFoundError as e:
        print(f"Dataset not found: {e}")
        print("Set CPFI_DATA_RAW environment variable to your data directory.")
