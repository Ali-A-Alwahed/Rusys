# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Image flashing engine for Rusys.

Writes a disk image (ISO/IMG/DD) to a target device or file with progress and
optional post-write verification. The implementation is OS-aware: on Linux it
writes directly to the block device node; the same code path supports writing
to a regular file (used for DD-image creation and for safe testing).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from typing import Callable, List, Optional

from . import checksum
from .devices import Device, ensure_safe_target, human_size
from .logger import log
from .privileges import (
    can_write_device,
    elevate_device_access,
    elevate_prepare_device,
    elevate_write,
    install_udev_rule,
    is_udev_rule_installed,
)

ProgressCb = Callable[[int, int], None]  # (bytes_written, total_bytes)


def _maybe_unmount(device: Device) -> None:
    """Unmount the device and all its partitions (non-elevated, best-effort).

    Only tries regular ``umount`` — no pkexec.  If unmounting fails due
    to permissions, the caller (``flash_image``) will use
    ``elevate_prepare_device()`` to do unmount + wipe + chmod in a
    single pkexec session (one password prompt).
    """
    if device.is_file:
        return
    base = os.path.basename(device.path)
    # Collect all partition paths for this device
    partition_paths = []
    dev_dir = "/dev"
    try:
        for entry in os.listdir(dev_dir):
            if entry.startswith(base) and entry != base:
                partition_paths.append(os.path.join(dev_dir, entry))
    except OSError:
        pass

    # Unmount individual mount-points first
    for mp in list(device.mount_points):
        try:
            subprocess.run(["umount", mp], check=False, capture_output=True)
        except Exception:
            pass

    # Unmount all partition device nodes
    for ppath in partition_paths:
        try:
            subprocess.run(["umount", ppath], check=False, capture_output=True)
        except Exception:
            pass

    # Unmount the whole-disk device node
    try:
        subprocess.run(["umount", device.path], check=False, capture_output=True)
    except Exception as exc:  # pragma: no cover - best effort
        log.debug("umount attempt failed: %s", exc)


def _wipe_partition_table(device: Device) -> None:
    """Wipe the partition table and filesystem signatures from *device*.

    This ensures a clean target for the new image.  Uses ``wipefs`` when
    available (fast, targeted), otherwise falls back to zeroing the
    first MiB of the device.  Non-elevated only — if this fails due to
    permissions, the caller will use ``elevate_prepare_device()`` to
    do unmount + wipe + chmod in a single pkexec session.
    """
    if device.is_file:
        return
    # Try wipefs first (wipes all filesystem/RAID/partition signatures)
    try:
        result = subprocess.run(
            ["wipefs", "--all", "--force", device.path],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            log.info("Partition table wiped (wipefs) on %s", device.path)
            return
    except FileNotFoundError:
        pass  # wipefs not available

    # Fallback: zero the first 1 MiB (covers MBR, GPT header, superblocks)
    try:
        out_fd = os.open(device.path, os.O_WRONLY)
        try:
            os.lseek(out_fd, 0, os.SEEK_SET)
            os.write(out_fd, b"\x00" * (1024 * 1024))
        finally:
            os.close(out_fd)
        log.info("Partition table zeroed on %s", device.path)
    except PermissionError:
        log.debug("Cannot wipe partition table on %s (permission denied) — will retry elevated", device.path)
    except Exception as exc:
        log.warning("Could not wipe partition table on %s: %s", device.path, exc)


def flash_image(
    image_path: str,
    device: Device,
    progress_cb: Optional[ProgressCb] = None,
    chunk_size: int = 4 * 1024 * 1024,
    verify: bool = True,
    custom_ops: Optional[List[str]] = None,
    run_custom_ops: bool = False,
    cancel_event: Optional[threading.Event] = None,
    part_scheme: str = "MBR",
    target_system: str = "BIOS or UEFI",
    fs_type: str = "FAT32",
    cluster_size: str = "4096 bytes (Default)",
    volume_label: str = "RUSYS",
    old_bios_fix: bool = False,
) -> dict:
    """Flash *image_path* onto *device*.

    Returns a result dict: {"written", "verified", "digest", "ops_result"}.

    Privilege escalation strategy:
      1. Try non-elevated unmount + wipe + open (no password prompt).
      2. If that fails, use ``elevate_prepare_device()`` which does
         unmount + wipe + chmod in **one** pkexec session (single prompt).
      3. After writing, restore permissions best-effort (no extra prompt).
    """
    if not os.path.isfile(image_path):
        raise RuntimeError(f"Image file not found: {image_path}")

    image_size = os.path.getsize(image_path)
    result: dict = {"written": 0, "verified": False, "digest": None, "ops_result": None}

    # --- Step 1: Try non-elevated unmount + wipe --------------------------
    _maybe_unmount(device)
    _wipe_partition_table(device)

    # Re-read device metadata after unmount + wipe (size may change,
    # mount status is now stale).
    from .devices import reprobe_device
    reprobe_device(device)

    ensure_safe_target(device)

    log.info("Flashing %s -> %s (%s) [%s/%s %s %s label=%s oldbios=%s]",
             image_path, device.path, device.size_human,
             part_scheme, target_system, fs_type, cluster_size, volume_label, old_bios_fix)

    # Detect if ISO is hybrid (has MBR boot signature) — if so raw dd is correct and preserves bootability
    # For non-hybrid (e.g. Windows), we will extract ISO contents to a formatted partition
    def _is_hybrid_iso(path: str) -> bool:
        try:
            with open(path, "rb") as f:
                f.seek(510)
                sig = f.read(2)
                return sig == b"\x55\xaa"
        except Exception:
            return False

    is_hybrid = _is_hybrid_iso(image_path)
    log.info("ISO hybrid check: %s -> %s", image_path, is_hybrid)

    # For hybrid ISOs (most Linux) raw dd is the most reliable and preserves ISO's own partition table
    # We respect UI's partition scheme choice for logging but raw dd will overwrite it — this is intentional
    # For non-hybrid we could extract, but raw dd still often works for modern ISOs; we keep raw for now
    # to ensure bootability and add explicit sync after each chunk for accurate progress

    # --- Step 2: Open device for writing ----------------------------------
    _elevated_access = False
    out_fd = -1
    try:
        out_fd = os.open(
            device.path,
            os.O_WRONLY | os.O_CREAT if device.is_file else os.O_WRONLY,
        )
    except PermissionError:
        # Cannot open device directly — use single-prompt elevated prepare
        # (unmount + wipe + chmod in ONE pkexec session).
        log.info("Direct open failed (permission denied), requesting elevated access...")
        if elevate_prepare_device(device.path):
            _elevated_access = True
            # Re-probe after elevated unmount+wipe
            reprobe_device(device)
            try:
                out_fd = os.open(device.path, os.O_WRONLY)
            except PermissionError as exc:
                raise RuntimeError(
                    f"Permission denied writing to {device.path} even after "
                    f"elevated access.  Try running with sudo or install the "
                    f"udev rule from Settings → USB Device Access."
                ) from exc
        else:
            # Single-prompt prepare failed or was cancelled — fall back to
            # pkexec dd (no progress, but at least the write completes)
            log.info("Elevated access denied, trying pkexec+dd fallback...")
            dd_result = elevate_write(image_path, device.path)
            if dd_result is not None:
                result["written"] = image_size
                log.info("Elevated write completed via pkexec+dd (no progress available)")
            else:
                # Offer to install udev rule for future runs
                if not is_udev_rule_installed():
                    log.info(
                        "Attempting to install udev rule for future USB access..."
                    )
                    if install_udev_rule():
                        raise RuntimeError(
                            f"udev rule installed successfully.  Please log out and "
                            f"log back in (or run `newgrp disk`) so the group "
                            f"membership takes effect, then try again."
                        )
                    else:
                        raise RuntimeError(
                            f"Permission denied writing to {device.path}.  "
                            f"Rusys tried elevated write (pkexec) but it was "
                            f"cancelled or unavailable.  Either:\n"
                            f"  1. Run Rusys with sudo:  sudo rusys\n"
                            f"  2. Install the udev rule from Settings → Install USB Rules\n"
                            f"  3. Add yourself to the 'disk' group:  sudo usermod -aG disk $USER"
                        )
                else:
                    raise RuntimeError(
                        f"Permission denied writing to {device.path}.  "
                        f"The udev rule is installed but may not have taken effect yet.  "
                        f"Try logging out and back in, or run:  newgrp disk"
                    )
            # Skip the direct-write path since dd already wrote the image
            if result["written"] > 0:
                return result

    # --- Step 3: Perform the write with progress reporting -----------------
    # Use unbuffered, synchronous writes so progress_cb reflects actual
    # device throughput, not just RAM buffering (which would hit 100% instantly).
    written = 0
    try:
        with open(image_path, "rb") as src:
            while True:
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError("Write cancelled by user.")
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                os.write(out_fd, chunk)
                written += len(chunk)
                # Flush to device so progress reflects real USB speed.
                try:
                    os.fsync(out_fd)
                except OSError:
                    pass
                if progress_cb:
                    progress_cb(written, image_size)
                # Log progress every 10% for visibility
                pct = int(written * 100 / image_size) if image_size else 0
                if written % (image_size // 10 + 1) < chunk_size and pct > 0:
                    log.info("Write progress: %d%% (%s / %s)", pct,
                             human_size(written), human_size(image_size))
        # Ensure data is flushed to the device and partition table is re-read.
        try:
            os.sync()
            # Force kernel to re-read partition table (helps BIOS/UEFI detect bootable)
            try:
                subprocess.run(["blockdev", "--rereadpt", device.path], check=False, capture_output=True, timeout=5)
            except Exception:
                pass
            # Also run partprobe if available
            try:
                subprocess.run(["partprobe", device.path], check=False, capture_output=True, timeout=5)
            except Exception:
                pass
        except OSError:
            pass
        result["written"] = written
        log.info("Write complete: %s written to %s (hybrid=%s, verify=%s)", human_size(written), device.path, is_hybrid, verify)
    finally:
        try:
            os.close(out_fd)
        except OSError:
            pass
        # Restore secure permissions if we elevated them.
        # Best-effort: try os.chmod first (works if we still have access),
        # otherwise log that permissions will reset on device replug.
        if _elevated_access and not device.is_file:
            try:
                os.chmod(device.path, 0o660)
                log.info("Restored secure permissions on %s", device.path)
            except PermissionError:
                log.info(
                    "Could not restore permissions on %s — "
                    "they will reset when the device is unplugged and replugged",
                    device.path,
                )

    # --- Step 4: Verify written data ---------------------------------------
    if verify:
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Write cancelled by user.")
        log.info("Verifying written media...")
        # Only hash the first image_size bytes from the device.
        # Block devices are typically larger than the ISO; hashing the
        # trailing zeros would cause a digest mismatch even when the
        # write was perfect.
        try:
            digest = checksum.hash_file(
                device.path, "sha256", progress_cb=None, max_bytes=image_size,
            )
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("Write cancelled by user.")
            img_digest = checksum.hash_file(image_path, "sha256")
            result["digest"] = digest
            result["verified"] = digest == img_digest
            if not result["verified"]:
                raise RuntimeError(
                    "Verification failed: written media does not match the source image."
                )
            log.info("Verification OK (%s)", digest[:16])
        except PermissionError:
            log.warning(
                "Cannot read %s for verification (permission denied) — skipping verify",
                device.path,
            )
            result["verified"] = None  # indeterminate, not a failure

    if run_custom_ops and custom_ops:
        result["ops_result"] = run_custom_file_ops(image_path, device, custom_ops)

    return result


def run_custom_file_ops(image_path: str, device: Device, ops: List[str]) -> List[dict]:
    """Run user-supplied shell operations after flashing (issue #322).

    Each entry of *ops* is executed via the shell with the environment variables
    RUSYS_IMAGE and RUSYS_TARGET available. This mirrors Rufus' request for
    custom file operations during ISO extraction.
    """
    results = []
    env = dict(os.environ)
    env["RUSYS_IMAGE"] = image_path
    env["RUSYS_TARGET"] = device.path
    for op in ops:
        if not op.strip():
            continue
        log.info("Running custom op: %s", op)
        proc = subprocess.run(
            op, shell=True, env=env, capture_output=True, text=True
        )
        results.append(
            {
                "cmd": op,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
        if proc.returncode != 0:
            log.warning("Custom op failed (%d): %s", proc.returncode, proc.stderr)
    return results
