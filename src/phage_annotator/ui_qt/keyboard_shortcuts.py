"""Keyboard shortcut management and conflict detection.

This module provides a comprehensive keyboard shortcut system with:
- Centralized shortcut registry
- Conflict detection and reporting
- Context-aware shortcut dispatch
- Shortcut persistence and configuration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple

try:
    from matplotlib.backends.qt_compat import QtGui, QtCore
except ImportError:
    from PySide6 import QtGui, QtCore


class ShortcutContext(Enum):
    """Context where a shortcut can be active."""
    GLOBAL = "global"           # Always active
    EDITING = "editing"         # When editing annotations
    BROWSING = "browsing"       # When browsing (not editing)
    MODALITY_VIEW = "modality"  # When modality/image is loaded
    TEXT_INPUT = "text_input"   # Never active (text input focus)


@dataclass
class ShortcutDefinition:
    """Definition of a single keyboard shortcut."""
    
    id: str                          # Unique identifier (e.g., "nav.jump_to_frame")
    category: str                    # Category for organization (e.g., "navigation", "editing")
    description: str                 # Human-readable description
    default_sequence: str            # QKeySequence-compatible string (e.g., "Ctrl+G")
    alternative_sequences: List[str] = field(default_factory=list)  # Alternative shortcuts
    context: ShortcutContext = ShortcutContext.GLOBAL
    enabled: bool = True
    callback: Optional[Callable] = None  # Callable to invoke when shortcut activated
    
    def __eq__(self, other: object) -> bool:
        """Compare shortcuts by ID."""
        if not isinstance(other, ShortcutDefinition):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash by ID."""
        return hash(self.id)
    
    def all_sequences(self) -> List[str]:
        """Return all key sequences (primary + alternatives)."""
        return [self.default_sequence] + self.alternative_sequences


@dataclass
class ShortcutConflict:
    """Report of a shortcut conflict between two shortcuts."""
    
    shortcut_a: ShortcutDefinition
    shortcut_b: ShortcutDefinition
    sequence: str  # The conflicting key sequence
    severity: str = "warning"  # "warning" or "error"
    
    def __str__(self) -> str:
        """Format conflict as human-readable string."""
        return (
            f"Shortcut conflict on '{self.sequence}':\n"
            f"  [{self.shortcut_a.category}] {self.shortcut_a.description} "
            f"(ID: {self.shortcut_a.id})\n"
            f"  [{self.shortcut_b.category}] {self.shortcut_b.description} "
            f"(ID: {self.shortcut_b.id})\n"
            f"Severity: {self.severity}"
        )


class KeyboardShortcutManager:
    """Centralized keyboard shortcut management with conflict detection."""
    
    # Predefined shortcut categories
    NAVIGATION = "navigation"
    ANNOTATION = "annotation"
    EDITING = "editing"
    VIEW = "view"
    TOOL = "tool"
    CONTROL = "control"
    PLAYBACK = "playback"
    
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
    
    def _detect_conflicts_for_shortcut(
        self,
        shortcut: ShortcutDefinition,
    ) -> None:
        """Detect conflicts for a single shortcut.
        
        Parameters
        ----------
        shortcut : ShortcutDefinition
            Shortcut to check.
        """
        if not shortcut.enabled:
            return
        
        for seq in shortcut.all_sequences():
            other_shortcuts = self._sequences_to_shortcuts.get(seq, [])
            
            for other in other_shortcuts:
                if other.id == shortcut.id or not other.enabled:
                    continue
                
                # Check if contexts are compatible (both active at same time)
                if self._contexts_conflict(shortcut.context, other.context):
                    # Check if already reported
                    conflict = ShortcutConflict(
                        shortcut_a=shortcut,
                        shortcut_b=other,
                        sequence=seq,
                    )
                    
                    if not any(
                        (c.shortcut_a.id == conflict.shortcut_a.id and
                         c.shortcut_b.id == conflict.shortcut_b.id and
                         c.sequence == conflict.sequence)
                        for c in self._conflicts
                    ):
                        self._conflicts.append(conflict)
    
    @staticmethod
    def _contexts_conflict(
        ctx1: ShortcutContext,
        ctx2: ShortcutContext,
    ) -> bool:
        """Check if two contexts can be active simultaneously.
        
        Parameters
        ----------
        ctx1, ctx2 : ShortcutContext
            Contexts to check.
        
        Returns
        -------
        bool
            True if both contexts can be active at the same time.
        """
        # TEXT_INPUT never conflicts (it disables all others)
        if ctx1 == ShortcutContext.TEXT_INPUT or ctx2 == ShortcutContext.TEXT_INPUT:
            return False
        
        # GLOBAL is compatible with everything
        if ctx1 == ShortcutContext.GLOBAL or ctx2 == ShortcutContext.GLOBAL:
            return True
        
        # EDITING and BROWSING are mutually exclusive
        if {ctx1, ctx2} == {ShortcutContext.EDITING, ShortcutContext.BROWSING}:
            return False
        
        # Same context always conflicts
        return ctx1 == ctx2
    
    def set_context_disabled(
        self,
        context: ShortcutContext,
        disabled: bool = True,
    ) -> None:
        """Disable all shortcuts in a specific context.
        
        Parameters
        ----------
        context : ShortcutContext
            Context to disable/enable.
        disabled : bool, default True
            If True, disable; if False, enable.
        """
        if disabled:
            self._disabled_contexts.add(context)
        else:
            self._disabled_contexts.discard(context)
    
    def is_context_active(self, context: ShortcutContext) -> bool:
        """Check if a context is currently active.
        
        Parameters
        ----------
        context : ShortcutContext
            Context to check.
        
        Returns
        -------
        bool
            True if context is active, False if disabled.
        """
        return context not in self._disabled_contexts
    
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
    
    def _register_default_shortcuts(self) -> None:
        """Register default keyboard shortcuts."""
        
        # Navigation shortcuts
        nav_shortcuts = [
            ShortcutDefinition(
                id="nav.jump_to_frame",
                category=self.NAVIGATION,
                description="Jump to frame (T)",
                default_sequence="Ctrl+G",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="nav.jump_to_z",
                category=self.NAVIGATION,
                description="Jump to Z slice",
                default_sequence="Ctrl+Shift+G",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="nav.next_frame",
                category=self.NAVIGATION,
                description="Next frame",
                default_sequence="Right",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="nav.prev_frame",
                category=self.NAVIGATION,
                description="Previous frame",
                default_sequence="Left",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="nav.next_z",
                category=self.NAVIGATION,
                description="Next Z slice",
                default_sequence="Down",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="nav.prev_z",
                category=self.NAVIGATION,
                description="Previous Z slice",
                default_sequence="Up",
                context=ShortcutContext.MODALITY_VIEW,
            ),
        ]
        
        # Undo/Redo shortcuts
        control_shortcuts = [
            ShortcutDefinition(
                id="control.undo",
                category=self.CONTROL,
                description="Undo last action",
                default_sequence="Ctrl+Z",
                context=ShortcutContext.GLOBAL,
            ),
            ShortcutDefinition(
                id="control.redo",
                category=self.CONTROL,
                description="Redo last undone action",
                default_sequence="Ctrl+Y",
                alternative_sequences=["Ctrl+Shift+Z"],
                context=ShortcutContext.GLOBAL,
            ),
        ]
        
        # Annotation shortcuts
        ann_shortcuts = [
            ShortcutDefinition(
                id="ann.new_annotation",
                category=self.ANNOTATION,
                description="Add annotation at cursor",
                default_sequence="Space",
                context=ShortcutContext.BROWSING,
            ),
            ShortcutDefinition(
                id="ann.delete_selected",
                category=self.ANNOTATION,
                description="Delete selected annotation",
                default_sequence="Delete",
                context=ShortcutContext.EDITING,
            ),
            ShortcutDefinition(
                id="ann.mark_uncertain",
                category=self.ANNOTATION,
                description="Mark selected as uncertain",
                default_sequence="Q",
                context=ShortcutContext.EDITING,
            ),
        ]
        
        # View shortcuts
        view_shortcuts = [
            ShortcutDefinition(
                id="view.zoom_in",
                category=self.VIEW,
                description="Zoom in",
                default_sequence="Ctrl++",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="view.zoom_out",
                category=self.VIEW,
                description="Zoom out",
                default_sequence="Ctrl+-",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="view.fit_window",
                category=self.VIEW,
                description="Fit to window",
                default_sequence="Ctrl+0",
                context=ShortcutContext.MODALITY_VIEW,
            ),
        ]
        
        # Register all
        for shortcut in nav_shortcuts + control_shortcuts + ann_shortcuts + view_shortcuts:
            self.register_shortcut(shortcut)
