import pytest

from shared.api_contracts import Paths
from shared.enums import Role
from shared.permissions import Permission, effective_permissions
from tests.server.helpers import sign_in
from tests.server.test_members import add_member, create_team, first_login, pc


@pytest.fixture()
def owner(client):
    return sign_in(client)


@pytest.fixture()
def team(owner):
    return create_team(owner, "Sales")


@pytest.fixture()
def leader(client, owner, team):
    add_member(owner, "lead@example.com", team, role="team_leader")
    session = first_login(client, "lead@example.com", pc(1))
    session.team_id = team
    return session


def create_bundle(session, name, permissions, description=""):
    r = session.post(Paths.ROLE_BUNDLES, {"name": name, "description": description, "permissions": permissions})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def member_by_email(session, email):
    return next(m for m in session.get(Paths.MEMBERS).json() if m["email"] == email)


def patch(session, path, body):
    return session.client.patch(path, json=body, headers=session.headers("PATCH", path))


def put(session, path, body):
    return session.client.put(path, json=body, headers=session.headers("PUT", path))


def delete(session, path):
    return session.client.delete(path, headers=session.headers("DELETE", path))


# ------------------------------------------------------------------ catalog
def test_member_permissions_imply_viewing_members():
    granted = effective_permissions(Role.MEMBER, ["members.add", "no.longer.defined"])
    assert Permission.MEMBERS_VIEW in granted and Permission.PROJECTS_VIEW in granted


def test_sign_in_returns_effective_permissions(client, owner):
    assert set(owner.user["permissions"]) == {p.value for p in Permission}


# ---------------------------------------------------------- bundle management
def test_owner_manages_bundles(owner):
    bundle = create_bundle(owner, "Onboarding", ["members.add", "members.reset_device"], "New starters")
    assert owner.post(Paths.ROLE_BUNDLES, {"name": "onboarding", "permissions": ["members.add"]}).status_code == 409
    assert owner.post(Paths.ROLE_BUNDLES, {"name": "Empty", "permissions": []}).status_code == 422
    assert owner.post(Paths.ROLE_BUNDLES, {"name": "Bad", "permissions": ["root"]}).status_code == 422

    r = put(owner, Paths.role_bundle(bundle), {"name": "Onboarding", "permissions": ["members.add"]})
    assert r.status_code == 200 and r.json()["permissions"] == ["members.add"]

    listed = owner.get(Paths.ROLE_BUNDLES).json()
    assert [(b["name"], b["member_count"]) for b in listed] == [("Onboarding", 0)]
    assert delete(owner, Paths.role_bundle(bundle)).status_code == 200
    assert owner.get(Paths.ROLE_BUNDLES).json() == []


def test_only_the_owner_defines_bundles(owner, leader):
    bundle = create_bundle(owner, "Reports", ["revenue.view"])
    assert leader.post(Paths.ROLE_BUNDLES, {"name": "Mine", "permissions": ["revenue.view"]}).status_code == 403
    assert put(leader, Paths.role_bundle(bundle), {"name": "X", "permissions": ["revenue.view"]}).status_code == 403
    assert delete(leader, Paths.role_bundle(bundle)).status_code == 403
    assert leader.get(Paths.ROLE_BUNDLES).status_code == 200  # but can see them to assign


# --------------------------------------------------------------- assignment
def test_bundles_can_be_given_when_adding_a_member(client, owner, team):
    bundle = create_bundle(owner, "Onboarding", ["members.add"])
    r = add_member(owner, "helper@example.com", team)
    assert r.json()["role_bundles"] == []
    body = {"email": "deputy@example.com", "team_id": team, "initial_password": "Initial-pass-1",
            "role_bundle_ids": [bundle]}
    r = owner.post(Paths.MEMBERS, body)
    assert r.status_code == 201
    assert [b["name"] for b in r.json()["role_bundles"]] == ["Onboarding"]
    assert "members.add" in r.json()["permissions"]
    assert owner.post(Paths.MEMBERS, {**body, "email": "x@example.com", "role_bundle_ids": [999]}).status_code == 404


def test_delegate_gains_and_loses_bundle_permissions(client, owner, team):
    bundle = create_bundle(owner, "Onboarding", ["members.add"])
    add_member(owner, "deputy@example.com", team)
    deputy = first_login(client, "deputy@example.com", pc(2))
    assert add_member(deputy, "new@example.com", team).status_code == 403

    deputy_id = member_by_email(owner, "deputy@example.com")["id"]
    assert patch(owner, Paths.member(deputy_id), {"role_bundle_ids": [bundle]}).status_code == 200
    assert add_member(deputy, "new@example.com", team).status_code == 201  # takes effect at once
    assert add_member(deputy, "lead2@example.com", team, role="team_leader").status_code == 403

    assert patch(owner, Paths.member(deputy_id), {"role_bundle_ids": []}).status_code == 200
    assert add_member(deputy, "other@example.com", team).status_code == 403


def test_deleting_a_bundle_removes_it_from_members(client, owner, team):
    bundle = create_bundle(owner, "Onboarding", ["members.add"])
    add_member(owner, "deputy@example.com", team)
    deputy_id = member_by_email(owner, "deputy@example.com")["id"]
    patch(owner, Paths.member(deputy_id), {"role_bundle_ids": [bundle]})
    delete(owner, Paths.role_bundle(bundle))
    assert member_by_email(owner, "deputy@example.com")["role_bundles"] == []


def test_team_leader_assigns_only_bundles_within_own_permissions(client, owner, leader, team):
    within = create_bundle(owner, "Reports", ["revenue.view"])
    beyond = create_bundle(owner, "Team admin", ["teams.create"])
    add_member(leader, "m@example.com", team)
    m_id = member_by_email(leader, "m@example.com")["id"]

    assert patch(leader, Paths.member(m_id), {"role_bundle_ids": [within]}).status_code == 200
    r = patch(leader, Paths.member(m_id), {"role_bundle_ids": [within, beyond]})
    assert r.status_code == 403 and "Team admin" in r.json()["detail"]

    # Nor can the leader remove a bundle they could not have given.
    patch(owner, Paths.member(m_id), {"role_bundle_ids": [within, beyond]})
    assert patch(leader, Paths.member(m_id), {"role_bundle_ids": [beyond]}).status_code == 200  # drops `within`
    assert patch(leader, Paths.member(m_id), {"role_bundle_ids": []}).status_code == 403


def test_team_leader_cannot_change_roles_outside_own_team(client, owner, leader, team):
    bundle = create_bundle(owner, "Reports", ["revenue.view"])
    other = create_team(owner, "Support")
    add_member(owner, "outsider@example.com", other)
    outsider = member_by_email(owner, "outsider@example.com")["id"]
    me = member_by_email(owner, "lead@example.com")["id"]
    owner_id = member_by_email(owner, "admin9531@gmail.com")["id"]

    assert patch(leader, Paths.member(outsider), {"role_bundle_ids": [bundle]}).status_code == 403
    assert patch(leader, Paths.member(me), {"role_bundle_ids": [bundle]}).status_code == 403
    assert patch(owner, Paths.member(owner_id), {"role_bundle_ids": [bundle]}).status_code == 403


def test_leaders_promote_but_only_the_owner_demotes(client, owner, leader, team):
    add_member(leader, "m@example.com", team)
    m_id = member_by_email(owner, "m@example.com")["id"]
    r = patch(leader, Paths.member(m_id), {"role": "team_leader"})
    assert r.status_code == 200 and r.json()["role"] == "team_leader"
    assert "members.add" in r.json()["permissions"]

    assert patch(leader, Paths.member(m_id), {"role": "member"}).status_code == 403
    r = patch(owner, Paths.member(m_id), {"role": "member"})
    assert r.status_code == 200 and r.json()["role"] == "member"


def test_bundles_grant_team_permissions(client, owner, team):
    bundle = create_bundle(owner, "Team admin", ["teams.create", "teams.rename"])
    add_member(owner, "ops@example.com", team, full_name="Ops")
    ops = first_login(client, "ops@example.com", pc(3))
    assert ops.post(Paths.TEAMS, {"name": "Support"}).status_code == 403

    patch(owner, Paths.member(member_by_email(owner, "ops@example.com")["id"]), {"role_bundle_ids": [bundle]})
    assert ops.post(Paths.TEAMS, {"name": "Support"}).status_code == 201
    r = patch(ops, Paths.team(team), {"name": "Sales EMEA"})
    assert r.status_code == 200 and r.json()["name"] == "Sales EMEA"
    assert {t["name"] for t in ops.get(Paths.TEAMS).json()} == {"Sales EMEA", "Support"}
    assert patch(ops, Paths.team(team), {"name": "Support"}).status_code == 409
