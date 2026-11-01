"""Enumerations shared by the server and the desktop client (stdlib only)."""

from __future__ import annotations

import enum


class Role(str, enum.Enum):
    """Organization-wide role. Higher roles include every permission of lower ones."""

    OWNER = "owner"
    TEAM_LEADER = "team_leader"
    MEMBER = "member"

    @property
    def rank(self) -> int:
        return _ROLE_RANK[self]

    def at_least(self, other: Role) -> bool:
        return self.rank >= other.rank


_ROLE_RANK = {Role.MEMBER: 0, Role.TEAM_LEADER: 1, Role.OWNER: 2}


class AuditAction(str, enum.Enum):
    LOGIN_SUCCEEDED = "auth.login_succeeded"
    LOGIN_FAILED = "auth.login_failed"
    ACCOUNT_LOCKED = "auth.account_locked"
    LOGOUT = "auth.logout"
    SESSION_REUSE_DETECTED = "auth.session_reuse_detected"
    PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"
    PASSWORD_RESET_COMPLETED = "auth.password_reset_completed"
    PASSWORD_CHANGED = "auth.password_changed"
    DEVICE_REGISTERED = "device.registered"
    DEVICE_REJECTED = "device.rejected"
    DEVICE_RESET = "device.reset"
    USER_CREATED = "user.created"
    USER_ROLES_CHANGED = "user.roles_changed"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    TEAM_CREATED = "team.created"
    TEAM_RENAMED = "team.renamed"
    ROLE_BUNDLE_CREATED = "role_bundle.created"
    ROLE_BUNDLE_UPDATED = "role_bundle.updated"
    ROLE_BUNDLE_DELETED = "role_bundle.deleted"
