"""Menu/action creation helpers for the main window."""

from __future__ import annotations

from typing import Dict, Tuple

from matplotlib.backends.qt_compat import QtWidgets
from phage_annotator.ui_qt.keyboard_registry import apply_menu_shortcuts


def build_menus(self) -> Tuple[Dict[str, QtWidgets.QAction], QtWidgets.QMenu]:
    """Build menus, actions, and shortcuts for the main window."""
    def _describe(action: QtWidgets.QAction, status_tip: str, *, whats_this: str | None = None) -> None:
        tip = str(status_tip or "").strip()
        action.setStatusTip(tip)
        action.setToolTip(tip)
        action.setProperty("baseStatusTip", tip)
        action.setProperty("baseToolTip", tip)
        if whats_this:
            action.setWhatsThis(str(whats_this).strip())

    menubar = self.menuBar()
    file_menu = menubar.addMenu("&File")
    import_menu = file_menu.addMenu("Import")
    self.open_files_act = import_menu.addAction("Open files…")
    self.open_folder_act = import_menu.addAction("Open folder…")
    annotations_menu = file_menu.addMenu("Annotations")
    self.load_ann_current_act = annotations_menu.addAction("Load annotations for current image…")
    self.load_ann_multi_act = annotations_menu.addAction("Load annotations for multiple files…")
    self.load_ann_all_act = annotations_menu.addAction("Load all annotations now")
    project_menu = file_menu.addMenu("Project")
    self.save_proj_act = project_menu.addAction("Save project…")
    self.load_proj_act = project_menu.addAction("Load project…")
    self.recent_menu = file_menu.addMenu("Open Recent")
    self.recent_clear_act = self.recent_menu.addAction("Clear Recent")
    file_menu.addSeparator()
    self.prefs_act = file_menu.addAction("Preferences…")
    file_menu.addSeparator()
    exit_act = file_menu.addAction("Exit")

    annotate_menu = menubar.addMenu("&Annotate")
    self.undo_act = annotate_menu.addAction("Undo")
    self.redo_act = annotate_menu.addAction("Redo")
    self.undo_act.setEnabled(False)
    self.redo_act.setEnabled(False)
    annotate_menu.addSeparator()
    navigate_menu = annotate_menu.addMenu("Navigate")
    self.jump_to_frame_act = navigate_menu.addAction("Jump to Frame...")
    self.jump_to_z_act = navigate_menu.addAction("Jump to Z Slice...")
    self.copy_display_act = annotate_menu.addAction("Copy Display Settings…")
    self.measure_act = annotate_menu.addAction("Measure (Results)")
    reload_ann_act = annotate_menu.addAction("Reload annotations for current image")
    annotate_menu.addSeparator()
    roi_menu = annotate_menu.addMenu("ROI")
    self.clear_roi_act = roi_menu.addAction("Clear ROI")
    self.copy_roi_to_all_act = roi_menu.addAction("Copy ROI to all images")
    self.save_roi_template_act = roi_menu.addAction("Save ROI as template")
    self.apply_roi_template_act = roi_menu.addAction("Apply ROI template…")

    assist_menu = menubar.addMenu("&Assist")
    self.suggest_points_act = assist_menu.addAction("Suggest Points")
    self.suggest_points_image_act = assist_menu.addAction("Suggest Points (All Slices)")
    self.select_suggestion_strategy_act = assist_menu.addAction("Select Strategy")
    self.load_suggestion_rule_config_act = assist_menu.addAction("Load Rule Config…")
    self.set_suggestion_score_threshold_act = assist_menu.addAction("Set Threshold")
    assist_menu.addSeparator()
    self.accept_visible_suggestions_act = assist_menu.addAction("Accept Visible")
    self.accept_green_suggestions_act = assist_menu.addAction("Accept All Green")
    self.accept_suggestions_in_roi_act = assist_menu.addAction("Accept In ROI")
    self.reject_visible_suggestions_act = assist_menu.addAction("Reject Visible")
    self.clear_suggestions_act = assist_menu.addAction("Clear Suggestions")
    self.show_suggestion_patch_act = assist_menu.addAction("Show Snap View")
    self.show_all_predictions_act = assist_menu.addAction("Show All Predictions")
    self.toggle_suggestions_overlay_act = assist_menu.addAction("Show Suggestion Overlay")
    self.toggle_suggestions_overlay_act.setCheckable(True)
    self.toggle_suggestions_overlay_act.setChecked(True)
    assist_menu.addSeparator()
    self.start_timed_session_assisted_act = assist_menu.addAction("Start Timed Session (With Assist)")
    self.start_timed_session_manual_act = assist_menu.addAction("Start Timed Session (Without Assist)")
    self.stop_timed_session_act = assist_menu.addAction("Stop Timed Session")
    self.assist_warmup_act = assist_menu.addAction("Warmup (Balanced A/R)")
    self.train_ranker_now_act = assist_menu.addAction("Train Ranker Now")
    self.show_calibration_visualizer_act = assist_menu.addAction("Show Calibration Visualizer")
    self.batch_correct_suggestions_act = assist_menu.addAction("Batch Correct Offset...")
    self.propagate_suggestions_act = assist_menu.addAction(
        "Propagate Suggestions to Remaining T/Z..."
    )

    review_menu = menubar.addMenu("&Review")
    self.set_current_user_act = review_menu.addAction("Set Current User…")
    self.mark_selected_in_review_act = review_menu.addAction("Mark Selected: In Review")
    self.mark_selected_approved_act = review_menu.addAction("Mark Selected: Approved")
    self.mark_selected_needs_changes_act = review_menu.addAction("Mark Selected: Needs Changes")
    self.assign_selected_act = review_menu.addAction("Assign Selected…")
    self.show_reviewer_analytics_act = review_menu.addAction("Show Reviewer Analytics…")
    review_menu.addSeparator()
    queue_menu = review_menu.addMenu("Queue Filter")
    self.queue_all_act = queue_menu.addAction("All")
    self.queue_all_act.setCheckable(True)
    self.queue_my_act = queue_menu.addAction("My Queue")
    self.queue_my_act.setCheckable(True)
    self.queue_needs_review_act = queue_menu.addAction("Needs Review")
    self.queue_needs_review_act.setCheckable(True)
    self.queue_blocked_qc_act = queue_menu.addAction("Blocked By QC")
    self.queue_blocked_qc_act.setCheckable(True)
    self.queue_all_act.setChecked(True)
    review_menu.addSeparator()
    self.qc_validate_act = review_menu.addAction("Validate QC")
    self.qc_jump_next_act = review_menu.addAction("Jump to Next QC Issue")
    self.review_context_pack_act = review_menu.addAction("Toggle Assist Context Pack")

    export_menu = menubar.addMenu("&Export")
    annotation_export_menu = export_menu.addMenu("Annotations")
    self.save_csv_act = annotation_export_menu.addAction("Save annotations (CSV)")
    self.save_json_act = annotation_export_menu.addAction("Save annotations (JSON)")
    export_standard_act = annotation_export_menu.addAction("Standard Formats")
    export_menu.addSeparator()
    self.export_view_act = export_menu.addAction("Export View…")

    view_menu = menubar.addMenu("&View")
    dock_panels_menu = view_menu.addMenu("Panels")
    self.advanced_panels_act = view_menu.addAction("Advanced Panels…")
    self.open_panel_policy_act = view_menu.addAction("Panel Auto-Open & Pinning…")
    self.toggle_profile_act = view_menu.addAction("Toggle Line Profile")
    self.toggle_profile_act.setCheckable(True)
    self.toggle_profile_act.setChecked(True)
    self.toggle_hist_act = view_menu.addAction("Toggle Histogram")
    self.toggle_hist_act.setCheckable(True)
    self.toggle_hist_act.setChecked(True)
    self.toggle_left_act = view_menu.addAction("Toggle Left Sidebar")
    self.toggle_left_act.setCheckable(True)
    self.toggle_left_act.setChecked(True)
    self.toggle_settings_act = view_menu.addAction("Toggle Advanced Settings")
    self.toggle_settings_act.setCheckable(True)
    self.toggle_settings_act.setChecked(False)
    self.toggle_overlay_act = view_menu.addAction("Show Overlay")
    self.toggle_overlay_act.setCheckable(True)
    self.toggle_overlay_act.setChecked(True)
    self.overlay_act = self.toggle_overlay_act
    self.view_overlay_act = self.toggle_overlay_act
    layouts_menu = view_menu.addMenu("Layouts")
    self.save_layout_act = layouts_menu.addAction("Save Current Layout As…")
    self.undo_layout_change_act = layouts_menu.addAction("Undo Layout Change")
    self.undo_layout_change_act.setEnabled(False)
    layouts_menu.addSeparator()
    self.layout_preset_default_act = layouts_menu.addAction("Reset to Default")
    self.layout_preset_annotate_act = layouts_menu.addAction("Preset: Annotate")
    self.layout_preset_analyze_act = layouts_menu.addAction("Preset: Analyze")
    self.layout_preset_assist_expert_act = layouts_menu.addAction("Preset: Assist Expert")
    self.layout_preset_minimal_act = layouts_menu.addAction("Preset: Minimal")
    self.focus_canvas_mode_act = view_menu.addAction("Focus Canvas Mode")
    self.focus_canvas_mode_act.setCheckable(True)
    self.focus_canvas_mode_act.setChecked(False)
    self.focus_canvas_mode_act.setShortcut("F")
    self.save_layout_default_act = view_menu.addAction("Save Layout as Default")
    self.reset_layout_act = view_menu.addAction("Reset Layout")
    self.link_zoom_act = view_menu.addAction("Link Zoom/Pan")
    self.link_zoom_act.setCheckable(True)
    self.link_zoom_act.setChecked(True)
    panels_menu = view_menu.addMenu("Image Panels")
    self.panel_actions = {}
    for key, label in [
        ("frame", "Show Frame"),
        ("mean", "Show Mean"),
        ("support", "Show Modality 2"),
        ("std", "Show STD"),
    ]:
        act = panels_menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(True)
        act.toggled.connect(lambda checked, k=key: self._on_panel_toggle(k, checked))
        self.panel_actions[key] = act
    overlays_menu = view_menu.addMenu("SMLM Overlays")
    self.show_smlm_points_act = overlays_menu.addAction("Localization Points")
    self.show_smlm_points_act.setCheckable(True)
    self.show_smlm_points_act.setChecked(True)
    self.show_smlm_sr_act = overlays_menu.addAction("SR Image Overlay")
    self.show_smlm_sr_act.setCheckable(True)
    self.show_smlm_sr_act.setChecked(True)
    self.show_roi_handles_act = view_menu.addAction("Show ROI Handles")
    self.show_roi_handles_act.setCheckable(True)
    self.show_roi_handles_act.setChecked(True)
    self.show_recorder_act = view_menu.addAction("Show Recorder")
    self.show_recorder_act.setCheckable(True)
    self.show_recorder_act.setChecked(False)
    advanced_menu = menubar.addMenu("&Advanced")
    self.reset_confirms_act = advanced_menu.addAction("Reset confirmations")
    self.clear_hist_cache_act = advanced_menu.addAction("Clear histogram cache")
    advanced_menu.addSeparator()
    self.show_profiles_act = advanced_menu.addAction("Line profiles (raw vs corrected)")
    self.show_bleach_act = advanced_menu.addAction("ROI mean + bleaching fit")
    self.show_table_act = advanced_menu.addAction("ROI mean table (per file)")
    self.threshold_act = advanced_menu.addAction("Threshold…")
    self.analyze_particles_act = advanced_menu.addAction("Analyze Particles…")
    smlm_menu = advanced_menu.addMenu("SMLM")
    self.smlm_act = smlm_menu.addAction("ThunderSTORM (ROI)")
    self.deepstorm_act = smlm_menu.addAction("Deep-STORM (ROI)")
    self.rerun_smlm_act = smlm_menu.addAction("Re-run Last SMLM on ROI")

    help_menu = menubar.addMenu("&Help")
    about_act = help_menu.addAction("About")
    shortcuts_act = help_menu.addAction("Keyboard Shortcuts…")
    self.context_help_act = help_menu.addAction("Contextual Help")
    self.context_help_act.setShortcut("Shift+F1")
    self.shortcuts_act = shortcuts_act
    help_menu.addSeparator()
    diagnostics_menu = help_menu.addMenu("Diagnostics")
    self.toggle_logs_act = diagnostics_menu.addAction("Toggle Diagnostics Dock")
    self.toggle_logs_act.setCheckable(True)
    self.toggle_logs_act.setChecked(False)
    self.command_palette_act = QtWidgets.QAction("Command Palette", self)
    self.addAction(self.command_palette_act)
    help_menu.addAction(self.command_palette_act)
    self.reset_view_act = QtWidgets.QAction("Reset View", self)
    self.addAction(self.reset_view_act)
    self._dev_demo_job_act = QtWidgets.QAction("Dev: Demo Job", self)
    self._dev_demo_job_act.triggered.connect(self._run_demo_job)
    self.addAction(self._dev_demo_job_act)

    actions = {
        "open_files": self.open_files_act,
        "open_folder": self.open_folder_act,
        "load_ann_current": self.load_ann_current_act,
        "load_ann_multi": self.load_ann_multi_act,
        "load_ann_all": self.load_ann_all_act,
        "reload_ann": reload_ann_act,
        "save_csv": self.save_csv_act,
        "save_json": self.save_json_act,
        "export_standard": export_standard_act,
        "export_view": self.export_view_act,
        "save_proj": self.save_proj_act,
        "load_proj": self.load_proj_act,
        "prefs": self.prefs_act,
        "exit": exit_act,
        "about": about_act,
        "shortcuts": shortcuts_act,
        "copy_display": self.copy_display_act,
        "reset_confirms": self.reset_confirms_act,
        "measure": self.measure_act,
        "focus_canvas_mode": self.focus_canvas_mode_act,
        "advanced_panels": self.advanced_panels_act,
        "open_panel_policy": self.open_panel_policy_act,
        "undo_layout_change": self.undo_layout_change_act,
        "show_recorder": self.show_recorder_act,
        "clear_hist_cache": self.clear_hist_cache_act,
        "suggest_points": self.suggest_points_act,
        "suggest_points_image": self.suggest_points_image_act,
        "select_suggestion_strategy": self.select_suggestion_strategy_act,
        "load_suggestion_rule_config": self.load_suggestion_rule_config_act,
        "set_suggestion_score_threshold": self.set_suggestion_score_threshold_act,
        "accept_visible_suggestions": self.accept_visible_suggestions_act,
        "accept_green_suggestions": self.accept_green_suggestions_act,
        "accept_suggestions_in_roi": self.accept_suggestions_in_roi_act,
        "reject_visible_suggestions": self.reject_visible_suggestions_act,
        "clear_suggestions": self.clear_suggestions_act,
        "show_suggestion_patch": self.show_suggestion_patch_act,
        "show_all_predictions": self.show_all_predictions_act,
        "start_timed_session_assisted": self.start_timed_session_assisted_act,
        "start_timed_session_manual": self.start_timed_session_manual_act,
        "stop_timed_session": self.stop_timed_session_act,
        "assist_warmup": self.assist_warmup_act,
        "train_ranker_now": self.train_ranker_now_act,
        "show_calibration_visualizer": self.show_calibration_visualizer_act,
        "batch_correct_suggestions": self.batch_correct_suggestions_act,
        "propagate_suggestions": self.propagate_suggestions_act,
        "toggle_suggestions_overlay": self.toggle_suggestions_overlay_act,
        "qc_validate": self.qc_validate_act,
        "qc_jump_next": self.qc_jump_next_act,
        "review_context_pack": self.review_context_pack_act,
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
        "context_help": self.context_help_act,
        "reset_view": self.reset_view_act,
    }
    _describe(
        self.open_files_act,
        "Open one or more image files into the current session",
        whats_this="Use this first when starting manual work on a small set of images.",
    )
    _describe(
        self.open_folder_act,
        "Load all supported images from a folder",
        whats_this="Use this when your experiment is organized as a folder of related microscopy images.",
    )
    _describe(self.load_ann_current_act, "Load annotations linked to the current image or context")
    _describe(self.save_proj_act, "Save the current workspace, views, and linked resources")
    _describe(self.load_proj_act, "Load a saved project workspace")
    _describe(
        self.prefs_act,
        "Open preferences and advanced panel behavior settings",
        whats_this="Preferences contains startup defaults, caching, panel behavior, and advanced workflow settings.",
    )
    _describe(self.undo_act, "Undo the last annotation or view command")
    _describe(self.redo_act, "Redo the last undone command")
    _describe(self.jump_to_frame_act, "Jump directly to a time frame")
    _describe(self.jump_to_z_act, "Jump directly to a Z slice")
    _describe(self.measure_act, "Measure the current annotations and send results to the results panel")
    _describe(self.clear_roi_act, "Clear the current ROI selection")
    _describe(self.suggest_points_act, "Generate suggestions for the current slice")
    _describe(self.suggest_points_image_act, "Generate suggestions across all slices in the current image")
    _describe(self.accept_visible_suggestions_act, "Accept currently visible suggestions")
    _describe(self.reject_visible_suggestions_act, "Reject currently visible suggestions")
    _describe(self.qc_validate_act, "Run quality-control validation for loaded annotations")
    _describe(self.review_context_pack_act, "Toggle the Assist review context pack (table, assist queue, and QC)")
    _describe(self.save_csv_act, "Write the active annotation context to CSV")
    _describe(self.save_json_act, "Write the active annotation context to JSON")
    _describe(self.export_view_act, "Export the current rendered view with overlays")
    _describe(
        self.advanced_panels_act,
        "Open the full dock and panel manager",
        whats_this="Use the panel manager if you cannot find a dock or want to re-open a hidden analysis panel.",
    )
    _describe(self.open_panel_policy_act, "Choose which panels auto-open and remain pinned")
    _describe(self.toggle_left_act, "Show or hide the left workflow sidebar")
    _describe(self.toggle_settings_act, "Show or hide the Advanced Settings panel on the right sidebar")
    _describe(self.link_zoom_act, "Link zoom and pan across synchronized image panels")
    _describe(self.reset_view_act, "Reset the canvas view to the default zoom and pan")
    _describe(self.toggle_logs_act, "Show or hide the diagnostics dock")
    _describe(
        self.command_palette_act,
        "Open the command palette for actions and panels",
        whats_this="The command palette is the fastest way to discover actions, panels, and commands by name.",
    )
    _describe(
        shortcuts_act,
        "Show the keyboard shortcuts reference",
        whats_this="Open a reference table of the current keyboard shortcuts used in the application.",
    )
    _describe(
        self.context_help_act,
        "Show contextual help for the current workflow area",
        whats_this="Use contextual help when you want a quick explanation of the current panel or workflow without leaving the app.",
    )
    _describe(self.layout_preset_annotate_act, "Switch to the annotation-focused layout")
    _describe(self.layout_preset_analyze_act, "Switch to the analysis-focused layout")
    _describe(self.layout_preset_assist_expert_act, "Switch to the assist and review layout")

    apply_menu_shortcuts(self)
    return actions, dock_panels_menu
