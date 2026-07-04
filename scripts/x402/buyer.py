"""x402 buyer script — pay USDC to call OmniNexu endpoints.

Usage:  uv run python scripts/x402/buyer.py [URL]

Environment (from .env or shell):
    BUYER_ADDRESS        — buyer wallet address
    BUYER_PRIVATE_KEY    — buyer wallet private key (0x...)
    BASE_RPC_URL         — Base RPC (default: https://mainnet.base.org)
"""

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

from eth_account import Account
from web3 import Web3

# ── Config ────────────────────────────────────────────
BUYER_ADDRESS = os.getenv("BUYER_ADDRESS", "0x3e9c7E0b781220ed054fb5516854FA272c3010cc")
BUYER_PRIVATE_KEY = os.getenv("BUYER_PRIVATE_KEY")
BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

if not BUYER_PRIVATE_KEY:
    print("[Buyer] BUYER_PRIVATE_KEY not set")
    sys.exit(1)

w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
account = Account.from_key(BUYER_PRIVATE_KEY)

# ── Balance ───────────────────────────────────────────
usdc_abi = json.loads('''[
    {"constant":true,"inputs":[{"name":"owner","type":"address"}],
     "name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],
     "type":"function"}
]''')
usdc = w3.eth.contract(address=USDC_ADDRESS, abi=usdc_abi)


def show_balance() -> int:
    balance = usdc.functions.balanceOf(account.address).call()
    print(f"[Buyer] USDC: ${balance / 1e6:.2f}")
    return balance


# ── Main ──────────────────────────────────────────────
async def main() -> None:
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    target = f"{server_url}/v1/company/context?ticker=AAPL"
    price_usd = 0.05

    print(f"[Buyer] Wallet: {account.address}")
    print(f"[Buyer] Target: {target}")
    print(f"[Buyer] Price:  ${price_usd} USDC\n")

    before = show_balance()

    # Step 1: Make an unpaid request → expect 402
    req = urllib.request.Request(target)
    try:
        urllib.request.urlopen(req)
        print("[Buyer] Unexpected: no 402 — middleware may be disabled")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        if e.code != 402:
            print(f"[Buyer] Unexpected status: {e.code}")
            print(f"[Buyer] Body: {e.read().decode()[:200]}")
            sys.exit(1)
        payment_required = e.headers.get("PAYMENT-REQUIRED")
        if not payment_required:
            print("[Buyer] No PAYMENT-REQUIRED header")
            sys.exit(1)

    print("[Buyer] Got 402 — payment required")

    # Step 2: Use the official x402 client to sign and pay
    print("[Buyer] Signing with x402 SDK...")

    from x402 import x402Client
    from x402.http.clients import x402HttpxClient
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client

    client = x402Client()
    register_exact_evm_client(client, EthAccountSigner(account))

    async with x402HttpxClient(client) as http:
        response = await http.get(target)
        response.raise_for_status()

        data = response.json()
        payment_header = response.headers.get("PAYMENT-RESPONSE")

    print("\n[Buyer] Payment success!")
    print(f"[Buyer]   HTTP: {response.status_code}")
    print(f"[Buyer]   Ticker: {data.get('ticker', 'N/A')}")
    print(f"[Buyer]   Confidence: {data.get('confidence', 'N/A')}")
    if payment_header:
        print(f"[Buyer]   Settlement: {payment_header[:80]}...")

    after = show_balance()
    spent = (before - after) / 1e6
    print(f"\n[Buyer] Actual cost: ${spent:.4f} USDC")


if __name__ == "__main__":
    asyncio.run(main())
