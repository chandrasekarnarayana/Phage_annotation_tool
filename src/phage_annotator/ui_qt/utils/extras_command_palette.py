"""Extracted method group 13 for UiExtrasMixin."""

from __future__ import annotations

from pathlib import Path
from typing import List, Set, Tuple

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.services.action_logger import get_action_logger

from phage_annotator.ui_qt.models.lazy_loader import (
    LAZY_LOADER_FILE_FILTER,
    LAZY_LOADER_OPEN_FILES_TITLE,
    LAZY_LOADER_OPEN_FOLDER_TITLE,
    LAZY_TABLE_COLUMN_GROUP,
    LAZY_TABLE_COLUMN_NAME,
    LAZY_TABLE_COLUMN_ANNOTATION_FILE,
    LAZY_TABLE_COLUMN_ANNOTATION_MODE,
    LAZY_TABLE_COLUMN_POINTS,
    LAZY_TABLE_COLUMN_PROJECTION,
    LAZY_TABLE_COLUMN_SHOW,
    LAZY_TABLE_COLUMN_SOURCE,
    LAZY_TABLE_COLUMN_SYNC_CONTRAST,
    LAZY_TABLE_COLUMN_SYNC_TIME,
    LAZY_TABLE_COLUMN_SYNC_VIEW,
    LAZY_TABLE_COLUMN_TABLE,
    LazyTableRowSpec,
    normalize_lazy_sync_groups,
    iter_tiff_paths,
)
from phage_annotator.ui_qt.utils.ui_extra_annotations import (
    UiAnnotationViewsMixin,
    _LogicalVisibilityLabel,
)
from phage_annotator.ui_qt.utils.ui_extra_refresh import UiRefreshMixin
from phage_annotator.ui_qt.utils.ui_extra_tooltips import UiTooltipMixin
from phage_annotator.ui_qt.utils.iconography import right_sidebar_icon, tool_icon, workflow_sidebar_icon
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.utils.sidebar_manager import SidebarLayoutConfig, SidebarManager
from phage_annotator.tools import Tool, ToolCallbacks, ToolRouter

PRIMARY_RIGHT_SIDEBAR_PANELS = (
    "annotations",
    "review_queue",
    "advanced_settings",
    "advanced_analysis",
    "qc_issues",
)
SUPPLEMENTAL_RIGHT_SIDEBAR_PANELS = (
    "status_details",
)
ALL_RIGHT_SIDEBAR_PANELS = PRIMARY_RIGHT_SIDEBAR_PANELS + SUPPLEMENTAL_RIGHT_SIDEBAR_PANELS



class ExtrasCommandPaletteMixin:
    """Method group 13 extracted from UiExtrasMixin."""

    def _show_command_palette_with_query(self, initial_query: str = "") -> None:
        """Show command palette with query for the current workflow."""
        existing = getattr(self, "_command_palette_dialog", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        actions = self._collect_command_actions()
        dlg = QtWidgets.QDialog(self)
        self._command_palette_dialog = dlg
        dlg.setWindowTitle("Command Palette")
        dlg.setWindowModality(QtCore.Qt.NonModal)
        dlg.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dlg.resize(520, 320)
        layout = QtWidgets.QVBoxLayout(dlg)
        search = QtWidgets.QLineEdit()
        search.setPlaceholderText("Type a command...")
        listw = QtWidgets.QListWidget()
        rationale_lbl = QtWidgets.QLabel("")
        rationale_lbl.setStyleSheet("color: #666666;")
        layout.addWidget(search)
        layout.addWidget(listw)
        layout.addWidget(rationale_lbl)

        action_map: List[Tuple[str, QtWidgets.QAction, str]] = []
        for act in actions:
            label = act.text().replace("&", "").strip()
            object_name = str(act.objectName() or "")
            search_blob = label.lower()
            if object_name.startswith("open_panel_"):
                panel_id = object_name.replace("open_panel_", "", 1)
                panel_specs = dict(getattr(self, "panel_specs_by_id", {}) or {})
                spec = panel_specs.get(panel_id)
                if spec is not None:
                    label = f"{label} [{str(spec.bucket).title()}]"
                    aliases = tuple(getattr(spec, "search_aliases", ()) or ())
                    if aliases:
                        search_blob = f"{search_blob} " + " ".join(str(a).lower() for a in aliases)
            action_map.append((label, act, search_blob))

        if not hasattr(self, "_command_usage_count"):
            self._command_usage_count = {}
        if not hasattr(self, "_command_last_used_ts"):
            self._command_last_used_ts = {}

        def _current_palette_mode() -> str:
            """Handle the current palette mode helper flow."""
            if getattr(self, "dock_review_queue", None) is not None and self.dock_review_queue.isVisible():
                return "review"
            return "annotate"

        mode_keywords = {
            "review": ("review", "queue", "qc", "issue", "approve", "assign", "reject"),
            "annotate": ("annotate", "point", "label", "roi", "slice", "frame", "accept"),
        }

        import time

        def _score(label: str, act: QtWidgets.QAction, filter_text: str) -> float:
            """Score score for the current workflow."""
            key = str(act.objectName() or label)
            usage = float(self._command_usage_count.get(key, 0))
            last_ts = float(self._command_last_used_ts.get(key, 0.0))
            age_sec = max(0.0, float(time.time()) - last_ts) if last_ts > 0 else 1e9
            recency_bonus = max(0.0, 1000.0 - min(1000.0, age_sec))
            score = usage * 3.0 + recency_bonus
            mode = _current_palette_mode()
            low = label.lower()
            if any(k in low for k in mode_keywords.get(mode, ())):
                score += 10.0
            if filter_text:
                if low.startswith(filter_text):
                    score += 30.0
                elif filter_text in low:
                    score += 10.0
            return score

        def _populate(filter_text: str = "") -> None:
            """Handle the populate helper flow."""
            listw.clear()
            panel_only = False
            filter_expr = filter_text
            if filter_text.startswith("panel "):
                panel_only = True
                filter_expr = filter_text[len("panel "):].strip()
            ranked = sorted(
                action_map,
                key=lambda row: _score(row[0], row[1], filter_text),
                reverse=True,
            )
            for label, act, search_blob in ranked:
                object_name = str(act.objectName() or "")
                if panel_only and not object_name.startswith("open_panel_"):
                    continue
                if filter_expr and filter_expr not in search_blob:
                    continue
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, act)
                if not act.isEnabled():
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
                listw.addItem(item)
            if listw.count():
                listw.setCurrentRow(0)
            mode = _current_palette_mode()
            if panel_only:
                rationale_lbl.setText("Panel switcher mode: searching panel commands only.")
            else:
                rationale_lbl.setText(
                    f"Ranking: frequency + recency + mode boost ({mode}). "
                    "Review mode boosts review/QC commands."
                )

        def _activate() -> None:
            """Handle the activate helper flow."""
            item = listw.currentItem()
            if item is None:
                return
            act = item.data(QtCore.Qt.UserRole)
            dlg.accept()
            if act is not None:
                key = str(act.objectName() or act.text().replace("&", "").strip())
                self._command_usage_count[key] = int(self._command_usage_count.get(key, 0) + 1)
                self._command_last_used_ts[key] = float(time.time())
                act.trigger()

        _populate(initial_query.strip().lower())
        search.textChanged.connect(lambda text: _populate(text.strip().lower()))
        search.returnPressed.connect(_activate)
        listw.itemActivated.connect(lambda _: _activate())
        dlg.finished.connect(lambda _code: setattr(self, "_command_palette_dialog", None))
        if initial_query:
            search.setText(initial_query)
            search.selectAll()
        search.setFocus()
        dlg.open()
    def _toggle_review_context_pack(self) -> None:
        """One-click toggle for the review workspace: table, assist, and QC."""
        keys = ("annotations", "review_queue", "qc_issues")
        visible_now = [
            bool(getattr(self, "panel_docks", {}).get(k).isVisible())
            for k in keys
            if getattr(self, "panel_docks", {}).get(k) is not None
        ]
        pack_on = not all(visible_now)
        if pack_on:
            for key in keys:
                self.set_panel_visible(key, True, source="review_context_pack")
            self.set_panel_visible("status_details", False, source="review_context_pack")
            if getattr(self, "dock_review_queue", None) is not None:
                self.dock_review_queue.raise_()
            self._status_info("Review Context Pack enabled.", source="ui_extra.review_pack")
        else:
            self.set_panel_visible("annotations", True, source="review_context_pack")
            self.set_panel_visible("review_queue", False, source="review_context_pack")
            self.set_panel_visible("qc_issues", False, source="review_context_pack")
            self.set_panel_visible("status_details", False, source="review_context_pack")
            self._status_info("Review Context Pack collapsed to table.", source="ui_extra.review_pack")
    def _apply_default_layout(self) -> None:
        """Save the initial layout as the default reset state."""
        self.apply_preset("Default")
        self._default_geometry = self.saveGeometry()
        self._default_state = self.saveState()
        self._preset_active = False
        self._apply_canvas_priority_layout()
    def _restore_layout(self) -> None:
        """Restore the user's custom layout from QSettings if present."""
        # DISABLED: Layout restoration disabled to prevent floating dock windows
        # geometry = self._settings.value("customGeometry", type=QtCore.QByteArray)
        # state = self._settings.value("customState", type=QtCore.QByteArray)
        # if geometry:
        #     self.restoreGeometry(geometry)
        # if state:
        #     self.restoreState(state)
        
        # Ensure no docks are floating
        for dock_attr in dir(self):
            if dock_attr.startswith("dock_") and hasattr(self, dock_attr):
                dock = getattr(self, dock_attr)
                if isinstance(dock, QtWidgets.QDockWidget) and dock is not None:
                    try:
                        dock.setFloating(False)
                    except Exception:
                        pass
        
        if self.dock_sidebar is not None and not self.dock_sidebar.isVisible():
            self.set_panel_visible("sidebar", True, source="layout_restore")
        # Keep status details dock opt-in only; do not auto-restore it.
        if hasattr(self, "set_panel_visible"):
            self.set_panel_visible("status_details", False, source="layout_restore")
        self._apply_canvas_priority_layout()
    def _save_layout(self) -> None:
        """Persist the current layout unless a preset is active."""
        if self._preset_active:
            return
        self._settings.setValue("customGeometry", self.saveGeometry())
        self._settings.setValue("customState", self.saveState())
    def _save_layout_default(self) -> None:
        """Save the current layout as the new default custom layout."""
        self._preset_active = False
        self._settings.setValue("customGeometry", self.saveGeometry())
        self._settings.setValue("customState", self.saveState())
    def _capture_layout_snapshot(self) -> None:
        """Capture one-step layout undo state before major layout changes."""
        self._layout_prev_geometry = self.saveGeometry()
        self._layout_prev_state = self.saveState()
        act = getattr(self, "undo_layout_change_act", None)
        if act is not None:
            act.setEnabled(True)
    def _undo_layout_change(self) -> None:
        """Restore the previous saved layout snapshot once."""
        geometry = getattr(self, "_layout_prev_geometry", None)
        state = getattr(self, "_layout_prev_state", None)
        if geometry is None or state is None:
            return
        self.restoreGeometry(geometry)
        self.restoreState(state)
        self._apply_canvas_priority_layout()
        self._layout_prev_geometry = None
        self._layout_prev_state = None
        act = getattr(self, "undo_layout_change_act", None)
        if act is not None:
            act.setEnabled(False)
        self._status_success("Layout restored.", timeout_ms=3000, source="ui_extra.layout")
