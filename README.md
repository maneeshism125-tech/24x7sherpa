# 24x7 Sherpa — S&P 500 equity stack

Python toolkit for **S&P 500 equities only**: free-tier data (Yahoo Finance + optional RSS/NewsAPI), technical features, simple rule-based signals, risk helpers, and **execution** via **in-memory paper trading** or **Alpaca** (paper API by default).

This is infrastructure, not investment advice. Markets are risky; there is no guaranteed daily return.

## GitHub and hosting

**GitHub** is worth using for version history, backups, and collaboration. Use a private repo if the code or your `.env` patterns should stay non-public (never commit real API keys).

**Vercel** fits **frontend** sites and **short** serverless API routes. This project is a **Python** data and trading stack: scans and indicators can exceed Vercel’s execution time limits, and you need durable storage for simulations. Typical split:

- **Vercel (or similar)**: marketing site, learner dashboard UI.
- **Backend**: Fly.io, Railway, Render, or a small VPS running this Python service (or container), with a database when you add multi-user accounts.

## Setup

```bash
cd /path/to/24x7sherpa
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install -e ".[web]"   # FastAPI + uvicorn for the website
cp .env.example .env   # optional: add keys
```

## Website (dashboard)

**Stack:** FastAPI (`api/`) + React + Vite + Tailwind (`web/`).

**One terminal (API + UI)**

From repo root (after `pip install -e ".[web]"` in your venv and `npm run install-web`):

```bash
npm run dev
```

Starts FastAPI on **:8000** and Vite on **:5173**. Open **http://127.0.0.1:5173**. **Ctrl+C** stops both.

Frontend only (you must run `sherpa-web` separately): `npm run dev:ui`.

**If something fails**, run:

```bash
source .venv/bin/activate
sherpa doctor
```

**Two terminals (optional):** Terminal A: `sherpa-web` — Terminal B: `npm run dev:ui`.

**If you only run `npm run dev:ui`:** nothing listens on port 8000, so `/api/...` fails — use **`npm run dev`** instead.

**Production-style (single server serves API + static UI):**

```bash
npm run install-web && npm run build
SHERPA_WEB_RELOAD=0 PORT=8000 sherpa-web
```

Open **http://127.0.0.1:8000** — API docs at `/docs`.

Deploy the same pattern on Fly.io, Railway, or a VPS (not ideal on Vercel serverless for long scans).

## CLI

Refresh the S&P 500 ticker cache (hits Wikipedia once):

```bash
sherpa universe-refresh
```

```bash
# Scan first 25 names for demo signals (uses yfinance + Google News RSS)
sherpa scan --top 25

# Faster scan without news
sherpa scan --top 50 --skip-news

# Paper trade (uses last Yahoo close + slippage bps from settings)
sherpa trade AAPL buy 1 --broker paper

# Fake-money learning: named sandboxes (files under data/simulations/<profile>/)
sherpa simulate reset --cash 25000 --profile lesson1
sherpa simulate status --profile lesson1
sherpa trade AAPL buy 1 --broker paper --profile lesson1
sherpa account --broker paper --profile lesson1

# Alpaca paper (set ALPACA_* in .env)
sherpa trade MSFT sell 2 --broker alpaca
sherpa account --broker alpaca
```

Paper trades persist under `data/simulations/<profile>/portfolio.json` (gitignored). The `default` profile migrates from legacy `data/paper_portfolio.json` if present. Set `SIMULATION_PROFILE` or pass `--profile` / `-p` on commands.

## Architecture

- `sherpa/universe` — S&P 500 list (cached under `data/`).
- `sherpa/providers` — `PriceProvider` / `NewsProvider` (swap Yahoo → Polygon/IEX later).
- `sherpa/technical` — indicators on `Bar` series.
- `sherpa/signals` — pluggable rules (replace with your models).
- `sherpa/risk` — position sizing and daily loss gate.
- `sherpa/execution` — `PaperBroker`, `AlpacaBroker`, shared `BrokerClient` shape for more brokers.
- `api/` — HTTP API for the dashboard; `web/` — Vite + React UI.

## Paid tier later

Add new provider classes implementing the same protocols and select them from config (e.g. `POLYGON_API_KEY`). Brokerage expansion: implement `BrokerClient` for Interactive Brokers, Schwab, etc.
