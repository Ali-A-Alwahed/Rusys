# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Graphical entry point for Rusys."""
from __future__ import annotations

import os
import sys

from . import __app_name__
from .core.settings import load_settings
from .data.os_catalog import load_user_overrides
from .ui.main_window import MainWindow


def run_gui(offscreen: bool = False) -> int:
    from PySide6.QtWidgets import QApplication

    if offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    # Frozen (PyInstaller onefile) resources live under sys._MEIPASS
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    icon_path = os.path.join(base_dir, "resources", "icons", "rusys.png")
    if os.path.isfile(icon_path):
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))

    settings = load_settings()
    overrides = os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "rusys", "catalog_overrides.json",
    )
    load_user_overrides(overrides)

    window = MainWindow(settings)
    window.show()
    return app.exec()
