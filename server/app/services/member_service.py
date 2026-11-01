"""Teams and members.

The Owner acts on the whole organization. Anyone else acts through permissions
(their base role's, plus their role bundles'), limited to plain members of their
own team, and can only hand out or take away role bundles whose permissions they
hold themselves, so nobody can grant more than they have.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from shared.enums import AuditAction, Role
from shared.permissions import Permission, parse_permissions

from ..core.security import hash_password, validate_password_strength
from ..models import RoleBundle, Team, User
from ..repositories.audit_repository import AuditRepository, ClientInfo
from ..repositories.device_repository import DeviceRepository
from ..repositories.role_bundle_repository import RoleBundleRepository
from ..repositories.team_repository import TeamRepository
from ..repositories.user_repository import UserRepository
from ..schemas.members import BundleRef, MemberCreate, MemberOut, MemberRolesUpdate, TeamOut
from .device_service import DeviceService
from .errors import ServiceError
from .role_bundle_service import BUNDLE_NOT_FOUND

OWN_TEAM_ONLY = "You can only manage plain members of your own team."
NO_PERMISSION = "You do not have permission to do this."


class MemberService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.teams = TeamRepository(db)
        self.devices = DeviceRepository(db)
        self.bundles = RoleBundleRepository(db)
        self.audit = AuditRepository(db)

    # ----------------------------------------------------------------- scope
    @staticmethod
    def _own_team(actor: User) -> int:
        if actor.team_id is None:
            raise ServiceError(403, "You are not assigned to a team.")
        return actor.team_id

    def _ensure_manageable(self, actor: User, target: User) -> None:
        """Non-owners manage only plain members of their own team, never themselves."""
        if actor.role == Role.OWNER:
            return
        if target.id == actor.id or target.role != Role.MEMBER or target.team_id != self._own_team(actor):
            raise ServiceError(403, OWN_TEAM_ONLY)

    def _get_member(self, actor: User, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None or user.organization_id != actor.organization_id:
            raise ServiceError(404, "Member not found.")
        return user

    # ------------------------------------------------------------------ teams
    def list_teams(self, actor: User) -> list[TeamOut]:
        org_wide = actor.role == Role.OWNER or actor.can(Permission.TEAMS_CREATE) or actor.can(Permission.TEAMS_RENAME)
        if org_wide:
            teams = self.teams.list(actor.organization_id)
        elif actor.team_id is not None:
            teams = self.teams.list(actor.organization_id, actor.team_id)
        else:
            teams = []
        counts = self.teams.member_counts([t.id for t in teams])
        return [TeamOut(id=t.id, name=t.name, member_count=counts.get(t.id, 0)) for t in teams]

    def create_team(self, actor: User, name: str, client: ClientInfo) -> TeamOut:
        if self.teams.get_by_name(actor.organization_id, name) is not None:
            raise ServiceError(409, f"A team named “{name}” already exists.")
        team = self.teams.add(Team(organization_id=actor.organization_id, name=name))
        self.audit.record(
            AuditAction.TEAM_CREATED, client, user_id=actor.id, organization_id=actor.organization_id,
            team_id=team.id, name=name,
        )
        self.db.commit()
        return TeamOut(id=team.id, name=team.name)

    def rename_team(self, actor: User, team_id: int, name: str, client: ClientInfo) -> TeamOut:
        team = self.teams.get(team_id)
        if team is None or team.organization_id != actor.organization_id:
            raise ServiceError(404, "Team not found.")
        existing = self.teams.get_by_name(actor.organization_id, name)
        if existing is not None and existing.id != team.id:
            raise ServiceError(409, f"A team named “{name}” already exists.")
        old = team.name
        team.name = name
        self.audit.record(
            AuditAction.TEAM_RENAMED, client, user_id=actor.id, organization_id=actor.organization_id,
            team_id=team.id, old_name=old, name=name,
        )
        self.db.commit()
        return TeamOut(id=team.id, name=team.name, member_count=self.teams.member_counts([team.id]).get(team.id, 0))

    # ---------------------------------------------------------------- bundles
    def _resolve_bundles(self, actor: User, bundle_ids: list[int]) -> list[RoleBundle]:
        ids = list(dict.fromkeys(bundle_ids))
        bundles = self.bundles.get_many(actor.organization_id, ids)
        if len(bundles) != len(ids):
            raise ServiceError(404, BUNDLE_NOT_FOUND)
        return bundles

    @staticmethod
    def _ensure_can_hand_out(actor: User, changed: list[RoleBundle]) -> None:
        """Adding or removing a bundle needs `members.assign_roles` and every permission in it."""
        if not changed or actor.role == Role.OWNER:
            return
        if not actor.can(Permission.MEMBERS_ASSIGN_ROLES):
            raise ServiceError(403, NO_PERMISSION)
        held = actor.permissions
        for bundle in changed:
            if not parse_permissions(bundle.permissions) <= held:
                raise ServiceError(403, f"“{bundle.name}” includes permissions you do not have.")

    # ---------------------------------------------------------------- members
    def list_members(self, actor: User) -> list[MemberOut]:
        team_id = None if actor.role == Role.OWNER else self._own_team(actor)
        users = self.users.list(actor.organization_id, team_id)
        bound = self.devices.bound_user_ids([u.id for u in users])
        return [self._out(u, u.id in bound) for u in users]

    def add_member(self, actor: User, body: MemberCreate, client: ClientInfo) -> MemberOut:
        team = self.teams.get(body.team_id)
        if team is None or team.organization_id != actor.organization_id:
            raise ServiceError(404, "Select a team.")
        if actor.role != Role.OWNER:
            if team.id != self._own_team(actor):
                raise ServiceError(403, OWN_TEAM_ONLY)
            if body.role != Role.MEMBER.value:
                raise ServiceError(403, "Only the Owner can add Team Leaders.")
        bundles = self._resolve_bundles(actor, body.role_bundle_ids)
        self._ensure_can_hand_out(actor, bundles)
        if (problem := validate_password_strength(body.initial_password)) is not None:
            raise ServiceError(422, f"Initial password: {problem}")
        if self.users.get_by_email(body.email) is not None:
            raise ServiceError(409, "An account with this email already exists.")

        user = self.users.add(
            User(
                organization_id=actor.organization_id,
                team_id=team.id,
                email=body.email,
                full_name=body.full_name.strip(),
                role=Role(body.role),
                password_hash=hash_password(body.initial_password),
                must_change_password=True,
                role_bundles=bundles,
            )
        )
        self.audit.record(
            AuditAction.USER_CREATED, client, user_id=actor.id, organization_id=actor.organization_id,
            created_user_id=user.id, team_id=team.id, role=body.role, role_bundles=[b.name for b in bundles],
        )
        self.db.commit()
        return self._out(user, device_registered=False)

    def update_roles(self, actor: User, user_id: int, body: MemberRolesUpdate, client: ClientInfo) -> MemberOut:
        """Change a member's base role (Owner only) and/or their set of role bundles."""
        user = self._get_member(actor, user_id)
        if user.role == Role.OWNER:
            raise ServiceError(403, "The Owner already has every permission.")
        if body.role is not None and body.role != user.role.value and actor.role != Role.OWNER:
            raise ServiceError(403, "Only the Owner can change a member's base role.")

        changes: dict = {}
        if body.role_bundle_ids is not None:
            self._ensure_manageable(actor, user)
            wanted = self._resolve_bundles(actor, body.role_bundle_ids)
            current = {b.id: b for b in user.role_bundles}
            wanted_ids = {b.id for b in wanted}
            added = [b for b in wanted if b.id not in current]
            removed = [b for b in current.values() if b.id not in wanted_ids]
            self._ensure_can_hand_out(actor, added + removed)
            if added or removed:
                user.role_bundles = sorted(wanted, key=lambda b: b.name)
                changes["added_bundles"] = [b.name for b in added]
                changes["removed_bundles"] = [b.name for b in removed]
        if body.role is not None and body.role != user.role.value:
            changes["role"] = {"from": user.role.value, "to": body.role}
            user.role = Role(body.role)

        if changes:
            self.audit.record(
                AuditAction.USER_ROLES_CHANGED, client, user_id=actor.id, organization_id=actor.organization_id,
                target_user_id=user.id, **changes,
            )
            self.db.commit()
        return self._out(user, self.devices.get_for_user(user.id) is not None)

    def reset_device(self, actor: User, user_id: int, client: ClientInfo) -> MemberOut:
        user = self._get_member(actor, user_id)
        self._ensure_manageable(actor, user)
        DeviceService(self.db).reset(user, actor, client)
        self.db.commit()
        return self._out(user, device_registered=False)

    @staticmethod
    def _out(user: User, device_registered: bool) -> MemberOut:
        return MemberOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            team_id=user.team_id,
            team_name=user.team.name if user.team else None,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            device_registered=device_registered,
            last_login_at=user.last_login_at,
            role_bundles=[BundleRef(id=b.id, name=b.name) for b in user.role_bundles],
            permissions=sorted(p.value for p in user.permissions),
        )
