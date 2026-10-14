# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Privilege escalation helpers for Rusys.

On Linux, writing to block devices (``/dev/sdX``) requires root privileges
by default.  This module provides two mechanisms to work around that:

1. **udev rule**: A one-time installation that grants write access to USB
   block devices for users in the ``disk`` group (or the current user via
   ``uaccess``).  After installing the rule and adding the user to the
   ``disk`` group, subsequent runs do **not** need elevated privileges.

2. **pkexec fallback**: If the udev rule is not installed (or the user
   declined), the flasher can use ``pkexec`` to run ``dd`` with
   temporary elevated privileges for the actual write operation.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Optional

from .logger import log


UDEV_RULE_PATH = "/etc/udev/rules.d/99-rusys-usb.rules"

UDEV_RULE_CONTENT = """\
# Rusys USB block device access
# Allows members of the 'disk' group to write to removable USB block devices
# so that Rusys can flash images without needing root/sudo.
#
# Install: sudo cp 99-rusys-usb.rules /etc/udev/rules.d/
#          sudo udevadm control --reload-rules
#          sudo udevadm trigger
#          sudo usermod -aG disk $USER   (then log out and back in)

# USB removable block devices — allow disk group write access
SUBSYSTEM=="block", KERNEL=="sd[a-z]", ATTR{removable}=="1", GROUP="disk", MODE="0660"
SUBSYSTEM=="block", KERNEL=="sd[a-z][0-9]*", ATTR{removable}=="1", GROUP="disk", MODE="0660"

# Also match USB devices detected by bus (for devices that don't report removable=1)
SUBSYSTEM=="block", KERNEL=="sd[a-z]", ATTRS{busnum}=="*", GROUP="disk", MODE="0660"
SUBSYSTEM=="block", KERNEL=="sd[a-z][0-9]*", ATTRS{busnum}=="*", GROUP="disk", MODE="0660"
"""


def is_udev_rule_installed() -> bool:
    """Check if the Rusys udev rule is already installed."""
    return os.path.isfile(UDEV_RULE_PATH)


def install_udev_rule() -> bool:
    """Install the udev rule and add the current user to the disk group.

    This requires root privileges (uses pkexec for the GUI prompt).
    Returns True if the installation succeeded.
    """
    if is_udev_rule_installed():
        log.info("udev rule already installed at %s", UDEV_RULE_PATH)
        return True

    # Build a script that does the installation
    script = f"""#!/bin/bash
set -e
cat > {UDEV_RULE_PATH} << 'UDEVRULE'
{UDEV_RULE_CONTENT}UDEVRULE
udevadm control --reload-rules
udevadm trigger
# Add current user to disk group if not already a member
if ! groups $(logname 2>/dev/null || echo $SUDO_USER) 2>/dev/null | grep -q disk; then
    usermod -aG disk $(logname 2>/dev/null || echo $SUDO_USER) 2>/dev/null || true
fi
echo "SUCCESS"
"""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, prefix="rusys_udev_"
        ) as fh:
            fh.write(script)
            script_path = fh.name
        os.chmod(script_path, 0o755)

        # Try pkexec first (graphical polkit prompt)
        result = subprocess.run(
            ["pkexec", script_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        os.unlink(script_path)

        if result.returncode == 0 and "SUCCESS" in (result.stdout or ""):
            log.info("udev rule installed successfully at %s", UDEV_RULE_PATH)
            return True
        else:
            log.warning(
                "udev rule installation failed (exit %d): %s %s",
                result.returncode,
                result.stdout or "",
                result.stderr or "",
            )
            return False
    except FileNotFoundError:
        log.warning("pkexec not found — cannot install udev rule automatically")
        return False
    except subprocess.TimeoutExpired:
        log.warning("udev rule installation timed out (user may have cancelled)")
        return False
    except Exception as exc:
        log.warning("udev rule installation failed: %s", exc)
        return False


def can_write_device(device_path: str) -> bool:
    """Check if the current user can write to the given block device."""
    if not os.path.exists(device_path):
        return False
    return os.access(device_path, os.W_OK)


def elevate_device_access(device_path: str, mode: str = "rw") -> bool:
    """Temporarily grant read/write access to a block device via pkexec.

    Uses ``pkexec chmod`` to open the device for the current user, so the
    normal Python write path (with progress callback) can be used instead
    of ``pkexec dd`` (which has no progress reporting).

    Returns True if the permission change succeeded.
    """
    if not shutil_which("pkexec"):
        return False
    # chmod: rw-rw-rw- (666) for write+read, or r--r--r-- (444) for read-only
    perm = "666" if mode == "rw" else "444"
    try:
        result = subprocess.run(
            ["pkexec", "chmod", perm, device_path],
            check=False,
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            log.info("Temporarily opened %s for %s access", device_path, mode)
            return True
        log.warning("pkexec chmod failed (exit %d)", result.returncode)
        return False
    except Exception as exc:
        log.warning("pkexec chmod failed: %s", exc)
        return False


def elevate_prepare_device(device_path: str) -> bool:
    """Unmount, wipe, and open a block device for writing in ONE pkexec prompt.

    This consolidates what would otherwise be 4-6 separate pkexec calls
    (umount partitions, umount device, wipefs, chmod rw) into a single
    helper script that runs under one authentication session.  The user
    sees only **one** password dialog instead of many.

    Returns True if the preparation succeeded.
    """
    if not shutil_which("pkexec"):
        return False

    base = os.path.basename(device_path)

    # Build a self-contained bash script that does everything at once.
    # This way pkexec only prompts once for the entire operation.
    script = f"""#!/bin/bash
set -e

DEV="{device_path}"
BASE="{base}"

# 1. Unmount all partitions of this device
for entry in $(ls /dev/ 2>/dev/null); do
    case "$entry" in
        "$BASE"[0-9]*)
            umount "/dev/$entry" 2>/dev/null || true
            ;;
    esac
done

# 2. Unmount the whole-disk device node
umount "$DEV" 2>/dev/null || true

# 3. Wipe partition table and filesystem signatures
if command -v wipefs >/dev/null 2>&1; then
    wipefs --all --force "$DEV" 2>/dev/null || true
else
    # Fallback: zero the first 1 MiB
    dd if=/dev/zero of="$DEV" bs=1M count=1 conv=fsync 2>/dev/null || true
fi

# 4. Open the device for read/write by the current user
chmod 666 "$DEV" 2>/dev/null || true

echo "PREPARE_OK"
"""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, prefix="rusys_prep_"
        ) as fh:
            fh.write(script)
            script_path = fh.name
        os.chmod(script_path, 0o755)

        result = subprocess.run(
            ["pkexec", script_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        os.unlink(script_path)

        if result.returncode == 0 and "PREPARE_OK" in (result.stdout or ""):
            log.info("Device %s prepared (unmount+wipe+chmod) in single pkexec session", device_path)
            return True
        log.warning(
            "elevate_prepare_device failed (exit %d): %s %s",
            result.returncode,
            result.stdout or "",
            result.stderr or "",
        )
        return False
    except FileNotFoundError:
        log.warning("pkexec not found — cannot prepare device")
        return False
    except subprocess.TimeoutExpired:
        log.warning("Device preparation timed out (user may have cancelled)")
        return False
    except Exception as exc:
        log.warning("elevate_prepare_device failed: %s", exc)
        return False


def restore_device_permissions(device_path: str) -> None:
    """Restore block device permissions to the secure default (660).

    Best-effort: if pkexec is not available or the user cancels, we just
    log a warning.
    """
    if not shutil_which("pkexec"):
        return
    try:
        subprocess.run(
            ["pkexec", "chmod", "660", device_path],
            check=False,
            capture_output=True,
            timeout=30,
        )
        log.info("Restored secure permissions on %s", device_path)
    except Exception:
        log.warning("Could not restore permissions on %s", device_path)


def elevate_write(image_path: str, device_path: str) -> Optional[str]:
    """Use pkexec+dd to write an image to a block device with elevated privileges.

    Returns the pkexec output on success, or None on failure.
    This is a fallback when direct write fails due to permissions.

    NOTE: This method does NOT support progress callbacks.  Prefer
    ``elevate_device_access()`` instead, which temporarily opens the
    device so the normal Python write path (with progress) can be used.
    """
    # Check if pkexec is available
    if not shutil_which("pkexec"):
        return None
    if not shutil_which("dd"):
        return None

    log.info(
        "Attempting elevated write via pkexec+dd: %s -> %s",
        image_path, device_path,
    )
    try:
        result = subprocess.run(
            [
                "pkexec", "dd",
                f"if={image_path}",
                f"of={device_path}",
                "bs=4M",
                "conv=fsync",
                "status=progress",
            ],
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour max
        )
        if result.returncode == 0:
            return result.stderr or result.stdout or "OK"
        else:
            log.warning(
                "pkexec+dd failed (exit %d): %s",
                result.returncode,
                result.stderr or "",
            )
            return None
    except subprocess.TimeoutExpired:
        log.warning("pkexec+dd timed out")
        return None
    except Exception as exc:
        log.warning("pkexec+dd failed: %s", exc)
        return None


def elevate_unmount(device_path: str) -> bool:
    """Use pkexec to unmount a device with elevated privileges."""
    if not shutil_which("pkexec"):
        return False
    base = os.path.basename(device_path)
    # Unmount the device and all partitions
    try:
        # Unmount all partitions first
        for entry in sorted(os.listdir("/dev")):
            if entry.startswith(base) and entry != base:
                subprocess.run(
                    ["pkexec", "umount", os.path.join("/dev", entry)],
                    check=False, capture_output=True, timeout=30,
                )
        # Unmount the main device
        result = subprocess.run(
            ["pkexec", "umount", device_path],
            check=False, capture_output=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def elevate_wipefs(device_path: str) -> bool:
    """Use pkexec to wipe the partition table with elevated privileges."""
    if not shutil_which("pkexec"):
        return False
    if not shutil_which("wipefs"):
        return False
    try:
        result = subprocess.run(
            ["pkexec", "wipefs", "--all", "--force", device_path],
            check=False, capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def shutil_which(name: str) -> Optional[str]:
    """Find an executable on PATH."""
    import shutil
    return shutil.which(name)
