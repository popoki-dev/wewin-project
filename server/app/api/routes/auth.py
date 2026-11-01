from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from ...core.authentication import get_client_info, get_device_signature, get_signed_in_user
from ...core.config import settings
from ...database.session import get_db
from ...models import User
from ...repositories.audit_repository import ClientInfo
from ...schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from ...schemas.common import MessageResponse
from ...services import mail_service
from ...services.auth_service import AuthService
from ...services.device_service import DeviceSignature

router = APIRouter(prefix="/auth", tags=["auth"])

FORGOT_PASSWORD_MESSAGE = "If an account exists for that email, a reset code has been sent."


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db, settings)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    client: ClientInfo = Depends(get_client_info),
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return auth.login(body.email, body.password, body.remember_me, body.device_id, client)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    signature: DeviceSignature | None = Depends(get_device_signature),
    client: ClientInfo = Depends(get_client_info),
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return auth.refresh(body.refresh_token, signature, client)


@router.post("/logout", response_model=MessageResponse)
def logout(
    body: LogoutRequest,
    client: ClientInfo = Depends(get_client_info),
    auth: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    auth.logout(body.refresh_token, client)
    return MessageResponse(message="Signed out.")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_signed_in_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_signed_in_user),
    client: ClientInfo = Depends(get_client_info),
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    # Signs every other session out and returns fresh tokens for this one.
    return auth.change_password(user, body.current_password, body.new_password, body.remember_me, client)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    background: BackgroundTasks,
    client: ClientInfo = Depends(get_client_info),
    auth: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    # Same response whether or not the account exists, to avoid email enumeration.
    pending = auth.request_password_reset(body.email, client)
    if pending is not None:
        background.add_task(mail_service.send_password_reset_code, pending.email, pending.code, pending.minutes_valid)
    return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    body: ResetPasswordRequest,
    client: ClientInfo = Depends(get_client_info),
    auth: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    auth.reset_password(body.email, body.code, body.new_password, client)
    return MessageResponse(message="Your password has been reset. You can now sign in.")
