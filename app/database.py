"""SQLAlchemy engine, session factory and declarative base.

Synchronous SQLAlchemy 2.0 is used deliberately: it composes cleanly with
APScheduler's BackgroundScheduler and the synchronous google-genai client,
and FastAPI runs sync routes in a threadpool. Candidate ranking happens in
Python (not SQL), so the same code works on Postgres and SQLite.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# SQLite needs check_same_thread=False because the scheduler runs in another thread.
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
