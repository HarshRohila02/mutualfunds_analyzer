"""Nightly data pipeline: refresh NAVs then recompute metrics/scores.

In-process APScheduler - no external infra. Runs at 02:30 IST, after AMFI's
late-evening NAV publication has settled. Disable with SCHEDULER_ENABLED=0.
"""

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def nightly_pipeline() -> None:
    from app.analytics.recompute import recompute_all
    from app.ingestion.mfapi_source import MFApiSource
    from app.ingestion.sync import refresh_nav_history, sync_scheme_master
    from app.models import SessionLocal

    session = SessionLocal()
    source = MFApiSource()
    try:
        inserted = sync_scheme_master(source, session)
        logger.info("nightly: scheme master synced, %d new schemes", inserted)
        attempted, succeeded = refresh_nav_history(source, session)
        logger.info("nightly: NAV refresh %d/%d schemes", succeeded, attempted)
        considered, written = recompute_all(session)
        logger.info("nightly: recomputed %d metric rows (of %d schemes)", written, considered)
    except Exception:
        logger.exception("nightly pipeline failed")
    finally:
        session.close()


def start_scheduler() -> BackgroundScheduler | None:
    if os.environ.get("SCHEDULER_ENABLED", "1") == "0":
        logger.info("scheduler disabled via SCHEDULER_ENABLED=0")
        return None
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(nightly_pipeline, CronTrigger(hour=2, minute=30), id="nightly")
    scheduler.start()
    return scheduler
