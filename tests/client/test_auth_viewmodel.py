import pytest
from PySide6.QtCore import QCoreApplication, QSettings

from client.api.client import ApiResult
from client.app import storage as storage_module
from client.app.storage import Storage
from client.viewmodels.auth_viewmodel import AuthViewModel
from shared import device_signature as ds

DEVICE_ID = ds.device_id_from_mac("02:00:00:00:00:0A")
TOKENS = {
    "access_token": "access",
    "refresh_token": "refresh-1",
    "expires_in": 1800,
    "device_secret": "secret-1",
    "user": {"email": "admin9531@gmail.com", "full_name": "Owner", "role": "owner"},
}


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


class FakeAuthApi:
    """Answers immediately with canned results and records calls."""

    def __init__(self):
        self.calls = []
        self.results = {}
        self.signer = None

    def set_signer(self, signer): self.signer = signer

    def _answer(self, name, callback, *args):
        self.calls.append((name, *args))
        callback(self.results.get(name, ApiResult(True, 200, {})))

    def health(self, server, cb): self._answer("health", cb, server)
    def login(self, server, email, password, remember, device_id, cb):
        self._answer("login", cb, server, email, password, remember, device_id)

    def change_password(self, server, token, current, new, remember, cb):
        self._answer("change_password", cb, server, token, current, new, remember)

    def refresh(self, server, token, cb): self._answer("refresh", cb, server, token)
    def logout(self, server, token, cb): self._answer("logout", cb, server, token)
    def forgot_password(self, server, email, cb): self._answer("forgot_password", cb, server, email)
    def reset_password(self, server, email, code, pw, cb): self._answer("reset_password", cb, server, email, code, pw)


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "keyring", None)  # exercise the settings-file path
    return Storage(QSettings(str(tmp_path / "wewin.ini"), QSettings.Format.IniFormat))


@pytest.fixture()
def api():
    return FakeAuthApi()


def make_vm(storage, api):
    return AuthViewModel(storage, api, device_id=lambda: DEVICE_ID)


def test_login_validates_before_calling_server(storage, api):
    vm = make_vm(storage, api)
    vm.login("", "a@b.co", "pw", False)
    assert "server address" in vm.errorMessage
    vm.login("localhost:8000", "not-an-email", "pw", False)
    assert vm.errorMessage == "Enter a valid email address."
    vm.login("localhost:8000", "a@b.co", "", False)
    assert vm.errorMessage == "Enter your password."
    assert api.calls == []


def test_login_normalizes_input(storage, api):
    api.results["login"] = ApiResult(True, 200, TOKENS)
    vm = make_vm(storage, api)
    vm.login("wewin.example.com", "  Admin9531@Gmail.com ", "pw", False)
    assert api.calls[0] == ("login", "https://wewin.example.com", "admin9531@gmail.com", "pw", False, DEVICE_ID)
    assert vm.loggedIn and vm.userRole == "owner"


def test_remember_me_persists_session_and_restores_it(storage, api):
    api.results["login"] = ApiResult(True, 200, TOKENS)
    make_vm(storage, api).login("localhost:8000", "admin9531@gmail.com", "pw", True)
    assert storage.remember_me and storage.email == "admin9531@gmail.com"
    assert storage.load_refresh_token("http://localhost:8000", "admin9531@gmail.com") == "refresh-1"

    # A new app start signs in with the stored refresh token.
    api.results["refresh"] = ApiResult(True, 200, {**TOKENS, "refresh_token": "refresh-2"})
    restored = make_vm(storage, api)
    restored.restoreSession()
    assert restored.loggedIn
    assert api.calls[-1] == ("refresh", "http://localhost:8000", "refresh-1")
    assert storage.load_refresh_token("http://localhost:8000", "admin9531@gmail.com") == "refresh-2"


def test_without_remember_me_nothing_secret_is_kept(storage, api):
    api.results["login"] = ApiResult(True, 200, TOKENS)
    make_vm(storage, api).login("localhost:8000", "admin9531@gmail.com", "pw", False)
    assert not storage.remember_me and storage.email == ""
    assert storage.load_refresh_token("http://localhost:8000", "admin9531@gmail.com") == ""


def test_expired_stored_session_shows_message(storage, api):
    storage.remember_me = True
    storage.email = "admin9531@gmail.com"
    storage.save_refresh_token(storage.server_url, storage.email, "stale")
    storage.save_device_secret(storage.server_url, storage.email, "secret-1")
    api.results["refresh"] = ApiResult(False, 401, {}, "Session expired.")
    vm = make_vm(storage, api)
    vm.restoreSession()
    assert not vm.loggedIn and "expired" in vm.errorMessage
    assert storage.load_refresh_token(storage.server_url, storage.email) == ""


def test_logout_revokes_and_forgets_token(storage, api):
    api.results["login"] = ApiResult(True, 200, TOKENS)
    vm = make_vm(storage, api)
    vm.login("localhost:8000", "admin9531@gmail.com", "pw", True)
    vm.logout()
    assert not vm.loggedIn
    assert ("logout", "http://localhost:8000", "refresh-1") in api.calls
    assert storage.load_refresh_token("http://localhost:8000", "admin9531@gmail.com") == ""


def test_reset_password_validates_locally(storage, api):
    vm = make_vm(storage, api)
    vm.resetPassword("localhost:8000", "a@b.co", "12", "Pw-123456", "Pw-123456")
    assert vm.resetError == "Enter the 6-digit code from the email."
    vm.resetPassword("localhost:8000", "a@b.co", "123456", "Pw-123456", "different")
    assert vm.resetError == "The passwords do not match."
    assert api.calls == []


def test_insecure_remote_server_is_flagged(storage, api):
    api.results["health"] = ApiResult(True, 200, {"app": "WeWin"})
    vm = make_vm(storage, api)
    vm.checkServer("http://wewin.example.com")
    assert vm.serverStatus == "online" and vm.serverInsecure
    vm.checkServer("wewin.example.com")
    assert not vm.serverInsecure


def test_server_status_follows_the_server_going_down_and_up(storage, api):
    api.results["health"] = ApiResult(True, 200, {"app": "WeWin"})
    vm = make_vm(storage, api)
    vm.checkServer("localhost:8000")
    assert vm.serverStatus == "online"

    api.results["health"] = ApiResult(False, 0, {}, "Could not reach the server.")
    vm._poll_server()
    assert vm.serverStatus == "offline"

    api.results["health"] = ApiResult(True, 200, {"app": "WeWin"})
    vm._poll_server()
    assert vm.serverStatus == "online"
    assert api.calls[-1] == ("health", "http://localhost:8000")


def test_connection_error_clears_when_server_is_back(storage, api):
    api.results["login"] = ApiResult(False, 0, {}, "Could not reach the server.")
    vm = make_vm(storage, api)
    vm.login("localhost:8000", "admin9531@gmail.com", "pw", False)
    assert vm.errorMessage == "Could not reach the server."

    api.results["health"] = ApiResult(True, 200, {"app": "WeWin"})
    vm.checkServer("localhost:8000")
    assert vm.serverStatus == "online" and vm.errorMessage == ""


def test_other_errors_stay_when_server_is_back(storage, api):
    api.results["login"] = ApiResult(False, 401, {}, "Invalid email or password.")
    api.results["health"] = ApiResult(True, 200, {"app": "WeWin"})
    vm = make_vm(storage, api)
    vm.login("localhost:8000", "admin9531@gmail.com", "pw", False)
    vm.checkServer("localhost:8000")
    assert vm.errorMessage == "Invalid email or password."


def test_input_error_clears_when_its_field_is_edited(storage, api):
    vm = make_vm(storage, api)
    vm.login("localhost:8000", "a@b.co", "", False)
    assert vm.errorMessage == "Enter your password." and vm.errorFields == ["password"]
    vm.fieldEdited("email")
    assert vm.errorMessage == "Enter your password."
    vm.fieldEdited("password")
    assert vm.errorMessage == "" and vm.errorFields == []


def test_wrong_credentials_clear_when_email_or_password_is_edited(storage, api):
    api.results["login"] = ApiResult(False, 401, {}, "Invalid email or password.")
    vm = make_vm(storage, api)
    vm.login("localhost:8000", "admin9531@gmail.com", "pw", False)
    vm.fieldEdited("server")
    assert vm.errorMessage == "Invalid email or password."
    vm.fieldEdited("email")
    assert vm.errorMessage == ""


def test_lockout_message_is_not_cleared_by_typing(storage, api):
    api.results["login"] = ApiResult(False, 429, {}, "Too many failed attempts.")
    vm = make_vm(storage, api)
    vm.login("localhost:8000", "admin9531@gmail.com", "pw", False)
    vm.fieldEdited("password")
    assert vm.errorMessage == "Too many failed attempts."


def test_reset_errors_clear_when_their_field_is_edited(storage, api):
    vm = make_vm(storage, api)
    vm.resetPassword("localhost:8000", "a@b.co", "123456", "Pw-123456", "different")
    assert vm.resetErrorFields == ["newPassword", "confirm"]
    vm.resetFieldEdited("code")
    assert vm.resetError == "The passwords do not match."
    vm.resetFieldEdited("confirm")
    assert vm.resetError == ""

    api.results["reset_password"] = ApiResult(False, 400, {}, "The reset code is invalid or has expired.")
    vm.resetPassword("localhost:8000", "a@b.co", "123456", "Pw-123456", "Pw-123456")
    assert vm.resetErrorFields == ["code"]
    vm.resetFieldEdited("code")
    assert vm.resetError == ""


def test_server_is_not_polled_while_signed_in(storage, api):
    api.results["login"] = ApiResult(True, 200, TOKENS)
    vm = make_vm(storage, api)
    vm.checkServer("localhost:8000")
    vm.login("localhost:8000", "admin9531@gmail.com", "pw", False)
    calls = len(api.calls)
    vm._poll_server()
    assert len(api.calls) == calls


def test_signed_in_requests_are_signed_with_the_device_secret(storage, api):
    api.results["login"] = ApiResult(True, 200, TOKENS)
    vm = make_vm(storage, api)
    vm.login("localhost:8000", "admin9531@gmail.com", "pw", False)
    headers = api.signer("GET", "/api/teams")
    assert headers[ds.DEVICE_HEADER] == DEVICE_ID
    expected = ds.sign("secret-1", DEVICE_ID, "admin9531@gmail.com", headers[ds.TIMESTAMP_HEADER],
                       headers[ds.NONCE_HEADER], "GET", "/api/teams")
    assert headers[ds.SIGNATURE_HEADER] == expected
    vm.logout()
    assert api.signer is None


def test_device_secret_is_kept_only_with_remember_me(storage, api):
    api.results["login"] = ApiResult(True, 200, TOKENS)
    make_vm(storage, api).login("localhost:8000", "admin9531@gmail.com", "pw", False)
    assert storage.load_device_secret("http://localhost:8000", "admin9531@gmail.com") == ""
    make_vm(storage, api).login("localhost:8000", "admin9531@gmail.com", "pw", True)
    assert storage.load_device_secret("http://localhost:8000", "admin9531@gmail.com") == "secret-1"


def test_restore_signs_the_refresh_and_keeps_the_secret(storage, api):
    api.results["login"] = ApiResult(True, 200, TOKENS)
    make_vm(storage, api).login("localhost:8000", "admin9531@gmail.com", "pw", True)
    refreshed = {**TOKENS, "refresh_token": "refresh-2", "device_secret": None}
    api.results["refresh"] = ApiResult(True, 200, refreshed)
    restored = make_vm(storage, api)
    restored.restoreSession()
    assert restored.loggedIn and api.signer is not None
    assert storage.load_device_secret("http://localhost:8000", "admin9531@gmail.com") == "secret-1"


def test_restore_without_device_secret_asks_for_sign_in(storage, api):
    storage.remember_me = True
    storage.email = "admin9531@gmail.com"
    storage.save_refresh_token(storage.server_url, storage.email, "refresh-1")
    vm = make_vm(storage, api)
    vm.restoreSession()
    assert not vm.loggedIn and api.calls == []


def test_initial_password_must_be_changed(storage, api):
    first = {**TOKENS, "user": {**TOKENS["user"], "role": "member", "must_change_password": True}}
    api.results["login"] = ApiResult(True, 200, first)
    vm = make_vm(storage, api)
    vm.login("localhost:8000", "admin9531@gmail.com", "Initial-1", False)
    assert vm.loggedIn and vm.mustChangePassword

    vm.changePassword("Initial-1", "New-pass-1", "other")
    assert vm.errorFields == ["newPassword", "confirm"]
    vm.fieldEdited("confirm")

    api.results["change_password"] = ApiResult(False, 400, {}, "Your current password is incorrect.")
    vm.changePassword("wrong", "New-pass-1", "New-pass-1")
    assert vm.errorFields == ["current"]

    changed = {**first, "access_token": "access-2", "device_secret": None,
               "user": {**first["user"], "must_change_password": False}}
    api.results["change_password"] = ApiResult(True, 200, changed)
    vm.changePassword("Initial-1", "New-pass-1", "New-pass-1")
    assert not vm.mustChangePassword and vm.errorMessage == ""
    assert api.calls[-1] == ("change_password", "http://localhost:8000", "access", "Initial-1", "New-pass-1", False)
    assert api.signer("GET", "/x")[ds.DEVICE_HEADER] == DEVICE_ID  # still signing with secret-1
