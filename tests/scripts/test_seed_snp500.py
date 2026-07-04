"""Tests for scripts/ingest/seed_snp500.py."""

from unittest.mock import MagicMock, patch


class TestSeedSnp500:
    def test_seeds_all_sample_companies(self):
        from scripts.ingest.seed_snp500 import seed_snp500

        with (
            patch("scripts.ingest.seed_snp500.SessionLocal"),
            patch("scripts.ingest.seed_snp500.EdgarClient"),
            patch("scripts.ingest.seed_snp500.seed_company") as mock_seed,
            patch("scripts.ingest.seed_snp500.seed_company_financials") as mock_seed_fin,
            patch("scripts.ingest.seed_snp500._apply_gics") as mock_gics,
            patch("scripts.ingest.seed_snp500.load_mapping"),
        ):
            seed_snp500()
            assert mock_seed.call_count == 10
            assert mock_seed_fin.call_count == 10
            assert mock_gics.call_count == 10

    def test_rollback_on_exception(self):
        from scripts.ingest.seed_snp500 import seed_snp500

        with (
            patch("scripts.ingest.seed_snp500.SessionLocal"),
            patch("scripts.ingest.seed_snp500.EdgarClient"),
            patch("scripts.ingest.seed_snp500.seed_company") as mock_seed,
            patch("scripts.ingest.seed_snp500.seed_company_financials"),
            patch("scripts.ingest.seed_snp500._apply_gics"),
            patch("scripts.ingest.seed_snp500.load_mapping"),
        ):
            mock_seed.side_effect = RuntimeError("DB error")

            import pytest
            with pytest.raises(RuntimeError):
                seed_snp500()

    def test_explicit_session_not_closed(self):
        """When db session is passed, seed_snp500 should not close it."""
        from scripts.ingest.seed_snp500 import seed_snp500

        session = MagicMock()
        with (
            patch("scripts.ingest.seed_snp500.EdgarClient"),
            patch("scripts.ingest.seed_snp500.seed_company"),
            patch("scripts.ingest.seed_snp500.seed_company_financials"),
            patch("scripts.ingest.seed_snp500._apply_gics"),
            patch("scripts.ingest.seed_snp500.load_mapping"),
        ):
            seed_snp500(db=session)
            session.close.assert_not_called()

    def test_apply_gics_no_lookup(self):
        """_apply_gics should warn when SIC not in mapping."""
        from scripts.ingest.seed_snp500 import _apply_gics

        session = MagicMock()
        with (
            patch("scripts.ingest.seed_snp500.CompanyRepository") as mock_repo_cls,
            patch("scripts.ingest.seed_snp500.lookup") as mock_lookup,
        ):
            mock_lookup.return_value = None

            _apply_gics(session, "AAPL", "9999")
            mock_repo_cls.return_value.update_gics.assert_not_called()
