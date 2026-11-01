"""Enumerations shared by the server and the desktop client (stdlib only)."""

from __future__ import annotations

import enum


class Role(str, enum.Enum):
    """Organization-wide role. Higher roles include every permission of lower ones."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

    @property
    def rank(self) -> int:
        return _ROLE_RANK[self]

    def at_least(self, other: Role) -> bool:
        return self.rank >= other.rank


_ROLE_RANK = {Role.MEMBER: 0, Role.ADMIN: 1, Role.OWNER: 2}


class AuditAction(str, enum.Enum):
    LOGIN_SUCCEEDED = "auth.login_succeeded"
    LOGIN_FAILED = "auth.login_failed"
    ACCOUNT_LOCKED = "auth.account_locked"
    LOGOUT = "auth.logout"
    SESSION_REUSE_DETECTED = "auth.session_reuse_detected"
    PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"
    PASSWORD_RESET_COMPLETED = "auth.password_reset_completed"
    USER_CREATED = "user.created"
