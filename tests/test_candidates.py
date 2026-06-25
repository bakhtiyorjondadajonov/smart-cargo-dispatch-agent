"""Tests for the deterministic candidate prefilter (no LLM, no network)."""
from __future__ import annotations

from datetime import date

from app.agent.candidates import select_candidates
from app.geo import haversine_km, normalize_region, region_distance_rank
from app.models import Malumotlar, Zaproslar


def test_haversine_known_distance():
    # Tashkent -> Samarkand is ~270 km as the crow flies.
    d = haversine_km(41.2995, 69.2401, 39.6542, 66.9597)
    assert 250 < d < 300


def test_normalize_region():
    assert normalize_region("Samarqand shahri") == "Samarqand"
    assert normalize_region("somewhere unknown") is None


def test_region_distance_rank_same_region_is_zero():
    ranks = region_distance_rank("Toshkent")
    assert ranks["Toshkent"] == 0
    assert ranks["Toshkent viloyati"] == 1


def test_gps_mode_ranks_nearest_first(db):
    near = Malumotlar(mashina_raqami="01 A001BC", joriy_lokatsiya="Toshkent",
                      lat=41.30, lng=69.25, location_type="gps")
    far = Malumotlar(mashina_raqami="02 B002CD", joriy_lokatsiya="Xorazm",
                     lat=41.55, lng=60.63, location_type="gps")
    db.add_all([near, far])
    db.commit()

    zapros = Zaproslar(yuk_ortish_joyi="Toshkent", yuk_tushirish_joyi="Buxoro",
                       yuklash_sanasi=date.today(), ortish_lat=41.31, ortish_lng=69.24,
                       location_type="gps")
    db.add(zapros)
    db.commit()

    cands = select_candidates(db, zapros, top_n=10, max_radius_km=2000)
    assert cands[0].mashina.id == near.id
    assert cands[0].distance_km < cands[1].distance_km


def test_named_mode_prefers_same_region(db):
    same = Malumotlar(mashina_raqami="40 A001BC", joriy_lokatsiya="Andijon",
                      lat=40.78, lng=72.34, location_type="named")
    neighbour = Malumotlar(mashina_raqami="30 B002CD", joriy_lokatsiya="Namangan",
                           lat=41.0, lng=71.67, location_type="named")
    db.add_all([same, neighbour])
    db.commit()

    zapros = Zaproslar(yuk_ortish_joyi="Andijon", yuk_tushirish_joyi="Toshkent",
                       yuklash_sanasi=date.today(), location_type="named")
    db.add(zapros)
    db.commit()

    cands = select_candidates(db, zapros, top_n=10, max_radius_km=2000)
    assert cands[0].mashina.id == same.id
    assert cands[0].region_hops == 0
