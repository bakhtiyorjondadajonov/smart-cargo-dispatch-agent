"""SQLAlchemy models.

Table and column names are kept in Uzbek to match the assignment spec verbatim.
Columns marked "additive" are extras (not in the spec) that enable GPS matching
and latency/quality analytics; the spec-required columns are present exactly.

Timestamps use Python-side UTC defaults (datetime.utcnow) rather than DB server
defaults so latency math is consistent and tz-safe across Postgres and SQLite.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.utcnow()


class Zaproslar(Base):
    """Cargo transport requests."""

    __tablename__ = "zaproslar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    yuk_ortish_joyi: Mapped[str] = mapped_column(String(255), nullable=False)   # pickup
    yuk_tushirish_joyi: Mapped[str] = mapped_column(String(255), nullable=False)  # dropoff
    yuklash_sanasi: Mapped[Date] = mapped_column(Date, nullable=False)          # load date

    # --- additive: GPS support for pickup location ---
    ortish_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    ortish_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_type: Mapped[str] = mapped_column(String(16), default="named", nullable=False)  # named|gps

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    takliflar: Mapped[list["AgentTakliflari"]] = relationship(back_populates="zapros")


class Malumotlar(Base):
    """Vehicle fleet."""

    __tablename__ = "malumotlar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mashina_raqami: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)  # plate
    joriy_lokatsiya: Mapped[str] = mapped_column(String(255), nullable=False)            # current location

    # --- additive: GPS support for current location ---
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_type: Mapped[str] = mapped_column(String(16), default="named", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    takliflar: Mapped[list["AgentTakliflari"]] = relationship(back_populates="mashina")


class AgentTakliflari(Base):
    """Agent recommendation log (one row per recommended vehicle)."""

    __tablename__ = "agent_takliflari"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zapros_id: Mapped[int] = mapped_column(ForeignKey("zaproslar.id"), nullable=False, index=True)
    mashina_id: Mapped[int] = mapped_column(ForeignKey("malumotlar.id"), nullable=False, index=True)
    zapros_yaratilgan_vaqti: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    agent_taklif_bergan_vaqti: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # --- additive: monitoring / analytics ---
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    zapros: Mapped["Zaproslar"] = relationship(back_populates="takliflar")
    mashina: Mapped["Malumotlar"] = relationship(back_populates="takliflar")
