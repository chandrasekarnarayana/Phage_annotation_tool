"""Annotation interaction helpers."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtWidgets


class AnnotationsMixin:
    """Mixin for annotation add/remove and profile line edits."""

    def _assist_annotation_for_suggestion_id(self, suggestion_id: str):
        sid = str(suggestion_id or "")
        if not sid:
            return None
        for kp in self.annotations.get(self.primary_image.id, []):
            meta = dict(getattr(kp, "meta", {}) or {})
            if str(meta.get("suggestion_id", "")) == sid:
                return kp
        return None

    def _is_refinable_assist_annotation(self, kp) -> bool:
        source = str(getattr(kp, "source", "") or "").strip().lower()
        meta = dict(getattr(kp, "meta", {}) or {})
        return source.startswith("suggested:") or bool(str(meta.get("suggestion_id", "")).strip())

    def _find_refinable_annotation_near(self, ax, x: float, y: float):
        pts = self._current_keypoints()
        if not pts:
            return None
        disp_x, disp_y = self._to_display_coords(ax, x, y)
        click_disp = ax.transData.transform((disp_x, disp_y))
        for kp in list(pts):
            if not self._is_refinable_assist_annotation(kp):
                continue
            kp_dx, kp_dy = self._to_display_coords(ax, kp.x, kp.y)
            kp_disp = ax.transData.transform((kp_dx, kp_dy))
            dist = np.hypot(kp_disp[0] - click_disp[0], kp_disp[1] - click_disp[1])
            if dist <= float(getattr(self, "click_radius_px", 6.0)) * 1.5:
                return kp
        return None

    def _start_assist_refine_drag(self, ax, x: float, y: float) -> bool:
        pending_sid = str(getattr(self, "_assist_refine_pending_annotation_id", "") or "")
        kp = self._assist_annotation_for_suggestion_id(pending_sid) if pending_sid else None
        if kp is None:
            kp = self._find_refinable_annotation_near(ax, x, y)
        if kp is None:
            return False
        self._selected_annotation_ids = {str(getattr(kp, "annotation_id", ""))}
        self._assist_drag_refine_state = {
            "annotation_id": str(getattr(kp, "annotation_id", "")),
            "suggestion_id": str(dict(getattr(kp, "meta", {}) or {}).get("suggestion_id", "")),
            "origin_x": float(getattr(kp, "x", 0.0)),
            "origin_y": float(getattr(kp, "y", 0.0)),
            "preview_x": float(x),
            "preview_y": float(y),
        }
        popup = getattr(self, "_suggestion_action_popup", None)
        if popup is not None:
            popup.hide()
        self._status_info("Drag to refine accepted assist point, then release to commit.", source="assist.canvas.drag")
        return True

    def _update_assist_refine_drag(self, ax, x: float, y: float) -> bool:
        state = dict(getattr(self, "_assist_drag_refine_state", {}) or {})
        if not state:
            return False
        state["preview_x"] = float(x)
        state["preview_y"] = float(y)
        self._assist_drag_refine_state = state
        self._request_ui_refresh("assist-drag-preview", image=True, status=False)
        return True

    def _finish_assist_refine_drag(self, ax, x: float, y: float) -> bool:
        state = dict(getattr(self, "_assist_drag_refine_state", {}) or {})
        if not state:
            return False
        annotation_id = str(state.get("annotation_id", "") or "")
        suggestion_id = str(state.get("suggestion_id", "") or "")
        for kp in list(self.annotations.get(self.primary_image.id, [])):
            if str(getattr(kp, "annotation_id", "")) != annotation_id:
                continue
            replacement = type(kp)(
                kp.image_id,
                kp.image_name,
                kp.t,
                kp.z,
                float(y),
                float(x),
                kp.label,
                source=str(getattr(kp, "source", "manual")),
                meta=dict(kp.meta),
                modality_idx=kp.modality_idx,
                annotation_context=getattr(kp, "annotation_context", ""),
            )
            replacement.annotation_id = kp.annotation_id
            replacement.status = str(getattr(kp, "status", "accepted"))
            replacement.confidence = getattr(kp, "confidence", None)
            replacement.roi_name = str(getattr(kp, "roi_name", "") or "")
            original = f"({float(state.get('origin_x', kp.x)):.2f}, {float(state.get('origin_y', kp.y)):.2f})"
            replacement.meta["refined_from_suggestion"] = True
            replacement.meta["original_suggestion_position"] = original
            notes = str(getattr(kp, "notes", "") or "")
            if "refined" not in notes.lower():
                replacement.notes = (notes + f" | refined from {original}").strip(" |")
            else:
                replacement.notes = notes
            if self.controller.update_annotation(kp.image_id, kp, replacement):
                self._assist_drag_refine_state = None
                self._assist_refine_pending_annotation_id = ""
                if suggestion_id:
                    self._selected_suggestion_id = suggestion_id
                self._status_success("Accepted assist point refined.", source="assist.canvas.drag")
                self._request_ui_refresh("assist-drag-finished", table=True, image=True, status=True)
                return True
        self._assist_drag_refine_state = None
        return False

    def _cancel_assist_refine_drag(self) -> None:
        if getattr(self, "_assist_drag_refine_state", None):
            self._assist_drag_refine_state = None
            self._request_ui_refresh("assist-drag-cancel", image=True, status=False)

    def _find_canvas_suggestion_near(self, event):
        if getattr(event, "inaxes", None) is None or getattr(event, "xdata", None) is None or getattr(event, "ydata", None) is None:
            return None
        if not bool(getattr(self, "_show_suggestion_overlay", True)):
            return None
        suggestions = list(self._visible_suggestions()) if hasattr(self, "_visible_suggestions") else []
        if not suggestions:
            return None
        hover_radius = max(5.0, float(getattr(self, "click_radius_px", 6.0)) * 1.8)
        best = None
        best_dist = None
        for suggestion in suggestions:
            sx, sy = self._to_display_coords(event.inaxes, float(suggestion.x), float(suggestion.y))
            dist = float(np.hypot(float(event.xdata) - float(sx), float(event.ydata) - float(sy)))
            if dist > hover_radius:
                continue
            if best is None or dist < float(best_dist):
                best = suggestion
                best_dist = dist
        return best

    def _ensure_suggestion_action_popup(self):
        popup = getattr(self, "_suggestion_action_popup", None)
        if popup is not None:
            return popup
        popup = QtWidgets.QFrame(self.canvas)
        popup.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        popup.setStyleSheet("QFrame { background: rgba(255,255,255,0.96); border: 1px solid #cfd8dc; border-radius: 6px; }")
        layout = QtWidgets.QHBoxLayout(popup)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)
        popup.summary_lbl = QtWidgets.QLabel("", popup)
        popup.accept_btn = QtWidgets.QToolButton(popup)
        popup.accept_btn.setText("✓")
        popup.reject_btn = QtWidgets.QToolButton(popup)
        popup.reject_btn.setText("✕")
        popup.jump_btn = QtWidgets.QToolButton(popup)
        popup.jump_btn.setText("◎")
        popup.refine_btn = QtWidgets.QToolButton(popup)
        popup.refine_btn.setText("↔")
        for widget in (popup.summary_lbl, popup.accept_btn, popup.reject_btn, popup.jump_btn, popup.refine_btn):
            layout.addWidget(widget)
        popup.hide()
        self._suggestion_action_popup = popup
        return popup

    def _show_suggestion_action_popup(self, suggestion, event) -> None:
        popup = self._ensure_suggestion_action_popup()
        meta = dict(getattr(suggestion, "meta", {}) or {})
        popup.summary_lbl.setText(
            f"{str(meta.get('candidate_class', 'new')).replace('_', ' ')} | "
            f"{float(meta.get('p_accept', getattr(suggestion, 'score', 0.0))):.2f}"
        )
        sid = str(getattr(suggestion, "suggestion_id", ""))
        try:
            popup.accept_btn.clicked.disconnect()
            popup.reject_btn.clicked.disconnect()
            popup.jump_btn.clicked.disconnect()
            popup.refine_btn.clicked.disconnect()
        except Exception:
            pass
        popup.accept_btn.clicked.connect(lambda _checked=False, s=sid: self._set_selected_suggestion_decision(s, "accepted"))
        popup.reject_btn.clicked.connect(lambda _checked=False, s=sid: self._set_selected_suggestion_decision(s, "rejected"))
        popup.jump_btn.clicked.connect(lambda _checked=False, s=sid: self._jump_to_table_suggestion(s))
        popup.refine_btn.clicked.connect(lambda _checked=False, s=sid: self._accept_and_refine_suggestion(s))
        x = int(max(0, min(self.canvas.width() - popup.sizeHint().width(), int(event.x) + 10)))
        y = int(max(0, min(self.canvas.height() - popup.sizeHint().height(), int(self.canvas.height() - event.y) + 10)))
        popup.move(x, y)
        popup.adjustSize()
        popup.show()

    def _apply_pending_assist_refine(self, ax, t: int, z: int, x: float, y: float) -> bool:
        suggestion_id = str(getattr(self, "_assist_refine_pending_annotation_id", "") or "")
        if not suggestion_id:
            return False
        for kp in list(self.annotations.get(self.primary_image.id, [])):
            meta = dict(getattr(kp, "meta", {}) or {})
            if str(meta.get("suggestion_id", "")) != suggestion_id:
                continue
            replacement = type(kp)(
                kp.image_id,
                kp.image_name,
                t if kp.t != -1 else kp.t,
                z if kp.z != -1 else kp.z,
                float(y),
                float(x),
                kp.label,
                source=str(getattr(kp, "source", "manual")),
                meta=dict(kp.meta),
                modality_idx=kp.modality_idx,
                annotation_context=getattr(kp, "annotation_context", ""),
            )
            replacement.annotation_id = kp.annotation_id
            replacement.status = str(getattr(kp, "status", "accepted"))
            replacement.confidence = getattr(kp, "confidence", None)
            replacement.roi_name = str(getattr(kp, "roi_name", "") or "")
            notes = str(getattr(kp, "notes", "") or "")
            replacement.notes = (notes + " | refined after accept").strip(" |")
            if self.controller.update_annotation(kp.image_id, kp, replacement):
                self._assist_refine_pending_annotation_id = ""
                popup = getattr(self, "_suggestion_action_popup", None)
                if popup is not None:
                    popup.hide()
                self._status_success("Accepted suggestion refined on canvas.", source="assist.canvas.refine")
                return True
        self._assist_refine_pending_annotation_id = ""
        return False

    def _on_click(self, event) -> None:
        if hasattr(self, "_toolbar_navigation_active") and self._toolbar_navigation_active():
            return
        # Annotation clicks follow the selected Annotation target panel directly,
        # independent of matplotlib toolbar mode.
        if event.inaxes == self.ax_frame and event.xdata is not None and event.ydata is not None:
            fx, fy = self._to_full_coords(self.ax_frame, event.xdata, event.ydata)
            self._set_cursor_xy(fx, fy, refresh=False)
        button = getattr(event, "button", None)
        is_right_click = button == 3 or str(button).lower().endswith("right")
        if (
            is_right_click
            and event.inaxes in self._get_image_axes()
            and event.xdata is not None
            and event.ydata is not None
            and hasattr(self, "_show_annotation_context_menu")
        ):
            fx, fy = self._to_full_coords(event.inaxes, event.xdata, event.ydata)
            global_pos = self.canvas.mapToGlobal(
                QtCore.QPoint(int(event.x), int(self.canvas.height() - event.y))
            )
            self._show_annotation_context_menu(fx, fy, global_pos)
            return
        if button == 1 and event.inaxes in self._get_image_axes():
            suggestion = self._find_canvas_suggestion_near(event)
            if suggestion is not None:
                self._selected_suggestion_id = str(getattr(suggestion, "suggestion_id", ""))
                self._focus_suggestion(suggestion)
                self._refresh_suggestion_explain_panel(suggestion)
                self._show_suggestion_action_popup(suggestion, event)
                self._request_ui_refresh("assist-canvas-select", table=True, image=True, status=True)
                return
            fx, fy = self._to_full_coords(event.inaxes, event.xdata, event.ydata)
            t_idx = int(self.t_slider.value()) if hasattr(self, "t_slider") else 0
            z_idx = int(self.z_slider.value()) if hasattr(self, "z_slider") else 0
            if self._apply_pending_assist_refine(event.inaxes, t_idx, z_idx, fx, fy):
                self._request_ui_refresh("assist-canvas-refine", table=True, image=True, status=True)
                return
        if self.tool_router is not None:
            self.tool_router.on_click(event)

    def _add_annotation(
        self, image_id: int, t: int, z: int, y: float, x: float, label: str, scope: str
    ) -> None:
        """Append a new annotation in full-resolution coordinates.

        Coordinates are stored in image space regardless of crop or downsample.
        Assigns active modality_idx if multi-modality system is enabled.
        """
        if hasattr(self, "_ensure_annotation_write_context_confirmed"):
            if not self._ensure_annotation_write_context_confirmed("Add annotation point"):
                return
        context = self.controller.current_annotation_context()
        target_image_id = int(context.get("source_image_id", image_id))
        source_image = next(
            (
                img
                for img in getattr(self, "images", [])
                if int(getattr(img, "id", -1)) == target_image_id
            ),
            self.primary_image,
        )
        self.controller.add_annotation(
            image_id=target_image_id,
            image_name=str(getattr(source_image, "name", self.primary_image.name)),
            t=t,
            z=z,
            y=y,
            x=x,
            label=label,
            scope=scope,
            modality_idx=context.get("modality_idx"),
            annotation_context=str(context.get("context_key", "")),
        )
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._update_status()
        self._mark_dirty()

    def _set_roi_rect(self, rect: Tuple[float, float, float, float]) -> None:
        if hasattr(self, "controller") and self.controller is not None:
            self.controller.set_roi(rect, shape=self.roi_shape)
        self.roi_rect = rect
        self.roi_x_spin.blockSignals(True)
        self.roi_y_spin.blockSignals(True)
        self.roi_w_spin.blockSignals(True)
        self.roi_h_spin.blockSignals(True)
        self.roi_x_spin.setValue(rect[0])
        self.roi_y_spin.setValue(rect[1])
        self.roi_w_spin.setValue(rect[2])
        self.roi_h_spin.setValue(rect[3])
        self.roi_x_spin.blockSignals(False)
        self.roi_y_spin.blockSignals(False)
        self.roi_w_spin.blockSignals(False)
        self.roi_h_spin.blockSignals(False)

    def _set_profile_line(self, line: Tuple[Tuple[float, float], Tuple[float, float]]) -> None:
        self.profile_line = line

    def _set_profile_mode(self, enabled: bool) -> None:
        self.profile_mode_chk.blockSignals(True)
        self.profile_mode_chk.setChecked(enabled)
        self.profile_mode_chk.blockSignals(False)

    def _remove_annotation_near(self, ax, t: int, z: int, x: float, y: float) -> bool:
        """Remove the nearest point within the click radius (P3.3: confirmation added)."""
        pts = self._current_keypoints()
        if not pts:
            return False
        disp_x, disp_y = self._to_display_coords(ax, x, y)
        click_disp = ax.transData.transform((disp_x, disp_y))
        for idx, kp in enumerate(list(pts)):
            if kp.t not in (t, -1) or kp.z not in (z, -1):
                continue
            kp_dx, kp_dy = self._to_display_coords(ax, kp.x, kp.y)
            kp_disp = ax.transData.transform((kp_dx, kp_dy))
            dist = np.hypot(kp_disp[0] - click_disp[0], kp_disp[1] - click_disp[1])
            if dist <= self.click_radius_px:
                removed = pts[idx]
                # Confirmation for click deletion (P3.3) - only for multi-select delete via table
                # Single clicks typically don't need confirmation for better UX
                self.controller.delete_annotations(removed.image_id, [removed])
                self.undo_act.setEnabled(self.controller.can_undo())
                self.redo_act.setEnabled(self.controller.can_redo())
                self._update_status()
                return True
        return False

    def undo_last_action(self) -> None:
        if not self.controller.can_undo():
            return
        if not self.controller.undo():
            return
        if hasattr(self, "t_slider"):
            target_t = int(getattr(self.controller.view_state, "t", self.t_slider.value()))
            if self.t_slider.value() != target_t:
                self.t_slider.setValue(target_t)
        if hasattr(self, "z_slider"):
            target_z = int(getattr(self.controller.view_state, "z", self.z_slider.value()))
            if self.z_slider.value() != target_z:
                self.z_slider.setValue(target_z)
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._request_ui_refresh("annotations-mixin", table=True)
        self._update_status()

    def redo_last_action(self) -> None:
        if not self.controller.can_redo():
            return
        if not self.controller.redo():
            return
        if hasattr(self, "t_slider"):
            target_t = int(getattr(self.controller.view_state, "t", self.t_slider.value()))
            if self.t_slider.value() != target_t:
                self.t_slider.setValue(target_t)
        if hasattr(self, "z_slider"):
            target_z = int(getattr(self.controller.view_state, "z", self.z_slider.value()))
            if self.z_slider.value() != target_z:
                self.z_slider.setValue(target_z)
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._request_ui_refresh("annotations-mixin", table=True)
        self._update_status()

    def _handle_profile_click(self, event) -> None:
        if self.profile_line is None or event.inaxes != self.ax_line:
            return
        if event.xdata is None or event.ydata is None:
            return
        (y1, x1), (y2, x2) = self.profile_line
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) > abs(dy):
            self.profile_line = ((y1, event.xdata), (y2, event.xdata))
        else:
            self.profile_line = ((event.ydata, x1), (event.ydata, x2))
        self._request_ui_refresh("annotations-mixin")
