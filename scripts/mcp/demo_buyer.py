#!/usr/bin/env python3
"""Demo buyer for OmniNexu MCP — validates the full x402 payment flow.

Requires a running MCP server::

    MCP_ENABLED=true X402_ENABLED=true python -m omninexu.mcp

Usage::

    # Part 1: connect, call free tool, see 402 on paid tool (no wallet needed)
    python scripts/mcp/demo_buyer.py

    # Part 2: call with x402 payment (needs testnet wallet + USDC)
    python scripts/mcp/demo_buyer.py --pay
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

MCP_URL = os.getenv("OMNINEXU_MCP_URL", "http://localhost:4022/sse")


def _print_402(struct: dict[str, Any]) -> None:
    """Pretty-print a 402 PaymentRequired response."""
    error = struct.get("error", "Payment Required")
    print(f"  402 Payment Required: {error}")
    accepts = struct.get("accepts", [{}])
    if accepts:
        a = accepts[0]
        amount = a.get("amount", "?")
        if amount and amount != "?":
            try:
                usd = float(amount) / 1_000_000
                amount = f"${usd:.2f} ({amount} atomic)"
            except (ValueError, TypeError):
                pass
        print(f"  Price:    {amount}")
        print(f"  Network:  {a.get('network', '?')}")
        print(f"  Pay to:   {a.get('payTo', '?')}")
        print(f"  Scheme:   {a.get('scheme', '?')}")


# ── part 1: inspect without payment ──


async def demo_inspect() -> None:
    """Connect to MCP server, call a free tool, observe 402 on paid ones."""
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    print("=" * 60)
    print("Part 1: Inspect (no payment)")
    print(f"Connecting to {MCP_URL} ...")
    print("=" * 60)

    async with sse_client(MCP_URL) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        # List tools
        tools_result = await session.list_tools()
        tools = tools_result.tools
        print(f"\nDiscovered {len(tools)} tool(s):\n")
        for t in tools:
            print(f"  {t.name:22s} — {t.description or '(no description)'}")

        # Call free tool
        print("\n── Calling omni_health (free) ──")
        try:
            result = await session.call_tool("omni_health", {})
            for c in result.content:
                if hasattr(c, "text"):
                    print(f"  Response: {c.text}")
        except Exception as e:
            print(f"  Error: {e}")

        # Call paid tool without payment → expect 402
        print("\n── Calling context (paid, $0.05) without payment ──")
        try:
            result = await session.call_tool(
                "context", {"ticker": "AAPL"}
            )
            # MCP returns CallToolResult; payment required raises as error
            if result.isError:
                for c in result.content:
                    if hasattr(c, "text"):
                        try:
                            parsed = json.loads(c.text)
                            if isinstance(parsed, dict) and "x402Version" in parsed:
                                _print_402(parsed)
                                break
                        except json.JSONDecodeError:
                            print(f"  402 Payment Required: {c.text[:120]}")
                else:
                    print("  402 Payment Required (see server for details)")
            else:
                print("  Unexpected: got data without payment!")
        except Exception as e:
            # Some MCP clients raise on isError results
            error_str = str(e)
            print(f"  Exception: {type(e).__name__}: {error_str[:200]}")

    print("\nPart 1 complete. To make real payments, run with --pay")
    print("(requires Base Sepolia testnet wallet with USDC)")


# ── part 2: call with x402 payment ──


async def demo_pay() -> None:
    """Connect with x402 payment client — auto-pay and get data."""
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from x402 import x402ClientAsync
    from x402.mechanisms.evm.exact import ExactEvmClientScheme

    signer_key = os.getenv("X402_BUYER_KEY")
    if not signer_key:
        print("Set X402_BUYER_KEY to a Base Sepolia private key with test USDC")
        print("Get test USDC from: https://docs.cdp.coinbase.com/x402/network-support")
        sys.exit(1)

    network = os.getenv("X402_NETWORK", "eip155:84532")  # 84532 = Base Sepolia

    print("=" * 60)
    print("Part 2: Pay (x402 auto-payment)")
    print(f"Connecting to {MCP_URL} ...")
    print(f"Network: {network}")
    print("=" * 60)

    # Build x402 payment client
    signer = ExactEvmClientScheme(signer_key)
    payment_client = x402ClientAsync()
    payment_client.register(network, signer)
    await payment_client.initialize()

    async with sse_client(MCP_URL) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        from x402.mcp import x402MCPSession

        mcp = x402MCPSession(session, payment_client, auto_payment=True)

        print("\n── omni_health (free) ──")
        result = await mcp.call_tool("omni_health", {})
        print(f"  Result: {result.content}")

        print("\n── context AAPL ($0.05) ──")
        result = await mcp.call_tool(
            "context", {"ticker": "AAPL"}
        )
        print(f"  Paid:    {result.payment_made}")
        if result.payment_made and result.payment_response:
            tx = (
                result.payment_response.transaction
                if hasattr(result.payment_response, "transaction")
                else result.payment_response.get("transaction", "?")
            )
            print(f"  Tx:      {tx}")
        for c in result.content:
            if hasattr(c, "text"):
                data = json.loads(c.text)
                print(f"  Status:  {data.get('status', '?')}")
                print(f"  Tx hash: {data.get('tx_hash', '?')}")

    print("\nDone.")


# ── main ──


def main() -> None:
    parser = argparse.ArgumentParser(description="OmniNexu MCP demo buyer")
    parser.add_argument(
        "--pay", action="store_true",
        help="Make real x402 payments (needs X402_BUYER_KEY env var)",
    )
    args = parser.parse_args()

    if args.pay:
        asyncio.run(demo_pay())
    else:
        asyncio.run(demo_inspect())


if __name__ == "__main__":
    main()
