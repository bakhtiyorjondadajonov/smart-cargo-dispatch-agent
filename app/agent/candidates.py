"""Deterministic candidate prefilter.

This narrows the full fleet down to the most plausible vehicles BEFORE the LLM
sees them. Two purposes:
  1. Keep the Gemini prompt small and cheap (top-N, not the whole table).
  2. Ground the LLM so it can only choose among real, nearby vehicles.

Ranking is done in Python (not SQL) so it is identical on Postgres and SQLite.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.geo import (
    REGION_CENTERS,
    haversine_km,
    normalize_region,
    region_distance_rank,
)
from app.models import Malumotlar, Zaproslar


@dataclass
class Candidate:
    mashina: Malumotlar
    distance_km: float | None      # set in gps mode (and named mode via centroids)
    region_hops: int | None        # set in named mode (0 = same region)

    @property
    def distance_label(self) -> str:
        if self.distance_km is not None:
            return f"{self.distance_km:.0f} km"
        if self.region_hops is not None:
            return f"{self.region_hops} region-hop(s) away"
        return "unknown distance"


def _vehicle_coords(v: Malumotlar) -> tuple[float, float] | None:
    if v.lat is not None and v.lng is not None:
        return v.lat, v.lng
    region = normalize_region(v.joriy_lokatsiya)
    if region:
        return REGION_CENTERS[region]
    return None


def select_candidates(
    db: Session, zapros: Zaproslar, top_n: int, max_radius_km: float
) -> list[Candidate]:
    vehicles = list(db.execute(select(Malumotlar)).scalars())
    if not vehicles:
        return []

    # GPS mode: rank everyone by haversine distance to the pickup point.
    if zapros.location_type == "gps" and zapros.ortish_lat is not None:
        scored: list[Candidate] = []
        for v in vehicles:
            coords = _vehicle_coords(v)
            if coords is None:
                continue
            d = haversine_km(zapros.ortish_lat, zapros.ortish_lng, coords[0], coords[1])
            if d <= max_radius_km:
                scored.append(Candidate(mashina=v, distance_km=d, region_hops=None))
        scored.sort(key=lambda c: c.distance_km)
        return scored[:top_n]

    # Named mode: rank by region-graph hops, then by centroid distance as a tiebreak.
    pickup_region = normalize_region(zapros.yuk_ortish_joyi)
    if pickup_region is None:
        # Unknown region: fall back to pure centroid distance if we have coords.
        return _fallback_by_centroid(zapros, vehicles, top_n, max_radius_km)

    hops = region_distance_rank(pickup_region)
    pickup_center = REGION_CENTERS[pickup_region]
    scored = []
    for v in vehicles:
        v_region = normalize_region(v.joriy_lokatsiya)
        hop = hops.get(v_region) if v_region else None
        if hop is None:
            continue  # unreachable / unknown region for this vehicle
        coords = _vehicle_coords(v)
        d = (
            haversine_km(pickup_center[0], pickup_center[1], coords[0], coords[1])
            if coords
            else None
        )
        scored.append(Candidate(mashina=v, distance_km=d, region_hops=hop))
    scored.sort(key=lambda c: (c.region_hops, c.distance_km if c.distance_km is not None else 1e9))
    return scored[:top_n]


def _fallback_by_centroid(zapros, vehicles, top_n, max_radius_km) -> list[Candidate]:
    region = normalize_region(zapros.yuk_ortish_joyi)
    if region is None:
        # Truly unknown pickup: just return the first top_n vehicles, no distance.
        return [Candidate(mashina=v, distance_km=None, region_hops=None) for v in vehicles[:top_n]]
    center = REGION_CENTERS[region]
    scored = []
    for v in vehicles:
        coords = _vehicle_coords(v)
        if coords is None:
            continue
        d = haversine_km(center[0], center[1], coords[0], coords[1])
        if d <= max_radius_km:
            scored.append(Candidate(mashina=v, distance_km=d, region_hops=None))
    scored.sort(key=lambda c: c.distance_km)
    return scored[:top_n]
