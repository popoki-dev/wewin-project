"""The PC's device identifier: a SHA-256 hash of its MAC address."""

from __future__ import annotations

import logging
import os
import uuid

from PySide6.QtNetwork import QNetworkInterface

from shared.device_signature import device_id_from_mac

log = logging.getLogger("wewin.device")

# Testing only: pretend to be another PC (e.g. WEWIN_DEVICE_MAC=02:00:00:00:00:01).
MAC_OVERRIDE_ENV = "WEWIN_DEVICE_MAC"

# Virtual adapters come and go (Docker, VPNs, VMs), so they must not identify the PC.
_VIRTUAL_PREFIXES = (
    "docker", "veth", "br-", "virbr", "vmnet", "vboxnet", "vethernet", "tun", "tap", "wg",
    "zt", "utun", "awdl", "llw", "bridge", "lo",
)


def _is_universal(mac: str) -> bool:
    """False for locally administered addresses (randomised Wi-Fi MACs, VMs)."""
    try:
        return not int(mac.split(":")[0], 16) & 0x02
    except ValueError:
        return False


def primary_mac() -> str:
    """The MAC of the PC's first physical adapter: wired before wireless, then by name.

    Up/down state is ignored, so unplugging a cable does not change the result.
    """
    override = os.environ.get(MAC_OVERRIDE_ENV, "").strip()
    if override:
        return override.upper()

    wired, wireless = QNetworkInterface.InterfaceType.Ethernet, QNetworkInterface.InterfaceType.Wifi
    candidates = []
    for iface in QNetworkInterface.allInterfaces():
        mac = iface.hardwareAddress().upper()
        if not mac or mac == "00:00:00:00:00:00" or not _is_universal(mac):
            continue
        if iface.flags() & QNetworkInterface.InterfaceFlag.IsLoopBack:
            continue
        if iface.type() not in (wired, wireless) or iface.name().lower().startswith(_VIRTUAL_PREFIXES):
            continue
        candidates.append((iface.type() != wired, iface.name(), mac))
    if candidates:
        return sorted(candidates)[0][2]

    log.warning("No physical network adapter found; using the system node ID")
    node = uuid.getnode()
    return ":".join(f"{(node >> shift) & 0xFF:02X}" for shift in range(40, -1, -8))


def device_id() -> str:
    return device_id_from_mac(primary_mac())
