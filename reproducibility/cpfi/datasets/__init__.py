"""
CPFI Datasets Module - Session 2

Extended dataset loaders for comprehensive ablation study.
"""

from .compas import load_compas
from .hmda import load_hmda
from .give_me_credit import load_give_me_credit

__all__ = [
    'load_compas',
    'load_hmda',
    'load_give_me_credit',
]
