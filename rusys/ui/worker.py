# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Background worker thread for Rusys (download/flash off the UI thread)."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    progress = Signal(float, float, object)   # done, total, extra (float avoids >2GB overflow)
    log_line = Signal(str, int)
    finished = Signal(object)
    errored = Signal(str)

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:  # noqa: D401
        try:
            # If the caller passed a progress_cb keyword argument, replace it
            # with a wrapper that emits the 'progress' signal so that Qt
            # widgets are only updated on the GUI thread.  Directly calling
            # QWidget methods from a worker thread causes segfaults.
            if "progress_cb" in self._kwargs:
                def _safe_progress_cb(*pargs):
                    # Emit the signal so the GUI thread handles the update.
                    # The signal carries (done, total, extra) for 3-arg
                    # callbacks or (done, total, None) for 2-arg callbacks.
                    # Convert to float to avoid OverflowError for files >2GB
                    # (C++ int32 overflow: values >2^31 crash Shiboken).
                    if len(pargs) == 3:
                        self.progress.emit(float(pargs[0]), float(pargs[1]), pargs[2])
                    elif len(pargs) == 2:
                        self.progress.emit(float(pargs[0]), float(pargs[1]), None)
                    else:
                        self.progress.emit(float(pargs[0]) if pargs else 0.0, 0.0, None)

                self._kwargs["progress_cb"] = _safe_progress_cb

            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as exc:  # surface as a user-friendly error
            self.errored.emit(str(exc))
