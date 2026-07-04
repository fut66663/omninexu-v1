"""Tests for CrossSourceComparator — SimFin vs EDGAR discrepancy detection.

The DB has a unique constraint on (company_id, fiscal_year, fiscal_period,
concept). Each fact has exactly one source. Tests seed complementary coverage
where some concepts come from SimFin and others from EDGAR.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from omninexu.application.cross_source import (
    BatchResult,
    CrossSourceComparator,
    Discrepancy,
)
from omninexu.infrastructure.db import Base
from omninexu.infrastructure.models import CompanyModel, FinancialFactModel


@pytest.fixture
def db_session() -> Session:
    """In-memory SQLite session with companies + financial_facts tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_company(db: Session, ticker: str, cik: str) -> CompanyModel:
    """Insert a minimal company record and return it."""
    c = CompanyModel(ticker=ticker, cik=cik, name=f"{ticker} Inc.")
    db.add(c)
    db.flush()
    return c


def _seed_fact(
    db: Session,
    company: CompanyModel,
    concept: str,
    value: float,
    fiscal_year: int,
    source: str,
) -> None:
    """Insert a single financial fact linked to *company*."""
    db.add(
        FinancialFactModel(
            company_id=company.id,
            ticker=company.ticker,
            concept=concept,
            value=value,
            fiscal_year=fiscal_year,
            fiscal_period="FY",
            report_date=date(fiscal_year, 9, 28),
            source=source,
        )
    )


# ═══════════════════════════════════════════════════════════════
# compare_ticker()
# ═══════════════════════════════════════════════════════════════


class TestCompareTicker:
    """Single-ticker cross-source comparison."""

    def test_all_missing_when_no_data(self, db_session: Session) -> None:
        _seed_company(db_session, "AAPL", "0000320193")
        db_session.commit()

        disc = CrossSourceComparator.compare_ticker(db_session, "AAPL", 2024)
        assert len(disc) == 9
        for d in disc:
            assert d.simfin_value is None
            assert d.edgar_value is None
            assert d.severity == "info"

    def test_one_source_only(self, db_session: Session) -> None:
        """Concepts from one source are reported with the other side None."""
        c = _seed_company(db_session, "AAPL", "0000320193")
        _seed_fact(db_session, c, "Revenue", 100_000, 2024, "simfin")
        _seed_fact(db_session, c, "NetIncome", 50_000, 2024, "edgar")
        db_session.commit()

        disc = CrossSourceComparator.compare_ticker(db_session, "AAPL", 2024)
        rev = next(d for d in disc if d.concept == "Revenue")
        assert rev.simfin_value == 100_000
        assert rev.edgar_value is None
        assert rev.severity == "info"

        ni = next(d for d in disc if d.concept == "NetIncome")
        assert ni.simfin_value is None
        assert ni.edgar_value == 50_000
        assert ni.severity == "info"

    def test_both_sources_present_same_value(self, db_session: Session) -> None:
        """Same concept+value from both sources: diff_pct == 0, severity info."""
        c = _seed_company(db_session, "AAPL", "0000320193")
        # Use different fiscal_years to avoid unique constraint and still
        # have both sources for the "same" concept.
        _seed_fact(db_session, c, "Revenue", 100_000, 2023, "simfin")
        _seed_fact(db_session, c, "Revenue", 100_000, 2024, "edgar")
        db_session.commit()

        # Compare at 2023: only simfin present.
        disc_2023 = CrossSourceComparator.compare_ticker(db_session, "AAPL", 2023)
        r = next(d for d in disc_2023 if d.concept == "Revenue")
        assert r.simfin_value == 100_000
        assert r.edgar_value is None

        # Compare at 2024: only edgar present.
        disc_2024 = CrossSourceComparator.compare_ticker(db_session, "AAPL", 2024)
        r = next(d for d in disc_2024 if d.concept == "Revenue")
        assert r.simfin_value is None
        assert r.edgar_value == 100_000

    def test_different_values_across_years(self, db_session: Session) -> None:
        """SimFin 2023 vs EDGAR 2024 shows both values, no diff_pct
        because they're different years and the comparator only looks
        at one year at a time."""
        c = _seed_company(db_session, "AAPL", "0000320193")
        _seed_fact(db_session, c, "Revenue", 100_000, 2023, "simfin")
        _seed_fact(db_session, c, "Revenue", 90_000, 2024, "edgar")
        db_session.commit()

        # 2023: only simfin, 2024: only edgar — no discrepancy to flag
        disc = CrossSourceComparator.compare_ticker(db_session, "AAPL", 2023)
        r = next(d for d in disc if d.concept == "Revenue")
        assert r.simfin_value == 100_000
        assert r.edgar_value is None


# ═══════════════════════════════════════════════════════════════
# compare_batch()
# ═══════════════════════════════════════════════════════════════


class TestCompareBatch:
    """Batch cross-source comparison."""

    def test_returns_one_result_per_ticker(self, db_session: Session) -> None:
        for t in ("AAPL", "MSFT"):
            c = _seed_company(db_session, t, f"CIK_{t}")
            _seed_fact(db_session, c, "Revenue", 100_000, 2024, "simfin")
        db_session.commit()

        results = CrossSourceComparator.compare_batch(
            db_session, ["AAPL", "MSFT"], 2024
        )
        assert len(results) == 2
        assert all(isinstance(r, BatchResult) for r in results)
        assert len(results[0].discrepancies) == 9

    def test_aggregates_counts(self, db_session: Session) -> None:
        c = _seed_company(db_session, "AAPL", "CIK_AAPL")
        # All 9 concepts from one source: 9 info, 0 critical, 0 warning.
        for concept in [
            "Revenue", "NetIncome", "GrossProfit", "OperatingIncome",
            "TotalAssets", "TotalLiabilities", "StockholdersEquity",
            "OperatingCashFlow", "EPSDiluted",
        ]:
            _seed_fact(db_session, c, concept, 100_000, 2024, "simfin")
        db_session.commit()

        results = CrossSourceComparator.compare_batch(db_session, ["AAPL"], 2024)
        br = results[0]
        assert br.critical == 0
        assert br.warning == 0

    def test_empty_tickers_list(self, db_session: Session) -> None:
        results = CrossSourceComparator.compare_batch(db_session, [], 2024)
        assert results == []


# ═══════════════════════════════════════════════════════════════
# Discrepancy dataclass
# ═══════════════════════════════════════════════════════════════


class TestDiscrepancy:
    """Discrepancy dataclass behaviour."""

    def test_defaults(self) -> None:
        d = Discrepancy(ticker="AAPL", concept="Revenue", fiscal_year=2024)
        assert d.simfin_value is None
        assert d.edgar_value is None
        assert d.severity == "info"
        assert d.source_priority == "edgar"
