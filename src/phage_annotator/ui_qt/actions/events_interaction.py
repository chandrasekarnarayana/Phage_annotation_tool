"""Event wiring and interaction handlers."""

from __future__ import annotations

import logging

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions.keyboard_events import KeyboardEventsMixin

logger = logging.getLogger(__name__)

class EventsInteractionMixin:
    """View state, interaction, and mouse event handlers."""

    def _toolbar_navigation_active(self) -> bool:
        """Return True when matplotlib toolbar pan/zoom mode is active."""
        toolbar = getattr(self, "toolbar", None)
        if toolbar is None:
            return False
        mode = str(getattr(toolbar, "mode", "") or "").strip().lower()
        return bool(mode)

    def _on_annotations_changed_event(self, event) -> None:
        """Handle annotation changes from event bus."""
        try:
            self._request_ui_refresh("annotations-event", table=True, image=True, status=True)
            QtCore.QTimer.singleShot(0, self._refresh_assist_warmup_panel)
        except Exception:
            logger.warning("Failed to handle AnnotationChangedEvent", exc_info=True)

    def _on_controller_view_changed(self) -> None:
        """Handle controller view changes with a lightweight path for linked zoom sync."""
        hint = str(getattr(self, "_controller_view_refresh_hint", "") or "").strip().lower()
        self._controller_view_refresh_hint = None
        if hint == "view_sync":
            self._request_ui_refresh("controller-view-sync", image=False, status=True)
            return
        self._request_ui_refresh("controller-view", image=True, status=True)

    def _on_view_state_changed_event(self, event) -> None:
        """Handle view state changes from event bus."""
        try:
            change_type = getattr(event, "change_type", None)

            if change_type == "t" and hasattr(self, "t_slider"):
                t_index = getattr(event, "t_index", None)
                if t_index is not None:
                    clamped = max(self.t_slider.minimum(), min(int(t_index), self.t_slider.maximum()))
                    if self.t_slider.value() != clamped:
                        self.t_slider.setValue(clamped)
                        return

            if change_type == "z" and hasattr(self, "z_slider"):
                z_index = getattr(event, "z_index", None)
                if z_index is not None:
                    clamped = max(self.z_slider.minimum(), min(int(z_index), self.z_slider.maximum()))
                    if self.z_slider.value() != clamped:
                        self.z_slider.setValue(clamped)
                        return

            if change_type == "view_sync":
                if not getattr(self, "_suppress_refresh", False):
                    self._request_ui_refresh("view-sync-event", status=True)
                return

            if not getattr(self, "_suppress_refresh", False):
                self._request_ui_refresh("view-state-event", image=True, status=True)
        except Exception:
            logger.warning("Failed to handle ViewStateChangedEvent", exc_info=True)

    def _on_cache_invalidation_event(self, event) -> None:
        """Handle cache invalidation from event bus."""
        try:
            # Invalidate relevant caches based on scope
            scope = getattr(event, 'scope', 'global')
            image_id = getattr(event, 'image_id', None)
            
            if hasattr(self, 'proj_cache') and self.proj_cache:
                if scope == 'image' and image_id is not None:
                    self.proj_cache.invalidate_image(image_id)
                elif scope == 'global' or scope == 'all':
                    self.proj_cache.clear()
        except Exception:
            logger.warning("Failed to handle CacheInvalidationEvent", exc_info=True)

    def reset_view(self) -> None:
        """Reset zoom/pan to full extent of current frame."""
        self._last_zoom_linked = None
        axes = []
        if getattr(self, "renderer", None) is not None:
            axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        for ax in axes:
            if ax is None:
                continue
            ax.set_xlim(auto=True)
            ax.set_ylim(auto=True)
        self._request_ui_refresh("events-reset-view")

    def reset_contrast(self) -> None:
        """Reset vmin/vmax to default percentiles of the primary image."""
        prim = self.primary_image
        if prim.array is None:
            self.vmin_slider.setValue(5)
            self.vmax_slider.setValue(95)
            return
        mapping = self._get_display_mapping(prim.id, "frame", prim.array)
        mapping.reset_to_auto(prim.array, low=5, high=95)
        self._sync_modality_display_settings("frame", mapping)
        self.vmin_slider.setValue(5)
        self.vmax_slider.setValue(95)
        self.vmin_label.setText(f"vmin: {mapping.min_val:.3f}")
        self.vmax_label.setText(f"vmax: {mapping.max_val:.3f}")
        self._request_ui_refresh("events-reset-contrast")

    def reset_all_view(self) -> None:
        """Reset zoom and contrast (ImageJ-like reset)."""
        self.reset_contrast()
        self.reset_view()

    def _start_interaction(self) -> None:
        """Enter interactive mode (downsample rendering during continuous input)."""
        self._interactive = True

    def _end_interaction(self) -> None:
        """Exit interactive mode and render full-resolution state."""
        self._interactive = False
        self._request_render_refresh("events-end-interaction", debounce=True)

    def _schedule_refresh(self) -> None:
        """Debounce refreshes during interactive input to avoid UI stalls."""
        if self._interactive:
            self._debounce_timer.start()
        else:
            self._request_ui_refresh("events-schedule-refresh")

    def _on_t_slider_pressed(self) -> None:
        """Pause prefetch to allow a user-initiated seek during playback."""
        if self._playback_mode:
            self._playback_ring.reset()

    def _on_t_slider_released(self) -> None:
        """Restart prefetch after a user scrub to the new T index."""
        if not self._playback_mode:
            return
        prim = self.primary_image
        if prim.array is None:
            return
        self._playback_ring.reset()
        self._playback_cursor = self.t_slider.value()
        if hasattr(self, "_restart_playback_prefetch"):
            self._restart_playback_prefetch(self._playback_cursor)

    def _on_z_slider_pressed(self) -> None:
        """Document the on_z_slider_pressed flow."""
        if self._playback_mode:
            self._playback_ring.reset()

    def _on_z_slider_released(self) -> None:
        """Document the on_z_slider_released flow."""
        if not self._playback_mode:
            return
        prim = self.primary_image
        if prim.array is None:
            return
        self._playback_ring.reset()
        self._playback_cursor = self.t_slider.value()
        if hasattr(self, "_restart_playback_prefetch"):
            self._restart_playback_prefetch(self._playback_cursor)

    def _on_mouse_press(self, event) -> None:
        """Document the on_mouse_press flow."""
        if self._toolbar_navigation_active():
            return
        if self._interactive:
            return
        self._start_interaction()

    def _on_mouse_release(self, event) -> None:
        """Document the on_mouse_release flow."""
        if self._toolbar_navigation_active():
            return
        if not self._interactive:
            return
        self._end_interaction()

    def _on_mouse_move(self, event) -> None:
        """Document the on_mouse_move flow."""
        if self._toolbar_navigation_active():
            QtWidgets.QToolTip.hideText()
            return
        if self._interactive:
            QtWidgets.QToolTip.hideText()
            self._schedule_refresh()
            return
        self._update_suggestion_hover_tooltip(event)

    def _update_suggestion_hover_tooltip(self, event) -> None:
        """Show suggestion details on hover near a visible suggestion marker."""
        inaxes = getattr(event, "inaxes", None)
        if inaxes is None or getattr(event, "xdata", None) is None or getattr(event, "ydata", None) is None:
            QtWidgets.QToolTip.hideText()
            return
        panel_axes = []
        if getattr(self, "renderer", None) is not None:
            panel_axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        if inaxes not in panel_axes:
            QtWidgets.QToolTip.hideText()
            return
        if not bool(getattr(self, "_show_suggestion_overlay", True)):
            QtWidgets.QToolTip.hideText()
            return

        suggestions = []
        if hasattr(self, "_visible_suggestions"):
            suggestions = list(self._visible_suggestions())
        if not suggestions:
            QtWidgets.QToolTip.hideText()
            return

        hover_radius = max(4.0, float(getattr(self, "click_radius_px", 6.0)) * 1.5)
        best = None
        best_dist = None
        for suggestion in suggestions:
            sx, sy = self._to_display_coords(inaxes, float(suggestion.x), float(suggestion.y))
            dx = float(event.xdata) - float(sx)
            dy = float(event.ydata) - float(sy)
            dist = float((dx * dx + dy * dy) ** 0.5)
            if dist > hover_radius:
                continue
            if best is None or dist < float(best_dist):
                best = suggestion
                best_dist = dist
        if best is None:
            QtWidgets.QToolTip.hideText()
            return

        meta = dict(getattr(best, "meta", {}) or {})
        confidence_available = bool(meta.get("confidence_available", False))
        generator_score = float(
            meta.get("generator_score", getattr(best, "score", getattr(best, "confidence", 0.0)))
        )
        state_txt = "Heuristic"
        if hasattr(self, "_canonical_assist_state"):
            state_txt = assist_state_label(self._canonical_assist_state([best]))
        if confidence_available:
            p_accept = float(meta.get("p_accept", getattr(best, "score", 0.0)))
            if p_accept >= 0.75:
                triage = "likely accept"
            elif p_accept >= 0.5:
                triage = "needs review"
            else:
                triage = "unlikely accept"
            lines = [
                f"Generator score: {generator_score:.2f}",
                f"Acceptance likelihood (p_accept): {p_accept:.2f} ({triage})",
                "p_accept predicts acceptance behavior, not ground-truth correctness.",
                f"Assist state: {state_txt}",
            ]
        else:
            lines = [
                f"Generator score: {generator_score:.2f}",
                "Acceptance likelihood (p_accept): not available (heuristic only)",
                f"Assist state: {state_txt}",
            ]
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "\n".join(lines), self.canvas)
