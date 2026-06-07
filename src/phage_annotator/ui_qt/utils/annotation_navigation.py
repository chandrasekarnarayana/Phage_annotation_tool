"""Extracted method group 5 for TableStatusMixin."""

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



class AnnotationMetadataActionsMixin:
    """Method group 5 extracted from TableStatusMixin."""

    def _point_in_roi(self, x: float, y: float) -> bool:
        """Handle the point in roi helper flow."""
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
        """Handle the current keypoints helper flow."""
        target = str(getattr(self, "annotate_target", "frame")).strip().lower() or "frame"
        if hasattr(getattr(self, "controller", None), "annotations_for_panel"):
            pts = list(self.controller.annotations_for_panel(target))
        else:
            primary_id = int(getattr(getattr(self, "primary_image", None), "id", 0))
            pts = list(getattr(self, "annotations", {}).get(primary_id, []))
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
        
        return pts
    def _jump_to_table_suggestion(self, suggestion_id: str) -> None:
        """Handle the jump to table suggestion helper flow."""
        for suggestion in self._suggestions_for_current_tz():
            if str(getattr(suggestion, "suggestion_id", "")) == str(suggestion_id):
                self._selected_suggestion_id = str(suggestion_id)
                self._focus_suggestion(suggestion)
                self._refresh_suggestion_explain_panel(suggestion)
                self._request_ui_refresh("table-jump-suggestion", image=True, table=True)
                return
    def _jump_to_table_annotation(self, annotation_id: str) -> None:
        """Handle the jump to table annotation helper flow."""
        for kp in self.annotations.get(self.primary_image.id, []):
            if str(getattr(kp, "annotation_id", "")) != str(annotation_id):
                continue
            if hasattr(self, "t_slider") and int(kp.t) >= 0:
                self.t_slider.setValue(max(self.t_slider.minimum(), min(int(kp.t), self.t_slider.maximum())))
            if hasattr(self, "z_slider") and int(kp.z) >= 0:
                self.z_slider.setValue(max(self.z_slider.minimum(), min(int(kp.z), self.z_slider.maximum())))
            self._selected_annotation_ids = {str(annotation_id)}
            self._request_ui_refresh("table-jump-annotation", image=True, table=True)
            return
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
        """Restore zoom for the current workflow."""
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
        """Handle the capture zoom state helper flow."""
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
        """Handle the valid zoom helper flow."""
        if xlim[0] == xlim[1] or ylim[0] == ylim[1]:
            return False
        if any(np.isnan(xlim)) or any(np.isnan(ylim)):
            return False
        return True
