"""Automatic request generator + agent trigger (APScheduler).

The generator reschedules itself at a random 1-10 minute interval and emits a
small batch of requests per tick. Why a batch: a uniform 1-10 min interval
averages 5.5 min -> ~262 ticks/day, which is BELOW the spec's ">=400/day".
Emitting GENERATOR_BATCH_SIZE (default 2) per tick guarantees the minimum
(~262 * 2 = ~524/day) while keeping the 1-10 min cadence the spec asks for.

Each generated request is matched immediately by the agent pipeline, so the
created->suggested latency reflects real end-to-end processing time.
"""
from __future__ import annotations

import logging
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.agent.pipeline import run_matching
from app.config import settings
from app.database import SessionLocal
from app.geo import ALL_REGIONS, REGION_CENTERS
from app.models import Zaproslar

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_rng = random.Random()
_JOB_ID = "request_generator"


def _random_request_payload() -> dict:
    """Build a randomized request, named or GPS depending on configured mode."""
    pickup, dropoff = _rng.sample(ALL_REGIONS, 2)
    load_date = date.today() + timedelta(days=_rng.randint(0, 5))

    mode = settings.location_mode
    if mode == "mixed":
        mode = _rng.choice(["named", "gps"])

    if mode == "gps":
        base_lat, base_lng = REGION_CENTERS[pickup]
        return dict(
            yuk_ortish_joyi=pickup,
            yuk_tushirish_joyi=dropoff,
            yuklash_sanasi=load_date,
            ortish_lat=round(base_lat + _rng.uniform(-0.3, 0.3), 5),
            ortish_lng=round(base_lng + _rng.uniform(-0.3, 0.3), 5),
            location_type="gps",
        )
    return dict(
        yuk_ortish_joyi=pickup,
        yuk_tushirish_joyi=dropoff,
        yuklash_sanasi=load_date,
        location_type="named",
    )


def generate_and_match() -> None:
    """One scheduler tick: create a batch of requests and match each immediately."""
    db = SessionLocal()
    try:
        new_ids: list[int] = []
        for _ in range(max(1, settings.generator_batch_size)):
            zapros = Zaproslar(**_random_request_payload())
            db.add(zapros)
            db.flush()
            new_ids.append(zapros.id)
        db.commit()
    finally:
        db.close()

    # Match the batch concurrently: each match runs in its own DB session
    # (SQLAlchemy sessions are not thread-safe), so wall-clock for the batch is
    # ~one Gemini call rather than N sequential calls.
    workers = min(max(1, settings.match_concurrency), len(new_ids)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pool.map(match_one, new_ids)
    _reschedule()


def match_one(zapros_id: int) -> None:
    """Match a single request in its own session. Never raises (scheduler-safe)."""
    db = SessionLocal()
    try:
        run_matching(db, zapros_id)
    except Exception:
        logger.exception("matching failed for zapros %s", zapros_id)
    finally:
        db.close()


def _reschedule() -> None:
    """Schedule the next tick at a random interval in [min, max] minutes."""
    if _scheduler is None:
        return
    minutes = _rng.uniform(settings.generator_min_minutes, settings.generator_max_minutes)
    from datetime import datetime
    run_at = datetime.utcnow() + timedelta(minutes=minutes)
    _scheduler.add_job(
        generate_and_match,
        trigger="date",
        run_date=run_at,
        id=_JOB_ID,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("next request batch in %.1f min", minutes)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.start()
    # Fire the first batch shortly after startup, then self-reschedule.
    from datetime import datetime
    _scheduler.add_job(
        generate_and_match,
        trigger="date",
        run_date=datetime.utcnow() + timedelta(seconds=5),
        id=_JOB_ID,
        replace_existing=True,
    )
    logger.info("request generator started (batch=%d)", settings.generator_batch_size)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
