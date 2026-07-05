"""Tests for CompanyDataSource Protocol contract and error boundaries."""

from unittest.mock import patch

import httpx
import pytest
from edgar import CompanyNotFoundError

from omninexu.infrastructure.clients import EdgarClient
from omninexu.observability import EdgarRateLimitError, TickerNotFoundError


class TestProtocolCompliance:
    """Every data source must satisfy the CompanyDataSource Protocol."""

    def test_edgar_client_has_required_methods(self) -> None:
        """EdgarClient must expose get_company_info and get_financial_facts."""
        client = EdgarClient()
        assert callable(client.get_company_info)
        assert callable(client.get_financial_facts)

    def test_fake_data_source_has_required_methods(self) -> None:
        """FakeDataSource must expose the same interface."""
        from tests.fakes import FakeDataSource

        ds = FakeDataSource()
        assert callable(ds.get_company_info)
        assert callable(ds.get_financial_facts)

    def test_failing_data_source_has_required_methods(self) -> None:
        """FailingDataSource must expose the same interface."""
        from tests.fakes import FailingDataSource

        ds = FailingDataSource()
        assert callable(ds.get_company_info)
        assert callable(ds.get_financial_facts)

    def test_fake_data_source_company_info_shape(self) -> None:
        """get_company_info must return a dict with ticker, cik, name, sic."""
        from tests.fakes import FakeDataSource

        ds = FakeDataSource()
        info = ds.get_company_info("AAPL")
        assert isinstance(info, dict)
        assert "ticker" in info
        assert "cik" in info
        assert "name" in info
        assert "sic" in info


class TestErrorBoundary:
    """edgartools exceptions must never escape the infrastructure layer."""

    def test_get_company_info_converts_not_found(self) -> None:
        """CompanyNotFoundError → TickerNotFoundError in get_company_info."""
        client = EdgarClient()
        with (
            patch(
                "omninexu.infrastructure.clients.edgar_client.Company",
                side_effect=CompanyNotFoundError("INVALID"),
            ),
            pytest.raises(TickerNotFoundError),
        ):
            client.get_company_info("INVALID")

    def test_get_company_info_converts_http_error(self) -> None:
        """httpx.HTTPError → EdgarRateLimitError in get_company_info."""
        client = EdgarClient()

        def raise_http_error(*_args, **_kwargs):
            raise httpx.HTTPError("rate limit")

        with (
            patch(
                "omninexu.infrastructure.clients.edgar_client.Company",
                side_effect=raise_http_error,
            ),
            pytest.raises(EdgarRateLimitError),
        ):
            client.get_company_info("AAPL")

    def test_get_financial_facts_converts_not_found(self) -> None:
        """CompanyNotFoundError → TickerNotFoundError in get_financial_facts."""
        client = EdgarClient()
        with (
            patch(
                "omninexu.infrastructure.clients.edgar_client.Company",
                side_effect=CompanyNotFoundError("INVALID"),
            ),
            pytest.raises(TickerNotFoundError),
        ):
            client.get_financial_facts("INVALID")

    def test_get_financial_facts_converts_http_error(self) -> None:
        """httpx.HTTPError → EdgarRateLimitError in get_financial_facts."""
        client = EdgarClient()

        def raise_http_error(*_args, **_kwargs):
            raise httpx.HTTPError("rate limit")

        with (
            patch(
                "omninexu.infrastructure.clients.edgar_client.Company",
                side_effect=raise_http_error,
            ),
            pytest.raises(EdgarRateLimitError),
        ):
            client.get_financial_facts("AAPL")


class TestNoEdgarLeak:
    """The application layer must never import edgartools directly."""

    def test_application_layer_no_edgar_import(self) -> None:
        """No file under application/ may import from edgar."""
        import ast
        from pathlib import Path

        app_dir = Path("src/omninexu/application")
        violations: list[str] = []
        for py_file in app_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.startswith("edgar")
                ):
                    violations.append(f"{py_file.name}: from {node.module} import ...")
        assert not violations, (
            "edgartools leaked into application layer:\n" + "\n".join(violations)
        )
