"""QC issues panel for quality-control and problem review workflows.

Displays quality control issues detected by validators with filtering
and click-to-jump navigation.
"""

from __future__ import annotations

from typing import List, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity
from phage_annotator.session.qc_state import QCState


class QCIssuesPanel(QtWidgets.QWidget):
    """Dock widget panel displaying QC issues with filtering and navigation.
    
    Provides issue browsing, severity-based filtering, and click-to-jump
    navigation to annotation locations.
    """
    
    # Signals
    jump_to_location = QtCore.Signal(float, float, int, int, int)  # x, y, z, t, image_id
    issue_clicked = QtCore.Signal(str)  # issue_id
    issue_status_changed = QtCore.Signal(str, str)  # issue_id, status
    validation_requested = QtCore.Signal()  # Request re-validation
    export_requested = QtCore.Signal(str)  # Export format: "csv", "json", "html"
    
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
    
    def _create_issue_widget(self, issue: QCIssue) -> QtWidgets.QWidget:
        """Create widget for a single issue.
        
        Parameters
        ----------
        issue : QCIssue
            Issue to display.
        
        Returns
        -------
        QWidget
            Issue display widget.
        """
        widget = QtWidgets.QFrame()
        widget.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        widget.setCursor(QtCore.Qt.PointingHandCursor)
        
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Header with severity badge
        header_layout = QtWidgets.QHBoxLayout()
        
        severity_badge = QtWidgets.QLabel(issue.severity.value.upper())
        severity_badge.setAlignment(QtCore.Qt.AlignCenter)
        severity_badge.setFixedSize(70, 20)
        
        if issue.severity == IssueSeverity.ERROR:
            severity_badge.setStyleSheet(
                "background-color: #d32f2f; color: white; font-weight: bold; "
                "border-radius: 3px; padding: 2px;"
            )
        elif issue.severity == IssueSeverity.WARNING:
            severity_badge.setStyleSheet(
                "background-color: #f57c00; color: white; font-weight: bold; "
                "border-radius: 3px; padding: 2px;"
            )
        else:  # INFO
            severity_badge.setStyleSheet(
                "background-color: #0277bd; color: white; font-weight: bold; "
                "border-radius: 3px; padding: 2px;"
            )
        
        header_layout.addWidget(severity_badge)
        
        type_label = QtWidgets.QLabel(issue.issue_type.replace("_", " ").title())
        type_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(type_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Message
        message_label = QtWidgets.QLabel(issue.message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("padding: 5px 0;")
        layout.addWidget(message_label)
        
        # Details
        details_layout = QtWidgets.QHBoxLayout()
        
        # Location info
        if issue.location_x is not None and issue.location_y is not None:
            location_text = f"📍 ({issue.location_x:.1f}, {issue.location_y:.1f}"
            if issue.location_z is not None and issue.location_z > 0:
                location_text += f", z={issue.location_z}"
            if issue.location_t is not None and issue.location_t > 0:
                location_text += f", t={issue.location_t}"
            location_text += ")"
            
            location_label = QtWidgets.QLabel(location_text)
            location_label.setStyleSheet("font-size: 10px; color: #666;")
            details_layout.addWidget(location_label)
        
        details_layout.addStretch()
        
        # Affected count
        affected_count = len(issue.affected_annotation_ids)
        if affected_count > 0:
            affected_label = QtWidgets.QLabel(f"{affected_count} annotation(s)")
            affected_label.setStyleSheet("font-size: 10px; color: #666;")
            details_layout.addWidget(affected_label)
        
        layout.addLayout(details_layout)

        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.addStretch()

        resolve_btn = QtWidgets.QPushButton("Resolve")
        resolve_btn.setToolTip("Mark this issue as resolved")
        resolve_btn.clicked.connect(
            lambda _checked=False, issue_id=str(issue.issue_id): self._set_issue_status(
                issue_id, self.qc_state.STATUS_RESOLVED
            )
        )
        actions_layout.addWidget(resolve_btn)

        ignore_btn = QtWidgets.QPushButton("Ignore")
        ignore_btn.setToolTip("Ignore this issue for now")
        ignore_btn.clicked.connect(
            lambda _checked=False, issue_id=str(issue.issue_id): self._set_issue_status(
                issue_id, self.qc_state.STATUS_IGNORED
            )
        )
        actions_layout.addWidget(ignore_btn)

        layout.addLayout(actions_layout)
        
        # Make entire widget clickable
        def click_handler(event):
            if issue.location_x is not None and issue.location_y is not None:
                z = issue.location_z if issue.location_z is not None else 0
                t = issue.location_t if issue.location_t is not None else 0
                try:
                    image_id = int(issue.image_id)
                except Exception:
                    image_id = -1
                self.jump_to_location.emit(issue.location_x, issue.location_y, z, t, image_id)
                self.issue_clicked.emit(issue.issue_id)
        
        widget.mousePressEvent = click_handler
        
        return widget

    def _set_issue_status(self, issue_id: str, status: str) -> None:
        """Update issue status and refresh list."""
        if not self.qc_state.set_issue_status(str(issue_id), str(status)):
            return
        self.issue_status_changed.emit(str(issue_id), str(status))
        self._update_issue_list()
    
    def refresh(self) -> None:
        """Refresh issue display (call after QC state changes)."""
        self._update_issue_list()
    
    def get_issue_count(self) -> int:
        """Get total number of issues.
        
        Returns
        -------
        int
            Total issue count.
        """
        return len(self.qc_state.issues)
    
    def get_visible_issue_count(self) -> int:
        """Get number of visible issues (after filtering).
        
        Returns
        -------
        int
            Visible issue count.
        """
        return len(self.qc_state.get_visible_issues())
    def set_monitor(self, monitor) -> None:
        """Set the background QC monitor.
        
        Parameters
        ----------
        monitor : QCBackgroundMonitor
            Background monitor instance.
        """
        self._monitor = monitor
        if monitor is not None:
            monitor.monitoring_started.connect(self._on_monitor_started)
            monitor.monitoring_stopped.connect(self._on_monitor_stopped)
    
    def set_monitor_status(self, message: str) -> None:
        """Update monitor status display.
        
        Parameters
        ----------
        message : str
            Status message to display.
        """
        if self.monitor_status is not None:
            self.monitor_status.set_status(message)
    
    def _on_monitor_started(self) -> None:
        """Called when background monitor starts."""
        if self.monitor_status is not None:
            self.monitor_status.set_monitoring_active(True)
    
    def _on_monitor_stopped(self) -> None:
        """Called when background monitor stops."""
        if self.monitor_status is not None:
            self.monitor_status.set_monitoring_active(False)