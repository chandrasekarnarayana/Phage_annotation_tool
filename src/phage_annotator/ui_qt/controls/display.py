"""Display, playback, and general control handlers."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_auto_window
from phage_annotator.session.modality import ProjectionType
from phage_annotator.session.multi_playback import PlaybackMode
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, lut_names


class DisplayControlsMixin:
    """Mixin for display, playback, and general control handlers."""

    def _bc_value_from_slider(self, value: int) -> float:
        scale = float(getattr(self, "_bc_slider_scale", 1.0))
        if scale <= 0:
            return float(value)
        return float(value) / scale

    def _bc_slider_from_value(self, value: float) -> int:
        scale = float(getattr(self, "_bc_slider_scale", 1.0))
        return int(round(float(value) * scale))

    def _bc_set_controls(self, min_val: float, max_val: float) -> None:
        if getattr(self, "bc_min_spin", None) is None:
            return
        range_slider = getattr(self, "bc_range_slider", None)
        min_slider_widget = getattr(self, "bc_min_slider", None)
        max_slider_widget = getattr(self, "bc_max_slider", None)
        self._bc_updating_controls = True
        try:
            self.bc_min_spin.blockSignals(True)
            self.bc_max_spin.blockSignals(True)
            if min_slider_widget is not None:
                min_slider_widget.blockSignals(True)
            if max_slider_widget is not None:
                max_slider_widget.blockSignals(True)
            if range_slider is not None:
                range_slider.blockSignals(True)
            self.bc_min_spin.setValue(float(min_val))
            self.bc_max_spin.setValue(float(max_val))
            if range_slider is not None:
                range_slider.setValues(min_val, max_val, emit_signal=False)
            if min_slider_widget is not None and max_slider_widget is not None:
                min_slider = self._bc_slider_from_value(min_val)
                max_slider = self._bc_slider_from_value(max_val)
                min_slider_widget.setValue(min_slider)
                max_slider_widget.setValue(max_slider)
        finally:
            self.bc_min_spin.blockSignals(False)
            self.bc_max_spin.blockSignals(False)
            if min_slider_widget is not None:
                min_slider_widget.blockSignals(False)
            if max_slider_widget is not None:
                max_slider_widget.blockSignals(False)
            if range_slider is not None:
                range_slider.blockSignals(False)
            self._bc_updating_controls = False

    def _bc_apply_minmax(self, min_val: float, max_val: float) -> None:
        prim = self.primary_image
        if prim.array is None:
            return
        data_min = getattr(self, "_bc_data_min", None)
        data_max = getattr(self, "_bc_data_max", None)
        step = float(getattr(self, "_bc_step", 1.0))
        if data_min is None or data_max is None:
            data_min = float(np.min(prim.array))
            data_max = float(np.max(prim.array))
        data_range = float(data_max - data_min)
        if data_range <= 0:
            return
        width = max(float(max_val - min_val), step)
        width = min(width, data_range)
        center = 0.5 * (min_val + max_val)
        min_val = center - width / 2.0
        max_val = center + width / 2.0
        if min_val < data_min:
            shift = data_min - min_val
            min_val += shift
            max_val += shift
        if max_val > data_max:
            shift = data_max - max_val
            min_val += shift
            max_val += shift
        if max_val - min_val < step:
            max_val = min_val + step
        mapping = self._get_display_mapping(prim.id, "frame", prim.array)
        mapping.set_window(min_val, max_val)
        self._sync_modality_display_settings("frame", mapping)
        
        # Propagate to synced modalities
        self._propagate_sync_to_modalities(prim.id, "frame", min_val, max_val)
        
        if self.vmin_label is not None:
            self.vmin_label.setText(f"vmin: {min_val:.3f}")
        if self.vmax_label is not None:
            self.vmax_label.setText(f"vmax: {max_val:.3f}")
        self._bc_set_controls(min_val, max_val)
        self._sync_contrast_from_frame()
        if hasattr(self, "_schedule_refresh"):
            self._schedule_refresh()
        else:
            self._refresh_image()


    def _update_bc_controls(self, vals: np.ndarray, vmin: float, vmax: float) -> None:
        if getattr(self, "bc_min_spin", None) is None or vals is None or vals.size == 0:
            return
        data_min = float(np.min(vals))
        data_max = float(np.max(vals))
        if data_min == data_max:
            data_max = data_min + 1.0
        is_int = np.issubdtype(vals.dtype, np.integer)
        step = 1.0 if is_int else max((data_max - data_min) / 1000.0, 0.001)
        decimals = 0 if is_int else 3
        scale = max(1, int(round(1.0 / step)))
        span = data_max - data_min
        if span * scale > 2_000_000_000:
            scale = max(1, int(2_000_000_000 / max(span, 1e-9)))
        min_slider = int(round(data_min * scale))
        max_slider = int(round(data_max * scale))
        if min_slider == max_slider:
            max_slider = min_slider + 1
        self._bc_slider_scale = float(scale)
        self._bc_step = float(step)
        self._bc_data_min = data_min
        self._bc_data_max = data_max
        range_slider = getattr(self, "bc_range_slider", None)
        min_slider_widget = getattr(self, "bc_min_slider", None)
        max_slider_widget = getattr(self, "bc_max_slider", None)
        self._bc_updating_controls = True
        try:
            for spin in (self.bc_min_spin, self.bc_max_spin):
                spin.blockSignals(True)
                spin.setDecimals(decimals)
                spin.setSingleStep(step)
                spin.setRange(data_min, data_max)
            if min_slider_widget is not None and max_slider_widget is not None:
                for slider in (min_slider_widget, max_slider_widget):
                    slider.blockSignals(True)
                    slider.setRange(min_slider, max_slider)
                    slider.setSingleStep(1)
                    slider.setPageStep(max(1, int(10 * scale)))
            if range_slider is not None:
                range_slider.blockSignals(True)
                range_slider.setRange(data_min, data_max)
                range_slider.setStep(step)
            data_mid = 0.5 * (data_min + data_max)
            min_val = float(vmin)
            max_val = float(vmax)
            center = 0.5 * (min_val + max_val)
            width = max(max_val - min_val, step)
            b_range = max(1, int(round((data_max - data_min) / step)))
            self.bc_brightness_slider.setRange(-b_range, b_range)
            brightness_val = int(round((center - data_mid) / step))
            self.bc_brightness_slider.setValue(
                max(-b_range, min(b_range, brightness_val))
            )
            c_min = -90
            c_max = 300
            self.bc_contrast_slider.setRange(c_min, c_max)
            contrast_val = int(round((data_max - data_min) / width - 1.0) * 100)
            contrast_val = max(c_min, min(c_max, contrast_val))
            self.bc_contrast_slider.setValue(contrast_val)
            self.bc_min_spin.setValue(float(vmin))
            self.bc_max_spin.setValue(float(vmax))
            if min_slider_widget is not None and max_slider_widget is not None:
                min_slider_widget.setValue(self._bc_slider_from_value(vmin))
                max_slider_widget.setValue(self._bc_slider_from_value(vmax))
            if range_slider is not None:
                range_slider.setValues(vmin, vmax, emit_signal=False)
        finally:
            for spin in (self.bc_min_spin, self.bc_max_spin):
                spin.blockSignals(False)
            if min_slider_widget is not None and max_slider_widget is not None:
                for slider in (min_slider_widget, max_slider_widget):
                    slider.blockSignals(False)
            if range_slider is not None:
                range_slider.blockSignals(False)
            self._bc_updating_controls = False
        self._bc_update_preview(vmin, vmax)

    def _on_bc_min_slider(self, value: int) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        min_val = self._bc_value_from_slider(value)
        max_val = float(self.bc_max_spin.value())
        self._bc_apply_minmax(min_val, max_val)

    def _on_bc_max_slider(self, value: int) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        min_val = float(self.bc_min_spin.value())
        max_val = self._bc_value_from_slider(value)
        self._bc_apply_minmax(min_val, max_val)

    def _on_bc_min_spin(self, value: float) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        min_val = float(value)
        max_val = float(self.bc_max_spin.value())
        self._bc_apply_minmax(min_val, max_val)

    def _on_bc_max_spin(self, value: float) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        min_val = float(self.bc_min_spin.value())
        max_val = float(value)
        self._bc_apply_minmax(min_val, max_val)

    def _on_bc_brightness_change(self, value: int) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        data_min = getattr(self, "_bc_data_min", None)
        data_max = getattr(self, "_bc_data_max", None)
        if data_min is None or data_max is None:
            return
        step = float(getattr(self, "_bc_step", 1.0))
        data_mid = 0.5 * (data_min + data_max)
        L = data_mid + value * step
        min_val, max_val = self._current_vmin_vmax()
        W = max_val - min_val
        self._bc_apply_minmax(L - W / 2.0, L + W / 2.0)

    def _on_bc_contrast_change(self, value: int) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        data_min = getattr(self, "_bc_data_min", None)
        data_max = getattr(self, "_bc_data_max", None)
        if data_min is None or data_max is None:
            return
        data_range = max(float(data_max - data_min), float(getattr(self, "_bc_step", 1.0)))
        min_val, max_val = self._current_vmin_vmax()
        center = 0.5 * (min_val + max_val)
        denom = max(0.01, 1.0 + (value / 100.0))
        W = data_range / denom
        W = max(W, float(getattr(self, "_bc_step", 1.0)))
        self._bc_apply_minmax(center - W / 2.0, center + W / 2.0)

    def _bc_set_from_inputs(self) -> None:
        if getattr(self, "bc_min_spin", None) is None:
            return
        min_val = float(self.bc_min_spin.value())
        max_val = float(self.bc_max_spin.value())
        self._bc_apply_minmax(min_val, max_val)

    def _bc_update_preview(self, min_val: float, max_val: float) -> None:
        label = getattr(self, "bc_preview", None)
        if label is None:
            return
        data_min = getattr(self, "_bc_data_min", None)
        data_max = getattr(self, "_bc_data_max", None)
        if data_min is None or data_max is None:
            return
        width = max(1, label.width())
        height = max(1, label.height())
        pm = QtGui.QPixmap(width, height)
        pm.fill(QtGui.QColor("#ffffff"))
        painter = QtGui.QPainter(pm)
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            rect = QtCore.QRect(4, 4, width - 8, height - 8)
            painter.setPen(QtGui.QPen(QtGui.QColor("#111111"), 1))
            painter.drawRect(rect)
            if data_max == data_min:
                return
            def _x(val: float) -> int:
                return int(
                    rect.left()
                    + (val - data_min) / (data_max - data_min) * rect.width()
                )
            x1 = _x(min_val)
            x2 = _x(max_val)
            y0 = rect.bottom()
            y1 = rect.top()
            painter.setPen(QtGui.QPen(QtGui.QColor("#333333"), 2))
            painter.drawLine(rect.left(), y0, x1, y0)
            painter.drawLine(x1, y0, x2, y1)
            painter.drawLine(x2, y1, rect.right(), y1)
        finally:
            painter.end()
            label.setPixmap(pm)

    def _on_bc_range_changed(self, min_val: float, max_val: float) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        self._bc_apply_minmax(float(min_val), float(max_val))

    def _sync_modality_display_settings(self, panel: str, mapping) -> None:
        panel_map = getattr(self, "_panel_modality_map", {})
        modality = panel_map.get(panel)
        if modality is None:
            return
        settings = modality.display_settings
        settings.vmin = float(mapping.min_val)
        settings.vmax = float(mapping.max_val)
        settings.lut = int(mapping.lut)
        settings.gamma = float(mapping.gamma)

    def _sync_contrast_from_frame(self) -> None:
        if getattr(self, "sync_contrast_chk", None) is None:
            return
        if not self.sync_contrast_chk.isChecked():
            return
        panel_keys = self._selected_sync_panels(default_to_all=True)
        if not panel_keys:
            return
        source = self.controller.display_mapping.mapping_for(
            self.primary_image.id, "frame"
        )
        panel_map = getattr(self, "_panel_modality_map", {})
        for key in panel_keys:
            modality = panel_map.get(key)
            if modality is None:
                continue
            image_id = modality.image_id
            img = self.images[image_id]
            data = img.array if img.array is not None else img
            mapping = self._get_display_mapping(image_id, key, data)
            if key == "frame" and image_id == self.primary_image.id:
                continue
            mapping.min_val = source.min_val
            mapping.max_val = source.max_val
            mapping.lut = source.lut
            mapping.invert = source.invert
            mapping.gamma = source.gamma
            self._sync_modality_display_settings(key, mapping)

    def _propagate_sync_to_modalities(
        self, source_image_id: int, panel: str, min_val: float, max_val: float
    ) -> None:
        """Propagate brightness/contrast changes to synced modalities.

        When a modality's display window is adjusted, this method updates any
        modalities that have sync rules enabled to receive the same adjustment.

        Parameters
        ----------
        source_image_id : int
            The image ID that originated the change.
        panel : str
            The panel type (e.g., "frame", "mean", "std", "support").
        min_val : float
            The new minimum value for the display window.
        max_val : float
            The new maximum value for the display window.

        Notes
        -----
        This method is called after updating the source modality's display mapping
        and uses the global display_mapping object to determine which modalities
        should receive the update based on their sync rules.

        The update is performed by:
        1. Getting sync targets from display_mapping.propagate_sync_updates()
        2. For each target, updating its display mapping window
        3. Syncing the modality display settings
        4. Scheduling a refresh to update the UI

        This design prevents circular updates because:
        - Propagation is one-directional (from source to targets)
        - Target modalities are only updated programmatically, not via UI gestures
        - Each modality only propagates from its own user interaction
        """
        try:
            mapping = self.controller.display_mapping
            sync_targets = mapping.propagate_sync_updates(source_image_id, panel)
            
            # Update each synced modality
            for target_image_id, target_panel in sync_targets:
                # Find the target image
                target_image = None
                for img in self.images:
                    if img.id == target_image_id:
                        target_image = img
                        break
                
                if target_image is None or target_image.array is None:
                    continue
                
                # Get and update the target's display mapping
                target_mapping = self._get_display_mapping(
                    target_image_id, target_panel, target_image.array
                )
                target_mapping.set_window(min_val, max_val)
                
                # Sync modality display settings
                self._sync_modality_display_settings(target_panel, target_mapping)
        except Exception as e:
            # Log error but don't let sync propagation break display updates
            import sys
            print(f"Error propagating sync to modalities: {e}", file=sys.stderr)

    def _set_fov(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.images):
            return
        self.stop_playback_t()
        # Clear all analysis overlays when changing images to prevent stale results
        self._smlm_overlay = None
        self._smlm_overlay_extent = None
        self._smlm_results = []
        self._smlm_image_id = None  # Track that results are cleared
        self._deepstorm_overlay = None
        self._deepstorm_overlay_extent = None
        self._deepstorm_results = []
        self._deepstorm_image_id = None  # Track that results are cleared
        self._sr_overlay = None
        self._sr_overlay_extent = None
        self._particles_results = []
        self._particles_overlays = []
        self._particles_selected = None
        self._binary_view_mask = None
        self._binary_view_enabled = False
        self.current_image_idx = idx
        self.primary_combo.blockSignals(True)
        self.primary_combo.setCurrentIndex(idx)
        self.primary_combo.blockSignals(False)
        if self.threshold_panel is not None:
            cfg = self.controller.session_state.threshold_configs_by_image.get(idx)
            if cfg:
                self._apply_threshold_settings(cfg)
        self.axis_mode_combo.setCurrentText(self.primary_image.interpret_3d_as)
        self._refresh_roi_manager()
        self._refresh_metadata_dock(self.primary_image.id)
        self._maybe_autoload_annotations(self.primary_image.id)
        if hasattr(self, "_sync_channel_panel_for_active_image"):
            self._sync_channel_panel_for_active_image()
        self._refresh_image()

    def _set_primary_combo(self, idx: int) -> None:
        if 0 <= idx < len(self.images):
            self.stop_playback_t()
            self._smlm_overlay = None
            self._smlm_overlay_extent = None
            self._smlm_results = []
            self._deepstorm_overlay = None
            self._deepstorm_overlay_extent = None
            self._deepstorm_results = []
            self._sr_overlay = None
            self._sr_overlay_extent = None
            self._particles_results = []
            self._particles_overlays = []
            self._particles_selected = None
            self._binary_view_mask = None
            self._binary_view_enabled = False
            self.current_image_idx = idx
            self.fov_list.blockSignals(True)
            self.fov_list.setCurrentRow(idx)
            self.fov_list.blockSignals(False)
            if self.threshold_panel is not None:
                cfg = self.controller.session_state.threshold_configs_by_image.get(idx)
                if cfg:
                    self._apply_threshold_settings(cfg)
            self.axis_mode_combo.setCurrentText(self.primary_image.interpret_3d_as)
            self._refresh_roi_manager()
            self._refresh_metadata_dock(self.primary_image.id)
            self._maybe_autoload_annotations(self.primary_image.id)
            if hasattr(self, "_sync_channel_panel_for_active_image"):
                self._sync_channel_panel_for_active_image()
            self._refresh_image()
            # P7c: Schedule prefetch for adjacent FOVs (multi-FOV stacks)
            self._schedule_adjacent_fov_prefetch()

    def _schedule_adjacent_fov_prefetch(self) -> None:
        """Schedule low-priority prefetch of adjacent FOVs (P7c).
        
        When user navigates to a new FOV in a multi-FOV grid, detect and prefetch
        adjacent FOVs (up, down, left, right) to enable faster navigation.
        Uses lazy decompression (P7b) for bandwidth efficiency.
        """
        try:
            # Check if FOV grid is configured
            app_config = self.controller.app_config if hasattr(self.controller, 'app_config') else None
            if app_config is None or not app_config.enable_fov_prefetch:
                return
            
            cols = app_config.fov_grid_cols
            rows = app_config.fov_grid_rows
            if cols <= 0 or rows <= 0:
                return  # Grid not configured
            
            current_idx = self.current_image_idx
            
            # Get adjacent FOV indices
            adjacent_ids = self.proj_cache.get_adjacent_fov_ids(current_idx, cols, rows)
            if not adjacent_ids:
                return
            
            # Check if we should prefetch (cache not full, not thrashing)
            if not self.proj_cache.should_prefetch_adjacent(current_idx):
                return
            
            # Schedule low-priority prefetch for each adjacent FOV
            for adj_idx in adjacent_ids:
                if adj_idx < 0 or adj_idx >= len(self.images):
                    continue
                
                adj_image = self.images[adj_idx]
                
                # Use lazy decompression (P7b) for bandwidth efficiency
                # Check disk cache first via lazy load
                def _lazy_prefetch_fn(img, callback_mgr):
                    """Background job to prefetch adjacent FOV using lazy decomp"""
                    try:
                        crop_rect = self._cache_crop_rect(img) if hasattr(self, '_cache_crop_rect') else (0.0, 0.0, 0.0, 0.0)
                        
                        # Try lazy decompression from disk cache (P7b)
                        for kind in ['mean', 'std']:
                            key = (img.id, kind, crop_rect, -1, -1)
                            buffer = self.proj_cache.get_lazy(key)
                            if buffer is not None:
                                # Got compressed buffer; decompress to reload to memory
                                data = buffer.decompress_full()
                                self.proj_cache.put(key, data)
                            elif img.array is not None:
                                # Not in disk cache; compute and cache
                                from phage_annotator.analysis.core import compute_mean_std
                                mean_proj, std_proj = compute_mean_std(img.array)
                                self.proj_cache.put((img.id, 'mean', crop_rect, -1, -1), mean_proj)
                                self.proj_cache.put((img.id, 'std', crop_rect, -1, -1), std_proj)
                    except Exception as e:
                        logger = __import__('logging').getLogger(__name__)
                        logger.debug(f"Adjacent FOV prefetch failed for {adj_image.id}: {e}")
                
                # Queue low-priority background job
                self.jobs.submit(
                    lambda img=adj_image: _lazy_prefetch_fn(img, self.jobs),
                    name=f"Prefetch FOV {adj_idx}",
                    on_error=lambda e: None,  # Silently ignore prefetch errors
                )
        
        except Exception as e:
            logger = __import__('logging').getLogger(__name__)
            logger.debug(f"FOV prefetch scheduling failed: {e}")

    def _set_support_combo(self, idx: int) -> None:
        if 0 <= idx < len(self.images):
            self.stop_playback_t()
            self.support_image_idx = idx
            self.support_combo.setCurrentIndex(idx)
            self._maybe_autoload_annotations(self.support_image.id)
            self._refresh_image()

    def _toggle_play(self, axis: str) -> None:
        if axis == "t" and getattr(self, "modality_playback", None) is not None:
            facade = getattr(self, "modality_facade", None)
            if facade is not None and facade.count_modalities() > 1:
                active_idx = facade.get_active_modality_idx()
                if self.modality_playback.is_playing(active_idx):
                    self.modality_playback.stop_playback()
                else:
                    self.modality_playback.set_mode(PlaybackMode.SYNCHRONIZED)
                    self.modality_playback.start_playback(active_idx)
                return
        if self.play_mode == axis:
            self.stop_playback_t()
            return
        self.start_playback_t()

    def _init_modality_playback(self) -> None:
        if getattr(self, "modality_playback", None) is None:
            return
        facade = getattr(self, "modality_facade", None)
        if facade is None:
            return
        manager = facade.get_manager()
        for modality in manager.get_all_modalities():
            img = self.images[modality.image_id]
            frame_count = int(img.shape[0]) if hasattr(img, "shape") else 1
            self.modality_playback.register_modality(
                modality.idx, modality.display_name, frame_count=frame_count
            )
        self.modality_playback.frame_changed.connect(self._on_modality_frame_changed)
        self._apply_playback_sync_selection()

    def _on_modality_frame_changed(self, modality_idx: int, frame_idx: int) -> None:
        if self._playback_mode:
            return
        if getattr(self, "t_slider", None) is None:
            return
        self.t_slider.blockSignals(True)
        self.t_slider.setValue(int(frame_idx))
        self.t_slider.blockSignals(False)
        self._refresh_image()

    def _on_play_tick(self) -> None:
        if self._playback_mode:
            return
        if hasattr(self, "controller") and self.controller is not None:
            self.controller.set_t(int(self.t_slider.value()))
            self.controller.set_z(int(self.z_slider.value()))
        self._refresh_image()

    def _on_loop_change(self) -> None:
        self.loop_playback = self.loop_chk.isChecked()

    def _on_speed_change(self, value: int) -> None:
        if getattr(self, "fps_label", None) is not None:
            self.fps_label.setText(f"FPS: {value}")

    def _on_axis_mode_change(self, mode: str) -> None:
        self.stop_playback_t()
        self.controller.set_axis_interpretation(self.primary_image.id, mode)
        # Force reload for current primary to honor new interpretation.
        self._evict_image_cache(self.primary_image)
        self.proj_cache.invalidate_image(self.primary_image.id)
        self.recorder.record(
            "set_axis_interpretation", {"image": self.primary_image.name, "mode": mode}
        )

    def _on_projection_axis_change(self, text: str) -> None:
        """Handle projection axis change from combo box for backward compat."""
        axis = text.lower()
        manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is None:
            return
        updated = False
        for modality in manager.get_all_modalities():
            if modality.image_id == self.primary_image.id:
                if modality.display_settings.projection_axis != axis:
                    modality.display_settings.projection_axis = axis
                    updated = True
                break
        if updated:
            self.proj_cache.invalidate_image(self.primary_image.id)
            self._refresh_image()
        self._refresh_image()

    def _on_projection_changed(self, projection_type: str, projection_axis: str) -> None:
        """Handle projection type and axis change from ProjectionSelectorWidget."""
        manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is None:
            return
        
        # Import ProjectionType enum
        from phage_annotator.session.modality import ProjectionType
        
        updated = False
        for modality in manager.get_all_modalities():
            if modality.image_id == self.primary_image.id:
                # Update projection type if changed
                try:
                    proj_type = ProjectionType(projection_type.lower())
                    if modality.projection_type != proj_type:
                        modality.projection_type = proj_type
                        updated = True
                except ValueError:
                    pass
                
                # Update projection axis if changed
                if modality.display_settings.projection_axis != projection_axis:
                    modality.display_settings.projection_axis = projection_axis
                    updated = True
                break
        
        if updated:
            self.proj_cache.invalidate_image(self.primary_image.id)
            self._refresh_image()

    def _on_vminmax_change(self) -> None:
        if self.vmin_slider.value() > self.vmax_slider.value():
            self.vmax_slider.setValue(self.vmin_slider.value())
            prim = self.primary_image
            if prim.array is not None:
                data = prim.array
                if self._interactive:
                    stride = max(1, self.downsample_factor)
                    data = data[::stride, ::stride, ::stride, ::stride]
                    vmin = float(np.percentile(data, self.vmin_slider.value()))
                    vmax = float(np.percentile(data, self.vmax_slider.value()))
                    mapping = self._get_display_mapping(prim.id, "frame", prim.array)
                    mapping.set_window(vmin, vmax)
                    self._sync_modality_display_settings("frame", mapping)
                    if self._interactive:
                        self._contrast_drag_active = True
                        self.recorder.record(
                            "set_minmax",
                            {
                                "vmin": f"{self._last_vmin:.4f}",
                                "vmax": f"{self._last_vmax:.4f}",
                            },
                        )
                        self._schedule_refresh()

    def _apply_display_mapping(self) -> None:
        """Destructively apply the current display mapping to pixel data."""
        prim = self.primary_image
        if prim.array is None:
            return
        mapping = self._get_display_mapping(prim.id, "frame", prim.array)
        # P1.4: Confirmation with "Don't show again" toggle stored in settings
        if self._settings.value("confirmApplyDisplayMapping", True, type=bool):
            mbox = QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Icon.Warning,
                "Apply display mapping",
                (
                    "This will permanently rescale pixel values for the current image.\n"
                    "This cannot be undone. Proceed?"
                ),
                parent=self,
            )
            mbox.setStandardButtons(
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No
            )
            dont = QtWidgets.QCheckBox("Don't show again")
            mbox.setCheckBox(dont)
            resp = mbox.exec()
            if resp != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            if dont.isChecked():
                self._settings.setValue("confirmApplyDisplayMapping", False)
        data = prim.array.astype(np.float32, copy=True)
        if mapping.max_val == mapping.min_val:
            return
        data = (data - mapping.min_val) / (mapping.max_val - mapping.min_val)
        data = np.clip(data, 0.0, 1.0)
        prim.array = data
        mapping.reset_to_full_range(float(data.min()), float(data.max()))
        self._sync_modality_display_settings("frame", mapping)
        self._refresh_image()

    def _current_vmin_vmax(self) -> Tuple[float, float]:
        prim = self.primary_image
        if prim.array is None:
            return 0.0, 1.0
        mapping = self._get_display_mapping(prim.id, "frame", prim.array)
        vmin, vmax = mapping.min_val, mapping.max_val
        if vmin > vmax:
            vmin, vmax = vmax, vmin
            mapping.set_window(vmin, vmax)
            self._sync_modality_display_settings("frame", mapping)
            self.vmin_label.setText(f"vmin: {vmin:.3f}")
            self.vmax_label.setText(f"vmax: {vmax:.3f}")
        # PHASE 2D FIX: Always return vmin, vmax (was missing return statement)
        return vmin, vmax

    def _on_lut_change(self, idx: int) -> None:
        if idx < 0:
            return
        self.current_cmap_idx = idx
        self.recorder.record(
            "set_lut",
            {"index": idx, "name": lut_names()[idx] if idx < len(lut_names()) else idx},
        )
        mapping = self.controller.display_mapping.mapping_for(self.primary_image.id, "frame")
        self._sync_modality_display_settings("frame", mapping)
        self._sync_contrast_from_frame()
        if self.lut_invert_chk is not None:
            invert_supported = True
            if 0 <= idx < len(LUTS):
                invert_supported = LUTS[idx].invert_supported
                self.lut_invert_chk.setEnabled(invert_supported)
                if not invert_supported:
                    self.lut_invert_chk.setChecked(False)
                    self._refresh_image()

    def _on_lut_invert(self) -> None:
        self.controller.set_invert(self.lut_invert_chk.isChecked())
        self.recorder.record(
            "set_lut_invert", {"invert": self.lut_invert_chk.isChecked()}
        )
        self._sync_contrast_from_frame()
        self._refresh_image()

    def _on_gamma_change(self, value: int) -> None:
        gamma = max(0.2, min(5.0, value / 10.0))
        mapping = self.controller.display_mapping.mapping_for(
            self.primary_image.id, "frame"
        )
        mapping.gamma = gamma
        self._sync_modality_display_settings("frame", mapping)
        if self.gamma_label is not None:
            self.gamma_label.setText(f"{gamma:.2f}")
            self.recorder.record("set_gamma", {"gamma": f"{gamma:.2f}"})
            self.controller.display_changed.emit()
            self._sync_contrast_from_frame()
            self._refresh_image()

    def _on_log_toggle(self) -> None:
        mapping = self.controller.display_mapping.mapping_for(
            self.primary_image.id, "frame"
        )
        mapping.mode = "log" if self.log_chk.isChecked() else "linear"
        self.recorder.record("set_log", {"enabled": self.log_chk.isChecked()})
        self.controller.display_changed.emit()
        self._refresh_image()

    def _copy_display_settings(self) -> None:
        """Copy LUT/min/max/gamma from primary to another target."""
        mapping = self.controller.display_mapping.mapping_for(
            self.primary_image.id, "frame"
        )
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Copy Display Settings")
        layout = QtWidgets.QFormLayout(dlg)
        target_combo = QtWidgets.QComboBox()
        target_combo.addItems(["Support image", "All images"])
        layout.addRow("Target", target_combo)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)

        def _apply() -> None:
            choice = target_combo.currentText()
            if choice == "Support image":
                self._apply_display_to_image(self.support_image.id, "support", mapping)
            else:
                for img in self.images:
                    self._apply_display_to_image(img.id, "frame", mapping)
            self._refresh_image()
            dlg.accept()

        buttons.accepted.connect(_apply)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()

    def _apply_display_to_image(self, image_id: int, panel: str, mapping) -> None:
        copy = mapping.clone()
        copy.lut = mapping.lut
        copy.gamma = mapping.gamma
        copy.min_val = mapping.min_val
        copy.max_val = mapping.max_val
        copy.mode = mapping.mode
        copy.invert = mapping.invert
        self.controller.set_display_for_image(image_id, panel, copy)
        self._sync_modality_display_settings(panel, copy)

    def _on_label_change(self, button, checked: bool) -> None:
        if checked:
            self.current_label = button.text()
            self._update_status()

    def _on_scope_change(self) -> None:
        self.annotation_scope = (
            "current" if self.scope_group.buttons()[0].isChecked() else "all"
        )

    def _on_target_change(self) -> None:
        buttons = self.target_group.buttons()
        if buttons[0].isChecked():
            self.annotate_target = "frame"
        elif buttons[1].isChecked():
            self.annotate_target = "mean"
        else:
            self.annotate_target = "support"

    def _on_marker_size_change(self, val: int) -> None:
        self.marker_size = float(val)
        self._settings.setValue("markerSize", int(val))
        self._refresh_image()

    def _on_click_radius_change(self, val: float) -> None:
        self.click_radius_px = float(val)
        self._settings.setValue("clickRadiusPx", float(val))

    def _on_profile_mode(self) -> None:
        self.profile_enabled = self.profile_mode_chk.isChecked()

    def _on_profile_chk_changed(self) -> None:
        self.profile_enabled = self.profile_chk.isChecked()
        self._refresh_image()

    def _on_hist_chk_changed(self) -> None:
        self.hist_enabled = self.hist_chk.isChecked()
        self._refresh_image()

    def _clear_profile(self) -> None:
        self.profile_line = None
        self._refresh_image()

    def _on_hist_region(self) -> None:
        text = self.hist_region_combo.currentText()
        if text == "ROI":
            self.hist_region = "roi"
        elif text == "Crop area":
            self.hist_region = "crop"
        else:
            self.hist_region = "full"
        self._refresh_image()

    def _on_hist_scope_change(self) -> None:
        self._hist_scope_mode = self.hist_scope_combo.currentText()
        self._hist_cache = None
        self._hist_cache_key = None
        if self._hist_job_id is not None:
            self.jobs.cancel(self._hist_job_id)
            self._hist_job_id = None
            self._refresh_image()

    def _on_contrast_slider_pressed(self) -> None:
        self._contrast_drag_active = True
        self._start_interaction()

    def _on_contrast_slider_released(self) -> None:
        self._end_interaction()
        if not self._contrast_drag_active:
            return
        self._contrast_drag_active = False
        prim = self.primary_image
        if prim.array is None:
            return
        vmin = float(np.percentile(prim.array, self.vmin_slider.value()))
        vmax = float(np.percentile(prim.array, self.vmax_slider.value()))
        mapping = self._get_display_mapping(prim.id, "frame", prim.array)
        mapping.set_window(vmin, vmax)
        self._sync_modality_display_settings("frame", mapping)
        self._sync_contrast_from_frame()
        if hasattr(self, "_schedule_refresh"):
            self._schedule_refresh()
        else:
            self._refresh_image()

    def _auto_set_dialog(self) -> None:
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Set Auto Contrast")
        layout = QtWidgets.QFormLayout(dlg)
        low_spin = QtWidgets.QDoubleSpinBox()
        high_spin = QtWidgets.QDoubleSpinBox()
        low_spin.setRange(0.0, 100.0)
        high_spin.setRange(0.0, 100.0)
        low_spin.setDecimals(2)
        high_spin.setDecimals(2)
        low_spin.setValue(float(self._settings.value("autoLowPct", 0.35)))
        high_spin.setValue(float(self._settings.value("autoHighPct", 99.65)))
        layout.addRow("Low percentile (%)", low_spin)
        layout.addRow("High percentile (%)", high_spin)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)

        def _apply() -> None:
            low = float(low_spin.value())
            high = float(high_spin.value())
            if high <= low:
                QtWidgets.QMessageBox.warning(
                    self, "Invalid range", "High percentile must be greater than low."
                )
                return
            self._settings.setValue("autoLowPct", low)
            self._settings.setValue("autoHighPct", high)
            if self.auto_pct_label is not None:
                self.auto_pct_label.setText(f"{low:.2f}% / {high:.2f}%")
            dlg.accept()

        buttons.accepted.connect(_apply)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()

    def _open_contrast_dialog(self) -> None:
        prim = self.primary_image
        if prim.array is None:
            return
        from phage_annotator.ui_qt.widgets.contrast_dialog import ContrastDialog

        data = self._slice_data(prim)
        mapping = self._get_display_mapping(prim.id, "frame", prim.array)

        def _apply(vmin: float, vmax: float) -> None:
            mapping.set_window(vmin, vmax)
            self._sync_modality_display_settings("frame", mapping)
            if self.vmin_label is not None:
                self.vmin_label.setText(f"vmin: {vmin:.3f}")
            if self.vmax_label is not None:
                self.vmax_label.setText(f"vmax: {vmax:.3f}")
            self._bc_set_controls(vmin, vmax)
            if hasattr(self, "_schedule_refresh"):
                self._schedule_refresh()
            else:
                self._refresh_image()

        dlg = ContrastDialog(self, data, mapping.min_val, mapping.max_val, _apply)
        dlg.exec()

    def _auto_contrast(self) -> None:
        """Run auto contrast with a quick preview and background job."""
        prim = self.primary_image
        if prim.array is None:
            return
        low_pct = float(self._settings.value("autoLowPct", 0.35))
        high_pct = float(self._settings.value("autoHighPct", 99.65))
        use_roi = self.auto_roi_chk.isChecked()
        scope = self.auto_scope_combo.currentText()
        target = self.auto_target_combo.currentText()
        if getattr(self, "sync_contrast_chk", None) is not None and self.sync_contrast_chk.isChecked():
            panel_ids = self._selected_sync_panels(default_to_all=True)
        elif target == "Current panel":
            panel_ids = [self.annotate_target]
        else:
            panel_ids = [
                panel for panel, visible in self._panel_visibility.items() if visible
            ]

        if not panel_ids:
            return

        auto_img = self.support_image if panel_ids == ["support"] else prim
        if auto_img.array is None:
            self._ensure_loaded(auto_img.id)
            if auto_img.array is None:
                return

        # Quick preview on current slice (downsampled).
        slice_data = self._slice_data(auto_img)
        roi_mask = self._roi_mask(slice_data.shape) if use_roi else None
        stride = max(1, self.downsample_factor)
        quick = slice_data[::stride, ::stride]
        quick_mask = roi_mask[::stride, ::stride] if roi_mask is not None else None
        vmin, vmax = compute_auto_window(quick, low_pct, high_pct, roi_mask=quick_mask)
        self._apply_auto_to_panels(panel_ids, vmin, vmax)
        if hasattr(self, "_schedule_refresh"):
            self._schedule_refresh()
        else:
            self._refresh_image()

        if self._auto_job_id is not None:
            self.jobs.cancel(self._auto_job_id)
            self._auto_job_id = None

        self._bump_job_generation()
        job_gen = self._job_generation

        def _sample_stack() -> np.ndarray:
            arr = auto_img.array
            if arr is None:
                return np.array([], dtype=np.float32)
            t_count, z_count = arr.shape[0], arr.shape[1]
            samples = []
            roi_mask_local = None
            if scope == "All frames":
                t_step = max(1, t_count // 16)
                z_idx = self.z_slider.value()
                for t in range(0, t_count, t_step):
                    frame = arr[t, z_idx, :, :]
                    if use_roi:
                        if roi_mask_local is None:
                            roi_mask_local = self._roi_mask(frame.shape)
                        samples.append(frame[roi_mask_local])
                    else:
                        samples.append(frame.ravel())
            elif scope == "Whole image":
                t_step = max(1, t_count // 8)
                z_step = max(1, z_count // 8)
                for t in range(0, t_count, t_step):
                    for z in range(0, z_count, z_step):
                        frame = arr[t, z, :, :]
                        if use_roi:
                            if roi_mask_local is None:
                                roi_mask_local = self._roi_mask(frame.shape)
                            samples.append(frame[roi_mask_local])
                        else:
                            samples.append(frame.ravel())
            else:
                t = self.t_slider.value()
                z = self.z_slider.value()
                frame = arr[t, z, :, :]
                if use_roi:
                    roi_mask_local = self._roi_mask(frame.shape)
                    samples.append(frame[roi_mask_local])
                else:
                    samples.append(frame.ravel())
            if not samples:
                return np.array([], dtype=np.float32)
            sample = np.concatenate(samples)
            if sample.size > 200000:
                # Deterministic sampling for reproducibility (P3.2)
                rng = np.random.default_rng(42)
                idx = rng.choice(sample.size, size=200000, replace=False)
                sample = sample[idx]
            return sample

        def _job(progress, cancel_token):
            if cancel_token.is_cancelled():
                return None
            vmin_full, vmax_full = compute_auto_window(_sample_stack, low_pct, high_pct)
            if cancel_token.is_cancelled():
                return None
            return vmin_full, vmax_full, job_gen

        def _on_result(result) -> None:
            if result is None:
                return
            vmin_full, vmax_full, gen = result
            if gen != self._job_generation:
                return
            self._apply_auto_to_panels(panel_ids, vmin_full, vmax_full)
            if hasattr(self, "_schedule_refresh"):
                self._schedule_refresh()
            else:
                self._refresh_image()

        def _on_error(err: str) -> None:
            self._append_log(f"[JOB] Auto contrast error\n{err}")

        handle = self.jobs.submit(
            _job,
            name="Auto contrast",
            on_result=_on_result,
            on_error=_on_error,
        )
        self._auto_job_id = handle.job_id

    def _apply_auto_to_panels(
        self, panel_ids: List[str], vmin: float, vmax: float
    ) -> None:
        panel_map = getattr(self, "_panel_modality_map", {})
        for panel in panel_ids:
            modality = panel_map.get(panel)
            if modality is not None:
                image_id = modality.image_id
                img = self.images[image_id]
                data = img.array if img.array is not None else img
            else:
                image_id = (
                    self.support_image.id if panel == "support" else self.primary_image.id
                )
                data = (
                    self.support_image.array
                    if panel == "support"
                    else self.primary_image.array
                )
            mapping = self._get_display_mapping(image_id, panel, data)
            mapping.set_window(vmin, vmax)
            self._sync_modality_display_settings(panel, mapping)

    def _mark_dirty(self, dirty: bool = True) -> None:
        self._annotations_dirty = dirty

    def _autosave_tick(self) -> None:
        path = self.controller.autosave_if_needed(self, self._current_keypoints)
        if path is None:
            return
        self._append_log(f"[RECOVERY] Autosaved annotations to {path}")
        self._set_status("Autosaved recovery file.")

    def _check_recovery(self) -> None:
        recovery = self.controller.find_recovery_file(self._current_keypoints)
        if recovery is None:
            return
        resp = QtWidgets.QMessageBox.question(
            self,
            "Recovery found",
            "A newer recovery file was found. Restore annotations?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
        )
        if resp == QtWidgets.QMessageBox.StandardButton.Yes:
            self.controller.restore_recovery(recovery)
            self._refresh_image()

    def _focus_axis_mode_control(self) -> None:
        if getattr(self, "advanced_group", None) is not None:
            self.advanced_group.setChecked(True)
            self.axis_mode_combo.setFocus()
            self.axis_mode_combo.showPopup()

    def _update_axes_info(self) -> None:
        """Refresh the Axes info panel and tooltip (OME vs heuristic)."""
        img = self.primary_image
        if img.array is not None:
            t, z, y, x = img.array.shape
        else:
            shape = img.shape
            if len(shape) == 2:
                t, z, y, x = 1, 1, shape[0], shape[1]
            elif len(shape) == 3:
                if img.has_time and not img.has_z:
                    t, z, y, x = shape[0], 1, shape[1], shape[2]
                elif img.has_z and not img.has_time:
                    t, z, y, x = 1, shape[0], shape[1], shape[2]
                else:
                    t, z, y, x = 1, 1, shape[1], shape[2]
            else:
                t, z, y, x = shape[0], shape[1], shape[2], shape[3]

        interp = img.interpret_3d_as
        self.axes_info_label.setText(
            f"T: {t}  Z: {z}  Y: {y}  X: {x}  | Interpretation: {interp}"
        )
        if img.ome_axes:
            tooltip = f"OME metadata axes: {img.ome_axes}"
        elif img.axis_auto_used and img.axis_auto_mode:
            tooltip = f"Auto heuristic used: {img.axis_auto_mode}"
        else:
            tooltip = "No OME metadata; manual interpretation"
        self.axes_info_label.setToolTip(tooltip)

    def _update_axis_warning(self) -> None:
        """Show a non-intrusive warning when auto heuristics are used."""
        img = self.primary_image
        if img.interpret_3d_as == "auto" and img.axis_auto_used and img.axis_auto_mode:
            mode = img.axis_auto_mode.upper()
            self.axis_warning.setText(
                f'<a href="axes">3D axis interpreted as {mode} (auto). Click to change.</a>'
            )
            self.axis_warning.setVisible(True)
        else:
            self.axis_warning.setVisible(False)

    def _on_limits_changed(self, ax) -> None:
        if getattr(self, "renderer", None) is not None:
            if ax not in set(self.renderer.axes.values()):
                return
        else:
            if ax not in {
                self.ax_frame,
                self.ax_mean,
                self.ax_comp,
                self.ax_support,
                self.ax_std,
            }:
                return
        if self._suppress_limits:
            return
        if self.link_zoom:
            self._last_zoom_linked = (ax.get_xlim(), ax.get_ylim())
            self._update_status()
        self._sync_view_from_axis(ax)

    def _sync_view_from_axis(self, ax) -> None:
        if getattr(self, "view_sync", None) is None:
            return
        if not self.link_zoom:
            return
        panel_key = self._panel_key_for_axis(ax)
        if panel_key is None:
            return
        shape = getattr(self, "_last_display_shape", None)
        if shape is None:
            return
        _, w = shape
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        span_x = max(1e-6, abs(xlim[1] - xlim[0]))
        zoom_level = max(0.1, min(20.0, w / span_x))
        pan_x = float(xlim[0])
        pan_y = float(ylim[1])  # top of view
        idx = getattr(self, "_panel_sync_index", {}).get(panel_key)
        if idx is not None:
            self.view_sync.set_view(idx, zoom_level, pan_x, pan_y)

    def _panel_key_for_axis(self, ax) -> Optional[str]:
        if getattr(self, "renderer", None) is not None:
            for key, panel_ax in self.renderer.axes.items():
                if panel_ax == ax:
                    return key
        if ax == self.ax_frame:
            return "frame"
        if ax == self.ax_mean:
            return "mean"
        if ax == self.ax_support:
            return "support"
        if ax == self.ax_std:
            return "std"
        return None

    def _update_sync_list(self, visible: List[str]) -> None:
        if getattr(self, "sync_list", None) is None:
            return
        selected = set(getattr(self, "_sync_selected_panels", set()))
        if not selected:
            selected = set(visible)
        self.sync_list.blockSignals(True)
        try:
            self.sync_list.clear()
            for key in visible:
                label = key
                modality = getattr(self, "_panel_modality_map", {}).get(key)
                if modality is not None:
                    label = modality.display_name
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
                item.setSelected(key in selected)
                self.sync_list.addItem(item)
        finally:
            self.sync_list.blockSignals(False)
        self._sync_selected_panels = set(self._selected_sync_panels(default_to_all=True))

    def _selected_sync_panels(self, default_to_all: bool = False) -> List[str]:
        if getattr(self, "sync_list", None) is None:
            return []
        selected = [
            item.data(QtCore.Qt.ItemDataRole.UserRole)
            for item in self.sync_list.selectedItems()
        ]
        if not selected and default_to_all:
            selected = list(getattr(self, "_panel_sync_index", {}).keys())
        return selected

    def _on_sync_selection_changed(self) -> None:
        self._sync_selected_panels = set(self._selected_sync_panels())
        self._apply_sync_selection()
        if getattr(self, "sync_contrast_chk", None) is not None:
            if self.sync_contrast_chk.isChecked():
                self._sync_contrast_from_frame()

    def _update_sync_indicators(self) -> None:
        """Update visual indicators showing which sync modes are enabled.

        Uses emoji icons to show sync state:
        - 🔲 (empty box): sync disabled
        - ✅ (checkmark): sync enabled
        """
        if getattr(self, "sync_playback_label", None) is not None:
            if self.sync_playback_chk.isChecked():
                self.sync_playback_label.setText("✅")
                self.sync_playback_label.setToolTip("Playback sync is ON")
            else:
                self.sync_playback_label.setText("🔲")
                self.sync_playback_label.setToolTip("Playback sync is OFF")

        if getattr(self, "sync_zoom_label", None) is not None:
            if self.sync_zoom_chk.isChecked():
                self.sync_zoom_label.setText("✅")
                self.sync_zoom_label.setToolTip("Zoom/Pan sync is ON")
            else:
                self.sync_zoom_label.setText("🔲")
                self.sync_zoom_label.setToolTip("Zoom/Pan sync is OFF")

        if getattr(self, "sync_contrast_label", None) is not None:
            if self.sync_contrast_chk.isChecked():
                self.sync_contrast_label.setText("✅")
                self.sync_contrast_label.setToolTip("Contrast sync is ON")
            else:
                self.sync_contrast_label.setText("🔲")
                self.sync_contrast_label.setToolTip("Contrast sync is OFF")

    def _on_sync_mode_changed(self) -> None:
        if getattr(self, "sync_zoom_chk", None) is not None:
            self.link_zoom = self.sync_zoom_chk.isChecked()
            if getattr(self, "link_zoom_act", None) is not None:
                self.link_zoom_act.setChecked(self.link_zoom)
        self._apply_sync_selection()
        self._update_sync_indicators()
        if getattr(self, "sync_contrast_chk", None) is not None:
            if self.sync_contrast_chk.isChecked():
                self._sync_contrast_from_frame()

    def _apply_sync_selection(self) -> None:
        self._apply_view_sync_selection()
        self._apply_playback_sync_selection()

    def _apply_view_sync_selection(self) -> None:
        if getattr(self, "view_sync", None) is None:
            return
        if not self.link_zoom:
            self.view_sync.enable_zoom_sync(False)
            self.view_sync.enable_pan_sync(False)
            return
        selected = set(self._selected_sync_panels(default_to_all=True))
        if not selected:
            return
        group = {
            idx
            for key, idx in getattr(self, "_panel_sync_index", {}).items()
            if key in selected
        }
        if group:
            self.view_sync.clear()
            for idx in getattr(self, "_panel_sync_reverse", {}).keys():
                self.view_sync.register_modality(idx)
            self.view_sync.create_link_group(group)
            self.view_sync.enable_zoom_sync(True)
            self.view_sync.enable_pan_sync(True)

    def _apply_playback_sync_selection(self) -> None:
        if getattr(self, "modality_playback", None) is None:
            return
        if getattr(self, "sync_playback_chk", None) is None:
            return
        if not self.sync_playback_chk.isChecked():
            self.modality_playback.set_sync_group(None)
            return
        targets = self._selected_playback_modalities()
        self.modality_playback.set_sync_group(targets if targets else None)

    def _selected_playback_modalities(self) -> set[int]:
        selected = set(self._selected_sync_panels(default_to_all=True))
        targets: set[int] = set()
        panel_map = getattr(self, "_panel_modality_map", {})
        for key in selected:
            modality = panel_map.get(key)
            if modality is None:
                continue
            if modality.idx < 0:
                continue
            if modality.projection_type != ProjectionType.RAW:
                continue
            targets.add(modality.idx)
        return targets

    def _sync_view_manager_panels(self, visible: List[str]) -> None:
        if getattr(self, "view_sync", None) is None:
            return
        self.view_sync.clear()
        self._panel_sync_index = {}
        self._panel_sync_reverse = {}
        for idx, key in enumerate(visible):
            self._panel_sync_index[key] = idx
            self._panel_sync_reverse[idx] = key
            self.view_sync.register_modality(idx)
        self._update_sync_list(visible)
        if getattr(self, "sync_zoom_chk", None) is not None:
            self.sync_zoom_chk.blockSignals(True)
            self.sync_zoom_chk.setChecked(self.link_zoom)
            self.sync_zoom_chk.blockSignals(False)
        self._update_sync_indicators()
        self._apply_view_sync_selection()
        self._apply_playback_sync_selection()

    def _on_view_sync_changed(self, modality_idx: int, zoom: float, pan_x: float, pan_y: float) -> None:
        panel_key = getattr(self, "_panel_sync_reverse", {}).get(modality_idx)
        if panel_key is None:
            return
        ax = None
        if getattr(self, "renderer", None) is not None:
            ax = self.renderer.axes.get(panel_key)
        if ax is None:
            ax = getattr(self, f"ax_{panel_key}", None)
        if ax is None:
            return
        shape = getattr(self, "_last_display_shape", None)
        if shape is None:
            return
        h, w = shape
        span_x = max(1.0, w / max(0.1, zoom))
        span_y = max(1.0, h / max(0.1, zoom))
        x0 = max(0.0, min(pan_x, max(0.0, w - span_x)))
        y0 = max(0.0, min(pan_y, max(0.0, h - span_y)))
        self._suppress_limits = True
        try:
            ax.set_xlim(x0, x0 + span_x)
            ax.set_ylim(y0 + span_y, y0)
        finally:
            self._suppress_limits = False
    def _on_modality_context_menu(self, pos: QtCore.QPoint) -> None:
        """Show context menu for modality renaming."""
        combo = self.sender()
        if combo is None:
            return
        
        menu = QtWidgets.QMenu(combo)
        rename_action = menu.addAction("Rename modality...")
        
        action = menu.exec_(combo.mapToGlobal(pos))
        
        if action == rename_action:
            self._show_rename_dialog(combo)
    
    def _show_rename_dialog(self, combo: QtWidgets.QComboBox) -> None:
        """Show rename dialog for the selected modality in combo."""
        from phage_annotator.ui_qt.dialogs.rename_modality_dialog import RenameModalityDialog
        
        current_idx = combo.currentIndex()
        current_name = combo.currentText()
        
        # Get all other modality names (for duplicate validation)
        existing_names = {combo.itemText(i) for i in range(combo.count())}
        existing_names.discard(current_name)
        
        dialog = RenameModalityDialog(current_name, existing_names, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_name = dialog.get_new_name()
            
            # Update the combo display
            combo.setItemText(current_idx, new_name)
            
            # Update the modality's display_name in the modality manager
            manager = getattr(self.controller.session_state, "modality_manager", None)
            if manager is not None:
                image_id = self.images[current_idx].id if current_idx < len(self.images) else None
                if image_id is not None:
                    for modality in manager.get_all_modalities():
                        if modality.image_id == image_id:
                            modality.display_name = new_name
                            break
            
            # Refresh UI to show updated names everywhere
            self._refresh_modality_display()
    
    def _refresh_modality_display(self) -> None:
        """Refresh all UI elements that display modality names."""
        # Update sync list
        if getattr(self, "sync_list", None) is not None:
            visible = list(getattr(self, "_panel_sync_index", {}).keys())
            self._update_sync_list(visible)

        if hasattr(self, "_update_analysis_panel_modalities"):
            self._update_analysis_panel_modalities()
        
        # Refresh image to update any modality-related displays
        self._refresh_image()
