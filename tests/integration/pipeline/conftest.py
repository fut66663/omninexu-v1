"""Shared fixtures for end-to-end pipeline integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine

from omninexu.infrastructure.db import Base


@pytest.fixture
def e2e_data_root(tmp_path: Path) -> Path:
    """Isolated temporary data root for PipelineMonitor logs."""
    root = tmp_path / "OmniNexuData"
    root.mkdir()
    for sub in ("operations/logs/ingestion",):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def e2e_db_session():
    """In-memory SQLite session for end-to-end tests (no PostgreSQL needed)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    with Session(engine) as session:
        yield session
