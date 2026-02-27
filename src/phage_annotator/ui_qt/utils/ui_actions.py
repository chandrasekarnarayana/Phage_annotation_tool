"""Menu/action creation helpers for the main window."""

from __future__ import annotations

from typing import Dict, Tuple

from matplotlib.backends.qt_compat import QtWidgets
from phage_annotator.ui_qt.keyboard_registry import apply_menu_shortcuts


def build_menus(self) -> Tuple[Dict[str, QtWidgets.QAction], QtWidgets.QMenu]:
    """Build menus, actions, and shortcuts for the main window."""
    menubar = self.menuBar()
    file_menu = menubar.addMenu("&File")
    open_files_act = file_menu.addAction("Open files…")
    open_folder_act = file_menu.addAction("Open folder…")
    load_ann_current_act = file_menu.addAction("Load annotations for current image…")
    load_ann_multi_act = file_menu.addAction("Load annotations for multiple files…")
    load_ann_all_act = file_menu.addAction("Load all annotations now")
    save_csv_act = file_menu.addAction("Save annotations (CSV)")
    save_json_act = file_menu.addAction("Save annotations (JSON)")
    export_standard_act = file_menu.addAction("Export Standard Bundle…")
    export_view_act = file_menu.addAction("Export View…")
    save_proj_act = file_menu.addAction("Save project…")
    load_proj_act = file_menu.addAction("Load project…")
    self.recent_menu = file_menu.addMenu("Open Recent")
    self.recent_clear_act = self.recent_menu.addAction("Clear Recent")
    prefs_act = file_menu.addAction("Preferences…")
    file_menu.addSeparator()
    exit_act = file_menu.addAction("Exit")

    view_menu = menubar.addMenu("&View")
    dock_panels_menu = view_menu.addMenu("Dock Panels")
    
    # ARCHITECTURAL FIX: Create missing toggle actions that are referenced in gui_ui_setup.py
    # These were being connected but never created, causing AttributeError on GUI launch.
    # Phase 2D: These should be part of an explicit ViewActions dataclass.
    self.toggle_profile_act = view_menu.addAction("Toggle Line Profile")
    self.toggle_profile_act.setCheckable(True)
    self.toggle_profile_act.setChecked(True)
    
    self.toggle_hist_act = view_menu.addAction("Toggle Histogram")
    self.toggle_hist_act.setCheckable(True)
    self.toggle_hist_act.setChecked(True)
    
    self.toggle_left_act = view_menu.addAction("Toggle Left Pane")
    self.toggle_left_act.setCheckable(True)
    self.toggle_left_act.setChecked(True)
    
    self.toggle_settings_act = view_menu.addAction("Toggle Settings")
    self.toggle_settings_act.setCheckable(True)
    self.toggle_settings_act.setChecked(True)
    
    
    self.overlay_act = view_menu.addAction("Overlay")
    self.overlay_act.setCheckable(True)
    self.overlay_act.setChecked(True)
    
    self.toggle_overlay_act = view_menu.addAction("Toggle Overlay (All)")
    self.toggle_overlay_act.setCheckable(True)
    self.toggle_overlay_act.setChecked(True)
    
    self.save_layout_act = view_menu.addAction("Save Layout")
    
    self.layout_preset_annotate_act = view_menu.addAction("Layout: Annotate")
    self.layout_preset_analyze_act = view_menu.addAction("Layout: Analyze")
    self.layout_preset_minimal_act = view_menu.addAction("Layout: Minimal")
    self.layout_preset_default_act = view_menu.addAction("Layout: Default")
    
    view_menu.addSeparator()
    
    overlays_menu = view_menu.addMenu("SMLM Overlays")
    self.show_smlm_points_act = overlays_menu.addAction("Localization Points")
    self.show_smlm_points_act.setCheckable(True)
    self.show_smlm_points_act.setChecked(True)
    self.show_smlm_sr_act = overlays_menu.addAction("SR Image Overlay")
    self.show_smlm_sr_act.setCheckable(True)
    self.show_smlm_sr_act.setChecked(True)
    self.view_overlay_act = view_menu.addAction("Toggle Overlay")
    self.view_overlay_act.setCheckable(True)
    self.view_overlay_act.setChecked(True)
    self.show_roi_handles_act = view_menu.addAction("Show ROI Handles")
    self.show_roi_handles_act.setCheckable(True)
    self.show_roi_handles_act.setChecked(True)
    self.show_recorder_act = view_menu.addAction("Show Recorder")
    self.show_recorder_act.setCheckable(True)
    self.show_recorder_act.setChecked(False)
    view_menu.addSeparator()
    presets_menu = view_menu.addMenu("Layout Presets")
    self.preset_annotate_act = presets_menu.addAction("Annotate")
    self.preset_analyze_act = presets_menu.addAction("Analyze")
    self.preset_minimal_act = presets_menu.addAction("Minimal")
    self.preset_default_act = presets_menu.addAction("Default")
    self.save_layout_default_act = view_menu.addAction("Save Layout as Default")
    self.reset_layout_act = view_menu.addAction("Reset Layout")
    self.link_zoom_act = view_menu.addAction("Link zoom")
    self.link_zoom_act.setCheckable(True)
    self.link_zoom_act.setChecked(True)
    panels_menu = view_menu.addMenu("Image Panels")
    self.panel_actions = {}
    for key, label in [
        ("frame", "Show Frame"),
        ("mean", "Show Mean"),
        ("support", "Show Support"),
        ("std", "Show STD"),
    ]:
        act = panels_menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(True)
        act.toggled.connect(lambda checked, k=key: self._on_panel_toggle(k, checked))
        self.panel_actions[key] = act

    edit_menu = menubar.addMenu("&Edit")
    self.undo_act = edit_menu.addAction("Undo")
    self.redo_act = edit_menu.addAction("Redo")
    self.undo_act.setEnabled(False)
    self.redo_act.setEnabled(False)
    edit_menu.addSeparator()
    self.jump_to_frame_act = edit_menu.addAction("Jump to Frame...")
    self.jump_to_z_act = edit_menu.addAction("Jump to Z Slice...")
    self.copy_display_act = edit_menu.addAction("Copy Display Settings…")
    self.reset_confirms_act = edit_menu.addAction("Reset confirmations")
    self.measure_act = edit_menu.addAction("Measure (Results)")

    tools_menu = menubar.addMenu("&Tools")
    self.clear_roi_act = tools_menu.addAction("Clear ROI")
    # P5.2: Multi-image ROI management
    self.copy_roi_to_all_act = tools_menu.addAction("Copy ROI to all images")
    self.save_roi_template_act = tools_menu.addAction("Save ROI as template")
    self.apply_roi_template_act = tools_menu.addAction("Apply ROI template…")
    tools_menu.addSeparator()
    self.clear_hist_cache_act = tools_menu.addAction("Clear histogram cache")
    reload_ann_act = tools_menu.addAction("Reload annotations for current image")
    tools_menu.addSeparator()
    assisted_menu = tools_menu.addMenu("Assisted Annotation")
    self.suggest_points_act = assisted_menu.addAction("Suggest Points")
    self.suggest_points_image_act = assisted_menu.addAction("Suggest Points (All Slices)")
    self.select_suggestion_strategy_act = assisted_menu.addAction("Suggest Points Using…")
    self.load_suggestion_rule_config_act = assisted_menu.addAction("Load Suggestion Rule Config…")
    self.set_suggestion_score_threshold_act = assisted_menu.addAction(
        "Show Suggestions With Confidence (p_accept) >= …"
    )
    self.accept_visible_suggestions_act = assisted_menu.addAction("Accept Visible Suggestions")
    self.accept_suggestions_in_roi_act = assisted_menu.addAction("Accept Suggestions In ROI")
    self.reject_visible_suggestions_act = assisted_menu.addAction("Reject Visible Suggestions")
    self.clear_suggestions_act = assisted_menu.addAction("Clear Suggestions")
    self.show_suggestion_patch_act = assisted_menu.addAction("Show Suggestion Snap View")
    self.toggle_suggestions_overlay_act = assisted_menu.addAction("Show Suggestion Overlay")
    assisted_menu.addSeparator()
    self.start_timed_session_assisted_act = assisted_menu.addAction("Start Timed Session (With Assist)")
    self.start_timed_session_manual_act = assisted_menu.addAction("Start Timed Session (Without Assist)")
    self.stop_timed_session_act = assisted_menu.addAction("Stop Timed Session")
    self.assist_warmup_act = assisted_menu.addAction("Assist Warmup (Balanced A/R)")
    self.toggle_suggestions_overlay_act.setCheckable(True)
    self.toggle_suggestions_overlay_act.setChecked(True)
    tools_menu.addSeparator()
    review_menu = tools_menu.addMenu("Review Workflow")
    self.set_current_user_act = review_menu.addAction("Set Current User…")
    self.mark_selected_in_review_act = review_menu.addAction("Mark Selected: In Review")
    self.mark_selected_approved_act = review_menu.addAction("Mark Selected: Approved")
    self.mark_selected_needs_changes_act = review_menu.addAction("Mark Selected: Needs Changes")
    self.assign_selected_act = review_menu.addAction("Assign Selected…")
    self.show_reviewer_analytics_act = review_menu.addAction("Show Reviewer Analytics…")
    review_menu.addSeparator()
    self.queue_all_act = review_menu.addAction("Queue: All")
    self.queue_all_act.setCheckable(True)
    self.queue_my_act = review_menu.addAction("Queue: My Queue")
    self.queue_my_act.setCheckable(True)
    self.queue_needs_review_act = review_menu.addAction("Queue: Needs Review")
    self.queue_needs_review_act.setCheckable(True)
    self.queue_blocked_qc_act = review_menu.addAction("Queue: Blocked By QC")
    self.queue_blocked_qc_act.setCheckable(True)
    self.queue_all_act.setChecked(True)

    analyze_menu = menubar.addMenu("&Analyze")
    self.show_profiles_act = analyze_menu.addAction("Line profiles (raw vs corrected)")
    self.show_bleach_act = analyze_menu.addAction("ROI mean + bleaching fit")
    self.show_table_act = analyze_menu.addAction("ROI mean table (per file)")
    self.threshold_act = analyze_menu.addAction("Threshold…")
    self.analyze_particles_act = analyze_menu.addAction("Analyze Particles…")
    smlm_menu = analyze_menu.addMenu("SMLM")
    self.smlm_act = smlm_menu.addAction("ThunderSTORM (ROI)")
    self.deepstorm_act = smlm_menu.addAction("Deep-STORM (ROI)")
    self.rerun_smlm_act = smlm_menu.addAction("Re-run Last SMLM on ROI")

    help_menu = menubar.addMenu("&Help")
    about_act = help_menu.addAction("About")
    shortcuts_act = help_menu.addAction("Keyboard Shortcuts…")
    self.shortcuts_act = shortcuts_act
    help_menu.addSeparator()
    diagnostics_menu = help_menu.addMenu("Diagnostics")
    self.toggle_logs_act = diagnostics_menu.addAction("Toggle Diagnostics Dock")
    self.toggle_logs_act.setCheckable(True)
    self.toggle_logs_act.setChecked(False)
    self.command_palette_act = QtWidgets.QAction("Command Palette", self)
    self.command_palette_act.triggered.connect(self._show_command_palette)
    self.addAction(self.command_palette_act)
    self.reset_view_act = QtWidgets.QAction("Reset View", self)
    self.reset_view_act.triggered.connect(self.reset_all_view)
    self.addAction(self.reset_view_act)
    self._dev_demo_job_act = QtWidgets.QAction("Dev: Demo Job", self)
    self._dev_demo_job_act.triggered.connect(self._run_demo_job)
    self.addAction(self._dev_demo_job_act)

    actions = {
        "open_files": open_files_act,
        "open_folder": open_folder_act,
        "load_ann_current": load_ann_current_act,
        "load_ann_multi": load_ann_multi_act,
        "load_ann_all": load_ann_all_act,
        "reload_ann": reload_ann_act,
        "save_csv": save_csv_act,
        "save_json": save_json_act,
        "export_standard": export_standard_act,
        "export_view": export_view_act,
        "save_proj": save_proj_act,
        "load_proj": load_proj_act,
        "prefs": prefs_act,
        "exit": exit_act,
        "about": about_act,
        "shortcuts": shortcuts_act,
        "copy_display": self.copy_display_act,
        "reset_confirms": self.reset_confirms_act,
        "measure": self.measure_act,
        "show_recorder": self.show_recorder_act,
        "clear_hist_cache": self.clear_hist_cache_act,
        "suggest_points": self.suggest_points_act,
        "suggest_points_image": self.suggest_points_image_act,
        "select_suggestion_strategy": self.select_suggestion_strategy_act,
        "load_suggestion_rule_config": self.load_suggestion_rule_config_act,
        "set_suggestion_score_threshold": self.set_suggestion_score_threshold_act,
        "accept_visible_suggestions": self.accept_visible_suggestions_act,
        "accept_suggestions_in_roi": self.accept_suggestions_in_roi_act,
        "reject_visible_suggestions": self.reject_visible_suggestions_act,
        "clear_suggestions": self.clear_suggestions_act,
        "show_suggestion_patch": self.show_suggestion_patch_act,
        "start_timed_session_assisted": self.start_timed_session_assisted_act,
        "start_timed_session_manual": self.start_timed_session_manual_act,
        "stop_timed_session": self.stop_timed_session_act,
        "assist_warmup": self.assist_warmup_act,
        "toggle_suggestions_overlay": self.toggle_suggestions_overlay_act,
        "set_current_user": self.set_current_user_act,
        "mark_selected_in_review": self.mark_selected_in_review_act,
        "mark_selected_approved": self.mark_selected_approved_act,
        "mark_selected_needs_changes": self.mark_selected_needs_changes_act,
        "assign_selected": self.assign_selected_act,
        "show_reviewer_analytics": self.show_reviewer_analytics_act,
        "queue_all": self.queue_all_act,
        "queue_my": self.queue_my_act,
        "queue_needs_review": self.queue_needs_review_act,
        "queue_blocked_qc": self.queue_blocked_qc_act,
        "jump_to_frame": self.jump_to_frame_act,
        "jump_to_z": self.jump_to_z_act,
    }
    apply_menu_shortcuts(self)
    return actions, dock_panels_menu
