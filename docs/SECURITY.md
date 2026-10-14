# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

# Security Policy

**Rusys** is a 3rd‑party extension of the Pro Tool project.

## Supported versions

| Version | Supported |
|---------|-----------|
| 26.10.x | ✅        |
| 26.9.x  | ⚠️ Security fixes only |
| < 26.9  | ❌        |

## Reporting a vulnerability

Please report security issues **privately** to the Pro Tool maintainer
(Ali A Alwahed) rather than opening a public issue. Include:

* A description of the impact and attack scenario.
* Steps to reproduce.
* Any relevant logs (Rusys logs all operations to its log widget / stderr).

## Safety notes

* Rusys writes directly to block devices. It refuses to write to a mounted
  device and validates the target size before writing.
* Downloads are verified against an expected SHA‑256 when provided, and ISO
  images are inspected before use.
* Custom file operations (#322) execute shell commands supplied by the user;
  only enable them if you trust the configured commands.
* On Linux, writing to a real USB device requires root privileges.