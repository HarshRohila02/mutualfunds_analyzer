from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.manager_scoring import score_manager
from app.models import get_session
from app.models.manager import Manager, ManagerAssignment

router = APIRouter(prefix="/api/managers", tags=["managers"])


class AssignmentOut(BaseModel):
    scheme_code: str
    scheme_name: str
    category: str | None
    start_date: date
    end_date: date | None
    window_years: float | None
    tenure_cagr: float | None
    tenure_sharpe: float | None
    peer_percentile: float | None
    peer_count: int | None
    skipped_reason: str | None
    note: str | None


class ManagerScoreOut(BaseModel):
    manager_id: int
    name: str
    amc: str | None
    bio: str | None
    career_start_year: int | None
    tenure_score: float | None
    performance_score: float | None
    composite: float | None
    assignments: list[AssignmentOut]
    caveats: list[str]


class ManagerSummary(BaseModel):
    manager_id: int
    name: str
    amc: str | None
    n_assignments: int


@router.get("", response_model=list[ManagerSummary])
def list_managers(session: Session = Depends(get_session)) -> list[ManagerSummary]:
    managers = session.execute(select(Manager).order_by(Manager.name)).scalars().all()
    return [
        ManagerSummary(
            manager_id=m.id, name=m.name, amc=m.amc, n_assignments=len(m.assignments)
        )
        for m in managers
    ]


@router.get("/{manager_id}", response_model=ManagerScoreOut)
def manager_detail(manager_id: int, session: Session = Depends(get_session)) -> ManagerScoreOut:
    manager = session.get(Manager, manager_id)
    if manager is None:
        raise HTTPException(404, f"Manager {manager_id} not found")
    return ManagerScoreOut(**asdict(score_manager(session, manager)))


@router.get("/by-scheme/{scheme_code}", response_model=list[ManagerScoreOut])
def managers_for_scheme(scheme_code: str, session: Session = Depends(get_session)) -> list[ManagerScoreOut]:
    assignments = session.execute(
        select(ManagerAssignment).where(ManagerAssignment.scheme_code == scheme_code)
    ).scalars().all()
    return [
        ManagerScoreOut(**asdict(score_manager(session, a.manager))) for a in assignments
    ]
