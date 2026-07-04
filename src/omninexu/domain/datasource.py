"""Data source protocol and domain exceptions.

Defines the abstraction boundary between the application layer and
external financial data providers (SEC EDGAR, Bloomberg, etc.).

Replace or upgrade the underlying data source by implementing
:class:`CompanyDataSource` — zero application-layer changes required.
"""

from typing import Any, Protocol

from omninexu.domain.financials import FinancialFact


class CompanyDataSource(Protocol):
    """Protocol that any financial data provider must implement.

    This is the **only** interface the application layer knows about.
    Infrastructure adapters (e.g. ``EdgarClient``) implement this
    protocol and convert provider-specific details into domain types.
    """

    def get_company_info(self, ticker: str) -> dict[str, Any]:
        """Return basic company metadata.

        Returns:
            dict with keys ``ticker``, ``cik``, ``name``, ``sic``.
        """
        ...

    def get_financial_facts(self, ticker: str) -> list[FinancialFact]:
        """Return financial facts from the latest SEC filing.

        Returns:
            List of :class:`FinancialFact` objects.
        """
        ...
