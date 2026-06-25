"""Seed the vehicle fleet (malumotlar) with sample data across Uzbekistan.

Idempotent: does nothing if the table already has vehicles. Roughly half the
fleet is stored as named regions and half as GPS coordinates so both matching
modes have data to work with.

Run standalone:  python -m app.seed
"""
from __future__ import annotations

import random

from sqlalchemy import func, select

from app.database import SessionLocal
from app.geo import ALL_REGIONS, REGION_CENTERS
from app.models import Malumotlar

FLEET_SIZE = 60
_LETTERS = "ABCDEFGHKLMNOPRSTXYZ"


def _plate(i: int, rng: random.Random) -> str:
    # Uzbek-style plate, e.g. "01 A123BC"
    region_code = f"{rng.randint(1, 95):02d}"
    return f"{region_code} {rng.choice(_LETTERS)}{i:03d}{rng.choice(_LETTERS)}{rng.choice(_LETTERS)}"


def seed_vehicles(force: bool = False) -> int:
    """Insert sample vehicles. Returns number inserted (0 if already seeded)."""
    rng = random.Random(42)  # deterministic fleet
    db = SessionLocal()
    try:
        existing = db.scalar(select(func.count(Malumotlar.id))) or 0
        if existing and not force:
            return 0

        inserted = 0
        for i in range(1, FLEET_SIZE + 1):
            region = rng.choice(ALL_REGIONS)
            base_lat, base_lng = REGION_CENTERS[region]
            # jitter coordinates a little so vehicles are spread around the centroid
            lat = round(base_lat + rng.uniform(-0.4, 0.4), 5)
            lng = round(base_lng + rng.uniform(-0.4, 0.4), 5)

            if i % 2 == 0:  # GPS-located vehicle
                v = Malumotlar(
                    mashina_raqami=_plate(i, rng),
                    joriy_lokatsiya=f"{region} ({lat}, {lng})",
                    lat=lat,
                    lng=lng,
                    location_type="gps",
                )
            else:  # named-location vehicle (still carries centroid coords as a hint)
                v = Malumotlar(
                    mashina_raqami=_plate(i, rng),
                    joriy_lokatsiya=region,
                    lat=lat,
                    lng=lng,
                    location_type="named",
                )
            db.add(v)
            inserted += 1
        db.commit()
        return inserted
    finally:
        db.close()


if __name__ == "__main__":
    n = seed_vehicles()
    print(f"Seeded {n} vehicles." if n else "Vehicles already present; nothing to do.")
