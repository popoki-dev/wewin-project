from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import Team, User, team_leaders


class TeamRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, team_id: int) -> Team | None:
        return self.db.get(Team, team_id)

    def get_by_name(self, organization_id: int, name: str) -> Team | None:
        query = select(Team).where(Team.organization_id == organization_id, func.lower(Team.name) == name.lower())
        return self.db.scalar(query)

    def list(self, organization_id: int, team_id: int | None = None) -> list[Team]:
        query = select(Team).where(Team.organization_id == organization_id).order_by(Team.name)
        if team_id is not None:
            query = query.where(Team.id == team_id)
        return list(self.db.scalars(query))

    def member_counts(self, team_ids: list[int]) -> dict[int, int]:
        if not team_ids:
            return {}
        query = select(User.team_id, func.count()).where(User.team_id.in_(team_ids)).group_by(User.team_id)
        return dict(self.db.execute(query).all())

    def add(self, team: Team) -> Team:
        self.db.add(team)
        self.db.flush()
        return team

    def leaders_of(self, team_ids: list[int]) -> dict[int, list[User]]:
        """Team Leaders of each team, by team id."""
        if not team_ids:
            return {}
        rows = self.db.execute(
            select(team_leaders.c.team_id, User)
            .join(User, User.id == team_leaders.c.user_id)
            .where(team_leaders.c.team_id.in_(team_ids))
            .order_by(User.full_name, User.email)
        ).all()
        result: dict[int, list[User]] = {}
        for team_id, user in rows:
            result.setdefault(team_id, []).append(user)
        return result

    def unassign_members(self, team_id: int) -> int:
        """Set team_id to NULL for everyone in the team; returns how many were moved."""
        result = self.db.execute(
            update(User).where(User.team_id == team_id).values(team_id=None).execution_options(synchronize_session="fetch")
        )
        return result.rowcount

    def delete(self, team: Team) -> None:
        self.db.delete(team)
        self.db.flush()
