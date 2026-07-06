"""API layer."""

from omninexu.api.endpoints.filings import router as filings_router
from omninexu.api.endpoints.insider_trading import router as insider_router
from omninexu.api.endpoints.institutional import router as institutional_router
from omninexu.api.endpoints.longitudinal import router as longitudinal_router
from omninexu.api.endpoints.peer_ranking import router as peer_ranking_router
from omninexu.api.endpoints.smart_money import router as smart_money_router
from omninexu.api.routes.company import router as company_router
from omninexu.api.routes.dashboard import router as dashboard_router
from omninexu.api.routes.health import router as health_router
from omninexu.api.routes.stats import router as stats_router

__all__ = [
    "company_router",
    "dashboard_router",
    "filings_router",
    "health_router",
    "stats_router",
    "insider_router",
    "institutional_router",
    "longitudinal_router",
    "peer_ranking_router",
    "smart_money_router",
]
