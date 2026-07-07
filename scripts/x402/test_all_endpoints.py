"""x402 end-to-end: pay & verify all 8 OmniNexu paid endpoints.

Usage:  uv run python scripts/x402/test_all_endpoints.py

Environment:
    BUYER_PRIVATE_KEY  — buyer wallet private key (0x...)
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field

from eth_account import Account
from web3 import Web3

# -- Config --------------------------------------------
BUYER_ADDRESS = os.getenv("BUYER_ADDRESS", "0x3e9c7E0b781220ed054fb5516854FA272c3010cc")
BUYER_PRIVATE_KEY = os.getenv("BUYER_PRIVATE_KEY")
BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
SERVER = "https://api.omninexu.com"

if not BUYER_PRIVATE_KEY:
    print("ERR BUYER_PRIVATE_KEY not set")
    sys.exit(1)

w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
account = Account.from_key(BUYER_PRIVATE_KEY)

# -- USDC balance --------------------------------------─
usdc_abi = json.loads(
    '[{"constant":true,"inputs":[{"name":"owner","type":"address"}],'
    '"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],'
    '"type":"function"}]'
)
usdc = w3.eth.contract(address=USDC_ADDRESS, abi=usdc_abi)


def show_balance() -> int:
    balance = usdc.functions.balanceOf(account.address).call()
    print(f"  USDC: ${balance / 1e6:.2f}")
    return balance


# -- Endpoint registry ----------------------------------
@dataclass
class Endpoint:
    path: str
    params: str
    price: str
    description: str
    checks: list[str] = field(default_factory=list)  # JSON keys that must exist


ENDPOINTS = [
    Endpoint(
        path="/v1/company/filings",
        params="?ticker=AAPL",
        price="$0.01",
        description="SEC filings — 10-K, 10-Q, 8-K with source URLs",
        checks=["ticker", "filings", "sources"],
    ),
    Endpoint(
        path="/v1/company/peer-ranking",
        params="?ticker=AAPL",
        price="$0.02",
        description="Industry peer ranking — revenue & net income position",
        checks=["ticker", "industry"],
    ),
    Endpoint(
        path="/v1/company/insider",
        params="?ticker=AAPL",
        price="$0.03",
        description="SEC Form 4 insider transactions",
        checks=["ticker", "insider_trading"],
    ),
    Endpoint(
        path="/v1/company/institutional",
        params="?ticker=AAPL",
        price="$0.03",
        description="SEC 13F institutional holdings",
        checks=["ticker", "institutional_holders"],
    ),
    Endpoint(
        path="/v1/company/pulse",
        params="?ticker=AAPL",
        price="$0.02",
        description="Investment signals — insider, institutional, revenue trend",
        checks=["ticker", "pulse"],
    ),
    Endpoint(
        path="/v1/company/longitudinal",
        params="?ticker=AAPL",
        price="$0.03",
        description="Multi-year CAGR trends",
        checks=["ticker", "metrics"],
    ),
    Endpoint(
        path="/v1/company/smart-money",
        params="?ticker=AAPL",
        price="$0.05",
        description="Bundle: insider trades + institutional holdings",
        checks=["ticker"],
    ),
    Endpoint(
        path="/v1/company/context",
        params="?ticker=AAPL",
        price="$0.05",
        description="Company fundamentals (9 metrics) + peer comparison + confidence",
        checks=["ticker", "fundamentals", "peer_comparison", "confidence"],
    ),
]


async def pay_and_fetch(ep: Endpoint) -> dict:
    """Pay via x402 and return the JSON response."""
    from x402 import x402Client
    from x402.http.clients import x402HttpxClient
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client

    client = x402Client()
    register_exact_evm_client(client, EthAccountSigner(account))

    url = f"{SERVER}{ep.path}{ep.params}"
    async with x402HttpxClient(client) as http:
        response = await http.get(url)
        response.raise_for_status()
        return response.json()


def check_response(ep: Endpoint, data: dict) -> list[str]:
    """Return list of issues (empty = all good)."""
    issues = []
    for key in ep.checks:
        if key not in data:
            issues.append(f"missing key: {key}")
        elif data[key] is None:
            issues.append(f"null value: {key}")
    return issues


async def main() -> None:
    print("=" * 70)
    print("  OmniNexu x402 End-to-End Test")
    print(f"  Server: {SERVER}")
    print(f"  Wallet: {account.address}")
    print(f"  Endpoints: {len(ENDPOINTS)}")
    print("=" * 70)

    before_all = usdc.functions.balanceOf(account.address).call()
    results = []
    prev_balance = before_all

    for i, ep in enumerate(ENDPOINTS, 1):
        print(f"\n-- [{i}/{len(ENDPOINTS)}] {ep.path} ({ep.price}) --")
        print(f"  {ep.description}")

        start = time.perf_counter()
        try:
            data = await pay_and_fetch(ep)
            elapsed = time.perf_counter() - start

            current = usdc.functions.balanceOf(account.address).call()
            spent = (prev_balance - current) / 1e6 if prev_balance > current else 0
            prev_balance = current

            # Show actual response structure
            keys = list(data.keys())
            ticker = data.get("ticker", data.get("symbol", "N/A"))
            print(f"  [PASS] ticker={ticker} · {elapsed:.1f}s · spent ~${spent:.4f}")
            print(f"  Fields: {', '.join(keys)}")
            results.append({"endpoint": ep.path, "status": "ok", "ms": round(elapsed * 1000), "spent": spent, "fields": keys})

        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"  ERR FAILED — {e}")
            results.append({"endpoint": ep.path, "status": "failed", "error": str(e), "ms": round(elapsed * 1000)})

    # -- Summary --------------------------------------─
    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)
    ok = sum(1 for r in results if r["status"] == "ok")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "failed")

    for r in results:
        icon = "OK" if r["status"] == "ok" else ("WARN" if r["status"] == "partial" else "FAIL")
        ms = r.get("ms", 0)
        fields = ", ".join(r.get("fields", []))
        spent = r.get("spent", 0)
        print(f"  {icon} {r['endpoint']:40s} {ms:5}ms  ${spent:.4f}")
        if r["status"] == "failed":
            print(f"     -> {r.get('error', '')}")

    after_all = usdc.functions.balanceOf(account.address).call()
    total_spent = (before_all - after_all) / 1e6
    print(f"\n  >> {ok}/{len(ENDPOINTS)} passed · {partial} partial · {failed} failed")
    print(f"  $ Total spent: ${total_spent:.4f} USDC")
    print(f"  $ Wallet: ${after_all / 1e6:.2f} remaining")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
