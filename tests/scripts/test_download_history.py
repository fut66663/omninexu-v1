"""Tests for scripts/download_history.py."""

from datetime import date
from unittest.mock import patch

from omninexu.domain.financials import FinancialFact


def _make_multi_year_facts(ticker: str, years: int = 5) -> list[FinancialFact]:
    """Build Revenue + NetIncome facts for *years* fiscal years."""
    facts: list[FinancialFact] = []
    for i in range(years):
        fy = 2025 - i
        facts.append(FinancialFact(
            ticker=ticker, fiscal_year=fy, fiscal_period="FY",
            report_date=date(fy, 9, 30), concept="Revenue",
            value=400e9 * (0.9 ** i),
        ))
        facts.append(FinancialFact(
            ticker=ticker, fiscal_year=fy, fiscal_period="FY",
            report_date=date(fy, 9, 30), concept="NetIncome",
            value=100e9 * (0.9 ** i),
        ))
    return facts


def test_download_history_saves_multi_year_facts():
    """download_history should fetch and save facts for all tickers."""
    from scripts.ingest.download_history import download_history

    tickers = [("AAPL", "0000320193", "Apple Inc.", "3571")]
    facts = _make_multi_year_facts("AAPL", years=5)

    with (
        patch("scripts.ingest.download_history.EdgarClient") as mock_client_cls,
        patch("scripts.ingest.download_history.SessionLocal"),
        patch("scripts.ingest.download_history.FinancialsRepository") as mock_repo_cls,
        patch("scripts.ingest.download_history.seed_company"),
    ):
        mock_client = mock_client_cls.return_value
        mock_client.get_financial_facts.return_value = facts
        mock_repo = mock_repo_cls.return_value

        results = download_history(tickers, num_filings=5)

        assert results["AAPL"] == len(facts)
        mock_client.get_financial_facts.assert_called_once_with("AAPL", num_filings=5)
        mock_repo.save_facts.assert_called_once_with(facts)


def test_download_history_partial_failure():
    """One ticker failing should not prevent others from succeeding."""
    from scripts.ingest.download_history import download_history

    tickers = [
        ("AAPL", "0000320193", "Apple Inc.", "3571"),
        ("MSFT", "0000789019", "Microsoft Corp", "7372"),
    ]
    aapl_facts = _make_multi_year_facts("AAPL", years=3)

    with (
        patch("scripts.ingest.download_history.EdgarClient") as mock_client_cls,
        patch("scripts.ingest.download_history.SessionLocal"),
        patch("scripts.ingest.download_history.FinancialsRepository"),
        patch("scripts.ingest.download_history.seed_company"),
    ):
        mock_client = mock_client_cls.return_value

        def get_facts(ticker, num_filings=1):
            if ticker == "MSFT":
                raise RuntimeError("SEC rate limit")
            return aapl_facts

        mock_client.get_financial_facts.side_effect = get_facts

        results = download_history(tickers, num_filings=3)

        assert results["AAPL"] == len(aapl_facts)
        assert results["MSFT"] == -1
