"""FastAPI dependencies that identify the caller."""

from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from shared import device_signature as ds

from ..database.session import get_db
from ..models import User
from ..repositories.audit_repository import ClientInfo
from ..services.device_service import DeviceService, DeviceSignature
from .security import decode_access_token, password_version

PASSWORD_CHANGE_REQUIRED = "Change your password to continue."


def get_client_info(request: Request, user_agent: str | None = Header(default=None)) -> ClientInfo:
    # Behind the reverse proxy, uvicorn's --proxy-headers sets request.client from X-Forwarded-For.
    return ClientInfo(ip_address=request.client.host if request.client else "", user_agent=user_agent or "")


def get_device_signature(request: Request) -> DeviceSignature | None:
    """The request's device signature headers, or None when any is missing or malformed."""
    headers = request.headers
    values = [headers.get(h, "") for h in (ds.DEVICE_HEADER, ds.TIMESTAMP_HEADER, ds.NONCE_HEADER, ds.SIGNATURE_HEADER)]
    device_id, timestamp, nonce, signature = values
    if not (
        ds.DEVICE_ID_RE.match(device_id)
        and ds.NONCE_RE.match(nonce)
        and ds.SIGNATURE_RE.match(signature)
        and 0 < len(timestamp) <= 40
    ):
        return None
    return DeviceSignature(device_id, timestamp, nonce, signature, request.method, request.url.path)


def get_signed_in_user(
    authorization: str | None = Header(default=None),
    signature: DeviceSignature | None = Depends(get_device_signature),
    db: Session = Depends(get_db),
) -> User:
    """The caller, authenticated by access token and device signature.

    Also returns accounts that still have to change their initial password; only
    the routes that let them do so should depend on this directly.
    """
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
    if payload.get("pwv") != password_version(user.password_changed_at):
        raise unauthorized

    DeviceService(db).verify(user, signature)
    db.commit()  # remember the nonce even when the route itself writes nothing
    return user


def get_current_user(user: User = Depends(get_signed_in_user)) -> User:
    """The caller, who must have replaced any initial password. Use this for every protected route."""
    if user.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, PASSWORD_CHANGE_REQUIRED)
    return user
