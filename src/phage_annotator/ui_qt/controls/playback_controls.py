"""Extracted method group 2 for DisplayControlsMixin."""

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



class PlaybackControlsMixin:
    """Method group 2 extracted from DisplayControlsMixin."""

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
        """Set support combo for the current workflow."""
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
        """Toggle play for the current workflow."""
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
        """Initialize modality playback for the current workflow."""
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
        """Handle the on modality frame changed helper flow."""
        if self._playback_mode:
            return
        if getattr(self, "t_slider", None) is None:
            return
        self.t_slider.blockSignals(True)
        self.t_slider.setValue(int(frame_idx))
        self.t_slider.blockSignals(False)
        self._request_ui_refresh("display-controls")
