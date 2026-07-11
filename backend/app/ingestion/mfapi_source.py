from __future__ import annotations

from datetime import date, datetime

import httpx

from app.config import settings
from app.ingestion.base import MFDataSource, NavPoint, SchemeInfo


class MFApiSource(MFDataSource):
    """https://www.mfapi.in - free, no-auth, NAV history + basic scheme metadata."""

    name = "mfapi.in"

    def __init__(self, base_url: str | None = None, timeout: float = 15.0) -> None:
        self._base_url = base_url or settings.mfapi_base_url
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    def search_schemes(self, query: str) -> list[SchemeInfo]:
        resp = self._client.get("/mf/search", params={"q": query})
        resp.raise_for_status()
        return [
            SchemeInfo(scheme_code=str(row["schemeCode"]), scheme_name=row["schemeName"])
            for row in resp.json()
        ]

    def get_scheme_info(self, scheme_code: str) -> SchemeInfo | None:
        resp = self._client.get(f"/mf/{scheme_code}")
        if resp.status_code != 200:
            return None
        payload = resp.json()
        meta = payload.get("meta", {})
        if not meta:
            return None
        return SchemeInfo(
            scheme_code=str(meta.get("scheme_code", scheme_code)),
            scheme_name=meta.get("scheme_name", ""),
            fund_house=meta.get("fund_house"),
            category=meta.get("scheme_category"),
            sub_category=meta.get("scheme_type"),
            isin_growth=meta.get("isin_growth"),
            isin_div_reinvestment=meta.get("isin_div_reinvestment"),
        )

    def get_nav_history(
        self, scheme_code: str, start: date | None = None, end: date | None = None
    ) -> list[NavPoint]:
        resp = self._client.get(f"/mf/{scheme_code}")
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        points = [
            NavPoint(nav_date=datetime.strptime(row["date"], "%d-%m-%Y").date(), nav=float(row["nav"]))
            for row in rows
            if row.get("nav") not in (None, "", "N.A.")
        ]
        if start:
            points = [p for p in points if p.nav_date >= start]
        if end:
            points = [p for p in points if p.nav_date <= end]
        return sorted(points, key=lambda p: p.nav_date)

    def get_latest_nav(self, scheme_code: str) -> NavPoint | None:
        resp = self._client.get(f"/mf/{scheme_code}/latest")
        if resp.status_code != 200:
            return None
        rows = resp.json().get("data", [])
        if not rows:
            return None
        row = rows[0]
        return NavPoint(nav_date=datetime.strptime(row["date"], "%d-%m-%Y").date(), nav=float(row["nav"]))
