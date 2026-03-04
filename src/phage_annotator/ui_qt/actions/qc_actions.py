"""QC workflow actions."""

from __future__ import annotations

import pathlib
import time
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class QCActionsMixin:
    """Quality-control issue validation, navigation, and export actions."""

    def _ensure_qc_runtime(self) -> None:
        """Ensure QC state and timer are initialized."""
        if getattr(self, "qc_state", None) is None:
            from phage_annotator.session.qc_state import QCState

            self.qc_state = QCState()
        if getattr(self, "_qc_validation_timer", None) is None:
            self._qc_pending_image_id: Optional[int] = None
            self._qc_validation_timer = QtCore.QTimer(self)
            self._qc_validation_timer.setSingleShot(True)
            self._qc_validation_timer.setInterval(250)
            self._qc_validation_timer.timeout.connect(self._execute_scheduled_qc_validation)
        if getattr(self, "_qc_background_monitor", None) is None:
            from phage_annotator.ui_qt.workers.qc_background_monitor import QCBackgroundMonitor
            
            self._qc_background_monitor = QCBackgroundMonitor()
            self._qc_background_monitor.set_validation_callback(
                lambda: self._trigger_qc_validation()
            )
            self._qc_background_monitor.status_changed.connect(self._on_qc_monitor_status_changed)
            self._qc_background_monitor.set_enabled(self.qc_state.auto_monitor_enabled)
            self._qc_background_monitor.start()
        if getattr(self, "qc_issues_panel", None) is not None:
            if self.qc_issues_panel.qc_state is not self.qc_state:
                self.qc_issues_panel.set_qc_state(self.qc_state)
            if getattr(self, "_qc_background_monitor", None) is not None:
                self.qc_issues_panel.set_monitor(self._qc_background_monitor)
        
        # Wire monitor to annotation changes
        if getattr(self, "controller", None) is not None:
            if not getattr(self, "_qc_annotations_changed_wired", False):
                self.controller.annotations_changed.connect(self._on_qc_annotations_changed)
                self._qc_annotations_changed_wired = True

    def _schedule_qc_validation(self, image_id: Optional[int] = None) -> None:
        """Schedule debounced QC validation."""
        self._ensure_qc_runtime()
        if image_id is None:
            self._qc_pending_image_id = None
        elif getattr(self, "_qc_pending_image_id", None) is not None:
            if self._qc_pending_image_id != image_id:
                self._qc_pending_image_id = None
        else:
            self._qc_pending_image_id = int(image_id)
        self._qc_validation_timer.start()

    def _execute_scheduled_qc_validation(self) -> None:
        """Run any queued debounced QC validation."""
        image_id = getattr(self, "_qc_pending_image_id", None)
        self._qc_pending_image_id = None
        self._run_qc_validation(image_id=image_id)

    def _trigger_qc_validation(self) -> None:
        """Run QC validation immediately for all loaded images."""
        self._ensure_qc_runtime()
        if getattr(self, "_qc_validation_timer", None) is not None:
            self._qc_validation_timer.stop()
        self._qc_pending_image_id = None
        self._run_qc_validation(image_id=None)

    def _run_qc_validation(self, image_id: Optional[int]) -> None:
        """Compute QC issues and refresh the QC issues panel."""
        from phage_annotator.analysis.qc_validators import QCValidator

        self._ensure_qc_runtime()

        if image_id is None:
            targets = [img.id for img in self.images]
            self.qc_state.clear_issues()
        else:
            targets = [int(image_id)]
            self.qc_state.issues = [
                issue for issue in self.qc_state.issues if int(issue.image_id) != int(image_id)
            ]
            self.qc_state.prune_issue_statuses()

        allowed_labels = list(self.labels) if self.labels else None

        for target_id in targets:
            image = next((img for img in self.images if img.id == target_id), None)
            if image is None:
                continue

            annotations = list(self.annotations.get(target_id, []))
            image_shape = None
            array = getattr(image, "array", None)
            if array is not None and getattr(array, "ndim", 0) >= 4:
                image_shape = (int(array.shape[2]), int(array.shape[3]))
            else:
                shape = getattr(image, "shape", ())
                if len(shape) >= 2:
                    image_shape = (int(shape[-2]), int(shape[-1]))

            issues = QCValidator.validate(
                annotations,
                image_id=target_id,
                image_shape=image_shape,
                image_array=array,
                allowed_labels=allowed_labels,
            )
            for issue in issues:
                self.qc_state.add_issue(issue)

        self.qc_state.validation_timestamp = time.time()
        if not hasattr(self, "_qc_issue_cursor"):
            self._qc_issue_cursor = -1
        self._qc_issue_cursor = -1
        if getattr(self, "qc_issues_panel", None) is not None:
            self.qc_issues_panel.set_qc_state(self.qc_state)
            self.qc_issues_panel.refresh()
        issue_count = int(len(self.qc_state.issues))
        open_count = int(
            len(
                self.qc_state.get_visible_issues(
                    respect_filters=False,
                    ignore_filters=True,
                    include_resolved=False,
                    include_ignored=False,
                )
            )
        )
        self._update_qc_button_highlight(open_count)
        dock_qc = getattr(self, "dock_qc_issues", None)
        if dock_qc is not None:
            dock_qc.setWindowTitle(f"QC Issues ({open_count})" if open_count > 0 else "QC Issues")
            if open_count > 0 and bool(self._settings.value("qcAutoShowOnIssues", True, type=bool)):
                self.set_panel_visible("qc_issues", True, source="qc_validation")
                dock_qc.raise_()
        issue_counts_by_type: dict[str, int] = {}
        for issue in self.qc_state.issues:
            key = str(getattr(issue, "issue_type", "unknown"))
            issue_counts_by_type[key] = issue_counts_by_type.get(key, 0) + 1
        self.controller.append_audit_event(
            "qc_validation_completed",
            image_id=(-1 if image_id is None else int(image_id)),
            total_issues=len(self.qc_state.issues),
            issue_counts_by_type=issue_counts_by_type,
        )

        self._set_status(f"QC validation complete: {len(self.qc_state.issues)} issue(s).")
        self._update_status()

    def _on_qc_issue_status_changed(self, issue_id: str, status: str) -> None:
        """Handle resolve/ignore actions from QC panel."""
        self._ensure_qc_runtime()
        open_count = int(
            len(
                self.qc_state.get_visible_issues(
                    respect_filters=False,
                    ignore_filters=True,
                    include_resolved=False,
                    include_ignored=False,
                )
            )
        )
        self._update_qc_button_highlight(open_count)
        dock_qc = getattr(self, "dock_qc_issues", None)
        if dock_qc is not None:
            dock_qc.setWindowTitle(f"QC Issues ({open_count})" if open_count > 0 else "QC Issues")
        self._set_status(f"QC issue {issue_id} marked {status}.")
        self._update_status()

    def _on_qc_monitor_status_changed(self, message: str) -> None:
        """Handle status updates from background monitor."""
        qc_panel = getattr(self, "qc_issues_panel", None)
        if qc_panel is not None:
            qc_panel.set_monitor_status(message)

    def _on_qc_annotations_changed(self) -> None:
        """Handle annotation changes: trigger monitor."""
        self._ensure_qc_runtime()
        if getattr(self, "_qc_background_monitor", None) is not None:
            self._qc_background_monitor.on_annotation_changed()

    def _on_qc_image_changed(self) -> None:
        """Handle image change: trigger QC monitor to scan new image."""
        self._ensure_qc_runtime()
        if getattr(self, "_qc_background_monitor", None) is not None:
            self._qc_background_monitor.on_image_loaded()

    def _jump_to_next_qc_issue(self) -> None:
        """Jump to the next visible QC issue in round-robin order."""
        self._ensure_qc_runtime()
        visible = list(self.qc_state.get_visible_issues(respect_filters=True))
        if not visible:
            self._set_status("No QC issues to review.")
            self._update_status()
            return
        cursor = int(getattr(self, "_qc_issue_cursor", -1))
        cursor = (cursor + 1) % len(visible)
        self._qc_issue_cursor = cursor
        issue = visible[cursor]
        x = float(getattr(issue, "location_x", 0.0) if getattr(issue, "location_x", None) is not None else 0.0)
        y = float(getattr(issue, "location_y", 0.0) if getattr(issue, "location_y", None) is not None else 0.0)
        z = int(getattr(issue, "location_z", 0) if getattr(issue, "location_z", None) is not None else 0)
        t = int(getattr(issue, "location_t", 0) if getattr(issue, "location_t", None) is not None else 0)
        image_id = int(getattr(issue, "image_id", self.current_image_idx))
        self._jump_to_qc_issue(x, y, z, t, image_id)
        self._set_status(
            f"QC issue {cursor + 1}/{len(visible)}: {str(getattr(issue, 'issue_type', 'issue'))}."
        )
        self._update_status()

    def _jump_to_qc_issue(self, x: float, y: float, z: int, t: int, image_id: int) -> None:
        """Navigate to an issue location from the QC issues panel."""
        if image_id != self.current_image_idx:
            target_row = next(
                (idx for idx, img in enumerate(self.images) if int(getattr(img, "id", -1)) == int(image_id)),
                None,
            )
            if target_row is not None:
                self._set_fov(int(target_row))

        if hasattr(self, "t_slider"):
            clamped_t = max(self.t_slider.minimum(), min(int(t), self.t_slider.maximum()))
            if self.t_slider.value() != clamped_t:
                self.t_slider.setValue(clamped_t)
        if hasattr(self, "z_slider"):
            clamped_z = max(self.z_slider.minimum(), min(int(z), self.z_slider.maximum()))
            if self.z_slider.value() != clamped_z:
                self.z_slider.setValue(clamped_z)

        frame_ax = self.renderer.axes.get("frame") if getattr(self, "renderer", None) is not None else None
        if frame_ax is not None:
            cx, cy = self._to_display_coords(frame_ax, float(x), float(y))
            xlim = frame_ax.get_xlim()
            ylim = frame_ax.get_ylim()
            width = abs(float(xlim[1] - xlim[0]))
            height = abs(float(ylim[1] - ylim[0]))
            frame_ax.set_xlim(cx - width / 2.0, cx + width / 2.0)
            if float(ylim[0]) > float(ylim[1]):
                frame_ax.set_ylim(cy + height / 2.0, cy - height / 2.0)
            else:
                frame_ax.set_ylim(cy - height / 2.0, cy + height / 2.0)

        self._refresh_image()
        self._set_status("Jumped to QC issue location.")
        self._update_status()

    def _export_qc_report(self, export_format: str) -> None:
        """Export QC issues in machine-readable format."""
        from phage_annotator.io.qc_export import QCReportExporter

        self._ensure_qc_runtime()
        issues = list(self.qc_state.issues)
        if not issues:
            QtWidgets.QMessageBox.information(self, "Export QC Report", "No QC issues to export.")
            return

        filters = {
            "csv": "CSV Files (*.csv)",
            "json": "JSON Files (*.json)",
            "html": "HTML Files (*.html)",
        }
        ext = export_format.lower()
        if ext not in filters:
            return
        default_path = pathlib.Path.cwd() / f"qc_report.{ext}"
        path_str, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export QC Report",
            str(default_path),
            filters[ext],
        )
        if not path_str:
            return

        output_path = pathlib.Path(path_str)
        if output_path.suffix.lower() != f".{ext}":
            output_path = output_path.with_suffix(f".{ext}")

        if ext == "csv":
            ok = QCReportExporter.export_csv(issues, output_path)
        elif ext == "json":
            ok = QCReportExporter.export_json(issues, output_path)
        else:
            ok = QCReportExporter.export_html_report(issues, output_path)

        if ok:
            self._set_status(f"Exported QC report to {output_path}.")
        else:
            QtWidgets.QMessageBox.critical(
                self,
                "Export QC Report",
                f"Failed to export QC report to {output_path}.",
            )
