from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from shared.enums import AuditAction

from ..models import AuditLog


@dataclass(frozen=True)
class ClientInfo:
    """Who is making a request, for audit records."""

    ip_address: str = ""
    user_agent: str = ""


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        action: AuditAction,
        client: ClientInfo,
        *,
        user_id: int | None = None,
        organization_id: int | None = None,
        **details: Any,
    ) -> None:
        self.db.add(
            AuditLog(
                action=action.value,
                user_id=user_id,
                organization_id=organization_id,
                ip_address=client.ip_address[:45],
                user_agent=client.user_agent[:255],
                details=details,
            )
        )
