"""API middleware: request logging.

Logs every HTTP request as one JSON line in a monthly file under
``operations/logs/api/``.  Logging failures are silently swallowed
so they can never take down the API.
"""

import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime

from fastapi import Request, Response

from omninexu.config import data_paths
from omninexu.observability import get_logger

logger = get_logger(__name__)


async def log_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log every HTTP request as one JSON line in a monthly log file.

    Log format (one line per request)::

        {"timestamp":"...","method":"GET","path":"/v1/...",
         "query":"...","status":200,"duration_ms":12.3}
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    _write_line(request, response, duration_ms)
    return response


def _write_line(
    request: Request, response: Response, duration_ms: float
) -> None:
    """Append one JSON line to the monthly log file."""
    x402_paid = response.headers.get("PAYMENT-RESPONSE") is not None
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query or "",
        "status": response.status_code,
        "duration_ms": round(duration_ms, 1),
        "x402_paid": x402_paid,
    }

    log_dir = data_paths.logs_api
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{date.today():%Y-%m}.jsonl"

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        logger.warning(f"Failed to write request log to {log_path}")
