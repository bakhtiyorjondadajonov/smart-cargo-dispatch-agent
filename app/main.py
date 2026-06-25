"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import analytics, malumotlar, takliflari, zaproslar
from app.scheduler import start_scheduler, stop_scheduler
from app.seed import seed_vehicles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_seed:
        n = seed_vehicles()
        if n:
            logger.info("seeded %d vehicles", n)
    if settings.enable_scheduler:
        start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="AI Cargo Matching System",
    description="Auto-generates transport requests and uses a Gemini agent to recommend vehicles.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(zaproslar.router)
app.include_router(malumotlar.router)
app.include_router(takliflari.router)
app.include_router(analytics.router)


@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "scheduler": settings.enable_scheduler,
        "gemini_configured": bool(settings.gemini_api_key),
        "location_mode": settings.location_mode,
    }
