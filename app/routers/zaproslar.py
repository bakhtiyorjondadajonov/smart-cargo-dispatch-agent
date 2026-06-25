"""Cargo request endpoints. Creating a request triggers the agent in the background."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.agent.pipeline import run_matching
from app.models import Zaproslar
from app.schemas import RequestCreate, RequestOut

router = APIRouter(tags=["requests"])


def create_request(db: Session, payload: RequestCreate) -> Zaproslar:
    zapros = Zaproslar(
        yuk_ortish_joyi=payload.pickup_location,
        yuk_tushirish_joyi=payload.dropoff_location,
        yuklash_sanasi=payload.load_date,
        ortish_lat=payload.pickup_lat,
        ortish_lng=payload.pickup_lng,
        location_type=payload.location_type,
    )
    db.add(zapros)
    db.commit()
    db.refresh(zapros)
    return zapros


def match_in_background(zapros_id: int) -> None:
    """Run the agent in its own session (background tasks must not reuse the request session)."""
    db = SessionLocal()
    try:
        run_matching(db, zapros_id)
    finally:
        db.close()


@router.post("/requests", response_model=RequestOut, status_code=201)
def post_request(
    payload: RequestCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    zapros = create_request(db, payload)
    background.add_task(match_in_background, zapros.id)
    return zapros


@router.get("/requests", response_model=list[RequestOut])
def list_requests(
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Zaproslar).order_by(Zaproslar.id.desc()).limit(limit)
    ).scalars().all()
    return rows
