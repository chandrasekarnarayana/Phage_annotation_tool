"""Metadata viewer dock for raw and parsed image metadata."""

from __future__ import annotations

import json
from typing import Any, Dict

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class MetadataDock(QtWidgets.QWidget):
    """Viewer widget for TIFF/OME metadata with search and raw view."""

    load_full_requested = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search metadata…")
        self.load_btn = QtWidgets.QPushButton("Load full metadata")
        self.copy_btn = QtWidgets.QPushButton("Copy metadata")
        self.save_btn = QtWidgets.QPushButton("Save metadata as JSON")
        top_row.addWidget(self.search_edit)
        top_row.addWidget(self.load_btn)
        top_row.addWidget(self.copy_btn)
        top_row.addWidget(self.save_btn)
        layout.addLayout(top_row)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Key", "Value"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.raw_text = QtWidgets.QPlainTextEdit()
        self.raw_text.setReadOnly(True)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.raw_text)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        self._bundle = None
        self.search_edit.textChanged.connect(self._filter_tree)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        self.load_btn.clicked.connect(self.load_full_requested.emit)
        self.copy_btn.clicked.connect(self._copy_metadata)
        self.save_btn.clicked.connect(self._save_metadata)

    def set_bundle(self, bundle: object) -> None:
        """Update the tree and raw viewer from a MetadataBundle-like object."""
        self._bundle = bundle
        self.tree.clear()
        self.raw_text.clear()
        if not bundle:
            self.tree.addTopLevelItem(QtWidgets.QTreeWidgetItem(["Summary", "No metadata found"]))
            return
        sections = _bundle_to_sections(bundle)
        for section, value in sections.items():
            item = QtWidgets.QTreeWidgetItem([section, ""])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, value)
            self.tree.addTopLevelItem(item)
            _populate_tree(item, value)
        self.tree.expandToDepth(1)

    def _on_tree_selection(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, QtCore.Qt.ItemDataRole.UserRole)
        self.raw_text.setPlainText(_pretty_text(data))

    def _filter_tree(self, text: str) -> None:
        text = text.lower().strip()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            _filter_item(item, text)

    def _copy_metadata(self) -> None:
        data = _bundle_to_sections(self._bundle) if self._bundle else {}
        QtWidgets.QApplication.clipboard().setText(_pretty_text(data))

    def _save_metadata(self) -> None:
        if self._bundle is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save metadata as JSON",
            "metadata.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        data = _bundle_to_sections(self._bundle)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, default=str)


def _bundle_to_sections(bundle: object) -> Dict[str, Any]:
    if bundle is None:
        return {}
    sections: Dict[str, Any] = {}
    summary = getattr(bundle, "summary", None)
    if summary is not None:
        sections["Summary"] = summary
    sections["TIFF Tags"] = getattr(bundle, "tiff_tags", {}) or {}
    sections["OME XML"] = getattr(bundle, "ome_xml", None) or ""
    sections["OME Parsed"] = getattr(bundle, "ome_parsed", {}) or {}
    sections["Micro-Manager"] = getattr(bundle, "micromanager", {}) or {}
    sections["Vendor Private"] = getattr(bundle, "vendor_private", {}) or {}
    return sections


def _populate_tree(parent: QtWidgets.QTreeWidgetItem, value: object) -> None:
    if isinstance(value, dict):
        for key, val in value.items():
            child = QtWidgets.QTreeWidgetItem([str(key), _summary_value(val)])
            child.setData(0, QtCore.Qt.ItemDataRole.UserRole, val)
            parent.addChild(child)
            _populate_tree(child, val)
    elif isinstance(value, (list, tuple)):
        for idx, val in enumerate(value):
            child = QtWidgets.QTreeWidgetItem([f"[{idx}]", _summary_value(val)])
            child.setData(0, QtCore.Qt.ItemDataRole.UserRole, val)
            parent.addChild(child)
            _populate_tree(child, val)


def _summary_value(val: object) -> str:
    if isinstance(val, dict):
        return f"{len(val)} keys"
    if isinstance(val, (list, tuple)):
        return f"{len(val)} items"
    if isinstance(val, str):
        return val if len(val) <= 64 else f"{val[:61]}..."
    return str(val)


def _pretty_text(data: object) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    try:
        return json.dumps(data, indent=2, default=str)
    except TypeError:
        return str(data)


def _filter_item(item: QtWidgets.QTreeWidgetItem, text: str) -> bool:
    if not text:
        item.setHidden(False)
        for i in range(item.childCount()):
            _filter_item(item.child(i), text)
        return True
    match = text in item.text(0).lower() or text in item.text(1).lower()
    child_match = False
    for i in range(item.childCount()):
        if _filter_item(item.child(i), text):
            child_match = True
    visible = match or child_match
    item.setHidden(not visible)
    return visible
