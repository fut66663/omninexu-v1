"""API layer tests."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from omninexu.api.main import app
from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure import cache as cache_module
from omninexu.infrastructure.db import get_db
from omninexu.infrastructure.repositories import (
    CompanyRepository,
    FinancialsRepository,
)
from tests.fakes import FakeCache


@pytest.fixture(autouse=True)
def fake_cache(monkeypatch):
    """Replace the global Redis cache with an in-memory FakeCache for API tests."""
    cache = FakeCache()
    monkeypatch.setattr(cache_module, "cache", cache)
    yield cache


def _seed_aapl(db_session):
    """Seed AAPL company and a Revenue fact for API tests."""
    company = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(),
    )
    CompanyRepository(db_session).create_or_update(company)
    FinancialsRepository(db_session).save_facts(
        [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=416_161_000_000.0,
            )
        ]
    )


def test_health_check(client: TestClient, monkeypatch) -> None:
    """Health endpoint returns ok when dependencies are healthy."""
    from omninexu.api.routes import health as health_module

    healthy_cache = FakeCache()
    monkeypatch.setattr(health_module, "cache", healthy_cache)

    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["cache"] == "ok"


def test_health_check_database_failure(client: TestClient, monkeypatch) -> None:
    """Health endpoint reports degraded when the database is unreachable."""
    from omninexu.api.routes import health as health_module

    healthy_cache = FakeCache()
    monkeypatch.setattr(health_module, "cache", healthy_cache)

    mock_db = MagicMock()
    mock_db.execute.side_effect = RuntimeError("DB down")

    def _override_get_db():
        try:
            yield mock_db
        finally:
            mock_db.close()

    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.get("/v1/health")
    finally:
        if original_override is not None:
            app.dependency_overrides[get_db] = original_override
        else:
            del app.dependency_overrides[get_db]

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "error"
    assert data["cache"] == "ok"


def test_health_check_cache_failure(client: TestClient, monkeypatch) -> None:
    """Health endpoint reports degraded when the cache is unreachable."""
    from omninexu.api.routes import health as health_module

    failing_cache = FakeCache()

    def _failing_ping():
        raise RuntimeError("Redis down")

    failing_cache.client.ping = _failing_ping
    monkeypatch.setattr(health_module, "cache", failing_cache)

    response = client.get("/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "ok"
    assert data["cache"] == "error"


def test_root_endpoint(client: TestClient) -> None:
    """Root endpoint returns service identity."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "OmniNexu"


def test_company_context_aapl(client: TestClient, db_session) -> None:
    """GET /v1/company/context?ticker=AAPL returns real revenue data."""
    _seed_aapl(db_session)

    response = client.get("/v1/company/context?ticker=AAPL")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["cik"] == "0000320193"
    assert "fundamentals" in data
    assert data["fundamentals"]["revenue"]["value"] == 416_161_000_000.0
    assert data["fundamentals"]["revenue"]["unit"] == "USD"
    assert data["fundamentals"]["revenue"]["fiscal_year"] == 2025


def test_company_context_exclude_peers(client: TestClient, db_session) -> None:
    """GET /v1/company/context?ticker=AAPL&include_peers=false returns no peer comparison."""
    _seed_aapl(db_session)

    response = client.get("/v1/company/context?ticker=AAPL&include_peers=false")

    assert response.status_code == 200
    data = response.json()
    assert data["peer_comparison"] is None


def test_company_context_include_peers(client: TestClient, db_session) -> None:
    """GET /v1/company/context?ticker=AAPL&include_peers=true returns peer comparison if available."""
    _seed_aapl(db_session)

    response = client.get("/v1/company/context?ticker=AAPL&include_peers=true")

    assert response.status_code == 200
    data = response.json()
    # AAPL has no GICS sub-industry in the seed, so peers are unavailable.
    assert data["peer_comparison"] is None


def test_company_context_response_schema(client: TestClient, db_session) -> None:
    """Response conforms to CompanyContextResponse schema."""
    _seed_aapl(db_session)

    response = client.get("/v1/company/context?ticker=AAPL")

    assert response.status_code == 200
    data = response.json()
    assert "ticker" in data
    assert "cik" in data
    assert "name" in data
    assert "fundamentals" in data
    assert "longitudinal" in data
    assert "peer_comparison" in data
    assert "sources" in data
    assert "confidence" in data


def test_company_context_not_found(client: TestClient) -> None:
    """Unknown ticker returns 404 with OMN-1101 error code."""
    response = client.get("/v1/company/context?ticker=INVALID_TICKER_XYZ")

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "OMN-1101"
    assert "message" in data["error"]
