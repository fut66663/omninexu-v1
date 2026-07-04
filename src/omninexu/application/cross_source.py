"""Cross-source data validation -- compare SimFin vs EDGAR financial facts.

Provides :class:`CrossSourceComparator` which queries both sources for the
same (ticker, fiscal_year, concept) and flags discrepancies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from omninexu.infrastructure.models import FinancialFactModel
from omninexu.observability import get_logger

logger = get_logger(__name__)

# -- core financial concepts compared across sources -----------------
CORE_CONCEPTS = [
    "Revenue",
    "NetIncome",
    "GrossProfit",
    "OperatingIncome",
    "TotalAssets",
    "TotalLiabilities",
    "StockholdersEquity",
    "OperatingCashFlow",
    "EPSDiluted",
]

# -- discrepancy severity thresholds ---------------------------------
_CRITICAL_THRESHOLD = 10.0   # diff > 10%
_WARNING_THRESHOLD = 2.0     # diff > 2%


@dataclass
class Discrepancy:
    """A single concept disagreement between two data sources.

    Attributes:
        ticker: Stock ticker symbol.
        concept: Financial concept name (e.g. ``"Revenue"``).
        fiscal_year: Fiscal year being compared.
        simfin_value: Value from SimFin (``None`` if missing).
        edgar_value: Value from EDGAR (``None`` if missing).
        diff_pct: Absolute percentage difference (``None`` if either
            source is missing or the base value is zero).
        severity: ``"critical"`` (>10%), ``"warning"`` (2-10%), or
            ``"info"`` (<2% or single-source only).
        source_priority: Which source is preferred -- ``"edgar"``
            (authoritative for 10-K data) or ``"simfin"``.
    """

    ticker: str
    concept: str
    fiscal_year: int
    simfin_value: float | None = None
    edgar_value: float | None = None
    diff_pct: float | None = None
    severity: Literal["critical", "warning", "info"] = "info"
    source_priority: str = "edgar"


@dataclass
class BatchResult:
    """Aggregate result for a batch cross-source comparison."""

    ticker: str
    discrepancies: list[Discrepancy] = field(default_factory=list)
    critical: int = 0
    warning: int = 0
    info: int = 0


class CrossSourceComparator:
    """Compare SimFin and EDGAR data for the same (ticker, year, concept).

    All methods are static -- callers provide their own DB session.
    """

    @staticmethod
    def compare_ticker(
        db: Session, ticker: str, fiscal_year: int
    ) -> list[Discrepancy]:
        """Return all discrepancies for *ticker* in *fiscal_year*.

        Queries ``financial_facts`` for both ``source='simfin'`` and
        ``source='edgar'``, then compares every concept in
        :data:`CORE_CONCEPTS`.
        """
        t = ticker.upper()

        # Load SimFin facts for this ticker+year.
        simfin_rows = db.execute(
            select(FinancialFactModel)
            .where(
                FinancialFactModel.ticker == t,
                FinancialFactModel.fiscal_year == fiscal_year,
                FinancialFactModel.source == "simfin",
                FinancialFactModel.concept.in_(CORE_CONCEPTS),
            )
        ).scalars().all()
        simfin_map: dict[str, float] = {r.concept: r.value for r in simfin_rows if r.value is not None}

        # Load EDGAR facts for this ticker+year.
        edgar_rows = db.execute(
            select(FinancialFactModel)
            .where(
                FinancialFactModel.ticker == t,
                FinancialFactModel.fiscal_year == fiscal_year,
                FinancialFactModel.source == "edgar",
                FinancialFactModel.concept.in_(CORE_CONCEPTS),
            )
        ).scalars().all()
        edgar_map: dict[str, float] = {r.concept: r.value for r in edgar_rows if r.value is not None}

        discrepancies: list[Discrepancy] = []
        for concept in CORE_CONCEPTS:
            sv = simfin_map.get(concept)
            ev = edgar_map.get(concept)
            diff = CrossSourceComparator._compute_diff(sv, ev)
            severity = CrossSourceComparator._classify(diff)
            discrepancies.append(
                Discrepancy(
                    ticker=t,
                    concept=concept,
                    fiscal_year=fiscal_year,
                    simfin_value=sv,
                    edgar_value=ev,
                    diff_pct=diff,
                    severity=severity,
                )
            )

        return discrepancies

    @staticmethod
    def compare_batch(
        db: Session, tickers: list[str], fiscal_year: int
    ) -> list[BatchResult]:
        """Compare *tickers* in batch, returning one result per ticker."""
        results: list[BatchResult] = []
        for ticker in tickers:
            disc = CrossSourceComparator.compare_ticker(db, ticker, fiscal_year)
            br = BatchResult(ticker=ticker, discrepancies=disc)
            for d in disc:
                if d.severity == "critical":
                    br.critical += 1
                elif d.severity == "warning":
                    br.warning += 1
                else:
                    br.info += 1
            results.append(br)

        # Summary log.
        total_crit = sum(r.critical for r in results)
        total_warn = sum(r.warning for r in results)
        if total_crit or total_warn:
            logger.warning(
                "Cross-source: %d critical, %d warning across %d tickers",
                total_crit, total_warn, len(tickers),
            )
        else:
            logger.info(
                "Cross-source: all clear across %d tickers", len(tickers)
            )
        return results

    # -- internal helpers ----------------------------------------------

    @staticmethod
    def _compute_diff(
        simfin: float | None, edgar: float | None
    ) -> float | None:
        """Return absolute percentage difference between two values.

        Uses the larger absolute value as denominator to avoid division
        by zero.  Returns ``None`` when a comparison is impossible.
        """
        if simfin is None or edgar is None:
            return None
        denom = max(abs(simfin), abs(edgar))
        if denom == 0:
            return None
        return round(abs(simfin - edgar) / denom * 100, 2)

    @staticmethod
    def _classify(
        diff_pct: float | None,
    ) -> Literal["critical", "warning", "info"]:
        """Classify severity of a cross-source percentage difference.

        Returns ``"info"`` when *diff_pct* is ``None`` (one source
        missing or denominator zero).
        """
        if diff_pct is None:
            return "info"
        if diff_pct > _CRITICAL_THRESHOLD:
            return "critical"
        if diff_pct > _WARNING_THRESHOLD:
            return "warning"
        return "info"
