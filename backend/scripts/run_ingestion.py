"""Phase 1 CLI: sync the scheme master, then backfill category/NAV details
for a filtered subset of schemes.

Usage:
  backend/.venv/Scripts/python backend/scripts/run_ingestion.py master
  backend/.venv/Scripts/python backend/scripts/run_ingestion.py backfill --contains "Direct Plan-Growth" --limit 300
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.mfapi_source import MFApiSource
from app.ingestion.sync import backfill_details, sync_scheme_master
from app.models.db import Base, SessionLocal, engine
from app.models.scheme import Scheme


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("master", help="Sync the full scheme code/name/ISIN universe")

    backfill_parser = sub.add_parser("backfill", help="Sync category + NAV history for a subset")
    backfill_parser.add_argument("--contains", default=None, help="Substring filter on scheme_name")
    backfill_parser.add_argument("--limit", type=int, default=None)
    backfill_parser.add_argument("--sleep", type=float, default=0.15)

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
                source, session, name_contains=args.contains, limit=args.limit, sleep_seconds=args.sleep
            )
            print(f"Backfill attempted={attempted} succeeded={succeeded}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
