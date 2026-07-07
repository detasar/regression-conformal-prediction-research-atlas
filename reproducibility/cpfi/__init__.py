"""
CPFI - Conformal Prediction Fairness Investigation

A Python package for studying fairness implications of conformal prediction
methods in human-in-the-loop (HITL) decision systems.

Author: Davut Emre Tasar
"""

from pathlib import Path
import os

# Package version
__version__ = "1.0.0"

# Data directories (configurable via environment variables)
_pkg_root = Path(__file__).parent
DATA_RAW = Path(os.environ.get("CPFI_DATA_RAW", _pkg_root / "data" / "raw"))
DATA_PROCESSED = Path(os.environ.get("CPFI_DATA_PROCESSED", _pkg_root / "data" / "processed"))
CACHE_DIR = Path(os.environ.get("CPFI_CACHE", _pkg_root / ".cache"))
CACHE_PREDS = Path(os.environ.get("CPFI_CACHE_PREDS", CACHE_DIR / "predictions"))


def ensure_runtime_dirs() -> None:
    """Create runtime data/cache directories at explicit writer boundaries."""

    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PREDS.mkdir(parents=True, exist_ok=True)

__all__ = [
    "__version__",
    "DATA_RAW",
    "DATA_PROCESSED",
    "CACHE_DIR",
    "CACHE_PREDS",
    "ensure_runtime_dirs",
]
