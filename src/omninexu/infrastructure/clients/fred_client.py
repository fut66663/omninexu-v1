"""FRED API client — macro-economic data from the Federal Reserve.

FRED (Federal Reserve Economic Data) provides free access to 800K+
US and international economic time series.  This client focuses on
five core indicators for the macro signal layer.

API docs: https://fred.stlouisfed.org/docs/api/fred/

Free API key registration (required):
    https://fred.stlouisfed.org/docs/api/api_key.html

Usage::

    client = FredClient(api_key="...")
    data = client.get_series("FEDFUNDS")
    # → [{"date": "2026-01-01", "value": 5.5}, ...]
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests

from omninexu.config.settings import settings
from omninexu.observability import get_logger

logger = get_logger(__name__)

FRED_API_BASE = "https://api.stlouisfed.org/fred"

# ── Core series (Phase 1) ──────────────────────────────────────

CORE_SERIES: dict[str, dict[str, str]] = {
    "FEDFUNDS": {
        "name": "Federal Funds Rate",
        "unit": "%",
        "frequency": "monthly",
        "description": "Effective federal funds rate — key policy rate",
    },
    "CPIAUCSL": {
        "name": "Consumer Price Index (All Urban)",
        "unit": "index",
        "frequency": "monthly",
        "description": "CPI-U seasonally adjusted — inflation benchmark",
    },
    "GDP": {
        "name": "Gross Domestic Product",
        "unit": "billions_usd",
        "frequency": "quarterly",
        "description": "Real GDP — overall economic output",
    },
    "UNRATE": {
        "name": "Unemployment Rate",
        "unit": "%",
        "frequency": "monthly",
        "description": "Civilian unemployment rate",
    },
    "DGS10": {
        "name": "10-Year Treasury Yield",
        "unit": "%",
        "frequency": "daily",
        "description": "Market-implied risk-free rate anchor",
    },
}


class FredClient:
    """FRED API client.

    Args:
        api_key: 32-char FRED API key.  If omitted, reads from
            ``FRED_API_KEY`` env var / settings.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else settings.fred_api_key
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "OmniNexu/0.5"

    # ── public API ──────────────────────────────────────────────

    def is_configured(self) -> bool:
        """Return True if a FRED API key is available."""
        return bool(self.api_key and len(self.api_key) == 32)

    def get_series(
        self,
        series_id: str,
        *,
        limit: int = 0,
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        """Fetch observations for *series_id*.

        Args:
            series_id: FRED series identifier (e.g. ``"FEDFUNDS"``).
            limit: Max observations (0 = all available).
            sort_order: ``"asc"`` or ``"desc"`` (default: newest first).

        Returns:
            List of ``{"date": str, "value": float}`` dicts.
            Returns empty list when the client is not configured or
            the series is not found.
        """
        if not self.is_configured():
            logger.warning(f"FRED: {series_id} skipped — no API key configured")
            return []

        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": sort_order,
        }
        if limit > 0:
            params["limit"] = limit

        try:
            resp = self._session.get(
                f"{FRED_API_BASE}/series/observations",
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            payload = resp.json()
            observations = payload.get("observations", [])
            return [
                {
                    "date": obs["date"],
                    "value": float(obs["value"]) if obs["value"] != "." else 0.0,
                }
                for obs in observations
            ]
        except requests.RequestException as exc:
            logger.error(f"FRED: {series_id} request failed — {exc}")
            return []
        except (KeyError, ValueError, TypeError) as exc:
            logger.error(f"FRED: {series_id} parse error — {exc}")
            return []

    def get_latest(self, series_id: str) -> dict[str, Any] | None:
        """Get the most recent observation for *series_id*."""
        data = self.get_series(series_id, limit=1, sort_order="desc")
        return data[0] if data else None

    def get_core_snapshot(self) -> dict[str, Any]:
        """Get the latest value for all five core series.

        Returns a dict keyed by series_id, each value is
        ``{"date", "value", "name", "unit"}`` or None on failure.
        """
        snapshot: dict[str, Any] = {
            "_fetched_at": datetime.now(UTC).isoformat(),
        }
        for sid, meta in CORE_SERIES.items():
            latest = self.get_latest(sid)
            if latest:
                snapshot[sid] = {**latest, "name": meta["name"], "unit": meta["unit"]}
            else:
                snapshot[sid] = None
        return snapshot
