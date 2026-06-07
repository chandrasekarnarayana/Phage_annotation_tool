"""Panel and runtime signal connection helpers for UI setup."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore


def connect_panel_runtime_signals(self: object, *, disable_qc: bool, disable_diagnostics: bool) -> None:
    """Connect panel widgets, runtime controls, and startup refresh hooks."""
    if getattr(self, "review_queue_panel", None) is not None:
        self.review_queue_panel.show_suggestions_chk.setChecked(
            bool(getattr(self, "_show_suggestion_overlay", True))
        )
        self.review_queue_panel.accept_requested.connect(
            self._accept_current_uncertain_suggestion
        )
        self.review_queue_panel.accept_next_requested.connect(
            self._accept_and_next_uncertain_suggestion
        )
        self.review_queue_panel.accept_all_green_requested.connect(
            self._accept_high_confidence_suggestions
        )
        self.review_queue_panel.reject_requested.connect(
            self._reject_current_uncertain_suggestion
        )
        self.review_queue_panel.skip_requested.connect(self._next_uncertain_suggestion)
        self.review_queue_panel.next_uncertain_requested.connect(
            self._focus_current_uncertain_suggestion
        )
        self.review_queue_panel.suggest_points_requested.connect(
            self._suggest_points_current_slice
        )
        self.review_queue_panel.clear_suggestions_requested.connect(
            self._clear_suggestions_current_image
        )
        self.review_queue_panel.show_suggestions_toggled.connect(
            self._toggle_suggestions_overlay
        )
        self.review_queue_panel.apply_offset_requested.connect(
            self._apply_review_queue_offset
        )
        self.review_queue_panel.suggestion_row_selected.connect(
            self._on_review_queue_row_selected
        )
        self.review_queue_panel.decision_requested.connect(
            self._set_selected_suggestion_decision
        )
    if getattr(self, "advanced_settings_panel", None) is not None:
        self.advanced_settings_panel.pixel_size_changed.connect(self._on_pixel_size_change)
        self.advanced_settings_panel.axis_mode_changed.connect(self._on_axis_mode_change)
        self.advanced_settings_panel.open_metadata_requested.connect(
            lambda: self.open_panel("metadata", reason="advanced_settings")
        )
        self.advanced_settings_panel.open_preferences_requested.connect(
            lambda: self._show_preferences_dialog()
        )
        self.advanced_settings_panel.retry_project_relink_requested.connect(
            self._retry_project_relink
        )
        self._refresh_advanced_settings_panel()
    if getattr(self, "dock_advanced_settings", None) is not None and getattr(self, "toggle_settings_act", None) is not None:
        self.toggle_settings_act.blockSignals(True)
        self.toggle_settings_act.setChecked(self.dock_advanced_settings.isVisible())
        self.toggle_settings_act.blockSignals(False)
        self.dock_advanced_settings.visibilityChanged.connect(
            lambda visible: (
                self.toggle_settings_act.blockSignals(True),
                self.toggle_settings_act.setChecked(bool(visible)),
                self.toggle_settings_act.blockSignals(False),
            )
        )
    self.quick_hist_act.triggered.connect(lambda _checked=False: self._toggle_hist_panel())
    self.quick_profile_act.triggered.connect(lambda _checked=False: self._toggle_profile_panel())
    if not disable_qc:
        self.quick_qc_act.triggered.connect(
            lambda _checked=False: self.set_panel_visible(
                "qc_issues", True, source="quick_button:qc"
            )
        )
    else:
        self.quick_qc_act.setEnabled(False)
        self.quick_qc_act.setVisible(False)
    for dock_attr in (
        "dock_hist",
        "dock_profile",
        "dock_qc_issues",
        "dock_density",
        "dock_logs",
        "dock_metadata",
        "dock_results",
        "dock_annotations",
        "dock_review_queue",
        "dock_advanced_settings",
        "dock_advanced_analysis",
    ):
        dock = getattr(self, dock_attr, None)
        if dock is not None:
            dock.visibilityChanged.connect(lambda _v: self._sync_panel_visibility_state())
    if self.density_panel is not None:
        self.density_panel.model_browse_btn.clicked.connect(self._density_pick_model)
        self.density_panel.load_btn.clicked.connect(self._density_load_model)
        self.density_panel.run_btn.clicked.connect(self._density_run)
        self.density_panel.cancel_btn.clicked.connect(self._density_cancel)
        self.density_panel.export_map_btn.clicked.connect(self._density_export_map)
        self.density_panel.export_counts_btn.clicked.connect(self._density_export_counts)
        self.density_panel.overlay_chk.toggled.connect(self._density_overlay_toggle)
        self.density_panel.overlay_alpha.valueChanged.connect(self._density_overlay_changed)
        self.density_panel.overlay_cmap.currentTextChanged.connect(
            self._density_overlay_changed
        )
        self.density_panel.contours_chk.toggled.connect(self._density_overlay_changed)
    if getattr(self, "qc_issues_panel", None) is not None and not disable_qc:
        self.qc_issues_panel.jump_to_location.connect(self._jump_to_qc_issue)
        self.qc_issues_panel.validation_requested.connect(self._trigger_qc_validation)
        self.qc_issues_panel.export_requested.connect(self._export_qc_report)
        self.qc_issues_panel.issue_status_changed.connect(self._on_qc_issue_status_changed)
    if hasattr(self, "annotation_meta_apply_btn"):
        self.annotation_meta_apply_btn.clicked.connect(self._apply_annotation_metadata)
        self.annotation_meta_close_btn.clicked.connect(self._dismiss_annotation_meta_banner)
    self._sync_panel_visibility_state()
    self._update_qc_button_highlight(0)
    self._refresh_panel_policy_controls()
    self._refresh_assist_warmup_panel()
    if hasattr(self, "_refresh_lazy_loader_tree"):
        self._refresh_lazy_loader_tree()
    if hasattr(self, "_refresh_lazy_modality_table"):
        self._refresh_lazy_modality_table()
    if hasattr(self, "advanced_open_explain_btn"):
        self.advanced_open_explain_btn.clicked.connect(
            lambda: self._set_panel_visibility("review_queue", True)
        )
    if hasattr(self, "advanced_open_training_btn"):
        self.advanced_open_training_btn.clicked.connect(
            lambda: self.open_preferences(section="training_controls")
        )
    if hasattr(self, "advanced_train_now_btn"):
        self.advanced_train_now_btn.clicked.connect(self._train_suggestion_ranker_now)
    if hasattr(self, "advanced_open_calib_btn"):
        self.advanced_open_calib_btn.clicked.connect(self._show_calibration_visualizer)
    if hasattr(self, "metadata_widget"):
        self.metadata_widget.load_full_requested.connect(self._load_full_metadata)
    if not disable_qc:
        self.controller.annotations_changed.connect(
            lambda: self._schedule_qc_validation(self.controller.session_state.active_primary_id)
        )
    if disable_qc:
        dock_qc = getattr(self, "dock_qc_issues", None)
        if dock_qc is not None:
            dock_qc.setVisible(False)
            dock_qc.toggleViewAction().setEnabled(False)
            dock_qc.toggleViewAction().setVisible(False)
    if disable_diagnostics:
        dock_logs = getattr(self, "dock_logs", None)
        if dock_logs is not None:
            dock_logs.setVisible(False)
            dock_logs.toggleViewAction().setEnabled(False)
            dock_logs.toggleViewAction().setVisible(False)
    self._rebuild_figure_layout()
    self._apply_default_layout()
    self._restore_layout()
    self._apply_default_preferences()
    QtCore.QTimer.singleShot(0, self._sync_channel_panel_for_active_image)
    QtCore.QTimer.singleShot(0, self._maybe_show_first_run_welcome)
