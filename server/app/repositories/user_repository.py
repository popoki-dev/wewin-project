from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from shared.enums import Role

from ..models import Organization, User, team_leaders


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str, *, for_update: bool = False) -> User | None:
        query = select(User).where(User.email == email)
        if for_update:
            query = query.with_for_update()
        return self.db.scalar(query)

    def any_owner(self) -> User | None:
        return self.db.scalar(select(User).where(User.role == Role.OWNER).limit(1))

    def list(self, organization_id: int, team_id: int | None = None) -> list[User]:
        query = select(User).where(User.organization_id == organization_id).order_by(User.full_name, User.email)
        if team_id is not None:
            query = query.where(User.team_id == team_id)
        return list(self.db.scalars(query))

    def list_in_teams(self, organization_id: int, team_ids: set[int]) -> list[User]:
        """Members of these teams and the Team Leaders who lead any of them."""
        if not team_ids:
            return []
        leads = select(team_leaders.c.user_id).where(team_leaders.c.team_id.in_(team_ids))
        query = (
            select(User)
            .where(User.organization_id == organization_id, or_(User.team_id.in_(team_ids), User.id.in_(leads)))
            .order_by(User.full_name, User.email)
        )
        return list(self.db.scalars(query))

    def list_unassigned(self, organization_id: int) -> list[User]:
        """Plain members who belong to no team."""
        query = (
            select(User)
            .where(User.organization_id == organization_id, User.team_id.is_(None), User.role == Role.MEMBER)
            .order_by(User.full_name, User.email)
        )
        return list(self.db.scalars(query))

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.flush()


class OrganizationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def first(self) -> Organization | None:
        return self.db.scalar(select(Organization).order_by(Organization.id).limit(1))

    def add(self, organization: Organization) -> Organization:
        self.db.add(organization)
        self.db.flush()
        return organization
