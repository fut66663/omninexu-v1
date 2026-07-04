"""Tests for ChecksumMan — SHA-256 file integrity verification.

Covers the core compute / verify / store_manifest / verify_manifest API.
Edge cases (large files, concurrency, binary) are in test_checksum_coverage.py.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from omninexu.infrastructure.storage.checksum import ChecksumMan


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Write a small text file in a temporary directory."""
    f = tmp_path / "sample.txt"
    f.write_text("OmniNexu data integrity test\n", encoding="utf-8")
    return f


# ═══════════════════════════════════════════════════════════════
# compute()
# ═══════════════════════════════════════════════════════════════


class TestCompute:
    """SHA-256 computation."""

    def test_compute_returns_64_char_hex(self, sample_file: Path) -> None:
        digest = ChecksumMan.compute(sample_file)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_compute_is_deterministic(self, sample_file: Path) -> None:
        assert ChecksumMan.compute(sample_file) == ChecksumMan.compute(sample_file)

    def test_compute_different_content_different_hash(self, tmp_path: Path) -> None:
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("hello", encoding="utf-8")
        b.write_text("world", encoding="utf-8")
        assert ChecksumMan.compute(a) != ChecksumMan.compute(b)

    def test_compute_matches_python_hashlib(self, sample_file: Path) -> None:
        expected = hashlib.sha256(sample_file.read_bytes()).hexdigest()
        assert ChecksumMan.compute(sample_file) == expected

    def test_compute_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ChecksumMan.compute(tmp_path / "nonexistent.txt")


# ═══════════════════════════════════════════════════════════════
# verify()
# ═══════════════════════════════════════════════════════════════


class TestVerify:
    """Single-file verification."""

    def test_verify_matching_hash_returns_true(self, sample_file: Path) -> None:
        digest = ChecksumMan.compute(sample_file)
        assert ChecksumMan.verify(sample_file, digest) is True

    def test_verify_mismatched_hash_returns_false(self, sample_file: Path) -> None:
        assert ChecksumMan.verify(sample_file, "0" * 64) is False

    def test_verify_case_insensitive(self, sample_file: Path) -> None:
        digest = ChecksumMan.compute(sample_file)
        assert ChecksumMan.verify(sample_file, digest.upper()) is True

    def test_verify_missing_file_returns_false(self, tmp_path: Path) -> None:
        assert ChecksumMan.verify(tmp_path / "gone.txt", "0" * 64) is False

    def test_verify_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.txt"
        empty.write_text("", encoding="utf-8")
        empty_hash = hashlib.sha256(b"").hexdigest()
        assert ChecksumMan.verify(empty, empty_hash) is True


# ═══════════════════════════════════════════════════════════════
# store_manifest()
# ═══════════════════════════════════════════════════════════════


class TestStoreManifest:
    """Manifest creation."""

    def test_store_manifest_writes_json(self, tmp_path: Path) -> None:
        f1 = tmp_path / "data" / "a.html"
        f1.parent.mkdir(parents=True, exist_ok=True)
        f1.write_text("<html>AAPL 10-K</html>", encoding="utf-8")

        manifest_path = tmp_path / "manifests" / "v1.json"
        result = ChecksumMan.store_manifest([f1], manifest_path)

        assert manifest_path.exists()
        assert result["manifest_version"] == 1
        assert "created_at" in result
        assert len(result["files"]) == 1

    def test_store_manifest_uses_relative_paths(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "sec" / "10-K" / "AAPL" / "2024-09-28"
        data_dir.mkdir(parents=True, exist_ok=True)
        f1 = data_dir / "filing.html"
        f1.write_text("10-K filing content", encoding="utf-8")

        manifest_path = tmp_path / "manifests" / "v1.json"
        result = ChecksumMan.store_manifest([f1], manifest_path)
        keys = list(result["files"].keys())
        assert any("sec" in k for k in keys)

    def test_store_manifest_overwrites_existing(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f1.write_text("first", encoding="utf-8")
        manifest_path = tmp_path / "manifest.json"
        ChecksumMan.store_manifest([f1], manifest_path)
        old_hash = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]

        f1.write_text("second", encoding="utf-8")
        ChecksumMan.store_manifest([f1], manifest_path)
        new_hash = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
        assert old_hash != new_hash

    def test_store_manifest_empty_list(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "empty_manifest.json"
        result = ChecksumMan.store_manifest([], manifest_path)
        assert result["files"] == {}
        assert manifest_path.exists()


# ═══════════════════════════════════════════════════════════════
# verify_manifest()
# ═══════════════════════════════════════════════════════════════


class TestVerifyManifest:
    """Manifest-based batch verification."""

    def test_all_pass_for_unchanged_files(self, tmp_path: Path) -> None:
        f1, f2 = tmp_path / "a.txt", tmp_path / "b.txt"
        f1.write_text("hello", encoding="utf-8")
        f2.write_text("world", encoding="utf-8")
        manifest_path = tmp_path / "manifest.json"
        ChecksumMan.store_manifest([f1, f2], manifest_path)

        passed, failed, failed_paths = ChecksumMan.verify_manifest(manifest_path)
        assert passed == 2
        assert failed == 0
        assert failed_paths == []

    def test_detects_modified_file(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f1.write_text("original", encoding="utf-8")
        manifest_path = tmp_path / "manifest.json"
        ChecksumMan.store_manifest([f1], manifest_path)
        f1.write_text("tampered", encoding="utf-8")

        passed, failed, failed_paths = ChecksumMan.verify_manifest(manifest_path)
        assert passed == 0
        assert failed == 1
        assert failed_paths[0] == f1.resolve()

    def test_detects_deleted_file(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f1.write_text("will be deleted", encoding="utf-8")
        manifest_path = tmp_path / "manifest.json"
        ChecksumMan.store_manifest([f1], manifest_path)
        f1.unlink()

        passed, failed, _ = ChecksumMan.verify_manifest(manifest_path)
        assert passed == 0
        assert failed == 1

    def test_corrupt_or_missing_manifest(self, tmp_path: Path) -> None:
        """Corrupt JSON or missing manifest returns zero counts, no crash."""
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        passed, failed, _ = ChecksumMan.verify_manifest(bad)
        assert (passed, failed) == (0, 0)

        passed2, failed2, _ = ChecksumMan.verify_manifest(tmp_path / "nonexistent.json")
        assert (passed2, failed2) == (0, 0)

    def test_manifest_empty_files_dict(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.json"
        empty.write_text('{"manifest_version": 1, "files": {}}', encoding="utf-8")
        passed, failed, _ = ChecksumMan.verify_manifest(empty)
        assert (passed, failed) == (0, 0)

    def test_mixed_pass_and_fail(self, tmp_path: Path) -> None:
        f1, f2 = tmp_path / "good.txt", tmp_path / "bad.txt"
        f1.write_text("good", encoding="utf-8")
        f2.write_text("bad-original", encoding="utf-8")
        manifest_path = tmp_path / "manifest.json"
        ChecksumMan.store_manifest([f1, f2], manifest_path)
        f2.write_text("bad-tampered", encoding="utf-8")

        passed, failed, failed_paths = ChecksumMan.verify_manifest(manifest_path)
        assert passed == 1
        assert failed == 1
        assert f2.resolve() in failed_paths
