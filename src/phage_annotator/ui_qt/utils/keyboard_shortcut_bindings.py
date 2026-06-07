"""Keyboard shortcut management."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

class KeyboardShortcutBindingsMixin:
    def _initialize_shortcuts(self) -> None:
        """Initialize all keyboard shortcuts."""
        # DISABLED: All keyboard shortcuts are disabled for normal working
        return

        # Modality management shortcuts
        self.register_action(
            "add_modality",
            "Ctrl+Shift+N",
            "Add new modality",
            self._add_modality
        )

        self.register_action(
            "remove_modality",
            "Ctrl+Shift+X",
            "Remove current modality",
            self._remove_modality
        )

        self.register_action(
            "rename_modality",
            "Ctrl+Shift+R",
            "Rename current modality",
            self._rename_modality
        )

        # Display & contrast shortcuts
        self.register_action(
            "open_contrast_dialog",
            "Ctrl+L",
            "Open contrast adjustment dialog",
            self._open_contrast_dialog
        )

        self.register_action(
            "reset_contrast",
            "Ctrl+Alt+L",
            "Reset contrast to default",
            self._reset_contrast
        )

        self.register_action(
            "auto_contrast",
            "Shift+A",
            "Apply auto-contrast",
            self._auto_contrast
        )

        # Playback shortcuts
        self.register_action(
            "play_pause",
            "Space",
            "Play/pause playback",
            self._toggle_playback
        )

        self.register_action(
            "next_frame",
            "Right",
            "Advance to next frame",
            self._next_frame
        )

        self.register_action(
            "prev_frame",
            "Left",
            "Go back to previous frame",
            self._prev_frame
        )

        # Zoom & link shortcuts
        self.register_action(
            "link_zoom_pan",
            "Ctrl+Alt+Z",
            "Toggle zoom/pan linking",
            self._toggle_zoom_link
        )

        self.register_action(
            "reset_zoom",
            "Ctrl+0",
            "Reset zoom to fit",
            self._reset_zoom
        )

        # Analysis shortcuts
        self.register_action(
            "open_threshold",
            "Ctrl+T",
            "Open threshold analysis",
            self._open_threshold
        )

        self.register_action(
            "open_particles",
            "Ctrl+P",
            "Open particle analysis",
            self._open_particles
        )

        # ROI Manager shortcuts
        self.register_action(
            "roi_add",
            "T",
            "Add ROI from current selection",
            self._roi_add
        )

        self.register_action(
            "roi_delete",
            "Delete",
            "Delete selected ROI(s)",
            self._roi_delete
        )

        self.register_action(
            "roi_duplicate",
            "Ctrl+D",
            "Duplicate selected ROI",
            self._roi_duplicate
        )

        self.register_action(
            "roi_rename",
            "F2",
            "Rename selected ROI",
            self._roi_rename
        )

        self.register_action(
            "roi_deselect",
            "Ctrl+Shift+D",
            "Deselect ROI without deleting",
            self._roi_deselect
        )

        self.register_action(
            "roi_update",
            "U",
            "Update ROI geometry from current selection",
            self._roi_update
        )

        self.register_action(
            "roi_bind_to_slice",
            "Ctrl+B",
            "Bind selected ROI(s) to current slice",
            self._roi_bind_to_slice
        )

        # ROI undo/redo shortcuts
        self.register_action(
            "roi_undo",
            "Ctrl+Z",
            "Undo last ROI operation",
            self._roi_undo
        )

        self.register_action(
            "roi_redo",
            "Ctrl+Shift+Z",
            "Redo last undone ROI operation",
            self._roi_redo
        )
