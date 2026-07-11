# Kosh — Mutual Fund Research Desk (India)

Deep-research tool for Indian (AMFI-registered) mutual funds: quant scoring from full NAV
history, fund-manager tenure analysis, and an AI research assistant grounded in the local
database.

## What it does

- **Data**: ingests the full AMFI scheme universe (~37.6k schemes) via [mfapi.in](https://www.mfapi.in),
  backfills full NAV history for all ~5k direct-growth plans (~5.3M NAV rows), refreshed nightly at 02:30 IST.
- **Fund Score (0–100)**: category-relative percentile composite — Sharpe 30%, rolling-3y
  consistency 20%, Sortino 20%, 3y CAGR 15%, drawdown resilience 15%. Dead schemes (no NAV
  print in 30 days) and funds younger than 3 years are excluded from scoring by design.
- **Manager Score**: from a curated seed dataset of well-known managers. Performance is
  measured only over the manager's actual tenure window, ranked against category peers over
  the *same* calendar window — inherited track records don't count.
- **Dashboard**: fund search, detail pages (score breakdown, NAV chart, percentile rails,
  manager panel), manager roster.
- **Research assistant**: Claude (claude-opus-4-8) tool-calling against the local DB. Every
  number in an answer traces to a tool result; nothing is quoted from model memory.

## Running it

```sh
# Backend (Python 3.13)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# Frontend (Node 20+)
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api to :8000
```

First-time data load (one-off, ~25 min total):

```sh
cd backend
.venv/Scripts/python scripts/run_ingestion.py master
.venv/Scripts/python scripts/run_ingestion.py backfill --contains Direct --contains Growth
.venv/Scripts/python scripts/run_recompute.py
.venv/Scripts/python scripts/load_managers.py
```

For the AI assistant, copy `backend/.env.example` to `backend/.env` and set `ANTHROPIC_API_KEY`.

## Tests

```sh
cd backend && .venv/Scripts/python -m pytest tests/
```

## Known gaps (backlog)

- Portfolio holdings / sector allocation — no free scriptable source found yet (mfdata.in is bot-protected)
- Benchmark-index NAV feed for true alpha/beta (currently category-peer-relative percentiles)
- Expense ratios (not in mfapi.in)
- Automated AMC factsheet parsing for full manager coverage (current dataset is a curated seed)
- ML-based forward performance prediction (deliberately deferred; v1 is explainable quant only)

**Not investment advice.** Scores are historical, data-driven measures; past performance does
not guarantee future results.
