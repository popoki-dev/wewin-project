from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.enums import Role
from shared.permissions import Permission, effective_permissions

from .base import AwareDateTime, Base, utcnow
from .role_bundle import RoleBundle, user_role_bundles

if TYPE_CHECKING:
    from .organization import Organization
    from .team import Team


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    # Members and team leaders belong to one team; the owner to none.
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    # Sign-in is by email alone, so emails are unique across organizations.
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=Role.MEMBER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set for accounts created with an initial password; cleared by the first password change.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    password_changed_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow, onupdate=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="users")
    team: Mapped[Team | None] = relationship()
    role_bundles: Mapped[list[RoleBundle]] = relationship(
        secondary=user_role_bundles, lazy="selectin", order_by=RoleBundle.name
    )

    @property
    def permissions(self) -> set[Permission]:
        """Base role permissions plus those of every assigned role bundle."""
        return effective_permissions(self.role, (p for b in self.role_bundles for p in b.permissions))

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions
