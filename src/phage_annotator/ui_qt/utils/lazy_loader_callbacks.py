"""Extracted method group 11 for UiExtrasMixin."""

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



class LazyLoaderCallbacksMixin:
    """Method group 11 extracted from UiExtrasMixin."""

    def _on_lazy_modality_projection_changed(self, modality_idx: int, projection_key: str) -> None:
        """Handle the on lazy modality projection changed helper flow."""
        if getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system
        from phage_annotator.session.modality import ProjectionType

        manager = ensure_modality_system(self.controller.session_state)
        modality = manager.get_modality(int(modality_idx))
        if modality is None:
            return
        old_projection = str(getattr(modality.projection_type, "value", "raw"))
        try:
            modality.projection_type = ProjectionType(str(projection_key).strip().lower())
        except Exception:
            modality.projection_type = ProjectionType.RAW
        self._queue_lazy_panel_auto_contrast(self._panel_key_for_modality_idx(int(modality_idx)))
        self._request_lazy_canvas_refresh("lazy-projection-change", refresh_table=False)
        self._flush_lazy_canvas_refresh()
        
        logger = get_action_logger()
        logger.log_action(
            "projection_changed",
            panel="lazy_loader",
            details={
                "modality_idx": modality_idx,
                "old_projection": old_projection,
                "new_projection": projection_key
            }
        )
    def _on_lazy_builtin_source_changed(self, panel_key: str, image_id: int) -> None:
        """Update source image for built-in mean/std panel rows."""
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        cfg = dict(builtin.get(str(panel_key), {}) or {})
        cfg["image_id"] = int(image_id)
        builtin[str(panel_key)] = cfg
        self._lazy_builtin_views = builtin
        self.controller.clear_annotation_binding_for_panel(
            str(panel_key),
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
        )
        self._auto_bind_detected_annotation_for_panel(str(panel_key), int(image_id))
        self._queue_lazy_panel_auto_contrast(str(panel_key))
        self._request_lazy_canvas_refresh("lazy-builtin-source", refresh_table=False)
        self._flush_lazy_canvas_refresh()
    def _on_lazy_builtin_projection_changed(self, panel_key: str, projection_key: str) -> None:
        """Update projection type for built-in mean/std panel rows."""
        if str(panel_key) == "support":
            return
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        cfg = dict(builtin.get(str(panel_key), {}) or {})
        old_projection = str(cfg.get("projection", "raw"))
        cfg["projection"] = str(projection_key).strip().lower()
        builtin[str(panel_key)] = cfg
        self._lazy_builtin_views = builtin
        self._queue_lazy_panel_auto_contrast(str(panel_key))
        self._request_lazy_canvas_refresh("lazy-builtin-projection", refresh_table=False)
        self._flush_lazy_canvas_refresh()
        
        logger = get_action_logger()
        logger.log_action(
            "projection_changed",
            panel="lazy_loader",
            details={
                "builtin_panel": panel_key,
                "old_projection": old_projection,
                "new_projection": projection_key
            }
        )
    def _on_lazy_builtin_support_source_changed(self, image_id: int) -> None:
        """Update support panel source image from lazy table."""
        self._set_support_combo(
            self._image_index_for_id(int(image_id)),
            refresh_lazy_table=False,
        )
    def _focus_playback_controls(self) -> None:
        """Focus playback controls in the bottom bar from sidebar launcher page."""
        slider = getattr(self, "t_slider", None)
        if slider is not None:
            slider.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
            self._status_info(
                "Playback controls are active in the bottom bar.",
                timeout_ms=3500,
                source="ui_extra.playback_focus",
            )
    def _sidebar_mode_label_for_stack_index(self, stack_idx: int) -> str:
        """Return the workflow page label associated with the stack index."""
        for action_idx, mapped_idx in dict(getattr(self, "sidebar_panel_indices", {}) or {}).items():
            if int(mapped_idx) != int(stack_idx):
                continue
            actions = getattr(self, "sidebar_actions", []) or []
            if 0 <= int(action_idx) < len(actions):
                return str(actions[int(action_idx)].text()).strip().lower()
            break
        return ""
    def _sidebar_mode_contract(self, mode_label: str) -> dict[str, object]:
        """Return the dock contract for a workflow page.

        The left sidebar declares user intent; this contract determines which
        supporting panels remain visible and which workflow panels should be
        surfaced automatically through the panel manager.
        """
        target = str(mode_label or "").strip().lower()
        contracts: dict[str, dict[str, object]] = {
            "lazy loading": {
                "keep": {"hist"},
                "auto_open": (),
                "right_mode": None,
            },
            "annotation": {
                "keep": {
                    "annotations",
                    "review_queue",
                    "qc_issues",
                },
                "auto_open": (),
                "right_mode": "annotate",
            },
            "roi": {
                "keep": {"roi", "roi_manager"},
                "auto_open": (),
                "right_mode": None,
            },
            "contrast": {
                "keep": {"hist", "profile"},
                "auto_open": (),
                "right_mode": None,
            },
        }
        return contracts.get(target, {"keep": set(), "auto_open": (), "right_mode": None})
    def _collapse_sidebar_context_docks_for_stack_index(self, stack_idx: int) -> None:
        """Collapse context docks from previous mode; keep only workflow-relevant panels."""
        mode_label = self._sidebar_mode_label_for_stack_index(stack_idx)
        keep = set(self._sidebar_mode_contract(mode_label).get("keep", set()))
        managed = {
            "annotations",
            "review_queue",
            "advanced_settings",
            "advanced_analysis",
            "status_details",
            "qc_issues",
            "roi",
            "roi_manager",
            "results",
            "orthoview",
            "density",
            "smlm",
            "threshold",
            "particles",
            "performance",
            "logs",
            "metadata",
            "hist",
            "profile",
        }
        for panel_id in managed:
            if panel_id in keep:
                continue
            if hasattr(self, "is_panel_pinned") and self.is_panel_pinned(panel_id):
                continue
            if hasattr(self, "get_panel_opened_by") and self.get_panel_opened_by(panel_id) == "user":
                continue
            self.set_panel_visible(panel_id, False, source="sidebar_mode_switch")
    def _apply_sidebar_mode_defaults_for_stack_index(self, stack_idx: int) -> None:
        """Apply default supporting docks for the active workflow page."""
        mode_label = self._sidebar_mode_label_for_stack_index(stack_idx)
        contract = self._sidebar_mode_contract(mode_label)
        right_mode = contract.get("right_mode")
        if isinstance(right_mode, str) and hasattr(self, "_set_right_dock_mode"):
            self._set_right_dock_mode(right_mode)
        for panel_id in tuple(contract.get("auto_open", ())):
            self.open_panel(str(panel_id), reason=f"sidebar_mode:{mode_label}")
    def _sidebar_action_index_for_label(self, label: str) -> int:
        """Return sidebar action index by label, or -1 if not found."""
        aliases = {
            "prepare": "lazy loading",
            "lazy loading": "lazy loading",
            "annotate": "annotation",
            "annotation": "annotation",
            "review / qc": "annotation",
            "assist / review": "annotation",
            "advanced": "contrast",
            "display": "contrast",
            "contrast": "contrast",
            "export / settings": None,
            "settings": None,
            "roi": "roi",
        }
        raw = str(label).strip().lower()
        want = aliases.get(raw, raw)
        if want is None:
            return -1
        for i, act in enumerate(getattr(self, "sidebar_actions", []) or []):
            if str(act.text()).strip().lower() == want:
                return i
        return -1
    def open_preferences(self, section: str | None = None) -> None:
        """Open the preferences dialog and optionally focus a settings subsection."""
        self._show_preferences_dialog()

        focus_widget = (
            getattr(self, "suggestion_auto_retrain_chk", None)
            if section == "training_controls"
            else getattr(self, "panel_policy_reset_btn", None)
        )
        if focus_widget is not None:
            focus_widget.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)

        # Brief highlight to confirm navigation target.
        if getattr(self, "advanced_group", None) is not None:
            group = self.advanced_group
            prior_style = group.styleSheet()
            group.setStyleSheet(
                prior_style
                + "\nQGroupBox { border: 2px solid #42a5f5; border-radius: 4px; }"
            )
            def _restore_group_style() -> None:
                """Restore group style for the current workflow."""
                try:
                    group.setStyleSheet(prior_style)
                except RuntimeError:
                    # Widget may be deleted during teardown before timer fires.
                    return

            QtCore.QTimer.singleShot(1500, _restore_group_style)
