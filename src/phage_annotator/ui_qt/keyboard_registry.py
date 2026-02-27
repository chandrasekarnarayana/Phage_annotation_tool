"""Central keyboard shortcut registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Tuple

try:
    from matplotlib.backends.qt_compat import QtCore
except ImportError:  # pragma: no cover - headless test environments
    QtCore = None


@dataclass(frozen=True)
class ShortcutEntry:
    """Shortcut definition used by handlers, dialogs, and menu actions."""

    id: str
    shortcut: str
    action: str
    description: str
    context: str = "global"
    menu_action_attr: Optional[str] = None


SHORTCUTS: Tuple[ShortcutEntry, ...] = (
    ShortcutEntry("undo", "Ctrl+Z", "Undo", "Undo last annotation change", menu_action_attr="undo_act"),
    ShortcutEntry(
        "redo",
        "Ctrl+Shift+Z",
        "Redo",
        "Redo last undone annotation change",
        menu_action_attr="redo_act",
    ),
    ShortcutEntry("measure", "Ctrl+M", "Measure", "Open measurement/results panel", menu_action_attr="measure_act"),
    ShortcutEntry(
        "command_palette",
        "Ctrl+Shift+P",
        "Command Palette",
        "Open command palette",
        menu_action_attr="command_palette_act",
    ),
    ShortcutEntry("jump_frame", "Ctrl+G", "Jump to Frame", "Open jump-to-frame dialog", menu_action_attr="jump_to_frame_act"),
    ShortcutEntry("jump_z", "Ctrl+Shift+G", "Jump to Z Slice", "Open jump-to-Z dialog", menu_action_attr="jump_to_z_act"),
    ShortcutEntry(
        "help_shortcuts",
        "F1",
        "Keyboard Shortcuts",
        "Show keyboard shortcuts reference",
        menu_action_attr="shortcuts_act",
    ),
    ShortcutEntry("contextual_help", "Shift+F1", "Contextual Help", "Show context-specific help"),
    ShortcutEntry("play_pause", "Space", "Play/Pause", "Toggle time-series playback"),
    ShortcutEntry("nav_time_prev", "Left", "Navigate Time", "Move backward in time"),
    ShortcutEntry("nav_time_next", "Right", "Navigate Time", "Move forward in time"),
    ShortcutEntry("nav_z_prev", "Up", "Navigate Z", "Move up in Z-stack"),
    ShortcutEntry("nav_z_next", "Down", "Navigate Z", "Move down in Z-stack"),
    ShortcutEntry("accept_suggestion", "A", "Accept Suggestion", "Accept current suggestion (assist mode)"),
    ShortcutEntry("reject_suggestion", "R", "Reject Suggestion", "Reject current suggestion (assist mode)"),
    ShortcutEntry("next_suggestion", "N", "Next Suggestion", "Jump to next uncertain suggestion"),
    ShortcutEntry("prev_suggestion", "P", "Previous Suggestion", "Jump to previous uncertain suggestion"),
    ShortcutEntry(
        "review_context_pack",
        "Ctrl+Alt+R",
        "Review Context Pack",
        "Toggle right-dock review context pack",
        menu_action_attr="review_context_pack_act",
    ),
    ShortcutEntry("reset_view", "Ctrl+R", "Reset View", "Reset zoom/contrast"),
    ShortcutEntry("clear_roi", "Shift+R", "Clear ROI", "Clear current ROI when ROI tool active"),
    ShortcutEntry("delete_selected", "Delete / Backspace", "Delete Point", "Delete selected annotation(s)"),
    ShortcutEntry("cycle_colormap", "C", "Cycle Colormap", "Cycle current colormap"),
    ShortcutEntry("quick_save", "S", "Quick Save CSV", "Quick-save annotations CSV"),
)


def all_shortcuts() -> Tuple[ShortcutEntry, ...]:
    return SHORTCUTS


def detect_conflicts(entries: Iterable[ShortcutEntry]) -> List[Tuple[str, str, str]]:
    """Return duplicate (context, shortcut) conflicts."""
    seen: dict[tuple[str, str], str] = {}
    conflicts: List[Tuple[str, str, str]] = []
    for entry in entries:
        key = (entry.context.lower(), entry.shortcut.lower())
        if key in seen:
            conflicts.append((entry.shortcut, seen[key], entry.id))
        else:
            seen[key] = entry.id
    return conflicts


def dialog_rows() -> List[Tuple[str, str, str]]:
    """Rows for KeyboardShortcutsDialog table."""
    rows = [(s.shortcut, s.action, s.description) for s in SHORTCUTS]
    return rows


def apply_menu_shortcuts(window) -> None:
    """Apply registered shortcuts to menu/toolbar Qt actions when available."""
    for entry in SHORTCUTS:
        if not entry.menu_action_attr:
            continue
        action = getattr(window, entry.menu_action_attr, None)
        if action is not None:
            action.setShortcut(entry.shortcut)


def qt_match(event, key: int, modifiers: Any = None) -> bool:
    if QtCore is None:
        return False
    if modifiers is None:
        modifiers = QtCore.Qt.KeyboardModifier.NoModifier
    return event.key() == key and event.modifiers() == modifiers


def matplotlib_key_bindings() -> dict[str, str]:
    """Map Matplotlib key string -> action id."""
    return {
        "r": "reset_view",
        "c": "cycle_colormap",
        "s": "quick_save",
    }


def qt_key_bindings() -> tuple[tuple[int, Any, str], ...]:
    """Map Qt key/modifier pairs -> action id."""
    if QtCore is None:
        return ()
    return (
        (QtCore.Qt.Key_Left, QtCore.Qt.KeyboardModifier.NoModifier, "nav_time_prev"),
        (QtCore.Qt.Key_Right, QtCore.Qt.KeyboardModifier.NoModifier, "nav_time_next"),
        (QtCore.Qt.Key_Up, QtCore.Qt.KeyboardModifier.NoModifier, "nav_z_prev"),
        (QtCore.Qt.Key_Down, QtCore.Qt.KeyboardModifier.NoModifier, "nav_z_next"),
        (QtCore.Qt.Key_Space, QtCore.Qt.KeyboardModifier.NoModifier, "play_pause"),
        (QtCore.Qt.Key_F1, QtCore.Qt.KeyboardModifier.ShiftModifier, "contextual_help"),
        (QtCore.Qt.Key_Delete, QtCore.Qt.KeyboardModifier.NoModifier, "delete_selected"),
        (QtCore.Qt.Key_Backspace, QtCore.Qt.KeyboardModifier.NoModifier, "delete_selected"),
        (QtCore.Qt.Key_A, QtCore.Qt.KeyboardModifier.NoModifier, "accept_suggestion"),
        (QtCore.Qt.Key_R, QtCore.Qt.KeyboardModifier.ShiftModifier, "clear_roi"),
        (QtCore.Qt.Key_N, QtCore.Qt.KeyboardModifier.NoModifier, "next_suggestion"),
        (QtCore.Qt.Key_P, QtCore.Qt.KeyboardModifier.NoModifier, "prev_suggestion"),
        (QtCore.Qt.Key_R, QtCore.Qt.KeyboardModifier.ControlModifier, "reset_view"),
        (QtCore.Qt.Key_R, QtCore.Qt.KeyboardModifier.NoModifier, "reject_suggestion"),
    )
