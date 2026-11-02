import pytest
from sqlalchemy import select

from server.app.database.session import SessionLocal
from server.app.models import AuditLog
from shared.api_contracts import Paths
from shared.enums import AuditAction
from tests.server.helpers import login, sign_in
from tests.server.test_members import CHOSEN, add_member, create_team, first_login, pc
from tests.server.test_role_bundles import create_bundle, delete, member_by_email, patch


@pytest.fixture()
def owner(client):
    return sign_in(client)


@pytest.fixture()
def team(owner):
    return create_team(owner, "Sales")


@pytest.fixture()
def leader(client, owner, team):
    add_member(owner, "lead@example.com", team, role="team_leader")
    return first_login(client, "lead@example.com", pc(1))


@pytest.fixture()
def member(client, owner, team):
    add_member(owner, "sam@example.com", team, full_name="Sam")
    session = first_login(client, "sam@example.com", pc(2))
    session.id = member_by_email(owner, "sam@example.com")["id"]
    return session


def audit_details(action):
    with SessionLocal() as db:
        return [row.details for row in db.scalars(select(AuditLog).where(AuditLog.action == action.value))]


# --------------------------------------------------------------------- owner
def test_owner_edits_details(owner, member):
    support = create_team(owner, "Support")
    r = patch(owner, Paths.member(member.id), {"full_name": "Samuel", "team_id": support})
    assert r.status_code == 200
    assert (r.json()["full_name"], r.json()["team_name"]) == ("Samuel", "Support")
    assert member.get(Paths.TEAMS).status_code == 200  # name and team changes keep the session
    updates = audit_details(AuditAction.USER_UPDATED)
    assert {"from": "Sam", "to": "Samuel"} in [d.get("full_name") for d in updates]
    assert any(d.get("team_id", {}).get("to") == support for d in updates)


def test_email_change_signs_the_member_out(client, owner, member):
    r = patch(owner, Paths.member(member.id), {"email": " Samuel@Example.com "})
    assert r.status_code == 200 and r.json()["email"] == "samuel@example.com"
    assert member.get(Paths.TEAMS).status_code == 401
    assert member.refresh().status_code == 401
    assert sign_in(client, "samuel@example.com", CHOSEN, device_id=pc(2)).user["email"] == "samuel@example.com"


def test_duplicate_email_is_refused(owner, leader, member):
    r = patch(owner, Paths.member(member.id), {"email": "lead@example.com"})
    assert r.status_code == 409


def test_disabling_signs_out_and_blocks_sign_in(client, owner, member):
    assert patch(owner, Paths.member(member.id), {"is_active": False}).status_code == 200
    assert member.get(Paths.TEAMS).status_code == 401
    assert login(client, "sam@example.com", CHOSEN, device_id=pc(2)).status_code == 403
    assert patch(owner, Paths.member(member.id), {"is_active": True}).status_code == 200
    assert login(client, "sam@example.com", CHOSEN, device_id=pc(2)).status_code == 200


def test_new_initial_password_forces_a_change(client, owner, member):
    weak = patch(owner, Paths.member(member.id), {"new_password": "weak"})
    assert weak.status_code == 422 and weak.json()["detail"].startswith("New password")
    r = patch(owner, Paths.member(member.id), {"new_password": "Fresh-pass-3"})
    assert r.status_code == 200 and r.json()["must_change_password"]
    assert member.get(Paths.TEAMS).status_code == 401
    session = sign_in(client, "sam@example.com", "Fresh-pass-3", device_id=pc(2))
    assert session.user["must_change_password"]


def test_owner_cannot_disable_delete_or_reset_themselves(owner):
    me = member_by_email(owner, "admin9531@gmail.com")["id"]
    assert patch(owner, Paths.member(me), {"is_active": False}).status_code == 422
    assert patch(owner, Paths.member(me), {"new_password": "Fresh-pass-3"}).status_code == 422
    assert delete(owner, Paths.member(me)).status_code == 422
    r = patch(owner, Paths.member(me), {"full_name": "The Owner"})
    assert r.status_code == 200 and r.json()["full_name"] == "The Owner"


def test_owner_deletes_a_member(client, owner, member):
    bundle = create_bundle(owner, "Reports", ["revenue.view"])
    patch(owner, Paths.member(member.id), {"role_bundle_ids": [bundle]})
    assert delete(owner, Paths.member(member.id)).status_code == 200
    assert "sam@example.com" not in {m["email"] for m in owner.get(Paths.MEMBERS).json()}
    assert member.get(Paths.TEAMS).status_code == 401
    assert owner.get(Paths.ROLE_BUNDLES).json()[0]["member_count"] == 0
    assert audit_details(AuditAction.USER_DELETED)[-1]["email"] == "sam@example.com"
    assert delete(owner, Paths.member(member.id)).status_code == 404


# ---------------------------------------------------------------- team leader
def test_team_leader_edits_and_deletes_own_team_members(owner, leader, member):
    r = patch(leader, Paths.member(member.id), {"full_name": "Sammy", "new_password": "Fresh-pass-3"})
    assert r.status_code == 200 and r.json()["full_name"] == "Sammy" and r.json()["must_change_password"]
    assert patch(leader, Paths.member(member.id), {"is_active": False}).status_code == 200
    assert delete(leader, Paths.member(member.id)).status_code == 200


def test_team_leader_cannot_move_members_or_change_base_roles(owner, leader, member):
    support = create_team(owner, "Support")
    assert patch(leader, Paths.member(member.id), {"team_id": support}).status_code == 403
    assert patch(leader, Paths.member(member.id), {"role": "team_leader"}).status_code == 403


def test_team_leader_stays_within_own_team(client, owner, leader):
    support = create_team(owner, "Support")
    add_member(owner, "outsider@example.com", support)
    sales = member_by_email(owner, "lead@example.com")["led_teams"][0]["id"]
    add_member(owner, "lead2@example.com", sales, role="team_leader")
    outsider = member_by_email(owner, "outsider@example.com")["id"]
    other_leader = member_by_email(owner, "lead2@example.com")["id"]
    me = member_by_email(owner, "lead@example.com")["id"]
    owner_id = member_by_email(owner, "admin9531@gmail.com")["id"]

    for target in (outsider, other_leader, me, owner_id):
        assert patch(leader, Paths.member(target), {"full_name": "X"}).status_code == 403
        assert delete(leader, Paths.member(target)).status_code in (403, 422)


def test_members_without_permission_cannot_edit_or_delete(client, owner, team, member):
    add_member(owner, "peer@example.com", team)
    peer = member_by_email(owner, "peer@example.com")["id"]
    assert patch(member, Paths.member(peer), {"full_name": "X"}).status_code == 403
    assert delete(member, Paths.member(peer)).status_code == 403


def test_bundle_can_grant_edit_and_delete(client, owner, team, member):
    bundle = create_bundle(owner, "Team admin", ["members.edit", "members.delete"])
    patch(owner, Paths.member(member.id), {"role_bundle_ids": [bundle]})
    add_member(owner, "peer@example.com", team)
    peer = member_by_email(owner, "peer@example.com")["id"]
    assert patch(member, Paths.member(peer), {"full_name": "Peer"}).status_code == 200
    assert delete(member, Paths.member(peer)).status_code == 200



# ------------------------------------------------------------- optional team
def add_without_team(session, email, role="member"):
    body = {"email": email, "role": role, "initial_password": "Initial-pass-1"}
    return session.post(Paths.MEMBERS, body)


def set_team(session, user_id, team_id):
    return patch(session, Paths.member(user_id), {"team_id": team_id})


def test_owner_adds_a_member_without_a_team(owner):
    r = add_without_team(owner, "solo@example.com")
    assert r.status_code == 201 and r.json()["team_id"] is None
    assert add_without_team(owner, "lead2@example.com", role="team_leader").status_code == 422


def test_owner_clears_and_sets_teams(owner, team, member):
    r = set_team(owner, member.id, None)
    assert r.status_code == 200 and r.json()["team_id"] is None
    assert set_team(owner, member.id, team).json()["team_name"] == "Sales"


def test_team_leaders_need_a_team(owner, team, leader):
    lead_id = member_by_email(owner, "lead@example.com")["id"]
    assert set_team(owner, lead_id, None).status_code == 422
    assert member_by_email(owner, "lead@example.com")["led_teams"] == [{"id": team, "name": "Sales"}]  # nothing saved
    # Demoting in the same request makes it fine.
    r = patch(owner, Paths.member(lead_id), {"team_id": None, "role": "member"})
    assert r.status_code == 200 and (r.json()["role"], r.json()["team_id"]) == ("member", None)

    solo = add_without_team(owner, "solo@example.com").json()["id"]
    assert patch(owner, Paths.member(solo), {"role": "team_leader"}).status_code == 422
    assert patch(owner, Paths.member(solo), {"role": "team_leader", "team_id": team}).status_code == 200


def test_team_leader_sees_and_brings_in_members_without_a_team(owner, leader, team):
    solo = add_without_team(owner, "solo@example.com").json()["id"]
    assert "solo@example.com" in {m["email"] for m in leader.get(Paths.MEMBERS).json()}
    r = set_team(leader, solo, team)
    assert r.status_code == 200 and r.json()["team_name"] == "Sales"


def test_team_leader_takes_members_out_of_own_team(owner, leader, team, member):
    r = set_team(leader, member.id, None)
    assert r.status_code == 200 and r.json()["team_id"] is None
    assert member.get(Paths.TEAMS).json() == []  # the member keeps their account and session


def test_team_leader_moves_are_limited(owner, leader, team, member):
    support = create_team(owner, "Support")
    add_member(owner, "other@example.com", support)
    other = member_by_email(owner, "other@example.com")["id"]
    lead_id = member_by_email(owner, "lead@example.com")["id"]
    solo = add_without_team(owner, "solo@example.com").json()["id"]

    assert set_team(leader, member.id, support).status_code == 403  # to another team
    assert set_team(leader, other, None).status_code == 403  # out of another team
    assert set_team(leader, other, team).status_code == 403  # poach from another team
    assert set_team(leader, solo, support).status_code == 403  # into another team
    assert set_team(leader, lead_id, None).status_code == 403  # themselves


def test_team_leader_adds_to_own_team_by_default(owner, leader, team):
    r = add_without_team(leader, "new@example.com")
    assert r.status_code == 201 and r.json()["team_id"] == team


def test_moving_teams_needs_the_permission(client, owner, team, member):
    add_member(owner, "peer@example.com", team)
    peer = member_by_email(owner, "peer@example.com")["id"]
    assert set_team(member, peer, None).status_code == 403
    bundle = create_bundle(owner, "Team moves", ["members.team"])
    patch(owner, Paths.member(member.id), {"role_bundle_ids": [bundle]})
    assert set_team(member, peer, None).status_code == 200
