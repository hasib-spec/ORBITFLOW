"""
OrbitFlow Core Configuration
=============================
"""

from __future__ import annotations

import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Project root (two levels up from backend/app/core/)
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
RULES_DIR: Path = PROJECT_ROOT / "rules"
TEMPLATES_DIR: Path = PROJECT_ROOT / "templates"
OUTPUT_DIR: Path = PROJECT_ROOT / "output"

# Ensure output dir exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger instance."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENGINE_VERSION: str = "0.1.0"
REGIME_PART_25: str = "FCC Part 25 (47 CFR Part 25)"
REGIME_PART_100: str = "FCC Part 100 (Adopted — FCC 25-69, SB Docket 25-306)"

# Altitude thresholds (km)
LEO_CEILING_KM: float = 2_000.0
GEO_ALTITUDE_KM: float = 35_786.0

# Trackability thresholds (cm)
TRACKABILITY_LEO_CM: float = 10.0
TRACKABILITY_ABOVE_LEO_CM: float = 100.0  # 1 meter

# De-orbit deadline (years)
DEORBIT_DEADLINE_YEARS: float = 5.0

# Bond
BOND_BASE_USD: int = 10_000_000
BOND_RELIEF_PCT: float = 90.0

# License terms
LICENSE_TERM_PART_25_YEARS: int = 15
LICENSE_TERM_PART_100_YEARS: int = 20
