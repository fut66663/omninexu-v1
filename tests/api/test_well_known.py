"""x402 discovery endpoint tests."""

from fastapi.testclient import TestClient


def test_well_known_returns_catalog(client: TestClient) -> None:
    """GET /.well-known/x402 returns endpoint catalog."""
    resp = client.get("/.well-known/x402")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "OmniNexu"
    assert data["version"] == "0.1.0"
    assert "payment" in data
    assert "network" in data["payment"]
    assert "pay_to" in data["payment"]
    assert "endpoints" in data
    assert isinstance(data["endpoints"], list)
    assert len(data["endpoints"]) == 8


def test_well_known_endpoints_have_prices(client: TestClient) -> None:
    """Every listed endpoint has path, price, description."""
    resp = client.get("/.well-known/x402")
    data = resp.json()
    for ep in data["endpoints"]:
        assert "path" in ep
        assert "price" in ep
        assert "description" in ep
        assert ep["path"].startswith("/v1/")
        assert ep["price"].startswith("$")
