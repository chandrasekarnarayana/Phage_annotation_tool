"""Overlay and header-building helpers for rendering."""

from __future__ import annotations

import time
from typing import Dict, List, Tuple, Optional

import numpy as np

from phage_annotator.ui_qt.rendering.lut_manager import LUTS


class RenderingOverlayMixin:
    """Mixin for overlay, label, and header text generation."""

    def _visible_suggestion_overlay_rows(self) -> List[object]:
        if not bool(getattr(self, "_show_suggestion_overlay", True)):
            return []
        image_id = self.primary_image.id
        t_idx = int(self.t_slider.value()) if hasattr(self, "t_slider") else 0
        z_idx = int(self.z_slider.value()) if hasattr(self, "z_slider") else 0
        min_score = float(getattr(self, "_suggestion_score_threshold", 0.0))
        rows = list(
            self.controller.get_visible_suggestions(
                image_id,
                t_index=t_idx,
                z_index=z_idx,
                min_score=min_score,
            )
        )
        if hasattr(self, "_filter_suggestions_to_active_roi"):
            rows = list(self._filter_suggestions_to_active_roi(rows))
        selected_suggestion_id = str(getattr(self, "_selected_suggestion_id", "") or "")
        max_points = int(getattr(self, "_suggestion_overlay_limit", 24) or 24)
        if max_points > 0 and len(rows) > max_points:
            pinned = [
                suggestion
                for suggestion in rows
                if str(getattr(suggestion, "suggestion_id", "")) == selected_suggestion_id
            ]
            remaining = [
                suggestion
                for suggestion in rows
                if str(getattr(suggestion, "suggestion_id", "")) != selected_suggestion_id
            ]
            remaining.sort(
                key=lambda suggestion: float(
                    getattr(suggestion, "score", getattr(suggestion, "confidence", 0.0))
                ),
                reverse=True,
            )
            budget = max(0, max_points - len(pinned))
            rows = pinned[:1] + remaining[:budget]
        return rows

    def _particle_labels(self) -> List[Tuple[float, float, str]]:
        if self.particles_panel is None or not self.particles_panel.show_labels_chk.isChecked():
            return []
        frame_ax = None
        if getattr(self, "renderer", None) is not None:
            frame_ax = next(iter(self.renderer.axes.values()), None)
        scale = self._axis_scale(frame_ax) if frame_ax is not None else 1.0
        labels: List[Tuple[float, float, str]] = []
        for idx, particle in enumerate(self._particles_results):
            x = (particle.centroid_x - (self.crop_rect[0] if self.crop_rect else 0.0)) / scale
            y = (particle.centroid_y - (self.crop_rect[1] if self.crop_rect else 0.0)) / scale
            labels.append((x, y, str(idx + 1)))
        return labels

    def _build_panel_annotations(self) -> Dict[str, List[Tuple[float, float, str, bool, bool]]]:
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        show_all_annotations = bool(
            getattr(getattr(self, "show_ann_master_chk", None), "isChecked", lambda: True)()
        )
        points_visible_by_panel = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        suggestion_points: List[Tuple[float, float, str, bool, bool]] = []
        selected_suggestion_id = str(getattr(self, "_selected_suggestion_id", "") or "")
        for suggestion in self._visible_suggestion_overlay_rows():
            color, _state = self._suggestion_overlay_style(suggestion)
            suggestion_points.append(
                (
                    float(suggestion.x),
                    float(suggestion.y),
                    color,
                    str(getattr(suggestion, "suggestion_id", "")) == selected_suggestion_id,
                    False,
                )
            )
        panel_annotations: Dict[str, List[Tuple[float, float, str, bool, bool]]] = {}
        for panel in panel_map.keys():
            pts = []
            if show_all_annotations and bool(points_visible_by_panel.get(str(panel), True)):
                for kp in self.controller.annotations_for_panel(str(panel)):
                    source = str(getattr(kp, "source", "manual")).strip().lower()
                    if source.startswith("suggested:"):
                        color = "#1565c0"
                    else:
                        color = self._label_color(kp.label, faded=kp.image_id != self.primary_image.id)
                    selected_ids = getattr(self, "_selected_annotation_ids", set()) or set()
                    pts.append((kp.x, kp.y, color, str(kp.annotation_id) in selected_ids, True))
            if suggestion_points and str(panel) == str(next(iter(panel_map.keys()), "")):
                pts.extend(suggestion_points)
            if not pts:
                panel_annotations[panel] = []
                continue
            panel_ax = self.renderer.axes.get(panel) if getattr(self, "renderer", None) is not None else None
            scale = self._axis_scale(panel_ax) if panel_ax is not None else 1.0
            panel_annotations[panel] = [(x / scale, y / scale, c, s, f) for x, y, c, s, f in pts]
        return panel_annotations

    def _build_suggestion_staleness_labels(self) -> Dict[str, List[Tuple[float, float, str]]]:
        panel_keys = list(dict(getattr(self, "_panel_modality_map", {}) or {}).keys())
        labels: Dict[str, List[Tuple[float, float, str]]] = {str(k): [] for k in panel_keys}
        if not bool(getattr(self, "_show_suggestion_overlay", True)):
            return labels
        now_ts = float(time.time())
        frame_ax = None
        if getattr(self, "renderer", None) is not None:
            frame_ax = next(iter(self.renderer.axes.values()), None)
        scale = self._axis_scale(frame_ax) if frame_ax is not None else 1.0
        primary_panel = panel_keys[0] if panel_keys else ""
        for suggestion in self._visible_suggestion_overlay_rows():
            ts = dict(getattr(suggestion, "meta", {}) or {}).get("generated_at_ts")
            if ts is None:
                continue
            age_s = max(0.0, now_ts - float(ts))
            label = f"{int(round(age_s))}s" if age_s < 60.0 else f"{int(round(age_s / 60.0))}m"
            if primary_panel:
                labels[str(primary_panel)].append((float(suggestion.x) / scale, float(suggestion.y) / scale, label))
        return labels

    def _build_roi_overlays(self) -> Dict[str, List[Tuple[str, object, str]]]:
        overlays: Dict[str, List[Tuple[str, object, str]]] = {
            panel: [] for panel in dict(getattr(self, "_panel_modality_map", {}) or {}).keys()
        }
        show_current_slice_only = getattr(self, "_roi_show_current_slice_only", False)
        if show_current_slice_only:
            current_z = getattr(self.controller.view_state, "z", 0)
            current_t = getattr(self.controller.view_state, "t", 0)
            current_c = getattr(self.controller.view_state, "c", 0)
            rois = self.roi_manager.filter_rois_by_position(self.primary_image.id, z=current_z, t=current_t, c=current_c)
        else:
            rois = self.roi_manager.list_rois(self.primary_image.id)
        for roi in rois:
            if not roi.visible:
                continue
            for panel in overlays:
                panel_ax = self.renderer.axes.get(panel) if getattr(self, "renderer", None) is not None else None
                scale = self._axis_scale(panel_ax) if panel_ax is not None else 1.0
                if roi.roi_type == "circle" and len(roi.points) >= 2:
                    (cx, cy), (px, py) = roi.points[:2]
                    r = float(np.hypot(px - cx, py - cy))
                    rect = (cx - r, cy - r, 2 * r, 2 * r)
                    overlays[panel].append(("circle", (rect[0] / scale, rect[1] / scale, rect[2] / scale, rect[3] / scale), roi.color))
                elif roi.roi_type == "box" and len(roi.points) >= 2:
                    (x0, y0), (x1, y1) = roi.points[:2]
                    rect = (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
                    overlays[panel].append(("box", (rect[0] / scale, rect[1] / scale, rect[2] / scale, rect[3] / scale), roi.color))
                elif roi.roi_type in ("polygon", "polyline") and len(roi.points) >= 3:
                    overlays[panel].append((roi.roi_type, [(x / scale, y / scale) for x, y in roi.points], roi.color))
        if self.crop_rect:
            for panel in overlays:
                panel_ax = self.renderer.axes.get(panel) if getattr(self, "renderer", None) is not None else None
                scale = self._axis_scale(panel_ax) if panel_ax is not None else 1.0
                x, y, w, h = self.crop_rect
                overlays[panel].append(("box", (x / scale, y / scale, w / scale, h / scale), "#00c0ff"))
        return overlays

    def _build_overlay_text(self) -> Optional[str]:
        if not self.overlay_enabled:
            return None
        img = self.primary_image
        t_idx, z_idx = self._slice_indices(img)
        t_total = img.array.shape[0] if img.array is not None else 1
        z_total = img.array.shape[1] if img.array is not None else 1
        panel_key = self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
        mapping = self._get_display_mapping(img.id, panel_key, img.array)
        idx = max(0, min(mapping.lut, len(LUTS) - 1))
        lut = LUTS[idx].name
        inv = " (inv)" if mapping.invert else ""
        crop_txt = "yes" if self.crop_rect else "no"
        roi_active = self.roi_shape != "none" and self.roi_rect and self.roi_rect[2] > 0 and self.roi_rect[3] > 0
        roi_txt = "yes" if roi_active else "no"
        crop_rect = self.crop_rect if self.crop_rect else (0, 0, 0, 0)
        roi_rect = self.roi_rect if roi_active else (0, 0, 0, 0)
        cal = self._get_calibration_state(img.id)
        pixel_size = f"{cal.pixel_size_um_per_px:.4f} um/px" if cal.pixel_size_um_per_px else "unknown"
        diag_lines = []
        if img.downsampled:
            diag_lines.append(f"Spatial downsampling: {img.downsample_factor}x (memory pressure)")
        render_scales = getattr(self, "_render_scales", {}) or {}
        render_scale = max(render_scales.values()) if render_scales else 1
        if render_scale > 1:
            diag_lines.append(f"Interactive downsampling: {int(render_scale)}x")
        lod_active = getattr(self, "_lod_mode_active", {}) or {}
        if lod_active.get(img.id, False):
            diag_lines.append("LOD mode: computing full-resolution")
        diag_txt = "\n" + "\n".join(diag_lines) if diag_lines else ""
        stale_count = 0
        visible_suggestions = 0
        now_ts = float(time.time())
        for suggestion in self.suggestions.get(img.id, ()):
            if int(getattr(suggestion, "t", -1)) not in (t_idx, -1) or int(getattr(suggestion, "z", -1)) not in (z_idx, -1):
                continue
            visible_suggestions += 1
            ts = dict(getattr(suggestion, "meta", {}) or {}).get("generated_at_ts")
            if ts is not None and (now_ts - float(ts)) >= 300.0:
                stale_count += 1
        stale_txt = f"\nSuggestion staleness: {stale_count}/{visible_suggestions} >= 5m old" if visible_suggestions > 0 else ""
        stale_badge = ""
        if hasattr(self, "_suggestion_freshness_state"):
            try:
                freshness = self._suggestion_freshness_state(self.primary_image.id)
                if freshness.get("is_stale", False):
                    stale_badge = "\nStale - regenerate recommended"
            except Exception:
                stale_badge = ""
        return (
            f"{img.name}\n"
            f"T {t_idx + 1}/{t_total} | Z {z_idx + 1}/{z_total}\n"
            f"Pixel size: {pixel_size}\n"
            f"LUT: {lut}{inv} | Mode: {mapping.mode} | Gamma: {mapping.gamma:.2f}\n"
            f"vmin/vmax: {mapping.min_val:.3f}/{mapping.max_val:.3f}\n"
            f"Crop: {crop_txt} {crop_rect}\n"
            f"ROI: {roi_txt} {roi_rect}\n"
            f"Memmap: {'yes' if getattr(img.array, 'filename', None) else 'no'}{diag_txt}{stale_txt}{stale_badge}"
        )

    def _build_canvas_header_text(self) -> str:
        img = self.primary_image
        t_idx, z_idx = self._slice_indices(img)
        default_target = self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
        target = str(getattr(self, "annotate_target", default_target))
        scope = str(getattr(self, "annotation_scope", "current"))
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        spec = panel_map.get(target)
        target_key = str(target).strip().lower()
        if spec is not None:
            target_txt = str(getattr(spec, "display_name", target))
        elif target_key == "mean":
            z_total = int(getattr(getattr(img, "array", None), "shape", (1, 1, 1, 1))[1]) if getattr(img, "array", None) is not None and len(img.array.shape) >= 2 else int(z_idx) + 1
            target_txt = f"Mean Projection (Z=1-{z_total})"
        elif target_key == "std":
            z_total = int(getattr(getattr(img, "array", None), "shape", (1, 1, 1, 1))[1]) if getattr(img, "array", None) is not None and len(img.array.shape) >= 2 else int(z_idx) + 1
            target_txt = f"Std Projection (Z=1-{z_total})"
        else:
            target_txt = f"{str(target).title()} T={int(t_idx) + 1} Z={int(z_idx) + 1}"
        scope_txt = "Stack Annotation (All Z)" if scope == "all" else "Slice Annotation (Current Z)"
        lock_pending = bool(hasattr(self, "_is_annotation_context_guard_pending") and self._is_annotation_context_guard_pending())
        base_text = f"{target_txt} | {scope_txt}{' | Write Context: Pending Confirm' if lock_pending else ''}"
        if not bool(getattr(self, "_canvas_header_verbose_context", False)):
            return base_text
        strategy = str(getattr(self, "_suggestion_strategy", "current_view"))
        active_label = str(getattr(self, "current_label", "phage"))
        modality_txt = f"Modality {int(getattr(self, '_active_modality_idx', -1))}"
        manager = getattr(getattr(self, "controller", None).session_state, "modality_manager", None) if getattr(self, "controller", None) is not None else None
        if manager is not None:
            try:
                for modality in manager.get_all_modalities():
                    if int(modality.image_id) == int(self.primary_image.id):
                        modality_txt = str(modality.display_name)
                        break
            except Exception:
                pass
        projection_txt = "raw"
        if getattr(self, "projection_selector", None) is not None:
            try:
                p_name, p_axis = self.projection_selector.current_selection()
                projection_txt = f"{'source slice' if str(p_name).strip().lower() == 'raw' else p_name} ({p_axis})"
            except Exception:
                projection_txt = "source slice"
        return f"{base_text} | Modality: {modality_txt} ({projection_txt}) | Strategy: {strategy} | Label: {active_label}"
