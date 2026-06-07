"""Extracted method group 6 for ExportMixin."""

from __future__ import annotations

import base64
import pathlib
import re
from datetime import datetime
from typing import Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis.core import compute_projection
from phage_annotator.core.workspace_snapshot import (
    build_workspace_snapshot,
    extract_ui_workspace_state,
    workspace_layer_registry,
)
from phage_annotator.io.metadata.annotation import format_tokens
from phage_annotator.data.display_mapping import build_norm
from phage_annotator.ui_qt.rendering.export_view import (
    ExportOptions, render_view_to_array, render_layer_to_array,
    render_chunk_to_array, calculate_export_chunks, create_streaming_writer
)
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.rendering.lut_manager import cmap_for
from phage_annotator.rendering.scalebar import ScaleBarSpec




class ExportMixinViewExportMixin:
    """Method group 6 extracted from ExportMixin."""

    def _export_view_dialog(self) -> None:
        """Export view dialog for the current workflow."""
        if self.primary_image.array is None:
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Export View")
        dlg.setObjectName("export_dialog")
        layout = QtWidgets.QFormLayout(dlg)
        panel_combo = QtWidgets.QComboBox()
        panel_combo.setObjectName("export_dialog_combo_panel")
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        if not panel_map and hasattr(self, "_current_layout_spec"):
            try:
                self._current_layout_spec()
            except Exception:
                pass
            panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        panel_visibility = dict(getattr(self, "_panel_visibility", {}) or {})
        added = 0
        for key, modality in panel_map.items():
            if not str(key).startswith("modality_"):
                continue
            if not bool(panel_visibility.get(str(key), False)):
                continue
            label = str(getattr(modality, "display_name", key))
            panel_combo.addItem(label, str(key))
            added += 1
        if added <= 0:
            for key, modality in panel_map.items():
                if not str(key).startswith("modality_"):
                    continue
                label = str(getattr(modality, "display_name", key))
                panel_combo.addItem(label, str(key))
                added += 1
        if added <= 0:
            panel_combo.addItem("Modality 1", "modality_0")
        default_target = str(
            getattr(
                self,
                "annotate_target",
                self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0",
            )
        ).strip()
        idx = panel_combo.findData(default_target)
        if idx >= 0:
            panel_combo.setCurrentIndex(idx)
        scope_combo = QtWidgets.QComboBox()
        scope_combo.setObjectName("export_dialog_combo_scope")
        scope_combo.addItems(["Current slice", "T range", "All frames"])
        t_start = QtWidgets.QSpinBox()
        t_start.setObjectName("export_dialog_spinbox_t_start")
        t_end = QtWidgets.QSpinBox()
        t_end.setObjectName("export_dialog_spinbox_t_end")
        t_start.setRange(0, max(0, self.primary_image.array.shape[0] - 1))
        t_end.setRange(0, max(0, self.primary_image.array.shape[0] - 1))
        t_start.setValue(self.t_slider.value())
        t_end.setValue(self.t_slider.value())
        region_combo = QtWidgets.QComboBox()
        region_combo.setObjectName("export_dialog_combo_region")
        region_combo.addItems(["Full view", "Crop", "ROI bounds", "ROI mask-clipped"])
        roi_outline_chk = QtWidgets.QCheckBox("ROI outline")
        roi_outline_chk.setObjectName("export_dialog_checkbox_roi_outline")
        roi_outline_chk.setChecked(bool(self.roi_rect))
        roi_fill_chk = QtWidgets.QCheckBox("ROI fill")
        roi_fill_chk.setObjectName("export_dialog_checkbox_roi_fill")
        ann_chk = QtWidgets.QCheckBox("Annotation points")
        ann_chk.setObjectName("export_dialog_checkbox_annotations")
        ann_chk.setChecked(True)
        ann_label_chk = QtWidgets.QCheckBox("Annotation labels")
        ann_label_chk.setObjectName("export_dialog_checkbox_annotation_labels")
        particle_chk = QtWidgets.QCheckBox("Particle outlines")
        particle_chk.setObjectName("export_dialog_checkbox_particles")
        scalebar_chk = QtWidgets.QCheckBox("Scale bar")
        scalebar_chk.setObjectName("export_dialog_checkbox_scalebar")
        scalebar_chk.setChecked(self.scale_bar_enabled and self.scale_bar_include_in_export)
        overlay_text_chk = QtWidgets.QCheckBox("Overlay text")
        overlay_text_chk.setObjectName("export_dialog_checkbox_overlay_text")
        marker_spin = QtWidgets.QDoubleSpinBox()
        marker_spin.setObjectName("export_dialog_spinbox_marker_size")
        marker_spin.setRange(1.0, 200.0)
        marker_spin.setValue(float(self.marker_size))
        roi_lw_spin = QtWidgets.QDoubleSpinBox()
        roi_lw_spin.setObjectName("export_dialog_spinbox_roi_linewidth")
        roi_lw_spin.setRange(0.5, 6.0)
        roi_lw_spin.setValue(1.5)
        dpi_spin = QtWidgets.QSpinBox()
        dpi_spin.setObjectName("export_dialog_spinbox_dpi")
        dpi_spin.setRange(72, 600)
        dpi_spin.setValue(150)
        fmt_combo = QtWidgets.QComboBox()
        fmt_combo.setObjectName("export_dialog_combo_format")
        fmt_combo.addItems(["PNG", "TIFF"])
        overlay_only_chk = QtWidgets.QCheckBox("Overlay only (transparent)")
        overlay_only_chk.setObjectName("export_dialog_checkbox_overlay_only")
        transparent_chk = QtWidgets.QCheckBox("Transparent background")
        transparent_chk.setObjectName("export_dialog_checkbox_transparent")
        transparent_chk.setChecked(True)
        # P3.4: Export as separate layer files
        export_layers_chk = QtWidgets.QCheckBox("Export as separate layers")
        export_layers_chk.setObjectName("export_dialog_checkbox_layers")
        export_layers_chk.setToolTip("Generate separate PNG files for base image, annotations, ROI, particles, and scalebar with alpha channel")

        layout.addRow("Panel", panel_combo)
        layout.addRow("Scope", scope_combo)
        range_row = QtWidgets.QHBoxLayout()
        range_row.addWidget(QtWidgets.QLabel("Start"))
        range_row.addWidget(t_start)
        range_row.addWidget(QtWidgets.QLabel("End"))
        range_row.addWidget(t_end)
        layout.addRow("T range", range_row)
        layout.addRow("Region", region_combo)
        layout.addRow(roi_outline_chk)
        layout.addRow(roi_fill_chk)
        layout.addRow(ann_chk)
        layout.addRow(ann_label_chk)
        layout.addRow(particle_chk)
        layout.addRow(scalebar_chk)
        layout.addRow(overlay_text_chk)
        layout.addRow("Marker size", marker_spin)
        layout.addRow("ROI line width", roi_lw_spin)
        layout.addRow("DPI", dpi_spin)
        layout.addRow("Format", fmt_combo)
        layout.addRow(overlay_only_chk)
        layout.addRow(transparent_chk)
        layout.addRow(export_layers_chk)  # P3.4
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setObjectName("export_dialog_buttonbox")
        layout.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        fmt = fmt_combo.currentText().lower()
        default_name = pathlib.Path(self.primary_image.path).with_suffix(f".export.{fmt}")
        panel_key = str(panel_combo.currentData() or panel_combo.currentText() or "").strip()
        opts = ExportOptions(
            panel=panel_key,
            region=region_combo.currentText().lower(),
            include_roi_outline=roi_outline_chk.isChecked(),
            include_roi_fill=roi_fill_chk.isChecked(),
            include_annotations=ann_chk.isChecked(),
            include_annotation_labels=ann_label_chk.isChecked(),
            include_particles=particle_chk.isChecked(),
            include_scalebar=scalebar_chk.isChecked(),
            include_overlay_text=overlay_text_chk.isChecked(),
            marker_size=float(marker_spin.value()),
            roi_line_width=float(roi_lw_spin.value()),
            dpi=int(dpi_spin.value()),
            fmt=fmt,
            overlay_only=overlay_only_chk.isChecked(),
            transparent_bg=transparent_chk.isChecked(),
            export_as_layers=export_layers_chk.isChecked(),  # P3.4
            roi_mask_clip=region_combo.currentText().lower() == "roi mask-clipped",
        )
        scope = scope_combo.currentText()
        t_values = self._export_t_values(scope, t_start.value(), t_end.value())

        # P1.5: Export guardrails and preflight validation
        # 1) ROI-based region requires a valid ROI
        if opts.region in ("roi bounds", "roi mask-clipped"):
            if self.roi_shape == "none" or self.roi_rect[2] <= 0 or self.roi_rect[3] <= 0:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Export blocked",
                    "ROI region requested but no valid ROI is set.",
                )
                return
        # 2) Overlay-only requires at least one overlay to be selected
        if opts.overlay_only:
            has_any_overlay = (
                opts.include_roi_outline
                or opts.include_roi_fill
                or opts.include_annotations
                or opts.include_annotation_labels
                or opts.include_particles
                or opts.include_scalebar
                or opts.include_overlay_text
            )
            if not has_any_overlay:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Export blocked",
                    "Overlay-only is selected but no overlays are enabled.",
                )
                return
        # 3) Ensure we actually have frames to export
        if not t_values:
            QtWidgets.QMessageBox.warning(
                self,
                "Export blocked",
                "No frames selected for export.",
            )
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export View", str(default_name))
        if not path:
            return
        self._export_view_job(pathlib.Path(path), t_values, opts)
