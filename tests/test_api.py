"""API-layer integration tests.

Uses the real FastAPI app via TestClient, but with:
  - the DB dependency overridden to the in-memory SQLite session (conftest `db`),
  - Gemini monkeypatched (no network),
  - the scheduler and auto-seed disabled.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.agent.pipeline as pipeline
import app.routers.zaproslar as zaproslar_router
from app.agent.gemini_agent import GeminiVerdict
from app.config import settings
from app.database import get_db
from app.main import app as fastapi_app


@pytest.fixture()
def client(db, monkeypatch):
    # No background generation / seeding during tests.
    monkeypatch.setattr(settings, "enable_scheduler", False)
    monkeypatch.setattr(settings, "auto_seed", False)

    # The POST /requests background task opens its own SessionLocal (real engine),
    # which bypasses our in-memory override; disable it so matching is driven
    # explicitly via POST /agent/run against the overridden session.
    monkeypatch.setattr(zaproslar_router, "match_in_background", lambda zid: None)

    # Always pick the first candidate, marked as a gemini decision.
    def fake_rank(zapros, candidates):
        return GeminiVerdict(best_mashina_id=candidates[0].mashina.id, score=0.88,
                             reasoning="test pick")
    monkeypatch.setattr(pipeline, "rank_with_gemini", fake_rank)

    fastapi_app.dependency_overrides[get_db] = lambda: db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


def _make_vehicle(client, plate="01 A001BC", location="Toshkent"):
    return client.post("/vehicles", json={
        "plate_number": plate, "location": location,
        "lat": 41.30, "lng": 69.25, "location_type": "gps"})


def test_create_vehicle_and_duplicate_conflict(client):
    r = _make_vehicle(client)
    assert r.status_code == 201
    assert r.json()["plate_number"] == "01 A001BC"

    dup = _make_vehicle(client)  # same plate
    assert dup.status_code == 409


def test_request_then_agent_run_logs_gemini_suggestion(client):
    _make_vehicle(client)
    r = client.post("/requests", json={
        "pickup_location": "Toshkent", "dropoff_location": "Buxoro",
        "load_date": "2026-07-01", "pickup_lat": 41.31, "pickup_lng": 69.24,
        "location_type": "gps"})
    assert r.status_code == 201
    rid = r.json()["id"]

    s = client.post(f"/agent/run/{rid}")
    assert s.status_code == 200
    body = s.json()
    assert body["request_id"] == rid
    assert body["reasoning"].startswith("[gemini]")
    assert body["score"] == 0.88
    assert body["latency_ms"] >= 0

    listed = client.get("/suggestions").json()
    assert any(x["id"] == body["id"] for x in listed)


def test_agent_run_unknown_request_404(client):
    assert client.post("/agent/run/999999").status_code == 404


def test_analytics_reflects_activity(client):
    _make_vehicle(client)
    rid = client.post("/requests", json={
        "pickup_location": "Toshkent", "dropoff_location": "Buxoro",
        "load_date": "2026-07-01", "pickup_lat": 41.31, "pickup_lng": 69.24,
        "location_type": "gps"}).json()["id"]
    client.post(f"/agent/run/{rid}")

    a = client.get("/analytics").json()
    assert a["total_requests"] >= 1
    assert a["gemini_suggestions"] >= 1
    assert a["fallback_suggestions"] == 0
