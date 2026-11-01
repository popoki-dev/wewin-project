"""Password hashing (Argon2id), token creation and password policy."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from shared.api_contracts import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_CHARACTER_CLASSES,
    PASSWORD_MIN_LENGTH,
    RESET_CODE_LENGTH,
)

from .config import settings

JWT_ALGORITHM = "HS256"

# argon2-cffi defaults to Argon2id with RFC 9106 "low memory" parameters.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# Verified against when the account does not exist, so response time does not
# reveal whether an email is registered.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def keyed_hash(value: str) -> str:
    """HMAC with the server secret, for low-entropy values such as reset codes."""
    return hmac.new(settings.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def new_reset_code() -> str:
    return f"{secrets.randbelow(10**RESET_CODE_LENGTH):0{RESET_CODE_LENGTH}d}"


def create_access_token(user_id: int, organization_id: int, role: str) -> tuple[str, int]:
    """Return (token, lifetime_seconds)."""
    lifetime = timedelta(minutes=settings.access_token_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org": organization_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM), int(lifetime.total_seconds())


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def validate_password_strength(password: str) -> str | None:
    """Return a user-facing error message, or None if the password is acceptable."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Password must be at most {PASSWORD_MAX_LENGTH} characters long."
    classes = [
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ]
    if sum(classes) < PASSWORD_MIN_CHARACTER_CLASSES:
        return "Password must contain at least three of: lowercase, uppercase, digits, symbols."
    return None
