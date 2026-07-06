"""Analytics middleware — stats telemetry, independent of logging.py.

Writes one JSON line per request to ``operations/logs/analytics/YYYY-MM.jsonl``.
"""
import base64
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime

from fastapi import Request, Response

from omninexu.config import data_paths

# ── helpers ──────────────────────────────────────────────────

def _mask_ip(ip: str) -> str:
    """Zero last octet: 1.2.3.4 → 1.2.3.0"""
    parts = ip.rsplit(".", 1)
    return f"{parts[0]}.0" if len(parts) == 2 else ip


def _classify(ua: str) -> str:
    """User-Agent → short label."""
    ua = ua.lower()
    if "claude" in ua or "anthropic" in ua:
        return "claude"
    if "gptbot" in ua or "chatgpt" in ua or "openai" in ua:
        return "openai"
    if "googlebot" in ua or "gemini" in ua:
        return "google"
    if "perplexity" in ua:
        return "perplexity"
    if "agentic" in ua or "x402" in ua:
        return "x402"
    if not ua:
        return "empty"
    if "bot" in ua or "crawler" in ua or "spider" in ua:
        return "bot"
    return "other"


def _decode_payment(header: str) -> dict[str, str] | None:
    """Decode base64 PAYMENT-RESPONSE → {payer, tx, network}."""
    try:
        payload = json.loads(base64.b64decode(header + "=="))
        return {
            "payer": payload.get("payer", "")[:14] + "...",
            "tx": payload.get("transaction", "")[:14] + "...",
        }
    except Exception:
        return None


# ── middleware ───────────────────────────────────────────────

async def track_analytics(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - start) * 1000, 1)

    ua = request.headers.get("user-agent", "")
    ip = request.headers.get(
        "x-forwarded-for",
        request.client.host if request.client else "unknown",
    )
    ip = ip.split(",")[0].strip()

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "path": request.url.path,
        "status": response.status_code,
        "ms": ms,
        "agent": _classify(ua),
        "ip": _mask_ip(ip),
        "paid": response.headers.get("PAYMENT-RESPONSE") is not None,
    }

    # Attach payment details when paid
    pay_header = response.headers.get("PAYMENT-RESPONSE")
    if pay_header:
        details = _decode_payment(pay_header)
        if details:
            entry["payer"] = details["payer"]
            entry["tx"] = details["tx"]

    log_dir = data_paths.logs_analytics
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        with (log_dir / f"{date.today():%Y-%m}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return response
