# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Spreadsheet-style OS table for Rusys (issue 1688: full keyboard/mnemonic support)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..data.os_catalog import CatalogNode, ROOT, iter_leaves

_HEADERS = ("Operating System", "Size", "Latest Update")


def _size(node: CatalogNode) -> str:
    gb = node.size_gb or 0
    return f"{gb:g} GB"


def _downloads(node: CatalogNode) -> str:
    """Compact download-count formatting (kept for tooltip, column hidden)."""
    n = node.downloads or 0
    if n >= 1_000_000:
        return f"{n / 1_000_000:g}M"
    if n >= 1_000:
        return f"{n / 1_000:g}K"
    return str(n)


def _downloads_full(node: CatalogNode) -> str:
    return f"{node.downloads:,}"


class CatalogWidget(QWidget):
    """A spreadsheet-like, sortable table of every OS in the catalogue.

    Columns: Operating System | Compatibility | Size | Latest Update.
    Clicking a row selects that OS for download/flash.
    """

    leaf_selected = Signal(object)  # CatalogNode

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._rows: list = []  # parallel list of (node, QTableWidgetItem row 0 item)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search operating systems... (e.g. Ubuntu, Tails)")
        self.search.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self.table)

        self._build()

    def _build(self):
        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)
        self._rows = []
        for node in iter_leaves(ROOT):
            row = self.table.rowCount()
            self.table.insertRow(row)
            name = QTableWidgetItem(node.name)
            name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            size = QTableWidgetItem(_size(node))
            date = QTableWidgetItem(node.latest_update)
            size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            date.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # Keep downloads in tooltip on name for reference, but hidden column for space
            name.setToolTip(
                f"{node.notes}\nApprox. downloads: {_downloads_full(node)}\nSize: {_size(node)}"
            )
            for item in (name, size, date):
                item.setData(Qt.UserRole, node)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, size)
            self.table.setItem(row, 2, date)
            self._rows.append((node, name))
        self.table.setSortingEnabled(True)

    def _on_selection(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.table.item(rows[0].row(), 0)
        node = item.data(Qt.UserRole) if item else None
        if node is not None:
            self.leaf_selected.emit(node)

    def _apply_filter(self, text: str):
        text = text.strip().lower()
        for node, name_item in self._rows:
            match = (not text) or (text in node.name.lower()) or (node.notes and text in node.notes.lower())
            self.table.setRowHidden(name_item.row(), not match)
