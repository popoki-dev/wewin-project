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
    MEMBERS_EDIT = "members.edit"
    MEMBERS_DELETE = "members.delete"
    MEMBERS_TEAM = "members.team"
    MEMBERS_PROMOTE = "members.promote"
    MEMBERS_RESET_DEVICE = "members.reset_device"
    MEMBERS_ASSIGN_ROLES = "members.assign_roles"
    TEAMS_CREATE = "teams.create"
    TEAMS_RENAME = "teams.rename"
    # Projects and Revenue are enforced once those modules exist.
    PROJECTS_VIEW = "projects.view"
    PROJECTS_CREATE = "projects.create"
    PROJECTS_EDIT = "projects.edit"
    PROJECTS_DELETE = "projects.delete"
    PROJECTS_CHECK = "projects.check"
    REVENUE_VIEW = "revenue.view"
    REVENUE_EDIT = "revenue.edit"


# (group, [(permission, label, description)]) in display order.
CATALOG: list[tuple[str, list[tuple[Permission, str, str]]]] = [
    ("Members", [
        (Permission.MEMBERS_VIEW, "View members", "See the members of their team."),
        (Permission.MEMBERS_ADD, "Add members", "Add plain members to their team."),
        (Permission.MEMBERS_EDIT, "Edit members",
         "Change team members' name, email and active status, or set a new initial password."),
        (Permission.MEMBERS_DELETE, "Delete members", "Delete team members' accounts."),
        (Permission.MEMBERS_TEAM, "Move members in/out of team",
         "Bring members who have no team into their team, or take members out of it."),
        (Permission.MEMBERS_PROMOTE, "Make Team Leaders",
         "Make a plain member of their team a Team Leader of that same team."),
        (Permission.MEMBERS_RESET_DEVICE, "Reset devices", "Release a team member's computer binding."),
        (Permission.MEMBERS_ASSIGN_ROLES, "Assign role bundles",
         "Give or take role bundles from team members, limited to permissions they hold."),
    ]),
    ("Teams", [
        (Permission.TEAMS_CREATE, "Create teams", "Create new teams in the organization."),
        (Permission.TEAMS_RENAME, "Rename teams", "Rename any team in the organization."),
    ]),
    ("Projects", [
        (Permission.PROJECTS_VIEW, "View projects", "See projects (members: their own; leaders: their teams')."),
        (Permission.PROJECTS_CREATE, "Create projects", "Register new projects."),
        (Permission.PROJECTS_EDIT, "Edit projects", "Change projects and their payment history, unless locked by a check."),
        (Permission.PROJECTS_DELETE, "Delete projects", "Delete projects, unless locked by a check."),
        (Permission.PROJECTS_CHECK, "Check projects", "Mark their teams' projects as checked, locking them for members."),
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
        Permission.MEMBERS_EDIT,
        Permission.MEMBERS_DELETE,
        Permission.MEMBERS_TEAM,
        Permission.MEMBERS_PROMOTE,
        Permission.MEMBERS_RESET_DEVICE,
        Permission.MEMBERS_ASSIGN_ROLES,
        Permission.PROJECTS_VIEW,
        Permission.PROJECTS_CREATE,
        Permission.PROJECTS_EDIT,
        Permission.PROJECTS_DELETE,
        Permission.PROJECTS_CHECK,
        Permission.REVENUE_VIEW,
        Permission.REVENUE_EDIT,
    }),
    # Members manage their own projects.
    Role.MEMBER: frozenset({
        Permission.PROJECTS_VIEW,
        Permission.PROJECTS_CREATE,
        Permission.PROJECTS_EDIT,
        Permission.PROJECTS_DELETE,
    }),
}

# Any Members permission is useless without seeing the members it applies to.
_IMPLIED = {
    Permission.MEMBERS_ADD: Permission.MEMBERS_VIEW,
    Permission.MEMBERS_EDIT: Permission.MEMBERS_VIEW,
    Permission.MEMBERS_DELETE: Permission.MEMBERS_VIEW,
    Permission.MEMBERS_TEAM: Permission.MEMBERS_VIEW,
    Permission.MEMBERS_PROMOTE: Permission.MEMBERS_VIEW,
    Permission.MEMBERS_RESET_DEVICE: Permission.MEMBERS_VIEW,
    Permission.MEMBERS_ASSIGN_ROLES: Permission.MEMBERS_VIEW,
    Permission.PROJECTS_CREATE: Permission.PROJECTS_VIEW,
    Permission.PROJECTS_EDIT: Permission.PROJECTS_VIEW,
    Permission.PROJECTS_DELETE: Permission.PROJECTS_VIEW,
    Permission.PROJECTS_CHECK: Permission.PROJECTS_VIEW,
}


def parse_permissions(values: Iterable[str]) -> set[Permission]:
    """Convert stored or submitted strings, ignoring any that are no longer defined."""
    known = {p.value for p in Permission}
    return {Permission(v) for v in values if v in known}


def effective_permissions(role: Role, bundle_permissions: Iterable[str] = ()) -> set[Permission]:
    granted = set(ROLE_PERMISSIONS[role]) | parse_permissions(bundle_permissions)
    granted |= {_IMPLIED[p] for p in granted if p in _IMPLIED}
    return granted
