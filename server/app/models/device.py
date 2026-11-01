from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import AwareDateTime, Base, utcnow


class Device(Base):
    """The one PC an account is bound to, from its first sign-in until the binding is reset.

    The device secret is never stored: it is derived from the server secret and
    `secret_nonce`, so a database dump alone cannot sign requests.
    """

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    device_id: Mapped[str] = mapped_column(String(64))
    secret_nonce: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)


class DeviceRequestNonce(Base):
    """Recently seen request nonces, so a captured signed request cannot be replayed."""

    __tablename__ = "device_request_nonces"
    __table_args__ = (UniqueConstraint("device_pk", "nonce"),)

    # BIGINT on PostgreSQL; INTEGER on SQLite so it stays an auto-increment rowid.
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    device_pk: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    nonce: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow, index=True)
