"""FRED client stub (Phase 1)."""

from omninexu.config.settings import settings
from omninexu.observability import get_logger

logger = get_logger(__name__)


class FredClient:
    """FRED API client (stub for Phase 1)."""

    def __init__(self, api_key: str | None = settings.fred_api_key):
        self.api_key = api_key

    def is_configured(self) -> bool:
        """Return True if a FRED API key has been provided."""
        return self.api_key is not None and self.api_key != ""

    def get_series(self, series_id: str) -> None:
        """Not implemented in Phase 0."""
        logger.info(f"FRED client called for {series_id}, but not configured")
        return None
