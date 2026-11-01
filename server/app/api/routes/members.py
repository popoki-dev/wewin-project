from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from shared.enums import Role
from shared.permissions import Permission

from ...core.authentication import get_client_info, get_current_user
from ...core.permissions import require_permission, require_role
from ...database.session import get_db
from ...models import User
from ...repositories.audit_repository import ClientInfo
from ...schemas.common import MessageResponse
from ...schemas.members import (
    MemberCreate,
    MemberOut,
    MemberUpdate,
    RoleBundleIn,
    RoleBundleOut,
    TeamCreate,
    TeamOut,
)
from ...services.member_service import MemberService
from ...services.role_bundle_service import RoleBundleService

router = APIRouter(tags=["members"])


def get_member_service(db: Session = Depends(get_db)) -> MemberService:
    return MemberService(db)


def get_bundle_service(db: Session = Depends(get_db)) -> RoleBundleService:
    return RoleBundleService(db)


# ---------------------------------------------------------------------- teams
@router.get("/teams", response_model=list[TeamOut])
def list_teams(
    user: User = Depends(get_current_user),
    members: MemberService = Depends(get_member_service),
) -> list[TeamOut]:
    return members.list_teams(user)


@router.post("/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    body: TeamCreate,
    user: User = Depends(require_permission(Permission.TEAMS_CREATE)),
    client: ClientInfo = Depends(get_client_info),
    members: MemberService = Depends(get_member_service),
) -> TeamOut:
    return members.create_team(user, body.name, client)


@router.patch("/teams/{team_id}", response_model=TeamOut)
def rename_team(
    team_id: int,
    body: TeamCreate,
    user: User = Depends(require_permission(Permission.TEAMS_RENAME)),
    client: ClientInfo = Depends(get_client_info),
    members: MemberService = Depends(get_member_service),
) -> TeamOut:
    return members.rename_team(user, team_id, body.name, client)


# -------------------------------------------------------------------- members
@router.get("/members", response_model=list[MemberOut])
def list_members(
    user: User = Depends(require_permission(Permission.MEMBERS_VIEW)),
    members: MemberService = Depends(get_member_service),
) -> list[MemberOut]:
    return members.list_members(user)


@router.post("/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    body: MemberCreate,
    user: User = Depends(require_permission(Permission.MEMBERS_ADD)),
    client: ClientInfo = Depends(get_client_info),
    members: MemberService = Depends(get_member_service),
) -> MemberOut:
    return members.add_member(user, body, client)


@router.patch("/members/{user_id}", response_model=MemberOut)
def update_member(
    user_id: int,
    body: MemberUpdate,
    user: User = Depends(require_permission(Permission.MEMBERS_VIEW)),
    client: ClientInfo = Depends(get_client_info),
    members: MemberService = Depends(get_member_service),
) -> MemberOut:
    # Finer checks (details and base role: Owner only; bundles: members.assign_roles) are in the service.
    return members.update_member(user, user_id, body, client)


@router.delete("/members/{user_id}", response_model=MessageResponse)
def delete_member(
    user_id: int,
    user: User = Depends(require_permission(Permission.MEMBERS_DELETE)),
    client: ClientInfo = Depends(get_client_info),
    members: MemberService = Depends(get_member_service),
) -> MessageResponse:
    members.delete_member(user, user_id, client)
    return MessageResponse(message="Member deleted.")


@router.post("/members/{user_id}/reset-device", response_model=MemberOut)
def reset_device(
    user_id: int,
    user: User = Depends(require_permission(Permission.MEMBERS_RESET_DEVICE)),
    client: ClientInfo = Depends(get_client_info),
    members: MemberService = Depends(get_member_service),
) -> MemberOut:
    return members.reset_device(user, user_id, client)


# --------------------------------------------------------------- role bundles
@router.get("/role-bundles", response_model=list[RoleBundleOut])
def list_role_bundles(
    user: User = Depends(require_permission(Permission.MEMBERS_VIEW)),
    bundles: RoleBundleService = Depends(get_bundle_service),
) -> list[RoleBundleOut]:
    return bundles.list(user)


@router.post("/role-bundles", response_model=RoleBundleOut, status_code=status.HTTP_201_CREATED)
def create_role_bundle(
    body: RoleBundleIn,
    user: User = Depends(require_role(Role.OWNER)),
    client: ClientInfo = Depends(get_client_info),
    bundles: RoleBundleService = Depends(get_bundle_service),
) -> RoleBundleOut:
    return bundles.create(user, body, client)


@router.put("/role-bundles/{bundle_id}", response_model=RoleBundleOut)
def update_role_bundle(
    bundle_id: int,
    body: RoleBundleIn,
    user: User = Depends(require_role(Role.OWNER)),
    client: ClientInfo = Depends(get_client_info),
    bundles: RoleBundleService = Depends(get_bundle_service),
) -> RoleBundleOut:
    return bundles.update(user, bundle_id, body, client)


@router.delete("/role-bundles/{bundle_id}", response_model=MessageResponse)
def delete_role_bundle(
    bundle_id: int,
    user: User = Depends(require_role(Role.OWNER)),
    client: ClientInfo = Depends(get_client_info),
    bundles: RoleBundleService = Depends(get_bundle_service),
) -> MessageResponse:
    bundles.delete(user, bundle_id, client)
    return MessageResponse(message="Role bundle deleted.")
