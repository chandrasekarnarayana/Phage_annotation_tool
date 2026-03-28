"""Display, playback, and general control handlers."""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_auto_window
from phage_annotator.session.signal_hub import emit_display_changed, emit_view_changed
from phage_annotator.session.modality import ProjectionType
from phage_annotator.session.multi_playback import PlaybackMode
from phage_annotator.ui_qt.controls.display_contrast import DisplayContrastMixin
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, lut_names
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


class DisplayControlsMixin(DisplayContrastMixin):
    """Mixin for display, playback, and general control handlers."""

    def _hist_region_widget(self):
        return getattr(self, "contrast_hist_region_combo", None) or getattr(self, "hist_region_combo", None)

    def _hist_scope_widget(self):
        return getattr(self, "contrast_hist_scope_combo", None) or getattr(self, "hist_scope_combo", None)

    def _sync_role_for_panel(self, panel_key: str):
        """Return the lazy-table role key associated with a canvas panel."""
        key = str(panel_key or "").strip().lower()
        if not key:
            return None
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        modality = panel_map.get(key)
        if modality is not None:
            idx = int(getattr(modality, "idx", -1))
            if idx >= 0:
                return idx
        if key == "frame":
            return 0
        if key == "support":
            return 1
        if key in {"mean", "std"}:
            return f"builtin:{key}"
        if key.startswith("modality_"):
            try:
                return int(key.split("_", 1)[1])
            except Exception:
                return None
        return None

    def _sync_mode_enabled_for_panel(self, panel_key: str, mode_key: str) -> bool:
        """Return whether a panel participates in a given sync mode."""
        key = str(panel_key or "").strip()
        mode = str(mode_key or "").strip().lower()
        if not key or mode not in {"contrast", "zoom", "playback"}:
            return False
        role = self._sync_role_for_panel(key)
        if role is None:
            return True
        modes = self._lazy_sync_modes_state() if hasattr(self, "_lazy_sync_modes_state") else {}
        flags = dict(modes.get(role, {}) or {})
        return bool(flags.get(mode, True))

    def _sync_follow_active_enabled(self) -> bool:
        """Return whether sync target should follow active canvas view group."""
        combo = getattr(self, "sync_target_mode_combo", None)
        if combo is not None:
            return str(combo.currentData() or "manual").strip().lower() == "active"
        follow = getattr(self, "sync_follow_active_chk", None)
        return bool(follow is not None and follow.isChecked())

    def _sync_key_active_group(self) -> str:
        """Return the sync group key derived from current active view/target."""
        default_target = (
            self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
        )
        active_key = str(getattr(self, "annotate_target", default_target)).strip().lower() or default_target
        return str(self._sync_key_for_panel(active_key) or "").strip()

    def _set_sync_key_combo_data(self, group_key: str) -> None:
        """Set sync-key combo selection without emitting change signals."""
        combo = getattr(self, "sync_key_combo", None)
        if combo is None:
            return
        group = str(group_key or "").strip()
        if not group:
            return
        idx = combo.findData(group)
        if idx < 0:
            return
        combo.blockSignals(True)
        try:
            combo.setCurrentIndex(idx)
        finally:
            combo.blockSignals(False)

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
            allowed_panels = set(self._contrast_target_panels())
            
            # Update each synced modality
            for target_image_id, target_panel in sync_targets:
                if allowed_panels and str(target_panel) not in allowed_panels:
                    continue
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

    def _sync_base_modality_sources(self) -> None:
        """Keep modality-manager base sources aligned with UI primary/support selection."""
        manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is None or not self.images:
            return
        try:
            primary_mod = manager.get_modality(0)
            if primary_mod is not None:
                primary_mod.image_id = int(self.primary_image.id)
            support_mod = manager.get_modality(1)
            if support_mod is not None:
                support_mod.image_id = int(self.support_image.id)
        except Exception:
            return

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
        status_combo = getattr(self, "status_modality_combo", None)
        if status_combo is not None:
            status_combo.blockSignals(True)
            status_combo.setCurrentIndex(idx)
            status_combo.blockSignals(False)
        if self.threshold_panel is not None:
            cfg = self.controller.session_state.threshold_configs_by_image.get(idx)
            if cfg:
                self._apply_threshold_settings(cfg)
        self._sync_base_modality_sources()
        self.axis_mode_combo.setCurrentText(self.primary_image.interpret_3d_as)
        self._refresh_roi_manager()
        self._refresh_metadata_dock(self.primary_image.id)
        self._maybe_autoload_annotations(self.primary_image.id)
        if hasattr(self, "_sync_channel_panel_for_active_image"):
            self._sync_channel_panel_for_active_image()
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        if hasattr(self, "_refresh_lazy_modality_table"):
            self._refresh_lazy_modality_table()
        if hasattr(self, "_refresh_advanced_settings_panel"):
            self._refresh_advanced_settings_panel()
        self._request_ui_refresh("display-controls", metadata=True)
        
        # Trigger QC monitor for new image
        if hasattr(self, "_on_qc_image_changed"):
            self._on_qc_image_changed()

    def _set_primary_combo(
        self,
        idx: int,
        *,
        refresh_lazy_table: bool = True,
        schedule_prefetch: bool = True,
    ) -> None:
        if 0 <= idx < len(self.images):
            self._set_fov(idx)
            if not refresh_lazy_table:
                self._lazy_apply_table_refresh = False
            self._refresh_prepare_setup_summary()
            if schedule_prefetch:
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
                    priority="background",
                    replace_key=f"prefetch-fov-{adj_idx}",
                )
        
        except Exception as e:
            logger = __import__('logging').getLogger(__name__)
            logger.debug(f"FOV prefetch scheduling failed: {e}")

    def _set_support_combo(self, idx: int, *, refresh_lazy_table: bool = True) -> None:
        if 0 <= idx < len(self.images):
            self.stop_playback_t()
            self.support_image_idx = idx
            self._sync_base_modality_sources()
            self._maybe_autoload_annotations(self.support_image.id)
            if hasattr(self, "_refresh_annotation_view_controls"):
                self._refresh_annotation_view_controls()
            if refresh_lazy_table and hasattr(self, "_refresh_lazy_modality_table"):
                self._refresh_lazy_modality_table()
            self._refresh_prepare_setup_summary()
            self._request_ui_refresh("display-controls")

    def _toggle_play(self, axis: str) -> None:
        axis = str(axis or "").strip().lower()
        if axis not in {"t", "z"}:
            return
        source_panel = str(self._playback_source_panel_key()) if hasattr(self, "_playback_source_panel_key") else "frame"
        source_img = self._playback_source_image() if hasattr(self, "_playback_source_image") else None
        source_id = int(getattr(source_img, "id", -1)) if source_img is not None else -1
        if hasattr(self, "_append_log"):
            self._append_log(
                f"[GUI] Playback toggle requested axis={axis} panel={source_panel} image_id={source_id}",
                category="GUI",
            )
        if hasattr(getattr(self, "recorder", None), "record"):
            try:
                self.recorder.record(
                    "gui_play_toggle",
                    {"axis": axis, "panel": source_panel, "image_id": source_id},
                )
            except Exception:
                pass
        timer = getattr(self, "play_timer", None)

        # Toggle off threaded T playback when clicking Play/Stop T again.
        if axis == "t" and bool(getattr(self, "_playback_mode", False)):
            self.stop_playback_t()
            if hasattr(self, "_append_log"):
                self._append_log("[GUI] Playback stopped axis=t", category="GUI")
            return

        # Toggle off when clicking the active play mode.
        if timer is not None and timer.isActive() and str(getattr(self, "play_mode", "")) == axis:
            timer.stop()
            self.play_mode = None
            self._sync_playback_button_labels(None)
            if hasattr(self, "_append_log"):
                self._append_log(f"[GUI] Playback stopped axis={axis}", category="GUI")
            self._update_status()
            return

        # Stop any currently running playback mode.
        if getattr(self, "_playback_mode", False):
            self.stop_playback_t()
        if timer is not None and timer.isActive():
            timer.stop()

        # Threaded T playback is opt-in; timer playback is the reliable default.
        use_threaded_t = False
        settings = getattr(self, "_settings", None)
        if axis == "t" and settings is not None:
            try:
                use_threaded_t = bool(settings.value("threadedPlaybackT", False, type=bool))
            except Exception:
                use_threaded_t = False
        if axis == "t" and use_threaded_t:
            self.start_playback_t()
            if getattr(self, "_playback_mode", False):
                self._sync_playback_button_labels("t")
                return

        # Fallback: timer-driven slider playback (works for Z and non-RAW T views).
        if timer is None:
            return
        self.play_mode = axis
        fps = max(1, int(getattr(self, "speed_slider", None).value() if getattr(self, "speed_slider", None) is not None else 10))
        timer.setInterval(max(16, int(1000 / fps)))
        timer.start()
        self._sync_playback_button_labels(axis)
        if hasattr(self, "_append_log"):
            self._append_log(
                f"[GUI] Playback started axis={axis} fps={int(fps)} loop={bool(getattr(self, 'loop_playback', False))}",
                category="GUI",
            )
        self._update_status()

    def _sync_playback_button_labels(self, active_axis: str | None) -> None:
        """Reflect active playback mode in play button text."""
        axis = str(active_axis or "").strip().lower()
        if getattr(self, "play_t_btn", None) is not None:
            self.play_t_btn.setText("Stop T" if axis == "t" else "Play T")
        if getattr(self, "play_z_btn", None) is not None:
            self.play_z_btn.setText("Stop Z" if axis == "z" else "Play Z")

    def _on_play_timer_tick(self) -> None:
        """Advance T/Z slider for timer-based playback mode."""
        axis = str(getattr(self, "play_mode", "") or "").strip().lower()
        if axis not in {"t", "z"}:
            timer = getattr(self, "play_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
            self._sync_playback_button_labels(None)
            return

        slider = self.t_slider if axis == "t" else self.z_slider
        if slider is None:
            return
        next_value = int(slider.value()) + 1
        if next_value > int(slider.maximum()):
            if bool(getattr(self, "loop_playback", False)):
                next_value = int(slider.minimum())
            else:
                timer = getattr(self, "play_timer", None)
                if timer is not None and timer.isActive():
                    timer.stop()
                self.play_mode = None
                self._sync_playback_button_labels(None)
                if hasattr(self, "_append_log"):
                    self._append_log(f"[GUI] Playback reached end axis={axis} (loop off)", category="GUI")
                self._update_status()
                return
        slider.setValue(int(next_value))

    def _init_modality_playback(self) -> None:
        if getattr(self, "modality_playback", None) is None:
            return
        facade = getattr(self, "modality_facade", None)
        if facade is None:
            return
        manager = facade.get_manager()
        for modality in manager.get_all_modalities():
            img = self.images[modality.image_id]
            # For projections (mean/std/etc), frame_count should be 1 regardless of image shape
            # Only RAW modalities with 3D+ stacks (T, H, W) have multiple frames
            if hasattr(img, "shape") and hasattr(img, "ndim"):
                # 3D or higher: shape[0] is time/frame dimension
                # 2D: single frame projection
                frame_count = int(img.shape[0]) if img.ndim >= 3 else 1
            else:
                frame_count = 1
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
        self._request_ui_refresh("display-controls")

    def _on_play_tick(self) -> None:
        if self._playback_mode:
            return
        if hasattr(self, "controller") and self.controller is not None:
            self.controller.set_t(int(self.t_slider.value()))
            self.controller.set_z(int(self.z_slider.value()))
        if bool(getattr(self, "auto_follow_table_chk", None) and self.auto_follow_table_chk.isChecked()):
            self._refresh_table()
        if hasattr(self, "_refresh_review_queue_panel"):
            self._refresh_review_queue_panel()
        self._request_ui_refresh("display-controls")

    def _on_loop_change(self) -> None:
        self.loop_playback = self.loop_chk.isChecked()
        if hasattr(self, "_append_log"):
            self._append_log(
                f"[GUI] Loop playback {'enabled' if self.loop_playback else 'disabled'}",
                category="GUI",
            )
        if getattr(self, "_playback_mode", False):
            try:
                self._playback_ring.reset()
                self._playback_cursor = int(self.t_slider.value())
                if hasattr(self, "_restart_playback_prefetch"):
                    self._restart_playback_prefetch(self._playback_cursor)
                if hasattr(self, "_append_log"):
                    self._append_log(
                        f"[GUI] Playback prefetch reconfigured loop={bool(self.loop_playback)} t={int(self._playback_cursor)}",
                        category="GUI",
                    )
            except Exception:
                pass
        if hasattr(getattr(self, "recorder", None), "record"):
            try:
                self.recorder.record("gui_loop_toggle", {"enabled": bool(self.loop_playback)})
            except Exception:
                pass

    def _on_speed_change(self, value: int) -> None:
        if getattr(self, "fps_label", None) is not None:
            self.fps_label.setText(f"FPS: {value}")
        # Keep legacy timer path bounded if it gets toggled by old shortcuts.
        timer = getattr(self, "play_timer", None)
        if timer is not None:
            fps = max(1, int(value))
            timer.setInterval(max(16, int(1000 / fps)))
        if hasattr(self, "_append_log"):
            self._append_log(f"[GUI] Playback speed set fps={int(value)}", category="GUI")
        if hasattr(getattr(self, "recorder", None), "record"):
            try:
                self.recorder.record("gui_playback_speed", {"fps": int(value)})
            except Exception:
                pass

    def _on_axis_mode_change(self, mode: str) -> None:
        old_mode = getattr(self.controller.view_state, "axis_interpretation", None)
        logger = get_panel_logger("prepare")
        self.stop_playback_t()
        self.controller.set_axis_interpretation(self.primary_image.id, mode)
        logger.log_action(
            "axis_mode_change",
            image_id=int(self.primary_image.id),
            image_name=str(self.primary_image.name),
            old_mode=old_mode,
            new_mode=mode,
        )
        # Force reload for current primary to honor new interpretation.
        self._evict_image_cache(self.primary_image)
        self.proj_cache.invalidate_image(self.primary_image.id)
        if hasattr(self, "_refresh_advanced_settings_panel"):
            self._refresh_advanced_settings_panel()
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
            self._request_ui_refresh("display-controls")
            if hasattr(self, "_append_assist_change_log"):
                self._append_assist_change_log(
                    "projection_changed",
                    projection_type="current_panel_axis_only",
                    projection_axis=str(axis),
                )
            if hasattr(self, "_maybe_emit_assist_context_delta"):
                self._maybe_emit_assist_context_delta("projection")
        self._request_ui_refresh("display-controls", table=True)

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
            self._request_ui_refresh("display-controls")

    def _on_vminmax_change(self) -> None:
        if self.vmin_slider.value() > self.vmax_slider.value():
            self.vmax_slider.setValue(self.vmin_slider.value())
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return
        data = prim.array
        if self._interactive:
            stride = max(1, self.downsample_factor)
            data = data[::stride, ::stride, ::stride, ::stride]
        vmin = float(np.percentile(data, self.vmin_slider.value()))
        vmax = float(np.percentile(data, self.vmax_slider.value()))
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)
        mapping.set_window(vmin, vmax)
        self._sync_modality_display_settings(panel_key, mapping)
        self._sync_contrast_from_frame()
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
        else:
            self._request_ui_refresh("display-controls")

    def _apply_display_mapping(self) -> None:
        """Destructively apply the current display mapping to pixel data."""
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)
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
        self._sync_modality_display_settings(panel_key, mapping)
        self._request_ui_refresh("display-controls")

    def _current_vmin_vmax(self) -> Tuple[float, float]:
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return 0.0, 1.0
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)
        vmin, vmax = mapping.min_val, mapping.max_val
        if vmin > vmax:
            vmin, vmax = vmax, vmin
            mapping.set_window(vmin, vmax)
            self._sync_modality_display_settings(panel_key, mapping)
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
        panel_key = self._display_source_panel_key()
        source_img = self._display_source_image()
        mapping = self.controller.display_mapping.mapping_for(source_img.id, panel_key)
        self._sync_modality_display_settings(panel_key, mapping)
        self._sync_contrast_from_frame()
        if self.lut_invert_chk is not None:
            invert_supported = True
            if 0 <= idx < len(LUTS):
                invert_supported = LUTS[idx].invert_supported
                self.lut_invert_chk.setEnabled(invert_supported)
                if not invert_supported:
                    self.lut_invert_chk.setChecked(False)
                    self._request_ui_refresh("display-controls")

    def _on_lut_invert(self) -> None:
        self.controller.set_invert(self.lut_invert_chk.isChecked())
        self.recorder.record(
            "set_lut_invert", {"invert": self.lut_invert_chk.isChecked()}
        )
        self._sync_contrast_from_frame()
        self._request_ui_refresh("display-controls")

    def _on_gamma_change(self, value: int) -> None:
        gamma = max(0.2, min(5.0, value / 10.0))
        panel_key = self._display_source_panel_key()
        source_img = self._display_source_image()
        mapping = self.controller.display_mapping.mapping_for(source_img.id, panel_key)
        mapping.gamma = gamma
        self._sync_modality_display_settings(panel_key, mapping)
        if self.gamma_label is not None:
            self.gamma_label.setText(f"{gamma:.2f}")
            self.recorder.record("set_gamma", {"gamma": f"{gamma:.2f}"})
            emit_display_changed(self.controller)
            self._sync_contrast_from_frame()
            self._request_ui_refresh("display-controls")

    def _on_log_toggle(self) -> None:
        panel_key = self._display_source_panel_key()
        source_img = self._display_source_image()
        mapping = self.controller.display_mapping.mapping_for(source_img.id, panel_key)
        mapping.mode = "log" if self.log_chk.isChecked() else "linear"
        self.recorder.record("set_log", {"enabled": self.log_chk.isChecked()})
        emit_display_changed(self.controller)
        self._request_ui_refresh("display-controls")

    def _copy_display_settings(self) -> None:
        """Copy LUT/min/max/gamma from primary to another target."""
        panel_key = self._display_source_panel_key()
        source_img = self._display_source_image()
        mapping = self.controller.display_mapping.mapping_for(source_img.id, panel_key)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Copy Display Settings")
        layout = QtWidgets.QFormLayout(dlg)
        target_combo = QtWidgets.QComboBox()
        target_combo.addItems(["Modality 2 image", "All images"])
        layout.addRow("Target", target_combo)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)

        def _apply() -> None:
            choice = target_combo.currentText()
            panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
            if choice == "Modality 2 image":
                modality1 = panel_map.get("modality_1")
                if modality1 is not None:
                    self._apply_display_to_image(int(modality1.image_id), "modality_1", mapping)
            else:
                for img in self.images:
                    for key, modality in panel_map.items():
                        if int(getattr(modality, "image_id", -1)) == int(getattr(img, "id", -2)):
                            self._apply_display_to_image(img.id, str(key), mapping)
            self._request_ui_refresh("display-controls")
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
        old_scope = str(getattr(self, "annotation_scope", "current"))
        new_scope = "current" if self.scope_group.buttons()[0].isChecked() else "all"
        if old_scope == "current" and new_scope == "all":
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Stack Annotation Mode",
                "Switch to Stack Annotation Mode (All Z)?\n"
                "New annotations will apply globally across Z.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Cancel,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                self.scope_group.buttons()[0].setChecked(True)
                return
        self.annotation_scope = new_scope
        if hasattr(self, "controller") and hasattr(self.controller, "append_audit_event"):
            self.controller.append_audit_event(
                "annotation_scope_changed",
                image_id=self.primary_image.id if getattr(self, "primary_image", None) is not None else -1,
                old_scope=old_scope,
                new_scope=new_scope,
            )
        if hasattr(self, "_append_assist_change_log"):
            self._append_assist_change_log(
                "scope_changed",
                old_scope=str(old_scope),
                new_scope=str(new_scope),
            )
        if new_scope == "all":
            msg = "Switched to Stack Annotation Mode (All Z)"
            QtWidgets.QToolTip.showText(
                self.mapToGlobal(QtCore.QPoint(20, 20)),
                msg,
                self,
            )
        else:
            msg = "Switched to Slice Annotation Mode (Current Z)"
            QtWidgets.QToolTip.showText(
                self.mapToGlobal(QtCore.QPoint(20, 20)),
                msg,
                self,
            )
        # Auto-hide tooltip after 2 seconds to prevent it from lingering
        QtCore.QTimer.singleShot(2000, lambda: QtWidgets.QToolTip.hideText())
        self._update_status()
        self._request_ui_refresh("display-controls")
        if hasattr(self, "_maybe_emit_assist_context_delta"):
            self._maybe_emit_assist_context_delta("scope")

    def _on_target_change(self) -> None:
        default_target = (
            self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
        )
        old_target = str(getattr(self, "annotate_target", default_target))
        combo = getattr(self, "annotate_target_combo", None)
        if combo is not None and combo.count() > 0:
            selected = str(combo.currentData() or combo.currentText() or "").strip().lower()
            if selected:
                self.annotate_target = selected
        elif getattr(self, "target_group", None) is not None:
            target_buttons = dict(getattr(self, "_target_buttons", {}) or {})
            if target_buttons:
                selected = None
                for key, btn in target_buttons.items():
                    if btn is not None and btn.isChecked():
                        selected = key
                        break
                self.annotate_target = str(selected or default_target)
            else:
                buttons = self.target_group.buttons()
                if buttons and buttons[0].isChecked():
                    self.annotate_target = default_target
                else:
                    self.annotate_target = default_target
        point_vis = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        point_vis[str(getattr(self, "annotate_target", default_target))] = True
        self._annotation_panel_visibility = point_vis
        chk = dict(getattr(self, "_annotation_view_checkboxes", {}) or {}).get(
            str(getattr(self, "annotate_target", default_target))
        )
        if chk is not None and not chk.isChecked():
            chk.blockSignals(True)
            chk.setChecked(True)
            chk.blockSignals(False)
        if hasattr(self, "_set_lazy_row_points_state"):
            self._set_lazy_row_points_state(str(getattr(self, "annotate_target", default_target)), True)
        badge = getattr(self, "target_state_badge_lbl", None)
        combo = getattr(self, "annotate_target_combo", None)
        if badge is not None:
            if combo is not None and combo.count() > 0:
                badge.setText(f"Write target: {combo.currentText()}")
            else:
                badge.setText(f"Write target: {str(getattr(self, 'annotate_target', default_target))}")
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        if old_target != str(self.annotate_target) and hasattr(
            self, "_mark_annotation_context_changed"
        ):
            self._mark_annotation_context_changed(
                f"target panel changed ({old_target} -> {self.annotate_target})"
            )
        if old_target != str(self.annotate_target) and hasattr(self, "_append_assist_change_log"):
            self._append_assist_change_log(
                "target_changed",
                old_target=str(old_target),
                new_target=str(self.annotate_target),
            )
        if hasattr(self, "_on_sync_mode_changed"):
            self._on_sync_mode_changed()
        self._update_status()
        self._request_ui_refresh("display-controls")
        if old_target != str(self.annotate_target) and hasattr(self, "_maybe_emit_assist_context_delta"):
            self._maybe_emit_assist_context_delta("target")

    def _on_marker_size_change(self, val: int) -> None:
        self.marker_size = float(val)
        self._settings.setValue("markerSize", int(val))
        for attr in ("marker_size_spin", "annotate_marker_size_spin"):
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            if int(widget.value()) == int(val):
                continue
            widget.blockSignals(True)
            widget.setValue(int(val))
            widget.blockSignals(False)
        self._request_ui_refresh("display-controls")

    def _on_marker_shape_change(self, _index: int = -1) -> None:
        combo = getattr(self, "annotate_marker_shape_combo", None)
        if combo is None or combo.count() <= 0:
            return
        marker = str(combo.currentData() or "o").strip() or "o"
        self.marker_shape = marker
        self._settings.setValue("markerShape", marker)
        self._request_ui_refresh("display-controls")

    def _on_click_radius_change(self, val: float) -> None:
        self.click_radius_px = float(val)
        self._settings.setValue("clickRadiusPx", float(val))

    def _on_profile_mode(self) -> None:
        self.profile_enabled = self.profile_mode_chk.isChecked()

    def _on_profile_chk_changed(self) -> None:
        self._set_panel_visibility("profile", self.profile_chk.isChecked())
        self.profile_enabled = bool(self.profile_chk.isChecked())
        self._request_ui_refresh("display-controls")

    def _on_hist_chk_changed(self) -> None:
        self._set_panel_visibility("hist", self.hist_chk.isChecked())
        self.hist_enabled = bool(self.hist_chk.isChecked())
        self._request_ui_refresh("display-controls")

    def _clear_profile(self) -> None:
        self.profile_line = None
        self._request_ui_refresh("display-controls")

    def _on_hist_region(self) -> None:
        widget = self._hist_region_widget()
        if widget is None:
            return
        text = widget.currentText()
        if text == "ROI":
            self.hist_region = "roi"
        elif text == "Crop area":
            self.hist_region = "crop"
        else:
            self.hist_region = "full"
        self._request_ui_refresh("display-controls")

    def _on_hist_scope_change(self) -> None:
        widget = self._hist_scope_widget()
        if widget is None:
            return
        self._hist_scope_mode = widget.currentText()
        self._hist_cache = None
        self._hist_cache_key = None
        if self._hist_job_id is not None:
            self.jobs.cancel(self._hist_job_id)
            self._hist_job_id = None
            self._request_ui_refresh("display-controls")

    def _on_contrast_slider_pressed(self) -> None:
        self._contrast_drag_active = True
        self._start_interaction()

    def _on_contrast_slider_released(self) -> None:
        self._end_interaction()
        if not self._contrast_drag_active:
            return
        self._contrast_drag_active = False
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return
        vmin = float(np.percentile(prim.array, self.vmin_slider.value()))
        vmax = float(np.percentile(prim.array, self.vmax_slider.value()))
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)
        mapping.set_window(vmin, vmax)
        self._sync_modality_display_settings(panel_key, mapping)
        self._sync_contrast_from_frame()
        if hasattr(self, "_schedule_refresh"):
            self._schedule_refresh()
        else:
            self._request_ui_refresh("display-controls")

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
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return
        from phage_annotator.ui_qt.widgets.contrast_dialog import ContrastDialog

        data = self._slice_data(prim)
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)

        def _apply(vmin: float, vmax: float) -> None:
            mapping.set_window(vmin, vmax)
            self._sync_modality_display_settings(panel_key, mapping)
            if self.vmin_label is not None:
                self.vmin_label.setText(f"vmin: {vmin:.3f}")
            if self.vmax_label is not None:
                self.vmax_label.setText(f"vmax: {vmax:.3f}")
            self._bc_set_controls(vmin, vmax)
            if hasattr(self, "_schedule_refresh"):
                self._schedule_refresh()
            else:
                self._request_ui_refresh("display-controls")

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
        panel_ids = self._contrast_target_panels()

        if not panel_ids:
            return

        source_panel = str(getattr(self, "annotate_target", "")).strip().lower()
        if not source_panel:
            source_panel = panel_ids[0] if panel_ids else "modality_0"
        if source_panel not in panel_ids:
            source_panel = panel_ids[0]
        panel_map = getattr(self, "_panel_modality_map", {})
        modality = panel_map.get(source_panel)
        if modality is not None:
            auto_img = self._image_obj_from_id(int(modality.image_id))
        else:
            auto_img = self.primary_image
        if auto_img is None:
            return
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
            self._request_ui_refresh("display-controls")

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
                self._request_ui_refresh("display-controls")

        def _on_error(err: str) -> None:
            self._append_log(f"[JOB] Auto contrast error\n{err}")

        handle = self.jobs.submit(
            _job,
            name="Auto contrast",
            on_result=_on_result,
            on_error=_on_error,
            priority="interactive",
            replace_key="auto-contrast",
        )
        self._auto_job_id = handle.job_id

    def _auto_contrast_panel(self, panel_key: str) -> None:
        """Apply a quick auto-contrast window to one panel immediately."""
        key = str(panel_key or "").strip().lower()
        if not key:
            return
        panel_map = getattr(self, "_panel_modality_map", {})
        modality = panel_map.get(key)
        if modality is not None:
            auto_img = self._image_obj_from_id(int(modality.image_id))
        elif key == "support":
            auto_img = getattr(self, "support_image", None)
        else:
            auto_img = getattr(self, "primary_image", None)
        if auto_img is None:
            return
        if auto_img.array is None:
            self._ensure_loaded(auto_img.id)
            if auto_img.array is None:
                return
        low_pct = float(self._settings.value("autoLowPct", 0.35))
        high_pct = float(self._settings.value("autoHighPct", 99.65))
        slice_data = self._slice_data(auto_img)
        stride = max(1, int(getattr(self, "downsample_factor", 1)))
        quick = slice_data[::stride, ::stride]
        vmin, vmax = compute_auto_window(quick, low_pct, high_pct)
        self._apply_auto_to_panels([key], vmin, vmax)
        if hasattr(self, "_schedule_refresh"):
            self._schedule_refresh()
        else:
            self._request_ui_refresh("display-controls")

    def _apply_auto_to_panels(
        self, panel_ids: List[str], vmin: float, vmax: float
    ) -> None:
        panel_map = getattr(self, "_panel_modality_map", {})
        for panel in panel_ids:
            modality = panel_map.get(panel)
            if modality is not None:
                image_id = modality.image_id
                img = self._image_obj_from_id(image_id)
                if img is None:
                    continue
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
        if dirty and hasattr(self, "_note_annotation_edit"):
            try:
                self._note_annotation_edit(self.primary_image.id)
            except Exception:
                pass

    def _autosave_tick(self) -> None:
        path = self.controller.autosave_if_needed(self, self._current_keypoints)
        if path is None:
            return
        self._last_autosave_path = str(path)
        self._last_autosave_timestamp = time.time()
        self._append_log(f"[RECOVERY] Autosaved annotations to {path}")
        self._status_success(
            "Autosaved recovery file.",
            timeout_ms=2500,
            source="display.autosave",
        )

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
            self._request_ui_refresh("display-controls")

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
                    # RGB/multi-channel 2D image.
                    t, z, y, x = 1, 1, shape[0], shape[1]
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
            return
        if self._suppress_limits:
            return
        if self.link_zoom:
            self._last_zoom_linked = (ax.get_xlim(), ax.get_ylim())
            self._update_status()
        self._sync_view_from_axis(ax)
        self._update_sync_keys_hint()

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
        if len(shape) < 2:
            return
        w = int(shape[1])
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
        return None

    def _update_sync_list(self, visible: List[str]) -> None:
        if hasattr(self, "_ensure_lazy_sync_group_keys"):
            try:
                self._ensure_lazy_sync_group_keys()
            except Exception:
                pass
        self._sync_selected_panels = set(visible)
        self._update_sync_key_selector()
        self._update_sync_keys_hint()

    def _update_sync_key_selector(self) -> None:
        """Refresh sync-key selector from current lazy-loading group keys."""
        combo = getattr(self, "sync_key_combo", None)
        if combo is None:
            return
        current = combo.currentData()
        keys = []
        for panel_key in getattr(self, "_panel_sync_index", {}).keys():
            sync_key = self._sync_key_for_panel(str(panel_key))
            if str(sync_key).strip().isdigit():
                keys.append(str(sync_key).strip())
        ordered = sorted(set(keys), key=lambda v: int(v))
        combo.blockSignals(True)
        try:
            combo.clear()
            for key in ordered:
                combo.addItem(f"Group {key}", key)
            idx = combo.findData(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            combo.blockSignals(False)

    def _on_sync_key_changed(self, _index: int) -> None:
        """Apply sync updates when manual sync-key selection changes."""
        combo = getattr(self, "sync_key_combo", None)
        if combo is None:
            return
        key = str(combo.currentData() or "").strip()
        if key.isdigit() and hasattr(self, "_apply_lazy_group_sync_selection"):
            self._on_sync_mode_changed()
            self._status_info(
                f"Sync target group: {key}",
                timeout_ms=2500,
                source="display.sync_group",
            )

    def _sync_key_for_panel(self, panel_key: str) -> str:
        """Return sync key for a panel from lazy modality/view group mapping."""
        groups = self._lazy_sync_groups_state() if hasattr(self, "_lazy_sync_groups_state") else {}
        role = self._sync_role_for_panel(panel_key)
        return str(groups.get(role, "")).strip() if role is not None else ""

    def _update_sync_keys_hint(self) -> None:
        """Show available sync keys and effective target source."""
        hint = getattr(self, "sync_keys_hint_lbl", None)
        live = getattr(self, "sync_target_live_lbl", None)
        contract = getattr(self, "sync_contract_live_lbl", None)
        panels = getattr(self, "sync_panels_live_lbl", None)
        view = getattr(self, "sync_view_live_lbl", None)
        if hint is None:
            return
        keys = []
        for panel_key in getattr(self, "_panel_sync_index", {}).keys():
            sync_key = self._sync_key_for_panel(str(panel_key))
            if str(sync_key).strip().isdigit():
                keys.append(str(sync_key).strip())
        if keys:
            ordered = sorted(set(keys), key=lambda v: int(v))
            selected_key = str(
                getattr(getattr(self, "sync_key_combo", None), "currentData", lambda: "")() or ""
            ).strip()
            mode = "active view group" if self._sync_follow_active_enabled() else f"group {selected_key or '-'}"
            hint.setText(f"Groups available: {', '.join(ordered)} | Target: {mode}")
            if live is not None:
                if "active view group" in mode:
                    default_target = (
                        self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
                    )
                    active_key = str(getattr(self, "annotate_target", default_target)).strip().lower() or default_target
                    active_group = self._sync_key_for_panel(active_key) or "-"
                    live.setText(f"Sync target: Active group ({active_group})")
                else:
                    live.setText(f"Sync target: Manual group ({selected_key or '-'})")
            if contract is not None:
                contract.setText(self._sync_contract_summary())
            if panels is not None:
                panels.setText(self._sync_panel_summary())
            if view is not None:
                view.setText(self._sync_view_summary())
        else:
            hint.setText("Groups available: none")
            if live is not None:
                live.setText("Sync target: -")
            if contract is not None:
                contract.setText("Sync contract: -")
            if panels is not None:
                panels.setText("Sync panels: -")
            if view is not None:
                view.setText("Sync view: -")
        prepare_target = getattr(self, "prepare_sync_target_lbl", None)
        if prepare_target is not None and live is not None:
            prepare_target.setText(live.text())
        prepare_contract = getattr(self, "prepare_sync_contract_lbl", None)
        if prepare_contract is not None and contract is not None:
            prepare_contract.setText(contract.text())
        prepare_panels = getattr(self, "prepare_sync_panels_lbl", None)
        if prepare_panels is not None and panels is not None:
            prepare_panels.setText(panels.text())
        self._refresh_prepare_setup_summary()

    def _sync_contract_summary(self) -> str:
        """Return a concise summary of the current effective sync contract."""
        selected = list(self._selected_sync_panels(default_to_all=True))
        if not selected:
            return "Sync contract: -"
        mode_labels: list[str] = []
        if any(self._sync_mode_enabled_for_panel(str(key), "contrast") for key in selected):
            mode_labels.append("Contrast")
        if any(self._sync_mode_enabled_for_panel(str(key), "zoom") for key in selected):
            mode_labels.append("Zoom/Pan")
        if any(self._sync_mode_enabled_for_panel(str(key), "playback") for key in selected):
            mode_labels.append("Playback")
        group = (
            self._sync_key_active_group()
            if self._sync_follow_active_enabled()
            else str(getattr(getattr(self, "sync_key_combo", None), "currentData", lambda: "")() or "").strip()
        ) or "-"
        return (
            f"Sync contract: Group {group} | {', '.join(mode_labels)}"
            if mode_labels
            else f"Sync contract: Group {group} | None"
        )

    def _sync_panel_summary(self) -> str:
        """Return the currently targeted panel set for the active/manual sync group."""
        selected = list(self._selected_sync_panels(default_to_all=True))
        if not selected:
            return "Sync panels: -"
        labels = []
        for key in selected:
            modality = dict(getattr(self, "_panel_modality_map", {}) or {}).get(str(key))
            if modality is not None:
                labels.append(str(getattr(modality, "display_name", key)))
            else:
                labels.append(str(key))
        preview = ", ".join(labels[:3])
        if len(labels) > 3:
            preview += f" +{len(labels) - 3}"
        return f"Sync panels: {preview}"

    def _sync_view_summary(self) -> str:
        """Return a compact viewport readout for the current sync target."""
        selected = list(self._selected_sync_panels(default_to_all=True))
        if not selected:
            return "Sync view: -"
        default_target = (
            self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
        )
        active_key = str(getattr(self, "annotate_target", default_target)).strip().lower() or default_target
        panel_key = active_key if active_key in selected else str(selected[0])
        ax = None
        if getattr(self, "renderer", None) is not None:
            ax = self.renderer.axes.get(panel_key)
        if ax is None:
            return f"Sync view: {panel_key}"
        try:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            shape = getattr(self, "_last_display_shape", None)
            if shape is None or len(shape) < 2:
                return f"Sync view: {panel_key}"
            width = max(1e-6, abs(float(xlim[1]) - float(xlim[0])))
            zoom = max(0.1, min(20.0, float(shape[1]) / width))
            pan_x = float(min(xlim))
            pan_y = float(min(ylim))
            return f"Sync view: {panel_key} | Zoom {zoom:.2f}x | Pan {pan_x:.0f}, {pan_y:.0f}"
        except Exception:
            return f"Sync view: {panel_key}"

    def _refresh_prepare_setup_summary(self) -> None:
        """Refresh the Prepare-page mirrors for reference, sync, and ROI setup."""
        reference_lbl = getattr(self, "prepare_reference_summary_lbl", None)
        if reference_lbl is not None:
            primary_name = "-"
            support_name = "-"
            images = list(getattr(self, "images", []) or [])
            primary_idx = int(getattr(self, "current_image_idx", 0))
            support_idx = int(getattr(self, "support_image_idx", 0))
            if 0 <= primary_idx < len(images):
                primary_name = str(getattr(images[primary_idx], "name", "-")).strip() or "-"
            if 0 <= support_idx < len(images):
                support_name = str(getattr(images[support_idx], "name", "-")).strip() or "-"
            relation = "same view" if primary_name == support_name else "compare pair"
            reference_lbl.setText(
                f"Reference views: Primary {primary_name} | Reference {support_name} ({relation})"
            )
        roi_lbl = getattr(self, "prepare_roi_summary_lbl", None)
        if roi_lbl is not None:
            rect = tuple(getattr(self, "roi_rect", (0.0, 0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0, 0.0))
            if len(rect) >= 4 and float(rect[2]) > 0 and float(rect[3]) > 0:
                roi_lbl.setText(
                    f"ROI: x={float(rect[0]):.0f}, y={float(rect[1]):.0f}, w={float(rect[2]):.0f}, h={float(rect[3]):.0f}"
                )
            else:
                roi_lbl.setText("ROI: Full field")

    def _selected_sync_panels(self, default_to_all: bool = False) -> List[str]:
        panel_keys = list(getattr(self, "_panel_sync_index", {}).keys())
        if not panel_keys:
            return []
        follow_active = self._sync_follow_active_enabled()
        if follow_active:
            group = self._sync_key_active_group()
            self._set_sync_key_combo_data(group)
        else:
            group = str(getattr(getattr(self, "sync_key_combo", None), "currentData", lambda: "")() or "")
        group = str(group).strip()
        if not group:
            return panel_keys if default_to_all else []
        selected = [k for k in panel_keys if self._sync_key_for_panel(str(k)) == group]
        if not selected and default_to_all:
            return panel_keys
        return selected

    def _on_sync_selection_changed(self) -> None:
        self._on_sync_mode_changed()

    def _update_sync_indicators(self) -> None:
        """Refresh sync target tooltips for current mode."""
        combo = getattr(self, "sync_key_combo", None)
        mode_combo = getattr(self, "sync_target_mode_combo", None)
        follow = getattr(self, "sync_follow_active_chk", None)
        if combo is not None:
            combo.setToolTip("Manual sync target group.")
        if mode_combo is not None:
            mode_combo.setToolTip("Choose manual group or active canvas group target.")
        if follow is not None:
            follow.setToolTip(
                "Use active canvas view group."
                if follow.isChecked()
                else "Use manually selected group."
            )

    def _on_sync_mode_changed(self) -> None:
        combo = getattr(self, "sync_key_combo", None)
        follow_active = self._sync_follow_active_enabled()
        follow = getattr(self, "sync_follow_active_chk", None)
        if follow is not None:
            follow.blockSignals(True)
            follow.setChecked(follow_active)
            follow.blockSignals(False)
        if follow_active:
            self._set_sync_key_combo_data(self._sync_key_active_group())
        if hasattr(self, "_apply_roi_for_sync_group"):
            try:
                target_group = (
                    self._sync_key_active_group()
                    if follow_active
                    else str(getattr(getattr(self, "sync_key_combo", None), "currentData", lambda: "")() or "")
                )
                self._apply_roi_for_sync_group(str(target_group).strip())
            except Exception:
                pass
        if combo is not None:
            combo.setEnabled(True)
        self._apply_sync_selection()
        self._update_sync_indicators()
        self._on_sync_scope_changed("")
        self._sync_contrast_from_frame()

    def _apply_sync_selection(self) -> None:
        self._apply_view_sync_selection()
        self._apply_playback_sync_selection()

    def _apply_view_sync_selection(self) -> None:
        if getattr(self, "view_sync", None) is None:
            return
        if not self.link_zoom:
            self.view_sync.clear()
            self.view_sync.enable_zoom_sync(False)
            self.view_sync.enable_pan_sync(False)
            return
        selected = {
            key
            for key in self._selected_sync_panels(default_to_all=True)
            if self._sync_mode_enabled_for_panel(str(key), "zoom")
        }
        if not selected:
            self.view_sync.clear()
            self.view_sync.enable_zoom_sync(False)
            self.view_sync.enable_pan_sync(False)
            return
        group = {
            idx
            for key, idx in getattr(self, "_panel_sync_index", {}).items()
            if key in selected
        }
        if not group:
            self.view_sync.clear()
            self.view_sync.enable_zoom_sync(False)
            self.view_sync.enable_pan_sync(False)
            return
        self.view_sync.clear()
        for idx in getattr(self, "_panel_sync_reverse", {}).keys():
            self.view_sync.register_modality(idx)
        self.view_sync.create_link_group(group)
        self.view_sync.enable_zoom_sync(True)
        self.view_sync.enable_pan_sync(True)

    def _apply_playback_sync_selection(self) -> None:
        if getattr(self, "modality_playback", None) is None:
            return
        targets = self._selected_playback_modalities()
        selected_panels = self._selected_sync_panels(default_to_all=True)
        if selected_panels and not targets:
            self.modality_playback.set_sync_group(set())
            return
        self.modality_playback.set_sync_group(targets if targets else None)

    def _selected_playback_modalities(self) -> set[int]:
        selected = {
            key
            for key in self._selected_sync_panels(default_to_all=True)
            if self._sync_mode_enabled_for_panel(str(key), "playback")
        }
        targets: set[int] = set()
        panel_map = getattr(self, "_panel_modality_map", {})
        manager = getattr(getattr(self, "controller", None), "session_state", None)
        manager = getattr(manager, "modality_manager", None)
        for key in selected:
            key_text = str(key)
            if key_text.startswith("modality_") and manager is not None:
                try:
                    mod_idx = int(key_text.split("_", 1)[1])
                    base_mod = manager.get_modality(mod_idx)
                    if base_mod is not None and base_mod.projection_type == ProjectionType.RAW:
                        targets.add(int(base_mod.idx))
                    continue
                except Exception:
                    pass
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
        self._update_sync_indicators()
        self._apply_view_sync_selection()
        self._apply_playback_sync_selection()

    def _on_view_sync_changed(
        self,
        modality_idx: int,
        zoom: float,
        pan_x: float,
        pan_y: float,
        t_idx: int = 0,
        z_idx: int = 0,
    ) -> None:
        """Apply linked zoom/pan updates and publish them through the signal hub.

        The view-sync manager emits T/Z indices alongside zoom/pan updates. They are
        accepted here for signal compatibility even though this handler currently
        only applies viewport changes.
        """
        panel_key = getattr(self, "_panel_sync_reverse", {}).get(modality_idx)
        if panel_key is None:
            return
        ax = None
        if getattr(self, "renderer", None) is not None:
            ax = self.renderer.axes.get(panel_key)
        if ax is None:
            return
        shape = getattr(self, "_last_display_shape", None)
        if shape is None:
            return
        if len(shape) < 2:
            return
        h, w = int(shape[0]), int(shape[1])
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
        if getattr(self, "link_zoom", False):
            self._last_zoom_linked = ((x0, x0 + span_x), (y0 + span_y, y0))
        self._controller_view_refresh_hint = "view_sync"
        emit_view_changed(
            self.controller,
            change_type="view_sync",
            viewport={
                "panel_key": str(panel_key),
                "modality_idx": int(modality_idx),
                "zoom": float(zoom),
                "pan_x": float(x0),
                "pan_y": float(y0),
                "xlim": (float(x0), float(x0 + span_x)),
                "ylim": (float(y0 + span_y), float(y0)),
            },
        )

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
        visible = list(getattr(self, "_panel_sync_index", {}).keys())
        self._update_sync_list(visible)

        if hasattr(self, "_update_analysis_panel_modalities"):
            self._update_analysis_panel_modalities()
        if hasattr(self, "_refresh_lazy_modality_table"):
            self._refresh_lazy_modality_table()
        
        # Refresh image to update any modality-related displays
        self._request_ui_refresh("display-controls")
    def _contrast_sync_scope(self) -> str:
        """Return contrast sync target mode."""
        if self._sync_follow_active_enabled():
            return "active_group"
        return "manual_group"

    def _contrast_target_panels(self) -> List[str]:
        """Resolve panels affected by contrast edits from selected sync group."""
        panel_keys = list(getattr(self, "_panel_sync_index", {}).keys())
        selected = [
            key
            for key in self._selected_sync_panels(default_to_all=True)
            if self._sync_mode_enabled_for_panel(str(key), "contrast")
        ]
        return selected if selected else panel_keys[:1]

    def _on_sync_scope_changed(self, _text: str) -> None:
        """Update sync hint text for current target mode."""
        hint = getattr(self, "sync_scope_hint_lbl", None)
        scope = self._contrast_sync_scope()
        selected_key = str(getattr(getattr(self, "sync_key_combo", None), "currentData", lambda: "")() or "")
        if hint is not None:
            if scope == "active_group":
                hint.setText("Sync target follows active canvas view group.")
            else:
                hint.setText(
                    f"Sync target uses Group {selected_key}."
                    if selected_key.isdigit()
                    else "Select a manual Sync Group."
                )
        self._update_sync_keys_hint()

    def _select_all_sync_views(self) -> None:
        """Compatibility no-op: legacy linked-view list was removed."""
        return

    def _clear_sync_view_selection(self) -> None:
        """Compatibility no-op: legacy linked-view list was removed."""
        return
