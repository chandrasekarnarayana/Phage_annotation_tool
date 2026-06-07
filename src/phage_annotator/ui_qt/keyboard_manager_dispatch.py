"""Shortcut dispatch and activation: registration, lookup, and Qt action creation."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set

try:
    from matplotlib.backends.qt_compat import QtGui, QtCore
except ImportError:
    from PySide6 import QtGui, QtCore

from phage_annotator.ui_qt.keyboard_shortcut_types import (
    ShortcutContext,
    ShortcutDefinition,
    ShortcutConflict,
)


class KeyboardManagerDispatch:
    """Shortcut registration, lookup, and Qt QAction creation."""

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        """Initialize shortcut manager.

        Parameters
        ----------
        parent : QtCore.QObject, optional
            Parent Qt object for signal/slot connections.
        """
        self.parent = parent
        self._shortcuts: Dict[str, ShortcutDefinition] = {}
        self._sequences_to_shortcuts: Dict[str, List[ShortcutDefinition]] = {}
        self._qt_actions: Dict[str, QtGui.QAction] = {}
        self._conflicts: List[ShortcutConflict] = []
        self._disabled_contexts: Set[ShortcutContext] = set()

        # Populate with default shortcuts
        self._register_default_shortcuts()

    def register_shortcut(
        self,
        shortcut: ShortcutDefinition,
        *,
        override: bool = False,
    ) -> bool:
        """Register a new shortcut definition.

        Parameters
        ----------
        shortcut : ShortcutDefinition
            Shortcut definition to register.
        override : bool, default False
            If True, replace existing shortcut with same ID.

        Returns
        -------
        bool
            True if registered successfully, False if ID already exists
            and override=False.
        """
        if shortcut.id in self._shortcuts and not override:
            return False

        # Remove old sequences if overriding
        if shortcut.id in self._shortcuts:
            old_shortcut = self._shortcuts[shortcut.id]
            for seq in old_shortcut.all_sequences():
                if seq in self._sequences_to_shortcuts:
                    self._sequences_to_shortcuts[seq] = [
                        s for s in self._sequences_to_shortcuts[seq]
                        if s.id != shortcut.id
                    ]

        # Register new shortcut
        self._shortcuts[shortcut.id] = shortcut

        # Map sequences to shortcuts
        for seq in shortcut.all_sequences():
            if seq not in self._sequences_to_shortcuts:
                self._sequences_to_shortcuts[seq] = []
            self._sequences_to_shortcuts[seq].append(shortcut)

        # Detect new conflicts
        self._detect_conflicts_for_shortcut(shortcut)

        return True

    def unregister_shortcut(self, shortcut_id: str) -> bool:
        """Unregister a shortcut by ID.

        Parameters
        ----------
        shortcut_id : str
            Shortcut ID to remove.

        Returns
        -------
        bool
            True if unregistered, False if not found.
        """
        if shortcut_id not in self._shortcuts:
            return False

        shortcut = self._shortcuts.pop(shortcut_id)

        # Remove from sequence mapping
        for seq in shortcut.all_sequences():
            if seq in self._sequences_to_shortcuts:
                self._sequences_to_shortcuts[seq] = [
                    s for s in self._sequences_to_shortcuts[seq]
                    if s.id != shortcut_id
                ]

        # Re-detect conflicts
        self._conflicts = []
        for s in self._shortcuts.values():
            self._detect_conflicts_for_shortcut(s)

        # Remove Qt action if exists
        if shortcut_id in self._qt_actions:
            self._qt_actions.pop(shortcut_id)

        return True

    def get_shortcut(self, shortcut_id: str) -> Optional[ShortcutDefinition]:
        """Retrieve shortcut definition by ID.

        Parameters
        ----------
        shortcut_id : str
            Shortcut ID.

        Returns
        -------
        ShortcutDefinition or None
            Shortcut definition if found, None otherwise.
        """
        return self._shortcuts.get(shortcut_id)

    def get_shortcuts_by_category(
        self,
        category: str,
    ) -> List[ShortcutDefinition]:
        """Get all shortcuts in a category.

        Parameters
        ----------
        category : str
            Category name.

        Returns
        -------
        list of ShortcutDefinition
            Shortcuts in the category.
        """
        return [s for s in self._shortcuts.values() if s.category == category]

    def get_all_shortcuts(self) -> List[ShortcutDefinition]:
        """Get all registered shortcuts.

        Returns
        -------
        list of ShortcutDefinition
            All shortcuts, sorted by category then description.
        """
        return sorted(
            self._shortcuts.values(),
            key=lambda s: (s.category, s.description),
        )

    def get_shortcuts_for_sequence(
        self,
        sequence: str,
    ) -> List[ShortcutDefinition]:
        """Get shortcuts matching a key sequence.

        Parameters
        ----------
        sequence : str
            QKeySequence-compatible string.

        Returns
        -------
        list of ShortcutDefinition
            Shortcuts matching the sequence.
        """
        return self._sequences_to_shortcuts.get(sequence, [])

    def detect_conflicts(self) -> List[ShortcutConflict]:
        """Detect all current shortcut conflicts.

        Conflicts occur when enabled shortcuts in compatible contexts
        share the same key sequence.

        Returns
        -------
        list of ShortcutConflict
            List of detected conflicts.
        """
        return list(self._conflicts)

    def create_qt_action(
        self,
        shortcut_id: str,
        parent: QtCore.QObject,
        triggered_callback: Optional[Callable] = None,
    ) -> Optional[QtGui.QAction]:
        """Create a Qt action for a shortcut.

        Parameters
        ----------
        shortcut_id : str
            Shortcut ID.
        parent : QtCore.QObject
            Parent Qt object.
        triggered_callback : Callable, optional
            Callback to invoke when action triggered.

        Returns
        -------
        QtGui.QAction or None
            Created action, or None if shortcut not found.
        """
        shortcut = self.get_shortcut(shortcut_id)
        if not shortcut:
            return None

        action = QtGui.QAction(shortcut.description, parent)
        action.setShortcut(QtGui.QKeySequence(shortcut.default_sequence))

        # Set callback
        callback = triggered_callback or shortcut.callback
        if callback:
            action.triggered.connect(callback)

        # Store reference
        self._qt_actions[shortcut_id] = action

        return action

    def export_shortcut_matrix(self) -> str:
        """Export shortcuts as human-readable matrix.

        Returns
        -------
        str
            Formatted table of all shortcuts.
        """
        lines = [
            "Shortcut Matrix",
            "=" * 100,
            f"{'Category':<15} {'Description':<40} {'Primary':<20} {'Alternatives':<20}",
            "-" * 100,
        ]

        for shortcut in self.get_all_shortcuts():
            alts = ", ".join(shortcut.alternative_sequences) or "—"
            lines.append(
                f"{shortcut.category:<15} {shortcut.description:<40} "
                f"{shortcut.default_sequence:<20} {alts:<20}"
            )

        lines.append("=" * 100)
        return "\n".join(lines)
