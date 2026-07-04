"""Tests for product_store async persistence."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from omninexu.config.data_paths import DataPaths
from omninexu.infrastructure.product_store import save_product


class TestSaveProduct:
    """Unit tests for save_product function."""

    @staticmethod
    def _sample_context() -> dict:
        """Return a minimal but realistic Company Context dict."""
        return {
            "ticker": "AAPL",
            "cik": "0000320193",
            "name": "Apple Inc.",
            "as_of_date": "2025-09-27",
            "fundamentals": {
                "revenue": {"value": 416161000000, "unit": "USD", "fiscal_year": 2025},
            },
            "longitudinal": {"revenue_cagr": 0.08},
            "peer_comparison": None,
            "institutional": None,
            "insider": None,
            "sources": [{"type": "10-K", "url": "https://..."}],
            "confidence": "high",
        }

    @staticmethod
    def _patch_data_paths(tmp_path: Path):
        """Redirect product_store's data_paths import to use *tmp_path*."""
        fake_dp = DataPaths(str(tmp_path))
        return patch(
            "omninexu.infrastructure.product_store.data_paths",
            fake_dp,
        )

    def test_save_context_creates_file(self, tmp_path: Path) -> None:
        """save_product("context", ...) writes a valid JSON file."""
        with self._patch_data_paths(tmp_path):
            result = save_product(
                "context", "AAPL", self._sample_context(),
                timestamp=datetime(2026, 6, 30, 12, 0, 0),
            )

        assert result is not None
        target = tmp_path / "products" / "context" / "AAPL" / "2026-06-30.json"
        assert target.exists()
        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert loaded["ticker"] == "AAPL"
        assert "revenue" in loaded["fundamentals"]

    def test_save_product_same_day_overwrites(self, tmp_path: Path) -> None:
        """Second call on the same day overwrites the file."""
        ts = datetime(2026, 6, 30, 12, 0, 0)
        first = {"ticker": "AAPL", "confidence": "high"}
        second = {"ticker": "AAPL", "confidence": "medium"}

        with self._patch_data_paths(tmp_path):
            save_product("context", "AAPL", first, timestamp=ts)
            save_product("context", "AAPL", second, timestamp=ts)

        target = tmp_path / "products" / "context" / "AAPL" / "2026-06-30.json"
        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert loaded["confidence"] == "medium"

    def test_save_product_unknown_type_raises(self) -> None:
        """Unknown product_type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown product_type"):
            save_product("unknown", "AAPL", {})

    def test_save_product_disk_full_returns_none(self, tmp_path: Path) -> None:
        """When the disk write fails the function returns None (no crash)."""
        with self._patch_data_paths(tmp_path), patch.object(
            Path, "write_text", side_effect=OSError("Disk full")
        ):
            result = save_product(
                "context", "AAPL", self._sample_context(),
                timestamp=datetime(2026, 6, 30, 12, 0, 0),
            )

        assert result is None

    def test_save_product_ticker_is_uppercased(self, tmp_path: Path) -> None:
        """Ticker is always stored uppercase regardless of input casing."""
        with self._patch_data_paths(tmp_path):
            result = save_product(
                "context", "aapl", self._sample_context(),
                timestamp=datetime(2026, 6, 30, 12, 0, 0),
            )

        assert result is not None
        assert "AAPL" in str(result)
        target = tmp_path / "products" / "context" / "AAPL" / "2026-06-30.json"
        assert target.exists()
