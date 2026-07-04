"""Edge-case and stress tests for ChecksumMan.

Covers large files, concurrency, binary content, and manifest corner cases.
Core API tests are in test_checksum.py.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from omninexu.infrastructure.storage.checksum import ChecksumMan

# ═══════════════════════════════════════════════════════════════
# Large files (multi-chunk read path)
# ═══════════════════════════════════════════════════════════════


class TestLargeFile:
    """Behaviour with files larger than the 64 KiB chunk buffer."""

    def test_compute_2mb_file(self, tmp_path: Path) -> None:
        big = tmp_path / "large.bin"
        big.write_bytes(b"\xAB" * (2 * 1024 * 1024))
        digest = ChecksumMan.compute(big)
        expected = hashlib.sha256(big.read_bytes()).hexdigest()
        assert digest == expected

    def test_verify_2mb_file(self, tmp_path: Path) -> None:
        big = tmp_path / "large.bin"
        big.write_bytes(b"\xCD" * (2 * 1024 * 1024))
        digest = ChecksumMan.compute(big)
        assert ChecksumMan.verify(big, digest) is True


# ═══════════════════════════════════════════════════════════════
# Concurrency (all methods are stateless → safe under contention)
# ═══════════════════════════════════════════════════════════════


class TestConcurrency:
    """Concurrent hashing is safe — no shared mutable state."""

    def test_concurrent_compute_eight_files(self, tmp_path: Path) -> None:
        files = []
        for i in range(8):
            f = tmp_path / f"file_{i}.bin"
            f.write_bytes(bytes([x % 256 for x in range(i, i + 256)]))
            files.append(f)

        results: list[str | None] = [None] * 8
        barrier = threading.Barrier(8, timeout=5)

        def worker(idx: int) -> None:
            barrier.wait()
            results[idx] = ChecksumMan.compute(files[idx])

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i, r in enumerate(results):
            assert r is not None, f"Thread {i} returned None"
            assert len(r) == 64

    def test_concurrent_verify_same_file(self, tmp_path: Path) -> None:
        f = tmp_path / "shared.txt"
        f.write_text("shared content for concurrent verify", encoding="utf-8")
        digest = ChecksumMan.compute(f)

        outcomes: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            ok = ChecksumMan.verify(f, digest)
            with lock:
                outcomes.append(ok)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(outcomes) == 4
        assert all(outcomes)


# ═══════════════════════════════════════════════════════════════
# Binary / non-UTF-8 edge cases
# ═══════════════════════════════════════════════════════════════


class TestBinaryEdgeCases:
    """Files that are not valid text must still hash correctly."""

    def test_null_bytes_only(self, tmp_path: Path) -> None:
        f = tmp_path / "nulls.bin"
        f.write_bytes(b"\x00" * 1024)
        digest = ChecksumMan.compute(f)
        assert ChecksumMan.verify(f, digest) is True

    def test_single_byte_file(self, tmp_path: Path) -> None:
        f = tmp_path / "single.bin"
        f.write_bytes(b"\xFF")
        digest = ChecksumMan.compute(f)
        assert ChecksumMan.verify(f, digest) is True

    def test_non_utf8_content(self, tmp_path: Path) -> None:
        f = tmp_path / "mixed.bin"
        f.write_bytes(b"\x00\x01\x02\xFF\xFE\xFDHello\x89PNG\r\n")
        digest = ChecksumMan.compute(f)
        expected = hashlib.sha256(f.read_bytes()).hexdigest()
        assert digest == expected

    def test_manifest_with_binary_file(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02")
        manifest_path = tmp_path / "manifest.json"
        ChecksumMan.store_manifest([f], manifest_path)
        passed, failed, _ = ChecksumMan.verify_manifest(manifest_path)
        assert passed == 1
        assert failed == 0


# ═══════════════════════════════════════════════════════════════
# store_manifest edge cases
# ═══════════════════════════════════════════════════════════════


class TestStoreManifestEdgeCases:
    """Manifest creation corner cases."""

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        f1 = tmp_path / "data.txt"
        f1.write_text("test", encoding="utf-8")
        deep = tmp_path / "a" / "b" / "c" / "manifest.json"
        assert not deep.parent.exists()
        ChecksumMan.store_manifest([f1], deep)
        assert deep.exists()
