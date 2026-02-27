"""Annotation table, status bar, and view stats helpers."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
try:
    from matplotlib.backends.qt_compat import QtCore, QtWidgets
except ImportError:  # pragma: no cover - exercised in headless CI/test envs
    class _MissingQtWidgets:
        def __getattr__(self, name: str) -> object:
            raise ImportError(
                "Qt bindings are required for GUI table/status operations."
            )

    QtWidgets = _MissingQtWidgets()
    QtCore = _MissingQtWidgets()

from phage_annotator.annotation.core import Keypoint
from phage_annotator.tools import Tool


class TableStatusMixin:
    """Mixin for annotation table and status rendering."""

    def _refresh_table(self) -> None:
        """Refresh table rows and keep selection focused for current T/Z when enabled."""
        self._populate_table()
        self._focus_table_current_slice_row()

    def _on_auto_follow_table_changed(self, state: int) -> None:
        """Persist auto-follow preference and refresh table view."""
        enabled = bool(state)
        if hasattr(self, "_settings"):
            self._settings.setValue("annotationTableAutoFollow", enabled)
        if enabled:
            self.filter_current_chk.blockSignals(True)
            self.filter_current_chk.setChecked(True)
            self.filter_current_chk.blockSignals(False)
        self._refresh_table()

    def _populate_table(self) -> None:
        """Populate the table from current keypoints."""
        pts = self._current_keypoints()
        self._table_rows = list(pts)
        sorting = bool(self.annot_table.isSortingEnabled())
        if sorting:
            self.annot_table.setSortingEnabled(False)
        self.annot_table.blockSignals(True)
        self.annot_table.setRowCount(len(pts))
        for row, kp in enumerate(pts):
            ann_id = str(kp.annotation_id)
            id_item = QtWidgets.QTableWidgetItem(ann_id[:8])
            id_item.setData(QtCore.Qt.ItemDataRole.UserRole, ann_id)
            id_item.setFlags(id_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            scope = "stack" if int(kp.t) == -1 and int(kp.z) == -1 else "slice"
            scope_item = QtWidgets.QTableWidgetItem(scope)
            scope_item.setData(QtCore.Qt.ItemDataRole.UserRole, ann_id)
            scope_item.setFlags(scope_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self.annot_table.setItem(row, 0, id_item)
            self.annot_table.setItem(row, 1, scope_item)
            self.annot_table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(kp.t)))
            self.annot_table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(kp.z)))
            self.annot_table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{kp.y:.2f}"))
            self.annot_table.setItem(row, 5, QtWidgets.QTableWidgetItem(f"{kp.x:.2f}"))
            self.annot_table.setItem(row, 6, QtWidgets.QTableWidgetItem(kp.label))
        self.annot_table.blockSignals(False)
        self.annot_table.resizeColumnsToContents()
        if sorting:
            self.annot_table.setSortingEnabled(True)

    def _keypoint_for_table_row(self, row: int) -> Optional[Keypoint]:
        """Resolve a keypoint from the currently visible table row using annotation id."""
        if row < 0:
            return None
        id_item = self.annot_table.item(int(row), 0)
        if id_item is None:
            return None
        ann_id = str(id_item.data(QtCore.Qt.ItemDataRole.UserRole) or "").strip()
        if not ann_id:
            return None
        for kp in self.annotations.get(self.primary_image.id, []):
            if str(kp.annotation_id) == ann_id:
                return kp
        return None

    def _focus_table_current_slice_row(self) -> None:
        """Auto-select and scroll to the first row matching current T/Z."""
        if not bool(getattr(self, "auto_follow_table_chk", None) and self.auto_follow_table_chk.isChecked()):
            return
        if self.annot_table.rowCount() <= 0:
            self.annot_table.clearSelection()
            return
        t_idx = int(self.t_slider.value())
        z_idx = int(self.z_slider.value())
        target_row = None
        for row in range(self.annot_table.rowCount()):
            t_item = self.annot_table.item(row, 2)
            z_item = self.annot_table.item(row, 3)
            if t_item is None or z_item is None:
                continue
            try:
                t_val = int(t_item.text())
                z_val = int(z_item.text())
            except ValueError:
                continue
            if t_val in (t_idx, -1) and z_val in (z_idx, -1):
                target_row = row
                break
        if target_row is None:
            self.annot_table.clearSelection()
            return
        self._block_table = True
        try:
            self.annot_table.selectRow(int(target_row))
            item = self.annot_table.item(int(target_row), 0)
            if item is not None:
                self.annot_table.scrollToItem(
                    item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter
                )
        finally:
            self._block_table = False

    def _on_table_selection(self) -> None:
        if self._block_table:
            return
        selected_ids = set()
        if self.annot_table.selectionModel() is not None:
            for idx in self.annot_table.selectionModel().selectedRows():
                kp = self._keypoint_for_table_row(idx.row())
                if kp is not None:
                    selected_ids.add(str(kp.annotation_id))
        self._selected_annotation_ids = selected_ids
        self._refresh_image()

    def _on_table_item_changed(self, item: "QtWidgets.QTableWidgetItem") -> None:
        if self._block_table:
            return
        row = item.row()
        col = item.column()
        kp = self._keypoint_for_table_row(row)
        if kp is None:
            return
        text = item.text()
        try:
            if col == 2:
                new_kp = Keypoint(kp.image_id, kp.image_name, int(text), kp.z, kp.y, kp.x, kp.label)
            elif col == 3:
                new_kp = Keypoint(kp.image_id, kp.image_name, kp.t, int(text), kp.y, kp.x, kp.label)
            elif col == 4:
                new_kp = Keypoint(
                    kp.image_id, kp.image_name, kp.t, kp.z, float(text), kp.x, kp.label
                )
            elif col == 5:
                new_kp = Keypoint(
                    kp.image_id, kp.image_name, kp.t, kp.z, kp.y, float(text), kp.label
                )
            elif col == 6:
                new_kp = Keypoint(kp.image_id, kp.image_name, kp.t, kp.z, kp.y, kp.x, text)
            else:
                return
        except ValueError:
            return
        new_kp.annotation_id = kp.annotation_id
        new_kp.meta = dict(kp.meta)
        new_kp.modality_idx = kp.modality_idx
        self.controller.update_annotation(self.primary_image.id, kp, new_kp)
        self._mark_dirty()
        self._refresh_table()
        self._refresh_image()

    def _delete_selected_annotations(self) -> None:
        """Delete selected annotations with confirmation (P3.3)."""
        if self.annot_table.selectionModel() is None:
            return
        rows = sorted({idx.row() for idx in self.annot_table.selectionModel().selectedRows()})
        if not rows:
            return
        removed: List[Keypoint] = []
        for row in reversed(rows):
            kp = self._keypoint_for_table_row(row)
            if kp is not None:
                removed.append(kp)
        if not removed:
            return
        # Confirmation dialog (P3.3)
        if self._settings.value("confirmDeleteAnnotations", True, type=bool):
            count = len(removed)
            reply = QtWidgets.QMessageBox.question(
                self,
                "Delete Annotations",
                f"Delete {count} annotation{'s' if count != 1 else ''}?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.controller.delete_annotations(self.primary_image.id, removed)
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._refresh_image()
        self._update_status()
        self._mark_dirty()

    def _update_status(self) -> None:
        total = sum(len(v) for v in self.annotations.values())
        current = len(
            [kp for kp in self._current_keypoints() if kp.t == self.t_slider.value() or kp.t == -1]
        )
        dataset_name = str(getattr(self.primary_image, "name", "unknown"))
        frame_txt = f"T{int(self.t_slider.value()) + 1}/Z{int(self.z_slider.value()) + 1}"
        annotation_space = str(
            getattr(getattr(self, "controller", None).session_state, "annotation_space", "stack")
            if getattr(self, "controller", None) is not None
            else "stack"
        )
        modality_txt = f"Modality {int(getattr(self, '_active_modality_idx', -1))}"
        manager = getattr(getattr(self, "controller", None).session_state, "modality_manager", None) if getattr(self, "controller", None) is not None else None
        if manager is not None:
            try:
                for modality in manager.get_all_modalities():
                    if int(modality.image_id) == int(self.primary_image.id):
                        modality_txt = str(modality.display_name)
                        break
            except Exception:
                pass

        pts_view, area_um2 = self._view_density_stats()
        density_txt = ""
        if area_um2 > 0:
            density = pts_view / area_um2 if area_um2 > 0 else 0.0
            density_txt = f" | View pts: {pts_view} | Area: {area_um2:.2f} um^2 | Density: {density:.3f} /um^2"
        cache_mb, cache_items = self.proj_cache.stats()
        cache_txt = f" | Cache: {cache_mb} MB | Items: {cache_items}"
        
        # Collect diagnostic flags
        diag_flags = []
        render_scales = getattr(self, "_render_scales", {}) or {}
        scale = max(render_scales.values()) if render_scales else 1
        if scale > 1:
            diag_flags.append(f"Downsample x{scale}")
        
        # Check for memory pressure / spatial downsampling on loaded image
        if self.primary_image.downsampled:
            diag_flags.append(f"Spatial 2x downsampled (memory)")
        
        lod_active = getattr(self, "_lod_mode_active", {})
        if lod_active.get(self.primary_image.id, False):
            diag_flags.append("LOD")
        if getattr(self.primary_image.array, "filename", None) is not None:
            diag_flags.append("Memmap")
        
        diag_txt = f" | {'; '.join(diag_flags)}" if diag_flags else ""
        assist_txt = ""
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "assist_status"):
            suggestions = self.suggestions.get(self.primary_image.id, []) if hasattr(self, "suggestions") else []
            annotation_space = str(getattr(controller.session_state, "annotation_space", "stack"))
            if suggestions:
                context_key = controller._context_key(suggestion=suggestions[0], annotation_space=annotation_space)
            else:
                context_key = f"{self.primary_image.name}|{annotation_space}|current_view"
            _level, msg = controller.assist_status(
                annotation_space=annotation_space,
                context_key=context_key,
            )
            assist_txt = f" | {msg}"
        jobs_txt = ""
        if getattr(self, "jobs", None) is not None:
            try:
                job_count = int(self.jobs.active_job_count())
                if job_count > 0:
                    jobs_txt = f" | Jobs: {job_count} ({getattr(self, '_active_job_name', 'running')})"
                else:
                    jobs_txt = " | Jobs: idle"
            except Exception:
                pass
        autosave_enabled = bool(
            getattr(self, "_settings", None).value("autosaveRecoveryEnabled", True, type=bool)
            if getattr(self, "_settings", None) is not None
            else True
        )
        autosave_txt = "Autosave: off"
        if autosave_enabled:
            if getattr(self, "_last_autosave_timestamp", None):
                autosave_txt = "Autosave: recent"
            else:
                autosave_txt = "Autosave: on"
        self._status_base = (
            f"{dataset_name} | {frame_txt} | Space: {annotation_space} | Modality: {modality_txt} "
            f"| Label: {self.current_label} | Current slice pts: {current} | Total pts: {total} "
            f"| Speed {self.speed_slider.value()} fps | {autosave_txt}{density_txt}{cache_txt}{diag_txt}{assist_txt}{jobs_txt}"
        )
        self._render_status()
        if self.tool_label is not None and self.tool_router is not None:
            self.tool_label.setText(f"Tool: {self._tool_label(self.tool_router.tool)}")
        if self.cache_stats_label is not None:
            self.cache_stats_label.setText(f"Cache: {cache_mb} MB | Items: {cache_items}")
        self._update_buffer_stats()

    def _set_status(self, text: str) -> None:
        """Set a transient status message; base status persists during playback."""
        self._status_extra = text
        self._render_status()

    def _render_status(self) -> None:
        if self._status_extra:
            self.status.setText(f"{self._status_base} | {self._status_extra}")
        else:
            self.status.setText(self._status_base)

    def _tool_label(self, tool: Tool) -> str:
        labels = {
            Tool.PAN_ZOOM: "Pan/Zoom",
            Tool.ANNOTATE_POINT: "Annotate",
            Tool.ROI_BOX: "ROI Box",
            Tool.ROI_CIRCLE: "ROI Circle",
            Tool.ROI_EDIT: "ROI Edit",
            Tool.PROFILE_LINE: "Profile Line",
            Tool.ERASER: "Eraser",
        }
        return labels.get(tool, tool.value)

    def _label_color(self, label: str, faded: bool = False) -> str:
        palette = {
            "phage": "#1f77b4",
            "not_phage": "#ff7f0e",
            "background": "#2ca02c",
            "other": "#d62728",
        }
        color = palette.get(label, "#2ca02c")
        if faded:
            color = "#cccccc"
        return color

    def _view_density_stats(self) -> Tuple[int, float]:
        axes = []
        if getattr(self, "renderer", None) is not None:
            axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        if not axes:
            return 0, 0.0
        scale = self._axis_scale(axes[0])
        xlim, ylim = axes[0].get_xlim(), axes[0].get_ylim()
        xlim = (xlim[0] * scale, xlim[1] * scale)
        ylim = (ylim[0] * scale, ylim[1] * scale)
        roi_active = self.roi_shape != "none" and self.roi_rect[2] > 0 and self.roi_rect[3] > 0
        circle_mode = self.roi_shape == "circle"
        circle_center = None
        circle_r = None
        if circle_mode and roi_active:
            rx, ry, rw, rh = self.roi_rect
            circle_center = (rx + rw / 2, ry + rh / 2)
            circle_r = min(rw, rh) / 2
        pts = self._current_keypoints()
        pts_view = 0
        for kp in pts:
            if kp.x < xlim[0] or kp.x > xlim[1] or kp.y < ylim[1] or kp.y > ylim[0]:
                continue
            if roi_active:
                if circle_mode and circle_center and circle_r is not None:
                    if (kp.x - circle_center[0]) ** 2 + (
                        kp.y - circle_center[1]
                    ) ** 2 > circle_r**2:
                        continue
                else:
                    rx, ry, rw, rh = self.roi_rect
                    if not (rx <= kp.x <= rx + rw and ry <= kp.y <= ry + rh):
                        continue
            pts_view += 1
        width = abs(xlim[1] - xlim[0])
        height = abs(ylim[1] - ylim[0])
        cal = self._get_calibration_state(self.primary_image.id)
        px_um = cal.pixel_size_um_per_px
        area_um2 = (width * height) * (px_um**2) if px_um else 0.0
        return pts_view, area_um2

    def _point_in_roi(self, x: float, y: float) -> bool:
        if self.roi_shape == "none":
            return True
        rx, ry, rw, rh = self.roi_rect
        if rw <= 0 or rh <= 0:
            return True
        if self.roi_shape == "box":
            return rx <= x <= rx + rw and ry <= y <= ry + rh
        cx, cy = rx + rw / 2, ry + rh / 2
        r = min(rw, rh) / 2
        return (x - cx) ** 2 + (y - cy) ** 2 <= r**2

    def _current_keypoints(self) -> List[Keypoint]:
        pts = self.annotations.get(self.primary_image.id, [])
        if self.filter_current_chk.isChecked():
            t = self.t_slider.value()
            z = self.z_slider.value()
            pts = [kp for kp in pts if (kp.t in (t, -1) and kp.z in (z, -1))]

        queue_mode = getattr(self, "_review_queue_filter", "all")
        if queue_mode == "my_queue":
            user = getattr(self.controller.session_state, "current_user", "local_user")
            pts = [kp for kp in pts if kp.meta.get("assignee", "") == user]
        elif queue_mode == "needs_review":
            pts = [
                kp
                for kp in pts
                if kp.meta.get("review_state", "new") in ("new", "in_review", "needs_changes")
            ]
        elif queue_mode == "blocked_qc":
            qc_state = getattr(self, "qc_state", None)
            affected_ids = (
                qc_state.get_affected_annotation_ids(respect_filters=False)
                if qc_state is not None
                else set()
            )
            pts = [kp for kp in pts if kp.annotation_id in affected_ids]
        
        # Phase ζ: Filter by current modality_idx if enabled
        if hasattr(self, '_filter_by_modality') and self._filter_by_modality:
            # Get current modality idx (from modality manager or primary image)
            current_modality_idx = self._get_current_modality_idx()
            if current_modality_idx is not None:
                from phage_annotator.core.multi_modality import filter_by_modality
                pts = filter_by_modality(pts, current_modality_idx, show_all=True)
        
        return pts
    
    def _get_current_modality_idx(self) -> Optional[int]:
        """Get the modality index for the currently displayed image."""
        manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is None:
            return None
        
        # Find modality for current primary image
        for modality in manager.get_all_modalities():
            if modality.image_id == self.primary_image.id:
                return modality.idx
        
        return None

    def _restore_zoom(self, data_shape: Tuple[int, int]) -> None:
        axes = []
        if getattr(self, "renderer", None) is not None:
            axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        if not axes:
            return
        if self.link_zoom:
            if self._last_zoom_linked is None:
                self._last_zoom_linked = (
                    (0.0, float(data_shape[1])),
                    (float(data_shape[0]), 0.0),
                )
            for ax in axes:
                scale = self._axis_scale(ax)
                default_xlim = (0, data_shape[1] / scale)
                default_ylim = (data_shape[0] / scale, 0)
                xlim_full, ylim_full = self._last_zoom_linked
                xlim = (xlim_full[0] / scale, xlim_full[1] / scale)
                ylim = (ylim_full[0] / scale, ylim_full[1] / scale)
                ax.set_xlim(xlim if self._valid_zoom(xlim_full, ylim_full) else default_xlim)
                ax.set_ylim(ylim if self._valid_zoom(xlim_full, ylim_full) else default_ylim)
        else:
            for ax in axes:
                scale = self._axis_scale(ax)
                default_xlim = (0, data_shape[1] / scale)
                default_ylim = (data_shape[0] / scale, 0)
                if ax.get_xlim() == (0.0, 1.0) or ax.get_ylim() == (0.0, 1.0):
                    ax.set_xlim(default_xlim)
                    ax.set_ylim(default_ylim)

    def _capture_zoom_state(self) -> None:
        axes = []
        if getattr(self, "renderer", None) is not None:
            axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        if not axes:
            return
        ax = axes[0]
        scale = self._axis_scale(ax)
        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        xlim_full = (xlim[0] * scale, xlim[1] * scale)
        ylim_full = (ylim[0] * scale, ylim[1] * scale)
        if self._valid_zoom(xlim_full, ylim_full):
            self._last_zoom_linked = (xlim_full, ylim_full)

    @staticmethod
    def _valid_zoom(xlim: Tuple[float, float], ylim: Tuple[float, float]) -> bool:
        if xlim[0] == xlim[1] or ylim[0] == ylim[1]:
            return False
        if any(np.isnan(xlim)) or any(np.isnan(ylim)):
            return False
        return True
