"""Quick verification of Company Context with real data."""

import sys

from omninexu.application.company_context import CompanyContextService
from omninexu.infrastructure.db import SessionLocal


class _FakeVerifyCache:
    """In-memory cache for verification."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def get_json(self, key: str):
        import json

        v = self._store.get(key)
        return json.loads(v) if v else None

    def set_json(self, key: str, value, ttl: int = 0):
        import json

        self._store[key] = json.dumps(value, default=str)

    def delete(self, key: str):
        self._store.pop(key, None)


ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

db = SessionLocal()
cache = _FakeVerifyCache()
service = CompanyContextService(db, cache_backend=cache)
ctx = service.build_context(ticker)

print(f"=== {ticker} Company Context ===")
print(f"Name: {ctx['name']}")
print(f"Fundamentals: {len(ctx['fundamentals'])} metrics")
for k, v in sorted(ctx["fundamentals"].items()):
    print(f"  {k}: {v['value']:,.0f} ({v['unit']})")

print("Longitudinal:")
for k, v in sorted(ctx["longitudinal"].items()):
    print(f"  {k}: {v:.4f}")

if ctx["peer_comparison"]:
    pc = ctx["peer_comparison"]
    r_rank = pc.get("revenue_rank") or "N/A"
    r_total = pc.get("revenue_total_peers") or "N/A"
    n_rank = pc.get("net_income_rank") or "N/A"
    n_total = pc.get("net_income_total_peers") or "N/A"
    print(f"Peer: revenue_rank={r_rank}/{r_total}, net_income_rank={n_rank}/{n_total}")
else:
    print("Peer: null (no GICS sub-industry peers in DB)")

if ctx["institutional"]:
    inst = ctx["institutional"]
    holders = inst.get("top_holders", [])
    print(f"Institutional: {len(holders)} holders")
    for h in holders[:3]:
        print(f"  {h['name']}: {h['shares']:,.0f} shares (${h['value']:,.0f})")
else:
    print("Institutional: null")

if ctx["insider"]:
    ins = ctx["insider"]
    trades = ins.get("transaction_count_90d", 0)
    net = ins.get("net_shares_90d", 0)
    print(f"Insider: {trades} trades, net {net:,.0f} shares")
else:
    print("Insider: null")

print(f"Confidence: {ctx['confidence']}")
db.close()
