from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from shared.permissions import Permission

from .auth import _EmailModel, normalize_email


def _clean_name(v: str, message: str) -> str:
    v = " ".join(v.split())
    if not v:
        raise ValueError(message)
    return v


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return _clean_name(v, "Enter a team name.")


class PersonRef(BaseModel):
    id: int
    name: str


class TeamRef(BaseModel):
    id: int
    name: str


class TeamOut(BaseModel):
    id: int
    name: str
    member_count: int = 0  # plain members (users.team_id); leaders are listed separately
    leaders: list[PersonRef] = []


class TeamLeaderAdd(BaseModel):
    user_id: int


class RoleBundleIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=300)
    permissions: list[Permission] = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return _clean_name(v, "Enter a bundle name.")


class RoleBundleOut(BaseModel):
    id: int
    name: str
    description: str
    permissions: list[str]
    member_count: int = 0


class BundleRef(BaseModel):
    id: int
    name: str


class MemberCreate(_EmailModel):
    full_name: str = Field(default="", max_length=200)
    # Optional for the Owner (plain members may have no team); a Team Leader always adds to
    # their own team, and Team Leaders being added need a team.
    team_id: int | None = None
    role: Literal["member", "team_leader"] = "member"
    initial_password: str = Field(min_length=1, max_length=256)
    role_bundle_ids: list[int] = Field(default_factory=list, max_length=50)


class MemberUpdate(BaseModel):
    """Omitted fields are left unchanged.

    Details (name, email, active, new initial password) need `members.edit`. `team_id`
    is applied whenever it is sent, so an explicit null takes the member out of their team;
    the Owner moves anyone, holders of `members.team` only bring members with no team into
    their own team or take them out of it. The base role is the Owner's; role bundles
    follow the assignment rules in docs/permissions.md.
    """

    full_name: str | None = Field(default=None, max_length=200)
    email: str | None = None
    team_id: int | None = None
    is_active: bool | None = None
    # Replaces the password with a new initial one the member must change at next sign-in.
    new_password: str | None = Field(default=None, min_length=1, max_length=256)
    role: Literal["member", "team_leader"] | None = None
    role_bundle_ids: list[int] | None = Field(default=None, max_length=50)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str | None) -> str | None:
        return None if v is None else normalize_email(v)

    def details_given(self) -> bool:
        return any(v is not None for v in (self.full_name, self.email, self.is_active, self.new_password))

    def team_given(self) -> bool:
        return "team_id" in self.model_fields_set


class MemberOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    team_id: int | None
    team_name: str | None
    # Team Leaders only: the teams they lead (they have no team_id).
    led_teams: list[TeamRef] = []
    is_active: bool
    must_change_password: bool
    device_registered: bool
    last_login_at: datetime | None
    created_at: datetime  # when the account was registered
    role_bundles: list[BundleRef]
    permissions: list[str]
