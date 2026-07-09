"""Company Context business logic."""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from omninexu.application.insider import build_insider_summary
from omninexu.application.institutional import build_institutional_summary
from omninexu.application.peer_comparison import build_peer_comparison
from omninexu.application.ranking import cagr, percentile_rank
from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.datasource import CompanyDataSource
from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.cache import CacheBackend, cache
from omninexu.infrastructure.clients import EdgarClient
from omninexu.infrastructure.repositories import (
    CompanyRepository,
    FinancialsRepository,
    InsiderRepository,
    InstitutionalRepository,
)
from omninexu.observability import (
    FinancialDataNotFoundError,
    TickerNotFoundError,
    get_logger,
)

logger = get_logger(__name__)

CACHE_TTL_SECONDS = 24 * 3600
CACHE_VERSION = "v5"  # +fiscal_period, +data_quality, +pulse confidence
# Maximum fiscal years to use for longitudinal calculations.
# SimFin provides FY2020+ (6-7 years); EDGAR supplements as available.
MAX_LONGITUDINAL_PERIODS = 10

CONCEPT_TO_KEY = {
    "Revenue": "revenue",
    "NetIncome": "net_income",
    "EPSDiluted": "eps_diluted",
    "GrossProfit": "gross_profit",
    "OperatingIncome": "operating_income",
    "TotalAssets": "total_assets",
    "TotalLiabilities": "total_liabilities",
    "StockholdersEquity": "stockholders_equity",
    "OperatingCashFlow": "operating_cash_flow",
}

LONGITUDINAL_CONCEPTS = [
    "Revenue", "NetIncome", "EPSDiluted",
    "OperatingIncome", "OperatingCashFlow",
]


class CompanyContextService:
    """Build Company Context responses."""

    def __init__(
        self,
        db: Session,
        data_source: CompanyDataSource | None = None,
        cache_backend: CacheBackend | None = None,
    ):
        self.db = db
        self.data_source = data_source or EdgarClient()
        self.cache = cache_backend or cache
        self.company_repo = CompanyRepository(db)
        self.financials_repo = FinancialsRepository(db)

    def build_context(
        self,
        ticker: str,
        include_peers: bool = True,
    ) -> dict[str, Any]:
        """Build full company context."""
        ticker_upper = ticker.upper()
        cache_key = f"company_context:{CACHE_VERSION}:{ticker_upper}"

        cached = self.cache.get_json(cache_key)
        if cached is not None:
            logger.info(f"Cache hit for {ticker_upper}")
            return dict(cached)

        logger.info(f"Cache miss for {ticker_upper}, building context")
        context = self._build_context_from_db(ticker_upper, include_peers)
        self.cache.set_json(cache_key, context, ttl=CACHE_TTL_SECONDS)
        return context

    def _build_context_from_db(
        self,
        ticker: str,
        include_peers: bool,
    ) -> dict[str, Any]:
        """Build context from database and Edgar fallback."""
        company = self._get_or_create_company(ticker)
        latest_facts = self.financials_repo.get_latest_facts(ticker)

        if not latest_facts:
            logger.warning(f"No financial data found for {ticker}")
            raise FinancialDataNotFoundError(f"{ticker}")

        peer_comparison = self._build_peer_comparison(company) if include_peers else None
        fundamentals = self._build_fundamentals(latest_facts)
        longitudinal = self._build_longitudinal(ticker)

        institutional = self._build_institutional(ticker)
        insider = self._build_insider(ticker)
        data_quality = self._build_data_quality(ticker, latest_facts)

        return {
            "ticker": company.ticker,
            "cik": company.cik,
            "name": company.name,
            "as_of_date": self._latest_report_date(latest_facts),
            "fundamentals": fundamentals,
            "longitudinal": longitudinal,
            "peer_comparison": peer_comparison,
            "institutional": (
                institutional.model_dump() if institutional is not None else None
            ),
            "insider": (
                insider.model_dump() if insider is not None else None
            ),
            "sources": self._build_sources(company.cik),
            "data_quality": data_quality,
            "confidence": self._compute_confidence(
                fundamentals=fundamentals,
                longitudinal=longitudinal,
                peer_comparison=peer_comparison,
                institutional=institutional,
                insider=insider,
            ),
        }

    def _get_or_create_company(self, ticker: str) -> Company:
        """Fetch company from DB or create from Edgar."""
        company = self.company_repo.get_by_ticker(ticker)
        if company is not None:
            return company

        logger.info(f"Company {ticker} not in DB, fetching from EDGAR")
        info = self._fetch_edgar_company_info(ticker)
        new_company = Company(
            ticker=info["ticker"],
            cik=info["cik"],
            name=info["name"],
            industry=IndustryClassification(),
        )
        return self.company_repo.create_or_update(new_company)

    def _fetch_edgar_company_info(self, ticker: str) -> dict[str, Any]:
        """Fetch company info from the data source.

        The data source (e.g. ``EdgarClient``) is responsible for converting
        provider-specific errors into domain exceptions.
        """
        info = self.data_source.get_company_info(ticker)
        if not info.get("cik"):
            raise TickerNotFoundError(f"{ticker}")
        return info

    @staticmethod
    def _build_fundamentals(facts: list[FinancialFact]) -> dict[str, dict[str, Any]]:
        """Convert latest facts to fundamentals dictionary."""
        fundamentals: dict[str, dict[str, Any]] = {}
        for fact in facts:
            key = CONCEPT_TO_KEY.get(fact.concept)
            if key is None:
                continue
            fundamentals[key] = {
                "value": fact.value,
                "unit": fact.unit,
                "fiscal_year": fact.fiscal_year,
                "fiscal_period": fact.fiscal_period,
                "source": fact.source,
            }
        return fundamentals

    @staticmethod
    def _latest_report_date(facts: list[FinancialFact]) -> date | None:
        """Return the most recent report date from facts."""
        if not facts:
            return None
        return max(f.report_date for f in facts)

    @staticmethod
    def _build_sources(cik: str) -> list[dict[str, str]]:
        """Build source links for 10-K, 10-Q, and 8-K filings."""
        base = (
            "https://www.sec.gov/cgi-bin/browse-edgar?"
            f"action=getcompany&CIK={cik}&dateb=&owner=exclude&count=5"
        )
        return [
            {"type": "10-K", "url": f"{base}&type=10-K"},
            {"type": "10-Q", "url": f"{base}&type=10-Q"},
            {"type": "8-K",  "url": f"{base}&type=8-K"},
        ]

    def _build_longitudinal(self, ticker: str) -> dict[str, float]:
        """Calculate CAGR and percentile rank for core metrics."""
        facts = self.financials_repo.get_facts(ticker)
        if not facts:
            return {}

        longitudinal: dict[str, float] = {}
        for concept in LONGITUDINAL_CONCEPTS:
            series = FinancialFact.to_series(facts, concept)
            if series is None or len(series) < 2:
                continue

            key = CONCEPT_TO_KEY.get(concept)
            if key is None:
                continue

            periods = min(MAX_LONGITUDINAL_PERIODS, len(series))
            longitudinal[f"{key}_cagr"] = cagr(series, periods)
            longitudinal[f"{key}_pct_rank"] = percentile_rank(series)

        return longitudinal

    def _build_peer_comparison(
        self,
        company: Company,
    ) -> dict[str, Any] | None:
        """Build peer comparison within the same GICS sub-industry."""
        sub_industry = company.industry.gics_sub_industry
        if not sub_industry:
            return None

        peers = self.company_repo.get_by_gics_sub_industry(sub_industry)
        return build_peer_comparison(
            company.ticker,
            sub_industry,
            peers,
            CONCEPT_TO_KEY,
            self.financials_repo.get_latest_facts,
        )

    @staticmethod
    def _compute_confidence(
        fundamentals: dict[str, Any],
        longitudinal: dict[str, float],
        peer_comparison: dict[str, Any] | None,
        institutional: Any | None,
        insider: Any | None,
    ) -> str:
        """Compute confidence level based on filled dimensions.

        Returns ``"high"`` when 5-6 dimensions are filled, ``"medium"``
        for 3-4, and ``"low"`` otherwise.
        """
        filled = sum(
            1 for v in (fundamentals, longitudinal, peer_comparison, institutional, insider)
            if v not in (None, {}, [])
        )
        if filled >= 5:
            return "high"
        if filled >= 3:
            return "medium"
        return "low"

    def _build_data_quality(
        self,
        ticker: str,
        facts: list[FinancialFact],
    ) -> dict[str, Any]:
        """Build data-quality metrics for the context response.

        Returns a dict with keys matching the ``DataQuality`` Pydantic model.
        """
        # 1. institutional_coverage — count total 13F holders
        inst_repo = InstitutionalRepository(self.db)
        holdings = inst_repo.get_holdings(ticker)
        holder_count = len(holdings)
        if holder_count >= 20:
            institutional_coverage = "full"
        elif holder_count >= 1:
            institutional_coverage = "partial"
        else:
            institutional_coverage = "missing"

        # 2. fiscal_period_labeled — every fact has a non-empty period
        fiscal_period_labeled = all(
            fact.fiscal_period and fact.fiscal_period.strip() != ""
            for fact in facts
        ) if facts else False

        # 3. cagr_reliability — based on distinct fiscal years
        all_facts = self.financials_repo.get_facts(ticker)
        distinct_years = len({f.fiscal_year for f in all_facts})
        if distinct_years >= 5:
            cagr_reliability = "high"
        elif distinct_years >= 3:
            cagr_reliability = "medium"
        else:
            cagr_reliability = "low"

        # 4. data_freshness_days — days since latest report_date
        latest = self._latest_report_date(facts)
        data_freshness_days = (date.today() - latest).days if latest else 0

        return {
            "institutional_coverage": institutional_coverage,
            "fiscal_period_labeled": fiscal_period_labeled,
            "cagr_reliability": cagr_reliability,
            "data_freshness_days": data_freshness_days,
        }

    def _build_institutional(self, ticker: str) -> Any:
        """Build institutional holdings summary from DB (13F data)."""
        return build_institutional_summary(ticker, InstitutionalRepository(self.db))

    def _build_insider(self, ticker: str) -> Any:
        """Build insider trading summary from DB (Form 4 data)."""
        return build_insider_summary(ticker, InsiderRepository(self.db))

    def invalidate_cache(self, ticker: str) -> None:
        """Remove cached context for a ticker."""
        cache_key = f"company_context:{CACHE_VERSION}:{ticker.upper()}"
        self.cache.delete(cache_key)
        logger.info(f"Invalidated cache for {ticker.upper()}")
