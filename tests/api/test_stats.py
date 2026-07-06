"""Stats endpoint tests."""

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def _write_log(log_dir: Path, filename: str, lines: list[dict]) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    p = log_dir / filename
    p.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in lines) + "\n",
        encoding="utf-8",
    )
    return p


def test_stats_empty(client: TestClient, monkeypatch) -> None:
    """Stats returns zeros when no data logged today."""
    import omninexu.api.routes.stats as m

    with TemporaryDirectory() as tmp:
        monkeypatch.setattr(
            type(m.data_paths), "logs_analytics",
            property(lambda s, d=Path(tmp): d),
        )
        resp = client.get("/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["paid"] == 0
        assert data["avg_ms"] == 0


def test_stats_with_data(client: TestClient, monkeypatch) -> None:
    """Stats correctly aggregates today's analytics lines."""
    import omninexu.api.routes.stats as m

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    month = datetime.now(UTC).strftime("%Y-%m")

    lines = [
        {"ts": f"{today}T10:00:00", "path": "/v1/health", "status": 200, "ms": 12, "agent": "claude", "ip": "1.2.3.0", "paid": False},
        {"ts": f"{today}T10:01:00", "path": "/v1/company/context", "status": 402, "ms": 234, "agent": "openai", "ip": "5.6.7.0", "paid": False},
        {"ts": f"{today}T10:02:00", "path": "/v1/company/context", "status": 200, "ms": 180, "agent": "x402", "ip": "8.8.8.0", "paid": True},
        {"ts": f"{today}T10:03:00", "path": "/v1/health", "status": 200, "ms": 15, "agent": "claude", "ip": "1.2.3.0", "paid": False},
        {"ts": f"{today}T10:04:00", "path": "/v1/company/pulse", "status": 500, "ms": 5000, "agent": "empty", "ip": "unknown", "paid": False},
        {"ts": "2020-01-01T00:00:00", "path": "/v1/old", "status": 200, "ms": 1, "agent": "bot", "ip": "0.0.0.0", "paid": False},
    ]

    with TemporaryDirectory() as tmp:
        _write_log(Path(tmp), f"{month}.jsonl", lines)
        monkeypatch.setattr(
            type(m.data_paths), "logs_analytics",
            property(lambda s, d=Path(tmp): d),
        )

        resp = client.get("/v1/stats")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 5
        assert data["paid"] == 1
        assert data["avg_ms"] > 0
        assert data["p95_ms"] == 5000.0
        assert data["statuses"]["200"] == 3
        assert data["statuses"]["402"] == 1
        assert data["statuses"]["500"] == 1
        assert data["agents"]["claude"] == 2
        assert data["agents"]["x402"] == 1
        assert data["paths"]["/v1/health"] == 2
        assert data["paths"]["/v1/company/context"] == 2
        assert len(data["recent"]) == 5
