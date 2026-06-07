"""Menu and action signal connection helpers for UI setup."""

from __future__ import annotations


def connect_main_window_actions(self: object, actions: dict[str, object], *, disable_shortcuts: bool, disable_qc: bool) -> None:
    """Connect menu actions and status-bar controls to main-window handlers."""
    open_files_act = actions["open_files"]
    open_folder_act = actions["open_folder"]
    load_ann_current_act = actions["load_ann_current"]
    load_ann_multi_act = actions["load_ann_multi"]
    load_ann_all_act = actions["load_ann_all"]
    save_csv_act = actions["save_csv"]
    save_json_act = actions["save_json"]
    export_standard_act = actions["export_standard"]
    export_view_act = actions["export_view"]
    save_proj_act = actions["save_proj"]
    load_proj_act = actions["load_proj"]
    prefs_act = actions["prefs"]
    reset_confirms_act = actions["reset_confirms"]
    reload_ann_act = actions["reload_ann"]
    suggest_points_act = actions["suggest_points"]
    suggest_points_image_act = actions["suggest_points_image"]
    select_suggestion_strategy_act = actions["select_suggestion_strategy"]
    load_suggestion_rule_config_act = actions["load_suggestion_rule_config"]
    set_suggestion_score_threshold_act = actions["set_suggestion_score_threshold"]
    accept_visible_suggestions_act = actions["accept_visible_suggestions"]
    accept_green_suggestions_act = actions["accept_green_suggestions"]
    accept_suggestions_in_roi_act = actions["accept_suggestions_in_roi"]
    reject_visible_suggestions_act = actions["reject_visible_suggestions"]
    clear_suggestions_act = actions["clear_suggestions"]
    show_suggestion_patch_act = actions["show_suggestion_patch"]
    start_timed_session_assisted_act = actions["start_timed_session_assisted"]
    start_timed_session_manual_act = actions["start_timed_session_manual"]
    stop_timed_session_act = actions["stop_timed_session"]
    assist_warmup_act = actions["assist_warmup"]
    train_ranker_now_act = actions["train_ranker_now"]
    batch_correct_suggestions_act = actions["batch_correct_suggestions"]
    propagate_suggestions_act = actions["propagate_suggestions"]
    toggle_suggestions_overlay_act = actions["toggle_suggestions_overlay"]
    qc_validate_act = actions["qc_validate"]
    qc_jump_next_act = actions["qc_jump_next"]
    set_current_user_act = actions["set_current_user"]
    mark_selected_in_review_act = actions["mark_selected_in_review"]
    mark_selected_approved_act = actions["mark_selected_approved"]
    mark_selected_needs_changes_act = actions["mark_selected_needs_changes"]
    assign_selected_act = actions["assign_selected"]
    show_reviewer_analytics_act = actions["show_reviewer_analytics"]
    queue_all_act = actions["queue_all"]
    queue_my_act = actions["queue_my"]
    queue_needs_review_act = actions["queue_needs_review"]
    queue_blocked_qc_act = actions["queue_blocked_qc"]
    clear_hist_cache_act = actions.get("clear_hist_cache")
    exit_act = actions["exit"]
    about_act = actions["about"]
    context_help_act = actions["context_help"]
    copy_display_act = actions["copy_display"]
    measure_act = actions["measure"]
    jump_to_frame_act = actions["jump_to_frame"]
    jump_to_z_act = actions["jump_to_z"]
    show_roi_handles_act = self.show_roi_handles_act
    clear_roi_act = self.clear_roi_act
    # Hooks for menus
    open_files_act.triggered.connect(self._open_files)
    open_folder_act.triggered.connect(self._open_folder)
    load_ann_current_act.triggered.connect(self._load_annotations_current)
    load_ann_multi_act.triggered.connect(self._load_annotations_multi)
    load_ann_all_act.triggered.connect(self._load_annotations_all)
    reload_ann_act.triggered.connect(self._reload_annotations_current)
    save_csv_act.triggered.connect(self._save_csv)
    save_json_act.triggered.connect(self._save_json)
    export_standard_act.triggered.connect(self._export_standard_bundle_dialog)
    export_view_act.triggered.connect(self._export_view_dialog)
    save_proj_act.triggered.connect(self._save_project)
    load_proj_act.triggered.connect(self._load_project)
    prefs_act.triggered.connect(self._show_preferences_dialog)
    reset_confirms_act.triggered.connect(self._reset_confirmations)
    about_act.triggered.connect(self._show_about)
    context_help_act.triggered.connect(self._show_contextual_help)
    shortcuts_act = actions.get("shortcuts")
    if shortcuts_act is not None:
        shortcuts_act.triggered.connect(self._show_keyboard_shortcuts)
        if disable_shortcuts:
            shortcuts_act.setEnabled(False)
            shortcuts_act.setVisible(False)
    if disable_shortcuts:
        try:
            self._disable_all_shortcuts()
        except Exception:
            pass
    exit_act.triggered.connect(self.close)
    show_roi_handles_act.toggled.connect(self._toggle_roi_handles)
    clear_roi_act.triggered.connect(self._clear_roi)
    # P5.2: Multi-image ROI management
    if hasattr(self, "copy_roi_to_all_act"):
        self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
    if hasattr(self, "save_roi_template_act"):
        self.save_roi_template_act.triggered.connect(self._save_roi_template)
    if hasattr(self, "apply_roi_template_act"):
        self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
    if clear_hist_cache_act is not None:
        clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)
    suggest_points_act.triggered.connect(self._suggest_points_current_slice)
    suggest_points_image_act.triggered.connect(self._suggest_points_current_image)
    select_suggestion_strategy_act.triggered.connect(self._select_suggestion_strategy_dialog)
    if getattr(self, "status_strategy_combo", None) is not None:
        self._sync_status_strategy_selector()
        self.status_strategy_combo.currentIndexChanged.connect(
            lambda _idx: self._set_suggestion_strategy(
                str(self.status_strategy_combo.currentData() or self.status_strategy_combo.currentText()),
                source="status_bar",
            )
        )
        self.status_strategy_combo.setToolTip(
            "Suggestion strategy:\n"
            "- Source Frame: peaks in unprocessed source signal\n"
            "- Corrected: peaks after correction\n"
            "- Evidence Consensus: strong across modalities\n"
            "- Evidence Contradiction: enforce positive/negative evidence rules"
        )
    if getattr(self, "status_modality_combo", None) is not None:
        self.status_modality_combo.currentIndexChanged.connect(
            lambda idx: self._set_primary_combo(int(idx))
        )
    if getattr(self, "status_assist_mode_btn", None) is not None:
        self.status_assist_mode_btn.toggled.connect(
            lambda checked: self._set_assist_mode(bool(checked), source="status_bar")
        )
        default_assist_mode = bool(self._settings.value("assistModeEnabled", False, type=bool))
        self._set_assist_mode(default_assist_mode, source="startup")
    load_suggestion_rule_config_act.triggered.connect(
        self._load_suggestion_rule_config_dialog
    )
    set_suggestion_score_threshold_act.triggered.connect(
        self._set_suggestion_score_threshold_dialog
    )
    accept_visible_suggestions_act.triggered.connect(self._accept_visible_suggestions)
    accept_green_suggestions_act.triggered.connect(self._accept_high_confidence_suggestions)
    accept_suggestions_in_roi_act.triggered.connect(self._accept_suggestions_in_roi)
    reject_visible_suggestions_act.triggered.connect(self._reject_visible_suggestions)
    clear_suggestions_act.triggered.connect(self._clear_suggestions_current_image)
    show_suggestion_patch_act.triggered.connect(self._show_current_suggestion_patch)
    if getattr(self, "show_all_predictions_act", None) is not None:
        self.show_all_predictions_act.triggered.connect(
            self._show_all_predictions_dialog
        )
    start_timed_session_assisted_act.triggered.connect(
        lambda: self._start_timed_annotation_session(True)
    )
    start_timed_session_manual_act.triggered.connect(
        lambda: self._start_timed_annotation_session(False)
    )
    stop_timed_session_act.triggered.connect(self._stop_timed_annotation_session)
    assist_warmup_act.triggered.connect(self._start_assist_warmup)
    train_ranker_now_act.triggered.connect(self._train_suggestion_ranker_now)
    if getattr(self, "show_calibration_visualizer_act", None) is not None:
        self.show_calibration_visualizer_act.triggered.connect(
            self._show_calibration_visualizer
        )
    batch_correct_suggestions_act.triggered.connect(
        self._batch_correct_suggestions_dialog
    )
    propagate_suggestions_act.triggered.connect(
        self._propagate_suggestions_remaining_dialog
    )
    toggle_suggestions_overlay_act.triggered.connect(self._toggle_suggestions_overlay)
    if not disable_qc:
        qc_validate_act.triggered.connect(self._trigger_qc_validation)
        qc_jump_next_act.triggered.connect(self._jump_to_next_qc_issue)
    set_current_user_act.triggered.connect(self._set_current_user_dialog)
    mark_selected_in_review_act.triggered.connect(
        lambda: self._set_selected_review_state("in_review")
    )
    mark_selected_approved_act.triggered.connect(
        lambda: self._set_selected_review_state("approved")
    )
    mark_selected_needs_changes_act.triggered.connect(
        lambda: self._set_selected_review_state("needs_changes")
    )
    assign_selected_act.triggered.connect(self._assign_selected_annotations_dialog)
    show_reviewer_analytics_act.triggered.connect(self._show_reviewer_analytics_dialog)
    queue_all_act.triggered.connect(lambda: self._set_review_queue_filter("all"))
    queue_my_act.triggered.connect(lambda: self._set_review_queue_filter("my_queue"))
    queue_needs_review_act.triggered.connect(
        lambda: self._set_review_queue_filter("needs_review")
    )
    queue_blocked_qc_act.triggered.connect(
        lambda: self._set_review_queue_filter("blocked_qc")
    )
    self.review_context_pack_act.triggered.connect(self._toggle_review_context_pack)

    self.toggle_profile_act.triggered.connect(self._toggle_profile_panel)
    self.toggle_hist_act.triggered.connect(self._toggle_hist_panel)
    self.toggle_left_act.triggered.connect(self._toggle_left_pane)
    self.toggle_settings_act.triggered.connect(self._toggle_settings_pane)
    self.link_zoom_act.triggered.connect(self._on_link_zoom_menu)
    self.reset_layout_act.triggered.connect(self._reset_layout)
    self.save_layout_act.triggered.connect(self._save_layout_default)
    self.toggle_overlay_act.triggered.connect(self._toggle_overlay)
    self.layout_preset_annotate_act.triggered.connect(lambda: self.apply_preset("Annotate"))
    self.layout_preset_analyze_act.triggered.connect(lambda: self.apply_preset("Analyze"))
    self.layout_preset_assist_expert_act.triggered.connect(
        lambda: self.apply_preset("Assist Expert")
    )
    self.layout_preset_minimal_act.triggered.connect(lambda: self.apply_preset("Minimal"))
    self.layout_preset_default_act.triggered.connect(lambda: self.apply_preset("Default"))
    if getattr(self, "advanced_panels_act", None) is not None:
        self.advanced_panels_act.triggered.connect(self._show_command_palette)
    if getattr(self, "undo_layout_change_act", None) is not None:
        self.undo_layout_change_act.triggered.connect(self._undo_layout_change)
    if getattr(self, "open_panel_policy_act", None) is not None:
        self.open_panel_policy_act.triggered.connect(
            lambda: self.open_preferences(section="panel_policy")
        )
    self.focus_canvas_mode_act.triggered.connect(
        lambda _checked=False: self._toggle_focus_canvas_mode()
    )
    self.command_palette_act.triggered.connect(self._show_command_palette)
    if getattr(self, "open_logs_help_act", None) is not None:
        self.open_logs_help_act.triggered.connect(
            lambda _checked=False: self.open_panel("logs", reason="menu:help")
        )
    if getattr(self, "open_performance_help_act", None) is not None:
        self.open_performance_help_act.triggered.connect(
            lambda _checked=False: self.open_panel("performance", reason="menu:help")
        )
    if getattr(self, "open_recorder_help_act", None) is not None:
        self.open_recorder_help_act.triggered.connect(
            lambda _checked=False: self.open_panel("recorder", reason="menu:help")
        )
    if not DISABLE_DIAGNOSTICS:
        self.toggle_logs_act.triggered.connect(
            lambda checked: self.set_panel_visible("logs", bool(checked), source="menu:layout")
        )
    self.toggle_overlay_act.setChecked(True)
    self.reset_view_act.triggered.connect(self.reset_all_view)
    self.show_profiles_act.triggered.connect(self._show_profile_dialog)
    self.show_bleach_act.triggered.connect(self._show_bleach_dialog)
    self.show_table_act.triggered.connect(self._show_table_dialog)
    if hasattr(self, "threshold_act"):
        self.threshold_act.triggered.connect(self._show_threshold_panel)
    if hasattr(self, "analyze_particles_act"):
        self.analyze_particles_act.triggered.connect(self._show_analyze_particles_panel)
    if hasattr(self, "smlm_act"):
        self.smlm_act.triggered.connect(self._show_smlm_panel)
    if hasattr(self, "deepstorm_act"):
        self.deepstorm_act.triggered.connect(self._show_deepstorm_panel)
    if hasattr(self, "rerun_smlm_act"):
        self.rerun_smlm_act.triggered.connect(self._rerun_last_smlm)
    if hasattr(self, "show_smlm_points_act"):
        self.show_smlm_points_act.triggered.connect(self._toggle_smlm_points)
    if hasattr(self, "show_smlm_sr_act"):
        self.show_smlm_sr_act.triggered.connect(self._toggle_smlm_sr)
    self.undo_act.triggered.connect(self.undo_last_action)
    self.redo_act.triggered.connect(self.redo_last_action)
    jump_to_frame_act.triggered.connect(self._jump_to_frame_dialog)
    jump_to_z_act.triggered.connect(self._jump_to_z_dialog)
    copy_display_act.triggered.connect(self._copy_display_settings)
    measure_act.triggered.connect(self._results_measure_current)
    self.show_recorder_act.triggered.connect(self._toggle_recorder)
    self.scalebar_chk.toggled.connect(self._on_scalebar_change)
    self.scalebar_length_spin.valueChanged.connect(self._on_scalebar_change)
    self.scalebar_thickness_spin.valueChanged.connect(self._on_scalebar_change)
    self.scalebar_location_combo.currentTextChanged.connect(self._on_scalebar_change)
    self.scalebar_text_chk.toggled.connect(self._on_scalebar_change)
    self.scalebar_background_chk.toggled.connect(self._on_scalebar_change)
    self.scalebar_export_chk.toggled.connect(self._on_scalebar_change)
    self.suggestion_auto_retrain_chk.toggled.connect(
        self._on_suggestion_auto_retrain_changed
    )
    self.suggestion_min_labels_spin.valueChanged.connect(
        self._on_suggestion_min_labels_changed
    )
    self.suggestion_train_now_btn.clicked.connect(self._train_suggestion_ranker_now)
    self.annotation_space_combo.currentTextChanged.connect(self._on_annotation_space_changed)
    self.generation_space_combo.currentTextChanged.connect(self._on_generation_space_changed)
    self.disable_bulk_accept_when_stale_chk.toggled.connect(
        self._on_disable_bulk_accept_when_stale_changed
    )
    self.interactive_learning_experimental_chk.toggled.connect(
        self._on_interactive_learning_experimental_changed
    )
    self.assist_min_total_spin.valueChanged.connect(self._on_assist_minima_changed)
    self.assist_min_positive_spin.valueChanged.connect(self._on_assist_minima_changed)
    self.assist_min_negative_spin.valueChanged.connect(self._on_assist_minima_changed)
    self.assist_min_context_spin.valueChanged.connect(self._on_assist_minima_changed)
    if not disable_qc:
        self.qc_auto_show_chk.toggled.connect(self._on_qc_auto_show_changed)
    else:
        self.qc_auto_show_chk.setChecked(False)
        self.qc_auto_show_chk.setEnabled(False)
    self.assist_warmup_next_btn.clicked.connect(self._next_uncertain_suggestion)
    self.assist_warmup_refresh_btn.clicked.connect(self._refresh_assist_warmup_panel)
