"""Tests for the FRED client stub."""

from omninexu.infrastructure.clients.fred_client import FredClient


def test_fred_client_configured_with_key():
    """is_configured should be True when a non-empty API key is provided."""
    client = FredClient(api_key="test-key")
    assert client.is_configured() is True


def test_fred_client_not_configured_without_key():
    """is_configured should be False when API key is None."""
    client = FredClient(api_key=None)
    assert client.is_configured() is False


def test_fred_client_not_configured_with_empty_key():
    """is_configured should be False when API key is an empty string."""
    client = FredClient(api_key="")
    assert client.is_configured() is False


def test_fred_get_series_returns_none():
    """get_series is a stub and should return None."""
    client = FredClient(api_key="test-key")
    assert client.get_series("GDP") is None
