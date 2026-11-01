from __future__ import annotations

from shared.api_contracts import Paths

from .client import ApiClient, Callback, Signer


class AuthApi:
    """Typed wrapper over the /api/auth endpoints."""

    def __init__(self, client: ApiClient) -> None:
        self._client = client

    def set_signer(self, signer: Signer | None) -> None:
        self._client.set_signer(signer)

    def health(self, server: str, callback: Callback) -> None:
        self._client.get(server, Paths.HEALTH, callback)

    def login(
        self, server: str, email: str, password: str, remember_me: bool, device_id: str, callback: Callback
    ) -> None:
        body = {"email": email, "password": password, "remember_me": remember_me, "device_id": device_id}
        self._client.post(server, Paths.AUTH_LOGIN, body, callback)

    def change_password(
        self, server: str, token: str, current: str, new: str, remember_me: bool, callback: Callback
    ) -> None:
        body = {"current_password": current, "new_password": new, "remember_me": remember_me}
        self._client.post(server, Paths.AUTH_CHANGE_PASSWORD, body, callback, token)

    def refresh(self, server: str, refresh_token: str, callback: Callback) -> None:
        self._client.post(server, Paths.AUTH_REFRESH, {"refresh_token": refresh_token}, callback)

    def logout(self, server: str, refresh_token: str, callback: Callback) -> None:
        self._client.post(server, Paths.AUTH_LOGOUT, {"refresh_token": refresh_token}, callback)

    def forgot_password(self, server: str, email: str, callback: Callback) -> None:
        self._client.post(server, Paths.AUTH_FORGOT_PASSWORD, {"email": email}, callback)

    def reset_password(self, server: str, email: str, code: str, new_password: str, callback: Callback) -> None:
        body = {"email": email, "code": code, "new_password": new_password}
        self._client.post(server, Paths.AUTH_RESET_PASSWORD, body, callback)
