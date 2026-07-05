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
            "summary": f"No insider transactions reported for {ticker} in the past 90 days.",
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
            f"过去90天内部人净{'买入' if net >= 0 else '卖出'} "
            f"（{buys}次买入 vs {sells}次卖出）"
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
            f"{holder_count}家机构持仓，前10大占比{concentration:.0%}，"
            f"机构关注度高"
        )
    elif holder_count >= 10:
        level, score = "neutral", SCORE_NEUTRAL
        summary = f"{holder_count}家机构持仓，前10大占比{concentration:.0%}"
    else:
        level, score = "neutral", SCORE_NEUTRAL
        summary = f"{holder_count}家机构持仓，覆盖面有限"

    return {
        "type": "institutional_flow",
        "level": level,
        "summary": summary,
        "score": score,
        "source": "SEC 13F",
    }


def _revenue_trend(ticker: str, repo: FinancialsRepository) -> dict[str, Any]:
    """Revenue year-over-year growth trajectory.

    Source: SimFin
    """
    facts = repo.get_facts(ticker)  # all years for trend comparison
    if not facts:
        return {
            "type": "revenue_trend",
            "level": "neutral",
            "summary": f"No revenue data available for {ticker}.",
            "score": SCORE_NEUTRAL,
            "source": "SimFin",
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
            "source": "SimFin",
        }

    revenues = sorted(revenue_by_period[best_period], key=lambda x: x[0])

    if len(revenues) < 2:
        return {
            "type": "revenue_trend",
            "level": "neutral",
            "summary": f"Insufficient revenue history for {ticker}.",
            "score": SCORE_NEUTRAL,
            "source": "SimFin",
        }

    # Sort by period, compare latest two
    revenues.sort(key=lambda x: x[0])
    _, older = revenues[-2]
    _, newer = revenues[-1]
    growth = (newer - older) / older if older > 0 else 0

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
            f"营收YoY增长{growth:.1%}"
            f"（${older/1e6:.0f}M → ${newer/1e6:.0f}M）"
        ),
        "score": score,
        "source": "SimFin",
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
            "summary": "最近30天无内部人交易记录。",
            "score": SCORE_NEUTRAL,
            "source": "SEC Form-4",
        }

    latest = trades[0]
    direction = "买入" if latest.transaction_type == "P" else "卖出"
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
            f"最近一笔交易: {name}（{latest.insider_title or 'N/A'}）"
            f"{direction} {latest.shares or 0:.0f}股"
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
                "summary": "宏观数据暂不可用（FRED API key 未配置）。",
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
                "summary": "无法获取联邦基金利率数据。",
                "score": SCORE_NEUTRAL,
                "source": "FRED",
            }

        unrate = (snap.get("UNRATE", {}) or {}).get("value")
        dgs10 = (snap.get("DGS10", {}) or {}).get("value")

        if fed_val >= 4.0:
            env = "紧缩"
            implication = "高利率环境：成长股承压，金融和能源板块受益"
        elif fed_val <= 2.0:
            env = "宽松"
            implication = "低利率环境：成长股和科技板块受益"
        else:
            env = "中性"
            implication = "利率适中：板块轮动取决于基本面"

        parts = [f"联邦基金利率 {fed_val}%（{env}）"]
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
            "summary": "宏观信号生成失败。",
            "score": SCORE_NEUTRAL,
            "source": "FRED",
        }


def _sector_relative(
    ticker: str, repo: FinancialsRepository, company: Any
) -> dict[str, Any]:
    """Sector-relative ranking signal.

    Compares revenue growth against peers in the same GICS sector.

    Source: SimFin (via DB)
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
            "summary": "行业分类数据不足，无法进行同行排名。",
            "score": SCORE_NEUTRAL,
            "source": "SimFin",
        }

    # Get revenue growth for this ticker
    facts = repo.get_facts(ticker)
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
            "summary": f"营收历史数据不足（{sector_name}行业）。",
            "score": SCORE_NEUTRAL,
            "source": "SimFin",
        }

    revenues.sort()
    growth = (revenues[-1][1] - revenues[-2][1]) / revenues[-2][1]

    return {
        "type": "sector_relative",
        "level": "positive" if growth > 0.05 else "neutral",
        "summary": (
            f"所属{sector_name}行业，营收YoY增长{growth:.1%}"
        ),
        "score": SCORE_POSITIVE if growth > 0.05 else SCORE_NEUTRAL,
        "source": "SimFin",
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
                "summary": "暂无同行对比数据，请先生成 context。",
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
                "summary": f"营收排名 {revenue_rank}/{total_peers}（前{pct:.0%}），行业同行对比。",
                "score": score,
                "source": "SimFin+SEC",
            }

        return {
            "type": "peer_comparison",
            "level": "neutral",
            "summary": "同行对比数据尚未生成，请先运行 product_store。",
            "score": SCORE_NEUTRAL,
            "source": "SimFin+SEC",
        }
    except Exception as exc:
        logger.warning(f"peer_comparison failed for {ticker}: {exc}")
        return {
            "type": "peer_comparison",
            "level": "neutral",
            "summary": "同行对比信号生成失败。",
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
