"""
Give Me Some Credit Dataset Loader

Kaggle competition dataset for credit scoring.
https://www.kaggle.com/c/GiveMeSomeCredit

Target: SeriousDlqin2yrs (binary - defaulted in 2 years)
Sensitive: age groups (derived from 'age' column)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)

# Kaggle dataset - needs to be downloaded manually or via kaggle API
KAGGLE_DATASET = "givemesomecredit"


def load_give_me_credit(
    data_dir: Path,
    sensitive_attrs: List[str] = ['age_group'],
    drop_sensitive_from_features: bool = True,
    max_samples: Optional[int] = None,
    random_state: int = 42
) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    """
    Load and preprocess the Give Me Some Credit dataset.

    Parameters
    ----------
    data_dir : Path
        Directory containing the dataset (cs-training.csv)
    sensitive_attrs : list
        Sensitive attributes to extract
    drop_sensitive_from_features : bool
        Whether to remove sensitive attrs from features
    max_samples : int, optional
        Maximum samples to use (for faster experiments)
    random_state : int
        Random state for reproducibility

    Returns
    -------
    X : pd.DataFrame
        Features
    y : np.ndarray
        Binary target (1 = serious delinquency in 2 years)
    sensitive : pd.DataFrame
        Sensitive attributes
    """
    logger.info("Loading Give Me Some Credit dataset...")

    data_path = Path(data_dir) / "give_me_credit" / "cs-training.csv"

    if not data_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {data_path}. "
            f"Download from: https://www.kaggle.com/c/GiveMeSomeCredit/data"
        )

    df = pd.read_csv(data_path)
    logger.info(f"Loaded {len(df)} rows")

    # Drop index column if present
    if 'Unnamed: 0' in df.columns:
        df = df.drop('Unnamed: 0', axis=1)

    # Handle missing values
    # MonthlyIncome and NumberOfDependents have missing values
    df['MonthlyIncome'] = df['MonthlyIncome'].fillna(df['MonthlyIncome'].median())
    df['NumberOfDependents'] = df['NumberOfDependents'].fillna(0)

    # Create age groups for sensitive attribute
    df['age_group'] = pd.cut(
        df['age'],
        bins=[0, 35, 55, 100],
        labels=['young_<35', 'middle_35-55', 'senior_>55']
    )

    # Additional groupings
    df['income_group'] = pd.cut(
        df['MonthlyIncome'],
        bins=[0, 3000, 6000, 10000, float('inf')],
        labels=['low', 'medium', 'high', 'very_high']
    )

    # Subsample if requested
    if max_samples is not None and len(df) > max_samples:
        df = df.sample(n=max_samples, random_state=random_state)
        logger.info(f"Subsampled to {len(df)} rows")

    # Target
    y = df['SeriousDlqin2yrs'].values

    # Sensitive attributes
    sensitive = df[sensitive_attrs].copy()

    # Features
    exclude_cols = ['SeriousDlqin2yrs']
    if drop_sensitive_from_features:
        exclude_cols.extend(sensitive_attrs)
        # Also exclude raw age if using age_group
        if 'age_group' in sensitive_attrs:
            exclude_cols.append('age')
        if 'income_group' in sensitive_attrs:
            exclude_cols.append('MonthlyIncome')

    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols].copy()

    # Convert categoricals to numeric
    for col in X.select_dtypes(include=['object', 'category']).columns:
        X[col] = pd.Categorical(X[col]).codes

    logger.info(f"Give Me Credit loaded: {len(X)} samples, {len(X.columns)} features")
    logger.info(f"Target balance: {y.mean():.3f} positive rate")
    logger.info(f"Sensitive attrs: {list(sensitive.columns)}")

    return X, y, sensitive


if __name__ == "__main__":
    # Test loading
    import os
    logging.basicConfig(level=logging.INFO)
    data_dir = Path(os.environ.get("CPFI_DATA_RAW", "./data/raw"))
    try:
        X, y, sensitive = load_give_me_credit(data_dir)
        print(f"\nX shape: {X.shape}")
        print(f"y shape: {y.shape}")
        print(f"sensitive:\n{sensitive.value_counts()}")
    except FileNotFoundError as e:
        print(f"Dataset not found: {e}")
        print("Set CPFI_DATA_RAW environment variable to your data directory.")
