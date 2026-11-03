from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.api_contracts import API_PREFIX, APP_ID

from ... import __version__
from ..database.session import get_db
from ..schemas.common import HealthResponse
from .routes import auth, members, projects

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(auth.router)
api_router.include_router(members.router)
api_router.include_router(projects.router)


@api_router.get("/health", response_model=HealthResponse, tags=["meta"])
def health(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - report, don't fail the probe handler
        database = "unavailable"
    return HealthResponse(status="ok", app=APP_ID, version=__version__, database=database)
