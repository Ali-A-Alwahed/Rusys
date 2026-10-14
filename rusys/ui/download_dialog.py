# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Download dialog for Rusys."""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ..core.downloader import Downloader
from .worker import Worker


class DownloadDialog(QDialog):
    downloaded = Signal(str)  # local file path

    def __init__(self, url: str, dest: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Rusys - Downloading")
        self.setMinimumWidth(460)
        self.url = url
        self.dest = dest
        self.worker: Optional[Worker] = None

        layout = QVBoxLayout(self)
        self.label = QLabel(f"Downloading:\n{url}\n\nTo: {dest}")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        layout.addWidget(self.bar)

        self.speed = QLabel("")
        layout.addWidget(self.speed)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.rejected.connect(self._cancel)
        layout.addWidget(self.buttons)

        self.downloader = Downloader(url, dest)

    def start(self):
        self.worker = Worker(self.downloader.run, progress_cb=lambda *a: None)
        self.worker.progress.connect(self._on_progress_signal)
        self.worker.finished.connect(self._on_finished)
        self.worker.errored.connect(self._on_error)
        self.worker.log_line.connect(lambda m, lvl: None)
        self.worker.start()

    def _on_progress_signal(self, done, total, speed):
        """Handle download progress from the Worker signal (runs on GUI thread)."""
        if total and total > 0:
            self.bar.setValue(int(done * 100 / total))
        self.speed.setText(f"{_fmt(done)} / {_fmt(total)}  @  {_fmt(speed)}/s")

    def _on_progress(self, done, total, speed):
        """Legacy direct callback — kept for API compatibility but no longer used."""
        if total and total > 0:
            self.bar.setValue(int(done * 100 / total))
        self.speed.setText(f"{_fmt(done)} / {_fmt(total)}  @  {_fmt(speed)}/s")

    def _on_finished(self, _result):
        self.downloaded.emit(self.dest)
        self.accept()

    def _on_error(self, message):
        self.label.setText(f"Download failed:\n{message}")
        self.buttons.setStandardButtons(QDialogButtonBox.StandardButton.Close)

    def _cancel(self):
        if self.downloader is not None:
            self.downloader.cancel()
        self.reject()

    def closeEvent(self, event):
        if self.downloader is not None:
            self.downloader.cancel()
        super().closeEvent(event)


def _fmt(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "?"
    units = ["B", "KB", "MB", "GB", "TB"]
    for u in units:
        if n < 1024 or u == units[-1]:
            return f"{n:.1f} {u}" if u != "B" else f"{int(n)} {u}"
        n /= 1024.0
