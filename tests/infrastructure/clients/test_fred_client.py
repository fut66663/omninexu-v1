"""Tests for FRED API client."""

import pytest

from omninexu.infrastructure.clients.fred_client import CORE_SERIES, FredClient


class TestFredClientCore:
    """Core client behavior — does not require a real API key."""

    def test_unconfigured_returns_empty(self) -> None:
        """Without an API key, get_series returns [] and doesn't crash."""
        client = FredClient(api_key="")
        assert not client.is_configured()
        assert client.get_series("FEDFUNDS") == []

    def test_short_key_not_configured(self) -> None:
        """A key shorter than 32 chars is treated as unconfigured."""
        client = FredClient(api_key="short")
        assert not client.is_configured()

    def test_32_char_key_is_configured(self) -> None:
        """A 32-char key is considered configured."""
        client = FredClient(api_key="a" * 32)
        assert client.is_configured()

    def test_get_latest_unconfigured_returns_none(self) -> None:
        """get_latest returns None without a key."""
        client = FredClient(api_key="")
        assert client.get_latest("FEDFUNDS") is None

    def test_core_snapshot_unconfigured(self) -> None:
        """get_core_snapshot returns None entries when unconfigured."""
        client = FredClient(api_key="")
        snap = client.get_core_snapshot()
        for sid in CORE_SERIES:
            assert snap[sid] is None, f"{sid} should be None"

    def test_core_series_has_5_indicators(self) -> None:
        """CORE_SERIES must contain exactly 5 indicators with metadata."""
        assert len(CORE_SERIES) == 5
        for sid in ["FEDFUNDS", "CPIAUCSL", "GDP", "UNRATE", "DGS10"]:
            assert sid in CORE_SERIES
            assert "name" in CORE_SERIES[sid]
            assert "unit" in CORE_SERIES[sid]


class TestFredClientLive:
    """Live API tests — require FRED_API_KEY in env/.env."""

    @pytest.fixture(scope="class")
    @classmethod
    def client(cls) -> FredClient:
        c = FredClient()
        if not c.is_configured():
            pytest.skip("FRED_API_KEY not configured")
        return c

    def test_get_latest_fedfunds(self, client: FredClient) -> None:
        """Latest federal funds rate within reasonable bounds."""
        result = client.get_latest("FEDFUNDS")
        assert result is not None
        assert 0.0 <= result["value"] <= 25.0

    def test_get_latest_unrate(self, client: FredClient) -> None:
        """Latest unemployment rate within reasonable bounds."""
        result = client.get_latest("UNRATE")
        assert result is not None
        assert 0.0 <= result["value"] <= 20.0

    def test_get_latest_dgs10(self, client: FredClient) -> None:
        """Latest 10Y Treasury yield within reasonable bounds."""
        result = client.get_latest("DGS10")
        assert result is not None
        assert -5.0 <= result["value"] <= 25.0

    def test_core_snapshot_all_five(self, client: FredClient) -> None:
        """get_core_snapshot returns non-None for all 5 core series."""
        snap = client.get_core_snapshot()
        for sid in CORE_SERIES:
            assert snap[sid] is not None, f"{sid} is None"

    def test_get_series_with_limit(self, client: FredClient) -> None:
        """get_series(limit=5) returns exactly 5 observations."""
        data = client.get_series("FEDFUNDS", limit=5)
        assert len(data) == 5

    def test_invalid_series_returns_empty(self, client: FredClient) -> None:
        """Bogus series ID returns empty list."""
        assert client.get_series("NOT_A_REAL_SERIES_XYZ") == []
