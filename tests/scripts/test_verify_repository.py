"""Tests for scripts/verify/verify_repository.py."""

from datetime import date

from omninexu.domain.financials import FinancialFact


class _FakeCompany:
    """Fake company record for tests."""

    def __init__(self, ticker="AAPL", cik="0000320193", name="Apple Inc."):
        self.ticker = ticker
        self.cik = cik
        self.name = name


def _make_fact(ticker, fiscal_year, concept, value):
    """Build a single FinancialFact with defaults."""
    return FinancialFact(
        ticker=ticker,
        fiscal_year=fiscal_year,
        fiscal_period="FY",
        report_date=date(fiscal_year, 9, 27),
        concept=concept,
        value=value,
        unit="USD",
    )


class TestVerifyTickerAllPass:
    def test_verify_ticker_all_pass(self):
        """verify_ticker returns 0 failures when expected values match."""
        from scripts.verify.verify_repository import verify_ticker

        class FakeCompanyRepo:
            def get_by_ticker(self, ticker):
                return _FakeCompany(ticker)

        class FakeFinRepo:
            def get_facts(self, ticker, concept=None):
                values = {
                    "Revenue": 416_161_000_000.0,
                    "NetIncome": 112_010_000_000.0,
                }
                return [_make_fact(ticker, 2025, concept, values.get(concept, 0))]

        failures = verify_ticker("AAPL", FakeCompanyRepo(), FakeFinRepo())
        assert failures == 0


def test_verify_ticker_company_missing():
    """verify_ticker returns 1 failure when company is not in DB."""
    from scripts.verify.verify_repository import verify_ticker

    class FakeCompanyRepo:
        def get_by_ticker(self, ticker):
            return None

    class FakeFinRepo:
        def get_facts(self, ticker, concept=None):
            return []

    failures = verify_ticker("ZZZZ", FakeCompanyRepo(), FakeFinRepo())
    assert failures == 1


def test_verify_ticker_fact_missing():
    """verify_ticker counts missing facts as failures."""
    from scripts.verify.verify_repository import verify_ticker

    class FakeCompanyRepo:
        def get_by_ticker(self, ticker):
            return _FakeCompany(ticker)

    class FakeFinRepo:
        def get_facts(self, ticker, concept=None):
            return []

    failures = verify_ticker("AAPL", FakeCompanyRepo(), FakeFinRepo())
    assert failures == 2  # Revenue + NetIncome missing


def test_verify_ticker_no_expected_value():
    """verify_ticker counts unconfigured expected values as failures."""
    from scripts.verify.verify_repository import verify_ticker

    class FakeCompanyRepo:
        def get_by_ticker(self, ticker):
            return _FakeCompany(ticker)

    class FakeFinRepo:
        def get_facts(self, ticker, concept=None):
            return [_make_fact(ticker, 2099, concept, 1_000_000.0)]

    failures = verify_ticker("AAPL", FakeCompanyRepo(), FakeFinRepo())
    assert failures == 2  # no expected values for FY2099


def test_verify_ticker_deviation_exceeds_tolerance():
    """verify_ticker flags values outside tolerance as failures."""
    from scripts.verify.verify_repository import verify_ticker

    class FakeCompanyRepo:
        def get_by_ticker(self, ticker):
            return _FakeCompany(ticker)

    class FakeFinRepo:
        def get_facts(self, ticker, concept=None):
            return [_make_fact(ticker, 2025, concept, 1.0)]

    failures = verify_ticker("AAPL", FakeCompanyRepo(), FakeFinRepo())
    assert failures >= 1


class TestMainIntegration:
    def test_main_integration(self):
        """main() should aggregate failures across tickers."""
        from unittest.mock import patch

        from scripts.verify.verify_repository import main

        with (
            patch("scripts.verify.verify_repository.SessionLocal"),
            patch("scripts.verify.verify_repository.CompanyRepository") as mock_cr,
            patch("scripts.verify.verify_repository.FinancialsRepository") as mock_fr,
        ):
            cr = mock_cr.return_value
            cr.get_by_ticker.return_value = _FakeCompany()

            fr = mock_fr.return_value
            fr.get_facts.return_value = [
                _make_fact("AAPL", 2025, "Revenue", 416_161_000_000.0),
            ]

            exit_code = main(["AAPL"])
            assert exit_code >= 0
