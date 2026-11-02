import pytest
from sqlalchemy import select

from server.app.database.session import SessionLocal
from server.app.models import AuditLog
from shared.api_contracts import Paths
from shared.device_signature import device_id_from_mac
from tests.server.helpers import sign_in

INITIAL = "Initial-pass-1"
CHOSEN = "Chosen-pass-2"


def pc(n: int) -> str:
    return device_id_from_mac(f"02:00:00:00:01:{n:02X}")


@pytest.fixture()
def owner(client):
    return sign_in(client)


def create_team(session, name):
    r = session.post(Paths.TEAMS, {"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def add_member(session, email, team_id, role="member", password=INITIAL, full_name=""):
    body = {"email": email, "full_name": full_name, "team_id": team_id, "role": role, "initial_password": password}
    return session.post(Paths.MEMBERS, body)


def first_login(client, email, device):
    """Sign in with the initial password and replace it, as the client forces on first login."""
    session = sign_in(client, email, INITIAL, device_id=device)
    assert session.user["must_change_password"]
    r = session.post(Paths.AUTH_CHANGE_PASSWORD, {"current_password": INITIAL, "new_password": CHOSEN})
    assert r.status_code == 200, r.text
    session.update(r.json())
    return session


@pytest.fixture()
def leader(client, owner):
    team = create_team(owner, "Sales")
    assert add_member(owner, "lead@example.com", team, role="team_leader").status_code == 201
    session = first_login(client, "lead@example.com", pc(1))
    session.team_id = team
    return session


# ------------------------------------------------------------------- teams
def test_owner_creates_teams_and_names_are_unique(owner):
    create_team(owner, "Sales")
    dup = owner.post(Paths.TEAMS, {"name": "  sales "})
    assert dup.status_code == 409
    assert [t["name"] for t in owner.get(Paths.TEAMS).json()] == ["Sales"]


def test_only_the_owner_creates_teams(owner, leader):
    assert leader.post(Paths.TEAMS, {"name": "Marketing"}).status_code == 403


# ----------------------------------------------------------------- members
def test_adding_a_member_needs_email_team_and_a_strong_password(owner):
    team = create_team(owner, "Sales")
    assert owner.post(Paths.MEMBERS, {"team_id": team, "initial_password": INITIAL}).status_code == 422
    assert add_member(owner, "a@example.com", 9999).status_code == 404
    weak = add_member(owner, "a@example.com", team, password="weak")
    assert weak.status_code == 422 and weak.json()["detail"].startswith("Initial password")
    assert add_member(owner, "a@example.com", team).status_code == 201
    assert add_member(owner, "A@example.com", team).status_code == 409


def test_new_member_must_change_password_before_anything_else(client, owner):
    team = create_team(owner, "Sales")
    created = add_member(owner, "new@example.com", team, full_name="New Person").json()
    assert created["must_change_password"] and not created["device_registered"]

    session = sign_in(client, "new@example.com", INITIAL, device_id=pc(2))
    assert session.user["must_change_password"]
    blocked = session.get(Paths.TEAMS)
    assert blocked.status_code == 403 and "Change your password" in blocked.json()["detail"]
    assert session.get(Paths.AUTH_ME).status_code == 200

    wrong = session.post(Paths.AUTH_CHANGE_PASSWORD, {"current_password": "nope", "new_password": CHOSEN})
    assert wrong.status_code == 400
    same = session.post(Paths.AUTH_CHANGE_PASSWORD, {"current_password": INITIAL, "new_password": INITIAL})
    assert same.status_code == 422

    old_token = session.access_token
    r = session.post(Paths.AUTH_CHANGE_PASSWORD, {"current_password": INITIAL, "new_password": CHOSEN})
    assert r.status_code == 200 and not r.json()["user"]["must_change_password"]
    assert r.json()["device_secret"] is None  # the PC keeps its secret

    session.access_token = old_token
    assert session.get(Paths.AUTH_ME).status_code == 401  # tokens from before the change are void
    session.update(r.json())
    assert session.get(Paths.TEAMS).status_code == 200
    assert sign_in(client, "new@example.com", CHOSEN, device_id=pc(2)).user["must_change_password"] is False


def test_team_leader_adds_members_to_own_team_only(owner, leader):
    other = create_team(owner, "Support")
    assert add_member(leader, "m1@example.com", leader.team_id).status_code == 201
    assert add_member(leader, "m2@example.com", other).status_code == 403
    assert add_member(leader, "m3@example.com", leader.team_id, role="team_leader").status_code == 403


def test_team_leader_sees_only_own_team(owner, leader):
    other = create_team(owner, "Support")
    add_member(owner, "outsider@example.com", other)
    add_member(leader, "insider@example.com", leader.team_id)

    emails = {m["email"] for m in leader.get(Paths.MEMBERS).json()}
    assert emails == {"lead@example.com", "insider@example.com"}
    assert [t["name"] for t in leader.get(Paths.TEAMS).json()] == ["Sales"]
    assert len(owner.get(Paths.MEMBERS).json()) == 4  # owner, leader, both members


def test_members_cannot_manage_members(client, owner):
    team = create_team(owner, "Sales")
    add_member(owner, "plain@example.com", team)
    member = first_login(client, "plain@example.com", pc(3))
    assert add_member(member, "x@example.com", team).status_code == 403
    assert member.get(Paths.MEMBERS).status_code == 403
    assert [t["name"] for t in member.get(Paths.TEAMS).json()] == ["Sales"]


def test_device_reset_by_owner_and_team_leader(client, owner, leader):
    other = create_team(owner, "Support")
    add_member(leader, "mine@example.com", leader.team_id)
    add_member(owner, "theirs@example.com", other)
    mine = first_login(client, "mine@example.com", pc(4))
    first_login(client, "theirs@example.com", pc(5))
    by_email = {m["email"]: m for m in owner.get(Paths.MEMBERS).json()}
    assert by_email["mine@example.com"]["device_registered"]

    r = leader.post(Paths.member_device_reset(by_email["mine@example.com"]["id"]))
    assert r.status_code == 200 and not r.json()["device_registered"]
    assert mine.get(Paths.TEAMS).status_code == 401  # the old PC is signed out
    assert sign_in(client, "mine@example.com", CHOSEN, device_id=pc(9)).user["email"] == "mine@example.com"

    assert leader.post(Paths.member_device_reset(by_email["theirs@example.com"]["id"])).status_code == 403
    assert leader.post(Paths.member_device_reset(by_email["admin9531@gmail.com"]["id"])).status_code == 403
    assert owner.post(Paths.member_device_reset(by_email["theirs@example.com"]["id"])).status_code == 200
    assert owner.post(Paths.member_device_reset(99999)).status_code == 404


# ------------------------------------------------------------- team deletion
def team_delete(session, team_id):
    path = Paths.team(team_id)
    return session.client.delete(path, headers=session.headers("DELETE", path))


def test_owner_deletes_a_team_and_its_members_lose_the_team(client, owner):
    sales = create_team(owner, "Sales")
    support = create_team(owner, "Support")
    add_member(owner, "a@example.com", sales)
    add_member(owner, "b@example.com", sales, role="team_leader")
    add_member(owner, "c@example.com", support)

    r = team_delete(owner, sales)
    # Only plain members belong to a team; the leader is counted separately (and demoted).
    assert r.status_code == 200 and r.json()["message"] == "Team deleted. 1 member now has no team."

    teams = owner.get(Paths.TEAMS).json()
    assert [t["name"] for t in teams] == ["Support"]
    by_email = {m["email"]: m for m in owner.get(Paths.MEMBERS).json()}
    assert by_email["a@example.com"]["team_id"] is None and by_email["a@example.com"]["team_name"] is None
    assert by_email["b@example.com"]["team_id"] is None and by_email["b@example.com"]["led_teams"] == []
    assert by_email["b@example.com"]["role"] == "member"  # the team's leader becomes a regular member
    assert "members.add" not in by_email["b@example.com"]["permissions"]
    assert by_email["c@example.com"]["team_name"] == "Support"  # other teams untouched
    assert team_delete(owner, sales).status_code == 404


def test_member_without_team_can_be_given_a_new_one(client, owner):
    sales = create_team(owner, "Sales")
    add_member(owner, "a@example.com", sales)
    team_delete(owner, sales)
    support = create_team(owner, "Support")
    a = next(m for m in owner.get(Paths.MEMBERS).json() if m["email"] == "a@example.com")
    path = Paths.member(a["id"])
    r = owner.client.patch(path, json={"team_id": support}, headers=owner.headers("PATCH", path))
    assert r.status_code == 200 and r.json()["team_name"] == "Support"


def test_only_the_owner_deletes_teams(client, owner, leader):
    assert team_delete(leader, leader.team_id).status_code == 403
    assert team_delete(owner, 99999).status_code == 404


def test_team_leader_of_a_deleted_team_becomes_a_member(client, owner, leader):
    team_delete(owner, leader.team_id)
    assert leader.get(Paths.AUTH_ME).json()["role"] == "member"  # takes effect on the next request
    assert leader.get(Paths.MEMBERS).status_code == 403
    assert leader.get(Paths.TEAMS).json() == []
    with SessionLocal() as db:
        details = db.scalars(select(AuditLog.details).where(AuditLog.action == "team.deleted")).one()
    assert details["leaders_demoted"] == ["lead@example.com"]
