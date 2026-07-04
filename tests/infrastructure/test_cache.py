"""Tests for cache integration."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from omninexu.application.company_context import CompanyContextService
from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.db import Base
from omninexu.infrastructure.repositories import (
    CompanyRepository,
    FinancialsRepository,
)
from tests.fakes import FakeCache


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session for cache tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed_aapl(db_session, revenue_value: float = 416_161_000_000.0):
    """Seed AAPL company and a single Revenue fact."""
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
                value=revenue_value,
            )
        ]
    )


def test_fake_cache_stores_and_retrieves_json():
    """FakeCache should store and retrieve JSON values without Redis."""
    fake_cache = FakeCache()
    fake_cache.set_json("test:cache:key", {"value": 42}, ttl=3600)

    result = fake_cache.get_json("test:cache:key")

    assert result == {"value": 42}


def test_build_context_uses_cache_on_second_call(db_session):
    """Second call should return cached result without re-reading changed DB data."""
    _seed_aapl(db_session, revenue_value=100.0)
    fake_cache = FakeCache()
    service = CompanyContextService(db_session, cache_backend=fake_cache)

    context_first = service.build_context("AAPL")
    assert context_first["fundamentals"]["revenue"]["value"] == 100.0

    # Update the underlying DB value after the first call.
    FinancialsRepository(db_session).save_facts(
        [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=200.0,
            )
        ]
    )

    context_second = service.build_context("AAPL")

    assert context_second["fundamentals"]["revenue"]["value"] == 100.0
    assert context_second["ticker"] == context_first["ticker"]
    assert context_second["cik"] == context_first["cik"]


def test_build_context_invalidates_cache(db_session):
    """Invalidating cache should force a fresh read from the DB."""
    _seed_aapl(db_session, revenue_value=100.0)
    fake_cache = FakeCache()
    service = CompanyContextService(db_session, cache_backend=fake_cache)

    context_first = service.build_context("AAPL")
    service.invalidate_cache("AAPL")

    FinancialsRepository(db_session).save_facts(
        [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=200.0,
            )
        ]
    )

    context_second = service.build_context("AAPL")

    assert context_second["fundamentals"]["revenue"]["value"] == 200.0
    assert context_first["fundamentals"]["revenue"]["value"] == 100.0


class TestCacheWithMockedRedis:
    """Tests for the real Cache class using a mocked Redis client."""

    @pytest.fixture
    def mock_client(self):
        """Return a fresh MagicMock redis client."""
        from unittest.mock import MagicMock

        return MagicMock()

    @pytest.fixture
    def cache(self, mock_client):
        """Return a Cache instance wired to the mocked client."""
        from omninexu.infrastructure.cache import Cache

        instance = Cache(redis_url="redis://localhost:6379/0")
        instance.client = mock_client
        return instance

    def test_get_returns_string_value(self, cache, mock_client):
        """get should return a string value directly."""
        mock_client.get.return_value = "raw-value"
        assert cache.get("key") == "raw-value"
        mock_client.get.assert_called_once_with("key")

    def test_get_decodes_bytes_value(self, cache, mock_client):
        """get should decode bytes values to UTF-8."""
        mock_client.get.return_value = b"bytes-value"
        assert cache.get("key") == "bytes-value"

    def test_get_json_returns_none_when_missing(self, cache, mock_client):
        """get_json should return None for missing keys."""
        mock_client.get.return_value = None
        assert cache.get_json("key") is None

    def test_get_json_parses_string_value(self, cache, mock_client):
        """get_json should parse JSON strings."""
        mock_client.get.return_value = '{"value": 42}'
        assert cache.get_json("key") == {"value": 42}

    def test_get_json_parses_bytes_value(self, cache, mock_client):
        """get_json should parse JSON bytes."""
        mock_client.get.return_value = b'{"value": 42}'
        assert cache.get_json("key") == {"value": 42}

    def test_set_stores_value_with_ttl(self, cache, mock_client):
        """set should forward value and TTL to Redis."""
        cache.set("key", "value", ttl=120)
        mock_client.set.assert_called_once_with("key", "value", ex=120)

    def test_set_json_serializes_value(self, cache, mock_client):
        """set_json should serialize dicts to JSON before storing."""
        cache.set_json("key", {"value": 42}, ttl=60)
        mock_client.set.assert_called_once()
        call_args = mock_client.set.call_args
        assert call_args.kwargs == {"ex": 60}
        assert call_args.args[0] == "key"
        assert '"value": 42' in call_args.args[1]

    def test_delete_removes_key(self, cache, mock_client):
        """delete should forward the delete call to Redis."""
        cache.delete("key")
        mock_client.delete.assert_called_once_with("key")
