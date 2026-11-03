from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ...core.authentication import get_client_info, get_current_user
from ...database.session import get_db
from ...models import User
from ...repositories.audit_repository import ClientInfo
from ...schemas.common import MessageResponse
from ...schemas.projects import ProjectIn, ProjectOut
from ...services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


# Permission and scope checks (who sees which project, what a check locks) live in the service.
@router.get("", response_model=list[ProjectOut])
def list_projects(
    user: User = Depends(get_current_user),
    projects: ProjectService = Depends(get_project_service),
) -> list[ProjectOut]:
    return projects.list(user)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectIn,
    user: User = Depends(get_current_user),
    client: ClientInfo = Depends(get_client_info),
    projects: ProjectService = Depends(get_project_service),
) -> ProjectOut:
    return projects.create(user, body, client)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    projects: ProjectService = Depends(get_project_service),
) -> ProjectOut:
    return projects.get(user, project_id)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectIn,
    user: User = Depends(get_current_user),
    client: ClientInfo = Depends(get_client_info),
    projects: ProjectService = Depends(get_project_service),
) -> ProjectOut:
    return projects.update(user, project_id, body, client)


@router.delete("/{project_id}", response_model=MessageResponse)
def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    client: ClientInfo = Depends(get_client_info),
    projects: ProjectService = Depends(get_project_service),
) -> MessageResponse:
    projects.delete(user, project_id, client)
    return MessageResponse(message="Project deleted.")


@router.post("/{project_id}/check", response_model=ProjectOut)
def check_project(
    project_id: int,
    user: User = Depends(get_current_user),
    client: ClientInfo = Depends(get_client_info),
    projects: ProjectService = Depends(get_project_service),
) -> ProjectOut:
    # Places the caller's check: the Owner check for the Owner, the Leader check for a Team Leader.
    return projects.check(user, project_id, client)


@router.delete("/{project_id}/check", response_model=ProjectOut)
def uncheck_project(
    project_id: int,
    level: Literal["leader", "owner"] = Query(),
    user: User = Depends(get_current_user),
    client: ClientInfo = Depends(get_client_info),
    projects: ProjectService = Depends(get_project_service),
) -> ProjectOut:
    return projects.uncheck(user, project_id, level, client)
