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

DISABLE_SHORTCUTS = False


class KeyboardEventsMixin:
    """Qt and Matplotlib keyboard shortcut handlers."""

    def _dispatch_base_key_press(self, event) -> None:
        """Fallback Qt key dispatch when this mixin does not handle a key."""
        try:
            QtWidgets.QMainWindow.keyPressEvent(self, event)
        except Exception:
            event.ignore()

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
        self._status_info(
            "No suggestions to review on current view.",
            timeout_ms=2000,
            source="keyboard",
        )

    def _keyboard_registry_ok(self) -> bool:
        return len(detect_conflicts(all_shortcuts())) == 0

    def _on_key(self, event) -> None:
        """Handle Matplotlib-key shortcuts (deprecated - now using Qt key events with modifiers)."""
        if DISABLE_SHORTCUTS or not bool(getattr(self, "_shortcuts_enabled", True)):
            return
        # Matplotlib direct key bindings are now handled via Qt keyPressEvent with modifiers
        # This prevents accidental single-key triggers when typing
        key_id = matplotlib_key_bindings().get(str(event.key).lower(), "")
        if key_id:  # Should be empty now, but keep for backwards compatibility
            pass

    def keyPressEvent(self, event) -> None:
        """Qt-level shortcuts for fast navigation; ignored when editing text fields."""
        if DISABLE_SHORTCUTS or not bool(getattr(self, "_shortcuts_enabled", True)):
            self._dispatch_base_key_press(event)
            return
        focused = QtWidgets.QApplication.focusWidget()
        if isinstance(
            focused,
            (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit),
        ):
            self._dispatch_base_key_press(event)
            return
        key = event.key()
        mods = event.modifiers()
        if key == QtCore.Qt.Key_Z and mods == QtCore.Qt.KeyboardModifier.ControlModifier:
            if hasattr(self, "_lazy_loader_focus_active") and self._lazy_loader_focus_active():
                if hasattr(self, "_undo_lazy_loader_removal") and self._undo_lazy_loader_removal():
                    return
            if hasattr(self, "undo_last_action"):
                self.undo_last_action()
            return
        if key == QtCore.Qt.Key_Z and mods == (
            QtCore.Qt.KeyboardModifier.ControlModifier
            | QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            if hasattr(self, "redo_last_action"):
                self.redo_last_action()
            return
        # Fast label selection: Ctrl+1..9 map to label buttons (requires modifier to avoid interference)
        if mods == QtCore.Qt.KeyboardModifier.ControlModifier and QtCore.Qt.Key_1 <= key <= QtCore.Qt.Key_9:
            idx = int(key - QtCore.Qt.Key_1)
            buttons = list(getattr(self, "label_buttons", QtWidgets.QButtonGroup()).buttons())
            if 0 <= idx < len(buttons):
                buttons[idx].setChecked(True)
                self.current_label = buttons[idx].text()
                self._status_info(
                    f"Active label: {self.current_label}",
                    timeout_ms=2000,
                    source="keyboard",
                )
                if hasattr(self, "_update_status"):
                    self._update_status()
                return
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
                self, "_accept_visible_suggestions"
            ):
                self._accept_visible_suggestions()
            else:
                self._suggestion_shortcut_noop_hint()
        elif action_id == "accept_current_suggestion":
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
        elif action_id == "label_prev":
            if hasattr(self, "_cycle_label"):
                self._cycle_label(-1)
        elif action_id == "label_next":
            if hasattr(self, "_cycle_label"):
                self._cycle_label(1)
        elif action_id == "focus_canvas_mode":
            if hasattr(self, "_toggle_focus_canvas_mode"):
                self._toggle_focus_canvas_mode()
        elif action_id == "cycle_colormap":
            self.current_cmap_idx = (self.current_cmap_idx + 1) % len(self.colormaps)
            if self.lut_combo is not None:
                self.lut_combo.setCurrentIndex(self.current_cmap_idx)
            self._request_ui_refresh("keyboard-events")
        else:
            self._dispatch_base_key_press(event)
