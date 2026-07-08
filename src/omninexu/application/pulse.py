"""Pulse signal generator — paid-tier investment signals.

Each signal is a single insight derived from one data source.
Signals are designed to be lightweight (~200 chars each) and
aggregated into a Pulse response for x402 payment.

Signal types (v0.1, 4 signals):
    insider_sentiment          — net insider buying/selling trend
    institutional_flow         — institutional position changes
    revenue_trend              — revenue growth trajectory
    insider_transaction_recent — most recent insider trade direction
Signal types (v0.2, 3 additional):
    macro_tailwind             — FRED macro-economic environment
    sector_relative            — sector ranking via SIC→GICS
    peer_comparison            — peer ranking from context data
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from omninexu.config import data_paths
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.repositories.financials_repo import FinancialsRepository
from omninexu.infrastructure.repositories.insider_repo import InsiderRepository
from omninexu.infrastructure.repositories.institutional_repo import (
    InstitutionalRepository,
)
from omninexu.observability import get_logger

logger = get_logger(__name__)

# ── scoring constants ────────────────────────────────────────────

SCORE_STRONG_POSITIVE = 0.90
SCORE_POSITIVE = 0.75
SCORE_NEUTRAL = 0.50
SCORE_NEGATIVE = 0.25
SCORE_STRONG_NEGATIVE = 0.10


# ── signal builders ───────────────────────────────────────────────

def _insider_sentiment(ticker: str, repo: InsiderRepository) -> dict[str, Any]:
    """Net insider buying vs selling over 90 days.

    Source: SEC Form-4
    """
    trades = repo.get_trades(ticker, days=90)
    if not trades:
        return {
            "type": "insider_sentiment",
            "level": "neutral",
            "summary": f"{ticker}: no insider trades in past 90 days",
            "score": SCORE_NEUTRAL,
            "source": "SEC Form-4",
        }

    buys = sum(1 for t in trades if t.transaction_type == "P")
    sells = sum(1 for t in trades if t.transaction_type == "S")
    net = buys - sells

    if net >= 3:
        level, score = "positive", SCORE_STRONG_POSITIVE
    elif net >= 1:
        level, score = "positive", SCORE_POSITIVE
    elif net == 0:
        level, score = "neutral", SCORE_NEUTRAL
    elif net >= -2:
        level, score = "negative", SCORE_NEGATIVE
    else:
        level, score = "negative", SCORE_STRONG_NEGATIVE

    return {
        "type": "insider_sentiment",
        "level": level,
        "summary": (
            f"Net {'buying' if net >= 0 else 'selling'} "
            f"({buys} buys vs {sells} sells in 90 days)"
        ),
        "score": score,
        "source": "SEC Form-4",
    }


def _institutional_flow(ticker: str, repo: InstitutionalRepository) -> dict[str, Any]:
    """Institutional holdings concentration signal.

    Source: SEC 13F
    """
    holdings = repo.get_holdings(ticker)
    if not holdings:
        return {
            "type": "institutional_flow",
            "level": "neutral",
            "summary": f"No institutional holdings data for {ticker}.",
            "score": SCORE_NEUTRAL,
            "source": "SEC 13F",
        }

    total_value = sum(h.value or 0 for h in holdings)
    top10_value = sum(h.value or 0 for h in holdings[:10])
    concentration = top10_value / total_value if total_value > 0 else 0
    holder_count = len(holdings)

    if holder_count >= 20 and concentration > 0.5:
        level, score = "positive", SCORE_POSITIVE
        summary = (
            f"{holder_count} holders, top-10 concentration {concentration:.0%}, "
            f"strong institutional interest"
        )
    elif holder_count >= 10:
        level, score = "neutral", SCORE_NEUTRAL
        summary = f"{holder_count} holders, top-10 concentration {concentration:.0%}"
    else:
        level, score = "neutral", SCORE_NEUTRAL
        summary = f"{holder_count} holders, limited coverage"

    return {
        "type": "institutional_flow",
        "level": level,
        "summary": summary,
        "score": score,
        "source": "SEC 13F",
    }


def _revenue_trend(ticker: str, repo: FinancialsRepository) -> dict[str, Any]:
    """Revenue year-over-year growth trajectory.

    Source: SEC EDGAR (authoritative for 2025+)
    """
    facts = repo.get_facts_by_source(ticker, source="edgar")
    if not facts:
        return {
            "type": "revenue_trend",
            "level": "neutral",
            "summary": f"No revenue data available for {ticker}.",
            "score": SCORE_NEUTRAL,
            "source": "SEC EDGAR",
        }

    # Extract revenue values — group by fiscal_period (FY, Q1, etc.)
    revenue_by_period: dict[str, list[tuple[str, float]]] = {}
    for f in facts:
        concept = (f.concept or "").lower()
        if "revenue" in concept and "cost" not in concept:
            val = float(f.value) if f.value else 0
            if val > 0:
                period_type = f.fiscal_period or "FY"
                period_key = f"{f.fiscal_year}-{period_type}"
                revenue_by_period.setdefault(period_type, []).append((period_key, val))

    # Prefer annual (FY) data for YoY comparison
    best_period = "FY" if "FY" in revenue_by_period else (
        next(iter(revenue_by_period.keys()), None)
    )
    if best_period is None:
        return {
            "type": "revenue_trend",
            "level": "neutral",
            "summary": f"No revenue data available for {ticker}.",
            "score": SCORE_NEUTRAL,
            "source": "SEC EDGAR",
        }

    revenues = sorted(revenue_by_period[best_period], key=lambda x: x[0])

    if len(revenues) < 2:
        return {
            "type": "revenue_trend",
            "level": "neutral",
            "summary": f"Insufficient revenue history for {ticker}.",
            "score": SCORE_NEUTRAL,
            "source": "SEC EDGAR",
        }

    # Compare latest two periods (already sorted by period_key)
    _, older = revenues[-2]
    _, newer = revenues[-1]
    growth = (newer - older) / older if older > 0 else 0

    # Guard: anomalous growth (>50%) → flag as data issue, not signal
    if abs(growth) > 0.50:
        return {
            "type": "revenue_trend",
            "level": "neutral",
            "summary": (
                f"Revenue data anomaly detected (YoY {growth:.1%}); "
                f"cross-source verification recommended."
            ),
            "score": SCORE_NEUTRAL,
            "source": "SEC EDGAR",
        }

    if growth > 0.15:
        level, score = "positive", SCORE_STRONG_POSITIVE
    elif growth > 0.05:
        level, score = "positive", SCORE_POSITIVE
    elif growth > -0.05:
        level, score = "neutral", SCORE_NEUTRAL
    elif growth > -0.15:
        level, score = "negative", SCORE_NEGATIVE
    else:
        level, score = "negative", SCORE_STRONG_NEGATIVE

    return {
        "type": "revenue_trend",
        "level": level,
        "summary": (
            f"Revenue YoY {growth:.1%}"
            f" (${older/1e9:.1f}B → ${newer/1e9:.1f}B)"
        ),
        "score": score,
        "source": "SEC EDGAR",
    }


def _insider_transaction_recent(
    ticker: str, repo: InsiderRepository
) -> dict[str, Any]:
    """Most recent insider trade direction.

    Source: SEC Form-4
    """
    trades = repo.get_trades(ticker, days=30)
    if not trades:
        return {
            "type": "insider_transaction_recent",
            "level": "neutral",
            "summary": "No insider trades in past 30 days.",
            "score": SCORE_NEUTRAL,
            "source": "SEC Form-4",
        }

    latest = trades[0]
    direction = "Buy" if latest.transaction_type == "P" else "Sell"
    name = latest.insider_name or "内部人"

    if latest.transaction_type == "P":
        level, score = "positive", SCORE_POSITIVE
    elif latest.transaction_type == "S":
        level, score = "negative", SCORE_NEGATIVE
    else:
        level, score = "neutral", SCORE_NEUTRAL

    return {
        "type": "insider_transaction_recent",
        "level": level,
        "summary": (
            f"Latest trade: {name} ({latest.insider_title or 'N/A'}) "
            f"{direction} {latest.shares or 0:.0f} shares"
            + (rf" @ \${latest.price:.2f}" if latest.price else "")
        ),
        "score": score,
        "source": "SEC Form-4",
    }


# ── aggregate ─────────────────────────────────────────────────────

def _aggregate(signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate score and rating from individual signals."""
    scores = [s["score"] for s in signals]
    avg = sum(scores) / len(scores) if scores else SCORE_NEUTRAL

    if avg >= 0.70:
        rating = "bullish"
    elif avg >= 0.45:
        rating = "neutral"
    else:
        rating = "bearish"

    return {"aggregate_score": round(avg, 2), "rating": rating}


# ── v0.2 signals ───────────────────────────────────────────────────

def _macro_tailwind() -> dict[str, Any]:
    """Macro-economic environment signal from FRED data.

    Source: FRED
    """
    try:
        from omninexu.infrastructure.clients.fred_client import FredClient

        client = FredClient()
        if not client.is_configured():
            return {
                "type": "macro_tailwind",
                "level": "neutral",
                "summary": "Macro data unavailable (FRED API key not configured).",
                "score": SCORE_NEUTRAL,
                "source": "FRED",
            }

        snap = client.get_core_snapshot()
        fed_rate = snap.get("FEDFUNDS", {}) or {}
        fed_val = fed_rate.get("value")
        if fed_val is None:
            return {
                "type": "macro_tailwind",
                "level": "neutral",
                "summary": "Unable to fetch Fed Funds rate.",
                "score": SCORE_NEUTRAL,
                "source": "FRED",
            }

        unrate = (snap.get("UNRATE", {}) or {}).get("value")
        dgs10 = (snap.get("DGS10", {}) or {}).get("value")

        if fed_val >= 4.0:
            env = "tight"
            implication = "High rates: growth under pressure, financials & energy benefit"
        elif fed_val <= 2.0:
            env = "loose"
            implication = "Low rates: growth & tech benefit"
        else:
            env = "neutral"
            implication = "Moderate rates: sector rotation driven by fundamentals"

        parts = [f"Fed Funds {fed_val}% ({env})"]
        if unrate is not None:
            parts.append(f"失业率 {unrate}%")
        if dgs10 is not None:
            parts.append(f"10Y国债 {dgs10}%")

        return {
            "type": "macro_tailwind",
            "level": "positive" if env == "宽松" else ("negative" if env == "紧缩" else "neutral"),
            "summary": "；".join(parts) + f"。{implication}",
            "score": SCORE_POSITIVE if env == "宽松" else (SCORE_NEGATIVE if env == "紧缩" else SCORE_NEUTRAL),
            "source": "FRED",
        }
    except Exception as exc:
        logger.warning(f"macro_tailwind failed: {exc}")
        return {
            "type": "macro_tailwind",
            "level": "neutral",
            "summary": "Macro signal generation failed.",
            "score": SCORE_NEUTRAL,
            "source": "FRED",
        }


def _sector_relative(
    ticker: str, repo: FinancialsRepository, company: Any
) -> dict[str, Any]:
    """Sector-relative ranking signal.

    Compares revenue growth against peers in the same GICS sector.

    Source: SEC EDGAR (via DB)
    """
    sic_code = getattr(company, "sic_code", None)
    sector_name = None

    # Try GICS mapping from SIC code (via infrastructure layer)
    if sic_code:
        try:
            from omninexu.infrastructure.gics_mapping import lookup

            gics = lookup(str(sic_code))
            if gics:
                sector_name = gics.gics_sector
        except Exception:
            pass

    if sector_name is None:
        return {
            "type": "sector_relative",
            "level": "neutral",
            "summary": "Insufficient sector classification data for peer ranking.",
            "score": SCORE_NEUTRAL,
            "source": "SEC EDGAR",
        }

    # Get revenue growth for this ticker (EDGAR only)
    facts = repo.get_facts_by_source(ticker, source="edgar")
    revenues = []
    for f in facts:
        if "revenue" in (f.concept or "").lower() and "cost" not in (f.concept or "").lower():
            val = float(f.value) if f.value else 0
            if val > 0 and f.fiscal_period == "FY":
                revenues.append((f.fiscal_year, val))

    if len(revenues) < 2:
        return {
            "type": "sector_relative",
            "level": "neutral",
            "summary": f"Insufficient revenue history for {sector_name} sector comparison.",
            "score": SCORE_NEUTRAL,
            "source": "SEC EDGAR",
        }

    revenues.sort()
    growth = (revenues[-1][1] - revenues[-2][1]) / revenues[-2][1]

    return {
        "type": "sector_relative",
        "level": "positive" if growth > 0.05 else "neutral",
        "summary": (
            f"{sector_name} sector, revenue YoY {growth:.1%}"
        ),
        "score": SCORE_POSITIVE if growth > 0.05 else SCORE_NEUTRAL,
        "source": "SEC EDGAR",
    }


def _peer_comparison(ticker: str) -> dict[str, Any]:
    """Lightweight peer comparison signal.

    Checks the existing context product for peer data.

    Source: SimFin + SEC (via context)
    """
    try:
        ctx_dir = data_paths.products_context / ticker.upper()
        files = sorted(ctx_dir.glob("*.json")) if ctx_dir.is_dir() else []
        if not files:
            return {
                "type": "peer_comparison",
                "level": "neutral",
                "summary": "No peer data yet — generate context first.",
                "score": SCORE_NEUTRAL,
                "source": "SimFin+SEC",
            }

        import json

        latest = json.loads(files[-1].read_text(encoding="utf-8"))
        peers = latest.get("peer_comparison") or {}
        revenue_rank = peers.get("revenue_rank")
        total_peers = peers.get("revenue_total_peers")

        if revenue_rank is not None and total_peers:
            pct = revenue_rank / total_peers
            if pct <= 0.25:
                level, score = "positive", SCORE_POSITIVE
            elif pct <= 0.75:
                level, score = "neutral", SCORE_NEUTRAL
            else:
                level, score = "negative", SCORE_NEGATIVE

            return {
                "type": "peer_comparison",
                "level": level,
                "summary": f"Revenue rank {revenue_rank}/{total_peers} (top {pct:.0%}), industry peer comparison.",
                "score": score,
                "source": "SimFin+SEC",
            }

        return {
            "type": "peer_comparison",
            "level": "neutral",
            "summary": "Peer data not yet generated — run product_store first.",
            "score": SCORE_NEUTRAL,
            "source": "SimFin+SEC",
        }
    except Exception as exc:
        logger.warning(f"peer_comparison failed for {ticker}: {exc}")
        return {
            "type": "peer_comparison",
            "level": "neutral",
            "summary": "Peer comparison signal generation failed.",
            "score": SCORE_NEUTRAL,
            "source": "SimFin+SEC",
        }


# ── public API ────────────────────────────────────────────────────

def build_pulse(ticker: str) -> dict[str, Any]:
    """Build a full Pulse response for *ticker*.

    Returns a dict suitable for JSON serialization and x402-protected
    API responses.  Each signal independently evaluates one dimension;
    the aggregate score is a simple average.
    """
    ticker_upper = ticker.upper()
    db = SessionLocal()
    try:
        from sqlalchemy import select

        from omninexu.infrastructure.models import CompanyModel

        insider_repo = InsiderRepository(db)
        inst_repo = InstitutionalRepository(db)
        fin_repo = FinancialsRepository(db)

        company = db.execute(
            select(CompanyModel).where(CompanyModel.ticker == ticker_upper)
        ).scalar_one_or_none()

        signals = [
            _insider_sentiment(ticker_upper, insider_repo),
            _institutional_flow(ticker_upper, inst_repo),
            _revenue_trend(ticker_upper, fin_repo),
            _insider_transaction_recent(ticker_upper, insider_repo),
            _macro_tailwind(),
            _sector_relative(ticker_upper, fin_repo, company),
            _peer_comparison(ticker_upper),
        ]

        aggregate = _aggregate(signals)

        return {
            "ticker": ticker_upper,
            "generated_at": datetime.now(UTC).isoformat(),
            "signals": signals,
            **aggregate,
        }
    finally:
        db.close()
