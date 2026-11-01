"""Device binding: the first sign-in binds an account to its PC, and every later
request must carry a signature made with that PC's device secret."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared import device_signature as ds
from shared.enums import AuditAction

from ..core.security import derive_device_secret, new_device_nonce
from ..models import Device, User
from ..repositories.audit_repository import AuditRepository, ClientInfo
from ..repositories.auth_repository import RefreshSessionRepository
from ..repositories.device_repository import DeviceRepository
from .errors import ServiceError

DEVICE_MISMATCH = (
    "This account is registered to another computer. "
    "Ask your Owner or Team Leader to reset the device registration."
)
DEVICE_VERIFICATION_FAILED = "Device verification failed. Please sign in again."


@dataclass(frozen=True)
class DeviceSignature:
    """The signature headers of one request, plus what was signed."""

    device_id: str
    timestamp: str
    nonce: str
    signature: str
    method: str
    path: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.devices = DeviceRepository(db)
        self.audit = AuditRepository(db)

    def bind_at_sign_in(self, user: User, device_id: str, client: ClientInfo) -> str:
        """Bind the account to this PC on first sign-in and return a fresh device secret.

        Raises ServiceError(403) when the account is bound to a different PC. The
        caller has already checked the password, so this reveals nothing to a guesser.
        """
        device = self.devices.get_for_user(user.id)
        if device is None:
            device = self.devices.add(Device(user_id=user.id, device_id=device_id, secret_nonce=new_device_nonce()))
            self.audit.record(AuditAction.DEVICE_REGISTERED, client, user_id=user.id, organization_id=user.organization_id)
        elif not hmac.compare_digest(device.device_id, device_id):
            self.audit.record(AuditAction.DEVICE_REJECTED, client, user_id=user.id, organization_id=user.organization_id)
            self.db.commit()
            raise ServiceError(403, DEVICE_MISMATCH)
        else:
            # Each sign-in issues a new secret, which retires the previous one.
            device.secret_nonce = new_device_nonce()
        device.last_seen_at = _now()
        return derive_device_secret(user.id, device.device_id, device.secret_nonce)

    def verify(self, user: User, signature: DeviceSignature | None) -> None:
        """Check a request's device signature. Adds its nonce to the session; the caller commits."""
        failed = ServiceError(401, DEVICE_VERIFICATION_FAILED)
        if signature is None:
            raise failed
        device = self.devices.get_for_user(user.id)
        if device is None or not hmac.compare_digest(device.device_id, signature.device_id):
            raise failed

        try:
            sent_at = ds.parse_timestamp(signature.timestamp)
        except ValueError:
            raise failed from None
        now = _now()
        window = timedelta(seconds=ds.MAX_CLOCK_SKEW_SECONDS)
        if abs(now - sent_at) > window:
            raise ServiceError(401, "Your computer's clock is wrong. Correct the date and time, then try again.")

        secret = derive_device_secret(user.id, device.device_id, device.secret_nonce)
        expected = ds.sign(
            secret, device.device_id, user.email, signature.timestamp, signature.nonce, signature.method, signature.path
        )
        if not hmac.compare_digest(expected, signature.signature):
            raise failed

        # A nonce is remembered for twice the clock window, which covers every
        # timestamp the check above can still accept.
        if self.devices.nonce_seen(device.id, signature.nonce):
            raise failed
        self.devices.forget_nonces_before(device.id, now - 2 * window)
        try:
            self.devices.add_nonce(device.id, signature.nonce)
        except IntegrityError:  # the same request arrived twice at once
            self.db.rollback()
            raise failed from None
        device.last_seen_at = now

    def reset(self, user: User, actor: User | None, client: ClientInfo) -> bool:
        """Unbind the account's PC and end its sessions. The next sign-in binds whichever PC it is made from."""
        removed = self.devices.delete_for_user(user.id)
        RefreshSessionRepository(self.db).revoke_all_for_user(user.id, _now())
        self.audit.record(
            AuditAction.DEVICE_RESET, client, user_id=actor.id if actor else None,
            organization_id=user.organization_id, target_user_id=user.id, via="api" if actor else "cli",
        )
        return removed
