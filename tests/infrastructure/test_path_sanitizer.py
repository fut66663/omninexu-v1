"""Tests for PathSanitizer -- cross-platform path normalisation."""

from __future__ import annotations

from pathlib import Path

from omninexu.config.path_sanitizer import PathSanitizer


class TestSanitize:
    """Path normalisation."""

    def test_absolute_path_unchanged(self) -> None:
        p = PathSanitizer.sanitize("/home/user/data")
        assert p.is_absolute()

    def test_relative_path_resolved(self, tmp_path: Path) -> None:
        p = PathSanitizer.sanitize(str(tmp_path / "sub"))
        assert p.is_absolute()
        assert p.name == "sub"

    def test_expands_tilde(self) -> None:
        p = PathSanitizer.sanitize("~/OmniNexuData")
        assert p.is_absolute()
        assert str(p).endswith("OmniNexuData")

    def test_expands_env_vars(self, monkeypatch) -> None:
        monkeypatch.setenv("TEST_DATA", "my_data_dir")
        p = PathSanitizer.sanitize("/base/$TEST_DATA/sub")
        assert p.name == "sub"
        assert "my_data_dir" in str(p)
