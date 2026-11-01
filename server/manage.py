"""Server management commands.

    python -m server.manage init      apply migrations, then create the initial owner if needed
    python -m server.manage migrate   apply migrations only
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from server.app.core.config import settings
from server.app.database.session import SessionLocal
from server.app.services.setup_service import SetupError, ensure_owner

ALEMBIC_INI = Path(__file__).with_name("alembic.ini")


def migrate() -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def init() -> None:
    migrate()
    with SessionLocal() as db:
        ensure_owner(db, settings)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="python -m server.manage")
    parser.add_argument("command", choices=["init", "migrate"])
    args = parser.parse_args()
    try:
        {"init": init, "migrate": migrate}[args.command]()
    except SetupError as exc:
        raise SystemExit(f"Setup failed: {exc}") from None


if __name__ == "__main__":
    main()
