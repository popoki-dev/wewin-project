from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from shared.permissions import Permission

from .auth import _EmailModel


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


class TeamOut(BaseModel):
    id: int
    name: str
    member_count: int = 0


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
    team_id: int
    role: Literal["member", "team_leader"] = "member"
    initial_password: str = Field(min_length=1, max_length=256)
    role_bundle_ids: list[int] = Field(default_factory=list, max_length=50)


class MemberRolesUpdate(BaseModel):
    """Omitted fields are left unchanged."""

    role: Literal["member", "team_leader"] | None = None
    role_bundle_ids: list[int] | None = Field(default=None, max_length=50)


class MemberOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    team_id: int | None
    team_name: str | None
    is_active: bool
    must_change_password: bool
    device_registered: bool
    last_login_at: datetime | None
    role_bundles: list[BundleRef]
    permissions: list[str]
