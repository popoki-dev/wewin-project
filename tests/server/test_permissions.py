import pytest
from fastapi import Depends
from sqlalchemy import select

from server.app.core.permissions import require_role
from server.app.core.security import hash_password
from server.app.database.session import SessionLocal
from server.app.models import User
from shared.api_contracts import Paths
from shared.enums import Role


@pytest.fixture()
def app(app):
    @app.get("/test/admin-only")
    def admin_only(user: User = Depends(require_role(Role.ADMIN))):
        return {"email": user.email}

    return app


def token_for(client, email, password):
    r = client.post(Paths.AUTH_LOGIN, json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def add_user(email: str, role: Role) -> None:
    with SessionLocal() as db:
        org_id = db.scalar(select(User.organization_id).limit(1))
        db.add(User(organization_id=org_id, email=email, role=role, password_hash=hash_password("Pass-word-1")))
        db.commit()


def test_role_ranking():
    assert Role.OWNER.at_least(Role.ADMIN)
    assert Role.ADMIN.at_least(Role.ADMIN)
    assert not Role.MEMBER.at_least(Role.ADMIN)


def test_require_role_allows_owner_and_admin_but_not_member(client):
    add_user("admin@example.com", Role.ADMIN)
    add_user("member@example.com", Role.MEMBER)

    owner = token_for(client, "admin9531@gmail.com", "asdqwe!@#123")
    admin = token_for(client, "admin@example.com", "Pass-word-1")
    member = token_for(client, "member@example.com", "Pass-word-1")

    assert client.get("/test/admin-only", headers=owner).status_code == 200
    assert client.get("/test/admin-only", headers=admin).status_code == 200
    assert client.get("/test/admin-only", headers=member).status_code == 403
    assert client.get("/test/admin-only").status_code == 401
