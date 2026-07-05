"""Paid endpoint modules — one directory per endpoint.

Each subdirectory is a self-contained plugin that exports:
    register(pay_to, network, free) -> dict[str, RouteConfig] | None
"""
