"""End-to-end matching pipeline: request -> candidates -> Gemini -> log.

This is what runs for every new request. It is deliberately resilient: if Gemini
is unavailable it falls back to the top deterministic candidate, so the system
always produces a suggestion and a latency measurement.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.candidates import select_candidates
from app.agent.gemini_agent import GeminiUnavailable, rank_with_gemini
from app.config import settings
from app.models import AgentTakliflari, Zaproslar

logger = logging.getLogger(__name__)


def run_matching(db: Session, zapros_id: int) -> AgentTakliflari | None:
    """Match one request and persist the recommendation. Returns the log row."""
    zapros = db.get(Zaproslar, zapros_id)
    if zapros is None:
        logger.warning("run_matching: zapros %s not found", zapros_id)
        return None

    candidates = select_candidates(
        db, zapros, top_n=settings.candidate_top_n, max_radius_km=settings.max_radius_km
    )
    if not candidates:
        logger.warning("run_matching: no candidate vehicles for zapros %s", zapros_id)
        return None

    score: float | None = None
    reasoning: str
    try:
        verdict = rank_with_gemini(zapros, candidates)
        chosen = next(c for c in candidates if c.mashina.id == verdict.best_mashina_id)
        score = verdict.score
        reasoning = f"[gemini] {verdict.reasoning}"
    except GeminiUnavailable as e:
        chosen = candidates[0]  # deterministic nearest
        reasoning = f"[fallback] nearest candidate ({chosen.distance_label}); gemini off: {e}"
        logger.info("zapros %s: gemini unavailable, using fallback: %s", zapros_id, e)

    suggested_at = datetime.utcnow()
    latency_ms = int((suggested_at - zapros.created_at).total_seconds() * 1000)

    taklif = AgentTakliflari(
        zapros_id=zapros.id,
        mashina_id=chosen.mashina.id,
        zapros_yaratilgan_vaqti=zapros.created_at,
        agent_taklif_bergan_vaqti=suggested_at,
        latency_ms=max(latency_ms, 0),
        score=score,
        reasoning=reasoning,
    )
    db.add(taklif)
    db.commit()
    db.refresh(taklif)
    logger.info(
        "zapros %s -> mashina %s (%s) latency=%dms",
        zapros.id, chosen.mashina.id, chosen.mashina.mashina_raqami, taklif.latency_ms,
    )
    return taklif
