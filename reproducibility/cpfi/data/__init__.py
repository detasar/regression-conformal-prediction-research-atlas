"""
Data loading module for CPFI experiments.

Datasets:
1. german_credit (OpenML)
2. taiwan_credit (OpenML)
3. adult (fairlearn/OpenML)
4. acs_income (folktables)
5. bank_marketing (OpenML)
6. home_credit (Kaggle - local file)
"""

from .loaders import (
    load_dataset,
    AVAILABLE_DATASETS,
    DatasetResult
)

__all__ = ['load_dataset', 'AVAILABLE_DATASETS', 'DatasetResult']
