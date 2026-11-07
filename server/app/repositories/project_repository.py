from __future__ import annotations

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..models import Project


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, project_id: int) -> Project | None:
        return self.db.get(Project, project_id)

    def list(
        self, organization_id: int, *, team_ids: set[int] | None = None, project_owner_id: int | None = None
    ) -> list[Project]:
        """Every project of the organization, or only those in `team_ids` or owned by
        `project_owner_id` (either matches) when one of them is given."""
        query = select(Project).where(Project.organization_id == organization_id)
        scope = []
        if team_ids:
            scope.append(Project.team_id.in_(team_ids))
        if project_owner_id is not None:
            scope.append(Project.project_owner_id == project_owner_id)
        if team_ids is not None or project_owner_id is not None:
            if not scope:
                return []
            query = query.where(or_(*scope))
        query = query.order_by(Project.start_date.desc(), Project.id.desc())
        return list(self.db.scalars(query))

    def forget_user(self, user_id: int) -> None:
        """A deleted account: its projects and checks stay, without the link to it."""
        for column in (Project.created_by_id, Project.project_owner_id, Project.leader_checked_by_id,
                       Project.owner_checked_by_id):
            self.db.execute(
                update(Project).where(column == user_id).values({column.key: None})
                .execution_options(synchronize_session="fetch")
            )

    def add(self, project: Project) -> Project:
        self.db.add(project)
        self.db.flush()
        return project

    def delete(self, project: Project) -> None:
        self.db.delete(project)
        self.db.flush()
