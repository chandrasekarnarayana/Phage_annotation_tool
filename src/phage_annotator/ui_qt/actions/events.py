"""Event wiring and interaction handlers."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions.keyboard_events import KeyboardEventsMixin


class EventsMixin(KeyboardEventsMixin):
    """Mixin for Qt/matplotlib event handlers and interaction state."""

    def _bind_events(self) -> None:
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("key_press_event", self._on_key)
        self.canvas.mpl_connect("button_press_event", self._on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self._on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self._bind_axis_callbacks()
        self.fov_list.currentRowChanged.connect(self._set_fov)
        self.primary_combo.currentIndexChanged.connect(self._set_primary_combo)
        self.support_combo.currentIndexChanged.connect(self._set_support_combo)
        self.play_t_btn.clicked.connect(lambda: self._toggle_play("t"))
        self.play_z_btn.clicked.connect(lambda: self._toggle_play("z"))
        self.t_minus_button.clicked.connect(lambda: self._step_slider(self.t_slider, -1))
        self.t_plus_button.clicked.connect(lambda: self._step_slider(self.t_slider, 1))
        self.z_minus_button.clicked.connect(lambda: self._step_slider(self.z_slider, -1))
        self.z_plus_button.clicked.connect(lambda: self._step_slider(self.z_slider, 1))
        self.speed_minus_button.clicked.connect(lambda: self._step_slider(self.speed_slider, -1))
        self.speed_plus_button.clicked.connect(lambda: self._step_slider(self.speed_slider, 1))
        self.t_slider.valueChanged.connect(self._on_play_tick)
        self.z_slider.valueChanged.connect(self._on_play_tick)
        self.speed_slider.valueChanged.connect(self._on_speed_change)
        self.t_slider.sliderPressed.connect(self._on_t_slider_pressed)
        self.t_slider.sliderReleased.connect(self._on_t_slider_released)
        self.z_slider.sliderPressed.connect(self._on_z_slider_pressed)
        self.z_slider.sliderReleased.connect(self._on_z_slider_released)
        self.loop_chk.stateChanged.connect(self._on_loop_change)
        self.axis_mode_combo.currentTextChanged.connect(self._on_axis_mode_change)
        self.vmin_slider.valueChanged.connect(self._on_vminmax_change)
        self.vmax_slider.valueChanged.connect(self._on_vminmax_change)
        self.vmin_minus_button.clicked.connect(lambda: self._step_slider(self.vmin_slider, -1))
        self.vmin_plus_button.clicked.connect(lambda: self._step_slider(self.vmin_slider, 1))
        self.vmax_minus_button.clicked.connect(lambda: self._step_slider(self.vmax_slider, -1))
        self.vmax_plus_button.clicked.connect(lambda: self._step_slider(self.vmax_slider, 1))
        self.vmin_slider.sliderPressed.connect(self._on_contrast_slider_pressed)
        self.vmin_slider.sliderReleased.connect(self._on_contrast_slider_released)
        self.vmax_slider.sliderPressed.connect(self._on_contrast_slider_pressed)
        self.vmax_slider.sliderReleased.connect(self._on_contrast_slider_released)
        self.auto_btn.clicked.connect(self._auto_contrast)
        self.auto_set_btn.clicked.connect(self._auto_set_dialog)
        self.pixel_size_spin.valueChanged.connect(self._on_pixel_size_change)
        self.reset_view_btn.clicked.connect(self.reset_all_view)
        self.lut_combo.currentIndexChanged.connect(self._on_lut_change)
        self.lut_invert_chk.stateChanged.connect(self._on_lut_invert)
        self.gamma_slider.valueChanged.connect(self._on_gamma_change)
        self.log_chk.stateChanged.connect(self._on_log_toggle)
        # Wire up projection selector widget (Phase γ)
        if getattr(self, "projection_selector", None) is not None:
            self.projection_selector.projection_changed.connect(
                self._on_projection_changed
            )
        elif getattr(self, "projection_axis_combo", None) is not None:
            # Backward compat for old axis-only combo
            self.projection_axis_combo.currentTextChanged.connect(
                self._on_projection_axis_change
            )
        if getattr(self, "sync_list", None) is not None:
            self.sync_list.itemSelectionChanged.connect(self._on_sync_selection_changed)
        if getattr(self, "sync_playback_chk", None) is not None:
            self.sync_playback_chk.stateChanged.connect(self._on_sync_mode_changed)
        if getattr(self, "sync_zoom_chk", None) is not None:
            self.sync_zoom_chk.stateChanged.connect(self._on_sync_mode_changed)
        if getattr(self, "sync_contrast_chk", None) is not None:
            self.sync_contrast_chk.stateChanged.connect(self._on_sync_mode_changed)
        self.label_buttons.buttonClicked.connect(self._on_label_change)
        self.scope_group.buttonClicked.connect(self._on_scope_change)
        self.target_group.buttonClicked.connect(self._on_target_change)
        self.marker_size_spin.valueChanged.connect(self._on_marker_size_change)
        self.click_radius_spin.valueChanged.connect(self._on_click_radius_change)
        self.show_profile_chk.stateChanged.connect(self._on_profile_chk_changed)
        self.show_hist_chk.stateChanged.connect(self._on_hist_chk_changed)
        self.profile_clear_btn.clicked.connect(self._clear_profile)
        self.hist_region_combo.currentIndexChanged.connect(self._on_hist_region)
        self.hist_scope_combo.currentIndexChanged.connect(self._on_hist_scope_change)
        if getattr(self, "bc_range_slider", None) is not None:
            self.bc_range_slider.rangeChanged.connect(self._on_bc_range_changed)
        if getattr(self, "bc_min_slider", None) is not None:
            self.bc_min_slider.valueChanged.connect(self._on_bc_min_slider)
            self.bc_max_slider.valueChanged.connect(self._on_bc_max_slider)
        if getattr(self, "bc_min_spin", None) is not None:
            self.bc_min_spin.valueChanged.connect(self._on_bc_min_spin)
            self.bc_max_spin.valueChanged.connect(self._on_bc_max_spin)
            self.bc_brightness_slider.valueChanged.connect(self._on_bc_brightness_change)
            self.bc_contrast_slider.valueChanged.connect(self._on_bc_contrast_change)
            self.bc_auto_btn.clicked.connect(self._auto_contrast)
            self.bc_reset_btn.clicked.connect(self.reset_contrast)
            self.bc_set_btn.clicked.connect(self._bc_set_from_inputs)
            if getattr(self, "bc_dialog_btn", None) is not None:
                self.bc_dialog_btn.clicked.connect(self._open_contrast_dialog)
            self.bc_apply_btn.clicked.connect(self._apply_display_mapping)
        self.roi_shape_group.buttonClicked.connect(self._on_roi_shape_change)
        self.roi_x_spin.valueChanged.connect(self._on_roi_change)
        self.roi_y_spin.valueChanged.connect(self._on_roi_change)
        self.roi_w_spin.valueChanged.connect(self._on_roi_change)
        self.roi_h_spin.valueChanged.connect(self._on_roi_change)
        self.crop_x_spin.valueChanged.connect(self._on_crop_change)
        self.crop_y_spin.valueChanged.connect(self._on_crop_change)
        self.crop_w_spin.valueChanged.connect(self._on_crop_change)
        self.crop_h_spin.valueChanged.connect(self._on_crop_change)
        if getattr(self, "auto_roi_btn", None) is not None:
            self.auto_roi_btn.clicked.connect(self._run_auto_roi)
        if getattr(self, "auto_roi_mode_combo", None) is not None:
            self.auto_roi_mode_combo.currentTextChanged.connect(self._auto_roi_mode_changed)
            self._auto_roi_mode_changed(self.auto_roi_mode_combo.currentText())
        if getattr(self, "auto_roi_shape_combo", None) is not None:
            self.auto_roi_shape_combo.currentTextChanged.connect(self._persist_auto_roi_settings)
        if getattr(self, "auto_roi_mode_combo", None) is not None:
            self.auto_roi_mode_combo.currentTextChanged.connect(self._persist_auto_roi_settings)
        if getattr(self, "auto_roi_w_spin", None) is not None:
            self.auto_roi_w_spin.valueChanged.connect(self._persist_auto_roi_settings)
        if getattr(self, "auto_roi_h_spin", None) is not None:
            self.auto_roi_h_spin.valueChanged.connect(self._persist_auto_roi_settings)
        if getattr(self, "auto_roi_area_spin", None) is not None:
            self.auto_roi_area_spin.valueChanged.connect(self._persist_auto_roi_settings)
        self.annot_table.itemSelectionChanged.connect(self._on_table_selection)
        self.annot_table.itemChanged.connect(self._on_table_item_changed)
        self.filter_current_chk.stateChanged.connect(lambda _state: self._refresh_table())
        if hasattr(self, "auto_follow_table_chk"):
            self.auto_follow_table_chk.stateChanged.connect(self._on_auto_follow_table_changed)
        self.show_ann_master_chk.stateChanged.connect(self._refresh_image)
        self.clear_fovs_btn.clicked.connect(self._clear_fov_list)
        if self.roi_manager_widget is not None:
            widget = self.roi_manager_widget
            widget.add_btn.clicked.connect(self._roi_mgr_add)
            widget.del_btn.clicked.connect(self._roi_mgr_delete)
            widget.rename_btn.clicked.connect(self._roi_mgr_rename)
            widget.dup_btn.clicked.connect(self._roi_mgr_duplicate)
            widget.save_btn.clicked.connect(self._roi_mgr_save)
            widget.load_btn.clicked.connect(self._roi_mgr_load)
            widget.measure_btn.clicked.connect(self._roi_mgr_measure)
            widget.table.itemSelectionChanged.connect(self._roi_mgr_selection_changed)
            widget.table.itemChanged.connect(self._roi_mgr_item_changed)
        if self.results_widget is not None:
            rw = self.results_widget
            rw.measure_btn.clicked.connect(self._results_measure_current)
            rw.measure_t_btn.clicked.connect(self._results_measure_over_time)
            rw.clear_btn.clicked.connect(self._results_clear)
            rw.copy_btn.clicked.connect(self._results_copy)
            rw.export_btn.clicked.connect(self._results_export)
        if self.smlm_panel is not None:
            sw = self.smlm_panel.thunder
            sw.run_btn.clicked.connect(self._run_smlm)
            sw.cancel_btn.clicked.connect(self._cancel_smlm)
            sw.export_csv_btn.clicked.connect(self._export_smlm_csv)
            sw.export_h5_btn.clicked.connect(self._export_smlm_hdf5)
            sw.add_ann_btn.clicked.connect(self._smlm_to_annotations)
            self.smlm_panel.preset_combo.currentTextChanged.connect(self._apply_smlm_preset)
        if self.smlm_panel is not None:
            dw = self.smlm_panel.deep
            dw.run_btn.clicked.connect(self._run_deepstorm)
            dw.cancel_btn.clicked.connect(self._cancel_deepstorm)
            dw.export_csv_btn.clicked.connect(self._export_deepstorm_csv)
            dw.export_sr_btn.clicked.connect(self._export_deepstorm_sr)
            dw.add_ann_btn.clicked.connect(self._deepstorm_to_annotations)
            dw.browse_btn.clicked.connect(self._browse_deepstorm_model)
        if self.threshold_panel is not None:
            tp = self.threshold_panel
            tp.method_combo.currentTextChanged.connect(self._threshold_method_changed)
            tp.auto_btn.clicked.connect(self._threshold_auto)
            tp.low_slider.valueChanged.connect(self._threshold_manual_changed)
            tp.high_slider.valueChanged.connect(self._threshold_manual_changed)
            tp.region_chk.stateChanged.connect(self._threshold_refresh_preview)
            tp.scope_combo.currentTextChanged.connect(self._threshold_refresh_preview)
            tp.sample_spin.valueChanged.connect(self._threshold_refresh_preview)
            tp.invert_chk.stateChanged.connect(self._threshold_refresh_preview)
            tp.background_combo.currentTextChanged.connect(self._threshold_refresh_preview)
            tp.smooth_spin.valueChanged.connect(self._threshold_refresh_preview)
            tp.preview_chk.stateChanged.connect(self._threshold_refresh_preview)
            tp.min_area_spin.valueChanged.connect(self._threshold_refresh_preview)
            tp.fill_holes_chk.stateChanged.connect(self._threshold_refresh_preview)
            tp.open_spin.valueChanged.connect(self._threshold_refresh_preview)
            tp.close_spin.valueChanged.connect(self._threshold_refresh_preview)
            tp.despeckle_chk.stateChanged.connect(self._threshold_refresh_preview)
            tp.target_combo.currentTextChanged.connect(self._threshold_refresh_preview)
            tp.create_mask_btn.clicked.connect(self._threshold_create_mask)
            tp.create_roi_btn.clicked.connect(self._threshold_create_roi)
            tp.analyze_btn.clicked.connect(self._threshold_analyze_particles)
            tp.apply_btn.clicked.connect(self._threshold_apply_destructive)
        if self.particles_panel is not None:
            pp = self.particles_panel
            pp.measure_btn.clicked.connect(self._run_analyze_particles)
            pp.export_btn.clicked.connect(self._export_particles_csv)
            pp.selection_btn.clicked.connect(self._particles_create_selection)
            pp.table.itemSelectionChanged.connect(self._particles_selection_changed)
            pp.show_outlines_chk.stateChanged.connect(self._particles_refresh_overlay)
            pp.show_boxes_chk.stateChanged.connect(self._particles_refresh_overlay)
            pp.show_ellipses_chk.stateChanged.connect(self._particles_refresh_overlay)
            pp.show_labels_chk.stateChanged.connect(self._particles_refresh_overlay)
        self._bind_application_events()

    def _bind_application_events(self) -> None:
        """Subscribe to application-level events from the event bus.
        
        This integrates GUI with the event service, allowing components
        to react to state changes without direct coupling.
        """
        try:
            from phage_annotator.framework import get_event_service
            from phage_annotator.framework.events import (
                AnnotationChangedEvent,
                ViewStateChangedEvent,
                CacheInvalidationEvent,
            )
            
            event_service = get_event_service()
            
            # When annotations change, refresh the annotation table and overlay
            event_service.subscribe(
                AnnotationChangedEvent,
                lambda evt: self._on_annotations_changed_event(evt),
            )
            
            # When view state changes (T, Z, crop), refresh rendering
            event_service.subscribe(
                ViewStateChangedEvent,
                lambda evt: self._on_view_state_changed_event(evt),
            )
            
            # When cache is invalidated, clear relevant caches
            event_service.subscribe(
                CacheInvalidationEvent,
                lambda evt: self._on_cache_invalidation_event(evt),
            )
        except (ImportError, AttributeError, RuntimeError):
            # Event service not available or not initialized; continue gracefully
            pass

    def _on_annotations_changed_event(self, event) -> None:
        """Handle annotation changes from event bus."""
        try:
            # Refresh annotation table to show latest annotations
            if hasattr(self, '_refresh_table'):
                self._refresh_table()
            # Refresh rendering to show/hide annotation overlay
            if hasattr(self, '_refresh_image'):
                self._refresh_image()
        except Exception:
            # Silently ignore errors in event handling
            pass

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

            if hasattr(self, "_refresh_image") and not getattr(self, "_suppress_refresh", False):
                self._refresh_image()
        except Exception:
            # Silently ignore errors in event handling
            pass

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
            # Silently ignore errors in event handling
            pass

    def _bind_axis_callbacks(self) -> None:
        """Bind zoom callbacks for current axes to keep zoom synced."""
        axes = []
        if getattr(self, "renderer", None) is not None:
            axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        for ax in axes:
            ax.callbacks.connect("xlim_changed", self._on_limits_changed)
            ax.callbacks.connect("ylim_changed", self._on_limits_changed)

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
        self._refresh_image()

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
        self._refresh_image()

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
        self._refresh_image()

    def _schedule_refresh(self) -> None:
        """Debounce refreshes during interactive input to avoid UI stalls."""
        if self._interactive:
            self._debounce_timer.start()
        else:
            self._refresh_image()

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
        self._prefetcher.start(self._playback_cursor, self.z_slider.value())

    def _on_z_slider_pressed(self) -> None:
        if self._playback_mode:
            self._playback_ring.reset()

    def _on_z_slider_released(self) -> None:
        if not self._playback_mode:
            return
        prim = self.primary_image
        if prim.array is None:
            return
        self._playback_ring.reset()
        self._playback_cursor = self.t_slider.value()
        self._prefetcher.start(self._playback_cursor, self.z_slider.value())

    def _on_mouse_press(self, event) -> None:
        if self._interactive:
            return
        self._start_interaction()

    def _on_mouse_release(self, event) -> None:
        if not self._interactive:
            return
        self._end_interaction()

    def _on_mouse_move(self, event) -> None:
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
                triage = "likely correct"
            elif p_accept >= 0.5:
                triage = "review recommended"
            else:
                triage = "likely reject"
            lines = [
                f"Generator score: {generator_score:.2f}",
                f"Calibrated p_accept: {p_accept:.2f} ({triage})",
                f"Assist state: {state_txt}",
            ]
        else:
            lines = [
                f"Generator score: {generator_score:.2f}",
                "Calibrated p_accept: not available (heuristic only)",
                f"Assist state: {state_txt}",
            ]
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "\n".join(lines), self.canvas)
