from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Device, DeviceRequestNonce


class DeviceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user(self, user_id: int) -> Device | None:
        return self.db.scalar(select(Device).where(Device.user_id == user_id))

    def add(self, device: Device) -> Device:
        self.db.add(device)
        self.db.flush()
        return device

    def delete_for_user(self, user_id: int) -> bool:
        return self.db.execute(delete(Device).where(Device.user_id == user_id)).rowcount > 0

    def bound_user_ids(self, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        return set(self.db.scalars(select(Device.user_id).where(Device.user_id.in_(user_ids))))

    # Replay protection -------------------------------------------------------
    def nonce_seen(self, device_pk: int, nonce: str) -> bool:
        query = select(DeviceRequestNonce.id).where(
            DeviceRequestNonce.device_pk == device_pk, DeviceRequestNonce.nonce == nonce
        )
        return self.db.scalar(query) is not None

    def add_nonce(self, device_pk: int, nonce: str) -> None:
        self.db.add(DeviceRequestNonce(device_pk=device_pk, nonce=nonce))
        self.db.flush()

    def forget_nonces_before(self, device_pk: int, cutoff: datetime) -> None:
        self.db.execute(
            delete(DeviceRequestNonce).where(
                DeviceRequestNonce.device_pk == device_pk, DeviceRequestNonce.created_at < cutoff
            )
        )
