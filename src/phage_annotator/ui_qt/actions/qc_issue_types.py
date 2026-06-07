"""Extracted method group 2 for QCActionsMixin."""

from __future__ import annotations

import pathlib
import time
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.services.panel_logging import get_panel_logger

DISABLE_QC = True



class QcIssueTypesMixin:
    """Method group 2 extracted from QCActionsMixin."""

    def _jump_to_next_qc_issue(self) -> None:
        """Jump to the next visible QC issue in round-robin order."""
        if not self._is_qc_enabled():
            return
        self._ensure_qc_runtime()
        visible = list(self.qc_state.get_visible_issues(respect_filters=True))
        if not visible:
            self._status_info(
                "No QC issues to review.",
                timeout_ms=2500,
                source="qc.navigate",
            )
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
        self._status_info(
            f"QC issue {cursor + 1}/{len(visible)}: {str(getattr(issue, 'issue_type', 'issue'))}.",
            timeout_ms=2500,
            source="qc.navigate",
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

        self._request_ui_refresh("qc-actions", table=True)
        self._status_info(
            "Jumped to QC issue location.",
            timeout_ms=2500,
            source="qc.jump",
        )
        self._update_status()
    def _export_qc_report(self, export_format: str) -> None:
        """Export QC issues in machine-readable format."""
        if not self._is_qc_enabled():
            return
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
            self._status_success(
                f"Exported QC report to {output_path}.",
                timeout_ms=4000,
                source="qc.export",
            )
        else:
            QtWidgets.QMessageBox.critical(
                self,
                "Export QC Report",
                f"Failed to export QC report to {output_path}.",
            )
