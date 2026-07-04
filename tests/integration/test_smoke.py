"""Smoke tests — every API-verified company returns valid context.

These tests use FastAPI TestClient (no HTTP server needed) and rely on
the configured database (PostgreSQL via dependency_overrides).

Skipped on CI when the database has no seed data.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from omninexu.api.main import app
from omninexu.infrastructure.db import get_db

client = TestClient(app)


def _db_has_companies() -> bool:
    """Check if the database has at least one company seeded."""
    try:
        db = next(get_db())
        count = db.execute(text("SELECT count(*) FROM companies")).scalar()
        return count > 0
    except Exception:
        return False


_db_seeded = _db_has_companies()

CORE = ["AAPL", "MSFT", "NVDA", "GOOGL", "JPM", "TSLA", "XOM", "WMT", "CAT", "PFE"]
PEER = ["ABBV", "ABNB", "ABT", "ACN", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AFL"]
# Companies legitimately without recent insider transactions (5/6 = medium):
PEER_NO_INSIDER = {"ABBV", "ACN", "AEP"}


class TestSmoke:
    """Quick checks that every API-verified company returns valid context."""

    @pytest.mark.parametrize("ticker", CORE + PEER)
    def test_returns_200(self, ticker: str) -> None:
        """Every verified ticker should return HTTP 200."""
        if not _db_seeded:
            pytest.skip("No seed data — CI environment")
        assert client.get(f"/v1/company/context?ticker={ticker}").status_code == 200

    @pytest.mark.parametrize("ticker", CORE + PEER)
    def test_has_required_dimensions(self, ticker: str) -> None:
        """Every verified ticker must have fundamentals + sources + valid confidence."""
        if not _db_seeded:
            pytest.skip("No seed data — CI environment")
        data = client.get(f"/v1/company/context?ticker={ticker}").json()
        assert "fundamentals" in data
        assert "sources" in data
        assert "confidence" in data
        assert data["confidence"] in ("high", "medium", "low")

    @pytest.mark.parametrize("ticker", CORE)
    def test_core_high_confidence(self, ticker: str) -> None:
        """Every core company must return high confidence."""
        if not _db_seeded:
            pytest.skip("No seed data — CI environment")
        data = client.get(f"/v1/company/context?ticker={ticker}").json()
        assert data["confidence"] == "high", f"{ticker} confidence={data['confidence']}"

    @pytest.mark.parametrize("ticker", PEER)
    def test_peer_acceptable_confidence(self, ticker: str) -> None:
        """Peer companies: high normally, medium if no recent insider (legitimate)."""
        if not _db_seeded:
            pytest.skip("No seed data — CI environment")
        data = client.get(f"/v1/company/context?ticker={ticker}").json()
        conf = data["confidence"]
        if ticker in PEER_NO_INSIDER:
            assert conf == "medium", f"{ticker} expected medium (no recent insider), got {conf}"
        else:
            assert conf == "high", f"{ticker} expected high, got {conf}"

    def test_health(self) -> None:
        """Health endpoint must return ok or degraded."""
        r = client.get("/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] in ("ok", "degraded")
