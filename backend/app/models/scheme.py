from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db import Base


class Scheme(Base):
    __tablename__ = "schemes"

    scheme_code: Mapped[str] = mapped_column(String, primary_key=True)
    scheme_name: Mapped[str] = mapped_column(String, index=True)
    fund_house: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    sub_category: Mapped[str | None] = mapped_column(String, nullable=True)
    isin_growth: Mapped[str | None] = mapped_column(String, nullable=True)
    isin_div_reinvestment: Mapped[str | None] = mapped_column(String, nullable=True)

    # True once we've pulled per-scheme detail (category, fund_house, NAV history).
    # Right after the scheme-master sync this is False for the whole ~37.6k universe.
    details_synced: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    nav_history: Mapped[list["NavHistory"]] = relationship(back_populates="scheme", cascade="all, delete-orphan")


class NavHistory(Base):
    __tablename__ = "nav_history"
    __table_args__ = (UniqueConstraint("scheme_code", "nav_date", name="uq_nav_scheme_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scheme_code: Mapped[str] = mapped_column(ForeignKey("schemes.scheme_code"), index=True)
    nav_date: Mapped[date] = mapped_column(Date, index=True)
    nav: Mapped[float] = mapped_column(Float)

    scheme: Mapped["Scheme"] = relationship(back_populates="nav_history")


class CategoryBenchmark(Base):
    """Curated category -> AMFI tier-1 benchmark name mapping.

    Reference data, not (yet) backed by a live benchmark NAV feed - see
    plan backlog. Kept as a table rather than a hardcoded dict so it can be
    corrected/extended without a code change once a real index-NAV source
    is wired up.
    """

    __tablename__ = "category_benchmarks"

    category: Mapped[str] = mapped_column(String, primary_key=True)
    benchmark_name: Mapped[str] = mapped_column(String)
