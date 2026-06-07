"""Extracted method group 1 for QCIssuesPanel."""

from __future__ import annotations

from typing import List, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity
from phage_annotator.session.qc_state import QCState



class QcissuesPanelUiMixin:
    """Method group 1 extracted from QCIssuesPanel."""

    def __init__(
        self,
        qc_state: Optional[QCState] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize QC issues panel.
        
        Parameters
        ----------
        qc_state : QCState, optional
            QC state object managing issues.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        
        self.qc_state = qc_state or QCState()
        self.issue_widgets: List[QtWidgets.QWidget] = []
        self.show_resolved = False
        self.show_ignored = False
        self._monitor = None
        
        self._setup_ui()
        self._update_issue_list()
    def _setup_ui(self) -> None:
        """Setup panel UI with issue list and controls."""
        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Summary header
        summary_layout = QtWidgets.QHBoxLayout()
        self.summary_label = QtWidgets.QLabel("No issues detected")
        self.summary_label.setStyleSheet("font-weight: bold; padding: 5px;")
        summary_layout.addWidget(self.summary_label)
        summary_layout.addStretch()
        
        # Monitor status widget (initially hidden)
        from phage_annotator.ui_qt.workers.qc_background_monitor import QCMonitorStatusWidget
        self.monitor_status = QCMonitorStatusWidget()
        self.monitor_status.hide()
        summary_layout.addWidget(self.monitor_status)
        
        # Validate button
        self.validate_btn = QtWidgets.QPushButton("Validate")
        self.validate_btn.setToolTip("Run QC validation on current annotations")
        self.validate_btn.clicked.connect(lambda: self.validation_requested.emit())
        summary_layout.addWidget(self.validate_btn)
        
        layout.addLayout(summary_layout)
        
        # Filter controls
        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel("Show:"))
        
        self.error_checkbox = QtWidgets.QCheckBox("Errors")
        self.error_checkbox.setChecked(self.qc_state.filters.get("error", True))
        self.error_checkbox.setStyleSheet("QCheckBox { color: #d32f2f; font-weight: bold; }")
        self.error_checkbox.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.error_checkbox)
        
        self.warning_checkbox = QtWidgets.QCheckBox("Warnings")
        self.warning_checkbox.setChecked(self.qc_state.filters.get("warning", True))
        self.warning_checkbox.setStyleSheet("QCheckBox { color: #f57c00; }")
        self.warning_checkbox.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.warning_checkbox)
        
        self.info_checkbox = QtWidgets.QCheckBox("Info")
        self.info_checkbox.setChecked(self.qc_state.filters.get("info", True))
        self.info_checkbox.setStyleSheet("QCheckBox { color: #0277bd; }")
        self.info_checkbox.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.info_checkbox)

        self.show_resolved_checkbox = QtWidgets.QCheckBox("Show Resolved")
        self.show_resolved_checkbox.setChecked(self.show_resolved)
        self.show_resolved_checkbox.setToolTip("Include issues marked as resolved")
        self.show_resolved_checkbox.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.show_resolved_checkbox)

        self.show_ignored_checkbox = QtWidgets.QCheckBox("Show Ignored")
        self.show_ignored_checkbox.setChecked(self.show_ignored)
        self.show_ignored_checkbox.setToolTip("Include issues marked as ignored")
        self.show_ignored_checkbox.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.show_ignored_checkbox)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Separator
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)
        
        # Issue list (scroll area)
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        self.issue_container = QtWidgets.QWidget()
        self.issue_layout = QtWidgets.QVBoxLayout(self.issue_container)
        self.issue_layout.setContentsMargins(0, 0, 0, 0)
        self.issue_layout.addStretch()
        
        self.scroll_area.setWidget(self.issue_container)
        layout.addWidget(self.scroll_area)
        
        # Export controls
        export_layout = QtWidgets.QHBoxLayout()
        export_layout.addWidget(QtWidgets.QLabel("Export:"))
        
        self.export_csv_btn = QtWidgets.QPushButton("CSV")
        self.export_csv_btn.clicked.connect(lambda: self.export_requested.emit("csv"))
        export_layout.addWidget(self.export_csv_btn)
        
        self.export_json_btn = QtWidgets.QPushButton("JSON")
        self.export_json_btn.clicked.connect(lambda: self.export_requested.emit("json"))
        export_layout.addWidget(self.export_json_btn)
        
        self.export_html_btn = QtWidgets.QPushButton("HTML")
        self.export_html_btn.clicked.connect(lambda: self.export_requested.emit("html"))
        export_layout.addWidget(self.export_html_btn)
        
        export_layout.addStretch()
        layout.addLayout(export_layout)
        
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(central_widget)
    def set_qc_state(self, qc_state: QCState) -> None:
        """Update QC state and refresh issues.
        
        Parameters
        ----------
        qc_state : QCState
            New QC state object.
        """
        self.qc_state = qc_state
        self._update_filter_checkboxes()
        self._update_issue_list()
    def _update_filter_checkboxes(self) -> None:
        """Sync filter checkboxes with QC state."""
        self.error_checkbox.blockSignals(True)
        self.warning_checkbox.blockSignals(True)
        self.info_checkbox.blockSignals(True)
        
        self.error_checkbox.setChecked(self.qc_state.filters.get("error", True))
        self.warning_checkbox.setChecked(self.qc_state.filters.get("warning", True))
        self.info_checkbox.setChecked(self.qc_state.filters.get("info", True))
        
        self.error_checkbox.blockSignals(False)
        self.warning_checkbox.blockSignals(False)
        self.info_checkbox.blockSignals(False)
    def _on_filter_changed(self) -> None:
        """Handle filter checkbox changes."""
        self.qc_state.set_filter("error", self.error_checkbox.isChecked())
        self.qc_state.set_filter("warning", self.warning_checkbox.isChecked())
        self.qc_state.set_filter("info", self.info_checkbox.isChecked())
        self.show_resolved = bool(self.show_resolved_checkbox.isChecked())
        self.show_ignored = bool(self.show_ignored_checkbox.isChecked())
        self._update_issue_list()
    def _update_issue_list(self) -> None:
        """Rebuild issue list based on current filters."""
        # Clear existing widgets
        while self.issue_layout.count() > 1:  # Keep the stretch
            item = self.issue_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.issue_widgets.clear()
        
        # Get visible issues
        visible_issues = self.qc_state.get_visible_issues(
            respect_filters=True,
            include_resolved=bool(self.show_resolved),
            include_ignored=bool(self.show_ignored),
            order_by_severity=True,
        )
        
        # Update summary
        total_issues = len(self.qc_state.issues)
        visible_count = len(visible_issues)
        resolved_count = len(
            [
                issue
                for issue in self.qc_state.issues
                if self.qc_state.get_issue_status(str(issue.issue_id)) == self.qc_state.STATUS_RESOLVED
            ]
        )
        ignored_count = len(
            [
                issue
                for issue in self.qc_state.issues
                if self.qc_state.get_issue_status(str(issue.issue_id)) == self.qc_state.STATUS_IGNORED
            ]
        )
        
        if total_issues == 0:
            self.summary_label.setText("No issues detected")
            self.summary_label.setStyleSheet("font-weight: bold; padding: 5px; color: #4caf50;")
        else:
            self.summary_label.setText(
                f"Open: {visible_count} / Total: {total_issues} "
                f"(Resolved: {resolved_count}, Ignored: {ignored_count})"
            )
            self.summary_label.setStyleSheet("font-weight: bold; padding: 5px;")
        
        # Create issue widgets
        for issue in visible_issues:
            issue_widget = self._create_issue_widget(issue)
            self.issue_layout.insertWidget(self.issue_layout.count() - 1, issue_widget)
            self.issue_widgets.append(issue_widget)
