"""Extracted method group 4 for ThresholdControlsMixin."""

from __future__ import annotations

import csv
from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis.core import roi_mask_for_shape
from phage_annotator.analysis.particles import ParticleOptions, analyze_particles
from phage_annotator.analysis.threshold import (
    PostprocessOptions,
    compute_threshold,
    make_mask,
    postprocess_mask,
    smooth_image,
)



class ThresholdControlsLogicMixin:
    """Method group 4 extracted from ThresholdControlsMixin."""

    def _export_particles_csv(self) -> None:
        """Export particles csv for the current workflow."""
        if not self._particles_results:
            self.particles_panel.status_label.setText("No particle results.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Particles CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "frame",
                    "area_px",
                    "perimeter_px",
                    "circularity",
                    "centroid_x",
                    "centroid_y",
                    "eq_diameter",
                    "bbox",
                ]
            )
            for p in self._particles_results:
                writer.writerow(
                    [
                        p.frame_index,
                        p.area_px,
                        f"{p.perimeter_px:.3f}",
                        f"{p.circularity:.3f}",
                        f"{p.centroid_x:.3f}",
                        f"{p.centroid_y:.3f}",
                        f"{p.eq_diameter:.3f}",
                        p.bbox,
                    ]
                )
        self.particles_panel.status_label.setText(f"Exported CSV: {path}")
    def _particles_create_selection(self) -> None:
        """Handle the particles create selection helper flow."""
        if not self._particles_results:
            self.particles_panel.status_label.setText("No particles to select.")
            return
        xs = []
        ys = []
        for p in self._particles_results:
            x, y, w, h = p.bbox
            xs.extend([x, x + w])
            ys.extend([y, y + h])
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        rect = (float(x0), float(y0), float(x1 - x0), float(y1 - y0))
        self.controller.set_roi(rect, shape="box")
        self.roi_shape = "box"
        self.roi_rect = rect
        self._sync_roi_controls()
        self._request_ui_refresh("threshold-controls")
    def _offset_particle(self, particle, dx: int, dy: int):
        """Handle the offset particle helper flow."""
        bbox = particle.bbox
        outline = None
        if particle.outline:
            outline = [(x + dx, y + dy) for x, y in particle.outline]
        return type(particle)(
            frame_index=particle.frame_index,
            area_px=particle.area_px,
            perimeter_px=particle.perimeter_px,
            circularity=particle.circularity,
            centroid_x=particle.centroid_x + dx,
            centroid_y=particle.centroid_y + dy,
            bbox=(bbox[0] + dx, bbox[1] + dy, bbox[2], bbox[3]),
            eq_diameter=particle.eq_diameter,
            outline=outline,
        )
    def _particles_log_message(self, particles, opts: ParticleOptions) -> str:
        """Handle the particles log message helper flow."""
        return (
            "[Particles] count={count} min_area={min_area} max_area={max_area} "
            "circ={cmin:.2f}-{cmax:.2f} exclude_edges={edge} watershed={ws}"
        ).format(
            count=len(particles),
            min_area=opts.min_area_px,
            max_area=opts.max_area_px if opts.max_area_px is not None else "inf",
            cmin=opts.min_circularity,
            cmax=opts.max_circularity,
            edge=opts.exclude_edges,
            ws=opts.watershed_split,
        )
    def _threshold_log_message(self, values, thr_value: Optional[float]) -> str:
        """Handle the threshold log message helper flow."""
        thr = thr_value if thr_value is not None else float("nan")
        return (
            "[Threshold] method={method} thr={thr:.4f} region_roi={roi} scope={scope} "
            "invert={invert} smooth={smooth:.2f} post(min={min_area}, open={open_r}, close={close_r}, "
            "holes={holes}, ws={ws})"
        ).format(
            method=values.method,
            thr=thr,
            roi=values.region_roi,
            scope=values.scope,
            invert=values.invert_mask,
            smooth=values.smooth_sigma,
            min_area=values.min_area_px,
            open_r=values.open_radius_px,
            close_r=values.close_radius_px,
            holes=values.fill_holes,
            ws=values.watershed_split,
        )
