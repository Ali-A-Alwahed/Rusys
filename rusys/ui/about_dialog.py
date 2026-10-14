# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""About dialog for Rusys."""
from __future__ import annotations

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
)

from .. import __version__, __app_name__, __copyright__, __author__, __license__


class AboutDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle(f"About {__app_name__}")
        self.setMinimumWidth(520)
        # Fully dark as rpm/deb, 10px Windows / 9pt Linux, no white title bar on Windows
        try:
            import sys as _sys
            if _sys.platform == "win32":
                import ctypes
                ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 20, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
        except:
            pass
        import sys as _sys2
        _is_win2 = _sys2.platform == "win32"
        _font2 = "9px" if _is_win2 else "10pt"
        self.setStyleSheet(f"""
            QDialog {{ background-color: #1e1e2e; color: #cdd6f4; font-size: {_font2}; font-family: "Segoe UI", "Noto Sans", sans-serif; }}
            QLabel {{ color: #cdd6f4; background: transparent; }}
            QTextBrowser {{ background-color: #181825; color: #cdd6f4; border: 1px solid #45475a; font-size: {_font2}; }}
            QDialogButtonBox QPushButton {{ background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 4px 12px; }}
            QDialogButtonBox QPushButton:hover {{ background-color: #45475a; }}
        """)
        # Remember the last size/position, like the main window (issue: avoid
        # re-resizing the About dialog every time it is opened).
        if settings is not None and getattr(settings, "about_geometry", ""):
            self.restoreGeometry(QByteArray.fromHex(settings.about_geometry.encode()))
        layout = QVBoxLayout(self)

        title = QLabel(f"<h2>{__app_name__}</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sub = QLabel(
            f"Version {__version__}<br>{__copyright__}<br>"
            f"Developer: {__author__}<br>License: {__license__}"
        )
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        info = QTextBrowser()
        info.setOpenExternalLinks(True)
        info.setHtml(
            "<p><b>Rusys</b> is a 3rd-party extension of the "
            "<b>Pro Tool</b> project. It is a from-scratch Python/PySide6 "
            "rebuild of the Rufus USB boot-media utility, rebranded and "
            "integrated for downloading official operating-system images and "
            "writing them to removable media.</p>"
            "<p>Features:</p>"
            "<ul>"
            "<li>Full OS download catalogue (Windows, Linux, Unix/BSD, Maintenance and Recovery)</li>"
            "<li>Resumable downloads with checksum verification</li>"
            "<li>Safe device flashing with post-write verification</li>"
            "<li>Settings mapped to community-requested fixes</li>"
            "<li>Command-line interface for automation</li>"
            "</ul>"
            "<p>This project is free software licensed under the "
            "<b>GNU General Public License v3.0 or later</b> "
            "(Copyright &copy; 2026 Ali A Alwahed). "
            "Every source file carries the Pro Tool header. Rusys bundles "
            "GPL-3.0 third-party components (Rufus, Ventoy, grub2-themes); "
            "see THIRD_PARTY_NOTICES.md.</p>"
            "<p><b>Libraries &amp; Credits</b></p>"
            "<ul>"
            "<li><b>Python</b> &mdash; general-purpose language "
            "(Python Software Foundation, &copy; PSF). "
            "<a href=\"https://www.python.org/\">python.org</a></li>"
            "<li><b>PySide6 (Qt for Python)</b> &mdash; GUI framework by "
            "The Qt Company / Riverbank Computing. "
            "<a href=\"https://doc.qt.io/qtforpython/\">qt.io/qtforpython</a></li>"
            "<li><b>requests</b> &mdash; HTTP library by Kenneth Reitz &amp; "
            "contributors, Apache-2.0. "
            "<a href=\"https://requests.readthedocs.io/\">requests.readthedocs.io</a></li>"
            "<li><b>Ventoy</b> &mdash; multiboot boot engine by longpanda "
            "(admin@ventoy.net), GPLv3. Bundled under <code>resources/ventoy</code>. "
            "<a href=\"https://www.ventoy.net/\">ventoy.net</a></li>"
            "<li><b>grub2-themes</b> &mdash; GRUB2 menu themes (whitesur / tela / "
            "vimix / stylish) by vinceliuice, GPLv3. Bundled under "
            "<code>resources/themes</code>. "
            "<a href=\"https://github.com/vinceliuice/grub2-themes\">github.com/"
            "vinceliuice/grub2-themes</a></li>"
            "</ul>"
            "<p><b>Special thanks</b></p>"
            "<ul>"
            "<li><b>Hyder 61112</b> &mdash; for debugging and invaluable help with "
            "the Rusys core. Thank you for the countless hours spent hunting down "
            "boot-chain and theming issues that made this multiboot release "
            "possible.</li>"
            "</ul>"
            "<p>Rusys is a from-scratch reimplementation inspired by the concepts "
            "of <b>Rufus</b> by Pete Batard (<a href=\"https://github.com/pbatard/rufus\">"
            "pbatard/rufus</a>, GPLv3) and <b>Ventoy</b> by longpanda "
            "(<a href=\"https://www.ventoy.net/\">ventoy.net</a>, GPLv3). "
            "No original Rufus or Ventoy source code is included.</p>"
        )
        layout.addWidget(info)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def closeEvent(self, event):
        if self._settings is not None:
            self._settings.about_geometry = str(
                self.saveGeometry().toHex(), encoding="ascii"
            )
        super().closeEvent(event)
