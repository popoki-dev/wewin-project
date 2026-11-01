from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from ..core.config import settings


def build_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        # SQLite is only used by the test-suite fallback.
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)


engine = build_engine(settings.database_url)
