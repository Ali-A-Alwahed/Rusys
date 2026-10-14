# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""User settings for Rusys (JSON-backed, Qt-independent in the core layer).

Every toggle here maps to a requested upstream issue/feature:
  * uefi_runtime_validation  -> #3003 runtime UEFI media validation
  * disable_bitlocker        -> #2877 BitLocker auto-encryption (Win-To-Go)
  * secure_boot_warn          -> #2244 PCA2011 revocation warning
  * silent_install            -> #3008 "Silent Install" UI state
  * custom_ops                -> #322 custom file operations during extraction
  * mnemonics                 -> #1688 button mnemonics (always on in UI)
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import List

from .logger import log

DEFAULT_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "rusys", "settings.json",
)


@dataclass
class Settings:
    # --- general ---
    download_dir: str = ""
    last_image: str = ""
    last_device: str = ""
    verify_after_write: bool = True
    # --- issue #3003: runtime UEFI media validation (opt-in, OFF by default) ---
    uefi_runtime_validation: bool = False
    # --- issue #2877: disable BitLocker auto device encryption (Win-To-Go) ---
    # Also used for "Create extended label and icon files" in single-boot (enabled by default per user request)
    disable_bitlocker: bool = True
    # --- issue #2244: warn on Secure Boot revocation (PCA2011) ---
    secure_boot_warn: bool = True
    # --- issue #3008: silent install (UI enabled/disabled state) ---
    silent_install: bool = False
    # --- issue #322: custom file operations during ISO extraction ---
    custom_ops_enabled: bool = False
    custom_ops: List[str] = field(default_factory=list)
    # --- single-boot UI ---
    list_usb_hard_drives: bool = True
    old_bios_fix: bool = False
    check_bad_blocks: bool = True
    headless_install: bool = False
    part_scheme: str = "MBR"
    target_system: str = "BIOS or UEFI"
    fs_type: str = "FAT32"
    cluster_size: str = "4096 bytes (Default)"
    volume_label: str = "RUSYS"
    parallel_limit: int = 3
    # --- appearance / behaviour ---
    theme: str = "whitesur"
    window_geometry: str = ""
    about_geometry: str = ""
    splitter_sizes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


def load_settings(path: str = DEFAULT_PATH) -> Settings:
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                return Settings.from_dict(json.load(fh))
    except Exception as exc:  # pragma: no cover - never fatal
        log.warning("Failed to load settings (%s); using defaults.", exc)
    return Settings()


def save_settings(settings: Settings, path: str = DEFAULT_PATH) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(settings.to_dict(), fh, indent=2)
    except Exception as exc:  # pragma: no cover
        log.warning("Failed to save settings: %s", exc)
