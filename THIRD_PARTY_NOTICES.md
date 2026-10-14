# Third-Party Notices

Rusys is licensed under the **GNU General Public License v3.0 or later**
(GPL-3.0-or-later). See [`LICENSE.txt`](LICENSE.txt) for the full text.

This distribution bundles or depends on the third-party components listed below.
Each component remains under its own upstream license. Nothing in this file
changes, overrides or extends the terms of those upstream licenses.

---

## 1. Bundled third-party source and binaries (`resources/`)

These components are redistributed verbatim inside the `resources/` directory and
are shipped as part of the frozen builds. Their licenses are compatible with
GPL-3.0-or-later, which is why Rusys itself is GPL-3.0-or-later.

### 1.1 Rufus — 4.15 (2026-06-30)

| | |
|---|---|
| Path | `resources/rufus/` |
| Upstream | <https://github.com/pbatard/rufus> |
| Author | Pete Batard |
| License | **GPL-3.0-or-later** (verbatim copy at `resources/rufus/LICENSE.txt`) |
| Role | Reference implementation. Rusys is an independent Python/PySide6 reimplementation of Rufus concepts; no Rufus code is linked, vendored or executed. |

### 1.2 Ventoy — 1.1.17

| | |
|---|---|
| Path | `resources/ventoy/` |
| Upstream | <https://www.ventoy.net/> · <https://github.com/ventoy/Ventoy> |
| Author | Ventoy Project (longsha) |
| License | **GPL-3.0-or-later** (copy placed at `resources/ventoy/LICENSE-GPL-3.0.txt`) |
| Role | Fully functional. Upstream Ventoy release binaries and scripts, used by the *Multi boot USB* feature to install a multi-ISO USB. Installed unmodified. |

### 1.3 grub2-themes — whitesur, tela, vimix, stylish

| | |
|---|---|
| Path | `resources/themes/` |
| Upstream | <https://github.com/adi1090x/GRUB2-themes> (theme assets) and the <https://github.com/Seowon/ventoy grub2-themes> collection |
| License | **GPL-3.0-or-later** (copy placed at `resources/themes/LICENSE-GPL-3.0.txt`) |
| Role | Fully functional. GRUB2 `gfxmenu` themes and OS icon sets used by the *Multi boot USB* menu theme selector. Used unmodified. |

### 1.4 Simple File Downloader

| | |
|---|---|
| Path | `resources/Downloader/` |
| Upstream | Bundled sample application |
| Author | Gabriel "Naka" |
| License | **MIT** (verbatim copy at `resources/Downloader/LICENSE`) |
| Role | Not used. Rusys does not import, execute or ship this code path at runtime; it is retained only as a reference asset. |

> **Note on bundling.** Because Rusys redistributes GPL-3.0 components, Rusys as
> a whole is distributed under GPL-3.0-or-later. If you redistribute a Rusys
> build, you must convey this license, keep all copyright and license notices
> intact, and make the corresponding source available under GPL-3.0-or-later.

---

## 2. Python runtime dependencies

Resolved via `pip`; not vendored into the repository. Pinned minimums are
declared in `pyproject.toml` and `requirements.txt`.

| Package | Minimum | License | Project |
|---|---|---|---|
| **PySide6** | `>=6.12,<6.13` | LGPL-3.0-only (with Qt for Python licensing terms) | <https://www.qt.io/qt-for-python> |
| **requests** | `>=2.34.2` | Apache-2.0 | <https://requests.readthedocs.io/> |

Transitive dependencies pulled in at runtime include `urllib3` (MIT),
`certifi` (MPL-2.0), `charset-normalizer` (MIT), `idna` (BSD-3-Clause) and
`shiboken6` (LGPL-3.0-only). All are dynamically linked into the frozen builds
and none impose additional obligations beyond attribution.

### 2.1 Build-time only

| Package | Minimum | License |
|---|---|---|
| **setuptools** | `>=80.0` | MIT |
| **PyInstaller** | `>=6.22.3` | GPL-2.0-or-later with a bootloader exception |

PyInstaller's bootloader exception permits distributing a frozen application
under a license of your choice; the generated application is not itself GPL.

---

## 3. Security advisories addressed

Rusys enforces minimum dependency versions that clear the following advisories.
Scanning with `pip-audit` against `pyproject.toml` is expected to report no
known vulnerabilities.

| Advisory | Affected | Fixed in | Status in Rusys |
|---|---|---|---|
| **CVE-2026-25645** (`GHSA-gc5v-m9x4-r6x2`) — insecure temp-file reuse in `requests.utils.extract_zipped_paths()` | `requests` `< 2.33.0` | `2.33.0` | **Cleared** — `>=2.34.2` |
| **CVE-2024-47081** (`GHSA-9hjg-9r4m-mvj7`) — `.netrc` credentials leaked to a third party on redirect | `requests` `< 2.32.4` | `2.32.4` | **Cleared** — `>=2.34.2` |
| **CVE-2024-35195** (`GHSA-9wx4-h78v-vm56`) — `Session.verify = False` silently persists across requests | `requests` `< 2.32.0` | `2.32.0` | **Cleared** — `>=2.34.2` |
| **CVE-2014-1829** (`GHSA-cfj3-7x9c-4p3h`) — `netrc` password obtainable via redirect | `requests` `< 2.3.0` | `2.3.0` | **Cleared** — `>=2.34.2` |

`resources/Downloader/requirements.txt` has also been updated; although that
tree is not a runtime dependency, its historical `requests==2.31.0` pin fell
below all four of the thresholds above.

---

## 4. Attributions

Rusys would not exist without the work of these projects and people:

- **Rufus** — Pete Batard and contributors. <https://github.com/pbatard/rufus>
- **Ventoy** — longsha and contributors. <https://github.com/ventoy/Ventoy>
- **GRUB2** — the boot loader Rusys themes and relies on. <https://www.gnu.org/software/grub/>
- **grub2-themes / adi1090x** — GRUB2 theme and icon assets.
- **Qt for Python (PySide6)** — The Qt Company and the Qt for Python team.
- **Requests** — Kenneth Reitz and contributors.
- **Python** — Python Software Foundation.

Full credits are also shown in the application's *About* dialog.
