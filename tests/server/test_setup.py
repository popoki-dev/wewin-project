import pytest
from sqlalchemy import delete

from server.app.core.config import settings
from server.app.database.session import SessionLocal
from server.app.models import User
from server.app.repositories.user_repository import UserRepository
from server.app.services.setup_service import DEV_OWNER_PASSWORD, SetupError, ensure_owner


def _setup(**overrides) -> User | None:
    """Run first-start setup on a database without an owner."""
    with SessionLocal() as db:
        db.execute(delete(User))
        db.commit()
        ensure_owner(db, settings.model_copy(update=overrides))
        return UserRepository(db).any_owner()


def test_production_rejects_the_development_default_password():
    with pytest.raises(SetupError, match="development default"):
        _setup(environment="production", owner_password=DEV_OWNER_PASSWORD)


@pytest.mark.parametrize("password", ["change-me", "short1!", "alllowercaseletters"])
def test_weak_owner_password_is_rejected(password):
    with pytest.raises(SetupError, match="too weak"):
        _setup(owner_password=password)


def test_production_accepts_a_strong_password():
    owner = _setup(environment="production", owner_password="Correct-Horse-42")
    assert owner is not None


def test_existing_owner_is_left_alone_whatever_the_password():
    with SessionLocal() as db:
        ensure_owner(db, settings.model_copy(update={"environment": "production", "owner_password": "change-me"}))
