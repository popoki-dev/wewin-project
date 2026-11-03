"""Projects, their payment history and checks.

Who may do what:
- The Owner sees, adds, edits and deletes every project, and places the Owner check.
- A Team Leader works on projects of the teams they lead (and their own), and places
  the Leader check on their teams' projects. An Owner check locks the project for them.
- A member works on the projects they created. A Leader or Owner check locks it for them.
Permissions (projects.*) gate each action on top of these scope rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from shared.enums import AuditAction, Role
from shared.permissions import Permission

from ..models import PaymentPayout, Project, ProjectCodeveloper, ProjectPayment, User
from ..repositories.audit_repository import AuditRepository, ClientInfo
from ..repositories.project_repository import ProjectRepository
from ..repositories.team_repository import TeamRepository
from ..schemas.projects import (
    CheckOut,
    CodeveloperIn,
    CodeveloperOut,
    PaymentIn,
    PaymentOut,
    PayoutOut,
    ProjectAccess,
    ProjectIn,
    ProjectOut,
)
from .errors import ServiceError

NOT_FOUND = "Project not found."
NO_PERMISSION = "You do not have permission to do this."
LOCKED_BY_OWNER = "The Owner has checked this project, so it can no longer be changed."
LOCKED_BY_LEADER = "A Team Leader has checked this project, so it can no longer be changed."

CheckLevel = Literal["leader", "owner"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.teams = TeamRepository(db)
        self.audit = AuditRepository(db)

    # ----------------------------------------------------------------- scope
    @staticmethod
    def _is_owner(actor: User) -> bool:
        return actor.role == Role.OWNER

    @staticmethod
    def _leads(actor: User, project: Project) -> bool:
        return actor.role == Role.TEAM_LEADER and project.team_id is not None and project.team_id in actor.led_team_ids

    def _can_see(self, actor: User, project: Project) -> bool:
        if project.organization_id != actor.organization_id:
            return False
        return self._is_owner(actor) or self._leads(actor, project) or project.created_by_id == actor.id

    def _lock_reason(self, actor: User, project: Project) -> str | None:
        """Why the actor may not change this project because of a check, if they may not."""
        if self._is_owner(actor):
            return None
        if project.owner_checked_at is not None:
            return LOCKED_BY_OWNER
        if not self._leads(actor, project) and project.leader_checked_at is not None:
            return LOCKED_BY_LEADER  # members (and leaders of other teams) on their own projects
        return None

    def _may_change(self, actor: User, project: Project, permission: Permission) -> bool:
        return actor.can(permission) and self._can_see(actor, project) and self._lock_reason(actor, project) is None

    def _check_level(self, actor: User, project: Project) -> CheckLevel | None:
        """The check this actor places on this project, if any."""
        if self._is_owner(actor):
            return "owner"
        if actor.can(Permission.PROJECTS_CHECK) and self._leads(actor, project):
            return "leader"
        return None

    def _access(self, actor: User, project: Project) -> ProjectAccess:
        level = self._check_level(actor, project)
        if level == "owner":
            check = project.owner_checked_at is None
            uncheck = project.owner_checked_at is not None or project.leader_checked_at is not None
        elif level == "leader":
            free = project.owner_checked_at is None
            check = free and project.leader_checked_at is None
            uncheck = free and project.leader_checked_at is not None
        else:
            check = uncheck = False
        return ProjectAccess(
            edit=self._may_change(actor, project, Permission.PROJECTS_EDIT),
            delete=self._may_change(actor, project, Permission.PROJECTS_DELETE),
            check=check,
            uncheck=uncheck,
        )

    def _get(self, actor: User, project_id: int) -> Project:
        project = self.projects.get(project_id)
        if project is None or not self._can_see(actor, project):
            raise ServiceError(404, NOT_FOUND)
        return project

    def _ensure_may_change(self, actor: User, project: Project, permission: Permission) -> None:
        if not actor.can(permission):
            raise ServiceError(403, NO_PERMISSION)
        if (reason := self._lock_reason(actor, project)) is not None:
            raise ServiceError(409, reason)

    def _resolve_team(self, actor: User, team_id: int | None, current: int | None = None) -> int | None:
        """The team a project may be filed under by this actor."""
        if self._is_owner(actor):
            if team_id is None:
                return None
            team = self.teams.get(team_id)
            if team is None or team.organization_id != actor.organization_id:
                raise ServiceError(404, "Select a team.")
            return team.id
        if actor.role == Role.TEAM_LEADER:
            led = actor.led_team_ids
            if team_id is None:
                if len(led) == 1:
                    return led[0]
                raise ServiceError(422, "Select one of your teams.")
            if team_id not in led:
                raise ServiceError(403, "You can only file projects under teams you lead.")
            return team_id
        # Members file projects under their own team; it cannot be changed.
        return actor.team_id if current is None else current

    # ------------------------------------------------------------------ read
    def list(self, actor: User) -> list[ProjectOut]:
        if not actor.can(Permission.PROJECTS_VIEW):
            raise ServiceError(403, NO_PERMISSION)
        if self._is_owner(actor):
            projects = self.projects.list(actor.organization_id)
        elif actor.role == Role.TEAM_LEADER:
            projects = self.projects.list(actor.organization_id, team_ids=set(actor.led_team_ids), created_by_id=actor.id)
        else:
            projects = self.projects.list(actor.organization_id, created_by_id=actor.id)
        return [self._out(actor, p) for p in projects]

    def get(self, actor: User, project_id: int) -> ProjectOut:
        if not actor.can(Permission.PROJECTS_VIEW):
            raise ServiceError(403, NO_PERMISSION)
        return self._out(actor, self._get(actor, project_id))

    # ----------------------------------------------------------------- write
    def create(self, actor: User, body: ProjectIn, client: ClientInfo) -> ProjectOut:
        if not actor.can(Permission.PROJECTS_CREATE):
            raise ServiceError(403, NO_PERMISSION)
        if any(p.id is not None for p in body.payments) or any(c.id is not None for c in body.codevelopers):
            raise ServiceError(422, "New projects cannot refer to existing payments or co-developers.")
        project = Project(
            organization_id=actor.organization_id,
            team_id=self._resolve_team(actor, body.team_id),
            created_by_id=actor.id,
        )
        self._apply(project, body)
        codevelopers = [self._codeveloper(c) for c in body.codevelopers]
        project.codevelopers = codevelopers
        project.payments = [self._payment(p, codevelopers) for p in body.payments]
        self.projects.add(project)
        self.audit.record(
            AuditAction.PROJECT_CREATED, client, user_id=actor.id, organization_id=actor.organization_id,
            project_id=project.id, title=project.title, team_id=project.team_id,
        )
        self.db.commit()
        return self._out(actor, project)

    def update(self, actor: User, project_id: int, body: ProjectIn, client: ClientInfo) -> ProjectOut:
        project = self._get(actor, project_id)
        self._ensure_may_change(actor, project, Permission.PROJECTS_EDIT)
        project.team_id = self._resolve_team(actor, body.team_id, current=project.team_id)
        project.team = None if project.team_id is None else self.teams.get(project.team_id)
        self._apply(project, body)
        codevelopers, codev_changes = self._sync_codevelopers(project, body.codevelopers)
        changes = {**codev_changes, **self._sync_payments(project, body.payments, codevelopers)}
        self.audit.record(
            AuditAction.PROJECT_UPDATED, client, user_id=actor.id, organization_id=actor.organization_id,
            project_id=project.id, title=project.title, **changes,
        )
        self.db.commit()
        return self._out(actor, project)

    def delete(self, actor: User, project_id: int, client: ClientInfo) -> None:
        project = self._get(actor, project_id)
        self._ensure_may_change(actor, project, Permission.PROJECTS_DELETE)
        self.audit.record(
            AuditAction.PROJECT_DELETED, client, user_id=actor.id, organization_id=actor.organization_id,
            project_id=project.id, title=project.title, team_id=project.team_id,
            payments=len(project.payments), paid_cents=sum(p.amount_cents for p in project.payments),
        )
        self.projects.delete(project)
        self.db.commit()

    # ---------------------------------------------------------------- checks
    def check(self, actor: User, project_id: int, client: ClientInfo) -> ProjectOut:
        project = self._get(actor, project_id)
        level = self._check_level(actor, project)
        if level is None:
            raise ServiceError(403, NO_PERMISSION)
        if level == "leader" and project.owner_checked_at is not None:
            raise ServiceError(409, LOCKED_BY_OWNER)
        if level == "owner":
            project.owner_checked_at, project.owner_checked_by_id = _now(), actor.id
            project.owner_checked_by = actor
        else:
            project.leader_checked_at, project.leader_checked_by_id = _now(), actor.id
            project.leader_checked_by = actor
        self.audit.record(
            AuditAction.PROJECT_CHECKED, client, user_id=actor.id, organization_id=actor.organization_id,
            project_id=project.id, level=level,
        )
        self.db.commit()
        return self._out(actor, project)

    def uncheck(self, actor: User, project_id: int, level: CheckLevel, client: ClientInfo) -> ProjectOut:
        """Remove a check. The Owner removes either; a Team Leader removes the Leader check
        of their teams' projects while the Owner has not checked them."""
        project = self._get(actor, project_id)
        mine = self._check_level(actor, project)
        if mine is None or (mine == "leader" and level == "owner"):
            raise ServiceError(403, NO_PERMISSION)
        if mine == "leader" and project.owner_checked_at is not None:
            raise ServiceError(409, LOCKED_BY_OWNER)
        if level == "owner":
            project.owner_checked_at = project.owner_checked_by_id = project.owner_checked_by = None
        else:
            project.leader_checked_at = project.leader_checked_by_id = project.leader_checked_by = None
        self.audit.record(
            AuditAction.PROJECT_UNCHECKED, client, user_id=actor.id, organization_id=actor.organization_id,
            project_id=project.id, level=level,
        )
        self.db.commit()
        return self._out(actor, project)

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _apply(project: Project, body: ProjectIn) -> None:
        project.title = body.title
        project.start_date = body.start_date
        project.end_date = body.end_date
        project.category = body.category.value
        project.total_budget_cents = body.total_budget_cents
        project.monthly_budget_cents = body.monthly_budget_cents
        project.details = body.details

    @staticmethod
    def _codeveloper(entry: CodeveloperIn) -> ProjectCodeveloper:
        return ProjectCodeveloper(nationality=entry.nationality, name=entry.name, external_id=entry.external_id)

    def _sync_codevelopers(
        self, project: Project, entries: list[CodeveloperIn]
    ) -> tuple[list[ProjectCodeveloper], dict]:
        """Make the co-developers match `entries` (update by id, add new, delete the rest).
        Returns them in `entries` order, which is what payouts' `codeveloper_index` refers to."""
        existing = {c.id: c for c in project.codevelopers}
        ids = [e.id for e in entries if e.id is not None]
        if len(ids) != len(set(ids)) or not set(ids) <= existing.keys():
            raise ServiceError(422, "The co-developers refer to entries that are not part of this project.")
        result: list[ProjectCodeveloper] = []
        for entry in entries:
            if entry.id is None:
                result.append(self._codeveloper(entry))
                continue
            codev = existing[entry.id]
            codev.nationality, codev.name, codev.external_id = entry.nationality, entry.name, entry.external_id
            result.append(codev)
        project.codevelopers = result
        return result, {"codevelopers": len(result), "codevelopers_removed": len(existing) - len(ids)}

    @staticmethod
    def _fill_payment(payment: ProjectPayment, entry: PaymentIn, codevelopers: list[ProjectCodeveloper]) -> None:
        payment.paid_on = entry.paid_on
        payment.description = entry.description
        payment.amount_cents = entry.amount_cents
        payment.my_share_cents = entry.my_share_cents
        payment.fund_location = entry.fund_location
        # Linked by object, not id, so co-developers added in this same request work too.
        payment.payouts = [
            PaymentPayout(codeveloper=codevelopers[p.codeveloper_index], amount_cents=p.amount_cents)
            for p in entry.payouts
        ]

    def _payment(self, entry: PaymentIn, codevelopers: list[ProjectCodeveloper]) -> ProjectPayment:
        payment = ProjectPayment()
        self._fill_payment(payment, entry, codevelopers)
        return payment

    def _sync_payments(
        self, project: Project, entries: list[PaymentIn], codevelopers: list[ProjectCodeveloper]
    ) -> dict:
        """Make the payment history match `entries`: update by id, add new, delete the rest."""
        existing = {p.id: p for p in project.payments}
        ids = [e.id for e in entries if e.id is not None]
        if len(ids) != len(set(ids)) or not set(ids) <= existing.keys():
            raise ServiceError(422, "The payment history refers to payments that are not part of this project.")
        kept: list[ProjectPayment] = []
        added = 0
        for entry in entries:
            if entry.id is None:
                kept.append(self._payment(entry, codevelopers))
                added += 1
                continue
            payment = existing[entry.id]
            self._fill_payment(payment, entry, codevelopers)
            kept.append(payment)
        project.payments = kept
        return {"payments": len(kept), "payments_added": added, "payments_removed": len(existing) - len(ids)}

    def _out(self, actor: User, project: Project) -> ProjectOut:
        def check(at, by) -> CheckOut | None:
            return None if at is None else CheckOut(at=at, by=(by.full_name or by.email) if by else None)

        payments = sorted(project.payments, key=lambda p: (p.paid_on, p.id or 0))

        def payment_out(p: ProjectPayment) -> PaymentOut:
            paid_out = sum(x.amount_cents for x in p.payouts)
            return PaymentOut(
                id=p.id, paid_on=p.paid_on, description=p.description, amount_cents=p.amount_cents,
                my_share_cents=p.my_share_cents, fund_location=p.fund_location,
                payouts=[
                    PayoutOut(codeveloper_id=x.codeveloper.id, codeveloper_label=x.codeveloper.label,
                              amount_cents=x.amount_cents)
                    for x in p.payouts
                ],
                paid_out_cents=paid_out,
                remaining_cents=p.amount_cents - p.my_share_cents - paid_out,
            )

        return ProjectOut(
            id=project.id,
            title=project.title,
            start_date=project.start_date,
            end_date=project.end_date,
            category=project.category,
            total_budget_cents=project.total_budget_cents,
            monthly_budget_cents=project.monthly_budget_cents,
            paid_cents=sum(p.amount_cents for p in payments),
            remaining_cents=sum(p.remaining_cents for p in payments),
            details=project.details,
            team_id=project.team_id,
            team_name=project.team.name if project.team else None,
            created_by_id=project.created_by_id,
            created_by_name=(project.created_by.full_name or project.created_by.email) if project.created_by else None,
            leader_check=check(project.leader_checked_at, project.leader_checked_by),
            owner_check=check(project.owner_checked_at, project.owner_checked_by),
            codevelopers=[
                CodeveloperOut(id=c.id, nationality=c.nationality, name=c.name, external_id=c.external_id)
                for c in project.codevelopers
            ],
            payments=[payment_out(p) for p in payments],
            created_at=project.created_at,
            updated_at=project.updated_at,
            access=self._access(actor, project),
        )
