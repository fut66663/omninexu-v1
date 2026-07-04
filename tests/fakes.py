"""Test fakes for external dependencies."""

import json
from typing import Any

from omninexu.domain.financials import FinancialFact


class FakeDataSource:
    """In-memory data source implementing ``CompanyDataSource``.

    Replace ``EdgarClient`` in unit tests to avoid network calls.
    Pass custom ``company_info`` or ``financial_facts`` to control
    the data returned to the service under test.
    """

    def __init__(
        self,
        company_info: dict[str, Any] | None = None,
        financial_facts: list[FinancialFact] | None = None,
    ):
        self.company_info = company_info or {
            "ticker": "AAPL",
            "cik": "0000320193",
            "name": "Apple Inc.",
            "sic": "3571",
        }
        self.financial_facts = financial_facts or []

    def get_company_info(self, ticker: str) -> dict[str, Any]:
        return {**self.company_info, "ticker": ticker.upper()}

    def get_financial_facts(self, ticker: str) -> list[FinancialFact]:
        return self.financial_facts


class FailingDataSource:
    """Data source that raises a domain error on every call.

    Used to verify that the application layer correctly propagates
    errors from the data source.
    """

    def __init__(self, error: Exception | None = None):
        from omninexu.observability import TickerNotFoundError

        self.error = error or TickerNotFoundError("TEST")

    def get_company_info(self, ticker: str) -> dict[str, Any]:
        raise self.error

    def get_financial_facts(self, ticker: str) -> list[FinancialFact]:
        raise self.error


class FakeCache:
    """In-memory cache implementing the same interface as Cache.

    Use this in unit tests to avoid requiring a running Redis server.
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self.client = _FakeRedisClient()

    def get(self, key: str) -> str | None:
        """Return the raw cached value, or None if missing."""
        return self._data.get(key)

    def get_json(self, key: str) -> Any | None:
        """Return the cached JSON value, or None if missing."""
        value = self.get(key)
        if value is None:
            return None
        return json.loads(value)

    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        """Store a raw value. TTL is ignored in the fake implementation."""
        del ttl  # Fake cache does not implement expiration.
        self._data[key] = value

    def set_json(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Store a JSON-serializable value."""
        self.set(key, json.dumps(value, default=str), ttl=ttl)

    def delete(self, key: str) -> None:
        """Remove a key from the cache."""
        self._data.pop(key, None)

    def clear(self) -> None:
        """Remove all cached values."""
        self._data.clear()


class _FakeRedisClient:
    """Minimal Redis client stand-in for health checks."""

    def __init__(self) -> None:
        self.ping = lambda: True

