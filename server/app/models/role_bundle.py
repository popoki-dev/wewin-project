from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import AwareDateTime, Base, utcnow

# Which role bundles each user holds.
user_role_bundles = Table(
    "user_role_bundles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("bundle_id", ForeignKey("role_bundles.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class RoleBundle(Base):
    """A named set of permissions (see shared/permissions.py), defined by the Owner."""

    __tablename__ = "role_bundles"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(300), default="")
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
