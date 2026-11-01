"""Server management commands.

    python -m server.manage init      apply migrations, then create the initial owner if needed
    python -m server.manage migrate   apply migrations only
    python -m server.manage reset-device EMAIL
                                      unbind an account's PC (e.g. the Owner's), so its next
                                      sign-in registers the PC it is made from
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from server.app.core.config import settings
from server.app.database.session import SessionLocal
from server.app.repositories.audit_repository import ClientInfo
from server.app.repositories.user_repository import UserRepository
from server.app.schemas.auth import normalize_email
from server.app.services.device_service import DeviceService
from server.app.services.setup_service import SetupError, ensure_owner

ALEMBIC_INI = Path(__file__).with_name("alembic.ini")


def migrate() -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def init() -> None:
    migrate()
    with SessionLocal() as db:
        ensure_owner(db, settings)


def reset_device(email: str) -> None:
    with SessionLocal() as db:
        user = UserRepository(db).get_by_email(normalize_email(email))
        if user is None:
            raise SystemExit(f"No account with email {email}")
        removed = DeviceService(db).reset(user, None, ClientInfo())
        db.commit()
    print(f"Device registration for {user.email} {'reset' if removed else 'was already empty'}; sessions ended.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="python -m server.manage")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    commands.add_parser("migrate")
    commands.add_parser("reset-device").add_argument("email")
    args = parser.parse_args()
    try:
        if args.command == "reset-device":
            reset_device(args.email)
        else:
            {"init": init, "migrate": migrate}[args.command]()
    except SetupError as exc:
        raise SystemExit(f"Setup failed: {exc}") from None


if __name__ == "__main__":
    main()
