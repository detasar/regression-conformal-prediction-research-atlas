"""
Preprocessing Variants for CPFI Session 4 Experiments.

Each variant is identified by a preproc_id and produces different feature
transformations and/or sample weights. Preprocessing changes affect model
training and probability distributions, making each variant a distinct
experimental arm.

LEAKAGE PREVENTION RULES (4-way split):
========================================
1. Imputer / Outlier caps / Encoder / Scaler / Feature selection → FIT ONLY ON train_idx
2. Probability calibration → FIT ONLY ON calib_idx
3. Conformal τ / Mondrian τg / ESS target → FIT ONLY ON cp_idx
4. test_idx → NEVER FIT ANYTHING

CACHE PATH STRUCTURE:
=====================
- 03_cache/splits/{dataset}/seed={seed}/split={split_id}/indices.npz  (shared)
- 03_cache/preds/{dataset}/{model}/{preproc_id}/seed={seed}/split={split_id}/probs.npz  (preproc-specific)

AVAILABLE PREPROCESSING VARIANTS:
=================================
- baseline: Standard preprocessing (impute median, scale, encode, outlier clip)
- no_outlier: Same as baseline but WITHOUT outlier capping
- knn_impute: KNN imputation instead of median (k=5)
- reweigh_aif360: AIF360 Reweighing algorithm for sample weights
- manual_reweigh: Manual sample weight computation (group×label frequency inverse)
- no_scale: No scaling (for tree models that don't need it)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, NamedTuple
from dataclasses import dataclass, field
from loguru import logger
import warnings

from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.preprocessing import StandardScaler, LabelEncoder


# =============================================================================
# PREPROCESSING VARIANT REGISTRY
# =============================================================================

# Standard preprocessing variants (no fairness intervention)
PREPROC_VARIANTS_STANDARD = [
    'baseline',      # Standard: impute median, outlier clip (percentile), scale, encode
    'no_outlier',    # No outlier capping
    'no_scale',      # No scaling (for tree models)
    'iqr_clip',      # IQR-based outlier clipping instead of percentile
]

# Imputation variants
PREPROC_VARIANTS_IMPUTE = [
    'knn_impute',    # KNN imputation (k=5)
]

# Fairness preprocessing variants (produce sample weights or transform features)
PREPROC_VARIANTS_FAIRNESS = [
    'manual_reweigh',    # Manual sample weight computation (group×label frequency)
    'reweigh_aif360',    # AIF360 Reweighing algorithm
    'corr_remove',       # CorrelationRemover (fairlearn) - removes correlation with sensitive
    'dir_aif360',        # DisparateImpactRemover (AIF360)
]

# All variants
PREPROC_VARIANTS = (
    PREPROC_VARIANTS_STANDARD +
    PREPROC_VARIANTS_IMPUTE +
    PREPROC_VARIANTS_FAIRNESS
)


@dataclass
class PreprocessingVariantConfig:
    """Configuration for a preprocessing variant."""
    preproc_id: str

    # Imputation
    impute_strategy: str = 'median'  # 'median', 'mean', 'knn'
    knn_neighbors: int = 5

    # Outlier handling
    outlier_capping: bool = True
    outlier_method: str = 'percentile'  # 'percentile', 'iqr', 'none'
    lower_quantile: float = 0.01
    upper_quantile: float = 0.99
    iqr_factor: float = 1.5  # For IQR-based clipping

    # Scaling
    scaling: bool = True

    # Fairness preprocessing
    fairness_reweighting: str = 'none'  # 'none', 'aif360', 'manual'
    fairness_transform: str = 'none'    # 'none', 'corr_remove', 'dir'
    corr_remove_alpha: float = 1.0      # 0=no removal, 1=full removal

    # Feature filtering
    drop_high_missing: bool = True
    missing_threshold: float = 0.95
    drop_constant: bool = True


def get_variant_config(preproc_id: str) -> PreprocessingVariantConfig:
    """Get configuration for a preprocessing variant."""

    configs = {
        # === STANDARD VARIANTS ===
        'baseline': PreprocessingVariantConfig(
            preproc_id='baseline',
            impute_strategy='median',
            outlier_capping=True,
            outlier_method='percentile',
            scaling=True,
            fairness_reweighting='none',
            fairness_transform='none'
        ),
        'no_outlier': PreprocessingVariantConfig(
            preproc_id='no_outlier',
            impute_strategy='median',
            outlier_capping=False,
            outlier_method='none',
            scaling=True,
            fairness_reweighting='none',
            fairness_transform='none'
        ),
        'no_scale': PreprocessingVariantConfig(
            preproc_id='no_scale',
            impute_strategy='median',
            outlier_capping=True,
            outlier_method='percentile',
            scaling=False,
            fairness_reweighting='none',
            fairness_transform='none'
        ),
        'iqr_clip': PreprocessingVariantConfig(
            preproc_id='iqr_clip',
            impute_strategy='median',
            outlier_capping=True,
            outlier_method='iqr',
            iqr_factor=1.5,
            scaling=True,
            fairness_reweighting='none',
            fairness_transform='none'
        ),

        # === IMPUTATION VARIANTS ===
        'knn_impute': PreprocessingVariantConfig(
            preproc_id='knn_impute',
            impute_strategy='knn',
            knn_neighbors=5,
            outlier_capping=True,
            outlier_method='percentile',
            scaling=True,
            fairness_reweighting='none',
            fairness_transform='none'
        ),

        # === FAIRNESS VARIANTS (Reweighting - produces sample_weights) ===
        'manual_reweigh': PreprocessingVariantConfig(
            preproc_id='manual_reweigh',
            impute_strategy='median',
            outlier_capping=True,
            outlier_method='percentile',
            scaling=True,
            fairness_reweighting='manual',
            fairness_transform='none'
        ),
        'reweigh_aif360': PreprocessingVariantConfig(
            preproc_id='reweigh_aif360',
            impute_strategy='median',
            outlier_capping=True,
            outlier_method='percentile',
            scaling=True,
            fairness_reweighting='aif360',
            fairness_transform='none'
        ),

        # === FAIRNESS VARIANTS (Feature Transform) ===
        'corr_remove': PreprocessingVariantConfig(
            preproc_id='corr_remove',
            impute_strategy='median',
            outlier_capping=True,
            outlier_method='percentile',
            scaling=True,
            fairness_reweighting='none',
            fairness_transform='corr_remove',
            corr_remove_alpha=1.0  # Full correlation removal
        ),
        'dir_aif360': PreprocessingVariantConfig(
            preproc_id='dir_aif360',
            impute_strategy='median',
            outlier_capping=True,
            outlier_method='percentile',
            scaling=True,
            fairness_reweighting='none',
            fairness_transform='dir'
        ),
    }

    if preproc_id not in configs:
        raise ValueError(f"Unknown preproc_id: {preproc_id}. Available: {list(configs.keys())}")

    return configs[preproc_id]


# =============================================================================
# PREPROCESSING RESULT
# =============================================================================

class PreprocessingResult(NamedTuple):
    """Result from preprocessing a dataset."""
    X_train: np.ndarray
    X_calib: np.ndarray
    X_cp: np.ndarray
    X_test: np.ndarray
    sample_weights_train: Optional[np.ndarray]  # For fairness reweighting
    feature_names: List[str]
    preproc_id: str
    metadata: Dict[str, Any]


@dataclass
class FittedVariantPreprocessor:
    """Stores all fitted transformers for a preprocessing variant."""
    config: PreprocessingVariantConfig

    # Column tracking
    numeric_cols: List[str] = field(default_factory=list)
    categorical_cols: List[str] = field(default_factory=list)
    cols_to_drop: List[str] = field(default_factory=list)

    # Fitted transformers
    num_imputer: Any = None  # SimpleImputer or KNNImputer
    cat_imputer: Optional[SimpleImputer] = None
    outlier_caps: Optional[Dict[str, Dict[str, float]]] = None
    scaler: Optional[StandardScaler] = None
    label_encoders: Optional[Dict[str, LabelEncoder]] = None

    # Fairness reweighting
    sample_weights: Optional[np.ndarray] = None
    reweighting_factors: Optional[Dict] = None

    # Fairness feature transforms
    correlation_remover: Any = None       # Fitted CorrelationRemover
    dir_repair_info: Optional[Dict] = None  # DisparateImpactRemover info

    # Feature names after encoding
    final_feature_names: List[str] = field(default_factory=list)


# =============================================================================
# CORE PREPROCESSING FUNCTIONS
# =============================================================================

def _identify_column_types(X: pd.DataFrame) -> Tuple[List[str], List[str]]:
    """Identify numeric and categorical columns."""
    numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = X.select_dtypes(include=['object', 'category']).columns.tolist()
    return numeric_cols, categorical_cols


def _identify_bad_columns(X_train: pd.DataFrame, missing_thresh: float = 0.95) -> List[str]:
    """Identify columns to drop based on train set."""
    cols_to_drop = []

    # High missing rate
    missing_rate = X_train.isnull().mean()
    high_missing = missing_rate[missing_rate > missing_thresh].index.tolist()
    cols_to_drop.extend(high_missing)

    # Constant columns
    for col in X_train.columns:
        n_unique = X_train[col].nunique(dropna=True)
        if n_unique <= 1 and col not in cols_to_drop:
            cols_to_drop.append(col)

    return cols_to_drop


def _fit_outlier_caps(
    X_train: pd.DataFrame,
    numeric_cols: List[str],
    method: str = 'percentile',
    lower_q: float = 0.01,
    upper_q: float = 0.99,
    iqr_factor: float = 1.5
) -> Dict[str, Dict[str, float]]:
    """
    Compute outlier caps from train set only.

    Args:
        X_train: Training data
        numeric_cols: Numeric column names
        method: 'percentile' or 'iqr'
        lower_q, upper_q: Quantiles for percentile method
        iqr_factor: IQR multiplier for IQR method (typically 1.5)

    Returns:
        Dict mapping column -> {'lower': val, 'upper': val}
    """
    caps = {}
    for col in numeric_cols:
        if col in X_train.columns:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                if method == 'iqr':
                    Q1 = X_train[col].quantile(0.25)
                    Q3 = X_train[col].quantile(0.75)
                    IQR = Q3 - Q1
                    lower = Q1 - iqr_factor * IQR
                    upper = Q3 + iqr_factor * IQR
                else:  # percentile
                    lower = X_train[col].quantile(lower_q)
                    upper = X_train[col].quantile(upper_q)

                if pd.notna(lower) and pd.notna(upper) and lower < upper:
                    caps[col] = {'lower': lower, 'upper': upper}
    return caps


def _apply_outlier_caps(X: pd.DataFrame, caps: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    """Apply outlier caps to any split."""
    X = X.copy()
    for col, bounds in caps.items():
        if col in X.columns:
            X[col] = X[col].clip(bounds['lower'], bounds['upper'])
    return X


# =============================================================================
# FAIRNESS REWEIGHTING
# =============================================================================

def compute_manual_sample_weights(
    y_train: np.ndarray,
    sensitive_train: np.ndarray
) -> Tuple[np.ndarray, Dict]:
    """
    Compute sample weights to balance group×label frequencies.

    This implements the same logic as AIF360 Reweighing but without the dependency.

    Weight formula: w(g,y) = P(Y=y) * P(G=g) / P(Y=y, G=g)

    Args:
        y_train: Binary labels (0/1)
        sensitive_train: Binary sensitive attribute (0/1)

    Returns:
        Tuple of (sample_weights array, weight_factors dict)
    """
    n = len(y_train)
    weights = np.ones(n)
    factors = {}

    # Compute marginal probabilities
    p_y0 = (y_train == 0).mean()
    p_y1 = (y_train == 1).mean()
    p_g0 = (sensitive_train == 0).mean()
    p_g1 = (sensitive_train == 1).mean()

    # Compute joint probabilities and weights for each (g, y) combination
    for g in [0, 1]:
        for y in [0, 1]:
            mask = (sensitive_train == g) & (y_train == y)
            p_gy = mask.mean()

            if p_gy > 0:
                # P(Y=y) * P(G=g) / P(Y=y, G=g)
                p_y = p_y1 if y == 1 else p_y0
                p_g = p_g1 if g == 1 else p_g0
                w = (p_y * p_g) / p_gy
                weights[mask] = w
                factors[(g, y)] = w
            else:
                factors[(g, y)] = 1.0

    # Normalize so mean weight = 1
    weights = weights / weights.mean()

    logger.info(f"Manual reweighting factors: {factors}")
    logger.info(f"Weight stats: min={weights.min():.3f}, max={weights.max():.3f}, mean={weights.mean():.3f}")

    return weights, factors


def compute_aif360_sample_weights(
    y_train: np.ndarray,
    sensitive_train: np.ndarray
) -> Tuple[np.ndarray, Dict]:
    """
    Compute sample weights using AIF360 Reweighing algorithm.

    Falls back to manual computation if AIF360 is not available.

    Args:
        y_train: Binary labels (0/1)
        sensitive_train: Binary sensitive attribute (0/1)

    Returns:
        Tuple of (sample_weights array, weight_factors dict)
    """
    try:
        from aif360.datasets import BinaryLabelDataset
        from aif360.algorithms.preprocessing import Reweighing

        # Create AIF360 dataset
        df = pd.DataFrame({
            'label': y_train,
            'sensitive': sensitive_train,
            'dummy': np.ones(len(y_train))  # AIF360 needs at least one feature
        })

        dataset = BinaryLabelDataset(
            df=df,
            label_names=['label'],
            protected_attribute_names=['sensitive'],
            favorable_label=1,
            unfavorable_label=0
        )

        # Apply Reweighing
        rw = Reweighing(
            unprivileged_groups=[{'sensitive': 0}],
            privileged_groups=[{'sensitive': 1}]
        )
        dataset_rw = rw.fit_transform(dataset)

        weights = dataset_rw.instance_weights

        # Compute weight factors for logging
        factors = {}
        for g in [0, 1]:
            for y in [0, 1]:
                mask = (sensitive_train == g) & (y_train == y)
                if mask.sum() > 0:
                    factors[(g, y)] = weights[mask][0]

        logger.info(f"AIF360 reweighting factors: {factors}")

        return weights, factors

    except ImportError:
        logger.warning("AIF360 not available, falling back to manual reweighting")
        return compute_manual_sample_weights(y_train, sensitive_train)


# =============================================================================
# FAIRNESS FEATURE TRANSFORMS
# =============================================================================

def apply_correlation_remover(
    X_train: np.ndarray,
    sensitive_train: np.ndarray,
    alpha: float = 1.0
) -> Tuple[np.ndarray, Any]:
    """
    Apply CorrelationRemover to remove correlation between features and sensitive attribute.

    IMPORTANT: Since we typically drop sensitive from X, we need to temporarily
    add it back for CorrelationRemover to work properly.

    Args:
        X_train: Training features (sensitive already dropped)
        sensitive_train: Sensitive attribute values
        alpha: Removal strength (0=none, 1=full)

    Returns:
        Tuple of (transformed X, fitted transformer for applying to other splits)
    """
    try:
        from fairlearn.preprocessing import CorrelationRemover

        # Add sensitive as first column (CorrelationRemover needs it)
        X_with_sens = np.column_stack([sensitive_train.reshape(-1, 1), X_train])

        # Fit and transform
        cr = CorrelationRemover(sensitive_feature_ids=[0], alpha=alpha)
        X_transformed = cr.fit_transform(X_with_sens)

        # CorrelationRemover outputs features without sensitive column
        # No need to slice - output shape is (n_samples, n_features)
        X_fair = X_transformed

        logger.info(f"CorrelationRemover applied with alpha={alpha}")

        return X_fair, cr

    except ImportError:
        logger.warning("fairlearn not available, skipping CorrelationRemover")
        return X_train, None
    except Exception as e:
        logger.warning(f"CorrelationRemover failed: {e}, returning original features")
        return X_train, None


def transform_correlation_remover(
    X: np.ndarray,
    sensitive: np.ndarray,
    fitted_cr: Any
) -> np.ndarray:
    """Apply fitted CorrelationRemover to new data."""
    if fitted_cr is None:
        return X

    try:
        X_with_sens = np.column_stack([sensitive.reshape(-1, 1), X])
        X_transformed = fitted_cr.transform(X_with_sens)
        # CorrelationRemover output already has sensitive column removed
        return X_transformed
    except Exception as e:
        logger.warning(f"CorrelationRemover transform failed: {e}")
        return X


def apply_disparate_impact_remover(
    X_train: np.ndarray,
    sensitive_train: np.ndarray,
    repair_level: float = 1.0
) -> Tuple[np.ndarray, Dict]:
    """
    Apply DisparateImpactRemover (AIF360) to transform features.

    This modifies the feature distributions to reduce disparate impact.

    Args:
        X_train: Training features
        sensitive_train: Sensitive attribute values
        repair_level: Repair strength (0=none, 1=full)

    Returns:
        Tuple of (transformed X, repair info dict for applying to other splits)
    """
    try:
        from aif360.datasets import BinaryLabelDataset
        from aif360.algorithms.preprocessing import DisparateImpactRemover

        # Create AIF360 dataset (needs labels, use dummy)
        n_features = X_train.shape[1]
        feature_names = [f'f{i}' for i in range(n_features)]

        df = pd.DataFrame(X_train, columns=feature_names)
        df['sensitive'] = sensitive_train
        df['label'] = 0  # Dummy label (DIR doesn't use it)

        dataset = BinaryLabelDataset(
            df=df,
            label_names=['label'],
            protected_attribute_names=['sensitive'],
            favorable_label=1,
            unfavorable_label=0
        )

        # Apply DIR
        dir_transformer = DisparateImpactRemover(repair_level=repair_level)
        dataset_transformed = dir_transformer.fit_transform(dataset)

        # Extract transformed features
        X_fair = dataset_transformed.features

        logger.info(f"DisparateImpactRemover applied with repair_level={repair_level}")

        # Store repair info for applying to other splits
        repair_info = {
            'repair_level': repair_level,
            'feature_names': feature_names,
            'dir_transformer': dir_transformer
        }

        return X_fair, repair_info

    except ImportError:
        logger.warning("AIF360 not available, skipping DisparateImpactRemover")
        return X_train, None
    except Exception as e:
        logger.warning(f"DisparateImpactRemover failed: {e}, returning original features")
        return X_train, None


def transform_disparate_impact_remover(
    X: np.ndarray,
    sensitive: np.ndarray,
    repair_info: Optional[Dict]
) -> np.ndarray:
    """Apply fitted DisparateImpactRemover to new data."""
    if repair_info is None:
        return X

    try:
        from aif360.datasets import BinaryLabelDataset

        feature_names = repair_info['feature_names']
        dir_transformer = repair_info['dir_transformer']

        df = pd.DataFrame(X, columns=feature_names)
        df['sensitive'] = sensitive
        df['label'] = 0

        dataset = BinaryLabelDataset(
            df=df,
            label_names=['label'],
            protected_attribute_names=['sensitive'],
            favorable_label=1,
            unfavorable_label=0
        )

        dataset_transformed = dir_transformer.transform(dataset)
        return dataset_transformed.features

    except Exception as e:
        logger.warning(f"DIR transform failed: {e}")
        return X


# =============================================================================
# MAIN PREPROCESSING FUNCTIONS
# =============================================================================

def fit_variant_preprocessing(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    sensitive_train: Optional[np.ndarray],
    config: PreprocessingVariantConfig
) -> FittedVariantPreprocessor:
    """
    Fit preprocessing pipeline on training data only.

    CRITICAL: This function must ONLY be called on train_idx data!

    Args:
        X_train: Training features (DataFrame)
        y_train: Training labels (for reweighting)
        sensitive_train: Training sensitive attribute (for reweighting)
        config: Preprocessing variant configuration

    Returns:
        FittedVariantPreprocessor with all fitted transformers
    """
    X = X_train.copy()
    preprocessor = FittedVariantPreprocessor(config=config)

    # Step 1: Identify column types
    numeric_cols, categorical_cols = _identify_column_types(X)

    # Step 2: Identify bad columns (fit on train)
    if config.drop_high_missing or config.drop_constant:
        cols_to_drop = _identify_bad_columns(X, config.missing_threshold)
        preprocessor.cols_to_drop = cols_to_drop
        numeric_cols = [c for c in numeric_cols if c not in cols_to_drop]
        categorical_cols = [c for c in categorical_cols if c not in cols_to_drop]

    preprocessor.numeric_cols = numeric_cols
    preprocessor.categorical_cols = categorical_cols

    # Drop bad columns
    X = X.drop(columns=preprocessor.cols_to_drop, errors='ignore')

    # Step 3: Fit imputers
    if numeric_cols:
        num_cols_present = [c for c in numeric_cols if c in X.columns]
        if num_cols_present:
            if config.impute_strategy == 'knn':
                preprocessor.num_imputer = KNNImputer(n_neighbors=config.knn_neighbors)
            else:
                preprocessor.num_imputer = SimpleImputer(strategy=config.impute_strategy)
            preprocessor.num_imputer.fit(X[num_cols_present])

    if categorical_cols:
        cat_cols_present = [c for c in categorical_cols if c in X.columns]
        if cat_cols_present:
            preprocessor.cat_imputer = SimpleImputer(strategy='most_frequent', fill_value='missing')
            preprocessor.cat_imputer.fit(X[cat_cols_present].astype(str))

    # Step 4: Fit outlier caps (on train only)
    if config.outlier_capping and config.outlier_method != 'none' and numeric_cols:
        num_cols_present = [c for c in numeric_cols if c in X.columns]
        preprocessor.outlier_caps = _fit_outlier_caps(
            X, num_cols_present,
            method=config.outlier_method,
            lower_q=config.lower_quantile,
            upper_q=config.upper_quantile,
            iqr_factor=config.iqr_factor
        )

    # Step 5: Fit scaler
    if config.scaling and numeric_cols:
        num_cols_present = [c for c in numeric_cols if c in X.columns]
        if num_cols_present:
            # Apply imputation and outlier caps first
            X_num = X[num_cols_present].copy()
            if preprocessor.num_imputer is not None:
                X_num = pd.DataFrame(
                    preprocessor.num_imputer.transform(X_num),
                    columns=num_cols_present, index=X.index
                )
            if preprocessor.outlier_caps:
                X_num = _apply_outlier_caps(X_num, preprocessor.outlier_caps)

            preprocessor.scaler = StandardScaler()
            preprocessor.scaler.fit(X_num)

    # Step 6: Fit label encoders
    if categorical_cols:
        cat_cols_present = [c for c in categorical_cols if c in X.columns]
        if cat_cols_present:
            preprocessor.label_encoders = {}
            for col in cat_cols_present:
                le = LabelEncoder()
                values = X[col].fillna('missing').astype(str).values
                le.fit(values)
                preprocessor.label_encoders[col] = le

    # Step 7: Compute sample weights (for fairness reweighting)
    if config.fairness_reweighting != 'none' and sensitive_train is not None:
        if config.fairness_reweighting == 'aif360':
            weights, factors = compute_aif360_sample_weights(y_train, sensitive_train)
        else:  # 'manual'
            weights, factors = compute_manual_sample_weights(y_train, sensitive_train)

        preprocessor.sample_weights = weights
        preprocessor.reweighting_factors = factors

    # Step 8: Fit fairness feature transforms (applied during apply_variant_preprocessing)
    # These are fit on the preprocessed training data
    if config.fairness_transform != 'none' and sensitive_train is not None:
        # First apply basic preprocessing to get X_train_preprocessed
        X_temp = apply_variant_preprocessing_internal(X, preprocessor)

        if config.fairness_transform == 'corr_remove':
            _, preprocessor.correlation_remover = apply_correlation_remover(
                X_temp, sensitive_train, alpha=config.corr_remove_alpha
            )
        elif config.fairness_transform == 'dir':
            _, preprocessor.dir_repair_info = apply_disparate_impact_remover(
                X_temp, sensitive_train, repair_level=1.0
            )

    # Store final feature names
    final_cols = [c for c in numeric_cols if c in X.columns]
    final_cols.extend([c for c in categorical_cols if c in X.columns])
    preprocessor.final_feature_names = final_cols

    logger.info(f"Fitted [{config.preproc_id}]: {len(numeric_cols)} numeric, "
                f"{len(categorical_cols)} categorical, {len(preprocessor.cols_to_drop)} dropped")

    return preprocessor


def apply_variant_preprocessing_internal(
    X: pd.DataFrame,
    preprocessor: FittedVariantPreprocessor
) -> np.ndarray:
    """
    Internal function: Apply basic preprocessing (without fairness transforms).

    Used during fitting to get preprocessed data for fairness transform fitting.
    """
    X = X.copy()

    # Step 1: Drop bad columns
    X = X.drop(columns=preprocessor.cols_to_drop, errors='ignore')

    # Step 2: Impute
    num_cols = [c for c in preprocessor.numeric_cols if c in X.columns]
    cat_cols = [c for c in preprocessor.categorical_cols if c in X.columns]

    if num_cols and preprocessor.num_imputer is not None:
        X[num_cols] = preprocessor.num_imputer.transform(X[num_cols])

    if cat_cols and preprocessor.cat_imputer is not None:
        X[cat_cols] = preprocessor.cat_imputer.transform(X[cat_cols].astype(str))

    # Step 3: Apply outlier caps
    if preprocessor.outlier_caps:
        X = _apply_outlier_caps(X, preprocessor.outlier_caps)

    # Step 4: Apply scaling
    if preprocessor.scaler is not None and num_cols:
        X[num_cols] = preprocessor.scaler.transform(X[num_cols])

    # Step 5: Apply label encoding
    if preprocessor.label_encoders:
        for col, le in preprocessor.label_encoders.items():
            if col in X.columns:
                values = X[col].fillna('missing').astype(str).values
                seen_classes = set(le.classes_)
                encoded = np.array([
                    le.transform([v])[0] if v in seen_classes else -1
                    for v in values
                ])
                X[col] = encoded

    # Return as numpy array with correct column order
    return X[preprocessor.final_feature_names].values


def apply_variant_preprocessing(
    X: pd.DataFrame,
    preprocessor: FittedVariantPreprocessor,
    sensitive: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Apply fitted preprocessing to any split.

    Args:
        X: Data to transform (DataFrame)
        preprocessor: Fitted preprocessor from fit_variant_preprocessing
        sensitive: Sensitive attribute (required for fairness transforms)

    Returns:
        Transformed features as numpy array
    """
    # Apply basic preprocessing
    X_processed = apply_variant_preprocessing_internal(X, preprocessor)

    # Apply fairness feature transforms if fitted
    if preprocessor.correlation_remover is not None and sensitive is not None:
        X_processed = transform_correlation_remover(
            X_processed, sensitive, preprocessor.correlation_remover
        )

    if preprocessor.dir_repair_info is not None and sensitive is not None:
        X_processed = transform_disparate_impact_remover(
            X_processed, sensitive, preprocessor.dir_repair_info
        )

    return X_processed


def preprocess_splits_with_variant(
    X_train: pd.DataFrame,
    X_calib: pd.DataFrame,
    X_cp: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: np.ndarray,
    sensitive_train: Optional[np.ndarray],
    sensitive_calib: Optional[np.ndarray] = None,
    sensitive_cp: Optional[np.ndarray] = None,
    sensitive_test: Optional[np.ndarray] = None,
    preproc_id: str = 'baseline'
) -> PreprocessingResult:
    """
    Preprocess all splits using a specific variant.

    CRITICAL: Fits ONLY on train, applies to all splits.

    Args:
        X_train, X_calib, X_cp, X_test: DataFrames for each split
        y_train: Training labels (for reweighting)
        sensitive_train: Training sensitive attribute (for reweighting/fairness transforms)
        sensitive_calib, sensitive_cp, sensitive_test: Sensitive attrs for other splits
            (required for fairness transforms like CorrelationRemover, DIR)
        preproc_id: Preprocessing variant ID

    Returns:
        PreprocessingResult with transformed splits and metadata
    """
    config = get_variant_config(preproc_id)

    # Fit on train only
    preprocessor = fit_variant_preprocessing(X_train, y_train, sensitive_train, config)

    # Apply to all splits (pass sensitive for fairness transforms)
    X_train_proc = apply_variant_preprocessing(X_train, preprocessor, sensitive_train)
    X_calib_proc = apply_variant_preprocessing(X_calib, preprocessor, sensitive_calib)
    X_cp_proc = apply_variant_preprocessing(X_cp, preprocessor, sensitive_cp)
    X_test_proc = apply_variant_preprocessing(X_test, preprocessor, sensitive_test)

    return PreprocessingResult(
        X_train=X_train_proc,
        X_calib=X_calib_proc,
        X_cp=X_cp_proc,
        X_test=X_test_proc,
        sample_weights_train=preprocessor.sample_weights,
        feature_names=preprocessor.final_feature_names,
        preproc_id=preproc_id,
        metadata={
            'config': config.__dict__,
            'n_numeric': len(preprocessor.numeric_cols),
            'n_categorical': len(preprocessor.categorical_cols),
            'n_dropped': len(preprocessor.cols_to_drop),
            'reweighting_factors': preprocessor.reweighting_factors
        }
    )


# =============================================================================
# CACHE PATH HELPERS
# =============================================================================

def get_split_cache_path(
    cache_root: str,
    dataset: str,
    seed: int,
    split_id: int
) -> str:
    """
    Get cache path for split indices (shared across preproc variants).

    Path: {cache_root}/splits/{dataset}/seed={seed}/split={split_id}/indices.npz
    """
    from pathlib import Path
    path = Path(cache_root) / "splits" / dataset / f"seed={seed}" / f"split={split_id}"
    path.mkdir(parents=True, exist_ok=True)
    return str(path / "indices.npz")


def get_probs_cache_path(
    cache_root: str,
    dataset: str,
    model: str,
    preproc_id: str,
    seed: int,
    split_id: int
) -> str:
    """
    Get cache path for model predictions (preproc-specific).

    Path: {cache_root}/preds/{dataset}/{model}/{preproc_id}/seed={seed}/split={split_id}/probs.npz
    """
    from pathlib import Path
    path = Path(cache_root) / "preds" / dataset / model / preproc_id / f"seed={seed}" / f"split={split_id}"
    path.mkdir(parents=True, exist_ok=True)
    return str(path / "probs.npz")
