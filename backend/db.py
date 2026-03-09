"""
Database configuration for Driver Pulse.

This module defines the SQLAlchemy engine, session factory, and declarative base.
Individual models live under `backend/models/` and import `Base` from here.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# Default to a local SQLite file for demos. Can be overridden via DATABASE_URL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./driver_pulse.db")

# Some providers still give `postgres://`, but SQLAlchemy expects `postgresql://`.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """
    Create all tables for registered models.

    Safe to call multiple times (uses CREATE IF NOT EXISTS under the hood).
    """
    # Import models so they are registered with SQLAlchemy's metadata
    # before Base.metadata.create_all() runs.
    from models import driver_goal, earnings_velocity  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency that yields a database session.

    Example:
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

