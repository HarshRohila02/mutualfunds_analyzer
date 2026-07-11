"""Phase 0 spike: hit the live data sources and print raw shapes so we can
confirm assumptions baked into app/ingestion/*.py before building on top of them.

Run with: backend/.venv/Scripts/python backend/scripts/spike_data_sources.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

# HDFC Top 100 Fund - Growth, a large well-known scheme, good for sanity checks.
SAMPLE_SCHEME_CODE = "118533"


def spike_mfapi() -> None:
    print("=" * 60, "\nmfapi.in\n", "=" * 60, sep="")
    with httpx.Client(base_url="https://api.mfapi.in", timeout=15) as c:
        r = c.get("/mf/search", params={"q": "HDFC Top 100"})
        print("search status:", r.status_code)
        print(json.dumps(r.json()[:3], indent=2) if r.status_code == 200 else r.text[:500])

        r = c.get(f"/mf/{SAMPLE_SCHEME_CODE}")
        print("\nscheme detail status:", r.status_code)
        if r.status_code == 200:
            payload = r.json()
            print("meta:", json.dumps(payload.get("meta"), indent=2))
            print("data sample (first 2):", json.dumps(payload.get("data", [])[:2], indent=2))
            print("data points total:", len(payload.get("data", [])))

        r = c.get(f"/mf/{SAMPLE_SCHEME_CODE}/latest")
        print("\nlatest status:", r.status_code)
        print(r.text[:500])


def spike_mfdata() -> None:
    print("\n", "=" * 60, "\nmfdata.in\n", "=" * 60, sep="")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) mf-analyzer-spike/0.1"}
    with httpx.Client(base_url="https://mfdata.in", timeout=15, headers=headers) as c:
        for path in (
            "/api/v1/schemes/118533",
            "/api/v1/schemes/search?q=HDFC",
            "/docs",
        ):
            try:
                r = c.get(path)
                print(f"\nGET {path} -> {r.status_code}")
                print(r.text[:800])
            except httpx.HTTPError as exc:
                print(f"\nGET {path} -> ERROR {exc}")


if __name__ == "__main__":
    spike_mfapi()
    spike_mfdata()
