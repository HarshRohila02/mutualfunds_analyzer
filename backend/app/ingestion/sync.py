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
    name_contains: list[str] | None = None,
    limit: int | None = None,
    workers: int = 8,
    progress_every: int = 100,
) -> tuple[int, int]:
    """Sync details+NAV history for schemes not yet synced, optionally
    filtered by substrings of scheme_name (all must match - e.g.
    ["Direct", "Growth"] cuts the ~37.6k universe down to the ~5k
    actively-relevant subset) and capped by `limit` so this is safe to
    run incrementally. Re-running skips already-synced schemes.

    HTTP fetches run on a thread pool (httpx.Client is thread-safe); all
    SQLite writes stay on the calling thread and are bulk-inserted.

    Returns (attempted, succeeded).
    """
    from concurrent.futures import ThreadPoolExecutor
    from app.ingestion.mfapi_source import MFApiSource

    if not isinstance(source, MFApiSource):
        raise NotImplementedError("Parallel backfill currently assumes MFApiSource.get_scheme_full")

    query = select(Scheme.scheme_code).where(Scheme.details_synced.is_(False))
    for fragment in name_contains or []:
        query = query.where(Scheme.scheme_name.contains(fragment))
    if limit:
        query = query.limit(limit)
    codes = [row[0] for row in session.execute(query)]

    succeeded = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (code, result) in enumerate(
            zip(codes, pool.map(lambda c: _fetch_with_retry(source, c), codes)), 1
        ):
            if result is not None:
                _write_scheme(session, code, *result)
                succeeded += 1
            if progress_every and i % progress_every == 0:
                print(f"  progress: {i}/{len(codes)} attempted, {succeeded} succeeded", flush=True)
    session.commit()
    return len(codes), succeeded


def _fetch_with_retry(source, code: str, attempts: int = 4):
    """Network blips (TLS handshake timeouts etc.) over a multi-thousand-call
    backfill are a certainty, not an edge case - retry with backoff and treat
    a scheme that still fails as skipped rather than aborting the whole run."""
    import httpx

    for attempt in range(attempts):
        try:
            return source.get_scheme_full(code)
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            if attempt == attempts - 1:
                print(f"  SKIP {code}: {type(exc).__name__} after {attempts} attempts", flush=True)
                return None
            time.sleep(2**attempt)
    return None


def _write_scheme(session: Session, scheme_code: str, info, points) -> None:
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
    new_rows = [
        {"scheme_code": scheme_code, "nav_date": p.nav_date, "nav": p.nav}
        for p in points
        if p.nav_date not in existing_dates
    ]
    if new_rows:
        session.execute(NavHistory.__table__.insert(), new_rows)
    session.commit()
