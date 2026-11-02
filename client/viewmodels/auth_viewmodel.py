from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from client.api.auth_api import AuthApi
from client.api.client import ApiResult, is_insecure_remote, normalize_server_url
from client.app import device
from client.app.storage import Storage
from shared.api_contracts import APP_ID, RESET_CODE_LENGTH
from shared.device_signature import signed_headers

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SESSION_EXPIRED = "Your session has expired. Please sign in again."
SERVER_POLL_MS = 5_000
# While signed in, this many failed server checks in a row (one every SERVER_POLL_MS)
# end the session; one dropped request alone does not.
MAX_MISSED_HEARTBEATS = 2
CONNECTION_LOST = "Lost connection to the server, so you were signed out. Sign in again once it is reachable."
CONNECTION_LOST_RESUMING = (
    "Lost connection to the server, so you were signed out. "
    "You will be signed back in automatically once it is reachable."
)


class AuthViewModel(QObject):
    """Sign-in, "Remember me" session persistence, device signing and password changes, exposed to QML."""

    busyChanged = Signal()
    errorChanged = Signal()
    serverStatusChanged = Signal()
    sessionChanged = Signal()
    resetStateChanged = Signal()

    resetCodeSent = Signal(str)
    passwordResetDone = Signal(str)
    passwordChanged = Signal()

    def __init__(
        self,
        storage: Storage,
        api: AuthApi,
        parent: QObject | None = None,
        device_id: Callable[[], str] = device.device_id,
    ) -> None:
        super().__init__(parent)
        self._storage = storage
        self._api = api
        self._device_id_source = device_id
        self._device_id = ""
        self._device_secret = ""

        self._busy = False
        self._error = ""
        self._error_is_connection = False
        self._error_fields: list[str] = []
        self._server_status = "unknown"  # unknown | checking | online | offline
        self._server_insecure = False
        self._server_check_seq = 0
        self._checked_server = ""
        self._probe_pending = False
        self._heartbeat_pending = False
        self._missed_heartbeats = 0
        # After a lost connection with "Remember me": sign back in once the server answers.
        self._resume_when_online = False

        self._server = ""
        self._access_token = ""
        self._refresh_token = ""
        self._remember = False
        self._user: dict = {}

        self._reset_busy = False
        self._reset_error = ""
        self._reset_error_fields: list[str] = []

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_access_token)

        # Keeps the sign-in page's server status current after the first check, and
        # while signed in, checks the connection so a lost server ends the session.
        self._server_poll = QTimer(self)
        self._server_poll.setInterval(SERVER_POLL_MS)
        self._server_poll.timeout.connect(self._poll_server)

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

    @Property("QStringList", notify=errorChanged)
    def errorFields(self) -> list[str]:
        """The inputs the current error is about; editing one of them clears it."""
        return self._error_fields

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

    @Property(bool, notify=sessionChanged)
    def mustChangePassword(self) -> bool:
        """True after signing in with an initial password; the app stays locked until it is changed."""
        return bool(self._user.get("must_change_password"))

    @Property(bool, notify=sessionChanged)
    def isOwner(self) -> bool:
        return self._user.get("role") == "owner"

    @Property("QStringList", notify=sessionChanged)
    def permissions(self) -> list[str]:
        """Effective permissions (base role plus role bundles), as sent by the server."""
        return list(self._user.get("permissions", []))

    def has(self, permission: str) -> bool:
        return permission in self._user.get("permissions", [])

    @Property(bool, notify=sessionChanged)
    def canManageMembers(self) -> bool:
        return self.has("members.view")

    @Property(bool, notify=sessionChanged)
    def canViewTeams(self) -> bool:
        """The Teams tab: for anyone who manages members or teams."""
        return self.has("members.view") or self.has("teams.create") or self.has("teams.rename")

    @Property(int, notify=sessionChanged)
    def userTeamId(self) -> int:
        return self._user.get("team_id") or 0

    @Property("QVariantList", notify=sessionChanged)
    def scopeTeamIds(self) -> list[int]:
        """The teams this user acts on: those a Team Leader leads, or a member's own team."""
        if self._user.get("role") == "team_leader":
            return list(self._user.get("led_team_ids", []))
        return [self._user["team_id"]] if self._user.get("team_id") else []

    @Property(bool, notify=resetStateChanged)
    def resetBusy(self) -> bool:
        return self._reset_busy

    @Property(str, notify=resetStateChanged)
    def resetError(self) -> str:
        return self._reset_error

    @Property("QStringList", notify=resetStateChanged)
    def resetErrorFields(self) -> list[str]:
        return self._reset_error_fields

    def access_token(self) -> str:
        """For other view models that call authenticated endpoints."""
        return self._access_token

    def _get_device_id(self) -> str:
        if not self._device_id:
            self._device_id = self._device_id_source()
        return self._device_id

    def _use_device_secret(self, secret: str, email: str) -> None:
        """Sign every later request with this PC's device secret (or stop, for "")."""
        self._device_secret = secret
        if not secret:
            self._api.set_signer(None)
            return
        device_id = self._get_device_id()
        self._api.set_signer(lambda method, path: signed_headers(secret, device_id, email, method, path))

    # ---------------------------------------------------------------- helpers
    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()

    def _set_error(self, message: str, *, fields: list[str] | None = None, connection: bool = False) -> None:
        # Connection errors clear themselves once the server is reachable again.
        self._error_is_connection = connection and bool(message)
        fields = (fields or []) if message else []
        if message != self._error or fields != self._error_fields:
            self._error = message
            self._error_fields = fields
            self.errorChanged.emit()

    def _set_server_status(self, status: str, insecure: bool | None = None) -> None:
        if insecure is None:
            insecure = self._server_insecure
        if status != self._server_status or insecure != self._server_insecure:
            self._server_status = status
            self._server_insecure = insecure
            self.serverStatusChanged.emit()

    def _set_reset_state(self, busy: bool, error: str = "", fields: list[str] | None = None) -> None:
        self._reset_busy = busy
        self._reset_error = error
        self._reset_error_fields = (fields or []) if error else []
        self.resetStateChanged.emit()

    @staticmethod
    def _validate(server: str, email: str) -> tuple[str, str]:
        """Return (message, field) for the first invalid input, or ("", "")."""
        if not server:
            return "Enter a valid server address, e.g. wewin.example.com", "server"
        if not _EMAIL_RE.match(email):
            return "Enter a valid email address.", "email"
        return "", ""

    def _start_session(self, server: str, data: dict, remember: bool) -> None:
        self._server = server
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._remember = remember
        self._user = data.get("user", {})
        email = self._user.get("email", "")
        # Sign-in issues a new device secret; refreshes and password changes keep the current one.
        self._use_device_secret(data.get("device_secret") or self._device_secret, email)

        self._storage.server_url = server
        self._storage.remember_me = remember
        if remember:
            self._storage.email = email
            self._storage.save_refresh_token(server, email, self._refresh_token)
            self._storage.save_device_secret(server, email, self._device_secret)
        else:
            self._storage.email = ""
            self._storage.clear_refresh_token(server, email)
            self._storage.clear_device_secret(server, email)

        # Renew the access token a minute before it expires.
        expires_in = int(data.get("expires_in", 1800))
        self._refresh_timer.start(max(30, expires_in - 60) * 1000)
        self._missed_heartbeats = 0
        if not self._server_poll.isActive():
            self._server_poll.start()
        self.sessionChanged.emit()

    def _end_session(self, keep_stored: bool = False) -> None:
        """Forget the session. `keep_stored` leaves "Remember me" credentials on disk."""
        self._refresh_timer.stop()
        self._missed_heartbeats = 0
        if not keep_stored:
            self._resume_when_online = False
            email = self._user.get("email", "")
            self._storage.clear_refresh_token(self._server, email)
            self._storage.clear_device_secret(self._server, email)
        self._use_device_secret("", "")
        self._access_token = ""
        self._refresh_token = ""
        self._user = {}
        self.sessionChanged.emit()

    # ------------------------------------------------------------------ slots
    @Slot(str)
    def checkServer(self, raw_server: str) -> None:
        server = normalize_server_url(raw_server)
        self._server_check_seq += 1
        self._checked_server = server
        if not server:
            self._server_poll.stop()
            self._set_server_status("unknown", False)
            return
        self._set_server_status("checking", is_insecure_remote(server))
        self._probe_server()
        self._server_poll.start()

    def _poll_server(self) -> None:
        if self._access_token:
            self._heartbeat()
            return
        # Re-check quietly (no "checking" state) while the sign-in page is shown,
        # and never stack requests behind a server that is slow to answer.
        if self._probe_pending or not self._checked_server:
            return
        self._probe_server()

    def _heartbeat(self) -> None:
        """While signed in: sign out after MAX_MISSED_HEARTBEATS failed checks in a row."""
        if self._heartbeat_pending:
            return
        self._heartbeat_pending = True
        server, token = self._server, self._access_token

        def done(result: ApiResult) -> None:
            self._heartbeat_pending = False
            if token != self._access_token or server != self._server:
                return  # signed out, or the session moved on, meanwhile
            if result.ok and result.data.get("app") == APP_ID:
                self._missed_heartbeats = 0
                self._set_server_status("online")
                return
            self._missed_heartbeats += 1
            if self._missed_heartbeats >= MAX_MISSED_HEARTBEATS:
                self._lose_connection()

        self._api.health(server, done)

    def _lose_connection(self) -> None:
        """End the session locally; the server cannot be told, but its tokens expire on their own.

        With "Remember me" the stored credentials are kept, and the sign-in page's server
        check signs the user back in as soon as the server answers again.
        """
        resume = self._remember
        server = self._server
        self._end_session(keep_stored=resume)
        self._resume_when_online = resume
        # Keep checking the server the session was on.
        self._server_check_seq += 1
        self._checked_server = server
        self._probe_pending = False
        if not self._server_poll.isActive():
            self._server_poll.start()
        self._set_server_status("offline")
        # Not a "connection" error: it explains why the user is back on the sign-in page,
        # so it stays until they sign in again rather than vanishing when the server returns.
        self._set_error(CONNECTION_LOST_RESUMING if resume else CONNECTION_LOST)

    def _probe_server(self) -> None:
        seq = self._server_check_seq
        self._probe_pending = True

        def done(result: ApiResult) -> None:
            if seq != self._server_check_seq:
                return  # superseded by a newer check
            self._probe_pending = False
            online = result.ok and result.data.get("app") == APP_ID
            self._set_server_status("online" if online else "offline")
            if online and self._error_is_connection:
                self._set_error("")
            if online and self._resume_when_online and not self._access_token and not self._busy:
                self._resume_from_storage(after_lost_connection=True)

        self._api.health(self._checked_server, done)

    @Slot(str, str, str, bool)
    def login(self, raw_server: str, email: str, password: str, remember: bool) -> None:
        if self._busy:
            return
        server = normalize_server_url(raw_server)
        email = email.strip().lower()
        problem, field = self._validate(server, email)
        if not problem and not password:
            problem, field = "Enter your password.", "password"
        if problem:
            self._set_error(problem, fields=[field])
            return

        self._set_error("")
        self._resume_when_online = False
        self._set_busy(True)

        def done(result: ApiResult) -> None:
            self._set_busy(False)
            if result.ok:
                self._set_server_status("online", is_insecure_remote(server))
                self._start_session(server, result.data, remember)
            else:
                if result.status == 0:
                    self._set_server_status("offline")
                # Wrong credentials are fixed by editing either field; a lockout is not.
                fields = ["email", "password"] if result.status == 401 else []
                self._set_error(result.error, fields=fields, connection=result.status == 0)

        self._api.login(server, email, password, remember, self._get_device_id(), done)

    @Slot()
    def restoreSession(self) -> None:
        """Sign in silently with the stored refresh token, if "Remember me" was used."""
        self._resume_from_storage(after_lost_connection=False)

    def _resume_from_storage(self, after_lost_connection: bool) -> None:
        self._resume_when_online = False
        if not self._storage.remember_me or self._busy or self._access_token:
            return
        server, email = self._storage.server_url, self._storage.email
        token = self._storage.load_refresh_token(server, email)
        secret = self._storage.load_device_secret(server, email)
        if not (server and email and token and secret):
            return

        self._set_busy(True)
        self._use_device_secret(secret, email)

        def done(result: ApiResult) -> None:
            self._set_busy(False)
            if result.ok:
                self._start_session(server, result.data, remember=True)
                if after_lost_connection:
                    self._set_error("")
                return
            self._use_device_secret("", "")
            if result.status == 401:
                self._storage.clear_refresh_token(server, email)
                self._storage.clear_device_secret(server, email)
                self._set_error(SESSION_EXPIRED)
            elif result.status == 0 or result.status >= 500:
                self._set_server_status("offline")
                if after_lost_connection:
                    self._resume_when_online = True  # try again at the next successful check
                else:
                    self._set_error(result.error, connection=True)

        self._api.refresh(server, token, done)

    def _refresh_access_token(self) -> None:
        if not self._refresh_token:
            return
        server, remember = self._server, self._remember

        def done(result: ApiResult) -> None:
            if result.ok:
                self._start_session(server, result.data, remember)
            elif result.status == 0:
                self._lose_connection()
            else:
                self._end_session()
                self._set_error(SESSION_EXPIRED)

        self._api.refresh(server, self._refresh_token, done)

    @Slot(str, str, str)
    def changePassword(self, current: str, new_password: str, confirm: str) -> None:
        if self._busy or not self._access_token:
            return
        problem, fields = "", []
        if not current:
            problem, fields = "Enter your current password.", ["current"]
        elif not new_password:
            problem, fields = "Enter a new password.", ["newPassword"]
        elif new_password != confirm:
            problem, fields = "The passwords do not match.", ["newPassword", "confirm"]
        if problem:
            self._set_error(problem, fields=fields)
            return

        self._set_error("")
        self._set_busy(True)
        server, remember = self._server, self._remember

        def done(result: ApiResult) -> None:
            self._set_busy(False)
            if result.ok:
                self._start_session(server, result.data, remember)
                self.passwordChanged.emit()
            else:
                # 400: wrong current password; 422: the new one breaks the policy.
                fields = {400: ["current"], 422: ["newPassword"]}.get(result.status, [])
                self._set_error(result.error, fields=fields, connection=result.status == 0)

        self._api.change_password(server, self._access_token, current, new_password, remember, done)

    def sign_out_with_message(self, message: str) -> None:
        """Sign out and leave `message` on the sign-in page (e.g. after an email change)."""
        self.logout()
        self._set_error(message)

    @Slot()
    def logout(self) -> None:
        if self._refresh_token:
            self._api.logout(self._server, self._refresh_token, lambda _: None)
        self._end_session()
        self._set_error("")

    @Slot()
    def clearError(self) -> None:
        self._set_error("")

    @Slot(str)
    def fieldEdited(self, field: str) -> None:
        if field in self._error_fields:
            self._set_error("")

    @Slot(str)
    def resetFieldEdited(self, field: str) -> None:
        if field in self._reset_error_fields:
            self._set_reset_state(self._reset_busy)

    @Slot()
    def clearResetState(self) -> None:
        self._set_reset_state(False)

    @Slot(str, str)
    def requestResetCode(self, raw_server: str, email: str) -> None:
        server = normalize_server_url(raw_server)
        email = email.strip().lower()
        problem, field = self._validate(server, email)
        if problem:
            self._set_reset_state(False, problem, [field])
            return
        self._set_reset_state(True)

        def done(result: ApiResult) -> None:
            if result.ok:
                self._set_reset_state(False)
                self.resetCodeSent.emit(result.data.get("message", ""))
            else:
                self._set_reset_state(False, result.error, ["email"] if result.status == 422 else [])

        self._api.forgot_password(server, email, done)

    @Slot(str, str, str, str, str)
    def resetPassword(self, raw_server: str, email: str, code: str, new_password: str, confirm: str) -> None:
        server = normalize_server_url(raw_server)
        email = email.strip().lower()
        code = code.strip()
        problem, field = self._validate(server, email)
        fields = [field]
        if not problem and not re.fullmatch(rf"\d{{{RESET_CODE_LENGTH}}}", code):
            problem, fields = f"Enter the {RESET_CODE_LENGTH}-digit code from the email.", ["code"]
        if not problem and not new_password:
            problem, fields = "Enter a new password.", ["newPassword"]
        if not problem and new_password != confirm:
            problem, fields = "The passwords do not match.", ["newPassword", "confirm"]
        if problem:
            self._set_reset_state(False, problem, fields)
            return
        self._set_reset_state(True)

        def done(result: ApiResult) -> None:
            if result.ok:
                self._set_reset_state(False)
                self.passwordResetDone.emit(result.data.get("message", ""))
            else:
                # 400: wrong or expired code; 422: the new password breaks the policy.
                fields = {400: ["code"], 422: ["newPassword"]}.get(result.status, [])
                self._set_reset_state(False, result.error, fields)

        self._api.reset_password(server, email, code, new_password, done)
