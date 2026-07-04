"""End-to-end SimFin pipeline tests.

Verifies: local CSV -> SimFinAdapter -> FinancialFact domain objects -> DB save.

These tests require SimFin CSV files at D:/OmniNexuData/raw/simfin/.
Run with: ``uv run pytest tests/integration/pipeline/ -m integration``
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from omninexu.infrastructure.clients.simfin_adapter import SimFinAdapter
from omninexu.infrastructure.models import CompanyModel
from omninexu.infrastructure.repositories.financials_repo import (
    FinancialsRepository,
)

pytestmark = pytest.mark.integration

_SIMFIN_DATA = Path("D:/OmniNexuData/raw/simfin")


def _ensure_company(db: Session, ticker: str, cik: str, name: str) -> CompanyModel:
    """Get-or-create a Company row."""
    from sqlalchemy import select as sa_select
    row = db.execute(
        sa_select(CompanyModel).where(CompanyModel.ticker == ticker.upper())
    ).scalar()
    if row:
        return row
    c = CompanyModel(ticker=ticker.upper(), cik=cik, name=name)
    db.add(c)
    db.flush()
    return c


def _has_simfin_data() -> bool:
    """Check whether local SimFin CSV files exist."""
    return (_SIMFIN_DATA / "us-income-annual.csv").exists()


class TestSimFinPipeline:
    """SimFin CSV ingestion pipeline."""

    def test_adapter_loads_data(
        self, e2e_db_session: Session
    ) -> None:
        """Adapter loads and returns facts for AAPL from local CSVs."""
        if not _has_simfin_data():
            pytest.skip(f"SimFin CSV files not found at {_SIMFIN_DATA}")

        db = e2e_db_session
        _ensure_company(db, "AAPL", "0000320193", "Apple Inc.")
        db.commit()

        adapter = SimFinAdapter(data_dir=str(_SIMFIN_DATA))
        facts = adapter.get_financial_facts("AAPL", start_year=2020)
        assert len(facts) > 0, "Should extract facts for AAPL"

        for f in facts:
            assert f.ticker == "AAPL"
            assert f.concept
            assert f.value is not None
            assert f.fiscal_year >= 2020

    def test_facts_persist_to_db(
        self, e2e_db_session: Session
    ) -> None:
        """Facts from adapter persist via FinancialsRepository."""
        if not _has_simfin_data():
            pytest.skip(f"SimFin CSV files not found at {_SIMFIN_DATA}")

        db = e2e_db_session
        _ensure_company(db, "AAPL", "0000320193", "Apple Inc.")
        db.commit()

        adapter = SimFinAdapter(data_dir=str(_SIMFIN_DATA))
        facts = adapter.get_financial_facts("AAPL", start_year=2023)
        assert len(facts) > 0

        repo = FinancialsRepository(db)
        repo.save_facts(facts)

        from sqlalchemy import func, select

        from omninexu.infrastructure.models import FinancialFactModel
        count = db.scalar(
            select(func.count()).where(
                FinancialFactModel.ticker == "AAPL",
                FinancialFactModel.source == "simfin",
            )
        )
        assert count and count > 0

    def test_multiple_tickers(
        self, e2e_db_session: Session
    ) -> None:
        """Adapter returns distinct facts for each ticker."""
        if not _has_simfin_data():
            pytest.skip(f"SimFin CSV files not found at {_SIMFIN_DATA}")

        db = e2e_db_session
        adapter = SimFinAdapter(data_dir=str(_SIMFIN_DATA))

        for t in ("AAPL", "MSFT"):
            _ensure_company(db, t, f"CIK_{t}", f"{t} Inc.")
            db.commit()
            facts = adapter.get_financial_facts(t, start_year=2023)
            tickers = {f.ticker for f in facts}
            assert t in tickers, f"Should include {t}"
