"""Keyboard dispatch mixin."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.keyboard_registry import (
    detect_conflicts,
    all_shortcuts,
    matplotlib_key_bindings,
    qt_key_bindings,
)
from phage_annotator.tools import Tool


class KeyboardEventsMixin:
    """Qt and Matplotlib keyboard shortcut handlers."""

    def _suggestion_shortcut_context_available(self) -> bool:
        """Return True when suggestion triage shortcuts are safe to execute."""
        if not bool(getattr(self, "_show_suggestion_overlay", True)):
            return False
        if not hasattr(self, "_visible_suggestions_uncertain_first"):
            return False
        try:
            return bool(self._visible_suggestions_uncertain_first())
        except Exception:
            return False

    def _suggestion_shortcut_noop_hint(self) -> None:
        """Show a subtle hint when suggestion shortcuts are used out of context."""
        if hasattr(self, "_set_status"):
            self._set_status("No suggestions to review on current view.")

    def _keyboard_registry_ok(self) -> bool:
        return len(detect_conflicts(all_shortcuts())) == 0

    def _on_key(self, event) -> None:
        """Handle Matplotlib-key shortcuts for reset, colormap cycle, and quick-save."""
        key_id = matplotlib_key_bindings().get(str(event.key).lower(), "")
        if key_id == "reset_view":
            self.reset_all_view()
        elif key_id == "cycle_colormap":
            self.current_cmap_idx = (self.current_cmap_idx + 1) % len(self.colormaps)
            if self.lut_combo is not None:
                self.lut_combo.setCurrentIndex(self.current_cmap_idx)
            self._refresh_image()
        elif key_id == "quick_save":
            self._quick_save_csv()

    def keyPressEvent(self, event) -> None:
        """Qt-level shortcuts for fast navigation; ignored when editing text fields."""
        focused = QtWidgets.QApplication.focusWidget()
        if isinstance(
            focused,
            (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit),
        ):
            return super().keyPressEvent(event)
        key = event.key()
        mods = event.modifiers()
        action_id = ""
        for bind_key, bind_mods, bind_id in qt_key_bindings():
            if key == bind_key and mods == bind_mods:
                action_id = bind_id
                break

        if action_id == "nav_time_prev":
            self._step_slider(self.t_slider, -1)
        elif action_id == "nav_time_next":
            self._step_slider(self.t_slider, 1)
        elif action_id == "nav_z_prev":
            self._step_slider(self.z_slider, -1)
        elif action_id == "nav_z_next":
            self._step_slider(self.z_slider, 1)
        elif action_id == "play_pause":
            self._toggle_play("t")
        elif action_id == "contextual_help":
            if hasattr(self, "_show_contextual_help"):
                self._show_contextual_help()
        elif action_id == "delete_selected":
            if self.tool_router and self.tool_router.tool in (
                Tool.ROI_BOX,
                Tool.ROI_CIRCLE,
                Tool.ROI_EDIT,
            ):
                self._clear_roi()
            else:
                self._delete_selected_annotations()
        elif action_id == "accept_suggestion":
            if self._suggestion_shortcut_context_available() and hasattr(
                self, "_accept_current_uncertain_suggestion"
            ):
                self._accept_current_uncertain_suggestion()
            else:
                self._suggestion_shortcut_noop_hint()
        elif action_id == "clear_roi":
            if self.tool_router and self.tool_router.tool in (
                Tool.ROI_BOX,
                Tool.ROI_CIRCLE,
                Tool.ROI_EDIT,
            ):
                self._clear_roi()
            return
        elif action_id == "next_suggestion":
            if self._suggestion_shortcut_context_available() and hasattr(
                self, "_next_uncertain_suggestion"
            ):
                self._next_uncertain_suggestion()
            else:
                self._suggestion_shortcut_noop_hint()
        elif action_id == "prev_suggestion":
            if self._suggestion_shortcut_context_available() and hasattr(
                self, "_prev_uncertain_suggestion"
            ):
                self._prev_uncertain_suggestion()
            else:
                self._suggestion_shortcut_noop_hint()
        elif action_id == "reset_view":
            self.reset_all_view()
        elif action_id == "reject_suggestion":
            if self._suggestion_shortcut_context_available() and hasattr(
                self, "_reject_current_uncertain_suggestion"
            ):
                self._reject_current_uncertain_suggestion()
            else:
                self._suggestion_shortcut_noop_hint()
        else:
            super().keyPressEvent(event)
