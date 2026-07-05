"""Route registry — auto-discovers endpoint modules from the filesystem.

Adding an endpoint = create a directory under ``endpoints/`` with an
``__init__.py`` that exports ``register(pay_to, network, free) -> dict``.

One broken endpoint never kills the others.
"""
import importlib
import logging
from pathlib import Path

from x402.http.types import RouteConfig

_logger = logging.getLogger(__name__)

_ENDPOINTS_PACKAGE = "omninexu.api.endpoints"


def collect_routes(
    pay_to: str, network: str, free_routes: set[str]
) -> dict[str, RouteConfig]:
    """Walk the endpoints directory and collect route definitions."""
    all_routes: dict[str, RouteConfig] = {}

    pkg_path = _endpoints_path()
    if pkg_path is None:
        return all_routes

    for child in sorted(pkg_path.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        _load_endpoint(child.name, pay_to, network, free_routes, all_routes)

    return all_routes


def _endpoints_path() -> Path | None:
    """Resolve the filesystem path to the endpoints package."""
    try:
        pkg = importlib.import_module(_ENDPOINTS_PACKAGE)
    except ImportError:
        return None
    pkg_dir = getattr(pkg, "__path__", None)
    if not pkg_dir:
        return None
    return Path(pkg_dir[0] if isinstance(pkg_dir, list) else pkg_dir)


def _load_endpoint(
    name: str,
    pay_to: str,
    network: str,
    free_routes: set[str],
    all_routes: dict[str, RouteConfig],
) -> None:
    """Import one endpoint module and collect its routes."""
    try:
        mod = importlib.import_module(f"{_ENDPOINTS_PACKAGE}.{name}")
    except ImportError:
        _logger.warning("x402: skip endpoint %s (import failed)", name)
        return

    register = getattr(mod, "register", None)
    if register is None:
        return

    try:
        routes = register(pay_to, network, free_routes)
    except Exception:
        _logger.exception("x402: endpoint %s.register() raised", name)
        return

    if routes:
        all_routes.update(routes)
