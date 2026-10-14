# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Settings dialog for Rusys (issues #3003, #2877, #2244, #3008, #322)."""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.privileges import install_udev_rule, is_udev_rule_installed
from ..core.settings import Settings, save_settings


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Rusys - Settings")
        self.setMinimumWidth(560)
        self.settings = settings

        layout = QVBoxLayout(self)

        # --- General ---
        gen = QGroupBox("General")
        gv = QVBoxLayout(gen)
        self.verify = QCheckBox("Verify media after writing (recommended)")
        self.verify.setChecked(settings.verify_after_write)
        gv.addWidget(self.verify)

        self.download_dir_edit = QLineEdit(settings.download_dir)
        self.download_dir_edit.setPlaceholderText("Download folder (empty = system default)")
        browse = QDialogButtonBox()
        dbtn = browse.addButton("Browse...", QDialogButtonBox.ButtonRole.ActionRole)
        dbtn.clicked.connect(self._browse_dir)
        drow = QHBoxLayout()
        drow.addWidget(QLabel("Downloads:"))
        drow.addWidget(self.download_dir_edit)
        drow.addWidget(dbtn)
        gv.addLayout(drow)
        layout.addWidget(gen)

        # --- Issue #3003: runtime UEFI media validation (opt-in) ---
        uefi = QGroupBox("UEFI media validation")
        uv = QVBoxLayout(uefi)
        self.uefi = QCheckBox("Enable runtime UEFI media validation")
        self.uefi.setChecked(settings.uefi_runtime_validation)
        self.uefi.setToolTip(
            "OFF by default. Forcing this ON with Ubuntu 24.04/26.04 ISOs "
            "can break the installer."
        )
        uv.addWidget(self.uefi)
        uv.addWidget(QLabel(
            "Note: this option is disabled automatically when an Ubuntu image "
            "is selected, unless you explicitly override it."
        ))
        layout.addWidget(uefi)

        # --- Issue #2877: disable BitLocker auto encryption ---
        bit = QGroupBox("Windows To Go")
        bv = QVBoxLayout(bit)
        self.bitlocker = QCheckBox("Disable BitLocker automatic device encryption")
        self.bitlocker.setChecked(settings.disable_bitlocker)
        bv.addWidget(self.bitlocker)
        layout.addWidget(bit)

        # --- Issue #2244: Secure Boot revocation warning ---
        sb = QGroupBox("Secure Boot")
        sv = QVBoxLayout(sb)
        self.secboot = QCheckBox("Warn if media may not boot via Secure Boot (PCA2011)")
        self.secboot.setChecked(settings.secure_boot_warn)
        sv.addWidget(self.secboot)
        layout.addWidget(sb)

        # --- Issue #3008: silent install ---
        si = QGroupBox("Windows setup")
        sv2 = QVBoxLayout(si)
        self.silent = QCheckBox("Use silent/unattended install defaults when supported")
        self.silent.setChecked(settings.silent_install)
        sv2.addWidget(self.silent)
        sv2.addWidget(QLabel(
            "The option is fully enabled/disabled (never left in a hidden but "
            "active half-state) and is greyed out when the selected image does "
            "not support it."
        ))
        layout.addWidget(si)

        # --- Issue #322: custom file operations ---
        co = QGroupBox("Custom file operations")
        cv = QVBoxLayout(co)
        self.co_enabled = QCheckBox("Run custom operations after writing")
        self.co_enabled.setChecked(settings.custom_ops_enabled)
        cv.addWidget(self.co_enabled)
        self.co_text = QPlainTextEdit("\n".join(settings.custom_ops))
        self.co_text.setPlaceholderText(
            "One shell command per line. The image and target paths are provided "
            "to your command as environment variables."
        )
        cv.addWidget(self.co_text)
        layout.addWidget(co)

        # --- USB Access ---
        usb = QGroupBox("USB Device Access")
        uv = QVBoxLayout(usb)
        self._udev_label = QLabel()
        uv.addWidget(self._udev_label)
        self._udev_btn = QPushButton("Install USB Rules")
        self._udev_btn.clicked.connect(self._install_udev_rules)
        uv.addWidget(self._udev_btn)
        self._update_udev_label()
        uv.addWidget(QLabel(
            "Installs a udev rule that grants write access to USB block "
            "devices. After installation, log out and back in (or run "
            "`newgrp disk`) for the change to take effect."
        ))
        layout.addWidget(usb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select download folder")
        if path:
            self.download_dir_edit.setText(path)

    def _accept(self):
        s = self.settings
        s.verify_after_write = self.verify.isChecked()
        s.download_dir = self.download_dir_edit.text().strip()
        s.uefi_runtime_validation = self.uefi.isChecked()
        s.disable_bitlocker = self.bitlocker.isChecked()
        s.secure_boot_warn = self.secboot.isChecked()
        s.silent_install = self.silent.isChecked()
        s.custom_ops_enabled = self.co_enabled.isChecked()
        s.custom_ops = [
            line.strip()
            for line in self.co_text.toPlainText().splitlines()
            if line.strip()
        ]
        save_settings(s)
        self.accept()

    def _update_udev_label(self):
        if is_udev_rule_installed():
            self._udev_label.setText("✅ USB udev rule is installed")
            self._udev_btn.setEnabled(False)
        else:
            self._udev_label.setText("⚠ USB udev rule is NOT installed — writing to USB requires sudo/pkexec")
            self._udev_btn.setEnabled(True)

    def _install_udev_rules(self):
        if install_udev_rule():
            QMessageBox.information(
                self, "USB Rules Installed",
                "The udev rule was installed successfully.\n\n"
                "Please log out and log back in (or run `newgrp disk` "
                "in a terminal) for the group membership to take effect.",
            )
            self._update_udev_label()
        else:
            QMessageBox.warning(
                self, "Installation Failed",
                "The udev rule could not be installed.  The pkexec "
                "prompt may have been cancelled, or polkit is not "
                "available on this system.\n\n"
                "You can install it manually:\n"
                "  sudo cp 99-rusys-usb.rules /etc/udev/rules.d/\n"
                "  sudo udevadm control --reload-rules\n"
                "  sudo udevadm trigger\n"
                "  sudo usermod -aG disk $USER",
            )
