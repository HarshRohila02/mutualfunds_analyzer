from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db import Base


class Manager(Base):
    __tablename__ = "managers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    amc: Mapped[str | None] = mapped_column(String, nullable=True)
    career_start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Seed data is curated by hand, not pulled from a verified feed - the UI
    # and assistant must surface this so nobody mistakes it for gospel.
    data_source: Mapped[str] = mapped_column(String, default="curated-seed")

    assignments: Mapped[list["ManagerAssignment"]] = relationship(
        back_populates="manager", cascade="all, delete-orphan"
    )


class ManagerAssignment(Base):
    __tablename__ = "manager_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    manager_id: Mapped[int] = mapped_column(ForeignKey("managers.id"), index=True)
    scheme_code: Mapped[str] = mapped_column(ForeignKey("schemes.scheme_code"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # None = current
    role: Mapped[str] = mapped_column(String, default="lead")  # lead | co
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    manager: Mapped["Manager"] = relationship(back_populates="assignments")
