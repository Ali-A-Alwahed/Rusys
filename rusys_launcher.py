# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Standalone launch entry for frozen builds (PyInstaller)."""
from __future__ import annotations

import os
import sys
import traceback


def _show_startup_error(text: str) -> None:
    # Try Qt message box, then Win32 MessageBox, then stderr/file.
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Rusys - startup error", text)
        return
    except Exception:
        pass
    try:
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, text, "Rusys - startup error", 0x10)
            return
    except Exception:
        pass
    try:
        print(text, file=sys.stderr)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from rusys.cli import main

        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - must never die silently on Windows
        log_path = os.path.join(
            os.path.dirname(os.path.abspath(sys.argv[0])),
            "Rusys_error.log",
        )
        detail = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        try:
            with open(log_path, "w", encoding="utf-8", errors="replace") as fh:
                fh.write(detail)
        except Exception:
            log_path = "<could not write log file>"
        _show_startup_error(
            "Rusys failed to start.\n\n"
            f"{type(exc).__name__}: {exc}\n\n"
            f"Details written to:\n{log_path}\n\n"
            "Please send this log when reporting the issue.\n\n"
            f"{detail[-2000:]}"
        )
        sys.exit(1)
