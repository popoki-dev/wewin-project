from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from server.app.database.session import SessionLocal
from server.app.models import AuditLog
from server.manage import reset_device
from shared import device_signature as ds
from shared.api_contracts import Paths
from shared.enums import AuditAction
from tests.server.helpers import OWNER_EMAIL, PC_A, PC_B, DeviceSession, login, sign_in


def audit_actions() -> list[str]:
    with SessionLocal() as db:
        return list(db.scalars(select(AuditLog.action).order_by(AuditLog.id)))


def test_first_sign_in_registers_the_pc_and_issues_a_secret(client):
    r = login(client)
    assert r.status_code == 200
    assert len(r.json()["device_secret"]) == 64
    assert AuditAction.DEVICE_REGISTERED.value in audit_actions()


def test_device_id_must_be_a_sha256_hash(client):
    r = login(client, device_id="00:11:22:33:44:55")
    assert r.status_code == 422


def test_other_pc_is_refused_until_the_device_is_reset(client):
    sign_in(client, device_id=PC_A)
    r = login(client, device_id=PC_B)
    assert r.status_code == 403 and "another computer" in r.json()["detail"]
    assert AuditAction.DEVICE_REJECTED.value in audit_actions()

    reset_device(OWNER_EMAIL)
    assert login(client, device_id=PC_B).status_code == 200
    assert login(client, device_id=PC_A).status_code == 403


def test_wrong_password_from_other_pc_does_not_reveal_the_binding(client):
    sign_in(client, device_id=PC_A)
    assert login(client, password="wrong", device_id=PC_B).status_code == 401


def test_requests_need_a_valid_signature(client):
    session = sign_in(client)
    bearer_only = {"Authorization": f"Bearer {session.access_token}"}
    assert client.get(Paths.AUTH_ME, headers=bearer_only).status_code == 401

    tokens = {"access_token": session.access_token, "refresh_token": session.refresh_token, "user": session.user}
    forged = DeviceSession(client, tokens, device_secret="0" * 64)
    assert forged.get(Paths.AUTH_ME).status_code == 401
    assert session.get(Paths.AUTH_ME).status_code == 200


def test_signature_from_another_device_id_is_refused(client):
    session = sign_in(client)
    session.device_id = PC_B
    assert session.get(Paths.AUTH_ME).status_code == 401


def test_signature_covers_the_path(client):
    session = sign_in(client)
    headers = session.headers("GET", Paths.TEAMS)
    assert client.get(Paths.AUTH_ME, headers=headers).status_code == 401


def test_replayed_request_is_refused(client):
    session = sign_in(client)
    headers = session.headers("GET", Paths.AUTH_ME)
    assert client.get(Paths.AUTH_ME, headers=headers).status_code == 200
    assert client.get(Paths.AUTH_ME, headers=headers).status_code == 401


def test_stale_timestamp_is_refused(client):
    session = sign_in(client)
    old = ds.utc_timestamp(datetime.now(timezone.utc) - timedelta(seconds=ds.MAX_CLOCK_SKEW_SECONDS + 30))
    nonce = "n" * 24
    headers = {
        "Authorization": f"Bearer {session.access_token}",
        ds.DEVICE_HEADER: PC_A,
        ds.TIMESTAMP_HEADER: old,
        ds.NONCE_HEADER: nonce,
        ds.SIGNATURE_HEADER: ds.sign(session.device_secret, PC_A, OWNER_EMAIL, old, nonce, "GET", Paths.AUTH_ME),
    }
    r = client.get(Paths.AUTH_ME, headers=headers)
    assert r.status_code == 401 and "clock" in r.json()["detail"]


def test_refresh_needs_a_signature(client):
    session = sign_in(client)
    assert client.post(Paths.AUTH_REFRESH, json={"refresh_token": session.refresh_token}).status_code == 401
    assert session.refresh().status_code == 200


def test_each_sign_in_retires_the_previous_secret(client):
    first = sign_in(client)
    second = sign_in(client)
    assert first.device_secret != second.device_secret
    assert first.get(Paths.AUTH_ME).status_code == 401
    assert second.get(Paths.AUTH_ME).status_code == 200


def test_device_reset_ends_sessions(client):
    session = sign_in(client, remember_me=True)
    reset_device(OWNER_EMAIL)
    assert session.get(Paths.AUTH_ME).status_code == 401
    assert session.refresh().status_code == 401
    assert AuditAction.DEVICE_RESET.value in audit_actions()


def test_signing_is_deterministic_and_email_case_insensitive():
    a = ds.sign("k", PC_A, "A@Example.com", "2026-11-02T00:00:00.000Z", "nonce-nonce-nonce", "get", "/x")
    b = ds.sign("k", PC_A, "a@example.com", "2026-11-02T00:00:00.000Z", "nonce-nonce-nonce", "GET", "/x")
    assert a == b
    assert ds.parse_timestamp(ds.utc_timestamp(datetime(2026, 11, 2, tzinfo=timezone.utc))).year == 2026
