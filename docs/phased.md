# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

# Rusys — Phased Upgrade Plan

**Project:** Rusys (a from-scratch Python/PySide6 rebuild of the Rufus USB
boot-media utility, rebranded and integrated as a 3rd‑party extension of the
*Pro Tool* project).

**Original base:** `pbatard/rufus` (C/Win32 sources found in `../Rufus`).
**Target runtime:** Cross‑platform desktop (developed & verified on Linux/Fedora;
the UI layer is portable, the low‑level flash path is OS‑aware).

**License:** GPL-3.0-or-later. See `LICENSE.txt` and `THIRD_PARTY_NOTICES.md`. Every source file carries the Pro Tool header.

**Status:** All phases complete (current release 26.10.14). The original C sources were removed
and the folder moved into the Pro Tool 3rd‑party extensions tree. Required docs
(README, integration_api, CHANGELOG, SECURITY) were updated to match the final
state after the build, before finalization.

---

## Phase 0 — Analysis (done)
- Audited the original Rufus C sources (816 files: 257 `.h`, 221 `.c`, res, po…).
- Extracted the feature surface that is portable to Python/PySide6:
  ISO download catalogue, device enumeration, image flashing, checksumming,
  settings, logging, CLI. Low‑level Windows‑only behaviors (VDS, bespoke
  bootloader injection, WIM/FFU) are re‑implemented as safe, OS‑appropriate
  equivalents rather than 1:1 ports.

## Phase 1 — Scaffold & Launchable Shell (done)
- Package skeleton (`rusys/` with `core/`, `ui/`, `data/`).
- `LICENSE.txt` (GPL-3.0-or-later), `THIRD_PARTY_NOTICES.md`, `requirements.txt`, `pyproject.toml`.
- Pro Tool header injected into every file.
- Minimal PySide6 main window that opens, shows the logo/title and an empty
  device/combo area. **Gate:** app launches with no import/Qt errors.

## Phase 2 — OS Catalogue + UI (done)
- `data/os_catalog.py`: the full OS catalogue — **80 unique operating systems**
  across **Microsoft Windows, Linux, BSD, and Maintenance and Recovery**.
  Apple/macOS was removed by request (incl. Mac Recovery). Each leaf carries
  compatibility, size, approximate download count, latest‑update date, and an
  official `page_url` (or direct `iso_url`).
- `ui/catalog_widget.py`: a flat, sortable **spreadsheet (`QTableWidget`)**
  with columns Operating System | Compatibility | Size | Downloads | Latest
  Update; searchable, row‑click selects an OS. **Gate:** catalogue renders,
  search works, links resolve.

## Phase 3 — Download Engine (done)
- `core/downloader.py`: resumable chunked HTTP download with progress,
  checksum verification, cancel, speed & ETA.
- `ui/download_dialog.py`: progress, verify, open‑in‑browser fallback.
- **Gate:** a small test asset downloads & verifies; cancel works.

## Phase 4 — Device Detection + Flasher (done)
- `core/devices.py`: enumerate removable block devices (Linux `/sys/block`,
  portable fallback), size, model, mount state.
- `core/flasher.py`: write an image to a device with progress, safe‑guard
  prompts, post‑write verify. OS‑aware (Linux `dd`/direct write; Windows path
  stubbed for portability).
- `core/iso.py` / `core/checksum.py`: ISO inspection + hash utils.
- **Gate:** flashing a sample image to a loop/real device verifies; bad‑block
  & size guards trigger correctly.

## Phase 5 — Settings & Community‑Issue Fixes (done)
Map every requested upstream issue to a concrete feature/behavior:
- **#3008** "Silent Install" hidden but not disabled → option is correctly
  *enabled/disabled* (never half‑state) and greyed when unsupported.
- **#3003** "Enable runtime UEFI media validation" breaks Ubuntu 26.04 →
  runtime UEFI validation is **opt‑in**, defaults OFF for Ubuntu, with a clear
  warning when forced on.
- **#2877** "Disable BitLocker automatic device encryption" for Win‑To‑Go →
  dedicated checkbox that records/logs the disable policy into the image workflow.
- **#2244** Warn if media no longer Secure‑Boot bootable (PCA2011 revocation)
  → pre‑flash Secure‑Boot compatibility warning with cert revocation notice.
- **#1778** `0xC0030002` "file not found" → robust path resolution + clearer
  error dialogs (no raw NTSTATUS codes leaked to users).
- **#1688** Button mnemonics → keyboard shortcuts (`F5`, `Ctrl+S`, `Ctrl+Q`).
  (Per request, visible `&` mnemonic underlines and `#`/`_` characters were
  removed from all UI labels.)
- **#322** Custom file operations during ISO extraction → user‑supplied
  post‑extract script hook.
- **Command‑line args** → `cli.py`: `--device`, `--image`, `--download`,
  `--silent`, `--check`, `--version`, `--help`.
- **Gate:** each toggle behaves as specified; CLI drives a headless run.

## Phase 6 — Documentation (done)
- `README.md`, `docs/integration_api.md` (how Pro Tool embeds Rusys),
  `CHANGELOG.md`, `SECURITY.md` — all updated to the final state.
- Window size/position persistence documented; Downloads column (approximate
  real counts from trusted references) documented.
- **Gate:** docs accurate; API example runs.

## Phase 7 — Finalization (done)
- Remove the original `../Rufus` C sources.
- Refresh docs (version bumped to 1.1.0, path, integration notes).
- Move the `Rusys` folder to
  `/home/fedora/Avalanche_Projects/Android_Tool/assets/Data/3rd_Party_Extensions/`.
- **Gate:** app still launches from new location; all docs accurate.

---

### Verification protocol (per phase)
After each phase I run: `python -m py_compile` on all modules, an `import` smoke
test, and (where possible) launch the UI under the Qt `offscreen` platform to
confirm zero startup errors/warnings. I then start the app for you to test
manually; when you close it and say *continue*, I proceed to the next phase.

### Iteration changes folded into the deliverable (post Phase 5)
- Added a **BSD** category and expanded the catalogue to 80 unique OS entries.
- Swapped the tree view for a flat, sortable `QTableWidget` spreadsheet.
- Replaced the (removed) community **Rating** column with a **Downloads** column
  of approximate real download counts from trusted public references.
- Removed Apple/macOS entirely; stripped `#`/`_` and `&` mnemonics from labels.
- Added window size/position persistence (bug fixed in the close handler).
- Updated Fedora KDE link to `https://fedoraproject.org/kde/`.
