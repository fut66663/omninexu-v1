"""Dashboard — server-rendered HTML stats page."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from omninexu.api.routes.stats import _read_today, _p95

router = APIRouter()

STYLE = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;max-width:800px;margin:0 auto}
h1{font-size:22px;font-weight:600;margin-bottom:4px}
.sub{color:#64748b;font-size:13px;margin-bottom:24px}
.kpis{display:flex;gap:12px;margin-bottom:28px}
.kpi{flex:1;background:#1e293b;border-radius:10px;padding:16px;text-align:center}
.kpi .num{font-size:32px;font-weight:700;color:#38bdf8}
.kpi .lbl{font-size:12px;color:#64748b;margin-top:4px}
h2{font-size:14px;font-weight:600;margin:24px 0 10px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px}
.bar{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #1e293b}
.bar .name{flex:0 0 160px;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar .wrap{flex:1;height:18px;background:#1e293b;border-radius:4px;overflow:hidden}
.bar .fill{height:100%;border-radius:4px;transition:width .3s}
.bar .num{flex:0 0 44px;text-align:right;font-size:13px;font-weight:600}
.bad{color:#ef4444}.ok{color:#10b981}.warn{color:#f59e0b}
.recent{font-size:12px;font-family:monospace}
.recent .r{display:flex;gap:10px;padding:4px 0;border-bottom:1px solid #1e293b}
.recent .t{flex:0 0 140px;color:#64748b}
.recent .a{flex:0 0 56px;font-weight:600}
.recent .p{flex:0 0 160px;color:#38bdf8}
.refresh{color:#38bdf8;font-size:12px;text-decoration:none}
.status{display:flex;gap:8px;align-items:center}
.status .dot{width:8px;height:8px;border-radius:50%}
.updated{color:#64748b;font-size:12px;margin-top:40px;text-align:center}
"""

AGENT_COLORS = {
    "claude": "#8b5cf6", "openai": "#10b981", "google": "#f59e0b",
    "perplexity": "#06b6d4", "x402": "#ec4899", "bot": "#6b7280",
    "empty": "#475569", "other": "#94a3b8",
}
STATUS_COLORS = {"200": "#10b981", "402": "#f59e0b", "4": "#ef4444", "5": "#ef4444"}


def _status_color(s: str) -> str:
    if s in STATUS_COLORS:
        return STATUS_COLORS[s]
    return STATUS_COLORS.get(s[0], "#94a3b8")


def _bar_html(label: str, count: int, max_count: int, color: str) -> str:
    pct = (count / max_count * 100) if max_count else 0
    return f"""<div class="bar">
  <span class="name">{label}</span>
  <span class="wrap"><span class="fill" style="width:{max(pct,1)}%;background:{color}"></span></span>
  <span class="num">{count}</span>
</div>"""


def _time_ago(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        delta = datetime.now(UTC).replace(tzinfo=None) - dt.replace(tzinfo=None)
        if delta < timedelta(minutes=1): return "just now"
        if delta < timedelta(hours=1): return f"{int(delta.total_seconds()/60)}m ago"
        if delta < timedelta(days=1): return f"{int(delta.total_seconds()/3600)}h ago"
        return f"{delta.days}d ago"
    except Exception:
        return ""


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> str:
    rows = _read_today()
    total = len(rows)

    # Aggregate
    statuses: dict[str, int] = {}
    agents: dict[str, int] = {}
    paths: dict[str, int] = {}
    times: list[float] = []
    paid = 0
    recent: list[dict] = []

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
        if len(recent) < 15:
            recent.append(r)

    avg_ms = round(sum(times) / total, 1) if total else 0
    p95 = round(_p95(times), 1)

    # Sort
    top_agents = sorted(agents.items(), key=lambda x: -x[1])[:6]
    top_paths = sorted(paths.items(), key=lambda x: -x[1])[:8]
    max_agent = max((v for _, v in top_agents), default=1)
    max_path = max((v for _, v in top_paths), default=1)

    # Status summary
    ok_count = statuses.get("200", 0)
    paywall = statuses.get("402", 0)
    errors = sum(v for k, v in statuses.items() if k[0] in "45")

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>OmniNexu Stats</title>
<style>{STYLE}</style>
</head>
<body>
<h1>📊 OmniNexu API Stats</h1>
<p class="sub">api.omninexu.com · Analytics Dashboard · <a class="refresh" href="?refresh={int(datetime.now(UTC).timestamp())}">Refresh</a></p>

<div class="kpis">
  <div class="kpi"><div class="num">{total:,}</div><div class="lbl">Today's Calls</div></div>
  <div class="kpi"><div class="num">{paid:,}</div><div class="lbl">x402 Paid</div></div>
  <div class="kpi"><div class="num">{avg_ms}ms</div><div class="lbl">Avg Response</div></div>
  <div class="kpi"><div class="num">{p95}ms</div><div class="lbl">P95 Latency</div></div>
</div>

<h2>Status Codes</h2>
<div class="status">
  <span class="dot" style="background:#10b981"></span> <b>{ok_count}</b> OK
  <span class="dot" style="background:#f59e0b;margin-left:12px"></span> <b>{paywall}</b> 402 (paywall)
  <span class="dot" style="background:#ef4444;margin-left:12px"></span> <b>{errors}</b> Errors
</div>

<h2>Agent Distribution</h2>
{''.join(_bar_html(ag, cnt, max_agent, AGENT_COLORS.get(ag, '#94a3b8')) for ag, cnt in top_agents)}
{'<p style="color:#64748b;font-size:13px;margin-top:8px">No agent data yet</p>' if not top_agents else ''}

<h2>Endpoint Distribution</h2>
{''.join(_bar_html(p, cnt, max_path, '#38bdf8') for p, cnt in top_paths)}
{'<p style="color:#64748b;font-size:13px;margin-top:8px">No endpoint data yet</p>' if not top_paths else ''}

<h2>Recent Requests</h2>
<div class="recent">
{''.join(f'''<div class="r">
  <span class="t">{_time_ago(r.get('ts',''))}</span>
  <span class="a">{r.get('agent','?')}</span>
  <span class="p">{r.get('path','/')}</span>
  <span style="color:{_status_color(str(r.get('status',0)))}">{r.get('status')}</span>
  <span>{r.get('ms')}ms</span>
  {'💰' if r.get('paid') else ''}
</div>''' for r in reversed(recent))}
{'<p style="color:#64748b;padding:12px">No recent requests</p>' if not recent else ''}
</div>

<p class="updated">Updated: {now} · Auto-refresh: 60s · <a class="refresh" href="/v1/stats">JSON API</a></p>
<script>setTimeout(()=>location.reload(),60000)</script>
</body>
</html>"""
