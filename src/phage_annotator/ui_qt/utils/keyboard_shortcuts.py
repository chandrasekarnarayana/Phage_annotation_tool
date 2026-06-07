"""Keyboard shortcut management."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.utils.keyboard_shortcut_bindings import KeyboardShortcutBindingsMixin
from phage_annotator.ui_qt.utils.keyboard_shortcut_handlers import KeyboardShortcutHandlersMixin


class KeyboardShortcutManager(KeyboardShortcutBindingsMixin, KeyboardShortcutHandlersMixin):
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
