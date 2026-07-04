"""Shared constants and utilities for data verification modules."""

from __future__ import annotations

import json

from omninexu.config import data_paths

UNIVERSE_DIR = data_paths.processed_universe

# All API-verified companies (20: 10 core + 10 peer).
# Used by verify_all, spotcheck, and other verification scripts.
VERIFY_TICKERS: list[str] = [
    # Core (10) — 6/6 high confidence
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "WMT",
    "XOM",
    "JPM",
    "CAT",
    "PFE",
    "GOOGL",
    # Peer (10) — 5-6/6 after Phase 1–2
    "ABBV",
    "ABNB",
    "ABT",
    "ACN",
    "ADBE",
    "ADI",
    "ADP",
    "ADSK",
    "AEP",
    "AFL",
]

# Anchor revenue values are stored in a JSON data file so they can be updated
# without changing code.  Path: D:/OmniNexuData/operations/quality/anchor_revenue.json
_ANCHOR_PATH = data_paths.quality_dir / "anchor_revenue.json"


def _load_anchors() -> dict[str, float]:
    """Load anchor revenue values from the quality data file."""
    if not _ANCHOR_PATH.exists():
        return {}
    with open(_ANCHOR_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("anchors", {})


ANCHOR_REVENUE: dict[str, float] = _load_anchors()


def load_universe(day: int) -> list[dict]:
    """Load company universe for a given batch day."""
    path = UNIVERSE_DIR / f"sp500_universe_day{day}.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
