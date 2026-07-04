"""Tests for data seeding utilities."""

from unittest.mock import MagicMock, patch

from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact
from omninexu.jobs.seed import seed_company, seed_company_financials


def test_seed_company_creates_company():
    """seed_company should persist a company record via CompanyRepository."""
    mock_session = MagicMock()

    with patch("omninexu.jobs.seed.CompanyRepository") as mock_repo_class:
        mock_repo = mock_repo_class.return_value
        mock_repo.create_or_update.return_value = Company(
            ticker="AAPL",
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(sic_code="3571"),
        )

        result = seed_company(mock_session, "AAPL", "0000320193", "Apple Inc.", "3571")

        assert result.ticker == "AAPL"
        mock_repo_class.assert_called_once_with(mock_session)
        mock_repo.create_or_update.assert_called_once()
        created = mock_repo.create_or_update.call_args[0][0]
        assert created.ticker == "AAPL"
        assert created.cik == "0000320193"
        assert created.industry.sic_code == "3571"


def test_seed_company_financials_saves_facts():
    """seed_company_financials should fetch facts and save them."""
    mock_session = MagicMock()
    fact = FinancialFact(
        ticker="AAPL",
        fiscal_year=2025,
        fiscal_period="FY",
        report_date=None,  # Not used by the mock repo.
        concept="Revenue",
        value=416_161_000_000.0,
    )
    mock_edgar = MagicMock()
    mock_edgar.get_financial_facts.return_value = [fact]

    with patch("omninexu.jobs.seed.FinancialsRepository") as mock_repo_class:
        mock_repo = mock_repo_class.return_value

        seed_company_financials(mock_session, "AAPL", data_source=mock_edgar)

        mock_edgar.get_financial_facts.assert_called_once_with("AAPL")
        mock_repo_class.assert_called_once_with(mock_session)
        mock_repo.save_facts.assert_called_once_with([fact])


def test_seed_company_financials_no_facts_warning():
    """seed_company_financials should not call save_facts when no facts are returned."""
    mock_session = MagicMock()
    mock_edgar = MagicMock()
    mock_edgar.get_financial_facts.return_value = []

    with patch("omninexu.jobs.seed.FinancialsRepository") as mock_repo_class:
        mock_repo = mock_repo_class.return_value

        seed_company_financials(mock_session, "AAPL", data_source=mock_edgar)

        mock_repo.save_facts.assert_not_called()


def test_seed_company_financials_defaults_client():
    """seed_company_financials should create an EdgarClient when none is provided."""
    mock_session = MagicMock()

    with (
        patch("omninexu.jobs.seed.EdgarClient") as mock_edgar_class,
        patch("omninexu.jobs.seed.FinancialsRepository") as mock_repo_class,
    ):
        mock_edgar = mock_edgar_class.return_value
        mock_edgar.get_financial_facts.return_value = []

        seed_company_financials(mock_session, "AAPL")

        mock_edgar_class.assert_called_once()
        mock_repo_class.assert_called_once_with(mock_session)
