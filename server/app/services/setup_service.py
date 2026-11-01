from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from shared.enums import AuditAction, Role

from ..core.config import Settings
from ..core.security import hash_password, validate_password_strength
from ..models import Organization, User
from ..repositories.audit_repository import AuditRepository, ClientInfo
from ..repositories.user_repository import OrganizationRepository, UserRepository
from ..schemas.auth import normalize_email

log = logging.getLogger("wewin.setup")

# The development default is published in the README, so it must never protect a real server.
DEV_OWNER_PASSWORD = Settings.model_fields["owner_password"].default


class SetupError(RuntimeError):
    pass


def check_owner_password(settings: Settings) -> None:
    if settings.environment == "production" and settings.owner_password == DEV_OWNER_PASSWORD:
        raise SetupError("Set WEWIN_OWNER_PASSWORD: the development default cannot be used in production")
    if (problem := validate_password_strength(settings.owner_password)) is not None:
        raise SetupError(f"WEWIN_OWNER_PASSWORD is too weak. {problem}")


def ensure_owner(db: Session, settings: Settings) -> None:
    """Create the organization and its owner on first start (no-op once an owner exists)."""
    users = UserRepository(db)
    if users.any_owner() is not None:
        return
    check_owner_password(settings)

    email = normalize_email(settings.owner_email)
    if users.get_by_email(email) is not None:
        log.error("Cannot create owner: %s already exists with another role", email)
        return

    organization = OrganizationRepository(db).first() or OrganizationRepository(db).add(
        Organization(name=settings.organization_name)
    )
    owner = users.add(
        User(
            organization_id=organization.id,
            email=email,
            full_name=settings.owner_name,
            password_hash=hash_password(settings.owner_password),
            role=Role.OWNER,
        )
    )
    AuditRepository(db).record(
        AuditAction.USER_CREATED, ClientInfo(), user_id=owner.id, organization_id=organization.id, via="initial_setup"
    )
    db.commit()
    log.info("Created organization %r with owner %s", organization.name, email)
