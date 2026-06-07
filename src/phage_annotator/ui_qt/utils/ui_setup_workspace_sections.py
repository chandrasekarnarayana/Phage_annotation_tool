"""Workspace and quick-menu setup helpers for the main window."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.utils.ui_setup_canvas import (
    build_annotation_table_panel,
    build_canvas_workspace,
)
from phage_annotator.ui_qt.utils.ui_setup_workspace import build_modality_loader_section


def build_workspace_sections(self: object) -> tuple[QtWidgets.QWidget, QtWidgets.QWidget]:
    """Build explore, annotation, canvas, playback, and quick-menu widgets."""
    # Explore pane: lazy loading and modality/view management.
    self.explore_panel = QtWidgets.QWidget()
    self.explore_panel.setStyleSheet(
        "QWidget { border: 1px solid #d8d8d8; border-radius: 3px; background: #fafafa; }"
    )
    explore_layout = QtWidgets.QVBoxLayout(self.explore_panel)
    explore_layout.setContentsMargins(8, 8, 8, 8)
    explore_layout.setSpacing(8)
    build_modality_loader_section(self, explore_layout)

    build_annotation_table_panel(self)
    fig_container, playback_bar = build_canvas_workspace(self)

    self.playback_mode_combo = QtWidgets.QComboBox()
    self.playback_mode_combo.addItems(["Synchronized", "Independent", "Sequential"])
    self.playback_target_combo = QtWidgets.QComboBox()
    self.playback_target_combo.addItem("Active")
    self.playback_target_btn = QtWidgets.QPushButton("Play Target")
    # Keep advanced playback routing controls available for programmatic use,
    # but do not crowd the default bottom control strip.
    self.playback_mode_combo.setVisible(False)
    self.playback_target_combo.setVisible(False)
    self.playback_target_btn.setVisible(False)
    self.quick_panels_btn = QtWidgets.QToolButton()
    self.quick_panels_btn.setText("Panels")
    self.quick_panels_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
    self.quick_panels_menu = QtWidgets.QMenu(self.quick_panels_btn)
    self.quick_hist_act = self.quick_panels_menu.addAction("Histogram")
    self.quick_hist_act.setCheckable(True)
    self.quick_profile_act = self.quick_panels_menu.addAction("Profile")
    self.quick_profile_act.setCheckable(True)
    self.quick_qc_act = self.quick_panels_menu.addAction("QC Issues")
    self.quick_qc_act.setCheckable(True)
    self.quick_panels_btn.setMenu(self.quick_panels_menu)
    self.quick_layout_btn = QtWidgets.QToolButton()
    self.quick_layout_btn.setText("Layouts")
    self.quick_layout_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
    self.quick_layout_menu = QtWidgets.QMenu(self.quick_layout_btn)
    self.quick_layout_menu.addAction("Default", lambda: self.apply_preset("Default"))
    self.quick_layout_menu.addAction("Annotate", lambda: self.apply_preset("Annotate"))
    self.quick_layout_menu.addAction("Analyze", lambda: self.apply_preset("Analyze"))
    self.quick_layout_menu.addAction("Assist Expert", lambda: self.apply_preset("Assist Expert"))
    self.quick_layout_menu.addAction("Minimal", lambda: self.apply_preset("Minimal"))
    self.quick_layout_btn.setMenu(self.quick_layout_menu)
    self.quick_panels_btn.setToolTip("Quick panel toggles")
    self.quick_layout_btn.setToolTip("Quick layout presets")
    # Keep panel/layout quick menus available from menu bar and command palette.
    self.quick_panels_btn.setVisible(False)
    self.quick_layout_btn.setVisible(False)

    return fig_container, playback_bar
