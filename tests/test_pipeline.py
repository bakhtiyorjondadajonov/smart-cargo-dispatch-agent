"""Pipeline tests with Gemini mocked — verifies a suggestion + latency is logged."""
from __future__ import annotations

from datetime import date

import pytest

import app.agent.gemini_agent as gemini_agent
import app.agent.pipeline as pipeline
from app.agent.gemini_agent import GeminiUnavailable, GeminiVerdict, _generate_with_retry
from app.models import AgentTakliflari, Malumotlar, Zaproslar


class _FakeModels:
    def __init__(self, fail_times):
        self.calls = 0
        self.fail_times = fail_times

    def generate_content(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient 503")
        return "OK"


class _FakeClient:
    def __init__(self, fail_times):
        self.models = _FakeModels(fail_times)


def test_generate_with_retry_recovers(monkeypatch):
    monkeypatch.setattr(gemini_agent.time, "sleep", lambda *_: None)  # no real backoff
    monkeypatch.setattr(gemini_agent.settings, "gemini_max_retries", 2)
    client = _FakeClient(fail_times=1)  # fail once, then succeed
    assert _generate_with_retry(client, "prompt", config=None) == "OK"
    assert client.models.calls == 2


def test_generate_with_retry_exhausts_and_raises(monkeypatch):
    monkeypatch.setattr(gemini_agent.time, "sleep", lambda *_: None)
    monkeypatch.setattr(gemini_agent.settings, "gemini_max_retries", 2)
    client = _FakeClient(fail_times=99)  # always fail
    with pytest.raises(GeminiUnavailable):
        _generate_with_retry(client, "prompt", config=None)
    assert client.models.calls == 3  # 1 + 2 retries


def _setup(db):
    v1 = Malumotlar(mashina_raqami="01 A001BC", joriy_lokatsiya="Toshkent",
                    lat=41.30, lng=69.25, location_type="gps")
    v2 = Malumotlar(mashina_raqami="40 B002CD", joriy_lokatsiya="Andijon",
                    lat=40.78, lng=72.34, location_type="gps")
    db.add_all([v1, v2])
    db.commit()
    zapros = Zaproslar(yuk_ortish_joyi="Toshkent", yuk_tushirish_joyi="Buxoro",
                       yuklash_sanasi=date.today(), ortish_lat=41.31, ortish_lng=69.24,
                       location_type="gps")
    db.add(zapros)
    db.commit()
    return zapros, v1, v2


def test_pipeline_uses_gemini_verdict(db, monkeypatch):
    zapros, v1, v2 = _setup(db)

    def fake_rank(z, candidates):
        return GeminiVerdict(best_mashina_id=v2.id, score=0.91, reasoning="picked v2")

    monkeypatch.setattr(pipeline, "rank_with_gemini", fake_rank)

    taklif = pipeline.run_matching(db, zapros.id)
    assert taklif is not None
    assert taklif.mashina_id == v2.id
    assert taklif.score == 0.91
    assert taklif.reasoning.startswith("[gemini]")
    assert taklif.latency_ms >= 0
    assert db.query(AgentTakliflari).count() == 1


def test_pipeline_falls_back_when_gemini_unavailable(db, monkeypatch):
    zapros, v1, v2 = _setup(db)

    def boom(z, candidates):
        raise GeminiUnavailable("no key")

    monkeypatch.setattr(pipeline, "rank_with_gemini", boom)

    taklif = pipeline.run_matching(db, zapros.id)
    assert taklif is not None
    # nearest candidate to the Tashkent pickup is v1
    assert taklif.mashina_id == v1.id
    assert taklif.reasoning.startswith("[fallback]")


def test_pipeline_no_vehicles_returns_none(db):
    zapros = Zaproslar(yuk_ortish_joyi="Toshkent", yuk_tushirish_joyi="Buxoro",
                       yuklash_sanasi=date.today(), location_type="named")
    db.add(zapros)
    db.commit()
    assert pipeline.run_matching(db, zapros.id) is None
