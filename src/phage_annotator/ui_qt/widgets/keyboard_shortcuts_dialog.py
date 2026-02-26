"""Keyboard shortcuts reference dialog."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class KeyboardShortcutsDialog(QtWidgets.QDialog):
    """Dialog showing all keyboard shortcuts in a searchable table."""
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(700, 500)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Search box
        search_layout = QtWidgets.QHBoxLayout()
        search_label = QtWidgets.QLabel("Search:")
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("Type to filter shortcuts...")
        self.search_box.textChanged.connect(self._filter_shortcuts)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)
        
        # Shortcuts table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Shortcut", "Action", "Description"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Close button
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)
        
        self._populate_shortcuts()
        
    def _populate_shortcuts(self) -> None:
        """Populate table with all known shortcuts."""
        shortcuts = [
            ("Ctrl+Z", "Undo", "Undo last annotation change"),
            ("Ctrl+Shift+Z", "Redo", "Redo last undone annotation change"),
            ("Ctrl+M", "Measure", "Open measurement/results panel"),
            ("Ctrl+Shift+P", "Command Palette", "Open command palette"),
            ("1", "Annotate Tool", "Switch to annotation tool"),
            ("2", "Eraser Tool", "Switch to eraser tool"),
            ("3", "Pan/Zoom Tool", "Switch to pan/zoom tool"),
            ("4", "ROI Box Tool", "Switch to ROI box drawing tool"),
            ("5", "ROI Circle Tool", "Switch to ROI circle drawing tool"),
            ("6", "ROI Edit Tool", "Switch to ROI editing tool"),
            ("7", "Profile Line Tool", "Switch to line profile tool"),
            ("Space", "Play/Pause", "Toggle time series playback"),
            ("Left/Right", "Navigate Time", "Move backward/forward in time"),
            ("Up/Down", "Navigate Z", "Move up/down in Z-stack"),
            ("Shift+Left/Right", "Step 10 Frames", "Jump 10 frames backward/forward"),
            ("Ctrl+Scroll", "Zoom", "Zoom in/out on canvas"),
            ("Middle Click Drag", "Pan", "Pan canvas view"),
            ("Delete/Backspace", "Delete Point", "Delete selected annotation"),
            ("Escape", "Cancel", "Cancel current operation/tool"),
        ]
        
        self.table.setRowCount(len(shortcuts))
        for i, (shortcut, action, desc) in enumerate(shortcuts):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(shortcut))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(action))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(desc))
        
        # Resize columns to content
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 180)
        
    def _filter_shortcuts(self, text: str) -> None:
        """Filter table rows based on search text."""
        search_lower = text.lower()
        for row in range(self.table.rowCount()):
            # Search in all columns
            matches = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_lower in item.text().lower():
                    matches = True
                    break
            self.table.setRowHidden(row, not matches)
