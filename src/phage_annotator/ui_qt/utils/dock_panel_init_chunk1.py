"""Dock panel initialization: init_panels, get_panel_spec, get_dock."""

from __future__ import annotations

import logging
from typing import Optional

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.panels.registry import PanelSpec
from phage_annotator.ui_qt.utils.dock_panel_create import create_dock, wire_dock_action, apply_panel_defaults
from phage_annotator.ui_qt.utils.dock_panel_registry_impl import (
    set_panel_auto_open_enabled,
    set_panel_pinned,
    refresh_panel_policy_actions,
    _init_panel_auto_policy_state,
)
from phage_annotator.ui_qt.utils.dock_panel_manager_impl import build_panel_registry
from phage_annotator.ui_qt.utils.panel_helpers import _merge_system_docks

logger = logging.getLogger(__name__)

def init_panels(self, dock_menu: QtWidgets.QMenu) -> None:
    """Create dock widgets and corresponding View menu actions."""
    from phage_annotator.ui_qt.utils.dock_panel_init_chunk2 import _apply_panel_constraints
    self.panel_specs = build_panel_registry(self)
    self.panel_docks.clear()
    self.dock_actions.clear()
    self.panel_open_actions = {}
    self.panel_policy_quick_auto_actions = {}
    self.panel_policy_quick_pin_actions = {}
    self.panel_policy_quick_open_actions = {}
    self.panel_specs_by_id = {spec.id: spec for spec in self.panel_specs}
    _init_panel_auto_policy_state(self)
    grouped_menus = {
        "inspect": dock_menu.addMenu("Inspect (Right)"),
        "tools": dock_menu.addMenu("Tools (Left)"),
        "plots": dock_menu.addMenu("Plots & Diagnostics (Bottom)"),
    }
    advanced_panels_menu = dock_menu.addMenu("Advanced Panels…")

    for spec in self.panel_specs:
        widget = spec.widget_factory()
        dock = create_dock(self, spec.id, spec.title, widget)
        _apply_panel_constraints(self, dock, spec)
        if spec.id == "sidebar":
            dock.setMinimumWidth(48)
        self.panel_docks[spec.id] = dock
        self.addDockWidget(spec.default_area, dock)
        parent_menu = grouped_menus.get(str(spec.bucket), dock_menu)
        action = parent_menu.addAction(spec.toggle_action_text)
        advanced_panels_menu.addAction(action)
        action.setCheckable(True)
        action.setChecked(spec.default_visible)
        if spec.shortcut:
            action.setShortcut(spec.shortcut)
        self.dock_actions[spec.id] = action
        open_action = QtWidgets.QAction(f"Open Panel: {spec.title}", self)
        open_action.setObjectName(f"open_panel_{spec.id}")
        open_action.triggered.connect(
            lambda _checked=False, panel_id=spec.id: self.open_panel(panel_id, reason="command_palette")
        )
        self.panel_open_actions[spec.id] = open_action
        # Some checkboxes are created by panel factories, so guard lookup here.
        checkbox = None
        if spec.id == "hist":
            checkbox = getattr(self, "hist_chk", None)
        elif spec.id == "profile":
            checkbox = getattr(self, "profile_chk", None)
        wire_dock_action(self, dock, action, checkbox)
        dock.setVisible(spec.default_visible)

    quick_policy_menu = dock_menu.addMenu("Quick Policy")
    for spec in self.panel_specs:
        panel_id = str(spec.id)
        panel_menu = quick_policy_menu.addMenu(str(spec.title))
        open_act = panel_menu.addAction("Open")
        open_act.setObjectName(f"panel_policy_open_{panel_id}")
        open_act.triggered.connect(
            lambda _checked=False, pid=panel_id: self.open_panel(pid, reason="panel_switcher")
        )
        auto_act = panel_menu.addAction("Auto-open")
        auto_act.setObjectName(f"panel_policy_auto_{panel_id}")
        auto_act.setCheckable(True)
        auto_act.toggled.connect(
            lambda checked, pid=panel_id: set_panel_auto_open_enabled(self, pid, bool(checked))
        )
        pin_act = panel_menu.addAction("Pinned")
        pin_act.setObjectName(f"panel_policy_pin_{panel_id}")
        pin_act.setCheckable(True)
        pin_act.toggled.connect(
            lambda checked, pid=panel_id: set_panel_pinned(self, pid, bool(checked))
        )
        self.panel_policy_quick_open_actions[panel_id] = open_act
        self.panel_policy_quick_auto_actions[panel_id] = auto_act
        self.panel_policy_quick_pin_actions[panel_id] = pin_act
    refresh_panel_policy_actions(self)

    self.dock_sidebar = self.panel_docks.get("sidebar")
    self.dock_annotations = self.panel_docks.get("annotations")
    self.dock_review_queue = self.panel_docks.get("review_queue")
    self.dock_advanced_settings = self.panel_docks.get("advanced_settings")
    self.dock_advanced_analysis = self.panel_docks.get("advanced_analysis")
    self.dock_roi = self.panel_docks.get("roi")
    self.dock_roi_manager = self.panel_docks.get("roi_manager")
    self.dock_results = self.panel_docks.get("results")
    self.dock_hist = self.panel_docks.get("hist")
    self.dock_profile = self.panel_docks.get("profile")
    self.dock_orthoview = self.panel_docks.get("orthoview")
    self.dock_smlm = self.panel_docks.get("smlm")
    self.dock_threshold = self.panel_docks.get("threshold")
    self.dock_particles = self.panel_docks.get("particles")
    self.dock_logs = self.panel_docks.get("logs")
    self.dock_recorder = self.panel_docks.get("recorder")
    self.dock_metadata = self.panel_docks.get("metadata")
    self.dock_density = self.panel_docks.get("density")
    self.dock_channels = self.panel_docks.get("channels")
    self.dock_performance = self.panel_docks.get("performance")
    self.dock_qc_issues = self.panel_docks.get("qc_issues")
    self.dock_system = None

    _merge_system_docks(self)

    if self.dock_hist and self.dock_profile:
        self.tabifyDockWidget(self.dock_hist, self.dock_profile)
    # Right inspect docks are not tabified; they should behave as standalone panels.
    if self.dock_roi and self.dock_roi_manager:
        self.tabifyDockWidget(self.dock_roi, self.dock_roi_manager)
    if self.dock_roi and self.dock_results:
        self.tabifyDockWidget(self.dock_roi, self.dock_results)
    if self.dock_roi and self.dock_orthoview:
        self.tabifyDockWidget(self.dock_roi, self.dock_orthoview)
    if self.dock_roi and self.dock_metadata:
        self.tabifyDockWidget(self.dock_roi, self.dock_metadata)
    if self.dock_smlm is not None:
        self.dock_smlm.setFloating(False)
        self.set_panel_visible("smlm", False, source="panel_init")
    if self.dock_orthoview is not None:
        self.dock_orthoview.setFloating(False)
        self.set_panel_visible("orthoview", False, source="panel_init")
    if self.dock_metadata is not None:
        self.dock_metadata.visibilityChanged.connect(self._on_metadata_dock_visibility)

    # Action wiring is intentionally centralized in ui_setup.py to avoid
    # duplicate signal connections and double-trigger behavior.
    apply_panel_defaults(self)
    self._restore_sidebar_mode()

def get_panel_spec(self, panel_id: str) -> Optional[PanelSpec]:
    """Return panel spec by id."""
    specs = getattr(self, "panel_specs_by_id", {})
    if isinstance(specs, dict):
        return specs.get(str(panel_id))
    for spec in getattr(self, "panel_specs", []) or []:
        if spec.id == str(panel_id):
            return spec
    return None

def get_dock(self, panel_id: str) -> Optional[QtWidgets.QDockWidget]:
    """Return the dock widget for a panel id."""
    panel_docks = getattr(self, "panel_docks", {})
    if isinstance(panel_docks, dict):
        dock = panel_docks.get(str(panel_id))
        if dock is not None:
            return dock
    return getattr(self, f"dock_{str(panel_id)}", None)
