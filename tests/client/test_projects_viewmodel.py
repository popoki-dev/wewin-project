import pytest
from PySide6.QtCore import QCoreApplication, QSettings

from client.api.client import ApiResult
from client.app import storage as storage_module
from client.app.storage import Storage
from client.viewmodels.auth_viewmodel import AuthViewModel
from client.viewmodels.projects_viewmodel import ProjectsViewModel, format_money, parse_money
from tests.client.test_auth_viewmodel import DEVICE_ID, TOKENS, FakeAuthApi


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


class FakeProjectsApi:
    def __init__(self):
        self.calls = []
        self.results = {}

    def _answer(self, name, cb, *args):
        self.calls.append((name, *args))
        cb(self.results.get(name, ApiResult(True, 200, {"items": [], "title": "P"})))

    def list(self, server, token, cb): self._answer("list", cb)
    def create(self, server, token, body, cb): self._answer("create", cb, body)
    def update(self, server, token, project_id, body, cb): self._answer("update", cb, project_id, body)
    def delete(self, server, token, project_id, cb): self._answer("delete", cb, project_id)
    def check(self, server, token, project_id, cb): self._answer("check", cb, project_id)
    def uncheck(self, server, token, project_id, level, cb): self._answer("uncheck", cb, project_id, level)


def signed_in(tmp_path, monkeypatch, role="owner"):
    monkeypatch.setattr(storage_module, "keyring", None)
    storage = Storage(QSettings(str(tmp_path / "wewin.ini"), QSettings.Format.IniFormat))
    auth_api = FakeAuthApi()
    perms = ["projects.view", "projects.create", "projects.edit", "projects.delete"]
    auth_api.results["login"] = ApiResult(True, 200, {**TOKENS, "user": {**TOKENS["user"], "role": role,
                                                                         "permissions": perms}})
    auth = AuthViewModel(storage, auth_api, device_id=lambda: DEVICE_ID)
    auth.login("localhost:8000", "admin9531@gmail.com", "pw", False)
    api = FakeProjectsApi()
    return ProjectsViewModel(auth, api), api


DETAILS = "Line one\n\n  indented line\n\ttab"


def save(vm, **kw):
    args = {"project_id": 0, "title": "Website", "start": "2026-11-01", "end": "", "category": "fixed",
            "total_budget": "12,000", "monthly_budget": "", "details": DETAILS, "team_id": 0,
            "codevelopers": [], "payments": []}
    args.update(kw)
    vm.saveProject(*args.values())


@pytest.mark.parametrize(("text", "cents"), [
    ("12000", 1_200_000), ("12,000.50", 1_200_050), ("$1,200.5", 120_050), (" 0 ", 0), ("", None),
])
def test_parse_money(text, cents):
    assert parse_money(text) == cents


@pytest.mark.parametrize("text", ["abc", "-5", "1.005", "1e30", "nan"])
def test_parse_money_rejects(text):
    with pytest.raises(ValueError):
        parse_money(text)


def test_format_money():
    assert format_money(1_200_050) == "$12,000.50" and format_money(5) == "$0.05" and format_money(None) == ""


def test_save_sends_cents_and_details_untouched(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch)
    save(vm, monthly_budget="1000", payments=[
        {"id": 0, "paid_on": "2026-11-05", "description": " Deposit ", "amount": "3,000"},
        {"id": 9, "paid_on": "2026-12-05", "description": "Second", "amount": "2000.25"},
    ])
    body = api.calls[0][1]
    assert body["total_budget_cents"] == 1_200_000 and body["monthly_budget_cents"] == 100_000
    assert body["end_date"] is None and body["team_id"] is None
    assert body["details"] == DETAILS
    assert body["payments"] == [
        {"paid_on": "2026-11-05", "description": "Deposit", "amount_cents": 300_000, "my_share_cents": 0,
         "fund_location": "", "payouts": []},
        {"paid_on": "2026-12-05", "description": "Second", "amount_cents": 200_025, "my_share_cents": 0,
         "fund_location": "", "payouts": [], "id": 9},
    ]


@pytest.mark.parametrize(("kw", "field"), [
    ({"title": "  "}, "title"),
    ({"start": "2026-13-01"}, "startDate"),
    ({"end": "2026-10-01"}, "endDate"),
    ({"total_budget": ""}, "totalBudget"),
    ({"total_budget": "lots"}, "totalBudget"),
    ({"monthly_budget": "-3"}, "monthlyBudget"),
    ({"payments": [{"paid_on": "2026-11-05", "amount": "0"}]}, "payments"),
    ({"payments": [{"paid_on": "soon", "amount": "5"}]}, "payments"),
])
def test_save_validates_locally(tmp_path, monkeypatch, kw, field):
    vm, api = signed_in(tmp_path, monkeypatch)
    save(vm, **kw)
    assert vm.errorFields == [field] and api.calls == []


def test_update_and_refresh(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch)
    saved = []
    vm.projectSaved.connect(lambda: saved.append(True))
    api.results["update"] = ApiResult(True, 200, {"title": "Website"})
    save(vm, project_id=4, team_id=2)
    assert api.calls[0][:2] == ("update", 4) and api.calls[0][2]["team_id"] == 2
    assert saved and api.calls[-1][0] == "list" and "saved" in vm.notice


def test_server_errors_point_at_fields(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch)
    api.results["create"] = ApiResult(False, 403, {}, "You can only file projects under teams you lead.")
    save(vm)
    assert vm.errorFields == ["team"]


def test_check_and_uncheck(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch, role="owner")
    vm.checkProject({"id": 3, "title": "P"})
    vm.uncheckProject({"id": 3, "title": "P", "owner_check": {"at": "x"}})
    vm.uncheckProject({"id": 3, "title": "P", "owner_check": None, "leader_check": {"at": "x"}})
    assert [c for c in api.calls if c[0] in ("check", "uncheck")] == [
        ("check", 3), ("uncheck", 3, "owner"), ("uncheck", 3, "leader"),
    ]


def test_money_input_round_trip(tmp_path, monkeypatch):
    vm, _ = signed_in(tmp_path, monkeypatch)
    assert vm.moneyInput(120_005) == "1200.05" and parse_money(vm.moneyInput(120_005)) == 120_005
    assert vm.moneyInput(None) == "" and vm.money(1_000_000) == "$10,000.00"


def test_hourly_projects_may_leave_the_total_blank(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch)
    save(vm, category="hourly", total_budget="", monthly_budget="1300")
    body = api.calls[0][1]
    assert body["total_budget_cents"] is None and body["monthly_budget_cents"] == 130_000
    save(vm, category="fixed", total_budget="")
    assert vm.errorFields == ["totalBudget"]



CODEVS = [{"id": 0, "nationality": "Japan", "name": " Aiko ", "external_id": "", "contact": " aiko@example.com "},
          {"id": 7, "nationality": "", "name": "", "external_id": "ben#42"}]


def split_row(**kw):
    row = {"id": 0, "paid_on": "2026-11-05", "description": "M1", "amount": "1,000", "my_share": "500",
           "fund_location": " Wise USD ", "payouts": [{"codeveloper_index": 0, "amount": "300"},
                                                     {"codeveloper_index": 1, "amount": "150"}]}
    row.update(kw)
    return row


def test_codevelopers_and_splits_are_sent(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch)
    save(vm, codevelopers=CODEVS, payments=[split_row()])
    body = api.calls[0][1]
    assert body["codevelopers"] == [
        {"nationality": "Japan", "name": "Aiko", "external_id": "", "contact": "aiko@example.com"},
        {"nationality": "", "name": "", "external_id": "ben#42", "contact": "", "id": 7},  # contact is optional
    ]
    assert body["payments"][0] == {
        "paid_on": "2026-11-05", "description": "M1", "amount_cents": 100_000, "my_share_cents": 50_000,
        "fund_location": "Wise USD",
        "payouts": [{"codeveloper_index": 0, "amount_cents": 30_000}, {"codeveloper_index": 1, "amount_cents": 15_000}],
    }


@pytest.mark.parametrize(("kw", "field", "text"), [
    ({"codevelopers": [{"id": 0, "nationality": " ", "name": "", "external_id": ""}]}, "codevelopers", "Co-developer 1"),
    ({"codevelopers": [{"id": 0, "contact": "a@b.c"}]}, "codevelopers", "Co-developer 1"),
    ({"payments": [split_row(my_share="900")]}, "payments", "more than the total"),
    ({"payments": [split_row(payouts=[{"codeveloper_index": -1, "amount": "5"}])]}, "payments", "choose the co-developer"),
    ({"payments": [split_row(payouts=[{"codeveloper_index": 0, "amount": "5"}, {"codeveloper_index": 0, "amount": "5"}])]},
     "payments", "only once"),
    ({"payments": [split_row(my_share="lots")]}, "payments", "your portion"),
])
def test_split_validation(tmp_path, monkeypatch, kw, field, text):
    vm, api = signed_in(tmp_path, monkeypatch)
    save(vm, **{"codevelopers": CODEVS, **kw})
    assert vm.errorFields == [field] and text in vm.errorMessage and api.calls == []


def test_remaining_is_calculated_live(tmp_path, monkeypatch):
    vm, _ = signed_in(tmp_path, monkeypatch)
    assert vm.paymentRemaining(split_row()) == {"text": "$50.00", "over": False}
    assert vm.paymentRemaining(split_row(my_share="900")) == {"text": "-$350.00", "over": True}
    assert vm.paymentRemaining(split_row(amount="")) == {"text": "", "over": False}


def test_fund_locations_are_suggested_most_used_first(tmp_path, monkeypatch):
    vm, api = signed_in(tmp_path, monkeypatch)
    api.results["list"] = ApiResult(True, 200, {"items": [
        {"payments": [{"fund_location": "PayPal"}, {"fund_location": "Wise USD"}]},
        {"payments": [{"fund_location": "Wise USD"}, {"fund_location": ""}]},
    ]})
    vm.refresh()
    assert vm.fundLocations == ["Wise USD", "PayPal"]
