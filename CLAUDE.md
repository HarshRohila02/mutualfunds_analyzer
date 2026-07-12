# CLAUDE.md — Kosh (Indian Mutual Fund Research Desk)

Read this first. It's the handoff doc for continuing work in a fresh session.
User-facing setup lives in `README.md`; this file is the engineering map + current state.

## What this is

A deep-research tool for Indian (AMFI-registered) mutual funds. Three layers:
1. **Data pipeline** — ingest scheme master + full NAV history from mfapi.in into SQLite.
2. **Quant engine** — per-scheme metrics + a category-relative composite Fund Score, plus
   tenure-window Manager Scores.
3. **Surfaces** — a React dashboard and a Claude tool-calling research assistant.

Repo: https://github.com/HarshRohila02/mutualfunds_analyzer (branch `main`).

## Working agreement (important)

Build in **phases, autonomously**. After each phase: run tests + smoke-test the feature
against real data, `git commit` + `git push`, then start the next phase **without asking**.
The user (Harsh) steers direction; Claude drives the build end-to-end.

## Layout

```
backend/                      FastAPI + SQLAlchemy + pandas (Python 3.13)
  app/
    config.py                 Settings (DB url, ANTHROPIC_API_KEY, source URLs)
    main.py                   FastAPI app, routers, APScheduler lifespan
    models/                   SQLAlchemy models
      scheme.py               Scheme, NavHistory, CategoryBenchmark
      metrics.py              SchemeMetricsRow (one row/scheme, overwritten nightly)
      manager.py              Manager, ManagerAssignment
    ingestion/
      base.py                 MFDataSource ABC (SchemeInfo, NavPoint) — provider interface
      mfapi_source.py         mfapi.in implementation (the only live source)
      sync.py                 scheme-master sync, threaded backfill, nightly refresh
      manager_seed.py         loads data/seeds/managers.json, fuzzy-resolves scheme names
    analytics/
      metrics.py              pure pandas: CAGR, vol, drawdown, Sharpe/Sortino, rolling-3y
      scoring.py              category percentile ranks -> composite Fund Score
      manager_scoring.py      tenure-window Sharpe vs same-window category peers
      recompute.py            NAV -> metrics -> scores, writes scheme_metrics
    api/                      funds.py, managers.py, chat.py (REST)
    assistant/                tools.py (@beta_tool, DB-backed), agent.py (tool runner)
    scheduler.py              APScheduler nightly pipeline (02:30 IST)
  scripts/                    run_ingestion.py, run_recompute.py, load_managers.py, spike_*
  tests/                      pytest (metrics + scoring math, synthetic NAV series)
  .venv/                      Python venv (gitignored) — already created on this machine
  mf_analyzer.db              SQLite (gitignored) — already populated on this machine
data/seeds/managers.json      curated fund-manager dataset
frontend/                     Vite + React + TS
  src/api.ts                  typed API client
  src/pages/                  SearchPage, FundPage, ManagersPage, ResearchPage
  src/index.css               all styles (bahi-khata ledger theme)
.claude/launch.json           dev-server configs for the run/preview tooling
```

## Run it

```sh
# backend  (venv + DB already exist on this machine)
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000
# frontend
cd frontend && npm run dev        # http://localhost:5173, proxies /api -> :8000
# tests
cd backend && .venv/Scripts/python -m pytest tests/
```

Windows/Git-Bash notes: use `.venv/Scripts/python.exe`. To free a stuck port:
`for pid in $(netstat -ano | grep ':8000' | grep LISTEN | awk '{print $5}' | sort -u); do taskkill //PID "$pid" //F; done`

The dev DB (`backend/mf_analyzer.db`) is already loaded on this machine (5,081 synced
direct-growth schemes, ~5.3M NAV rows, 4,204 scored, 9 managers). A **fresh clone** must
run the one-off load in `README.md`. Set `SCHEDULER_ENABLED=0` to skip the nightly job in dev.

## Key decisions & non-obvious constraints

- **mfapi.in is the only data source.** mfdata.in was ruled out in Phase 0 — bot-protected,
  every request times out. Consequence: **no holdings, sector allocation, or expense-ratio
  data** is available. Don't promise those; they're backlog.
- **Fund Score is category-relative** (percentile within the scheme's own AMFI category):
  Sharpe 30% / consistency 20% / Sortino 20% / 3y CAGR 15% / drawdown 15%. Two integrity
  gates in `scoring.py`/`recompute.py`: **dead schemes** (no NAV in 30 days — matured FMPs)
  and **sub-3y funds** are excluded, else they sweep the top lists.
- **Manager Score isolates the tenure window**: fund Sharpe over the manager's actual dates,
  ranked against peers over the *same* calendar window. Inherited track records don't count.
  Data is a **curated seed** (`data/seeds/managers.json`) — absence ≠ bad manager; the UI and
  assistant say so.
- **Direct plans only exist since Jan 2013**, so pre-2013 tenures are clipped to NAV availability.
- **Fund renames** that broke seed matching (fixed, but watch for more): Mirae Emerging
  Bluechip → "Mirae Asset Large & Midcap Fund", Axis Bluechip → "Axis Large Cap Fund",
  HDFC Mid-Cap Opportunities → "HDFC Mid Cap Fund", SBI Focused Equity → "SBI FOCUSED FUND".
- **Assistant grounding is non-negotiable**: every number in a reply must come from a tool
  result, never model memory. The system prompt in `agent.py` enforces this; tools return
  JSON straight from the DB.
- **New SQLAlchemy models** must be imported in `app/models/__init__.py` or
  `Base.metadata.create_all` won't create their tables.
- **Ingestion/refresh assume `MFApiSource`** (they call `get_scheme_full`). Keep the
  `MFDataSource` interface if adding a provider, but those two functions currently type-check
  for the concrete class.

## Conventions

- Backend: pandas for math (keep analytics pure/DB-free in `analytics/`), SQLAlchemy 2.0
  typed models, FastAPI + Pydantic response models. Comments explain *why*, not *what*.
- Frontend: no component lib; styles are hand-rolled in `index.css` (ledger theme —
  paper/ink/kumkum-red, Fraunces + IBM Plex, the fund score as an auditor's "stamp").
- Verify new metrics with a synthetic NAV series where the answer is known analytically
  (see `tests/test_metrics.py`), then smoke-test against a real well-known fund.

## LLM / assistant cost

The assistant uses Claude `claude-opus-4-8` via the `anthropic` SDK. It needs
`ANTHROPIC_API_KEY` in `backend/.env` (copy `.env.example`); without it, `/api/chat` returns
a clean 503 and the rest of the app works. **Do not** wire in pooled/rotated "free API key"
repos — those distribute leaked keys or abuse free tiers (ToS violation). Legitimate
low/zero-cost path if desired: make the assistant provider-pluggable (an interface over
Claude / Google AI Studio Gemini free tier / local Ollama), selected by env var. This is an
open backlog option, not yet built.

## Status (as of 2026-07-12)

**Done & committed (Phases 0–6):** data pipeline, quant engine + Fund Score, manager
scoring, dashboard (search / fund detail / managers), research assistant + chat UI, nightly
scheduler, benchmark alpha/beta engine. 16 tests passing.

**Phase 6 notes (benchmark alpha/beta):** `analytics/benchmarks.py` holds the curated
`CATEGORY_PROXIES` map (equity category → index-fund proxy already in the DB) and the pure
`compute_alpha_beta` regression: daily fund excess returns on proxy excess returns over the
trailing 3y, gated on the joint window spanning ≥95% of 3y and ≥500 overlapping points.
Sectoral/Thematic is deliberately unmapped (dozens of unrelated sector benchmarks);
debt/hybrid have no proxies yet. Columns `alpha_3y`, `beta_3y`, `benchmark_code`,
`benchmark_name` live on `scheme_metrics`. Since `create_all` never ALTERs existing tables,
additive columns go through `run_light_migrations()` in `models/db.py` (called from `main.py`
and `run_recompute.py`) — extend `_LIGHT_MIGRATIONS` for future column adds. Alpha is
measured net of the proxy fund's expense drag (no TRI feed); the assistant prompt and the
fund-page footnote both disclose this.

**Backlog:** provider-pluggable assistant (see above), side-by-side fund comparison view,
holdings/sector data (needs a new source), automated factsheet parsing for manager coverage,
ML forward-performance prediction (deliberately deferred — v1 is explainable quant only).

## Memory

Machine-local memory files exist for this project (auto-loaded each session): project
overview + data constraints, the phase workflow above, and the Phase-6 in-progress note.
```
