from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.base import MFDataSource
from app.models.scheme import NavHistory, Scheme


def sync_scheme_master(source: MFDataSource, session: Session) -> int:
    """Upsert the full scheme universe (code + name + ISIN only, no category/NAV
    yet - that requires a per-scheme call). Cheap: a single HTTP request.
    Returns the number of new schemes inserted.
    """
    schemes = _list_all(source)
    existing = {row[0] for row in session.execute(select(Scheme.scheme_code))}
    inserted = 0
    for info in schemes:
        if info.scheme_code in existing:
            continue
        session.add(
            Scheme(
                scheme_code=info.scheme_code,
                scheme_name=info.scheme_name,
                isin_growth=info.isin_growth,
                isin_div_reinvestment=info.isin_div_reinvestment,
            )
        )
        inserted += 1
    session.commit()
    return inserted


def _list_all(source: MFDataSource):
    # MFApiSource doesn't implement a "list everything" method on the shared
    # interface (other providers may not support unbounded listing), so we
    # reach for the concrete client here rather than widening MFDataSource
    # for one provider's capability.
    from app.ingestion.mfapi_source import MFApiSource

    if isinstance(source, MFApiSource):
        resp = source._client.get("/mf")
        resp.raise_for_status()
        from app.ingestion.base import SchemeInfo

        return [
            SchemeInfo(
                scheme_code=str(row["schemeCode"]),
                scheme_name=row["schemeName"],
                isin_growth=row.get("isinGrowth"),
                isin_div_reinvestment=row.get("isinDivReinvestment"),
            )
            for row in resp.json()
        ]
    raise NotImplementedError(f"Full-universe listing not supported for {source.name}")


def sync_scheme_details(source: MFDataSource, session: Session, scheme_code: str) -> bool:
    """Fetch category/fund-house metadata + full NAV history for one scheme
    and upsert. Returns True if the scheme was found and synced."""
    info = source.get_scheme_info(scheme_code)
    if info is None:
        return False

    scheme = session.get(Scheme, scheme_code)
    if scheme is None:
        scheme = Scheme(scheme_code=scheme_code, scheme_name=info.scheme_name)
        session.add(scheme)
    scheme.scheme_name = info.scheme_name
    scheme.fund_house = info.fund_house
    scheme.category = info.category
    scheme.sub_category = info.sub_category
    scheme.isin_growth = info.isin_growth or scheme.isin_growth
    scheme.isin_div_reinvestment = info.isin_div_reinvestment or scheme.isin_div_reinvestment
    scheme.details_synced = True

    existing_dates = {
        row[0]
        for row in session.execute(select(NavHistory.nav_date).where(NavHistory.scheme_code == scheme_code))
    }
    for point in source.get_nav_history(scheme_code):
        if point.nav_date in existing_dates:
            continue
        session.add(NavHistory(scheme_code=scheme_code, nav_date=point.nav_date, nav=point.nav))

    session.commit()
    return True


def backfill_details(
    source: MFDataSource,
    session: Session,
    name_contains: str | None = None,
    limit: int | None = None,
    sleep_seconds: float = 0.15,
) -> tuple[int, int]:
    """Sync details+NAV history for schemes not yet synced, optionally
    filtered by a substring of scheme_name (e.g. "Direct" + "Growth" to
    cut the ~37.6k universe down to the actively-relevant subset) and
    capped by `limit` so this is safe to run incrementally.

    Returns (attempted, succeeded).
    """
    query = select(Scheme.scheme_code).where(Scheme.details_synced.is_(False))
    if name_contains:
        query = query.where(Scheme.scheme_name.contains(name_contains))
    if limit:
        query = query.limit(limit)

    codes = [row[0] for row in session.execute(query)]
    succeeded = 0
    for code in codes:
        if sync_scheme_details(source, session, code):
            succeeded += 1
        time.sleep(sleep_seconds)
    return len(codes), succeeded
