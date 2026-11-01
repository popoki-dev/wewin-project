"""Role-based access control. See docs/permissions.md for the permission matrix."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from shared.enums import Role
from shared.permissions import Permission

from ..models import User
from .authentication import get_current_user


def require_role(minimum: Role) -> Callable[..., User]:
    """Dependency factory: the caller must hold `minimum` or a higher role.

    Usage: ``def route(user: User = Depends(require_role(Role.TEAM_LEADER)))``
    """

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not user.role.at_least(minimum):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to do this.")
        return user

    return dependency


def require_permission(permission: Permission) -> Callable[..., User]:
    """Dependency factory: the caller's role or role bundles must grant `permission`.

    Usage: ``def route(user: User = Depends(require_permission(Permission.MEMBERS_ADD)))``
    """

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not user.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to do this.")
        return user

    return dependency


def ensure_same_organization(user: User, organization_id: int) -> None:
    """Guard for resources that belong to an organization."""
    if user.organization_id != organization_id:
        # 404 rather than 403, so other organizations' IDs are not confirmed.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
