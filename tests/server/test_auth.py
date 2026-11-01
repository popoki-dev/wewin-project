from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from server.app.core.security import hash_password
from server.app.database.session import SessionLocal
from server.app.models import AuditLog, PasswordResetCode, User
from shared.api_contracts import Paths
from shared.enums import AuditAction

OWNER_EMAIL = "admin9531@gmail.com"
OWNER_PASSWORD = "asdqwe!@#123"
NEW_PASSWORD = "N3w-Secure!pass"


def login(client, email=OWNER_EMAIL, password=OWNER_PASSWORD, remember_me=False):
    return client.post(Paths.AUTH_LOGIN, json={"email": email, "password": password, "remember_me": remember_me})


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def audit_actions() -> list[str]:
    with SessionLocal() as db:
        return list(db.scalars(select(AuditLog.action).order_by(AuditLog.id)))


def test_health_reports_database(client):
    body = client.get(Paths.HEALTH).json()
    assert body["app"] == "WeWin" and body["database"] == "ok"


def test_owner_is_seeded_with_argon2id_hash(client):
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == OWNER_EMAIL))
    assert owner is not None and owner.role.value == "owner"
    assert owner.password_hash.startswith("$argon2id$")


def test_owner_can_log_in(client):
    r = login(client)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["role"] == "owner"
    me = client.get(Paths.AUTH_ME, headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == OWNER_EMAIL
    assert AuditAction.LOGIN_SUCCEEDED.value in audit_actions()


def test_email_is_case_insensitive(client):
    assert login(client, email="  Admin9531@Gmail.com ").status_code == 200


def test_wrong_password_and_unknown_user_look_the_same(client):
    a = login(client, password="nope")
    b = login(client, email="ghost@example.com")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()
    assert audit_actions().count(AuditAction.LOGIN_FAILED.value) == 2


def test_invalid_email_is_rejected_with_plain_message(client):
    r = login(client, email="not-an-email")
    assert r.status_code == 422 and r.json()["detail"] == "Enter a valid email address."


def test_remember_me_extends_session(client):
    short = parse_time(login(client).json()["refresh_expires_at"])
    long = parse_time(login(client, remember_me=True).json()["refresh_expires_at"])
    assert long - short > timedelta(days=7)


def test_lockout_after_repeated_failures(client):
    for _ in range(5):
        assert login(client, password="wrong").status_code == 401
    r = login(client)
    assert r.status_code == 429 and "Try again" in r.json()["detail"]
    assert AuditAction.ACCOUNT_LOCKED.value in audit_actions()


def test_disabled_account_cannot_log_in(client):
    with SessionLocal() as db:
        db.execute(update(User).values(is_active=False))
        db.commit()
    assert login(client).status_code == 403


def test_refresh_rotates_and_detects_reuse(client):
    first = login(client, remember_me=True).json()["refresh_token"]
    r = client.post(Paths.AUTH_REFRESH, json={"refresh_token": first})
    assert r.status_code == 200
    second = r.json()["refresh_token"]
    assert second != first

    # Replaying the rotated-out token ends every session of that user.
    assert client.post(Paths.AUTH_REFRESH, json={"refresh_token": first}).status_code == 401
    assert client.post(Paths.AUTH_REFRESH, json={"refresh_token": second}).status_code == 401
    assert AuditAction.SESSION_REUSE_DETECTED.value in audit_actions()


def test_logout_revokes_refresh_token(client):
    token = login(client).json()["refresh_token"]
    assert client.post(Paths.AUTH_LOGOUT, json={"refresh_token": token}).status_code == 200
    assert client.post(Paths.AUTH_REFRESH, json={"refresh_token": token}).status_code == 401


def test_me_requires_valid_token(client):
    assert client.get(Paths.AUTH_ME).status_code == 401
    assert client.get(Paths.AUTH_ME, headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_legacy_hash_is_upgraded_on_login(client):
    # A hash with weaker parameters is transparently re-hashed with the current ones.
    from argon2 import PasswordHasher

    weak = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(OWNER_PASSWORD)
    with SessionLocal() as db:
        db.execute(update(User).values(password_hash=weak))
        db.commit()
    assert login(client).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(User.password_hash)) != weak


def test_forgot_password_does_not_reveal_accounts(client, outbox):
    a = client.post(Paths.AUTH_FORGOT_PASSWORD, json={"email": OWNER_EMAIL})
    b = client.post(Paths.AUTH_FORGOT_PASSWORD, json={"email": "ghost@example.com"})
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()
    assert [to for to, _ in outbox] == [OWNER_EMAIL]


def test_forgot_password_is_throttled(client, outbox):
    client.post(Paths.AUTH_FORGOT_PASSWORD, json={"email": OWNER_EMAIL})
    client.post(Paths.AUTH_FORGOT_PASSWORD, json={"email": OWNER_EMAIL})
    assert len(outbox) == 1


def test_full_password_reset_flow(client, outbox):
    old_refresh = login(client, remember_me=True).json()["refresh_token"]
    client.post(Paths.AUTH_FORGOT_PASSWORD, json={"email": OWNER_EMAIL})
    code = outbox[-1][1]

    weak = client.post(Paths.AUTH_RESET_PASSWORD, json={"email": OWNER_EMAIL, "code": code, "new_password": "short"})
    assert weak.status_code == 422

    wrong = "000000" if code != "000000" else "111111"
    bad = client.post(Paths.AUTH_RESET_PASSWORD, json={"email": OWNER_EMAIL, "code": wrong, "new_password": NEW_PASSWORD})
    assert bad.status_code == 400

    ok = client.post(Paths.AUTH_RESET_PASSWORD, json={"email": OWNER_EMAIL, "code": code, "new_password": NEW_PASSWORD})
    assert ok.status_code == 200, ok.text

    assert login(client).status_code == 401
    assert login(client, password=NEW_PASSWORD).status_code == 200
    assert client.post(Paths.AUTH_REFRESH, json={"refresh_token": old_refresh}).status_code == 401
    again = client.post(Paths.AUTH_RESET_PASSWORD, json={"email": OWNER_EMAIL, "code": code, "new_password": NEW_PASSWORD})
    assert again.status_code == 400
    assert AuditAction.PASSWORD_RESET_COMPLETED.value in audit_actions()


def test_reset_code_burns_after_too_many_attempts(client, outbox):
    client.post(Paths.AUTH_FORGOT_PASSWORD, json={"email": OWNER_EMAIL})
    code = outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        client.post(Paths.AUTH_RESET_PASSWORD, json={"email": OWNER_EMAIL, "code": wrong, "new_password": NEW_PASSWORD})
    r = client.post(Paths.AUTH_RESET_PASSWORD, json={"email": OWNER_EMAIL, "code": code, "new_password": NEW_PASSWORD})
    assert r.status_code == 400


def test_expired_reset_code_is_rejected(client, outbox):
    client.post(Paths.AUTH_FORGOT_PASSWORD, json={"email": OWNER_EMAIL})
    code = outbox[-1][1]
    with SessionLocal() as db:
        db.execute(update(PasswordResetCode).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    r = client.post(Paths.AUTH_RESET_PASSWORD, json={"email": OWNER_EMAIL, "code": code, "new_password": NEW_PASSWORD})
    assert r.status_code == 400


def test_member_account_signs_in_as_member(client):
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == OWNER_EMAIL))
        db.add(User(organization_id=owner.organization_id, email="member@example.com",
                    password_hash=hash_password("Member-pass-1")))
        db.commit()
    r = login(client, email="member@example.com", password="Member-pass-1")
    assert r.status_code == 200 and r.json()["user"]["role"] == "member"
