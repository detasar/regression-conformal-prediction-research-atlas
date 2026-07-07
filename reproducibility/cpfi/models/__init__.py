"""
Model training module for CPFI experiments.

Supports GPU-accelerated training with automatic CPU fallback.
Models: XGBoost, LightGBM, CatBoost
"""

from .trainers import (
    train_model,
    get_cached_probs,
    clear_cache,
    TrainedModel
)

__all__ = ['train_model', 'get_cached_probs', 'clear_cache', 'TrainedModel']
