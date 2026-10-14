# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Resumable download engine for Rusys.

Handles os.click and other CDN URLs that require specific headers
(Referer, User-Agent) and cookie-based sessions for proper downloads.
"""
from __future__ import annotations

import os
import re
import threading
import time
from typing import Callable, Optional
from urllib.parse import urlparse

import requests

from . import checksum
from .logger import log

ProgressCb = Callable[[int, int, float], None]  # (downloaded, total, speed_bps)

# Headers required by os.click and similar CDN services
_WGET_UA = "Wget/1.21.1"
_OSCLICK_REFERER = "https://os.click/en"
_DEFAULT_UA = "Rusys/26.10.14 (https://github.com/Ali-A-Alwahed/Rusys)"


class DownloadError(RuntimeError):
    pass


class Downloader:
    """Streaming, resumable downloader with progress, cancel, and cookie support."""

    def __init__(self, url: str, dest: str, expected_sha256: str = ""):
        self.url = url
        self.dest = dest
        self.expected_sha256 = expected_sha256
        self._cancel = threading.Event()
        self._lock = threading.Lock()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def _build_headers(self, resume_at: int = 0) -> dict:
        """Build request headers with proper User-Agent and Referer for CDN compatibility."""
        headers = {}
        parsed = urlparse(self.url)
        host = parsed.hostname or ""

        # os.click / dl.os.click require Wget UA + Referer for 206 partial content
        if "os.click" in host:
            headers["User-Agent"] = _WGET_UA
            headers["Referer"] = _OSCLICK_REFERER
        elif "sourceforge" in host or "netix" in host:
            headers["User-Agent"] = _WGET_UA
            headers["Referer"] = "https://sourceforge.net/"
        else:
            headers["User-Agent"] = _DEFAULT_UA

        if resume_at > 0:
            headers["Range"] = f"bytes={resume_at}-"

        return headers

    def _create_session(self) -> requests.Session:
        """Create a requests Session with cookie jar for CDN compatibility."""
        session = requests.Session()
        parsed = urlparse(self.url)
        host = parsed.hostname or ""

        # os.click sets cookies on first request; session preserves them for redirects
        if "os.click" in host:
            session.headers.update({
                "User-Agent": _WGET_UA,
                "Referer": _OSCLICK_REFERER,
            })
        elif "sourceforge" in host or "netix" in host:
            session.headers.update({
                "User-Agent": _WGET_UA,
                "Referer": "https://sourceforge.net/",
            })
        else:
            session.headers.update({"User-Agent": _DEFAULT_UA})

        return session

    def _open_output(self, resume_at: int):
        mode = "ab" if resume_at > 0 else "wb"
        return open(self.dest, mode)

    def run(
        self,
        progress_cb: Optional[ProgressCb] = None,
        chunk_size: int = 1 << 16,
        pause_event: Optional[threading.Event] = None,
    ) -> str:
        resume_at = 0
        if os.path.exists(self.dest):
            resume_at = os.path.getsize(self.dest)
            if resume_at > 0:
                log.info("Resuming download at %d bytes", resume_at)

        session = self._create_session()
        try:
            headers = self._build_headers(resume_at)

            # First request — may set cookies on the session
            resp = session.get(
                self.url, headers=headers, stream=True, timeout=30,
                allow_redirects=True,
            )
            resp.raise_for_status()

            total = int(resp.headers.get("Content-Length", 0)) or None
            # Handle 206 Partial Content
            if resp.status_code == 206 and total is not None and resume_at > 0:
                total += resume_at
            elif total is None:
                total = resume_at or 0

            mode = "ab" if resume_at > 0 else "wb"
            written = resume_at
            start = time.monotonic()

            with open(self.dest, mode) as fh:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if self._cancel.is_set():
                        raise DownloadError("Download cancelled by user.")
                    if pause_event is not None and pause_event.is_set():
                        raise DownloadError("Download paused by user.")
                    if not chunk:
                        continue
                    fh.write(chunk)
                    written += len(chunk)
                    elapsed = time.monotonic() - start
                    speed = (written - resume_at) / elapsed if elapsed > 0 else 0
                    if progress_cb:
                        progress_cb(written, total or written, speed)

            resp.close()
        except requests.RequestException as exc:
            raise DownloadError(str(exc)) from exc
        finally:
            session.close()

        if self.expected_sha256:
            log.info("Verifying SHA-256 of downloaded file...")
            if not checksum.verify_file(self.dest, self.expected_sha256, "sha256"):
                raise DownloadError("Checksum verification failed for download.")
        return self.dest

    @staticmethod
    def is_direct_iso(url: str) -> bool:
        try:
            from .iso_resolver import is_direct_iso_url
            if is_direct_iso_url(url):
                return True
        except Exception:
            pass
        return url.lower().split("?")[0].endswith(
            (".iso", ".img", ".raw", ".zip", ".7z"))
