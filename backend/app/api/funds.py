from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import NavHistory, Scheme, SchemeMetricsRow, get_session

router = APIRouter(prefix="/api/funds", tags=["funds"])


class FundSummary(BaseModel):
    scheme_code: str
    scheme_name: str
    fund_house: str | None
    category: str | None
    fund_score: float | None = None
    cagr_3y: float | None = None
    sharpe_3y: float | None = None


class NavPointOut(BaseModel):
    date: date
    nav: float


class MetricsOut(BaseModel):
    computed_at: str | None
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
    rolling_3y_windows: int
    rolling_3y_positive_pct: float | None
    rolling_3y_median_cagr: float | None
    pct_cagr_3y: float | None
    pct_sharpe_3y: float | None
    pct_sortino_3y: float | None
    pct_max_drawdown: float | None
    pct_consistency: float | None
    fund_score: float | None
    category_peer_count: int | None
    score_category: str | None


class FundDetail(BaseModel):
    scheme_code: str
    scheme_name: str
    fund_house: str | None
    category: str | None
    sub_category: str | None
    isin_growth: str | None
    metrics: MetricsOut | None


@router.get("/search", response_model=list[FundSummary])
def search_funds(
    q: str = Query(min_length=2),
    limit: int = Query(default=25, le=100),
    session: Session = Depends(get_session),
) -> list[FundSummary]:
    rows = session.execute(
        select(Scheme, SchemeMetricsRow)
        .outerjoin(SchemeMetricsRow, Scheme.scheme_code == SchemeMetricsRow.scheme_code)
        .where(Scheme.scheme_name.icontains(q), Scheme.details_synced.is_(True))
        .order_by(SchemeMetricsRow.fund_score.desc().nullslast())
        .limit(limit)
    ).all()
    return [
        FundSummary(
            scheme_code=scheme.scheme_code,
            scheme_name=scheme.scheme_name,
            fund_house=scheme.fund_house,
            category=scheme.category,
            fund_score=metrics.fund_score if metrics else None,
            cagr_3y=metrics.cagr_3y if metrics else None,
            sharpe_3y=metrics.sharpe_3y if metrics else None,
        )
        for scheme, metrics in rows
    ]


@router.get("/top", response_model=list[FundSummary])
def top_funds(
    category: str | None = None,
    limit: int = Query(default=20, le=100),
    session: Session = Depends(get_session),
) -> list[FundSummary]:
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
    return [
        FundSummary(
            scheme_code=scheme.scheme_code,
            scheme_name=scheme.scheme_name,
            fund_house=scheme.fund_house,
            category=scheme.category,
            fund_score=metrics.fund_score,
            cagr_3y=metrics.cagr_3y,
            sharpe_3y=metrics.sharpe_3y,
        )
        for scheme, metrics in rows
    ]


@router.get("/categories", response_model=list[dict])
def categories(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.execute(
        select(Scheme.category, func.count())
        .where(Scheme.details_synced.is_(True), Scheme.category.is_not(None))
        .group_by(Scheme.category)
        .order_by(func.count().desc())
    ).all()
    return [{"category": category, "scheme_count": count} for category, count in rows]


@router.get("/{scheme_code}", response_model=FundDetail)
def fund_detail(scheme_code: str, session: Session = Depends(get_session)) -> FundDetail:
    scheme = session.get(Scheme, scheme_code)
    if scheme is None:
        raise HTTPException(404, f"Scheme {scheme_code} not found")
    metrics = session.get(SchemeMetricsRow, scheme_code)
    return FundDetail(
        scheme_code=scheme.scheme_code,
        scheme_name=scheme.scheme_name,
        fund_house=scheme.fund_house,
        category=scheme.category,
        sub_category=scheme.sub_category,
        isin_growth=scheme.isin_growth,
        metrics=MetricsOut(
            computed_at=metrics.computed_at.isoformat() if metrics.computed_at else None,
            **{
                col: getattr(metrics, col)
                for col in MetricsOut.model_fields
                if col != "computed_at"
            },
        )
        if metrics
        else None,
    )


@router.get("/{scheme_code}/nav", response_model=list[NavPointOut])
def nav_history(
    scheme_code: str,
    start: date | None = None,
    session: Session = Depends(get_session),
) -> list[NavPointOut]:
    query = (
        select(NavHistory.nav_date, NavHistory.nav)
        .where(NavHistory.scheme_code == scheme_code)
        .order_by(NavHistory.nav_date)
    )
    if start:
        query = query.where(NavHistory.nav_date >= start)
    rows = session.execute(query).all()
    if not rows:
        raise HTTPException(404, f"No NAV history for scheme {scheme_code}")
    return [NavPointOut(date=nav_date, nav=nav) for nav_date, nav in rows]
