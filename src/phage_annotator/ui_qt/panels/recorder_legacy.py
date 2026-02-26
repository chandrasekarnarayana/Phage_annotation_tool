"""Lightweight action recorder for GUI events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets


@dataclass
class RecorderEntry:
    timestamp: str
    action: str
    params: Dict[str, object]


class ActionRecorder(QtCore.QObject):
    """Append-only action recorder with simple text serialization."""

    updated = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self.entries: List[RecorderEntry] = []

    def record(self, action: str, params: Optional[Dict[str, object]] = None) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = RecorderEntry(timestamp=ts, action=action, params=params or {})
        self.entries.append(entry)
        self.updated.emit()

    def to_text(self) -> str:
        lines = []
        for entry in self.entries:
            params = ", ".join(f"{k}={v}" for k, v in entry.params.items())
            lines.append(f"[{entry.timestamp}] {entry.action}({params})")
        return "\n".join(lines)

    def save_to_project(self, project_path: Path) -> Path:
        path = Path(project_path).with_suffix(".recorder.txt")
        path.write_text(self.to_text(), encoding="utf-8")
        return path

    def attach_actions(self, actions: Dict[str, QtWidgets.QAction]) -> None:
        """Hook QAction triggers to recorder entries."""
        for name, action in actions.items():
            action.triggered.connect(lambda _checked=False, n=name: self.record(n))


class RecorderWidget(QtWidgets.QWidget):
    """Recorder dock widget with copy/save controls."""

    def __init__(self, recorder: ActionRecorder, parent=None) -> None:
        super().__init__(parent)
        self.recorder = recorder
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        btn_row = QtWidgets.QHBoxLayout()
        self.copy_btn = QtWidgets.QPushButton("Copy")
        self.save_btn = QtWidgets.QPushButton("Save")
        btn_row.addWidget(self.copy_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.text = QtWidgets.QPlainTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

        self.recorder.updated.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        self.text.setPlainText(self.recorder.to_text())

    def copy_to_clipboard(self) -> None:
        QtWidgets.QApplication.clipboard().setText(self.recorder.to_text())
