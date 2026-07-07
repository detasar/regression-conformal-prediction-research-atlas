"""
COMPAS Dataset Loader

The COMPAS (Correctional Offender Management Profiling for Alternative Sanctions)
dataset from ProPublica's investigation on algorithmic bias in criminal justice.

Target: 2-year recidivism (binary)
Sensitive: race (African-American, Caucasian), sex
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)

# ProPublica COMPAS data URL
COMPAS_URL = "https://raw.githubusercontent.com/propublica/compas-analysis/master/compas-scores-two-years.csv"


def load_compas(
    data_dir: Optional[Path] = None,
    sensitive_attrs: List[str] = ['race', 'sex'],
    drop_sensitive_from_features: bool = True,
    binary_race: bool = True,
    random_state: int = 42
) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    """
    Load and preprocess the COMPAS dataset.

    Parameters
    ----------
    data_dir : Path, optional
        Directory to cache the data
    sensitive_attrs : list
        Sensitive attributes to extract
    drop_sensitive_from_features : bool
        Whether to remove sensitive attrs from features
    binary_race : bool
        If True, keep only African-American and Caucasian
    random_state : int
        Random state for reproducibility

    Returns
    -------
    X : pd.DataFrame
        Features
    y : np.ndarray
        Binary target (1 = recidivated within 2 years)
    sensitive : pd.DataFrame
        Sensitive attributes
    """
    logger.info("Loading COMPAS dataset...")

    # Try to load from cache first
    if data_dir is not None:
        cache_path = Path(data_dir) / "compas" / "compas_processed.parquet"
        if cache_path.exists():
            logger.info(f"Loading from cache: {cache_path}")
            df = pd.read_parquet(cache_path)
        else:
            df = _download_and_process(cache_path)
    else:
        df = _download_and_process(None)

    # Filter to binary race if requested
    if binary_race:
        df = df[df['race'].isin(['African-American', 'Caucasian'])].copy()
        logger.info(f"Filtered to binary race: {len(df)} samples")

    # Define target
    y = df['two_year_recid'].values

    # Extract sensitive attributes
    sensitive = df[sensitive_attrs].copy()

    # Create combined sensitive attribute for intersectionality
    if 'race' in sensitive_attrs and 'sex' in sensitive_attrs:
        sensitive['race_sex'] = sensitive['race'] + '_' + sensitive['sex']

    # Define feature columns (exclude target and sensitive if requested)
    exclude_cols = ['two_year_recid', 'is_recid', 'decile_score', 'score_text']
    if drop_sensitive_from_features:
        exclude_cols.extend(sensitive_attrs)
        exclude_cols.extend(['race_sex'])  # Also drop combined

    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols].copy()

    # Convert categoricals to numeric
    for col in X.select_dtypes(include=['object', 'category']).columns:
        X[col] = pd.Categorical(X[col]).codes

    logger.info(f"COMPAS loaded: {len(X)} samples, {len(X.columns)} features")
    logger.info(f"Target balance: {y.mean():.3f} positive rate")
    logger.info(f"Sensitive attrs: {list(sensitive.columns)}")

    return X, y, sensitive


def _download_and_process(cache_path: Optional[Path]) -> pd.DataFrame:
    """Download and preprocess raw COMPAS data."""
    logger.info(f"Downloading COMPAS from {COMPAS_URL}")

    df_raw = pd.read_csv(COMPAS_URL)

    # Apply ProPublica's filtering criteria
    df = df_raw[
        (df_raw['days_b_screening_arrest'] <= 30) &
        (df_raw['days_b_screening_arrest'] >= -30) &
        (df_raw['is_recid'] != -1) &
        (df_raw['c_charge_degree'] != 'O') &
        (df_raw['score_text'] != 'N/A')
    ].copy()

    # Select relevant columns
    cols_to_keep = [
        'age', 'sex', 'race',
        'juv_fel_count', 'juv_misd_count', 'juv_other_count',
        'priors_count', 'c_charge_degree',
        'two_year_recid', 'is_recid',
        'decile_score', 'score_text'
    ]
    df = df[cols_to_keep].copy()

    # Clean up
    df = df.dropna()

    # Create age groups for additional sensitive attribute
    df['age_group'] = pd.cut(
        df['age'],
        bins=[0, 25, 35, 45, 100],
        labels=['<25', '25-35', '35-45', '45+']
    )

    # Cache if path provided
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_path)
        logger.info(f"Cached to {cache_path}")

    return df


if __name__ == "__main__":
    # Test loading
    logging.basicConfig(level=logging.INFO)
    X, y, sensitive = load_compas()
    print(f"\nX shape: {X.shape}")
    print(f"y shape: {y.shape}")
    print(f"sensitive:\n{sensitive.value_counts()}")
