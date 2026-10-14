# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Multiboot USB engine for Rusys (real Ventoy backend).

We drive the upstream Ventoy release (shipped under ``resources/ventoy``) to
turn a USB stick into a reliable multiboot device:

  1. ``Ventoy2Disk.sh`` partitions the whole disk (GPT) and installs Ventoy's
     Secure-Boot-capable boot chain (its own shim + MOK-enrolled GRUB) plus a
     large exFAT data partition labelled ``Rusys``.  Ventoy reliably boots
     almost any Linux ISO with Secure Boot enabled (it enrolls its own key in
     MokManager on first boot).
  2. We drop a ``ventoy/ventoy.json`` plugin onto the data partition that points
     Ventoy's menu at one of the four GRUB2 themes (``resources/themes``), so the
     Ventoy boot menu is fully themed (whitesur by default).
  3. ISOs are simply *copied* into ``Rusys_Iso-Files`` on the data partition;
     Ventoy auto-discovers them at boot -- no re-imaging, no grub.cfg editing.

At boot the machine shows the themed Ventoy menu; selecting an ISO boots it
directly.  Themes can be switched at any time via the GUI (Apply theme) without
re-formatting.  This avoids the Secure-Boot signature problem of a hand-rolled
loopback GRUB (distro kernels are not signed by our shim's keys).
"""
from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from typing import Callable, List, Optional, Tuple

from . import checksum  # noqa: F401  (kept for symmetry / future verification)
from .logger import log


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
ISO_DIRNAME = "Rusys_Iso-Files"
THEME_NAME = "whitesur"
# Selectable GRUB2 themes (from the grub2-themes project).  whitesur is the
# default; the GUI lets the user switch between any of these at any time.
AVAILABLE_THEMES = ["whitesur", "tela", "vimix", "stylish"]
MARKER_FILE = ".rusys_multiboot"
# Bundled upstream Ventoy release (real, working Ventoy) used to install the
# boot chain.  Falls back to the user's downloaded copy if the bundle is
# missing (e.g. during development).
VENTOY_BUNDLE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources", "ventoy",
)
VENTOY_FALLBACK_DIR = os.path.join(
    os.path.expanduser("~"), "Downloads", "ventoy",
)
# Ventoy's default data-partition label is "Ventoy"; we set ours to "Rusys" so
# our auto-detect matches, but we accept either.
VENTOY_LABELS = ("rusys", "ventoy")
# On a Ventoy (GPT) disk: partition 1 = large data partition (ISOs + the
# ventoy/ plugin directory); partition 2 = Ventoy's internal EFI image.
ESP_BOOT_DIR = "EFI/BOOT"
ESP_GRUB_DIR = "EFI/fedora"

# Ventoy shows a per-ISO icon by mapping each ISO to a "class" and loading
# ``<theme>/icons/<class>.png``.  This mapping assigns a class from a substring
# of the ISO filename.  Every ``class`` below has a matching icon file in our
# grub2-themes ``icons/`` directory (plus the Ventoy fallback icons we copy in).
MENU_CLASS = [
    {"key": "ubuntu", "class": "ubuntu"},
    {"key": "pop-os", "class": "pop-os"},
    {"key": "pop", "class": "pop-os"},
    {"key": "zorin", "class": "zorin"},
    {"key": "mint", "class": "linuxmint"},
    {"key": "elementary", "class": "elementary"},
    {"key": "kubuntu", "class": "kubuntu"},
    {"key": "lubuntu", "class": "lubuntu"},
    {"key": "xubuntu", "class": "xubuntu"},
    {"key": "deepin", "class": "deepin"},
    {"key": "debian", "class": "debian"},
    {"key": "fedora", "class": "fedora"},
    {"key": "nobara", "class": "nobara"},
    {"key": "korora", "class": "korora"},
    {"key": "arch", "class": "archlinux"},
    {"key": "garuda", "class": "archlinux"},
    {"key": "manjaro", "class": "manjaro"},
    {"key": "endeavour", "class": "endeavouros"},
    {"key": "artix", "class": "artix"},
    {"key": "antergos", "class": "antergos"},
    {"key": "arcolinux", "class": "arcolinux"},
    {"key": "opensuse", "class": "opensuse"},
    {"key": "suse", "class": "opensuse"},
    {"key": "kali", "class": "kali"},
    {"key": "parrot", "class": "parrot"},
    {"key": "gentoo", "class": "gentoo"},
    {"key": "void", "class": "void"},
    {"key": "windows", "class": "windows"},
    {"key": "win", "class": "windows"},
    {"key": "android", "class": "android"},
    {"key": "phoenix", "class": "android"},
    {"key": "chrome", "class": "android"},
    {"key": "freebsd", "class": "freebsd"},
    {"key": "linux", "class": "linux"},
    {"key": "mx", "class": "mx-linux"},
    {"key": "rhel", "class": "red-hat"},
    {"key": "redhat", "class": "red-hat"},
    {"key": "centos", "class": "red-hat"},
    {"key": "haiku", "class": "haiku"},
    {"key": "macosx", "class": "macosx"},
    {"key": "steamos", "class": "steamos"},
    {"key": "solus", "class": "solus"},
    {"key": "nixos", "class": "nixos"},
    {"key": "mageia", "class": "mageia"},
    {"key": "kaos", "class": "kaos"},
    {"key": "chakra", "class": "chakra"},
    {"key": "devuan", "class": "devuan"},
    {"key": "alpine", "class": "AlpineLinux"},
    {"key": "4mlinux", "class": "4MLinux"},
    {"key": "systemrescue", "class": "SystemRescueCD"},
    {"key": "gparted", "class": "gpart"},
]


ProgressCb = Callable[[str, int, int], None]  # (stage, done, total)


# --------------------------------------------------------------------------- #
# Elevated command helper (mirrors privileges.install_udev_rule)
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Single-prompt privilege escalation
# --------------------------------------------------------------------------- #
# Every privileged operation (partition/format/grub-install, mount, add/remove
# ISO) runs through ``sudo`` with a graphical askpass (kdialog/zenity).  The
# first privileged call primes the sudo timestamp (one graphical password
# prompt); all later calls use ``sudo -n`` (cached credentials), so no further
# prompt appears for the rest of the session.  A background thread refreshes the
# timestamp so it never expires while the app is open.  Falls back to per-call
# ``pkexec`` when ``sudo`` is unavailable or not authorised.
import time

_SUDO_READY = False
_SUDO_LOCK = threading.Lock()
_ASKPASS_PATH: Optional[str] = None


def _make_askpass() -> Optional[str]:
    """Create (once) a tiny askpass helper that prompts with kdialog/zenity."""
    global _ASKPASS_PATH
    if _ASKPASS_PATH and os.path.exists(_ASKPASS_PATH):
        return _ASKPASS_PATH
    ask = None
    for tool in ("kdialog", "zenity"):
        if shutil.which(tool):
            ask = tool
            break
    if ask is None:
        return None
    if ask == "kdialog":
        body = "kdialog --password 'Rusys needs administrator privileges' 2>/dev/null\n"
    else:
        body = "zenity --password --title='Rusys' 2>/dev/null\n"
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False, prefix="rusys_askpass_"
    )
    fh.write("#!/bin/bash\n" + body + "exit $?\n")
    fh.close()
    os.chmod(fh.name, 0o755)
    _ASKPASS_PATH = fh.name
    return _ASKPASS_PATH


def _sudo_env() -> dict:
    ap = _make_askpass()
    env = dict(os.environ)
    if ap:
        env["SUDO_ASKPASS"] = ap
        env["SSH_ASKPASS"] = ap
    return env


def _prime_sudo() -> bool:
    """Validate/extend the sudo timestamp (prompts once via askpass)."""
    global _SUDO_READY
    if not shutil.which("sudo"):
        return False
    try:
        r = subprocess.run(
            ["sudo", "-A", "-v"], env=_sudo_env(),
            capture_output=True, text=True, timeout=300,
        )
    except Exception as exc:  # pragma: no cover
        log.debug("sudo prime failed: %s", exc)
        return False
    if r.returncode != 0:
        return False
    with _SUDO_LOCK:
        _SUDO_READY = True
    threading.Thread(target=_sudo_keepalive, daemon=True).start()
    return True


def _sudo_keepalive() -> None:
    while True:
        time.sleep(120)
        with _SUDO_LOCK:
            if not _SUDO_READY:
                return
        try:
            subprocess.run(
                ["sudo", "-A", "-n", "-v"], env=_sudo_env(),
                capture_output=True, text=True, timeout=30,
            )
        except Exception:  # pragma: no cover
            pass


def _run_elevated_legacy(script_body: str, timeout: int = 600) -> Tuple[int, str, str]:
    """Per-call pkexec/sudo fallback when the persistent helper is unavailable."""
    runner = None
    for cand in ("pkexec", "sudo"):
        if shutil.which(cand):
            runner = cand
            break
    if runner is None:
        return 1, "", "no privilege-elevation helper (pkexec/sudo) found"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False, prefix="rusys_mb_"
    ) as fh:
        fh.write("#!/bin/bash\nset -e\n")
        fh.write(script_body)
        script_path = fh.name
    os.chmod(script_path, 0o755)
    try:
        result = subprocess.run(
            [runner, "bash", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except FileNotFoundError:
        return 127, "", f"{runner} not found"
    except subprocess.TimeoutExpired:
        return 124, "", "elevated command timed out (user may have cancelled)"
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def _run_elevated(script_body: str, timeout: int = 600) -> Tuple[int, str, str]:
    """Run *script_body* as root, asking for a password at most ONCE per session.

    Uses a primed ``sudo`` timestamp (graphical askpass).  The first call prompts
    once; later calls reuse cached credentials.  Falls back to per-call
    ``pkexec`` when ``sudo`` is unavailable.
    """
    with _SUDO_LOCK:
        ready = _SUDO_READY
    if not ready and not _prime_sudo():
        return _run_elevated_legacy(script_body, timeout)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False, prefix="rusys_mb_"
    ) as fh:
        fh.write("#!/bin/bash\nset -e\n")
        fh.write(script_body)
        script_path = fh.name
    env = _sudo_env()
    try:
        r = subprocess.run(
            ["sudo", "-A", "-n", "bash", script_path], env=env,
            capture_output=True, text=True, timeout=timeout,
        )
        # Timestamp expired unexpectedly (e.g. between priming and this call):
        # re-prime once (one prompt) and retry with cached credentials.
        if r.returncode != 0 and "password is required" in (r.stderr or ""):
            if _prime_sudo():
                r = subprocess.run(
                    ["sudo", "-A", "-n", "bash", script_path], env=env,
                    capture_output=True, text=True, timeout=timeout,
                )
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "elevated command timed out (user may have cancelled)"
    except FileNotFoundError:
        return 127, "", "sudo not found"
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def _have(cmd: str) -> bool:
    import shutil as _sh
    return bool(_sh.which(cmd))


def _grub_install_bin() -> Optional[str]:
    """Return the available ``grub-install`` binary name.

    Debian/Ubuntu ship ``grub-install``; Fedora/RHEL ship ``grub2-install``.
    Returns ``None`` if neither is present.  (Kept for completeness; the
    Ventoy-based boot chain no longer requires the host grub-install.)
    """
    import shutil as _sh
    for cand in ("grub-install", "grub2-install"):
        if _sh.which(cand):
            return cand
    return None


def _ventoy_efi_source() -> str:
    """Path to the bundled Ventoy Secure-Boot EFI files.

    These are copied from the downloaded Ventoy tree into
    ``resources/ventoy_efi`` so the app is self-contained.
    """
    import rusys

    return os.path.join(
        os.path.dirname(os.path.dirname(rusys.__file__)), "resources", "ventoy_efi"
    )


# --------------------------------------------------------------------------- #
# ISO detection + GRUB menuentry generation
# --------------------------------------------------------------------------- #
def _t_casper(iso: str) -> str:
    return (
        f"  loopback loop {iso}\n"
        f"  linux (loop)/casper/vmlinuz iso-scan/filename={iso} quiet splash ---\n"
        f"  initrd (loop)/casper/initrd\n"
    )


def _t_arch(iso: str) -> str:
    return (
        f"  loopback loop {iso}\n"
        f"  linux (loop)/arch/boot/x86_64/vmlinuz-linux img_loop={iso}\n"
        f"  initrd (loop)/arch/boot/x86_64/initramfs-linux.img\n"
    )


def _t_fedora(iso: str) -> str:
    return (
        f"  loopback loop {iso}\n"
        f"  linux (loop)/isolinux/vmlinuz iso-scan/filename={iso} root=live:{iso} rd.live.image quiet\n"
        f"  initrd (loop)/isolinux/initrd.img\n"
    )


def _t_opensuse(iso: str) -> str:
    return (
        f"  loopback loop {iso}\n"
        f"  linux (loop)/boot/x86_64/loader/linux iso-scan/filename={iso} root=live:{iso} rd.live.image quiet\n"
        f"  initrd (loop)/boot/x86_64/loader/initrd\n"
    )


# Keyword (lowercased) -> template.  First match wins.
_FAMILY_TEMPLATES: List[Tuple[str, Callable[[str], str]]] = [
    ("ubuntu", _t_casper),
    ("mint", _t_casper),
    ("elementary", _t_casper),
    ("zorin", _t_casper),
    ("pop", _t_casper),
    ("kali", _t_casper),
    ("debian", _t_casper),
    ("antix", _t_casper),
    ("mx linux", _t_casper),
    ("devuan", _t_casper),
    ("arch", _t_arch),
    ("manjaro", _t_arch),
    ("artix", _t_arch),
    ("endeavouros", _t_arch),
    ("arco", _t_arch),
    ("fedora", _t_fedora),
    ("centos", _t_fedora),
    ("almalinux", _t_fedora),
    ("rocky", _t_fedora),
    ("rhel", _t_fedora),
    ("qubes", _t_fedora),
    ("opensuse", _t_fedora),
    ("suse", _t_fedora),
]


def _family_template(name: str) -> Optional[Callable[[str], str]]:
    low = (name or "").lower()
    for keyword, templ in _FAMILY_TEMPLATES:
        if keyword in low:
            return templ
    return None


# Map a display name to the b-grub theme icon file (icons/<class>.png) so the
# GRUB menu shows a per-distro icon.  Falls back to a generic Linux icon.
_ICON_MAP: List[Tuple[str, str]] = [
    ("ubuntu", "ubuntu"),
    ("mint", "linuxmint"),
    ("elementary", "elementary"),
    ("zorin", "ubuntu"),
    ("pop", "pop-os"),
    ("kali", "kali"),
    ("debian", "debian"),
    ("antix", "debian"),
    ("mx linux", "mx-linux"),
    ("mx", "mx-linux"),
    ("devuan", "devuan"),
    ("arch", "archlinux"),
    ("manjaro", "manjaro"),
    ("artix", "artix"),
    ("endeavouros", "endeavouros"),
    ("arco", "arcolinux"),
    ("garuda", "garuda"),
    ("fedora", "fedora"),
    ("centos", "centos"),
    ("alma", "alma"),
    ("rocky", "rocky"),
    ("rhel", "centos"),
    ("qubes", "fedora"),
    ("opensuse", "opensuse"),
    ("suse", "opensuse"),
    ("gentoo", "gentoo"),
    ("void", "void"),
    ("alpine", "alpine"),
    ("linux", "linux"),
]


def _icon_class(name: str) -> str:
    low = (name or "").lower()
    for keyword, icon in _ICON_MAP:
        if keyword in low:
            return icon
    if "windows" in low:
        return "windows"
    return "gnu-linux"


def _menu_entry(name: str, iso_grub_path: str, wimboot: bool) -> str:
    """Build one ``menuentry`` block for *name* at grub path *iso_grub_path*."""
    low = name.lower()
    icon = _icon_class(name)
    if "windows" in low:
        if wimboot:
            body = f"  loopback loop {iso_grub_path}\n  wimboot @:bootmgr\n"
        else:
            body = (
                f"  loopback loop {iso_grub_path}\n"
                f"  echo 'wimboot.efi not bundled -- Windows ISO needs it; see docs'\n"
                f"  sleep 3\n"
            )
    else:
        templ = _family_template(name)
        if templ is not None:
            body = templ(iso_grub_path)
        else:
            body = (
                f"  loopback loop {iso_grub_path}\n"
                f"  echo 'No distro-specific template; trying embedded bootloader'\n"
                f"  configfile (loop)/boot/grub/grub.cfg\n"
            )
    safe = name.replace('"', "")
    # --class drives the per-entry icon (icons/<class>.png) in the b-grub theme.
    return (
        f"menuentry \"{safe}\" --class {icon} {{\n"
        f"  set isofile=\"{iso_grub_path}\"\n"
        f"{body}"
        f"}}\n\n"
    )


def generate_grub_cfg(
    iso_entries: List[Tuple[str, str]], theme_name: str = THEME_NAME
) -> str:
    """Return the full ``grub.cfg`` text.

    *iso_entries* is a list of ``(display_name, grub_path)`` where *grub_path*
    is the path GRUB sees, e.g. ``"/Rusys_Iso-Files/ubuntu-24.04.iso"``.
    """
    lines: List[str] = []
    lines.append("set timeout=30")
    lines.append("set default=0")
    lines.append("insmod all_video")
    lines.append("insmod efi_gop")
    lines.append("insmod efi_uga")
    lines.append("insmod vbe")
    lines.append("insmod gfxterm")
    lines.append("insmod gfxmenu")
    lines.append("insmod png")
    lines.append("insmod font")
    # Force a graphical video mode BEFORE switching the terminal to gfxterm.
    # Without an active gfxterm the theme cannot render and GRUB silently falls
    # back to the plain text/tty menu.
    lines.append("set gfxmode=1024x768,800x600,auto")
    lines.append("set gfxpayload=keep")
    # Load the bundled Unifont so the b-grub theme (which references
    # "Unifont Regular 16") can actually render.  Without this GRUB silently
    # drops the theme and shows a plain text/tty menu.
    lines.append(f"loadfont $prefix/themes/{theme_name}/fonts/unifont.pf2")
    lines.append("terminal_output gfxterm")
    lines.append("insmod loopback")
    lines.append("insmod iso9660")
    lines.append("insmod exfat")
    lines.append("insmod part_gpt")
    lines.append("insmod fat")
    lines.append("insmod search")
    lines.append("insmod search_label")
    lines.append(f"set theme=$prefix/themes/{theme_name}/theme.txt")
    # The ISOs live on the exFAT data partition (labelled "Rusys"), not on the
    # ESP where this grub.cfg is stored.  Point grub's root at it so the
    # loopback paths in the menuentries resolve correctly.
    lines.append("search --no-floppy --label --set=root Rusys")
    lines.append("")
    lines.append("menuentry \"Reboot\" { reboot }")
    lines.append("menuentry \"Shutdown\" { halt }")
    lines.append("")
    if not iso_entries:
        lines.append("# No ISOs yet -- copy files into Rusys_Iso-Files and re-prepare.")
        lines.append("")
    for name, grub_path in iso_entries:
        lines.append(_menu_entry(name, grub_path, wimboot=False))
    return "\n".join(lines)


def generate_grub_autodetect(theme_name: str = THEME_NAME) -> str:
    """Return a GRUB config that auto-discovers ISOs *at boot*.

    Instead of a static menu built by the app, GRUB scans the data partition
    (label "Rusys") for ``*.iso`` files in the root and in *any* sub-directory,
    and creates a menu entry for each.  This means the user can copy ISOs from
    any other PC into any folder on the stick and they simply appear on the
    next boot -- no app "Refresh" / re-prepare step required.
    """
    L: List[str] = []
    L.append("set timeout=30")
    L.append("set default=0")
    L.append("insmod all_video")
    L.append("insmod efi_gop")
    L.append("insmod efi_uga")
    L.append("insmod vbe")
    L.append("insmod gfxterm")
    L.append("insmod gfxmenu")
    L.append("insmod png")
    L.append("insmod font")
    L.append("set gfxmode=1024x768,800x600,auto")
    L.append("set gfxpayload=keep")
    L.append(f"set theme=$prefix/themes/{theme_name}/theme.txt")
    # Load every .pf2 shipped with the selected theme (unifont/terminus/etc.) so
    # the theme's item_font / terminal-font names actually resolve.
    L.append(f"for f in ($prefix)/themes/{theme_name}/*.pf2; do loadfont $f; done")
    L.append("terminal_output gfxterm")
    L.append("insmod loopback")
    L.append("insmod iso9660")
    L.append("insmod exfat")
    L.append("insmod part_gpt")
    L.append("insmod part_msdos")
    L.append("insmod fat")
    L.append("insmod ntfs")
    L.append("insmod search")
    L.append("insmod search_label")
    L.append("insmod regexp")
    L.append("insmod linux")
    L.append("insmod chain")
    L.append("")
    L.append('# Locate the data partition that holds the ISO files.')
    L.append('search --no-floppy --label --set=datadev Rusys')
    L.append('set root=$datadev')
    L.append("")
    L.append('# Build one menu entry per discovered ISO (from any folder).')
    L.append('function add_iso {')
    L.append('    set isofile="$1"')
    L.append('    regexp --set=isoname \'([^/]*)\\.iso$\' "$isofile"')
    L.append('    menuentry "$isoname" "$isofile" {')
    L.append('    set isofile="$2"')
    L.append('    regexp --set=isopath \'\\([^)]*\\)(.*)\' "$isofile"')
    L.append('    loopback loop "$isofile"')
    L.append('    # Ubuntu / Debian / Mint / Zorin / Pop!_OS / Kali (casper)')
    L.append('    if [ -e (loop)/casper/vmlinuz ]; then')
    L.append('        linux (loop)/casper/vmlinuz boot=casper iso-scan/filename="$isopath" quiet splash ---')
    L.append('        initrd (loop)/casper/initrd')
    L.append('        return')
    L.append('    fi')
    L.append('    if [ -e (loop)/casper/vmlinuz.efi ]; then')
    L.append('        linux (loop)/casper/vmlinuz.efi boot=casper iso-scan/filename="$isopath" quiet splash ---')
    L.append('        initrd (loop)/casper/initrd')
    L.append('        return')
    L.append('    fi')
    L.append('        # Fedora / RHEL live')
    L.append('        if [ -e (loop)/images/pxeboot/vmlinuz ]; then')
    L.append('            linux (loop)/images/pxeboot/vmlinuz iso-scan/filename="$isofile" root=live:CDLABEL=Fedora rd.live.image quiet')
    L.append('            initrd (loop)/images/pxeboot/initrd.img')
    L.append('            return')
    L.append('        fi')
    L.append('        # Arch / Manjaro (archiso)')
    L.append('        if [ -e (loop)/arch/boot/x86_64/vmlinuz-linux ]; then')
    L.append('            linux (loop)/arch/boot/x86_64/vmlinuz-linux img_loop="$isofile" earlymodules=loop')
    L.append('            initrd (loop)/arch/boot/x86_64/initramfs-linux.img')
    L.append('            return')
    L.append('        fi')
    L.append('        # Generic: chain-load the ISO\'s own UEFI bootloader.')
    L.append('        if [ -e (loop)/EFI/BOOT/bootx64.efi ]; then')
    L.append('            chainloader (loop)/EFI/BOOT/bootx64.efi')
    L.append('            return')
    L.append('        fi')
    L.append('        if [ -e (loop)/efi/boot/bootx64.efi ]; then')
    L.append('            chainloader (loop)/efi/boot/bootx64.efi')
    L.append('            return')
    L.append('        fi')
    L.append('        loopback --delete loop')
    L.append('        echo "No automatic boot method for $isofile"')
    L.append('    }')
    L.append('}')
    L.append("")
    L.append('# Scan: ISOs in the data root, then inside any sub-directory.')
    L.append('for isofile in ($datadev)/*.iso; do')
    L.append('    if [ -e "$isofile" ]; then add_iso "$isofile"; fi')
    L.append('done')
    L.append('for d in ($datadev)/*; do')
    L.append('    if [ -d "$d" ]; then')
    L.append('        for isofile in "$d"/*.iso; do')
    L.append('            if [ -e "$isofile" ]; then add_iso "$isofile"; fi')
    L.append('        done')
    L.append('    fi')
    L.append('done')
    L.append("")
    L.append('if [ -z "$isoname" ]; then')
    L.append('    menuentry "No ISO files found" {')
    L.append('        echo "Copy .iso files into any folder on this USB, then reboot."')
    L.append('        sleep 8')
    L.append('    }')
    L.append('fi')
    L.append("")
    L.append('menuentry "Reboot" { reboot }')
    L.append('menuentry "Shutdown" { halt }')
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# Theme install
# --------------------------------------------------------------------------- #
def install_theme(
    boot_grub_dir: str, theme_source_dir: str, theme_name: str = THEME_NAME
) -> str:
    """Copy *theme_source_dir* into ``<boot_grub_dir>/themes/<theme_name>``.

    Returns the absolute path of the installed ``theme.txt``.
    """
    dest = os.path.join(boot_grub_dir, "themes", theme_name)
    os.makedirs(dest, exist_ok=True)
    for item in os.listdir(theme_source_dir):
        if item in (".git", ".github"):
            continue
        src = os.path.join(theme_source_dir, item)
        dst = os.path.join(dest, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    theme_txt = os.path.join(dest, "theme.txt")
    log.info("b-grub theme installed at %s", dest)
    return theme_txt


def theme_source_dir(name: str = THEME_NAME) -> str:
    """Return the on-disk directory for theme *name*."""
    base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "resources",
        "themes",
    )
    p = os.path.join(base, name)
    if os.path.isdir(p):
        return p
    return os.path.join(base, THEME_NAME)


def install_theme_to_esp(esp_mount: str, theme_name: str = THEME_NAME) -> None:
    """Install *theme_name* into both GRUB prefix dirs on the mounted ESP."""
    src = theme_source_dir(theme_name)
    for prefix in (ESP_GRUB_DIR, ESP_BOOT_DIR):
        install_theme(os.path.join(esp_mount, prefix), src, theme_name)


# --------------------------------------------------------------------------- #
# USB preparation + ISO management
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Ventoy backend (real upstream Ventoy)
# --------------------------------------------------------------------------- #
def ventoy_dir() -> str:
    """Return the directory of the bundled Ventoy release."""
    if os.path.isdir(VENTOY_BUNDLE_DIR):
        return VENTOY_BUNDLE_DIR
    return VENTOY_FALLBACK_DIR


def build_ventoy_json(theme_name: str = THEME_NAME) -> str:
    """Return the ``ventoy.json`` plugin config pointing at *theme_name*."""
    cfg = {
        "control": [
            {"VTOY_DEFAULT_MENU_MODE": "1"},
            {"VTOY_FILT_DOT_UNDERSCORE_FILE": "1"},
        ],
        "theme": {
            "file": "/ventoy/themes/%s/theme.txt" % theme_name,
            "display_mode": "GUI",
        },
        # Per-ISO icons: map ISO filename substrings to an icon class.  The
        # icon file is <theme>/icons/<class>.png (merged with Ventoy's own
        # fallback icons in install_ventoy_theme).
        "menu_class": MENU_CLASS,
    }
    return json.dumps(cfg, indent=4)


# Ventoy's own theme ships a handful of icons (notably the "unknown ISO"
# fallback).  We merge these into every theme so the menu never lacks an icon.
_VENTOY_FALLBACK_ICONS = os.path.join(
    VENTOY_BUNDLE_DIR, "plugin", "ventoy", "theme", "icons"
)


def install_ventoy_theme(data_mount: str, theme_name: str = THEME_NAME) -> None:
    """Copy *theme_name* into ``<data>/ventoy/themes`` and write ventoy.json."""
    vt = os.path.join(data_mount, "ventoy")
    os.makedirs(os.path.join(vt, "themes"), exist_ok=True)
    src = theme_source_dir(theme_name)
    dest = os.path.join(vt, "themes", theme_name)
    if os.path.isdir(src):
        shutil.copytree(src, dest, dirs_exist_ok=True)
    # Merge Ventoy's fallback icons (esp. vtoyiso.png) so every class resolves.
    icon_dst = os.path.join(dest, "icons")
    os.makedirs(icon_dst, exist_ok=True)
    if os.path.isdir(_VENTOY_FALLBACK_ICONS):
        for name in os.listdir(_VENTOY_FALLBACK_ICONS):
            if name.lower().endswith(".png") and not os.path.exists(
                os.path.join(icon_dst, name)
            ):
                shutil.copy2(
                    os.path.join(_VENTOY_FALLBACK_ICONS, name), icon_dst
                )
    with open(os.path.join(vt, "ventoy.json"), "w", encoding="utf-8") as fh:
        fh.write(build_ventoy_json(theme_name))
    log.info("Ventoy theme '%s' installed at %s", theme_name, dest)


def run_ventoy_install(
    device_path: str, label: str = "Rusys", gpt: bool = True
) -> Tuple[int, str, str]:
    """Run Ventoy2Disk.sh to install the Ventoy boot chain on *device_path*.

    Returns ``(rc, out, err)`` where *rc* is Ventoy2Disk's exit code (parsed
    from the script output, since the install is driven via stdin answers).
    """
    vdir = ventoy_dir()
    if not os.path.isfile(os.path.join(vdir, "Ventoy2Disk.sh")):
        return (-1, "", "Ventoy installer not found at %s" % vdir)
    gpt_flag = "-g" if gpt else ""
    script = (
        'DEV="' + device_path + '"\n'
        'for mp in $(lsblk -n -o MOUNTPOINT "$DEV" 2>/dev/null | grep -v \'^$\'); do umount "$mp" 2>/dev/null || true; done\n'
        'umount "$DEV"* 2>/dev/null || true\n'
        'cd "' + vdir + '" || exit 7\n'
        "printf 'y\\ny\\ny\\ny\\n' > /tmp/rusys_vt_ans\n"
        'sh Ventoy2Disk.sh ' + gpt_flag + ' -I -L "' + label + '" "$DEV" < /tmp/rusys_vt_ans\n'
        'EC=$?\n'
        'echo "VENTOY_RC=$EC"\n'
    )
    rc, out, err = _run_elevated(script)
    m = re.search(r"VENTOY_RC=(\d+)", out + err)
    if m:
        rc = int(m.group(1))
    return (rc, out, err)


def set_data_label(
    device_path: str, label: str = "Rusys"
) -> Tuple[int, str, str]:
    """Force the Ventoy data partition (part 1) volume label to *label*.

    Ventoy2Disk.sh ignores the ``-L`` flag in this release, so the data
    partition otherwise keeps the default "Ventoy" name.  We relabel it
    explicitly to "Rusys" (the required drive name).  Requires root.
    """
    part = data_partition_path(device_path)
    script = (
        'PART="' + part + '"\n'
        'for i in $(seq 1 20); do [ -b "$PART" ] && break; sleep 1; done\n'
        'for mp in $(lsblk -n -o MOUNTPOINT "$PART" 2>/dev/null | grep -v \'^$\'); do umount "$mp" 2>/dev/null || true; done\n'
        'umount "$PART" 2>/dev/null || true\n'
        'exfatlabel "$PART" ' + label + ' 2>/dev/null\n'
        'echo "RUSYS_LABEL_RC=$?"\n'
    )
    return _run_elevated(script)


# Hide Ventoy's internal EFI partition (labelled "VTOYEFI") from file managers
# so only the "Rusys" data partition appears.  Implemented with a udev rule that
# sets UDISKS_IGNORE=1 (udisks2 honours this and hides the device in
# Nautilus/Dolphin).  Requires root; idempotent.
HIDE_EFI_RULE_PATH = "/etc/udev/rules.d/99-rusys-hide-ventoy-efi.rules"
HIDE_EFI_RULE = (
    "# Rusys: hide Ventoy's internal EFI partition from file managers\n"
    '# so only the "Rusys" data partition is shown.\n'
    'SUBSYSTEM=="block", ENV{ID_FS_LABEL}=="VTOYEFI", ENV{UDISKS_IGNORE}="1"\n'
)


def install_hide_efi_rule() -> Tuple[int, str, str]:
    """Install the udev rule that hides the VTOYEFI partition from file managers.

    Returns ``(rc, out, err)``.  Safe to call repeatedly.
    """
    script = (
        'cat > "' + HIDE_EFI_RULE_PATH + '" <<\'RULEOF\'\n'
        + HIDE_EFI_RULE
        + 'RULEOF\n'
        'udevadm control --reload-rules 2>/dev/null\n'
        'udevadm trigger --subsystem-match=block 2>/dev/null\n'
        'echo RUSYS_EFI_RULE_DONE\n'
    )
    return _run_elevated(script)


def _install_ventoy_theme_elevated(
    device_path: str, theme_name: str = THEME_NAME
) -> Tuple[int, str, str]:
    """Mount the Ventoy data partition, install the theme + ventoy.json, unmount."""
    part = data_partition_path(device_path)
    src = theme_source_dir(theme_name)
    uid = os.getuid()
    gid = os.getgid()
    json_str = build_ventoy_json(theme_name)
    script = (
        'PART="' + part + '"\n'
        'for i in $(seq 1 20); do [ -b "$PART" ] && break; sleep 1; done\n'
        'mkdir -p /mnt/rusys_vt\n'
        'mount -o uid=' + str(uid) + ',gid=' + str(gid) + ' "$PART" /mnt/rusys_vt\n'
        'mkdir -p "/mnt/rusys_vt/ventoy/themes"\n'
        'rm -rf "/mnt/rusys_vt/ventoy/themes/' + theme_name + '"\n'
        "cp -r '" + src + "/.' \"/mnt/rusys_vt/ventoy/themes/" + theme_name + "\"\n"
        'cat > "/mnt/rusys_vt/ventoy/ventoy.json" <<\'RVTJSON\'\n'
        + json_str + '\n'
        + 'RVTJSON\n'
        + 'mkdir -p "/mnt/rusys_vt/' + ISO_DIRNAME + '"\n'
        # Hide the Ventoy config folder from the file manager (works with the
        # standard Linux .hidden mechanism used by Nautilus/Dolphin) so only
        # Rusys_Iso-Files is visible. Ventoy still reads /ventoy at boot.
        + 'printf "ventoy\\n" > "/mnt/rusys_vt/.hidden" 2>/dev/null || true\n'
        + 'umount /mnt/rusys_vt 2>/dev/null || true\n'
        + 'umount "$PART" 2>/dev/null || true\n'
        + 'exfatlabel "$PART" Rusys 2>/dev/null || true\n'
        + 'echo RUSYS_THEME_DONE\n'
    )
    return _run_elevated(script)


def apply_theme_to_ventoy(
    device_path: str, theme_name: str = THEME_NAME
) -> dict:
    """Switch the active Ventoy menu theme without re-formatting."""
    rc, out, err = _install_ventoy_theme_elevated(device_path, theme_name)
    # Also ensure the VTOYEFI partition stays hidden from file managers.
    install_hide_efi_rule()
    return {"returncode": rc, "stdout": out, "stderr": err}


def is_prepared(data_mount: str, esp_mount: Optional[str] = None) -> bool:
    """Return True if the volume looks like a Rusys/Ventoy multiboot USB.

    *data_mount* is the mounted Ventoy data partition; the presence of the
    ``ventoy/ventoy.json`` plugin we write distinguishes a Rusys-prepared stick.
    """
    if not data_mount or not os.path.isdir(data_mount):
        return False
    return os.path.isfile(os.path.join(data_mount, "ventoy", "ventoy.json"))


def is_prepared_label(device_path: str) -> bool:
    """Cheap (no-mount) check: does *device_path* look like a Rusys/Ventoy USB?

    Inspects partition labels via ``lsblk``; a data partition labelled
    "Rusys" and/or "Ventoy" marks one of our sticks.  Used by the GUI to
    auto-select the right device without mounting.
    """
    try:
        out = subprocess.check_output(
            ["lsblk", "-n", "-o", "LABEL,PATH", device_path],
            stderr=subprocess.DEVNULL,
        ).decode()
    except Exception:
        return False
    labels = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            labels.append(line.split(None, 1)[0].strip())
    return any(l.lower() in VENTOY_LABELS for l in labels)


# Image-file extensions Ventoy boots (ISO and disk images alike) — these are
# what the ISO list shows.
IMAGE_EXTS = (".iso", ".img", ".wim", ".vhd", ".vhdx", ".efi", ".vtoy")


def list_isos(mount_point: str) -> List[str]:
    """Return sorted ISO/image filenames found on the Ventoy data partition.

    Ventoy scans the whole partition recursively, so we mirror that: every
    image file (``.iso``, ``.img``, ``.wim``, ``.vhd`` …) under *mount_point* is
    listed (the ``ventoy/`` plugin directory is skipped).  ISOs the user adds
    land in ``Rusys_Iso-Files`` but any other location works too.
    """
    found = []
    for root, dirs, files in os.walk(mount_point):
        # Don't descend into / collect Ventoy's own plugin directory.
        if root == os.path.join(mount_point, "ventoy"):
            dirs[:] = []
            continue
        for f in files:
            if f.lower().endswith(IMAGE_EXTS):
                found.append(f)
    return sorted(found)


def _regenerate_grub(esp_mount: str, data_mount: str, theme_name: str = THEME_NAME) -> str:
    """Rebuild grub.cfg on the ESP.

    The deployed config auto-discovers ISOs at boot (see
    :func:`generate_grub_autodetect`), so this simply (re)installs that dynamic
    template to BOTH ``EFI/fedora`` and ``EFI/BOOT`` -- the shim may hand GRUB
    either prefix.
    """
    cfg = generate_grub_autodetect(theme_name=theme_name)
    last = None
    for prefix_dir in (ESP_GRUB_DIR, ESP_BOOT_DIR):
        boot_dir = os.path.join(esp_mount, prefix_dir)
        os.makedirs(boot_dir, exist_ok=True)
        cfg_path = os.path.join(boot_dir, "grub.cfg")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            fh.write(cfg)
        log.info("Regenerated %s (auto-detect template)", cfg_path)
        last = cfg_path
    return last


def esp_partition_path(device_path: str) -> str:
    """Return Ventoy's internal EFI partition node (partition 2 on GPT)."""
    base = os.path.basename(device_path)
    if base.startswith("nvme") or base.startswith("mmcblk"):
        return f"{device_path}p2"
    return f"{device_path}2"


def prepare_usb(
    device_path: str,
    label: str = "Rusys",
    data_fstype: str = "ntfs",
    esp_size_mib: int = 512,
    theme_name: str = THEME_NAME,
    progress_cb: Optional[ProgressCb] = None,
) -> dict:
    """Install the real Ventoy boot chain + apply *theme_name* on *device_path*.

    Destructive: wipes the whole device via ``Ventoy2Disk.sh``.  Requires root
    (uses :func:`_run_elevated`).  Returns a result dict with status details.
    """
    if progress_cb:
        progress_cb(0, 3, "install")
    rc, out, err = run_ventoy_install(device_path, label=label, gpt=True)
    result = {
        "returncode": rc,
        "boot_chain": "ventoy",
        "secure_boot": True,
        "stdout": out,
        "stderr": err,
    }
    if rc != 0:
        log.warning("prepare_usb (Ventoy install) failed (rc=%d): %s", rc, err)
        return result
    if progress_cb:
        progress_cb(2, 3, "theme")
    rc2, out2, err2 = _install_ventoy_theme_elevated(device_path, theme_name)
    # Ventoy2Disk ignores -L, so force the drive name to "Rusys" explicitly.
    set_data_label(device_path, label)
    if progress_cb:
        progress_cb(3, 3, "done")
    result.update(
        {
            "theme_returncode": rc2,
            "theme_stdout": out2,
            "theme_stderr": err2,
        }
    )
    if rc2 != 0:
        log.warning("prepare_usb (theme install) failed (rc=%d): %s", rc2, err2)
    # Hide Ventoy's internal EFI partition so only "Rusys" shows in the FM.
    install_hide_efi_rule()
    return result


def add_iso(
    data_mount: str,
    iso_src: str,
    esp_mount: Optional[str] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> str:
    """Copy *iso_src* into ``Rusys_Iso-Files`` on the Ventoy data partition.

    Ventoy auto-discovers ISOs at boot, so no grub.cfg rewrite is needed.
    Returns the installed ISO path.  If *cancel_event* is set during the copy
    the operation is aborted (the partially written file is removed) and
    ``RuntimeError`` is raised.
    """
    if not os.path.isfile(iso_src):
        raise RuntimeError(f"ISO not found: {iso_src}")
    folder = os.path.join(data_mount, ISO_DIRNAME)
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, os.path.basename(iso_src))
    size = os.path.getsize(iso_src)
    written = 0
    with open(iso_src, "rb") as src, open(dest, "wb") as dst:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                try:
                    dst.close()
                    os.remove(dest)
                except OSError:
                    pass
                raise RuntimeError("Operation cancelled by user")
            chunk = src.read(4 * 1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
            # Force the chunk down to the device so the progress value reflects
            # real write throughput (otherwise the OS caches everything and the
            # bar jumps to 100% while data is still flushing to the USB).
            dst.flush()
            os.fsync(dst.fileno())
            written += len(chunk)
            if progress_cb:
                progress_cb(written, size)
    log.info("Added ISO %s -> %s", iso_src, dest)
    return dest


def remove_iso(
    data_mount: str,
    iso_name: str,
    esp_mount: Optional[str] = None,
) -> None:
    """Delete one ISO from ``Rusys_Iso-Files`` (Ventoy re-scans at boot)."""
    path = os.path.join(data_mount, ISO_DIRNAME, iso_name)
    if os.path.isfile(path):
        os.remove(path)
    log.info("Removed ISO %s", iso_name)


# --------------------------------------------------------------------------- #
# Mount helpers (used by the GUI to read/write the data partition)
# --------------------------------------------------------------------------- #
def mount_partition(partition_path: str, mountpoint: Optional[str] = None) -> str:
    """Mount *partition_path* (e.g. /dev/sdb2) and return the mount point.

    Uses :func:`_run_elevated` because normal users cannot mount block
    devices.  Creates a temp mountpoint when none is supplied.
    """
    mp = mountpoint or tempfile.mkdtemp(prefix="rusys_mnt_")
    os.makedirs(mp, exist_ok=True)
    uid = os.getuid()
    gid = os.getgid()
    rc, _out, err = _run_elevated(
        f"mount -o uid={uid},gid={gid} '{partition_path}' '{mp}'\n"
    )
    if rc != 0:
        raise RuntimeError(f"Could not mount {partition_path}: {err}")
    return mp


def unmount_partition(mountpoint: str) -> None:
    """Unmount *mountpoint* (best-effort)."""
    _run_elevated(f"umount '{mountpoint}' 2>/dev/null || true\n")


def eject_device(device_path: str) -> Tuple[int, str, str]:
    """Unmount all partitions of *device_path* and power the device off.

    Best-effort: failures are reported but not fatal.  Requires root (uses
    :func:`_run_elevated`, so it reuses the cached sudo credential).
    """
    script = (
        f"umount {device_path}* 2>/dev/null || true\n"
        f"udisksctl power-off -b {device_path} 2>/dev/null || true\n"
        "echo RUSYS_EJECT_DONE\n"
    )
    return _run_elevated(script)


def data_partition_path(device_path: str) -> str:
    """Return the data-partition device node for a prepared Ventoy (GPT) disk.

    Ventoy layout: partition 1 = large data partition (ISOs + ventoy/ dir);
    partition 2 = Ventoy's internal EFI image.
    """
    base = os.path.basename(device_path)
    # /dev/sdb -> /dev/sdb1 ; /dev/nvme0n1 -> /dev/nvme0n1p1
    if base.startswith("nvme") or base.startswith("mmcblk"):
        return f"{device_path}p1"
    return f"{device_path}1"
