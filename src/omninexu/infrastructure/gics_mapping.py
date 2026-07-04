"""SIC → GICS industry classification lookup.

Data source: ``D:/OmniNexuData/processed/gics/sic_to_gics.csv`` — 10 S&P 500
companies manually annotated.  Path resolved via :class:`DataPaths`.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from omninexu.config import data_paths
from omninexu.observability import get_logger

logger = get_logger(__name__)

# Cached mapping: sic_code → GicsClassification
_cache: dict[str, "GicsClassification"] | None = None


@dataclass(frozen=True)
class GicsClassification:
    """GICS four-tier industry classification."""

    sic: str
    gics_sector: str
    gics_sub_industry: str
    gics_industry_group: str | None = None
    gics_industry: str | None = None


def _default_csv_path() -> Path:
    """Return the default path to gics_mapping.csv (via DataPaths)."""
    return data_paths.processed_gics / "sic_to_gics.csv"


def load_mapping(path: str | Path | None = None) -> dict[str, GicsClassification]:
    """Load SIC→GICS mapping from CSV. Results are cached in memory."""
    global _cache
    if _cache is not None:
        return _cache

    csv_path = Path(path) if path else _default_csv_path()
    logger.info(f"Loading GICS mapping from {csv_path}")

    mapping: dict[str, GicsClassification] = {}
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sic = row["sic"].strip()
            mapping[sic] = GicsClassification(
                sic=sic,
                gics_sector=row["gics_sector"].strip(),
                gics_industry_group=row["gics_industry_group"].strip() or None,
                gics_industry=row["gics_industry"].strip() or None,
                gics_sub_industry=row["gics_sub_industry"].strip(),
            )

    _cache = mapping
    logger.info(f"Loaded {len(mapping)} GICS mappings")
    return mapping


def lookup(sic_code: str) -> GicsClassification | None:
    """Look up GICS classification for a SIC code. Returns None if not found."""
    return load_mapping().get(sic_code.strip())
