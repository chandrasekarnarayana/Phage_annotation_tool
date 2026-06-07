"""Extracted method group 4 for TableStatusMixin."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
try:
    from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui
except ImportError:  # pragma: no cover - exercised in headless CI/test envs
    class _MissingQtWidgets:
        def __getattr__(self, name: str) -> object:
            """Delegate unknown attribute access to the wrapped value."""
            raise ImportError(
                "Qt bindings are required for GUI table/status operations."
            )

    QtWidgets = _MissingQtWidgets()
    QtCore = _MissingQtWidgets()
    QtGui = _MissingQtWidgets()

from phage_annotator.ui_qt.services.panel_logging import get_panel_logger

from phage_annotator.annotation.core import Keypoint
from phage_annotator.tools import Tool
from phage_annotator.ui_qt.assist_state import (
    AssistState,
    assist_state_color,
    assist_state_label,
    infer_assist_state,
)
from phage_annotator.ui_qt.services.status import StatusText
from phage_annotator.ui_qt.services.status_derived import (
    DerivedStatusSnapshot,
    build_status_snapshot,
)



class TableStatusUpdateMixin:
    """Method group 4 extracted from TableStatusMixin."""

    def _apply_legacy_status_snapshot(self, snapshot: DerivedStatusSnapshot) -> None:
        """Update compatibility widgets from the unified status snapshot."""
        status_modality_combo = getattr(self, "status_modality_combo", None)
        if status_modality_combo is not None:
            status_modality_combo.blockSignals(True)
            status_modality_combo.clear()
            for idx, img in enumerate(getattr(self, "images", []) or []):
                status_modality_combo.addItem(str(getattr(img, "name", f"Image {idx}")), idx)
            if 0 <= int(getattr(self, "current_image_idx", 0)) < status_modality_combo.count():
                status_modality_combo.setCurrentIndex(int(self.current_image_idx))
            status_modality_combo.setToolTip(
                f"Active modality/view source: {snapshot.modality_txt}. "
                "Use this selector to switch annotation/suggestion source."
            )
            status_modality_combo.blockSignals(False)
        assist_state = snapshot.assist_state
        need = snapshot.assist_need
        state_name = str(getattr(assist_state, "name", ""))
        prev_state = getattr(self, "_last_assist_state_name", None)
        if prev_state is None:
            self._last_assist_state_name = state_name
        elif prev_state != state_name:
            self._last_assist_state_name = state_name
            transition_txt = f"Assist state transitioned: {prev_state.lower()} -> {state_name.lower()}."
            self._status_info(transition_txt, timeout_ms=2500, source="assist.transition")
            if getattr(self, "canvas", None) is not None:
                try:
                    QtWidgets.QToolTip.showText(self.canvas.mapToGlobal(QtCore.QPoint(16, 16)), transition_txt, self.canvas)
                except Exception:
                    pass
        readiness = f"Assist readiness: heuristic-only, need {need} more labels in this context." if assist_state == AssistState.HEURISTIC and need > 0 else f"Assist readiness: {assist_state_label(assist_state)}."
        for attr in ("suggest_points_act", "suggest_points_image_act", "accept_visible_suggestions_act", "accept_green_suggestions_act", "train_ranker_now_act"):
            action = getattr(self, attr, None)
            if action is not None:
                action.setToolTip(readiness)
                action.setStatusTip(readiness)
        for act_name in ("accept_visible_suggestions_act", "accept_green_suggestions_act"):
            act = getattr(self, act_name, None)
            if act is not None and snapshot.freshness.get("is_stale", False):
                act.setToolTip("Stale suggestions detected: preview dialog will require one-shot override acknowledgement.")
        if getattr(self, "evidence_strip_lbl", None) is not None:
            projection_txt = "raw"
            if getattr(self, "projection_selector", None) is not None:
                try:
                    projection_txt, axis_txt = self.projection_selector.current_selection()
                    if str(projection_txt).strip().lower() == "raw":
                        projection_txt = "source frame"
                    projection_txt = f"{projection_txt} ({axis_txt})"
                except Exception:
                    projection_txt = "source frame"
            modality_count = len(getattr(self, "_panel_modality_map", {}) or {})
            self.evidence_strip_lbl.setText(
                f"Evidence: modality={snapshot.modality_txt} | "
                f"target={snapshot.target_state} | projection={projection_txt} | "
                f"mapped modalities={modality_count}"
            )
    def _tool_label(self, tool: Tool) -> str:
        """Handle the tool label helper flow."""
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
        """Label color for the current workflow."""
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
        """Calculate view+ROI density statistics.
        
        Returns
        -------
        pts_view : int
            Points in visible view intersected with ROI.
        area_um2 : float
            Area of visible view intersected with ROI in μm².
        
        Note: Use _roi_total_stats() for total ROI statistics.
        """
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
        
        # Calculate area of intersection between view and ROI
        cal = self._get_calibration_state(self.primary_image.id)
        px_um = cal.pixel_size_um_per_px
        
        if roi_active:
            # Calculate intersection of view bounds and ROI
            rx, ry, rw, rh = self.roi_rect
            if circle_mode and circle_center and circle_r is not None:
                # For circle ROI, approximate as bounding box intersection
                # (true circle-rect intersection is complex, this is good enough for density)
                roi_left, roi_right = rx, rx + rw
                roi_bottom, roi_top = ry + rh, ry
            else:
                roi_left, roi_right = rx, rx + rw
                roi_bottom, roi_top = ry + rh, ry
            
            # View bounds (note: ylim is inverted in matplotlib image coordinates)
            view_left, view_right = xlim[0], xlim[1]
            view_bottom, view_top = max(ylim), min(ylim)
            
            # Intersection bounds
            intersect_left = max(roi_left, view_left)
            intersect_right = min(roi_right, view_right)
            intersect_bottom = max(roi_bottom, view_bottom)
            intersect_top = min(roi_top, view_top)
            
            # Calculate intersection area
            if intersect_right > intersect_left and intersect_bottom > intersect_top:
                width = intersect_right - intersect_left
                height = intersect_bottom - intersect_top
                area_um2 = (width * height) * (px_um**2) if px_um else 0.0
            else:
                area_um2 = 0.0  # No intersection
        else:
            # No ROI active, use full view area
            width = abs(xlim[1] - xlim[0])
            height = abs(ylim[1] - ylim[0])
            area_um2 = (width * height) * (px_um**2) if px_um else 0.0
        
        return pts_view, area_um2
    def _roi_total_stats(self) -> Tuple[int, float]:
        """Calculate total ROI statistics (entire ROI, not just visible view).
        
        Returns
        -------
        pts_roi : int
            Total points in entire ROI.
        roi_area_um2 : float
            Total area of entire ROI in μm².
        """
        roi_active = self.roi_shape != "none" and self.roi_rect[2] > 0 and self.roi_rect[3] > 0
        if not roi_active:
            return 0, 0.0
        
        circle_mode = self.roi_shape == "circle"
        rx, ry, rw, rh = self.roi_rect
        
        # Calculate total ROI area
        cal = self._get_calibration_state(self.primary_image.id)
        px_um = cal.pixel_size_um_per_px
        
        if circle_mode:
            circle_r = min(rw, rh) / 2
            roi_area_um2 = (np.pi * circle_r**2) * (px_um**2) if px_um else 0.0
        else:
            roi_area_um2 = (rw * rh) * (px_um**2) if px_um else 0.0
        
        # Count total points in ROI
        pts = self._current_keypoints()
        pts_roi = 0
        
        if circle_mode:
            circle_center = (rx + rw / 2, ry + rh / 2)
            circle_r = min(rw, rh) / 2
            for kp in pts:
                if (kp.x - circle_center[0]) ** 2 + (kp.y - circle_center[1]) ** 2 <= circle_r**2:
                    pts_roi += 1
        else:
            for kp in pts:
                if rx <= kp.x <= rx + rw and ry <= kp.y <= ry + rh:
                    pts_roi += 1
        
        return pts_roi, roi_area_um2
