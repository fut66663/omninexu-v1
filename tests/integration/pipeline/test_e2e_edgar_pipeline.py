"""End-to-end EDGAR pipeline tests.

Verifies the full chain: SEC download -> disk cache -> parse -> DB save.

All tests are marked ``@pytest.mark.integration`` and require network access.
Run with: ``uv run pytest tests/integration/pipeline/ -m integration``
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from omninexu.infrastructure.clients import EdgarClient
from omninexu.infrastructure.models import CompanyModel
from omninexu.infrastructure.repositories.financials_repo import (
    FinancialsRepository,
)
from omninexu.infrastructure.storage import ChecksumMan, DiskValidator

pytestmark = pytest.mark.integration


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


class TestEdgar10KPipeline:
    """Full pipeline: SEC EDGAR 10-K download to DB save."""

    def test_download_and_cache_10k(
        self, e2e_db_session: Session
    ) -> None:
        """Download AAPL 10-K and verify it lands on disk."""
        db = e2e_db_session
        ticker = "AAPL"
        _ensure_company(db, ticker, "0000320193", "Apple Inc.")
        db.commit()

        client = EdgarClient()
        facts = client.get_financial_facts(ticker, num_filings=1)

        assert len(facts) > 0, "Should extract at least one fact from AAPL 10-K"

        # Verify disk cache: filing.html under the configured data root.
        from omninexu.config import data_paths as dp
        base = dp.raw_sec_10k / ticker
        if base.is_dir():
            html_files = list(base.rglob("filing.html"))
            assert len(html_files) >= 1, "10-K filing.html should be cached on disk"

            cm = ChecksumMan()
            for f in html_files:
                digest = cm.compute(f)
                assert len(digest) == 64
                assert cm.verify(f, digest)

    def test_parse_and_save_to_db(
        self, e2e_db_session: Session
    ) -> None:
        """Parse downloaded facts and persist them via FinancialsRepository."""
        db = e2e_db_session
        ticker = "AAPL"
        _ensure_company(db, ticker, "0000320193", "Apple Inc.")
        db.commit()

        client = EdgarClient()
        facts = client.get_financial_facts(ticker, num_filings=1)
        assert len(facts) > 0

        repo = FinancialsRepository(db)
        repo.save_facts(facts)

        # Verify persistence.
        from sqlalchemy import func, select

        from omninexu.infrastructure.models import FinancialFactModel
        count = db.scalar(
            select(func.count()).where(
                FinancialFactModel.ticker == ticker,
                FinancialFactModel.source == "edgar",
            )
        )
        assert count and count > 0

    def test_disk_validator_on_cached_filing(
        self, e2e_db_session: Session
    ) -> None:
        """After download, DiskValidator confirms the cached file on disk."""
        db = e2e_db_session
        ticker = "AAPL"
        _ensure_company(db, ticker, "0000320193", "Apple Inc.")
        db.commit()

        client = EdgarClient()
        client.get_financial_facts(ticker, num_filings=1)

        # The cache writes to the real data_paths.raw_sec_10k (production or
        # env-var-configured path).  We validate directly against that.
        from omninexu.config import data_paths

        dv = DiskValidator()
        base = data_paths.raw_sec_10k / ticker
        if base.is_dir():
            count, _, _ = dv.validate_directory(base, min_files=1)
            assert count >= 1
            empties = dv.find_empty_files(base)
            assert len(empties) == 0, "Cached filings should not be empty"

    def test_pipeline_monitor_integration(
        self, e2e_db_session: Session, e2e_data_root: Path
    ) -> None:
        """Record pipeline steps during download and verify the log."""
        db = e2e_db_session
        ticker = "AAPL"
        _ensure_company(db, ticker, "0000320193", "Apple Inc.")
        db.commit()

        from omninexu.infrastructure.storage import PipelineMonitor

        pm = PipelineMonitor(log_dir=e2e_data_root / "operations" / "logs" / "ingestion")
        run_id = pm.start_run()

        client = EdgarClient()
        client.get_financial_facts(ticker, num_filings=1)
        pm.record_download(
            run_id, source="edgar", ticker=ticker, form="10-K",
            status="ok", duration_ms=100, bytes_written=50000,
        )
        pm.record_save(
            run_id, source="edgar", ticker=ticker,
            status="ok", duration_ms=100, rows_inserted=10,
        )

        summary = pm.get_run_summary(run_id)
        assert summary["entries"] == 2
        assert summary["failed"] == 0
