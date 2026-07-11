import numpy as np
import pandas as pd
import pytest

from app.analytics.metrics import (
    compute_scheme_metrics,
    max_drawdown,
    rolling_cagr_windows,
)
from app.analytics.scoring import add_category_percentiles


def make_nav(annual_growth: float, years: int = 6, start: str = "2018-01-01") -> pd.Series:
    """Deterministic NAV compounding smoothly at `annual_growth`/yr on business days."""
    dates = pd.bdate_range(start=start, periods=252 * years)
    daily = (1 + annual_growth) ** (1 / 252) - 1
    values = 100 * (1 + daily) ** np.arange(len(dates))
    return pd.Series(values, index=dates)


def test_cagr_recovers_known_growth_rate():
    nav = make_nav(0.12)
    m = compute_scheme_metrics(nav)
    assert m is not None
    # bdate spacing vs calendar-year math introduces small drift; 1% tolerance
    assert m.cagr_1y == pytest.approx(0.12, abs=0.01)
    assert m.cagr_3y == pytest.approx(0.12, abs=0.01)
    assert m.cagr_5y == pytest.approx(0.12, abs=0.01)


def test_smooth_series_has_no_drawdown_and_positive_consistency():
    nav = make_nav(0.10)
    m = compute_scheme_metrics(nav)
    assert m.max_drawdown == pytest.approx(0.0, abs=1e-9)
    assert m.rolling_3y_positive_pct == 1.0


def test_max_drawdown_known_crash():
    nav = pd.Series(
        [100, 120, 60, 80, 130],
        index=pd.to_datetime(["2020-01-01", "2020-06-01", "2020-09-01", "2021-01-01", "2021-06-01"]),
    )
    assert max_drawdown(nav) == pytest.approx(-0.5)  # 120 -> 60


def test_too_short_history_returns_none():
    nav = make_nav(0.10)[:100]
    assert compute_scheme_metrics(nav) is None


def test_young_fund_has_no_long_horizon_cagr():
    nav = make_nav(0.10, years=2)
    m = compute_scheme_metrics(nav)
    assert m.cagr_1y is not None
    assert m.cagr_5y is None
    assert m.cagr_10y is None


def test_sharpe_sign_matches_excess_return():
    strong = compute_scheme_metrics(make_nav(0.20))
    weak = compute_scheme_metrics(make_nav(0.02))
    # 20% growth > 7% risk-free -> positive sharpe; 2% < rf -> negative
    assert strong.sharpe_3y > 0
    assert weak.sharpe_3y < 0


def test_rolling_windows_exist_for_long_series():
    windows = rolling_cagr_windows(make_nav(0.10, years=6))
    assert len(windows) > 20
    assert (windows > 0.08).all()


def test_category_percentiles_rank_within_category_only():
    df = pd.DataFrame(
        {
            "scheme_code": [str(i) for i in range(12)],
            "category": ["Mid Cap"] * 6 + ["Gilt"] * 6,
            "cagr_3y": [0.05, 0.08, 0.11, 0.14, 0.17, 0.20, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09],
            "sharpe_3y": [0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
            "sortino_3y": [0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
            "max_drawdown": [-0.5, -0.4, -0.3, -0.25, -0.2, -0.1, -0.1, -0.09, -0.08, -0.07, -0.06, -0.05],
            "rolling_3y_positive_pct": [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0],
        }
    )
    out = add_category_percentiles(df)
    best_midcap = out[out.scheme_code == "5"].iloc[0]
    worst_midcap = out[out.scheme_code == "0"].iloc[0]
    assert best_midcap.fund_score > worst_midcap.fund_score
    assert best_midcap.pct_cagr_3y == 100.0
    # A middling gilt fund is ranked against gilts, not against mid-caps:
    # scheme 11 has the best gilt numbers -> 100th pct in its own category
    best_gilt = out[out.scheme_code == "11"].iloc[0]
    assert best_gilt.pct_sharpe_3y == 100.0


def test_small_category_gets_no_score():
    df = pd.DataFrame(
        {
            "scheme_code": ["a", "b"],
            "category": ["Tiny Category"] * 2,
            "cagr_3y": [0.1, 0.2],
            "sharpe_3y": [0.5, 1.0],
            "sortino_3y": [0.5, 1.0],
            "max_drawdown": [-0.2, -0.1],
            "rolling_3y_positive_pct": [0.8, 0.9],
        }
    )
    out = add_category_percentiles(df)
    assert out.fund_score.isna().all()
