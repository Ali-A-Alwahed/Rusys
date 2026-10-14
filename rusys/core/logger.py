# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Logging helpers for Rusys (thread-safe, UI-friendly)."""
from __future__ import annotations

import logging
import sys
from typing import Optional

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class QtLogHandler(logging.Handler):
    """A logging handler that forwards records to a callable (e.g. a Qt signal).

    Used so the GUI log widget and the background workers stay in sync without
    importing PySide6 inside the core layer.
    """

    def __init__(self, emit_fn):
        super().__init__()
        self._emit_fn = emit_fn

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._emit_fn(msg, record.levelno)
        except Exception:  # pragma: no cover - never let logging crash the app
            pass


def build_logger(name: str = "rusys", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger


def attach_ui_handler(logger: logging.Logger, emit_fn) -> QtLogHandler:
    handler = QtLogHandler(emit_fn)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    return handler


log = build_logger()
