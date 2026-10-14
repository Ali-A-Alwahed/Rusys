# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Lightweight ISO / image inspection utilities for Rusys."""
from __future__ import annotations

import struct
from typing import Dict, Optional


def is_iso9660(path: str) -> bool:
    """Detect an ISO 9660 (optical) image by its magic at offset 32769."""
    try:
        with open(path, "rb") as fh:
            fh.seek(32769)
            magic = fh.read(5)
        return magic == b"CD001"
    except OSError:
        return False


def iso_volume_label(path: str) -> Optional[str]:
    """Best-effort read of the ISO 9660 volume identifier."""
    try:
        with open(path, "rb") as fh:
            fh.seek(32808)
            raw = fh.read(32)
        label = raw.split(b";")[0].rstrip(b" ").decode("ascii", "ignore")
        return label or None
    except OSError:
        return None


def image_info(path: str) -> Dict[str, object]:
    """Return a small dictionary describing an image file."""
    import os

    info: Dict[str, object] = {
        "path": path,
        "size": None,
        "is_iso": False,
        "label": None,
    }
    try:
        info["size"] = os.path.getsize(path)
    except OSError:
        return info
    try:
        info["is_iso"] = is_iso9660(path)
        if info["is_iso"]:
            info["label"] = iso_volume_label(path)
    except Exception:
        pass
    return info


def read_utf16le_string(data: bytes, offset: int, max_len: int = 512) -> str:
    """Helper used by UEFI/Secure-Boot checks: decode a UTF-16LE string."""
    raw = data[offset : offset + max_len * 2]
    out = []
    for i in range(0, len(raw) - 1, 2):
        ch = struct.unpack_from("<H", raw, i)[0]
        if ch == 0:
            break
        out.append(chr(ch))
    return "".join(out)
