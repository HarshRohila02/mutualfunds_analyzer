"""Load the curated manager seed into the DB and print a scoring preview.

Usage: backend/.venv/Scripts/python backend/scripts/load_managers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.analytics.manager_scoring import score_manager
from app.ingestion.manager_seed import load_manager_seed
from app.models import Base, Manager, SessionLocal, engine


def main() -> None:
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        n_managers, n_assignments, warnings = load_manager_seed(session)
        print(f"Loaded {n_managers} managers, {n_assignments} assignments.")
        for warning in warnings:
            print(" ", warning)

        print("\nScoring preview:")
        for manager in session.execute(select(Manager).order_by(Manager.name)).scalars():
            score = score_manager(session, manager)
            print(
                f"  {score.name:22s} composite={score.composite} "
                f"(tenure={score.tenure_score}, perf={score.performance_score})"
            )
            for a in score.assignments:
                if a.skipped_reason:
                    print(f"    - {a.scheme_name[:50]:52s} SKIPPED: {a.skipped_reason}")
                else:
                    print(
                        f"    - {a.scheme_name[:50]:52s} {a.window_years}y "
                        f"cagr={a.tenure_cagr:.1%} sharpe={a.tenure_sharpe:.2f} "
                        f"peer_pct={a.peer_percentile} (n={a.peer_count})"
                    )
    finally:
        session.close()


if __name__ == "__main__":
    main()
