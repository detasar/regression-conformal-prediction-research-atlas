"""
Preprocessing pipeline for CPFI experiments.

CRITICAL: All transformations are fit ONLY on train_idx to prevent data leakage.
Apply transformations to calib/cp/test splits without refitting.

Pipeline steps:
1. Identify column types (numeric vs categorical)
2. Drop high-missing columns (>95% missing in train)
3. Drop constant columns (<=1 unique value in train)
4. Impute missing values (median for numeric, mode for categorical)
5. Outlier capping (winsorization based on train quantiles)
6. Scaling (StandardScaler fit on train)
7. Categorical encoding (OneHotEncoder fit on train)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from loguru import logger

from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
import warnings


@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing pipeline."""
    # Feature filtering
    drop_high_missing: bool = True
    missing_threshold: float = 0.95
    drop_constant: bool = True

    # Imputation
    numeric_impute_strategy: str = 'median'
    categorical_impute_strategy: str = 'most_frequent'

    # Outlier handling
    outlier_capping: bool = True
    lower_quantile: float = 0.01
    upper_quantile: float = 0.99

    # Scaling
    scaling: bool = True
    scaling_method: str = 'standard'


@dataclass
class FittedPreprocessor:
    """Fitted preprocessing pipeline - stores all fitted transformers."""
    config: PreprocessingConfig

    # Column tracking
    numeric_cols: List[str] = field(default_factory=list)
    categorical_cols: List[str] = field(default_factory=list)
    cols_to_drop: List[str] = field(default_factory=list)

    # Fitted transformers
    num_imputer: Optional[SimpleImputer] = None
    cat_imputer: Optional[SimpleImputer] = None
    outlier_caps: Optional[Dict[str, Dict[str, float]]] = None
    scaler: Optional[StandardScaler] = None
    encoder: Optional[OneHotEncoder] = None
    label_encoders: Optional[Dict[str, LabelEncoder]] = None

    # Feature names after encoding
    final_feature_names: List[str] = field(default_factory=list)


def identify_column_types(X: pd.DataFrame) -> Tuple[List[str], List[str]]:
    """
    Identify numeric and categorical columns.

    Returns:
        Tuple of (numeric_cols, categorical_cols)
    """
    numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = X.select_dtypes(include=['object', 'category']).columns.tolist()

    # Also check for low-cardinality integers that should be categorical
    for col in numeric_cols.copy():
        if X[col].nunique() <= 10 and X[col].dtype in ['int64', 'int32']:
            # Could be categorical, but leave as numeric for tree models
            pass

    return numeric_cols, categorical_cols


def identify_bad_columns(
    X_train: pd.DataFrame,
    missing_thresh: float = 0.95
) -> List[str]:
    """
    Identify columns to drop based on train set.

    Args:
        X_train: Training data
        missing_thresh: Drop columns with missing rate > this threshold

    Returns:
        List of column names to drop
    """
    cols_to_drop = []

    # High missing rate
    missing_rate = X_train.isnull().mean()
    high_missing = missing_rate[missing_rate > missing_thresh].index.tolist()
    cols_to_drop.extend(high_missing)

    # Constant columns (<=1 unique value)
    for col in X_train.columns:
        n_unique = X_train[col].nunique(dropna=True)
        if n_unique <= 1:
            if col not in cols_to_drop:
                cols_to_drop.append(col)

    if cols_to_drop:
        logger.info(f"Dropping {len(cols_to_drop)} bad columns: {cols_to_drop[:5]}...")

    return cols_to_drop


def fit_outlier_caps(
    X_train: pd.DataFrame,
    numeric_cols: List[str],
    lower_q: float = 0.01,
    upper_q: float = 0.99
) -> Dict[str, Dict[str, float]]:
    """
    Compute outlier caps from train set only.

    Args:
        X_train: Training data
        numeric_cols: List of numeric column names
        lower_q: Lower quantile for capping
        upper_q: Upper quantile for capping

    Returns:
        Dictionary mapping column name to {'lower': val, 'upper': val}
    """
    caps = {}
    for col in numeric_cols:
        if col in X_train.columns:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                lower = X_train[col].quantile(lower_q)
                upper = X_train[col].quantile(upper_q)

                # Only cap if there's a meaningful range
                if pd.notna(lower) and pd.notna(upper) and lower < upper:
                    caps[col] = {'lower': lower, 'upper': upper}

    return caps


def apply_outlier_caps(
    X: pd.DataFrame,
    caps: Dict[str, Dict[str, float]]
) -> pd.DataFrame:
    """
    Apply outlier caps to any split.

    Args:
        X: Data to transform
        caps: Dictionary from fit_outlier_caps

    Returns:
        Transformed DataFrame
    """
    X = X.copy()
    for col, bounds in caps.items():
        if col in X.columns:
            X[col] = X[col].clip(bounds['lower'], bounds['upper'])
    return X


def fit_preprocessing(
    X_train: pd.DataFrame,
    config: Optional[PreprocessingConfig] = None
) -> FittedPreprocessor:
    """
    Fit preprocessing pipeline on training data.

    CRITICAL: Only call this on train_idx data!

    Args:
        X_train: Training features (DataFrame)
        config: Preprocessing configuration

    Returns:
        FittedPreprocessor with all fitted transformers
    """
    if config is None:
        config = PreprocessingConfig()

    X = X_train.copy()

    # Initialize preprocessor
    preprocessor = FittedPreprocessor(config=config)

    # Step 1: Identify column types
    numeric_cols, categorical_cols = identify_column_types(X)

    # Step 2: Identify bad columns (fit on train)
    if config.drop_high_missing or config.drop_constant:
        cols_to_drop = identify_bad_columns(X, config.missing_threshold)
        preprocessor.cols_to_drop = cols_to_drop

        # Update column lists
        numeric_cols = [c for c in numeric_cols if c not in cols_to_drop]
        categorical_cols = [c for c in categorical_cols if c not in cols_to_drop]

    preprocessor.numeric_cols = numeric_cols
    preprocessor.categorical_cols = categorical_cols

    # Drop bad columns for fitting
    X = X.drop(columns=preprocessor.cols_to_drop, errors='ignore')

    # Step 3: Fit imputers
    if numeric_cols:
        num_cols_present = [c for c in numeric_cols if c in X.columns]
        if num_cols_present:
            preprocessor.num_imputer = SimpleImputer(strategy=config.numeric_impute_strategy)
            preprocessor.num_imputer.fit(X[num_cols_present])

    if categorical_cols:
        cat_cols_present = [c for c in categorical_cols if c in X.columns]
        if cat_cols_present:
            preprocessor.cat_imputer = SimpleImputer(
                strategy=config.categorical_impute_strategy,
                fill_value='missing'
            )
            preprocessor.cat_imputer.fit(X[cat_cols_present].astype(str))

    # Step 4: Fit outlier caps (on train only)
    if config.outlier_capping and numeric_cols:
        num_cols_present = [c for c in numeric_cols if c in X.columns]
        preprocessor.outlier_caps = fit_outlier_caps(
            X, num_cols_present, config.lower_quantile, config.upper_quantile
        )

    # Step 5: Fit scaler
    if config.scaling and numeric_cols:
        num_cols_present = [c for c in numeric_cols if c in X.columns]
        if num_cols_present:
            # Impute first, then fit scaler
            X_num = X[num_cols_present].copy()
            if preprocessor.num_imputer is not None:
                X_num = pd.DataFrame(
                    preprocessor.num_imputer.transform(X_num),
                    columns=num_cols_present,
                    index=X.index
                )
            # Apply outlier caps before fitting scaler
            if preprocessor.outlier_caps:
                X_num = apply_outlier_caps(X_num, preprocessor.outlier_caps)

            preprocessor.scaler = StandardScaler()
            preprocessor.scaler.fit(X_num)

    # Step 6: Fit label encoders for categorical columns
    # (We use LabelEncoder for tree models instead of OneHotEncoder for efficiency)
    if categorical_cols:
        cat_cols_present = [c for c in categorical_cols if c in X.columns]
        if cat_cols_present:
            preprocessor.label_encoders = {}
            for col in cat_cols_present:
                le = LabelEncoder()
                # Fit on string representation, handle unseen values
                values = X[col].astype('object').where(X[col].notna(), 'missing').astype(str).values
                le.fit(values)
                preprocessor.label_encoders[col] = le

    # Store final feature names
    final_cols = [c for c in numeric_cols if c in X.columns]
    final_cols.extend([c for c in categorical_cols if c in X.columns])
    preprocessor.final_feature_names = final_cols

    logger.info(f"Fitted preprocessor: {len(numeric_cols)} numeric, {len(categorical_cols)} categorical, {len(preprocessor.cols_to_drop)} dropped")

    return preprocessor


def apply_preprocessing(
    X: pd.DataFrame,
    preprocessor: FittedPreprocessor
) -> pd.DataFrame:
    """
    Apply fitted preprocessing to any split.

    Args:
        X: Data to transform
        preprocessor: Fitted preprocessor from fit_preprocessing

    Returns:
        Transformed DataFrame
    """
    X = X.copy()

    # Step 1: Drop bad columns
    X = X.drop(columns=preprocessor.cols_to_drop, errors='ignore')

    # Step 2: Impute missing values
    num_cols = [c for c in preprocessor.numeric_cols if c in X.columns]
    cat_cols = [c for c in preprocessor.categorical_cols if c in X.columns]

    if num_cols and preprocessor.num_imputer is not None:
        X[num_cols] = preprocessor.num_imputer.transform(X[num_cols])

    if cat_cols and preprocessor.cat_imputer is not None:
        X[cat_cols] = preprocessor.cat_imputer.transform(X[cat_cols].astype(str))

    # Step 3: Apply outlier caps
    if preprocessor.outlier_caps:
        X = apply_outlier_caps(X, preprocessor.outlier_caps)

    # Step 4: Apply scaling
    if preprocessor.scaler is not None and num_cols:
        X[num_cols] = preprocessor.scaler.transform(X[num_cols])

    # Step 5: Apply label encoding for categorical
    if preprocessor.label_encoders:
        for col, le in preprocessor.label_encoders.items():
            if col in X.columns:
                values = X[col].astype('object').where(X[col].notna(), 'missing').astype(str).values
                # Handle unseen categories
                seen_classes = set(le.classes_)
                encoded = np.array([
                    le.transform([v])[0] if v in seen_classes else -1
                    for v in values
                ])
                X[col] = encoded

    return X


def preprocess_splits(
    X_train: pd.DataFrame,
    X_calib: pd.DataFrame,
    X_cp: pd.DataFrame,
    X_test: pd.DataFrame,
    config: Optional[PreprocessingConfig] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, FittedPreprocessor]:
    """
    Preprocess all splits in one call.

    Fits on train, applies to all splits.

    Args:
        X_train, X_calib, X_cp, X_test: DataFrames for each split
        config: Preprocessing configuration

    Returns:
        Tuple of (X_train, X_calib, X_cp, X_test, preprocessor)
    """
    # Fit on train
    preprocessor = fit_preprocessing(X_train, config)

    # Apply to all splits
    X_train = apply_preprocessing(X_train, preprocessor)
    X_calib = apply_preprocessing(X_calib, preprocessor)
    X_cp = apply_preprocessing(X_cp, preprocessor)
    X_test = apply_preprocessing(X_test, preprocessor)

    return X_train, X_calib, X_cp, X_test, preprocessor
