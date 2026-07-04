"""Tests for DataPaths — all property accessors + ensure_dirs()."""

from pathlib import Path

import pytest

from omninexu.config.data_paths import DataPaths, _default_root


@pytest.fixture
def dp():
    """DataPaths instance rooted at a test temp location."""
    return DataPaths(root="D:/OmniNexuData")


class TestDefaultRoot:
    """Root path resolution."""

    def test_default_root_is_drive_d(self):
        dp = DataPaths(root="D:/OmniNexuData")
        assert dp.root == Path("D:/OmniNexuData")

    def test_custom_root(self):
        dp = DataPaths(root="/custom/data")
        assert dp.root == Path("/custom/data")

    def test_default_root_func_returns_path(self):
        assert isinstance(_default_root(), Path)


class TestRawSecPhase0:
    """Phase 0 SEC paths."""

    def test_raw_sec(self, dp):
        assert dp.raw_sec == dp.root / "raw" / "sec"

    def test_raw_sec_10k(self, dp):
        assert dp.raw_sec_10k == dp.root / "raw" / "sec" / "10-K"

    def test_raw_simfin(self, dp):
        assert dp.raw_simfin == dp.root / "raw" / "simfin"


class TestRawReserved:
    """Phase 1–C reserved SEC paths."""

    def test_raw_sec_13f(self, dp):
        assert dp.raw_sec_13f == dp.root / "raw" / "sec" / "13F"

    def test_raw_sec_form4(self, dp):
        assert dp.raw_sec_form4 == dp.root / "raw" / "sec" / "Form-4"

    def test_raw_fred(self, dp):
        assert dp.raw_fred == dp.root / "raw" / "fred"


class TestRawSecPhase0Reserved:
    """Phase 0–1 reserved SEC paths (currently untested)."""

    def test_raw_sec_10q(self, dp):
        """Phase 0: 10-Q quarterly report cache (line 65)."""
        assert dp.raw_sec_10q == dp.root / "raw" / "sec" / "10-Q"

    def test_raw_sec_8k(self, dp):
        """Phase 1: 8-K current events (line 70)."""
        assert dp.raw_sec_8k == dp.root / "raw" / "sec" / "8-K"

    def test_raw_sec_form3(self, dp):
        """Phase 1: Form 3 initial insider holdings (line 75)."""
        assert dp.raw_sec_form3 == dp.root / "raw" / "sec" / "Form-3"

    def test_raw_sec_def14a(self, dp):
        """Phase 1: DEF 14A proxy statements (line 80)."""
        assert dp.raw_sec_def14a == dp.root / "raw" / "sec" / "DEF-14A"


class TestRawExternalPhase1:
    """Phase 1 planned external data source paths (currently untested)."""

    def test_raw_finra(self, dp):
        """FINRA TRACE corporate bond data (line 92)."""
        assert dp.raw_finra == dp.root / "raw" / "finra"

    def test_raw_cboe(self, dp):
        """CBOE historical options EOD data (line 97)."""
        assert dp.raw_cboe == dp.root / "raw" / "cboe"

    def test_raw_bea(self, dp):
        """BEA GDP-by-industry data (line 102)."""
        assert dp.raw_bea == dp.root / "raw" / "bea"

    def test_raw_finnhub(self, dp):
        """Finnhub options/quotes data (line 107)."""
        assert dp.raw_finnhub == dp.root / "raw" / "finnhub"


class TestProcessedPhase1:
    """Phase 1 processed layer paths (currently untested)."""

    def test_processed_naics(self, dp):
        """SIC → NAICS classification mapping (line 124)."""
        assert dp.processed_naics == dp.root / "processed" / "naics"


class TestProcessed:
    """processed/ layer paths."""

    def test_processed_universe(self, dp):
        assert dp.processed_universe == dp.root / "processed" / "universe"

    def test_processed_gics(self, dp):
        assert dp.processed_gics == dp.root / "processed" / "gics"

    def test_processed_financials(self, dp):
        assert dp.processed_financials == dp.root / "processed" / "financials"

    def test_processed_text(self, dp):
        assert dp.processed_text == dp.root / "processed" / "text"

    def test_processed_graph(self, dp):
        assert dp.processed_graph == dp.root / "processed" / "graph"


class TestProducts:
    """products/ layer paths."""

    def test_products_context(self, dp):
        assert dp.products_context == dp.root / "products" / "context"

    def test_products_radar(self, dp):
        assert dp.products_radar == dp.root / "products" / "radar"

    def test_products_pulse(self, dp):
        assert dp.products_pulse == dp.root / "products" / "pulse"


class TestOperationsPhase0:
    """Phase 0 operations paths."""

    def test_logs_api(self, dp):
        assert dp.logs_api == dp.root / "operations" / "logs" / "api"

    def test_logs_errors(self, dp):
        assert dp.logs_errors == dp.root / "operations" / "logs" / "errors"

    def test_checkpoints_dir(self, dp):
        assert dp.checkpoints_dir == dp.root / "operations" / "checkpoints"

    def test_state_dir(self, dp):
        assert dp.state_dir == dp.root / "operations" / "state"

    def test_cache_dir(self, dp):
        assert dp.cache_dir == dp.root / "operations" / "cache"

    def test_backup_dir(self, dp):
        assert dp.backup_dir == dp.root / "operations" / "backups"

    def test_quality_dir(self, dp):
        assert dp.quality_dir == dp.root / "operations" / "quality"


class TestOperationsReserved:
    """Phase 0.5–1 reserved operations paths."""

    def test_logs_ingestion(self, dp):
        assert dp.logs_ingestion == dp.root / "operations" / "logs" / "ingestion"

    def test_audit_dir(self, dp):
        assert dp.audit_dir == dp.root / "operations" / "audit"

    def test_metrics_dir(self, dp):
        assert dp.metrics_dir == dp.root / "operations" / "metrics"


class TestX402:
    """Phase 0.5 x402 payment paths."""

    def test_x402_receipts(self, dp):
        assert dp.x402_receipts == dp.root / "x402" / "receipts"

    def test_x402_usage(self, dp):
        assert dp.x402_usage == dp.root / "x402" / "usage"

    def test_x402_settlements(self, dp):
        assert dp.x402_settlements == dp.root / "x402" / "settlements"


class TestDatabases:
    """Database paths."""

    def test_duckdb_path(self, dp):
        assert dp.duckdb_path == dp.root / "db" / "omninexu.duckdb"


class TestEnsureDirs:
    """ensure_dirs() creates Phase 0 directories."""

    def test_ensure_dirs_creates_all(self, tmp_path):
        dp = DataPaths(root=tmp_path)
        dp.ensure_dirs()
        assert dp.raw_sec_10k.exists()
        assert dp.processed_universe.exists()
        assert dp.checkpoints_dir.exists()
        assert dp.logs_errors.exists()

    def test_ensure_dirs_idempotent(self, tmp_path):
        dp = DataPaths(root=tmp_path)
        dp.ensure_dirs()
        dp.ensure_dirs()  # no error on second call
        assert dp.cache_dir.exists()
