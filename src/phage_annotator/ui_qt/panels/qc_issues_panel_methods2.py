"""Method group 2 split from qc_issues_panel.py."""

from __future__ import annotations

from typing import List, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity
from phage_annotator.session.qc_state import QCState


class _QCIssuesPanelMethods2:
    """Methods split from QCIssuesPanel."""

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

        message_label = QtWidgets.QLabel(issue.message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("padding: 5px 0;")
        layout.addWidget(message_label)

        details_layout = QtWidgets.QHBoxLayout()

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

        def click_handler(event):
            """Run the click handler workflow."""
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
