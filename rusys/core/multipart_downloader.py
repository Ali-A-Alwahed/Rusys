# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""IDM-like download engine for Rusys OS Downloads.

Single-file download with pause/resume (Range headers), retries,
a download queue with a parallel limit, accurate progress callbacks,
and optional background URL resolving (MSDL fresh links, page scraping).

All network runs in worker threads — the GUI thread never blocks.
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import requests

from .iso_resolver import (BROWSER_UA, WGET_UA, BrowserNeededError,
                            is_direct_iso_url, is_filehost_url,
                            make_session, resolve_iso_url)

ProgressCb = Callable[[int, int], None]  # (bytes_done, total_bytes)
ResolveFn = Callable[[], Optional[str]]

DEFAULT_PARTS = 30
DEFAULT_RETRIES = 3
CHUNK_SIZE = 8192


def _get_total_size(url: str, session: Optional[requests.Session] = None, timeout: int = 15) -> int:
    """Return total file size via HEAD (or GET Range 0-0). 0 if unknown."""
    sess = session or requests.Session()
    close = session is None
    try:
        try:
            hdrs = {}
            if "dl.os.click" in url:
                hdrs["Referer"] = "https://os.click/en"
            r = sess.head(url, headers=hdrs, allow_redirects=True, timeout=timeout)
            if r.ok:
                cl = r.headers.get("content-length")
                if cl and cl.isdigit():
                    return int(cl)
        except Exception:
            pass
        try:
            with sess.get(url, headers={"Range": "bytes=0-0"}, stream=True,
                          allow_redirects=True, timeout=timeout) as r:
                if r.status_code in (200, 206):
                    cr = r.headers.get("content-range", "")
                    if "/" in cr:
                        try:
                            return int(cr.split("/")[-1])
                        except ValueError:
                            pass
                    cl = r.headers.get("content-length")
                    if cl and cl.isdigit():
                        return int(cl)
        except Exception:
            pass
        return 0
    finally:
        if close:
            sess.close()


def _supports_range(url: str, session: Optional[requests.Session] = None, timeout: int = 10) -> bool:
    """Check if server supports Range requests."""
    sess = session or requests.Session()
    close = session is None
    try:
        try:
            r = sess.head(url, allow_redirects=True, timeout=timeout)
            if r.ok and r.headers.get("accept-ranges", "").lower() == "bytes":
                return True
        except Exception:
            pass
        try:
            with sess.get(url, headers={"Range": "bytes=0-0"}, stream=True,
                          timeout=timeout) as r:
                return r.status_code == 206
        except Exception:
            return False
    except Exception:
        return False
    finally:
        if close:
            sess.close()


def _maybe_resolve(url: str, session: Optional[requests.Session]) -> tuple:
    """Resolve browser pages to direct ISO with cookie generation."""
    if is_direct_iso_url(url):
        return url, session
    ua = WGET_UA if "sourceforge.net" in url.lower() else BROWSER_UA
    sess = session or make_session(ua)
    try:
        resolved = resolve_iso_url(url, session=sess, timeout=15)
        if resolved and is_direct_iso_url(resolved):
            return resolved, sess
    except Exception:
        pass
    return url, sess


def download(
    url: str,
    dest: str,
    num_parts: int = DEFAULT_PARTS,
    session: Optional[requests.Session] = None,
    progress_cb: Optional[ProgressCb] = None,
    cancel_event: Optional[threading.Event] = None,
    pause_event: Optional[threading.Event] = None,
    retries: int = DEFAULT_RETRIES,
    timeout: int = 30,
) -> str:
    """Download url to dest — single file with pause/resume and retries.

    If ``url`` is a browser page it is first resolved via the cookie-aware
    ISO resolver. Returns final dest path on success.
    """
    if cancel_event and cancel_event.is_set():
        raise RuntimeError("Download cancelled")

    url, session = _maybe_resolve(url, session)
    if is_filehost_url(url):
        # File hosts need an interactive Turnstile check — never save
        # their HTML as an ISO. Signal the UI to open the browser instead.
        raise BrowserNeededError(url, "file host needs browser verification")
    return _download_single(url, dest, session=session, progress_cb=progress_cb,
                            cancel_event=cancel_event, pause_event=pause_event,
                            retries=retries, timeout=timeout)


def _download_single(
    url: str,
    dest: str,
    session: Optional[requests.Session] = None,
    progress_cb: Optional[ProgressCb] = None,
    cancel_event: Optional[threading.Event] = None,
    pause_event: Optional[threading.Event] = None,
    retries: int = DEFAULT_RETRIES,
    timeout: int = 30,
) -> str:
    """Single-stream download with resume + pause + progress + retries."""
    existing = 0
    if os.path.isfile(dest):
        existing = os.path.getsize(dest)

    headers: Dict[str, str] = {}
    if "dl.os.click" in url:
        headers["Referer"] = "https://os.click/en"
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    ua = WGET_UA if "sourceforge.net" in url.lower() else BROWSER_UA
    sess = session or make_session(ua)
    close = session is None
    try:
        for attempt in range(retries + 1):
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("Download cancelled")
            try:
                with sess.get(url, headers=headers, stream=True, timeout=timeout) as r:
                    if r.status_code not in (200, 206):
                        if r.status_code == 416 and existing > 0:
                            return dest
                        if r.status_code in (401, 403):
                            raise BrowserNeededError(url, f"HTTP {r.status_code} (verification wall)")
                        raise RuntimeError(f"HTTP {r.status_code}")
                    ct = (r.headers.get("content-type") or "").lower()
                    cl = r.headers.get("content-length")
                    if "text/html" in ct and (not cl or (cl.isdigit() and int(cl) < 2 * 1024 * 1024)):
                        # Server returned a web page, not a file — never save as ISO
                        raise BrowserNeededError(url, "server returned a web page, not a file")
                    total = 0
                    cr = r.headers.get("content-range", "")
                    if "/" in cr:
                        try:
                            total = int(cr.split("/")[-1])
                        except ValueError:
                            pass
                    if total == 0:
                        cl = r.headers.get("content-length")
                        if cl and cl.isdigit():
                            total = int(cl) + existing if r.status_code == 206 else int(cl)

                    mode = "ab" if existing > 0 and r.status_code == 206 else "wb"
                    if r.status_code == 200 and existing > 0:
                        existing = 0
                        mode = "wb"

                    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
                    downloaded = existing
                    with open(dest, mode) as f:
                        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                            if cancel_event and cancel_event.is_set():
                                raise RuntimeError("Download cancelled")
                            if pause_event and pause_event.is_set():
                                raise RuntimeError("Download paused")
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_cb and total > 0:
                                    progress_cb(downloaded, total)
                                elif progress_cb:
                                    progress_cb(downloaded, 0)
                    if progress_cb and total > 0:
                        progress_cb(total, total)
                    return dest
            except RuntimeError:
                raise
            except Exception:
                if attempt >= retries:
                    raise
                time.sleep(0.5 * (attempt + 1))
        raise RuntimeError("Download failed after retries")
    finally:
        if close:
            sess.close()


# ---------------------------------------------------------------------------
# Queue + parallel limit (IDM-like)
# ---------------------------------------------------------------------------

@dataclass
class DownloadTask:
    url: str
    dest: str
    status: str = "queued"  # queued, downloading, paused, completed, failed, cancelled, needs_browser
    progress: float = 0.0
    bytes_done: int = 0
    total_bytes: int = 0
    error: str = ""
    resolve_fn: Optional[ResolveFn] = None  # background URL resolver (MSDL etc.)
    browser_url: str = ""  # page to open when status == needs_browser
    cancel_event: threading.Event = field(default_factory=threading.Event)
    pause_event: threading.Event = field(default_factory=threading.Event)
    thread: Optional[threading.Thread] = None


class DownloadQueue:
    """IDM-like queue with parallel limit and accurate progress."""

    def __init__(self, parallel_limit: int = 3):
        self.parallel_limit = parallel_limit
        self.tasks: List[DownloadTask] = []
        self._lock = threading.Lock()
        self._active_count = 0
        self._pool = ThreadPoolExecutor(max_workers=parallel_limit + 2)

    def add(self, url: str, dest: str,
            resolve_fn: Optional[ResolveFn] = None,
            browser_url: str = "") -> DownloadTask:
        task = DownloadTask(url=url, dest=dest, resolve_fn=resolve_fn,
                            browser_url=browser_url or url)
        with self._lock:
            self.tasks.append(task)
        return task

    def _run_task(self, task: DownloadTask):
        task.status = "downloading"
        task.cancel_event.clear()
        task.pause_event.clear()

        def _cb(done: int, total: int):
            # Smooth progress: only move forward, never backward
            if done < task.bytes_done:
                return
            task.bytes_done = done
            task.total_bytes = total
            task.progress = (done / total) if total > 0 else 0.0

        try:
            # Background resolve first (MSDL fresh links, page scraping).
            # This is what used to freeze/crash the GUI — now in worker thread.
            if task.resolve_fn is not None:
                try:
                    real_url = task.resolve_fn()
                except Exception as exc:
                    raise RuntimeError(f"Resolve failed: {exc}")
                if not real_url:
                    task.status = "needs_browser"
                    task.error = ("Automatic link resolve failed "
                                  "(page needs verification).")
                    return
                task.url = real_url
                task.resolve_fn = None  # resolve once
            try:
                download(task.url, task.dest, session=None,
                         progress_cb=_cb, cancel_event=task.cancel_event,
                         pause_event=task.pause_event)
            except BrowserNeededError as exc:
                if exc.url:
                    task.browser_url = exc.url
                task.status = "needs_browser"
                task.error = str(exc) or "browser verification needed"
                return
            if task.cancel_event.is_set():
                task.status = "cancelled"
            elif task.pause_event.is_set():
                task.status = "paused"
            else:
                task.status = "completed"
                task.progress = 1.0
        except RuntimeError as exc:
            msg = str(exc).lower()
            if "cancelled" in msg:
                task.status = "cancelled"
            elif "paused" in msg or task.pause_event.is_set():
                task.status = "paused"
            else:
                task.status = "failed"
                task.error = str(exc)
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
        finally:
            with self._lock:
                self._active_count -= 1
            self._pump()

    def _pump(self):
        """Start queued tasks up to parallel_limit."""
        with self._lock:
            if self._active_count >= self.parallel_limit:
                return
            for task in self.tasks:
                if task.status == "queued":
                    self._active_count += 1
                    task.thread = threading.Thread(target=self._run_task,
                                                   args=(task,), daemon=True)
                    task.thread.start()
                    if self._active_count >= self.parallel_limit:
                        break

    def start_all(self):
        self._pump()

    def start(self, task: DownloadTask):
        if task.status in ("queued", "paused", "failed", "cancelled"):
            task.status = "queued"
            task.cancel_event.clear()
            task.pause_event.clear()
            self._pump()

    def pause(self, task: DownloadTask):
        if task.status == "downloading":
            task.pause_event.set()
            task.status = "paused"

    def resume(self, task: DownloadTask):
        if task.status == "paused":
            task.pause_event.clear()
            task.status = "queued"
            self._pump()

    def cancel(self, task: DownloadTask):
        task.cancel_event.set()
        task.pause_event.clear()
        task.status = "cancelled"

    def remove(self, task: DownloadTask):
        self.cancel(task)
        with self._lock:
            if task in self.tasks:
                self.tasks.remove(task)
                try:
                    if os.path.isfile(task.dest):
                        os.remove(task.dest)
                except OSError:
                    pass
                for i in range(DEFAULT_PARTS):
                    pp = f"{task.dest}.part{i}"
                    try:
                        if os.path.isfile(pp):
                            os.remove(pp)
                    except OSError:
                        pass

    def clear_completed(self):
        with self._lock:
            self.tasks = [t for t in self.tasks if t.status != "completed"]

    def shutdown(self):
        for t in self.tasks:
            t.cancel_event.set()
        self._pool.shutdown(wait=False)
