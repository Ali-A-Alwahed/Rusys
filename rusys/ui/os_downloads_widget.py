# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""OS Downloads tab — IDM-like download manager for Rusys.

* Direct ISO downloads with resume, pause/cancel, parallel queue.
* Windows language (+arch) dropdown; a fresh os.click download link is
  resolved in the background worker thread (never in the GUI thread), so
  signed URLs never expire and the UI never freezes or crashes.
* Each OS lands in its own subfolder under ~/Downloads/Rusys/.
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.multipart_downloader import DownloadQueue, DownloadTask
from ..core.settings import Settings, save_settings
from ..data.os_catalog import CatalogNode

LANG_NAMES = {
    "ar-sa": "Arabic", "ar": "Arabic",
    "bg-bg": "Bulgarian", "cs-cz": "Czech", "da-dk": "Danish",
    "de-de": "German", "el-gr": "Greek", "en-gb": "English (UK)",
    "en-us": "English", "en": "English",
    "es-es": "Spanish", "es-mx": "Spanish (Mexico)", "et-ee": "Estonian",
    "fi-fi": "Finnish", "fr-ca": "French (Canada)", "fr-fr": "French",
    "he-il": "Hebrew", "hr-hr": "Croatian", "hu-hu": "Hungarian",
    "it-it": "Italian", "ja-jp": "Japanese", "ja": "Japanese",
    "ko-kr": "Korean", "lt-lt": "Lithuanian", "lv-lv": "Latvian",
    "nb-no": "Norwegian Bokmal", "nl-nl": "Dutch", "pl-pl": "Polish",
    "pt-br": "Portuguese (Brazil)", "pt-pt": "Portuguese (Portugal)",
    "ro-ro": "Romanian", "ru-ru": "Russian", "ru": "Russian",
    "sk-sk": "Slovak", "sl-si": "Slovenian",
    "sr-latn-rs": "Serbian (Latin)", "sv-se": "Swedish", "th-th": "Thai",
    "tr-tr": "Turkish", "uk-ua": "Ukrainian",
    "zh-cn": "Chinese (Simplified)", "zh-hans": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)", "cn": "Chinese (Simplified)",
    "English": "English", "Arabic": "Arabic", "Bulgarian": "Bulgarian",
    "Czech": "Czech", "Danish": "Danish", "German": "German",
    "Greek": "Greek", "Spanish": "Spanish", "Estonian": "Estonian",
    "Finnish": "Finnish", "French": "French", "Hebrew": "Hebrew",
    "Croatian": "Croatian", "Hungarian": "Hungarian", "Italian": "Italian",
    "Japanese": "Japanese", "Korean": "Korean", "Lithuanian": "Lithuanian",
    "Latvian": "Latvian", "Norwegian": "Norwegian", "Dutch": "Dutch",
    "Polish": "Polish", "Romanian": "Romanian", "Russian": "Russian",
    "Slovak": "Slovak", "Slovenian": "Slovenian", "Serbian": "Serbian",
    "Serbia": "Serbian", "Swedish": "Swedish", "Thai": "Thai",
    "Turkish": "Turkish", "Ukrainian": "Ukrainian", "Ukranian": "Ukrainian",
    "Chinese - Simplified": "Chinese (Simplified)",
    "Chinese - Traditional": "Chinese (Traditional)",
    "Chinese - Hong Kong SAR": "Chinese (Hong Kong)",
    "English - United Kingdom": "English (UK)",
    "Portuguese - Brazil": "Portuguese (Brazil)",
    "Portuguese-Brazil": "Portuguese (Brazil)",
    "Portuguese - Portugal": "Portuguese (Portugal)",
    "Portuguese-Portugal": "Portuguese (Portugal)",
}


def _download_dir(settings: Settings) -> str:
    if settings.download_dir and os.path.isdir(settings.download_dir):
        return settings.download_dir
    dl = os.path.join(os.path.expanduser("~/Downloads"), "Rusys")
    os.makedirs(dl, exist_ok=True)
    return dl


class _DownloadRow(QFrame):
    """One row in the download list: filename + progress + controls."""

    def __init__(self, task: DownloadTask, queue: DownloadQueue, parent=None):
        super().__init__(parent)
        self.task = task
        self.queue = queue
        self.setFrameShape(QFrame.StyledPanel)
        self._build()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(200)

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(6)

        name = os.path.basename(self.task.dest) or (self.task.url[:40] if self.task.url else "download")
        self.name_lbl = QLabel(name)
        self.name_lbl.setMinimumWidth(180)
        self.name_lbl.setWordWrap(True)
        lay.addWidget(self.name_lbl, 1)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setMinimumWidth(140)
        lay.addWidget(self.bar, 1)

        self.pct_lbl = QLabel("0%")
        self.pct_lbl.setMinimumWidth(45)
        lay.addWidget(self.pct_lbl)

        self.size_lbl = QLabel("—")
        self.size_lbl.setMinimumWidth(90)
        lay.addWidget(self.size_lbl)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setMinimumWidth(60)
        self.pause_btn.clicked.connect(self._on_pause)
        lay.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumWidth(60)
        self.cancel_btn.clicked.connect(self._on_cancel)
        lay.addWidget(self.cancel_btn)

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setMaximumWidth(30)
        self.remove_btn.clicked.connect(self._on_remove)
        lay.addWidget(self.remove_btn)

    def _refresh(self):
        t = self.task
        if t.status == "needs_browser":
            self.bar.setValue(0)
            self.pct_lbl.setText("—")
            self.size_lbl.setText("browser")
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            return
        pct = int(t.progress * 100) if t.total_bytes else 0
        self.bar.setValue(pct)
        self.pct_lbl.setText(f"{pct}%")
        if t.total_bytes:
            done_m = t.bytes_done / (1024 * 1024)
            total_m = t.total_bytes / (1024 * 1024)
            self.size_lbl.setText(f"{done_m:.1f}/{total_m:.1f} MB")
        else:
            self.size_lbl.setText(f"{t.bytes_done // 1024} KB")

        if t.status == "downloading":
            self.pause_btn.setText("Pause")
            self.pause_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.bar.setStyleSheet("")
        elif t.status == "paused":
            self.pause_btn.setText("Resume")
            self.pause_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.bar.setStyleSheet("QProgressBar::chunk { background: #e6a800; }")
        elif t.status == "completed":
            self.bar.setStyleSheet("QProgressBar::chunk { background: #2ecc71; }")
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self._timer.stop()
        elif t.status in ("failed", "cancelled"):
            self.bar.setStyleSheet("QProgressBar::chunk { background: #e74c3c; }")
            self.pause_btn.setText("Retry")
            self.pause_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            if t.status == "failed":
                self.name_lbl.setToolTip(t.error)
        elif t.status == "queued":
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)

    def _on_pause(self):
        if self.task.status == "downloading":
            self.queue.pause(self.task)
        elif self.task.status == "paused":
            self.queue.resume(self.task)
        elif self.task.status in ("failed", "cancelled"):
            self.queue.start(self.task)

    def _on_cancel(self):
        self.queue.cancel(self.task)

    def _on_remove(self):
        # Yes = entry + files + folder, No = entry only, Cancel = abort
        import shutil

        fname = os.path.basename(self.task.dest) or "download"
        folder = os.path.dirname(self.task.dest)
        box = QMessageBox(self)
        box.setWindowTitle("Remove download")
        box.setText(
            f"Remove download entry '{fname}'?\n\n"
            f"• Yes — remove the entry and delete its files and folder:\n"
            f"  {self.task.dest}\n  {folder}\n\n"
            f"• No — remove the entry only, keep files and folder on disk.\n\n"
            f"• Cancel — keep the entry and do nothing."
        )
        box.setIcon(QMessageBox.Question)
        btn_yes = box.addButton("Yes", QMessageBox.YesRole)
        box.addButton("No", QMessageBox.NoRole)
        btn_cancel = box.addButton("Cancel", QMessageBox.RejectRole)
        box.setDefaultButton(btn_cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked == btn_cancel:
            return
        delete_files = (clicked == btn_yes)

        if delete_files:
            self.queue.remove(self.task)
            try:
                if folder and os.path.isdir(folder):
                    if not os.listdir(folder):
                        os.rmdir(folder)
                    else:
                        shutil.rmtree(folder, ignore_errors=True)
            except Exception:
                pass
        else:
            with self.queue._lock:
                if self.task in self.queue.tasks:
                    self.queue.tasks.remove(self.task)
            try:
                self.task.cancel_event.set()
            except Exception:
                pass

        p = self.parent()
        qlist = None
        downloads_widget = None
        cur = p
        while cur:
            if isinstance(cur, QListWidget) and qlist is None:
                qlist = cur
            if cur.__class__.__name__ == "OSDownloadsWidget":
                downloads_widget = cur
                break
            cur = cur.parent()
        if qlist is None:
            cur = self.parent()
            while cur and not isinstance(cur, QListWidget):
                cur = cur.parent()
            qlist = cur
        if qlist:
            for i in range(qlist.count()):
                item = qlist.item(i)
                w = qlist.itemWidget(item)
                if w is self:
                    qlist.takeItem(i)
                    break
        self.deleteLater()
        if downloads_widget and hasattr(downloads_widget, "_update_queue_buttons"):
            QTimer.singleShot(0, downloads_widget._update_queue_buttons)
            QTimer.singleShot(0, downloads_widget._update_download_button_state)
        elif qlist:
            cur = qlist.parent()
            while cur:
                if hasattr(cur, "_update_queue_buttons"):
                    QTimer.singleShot(0, cur._update_queue_buttons)
                    if hasattr(cur, "_update_download_button_state"):
                        QTimer.singleShot(0, cur._update_download_button_state)
                    break
                cur = cur.parent()


class OSDownloadsWidget(QWidget):
    """OS Downloads tab: selected-OS bar + queue controls + download list."""

    downloaded = Signal(str)  # dest path on completion

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.queue = DownloadQueue(parallel_limit=getattr(settings, "parallel_limit", 3) or 3)
        self._current_leaf: Optional[CatalogNode] = None
        self._lang_connected = False
        self._build()
        self._limit_timer = QTimer(self)
        self._limit_timer.timeout.connect(self._update_download_button_state)
        self._limit_timer.start(500)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        hdr = QLabel("<b>OS Downloads</b> — Direct download, resume, pause/cancel, parallel queue")
        hdr.setWordWrap(True)
        lay.addWidget(hdr)

        sel_box = QGroupBox("Selected OS")
        sl = QHBoxLayout(sel_box)
        self.sel_label = QLabel("No OS selected — pick one from the catalogue on the left")
        self.sel_label.setWordWrap(True)
        sl.addWidget(self.sel_label, 1)

        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumWidth(160)
        self.lang_combo.setVisible(False)
        sl.addWidget(self.lang_combo)

        self.arch_combo = QComboBox()
        self.arch_combo.setMinimumWidth(90)
        self.arch_combo.setVisible(False)
        self.arch_combo.setToolTip("Architecture")
        sl.addWidget(self.arch_combo)

        self.single_dl_btn = QPushButton("Download")
        self.single_dl_btn.setEnabled(False)
        self.single_dl_btn.clicked.connect(self._on_single_download)
        sl.addWidget(self.single_dl_btn)
        lay.addWidget(sel_box)

        ctrl_box = QGroupBox("Queue controls")
        cl = QHBoxLayout(ctrl_box)

        self.pause_all_btn = QPushButton("Pause All")
        self.pause_all_btn.clicked.connect(self._pause_all)
        self.pause_all_btn.setEnabled(False)
        cl.addWidget(self.pause_all_btn)

        self.resume_all_btn = QPushButton("Resume All")
        self.resume_all_btn.clicked.connect(self._resume_all)
        self.resume_all_btn.setEnabled(False)
        cl.addWidget(self.resume_all_btn)

        self.cancel_all_btn = QPushButton("Cancel All")
        self.cancel_all_btn.clicked.connect(self._cancel_all)
        self.cancel_all_btn.setEnabled(False)
        cl.addWidget(self.cancel_all_btn)

        self.remove_all_btn = QPushButton("Remove All")
        self.remove_all_btn.clicked.connect(self._remove_all)
        self.remove_all_btn.setEnabled(False)
        cl.addWidget(self.remove_all_btn)

        cl.addWidget(QLabel("Parallel:"))
        self.parallel_spin = QSpinBox()
        self.parallel_spin.setRange(1, 5)
        self.parallel_spin.setValue(self.queue.parallel_limit)
        self.parallel_spin.valueChanged.connect(self._on_parallel_changed)
        cl.addWidget(self.parallel_spin)

        cl.addStretch()
        lay.addWidget(ctrl_box)

        self.list = QListWidget()
        self.list.setMinimumHeight(260)
        lay.addWidget(self.list, 1)

        hint = QLabel("Tip: select any OS from the catalogue on the left, then click Download — "
                      "Windows asks for a language first. Track progress in the list.")
        hint.setWordWrap(True)
        hint.setObjectName("MutedText")
        lay.addWidget(hint)

    # ------------------------------------------------------------- selection
    def set_selected_os(self, leaf: Optional[CatalogNode]):
        """Called by MainWindow when user picks an OS. No network here."""
        self._current_leaf = leaf
        if self._lang_connected:
            try:
                self.lang_combo.currentIndexChanged.disconnect(self._on_lang_changed)
            except RuntimeError:
                pass
            self._lang_connected = False

        if not leaf:
            self.sel_label.setText("No OS selected — pick one from the catalogue on the left")
            self.single_dl_btn.setEnabled(False)
            self.single_dl_btn.setToolTip("")
            self.lang_combo.setVisible(False)
            self.arch_combo.setVisible(False)
            return

        desc = leaf.notes or f"{leaf.compatibility} — {leaf.size_gb:g}GB — {leaf.latest_update}"
        self.sel_label.setText(f"<b>{leaf.name}</b><br><span style='color:#a6adc8'>{desc}</span>")
        self.sel_label.setToolTip("Select language (if shown), then Download — single click.")

        if leaf.osc_walk:
            # Windows fresh-link entry: language + arch dropdowns.
            self.single_dl_btn.setEnabled(False)
            self.single_dl_btn.setToolTip("Select a language first")
            self.single_dl_btn.setText("Download")
            self.lang_combo.clear()
            self.lang_combo.addItem("-- Choose language --", None)
            for label in sorted((leaf.languages or {}).keys()):
                self.lang_combo.addItem(label, (leaf.languages or {})[label])
            self.lang_combo.setVisible(True)
            self.lang_combo.setCurrentIndex(0)
            try:
                self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
            except RuntimeError:
                pass
            self._lang_connected = True
            archs = (leaf.osc_walk or {}).get("archs", []) or [leaf.compatibility]
            self.arch_combo.clear()
            for arch in archs:
                self.arch_combo.addItem(arch, arch)
            if leaf.compatibility in archs:
                self.arch_combo.setCurrentIndex(archs.index(leaf.compatibility))
            self.arch_combo.setVisible(len(archs) > 1)
            self._update_download_button_state()
            return

        codes = None
        if leaf.languages:
            codes = sorted(leaf.languages.keys())
        if codes is not None:
            self.single_dl_btn.setEnabled(False)
            self.single_dl_btn.setToolTip("Select a language first")
            self.single_dl_btn.setText("Download")
            self.lang_combo.clear()
            self.lang_combo.addItem("-- Choose language --", None)
            for code in codes:
                self.lang_combo.addItem(LANG_NAMES.get(code, code), code)
            self.lang_combo.setVisible(True)
            self.lang_combo.setCurrentIndex(0)
            self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
            self._lang_connected = True
            self._update_download_button_state()
            return

        self.lang_combo.setVisible(False)
        self.arch_combo.setVisible(False)
        self.single_dl_btn.setText("Download")
        self._update_download_button_state()

    def _on_lang_changed(self, index: int):
        code = self.lang_combo.currentData()
        ok = False
        if code and self._current_leaf:
            if self._current_leaf.osc_walk:
                ok = code in (self._current_leaf.languages or {}).values()
            elif self._current_leaf.languages:
                ok = code in self._current_leaf.languages
        self.single_dl_btn.setEnabled(bool(ok))
        self.single_dl_btn.setToolTip("Single-click direct download" if ok else "Select a language first")
        self._update_download_button_state()

    # ------------------------------------------------------------- download
    def _on_single_download(self):
        # No network in the GUI thread: just queue, the worker resolves.
        if not self._current_leaf:
            QMessageBox.warning(self, "No OS selected",
                                "Please select an OS from the catalogue on the left first.")
            return
        leaf = self._current_leaf

        if leaf.osc_walk or leaf.languages:
            code = self.lang_combo.currentData()
            if leaf.osc_walk:
                valid = bool(code and code in (leaf.languages or {}).values())
            else:
                valid = bool(code and leaf.languages and code in leaf.languages)
            if not valid:
                QMessageBox.warning(self, "No language selected",
                                    "Please select a language from the dropdown first.")
                return
            if leaf.osc_walk:
                arch = self.arch_combo.currentData() or leaf.compatibility
                self._queue_osclick(leaf, code, arch)
            else:
                self.add_download(leaf.languages[code])
            return

        url = leaf.leaf_url()
        if not url:
            QMessageBox.warning(self, "No URL", f"No download URL available for '{leaf.name}'.")
            return
        from ..core.downloader import Downloader
        from ..core.iso_resolver import is_direct_iso_url
        if (leaf.iso_url and Downloader.is_direct_iso(url)) or is_direct_iso_url(url):
            self.add_download(url)
            return
        # Page-only entry: honest browser fallback
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        import webbrowser
        if not QDesktopServices.openUrl(QUrl(url)):
            webbrowser.open(url)
        QMessageBox.information(
            self, "Browser opened",
            f"Opened the official page for '{leaf.name}' in your browser.\n\n"
            "This entry has no direct link — download the ISO there, then use "
            "'Add image...' on the Single boot USB tab.")

    def _queue_osclick(self, leaf: CatalogNode, code: str, arch: str):
        """Queue a Windows ISO. A fresh os.click link is fetched in the worker.

        The signed dl.os.click URL is re-issued at download time (never
        stored), so it cannot expire. All network runs in the queue worker —
        the GUI thread never blocks, so no freeze/crash while resolving.
        """
        from ..core.iso_resolver import OsClickError, OsClickResolver

        spec = leaf.osc_walk or {}

        def _resolve():
            info = OsClickResolver().walk(
                spec.get("os", ""), list(spec.get("middle", [])), code, arch)
            url = info.get("url", "")
            if not url.startswith(("http://", "https://")):
                raise OsClickError("no download URL returned")
            return url

        fname = f"{leaf.name.replace(' ', '_')}_{code}_{arch}.iso"
        fname = "".join(c for c in fname if c not in r'\/:*?"<>|')
        folder = "".join(c for c in leaf.name if c not in r'\/:*?"<>|').strip().replace(" ", "_")
        dest_dir = os.path.join(_download_dir(self.settings), folder or "Windows")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, fname)
        base, ext = os.path.splitext(dest)
        i = 1
        while os.path.exists(dest):
            dest = f"{base} ({i}){ext}"
            i += 1
        self._queue_task(url="", dest=dest, resolve_fn=_resolve,
                         browser_url=leaf.page_url or "",
                         name=f"{leaf.name} [{code} {arch}]")

    def add_download(self, url: str, dest: Optional[str] = None):
        """Queue a direct URL (per-OS subfolder under ~/Downloads/Rusys/)."""
        if not url or not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Invalid URL", f"Not a valid download URL:\n{url}")
            return
        for t in self.queue.tasks:
            if t.url == url and t.status in ("queued", "downloading", "paused"):
                QMessageBox.information(self, "Already queued",
                                        "This URL is already in the download queue.")
                return
        if dest is None:
            fname = os.path.basename(url.split("?")[0]) or "download.iso"
            fname = "".join(c for c in fname if c not in r'\/:*?"<>|')
            base_name = os.path.splitext(fname)[0] or "download"
            folder = "".join(c for c in base_name if c not in r'\/:*?"<>|').strip()
            if not folder or folder.lower() in ("download",):
                leaf_name = self._current_leaf.name if self._current_leaf else "download"
                folder = "".join(c for c in leaf_name if c not in r'\/:*?"<>|').strip().replace(" ", "_") or "download"
            dest_dir = os.path.join(_download_dir(self.settings), folder)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, fname)
            base, ext = os.path.splitext(dest)
            i = 1
            while os.path.exists(dest):
                dest = f"{base} ({i}){ext}"
                i += 1
        self._queue_task(url=url, dest=dest)

    def _queue_task(self, url: str, dest: str, resolve_fn=None, browser_url: str = "",
                    name: str = ""):
        task = self.queue.add(url, dest, resolve_fn=resolve_fn,
                              browser_url=browser_url or url)
        row = _DownloadRow(task, self.queue)
        if name:
            row.name_lbl.setText(os.path.basename(dest))
        item = QListWidgetItem(self.list)
        item.setSizeHint(row.sizeHint())
        self.list.addItem(item)
        self.list.setItemWidget(item, row)

        self._update_queue_buttons()
        self.queue.start(task)

        def _watch():
            timer = QTimer(row)

            def _check():
                if task.status == "completed":
                    timer.stop()
                    self.downloaded.emit(task.dest)
                elif task.status == "needs_browser":
                    timer.stop()
                    self._browser_fallback(task)
                elif task.status in ("failed", "cancelled"):
                    timer.stop()
                self._update_queue_buttons()
            timer.timeout.connect(_check)
            timer.start(500)
        _watch()

    def _browser_fallback(self, task):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        import webbrowser
        url = task.browser_url or task.url
        if url and not QDesktopServices.openUrl(QUrl(url)):
            try:
                webbrowser.open(url)
            except Exception:
                pass
        QMessageBox.information(
            self, "Browser verification needed",
            f"Rusys could not fetch a direct link automatically:\n{task.error}\n\n"
            f"Opened the official page in your browser — complete any check there, "
            f"download the ISO, then use 'Add image...' on the Single boot USB tab.\n\n"
            f"URL: {url}")

    def _start_all(self):
        self.queue.start_all()

    def _pause_all(self):
        for t in list(self.queue.tasks):
            if t.status == "downloading":
                self.queue.pause(t)

    def _resume_all(self):
        for t in list(self.queue.tasks):
            if t.status == "paused":
                self.queue.resume(t)
            elif t.status in ("failed", "cancelled", "queued"):
                self.queue.start(t)

    def _cancel_all(self):
        for t in list(self.queue.tasks):
            if t.status in ("queued", "downloading", "paused"):
                self.queue.cancel(t)

    def _remove_all(self):
        for i in reversed(range(self.list.count())):
            item = self.list.item(i)
            w = self.list.itemWidget(item)
            if w and w.task.status != "downloading":
                self.list.takeItem(i)
                try:
                    if w.task in self.queue.tasks:
                        self.queue.tasks.remove(w.task)
                except Exception:
                    pass
                w.deleteLater()
        self._update_queue_buttons()

    def _clear_completed(self):
        for i in reversed(range(self.list.count())):
            item = self.list.item(i)
            w = self.list.itemWidget(item)
            if w and w.task.status == "completed":
                self.list.takeItem(i)
                w.deleteLater()
        self.queue.clear_completed()
        self._update_queue_buttons()

    def _on_parallel_changed(self, val: int):
        self.queue.parallel_limit = val
        try:
            self.settings.parallel_limit = val
            save_settings(self.settings)
        except Exception:
            pass
        self._update_download_button_state()

    def _update_queue_buttons(self):
        has_tasks = self.list.count() > 0
        self.pause_all_btn.setEnabled(has_tasks)
        self.resume_all_btn.setEnabled(has_tasks)
        self.cancel_all_btn.setEnabled(has_tasks)
        self.remove_all_btn.setEnabled(has_tasks)
        self._update_download_button_state()

    def _update_download_button_state(self):
        active = sum(1 for t in self.queue.tasks if t.status == "downloading")
        at_limit = active >= self.queue.parallel_limit
        if not self._current_leaf:
            return
        if self._current_leaf.osc_walk or self._current_leaf.languages:
            code = self.lang_combo.currentData()
            has_url = False
            if code:
                if self._current_leaf.osc_walk:
                    has_url = code in (self._current_leaf.languages or {}).values()
                elif self._current_leaf.languages:
                    has_url = code in self._current_leaf.languages
            if at_limit and has_url:
                self.single_dl_btn.setEnabled(False)
                self.single_dl_btn.setToolTip(
                    f"Parallel limit reached ({active}/{self.queue.parallel_limit}) — "
                    "increase Parallel or wait for a slot")
                return
            self.single_dl_btn.setEnabled(bool(has_url))
            self.single_dl_btn.setToolTip(
                "Single-click direct download" if has_url else "Select a language first")
        else:
            url = self._current_leaf.leaf_url()
            from ..core.iso_resolver import is_direct_iso_url
            from ..core.downloader import Downloader
            is_direct = bool(self._current_leaf.iso_url and Downloader.is_direct_iso(url)) \
                or is_direct_iso_url(url or "")
            if is_direct and at_limit:
                self.single_dl_btn.setEnabled(False)
                self.single_dl_btn.setToolTip(
                    f"Parallel limit reached ({active}/{self.queue.parallel_limit})")
            elif is_direct:
                self.single_dl_btn.setEnabled(True)
                self.single_dl_btn.setToolTip(url or "")

    def shutdown(self):
        self.queue.shutdown()
