"""
Preprocessing module for CPFI experiments.

CRITICAL: All preprocessing is fit ONLY on train_idx to prevent data leakage.
"""

from .pipeline import (
    PreprocessingConfig,
    FittedPreprocessor,
    fit_preprocessing,
    apply_preprocessing,
    preprocess_splits,
    identify_column_types,
    identify_bad_columns,
    fit_outlier_caps,
    apply_outlier_caps,
)

__all__ = [
    'PreprocessingConfig',
    'FittedPreprocessor',
    'fit_preprocessing',
    'apply_preprocessing',
    'preprocess_splits',
    'identify_column_types',
    'identify_bad_columns',
    'fit_outlier_caps',
    'apply_outlier_caps',
]
