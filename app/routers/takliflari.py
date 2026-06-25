"""Agent suggestion log + manual re-run endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.pipeline import run_matching
from app.database import get_db
from app.models import AgentTakliflari, Zaproslar
from app.schemas import SuggestionOut

router = APIRouter(tags=["suggestions"])


@router.get("/suggestions", response_model=list[SuggestionOut])
def list_suggestions(limit: int = Query(50, le=500), db: Session = Depends(get_db)):
    rows = db.execute(
        select(AgentTakliflari).order_by(AgentTakliflari.id.desc()).limit(limit)
    ).scalars().all()
    return rows


@router.post("/agent/run/{request_id}", response_model=SuggestionOut)
def run_agent(request_id: int, db: Session = Depends(get_db)):
    if db.get(Zaproslar, request_id) is None:
        raise HTTPException(status_code=404, detail="request not found")
    taklif = run_matching(db, request_id)
    if taklif is None:
        raise HTTPException(status_code=422, detail="no candidate vehicle could be matched")
    return taklif
