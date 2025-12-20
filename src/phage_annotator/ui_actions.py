"""Menu/action creation helpers for the main window."""

from __future__ import annotations

from typing import Dict, Tuple

from matplotlib.backends.qt_compat import QtWidgets


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
    
    self.toggle_logs_act = view_menu.addAction("Toggle Logs")
    self.toggle_logs_act.setCheckable(True)
    self.toggle_logs_act.setChecked(True)
    
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
        ("composite", "Show Composite"),
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
    self.undo_act.setShortcut("Ctrl+Z")
    self.redo_act.setShortcut("Ctrl+Shift+Z")
    self.undo_act.setEnabled(False)
    self.redo_act.setEnabled(False)
    self.copy_display_act = edit_menu.addAction("Copy Display Settings…")
    self.reset_confirms_act = edit_menu.addAction("Reset confirmations")
    self.measure_act = edit_menu.addAction("Measure (Results)")
    self.measure_act.setShortcut("Ctrl+M")

    tools_menu = menubar.addMenu("&Tools")
    self.clear_roi_act = tools_menu.addAction("Clear ROI")
    # P5.2: Multi-image ROI management
    self.copy_roi_to_all_act = tools_menu.addAction("Copy ROI to all images")
    self.save_roi_template_act = tools_menu.addAction("Save ROI as template")
    self.apply_roi_template_act = tools_menu.addAction("Apply ROI template…")
    tools_menu.addSeparator()
    self.clear_hist_cache_act = tools_menu.addAction("Clear histogram cache")
    reload_ann_act = tools_menu.addAction("Reload annotations for current image")

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
    shortcuts_act.setShortcut("F1")
    self.command_palette_act = QtWidgets.QAction("Command Palette", self)
    self.command_palette_act.setShortcut("Ctrl+Shift+P")
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
    }
    return actions, dock_panels_menu
