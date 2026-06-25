"""Geography helpers: Uzbekistan regions, their approximate centers, and a small
adjacency graph used for the named-location matching mode.

Coordinates are regional capital centroids — good enough for distance ranking
in this assignment (we are not doing turn-by-turn routing).
"""
from __future__ import annotations

import math

# region -> (lat, lng) approximate centroid
REGION_CENTERS: dict[str, tuple[float, float]] = {
    "Toshkent": (41.2995, 69.2401),
    "Toshkent viloyati": (41.0, 69.5),
    "Samarqand": (39.6542, 66.9597),
    "Buxoro": (39.7747, 64.4286),
    "Andijon": (40.7821, 72.3442),
    "Farg'ona": (40.3864, 71.7864),
    "Namangan": (40.9983, 71.6726),
    "Qashqadaryo": (38.8610, 65.7890),  # Qarshi
    "Surxondaryo": (37.2242, 67.2783),  # Termiz
    "Jizzax": (40.1158, 67.8422),
    "Sirdaryo": (40.4897, 68.7842),  # Guliston
    "Navoiy": (40.0844, 65.3792),
    "Xorazm": (41.5500, 60.6333),  # Urganch
    "Qoraqalpog'iston": (42.4600, 59.6100),  # Nukus
}

# Direct neighbours (drivable adjacency). Used as a fallback when no vehicle is
# in the exact pickup region.
REGION_ADJACENCY: dict[str, list[str]] = {
    "Toshkent": ["Toshkent viloyati", "Sirdaryo"],
    "Toshkent viloyati": ["Toshkent", "Sirdaryo", "Jizzax", "Namangan"],
    "Sirdaryo": ["Toshkent viloyati", "Jizzax", "Toshkent"],
    "Jizzax": ["Sirdaryo", "Samarqand", "Toshkent viloyati"],
    "Samarqand": ["Jizzax", "Navoiy", "Qashqadaryo"],
    "Navoiy": ["Samarqand", "Buxoro", "Qashqadaryo"],
    "Buxoro": ["Navoiy", "Xorazm", "Qashqadaryo"],
    "Qashqadaryo": ["Samarqand", "Navoiy", "Surxondaryo", "Buxoro"],
    "Surxondaryo": ["Qashqadaryo"],
    "Xorazm": ["Buxoro", "Qoraqalpog'iston"],
    "Qoraqalpog'iston": ["Xorazm", "Buxoro"],
    "Andijon": ["Farg'ona", "Namangan"],
    "Farg'ona": ["Andijon", "Namangan"],
    "Namangan": ["Farg'ona", "Andijon", "Toshkent viloyati"],
}

ALL_REGIONS = list(REGION_CENTERS.keys())


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometers."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def normalize_region(text: str | None) -> str | None:
    """Best-effort map of a free-text location to a known region name."""
    if not text:
        return None
    t = text.strip().lower()
    for region in REGION_CENTERS:
        if region.lower() in t or t in region.lower():
            return region
    return None


def region_distance_rank(pickup_region: str) -> dict[str, int]:
    """Rank every region by graph hops from the pickup region (0 = same region)."""
    ranks = {pickup_region: 0}
    frontier = [pickup_region]
    hop = 0
    while frontier:
        hop += 1
        nxt = []
        for r in frontier:
            for neigh in REGION_ADJACENCY.get(r, []):
                if neigh not in ranks:
                    ranks[neigh] = hop
                    nxt.append(neigh)
        frontier = nxt
    return ranks
