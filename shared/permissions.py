"""Permission catalog, shared by server and client (stdlib only).

A user's effective permissions are their base role's permissions plus those of
every role bundle assigned to them. See docs/permissions.md.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable

from .enums import Role


class Permission(str, enum.Enum):
    MEMBERS_VIEW = "members.view"
    MEMBERS_ADD = "members.add"
    MEMBERS_RESET_DEVICE = "members.reset_device"
    MEMBERS_ASSIGN_ROLES = "members.assign_roles"
    TEAMS_CREATE = "teams.create"
    TEAMS_RENAME = "teams.rename"
    # Projects and Revenue are enforced once those modules exist.
    PROJECTS_VIEW = "projects.view"
    PROJECTS_CREATE = "projects.create"
    PROJECTS_EDIT = "projects.edit"
    REVENUE_VIEW = "revenue.view"
    REVENUE_EDIT = "revenue.edit"


# (group, [(permission, label, description)]) in display order.
CATALOG: list[tuple[str, list[tuple[Permission, str, str]]]] = [
    ("Members", [
        (Permission.MEMBERS_VIEW, "View members", "See the members of their team."),
        (Permission.MEMBERS_ADD, "Add members", "Add plain members to their team."),
        (Permission.MEMBERS_RESET_DEVICE, "Reset devices", "Release a team member's computer binding."),
        (Permission.MEMBERS_ASSIGN_ROLES, "Assign role bundles",
         "Give or take role bundles from team members, limited to permissions they hold."),
    ]),
    ("Teams", [
        (Permission.TEAMS_CREATE, "Create teams", "Create new teams in the organization."),
        (Permission.TEAMS_RENAME, "Rename teams", "Rename any team in the organization."),
    ]),
    ("Projects", [
        (Permission.PROJECTS_VIEW, "View projects", "See projects."),
        (Permission.PROJECTS_CREATE, "Create projects", "Start new projects."),
        (Permission.PROJECTS_EDIT, "Edit projects", "Change existing projects."),
    ]),
    ("Revenue", [
        (Permission.REVENUE_VIEW, "View revenue", "See revenue figures."),
        (Permission.REVENUE_EDIT, "Edit revenue", "Enter and correct revenue."),
    ]),
]

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.TEAM_LEADER: frozenset({
        Permission.MEMBERS_VIEW,
        Permission.MEMBERS_ADD,
        Permission.MEMBERS_RESET_DEVICE,
        Permission.MEMBERS_ASSIGN_ROLES,
        Permission.PROJECTS_VIEW,
        Permission.PROJECTS_CREATE,
        Permission.PROJECTS_EDIT,
        Permission.REVENUE_VIEW,
        Permission.REVENUE_EDIT,
    }),
    Role.MEMBER: frozenset({Permission.PROJECTS_VIEW}),
}

# Any Members permission is useless without seeing the members it applies to.
_IMPLIED = {
    Permission.MEMBERS_ADD: Permission.MEMBERS_VIEW,
    Permission.MEMBERS_RESET_DEVICE: Permission.MEMBERS_VIEW,
    Permission.MEMBERS_ASSIGN_ROLES: Permission.MEMBERS_VIEW,
}


def parse_permissions(values: Iterable[str]) -> set[Permission]:
    """Convert stored or submitted strings, ignoring any that are no longer defined."""
    known = {p.value for p in Permission}
    return {Permission(v) for v in values if v in known}


def effective_permissions(role: Role, bundle_permissions: Iterable[str] = ()) -> set[Permission]:
    granted = set(ROLE_PERMISSIONS[role]) | parse_permissions(bundle_permissions)
    granted |= {_IMPLIED[p] for p in granted if p in _IMPLIED}
    return granted
