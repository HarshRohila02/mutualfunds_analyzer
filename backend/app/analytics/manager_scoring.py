"""Manager Score: how good is the person, isolated from the fund's legacy.

For each assignment we look only at the NAV window where the manager was
actually in charge (intersected with available NAV data), compute the fund's
Sharpe over that window, and rank it against every category peer's Sharpe
computed over the *same calendar window*. That kills the two classic
distortions: inheriting a great fund's pre-tenure track record, and being
judged against peers over a different market regime.

Composite = 40% tenure length + 60% mean same-window peer percentile across
assignments. Only assignments with >= 1 year of usable overlap count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.metrics import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR
from app.models.manager import Manager, ManagerAssignment
from app.models.scheme import NavHistory, Scheme

MIN_OVERLAP_YEARS = 1.0
TENURE_FULL_CREDIT_YEARS = 10.0
WEIGHT_TENURE = 0.4
WEIGHT_PERFORMANCE = 0.6


@dataclass
class AssignmentScore:
    scheme_code: str
    scheme_name: str
    category: str | None
    start_date: date
    end_date: date | None
    window_years: float | None = None
    tenure_cagr: float | None = None
    tenure_sharpe: float | None = None
    peer_percentile: float | None = None  # 0-100 within category, same window
    peer_count: int | None = None
    skipped_reason: str | None = None
    note: str | None = None


@dataclass
class ManagerScore:
    manager_id: int
    name: str
    amc: str | None
    bio: str | None
    career_start_year: int | None
    tenure_score: float | None
    performance_score: float | None
    composite: float | None
    assignments: list[AssignmentScore] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


def _nav_series(session: Session, scheme_code: str, start: date, end: date | None) -> pd.Series:
    query = (
        select(NavHistory.nav_date, NavHistory.nav)
        .where(NavHistory.scheme_code == scheme_code, NavHistory.nav_date >= start)
        .order_by(NavHistory.nav_date)
    )
    if end:
        query = query.where(NavHistory.nav_date <= end)
    rows = session.execute(query).all()
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series(
        [r.nav for r in rows], index=pd.DatetimeIndex([pd.Timestamp(r.nav_date) for r in rows])
    )


def _window_sharpe_cagr(nav: pd.Series) -> tuple[float | None, float | None, float]:
    """(sharpe, cagr, actual_years) over the whole series given."""
    if len(nav) < 60:
        return None, None, 0.0
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    if years <= 0:
        return None, None, 0.0
    cagr = float((nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1)
    rets = nav.pct_change().dropna()
    vol = float(rets.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    if vol == 0:
        return None, cagr, years
    daily_rf = (1 + RISK_FREE_RATE_ANNUAL) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    sharpe = float((rets - daily_rf).mean() * TRADING_DAYS_PER_YEAR) / vol
    return sharpe, cagr, years


def score_assignment(session: Session, assignment: ManagerAssignment) -> AssignmentScore:
    scheme = session.get(Scheme, assignment.scheme_code)
    result = AssignmentScore(
        scheme_code=assignment.scheme_code,
        scheme_name=scheme.scheme_name if scheme else assignment.scheme_code,
        category=scheme.category if scheme else None,
        start_date=assignment.start_date,
        end_date=assignment.end_date,
        note=assignment.note,
    )

    nav = _nav_series(session, assignment.scheme_code, assignment.start_date, assignment.end_date)
    sharpe, cagr, years = _window_sharpe_cagr(nav)
    if years < MIN_OVERLAP_YEARS:
        result.skipped_reason = f"only {years:.1f}y of NAV overlap with tenure (need >= {MIN_OVERLAP_YEARS:.0f}y)"
        return result
    result.window_years = round(years, 2)
    result.tenure_cagr = cagr
    result.tenure_sharpe = sharpe

    if scheme is None or scheme.category is None or sharpe is None:
        return result

    # Same-window Sharpe for every category peer with data in the window.
    window_start = nav.index[0].date()
    window_end = nav.index[-1].date()
    peer_codes = [
        row[0]
        for row in session.execute(
            select(Scheme.scheme_code).where(
                Scheme.category == scheme.category,
                Scheme.details_synced.is_(True),
                Scheme.scheme_code != assignment.scheme_code,
            )
        )
    ]
    peer_sharpes: list[float] = []
    for code in peer_codes:
        peer_nav = _nav_series(session, code, window_start, window_end)
        peer_sharpe, _, peer_years = _window_sharpe_cagr(peer_nav)
        # Peer must cover (nearly) the same window to be a fair comparison.
        if peer_sharpe is not None and peer_years >= years * 0.9:
            peer_sharpes.append(peer_sharpe)

    if len(peer_sharpes) >= 5:
        result.peer_count = len(peer_sharpes)
        result.peer_percentile = round(
            float((np.array(peer_sharpes) < sharpe).mean() * 100), 1
        )
    return result


def score_manager(session: Session, manager: Manager) -> ManagerScore:
    result = ManagerScore(
        manager_id=manager.id,
        name=manager.name,
        amc=manager.amc,
        bio=manager.bio,
        career_start_year=manager.career_start_year,
        tenure_score=None,
        performance_score=None,
        composite=None,
    )
    if manager.data_source == "curated-seed":
        result.caveats.append(
            "Manager data comes from a hand-curated seed dataset, not a verified feed."
        )

    scored = [score_assignment(session, a) for a in manager.assignments]
    result.assignments = scored

    usable = [s for s in scored if s.window_years is not None]
    if not usable:
        result.caveats.append("No assignment had enough NAV overlap to score.")
        return result

    longest = max(s.window_years for s in usable)
    result.tenure_score = round(min(longest / TENURE_FULL_CREDIT_YEARS, 1.0) * 100, 1)

    percentiles = [s.peer_percentile for s in usable if s.peer_percentile is not None]
    if percentiles:
        result.performance_score = round(float(np.mean(percentiles)), 1)
        result.composite = round(
            WEIGHT_TENURE * result.tenure_score + WEIGHT_PERFORMANCE * result.performance_score, 1
        )
    else:
        result.caveats.append(
            "No peer percentile could be computed (too few same-window category peers); composite omitted."
        )
    return result
