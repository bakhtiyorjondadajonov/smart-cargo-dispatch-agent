"""Vehicle endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Malumotlar
from app.schemas import VehicleCreate, VehicleOut

router = APIRouter(tags=["vehicles"])


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
def post_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    vehicle = Malumotlar(
        mashina_raqami=payload.plate_number,
        joriy_lokatsiya=payload.location,
        lat=payload.lat,
        lng=payload.lng,
        location_type=payload.location_type,
    )
    db.add(vehicle)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="plate_number already exists")
    db.refresh(vehicle)
    return vehicle


@router.get("/vehicles", response_model=list[VehicleOut])
def list_vehicles(limit: int = Query(100, le=1000), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Malumotlar).order_by(Malumotlar.id).limit(limit)
    ).scalars().all()
    return rows
