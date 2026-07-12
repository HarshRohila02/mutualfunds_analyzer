from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class SchemeMetricsRow(Base):
    """Latest computed metrics + category-relative score per scheme.

    One row per scheme, overwritten on each nightly recompute (history of
    score evolution is a backlog item, not needed for v1 research flows).
    """

    __tablename__ = "scheme_metrics"

    scheme_code: Mapped[str] = mapped_column(ForeignKey("schemes.scheme_code"), primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    n_nav_points: Mapped[int] = mapped_column(Integer)
    history_years: Mapped[float] = mapped_column(Float)

    cagr_1y: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr_5y: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr_10y: Mapped[float | None] = mapped_column(Float, nullable=True)
    ann_volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    sortino_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_3y_windows: Mapped[int] = mapped_column(Integer, default=0)
    rolling_3y_positive_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_3y_median_cagr: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Category-relative percentiles (0-100, higher = better within category).
    pct_cagr_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_sharpe_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_sortino_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_consistency: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Composite 0-100 category-relative score + how many peers it was ranked against.
    fund_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    category_peer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_category: Mapped[str | None] = mapped_column(String, nullable=True)

    # Trailing-3y regression vs the category's index-fund proxy (see
    # analytics/benchmarks.py). Null when the category has no proxy or the
    # joint history is too short. NOTE: new columns here also need an entry
    # in db.run_light_migrations - create_all never ALTERs existing tables.
    alpha_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    beta_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark_code: Mapped[str | None] = mapped_column(String, nullable=True)
    benchmark_name: Mapped[str | None] = mapped_column(String, nullable=True)
