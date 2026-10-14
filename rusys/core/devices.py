# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Removable device enumeration for Rusys.

This is OS-aware: on Linux it reads sysfs to list real block devices. On other
platforms (or when run without privileges) it falls back gracefully so the UI
still renders. A regular file may also be used as a target (handy for creating
DD images or for safe testing).
"""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from typing import List, Optional

from .logger import log


@dataclass
class Device:
    path: str                 # e.g. /dev/sdb  (or a regular file path)
    model: str = ""
    size_bytes: int = 0
    removable: bool = True
    mounted: bool = False
    mount_points: List[str] = field(default_factory=list)
    is_file: bool = False     # True when the target is a regular file
    bus_type: str = ""

    @property
    def size_human(self) -> str:
        return human_size(self.size_bytes)

    @property
    def display(self) -> str:
        if self.is_file:
            return f"{os.path.basename(self.path)} ({self.size_human})"
        label = self.model or os.path.basename(self.path)
        return f"{self.path}  -  {label}  ({self.size_human})"


def human_size(n: int) -> str:
    if n is None or n <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.1f} {u}" if u != "B" else f"{int(f)} {u}"
        f /= 1024.0
    return "0 B"


def _read_sys(path: str) -> Optional[str]:
    try:
        with open(path, "r") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _is_mounted(dev_base: str) -> tuple[bool, List[str]]:
    """Cross-check /proc/mounts for any mount of this block device."""
    mounts: List[str] = []
    try:
        with open("/proc/mounts", "r") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 2:
                    continue
                dev = parts[0]
                mp = parts[1]
                base = os.path.basename(dev)
                if base == dev_base or base.startswith(dev_base):
                    mounts.append(mp)
    except OSError:
        pass
    return (len(mounts) > 0, mounts)


def _is_usb_device(name: str, sys_block: str) -> bool:
    """Check if a block device is connected via USB bus.

    Many USB flash drives report ``removable=0`` in sysfs, so we also
    check the device symlink target for ``/usb`` and the bus type.
    """
    # Check removable flag first (floppy, card readers, some USB sticks)
    if _read_sys(os.path.join(sys_block, name, "removable")) == "1":
        return True
    # Check if the device symlink points to a USB device
    device_link = os.path.join(sys_block, name, "device")
    try:
        real_path = os.path.realpath(device_link)
        if "/usb" in real_path:
            return True
    except OSError:
        pass
    # Check the uevent for USB bus
    uevent = _read_sys(os.path.join(sys_block, name, "device", "uevent")) or ""
    for line in uevent.splitlines():
        if line.startswith("DRIVER=") and "usb" in line.split("=", 1)[1].lower():
            return True
        if line.startswith("BUSNUM="):
            return True
    # Check if the device has a USB parent in sysfs
    try:
        subsystem = os.path.realpath(
            os.path.join(sys_block, name, "device", "subsystem")
        )
        if "usb" in subsystem.lower():
            return True
    except OSError:
        pass
    return False


def enumerate_linux() -> List[Device]:
    devices: List[Device] = []
    sys_block = "/sys/block"
    if not os.path.isdir(sys_block):
        return devices
    for name in sorted(os.listdir(sys_block)):
        # Skip loop, ram, dm and partition entries (partitions live under device)
        if name.startswith(("loop", "ram", "dm-", "sr")):
            continue
        dev_path = f"/dev/{name}"
        # Detect USB devices (including those that don't report removable=1)
        is_usb = _is_usb_device(name, sys_block)
        removable = _read_sys(os.path.join(sys_block, name, "removable")) == "1"
        # Only surface removable media or USB devices
        if not removable and not is_usb:
            continue
        try:
            size_sectors = int(_read_sys(os.path.join(sys_block, name, "size")) or "0")
        except ValueError:
            size_sectors = 0
        size_bytes = size_sectors * 512
        model = (_read_sys(os.path.join(sys_block, name, "device", "model")) or "").strip()
        bus = (_read_sys(os.path.join(sys_block, name, "device", "uevent")) or "")
        bus_type = "usb" if is_usb else ""
        if not bus_type:
            for line in bus.splitlines():
                if line.startswith("DRIVER="):
                    bus_type = line.split("=", 1)[1]
        mounted, mps = _is_mounted(name)
        if os.path.exists(dev_path):
            devices.append(
                Device(
                    path=dev_path,
                    model=model,
                    size_bytes=size_bytes,
                    removable=True,
                    mounted=mounted,
                    mount_points=mps,
                    is_file=False,
                    bus_type=bus_type,
                )
            )
    return devices


def enumerate_devices() -> List[Device]:
    """Return the list of candidate target devices for the current OS."""
    system = platform.system().lower()
    try:
        if system == "linux":
            return enumerate_linux()
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Device enumeration failed: %s", exc)
    return []


def add_file_target(path: str) -> Optional[Device]:
    if not os.path.isfile(path):
        return None
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    return Device(path=path, size_bytes=size, removable=True, is_file=True)


def reprobe_device(device: Device) -> Device:
    """Re-read device metadata from sysfs (size, mount status, model).

    Useful after unmounting or wiping a device when the cached data may
    be stale.
    """
    if device.is_file:
        try:
            device.size_bytes = os.path.getsize(device.path)
        except OSError:
            pass
        return device
    base = os.path.basename(device.path)
    sys_block = "/sys/block"
    # Re-read size
    try:
        size_sectors = int(_read_sys(os.path.join(sys_block, base, "size")) or "0")
        device.size_bytes = size_sectors * 512
    except (ValueError, OSError):
        pass
    # Re-read mount status
    mounted, mps = _is_mounted(base)
    device.mounted = mounted
    device.mount_points = mps
    # Re-read model
    model = (_read_sys(os.path.join(sys_block, base, "device", "model")) or "").strip()
    if model:
        device.model = model
    return device


def ensure_safe_target(device: Device) -> None:
    """Raise a clear error if flashing *device* is unsafe (issue #1778/#2244).

    If the device reports ``size_bytes == 0`` we attempt one re-probe from
    sysfs before failing — some USB drives only report their size after
    the partition table is wiped.
    """
    if device.mounted:
        raise RuntimeError(
            f"Target '{device.path}' is still mounted at "
            f"{', '.join(device.mount_points)}. Unmount it before flashing."
        )
    if not device.is_file and not os.path.exists(device.path):
        raise RuntimeError(f"Target device not found: {device.path}")
    if device.size_bytes <= 0:
        # Try re-probing once (size may become visible after wipefs)
        reprobe_device(device)
    if device.size_bytes <= 0:
        raise RuntimeError(
            f"Cannot determine a valid size for: {device.path}.  "
            "Make sure the USB drive is properly connected and not "
            "hardware-locked (read-only switch)."
        )
