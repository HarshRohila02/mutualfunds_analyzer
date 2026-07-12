"""Phase 1 CLI: sync the scheme master, then backfill category/NAV details
for a filtered subset of schemes.

Usage:
  backend/.venv/Scripts/python backend/scripts/run_ingestion.py master
  backend/.venv/Scripts/python backend/scripts/run_ingestion.py backfill --contains "Direct Plan-Growth" --limit 300
  backend/.venv/Scripts/python backend/scripts/run_ingestion.py refresh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.mfapi_source import MFApiSource
from app.ingestion.sync import backfill_details, refresh_nav_history, sync_scheme_master
from app.models.db import Base, SessionLocal, engine
from app.models.scheme import Scheme


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("master", help="Sync the full scheme code/name/ISIN universe")

    backfill_parser = sub.add_parser("backfill", help="Sync category + NAV history for a subset")
    backfill_parser.add_argument(
        "--contains", action="append", default=None, help="Substring filter on scheme_name (repeatable, ANDed)"
    )
    backfill_parser.add_argument("--limit", type=int, default=None)
    backfill_parser.add_argument("--workers", type=int, default=8)

    refresh_parser = sub.add_parser(
        "refresh", help="Re-fetch every synced scheme and append missing NAV dates (the nightly job, on demand)"
    )
    refresh_parser.add_argument("--workers", type=int, default=8)

    args = parser.parse_args()

    Base.metadata.create_all(engine)
    session = SessionLocal()
    source = MFApiSource()

    try:
        if args.command == "master":
            inserted = sync_scheme_master(source, session)
            total = session.query(Scheme).count()
            print(f"Inserted {inserted} new schemes. Total schemes in DB: {total}")
        elif args.command == "backfill":
            attempted, succeeded = backfill_details(
                source, session, name_contains=args.contains, limit=args.limit, workers=args.workers
            )
            print(f"Backfill attempted={attempted} succeeded={succeeded}")
        elif args.command == "refresh":
            attempted, succeeded = refresh_nav_history(source, session, workers=args.workers)
            print(f"Refresh attempted={attempted} succeeded={succeeded}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
