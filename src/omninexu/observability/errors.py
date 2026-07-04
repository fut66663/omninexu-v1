"""Application exception hierarchy."""


class OmniNexuError(Exception):
    """Base application error."""

    code: str = "OMN-1000"
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.detail
        super().__init__(self.detail)


class TickerNotFoundError(OmniNexuError):
    """Requested ticker not found in universe."""

    code = "OMN-1101"
    status_code = 404
    detail = "Ticker not found in our universe"


class FinancialDataNotFoundError(OmniNexuError):
    """No financial data available for ticker."""

    code = "OMN-1201"
    status_code = 404
    detail = "Financial data not found for this company"


class EdgarRateLimitError(OmniNexuError):
    """SEC EDGAR rate limit exceeded."""

    code = "OMN-1301"
    status_code = 429
    detail = "SEC EDGAR rate limit exceeded, please retry later"


class X402ConfigError(OmniNexuError):
    """OMN-2002: x402 configuration error (e.g. X402_ENABLED=true but X402_PAY_TO empty)."""

    code = "OMN-2002"
    status_code = 500
    detail = "Payment configuration error"
