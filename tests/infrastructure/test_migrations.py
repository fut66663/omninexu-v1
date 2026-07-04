"""Tests for Alembic migrations."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _make_alembic_config(database_url: str) -> Config:
    """Create an Alembic config pointing at the given database URL."""
    project_root = Path(__file__).resolve().parent.parent.parent
    config = Config(project_root / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _sqlite_file_url(tmp_path: Path) -> str:
    """Return a file-based SQLite URL in the given temp path."""
    return f"sqlite:///{tmp_path / 'migrations_test.db'}"


class TestMigrationsOnSQLite:
    """Migration tests using a shared file-based SQLite database."""

    def test_migration_upgrade_creates_expected_tables(self, tmp_path: Path) -> None:
        """Applying all migrations creates the expected tables."""
        database_url = _sqlite_file_url(tmp_path)
        config = _make_alembic_config(database_url)
        engine = create_engine(database_url)

        command.upgrade(config, "head")

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "companies" in tables
        assert "financial_facts" in tables
        assert "institutional_holdings" in tables
        assert "insider_transactions" in tables
        assert "alembic_version" in tables

    def test_migration_downgrade_upgrade_roundtrip(self, tmp_path: Path) -> None:
        """Migrations can be downgraded to base and re-applied."""
        database_url = _sqlite_file_url(tmp_path)
        config = _make_alembic_config(database_url)
        engine = create_engine(database_url)

        command.upgrade(config, "head")
        command.downgrade(config, "base")
        command.upgrade(config, "head")

        tables = inspect(engine).get_table_names()

        assert "companies" in tables
        assert "financial_facts" in tables
        assert "institutional_holdings" in tables
        assert "insider_transactions" in tables

    def test_migration_matches_model_indexes(self, tmp_path: Path) -> None:
        """Indexes created by migrations match those declared on models."""
        database_url = _sqlite_file_url(tmp_path)
        config = _make_alembic_config(database_url)
        engine = create_engine(database_url)

        command.upgrade(config, "head")

        inspector = inspect(engine)
        company_indexes = {idx["name"] for idx in inspector.get_indexes("companies")}
        fact_indexes = {idx["name"] for idx in inspector.get_indexes("financial_facts")}

        # Companies model declares unique indexes on ticker and cik.
        assert any("ticker" in name for name in company_indexes)
        assert any("cik" in name for name in company_indexes)

        # FinancialFactModel declares indexes on company_id, ticker, and concept.
        assert any("company_id" in name for name in fact_indexes)
        assert any("ticker" in name for name in fact_indexes)
        assert any("concept" in name for name in fact_indexes)

        # SQLite reports unique constraints both as indexes and via get_unique_constraints.
        unique_constraints = inspector.get_unique_constraints("financial_facts")
        unique_index_names = {
            idx["name"] for idx in inspector.get_indexes("financial_facts") if idx.get("unique")
        }
        assert unique_constraints or unique_index_names, (
            "Expected a unique constraint/index on financial_facts"
        )

    def test_migration_matches_model_columns(self, tmp_path: Path) -> None:
        """Columns created by migrations match the model metadata."""
        from omninexu.infrastructure.db import Base

        database_url = _sqlite_file_url(tmp_path)
        config = _make_alembic_config(database_url)
        engine = create_engine(database_url)

        command.upgrade(config, "head")

        inspector = inspect(engine)
        for table in Base.metadata.tables.values():
            actual_columns = {col["name"] for col in inspector.get_columns(table.name)}
            expected_columns = {col.name for col in table.columns}
            assert actual_columns == expected_columns, (
                f"{table.name} columns mismatch: {actual_columns ^ expected_columns}"
            )


class TestMigrationsOnPostgres:
    """Migration tests using the configured PostgreSQL database."""

    @pytest.mark.skip(reason="Integration test: mutates the PostgreSQL database")
    def test_postgres_migration_roundtrip(self) -> None:
        """Migrations can be downgraded and re-applied on PostgreSQL."""
        from omninexu.config.settings import settings

        config = _make_alembic_config(settings.database_url)

        command.downgrade(config, "base")
        command.upgrade(config, "head")

        engine = create_engine(settings.database_url)
        tables = inspect(engine).get_table_names()

        assert "companies" in tables
        assert "financial_facts" in tables
        assert "institutional_holdings" in tables
        assert "insider_transactions" in tables
        assert "alembic_version" in tables
