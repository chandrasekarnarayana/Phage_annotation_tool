"""Playback helpers for high-FPS viewing."""

from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.utils.constants import DEBUG_FPS, FPS_UPDATE_STRIDE


class PlaybackMixin:
    """Mixin for playback thread handling and frame stepping."""

    def _playback_source_panel_key(self) -> str:
        layout_spec = self._current_layout_spec() if hasattr(self, "_current_layout_spec") else {}
        order = list(layout_spec.get("order", []) or [])
        visibility = dict(layout_spec.get("panel_visibility", {}) or {})
        visible = [key for key in order if bool(visibility.get(key, False))]
        if visible:
            return str(visible[0])
        if hasattr(self, "_display_source_panel_key"):
            return str(self._display_source_panel_key())
        return "frame"

    def _playback_source_image(self):
        panel_key = self._playback_source_panel_key()
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        modality = panel_map.get(panel_key)
        if modality is not None and hasattr(self, "_image_obj_from_id"):
            img = self._image_obj_from_id(int(getattr(modality, "image_id", -1)))
            if img is not None:
                return img
        if panel_key == "support":
            return self.support_image
        return self.primary_image

    def _playback_source_is_raw(self) -> bool:
        panel_key = self._playback_source_panel_key()
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        modality = panel_map.get(panel_key)
        if modality is None:
            return panel_key in {"frame", "support"}
        projection = str(getattr(getattr(modality, "projection_type", None), "value", "raw")).strip().lower()
        return projection == "raw"

    def _playback_target_axis(self):
        if getattr(self, "renderer", None) is None:
            return None
        ax = self.renderer.axes.get("frame")
        if ax is not None:
            return ax
        return next(iter(self.renderer.axes.values()), None)

    def start_playback_t(self, fps: Optional[int] = None) -> None:
        """Start high-FPS playback along the time axis with prefetch buffer."""
        source_img = self._playback_source_image()
        if source_img is None:
            return
        if not self._playback_source_is_raw():
            if hasattr(self, "_set_status"):
                self._set_status("Playback is only available for Source Frame panels.")
            return
        self._ensure_loaded(int(getattr(source_img, "id", self.current_image_idx)))
        source_img = self._playback_source_image()
        if source_img is None or getattr(source_img, "array", None) is None:
            return
        if int(source_img.array.shape[0]) <= 1:
            if hasattr(self, "_set_status"):
                self._set_status("Current source frame has only one timepoint.")
            return
        # Heavy refresh once to ensure artists/vmin/vmax exist.
        frame_ax = self._playback_target_axis()
        if self.im_frame is None or frame_ax is None or self._axis_scale(frame_ax) != 1.0:
            self._refresh_image()
        self._playback_mode = True
        self.play_mode = "t"
        if fps is not None:
            self.speed_slider.setValue(fps)
        self._playback_cursor = self.t_slider.value()
        self._playback_ring.reset()
        self._prefetcher.start(self._playback_cursor, self.z_slider.value())
        self._start_playback_thread()
        self._update_status()

    def stop_playback_t(self) -> None:
        """Stop playback and clear prefetch buffer."""
        if not self._playback_mode:
            return
        self._playback_mode = False
        self.play_mode = None
        self._playback_stop_event.set()
        if self._playback_thread is not None:
            self._playback_thread.join(timeout=1.0)
        self._playback_thread = None
        self._playback_stop_event.clear()
        self._playback_ring.reset()
        self._prefetcher.stop()
        self._update_status()

    def _start_playback_thread(self) -> None:
        if self._playback_thread is not None:
            return
        self._playback_thread = threading.Thread(target=self._playback_tick, daemon=True)
        self._playback_thread.start()

    def _playback_tick(self) -> None:
        self._last_frame_time = time.monotonic()
        while self._playback_mode:
            fps = max(1, self.speed_slider.value())
            sleep_time = 1.0 / fps
            frame = self._playback_ring.pop(timeout=sleep_time)
            if frame is None:
                self._playback_underruns += 1
                self._flash_status("Buffer underrun")
                QtCore.QMetaObject.invokeMethod(
                    self, "_update_buffer_stats", QtCore.Qt.QueuedConnection
                )
                time.sleep(sleep_time)
                continue
            self._playback_cursor += 1
            QtCore.QMetaObject.invokeMethod(
                self,
                "_update_frame_only",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(object, frame),
                QtCore.Q_ARG(int, self._playback_cursor),
            )
            source_img = self._playback_source_image()
            if self.loop_playback and source_img is not None and getattr(source_img, "array", None) is not None:
                t_max = source_img.array.shape[0] - 1
                if self._playback_cursor > t_max:
                    self._playback_cursor = 0
                    self._playback_ring.reset()
                    self._prefetcher.start(self._playback_cursor, self.z_slider.value())
            self._last_frame_time = time.monotonic()
            if DEBUG_FPS:
                self._update_fps_meter()
            time.sleep(sleep_time)

    def _update_frame_only(self, frame: np.ndarray, t_idx: int) -> None:
        if not self._playback_mode:
            return
        if self.im_frame is None:
            return
        self.im_frame.set_data(frame)
        frame_ax = self._playback_target_axis()
        if frame_ax is not None:
            title = frame_ax.get_title() or "Frame"
            base_title = title.split(" (T=", 1)[0]
            frame_ax.set_title(f"{base_title} (T={t_idx})")
        self._update_status()
        self.canvas.draw_idle()

    def _update_fps_meter(self) -> None:
        if self._playback_frame_counter % FPS_UPDATE_STRIDE == 0:
            now = time.monotonic()
            if self._last_frame_time is not None:
                dt = now - self._last_frame_time
                if dt > 0:
                    self._fps_times.append(1.0 / dt)
        self._playback_frame_counter += 1
        frame_ax = self._playback_target_axis()
        if self._fps_text is None and frame_ax is not None:
            self._fps_text = frame_ax.text(
                0.02, 0.98, "", transform=frame_ax.transAxes, color="w"
            )
        if self._fps_text is not None and self._fps_times:
            fps = sum(self._fps_times) / len(self._fps_times)
            self._fps_text.set_text(f"FPS: {fps:.1f}")

    def _step_slider(self, slider: QtWidgets.QSlider, direction: int) -> None:
        value = slider.value() + direction
        slider.setValue(max(slider.minimum(), min(slider.maximum(), value)))
