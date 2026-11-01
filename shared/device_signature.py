"""Device-bound request signatures, shared by server and client (stdlib only).

Every authenticated request carries the device identifier, a UTC timestamp, a
random nonce and an HMAC-SHA256 signature over those values, the user's email
and the request method and path. The HMAC key is the device secret the server
issues at sign-in; the MAC-derived device identifier alone is guessable, so it
is never used as a key.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone

DEVICE_HEADER = "X-WeWin-Device"
TIMESTAMP_HEADER = "X-WeWin-Timestamp"
NONCE_HEADER = "X-WeWin-Nonce"
SIGNATURE_HEADER = "X-WeWin-Signature"

# Requests whose timestamp is further than this from the server clock are refused.
MAX_CLOCK_SKEW_SECONDS = 300

DEVICE_ID_RE = re.compile(r"^[0-9a-f]{64}$")
NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
SIGNATURE_RE = re.compile(r"^[0-9a-f]{64}$")


def device_id_from_mac(mac: str) -> str:
    """The device identifier: a SHA-256 hash of the PC's MAC address."""
    return hashlib.sha256(f"WeWin-device:{mac.strip().upper()}".encode()).hexdigest()


def utc_timestamp(now: datetime | None = None) -> str:
    """ISO 8601 UTC with milliseconds, e.g. 2026-11-02T09:30:00.123Z."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    """Inverse of utc_timestamp. Raises ValueError for anything else."""
    if not value.endswith("Z"):
        raise ValueError("timestamp must be UTC")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def sign(secret: str, device_id: str, email: str, timestamp: str, nonce: str, method: str, path: str) -> str:
    message = "\n".join([device_id, email.lower(), timestamp, nonce, method.upper(), path])
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def signed_headers(secret: str, device_id: str, email: str, method: str, path: str) -> dict[str, str]:
    timestamp = utc_timestamp()
    nonce = secrets.token_urlsafe(18)
    return {
        DEVICE_HEADER: device_id,
        TIMESTAMP_HEADER: timestamp,
        NONCE_HEADER: nonce,
        SIGNATURE_HEADER: sign(secret, device_id, email, timestamp, nonce, method, path),
    }
