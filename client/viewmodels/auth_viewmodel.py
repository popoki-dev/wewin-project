from __future__ import annotations

import re

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from client.api.auth_api import AuthApi
from client.api.client import ApiResult, is_insecure_remote, normalize_server_url
from client.app.storage import Storage
from shared.api_contracts import APP_ID, RESET_CODE_LENGTH

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SESSION_EXPIRED = "Your session has expired. Please sign in again."


class AuthViewModel(QObject):
    """Sign-in, "Remember me" session persistence and password reset, exposed to QML."""

    busyChanged = Signal()
    errorChanged = Signal()
    serverStatusChanged = Signal()
    sessionChanged = Signal()
    resetStateChanged = Signal()

    resetCodeSent = Signal(str)
    passwordResetDone = Signal(str)

    def __init__(self, storage: Storage, api: AuthApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._storage = storage
        self._api = api

        self._busy = False
        self._error = ""
        self._server_status = "unknown"  # unknown | checking | online | offline
        self._server_insecure = False
        self._server_check_seq = 0

        self._server = ""
        self._access_token = ""
        self._refresh_token = ""
        self._remember = False
        self._user: dict = {}

        self._reset_busy = False
        self._reset_error = ""

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_access_token)

    # ------------------------------------------------------------------ props
    @Property(str, constant=True)
    def savedServerUrl(self) -> str:
        return self._storage.server_url

    @Property(str, constant=True)
    def savedEmail(self) -> str:
        return self._storage.email if self._storage.remember_me else ""

    @Property(bool, constant=True)
    def savedRememberMe(self) -> bool:
        return self._storage.remember_me

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=errorChanged)
    def errorMessage(self) -> str:
        return self._error

    @Property(str, notify=serverStatusChanged)
    def serverStatus(self) -> str:
        return self._server_status

    @Property(bool, notify=serverStatusChanged)
    def serverInsecure(self) -> bool:
        return self._server_insecure

    @Property(bool, notify=sessionChanged)
    def loggedIn(self) -> bool:
        return bool(self._access_token)

    @Property(str, notify=sessionChanged)
    def userName(self) -> str:
        return self._user.get("full_name") or self._user.get("email", "")

    @Property(str, notify=sessionChanged)
    def userEmail(self) -> str:
        return self._user.get("email", "")

    @Property(str, notify=sessionChanged)
    def userRole(self) -> str:
        return self._user.get("role", "")

    @Property(str, notify=sessionChanged)
    def serverUrl(self) -> str:
        return self._server

    @Property(bool, notify=resetStateChanged)
    def resetBusy(self) -> bool:
        return self._reset_busy

    @Property(str, notify=resetStateChanged)
    def resetError(self) -> str:
        return self._reset_error

    def access_token(self) -> str:
        """For other view models that call authenticated endpoints."""
        return self._access_token

    # ---------------------------------------------------------------- helpers
    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()

    def _set_error(self, message: str) -> None:
        if message != self._error:
            self._error = message
            self.errorChanged.emit()

    def _set_server_status(self, status: str, insecure: bool | None = None) -> None:
        if insecure is None:
            insecure = self._server_insecure
        if status != self._server_status or insecure != self._server_insecure:
            self._server_status = status
            self._server_insecure = insecure
            self.serverStatusChanged.emit()

    def _set_reset_state(self, busy: bool, error: str = "") -> None:
        self._reset_busy = busy
        self._reset_error = error
        self.resetStateChanged.emit()

    @staticmethod
    def _validate(server: str, email: str) -> str:
        if not server:
            return "Enter a valid server address, e.g. wewin.example.com"
        if not _EMAIL_RE.match(email):
            return "Enter a valid email address."
        return ""

    def _start_session(self, server: str, data: dict, remember: bool) -> None:
        self._server = server
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._remember = remember
        self._user = data.get("user", {})

        self._storage.server_url = server
        self._storage.remember_me = remember
        email = self._user.get("email", "")
        if remember:
            self._storage.email = email
            self._storage.save_refresh_token(server, email, self._refresh_token)
        else:
            self._storage.email = ""
            self._storage.clear_refresh_token(server, email)

        # Renew the access token a minute before it expires.
        expires_in = int(data.get("expires_in", 1800))
        self._refresh_timer.start(max(30, expires_in - 60) * 1000)
        self.sessionChanged.emit()

    def _end_session(self) -> None:
        self._refresh_timer.stop()
        self._storage.clear_refresh_token(self._server, self._user.get("email", ""))
        self._access_token = ""
        self._refresh_token = ""
        self._user = {}
        self.sessionChanged.emit()

    # ------------------------------------------------------------------ slots
    @Slot(str)
    def checkServer(self, raw_server: str) -> None:
        server = normalize_server_url(raw_server)
        self._server_check_seq += 1
        seq = self._server_check_seq
        if not server:
            self._set_server_status("unknown", False)
            return
        self._set_server_status("checking", is_insecure_remote(server))

        def done(result: ApiResult) -> None:
            if seq != self._server_check_seq:
                return  # superseded by a newer check
            online = result.ok and result.data.get("app") == APP_ID
            self._set_server_status("online" if online else "offline")

        self._api.health(server, done)

    @Slot(str, str, str, bool)
    def login(self, raw_server: str, email: str, password: str, remember: bool) -> None:
        if self._busy:
            return
        server = normalize_server_url(raw_server)
        email = email.strip().lower()
        problem = self._validate(server, email) or ("" if password else "Enter your password.")
        if problem:
            self._set_error(problem)
            return

        self._set_error("")
        self._set_busy(True)

        def done(result: ApiResult) -> None:
            self._set_busy(False)
            if result.ok:
                self._set_server_status("online", is_insecure_remote(server))
                self._start_session(server, result.data, remember)
            else:
                if result.status == 0:
                    self._set_server_status("offline")
                self._set_error(result.error)

        self._api.login(server, email, password, remember, done)

    @Slot()
    def restoreSession(self) -> None:
        """Sign in silently with the stored refresh token, if "Remember me" was used."""
        if not self._storage.remember_me or self._busy:
            return
        server, email = self._storage.server_url, self._storage.email
        token = self._storage.load_refresh_token(server, email)
        if not (server and email and token):
            return

        self._set_busy(True)

        def done(result: ApiResult) -> None:
            self._set_busy(False)
            if result.ok:
                self._start_session(server, result.data, remember=True)
            elif result.status == 401:
                self._storage.clear_refresh_token(server, email)
                self._set_error(SESSION_EXPIRED)
            elif result.status == 0:
                self._set_server_status("offline")
                self._set_error(result.error)

        self._api.refresh(server, token, done)

    def _refresh_access_token(self) -> None:
        if not self._refresh_token:
            return
        server, remember = self._server, self._remember

        def done(result: ApiResult) -> None:
            if result.ok:
                self._start_session(server, result.data, remember)
            elif result.status == 0:
                self._refresh_timer.start(30_000)  # offline: retry shortly
            else:
                self._end_session()
                self._set_error(SESSION_EXPIRED)

        self._api.refresh(server, self._refresh_token, done)

    @Slot()
    def logout(self) -> None:
        if self._refresh_token:
            self._api.logout(self._server, self._refresh_token, lambda _: None)
        self._end_session()
        self._set_error("")

    @Slot()
    def clearError(self) -> None:
        self._set_error("")

    @Slot()
    def clearResetState(self) -> None:
        self._set_reset_state(False)

    @Slot(str, str)
    def requestResetCode(self, raw_server: str, email: str) -> None:
        server = normalize_server_url(raw_server)
        email = email.strip().lower()
        problem = self._validate(server, email)
        if problem:
            self._set_reset_state(False, problem)
            return
        self._set_reset_state(True)

        def done(result: ApiResult) -> None:
            if result.ok:
                self._set_reset_state(False)
                self.resetCodeSent.emit(result.data.get("message", ""))
            else:
                self._set_reset_state(False, result.error)

        self._api.forgot_password(server, email, done)

    @Slot(str, str, str, str, str)
    def resetPassword(self, raw_server: str, email: str, code: str, new_password: str, confirm: str) -> None:
        server = normalize_server_url(raw_server)
        email = email.strip().lower()
        code = code.strip()
        problem = self._validate(server, email)
        if not problem and not re.fullmatch(rf"\d{{{RESET_CODE_LENGTH}}}", code):
            problem = f"Enter the {RESET_CODE_LENGTH}-digit code from the email."
        if not problem and not new_password:
            problem = "Enter a new password."
        if not problem and new_password != confirm:
            problem = "The passwords do not match."
        if problem:
            self._set_reset_state(False, problem)
            return
        self._set_reset_state(True)

        def done(result: ApiResult) -> None:
            if result.ok:
                self._set_reset_state(False)
                self.passwordResetDone.emit(result.data.get("message", ""))
            else:
                self._set_reset_state(False, result.error)

        self._api.reset_password(server, email, code, new_password, done)
