import pytest
from PySide6.QtCore import QCoreApplication, QSettings

from client.api.client import ApiResult
from client.app import storage as storage_module
from client.app.storage import Storage
from client.viewmodels.auth_viewmodel import AuthViewModel
from client.viewmodels.members_viewmodel import MembersViewModel
from tests.client.test_auth_viewmodel import DEVICE_ID, TOKENS, FakeAuthApi


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


class FakeMembersApi:
    def __init__(self):
        self.calls = []
        self.results = {}

    def _answer(self, name, cb, *args):
        self.calls.append((name, *args))
        cb(self.results.get(name, ApiResult(True, 200, {"items": []})))

    def list_teams(self, server, token, cb): self._answer("list_teams", cb)
    def create_team(self, server, token, name, cb): self._answer("create_team", cb, name)
    def list_members(self, server, token, cb): self._answer("list_members", cb)
    def add_member(self, server, token, body, cb): self._answer("add_member", cb, body)
    def reset_device(self, server, token, user_id, cb): self._answer("reset_device", cb, user_id)
    def rename_team(self, server, token, team_id, name, cb): self._answer("rename_team", cb, team_id, name)
    def update_member(self, server, token, user_id, body, cb): self._answer("update_member", cb, user_id, body)
    def list_bundles(self, server, token, cb): self._answer("list_bundles", cb)
    def create_bundle(self, server, token, body, cb): self._answer("create_bundle", cb, body)
    def update_bundle(self, server, token, bundle_id, body, cb): self._answer("update_bundle", cb, bundle_id, body)
    def delete_bundle(self, server, token, bundle_id, cb): self._answer("delete_bundle", cb, bundle_id)
    def delete_member(self, server, token, user_id, cb): self._answer("delete_member", cb, user_id)
    def delete_team(self, server, token, team_id, cb): self._answer("delete_team", cb, team_id)


ROLE_PERMISSIONS = {
    "owner": ["members.add", "members.assign_roles", "members.reset_device", "members.view", "teams.create"],
    "team_leader": ["members.add", "members.assign_roles", "members.delete", "members.edit", "members.reset_device",
                    "members.view", "revenue.view"],
    "member": ["projects.view"],
}


def signed_in(tmp_path, monkeypatch, role):
    monkeypatch.setattr(storage_module, "keyring", None)
    storage = Storage(QSettings(str(tmp_path / "wewin.ini"), QSettings.Format.IniFormat))
    auth_api = FakeAuthApi()
    auth_api.results["login"] = ApiResult(True, 200, {**TOKENS, "user": {**TOKENS["user"], "role": role, "team_id": 7,
                                                                         "permissions": ROLE_PERMISSIONS[role]}})
    auth = AuthViewModel(storage, auth_api, device_id=lambda: DEVICE_ID)
    auth.login("localhost:8000", "admin9531@gmail.com", "pw", False)
    api = FakeMembersApi()
    return MembersViewModel(auth, api), api


def test_add_member_validates_email_team_and_password(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "owner")
    vm.addMember("nope", "", 1, "member", "Pass-word-1", [])
    assert vm.errorFields == ["email"]
    vm.fieldEdited("email")
    assert vm.errorMessage == ""
    vm.addMember("a@b.co", "", 0, "member", "Pass-word-1", [])
    assert vm.errorFields == ["team"]
    vm.addMember("a@b.co", "", 1, "member", "", [])
    assert vm.errorFields == ["password"]
    assert api.calls == []


def test_team_leader_always_adds_plain_members(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "team_leader")
    api.results["add_member"] = ApiResult(True, 201, {"email": "a@b.co"})
    vm.addMember(" A@B.co ", "Ann", 7, "team_leader", "Pass-word-1", [3])
    body = api.calls[0][1]
    assert body["role"] == "member" and body["email"] == "a@b.co" and body["role_bundle_ids"] == [3]
    assert "initial password" in vm.notice


def test_server_errors_point_at_their_field(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "owner")
    api.results["add_member"] = ApiResult(False, 409, {}, "An account with this email already exists.")
    vm.addMember("a@b.co", "", 1, "member", "Pass-word-1", [])
    assert vm.errorFields == ["email"]


def test_refresh_loads_teams_then_members(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "owner")
    api.results["list_teams"] = ApiResult(True, 200, {"items": [{"id": 1, "name": "Sales", "member_count": 0}]})
    api.results["list_members"] = ApiResult(True, 200, {"items": [{"id": 2, "email": "a@b.co"}]})
    vm.refresh()
    assert [t["name"] for t in vm.teams] == ["Sales"] and vm.members[0]["email"] == "a@b.co"


def test_members_are_not_loaded_for_plain_members(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "member")
    vm.refresh()
    assert [c[0] for c in api.calls] == ["list_teams"]


BUNDLES = [
    {"id": 1, "name": "Reports", "permissions": ["revenue.view"]},
    {"id": 2, "name": "Team admin", "permissions": ["teams.create"]},
]


def load(vm, api):
    api.results["list_bundles"] = ApiResult(True, 200, {"items": BUNDLES})
    vm.refresh()


def test_team_leader_may_assign_only_bundles_within_own_permissions(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "team_leader")
    load(vm, api)
    assert vm.assignableBundleIds == [1]


def test_owner_may_assign_every_bundle(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "owner")
    load(vm, api)
    assert vm.assignableBundleIds == [1, 2]


def test_who_can_edit_whose_roles(tmp_path, monkeypatch):
    leader, _ = signed_in(tmp_path, monkeypatch, "team_leader")
    mine = {"role": "member", "team_id": 7, "email": "m@b.co"}
    assert leader.canEditRoles(mine)
    assert not leader.canEditRoles({**mine, "team_id": 8})
    assert not leader.canEditRoles({**mine, "role": "team_leader"})
    assert not leader.canEditRoles({**mine, "email": "admin9531@gmail.com"})  # themselves
    assert not leader.canEditRoles({"role": "owner"})


def test_bundle_form_validation_and_save(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "owner")
    vm.createBundle("  ", "", ["revenue.view"])
    assert vm.errorFields == ["bundleName"]
    vm.createBundle("Reports", "", [])
    assert vm.errorFields == ["bundlePermissions"]
    assert api.calls == []

    saved = []
    vm.bundleSaved.connect(lambda: saved.append(True))
    api.results["create_bundle"] = ApiResult(True, 201, {"id": 1, "name": "Reports"})
    vm.createBundle(" Reports ", " Read-only ", ["revenue.view"])
    assert api.calls[0] == ("create_bundle", {"name": "Reports", "description": "Read-only", "permissions": ["revenue.view"]})
    assert saved and "Reports" in vm.notice


def test_saving_member_roles_sends_base_role_only_for_the_owner(tmp_path, monkeypatch):
    owner, api = signed_in(tmp_path, monkeypatch, "owner")
    api.results["update_member"] = ApiResult(True, 200, {"email": "m@b.co"})
    owner.saveMemberRoles(5, "team_leader", [1, 2])
    assert api.calls[0] == ("update_member", 5, {"role_bundle_ids": [1, 2], "role": "team_leader"})

    leader, api = signed_in(tmp_path, monkeypatch, "team_leader")
    api.results["update_member"] = ApiResult(True, 200, {"email": "m@b.co"})
    leader.saveMemberRoles(5, "team_leader", [1])
    assert api.calls[0] == ("update_member", 5, {"role_bundle_ids": [1]})


SAM = {"id": 5, "email": "sam@b.co", "full_name": "Sam", "role": "member", "team_id": 7, "is_active": True}


def test_save_member_sends_only_changes(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "owner")
    api.results["update_member"] = ApiResult(True, 200, {**SAM, "full_name": "Samuel"})
    vm.saveMember(SAM, "Samuel ", " Sam@B.co ", 7, True, "")
    assert api.calls[0] == ("update_member", 5, {"full_name": "Samuel"})
    vm.saveMember(SAM, "Sam", "sam@b.co", 9, False, "Fresh-pass-3")
    updates = [c for c in api.calls if c[0] == "update_member"]
    assert updates[-1] == ("update_member", 5, {"team_id": 9, "is_active": False, "new_password": "Fresh-pass-3"})


def test_save_member_validates_email(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "owner")
    vm.saveMember(SAM, "Sam", "not-an-email", 7, True, "")
    assert vm.errorFields == ["email"] and api.calls == []


def test_team_leader_cannot_move_members(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "team_leader")
    api.results["update_member"] = ApiResult(True, 200, SAM)
    vm.saveMember(SAM, "Sammy", "sam@b.co", 9, True, "")
    assert api.calls[0] == ("update_member", 5, {"full_name": "Sammy"})


def test_who_can_edit_and_delete_whom(tmp_path, monkeypatch):
    owner, _ = signed_in(tmp_path, monkeypatch, "owner")
    assert owner.canEditMember({"role": "owner", "email": "admin9531@gmail.com"})
    assert not owner.canDeleteMember({"role": "owner"})
    assert owner.canDeleteMember({**SAM, "team_id": 99})

    leader, _ = signed_in(tmp_path, monkeypatch, "team_leader")
    assert leader.canEditMember(SAM) and leader.canDeleteMember(SAM)
    assert not leader.canEditMember({**SAM, "team_id": 99})
    assert not leader.canDeleteMember({**SAM, "role": "team_leader"})

    member, _ = signed_in(tmp_path, monkeypatch, "member")
    assert not member.canEditMember(SAM) and not member.canDeleteMember(SAM)


def test_changing_own_email_signs_out(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "owner")
    me = {"id": 1, "email": "admin9531@gmail.com", "full_name": "Owner", "role": "owner", "team_id": None,
          "is_active": True}
    api.results["update_member"] = ApiResult(True, 200, {**me, "email": "boss@b.co"})
    vm.saveMember(me, "Owner", "boss@b.co", 0, True, "")
    assert not vm._auth.loggedIn and "boss@b.co" in vm._auth.errorMessage


def test_delete_member(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "owner")
    api.results["delete_member"] = ApiResult(True, 200, {"message": "Member deleted."})
    vm.deleteMember(SAM)
    assert api.calls[0] == ("delete_member", 5) and "sam@b.co" in vm.notice


def test_delete_team(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, "owner")
    deleted = []
    vm.teamDeleted.connect(deleted.append)
    api.results["delete_team"] = ApiResult(True, 200, {"message": "Team deleted. 2 members now have no team."})
    vm.deleteTeam({"id": 3, "name": "Sales"})
    assert api.calls[0] == ("delete_team", 3) and deleted == ["Sales"]
    assert vm.notice == "Team “Sales” deleted. 2 members now have no team."
