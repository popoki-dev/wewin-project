import pytest
from fastapi import Depends
from sqlalchemy import select

from server.app.core.permissions import require_role
from server.app.core.security import hash_password
from server.app.database.session import SessionLocal
from server.app.models import User
from shared.device_signature import device_id_from_mac
from shared.enums import Role
from tests.server.helpers import OWNER_EMAIL, OWNER_PASSWORD, sign_in


@pytest.fixture()
def app(app):
    @app.get("/test/leaders-only")
    def leaders_only(user: User = Depends(require_role(Role.TEAM_LEADER))):
        return {"email": user.email}

    return app


def add_user(email: str, role: Role) -> None:
    with SessionLocal() as db:
        org_id = db.scalar(select(User.organization_id).limit(1))
        db.add(User(organization_id=org_id, email=email, role=role, password_hash=hash_password("Pass-word-1")))
        db.commit()


def test_role_ranking():
    assert Role.OWNER.at_least(Role.TEAM_LEADER)
    assert Role.TEAM_LEADER.at_least(Role.TEAM_LEADER)
    assert not Role.MEMBER.at_least(Role.TEAM_LEADER)


def test_require_role_allows_owner_and_team_leader_but_not_member(client):
    add_user("leader@example.com", Role.TEAM_LEADER)
    add_user("member@example.com", Role.MEMBER)

    owner = sign_in(client, OWNER_EMAIL, OWNER_PASSWORD)
    leader = sign_in(client, "leader@example.com", "Pass-word-1", device_id=device_id_from_mac("02:00:00:00:00:01"))
    member = sign_in(client, "member@example.com", "Pass-word-1", device_id=device_id_from_mac("02:00:00:00:00:02"))

    assert owner.get("/test/leaders-only").status_code == 200
    assert leader.get("/test/leaders-only").status_code == 200
    assert member.get("/test/leaders-only").status_code == 403
    assert client.get("/test/leaders-only").status_code == 401
