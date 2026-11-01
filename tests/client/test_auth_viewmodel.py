import pytest
from PySide6.QtCore import QCoreApplication, QSettings

from client.api.client import ApiResult
from client.app import storage as storage_module
from client.app.storage import Storage
from client.viewmodels.auth_viewmodel import AuthViewModel

TOKENS = {
    "access_token": "access",
    "refresh_token": "refresh-1",
    "expires_in": 1800,
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

    def _answer(self, name, callback, *args):
        self.calls.append((name, *args))
        callback(self.results.get(name, ApiResult(True, 200, {})))

    def health(self, server, cb): self._answer("health", cb, server)
    def login(self, server, email, password, remember, cb): self._answer("login", cb, server, email, password, remember)
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
    return AuthViewModel(storage, api)


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
    assert api.calls[0] == ("login", "https://wewin.example.com", "admin9531@gmail.com", "pw", False)
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
