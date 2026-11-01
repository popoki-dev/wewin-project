from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import AwareDateTime, Base, utcnow

if TYPE_CHECKING:
    from .user import User


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)

    users: Mapped[list[User]] = relationship(back_populates="organization")
