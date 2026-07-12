"""Recompute all scheme metrics + category-relative scores.

Usage: backend/.venv/Scripts/python backend/scripts/run_recompute.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.recompute import recompute_all
from app.models.db import Base, SessionLocal, engine, run_light_migrations


def main() -> None:
    Base.metadata.create_all(engine)
    run_light_migrations()
    session = SessionLocal()
    try:
        considered, written = recompute_all(session)
        print(f"Considered {considered} synced schemes, wrote {written} metric rows.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
