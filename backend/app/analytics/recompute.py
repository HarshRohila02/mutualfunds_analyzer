"""Nightly (or on-demand) recompute: NAV history -> per-scheme metrics ->
category-relative scores -> scheme_metrics table."""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analytics.benchmarks import CATEGORY_PROXIES, compute_alpha_beta
from app.analytics.metrics import compute_scheme_metrics
from app.analytics.scoring import add_category_percentiles
from app.models.metrics import SchemeMetricsRow
from app.models.scheme import NavHistory, Scheme

# A fund whose NAV hasn't printed in this long is dead (matured FMP, wound-up
# or merged scheme). Dead funds must not enter percentile pools or top lists -
# otherwise matured fixed-maturity plans with smooth historical NAVs dominate
# every ranking.
STALE_NAV_DAYS = 30


def _load_nav_series(session: Session, scheme_code: str) -> pd.Series:
    rows = session.execute(
        select(NavHistory.nav_date, NavHistory.nav)
        .where(NavHistory.scheme_code == scheme_code)
        .order_by(NavHistory.nav_date)
    ).all()
    return pd.Series(
        [row.nav for row in rows],
        index=pd.DatetimeIndex([pd.Timestamp(row.nav_date) for row in rows]),
    )


def recompute_all(session: Session, progress_every: int = 250) -> tuple[int, int]:
    """Returns (schemes_considered, metrics_rows_written)."""
    latest_overall = session.execute(select(func.max(NavHistory.nav_date))).scalar_one()
    cutoff = latest_overall - timedelta(days=STALE_NAV_DAYS)

    live_codes = {
        row[0]
        for row in session.execute(
            select(NavHistory.scheme_code)
            .group_by(NavHistory.scheme_code)
            .having(func.max(NavHistory.nav_date) >= cutoff)
        )
    }

    schemes = [
        row
        for row in session.execute(
            select(Scheme.scheme_code, Scheme.category).where(Scheme.details_synced.is_(True))
        ).all()
        if row[0] in live_codes
    ]

    # Drop metrics rows for schemes that have since gone stale.
    session.execute(
        delete(SchemeMetricsRow).where(SchemeMetricsRow.scheme_code.not_in(live_codes))
    )
    session.commit()

    # Load each benchmark proxy's NAV once up front; hundreds of schemes
    # regress against the same handful of index funds.
    proxy_navs = {
        proxy.scheme_code: _load_nav_series(session, proxy.scheme_code)
        for proxy in set(CATEGORY_PROXIES.values())
    }

    records: list[dict] = []
    for i, (code, category) in enumerate(schemes, 1):
        nav = _load_nav_series(session, code)
        if nav.empty:
            continue
        metrics = compute_scheme_metrics(nav)
        if metrics is None:
            continue
        record = asdict(metrics)
        record["scheme_code"] = code
        record["category"] = category

        record["alpha_3y"] = record["beta_3y"] = None
        record["benchmark_code"] = record["benchmark_name"] = None
        proxy = CATEGORY_PROXIES.get(category) if category else None
        if proxy and not proxy_navs[proxy.scheme_code].empty:
            ab = compute_alpha_beta(nav, proxy_navs[proxy.scheme_code])
            if ab is not None:
                record["alpha_3y"] = ab.alpha_3y
                record["beta_3y"] = ab.beta_3y
                record["benchmark_code"] = proxy.scheme_code
                record["benchmark_name"] = proxy.index_name

        records.append(record)
        if progress_every and i % progress_every == 0:
            print(f"  metrics: {i}/{len(schemes)} schemes processed", flush=True)

    if not records:
        return len(schemes), 0

    df = pd.DataFrame.from_records(records)
    df = add_category_percentiles(df)

    pct_cols = [
        "pct_cagr_3y",
        "pct_sharpe_3y",
        "pct_sortino_3y",
        "pct_max_drawdown",
        "pct_consistency",
        "fund_score",
        "category_peer_count",
    ]
    metric_cols = [
        "n_nav_points",
        "history_years",
        "cagr_1y",
        "cagr_3y",
        "cagr_5y",
        "cagr_10y",
        "ann_volatility",
        "max_drawdown",
        "sharpe_3y",
        "sortino_3y",
        "rolling_3y_windows",
        "rolling_3y_positive_pct",
        "rolling_3y_median_cagr",
        "alpha_3y",
        "beta_3y",
        "benchmark_code",
        "benchmark_name",
    ]

    written = 0
    for record in df.to_dict("records"):
        row = session.get(SchemeMetricsRow, record["scheme_code"]) or SchemeMetricsRow(
            scheme_code=record["scheme_code"]
        )
        for col in metric_cols + pct_cols:
            value = record.get(col)
            if pd.isna(value):
                value = None
            elif col in ("n_nav_points", "rolling_3y_windows", "category_peer_count"):
                value = int(value)
            setattr(row, col, value)
        row.score_category = record.get("category")
        session.merge(row)
        written += 1

    session.commit()
    return len(schemes), written
