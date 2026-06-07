"""Extracted method group 8 for ExportMixin."""

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




class AnnotationIoMixin:
    """Method group 8 extracted from ExportMixin."""

    def _export_view_job_chunked(
        self, frame, offset, t_idx, z_idx, cmap, norm,
        annotation_points, annotation_labels, roi_overlays, particle_overlays,
        overlay_text, scalebar_spec, pixel_size_um, opts,
        base_path, total, idx, progress, cancel_token
    ) -> None:
        """Export frame using streaming chunk-based approach (P4a).
        
        Parameters
        ----------
        frame : ndarray
            Frame data
        offset : tuple
            ROI offset
        t_idx : int
            Time index
        z_idx : int
            Z index
        cmap : matplotlib colormap
            Color map
        norm : matplotlib norm
            Normalization
        annotation_points : list
            Point annotations
        annotation_labels : list
            Annotation labels
        roi_overlays : list
            ROI overlay items
        particle_overlays : list
            Particle overlay items
        overlay_text : str
            Overlay text
        scalebar_spec : ScaleBarSpec
            Scalebar specification
        pixel_size_um : float
            Pixel size in micrometers
        opts : ExportOptions
            Export options
        base_path : pathlib.Path
            Base export path
        total : int
            Total frames
        idx : int
            Current frame index
        progress : callable
            Progress callback
        cancel_token : CancelToken
            Cancellation token
        """
        out_path = self._export_frame_path(
            base_path, t_idx, opts, multiple=total > 1
        )
        
        # Create streaming writer
        image_shape = frame.shape
        writer = create_streaming_writer(opts.fmt, out_path, image_shape)
        
        # Calculate chunks
        chunks = calculate_export_chunks(image_shape, chunk_size=256)
        num_chunks = len(chunks)
        
        # Render and write each chunk
        for chunk_idx, (x0, y0, x1, y1) in enumerate(chunks):
            if cancel_token.is_cancelled():
                return None
            
            # Render chunk with filtered overlays
            chunk = render_chunk_to_array(
                frame,
                crop_box=(x0, y0, x1, y1),
                cmap=cmap,
                norm=norm,
                overlays=[],
                annotations=annotation_points,
                annotation_labels=annotation_labels,
                roi_overlays=roi_overlays,
                particle_overlays=particle_overlays,
                overlay_text=overlay_text,
                scalebar_spec=scalebar_spec,
                pixel_size_um=pixel_size_um,
                options=opts,
            )
            
            # Write chunk
            writer.write_chunk(chunk, (y0, x0))
            
            # Update progress with chunk progress
            chunk_progress = int((chunk_idx + 1) / num_chunks * 100)
            frame_progress = int((idx + chunk_progress / 100) / total * 100)
            progress(frame_progress, f"{idx + 1}/{total} (chunk {chunk_idx + 1}/{num_chunks})")
        
        # Finalize writer
        writer.finalize()
    def _export_panel_frame(self, t_idx: int, z_idx: int, panel: str, crop_rect):
        """Export panel frame for the current workflow."""
        panel_key = str(panel or "").strip()
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        modality = panel_map.get(panel_key)
        if modality is None:
            return None
        img = self._image_obj_from_id(int(getattr(modality, "image_id", -1)))
        if img is None:
            return None
        if img.array is None:
            self._ensure_loaded(img.id)
            if img.array is None:
                return None
        projection = str(getattr(getattr(modality, "projection_type", None), "value", "raw")).strip().lower()
        axis = str(
            getattr(getattr(modality, "display_settings", None), "projection_axis", "t")
        ).strip().lower()
        if projection == "raw":
            data = self._build_multichannel_frame(img, t_idx, z_idx)
            if data is None:
                t_safe = max(0, min(int(t_idx), int(img.array.shape[0]) - 1))
                z_safe = max(0, min(int(z_idx), int(img.array.shape[1]) - 1))
                data = img.array[t_safe, z_safe, :, :]
        else:
            data = compute_projection(np.asarray(img.array), projection, axis=axis)
        return self._apply_crop_rect(data, crop_rect, data.shape)
    def _apply_roi_region(
        self, frame: np.ndarray, roi_rect, roi_shape: str, region: str, crop_rect
    ):
        """Apply roi region for the current workflow."""
        offset = (crop_rect[0], crop_rect[1]) if crop_rect else (0.0, 0.0)
        if roi_rect is None:
            return frame, offset
        if region not in ("roi bounds", "roi mask-clipped"):
            return frame, offset
        x, y, w, h = roi_rect
        x0 = int(max(0, x - offset[0]))
        y0 = int(max(0, y - offset[1]))
        x1 = int(min(frame.shape[1], x0 + w))
        y1 = int(min(frame.shape[0], y0 + h))
        return frame[y0:y1, x0:x1], (offset[0] + x0, offset[1] + y0)
    def _export_annotations(self, t_idx: int, offset, opts: ExportOptions):
        """Export annotations for the current workflow."""
        if not opts.include_annotations:
            return []
        points = []
        for kp in self._current_keypoints():
            if kp.t not in (-1, t_idx) or kp.z not in (-1, self.z_slider.value()):
                continue
            x = kp.x - offset[0]
            y = kp.y - offset[1]
            points.append((x, y, self._label_color(kp.label, faded=False), kp.label))
        return points
    def _export_annotation_labels(self, annotations, opts: ExportOptions):
        """Export annotation labels for the current workflow."""
        if not opts.include_annotation_labels:
            return []
        return [(x, y, label) for x, y, _, label in annotations]
    def _export_roi_overlays(self, offset, opts: ExportOptions):
        """Export roi overlays for the current workflow."""
        overlays = []
        roi_active = self.roi_shape != "none" and self.roi_rect[2] > 0 and self.roi_rect[3] > 0
        if roi_active and (opts.include_roi_outline or opts.include_roi_fill):
            x, y, w, h = self.roi_rect
            rect = (x - offset[0], y - offset[1], w, h)
            if self.roi_shape == "circle":
                overlays.append(("circle", rect, "#00c0ff"))
            else:
                overlays.append(("box", rect, "#00c0ff"))
        return overlays
