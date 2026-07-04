"""Tests for CoverageReport — disk vs. database ticker coverage comparison."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from omninexu.infrastructure.db import Base
from omninexu.infrastructure.models import CompanyModel
from omninexu.infrastructure.storage.coverage_report import CoverageReport


@pytest.fixture
def db_session() -> Session:
    """Return a fresh in-memory SQLite session with the companies table."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ═══════════════════════════════════════════════════════════════
# count_tickers()
# ═══════════════════════════════════════════════════════════════


class TestCountTickers:
    """Ticker directory counting."""

    def test_counts_uppercase_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "AAPL").mkdir()
        (tmp_path / "MSFT").mkdir()
        (tmp_path / "GOOGL").mkdir()
        assert CoverageReport.count_tickers(tmp_path) == 3

    def test_ignores_lowercase_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "AAPL").mkdir()
        (tmp_path / "data").mkdir()
        assert CoverageReport.count_tickers(tmp_path) == 1

    def test_ignores_files(self, tmp_path: Path) -> None:
        (tmp_path / "AAPL").mkdir()
        (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
        assert CoverageReport.count_tickers(tmp_path) == 1

    def test_ignores_long_names(self, tmp_path: Path) -> None:
        (tmp_path / "AAPL").mkdir()
        (tmp_path / "TOOLONGNAME").mkdir()
        assert CoverageReport.count_tickers(tmp_path) == 1

    def test_nonexistent_directory_returns_zero(self, tmp_path: Path) -> None:
        assert CoverageReport.count_tickers(tmp_path / "no_dir") == 0


# ═══════════════════════════════════════════════════════════════
# compare_tickers()
# ═══════════════════════════════════════════════════════════════


class TestCompareTickers:
    """Disk vs DB ticker set comparison."""

    def test_perfect_match(self, tmp_path: Path) -> None:
        for t in ("AAPL", "MSFT", "GOOGL"):
            (tmp_path / t).mkdir()
        result = CoverageReport.compare_tickers(tmp_path, {"AAPL", "MSFT", "GOOGL"})
        assert result["common"] == 3
        assert result["coverage_pct"] == 100.0
        assert result["disk_only"] == []
        assert result["db_only"] == []

    def test_missing_on_disk(self, tmp_path: Path) -> None:
        (tmp_path / "AAPL").mkdir()
        result = CoverageReport.compare_tickers(tmp_path, {"AAPL", "MSFT"})
        assert result["common"] == 1
        assert result["db_only"] == ["MSFT"]
        assert result["coverage_pct"] == 50.0

    def test_extra_on_disk(self, tmp_path: Path) -> None:
        for t in ("AAPL", "EXTRA"):
            (tmp_path / t).mkdir()
        result = CoverageReport.compare_tickers(tmp_path, {"AAPL"})
        assert result["disk_only"] == ["EXTRA"]
        assert result["coverage_pct"] == 100.0  # DB tickers all on disk

    def test_empty_db_tickers(self, tmp_path: Path) -> None:
        (tmp_path / "AAPL").mkdir()
        result = CoverageReport.compare_tickers(tmp_path, set())
        assert result["coverage_pct"] == 0.0
        assert result["disk_only"] == ["AAPL"]

    def test_nonexistent_disk_dir(self, tmp_path: Path) -> None:
        result = CoverageReport.compare_tickers(
            tmp_path / "no_dir", {"AAPL", "MSFT"}
        )
        assert result["disk_count"] == 0
        assert result["db_only"] == ["AAPL", "MSFT"]


# ═══════════════════════════════════════════════════════════════
# get_db_tickers()
# ═══════════════════════════════════════════════════════════════


class TestGetDbTickers:
    """Database ticker extraction."""

    def test_returns_uppercase_tickers(self, db_session: Session) -> None:
        db_session.add_all([
            CompanyModel(ticker="AAPL", cik="0000320193", name="Apple Inc."),
            CompanyModel(ticker="msft", cik="0000789019", name="Microsoft Corp"),
        ])
        db_session.commit()

        tickers = CoverageReport.get_db_tickers(db_session)
        assert tickers == {"AAPL", "MSFT"}

    def test_empty_table_returns_empty_set(self, db_session: Session) -> None:
        assert CoverageReport.get_db_tickers(db_session) == set()


# ═══════════════════════════════════════════════════════════════
# generate_report()
# ═══════════════════════════════════════════════════════════════


class TestGenerateReport:
    """Full report generation."""

    def test_generates_report_structure(self) -> None:
        comparison = {
            "disk_count": 498, "db_count": 500, "common": 498,
            "disk_only": [], "db_only": ["BRK-B", "BF-B"],
            "coverage_pct": 99.6,
        }
        report = CoverageReport.generate_report(500, comparison)
        assert report["expected_total"] == 500
        assert report["missing_count"] == 2
        assert report["status"] == "incomplete"
        assert "timestamp" in report

    def test_full_coverage_marks_ok(self) -> None:
        comparison = {
            "disk_count": 500, "db_count": 500, "common": 500,
            "disk_only": [], "db_only": [],
            "coverage_pct": 100.0,
        }
        report = CoverageReport.generate_report(500, comparison)
        assert report["status"] == "ok"
        assert report["missing_count"] == 0
