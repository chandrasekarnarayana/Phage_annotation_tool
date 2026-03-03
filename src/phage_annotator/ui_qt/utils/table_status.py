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
from phage_annotator.ui_qt.assist_state import (
    AssistState,
    assist_state_color,
    assist_state_label,
    infer_assist_state,
)


class TableStatusMixin:
    """Mixin for annotation table and status rendering."""

    def _refresh_table(self) -> None:
        """Refresh table rows and keep selection focused for current T/Z when enabled."""
        self._populate_table()
        self._focus_table_current_slice_row()
        self._refresh_right_dock_segment_headers()
        if hasattr(self, "_refresh_review_queue_panel"):
            self._refresh_review_queue_panel()

    def _canonical_assist_state(self, suggestions: Optional[List[object]] = None) -> AssistState:
        """Resolve assist-state from one canonical inference path."""
        rows = list(suggestions) if suggestions is not None else list(
            getattr(self, "suggestions", {}).get(self.primary_image.id, [])
        )
        annotation_space = str(
            getattr(self.controller.session_state, "annotation_space", "stack")
            if getattr(self, "controller", None) is not None
            else "stack"
        )
        return infer_assist_state(
            controller=getattr(self, "controller", None),
            image_name=str(getattr(self.primary_image, "name", "unknown")),
            annotation_space=annotation_space,
            suggestions=rows,
        )

    def _assist_context_need_count(self, suggestions: Optional[List[object]] = None) -> int:
        """Return remaining labels needed for current assist context."""
        controller = getattr(self, "controller", None)
        if controller is None or not hasattr(controller, "assist_need_breakdown"):
            return 0
        rows = list(suggestions) if suggestions is not None else list(
            getattr(self, "suggestions", {}).get(self.primary_image.id, [])
        )
        annotation_space = str(getattr(controller.session_state, "annotation_space", "stack"))
        if rows:
            context_key = controller._context_key(
                suggestion=rows[0], annotation_space=annotation_space
            )
        else:
            context_key = f"{self.primary_image.name}|{annotation_space}|current_view"
        breakdown = controller.assist_need_breakdown(
            annotation_space=annotation_space,
            context_key=context_key,
        )
        return int(
            max(
                breakdown.get("need_total", 0),
                breakdown.get("need_pos", 0),
                breakdown.get("need_neg", 0),
                breakdown.get("need_context", 0),
            )
        )

    def _style_assist_state_label(
        self,
        widget: Optional["QtWidgets.QLabel"],
        state: AssistState,
        prefix: str = "Assist: ",
        suffix: str = "",
    ) -> None:
        """Apply canonical assist-state wording and color to a label."""
        if widget is None:
            return
        widget.setText(f"{prefix}{assist_state_label(state)}{suffix}")
        widget.setStyleSheet(
            "font-weight: 600; "
            f"color: {assist_state_color(state)};"
        )

    def _refresh_right_dock_segment_headers(self) -> None:
        """Sync segmented right-dock headers with counts and active tab state."""
        table_count = int(self.annot_table.rowCount()) if getattr(self, "annot_table", None) is not None else 0
        queue_count = 0
        if hasattr(self, "_visible_suggestions_uncertain_first"):
            try:
                queue_count = int(len(self._visible_suggestions_uncertain_first()))
            except Exception:
                queue_count = 0

        active = "table"
        dock_annotations = getattr(self, "dock_annotations", None)
        dock_review_queue = getattr(self, "dock_review_queue", None)
        dock_suggestion_explain = getattr(self, "dock_suggestion_explain", None)
        if dock_review_queue is not None and bool(dock_review_queue.isVisible()):
            active = "queue"
        elif dock_suggestion_explain is not None and bool(dock_suggestion_explain.isVisible()):
            active = "why"
        elif dock_annotations is not None and bool(dock_annotations.isVisible()):
            active = "table"

        for attr in ("annotation_segment_header", "review_segment_header", "explain_segment_header"):
            header = getattr(self, attr, None)
            if header is None:
                continue
            header.set_counts(table_count=table_count, queue_count=queue_count)
            header.set_active(active)

    def _bottom_task_counts(self) -> tuple[int, int, int]:
        """Return counts for task-specific bottom tabs: (qc_issues, results_rows, log_alerts)."""
        qc_count = 0
        qc_state = getattr(self, "qc_state", None)
        if qc_state is not None:
            qc_count = int(len(getattr(qc_state, "issues", []) or []))
        results_rows = 0
        results_widget = getattr(self, "results_widget", None)
        if results_widget is not None and getattr(results_widget, "table", None) is not None:
            results_rows = int(results_widget.table.rowCount())
        log_alerts = 0
        all_logs = list(getattr(self, "_all_logs", []) or [])
        for row in all_logs[-200:]:
            txt = str(row).upper()
            if "ERROR" in txt or "WARNING" in txt or "[EXCEPTION]" in txt:
                log_alerts += 1
        return qc_count, results_rows, log_alerts

    def _update_bottom_task_panels(self) -> None:
        """Auto-collapse bottom panel by default; expand only for non-empty task tabs."""
        qc_count, results_rows, log_alerts = self._bottom_task_counts()
        has_qc = qc_count > 0
        if str(getattr(self, "_active_layout_preset", "")) == "Assist Expert":
            has_qc = True
        has_results = results_rows > 0
        has_logs = log_alerts > 0
        if hasattr(self, "set_panel_visible"):
            self.set_panel_visible("qc_issues", has_qc, source="bottom_task_auto")
            self.set_panel_visible("results", has_results, source="bottom_task_auto")
            self.set_panel_visible("logs", has_logs, source="bottom_task_auto")
        # Keep Results/QC/Diagnostics tabbed together when active.
        dock_results = getattr(self, "dock_results", None)
        dock_qc = getattr(self, "dock_qc_issues", None)
        dock_logs = getattr(self, "dock_logs", None)
        if dock_results is not None and dock_qc is not None:
            try:
                self.tabifyDockWidget(dock_results, dock_qc)
            except Exception:
                pass
        if dock_qc is not None and dock_logs is not None:
            try:
                self.tabifyDockWidget(dock_qc, dock_logs)
            except Exception:
                pass
        # Collapse bottom to slim footprint when empty; expand modestly when active.
        bottom_docks = [d for d in (dock_results, dock_qc, dock_logs) if d is not None and d.isVisible()]
        if bottom_docks:
            try:
                target = max(64, int(max(1, self.height()) * 0.12))
                self.resizeDocks(bottom_docks, [target for _ in bottom_docks], QtCore.Qt.Orientation.Vertical)
            except Exception:
                pass

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
        array = getattr(self.primary_image, "array", None)
        t_total = int(array.shape[0]) if array is not None and getattr(array, "ndim", 0) >= 1 else int(self.t_slider.maximum() + 1)
        z_total = int(array.shape[1]) if array is not None and getattr(array, "ndim", 0) >= 2 else int(self.z_slider.maximum() + 1)
        frame_txt = f"T: {int(self.t_slider.value()) + 1}/{max(1, t_total)} | Z: {int(self.z_slider.value()) + 1}/{max(1, z_total)}"
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
        density = (pts_view / area_um2) if area_um2 > 0 else 0.0
        cache_mb, cache_items = self.proj_cache.stats()
        
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
        
        assist_state = self._canonical_assist_state()
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
        scope_state = "Stack" if str(getattr(self, "annotation_scope", "current")) == "all" else "Slice"
        target_map = {"frame": "Frame", "mean": "Mean Projection", "support": "Modality 2"}
        target_state = target_map.get(str(getattr(self, "annotate_target", "frame")), "Frame")
        qc_warnings = 0
        qc_errors = 0
        qc_state = getattr(self, "qc_state", None)
        if qc_state is not None:
            for issue in getattr(qc_state, "issues", []):
                sev = str(getattr(getattr(issue, "severity", None), "value", "")).lower()
                if sev == "warning":
                    qc_warnings += 1
                elif sev == "error":
                    qc_errors += 1
        qc_total = qc_warnings + qc_errors
        qc_label = "QC: no issues" if qc_total == 0 else f"QC: {qc_warnings} warnings"
        if qc_errors > 0:
            qc_label += f", {qc_errors} errors"

        # Permanent status widgets are the primary operational state display.
        if getattr(self, "status_dataset_lbl", None) is not None:
            self.status_dataset_lbl.setText(f"Dataset: {dataset_name}")
        if getattr(self, "status_label_lbl", None) is not None:
            self.status_label_lbl.setText(f"Label: {self.current_label}")
        if getattr(self, "status_tz_lbl", None) is not None:
            self.status_tz_lbl.setText(frame_txt)
        if getattr(self, "status_points_lbl", None) is not None:
            self.status_points_lbl.setText(f"Points ({target_state}): {current}")
        if getattr(self, "status_roi_area_lbl", None) is not None:
            self.status_roi_area_lbl.setText(
                f"ROI area: {area_um2:.2f} um^2" if area_um2 > 0 else "ROI area: n/a"
            )
        if getattr(self, "status_density_lbl", None) is not None:
            self.status_density_lbl.setText(
                f"Density: {density:.3f} /um^2" if area_um2 > 0 else "Density: n/a"
            )
        if getattr(self, "status_fps_lbl", None) is not None:
            self.status_fps_lbl.setText(f"FPS: {int(self.speed_slider.value())}")
        # Keep live metrics contextual: show only while annotation workflow is active.
        annotate_tool_active = bool(
            getattr(self, "tool_router", None) is not None
            and getattr(self.tool_router, "tool", None) == Tool.ANNOTATE_POINT
        )
        for attr in ("status_points_lbl", "status_roi_area_lbl", "status_density_lbl", "status_fps_lbl"):
            widget = getattr(self, attr, None)
            if widget is not None:
                # Hide tooltip when hiding widget
                if not annotate_tool_active:
                    try:
                        from matplotlib.backends.qt_compat import QtWidgets
                        QtWidgets.QToolTip.hideText()
                    except Exception:
                        pass
                widget.setVisible(annotate_tool_active)
        if getattr(self, "status_scope_lbl", None) is not None:
            self.status_scope_lbl.setText(f"Scope: {scope_state}")
            if str(getattr(self, "annotation_scope", "current")) == "all":
                self.status_scope_lbl.setStyleSheet("color: #ef6c00; font-weight: 600;")
            else:
                self.status_scope_lbl.setStyleSheet("")
        if getattr(self, "status_target_lbl", None) is not None:
            self.status_target_lbl.setText(f"Target: {target_state}")
        status_modality_combo = getattr(self, "status_modality_combo", None)
        if status_modality_combo is not None and getattr(self, "primary_combo", None) is not None:
            status_modality_combo.blockSignals(True)
            status_modality_combo.clear()
            for idx in range(self.primary_combo.count()):
                status_modality_combo.addItem(self.primary_combo.itemText(idx), idx)
            if 0 <= int(getattr(self, "current_image_idx", 0)) < status_modality_combo.count():
                status_modality_combo.setCurrentIndex(int(self.current_image_idx))
            status_modality_combo.setToolTip(
                f"Active modality/view source: {modality_txt}. "
                "Use this selector to switch annotation/suggestion source."
            )
            status_modality_combo.blockSignals(False)
        if getattr(self, "status_context_lock_lbl", None) is not None:
            pending = bool(
                hasattr(self, "_is_annotation_context_guard_pending")
                and self._is_annotation_context_guard_pending()
            )
            if pending:
                self.status_context_lock_lbl.setText("Write Context: Pending Confirm")
                self.status_context_lock_lbl.setStyleSheet("color: #e65100; font-weight: 600;")
            else:
                self.status_context_lock_lbl.setText("Write Context: Locked")
                self.status_context_lock_lbl.setStyleSheet("")
        if getattr(self, "status_effective_context_lbl", None) is not None:
            context_line = (
                self._effective_assist_context_line()
                if hasattr(self, "_effective_assist_context_line")
                else "-"
            )
            self.status_effective_context_lbl.setText(
                f"Effective Assist Context: {context_line}"
            )
        need = self._assist_context_need_count()
        suffix = f" (Need {need} more labels in this context)" if assist_state == AssistState.HEURISTIC and need > 0 else ""
        self._style_assist_state_label(
            getattr(self, "status_assist_lbl", None),
            assist_state,
            suffix=suffix,
        )
        state_name = str(getattr(assist_state, "name", ""))
        prev_state = getattr(self, "_last_assist_state_name", None)
        if prev_state is None:
            self._last_assist_state_name = state_name
        elif prev_state != state_name:
            self._last_assist_state_name = state_name
            transition_txt = (
                f"Assist state transitioned: {prev_state.lower()} -> {state_name.lower()}."
            )
            self._set_status(transition_txt)
            if getattr(self, "canvas", None) is not None:
                try:
                    from matplotlib.backends.qt_compat import QtCore, QtWidgets
                    QtWidgets.QToolTip.showText(
                        self.canvas.mapToGlobal(QtCore.QPoint(16, 16)),
                        transition_txt,
                        self.canvas,
                    )
                except Exception:
                    pass
        readiness = (
            f"Assist readiness: heuristic-only, need {need} more labels in this context."
            if assist_state == AssistState.HEURISTIC and need > 0
            else f"Assist readiness: {assist_state_label(assist_state)}."
        )
        for attr in (
            "suggest_points_act",
            "suggest_points_image_act",
            "accept_visible_suggestions_act",
            "accept_green_suggestions_act",
            "train_ranker_now_act",
        ):
            action = getattr(self, attr, None)
            if action is not None:
                action.setToolTip(readiness)
                action.setStatusTip(readiness)
        if getattr(self, "status_qc_lbl", None) is not None:
            self.status_qc_lbl.setText(qc_label)
        if getattr(self, "status_results_lbl", None) is not None:
            _, results_rows, _ = self._bottom_task_counts()
            self.status_results_lbl.setText(
                "Results: empty" if results_rows <= 0 else f"Results: {results_rows} rows"
            )
        freshness = (
            self._suggestion_freshness_state(self.primary_image.id)
            if hasattr(self, "_suggestion_freshness_state")
            else {"has_suggestions": False, "age_text": "n/a", "is_stale": False}
        )
        if getattr(self, "status_suggestion_fresh_lbl", None) is not None:
            if not freshness.get("has_suggestions", False):
                self.status_suggestion_fresh_lbl.setText("Suggestions: n/a")
                self.status_suggestion_fresh_lbl.setStyleSheet("")
            elif freshness.get("is_stale", False):
                self.status_suggestion_fresh_lbl.setText(
                    f"Suggestions: {freshness.get('age_text', 'n/a')} old (Stale)"
                )
                self.status_suggestion_fresh_lbl.setStyleSheet("color: #d84315; font-weight: 600;")
            else:
                self.status_suggestion_fresh_lbl.setText(
                    f"Suggestions: {freshness.get('age_text', 'n/a')} old"
                )
                self.status_suggestion_fresh_lbl.setStyleSheet("")
        for act_name in ("accept_visible_suggestions_act", "accept_green_suggestions_act"):
            act = getattr(self, act_name, None)
            if act is not None:
                if freshness.get("is_stale", False):
                    act.setToolTip(
                        "Stale suggestions detected: preview dialog will require one-shot override acknowledgement."
                    )
        if getattr(self, "evidence_strip_lbl", None) is not None:
            projection_txt = "raw"
            if getattr(self, "projection_selector", None) is not None:
                try:
                    projection_txt, axis_txt = self.projection_selector.current_selection()
                    projection_txt = f"{projection_txt} ({axis_txt})"
                except Exception:
                    projection_txt = "raw"
            modality_count = len(getattr(self, "_panel_modality_map", {}) or {})
            target_key = str(getattr(self, "annotate_target", "frame"))
            target_txt = {"frame": "Frame", "mean": "Mean Projection", "support": "Modality 2"}.get(
                target_key, target_key
            )
            self.evidence_strip_lbl.setText(
                f"Evidence: modality={modality_txt} | target={target_txt} | projection={projection_txt} | mapped modalities={modality_count}"
            )

        status_details = getattr(self, "status_details_panel", None)
        if status_details is not None:
            try:
                status_details.dataset_lbl.setText(dataset_name)
                status_details.tz_lbl.setText(frame_txt)
                status_details.scope_lbl.setText(scope_state)
                status_details.target_lbl.setText(target_state)
                status_details.modality_lbl.setText(modality_txt)
                status_details.label_lbl.setText(str(self.current_label))
                status_details.assist_lbl.setText(
                    f"{assist_state_label(assist_state)}"
                    + (f" (Need {need} more labels)" if assist_state == AssistState.HEURISTIC and need > 0 else "")
                )
                status_details.context_lbl.setText(
                    self._effective_assist_context_line()
                    if hasattr(self, "_effective_assist_context_line")
                    else "-"
                )
                status_details.suggestions_lbl.setText(
                    self.status_suggestion_fresh_lbl.text()
                    if getattr(self, "status_suggestion_fresh_lbl", None) is not None
                    else "n/a"
                )
                status_details.qc_lbl.setText(qc_label)
                status_details.results_lbl.setText(
                    self.status_results_lbl.text()
                    if getattr(self, "status_results_lbl", None) is not None
                    else "Results: n/a"
                )
                status_details.points_lbl.setText(f"Slice {current} | Total {total}")
                status_details.roi_area_lbl.setText(
                    f"{area_um2:.2f} um^2" if area_um2 > 0 else "n/a"
                )
                status_details.density_lbl.setText(
                    f"{density:.3f} /um^2" if area_um2 > 0 else "n/a"
                )
                status_details.fps_lbl.setText(f"{int(self.speed_slider.value())} fps")
                status_details.autosave_lbl.setText(autosave_txt.replace("Autosave: ", ""))
                status_details.cache_lbl.setText(f"{cache_mb} MB | {cache_items} items")
                status_details.jobs_lbl.setText(jobs_txt.replace(" | Jobs: ", "") if jobs_txt else "idle")
                status_details.diag_lbl.setText("; ".join(diag_flags) if diag_flags else "none")
            except Exception:
                pass

        tool_name = "Annotate"
        try:
            if getattr(self, "tool_router", None) is not None:
                tool_name = self._tool_label(self.tool_router.tool)
        except Exception:
            pass
        self._status_base = "Ready"
        self._render_status()
        self._update_bottom_task_panels()
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
