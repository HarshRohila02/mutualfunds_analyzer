"""Tools the research assistant can call. Each returns JSON-serialized data
pulled straight from our DB - the assistant must ground every number it
states in one of these results, never from model memory."""

from __future__ import annotations

import json
from dataclasses import asdict

from anthropic import beta_tool
from sqlalchemy import func, select

from app.analytics.manager_scoring import score_manager
from app.models import Manager, ManagerAssignment, Scheme, SchemeMetricsRow, SessionLocal


def _fund_summary_row(scheme: Scheme, metrics: SchemeMetricsRow | None) -> dict:
    out = {
        "scheme_code": scheme.scheme_code,
        "scheme_name": scheme.scheme_name,
        "fund_house": scheme.fund_house,
        "category": scheme.category,
    }
    if metrics:
        out.update(
            fund_score=metrics.fund_score,
            cagr_1y=metrics.cagr_1y,
            cagr_3y=metrics.cagr_3y,
            cagr_5y=metrics.cagr_5y,
            sharpe_3y=metrics.sharpe_3y,
        )
    return out


@beta_tool
def search_funds(query: str, limit: int = 10) -> str:
    """Search Indian mutual fund schemes by name substring. Only direct-growth
    plans are indexed. Returns scheme codes, names, categories and headline
    metrics, ordered by fund score.

    Args:
        query: Substring of the fund name, e.g. "Parag Parikh Flexi".
        limit: Max results (default 10, max 25).
    """
    limit = min(limit, 25)
    session = SessionLocal()
    try:
        rows = session.execute(
            select(Scheme, SchemeMetricsRow)
            .outerjoin(SchemeMetricsRow, Scheme.scheme_code == SchemeMetricsRow.scheme_code)
            .where(Scheme.scheme_name.icontains(query), Scheme.details_synced.is_(True))
            .order_by(SchemeMetricsRow.fund_score.desc().nullslast())
            .limit(limit)
        ).all()
        return json.dumps([_fund_summary_row(s, m) for s, m in rows])
    finally:
        session.close()


@beta_tool
def get_fund_details(scheme_code: str) -> str:
    """Full quantitative readout for one scheme: returns, risk, risk-adjusted
    metrics, category percentile ranks and the composite fund score, plus any
    known fund manager assignments.

    Args:
        scheme_code: AMFI scheme code, e.g. "122639".
    """
    session = SessionLocal()
    try:
        scheme = session.get(Scheme, scheme_code)
        if scheme is None:
            return json.dumps({"error": f"scheme {scheme_code} not found"})
        metrics = session.get(SchemeMetricsRow, scheme_code)
        assignments = session.execute(
            select(ManagerAssignment).where(ManagerAssignment.scheme_code == scheme_code)
        ).scalars().all()

        payload: dict = {
            "scheme_code": scheme.scheme_code,
            "scheme_name": scheme.scheme_name,
            "fund_house": scheme.fund_house,
            "category": scheme.category,
            "isin_growth": scheme.isin_growth,
            "metrics": None,
            "managers": [
                {"name": a.manager.name, "manager_id": a.manager_id,
                 "start_date": a.start_date.isoformat(),
                 "end_date": a.end_date.isoformat() if a.end_date else None,
                 "note": a.note}
                for a in assignments
            ],
        }
        if metrics:
            payload["metrics"] = {
                col: getattr(metrics, col)
                for col in (
                    "history_years", "n_nav_points", "cagr_1y", "cagr_3y", "cagr_5y",
                    "cagr_10y", "ann_volatility", "max_drawdown", "sharpe_3y",
                    "sortino_3y", "rolling_3y_positive_pct", "rolling_3y_median_cagr",
                    "pct_cagr_3y", "pct_sharpe_3y", "pct_sortino_3y", "pct_max_drawdown",
                    "pct_consistency", "fund_score", "category_peer_count", "score_category",
                    "alpha_3y", "beta_3y", "benchmark_name",
                )
            }
        return json.dumps(payload)
    finally:
        session.close()


@beta_tool
def get_top_funds(category: str | None = None, limit: int = 10) -> str:
    """Highest-scored live funds, optionally within one category. Scores are
    0-100, category-relative (a fund is only compared with its own peers).

    Args:
        category: Exact category name, e.g. "Equity Scheme - Mid Cap Fund".
            Omit for the overall top list.
        limit: Max results (default 10, max 25).
    """
    limit = min(limit, 25)
    session = SessionLocal()
    try:
        query = (
            select(Scheme, SchemeMetricsRow)
            .join(SchemeMetricsRow, Scheme.scheme_code == SchemeMetricsRow.scheme_code)
            .where(SchemeMetricsRow.fund_score.is_not(None))
            .order_by(SchemeMetricsRow.fund_score.desc())
            .limit(limit)
        )
        if category:
            query = query.where(Scheme.category == category)
        rows = session.execute(query).all()
        return json.dumps([_fund_summary_row(s, m) for s, m in rows])
    finally:
        session.close()


@beta_tool
def list_categories() -> str:
    """All scheme categories in the database with scheme counts. Useful to
    find the exact category string before calling get_top_funds."""
    session = SessionLocal()
    try:
        rows = session.execute(
            select(Scheme.category, func.count())
            .where(Scheme.details_synced.is_(True), Scheme.category.is_not(None))
            .group_by(Scheme.category)
            .order_by(func.count().desc())
        ).all()
        return json.dumps([{"category": c, "scheme_count": n} for c, n in rows])
    finally:
        session.close()


@beta_tool
def get_manager_profile(manager_name: str) -> str:
    """Profile and score for a fund manager from the curated dataset: tenure,
    per-fund tenure-window performance ranked against same-window category
    peers, and caveats. Coverage is a small curated seed - absence of a
    manager here says nothing about them.

    Args:
        manager_name: Full or partial manager name, e.g. "Naren" or
            "R. Srinivasan".
    """
    session = SessionLocal()
    try:
        manager = session.execute(
            select(Manager).where(Manager.name.icontains(manager_name))
        ).scalars().first()
        if manager is None:
            available = [m.name for m in session.execute(select(Manager)).scalars()]
            return json.dumps(
                {"error": f"no manager matching '{manager_name}' in curated dataset",
                 "available_managers": available}
            )
        return json.dumps(asdict(score_manager(session, manager)), default=str)
    finally:
        session.close()
