"""Role bundles: named permission sets that only the Owner defines."""

from __future__ import annotations

from sqlalchemy.orm import Session

from shared.enums import AuditAction
from shared.permissions import Permission

from ..models import RoleBundle, User
from ..repositories.audit_repository import AuditRepository, ClientInfo
from ..repositories.role_bundle_repository import RoleBundleRepository
from ..schemas.members import RoleBundleIn, RoleBundleOut
from .errors import ServiceError

BUNDLE_NOT_FOUND = "Role bundle not found."


def _sorted_values(permissions: list[Permission]) -> list[str]:
    return sorted({p.value for p in permissions})


class RoleBundleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.bundles = RoleBundleRepository(db)
        self.audit = AuditRepository(db)

    def list(self, actor: User) -> list[RoleBundleOut]:
        bundles = self.bundles.list(actor.organization_id)
        counts = self.bundles.member_counts([b.id for b in bundles])
        return [self._out(b, counts.get(b.id, 0)) for b in bundles]

    def create(self, actor: User, body: RoleBundleIn, client: ClientInfo) -> RoleBundleOut:
        self._ensure_name_free(actor, body.name)
        bundle = self.bundles.add(
            RoleBundle(
                organization_id=actor.organization_id,
                name=body.name,
                description=body.description.strip(),
                permissions=_sorted_values(body.permissions),
            )
        )
        self.audit.record(
            AuditAction.ROLE_BUNDLE_CREATED, client, user_id=actor.id, organization_id=actor.organization_id,
            bundle_id=bundle.id, name=bundle.name, permissions=bundle.permissions,
        )
        self.db.commit()
        return self._out(bundle, 0)

    def update(self, actor: User, bundle_id: int, body: RoleBundleIn, client: ClientInfo) -> RoleBundleOut:
        bundle = self._get(actor, bundle_id)
        if body.name.lower() != bundle.name.lower():
            self._ensure_name_free(actor, body.name)
        before = list(bundle.permissions)
        bundle.name = body.name
        bundle.description = body.description.strip()
        bundle.permissions = _sorted_values(body.permissions)
        self.audit.record(
            AuditAction.ROLE_BUNDLE_UPDATED, client, user_id=actor.id, organization_id=actor.organization_id,
            bundle_id=bundle.id, name=bundle.name, permissions_before=before, permissions=bundle.permissions,
        )
        self.db.commit()
        return self._out(bundle, self.bundles.member_counts([bundle.id]).get(bundle.id, 0))

    def delete(self, actor: User, bundle_id: int, client: ClientInfo) -> None:
        """Delete a bundle; every member holding it loses its permissions at once."""
        bundle = self._get(actor, bundle_id)
        self.audit.record(
            AuditAction.ROLE_BUNDLE_DELETED, client, user_id=actor.id, organization_id=actor.organization_id,
            bundle_id=bundle.id, name=bundle.name,
        )
        self.bundles.delete(bundle)
        self.db.commit()

    def _get(self, actor: User, bundle_id: int) -> RoleBundle:
        bundle = self.bundles.get(bundle_id)
        if bundle is None or bundle.organization_id != actor.organization_id:
            raise ServiceError(404, BUNDLE_NOT_FOUND)
        return bundle

    def _ensure_name_free(self, actor: User, name: str) -> None:
        if self.bundles.get_by_name(actor.organization_id, name) is not None:
            raise ServiceError(409, f"A role bundle named “{name}” already exists.")

    @staticmethod
    def _out(bundle: RoleBundle, member_count: int) -> RoleBundleOut:
        return RoleBundleOut(
            id=bundle.id,
            name=bundle.name,
            description=bundle.description,
            permissions=list(bundle.permissions),
            member_count=member_count,
        )
