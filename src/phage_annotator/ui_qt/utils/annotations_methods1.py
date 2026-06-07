"""Method group 1 split from annotations.py."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.tools.router import Tool
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


class _AnnotationsMixinMethods1:
    """Methods split from AnnotationsMixin."""

    def _find_canvas_suggestion_near(self, event):
        """Find canvas suggestion near for the current workflow."""
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
        """Ensure suggestion action popup for the current workflow."""
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
        for widget in (popup.summary_lbl, popup.accept_btn, popup.reject_btn, popup.jump_btn):
            layout.addWidget(widget)
        popup.hide()
        self._suggestion_action_popup = popup
        return popup

    def _show_suggestion_action_popup(self, suggestion, event) -> None:
        """Show suggestion action popup for the current workflow."""
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
        except Exception:
            pass
        popup.accept_btn.clicked.connect(lambda _checked=False, s=sid: self._set_selected_suggestion_decision(s, "accepted"))
        popup.reject_btn.clicked.connect(lambda _checked=False, s=sid: self._set_selected_suggestion_decision(s, "rejected"))
        popup.jump_btn.clicked.connect(lambda _checked=False, s=sid: self._jump_to_table_suggestion(s))
        x = int(max(0, min(self.canvas.width() - popup.sizeHint().width(), int(event.x) + 10)))
        y = int(max(0, min(self.canvas.height() - popup.sizeHint().height(), int(self.canvas.height() - event.y) + 10)))
        popup.move(x, y)
        popup.adjustSize()
        popup.show()

    def _on_click(self, event) -> None:
        """Handle the on click helper flow."""
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
            active_tool = getattr(self.tool_router, "tool", None) if self.tool_router is not None else None
            enabled_chk = getattr(self, "annotate_enabled_chk", None)
            click_annotation_enabled = bool(
                enabled_chk.isChecked() if enabled_chk is not None else True
            )
            annotation_click_has_priority = bool(
                click_annotation_enabled
                and active_tool in (Tool.ANNOTATE_POINT, Tool.ERASER)
                and event.inaxes == self._get_target_axis()
            )
            suggestion = None if annotation_click_has_priority else self._find_canvas_suggestion_near(event)
            if suggestion is not None:
                self._selected_suggestion_id = str(getattr(suggestion, "suggestion_id", ""))
                self._focus_suggestion(suggestion)
                self._refresh_suggestion_explain_panel(suggestion)
                self._show_suggestion_action_popup(suggestion, event)
                self._request_ui_refresh("assist-canvas-select", table=True, image=True, status=True)
                return
        if self.tool_router is not None:
            enabled_chk = getattr(self, "annotate_enabled_chk", None)
            click_annotation_enabled = bool(
                enabled_chk.isChecked() if enabled_chk is not None else True
            )
            if (
                not click_annotation_enabled
                and getattr(self.tool_router, "tool", None) in (Tool.ANNOTATE_POINT, Tool.ERASER)
            ):
                if button == 1 and event.inaxes == self._get_target_axis():
                    self._status_info(
                        "Click annotation is disabled in the Annotation panel.",
                        source="annotate.disabled",
                    )
                return
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
        logger = get_panel_logger("annotate")
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
        logger.log_action(
            "add_annotation",
            image_id=target_image_id,
            t=t,
            z=z,
            y=round(float(y), 2),
            x=round(float(x), 2),
            label=label,
            scope=scope,
            context_key=context.get("context_key"),
        )
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._update_status()
        self._mark_dirty()

    def _set_roi_rect(self, rect: Tuple[float, float, float, float]) -> None:
        """Set roi rect for the current workflow."""
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
        """Set profile line for the current workflow."""
        self.profile_line = line

    def _set_profile_mode(self, enabled: bool) -> None:
        """Set profile mode for the current workflow."""
        self.profile_mode_chk.blockSignals(True)
        self.profile_mode_chk.setChecked(enabled)
        self.profile_mode_chk.blockSignals(False)
