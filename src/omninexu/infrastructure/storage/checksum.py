"""SHA-256 checksum verification for downloaded data files.

Provides :class:`ChecksumMan` — a lightweight manifest-based integrity checker.
Each manifest is a JSON file mapping relative file paths to their SHA-256 hashes,
enabling fast batch verification of entire data directories.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omninexu.observability import get_logger

logger = get_logger(__name__)

# 64 KiB chunks balance memory usage and syscall overhead.
_CHUNK_SIZE = 64 * 1024


class ChecksumMan:
    """SHA-256 checksum manager for file integrity verification.

    Usage::

        cm = ChecksumMan()
        manifest = cm.store_manifest(
            [Path("data/file1.html"), Path("data/file2.csv")],
            Path("manifests/v1.json"),
        )
        passed, failed, paths = cm.verify_manifest(Path("manifests/v1.json"))
    """

    MANIFEST_VERSION = 1

    # ── single-file API ──────────────────────────────────────────

    @staticmethod
    def compute(path: Path) -> str:
        """Compute the SHA-256 hex digest of *path*.

        Args:
            path: File to hash.

        Returns:
            64-character lowercase hex digest.

        Raises:
            FileNotFoundError: If *path* does not exist.
            OSError: If the file cannot be read.
        """
        sha = hashlib.sha256()
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(_CHUNK_SIZE)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def verify(path: Path, expected: str) -> bool:
        """Return ``True`` if *path*'s SHA-256 matches *expected*.

        Args:
            path: File to verify.
            expected: Expected hex digest (case-insensitive comparison).
        """
        try:
            actual = ChecksumMan.compute(path)
        except (FileNotFoundError, OSError):
            return False
        return actual.lower() == expected.lower()

    # ── manifest API ─────────────────────────────────────────────

    @classmethod
    def store_manifest(cls, paths: list[Path], output: Path) -> dict[str, Any]:
        """Compute hashes for *paths* and persist a JSON manifest at *output*.

        The manifest records every file's relative path (vs. *output*'s parent
        directory) and its SHA-256 hash.  Existing files at *output* are
        overwritten.

        Args:
            paths: Files to include in the manifest.
            output: Where to write the manifest JSON file.

        Returns:
            The manifest dict that was written to disk:
            ``{"manifest_version": 1, "created_at": "...", "files": {...}}``
        """
        base = output.parent.resolve()
        files: dict[str, str] = {}
        for p in paths:
            # walk_up=True allows ../-prefixed keys when files are not
            # under the manifest's parent directory.
            key = str(p.resolve().relative_to(base, walk_up=True))
            files[key] = cls.compute(p)
            logger.debug("Hashed %s → %s", key, files[key][:12])

        manifest: dict[str, Any] = {
            "manifest_version": cls.MANIFEST_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "files": files,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Manifest stored: %d files → %s", len(files), output)
        return manifest

    @staticmethod
    def verify_manifest(manifest_path: Path) -> tuple[int, int, list[Path]]:
        """Verify every file listed in *manifest_path*.

        Corrupt or missing manifest entries are treated as failures.

        Args:
            manifest_path: Path to a JSON manifest file created by
                :meth:`store_manifest`.

        Returns:
            ``(passed, failed, failed_paths)`` — a three-tuple where
            *passed* and *failed* are counts and *failed_paths* lists
            the absolute paths of files whose hashes did not match.
        """
        try:
            raw = manifest_path.read_text(encoding="utf-8")
            manifest = json.loads(raw)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.error("Cannot read manifest %s: %s", manifest_path, exc)
            return (0, 0, [])

        base = manifest_path.parent
        files: dict[str, str] = manifest.get("files", {})
        if not files:
            logger.warning("Manifest %s contains no file entries", manifest_path)

        passed = 0
        failed = 0
        failed_paths: list[Path] = []

        for rel, expected in files.items():
            abs_path = base / rel
            if ChecksumMan.verify(abs_path, expected):
                passed += 1
            else:
                failed += 1
                failed_paths.append(abs_path)
                logger.warning("Checksum mismatch: %s", abs_path)

        logger.info(
            "Manifest verification complete: %d passed, %d failed (of %d total)",
            passed,
            failed,
            len(files),
        )
        return (passed, failed, failed_paths)
