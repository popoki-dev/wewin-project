"""Server test fixtures.

Uses PostgreSQL when WEWIN_TEST_DATABASE_URL is set (recommended), otherwise a
temporary SQLite file. The schema is always built with the Alembic migrations.
"""

import os
import tempfile
from pathlib import Path

import pytest

_db_url = os.environ.get("WEWIN_TEST_DATABASE_URL") or f"sqlite:///{tempfile.mkdtemp(prefix='wewin-test-')}/test.db"
os.environ["WEWIN_DATABASE_URL"] = _db_url
os.environ["WEWIN_SECRET_KEY"] = "test-secret-key-for-unit-tests-only-0123456789"
os.environ["WEWIN_ENVIRONMENT"] = "development"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from server.app.core.config import settings  # noqa: E402
from server.app.database.connection import engine  # noqa: E402
from server.app.database.session import SessionLocal  # noqa: E402
from server.app.models import Base  # noqa: E402
from server.app.services import mail_service  # noqa: E402
from server.app.services.setup_service import ensure_owner  # noqa: E402
from server.main import create_app  # noqa: E402

OWNER_EMAIL = "admin9531@gmail.com"
OWNER_PASSWORD = "asdqwe!@#123"
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "server" / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = _db_url
    config.attributes["configure_logger"] = False
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    tables = [t.name for t in reversed(Base.metadata.sorted_tables)]
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        else:
            for table in tables:
                conn.execute(text(f"DELETE FROM {table}"))
    with SessionLocal() as db:
        ensure_owner(db, settings)
    yield


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(mail_service, "send_password_reset_code", lambda to, code, minutes: sent.append((to, code)))
    return sent


@pytest.fixture()
def app(outbox):
    return create_app()


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c
