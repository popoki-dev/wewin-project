"""Persistent client preferences and the "Remember me" credential.

Non-secret preferences live in QSettings. The refresh token and the device
secret go to the OS keyring when one works, otherwise to the QSettings file.
The password itself is never stored.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QSettings

log = logging.getLogger("wewin.storage")

KEYRING_SERVICE = "WeWin"
DEFAULT_SERVER = "http://127.0.0.1:8000"

# (keyring account prefix, settings key). The refresh token keeps its original names.
_REFRESH_TOKEN = ("", "login/refresh_token")
_DEVICE_SECRET = ("device:", "login/device_secret")

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

    # Secrets ------------------------------------------------------------------
    # The refresh token and the device secret are kept only with "Remember me".
    def load_refresh_token(self, server: str, email: str) -> str:
        return self._load_secret(_REFRESH_TOKEN, server, email)

    def save_refresh_token(self, server: str, email: str, token: str) -> None:
        self._save_secret(_REFRESH_TOKEN, server, email, token)

    def clear_refresh_token(self, server: str, email: str) -> None:
        self._clear_secret(_REFRESH_TOKEN, server, email)

    def load_device_secret(self, server: str, email: str) -> str:
        return self._load_secret(_DEVICE_SECRET, server, email)

    def save_device_secret(self, server: str, email: str, secret: str) -> None:
        self._save_secret(_DEVICE_SECRET, server, email, secret)

    def clear_device_secret(self, server: str, email: str) -> None:
        self._clear_secret(_DEVICE_SECRET, server, email)

    @staticmethod
    def _account(kind: tuple[str, str], server: str, email: str) -> str:
        return f"{kind[0]}{email}@{server}"

    def _load_secret(self, kind: tuple[str, str], server: str, email: str) -> str:
        if keyring is not None:
            try:
                value = keyring.get_password(KEYRING_SERVICE, self._account(kind, server, email))
                if value:
                    return value
            except Exception as exc:  # noqa: BLE001 - backends raise assorted errors
                log.info("Keyring unavailable (%s); using settings fallback", exc)
        return self.value(kind[1])

    def _save_secret(self, kind: tuple[str, str], server: str, email: str, value: str) -> None:
        if keyring is not None:
            try:
                account = self._account(kind, server, email)
                keyring.set_password(KEYRING_SERVICE, account, value)
                # Some backends (e.g. the null keyring) accept writes but store nothing.
                if keyring.get_password(KEYRING_SERVICE, account) == value:
                    self.remove(kind[1])
                    return
            except Exception as exc:  # noqa: BLE001 - backends raise assorted errors
                log.info("Keyring unavailable (%s); using settings fallback", exc)
        self.set_value(kind[1], value)

    def _clear_secret(self, kind: tuple[str, str], server: str, email: str) -> None:
        if keyring is not None and email:
            try:
                keyring.delete_password(KEYRING_SERVICE, self._account(kind, server, email))
            except Exception:  # noqa: BLE001
                pass
        self.remove(kind[1])
