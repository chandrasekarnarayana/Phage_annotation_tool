"""Extracted method group 1 for EventsMixin."""

from __future__ import annotations

import logging

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions.keyboard_events import KeyboardEventsMixin

logger = logging.getLogger(__name__)



class EventsMixinCoreMixin:
    """Method group 1 extracted from EventsMixin."""

    def _bind_events(self) -> None:
        """Bind widget, controller, and application events.

        UI events remain thin and route mutations through controller/state
        services whenever possible. Expensive refresh work is queued on the
        Qt loop to avoid one widget interaction starving the rest of the GUI.
        """
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("key_press_event", self._on_key)
        self.canvas.mpl_connect("button_press_event", self._on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self._on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self._bind_axis_callbacks()
        if getattr(self, "lazy_modality_table", None) is not None:
            self.lazy_modality_table.itemChanged.connect(self._on_lazy_modality_item_changed)
        if getattr(self, "lazy_open_btn", None) is not None:
            self.lazy_open_btn.pressed.connect(self._open_lazy_loader_dialog)
        if getattr(self, "lazy_clear_btn", None) is not None:
            self.lazy_clear_btn.pressed.connect(self._clear_lazy_loader_sources)
        if getattr(self, "lazy_loader_tree", None) is not None:
            self.lazy_loader_tree.currentItemChanged.connect(
                self._on_lazy_loader_tree_item_changed
            )
        if getattr(self, "lazy_add_raw_btn", None) is not None:
            self.lazy_add_raw_btn.pressed.connect(lambda: self._add_lazy_modality_view("raw"))
        if getattr(self, "lazy_add_mean_btn", None) is not None:
            self.lazy_add_mean_btn.pressed.connect(lambda: self._add_lazy_modality_view("mean"))
        if getattr(self, "lazy_add_std_btn", None) is not None:
            self.lazy_add_std_btn.pressed.connect(lambda: self._add_lazy_modality_view("std"))
        if getattr(self, "lazy_remove_btn", None) is not None:
            self.lazy_remove_btn.pressed.connect(self._remove_selected_lazy_modality_view)
        if getattr(self, "lazy_auto_update_chk", None) is not None:
            self.lazy_auto_update_chk.toggled.connect(self._on_lazy_auto_update_toggled)
        if getattr(self, "lazy_apply_btn", None) is not None:
            self.lazy_apply_btn.pressed.connect(self._apply_lazy_pending_updates)
        if getattr(self, "controller", None) is not None:
            self._bind_controller_signals()
        self.play_t_btn.clicked.connect(lambda: self._toggle_play("t"))
        self.play_z_btn.clicked.connect(lambda: self._toggle_play("z"))
        if getattr(self, "play_timer", None) is not None:
            self.play_timer.timeout.connect(self._on_play_timer_tick)
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
        if getattr(self, "pixel_size_spin", None) is not None:
            self.pixel_size_spin.valueChanged.connect(self._on_pixel_size_change)
        if getattr(self, "reset_view_btn", None) is not None:
            self.reset_view_btn.clicked.connect(self.reset_all_view)
        self.lut_combo.currentIndexChanged.connect(self._on_lut_change)
        self.lut_invert_chk.stateChanged.connect(self._on_lut_invert)
        self.gamma_slider.valueChanged.connect(self._on_gamma_change)
        self.log_chk.stateChanged.connect(self._on_log_toggle)
        # Wire up projection selector widget
        if getattr(self, "projection_selector", None) is not None:
            self.projection_selector.projection_changed.connect(
                self._on_projection_changed
            )
        elif getattr(self, "projection_axis_combo", None) is not None:
            # Backward compat for old axis-only combo
            self.projection_axis_combo.currentTextChanged.connect(
                self._on_projection_axis_change
            )
        if getattr(self, "sync_key_combo", None) is not None:
            self.sync_key_combo.currentIndexChanged.connect(self._on_sync_key_changed)
        if getattr(self, "sync_target_mode_combo", None) is not None:
            self.sync_target_mode_combo.currentIndexChanged.connect(self._on_sync_mode_changed)
        if getattr(self, "sync_follow_active_chk", None) is not None:
            self.sync_follow_active_chk.toggled.connect(self._on_sync_mode_changed)
        self.label_buttons.buttonClicked.connect(self._on_label_change)
        self.scope_group.buttonClicked.connect(self._on_scope_change)
        if getattr(self, "annotate_target_combo", None) is not None:
            self.annotate_target_combo.currentIndexChanged.connect(self._on_target_change)
        elif getattr(self, "target_group", None) is not None:
            self.target_group.buttonClicked.connect(self._on_target_change)
        self.marker_size_spin.valueChanged.connect(self._on_marker_size_change)
        if getattr(self, "annotate_marker_size_spin", None) is not None:
            self.annotate_marker_size_spin.valueChanged.connect(self._on_marker_size_change)
        if getattr(self, "annotate_marker_shape_combo", None) is not None:
            self.annotate_marker_shape_combo.currentIndexChanged.connect(self._on_marker_shape_change)
        self.click_radius_spin.valueChanged.connect(self._on_click_radius_change)
        self.show_profile_chk.stateChanged.connect(self._on_profile_chk_changed)
        self.show_hist_chk.stateChanged.connect(self._on_hist_chk_changed)
        self.profile_clear_btn.clicked.connect(self._clear_profile)
        if getattr(self, "hist_region_combo", None) is not None:
            self.hist_region_combo.currentIndexChanged.connect(self._on_hist_region)
        if getattr(self, "hist_scope_combo", None) is not None:
            self.hist_scope_combo.currentIndexChanged.connect(self._on_hist_scope_change)
        if getattr(self, "hist_bins_spin", None) is not None:
            self.hist_bins_spin.valueChanged.connect(lambda _value: self._request_ui_refresh("display-controls"))
        if getattr(self, "contrast_hist_region_combo", None) is not None:
            self.contrast_hist_region_combo.currentIndexChanged.connect(self._on_hist_region)
        if getattr(self, "contrast_hist_scope_combo", None) is not None:
            self.contrast_hist_scope_combo.currentIndexChanged.connect(self._on_hist_scope_change)
        if getattr(self, "contrast_hist_bins_spin", None) is not None:
            self.contrast_hist_bins_spin.valueChanged.connect(
                lambda _value: self._request_ui_refresh("display-controls")
            )
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
        if getattr(self, "roi_shape_group", None) is not None:
            self.roi_shape_group.buttonClicked.connect(self._on_roi_shape_change)
        for attr in ("roi_x_spin", "roi_y_spin", "roi_w_spin", "roi_h_spin"):
            spin = getattr(self, attr, None)
            if spin is not None:
                spin.valueChanged.connect(self._on_roi_change)
        for attr in ("crop_x_spin", "crop_y_spin", "crop_w_spin", "crop_h_spin"):
            spin = getattr(self, attr, None)
            if spin is not None:
                spin.valueChanged.connect(self._on_crop_change)
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
        if hasattr(self, "annotation_table_mode_combo"):
            self.annotation_table_mode_combo.currentIndexChanged.connect(lambda _idx: self._refresh_table())
            self.annotation_table_source_filter.currentIndexChanged.connect(lambda _idx: self._refresh_table())
            self.annotation_table_status_filter.currentIndexChanged.connect(lambda _idx: self._refresh_table())
            self.annotation_table_candidate_filter.currentIndexChanged.connect(lambda _idx: self._refresh_table())
            self.annotation_table_roi_filter.currentIndexChanged.connect(lambda _idx: self._refresh_table())
        if hasattr(self, "auto_follow_table_chk"):
            self.auto_follow_table_chk.stateChanged.connect(self._on_auto_follow_table_changed)
        if getattr(self, "review_queue_panel", None) is not None:
            self.review_queue_panel.filter_combo.currentIndexChanged.connect(
                lambda _idx: self._set_review_queue_filter(
                    str(self.review_queue_panel.filter_combo.currentData() or "all")
                )
            )
            self.review_queue_panel.sort_combo.currentIndexChanged.connect(
                lambda _idx: self._refresh_review_queue_panel()
            )
        self.show_ann_master_chk.stateChanged.connect(self._on_show_annotations_master_changed)
        if self.roi_manager_widget is not None:
            widget = self.roi_manager_widget
            widget.add_btn.clicked.connect(self._roi_mgr_add)
            widget.del_btn.clicked.connect(self._roi_mgr_delete)
            widget.deselect_btn.clicked.connect(self._roi_mgr_deselect)
            widget.update_btn.clicked.connect(self._roi_mgr_update)
            widget.rename_btn.clicked.connect(self._roi_mgr_rename)
            widget.dup_btn.clicked.connect(self._roi_mgr_duplicate)
            widget.save_btn.clicked.connect(self._roi_mgr_save)
            widget.load_btn.clicked.connect(self._roi_mgr_load)
            widget.show_all_btn.toggled.connect(self._roi_mgr_show_all_toggled)
            widget.show_current_slice_only_btn.toggled.connect(self._roi_mgr_show_current_slice_only_toggled)
            widget.measure_btn.clicked.connect(self._roi_mgr_measure)
            widget.manage_tags_btn.clicked.connect(self._roi_mgr_manage_tags)
            widget.filter_by_tag_btn.clicked.connect(self._roi_mgr_filter_by_tag)
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
            sw.preflight_btn.clicked.connect(self._run_smlm_preflight)
            sw.export_csv_btn.clicked.connect(self._export_smlm_csv)
            sw.export_h5_btn.clicked.connect(self._export_smlm_hdf5)
            sw.add_ann_btn.clicked.connect(self._smlm_to_annotations)
            sw.show_points_chk.toggled.connect(self._toggle_smlm_points_from_panel)
            sw.lock_profile_btn.clicked.connect(self._lock_current_smlm_profile)
            sw.export_runbook_btn.clicked.connect(self._export_smlm_runbook)
            sw.repro_mode_chk.toggled.connect(self._on_smlm_runbook_toggled)
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
