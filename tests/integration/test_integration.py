"""End-to-end integration tests for the company context API."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure import cache as cache_module
from omninexu.infrastructure.repositories import (
    CompanyRepository,
    FinancialsRepository,
)
from tests.fakes import FakeCache


@pytest.fixture(autouse=True)
def fake_cache(monkeypatch):
    """Replace the global Redis cache with an in-memory FakeCache for integration tests."""
    cache = FakeCache()
    monkeypatch.setattr(cache_module, "cache", cache)
    yield cache


def _seed_aapl(db_session):
    """Seed AAPL company and a Revenue fact for integration tests."""
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


def test_integration_company_context_aapl(client: TestClient, db_session):
    """GET /v1/company/context?ticker=AAPL should return real revenue data."""
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


def test_integration_company_context_invalid_ticker(client: TestClient):
    """Invalid ticker should return 404 with OMN-1101 error code."""
    response = client.get("/v1/company/context?ticker=INVALID")

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "OMN-1101"
    assert "message" in data["error"]
