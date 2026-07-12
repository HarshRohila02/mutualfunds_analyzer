"""Benchmark alpha/beta vs index-fund proxies.

We have no direct index (TRI) feed - mfapi.in only serves mutual fund NAVs.
Instead, each equity category is mapped to a long-running *index fund* already
in our DB, whose NAV tracks the index minus a small expense drag. Alpha
computed this way is therefore alpha vs "the index as an investor could
actually buy it", which slightly flatters active funds (a few bps/yr) but
ranks them correctly.

The regression itself is pure pandas and DB-free, like the rest of analytics/.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.analytics.metrics import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR

# The joint fund+benchmark window must genuinely span the trailing period
# (same 0.95 slack as _cagr) and have enough overlapping trading days for the
# regression to be stable.
ALPHA_BETA_YEARS = 3
MIN_JOINT_SPAN_FRACTION = 0.95
MIN_REGRESSION_POINTS = 500


@dataclass(frozen=True)
class BenchmarkProxy:
    index_name: str  # what the user should read, e.g. "Nifty Midcap 150"
    scheme_code: str  # index fund in our DB standing in for that index


# Curated AMFI equity category -> index proxy. Proxy funds were chosen for the
# longest available direct-plan NAV history per index (scouted 2026-07).
# Sectoral/Thematic is deliberately unmapped: those funds track dozens of
# unrelated sector indices, and alpha vs a broad index would be noise dressed
# up as insight. Debt/hybrid need yield-curve proxies we don't have yet.
CATEGORY_PROXIES: dict[str, BenchmarkProxy] = {
    "Equity Scheme - Large Cap Fund": BenchmarkProxy("Nifty 50", "118581"),
    "Equity Scheme - Mid Cap Fund": BenchmarkProxy("Nifty Midcap 150", "148726"),
    "Equity Scheme - Small Cap Fund": BenchmarkProxy("Nifty Smallcap 250", "148519"),
    # Broad-mandate categories all regress against the full-market Nifty 500.
    # (Large & Mid Cap's official benchmark is LargeMidcap 250 - no investable
    # proxy with usable history exists in the DB, Nifty 500 is the closest.)
    "Equity Scheme - Large & Mid Cap Fund": BenchmarkProxy("Nifty 500", "147625"),
    "Equity Scheme - Flexi Cap Fund": BenchmarkProxy("Nifty 500", "147625"),
    "Equity Scheme - Multi Cap Fund": BenchmarkProxy("Nifty 500", "147625"),
    "Equity Scheme - ELSS": BenchmarkProxy("Nifty 500", "147625"),
    "Equity Scheme - Focused Fund": BenchmarkProxy("Nifty 500", "147625"),
    "Equity Scheme - Value Fund": BenchmarkProxy("Nifty 500", "147625"),
    "Equity Scheme - Contra Fund": BenchmarkProxy("Nifty 500", "147625"),
    "Equity Scheme - Dividend Yield Fund": BenchmarkProxy("Nifty 500", "147625"),
}


@dataclass
class AlphaBeta:
    alpha_3y: float  # annualized Jensen's alpha (daily intercept * 252)
    beta_3y: float
    n_obs: int


def compute_alpha_beta(
    fund_nav: pd.Series,
    benchmark_nav: pd.Series,
    years: int = ALPHA_BETA_YEARS,
) -> AlphaBeta | None:
    """OLS of daily fund excess returns on benchmark excess returns over the
    trailing `years` window (window ends at the latest date both series share).

    Both inputs: float NAV Series on a DatetimeIndex. Returns None when the
    joint history can't honestly support a 3y regression.
    """
    joint = pd.concat(
        [fund_nav.dropna().sort_index(), benchmark_nav.dropna().sort_index()],
        axis=1,
        join="inner",
        keys=["fund", "bench"],
    ).dropna()
    if len(joint) < 2:
        return None

    end_date = joint.index[-1]
    window = joint[joint.index >= end_date - pd.DateOffset(years=years)]
    span_years = (window.index[-1] - window.index[0]).days / 365.25
    if span_years < years * MIN_JOINT_SPAN_FRACTION:
        return None

    rets = window.pct_change().dropna()
    if len(rets) < MIN_REGRESSION_POINTS:
        return None

    daily_rf = (1 + RISK_FREE_RATE_ANNUAL) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    fund_excess = rets["fund"] - daily_rf
    bench_excess = rets["bench"] - daily_rf

    bench_var = float(bench_excess.var())
    if bench_var <= 0:  # flat benchmark => beta undefined
        return None
    beta = float(bench_excess.cov(fund_excess)) / bench_var
    alpha_daily = float(fund_excess.mean()) - beta * float(bench_excess.mean())

    return AlphaBeta(
        alpha_3y=alpha_daily * TRADING_DAYS_PER_YEAR,
        beta_3y=beta,
        n_obs=len(rets),
    )
