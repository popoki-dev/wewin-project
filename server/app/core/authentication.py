"""FastAPI dependencies that identify the caller."""

from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..models import User
from ..repositories.audit_repository import ClientInfo
from .security import decode_access_token


def get_client_info(request: Request, user_agent: str | None = Header(default=None)) -> ClientInfo:
    # Behind the reverse proxy, uvicorn's --proxy-headers sets request.client from X-Forwarded-For.
    return ClientInfo(ip_address=request.client.host if request.client else "", user_agent=user_agent or "")


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise unauthorized
    try:
        payload = decode_access_token(authorization[7:].strip())
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise unauthorized from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    # Tokens issued before the last password change are no longer valid.
    if int(payload.get("iat", 0)) < int(user.password_changed_at.timestamp()):
        raise unauthorized
    return user
