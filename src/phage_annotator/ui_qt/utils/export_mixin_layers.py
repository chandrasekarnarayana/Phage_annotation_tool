"""Extracted method group 9 for ExportMixin."""

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




class ExportMixinLayersMixin:
    """Method group 9 extracted from ExportMixin."""

    def _apply_roi_mask_clip(
        self,
        image: np.ndarray,
        frame: np.ndarray,
        roi_rect,
        roi_shape: str,
        opts: ExportOptions,
        offset,
    ):
        """Apply roi mask clip for the current workflow."""
        if not opts.roi_mask_clip or roi_rect is None:
            return image
        mask = np.ones(frame.shape, dtype=bool)
        rx, ry, rw, rh = roi_rect
        rx -= offset[0]
        ry -= offset[1]
        rx = max(0, rx)
        ry = max(0, ry)
        if roi_shape == "circle":
            cx, cy = rx + rw / 2, ry + rh / 2
            r = min(rw, rh) / 2
            yy, xx = np.ogrid[: frame.shape[0], : frame.shape[1]]
            mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r**2
        else:
            x0 = int(max(0, rx))
            y0 = int(max(0, ry))
            x1 = int(min(frame.shape[1], rx + rw))
            y1 = int(min(frame.shape[0], ry + rh))
            mask = np.zeros(frame.shape, dtype=bool)
            mask[y0:y1, x0:x1] = True
        if image.shape[-1] == 4:
            if opts.transparent_bg:
                image[..., 3] = np.where(mask, image[..., 3], 0)
            else:
                image[~mask] = 0
        return image
    def _export_layers(
        self,
        base_path: pathlib.Path,
        frame: np.ndarray,
        cmap,
        norm,
        annotation_points,
        annotation_labels,
        roi_overlays,
        particle_overlays,
        overlay_text,
        scalebar_spec,
        pixel_size_um,
        opts: ExportOptions,
    ) -> None:
        """Export each overlay as a separate PNG file with alpha channel (P3.4).
        
        Creates files like:
        - base_t0000_base.png (base image)
        - base_t0000_annotations.png (annotations with alpha)
        - base_t0000_roi.png (ROI with alpha)
        - base_t0000_particles.png (particles with alpha)
        - base_t0000_scalebar.png (scalebar with alpha)
        """
        stem = base_path.stem
        parent = base_path.parent
        image_shape = frame.shape[:2]
        
        # Always export base layer
        if not opts.overlay_only:
            base_layer = render_layer_to_array(
                image_shape,
                layer_type="base",
                cmap=cmap,
                norm=norm,
                image=frame,
                options=opts,
            )
            base_file = parent / f"{stem}_base.png"
            _save_image(base_file, base_layer, opts)
        
        # Export annotations layer
        if opts.include_annotations and annotation_points:
            ann_layer = render_layer_to_array(
                image_shape,
                layer_type="annotations",
                annotations=annotation_points,
                annotation_labels=annotation_labels if opts.include_annotation_labels else [],
                options=opts,
            )
            ann_file = parent / f"{stem}_annotations.png"
            _save_image(ann_file, ann_layer, opts)
        
        # Export ROI layer
        if (opts.include_roi_outline or opts.include_roi_fill) and roi_overlays:
            roi_layer = render_layer_to_array(
                image_shape,
                layer_type="roi",
                roi_overlays=roi_overlays,
                options=opts,
            )
            roi_file = parent / f"{stem}_roi.png"
            _save_image(roi_file, roi_layer, opts)
        
        # Export particles layer
        if opts.include_particles and particle_overlays:
            particles_layer = render_layer_to_array(
                image_shape,
                layer_type="particles",
                particle_overlays=particle_overlays,
                options=opts,
            )
            particles_file = parent / f"{stem}_particles.png"
            _save_image(particles_file, particles_layer, opts)
        
        # Export scalebar layer
        if opts.include_scalebar and scalebar_spec:
            scalebar_layer = render_layer_to_array(
                image_shape,
                layer_type="scalebar",
                scalebar_spec=scalebar_spec,
                pixel_size_um=pixel_size_um,
                options=opts,
            )
            scalebar_file = parent / f"{stem}_scalebar.png"
            _save_image(scalebar_file, scalebar_layer, opts)
        
        # Export text overlay layer
        if opts.include_overlay_text and overlay_text:
            text_layer = render_layer_to_array(
                image_shape,
                layer_type="text",
                overlay_text=overlay_text,
                options=opts,
            )
            text_file = parent / f"{stem}_text.png"
            _save_image(text_file, text_layer, opts)
    def _export_frame_path(
        self, base: pathlib.Path, t_idx: int, opts: ExportOptions, *, multiple: bool
    ) -> pathlib.Path:
        """Export frame path for the current workflow."""
        if not multiple:
            return base
        stem = base.stem
        return base.with_name(f"{stem}_t{t_idx:04d}{base.suffix}")
