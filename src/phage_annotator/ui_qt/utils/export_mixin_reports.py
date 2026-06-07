"""Extracted method group 7 for ExportMixin."""

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




class ExportMixinReportsMixin:
    """Method group 7 extracted from ExportMixin."""

    def _export_t_values(self, scope: str, t_start: int, t_end: int) -> list[int]:
        """Export t values for the current workflow."""
        if scope == "Current slice":
            return [self.t_slider.value()]
        if scope == "All frames":
            return list(range(self.primary_image.array.shape[0]))
        if t_end < t_start:
            t_start, t_end = t_end, t_start
        return list(range(t_start, t_end + 1))
    def _export_view_job(
        self, base_path: pathlib.Path, t_values: list[int], opts: ExportOptions
    ) -> None:
        """Export view job for the current workflow."""
        prim = self.primary_image
        if prim.array is None:
            return
        z_idx = self.z_slider.value()
        cal = self._get_calibration_state(prim.id)
        scalebar_spec = ScaleBarSpec(
            enabled=opts.include_scalebar,
            length_um=self.scale_bar_length_um,
            thickness_px=self.scale_bar_thickness_px,
            location=self.scale_bar_location,
            padding_px=self.scale_bar_padding_px,
            show_text=self.scale_bar_show_text,
            text_offset_px=self.scale_bar_text_offset_px,
            background_box=self.scale_bar_background_box,
        )
        crop_rect = (
            self.crop_rect if opts.region in ("crop", "roi bounds", "roi mask-clipped") else None
        )
        roi_rect = self.roi_rect if opts.region in ("roi bounds", "roi mask-clipped") else None
        roi_shape = self.roi_shape

        def _job(progress, cancel_token):
            """Handle the job helper flow."""
            total = len(t_values)
            for idx, t_idx in enumerate(t_values):
                if cancel_token.is_cancelled():
                    return None
                frame = self._export_panel_frame(t_idx, z_idx, opts.panel, crop_rect)
                if frame is None:
                    continue
                frame, offset = self._apply_roi_region(
                    frame, roi_rect, roi_shape, opts.region, crop_rect
                )
                annotations = self._export_annotations(t_idx, offset, opts)
                annotation_labels = self._export_annotation_labels(annotations, opts)
                annotation_points = [(x, y, color) for x, y, color, _ in annotations]
                roi_overlays = self._export_roi_overlays(offset, opts)
                particle_overlays = (
                    self._particles_overlays
                    if opts.include_particles and t_idx == self.t_slider.value()
                    else []
                )
                overlay_text = self._build_overlay_text() if opts.include_overlay_text else None
                panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
                modality = panel_map.get(str(opts.panel))
                mapping_image_id = int(getattr(modality, "image_id", prim.id))
                mapping = self._get_display_mapping(mapping_image_id, opts.panel, frame)
                norm = build_norm(mapping)
                cmap = cmap_for(mapping.lut, mapping.invert)
                
                # P4: Check for streaming chunk-based export
                if opts.export_as_chunked:
                    self._export_view_job_chunked(
                        frame, offset, t_idx, z_idx, cmap, norm,
                        annotation_points, annotation_labels, roi_overlays, particle_overlays,
                        overlay_text, scalebar_spec, cal.pixel_size_um_per_px, opts,
                        base_path, total, idx, progress, cancel_token
                    )
                else:
                    image = render_view_to_array(
                        frame,
                        cmap=cmap,
                        norm=norm,
                        overlays=[],
                        annotations=annotation_points,
                        annotation_labels=annotation_labels,
                        roi_overlays=roi_overlays,
                        particle_overlays=particle_overlays,
                        overlay_text=overlay_text,
                        scalebar_spec=scalebar_spec if opts.include_scalebar else None,
                        pixel_size_um=cal.pixel_size_um_per_px,
                        options=opts,
                    )
                    image = self._apply_roi_mask_clip(image, frame, roi_rect, roi_shape, opts, offset)
                    out_path = self._export_frame_path(
                        base_path, t_idx, opts, multiple=len(t_values) > 1
                    )
                    
                    # P3.4: Export as separate layers if requested
                    if opts.export_as_layers:
                        self._export_layers(
                            out_path,
                            frame,
                            cmap,
                            norm,
                            annotation_points,
                            annotation_labels,
                            roi_overlays,
                            particle_overlays,
                            overlay_text,
                            scalebar_spec,
                            cal.pixel_size_um_per_px,
                            opts,
                        )
                    else:
                        _save_image(out_path, image, opts)
                
                progress(int((idx + 1) / max(1, total) * 100), f"{idx + 1}/{total}")
            return True

        self.jobs.submit(
            _job,
            name="Export view",
            timeout_sec=600.0,
            priority="normal",
            replace_key="export-view",
        )
