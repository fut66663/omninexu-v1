"""Tests for database connection utilities."""

from unittest.mock import MagicMock, patch

import pytest

from omninexu.infrastructure.db import get_db


@patch("omninexu.infrastructure.db.SessionLocal")
def test_get_db_yields_session(mock_session_local):
    """get_db should yield a session obtained from SessionLocal."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    gen = get_db()
    db = next(gen)

    assert db is mock_db
    mock_db.close.assert_not_called()

    # Exhaust the generator to trigger the finally block.
    list(gen)

    mock_db.close.assert_called_once()


@patch("omninexu.infrastructure.db.SessionLocal")
def test_get_db_closes_on_exception(mock_session_local):
    """get_db should close the session even if the caller raises."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    gen = get_db()
    db = next(gen)
    assert db is mock_db

    # Simulate an exception inside the with-block (before generator exhaustion).
    with pytest.raises(RuntimeError, match="boom"):
        gen.throw(RuntimeError("boom"))

    mock_db.close.assert_called_once()
