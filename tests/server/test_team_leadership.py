import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from shared.api_contracts import Paths
from tests.server.helpers import sign_in
from tests.server.test_members import add_member, create_team, first_login, pc
from tests.server.test_role_bundles import delete, member_by_email, patch

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "server" / "alembic.ini"


@pytest.fixture()
def owner(client):
    return sign_in(client)


@pytest.fixture()
def teams(owner):
    return {name: create_team(owner, name) for name in ("Sales", "Support", "Ops")}


def add_leader(session, team_id, user_id):
    return session.post(Paths.team_leaders(team_id), {"user_id": user_id})


def remove_leader(session, team_id, user_id):
    return delete(session, Paths.team_leader(team_id, user_id))


@pytest.fixture()
def leader(client, owner, teams):
    """Lena leads Sales and Support."""
    add_member(owner, "lead@example.com", teams["Sales"], role="team_leader")
    lena = member_by_email(owner, "lead@example.com")["id"]
    assert add_leader(owner, teams["Support"], lena).status_code == 200
    session = first_login(client, "lead@example.com", pc(1))
    session.id = lena
    return session


def led_names(owner, email):
    return [t["name"] for t in member_by_email(owner, email)["led_teams"]]


# ------------------------------------------------------------- leading many
def test_a_team_leader_leads_several_teams(owner, teams, leader):
    assert led_names(owner, "lead@example.com") == ["Sales", "Support"]
    assert member_by_email(owner, "lead@example.com")["team_id"] is None
    assert sorted(leader.get(Paths.AUTH_ME).json()["led_team_ids"]) == sorted([teams["Sales"], teams["Support"]])
    by_name = {t["name"]: t for t in owner.get(Paths.TEAMS).json()}
    assert [p["name"] for p in by_name["Support"]["leaders"]] == ["lead@example.com"]
    assert by_name["Ops"]["leaders"] == []


def test_team_leader_works_across_all_led_teams_only(owner, teams, leader):
    add_member(owner, "s1@example.com", teams["Sales"])
    add_member(owner, "u1@example.com", teams["Support"])
    add_member(owner, "o1@example.com", teams["Ops"])

    assert {t["name"] for t in leader.get(Paths.TEAMS).json()} == {"Sales", "Support"}
    visible = {m["email"] for m in leader.get(Paths.MEMBERS).json()}
    assert {"s1@example.com", "u1@example.com", "lead@example.com"} <= visible
    assert "o1@example.com" not in visible

    u1 = member_by_email(owner, "u1@example.com")["id"]
    o1 = member_by_email(owner, "o1@example.com")["id"]
    assert patch(leader, Paths.member(u1), {"full_name": "Una"}).status_code == 200
    assert patch(leader, Paths.member(o1), {"full_name": "X"}).status_code == 403
    # Moving a member between two led teams is allowed; into a team they don't lead is not.
    assert patch(leader, Paths.member(u1), {"team_id": teams["Sales"]}).status_code == 200
    assert patch(leader, Paths.member(u1), {"team_id": teams["Ops"]}).status_code == 403


def test_team_leader_with_several_teams_picks_one_when_adding(owner, teams, leader):
    body = {"email": "new@example.com", "initial_password": "Initial-pass-1"}
    assert leader.post(Paths.MEMBERS, body).status_code == 422  # which team?
    r = leader.post(Paths.MEMBERS, {**body, "team_id": teams["Support"]})
    assert r.status_code == 201 and r.json()["team_name"] == "Support"
    assert leader.post(Paths.MEMBERS, {**body, "email": "x@example.com", "team_id": teams["Ops"]}).status_code == 403


# ------------------------------------------------------- owner manages teams
def test_owner_promotes_a_member_to_lead_a_team(owner, teams):
    add_member(owner, "sam@example.com", teams["Sales"])
    sam = member_by_email(owner, "sam@example.com")["id"]
    r = add_leader(owner, teams["Ops"], sam)
    assert r.status_code == 200
    assert (r.json()["role"], r.json()["team_id"], [t["name"] for t in r.json()["led_teams"]]) == (
        "team_leader", None, ["Ops"],
    )


def test_removing_the_last_led_team_makes_a_member(owner, teams, leader):
    r = remove_leader(owner, teams["Support"], leader.id)
    assert r.status_code == 200 and r.json()["role"] == "team_leader"
    r = remove_leader(owner, teams["Sales"], leader.id)
    assert r.status_code == 200 and (r.json()["role"], r.json()["led_teams"]) == ("member", [])
    assert remove_leader(owner, teams["Sales"], leader.id).status_code == 404


def test_deleting_one_of_several_led_teams_keeps_the_leader(owner, teams, leader):
    path = Paths.team(teams["Support"])
    assert owner.client.delete(path, headers=owner.headers("DELETE", path)).status_code == 200
    assert led_names(owner, "lead@example.com") == ["Sales"]
    assert member_by_email(owner, "lead@example.com")["role"] == "team_leader"


def test_owner_adds_and_removes_team_members(owner, teams):
    add_member(owner, "sam@example.com", teams["Sales"])
    sam = member_by_email(owner, "sam@example.com")["id"]
    assert patch(owner, Paths.member(sam), {"team_id": teams["Support"]}).json()["team_name"] == "Support"
    assert patch(owner, Paths.member(sam), {"team_id": None}).json()["team_id"] is None


def test_only_the_owner_assigns_leaders(owner, teams, leader):
    add_member(owner, "sam@example.com", teams["Sales"])
    sam = member_by_email(owner, "sam@example.com")["id"]
    assert add_leader(leader, teams["Sales"], sam).status_code == 403
    assert remove_leader(leader, teams["Support"], leader.id).status_code == 403
    owner_id = member_by_email(owner, "admin9531@gmail.com")["id"]
    assert add_leader(owner, teams["Sales"], owner_id).status_code == 422


def test_demoting_a_leader_clears_their_teams(owner, teams, leader):
    r = patch(owner, Paths.member(leader.id), {"role": "member", "team_id": teams["Ops"]})
    assert r.status_code == 200
    assert (r.json()["role"], r.json()["team_name"], r.json()["led_teams"]) == ("member", "Ops", [])


# ----------------------------------------------------------------- migration
def test_migration_turns_existing_leaders_into_team_leaders():
    db_file = Path(tempfile.mkdtemp(prefix="wewin-migration-")) / "m.db"
    url = f"sqlite:///{db_file}"
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    command.upgrade(config, "0003")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO organizations (id, name, created_at) VALUES (1, 'Org', CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO teams (id, organization_id, name, created_at) VALUES (5, 1, 'Sales', CURRENT_TIMESTAMP)"))
        for uid, role in ((1, "team_leader"), (2, "member")):
            conn.execute(text(
                "INSERT INTO users (id, organization_id, team_id, email, full_name, password_hash, role, is_active, "
                "must_change_password, failed_login_count, password_changed_at, created_at, updated_at) VALUES "
                f"({uid}, 1, 5, 'u{uid}@x.co', '', 'h', '{role}', 1, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            ))
    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT team_id, user_id FROM team_leaders")).all() == [(5, 1)]
        assert dict(conn.execute(text("SELECT id, team_id FROM users ORDER BY id")).all()) == {1: None, 2: 5}
    command.downgrade(config, "0003")
    with engine.connect() as conn:
        assert dict(conn.execute(text("SELECT id, team_id FROM users ORDER BY id")).all()) == {1: 5, 2: 5}
    engine.dispose()
