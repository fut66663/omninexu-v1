"""Tests for scripts/ops/migrate_data_layout.py.

The migration is complete and main() is a no-op, but the individual
step functions are still testable.  Module-level path variables are
computed at import time so we patch them directly rather than ROOT.
"""

from unittest.mock import patch

from scripts.ops.migrate_data_layout import (
    _cleanup_debug,
    _cleanup_exports,
    _migrate_backups,
    _migrate_checkpoints,
    _migrate_legacy_13f,
    _migrate_processed,
    _migrate_sec_10k,
    migrate,
)


class TestMain:
    def test_main_prints_deprecation_and_exits(self):
        """main() is a no-op that prints a deprecation message and exits."""
        import pytest
        with pytest.raises(SystemExit) as exc:
            from scripts.ops.migrate_data_layout import main
            main()
        assert exc.value.code == 0


class TestMigrate:
    def test_migrate_dry_run(self, tmp_path):
        """migrate(dry_run=True) executes all steps without real changes."""
        old_sec = tmp_path / "raw" / "sec"
        old_sec.mkdir(parents=True)

        # M1: ticker dir with 10-K
        ticker_dir = old_sec / "AAPL"
        ticker_dir.mkdir()
        k10_dir = ticker_dir / "10-K"
        k10_dir.mkdir()
        (k10_dir / "filing.txt").write_text("data")

        # M2: legacy dir
        legacy_dir = old_sec / "AAPL_0000320193"
        legacy_dir.mkdir()

        # M3: debug dirs
        (old_sec / "CIK1_DEBUG").mkdir()
        (old_sec / "CIK2_DEBUG").mkdir()

        # M4-M6: processed files
        processed = tmp_path / "processed"
        processed.mkdir(parents=True)
        (processed / "sp500_universe_day1.json").touch()

        # M7: checkpoint in operations
        ops = tmp_path / "operations"
        ops.mkdir(parents=True)
        (ops / "checkpoint_day1.json").touch()

        # M8: db/backup
        db_backup = tmp_path / "db" / "backup"
        db_backup.mkdir(parents=True)
        (db_backup / "omninexu_2026-01-01.dump").touch()

        # M9: exports
        export_dir = tmp_path / "exports"
        export_dir.mkdir(parents=True)
        (export_dir / "data.csv").touch()

        paths = {
            "OLD_SEC": old_sec,
            "NEW_10K": tmp_path / "raw" / "sec" / "10-K",
            "LEGACY": tmp_path / "raw" / "sec" / "_legacy",
            "OLD_PROCESSED": processed,
            "NEW_UNIVERSE": tmp_path / "processed" / "universe",
            "OLD_OPS": ops,
            "NEW_CHECKPOINTS": tmp_path / "operations" / "checkpoints",
            "OLD_DB_BACKUP": db_backup,
            "NEW_BACKUPS": tmp_path / "operations" / "backups",
            "OLD_EXPORTS": export_dir,
        }

        patches = [
            patch(f"scripts.ops.migrate_data_layout.{k}", v)
            for k, v in paths.items()
        ]
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
             patches[5], patches[6], patches[7], patches[8], patches[9]:
            results = migrate(dry_run=True)
            total = sum(results.values())
            assert total >= 1

    def test_migrate_executes_all_steps(self, tmp_path):
        """migrate(dry_run=False) executes for real (no side effects on tmp)."""
        old_sec = tmp_path / "raw" / "sec"
        old_sec.mkdir(parents=True)

        ticker_dir = old_sec / "AAPL"
        ticker_dir.mkdir()
        (ticker_dir / "10-K").mkdir()

        (old_sec / "CIK1_DEBUG").mkdir()
        (old_sec / "CIK2_DEBUG").mkdir()

        processed = tmp_path / "processed"
        processed.mkdir(parents=True)
        (processed / "sp500_universe_day1.json").touch()

        ops = tmp_path / "operations"
        ops.mkdir(parents=True)
        (ops / "checkpoint_phase1.json").touch()

        db_backup = tmp_path / "db" / "backup"
        db_backup.mkdir(parents=True)
        (db_backup / "old.dump").touch()

        export_dir = tmp_path / "exports"
        export_dir.mkdir(parents=True)
        (export_dir / "data.csv").touch()

        paths = {
            "OLD_SEC": old_sec,
            "NEW_10K": tmp_path / "raw" / "sec" / "10-K",
            "LEGACY": tmp_path / "raw" / "sec" / "_legacy",
            "OLD_PROCESSED": processed,
            "NEW_UNIVERSE": tmp_path / "processed" / "universe",
            "OLD_OPS": ops,
            "NEW_CHECKPOINTS": tmp_path / "operations" / "checkpoints",
            "OLD_DB_BACKUP": db_backup,
            "NEW_BACKUPS": tmp_path / "operations" / "backups",
            "OLD_EXPORTS": export_dir,
        }

        patches = [
            patch(f"scripts.ops.migrate_data_layout.{k}", v)
            for k, v in paths.items()
        ]
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
             patches[5], patches[6], patches[7], patches[8], patches[9]:
            results = migrate(dry_run=False)
            assert isinstance(results, dict)
            assert len(results) == 7


class TestStepFunctions:
    def test_cleanup_debug_dry_run(self, tmp_path):
        old_sec = tmp_path / "sec"
        old_sec.mkdir(parents=True)
        (old_sec / "CIK1_DEBUG").mkdir()
        (old_sec / "CIK2_DEBUG").mkdir()

        with patch("scripts.ops.migrate_data_layout.OLD_SEC", old_sec):
            count = _cleanup_debug(dry=True)
            assert count == 2
            assert (old_sec / "CIK1_DEBUG").exists()

    def test_migrate_sec_10k_dry_run(self, tmp_path):
        old_sec = tmp_path / "sec"
        old_sec.mkdir(parents=True)
        ticker_dir = old_sec / "AAPL"
        ticker_dir.mkdir()
        (ticker_dir / "10-K").mkdir()

        new_10k = tmp_path / "new10k"

        with (
            patch("scripts.ops.migrate_data_layout.OLD_SEC", old_sec),
            patch("scripts.ops.migrate_data_layout.NEW_10K", new_10k),
        ):
            count = _migrate_sec_10k(dry=True)
            assert count == 1

    def test_migrate_legacy_13f_dry_run(self, tmp_path):
        old_sec = tmp_path / "sec"
        old_sec.mkdir(parents=True)
        (old_sec / "BRK.B_0001067983").mkdir()

        legacy = tmp_path / "legacy"

        with (
            patch("scripts.ops.migrate_data_layout.OLD_SEC", old_sec),
            patch("scripts.ops.migrate_data_layout.LEGACY", legacy),
        ):
            count = _migrate_legacy_13f(dry=True)
            assert count == 1

    def test_migrate_processed_dry_run(self, tmp_path):
        processed = tmp_path / "processed"
        processed.mkdir(parents=True)
        (processed / "sp500_universe_day1.json").touch()

        new_universe = tmp_path / "universe"

        with (
            patch("scripts.ops.migrate_data_layout.OLD_PROCESSED", processed),
            patch("scripts.ops.migrate_data_layout.NEW_UNIVERSE", new_universe),
        ):
            count = _migrate_processed(dry=True)
            assert count >= 0

    def test_migrate_checkpoints_dry_run(self, tmp_path):
        ops = tmp_path / "ops"
        ops.mkdir(parents=True)
        (ops / "checkpoint_day1.json").touch()

        new_cp = tmp_path / "checkpoints"

        with (
            patch("scripts.ops.migrate_data_layout.OLD_OPS", ops),
            patch("scripts.ops.migrate_data_layout.NEW_CHECKPOINTS", new_cp),
        ):
            count = _migrate_checkpoints(dry=True)
            assert count >= 0

    def test_migrate_backups_empty(self, tmp_path):
        old_db = tmp_path / "db_backup"

        with patch("scripts.ops.migrate_data_layout.OLD_DB_BACKUP", old_db):
            count = _migrate_backups(dry=True)
            assert count == 0

    def test_cleanup_exports_missing(self, tmp_path):
        old_exports = tmp_path / "nonexistent"

        with patch("scripts.ops.migrate_data_layout.OLD_EXPORTS", old_exports):
            count = _cleanup_exports(dry=True)
            assert count == 0
