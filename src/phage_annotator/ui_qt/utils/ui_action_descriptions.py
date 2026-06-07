"""Status-tip and help metadata for main-window actions."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets


def describe_action(action: QtWidgets.QAction, status_tip: str, *, whats_this: str | None = None) -> None:
    """Apply tooltip, status-tip, and optional WhatsThis text to an action."""
    # Store base text as properties so dynamic status helpers can restore it.
    tip = str(status_tip or "").strip()
    action.setStatusTip(tip)
    action.setToolTip(tip)
    action.setProperty("baseStatusTip", tip)
    action.setProperty("baseToolTip", tip)
    if whats_this:
        action.setWhatsThis(str(whats_this).strip())


def describe_main_window_actions(self: object, shortcuts_act: QtWidgets.QAction) -> None:
    """Attach descriptive metadata to the standard main-window actions."""
    describe_action(
        self.open_files_act,
        "Open one or more image files into the current session",
        whats_this="Use this first when starting manual work on a small set of images.",
    )
    describe_action(
        self.open_folder_act,
        "Load all supported images from a folder",
        whats_this="Use this when your experiment is organized as a folder of related microscopy images.",
    )
    describe_action(self.load_ann_current_act, "Load annotations linked to the current image or context")
    describe_action(self.save_proj_act, "Save the current workspace, views, and linked resources")
    describe_action(self.load_proj_act, "Load a saved project workspace")
    describe_action(
        self.prefs_act,
        "Open preferences and advanced panel behavior settings",
        whats_this="Preferences contains startup defaults, caching, panel behavior, and advanced workflow settings.",
    )
    describe_action(self.undo_act, "Undo the last annotation or view command")
    describe_action(self.redo_act, "Redo the last undone command")
    describe_action(self.jump_to_frame_act, "Jump directly to a time frame")
    describe_action(self.jump_to_z_act, "Jump directly to a Z slice")
    describe_action(self.measure_act, "Measure the current annotations and send results to the results panel")
    describe_action(self.clear_roi_act, "Clear the current ROI selection")
    describe_action(self.suggest_points_act, "Generate suggestions for the current slice")
    describe_action(self.suggest_points_image_act, "Generate suggestions across all slices in the current image")
    describe_action(self.accept_visible_suggestions_act, "Accept currently visible suggestions")
    describe_action(self.reject_visible_suggestions_act, "Reject currently visible suggestions")
    describe_action(self.qc_validate_act, "Run quality-control validation for loaded annotations")
    describe_action(self.review_context_pack_act, "Toggle the Assist review context pack (table, assist queue, and QC)")
    describe_action(self.save_csv_act, "Write the active annotation context to CSV")
    describe_action(self.save_json_act, "Write the active annotation context to JSON")
    describe_action(self.export_view_act, "Export the current rendered view with overlays")
    describe_action(
        self.advanced_panels_act,
        "Open the full dock and panel manager",
        whats_this="Use the panel manager if you cannot find a dock or want to re-open a hidden analysis panel.",
    )
    describe_action(self.open_panel_policy_act, "Choose which panels auto-open and remain pinned")
    describe_action(self.toggle_left_act, "Show or hide the left workflow sidebar")
    describe_action(self.toggle_settings_act, "Show or hide the Advanced Settings panel on the right sidebar")
    describe_action(self.link_zoom_act, "Link zoom and pan across synchronized image panels")
    describe_action(self.reset_view_act, "Reset the canvas view to the default zoom and pan")
    describe_action(self.toggle_logs_act, "Show or hide the diagnostics dock")
    describe_action(
        self.command_palette_act,
        "Open the command palette for actions and panels",
        whats_this="The command palette is the fastest way to discover actions, panels, and commands by name.",
    )
    describe_action(
        shortcuts_act,
        "Show the keyboard shortcuts reference",
        whats_this="Open a reference table of the current keyboard shortcuts used in the application.",
    )
    describe_action(
        self.context_help_act,
        "Show contextual help for the current workflow area",
        whats_this="Use contextual help when you want a quick explanation of the current panel or workflow without leaving the app.",
    )
    describe_action(self.layout_preset_annotate_act, "Switch to the annotation-focused layout")
    describe_action(self.layout_preset_analyze_act, "Switch to the analysis-focused layout")
    describe_action(self.layout_preset_assist_expert_act, "Switch to the assist and review layout")
