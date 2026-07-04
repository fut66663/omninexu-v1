"""Product async persistence.

Write API response snapshots (Company Context / Radar / Pulse) to the
``products/`` directory asynchronously for historical comparison, cache
warm-up and quality audit.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omninexu.config import data_paths
from omninexu.observability import get_logger

logger = get_logger(__name__)


def save_product(
    product_type: str,
    ticker: str,
    data: dict[str, Any],
    *,
    timestamp: datetime | None = None,
) -> Path | None:
    """Save an API product snapshot to disk.

    Args:
        product_type: ``"context"`` / ``"radar"`` / ``"pulse"``.
        ticker: Stock ticker (auto-uppercased).
        data: Full API response dict.
        timestamp: Optional UTC timestamp (defaults to now).

    Returns:
        Path to the written file, or ``None`` on failure.
        This function never raises — a disk-full or permission
        error must not take down the API.
    """
    ts = timestamp or datetime.now(UTC)
    date_str = ts.strftime("%Y-%m-%d")
    ticker_upper = ticker.upper()

    try:
        dir_path = _product_dir(product_type) / ticker_upper
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{date_str}.json"
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        logger.debug(
            f"Product saved: {product_type}/{ticker_upper}/{date_str}.json"
        )
        return file_path
    except (OSError, TypeError) as exc:
        logger.warning(
            f"Failed to save product {product_type}/{ticker}: {exc}"
        )
        return None


def _product_dir(product_type: str) -> Path:
    """Map product type string to configured directory."""
    mapping: dict[str, Path] = {
        "context": data_paths.products_context,
        "radar": data_paths.products_radar,
        "pulse": data_paths.products_pulse,
    }
    if product_type not in mapping:
        raise ValueError(f"Unknown product_type: {product_type}")
    return mapping[product_type]
