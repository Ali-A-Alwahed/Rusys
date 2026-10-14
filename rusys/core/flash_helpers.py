# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Shared advisory strings and Secure-Boot helpers for Rusys.

Implements the user-facing behaviour described in upstream issue #2244
(PCA2011 certificate revocation can make older media unbootable through
Secure Boot). The advisory text is shown before writing such media.
"""
from __future__ import annotations

SECURE_BOOT_ADVISORY = (
    "The selected media may no longer boot through Secure Boot.\n\n"
    "Microsoft revoked the PCA2011 code-signing certificate, so boot files "
    "signed with it are rejected by modern Secure Boot. This target ({name}) "
    "appears to rely on pre-revocation signatures. To boot it you may need to "
    "disable Secure Boot in the firmware, or use an image signed with a "
    "current Microsoft certificate."
)
