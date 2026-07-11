from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class SchemeInfo:
    scheme_code: str
    scheme_name: str
    fund_house: str | None = None
    category: str | None = None
    sub_category: str | None = None
    isin_growth: str | None = None
    isin_div_reinvestment: str | None = None


@dataclass
class NavPoint:
    nav_date: date
    nav: float


class MFDataSource(ABC):
    """Common interface every mutual-fund data provider must implement.

    Ingestion code depends only on this interface, never on a specific
    provider's response shape, so providers can be swapped or layered as
    primary/fallback without touching callers.
    """

    name: str

    @abstractmethod
    def search_schemes(self, query: str) -> list[SchemeInfo]: ...

    @abstractmethod
    def get_scheme_info(self, scheme_code: str) -> SchemeInfo | None: ...

    @abstractmethod
    def get_nav_history(
        self, scheme_code: str, start: date | None = None, end: date | None = None
    ) -> list[NavPoint]: ...

    @abstractmethod
    def get_latest_nav(self, scheme_code: str) -> NavPoint | None: ...
