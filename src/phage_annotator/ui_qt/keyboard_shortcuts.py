"""Keyboard shortcut management and conflict detection.

This module provides a comprehensive keyboard shortcut system with:
- Centralized shortcut registry
- Conflict detection and reporting
- Context-aware shortcut dispatch
- Shortcut persistence and configuration
"""

from __future__ import annotations

from phage_annotator.ui_qt.keyboard_shortcut_types import (
    ShortcutContext,
    ShortcutDefinition,
    ShortcutConflict,
)
from phage_annotator.ui_qt.keyboard_manager_dispatch import KeyboardManagerDispatch
from phage_annotator.ui_qt.keyboard_manager_conflicts import KeyboardManagerConflicts
from phage_annotator.ui_qt.keyboard_manager_persistence import KeyboardManagerPersistence


class KeyboardShortcutManager(
    KeyboardManagerDispatch,
    KeyboardManagerConflicts,
    KeyboardManagerPersistence,
):
    """Centralized keyboard shortcut management with conflict detection."""

    # Predefined shortcut categories
    NAVIGATION = "navigation"
    ANNOTATION = "annotation"
    EDITING = "editing"
    VIEW = "view"
    TOOL = "tool"
    CONTROL = "control"
    PLAYBACK = "playback"
