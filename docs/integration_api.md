# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

# Rusys — Integration API (Pro Tool)

This document explains how the **Pro Tool** host application integrates the
**Rusys** 3rd‑party extension: embedding, launching, and automating it.

---

## 1. Files & placement

Rusys lives under the Pro Tool 3rd‑party extensions directory:

```
<Pro Tool>/assets/Data/3rd_Party_Extensions/Rusys/
```

The `rusys/` Python package and its `phased.md`, `LICENSE.txt`, `README.md`,
`CHANGELOG.md`, `docs/` and `pyproject.toml` should be copied as‑is. No build
step is required at runtime (pure Python + PySide6).

---

## 2. Launching the GUI from Pro Tool

Rusys is a normal Python application. From Pro Tool (Python side):

```python
import subprocess, sys

def launch_rusys():
    subprocess.Popen(
        [sys.executable, "-m", "rusys", "--gui"],
        cwd="<Pro Tool>/assets/Data/3rd_Party_Extensions/Rusys",
    )
```

For a true embedded feel you can instead import the window class directly:

```python
import sys
sys.path.insert(0, "<Pro Tool>/assets/Data/3rd_Party_Extensions/Rusys")
from rusys.ui.main_window import MainWindow
from rusys.core.settings import load_settings

win = MainWindow(load_settings())
win.show()
```

---

## 3. Command‑line automation (headless)

Rusys exposes a stable CLI (`rusys.cli:main`). Pro Tool can drive it for
unattended workflows:

| Argument | Purpose |
|----------|---------|
| `--gui` / `--offscreen` | Launch UI (offscreen for tests) |
| `--download "CATALOG_PATH"` | Download an ISO for a catalogue path |
| `--dir DIR` | Download destination |
| `--image PATH` | Source image file |
| `--device PATH` | Target device (`/dev/sdX`) or a file |
| `--verify` / `--no-verify` | Toggle post‑write verification |
| `--check --sha256 HASH` | Only verify an image's hash |
| `--secure-boot-warn` | Print the PCA2011 Secure‑Boot advisory |
| `--silent` | Use silent/unattended install defaults |
| `--version` | Print version |

Catalogue paths follow `Parent/Child/Leaf`, e.g.:
`"Microsoft Windows/Windows 11/x64"`,
`"Linux/Ubuntu/Desktop"`,
`"Maintenance and Recovery/Linux Recovery/Clonezilla"`.

The catalogue currently lists **78 operating systems** across four
top‑level categories: **Microsoft Windows**, **Linux**, **Unix / BSD**, and
**Maintenance and Recovery** (Apple/macOS was removed by request). Each leaf
carries compatibility, size, an approximate download count, and a latest‑update
date, and exposes either a direct `iso_url` or an official `page_url`.

### Examples

```bash
# Download Ubuntu desktop ISO into ~/iso
python -m rusys --download "Linux/Ubuntu/Desktop" --dir ~/iso

# Write it to a USB stick (requires root on Linux)
python -m rusys --image ~/iso/ubuntu.iso --device /dev/sdb --verify

# Verify an existing image without writing
python -m rusys --check --image ./win.iso --sha256 <sha256>
```

---

## 4. Programming API (Python)

```python
from rusys.core.devices import enumerate_devices, add_file_target
from rusys.core.downloader import Downloader
from rusys.core.flasher import flash_image
from rusys.core.privileges import elevate_prepare_device, install_udev_rule
from rusys.core import checksum
from rusys.data.os_catalog import ROOT, iter_leaves, load_user_overrides

# List removable devices
for dev in enumerate_devices():
    print(dev.display, dev.size_human)

# Download a direct ISO
Downloader(url, dest, expected_sha256=sha).run(progress_cb=cb)

# Prepare a device for writing (single pkexec prompt: unmount+wipe+chmod)
elevate_prepare_device("/dev/sdb")

# Flash (device may be a real block device or a file target)
result = flash_image(image_path, device, verify=True,
                     custom_ops=ops, run_custom_ops=bool(ops))

# Verify only the first N bytes (block devices are larger than the ISO)
digest = checksum.hash_file("/dev/sdb", "sha256", max_bytes=image_size)

# Install udev rule for passwordless future access
install_udev_rule()

# Override catalogue URLs
load_user_overrides("/path/to/catalog_overrides.json")
```

`catalog_overrides.json` format — a map of `"Parent/Child/Leaf"` paths to
`{"iso_url": "...", "page_url": "..."}`.

---

## 5. Settings storage

User settings live at
`$XDG_CONFIG_HOME/rusys/settings.json` (or `~/.config/rusys/settings.json`).
Pro Tool may pre‑seed this file to configure Rusys defaults for its users.

---

## 6. Licensing

Rusys is licensed under the **GNU General Public License v3.0 or later**
(GPL-3.0-or-later); the full text is in `LICENSE.txt`, and every bundled
third-party component is itemised in `THIRD_PARTY_NOTICES.md`.

This is a change from earlier releases. Up to and including 26.9.9 Rusys was
published under a custom permissive license ("LGPT v1.0"). That license is
incompatible with the GPL-3.0 software Rusys redistributes inside `resources/`
(Rufus 4.15, Ventoy 1.1.17, grub2-themes), so the project was relicensed as of
**26.10.14** to make the distribution lawful.

### What this means for Pro Tool as a host

- **Redistributing Rusys, modified or unmodified, requires conveying the
  GPL-3.0-or-later license**, retaining all copyright and license notices, and
  offering the corresponding Rusys source under the same terms.
- **Rusys is no longer permissively licensed.** A previously LGPL-3.0 / LGPT
  integration that relied on Rusys *not* imposing copyleft must be re-reviewed.
  Run the GPL-3.0 compatibility analysis for your specific deployment before
  shipping.
- **Simply running Rusys as a separate process** (which is how it is designed
  to be used — it is a standalone binary or CLI, never linked into Pro Tool)
  does not make Pro Tool a GPL work.
- The GPL-3.0 obligations attach to the Rusys work and any derivative of it,
  not to the Pro Tool host's own independent code.