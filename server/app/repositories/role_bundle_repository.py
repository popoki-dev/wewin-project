from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import RoleBundle, user_role_bundles


class RoleBundleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, bundle_id: int) -> RoleBundle | None:
        return self.db.get(RoleBundle, bundle_id)

    def get_by_name(self, organization_id: int, name: str) -> RoleBundle | None:
        query = select(RoleBundle).where(
            RoleBundle.organization_id == organization_id, func.lower(RoleBundle.name) == name.lower()
        )
        return self.db.scalar(query)

    def get_many(self, organization_id: int, bundle_ids: list[int]) -> list[RoleBundle]:
        if not bundle_ids:
            return []
        query = select(RoleBundle).where(RoleBundle.organization_id == organization_id, RoleBundle.id.in_(bundle_ids))
        return list(self.db.scalars(query))

    def list(self, organization_id: int) -> list[RoleBundle]:
        query = select(RoleBundle).where(RoleBundle.organization_id == organization_id).order_by(RoleBundle.name)
        return list(self.db.scalars(query))

    def member_counts(self, bundle_ids: list[int]) -> dict[int, int]:
        if not bundle_ids:
            return {}
        query = (
            select(user_role_bundles.c.bundle_id, func.count())
            .where(user_role_bundles.c.bundle_id.in_(bundle_ids))
            .group_by(user_role_bundles.c.bundle_id)
        )
        return dict(self.db.execute(query).all())

    def add(self, bundle: RoleBundle) -> RoleBundle:
        self.db.add(bundle)
        self.db.flush()
        return bundle

    def delete(self, bundle: RoleBundle) -> None:
        self.db.delete(bundle)
        self.db.flush()
