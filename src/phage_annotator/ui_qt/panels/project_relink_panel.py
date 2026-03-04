"""Right-dock panel for project image relink results and retry actions."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class ProjectRelinkPanel(QtWidgets.QWidget):
    """Displays relink summary and lets user retry auto/manual relinking."""

    retry_auto_requested = QtCore.Signal()
    retry_manual_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("project_relink_panel")
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        title = QtWidgets.QLabel("Project Relink")
        title.setStyleSheet("font-weight: 600;")
        root.addWidget(title)

        self.summary_lbl = QtWidgets.QLabel("No relink activity.")
        self.summary_lbl.setWordWrap(True)
        root.addWidget(self.summary_lbl)

        self.relinked_group = QtWidgets.QGroupBox("Relinked")
        relinked_layout = QtWidgets.QVBoxLayout(self.relinked_group)
        relinked_layout.setContentsMargins(6, 6, 6, 6)
        self.relinked_list = QtWidgets.QListWidget()
        self.relinked_list.setObjectName("project_relink_relinked_list")
        self.relinked_list.setMinimumHeight(100)
        relinked_layout.addWidget(self.relinked_list)
        root.addWidget(self.relinked_group)

        self.unresolved_group = QtWidgets.QGroupBox("Unresolved")
        unresolved_layout = QtWidgets.QVBoxLayout(self.unresolved_group)
        unresolved_layout.setContentsMargins(6, 6, 6, 6)
        self.unresolved_table = QtWidgets.QTableWidget(0, 2)
        self.unresolved_table.setObjectName("project_relink_unresolved_table")
        self.unresolved_table.setHorizontalHeaderLabels(["Image", "Original Path"])
        self.unresolved_table.verticalHeader().setVisible(False)
        self.unresolved_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.unresolved_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.unresolved_table.horizontalHeader().setStretchLastSection(True)
        self.unresolved_table.setMinimumHeight(120)
        unresolved_layout.addWidget(self.unresolved_table)
        root.addWidget(self.unresolved_group)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.retry_auto_btn = QtWidgets.QPushButton("Retry Auto-Relink")
        self.retry_manual_btn = QtWidgets.QPushButton("Manual Link Missing…")
        btn_row.addWidget(self.retry_auto_btn)
        btn_row.addWidget(self.retry_manual_btn)
        root.addLayout(btn_row)

        self.retry_auto_btn.clicked.connect(self.retry_auto_requested.emit)
        self.retry_manual_btn.clicked.connect(self.retry_manual_requested.emit)
        self.set_report({})

    def set_report(self, report: dict) -> None:
        relinked = list(report.get("relinked", []) or [])
        unresolved = list(report.get("unresolved", []) or [])
        loaded = int(report.get("loaded_count", 0))
        self.summary_lbl.setText(
            f"Loaded {loaded} image(s). Relinked: {len(relinked)} | Unresolved: {len(unresolved)}"
        )
        self.relinked_list.clear()
        self.relinked_list.addItems([str(v) for v in relinked])
        self.relinked_group.setVisible(bool(relinked))
        self.unresolved_table.setRowCount(len(unresolved))
        for row, item in enumerate(unresolved):
            self.unresolved_table.setItem(
                row, 0, QtWidgets.QTableWidgetItem(str(item.get("image_name", "")))
            )
            self.unresolved_table.setItem(
                row, 1, QtWidgets.QTableWidgetItem(str(item.get("original_path", "")))
            )
        self.unresolved_group.setVisible(bool(unresolved))
        has_unresolved = bool(unresolved)
        self.retry_auto_btn.setEnabled(has_unresolved)
        self.retry_manual_btn.setEnabled(has_unresolved)
