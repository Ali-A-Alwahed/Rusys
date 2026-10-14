# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

# Rusys

**Rusys** is a 3rd‑party extension of the *Pro Tool* project — a from‑scratch
Python / PySide6 rebuild of the Rufus USB boot‑media utility, rebranded and
integrated so it can download official operating‑system images and write them
to removable media.

> Rebuilt from the concepts of [`pbatard/rufus`](https://github.com/pbatard/rufus)
> (the original C/Win32 sources shipped in this repository's `../Rufus`
> folder). Rusys is **not** a 1:1 port; platform‑specific behaviours are
> re‑implemented as safe, OS‑appropriate equivalents.

* **License:** GPL-3.0-or-later (see `LICENSE.txt` and `THIRD_PARTY_NOTICES.md`).
* **Author:** Ali A Alwahed · © 2026 Pro_Tool Project.
* **Runtime:** Python ≥ 3.10 (< 3.16), PySide6 ≥ 6.12, requests ≥ 2.34.2 (Linux/Windows; verified on Linux/Fedora with Python 3.14).

---

## Features

* Full **OS download catalogue — 78 entries** across **Windows, Linux,
  Unix / BSD, and Maintenance and Recovery**. Each row shows Operating System, Size, and Latest Update — click
  any item to download the ISO (Windows asks for language + arch first) or open
  its official page. Windows entries resolve a fresh os.click signed link at
  download time (never expires, no browser); page-only entries fall back to
  the browser honestly.
* **Downloads column** with approximate real download counts from trusted public
  references (DistroWatch popularity, official project/blog statistics, vendor
  figures). Hover for the full number and source note.
* Flat, sortable **spreadsheet (`QTableWidget`)** view with centred text and a
  compact, resizable window that remembers its last size & position.
* **Resumable downloads** with SHA‑256 verification and cancel support.
* **Safe device flashing** with post‑write verification and mount/size guards.
* **Single-prompt privilege escalation**: unmount + wipe + chmod in one
  `pkexec` session (no more 4-6 password dialogs per flash).
* **USB hotplug detection**: auto-refreshes device list when USB devices
  are plugged/unplugged (3-second poll). First USB device auto-selected.
* **udev rule installer**: Settings → USB Device Access installs a
  persistent udev rule so future runs need no elevated privileges.
* **Accurate progress bar for >2GB images**: uses `float` signals to avoid
  C++ int32 overflow that caused the bar to jump to 100% or stay at 0%.
* **Correct verification**: only hashes the ISO-sized portion of the block
  device (trailing zeros no longer cause SHA-256 mismatch).
* Settings mapped to the requested community fixes:
  * #3008 — "Silent Install" is properly enabled/disabled (never a hidden,
    half‑state) and greyed when unsupported.
  * #3003 — "Runtime UEFI media validation" is **opt‑in**, defaults OFF, and is
    auto‑disabled for Ubuntu images (which it would otherwise break).
  * #2877 — "Disable BitLocker automatic device encryption" for Windows‑To‑Go.
  * #2244 — Secure‑Boot (PCA2011 revocation) advisory before writing old media.
  * #1778 — clear, non‑NTSTATUS error reporting for missing files / paths.
  * #322 — user‑supplied custom shell operations run after writing.
  * Command‑line interface for automation (`rusys --help`).
* Cross‑platform core with an OS‑aware flash path.

---

## Quick start

```bash
# From the project directory
pip install -r requirements.txt
python -m rusys --gui          # graphical interface
# or, headless:
python -m rusys --download "Linux/Ubuntu/Desktop" --dir ~/iso
python -m rusys --image ~/iso/ubuntu.iso --device /dev/sdb --verify
```

> **Linux note:** writing to a block device (`/dev/sdX`) requires root. Rusys
> will prompt once for elevated access via `pkexec` (single authentication
> dialog). You can also install the udev rule from Settings → USB Device Access
> to grant permanent write access without any password prompt. Alternatively,
> flash to a regular file to create a DD image, or for safe testing.

### Keyboard shortcuts
| Shortcut | Action |
|----------|--------|
| `F5`     | Refresh devices |
| `Ctrl+S` | Settings |
| `Ctrl+Q` | Quit |

---

## Project layout

```
Rusys/
├── phased.md                 # the upgrade plan this build followed
├── LICENSE.txt               # GPL-3.0-or-later (FSF full text)
├── THIRD_PARTY_NOTICES.md    # Bundled Rufus / Ventoy / grub2-themes notices
├── README.md
├── CHANGELOG.md
├── docs/
│   └── integration_api.md    # how Pro Tool embeds/automates Rusys
├── pyproject.toml
├── requirements.txt
└── rusys/
    ├── __init__.py           # version / Pro Tool header constant
    ├── cli.py                # command-line interface
    ├── main.py               # GUI launcher
    ├── core/                 # download, devices, flasher, checksum, iso, settings
    ├── ui/                   # PySide6 widgets (main window, dialogs, catalogue)
    └── data/                 # os_catalog.py (the OS tree + download links)
```

Every source file carries the mandatory Pro Tool header:

```
# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later
```

---

## Limitations / roadmap

* **Download counts are approximate public estimates** (DistroWatch popularity,
  official project/blog statistics, vendor figures), not vendor‑exact tallies.
* Windows‑To‑Go BitLocker policy injection (#2877) is recorded as intent and
  logged; true policy injection requires Windows‑only tooling not available
  cross‑platform and is stubbed accordingly.
* Direct ISO URLs for some distributions may need updating as vendors change
  their mirrors — override them via `catalog_overrides.json` (see integration
  docs). Use `catalog_overrides.json` to point an OS at a different official page.
* Low‑level Windows‑only Rufus features (VDS, bespoke bootloader injection,
  WIM/FFU) are not reproduced; the equivalent cross‑platform behaviour is raw
  image writing with verification.

---

## Distribution packages

Rusys ships as **self‑contained standalone executables** (Python + PySide6 +
requests bundled via PyInstaller), so end users need nothing pre‑installed:

| Package | Built with | Contents |
|---------|------------|----------|
| `Rusys.rpm` | `rpmbuild` | `/usr/bin/Rusys`, `.desktop`, icons, docs |
| `Rusys.deb` | `dpkg-deb` | `/usr/bin/Rusys`, `.desktop`, icons, docs |
| `Rusys.exe` | PyInstaller (under Wine) | standalone Windows executable |

Install: `sudo rpm -i Rusys.rpm` / `sudo dpkg -i Rusys.deb` / run `Rusys.exe`.
The standalone `dist/Rusys` binary also runs directly on Linux.