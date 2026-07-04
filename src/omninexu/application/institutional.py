"""Build institutional holdings summary from repository data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from omninexu.infrastructure.repositories.institutional_repo import (
    InstitutionalRepository,
)


def build_institutional_summary(
    ticker: str, repo: InstitutionalRepository
) -> Any:
    """Build an InstitutionalSummary with Top 10 holders sorted by value.

    Returns None when no holdings data exists in the database.
    """
    from omninexu.api.schemas.company import InstitutionalHolder, InstitutionalSummary  # noqa: E402

    holdings = repo.get_holdings(ticker)
    if not holdings:
        return None

    top_holders = []
    for h in holdings[:10]:
        top_holders.append(
            InstitutionalHolder(
                name=h.reporting_manager,
                shares=int(h.shares) if h.shares is not None else 0,
                value=h.value or 0.0,
                source_filing_url=_filing_url(h.source_filing),
            )
        )

    as_of_date = holdings[0].report_date if holdings else None
    return InstitutionalSummary(top_holders=top_holders, as_of_date=as_of_date)


def _filing_url(accession: str | None) -> str:
    """Convert an accession number to a SEC filing URL."""
    if not accession:
        return ""
    cleaned = accession.replace("-", "")
    return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cleaned}&type=13F-HR"
