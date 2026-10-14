# Changelog

All notable changes to **Rusys** are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
Semantic Versioning.

## [26.10.14] - 2026-10-14

### Security
- **Dependency floors raised to clear all known CVEs.** `requests` is now
  pinned `>=2.34.2`, clearing **CVE-2026-25645** (insecure temp-file reuse in
  `requests.utils.extract_zipped_paths()`, fixed in 2.33.0),
  **CVE-2024-47081** (`.netrc` credential leak on redirect, fixed in 2.32.4),
  **CVE-2024-35195** (`Session.verify=False` persistence, fixed in 2.32.0) and
  **CVE-2014-1829** (netrc password disclosure, fixed in 2.3.0).
- **`setuptools` build floor raised to `>=83.0.0`**, clearing
  **PYSEC-2026-3447** (fixed in 83.0.0).
- `resources/Downloader/requirements.txt` refreshed from its historical
  `requests==2.31.0` pin to current CVE-free releases.
- Verified clean with `pip-audit` against both the resolved dependency set and
  the declared minimums.

### Changed
- **License changed from LGPT v1.0 to GPL-3.0-or-later.** Rusys redistributes
  GPL-3.0 software inside `resources/` — Rufus 4.15 sources, Ventoy 1.1.17
  binaries and the grub2-themes assets. The previous custom permissive license
  was incompatible with those components and could not lawfully be combined
  with them. `LICENSE.txt` is now the verbatim FSF GPL-3.0 text.
- **Added `THIRD_PARTY_NOTICES.md`** documenting every bundled and depended-upon
  component, its upstream, version and license.
- Upstream GPL-3.0 license texts placed into `resources/ventoy/` and
  `resources/themes/`, which previously shipped without any license file.
- **Dependencies updated**: `PySide6>=6.12,<6.13`, `requests>=2.34.2`,
  `pyinstaller>=6.22.3`, `setuptools>=83.0.0`.
- **Minimum Python raised to 3.10** (PySide6 6.12 requires `>=3.10,<3.16`).
- Packaging modernised to PEP 621 / PEP 639: SPDX `license` expression and
  `license-files`, project URLs, and Python 3.10–3.14 classifiers.
- Repository and download links repointed to `github.com/Ali-A-Alwahed/Rusys`.
- Version bumped to 26.10.14 (`__init__`, `pyproject`, `Rusys.spec`,
  `version_info.txt`, `Rusys.exe.manifest`, downloader User-Agent).

### Fixed
- **Removed a machine-specific absolute path** (`/home/fedora/Downloads/ventoy`)
  hardcoded as the Ventoy fallback directory; it now derives from `$HOME`.
- **`setuptools>=80.0` floor** in `pyproject.toml` permitted installing a
  release vulnerable to PYSEC-2026-3447; now `>=83.0.0`.
- **Broken PEP 639 metadata**: the `License ::` classifier conflicted with the
  SPDX `license` expression and made `python -m build` fail outright.
- Added the missing `rusys/py.typed` marker that `pyproject.toml` already
  declared in `package-data` but which was never present.
- `download_dialog.py` imported its sibling via `..ui.worker` instead of
  `.worker`; now uses the direct relative import.

### Removed
- Stale `__pycache__/` build residue from the repository.

## [26.9.9] - 2026-09-09

### Added
- **os.click fresh Windows links**: all 7 Windows groups (XP, Vista, 7, 8,
  8.1, 10 LTSC 2021, 11 26H1 — 24 to 38 languages each) replay the site's
  own search flow at download time and receive a freshly signed
  `dl.os.click` URL, so no expiring signed URL is ever stored and no
  browser is opened. Verified end-to-end for every group.
- **FreeBSD direct ISO download**: FreeBSD 15.1 RELEASE amd64 DVD
  (4.3 GB, verified) with direct `iso_url` link to `download.freebsd.org`
  — no browser redirect needed.
- **Unix / BSD category**: Windows, Linux, Unix/BSD, and Maintenance and
  Recovery are separate top-level sections (78 leaves total).
- **Crash-proof downloads**: URL resolving (os.click fresh-link walk,
  page scraping, cookies) runs in the background worker thread — the GUI
  thread never does network. Challenge pages degrade to an honest browser
  fallback (`needs_browser` status) instead of crashing or saving HTML
  as ISO.
- **HTML-as-ISO guard**: the engine refuses to save web pages (403/HTML
  under 2 MB) as ISO files.
- **Startup error dialog**: frozen builds show the real traceback in a
  message box and write `Rusys_error.log` instead of dying silently.

### Changed
- **License changed to LGPT v1.0**: by Ali A Alwahed instead of
  LGPL-3.0-or-later. `LICENSE.txt` is the unchanged LGPT text; all source
  headers updated accordingly.
- **Dependencies updated**: `PySide6>=6.11`, `requests>=2.34`.
- **Expired os.click signed links removed**: all stored `dl.os.click`
  `?md5=…&expires=…` URLs (HTTP 410 since 2026-09-02) replaced with walk
  specs — a fresh signed URL is issued per download, valid for days.
- **Version bumped to 26.9.9**.

### Fixed
- **Windows download crash (XP English etc.)**: selecting a Windows edition,
  picking a language and clicking Download no longer freezes/crashes the app
  while "generating cookies". Resolve happens off-thread with timeouts.
- **Slimmer portable builds**: `Rusys.spec` no longer uses `collect_all`
  (which pulled all of Qt incl. WebEngine/QML); unused Qt modules excluded.

## [1.2.0] - 2026-08-18

### Added
- Full OS download catalogue (Windows, Linux, BSD, Maintenance and Recovery).
- Resumable downloads with checksum verification.
- Safe device flashing with post-write verification.
- Settings mapped to community-requested fixes.
- Command-line interface for automation.

## [26.8.30] - 2026-08-30

### Added
- Ventoy-powered Multiboot USB with 4 themed GRUB2 menus.
- Per-OS icons in the Ventoy boot menu.
- Bulk ISO adding with drag & drop support.

## [26.9.3] - 2026-09-03

### Added
- os.click catalogue with 85 ISOs.
- 30-part parallel downloads with Range requests.
- Queue controls for download management.
- Persistent settings at `~/.config/rusys/settings.json`.
