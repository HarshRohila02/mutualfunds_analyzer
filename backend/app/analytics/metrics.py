"""Per-scheme quant metrics computed from a daily NAV series.

All functions take a pandas Series of NAVs indexed by date (ascending,
irregular trading-day spacing is fine) and are pure - no DB access here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
# Rough Indian risk-free proxy (10yr G-sec neighbourhood). Good enough for
# ranking funds against each other; not meant to be a precise RBI feed.
RISK_FREE_RATE_ANNUAL = 0.07

# A scheme needs at least ~1 year of NAVs before any metric is meaningful.
MIN_HISTORY_DAYS = 252


@dataclass
class SchemeMetrics:
    n_nav_points: int
    history_years: float
    cagr_1y: float | None
    cagr_3y: float | None
    cagr_5y: float | None
    cagr_10y: float | None
    ann_volatility: float | None
    max_drawdown: float | None
    sharpe_3y: float | None
    sortino_3y: float | None
    # % of rolling 3y windows where the scheme's CAGR was positive - a
    # baseline consistency signal; category-relative consistency is layered
    # on in scoring.py where peers are available.
    rolling_3y_windows: int
    rolling_3y_positive_pct: float | None
    rolling_3y_median_cagr: float | None


def _cagr(nav: pd.Series, years: float) -> float | None:
    """Point-to-point CAGR over the trailing `years` window."""
    if nav.empty:
        return None
    end_date = nav.index[-1]
    start_date = end_date - pd.DateOffset(years=years)
    window = nav[nav.index >= start_date]
    if len(window) < 2:
        return None
    # Require the window to actually span (almost) the full period, else a
    # 6-month-old fund would report a fake "1y CAGR".
    actual_years = (window.index[-1] - window.index[0]).days / 365.25
    if actual_years < years * 0.95:
        return None
    total_return = window.iloc[-1] / window.iloc[0]
    return float(total_return ** (1 / actual_years) - 1)


def _daily_returns(nav: pd.Series) -> pd.Series:
    return nav.pct_change().dropna()


def annualized_volatility(nav: pd.Series) -> float | None:
    rets = _daily_returns(nav)
    if len(rets) < 30:
        return None
    return float(rets.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def max_drawdown(nav: pd.Series) -> float | None:
    if len(nav) < 2:
        return None
    running_peak = nav.cummax()
    drawdown = nav / running_peak - 1
    return float(drawdown.min())


def _sharpe_sortino(nav: pd.Series, years: int = 3) -> tuple[float | None, float | None]:
    end_date = nav.index[-1]
    window = nav[nav.index >= end_date - pd.DateOffset(years=years)]
    rets = _daily_returns(window)
    if len(rets) < TRADING_DAYS_PER_YEAR:  # need at least ~1y of dailies
        return None, None
    daily_rf = (1 + RISK_FREE_RATE_ANNUAL) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess = rets - daily_rf
    ann_excess = float(excess.mean() * TRADING_DAYS_PER_YEAR)

    vol = float(rets.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    sharpe = ann_excess / vol if vol > 0 else None

    downside = rets[rets < daily_rf] - daily_rf
    if len(downside) < 10:
        sortino = None
    else:
        downside_dev = float(np.sqrt((downside**2).mean()) * np.sqrt(TRADING_DAYS_PER_YEAR))
        sortino = ann_excess / downside_dev if downside_dev > 0 else None
    return sharpe, sortino


def rolling_cagr_windows(nav: pd.Series, window_years: int = 3, step_days: int = 21) -> pd.Series:
    """CAGR for every rolling `window_years` window, sampled every
    `step_days` trading rows. Returns a Series indexed by window end date."""
    if len(nav) < 2:
        return pd.Series(dtype=float)
    out: dict[pd.Timestamp, float] = {}
    offset = pd.DateOffset(years=window_years)
    for end_pos in range(len(nav) - 1, -1, -step_days):
        end_date = nav.index[end_pos]
        start_date = end_date - offset
        window = nav[(nav.index >= start_date) & (nav.index <= end_date)]
        if len(window) < 2:
            continue
        actual_years = (window.index[-1] - window.index[0]).days / 365.25
        if actual_years < window_years * 0.95:
            continue
        out[end_date] = float((window.iloc[-1] / window.iloc[0]) ** (1 / actual_years) - 1)
    return pd.Series(out).sort_index()


def compute_scheme_metrics(nav: pd.Series) -> SchemeMetrics | None:
    """nav: float Series indexed by DatetimeIndex, ascending. Returns None if
    the series is too short to say anything meaningful."""
    nav = nav.dropna().sort_index()
    nav = nav[nav > 0]  # zero/negative NAVs are data errors and poison ratio math
    if len(nav) < MIN_HISTORY_DAYS:
        return None

    history_years = (nav.index[-1] - nav.index[0]).days / 365.25
    sharpe, sortino = _sharpe_sortino(nav)
    rolling = rolling_cagr_windows(nav)

    return SchemeMetrics(
        n_nav_points=len(nav),
        history_years=round(history_years, 2),
        cagr_1y=_cagr(nav, 1),
        cagr_3y=_cagr(nav, 3),
        cagr_5y=_cagr(nav, 5),
        cagr_10y=_cagr(nav, 10),
        ann_volatility=annualized_volatility(nav),
        max_drawdown=max_drawdown(nav),
        sharpe_3y=sharpe,
        sortino_3y=sortino,
        rolling_3y_windows=len(rolling),
        rolling_3y_positive_pct=float((rolling > 0).mean()) if len(rolling) else None,
        rolling_3y_median_cagr=float(rolling.median()) if len(rolling) else None,
    )
