"""Analysis, detection, scoring, and interactive learning actions."""

from __future__ import annotations

import csv
import gc
import logging
import pathlib
import time
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_roi_mean_for_path, fit_bleach_curve
from phage_annotator.analysis.interactive_learning import InteractiveLearningModel
from phage_annotator.analysis.suggestion_rules import load_suggestion_rule_config
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions import assist_generation, assist_review, assist_training
from phage_annotator.ui_qt.utils.debug import debug_log

logger = logging.getLogger(__name__)

class ActionsPipelineBatchMixin:
    """Mixin for analysis, detection, calibration, and interactive learning actions."""

    # ── Modal consensus ────────────────────────────────────────────────────:
    """Mixin extracted from ActionsMixinAnalysis."""
    pass

    def _batch_correct_suggestions_dialog(self) -> None:
        """Apply a constant (dx, dy) correction to top-N uncertain suggestions."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions to batch-correct.",
                timeout_ms=2500,
                source="standard.batch_correct",
            )
            return
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Batch Correct Suggestions")
        layout = QtWidgets.QFormLayout(dialog)
        n_spin = QtWidgets.QSpinBox(dialog)
        n_spin.setRange(1, len(ranked))
        n_spin.setValue(min(25, len(ranked)))
        dx_spin = QtWidgets.QDoubleSpinBox(dialog)
        dx_spin.setRange(-500.0, 500.0)
        dx_spin.setDecimals(2)
        dx_spin.setValue(0.0)
        dy_spin = QtWidgets.QDoubleSpinBox(dialog)
        dy_spin.setRange(-500.0, 500.0)
        dy_spin.setDecimals(2)
        dy_spin.setValue(0.0)
        layout.addRow("Select top-N uncertain:", n_spin)
        layout.addRow("Offset dx (pixels):", dx_spin)
        layout.addRow("Offset dy (pixels):", dy_spin)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        layout.addRow(btns)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        if dialog.exec() != int(QtWidgets.QDialog.DialogCode.Accepted):
            return
        self._apply_batch_suggestion_offset(
            count=int(n_spin.value()),
            dx=float(dx_spin.value()),
            dy=float(dy_spin.value()),
        )

    def _apply_batch_suggestion_offset(self, *, count: int, dx: float, dy: float) -> None:
        """Apply (dx, dy) to first `count` uncertain suggestions and log correction signal."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions to batch-correct.",
                timeout_ms=2500,
                source="standard.batch_correct",
            )
            return
        rows = list(ranked[: max(0, int(count))])
        if not rows:
            self._status_info(
                "No suggestions selected for batch correction.",
                timeout_ms=2500,
                source="standard.batch_correct",
            )
            return
        moved = 0
        h = int(self.primary_image.array.shape[2]) if getattr(self.primary_image, "array", None) is not None else None
        w = int(self.primary_image.array.shape[3]) if getattr(self.primary_image, "array", None) is not None else None
        for suggestion in rows:
            old_x = float(suggestion.x)
            old_y = float(suggestion.y)
            new_x = old_x + float(dx)
            new_y = old_y + float(dy)
            if w is not None:
                new_x = float(max(0.0, min(float(w - 1), new_x)))
            if h is not None:
                new_y = float(max(0.0, min(float(h - 1), new_y)))
            suggestion.x = new_x
            suggestion.y = new_y
            suggestion.meta["batch_corrected"] = True
            suggestion.meta["batch_dx"] = float(dx)
            suggestion.meta["batch_dy"] = float(dy)
            suggestion.meta["batch_shift_distance"] = float((dx * dx + dy * dy) ** 0.5)
            if hasattr(self.controller, "observe_suggestion_correction"):
                self.controller.observe_suggestion_correction(suggestion, dx=dx, dy=dy)
            self.controller.update_suggestion_metrics(
                correction_distance=float((new_x - old_x) ** 2 + (new_y - old_y) ** 2) ** 0.5
            )
            moved += 1
        self.controller.append_audit_event(
            "suggestions_batch_corrected",
            image_id=self.primary_image.id,
            count=int(moved),
            dx=float(dx),
            dy=float(dy),
        )
        self._request_ui_refresh("standard-actions")
        self._refresh_assist_warmup_panel()
        self._status_success(
            f"Batch-corrected {moved} suggestion(s) with dx={dx:.2f}, dy={dy:.2f}.",
            timeout_ms=3000,
            source="standard.batch_correct",
        )

    def _apply_review_queue_offset(self, count: int, dx: float, dy: float) -> None:
        """Apply inline review-queue XY offset controls without opening a modal."""
        self._apply_batch_suggestion_offset(count=int(count), dx=float(dx), dy=float(dy))

    def _propagate_suggestions_remaining_dialog(self) -> None:
        """Generate suggestions in remaining T/Z slices as a background task."""
        image = self.primary_image
        arr = getattr(image, "array", None)
        if arr is None or getattr(arr, "ndim", 0) < 4:
            self._status_warning(
                "No stack loaded for propagation.",
                timeout_ms=2500,
                source="standard.propagate",
            )
            return
        modes = (
            "remaining_t_current_z",
            "remaining_z_current_t",
            "remaining_tz",
        )
        labels = {
            "remaining_t_current_z": "Remaining T at current Z",
            "remaining_z_current_t": "Remaining Z at current T",
            "remaining_tz": "Remaining T/Z (grid)",
        }
        mode, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Propagate Suggestions",
            "Scope:",
            [labels[m] for m in modes],
            0,
            False,
        )
        if not ok:
            return
        mode_key = next((k for k, v in labels.items() if v == str(mode)), "remaining_t_current_z")
        t0 = int(self.t_slider.value())
        z0 = int(self.z_slider.value())
        t_size = int(arr.shape[0])
        z_size = int(arr.shape[1])
        targets: list[tuple[int, int]] = []
        if mode_key == "remaining_t_current_z":
            targets = [(t, z0) for t in range(t0, t_size)]
        elif mode_key == "remaining_z_current_t":
            targets = [(t0, z) for z in range(z0, z_size)]
        else:
            for t in range(t0, t_size):
                for z in range(z_size):
                    if t == t0 and z < z0:
                        continue
                    targets.append((t, z))
        if not targets:
            self._status_info(
                "No remaining slices to propagate.",
                timeout_ms=2500,
                source="standard.propagate",
            )
            return

        image_id = int(image.id)
        image_name = str(image.name)
        label = str(self.current_label)
        strategy = str(getattr(self, "_suggestion_strategy", "current_view"))
        roi_shape = str(self.roi_shape)
        roi_rect = tuple(self.roi_rect)

        def _job(progress, cancel_token):
            """Handle the job helper flow."""
            out: list[PointSuggestion] = []
            total = max(1, len(targets))
            for idx, (t_idx, z_idx) in enumerate(targets):
                if cancel_token.is_cancelled():
                    return None
                frame = np.asarray(arr[t_idx, z_idx, :, :], dtype=np.float32)
                generated = self._suggestion_model.predict(
                    frame,
                    image_id=image_id,
                    image_name=image_name,
                    t=int(t_idx),
                    z=int(z_idx),
                    label=label,
                    strategy=strategy,
                    roi_shape=roi_shape,
                    roi_rect=roi_rect,
                )
                out.extend(generated)
                progress(int((idx + 1) / total * 100), f"{idx + 1}/{total} slices")
            return out

        def _on_result(result):
            """Handle the on result helper flow."""
            if result is None:
                self._status_info(
                    "Suggestion propagation cancelled.",
                    timeout_ms=2500,
                    source="standard.propagate",
                )
                return
            generated = list(result)
            for suggestion in generated:
                frame = np.asarray(arr[int(suggestion.t), int(suggestion.z), :, :], dtype=np.float32)
                self._enrich_suggestions_for_training([suggestion], frame)
            generated = self._rank_and_calibrate_suggestions(generated)
            generated_at = float(time.time())
            for suggestion in generated:
                suggestion.meta["generated_at_ts"] = generated_at
            self.controller.append_generated_suggestions(image_id, generated, sort_pending=True)
            self.controller.update_suggestion_metrics(generated=len(generated))
            self.controller.append_audit_event(
                "suggestions_propagated_remaining",
                image_id=image_id,
                count=len(generated),
                mode=str(mode_key),
                strategy=strategy,
            )
            self._remember_generation_context(generated)
            if generated:
                first = generated[0]
                self.t_slider.setValue(max(self.t_slider.minimum(), min(int(first.t), self.t_slider.maximum())))
                self.z_slider.setValue(max(self.z_slider.minimum(), min(int(first.z), self.z_slider.maximum())))
            self._request_ui_refresh("standard-actions")
            self._refresh_assist_warmup_panel()
            self._status_success(
                f"Propagated {len(generated)} suggestions across remaining slices.",
                timeout_ms=3500,
                source="standard.propagate",
            )

        self._submit_analysis_job(
            _job,
            name="Propagate suggestions",
            on_result=_on_result,
        )
