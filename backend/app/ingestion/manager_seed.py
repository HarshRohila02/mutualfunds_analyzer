"""Load the curated manager seed JSON, resolving each assignment's
scheme_name_hint to a real scheme_code in the schemes table."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.models.manager import Manager, ManagerAssignment
from app.models.scheme import Scheme

SEED_PATH = DATA_DIR / "seeds" / "managers.json"


def _resolve_scheme(session: Session, hint: str) -> Scheme | None:
    """Resolve a human-written scheme name to a scheme row.

    Strategy: exact match first, then all-words-present substring match,
    preferring Direct+Growth variants and the shortest (least-suffixed) name.
    """
    exact = session.execute(select(Scheme).where(Scheme.scheme_name == hint)).scalar_one_or_none()
    if exact:
        return exact

    words = [w for w in hint.replace("-", " ").split() if w.lower() not in ("plan", "option")]
    query = select(Scheme).where(Scheme.details_synced.is_(True))
    for word in words:
        query = query.where(Scheme.scheme_name.icontains(word))
    candidates = list(session.execute(query).scalars())
    if not candidates:
        # Retry without the Direct/Growth qualifiers in case the DB names
        # them differently (e.g. "Direct - Growth" vs "Direct Plan - Growth").
        core_words = [w for w in words if w.lower() not in ("direct", "growth")]
        query = select(Scheme).where(
            Scheme.details_synced.is_(True),
            Scheme.scheme_name.icontains("direct"),
            Scheme.scheme_name.icontains("growth"),
        )
        for word in core_words:
            query = query.where(Scheme.scheme_name.icontains(word))
        candidates = list(session.execute(query).scalars())
    if not candidates:
        return None
    # Least-suffixed name is almost always the plain Growth option rather
    # than IDCW/Bonus variants that also contain all the words.
    return min(candidates, key=lambda s: len(s.scheme_name))


def load_manager_seed(session: Session, seed_path: Path = SEED_PATH) -> tuple[int, int, list[str]]:
    """Upsert managers + assignments. Returns (managers, assignments, warnings)."""
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    warnings: list[str] = []
    n_managers = 0
    n_assignments = 0

    for entry in payload["managers"]:
        manager = session.execute(
            select(Manager).where(Manager.name == entry["name"])
        ).scalar_one_or_none()
        if manager is None:
            manager = Manager(name=entry["name"])
            session.add(manager)
        manager.amc = entry.get("amc")
        manager.career_start_year = entry.get("career_start_year")
        manager.bio = entry.get("bio")
        session.flush()
        n_managers += 1

        for item in entry.get("assignments", []):
            scheme = _resolve_scheme(session, item["scheme_name_hint"])
            if scheme is None:
                warnings.append(f"UNRESOLVED: {entry['name']} -> {item['scheme_name_hint']}")
                continue
            existing = session.execute(
                select(ManagerAssignment).where(
                    ManagerAssignment.manager_id == manager.id,
                    ManagerAssignment.scheme_code == scheme.scheme_code,
                )
            ).scalar_one_or_none()
            assignment = existing or ManagerAssignment(
                manager_id=manager.id, scheme_code=scheme.scheme_code
            )
            assignment.start_date = date.fromisoformat(item["start_date"])
            assignment.end_date = date.fromisoformat(item["end_date"]) if item.get("end_date") else None
            assignment.role = item.get("role", "lead")
            note = item.get("note") or ""
            if not item.get("verified", False):
                note = (note + " [unverified seed data]").strip()
            assignment.note = note or None
            if existing is None:
                session.add(assignment)
            n_assignments += 1

    session.commit()
    return n_managers, n_assignments, warnings
