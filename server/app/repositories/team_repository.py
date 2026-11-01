from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Team, User


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
