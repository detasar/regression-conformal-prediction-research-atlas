"""
Model training with GPU fallback for CPFI experiments - V3.4

Supports: XGBoost, LightGBM, CatBoost, RandomForest
All models output calibrated probabilities.

V3.4 CHANGES:
- Class imbalance handling (class_weight, SMOTE)
- Updated to work with 4-way splits (train/calib/cp/test)
- Returns probs for cp and test separately
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Tuple, Any, Literal
from dataclasses import dataclass
from loguru import logger

from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV
from sklearn.utils.class_weight import compute_class_weight

from cpfi import CACHE_PREDS


# Try importing SMOTE
try:
    from imblearn.over_sampling import SMOTE
    IMBLEARN_AVAILABLE = True
except ImportError:
    IMBLEARN_AVAILABLE = False
    logger.debug("imblearn not available, SMOTE disabled")


@dataclass
class TrainedModel:
    """Result from training a model."""
    model: Any
    probs_calib: np.ndarray  # V3.4: For probability calibration set
    probs_cp: np.ndarray     # V3.4: For conformal calibration set
    probs_test: np.ndarray   # For final evaluation
    train_time: float
    used_gpu: bool
    metadata: Dict

    # Backwards compatibility
    @property
    def probs_cal(self) -> np.ndarray:
        """Backwards compatibility: probs_cal is now probs_cp."""
        return self.probs_cp


def _check_gpu_available(model_type: str) -> bool:
    """Check if GPU is available for the given model type."""
    if model_type == 'xgboost':
        try:
            import xgboost as xgb
            # Try to create a small GPU model
            test_model = xgb.XGBClassifier(
                device='cuda',
                n_estimators=1,
                verbosity=0
            )
            X_test = np.random.randn(10, 5)
            y_test = np.random.randint(0, 2, 10)
            test_model.fit(X_test, y_test)
            return True
        except Exception:
            return False

    elif model_type == 'lightgbm':
        try:
            import lightgbm as lgb
            # Check if GPU device is available
            test_model = lgb.LGBMClassifier(
                device='gpu',
                n_estimators=1,
                verbose=-1
            )
            X_test = np.random.randn(10, 5)
            y_test = np.random.randint(0, 2, 10)
            test_model.fit(X_test, y_test)
            return True
        except Exception:
            return False

    elif model_type == 'catboost':
        try:
            from catboost import CatBoostClassifier
            test_model = CatBoostClassifier(
                task_type='GPU',
                iterations=1,
                verbose=False
            )
            X_test = np.random.randn(10, 5)
            y_test = np.random.randint(0, 2, 10)
            test_model.fit(X_test, y_test)
            return True
        except Exception:
            return False

    return False


def _compute_sample_weights(
    y: np.ndarray,
    method: str = 'class_weight'
) -> Optional[np.ndarray]:
    """
    Compute sample weights for class imbalance handling.

    Args:
        y: Training labels
        method: 'none', 'class_weight', or 'smote'

    Returns:
        Sample weights array or None
    """
    if method == 'none' or method == 'smote':
        return None

    if method == 'class_weight':
        classes = np.unique(y)
        weights = compute_class_weight('balanced', classes=classes, y=y)
        weight_dict = dict(zip(classes, weights))
        sample_weights = np.array([weight_dict[yi] for yi in y])
        logger.debug(f"Class weights computed: {weight_dict}")
        return sample_weights

    return None


def _apply_smote(
    X: pd.DataFrame,
    y: np.ndarray,
    k_neighbors: int = 5,
    sampling_strategy: str = 'auto',
    random_state: int = 42
) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Apply SMOTE oversampling for class imbalance.

    Args:
        X: Features
        y: Labels
        k_neighbors: Number of neighbors for SMOTE
        sampling_strategy: SMOTE sampling strategy
        random_state: Random seed

    Returns:
        Tuple of (resampled_X, resampled_y)
    """
    if not IMBLEARN_AVAILABLE:
        logger.warning("imblearn not available, skipping SMOTE")
        return X, y

    try:
        smote = SMOTE(
            k_neighbors=k_neighbors,
            sampling_strategy=sampling_strategy,
            random_state=random_state
        )
        X_resampled, y_resampled = smote.fit_resample(X, y)
        logger.info(f"SMOTE applied: {len(y)} -> {len(y_resampled)} samples")

        # Convert back to DataFrame if needed
        if isinstance(X, pd.DataFrame):
            X_resampled = pd.DataFrame(X_resampled, columns=X.columns)

        return X_resampled, y_resampled

    except Exception as e:
        logger.warning(f"SMOTE failed: {e}, using original data")
        return X, y


def _create_xgboost_model(
    use_gpu: bool,
    params: Dict,
    scale_pos_weight: Optional[float] = None
) -> Any:
    """Create XGBoost classifier with optional GPU support."""
    import xgboost as xgb

    default_params = {
        'n_estimators': 500,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'verbosity': 0,
        'early_stopping_rounds': 50,
    }
    default_params.update(params)

    # Add scale_pos_weight for imbalanced data
    if scale_pos_weight is not None:
        default_params['scale_pos_weight'] = scale_pos_weight

    if use_gpu:
        default_params['device'] = 'cuda'
        default_params['tree_method'] = 'hist'
    else:
        default_params['device'] = 'cpu'
        default_params['tree_method'] = 'hist'

    return xgb.XGBClassifier(**default_params)


def _create_lightgbm_model(
    use_gpu: bool,
    params: Dict,
    class_weight: Optional[str] = None
) -> Any:
    """Create LightGBM classifier with optional GPU support."""
    import lightgbm as lgb

    default_params = {
        'n_estimators': 500,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'verbose': -1,
    }
    default_params.update(params)

    # Add class_weight for imbalanced data
    if class_weight is not None:
        default_params['class_weight'] = class_weight

    if use_gpu:
        default_params['device'] = 'gpu'
    else:
        default_params['device'] = 'cpu'

    return lgb.LGBMClassifier(**default_params)


def _create_catboost_model(
    use_gpu: bool,
    params: Dict,
    class_weights: Optional[Dict] = None
) -> Any:
    """Create CatBoost classifier with optional GPU support."""
    from catboost import CatBoostClassifier

    default_params = {
        'iterations': 500,
        'depth': 6,
        'learning_rate': 0.1,
        'random_seed': 42,
        'verbose': False,
        'early_stopping_rounds': 50,
    }
    default_params.update(params)

    # Add class_weights for imbalanced data
    if class_weights is not None:
        default_params['class_weights'] = class_weights

    if use_gpu:
        default_params['task_type'] = 'GPU'
    else:
        default_params['task_type'] = 'CPU'

    return CatBoostClassifier(**default_params)


def _create_random_forest_model(
    params: Dict,
    class_weight: Optional[str] = None
) -> Any:
    """Create RandomForest classifier (CPU only, but fast)."""
    from sklearn.ensemble import RandomForestClassifier

    default_params = {
        'n_estimators': 200,
        'max_depth': 10,
        'min_samples_split': 5,
        'min_samples_leaf': 2,
        'random_state': 42,
        'n_jobs': -1,  # Use all cores
    }
    default_params.update(params)

    # Add class_weight for imbalanced data
    if class_weight is not None:
        default_params['class_weight'] = class_weight

    return RandomForestClassifier(**default_params)


def train_model(
    model_name: str,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_calib: pd.DataFrame,
    X_cp: pd.DataFrame,
    X_test: pd.DataFrame,
    use_gpu: bool = True,
    params: Optional[Dict] = None,
    cache_key: Optional[str] = None,
    seed: int = 0,
    class_imbalance: str = 'class_weight',
    smote_k_neighbors: int = 5,
    smote_sampling_strategy: str = 'auto'
) -> TrainedModel:
    """
    Train a model and return probabilities for all evaluation sets.

    V3.4: Supports 4-way splits and class imbalance handling.

    Args:
        model_name: One of 'xgboost', 'lightgbm', 'catboost'
        X_train: Training features
        y_train: Training labels
        X_calib: Probability calibration features (V3.4)
        X_cp: Conformal calibration features
        X_test: Test features
        use_gpu: Whether to try GPU first
        params: Additional model parameters
        cache_key: Optional cache key for saving probs (dataset/model)
        seed: Random seed
        class_imbalance: 'none', 'class_weight', or 'smote'
        smote_k_neighbors: K for SMOTE (if used)
        smote_sampling_strategy: SMOTE sampling strategy (if used)

    Returns:
        TrainedModel with probabilities for calib, cp, and test sets
    """
    import time

    params = params or {}

    # V3.4: Check cache first (new format with 3 prob arrays)
    if cache_key:
        cache_path = CACHE_PREDS / cache_key / f"seed={seed}"
        probs_file = cache_path / "probs_v34.npz"
        if probs_file.exists():
            logger.info(f"Loading cached V3.4 probabilities from {probs_file}")
            data = np.load(probs_file)
            return TrainedModel(
                model=None,
                probs_calib=data['probs_calib'],
                probs_cp=data['probs_cp'],
                probs_test=data['probs_test'],
                train_time=0.0,
                used_gpu=False,
                metadata={'cached': True, 'cache_path': str(probs_file)}
            )
        # Also check old format for backwards compatibility
        old_probs_file = cache_path / "probs.npz"
        if old_probs_file.exists():
            logger.info(f"Loading cached (old format) probabilities from {old_probs_file}")
            data = np.load(old_probs_file)
            # Old format doesn't have calib, set to empty
            return TrainedModel(
                model=None,
                probs_calib=np.array([]),
                probs_cp=data['probs_cal'],
                probs_test=data['probs_test'],
                train_time=0.0,
                used_gpu=False,
                metadata={'cached': True, 'cache_path': str(old_probs_file), 'old_format': True}
            )

    # Determine if GPU should be used
    actual_gpu = False
    if use_gpu:
        actual_gpu = _check_gpu_available(model_name)
        if actual_gpu:
            logger.info(f"GPU available for {model_name}")
        else:
            logger.info(f"GPU not available for {model_name}, falling back to CPU")

    # V3.4: Handle class imbalance
    X_train_fit, y_train_fit = X_train, y_train
    sample_weights = None
    scale_pos_weight = None
    class_weight_param = None
    class_weights_dict = None

    if class_imbalance == 'smote':
        X_train_fit, y_train_fit = _apply_smote(
            X_train, y_train, smote_k_neighbors, smote_sampling_strategy, seed
        )
    elif class_imbalance == 'class_weight':
        # Compute class weight for model-specific parameters
        n_neg = (y_train == 0).sum()
        n_pos = (y_train == 1).sum()
        if n_pos > 0:
            scale_pos_weight = n_neg / n_pos  # For XGBoost
            class_weight_param = 'balanced'    # For LightGBM
            class_weights_dict = {0: n_pos / (n_neg + n_pos), 1: n_neg / (n_neg + n_pos)}  # For CatBoost

    # Create model with class imbalance parameters
    if model_name == 'xgboost':
        model = _create_xgboost_model(actual_gpu, params, scale_pos_weight)
    elif model_name == 'lightgbm':
        model = _create_lightgbm_model(actual_gpu, params, class_weight_param)
    elif model_name == 'catboost':
        model = _create_catboost_model(actual_gpu, params, class_weights_dict)
    elif model_name == 'random_forest':
        model = _create_random_forest_model(params, class_weight_param)
        actual_gpu = False  # RF is CPU only
    else:
        raise ValueError(f"Unknown model: {model_name}")

    # Train with OOM fallback
    start_time = time.time()
    try:
        # Split some training data for early stopping validation
        X_tr, X_val, y_tr, y_val = train_test_split(
            X_train_fit, y_train_fit, test_size=0.1, random_state=seed, stratify=y_train_fit
        )

        if model_name == 'xgboost':
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
        elif model_name == 'lightgbm':
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_val, y_val)],
                callbacks=[
                    __import__('lightgbm').early_stopping(50, verbose=False)
                ]
            )
        elif model_name == 'catboost':
            model.fit(
                X_tr, y_tr,
                eval_set=(X_val, y_val),
                verbose=False
            )
        elif model_name == 'random_forest':
            # RandomForest doesn't have early stopping, train on full data
            model.fit(X_train_fit, y_train_fit)

    except Exception as e:
        if actual_gpu and ('CUDA' in str(e) or 'GPU' in str(e) or 'memory' in str(e).lower()):
            logger.warning(f"GPU OOM for {model_name}, retrying with CPU...")
            actual_gpu = False

            # Recreate model for CPU
            if model_name == 'xgboost':
                model = _create_xgboost_model(False, params, scale_pos_weight)
            elif model_name == 'lightgbm':
                model = _create_lightgbm_model(False, params, class_weight_param)
            elif model_name == 'catboost':
                model = _create_catboost_model(False, params, class_weights_dict)

            # Retry on CPU
            X_tr, X_val, y_tr, y_val = train_test_split(
                X_train_fit, y_train_fit, test_size=0.1, random_state=seed, stratify=y_train_fit
            )

            if model_name == 'xgboost':
                model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
            elif model_name == 'lightgbm':
                model.fit(
                    X_tr, y_tr,
                    eval_set=[(X_val, y_val)],
                    callbacks=[__import__('lightgbm').early_stopping(50, verbose=False)]
                )
            elif model_name == 'catboost':
                model.fit(X_tr, y_tr, eval_set=(X_val, y_val), verbose=False)
        else:
            raise

    train_time = time.time() - start_time

    # V3.4: Get probabilities for all three sets
    probs_calib = model.predict_proba(X_calib)[:, 1] if len(X_calib) > 0 else np.array([])
    probs_cp = model.predict_proba(X_cp)[:, 1]
    probs_test = model.predict_proba(X_test)[:, 1]

    # V3.4: Cache probabilities in new format
    if cache_key:
        cache_path = CACHE_PREDS / cache_key / f"seed={seed}"
        cache_path.mkdir(parents=True, exist_ok=True)
        probs_file = cache_path / "probs_v34.npz"
        np.savez_compressed(
            probs_file,
            probs_calib=probs_calib,
            probs_cp=probs_cp,
            probs_test=probs_test
        )
        logger.info(f"Cached V3.4 probabilities to {probs_file}")

    return TrainedModel(
        model=model,
        probs_calib=probs_calib,
        probs_cp=probs_cp,
        probs_test=probs_test,
        train_time=train_time,
        used_gpu=actual_gpu,
        metadata={
            'model_name': model_name,
            'n_train': len(y_train),
            'n_train_after_smote': len(y_train_fit) if class_imbalance == 'smote' else len(y_train),
            'n_calib': len(X_calib),
            'n_cp': len(X_cp),
            'n_test': len(X_test),
            'train_time_seconds': train_time,
            'class_imbalance': class_imbalance
        }
    )


def get_cached_probs(
    cache_key: str,
    seed: int
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    Load cached probabilities if they exist.

    V3.4: Returns 3 probability arrays (calib, cp, test).

    Args:
        cache_key: Cache key (dataset/model)
        seed: Random seed

    Returns:
        Tuple of (probs_calib, probs_cp, probs_test) or None if not cached
    """
    cache_path = CACHE_PREDS / cache_key / f"seed={seed}"

    # Try V3.4 format first
    v34_file = cache_path / "probs_v34.npz"
    if v34_file.exists():
        data = np.load(v34_file)
        return data['probs_calib'], data['probs_cp'], data['probs_test']

    # Fall back to old format
    old_file = cache_path / "probs.npz"
    if old_file.exists():
        data = np.load(old_file)
        # Old format doesn't have calib
        return np.array([]), data['probs_cal'], data['probs_test']

    return None


def clear_cache(cache_key: Optional[str] = None):
    """Clear probability cache."""
    import shutil

    if cache_key:
        cache_path = CACHE_PREDS / cache_key
        if cache_path.exists():
            shutil.rmtree(cache_path)
            logger.info(f"Cleared cache: {cache_path}")
    else:
        if CACHE_PREDS.exists():
            shutil.rmtree(CACHE_PREDS)
        CACHE_PREDS.mkdir(parents=True, exist_ok=True)
        logger.info("Cleared all probability cache")
