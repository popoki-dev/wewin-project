from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.api_contracts import RESET_CODE_LENGTH
from shared.device_signature import DEVICE_ID_RE

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 255 or not _EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address.")
    return value


class _EmailModel(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return normalize_email(v)


class LoginRequest(_EmailModel):
    password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False
    # SHA-256 of the PC's MAC address (see shared/device_signature.py).
    device_id: str = Field(pattern=DEVICE_ID_RE.pattern)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=512)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False


class ForgotPasswordRequest(_EmailModel):
    pass


class ResetPasswordRequest(_EmailModel):
    code: str = Field(pattern=rf"^\d{{{RESET_CODE_LENGTH}}}$")
    new_password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    email: str
    full_name: str
    role: str
    team_id: int | None = None
    must_change_password: bool = False
    # Effective permissions (role plus role bundles), for showing the right UI.
    permissions: list[str] = []
    last_login_at: datetime | None = None

    @field_validator("permissions", mode="before")
    @classmethod
    def _sorted(cls, v) -> list[str]:
        return sorted(p.value if hasattr(p, "value") else p for p in v)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime
    # Returned by sign-in only: the key this PC signs every later request with.
    device_secret: str | None = None
    user: UserOut
