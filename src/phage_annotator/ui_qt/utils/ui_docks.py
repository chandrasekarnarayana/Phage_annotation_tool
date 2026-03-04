"""Dock/panel wiring helpers for the main window."""

from __future__ import annotations

import pathlib
from typing import List, Optional

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets
from matplotlib.figure import Figure

from phage_annotator.roi.widgets import RoiManagerWidget
from phage_annotator.ui_qt.panels.particles import AnalyzeParticlesPanel
from phage_annotator.ui_qt.panels.channel_controls import ChannelControlPanel
from phage_annotator.ui_qt.panels.density import DensityPanel
from phage_annotator.ui_qt.panels.modality_layers_panel import ModalityLayersPanel
from phage_annotator.ui_qt.panels.qc_issues_panel import QCIssuesPanel
from phage_annotator.ui_qt.panels.review_queue_panel import ReviewQueuePanel
from phage_annotator.ui_qt.panels.project_relink_panel import ProjectRelinkPanel
from phage_annotator.ui_qt.panels.status_details_panel import StatusDetailsPanel
from phage_annotator.ui_qt.panels.suggestion_explain_panel import SuggestionExplainPanel
from phage_annotator.ui_qt.panels.recorder_legacy import RecorderWidget
from phage_annotator.ui_qt.panels.registry_legacy import PanelConstraints, PanelSpec
from phage_annotator.ui_qt.panels.threshold import ThresholdPanel
from phage_annotator.ui_qt.docks.metadata_dock import MetadataDock
from phage_annotator.ui_qt.widgets.table_legacy import ResultsTableWidget
from phage_annotator.ui_qt.widgets.orthoview import OrthoViewWidget
from phage_annotator.ui_qt.widgets.slider_panel_double import SliderPanelDouble
from phage_annotator.ui_qt.panels.smlm import SmlmPanel


PANEL_TAB_GROUPS = {
    # Right inspect panels are intentionally NOT tabified; they are shown as
    # distinct panels via right-sidebar selection.
    "tools_roi": ("roi", "roi_manager", "results", "orthoview", "metadata"),
    "plots_hist": ("hist", "profile"),
    "system": ("logs", "performance", "recorder"),
}
# so placement recipes are defined in one declarative source of truth.


def _panel_auto_open_key(panel_id: str) -> str:
    return f"ui/panels/{str(panel_id)}/autoOpenEnabled"


def _panel_pinned_key(panel_id: str) -> str:
    return f"ui/panels/{str(panel_id)}/pinned"


def _panel_auto_open_trigger_key(panel_id: str, trigger: str) -> str:
    return f"ui/panels/{str(panel_id)}/autoOpenEnabled/{str(trigger)}"


def _is_auto_reason(reason: str) -> bool:
    text = str(reason or "").strip().lower()
    return "auto" in text


def _auto_trigger_from_reason(reason: str) -> str:
    text = str(reason or "").strip().lower()
    if not text:
        return "default"
    if ":" in text:
        tail = text.split(":", 1)[1].strip()
        if tail:
            return tail
    if "_" in text:
        tail = text.split("_", 1)[1].strip()
        if tail:
            return tail
    return "default"


def _is_user_intent_reason(reason: str) -> bool:
    text = str(reason or "").strip().lower()
    if text in {"user", "command_palette", "panel_switcher"}:
        return True
    return text.startswith(("menu:", "quick_button:"))


def _show_status_message(self, text: str, timeout_ms: int = 3500) -> None:
    try:
        bar = self.statusBar()
    except Exception:
        bar = None
    if bar is not None:
        bar.showMessage(str(text), int(timeout_ms))


def _hide_auto_open_toast(self) -> None:
    frame = getattr(self, "_auto_open_toast_frame", None)
    if frame is not None:
        try:
            frame.hide()
        except Exception:
            pass
        try:
            frame.deleteLater()
        except Exception:
            pass
    self._auto_open_toast_frame = None
    timer = getattr(self, "_auto_open_toast_timer", None)
    if timer is not None:
        try:
            timer.stop()
        except Exception:
            pass
        try:
            timer.deleteLater()
        except Exception:
            pass
    self._auto_open_toast_timer = None


def _show_auto_open_toast(self, panel_id: str, panel_title: str, *, timeout_ms: int = 7000) -> None:
    """Show interactive toast for auto-open events with Pin/Disable actions."""
    if bool(
        getattr(self, "_settings", None).value("statusBarMinimalMode", True, type=bool)
        if getattr(self, "_settings", None) is not None
        else True
    ):
        return
    if not bool(getattr(self, "_settings", None).value("panelAutoOpenToastsEnabled", False, type=bool) if getattr(self, "_settings", None) is not None else False):
        return
    _hide_auto_open_toast(self)
    bar = None
    try:
        bar = self.statusBar()
    except Exception:
        bar = None
    if bar is None:
        return

    frame = QtWidgets.QFrame(self)
    frame.setObjectName("auto_open_toast")
    frame.setStyleSheet(
        "#auto_open_toast {"
        "background:#263238; color:#eceff1; border:1px solid #455a64; border-radius:4px;}"
        "#auto_open_toast QToolButton { padding:2px 6px; }"
    )
    row = QtWidgets.QHBoxLayout(frame)
    row.setContentsMargins(8, 3, 8, 3)
    row.setSpacing(6)
    msg = QtWidgets.QLabel(f"Opened {panel_title} (auto).")
    msg.setStyleSheet("color:#eceff1;")
    pin_btn = QtWidgets.QToolButton(frame)
    pin_btn.setText("Pin")
    disable_btn = QtWidgets.QToolButton(frame)
    disable_btn.setText("Disable auto-open")
    close_btn = QtWidgets.QToolButton(frame)
    close_btn.setText("×")
    close_btn.setAutoRaise(True)

    row.addWidget(msg)
    row.addWidget(pin_btn)
    row.addWidget(disable_btn)
    row.addWidget(close_btn)
    bar.addPermanentWidget(frame)
    self._auto_open_toast_frame = frame

    def _close_toast() -> None:
        try:
            frame.hide()
        except Exception:
            pass
        try:
            frame.deleteLater()
        except Exception:
            pass
        if getattr(self, "_auto_open_toast_frame", None) is frame:
            self._auto_open_toast_frame = None
        self._auto_open_toast_timer = None

    def _on_pin() -> None:
        set_panel_pinned(self, str(panel_id), True)
        _show_status_message(self, f"Pinned {panel_title}.")
        _close_toast()

    def _on_disable() -> None:
        set_panel_auto_open_enabled(self, str(panel_id), False)
        _show_status_message(self, f"Auto-open disabled for {panel_title}.")
        _close_toast()

    pin_btn.clicked.connect(_on_pin)
    disable_btn.clicked.connect(_on_disable)
    close_btn.clicked.connect(_close_toast)
    # Keep interactive toast stable under test teardown; close on explicit user action
    # or when a new auto-open toast replaces it.
    self._auto_open_toast_timer = None


def _merge_system_docks(self) -> None:
    """Merge logs/performance/recorder into a single tabbed System dock."""
    dock_logs = getattr(self, "dock_logs", None)
    dock_perf = getattr(self, "dock_performance", None)
    dock_rec = getattr(self, "dock_recorder", None)
    if dock_logs is None or dock_perf is None or dock_rec is None:
        return
    if getattr(self, "dock_system", None) is not None:
        return

    logs_w = dock_logs.widget()
    perf_w = dock_perf.widget()
    rec_w = dock_rec.widget()
    if logs_w is None or perf_w is None or rec_w is None:
        return

    tabs = QtWidgets.QTabWidget(self)
    tabs.setObjectName("system_tabs")
    tabs.addTab(logs_w, "Logs / Diagnostics")
    tabs.addTab(perf_w, "Performance")
    tabs.addTab(rec_w, "Recorder")

    container = QtWidgets.QWidget(self)
    layout = QtWidgets.QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(tabs)
    self.system_tabs = tabs

    system_dock = create_dock(self, "system", "System", container)
    self.addDockWidget(QtCore.Qt.RightDockWidgetArea, system_dock)
    system_dock.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)
    system_dock.setFloating(False)
    try:
        features = system_dock.features()
        system_dock.setFeatures(features & ~QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)
    except Exception:
        pass
    self.dock_system = system_dock

    # Remove old standalone docks and remap panel ids to unified dock.
    for old in (dock_logs, dock_perf, dock_rec):
        try:
            self.removeDockWidget(old)
        except Exception:
            pass
        try:
            old.hide()
        except Exception:
            pass
    self.panel_docks["logs"] = system_dock
    self.panel_docks["performance"] = system_dock
    self.panel_docks["recorder"] = system_dock
    self.panel_docks["system"] = system_dock
    self.dock_logs = system_dock
    self.dock_performance = system_dock
    self.dock_recorder = system_dock


def _select_system_tab_for_panel(self, panel_id: str) -> None:
    """Select the appropriate tab inside merged System dock for a panel id."""
    tabs = getattr(self, "system_tabs", None)
    if tabs is None:
        return
    panel_id = str(panel_id)
    target_idx = {"logs": 0, "performance": 1, "recorder": 2}.get(panel_id)
    if target_idx is None:
        return
    if 0 <= int(target_idx) < int(tabs.count()):
        tabs.setCurrentIndex(int(target_idx))


def _iter_unique_dock_specs(self):
    """Yield first spec for each unique dock object in current panel mapping."""
    seen = set()
    for spec in getattr(self, "panel_specs", []) or []:
        dock = getattr(self, "panel_docks", {}).get(spec.id)
        if dock is None:
            continue
        key = id(dock)
        if key in seen:
            continue
        seen.add(key)
        yield spec, dock


def _find_tab_for_dock(self, dock: QtWidgets.QDockWidget) -> tuple[Optional[QtWidgets.QTabBar], int]:
    """Find QTabBar/index entry corresponding to a dock title."""
    title = str(dock.windowTitle() or "")
    for bar in self.findChildren(QtWidgets.QTabBar):
        try:
            for idx in range(bar.count()):
                if str(bar.tabText(idx) or "") == title:
                    return bar, idx
        except Exception:
            continue
    return None, -1


def _init_panel_auto_policy_state(self) -> None:
    settings = getattr(self, "_settings", None)
    self._panel_auto_open_enabled = {}
    self._panel_auto_open_enabled_by_trigger = {}
    self._panel_pinned = {}
    self._panel_opened_by = {}
    self._panel_auto_notice_shown = set()
    for spec in getattr(self, "panel_specs", []) or []:
        panel_id = str(spec.id)
        enabled = True
        pinned = False
        default_auto_open = panel_id not in {"density", "performance", "logs", "qc_issues"}
        if settings is not None:
            try:
                enabled = bool(
                    settings.value(
                        _panel_auto_open_key(panel_id),
                        default_auto_open,
                        type=bool,
                    )
                )
            except Exception:
                enabled = default_auto_open
        else:
            enabled = default_auto_open
            try:
                pinned = bool(settings.value(_panel_pinned_key(panel_id), False, type=bool))
            except Exception:
                pinned = False
        self._panel_auto_open_enabled[panel_id] = enabled
        self._panel_pinned[panel_id] = pinned


def refresh_panel_policy_actions(self) -> None:
    """Synchronize menu quick-policy action check states from policy state."""
    auto_actions = dict(getattr(self, "panel_policy_quick_auto_actions", {}) or {})
    pin_actions = dict(getattr(self, "panel_policy_quick_pin_actions", {}) or {})
    for panel_id, action in auto_actions.items():
        if action is None:
            continue
        desired = bool(is_panel_auto_open_enabled(self, panel_id))
        if action.isChecked() != desired:
            action.blockSignals(True)
            action.setChecked(desired)
            action.blockSignals(False)
    for panel_id, action in pin_actions.items():
        if action is None:
            continue
        desired = bool(is_panel_pinned(self, panel_id))
        if action.isChecked() != desired:
            action.blockSignals(True)
            action.setChecked(desired)
            action.blockSignals(False)


def is_panel_auto_open_enabled(self, panel_id: str) -> bool:
    state = getattr(self, "_panel_auto_open_enabled", {}) or {}
    return bool(state.get(str(panel_id), True))


def is_panel_auto_open_enabled_for_trigger(self, panel_id: str, trigger: str) -> bool:
    trigger_state = getattr(self, "_panel_auto_open_enabled_by_trigger", {}) or {}
    panel_id = str(panel_id)
    trigger = str(trigger or "default")
    panel_map = trigger_state.get(panel_id)
    if not isinstance(panel_map, dict):
        panel_map = {}
        self._panel_auto_open_enabled_by_trigger[panel_id] = panel_map
    if trigger not in panel_map:
        settings = getattr(self, "_settings", None)
        enabled = True
        if settings is not None:
            try:
                enabled = bool(
                    settings.value(
                        _panel_auto_open_trigger_key(panel_id, trigger),
                        True,
                        type=bool,
                    )
                )
            except Exception:
                enabled = True
        panel_map[trigger] = enabled
    return bool(panel_map.get(trigger, True))


def set_panel_auto_open_enabled(self, panel_id: str, enabled: bool) -> None:
    key = str(panel_id)
    if not hasattr(self, "_panel_auto_open_enabled") or not isinstance(
        getattr(self, "_panel_auto_open_enabled", None), dict
    ):
        self._panel_auto_open_enabled = {}
    self._panel_auto_open_enabled[key] = bool(enabled)
    settings = getattr(self, "_settings", None)
    if settings is not None:
        try:
            settings.setValue(_panel_auto_open_key(key), bool(enabled))
        except Exception:
            pass
    refresh_panel_policy_actions(self)
    if hasattr(self, "_refresh_panel_policy_controls"):
        try:
            self._refresh_panel_policy_controls()
        except Exception:
            pass


def set_panel_auto_open_enabled_for_trigger(
    self,
    panel_id: str,
    trigger: str,
    enabled: bool,
) -> None:
    panel_key = str(panel_id)
    trigger_key = str(trigger or "default")
    if not isinstance(getattr(self, "_panel_auto_open_enabled_by_trigger", None), dict):
        self._panel_auto_open_enabled_by_trigger = {}
    panel_map = self._panel_auto_open_enabled_by_trigger.get(panel_key)
    if not isinstance(panel_map, dict):
        panel_map = {}
        self._panel_auto_open_enabled_by_trigger[panel_key] = panel_map
    panel_map[trigger_key] = bool(enabled)
    settings = getattr(self, "_settings", None)
    if settings is not None:
        try:
            settings.setValue(
                _panel_auto_open_trigger_key(panel_key, trigger_key),
                bool(enabled),
            )
        except Exception:
            pass


def is_panel_pinned(self, panel_id: str) -> bool:
    state = getattr(self, "_panel_pinned", {}) or {}
    return bool(state.get(str(panel_id), False))


def set_panel_pinned(self, panel_id: str, pinned: bool) -> None:
    key = str(panel_id)
    if not hasattr(self, "_panel_pinned") or not isinstance(
        getattr(self, "_panel_pinned", None), dict
    ):
        self._panel_pinned = {}
    self._panel_pinned[key] = bool(pinned)
    settings = getattr(self, "_settings", None)
    if settings is not None:
        try:
            settings.setValue(_panel_pinned_key(key), bool(pinned))
        except Exception:
            pass
    refresh_panel_policy_actions(self)
    if hasattr(self, "_refresh_panel_policy_controls"):
        try:
            self._refresh_panel_policy_controls()
        except Exception:
            pass


def get_panel_opened_by(self, panel_id: str) -> str:
    state = getattr(self, "_panel_opened_by", {}) or {}
    return str(state.get(str(panel_id), "unknown"))


def init_panels(self, dock_menu: QtWidgets.QMenu) -> None:
    """Create dock widgets and corresponding View menu actions."""
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
            lambda _checked=False, panel_id=spec.id: open_panel(
                self, panel_id, reason="command_palette"
            )
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
            lambda _checked=False, pid=panel_id: open_panel(self, pid, reason="panel_switcher")
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
    self.dock_suggestion_explain = self.panel_docks.get("suggestion_explain")
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
    self.dock_modality_layers = self.panel_docks.get("modality_layers")
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


def _apply_panel_constraints(self, dock: QtWidgets.QDockWidget, spec: PanelSpec) -> None:
    """Apply floatability and allowed-area constraints from PanelSpec."""
    constraints = spec.constraints if isinstance(spec.constraints, PanelConstraints) else PanelConstraints()
    features = QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
    # Exclude close button from sidebar panels (left and right) that have collapse/expand controls
    right_sidebar_panels = {
        "annotations",
        "review_queue",
        "suggestion_explain",
        "advanced_analysis",
        "modality_layers",
        "status_details",
    }
    if spec.id not in {"sidebar"} | right_sidebar_panels:
        features |= QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
    if constraints.floatable:
        features |= QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
    dock.setFeatures(features)
    if constraints.allowed_areas:
        allowed = QtCore.Qt.DockWidgetAreas(0)
        for area in constraints.allowed_areas:
            allowed |= area
        dock.setAllowedAreas(allowed)
    else:
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
    if spec.id in right_sidebar_panels:
        dock.setMinimumWidth(360)
        dock.setStyleSheet(
            "QDockWidget { margin: 0px; padding: 0px; }"
            "QDockWidget::title { padding: 6px 8px; font-weight: 600; }"
        )


def _canonical_area_for_panel(self, spec: PanelSpec) -> QtCore.Qt.DockWidgetArea:
    """Return canonical dock area for the panel."""
    constraints = spec.constraints if isinstance(spec.constraints, PanelConstraints) else PanelConstraints()
    if constraints.allowed_areas:
        return constraints.allowed_areas[0]
    return spec.default_area


def _tabify_group_for_panel(self, panel_id: str) -> None:
    """Ensure panel is tabified into its configured group."""
    spec = get_panel_spec(self, panel_id)
    if spec is None or not spec.tab_group:
        return
    group_ids = PANEL_TAB_GROUPS.get(str(spec.tab_group), ())
    if len(group_ids) < 2:
        return
    anchor = get_dock(self, group_ids[0])
    target = get_dock(self, panel_id)
    if anchor is None or target is None or anchor is target:
        return
    try:
        self.tabifyDockWidget(anchor, target)
    except Exception:
        return


def _flash_dock(self, dock: QtWidgets.QDockWidget) -> None:
    """Flash the dock tab entry with a short animation (fallback to dock border)."""
    if dock is None:
        return
    tabbar, tab_idx = _find_tab_for_dock(self, dock)
    if tabbar is not None and tab_idx >= 0:
        rect = tabbar.tabRect(tab_idx).adjusted(2, 2, -2, -2)
        overlay = QtWidgets.QWidget(tabbar)
        overlay.setObjectName("dock_tab_flash_overlay")
        overlay.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        overlay.setGeometry(rect)
        overlay.setStyleSheet(
            "#dock_tab_flash_overlay {"
            "background: rgba(30, 136, 229, 120); border-radius: 4px; }"
        )
        effect = QtWidgets.QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        overlay.show()
        anim = QtCore.QPropertyAnimation(effect, b"opacity", overlay)
        anim.setDuration(700)
        anim.setStartValue(0.0)
        anim.setKeyValueAt(0.4, 0.95)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutSine)

        def _cleanup() -> None:
            try:
                overlay.hide()
            except Exception:
                pass
            try:
                overlay.deleteLater()
            except Exception:
                pass

        anim.finished.connect(_cleanup)
        if not isinstance(getattr(tabbar, "_flash_anims", None), list):
            tabbar._flash_anims = []
        tabbar._flash_anims.append(anim)
        self._tab_flash_anims = tabbar._flash_anims

        def _remove_anim() -> None:
            anims = getattr(tabbar, "_flash_anims", None)
            if isinstance(anims, list):
                try:
                    anims.remove(anim)
                except ValueError:
                    pass

        anim.finished.connect(_remove_anim)
        anim.start()
        return

    # Fallback for non-tabified docks.
    original = dock.styleSheet()
    dock.setStyleSheet(
        f"{original}\nQDockWidget {{ border: 2px solid #1976d2; background: #e3f2fd; }}"
    )

    def _restore() -> None:
        try:
            dock.setStyleSheet(original)
        except RuntimeError:
            return

    QtCore.QTimer.singleShot(650, _restore)


class PanelManager:
    """Single entrypoint for panel open/place/raise/flash behavior."""

    def __init__(self, window) -> None:
        self.window = window

    def open_panel(self, panel_id: str, *, reason: str = "user") -> Optional[QtWidgets.QDockWidget]:
        spec = get_panel_spec(self.window, panel_id)
        dock = get_dock(self.window, panel_id)
        if spec is None or dock is None:
            return dock
        reason_text = str(reason or "user")
        is_auto = _is_auto_reason(reason_text)
        panel_key = str(panel_id)
        auto_trigger = _auto_trigger_from_reason(reason_text)
        if is_auto and not is_panel_auto_open_enabled(self.window, panel_key):
            _show_status_message(self.window, f"Auto-open skipped for {spec.title} (disabled).")
            return dock
        if is_auto and not is_panel_auto_open_enabled_for_trigger(
            self.window, panel_key, auto_trigger
        ):
            _show_status_message(
                self.window,
                f"Auto-open skipped for {spec.title} ({auto_trigger} disabled).",
            )
            return dock
        _apply_panel_constraints(self.window, dock, spec)
        if spec.constraints.fixed_area:
            try:
                self.window.addDockWidget(_canonical_area_for_panel(self.window, spec), dock)
            except Exception:
                pass
        _tabify_group_for_panel(self.window, panel_id)
        dock.show()
        _select_system_tab_for_panel(self.window, panel_key)
        if not is_auto:
            dock.raise_()
            try:
                dock.activateWindow()
            except Exception:
                pass
        self._focus_panel_widget(dock)
        opened_by = "auto" if is_auto else "user"
        if not isinstance(getattr(self.window, "_panel_opened_by", None), dict):
            self.window._panel_opened_by = {}
        if not isinstance(getattr(self.window, "_panel_opened_reason", None), dict):
            self.window._panel_opened_reason = {}
        self.window._panel_opened_by[panel_key] = opened_by
        self.window._panel_opened_reason[panel_key] = reason_text
        if (not is_auto) and _is_user_intent_reason(reason_text):
            set_panel_pinned(self.window, panel_key, True)
        if is_auto:
            shown = getattr(self.window, "_panel_auto_notice_shown", set())
            if panel_key not in shown:
                _show_auto_open_toast(self.window, panel_key, str(spec.title))
                shown.add(panel_key)
                self.window._panel_auto_notice_shown = shown
        if str(reason) in {"user", "command_palette", "panel_switcher"}:
            _flash_dock(self.window, dock)
        return dock

    @staticmethod
    def _focus_panel_widget(dock: QtWidgets.QDockWidget) -> None:
        try:
            root = dock.widget()
        except Exception:
            root = None
        if root is None:
            return
        try:
            if root.focusPolicy() != QtCore.Qt.FocusPolicy.NoFocus:
                root.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
                return
        except Exception:
            pass
        for child in root.findChildren(QtWidgets.QWidget):
            try:
                if not child.isVisible():
                    continue
                if child.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus:
                    continue
                child.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
                return
            except Exception:
                continue


def _panel_manager(self) -> PanelManager:
    manager = getattr(self, "_panel_manager_obj", None)
    if not isinstance(manager, PanelManager):
        manager = PanelManager(self)
        self._panel_manager_obj = manager
    return manager


def open_panel(self, panel_id: str, *, reason: str = "user") -> Optional[QtWidgets.QDockWidget]:
    """Open panel by id with canonical placement, raise, and flash."""
    return _panel_manager(self).open_panel(panel_id, reason=reason)


def build_panel_registry(self) -> List[PanelSpec]:
    """Return the declarative list of dock panel specs."""
    return [
        PanelSpec(
            id="sidebar",
            title="Sidebar",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=True,
            widget_factory=self._make_sidebar_widget,
            toggle_action_text="Toggle Sidebar",
            bucket="tools",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.LeftDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="annotations",
            title="Annotation Table",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=True,
            widget_factory=self._make_annotations_widget,
            toggle_action_text="Annotation Table",
            bucket="inspect",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="review_queue",
            title="Review Queue",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_review_queue_widget,
            toggle_action_text="Review Queue",
            bucket="inspect",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="suggestion_explain",
            title="Why This Suggestion?",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_suggestion_explain_widget,
            toggle_action_text="Why This Suggestion?",
            bucket="inspect",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="status_details",
            title="Status Details",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_status_details_widget,
            toggle_action_text="Status Details",
            bucket="inspect",
            search_aliases=("status details", "run context", "session status"),
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="project_relink",
            title="Project Relink",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_project_relink_widget,
            toggle_action_text="Project Relink",
            bucket="inspect",
            search_aliases=("relink", "missing images", "project relink"),
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="advanced_analysis",
            title="Advanced Analysis",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_advanced_analysis_widget,
            toggle_action_text="Advanced Analysis",
            bucket="inspect",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="roi",
            title="ROI Controls",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,  # Hidden by default, opened from ROI/Crop panel
            widget_factory=self._make_roi_widget,
            toggle_action_text="ROI Controls",
            bucket="tools",
            tab_group="tools_roi",
        ),
        PanelSpec(
            id="roi_manager",
            title="ROI Manager",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_roi_manager_widget,
            toggle_action_text="ROI Manager",
            bucket="tools",
            tab_group="tools_roi",
        ),
        PanelSpec(
            id="results",
            title="Results",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_results_widget,
            toggle_action_text="Results",
            bucket="plots",
            search_aliases=("results table", "results hub"),
        ),
        PanelSpec(
            id="recorder",
            title="Recorder",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_recorder_widget,
            toggle_action_text="Recorder",
            bucket="plots",
            tab_group="system",
        ),
        PanelSpec(
            id="hist",
            title="Histogram",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,  # Hidden by default per Task G
            widget_factory=self._make_hist_widget,
            toggle_action_text="Histogram",
            bucket="plots",
            tab_group="plots_hist",
        ),
        PanelSpec(
            id="profile",
            title="Line Profile",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,  # Hidden by default per Task G
            widget_factory=self._make_profile_widget,
            toggle_action_text="Line Profile",
            bucket="plots",
            tab_group="plots_hist",
        ),
        PanelSpec(
            id="orthoview",
            title="Ortho Views",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_orthoview_widget,
            toggle_action_text="Ortho Views",
            bucket="tools",
            tab_group="tools_roi",
        ),
        PanelSpec(
            id="smlm",
            title="SMLM (ROI)",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_smlm_widget,
            toggle_action_text="SMLM (ROI)",
            bucket="tools",
        ),
        PanelSpec(
            id="threshold",
            title="Threshold",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_threshold_widget,
            toggle_action_text="Threshold",
            bucket="tools",
        ),
        PanelSpec(
            id="particles",
            title="Analyze Particles",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_particles_widget,
            toggle_action_text="Analyze Particles",
            bucket="tools",
        ),
        PanelSpec(
            id="density",
            title="Density",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_density_widget,
            toggle_action_text="Density",
            bucket="tools",
        ),
        PanelSpec(
            id="modality_layers",
            title="Modality Layers",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_modality_layers_widget,
            toggle_action_text="Modality Layers",
            bucket="inspect",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="channels",
            title="Channels",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_channel_controls_widget,
            toggle_action_text="Channels",
            bucket="tools",
        ),
        PanelSpec(
            id="logs",
            title="Logs / Diagnostics",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_logs_widget,
            toggle_action_text="Logs / Diagnostics",
            bucket="plots",
            tab_group="system",
            search_aliases=("logs", "system logs"),
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="metadata",
            title="Metadata",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_metadata_widget,
            toggle_action_text="Metadata",
            bucket="tools",
            tab_group="tools_roi",
        ),
        PanelSpec(
            id="performance",
            title="Performance",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_performance_widget,
            toggle_action_text="Performance Monitor",
            bucket="plots",
            tab_group="system",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="qc_issues",
            title="QC Issues",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_qc_issues_widget,
            toggle_action_text="QC Issues",
            bucket="plots",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
    ]


def apply_panel_defaults(self) -> None:
    """Reset dock placement/visibility using PanelSpec defaults."""
    for spec, dock in _iter_unique_dock_specs(self):
        _apply_panel_constraints(self, dock, spec)
        self.addDockWidget(spec.default_area, dock)
        dock.setVisible(spec.default_visible)
    for group_id, members in PANEL_TAB_GROUPS.items():
        if len(members) < 2:
            continue
        anchor = self.panel_docks.get(members[0])
        if anchor is None:
            continue
        for member in members[1:]:
            dock = self.panel_docks.get(member)
            if dock is None:
                continue
            try:
                self.tabifyDockWidget(anchor, dock)
            except Exception:
                continue


def create_dock(self, name: str, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QDockWidget:
    """Create a standard dock widget with common features enabled."""
    dock = QtWidgets.QDockWidget(title, self)
    dock.setObjectName(name)
    dock.setWidget(widget)
    dock.setFeatures(
        QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
        | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
    )
    dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
    return dock


def wire_dock_action(
    self,
    dock: QtWidgets.QDockWidget,
    action: QtWidgets.QAction,
    checkbox: Optional[QtWidgets.QCheckBox] = None,
) -> None:
    """Keep dock visibility, menu toggle, and optional checkbox in sync."""

    def _set_visible(checked: bool) -> None:
        setter = getattr(self, "set_panel_visible", None)
        panel_id = str(dock.objectName() or "")
        if callable(setter) and panel_id:
            setter(panel_id, bool(checked), source="menu:panels")
        else:
            dock.setVisible(bool(checked))

    def _sync_action(visible: bool) -> None:
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)
        if checkbox is not None:
            checkbox.blockSignals(True)
            checkbox.setChecked(visible)
            checkbox.blockSignals(False)
            try:
                self._refresh_image()
            except RuntimeError:
                return

    action.toggled.connect(_set_visible)
    dock.visibilityChanged.connect(_sync_action)


def make_sidebar_widget(self) -> QtWidgets.QWidget:
    return self._build_sidebar_stack()


def make_annotations_widget(self) -> QtWidgets.QWidget:
    return self.annotation_table_panel


def make_review_queue_widget(self) -> QtWidgets.QWidget:
    widget = ReviewQueuePanel(parent=self)
    self.review_queue_panel = widget
    return widget


def make_suggestion_explain_widget(self) -> QtWidgets.QWidget:
    widget = SuggestionExplainPanel(parent=self)
    self.suggestion_explain_panel = widget
    return widget


def make_status_details_widget(self) -> QtWidgets.QWidget:
    widget = StatusDetailsPanel(parent=self)
    self.status_details_panel = widget
    return widget


def make_project_relink_widget(self) -> QtWidgets.QWidget:
    widget = ProjectRelinkPanel(parent=self)
    self.project_relink_panel = widget
    return widget


def make_advanced_analysis_widget(self) -> QtWidgets.QWidget:
    """Create progressive-disclosure container for advanced assist analysis."""
    container = QtWidgets.QWidget(parent=self)
    layout = QtWidgets.QVBoxLayout(container)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(3)

    intro = QtWidgets.QLabel(
        "Advanced assist analysis tools.\n"
        "Hidden by default to reduce onboarding load."
    )
    intro.setWordWrap(True)
    layout.addWidget(intro)

    toolbox = QtWidgets.QToolBox(container)
    section_explain = QtWidgets.QWidget()
    explain_layout = QtWidgets.QVBoxLayout(section_explain)
    explain_layout.setContentsMargins(3, 3, 3, 3)
    explain_layout.addWidget(
        QtWidgets.QLabel("Inspect score components, patch preview, and staleness.")
    )
    self.advanced_open_explain_btn = QtWidgets.QPushButton("Open Why This Suggestion")
    explain_layout.addWidget(self.advanced_open_explain_btn)
    explain_layout.addStretch(1)
    toolbox.addItem(section_explain, "Explain Panel")

    section_train = QtWidgets.QWidget()
    train_layout = QtWidgets.QVBoxLayout(section_train)
    train_layout.setContentsMargins(3, 3, 3, 3)
    train_layout.addWidget(
        QtWidgets.QLabel("Training controls and minima are in Settings -> Advanced.")
    )
    self.advanced_open_training_btn = QtWidgets.QPushButton("Open Training Controls")
    train_layout.addWidget(self.advanced_open_training_btn)
    self.advanced_train_now_btn = QtWidgets.QPushButton("Train Ranker Now")
    train_layout.addWidget(self.advanced_train_now_btn)
    train_layout.addStretch(1)
    toolbox.addItem(section_train, "Training Controls")

    section_cal = QtWidgets.QWidget()
    cal_layout = QtWidgets.QVBoxLayout(section_cal)
    cal_layout.setContentsMargins(3, 3, 3, 3)
    cal_layout.addWidget(
        QtWidgets.QLabel("Inspect calibration and proposal metrics diagnostics.")
    )
    self.advanced_open_calib_btn = QtWidgets.QPushButton("Open Calibration Diagnostics")
    cal_layout.addWidget(self.advanced_open_calib_btn)
    cal_layout.addStretch(1)
    toolbox.addItem(section_cal, "Calibration Diagnostics")

    layout.addWidget(toolbox)
    layout.addStretch(1)
    return container


def make_roi_widget(self) -> QtWidgets.QWidget:
    roi_widget = QtWidgets.QWidget()
    roi_layout = QtWidgets.QVBoxLayout(roi_widget)
    roi_layout.setContentsMargins(8, 8, 8, 8)
    roi_layout.setSpacing(8)
    roi_layout.addWidget(QtWidgets.QLabel("ROI (X, Y, W, H)"))
    if self._roi_controls_layout is not None:
        roi_layout.addLayout(self._roi_controls_layout)
    return roi_widget


def make_roi_manager_widget(self) -> QtWidgets.QWidget:
    widget = RoiManagerWidget(self.roi_manager, parent=self)
    self.roi_manager_widget = widget
    return widget


def make_results_widget(self) -> QtWidgets.QWidget:
    widget = ResultsTableWidget(parent=self)
    self.results_widget = widget
    return widget


def make_recorder_widget(self) -> QtWidgets.QWidget:
    widget = RecorderWidget(self.recorder, parent=self)
    self.recorder_widget = widget
    return widget


def make_hist_widget(self) -> QtWidgets.QWidget:
    if self.hist_canvas is None:
        self.hist_fig = Figure(figsize=(4, 3))
        self.hist_canvas = FigureCanvasQTAgg(self.hist_fig)
        self.ax_hist = self.hist_fig.add_subplot(111)
    hist_container = QtWidgets.QWidget()
    hist_layout = QtWidgets.QVBoxLayout(hist_container)
    hist_layout.setContentsMargins(8, 8, 8, 8)
    hist_layout.setSpacing(6)
    controls = QtWidgets.QHBoxLayout()
    self.hist_chk = QtWidgets.QCheckBox("Histogram")
    self.hist_chk.setChecked(True)
    self.show_hist_chk = self.hist_chk
    self.hist_bins_spin = QtWidgets.QSpinBox()
    self.hist_bins_spin.setRange(16, 512)
    self.hist_bins_spin.setValue(self.hist_bins)
    self.hist_region_combo = QtWidgets.QComboBox()
    self.hist_region_combo.addItems(["Full image", "ROI", "Crop area"])
    if self.hist_region == "roi":
        self.hist_region_combo.setCurrentText("ROI")
    elif self.hist_region == "crop":
        self.hist_region_combo.setCurrentText("Crop area")
    else:
        self.hist_region_combo.setCurrentText("Full image")
    self.hist_scope_combo = QtWidgets.QComboBox()
    self.hist_scope_combo.addItems(["Current slice", "Sampled stack"])
    self.hist_scope_combo.setCurrentText(self._hist_scope_mode)
    controls.addWidget(self.hist_chk)
    controls.addWidget(QtWidgets.QLabel("Bins"))
    controls.addWidget(self.hist_bins_spin)
    controls.addWidget(self.hist_region_combo)
    controls.addWidget(self.hist_scope_combo)
    controls.addStretch(1)
    hist_layout.addLayout(controls)
    hist_layout.addWidget(self.hist_canvas)
    bc_group = QtWidgets.QGroupBox("B&C")
    bc_layout = QtWidgets.QGridLayout(bc_group)
    bc_layout.setContentsMargins(6, 6, 6, 6)
    bc_layout.setSpacing(6)

    self.bc_preview = QtWidgets.QLabel()
    self.bc_preview.setFixedHeight(60)
    self.bc_preview.setMinimumWidth(140)
    self.bc_preview.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.Fixed,
    )
    bc_layout.addWidget(self.bc_preview, 0, 0, 1, 3)

    self.bc_range_slider = SliderPanelDouble()
    self.bc_range_slider.setMinimumHeight(26)
    bc_layout.addWidget(QtWidgets.QLabel("Range"), 1, 0)
    bc_layout.addWidget(self.bc_range_slider, 1, 1, 1, 2)

    self.bc_min_spin = QtWidgets.QDoubleSpinBox()
    self.bc_max_spin = QtWidgets.QDoubleSpinBox()
    for spin in (self.bc_min_spin, self.bc_max_spin):
        spin.setDecimals(3)
        spin.setSingleStep(1.0)
        spin.setKeyboardTracking(False)
    bc_layout.addWidget(QtWidgets.QLabel("Minimum"), 2, 0)
    bc_layout.addWidget(self.bc_min_spin, 2, 1)
    bc_layout.addWidget(QtWidgets.QLabel("Maximum"), 3, 0)
    bc_layout.addWidget(self.bc_max_spin, 3, 1)

    self.bc_brightness_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    self.bc_brightness_slider.setRange(-100, 100)
    self.bc_brightness_slider.setValue(0)
    self.bc_contrast_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    self.bc_contrast_slider.setRange(-100, 100)
    self.bc_contrast_slider.setValue(0)
    bc_layout.addWidget(QtWidgets.QLabel("Brightness"), 4, 0)
    bc_layout.addWidget(self.bc_brightness_slider, 4, 1, 1, 2)
    bc_layout.addWidget(QtWidgets.QLabel("Contrast"), 5, 0)
    bc_layout.addWidget(self.bc_contrast_slider, 5, 1, 1, 2)

    bc_btns = QtWidgets.QHBoxLayout()
    self.bc_auto_btn = QtWidgets.QPushButton("Auto")
    self.bc_reset_btn = QtWidgets.QPushButton("Reset")
    self.bc_set_btn = QtWidgets.QPushButton("Set")
    self.bc_dialog_btn = QtWidgets.QPushButton("Dialog")
    self.bc_apply_btn = QtWidgets.QPushButton("Apply")
    bc_btns.addWidget(self.bc_auto_btn)
    bc_btns.addWidget(self.bc_reset_btn)
    bc_btns.addWidget(self.bc_set_btn)
    bc_btns.addWidget(self.bc_dialog_btn)
    bc_btns.addWidget(self.bc_apply_btn)
    bc_layout.addLayout(bc_btns, 6, 0, 1, 3)

    hist_layout.addWidget(bc_group)
    return hist_container


def make_profile_widget(self) -> QtWidgets.QWidget:
    """Create the profile (line-plot) widget and checkbox."""
    if self.profile_canvas is None:
        self.profile_fig = Figure(figsize=(4, 3))
        self.profile_canvas = FigureCanvasQTAgg(self.profile_fig)
        self.ax_line = self.profile_fig.add_subplot(111)
    profile_container = QtWidgets.QWidget()
    profile_layout = QtWidgets.QVBoxLayout(profile_container)
    profile_layout.setContentsMargins(8, 8, 8, 8)
    profile_layout.setSpacing(6)
    controls = QtWidgets.QHBoxLayout()
    self.profile_chk = QtWidgets.QCheckBox("Profile")
    self.profile_chk.setChecked(True)
    self.show_profile_chk = self.profile_chk  # Alias for backward compatibility
    controls.addWidget(self.profile_chk)
    controls.addStretch(1)
    profile_layout.addLayout(controls)
    profile_layout.addWidget(self.profile_canvas)
    return profile_container


def make_orthoview_widget(self) -> QtWidgets.QWidget:
    widget = OrthoViewWidget(parent=self)
    self.orthoview_widget = widget
    return widget


def make_smlm_widget(self) -> QtWidgets.QWidget:
    widget = SmlmPanel(parent=self)
    self.smlm_panel = widget
    return widget


def make_threshold_widget(self) -> QtWidgets.QWidget:
    widget = ThresholdPanel(parent=self)
    self.threshold_panel = widget
    return widget


def make_particles_widget(self) -> QtWidgets.QWidget:
    widget = AnalyzeParticlesPanel(parent=self)
    self.particles_panel = widget
    return widget


def make_channel_controls_widget(self) -> QtWidgets.QWidget:
    """Create the channel controls dock widget."""
    widget = ChannelControlPanel(parent=self)
    self.channel_panel = widget
    return widget


def make_logs_widget(self) -> QtWidgets.QWidget:
    """Create the logs and cache statistics widget."""
    logs_widget = QtWidgets.QWidget()
    logs_layout = QtWidgets.QVBoxLayout(logs_widget)
    logs_layout.setContentsMargins(8, 8, 8, 8)
    logs_layout.setSpacing(6)
    # Status label is initialized during UI setup; guard prevents startup-order issues.
    if self.status is not None:
        logs_layout.addWidget(self.status)
    # Header row: cache stats + filter + actions
    header_row = QtWidgets.QHBoxLayout()
    self.cache_stats_label = QtWidgets.QLabel("Cache: 0 MB | Items: 0")
    header_row.addWidget(self.cache_stats_label)
    
    # Severity filter
    filter_label = QtWidgets.QLabel(" Level:")
    self.log_level_combo = QtWidgets.QComboBox()
    self.log_level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
    self.log_level_combo.setCurrentText("ALL")
    self.log_level_combo.setToolTip("Filter log messages by severity level")
    self.log_level_combo.setMaximumWidth(100)
    header_row.addWidget(filter_label)
    header_row.addWidget(self.log_level_combo)
    
    header_row.addStretch(1)
    copy_btn = QtWidgets.QToolButton()
    copy_btn.setText("Copy")
    copy_btn.setToolTip("Copy logs to clipboard")
    save_btn = QtWidgets.QToolButton()
    save_btn.setText("Save…")
    save_btn.setToolTip("Save logs to file")
    clear_btn = QtWidgets.QToolButton()
    clear_btn.setText("Clear")
    clear_btn.setToolTip("Clear log view")
    header_row.addWidget(copy_btn)
    header_row.addWidget(save_btn)
    header_row.addWidget(clear_btn)
    logs_layout.addLayout(header_row)
    self.log_view = QtWidgets.QPlainTextEdit()
    self.log_view.setReadOnly(True)
    self.log_view.setMaximumBlockCount(1000)
    self.log_view.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
    logs_layout.addWidget(self.log_view)

    # Store full logs for filtering
    self._all_logs = []
    
    # Wire actions
    def _copy_logs() -> None:
        QtWidgets.QApplication.clipboard().setText(self.log_view.toPlainText())
    
    def _clear_logs() -> None:
        self.log_view.clear()
        self._all_logs.clear()

    def _save_logs() -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Logs", str(pathlib.Path.cwd() / "phage_annotator.log"), "Log Files (*.log);;Text Files (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_view.toPlainText())
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save Logs failed", str(exc))
    
    def _filter_logs() -> None:
        """Filter logs based on selected severity level."""
        level = self.log_level_combo.currentText()
        self.log_view.clear()
        
        if level == "ALL":
            for log_entry in self._all_logs:
                self.log_view.appendPlainText(log_entry)
        else:
            # Filter by level keyword
            for log_entry in self._all_logs:
                if f"[{level}]" in log_entry or (level == "ERROR" and "[EXCEPTION]" in log_entry):
                    self.log_view.appendPlainText(log_entry)

    copy_btn.clicked.connect(_copy_logs)
    save_btn.clicked.connect(_save_logs)
    clear_btn.clicked.connect(_clear_logs)
    self.log_level_combo.currentTextChanged.connect(_filter_logs)
    return logs_widget


def make_metadata_widget(self) -> QtWidgets.QWidget:
    widget = MetadataDock(parent=self)
    self.metadata_widget = widget
    return widget


def make_density_widget(self) -> QtWidgets.QWidget:
    widget = DensityPanel(parent=self)
    self.density_panel = widget
    return widget


def make_modality_layers_widget(self) -> QtWidgets.QWidget:
    widget = ModalityLayersPanel(parent=self)
    self.modality_layers_panel = widget
    return widget


def make_qc_issues_widget(self) -> QtWidgets.QWidget:
    widget = QCIssuesPanel(qc_state=getattr(self, "qc_state", None), parent=self)
    self.qc_issues_panel = widget
    return widget


def setup_status_bar(self) -> None:
    """Initialize status-bar widgets (progress, buffer stats, and tool status)."""
    status_bar = self.statusBar()
    status_bar.setSizeGripEnabled(True)
    indicator = getattr(self, "_status_indicator_bar", None)
    if indicator is not None:
        try:
            status_bar.removeWidget(indicator)
            indicator.setParent(None)
            indicator.deleteLater()
        except Exception:
            pass
        self._status_indicator_bar = None
    # Add soft border and background styling to the status bar
    status_bar.setStyleSheet(
        "QStatusBar { border-top: 2px solid #b8b8b8; background: #f5f5f5; padding: 2px; }"
    )

    # QLabel used by docks as the shared status text widget.
    self.status = QtWidgets.QLabel("", status_bar)
    self.status.setMinimumWidth(180)
    status_bar.addWidget(self.status, stretch=0)
    self.status_runtime_lbl = QtWidgets.QLabel(
        "Points: 0 | ROI: n/a | Density: n/a | FPS: 30",
        status_bar,
    )
    self.status_runtime_lbl.setVisible(False)
    status_bar.addPermanentWidget(self.status_runtime_lbl)

    # Permanent operational state widgets (single source of truth).
    self.status_dataset_lbl = QtWidgets.QLabel("Dataset: -", status_bar)
    self.status_tz_lbl = QtWidgets.QLabel("T: -/- | Z: -/-", status_bar)
    self.status_points_lbl = QtWidgets.QLabel("Points: 0", status_bar)
    self.status_roi_area_lbl = QtWidgets.QLabel("ROI area: -", status_bar)
    self.status_density_lbl = QtWidgets.QLabel("Density: -", status_bar)
    self.status_fps_lbl = QtWidgets.QLabel("FPS: 30", status_bar)
    self.status_label_lbl = QtWidgets.QLabel("Label: -", status_bar)
    self.status_scope_lbl = QtWidgets.QLabel("Scope: Slice", status_bar)
    self.status_target_lbl = QtWidgets.QLabel("Target: Frame", status_bar)
    self.status_modality_combo = QtWidgets.QComboBox(status_bar)
    self.status_modality_combo.setMinimumContentsLength(16)
    self.status_context_lock_lbl = QtWidgets.QLabel("Write Context: Locked", status_bar)
    self.status_effective_context_lbl = QtWidgets.QLabel("Effective Assist Context: -", status_bar)
    self.status_assist_lbl = QtWidgets.QLabel("Assist: Off", status_bar)
    self.status_suggestion_fresh_lbl = QtWidgets.QLabel("Suggestions: n/a", status_bar)
    self.status_qc_lbl = QtWidgets.QLabel("QC: 0 warnings", status_bar)
    self.status_results_lbl = QtWidgets.QLabel("Results: empty", status_bar)
    self.status_strategy_combo = QtWidgets.QComboBox(status_bar)
    self.status_strategy_combo.setMinimumContentsLength(14)
    self.status_assist_mode_btn = QtWidgets.QToolButton(status_bar)
    self.status_assist_mode_btn.setCheckable(True)
    self.status_assist_mode_btn.setText("Assist Mode: Off")
    # Keep status bar transient-first: no always-on permanent info strip widgets.
    # Detailed operational context is available via status-details panel/actions.
    # Secondary state stays available for logic/tooltips but is hidden from the
    # default status bar strip to reduce visual crowding.
    for widget in (
        self.status_dataset_lbl,
        self.status_tz_lbl,
        self.status_label_lbl,
        self.status_scope_lbl,
        self.status_target_lbl,
        self.status_points_lbl,
        self.status_roi_area_lbl,
        self.status_density_lbl,
        self.status_fps_lbl,
        self.status_context_lock_lbl,
        self.status_effective_context_lbl,
        self.status_assist_lbl,
        self.status_suggestion_fresh_lbl,
        self.status_qc_lbl,
        self.status_results_lbl,
        self.status_modality_combo,
        self.status_strategy_combo,
        self.status_assist_mode_btn,
    ):
        widget.setVisible(False)
    
    self.progress_label = QtWidgets.QLabel("Working:")
    self.progress_bar = QtWidgets.QProgressBar()
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)
    self.progress_bar.setFixedWidth(160)
    self.progress_cancel_btn = QtWidgets.QToolButton()
    self.progress_cancel_btn.setText("Cancel")
    self.progress_cancel_btn.clicked.connect(self._cancel_active_job)
    # Add a 'Cancel All' button to stop all background jobs
    self.progress_cancel_all_btn = QtWidgets.QToolButton()
    self.progress_cancel_all_btn.setText("Cancel All")
    self.progress_cancel_all_btn.clicked.connect(self._cancel_all_jobs)
    for w in (self.progress_label, self.progress_bar, self.progress_cancel_btn, self.progress_cancel_all_btn):
        w.setVisible(False)
        status_bar.addPermanentWidget(w)
    self.buffer_stats_label = QtWidgets.QLabel("Buffer: 0/0 | Prefetch: 64 | Underruns: 0")
    self.buffer_stats_label.setVisible(False)
    status_bar.addPermanentWidget(self.buffer_stats_label)
    self.render_level_label = QtWidgets.QLabel("Render: L0")
    self.render_level_label.setVisible(False)
    status_bar.addPermanentWidget(self.render_level_label)
    self.tool_label = QtWidgets.QLabel("Tool: Annotate")
    self.tool_label.setVisible(False)
    status_bar.addPermanentWidget(self.tool_label)
    self.annotation_meta_widget = QtWidgets.QWidget()
    meta_layout = QtWidgets.QHBoxLayout(self.annotation_meta_widget)
    meta_layout.setContentsMargins(6, 0, 6, 0)
    meta_layout.setSpacing(6)
    self.annotation_meta_label = QtWidgets.QLabel("Metadata detected.")
    self.annotation_meta_apply_btn = QtWidgets.QToolButton()
    self.annotation_meta_apply_btn.setText("Apply")
    self.annotation_meta_close_btn = QtWidgets.QToolButton()
    self.annotation_meta_close_btn.setText("Dismiss")
    meta_layout.addWidget(self.annotation_meta_label)
    meta_layout.addWidget(self.annotation_meta_apply_btn)
    meta_layout.addWidget(self.annotation_meta_close_btn)
    self.annotation_meta_widget.setVisible(False)
    status_bar.addWidget(self.annotation_meta_widget)
