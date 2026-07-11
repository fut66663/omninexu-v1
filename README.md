# OmniNexu

AI Agent Decision Context Engine for Public Companies — structured financial intelligence via HTTP API.

🌐 [omninexu.com](https://www.omninexu.com) · 📊 [Dashboard](https://api.omninexu.com/dashboard) · 📖 [Docs](https://api.omninexu.com/docs)

[![CI](https://github.com/fut66663/omninexu-v1/actions/workflows/ci.yml/badge.svg)](https://github.com/fut66663/omninexu-v1/actions/workflows/ci.yml)

---

## What is OmniNexu

OmniNexu is a **FastAPI backend** that collects S&P 500 public company financial data from SEC EDGAR and SimFin, processes it into structured JSON, and serves it to AI agents via HTTP API.

Built-in **[x402](https://docs.x402.org)** payment support — agents pay per query in USDC on Base. No API keys. No signup.

## Data Coverage

| Dimension | Coverage | Source |
|-----------|:---:|--------|
| Fundamentals (9 standardized metrics) | 500 companies / 18,676 facts | SimFin + SEC EDGAR |
| Quarterly financials (10-Q) | 115 tickers (Q1:85 / Q2:21 / Q3:14) | SEC EDGAR |
| Insider transactions (Form 4) | 20 tickers / 380 transactions | SEC EDGAR |
| Institutional holdings (13F) | 20 tickers / 159 records | SEC EDGAR |
| Macro-economic indicators | 5 series (Fed rate, CPI, GDP, unemployment, 10Y) | FRED |
| Peer comparison (GICS industry) | 500 companies | SIC → GICS mapping |
| Investment signals (pulse) | 7 signal types across 114 tickers | Multi-source |
| Analytical database | 24,360 rows / 5 tables / pivot view | DuckDB |

## API Endpoints

| Method | Path | Price | Description |
|--------|------|:---:|-------------|
| GET | `/v1/health` | Free | Health check (DB + Redis + DuckDB + pipelines) |
| GET | `/v1/company/context?ticker={t}` | $0.05 | Company fundamentals + peers + institutional + insider |
| GET | `/v1/company/pulse?ticker={t}` | $0.02 | Investment signals (insider, institutional, revenue trend, macro) |
| GET | `/v1/company/filings?ticker={t}` | $0.01 | SEC filing metadata (10-K, 10-Q, 8-K) |
| GET | `/v1/company/peer-ranking?ticker={t}` | $0.02 | Industry peer ranking — revenue & net income |
| GET | `/v1/company/insider?ticker={t}` | $0.03 | SEC Form 4 insider transactions |
| GET | `/v1/company/institutional?ticker={t}` | $0.03 | SEC 13F institutional holdings |
| GET | `/v1/company/longitudinal?ticker={t}` | $0.03 | Multi-year CAGR growth trends |
| GET | `/v1/company/smart-money?ticker={t}` | $0.05 | Bundle: insider + institutional in one call |

> All data endpoints use x402 per-query pricing on Base mainnet (USDC). No API keys. No signup.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| Web Framework | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 |
| Analytical DB | DuckDB (in-process OLAP) |
| Cache | Redis 7 |
| Payment | x402 protocol (Base mainnet, USDC) |
| Data Ingestion | edgartools + SimFin + FRED API |
| Pipeline Scheduler | Cron + custom scheduler (6 commands) |
| Package Manager | uv |
| Deployment | Docker + Docker Compose + Nginx + GitHub Actions CI |
| Quality | ruff + mypy + pytest (725 tests) |

## Project Structure

```
src/omninexu/
├── api/                   FastAPI application
│   ├── main.py            Entry point + middleware registration
│   ├── middleware/         x402 payment + request logging
│   ├── routes/             Endpoints (health, company)
│   ├── schemas/            Pydantic response models
│   └── endpoints/          Per-endpoint x402 route registration (8 endpoints)
├── application/            Business use cases
│   ├── company_context.py  Company fundamentals + peer comparison
│   └── pulse.py            7 investment signal generators
├── domain/                 Domain models
├── infrastructure/         External dependencies
│   ├── clients/            SEC EDGAR, SimFin, FRED, CDP auth
│   ├── repositories/       SQLAlchemy query wrappers
│   ├── storage/            Disk validation + product persistence
│   ├── cache/              Redis cache layer
│   ├── db.py               Session factory
│   └── models.py           ORM models
├── config/                 Configuration (pydantic-settings)
└── observability/          Structured logging + error handling

scripts/
├── ingest/                 Data collection (SEC 10-K/10-Q, SimFin, FRED, GICS)
├── ops/                    Pipeline scheduler (6 commands) + DuckDB export
├── verify/                 Data quality verification
└── x402/buyer.py           x402 buyer payment script

tests/                      725 tests (unit + integration)
docs/                       Architecture + data reports
deploy/                     Nginx config + crontab
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
