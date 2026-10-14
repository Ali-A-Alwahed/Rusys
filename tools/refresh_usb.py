#!/usr/bin/env python3
"""Sync the Ventoy theme + ventoy.json onto a prepared Rusys (Ventoy) USB.

Run as root.  Detects the Ventoy data partition (label "Ventoy" or "Rusys"),
mounts it, installs the selected GRUB2 theme via the Ventoy theme plugin, lists
the ISOs it found, and unmounts.  Optional first argument = theme name
(default: whitesur).
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rusys.core.multiboot as mb

RUSYS_ROOT = "/mnt/rusys_refresh"
THEME = sys.argv[1] if len(sys.argv) > 1 else mb.THEME_NAME


def find_data_node():
    out = subprocess.check_output(
        ["lsblk", "-J", "-o", "PATH,LABEL,MOUNTPOINT,FSTYPE"], stderr=subprocess.DEVNULL
    )
    tree = json.loads(out)["blockdevices"]

    def walk(node):
        label = (node.get("label") or "").strip().lower()
        if label in mb.VENTOY_LABELS and node.get("mountpoint") is None:
            # Prefer unmounted so we control the mount; but accept mounted too.
            return node
        for child in node.get("children", []):
            r = walk(child)
            if r:
                return r
        return None

    for dev in tree:
        r = walk(dev)
        if r:
            return r
    return None


def main():
    node = find_data_node()
    if not node:
        print("ERROR: prepared Rusys/Ventoy USB not found (need label Ventoy/Rusys).")
        sys.exit(2)
    dev = node["path"]
    mp = node.get("mountpoint")
    mounted_here = False
    if not mp:
        mp = os.path.join(RUSYS_ROOT, os.path.basename(dev))
        os.makedirs(mp, exist_ok=True)
        subprocess.run(["mount", "-o", "uid=0,gid=0", dev, mp], check=True)
        mounted_here = True
    try:
        isos = mb.list_isos(mp)
        print(f"Found ISOs: {isos}")
        mb.install_ventoy_theme(mp, THEME)
        print(f"Theme '{THEME}' applied to {dev} (ventoy/ventoy.json + themes/{THEME}).")
    finally:
        if mounted_here:
            subprocess.run(["umount", mp], check=False)


if __name__ == "__main__":
    main()
