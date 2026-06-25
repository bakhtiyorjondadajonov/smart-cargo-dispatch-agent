"""Pydantic schemas. The public API is in English; ``validation_alias`` maps each
field to its Uzbek ORM column so the DB matches the spec while the JSON reads cleanly.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# --------------------------- Vehicles (malumotlar) ---------------------------
class VehicleCreate(BaseModel):
    plate_number: str
    location: str
    lat: float | None = None
    lng: float | None = None
    location_type: str = "named"  # named | gps


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    plate_number: str = Field(validation_alias="mashina_raqami")
    location: str = Field(validation_alias="joriy_lokatsiya")
    lat: float | None = None
    lng: float | None = None
    location_type: str
    created_at: datetime


# --------------------------- Requests (zaproslar) ---------------------------
class RequestCreate(BaseModel):
    pickup_location: str
    dropoff_location: str
    load_date: date
    pickup_lat: float | None = None
    pickup_lng: float | None = None
    location_type: str = "named"  # named | gps


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    pickup_location: str = Field(validation_alias="yuk_ortish_joyi")
    dropoff_location: str = Field(validation_alias="yuk_tushirish_joyi")
    load_date: date = Field(validation_alias="yuklash_sanasi")
    pickup_lat: float | None = Field(default=None, validation_alias="ortish_lat")
    pickup_lng: float | None = Field(default=None, validation_alias="ortish_lng")
    location_type: str
    created_at: datetime


# ----------------------- Suggestions (agent_takliflari) ----------------------
class SuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    request_id: int = Field(validation_alias="zapros_id")
    vehicle_id: int = Field(validation_alias="mashina_id")
    request_created_at: datetime = Field(validation_alias="zapros_yaratilgan_vaqti")
    suggested_at: datetime = Field(validation_alias="agent_taklif_bergan_vaqti")
    latency_ms: int
    score: float | None = None
    reasoning: str | None = None


class AnalyticsOut(BaseModel):
    total_requests: int
    total_suggestions: int
    match_rate: float
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    gemini_suggestions: int
    fallback_suggestions: int
    requests_last_24h: int
    suggestions_last_24h: int
