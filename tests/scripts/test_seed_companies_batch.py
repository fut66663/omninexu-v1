"""Tests for scripts/ingest/seed_companies_batch.py."""

import json
from unittest.mock import patch


def _make_universe_file(tmp_path, day=1, tickers=None):
    if tickers is None:
        tickers = [{
            "ticker": "AAPL",
            "cik": "0000320193",
            "name": "Apple Inc.",
            "gics_sector": "Information Technology",
            "gics_sub_industry": "Technology Hardware",
            "sic": "3571",
        }]
    path = tmp_path / f"sp500_universe_day{day}.json"
    path.write_text(json.dumps(tickers), encoding="utf-8")
    return path


class TestSeedCompaniesBatch:
    def test_seeds_all_companies(self, tmp_path):
        from scripts.ingest.seed_companies_batch import seed_companies_batch

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        _make_universe_file(universe_dir, day=1)

        with (
            patch("scripts.ingest.seed_companies_batch.UNIVERSE_DIR", universe_dir),
            patch("scripts.ingest.seed_companies_batch.SessionLocal"),
            patch("scripts.ingest.seed_companies_batch.CompanyRepository") as mock_repo_cls,
            patch("scripts.ingest.seed_companies_batch.CheckpointManager") as mock_cpm,
        ):
            mock_repo = mock_repo_cls.return_value
            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["AAPL"]

            results = seed_companies_batch(day=1)
            assert results["AAPL"] == 1
            mock_repo.create_or_update.assert_called_once()

    def test_returns_empty_when_all_seeded(self, tmp_path):
        from scripts.ingest.seed_companies_batch import seed_companies_batch

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        _make_universe_file(universe_dir, day=1)

        with (
            patch("scripts.ingest.seed_companies_batch.UNIVERSE_DIR", universe_dir),
            patch("scripts.ingest.seed_companies_batch.SessionLocal"),
            patch("scripts.ingest.seed_companies_batch.CompanyRepository"),
            patch("scripts.ingest.seed_companies_batch.CheckpointManager") as mock_cpm,
        ):
            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = []

            results = seed_companies_batch(day=1)
            assert results == {}

    def test_deduplicates_by_cik(self, tmp_path):
        """GOOGL and GOOG share the same CIK — only one should be seeded."""
        from scripts.ingest.seed_companies_batch import seed_companies_batch

        tickers = [
            {"ticker": "GOOGL", "cik": "0001652044", "name": "Alphabet Inc.", "gics_sector": "Communication Services", "gics_sub_industry": "Interactive Media", "sic": "7370"},
            {"ticker": "GOOG", "cik": "0001652044", "name": "Alphabet Inc.", "gics_sector": "Communication Services", "gics_sub_industry": "Interactive Media", "sic": "7370"},
        ]
        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        _make_universe_file(universe_dir, day=1, tickers=tickers)

        with (
            patch("scripts.ingest.seed_companies_batch.UNIVERSE_DIR", universe_dir),
            patch("scripts.ingest.seed_companies_batch.SessionLocal"),
            patch("scripts.ingest.seed_companies_batch.CompanyRepository"),
            patch("scripts.ingest.seed_companies_batch.CheckpointManager") as mock_cpm,
        ):
            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["GOOGL"]

            results = seed_companies_batch(day=1)
            # Only GOOGL (first) should be seeded; GOOG skipped as duplicate
            assert "GOOGL" in results

    def test_handles_db_failure(self, tmp_path):
        from scripts.ingest.seed_companies_batch import seed_companies_batch

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        _make_universe_file(universe_dir, day=1)

        with (
            patch("scripts.ingest.seed_companies_batch.UNIVERSE_DIR", universe_dir),
            patch("scripts.ingest.seed_companies_batch.SessionLocal"),
            patch("scripts.ingest.seed_companies_batch.CompanyRepository") as mock_repo_cls,
            patch("scripts.ingest.seed_companies_batch.CheckpointManager") as mock_cpm,
        ):
            mock_repo = mock_repo_cls.return_value
            mock_repo.create_or_update.side_effect = RuntimeError("DB down")
            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["AAPL"]

            results = seed_companies_batch(day=1)
            assert results["AAPL"] == -1

    def test_retry_failed_mode(self, tmp_path):
        from scripts.ingest.seed_companies_batch import seed_companies_batch

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        _make_universe_file(universe_dir, day=1)

        with (
            patch("scripts.ingest.seed_companies_batch.UNIVERSE_DIR", universe_dir),
            patch("scripts.ingest.seed_companies_batch.SessionLocal"),
            patch("scripts.ingest.seed_companies_batch.CompanyRepository"),
            patch("scripts.ingest.seed_companies_batch.CheckpointManager") as mock_cpm,
        ):
            cpm = mock_cpm.return_value
            cpm.get_failed.return_value = [{"ticker": "AAPL"}]
            cpm.get_pending.return_value = []

            results = seed_companies_batch(day=1, retry_failed=True)
            assert "AAPL" in results
