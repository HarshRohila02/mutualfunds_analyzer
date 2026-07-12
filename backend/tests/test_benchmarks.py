import numpy as np
import pandas as pd
import pytest

from app.analytics.benchmarks import CATEGORY_PROXIES, compute_alpha_beta
from app.analytics.metrics import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR

DAILY_RF = (1 + RISK_FREE_RATE_ANNUAL) ** (1 / TRADING_DAYS_PER_YEAR) - 1


def make_benchmark(years: int = 4, seed: int = 7, start: str = "2019-01-01") -> pd.Series:
    """Noisy geometric random walk - seeded, so tests are deterministic."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=252 * years)
    rets = 0.0005 + 0.01 * rng.standard_normal(len(dates))
    return pd.Series(100 * np.cumprod(1 + rets), index=dates)


def nav_from_returns(returns: pd.Series, first_date: pd.Timestamp) -> pd.Series:
    """Rebuild a NAV series (starting at 100 on first_date) from daily returns."""
    nav = 100 * (1 + returns).cumprod()
    return pd.concat([pd.Series([100.0], index=[first_date]), nav])


def test_scaled_excess_returns_recover_beta_k_alpha_zero():
    # fund excess return = k * benchmark excess return, exactly. The
    # regression must return beta = k and alpha = 0 (to numerical precision).
    bench = make_benchmark()
    k = 1.4
    bench_rets = bench.pct_change().dropna()
    fund = nav_from_returns(DAILY_RF + k * (bench_rets - DAILY_RF), bench.index[0])

    ab = compute_alpha_beta(fund, bench)
    assert ab is not None
    assert ab.beta_3y == pytest.approx(k, abs=1e-9)
    assert ab.alpha_3y == pytest.approx(0.0, abs=1e-9)


def test_constant_daily_outperformance_shows_up_as_alpha():
    # fund return = benchmark return + d every day -> beta 1, alpha d*252.
    bench = make_benchmark()
    d = 0.0002  # ~5%/yr annualized
    fund = nav_from_returns(bench.pct_change().dropna() + d, bench.index[0])

    ab = compute_alpha_beta(fund, bench)
    assert ab is not None
    assert ab.beta_3y == pytest.approx(1.0, abs=1e-9)
    assert ab.alpha_3y == pytest.approx(d * TRADING_DAYS_PER_YEAR, abs=1e-9)


def test_benchmark_against_itself_is_beta_one_alpha_zero():
    bench = make_benchmark()
    ab = compute_alpha_beta(bench, bench)
    assert ab is not None
    assert ab.beta_3y == pytest.approx(1.0)
    assert ab.alpha_3y == pytest.approx(0.0, abs=1e-12)


def test_short_overlap_returns_none():
    # Fund launched ~1y ago: joint window can't span 3y -> no alpha, ever,
    # rather than a fake "3y" number from 12 months of data.
    bench = make_benchmark()
    young_fund = bench.iloc[-252:] * 0.5
    assert compute_alpha_beta(young_fund, bench) is None


def test_disjoint_histories_return_none():
    bench = make_benchmark(start="2019-01-01")
    fund = make_benchmark(start="2010-01-01", years=3, seed=11)
    assert compute_alpha_beta(fund, bench) is None


def test_sparse_overlap_returns_none():
    # 3y of span but only weekly overlapping points - too few observations
    # for a stable regression.
    bench = make_benchmark()
    weekly_fund = bench[::5]
    assert compute_alpha_beta(weekly_fund, bench) is None


def test_proxy_map_is_well_formed():
    for category, proxy in CATEGORY_PROXIES.items():
        assert category.startswith("Equity Scheme"), category
        assert proxy.scheme_code.isdigit()
        assert proxy.index_name
