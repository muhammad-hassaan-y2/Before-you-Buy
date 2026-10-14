"""Durable state for Buy You Before simulations.

Postgres is the production target; column types stay dialect-portable so the
test suite can run against SQLite without a server.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class Simulation(Base):
    __tablename__ = "simulations"
    __table_args__ = (Index("ix_simulations_created_status", "created_at", "status"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    product_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shopper_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    room_width_m: Mapped[float] = mapped_column(Float, default=4.0)
    room_depth_m: Mapped[float] = mapped_column(Float, default=3.5)
    room_height_m: Mapped[float] = mapped_column(Float, default=2.4)

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    result: Mapped["SimulationResult | None"] = relationship(
        back_populates="simulation", uselist=False, cascade="all, delete-orphan"
    )


class SimulationResult(Base):
    """Snapshot of the product profile and the Shapely fit report, as JSON."""

    __tablename__ = "simulation_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False)

    product_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fit_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    simulation: Mapped[Simulation] = relationship(back_populates="result")
