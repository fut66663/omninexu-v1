# OmniNexu

AI Agent Decision Context Engine for Public Companies — structured financial intelligence via HTTP API.

[![CI](https://github.com/fut66663/omninexu-v1/actions/workflows/ci.yml/badge.svg)](https://github.com/fut66663/omninexu-v1/actions/workflows/ci.yml)

---

## What is OmniNexu

OmniNexu is a **FastAPI backend** that collects S&P 500 public company financial data from SEC EDGAR and SimFin, processes it into structured JSON, and serves it to AI agents via HTTP API.

Built-in **[x402](https://docs.cdp.coinbase.com/x402/welcome)** payment support — agents pay per query in USDC on Base. No API keys. No signup.

## Data Coverage

| Dimension | Coverage | Source |
|-----------|:---:|--------|
| Fundamentals (9 standardized metrics) | 440 tickers (88%) | SimFin + SEC EDGAR XBRL |
| Cross-source validation (SEC vs SimFin) | Within coverage | Alert on >2% discrepancy |
| Peer comparison (GICS industry) | 500 companies | SEC SIC → GICS mapping |
| Insider transactions (Form 4) | 18 tickers | SEC EDGAR |
| Institutional holdings (13F) | 20 tickers | SEC EDGAR |
| Longitudinal trends (CAGR) | Roadmap | — |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| Web Framework | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 |
| Cache | Redis 7 |
| Payment | x402 protocol (Base mainnet, USDC) |
| Data Ingestion | edgartools + SimFin API |
| Package Manager | uv |
| Deployment | Docker + Docker Compose + Nginx |

## Project Structure

```
src/omninexu/
├── api/                   FastAPI application
│   ├── main.py            Entry point + middleware registration
│   ├── middleware/         x402 payment + request logging
│   ├── routes/             Endpoints (health, company)
│   └── schemas/            Pydantic response models
├── application/            Business use cases
├── domain/                 Domain models
├── infrastructure/         External dependencies
│   ├── clients/            SEC EDGAR, SimFin, CDP auth
│   ├── repositories/       SQLAlchemy query wrappers
│   ├── cache/              Redis cache layer
│   ├── db.py               Session factory
│   └── models.py           ORM models
├── config/                 Configuration (pydantic-settings)
├── jobs/                   Data seeding
└── observability/          Structured logging + error handling

scripts/
├── ingest/                 Data collection pipelines (SEC, SimFin, GICS)
├── verify/                 Data quality verification
├── ops/                    Operations (backup, log rotation)
└── x402/buyer.py           x402 buyer payment script

tests/                      Pytest suite
docs/                       Documentation
```

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16
- Redis 7
- [uv](https://docs.astral.sh/uv/)

### Setup

```bash
git clone https://github.com/fut66663/omninexu-v1.git
cd omninexu-v1

# Install dependencies
uv sync

# Configure environment (set your DB connection, etc.)
cp .env.example .env

# Start database & cache (Docker)
docker compose -f .docker/docker-compose.yml up -d

# Run migrations
uv run alembic upgrade head

# Start dev server
uv run uvicorn src.omninexu.api.main:app --reload --port 8000
```

### Verify

```bash
# Health check
curl http://localhost:8000/v1/health

# Company context (requires seed data)
curl "http://localhost:8000/v1/company/context?ticker=AAPL"
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info |
| GET | `/v1/health` | Health check (DB + Redis) |
| GET | `/v1/company/context?ticker={ticker}` | Company context |

> When x402 middleware is enabled in production, `/v1/company/context` requires USDC payment. Set `X402_ENABLED=false` in `.env` for local development to disable payment.

## x402 Payment

OmniNexu includes [x402 protocol](https://docs.cdp.coinbase.com/x402/welcome) middleware out of the box:

```
Agent requests data → 402 Payment Required + PAYMENT-REQUIRED header
Agent signs payment → CDP Facilitator verifies → USDC settles on Base
Agent retries with proof → 200 + data
```

See `scripts/x402/buyer.py` for a working buyer implementation.

Configure in `.env`:

```bash
X402_ENABLED=true
X402_FACILITATOR_URL=https://api.cdp.coinbase.com/platform/v2/x402
X402_NETWORK=eip155:8453
X402_PAY_TO=<your-wallet-address>
CDP_API_KEY_ID=<your-cdp-key-id>
CDP_API_KEY_SECRET=<your-cdp-key-secret>
```

## Production Deployment

```bash
cp .env.production .env
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

## Run Tests

```bash
uv run pytest
```

## License

[Apache License 2.0](LICENSE)

---

> OmniNexu — Structured financial intelligence, built for AI agents.
