"""Aggregate monitoring: latency stats and matching throughput."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentTakliflari, Zaproslar
from app.schemas import AnalyticsOut

router = APIRouter(tags=["analytics"])


def _percentile(values: list[int], pct: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


@router.get("/analytics", response_model=AnalyticsOut)
def analytics(db: Session = Depends(get_db)):
    total_requests = db.scalar(select(func.count(Zaproslar.id))) or 0
    total_suggestions = db.scalar(select(func.count(AgentTakliflari.id))) or 0

    latencies = list(db.execute(select(AgentTakliflari.latency_ms)).scalars())
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    p95 = _percentile(latencies, 0.95)

    gemini = db.scalar(
        select(func.count(AgentTakliflari.id)).where(
            AgentTakliflari.reasoning.like("[gemini]%")
        )
    ) or 0
    fallback = total_suggestions - gemini

    since = datetime.utcnow() - timedelta(hours=24)
    req_24h = db.scalar(
        select(func.count(Zaproslar.id)).where(Zaproslar.created_at >= since)
    ) or 0
    sug_24h = db.scalar(
        select(func.count(AgentTakliflari.id)).where(
            AgentTakliflari.agent_taklif_bergan_vaqti >= since
        )
    ) or 0

    return AnalyticsOut(
        total_requests=total_requests,
        total_suggestions=total_suggestions,
        match_rate=(total_suggestions / total_requests) if total_requests else 0.0,
        avg_latency_ms=round(avg_latency, 1) if avg_latency is not None else None,
        p95_latency_ms=round(p95, 1) if p95 is not None else None,
        gemini_suggestions=gemini,
        fallback_suggestions=fallback,
        requests_last_24h=req_24h,
        suggestions_last_24h=sug_24h,
    )
