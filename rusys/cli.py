# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Command-line interface for Rusys.

Examples
--------
  rusys --gui                      # launch the graphical interface
  rusys --download "Linux/Ubuntu/Desktop" --dir ~/iso
  rusys --image ~/iso/ubuntu.iso --device /dev/sdb --verify
  rusys --check ~/iso/ubuntu.iso --sha256 <hash>
  rusys --version
"""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__, __app_name__
from .core import checksum
from .core.devices import add_file_target, enumerate_devices
from .core.downloader import Downloader
from .core.flash_helpers import SECURE_BOOT_ADVISORY
from .core.flasher import flash_image
from .core.settings import Settings, load_settings, save_settings
from .data.os_catalog import ROOT, load_user_overrides


def _resolve_leaf(path: str):
    """Resolve a 'Parent/Child/Leaf' catalogue path to a CatalogNode."""
    node = ROOT
    parts = [p for p in path.strip("/").split("/") if p]
    for part in parts:
        found = None
        for c in node.children:
            if c.name.lower() == part.lower():
                found = c
                break
        if found is None:
            return None
        node = found
    return node


def cmd_download(args) -> int:
    leaf = _resolve_leaf(args.download) if args.download else None
    if leaf is None or not leaf.leaf_url():
        print(f"Catalogue path not found or has no download link: {args.download}")
        return 2
    url = leaf.leaf_url()
    if leaf.iso_url and Downloader.is_direct_iso(url):
        dest_dir = args.dir or os.path.expanduser("~/Downloads")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(url.split("?")[0]))
        print(f"Downloading {url}\n  -> {dest}")
        Downloader(url, dest).run(progress_cb=lambda d, t, s: print(f"  {d}/{t} {s:.0f} B/s", end="\r"))
        print("\nDone.")
        return 0
    print(f"Leaf '{leaf.name}' has no direct ISO URL. Open its page:\n  {leaf.page_url}")
    return 0


def cmd_flash(args) -> int:
    settings = load_settings()
    device = None
    if args.device:
        # match by path among enumerated devices or treat as explicit path
        for d in enumerate_devices():
            if d.path == args.device:
                device = d
                break
        if device is None:
            if os.path.isfile(args.device):
                device = add_file_target(args.device)
            else:
                # Allow raw device path (e.g. when run as root)
                from .core.devices import Device, ensure_safe_target
                device = Device(path=args.device, size_bytes=0, is_file=False)
                try:
                    ensure_safe_target(device)
                except Exception as exc:
                    print(f"Target error: {exc}")
                    return 2
    if device is None:
        print("No valid target device. Use --device /dev/sdX or a file path.")
        return 2

    if args.check:
        print("Verifying source image hash...")
        if not checksum.verify_file(args.image, args.sha256, "sha256"):
            print("Checksum mismatch!")
            return 1
        print("Checksum OK.")
        return 0

    if args.secure_boot_warn:
        print("Secure Boot advisory (#2244):")
        print(SECURE_BOOT_ADVISORY.format(name=device.path))

    result = flash_image(
        args.image, device,
        verify=not args.no_verify,
        custom_ops=settings.custom_ops if settings.custom_ops_enabled else None,
        run_custom_ops=settings.custom_ops_enabled,
    )
    print(f"Wrote {result['written']} bytes. Verified={result['verified']}.")
    return 0


def cmd_check(args) -> int:
    ok = checksum.verify_file(args.image, args.sha256, "sha256")
    print(f"{args.image}: {'OK' if ok else 'MISMATCH'} ({args.sha256})")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=__app_name__.lower(), description=__doc__)
    p.add_argument("--version", action="version", version=f"{__app_name__} {__version__}")
    p.add_argument("--gui", action="store_true", help="Launch the graphical interface.")
    p.add_argument("--download", metavar="CATALOG_PATH",
                   help="Download the ISO for a catalogue path, e.g. 'Linux/Ubuntu/Desktop'.")
    p.add_argument("--dir", help="Download directory.")
    p.add_argument("--image", help="Source image file.")
    p.add_argument("--device", help="Target device (e.g. /dev/sdb) or file.")
    p.add_argument("--verify", action="store_true", help="Verify after writing (default).")
    p.add_argument("--no-verify", action="store_true", help="Skip post-write verification.")
    p.add_argument("--check", action="store_true", help="Only verify the image hash.")
    p.add_argument("--sha256", help="Expected SHA-256 for --check.")
    p.add_argument("--secure-boot-warn", action="store_true",
                   help="Print the Secure Boot (PCA2011) advisory and continue.")
    p.add_argument("--silent", action="store_true",
                   help="Use silent/unattended install defaults where supported.")
    p.add_argument("--offscreen", action="store_true",
                   help="Run the GUI under the offscreen Qt platform (testing).")
    return p


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load catalogue overrides if present.
    overrides = os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "rusys", "catalog_overrides.json",
    )
    load_user_overrides(overrides)

    if args.silent:
        s = load_settings()
        s.silent_install = True
        save_settings(s)

    # Dispatch.
    if args.download:
        return cmd_download(args)
    if args.check and args.image and args.sha256:
        return cmd_check(args)
    if args.image and args.device:
        return cmd_flash(args)
    if args.gui or args.offscreen:
        from .main import run_gui
        return run_gui(offscreen=args.offscreen)
    # Default: open the GUI.
    from .main import run_gui
    return run_gui(offscreen=False)


if __name__ == "__main__":
    raise SystemExit(main())
