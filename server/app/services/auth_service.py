"""Authentication use cases: sign-in, session refresh/rotation, sign-out, password reset."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from shared.enums import AuditAction

from ..core.config import Settings
from ..core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    keyed_hash,
    new_refresh_token,
    new_reset_code,
    password_needs_rehash,
    sha256,
    validate_password_strength,
    verify_password,
)
from ..models import PasswordResetCode, RefreshSession, User
from ..repositories.audit_repository import AuditRepository, ClientInfo
from ..repositories.auth_repository import PasswordResetRepository, RefreshSessionRepository
from ..repositories.user_repository import UserRepository
from ..schemas.auth import TokenResponse, UserOut
from .device_service import DeviceService, DeviceSignature
from .errors import ServiceError

INVALID_CREDENTIALS = "Invalid email or password."
SESSION_EXPIRED = "Session expired. Please sign in again."
INVALID_RESET_CODE = "The reset code is invalid or has expired."


class AuthError(ServiceError):
    pass


@dataclass(frozen=True)
class PendingResetCode:
    """A reset code to deliver after the transaction commits."""

    email: str
    code: str
    minutes_valid: int


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.users = UserRepository(db)
        self.sessions = RefreshSessionRepository(db)
        self.reset_codes = PasswordResetRepository(db)
        self.audit = AuditRepository(db)
        self.devices = DeviceService(db)

    # ----------------------------------------------------------------- tokens
    def _issue_tokens(
        self, user: User, remember_me: bool, client: ClientInfo, device_secret: str | None = None
    ) -> TokenResponse:
        lifetime = (
            timedelta(days=self.settings.remember_me_days)
            if remember_me
            else timedelta(hours=self.settings.refresh_token_hours)
        )
        refresh_token = new_refresh_token()
        session = self.sessions.add(
            RefreshSession(
                user_id=user.id,
                token_hash=sha256(refresh_token),
                remember_me=remember_me,
                user_agent=client.user_agent[:255],
                ip_address=client.ip_address[:45],
                expires_at=_now() + lifetime,
            )
        )
        access_token, expires_in = create_access_token(
            user.id, user.organization_id, user.role.value, user.password_changed_at
        )
        return TokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=refresh_token,
            refresh_expires_at=session.expires_at,
            device_secret=device_secret,
            user=UserOut.model_validate(user),
        )

    # ---------------------------------------------------------------- sign in
    def login(self, email: str, password: str, remember_me: bool, device_id: str, client: ClientInfo) -> TokenResponse:
        user = self.users.get_by_email(email, for_update=True)
        if user is None:
            burn_password_check(password)
            self.audit.record(AuditAction.LOGIN_FAILED, client, email=email, reason="unknown_email")
            self.db.commit()
            raise AuthError(401, INVALID_CREDENTIALS)

        now = _now()
        if user.locked_until and user.locked_until > now:
            minutes = int((user.locked_until - now).total_seconds() // 60) + 1
            raise AuthError(429, f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.")

        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1
            self.audit.record(
                AuditAction.LOGIN_FAILED, client, user_id=user.id, organization_id=user.organization_id,
                reason="wrong_password",
            )
            if user.failed_login_count >= self.settings.max_failed_logins:
                user.failed_login_count = 0
                user.locked_until = now + timedelta(minutes=self.settings.lockout_minutes)
                self.audit.record(AuditAction.ACCOUNT_LOCKED, client, user_id=user.id, organization_id=user.organization_id)
            self.db.commit()
            raise AuthError(401, INVALID_CREDENTIALS)

        if not user.is_active:
            raise AuthError(403, "This account has been disabled.")

        device_secret = self.devices.bind_at_sign_in(user, device_id, client)

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        tokens = self._issue_tokens(user, remember_me, client, device_secret)
        self.audit.record(
            AuditAction.LOGIN_SUCCEEDED, client, user_id=user.id, organization_id=user.organization_id,
            remember_me=remember_me,
        )
        self.db.commit()
        return tokens

    def refresh(self, refresh_token: str, signature: DeviceSignature | None, client: ClientInfo) -> TokenResponse:
        session = self.sessions.get_by_token_hash(sha256(refresh_token), for_update=True)
        if session is None:
            raise AuthError(401, SESSION_EXPIRED)
        if session.revoked_at is not None:
            # A rotated-out token was replayed: assume it leaked and end every session.
            self.sessions.revoke_all_for_user(session.user_id, _now())
            self.audit.record(AuditAction.SESSION_REUSE_DETECTED, client, user_id=session.user_id)
            self.db.commit()
            raise AuthError(401, SESSION_EXPIRED)
        if session.expires_at <= _now() or not session.user.is_active:
            raise AuthError(401, SESSION_EXPIRED)
        self.devices.verify(session.user, signature)

        session.revoked_at = _now()
        tokens = self._issue_tokens(session.user, session.remember_me, client)
        self.db.commit()
        return tokens

    def logout(self, refresh_token: str | None, client: ClientInfo) -> None:
        if not refresh_token:
            return
        session = self.sessions.get_by_token_hash(sha256(refresh_token))
        if session is not None and session.revoked_at is None:
            session.revoked_at = _now()
            self.audit.record(AuditAction.LOGOUT, client, user_id=session.user_id)
            self.db.commit()

    def change_password(
        self, user: User, current_password: str, new_password: str, remember_me: bool, client: ClientInfo
    ) -> TokenResponse:
        """Change the password (required after an initial one). Ends every other session."""
        if not verify_password(current_password, user.password_hash):
            raise AuthError(400, "Your current password is incorrect.")
        if (problem := validate_password_strength(new_password)) is not None:
            raise AuthError(422, problem)
        if new_password == current_password:
            raise AuthError(422, "Choose a password different from your current one.")

        now = _now()
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        user.must_change_password = False
        self.sessions.revoke_all_for_user(user.id, now)
        tokens = self._issue_tokens(user, remember_me, client)
        self.audit.record(AuditAction.PASSWORD_CHANGED, client, user_id=user.id, organization_id=user.organization_id)
        self.db.commit()
        return tokens

    # ---------------------------------------------------------- password reset
    def request_password_reset(self, email: str, client: ClientInfo) -> PendingResetCode | None:
        """Create a reset code. Returns None (silently) when nothing should be sent."""
        user = self.users.get_by_email(email)
        if user is None or not user.is_active:
            return None

        now = _now()
        latest = self.reset_codes.latest_unused(user.id)
        if latest and (now - latest.created_at).total_seconds() < self.settings.reset_code_resend_seconds:
            return None

        self.reset_codes.invalidate_all(user.id, now)
        code = new_reset_code()
        self.reset_codes.add(
            PasswordResetCode(
                user_id=user.id,
                code_hash=keyed_hash(f"{user.id}:{code}"),
                expires_at=now + timedelta(minutes=self.settings.reset_code_minutes),
            )
        )
        self.audit.record(AuditAction.PASSWORD_RESET_REQUESTED, client, user_id=user.id, organization_id=user.organization_id)
        self.db.commit()
        return PendingResetCode(user.email, code, self.settings.reset_code_minutes)

    def reset_password(self, email: str, code: str, new_password: str, client: ClientInfo) -> None:
        if (problem := validate_password_strength(new_password)) is not None:
            raise AuthError(422, problem)

        user = self.users.get_by_email(email)
        if user is None or not user.is_active:
            raise AuthError(400, INVALID_RESET_CODE)

        now = _now()
        entry = self.reset_codes.latest_unused(user.id, for_update=True)
        if entry is None or entry.expires_at <= now or entry.attempts >= self.settings.reset_code_max_attempts:
            raise AuthError(400, INVALID_RESET_CODE)

        if not hmac.compare_digest(entry.code_hash, keyed_hash(f"{user.id}:{code}")):
            entry.attempts += 1
            if entry.attempts >= self.settings.reset_code_max_attempts:
                entry.used_at = now
            self.db.commit()
            raise AuthError(400, INVALID_RESET_CODE)

        entry.used_at = now
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        user.must_change_password = False  # the user chose this password themselves
        user.failed_login_count = 0
        user.locked_until = None
        self.sessions.revoke_all_for_user(user.id, now)
        self.audit.record(AuditAction.PASSWORD_RESET_COMPLETED, client, user_id=user.id, organization_id=user.organization_id)
        self.db.commit()
