from datetime import date, datetime, timezone

import pytest

from shared.api_contracts import Paths
from tests.server.helpers import sign_in
from tests.server.test_members import add_member, create_team, first_login, pc
from tests.server.test_role_bundles import delete, member_by_email, patch, put

DETAILS = "Scope:\n  - design\n  - build\n\n\tTabbed line  with  double spaces \n"


@pytest.fixture()
def owner(client):
    return sign_in(client)


@pytest.fixture()
def teams(owner):
    return {name: create_team(owner, name) for name in ("Sales", "Ops")}


@pytest.fixture()
def leader(client, owner, teams):
    add_member(owner, "lead@example.com", teams["Sales"], role="team_leader")
    return first_login(client, "lead@example.com", pc(1))


@pytest.fixture()
def member(client, owner, teams):
    add_member(owner, "sam@example.com", teams["Sales"])
    return first_login(client, "sam@example.com", pc(2))


def body(**overrides):
    data = {
        "title": "Website", "start_date": "2026-11-01", "category": "fixed",
        "total_budget_cents": 1_200_000, "details": DETAILS,
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not ...}


def create(session, **overrides):
    r = session.post(Paths.PROJECTS, body(**overrides))
    assert r.status_code == 201, r.text
    return r.json()


def check(session, project_id):
    return session.post(Paths.project_check(project_id))


def uncheck(session, project_id, level):
    path = Paths.project_check(project_id)
    return session.client.delete(path, params={"level": level}, headers=session.headers("DELETE", path))


def titles(session):
    return sorted(p["title"] for p in session.get(Paths.PROJECTS).json())


# ------------------------------------------------------------------ fields
def test_project_fields_and_defaults(owner):
    p = create(owner, start_date=..., monthly_budget_cents=100_000)
    assert p["start_date"] == datetime.now(timezone.utc).date().isoformat()  # defaults to today
    assert p["end_date"] is None  # completion date may be blank
    assert (p["category"], p["total_budget_cents"], p["monthly_budget_cents"]) == ("fixed", 1_200_000, 100_000)
    assert p["details"] == DETAILS  # line breaks, tabs and spaces kept exactly
    assert owner.get(Paths.project(p["id"])).json()["details"] == DETAILS


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "   "},
        {"total_budget_cents": ...},  # total budget is required (except for hourly projects)
        {"total_budget_cents": None, "category": "milestone"},
        {"total_budget_cents": -1},
        {"monthly_budget_cents": -5},
        {"category": "weekly"},
        {"end_date": "2026-10-01"},  # before the start
        {"payments": [{"paid_on": "2026-11-02", "amount_cents": 0}]},
    ],
)
def test_invalid_projects_are_rejected(owner, overrides):
    assert owner.post(Paths.PROJECTS, body(**overrides)).status_code == 422


def test_payment_history_add_edit_delete(owner):
    p = create(owner, payments=[
        {"paid_on": "2026-11-05", "description": "Deposit", "amount_cents": 300_000},
        {"paid_on": "2026-12-05", "description": "Second", "amount_cents": 200_000},
    ])
    assert p["paid_cents"] == 500_000
    first, second = p["payments"]

    edited = [
        {**first, "description": "Deposit (50%)", "amount_cents": 600_000},  # modify
        {"paid_on": "2027-01-05", "description": "Final", "amount_cents": 600_000},  # add
    ]  # `second` is left out: deleted
    r = put(owner, Paths.project(p["id"]), body(payments=edited))
    assert r.status_code == 200
    payments = r.json()["payments"]
    assert [(x["description"], x["amount_cents"]) for x in payments] == [("Deposit (50%)", 600_000), ("Final", 600_000)]
    assert payments[0]["id"] == first["id"] and second["id"] not in {x["id"] for x in payments}
    assert r.json()["paid_cents"] == 1_200_000


def test_payments_of_another_project_are_refused(owner):
    a = create(owner, payments=[{"paid_on": "2026-11-05", "amount_cents": 100}])
    b = create(owner, title="Other")
    stolen = a["payments"][0]
    assert put(owner, Paths.project(b["id"]), body(payments=[stolen])).status_code == 422


# ------------------------------------------------------------------- scope
def test_who_sees_which_projects(owner, teams, leader, member):
    create(owner, title="Ops project", team_id=teams["Ops"])
    create(owner, title="Sales project", team_id=teams["Sales"])
    create(member, title="Sam's project")
    create(leader, title="Lena's project")

    assert titles(owner) == ["Lena's project", "Ops project", "Sales project", "Sam's project"]
    assert titles(leader) == ["Lena's project", "Sales project", "Sam's project"]  # their team's
    assert titles(member) == ["Sam's project"]  # their own


def test_members_file_projects_under_their_own_team(owner, teams, member):
    p = create(member, team_id=teams["Ops"])
    assert p["team_name"] == "Sales"
    assert put(member, Paths.project(p["id"]), body(team_id=teams["Ops"])).json()["team_name"] == "Sales"


def test_team_leaders_file_projects_under_teams_they_lead(owner, teams, leader):
    assert create(leader)["team_name"] == "Sales"  # their only team
    assert leader.post(Paths.PROJECTS, body(team_id=teams["Ops"])).status_code == 403
    path = Paths.team_leaders(teams["Ops"])
    owner.post(path, {"user_id": member_by_email(owner, "lead@example.com")["id"]})
    leader = sign_in(leader.client, "lead@example.com", "Chosen-pass-2", device_id=pc(1))
    assert leader.post(Paths.PROJECTS, body()).status_code == 422  # two teams: pick one
    assert create(leader, team_id=teams["Ops"])["team_name"] == "Ops"


def test_others_cannot_see_or_change_a_project(owner, teams, leader, member):
    ops = create(owner, team_id=teams["Ops"])
    mine = create(member)
    assert leader.get(Paths.project(ops["id"])).status_code == 404
    assert put(leader, Paths.project(ops["id"]), body()).status_code == 404
    assert delete(member, Paths.project(ops["id"])).status_code == 404
    assert put(leader, Paths.project(mine["id"]), body(title="Edited by leader")).status_code == 200


# ------------------------------------------------------------------ checks
def test_leader_check_locks_the_project_for_members(owner, teams, leader, member):
    p = create(member)
    assert p["access"] == {"edit": True, "delete": True, "check": False, "uncheck": False}
    r = check(leader, p["id"])
    assert r.status_code == 200 and r.json()["leader_check"]["by"] == "lead@example.com"

    blocked = put(member, Paths.project(p["id"]), body(title="Changed"))
    assert blocked.status_code == 409 and "Team Leader" in blocked.json()["detail"]
    assert delete(member, Paths.project(p["id"])).status_code == 409
    assert member.get(Paths.project(p["id"])).json()["access"]["edit"] is False
    assert put(leader, Paths.project(p["id"]), body(title="Leader still edits")).status_code == 200


def test_owner_check_locks_the_project_for_team_leaders(owner, teams, leader, member):
    p = create(leader)
    assert check(owner, p["id"]).json()["owner_check"] is not None
    blocked = put(leader, Paths.project(p["id"]), body(title="Changed"))
    assert blocked.status_code == 409 and "Owner" in blocked.json()["detail"]
    assert delete(leader, Paths.project(p["id"])).status_code == 409
    assert check(leader, p["id"]).status_code == 409  # nor add their check now
    assert put(owner, Paths.project(p["id"]), body(title="Owner edits anyway")).status_code == 200


def test_who_removes_checks(owner, teams, leader, member):
    p = create(member)
    check(leader, p["id"])
    assert uncheck(member, p["id"], "leader").status_code == 403
    assert uncheck(leader, p["id"], "leader").json()["leader_check"] is None
    check(leader, p["id"])
    check(owner, p["id"])
    assert uncheck(leader, p["id"], "leader").status_code == 409  # the Owner has checked it
    assert uncheck(leader, p["id"], "owner").status_code == 403
    r = uncheck(owner, p["id"], "owner")
    assert r.json()["owner_check"] is None and r.json()["leader_check"] is not None
    assert uncheck(owner, p["id"], "leader").json()["leader_check"] is None


def test_members_cannot_check(owner, member):
    p = create(member)
    assert check(member, p["id"]).status_code == 403


# ----------------------------------------------------------------- delete
def test_delete_projects(owner, teams, leader, member):
    a, b = create(member), create(member, title="B")
    assert delete(member, Paths.project(a["id"])).status_code == 200
    check(owner, b["id"])
    assert delete(owner, Paths.project(b["id"])).status_code == 200  # the Owner deletes anything
    assert titles(owner) == []


def test_projects_outlive_their_team_and_creator(owner, teams, member):
    p = create(member)
    team_path = Paths.team(teams["Sales"])
    owner.client.delete(team_path, headers=owner.headers("DELETE", team_path))
    sam = member_by_email(owner, "sam@example.com")["id"]
    delete(owner, Paths.member(sam))
    kept = owner.get(Paths.project(p["id"])).json()
    assert (kept["team_id"], kept["created_by_id"], kept["created_by_name"]) == (None, None, None)
    assert kept["details"] == DETAILS


def test_hourly_projects_may_have_no_total_budget(owner):
    p = create(owner, category="hourly", total_budget_cents=..., monthly_budget_cents=130_000,
               payments=[{"paid_on": "2026-11-03", "description": "week-1", "amount_cents": 60_000}])
    assert (p["total_budget_cents"], p["monthly_budget_cents"], p["paid_cents"]) == (None, 130_000, 60_000)
    assert create(owner, category="hourly", total_budget_cents=500_000)["total_budget_cents"] == 500_000
    # Switching to a category that needs one, without giving it, is refused.
    assert put(owner, Paths.project(p["id"]), body(category="fixed", total_budget_cents=None)).status_code == 422


# --------------------------------------------------- co-developers & splits
CODEVS = [
    {"nationality": "Japan", "name": "Aiko", "external_id": "aiko-dev"},
    {"nationality": "", "name": "", "external_id": "ben#42"},  # one field is enough
]


def split_payment(**overrides):
    payment = {"paid_on": "2026-11-05", "description": "Milestone 1", "amount_cents": 100_000,
               "my_share_cents": 50_000, "fund_location": "Wise USD",
               "payouts": [{"codeveloper_index": 0, "amount_cents": 30_000},
                           {"codeveloper_index": 1, "amount_cents": 15_000}]}
    payment.update(overrides)
    return payment


def test_codevelopers_and_payment_splits(owner):
    p = create(owner, codevelopers=CODEVS, payments=[split_payment()])
    assert [(c["name"], c["external_id"]) for c in p["codevelopers"]] == [("Aiko", "aiko-dev"), ("", "ben#42")]
    pay = p["payments"][0]
    assert (pay["amount_cents"], pay["my_share_cents"], pay["paid_out_cents"], pay["remaining_cents"]) == (
        100_000, 50_000, 45_000, 5_000,
    )
    assert pay["fund_location"] == "Wise USD"
    assert [(x["codeveloper_label"], x["amount_cents"]) for x in pay["payouts"]] == [("Aiko", 30_000), ("ben#42", 15_000)]
    assert (p["paid_cents"], p["remaining_cents"]) == (100_000, 5_000)


@pytest.mark.parametrize(
    "overrides",
    [
        {"codevelopers": [{"nationality": " ", "name": "", "external_id": ""}]},  # nothing filled in
        {"payments": [split_payment(my_share_cents=90_000)]},  # splits exceed the total received
        {"payments": [split_payment(payouts=[{"codeveloper_index": 5, "amount_cents": 1}])]},  # unknown co-dev
        {"payments": [split_payment(payouts=[{"codeveloper_index": 0, "amount_cents": 1},
                                             {"codeveloper_index": 0, "amount_cents": 1}])]},  # twice
        {"payments": [split_payment(my_share_cents=-1)]},
    ],
)
def test_invalid_codevelopers_and_splits_are_rejected(owner, overrides):
    r = owner.post(Paths.PROJECTS, body(**{"codevelopers": CODEVS, **overrides}))
    assert r.status_code == 422, r.text


def test_editing_codevelopers_keeps_payouts_linked(owner):
    p = create(owner, codevelopers=CODEVS, payments=[split_payment()])
    aiko, ben = p["codevelopers"]
    # Rename Aiko, drop Ben (and so his payout), add Chen and pay him in the same save.
    codevs = [{**aiko, "name": "Aiko Tanaka"}, {"nationality": "China", "name": "Chen", "external_id": ""}]
    payment = {**split_payment(), "id": p["payments"][0]["id"],
               "payouts": [{"codeveloper_index": 0, "amount_cents": 30_000},
                           {"codeveloper_index": 1, "amount_cents": 10_000}]}
    r = put(owner, Paths.project(p["id"]), body(codevelopers=codevs, payments=[payment]))
    assert r.status_code == 200, r.text
    out = r.json()
    assert [c["name"] for c in out["codevelopers"]] == ["Aiko Tanaka", "Chen"]
    assert out["codevelopers"][0]["id"] == aiko["id"] and ben["id"] not in {c["id"] for c in out["codevelopers"]}
    assert [(x["codeveloper_label"], x["amount_cents"]) for x in out["payments"][0]["payouts"]] == [
        ("Aiko Tanaka", 30_000), ("Chen", 10_000),
    ]
    assert out["payments"][0]["remaining_cents"] == 10_000


def test_removing_a_codeveloper_removes_their_payouts(owner):
    p = create(owner, codevelopers=CODEVS, payments=[split_payment()])
    aiko = p["codevelopers"][0]
    payment = {**split_payment(), "id": p["payments"][0]["id"],
               "payouts": [{"codeveloper_index": 0, "amount_cents": 30_000}]}
    out = put(owner, Paths.project(p["id"]), body(codevelopers=[aiko], payments=[payment])).json()
    assert [x["codeveloper_label"] for x in out["payments"][0]["payouts"]] == ["Aiko"]
    assert out["payments"][0]["remaining_cents"] == 20_000
    # Removing everyone at once is fine too: the payouts go with them.
    out = put(owner, Paths.project(p["id"]), body(codevelopers=[], payments=[{**payment, "payouts": []}])).json()
    assert out["codevelopers"] == [] and out["payments"][0]["payouts"] == []


def test_codeveloper_contact_details_are_optional(owner):
    p = create(owner, codevelopers=CODEVS)
    assert [c["contact"] for c in p["codevelopers"]] == ["", ""]
    aiko = {**p["codevelopers"][0], "contact": "  aiko@example.com, Telegram @aiko  "}
    out = put(owner, Paths.project(p["id"]), body(codevelopers=[aiko])).json()
    assert out["codevelopers"][0]["contact"] == "aiko@example.com, Telegram @aiko"
    # A contact alone does not identify anyone, and it has a length limit.
    for codev in ({"contact": "aiko@example.com"}, {"name": "Aiko", "contact": "x" * 301}):
        assert owner.post(Paths.PROJECTS, body(codevelopers=[codev])).status_code == 422


def test_codevelopers_of_another_project_are_refused(owner):
    a = create(owner, codevelopers=CODEVS)
    b = create(owner, title="Other")
    assert put(owner, Paths.project(b["id"]), body(codevelopers=[a["codevelopers"][0]])).status_code == 422
