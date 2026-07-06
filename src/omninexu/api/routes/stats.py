"""Stats endpoint — aggregates analytics logs for the dashboard."""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from omninexu.config import data_paths

router = APIRouter()

# ── helpers ──────────────────────────────────────────────────

def _read_today() -> list[dict[str, Any]]:
    """Read today's analytics lines from the monthly JSONL file."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    log_path = data_paths.logs_analytics / f"{datetime.now(UTC):%Y-%m}.jsonl"
    if not log_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if today in line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return rows


def _p95(values: list[float]) -> float:
    """95th percentile of a sorted list."""
    if not values:
        return 0.0
    values.sort()
    return values[int(len(values) * 0.95)]


# ── endpoint ─────────────────────────────────────────────────

@router.get("/stats")
async def stats() -> dict[str, Any]:
    rows = _read_today()
    total = len(rows)

    # Status code distribution
    statuses: dict[str, int] = {}
    # Agent distribution
    agents: dict[str, int] = {}
    # Path distribution
    paths: dict[str, int] = {}
    # Response times
    times: list[float] = []
    # Paid count
    paid = 0
    # Recent
    recent: list[dict[str, Any]] = []

    for r in rows:
        s = str(r.get("status", 0))
        statuses[s] = statuses.get(s, 0) + 1
        a = r.get("agent", "other")
        agents[a] = agents.get(a, 0) + 1
        p = r.get("path", "/")
        paths[p] = paths.get(p, 0) + 1
        times.append(float(r.get("ms", 0)))
        if r.get("paid"):
            paid += 1
        if len(recent) < 20:
            recent.append(r)

    return {
        "total": total,
        "paid": paid,
        "avg_ms": round(sum(times) / total, 1) if total else 0,
        "p95_ms": round(_p95(times), 1),
        "statuses": dict(sorted(statuses.items(), key=lambda x: -x[1])),
        "agents": dict(sorted(agents.items(), key=lambda x: -x[1])),
        "paths": dict(sorted(paths.items(), key=lambda x: -x[1])),
        "recent": list(reversed(recent))[:10],
    }
