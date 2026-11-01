"""Persistent client preferences and the "Remember me" credential.

Non-secret preferences live in QSettings. The refresh token goes to the OS
keyring when one works, otherwise to the QSettings file. The password itself is
never stored.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QSettings

log = logging.getLogger("wewin.storage")

KEYRING_SERVICE = "WeWin"
DEFAULT_SERVER = "http://127.0.0.1:8000"

try:
    import keyring
except ImportError:  # pragma: no cover - optional dependency
    keyring = None


class Storage:
    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings("WeWin", "WeWin")

    # Preferences -----------------------------------------------------------
    def value(self, key: str, default: str = "") -> str:
        return str(self._settings.value(key, default))

    def set_value(self, key: str, value: str) -> None:
        self._settings.setValue(key, value)

    def remove(self, key: str) -> None:
        self._settings.remove(key)

    @property
    def server_url(self) -> str:
        return self.value("login/server", DEFAULT_SERVER)

    @server_url.setter
    def server_url(self, value: str) -> None:
        self.set_value("login/server", value)

    @property
    def email(self) -> str:
        return self.value("login/email")

    @email.setter
    def email(self, value: str) -> None:
        if value:
            self.set_value("login/email", value)
        else:
            self.remove("login/email")

    @property
    def remember_me(self) -> bool:
        return self.value("login/remember", "false") == "true"

    @remember_me.setter
    def remember_me(self, value: bool) -> None:
        self.set_value("login/remember", "true" if value else "false")

    # Refresh token -----------------------------------------------------------
    @staticmethod
    def _account(server: str, email: str) -> str:
        return f"{email}@{server}"

    def load_refresh_token(self, server: str, email: str) -> str:
        if keyring is not None:
            try:
                token = keyring.get_password(KEYRING_SERVICE, self._account(server, email))
                if token:
                    return token
            except Exception as exc:  # noqa: BLE001 - backends raise assorted errors
                log.info("Keyring unavailable (%s); using settings fallback", exc)
        return self.value("login/refresh_token")

    def save_refresh_token(self, server: str, email: str, token: str) -> None:
        if keyring is not None:
            try:
                account = self._account(server, email)
                keyring.set_password(KEYRING_SERVICE, account, token)
                # Some backends (e.g. the null keyring) accept writes but store nothing.
                if keyring.get_password(KEYRING_SERVICE, account) == token:
                    self.remove("login/refresh_token")
                    return
            except Exception as exc:  # noqa: BLE001 - backends raise assorted errors
                log.info("Keyring unavailable (%s); using settings fallback", exc)
        self.set_value("login/refresh_token", token)

    def clear_refresh_token(self, server: str, email: str) -> None:
        if keyring is not None and email:
            try:
                keyring.delete_password(KEYRING_SERVICE, self._account(server, email))
            except Exception:  # noqa: BLE001
                pass
        self.remove("login/refresh_token")
