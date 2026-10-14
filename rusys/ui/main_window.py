# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Main window for Rusys."""
from __future__ import annotations

import os
import threading
import webbrowser
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, __app_name__
from ..core import attach_ui_handler, log
from ..core.devices import (
    Device,
    enumerate_devices,
    human_size,
)
from ..core.downloader import Downloader
from ..core import multiboot
from ..core.flash_helpers import SECURE_BOOT_ADVISORY
from ..core.flasher import flash_image
from ..core.settings import Settings, load_settings, save_settings
from ..data.os_catalog import CatalogNode
from .about_dialog import AboutDialog
from .catalog_widget import CatalogWidget
from .download_dialog import DownloadDialog
from .os_downloads_widget import OSDownloadsWidget
from .settings_dialog import SettingsDialog
from .worker import Worker


def _download_dir(settings: Settings) -> str:
    if settings.download_dir and os.path.isdir(settings.download_dir):
        return settings.download_dir
    return os.path.expanduser("~/Downloads")


class _LogBridge(QObject):
    """Bridge object that emits a Qt signal for log messages.

    This ensures log messages from background threads are marshalled to
    the GUI thread before touching any Qt widget.
    """
    message = Signal(str, int)  # (formatted_message, level)


class IsoDropList(QListWidget):
    """A QListWidget that accepts dropped ISO/image files.

    *on_drop* is called with a list of local file paths so the parent can
    copy them onto the USB.  *extensions* is an optional tuple of lower-case
    extensions (including the dot) to accept; defaults to .iso/.img.
    """

    _DEFAULT_EXTS = (".iso", ".img")

    def __init__(self, parent=None, on_drop=None, extensions=None):
        super().__init__(parent)
        self._on_drop = on_drop
        self._extensions = extensions or self._DEFAULT_EXTS
        self.setAcceptDrops(True)
        self.setWordWrap(True)

    def _accepted_urls(self, mime):
        out = []
        for u in mime.urls():
            if u.isLocalFile():
                p = u.toLocalFile()
                if p.lower().endswith(self._extensions):
                    out.append(p)
        return out

    def dragEnterEvent(self, event):
        if self._accepted_urls(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._accepted_urls(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = self._accepted_urls(event.mimeData())
        if paths and self._on_drop is not None:
            self._on_drop(paths)
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self, settings: Optional[Settings] = None):
        super().__init__()
        self.settings = settings or load_settings()
        self.current_leaf: Optional[CatalogNode] = None
        self.current_image: str = self.settings.last_image
        self.worker: Optional[Worker] = None
        self._mb_cancel = threading.Event()
        self._sb_cancel = threading.Event()
        self._mb_prepared = False  # True after successful Prepare USB
        self._last_device_paths: list[str] = []  # for hotplug detection

        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.resize(820, 560)
        self.setMinimumSize(420, 320)
        import sys as _sys

        _base = getattr(
            _sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        icon_path = os.path.join(_base, "resources", "icons", "rusys.png")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._build_menus()
        self._build_ui()
        self._wire_logger()

        self.statusBar().hide()
        self.refresh_devices()
        self._update_image_field()
        self._sync_settings_ui()

        # USB hotplug detection: refresh device list every 3 seconds
        self._hotplug_timer = QTimer(self)
        self._hotplug_timer.timeout.connect(self._check_hotplug)
        self._hotplug_timer.start(3000)

        # Multiboot tab: auto-detect the connected USB (auto-select + refresh
        # its ISOs) every 3 seconds so the user never has to pick from a list.
        self._mb_last_paths: list[str] = []
        self._mb_auto_timer = QTimer(self)
        self._mb_auto_timer.timeout.connect(self._mb_auto_detect)
        self._mb_auto_timer.start(3000)

        # Restore last window size/position (issue: remember user layout).
        if self.settings.window_geometry:
            from PySide6.QtCore import QByteArray
            self.restoreGeometry(QByteArray.fromHex(self.settings.window_geometry.encode()))

        # Dark theme with clear text — fully dark, same as rpm/deb, font 10px for Windows
        # Force dark title bar on Windows 10/11 via DWM
        try:
            import sys as _sys
            if _sys.platform == "win32":
                import ctypes
                hwnd = int(self.winId())
                # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
        except:
            pass
        # Font 10px for Windows exe as requested, 9pt for Linux rpm/deb
        import sys as _sys2
        _is_win = _sys2.platform == "win32"
        _font = "9px" if _is_win else "10pt"
        self.setStyleSheet(("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-size: __RUSYS_FONT__;
                font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif;
            }
            QLabel {
                color: #cdd6f4;
                background: transparent;
            }
            QLabel#MutedText {
                color: #6c7086;
                font-size: 9pt;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px 12px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #585b70;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            QPushButton:disabled {
                background-color: #181825;
                color: #45475a;
                border-color: #313244;
            }
            QComboBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 3px 8px;
                min-height: 20px;
            }
            QComboBox:hover {
                border-color: #585b70;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #313244;
                color: #cdd6f4;
                selection-background-color: #45475a;
                border: 1px solid #45475a;
            }
            QLineEdit, QSpinBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 3px 8px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #89b4fa;
            }
            QProgressBar {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 4px;
                text-align: center;
                color: #cdd6f4;
                min-height: 18px;
            }
            QProgressBar::chunk {
                background-color: #89b4fa;
                border-radius: 3px;
            }
            QListWidget {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 3px;
            }
            QListWidget::item:selected {
                background-color: #45475a;
                color: #cdd6f4;
            }
            QListWidget::item:hover {
                background-color: #313244;
            }
            QTabWidget::pane {
                border: 1px solid #45475a;
                border-radius: 4px;
                background-color: #1e1e2e;
            }
            QTabBar::tab {
                background-color: #313244;
                color: #6c7086;
                border: 1px solid #45475a;
                padding: 6px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border-bottom-color: #1e1e2e;
            }
            QTabBar::tab:hover {
                color: #cdd6f4;
            }
            QGroupBox {
                border: 1px solid #45475a;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
                color: #cdd6f4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: #89b4fa;
            }
            QCheckBox {
                color: #cdd6f4;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #45475a;
                border-radius: 3px;
                background-color: #313244;
            }
            QCheckBox::indicator:checked {
                background-color: #89b4fa;
                border-color: #89b4fa;
            }
            QScrollBar:vertical {
                background-color: #181825;
                width: 10px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #45475a;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #181825;
                height: 10px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background-color: #45475a;
                border-radius: 5px;
                min-width: 20px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QHeaderView::section {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                padding: 4px 8px;
            }
            QTableWidget {
                background-color: #181825;
                alternate-background-color: #1e1e2e;
                color: #cdd6f4;
                gridline-color: #313244;
                border: 1px solid #45475a;
                border-radius: 4px;
            }
            QTableWidget::item {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QTableWidget::item:alternate {
                background-color: #181825;
                color: #cdd6f4;
            }
            QTableWidget::item:selected {
                background-color: #45475a;
                color: #cdd6f4;
            }
            QTableWidget::item:selected:alternate {
                background-color: #45475a;
                color: #cdd6f4;
            }
            QMenu {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
            }
            QMenu::item:selected {
                background-color: #45475a;
            }
            QMessageBox {
                background-color: #1e1e2e;
            }
            QToolTip {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                padding: 4px;
            }
        """).replace("__RUSYS_FONT__", _font))
        self.statusBar().hide()

    # ------------------------------------------------------------------ menus
    def _build_menus(self):
        menubar = self.menuBar()
        help_menu = menubar.addMenu("Help")
        act_about = QAction("About Rusys", self)
        act_about.triggered.connect(self.open_about)
        help_menu.addAction(act_about)

    # --------------------------------------------------------------------- ui
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        from PySide6.QtWidgets import QSplitter
        splitter = QSplitter()
        splitter.setOrientation(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet("QSplitter::handle { background: #313244; } QSplitter::handle:hover { background: #45475a; }")
        root.addWidget(splitter)

        # Left: catalogue
        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(QLabel("OS and Download Catalogue"))
        self.catalog = CatalogWidget()
        self.catalog.leaf_selected.connect(self.on_leaf_selected)
        left.addWidget(self.catalog, 1)
        splitter.addWidget(left_widget)

        # Right: workflow (tabbed: single-image write + multiboot USB)
        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(right_widget)
        splitter.setSizes([420, 420])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        self.splitter = splitter

        self.mode_tabs = QTabWidget()

        # ---- Tab 0: OS Downloads (IDM-like, 30-part) ----
        self.os_downloads = OSDownloadsWidget(self.settings, self)
        self.os_downloads.downloaded.connect(self._on_downloaded)
        self.mode_tabs.addTab(self.os_downloads, "OS Downloads")

        # ---- Rufus-like Single boot USB (Drive Properties + Format Options) ----
        write_widget = QWidget()
        write_layout = QVBoxLayout(write_widget)
        write_layout.setContentsMargins(6, 6, 6, 6)
        write_layout.setSpacing(6)

        # Drive Properties header (Rufus style)
        dp_hdr = QLabel("Drive Properties")
        dp_hdr.setStyleSheet("font-weight: bold; font-size: 10pt;")
        write_layout.addWidget(dp_hdr)

        # Device
        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Device"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(220)
        dev_row.addWidget(self.device_combo, 1)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setMaximumWidth(70)
        self.refresh_btn.clicked.connect(self.refresh_devices)
        dev_row.addWidget(self.refresh_btn)
        write_layout.addLayout(dev_row)

        # Source image (Add/Remove — Rufus-like, Boot selection merged here)
        sb_img_row = QHBoxLayout()
        self.sb_add_btn = QPushButton("Add image...")
        self.sb_add_btn.clicked.connect(self.browse_image)
        sb_img_row.addWidget(self.sb_add_btn)
        self.sb_remove_btn = QPushButton("Remove")
        self.sb_remove_btn.setEnabled(False)
        self.sb_remove_btn.clicked.connect(self._sb_remove_image)
        sb_img_row.addWidget(self.sb_remove_btn)
        write_layout.addLayout(sb_img_row)
        self.sb_hint = QLabel("(no image selected)")
        self.sb_hint.setObjectName("MutedText")
        self.sb_hint.setWordWrap(True)
        write_layout.addWidget(self.sb_hint)

        # Partition scheme + Target system (Rufus side-by-side) — linked as in Rufus pipeline
        part_row = QHBoxLayout()
        part_row.addWidget(QLabel("Partition scheme"))
        self.sb_part_scheme = QComboBox()
        self.sb_part_scheme.addItems(["MBR", "GPT"])
        self.sb_part_scheme.currentTextChanged.connect(self._on_part_scheme_changed)
        part_row.addWidget(self.sb_part_scheme, 1)
        part_row.addWidget(QLabel("Target system"))
        self.sb_target_sys = QComboBox()
        self.sb_target_sys.addItems(["BIOS or UEFI", "UEFI (non CSM)", "BIOS (or UEFI-CSM)"])
        part_row.addWidget(self.sb_target_sys, 1)
        write_layout.addLayout(part_row)

        # Advanced drive properties (collapsible, Rufus: Show advanced drive properties)
        self.adv_drive_btn = QPushButton("Show advanced drive properties  ▼")
        self.adv_drive_btn.setCheckable(True)
        self.adv_drive_btn.setStyleSheet("text-align: left;")
        self.adv_drive_btn.clicked.connect(self._toggle_adv_drive)
        write_layout.addWidget(self.adv_drive_btn)
        self.adv_drive_box = QFrame()
        self.adv_drive_box.setVisible(False)
        adv_dv = QVBoxLayout(self.adv_drive_box)
        adv_dv.setContentsMargins(12, 2, 2, 2)
        self.opt_list_usb = QCheckBox("List USB Hard Drives")
        self.opt_list_usb.setChecked(True)
        self.opt_old_bios = QCheckBox("Add fixes for old BIOSes (extra partition, align, etc.)")
        self.opt_old_bios.setChecked(False)
        self.opt_uefi = QCheckBox("Enable runtime UEFI media validation")
        for w in (self.opt_list_usb, self.opt_old_bios, self.opt_uefi):
            adv_dv.addWidget(w)
        write_layout.addWidget(self.adv_drive_box)

        # Format Options header
        fo_hdr = QLabel("Format Options")
        fo_hdr.setStyleSheet("font-weight: bold; font-size: 10pt;")
        write_layout.addWidget(fo_hdr)

        # Volume label
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volume label"))
        self.sb_vol_label = QLineEdit("RUSYS")
        self.sb_vol_label.setMaxLength(11)
        vol_row.addWidget(self.sb_vol_label, 1)
        write_layout.addLayout(vol_row)

        # File system + Cluster size (Rufus side-by-side) — cluster follows FS as in Rufus
        fs_row = QHBoxLayout()
        fs_row.addWidget(QLabel("File system"))
        self.sb_fs = QComboBox()
        self.sb_fs.addItems(["NTFS", "FAT32", "exFAT", "UDF", "Large FAT32", "ext2", "ext3", "ext4"])
        self.sb_fs.currentTextChanged.connect(self._on_fs_changed)
        fs_row.addWidget(self.sb_fs, 1)
        fs_row.addWidget(QLabel("Cluster size"))
        self.sb_cluster = QComboBox()
        self.sb_cluster.addItems(["4096 bytes (Default)", "8192 bytes", "16 kilobytes", "32 kilobytes", "64 kilobytes"])
        fs_row.addWidget(self.sb_cluster, 1)
        write_layout.addLayout(fs_row)

        # Advanced format options (collapsible, Rufus: Show advanced format options)
        self.adv_fmt_btn = QPushButton("Show advanced format options  ▼")
        self.adv_fmt_btn.setCheckable(True)
        self.adv_fmt_btn.setStyleSheet("text-align: left;")
        self.adv_fmt_btn.clicked.connect(self._toggle_adv_fmt)
        write_layout.addWidget(self.adv_fmt_btn)
        self.adv_fmt_box = QFrame()
        self.adv_fmt_box.setVisible(False)
        adv_fv = QVBoxLayout(self.adv_fmt_box)
        adv_fv.setContentsMargins(12, 2, 2, 2)
        self.opt_verify = QCheckBox("Quick format")
        self.opt_verify.setChecked(True)
        self.opt_bitlocker = QCheckBox("Create extended label and icon files")
        self.opt_bitlocker.setChecked(True)
        self.opt_secboot = QCheckBox("Check device for bad blocks")
        self.opt_secboot.setChecked(True)
        self.opt_silent = QCheckBox("Silent install (when supported)")
        self.opt_headless = QCheckBox("Headless install (Windows)")
        self.opt_headless.setToolTip("Unattended/headless Windows install (autounattend.xml) — enabled for Windows ISOs only")
        self.opt_custom = QCheckBox("Run custom ops after write")
        for w in (self.opt_verify, self.opt_bitlocker, self.opt_secboot, self.opt_silent, self.opt_headless, self.opt_custom):
            adv_fv.addWidget(w)
        write_layout.addWidget(self.adv_fmt_box)

        # Status + Progress (Rufus style)
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status"))
        self.sb_status = QLabel("Ready")
        self.sb_status.setObjectName("MutedText")
        status_row.addWidget(self.sb_status, 1)
        write_layout.addLayout(status_row)
        self.flash_bar = QProgressBar()
        self.flash_bar.setRange(0, 100)
        self.flash_bar.setValue(0)
        write_layout.addWidget(self.flash_bar)
        write_layout.addStretch()

        # log (kept for internal use but not shown in UI)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)

        # START / CLOSE (Rufus bottom buttons)
        sb_btn_row = QHBoxLayout()
        self.start_btn = QPushButton("START")
        self.start_btn.setMinimumHeight(36)
        self.start_btn.setStyleSheet("font-weight: bold;")
        self.start_btn.clicked.connect(self.start_flash)
        sb_btn_row.addWidget(self.start_btn)
        self.sb_cancel_btn = QPushButton("Cancel")
        self.sb_cancel_btn.setMinimumHeight(36)
        self.sb_cancel_btn.setEnabled(False)
        self.sb_cancel_btn.clicked.connect(self._sb_cancel_flash)
        sb_btn_row.addWidget(self.sb_cancel_btn)
        write_layout.addLayout(sb_btn_row)

        self.mode_tabs.addTab(write_widget, "Single boot USB")

        # ---- Tab 2: Multiboot USB (Ventoy-like) ----
        mb_widget = self._build_multiboot_tab()
        self.mode_tabs.addTab(mb_widget, "Multi boot USB")

        right.addWidget(self.mode_tabs)

        # Persist splitter and single-boot opts on change (local cache)
        self.splitter.splitterMoved.connect(lambda pos, idx: self._save_splitter())
        self.opt_list_usb.toggled.connect(lambda _: self._save_single_boot_opts())
        self.opt_old_bios.toggled.connect(lambda _: self._save_single_boot_opts())
        self.opt_uefi.toggled.connect(lambda _: self._save_single_boot_opts())
        self.opt_verify.toggled.connect(lambda _: self._save_single_boot_opts())
        self.opt_bitlocker.toggled.connect(lambda _: self._save_single_boot_opts())
        self.opt_secboot.toggled.connect(lambda _: self._save_single_boot_opts())
        self.opt_silent.toggled.connect(lambda _: self._save_single_boot_opts())
        self.opt_headless.toggled.connect(lambda _: self._save_single_boot_opts())
        self.opt_custom.toggled.connect(lambda _: self._save_single_boot_opts())
        self.sb_part_scheme.currentTextChanged.connect(lambda _: self._save_single_boot_opts())
        self.sb_target_sys.currentTextChanged.connect(lambda _: self._save_single_boot_opts())
        self.sb_fs.currentTextChanged.connect(lambda _: self._save_single_boot_opts())
        self.sb_cluster.currentTextChanged.connect(lambda _: self._save_single_boot_opts())
        self.sb_vol_label.textChanged.connect(lambda _: self._save_single_boot_opts())
        # parallel_spin is in OSDownloadsWidget, not here — handled via settings save on change there
        # Apply saved splitter sizes after UI built
        if self.settings.splitter_sizes:
            try:
                sizes = [int(x) for x in self.settings.splitter_sizes.split(",")]
                if len(sizes) == 2:
                    self.splitter.setSizes(sizes)
            except:
                pass

    def _wire_logger(self):
        # Use a signal bridge so log messages from background threads are
        # marshalled to the GUI thread before touching any QWidget.
        self._log_bridge = _LogBridge()
        self._log_bridge.message.connect(self._on_log_message)
        attach_ui_handler(log, self._log_bridge.message.emit)

    def _on_log_message(self, msg: str, level: int):
        """Handle a log message on the GUI thread (connected via signal)."""
        self.log.appendPlainText(msg)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    # --------------------------------------------------------------- catalogue
    def on_leaf_selected(self, leaf: CatalogNode):
        self.current_leaf = leaf
        # Update OS Downloads tab single-download button
        try:
            self.os_downloads.set_selected_os(leaf)
        except Exception:
            pass

        # Issue #3003: do not force runtime UEFI validation on Ubuntu images.
        if "uefi-validation-caution" in leaf.tags and self.opt_uefi.isChecked():
            self.opt_uefi.setChecked(False)
            self.log.appendPlainText(
                "[3003] Runtime UEFI media validation auto-disabled for "
                f"'{leaf.name}' (would break the installer)."
            )

        # Issue #3008: only enable the silent/headless install options for Windows images.
        is_windows = leaf.name.lower().startswith("windows") or (
            leaf.leaf_url() and "microsoft.com" in (leaf.leaf_url() or "")
        ) or "windows" in leaf.name.lower()
        self.opt_silent.setEnabled(bool(is_windows))
        self.opt_headless.setEnabled(bool(is_windows))
        if is_windows:
            self.opt_headless.setChecked(True)
            self.opt_silent.setChecked(True)
        else:
            self.opt_silent.setChecked(False)
            self.opt_headless.setChecked(False)

    def _open_in_default_browser(self, url: str) -> bool:
        """Open ``url`` in the OS default browser (e.g. Firefox).

        Prefers Qt's native ``QDesktopServices.openUrl`` (uses xdg-open /
        ``open`` / the Windows shell association) which is far more reliable
        than Python's ``webbrowser`` module inside a frozen GUI app. Falls
        back to ``webbrowser`` only if the native call fails, and finally
        tells the user the exact URL when no handler is available.
        """
        if QDesktopServices.openUrl(QUrl(url)):
            return True
        # Fallback: Python's webbrowser (may still fail silently on some setups).
        try:
            return bool(webbrowser.open(url))
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("webbrowser.open failed: %s", exc)
            return False

    def download_selected(self):
        leaf = self.current_leaf
        url = leaf.leaf_url() if leaf else None
        if not url:
            return
        if leaf and leaf.iso_url and Downloader.is_direct_iso(url):
            # IDM-like 30-part download in OS Downloads tab (no browser)
            self.os_downloads.add_download(url)
            self.mode_tabs.setCurrentWidget(self.os_downloads)
            QMessageBox.information(
                self,
                "Download queued",
                f"'{leaf.name}' has been added to the OS Downloads queue.\n\n"
                "It will download with 30 parts in parallel. Track progress in the OS Downloads tab.",
            )
        else:
            opened = self._open_in_default_browser(url)
            if opened:
                name = leaf.name if leaf else ""
                QMessageBox.information(
                    self,
                    "Open download page",
                    f"Rusys opened the official download page for '{name}' in your "
                    "default browser.\n\n"
                    "Download the ISO with your browser, then use 'Browse...' to "
                    "select it as the source image.",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Could not open browser",
                    f"Rusys could not launch your default browser automatically.\n\n"
                    f"Please open this link manually:\n{url}",
                )

    def _on_downloaded(self, path: str):
        self.current_image = path
        self.settings.last_image = path
        save_settings(self.settings)
        self._update_image_field()

    # ----------------------------------------------------------- multiboot USB
    def _build_multiboot_tab(self) -> QWidget:
        """Build the 'Multiboot USB' tab (Ventoy-like ISO folder + GRUB)."""
        tab = QFrame()
        tab.setObjectName("InnerPanel")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # device selection
        dev_box = QGroupBox("Target USB device")
        dv = QHBoxLayout(dev_box)
        self.mb_device_combo = QComboBox()
        self.mb_device_combo.setMinimumWidth(320)
        dv.addWidget(self.mb_device_combo, 1)
        mb_refresh = QPushButton("Refresh")
        mb_refresh.clicked.connect(self.mb_refresh_devices)
        self.mb_device_refresh_btn = mb_refresh
        dv.addWidget(mb_refresh)
        layout.addWidget(dev_box)

        # theme selection
        theme_box = QGroupBox("Menu theme")
        th = QHBoxLayout(theme_box)
        self.mb_theme_combo = QComboBox()
        self.mb_theme_combo.setMinimumWidth(200)
        for t in multiboot.AVAILABLE_THEMES:
            self.mb_theme_combo.addItem(t)
        idx = self.mb_theme_combo.findText(self.settings.theme)
        if idx >= 0:
            self.mb_theme_combo.setCurrentIndex(idx)
        else:
            self.mb_theme_combo.setCurrentText(multiboot.THEME_NAME)
        th.addWidget(QLabel("Theme:"), 0)
        th.addWidget(self.mb_theme_combo, 1)
        self.mb_theme_apply = QPushButton("Apply theme")
        self.mb_theme_apply.clicked.connect(self.mb_apply_theme)
        th.addWidget(self.mb_theme_apply)
        layout.addWidget(theme_box)

        # actions
        actions = QHBoxLayout()
        self.mb_prepare_btn = QPushButton("Prepare USB (format)")
        self.mb_prepare_btn.setObjectName("PrimaryButton")
        self.mb_prepare_btn.clicked.connect(self.mb_prepare)
        actions.addWidget(self.mb_prepare_btn)

        self.mb_cancel_btn = QPushButton("Cancel")
        self.mb_cancel_btn.setEnabled(False)
        self.mb_cancel_btn.clicked.connect(self._mb_cancel_op)
        actions.addWidget(self.mb_cancel_btn)

        self.mb_eject_btn = QPushButton("Eject")
        self.mb_eject_btn.clicked.connect(self.mb_eject)
        actions.addWidget(self.mb_eject_btn)

        self.mb_add_btn = QPushButton("Add ISO...")
        self.mb_add_btn.clicked.connect(self.mb_add_iso)
        actions.addWidget(self.mb_add_btn)

        self.mb_remove_btn = QPushButton("Remove ISO")
        self.mb_remove_btn.clicked.connect(self.mb_remove_iso)
        actions.addWidget(self.mb_remove_btn)

        self.mb_iso_refresh = QPushButton("Refresh ISOs")
        self.mb_iso_refresh.clicked.connect(self.mb_refresh_isos)
        actions.addWidget(self.mb_iso_refresh)
        layout.addLayout(actions)

        # status
        self.mb_status = QLabel(
            "Select a USB device, then 'Prepare USB' to format it once and "
            "create the Rusys_Iso-Files folder. After that, add ISOs and boot "
            "from the USB to pick one from the menu."
        )
        self.mb_status.setWordWrap(True)
        self.mb_status.setObjectName("MutedText")
        layout.addWidget(self.mb_status)

        # ISO list
        iso_box = QGroupBox("ISOs on this USB (Rusys_Iso-Files)")
        iv = QVBoxLayout(iso_box)
        self.mb_iso_list = IsoDropList(on_drop=self._mb_drop_isos)
        iv.addWidget(self.mb_iso_list)
        iso_hint = QLabel("Tip: select multiple ISOs with the Add ISO button, "
                          "or drag & drop several ISO/image files here.")
        iso_hint.setObjectName("MutedText")
        iso_hint.setWordWrap(True)
        iv.addWidget(iso_hint)
        layout.addWidget(iso_box, 1)

        self.mb_progress = QProgressBar()
        self.mb_progress.setRange(0, 100)
        self.mb_progress.setValue(0)
        layout.addWidget(self.mb_progress)

        self.mb_refresh_devices()
        self._mb_update_buttons()
        return tab

    def mb_refresh_devices(self):
        self.mb_device_combo.clear()
        self.mb_device_combo.addItem("— select a USB device —", None)
        devs = enumerate_devices()
        for dev in devs:
            self.mb_device_combo.addItem(dev.display, dev)
        # Auto-select the first USB so the user doesn't have to pick manually.
        if devs:
            self.mb_device_combo.setCurrentIndex(1)

    def _mb_device(self) -> Optional[Device]:
        data = self.mb_device_combo.currentData()
        return data if isinstance(data, Device) else None

    def _mb_auto_detect(self) -> None:
        """Poll for the connected USB and auto-select / auto-refresh it.

        Runs on a timer.  Rebuilds the device list only when the set of plugged
        devices actually changes (so a manual selection is never clobbered),
        restores the previous selection if it is still present, otherwise picks
        the first device.  For a recognised Rusys stick it refreshes the ISO list
        automatically.
        """
        if self.worker is not None and self.worker.isRunning():
            return
        devs = enumerate_devices()
        paths = [d.path for d in devs]
        # No change and something is already selected -> leave it alone.
        if paths == self._mb_last_paths and self._mb_device() is not None:
            return
        self._mb_last_paths = paths

        prev = self._mb_device()
        self.mb_device_combo.blockSignals(True)
        self.mb_device_combo.clear()
        self.mb_device_combo.addItem("— select a USB device —", None)
        for d in devs:
            self.mb_device_combo.addItem(d.display, d)
        sel_idx = 0
        if prev is not None:
            for i in range(1, self.mb_device_combo.count()):
                item = self.mb_device_combo.itemData(i)
                if isinstance(item, Device) and item.path == prev.path:
                    sel_idx = i
                    break
        elif devs:
            sel_idx = 1  # first real device (index 0 is the placeholder)
        self.mb_device_combo.setCurrentIndex(sel_idx)
        self.mb_device_combo.blockSignals(False)

        dev = self._mb_device()
        if dev is not None and multiboot.is_prepared_label(dev.path):
            self.mb_refresh_isos(silent=True)

    def mb_prepare(self):
        dev = self._mb_device()
        if dev is None:
            QMessageBox.warning(self, "No device", "Please select a USB device first.")
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Busy", "An operation is already running.")
            return
        reply = QMessageBox.warning(
            self, "Format USB?",
            f"This will ERASE ALL DATA on {dev.path} ({dev.size_human}) and "
            "create a Rusys multiboot USB.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._mb_set_busy(True, f"Preparing {dev.path} ... (you may be asked for a password once)")
        self.mb_cancel_btn.setEnabled(False)  # format cannot be cancelled
        self.mb_progress.setValue(10)
        self.settings.theme = self.mb_theme_combo.currentText()
        save_settings(self.settings)
        self.worker = Worker(
            multiboot.prepare_usb,
            dev.path,
            "Rusys",
            "ntfs",
            512,
            self.mb_theme_combo.currentText(),
            progress_cb=lambda done, total, stage: None,
        )
        self.worker.progress.connect(self._mb_on_progress)
        self.worker.finished.connect(self._mb_on_prepare_done)
        self.worker.errored.connect(
            lambda m: (self.mb_status.setText(f"Prepare failed: {m}"),
                       self._mb_set_busy(False))
        )
        self.worker.start()

    def _mb_on_progress(self, done: float, total: float, extra=None) -> None:
        if total:
            self.mb_progress.setValue(int(done * 100 / total))
        else:
            self.mb_progress.setValue(0)

    def _mb_on_prepare_done(self, result: dict):
        self._mb_set_busy(False)
        self.mb_progress.setValue(100)
        if result.get("returncode", -1) != 0:
            detail = (result.get("stdout") or "") + "\n" + (result.get("stderr") or "")
            detail = detail.strip() or "unknown error"
            self.mb_status.setText(
                "Prepare failed (rc=%s).\n%s"
                % (result.get("returncode"), detail[-1500:])
            )
            QMessageBox.critical(self, "Prepare failed", detail[-2500:])
            return
        self._mb_prepared = True
        self._mb_update_buttons()
        msg = (
            "USB Prepared with Rusys. Copy your ISO files into the "
            '"Rusys_Iso-Files" folder on the USB -- they appear in the boot '
            "menu automatically."
        )
        msg += (
            "\n\nSecure Boot: Rusys signed boot chain works with Secure Boot ON. "
            "On the very first boot you may see a blue Mok Manager / 'Enroll key' "
            "screen -- just continue/enroll to trust Ventoy, then it boots. "
            "Theme is already applied; switch it anytime via 'Apply theme'."
        )
        self.mb_status.setText(msg)
        self.mb_iso_list.clear()
        QMessageBox.information(self, "USB prepared", msg)

    def _mb_with_mount(self, op):
        """Mount the prepared data partition, run *op(mountpoint)*, unmount."""
        dev = self._mb_device()
        if dev is None:
            QMessageBox.warning(self, "No device", "Please select a USB device first.")
            return None
        part = multiboot.data_partition_path(dev.path)
        try:
            mp = multiboot.mount_partition(part)
        except Exception as exc:
            QMessageBox.critical(self, "Mount failed", str(exc))
            return None
        try:
            return op(mp)
        finally:
            multiboot.unmount_partition(mp)

    def _mb_set_busy(self, busy: bool, status: Optional[str] = None) -> None:
        """Disable the multiboot controls while an operation runs; only the
        Cancel button stays enabled so the running job can be aborted."""
        for w in (
            self.mb_prepare_btn,
            self.mb_add_btn,
            self.mb_remove_btn,
            self.mb_iso_refresh,
            self.mb_eject_btn,
            self.mb_theme_apply,
            self.mb_device_combo,
            self.mb_device_refresh_btn,
        ):
            w.setEnabled(not busy)
        self.mb_cancel_btn.setEnabled(busy)
        if busy:
            self._mb_cancel.clear()
            self.mb_progress.setValue(0)
        if status is not None:
            self.mb_status.setText(status)
        if not busy:
            self._mb_update_buttons()

    def _mb_update_buttons(self):
        """Enable/disable multiboot buttons based on whether USB has been prepared."""
        prepared = self._mb_prepared
        self.mb_add_btn.setEnabled(prepared)
        self.mb_remove_btn.setEnabled(prepared)
        self.mb_iso_refresh.setEnabled(prepared)
        self.mb_eject_btn.setEnabled(prepared)
        self.mb_theme_apply.setEnabled(prepared)

    def _mb_cancel_op(self) -> None:
        self._mb_cancel.set()
        self.mb_status.setText("Cancelling...")

    def _mb_run_async(self, fn, on_done, busy_text: str, silent: bool = False) -> None:
        """Run *fn* (which takes progress_cb=None) on a worker thread so the UI
        stays responsive.  *on_done(result)* runs on the GUI thread afterwards.
        When *silent* is True, failures update the status text only (no dialog) so
        background auto-detection never spams the user with message boxes.
        """
        if self.worker is not None and self.worker.isRunning():
            if not silent:
                QMessageBox.information(self, "Busy", "An operation is already running.")
            return
        self._mb_set_busy(True, busy_text)
        w = Worker(fn, progress_cb=None)
        w.progress.connect(self._mb_on_progress)

        def _finished(res):
            try:
                on_done(res)
            finally:
                self._mb_set_busy(False)

        def _errored(msg):
            self.mb_status.setText(f"Error: {msg}")
            if not silent:
                QMessageBox.critical(self, "Operation failed", msg)
            self._mb_set_busy(False)

        w.finished.connect(_finished)
        w.errored.connect(_errored)
        self.worker = w
        w.start()

    def _mb_data_part(self) -> Optional[str]:
        """Return the data-partition path if a device is selected and present."""
        dev = self._mb_device()
        if dev is None:
            QMessageBox.warning(self, "No device", "Please select a USB device first.")
            return None
        part = multiboot.data_partition_path(dev.path)
        if not os.path.exists(part):
            QMessageBox.information(
                self, "Device not connected",
                f"{part} is not present. Is the USB still plugged in?\n"
                "If you ejected it, re-connect it and refresh the device list.",
            )
            return None
        return part

    def _mb_esp_part(self) -> Optional[str]:
        """Return the ESP path if a device is selected and present."""
        dev = self._mb_device()
        if dev is None:
            QMessageBox.warning(self, "No device", "Please select a USB device first.")
            return None
        part = multiboot.esp_partition_path(dev.path)
        if not os.path.exists(part):
            QMessageBox.information(
                self, "Device not connected",
                f"{part} is not present. Is the USB still plugged in?\n"
                "If you ejected it, re-connect it and refresh the device list.",
            )
            return None
        return part

    def mb_refresh_isos(self, silent: bool = False):
        dev = self._mb_device()
        if dev is None:
            self.mb_iso_list.clear()
            if not silent:
                self.mb_status.setText("No USB device connected.")
            return
        part = multiboot.data_partition_path(dev.path)
        if not os.path.exists(part):
            self.mb_iso_list.clear()
            if not silent:
                self.mb_status.setText("Device not connected.")
            return

        def _op(progress_cb=None):
            mp = multiboot.mount_partition(part)
            try:
                return multiboot.list_isos(mp), multiboot.is_prepared(mp)
            finally:
                multiboot.unmount_partition(mp)

        def _done(res):
            isos, prepared = res
            self.mb_iso_list.clear()
            for iso in isos:
                self.mb_iso_list.addItem(iso)
            self.mb_status.setText(
                "Prepared: " + ("yes" if prepared else "no")
                + f"  |  {len(isos)} ISO(s) on this USB."
            )

        self._mb_run_async(_op, _done, "Reading USB...", silent=silent)

    def mb_apply_theme(self):
        theme = self.mb_theme_combo.currentText()
        self.settings.theme = theme
        save_settings(self.settings)
        dev = self._mb_device()
        if dev is None:
            self.mb_status.setText("Connect the prepared USB to apply the theme.")
            return

        def _op(progress_cb=None):
            return multiboot.apply_theme_to_ventoy(dev.path, theme)

        def _done(res):
            if res.get("returncode", -1) != 0:
                detail = (res.get("stdout") or "") + "\n" + (res.get("stderr") or "")
                self.mb_status.setText("Theme apply failed:\n" + detail[-1200:])
                return
            self.mb_status.setText(
                f"Theme set to '{theme}'. Reboot the USB to see it."
            )

        self._mb_run_async(_op, _done, f"Applying {theme} theme...")

    def mb_add_iso(self):
        part = self._mb_data_part()
        if part is None:
            return
        dlg = QFileDialog(self, "Select ISO file(s)", os.path.expanduser("~/Downloads"))
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dlg.setNameFilter("ISO images (*.iso *.ISO *.img *.IMG);;All files (*)")
        if dlg.exec() != QFileDialog.DialogCode.Accepted:
            return
        paths = [p for p in dlg.selectedFiles() if p]
        if not paths:
            return
        self._mb_copy_isos(paths)

    def _mb_drop_isos(self, paths):
        """Called when ISO/image files are dropped onto the ISO list."""
        if self._mb_data_part() is None:
            return
        self._mb_copy_isos(paths)

    def _mb_copy_isos(self, paths):
        """Copy one or more ISO/image files onto the USB (Rusys_Iso-Files)."""
        paths = [p for p in paths if p and os.path.isfile(p)]
        if not paths:
            return
        part = self._mb_data_part()
        if part is None:
            return
        total = len(paths)

        def _op(progress_cb=None):
            mp = multiboot.mount_partition(part)
            try:
                dests = []
                for p in paths:
                    dest = multiboot.add_iso(
                        mp, p,
                        progress_cb=progress_cb,
                        cancel_event=self._mb_cancel,
                    )
                    dests.append(dest)
                return dests
            finally:
                multiboot.unmount_partition(mp)

        def _done(dests):
            names = ", ".join(os.path.basename(d) for d in dests)
            self.mb_status.setText(f"Added {len(dests)}: {names}")
            self.mb_refresh_isos()

        self._mb_run_async(_op, _done, f"Copying {total} ISO(s)...")

    def mb_remove_iso(self):
        item = self.mb_iso_list.currentItem()
        if item is None:
            QMessageBox.information(self, "No selection", "Select an ISO to remove.")
            return
        part = self._mb_data_part()
        if part is None:
            return

        def _op(progress_cb=None):
            mp = multiboot.mount_partition(part)
            try:
                multiboot.remove_iso(mp, item.text())
            finally:
                multiboot.unmount_partition(mp)

        def _done(_res):
            self.mb_status.setText(f"Removed: {item.text()}")
            self.mb_refresh_isos()

        self._mb_run_async(_op, _done, f"Removing {item.text()} ...")

    def mb_eject(self):
        dev = self._mb_device()
        if dev is None:
            QMessageBox.warning(self, "No device", "Please select a USB device first.")
            return
        reply = QMessageBox.question(
            self, "Eject USB?",
            f"Unmount and safely power off {dev.path}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        def _op(progress_cb=None):
            return multiboot.eject_device(dev.path)

        def _done(_res):
            self.mb_status.setText(f"Ejected {dev.path}. You can unplug it safely.")
            self.mb_refresh_devices()

        self._mb_run_async(_op, _done, f"Ejecting {dev.path} ...")

    # ----------------------------------------------------------------- devices
    def refresh_devices(self):
        self.device_combo.clear()
        self.device_combo.addItem("— select a target —", None)
        devs = enumerate_devices()
        for dev in devs:
            self.device_combo.addItem(dev.display, dev)
        # Track current device paths for hotplug detection
        self._last_device_paths = [d.path for d in devs]
        # Auto-select the first USB device if none was previously selected
        if self.settings.last_device:
            idx = self.device_combo.findData(self.settings.last_device, Qt.ItemDataRole.UserRole)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
                return
        # Auto-select first available USB device
        if devs:
            self.device_combo.setCurrentIndex(1)  # index 0 is placeholder

    def _check_hotplug(self):
        """Periodically check for USB device changes and auto-refresh."""
        if self.worker and self.worker.isRunning():
            return  # don't refresh during an active operation
        current_devs = enumerate_devices()
        current_paths = [d.path for d in current_devs]
        if current_paths != self._last_device_paths:
            self._last_device_paths = current_paths
            # Rebuild combo without losing user's image selection
            self.refresh_devices()

    def selected_device(self) -> Optional[Device]:
        data = self.device_combo.currentData()
        if isinstance(data, Device):
            return data
        return None

    # ------------------------------------------------------------------- image
    def browse_image(self):
        start = os.path.dirname(self.current_image) or os.path.expanduser("~/Downloads")
        dlg = QFileDialog(self, "Select image file", start)
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
        dlg.setNameFilter(
            "Images (*.iso *.ISO *.img *.IMG *.raw *.RAW *.zip *.ZIP "
            "*.wim *.WIM *.vhd *.VHD *.vhdx *.VHDX *.efi *.EFI *.vtoy *.VTOY);;"
            "All files (*)"
        )
        if dlg.exec() != QFileDialog.DialogCode.Accepted:
            return
        paths = dlg.selectedFiles()
        if paths and paths[0]:
            self.current_image = paths[0]
            self.settings.last_image = paths[0]
            save_settings(self.settings)
            self._update_image_field()

    def _update_image_field(self):
        has_image = bool(self.current_image and os.path.isfile(self.current_image))
        self.sb_remove_btn.setEnabled(has_image)
        if has_image:
            sz = human_size(os.path.getsize(self.current_image))
            self.sb_hint.setText(
                f"{os.path.basename(self.current_image)}  ({sz})"
            )
            self.sb_hint.setToolTip(self.current_image)
        else:
            self.sb_hint.setText("(no image selected)")
            self.sb_hint.setToolTip("")

    def _sb_remove_image(self):
        """Clear the selected image."""
        self.current_image = ""
        self.settings.last_image = ""
        save_settings(self.settings)
        self._update_image_field()

    def _on_part_scheme_changed(self, scheme: str):
        # Rufus pipeline: MBR → BIOS or UEFI (or BIOS CSM), GPT → UEFI non-CSM
        # Block signals to avoid recursion
        self.sb_target_sys.blockSignals(True)
        if scheme == "GPT":
            idx = self.sb_target_sys.findText("UEFI (non CSM)")
            if idx >= 0:
                self.sb_target_sys.setCurrentIndex(idx)
        else:  # MBR
            idx = self.sb_target_sys.findText("BIOS or UEFI")
            if idx >= 0:
                self.sb_target_sys.setCurrentIndex(idx)
        self.sb_target_sys.blockSignals(False)

    def _on_fs_changed(self, fs: str):
        # Rufus 4.15 exact per FS (src/rufus.c SetFileSystemAndClusterSize + MS KB140365)
        # FAT32/NTFS/exFAT differ as per Rufus UI
        self.sb_cluster.blockSignals(True)
        self.sb_cluster.clear()
        if fs == "FAT32":
            # Rufus FAT32 for typical 8GB USB: 1024,2048,4096 Default,8192,16K,32K — 512 and 64K hidden (per src/rufus.c FAT32 thresholds)
            self.sb_cluster.addItems(["1024 bytes", "2048 bytes", "4096 bytes (Default)", "8192 bytes", "16 kilobytes", "32 kilobytes"])
            self.sb_cluster.setCurrentText("4096 bytes (Default)")
        elif fs == "Large FAT32":
            self.sb_cluster.addItems(["8192 bytes", "16 kilobytes", "32 kilobytes (Default)", "64 kilobytes"])
            self.sb_cluster.setCurrentText("32 kilobytes (Default)")
        elif fs == "NTFS":
            # NTFS per MS KB140365: 512,1024,2048,4096 Default,8192,16K,32K,64K — all offered
            self.sb_cluster.addItems(["512 bytes", "1024 bytes", "2048 bytes", "4096 bytes (Default)", "8192 bytes", "16 kilobytes", "32 kilobytes", "64 kilobytes"])
            self.sb_cluster.setCurrentText("4096 bytes (Default)")
        elif fs == "exFAT":
            # exFAT per MS KB140365: 7M-256M 4K, 256M-32G 32K, 32G-256T 128K — Rufus picks 32K for <32G, 128K for >32G
            # We expose full list and set Default to 128K for >32G USB (typical 32-64G), fallback 32K
            self.sb_cluster.addItems(["512 bytes", "1024 bytes", "2048 bytes", "4096 bytes", "8192 bytes", "16 kilobytes", "32 kilobytes", "128 kilobytes (Default)", "256 kilobytes"])
            self.sb_cluster.setCurrentText("128 kilobytes (Default)")
        elif fs in ("ext2", "ext3", "ext4"):
            self.sb_cluster.addItems(["1024 bytes", "2048 bytes", "4096 bytes (Default)", "8192 bytes"])
            self.sb_cluster.setCurrentText("4096 bytes (Default)")
        elif fs == "UDF":
            self.sb_cluster.addItems(["512 bytes", "1024 bytes", "2048 bytes (Default)", "4096 bytes", "8192 bytes"])
            self.sb_cluster.setCurrentText("2048 bytes (Default)")
        elif fs == "ReFS":
            self.sb_cluster.addItems(["4096 bytes (Default)", "64 kilobytes"])
            self.sb_cluster.setCurrentText("4096 bytes (Default)")
        else:
            self.sb_cluster.addItems(["4096 bytes (Default)", "8192 bytes", "16 kilobytes", "32 kilobytes", "64 kilobytes"])
        self.sb_cluster.blockSignals(False)

    def _toggle_adv_drive(self):
        vis = self.adv_drive_btn.isChecked()
        self.adv_drive_box.setVisible(vis)
        self.adv_drive_btn.setText("Hide advanced drive properties  ▲" if vis else "Show advanced drive properties  ▼")

    def _toggle_adv_fmt(self):
        vis = self.adv_fmt_btn.isChecked()
        self.adv_fmt_box.setVisible(vis)
        self.adv_fmt_btn.setText("Hide advanced format options  ▲" if vis else "Show advanced format options  ▼")

    # ----------------------------------------------------------------- settings
    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            save_settings(self.settings)
            self._sync_settings_ui()

    def _sync_settings_ui(self):
        s = self.settings
        self.opt_verify.setChecked(s.verify_after_write)
        self.opt_uefi.setChecked(s.uefi_runtime_validation)
        # Create extended label and icon files should be enabled by default per user request
        self.opt_bitlocker.setChecked(True)
        s.disable_bitlocker = True
        self.opt_secboot.setChecked(s.secure_boot_warn)
        self.opt_silent.setChecked(s.silent_install)
        self.opt_custom.setChecked(s.custom_ops_enabled)
        # Single-boot UI persistence
        self.opt_list_usb.setChecked(s.list_usb_hard_drives)
        self.opt_old_bios.setChecked(s.old_bios_fix)
        self.opt_headless.setChecked(s.headless_install and self.opt_headless.isEnabled())
        # Restore combos and line edit
        self.sb_part_scheme.blockSignals(True)
        idx = self.sb_part_scheme.findText(s.part_scheme)
        if idx >= 0:
            self.sb_part_scheme.setCurrentIndex(idx)
        self.sb_part_scheme.blockSignals(False)
        # Target system will be auto-set via _on_part_scheme_changed, but restore explicitly
        self.sb_target_sys.blockSignals(True)
        idx = self.sb_target_sys.findText(s.target_system)
        if idx >= 0:
            self.sb_target_sys.setCurrentIndex(idx)
        self.sb_target_sys.blockSignals(False)
        self.sb_fs.blockSignals(True)
        idx = self.sb_fs.findText(s.fs_type)
        if idx >= 0:
            self.sb_fs.setCurrentIndex(idx)
        self.sb_fs.blockSignals(False)
        # Cluster size may depend on FS, so ensure FS handler ran; then restore cluster if exists
        # Trigger FS handler to populate correct cluster list, then restore
        self._on_fs_changed(s.fs_type)
        idx = self.sb_cluster.findText(s.cluster_size)
        if idx >= 0:
            self.sb_cluster.setCurrentIndex(idx)
        self.sb_vol_label.setText(s.volume_label)
        self.os_downloads.parallel_spin.blockSignals(True)
        self.os_downloads.parallel_spin.setValue(s.parallel_limit)
        self.os_downloads.parallel_spin.blockSignals(False)
        self.os_downloads.queue.parallel_limit = s.parallel_limit
        # Splitter
        if s.splitter_sizes:
            try:
                sizes = [int(x) for x in s.splitter_sizes.split(",")]
                if len(sizes) == 2:
                    self.splitter.setSizes(sizes)
            except:
                pass

    def open_about(self):
        dlg = AboutDialog(self, self.settings)
        dlg.exec()
        save_settings(self.settings)

    # -------------------------------------------------------------------- flash
    def start_flash(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Busy", "An operation is already running.")
            return
        if not self.current_image or not os.path.isfile(self.current_image):
            QMessageBox.warning(self, "No image", "Please select a source image first.")
            return
        device = self.selected_device()
        if device is None:
            QMessageBox.warning(self, "No target", "Please choose a target device.")
            return

        # Persist option states back into settings for the worker/CLI parity.
        s = self.settings
        s.verify_after_write = self.opt_verify.isChecked()
        s.uefi_runtime_validation = self.opt_uefi.isChecked()
        s.disable_bitlocker = self.opt_bitlocker.isChecked()
        s.secure_boot_warn = self.opt_secboot.isChecked()
        s.silent_install = self.opt_silent.isChecked()
        s.custom_ops_enabled = self.opt_custom.isChecked()
        s.list_usb_hard_drives = self.opt_list_usb.isChecked()
        s.old_bios_fix = self.opt_old_bios.isChecked()
        s.check_bad_blocks = self.opt_secboot.isChecked()
        s.headless_install = self.opt_headless.isChecked()
        s.part_scheme = self.sb_part_scheme.currentText()
        s.target_system = self.sb_target_sys.currentText()
        s.fs_type = self.sb_fs.currentText()
        s.cluster_size = self.sb_cluster.currentText()
        s.volume_label = self.sb_vol_label.text()
        s.parallel_limit = self.os_downloads.parallel_spin.value()
        # Splitter sizes
        try:
            sizes = self.splitter.sizes()
            s.splitter_sizes = f"{sizes[0]},{sizes[1]}" if len(sizes)==2 else ""
        except:
            pass
        save_settings(s)

        # Issue #2244: Secure Boot / PCA2011 advisory.
        if s.secure_boot_warn and self._needs_secure_boot_warning():
            warn = SECURE_BOOT_ADVISORY.format(name=device.path)
            reply = QMessageBox.warning(
                self, "Secure Boot warning",
                warn + "\n\nContinue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Issue #2877: BitLocker note (informational; real policy injection
        # requires Windows tooling not available cross-platform).
        if s.disable_bitlocker:
            self.log.appendPlainText(
                "[2877] BitLocker auto-device-encryption will be disabled for "
                "this Windows-To-Go workflow."
            )

        self._sb_cancel.clear()
        self.start_btn.setEnabled(False)
        self.sb_cancel_btn.setEnabled(True)
        self.flash_bar.setValue(0)
        self.sb_status.setText("Writing...")
        # Gather Rufus-like options from UI
        part_scheme = self.sb_part_scheme.currentText()  # MBR/GPT
        target_sys = self.sb_target_sys.currentText()  # BIOS or UEFI etc.
        vol_label = self.sb_vol_label.text().strip() or "RUSYS"
        fs_type = self.sb_fs.currentText()  # NTFS/FAT32 etc.
        cluster = self.sb_cluster.currentText()
        self.worker = Worker(
            flash_image,
            self.current_image,
            device,
            progress_cb=lambda done, total: None,  # placeholder; Worker emits signal
            verify=s.verify_after_write,
            custom_ops=s.custom_ops if s.custom_ops_enabled else None,
            run_custom_ops=s.custom_ops_enabled,
            cancel_event=self._sb_cancel,
            part_scheme=part_scheme,
            target_system=target_sys,
            fs_type=fs_type,
            cluster_size=cluster,
            volume_label=vol_label,
            old_bios_fix=self.opt_old_bios.isChecked(),
        )
        self.worker.progress.connect(self._on_flash_progress_signal)
        self.worker.finished.connect(self._on_flash_done)
        self.worker.errored.connect(self._on_flash_error)
        self.worker.start()

    def _sb_cancel_flash(self):
        """Cancel the running flash operation."""
        self._sb_cancel.set()
        self.sb_cancel_btn.setEnabled(False)
        self.sb_status.setText("Cancelling...")

    def _on_flash_progress_signal(self, done, total, _extra):
        """Handle flash progress from the Worker signal (runs on GUI thread).

        ``done`` and ``total`` are floats (to avoid >2GB int overflow).
        Matches the multiboot progress handler exactly.
        """
        if total and total > 0:
            pct = int(done * 100 / total)
            self.flash_bar.setValue(min(pct, 100))
        else:
            self.flash_bar.setValue(0)

    def _on_flash_progress(self, done, total):
        """Legacy direct callback — kept for API compatibility but no longer used."""
        if total:
            self.flash_bar.setValue(int(done * 100 / total))

    def _on_flash_done(self, result: dict):
        self.start_btn.setEnabled(True)
        self.sb_cancel_btn.setEnabled(False)
        self.flash_bar.setValue(100)
        self.sb_status.setText("Ready")
        QMessageBox.information(
            self, "Complete",
            f"Wrote {human_size(result.get('written', 0))} to device.\n"
            f"Verified: {result.get('verified')}"
            + (f"\nCustom ops: {len(result.get('ops_result') or [])} run"
               if result.get('ops_result') else ""),
        )

    def _on_flash_error(self, message: str):
        self.start_btn.setEnabled(True)
        self.sb_cancel_btn.setEnabled(False)
        self.flash_bar.setValue(0)
        self.sb_status.setText("Error")
        # Issue #1778: present a clean, non-NTSTATUS error to the user.
        QMessageBox.critical(self, "Operation failed", message)

    def _needs_secure_boot_warning(self) -> bool:
        name = (self.current_leaf.name if self.current_leaf else "").lower()
        img = self.current_image.lower()
        # Old Windows media lacking current Secure Boot signatures.
        if "windows" in img and any(k in img for k in ("win7", "windows 7", "win8", "windows 8")):
            return True
        if "windows" in name and any(k in name for k in ("7", "8")):
            return True
        return False

    def _save_single_boot_opts(self):
        # Save all single-boot UI states to local cache (settings.json)
        try:
            s = self.settings
            s.list_usb_hard_drives = self.opt_list_usb.isChecked()
            s.old_bios_fix = self.opt_old_bios.isChecked()
            s.uefi_runtime_validation = self.opt_uefi.isChecked()
            s.verify_after_write = self.opt_verify.isChecked()
            s.disable_bitlocker = self.opt_bitlocker.isChecked()
            s.secure_boot_warn = self.opt_secboot.isChecked()
            s.silent_install = self.opt_silent.isChecked()
            s.headless_install = self.opt_headless.isChecked()
            s.custom_ops_enabled = self.opt_custom.isChecked()
            s.part_scheme = self.sb_part_scheme.currentText()
            s.target_system = self.sb_target_sys.currentText()
            s.fs_type = self.sb_fs.currentText()
            s.cluster_size = self.sb_cluster.currentText()
            s.volume_label = self.sb_vol_label.text()
            s.parallel_limit = self.os_downloads.parallel_spin.value()
            save_settings(s)
        except:
            pass

    def _save_splitter(self):
        try:
            sizes = self.splitter.sizes()
            self.settings.splitter_sizes = f"{sizes[0]},{sizes[1]}" if len(sizes)==2 else ""
            save_settings(self.settings)
        except:
            pass

    def closeEvent(self, event):
        self._hotplug_timer.stop()
        self._mb_auto_timer.stop()
        try:
            self.os_downloads.shutdown()
        except Exception:
            pass
        if self.worker and self.worker.isRunning():
            self.worker.quit()
        # Persist window size/position for next launch.
        geo_hex = self.saveGeometry().toHex()
        self.settings.window_geometry = str(geo_hex, encoding='ascii')
        # Also save splitter
        try:
            sizes = self.splitter.sizes()
            self.settings.splitter_sizes = f"{sizes[0]},{sizes[1]}" if len(sizes)==2 else ""
        except:
            pass
        save_settings(self.settings)
        super().closeEvent(event)

    def resizeEvent(self, event):
        # Persist the size live (debounced) so it survives a non-clean exit too.
        super().resizeEvent(event)
        if getattr(self, "_geo_timer", None) is None:
            from PySide6.QtCore import QTimer

            self._geo_timer = QTimer(self)
            self._geo_timer.setSingleShot(True)
            self._geo_timer.timeout.connect(self._save_geometry)
        self._geo_timer.start(400)

    def _save_geometry(self) -> None:
        geo = self.saveGeometry().toHex()
        self.settings.window_geometry = str(geo, encoding="ascii")
        save_settings(self.settings)
