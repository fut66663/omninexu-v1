"""Tests for API request-logging middleware."""

import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from omninexu.api.middleware import log_request
from omninexu.config.data_paths import DataPaths


class TestRequestLoggingMiddleware:
    """Tests for the HTTP request-logging middleware."""

    @staticmethod
    def _make_test_app() -> FastAPI:
        """Create a minimal FastAPI app with the logging middleware."""
        app = FastAPI()

        @app.get("/ok")
        async def ok_endpoint() -> dict:
            return {"status": "ok"}

        @app.get("/fail")
        async def fail_endpoint() -> dict:
            return {"status": "ok"}

        app.middleware("http")(log_request)
        return app

    @staticmethod
    def _patch_data_paths(tmp_path: Path):
        """Redirect middleware's data_paths to use *tmp_path*."""
        fake_dp = DataPaths(str(tmp_path))
        return patch(
            "omninexu.api.middleware.logging.data_paths",
            fake_dp,
        )

    def test_middleware_writes_jsonl(self, tmp_path: Path) -> None:
        """After a request a JSONL line is appended to the log file."""
        app = self._make_test_app()
        client = TestClient(app)

        with self._patch_data_paths(tmp_path):
            response = client.get("/ok")

        assert response.status_code == 200

        log_dir = tmp_path / "operations" / "logs" / "api"
        log_files = sorted(log_dir.glob("*.jsonl"))
        assert len(log_files) == 1, f"Expected 1 log file, got {log_files}"

        lines = log_files[0].read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["method"] == "GET"
        assert entry["path"] == "/ok"
        assert entry["status"] == 200

    def test_middleware_records_404_status(self, tmp_path: Path) -> None:
        """A 404 response is logged with the correct status code."""
        app = self._make_test_app()
        client = TestClient(app)

        with self._patch_data_paths(tmp_path):
            client.get("/nonexistent")

        log_dir = tmp_path / "operations" / "logs" / "api"
        log_files = sorted(log_dir.glob("*.jsonl"))
        lines = log_files[0].read_text(encoding="utf-8").strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["status"] == 404
        assert entry["path"] == "/nonexistent"

    def test_middleware_duration_is_positive(self, tmp_path: Path) -> None:
        """Duration field is present and positive."""
        app = self._make_test_app()
        client = TestClient(app)

        with self._patch_data_paths(tmp_path):
            client.get("/ok")

        log_dir = tmp_path / "operations" / "logs" / "api"
        log_files = sorted(log_dir.glob("*.jsonl"))
        entry = json.loads(log_files[0].read_text(encoding="utf-8").strip())
        assert entry["duration_ms"] > 0

    def test_middleware_survives_disk_error(self, tmp_path: Path) -> None:
        """When disk write fails the API still returns a normal response."""
        app = self._make_test_app()
        client = TestClient(app)

        with self._patch_data_paths(tmp_path), patch(
            "builtins.open", side_effect=OSError("Disk full")
        ):
            response = client.get("/ok")

        # API must still return 200 — logging failure is not a request failure.
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
