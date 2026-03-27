"""Keyboard shortcuts for rapid modality and display control.

This module defines and manages keyboard shortcuts for the application,
including modality switching, display control, and analysis commands.
"""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets
from typing import Callable, Dict, List, Tuple, Optional


class KeyboardShortcutManager:
    """Manages keyboard shortcuts for the application.
    
    Provides centralized management of keyboard shortcuts with proper
    conflict resolution and user customization support.
    """

    def __init__(self, main_window: QtWidgets.QMainWindow):
        """Initialize keyboard shortcut manager.
        
        Args:
            main_window: Main application window
        """
        self.main_window = main_window
        self._shortcuts: Dict[str, QtWidgets.QShortcut] = {}
        self._registered_actions: Dict[str, Tuple[str, str, Callable]] = {}
        self._initialize_shortcuts()

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

    def register_action(
        self,
        action_id: str,
        shortcut_key: str,
        description: str,
        callback: Callable[[], None]
    ) -> None:
        """Register a keyboard shortcut with action.
        
        Args:
            action_id: Unique identifier for the action
            shortcut_key: Key sequence (e.g., "Ctrl+C", "Shift+A")
            description: Human-readable description
            callback: Function to call when shortcut is triggered
        """
        self._registered_actions[action_id] = (shortcut_key, description, callback)
        
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence(shortcut_key),
            self.main_window
        )
        shortcut.activated.connect(callback)
        self._shortcuts[action_id] = shortcut

    def get_shortcut(self, action_id: str) -> Optional[str]:
        """Get shortcut key sequence for an action.
        
        Args:
            action_id: Action identifier
            
        Returns:
            Shortcut key sequence or None if not found
        """
        if action_id in self._registered_actions:
            return self._registered_actions[action_id][0]
        return None

    def get_description(self, action_id: str) -> Optional[str]:
        """Get description for an action.
        
        Args:
            action_id: Action identifier
            
        Returns:
            Description or None if not found
        """
        if action_id in self._registered_actions:
            return self._registered_actions[action_id][1]
        return None

    def get_all_shortcuts(self) -> List[Tuple[str, str, str]]:
        """Get all registered shortcuts.
        
        Returns:
            List of (action_id, shortcut_key, description) tuples
        """
        return [
            (action_id, shortcut_key, description)
            for action_id, (shortcut_key, description, _)
            in self._registered_actions.items()
        ]

    # Modality action handlers
    def _switch_modality(self, idx: int) -> None:
        """Switch to specified modality."""
        if 0 <= idx < len(getattr(self.main_window, "images", []) or []):
            self.main_window._set_fov(idx)

    def _add_modality(self) -> None:
        """Add new modality (placeholder - requires session integration)."""
        # This will be implemented in main window integration
        pass

    def _remove_modality(self) -> None:
        """Remove current modality (placeholder - requires session integration)."""
        # This will be implemented in main window integration
        pass

    def _rename_modality(self) -> None:
        """Rename current modality (placeholder - requires session integration)."""
        # This will be implemented in main window integration
        pass

    # Display action handlers
    def _open_contrast_dialog(self) -> None:
        """Open contrast adjustment dialog."""
        if hasattr(self.main_window, '_on_contrast_dialog'):
            self.main_window._on_contrast_dialog()

    def _reset_contrast(self) -> None:
        """Reset contrast to default."""
        if hasattr(self.main_window, 'reset_contrast'):
            self.main_window.reset_contrast()

    def _auto_contrast(self) -> None:
        """Apply auto-contrast to current view."""
        if hasattr(self.main_window, '_auto_contrast'):
            self.main_window._auto_contrast()

    # Playback action handlers
    def _toggle_playback(self) -> None:
        """Toggle play/pause."""
        if hasattr(self.main_window, 'play_t_btn'):
            self.main_window.play_t_btn.click()

    def _next_frame(self) -> None:
        """Advance to next frame."""
        if hasattr(self.main_window, 't_plus_button'):
            self.main_window.t_plus_button.click()

    def _prev_frame(self) -> None:
        """Go back to previous frame."""
        if hasattr(self.main_window, 't_minus_button'):
            self.main_window.t_minus_button.click()

    # Zoom action handlers
    def _toggle_zoom_link(self) -> None:
        """Toggle zoom/pan linking between modalities."""
        if hasattr(self.main_window, '_toggle_zoom_link'):
            self.main_window._toggle_zoom_link()

    def _reset_zoom(self) -> None:
        """Reset zoom to fit entire image."""
        if hasattr(self.main_window, '_reset_zoom'):
            self.main_window._reset_zoom()

    # Analysis action handlers
    def _open_threshold(self) -> None:
        """Open threshold analysis panel."""
        if hasattr(self.main_window, '_open_threshold'):
            self.main_window._open_threshold()

    def _open_particles(self) -> None:
        """Open particle analysis panel."""
        if hasattr(self.main_window, '_open_particles'):
            self.main_window._open_particles()

    # ROI Manager action handlers
    def _roi_add(self) -> None:
        """Add ROI from current selection."""
        if hasattr(self.main_window, '_roi_mgr_add'):
            self.main_window._roi_mgr_add()

    def _roi_delete(self) -> None:
        """Delete selected ROI(s)."""
        if hasattr(self.main_window, '_roi_mgr_delete'):
            self.main_window._roi_mgr_delete()

    def _roi_duplicate(self) -> None:
        """Duplicate selected ROI."""
        if hasattr(self.main_window, '_roi_mgr_duplicate'):
            self.main_window._roi_mgr_duplicate()

    def _roi_rename(self) -> None:
        """Rename selected ROI."""
        if hasattr(self.main_window, '_roi_mgr_rename'):
            self.main_window._roi_mgr_rename()

    def _roi_deselect(self) -> None:
        """Deselect ROI without deleting."""
        if hasattr(self.main_window, '_roi_mgr_deselect'):
            self.main_window._roi_mgr_deselect()

    def _roi_update(self) -> None:
        """Update ROI geometry from current selection."""
        if hasattr(self.main_window, '_roi_mgr_update'):
            self.main_window._roi_mgr_update()

    def _roi_bind_to_slice(self) -> None:
        """Bind selected ROI(s) to current slice."""
        if hasattr(self.main_window, '_roi_mgr_batch_bind_to_slice'):
            self.main_window._roi_mgr_batch_bind_to_slice()

    def _roi_undo(self) -> None:
        """Undo last ROI operation."""
        if hasattr(self.main_window, '_roi_mgr_undo'):
            self.main_window._roi_mgr_undo()

    def _roi_redo(self) -> None:
        """Redo last undone ROI operation."""
        if hasattr(self.main_window, '_roi_mgr_redo'):
            self.main_window._roi_mgr_redo()

    def show_shortcuts_help(self) -> None:
        """Display all available shortcuts in a help dialog."""
        shortcuts = self.get_all_shortcuts()
        
        text = "<h3>Keyboard Shortcuts</h3><table border='1'>"
        text += "<tr><th>Action</th><th>Shortcut</th></tr>"
        
        for action_id, shortcut_key, description in sorted(
            shortcuts, key=lambda x: x[1]
        ):
            text += f"<tr><td>{description}</td><td><code>{shortcut_key}</code></td></tr>"
        
        text += "</table>"
        
        dialog = QtWidgets.QDialog(self.main_window)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.setMinimumWidth(500)
        
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        
        ok_button = QtWidgets.QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        
        dialog.setLayout(layout)
        dialog.exec()


# Import at module level for type hints
from matplotlib.backends.qt_compat import QtGui
