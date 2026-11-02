"""Teams and members.

The Owner acts on the whole organization. Anyone else acts through permissions
(their base role's, plus their role bundles'), limited to plain members of the teams
in their scope: the teams a Team Leader leads, or a member's own team. They can only
hand out or take away role bundles whose permissions they hold themselves, so nobody
can grant more than they have.

Team membership: a plain member belongs to at most one team (users.team_id). A Team
Leader leads one or more teams (team_leaders) and has no team_id. The Owner has neither.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from shared.enums import AuditAction, Role
from shared.permissions import Permission, parse_permissions

from ..core.security import hash_password, validate_password_strength
from ..models import RoleBundle, Team, User
from ..repositories.audit_repository import AuditRepository, ClientInfo
from ..repositories.auth_repository import RefreshSessionRepository
from ..repositories.device_repository import DeviceRepository
from ..repositories.role_bundle_repository import RoleBundleRepository
from ..repositories.team_repository import TeamRepository
from ..repositories.user_repository import UserRepository
from ..schemas.members import BundleRef, MemberCreate, MemberOut, MemberUpdate, PersonRef, TeamOut, TeamRef
from .device_service import DeviceService
from .errors import ServiceError
from .role_bundle_service import BUNDLE_NOT_FOUND

OWN_TEAM_ONLY = "You can only manage plain members of your own teams."
LEADER_NEEDS_TEAM = "A Team Leader must lead at least one team."
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
    def _scope(actor: User) -> set[int]:
        """The teams a non-owner acts on: those a Team Leader leads, or a member's own team."""
        if actor.role == Role.TEAM_LEADER:
            return set(actor.led_team_ids)
        return {actor.team_id} if actor.team_id is not None else set()

    def _require_scope(self, actor: User) -> set[int]:
        scope = self._scope(actor)
        if not scope:
            raise ServiceError(403, "You are not assigned to a team.")
        return scope

    def _ensure_manageable(self, actor: User, target: User) -> None:
        """Non-owners manage only plain members of their teams, never themselves."""
        if actor.role == Role.OWNER:
            return
        scope = self._require_scope(actor)
        if target.id == actor.id or target.role != Role.MEMBER or target.team_id not in scope:
            raise ServiceError(403, OWN_TEAM_ONLY)

    def _get_member(self, actor: User, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None or user.organization_id != actor.organization_id:
            raise ServiceError(404, "Member not found.")
        return user

    def _get_team(self, actor: User, team_id: int, message: str = "Team not found.") -> Team:
        team = self.teams.get(team_id)
        if team is None or team.organization_id != actor.organization_id:
            raise ServiceError(404, message)
        return team

    # ------------------------------------------------------------------ teams
    def _team_out(self, teams: list[Team]) -> list[TeamOut]:
        ids = [t.id for t in teams]
        counts = self.teams.member_counts(ids)
        leaders = self.teams.leaders_of(ids)
        return [
            TeamOut(
                id=t.id,
                name=t.name,
                member_count=counts.get(t.id, 0),
                leaders=[PersonRef(id=u.id, name=u.full_name or u.email) for u in leaders.get(t.id, [])],
            )
            for t in teams
        ]

    def list_teams(self, actor: User) -> list[TeamOut]:
        org_wide = actor.role == Role.OWNER or actor.can(Permission.TEAMS_CREATE) or actor.can(Permission.TEAMS_RENAME)
        teams = self.teams.list(actor.organization_id)
        if not org_wide:
            scope = self._scope(actor)
            teams = [t for t in teams if t.id in scope]
        return self._team_out(teams)

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
        team = self._get_team(actor, team_id)
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
        return self._team_out([team])[0]

    def delete_team(self, actor: User, team_id: int, client: ClientInfo) -> int:
        """Delete a team (Owner only). Its members stay, with no team. Its Team Leaders stop
        leading it, and those who lead no other team become plain members. Returns how many
        members were left without a team."""
        if actor.role != Role.OWNER:
            raise ServiceError(403, "Only the Owner can delete teams.")
        team = self._get_team(actor, team_id)
        demoted = []
        for leader in self.teams.leaders_of([team.id]).get(team.id, []):
            self._drop_leadership(leader, team)
            if leader.role == Role.MEMBER:
                demoted.append(leader.email)
        # Done here rather than left to the foreign key's ON DELETE SET NULL, so the
        # result is the same on every database and in this session's loaded objects.
        moved = self.teams.unassign_members(team.id)
        self.audit.record(
            AuditAction.TEAM_DELETED, client, user_id=actor.id, organization_id=actor.organization_id,
            team_id=team.id, name=team.name, members_unassigned=moved, leaders_demoted=demoted,
        )
        self.teams.delete(team)
        self.db.commit()
        return moved

    # ------------------------------------------------------------ leadership
    @staticmethod
    def _drop_leadership(user: User, team: Team) -> None:
        """Stop leading `team`; a Team Leader who leads nothing any more becomes a member."""
        user.led_teams = [t for t in user.led_teams if t.id != team.id]
        if user.role == Role.TEAM_LEADER and not user.led_teams:
            user.role = Role.MEMBER

    @staticmethod
    def _make_leader_of(user: User, team: Team) -> None:
        """Lead `team` too; a member is promoted and leaves their own team."""
        if team.id not in user.led_team_ids:
            user.led_teams = sorted([*user.led_teams, team], key=lambda t: t.name)
        user.role = Role.TEAM_LEADER
        user.team_id = None
        user.team = None

    def add_team_leader(self, actor: User, team_id: int, user_id: int, client: ClientInfo) -> MemberOut:
        """Owner: make someone a leader of this team (a member is promoted to Team Leader)."""
        team = self._get_team(actor, team_id)
        user = self._get_member(actor, user_id)
        if user.role == Role.OWNER:
            raise ServiceError(422, "The Owner does not lead teams.")
        was = user.role.value
        self._make_leader_of(user, team)
        self.audit.record(
            AuditAction.USER_ROLES_CHANGED, client, user_id=actor.id, organization_id=actor.organization_id,
            target_user_id=user.id, leads_team={"added": team.id, "name": team.name},
            role={"from": was, "to": "team_leader"},
        )
        self.db.commit()
        return self._out(user, self.devices.get_for_user(user.id) is not None)

    def remove_team_leader(self, actor: User, team_id: int, user_id: int, client: ClientInfo) -> MemberOut:
        """Owner: stop someone leading this team. Leading no team any more makes them a member."""
        team = self._get_team(actor, team_id)
        user = self._get_member(actor, user_id)
        if team.id not in user.led_team_ids:
            raise ServiceError(404, "This person does not lead that team.")
        self._drop_leadership(user, team)
        self.audit.record(
            AuditAction.USER_ROLES_CHANGED, client, user_id=actor.id, organization_id=actor.organization_id,
            target_user_id=user.id, leads_team={"removed": team.id, "name": team.name}, role=user.role.value,
        )
        self.db.commit()
        return self._out(user, self.devices.get_for_user(user.id) is not None)

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
        if actor.role == Role.OWNER:
            users = self.users.list(actor.organization_id)
        else:
            users = self.users.list_in_teams(actor.organization_id, self._require_scope(actor))
            if actor.can(Permission.MEMBERS_TEAM):
                # Members with no team, so they can be brought into one of these teams.
                users += self.users.list_unassigned(actor.organization_id)
        bound = self.devices.bound_user_ids([u.id for u in users])
        return [self._out(u, u.id in bound) for u in users]

    def add_member(self, actor: User, body: MemberCreate, client: ClientInfo) -> MemberOut:
        team_id = body.team_id
        if actor.role != Role.OWNER:
            # Everyone but the Owner adds plain members to one of their teams.
            scope = self._require_scope(actor)
            if team_id is None:
                if len(scope) != 1:
                    raise ServiceError(422, "Select a team.")
                team_id = next(iter(scope))
            if team_id not in scope:
                raise ServiceError(403, OWN_TEAM_ONLY)
            if body.role != Role.MEMBER.value:
                raise ServiceError(403, "Only the Owner can add Team Leaders.")
        team = self._get_team(actor, team_id, "Select a team.") if team_id is not None else None
        if team is None and body.role == Role.TEAM_LEADER.value:
            raise ServiceError(422, LEADER_NEEDS_TEAM)
        bundles = self._resolve_bundles(actor, body.role_bundle_ids)
        self._ensure_can_hand_out(actor, bundles)
        if (problem := validate_password_strength(body.initial_password)) is not None:
            raise ServiceError(422, f"Initial password: {problem}")
        if self.users.get_by_email(body.email) is not None:
            raise ServiceError(409, "An account with this email already exists.")

        leader = body.role == Role.TEAM_LEADER.value
        user = self.users.add(
            User(
                organization_id=actor.organization_id,
                team_id=None if leader or team is None else team.id,
                led_teams=[team] if leader else [],
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
            created_user_id=user.id, team_id=team.id if team else None, role=body.role,
            role_bundles=[b.name for b in bundles],
        )
        self.db.commit()
        return self._out(user, device_registered=False)

    def update_member(self, actor: User, user_id: int, body: MemberUpdate, client: ClientInfo) -> MemberOut:
        """Edit a member's details, team, base role (Owner only) and/or role bundles."""
        user = self._get_member(actor, user_id)
        if body.details_given():
            self._update_details(actor, user, body, client)
        if body.role is not None and body.role != user.role.value:
            self._change_role(actor, user, body, client)
        elif body.team_given():
            if user.role == Role.TEAM_LEADER:
                if actor.role != Role.OWNER:
                    raise ServiceError(403, OWN_TEAM_ONLY)
                if body.team_id is None:
                    raise ServiceError(422, LEADER_NEEDS_TEAM)
                self._make_leader_of(user, self._get_team(actor, body.team_id, "Select a team."))
            elif body.team_id != user.team_id:
                self._update_team(actor, user, body.team_id, client)
        if body.role_bundle_ids is not None:
            self._update_bundles(actor, user, body.role_bundle_ids, client)
        if user.role == Role.TEAM_LEADER and not user.led_teams:
            raise ServiceError(422, LEADER_NEEDS_TEAM)  # nothing is saved
        self.db.commit()
        return self._out(user, self.devices.get_for_user(user.id) is not None)

    def _update_details(self, actor: User, user: User, body: MemberUpdate, client: ClientInfo) -> None:
        if actor.role != Role.OWNER:
            if not actor.can(Permission.MEMBERS_EDIT):
                raise ServiceError(403, NO_PERMISSION)
            self._ensure_manageable(actor, user)
        is_self = user.id == actor.id
        changes: dict = {}
        # Changes that make the member's current sessions wrong (email is signed into
        # every request) or unwanted end those sessions.
        sign_out = False

        if body.full_name is not None and body.full_name.strip() != user.full_name:
            changes["full_name"] = {"from": user.full_name, "to": body.full_name.strip()}
            user.full_name = body.full_name.strip()

        if body.email is not None and body.email != user.email:
            if self.users.get_by_email(body.email) is not None:
                raise ServiceError(409, "An account with this email already exists.")
            changes["email"] = {"from": user.email, "to": body.email}
            user.email = body.email
            sign_out = True

        if body.is_active is not None and body.is_active != user.is_active:
            if is_self:
                raise ServiceError(422, "You cannot disable your own account.")
            changes["is_active"] = body.is_active
            user.is_active = body.is_active
            sign_out = sign_out or not body.is_active

        if body.new_password is not None:
            if is_self:
                raise ServiceError(422, "Change your own password with Change password.")
            if (problem := validate_password_strength(body.new_password)) is not None:
                raise ServiceError(422, f"New password: {problem}")
            user.password_hash = hash_password(body.new_password)
            user.password_changed_at = datetime.now(timezone.utc)
            user.must_change_password = True
            user.failed_login_count = 0
            user.locked_until = None
            changes["password"] = "reset_to_initial"
            sign_out = True

        if sign_out:
            RefreshSessionRepository(self.db).revoke_all_for_user(user.id, datetime.now(timezone.utc))
        if changes:
            self.audit.record(
                AuditAction.USER_UPDATED, client, user_id=actor.id, organization_id=actor.organization_id,
                target_user_id=user.id, **changes,
            )

    def _update_team(self, actor: User, user: User, team_id: int | None, client: ClientInfo) -> None:
        """Move a plain member to a team, or out of their team (team_id None).

        The Owner moves anyone. Holders of `members.team` only bring a member with no team
        into one of their teams, take a member out of one, or move them between their teams.
        """
        if user.role == Role.OWNER:
            raise ServiceError(422, "The Owner does not belong to a team.")
        team = self._get_team(actor, team_id, "Select a team.") if team_id is not None else None
        if actor.role != Role.OWNER:
            if not actor.can(Permission.MEMBERS_TEAM):
                raise ServiceError(403, NO_PERMISSION)
            scope = self._require_scope(actor)
            if user.id == actor.id or user.role != Role.MEMBER:
                raise ServiceError(403, OWN_TEAM_ONLY)
            source_ok = user.team_id is None or user.team_id in scope
            target_ok = team_id is None or team_id in scope
            if not (source_ok and target_ok):
                raise ServiceError(
                    403, "You can only bring members with no team into your teams, or take members out of them."
                )
        self.audit.record(
            AuditAction.USER_UPDATED, client, user_id=actor.id, organization_id=actor.organization_id,
            target_user_id=user.id, team_id={"from": user.team_id, "to": team_id},
        )
        user.team_id = team_id
        user.team = team

    def _change_role(self, actor: User, user: User, body: MemberUpdate, client: ClientInfo) -> None:
        """Owner only. Member → Team Leader leads the given team (or their own team);
        Team Leader → Member stops leading and joins the given team, if any."""
        if user.role == Role.OWNER:
            raise ServiceError(403, "The Owner already has every permission.")
        if actor.role != Role.OWNER:
            raise ServiceError(403, "Only the Owner can change a member's base role.")
        was = user.role.value
        if body.role == Role.TEAM_LEADER.value:
            team_id = body.team_id if body.team_given() else user.team_id
            if team_id is None:
                raise ServiceError(422, LEADER_NEEDS_TEAM)
            self._make_leader_of(user, self._get_team(actor, team_id, "Select a team."))
        else:
            user.led_teams = []
            user.role = Role.MEMBER
            team_id = body.team_id if body.team_given() else None
            user.team = self._get_team(actor, team_id, "Select a team.") if team_id is not None else None
            user.team_id = team_id
        self.audit.record(
            AuditAction.USER_ROLES_CHANGED, client, user_id=actor.id, organization_id=actor.organization_id,
            target_user_id=user.id, role={"from": was, "to": user.role.value},
            team_id=user.team_id, led_teams=user.led_team_ids,
        )

    def _update_bundles(self, actor: User, user: User, bundle_ids: list[int], client: ClientInfo) -> None:
        if user.role == Role.OWNER:
            raise ServiceError(403, "The Owner already has every permission.")
        self._ensure_manageable(actor, user)
        wanted = self._resolve_bundles(actor, bundle_ids)
        current = {b.id: b for b in user.role_bundles}
        wanted_ids = {b.id for b in wanted}
        added = [b for b in wanted if b.id not in current]
        removed = [b for b in current.values() if b.id not in wanted_ids]
        self._ensure_can_hand_out(actor, added + removed)
        if added or removed:
            user.role_bundles = sorted(wanted, key=lambda b: b.name)
            self.audit.record(
                AuditAction.USER_ROLES_CHANGED, client, user_id=actor.id, organization_id=actor.organization_id,
                target_user_id=user.id, added_bundles=[b.name for b in added],
                removed_bundles=[b.name for b in removed],
            )

    def delete_member(self, actor: User, user_id: int, client: ClientInfo) -> None:
        """Delete an account for good. Its device, sessions and bundles go with it; the
        audit log keeps who it was. Non-owners delete only plain members of their teams."""
        user = self._get_member(actor, user_id)
        if user.role == Role.OWNER:
            raise ServiceError(422, "The Owner's account cannot be deleted.")
        self._ensure_manageable(actor, user)
        self.audit.record(
            AuditAction.USER_DELETED, client, user_id=actor.id, organization_id=actor.organization_id,
            deleted_user_id=user.id, email=user.email, full_name=user.full_name, role=user.role.value,
            team_id=user.team_id, led_teams=user.led_team_ids,
        )
        self.users.delete(user)
        self.db.commit()

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
            led_teams=[TeamRef(id=t.id, name=t.name) for t in user.led_teams],
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            device_registered=device_registered,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            role_bundles=[BundleRef(id=b.id, name=b.name) for b in user.role_bundles],
            permissions=sorted(p.value for p in user.permissions),
        )
