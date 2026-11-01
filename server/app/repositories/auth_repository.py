from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import PasswordResetCode, RefreshSession


class RefreshSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_token_hash(self, token_hash: str, *, for_update: bool = False) -> RefreshSession | None:
        query = select(RefreshSession).where(RefreshSession.token_hash == token_hash)
        if for_update:
            query = query.with_for_update()
        return self.db.scalar(query)

    def add(self, session: RefreshSession) -> RefreshSession:
        self.db.add(session)
        self.db.flush()
        return session

    def revoke_all_for_user(self, user_id: int, now: datetime) -> None:
        self.db.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )


class PasswordResetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def latest_unused(self, user_id: int, *, for_update: bool = False) -> PasswordResetCode | None:
        query = (
            select(PasswordResetCode)
            .where(PasswordResetCode.user_id == user_id, PasswordResetCode.used_at.is_(None))
            .order_by(PasswordResetCode.created_at.desc(), PasswordResetCode.id.desc())
            .limit(1)
        )
        if for_update:
            query = query.with_for_update()
        return self.db.scalar(query)

    def invalidate_all(self, user_id: int, now: datetime) -> None:
        self.db.execute(
            update(PasswordResetCode)
            .where(PasswordResetCode.user_id == user_id, PasswordResetCode.used_at.is_(None))
            .values(used_at=now)
        )

    def add(self, code: PasswordResetCode) -> PasswordResetCode:
        self.db.add(code)
        self.db.flush()
        return code
